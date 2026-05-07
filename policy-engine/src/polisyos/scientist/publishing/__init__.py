"""Canonical Scientist publishing facade."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "COMPILER_BACKED_DECISION_CARD_FLAG",
    "DECISION_GRADE_COMPILER_FLAG",
    "DECISION_GRADE_EXPORT_KIND",
    "DECISION_GRADE_EXPORT_SCHEMA_NAME",
    "DECISION_GRADE_EXPORT_SCHEMA_VERSION",
    "FORBIDDEN_PUBLIC_EXPORT_TOKENS",
    "DecisionGradeExport",
    "OutputAudience",
    "OutputOmissionRecord",
    "assert_decision_grade_exports_consistent",
    "compile_decision_grade_export",
    "compile_decision_grade_exports",
    "decision_grade_export_inputs",
    "load_decision_grade_export",
    "persist_decision_grade_export",
    "publish_decision",
)

_PUBLISHER_MODULE = "polisyos.scientist.orchestration.orchestrator.publisher"


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(_PUBLISHER_MODULE), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
