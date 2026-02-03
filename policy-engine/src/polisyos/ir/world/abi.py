from __future__ import annotations

from enum import Enum


class NodeKind(str, Enum):
    ARTIFACT = "artifact"
    DOC_SOURCE = "doc.source"
    DOC_VERSION = "doc.version"
    DOC_FRAGMENT = "doc.fragment"
    CLAIM = "claim"
    WORLD_EVENT = "world.event"
    PROV_AGENT = "prov.agent"
    PROV_ACTIVITY = "prov.activity"


class EdgeKind(str, Enum):
    DOC_HAS_VERSION = "doc.has_version"
    DOC_HAS_FRAGMENT = "doc.has_fragment"
    CLAIM_CITES = "claim.cites"
    CLAIM_DERIVED_FROM = "claim.derived_from"
    PROV_USED = "prov.used"
    PROV_WAS_GENERATED_BY = "prov.was_generated_by"
    PROV_WAS_DERIVED_FROM = "prov.was_derived_from"
    PROV_WAS_ASSOCIATED_WITH = "prov.was_associated_with"
    PROV_WAS_ATTRIBUTED_TO = "prov.was_attributed_to"


RESERVED_WORLD_PREFIXES_V1: tuple[str, ...] = (
    "artifact",
    "doc",
    "docv",
    "frag",
    "claim",
    "event",
    "prov",
)


__all__ = [
    "EdgeKind",
    "NodeKind",
    "RESERVED_WORLD_PREFIXES_V1",
]
