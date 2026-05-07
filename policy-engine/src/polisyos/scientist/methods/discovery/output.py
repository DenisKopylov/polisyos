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
from polisyos.ir.analytics.causal_discovery import (
    CausalDiscoveryReport,
    DataCharacteristics,
    LatentAssumptionCard,
    LatentDiscoveryBundle,
    LatentPromotionEvidence,
    LatentTrustLevel,
    load_causal_discovery_report,
    persist_causal_discovery_report,
)
from polisyos.ir.analytics.causal_queries import CausalQuery
from polisyos.ir.artifacts import InputRef as IRInputRef
from polisyos.ir.refs import CausalDiscoveryReportRef
from polisyos.scientist.methods.causal.latent_separation import (
    SEPARATION_DIAGNOSTICS_KEY,
    certify_latent_separation_trust,
    merge_latent_separation_diagnostics_payloads,
    metadata_with_computed_latent_separation,
    separation_diagnostics_payload,
)
from polisyos.scientist.methods.discovery.active import (
    ActiveDisambiguationConfig,
    ActiveDisambiguationPlan,
    ActiveDisambiguationPlanner,
    ActiveDisambiguationPlannerInput,
)
from polisyos.scientist.methods.discovery.aggregator import (
    EdgeConfidenceMatrix,
    load_edge_confidence_matrix,
    persist_edge_confidence_matrix,
)
from polisyos.scientist.methods.discovery.portfolio import PortfolioRunnerConfig, PortfolioRunResult
from polisyos.scientist.methods.discovery.priors import (
    GraphPriorBundle,
    PriorKnowledgeBundle,
    load_graph_prior_bundle,
    load_prior_knowledge_bundle,
    persist_graph_prior_bundle,
    persist_prior_knowledge_bundle,
)
from polisyos.scientist.methods.discovery.schema import (
    GraphHypothesis,
    load_graph_hypothesis,
    persist_graph_hypothesis,
)
from polisyos.scientist.methods.discovery.stability import (
    BootstrapStabilityReport,
    load_bootstrap_stability_report,
    persist_bootstrap_stability_report,
)
from polisyos.scientist.methods.discovery.utility_judge import (
    DownstreamUtilityReport,
    load_downstream_utility_report,
    persist_downstream_utility_report,
)
from polisyos.scientist.methods.discovery.workers import (
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
from polisyos.scientist.methods.search.artifact_minimality import (
    ArtifactFunction,
    ArtifactMinimalityMixin,
    artifact_functions_field,
)
from polisyos.scientist.methods.search.latent_promotion import evaluate_latent_promotion

DISCOVERY_TASK_PROFILE_SCHEMA_NAME = "polisyos.scientist.discovery.DiscoveryTaskProfile"
GRAPH_HYPOTHESIS_SET_SCHEMA_NAME = "polisyos.scientist.discovery.GraphHypothesisSet"
REFUTATION_REPORT_SCHEMA_NAME = "polisyos.scientist.discovery.RefutationReport"
REPRODUCIBILITY_REPORT_SCHEMA_NAME = "polisyos.scientist.discovery.ReproducibilityReport"
ACTIVE_DISAMBIGUATION_PLAN_SCHEMA_NAME = "polisyos.scientist.discovery.ActiveDisambiguationPlan"
DISCOVERY_AUDIT_BUNDLE_SCHEMA_NAME = "polisyos.scientist.discovery.DiscoveryAuditBundle"
DISCOVERY_ARTIFACT_BUNDLE_SCHEMA_NAME = "polisyos.scientist.discovery.DiscoveryArtifactBundle"
_LATENT_CARDINALITY_METADATA_KEYS = {
    "model_class",
    "identifiability_status",
    "latent_blocks",
    "latent_candidates",
    "ambiguity_notes",
}


class SeedVariationStatus(str, Enum):
    """Seed variation status public type."""

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
    discovery_report_refs_by_hypothesis: dict[str, CausalDiscoveryReportRef] = Field(
        default_factory=dict
    )
    portfolio_config: dict[str, Any] = Field(default_factory=dict)
    method_params_by_hypothesis: dict[str, dict[str, Any]] = Field(default_factory=dict)
    skipped_families: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    latent_discovery_summary: dict[str, Any] = Field(default_factory=dict)
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

        prepared_hypotheses, discovery_report_refs = self._prepare_hypotheses(
            store,
            source,
            inputs=inputs,
        )
        hypothesis_refs = [
            persist_graph_hypothesis(store, hypothesis, inputs=inputs)
            for hypothesis in prepared_hypotheses
        ]
        hypothesis_set = self._build_hypothesis_set(
            source.model_copy(update={"hypotheses": prepared_hypotheses}),
            hypothesis_refs,
        )
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
            source.model_copy(update={"hypotheses": prepared_hypotheses}),
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
            discovery_report_refs=discovery_report_refs,
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

    def _prepare_hypotheses(
        self,
        store: FileSystemCAS,
        source: DiscoveryArtifactBuildInput,
        *,
        inputs: list[InputRef],
    ) -> tuple[list[GraphHypothesis], dict[str, CausalDiscoveryReportRef]]:
        ir_inputs = [
            IRInputRef(artifact_id=input_ref.artifact_id, role=input_ref.role)
            for input_ref in inputs
        ]
        if source.portfolio_result is None:
            return list(source.hypotheses), {
                hypothesis.hypothesis_id: hypothesis.source_discovery_report_ref
                for hypothesis in source.hypotheses
                if hypothesis.source_discovery_report_ref is not None
            }

        report_refs: dict[str, CausalDiscoveryReportRef] = {}
        hypothesis_updates: dict[str, GraphHypothesis] = {}
        for candidate in source.portfolio_result.candidates:
            ref = persist_causal_discovery_report(
                store,
                candidate.source_report,
                inputs=ir_inputs,
            )
            hypothesis = candidate.hypothesis.model_copy(
                update={"source_discovery_report_ref": ref}
            )
            report_refs[hypothesis.hypothesis_id] = ref
            hypothesis_updates[hypothesis.hypothesis_id] = hypothesis

        prepared = [
            hypothesis_updates.get(hypothesis.hypothesis_id, hypothesis)
            for hypothesis in source.hypotheses
        ]
        return prepared, report_refs

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
                    (
                        portfolio_result.skipped_families if portfolio_result is not None else {}
                    ).items()
                )
            },
            portfolio_warnings=list(
                portfolio_result.warnings if portfolio_result is not None else []
            ),
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
        discovery_report_refs: dict[str, CausalDiscoveryReportRef],
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
            discovery_report_refs_by_hypothesis=dict(discovery_report_refs),
            portfolio_config=(
                source.portfolio_config.model_dump(mode="json")
                if source.portfolio_config is not None
                else {}
            ),
            method_params_by_hypothesis=method_params_by_hypothesis,
            skipped_families={
                family.value if hasattr(family, "value") else str(family): reason
                for family, reason in (
                    (
                        portfolio_result.skipped_families if portfolio_result is not None else {}
                    ).items()
                )
            },
            warnings=[
                *(portfolio_result.warnings if portfolio_result is not None else []),
                *source.graph_prior_bundle.warnings,
                *source.prior_knowledge_bundle.warnings,
            ],
            latent_discovery_summary=_summarize_latent_discovery_hypotheses(
                source.hypotheses,
                ranking_order=[
                    score.hypothesis_id for score in source.downstream_utility_report.scores
                ],
                shortlist=list(source.downstream_utility_report.recommended_shortlist),
            ),
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
    """Persist the discovery task profile describing the run's objectives, contexts, and assumptions."""
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
    """Load discovery task profile."""
    return _load_model(store, ref, DiscoveryTaskProfile)


