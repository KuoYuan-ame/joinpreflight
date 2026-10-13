"""End-to-end CLI tests for optional publication-style figures."""

import json

import pandas as pd
import pytest

from joinpreflight.cli import main


def _csv_pair(tmp_path, right_ids=None):
    left_path = tmp_path / "orders.csv"
    right_path = tmp_path / "items.csv"
    pd.DataFrame({"id": ["A", "B", "C", "D"]}).to_csv(left_path, index=False)
    if right_ids is None:
        right_ids = ["A"] * 4 + ["B"] * 3 + ["C"] * 2 + ["D"]
    pd.DataFrame({"id": right_ids}).to_csv(right_path, index=False)
    return left_path, right_path


def test_figure_cli_exports_png_and_pdf_without_html(tmp_path):
    left, right = _csv_pair(tmp_path)
    prefix = tmp_path / "out" / "figure"
    exit_code = main([
        "join", "--left", str(left), "--right", str(right),
        "--on", "id", "--top", "2", "--figure", str(prefix),
    ])
    assert exit_code == 0
    assert prefix.with_suffix(".png").stat().st_size > 1000
    assert prefix.with_suffix(".pdf").stat().st_size > 1000
    assert not prefix.with_suffix(".html").exists()


def test_figure_cli_inserts_visual_before_details_and_keeps_json(tmp_path):
    left, right = _csv_pair(tmp_path)
    prefix = tmp_path / "plots" / "figure"
    html = tmp_path / "reports" / "diagnostic.html"
    json_path = tmp_path / "reports" / "summary.json"
    exit_code = main([
        "join", "--left", str(left), "--right", str(right),
        "--on", "id", "--expected", "1:N", "--top", "2",
        "--figure", str(prefix), "--html", str(html),
        "--json", str(json_path),
    ])
    assert exit_code == 0
    report_html = html.read_text(encoding="utf-8")
    assert report_html.index("JOIN Diagnostic Figure") < report_html.index("Top 2 扩张键")
    assert report_html.index("JOIN Diagnostic Figure") < report_html.index("<footer>")
    assert report_html.count("data:image/png;base64,") == 1
    assert prefix.with_suffix(".png").exists()
    assert prefix.with_suffix(".pdf").exists()
    summary = json.loads(json_path.read_text(encoding="utf-8"))
    assert summary["predicted_rows"] == 10
    assert summary["repeated_left_metric_rows"] == 6


def test_figure_cli_handles_no_expansion(tmp_path):
    left, right = _csv_pair(tmp_path, right_ids=["A", "B", "C", "D"])
    prefix = tmp_path / "empty_figure"
    assert main([
        "join", "--left", str(left), "--right", str(right),
        "--on", "id", "--figure", str(prefix),
    ]) == 0
    assert prefix.with_suffix(".png").exists()
    assert prefix.with_suffix(".pdf").exists()


def test_figure_cli_still_returns_constraint_violation(tmp_path):
    left, right = _csv_pair(tmp_path)
    prefix = tmp_path / "violating_figure"
    assert main([
        "join", "--left", str(left), "--right", str(right),
        "--on", "id", "--expected", "1:1", "--figure", str(prefix),
    ]) == 1
    assert prefix.with_suffix(".png").exists()


def test_figure_cli_rejects_file_extension(tmp_path, capsys):
    left, right = _csv_pair(tmp_path)
    code = main([
        "join", "--left", str(left), "--right", str(right),
        "--on", "id", "--figure", str(tmp_path / "chart.png"),
    ])
    assert code == 2
    assert "without an extension" in capsys.readouterr().err
