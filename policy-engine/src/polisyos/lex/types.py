"""Lex runtime contracts plus compatibility aliases for legal corpus write contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from polisyos.data_forge.domains.legal.contracts import (
    ActiveVersionResult,
    ActiveVersionStrategy,
    LegalDocSource,
    LexIngestOptions,
    LexIngestResult,
    LexStructureOptions,
    LexStructureResult,
    LexVersionIndexOptions,
    LexVersionIndexResult,
    WorldEventRefLike,
)
from polisyos.fabric.docs import (
    DocChunkOptions,
    DocIngestOptions,
    DocNormalizeOptions,
    DocStructureOptions,
)

if TYPE_CHECKING:
    from polisyos.ir.loading.fact_log import FactSegmentManifest


class ResolveCandidate(BaseModel):
    """Candidate row exposed when ``ActiveVersionStrategy.include_candidates`` is enabled.

    Attributes:
        doc_version_id: Candidate legal revision id.
        doc_meta_artifact_id: Artifact id of the candidate ``DocMeta`` payload.
        published_at: Publication date carried from the document metadata.
        effective_from: Inclusive effectivity start date.
        effective_to: Inclusive effectivity end date, or ``None`` for open-ended versions.
    """

    model_config = ConfigDict(extra="forbid")

    doc_version_id: str
    doc_meta_artifact_id: str
    published_at: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None


@dataclass(frozen=True)
class NormPackBudgets:
    """Soft assembly limits applied while building a `NormPack`."""

    max_docs: int | None = None
    max_provisions: int | None = None
    max_claims: int | None = None


@dataclass(frozen=True)
class NormPackBuildRequest:
    """Inputs that define which legal materials should form a `NormPack`."""

    jurisdiction: str
    as_of: str
    domain: str | None = None
    doc_source_ids: list[str] | None = None
    claim_set_artifact_ids: list[str] | None = None

    selection_policy_id: str = "lex.versioning_v1.effective_range_then_published_at"
    conflict_policy_id: str = "policy.conflicts.default_v1"
    trust_policy_id: str = "policy.trust.default_v1"

    budgets: NormPackBudgets = field(default_factory=NormPackBudgets)


@dataclass(frozen=True)
class SelectedDocVersion:
    """One selected document revision included in a ``NormPack`` assembly.

    The row records both the winning ``doc_version_id`` and the selection policy/index that
    justified it, which lets downstream audit tooling distinguish explicit claim-set selection
    from temporal source resolution.
    """

    doc_source_id: str
    doc_version_id: str
    doc_meta_artifact_id: str
    selection_policy_id: str
    used_version_index_artifact_id: str | None
    explanation: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NormPackBuildResult:
    """Materialized `NormPack` selection, provenance, and world-event outputs."""

    request: NormPackBuildRequest
    jurisdiction_norm: str
    as_of_norm: str
    domain_norm: str | None

    selected_doc_versions: list[SelectedDocVersion]
    selected_fragment_ids: list[str]

    claim_set_artifact_ids: list[str]
    norm_claim_ids: list[str]

    conflict_set_ids: list[str]
    conflict_resolution_artifact_ids: list[str]
    trust_assessment_ids: list[str]

    norm_pack_artifact_id: str
    norm_pack_world_id: str

    world_event_id: str
    world_event_artifact_id: str
    world_segment_manifest: FactSegmentManifest

    built_by: str = "pipeline:lex.normpack.assembly_v1"
    warnings: list[str] = field(default_factory=list)


__all__ = [
    "ActiveVersionResult",
    "ActiveVersionStrategy",
    "DocChunkOptions",
    "DocIngestOptions",
    "DocNormalizeOptions",
    "DocStructureOptions",
    "LegalDocSource",
    "LexIngestOptions",
    "LexIngestResult",
    "LexStructureOptions",
    "LexStructureResult",
    "LexVersionIndexOptions",
    "LexVersionIndexResult",
    "NormPackBudgets",
    "NormPackBuildRequest",
    "NormPackBuildResult",
    "ResolveCandidate",
    "SelectedDocVersion",
    "WorldEventRefLike",
]
