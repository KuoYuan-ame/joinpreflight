# Synthetic demonstration fixture

These CSVs are **fictional**. They are deliberately small enough to verify by hand; they are **not** a sample extracted from the Olist dataset.

- Orders: 6 unique identifiers, `A001` through `A006`.
- Item lines: A001 has 2, A002 has 1, A003 has 3, A004 has 0, A005 has 1, A006 has 0.
- Payments: A001 has two payment records (10.25 + 19.75 = 30.00 BRL). A006 has **no** payment record.
- Correct known payment total over available recorded payments = 215.00 BRL.
- Predicted LEFT JOIN row count = 2 + 1 + 3 + 1 + 1 + 1 = 9.
- Naive payment SUM after LEFT JOIN = 2·30 + 50 + 3·70 + 25 + 40 = 385.00 BRL.
- Modeled overcount = 170.00 BRL, or 79.07% of the recorded-payment baseline.

The missing payment record is not evidence that the corresponding order was paid 0 BRL. The baseline is defined using **available recorded payments**.
