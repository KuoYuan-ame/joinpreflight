
import json
import pandas as pd

from joinpreflight.joins import analyze_join


orders = pd.DataFrame({
    "order_id": ["A001", "A002", "A003"],
    "order_amount": [100, 200, 300],
})

order_items = pd.DataFrame({
    "order_id": ["A001", "A001", "A002"],
    "product": ["X", "Y", "Z"],
})

report = analyze_join(
    left=orders,
    right=order_items,
    on="order_id",
    how="left",
    expected="1:N",
)

print("=" * 60)
print("JOINPREFLIGHT - JOIN SAFETY REPORT")
print("=" * 60)

print(json.dumps(report, indent=4))

# Compare with an actual Pandas JOIN
joined = orders.merge(
    order_items,
    on="order_id",
    how="left"
)

print("\nOriginal order amount:")
print(orders["order_amount"].sum())

print("\nAmount summed after JOIN:")
print(joined["order_amount"].sum())

print("\nPredicted JOIN rows:")
print(report["predicted_rows"])

print("\nActual JOIN rows:")
print(len(joined))
