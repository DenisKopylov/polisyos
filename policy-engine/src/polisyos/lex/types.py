"""Boundary contracts for Lex corpus, versioning, and NormPack stages.

These dataclasses and Pydantic models are the payloads returned by ``polisyos.lex.api`` and
persisted alongside legal corpus artifacts. They intentionally carry provenance references and
selection explanations so downstream legal-evaluation and intervention code can reason about
which document revision, provision set, and claim set formed a ``NormPack``.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict

from polisyos.fabric.docs import (
    DocChunkOptions,
    DocIngestOptions,
    DocNormalizeOptions,
    DocStructureOptions,
)

from .errors import LexValidationError

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from polisyos.ir.fact_log import FactSegmentManifest


@dataclass(frozen=True)
class LegalDocSource:
    """Canonical source identity and provenance for one legal document.

    Exactly one stable locator must be supplied: either a canonical URL or an
    official registry identifier. The remaining fields capture the publication,
    jurisdiction, and temporal metadata that downstream Lex pipelines preserve
    into document manifests.
    """

    canonical_url: str | None = None
    official_id: str | None = None

    license: str = ""
    retrieved_at: datetime | None = None
    jurisdiction: str | None = None
    language: str | None = None
    title: str | None = None
    publisher: str | None = None
    source_type: str | None = None
    source_url: str | None = None

    published_at_iso: str | None = None
    effective_from_iso: str | None = None
    effective_to_iso: str | None = None

    def __post_init__(self) -> None:
        provided = [value for value in (self.canonical_url, self.official_id) if value]
        if len(provided) != 1:
            raise LexValidationError("exactly one of canonical_url or official_id is required")
        if not self.license.strip():
            raise LexValidationError("license is required")

        if (
            self.official_id
            and self.jurisdiction
            and not self.official_id.startswith(f"{self.jurisdiction}:")
        ):
            warnings.warn(
                "official_id is recommended to use '{jurisdiction}:{act_code}' format",
                UserWarning,
                stacklevel=2,
            )


@dataclass(frozen=True)
class LexIngestOptions:
    """Controls the corpus ingest, normalization, and chunking stages.

    The Lex ingest pipeline can stop after raw persistence or continue into
    normalization, structure building, and chunk generation. These flags also
    carry the provenance identifiers written into fact-log events.
    """

    docs_ingest: DocIngestOptions | None = None
    docs_normalize: DocNormalizeOptions | None = None
    docs_structure: DocStructureOptions | None = None
    docs_chunk: DocChunkOptions | None = None

    run_normalize: bool = True
    run_structure: bool = False
    run_chunk: bool = False

    write_lex_meta_update_event: bool = True
    lex_agent_id: str = "prov.agent.lex_corpus"
    lex_activity_id: str = "prov.activity.lex_corpus.ingest"
    doc_props_merge_policy: Literal["overwrite_lex", "merge_lex"] = "merge_lex"


@dataclass(frozen=True)
class WorldEventRefLike:
    """Minimal reference to a world event emitted during legal corpus ingest."""

    event_id: str
    event_artifact_id: str
    event_kind: str | None = None


@dataclass(frozen=True)
class LexIngestResult:
    """Artifact references and event metadata produced by document ingest."""

    doc_source_id: str
    doc_version_id: str
    raw_ref: str
    normalized_ref: str | None
    structure_ref: str | None
    chunks_ref: str | None
    doc_meta_artifact_id: str
    world_events: list[WorldEventRefLike] = field(default_factory=list)
    world_segments: list[FactSegmentManifest] = field(default_factory=list)
    fabric_results: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LexStructureOptions:
    """Options for deterministic legal-structure extraction from a document."""

    jurisdiction: str | None = None
    structure_algorithm_id: str | None = None
    require_articles: bool = False
    enable_tier_b: bool = True
    enable_paragraphs: bool = False
    write_structure_built_at: bool = True

    lex_agent_id: str = "prov.agent.lex_corpus"
    lex_activity_id: str = "prov.activity.lex_corpus.structure"


@dataclass(frozen=True)
class LexStructureResult:
    """Provision-level outputs emitted by the legal structuring stage."""

    doc_source_id: str
    doc_version_id: str
    doc_meta_artifact_id: str
    fragment_ids: list[str]
    provision_index_artifact_id: str
    world_event_id: str
    world_event_artifact_id: str
    world_segment_manifest: FactSegmentManifest
    quality_issues: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LexVersionIndexOptions:
    """Configuration for building active-version indexes across document revisions."""

    selection_policy_id: str = "lex.versioning_v1.effective_range_then_published_at"
    write_doc_source_props_pointer: bool = True

    lex_agent_id: str = "prov.agent.lex_corpus"
    lex_activity_id: str = "prov.activity.lex_corpus.version_index"


@dataclass(frozen=True)
class LexVersionIndexResult:
    """Persisted version-index metadata for one legal document source."""

    doc_source_id: str
    version_index_artifact_id: str
    doc_source_props_artifact_id: str
    world_event_id: str
    world_event_artifact_id: str
    world_segment_manifest: FactSegmentManifest
    versions_count: int
    quality_issues: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ActiveVersionStrategy:
    """How to resolve the active document version for a given `as_of` date."""

    mode: Literal["by_version_index_v1"] = "by_version_index_v1"
    version_index_artifact_id: str | None = None
    fact_log_root: Path | None = None
    as_of_semantics: Literal["date_inclusive"] = "date_inclusive"
    tie_breaker: Literal["effective_from_then_published_then_doc_version_id"] = (
        "effective_from_then_published_then_doc_version_id"
    )
    include_candidates: bool = False


@dataclass(frozen=True)
class ActiveVersionResult:
    """Outcome of active-version resolution for a legal document source."""

    doc_source_id: str
    as_of_iso: str
    selected_doc_version_id: str | None
    selected_doc_meta_artifact_id: str | None
    selection_policy_id: str
    used_version_index_artifact_id: str
    explanation: list[str]
    candidates: list[dict[str, str | None]] = field(default_factory=list)


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
