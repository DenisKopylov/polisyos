"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "_aggregate_monitoring_verdict",
    "_as_bool_or_none",
    "_as_float",
    "_as_str",
    "_extract_artifact_id",
    "_extract_feedback_ref",
    "_extract_metric_observation",
    "_extract_numeric_value",
    "_extract_revised_metric_ids",
    "_extract_rows",
    "_outside_range",
    "_path_get",
    "_within_range",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "_aggregate_monitoring_verdict": (
        "polisyos.scientist.feedback.utils",
        "_aggregate_monitoring_verdict",
    ),
    "_as_bool_or_none": ("polisyos.scientist.feedback.utils", "_as_bool_or_none"),
    "_as_float": ("polisyos.scientist.feedback.utils", "_as_float"),
    "_as_str": ("polisyos.scientist.feedback.utils", "_as_str"),
    "_extract_artifact_id": ("polisyos.scientist.feedback.utils", "_extract_artifact_id"),
    "_extract_feedback_ref": ("polisyos.scientist.feedback.utils", "_extract_feedback_ref"),
    "_extract_metric_observation": (
        "polisyos.scientist.feedback.utils",
        "_extract_metric_observation",
    ),
    "_extract_numeric_value": ("polisyos.scientist.feedback.utils", "_extract_numeric_value"),
    "_extract_revised_metric_ids": (
        "polisyos.scientist.feedback.utils",
        "_extract_revised_metric_ids",
    ),
    "_extract_rows": ("polisyos.scientist.feedback.utils", "_extract_rows"),
    "_outside_range": ("polisyos.scientist.feedback.utils", "_outside_range"),
    "_path_get": ("polisyos.scientist.feedback.utils", "_path_get"),
    "_within_range": ("polisyos.scientist.feedback.utils", "_within_range"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(
            f"module 'polisyos.scientist.feedback_utils' has no attribute {name!r}"
        )
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
