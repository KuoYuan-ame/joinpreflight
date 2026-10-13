"""Order-grain segment comparison for JoinPreflight v7.2.

Descriptive exploratory analysis only: differences in Spearman rho do not
establish causality or statistical significance. No item rows are counted as
zero, but *missing monetary totals remain missing*.

This module is additive: it does not change the v7.1 matrix implementation.
"""
from __future__ import annotations

import json
import math
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from joinpreflight.relationship_matrix import build_order_features, CANDIDATE_MAP

DEFAULT_FEATURES = (
    "payment_total", "avg_item_price", "freight_total",
    "delivery_days", "max_installments",
)
# These pairs make different business questions visible without an unreadable
# grid of scatter plots. The full pairwise matrix is saved separately.
PRIORITY_PAIRS = (
    ("avg_item_price", "payment_total"),
    ("payment_total", "freight_total"),
    ("payment_total", "max_installments"),
    ("freight_total", "delivery_days"),
    ("payment_total", "delivery_days"),
)
SEGMENTS = ("Single", "Multi")
COLORS = {"Single": "#397f9e", "Multi": "#da7844", "No items": "#a5b5c0"}
NAVY = "#1d3854"


def _ensure_features(frame: pd.DataFrame, features: list[str]) -> None:
    if not (2 <= len(features) <= 8):
        raise ValueError("Choose 2 to 8 different features")
    if len(features) != len(set(features)):
        raise ValueError("Repeated features are not allowed")
    unknown = [f for f in features if f not in CANDIDATE_MAP]
    if unknown:
        raise ValueError("Unknown candidate features: " + ", ".join(unknown))
    missing = [f for f in features if f not in frame]
    if missing:
        raise ValueError("Unavailable source columns: " + ", ".join(missing))


def classify_orders(frame: pd.DataFrame) -> pd.DataFrame:
    """Produce one classification per order, without dropping unmatched orders."""
    if "item_count" not in frame.columns:
        raise ValueError("item_count is required for order segmentation")
    if "order_id" not in frame.columns:
        raise ValueError("order_id is required")
    if frame["order_id"].isna().any() or frame["order_id"].duplicated().any():
        raise ValueError("order_id must be non-null and unique at order grain")
    counts = pd.to_numeric(frame["item_count"], errors="coerce")
    if (counts.isna().any() or (~np.isfinite(counts)).any()
            or (counts < 0).any() or (counts != np.floor(counts)).any()):
        raise ValueError("item_count must be finite, nonnegative integers")
    out = frame.copy()
    out["segment"] = np.select(
        [counts.eq(0), counts.eq(1), counts.ge(2)],
        ["No items", "Single", "Multi"], default="No items",
    )
    return out


def safe_spearman(x: pd.Series, y: pd.Series, *, min_pairs: int = 30) -> dict:
    """Pairwise-valid rank Pearson with explicit constant and low-N states.

    pandas/SciPy sometimes warn on a constant input; that coefficient is
    undefined, so we return null + an explanation instead of hiding a warning.
    Ties use pandas rank(method='average'), matching Spearman's definition.
    """
    if min_pairs < 3:
        raise ValueError("min_pairs must be at least 3")
    pair = pd.concat([pd.to_numeric(x, errors="coerce"),
                      pd.to_numeric(y, errors="coerce")], axis=1)
    pair = pair.replace([np.inf, -np.inf], np.nan).dropna()
    n = len(pair)
    if n < min_pairs:
        return {"rho": None, "n": int(n), "status": "insufficient_pairs"}
    if pair.iloc[:, 0].nunique() < 2 or pair.iloc[:, 1].nunique() < 2:
        return {"rho": None, "n": int(n), "status": "constant_input"}
    ranks = pair.rank(method="average")
    rho = ranks.iloc[:, 0].corr(ranks.iloc[:, 1], method="pearson")
    if pd.isna(rho):
        return {"rho": None, "n": int(n), "status": "undefined"}
    return {"rho": float(np.clip(rho, -1., 1.)), "n": int(n), "status": "ok"}


