"""Publication-style diagnostics for a single-key LEFT JOIN.

The four panels answer distinct questions:
(a) What is joined? (b) How many rows are added?
(c) Which keys add the most rows? (d) How concentrated is the expansion?

This module requires matplotlib but does not change the existing report API.
"""

from __future__ import annotations

import base64
import re
from itertools import accumulate
from pathlib import Path
from typing import Any, Mapping

import matplotlib

# Headless rendering works in PyCharm, CI, and command-line environments.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import pandas as pd

INK = "#17324D"
BLUE = "#377C9D"
ORANGE = "#D47748"
LIGHT = "#DFE8ED"
GRAY = "#66788A"
GRID = "#E4EAF0"


def _require_complete_distribution(report: Mapping[str, Any], risky_keys: pd.DataFrame) -> pd.DataFrame:
    """Ensure cumulative shares use *every* expanding key, not just Top N."""
    if report.get("join_type") != "left":
        raise ValueError("Figure board currently supports LEFT JOIN only")
    required = {
        "join_key", "left_rows", "right_rows", "predicted_rows",
        "left_join_row_growth", "repeated_left_metric_rows",
        "actual_relationship", "relationship_valid",
    }
    missing = required - report.keys()
    if missing:
        raise ValueError(f"Missing report fields: {sorted(missing)}")
    if not isinstance(risky_keys, pd.DataFrame):
        raise TypeError("risky_keys must be a pandas DataFrame")
    needed = {report["join_key"], "left_count", "right_count", "extra_left_rows"}
    if not needed.issubset(risky_keys.columns):
        raise ValueError(f"Missing risky-key columns: {sorted(needed - set(risky_keys.columns))}")

    ranked = risky_keys.sort_values("extra_left_rows", ascending=False, kind="stable").reset_index(drop=True)
    values = [int(x) for x in ranked["extra_left_rows"]]
    if any(x <= 0 for x in values):
        raise ValueError("risky_keys must contain only positive expansion values")
    if len(ranked) and ranked[report["join_key"]].duplicated().any():
        raise ValueError("risky_keys contains duplicate key groups")
    total = int(report["repeated_left_metric_rows"])
    if sum(values) != total:
        raise ValueError(
            "Cumulative curve needs ALL expanding keys. "
            "Call rank_risky_keys(..., top_n=max(1, len(left)))."
        )
    return ranked


def _card(ax, x: float, y: float, w: float, h: float, title: str, value: str, fill: str) -> None:
    patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.035",
                           facecolor=fill, edgecolor=GRID, linewidth=1.15)
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h * 0.70, title, ha="center", va="center", fontsize=9, color=GRAY)
    ax.text(x + w / 2, y + h * 0.35, value, ha="center", va="center", fontsize=13, fontweight="bold", color=INK)


def _panel_structure(ax, report):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    _card(ax, 0.04, 0.64, 0.39, 0.22, "LEFT TABLE", f"{int(report['left_rows']):,} rows", "#F3F8FB")
    _card(ax, 0.57, 0.64, 0.39, 0.22, "RIGHT TABLE", f"{int(report['right_rows']):,} rows", "#F3F8FB")
    for x in (0.24, 0.76):
        ax.add_patch(FancyArrowPatch((x, 0.62), (0.5, 0.34), arrowstyle="-|>",
                                     mutation_scale=16, color=BLUE, linewidth=1.6))
    _card(ax, 0.29, 0.08, 0.42, 0.22, "LEFT JOIN OUTPUT", f"{int(report['predicted_rows']):,} rows", "#FFF3EC")
    ax.text(0.50, 0.51, f"key: {str(report['join_key'])}", ha="center", fontsize=9,
            color=INK, bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="none"))
    status = ("constraint satisfied" if report["relationship_valid"] is True
              else "constraint violated" if report["relationship_valid"] is False else "no expected constraint")
    ax.text(0.50, 0.01, f"Actual relationship: {report['actual_relationship']} · {status}",
            ha="center", fontsize=8.5, color=GRAY)


