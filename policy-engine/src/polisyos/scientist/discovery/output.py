"""Typed discovery output bundle and artifact builder."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.scientist import (
    ActiveDisambiguationPlanRef,
    BootstrapStabilityReportRef,
    DiscoveryArtifactBundleRef,
    DiscoveryAuditBundleRef,
    DiscoveryTaskProfileRef,
    DownstreamUtilityReportRef,
    EdgeConfidenceMatrixRef,
    GraphHypothesisRef,
    GraphHypothesisSetRef,
    GraphPriorBundleRef,
    PriorKnowledgeBundleRef,
    RefutationReportRef,
    ReproducibilityReportRef,
)
from polisyos.ir.analytics.causal_discovery import DataCharacteristics
from polisyos.ir.analytics.causal_queries import CausalQuery
from polisyos.scientist.discovery.active import (
    ActiveDisambiguationConfig,
    ActiveDisambiguationPlan,
    ActiveDisambiguationPlanner,
    ActiveDisambiguationPlannerInput,
)
from polisyos.scientist.discovery.aggregator import (
    EdgeConfidenceMatrix,
    load_edge_confidence_matrix,
    persist_edge_confidence_matrix,
)
from polisyos.scientist.discovery.portfolio import PortfolioRunResult, PortfolioRunnerConfig
from polisyos.scientist.discovery.priors import (
    GraphPriorBundle,
    PriorKnowledgeBundle,
    load_graph_prior_bundle,
    load_prior_knowledge_bundle,
    persist_graph_prior_bundle,
    persist_prior_knowledge_bundle,
)
from polisyos.scientist.discovery.schema import (
    GraphHypothesis,
    persist_graph_hypothesis,
)
from polisyos.scientist.discovery.stability import (
    BootstrapStabilityReport,
    load_bootstrap_stability_report,
    persist_bootstrap_stability_report,
)
from polisyos.scientist.discovery.utility_judge import (
    DownstreamUtilityReport,
    load_downstream_utility_report,
    persist_downstream_utility_report,
)
from polisyos.scientist.discovery.workers import (
    DataProfileReport,
    DataProfilerWorkerInput,
    DiscoveryWorkerBudget,
    DiscoveryWorkerBundle,
    DiscoveryWorkerContext,
    SkepticFinding,
    SkepticWorkerInput,
    WorkerExecutionProvenance,
    run_bounded_discovery_workers,
)
from polisyos.scientist.search.artifact_minimality import (
    ArtifactFunction,
    ArtifactMinimalityMixin,
    artifact_functions_field,
)

DISCOVERY_TASK_PROFILE_SCHEMA_NAME = "polisyos.scientist.discovery.DiscoveryTaskProfile"
GRAPH_HYPOTHESIS_SET_SCHEMA_NAME = "polisyos.scientist.discovery.GraphHypothesisSet"
REFUTATION_REPORT_SCHEMA_NAME = "polisyos.scientist.discovery.RefutationReport"
REPRODUCIBILITY_REPORT_SCHEMA_NAME = "polisyos.scientist.discovery.ReproducibilityReport"
ACTIVE_DISAMBIGUATION_PLAN_SCHEMA_NAME = (
    "polisyos.scientist.discovery.ActiveDisambiguationPlan"
)
DISCOVERY_AUDIT_BUNDLE_SCHEMA_NAME = "polisyos.scientist.discovery.DiscoveryAuditBundle"
DISCOVERY_ARTIFACT_BUNDLE_SCHEMA_NAME = "polisyos.scientist.discovery.DiscoveryArtifactBundle"


class SeedVariationStatus(str, Enum):
    MEASURED = "measured"
    ESTIMATED = "estimated"
    NOT_RUN = "not_run"


class DiscoveryTaskProfile(ArtifactMinimalityMixin):
    """Top-level task context for a discovery run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.REPLAY_AUDIT,
        )
    )
    task_id: str = Field(default_factory=lambda: f"discovery_task_{uuid4().hex[:12]}")
    run_id: str = Field(default="discovery", min_length=1)
    variable_names: list[str] = Field(default_factory=list)
    causal_query: CausalQuery | None = None
    data_characteristics: DataCharacteristics | None = None
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphHypothesisSet(ArtifactMinimalityMixin):
    """Persisted index of discovery hypotheses and their ranking surface."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.ROUTING,
            ArtifactFunction.CROSS_RUN_LEARNING,
        )
    )
    graph_hypothesis_refs: list[GraphHypothesisRef] = Field(default_factory=list)
    ranking_order: list[str] = Field(default_factory=list)
    family_coverage: dict[str, int] = Field(default_factory=dict)
    skipped_families: dict[str, str] = Field(default_factory=dict)
    portfolio_warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RefutationReport(ArtifactMinimalityMixin):
    """Discovery refutation artifact produced by bounded workers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.PROMOTION_GATING,
            ArtifactFunction.REPLAY_AUDIT,
        )
    )
    status: str = Field(default="not_run_yet", min_length=1)
    skeptic_findings: list[SkepticFinding] = Field(default_factory=list)
    data_profile: DataProfileReport = Field(default_factory=DataProfileReport)
    targeted_hypothesis_ids: list[str] = Field(default_factory=list)
    targeted_edge_keys: list[str] = Field(default_factory=list)
    recommended_checks: list[str] = Field(default_factory=list)
    worker_provenance: list[WorkerExecutionProvenance] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReproducibilityReport(ArtifactMinimalityMixin):
    """Discovery reproducibility surface with explicit seed/stability coverage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.PROMOTION_GATING,
            ArtifactFunction.REPLAY_AUDIT,
        )
    )
    status: str = Field(default="complete", min_length=1)
    bootstrap_reproducibility: float | None = Field(default=None, ge=0.0, le=1.0)
    subsample_reproducibility: float | None = Field(default=None, ge=0.0, le=1.0)
    seed_variation_status: SeedVariationStatus = SeedVariationStatus.ESTIMATED
    seed_variation_score: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveryAuditBundle(ArtifactMinimalityMixin):
    """Replay-oriented discovery audit payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.REPLAY_AUDIT,
        )
    )
    run_id: str = Field(default="discovery", min_length=1)
    source_refs: dict[str, ArtifactRef] = Field(default_factory=dict)
    portfolio_config: dict[str, Any] = Field(default_factory=dict)
    method_params_by_hypothesis: dict[str, dict[str, Any]] = Field(default_factory=dict)
    skipped_families: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    upstream_audit_refs: list[ArtifactRef] = Field(default_factory=list)
    actionable_side_information_refs: list[ArtifactRef] = Field(default_factory=list)
    output_refs: dict[str, ArtifactRef] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveryArtifactBundle(ArtifactMinimalityMixin):
    """Wrapper over the 11 Phase-C discovery artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.PROMOTION_GATING,
            ArtifactFunction.REPLAY_AUDIT,
        )
    )
    bundle_id: str = Field(default_factory=lambda: f"discovery_bundle_{uuid4().hex[:12]}")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    discovery_task_profile_ref: DiscoveryTaskProfileRef
    prior_knowledge_bundle_ref: PriorKnowledgeBundleRef
    graph_hypothesis_set_ref: GraphHypothesisSetRef
    edge_confidence_matrix_ref: EdgeConfidenceMatrixRef
    bootstrap_stability_report_ref: BootstrapStabilityReportRef
    downstream_utility_report_ref: DownstreamUtilityReportRef
    refutation_report_ref: RefutationReportRef
    reproducibility_report_ref: ReproducibilityReportRef
    active_disambiguation_plan_ref: ActiveDisambiguationPlanRef
    discovery_audit_bundle_ref: DiscoveryAuditBundleRef
    graph_prior_bundle_ref: GraphPriorBundleRef
    audit_refs: list[ArtifactRef] = Field(default_factory=list)
    actionable_side_information_refs: list[ArtifactRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveryArtifactBuildInput(BaseModel):
    """Inputs needed to assemble the full discovery output bundle."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    run_id: str = Field(default="discovery", min_length=1)
    task_id: str = Field(default="discovery", min_length=1)
    variable_names: list[str] = Field(default_factory=list)
    causal_query: CausalQuery | None = None
    data_characteristics: DataCharacteristics | None = None
    hypotheses: list[GraphHypothesis] = Field(default_factory=list)
    portfolio_result: PortfolioRunResult | None = None
    portfolio_config: PortfolioRunnerConfig | None = None
    edge_confidence_matrix: EdgeConfidenceMatrix
    bootstrap_stability_report: BootstrapStabilityReport
    downstream_utility_report: DownstreamUtilityReport
    graph_prior_bundle: GraphPriorBundle
    prior_knowledge_bundle: PriorKnowledgeBundle
    active_disambiguation_plan: ActiveDisambiguationPlan | None = None
    active_disambiguation_config: ActiveDisambiguationConfig | None = None
    worker_bundle: DiscoveryWorkerBundle | None = None
    worker_budget: DiscoveryWorkerBudget | None = None
    worker_context: DiscoveryWorkerContext | None = None
    data_quality_report: Any | None = None
    evidence_bundle: Any | None = None
    source_refs: dict[str, ArtifactRef] = Field(default_factory=dict)
    audit_refs: list[ArtifactRef] = Field(default_factory=list)
    actionable_side_information_refs: list[ArtifactRef] = Field(default_factory=list)
    seed_replay_scores: dict[str, float] = Field(default_factory=dict)
    seed_variation_status_override: SeedVariationStatus | None = None
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveryArtifactBuilder:
    """Persist the full Phase-C discovery artifact bundle."""

    def build(
        self,
        store: FileSystemCAS,
        source: DiscoveryArtifactBuildInput,
    ) -> DiscoveryArtifactBundleRef:
        inputs = _bundle_inputs(source)
        upstream_audit_refs = _dedupe_artifact_refs(source.audit_refs)
        actionable_side_information_refs = _dedupe_artifact_refs(
            source.actionable_side_information_refs
        )
        task_profile = self._build_task_profile(source)
        task_profile_ref = persist_discovery_task_profile(store, task_profile, inputs=inputs)

        hypothesis_refs = [
            persist_graph_hypothesis(store, hypothesis, inputs=inputs)
            for hypothesis in source.hypotheses
        ]
        hypothesis_set = self._build_hypothesis_set(source, hypothesis_refs)
        hypothesis_set_ref = persist_graph_hypothesis_set(store, hypothesis_set, inputs=inputs)

        edge_confidence_matrix_ref = persist_edge_confidence_matrix(
            store,
            source.edge_confidence_matrix,
            inputs=inputs,
        )
        bootstrap_stability_report_ref = persist_bootstrap_stability_report(
            store,
            source.bootstrap_stability_report,
            inputs=inputs,
        )
        downstream_utility_report_ref = persist_downstream_utility_report(
            store,
            source.downstream_utility_report,
            inputs=inputs,
        )
        graph_prior_bundle_ref = persist_graph_prior_bundle(
            store,
            source.graph_prior_bundle,
            inputs=inputs,
        )
        prior_knowledge_bundle_ref = persist_prior_knowledge_bundle(
            store,
            source.prior_knowledge_bundle,
            inputs=inputs,
        )

        worker_bundle = self._resolve_worker_bundle(source)
        refutation_report = self._build_refutation_report(source, worker_bundle)
        refutation_report_ref = persist_refutation_report(store, refutation_report, inputs=inputs)

        reproducibility_report = self._build_reproducibility_report(source)
        reproducibility_report_ref = persist_reproducibility_report(
            store,
            reproducibility_report,
            inputs=inputs,
        )

        active_disambiguation_plan = self._build_active_disambiguation_plan(source, worker_bundle)
        active_disambiguation_plan_ref = persist_active_disambiguation_plan(
            store,
            active_disambiguation_plan,
            inputs=inputs,
        )

        audit_bundle = self._build_audit_bundle(
            source,
            refs={
                "discovery_task_profile_ref": task_profile_ref,
                "prior_knowledge_bundle_ref": prior_knowledge_bundle_ref,
                "graph_hypothesis_set_ref": hypothesis_set_ref,
                "edge_confidence_matrix_ref": edge_confidence_matrix_ref,
                "bootstrap_stability_report_ref": bootstrap_stability_report_ref,
                "downstream_utility_report_ref": downstream_utility_report_ref,
                "refutation_report_ref": refutation_report_ref,
                "reproducibility_report_ref": reproducibility_report_ref,
                "active_disambiguation_plan_ref": active_disambiguation_plan_ref,
                "graph_prior_bundle_ref": graph_prior_bundle_ref,
            },
            worker_bundle=worker_bundle,
            upstream_audit_refs=upstream_audit_refs,
            actionable_side_information_refs=actionable_side_information_refs,
        )
        discovery_audit_bundle_ref = persist_discovery_audit_bundle(
            store,
            audit_bundle,
            inputs=inputs,
        )

        bundle = DiscoveryArtifactBundle(
            discovery_task_profile_ref=task_profile_ref,
            prior_knowledge_bundle_ref=prior_knowledge_bundle_ref,
            graph_hypothesis_set_ref=hypothesis_set_ref,
            edge_confidence_matrix_ref=edge_confidence_matrix_ref,
            bootstrap_stability_report_ref=bootstrap_stability_report_ref,
            downstream_utility_report_ref=downstream_utility_report_ref,
            refutation_report_ref=refutation_report_ref,
            reproducibility_report_ref=reproducibility_report_ref,
            active_disambiguation_plan_ref=active_disambiguation_plan_ref,
            discovery_audit_bundle_ref=discovery_audit_bundle_ref,
            graph_prior_bundle_ref=graph_prior_bundle_ref,
            audit_refs=upstream_audit_refs,
            actionable_side_information_refs=actionable_side_information_refs,
            metadata={
                "task_id": source.task_id,
                "run_id": source.run_id,
                **source.metadata,
            },
        )
        return persist_discovery_artifact_bundle(store, bundle, inputs=inputs)

    def _build_task_profile(self, source: DiscoveryArtifactBuildInput) -> DiscoveryTaskProfile:
        return DiscoveryTaskProfile(
            task_id=source.task_id,
            run_id=source.run_id,
            variable_names=list(source.variable_names),
            causal_query=source.causal_query,
            data_characteristics=source.data_characteristics,
            notes=list(source.notes),
            metadata=dict(source.metadata),
        )

    def _build_hypothesis_set(
        self,
        source: DiscoveryArtifactBuildInput,
        hypothesis_refs: list[GraphHypothesisRef],
    ) -> GraphHypothesisSet:
        ranking_order = [score.hypothesis_id for score in source.downstream_utility_report.scores]
        family_coverage: dict[str, int] = {}
        for hypothesis in source.hypotheses:
            family_key = hypothesis.algorithm_family.value
            family_coverage[family_key] = family_coverage.get(family_key, 0) + 1
        portfolio_result = source.portfolio_result
        return GraphHypothesisSet(
            graph_hypothesis_refs=hypothesis_refs,
            ranking_order=ranking_order,
            family_coverage=family_coverage,
            skipped_families={
                family.value if hasattr(family, "value") else str(family): reason
                for family, reason in (
                    (portfolio_result.skipped_families if portfolio_result is not None else {}).items()
                )
            },
            portfolio_warnings=list(portfolio_result.warnings if portfolio_result is not None else []),
            metadata={
                "n_hypotheses": len(source.hypotheses),
            },
        )

    def _resolve_worker_bundle(
        self,
        source: DiscoveryArtifactBuildInput,
    ) -> DiscoveryWorkerBundle:
        if source.worker_bundle is not None:
            return source.worker_bundle
        return run_bounded_discovery_workers(
            data_profiler_input=DataProfilerWorkerInput(
                data_characteristics=source.data_characteristics,
                data_quality_report=source.data_quality_report,
                evidence_bundle=source.evidence_bundle,
                bootstrap_stability_report=source.bootstrap_stability_report,
                downstream_utility_report=source.downstream_utility_report,
                graph_prior_bundle=source.graph_prior_bundle,
                prior_knowledge_bundle=source.prior_knowledge_bundle,
                metadata={
                    "run_id": source.run_id,
                    "task_id": source.task_id,
                },
            ),
            skeptic_input=SkepticWorkerInput(
                hypotheses=list(source.hypotheses),
                edge_confidence_matrix=source.edge_confidence_matrix,
                bootstrap_stability_report=source.bootstrap_stability_report,
                downstream_utility_report=source.downstream_utility_report,
                graph_prior_bundle=source.graph_prior_bundle,
                prior_knowledge_bundle=source.prior_knowledge_bundle,
                metadata={
                    "run_id": source.run_id,
                    "task_id": source.task_id,
                },
            ),
            budget=source.worker_budget,
            context=source.worker_context
            or DiscoveryWorkerContext(
                run_id=source.run_id,
                task_id=source.task_id,
                metadata=dict(source.metadata),
            ),
        )

    def _build_refutation_report(
        self,
        source: DiscoveryArtifactBuildInput,
        worker_bundle: DiscoveryWorkerBundle,
    ) -> RefutationReport:
        return RefutationReport(
            status=worker_bundle.status,
            skeptic_findings=worker_bundle.skeptic_findings,
            data_profile=worker_bundle.data_profile,
            targeted_hypothesis_ids=worker_bundle.targeted_hypothesis_ids,
            targeted_edge_keys=worker_bundle.targeted_edge_keys,
            recommended_checks=worker_bundle.recommended_checks,
            worker_provenance=worker_bundle.worker_provenance,
            notes=list(worker_bundle.notes),
            metadata={
                "run_id": source.run_id,
                "task_id": source.task_id,
                **worker_bundle.metadata,
            },
        )

    def _build_reproducibility_report(
        self,
        source: DiscoveryArtifactBuildInput,
    ) -> ReproducibilityReport:
        bootstrap_scores = [
            summary.mean_edge_stability
            for summary in source.bootstrap_stability_report.summaries
            if summary.mean_edge_stability is not None
        ]
        subsample_scores = [
            summary.adjustment_set_stability
            for summary in source.bootstrap_stability_report.summaries
            if summary.adjustment_set_stability is not None
        ]
        bootstrap_reproducibility = _mean_or_none(bootstrap_scores)
        subsample_reproducibility = _mean_or_none(subsample_scores)
        seed_variation_score = _estimate_seed_variation_score(
            source,
            bootstrap_reproducibility=bootstrap_reproducibility,
            subsample_reproducibility=subsample_reproducibility,
        )
        seed_count = len(
            {
                hypothesis.compute_footprint.random_seed
                for hypothesis in source.hypotheses
                if hypothesis.compute_footprint.random_seed is not None
            }
        )
        if source.seed_replay_scores:
            measured_score = _mean_or_none(source.seed_replay_scores.values())
            return ReproducibilityReport(
                status="complete",
                bootstrap_reproducibility=bootstrap_reproducibility,
                subsample_reproducibility=subsample_reproducibility,
                seed_variation_status=SeedVariationStatus.MEASURED,
                seed_variation_score=measured_score,
                notes=[
                    "Seed-variation reproducibility is measured from multi-seed replay over the shortlist.",
                    f"Measured shortlist size: {len(source.seed_replay_scores)}.",
                    "Bootstrap-derived stability is surfaced from the shared C.3 analyzer.",
                ],
                metadata={
                    "seed_variation_estimation_mode": "measured_replay_matrix",
                    "seed_count": seed_count,
                    "seed_replay_scores": dict(source.seed_replay_scores),
                },
            )
        if source.seed_variation_status_override is SeedVariationStatus.NOT_RUN:
            return ReproducibilityReport(
                status="degraded",
                bootstrap_reproducibility=bootstrap_reproducibility,
                subsample_reproducibility=subsample_reproducibility,
                seed_variation_status=SeedVariationStatus.NOT_RUN,
                seed_variation_score=None,
                notes=[
                    "Seed-variation reproducibility was not run for this discovery bundle.",
                    "Bootstrap-derived stability is still surfaced from the shared C.3 analyzer.",
                ],
                metadata={
                    "seed_variation_estimation_mode": "not_run",
                    "seed_count": seed_count,
                },
            )
        return ReproducibilityReport(
            status="complete",
            bootstrap_reproducibility=bootstrap_reproducibility,
            subsample_reproducibility=subsample_reproducibility,
            seed_variation_status=SeedVariationStatus.ESTIMATED,
            seed_variation_score=seed_variation_score,
            notes=[
                (
                    "Seed-variation reproducibility is estimated from the seeded portfolio "
                    "surface plus shared bootstrap/subsample stability."
                ),
                f"Seeded hypothesis count available for estimation: {seed_count}.",
                "Bootstrap-derived stability is surfaced from the shared C.3 analyzer.",
            ],
            metadata={
                "seed_variation_estimation_mode": "portfolio_seed_proxy",
                "seed_count": seed_count,
            },
        )

    def _build_active_disambiguation_plan(
        self,
        source: DiscoveryArtifactBuildInput,
        worker_bundle: DiscoveryWorkerBundle,
    ) -> ActiveDisambiguationPlan:
        if source.active_disambiguation_plan is not None:
            return source.active_disambiguation_plan
        planner = ActiveDisambiguationPlanner(config=source.active_disambiguation_config)
        return planner.plan(
            ActiveDisambiguationPlannerInput(
                edge_confidence_matrix=source.edge_confidence_matrix,
                bootstrap_stability_report=source.bootstrap_stability_report,
                downstream_utility_report=source.downstream_utility_report,
                hypotheses=list(source.hypotheses),
                graph_prior_bundle=source.graph_prior_bundle,
                prior_knowledge_bundle=source.prior_knowledge_bundle,
                causal_query=source.causal_query,
                target_context={
                    "run_id": source.run_id,
                    "task_id": source.task_id,
                    "worker_findings": worker_bundle.active_planner_context(),
                    **source.metadata,
                },
            )
        )

    def _build_audit_bundle(
        self,
        source: DiscoveryArtifactBuildInput,
        *,
        refs: dict[str, ArtifactRef],
        worker_bundle: DiscoveryWorkerBundle,
        upstream_audit_refs: list[ArtifactRef],
        actionable_side_information_refs: list[ArtifactRef],
    ) -> DiscoveryAuditBundle:
        portfolio_result = source.portfolio_result
        method_params_by_hypothesis = {
            hypothesis.hypothesis_id: dict(hypothesis.compute_footprint.method_params)
            for hypothesis in source.hypotheses
        }
        return DiscoveryAuditBundle(
            run_id=source.run_id,
            source_refs=dict(source.source_refs),
            portfolio_config=(
                source.portfolio_config.model_dump(mode="json")
                if source.portfolio_config is not None
                else {}
            ),
            method_params_by_hypothesis=method_params_by_hypothesis,
            skipped_families={
                family.value if hasattr(family, "value") else str(family): reason
                for family, reason in (
                    (portfolio_result.skipped_families if portfolio_result is not None else {}).items()
                )
            },
            warnings=[
                *(portfolio_result.warnings if portfolio_result is not None else []),
                *source.graph_prior_bundle.warnings,
                *source.prior_knowledge_bundle.warnings,
            ],
            upstream_audit_refs=upstream_audit_refs,
            actionable_side_information_refs=actionable_side_information_refs,
            output_refs=refs,
            metadata={
                "notes": list(source.notes),
                "artifact_bundle_ref_omitted_due_to_parent_cycle": True,
                "worker_bundle": worker_bundle.model_dump(mode="json"),
                **source.metadata,
            },
        )