def persist_graph_hypothesis_set(
    store: FileSystemCAS,
    payload: GraphHypothesisSet,
    *,
    inputs: list[InputRef] | None = None,
) -> GraphHypothesisSetRef:
    """Persist the ranked set of graph hypotheses emitted by the discovery workflow."""
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
    """Load graph hypothesis set."""
    return _load_model(store, ref, GraphHypothesisSet)


def persist_refutation_report(
    store: FileSystemCAS,
    payload: RefutationReport,
    *,
    inputs: list[InputRef] | None = None,
) -> RefutationReportRef:
    """Persist the report describing which discovery hypotheses survived refutation checks."""
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
    """Load refutation report."""
    return _load_model(store, ref, RefutationReport)


def persist_reproducibility_report(
    store: FileSystemCAS,
    payload: ReproducibilityReport,
    *,
    inputs: list[InputRef] | None = None,
) -> ReproducibilityReportRef:
    """Persist the reproducibility report covering replay, seeds, and stability checks."""
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
    """Load reproducibility report."""
    return _load_model(store, ref, ReproducibilityReport)


def persist_active_disambiguation_plan(
    store: FileSystemCAS,
    payload: ActiveDisambiguationPlan,
    *,
    inputs: list[InputRef] | None = None,
) -> ActiveDisambiguationPlanRef:
    """Persist the active-disambiguation plan that schedules follow-up data collection or labeling."""
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
    """Load active disambiguation plan."""
    return _load_model(store, ref, ActiveDisambiguationPlan)


