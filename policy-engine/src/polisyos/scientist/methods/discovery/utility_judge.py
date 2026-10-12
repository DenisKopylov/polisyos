"""Downstream causal-utility scoring for discovery hypotheses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.scientist import DownstreamUtilityReportRef
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.foundry.methods.catalog.causal.id_engine import (
    IdentificationResult,
    IdentificationStatus,
)
from polisyos.foundry.methods.catalog.causal.transport_engine import solve_transportability
from polisyos.ir.analytics.causal import CausalEffectReport, EstimationStatus
from polisyos.ir.analytics.causal_discovery import (
    AlgebraicAssumptionStatus,
    AlgebraicFalsificationScope,
)
from polisyos.ir.analytics.causal_queries import CausalQuery
from polisyos.ir.analytics.negative_certificate import NegativeCertificate
from polisyos.ir.analytics.transportability import SelectionDiagram, SNode, TransportabilityStatus
from polisyos.scientist.methods.discovery.artifact_refs import profile_bound_written_ref
from polisyos.scientist.methods.discovery.schema import (
    GraphHypothesis,
    edge_key_for_edge,
    orientation_key_for_edge,
    skeleton_key_for_edge,
)
from polisyos.scientist.methods.discovery.stability import BootstrapStabilityReport
from polisyos.scientist.methods.search.artifact_minimality import (
    ArtifactFunction,
    ArtifactMinimalityMixin,
    artifact_functions_field,
)

DOWNSTREAM_UTILITY_REPORT_SCHEMA_NAME = (
    "polisyos.scientist.methods.discovery.DownstreamUtilityReport"
)
IDENTIFICATION_SOURCE_ALGORITHM_VERSION = "causal_engine_identification_projection_v1"
DOWNSTREAM_UTILITY_REPORT_SCHEMA_VERSION = "1.2"
_DOWNSTREAM_UTILITY_REPORT_LEGACY_SCHEMA_VERSION = "1.1"

# The v1.1 scorecard predates the typed graph-diagnostic scope fields. These
# pinned field sets are the historical wire contract; current DTO growth must
# not silently expand what the legacy reader accepts.
_DOWNSTREAM_UTILITY_REPORT_V1_1_FIELDS = frozenset(
    {"schema_version", "artifact_functions", "scores", "recommended_shortlist", "metadata"}
)
_HYPOTHESIS_UTILITY_SCORE_V1_1_FIELDS = frozenset(
    {
        "hypothesis_id",
        "identification_status",
        "identifiability_score",
        "stability_score",
        "transport_status",
        "transportability_score",
        "estimation_quality_score",
        "discovery_consistency_score",
        "algebraic_severity",
        "disputed_edge_count",
        "disputed_edge_fraction",
        "composite_score",
        "rank",
        "reasons",
        "warnings",
        "blocking_certificates",
    }
)


class UtilityJudgeConfig(BaseModel):
    """Fixed-weight utility-judge configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    identifiability_weight: float = Field(default=0.40, ge=0.0)
    stability_weight: float = Field(default=0.25, ge=0.0)
    transportability_weight: float = Field(default=0.15, ge=0.0)
    estimation_quality_weight: float = Field(default=0.10, ge=0.0)
    discovery_consistency_weight: float = Field(default=0.10, ge=0.0)
    non_identified_cap: float = Field(default=0.25, ge=0.0, le=1.0)
    partial_identified_cap: float = Field(default=0.60, ge=0.0, le=1.0)
    shortlist_size: int = Field(default=3, ge=1)


class UtilityJudgeInput(BaseModel):
    """Inputs needed to rank graph hypotheses by downstream usefulness."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    hypotheses: list[GraphHypothesis] = Field(default_factory=list)
    stability_report: BootstrapStabilityReport
    causal_query: CausalQuery
    selection_diagram: SelectionDiagram | None = None
    s_nodes: list[SNode] = Field(default_factory=list)
    benchmark_reports: dict[str, CausalEffectReport] = Field(default_factory=dict)


class HypothesisUtilityScore(BaseModel):
    """Per-hypothesis downstream utility scorecard."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hypothesis_id: str = Field(min_length=1)
    identification_status: str = Field(min_length=1)
    identifiability_score: float = Field(ge=0.0, le=1.0)
    stability_score: float = Field(ge=0.0, le=1.0)
    transport_status: str | None = None
    transportability_score: float | None = Field(default=None, ge=0.0, le=1.0)
    estimation_quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    discovery_consistency_score: float | None = Field(default=None, ge=0.0, le=1.0)
    algebraic_severity: str | None = None
    graph_derived_assumption_status: AlgebraicAssumptionStatus | None = None
    graph_derived_scope_of_falsification: AlgebraicFalsificationScope | None = None
    disputed_edge_count: int | None = Field(default=None, ge=0)
    disputed_edge_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    composite_score: float = Field(ge=0.0, le=1.0)
    rank: int = Field(default=0, ge=0)
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blocking_certificates: list[str] = Field(default_factory=list)


