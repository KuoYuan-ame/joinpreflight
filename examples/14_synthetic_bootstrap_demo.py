"""Self-contained synthetic example, no Olist files needed.

This deliberately simulates a different Single/Multi dependence pattern.
All results are synthetic and must never be represented as real Olist findings.
"""
from __future__ import annotations

from tempfile import TemporaryDirectory
from pathlib import Path
import numpy as np
import pandas as pd

from joinpreflight.bootstrap_inference import analyze_and_export_bootstrap


def main():
    rng = np.random.default_rng(20261013)
    orders, items, payments = [], [], []
    for i in range(270):
        key = f"FAKE-{i:05d}"
        count = 0 if i < 12 else (1 if i < 182 else 2 + i % 3)
        price = float(rng.lognormal(4.15, .55))
        delivery = int(rng.integers(3, 24))
        dt = pd.Timestamp("2024-01-01") + pd.Timedelta(days=i)
        orders.append({
            "order_id": key,
            "order_purchase_timestamp": str(dt),
            "order_delivered_customer_date": str(dt + pd.Timedelta(days=delivery)),
            "order_estimated_delivery_date": str(dt + pd.Timedelta(days=18)),
        })
        for j in range(count):
            items.append({
                "order_id": key,
                "price": round(price*(1+j*.05), 2),
                "freight_value": round(5.8 + (i % 4) + 1.2*j + rng.uniform(0, 3), 2),
            })
        payments.append({
            "order_id": key,
            "payment_value": round(price * max(count, 1) + 6.0*count + rng.uniform(1, 15), 2),
            "payment_installments": int(rng.integers(1, 9)),
            "payment_type": "credit_card",
        })
    with TemporaryDirectory() as folder:
        folder = Path(folder)
        paths = [folder / (name+".csv") for name in ("orders", "items", "payments")]
        for path, rows in zip(paths, (orders, items, payments)):
            pd.DataFrame(rows).to_csv(path, index=False)
        meta = analyze_and_export_bootstrap(*paths, "reports/demo_bootstrap",
                                             n_boot=250, min_pairs=20, seed=42)
    print("SYNTHETIC DEMO — NOT OLIST DATA")
    print("Groups:", meta["group_counts"])
    for row in meta["results"]:
        print(row["feature_x"], "/", row["feature_y"],
              "Δrho:", None if row["delta_rho_multi_minus_single"] is None else
              round(row["delta_rho_multi_minus_single"], 4),
              "CI:", (row["ci_low"], row["ci_high"]), "status:", row["status"])
    print("Outputs:", *meta["outputs"].values(), sep="\n  ")


if __name__ == "__main__":
    main()
