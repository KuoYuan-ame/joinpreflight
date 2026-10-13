"""Self-contained, publication-style JOIN + payment-inflation HTML report.

Consumes the results of the existing v3 / v4 analysis functions. No business
metric is inferred from row growth alone; HTML is escaped and figures embedded.
"""
from __future__ import annotations

import base64
import re
from html import escape
from pathlib import Path
from string import Template
from typing import Mapping

import pandas as pd


def _h(value: object) -> str:
    return escape(str(value), quote=True)


def _money(value: object, currency: str) -> str:
    return f"{float(value):,.2f} {_h(currency)}"


def _as_image(path: str | Path, alt: str) -> str:
    p = Path(path)
    raw = p.read_bytes()
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"Expected a PNG image: {p}")
    encoded = base64.b64encode(raw).decode("ascii")
    return (f'<img class="figure" loading="lazy" alt="{_h(alt)}" '
            f'src="data:image/png;base64,{encoded}">')


def _table_rows(df: pd.DataFrame, columns: list[str], formats: Mapping[str, str]) -> str:
    if df.empty:
        return f'<tr><td class="empty" colspan="{len(columns)}">None in this dataset</td></tr>'
    out: list[str] = []
    for _, row in df.iterrows():
        cells: list[str] = []
        for col in columns:
            value = row[col]
            fmt = formats.get(col)
            if fmt == "int":
                view = f"{int(value):,}"
            elif fmt == "money":
                view = f"{float(value):,.2f}"
            else:
                view = str(value)
            cls = ' class="key"' if col == columns[0] else ' class="num"'
            cells.append(f'<td{cls}>{_h(view)}</td>')
        out.append("<tr>" + "".join(cells) + "</tr>")
    return "\n".join(out)