class DownstreamUtilityReport(ArtifactMinimalityMixin):
    """Persisted utility-judge output over graph hypotheses."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.1", "1.2"] = DOWNSTREAM_UTILITY_REPORT_SCHEMA_VERSION
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.ROUTING,
            ArtifactFunction.PROMOTION_GATING,
        )
    )
    scores: list[HypothesisUtilityScore] = Field(default_factory=list)
    recommended_shortlist: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _limit_historical_scorecards(self) -> DownstreamUtilityReport:
        if self.schema_version == _DOWNSTREAM_UTILITY_REPORT_LEGACY_SCHEMA_VERSION:
            if self.artifact_functions != {ArtifactFunction.ROUTING}:
                raise ValueError("historical downstream utility reports are routing-only")
            if any(
                score.graph_derived_assumption_status is not AlgebraicAssumptionStatus.UNKNOWN
                or score.graph_derived_scope_of_falsification
                is not AlgebraicFalsificationScope.RANKING_ONLY
                for score in self.scores
            ):
                raise ValueError(
                    "historical downstream utility reports require unknown, ranking-only scope"
                )
        return self


def _validate_legacy_v1_1_utility_payload(payload: Any) -> None:
    if type(payload) is not dict:
        raise ValueError("historical downstream utility payload must be an object")
    if set(payload) - _DOWNSTREAM_UTILITY_REPORT_V1_1_FIELDS:
        raise ValueError("historical downstream utility payload has non-v1.1 fields")
    scores = payload.get("scores", [])
    if type(scores) is not list:
        raise ValueError("historical downstream utility scores must be a list")
    for score in scores:
        if type(score) is not dict:
            raise ValueError("historical downstream utility score must be an object")
        if set(score) - _HYPOTHESIS_UTILITY_SCORE_V1_1_FIELDS:
            raise ValueError("historical downstream utility score has non-v1.1 fields")


def _validate_current_v1_2_utility_payload(payload: Any) -> None:
    if type(payload) is not dict:
        raise ValueError("current downstream utility payload must be an object")
    scores = payload.get("scores", [])
    if type(scores) is not list:
        raise ValueError("current downstream utility scores must be a list")
    required_scope_fields = {
        "graph_derived_assumption_status",
        "graph_derived_scope_of_falsification",
    }
    for score in scores:
        if type(score) is not dict or not required_scope_fields.issubset(score):
            raise ValueError("current downstream utility score is missing v1.2 scope fields")


def _validate_downstream_utility_artifact_binding(
    ref: DownstreamUtilityReportRef,
    manifest: Any,
    payload: Any,
) -> str:
    """Bind report bytes to the exact report manifest and historical/current wire schema."""
    if ref.manifest_profile_sha256 is None:
        raise ValueError("downstream utility report manifest profile is missing")
    if (
        manifest.artifact_id != ref.artifact_id
        or manifest.kind != ref.kind
        or manifest.kind != "scientist.downstream_utility_report"
        or manifest.media_type != ref.media_type
        or manifest.media_type != "application/json"
    ):
        raise ValueError("downstream utility report manifest identity mismatch")
    schema = manifest.artifact_schema
    if schema is None or schema.name != DOWNSTREAM_UTILITY_REPORT_SCHEMA_NAME:
        raise ValueError("downstream utility report manifest schema is missing or invalid")
    if type(payload) is not dict:
        raise ValueError("downstream utility report payload must be an object")
    payload_version = payload.get("schema_version")
    if payload_version != schema.version:
        raise ValueError("downstream utility report manifest/payload schema mismatch")
    if schema.version == DOWNSTREAM_UTILITY_REPORT_SCHEMA_VERSION:
        _validate_current_v1_2_utility_payload(payload)
        return DOWNSTREAM_UTILITY_REPORT_SCHEMA_VERSION
    if schema.version == _DOWNSTREAM_UTILITY_REPORT_LEGACY_SCHEMA_VERSION:
        _validate_legacy_v1_1_utility_payload(payload)
        return _DOWNSTREAM_UTILITY_REPORT_LEGACY_SCHEMA_VERSION
    raise ValueError("unsupported downstream utility report manifest schema version")


def _adapt_historical_v1_1_utility_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Limit exact historical scorecards to candidate ranking with unknown scope."""
    adapted = dict(payload)
    adapted["artifact_functions"] = [ArtifactFunction.ROUTING.value]
    adapted_scores: list[dict[str, Any]] = []
    for raw_score in payload.get("scores", []):
        score = dict(raw_score)
        score["graph_derived_assumption_status"] = AlgebraicAssumptionStatus.UNKNOWN.value
        score["graph_derived_scope_of_falsification"] = (
            AlgebraicFalsificationScope.RANKING_ONLY.value
        )
        adapted_scores.append(score)
    adapted["scores"] = adapted_scores
    return adapted


