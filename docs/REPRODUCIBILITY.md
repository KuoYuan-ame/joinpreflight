# Reproducibility

JoinPreflight provides two reproducibility paths: a small public synthetic demonstration and analyses based on the publicly available Olist e-commerce dataset.

## Public Synthetic Demo

Install the project in a Python virtual environment, then run:

```bash
python tools/smoke_demo.py
```

The demonstration verifies JOIN cardinality, payment aggregation impact, and report generation without requiring the Olist dataset.

The included example expands six order rows to nine joined rows. A deliberately incorrect post-JOIN aggregation increases the payment sum from BRL 215.00 to BRL 385.00.

## Real Olist Analysis

Download the Olist e-commerce datasets separately. The raw source data is not included in this repository.

The segmented Bootstrap analysis uses:

- `olist_orders_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_order_payments_dataset.csv`

Run `examples/13_bootstrap_segmented.py` with the three CSV paths and the parameters `--n-boot 400 --seed 42`.

The published analysis compares Single and Multi item-row orders using Spearman rank correlations and within-group percentile Bootstrap confidence intervals.

The default reported intervals are nominal 95% intervals. They are exploratory, do not adjust for multiple comparisons, and rely on approximate independence between orders.

## Tests

Run:

```bash
python -m pytest -q
```

Reproducibility may depend on Python and dependency versions, input data, and the random seed. Record the environment and parameter settings when publishing new results.