def generate_unified_html(
    join_summary: Mapping,
    impact_summary: Mapping,
    expansion_keys: pd.DataFrame,
    impact_orders: pd.DataFrame,
    output_path: str | Path,
    join_png: str | Path,
    impact_png: str | Path,
    *,
    currency: str = "BRL",
) -> Path:
    """Export offline HTML that combines existing v3 and v4 analysis results.

    The caller must supply the same dataset and join key to both engines.
    Numerical cross-checks prevent mismatched JSON/figures from being combined.
    """
    if not re.fullmatch(r"[A-Za-z]{3,8}", currency):
        raise ValueError("currency must contain 3–8 ASCII letters")
    currency = currency.upper()
    if not isinstance(join_summary, Mapping) or not isinstance(impact_summary, Mapping):
        raise TypeError("join_summary and impact_summary must be mappings")
    if not isinstance(expansion_keys, pd.DataFrame) or not isinstance(impact_orders, pd.DataFrame):
        raise TypeError("rankings must be pandas DataFrames")
    if join_summary.get("join_type") != "left":
        raise ValueError("Unified report supports single-key LEFT JOIN only")
    key = join_summary.get("join_key")
    if not isinstance(key, str) or not key or impact_summary.get("join_key") != key:
        raise ValueError("Join and payment analysis must have the same join key")
    if (int(join_summary["left_rows"]) != int(impact_summary["orders_rows"]) or
            int(join_summary["right_rows"]) != int(impact_summary["item_rows"]) or
            int(join_summary["left_join_row_growth"]) != int(impact_summary["extra_join_rows"])):
        raise ValueError("JOIN and payment summaries disagree; verify source tables")
    if abs((float(impact_summary["correct_payment_total"]) +
            float(impact_summary["inflation_amount"])) -
           float(impact_summary["naive_payment_total"])) > 0.011:
        raise ValueError("Payment totals are inconsistent")
    exp_fields = {key, "left_count", "right_count", "extra_left_rows"}
    impact_fields = {key, "item_rows", "payment_total", "overcount_amount"}
    if not exp_fields.issubset(expansion_keys.columns):
        raise ValueError(f"Missing expansion columns: {sorted(exp_fields - set(expansion_keys.columns))}")
    if not impact_fields.issubset(impact_orders.columns):
        raise ValueError(f"Missing impact columns: {sorted(impact_fields - set(impact_orders.columns))}")
    target = Path(output_path)
    if target.suffix.lower() != ".html":
        raise ValueError("output_path must end in .html")

    top_expansion = _table_rows(expansion_keys,
        [key, "left_count", "right_count", "extra_left_rows"],
        {"left_count": "int", "right_count": "int", "extra_left_rows": "int"})
    top_payment = _table_rows(impact_orders,
        [key, "item_rows", "payment_total", "overcount_amount"],
        {"item_rows": "int", "payment_total": "money", "overcount_amount": "money"})
    join_picture = _as_image(join_png, "Four-panel JOIN structure and expansion diagnostics")
    payment_picture = _as_image(impact_png, "Correct payment total versus naive post-JOIN total")

    original = int(join_summary["left_rows"])
    extra = int(join_summary["left_join_row_growth"])
    pct = 100 * extra / original if original else 0.0
    rate = impact_summary["inflation_rate_pct"]
    rate_string = f"+{float(rate):,.2f}%" if rate is not None else "Undefined (zero baseline)"
    rate_text = (f"{float(rate):,.2f}%" if rate is not None else "undefined with zero baseline")
    relationship_ok = join_summary.get("relationship_valid")
    if relationship_ok is True:
        constraint = "Expected relationship satisfied"
        constraint_class = "ok"
    elif relationship_ok is False:
        constraint = "Expected relationship violated"
        constraint_class = "warning"
    else:
        constraint = "No expected relationship constraint"
        constraint_class = "neutral"

    unmatched_pay = int(impact_summary["orders_without_payment_records"])
    unmatched_items = int(impact_summary["orders_without_items"])
    notes = [
        f"The LEFT JOIN expands the order table by {extra:,} rows ({pct:.2f}%).",
        (f"A naive post-JOIN payment SUM would overcount recorded payments by "
         f"{_money(impact_summary['inflation_amount'], currency)} ({rate_text})."),
        (f"The top {len(impact_orders)} orders ranked by monetary impact account for "
         f"{float(impact_summary['top_n_inflation_share_pct']):.2f}% of modeled overcount."),
    ]
    if unmatched_pay:
        notes.append(f"{unmatched_pay:,} orders have no payment records; absence is not proof of a zero payment.")
    if unmatched_items:
        notes.append(f"{unmatched_items:,} orders have no item records; LEFT JOIN retains those orders.")
    notes_html = "".join(f"<li>{_h(s)}</li>" for s in notes)

    template = Template(r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JoinPreflight | Unified Diagnostic Report</title>
<style>
:root { --navy:#1b3853;--muted:#5f7486;--blue:#377c9d;--orange:#d7784a;
        --line:#e2e9ef;--pale:#f3f7fa;--white:#fff; }
* { box-sizing:border-box; }
body { margin:0;background:var(--pale);color:var(--navy);
       font-family:system-ui,-apple-system,"Segoe UI",Arial,sans-serif;line-height:1.55; }
main { max-width:1150px;margin:auto;padding:24px 24px 65px; }
header { padding:34px 36px 30px;border-radius:14px;background:var(--navy);color:white; }
header .eyebrow { color:#c9deeb;font-size:12px;letter-spacing:.1em;text-transform:uppercase; }
h1 { font-size:30px;margin:5px 0 5px;letter-spacing:-.035em; }
header p { margin:0;color:#d6e2ea;max-width:780px; }
.meta { display:flex;gap:10px;flex-wrap:wrap;margin-top:15px; }
.meta span { font-size:12px;border:1px solid #6a8295;padding:4px 9px;border-radius:4px; }
.kpis { display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0; }
.kpi { background:white;border:1px solid var(--line);border-radius:10px;padding:18px; }
.kpi .label { font-size:12px;color:var(--muted); }
.kpi .value { font-size:23px;font-weight:750;white-space:normal;overflow-wrap:anywhere;letter-spacing:-.025em; }
.kpi .value.alert { color:#b9572d; }
.kpi .foot { font-size:12px;color:var(--muted);margin-top:5px; }
section { background:white;border:1px solid var(--line);border-radius:10px;
          padding:24px 26px;margin:16px 0; }
h2 { font-size:19px;margin:0 0 10px;letter-spacing:-.02em; }
h3 { font-size:14px;margin:20px 0 8px; }
p { margin:8px 0; }
.subtitle { font-size:13px;color:var(--muted); }
.section-tag { color:var(--blue);font-size:11px;font-weight:800;letter-spacing:.12em; }
.figure { display:block;width:100%;max-width:100%;height:auto;margin:12px auto 0; }
figcaption { font-size:12px;color:var(--muted);margin-top:12px;text-align:center; }
figure { margin:0; }
.insights { margin:14px 0 0;padding-left:21px; }
.insights li { margin:7px 0; }
.status { display:inline-block;border-radius:5px;padding:3px 7px;font-size:12px;font-weight:700; }
.status.ok { color:#155d49;background:#def3e9; }
.status.warning { color:#9a401e;background:#fff0e6; }
.status.neutral { color:#536d83;background:#eaf1f6; }
.table-wrap { overflow-x:auto; }
table { border-collapse:collapse;width:100%;min-width:650px;font-size:13px; }
summary { color:var(--navy);cursor:pointer;font-size:14px;font-weight:700;padding:8px 0; }
th { font-size:12px;text-align:left;color:var(--muted);border-bottom:2px solid var(--line);padding:10px; }
td { padding:9px 10px;border-bottom:1px solid var(--line); }
td.key { font-family:Consolas,monospace;overflow-wrap:anywhere;max-width:355px; }
td.num { text-align:right;font-variant-numeric:tabular-nums; }
th.num { text-align:right; }
.empty { text-align:center;color:var(--muted); }
.two-col { display:grid;grid-template-columns:1fr 1fr;gap:14px; }
.tip { border-left:3px solid var(--blue);background:#f1f7fa;padding:12px 15px;margin-top:14px; }
.warning-note { border-left:3px solid var(--orange);background:#fff7f1;padding:12px 15px; }
code { font-family:Consolas,"Liberation Mono",monospace; }
pre { overflow-x:auto;background:#18344f;color:#e8f3fb;padding:14px;border-radius:6px;font-size:12px; }
footer { color:var(--muted);text-align:center;font-size:12px;padding-top:14px; }
@media(max-width:850px) { .kpis {grid-template-columns:repeat(2,minmax(0,1fr));}
.two-col {grid-template-columns:1fr;} main {padding:12px;}section {padding:18px;} header {padding:24px;} }
@media(max-width:510px) { .kpis {grid-template-columns:1fr;} h1 {font-size:25px;} }
@media print { body { background:white; } main {max-width:none;padding:0;} section,.kpi {break-inside:avoid;} }
</style>
</head><body><main>
<header>
<div class="eyebrow">Data quality / reproducible diagnostic</div>
<h1>JoinPreflight</h1>
<p>Unified JOIN Cardinality &amp; Payment Metric Impact</p>
<div class="meta"><span>Single-key LEFT JOIN</span><span>Join key: $key</span><span>Currency: $currency</span></div>
</header>
<div class="kpis">
<div class="kpi"><div class="label">Order rows</div><div class="value">$orders</div><div class="foot">Left table · order grain</div></div>
<div class="kpi"><div class="label">Predicted JOIN rows</div><div class="value">$joined</div><div class="foot">+$row_growth rows · +$row_growth_pct%</div></div>
<div class="kpi"><div class="label">Correct payment SUM</div><div class="value">$correct</div><div class="foot">Payments aggregated by order</div></div>
<div class="kpi"><div class="label">Potential payment overcount</div><div class="value alert">+$overcount</div><div class="foot">$rate above correct baseline</div></div>
</div>
<section aria-label="Executive summary">
<span class="section-tag">EXECUTIVE SUMMARY</span><h2>What the join means</h2>
<p>Observed cardinality: <strong>$actual</strong> · <span class="status $constraint_class">$constraint</span></p>
<ul class="insights">$notes</ul>
<div class="warning-note">A valid 1:N join is not itself a data error. Monetary overcount represents a <strong>modeled naive SUM after JOIN</strong>, not incorrect source payments or recognized accounting revenue.</div>
</section>
<section id="structural">
<span class="section-tag">PART A · STRUCTURE</span><h2>Cardinality &amp; row expansion</h2>
<p class="subtitle">Four complementary views: the table relationship, predicted row count, largest expanding keys and full expansion concentration.</p>
<figure>$join_picture
<figcaption>Figure 1. Complete expansion distribution is used in panel (d), rather than only the displayed Top N.</figcaption></figure>
<details><summary>View top $expansion_n keys by additional rows</summary><div class="table-wrap">
<table><thead><tr><th>Join key</th><th class="num">Left count</th><th class="num">Right count</th><th class="num">Extra rows</th></tr></thead>
<tbody>$expansion_rows</tbody></table></div></details>
</section>
<section id="impact">
<span class="section-tag">PART B · BUSINESS IMPACT</span><h2>Payment SUM inflation under a naive aggregation</h2>
<p class="subtitle">Each payment record is first summed to order grain; the hypothetical post-JOIN SUM duplicates the amount once per matched item row.</p>
<figure>$impact_picture
<figcaption>Figure 2. Recorded payments in $currency. Orange indicates the added amount from the modeled naive aggregation.</figcaption></figure>
<details><summary>View top $impact_n orders by potential overcount</summary><div class="table-wrap">
<table><thead><tr><th>Order ID</th><th class="num">Item rows</th><th class="num">Order payment ($currency)</th><th class="num">Overcount ($currency)</th></tr></thead>
<tbody>$impact_rows</tbody></table></div></details>
</section>
<section id="recommendations">
<span class="section-tag">PART C · ACTIONS</span><h2>Recommended aggregation pattern</h2>
<div class="two-col">
<div><h3>Do</h3><p>Aggregate payment records to one row per order before joining to item-level data. Compute order-level sums from the order-grain dataset or after de-duplicating to the validated grain.</p></div>
<div><h3>Avoid</h3><p>Do not apply <code>SUM(payment_value)</code> directly to item-expanded rows. An expected 1:N relationship does not make duplicated monetary aggregates safe.</p></div>
</div>
<div class="tip">Validation checks: $no_pay orders missing payment records; $no_item orders without item records; $unmatched_payment payment rows and $unmatched_item item rows excluded because no master order matched.</div>
<h3>Illustrative SQL pattern</h3>
<pre>WITH payment_by_order AS (
  SELECT order_id, SUM(payment_value) AS order_payment
  FROM order_payments
  GROUP BY order_id
)
SELECT SUM(p.order_payment) AS correct_payment_sum
FROM orders AS o
LEFT JOIN payment_by_order AS p ON o.order_id = p.order_id;</pre>
<p class="subtitle">SQL is illustrative and uses the Olist column naming convention. Production handling of NULL values, status filters and recognized revenue requires an explicit business definition.</p>
</section>
<section id="methodology">
<span class="section-tag">METHODOLOGY</span><h2>Definitions and limitations</h2>
<p><strong>Extra rows:</strong> for each order, <code>max(item_count - 1, 0)</code>; summed over all master orders.</p>
<p><strong>Correct amount:</strong> sum of order-level payment totals for all master orders with recorded payments.</p>
<p><strong>Modeled naive amount:</strong> sum of each order's payment total times <code>max(item_count, 1)</code>.</p>
<p><strong>Inflation rate:</strong> (modeled naive amount − correct amount) / correct amount. Undefined when the correct amount is zero.</p>
<p class="subtitle">Current scope: single-key LEFT JOIN on CSV inputs, nonnegative payment values with at most two decimal places, pandas matching behavior for the structural analyzer; payment impact requires non-null unique master order IDs and non-null detail IDs. This report is descriptive, not a financial audit.</p>
</section>
<footer>Generated locally by JoinPreflight · Self-contained HTML · No external scripts or network assets</footer>
</main></body></html>''')

    result = template.substitute(
        key=_h(key), currency=_h(currency),
        orders=f"{original:,}", joined=f"{int(join_summary['predicted_rows']):,}",
        row_growth=f"{extra:,}", row_growth_pct=f"{pct:.2f}",
        correct=_money(impact_summary["correct_payment_total"], currency),
        overcount=_money(impact_summary["inflation_amount"], currency),
        rate=_h(rate_string), actual=_h(join_summary["actual_relationship"]),
        constraint=_h(constraint), constraint_class=constraint_class,
        notes=notes_html, join_picture=join_picture, impact_picture=payment_picture,
        expansion_n=len(expansion_keys), impact_n=len(impact_orders),
        expansion_rows=top_expansion, impact_rows=top_payment,
        no_pay=f"{unmatched_pay:,}", no_item=f"{unmatched_items:,}",
        unmatched_payment=f"{int(impact_summary['unmatched_payment_rows_excluded']):,}",
        unmatched_item=f"{int(impact_summary['unmatched_item_rows_excluded']):,}",
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result, encoding="utf-8")
    return target.resolve()