def persist_discovery_task_profile(
    store: FileSystemCAS,
    payload: DiscoveryTaskProfile,
    *,
    inputs: list[InputRef] | None = None,
) -> DiscoveryTaskProfileRef:
    return _put_model(
        store,
        payload,
        kind="scientist.discovery_task_profile",
        schema_name=DISCOVERY_TASK_PROFILE_SCHEMA_NAME,
        ref_cls=DiscoveryTaskProfileRef,
        inputs=inputs,
    )


def load_discovery_task_profile(
    store: FileSystemCAS,
    ref: DiscoveryTaskProfileRef,
) -> DiscoveryTaskProfile:
    return _load_model(store, ref, DiscoveryTaskProfile)


def persist_graph_hypothesis_set(
    store: FileSystemCAS,
    payload: GraphHypothesisSet,
    *,
    inputs: list[InputRef] | None = None,
) -> GraphHypothesisSetRef:
    return _put_model(
        store,
        payload,
        kind="scientist.graph_hypothesis_set",
        schema_name=GRAPH_HYPOTHESIS_SET_SCHEMA_NAME,
        ref_cls=GraphHypothesisSetRef,
        inputs=inputs,
    )


def load_graph_hypothesis_set(
    store: FileSystemCAS,
    ref: GraphHypothesisSetRef,
) -> GraphHypothesisSet:
    return _load_model(store, ref, GraphHypothesisSet)


