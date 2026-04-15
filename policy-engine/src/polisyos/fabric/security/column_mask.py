"""Column-level filtering helpers driven by authorization decisions."""
from __future__ import annotations

from collections.abc import Iterable, Sequence

import pandas as pd


def _normalize_column_token(value: object) -> str:
    return str(value).strip().casefold()


def _canonical_column_name(value: object) -> str:
    return str(value).strip().lower()


def normalize_allowed_columns(columns: Iterable[str] | None) -> frozenset[str] | None:
    """Canonicalize authz-approved column names before request-time masking is applied."""
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

    allowed_by_token = {_normalize_column_token(column): column for column in allowed}

    if len(requested) == 1 and requested[0] == "*":
        return tuple(sorted(_canonical_column_name(column) for column in allowed_by_token.values()))

    disallowed = [
        column
        for column in requested
        if column != "*" and _normalize_column_token(column) not in allowed_by_token
    ]
    if disallowed:
        raise ValueError(f"Unauthorized columns requested: {sorted(disallowed)}")

    if "*" in requested:
        return tuple(sorted(_canonical_column_name(column) for column in allowed_by_token.values()))
    return tuple(
        _canonical_column_name(
            allowed_by_token.get(_normalize_column_token(column), str(column).strip())
        )
        for column in requested
    )


def mask_dataframe_columns(
    frame: pd.DataFrame,
    *,
    allowed: frozenset[str] | None,
) -> pd.DataFrame:
    """Drop unauthorized columns from a DataFrame (defense in depth)."""

    if allowed is None:
        return frame
    allowed_tokens = {_normalize_column_token(column) for column in allowed}
    keep = [
        column for column in frame.columns if _normalize_column_token(column) in allowed_tokens
    ]
    return frame.loc[:, keep]


__all__ = [
    "apply_requested_column_guard",
    "mask_dataframe_columns",
    "normalize_allowed_columns",
]
