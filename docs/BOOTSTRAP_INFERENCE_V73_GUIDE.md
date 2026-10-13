# JoinPreflight v7.3 — Segmented Bootstrap Inference

## Purpose and analysis unit

This additive module analyzes rank-correlation differences between **Single** (one item row) and **Multi** (two or more item rows). Orders with no item rows remain counted and are excluded from the two-group contrast. The order is the bootstrap resampling unit, not a payment record or a line item.

Default focused comparisons (selected **after** preliminary v7.2 EDA and therefore **exploratory**):

1. `payment_total` vs `max_installments`
2. `avg_item_price` vs `freight_total`
3. `freight_total` vs `delivery_days`

All estimates use pairwise-complete data **within** each segment. The pair-specific analysis N may vary. The point estimate is `rho_multi - rho_single` using average ranks for tied values. For each pair, draw `B` replacement samples of the same pair-valid size from each group; recompute Spearman rho separately; subtract; and take the 2.5% and 97.5% quantiles as a **nominal 95% percentile interval**. The random seed and input filenames are saved.

These are **not** multiplicity-adjusted intervals, causal effects, formal test p-values, or evidence for a probabilistic sampling design. Pair selection is post hoc. If individual orders are correlated via repeated customers/sellers or time, an IID order bootstrap can understate uncertainty. Future work: cluster-aware bootstrap and validation on external data. A CI excluding 0 is labeled descriptively, not as a multiplicity-adjusted decision.

## Quick synthetic smoke test

```powershell
.\.venv\Scripts\python.exe .\examples\14_synthetic_bootstrap_demo.py
```

This outputs `reports/demo_bootstrap_*` from **fabricated** orders and is only for validating the workflow.

## Windows commands

From `C:\Users\13927\PycharmProjects\granguard`:

```powershell
$root = "C:\Users\13927\PycharmProjects\olist-ecommerce-analysis\data"
$orders = Join-Path $root "olist_orders_dataset.csv"
$items = Join-Path $root "olist_order_items_dataset.csv"
$payments = Join-Path $root "olist_order_payments_dataset.csv"

# Quick exploratory run (three focused pairs)
.\.venv\Scripts\python.exe .\examples\13_bootstrap_segmented.py $orders $items $payments --n-boot 400 --seed 42 --output reports\olist_bootstrap

# More stable estimate for the same three pairs (may run several minutes)
.\.venv\Scripts\python.exe .\examples\13_bootstrap_segmented.py $orders $items $payments --n-boot 1000 --seed 42 --output reports\olist_bootstrap_1000

# Or choose specific pairs
.\.venv\Scripts\python.exe .\examples\13_bootstrap_segmented.py $orders $items $payments --n-boot 400 --pair payment_total max_installments --pair freight_total delivery_days --output reports\selected_bootstrap
```

`--n-boot` must be in `[50,20000]`; use 400 to verify correctness and 1000–2000 for more stable final CI endpoints. `--confidence` accepts values strictly between 0 and 1. A bootstrap with an invalid constant-input replicate *does not silently assign zero*: it is discarded, with the count recorded. If too many fail, CI is not reported.

## Outputs

Given `--output reports/olist_bootstrap`:

- `reports/olist_bootstrap_forest.png`
- `reports/olist_bootstrap_forest.svg`
- `reports/olist_bootstrap_forest.pdf`
- `reports/olist_bootstrap_results.csv`
- `reports/olist_bootstrap_metadata.json`

The CSV includes each pair's Single/Multi N, coefficients, observed Δrho, CI bounds, replicate counts, and status. JSON includes method, confidence, seed, limitations, population counts and source filenames. The forest plot draws only finite valid intervals.

## Validations

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The v7.3 patch **does not replace** v7.2 `segmented_analysis.py`, v7.1 `relationship_matrix.py`, CLI, or any packaging files. It imports from these modules, which must already be installed in editable mode. SciPy is required for fast tie-aware re-ranking; v7.1 users have typically installed SciPy already.

The Olist analysis output must be computed on the user's original CSVs; this patch does not bundle large Olist source data.
