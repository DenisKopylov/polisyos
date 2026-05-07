"""Scientist orchestrator public exports."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "DecisionCard",
    "IssuesSummary",
    "KeyMetric",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "DecisionCard": ("polisyos.scientist.orchestration.orchestrator.decision_card", "DecisionCard"),
    "IssuesSummary": ("polisyos.scientist.orchestration.orchestrator.decision_card", "IssuesSummary"),
    "KeyMetric": ("polisyos.scientist.orchestration.orchestrator.decision_card", "KeyMetric"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.scientist.orchestration.orchestrator' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