def persist_discovery_audit_bundle(
    store: FileSystemCAS,
    payload: DiscoveryAuditBundle,
    *,
    inputs: list[InputRef] | None = None,
) -> DiscoveryAuditBundleRef:
    """Persist the audit bundle that makes a discovery run replayable end to end."""
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
    """Load discovery audit bundle."""
    return _load_model(store, ref, DiscoveryAuditBundle)


def persist_discovery_artifact_bundle(
    store: FileSystemCAS,
    payload: DiscoveryArtifactBundle,
    *,
    inputs: list[InputRef] | None = None,
) -> DiscoveryArtifactBundleRef:
    """Persist the top-level discovery bundle linking hypotheses, reports, and audit refs."""
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
    """Load discovery artifact bundle."""
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


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _ordered_hypothesis_ids(
    hypotheses: list[GraphHypothesis],
    *,
    ranking_order: list[str],
    shortlist: list[str],
) -> list[str]:
    ordered_ids = list(shortlist) if shortlist else list(ranking_order)
    known_ids = {hypothesis.hypothesis_id for hypothesis in hypotheses}
    output: list[str] = []
    seen: set[str] = set()
    for hypothesis_id in ordered_ids:
        if hypothesis_id in known_ids and hypothesis_id not in seen:
            seen.add(hypothesis_id)
            output.append(hypothesis_id)
    for hypothesis in hypotheses:
        if hypothesis.hypothesis_id not in seen:
            seen.add(hypothesis.hypothesis_id)
            output.append(hypothesis.hypothesis_id)
    return output


def _merge_proxy_boundary_payloads(values: list[dict[str, Any]]) -> dict[str, Any]:
    boundary_notes: list[str] = []
    no_promotion_reasons: list[str] = []
    metadata: dict[str, Any] = {}
    for value in values:
        for note in list(value.get("boundary_notes", []) or []):
            note_text = str(note).strip()
            if note_text and note_text not in boundary_notes:
                boundary_notes.append(note_text)
        for reason in list(value.get("no_promotion_reasons", []) or []):
            reason_text = str(reason).strip()
            if reason_text and reason_text not in no_promotion_reasons:
                no_promotion_reasons.append(reason_text)
        for key, payload in value.items():
            if key in {"boundary_notes", "no_promotion_reasons"}:
                continue
            metadata.setdefault(str(key), payload)
    merged: dict[str, Any] = dict(metadata)
    if boundary_notes:
        merged["boundary_notes"] = boundary_notes
    if no_promotion_reasons:
        merged["no_promotion_reasons"] = no_promotion_reasons
    return merged


def _latent_cardinality_payload(metadata: dict[str, Any]) -> dict[str, Any] | None:
    payload = {key: metadata[key] for key in _LATENT_CARDINALITY_METADATA_KEYS if key in metadata}
    return payload or None


