"""Column-level filtering helpers driven by authorization decisions."""
from __future__ import annotations

from collections.abc import Iterable, Sequence

import pandas as pd


def normalize_allowed_columns(columns: Iterable[str] | None) -> frozenset[str] | None:
    """Normalize allowed columns helper."""
    if columns is None:
        return None
    normalized = {str(column).strip() for column in columns if str(column).strip()}
    return frozenset(normalized)


def apply_requested_column_guard(
    *,
    requested: Sequence[str],
    allowed: frozenset[str] | None,
) -> tuple[str, ...]:
    """Return effective requested columns after authz guard checks.

    Rules:
    - If no allowlist is provided, preserve requested columns.
    - If requested is ["*"], expand to sorted allowlist.
    - If requested contains any disallowed column, raise ValueError.
    """

    if allowed is None:
        return tuple(requested)
    if not allowed:
        raise ValueError("No columns are authorized for this principal")

    if len(requested) == 1 and requested[0] == "*":
        return tuple(sorted(allowed))

    disallowed = [column for column in requested if column != "*" and column not in allowed]
    if disallowed:
        raise ValueError(f"Unauthorized columns requested: {sorted(disallowed)}")

    if "*" in requested:
        return tuple(sorted(allowed))
    return tuple(requested)


def mask_dataframe_columns(
    frame: pd.DataFrame,
    *,
    allowed: frozenset[str] | None,
) -> pd.DataFrame:
    """Drop unauthorized columns from a DataFrame (defense in depth)."""

    if allowed is None:
        return frame
    keep = [column for column in frame.columns if column in allowed]
    return frame.loc[:, keep]


__all__ = [
    "apply_requested_column_guard",
    "mask_dataframe_columns",
    "normalize_allowed_columns",
]