def _feature_stats(group: pd.DataFrame, feature: str) -> dict:
    valid = pd.to_numeric(group[feature], errors="coerce").replace(
        [np.inf, -np.inf], np.nan).dropna()
    q = valid.quantile([.25, .5, .75]) if len(valid) else None
    return {
        "feature": feature, "non_null": int(len(valid)),
        "missing": int(len(group) - len(valid)),
        "median": float(q.loc[.5]) if q is not None else None,
        "p25": float(q.loc[.25]) if q is not None else None,
        "p75": float(q.loc[.75]) if q is not None else None,
    }


def analyze_segments(frame: pd.DataFrame, *, features: list[str] | tuple[str, ...] = DEFAULT_FEATURES,
                     min_pairs: int = 30) -> dict:
    """Compute full-order-population group summaries and within-group rho.

    Never infer significance from differences. A per-group pairwise N and
    status is preserved for every pair; 'No items' stays in population counts
    but is *not* used to compare Single vs Multi.
    """
    features = list(features)
    _ensure_features(frame, features)
    classified = classify_orders(frame)
    if min_pairs < 3:
        raise ValueError("min_pairs must be at least 3")
    n_all = len(classified)
    group_counts = {label: int(classified.segment.eq(label).sum())
                    for label in ("No items", *SEGMENTS)}
    grouped = {label: classified[classified.segment.eq(label)] for label in SEGMENTS}
    summary = []
    for label in ("No items", *SEGMENTS):
        df = classified[classified.segment.eq(label)]
        for f in features:
            summary.append({"segment": label, "orders": int(len(df)),
                            "share_of_all_pct": 100 * len(df) / n_all if n_all else None,
                            **_feature_stats(df, f)})
    correlation_rows = []
    for label in SEGMENTS:
        df = grouped[label]
        for a, b in combinations(features, 2):
            stats = safe_spearman(df[a], df[b], min_pairs=min_pairs)
            correlation_rows.append({"segment": label, "feature_x": a, "feature_y": b,
                                     **stats})
    index = {(r["segment"], r["feature_x"], r["feature_y"]): r
             for r in correlation_rows}
    differences = []
    for a, b in combinations(features, 2):
        single = index[("Single", a, b)]
        multi = index[("Multi", a, b)]
        ok = single["status"] == multi["status"] == "ok"
        differences.append({
            "feature_x": a, "feature_y": b,
            "rho_single": single["rho"], "n_single": single["n"],
            "single_status": single["status"],
            "rho_multi": multi["rho"], "n_multi": multi["n"],
            "multi_status": multi["status"],
            "delta_rho_multi_minus_single": multi["rho"] - single["rho"] if ok else None,
            "status": "descriptive_only" if ok else "not_comparable",
        })
    return {
        "features": features,
        "total_orders": n_all,
        "group_counts": group_counts,
        "min_pairs": min_pairs,
        "group_summary": pd.DataFrame(summary),
        "correlations": pd.DataFrame(correlation_rows),
        "differences": pd.DataFrame(differences),
        "classified": classified,
    }


