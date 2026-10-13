"""Order-grain adaptive n×n relationship matrix, v7.1.

Use: python examples/09_adaptive_pair_matrix.py ORDERS ITEMS PAYMENTS \
      --max-features 7 --profile exploratory --include avg_item_price
"""
import argparse
import json
from joinpreflight.relationship_matrix import analyze_and_plot


def main():
    parser = argparse.ArgumentParser(
        description="Auditable adaptive relationship matrix: scored features, manual overrides, robust plots")
    parser.add_argument("orders_csv")
    parser.add_argument("items_csv")
    parser.add_argument("payments_csv")
    parser.add_argument("--output", default="reports/order_relationship_matrix.png")
    parser.add_argument("--max-features", type=int, default=7)
    parser.add_argument("--max-points", type=int, default=2400)
    parser.add_argument("--min-coverage", type=float, default=.75)
    parser.add_argument("--min-distinct", type=int, default=6)
    parser.add_argument("--max-mode-share", type=float, default=.95)
    parser.add_argument("--redundant-at", type=float, default=.93)
    parser.add_argument("--profile", choices=["exploratory", "business", "risk"], default="exploratory")
    parser.add_argument("--include", action="append", default=[], metavar="FEATURE",
                        help="Keep feature (may repeat; quality overrides noted in audit)")
    parser.add_argument("--exclude", action="append", default=[], metavar="FEATURE",
                        help="Drop feature (may repeat)")
    args = parser.parse_args()
    metadata = analyze_and_plot(
        args.orders_csv, args.items_csv, args.payments_csv, args.output,
        max_features=args.max_features, max_points=args.max_points,
        min_coverage=args.min_coverage, min_distinct=args.min_distinct,
        max_mode_share=args.max_mode_share, redundant_at=args.redundant_at,
        profile=args.profile, force_include=args.include, force_exclude=args.exclude)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    print("Figure saved:", args.output)
    print("Companion files: SVG, *_candidate_audit.csv, *_metadata.json")


if __name__ == "__main__":
    main()
