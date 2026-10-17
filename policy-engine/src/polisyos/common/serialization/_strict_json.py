"""Enforce unambiguous finite JSON values for persisted object intake."""

from __future__ import annotations

import json
import math
from typing import Any, NoReturn


def _reject_json_constant(value: str) -> NoReturn:
    """Reject JavaScript-style non-finite constants outside the JSON number grammar."""
    raise ValueError(f"Non-standard JSON numeric constant: {value}")


def _parse_finite_json_float(value: str) -> float:
    """Parse one JSON decimal number without accepting overflow to infinity."""
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("JSON number is outside the finite float range")
    return parsed


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build one JSON object only when its decoded keys are unambiguous."""
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"Duplicate JSON object key: {key}")
        payload[key] = value
    return payload


def load_strict_json(text: str) -> Any:
    """Parse JSON while rejecting ambiguous keys and non-finite numbers."""
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_json_constant,
        parse_float=_parse_finite_json_float,
    )
