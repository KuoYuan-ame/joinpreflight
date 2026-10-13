"""Run the v5 end-to-end report without downloading the Olist dataset."""
from pathlib import Path

import pandas as pd

from joinpreflight.cli import main


def run() -> int:
    root = Path(__file__).resolve().parents[1]
    demo = root / "reports" / "demo_data"
    demo.mkdir(parents=True, exist_ok=True)
    orders = demo / "orders.csv"
    items = demo / "items.csv"
    payments = demo / "payments.csv"
    pd.DataFrame({"order_id": ["A001", "A002", "A003", "A004"]}).to_csv(orders, index=False)
    pd.DataFrame({"order_id": ["A001", "A001", "A002", "A002", "A002", "A003"]}).to_csv(items, index=False)
    pd.DataFrame({
        "order_id": ["A001", "A001", "A002", "A003"],
        "payment_value": ["20.01", "9.99", "100.00", "40.00"],
    }).to_csv(payments, index=False)
    return main([
        "report", "--orders", str(orders), "--items", str(items),
        "--payments", str(payments), "--on", "order_id", "--value", "payment_value",
        "--expected", "1:N", "--currency", "BRL", "--top", "3",
        "--output", str(root / "reports" / "demo_unified.html"),
    ])


if __name__ == "__main__":
    raise SystemExit(run())
