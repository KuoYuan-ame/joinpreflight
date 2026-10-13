"""v7.1 behavior / invariants, no Olist download required."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import pytest
from joinpreflight.relationship_matrix import (select_features, plot_matrix, analyze_and_plot)


def demo_frame(n=150):
    rng = np.random.default_rng(14)
    x = rng.integers(1, 12, n)
    return pd.DataFrame({
        "item_count": x,
        "payment_total": 10 + rng.lognormal(4, .9, n),
        "avg_item_price": 20 + rng.lognormal(3, .7, n),
        "freight_total": 10 + rng.lognormal(2, .9, n),
        "delivery_days": rng.gamma(2, 6, n),
        "delivery_delay_days": rng.normal(-3, 6, n),
        "max_installments": rng.integers(1, 10, n),
        "payment_record_count": np.ones(n),
    })


def test_audit_contains_counts_scores_and_reasons():
    data = demo_frame()
    data.loc[0, "payment_total"] = np.nan
    selected, audit = select_features(data)
    assert len(selected) >= 2
    row = audit.set_index("feature").loc["payment_total"]
    assert row["non_null_count"] == len(data) - 1
    assert row["missing_count"] == 1
    assert 0 < row["information_score"] <= 1
    assert 0 < row["coverage"] < 1
    assert {"base_score", "selection_score", "manual_override", "reason"}.issubset(audit.columns)


def test_forced_keep_and_drop():
    data = demo_frame()
    selected, audit = select_features(data, max_features=4,
                                      force_include=["payment_record_count"],
                                      force_exclude=["freight_total"])
    assert "payment_record_count" in selected
    assert "freight_total" not in selected
    rows = audit.set_index("feature")
    assert "bypassed" in rows.loc["payment_record_count", "reason"]
    assert rows.loc["freight_total", "reason"] == "forced exclude"


def test_reject_invalid_manual_override():
    data = demo_frame()
    with pytest.raises(ValueError, match="cannot be force-included"):
        select_features(data, force_include=["item_count"], force_exclude=["item_count"])
    with pytest.raises(ValueError, match="unknown feature"):
        select_features(data, force_include=["arbitrary_column"])
    with pytest.raises(ValueError, match="missing"):
        select_features(data, force_include=["item_price_std"])


def test_profile_validation():
    with pytest.raises(ValueError, match="profile"):
        select_features(demo_frame(), profile="unexpected")


def test_visual_modes_long_tails_and_discrete(tmp_path: Path):
    df = demo_frame(n=180)
    df["payment_total"] = np.random.default_rng(2026).lognormal(4, 1.8, 180)
    df.loc[0:9, "delivery_delay_days"] = -80.
    path = tmp_path / "plot.png"
    meta = plot_matrix(df, ["item_count", "payment_total", "delivery_delay_days"],
                       path, max_points=150)
    assert meta["n"] == 3
    assert meta["feature_visualization"]["item_count"]["type"] == "discrete"
    assert meta["feature_visualization"]["payment_total"]["scale"] == "log1p"
    assert meta["rendered_panels"]["jitter"] >= 1
    assert path.exists() and path.with_suffix(".svg").exists()
    assert meta["pairwise_observation_counts"]["item_count"]["payment_total"] == 180
    assert meta["histogram_population"].startswith("all non-null")


def test_plot_reproducible_metadata_and_per_pair_count(tmp_path: Path):
    df = demo_frame()
    df.loc[:4, "freight_total"] = np.nan
    path = tmp_path / "plot.png"
    meta = plot_matrix(df, ["payment_total", "freight_total", "delivery_days"], path)
    assert meta["pairwise_observation_counts"]["payment_total"]["freight_total"] == len(df)-5
    assert meta["complete_case_orders"] == len(df)-5
    assert meta["feature_missing_counts"]["freight_total"] == 5
    assert meta["scatter_seed"] == 42


def test_scored_selection_respects_size_limit():
    selected, audit = select_features(demo_frame(), max_features=3)
    assert len(selected) == 3
    assert (audit["reason"].str.contains("figure size cap")).any()


def test_dense_continuous_panels_switch_to_hexbin(tmp_path: Path):
    df = demo_frame(n=1400)
    path = tmp_path / "dense.png"
    meta = plot_matrix(df, ["payment_total", "freight_total"], path, max_points=1400)
    assert meta["rendered_panels"]["hexbin"] == 1
    assert meta["rendered_panels"]["scatter"] == 0
