"""Evidence-weighted aggregation over discovery hypotheses."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.scientist import EdgeConfidenceMatrixRef
from polisyos.scientist.methods.discovery.schema import (
    DiscoveryAlgorithmFamily,
    GraphHypothesis,
    edge_key_for_edge,
    orientation_key_for_edge,
    skeleton_key_for_edge,
)
from polisyos.scientist.methods.discovery.stability import BootstrapStabilityReport
from polisyos.scientist.methods.discovery.utility_judge import DownstreamUtilityReport
from polisyos.scientist.methods.search.artifact_minimality import (
    ArtifactFunction,
    ArtifactMinimalityMixin,
    artifact_functions_field,
)

EDGE_CONFIDENCE_MATRIX_SCHEMA_NAME = "polisyos.scientist.methods.discovery.EdgeConfidenceMatrix"


class EvidenceWeightedAggregatorConfig(BaseModel):
    """Deterministic thresholds for evidence-weighted discovery aggregation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_utility_floor: float = Field(default=0.05, ge=0.0, le=1.0)
    middling_presence_low: float = Field(default=0.40, ge=0.0, le=1.0)
    middling_presence_high: float = Field(default=0.75, ge=0.0, le=1.0)
    competing_direction_support: float = Field(default=0.25, ge=0.0, le=1.0)
    orientation_margin_threshold: float = Field(default=0.15, ge=0.0, le=1.0)


