
import json

import pandas as pd

from joinpreflight.cli import main


def test_cli_generates_reports(tmp_path):
    """CLI should generate HTML and JSON files."""

    left_path = tmp_path / "orders.csv"
    right_path = tmp_path / "items.csv"

    html_path = tmp_path / "report.html"
    json_path = tmp_path / "report.json"

    pd.DataFrame({
        "id": ["A", "B"]
    }).to_csv(left_path, index=False)

    pd.DataFrame({
        "id": ["A", "A", "B"]
    }).to_csv(right_path, index=False)

    exit_code = main([
        "join",
        "--left", str(left_path),
        "--right", str(right_path),
        "--on", "id",
        "--expected", "1:N",
        "--top", "5",
        "--html", str(html_path),
        "--json", str(json_path),
    ])

    assert exit_code == 0
    assert html_path.exists()
    assert json_path.exists()

    report = json.loads(
        json_path.read_text(encoding="utf-8")
    )

    assert report["predicted_rows"] == 3
    assert report["actual_relationship"] == "1:N"
    assert report["metric_duplication_risk"] is True


def test_cli_relationship_violation(tmp_path):
    """Unexpected cardinality should return exit code 1."""

    left_path = tmp_path / "left.csv"
    right_path = tmp_path / "right.csv"

    pd.DataFrame({
        "id": ["A", "B"]
    }).to_csv(left_path, index=False)

    pd.DataFrame({
        "id": ["A", "A"]
    }).to_csv(right_path, index=False)

    exit_code = main([
        "join",
        "--left", str(left_path),
        "--right", str(right_path),
        "--on", "id",
        "--expected", "1:1",
    ])

    assert exit_code == 1


def test_cli_missing_file(tmp_path):
    """Missing CSV files should return exit code 2."""

    exit_code = main([
        "join",
        "--left", str(tmp_path / "missing.csv"),
        "--right", str(tmp_path / "other.csv"),
        "--on", "id",
    ])

    assert exit_code == 2


def test_cli_preserves_leading_zero_keys(tmp_path):
    """Identifiers with leading zeros must be preserved."""

    left_path = tmp_path / "left.csv"
    right_path = tmp_path / "right.csv"
    json_path = tmp_path / "report.json"

    left_path.write_text(
        "id\n001\n002\n",
        encoding="utf-8",
    )

    right_path.write_text(
        "id\n001\n001\n",
        encoding="utf-8",
    )

    exit_code = main([
        "join",
        "--left", str(left_path),
        "--right", str(right_path),
        "--on", "id",
        "--json", str(json_path),
    ])

    report = json.loads(
        json_path.read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert report["predicted_rows"] == 3
    assert report["repeated_left_metric_rows"] == 1
