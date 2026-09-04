"""Discovery priors emitted toward Layer B policy design."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.scientist import GraphPriorBundleRef, PriorKnowledgeBundleRef
from polisyos.ir.analytics.cross_graph import EvidenceSourceStatus
from polisyos.ir.analytics.literature import ClaimVocabularyAxisStatus
from polisyos.scientist.methods.discovery.aggregator import (
    EdgeConfidenceEntry,
    EdgeConfidenceMatrix,
)
from polisyos.scientist.methods.discovery.utility_judge import DownstreamUtilityReport
from polisyos.scientist.methods.search.artifact_minimality import (
    ArtifactFunction,
    ArtifactMinimalityMixin,
    artifact_functions_field,
)

GRAPH_PRIOR_BUNDLE_SCHEMA_NAME = "polisyos.scientist.methods.discovery.GraphPriorBundle"
PRIOR_KNOWLEDGE_BUNDLE_SCHEMA_NAME = "polisyos.scientist.methods.discovery.PriorKnowledgeBundle"


class PriorEdge(BaseModel):
    """Directional prior emitted from discovery aggregation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    edge_key: str = Field(min_length=1)
    src: str = Field(min_length=1)
    dst: str = Field(min_length=1)
    lag: int | None = Field(default=None, ge=0)
    presence_confidence: float = Field(ge=0.0, le=1.0)
    orientation_confidence: float = Field(ge=0.0, le=1.0)
    provenance_refs: list[str] = Field(default_factory=list)
    supporting_hypothesis_ids: list[str] = Field(default_factory=list)
    supporting_families: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class DisputedEdge(BaseModel):
    """Unresolved discovery edge with multiple plausible orientations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dispute_id: str = Field(min_length=1)
    skeleton_key: str = Field(min_length=1)
    candidate_edges: list[PriorEdge] = Field(default_factory=list)
    dispute_reasons: list[str] = Field(default_factory=list)
    provenance_refs: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PriorKnowledgeSupport(BaseModel):
    """Academic support row mined for a discovery prior edge."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    edge_key: str = Field(min_length=1)
    src: str = Field(min_length=1)
    dst: str = Field(min_length=1)
    direction: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    n_articles: int = Field(default=0, ge=0)
    evidence_strength: str | None = Field(default="unknown", min_length=1)
    evidence_strength_status: ClaimVocabularyAxisStatus = ClaimVocabularyAxisStatus.CANDIDATE
    candidate_layer: str = Field(default="hybrid", min_length=1)
    article_refs: list[str] = Field(default_factory=list)
    quality_signals: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_evidence_strength_status(self) -> PriorKnowledgeSupport:
        if self.evidence_strength is None:
            if self.evidence_strength_status is not ClaimVocabularyAxisStatus.NOT_ESTABLISHED:
                raise ValueError(
                    "evidence_strength must be absent when its status is not_established"
                )
        elif self.evidence_strength_status is not ClaimVocabularyAxisStatus.CANDIDATE:
            raise ValueError("evidence_strength requires candidate status when present")
        return self


