"""JoinPreflight v7.3: exploratory within-segment rank-correlation bootstrap.

Order-grain, pairwise complete-case, within-group IID percentile bootstrap.
This produces *nominal*, unadjusted CIs; no formal significance or causal claims.
Conditional on Olist being treated as an IID sample, not a population census.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import rankdata

from joinpreflight.relationship_matrix import build_order_features, CANDIDATE_MAP
from joinpreflight.segmented_analysis import classify_orders, safe_spearman

DEFAULT_PAIRS = (
    ("payment_total", "max_installments"),
    ("avg_item_price", "freight_total"),
    ("freight_total", "delivery_days"),
)
COLORS = {"point": "#347e9f", "interval": "#347e9f", "zero": "#d57a48", "text": "#1d3854"}


def _validate_pairs(pairs: Sequence[tuple[str, str]], frame: pd.DataFrame) -> list[tuple[str, str]]:
    if not pairs:
        raise ValueError("At least one variable pair is required")
    if len(pairs) > 28:
        raise ValueError("No more than 28 variable pairs per figure")
    seen = set()
    result = []
    for pair in pairs:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("Pairs must contain two variable names")
        a, b = pair
        if not isinstance(a, str) or not isinstance(b, str):
            raise ValueError("Pair names must be strings")
        if a == b:
            raise ValueError(f"Self-pair is not supported: {a}")
        missing = [name for name in (a, b) if name not in CANDIDATE_MAP or name not in frame.columns]
        if missing:
            raise ValueError("Unknown or unavailable candidate feature(s): " + ", ".join(missing))
        key = frozenset((a, b))
        if key in seen:
            raise ValueError(f"Repeated unordered pair: {a} / {b}")
        seen.add(key)
        result.append((a, b))
    return result


def _valid_pair_arrays(group: pd.DataFrame, a: str, b: str) -> tuple[np.ndarray, np.ndarray]:
    numeric = group[[a, b]].apply(pd.to_numeric, errors="coerce")
    numeric = numeric.replace([np.inf, -np.inf], np.nan).dropna()
    return numeric[a].to_numpy(dtype=np.float64), numeric[b].to_numpy(dtype=np.float64)


def _rank_pearson(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman rho with average ranks for ties; return NaN on constants."""
    # np.ptp can overflow for huge inputs; direct equality is enough here.
    if x.size < 3 or np.all(x == x[0]) or np.all(y == y[0]):
        return float("nan")
    rx = rankdata(x, method="average").astype(np.float64, copy=False)
    ry = rankdata(y, method="average").astype(np.float64, copy=False)
    rx -= rx.mean()
    ry -= ry.mean()
    denom = np.linalg.norm(rx) * np.linalg.norm(ry)
    if denom <= 0 or not np.isfinite(denom):
        return float("nan")
    return float(np.clip(np.dot(rx, ry) / denom, -1., 1.))


def _bootstrap_group(x: np.ndarray, y: np.ndarray, n_boot: int,
                     rng: np.random.Generator) -> np.ndarray:
    """IID resample *orders* within one segment, keeping its pairwise-valid N."""
    n = len(x)
    results = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        ids = rng.integers(0, n, size=n)
        results[b] = _rank_pearson(x[ids], y[ids])
    return results


