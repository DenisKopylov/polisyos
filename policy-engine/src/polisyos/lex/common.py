from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any

__all__ = ["collapse_ws", "latest_object_by_subject", "parse_iso_date"]


def collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def parse_iso_date(value: str | None) -> date | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        if len(raw) == 10 and raw.count("-") == 2:
            return date.fromisoformat(raw)
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except Exception:
        return None


def latest_object_by_subject(
    facts: Any,
    *,
    subject_ids: set[str],
    predicate_id: str,
) -> dict[str, str]:
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
        by=["subject_id", "tx_time", "fact_id"],
        ascending=[True, False, False],
    )
    subset = subset.drop_duplicates(subset=["subject_id"], keep="first")
    return {str(row["subject_id"]): str(row["object_value"]) for _, row in subset.iterrows()}
