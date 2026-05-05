"""Compatibility shim for a Phase 5/6 decomposition module move."""

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

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "COMPILER_BACKED_DECISION_CARD_FLAG": (
        "polisyos.scientist.orchestrator.publisher",
        "COMPILER_BACKED_DECISION_CARD_FLAG",
    ),
    "DECISION_GRADE_COMPILER_FLAG": (
        "polisyos.scientist.orchestrator.publisher",
        "DECISION_GRADE_COMPILER_FLAG",
    ),
    "DECISION_GRADE_EXPORT_KIND": (
        "polisyos.scientist.orchestrator.publisher",
        "DECISION_GRADE_EXPORT_KIND",
    ),
    "DECISION_GRADE_EXPORT_SCHEMA_NAME": (
        "polisyos.scientist.orchestrator.publisher",
        "DECISION_GRADE_EXPORT_SCHEMA_NAME",
    ),
    "DECISION_GRADE_EXPORT_SCHEMA_VERSION": (
        "polisyos.scientist.orchestrator.publisher",
        "DECISION_GRADE_EXPORT_SCHEMA_VERSION",
    ),
    "DecisionGradeExport": ("polisyos.scientist.orchestrator.publisher", "DecisionGradeExport"),
    "FORBIDDEN_PUBLIC_EXPORT_TOKENS": (
        "polisyos.scientist.orchestrator.publisher",
        "FORBIDDEN_PUBLIC_EXPORT_TOKENS",
    ),
    "OutputAudience": ("polisyos.scientist.orchestrator.publisher", "OutputAudience"),
    "OutputOmissionRecord": ("polisyos.scientist.orchestrator.publisher", "OutputOmissionRecord"),
    "assert_decision_grade_exports_consistent": (
        "polisyos.scientist.orchestrator.publisher",
        "assert_decision_grade_exports_consistent",
    ),
    "compile_decision_grade_export": (
        "polisyos.scientist.orchestrator.publisher",
        "compile_decision_grade_export",
    ),
    "compile_decision_grade_exports": (
        "polisyos.scientist.orchestrator.publisher",
        "compile_decision_grade_exports",
    ),
    "decision_grade_export_inputs": (
        "polisyos.scientist.orchestrator.publisher",
        "decision_grade_export_inputs",
    ),
    "load_decision_grade_export": (
        "polisyos.scientist.orchestrator.publisher",
        "load_decision_grade_export",
    ),
    "persist_decision_grade_export": (
        "polisyos.scientist.orchestrator.publisher",
        "persist_decision_grade_export",
    ),
    "publish_decision": ("polisyos.scientist.orchestrator.publisher", "publish_decision"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.scientist.publisher' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
