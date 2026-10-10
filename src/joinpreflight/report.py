
from collections.abc import Mapping
from html import escape
from pathlib import Path
from string import Template

import pandas as pd


def generate_html_report(
    report: Mapping,
    risky_keys: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    """Generate an offline HTML report for a LEFT JOIN."""

    if not isinstance(report, Mapping):
        raise TypeError("report must be a mapping")

    if not isinstance(risky_keys, pd.DataFrame):
        raise TypeError("risky_keys must be a DataFrame")

    if report.get("join_type") != "left":
        raise ValueError(
            "HTML report currently supports LEFT JOIN only"
        )

    required = {
        "join_key",
        "expected_relationship",
        "actual_relationship",
        "relationship_valid",
        "left_rows",
        "right_rows",
        "predicted_rows",
        "unmatched_left_rows",
        "left_join_row_growth",
        "repeated_left_metric_rows",
        "metric_duplication_risk",
    }

    missing = required - report.keys()
    if missing:
        raise ValueError(
            f"Missing report fields: {sorted(missing)}"
        )

    key = report["join_key"]

    columns = {
        key,
        "left_count",
        "right_count",
        "joined_rows",
        "extra_left_rows",
    }

    if not columns.issubset(risky_keys.columns):
        raise ValueError(
            "Missing risky-key fields: "
            f"{sorted(columns - set(risky_keys.columns))}"
        )

    def safe(value) -> str:
        return escape(str(value), quote=True)

    # Summary metrics
    total_extra = int(report["repeated_left_metric_rows"])

    top_extra = sum(
        int(x) for x in risky_keys["extra_left_rows"]
    )

    share = (
        100 * top_extra / total_extra
        if total_extra else 0.0
    )

    left_rows = int(report["left_rows"])
    growth = int(report["left_join_row_growth"])

    growth_pct = (
        100 * growth / left_rows
        if left_rows else 0.0
    )

    # Build risky-key table
    max_extra = max(
        (int(x) for x in risky_keys["extra_left_rows"]),
        default=0,
    )

    rows = []

    for _, item in risky_keys.iterrows():
        raw_key = item[key]

        display_key = (
            "NULL" if pd.isna(raw_key)
            else str(raw_key)
        )

        extra = int(item["extra_left_rows"])

        bar_width = (
            100 * extra / max_extra
            if max_extra else 0
        )

        rows.append(
            "<tr>"
            f"<td><code>{safe(display_key)}</code></td>"
            f"<td>{int(item['left_count']):,}</td>"
            f"<td>{int(item['right_count']):,}</td>"
            f"<td>{int(item['joined_rows']):,}</td>"
            "<td class='bar-cell'>"
            f"<span class='bar' "
            f"style='width:{bar_width:.1f}%'></span>"
            f"<strong>{extra:,}</strong>"
            "</td></tr>"
        )

    table_rows = "\n".join(rows) if rows else (
        "<tr><td colspan='5' class='empty'>"
        "未发现导致左表重复的关联键。"
        "</td></tr>"
    )

    # Relationship status
    valid = report["relationship_valid"]

    if valid is True:
        relation_status = "符合预期"
        status_class = "ok"
    elif valid is False:
        relation_status = "不符合预期"
        status_class = "warn"
    else:
        relation_status = "未指定预期关系"
        status_class = "neutral"

    if report["metric_duplication_risk"]:
        risk_message = (
            "检测到左表记录在关联后被重复。"
            "订单级金额等指标直接求和可能产生重复统计；"
            "这并不表示关联本身有错误。"
        )
    else:
        risk_message = (
            "未检测到左表记录因多重匹配而重复，"
            "但仍需按照指标粒度判断聚合方式。"
        )

    # Static HTML template
    template = Template("""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport"
      content="width=device-width, initial-scale=1">
<title>JoinPreflight | JOIN Safety Report</title>
<style>
:root {
    font-family: -apple-system, BlinkMacSystemFont,
                 "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
body {
    background: #f4f7fb;
    color: #172436;
    margin: 0;
    line-height: 1.6;
}
main {
    max-width: 1100px;
    margin: auto;
    padding: 40px 20px 80px;
}
header {
    background: #162d47;
    color: white;
    padding: 30px;
    border-radius: 16px;
}
header h1 { margin: 0 0 8px; }
header p { opacity: .85; margin: 0; }
.grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin: 24px 0;
}
.card, section {
    background: white;
    padding: 22px;
    border-radius: 14px;
    box-shadow: 0 2px 10px #142f4810;
}
.label { color: #57677a; font-size: 13px; }
.value {
    font-size: 26px;
    font-weight: 700;
    margin-top: 5px;
}
section { margin-top: 18px; }
h2 { font-size: 18px; margin: 0 0 12px; }
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 99px;
    font-weight: 600;
}
.ok { color: #17633b; background: #e4f4e9; }
.warn { color: #87540e; background: #fff1d4; }
.neutral { color: #4f6177; background: #e9eef3; }
.notice {
    border-left: 4px solid #e5a83e;
    background: #fff8ea;
    padding: 14px;
    border-radius: 5px;
}
.table-wrap { overflow-x: auto; }
table {
    border-collapse: collapse;
    min-width: 780px;
    width: 100%;
}
th, td {
    text-align: left;
    padding: 11px 10px;
    border-bottom: 1px solid #e7ecf2;
}
th { color: #506177; font-size: 13px; }
code { font-size: 12px; }
.bar-cell { min-width: 160px; }
.bar {
    display: inline-block;
    height: 9px;
    background: #347eac;
    border-radius: 5px;
    vertical-align: middle;
    margin-right: 10px;
}
.empty { text-align: center; }
.muted, footer {
    color: #62738a;
    font-size: 13px;
}
@media(max-width:750px) {
    .grid { grid-template-columns: repeat(2,1fr); }
    main { padding: 16px 12px; }
}
</style>
</head>
<body>
<main>
<header>
<h1>JoinPreflight</h1>
<p>JOIN Safety Report · 单键 LEFT JOIN 诊断</p>
</header>

<div class="grid">
<div class="card">
<div class="label">左表行数</div>
<div class="value">$left_rows</div>
</div>
<div class="card">
<div class="label">右表行数</div>
<div class="value">$right_rows</div>
</div>
<div class="card">
<div class="label">预测 JOIN 行数</div>
<div class="value">$predicted_rows</div>
</div>
<div class="card">
<div class="label">左表行数增长</div>
<div class="value">+$growth</div>
<div class="muted">+$growth_pct%</div>
</div>
</div>

<section>
<h2>关系与风险概览</h2>
<p>
关联键：<code>$key</code>
· 预期：$expected
· 实际：$actual
<span class="badge $status_class">$relation_status</span>
</p>
<p>
未匹配左表行数：<strong>$unmatched</strong>
· 左表额外重复行数：<strong>$total_extra</strong>
</p>
<div class="notice">$risk_message</div>
</section>

<section>
<h2>Top $top_n 扩张键</h2>
<p class="muted">
这 $top_n 个键合计贡献 $top_extra 条额外记录，
占所有额外重复行的 $share%。
排名并不等同于数据质量错误。
</p>
<div class="table-wrap">
<table>
<thead><tr>
<th>关联键</th>
<th>左表次数</th>
<th>右表次数</th>
<th>JOIN 行数</th>
<th>额外重复行数</th>
</tr></thead>
<tbody>$table_rows</tbody>
</table>
</div>
</section>

<footer>
<p>
报告由 JoinPreflight 生成。
本版本针对 pandas 单列 LEFT JOIN，
空键采用 pandas 的匹配语义。
</p>
</footer>
</main>
</body>
</html>""")

    html = template.substitute(
        left_rows=f"{left_rows:,}",
        right_rows=f"{int(report['right_rows']):,}",
        predicted_rows=f"{int(report['predicted_rows']):,}",
        growth=f"{growth:,}",
        growth_pct=f"{growth_pct:.2f}",
        key=safe(key),
        expected=safe(report["expected_relationship"]),
        actual=safe(report["actual_relationship"]),
        status_class=status_class,
        relation_status=safe(relation_status),
        unmatched=f"{int(report['unmatched_left_rows']):,}",
        total_extra=f"{total_extra:,}",
        risk_message=safe(risk_message),
        top_n=len(risky_keys),
        top_extra=f"{top_extra:,}",
        share=f"{share:.2f}",
        table_rows=table_rows,
    )

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")

    return target.resolve()