def verify_overall_pair(frame: pd.DataFrame, a: str = "freight_total",
                        b: str = "delivery_days") -> dict:
    """Independent consistency check on the same raw pairwise-valid rows.

    Uses a rank-Pearson implementation and pandas Spearman; this is not an
    independent replication with a different dataset or an external claim.
    """
    if a not in frame or b not in frame:
        return {"pair": [a, b], "status": "missing_column"}
    x = pd.to_numeric(frame[a], errors="coerce")
    y = pd.to_numeric(frame[b], errors="coerce")
    result = safe_spearman(x, y, min_pairs=10)
    if result["status"] != "ok":
        return {"pair": [a, b], "status": result["status"], "n": result["n"]}
    clean = pd.concat([x, y], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    via_pandas = float(clean.iloc[:, 0].corr(clean.iloc[:, 1], method="spearman"))
    delta = abs(result["rho"] - via_pandas)
    return {"pair": [a, b], "status": "pass" if delta <= 1e-10 else "mismatch",
            "n": result["n"], "rank_pearson": result["rho"],
            "pandas_spearman": via_pandas, "absolute_difference": delta}


def _style_axes(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#d9e4eb")
    ax.tick_params(labelsize=9, colors="#5b7085")
    ax.grid(axis="x", alpha=.6, color="#dbe4ea")
    ax.set_axisbelow(True)


def _boxplot(ax, classified: pd.DataFrame, name: str, letter: str):
    datasets = []
    all_valid = pd.to_numeric(classified[name], errors="coerce").replace(
        [np.inf, -np.inf], np.nan).dropna()
    # Never silently discard valid negative values. Monetary amounts should be
    # nonnegative in Olist; signed datasets receive a display-only asinh scale.
    transform = np.arcsinh if (all_valid < 0).any() else np.log1p
    transform_label = "asinh" if (all_valid < 0).any() else "log(1 + x)"
    for label in SEGMENTS:
        arr = pd.to_numeric(classified.loc[classified.segment.eq(label), name],
                            errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        if len(arr):
            datasets.append(transform(arr.to_numpy(dtype=float)))
        else:
            datasets.append(np.array([np.nan]))
    # `orientation` replaces `vert` in newer Matplotlib. Support the
    # project's existing minimum Matplotlib version without warnings.
    # Matplotlib 3.10 introduced orientation; 3.9 introduced tick_labels.
    mpl_version = tuple(int(v) for v in matplotlib.__version__.split(".")[:2])
    orientation_kw = ({"orientation": "horizontal"}
                      if mpl_version >= (3, 10) else {"vert": False})
    label_kw = ({"tick_labels": ["Single", "Multi"]}
                if mpl_version >= (3, 9) else {"labels": ["Single", "Multi"]})
    obj = ax.boxplot(datasets, showfliers=False, patch_artist=True, widths=.5,
                     medianprops={"color": NAVY, "linewidth": 1.6},
                     **orientation_kw, **label_kw)
    for patch, segment in zip(obj["boxes"], SEGMENTS):
        patch.set_facecolor(COLORS[segment]); patch.set_alpha(.52)
    ax.invert_yaxis()
    ax.set_title(f"({letter})  {name.replace('_', ' ').capitalize()} by segment", loc="left",
                 fontweight="bold", fontsize=11, color=NAVY)
    ax.set_xlabel(f"{transform_label}({name})   [visualization only]", fontsize=9, color=NAVY)
    ax.text(.98, .95, "Whiskers: 1.5 IQR; outliers hidden", transform=ax.transAxes,
            ha="right", va="top", fontsize=8, color="#687f92")
    _style_axes(ax)


def plot_overview(results: dict, output: str | Path) -> None:
    """Four nonredundant panels: population, two skewed distributions, rho comparison."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(15.5, 10.5), dpi=170)
    fig.patch.set_facecolor("white")
    groups = ("No items", "Single", "Multi")
    counts = results["group_counts"]
    ax = axes[0, 0]
    ypos = np.arange(3)
    ax.barh(ypos, [counts[g] for g in groups], color=[COLORS[g] for g in groups], height=.55)
    ax.set_yticks(ypos, groups)
    ax.invert_yaxis()
    xmax = max(counts.values()) * 1.23 if max(counts.values()) else 1
    ax.set_xlim(0, xmax)
    for y, g in enumerate(groups):
        n = counts[g]
        pct = 100 * n / results["total_orders"] if results["total_orders"] else 0
        ax.text(n + xmax*.015, y, f"{n:,}  ({pct:.1f}%)", va="center", color=NAVY, fontsize=9)
    ax.set_title("(a)  Order population by segment", loc="left", fontsize=11, fontweight="bold", color=NAVY)
    ax.set_xlabel("Orders", fontsize=9, color=NAVY)
    _style_axes(ax)
    for ax, name, letter in [(axes[0, 1], "payment_total", "b"),
                             (axes[1, 0], "freight_total", "c")]:
        if name in results["classified"]:
            _boxplot(ax, results["classified"], name, letter)
        else:
            ax.text(.5, .5, f"{name} unavailable", ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
    ax = axes[1, 1]
    differences = results["differences"]
    rows = []
    priority = [p for p in PRIORITY_PAIRS if set(p).issubset(results["features"])]
    for a, b in priority:
        match = differences[(differences.feature_x.eq(a) & differences.feature_y.eq(b)) |
                            (differences.feature_x.eq(b) & differences.feature_y.eq(a))]
        if len(match) and match.iloc[0]["status"] == "descriptive_only":
            r = match.iloc[0]
            rows.append((f"{a.replace('_', ' ')} / {b.replace('_', ' ')}",
                         float(r["rho_single"]), float(r["rho_multi"])))
    if not rows:
        ax.text(.5, .5, "No comparable pairs (insufficient or constant data)",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
    else:
        for i, (label, first, second) in enumerate(rows):
            ax.plot([first, second], [i, i], linewidth=1.7, color="#a9bac6", zorder=1)
            ax.scatter([first], [i], s=65, color=COLORS["Single"], zorder=3)
            ax.scatter([second], [i], s=65, color=COLORS["Multi"], zorder=3)
        ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=8)
        ax.invert_yaxis()
        ax.set_xlim(-1.05, 1.05)
        ax.axvline(0, color="#9caebc", linestyle="--", linewidth=.7)
        ax.plot([], [], "o", color=COLORS["Single"], label="Single")
        ax.plot([], [], "o", color=COLORS["Multi"], label="Multi")
        ax.legend(frameon=False, loc="lower right", fontsize=9)
        ax.set_xlabel("Spearman ρ (descriptive; full available pairs)", fontsize=9, color=NAVY)
        ax.set_title("(d)  Within-segment correlations", loc="left", fontsize=11,
                     fontweight="bold", color=NAVY)
        _style_axes(ax)
    fig.suptitle("JoinPreflight  |  Order Segment Diagnostics", fontsize=19,
                 fontweight="bold", color=NAVY, y=.985)
    fig.text(.5, .943, "Single = 1 item row   |   Multi = 2+ item rows   |   No items reported separately",
             ha="center", fontsize=10, color="#667f91")
    fig.subplots_adjust(left=.17, right=.965, top=.88, bottom=.09, wspace=.45, hspace=.34)
    fig.savefig(output, dpi=200, facecolor="white")
    fig.savefig(output.with_suffix(".svg"), facecolor="white")
    plt.close(fig)


def _matrix_of_corr(result: dict, segment: str) -> np.ndarray:
    features = result["features"]
    matrix = np.full((len(features), len(features)), np.nan)
    # The diagonal is 1 only for a nonconstant, adequately observed feature;
    # forcing 1 for an empty/constant feature would misrepresent the statistic.
    df = result["classified"]
    group = df[df.segment.eq(segment)]
    for i, feature in enumerate(features):
        valid = pd.to_numeric(group[feature], errors="coerce").replace(
            [np.inf, -np.inf], np.nan).dropna()
        if len(valid) >= result["min_pairs"] and valid.nunique() >= 2:
            matrix[i, i] = 1.
    for r in result["correlations"].to_dict("records"):
        if r["segment"] != segment:
            continue
        i = features.index(r["feature_x"]); j = features.index(r["feature_y"])
        matrix[i, j] = matrix[j, i] = r["rho"] if r["rho"] is not None else np.nan
    return matrix


def plot_correlation_panels(result: dict, output: str | Path) -> None:
    """Single/Multi/Δrho aligned heatmaps with same [-1,1] scale."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    a = _matrix_of_corr(result, "Single")
    b = _matrix_of_corr(result, "Multi")
    difference = b-a
    np.fill_diagonal(difference, np.nan)
    features = result["features"]
    n = len(features)
    fig, axes = plt.subplots(1, 3, figsize=(18, max(6, n * .95 + 2.3)), dpi=165)
    colormap = plt.get_cmap("RdBu_r").copy()
    colormap = colormap.with_extremes(bad="#edf2f5")
    for index, (ax, matrix, label) in enumerate(zip(
            axes, [a, b, difference], ["(a) Single", "(b) Multi", "(c) Δρ = Multi − Single"])):
        img = ax.imshow(np.ma.masked_invalid(matrix), cmap=colormap, vmin=-1, vmax=1)
        ax.set_xticks(range(n), [f.replace("_", " ") for f in features], rotation=48, ha="right", fontsize=8)
        ax.set_yticks(range(n), [f.replace("_", " ") for f in features], fontsize=8)
        ax.set_title(label, fontsize=12, fontweight="bold", color=NAVY, pad=12)
        for row in range(n):
            for col in range(n):
                val = matrix[row, col]
                if index == 2 and row == col:
                    continue
                ax.text(col, row, f"{val:+.2f}" if np.isfinite(val) else "n/a",
                        ha="center", va="center", fontsize=8,
                        color="white" if np.isfinite(val) and abs(val) > .55 else NAVY)
        ax.set_xticks(np.arange(-.5,n,1),minor=True)
        ax.set_yticks(np.arange(-.5,n,1),minor=True)
        ax.grid(which="minor",color="white",linewidth=1.5)
        ax.tick_params(which="minor",bottom=False,left=False)

    fig.suptitle("JoinPreflight  |  Within-segment Relationship Comparison", fontsize=18,
                 fontweight="bold", color=NAVY, y=.975)
    fig.text(.5, .925, "Full available pairwise observations · undefined coefficients shown as n/a · no causal inference",
             ha="center", fontsize=9, color="#657a8e")
    # Keep the colorbar outside the three heatmaps; never float it over cells.
    fig.subplots_adjust(left=.09,right=.905,bottom=.24,top=.84,wspace=.33)
    colorbar_axis = fig.add_axes([.925, .34, .012, .39])
    fig.colorbar(img, cax=colorbar_axis, label="Spearman ρ / Δρ")
    fig.savefig(output, dpi=200, facecolor="white")
    fig.savefig(output.with_suffix(".svg"), facecolor="white")
    plt.close(fig)


def _json_safe(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value) if np.isfinite(value) else None
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def analyze_and_export(orders_csv: str | Path, items_csv: str | Path,
                       payments_csv: str | Path, output_prefix: str | Path,
                       *, features: list[str] | tuple[str, ...] = DEFAULT_FEATURES,
                       min_pairs: int = 30) -> dict:
    """Additive v7.2 entrypoint; produces 2 figures, 3 CSVs, and metadata."""
    source = build_order_features(orders_csv, items_csv, payments_csv)
    result = analyze_segments(source, features=features, min_pairs=min_pairs)
    validation = verify_overall_pair(source)
    if validation.get("status") == "mismatch":
        raise AssertionError("Two implementations of the overall Spearman coefficient disagree")
    base = Path(output_prefix)
    base.parent.mkdir(parents=True, exist_ok=True)
    overview_path = base.with_name(base.name + "_overview.png")
    correlations_path = base.with_name(base.name + "_correlations.png")
    plot_overview(result, overview_path)
    plot_correlation_panels(result, correlations_path)
    paths = {
        "overview_png": overview_path,
        "overview_svg": overview_path.with_suffix(".svg"),
        "correlation_png": correlations_path,
        "correlation_svg": correlations_path.with_suffix(".svg"),
        "group_summary_csv": base.with_name(base.name + "_group_summary.csv"),
        "pair_correlations_csv": base.with_name(base.name + "_pair_correlations.csv"),
        "rho_differences_csv": base.with_name(base.name + "_rho_differences.csv"),
        "metadata_json": base.with_name(base.name + "_metadata.json"),
    }
    result["group_summary"].to_csv(paths["group_summary_csv"], index=False)
    result["correlations"].to_csv(paths["pair_correlations_csv"], index=False)
    result["differences"].to_csv(paths["rho_differences_csv"], index=False)
    metadata = {
        "version": "v7.2",
        "total_orders": result["total_orders"],
        "features": result["features"],
        "group_counts": result["group_counts"],
        "min_pairs": result["min_pairs"],
        "correlation_method": "Spearman via average-rank Pearson; pairwise non-null, full group",
        "statistical_note": "Descriptive comparisons only; no causal inference or significance claims",
        "population_note": "No-items orders reported, excluded from Single-vs-Multi comparison",
        "consistency_check": validation,
        "source_files": {"orders": Path(orders_csv).name, "items": Path(items_csv).name,
                         "payments": Path(payments_csv).name},
        "outputs": {k: str(v) for k, v in paths.items()},
    }
    paths["metadata_json"].write_text(json.dumps(metadata, indent=2, ensure_ascii=False,
                                                  default=_json_safe), encoding="utf-8")
    return metadata
