"""Standalone offline HTML for payment metric inflation diagnostics."""
from __future__ import annotations

import base64
from html import escape
from pathlib import Path
from string import Template

import pandas as pd


def generate_impact_html(
    summary: dict,
    top_orders: pd.DataFrame,
    output_path: str | Path,
    currency: str = "BRL",
    figure_png: str | Path | None = None,
) -> Path:
    def safe(x: object) -> str:
        return escape(str(x), quote=True)

    def amount(x: object) -> str:
        return f"{float(x):,.2f} {safe(currency)}"

    rate = summary["inflation_rate_pct"]
    rate_label = "N/A (zero baseline)" if rate is None else f"+{rate:,.2f}%"
    plot = ""
    if figure_png is not None:
        encoded = base64.b64encode(Path(figure_png).read_bytes()).decode("ascii")
        plot = (
            '<section><h2>Payment metric comparison</h2>'
            '<img class="figure" alt="Correct versus naive payment sum" '
            f'src="data:image/png;base64,{encoded}"></section>'
        )

    cells = []
    for _, rec in top_orders.iterrows():
        cells.append(
            "<tr>"
            f"<td><code>{safe(rec[summary['join_key']])}</code></td>"
            f"<td>{int(rec['item_rows']):,}</td>"
            f"<td>{amount(rec['payment_total'])}</td>"
            f"<td>{amount(rec['overcount_amount'])}</td>"
            "</tr>"
        )
    rows = "\n".join(cells) or '<tr><td colspan="4">No positive inflation found.</td></tr>'
    tmpl = Template("""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>JoinPreflight | Payment Impact</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f3f7fa;color:#19334b;font-family:Arial,'Segoe UI',sans-serif;line-height:1.6}
main{max-width:1120px;margin:0 auto;padding:30px 20px 75px}
header{background:#19334b;color:white;padding:27px 30px;border-radius:16px}
header h1{margin:0;font-size:29px}header p{margin:4px 0 0;color:#c9d7e1}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:22px 0}
.metric,section{background:#fff;border:1px solid #e5edf2;border-radius:13px;padding:20px}
.metric .caption{font-size:12px;color:#61788c}.metric .num{font-size:24px;font-weight:bold;overflow-wrap:anywhere}
.metric .alert{color:#c5683f}section{margin-top:15px}h2{font-size:17px;margin:0 0 11px}
.figure{max-width:100%;height:auto;display:block;margin:0 auto}
.explain{background:#fff7ee;border-left:4px solid #df7446;padding:12px 15px}
.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:650px}
th,td{text-align:left;border-bottom:1px solid #e5edf2;padding:9px 12px}
th{font-size:13px;color:#60758a}code{font-size:12px;overflow-wrap:anywhere}
small,footer{color:#667b8d;font-size:13px}
@media(max-width:760px){.grid{grid-template-columns:repeat(2,1fr)}}
</style></head><body><main>
<header><h1>JoinPreflight</h1><p>Metric Inflation Impact · Single-key LEFT JOIN</p></header>
<div class="grid">
<div class="metric"><div class="caption">Correct order-level payment SUM</div><div class="num">$correct</div></div>
<div class="metric"><div class="caption">Naive post-JOIN payment SUM</div><div class="num">$naive</div></div>
<div class="metric"><div class="caption">Overcounted amount</div><div class="num alert">+$extra</div></div>
<div class="metric"><div class="caption">Inflation relative to baseline</div><div class="num alert">$rate</div></div>
</div>
<section><h2>What this means</h2>
<div class="explain">A one-to-many LEFT JOIN can replicate an order's payment amount across item rows.
Summing this order-level metric after JOIN can overstate recorded payments. This is a hypothetical aggregation mistake,
not a claim that the raw dataset's payments or recognized revenue are incorrect.</div>
<p><small>Join key: <code>$key</code> | Items: $items | Payment records: $payrows | Orders without payment records: $missingpay | Orders without items: $missingitems</small></p>
<p><small>Unmatched payment rows excluded: $orphanpay | Unmatched item rows excluded: $orphanitems</small></p></section>
$plot
<section><h2>Top $topn orders by monetary overcount</h2>
<p><small>Top $topn contribute $topshare% of duplicated payment value. Ranked by money, not row count.</small></p>
<div class="table-wrap"><table><thead><tr><th>Order ID</th><th>Item rows</th><th>Order payment</th><th>Potential overcount</th></tr></thead>
<tbody>$rows</tbody></table></div></section>
<footer><p>Method: payment records are grouped by order first; no full orders × items JOIN is materialized.
Null keys and duplicate order master keys are rejected. Amounts use exact integer cents internally.
Missing payment rows are excluded from the SUM, not treated as evidence of zero payment.</p></footer>
</main></body></html>""")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    html = tmpl.substitute(
        correct=amount(summary["correct_payment_total"]),
        naive=amount(summary["naive_payment_total"]),
        extra=amount(summary["inflation_amount"]),
        rate=safe(rate_label),
        key=safe(summary["join_key"]),
        items=f"{summary['item_rows']:,}",
        payrows=f"{summary['payment_records']:,}",
        missingpay=f"{summary['orders_without_payment_records']:,}",
        missingitems=f"{summary['orders_without_items']:,}",
        orphanpay=f"{summary['unmatched_payment_rows_excluded']:,}",
        orphanitems=f"{summary['unmatched_item_rows_excluded']:,}",
        plot=plot,
        topn=int(summary["top_n"]),
        topshare=f"{summary['top_n_inflation_share_pct']:.2f}",
        rows=rows,
    )
    output.write_text(html, encoding="utf-8")
    return output.resolve()
