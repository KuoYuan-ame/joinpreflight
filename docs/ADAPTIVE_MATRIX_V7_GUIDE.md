# JoinPreflight — Adaptive Order-Grain Relationship Matrix

## Design

This optional exploratory figure is **not** automatically added to the unified report.

1. Aggregate all source measurements to the **order** grain (`order_id`).
2. Consider domain-relevant candidate features, not numeric identifiers.
3. Apply a quality threshold: >=75% nonmissing, >=6 distinct values, most common value <=95% of observations.
4. Prune near-duplicates via Spearman absolute correlation >=0.93, keeping the better-prioritized feature.
5. Cap the view at 7 candidates by default. Resulting `n` is selected by the data, not hard-coded.
6. Diagonal: histogram; lower triangle: sampled scatter; upper triangle: full-data pairwise Spearman.
7. Export PNG, SVG, feature-selection audit CSV, and JSON metadata.

### Candidate priority and caveats

The candidate order is item rows, payment total, average item price, total freight,
delivery duration, delivery delay, maximum installments, number of payments, number
of payment types, within-order item price standard deviation.

Derived inflation is **not** treated as an independent predictor because:
`overcount = payment_total * max(item_count-1, 0)` by construction.

This figure is exploratory. Correlation does not demonstrate causation; observed
associations may be affected by selection, conditioning, nonlinearity, or common factors.
Order-item rows count **line items**, not necessarily physical units. `payment_total`
is recorded payments, not accounting revenue.

### Missingness and sampling

A blank payment amount is left **missing**, not converted into a zero amount. Missing
item/payment counts are legitimately zero. Diagonal histograms and lower-triangle
scatter use complete-case rows only so they represent the same population. If there
are more than `--max-points` complete orders, the display uses a reproducible uniform
random subset; this may underrepresent rare extreme orders. Upper-triangle Spearman
uses all pairwise nonmissing data (not sampled), potentially a slightly different
population; the figure subtitle discloses this distinction.

### Running with the complete Olist dataset

PowerShell:

```powershell
$root = "C:\Users\13927\PycharmProjects\olist-ecommerce-analysis\data"
$orders = Join-Path $root "olist_orders_dataset.csv"
$items = Join-Path $root "olist_order_items_dataset.csv"
$payments = Join-Path $root "olist_order_payments_dataset.csv"

.\.venv\Scripts\python.exe .\examples\09_adaptive_pair_matrix.py $orders $items $payments --max-features 7
Start-Process .\reports\order_relationship_matrix.png
```

The six-order public demo is too small and too sparse to select meaningful variables.
Use real Olist or a sufficiently large synthetic dataset to learn from this figure.

### Selection audit

`reports/order_relationship_matrix_candidate_audit.csv` contains one row per candidate
with completeness, number of distinct values, mode share, selected, and reason.
Inspect this file **before** interpreting the correlation matrix.

### Future improvements

- Stratify scatter samples so rare high-impact orders are visible.
- Offer outcome-informed screening without treating an algebraic outcome as an independent cause.
- Make the feature registry configurable while preserving a documented data dictionary.
- Separate payment, logistics, and JOIN-cardinality matrices when more than seven useful variables survive.

### Demo without downloading Olist

```powershell
.\.venv\Scripts\python.exe .\examples\10_synthetic_matrix_demo.py
Start-Process .\reports\synthetic_order_relationship_matrix.png
```

This demo generates synthetic order, item and payment tables in a temporary folder.
Do not describe its relationships as evidence about actual Olist transactions.
