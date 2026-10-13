# JoinPreflight Adaptive Matrix v7.1

**Incremental upgrade** for an existing v7 project. The patch replaces only `src/joinpreflight/relationship_matrix.py` and `examples/09_adaptive_pair_matrix.py`, adds `tests/test_relationship_matrix_v71.py` and this guide. The v7 synthetic demo script is included unchanged as a convenience. It does **not** overwrite your existing JOIN engine, CLI, or unified report.

## Changes

1. **Auditable scored selection**. Candidates originate from the existing fixed registry of ten Olist order-level features. The selection process checks missingness, distinct counts, dominant-value fraction; then ranks eligible candidates by registry business priority, data coverage, an information heuristic, and feature-domain novelty. This is a transparent *heuristic*, not a predictive ML feature-selection algorithm.
2. **Manual override**. `--include FEATURE` forces an available registry feature into the matrix even if it normally fails the quality filter or would be considered redundant. The bypass and reason are written to CSV. `--exclude FEATURE` prevents selection. Conflicts, unknown feature names, nonexisting forced-included columns, and too many includes fail loudly.
3. **Adaptive plotting**. Right-tailed nonnegative continuous features may use log1p; severely skewed signed features may use asinh. Low-cardinality integer features are treated as discrete; scatter-only random jitter separates coincident dots. Dense continuous/continuous scatter panels are rendered with hexbins. Underlying order-level numbers and Spearman correlations are never transformed/jittered.
4. **Full-data distributions and statistics**. Diagonal histograms use all available non-null observations. Correlations use all available pairwise non-null observations, not the scatter sample. Lower-triangle sampling is complete-case, deterministic (`seed=42`). The distinction is reported explicitly.
5. **Reproducibility**. Metadata includes the selected columns, coverage, zero/missing counts, pairwise effective N for every combination, plotting modes, random seed, and thresholds. CSV audit explains every acceptance, exclusion, forced override, or figure-size cap.

## Install

You already installed SciPy 1.18.1. No new environment is necessary. To check:

```powershell
.\.venv\Scripts\python.exe -c "import pandas, matplotlib, scipy; print('Dependencies OK')"
```

If installing on another machine, your `pyproject.toml`'s visualization extras should include `matplotlib>=3.8` and `scipy>=1.10`; add both to the `dev` extra too if `dev` does not depend on `viz`. Do not create a second `[project.optional-dependencies]` section.

## Quick demo

```powershell
.\.venv\Scripts\python.exe .\examples\10_synthetic_matrix_demo.py
```

## Real Olist data

```powershell
$root = "C:\Users\13927\PycharmProjects\olist-ecommerce-analysis\data"
$orders = Join-Path $root "olist_orders_dataset.csv"
$items = Join-Path $root "olist_order_items_dataset.csv"
$payments = Join-Path $root "olist_order_payments_dataset.csv"

.\.venv\Scripts\python.exe .\examples\09_adaptive_pair_matrix.py $orders $items $payments --max-features 7 --profile exploratory --output reports\olist_v71.png
```

To **keep** average item price even if the redundancy heuristic ordinarily drops it, and to remove delivery delay for an alternative view:

```powershell
.\.venv\Scripts\python.exe .\examples\09_adaptive_pair_matrix.py $orders $items $payments --max-features 7 --include avg_item_price --exclude delivery_delay_days --output reports\olist_business_v71.png
```

If you want two manual includes, repeat `--include`.

## Output

- `olist_v71.png`: high-resolution research-style matrix;
- `olist_v71.svg`: vector artwork;
- `olist_v71_candidate_audit.csv`: audit log for **all ten candidates**, including `coverage`, `non_null_count`, `missing_count`, `information_score`, `base_score`, `selection_score`, `selected`, `reason`, `correlated_feature`, `redundancy_rho`;
- `olist_v71_metadata.json`: visualization modes, sample counts, pairwise observation counts, included/excluded fields and selection rule configuration.

The number of selected variables can change compared with v7. If fewer than two quality-passing (or explicitly included) features are available, an exception is preferable to producing a misleading chart.

## Interpreting plots correctly

- `'log1p'` displayed on an axis means **the graph coordinate was transformed**, not the source observations or the computed Spearman coefficient. `asinh` supports both signs.
- Discrete jitter is for visibility **only**; it must never affect statistical summaries.
- Hexbin shading corresponds to density; not to a higher monetary impact.
- No causal relation follows from a strong Spearman coefficient. `delivery_days` and `delivery_delay_days` share the same delivery timestamp. `payment_total` and `avg_item_price` are economically related, so do not assume a high correlation makes either irrelevant.
- Missing payments are not equivalent to zero payment; missingness appears in the audit. `item_count` counts order-item *rows*, not necessarily physical units.
- The plot only auto-selects among **ten known Olist-derived features**; it is not a schema-independent automatic feature discoverer.

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The v7.1 patch adds seven tests. If all your earlier 63 collected tests are present, the anticipated count is **70**, but trust the actual pytest collection and results.

## Design limitations / next validation

The plot uses a deterministic complete-case scatter subsample; correlational results use pairwise-valid full observations. Drawing panels with different effective samples is deliberate and disclosed. Changes to the ranking profile should be treated as visualization sensitivity analysis. Use `candidate_audit.csv` to justify selection rather than assuming the highest score yields the most causally meaningful feature.
