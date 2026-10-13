import json

import pandas as pd

from joinpreflight.cli import main


def _make_csv(tmp_path):
    orders = tmp_path / "orders.csv"
    items = tmp_path / "items.csv"
    payments = tmp_path / "payments.csv"
    pd.DataFrame({"order_id": ["001", "002", "003"]}).to_csv(orders, index=False)
    pd.DataFrame({"order_id": ["001", "001", "002", "002", "002"]}).to_csv(items, index=False)
    pd.DataFrame({"order_id": ["001", "001", "002"],
                  "payment_value": ["20.01", "9.99", "100.00"]}).to_csv(payments, index=False)
    return orders, items, payments


def test_cli_impact_exports_json_html_and_figure(tmp_path):
    orders, items, payments = _make_csv(tmp_path)
    prefix = tmp_path / "reports" / "metric_impact"
    html = tmp_path / "reports" / "impact.html"
    jsonfile = tmp_path / "reports" / "impact.json"
    status = main([
        "impact", "--orders", str(orders), "--items", str(items),
        "--payments", str(payments), "--on", "order_id",
        "--value", "payment_value", "--top", "1", "--currency", "BRL",
        "--figure", str(prefix), "--html", str(html), "--json", str(jsonfile),
    ])
    assert status == 0
    assert prefix.with_suffix(".png").stat().st_size > 1000
    assert prefix.with_suffix(".pdf").stat().st_size > 1000
    data = json.loads(jsonfile.read_text(encoding="utf-8"))
    assert data["summary"]["correct_payment_total"] == 130
    assert data["summary"]["naive_payment_total"] == 360
    assert data["summary"]["inflation_amount"] == 230
    assert data["top_impact_orders"][0]["order_id"] == "002"
    content = html.read_text(encoding="utf-8")
    assert "data:image/png;base64," in content
    assert "Payment metric comparison" in content
    assert "230.00 BRL" in content


def test_cli_impact_without_visualization(tmp_path):
    orders, items, payments = _make_csv(tmp_path)
    out = tmp_path / "impact.json"
    assert main([
        "impact", "--orders", str(orders), "--items", str(items),
        "--payments", str(payments), "--json", str(out),
    ]) == 0
    assert out.exists()


def test_cli_impact_rejects_bad_input(tmp_path):
    orders, items, payments = _make_csv(tmp_path)
    assert main([
        "impact", "--orders", str(orders), "--items", str(items),
        "--payments", str(payments), "--currency", "<bad>",
    ]) == 2
