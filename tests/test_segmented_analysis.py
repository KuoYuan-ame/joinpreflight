"""v7.2 regression tests; Olist download not required."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from joinpreflight.segmented_analysis import (
    classify_orders, safe_spearman, analyze_segments, verify_overall_pair,
    analyze_and_export, plot_overview, plot_correlation_panels,
)


def toy_frame(n=120):
    rng = np.random.default_rng(109)
    item_counts = np.array([0]*8 + [1]*64 + [2]*24 + [3]*24)
    assert len(item_counts) == n
    payment = 70 + np.arange(n)*.37 + rng.normal(0,5,n)
    freight = payment*.12 + rng.normal(0,3,n)
    frame = pd.DataFrame({
        "order_id": [f"o_{i:04}" for i in range(n)],
        "item_count": item_counts,
        "payment_total": payment,
        "freight_total": freight,
        "avg_item_price": payment/(item_counts.clip(1)),
        "delivery_days": 10 + rng.normal(0, 2, n),
        "max_installments": rng.integers(1, 8, n),
    })
    return frame


def test_segments_are_disjoint_and_keep_zero_item_orders():
    data = classify_orders(toy_frame())
    assert data.segment.value_counts().to_dict() == {"Single":64,"Multi":48,"No items":8}
    assert len(data) == 120


def test_reject_duplicate_order_ids_and_negative_counts():
    d = toy_frame()
    d.loc[1, "order_id"] = d.loc[0, "order_id"]
    with pytest.raises(ValueError, match="unique"):
        classify_orders(d)
    d = toy_frame()
    d.loc[0,"item_count"] = -1
    with pytest.raises(ValueError, match="nonnegative"):
        classify_orders(d)


def test_safe_spearman_matches_known_monotone_and_ties():
    x = pd.Series([1,1,2,3,4,5,5,6])
    y = pd.Series([10,10,20,30,40,50,50,60])
    r = safe_spearman(x,y,min_pairs=3)
    assert r["status"] == "ok"
    assert abs(r["rho"]-1) < 1e-12
    assert r["n"] == 8


def test_constant_and_low_n_do_not_warn_or_invent_rho():
    a = pd.Series([1]*30)
    b = pd.Series(range(30))
    assert safe_spearman(a,b,min_pairs=10)["status"] == "constant_input"
    assert safe_spearman(a,b,min_pairs=35)["status"] == "insufficient_pairs"
    assert safe_spearman(a,b,min_pairs=10)["rho"] is None


def test_correlation_uses_pairwise_n_not_complete_case_n():
    d=toy_frame()
    d.loc[9:14,"freight_total"]=np.nan
    d.loc[15:20,"delivery_days"]=np.nan
    res=analyze_segments(d,features=["freight_total","delivery_days"],min_pairs=10)
    pairs=res["correlations"].set_index("segment")
    assert pairs.loc["Single","n"] == 52  # 64 - 6 - 6
    assert res["group_counts"]["No items"] == 8
    assert len(res["differences"]) == 1


def test_constant_item_count_in_single_is_explicitly_undefined():
    res=analyze_segments(toy_frame(),features=["item_count","payment_total"],min_pairs=10)
    r=res["correlations"].set_index("segment")
    assert r.loc["Single","status"] == "constant_input"
    assert pd.isna(r.loc["Single","rho"])
    assert res["differences"].iloc[0]["status"] == "not_comparable"


def test_overall_rho_independent_implementations_agree():
    r=verify_overall_pair(toy_frame())
    assert r["status"] == "pass"
    assert r["n"] == 120
    assert r["absolute_difference"] < 1e-10


def test_group_summary_preserves_missing_monetary_values():
    d=toy_frame()
    d.loc[11,"payment_total"] = np.nan
    res=analyze_segments(d,features=["payment_total","freight_total"],min_pairs=10)
    s=res["group_summary"].set_index(["segment","feature"])
    assert s.loc[("Single","payment_total"),"missing"] == 1
    assert s.loc[("Single","payment_total"),"non_null"] == 63


def test_invalid_variables_and_min_pairs_rejected():
    with pytest.raises(ValueError,match="Unknown"):
        analyze_segments(toy_frame(),features=["payment_total","not_a_feature"])
    with pytest.raises(ValueError,match="Repeated"):
        analyze_segments(toy_frame(),features=["payment_total","payment_total"])
    with pytest.raises(ValueError,match="min_pairs"):
        analyze_segments(toy_frame(),min_pairs=1)


def test_figures_generate_without_nonexistent_external_data(tmp_path):
    result=analyze_segments(toy_frame())
    a=tmp_path/"overview.png"
    b=tmp_path/"heatmap.png"
    plot_overview(result,a)
    plot_correlation_panels(result,b)
    for f in (a,b,a.with_suffix(".svg"),b.with_suffix(".svg")):
        assert f.exists() and f.stat().st_size > 300


def test_end_to_end_csv_joins_and_export(tmp_path):
    order_rows=[]; items=[]; payments=[]
    for i in range(85):
        k=f"ID{i:03d}"
        order_rows.append({"order_id":k,"order_purchase_timestamp":"2024-01-01",
                           "order_delivered_customer_date":str(pd.Timestamp("2024-01-11")+pd.Timedelta(days=i%9)),
                           "order_estimated_delivery_date":"2024-01-13"})
        count=0 if i < 5 else (1 if i < 50 else 2)
        for j in range(count):
            items.append({"order_id":k,"price":10+i, "freight_value":2+i*.03+j})
        payments.append({"order_id":k,"payment_value":20+i*.5,"payment_installments":1+(i%7),
                         "payment_type":"credit_card"})
    path_orders=tmp_path/"orders.csv"; path_items=tmp_path/"items.csv"; path_payments=tmp_path/"payments.csv"
    pd.DataFrame(order_rows).to_csv(path_orders,index=False)
    pd.DataFrame(items).to_csv(path_items,index=False)
    pd.DataFrame(payments).to_csv(path_payments,index=False)
    meta=analyze_and_export(path_orders,path_items,path_payments, tmp_path/"sample",min_pairs=10)
    assert meta["group_counts"] == {"No items":5,"Single":45,"Multi":35}
    assert meta["consistency_check"]["status"] == "pass"
    assert len(pd.read_csv(tmp_path/"sample_rho_differences.csv")) == 10
    for name in ("sample_overview.png","sample_overview.svg",
                 "sample_correlations.png","sample_correlations.svg",
                 "sample_group_summary.csv","sample_pair_correlations.csv",
                 "sample_rho_differences.csv","sample_metadata.json"):
        assert (tmp_path/name).exists()
    actual=json.loads((tmp_path/"sample_metadata.json").read_text(encoding="utf-8"))
    assert actual["total_orders"] == 85
