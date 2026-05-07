"""Public fabric tabular module API."""

from __future__ import annotations

from typing import Any

import pandas as pd

__all__ = ["payload_to_dataframe", "require_dataframe"]


def payload_to_dataframe(
    payload: Any,
    *,
    allow_dict: bool = False,
) -> pd.DataFrame | None:
    """Best-effort conversion of connector payloads into pandas DataFrame."""
    if isinstance(payload, pd.DataFrame):
        return payload
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    if allow_dict and isinstance(payload, dict):
        return pd.DataFrame(payload)
    if hasattr(payload, "to_pandas"):
        converted = payload.to_pandas()
        return converted if isinstance(converted, pd.DataFrame) else pd.DataFrame(converted)
    return None


def require_dataframe(
    payload: Any,
    *,
    allow_dict: bool = False,
    label: str = "payload",
) -> pd.DataFrame:
    """Convert payload to DataFrame or raise ValueError for unsupported types."""
    df = payload_to_dataframe(payload, allow_dict=allow_dict)
    if df is None:
        raise ValueError(f"Unsupported {label} type: {type(payload)}")
    return df
