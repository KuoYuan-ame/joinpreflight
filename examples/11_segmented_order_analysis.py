"""v7.2 Segment analysis: existing order/items/payments CSVs, no new dependencies.

Example:
python examples/11_segmented_order_analysis.py ORDERS ITEMS PAYMENTS --output reports/olist_segmented
"""
import argparse
import json
from joinpreflight.segmented_analysis import analyze_and_export, DEFAULT_FEATURES


def main():
    p = argparse.ArgumentParser(description="Order-grain Single/Multi segmented relationship diagnostics")
    p.add_argument("orders_csv")
    p.add_argument("items_csv")
    p.add_argument("payments_csv")
    p.add_argument("--output", default="reports/olist_segmented", help="Output prefix, without extension")
    p.add_argument("--min-pairs", type=int, default=30, help="Minimum pairwise valid N (default: 30)")
    p.add_argument("--features", nargs="+", default=list(DEFAULT_FEATURES),
                   help="2..8 feature names from the existing JoinPreflight candidate registry")
    args = p.parse_args()
    result = analyze_and_export(args.orders_csv, args.items_csv, args.payments_csv,
                                args.output, min_pairs=args.min_pairs, features=args.features)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("Completed. Review correlation N and status before interpreting differences.")


if __name__ == "__main__":
    main()
