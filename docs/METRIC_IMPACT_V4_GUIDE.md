# JoinPreflight v4 — Metric Inflation Impact

## Purpose

Quantify a *specific hypothetical misuse*: summing an **order-level payment amount** after an order-to-item LEFT JOIN without re-aggregating or de-duplicating by order.

The previous four-panel JOIN diagnostic stays unchanged. v4 adds **one** monetary impact comparison figure, a standalone offline HTML report, and a new CLI `impact` subcommand.

## What's included

- `src/joinpreflight/metric_impact.py` — amount analysis using integer cents internally
- `src/joinpreflight/impact_visualization.py` — single payment comparison chart, PNG + vector PDF
- `src/joinpreflight/impact_report.py` — independent offline HTML with embedded figure and Top N *monetary* impact orders
- `src/joinpreflight/cli.py` — full v3 CLI with added v4 `impact` subcommand
- `examples/07_impact_demo.py` — independent synthetic proof-of-concept
- `tests/test_metric_impact.py` / `tests/test_cli_impact.py` — 16 additional tests

The core `joins.py`, previous `visualization.py`, and earlier test files are not overwritten.

## Windows PowerShell installation

From the local project root, back up your code with Git if needed. Extract the v4 zip with the project root as destination (rather than into `src`):

```powershell
Expand-Archive -LiteralPath "C:\Users\13927\OneDrive\文档\Downloads\JoinPreflight_Metric_Impact_v4.zip" -DestinationPath "." -Force
```

Check existing imports before installing anything else:

```powershell
.\.venv\Scripts\python.exe -c "import joinpreflight; import pandas, matplotlib; print(joinpreflight.__file__)"
```

If matplotlib is missing, install it using a working PyPI mirror. You do **not** need to reinstall `joinpreflight` simply because its Python modules changed when it is already installed in editable mode. If the CLI script has not been installed at all, reinstall the editable package according to its `pyproject.toml`.

## Try a small example first

```powershell
.\.venv\Scripts\python.exe .\examples\07_impact_demo.py
Start-Process .\reports\demo_impact.html
```

The example is **synthetic**, not Olist results.

## Run real Olist data

```powershell
$root = "C:\Users\13927\PycharmProjects\olist-ecommerce-analysis\data"
$orders = Join-Path $root "olist_orders_dataset.csv"
$items = Join-Path $root "olist_order_items_dataset.csv"
$payments = Join-Path $root "olist_order_payments_dataset.csv"

.\.venv\Scripts\joinpreflight.exe impact `
  --orders $orders `
  --items $items `
  --payments $payments `
  --on order_id `
  --value payment_value `
  --currency BRL `
  --top 10 `
  --figure reports\olist_payment_impact `
  --html reports\olist_payment_impact.html `
  --json reports\olist_payment_impact.json

Start-Process .\reports\olist_payment_impact.html
```

Outputs:

- `reports/olist_payment_impact.png`
- `reports/olist_payment_impact.pdf`
- `reports/olist_payment_impact.html`
- `reports/olist_payment_impact.json`

Note: PowerShell backtick (\`) is a line-continuation character and must be the **last** character on its line. You can also write the command on one line.

## Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

When the previous v3 suite has 35 tests, the 16 additional v4 tests make **51 tests** in total.

## Exact definition

For a unique order master key `i`, `p_i` is the sum of all payment records for that order. `n_i` is the number of order item records. With LEFT JOIN repetition factor `m_i = max(n_i, 1)`:

- Correct payment SUM: `S_correct = sum(p_i)`
- Incorrect after-JOIN SUM: `S_naive = sum(m_i * p_i)`
- Duplicated amount: `Delta = sum((m_i - 1) * p_i)`
- Relative overcount: `Delta / S_correct` when `S_correct > 0`, otherwise undefined (JSON `null`)

The numeric input must be **finite, nonnegative and have no more than two fractional decimal places**; this is a **payment-specific**, not a generic signed/continuous metric feature. Amounts are parsed to integer cents before summation to avoid binary-floating point accumulation error.

**Important restrictions**

1. `orders` must be unique and have non-null order IDs. Any null order IDs in items or payments are rejected.
2. Payment rows are aggregated by order first. Split payments therefore count only once per order-level payment total.
3. Missing payment records are *excluded from the SUM* and counted separately; their absence is not proof of zero payment.
4. Payment and item records whose order IDs are not in `orders` are excluded and counted.
5. The analyzer simulates a mistaken post-JOIN SUM. It does not detect actual revenue fraud, accounting-recognized revenue, or true payment errors.
6. The reported numeric monetary label (default `BRL`) is provided by the caller; the tool cannot independently certify dataset currency.
7. This first release supports a single-column pandas-style **LEFT JOIN** with an order-grain left table and a nonnegative two-decimal payment metric.

## Interview description

> I built a JOIN preflight diagnostic tool that goes beyond row-expansion detection. It computes how much a naive order-level payment SUM could be overcounted after a one-to-many order-item join, without materializing the full join. It aggregates split payments at the order grain, uses cent-based calculations, pinpoints the highest monetary-impact orders, and exports an offline diagnostic report with a reproducible chart and JSON results.
