
import argparse
from pathlib import Path

import pandas as pd

from joinpreflight.joins import (
    analyze_join,
    rank_risky_keys,
)
from joinpreflight.report import generate_html_report


def main():
    parser = argparse.ArgumentParser(
        description="Generate Olist JOIN safety report"
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

    analysis = analyze_join(
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

    output = generate_html_report(
        report=analysis,
        risky_keys=risky_keys,
        output_path=Path("reports") / "olist_join_report.html",
    )

    print("=" * 60)
    print("JOINPREFLIGHT HTML REPORT")
    print("=" * 60)
    print(f"Original rows: {len(orders):,}")
    print(f"Predicted JOIN rows: {analysis['predicted_rows']:,}")
    print(f"Top risky keys: {len(risky_keys)}")
    print(f"Report saved to: {output}")


if __name__ == "__main__":
    main()
