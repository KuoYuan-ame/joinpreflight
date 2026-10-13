"""Synthetic demonstration of v7.2; never presented as Olist results."""
from pathlib import Path
from tempfile import TemporaryDirectory
import numpy as np
import pandas as pd

from joinpreflight.segmented_analysis import analyze_and_export


def main():
    rng = np.random.default_rng(20261013)
    with TemporaryDirectory() as directory:
        root = Path(directory)
        orders, items, payments = [], [], []
        for i in range(210):
            order_id = f"DEMO-{i:05d}"
            count = 0 if i < 10 else (1 if i < 120 else int(rng.integers(2, 5)))
            price = float(rng.lognormal(4.1, .55))
            for j in range(count):
                items.append({"order_id": order_id, "price": round(price * (1+.03*j), 2),
                              "freight_value": round(6+1.2*j+rng.uniform(0,12), 2)})
            total = price * max(count, 1) + 6 * count + rng.normal(8,3)
            payments.append({"order_id": order_id, "payment_value": max(round(total, 2),0),
                             "payment_installments": int(rng.integers(1, 9)),
                             "payment_type": "credit_card"})
            dt = pd.Timestamp("2024-01-01") + pd.Timedelta(days=i)
            days = int(rng.integers(3, 26))
            orders.append({"order_id": order_id,
                           "order_purchase_timestamp": str(dt),
                           "order_delivered_customer_date": str(dt+pd.Timedelta(days=days)),
                           "order_estimated_delivery_date": str(dt+pd.Timedelta(days=18))})
        p_orders, p_items, p_payments = (root / name for name in ("orders.csv", "items.csv", "payments.csv"))
        pd.DataFrame(orders).to_csv(p_orders, index=False)
        pd.DataFrame(items).to_csv(p_items, index=False)
        pd.DataFrame(payments).to_csv(p_payments, index=False)
        result = analyze_and_export(p_orders, p_items, p_payments, "reports/demo_segmented", min_pairs=20)
    print("SYNTHETIC DEMO, not Olist")
    print("Population:", result["group_counts"])
    print("Consistency check:", result["consistency_check"])
    print("Figures and CSV: reports/demo_segmented_*")


if __name__ == "__main__":
    main()
