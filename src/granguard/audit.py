
import pandas as pd


def audit_primary_key(
    df: pd.DataFrame,
    key: str,
    table_name: str = "table"
) -> dict:
    """
    Audit the quality of a single-column primary key.

    Checks:
    1. Whether the key column exists
    2. Number of missing key values
    3. Number of additional duplicate non-null keys
    4. Whether the primary key is valid
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    if key not in df.columns:
        raise ValueError(
            f"Column '{key}' not found in table '{table_name}'"
        )

    # Basic table information
    row_count = int(df.shape[0])
    column_count = int(df.shape[1])

    # Missing key values
    null_key_count = int(df[key].isna().sum())

    # Additional duplicate non-null key values
    duplicate_key_count = int(
        df[key].dropna().duplicated().sum()
    )

    # Primary key validity
    is_valid_primary_key = bool(
        null_key_count == 0
        and duplicate_key_count == 0
    )

    return {
        "table_name": table_name,
        "key": key,
        "row_count": row_count,
        "column_count": column_count,
        "null_key_count": null_key_count,
        "duplicate_key_count": duplicate_key_count,
        "is_valid_primary_key": is_valid_primary_key,
    }