def bootstrap_segment_differences(
    frame: pd.DataFrame,
    *,
    pairs: Sequence[tuple[str, str]] = DEFAULT_PAIRS,
    n_boot: int = 400,
    confidence: float = 0.95,
    seed: int = 42,
    min_pairs: int = 30,
    min_valid_fraction: float = 0.95,
) -> dict:
    """Estimate Δrho = rho(Multi) - rho(Single) with percentile CIs.

    Pairwise missing values are discarded BEFORE bootstrap in each group.
    Different pairs can have different analysis populations. Both segments
    are resampled independently, with replacement and at their original
    pairwise-valid sample sizes. Invalid replicates are not set to zero.
    The percentile CI is nominal and unadjusted for multiple comparisons.
    """
    if not isinstance(n_boot, int) or isinstance(n_boot, bool) or not 50 <= n_boot <= 20000:
        raise ValueError("n_boot must be an integer between 50 and 20000")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be strictly between 0 and 1")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if not isinstance(min_pairs, int) or min_pairs < 3:
        raise ValueError("min_pairs must be at least 3")
    if not 0 < min_valid_fraction <= 1:
        raise ValueError("min_valid_fraction must belong to (0,1]")

    classified = classify_orders(frame)
    pairs = _validate_pairs(pairs, classified)
    counts = {name: int(classified["segment"].eq(name).sum())
              for name in ("No items", "Single", "Multi")}
    groups = {name: classified.loc[classified.segment.eq(name)]
              for name in ("Single", "Multi")}
    # Separate, reproducible RNG streams per pair and per group.
    seeds = np.random.SeedSequence(seed).spawn(len(pairs) * 2)
    alpha = 1.0 - confidence
    rows = []
    for i, (a, b) in enumerate(pairs):
        arrays = {label: _valid_pair_arrays(groups[label], a, b)
                  for label in ("Single", "Multi")}
        observed = {label: safe_spearman(groups[label][a], groups[label][b],
                                         min_pairs=min_pairs)
                    for label in ("Single", "Multi")}
        row = {
            "feature_x": a, "feature_y": b,
            "n_single": observed["Single"]["n"], "n_multi": observed["Multi"]["n"],
            "single_status": observed["Single"]["status"],
            "multi_status": observed["Multi"]["status"],
            "rho_single": observed["Single"]["rho"],
            "rho_multi": observed["Multi"]["rho"],
            "delta_rho_multi_minus_single": None,
            "ci_low": None, "ci_high": None,
            "bootstrap_sd": None, "successful_replicates": 0,
            "invalid_replicates": 0, "nominal_ci_excludes_zero": None,
            "status": "not_estimable", "method": "stratified_iid_percentile_bootstrap",
        }
        if any(observed[label]["status"] != "ok" for label in ("Single", "Multi")):
            rows.append(row)
            continue
        row["delta_rho_multi_minus_single"] = (
            observed["Multi"]["rho"] - observed["Single"]["rho"]
        )
        bs = {}
        for offset, label in enumerate(("Single", "Multi")):
            x, y = arrays[label]
            bs[label] = _bootstrap_group(x, y, n_boot, np.random.default_rng(seeds[2*i+offset]))
        deltas = bs["Multi"] - bs["Single"]
        valid = deltas[np.isfinite(deltas)]
        row["successful_replicates"] = int(len(valid))
        row["invalid_replicates"] = int(n_boot - len(valid))
        if len(valid) < n_boot * min_valid_fraction or len(valid) < 2:
            row["status"] = "unstable_bootstrap"
            rows.append(row)
            continue
        low, high = np.quantile(valid, [alpha / 2, 1-alpha/2])
        row.update({
            "ci_low": float(low), "ci_high": float(high),
            "bootstrap_sd": float(np.std(valid, ddof=1)),
            "nominal_ci_excludes_zero": bool(low > 0 or high < 0),
            "status": "ok",
        })
        rows.append(row)

    return {
        "version": "v7.3",
        "total_orders": int(len(classified)),
        "group_counts": counts,
        "pairs": pd.DataFrame(rows),
        "parameters": {
            "n_boot": n_boot, "confidence": confidence, "seed": seed,
            "min_pairs": min_pairs, "min_valid_fraction": min_valid_fraction,
            "bootstrap_unit": "order_id (one row per order)",
            "resampling": "pairwise complete-case, within-group IID, fixed group N",
            "interval": "nominal percentile interval, no multiplicity adjustment",
        },
        "limitations": [
            "Exploratory post-selection intervals: variable pairs were selected after inspecting Olist correlations.",
            "Intervals assume approximately independent orders sampled from a relevant population; repeated customers/sellers may violate this.",
            "Bootstrap CI excludes zero is not a multiplicity-adjusted statistical test or causal evidence.",
            "Missingness is handled pairwise; comparisons across pairs may use different orders.",
        ],
    }