def persist_refutation_report(
    store: FileSystemCAS,
    payload: RefutationReport,
    *,
    inputs: list[InputRef] | None = None,
) -> RefutationReportRef:
    return _put_model(
        store,
        payload,
        kind="scientist.discovery_refutation_report",
        schema_name=REFUTATION_REPORT_SCHEMA_NAME,
        ref_cls=RefutationReportRef,
        inputs=inputs,
    )


def load_refutation_report(
    store: FileSystemCAS,
    ref: RefutationReportRef,
) -> RefutationReport:
    return _load_model(store, ref, RefutationReport)


def persist_reproducibility_report(
    store: FileSystemCAS,
    payload: ReproducibilityReport,
    *,
    inputs: list[InputRef] | None = None,
) -> ReproducibilityReportRef:
    return _put_model(
        store,
        payload,
        kind="scientist.discovery_reproducibility_report",
        schema_name=REPRODUCIBILITY_REPORT_SCHEMA_NAME,
        ref_cls=ReproducibilityReportRef,
        inputs=inputs,
    )


def load_reproducibility_report(
    store: FileSystemCAS,
    ref: ReproducibilityReportRef,
) -> ReproducibilityReport:
    return _load_model(store, ref, ReproducibilityReport)


def persist_active_disambiguation_plan(
    store: FileSystemCAS,
    payload: ActiveDisambiguationPlan,
    *,
    inputs: list[InputRef] | None = None,
) -> ActiveDisambiguationPlanRef:
    return _put_model(
        store,
        payload,
        kind="scientist.active_disambiguation_plan",
        schema_name=ACTIVE_DISAMBIGUATION_PLAN_SCHEMA_NAME,
        ref_cls=ActiveDisambiguationPlanRef,
        inputs=inputs,
    )