def _panel_rows(ax, report):
    left = int(report["left_rows"])
    joined = int(report["predicted_rows"])
    growth = joined - left
    ax.barh([1], [left], height=0.38, color=BLUE)
    ax.barh([0], [left], height=0.38, color=LIGHT)
    if growth > 0:
        ax.barh([0], [growth], left=[left], height=0.38, color=ORANGE)
    ax.set_yticks([1, 0], ["Left table", "LEFT JOIN output"])
    ax.set_xlim(0, max(1, joined, left) * 1.28)
    ax.set_ylim(-0.65, 1.65)
    ax.set_xlabel("Rows", fontsize=9)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for y, value in ((1, left), (0, joined)):
        ax.text(value + max(joined, left, 1) * 0.02, y, f"{value:,}", va="center", fontsize=10, color=INK)
    pct = 100 * growth / left if left else 0.0
    ax.text(0.02, 0.02, f"Additional rows: +{growth:,}  (+{pct:.2f}%)", transform=ax.transAxes,
            color=ORANGE, fontweight="bold", fontsize=10)


def _short_key(value: Any, rank: int) -> str:
    label = "NULL" if pd.isna(value) else str(value)
    if len(label) > 17:
        label = label[:8] + "..." + label[-5:]
    return f"{rank:02d}  {label}"


def _panel_top(ax, ranked: pd.DataFrame, key: str, top_n: int):
    top = ranked.head(top_n)
    if top.empty:
        ax.text(0.5, 0.5, "No left-side duplication detected", ha="center", va="center",
                color=GRAY, transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        return
    values = [int(x) for x in top["extra_left_rows"]]
    labels = [_short_key(value, i) for i, value in enumerate(top[key], start=1)]
    positions = list(range(len(top)))
    ax.barh(positions, values, height=0.66, color=BLUE)
    ax.set_yticks(positions, labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, max(values) * 1.20)
    ax.set_xlabel("Additional left-side rows", fontsize=9)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for y, value in zip(positions, values):
        ax.text(value + max(values) * 0.02, y, str(value), va="center", fontsize=8, color=INK)
    ax.text(0, 1.02, "Keys shortened for display; full values remain in the HTML table.",
            transform=ax.transAxes, fontsize=7.5, color=GRAY)


def _panel_cumulative(ax, report, ranked):
    """Plot concentration against share of keys (linear scale).

    Both axes run from 0% to 100%. A steep early rise means expansion
    is concentrated in a small fraction of keys; a curve near the
    diagonal means contributions are relatively diffuse.
    """
    total = int(report["repeated_left_metric_rows"])
    if total <= 0 or ranked.empty:
        ax.text(0.5, 0.5, "No expansion to analyze", ha="center", va="center",
                transform=ax.transAxes, color=GRAY)
        ax.set_xticks([])
        ax.set_yticks([])
        return

    extra = [int(value) for value in ranked["extra_left_rows"]]
    n = len(extra)
    x = [0.0] + [100 * rank / n for rank in range(1, n + 1)]
    y = [0.0] + [100 * value / total for value in accumulate(extra)]
    n80 = next(rank for rank, share in enumerate(y[1:], start=1) if share >= 80)
    k80_pct = 100 * n80 / n
    top10 = min(10, n)
    top10_share = y[top10]

    ax.plot(x, y, color=BLUE, linewidth=2.2, label="Observed expansion")
    ax.plot([0, 100], [0, 100], linestyle=":", color=GRAY,
            linewidth=1.25, label="Equal contribution")
    ax.fill_between(x, y, color=BLUE, alpha=0.07)
    ax.axhline(80, color=ORANGE, linewidth=1, linestyle="--", alpha=0.85)
    ax.scatter([k80_pct], [y[n80]], s=34, color=ORANGE, zorder=5)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 105)
    ax.set_xlabel("Share of expanding keys, ranked by contribution (%)", fontsize=9)
    ax.set_ylabel("Cumulative share of extra rows (%)", fontsize=9)
    ax.grid(True, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.legend(loc="lower right", frameon=False, fontsize=8)
    ax.text(0.02, 0.98,
            f"Top {top10}: {top10_share:.2f}%  |  "
            f"80% from {n80:,} keys ({k80_pct:.1f}% of keys)",
            transform=ax.transAxes, va="top", fontsize=8.2, color=INK,
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.9, pad=3))


