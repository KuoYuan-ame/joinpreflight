"""v4 impact engine regression tests, independent of the Olist dataset."""
import pandas as pd
import pytest

from joinpreflight.metric_impact import analyze_metric_inflation


def sample():
    orders = pd.DataFrame({"order_id": ["A", "B", "C", "D"]})
    items = pd.DataFrame({"order_id": ["A", "A", "A", "B", "B", "C", "X"]})
    payments = pd.DataFrame({
        "order_id": ["A", "A", "B", "C", "X"],
        "payment_value": ["100.01", "0.02", "200.00", "50.00", "99.99"],
    })
    return orders, items, payments


def test_split_payments_and_unmatched_rows_are_handled_exactly():
    summary, top = analyze_metric_inflation(*sample())
    assert summary["correct_payment_total"] == pytest.approx(350.03)
    assert summary["naive_payment_total"] == pytest.approx(750.09)
    assert summary["inflation_amount"] == pytest.approx(400.06)
    assert summary["extra_join_rows"] == 3
    assert summary["orders_without_payment_records"] == 1
    assert summary["orders_without_items"] == 1
    assert summary["unmatched_item_rows_excluded"] == 1
    assert summary["unmatched_payment_rows_excluded"] == 1
    assert top["order_id"].tolist() == ["A", "B"]
    assert top["overcount_amount"].tolist() == pytest.approx([200.06, 200.0])


def test_monetary_ranking_differs_from_row_count_ranking():
    o = pd.DataFrame({"order_id": ["A", "B"]})
    i = pd.DataFrame({"order_id": ["A"] * 4 + ["B"] * 2})
    p = pd.DataFrame({"order_id": ["A", "B"], "payment_value": ["20.00", "500.00"]})
    _, top = analyze_metric_inflation(o, i, p)
    assert top["order_id"].tolist() == ["B", "A"]
    assert top["overcount_amount"].tolist() == [500.0, 60.0]


def test_duplicate_order_master_rejected():
    orders, items, payments = sample()
    orders = pd.concat([orders, orders.iloc[:1]], ignore_index=True)
    with pytest.raises(ValueError, match="unique join key"):
        analyze_metric_inflation(orders, items, payments)


@pytest.mark.parametrize("bad", ["-1.00", "NaN", "1.001", "Infinity", "oops", None])
def test_invalid_payment_amount_rejected(bad):
    orders, items, payments = sample()
    payments.loc[0, "payment_value"] = bad
    with pytest.raises(ValueError, match="Payment|Invalid"):
        analyze_metric_inflation(orders, items, payments)


def test_null_join_key_rejected():
    orders, items, payments = sample()
    items.loc[0, "order_id"] = None
    with pytest.raises(ValueError, match="Null join keys"):
        analyze_metric_inflation(orders, items, payments)


def test_no_money_inflation_and_zero_baseline_is_defined_as_none():
    orders = pd.DataFrame({"order_id": ["A", "B"]})
    items = pd.DataFrame({"order_id": ["A", "A", "B"]})
    payments = pd.DataFrame({"order_id": ["A"], "payment_value": ["0.00"]})
    summary, ranked = analyze_metric_inflation(orders, items, payments)
    assert summary["inflation_amount"] == 0
    assert summary["inflation_rate_pct"] is None
    assert ranked.empty


def test_with_no_item_rows_order_is_kept_once():
    orders = pd.DataFrame({"order_id": ["A", "B"]})
    items = pd.DataFrame({"order_id": ["A", "A"]})
    payments = pd.DataFrame({"order_id": ["A", "B"], "payment_value": ["10.00", "30.00"]})
    summary, _ = analyze_metric_inflation(orders, items, payments)
    assert summary["correct_payment_total"] == 40
    assert summary["naive_payment_total"] == 50
    assert summary["inflation_amount"] == 10


def test_top_n_is_exposure_only_not_baseline():
    s1, t1 = analyze_metric_inflation(*sample(), top_n=1)
    s2, t2 = analyze_metric_inflation(*sample(), top_n=10)
    assert len(t1) == 1 and len(t2) == 2
    assert s1["inflation_amount"] == s2["inflation_amount"]
    assert s1["top_n_inflation_share_pct"] < s2["top_n_inflation_share_pct"]