def _merge_latent_cardinality_payloads(values: list[dict[str, Any]]) -> dict[str, Any]:
    model_classes: list[str] = []
    status_values: list[str] = []
    latent_blocks: list[dict[str, Any]] = []
    latent_candidates: list[dict[str, Any]] = []
    ambiguity_notes: list[str] = []
    seen_blocks: set[str] = set()
    seen_candidates: set[str] = set()

    for value in values:
        model_class = str(value.get("model_class", "")).strip()
        if model_class and model_class not in model_classes:
            model_classes.append(model_class)
        status = str(value.get("identifiability_status", "")).strip()
        if status:
            status_values.append(status)

        for block in list(value.get("latent_blocks", []) or []):
            if not isinstance(block, dict):
                continue
            key = str(block.get("latent_id") or block)
            if key in seen_blocks:
                continue
            seen_blocks.add(key)
            latent_blocks.append(dict(block))

        for candidate in list(value.get("latent_candidates", []) or []):
            if not isinstance(candidate, dict):
                continue
            key = str(candidate.get("latent_id") or candidate)
            if key in seen_candidates:
                continue
            seen_candidates.add(key)
            latent_candidates.append(dict(candidate))

        for note in list(value.get("ambiguity_notes", []) or []):
            text = str(note).strip()
            if text and text not in ambiguity_notes:
                ambiguity_notes.append(text)

    merged: dict[str, Any] = {}
    if len(model_classes) == 1:
        merged["model_class"] = model_classes[0]
    elif model_classes:
        merged["model_class"] = "mixed"
        merged["model_classes"] = model_classes
    status = _conservative_latent_identifiability_status(status_values)
    if status is not None:
        merged["identifiability_status"] = status
    if latent_blocks:
        merged["latent_blocks"] = latent_blocks
    if latent_candidates:
        merged["latent_candidates"] = latent_candidates
    if ambiguity_notes:
        merged["ambiguity_notes"] = ambiguity_notes
    return merged


def _conservative_latent_identifiability_status(values: list[str]) -> str | None:
    if not values:
        return None
    rank = {"suspected_only": 0, "partial": 1, "partial_or_full": 1, "full": 2}
    return min(values, key=lambda value: rank.get(value, 0))


def _merge_latent_promotion_evidence(
    evidences: list[LatentPromotionEvidence],
) -> LatentPromotionEvidence | None:
    if not evidences:
        return None

    invariance_rank = {
        "none": 0,
        "configural": 1,
        "metric": 2,
        "approximate": 2,
        "scalar": 3,
        "strict": 4,
    }

    def _merge_ref_list(field_name: str) -> list[Any]:
        seen: set[str] = set()
        refs: list[Any] = []
        for evidence in evidences:
            for ref in getattr(evidence, field_name):
                key = str(ref.artifact_id)
                if key in seen:
                    continue
                seen.add(key)
                refs.append(ref)
        return refs

    def _merge_single_ref(field_name: str) -> Any | None:
        values = [
            getattr(evidence, field_name)
            for evidence in evidences
            if getattr(evidence, field_name) is not None
        ]
        if len(values) != len(evidences):
            return None
        return values[0]

    scope_sets = [set(evidence.scope_regime) for evidence in evidences if evidence.scope_regime]
    if len(scope_sets) == len(evidences) and scope_sets:
        scope_regime = sorted(set.intersection(*scope_sets))
    else:
        scope_regime = _dedupe_preserve_order(
            [value for evidence in evidences for value in evidence.scope_regime]
        )

    invariance_level = min(
        (evidence.invariance_level for evidence in evidences),
        key=lambda value: invariance_rank.get(value, 0),
    )

    return LatentPromotionEvidence(
        observable_implication_refs=_merge_ref_list("observable_implication_refs"),
        local_misspecification_test_refs=_merge_ref_list("local_misspecification_test_refs"),
        environment_stability_ref=_merge_single_ref("environment_stability_ref"),
        rival_explanation_audit_ref=_merge_single_ref("rival_explanation_audit_ref"),
        external_evidence_refs=_merge_ref_list("external_evidence_refs"),
        replication_refs=_merge_ref_list("replication_refs"),
        hidden_benchmark_ref=_merge_single_ref("hidden_benchmark_ref"),
        reviewer_decision_ref=_merge_single_ref("reviewer_decision_ref"),
        exclusion_test_refs=_merge_ref_list("exclusion_test_refs"),
        external_anchor_refs=_merge_ref_list("external_anchor_refs"),
        cross_model_robustness_refs=_merge_ref_list("cross_model_robustness_refs"),
        scope_regime=scope_regime,
        invariance_level=invariance_level,
        measurement_scope=all(evidence.measurement_scope for evidence in evidences),
        structural_interpretation_rejected=any(
            evidence.structural_interpretation_rejected for evidence in evidences
        ),
        notes=_dedupe_preserve_order([note for evidence in evidences for note in evidence.notes]),
    )


