"""Legal knowledge graph: SPO entities, facts, and semantic search."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "LegalEntity",
    "LegalFact",
    "LegalFactResult",
    "LegalKnowledgeGraph",
    "LegalProvision",
    "LegalProvisionResult",
    "LegalQueryInput",
    "LegalQueryProfile",
    "LegalQueryProfileError",
    "LegalRuleThresholdRow",
    "LegalSearchResult",
    "LegalTemporalCompetence",
    "LegalThresholdEvaluation",
    "search_legal_knowledge",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "LegalKnowledgeGraph": ("polisyos.lex.knowledge.search", "LegalKnowledgeGraph"),
    "LegalQueryInput": ("polisyos.lex.knowledge.store", "LegalQueryInput"),
    "LegalQueryProfile": ("polisyos.lex.knowledge.store", "LegalQueryProfile"),
    "LegalQueryProfileError": ("polisyos.lex.knowledge.store", "LegalQueryProfileError"),
    "LegalEntity": ("polisyos.lex.knowledge.types", "LegalEntity"),
    "LegalFact": ("polisyos.lex.knowledge.types", "LegalFact"),
    "LegalFactResult": ("polisyos.lex.knowledge.types", "LegalFactResult"),
    "LegalProvision": ("polisyos.lex.knowledge.types", "LegalProvision"),
    "LegalProvisionResult": ("polisyos.lex.knowledge.types", "LegalProvisionResult"),
    "LegalRuleThresholdRow": ("polisyos.lex.knowledge.types", "LegalRuleThresholdRow"),
    "LegalSearchResult": ("polisyos.lex.knowledge.types", "LegalSearchResult"),
    "LegalTemporalCompetence": ("polisyos.lex.knowledge.types", "LegalTemporalCompetence"),
    "LegalThresholdEvaluation": ("polisyos.lex.knowledge.types", "LegalThresholdEvaluation"),
    "search_legal_knowledge": (
        "polisyos.lex.knowledge.cli",
        "search_legal_knowledge",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.lex.knowledge' has no attribute '{name}'")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
