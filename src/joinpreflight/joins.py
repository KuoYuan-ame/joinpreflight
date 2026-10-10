
import pandas as pd


RELATIONSHIPS = {"1:1", "1:N", "N:1", "N:N"}
JOIN_TYPES = {"left", "right", "inner", "outer"}


def _key_frequencies(
    left: pd.DataFrame,
    right: pd.DataFrame,
    on: str,
):
    """
    Build non-null key frequency tables.

    Null keys are counted separately to avoid
    dtype mismatches in frequency-table merges.
    """

    for side, df in (("left", left), ("right", right)):
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"{side} must be a DataFrame")

    if not isinstance(on, str):
        raise TypeError("on must be a column name")

    if on in {"_gg_left_count", "_gg_right_count"}:
        raise ValueError(
            "Join key conflicts with internal count columns"
        )

    for side, df in (("left", left), ("right", right)):
        if on not in df.columns:
            raise ValueError(
                f"Column '{on}' not found in {side}"
            )

        if list(df.columns).count(on) != 1:
            raise ValueError(
                f"Column '{on}' must be unique in {side}"
            )

    # Count null keys independently
    left_nulls = int(left[on].isna().sum())
    right_nulls = int(right[on].isna().sum())

    # Only use non-null keys in the frequency merge
    left_present = left.loc[left[on].notna(), [on]]
    right_present = right.loc[right[on].notna(), [on]]

    left_counts = (
        left_present.groupby(
            on, observed=True, sort=False
        )
        .size()
        .reset_index(name="_gg_left_count")
    )

    right_counts = (
        right_present.groupby(
            on, observed=True, sort=False
        )
        .size()
        .reset_index(name="_gg_right_count")
    )

    # Avoid merging incompatible inferred dtypes
    # when either side contains only null keys
    if right_counts.empty:
        counts = left_counts.copy()
        counts["_gg_right_count"] = 0

    elif left_counts.empty:
        counts = right_counts.copy()
        counts["_gg_left_count"] = 0

    else:
        counts = left_counts.merge(
            right_counts,
            on=on,
            how="outer",
            validate="one_to_one",
        )

    counts["_gg_left_count"] = (
        counts["_gg_left_count"]
        .fillna(0)
        .astype("int64")
    )

    counts["_gg_right_count"] = (
        counts["_gg_right_count"]
        .fillna(0)
        .astype("int64")
    )

    return counts, left_nulls, right_nulls


