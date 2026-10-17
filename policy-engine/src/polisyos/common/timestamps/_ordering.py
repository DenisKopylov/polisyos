"""Resolve the latest non-empty fact object for each requested subject."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


def latest_object_by_subject(
    facts: pd.DataFrame,
    *,
    subject_ids: set[str],
    predicate_id: str,
) -> dict[str, str]:
    """Return the latest non-empty object value for each requested fact subject."""
    if not subject_ids:
        return {}
    subset = facts[
        (facts["predicate_id"] == predicate_id)
        & (facts["subject_id"].isin(subject_ids))
        & (facts["object_value"].notna())
    ].copy()
    if subset.empty:
        return {}
    subset["tx_time"] = subset["tx_time"].fillna("").astype(str)
    subset["fact_id"] = subset["fact_id"].fillna("").astype(str)
    subset = subset.sort_values(
        by=["subject_id", "tx_time", "fact_id"], ascending=[True, False, False]
    )
    subset = subset.drop_duplicates(subset=["subject_id"], keep="first")
    return {str(row["subject_id"]): str(row["object_value"]) for _, row in subset.iterrows()}
