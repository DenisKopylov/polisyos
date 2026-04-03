"""Expose the governance-side IR contracts for Trinity policy authoring.

This package facade groups the ``ProblemFrame`` objective vocabulary,
``PolicySpec`` intervention contracts, selector expressions, schedules, and
gate payloads. Public names are resolved lazily to keep the stable authoring
surface available without importing every governance submodule at package load.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "GateVerdict",
    "GatePriority",
    "GateEventType",
    "GateContext",
    "GateRequest",
    "GateDecision",
    "GateEvent",
    "ProblemDomain",
    "ConstraintType",
    "NormativeArbitrationPolicy",
    "NormativeComparisonMode",
    "NormativeOutcomeChannel",
    "NormativeComparisonTarget",
    "UtilityDirection",
    "KPISpec",
    "ObjectiveSpec",
    "SuccessCriterion",
    "ConstraintSpec",
    "StakeholderSpec",
    "StakeholderOutcomeBinding",
    "StakeholderUtilityTerm",
    "StakeholderRightSpec",
    "NormativeFrame",
    "ProblemFrame",
    "MechanismBinding",
    "InterventionSpec",
    "TemporalInterventionStep",
    "TemporalInterventionSequence",
    "ParameterSpec",
    "PolicySpec",
    "ScheduleSpec",
    "schedule_range",
    "SelectorScalar",
    "SelectorValue",
    "SelectorPredicate",
    "SelectorAll",
    "SelectorAny",
    "SelectorNot",
    "SelectorExpr",
    "ValidationIssue",
    "ValidationReport",
    "diff_payloads",
    "issues_from_validation_error",
    "summarize_issues",
    "build_validation_report",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "GateVerdict": ("polisyos.ir.governance.gate", "GateVerdict"),
    "GatePriority": ("polisyos.ir.governance.gate", "GatePriority"),
    "GateEventType": ("polisyos.ir.governance.gate", "GateEventType"),
    "GateContext": ("polisyos.ir.governance.gate", "GateContext"),
    "GateRequest": ("polisyos.ir.governance.gate", "GateRequest"),
    "GateDecision": ("polisyos.ir.governance.gate", "GateDecision"),
    "GateEvent": ("polisyos.ir.governance.gate", "GateEvent"),
    "ProblemDomain": ("polisyos.ir.governance.problem_frame", "ProblemDomain"),
    "ConstraintType": ("polisyos.ir.governance.problem_frame", "ConstraintType"),
    "NormativeArbitrationPolicy": (
        "polisyos.ir.governance.problem_frame",
        "NormativeArbitrationPolicy",
    ),
    "NormativeComparisonMode": (
        "polisyos.ir.governance.problem_frame",
        "NormativeComparisonMode",
    ),
    "NormativeOutcomeChannel": (
        "polisyos.ir.governance.problem_frame",
        "NormativeOutcomeChannel",
    ),
    "NormativeComparisonTarget": (
        "polisyos.ir.governance.problem_frame",
        "NormativeComparisonTarget",
    ),
    "UtilityDirection": ("polisyos.ir.governance.problem_frame", "UtilityDirection"),
    "KPISpec": ("polisyos.ir.governance.problem_frame", "KPISpec"),
    "ObjectiveSpec": ("polisyos.ir.governance.problem_frame", "ObjectiveSpec"),
    "SuccessCriterion": ("polisyos.ir.governance.problem_frame", "SuccessCriterion"),
    "ConstraintSpec": ("polisyos.ir.governance.problem_frame", "ConstraintSpec"),
    "StakeholderSpec": ("polisyos.ir.governance.problem_frame", "StakeholderSpec"),
    "StakeholderOutcomeBinding": (
        "polisyos.ir.governance.problem_frame",
        "StakeholderOutcomeBinding",
    ),
    "StakeholderUtilityTerm": (
        "polisyos.ir.governance.problem_frame",
        "StakeholderUtilityTerm",
    ),
    "StakeholderRightSpec": (
        "polisyos.ir.governance.problem_frame",
        "StakeholderRightSpec",
    ),
    "NormativeFrame": ("polisyos.ir.governance.problem_frame", "NormativeFrame"),
    "ProblemFrame": ("polisyos.ir.governance.problem_frame", "ProblemFrame"),
    "MechanismBinding": ("polisyos.ir.governance.policy_spec", "MechanismBinding"),
    "InterventionSpec": ("polisyos.ir.governance.policy_spec", "InterventionSpec"),
    "TemporalInterventionStep": (
        "polisyos.ir.governance.policy_spec",
        "TemporalInterventionStep",
    ),
    "TemporalInterventionSequence": (
        "polisyos.ir.governance.policy_spec",
        "TemporalInterventionSequence",
    ),
    "ParameterSpec": ("polisyos.ir.governance.policy_spec", "ParameterSpec"),
    "PolicySpec": ("polisyos.ir.governance.policy_spec", "PolicySpec"),
    "ScheduleSpec": ("polisyos.ir.governance.schedule", "ScheduleSpec"),
    "schedule_range": ("polisyos.ir.governance.schedule", "schedule_range"),
    "SelectorScalar": ("polisyos.ir.governance.selector_expr", "SelectorScalar"),
    "SelectorValue": ("polisyos.ir.governance.selector_expr", "SelectorValue"),
    "SelectorPredicate": ("polisyos.ir.governance.selector_expr", "SelectorPredicate"),
    "SelectorAll": ("polisyos.ir.governance.selector_expr", "SelectorAll"),
    "SelectorAny": ("polisyos.ir.governance.selector_expr", "SelectorAny"),
    "SelectorNot": ("polisyos.ir.governance.selector_expr", "SelectorNot"),
    "SelectorExpr": ("polisyos.ir.governance.selector_expr", "SelectorExpr"),
    "ValidationIssue": ("polisyos.ir.governance.validation", "ValidationIssue"),
    "ValidationReport": ("polisyos.ir.governance.validation", "ValidationReport"),
    "diff_payloads": ("polisyos.ir.governance.validation", "diff_payloads"),
    "issues_from_validation_error": (
        "polisyos.ir.governance.validation",
        "issues_from_validation_error",
    ),
    "summarize_issues": ("polisyos.ir.governance.validation", "summarize_issues"),
    "build_validation_report": (
        "polisyos.ir.governance.validation",
        "build_validation_report",
    ),
}


def __getattr__(name: str) -> Any:
    """Resolve a lazily exported governance contract by public name."""
    if name in _LAZY_IMPORTS:
        module_name, attr = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_name)
        value = getattr(module, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'polisyos.ir.governance' has no attribute '{name}'")


def __dir__() -> list[str]:
    """Return eagerly defined names plus lazily exported governance symbols."""
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
