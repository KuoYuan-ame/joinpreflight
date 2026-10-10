
import json
import pandas as pd

from joinpreflight.audit import audit_primary_key


def main():

    # Case 1: Invalid primary key
    orders = pd.DataFrame({
        "order_id": ["A001", "A002", "A002", None],
        "amount": [100, 200, 300, 50]
    })

    result = audit_primary_key(
        df=orders,
        key="order_id",
        table_name="orders"
    )

    print("=" * 60)
    print("CASE 1: INVALID PRIMARY KEY")
    print("=" * 60)
    print(json.dumps(result, indent=4))

    # Case 2: Valid primary key
    clean_orders = pd.DataFrame({
        "order_id": ["A001", "A002", "A003"],
        "amount": [100, 200, 300]
    })

    clean_result = audit_primary_key(
        df=clean_orders,
        key="order_id",
        table_name="clean_orders"
    )

    print("\n" + "=" * 60)
    print("CASE 2: VALID PRIMARY KEY")
    print("=" * 60)
    print(json.dumps(clean_result, indent=4))


if __name__ == "__main__":
    main()