def analyze_join(
    left: pd.DataFrame,
    right: pd.DataFrame,
    on: str,
    how: str = "left",
    expected: str | None = None,
) -> dict:
    """
    Analyze single-key JOIN cardinality
    without materializing the full JOIN.
    """

    if how not in JOIN_TYPES:
        raise ValueError(
            f"how must be one of {sorted(JOIN_TYPES)}"
        )

    if expected is not None and expected not in RELATIONSHIPS:
        raise ValueError(
            f"expected must be one of {sorted(RELATIONSHIPS)}"
        )

    counts, left_nulls, right_nulls = _key_frequencies(
        left, right, on
    )

    a = counts["_gg_left_count"]
    b = counts["_gg_right_count"]

    # Relationship cardinality
    left_unique = bool(
        a.le(1).all() and left_nulls <= 1
    )

    right_unique = bool(
        b.le(1).all() and right_nulls <= 1
    )

    if left_unique and right_unique:
        actual = "1:1"
    elif left_unique:
        actual = "1:N"
    elif right_unique:
        actual = "N:1"
    else:
        actual = "N:N"

    constraints = {
        "1:1": left_unique and right_unique,
        "1:N": left_unique,
        "N:1": right_unique,
        "N:N": True,
    }

    relationship_valid = (
        None
        if expected is None
        else bool(constraints[expected])
    )

    # Non-null key matching
    matched = (a > 0) & (b > 0)
    left_only = (a > 0) & (b == 0)
    right_only = (a == 0) & (b > 0)

    # Inner JOIN: non-null matches + null matches
    inner_rows = sum(
        int(x) * int(y)
        for x, y in zip(a[matched], b[matched])
    )

    inner_rows += left_nulls * right_nulls

    unmatched_left_rows = int(a[left_only].sum())

    if right_nulls == 0:
        unmatched_left_rows += left_nulls

    unmatched_right_rows = int(b[right_only].sum())

    if left_nulls == 0:
        unmatched_right_rows += right_nulls

    predicted_by_type = {
        "inner": inner_rows,
        "left": inner_rows + unmatched_left_rows,
        "right": inner_rows + unmatched_right_rows,
        "outer": (
            inner_rows
            + unmatched_left_rows
            + unmatched_right_rows
        ),
    }

    predicted_rows = int(predicted_by_type[how])

    # Repeated left-side rows
    repeated_left_metric_rows = sum(
        int(x) * (int(y) - 1)
        for x, y in zip(
            a[matched & (b > 1)],
            b[matched & (b > 1)],
        )
    )

    # Null keys can also multiply rows
    if right_nulls > 1:
        repeated_left_metric_rows += (
            left_nulls * (right_nulls - 1)
        )

    matched_key_groups = int(matched.sum())

    if left_nulls > 0 and right_nulls > 0:
        matched_key_groups += 1

    return {
        "join_key": on,
        "join_type": how,
        "expected_relationship": expected,
        "actual_relationship": actual,
        "relationship_valid": relationship_valid,
        "left_rows": int(len(left)),
        "right_rows": int(len(right)),
        "left_null_keys": left_nulls,
        "right_null_keys": right_nulls,
        "matched_key_groups": matched_key_groups,
        "unmatched_left_rows": unmatched_left_rows,
        "unmatched_right_rows": unmatched_right_rows,
        "predicted_rows": predicted_rows,
        "left_join_row_growth": (
            predicted_rows - len(left)
            if how == "left"
            else None
        ),
        "repeated_left_metric_rows": int(
            repeated_left_metric_rows
        ),
        "metric_duplication_risk": bool(
            repeated_left_metric_rows > 0
        ),
    }


def rank_risky_keys(
    left: pd.DataFrame,
    right: pd.DataFrame,
    on: str,
    top_n: int = 10,
) -> pd.DataFrame:
    """
    Rank keys contributing to LEFT JOIN row growth.

    Risk means left-side row duplication,
    not necessarily an incorrect JOIN.
    """

    if (
        not isinstance(top_n, int)
        or isinstance(top_n, bool)
        or top_n < 1
    ):
        raise ValueError(
            "top_n must be a positive integer"
        )

    output_columns = [
        on,
        "left_count",
        "right_count",
        "joined_rows",
        "extra_left_rows",
    ]

    if len(output_columns) != len(set(output_columns)):
        raise ValueError(
            "Join key conflicts with report columns"
        )

    counts, left_nulls, right_nulls = _key_frequencies(
        left, right, on
    )

    # Find non-null keys causing expansion
    risky = counts.loc[
        (counts["_gg_left_count"] > 0)
        & (counts["_gg_right_count"] > 1)
    ].copy()

    # Handle null-key expansion independently
    if left_nulls > 0 and right_nulls > 1:
        null_risk = pd.DataFrame([
            {
                on: None,
                "_gg_left_count": left_nulls,
                "_gg_right_count": right_nulls,
            }
        ])

        risky = pd.concat(
            [risky, null_risk],
            ignore_index=True,
        )

    if risky.empty:
        return pd.DataFrame(
            columns=output_columns
        )

    a = risky["_gg_left_count"]
    b = risky["_gg_right_count"]

    # Python integers prevent multiplication overflow
    risky["joined_rows"] = [
        int(x) * int(y)
        for x, y in zip(a, b)
    ]

    risky["extra_left_rows"] = [
        int(x) * (int(y) - 1)
        for x, y in zip(a, b)
    ]

    risky = risky.rename(
        columns={
            "_gg_left_count": "left_count",
            "_gg_right_count": "right_count",
        }
    )

    risky = risky.sort_values(
        by=["extra_left_rows", "joined_rows"],
        ascending=[False, False],
        kind="stable",
    )

    return (
        risky[output_columns]
        .head(top_n)
        .reset_index(drop=True)
    )
