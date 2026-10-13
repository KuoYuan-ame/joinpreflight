"""Exact (cent-based) payment inflation diagnostics for single-key LEFT JOINs.

We assume the metric is a nonnegative order-level amount with at most two
fractional decimal places. Rows in the payment table are aggregated by order
BEFORE analyzing how an order-to-item join replicates that amount.

No full orders x items join is materialized.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

import pandas as pd


def _to_cents(value: object) -> int:
    if pd.isna(value) or isinstance(value, bool):
        raise ValueError("Payment values must be finite, nonnegative amounts")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid payment amount: {value!r}") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("Payment values must be finite, nonnegative amounts")
    cents = amount * 100
    if cents != cents.to_integral_value():
        raise ValueError("Payment values may have at most two decimal places")
    if cents > 9_000_000_000_000_000:
        raise ValueError("Payment amount is too large for safe aggregation")
    return int(cents)


def analyze_metric_inflation(
    orders: pd.DataFrame,
    items: pd.DataFrame,
    payments: pd.DataFrame,
    on: str = "order_id",
    value: str = "payment_value",
    top_n: int = 10,
) -> tuple[dict, pd.DataFrame]:
    """Analyze naive SUM(payment) after orders LEFT JOIN items.

    Returns (summary, top_impact_orders). Payment records are FIRST aggregated
    to one row per order; payments without an order in ``orders`` are excluded
    and explicitly counted. Missing payments are not asserted to be zero.
    """
    if not isinstance(on, str) or not on:
        raise ValueError("on must be a nonempty column name")
    if not isinstance(value, str) or not value or value == on:
        raise ValueError("value must differ from the join key")
    if not isinstance(top_n, int) or isinstance(top_n, bool) or top_n < 1:
        raise ValueError("top_n must be a positive integer")
    for name, df, required in (
        ("orders", orders, [on]),
        ("items", items, [on]),
        ("payments", payments, [on, value]),
    ):
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"{name} must be a DataFrame")
        for col in required:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in {name}")
            if list(df.columns).count(col) != 1:
                raise ValueError(f"Duplicate column '{col}' in {name}")
        if df[on].isna().any():
            raise ValueError(f"Null join keys in {name}; impact analysis requires known order IDs")
    if orders[on].duplicated().any():
        raise ValueError("orders must contain one row per order_id (unique join key)")

    # Aggregate payment lines in Python integer cents; this avoids an
    # int64 GroupBy overflow even if many payment records share one order.
    payment_totals: dict = {}
    for key, raw_amount in zip(payments[on], payments[value]):
        payment_totals[key] = payment_totals.get(key, 0) + _to_cents(raw_amount)
    item_counts = items.groupby(on, sort=False).size().to_dict()
    order_ids = orders[on].tolist()

    order_set = set(order_ids)
    unmatched_item_rows = int((~items[on].isin(order_set)).sum())
    unmatched_payment_rows = int((~payments[on].isin(order_set)).sum())
    missing_payment_orders = sum(key not in payment_totals for key in order_ids)

    details = []
    correct_cents = 0
    naive_cents = 0
    extra_row_count = 0
    paid_affected = 0
    rows_multiple_items = 0
    orders_without_items = 0
    for key in order_ids:
        n = int(item_counts.get(key, 0))
        p = int(payment_totals.get(key, 0))
        multiplier = max(n, 1)
        extra = multiplier - 1
        correct_cents += p
        naive_cents += p * multiplier
        extra_row_count += extra
        if n == 0:
            orders_without_items += 1
        if n > 1:
            rows_multiple_items += 1
        if extra > 0 and p > 0:
            paid_affected += 1
            details.append({
                on: str(key),
                "item_rows": n,
                "payment_total": p / 100,
                "naive_join_total": (p * multiplier) / 100,
                "overcount_amount": (p * extra) / 100,
                "extra_rows": extra,
            })

    inflation_cents = naive_cents - correct_cents
    sorted_details = pd.DataFrame(details, columns=[
        on, "item_rows", "payment_total", "naive_join_total",
        "overcount_amount", "extra_rows",
    ])
    if not sorted_details.empty:
        sorted_details = sorted_details.sort_values(
            ["overcount_amount", "extra_rows"], ascending=[False, False],
            kind="stable",
        ).reset_index(drop=True)
    top = sorted_details.head(top_n).copy()
    top_cents = sum(int(Decimal(str(x)) * 100) for x in top["overcount_amount"])
    summary = {
        "join_key": on,
        "metric_column": value,
        "orders_rows": int(len(orders)),
        "item_rows": int(len(items)),
        "payment_records": int(len(payments)),
        "payment_orders": int(len(payment_totals)),
        "orders_without_payment_records": int(missing_payment_orders),
        "orders_without_items": orders_without_items,
        "orders_with_multiple_items": rows_multiple_items,
        "orders_with_positive_payment_and_multiple_items": paid_affected,
        "unmatched_item_rows_excluded": unmatched_item_rows,
        "unmatched_payment_rows_excluded": unmatched_payment_rows,
        "extra_join_rows": extra_row_count,
        "correct_payment_total": correct_cents / 100,
        "naive_payment_total": naive_cents / 100,
        "inflation_amount": inflation_cents / 100,
        "inflation_rate_pct": (
            100 * inflation_cents / correct_cents if correct_cents > 0 else None
        ),
        "top_n": int(len(top)),
        "top_n_inflation_amount": top_cents / 100,
        "top_n_inflation_share_pct": (
            100 * top_cents / inflation_cents if inflation_cents > 0 else 0.0
        ),
    }
    return summary, top
