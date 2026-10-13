"""V7.3 Bootstrap CIs for Single vs Multi Spearman differences.

PowerShell:
python examples/13_bootstrap_segmented.py ORDERS ITEMS PAYMENTS --output reports/olist_bootstrap --n-boot 400
"""
from __future__ import annotations

import argparse
import json

from joinpreflight.bootstrap_inference import (
    DEFAULT_PAIRS, analyze_and_export_bootstrap,
)


def main() -> None:
    p = argparse.ArgumentParser(description="JoinPreflight: exploratory segmented bootstrap forest plot")
    p.add_argument("orders_csv")
    p.add_argument("items_csv")
    p.add_argument("payments_csv")
    p.add_argument("--output", default="reports/olist_bootstrap", help="Output prefix")
    p.add_argument("--n-boot", type=int, default=400, help="Bootstrap replications (50..20000)")
    p.add_argument("--confidence", type=float, default=.95)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--min-pairs", type=int, default=30)
    p.add_argument("--pair", nargs=2, action="append", metavar=("FEATURE_X", "FEATURE_Y"),
                   help="Repeat for each pair. Omitting selects three focused exploratory pairs")
    opts = p.parse_args()
    meta = analyze_and_export_bootstrap(
        opts.orders_csv, opts.items_csv, opts.payments_csv,
        opts.output, pairs=opts.pair if opts.pair is not None else DEFAULT_PAIRS,
        n_boot=opts.n_boot, confidence=opts.confidence,
        seed=opts.seed, min_pairs=opts.min_pairs,
    )
    print(json.dumps({"group_counts": meta["group_counts"], "parameters": meta["parameters"],
                      "outputs": meta["outputs"],
                      "pairs": [{k: v for k, v in r.items() if k in (
                          "feature_x", "feature_y", "delta_rho_multi_minus_single",
                          "ci_low", "ci_high", "status")}
                          for r in meta["results"]]},
                     indent=2, ensure_ascii=False))
    print("Reminder: nominal exploratory intervals, not multiplicity-adjusted tests or causal effects.")


if __name__ == "__main__":
    main()