class AggregatedEdgeEvidence(BaseModel):
    """Intermediate weighted evidence before the persisted matrix view."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    skeleton_key: str = Field(min_length=1)
    total_active_mass: float = Field(ge=0.0)
    weighted_presence_support: float = Field(ge=0.0)
    directional_support_mass: dict[str, float] = Field(default_factory=dict)
    orientation_support_mass: dict[str, float] = Field(default_factory=dict)
    contributing_hypothesis_ids: list[str] = Field(default_factory=list)
    contributing_families: list[str] = Field(default_factory=list)
    provenance_refs: list[str] = Field(default_factory=list)
    mean_edge_stability: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EdgeConfidenceEntry(BaseModel):
    """One edge-level row in the aggregated discovery confidence matrix."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    skeleton_key: str = Field(min_length=1)
    edge_key: str = Field(min_length=1)
    src: str = Field(min_length=1)
    dst: str = Field(min_length=1)
    lag: int | None = Field(default=None, ge=0)
    presence_confidence: float = Field(ge=0.0, le=1.0)
    orientation_confidence: float = Field(ge=0.0, le=1.0)
    directional_support: dict[str, float] = Field(default_factory=dict)
    orientation_support: dict[str, float] = Field(default_factory=dict)
    supporting_hypothesis_ids: list[str] = Field(default_factory=list)
    supporting_families: list[str] = Field(default_factory=list)
    provenance_refs: list[str] = Field(default_factory=list)
    disputed: bool = False
    dispute_reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EdgeConfidenceMatrix(ArtifactMinimalityMixin):
    """Persisted aggregated edge-confidence surface for Phase C."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.ROUTING,
            ArtifactFunction.CROSS_RUN_LEARNING,
        )
    )
    entries: list[EdgeConfidenceEntry] = Field(default_factory=list)
    hypothesis_weights: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def entry_for_key(self, edge_key: str) -> EdgeConfidenceEntry | None:
        for entry in self.entries:
            if entry.edge_key == edge_key:
                return entry
        return None


@dataclass
class _AggregationBucket:
    weighted_presence_support: float = 0.0
    directional_support_mass: defaultdict[str, float] = field(
        default_factory=lambda: defaultdict(float)
    )
    orientation_support_mass: defaultdict[str, float] = field(
        default_factory=lambda: defaultdict(float)
    )
    supporting_hypothesis_ids: set[str] = field(default_factory=set)
    supporting_families: set[str] = field(default_factory=set)
    provenance_refs: set[str] = field(default_factory=set)
    stability_values: list[float] = field(default_factory=list)
    graph_types: set[str] = field(default_factory=set)


class EvidenceWeightedAggregator:
    """Aggregate discovery hypotheses using utility-weighted evidence."""

    def __init__(
        self,
        *,
        config: EvidenceWeightedAggregatorConfig | None = None,
    ) -> None:
        self._config = config or EvidenceWeightedAggregatorConfig()

    @property
    def config(self) -> EvidenceWeightedAggregatorConfig:
        return self._config

    def aggregate(
        self,
        hypotheses: list[GraphHypothesis],
        stability_report: BootstrapStabilityReport,
        utility_report: DownstreamUtilityReport,
    ) -> EdgeConfidenceMatrix:
        hypothesis_weights = _compute_hypothesis_weights(
            hypotheses,
            utility_report,
            config=self._config,
        )
        total_active_mass = float(sum(hypothesis_weights.values()))
        grouped: defaultdict[str, _AggregationBucket] = defaultdict(_AggregationBucket)

        for hypothesis in hypotheses:
            weight = hypothesis_weights.get(hypothesis.hypothesis_id, 0.0)
            if weight <= 0.0:
                continue
            summary = stability_report.summary_for(hypothesis.hypothesis_id)
            edge_selection_frequency = (
                {} if summary is None else dict(getattr(summary, "edge_selection_frequency", {}))
            )
            for edge in hypothesis.graph.edges:
                edge_key = edge_key_for_edge(edge)
                skeleton_key = skeleton_key_for_edge(edge)
                orientation_key = orientation_key_for_edge(edge)
                edge_reliability = _edge_reliability(hypothesis, summary, edge_key)
                contribution = weight * edge_reliability
                if contribution <= 0.0:
                    continue
                bucket = grouped[skeleton_key]
                bucket.weighted_presence_support += contribution
                bucket.directional_support_mass[edge_key] += contribution
                bucket.orientation_support_mass[orientation_key] += contribution
                bucket.supporting_hypothesis_ids.add(hypothesis.hypothesis_id)
                bucket.supporting_families.add(hypothesis.algorithm_family.value)
                bucket.provenance_refs.update(edge.evidence_refs)
                bucket.graph_types.add(getattr(hypothesis.graph.graph_type, "value", "unknown"))
                if edge_key in edge_selection_frequency:
                    bucket.stability_values.append(edge_selection_frequency[edge_key])

        entries: list[EdgeConfidenceEntry] = []
        unresolved_disputes: list[str] = []
        for skeleton_key, bucket in grouped.items():
            evidence = AggregatedEdgeEvidence(
                skeleton_key=skeleton_key,
                total_active_mass=total_active_mass,
                weighted_presence_support=float(bucket.weighted_presence_support),
                directional_support_mass={
                    key: float(value) for key, value in bucket.directional_support_mass.items()
                },
                orientation_support_mass={
                    key: float(value) for key, value in bucket.orientation_support_mass.items()
                },
                contributing_hypothesis_ids=sorted(bucket.supporting_hypothesis_ids),
                contributing_families=sorted(bucket.supporting_families),
                provenance_refs=sorted(bucket.provenance_refs),
                mean_edge_stability=_mean_or_none(bucket.stability_values),
                metadata={
                    "graph_types": sorted(bucket.graph_types),
                },
            )
            entry = _entry_from_evidence(evidence, config=self._config)
            if entry.disputed:
                unresolved_disputes.append(entry.edge_key)
            entries.append(entry)

        entries.sort(
            key=lambda item: (
                item.presence_confidence,
                item.orientation_confidence,
                item.edge_key,
            ),
            reverse=True,
        )
        graph_type_summary: dict[str, int] = defaultdict(int)
        for hypothesis in hypotheses:
            graph_type_summary[getattr(hypothesis.graph.graph_type, "value", "unknown")] += 1
        metadata = {
            "equivalence_class_summary": {
                "graph_type_counts": dict(sorted(graph_type_summary.items())),
                "unresolved_disputes": unresolved_disputes,
                "n_entries": len(entries),
            },
            "n_hypotheses": len(hypotheses),
            "n_weighted_hypotheses": len(
                [value for value in hypothesis_weights.values() if value > 0.0]
            ),
        }
        return EdgeConfidenceMatrix(
            entries=entries,
            hypothesis_weights=hypothesis_weights,
            metadata=metadata,
        )


def persist_edge_confidence_matrix(
    store: FileSystemCAS,
    matrix: EdgeConfidenceMatrix,
    *,
    inputs: list[InputRef] | None = None,
) -> EdgeConfidenceMatrixRef:
    """Persist the edge-confidence matrix used to summarize support across discovery hypotheses."""
    ref = store.put_json(
        matrix,
        PutOptions(
            kind="scientist.edge_confidence_matrix",
            media_type="application/json",
            schema=SchemaInfo(
                name=EDGE_CONFIDENCE_MATRIX_SCHEMA_NAME,
                version=matrix.schema_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return EdgeConfidenceMatrixRef.model_validate(ref.model_dump(mode="json"))


def load_edge_confidence_matrix(
    store: FileSystemCAS,
    ref: EdgeConfidenceMatrixRef,
) -> EdgeConfidenceMatrix:
    """Load edge confidence matrix."""
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return EdgeConfidenceMatrix.model_validate(payload)


def _compute_hypothesis_weights(
    hypotheses: list[GraphHypothesis],
    utility_report: DownstreamUtilityReport,
    *,
    config: EvidenceWeightedAggregatorConfig,
) -> dict[str, float]:
    utility_by_hypothesis = {
        score.hypothesis_id: float(score.composite_score) for score in utility_report.scores
    }
    active_by_family: dict[DiscoveryAlgorithmFamily, list[GraphHypothesis]] = defaultdict(list)
    for hypothesis in hypotheses:
        if _is_active_candidate(hypothesis):
            active_by_family[hypothesis.algorithm_family].append(hypothesis)
    if not active_by_family:
        return {}

    family_share = 1.0 / float(len(active_by_family))
    weights: dict[str, float] = {}
    for family, family_hypotheses in active_by_family.items():
        del family  # family is captured by the grouping, but not needed below.
        family_utilities = [
            max(config.min_utility_floor, utility_by_hypothesis.get(item.hypothesis_id, 0.0))
            for item in family_hypotheses
        ]
        family_total = sum(family_utilities)
        for hypothesis, utility in zip(family_hypotheses, family_utilities, strict=False):
            if family_total <= 0.0:
                weights[hypothesis.hypothesis_id] = family_share / float(len(family_hypotheses))
            else:
                weights[hypothesis.hypothesis_id] = family_share * (utility / family_total)
    return weights


def _is_active_candidate(hypothesis: GraphHypothesis) -> bool:
    if hypothesis.graph.edges:
        return True
    if hypothesis.failure_reasons:
        return False
    failure_warning_markers = ("algorithm_failed", "timeout", "unsupported", "executor_failed")
    return not any(
        marker in warning.lower()
        for marker in failure_warning_markers
        for warning in hypothesis.warnings
    )


def _edge_reliability(
    hypothesis: GraphHypothesis,
    summary: Any,
    edge_key: str,
) -> float:
    if summary is not None and edge_key in getattr(summary, "edge_selection_frequency", {}):
        return float(summary.edge_selection_frequency[edge_key])
    return float(hypothesis.edge_confidence.get(edge_key, 0.5))


def _entry_from_evidence(
    evidence: AggregatedEdgeEvidence,
    *,
    config: EvidenceWeightedAggregatorConfig,
) -> EdgeConfidenceEntry:
    presence_confidence = (
        evidence.weighted_presence_support / evidence.total_active_mass
        if evidence.total_active_mass > 0.0
        else 0.0
    )
    dominant_direction = _top_item(evidence.directional_support_mass)
    dominant_orientation = _top_item(evidence.orientation_support_mass)
    if dominant_direction is None:
        edge_key = evidence.skeleton_key.replace("--", "->")
        src, dst, lag = _parse_edge_key(edge_key)
        directional_support: dict[str, float] = {}
        orientation_support: dict[str, float] = {}
        orientation_confidence = 0.0
    else:
        edge_key, dominant_direction_mass = dominant_direction
        src, dst, lag = _parse_edge_key(edge_key)
        directional_support = _normalize_support(
            evidence.directional_support_mass,
            denominator=evidence.weighted_presence_support,
        )
        orientation_support = _normalize_support(
            evidence.orientation_support_mass,
            denominator=evidence.weighted_presence_support,
        )
        orientation_confidence = (
            float(dominant_orientation[1] / evidence.weighted_presence_support)
            if dominant_orientation is not None and evidence.weighted_presence_support > 0.0
            else 0.0
        )
        del dominant_direction_mass

    dispute_reasons = _dispute_reasons(
        directional_support=directional_support,
        presence_confidence=float(presence_confidence),
        orientation_confidence=float(orientation_confidence),
        config=config,
    )
    return EdgeConfidenceEntry(
        skeleton_key=evidence.skeleton_key,
        edge_key=edge_key,
        src=src,
        dst=dst,
        lag=lag,
        presence_confidence=float(presence_confidence),
        orientation_confidence=float(orientation_confidence),
        directional_support=directional_support,
        orientation_support=orientation_support,
        supporting_hypothesis_ids=evidence.contributing_hypothesis_ids,
        supporting_families=evidence.contributing_families,
        provenance_refs=evidence.provenance_refs,
        disputed=bool(dispute_reasons),
        dispute_reasons=dispute_reasons,
        metadata={
            **evidence.metadata,
            "mean_edge_stability": evidence.mean_edge_stability,
        },
    )


def _dispute_reasons(
    *,
    directional_support: dict[str, float],
    presence_confidence: float,
    orientation_confidence: float,
    config: EvidenceWeightedAggregatorConfig,
) -> list[str]:
    reasons: list[str] = []
    if config.middling_presence_low <= presence_confidence < config.middling_presence_high:
        reasons.append("middling_presence_confidence")
    top_two = sorted(directional_support.items(), key=lambda item: item[1], reverse=True)[:2]
    if len(top_two) >= 2:
        if top_two[1][1] >= config.competing_direction_support:
            reasons.append("competing_direction_support")
        if (top_two[0][1] - top_two[1][1]) < config.orientation_margin_threshold:
            reasons.append("small_orientation_margin")
    if orientation_confidence < config.middling_presence_high and directional_support:
        reasons.append("orientation_unresolved")
    return sorted(set(reasons))


def _normalize_support(
    mass: dict[str, float],
    *,
    denominator: float,
) -> dict[str, float]:
    if denominator <= 0.0:
        return {}
    return {key: float(value / denominator) for key, value in sorted(mass.items())}


def _top_item(mapping: dict[str, float]) -> tuple[str, float] | None:
    if not mapping:
        return None
    return max(mapping.items(), key=lambda item: (item[1], item[0]))


def _parse_edge_key(edge_key: str) -> tuple[str, str, int | None]:
    base, _, lag_token = edge_key.partition("@lag=")
    src, _, dst = base.partition("->")
    lag = int(lag_token) if lag_token else None
    return src, dst, lag


def _mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


__all__ = [
    "EDGE_CONFIDENCE_MATRIX_SCHEMA_NAME",
    "AggregatedEdgeEvidence",
    "EdgeConfidenceEntry",
    "EdgeConfidenceMatrix",
    "EvidenceWeightedAggregator",
    "EvidenceWeightedAggregatorConfig",
    "load_edge_confidence_matrix",
    "persist_edge_confidence_matrix",
]