def _revalidate_current_downstream_utility_report(
    report: DownstreamUtilityReport,
) -> DownstreamUtilityReport:
    """Rebuild a writer payload from actual declared fields before CAS mutation."""
    if type(report) is not DownstreamUtilityReport:
        raise ValueError("downstream utility persistence requires the canonical model type")
    stored = object.__getattribute__(report, "__dict__")
    field_names = set(DownstreamUtilityReport.model_fields)
    if type(stored) is not dict or set(stored) != field_names:
        raise ValueError("downstream utility report has undeclared or missing stored fields")
    payload = {name: stored[name] for name in DownstreamUtilityReport.model_fields}
    if payload["schema_version"] != DOWNSTREAM_UTILITY_REPORT_SCHEMA_VERSION:
        raise ValueError("downstream utility writer requires schema version 1.2")
    scores = payload["scores"]
    if type(scores) is not list:
        raise ValueError("downstream utility report scores must be a list")
    rebuilt_scores: list[dict[str, Any]] = []
    score_fields = set(HypothesisUtilityScore.model_fields)
    for score in scores:
        if type(score) is not HypothesisUtilityScore:
            raise ValueError("downstream utility score requires the canonical model type")
        score_stored = object.__getattribute__(score, "__dict__")
        if type(score_stored) is not dict or set(score_stored) != score_fields:
            raise ValueError("downstream utility score has undeclared or missing stored fields")
        rebuilt_scores.append(
            {name: score_stored[name] for name in HypothesisUtilityScore.model_fields}
        )
    payload["scores"] = rebuilt_scores
    try:
        return DownstreamUtilityReport.model_validate(payload)
    except (TypeError, ValueError) as exc:
        raise ValueError("downstream utility report failed current schema validation") from exc


