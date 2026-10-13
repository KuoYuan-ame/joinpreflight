# JoinPreflight v5 — Unified Diagnostic Report

## Goal

Generate **one offline HTML report** combining:

1. An executive summary with four key business/structural metrics.
2. The existing four-panel JOIN cardinality / row expansion visualization.
3. The existing payment inflation comparison chart.
4. Top-N tables ranked separately by **additional JOIN rows** and by **modeled monetary overcount**.
5. Recommendations, assumptions, input-quality flags, and a reproducible JSON artifact.

The algorithm modules (`joins.py`, `metric_impact.py`) remain unchanged.

## Install on Windows (PowerShell, project root)

Make sure the original v4 project works first (`51 passed`). Extract the v5 zip **into the project root**, overwriting the existing `cli.py` and `impact_visualization.py` and adding `unified_report.py` and the new test.

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]" --no-build-isolation -i https://mirrors.aliyun.com/pypi/simple/
.\.venv\Scripts\joinpreflight.exe report --help
```

The install command is only needed if the current environment is missing a dependency or the executable entry point. The v5 patch does not introduce a new third-party dependency beyond v4's `pandas` and optional `matplotlib`.

## Quick demo (no Olist dataset needed)

```powershell
.\.venv\Scripts\python.exe .\examples\08_unified_report_demo.py
Start-Process .\reports\demo_unified.html
```

The demo generates small synthetic input CSVs in the ignored `reports/demo_data/` directory. It is not an Olist result.

## Real Olist example

```powershell
$root = "C:\Users\13927\PycharmProjects\olist-ecommerce-analysis\data"
$orders = Join-Path $root "olist_orders_dataset.csv"
$items = Join-Path $root "olist_order_items_dataset.csv"
$payments = Join-Path $root "olist_order_payments_dataset.csv"

.\.venv\Scripts\joinpreflight.exe report `
  --orders $orders `
  --items $items `
  --payments $payments `
  --on order_id `
  --value payment_value `
  --expected "1:N" `
  --currency BRL `
  --top 10 `
  --output reports\olist_unified.html

Start-Process .\reports\olist_unified.html
.\.venv\Scripts\python.exe -m pytest -q
```

### Generated outputs

```text
reports/
├── olist_unified.html                   # Self-contained, two figures embedded
├── olist_unified.json                   # Both result summaries + Top N rankings
└── figures/
    ├── olist_unified_join.png          # Four-panel figure
    ├── olist_unified_join.pdf          # Publication-quality vector PDF
    ├── olist_unified_payment.png       # Monetary comparison figure
    └── olist_unified_payment.pdf       # Publication-quality vector PDF
```

Optional flags: `--json PATH` to write JSON elsewhere; `--figure-dir PATH` to change the figure directory. Do **not** add a file suffix to the figure directory.

## Expected verified Olist results

Based on the Olist results already calculated in v3 and v4:

- Orders: 99,441 rows
- Order items: 112,650 rows
- Predicted left-joined rows: 113,425 rows
- Added left-side rows: 13,984 (+14.06%)
- Correct payment total: 16,008,872.12 BRL
- Naive post-JOIN payment total: 20,470,726.66 BRL
- Modeled overcount: 4,461,854.54 BRL (+27.87%)
- Top-10 impact orders: 333,843.94 BRL, or 7.48% of modeled overcount

These describe the **modeled consequences of an incorrect JOIN-then-SUM pipeline**; they do not imply source-record mistakes or accounting revenue overstatement.

## Reporting methodology

Let `p_i` be the total recorded payment for master order `i`, aggregated from payment records; and `n_i` the item-row count for that order.

- **Correct order-grain payment amount:** `sum(p_i)`
- **Naive JOIN-then-SUM amount:** `sum(p_i * max(n_i, 1))`
- **Extra rows:** `sum(max(n_i - 1, 0))`
- **Modeled payment overcount:** `sum(p_i * max(n_i - 1, 0))`

Impact calculations require unique non-null master order keys and non-null detail keys, and accept nonnegative monetary inputs with at most two decimal places. Internally they aggregate cents as Python integers. Missing payment records are counted and disclosed, not presented as proof of zero paid.

The v5 CLI checks the source-table row counts, join key and additional-row totals **match between the structural and business-analysis engines** before combining them into a report.

**Important:** The cumulative concentration plot is created from **every expanding join key**; the Top-N tables only display the selected number of rows.

## Testing and return codes

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Target with v4's 51 tests + v5's 8 tests: **59 passed** (independently verified in a test environment). Do not regard this as a replacement for Windows testing.

CLI codes: `0` = success, `1` = expected relationship violated (report still written if payment analysis valid), `2` = input/analysis/output error.

## Publication note

Before publishing to GitHub, remove personal directories, private datasets, screenshots showing personal details, and generated `reports/` artifacts from the Git commit. Keep representative screenshots under a deliberate tracked `docs/assets/` directory and provide a data-source link in README.
