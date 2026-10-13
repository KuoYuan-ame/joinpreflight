"""Tiny reproducible example, using only synthetic orders (not Olist data)."""
from pathlib import Path

import pandas as pd

from joinpreflight.metric_impact import analyze_metric_inflation
from joinpreflight.impact_visualization import render_impact_figure
from joinpreflight.impact_report import generate_impact_html


if __name__ == "__main__":
    orders = pd.DataFrame({"order_id": ["A", "B", "C"]})
    items = pd.DataFrame({"order_id": ["A", "A", "A", "B", "B"]})
    payments = pd.DataFrame({
        "order_id": ["A", "A", "B", "C"],
        "payment_value": ["100.01", "0.02", "200.00", "50.00"],
    })
    summary, top = analyze_metric_inflation(orders, items, payments)
    prefix = Path("reports/demo_impact")
    paths = render_impact_figure(summary, prefix)
    html = generate_impact_html(summary, top, "reports/demo_impact.html",
                                figure_png=paths["png"])
    print("SYNTHETIC EXAMPLE - NOT OLIST RESULTS")
    print(summary)
    print(f"HTML report: {html}")
