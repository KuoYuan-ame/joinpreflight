from pathlib import Path

import pandas as pd
import pytest

from joinpreflight.joins import analyze_join, rank_risky_keys
from joinpreflight.visualization import render_figure_board, embed_figure_in_report


def _data():
    left = pd.DataFrame({"id": ["A", "B", "C", "D"]})
    right = pd.DataFrame({"id": ["A"] * 4 + ["B"] * 3 + ["C"] * 2 + ["D"]})
    return left, right


def test_render_png_pdf(tmp_path):
    left, right = _data()
    report = analyze_join(left, right, on="id", expected="1:N")
    ranked = rank_risky_keys(left, right, on="id", top_n=len(left))
    paths = render_figure_board(report, ranked, tmp_path / "board", top_n=3)
    assert paths["png"].exists() and paths["png"].stat().st_size > 1000
    assert paths["pdf"].exists() and paths["pdf"].stat().st_size > 1000


def test_reject_top_n_only_for_cumulative_curve(tmp_path):
    left, right = _data()
    report = analyze_join(left, right, on="id")
    incomplete = rank_risky_keys(left, right, on="id", top_n=2)
    with pytest.raises(ValueError, match="ALL expanding keys"):
        render_figure_board(report, incomplete, tmp_path / "board")


def test_embed_self_contained_image(tmp_path):
    source = tmp_path / "base.html"
    source.write_text("<html><main><p>Existing report</p></main></html>", encoding="utf-8")
    picture = tmp_path / "figure.png"
    picture.write_bytes(b"\x89PNG\r\n\x1a\n" + b"dummy")
    output = embed_figure_in_report(source, picture, tmp_path / "visual.html")
    body = output.read_text(encoding="utf-8")
    assert "Existing report" in body
    assert "data:image/png;base64," in body
    assert "JOIN Diagnostic Figure" in body


def test_cumulative_profile_linear_percent_axes(tmp_path):
    from matplotlib import pyplot as plt
    from joinpreflight.visualization import _panel_cumulative
    report = {"repeated_left_metric_rows": 6}
    ranked = pd.DataFrame({"extra_left_rows": [3, 2, 1]})
    fig, ax = plt.subplots()
    try:
        _panel_cumulative(ax, report, ranked)
        x = list(ax.lines[0].get_xdata())
        y = list(ax.lines[0].get_ydata())
        assert x == pytest.approx([0, 100 / 3, 200 / 3, 100])
        assert y == pytest.approx([0, 50, 500 / 6, 100])
        assert ax.get_xscale() == "linear"
    finally:
        plt.close(fig)

def test_figure_appears_before_footer(tmp_path):
    source = tmp_path / "base.html"
    source.write_text(
        "<html><main><section><h2>Top 10 扩张键</h2></section><footer>End</footer></main></html>",
        encoding="utf-8",
    )
    picture = tmp_path / "figure.png"
    picture.write_bytes(b"\x89PNG\r\n\x1a\n" + b"dummy")
    dest = embed_figure_in_report(source, picture, tmp_path / "report.html")
    html = dest.read_text(encoding="utf-8")
    assert html.index("JOIN Diagnostic Figure") < html.index("Top 10 扩张键")
    assert html.index("JOIN Diagnostic Figure") < html.index("<footer>")
