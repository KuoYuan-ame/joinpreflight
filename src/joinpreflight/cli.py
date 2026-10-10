
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from .joins import analyze_join, rank_risky_keys
from .report import generate_html_report


def positive_integer(value: str) -> int:
    """Validate positive integer arguments."""
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Must be a positive integer"
        ) from exc

    if number < 1:
        raise argparse.ArgumentTypeError(
            "Must be a positive integer"
        )

    return number


def build_parser() -> argparse.ArgumentParser:
    """Build the JoinPreflight command-line interface."""

    parser = argparse.ArgumentParser(
        prog="joinpreflight",
        description=(
            "Detect JOIN cardinality and aggregation risks."
        ),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    join_parser = subparsers.add_parser(
        "join",
        help="Analyze a LEFT JOIN between two CSV files",
    )

    join_parser.add_argument(
        "--left",
        required=True,
        help="Path to the left CSV file",
    )

    join_parser.add_argument(
        "--right",
        required=True,
        help="Path to the right CSV file",
    )

    join_parser.add_argument(
        "--on",
        required=True,
        help="Name of the JOIN key column",
    )

    join_parser.add_argument(
        "--expected",
        choices=["1:1", "1:N", "N:1", "N:N"],
        default=None,
        help="Expected relationship constraint",
    )

    join_parser.add_argument(
        "--top",
        type=positive_integer,
        default=10,
        help="Number of risky keys to display",
    )

    join_parser.add_argument(
        "--html",
        default=None,
        help="Optional HTML report output path",
    )

    join_parser.add_argument(
        "--json",
        default=None,
        help="Optional JSON report output path",
    )

    return parser


def load_join_keys(path: str, key: str) -> pd.DataFrame:
    """
    Load only the JOIN key from a CSV file.

    Read keys as strings to preserve identifiers
    such as leading-zero customer or order IDs.
    """

    return pd.read_csv(
        path,
        usecols=[key],
        dtype={key: "string"},
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Return a process exit code."""

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        left = load_join_keys(args.left, args.on)
        right = load_join_keys(args.right, args.on)

        analysis = analyze_join(
            left=left,
            right=right,
            on=args.on,
            how="left",
            expected=args.expected,
        )

        risky_keys = rank_risky_keys(
            left=left,
            right=right,
            on=args.on,
            top_n=args.top,
        )

        # Optional HTML report
        if args.html:
            html_path = generate_html_report(
                report=analysis,
                risky_keys=risky_keys,
                output_path=args.html,
            )
        else:
            html_path = None

        # Optional JSON report
        if args.json:
            json_path = Path(args.json)
            json_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            json_path.write_text(
                json.dumps(
                    analysis,
                    indent=4,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        else:
            json_path = None

    except (
        OSError,
        ValueError,
        TypeError,
        pd.errors.ParserError,
    ) as exc:
        print(
            f"JoinPreflight error: {exc}",
            file=sys.stderr,
        )
        return 2

    # Console report
    print("=" * 65)
    print("JOINPREFLIGHT - JOIN SAFETY ANALYSIS")
    print("=" * 65)

    print(
        json.dumps(
            analysis,
            indent=4,
            ensure_ascii=False,
        )
    )

    print("\nTOP RISKY KEYS")
    print("-" * 65)

    if risky_keys.empty:
        print("No left-side row duplication detected.")
    else:
        print(risky_keys.to_string(index=False))

    if html_path is not None:
        print(f"\nHTML report: {html_path}")

    if json_path is not None:
        print(f"JSON report: {json_path.resolve()}")

    # Exit codes:
    # 0 = success
    # 1 = relationship constraint violation
    # 2 = input or execution error

    if analysis["relationship_valid"] is False:
        print(
            "\nWARNING: Expected relationship violated!",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