class DownstreamUtilityJudge:
    """Deterministic downstream-utility judge for graph discovery."""

    def __init__(
        self,
        *,
        config: UtilityJudgeConfig | None = None,
    ) -> None:
        self._config = config or UtilityJudgeConfig()

    @property
    def config(self) -> UtilityJudgeConfig:
        return self._config

    def evaluate(self, bundle: UtilityJudgeInput) -> DownstreamUtilityReport:
        dispute_stats = _disputed_edge_stats(bundle.hypotheses)
        scores: list[HypothesisUtilityScore] = []
        for hypothesis in bundle.hypotheses:
            scores.append(
                self._score_hypothesis(
                    hypothesis,
                    bundle,
                    dispute_stats=dispute_stats.get(
                        hypothesis.hypothesis_id,
                        _HypothesisDisputeStats(),
                    ),
                )
            )

        scores.sort(
            key=lambda item: (
                item.composite_score,
                item.discovery_consistency_score or 0.0,
                item.identifiability_score,
                item.stability_score,
            ),
            reverse=True,
        )
        ranked = [item.model_copy(update={"rank": index + 1}) for index, item in enumerate(scores)]
        shortlist, shortlist_exclusions = _build_shortlist(
            ranked,
            size=self._config.shortlist_size,
        )
        channel_coverage = {
            "identifiability": True,
            "stability": True,
            "transportability": bundle.selection_diagram is not None or bool(bundle.s_nodes),
            "benchmark": bool(bundle.benchmark_reports),
            "discovery_consistency": bool(bundle.hypotheses),
        }
        return DownstreamUtilityReport(
            scores=ranked,
            recommended_shortlist=shortlist,
            metadata={
                "n_hypotheses": len(bundle.hypotheses),
                "transport_context_present": bundle.selection_diagram is not None
                or bool(bundle.s_nodes),
                "benchmark_reports_present": bool(bundle.benchmark_reports),
                "channel_coverage": channel_coverage,
                "identification_source_algorithm_version": IDENTIFICATION_SOURCE_ALGORITHM_VERSION,
                "algebraic_summary": _algebraic_summary(ranked),
                "dispute_summary": _dispute_summary(ranked, dispute_stats),
                "shortlist_exclusions": shortlist_exclusions,
            },
        )

    def _score_hypothesis(
        self,
        hypothesis: GraphHypothesis,
        bundle: UtilityJudgeInput,
        *,
        dispute_stats: _HypothesisDisputeStats,
    ) -> HypothesisUtilityScore:
        identification = identify_hypothesis_identification_status(
            hypothesis,
            bundle.causal_query,
        )
        ident_score = identification.identifiability_score
        ident_status = identification.identification_status
        ident_reasons = list(identification.reasons)
        ident_warnings = list(identification.warnings)
        blocking = list(identification.blocking_certificates)
        algebraic_severity, algebraic_consistency = _algebraic_consistency(hypothesis)
        graph_assumption_status, graph_falsification_scope = (
            graph_derived_candidate_scope(hypothesis)
        )
        graph_derived = graph_assumption_status is not None
        dispute_consistency = max(0.0, min(1.0, 1.0 - dispute_stats.disputed_edge_fraction))
        discovery_consistency_score = float(
            max(0.0, min(1.0, (0.7 * algebraic_consistency) + (0.3 * dispute_consistency)))
        )
        summary = bundle.stability_report.summary_for(hypothesis.hypothesis_id)
        stability_score = _score_stability(summary)
        reasons = list(ident_reasons)
        warnings = list(ident_warnings)
        reasons.append(f"discovery_consistency:{discovery_consistency_score:.3f}")
        if graph_derived:
            reasons.append("graph_derived_diagnostics:unknown_assumptions;ranking_only")
            warnings.append(
                "Graph-derived diagnostics remain candidate-ranking-only; source completeness, "
                "population, temporal scope, selection, and the Markov assumption are unknown."
            )
        if algebraic_severity is not None:
            reasons.append(f"algebraic_severity:{algebraic_severity}")
        if dispute_stats.disputed_edge_count:
            reasons.append(
                f"disputed_edges:{dispute_stats.disputed_edge_count}/{dispute_stats.total_edge_count}"
            )
        if summary is None:
            reasons.append("stability:missing_bootstrap_summary")
            warnings.append("No bootstrap stability summary available for hypothesis.")
        else:
            reasons.append(f"stability:{stability_score:.3f}")
            warnings.extend(summary.warnings)

        transport_score: float | None = None
        transport_status: str | None = None
        if bundle.selection_diagram is not None or bundle.s_nodes:
            transport_score, transport_status, transport_reasons, transport_warnings = (
                _score_transportability(
                    hypothesis,
                    bundle.causal_query,
                    selection_diagram=bundle.selection_diagram,
                    s_nodes=bundle.s_nodes,
                )
            )
            reasons.extend(transport_reasons)
            warnings.extend(transport_warnings)

        estimation_score: float | None = None
        benchmark_report = bundle.benchmark_reports.get(hypothesis.hypothesis_id)
        if benchmark_report is not None:
            estimation_score, estimation_reasons = _score_estimation_quality(benchmark_report)
            reasons.extend(estimation_reasons)

        components: list[tuple[float, float]] = [
            (ident_score, self._config.identifiability_weight),
            (stability_score, self._config.stability_weight),
            (discovery_consistency_score, self._config.discovery_consistency_weight),
        ]
        if transport_score is not None:
            components.append((transport_score, self._config.transportability_weight))
        if estimation_score is not None:
            components.append((estimation_score, self._config.estimation_quality_weight))
        total_weight = sum(weight for _, weight in components) or 1.0
        composite = sum(score * weight for score, weight in components) / total_weight
        if ident_score <= 0.0:
            composite = min(composite, self._config.non_identified_cap)
        elif ident_score < 1.0:
            composite = min(composite, self._config.partial_identified_cap)

        return HypothesisUtilityScore(
            hypothesis_id=hypothesis.hypothesis_id,
            identification_status=ident_status,
            identifiability_score=ident_score,
            stability_score=stability_score,
            transport_status=transport_status,
            transportability_score=transport_score,
            estimation_quality_score=estimation_score,
            discovery_consistency_score=discovery_consistency_score,
            algebraic_severity=algebraic_severity,
            graph_derived_assumption_status=graph_assumption_status,
            graph_derived_scope_of_falsification=graph_falsification_scope,
            disputed_edge_count=dispute_stats.disputed_edge_count,
            disputed_edge_fraction=dispute_stats.disputed_edge_fraction,
            composite_score=float(composite),
            reasons=reasons,
            warnings=warnings,
            blocking_certificates=blocking,
        )


