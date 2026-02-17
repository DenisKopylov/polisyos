"""Legal knowledge graph: SPO entities, facts, and semantic search."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "LegalKnowledgeGraph",
    "LegalEntity",
    "LegalFact",
    "LegalFactResult",
    "LegalProvision",
    "LegalProvisionResult",
    "LegalSearchResult",
    "SPOCandidate",
    "SPOExtractionResult",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "LegalKnowledgeGraph": ("polisyos.lex.knowledge.search", "LegalKnowledgeGraph"),
    "LegalEntity": ("polisyos.lex.knowledge.types", "LegalEntity"),
    "LegalFact": ("polisyos.lex.knowledge.types", "LegalFact"),
    "LegalFactResult": ("polisyos.lex.knowledge.types", "LegalFactResult"),
    "LegalProvision": ("polisyos.lex.knowledge.types", "LegalProvision"),
    "LegalProvisionResult": ("polisyos.lex.knowledge.types", "LegalProvisionResult"),
    "LegalSearchResult": ("polisyos.lex.knowledge.types", "LegalSearchResult"),
    "SPOCandidate": ("polisyos.lex.knowledge.types", "SPOCandidate"),
    "SPOExtractionResult": ("polisyos.lex.knowledge.types", "SPOExtractionResult"),
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
