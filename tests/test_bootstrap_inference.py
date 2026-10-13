"""Isolated v7.3 tests: no external Olist download is necessary."""
import json
import numpy as np
import pandas as pd
import pytest
from joinpreflight.bootstrap_inference import (
    bootstrap_segment_differences, plot_bootstrap_forest,
    analyze_and_export_bootstrap, _rank_pearson,
)
from joinpreflight.segmented_analysis import safe_spearman


def sample_orders(seed=7):
    rng = np.random.default_rng(seed)
    n1, n2 = 90, 45
    n = n1 + n2 + 10
    counts = [0]*10 + [1]*n1 + [2]*n2
    freight = rng.normal(45, 13, n)
    cost = rng.normal(120, 30, n)
    payment = cost.copy()
    # Single group: strong relationship, Multi group: weak relationship
    payment[10:100] = 3 * freight[10:100] + rng.normal(0, 3, n1)
    payment[100:] = rng.normal(100, 30, n2)
    return pd.DataFrame({
        "order_id": [f"ord{i:04}" for i in range(n)],
        "item_count": counts,
        "freight_total": freight,
        "payment_total": payment,
        "avg_item_price": cost,
        "max_installments": rng.integers(1, 6, n),
        "delivery_days": rng.normal(14, 5, n),
    })


def test_rank_pearson_matches_pandas_with_ties():
    a = np.array([1, 1, 3, 5, 5, 8], dtype=float)
    b = np.array([2, 4, 4, 6, 9, 9], dtype=float)
    assert _rank_pearson(a, b) == pytest.approx(safe_spearman(pd.Series(a), pd.Series(b), min_pairs=3)["rho"])


def test_bootstrap_reproducible_and_interval_finite():
    opts = dict(pairs=[("freight_total", "payment_total")], n_boot=100, seed=21, min_pairs=10)
    a = bootstrap_segment_differences(sample_orders(), **opts)
    b = bootstrap_segment_differences(sample_orders(), **opts)
    pd.testing.assert_frame_equal(a["pairs"], b["pairs"])
    record = a["pairs"].iloc[0]
    assert record["status"] == "ok"
    assert record["ci_low"] < record["ci_high"]
    assert record["ci_low"] <= record["delta_rho_multi_minus_single"] <= record["ci_high"]
    assert record["delta_rho_multi_minus_single"] < -0.6
    assert record["successful_replicates"] == 100
    assert a["group_counts"] == {"No items": 10, "Single": 90, "Multi": 45}


def test_bootstrap_point_estimate_matches_v72():
    from joinpreflight.segmented_analysis import analyze_segments
    frame = sample_orders()
    v72 = analyze_segments(frame, features=["payment_total", "freight_total"], min_pairs=10)
    v73 = bootstrap_segment_differences(frame, pairs=[("payment_total", "freight_total")],
                                         n_boot=50, min_pairs=10)
    assert v73["pairs"].iloc[0]["delta_rho_multi_minus_single"] == pytest.approx(
        v72["differences"].iloc[0]["delta_rho_multi_minus_single"], abs=1e-12)


def test_pairwise_valid_orders_not_imputed_to_zero():
    frame = sample_orders()
    frame.loc[10:16, "freight_total"] = np.nan
    result = bootstrap_segment_differences(frame, pairs=[("payment_total", "freight_total")],
                                            n_boot=50, min_pairs=10)
    assert result["pairs"].iloc[0]["n_single"] == 83
    assert result["pairs"].iloc[0]["n_multi"] == 45


def test_constant_group_reports_undefined_and_empty_ci():
    r = bootstrap_segment_differences(sample_orders(), pairs=[("item_count", "payment_total")],
                                      n_boot=50, min_pairs=10)["pairs"].iloc[0]
    assert r["single_status"] == "constant_input"
    assert r["status"] == "not_estimable"
    assert pd.isna(r["ci_low"])
    assert r["successful_replicates"] == 0


def test_low_n_status():
    frame = sample_orders()
    result = bootstrap_segment_differences(frame, pairs=[("freight_total", "payment_total")],
                                           n_boot=50, min_pairs=60)
    assert result["pairs"].iloc[0]["status"] == "not_estimable"
    assert result["pairs"].iloc[0]["multi_status"] == "insufficient_pairs"


@pytest.mark.parametrize("overrides", [
    {"n_boot": 10}, {"n_boot": 25.0}, {"confidence": 1},
    {"seed": -3}, {"min_pairs": 2},
    {"pairs": [("payment_total", "payment_total")]},
    {"pairs": [("payment_total", "freight_total"), ("freight_total", "payment_total")]},
    {"pairs": [("payment_total", "nonexistent")]},
])
def test_reject_invalid_configuration(overrides):
    with pytest.raises(ValueError):
        bootstrap_segment_differences(sample_orders(), **overrides)


def test_plot_outputs_and_handles_nonestimable(tmp_path):
    result = bootstrap_segment_differences(sample_orders(),
                 pairs=[("freight_total", "payment_total"), ("item_count", "payment_total")],
                 n_boot=50, min_pairs=10)
    fig = tmp_path/"forest.png"
    plot_bootstrap_forest(result, fig)
    for path in [fig, fig.with_suffix('.svg'), fig.with_suffix('.pdf')]:
        assert path.exists() and path.stat().st_size > 250


def test_end_to_end_csv_and_json_null_for_nonestimable(tmp_path):
    orders, items, payments = [], [], []
    for i in range(90):
        order_id = f"ORDER{i:03d}"
        orders.append({"order_id":order_id, "order_purchase_timestamp":"2024-01-01",
                       "order_delivered_customer_date": "2024-01-09",
                       "order_estimated_delivery_date":"2024-01-12"})
        count = 0 if i < 5 else (1 if i < 52 else 3)
        for j in range(count):
            items.append({"order_id": order_id, "price": 10+i*.35,
                          "freight_value": 2+j+i*.12})
        payments.append({"order_id":order_id,"payment_value":40+i*.75,
                         "payment_installments":1+(i%5), "payment_type":"credit_card"})
    files=[]
    for name,data in [("orders",orders),("items",items),("payments",payments)]:
        path=tmp_path/(name+'.csv')
        pd.DataFrame(data).to_csv(path,index=False)
        files.append(path)
    meta = analyze_and_export_bootstrap(*files, tmp_path/"demo", n_boot=50,
                    min_pairs=10, pairs=[("item_count", "payment_total"),
                                          ("payment_total", "freight_total")])
    assert meta["group_counts"] == {"No items":5, "Single":47, "Multi":38}
    assert meta["results"][0]["status"] == "not_estimable"
    assert meta["results"][0]["ci_low"] is None
    json_obj = json.loads((tmp_path/"demo_metadata.json").read_text(encoding="utf-8"))
    assert json_obj["results"][0]["ci_low"] is None
    assert len(pd.read_csv(tmp_path/"demo_results.csv")) == 2
    for ext in ['png','svg','pdf']:
        assert (tmp_path/f'demo_forest.{ext}').exists()
