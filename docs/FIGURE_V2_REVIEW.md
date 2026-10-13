# Figure Board v2: focused visual revision

Changes compared with v1:

1. Panel (d) now uses the **percentage of expanding keys**, in ranked order, on a **linear 0–100% x-axis**. The equal-contribution diagonal helps distinguish broadly distributed expansion from concentration. The former log-scale plot was mathematically valid but visually counterintuitive.
2. The HTML report inserts the figure **before** the Top-N detail table and footer, instead of appending it after the footer.
3. Panel (b) labels clarify the two populations: **Left table** and **LEFT JOIN output**.
4. No core join analysis, JSON schema, or CLI contracts were changed.

Run the existing `examples/06_figure_board.py` script with the same two CSV arguments, and run `pytest -v`. Existing 25 unit tests plus five visualization tests aim for 30 passed.

**Analysis note:** Positive row growth in an expected 1:N join is not itself an invalid join or a confirmed revenue error. It indicates possible double-counting when order-grain metrics are aggregated after joining to item-grain data.
