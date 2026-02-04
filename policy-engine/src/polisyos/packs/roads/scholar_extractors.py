from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata

_SPEED_RE = re.compile(
    r"(?:speed\s*limit|max\s*speed|максимальн\w*\s+швидк\w*)[^\d]*(\d{2,3})",
    re.IGNORECASE,
)


def roads_speed_limit_extract(
    *,
    ctx,
    meta,
    normalized_text: str,
    options,
):
    from polisyos.fabric.claims.types import ClaimCandidate

    chunk = normalized_text[ctx.offset_start : ctx.offset_end]
    candidates = []

    for match in _SPEED_RE.finditer(chunk):
        value_text = match.group(1)
        candidates.append(
            ClaimCandidate(
                predicate_id="roads.speed_limit_kmh",
                value_text=value_text,
                value_decimal=Decimal(value_text),
                unit_id="roads.kmh",
                citation_fragment_id=ctx.fragment_id,
                qualifiers={"op": "<="},
            )
        )

    return candidates


def _create_lex_norm_regex_extractor():
    from polisyos.fabric.claims.backends.lex_norm_regex_v1 import extract as lex_norm_regex_extract

    return lex_norm_regex_extract


@dataclass(frozen=True)
class _StaticComponent:
    metadata: ComponentMetadata
    factory: Callable[[], object]

    def create(self) -> object:
        return self.factory()


roads_extractor_component = _StaticComponent(
    metadata=ComponentMetadata(
        component_id=ComponentId.parse("roads.scholar.speed_limit@1.0.0"),
        kind=ComponentKind.SCHOLAR_EXTRACTOR,
        abi_targets={"world_abi": "1.x", "ir_abi": "1.x"},
        domains=["roads"],
        jurisdictions=[],
        tags=["pack:roads", "lang:en", "lang:uk", "mime:text/plain"],
        capabilities=Capability.SCHOLAR_EXTRACTOR | Capability.SCHOLAR_ENRICH,
        deps=[],
        display_name="Roads Speed Extractor",
        description="Extracts road speed-limit claims from plain text.",
    ),
    factory=lambda: roads_speed_limit_extract,
)


lex_norm_regex_extractor_component = _StaticComponent(
    metadata=ComponentMetadata(
        component_id=ComponentId.parse("lex.norm_extractor.regex_v1@1.0.0"),
        kind=ComponentKind.LEX_EXTRACTOR,
        abi_targets={"world_abi": "1.x", "ir_abi": "1.x"},
        domains=[],
        jurisdictions=[],
        tags=["pack:roads", "mime:text/plain"],
        capabilities=Capability.LEX_EXTRACTOR,
        deps=[],
        display_name="Lex Norm Regex Extractor",
        description="Component wrapper over legacy lex norm regex extractor.",
    ),
    factory=_create_lex_norm_regex_extractor,
)


__all__ = [
    "lex_norm_regex_extractor_component",
    "roads_extractor_component",
    "roads_speed_limit_extract",
]
