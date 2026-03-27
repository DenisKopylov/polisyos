"""Downstream causal-utility scoring for discovery hypotheses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.scientist import DownstreamUtilityReportRef
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationResult, IdentificationStatus
from polisyos.foundry.methods.catalog.causal.transport_engine import solve_transportability
from polisyos.ir.analytics.causal import CausalEffectReport, EstimationStatus
from polisyos.ir.analytics.causal_queries import CausalQuery
from polisyos.ir.analytics.negative_certificate import NegativeCertificate
from polisyos.ir.analytics.transportability import SNode, SelectionDiagram, TransportabilityStatus
from polisyos.scientist.discovery.schema import (
    GraphHypothesis,
    edge_key_for_edge,
    orientation_key_for_edge,
    skeleton_key_for_edge,
)
from polisyos.scientist.discovery.stability import BootstrapStabilityReport
from polisyos.scientist.search.artifact_minimality import (
    ArtifactFunction,
    ArtifactMinimalityMixin,
    artifact_functions_field,
)

DOWNSTREAM_UTILITY_REPORT_SCHEMA_NAME = (
    "polisyos.scientist.discovery.DownstreamUtilityReport"
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

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.ROUTING,
            ArtifactFunction.PROMOTION_GATING,
        )
    )
    scores: list[HypothesisUtilityScore] = Field(default_factory=list)
    recommended_shortlist: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


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
        ranked = [
            item.model_copy(update={"rank": index + 1})
            for index, item in enumerate(scores)
        ]
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
                "transport_context_present": bundle.selection_diagram is not None or bool(bundle.s_nodes),
                "benchmark_reports_present": bool(bundle.benchmark_reports),
                "channel_coverage": channel_coverage,
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
        dispute_stats: "_HypothesisDisputeStats",
    ) -> HypothesisUtilityScore:
        ident_score, ident_status, ident_reasons, ident_warnings, blocking = _score_identifiability(
            hypothesis,
            bundle.causal_query,
        )
        algebraic_severity, algebraic_consistency = _algebraic_consistency(hypothesis)
        dispute_consistency = max(0.0, min(1.0, 1.0 - dispute_stats.disputed_edge_fraction))
        discovery_consistency_score = float(
            max(0.0, min(1.0, (0.7 * algebraic_consistency) + (0.3 * dispute_consistency)))
        )
        summary = bundle.stability_report.summary_for(hypothesis.hypothesis_id)
        stability_score = _score_stability(summary)
        reasons = list(ident_reasons)
        warnings = list(ident_warnings)
        reasons.append(f"discovery_consistency:{discovery_consistency_score:.3f}")
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
            transport_score, transport_status, transport_reasons, transport_warnings = _score_transportability(
                hypothesis,
                bundle.causal_query,
                selection_diagram=bundle.selection_diagram,
                s_nodes=bundle.s_nodes,
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
    ref = store.put_json(
        report,
        PutOptions(
            kind="scientist.downstream_utility_report",
            media_type="application/json",
            schema=SchemaInfo(
                name=DOWNSTREAM_UTILITY_REPORT_SCHEMA_NAME,
                version=report.schema_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return DownstreamUtilityReportRef.model_validate(ref.model_dump(mode="json"))


def load_downstream_utility_report(
    store: FileSystemCAS,
    ref: DownstreamUtilityReportRef,
) -> DownstreamUtilityReport:
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return DownstreamUtilityReport.model_validate(payload)


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
        fraction = (
            float(disputed_edge_count / total_edge_count)
            if total_edge_count > 0
            else 0.0
        )
        stats[hypothesis.hypothesis_id] = _HypothesisDisputeStats(
            disputed_edge_count=disputed_edge_count,
            total_edge_count=total_edge_count,
            disputed_edge_fraction=max(0.0, min(1.0, fraction)),
        )
    return stats


def _algebraic_consistency(
    hypothesis: GraphHypothesis,
) -> tuple[str | None, float]:
    report_metadata = hypothesis.metadata.get("discovery_report_metadata")
    if isinstance(report_metadata, dict):
        severity = str(report_metadata.get("algebraic_constraint_severity") or "").strip().lower()
    else:
        severity = ""
    if not severity:
        direct = str(hypothesis.metadata.get("algebraic_constraint_severity") or "").strip().lower()
        severity = direct
    if severity == "blocker":
        return "blocker", 0.0
    if severity == "warning":
        return "warning", 0.5
    if severity == "info":
        return "info", 1.0
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
        if (dispute_stats.get(score.hypothesis_id) or _HypothesisDisputeStats()).disputed_edge_count > 0
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


def _score_identifiability(
    hypothesis: GraphHypothesis,
    causal_query: CausalQuery,
) -> tuple[float, str, list[str], list[str], list[str]]:
    warnings: list[str] = []
    reasons: list[str] = []
    blocking: list[str] = []
    graph = hypothesis.resolved_graph or hypothesis.graph
    if hypothesis.resolved_graph is not None:
        warnings.append("resolved_graph_used_for_identifiability")
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
    graph = hypothesis.resolved_graph or hypothesis.graph
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
    if isinstance(result, IdentificationResult) and result.status is IdentificationStatus.IDENTIFIED:
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
    "DownstreamUtilityJudge",
    "DownstreamUtilityReport",
    "HypothesisUtilityScore",
    "UtilityJudgeConfig",
    "UtilityJudgeInput",
    "load_downstream_utility_report",
    "persist_downstream_utility_report",
]
