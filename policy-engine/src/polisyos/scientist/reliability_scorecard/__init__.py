"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "BENCHMARK_EVIDENCE_CASES",
    "OPERATIONAL_EVIDENCE_CASES",
    "REQUIRED_BENCHMARKS",
    "REQUIRED_OPERATIONAL_SIGNALS",
    "REQUIRED_SCENARIOS",
    "SCENARIO_EVIDENCE_CASES",
    "ScientistReliabilityScorecard",
    "build_scientist_reliability_scorecard",
    "build_scientist_reliability_scorecard_from_evidence",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "BENCHMARK_EVIDENCE_CASES": (
        "polisyos.scientist.validation.reliability_scorecard",
        "BENCHMARK_EVIDENCE_CASES",
    ),
    "OPERATIONAL_EVIDENCE_CASES": (
        "polisyos.scientist.validation.reliability_scorecard",
        "OPERATIONAL_EVIDENCE_CASES",
    ),
    "REQUIRED_BENCHMARKS": (
        "polisyos.scientist.validation.reliability_scorecard",
        "REQUIRED_BENCHMARKS",
    ),
    "REQUIRED_OPERATIONAL_SIGNALS": (
        "polisyos.scientist.validation.reliability_scorecard",
        "REQUIRED_OPERATIONAL_SIGNALS",
    ),
    "REQUIRED_SCENARIOS": (
        "polisyos.scientist.validation.reliability_scorecard",
        "REQUIRED_SCENARIOS",
    ),
    "SCENARIO_EVIDENCE_CASES": (
        "polisyos.scientist.validation.reliability_scorecard",
        "SCENARIO_EVIDENCE_CASES",
    ),
    "ScientistReliabilityScorecard": (
        "polisyos.scientist.validation.reliability_scorecard",
        "ScientistReliabilityScorecard",
    ),
    "build_scientist_reliability_scorecard": (
        "polisyos.scientist.validation.reliability_scorecard",
        "build_scientist_reliability_scorecard",
    ),
    "build_scientist_reliability_scorecard_from_evidence": (
        "polisyos.scientist.validation.reliability_scorecard",
        "build_scientist_reliability_scorecard_from_evidence",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(
            f"module 'polisyos.scientist.reliability_scorecard' has no attribute {name!r}"
        )
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
