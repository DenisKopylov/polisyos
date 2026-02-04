from __future__ import annotations

from enum import Enum


class NodeKind(str, Enum):
    ARTIFACT = "artifact"
    DOC_SOURCE = "doc.source"
    DOC_VERSION = "doc.version"
    DOC_FRAGMENT = "doc.fragment"
    CLAIM = "claim"
    CONFLICT_SET = "conflict_set"
    TRUST_ASSESSMENT = "trust.assessment"
    QUALITY_REPORT = "quality.report"
    WORLD_EVENT = "world.event"
    PROV_AGENT = "prov.agent"
    PROV_ACTIVITY = "prov.activity"


class EdgeKind(str, Enum):
    DOC_HAS_VERSION = "doc.has_version"
    DOC_HAS_FRAGMENT = "doc.has_fragment"
    CLAIM_CITES = "claim.cites"
    CLAIM_DERIVED_FROM = "claim.derived_from"
    CLAIM_IN_CONFLICT_SET = "claim.in_conflict_set"
    CONFLICT_RESOLVES_TO = "conflict.resolves_to"
    CLAIM_SUPPORTS = "claim.supports"
    CLAIM_CONTRADICTS = "claim.contradicts"
    REPORT_ABOUT = "report.about"
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
    "cset",
    "trust",
    "quality",
    "event",
    "prov",
)


__all__ = [
    "EdgeKind",
    "NodeKind",
    "RESERVED_WORLD_PREFIXES_V1",
]