def render_figure_board(
    report: Mapping[str, Any],
    all_risky_keys: pd.DataFrame,
    output_prefix: str | Path,
    top_n: int = 10,
) -> dict[str, Path]:
    """Create publication-style PNG (240 dpi) and vector PDF figures."""
    if isinstance(top_n, bool) or not isinstance(top_n, int) or top_n < 1:
        raise ValueError("top_n must be a positive integer")
    ranked = _require_complete_distribution(report, all_risky_keys)
    prefix = Path(output_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)

    style = {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.labelcolor": INK,
        "axes.edgecolor": GRID,
        "xtick.color": GRAY,
        "ytick.color": GRAY,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "pdf.fonttype": 42,
    }
    with plt.rc_context(style):
        fig, axs = plt.subplots(2, 2, figsize=(14, 9.2), layout="constrained")
        fig.suptitle("JoinPreflight  |  JOIN Cardinality & Expansion Diagnostics",
                     fontsize=16, weight="bold", color=INK)
        panels = axs.flatten()
        labels = ["(a) JOIN structure", "(b) Row-count change",
                  "(c) Largest expansion keys", "(d) Expansion concentration profile"]
        for ax, label in zip(panels, labels):
            ax.set_title(label, loc="left", pad=13)
            ax.spines[["top", "right"]].set_visible(False)
        _panel_structure(panels[0], report)
        _panel_rows(panels[1], report)
        _panel_top(panels[2], ranked, str(report["join_key"]), top_n)
        _panel_cumulative(panels[3], report, ranked)
        png = prefix.with_suffix(".png")
        pdf = prefix.with_suffix(".pdf")
        fig.savefig(png, dpi=240, bbox_inches="tight", pad_inches=0.18)
        fig.savefig(pdf, bbox_inches="tight", pad_inches=0.18)
        plt.close(fig)
    return {"png": png.resolve(), "pdf": pdf.resolve()}


def embed_figure_in_report(
    original_html: str | Path,
    figure_png: str | Path,
    destination_html: str | Path,
) -> Path:
    """Append a self-contained, offline visual section to the current HTML report."""
    template = Path(original_html).read_text(encoding="utf-8")
    if "</main>" not in template:
        raise ValueError("Expected '</main>' in the original HTML report")
    picture = base64.b64encode(Path(figure_png).read_bytes()).decode("ascii")
    section = (
        '<section class="jpf-figure" aria-label="Join diagnostic figure">'
        '<h2>JOIN Diagnostic Figure</h2>'
        '<p style="color:#66788a">Four complementary views: structure, row growth, key ranking and cumulative contribution.</p>'
        '<img alt="Four-panel JOIN cardinality and row expansion diagnostic" '
        'style="width:100%;height:auto;display:block" '
        f'src="data:image/png;base64,{picture}">'
        '</section>'
    )
    # Show the figure before the detailed Top-N table, not after the footer.
    # Fall back to before the footer if the report template changes.
    top_section = re.search(r"<section>\s*<h2>Top\s+\d+\s+扩张键</h2>", template)
    if top_section:
        point = top_section.start()
        result = template[:point] + section + "\n" + template[point:]
    elif "<footer>" in template:
        result = template.replace("<footer>", section + "\n<footer>", 1)
    else:
        result = template.replace("</main>", section + "\n</main>", 1)
    output = Path(destination_html)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result, encoding="utf-8")
    return output.resolve()