def persist_downstream_utility_report(
    store: FileSystemCAS,
    report: DownstreamUtilityReport,
    *,
    inputs: list[InputRef] | None = None,
) -> DownstreamUtilityReportRef:
    """Persist the downstream-utility report that ranks hypotheses by decision usefulness."""
    current_report = _revalidate_current_downstream_utility_report(report)
    ref = store.put_json(
        current_report,
        PutOptions(
            kind="scientist.downstream_utility_report",
            media_type="application/json",
            schema=SchemaInfo(
                name=DOWNSTREAM_UTILITY_REPORT_SCHEMA_NAME,
                version=DOWNSTREAM_UTILITY_REPORT_SCHEMA_VERSION,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    typed_ref = DownstreamUtilityReportRef.model_validate(ref.model_dump(mode="json"))
    return profile_bound_written_ref(store, typed_ref)


def load_downstream_utility_report(
    store: FileSystemCAS,
    ref: DownstreamUtilityReportRef,
) -> DownstreamUtilityReport:
    """Load a manifest-bound current report or an exact bounded historical scorecard."""
    manifest = store.get_manifest(ref)
    payload = from_canonical_bytes(store.get_bytes(ref))
    stored_version = _validate_downstream_utility_artifact_binding(
        ref, manifest, payload
    )
    if stored_version == _DOWNSTREAM_UTILITY_REPORT_LEGACY_SCHEMA_VERSION:
        payload = _adapt_historical_v1_1_utility_payload(payload)
    report = DownstreamUtilityReport.model_validate(payload)
    if report.schema_version != stored_version:
        raise ValueError("downstream utility report did not retain its manifest-bound version")
    return report


@dataclass(frozen=True)
class _HypothesisDisputeStats:
    disputed_edge_count: int = 0
    total_edge_count: int = 0
    disputed_edge_fraction: float = 0.0


def _disputed_edge_stats(
    hypotheses: list[GraphHypothesis],
) -> dict[str, _HypothesisDisputeStats]:
    skeleton_support: dict[str, dict[str, set[str]]] = {}
    for hypothesis in hypotheses:
        for edge in hypothesis.graph.edges:
            skeleton_key = skeleton_key_for_edge(edge)
            bucket = skeleton_support.setdefault(
                skeleton_key,
                {"directions": set(), "orientations": set()},
            )
            bucket["directions"].add(edge_key_for_edge(edge))
            bucket["orientations"].add(orientation_key_for_edge(edge))

    disputed_skeletons = {
        key
        for key, support in skeleton_support.items()
        if len(support["directions"]) > 1 or len(support["orientations"]) > 1
    }

    stats: dict[str, _HypothesisDisputeStats] = {}
    for hypothesis in hypotheses:
        total_edge_count = len(hypothesis.graph.edges)
        disputed_edge_count = sum(
            1
            for edge in hypothesis.graph.edges
            if skeleton_key_for_edge(edge) in disputed_skeletons
        )
        fraction = float(disputed_edge_count / total_edge_count) if total_edge_count > 0 else 0.0
        stats[hypothesis.hypothesis_id] = _HypothesisDisputeStats(
            disputed_edge_count=disputed_edge_count,
            total_edge_count=total_edge_count,
            disputed_edge_fraction=max(0.0, min(1.0, fraction)),
        )
    return stats



def graph_derived_candidate_scope(
    hypothesis: GraphHypothesis,
) -> tuple[AlgebraicAssumptionStatus | None, AlgebraicFalsificationScope | None]:
    """Derive candidate-only scope from typed constraint evidence, not labels.

    The score can use the severity summary even when detailed constraints are
    still referenced by CAS rather than hydrated into previews. Any typed family,
    count, preview, or unhydrated constraint reference therefore carries the
    same conservative scope until its source and population assumptions are
    independently established.
    """
    report = hypothesis.algebraic_constraints
    report_has_evidence = False
    if report is not None:
        report_has_evidence = bool(
            report.families_run
            or any(value > 0 for value in report.tested_by_family.values())
            or any(value > 0 for value in report.violated_by_family.values())
            or report.n_implied_constraints
            or report.n_violated_constraints
            or report.implied_constraints_preview
            or report.violated_constraints_preview
            or report.implied_constraints_ref is not None
            or report.violated_constraints_ref is not None
            or report.severity != "info"
        )
    discovery_metadata = hypothesis.metadata.get("discovery_report_metadata")
    metadata_severity = (
        discovery_metadata.get("algebraic_constraint_severity")
        if isinstance(discovery_metadata, dict)
        else None
    )
    metadata_severity = metadata_severity or hypothesis.metadata.get(
        "algebraic_constraint_severity"
    )
    if report_has_evidence or metadata_severity:
        return (
            AlgebraicAssumptionStatus.UNKNOWN,
            AlgebraicFalsificationScope.RANKING_ONLY,
        )
    return None, None

def _algebraic_consistency(
    hypothesis: GraphHypothesis,
) -> tuple[str | None, float]:
    severity = ""
    if hypothesis.algebraic_constraints is not None:
        severity = str(hypothesis.algebraic_constraints.severity or "").strip().lower()
    report_metadata = hypothesis.metadata.get("discovery_report_metadata")
    if not severity and isinstance(report_metadata, dict):
        severity = str(report_metadata.get("algebraic_constraint_severity") or "").strip().lower()
    if not severity:
        direct = str(hypothesis.metadata.get("algebraic_constraint_severity") or "").strip().lower()
        severity = direct
    if severity == "blocker":
        return "blocker", 0.0
    if severity == "warning":
        return "warning", 0.5
    if severity == "info":
        return "info", 1.0
    if hypothesis.method.value in {"pc", "fci", "ges", "dagma"} and (
        hypothesis.source_discovery_report_ref is not None
        or isinstance(report_metadata, dict)
        or "portfolio_method" in hypothesis.metadata
    ):
        return "warning", 0.5
    return None, 1.0


def _algebraic_summary(
    scores: list[HypothesisUtilityScore],
) -> dict[str, Any]:
    severity_counts = {"info_or_missing": 0, "warning": 0, "blocker": 0}
    warning_hypotheses: list[str] = []
    blocker_hypotheses: list[str] = []
    for score in scores:
        if score.algebraic_severity == "blocker":
            severity_counts["blocker"] += 1
            blocker_hypotheses.append(score.hypothesis_id)
        elif score.algebraic_severity == "warning":
            severity_counts["warning"] += 1
            warning_hypotheses.append(score.hypothesis_id)
        else:
            severity_counts["info_or_missing"] += 1
    return {
        "severity_counts": severity_counts,
        "warning_hypotheses": warning_hypotheses,
        "blocker_hypotheses": blocker_hypotheses,
    }


def _dispute_summary(
    scores: list[HypothesisUtilityScore],
    dispute_stats: dict[str, _HypothesisDisputeStats],
) -> dict[str, Any]:
    disputed_hypotheses = [
        score.hypothesis_id
        for score in scores
        if (dispute_stats.get(score.hypothesis_id) or _HypothesisDisputeStats()).disputed_edge_count
        > 0
    ]
    return {
        "n_hypotheses_with_disputes": len(disputed_hypotheses),
        "disputed_hypotheses": disputed_hypotheses,
        "per_hypothesis": {
            hypothesis_id: {
                "disputed_edge_count": stats.disputed_edge_count,
                "disputed_edge_fraction": stats.disputed_edge_fraction,
            }
            for hypothesis_id, stats in dispute_stats.items()
        },
    }


@dataclass(frozen=True)
class HypothesisIdentificationProjection:
    """Current source-code projection used by both scoring and downstream intake."""

    identification_status: str
    identifiability_score: float
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    blocking_certificates: tuple[str, ...]


def identify_hypothesis_identification_status(
    hypothesis: GraphHypothesis,
    causal_query: CausalQuery,
) -> HypothesisIdentificationProjection:
    """Recompute one hypothesis identification result with the current causal engine.

    The utility judge and graph-prior consumer call this same function so that
    persisted score labels cannot substitute for the current source algorithm.
    """
    score, status, reasons, warnings, blocking = _score_identifiability(
        hypothesis,
        causal_query,
    )
    return HypothesisIdentificationProjection(
        identification_status=status,
        identifiability_score=score,
        reasons=tuple(reasons),
        warnings=tuple(warnings),
        blocking_certificates=tuple(blocking),
    )


def _score_identifiability(
    hypothesis: GraphHypothesis,
    causal_query: CausalQuery,
) -> tuple[float, str, list[str], list[str], list[str]]:
    warnings: list[str] = []
    reasons: list[str] = []
    blocking: list[str] = []
    graph = hypothesis.graph_for_analysis()
    if graph is None:
        reason = "identifiability:unsupported:graph_projection_unavailable"
        return (
            0.0,
            "unsupported_graph_profile",
            [reason],
            ["partial_graph_source_retained"],
            [reason],
        )
    if hypothesis.resolved_graph is not None:
        warnings.append("content_bound_graph_projection_used_for_identifiability")
    elif getattr(hypothesis.graph.graph_type, "value", "") in {"pag", "cpdag"}:
        warnings.append("structural_uncertainty_limited_identifiability")

    engine = CausalEngine()
    result = engine.identify(
        treatment=causal_query.treatment_variable,
        outcome=causal_query.outcome_variable,
        graph=graph,
    )
    if isinstance(result, NegativeCertificate):
        blocking.append(result.blocking_description)
        reasons.append(f"identifiability:blocked:{result.blocking_type.value}")
        return 0.0, result.blocking_type.value, reasons, warnings, blocking
    if isinstance(result, IdentificationResult):
        if result.status is IdentificationStatus.IDENTIFIED:
            pag_confidence = getattr(graph, "id_confidence_under_pag", None)
            if pag_confidence is not None and float(pag_confidence) < 1.0:
                reasons.append("identifiability:partial_probabilistic")
                return 0.5, "partial_probabilistic", reasons, warnings, blocking
            reasons.append("identifiability:identified")
            return 1.0, result.status.value, reasons, warnings, blocking
        if result.status in {
            IdentificationStatus.PAG_AMBIGUOUS,
            IdentificationStatus.ORACLE_NEEDED,
        }:
            reasons.append(f"identifiability:partial:{result.status.value}")
            if result.metadata.get("limitation_code") == "unsupported_static_admg_profile":
                reasons.append("identifiability:unsupported_static_admg_profile")
            return 0.5, result.status.value, reasons, warnings, blocking
        blocking.append(result.status.value)
        reasons.append(f"identifiability:failed:{result.status.value}")
        return 0.0, result.status.value, reasons, warnings, blocking
    blocking.append("unsupported_identification_result")
    reasons.append("identifiability:failed:unsupported_result")
    return 0.0, "unsupported_result", reasons, warnings, blocking


def _score_stability(summary: Any) -> float:
    if summary is None:
        return 0.0
    if summary.adjustment_set_stability is not None and summary.mean_edge_stability is not None:
        return float((0.7 * summary.adjustment_set_stability) + (0.3 * summary.mean_edge_stability))
    if summary.adjustment_set_stability is not None:
        return float(summary.adjustment_set_stability)
    if summary.mean_edge_stability is not None:
        return float(summary.mean_edge_stability)
    return 0.0


def _score_transportability(
    hypothesis: GraphHypothesis,
    causal_query: CausalQuery,
    *,
    selection_diagram: SelectionDiagram | None,
    s_nodes: list[SNode],
) -> tuple[float, str, list[str], list[str]]:
    reasons: list[str] = []
    warnings: list[str] = []
    graph = hypothesis.graph_for_analysis()
    if graph is None:
        reason = "transportability:unsupported:graph_projection_unavailable"
        return (
            0.0,
            "unsupported_graph_profile",
            [reason],
            ["partial_graph_source_retained"],
        )
    if selection_diagram is not None:
        diagram = selection_diagram.model_copy(update={"base_graph": graph})
        result = solve_transportability(
            selection_diagram=diagram,
            query_treatment=causal_query.treatment_variable,
            query_outcome=causal_query.outcome_variable,
        )
        reasons.append(f"transportability:{result.status.value}")
        warnings.extend(result.warnings)
        if result.status is TransportabilityStatus.IDENTIFIED:
            if result.requires_expert_review:
                reasons.append("transportability_requires_expert_review")
                warnings.extend(result.expert_review_reasons)
                return 0.5, result.status.value, reasons, warnings
            return 1.0, result.status.value, reasons, warnings
        if result.status in {
            TransportabilityStatus.PARTIALLY_IDENTIFIED,
            TransportabilityStatus.BOUNDED_NON_IDENTIFIED,
        }:
            return 0.5, result.status.value, reasons, warnings
        return 0.0, result.status.value, reasons, warnings

    engine = CausalEngine()
    result = engine.identify(
        treatment=causal_query.treatment_variable,
        outcome=causal_query.outcome_variable,
        graph=graph,
        s_nodes=s_nodes,
    )
    if (
        isinstance(result, IdentificationResult)
        and result.status is IdentificationStatus.IDENTIFIED
    ):
        reasons.append("transportability:identified_via_s_nodes")
        return 1.0, "identified", reasons, warnings
    if isinstance(result, IdentificationResult) and result.status in {
        IdentificationStatus.PAG_AMBIGUOUS,
        IdentificationStatus.ORACLE_NEEDED,
    }:
        reasons.append(f"transportability:partial:{result.status.value}")
        return 0.5, result.status.value, reasons, warnings
    if isinstance(result, NegativeCertificate):
        reasons.append(f"transportability:blocked:{result.blocking_type.value}")
        return 0.0, result.blocking_type.value, reasons, warnings
    reasons.append("transportability:unsupported_result")
    return 0.0, "unsupported_result", reasons, warnings


def _score_estimation_quality(
    report: CausalEffectReport,
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    if report.status is not EstimationStatus.SUCCESS or report.confidence_interval is None:
        reasons.append(f"estimation_quality:failed:{report.status.value}")
        return 0.0, reasons
    low, high = report.confidence_interval
    ci_width = max(0.0, float(high - low))
    ci_score = 1.0 / (1.0 + ci_width)
    refutations = report.refutation_results
    refutation_rate = (
        float(sum(1 for item in refutations if item.passed) / len(refutations))
        if refutations
        else 0.5
    )
    score = (0.4 * 1.0) + (0.3 * ci_score) + (0.3 * refutation_rate)
    reasons.append(f"estimation_quality:{score:.3f}")
    return float(score), reasons


def _build_shortlist(
    scores: list[HypothesisUtilityScore],
    *,
    size: int,
) -> tuple[list[str], list[str]]:
    eligible = list(scores)
    exclusions: list[str] = []
    if any(score.algebraic_severity != "blocker" for score in scores):
        eligible = []
        for score in scores:
            if score.algebraic_severity == "blocker":
                exclusions.append(f"blocked:{score.hypothesis_id}:algebraic_blocker")
                continue
            eligible.append(score)
    identified = [score for score in eligible if score.identifiability_score > 0.0]
    if identified:
        return [score.hypothesis_id for score in identified[:size]], exclusions
    if eligible:
        return [score.hypothesis_id for score in eligible[:1]], exclusions
    return [score.hypothesis_id for score in scores[:1]], exclusions


__all__ = [
    "DOWNSTREAM_UTILITY_REPORT_SCHEMA_NAME",
    "DOWNSTREAM_UTILITY_REPORT_SCHEMA_VERSION",
    "IDENTIFICATION_SOURCE_ALGORITHM_VERSION",
    "DownstreamUtilityJudge",
    "DownstreamUtilityReport",
    "HypothesisIdentificationProjection",
    "HypothesisUtilityScore",
    "UtilityJudgeConfig",
    "UtilityJudgeInput",
    "graph_derived_candidate_scope",
    "identify_hypothesis_identification_status",
    "load_downstream_utility_report",
    "persist_downstream_utility_report",
]
