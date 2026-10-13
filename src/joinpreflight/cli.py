"""Command-line interface for JoinPreflight.

The optional --figure option uses the publication-style four-panel chart.
Matplotlib is imported only when figures are requested, preserving a lean
regular installation for analysis-only users.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from .joins import analyze_join, rank_risky_keys
from .report import generate_html_report


def positive_integer(value: str) -> int:
    """Parse a strictly positive integer CLI option."""
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Must be a positive integer") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("Must be a positive integer")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="joinpreflight",
        description="Detect JOIN cardinality and aggregation risks.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    join_parser = subparsers.add_parser(
        "join", help="Analyze a single-key LEFT JOIN between CSV files"
    )
    join_parser.add_argument("--left", required=True, help="Path to left CSV")
    join_parser.add_argument("--right", required=True, help="Path to right CSV")
    join_parser.add_argument("--on", required=True, help="JOIN key column name")
    join_parser.add_argument(
        "--expected", choices=["1:1", "1:N", "N:1", "N:N"], default=None,
        help="Expected relationship constraint",
    )
    join_parser.add_argument(
        "--top", type=positive_integer, default=10,
        help="Number of expansion keys in the console/HTML table (default: 10)",
    )
    join_parser.add_argument(
        "--html", default=None, help="Optional standalone HTML report path"
    )
    join_parser.add_argument(
        "--json", default=None, help="Optional JSON summary path"
    )
    join_parser.add_argument(
        "--figure", default=None,
        help="Output prefix (without extension) for four-panel PNG and PDF",
    )
    impact_parser = subparsers.add_parser(
        "impact",
        help="Quantify duplicated order-level payment SUM after a LEFT JOIN",
    )
    impact_parser.add_argument("--orders", required=True, help="Order master CSV")
    impact_parser.add_argument("--items", required=True, help="Order-item CSV")
    impact_parser.add_argument("--payments", required=True, help="Payment records CSV")
    impact_parser.add_argument("--on", default="order_id", help="Order join key")
    impact_parser.add_argument("--value", default="payment_value", help="Payment amount column")
    impact_parser.add_argument("--currency", default="BRL", help="Reporting currency label")
    impact_parser.add_argument("--top", type=positive_integer, default=10)
    impact_parser.add_argument("--figure", default=None, help="Output prefix for impact PNG/PDF")
    impact_parser.add_argument("--html", default=None, help="Standalone HTML output path")
    impact_parser.add_argument("--json", default=None, help="Structured JSON output path")
    report_parser = subparsers.add_parser(
        "report", help="Generate one complete offline structural + payment report"
    )
    report_parser.add_argument("--orders", required=True, help="Order master CSV")
    report_parser.add_argument("--items", required=True, help="Item detail CSV")
    report_parser.add_argument("--payments", required=True, help="Payment record CSV")
    report_parser.add_argument("--on", default="order_id", help="Shared JOIN key")
    report_parser.add_argument("--value", default="payment_value", help="Payment metric")
    report_parser.add_argument("--currency", default="BRL", help="Currency label")
    report_parser.add_argument("--expected", choices=["1:1", "1:N", "N:1", "N:N"],
                               default="1:N", help="Expected relationship constraint")
    report_parser.add_argument("--top", type=positive_integer, default=10,
                               help="Top N rows in both detailed ranking tables")
    report_parser.add_argument("--output", default="reports/olist_unified.html",
                               help="Destination offline HTML (required extension .html)")
    report_parser.add_argument("--json", default=None,
                               help="Optional JSON path; defaults to output stem + .json")
    report_parser.add_argument("--figure-dir", default=None,
                               help="Directory for separately exported PNG/PDF figures")
    return parser


def load_join_keys(path: str, key: str) -> pd.DataFrame:
    """Read only the key, preserving leading zero identifiers."""
    return pd.read_csv(path, usecols=[key], dtype={key: "string"})


def main(argv: list[str] | None = None) -> int:
    """Return 0 for success, 1 for constraint violations, 2 for errors."""
    args = build_parser().parse_args(argv)
    if args.command == "impact":
        return _run_impact(args)
    if args.command == "report":
        return _run_report(args)

    try:
        left = load_join_keys(args.left, args.on)
        right = load_join_keys(args.right, args.on)
        analysis = analyze_join(
            left=left, right=right, on=args.on,
            how="left", expected=args.expected,
        )

        if args.figure is not None:
            # A suffixless prefix prevents accidentally replacing the requested
            # extension; visualization.render_figure_board adds .png / .pdf.
            if Path(args.figure).suffix:
                raise ValueError("--figure needs a prefix without an extension")
            try:
                from .visualization import (
                    embed_figure_in_report,
                    render_figure_board,
                )
            except ImportError as exc:
                raise RuntimeError(
                    'Visualization needs matplotlib. Install with: '
                    'python -m pip install -e ".[viz]"'
                ) from exc

            # rank_risky_keys() is already sorted; ALL keys are necessary for
            # the exact cumulative contribution curve in panel (d).
            all_risky = rank_risky_keys(
                left, right, on=args.on, top_n=max(1, len(left))
            )
            risky_keys = all_risky.head(args.top).copy()
            figures = render_figure_board(
                analysis, all_risky, args.figure, top_n=args.top
            )
        else:
            risky_keys = rank_risky_keys(left, right, on=args.on, top_n=args.top)
            figures = None

        if args.html:
            html_path = generate_html_report(
                report=analysis, risky_keys=risky_keys, output_path=args.html
            )
            if figures is not None:
                # Read the base HTML, insert figure before Top N table, then
                # write to the SAME path; no intermediary _base file needed.
                html_path = embed_figure_in_report(
                    html_path, figures["png"], html_path
                )
        else:
            html_path = None

        if args.json:
            json_path = Path(args.json)
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(
                json.dumps(analysis, ensure_ascii=False, indent=4),
                encoding="utf-8",
            )
        else:
            json_path = None

    except (
        OSError, ValueError, TypeError, ImportError, RuntimeError,
        pd.errors.ParserError,
    ) as exc:
        print(f"JoinPreflight error: {exc}", file=sys.stderr)
        return 2

    print("=" * 65)
    print("JOINPREFLIGHT - JOIN SAFETY ANALYSIS")
    print("=" * 65)
    print(json.dumps(analysis, ensure_ascii=False, indent=4))
    print("\nTOP EXPANSION KEYS")
    print("-" * 65)
    if risky_keys.empty:
        print("No left-side row duplication detected.")
    else:
        print(risky_keys.to_string(index=False))

    if figures is not None:
        print(f"\nPNG figure: {figures['png']}")
        print(f"PDF figure: {figures['pdf']}")
    if html_path is not None:
        print(f"HTML report: {html_path}")
    if json_path is not None:
        print(f"JSON report: {json_path.resolve()}")

    if analysis["relationship_valid"] is False:
        print("\nWARNING: Expected relationship violated!", file=sys.stderr)
        return 1
    return 0


def _run_impact(args: argparse.Namespace) -> int:
    """Run the v4 money-impact subcommand without changing v3 JOIN behavior."""
    try:
        import re
        from .metric_impact import analyze_metric_inflation
        from .impact_report import generate_impact_html

        if not re.fullmatch(r"[A-Za-z]{3,8}", args.currency):
            raise ValueError("--currency must be 3–8 letters, e.g. BRL")
        currency = args.currency.upper()
        if args.figure is not None and Path(args.figure).suffix:
            raise ValueError("--figure expects a prefix without an extension")

        # Read ONLY necessary fields; payment values remain strings for
        # exact decimal-to-cent conversion (avoids binary float artifacts).
        orders = pd.read_csv(args.orders, usecols=[args.on], dtype={args.on: "string"})
        items = pd.read_csv(args.items, usecols=[args.on], dtype={args.on: "string"})
        payments = pd.read_csv(
            args.payments,
            usecols=[args.on, args.value],
            dtype={args.on: "string", args.value: "string"},
        )
        summary, top_orders = analyze_metric_inflation(
            orders, items, payments, on=args.on, value=args.value,
            top_n=args.top,
        )
        figures = None
        if args.figure:
            try:
                from .impact_visualization import render_impact_figure
            except ImportError as exc:
                raise RuntimeError(
                    'Figure rendering needs matplotlib. Install with '
                    'python -m pip install -e ".[viz]"'
                ) from exc
            figures = render_impact_figure(summary, args.figure, currency=currency)
        html_path = None
        if args.html:
            html_path = generate_impact_html(
                summary, top_orders, args.html, currency=currency,
                figure_png=figures["png"] if figures else None,
            )
        json_path = None
        if args.json:
            json_path = Path(args.json)
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(
                json.dumps({"summary": summary,
                            "top_impact_orders": top_orders.to_dict(orient="records")},
                           ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except (
        OSError, ValueError, TypeError, ImportError, RuntimeError,
        pd.errors.ParserError,
    ) as exc:
        print(f"JoinPreflight impact error: {exc}", file=sys.stderr)
        return 2

    print("=" * 65)
    print("JOINPREFLIGHT - METRIC INFLATION IMPACT")
    print("=" * 65)
    print(f"Correct payment SUM: {summary['correct_payment_total']:,.2f} {currency}")
    print(f"Naive post-JOIN SUM: {summary['naive_payment_total']:,.2f} {currency}")
    print(f"Potential overcount: +{summary['inflation_amount']:,.2f} {currency}")
    if summary["inflation_rate_pct"] is None:
        print("Inflation rate: undefined (correct total = 0)")
    else:
        print(f"Inflation rate: +{summary['inflation_rate_pct']:.2f}%")
    print(f"Orders with missing payment records: {summary['orders_without_payment_records']:,}")
    print("\nTOP ORDERS BY POTENTIAL PAYMENT OVERCOUNT")
    print("-" * 65)
    print(top_orders.to_string(index=False) if not top_orders.empty else "None")
    if figures:
        print(f"\nPNG figure: {figures['png']}")
        print(f"PDF figure: {figures['pdf']}")
    if html_path:
        print(f"HTML report: {html_path}")
    if json_path:
        print(f"JSON report: {json_path.resolve()}")
    return 0


def _run_report(args: argparse.Namespace) -> int:
    """v5 unified report, built on top of the unchanged v3/v4 engines."""
    try:
        import re
        from .metric_impact import analyze_metric_inflation
        from .visualization import render_figure_board
        from .impact_visualization import render_impact_figure
        from .unified_report import generate_unified_html

        if not re.fullmatch(r"[A-Za-z]{3,8}", args.currency):
            raise ValueError("--currency must contain 3–8 ASCII letters")
        currency = args.currency.upper()
        html_target = Path(args.output)
        if html_target.suffix.lower() != ".html":
            raise ValueError("--output must have a .html extension")
        figures_dir = Path(args.figure_dir) if args.figure_dir else html_target.parent / "figures"
        # Only columns required by the analyzers are read; monetary values
        # are strings to retain exact two-decimal parsing inside v4.
        orders = pd.read_csv(args.orders, usecols=[args.on], dtype={args.on: "string"})
        items = pd.read_csv(args.items, usecols=[args.on], dtype={args.on: "string"})
        payments = pd.read_csv(args.payments, usecols=[args.on, args.value],
                               dtype={args.on: "string", args.value: "string"})

        join_summary = analyze_join(orders, items, on=args.on, how="left", expected=args.expected)
        impact_summary, top_impact = analyze_metric_inflation(
            orders, items, payments, on=args.on, value=args.value, top_n=args.top
        )
        # The concentration curve MUST receive every expanding key.
        all_expansion = rank_risky_keys(orders, items, on=args.on,
                                        top_n=max(1, len(orders)))
        top_expansion = all_expansion.head(args.top).copy()
        # Use unique figure filenames derived from the HTML stem.
        join_figures = render_figure_board(
            join_summary, all_expansion,
            figures_dir / f"{html_target.stem}_join", top_n=args.top,
        )
        impact_figures = render_impact_figure(
            impact_summary, figures_dir / f"{html_target.stem}_payment", currency=currency,
        )
        report_path = generate_unified_html(
            join_summary, impact_summary, top_expansion, top_impact, html_target,
            join_figures["png"], impact_figures["png"], currency=currency,
        )
        json_path = Path(args.json) if args.json else html_target.with_suffix(".json")
        json_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "join_summary": join_summary,
            "impact_summary": impact_summary,
            "top_expansion_keys": top_expansion.to_dict(orient="records"),
            "top_impact_orders": top_impact.to_dict(orient="records"),
        }
        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False,
                       default=lambda obj: obj.item() if hasattr(obj, "item") else str(obj)),
            encoding="utf-8",
        )
    except (
        OSError, ValueError, TypeError, ImportError, RuntimeError,
        pd.errors.ParserError,
    ) as exc:
        print(f"JoinPreflight report error: {exc}", file=sys.stderr)
        return 2

    print("=" * 65)
    print("JOINPREFLIGHT - UNIFIED DIAGNOSTIC REPORT")
    print("=" * 65)
    print(f"Left rows: {join_summary['left_rows']:,}")
    print(f"Predicted LEFT JOIN rows: {join_summary['predicted_rows']:,}")
    print(f"Additional rows: {join_summary['left_join_row_growth']:,}")
    print(f"Correct payment SUM: {impact_summary['correct_payment_total']:,.2f} {currency}")
    print(f"Naive payment SUM: {impact_summary['naive_payment_total']:,.2f} {currency}")
    print(f"Potential overcount: +{impact_summary['inflation_amount']:,.2f} {currency}")
    rate = impact_summary['inflation_rate_pct']
    print(f"Inflation rate: {rate:.2f}%" if rate is not None else "Inflation rate: undefined")
    print(f"HTML: {report_path}")
    print(f"JSON: {json_path.resolve()}")
    print(f"Figures: {join_figures['png']}, {impact_figures['png']}")
    if join_summary["relationship_valid"] is False:
        print("WARNING: expected relationship constraint violated", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