def merge_latent_discovery_hypotheses(
    hypotheses: list[GraphHypothesis],
    *,
    ranking_order: list[str],
    shortlist: list[str],
) -> LatentDiscoveryBundle | None:
    """Merge latent discovery hypotheses while preserving stronger evidence and metadata."""
    order = _ordered_hypothesis_ids(
        hypotheses,
        ranking_order=ranking_order,
        shortlist=shortlist,
    )
    by_id = {hypothesis.hypothesis_id: hypothesis for hypothesis in hypotheses}
    selected: list[tuple[str, LatentDiscoveryBundle]] = []
    for hypothesis_id in order:
        hypothesis = by_id[hypothesis_id]
        if hypothesis.latent_discovery is not None:
            selected.append((hypothesis_id, hypothesis.latent_discovery))
    if not selected:
        return None

    proposed_latent_nodes: list[str] = []
    inducing_environments: list[str] = []
    identification_conditions: list[str] = []
    falsification_tests: list[str] = []
    no_promotion_reasons: list[str] = []
    source_hypothesis_ids: list[str] = []
    assumption_cards: list[LatentAssumptionCard] = []
    proxy_boundary_payloads: list[dict[str, Any]] = []
    latent_cardinality_payloads: list[dict[str, Any]] = []
    separation_diagnostics_payloads: list[dict[str, Any]] = []
    separation_diagnostics_trusts: list[LatentTrustLevel] = []
    seen_assumptions: set[str] = set()
    trust_rank = {
        LatentTrustLevel.RESEARCH: 0,
        LatentTrustLevel.CONDITIONAL: 1,
        LatentTrustLevel.VALIDATED: 2,
    }
    trust_level = LatentTrustLevel.VALIDATED
    component_promotion_evidence: list[LatentPromotionEvidence] = []
    all_components_have_evidence = True

    for hypothesis_id, bundle in selected:
        bundle_metadata = metadata_with_computed_latent_separation(bundle.metadata)
        source_hypothesis_ids.append(hypothesis_id)
        effective_trust = certify_latent_separation_trust(
            bundle_metadata,
            fallback=bundle.trust_level,
        )
        if trust_rank[effective_trust] < trust_rank[trust_level]:
            trust_level = effective_trust
        if bundle.promotion_evidence is not None:
            component_promotion_evidence.append(bundle.promotion_evidence)
        else:
            all_components_have_evidence = False
        for value in bundle.proposed_latent_nodes:
            text = str(value).strip()
            if text and text not in proposed_latent_nodes:
                proposed_latent_nodes.append(text)
        for value in bundle.inducing_environments:
            text = str(value).strip()
            if text and text not in inducing_environments:
                inducing_environments.append(text)
        for value in bundle.identification_conditions:
            text = str(value).strip()
            if text and text not in identification_conditions:
                identification_conditions.append(text)
        for value in bundle.falsification_tests:
            text = str(value).strip()
            if text and text not in falsification_tests:
                falsification_tests.append(text)
        for value in bundle.no_promotion_reasons:
            text = str(value).strip()
            if text and text not in no_promotion_reasons:
                no_promotion_reasons.append(text)
        for card in bundle.assumption_cards:
            key = card.assumption_id or card.title
            if key in seen_assumptions:
                continue
            seen_assumptions.add(key)
            assumption_cards.append(card)
        proxy_boundary = bundle_metadata.get("proxy_boundary")
        if isinstance(proxy_boundary, dict):
            proxy_boundary_payloads.append(dict(proxy_boundary))
        latent_cardinality = _latent_cardinality_payload(bundle_metadata)
        if latent_cardinality is not None:
            latent_cardinality_payloads.append(latent_cardinality)
        separation_diagnostics = separation_diagnostics_payload(bundle_metadata)
        if separation_diagnostics is not None:
            separation_diagnostics_payloads.append(separation_diagnostics)
            separation_diagnostics_trusts.append(effective_trust)

    metadata: dict[str, Any] = {
        "source_hypothesis_ids": source_hypothesis_ids,
        "merged_from": "discovery_artifact_bundle",
    }
    if proxy_boundary_payloads:
        metadata["proxy_boundary"] = _merge_proxy_boundary_payloads(proxy_boundary_payloads)
    if latent_cardinality_payloads:
        metadata.update(_merge_latent_cardinality_payloads(latent_cardinality_payloads))
    merged_separation_diagnostics = merge_latent_separation_diagnostics_payloads(
        separation_diagnostics_payloads
    )
    if merged_separation_diagnostics is not None:
        metadata[SEPARATION_DIAGNOSTICS_KEY] = merged_separation_diagnostics
        diagnostic_trust = certify_latent_separation_trust(
            metadata,
            fallback=trust_level,
        )
        all_sources_have_diagnostics = len(separation_diagnostics_payloads) == len(selected)
        all_diagnostic_sources_promotable = all(
            trust_rank[value] > trust_rank[LatentTrustLevel.RESEARCH]
            for value in separation_diagnostics_trusts
        )
        if trust_rank[diagnostic_trust] < trust_rank[trust_level] or (
            all_sources_have_diagnostics and all_diagnostic_sources_promotable
        ):
            trust_level = diagnostic_trust

    merged_promotion_evidence = (
        _merge_latent_promotion_evidence(component_promotion_evidence)
        if all_components_have_evidence
        else None
    )
    provisional_bundle = LatentDiscoveryBundle(
        proposed_latent_nodes=proposed_latent_nodes,
        inducing_environments=inducing_environments,
        identification_conditions=identification_conditions,
        falsification_tests=falsification_tests,
        trust_level=trust_level,
        assumption_cards=assumption_cards,
        readiness_cap="proof_only",
        human_gate_required=True,
        promotion_allowed=False,
        no_promotion_reasons=_dedupe_preserve_order(
            [reason for reason in no_promotion_reasons if reason != "latent_discovery_proof_only"]
        ),
        not_for_decision_support=True,
        promotion_evidence=merged_promotion_evidence,
        metadata=metadata,
    )
    promotion_verdict = evaluate_latent_promotion(provisional_bundle)
    resolved_trust_level = trust_level
    if trust_rank[promotion_verdict.derived_trust_level] > trust_rank[resolved_trust_level]:
        resolved_trust_level = promotion_verdict.derived_trust_level
    derived_no_promotion_reasons = _dedupe_preserve_order(
        [
            *provisional_bundle.no_promotion_reasons,
            *(f"latent_promotion_blocker:{value}" for value in promotion_verdict.blockers),
            *(
                ["latent_discovery_proof_only"]
                if promotion_verdict.derived_readiness_cap == "proof_only"
                else []
            ),
        ]
    )
    return provisional_bundle.model_copy(
        update={
            "trust_level": resolved_trust_level,
            "readiness_cap": promotion_verdict.derived_readiness_cap,
            "promotion_allowed": promotion_verdict.promotion_allowed,
            "no_promotion_reasons": derived_no_promotion_reasons,
            "not_for_decision_support": promotion_verdict.not_for_decision_support,
        }
    )


