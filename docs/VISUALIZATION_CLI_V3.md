# JoinPreflight Visualization CLI v3

This patch integrates the **existing v2** figure board into the supported
`joinpreflight join` command. It is *not* a replacement for the v2 visualization
module. Keep `src/joinpreflight/visualization.py` from v2.

## Installation

Add matplotlib to your existing `pyproject.toml` under the **existing** optional
-dependencies section, merging rather than duplicating the section:

```toml
[project.optional-dependencies]
dev = ["pytest>=8,<10", "build>=1", "twine>=6", "matplotlib>=3.8"]
viz = ["matplotlib>=3.8"]
```

Then run on Windows PowerShell from the project root:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]" -i https://pypi.tuna.tsinghua.edu.cn/simple
.\.venv\Scripts\joinpreflight.exe join --help
.\.venv\Scripts\python.exe -m pytest -v
```

If you **only** need visualization and not developer dependencies, install
`-e ".[viz]"` instead.

## CLI usage

```powershell
$orders = "C:\Users\13927\PycharmProjects\olist-ecommerce-analysis\data\olist_orders_dataset.csv"
$items = "C:\Users\13927\PycharmProjects\olist-ecommerce-analysis\data\olist_order_items_dataset.csv"

.\.venv\Scripts\joinpreflight.exe join --left $orders --right $items --on order_id --expected "1:N" --top 10 --figure reports\olist_figure --html reports\olist_v3.html --json reports\olist_summary.json
```

`--figure` accepts a **prefix without a file extension**, and produces both
`reports/olist_figure.png` and `reports/olist_figure.pdf`.

`--html` alone produces the regular HTML report. When `--html` and `--figure`
are both provided, the four-panel figure is embedded in the same standalone
HTML report before the Top N key table. `--json` retains the previous JSON schema.

When visualization is enabled, the CLI uses **ALL expansion keys** for the
cumulative contribution curve, independently of `--top`. The latter controls
the console/HTML table and the plotted Top N bars only.

## Compatibility and scope

- Only single-key pandas-style LEFT JOIN is exposed by this CLI.
- The code loads identifier columns as strings; pandas null-key behavior applies.
- `--figure` is optional: the regular analysis CLI works without matplotlib.
- Outputs are in `reports/` by default only when those paths are requested.
- CLI exit statuses are unchanged: 0 success, 1 relationship violation, 2 error.
- v2 visualization is required before applying this patch.
- Use `python -m pytest -v` to validate. With 25 original + 5 v2 + 5 new tests,
  the **expected** total is 35, assuming all prior tests are present.
- Do not commit the original large Olist data files or the local virtualenv.

## Suggested README paragraph

Add a `Visual diagnostics` section with this PowerShell example. Include an
image reference to a curated screenshot, e.g. `docs/images/olist_figure.png`,
not to `reports/` (which should remain gitignored).

```markdown
## Visual diagnostics

Use `--figure reports/olist_figure` together with `--html` and `--json` to
produce publication-style PNG/PDF charts and a self-contained HTML report.
The cumulative profile uses **all expanding keys**, even when `--top 10`
restricts the key ranking table.

![Olist LEFT JOIN diagnostics](docs/images/olist_figure.png)
```