def plot_bootstrap_forest(result: dict, output: str | Path) -> None:
    """Single forest plot with truthful unadjusted bootstrap intervals."""
    frame = result["pairs"]
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    n = len(frame)
    fig, ax = plt.subplots(figsize=(11.8, max(4.6, 1.03*n + 2.6)), dpi=160)
    fig.patch.set_facecolor("white")
    plotted = []
    for i, r in frame.iterrows():
        label = f"{str(r['feature_x']).replace('_',' ')} / {str(r['feature_y']).replace('_',' ')}"
        if r["status"] != "ok":
            ax.text(0.015, i, f"n/a  ({r['status']})", transform=ax.get_yaxis_transform(),
                    va="center", fontsize=9, color="#ad5d4b")
            continue
        point = float(r["delta_rho_multi_minus_single"])
        low, high = float(r["ci_low"]), float(r["ci_high"])
        ax.plot([low, high], [i, i], linewidth=2.7, color=COLORS["interval"], zorder=2)
        ax.plot([low, low], [i-.10, i+.10], color=COLORS["interval"], linewidth=1.2)
        ax.plot([high, high], [i-.10, i+.10], color=COLORS["interval"], linewidth=1.2)
        ax.scatter([point], [i], color=COLORS["point"], s=53, edgecolor="white", zorder=3)
        plotted += [point, low, high]
    ax.set_yticks(range(n), [str(r.feature_x).replace('_',' ') + " / " + str(r.feature_y).replace('_',' ')
                                for r in frame.itertuples()], fontsize=9)
    ax.invert_yaxis()
    ax.axvline(0, color=COLORS["zero"], linestyle="--", linewidth=1.5, label="Zero difference")
    extent = max([abs(x) for x in plotted] + [.10])
    lim = min(2.0, max(.12, extent*1.22))
    ax.set_xlim(-lim, lim)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#dae5ed")
    ax.grid(axis="x", color="#e7edf2", zorder=0)
    ax.tick_params(axis="y", length=0, pad=9, colors=COLORS["text"])
    ax.tick_params(axis="x", colors="#566d82")
    ax.set_xlabel("Δ Spearman ρ = Multi − Single", fontsize=11, color=COLORS["text"])
    fig.suptitle("JoinPreflight  |  Segmented Bootstrap Comparison", y=.98,
                 fontsize=18, fontweight="bold", color=COLORS["text"])
    info = result["parameters"]
    fig.text(.53, .916, f"Nominal {info['confidence']:.0%} percentile CIs  ·  {info['n_boot']:,} resamples  ·  seed {info['seed']}",
             ha="center", fontsize=10, color="#5e7388")
    fig.text(.53, .035, "Exploratory & unadjusted for multiple comparisons; no causal inference."
             "  CI bars exclude invalid resamples.", ha="center", fontsize=9, color="#657b90")
    fig.subplots_adjust(left=.33, right=.965, top=.865, bottom=.16)
    fig.savefig(output, dpi=200, facecolor="white")
    fig.savefig(output.with_suffix(".svg"), facecolor="white")
    fig.savefig(output.with_suffix(".pdf"), facecolor="white")
    plt.close(fig)


def analyze_and_export_bootstrap(
    orders_csv: str | Path, items_csv: str | Path, payments_csv: str | Path,
    output_prefix: str | Path,
    *, pairs: Sequence[tuple[str, str]] = DEFAULT_PAIRS,
    n_boot: int = 400, confidence: float = .95, seed: int = 42,
    min_pairs: int = 30,
) -> dict:
    """Complete CSV -> order grain -> bootstrap -> CSV/JSON/PNG/SVG/PDF workflow."""
    frame = build_order_features(orders_csv, items_csv, payments_csv)
    result = bootstrap_segment_differences(
        frame, pairs=pairs, n_boot=n_boot, confidence=confidence,
        seed=seed, min_pairs=min_pairs,
    )
    prefix = Path(output_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    fig = prefix.with_name(prefix.name + "_forest.png")
    plot_bootstrap_forest(result, fig)
    csv = prefix.with_name(prefix.name + "_results.csv")
    json_path = prefix.with_name(prefix.name + "_metadata.json")
    result["pairs"].to_csv(csv, index=False, float_format="%.12g")
    meta = {
        "version": result["version"],
        "total_orders": result["total_orders"],
        "group_counts": result["group_counts"],
        "parameters": result["parameters"],
        "limitations": result["limitations"],
        "source_files": {"orders": Path(orders_csv).name,
                         "items": Path(items_csv).name,
                         "payments": Path(payments_csv).name},
        "results": result["pairs"].astype(object).where(pd.notna(result["pairs"]), None).to_dict(orient="records"),
        "outputs": {"figure_png": str(fig), "figure_svg": str(fig.with_suffix(".svg")),
                    "figure_pdf": str(fig.with_suffix(".pdf")), "results_csv": str(csv),
                    "metadata_json": str(json_path)},
    }
    json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, allow_nan=False),
                         encoding="utf-8")
    return meta
