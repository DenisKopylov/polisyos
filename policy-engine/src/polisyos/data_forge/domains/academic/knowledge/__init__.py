"""Academic SKG query/search API."""

from __future__ import annotations

import importlib

__all__ = [
    "CanonicalVariableResolver",
    "EdgeSupportRecord",
    "EdgeTransportRecord",
    "ParameterCandidate",
    "ParameterSelector",
    "ResolutionResult",
    "SKGQuery",
    "SKGVersionManager",
    "ScholarKnowledgeGraph",
    "VariableCanonizer",
]

_LAZY_EXPORTS = {
    "ScholarKnowledgeGraph": "polisyos.data_forge.domains.academic.knowledge.search",
    "CanonicalVariableResolver": "polisyos.data_forge.domains.academic.knowledge.canonical_resolver",
    "ResolutionResult": "polisyos.data_forge.domains.academic.knowledge.canonical_resolver",
    "ParameterSelector": "polisyos.data_forge.domains.academic.knowledge.parameter_selector",
    "SKGQuery": "polisyos.data_forge.domains.academic.knowledge.skg_query",
    "ParameterCandidate": "polisyos.data_forge.domains.academic.knowledge.skg_query",
    "EdgeSupportRecord": "polisyos.data_forge.domains.academic.knowledge.skg_query",
    "EdgeTransportRecord": "polisyos.data_forge.domains.academic.knowledge.skg_query",
    "SKGVersionManager": "polisyos.data_forge.domains.academic.knowledge.skg_versioning",
    "VariableCanonizer": "polisyos.data_forge.domains.academic.knowledge.variable_canonizer",
}


def __getattr__(name: str):
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value
