
import pandas as pd
import pytest

from granguard.joins import analyze_join


def test_one_to_one():
    left = pd.DataFrame({"id": [1, 2, 3]})
    right = pd.DataFrame({"id": [1, 2, 3]})

    result = analyze_join(
        left, right, on="id", expected="1:1"
    )

    assert result["actual_relationship"] == "1:1"
    assert result["relationship_valid"] is True
    assert result["predicted_rows"] == 3
    assert result["metric_duplication_risk"] is False


def test_one_to_many():
    left = pd.DataFrame({
        "id": ["A001", "A002", "A003"]
    })

    right = pd.DataFrame({
        "id": ["A001", "A001", "A002"]
    })

    result = analyze_join(
        left, right, on="id", expected="1:N"
    )

    assert result["actual_relationship"] == "1:N"
    assert result["relationship_valid"] is True
    assert result["predicted_rows"] == 4
    assert result["left_join_row_growth"] == 1
    assert result["unmatched_left_rows"] == 1
    assert result["metric_duplication_risk"] is True


def test_relationship_violation():
    left = pd.DataFrame({"id": [1, 2, 3]})
    right = pd.DataFrame({"id": [1, 1, 2]})

    result = analyze_join(
        left, right, on="id", expected="1:1"
    )

    assert result["actual_relationship"] == "1:N"
    assert result["relationship_valid"] is False


def test_many_to_many():
    left = pd.DataFrame({"id": ["A", "A"]})
    right = pd.DataFrame({"id": ["A", "A", "A"]})

    result = analyze_join(
        left, right, on="id", expected="N:N"
    )

    assert result["actual_relationship"] == "N:N"
    assert result["relationship_valid"] is True
    assert result["predicted_rows"] == 6
    assert result["left_join_row_growth"] == 4
    assert result["repeated_left_metric_rows"] == 4


def test_unmatched_keys():
    left = pd.DataFrame({"id": [1, 2]})
    right = pd.DataFrame({"id": [3]})

    result = analyze_join(
        left, right, on="id", how="left"
    )

    assert result["predicted_rows"] == 2
    assert result["unmatched_left_rows"] == 2
    assert result["unmatched_right_rows"] == 1
    assert result["matched_key_groups"] == 0


def test_null_keys_match():
    left = pd.DataFrame({
        "id": ["A", None]
    })
    right = pd.DataFrame({
        "id": ["A", None, None]
    })

    result = analyze_join(
        left, right, on="id"
    )

    actual = left.merge(right, on="id", how="left")

    assert result["predicted_rows"] == len(actual)
    assert result["predicted_rows"] == 3
    assert result["right_null_keys"] == 2


def test_invalid_column():
    left = pd.DataFrame({"id": [1, 2]})
    right = pd.DataFrame({"other_id": [1, 2]})

    with pytest.raises(ValueError, match="not found"):
        analyze_join(left, right, on="id")

def test_analyze_join_with_all_null_right_keys():
    """
    Test join prediction when the right key
    contains only null values.
    """

    left = pd.DataFrame({
        "id": ["A", None, None]
    })

    right = pd.DataFrame({
        "id": [None, None]
    })

    result = analyze_join(
        left,
        right,
        on="id",
        how="left"
    )

    assert result["predicted_rows"] == 5
    assert result["left_join_row_growth"] == 2
    assert result["repeated_left_metric_rows"] == 2
    assert result["matched_key_groups"] == 1
    assert result["metric_duplication_risk"] is True