class GraphPriorBundle(ArtifactMinimalityMixin):
    """Contract passed from discovery into Layer B planning."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.ROUTING,
            ArtifactFunction.PROMOTION_GATING,
        )
    )
    high_confidence_edges: list[PriorEdge] = Field(default_factory=list)
    disputed_edges: list[DisputedEdge] = Field(default_factory=list)
    forbidden_edges: list[PriorEdge] = Field(default_factory=list)
    required_edges: list[PriorEdge] = Field(default_factory=list)
    equivalence_class_summary: dict[str, Any] = Field(default_factory=dict)
    downstream_utility_scores: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_required_edge_provenance(self) -> GraphPriorBundle:
        for edge in self.required_edges:
            if not edge.provenance_refs:
                raise ValueError(f"required_edge '{edge.edge_key}' must carry provenance_refs")
        return self


class PriorKnowledgeBundle(ArtifactMinimalityMixin):
    """Academic/literature prior support narrowed by discovery priors."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.1", pattern=r"^\d+\.\d+$")
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.ROUTING,
            ArtifactFunction.REPLAY_AUDIT,
        )
    )
    status: str = Field(default="ok", min_length=1)
    support_mode: str = Field(default="academic_hybrid", min_length=1)
    query_edge_keys: list[str] = Field(default_factory=list)
    support_rows: list[PriorKnowledgeSupport] = Field(default_factory=list)
    unresolved_edges: list[str] = Field(default_factory=list)
    skg_version_id: int | None = Field(default=None, ge=0)
    skg_snapshot_ref: str | None = None
    provenance_refs: list[str] = Field(default_factory=list)
    source_statuses: dict[str, EvidenceSourceStatus] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphPriorBuilder:
    """Build a GraphPriorBundle from the aggregated edge-confidence matrix."""

    HIGH_CONFIDENCE_THRESHOLD = 0.75
    REQUIRED_PRESENCE_THRESHOLD = 0.85
    REQUIRED_ORIENTATION_THRESHOLD = 0.80
    FORBIDDEN_REVERSE_THRESHOLD = 0.10

    def build(
        self,
        matrix: EdgeConfidenceMatrix,
        utility_report: DownstreamUtilityReport,
    ) -> GraphPriorBundle:
        high_confidence: list[PriorEdge] = []
        required: list[PriorEdge] = []
        disputed: list[DisputedEdge] = []
        forbidden: list[PriorEdge] = []
        warnings: list[str] = []

        for entry in matrix.entries:
            dominant_edge = _prior_edge_from_entry(entry)
            if entry.disputed:
                disputed.append(_disputed_edge_from_entry(entry))
                continue

            if entry.presence_confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
                high_confidence.append(dominant_edge)
            if (
                entry.presence_confidence >= self.REQUIRED_PRESENCE_THRESHOLD
                and entry.orientation_confidence >= self.REQUIRED_ORIENTATION_THRESHOLD
            ):
                if dominant_edge.provenance_refs:
                    required.append(dominant_edge)
                else:
                    warnings.append(
                        f"required_edge_downgraded_without_provenance:{dominant_edge.edge_key}"
                    )
                    high_confidence = _upsert_prior_edge(
                        high_confidence,
                        dominant_edge.model_copy(
                            update={
                                "notes": [
                                    *dominant_edge.notes,
                                    "downgraded_from_required_due_to_missing_provenance",
                                ]
                            }
                        ),
                    )

            reverse_edge = _reverse_prior_edge(entry)
            reverse_support = float(entry.directional_support.get(reverse_edge.edge_key, 0.0))
            if (
                entry.presence_confidence >= self.HIGH_CONFIDENCE_THRESHOLD
                and reverse_support <= self.FORBIDDEN_REVERSE_THRESHOLD
            ):
                forbidden.append(
                    reverse_edge.model_copy(
                        update={
                            "presence_confidence": reverse_support,
                            "orientation_confidence": max(0.0, 1.0 - entry.orientation_confidence),
                            "notes": [
                                "forbidden_by_reverse_consensus",
                                f"reverse_edge_support={reverse_support:.3f}",
                            ],
                        }
                    )
                )

        utility_scores = {
            score.hypothesis_id: float(score.composite_score) for score in utility_report.scores
        }
        return GraphPriorBundle(
            high_confidence_edges=_dedupe_prior_edges(high_confidence),
            disputed_edges=disputed,
            forbidden_edges=_dedupe_prior_edges(forbidden),
            required_edges=_dedupe_prior_edges(required),
            equivalence_class_summary=dict(matrix.metadata.get("equivalence_class_summary") or {}),
            downstream_utility_scores=utility_scores,
            warnings=sorted(set(warnings)),
            metadata={
                "thresholds": {
                    "high_confidence": self.HIGH_CONFIDENCE_THRESHOLD,
                    "required_presence": self.REQUIRED_PRESENCE_THRESHOLD,
                    "required_orientation": self.REQUIRED_ORIENTATION_THRESHOLD,
                    "forbidden_reverse_support": self.FORBIDDEN_REVERSE_THRESHOLD,
                },
                "hypothesis_weights": dict(matrix.hypothesis_weights),
            },
        )


