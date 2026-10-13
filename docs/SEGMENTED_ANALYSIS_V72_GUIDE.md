# JoinPreflight v7.2 — Segmented Relationship Analysis

## Why this module?

The v7.1 adaptive n×n matrix shows associations among **all orders**. v7.2 asks whether those associations change when we compare **one-item-row** and **multiple-item-row** orders. It also validates the Spearman computation that was previously misread in a plot.

**Important correction.** In the user's v7.1 Business matrix, `freight_total` vs `delivery_days` is approximately **+0.38**; the **+0.14** cell represents `payment_total` vs `delivery_days`. The discrepancy was in the prior *verbal interpretation*, not established evidence of a changed computation. This patch provides an independent all-orders check using rank-Pearson and pandas Spearman on the same pairwise-valid rows; it does not hardcode any expected Olist rho value.

## Scope and design

- Additive `segmented_analysis.py`: reuses `build_order_features` to preserve **one row per order**, preventing item/payment Cartesian products.
- One item row = **Single**; two or more item rows = **Multi**; zero item rows = **No items**, retained in population counts but not treated as Single.
- Uses *all available pairwise rows within each group*, not a scatter subsample.
- Reports effective sample size **N** for every group and variable pair.
- Safeguards: for `n < min_pairs` or constant inputs, rho is undefined (`NaN` in CSV), with explicit status. Uses Pearson correlation of **average ranks** (Spearman definition) to avoid `ConstantInputWarning`.
- `Δρ = ρ_multi - ρ_single` is a **descriptive difference**, not a significance test or causal estimate. Different group distributions and confounding can explain differences. Do not infer that item multiplicity causes the relationship to change.
- Default variables: `payment_total`, `avg_item_price`, `freight_total`, `delivery_days`, `max_installments`. The `item_count` feature is omitted by default because it is **identically 1** in the Single group, making every within-group correlation involving it undefined. This is intentional.
- Original Olist variables: `item_count` counts **item rows**, not necessarily physical product units. Payments are recorded totals, not accounting-recognized revenue.
- Financial boxplots use **display-only** log(1+x), or `asinh` if signed data are present. Group medians, quartiles, and Spearman correlations always use the original numeric values. Whiskers are 1.5 IQR; outliers are hidden in the plot but **not removed from analysis**.
- `relationship_matrix.py` includes a targeted guard for pairwise constant inputs in v7.1, avoiding the previously observed warning. Existing API and selection criteria remain unchanged.

## Installation on your existing Windows project

In PowerShell:

```powershell
cd C:\Users\13927\PycharmProjects\granguard

# Review your local changes before unpacking:
git status

Expand-Archive -LiteralPath "C:\Users\13927\OneDrive\文档\Downloads\JoinPreflight_v7_2_SEGMENTED_PATCH.zip" -DestinationPath "." -Force

.\.venv\Scripts\python.exe -m pytest -q
```

**Patch files:** `src/joinpreflight/segmented_analysis.py` (new), `src/joinpreflight/relationship_matrix.py` (v7.1 bugfix), `examples/11_segmented_order_analysis.py`, `examples/12_synthetic_segmented_demo.py`, `tests/test_segmented_analysis.py`, `docs/SEGMENTED_ANALYSIS_V72_GUIDE.md`. The patch does **not** replace your CLI, the JOIN analyzer, unified HTML report, payment impact engine, or README.

## Fast demo, no Olist downloads

```powershell
.\.venv\Scripts\python.exe .\examples\12_synthetic_segmented_demo.py
Start-Process .\reports\demo_segmented_overview.png
Start-Process .\reports\demo_segmented_correlations.png
```

The demo uses 210 **synthetic** orders. Its numeric correlations do not describe Olist.

## Real Olist analysis

```powershell
$root = "C:\Users\13927\PycharmProjects\olist-ecommerce-analysis\data"
$orders   = Join-Path $root "olist_orders_dataset.csv"
$items    = Join-Path $root "olist_order_items_dataset.csv"
$payments = Join-Path $root "olist_order_payments_dataset.csv"

.\.venv\Scripts\python.exe .\examples\11_segmented_order_analysis.py `
  $orders $items $payments --output reports\olist_segmented --min-pairs 30

Start-Process .\reports\olist_segmented_overview.png
Start-Process .\reports\olist_segmented_correlations.png

Import-Csv .\reports\olist_segmented_rho_differences.csv | Format-Table -AutoSize
```

### Files created

1. `olist_segmented_overview.png` and `.svg` — (a) group sizes, (b) payment distribution, (c) freight distribution, (d) five business-relevant rho comparisons.
2. `olist_segmented_correlations.png` and `.svg` — two matching correlation matrices and their **Multi − Single** difference matrix.
3. `olist_segmented_group_summary.csv` — counts, coverage and quartiles for every segment and feature.
4. `olist_segmented_pair_correlations.csv` — group/pair/rho/N/status for every pair.
5. `olist_segmented_rho_differences.csv` — both groups' rho/N, explicit `not_comparable` or descriptive delta.
6. `olist_segmented_metadata.json` — source filenames (not full private paths), population, variables, computation method, caveats, and all-order consistency result.

## How to interpret the data

- Compare the *magnitude* of rho across groups with their pairwise effective sample counts. Large differences can reflect small effective N, nonlinearities, different subgroup distributions, and confounding. This stage does not calculate p-values or confidence intervals.
- `ρ(payment_total, avg_item_price)` is partly structurally related to the underlying price and total, especially for Single; avoid treating it as a discovery of causality.
- `freight_total` vs `delivery_days` should be compared within Single and Multi; the overall rho does not tell you the subgroup values.
- Financial totals without a payment record are missing, **not automatically zero**.

## Tests and reproducibility

The incremental set adds **11 tests**. In an isolated environment containing the v7 and v7.1 matrix tests, **23 tests passed without warnings**. Your last complete local suite had **71 passed**; if all those tests are still present, expect **82 collected and passing** after this patch. Verify on Windows before GitHub release.

## Git safety

Keep the ZIP outside the repo, or verify it is ignored. Run `git status` and inspect staged files before committing. Never use `git reset --hard` or overwrite uncommitted local changes without review. Save a checkpoint commit after tests pass.
