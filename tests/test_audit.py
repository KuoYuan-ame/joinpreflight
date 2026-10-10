
import pandas as pd
import pytest

from granguard.audit import audit_primary_key


def test_valid_primary_key():
    """A valid primary key has no missing or duplicate values."""

    df = pd.DataFrame({
        "order_id": ["A001", "A002", "A003"],
        "amount": [100, 200, 300]
    })

    result = audit_primary_key(df, "order_id", "orders")

    assert result["row_count"] == 3
    assert result["column_count"] == 2
    assert result["null_key_count"] == 0
    assert result["duplicate_key_count"] == 0
    assert result["is_valid_primary_key"] is True


def test_invalid_primary_key():
    """Detect missing and duplicate primary keys."""

    df = pd.DataFrame({
        "order_id": ["A001", "A002", "A002", None],
        "amount": [100, 200, 300, 50]
    })

    result = audit_primary_key(df, "order_id", "orders")

    assert result["null_key_count"] == 1
    assert result["duplicate_key_count"] == 1
    assert result["is_valid_primary_key"] is False


def test_multiple_missing_keys():
    """Missing values should not count as duplicate keys."""

    df = pd.DataFrame({
        "order_id": ["A001", None, None]
    })

    result = audit_primary_key(df, "order_id")

    assert result["null_key_count"] == 2
    assert result["duplicate_key_count"] == 0
    assert result["is_valid_primary_key"] is False


def test_missing_column():
    """Raise an error when the key column does not exist."""

    df = pd.DataFrame({
        "amount": [100, 200]
    })

    with pytest.raises(ValueError, match="not found"):
        audit_primary_key(df, "order_id")


def test_invalid_dataframe():
    """Reject inputs that are not DataFrames."""

    with pytest.raises(TypeError):
        audit_primary_key(
            ["A001", "A002"],
            "order_id"
        )


def test_empty_dataframe():
    """An empty table satisfies key constraints vacuously."""

    df = pd.DataFrame({
        "order_id": pd.Series(dtype="string")
    })

    result = audit_primary_key(df, "order_id")

    assert result["row_count"] == 0
    assert result["null_key_count"] == 0
    assert result["duplicate_key_count"] == 0
    assert result["is_valid_primary_key"] is True
