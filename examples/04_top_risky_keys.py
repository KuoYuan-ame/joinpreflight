
import argparse
import pandas as pd

from joinpreflight.joins import (
    analyze_join,
    rank_risky_keys,
)


def main():
    parser = argparse.ArgumentParser(
        description="Rank Olist JOIN expansion keys"
    )

    parser.add_argument("orders_csv")
    parser.add_argument("items_csv")

    args = parser.parse_args()

    orders = pd.read_csv(
        args.orders_csv,
        usecols=["order_id"],
    )

    items = pd.read_csv(
        args.items_csv,
        usecols=["order_id"],
    )

    report = analyze_join(
        left=orders,
        right=items,
        on="order_id",
        how="left",
        expected="1:N",
    )

    risky_keys = rank_risky_keys(
        left=orders,
        right=items,
        on="order_id",
        top_n=10,
    )

    print("=" * 65)
    print("JOINPREFLIGHT - TOP RISKY JOIN KEYS")
    print("=" * 65)

    print(f"Original orders: {len(orders):,}")
    print(f"Order items: {len(items):,}")

    print(
        "Predicted JOIN rows: "
        f"{report['predicted_rows']:,}"
    )

    print(
        "Total extra left rows: "
        f"{report['repeated_left_metric_rows']:,}"
    )

    print("\nTOP 10 KEYS BY JOIN EXPANSION")
    print("-" * 65)

    print(risky_keys.to_string(index=False))

    print("\nTOP 10 CONTRIBUTION")
    print("-" * 65)

    top_extra = sum(
        int(value)
        for value in risky_keys["extra_left_rows"]
    )

    total_extra = report["repeated_left_metric_rows"]

    if total_extra > 0:
        contribution = top_extra / total_extra * 100
    else:
        contribution = 0.0

    print(f"Extra rows from top 10 keys: {top_extra:,}")
    print(f"Share of total expansion: {contribution:.2f}%")


if __name__ == "__main__":
    main()
