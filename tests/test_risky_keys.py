
import pandas as pd
import pytest

from joinpreflight.joins import (
    analyze_join,
    rank_risky_keys,
)


def test_risky_keys_ranking():
    left = pd.DataFrame({
        "id": ["A", "B", "B", "C", "D"]
    })

    right = pd.DataFrame({
        "id": ["A", "A", "A", "A", "B", "B", "C"]
    })

    result = rank_risky_keys(
        left, right, on="id", top_n=10
    )

    assert result["id"].tolist() == ["A", "B"]
    assert result["extra_left_rows"].tolist() == [3, 2]
    assert result["joined_rows"].tolist() == [4, 4]

    report = analyze_join(left, right, on="id")

    assert sum(result["extra_left_rows"]) == (
        report["left_join_row_growth"]
    )


def test_no_risky_keys():
    left = pd.DataFrame({"id": [1, 2]})
    right = pd.DataFrame({"id": [1, 2]})

    result = rank_risky_keys(left, right, on="id")

    assert result.empty


def test_null_key_expansion():
    left = pd.DataFrame({
        "id": ["A", None, None]
    })

    right = pd.DataFrame({
        "id": [None, None]
    })

    result = rank_risky_keys(left, right, on="id")

    assert len(result) == 1
    assert pd.isna(result.iloc[0]["id"])
    assert result.iloc[0]["extra_left_rows"] == 2


def test_invalid_top_n():
    left = pd.DataFrame({"id": [1]})
    right = pd.DataFrame({"id": [1]})

    with pytest.raises(ValueError):
        rank_risky_keys(left, right, "id", top_n=0)
