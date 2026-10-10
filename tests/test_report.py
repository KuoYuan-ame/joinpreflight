
import pandas as pd
import pytest

from joinpreflight.joins import analyze_join, rank_risky_keys
from joinpreflight.report import generate_html_report


def test_html_report_generation(tmp_path):
    left = pd.DataFrame({
        "id": ["A", "B"]
    })
    right = pd.DataFrame({
        "id": ["A", "A", "B"]
    })

    report = analyze_join(
        left, right, on="id", expected="1:N"
    )

    risky = rank_risky_keys(left, right, on="id")

    target = tmp_path / "report.html"

    result = generate_html_report(
        report, risky, target
    )

    assert result.exists()

    content = result.read_text(encoding="utf-8")

    assert "JoinPreflight" in content
    assert "JOIN Safety Report" in content
    assert "符合预期" in content
    assert "100.00%" in content


def test_html_escapes_external_keys(tmp_path):
    dangerous_key = "<script>alert(1)</script>"

    left = pd.DataFrame({
        "id": [dangerous_key]
    })
    right = pd.DataFrame({
        "id": [dangerous_key, dangerous_key]
    })

    report = analyze_join(left, right, on="id")
    risky = rank_risky_keys(left, right, on="id")

    target = generate_html_report(
        report, risky, tmp_path / "safe.html"
    )

    content = target.read_text(encoding="utf-8")

    assert "&lt;script&gt;" in content
    assert "<script>" not in content


def test_report_rejects_inner_join(tmp_path):
    left = pd.DataFrame({"id": [1]})
    right = pd.DataFrame({"id": [1]})

    report = analyze_join(
        left, right, on="id", how="inner"
    )

    risky = rank_risky_keys(left, right, on="id")

    with pytest.raises(ValueError, match="LEFT JOIN"):
        generate_html_report(
            report, risky, tmp_path / "report.html"
        )
