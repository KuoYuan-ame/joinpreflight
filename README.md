# JoinPreflight

**Inspect pandas JOIN cardinality before materializing the joined table.**

JoinPreflight is a lightweight Python CLI and library for checking key uniqueness, predicting JOIN output row counts, identifying possible duplication of left-table metrics, and producing an offline HTML diagnostic report.

> **Status:** Early-stage v0.1.0 candidate. Designed for single-column `LEFT JOIN` analysis on CSV files. The release has not yet been published to PyPI.

## Why this project?

A join can be structurally valid and still make downstream metrics misleading. For example, joining an order-level table to an order-item-level table duplicates the order's amount across item rows. Summing that amount after the join overstates revenue.

JoinPreflight makes these risks visible before you materialize a potentially large joined table.

## Features

- **Primary-key audit:** count missing keys and extra duplicate non-null keys (`audit_primary_key`).
- **Cardinality analysis:** determine observed `1:1`, `1:N`, `N:1`, or `N:N` relationships and check expected constraints.
- **Row-count prediction:** estimate `INNER`, `LEFT`, `RIGHT`, and `OUTER` join sizes from key-frequency tables without creating the full join result (Python API).
- **Left-side metric duplication warning:** identify when joined rows repeat records from the left table.
- **Top expansion keys:** rank keys contributing the most additional rows to a `LEFT JOIN`.
- **Offline HTML and JSON reports:** generate a readable report and a machine-readable summary.
- **CLI:** analyze CSV files using a single command.
- **Automated tests:** tests for invalid input, missing keys, null-key matching, many-to-many joins, and report generation.

## Installation (from source)

Python **3.10+** is required. The project uses pandas; no database server is needed.

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/joinpreflight.git
cd joinpreflight
python -m venv .venv
```

Activate the virtual environment on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Or on macOS/Linux:

```bash
source .venv/bin/activate
python -m pip install -e .
```

Until an actual PyPI release is published, **do not assume `pip install joinpreflight` is available**.

## Quick start

Suppose `orders.csv` contains one row per order and `order_items.csv` contains one row per item. Both share the `order_id` column.

```bash
joinpreflight join \
  --left orders.csv \
  --right order_items.csv \
  --on order_id \
  --expected '1:N' \
  --top 10 \
  --html reports/join_report.html \
  --json reports/join_report.json
```

On Windows PowerShell, run this on one line, or use PowerShell's backtick for line continuation. Without activation, use `.\.venv\Scripts\joinpreflight.exe`.

The CLI reports:

- Actual versus expected key cardinality.
- Original input sizes, predicted joined rows, and left-side row growth.
- Unmatched key counts and potential duplication of left-side metrics.
- Keys with the largest contribution to `LEFT JOIN` expansion.
- Optional HTML and JSON output paths.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Analysis completed; no declared relationship constraint was violated. |
| `1` | Declared relationship constraint was violated. |
| `2` | Input or execution error. |

**A `0` exit code does not guarantee metric safety.** A valid one-to-many join can still duplicate order-level measures.

## Python API

```python
import pandas as pd
from joinpreflight.audit import audit_primary_key
from joinpreflight.joins import analyze_join, rank_risky_keys
from joinpreflight.report import generate_html_report

orders = pd.DataFrame({
    "order_id": ["A001", "A002", "A003"],
    "order_amount": [100, 200, 300],
})
items = pd.DataFrame({
    "order_id": ["A001", "A001", "A002"],
    "item": ["X", "Y", "Z"],
})

key_report = audit_primary_key(orders, "order_id", "orders")
join_report = analyze_join(orders, items, "order_id", how="left", expected="1:N")
top_keys = rank_risky_keys(orders, items, "order_id", top_n=10)
generate_html_report(join_report, top_keys, "reports/demo.html")

print(key_report)
print(join_report["predicted_rows"])  # 4
```

## Real-data validation: Olist e-commerce

The current prototype has been checked against the public Olist e-commerce dataset, joining orders to order items on `order_id` using `LEFT JOIN`.

| Metric | Observed result |
| --- | ---: |
| Order rows | 99,441 |
| Order-item rows | 112,650 |
| Matched order-key groups | 98,666 |
| Unmatched left rows | 775 |
| Predicted LEFT JOIN rows | 113,425 |
| Actual pandas LEFT JOIN rows | 113,425 |
| Extra rows versus orders | 13,984 (14.06%) |
| Extra rows attributable to the top 10 expansion keys | 146 (1.04% of extra rows) |

This validates **row-count prediction on this dataset**, not correctness for every dtype, key distribution, or downstream financial metric. Olist data is not bundled with this repository.

## Important semantics and limitations

1. The **CLI currently supports only a single join key and `LEFT JOIN`**, even though `analyze_join()` can predict additional join types in the Python API.
2. Join-key columns are loaded from CSV **as strings** to preserve identifiers such as `001`. With pandas' default CSV settings, common missing-value markers are interpreted as missing.
3. **Null keys may match other null keys**, consistent with `pandas.merge`. This differs from ordinary SQL `NULL = NULL` behavior.
4. An expected relationship such as `1:N` is a **uniqueness constraint** on the left side. An observed `1:1` relationship also satisfies that constraint. `N:N` places no uniqueness constraint on either side.
5. Row expansion is **not necessarily a join error**. The correct aggregation strategy depends on the grain of each measure.
6. This implementation counts key frequencies before joining; it still needs memory proportional to the number of distinct keys.
7. Mixed or incompatible non-null key dtypes may cause pandas merge errors. Compound join keys, database connections, and automatic metric corrections are not yet supported.
8. The HTML report currently summarizes `LEFT JOIN` analysis only.

## Development and testing

```bash
python -m pip install -e ".[dev]"
python -m pytest -v
joinpreflight --help
```

A CI workflow runs tests across multiple Python versions. Before publishing, ensure CI and the source-distribution/wheel build both pass.

## Roadmap

- Validate non-null join key dtype compatibility and edge cases.
- Support compound keys and explicit null-matching policies.
- Add more informative warnings for business-metric grain mismatches.
- Improve benchmark coverage and extend the CLI beyond `LEFT JOIN`.
- Add screenshots, tutorials, and more representative reproducible examples.

## Contributing

Issues, reproducible bug reports, tests, documentation improvements, and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