def load_active_disambiguation_plan(
    store: FileSystemCAS,
    ref: ActiveDisambiguationPlanRef,
) -> ActiveDisambiguationPlan:
    return _load_model(store, ref, ActiveDisambiguationPlan)


def persist_discovery_audit_bundle(
    store: FileSystemCAS,
    payload: DiscoveryAuditBundle,
    *,
    inputs: list[InputRef] | None = None,
) -> DiscoveryAuditBundleRef:
    return _put_model(
        store,
        payload,
        kind="scientist.discovery_audit_bundle",
        schema_name=DISCOVERY_AUDIT_BUNDLE_SCHEMA_NAME,
        ref_cls=DiscoveryAuditBundleRef,
        inputs=inputs,
    )


def load_discovery_audit_bundle(
    store: FileSystemCAS,
    ref: DiscoveryAuditBundleRef,
) -> DiscoveryAuditBundle:
    return _load_model(store, ref, DiscoveryAuditBundle)


def persist_discovery_artifact_bundle(
    store: FileSystemCAS,
    payload: DiscoveryArtifactBundle,
    *,
    inputs: list[InputRef] | None = None,
) -> DiscoveryArtifactBundleRef:
    return _put_model(
        store,
        payload,
        kind="scientist.discovery_artifact_bundle",
        schema_name=DISCOVERY_ARTIFACT_BUNDLE_SCHEMA_NAME,
        ref_cls=DiscoveryArtifactBundleRef,
        inputs=inputs,
    )


