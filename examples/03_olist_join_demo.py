
import argparse
import json

import pandas as pd

from joinpreflight.joins import analyze_join


def main():
    parser = argparse.ArgumentParser(
        description="Analyze the Olist order-to-item JOIN"
    )

    parser.add_argument(
        "orders_csv",
        help="Path to olist_orders_dataset.csv"
    )

    parser.add_argument(
        "items_csv",
        help="Path to olist_order_items_dataset.csv"
    )

    args = parser.parse_args()

    # Only load the required JOIN key
    orders = pd.read_csv(
        args.orders_csv,
        usecols=["order_id"]
    )

    order_items = pd.read_csv(
        args.items_csv,
        usecols=["order_id"]
    )

    print("=" * 60)
    print("JOINPREFLIGHT - OLIST JOIN ANALYSIS")
    print("=" * 60)

    report = analyze_join(
        left=orders,
        right=order_items,
        on="order_id",
        how="left",
        expected="1:N"
    )

    print(json.dumps(report, indent=4))

    # Ground-truth validation using Pandas
    actual_join = orders.merge(
        order_items,
        on="order_id",
        how="left"
    )

    predicted = report["predicted_rows"]
    actual = len(actual_join)

    print("\n" + "=" * 60)
    print("VALIDATION")
    print("=" * 60)

    print(f"Original orders: {len(orders):,}")
    print(f"Order items: {len(order_items):,}")
    print(f"Predicted JOIN rows: {predicted:,}")
    print(f"Actual JOIN rows: {actual:,}")

    assert predicted == actual, (
        "Predicted JOIN rows do not match actual rows!"
    )

    print("\nSUCCESS: JOIN row prediction is correct!")


if __name__ == "__main__":
    main()
