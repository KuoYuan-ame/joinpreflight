"""Build a publication-style figure board from Olist or other two CSV files."""
import argparse
from pathlib import Path

import pandas as pd

from joinpreflight.joins import analyze_join, rank_risky_keys
from joinpreflight.report import generate_html_report
from joinpreflight.visualization import render_figure_board, embed_figure_in_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a four-panel JoinPreflight diagnostic figure")
    parser.add_argument("left_csv", help="CSV for the left table")
    parser.add_argument("right_csv", help="CSV for the right table")
    parser.add_argument("--key", default="order_id", help="JOIN key column, default: order_id")
    parser.add_argument("--expected", default="1:N", choices=["1:1", "1:N", "N:1", "N:N"])
    parser.add_argument("--out", default="reports/joinpreflight_figure", help="Output prefix without extension")
    args = parser.parse_args()

    left = pd.read_csv(args.left_csv, usecols=[args.key], dtype={args.key: "string"})
    right = pd.read_csv(args.right_csv, usecols=[args.key], dtype={args.key: "string"})

    report = analyze_join(left, right, on=args.key, how="left", expected=args.expected)
    # IMPORTANT: cumulative contribution requires ALL expanding keys, not merely the top ten.
    all_risky = rank_risky_keys(left, right, on=args.key, top_n=max(1, len(left)))
    top_ten = all_risky.head(10)

    prefix = Path(args.out)
    images = render_figure_board(report, all_risky, prefix, top_n=10)
    old_html = generate_html_report(report, top_ten, prefix.with_name(prefix.name + "_base.html"))
    new_html = embed_figure_in_report(old_html, images["png"], prefix.with_suffix(".html"))

    print("JOIN rows:", f"{report['predicted_rows']:,}")
    print("Additional left rows:", f"{report['repeated_left_metric_rows']:,}")
    print("Expanding key groups:", f"{len(all_risky):,}")
    print("PNG:", images["png"])
    print("PDF:", images["pdf"])
    print("HTML:", new_html)


if __name__ == "__main__":
    main()
