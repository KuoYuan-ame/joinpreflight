"""Make a clearly synthetic demonstration dataset and plot an adaptive matrix.

Run: python examples/10_synthetic_matrix_demo.py
Unlike the six-row public CLI sample, these 1200 orders vary enough to illustrate
relationship screening. This is NOT a real Olist result.
"""
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
from joinpreflight.relationship_matrix import analyze_and_plot


def main() -> None:
    rng = np.random.default_rng(20261011)
    n = 1200
    order_rows = []
    item_rows = []
    payment_rows = []
    start = pd.Timestamp("2025-01-01")
    with TemporaryDirectory() as directory:
        base = Path(directory)
        for i in range(n):
            order_id = f"SYN{i:06d}"
            purchase = start + pd.Timedelta(days=int(rng.integers(0, 330)))
            count = int(rng.choice([1,2,3,4,5,6], p=[.72,.17,.065,.025,.015,.005]))
            item_price_base = float(rng.lognormal(4,.65))
            amounts=[]
            for j in range(count):
                price = round(max(3,item_price_base*rng.lognormal(0,.15)),2)
                freight = round(6+.03*price+rng.gamma(2,2),2)
                amounts.append(price+freight)
                item_rows.append(dict(order_id=order_id,price=price,freight_value=freight))
            paid = round(sum(amounts)*(1+rng.normal(.002,.012)),2)
            installments = int(np.clip(np.ceil(paid/65+rng.normal(0,1)),1,12))
            payment_rows.append(dict(order_id=order_id,payment_value=paid,
                                     payment_installments=installments,payment_type="credit_card"))
            days = int(np.clip(rng.gamma(4,3)+3+(count-1),2,80))
            target = int(np.clip(days+rng.normal(3,6),4,50))
            delivered = pd.NaT if rng.random()<.08 else purchase + pd.Timedelta(days=days)
            order_rows.append(dict(order_id=order_id,order_purchase_timestamp=purchase,
                                   order_delivered_customer_date=delivered,
                                   order_estimated_delivery_date=purchase+pd.Timedelta(days=target)))
        for name, rows in [("orders",order_rows),("items",item_rows),("payments",payment_rows)]:
            pd.DataFrame(rows).to_csv(base/f"{name}.csv", index=False)
        result=analyze_and_plot(base/"orders.csv",base/"items.csv",base/"payments.csv",
             "reports/synthetic_order_relationship_matrix.png",max_features=7)
        print("SYNTHETIC DEMO (not real Olist)")
        print("Selected",result["n"],"features:",", ".join(result["features"]))
        print("Saved to reports/synthetic_order_relationship_matrix.png")


if __name__ == "__main__":
    main()