def _summarize_latent_discovery_hypotheses(
    hypotheses: list[GraphHypothesis],
    *,
    ranking_order: list[str],
    shortlist: list[str],
) -> dict[str, Any]:
    merged = merge_latent_discovery_hypotheses(
        hypotheses,
        ranking_order=ranking_order,
        shortlist=shortlist,
    )
    if merged is None:
        return {}
    separation_diagnostics = merged.metadata.get(SEPARATION_DIAGNOSTICS_KEY)
    resolution_label = None
    separated_pairs: list[str] = []
    if isinstance(separation_diagnostics, dict):
        value = separation_diagnostics.get("resolution_label")
        if value is not None:
            resolution_label = str(value)
        raw_pairs = separation_diagnostics.get("separated_pairs")
        if isinstance(raw_pairs, list):
            separated_pairs = [str(item) for item in raw_pairs]
    return {
        "source_hypothesis_ids": list(merged.metadata.get("source_hypothesis_ids", []) or []),
        "proposed_latent_nodes": list(merged.proposed_latent_nodes),
        "inducing_environments": list(merged.inducing_environments),
        "model_class": merged.metadata.get("model_class"),
        "identifiability_status": merged.metadata.get("identifiability_status"),
        "latent_block_count": len(list(merged.metadata.get("latent_blocks", []) or [])),
        "trust_level": merged.trust_level.value,
        "resolution_label": resolution_label,
        "separated_pairs": separated_pairs,
        "readiness_cap": merged.readiness_cap,
        "promotion_allowed": merged.promotion_allowed,
        "human_gate_required": merged.human_gate_required,
    }


