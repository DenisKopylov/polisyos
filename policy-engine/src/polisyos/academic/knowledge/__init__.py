"""Academic SKG query/search API."""

from __future__ import annotations

import importlib

__all__ = [
    "ScholarKnowledgeGraph",
    "CanonicalVariableResolver",
    "ResolutionResult",
    "ParameterSelector",
    "SKGQuery",
    "ParameterCandidate",
    "EdgeSupportRecord",
    "EdgeTransportRecord",
    "SKGVersionManager",
    "VariableCanonizer",
]

_LAZY_EXPORTS = {
    "ScholarKnowledgeGraph": "polisyos.academic.knowledge.search",
    "CanonicalVariableResolver": "polisyos.academic.knowledge.canonical_resolver",
    "ResolutionResult": "polisyos.academic.knowledge.canonical_resolver",
    "ParameterSelector": "polisyos.academic.knowledge.parameter_selector",
    "SKGQuery": "polisyos.academic.knowledge.skg_query",
    "ParameterCandidate": "polisyos.academic.knowledge.skg_query",
    "EdgeSupportRecord": "polisyos.academic.knowledge.skg_query",
    "EdgeTransportRecord": "polisyos.academic.knowledge.skg_query",
    "SKGVersionManager": "polisyos.academic.knowledge.skg_versioning",
    "VariableCanonizer": "polisyos.academic.knowledge.variable_canonizer",
}


def __getattr__(name: str):
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value
