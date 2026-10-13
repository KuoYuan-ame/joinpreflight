"""Order-grain adaptive relationship matrix for exploratory JOIN diagnostics.

Important: this module intentionally excludes calculated JOIN overcount from the
predictor matrix, because overcount is algebraically determined by payment and
item multiplicity. It is exploratory, not a causal explanation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Candidate:
    name: str
    label: str
    domain: str
    priority: int
    description: str


CANDIDATES = [
    Candidate("item_count", "Item rows", "items", 1, "Number of order-item rows, not necessarily units"),
    Candidate("payment_total", "Payment total (BRL)", "payments", 1, "Total recorded payments at order grain"),
    Candidate("avg_item_price", "Mean item price (BRL)", "items", 2, "Mean product price across item rows"),
    Candidate("freight_total", "Freight total (BRL)", "items", 3, "Sum of line-item freight charges"),
    Candidate("delivery_days", "Delivery time (days)", "orders", 4, "Customer delivery timestamp minus purchase timestamp"),
    Candidate("delivery_delay_days", "Delivery delay (days)", "orders", 5, "Delivery timestamp minus estimated delivery timestamp"),
    Candidate("max_installments", "Max installments", "payments", 6, "Largest installment count observed for this order"),
    Candidate("payment_record_count", "Payment records", "payments", 7, "Number of payment rows associated with order"),
    Candidate("payment_type_count", "Payment types", "payments", 8, "Number of different payment types on an order"),
    Candidate("item_price_std", "Item price SD (BRL)", "items", 9, "Within-order item price standard deviation (requires >=2 items)"),
]
CANDIDATE_MAP = {c.name: c for c in CANDIDATES}


def _read_required(path: str | Path, kind: str) -> pd.DataFrame:
    p = Path(path)
    df = pd.read_csv(p, dtype={"order_id": "string"}, low_memory=False)
    if "order_id" not in df.columns:
        raise ValueError(f"{kind}: missing required column order_id in {p}")
    if df["order_id"].isna().any():
        raise ValueError(f"{kind}: null order_id keys are not supported by this analysis")
    return df


def _add_numeric(df: pd.DataFrame, col: str) -> None:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")


def build_order_features(
    orders_csv: str | Path, items_csv: str | Path, payments_csv: str | Path
) -> pd.DataFrame:
    """Create one and only one row per order, preserving the Orders population."""
    orders = _read_required(orders_csv, "orders")
    items = _read_required(items_csv, "items")
    payments = _read_required(payments_csv, "payments")
    if orders["order_id"].duplicated().any():
        raise ValueError("orders: order_id must be unique (one row per order)")

    left = orders[["order_id"]].copy()
    for col in ["order_purchase_timestamp", "order_delivered_customer_date", "order_estimated_delivery_date"]:
        if col in orders.columns:
            left[col] = pd.to_datetime(orders[col], errors="coerce")
    if {"order_purchase_timestamp", "order_delivered_customer_date"}.issubset(left.columns):
        left["delivery_days"] = (
            left["order_delivered_customer_date"] - left["order_purchase_timestamp"]
        ).dt.total_seconds() / 86400.0
    if {"order_estimated_delivery_date", "order_delivered_customer_date"}.issubset(left.columns):
        left["delivery_delay_days"] = (
            left["order_delivered_customer_date"] - left["order_estimated_delivery_date"]
        ).dt.total_seconds() / 86400.0
    left = left.drop(columns=[c for c in left if c.endswith("timestamp") or c.endswith("date") and c != "order_id"], errors="ignore")

    for name in ["price", "freight_value"]:
        _add_numeric(items, name)
    ig = items.groupby("order_id", dropna=False)
    item_data = pd.DataFrame({"item_count": ig.size()})
    if "price" in items.columns:
        item_data["avg_item_price"] = ig["price"].mean()
        item_data["item_price_std"] = ig["price"].std(ddof=1)
    if "freight_value" in items.columns:
        item_data["freight_total"] = ig["freight_value"].sum(min_count=1)
    item_data = item_data.reset_index()

    for name in ["payment_value", "payment_installments"]:
        _add_numeric(payments, name)
    pg = payments.groupby("order_id", dropna=False)
    payment_data = pd.DataFrame({"payment_record_count": pg.size()})
    if "payment_value" in payments.columns:
        payment_data["payment_total"] = pg["payment_value"].sum(min_count=1)
    if "payment_installments" in payments.columns:
        payment_data["max_installments"] = pg["payment_installments"].max()
    if "payment_type" in payments.columns:
        payment_data["payment_type_count"] = pg["payment_type"].nunique()
    payment_data = payment_data.reset_index()

    merged = left.merge(item_data, on="order_id", how="left", validate="1:1")
    merged = merged.merge(payment_data, on="order_id", how="left", validate="1:1")
    # A missing item/payment row is not equivalent to a 0 BRL amount.
    # Only the count of rows is genuinely 0 when no matches exist.
    for count_name in ["item_count", "payment_record_count", "payment_type_count"]:
        if count_name in merged.columns:
            merged[count_name] = merged[count_name].fillna(0).astype(int)
    if len(merged) != len(orders) or merged["order_id"].nunique() != len(orders):
        raise AssertionError("Order-grain integrity check failed")
    return merged




# v7.1: selection remains limited to the audited order-level candidate registry.
# Do not automatically ingest arbitrary numeric identifiers or mechanically
# calculated metric-inflation targets into an exploratory predictor matrix.


def _normalise_feature_names(names: list[str] | tuple[str, ...] | None, label: str) -> list[str]:
    values = list(names or [])
    if len(values) != len(set(values)):
        raise ValueError(f"{label}: repeated feature names")
    unknown = set(values) - set(CANDIDATE_MAP)
    if unknown:
        raise ValueError(f"{label}: unknown feature(s): {', '.join(sorted(unknown))}")
    return values


def _information_score(distinct: int, mode_share: float | None) -> float:
    if not distinct or mode_share is None:
        return 0.0
    diversity = min(1.0, math.log1p(distinct) / math.log1p(50))
    return round(0.55 * (1 - mode_share) + 0.45 * diversity, 6)


def _profile_weights(profile: str) -> dict[str, float]:
    # Weight profiles are *transparent heuristics*, not a learned predictor.
    choices = {
        "exploratory": {"priority": .55, "coverage": .20, "information": .15, "domain": .10},
        "business": {"priority": .60, "coverage": .15, "information": .10, "domain": .15},
        "risk": {"priority": .65, "coverage": .15, "information": .15, "domain": .05},
    }
    if profile not in choices:
        raise ValueError(f"profile must be one of: {', '.join(choices)}")
    return choices[profile]


def select_features(
    frame: pd.DataFrame,
    *,
    min_coverage: float = 0.75,
    min_distinct: int = 6,
    max_mode_share: float = 0.95,
    redundant_at: float = 0.93,
    max_features: int = 7,
    force_include: list[str] | tuple[str, ...] | None = None,
    force_exclude: list[str] | tuple[str, ...] | None = None,
    profile: str = "exploratory",
) -> tuple[list[str], pd.DataFrame]:
    """Quality gate -> scored greedy selection -> full selection audit.

    Forced includes bypass quality and redundancy heuristics but never missing
    columns; audit explicitly records the override and failed quality checks.
    Automatic feature selection keeps high-priority variables, improves domain
    diversity, and rejects near-duplicate ranked variables.
    """
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")
    if not 2 <= max_features <= 10:
        raise ValueError("max_features must be in the range 2..10")
    if not 0 < min_coverage <= 1 or not 0 < max_mode_share <= 1:
        raise ValueError("Coverage and dominant share must belong to (0,1]")
    if not isinstance(min_distinct, int) or min_distinct < 2:
        raise ValueError("min_distinct must be >= 2")
    if not 0 <= redundant_at <= 1:
        raise ValueError("redundant_at must belong to [0,1]")
    weights = _profile_weights(profile)
    included = _normalise_feature_names(force_include, "force_include")
    excluded = _normalise_feature_names(force_exclude, "force_exclude")
    overlap = set(included) & set(excluded)
    if overlap:
        raise ValueError("A feature cannot be force-included and force-excluded: " + ", ".join(sorted(overlap)))
    if len(included) > max_features:
        raise ValueError("force_include contains more features than max_features")
    missing = [name for name in included if name not in frame.columns]
    if missing:
        raise ValueError("Cannot force-include source columns that are missing: " + ", ".join(missing))

    observations: dict[str, pd.Series] = {}
    entries: dict[str, dict] = {}
    count = len(frame)
    for index, candidate in enumerate(CANDIDATES):
        name = candidate.name
        s = (pd.to_numeric(frame[name], errors="coerce").replace([np.inf, -np.inf], np.nan)
             if name in frame.columns else pd.Series(dtype="float64"))
        observations[name] = s
        valid = s.dropna()
        coverage = len(valid) / count if count else 0.0
        distinct = int(valid.nunique())
        mode_share = float(valid.value_counts(normalize=True).iloc[0]) if distinct else None
        information = _information_score(distinct, mode_share)
        # Explicit registry priority is weighted against observed quality;
        # dynamic domain coverage is added at each greedy selection step.
        base = (weights["priority"] * (1 - index / max(1, len(CANDIDATES)))
                + weights["coverage"] * coverage
                + weights["information"] * information)
        reasons: list[str] = []
        if name not in frame.columns:
            reasons.append("not available in source columns")
        else:
            if coverage < min_coverage:
                reasons.append("insufficient coverage")
            if distinct < min_distinct:
                reasons.append("too few distinct values")
            if mode_share is not None and mode_share > max_mode_share:
                reasons.append("near-constant variable")
        entries[name] = {
            "feature": name, "domain": candidate.domain, "description": candidate.description,
            "priority": candidate.priority,
            "non_null_count": int(len(valid)), "missing_count": int(max(0, count - len(valid))),
            "coverage": round(coverage, 8), "distinct": distinct,
            "mode_share": round(mode_share, 8) if mode_share is not None else None,
            "information_score": information, "base_score": round(base, 6),
            "selection_score": None, "manual_override": "none",
            "selected": False, "correlated_feature": "", "redundancy_rho": None,
            "reason": "; ".join(reasons) if reasons else "eligible",
        }

    selected: list[str] = []
    for name in included:
        selected.append(name)
        entries[name].update(selected=True, manual_override="forced include",
                             reason="forced include" + ("; bypassed: " + entries[name]["reason"]
                                 if entries[name]["reason"] != "eligible" else ""),
                             selection_score=entries[name]["base_score"])
    for name in excluded:
        entries[name].update(manual_override="forced exclude", reason="forced exclude")

    remaining = {c.name for c in CANDIDATES if c.name not in included and c.name not in excluded
                 and entries[c.name]["reason"] == "eligible"}
    rejected: dict[str, str] = {}
    while remaining and len(selected) < max_features:
        # Greedy score rewards informative/complete high-priority features from
        # underrepresented domains; ties follow original registry ordering.
        ranked = sorted(remaining, key=lambda name: (
            -(entries[name]["base_score"] + weights["domain"] *
              (CANDIDATE_MAP[name].domain not in {CANDIDATE_MAP[t].domain for t in selected})),
            list(CANDIDATE_MAP).index(name)))
        name = ranked[0]
        remaining.remove(name)
        candidate = CANDIDATE_MAP[name]
        score = entries[name]["base_score"] + weights["domain"] * (
            candidate.domain not in {CANDIDATE_MAP[t].domain for t in selected})
        entries[name]["selection_score"] = round(score, 6)
        for prior in selected:
            pair = pd.concat([observations[name], observations[prior]], axis=1).dropna()
            if len(pair) < 10:
                continue
            # Check *pairwise* constancy first: a globally varying field can
            # become constant on the rows shared by these two features.
            # Spearman = Pearson correlation of average tied ranks.
            if pair.iloc[:, 0].nunique() < 2 or pair.iloc[:, 1].nunique() < 2:
                continue
            ranked = pair.rank(method="average")
            rho = ranked.iloc[:, 0].corr(ranked.iloc[:, 1], method="pearson")
            if pd.notna(rho) and abs(float(rho)) >= redundant_at:
                entries[name].update(correlated_feature=prior,
                                     redundancy_rho=round(float(rho), 6))
                rejected[name] = f"near-duplicate of {prior} (Spearman={rho:+.2f})"
                break
        if name not in rejected:
            selected.append(name)
            entries[name].update(selected=True, reason="selected")
        else:
            entries[name]["reason"] = rejected[name]

    for name in remaining:
        entries[name]["reason"] = f"figure size cap ({max_features})"
    audit = pd.DataFrame([entries[c.name] for c in CANDIDATES])
    return selected, audit


def _visual_kind(s: pd.Series) -> dict:
    """Choose readable rendering without changing source values or correlations.

    The transform affects charts only. Spearman still uses raw order-level values.
    'log1p' is used only for nonnegative, sufficiently right-skewed variables.
    A signed, heavy-tailed variable uses asinh instead of an invalid log1p.
    """
    valid = s.replace([np.inf, -np.inf], np.nan).dropna()
    if valid.empty:
        return {"scale": "linear", "type": "continuous", "skew": None}
    distinct = int(valid.nunique())
    integer_like = bool(np.all(np.isclose(valid.to_numpy(dtype=float), np.rint(valid.to_numpy(dtype=float)), atol=1e-9)))
    discrete = integer_like and distinct <= 25
    skew = float(valid.skew()) if len(valid) >= 3 else 0.0
    if not math.isfinite(skew):
        skew = 0.0
    q50 = float(valid.quantile(.5))
    q99 = float(valid.quantile(.99))
    ratio = q99 / max(q50, 1.0) if q50 >= 0 else 0.0
    scale = "linear"
    if not discrete and skew > 2.5 and ratio >= 10 and valid.min() >= 0:
        scale = "log1p"
    elif not discrete and abs(skew) > 2.5 and valid.min() < 0:
        scale = "asinh"
    return {"scale": scale, "type": "discrete" if discrete else "continuous", "skew": round(skew, 5)}


def _transform(values: np.ndarray, mode: str) -> np.ndarray:
    if mode == "log1p":
        return np.log1p(values)
    if mode == "asinh":
        return np.arcsinh(values)
    return values


def plot_matrix(frame: pd.DataFrame, features: list[str], output_png: str | Path,
                *, max_points: int = 2400, seed: int = 42,
                vector_svg: bool = True) -> dict:
    """Upper: full-population pairwise Spearman; diagonal: full-data histogram;
    lower: reproducible complete-case scatter/hexbin. Visual transforms and
    jitter do not affect the reported correlation or the underlying data.
    """
    if len(features) < 2:
        raise ValueError("At least two approved features are needed to plot a matrix")
    if max_points < 100:
        raise ValueError("max_points must be >= 100")
    unknown = [x for x in features if x not in frame]
    if unknown:
        raise ValueError("Missing selected features: " + ", ".join(unknown))
    n = len(features)
    values = frame[features].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    complete = values.dropna()
    if len(complete) < 10:
        raise ValueError("Fewer than 10 complete orders; cannot draw a reliable pair matrix")
    points = (complete.sample(n=max_points, random_state=seed)
              if len(complete) > max_points else complete.copy())
    settings = {f: _visual_kind(values[f]) for f in features}
    fig, axes = plt.subplots(n, n, figsize=(max(10, n * 2.15), max(10, n * 2.08)), dpi=155)
    navy, blue, orange = "#1D3854", "#397f9e", "#d87443"
    fig.patch.set_facecolor("white")
    # Constant inputs have undefined Spearman rho, not zero correlation.
    # Rank-Pearson callback avoids SciPy's ConstantInputWarning while
    # preserving average-tie ranks on exactly the same available pairs.
    def _rank_spearman(a: np.ndarray, b: np.ndarray) -> float:
        x, y = pd.Series(a), pd.Series(b)
        if x.nunique() < 2 or y.nunique() < 2:
            return float("nan")
        return float(x.rank(method="average").corr(y.rank(method="average"),
                                                     method="pearson"))

    correlations = values.corr(method=_rank_spearman, min_periods=10)
    valid_mask = values.notna().astype("int64")
    pair_counts = valid_mask.T.dot(valid_mask)
    render_counts = {"scatter": 0, "hexbin": 0, "jitter": 0}
    for i, yi in enumerate(features):
        for j, xj in enumerate(features):
            ax = axes[i, j]
            ax.spines[["top", "right"]].set_visible(False)
            ax.spines[["bottom", "left"]].set_color("#d8e3ea")
            ax.tick_params(axis="both", labelsize=7, colors="#567188", length=2)
            xmode, ymode = settings[xj]["scale"], settings[yi]["scale"]
            if i == j:
                full = values[yi].dropna().to_numpy(dtype=float)
                transformed = _transform(full, ymode)
                if settings[yi]["type"] == "discrete":
                    vals, freq = np.unique(transformed, return_counts=True)
                    ax.bar(vals, freq, width=.75, color=blue, alpha=.85)
                else:
                    ax.hist(transformed, bins=25, color=blue, alpha=.85,
                            edgecolor="white", linewidth=.25)
                ax.grid(axis="y", color="#e6edf2", linewidth=.5)
                ax.set_axisbelow(True)
                ax.text(.97, .91, chr(ord('a') + i), transform=ax.transAxes,
                        ha="right", va="top", weight="bold", color=navy, fontsize=10)
            elif i > j:
                x = _transform(points[xj].to_numpy(dtype=float), xmode)
                y = _transform(points[yi].to_numpy(dtype=float), ymode)
                discrete_x = settings[xj]["type"] == "discrete"
                discrete_y = settings[yi]["type"] == "discrete"
                if (len(points) >= 1200 and not discrete_x and not discrete_y
                        and points[xj].nunique() >= 40 and points[yi].nunique() >= 40):
                    ax.hexbin(x, y, gridsize=23, mincnt=1, bins="log", cmap="Blues", linewidths=0,
                              rasterized=True)
                    render_counts["hexbin"] += 1
                else:
                    if discrete_x or discrete_y:
                        rng = np.random.default_rng(seed + i * 97 + j * 271)
                        if discrete_x:
                            x = x + rng.uniform(-.12, .12, len(x))
                        if discrete_y:
                            y = y + rng.uniform(-.12, .12, len(y))
                        render_counts["jitter"] += 1
                    ax.scatter(x, y, s=5, alpha=.22, c=blue,
                               edgecolors="none", rasterized=True)
                    render_counts["scatter"] += 1
                ax.grid(color="#e9eef2", linewidth=.4)
                ax.set_axisbelow(True)
            else:
                rho = correlations.loc[yi, xj]
                ax.set_facecolor("#f5f8fb")
                ax.set_xticks([])
                ax.set_yticks([])
                ax.text(.5, .58, "ρ = " + (f"{rho:+.2f}" if pd.notna(rho) else "n/a"),
                        ha="center", va="center", transform=ax.transAxes, fontsize=11,
                        weight="bold", color=(orange if pd.notna(rho) and abs(rho) >= .65 else navy))
                ax.text(.5, .27, f"Spearman · n={int(pair_counts.loc[yi, xj]):,}",
                        ha="center", va="center", transform=ax.transAxes,
                        fontsize=7, color="#607c91")
            if i < n - 1:
                ax.set_xticklabels([])
            if j > 0:
                ax.set_yticklabels([])
            if i == n - 1:
                label = CANDIDATE_MAP[xj].label if xj in CANDIDATE_MAP else xj
                ax.set_xlabel(label + (" [log1p]" if xmode == "log1p" else
                                       " [asinh]" if xmode == "asinh" else ""),
                              fontsize=8, color=navy)
            if j == 0:
                label = CANDIDATE_MAP[yi].label if yi in CANDIDATE_MAP else yi
                ax.set_ylabel(label + (" [log1p]" if ymode == "log1p" else
                                       " [asinh]" if ymode == "asinh" else ""),
                              fontsize=8, color=navy)
    fig.suptitle(f"JoinPreflight  |  Adaptive Order-level Relationship Matrix ({n} × {n})",
                 color=navy, weight="bold", fontsize=16, y=.997)
    fig.text(.5, .972, f"{len(frame):,} orders  ·  {len(complete):,} complete cases  ·  "
                         f"{len(points):,} scatter sample  ·  full-data pairwise Spearman",
             ha="center", va="top", fontsize=8, color="#587186")
    fig.subplots_adjust(left=.13, right=.985, bottom=.12, top=.92, wspace=.13, hspace=.13)
    out = Path(output_png)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=215, facecolor="white")
    if vector_svg:
        fig.savefig(out.with_suffix(".svg"), facecolor="white")
    plt.close(fig)
    return {
        "n": n, "features": features,
        "total_orders": int(len(frame)),
        "complete_case_orders": int(len(complete)),
        "scatter_sample_orders": int(len(points)),
        "correlation_method": "Spearman rank; all available pairwise observations (untransformed)",
        "scatter_sampling": "complete-case uniform random sample; deterministic seed",
        "scatter_seed": seed,
        "histogram_population": "all non-null observations for each selected feature",
        "feature_visualization": settings,
        "rendered_panels": render_counts,
        "feature_missing_counts": {f: int(len(values) - values[f].notna().sum()) for f in features},
        "pairwise_observation_counts": {
            k: {v: int(pair_counts.loc[k, v]) for v in features} for k in features},
        "synthetic_warning": "None: data values supplied by caller; check source provenance",
    }


def analyze_and_plot(orders_csv: str | Path, items_csv: str | Path,
                     payments_csv: str | Path, output_png: str | Path,
                     *, max_features: int = 7, max_points: int = 2400,
                     min_coverage: float = .75, min_distinct: int = 6,
                     max_mode_share: float = .95, redundant_at: float = .93,
                     force_include: list[str] | tuple[str, ...] | None = None,
                     force_exclude: list[str] | tuple[str, ...] | None = None,
                     profile: str = "exploratory") -> dict:
    frame = build_order_features(orders_csv, items_csv, payments_csv)
    selected, audit = select_features(
        frame, max_features=max_features, min_coverage=min_coverage,
        min_distinct=min_distinct, max_mode_share=max_mode_share,
        redundant_at=redundant_at, force_include=force_include,
        force_exclude=force_exclude, profile=profile)
    if len(selected) < 2:
        raise ValueError("Fewer than two informative numeric features. Consider adjusting "
                         "filters or inspecting the source tables.")
    output = Path(output_png)
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata = plot_matrix(frame, selected, output, max_points=max_points)
    audit.to_csv(output.with_name(output.stem + "_candidate_audit.csv"), index=False)
    metadata["dataset_files"] = {
        "orders": Path(orders_csv).name, "items": Path(items_csv).name,
        "payments": Path(payments_csv).name}
    metadata["selection_rules"] = {
        "min_coverage": min_coverage, "min_distinct": min_distinct,
        "max_mode_share": max_mode_share, "redundant_at": redundant_at,
        "max_features": max_features, "profile": profile,
        "force_include": list(force_include or []),
        "force_exclude": list(force_exclude or []),
    }
    output.with_name(output.stem + "_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata
