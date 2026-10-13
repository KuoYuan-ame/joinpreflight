"""v5 integration tests: actual CLI flow, safety, consistency and HTML output."""
import json

import pandas as pd
import pytest

from joinpreflight.cli import main
from joinpreflight.unified_report import generate_unified_html


def _dataset(folder, *, no_items=False, injection=False):
    folder.mkdir(parents=True, exist_ok=True)
    orders = folder / "orders.csv"
    items = folder / "items.csv"
    payments = folder / "payments.csv"
    a = '<img src=x onerror=alert(1)>' if injection else '001'
    pd.DataFrame({"order_id": [a, "002", "003"]}).to_csv(orders, index=False)
    pd.DataFrame({"order_id": ["002"] if no_items else [a, a, "002", "002", "002"]}).to_csv(items, index=False)
    pd.DataFrame({"order_id": [a, a, "002"],
                  "payment_value": ["20.01", "9.99", "100.00"]}).to_csv(payments, index=False)
    return orders, items, payments


def _args(paths, folder, *extra):
    orders, items, payments = paths
    return [
        "report", "--orders", str(orders), "--items", str(items),
        "--payments", str(payments), "--output", str(folder / "report.html"),
        "--top", "1", *extra,
    ]


def test_report_cli_emits_integrated_html_and_two_figures(tmp_path):
    paths = _dataset(tmp_path / "input")
    assert main(_args(paths, tmp_path)) == 0
    html = (tmp_path / "report.html").read_text(encoding="utf-8")
    data = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert html.count("data:image/png;base64,") == 2
    assert html.index("PART A") < html.index("PART B") < html.index("PART C")
    assert "EXECUTIVE SUMMARY" in html and "27.87%" not in html
    assert "230.00 BRL" in html
    assert "<details>" in html and "payment_by_order" in html
    assert data["join_summary"]["predicted_rows"] == 6
    assert data["impact_summary"]["correct_payment_total"] == 130
    assert data["impact_summary"]["inflation_amount"] == 230
    assert data["top_impact_orders"][0]["order_id"] == "002"
    assert len(data["top_expansion_keys"]) == 1
    for name in ("report_join", "report_payment"):
        for suffix in ("png", "pdf"):
            assert (tmp_path / "figures" / f"{name}.{suffix}").stat().st_size > 1000


def test_report_no_expansion_and_zero_baseline(tmp_path):
    paths = _dataset(tmp_path / "input", no_items=True)
    # Remove payments and leave header, exercising zero-baseline rendering.
    paths[2].write_text("order_id,payment_value\n", encoding="utf-8")
    status = main(_args(paths, tmp_path))
    assert status == 0
    html = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "Undefined (zero baseline)" in html
    assert "None in this dataset" in html
    assert "3 orders have no payment records" in html


def test_report_html_escapes_user_key(tmp_path):
    paths = _dataset(tmp_path / "input", injection=True)
    assert main(_args(paths, tmp_path, "--top", "2")) == 0
    html = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert '&lt;img src=x onerror=alert(1)&gt;' in html
    assert '<img src=x onerror=alert(1)>' not in html


def test_report_bad_currency_and_output_extension(tmp_path):
    paths = _dataset(tmp_path / "input")
    assert main(_args(paths, tmp_path, "--currency", "<BRL>")) == 2
    assert main(_args(paths, tmp_path, "--output", str(tmp_path / "not-html.pdf"))) == 2


def test_report_detects_duplicate_master_orders(tmp_path):
    paths = _dataset(tmp_path / "input")
    pd.DataFrame({"order_id": ["001", "001"]}).to_csv(paths[0], index=False)
    assert main(_args(paths, tmp_path)) == 2
    assert not (tmp_path / "report.html").exists()


def test_report_constraint_violation_generates_report_and_returns_one(tmp_path):
    paths = _dataset(tmp_path / "input")
    assert main(_args(paths, tmp_path, "--expected", "1:1")) == 1
    html = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "Expected relationship violated" in html


def test_unified_rejects_cross_dataset_mismatch(tmp_path):
    join = {"join_type": "left", "join_key": "id", "left_rows": 3,
            "right_rows": 4, "left_join_row_growth": 1}
    impact = {"join_key": "id", "orders_rows": 4, "item_rows": 4,
              "extra_join_rows": 1}
    with pytest.raises(ValueError, match="disagree"):
        generate_unified_html(join, impact, pd.DataFrame(), pd.DataFrame(),
                              tmp_path / "report.html", tmp_path / "x.png", tmp_path / "y.png")


def test_existing_commands_still_exist():
    from joinpreflight.cli import build_parser
    parser = build_parser()
    assert parser.parse_args(["join", "--left", "a.csv", "--right", "b.csv", "--on", "id"]).command == "join"
    assert parser.parse_args(["impact", "--orders", "a.csv", "--items", "b.csv", "--payments", "c.csv"]).command == "impact"
