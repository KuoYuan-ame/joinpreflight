"""Run the installed CLI against committed synthetic fixtures and check results.

Usage: python tools/smoke_demo.py
No network access or Olist download required.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples" / "sample_data"


def cli_executable() -> Path:
    """Prefer the CLI entry point installed alongside the current Python."""
    name = "joinpreflight.exe" if os.name == "nt" else "joinpreflight"
    candidate = Path(sys.executable).resolve().parent / name
    if not candidate.is_file():
        raise RuntimeError(
            f"CLI entry point not found at {candidate}; install project first: "
            'python -m pip install -e ".[dev]"'
        )
    return candidate


def main() -> int:
    for name in ("orders.csv", "order_items.csv", "payments.csv"):
        if not (FIXTURES / name).is_file():
            raise FileNotFoundError(FIXTURES / name)
    with tempfile.TemporaryDirectory(prefix="joinpreflight-smoke-") as tmp:
        dest = Path(tmp) / "sample_unified.html"
        cmd = [
            str(cli_executable()), "report",
            "--orders", str(FIXTURES / "orders.csv"),
            "--items", str(FIXTURES / "order_items.csv"),
            "--payments", str(FIXTURES / "payments.csv"),
            "--on", "order_id", "--value", "payment_value",
            "--expected", "1:N", "--currency", "BRL",
            "--top", "5", "--output", str(dest),
        ]
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(
                f"CLI exited with status {proc.returncode}\n"
                f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )
        payload = json.loads(dest.with_suffix(".json").read_text(encoding="utf-8"))
        join = payload["join_summary"]
        impact = payload["impact_summary"]
        assert join["left_rows"] == 6, join
        assert join["right_rows"] == 7, join
        assert join["predicted_rows"] == 9, join
        assert join["left_join_row_growth"] == 3, join
        assert join["actual_relationship"] == "1:N", join
        assert join["relationship_valid"] is True, join
        assert impact["orders_without_items"] == 2, impact
        assert impact["orders_without_payment_records"] == 1, impact
        assert abs(impact["correct_payment_total"] - 215.00) < 0.001, impact
        assert abs(impact["naive_payment_total"] - 385.00) < 0.001, impact
        assert abs(impact["inflation_amount"] - 170.00) < 0.001, impact
        assert abs(impact["inflation_rate_pct"] - (170/215*100)) < 0.001, impact
        html = dest.read_text(encoding="utf-8")
        assert html.count("data:image/png;base64,") == 2
        assert "EXECUTIVE SUMMARY" in html
        for stem in ("sample_unified_join", "sample_unified_payment"):
            for suffix in ("png", "pdf"):
                fp = Path(tmp) / "figures" / f"{stem}.{suffix}"
                assert fp.stat().st_size > 1000, fp
        print("PASS: synthetic public demo / registered CLI / report / JSON / PNG / PDF")
        print("Rows: 6 -> 9 (+3); payment SUM: 215.00 -> 385.00 BRL (+170.00)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, RuntimeError, ValueError, KeyError) as exc:
        print(f"Smoke demo FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