def load_discovery_artifact_bundle(
    store: FileSystemCAS,
    ref: DiscoveryArtifactBundleRef,
) -> DiscoveryArtifactBundle:
    return _load_model(store, ref, DiscoveryArtifactBundle)


def _put_model(
    store: FileSystemCAS,
    payload: BaseModel,
    *,
    kind: str,
    schema_name: str,
    ref_cls: type[ArtifactRef],
    inputs: list[InputRef] | None = None,
) -> Any:
    ref = store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(
                name=schema_name,
                version=str(payload.schema_version),
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ref_cls.model_validate(ref.model_dump(mode="json"))


def _load_model(
    store: FileSystemCAS,
    ref: ArtifactRef,
    model_cls: type[BaseModel],
) -> Any:
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return model_cls.model_validate(payload)


def _bundle_inputs(source: DiscoveryArtifactBuildInput) -> list[InputRef]:
    inputs = [
        InputRef(artifact_id=ref.artifact_id, role=role)
        for role, ref in sorted(source.source_refs.items())
    ]
    for index, ref in enumerate(_dedupe_artifact_refs(source.audit_refs)):
        inputs.append(
            InputRef(
                artifact_id=ref.artifact_id,
                role=f"upstream_audit_ref_{index}",
            )
        )
    for index, ref in enumerate(_dedupe_artifact_refs(source.actionable_side_information_refs)):
        inputs.append(
            InputRef(
                artifact_id=ref.artifact_id,
                role=f"actionable_side_information_ref_{index}",
            )
        )
    return inputs


def _dedupe_artifact_refs(items: list[ArtifactRef]) -> list[ArtifactRef]:
    output: list[ArtifactRef] = []
    seen: set[str] = set()
    for item in items:
        artifact_id = str(item.artifact_id)
        if artifact_id in seen:
            continue
        seen.add(artifact_id)
        output.append(item)
    return output


def _mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _estimate_seed_variation_score(
    source: DiscoveryArtifactBuildInput,
    *,
    bootstrap_reproducibility: float | None,
    subsample_reproducibility: float | None,
) -> float:
    base_components = [
        value
        for value in (bootstrap_reproducibility, subsample_reproducibility)
        if value is not None
    ]
    base_score = _mean_or_none(base_components) or 0.0
    seed_values = {
        hypothesis.compute_footprint.random_seed
        for hypothesis in source.hypotheses
        if hypothesis.compute_footprint.random_seed is not None
    }
    family_values = {hypothesis.algorithm_family.value for hypothesis in source.hypotheses}
    diversity_bonus = min(0.10, 0.03 * len(seed_values) + 0.02 * len(family_values))
    return max(0.0, min(1.0, base_score + diversity_bonus))


__all__ = [
    "ACTIVE_DISAMBIGUATION_PLAN_SCHEMA_NAME",
    "ActiveDisambiguationConfig",
    "ActiveDisambiguationPlan",
    "ActiveDisambiguationPlanner",
    "ActiveDisambiguationPlannerInput",
    "DISCOVERY_ARTIFACT_BUNDLE_SCHEMA_NAME",
    "DISCOVERY_AUDIT_BUNDLE_SCHEMA_NAME",
    "DISCOVERY_TASK_PROFILE_SCHEMA_NAME",
    "DiscoveryArtifactBuildInput",
    "DiscoveryArtifactBuilder",
    "DiscoveryArtifactBundle",
    "DiscoveryAuditBundle",
    "DiscoveryTaskProfile",
    "GRAPH_HYPOTHESIS_SET_SCHEMA_NAME",
    "GraphHypothesisSet",
    "REFUTATION_REPORT_SCHEMA_NAME",
    "REPRODUCIBILITY_REPORT_SCHEMA_NAME",
    "RefutationReport",
    "ReproducibilityReport",
    "load_active_disambiguation_plan",
    "load_bootstrap_stability_report",
    "load_discovery_artifact_bundle",
    "load_discovery_audit_bundle",
    "load_discovery_task_profile",
    "load_downstream_utility_report",
    "load_edge_confidence_matrix",
    "load_graph_hypothesis_set",
    "load_graph_prior_bundle",
    "load_prior_knowledge_bundle",
    "load_refutation_report",
    "load_reproducibility_report",
    "persist_active_disambiguation_plan",
    "persist_discovery_artifact_bundle",
    "persist_discovery_audit_bundle",
    "persist_discovery_task_profile",
    "persist_graph_hypothesis_set",
    "persist_refutation_report",
    "persist_reproducibility_report",
]