def load_graph_hypotheses_for_bundle(
    store: FileSystemCAS,
    bundle: DiscoveryArtifactBundle,
) -> list[GraphHypothesis]:
    """Load graph hypotheses for bundle."""
    hypothesis_set = load_graph_hypothesis_set(store, bundle.graph_hypothesis_set_ref)
    return [load_graph_hypothesis(store, ref) for ref in hypothesis_set.graph_hypothesis_refs]


def load_source_discovery_reports_for_bundle(
    store: FileSystemCAS,
    bundle: DiscoveryArtifactBundle,
) -> dict[str, CausalDiscoveryReport]:
    """Load source discovery reports for bundle."""
    audit_bundle = load_discovery_audit_bundle(store, bundle.discovery_audit_bundle_ref)
    ref_map = dict(audit_bundle.discovery_report_refs_by_hypothesis)
    if not ref_map:
        for hypothesis in load_graph_hypotheses_for_bundle(store, bundle):
            if hypothesis.source_discovery_report_ref is not None:
                ref_map[hypothesis.hypothesis_id] = hypothesis.source_discovery_report_ref
    reports: dict[str, CausalDiscoveryReport] = {}
    for hypothesis_id, ref in ref_map.items():
        reports[hypothesis_id] = load_causal_discovery_report(store, ref)
    return reports


def load_merged_latent_discovery_bundle(
    store: FileSystemCAS,
    bundle: DiscoveryArtifactBundle,
) -> LatentDiscoveryBundle | None:
    """Load merged latent discovery bundle."""
    hypotheses = load_graph_hypotheses_for_bundle(store, bundle)
    hypothesis_set = load_graph_hypothesis_set(store, bundle.graph_hypothesis_set_ref)
    utility_report = load_downstream_utility_report(store, bundle.downstream_utility_report_ref)
    return merge_latent_discovery_hypotheses(
        hypotheses,
        ranking_order=list(hypothesis_set.ranking_order),
        shortlist=list(utility_report.recommended_shortlist),
    )


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
    "DISCOVERY_ARTIFACT_BUNDLE_SCHEMA_NAME",
    "DISCOVERY_AUDIT_BUNDLE_SCHEMA_NAME",
    "DISCOVERY_TASK_PROFILE_SCHEMA_NAME",
    "GRAPH_HYPOTHESIS_SET_SCHEMA_NAME",
    "REFUTATION_REPORT_SCHEMA_NAME",
    "REPRODUCIBILITY_REPORT_SCHEMA_NAME",
    "ActiveDisambiguationConfig",
    "ActiveDisambiguationPlan",
    "ActiveDisambiguationPlanner",
    "ActiveDisambiguationPlannerInput",
    "DiscoveryArtifactBuildInput",
    "DiscoveryArtifactBuilder",
    "DiscoveryArtifactBundle",
    "DiscoveryAuditBundle",
    "DiscoveryTaskProfile",
    "GraphHypothesisSet",
    "RefutationReport",
    "ReproducibilityReport",
    "load_active_disambiguation_plan",
    "load_bootstrap_stability_report",
    "load_discovery_artifact_bundle",
    "load_discovery_audit_bundle",
    "load_discovery_task_profile",
    "load_downstream_utility_report",
    "load_edge_confidence_matrix",
    "load_graph_hypotheses_for_bundle",
    "load_graph_hypothesis_set",
    "load_graph_prior_bundle",
    "load_merged_latent_discovery_bundle",
    "load_prior_knowledge_bundle",
    "load_refutation_report",
    "load_reproducibility_report",
    "load_source_discovery_reports_for_bundle",
    "merge_latent_discovery_hypotheses",
    "persist_active_disambiguation_plan",
    "persist_discovery_artifact_bundle",
    "persist_discovery_audit_bundle",
    "persist_discovery_task_profile",
    "persist_graph_hypothesis_set",
    "persist_refutation_report",
    "persist_reproducibility_report",
]