def persist_graph_prior_bundle(
    store: FileSystemCAS,
    bundle: GraphPriorBundle,
    *,
    inputs: list[InputRef] | None = None,
) -> GraphPriorBundleRef:
    """Persist the graph-prior bundle assembled before discovery execution begins."""
    ref = store.put_json(
        bundle,
        PutOptions(
            kind="scientist.graph_prior_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name=GRAPH_PRIOR_BUNDLE_SCHEMA_NAME,
                version=bundle.schema_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return GraphPriorBundleRef.model_validate(ref.model_dump(mode="json"))


def load_graph_prior_bundle(
    store: FileSystemCAS,
    ref: GraphPriorBundleRef,
) -> GraphPriorBundle:
    """Load graph prior bundle."""
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return GraphPriorBundle.model_validate(payload)


def persist_prior_knowledge_bundle(
    store: FileSystemCAS,
    bundle: PriorKnowledgeBundle,
    *,
    inputs: list[InputRef] | None = None,
) -> PriorKnowledgeBundleRef:
    """Persist the prior-knowledge bundle used to seed discovery reasoning and retrieval."""
    ref = store.put_json(
        bundle,
        PutOptions(
            kind="scientist.prior_knowledge_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name=PRIOR_KNOWLEDGE_BUNDLE_SCHEMA_NAME,
                version=bundle.schema_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return PriorKnowledgeBundleRef.model_validate(ref.model_dump(mode="json"))


def load_prior_knowledge_bundle(
    store: FileSystemCAS,
    ref: PriorKnowledgeBundleRef,
) -> PriorKnowledgeBundle:
    """Load prior knowledge bundle."""
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return PriorKnowledgeBundle.model_validate(payload)


def _prior_edge_from_entry(entry: EdgeConfidenceEntry) -> PriorEdge:
    return PriorEdge(
        edge_key=entry.edge_key,
        src=entry.src,
        dst=entry.dst,
        lag=entry.lag,
        presence_confidence=entry.presence_confidence,
        orientation_confidence=entry.orientation_confidence,
        provenance_refs=entry.provenance_refs,
        supporting_hypothesis_ids=entry.supporting_hypothesis_ids,
        supporting_families=entry.supporting_families,
    )


def _disputed_edge_from_entry(entry: EdgeConfidenceEntry) -> DisputedEdge:
    candidate_edges = [
        PriorEdge(
            edge_key=edge_key,
            src=src,
            dst=dst,
            lag=lag,
            presence_confidence=float(entry.presence_confidence * support),
            orientation_confidence=float(support),
            provenance_refs=entry.provenance_refs,
            supporting_hypothesis_ids=entry.supporting_hypothesis_ids,
            supporting_families=entry.supporting_families,
            notes=["candidate_from_disputed_edge"],
        )
        for edge_key, support in sorted(
            entry.directional_support.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        for src, dst, lag in [_parse_edge_key(edge_key)]
    ]
    return DisputedEdge(
        dispute_id=f"dispute:{entry.skeleton_key}",
        skeleton_key=entry.skeleton_key,
        candidate_edges=candidate_edges,
        dispute_reasons=entry.dispute_reasons,
        provenance_refs=entry.provenance_refs,
    )


def _reverse_prior_edge(entry: EdgeConfidenceEntry) -> PriorEdge:
    reverse_key = _reverse_edge_key(entry.edge_key)
    src, dst, lag = _parse_edge_key(reverse_key)
    return PriorEdge(
        edge_key=reverse_key,
        src=src,
        dst=dst,
        lag=lag,
        presence_confidence=0.0,
        orientation_confidence=0.0,
        provenance_refs=entry.provenance_refs,
        supporting_hypothesis_ids=entry.supporting_hypothesis_ids,
        supporting_families=entry.supporting_families,
    )


def _reverse_edge_key(edge_key: str) -> str:
    src, dst, lag = _parse_edge_key(edge_key)
    reversed_key = f"{dst}->{src}"
    if lag is not None:
        reversed_key = f"{reversed_key}@lag={lag}"
    return reversed_key


def _parse_edge_key(edge_key: str) -> tuple[str, str, int | None]:
    base, _, lag_token = edge_key.partition("@lag=")
    src, _, dst = base.partition("->")
    lag = int(lag_token) if lag_token else None
    return src, dst, lag


def _dedupe_prior_edges(edges: list[PriorEdge]) -> list[PriorEdge]:
    deduped: dict[str, PriorEdge] = {}
    for edge in edges:
        existing = deduped.get(edge.edge_key)
        if existing is None or (
            edge.presence_confidence,
            edge.orientation_confidence,
            len(edge.provenance_refs),
        ) > (
            existing.presence_confidence,
            existing.orientation_confidence,
            len(existing.provenance_refs),
        ):
            deduped[edge.edge_key] = edge
    return [deduped[key] for key in sorted(deduped)]


def _upsert_prior_edge(edges: list[PriorEdge], edge: PriorEdge) -> list[PriorEdge]:
    return _dedupe_prior_edges([*edges, edge])


__all__ = [
    "GRAPH_PRIOR_BUNDLE_SCHEMA_NAME",
    "PRIOR_KNOWLEDGE_BUNDLE_SCHEMA_NAME",
    "DisputedEdge",
    "GraphPriorBuilder",
    "GraphPriorBundle",
    "PriorEdge",
    "PriorKnowledgeBundle",
    "PriorKnowledgeSupport",
    "load_graph_prior_bundle",
    "load_prior_knowledge_bundle",
    "persist_graph_prior_bundle",
    "persist_prior_knowledge_bundle",
]
