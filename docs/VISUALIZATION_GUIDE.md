# JoinPreflight Figure Board v1

## Four plots, four analytical questions

| Panel | Question | Chart | Data required |
|---|---|---|---|
| a | What is joined? | Relation schematic | Report summary |
| b | How much does the row count change? | Before/after bars with growth segment | Report summary |
| c | Which keys contribute the most? | Sorted horizontal bars | Top 10 expanding keys |
| d | Is expansion concentrated or distributed? | Cumulative contribution / Pareto curve | **All** expanding keys |

**Interpretation:** Row expansion is not a data-quality violation by itself. A legitimate 1:N join duplicates left-table rows in the output, and aggregation at the wrong grain may then overstate an order-level metric.

## Integration

1. Copy `src/joinpreflight/visualization.py` to your project.
2. Copy `examples/06_figure_board.py` and `tests/test_visualization.py` to the corresponding directories.
3. Add `matplotlib>=3.8` to the existing `dev` extra in `pyproject.toml` (so GitHub CI installs it), and optionally add `viz = ["matplotlib>=3.8"]` as a separate extra for users. Then run `python -m pip install -e ".[dev]"`.
4. Run `python -m pytest -q`.
5. Run:

```powershell
$orders = 'C:\Users\13927\PycharmProjects\olist-ecommerce-analysis\data\olist_orders_dataset.csv'
$items = 'C:\Users\13927\PycharmProjects\olist-ecommerce-analysis\data\olist_order_items_dataset.csv'
.\.venv\Scripts\python.exe .\examples\06_figure_board.py $orders $items
Start-Process .\reports\joinpreflight_figure.html
```

Outputs: an offline HTML report with an embedded figure, a high-resolution PNG for GitHub README, and a vector PDF for documents.

## Why not include six plots?

We deliberately omit a pie chart of Top 10 vs rest (redundant with panel d) and a separate matched/unmatched row pie (the numeric report already contains exact counts). Prefer adding a chart only when it answers a *new* question.

## Practical limitations

- The publication figure is for the currently supported single-key LEFT JOIN workflow.
- The cumulative curve requires the entire expanding-key distribution. Passing only the Top 10 silently biases the plot; the code rejects it.
- For very large cardinality, retaining and sorting all expanding keys can take significant memory. Consider streaming or aggregated rank bins in a future version.
- IDs are abbreviated in the image to keep labels readable; the existing HTML table retains the full key values.
- The PNG is embedded into the visual HTML as base64 so the page works offline. PDF remains independently downloadable/printable.
- The plot labels are English, to avoid missing Chinese glyphs on CI systems; the existing summary report still uses Chinese.
