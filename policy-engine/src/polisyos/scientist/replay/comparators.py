"""Built-in custom comparators for replay diff."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from polisyos.scientist.replay.diff import DiffToleranceConfig


def date_comparator(a: Any, b: Any, cfg: DiffToleranceConfig) -> float:
    """Compare ISO 8601 date strings by timedelta."""
    try:
        dt_a = datetime.fromisoformat(str(a))
        dt_b = datetime.fromisoformat(str(b))
    except (ValueError, TypeError):
        return 0.0 if a != b else 1.0
    diff_seconds = abs((dt_a - dt_b).total_seconds())
    # Within 1 second → perfect match, decays linearly over 1 hour
    if diff_seconds <= 1.0:
        return 1.0
    return max(0.0, 1.0 - diff_seconds / 3600.0)


def json_string_comparator(a: Any, b: Any, cfg: DiffToleranceConfig) -> float:
    """Parse JSON strings and compare structurally."""
    try:
        parsed_a = json.loads(str(a))
        parsed_b = json.loads(str(b))
    except (json.JSONDecodeError, TypeError):
        return 0.0 if a != b else 1.0
    if parsed_a == parsed_b:
        return 1.0
    # Shallow key comparison for dicts
    if isinstance(parsed_a, dict) and isinstance(parsed_b, dict):
        all_keys = set(parsed_a.keys()) | set(parsed_b.keys())
        if not all_keys:
            return 1.0
        common = sum(
            1 for k in all_keys if k in parsed_a and k in parsed_b and parsed_a[k] == parsed_b[k]
        )
        return common / len(all_keys)
    return 0.0
