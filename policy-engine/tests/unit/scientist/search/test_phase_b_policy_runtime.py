from __future__ import annotations

import importlib
import json
import sys
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.foundry.validation.phase2_closure import PHASE2_CLOSURE_ENV_VAR
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    DataReadinessReport,
    EstimationStatus,
    RefutationResult,
    RefutationTestType,
    build_data_readiness_report,
    persist_data_readiness_report,
)
from polisyos.ir.analytics.causal_discovery import (
    LatentAssumptionCard,
    LatentDiscoveryBundle,
    LatentPromotionEvidence,
    LatentTrustLevel,
)
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    CrossGraphEvidenceSummary,
    EvidenceNeed,
    EvidenceNeedAssessment,
    EvidenceNeedType,
    EvidenceSourceKind,
    EvidenceSourceState,
    EvidenceSourceStatus,
    EvidenceStatus,
    LegalStatus,
    ObservabilityStatus,
    TransportStatus,
)
from polisyos.ir.analytics.distributional import (
    CohortDimension,
    CohortImpact,
    DimensionBreakdown,
    DistributionalReport,
    ImpactDirection,
    MetricUnit,
    WinnersLosersEntry,
    WinnersLosersTable,
)
from polisyos.ir.governance.policy_spec import InterventionSpec, ParameterSpec, PolicySpec
from polisyos.ir.governance.problem_frame import (
    ConstraintSpec,
    ConstraintType,
    KPISpec,
    ObjectiveSpec,
    ProblemDomain,
    ProblemFrame,
)
from polisyos.ir.kernel.values import MoneyValue
from polisyos.ir.model_layer.model_spec import AssumptionSpec, AssumptionType, ModelSpec
from polisyos.ir.model_layer.types import OptimizationDirection, SelectorOperator
from polisyos.ir.registry.refs import (
    ArtifactRefModel,
    OptimizationAmbiguityCertificateRef,
    WelfareBundleRef,
)
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    PromotionPolicy,
    persist_benchmark_evaluation,
)
from polisyos.scientist.methods.autotune.registry import ChampionRegistry
from polisyos.scientist.methods.discovery.priors import (
    PriorKnowledgeBundle,
    PriorKnowledgeSupport,
)
from polisyos.scientist.methods.search.adversarial import PlatformMetaEvaluationReport
from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.judge_stack import (
    JudgeInputBundle,
    JudgeName,
    JudgeStack,
    JudgeVerdict,
    PolicyPromotionCoordinator,
    SingleJudgeVerdict,
)
from polisyos.scientist.methods.search.latent_governance import latent_governance_metadata
from polisyos.scientist.methods.search.objective import CompositeObjective
from polisyos.scientist.methods.search.pareto_registry import (
    ParetoBasisScope,
    ParetoRegistry,
    ParetoRegistrySnapshot,
    ParetoView,
    ParetoViewAssessment,
)
from polisyos.scientist.methods.search.readiness import (
    DecisionReadiness,
    DecisionReadinessEvaluator,
)
from polisyos.scientist.methods.search.stopping import MaxIterations
from polisyos.scientist.methods.search.transfer_context import TransferContext
from polisyos.scientist.methods.search.uncertainty import (
    UncertaintyEnvelope,
    UncertaintyEstimate,
    UncertaintyType,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    PolicyRuntimeEvaluationSafetyError,
    ProductionPolicyEvaluationBackend,
)
from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
    _PolicyRuntimeWorkflowEngine,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.workflows import builder as workflow_builder
from polisyos.scientist.policy_design.objectives import (
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    ObjectiveStack,
    PolicyEvaluationBundle,
    PolicyEvaluationVector,
)
from polisyos.scientist.policy_design.output import (
    ReplayableAuditBundle,
    persist_replayable_audit_bundle,
)
from polisyos.scientist.policy_design.phase3 import Phase3CertificateStatus
from polisyos.scientist.policy_design.schema import (
    BudgetAllocationEntry,
    PolicyCandidateSchema,
    TargetPopulationSpec,
    persist_policy_candidate_schema,
)
from polisyos.scientist.replay.verification import (
    load_replay_verification_report,
    verify_and_persist_replay_bundle,
)


def _artifact_ref(seed: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{seed * 64}",
        kind="scientist.test",
        media_type="application/json",
    )


def _phase3_passed() -> Phase3CertificateStatus:
    return Phase3CertificateStatus(
        welfare_bundle_ref=WelfareBundleRef(
            artifact_id="sha256:" + "a" * 64,
            kind="ir.welfare_bundle",
            media_type="application/json",
        ),
        ambiguity_certificate_ref=OptimizationAmbiguityCertificateRef(
            artifact_id="sha256:" + "b" * 64,
            kind="ir.optimization_ambiguity_certificate",
            media_type="application/json",
        ),
        gate_passed=True,
    )


def _bundle() -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="problem_b",
            domain=ProblemDomain.FISCAL,
            objectives=[
                ObjectiveSpec(
                    objective_id="welfare_objective",
                    metric_id="welfare_metric",
                    direction=OptimizationDirection.MAXIMIZE,
                )
            ],
            kpis=[
                KPISpec(
                    kpi_id="employment_kpi",
                    metric_id="employment_metric",
                    direction=OptimizationDirection.MAXIMIZE,
                )
            ],
            hard_constraints=[
                ConstraintSpec(
                    constraint_id="budget_cap",
                    constraint_type=ConstraintType.HARD,
                    value=MoneyValue(amount=Decimal("100"), currency="USD"),
                    operator="<=",
                    notes=["budget ceiling"],
                )
            ],
        ),
        policy_spec=PolicySpec(
            policy_id="policy_b",
            interventions=[
                InterventionSpec(
                    intervention_id="tax_cut",
                    kind="tax_policy",
                    target={
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    schedule={"start_step": 0, "duration_steps": 3},
                    params={"rate": Decimal("0.1")},
                )
            ],
            parameters=[
                ParameterSpec(
                    param_id="tax_rate",
                    intervention_id="tax_cut",
                    param_path="rate",
                    default_value=Decimal("0.1"),
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_b",
            data_snapshot_ref="sha256:" + "2" * 64,
            assumptions=[
                AssumptionSpec(
                    assumption_id="behavioral_stability",
                    assumption_type=AssumptionType.BEHAVIORAL,
                    description="Agents do not change treatment uptake abruptly.",
                )
            ],
        ),
    )


def _candidate(*, evidence_depth: str = "replicated") -> PolicyCandidateSchema:
    return PolicyCandidateSchema(
        candidate_id="candidate_b",
        trinity_bundle=_bundle(),
        target_population=TargetPopulationSpec(
            population_id="population_b",
            description="General population",
            geography="national",
        ),
        budget_allocation=[
            BudgetAllocationEntry(
                allocation_id="alloc_b",
                intervention_id="tax_cut",
                amount=MoneyValue(amount=Decimal("75"), currency="USD"),
            )
        ],
        metadata={"evidence_depth": evidence_depth, "interpretability_score": 0.8},
    )


def _distributional_report() -> DistributionalReport:
    return DistributionalReport(
        breakdowns=[
            DimensionBreakdown(
                dimension=CohortDimension.INCOME_QUINTILE,
                dimension_label="Income quintiles",
                primary_metric="income",
                primary_metric_unit=MetricUnit.PERCENT,
                cohorts=[
                    CohortImpact(
                        cohort_id="low_income",
                        cohort_label="Low income",
                        population_share=0.5,
                        metric_deltas={"income": 1.5},
                        impact_direction=ImpactDirection.POSITIVE,
                        is_vulnerable=True,
                    ),
                    CohortImpact(
                        cohort_id="high_income",
                        cohort_label="High income",
                        population_share=0.5,
                        metric_deltas={"income": 1.0},
                        impact_direction=ImpactDirection.POSITIVE,
                    ),
                ],
                gini_before=0.30,
                gini_after=0.31,
            )
        ],
        winners_losers=WinnersLosersTable(
            winners=[
                WinnersLosersEntry(
                    cohort_id="low_income",
                    cohort_label="Low income",
                    dimension=CohortDimension.INCOME_QUINTILE,
                    net_impact=1.5,
                    impact_direction=ImpactDirection.POSITIVE,
                    population_share=0.5,
                    is_vulnerable=True,
                    key_metric="income",
                    key_metric_delta=1.5,
                ),
                WinnersLosersEntry(
                    cohort_id="high_income",
                    cohort_label="High income",
                    dimension=CohortDimension.INCOME_QUINTILE,
                    net_impact=1.0,
                    impact_direction=ImpactDirection.POSITIVE,
                    population_share=0.5,
                    key_metric="income",
                    key_metric_delta=1.0,
                ),
            ]
        ),
        overall_gini_before=0.30,
        overall_gini_after=0.31,
    )


def _causal_effect_report() -> CausalEffectReport:
    return CausalEffectReport(
        method=CausalMethod.DOWHY_BACKDOOR,
        status=EstimationStatus.SUCCESS,
        estimand="ATE",
        point_estimate=1.2,
        confidence_interval=(1.0, 1.4),
        inference_method="bootstrap",
        refutation_results=[
            RefutationResult(
                test_type=test_type,
                original_estimate=1.2,
                refuted_estimate=1.15,
                passed=True,
                effect_ratio=0.95,
            )
            for test_type in (
                RefutationTestType.PLACEBO_TREATMENT,
                RefutationTestType.RANDOM_COMMON_CAUSE,
                RefutationTestType.DATA_SUBSET,
                RefutationTestType.BOOTSTRAP,
            )
        ],
        method_params={"source_type": "external", "treatment": "tax_rate"},
        sample_size=250,
        n_treated=125,
        n_control=125,
        pre_periods=1,
        post_periods=1,
    )


def _cross_graph_profile() -> CrossGraphEvidenceProfile:
    return CrossGraphEvidenceProfile(
        summary=CrossGraphEvidenceSummary(total_needs=1),
        needs=[
            EvidenceNeedAssessment(
                need=EvidenceNeed(
                    need_id="need_b",
                    need_type=EvidenceNeedType.OBJECTIVE_METRIC,
                    source_path="problem_frame.objectives[0]",
                    metric_id="welfare_metric",
                ),
                legal_status=LegalStatus.ALLOWED,
                observability_status=ObservabilityStatus.DIRECT,
                evidence_status=EvidenceStatus.SUPPORTED,
                transport_status=TransportStatus.IDENTIFIED,
                confidence=0.9,
            )
        ],
        source_statuses={
            "academic": EvidenceSourceStatus(
                source=EvidenceSourceKind.ACADEMIC,
                configured=True,
                status=EvidenceSourceState.AVAILABLE,
            )
        },
    )


def _prior_knowledge_bundle(
    *, status: str = "ok", coverage_complete: bool = True
) -> PriorKnowledgeBundle:
    unresolved = [] if coverage_complete else ["X->Y"]
    support_rows = (
        [
            PriorKnowledgeSupport(
                edge_key="X->Y",
                src="X",
                dst="Y",
                direction="positive",
                confidence=0.9,
                n_articles=3,
                evidence_strength="meta_analysis",
                article_refs=["oa:1"],
            )
        ]
        if status == "ok"
        else []
    )
    return PriorKnowledgeBundle(
        status=status,
        query_edge_keys=["X->Y"],
        unresolved_edges=unresolved,
        support_rows=support_rows,
        source_statuses={
            "academic": EvidenceSourceStatus(
                source=EvidenceSourceKind.ACADEMIC,
                configured=status == "ok",
                status=(
                    EvidenceSourceState.AVAILABLE
                    if status == "ok"
                    else EvidenceSourceState.MISSING_CONFIG
                ),
            )
        },
    )


def _uncertainty(level: float = 0.2) -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        uncertainties={
            uncertainty_type: UncertaintyEstimate(
                level=level,
                source="test",
                quantification_method="manual",
                is_reducible=True,
            )
            for uncertainty_type in UncertaintyType
        }
    )


def _passed_judge_verdict() -> JudgeVerdict:
    judge_names = (
        "structural",
        "statistical",
        "robustness",
        "governance",
        "reproducibility",
        "compute",
    )
    return JudgeVerdict(
        per_judge={
            name: SingleJudgeVerdict(judge_name=name, passed=True, is_fatal=True)
            for name in judge_names
        },
        composite_decision="promote",
    )


def _benchmark(
    candidate_ref: ArtifactRef, *, holdout_score: float = 0.94
) -> tuple[BenchmarkEvaluation, BenchmarkEvaluation]:
    selection = BenchmarkEvaluation(
        loop_id="policy_loop",
        suite_id="suite_a",
        candidate_ref=candidate_ref,
        selection_metrics={"score": 0.95},
        holdout_metrics={"score": 0.94},
        sample_counts={
            BenchmarkSplit.SELECTION.value: 120,
            BenchmarkSplit.HOLDOUT.value: 80,
            BenchmarkSplit.HIDDEN_HOLDOUT.value: 80,
        },
        promotable=True,
        runtime_split_type=BenchmarkSplit.SELECTION,
        metadata={"lineage_complete": True},
    )
    hidden_holdout = BenchmarkEvaluation(
        loop_id="policy_loop",
        suite_id="suite_a_hidden",
        candidate_ref=candidate_ref,
        selection_metrics={"score": 0.95},
        holdout_metrics={"score": holdout_score},
        sample_counts={
            BenchmarkSplit.HOLDOUT.value: 40,
            BenchmarkSplit.HIDDEN_HOLDOUT.value: 40,
        },
        promotable=True,
        runtime_split_type=BenchmarkSplit.HIDDEN_HOLDOUT,
        metadata={"lineage_complete": True},
    )
    return selection, hidden_holdout


def _write_phase2_closure_report(
    path,
    *,
    artifact_family: str,
    passes_all: bool,
    status: str,
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "assessment_id": "foundry_phase2_closure",
                "phase_id": "foundry.phase2",
                "overall_status": "complete" if passes_all else "incomplete",
                "manifest_path": "tools/quality/validation/foundry_phase2_manifest.json",
                "acceptance_junit_xml": "foundry_phase2_acceptance.xml",
                "benchmark_report": "foundry_phase2_benchmarks.json",
                "evidence_report": "foundry_phase2_evidence.json",
                "source_of_truth": {},
                "tracks": {},
                "artifact_families": {
                    artifact_family: {
                        "artifact_family": artifact_family,
                        "applies_to": [artifact_family],
                        "blocking_transition": "PROOF_ONLY->ENGINEER_READY",
                        "passes_all": passes_all,
                        "status": status,
                        "track_ids": ["P2.synthetic"],
                    }
                },
                "notes": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _evaluation_vector(candidate: PolicyCandidateSchema):
    stack = ObjectiveStack()
    return stack.evaluate(
        PolicyEvaluationBundle(
            candidate=candidate,
            simulation_metrics={"policy_value": 12.0, "employment_rate": 0.91, "welfare": 13.0},
            distributional_report=_distributional_report(),
            causal_effect_report=_causal_effect_report(),
            cross_graph_profile=_cross_graph_profile(),
            uncertainty_envelope=_uncertainty(0.2),
        )
    )


def _declared_global_pareto_basis() -> ParetoBasisScope:
    return ParetoBasisScope(
        scope="declared",
        coordinate_ids=["policy_value", "employment"],
        basis_ref="test:objective-stack.global-feasible.v1",
    )


def _persist_replay_support(
    store: FileSystemCAS,
    *,
    candidate_ref: ArtifactRef,
    evaluation_ref: ArtifactRef,
    monkeypatch,
    run_id: str = "policy_promotion",
) -> tuple[ArtifactRef, ArtifactRef]:
    """Persist a measured replay using a controlled executor over the same CAS evaluation."""
    runtime_input_ref = store.put_json(
        {"decision_packet": "controlled-replay-input"},
        PutOptions(kind="scientist.runtime_input", media_type="application/json"),
        return_selected_profile=True,
    )
    replay_ref = persist_replayable_audit_bundle(
        store,
        ReplayableAuditBundle(
            run_id=run_id,
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
            workflow_id="policy_design",
            execution_profile="full",
            runtime_input_refs={"decision_packet": runtime_input_ref},
            runtime_params_snapshot={"workflow_id": "policy_design"},
        ),
    )

    def _run_selected_workflow(*, initial_state, store):
        del store
        assert initial_state.inputs["decision_packet"] == runtime_input_ref
        assert initial_state.params["replay_mode"] is True
        return SimpleNamespace(
            state=SimpleNamespace(
                params={"policy_evaluation_ref": evaluation_ref},
                artifacts_index={},
                reports_index={},
            )
        )

    monkeypatch.setattr(workflow_builder, "run_selected_workflow", _run_selected_workflow)
    verification_ref = verify_and_persist_replay_bundle(
        store,
        run_id=run_id,
        replay_bundle_ref=replay_ref,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
    )
    report = load_replay_verification_report(store, verification_ref)
    assert report.verification_mode == "semantic_diff"
    assert report.passed is True
    assert report.overall_similarity == 1.0
    return replay_ref, verification_ref


def _latent_bundle(*, complete: bool = True) -> LatentDiscoveryBundle:
    return LatentDiscoveryBundle(
        proposed_latent_nodes=["U_labor_market"],
        inducing_environments=["region_a", "region_b"],
        identification_conditions=["environmental shift is exogenous"],
        falsification_tests=(["negative_control_outcome"] if complete else []),
        trust_level=LatentTrustLevel.RESEARCH,
        assumption_cards=(
            [
                LatentAssumptionCard(
                    assumption_id="latent_shift_exogeneity",
                    title="Shift exogeneity",
                    description="Regional shift is not downstream of the proposed policy.",
                    evidence_basis=["design_note:regional_comparison"],
                    falsification_hook="check baseline covariate balance",
                )
            ]
            if complete
            else []
        ),
        no_promotion_reasons=["latent_discovery_proof_only"],
    )


def _latent_promotion_ref(ch: str, *, kind: str) -> ArtifactRefModel:
    seed = ch.lower()
    if seed not in "0123456789abcdef":
        seed = format(sum(ord(symbol) for symbol in seed) % 16, "x")
    return ArtifactRefModel(
        artifact_id=f"sha256:{seed * 64}",
        kind=kind,
        media_type="application/json",
    )


def _conditional_latent_bundle() -> LatentDiscoveryBundle:
    return LatentDiscoveryBundle(
        proposed_latent_nodes=["U_labor_market"],
        inducing_environments=["region_a", "region_b"],
        identification_conditions=["environmental shift is exogenous"],
        falsification_tests=["negative_control_outcome"],
        trust_level=LatentTrustLevel.CONDITIONAL,
        assumption_cards=[
            LatentAssumptionCard(
                assumption_id="latent_shift_exogeneity",
                title="Shift exogeneity",
                description="Regional shift is not downstream of the proposed policy.",
                evidence_basis=["design_note:regional_comparison"],
                falsification_hook="check baseline covariate balance",
            )
        ],
        readiness_cap="bounds_ready",
        promotion_allowed=True,
        no_promotion_reasons=[],
        not_for_decision_support=False,
        promotion_evidence=LatentPromotionEvidence(
            observable_implication_refs=[
                _latent_promotion_ref("a", kind="scientist.latent.observable_implication")
            ],
            local_misspecification_test_refs=[
                _latent_promotion_ref("b", kind="scientist.latent.local_misspecification")
            ],
            environment_stability_ref=_latent_promotion_ref(
                "c", kind="scientist.latent.environment_stability"
            ),
            rival_explanation_audit_ref=_latent_promotion_ref(
                "d", kind="scientist.latent.rival_explanation_audit"
            ),
            external_evidence_refs=[
                _latent_promotion_ref("e", kind="scientist.latent.external_evidence")
            ],
            replication_refs=[_latent_promotion_ref("f", kind="scientist.latent.replication")],
            hidden_benchmark_ref=_latent_promotion_ref(
                "g", kind="scientist.latent.hidden_benchmark"
            ),
            reviewer_decision_ref=_latent_promotion_ref(
                "h", kind="scientist.latent.reviewer_decision"
            ),
            scope_regime=["linear_nongaussian", "metric_invariant"],
            invariance_level="metric",
        ),
    )


def _latent_separation_diagnostics() -> dict[str, object]:
    return {
        "resolution_label": "latent_confounding",
        "design": {
            "n_env": 2,
            "proxy_blocks": ["W", "Z"],
            "repeated_indicator_blocks": ["R"],
        },
        "measurement_block": {
            "status": "passed",
            "tetrad_test": "single_signal_tetrad_passed",
            "invariance_test": "measurement_invariance_passed",
        },
        "proxy_block": {
            "status": "passed",
            "bridge_test": "proximal_bridge_solved",
            "bridge_stability": "cross_environment_stable",
        },
        "environment_block": {
            "status": "passed",
            "residual_invariance": "post_calibration_residual_invariance_failed",
            "post_calibration_shift": "not_restored",
        },
        "separated_pairs": ["measurement_vs_confounding"],
    }


def test_pareto_registry_tracks_frontiers_and_voi_snapshot(tmp_path) -> None:
    registry = ParetoRegistry(root=tmp_path / "pareto")
    candidate = _candidate()
    vector_a = _evaluation_vector(candidate)
    vector_b = vector_a.model_copy(
        update={
            "candidate_id": "candidate_c",
            "primary": {
                **vector_a.primary,
                "policy_value": vector_a.primary["policy_value"].model_copy(update={"value": 9.0}),
                "employment": vector_a.primary["employment"].model_copy(update={"value": 0.85}),
            },
        }
    )
    vector_c = vector_a.model_copy(
        update={
            "candidate_id": "candidate_d",
            "primary": {
                **vector_a.primary,
                "policy_value": vector_a.primary["policy_value"].model_copy(update={"value": 10.0}),
                "employment": vector_a.primary["employment"].model_copy(update={"value": 0.95}),
            },
            "secondary": {
                **vector_a.secondary,
                "inequality": vector_a.secondary["inequality"].model_copy(update={"value": 0.005}),
                "simplicity": vector_a.secondary["simplicity"].model_copy(update={"value": 0.95}),
            },
        }
    )
    vector_bad = vector_a.model_copy(
        update={
            "candidate_id": "candidate_bad",
            "feasible": False,
            "blocking_reasons": ["statistical_constraint"],
        }
    )

    registry.update(
        "loop",
        candidate_hash="sha256:" + "a" * 64,
        evaluation=vector_a,
        candidate_id="candidate_b",
        objective_basis_by_view={
            "global_feasible": _declared_global_pareto_basis(),
        },
    )
    registry.update(
        "loop", candidate_hash="sha256:" + "b" * 64, evaluation=vector_b, candidate_id="candidate_c"
    )
    registry.update(
        "loop", candidate_hash="sha256:" + "c" * 64, evaluation=vector_c, candidate_id="candidate_d"
    )
    registry.update(
        "loop",
        candidate_hash="sha256:" + "d" * 64,
        evaluation=vector_bad,
        candidate_id="candidate_bad",
    )

    global_frontier = registry.get_frontier("loop", ParetoView.GLOBAL_FEASIBLE)
    assert {entry.candidate_id for entry in global_frontier} == {"candidate_b", "candidate_d"}
    assert all(entry.evaluation.feasible for entry in global_frontier)

    equity_frontier = registry.get_frontier("loop", ParetoView.EQUITY_AWARE)
    assert {entry.candidate_id for entry in equity_frontier} == {"candidate_b", "candidate_d"}

    snapshot = registry.to_voi_snapshot("loop")
    assert "sha256:" + "a" * 64 in snapshot.frontier_candidate_hashes
    assert "sha256:" + "c" * 64 in snapshot.frontier_candidate_hashes
    assert "sha256:" + "b" * 64 in snapshot.near_frontier_candidate_hashes
    assert "sha256:" + "d" * 64 in snapshot.dominated_candidate_hashes


def test_pareto_registry_keeps_missing_axis_typed_unassessed(tmp_path) -> None:
    registry = ParetoRegistry(root=tmp_path / "pareto")
    candidate = _candidate()
    template = _evaluation_vector(candidate)
    complete = template.model_copy(
        update={
            "candidate_id": "complete",
            "primary": {
                "policy_value": template.primary["policy_value"].model_copy(update={"value": 1.0}),
                "employment": template.primary["employment"].model_copy(update={"value": 1.0}),
            },
        }
    )
    complete_hash = "sha256:" + "f" * 64
    registry.update(
        "loop",
        candidate_hash=complete_hash,
        evaluation=complete,
        objective_basis_by_view={
            "global_feasible": _declared_global_pareto_basis(),
        },
    )

    missing_hashes = ["sha256:" + f"{index:064x}" for index in range(1, 7)]
    for index, candidate_hash in enumerate(missing_hashes, start=2):
        source = template
        unassessed = source.model_copy(
            update={
                "candidate_id": f"missing_{index}",
                "primary": {
                    "policy_value": source.primary["policy_value"].model_copy(
                        update={"value": float(index)}
                    ),
                },
            }
        )
        registry.update("loop", candidate_hash=candidate_hash, evaluation=unassessed)

    empty_axes_hash = "sha256:" + "0" * 64
    no_primary = template.model_copy(update={"candidate_id": "no_primary", "primary": {}})
    assert PolicyEvaluationVector().frontier_objectives("global_feasible") == {}
    registry.update("loop", candidate_hash=empty_axes_hash, evaluation=no_primary)

    no_axis_registry = ParetoRegistry(root=tmp_path / "no-axis")
    no_axis_registry.update("empty", candidate_hash=empty_axes_hash, evaluation=no_primary)
    no_axis_assessment = no_axis_registry.get_snapshot("empty").view_assessments["global_feasible"]

    snapshot = registry.get_snapshot("loop")
    view = snapshot.view_assessments["global_feasible"]
    projection = snapshot.project_view(ParetoView.GLOBAL_FEASIBLE)
    voi_snapshot = registry.to_voi_snapshot("loop")

    assert snapshot.schema_version == "3.0"
    assert view.status == "partial"
    assert view.input_count == 8
    assert view.assessed_count == 1
    assert set(view.unassessed_candidate_hashes) == (set(missing_hashes) | {empty_axes_hash})
    assert view.missing_coordinate_ids_by_candidate_hash
    assert complete_hash in snapshot.frontiers["global_feasible"]
    assert projection.assessment == view
    assert projection.candidate_frontier_hashes == (complete_hash,)
    assert projection.ranked_frontier_hashes == ()
    assert set(projection.eligible_candidate_hashes) == {
        complete_hash,
        *missing_hashes,
        empty_axes_hash,
    }
    assert set(projection.unassessed_candidate_hashes) == set(missing_hashes) | {empty_axes_hash}
    assert voi_snapshot.assessment_status == "partial"
    assert not voi_snapshot.frontier_candidate_hashes
    assert voi_snapshot.position_for(complete_hash) == "unassessed"
    assert voi_snapshot.position_for(missing_hashes[0]) == "unassessed"
    assert missing_hashes[0] not in voi_snapshot.dominated_candidate_hashes
    assert voi_snapshot.position_for(empty_axes_hash) == "unassessed"
    assert no_axis_assessment.status == "basis_limited"
    assert no_axis_assessment.basis_scope.scope == "not_established"
    assert no_axis_assessment.coverage_status == "no_usable_inputs"
    assert no_axis_assessment.unresolved_axis_contract_candidate_hashes == [empty_axes_hash]


def test_pareto_registry_observed_axis_union_is_not_complete(tmp_path) -> None:
    registry = ParetoRegistry(root=tmp_path / "pareto")
    template = _evaluation_vector(_candidate())
    candidate_hashes = ["sha256:" + "1" * 64, "sha256:" + "2" * 64]
    for index, candidate_hash in enumerate(candidate_hashes):
        evaluation = template.model_copy(
            update={
                "candidate_id": f"observed_only_{index}",
                "primary": {"policy_value": template.primary["policy_value"]},
            }
        )
        registry.update("observed-only", candidate_hash=candidate_hash, evaluation=evaluation)

    snapshot = registry.get_snapshot("observed-only")
    assessment = snapshot.view_assessments["global_feasible"]
    projection = snapshot.project_view(ParetoView.GLOBAL_FEASIBLE)
    voi_snapshot = registry.to_voi_snapshot("observed-only")

    assert assessment.status == "basis_limited"
    assert assessment.coverage_status == "complete"
    assert assessment.basis_scope.scope == "observed_axis_union"
    assert assessment.basis_scope.coordinate_ids == ["policy_value"]
    assert projection.assessment == assessment
    assert projection.ranked_frontier_hashes == ()
    assert projection.eligible_candidate_hashes == tuple(sorted(candidate_hashes))
    assert set(projection.unassessed_candidate_hashes) == set(candidate_hashes)
    assert set(voi_snapshot.unassessed_candidate_hashes) == set(candidate_hashes)
    assert not voi_snapshot.frontier_candidate_hashes
    assert all(voi_snapshot.position_for(item) == "unassessed" for item in candidate_hashes)


def test_pareto_registry_declared_basis_omissions_stay_unassessed_and_finite_control_ranks(
    tmp_path,
) -> None:
    template = _evaluation_vector(_candidate())
    declared_basis = _declared_global_pareto_basis()
    missing_registry = ParetoRegistry(root=tmp_path / "missing")
    missing_hashes = ["sha256:" + "3" * 64, "sha256:" + "4" * 64]
    for index, candidate_hash in enumerate(missing_hashes):
        evaluation = template.model_copy(
            update={
                "candidate_id": f"missing_employment_{index}",
                "primary": {"policy_value": template.primary["policy_value"]},
            }
        )
        missing_registry.update(
            "missing-basis-axis",
            candidate_hash=candidate_hash,
            evaluation=evaluation,
            objective_basis_by_view={"global_feasible": declared_basis},
        )

    missing_assessment = missing_registry.get_snapshot("missing-basis-axis").view_assessments[
        "global_feasible"
    ]
    missing_voi = missing_registry.to_voi_snapshot("missing-basis-axis")

    assert missing_assessment.basis_scope == declared_basis
    assert missing_assessment.status == "no_usable_inputs"
    assert missing_assessment.coverage_status == "no_usable_inputs"
    assert set(missing_assessment.unassessed_candidate_hashes) == set(missing_hashes)
    missing_coordinate_sets = [
        missing_assessment.missing_coordinate_ids_by_candidate_hash[item] for item in missing_hashes
    ]
    assert all(len(coordinates) == 1 for coordinates in missing_coordinate_sets)
    assert len({coordinates[0] for coordinates in missing_coordinate_sets}) == 1
    assert set(missing_voi.unassessed_candidate_hashes) == set(missing_hashes)
    assert not missing_voi.frontier_candidate_hashes

    finite_registry = ParetoRegistry(root=tmp_path / "finite")
    finite_hashes = ["sha256:" + "5" * 64, "sha256:" + "6" * 64]
    for index, candidate_hash in enumerate(finite_hashes):
        evaluation = template.model_copy(
            update={
                "candidate_id": f"finite_{index}",
                "primary": {
                    "policy_value": template.primary["policy_value"].model_copy(
                        update={"value": float(index + 1)}
                    ),
                    "employment": template.primary["employment"].model_copy(
                        update={"value": float(index + 1)}
                    ),
                },
            }
        )
        finite_registry.update(
            "finite-control",
            candidate_hash=candidate_hash,
            evaluation=evaluation,
            objective_basis_by_view={"global_feasible": declared_basis},
        )

    finite_snapshot = finite_registry.get_snapshot("finite-control")
    finite_assessment = finite_snapshot.view_assessments["global_feasible"]
    finite_projection = finite_snapshot.project_view(ParetoView.GLOBAL_FEASIBLE)
    finite_voi = finite_registry.to_voi_snapshot("finite-control")
    assert finite_assessment.status == "complete"
    assert finite_assessment.coverage_status == "complete"
    assert finite_snapshot.frontiers["global_feasible"] == [finite_hashes[1]]
    assert set(finite_projection.ranked_frontier_hashes) == {finite_hashes[1]}
    assert finite_projection.eligible_candidate_hashes == tuple(sorted(finite_hashes))
    assert not finite_projection.unassessed_candidate_hashes
    assert finite_voi.position_for(finite_hashes[1]) == "frontier"


def test_v1_pareto_registry_projection_excludes_v2_assessment_fields() -> None:
    historical = ParetoRegistrySnapshot(schema_version="1.0", loop_id="historical")

    payload = historical.historical_v1_payload()

    assert payload["schema_version"] == "1.0"
    assert set(payload) == {
        "schema_version",
        "loop_id",
        "task_family",
        "domain",
        "updated_at",
        "entries",
        "frontiers",
        "hypervolume_by_view",
    }
    assert ParetoRegistrySnapshot.model_validate(payload).schema_version == "1.0"


def test_basisless_v2_assessment_is_limited_on_read() -> None:
    assessment = ParetoViewAssessment(
        status="complete",
        input_count=1,
        assessed_count=1,
    )

    assert assessment.status == "basis_limited"
    assert assessment.coverage_status == "complete"
    assert assessment.basis_scope.scope == "not_established"


def test_judge_stack_reduced_mode_and_human_gate() -> None:
    candidate = _candidate()
    vector = _evaluation_vector(candidate)
    bundle = JudgeInputBundle(
        candidate=candidate,
        evaluation_vector=vector,
        causal_effect_report=_causal_effect_report(),
        distributional_report=_distributional_report(),
        cross_graph_profile=_cross_graph_profile(),
        uncertainty_envelope=_uncertainty(0.2),
        candidate_ref=_artifact_ref("a"),
        evaluation_ref=_artifact_ref("b"),
        governance_report={"verdict": "human_gate", "issues": []},
        state={
            "checkpoints": [
                {"stage": "data_loaded", "timestamp": "2026-03-25T10:00:00Z"},
                {"stage": "estimation_complete", "timestamp": "2026-03-25T10:01:00Z"},
            ],
            "verified_claims": [{"source_ref": "source:1", "confidence": 0.9}],
            "data_sources": [{"name": "dataset", "last_updated": "2026-03-01T00:00:00+00:00"}],
            "knowledge_metadata": {"last_updated": "2026-03-01T00:00:00+00:00"},
            "pii_scan_results": {"max_severity": "none", "total_entities_found": 0},
            "audit_lineage_complete": True,
        },
    )
    stack = JudgeStack()

    reduced = stack.evaluate(bundle, active_judges={JudgeName.STRUCTURAL})
    assert reduced.composite_decision == "reject"
    assert reduced.per_judge["governance"].failure_card.failure_type == "judge_unavailable"

    full = stack.evaluate(bundle)
    assert full.composite_decision == "defer_to_human"
    assert full.per_judge["governance"].failure_card.failure_type == "human_gate_required"


def test_statistical_judge_emits_threshold_metrics_and_violations() -> None:
    candidate = _candidate()
    candidate_ref = _artifact_ref("a")
    selection_eval, _ = _benchmark(candidate_ref)
    bundle = JudgeInputBundle(
        candidate=candidate,
        benchmark_evaluation=selection_eval,
        data_readiness_report=build_data_readiness_report(
            sample_size=120,
            measurement_quality="known_good",
            fallback_data_available=True,
        ),
        uncertainty_envelope=_uncertainty(0.8),
        candidate_ref=candidate_ref,
        evaluation_ref=_artifact_ref("b"),
    )
    stack = JudgeStack()

    verdict = stack.evaluate(bundle, active_judges={JudgeName.STATISTICAL})
    statistical = verdict.per_judge["statistical"]

    assert statistical.metrics["statistical_uncertainty_level"] == 0.8
    assert statistical.thresholds["statistical_uncertainty_level"] == 0.5
    assert "statistical_uncertainty_level" in statistical.violations
    assert statistical.escalation_level == "fatal"


def test_structural_judge_surfaces_dp_bounds_only_for_proof_mode() -> None:
    candidate = _candidate()
    bundle = JudgeInputBundle(
        candidate=candidate,
        claim_mode="proof_only",
        data_readiness_report=DataReadinessReport(
            decision="warn",
            can_compile_estimation=True,
            can_run_estimation=False,
            sample_size=120,
            measurement_quality="known_good",
            fallback_data_available=True,
            warnings=["dp_bounds_only"],
            dp_distortion={
                "effective_status": "bounded",
                "reason": "DP distortion exceeds the point-estimate tolerance.",
                "block_reason": None,
                "distortion_radius": 0.0125,
                "mechanism_family": "laplace",
                "effect_interval": [-0.2, 0.1],
            },
        ),
        uncertainty_envelope=_uncertainty(0.1),
        candidate_ref=_artifact_ref("a"),
        evaluation_ref=_artifact_ref("b"),
    )

    verdict = JudgeStack().evaluate(bundle, active_judges={JudgeName.STRUCTURAL})
    structural = verdict.per_judge["structural"]

    assert structural.passed is True
    assert structural.metrics["dp_distortion_radius"] == 0.0125
    assert structural.metrics["dp_release_identified"] == 0.0
    assert any(card.failure_type == "dp_release_bounded" for card in structural.warnings)


def test_platform_meta_eval_only_blocks_when_report_is_attached() -> None:
    candidate = _candidate()
    vector = _evaluation_vector(candidate)
    base_kwargs = dict(
        candidate=candidate,
        evaluation_vector=vector,
        causal_effect_report=_causal_effect_report(),
        distributional_report=_distributional_report(),
        cross_graph_profile=_cross_graph_profile(),
        uncertainty_envelope=_uncertainty(0.2),
        candidate_ref=_artifact_ref("a"),
        evaluation_ref=_artifact_ref("b"),
        governance_report={"verdict": "approve", "issues": []},
        state={
            "checkpoints": [{"stage": "data_loaded", "timestamp": "2026-03-25T10:00:00Z"}],
            "verified_claims": [{"source_ref": "source:1", "confidence": 0.9}],
            "data_sources": [{"name": "dataset", "last_updated": "2026-03-01T00:00:00+00:00"}],
            "knowledge_metadata": {"last_updated": "2026-03-01T00:00:00+00:00"},
            "pii_scan_results": {"max_severity": "none", "total_entities_found": 0},
            "audit_lineage_complete": True,
        },
    )
    stack = JudgeStack()

    without_report = stack.evaluate(JudgeInputBundle(**base_kwargs))
    assert not any(
        card.failure_type == "platform_meta_evaluation_failed"
        for card in without_report.blocking_failures
    )

    with_report = stack.evaluate(
        JudgeInputBundle(
            **base_kwargs,
            platform_meta_evaluation_report=PlatformMetaEvaluationReport(
                overall_status="failed",
                promotion_safe=False,
                attack_results=[],
                triggered_guards=["PROMOTION_BAN"],
            ),
        )
    )
    assert any(
        card.failure_type == "platform_meta_evaluation_failed"
        for card in with_report.blocking_failures
    )


def test_promotion_coordinator_persists_readiness_and_requires_canonical_n9(
    tmp_path, monkeypatch
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "search_registry", store=store)
    coordinator = PolicyPromotionCoordinator(champion_registry=registry, store=store)

    candidate = _candidate(evidence_depth="replicated")
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    selection_eval, hidden_holdout = _benchmark(candidate_ref, holdout_score=0.94)
    evaluation_ref = persist_benchmark_evaluation(
        store, selection_eval, return_selected_profile=True
    )
    replay_ref, replay_verification_ref = _persist_replay_support(
        store,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        monkeypatch=monkeypatch,
    )
    vector = _evaluation_vector(candidate)
    bundle = coordinator.build_input_bundle(
        candidate=candidate,
        phase3_gate=_phase3_passed(),
        benchmark_evaluation=selection_eval,
        hidden_holdout_evaluation=hidden_holdout,
        evaluation_vector=vector,
        distributional_report=_distributional_report(),
        causal_effect_report=_causal_effect_report(),
        data_readiness_report=build_data_readiness_report(
            sample_size=120,
            measurement_quality="known_good",
            fallback_data_available=True,
        ),
        cross_graph_profile=_cross_graph_profile(),
        prior_knowledge_bundle=_prior_knowledge_bundle(status="ok", coverage_complete=True),
        governance_report={"verdict": "approve", "issues": []},
        uncertainty_envelope=_uncertainty(0.1),
        replay_bundle_ref=replay_ref,
        replay_verification_ref=replay_verification_ref,
        budget_state=BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("10.0"))},
            spent={"run": Decimal("1.0")},
        ),
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        state={
            "checkpoints": [
                {"stage": "data_loaded", "timestamp": "2026-03-25T10:00:00Z"},
                {"stage": "estimation_complete", "timestamp": "2026-03-25T10:01:00Z"},
            ],
            "verified_claims": [{"source_ref": "source:1", "confidence": 0.9}],
            "data_sources": [{"name": "dataset", "last_updated": "2026-03-01T00:00:00+00:00"}],
            "knowledge_metadata": {"last_updated": "2026-03-01T00:00:00+00:00"},
            "pii_scan_results": {"max_severity": "none", "total_entities_found": 0},
            "audit_lineage_complete": True,
        },
        compute_cost_usd=1.0,
        replay_cost_usd=0.5,
        expected_improvement=2.0,
        timeout_risk=0.1,
    )

    result = coordinator.coordinate_promotion(
        loop_id="policy_loop",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        promotion_policy=PromotionPolicy(loop_id="policy_loop", primary_metric="score"),
        judge_input=bundle,
    )

    assert result.promotion_decision.promoted is False
    assert result.promotion_decision.reason == "canonical_n9_promotion_sequence_required"
    assert result.judge_verdict_ref is not None
    assert result.readiness_contract.readiness_level == DecisionReadiness.DEPLOYMENT_READY
    assert result.readiness_ref is not None
    expected_candidate_evaluation_edges = [
        input_ref_from_artifact_ref(candidate_ref, role="candidate"),
        input_ref_from_artifact_ref(evaluation_ref, role="evaluation"),
    ]
    assert store.get_manifest(result.judge_verdict_ref).inputs[:2] == (
        expected_candidate_evaluation_edges
    )
    assert store.get_manifest(result.readiness_ref).inputs == expected_candidate_evaluation_edges
    assert (
        result.judge_verdict.per_judge["statistical"].metrics["statistical_uncertainty_level"]
        == 0.1
    )
    assert (
        result.judge_verdict.per_judge["statistical"].thresholds["statistical_uncertainty_level"]
        == 0.5
    )
    assert result.judge_verdict.per_judge["statistical"].violations == []
    assert result.judge_verdict.per_judge["reproducibility"].metrics["replay_match"] == 1.0

    assert registry.get("policy_loop") is None


def test_missing_prior_knowledge_caps_readiness_before_canonical_n9_refusal(
    tmp_path, monkeypatch
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "search_registry", store=store)
    coordinator = PolicyPromotionCoordinator(champion_registry=registry, store=store)

    candidate = _candidate(evidence_depth="replicated")
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    selection_eval, hidden_holdout = _benchmark(candidate_ref, holdout_score=0.94)
    evaluation_ref = persist_benchmark_evaluation(
        store, selection_eval, return_selected_profile=True
    )
    replay_ref, replay_verification_ref = _persist_replay_support(
        store,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        monkeypatch=monkeypatch,
    )

    bundle = coordinator.build_input_bundle(
        candidate=candidate,
        phase3_gate=_phase3_passed(),
        benchmark_evaluation=selection_eval,
        hidden_holdout_evaluation=hidden_holdout,
        evaluation_vector=_evaluation_vector(candidate),
        distributional_report=_distributional_report(),
        causal_effect_report=_causal_effect_report(),
        data_readiness_report=build_data_readiness_report(
            sample_size=120,
            measurement_quality="known_good",
            fallback_data_available=True,
        ),
        cross_graph_profile=_cross_graph_profile(),
        governance_report={"verdict": "approve", "issues": []},
        uncertainty_envelope=_uncertainty(0.1),
        replay_bundle_ref=replay_ref,
        replay_verification_ref=replay_verification_ref,
        budget_state=BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("10.0"))},
            spent={"run": Decimal("1.0")},
        ),
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        state={
            "checkpoints": [
                {"stage": "data_loaded", "timestamp": "2026-03-25T10:00:00Z"},
                {"stage": "estimation_complete", "timestamp": "2026-03-25T10:01:00Z"},
            ],
            "verified_claims": [{"source_ref": "source:1", "confidence": 0.9}],
            "data_sources": [{"name": "dataset", "last_updated": "2026-03-01T00:00:00+00:00"}],
            "knowledge_metadata": {"last_updated": "2026-03-01T00:00:00+00:00"},
            "pii_scan_results": {"max_severity": "none", "total_entities_found": 0},
            "audit_lineage_complete": True,
        },
        compute_cost_usd=1.0,
        replay_cost_usd=0.5,
        expected_improvement=2.0,
        timeout_risk=0.1,
    )

    result = coordinator.coordinate_promotion(
        loop_id="policy_loop",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        promotion_policy=PromotionPolicy(loop_id="policy_loop", primary_metric="score"),
        judge_input=bundle,
    )

    assert result.promotion_decision.promoted is False
    assert result.promotion_decision.reason == "canonical_n9_promotion_sequence_required"
    assert result.readiness_contract.readiness_level == DecisionReadiness.SIMULATION_READY
    assert registry.get("policy_loop") is None
    assert result.readiness_contract.metadata["actual_evidence_depth"] == "single_study"
    assert result.readiness_contract.metadata["prior_knowledge_status"] == "missing"
    assert result.readiness_contract.metadata["evidence_support_summary"]["available"] is False


def test_synthetic_runtime_caps_readiness_and_blocks_promotion(tmp_path, monkeypatch) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "search_registry", store=store)
    coordinator = PolicyPromotionCoordinator(champion_registry=registry, store=store)

    candidate = _candidate(evidence_depth="replicated")
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    selection_eval, hidden_holdout = _benchmark(candidate_ref, holdout_score=0.94)
    evaluation_ref = persist_benchmark_evaluation(
        store, selection_eval, return_selected_profile=True
    )
    replay_ref, replay_verification_ref = _persist_replay_support(
        store,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        monkeypatch=monkeypatch,
    )
    bundle = coordinator.build_input_bundle(
        candidate=candidate,
        phase3_gate=_phase3_passed(),
        benchmark_evaluation=selection_eval,
        hidden_holdout_evaluation=hidden_holdout,
        evaluation_vector=_evaluation_vector(candidate),
        distributional_report=_distributional_report(),
        causal_effect_report=_causal_effect_report(),
        data_readiness_report=build_data_readiness_report(
            sample_size=120,
            measurement_quality="known_good",
            fallback_data_available=True,
        ),
        cross_graph_profile=_cross_graph_profile(),
        prior_knowledge_bundle=_prior_knowledge_bundle(status="ok", coverage_complete=True),
        governance_report={"verdict": "approve", "issues": []},
        uncertainty_envelope=_uncertainty(0.1),
        replay_bundle_ref=replay_ref,
        replay_verification_ref=replay_verification_ref,
        budget_state=BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("10.0"))},
            spent={"run": Decimal("1.0")},
        ),
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        state={
            "checkpoints": [
                {"stage": "data_loaded", "timestamp": "2026-03-25T10:00:00Z"},
                {"stage": "estimation_complete", "timestamp": "2026-03-25T10:01:00Z"},
            ],
            "verified_claims": [{"source_ref": "source:1", "confidence": 0.9}],
            "data_sources": [{"name": "dataset", "last_updated": "2026-03-01T00:00:00+00:00"}],
            "knowledge_metadata": {"last_updated": "2026-03-01T00:00:00+00:00"},
            "pii_scan_results": {"max_severity": "none", "total_entities_found": 0},
            "audit_lineage_complete": True,
        },
        compute_cost_usd=1.0,
        replay_cost_usd=0.5,
        expected_improvement=2.0,
        timeout_risk=0.1,
        evaluation_backend_kind="synthetic",
        evaluation_fidelity_mode="full",
        evaluation_promotable_source=False,
        evaluation_degradation_mode="research_only",
        evaluation_provenance_notes=["Synthetic backend is test-only and not promotion-safe."],
    )

    result = coordinator.coordinate_promotion(
        loop_id="policy_loop",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        promotion_policy=PromotionPolicy(loop_id="policy_loop", primary_metric="score"),
        judge_input=bundle,
    )

    assert result.judge_verdict.composite_decision == "promote"
    assert result.promotion_decision.promoted is False
    assert result.promotion_decision.reason == "evaluation_source_not_promotable"
    assert result.readiness_contract.readiness_level == DecisionReadiness.RESEARCH_ARTIFACT
    assert result.readiness_contract.metadata["readiness_cap"] == "research_artifact"
    assert result.readiness_contract.metadata["evaluation_backend_kind"] == "synthetic"
    assert registry.get("policy_loop") is None


def test_phase2_closure_caps_readiness_for_incomplete_relevant_family() -> None:
    contract = DecisionReadinessEvaluator().evaluate(
        candidate=_candidate(evidence_depth="replicated"),
        judge_verdict=_passed_judge_verdict(),
        uncertainty_envelope=_uncertainty(0.1),
        phase3_gate=_phase3_passed(),
        evidence_metadata={
            "artifact_family": "distributional_frontier",
            "phase2_closure": {
                "phase": "phase_2",
                "artifact_families": {
                    "distributional_frontier": {
                        "passes_all": False,
                        "status": "incomplete",
                        "deliverables": [
                            {
                                "deliverable_id": "distributional_bounds_bundle",
                                "status": "missing_judge_verdict",
                            }
                        ],
                    }
                },
            },
        },
    )

    assert contract.readiness_level == DecisionReadiness.RESEARCH_ARTIFACT
    assert contract.metadata["readiness_cap"] == "research_artifact"
    assert (
        contract.metadata["readiness_cap_reason"]
        == "phase2_closure_incomplete:distributional_frontier"
    )
    assert contract.metadata["phase2_closure_family"] == "distributional_frontier"
    assert contract.metadata["phase2_closure_status"] == "incomplete"


def test_fabric_trust_metadata_caps_decision_readiness() -> None:
    contract = DecisionReadinessEvaluator().evaluate(
        candidate=_candidate(evidence_depth="replicated"),
        judge_verdict=_passed_judge_verdict(),
        uncertainty_envelope=_uncertainty(0.1),
        phase3_gate=_phase3_passed(),
        evidence_metadata={
            "fabric_decision_data": [
                {
                    "id": "fabric_decision_data:policy_cost",
                    "quality": {"status": "passed"},
                    "lineage": {"id": "untraced", "status": "untraced"},
                    "access": {"classification": "public"},
                }
            ]
        },
    )

    assert contract.readiness_level == DecisionReadiness.RESEARCH_ARTIFACT
    assert contract.metadata["readiness_cap"] == "research_artifact"
    assert contract.metadata["readiness_cap_reason"] == "fabric_lineage_untraced"
    assert contract.metadata["fabric_readiness_cap"] == "research_artifact"


def test_fabric_quality_failure_caps_decision_readiness() -> None:
    contract = DecisionReadinessEvaluator().evaluate(
        candidate=_candidate(evidence_depth="replicated"),
        judge_verdict=_passed_judge_verdict(),
        uncertainty_envelope=_uncertainty(0.1),
        phase3_gate=_phase3_passed(),
        evidence_metadata={
            "fabric_decision_data": [
                {
                    "id": "fabric_decision_data:policy_cost",
                    "quality": {"status": "failed"},
                    "lineage": {"id": "lin_policy_cost", "status": "verified"},
                    "access": {"classification": "public"},
                }
            ]
        },
    )

    assert contract.readiness_level == DecisionReadiness.RESEARCH_ARTIFACT
    assert contract.metadata["readiness_cap_reason"] == "fabric_quality_failed"


def test_fabric_stale_evidence_caps_decision_readiness_to_advisory() -> None:
    contract = DecisionReadinessEvaluator().evaluate(
        candidate=_candidate(evidence_depth="replicated"),
        judge_verdict=_passed_judge_verdict(),
        uncertainty_envelope=_uncertainty(0.1),
        phase3_gate=_phase3_passed(),
        evidence_metadata={
            "fabric_decision_data": [
                {
                    "id": "fabric_decision_data:policy_cost",
                    "quality": {"status": "passed"},
                    "lineage": {
                        "id": "lin_policy_cost",
                        "status": "verified",
                        "trust_metadata": {"freshness": "stale"},
                    },
                    "access": {"classification": "public"},
                }
            ]
        },
    )

    assert contract.readiness_level == DecisionReadiness.ANALYST_ADVISORY
    assert contract.metadata["readiness_cap_reason"] == "fabric_evidence_stale"


def test_fabric_low_source_trust_caps_decision_readiness() -> None:
    contract = DecisionReadinessEvaluator().evaluate(
        candidate=_candidate(evidence_depth="replicated"),
        judge_verdict=_passed_judge_verdict(),
        uncertainty_envelope=_uncertainty(0.1),
        phase3_gate=_phase3_passed(),
        evidence_metadata={
            "fabric_source_scorecards": {
                "worldbank.wdi.generic": {
                    "metrics": [
                        {
                            "name": "source_trust",
                            "reason": "source_trust=low",
                            "score": 0.4,
                        }
                    ]
                }
            }
        },
    )

    assert contract.readiness_level == DecisionReadiness.RESEARCH_ARTIFACT
    assert contract.metadata["readiness_cap_reason"] == "fabric_source_trust_low"


def test_phase2_closure_summary_flows_through_promotion_runtime(tmp_path, monkeypatch) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "search_registry", store=store)
    coordinator = PolicyPromotionCoordinator(champion_registry=registry, store=store)

    candidate = _candidate(evidence_depth="replicated")
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    selection_eval, _ = _benchmark(candidate_ref, holdout_score=0.94)
    evaluation_ref = persist_benchmark_evaluation(
        store, selection_eval, return_selected_profile=True
    )
    replay_ref, replay_verification_ref = _persist_replay_support(
        store,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        monkeypatch=monkeypatch,
    )

    bundle = coordinator.build_input_bundle(
        candidate=candidate,
        phase3_gate=_phase3_passed(),
        artifact_family="distributional_frontier",
        benchmark_evaluation=selection_eval,
        evaluation_vector=_evaluation_vector(candidate),
        governance_report={"verdict": "approve", "issues": []},
        phase2_closure={
            "phase": "phase_2",
            "artifact_families": {
                "distributional_frontier": {
                    "passes_all": False,
                    "status": "fail",
                    "deliverables": [
                        {
                            "deliverable_id": "distributional_bounds_bundle",
                            "status": "synthetic_world_missing",
                        }
                    ],
                }
            },
        },
        uncertainty_envelope=_uncertainty(0.1),
        replay_bundle_ref=replay_ref,
        replay_verification_ref=replay_verification_ref,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        state={
            "checkpoints": [{"stage": "done", "timestamp": "2026-03-25T10:00:00Z"}],
            "verified_claims": [{"source_ref": "source:1", "confidence": 0.9}],
            "data_sources": [{"name": "dataset", "last_updated": "2026-03-01T00:00:00+00:00"}],
            "knowledge_metadata": {"last_updated": "2026-03-01T00:00:00+00:00"},
            "audit_lineage_complete": True,
        },
    )

    result = coordinator.coordinate_promotion(
        loop_id="policy_loop",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        promotion_policy=PromotionPolicy(loop_id="policy_loop", primary_metric="score"),
        judge_input=bundle,
    )

    assert result.readiness_contract.readiness_level == DecisionReadiness.RESEARCH_ARTIFACT
    assert (
        result.readiness_contract.metadata["readiness_cap_reason"]
        == "phase2_closure_incomplete:distributional_frontier"
    )
    assert result.readiness_contract.metadata["phase2_closure_family"] == "distributional_frontier"
    assert result.readiness_contract.metadata["phase2_closure_status"] == "fail"


def test_missing_phase3_gate_caps_readiness_to_research() -> None:
    contract = DecisionReadinessEvaluator().evaluate(
        candidate=_candidate(evidence_depth="replicated"),
        judge_verdict=JudgeVerdict(per_judge={}, composite_decision="promote"),
        uncertainty_envelope=_uncertainty(0.1),
        evidence_metadata={},
    )

    assert contract.readiness_level == DecisionReadiness.RESEARCH_ARTIFACT
    assert contract.metadata["readiness_cap_reason"] == "phase3_gate_blocked"
    assert contract.phase3_gate.gate_passed is False
    assert "phase3.welfare_missing" in contract.phase3_gate.blocking_reasons
    assert "phase3.ambiguity_missing" in contract.phase3_gate.blocking_reasons


def test_phase2_closure_report_env_caps_readiness_without_inline_summary(
    tmp_path,
    monkeypatch,
) -> None:
    report_path = tmp_path / "foundry_phase2_closure.json"
    _write_phase2_closure_report(
        report_path,
        artifact_family="distributional_frontier",
        passes_all=False,
        status="incomplete",
    )
    monkeypatch.setenv(PHASE2_CLOSURE_ENV_VAR, str(report_path))

    contract = DecisionReadinessEvaluator().evaluate(
        candidate=_candidate(evidence_depth="replicated"),
        judge_verdict=JudgeVerdict(per_judge={}, composite_decision="promote"),
        uncertainty_envelope=_uncertainty(0.1),
        phase3_gate=_phase3_passed(),
        evidence_metadata={"artifact_family": "distributional_frontier"},
    )

    assert contract.readiness_level == DecisionReadiness.RESEARCH_ARTIFACT
    assert contract.metadata["readiness_cap"] == "research_artifact"
    assert (
        contract.metadata["readiness_cap_reason"]
        == "phase2_closure_incomplete:distributional_frontier"
    )
    assert contract.metadata["phase2_closure_family"] == "distributional_frontier"
    assert contract.metadata["phase2_closure_status"] == "incomplete"


def test_phase2_closure_summary_flows_through_promotion_runtime_via_env_report(
    tmp_path,
    monkeypatch,
) -> None:
    report_path = tmp_path / "foundry_phase2_closure.json"
    _write_phase2_closure_report(
        report_path,
        artifact_family="distributional_frontier",
        passes_all=False,
        status="fail",
    )
    monkeypatch.setenv(PHASE2_CLOSURE_ENV_VAR, str(report_path))

    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "search_registry", store=store)
    coordinator = PolicyPromotionCoordinator(champion_registry=registry, store=store)

    candidate = _candidate(evidence_depth="replicated")
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    selection_eval, _ = _benchmark(candidate_ref, holdout_score=0.94)
    evaluation_ref = persist_benchmark_evaluation(
        store, selection_eval, return_selected_profile=True
    )
    replay_ref, replay_verification_ref = _persist_replay_support(
        store,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        monkeypatch=monkeypatch,
    )

    bundle = coordinator.build_input_bundle(
        candidate=candidate,
        phase3_gate=_phase3_passed(),
        artifact_family="distributional_frontier",
        benchmark_evaluation=selection_eval,
        evaluation_vector=_evaluation_vector(candidate),
        governance_report={"verdict": "approve", "issues": []},
        uncertainty_envelope=_uncertainty(0.1),
        replay_bundle_ref=replay_ref,
        replay_verification_ref=replay_verification_ref,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        state={
            "checkpoints": [{"stage": "done", "timestamp": "2026-03-25T10:00:00Z"}],
            "verified_claims": [{"source_ref": "source:1", "confidence": 0.9}],
            "data_sources": [{"name": "dataset", "last_updated": "2026-03-01T00:00:00+00:00"}],
            "knowledge_metadata": {"last_updated": "2026-03-01T00:00:00+00:00"},
            "audit_lineage_complete": True,
        },
    )

    result = coordinator.coordinate_promotion(
        loop_id="policy_loop",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        promotion_policy=PromotionPolicy(loop_id="policy_loop", primary_metric="score"),
        judge_input=bundle,
    )

    assert result.readiness_contract.readiness_level == DecisionReadiness.RESEARCH_ARTIFACT
    assert (
        result.readiness_contract.metadata["readiness_cap_reason"]
        == "phase2_closure_incomplete:distributional_frontier"
    )
    assert result.readiness_contract.metadata["phase2_closure_family"] == "distributional_frontier"
    assert result.readiness_contract.metadata["phase2_closure_status"] == "fail"


def test_phase2_benchmark_scope_normalizes_frontier_family() -> None:
    runtime_module = importlib.import_module(
        "polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime"
    )
    state = type("State", (), {"params": {}})()
    candidate = type(
        "Candidate",
        (),
        {
            "metadata": {
                "artifact_family": "causal_core",
                "query_type": "partial_observability_bounds",
            }
        },
    )()
    selection_vector = type(
        "SelectionVector",
        (),
        {"metadata": {"estimator_name": "network_missingness_frontier"}},
    )()

    scope = runtime_module._resolve_benchmark_scope(
        state=state,
        candidate=candidate,
        selection_vector=selection_vector,
    )

    assert scope["artifact_family"] == "network_identification"
    assert scope["query_type"] == "partial_observability_bounds"
    assert scope["estimator_name"] == "network_missingness_frontier"


def test_latent_bundle_forces_research_only_cap_and_human_gate(tmp_path, monkeypatch) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "search_registry", store=store)
    coordinator = PolicyPromotionCoordinator(champion_registry=registry, store=store)

    candidate = _candidate(evidence_depth="replicated")
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    selection_eval, _ = _benchmark(candidate_ref, holdout_score=0.94)
    evaluation_ref = persist_benchmark_evaluation(
        store, selection_eval, return_selected_profile=True
    )
    replay_ref, replay_verification_ref = _persist_replay_support(
        store,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        monkeypatch=monkeypatch,
    )

    bundle = coordinator.build_input_bundle(
        candidate=candidate,
        phase3_gate=_phase3_passed(),
        benchmark_evaluation=selection_eval,
        evaluation_vector=_evaluation_vector(candidate),
        governance_report={"verdict": "approve", "issues": []},
        latent_discovery_bundle=_latent_bundle(),
        uncertainty_envelope=_uncertainty(0.1),
        replay_bundle_ref=replay_ref,
        replay_verification_ref=replay_verification_ref,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        state={
            "checkpoints": [{"stage": "done", "timestamp": "2026-03-25T10:00:00Z"}],
            "verified_claims": [{"source_ref": "source:1", "confidence": 0.9}],
            "data_sources": [{"name": "dataset", "last_updated": "2026-03-01T00:00:00+00:00"}],
            "knowledge_metadata": {"last_updated": "2026-03-01T00:00:00+00:00"},
            "audit_lineage_complete": True,
        },
    )

    result = coordinator.coordinate_promotion(
        loop_id="policy_loop",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        promotion_policy=PromotionPolicy(loop_id="policy_loop", primary_metric="score"),
        judge_input=bundle,
    )

    assert result.judge_verdict.composite_decision == "defer_to_human"
    assert result.promotion_decision.promoted is False
    assert result.readiness_contract.readiness_level == DecisionReadiness.RESEARCH_ARTIFACT
    assert result.readiness_contract.metadata["readiness_cap_reason"] == (
        "latent_discovery_proof_only"
    )
    assert result.readiness_contract.metadata["not_for_decision_support"] is True
    assert result.readiness_contract.metadata["latent_falsification_tests"] == [
        "negative_control_outcome"
    ]


def test_readiness_metadata_surfaces_latent_separation_summary() -> None:
    latent_bundle = _latent_bundle().model_copy(
        update={"metadata": {"separation_diagnostics": _latent_separation_diagnostics()}}
    )
    governance_payload = latent_governance_metadata(latent_bundle)
    assert governance_payload is not None

    contract = DecisionReadinessEvaluator().evaluate(
        candidate=_candidate(evidence_depth="single_study"),
        judge_verdict=JudgeVerdict(per_judge={}, composite_decision="promote"),
        uncertainty_envelope=_uncertainty(0.1),
        phase3_gate=_phase3_passed(),
        evidence_metadata={"latent_governance": governance_payload},
    )

    assert contract.readiness_level == DecisionReadiness.RESEARCH_ARTIFACT
    assert contract.metadata["readiness_cap_reason"] == "latent_discovery_proof_only"
    assert contract.metadata["latent_trust_level"] == "conditional"
    assert contract.metadata["latent_resolution_label"] == "latent_confounding"
    assert contract.metadata["latent_separated_pairs"] == ["measurement_vs_confounding"]


def test_promoted_latent_bundle_maps_to_bounds_claim_mode_in_runtime(
    tmp_path,
    monkeypatch,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "search_registry", store=store)
    coordinator = PolicyPromotionCoordinator(champion_registry=registry, store=store)

    candidate = _candidate(evidence_depth="replicated")
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    selection_eval, _ = _benchmark(candidate_ref, holdout_score=0.94)
    evaluation_ref = persist_benchmark_evaluation(
        store, selection_eval, return_selected_profile=True
    )
    replay_ref, replay_verification_ref = _persist_replay_support(
        store,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        monkeypatch=monkeypatch,
    )

    bundle = coordinator.build_input_bundle(
        candidate=candidate,
        phase3_gate=_phase3_passed(),
        benchmark_evaluation=selection_eval,
        evaluation_vector=_evaluation_vector(candidate),
        governance_report={"verdict": "approve", "issues": []},
        latent_discovery_bundle=_conditional_latent_bundle(),
        uncertainty_envelope=_uncertainty(0.1),
        replay_bundle_ref=replay_ref,
        replay_verification_ref=replay_verification_ref,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        state={
            "checkpoints": [{"stage": "done", "timestamp": "2026-03-25T10:00:00Z"}],
            "verified_claims": [{"source_ref": "source:1", "confidence": 0.9}],
            "data_sources": [{"name": "dataset", "last_updated": "2026-03-01T00:00:00+00:00"}],
            "knowledge_metadata": {"last_updated": "2026-03-01T00:00:00+00:00"},
            "audit_lineage_complete": True,
        },
    )

    result = coordinator.coordinate_promotion(
        loop_id="policy_loop",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        promotion_policy=PromotionPolicy(loop_id="policy_loop", primary_metric="score"),
        judge_input=bundle,
    )

    governance = result.judge_verdict.per_judge["governance"]

    assert bundle.effective_claim_mode() == "bounds"
    assert result.judge_verdict.composite_decision == "defer_to_human"
    assert governance.passed is True
    assert governance.failure_card is None
    assert any(card.failure_type == "human_gate_required" for card in governance.warnings)
    assert result.readiness_contract.readiness_level == DecisionReadiness.RESEARCH_ARTIFACT
    assert result.readiness_contract.metadata["claim_mode"] == "bounds"
    assert result.readiness_contract.metadata["not_for_decision_support"] is False
    assert (
        result.readiness_contract.metadata["latent_governance"]["readiness_cap"] == "bounds_ready"
    )
    analyst_assessment = next(
        assessment
        for assessment in result.readiness_contract.assessments
        if assessment.readiness_level == DecisionReadiness.ANALYST_ADVISORY
    )
    assert analyst_assessment.passed is False
    assert analyst_assessment.reasons == ["judge_failed:statistical"]


def test_incomplete_latent_bundle_is_rejected_by_governance_judge() -> None:
    candidate = _candidate(evidence_depth="replicated")
    bundle = JudgeInputBundle(
        candidate=candidate,
        governance_report={"verdict": "approve", "issues": []},
        latent_discovery_bundle=_latent_bundle(complete=False),
        uncertainty_envelope=_uncertainty(0.1),
        candidate_ref=_artifact_ref("a"),
        evaluation_ref=_artifact_ref("b"),
        replay_bundle_ref=_artifact_ref("c"),
        state={
            "checkpoints": [{"stage": "done", "timestamp": "2026-03-25T10:00:00Z"}],
            "verified_claims": [{"source_ref": "source:1", "confidence": 0.9}],
            "data_sources": [{"name": "dataset", "last_updated": "2026-03-01T00:00:00+00:00"}],
            "knowledge_metadata": {"last_updated": "2026-03-01T00:00:00+00:00"},
            "audit_lineage_complete": True,
        },
    )

    verdict = JudgeStack().evaluate(bundle)

    assert verdict.composite_decision == "reject"
    assert any(
        card.failure_type == "latent_discovery_bundle_incomplete"
        for card in verdict.blocking_failures
    )


def test_missing_identification_conditions_rejects_latent_bundle() -> None:
    candidate = _candidate(evidence_depth="replicated")
    bundle = JudgeInputBundle(
        candidate=candidate,
        governance_report={"verdict": "approve", "issues": []},
        latent_discovery_bundle=_latent_bundle().model_copy(
            update={"identification_conditions": []}
        ),
        uncertainty_envelope=_uncertainty(0.1),
        candidate_ref=_artifact_ref("a"),
        evaluation_ref=_artifact_ref("b"),
        replay_bundle_ref=_artifact_ref("c"),
        state={
            "checkpoints": [{"stage": "done", "timestamp": "2026-03-25T10:00:00Z"}],
            "verified_claims": [{"source_ref": "source:1", "confidence": 0.9}],
            "data_sources": [{"name": "dataset", "last_updated": "2026-03-01T00:00:00+00:00"}],
            "knowledge_metadata": {"last_updated": "2026-03-01T00:00:00+00:00"},
            "audit_lineage_complete": True,
        },
    )

    verdict = JudgeStack().evaluate(bundle)

    assert verdict.composite_decision == "reject"
    latent_failure = next(
        card
        for card in verdict.blocking_failures
        if card.failure_type == "latent_discovery_bundle_incomplete"
    )
    assert "identification_conditions" in latent_failure.description


def test_unreadable_latent_bundle_resolution_is_rejected_and_caps_readiness(
    tmp_path,
    monkeypatch,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "search_registry", store=store)
    coordinator = PolicyPromotionCoordinator(champion_registry=registry, store=store)

    candidate = _candidate(evidence_depth="replicated")
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    selection_eval, _ = _benchmark(candidate_ref, holdout_score=0.94)
    evaluation_ref = persist_benchmark_evaluation(
        store, selection_eval, return_selected_profile=True
    )
    replay_ref, replay_verification_ref = _persist_replay_support(
        store,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        monkeypatch=monkeypatch,
    )

    bundle = coordinator.build_input_bundle(
        candidate=candidate,
        phase3_gate=_phase3_passed(),
        benchmark_evaluation=selection_eval,
        evaluation_vector=_evaluation_vector(candidate),
        governance_report={"verdict": "approve", "issues": []},
        latent_discovery_resolution_error={
            "error_code": "ArtifactNotFound",
            "error_message": "discovery artifact bundle could not be loaded",
        },
        uncertainty_envelope=_uncertainty(0.1),
        replay_bundle_ref=replay_ref,
        replay_verification_ref=replay_verification_ref,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        state={
            "checkpoints": [{"stage": "done", "timestamp": "2026-03-25T10:00:00Z"}],
            "verified_claims": [{"source_ref": "source:1", "confidence": 0.9}],
            "data_sources": [{"name": "dataset", "last_updated": "2026-03-01T00:00:00+00:00"}],
            "knowledge_metadata": {"last_updated": "2026-03-01T00:00:00+00:00"},
            "audit_lineage_complete": True,
        },
    )

    result = coordinator.coordinate_promotion(
        loop_id="policy_loop",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        promotion_policy=PromotionPolicy(loop_id="policy_loop", primary_metric="score"),
        judge_input=bundle,
    )

    assert result.judge_verdict.composite_decision == "reject"
    assert result.promotion_decision.promoted is False
    assert result.readiness_contract.readiness_level == DecisionReadiness.RESEARCH_ARTIFACT
    assert result.readiness_contract.metadata["readiness_cap_reason"] == (
        "latent_discovery_bundle_unreadable"
    )
    assert result.readiness_contract.metadata["latent_discovery_resolution_error"] == {
        "error_code": "ArtifactNotFound",
        "error_message": "discovery artifact bundle could not be loaded",
    }
    assert any(
        card.failure_type == "latent_discovery_bundle_unreadable"
        for card in result.judge_verdict.blocking_failures
    )


def test_data_readiness_metadata_uses_ref_and_summary_not_inline_dump(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "search_registry", store=store)
    coordinator = PolicyPromotionCoordinator(champion_registry=registry, store=store)

    candidate = _candidate(evidence_depth="replicated")
    candidate_ref = persist_policy_candidate_schema(store, candidate)
    selection_eval, hidden_holdout = _benchmark(candidate_ref, holdout_score=0.94)
    evaluation_ref = persist_benchmark_evaluation(store, selection_eval)
    bundle = coordinator.build_input_bundle(
        candidate=candidate,
        phase3_gate=_phase3_passed(),
        benchmark_evaluation=selection_eval,
        hidden_holdout_evaluation=hidden_holdout,
        evaluation_vector=_evaluation_vector(candidate),
        distributional_report=_distributional_report(),
        causal_effect_report=_causal_effect_report(),
        data_readiness_report=build_data_readiness_report(
            sample_size=120,
            measurement_quality="known_good",
            fallback_data_available=True,
        ),
        cross_graph_profile=_cross_graph_profile(),
        prior_knowledge_bundle=_prior_knowledge_bundle(status="ok", coverage_complete=True),
        governance_report={"verdict": "approve", "issues": []},
        uncertainty_envelope=_uncertainty(0.1),
        budget_state=BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("10.0"))},
            spent={"run": Decimal("1.0")},
        ),
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        state={
            "checkpoints": [{"stage": "done", "timestamp": "2026-03-25T10:00:00Z"}],
            "verified_claims": [{"source_ref": "source:1", "confidence": 0.9}],
            "data_sources": [{"name": "dataset", "last_updated": "2026-03-01T00:00:00+00:00"}],
            "knowledge_metadata": {"last_updated": "2026-03-01T00:00:00+00:00"},
            "pii_scan_results": {"max_severity": "none", "total_entities_found": 0},
            "audit_lineage_complete": True,
        },
        compute_cost_usd=1.0,
        replay_cost_usd=0.5,
        expected_improvement=2.0,
        timeout_risk=0.1,
    )

    result = coordinator.coordinate_promotion(
        loop_id="policy_loop",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        promotion_policy=PromotionPolicy(loop_id="policy_loop", primary_metric="score"),
        judge_input=bundle,
    )

    metadata = result.readiness_contract.metadata
    assert metadata["data_readiness_decision"] == "pass"
    assert metadata["data_readiness_can_run_estimation"] is True
    assert "data_readiness_report_ref" in metadata
    assert "data_readiness_report" not in metadata


def test_ref_only_data_readiness_warn_caps_readiness(tmp_path, monkeypatch) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "search_registry", store=store)
    coordinator = PolicyPromotionCoordinator(champion_registry=registry, store=store)

    candidate = _candidate(evidence_depth="replicated")
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    selection_eval, hidden_holdout = _benchmark(candidate_ref, holdout_score=0.94)
    evaluation_ref = persist_benchmark_evaluation(
        store, selection_eval, return_selected_profile=True
    )
    replay_ref, replay_verification_ref = _persist_replay_support(
        store,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        monkeypatch=monkeypatch,
    )
    readiness_report = build_data_readiness_report(
        sample_size=120,
        measurement_quality="unknown",
        fallback_data_available=True,
    )
    readiness_ref = persist_data_readiness_report(
        _ensure_ir_artifact_store(store), readiness_report
    )

    bundle = coordinator.build_input_bundle(
        candidate=candidate,
        phase3_gate=_phase3_passed(),
        benchmark_evaluation=selection_eval,
        hidden_holdout_evaluation=hidden_holdout,
        evaluation_vector=_evaluation_vector(candidate),
        distributional_report=_distributional_report(),
        causal_effect_report=_causal_effect_report(),
        data_readiness_report_ref=readiness_ref,
        cross_graph_profile=_cross_graph_profile(),
        prior_knowledge_bundle=_prior_knowledge_bundle(status="ok", coverage_complete=True),
        governance_report={"verdict": "approve", "issues": []},
        uncertainty_envelope=_uncertainty(0.1),
        replay_bundle_ref=replay_ref,
        replay_verification_ref=replay_verification_ref,
        budget_state=BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("10.0"))},
            spent={"run": Decimal("1.0")},
        ),
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        state={
            "checkpoints": [{"stage": "done", "timestamp": "2026-03-25T10:00:00Z"}],
            "verified_claims": [{"source_ref": "source:1", "confidence": 0.9}],
            "data_sources": [{"name": "dataset", "last_updated": "2026-03-01T00:00:00+00:00"}],
            "knowledge_metadata": {"last_updated": "2026-03-01T00:00:00+00:00"},
            "pii_scan_results": {"max_severity": "none", "total_entities_found": 0},
            "audit_lineage_complete": True,
        },
        compute_cost_usd=1.0,
        replay_cost_usd=0.5,
        expected_improvement=2.0,
        timeout_risk=0.1,
    )

    result = coordinator.coordinate_promotion(
        loop_id="policy_loop",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        promotion_policy=PromotionPolicy(loop_id="policy_loop", primary_metric="score"),
        judge_input=bundle,
    )

    metadata = result.readiness_contract.metadata
    assert result.readiness_contract.readiness_level == DecisionReadiness.ANALYST_ADVISORY
    assert metadata["readiness_cap"] == "analyst_advisory"
    assert metadata["data_readiness_decision"] == "warn"
    assert metadata["data_readiness_can_run_estimation"] is True
    assert metadata["data_readiness_report_ref"]["artifact_id"] == str(readiness_ref.artifact_id)


def test_dp_bounds_only_metadata_is_surfaced_in_readiness_contract(tmp_path, monkeypatch) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "search_registry", store=store)
    coordinator = PolicyPromotionCoordinator(champion_registry=registry, store=store)

    candidate = _candidate(evidence_depth="replicated")
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    selection_eval, hidden_holdout = _benchmark(candidate_ref, holdout_score=0.94)
    evaluation_ref = persist_benchmark_evaluation(
        store, selection_eval, return_selected_profile=True
    )
    replay_ref, replay_verification_ref = _persist_replay_support(
        store,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        monkeypatch=monkeypatch,
    )
    readiness_report = DataReadinessReport(
        decision="warn",
        can_compile_estimation=True,
        can_run_estimation=False,
        sample_size=120,
        measurement_quality="known_good",
        fallback_data_available=True,
        warnings=["dp_bounds_only"],
        metrics={"dp_distortion_radius": 0.021},
        dp_distortion={
            "effective_status": "bounded",
            "reason": "DP distortion exceeds the point-estimate tolerance.",
            "block_reason": None,
            "distortion_radius": 0.021,
            "mechanism_family": "laplace",
            "effect_interval": [-0.12, -0.03],
        },
    )

    bundle = coordinator.build_input_bundle(
        candidate=candidate,
        phase3_gate=_phase3_passed(),
        benchmark_evaluation=selection_eval,
        hidden_holdout_evaluation=hidden_holdout,
        evaluation_vector=_evaluation_vector(candidate),
        distributional_report=_distributional_report(),
        causal_effect_report=_causal_effect_report(),
        data_readiness_report=readiness_report,
        cross_graph_profile=_cross_graph_profile(),
        prior_knowledge_bundle=_prior_knowledge_bundle(status="ok", coverage_complete=True),
        governance_report={"verdict": "approve", "issues": []},
        uncertainty_envelope=_uncertainty(0.1),
        replay_bundle_ref=replay_ref,
        replay_verification_ref=replay_verification_ref,
        claim_mode="bounds",
        budget_state=BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("10.0"))},
            spent={"run": Decimal("1.0")},
        ),
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        state={
            "checkpoints": [{"stage": "done", "timestamp": "2026-03-25T10:00:00Z"}],
            "verified_claims": [{"source_ref": "source:1", "confidence": 0.9}],
            "data_sources": [{"name": "dataset", "last_updated": "2026-03-01T00:00:00+00:00"}],
            "knowledge_metadata": {"last_updated": "2026-03-01T00:00:00+00:00"},
            "pii_scan_results": {"max_severity": "none", "total_entities_found": 0},
            "audit_lineage_complete": True,
        },
        compute_cost_usd=1.0,
        replay_cost_usd=0.5,
        expected_improvement=2.0,
        timeout_risk=0.1,
    )

    result = coordinator.coordinate_promotion(
        loop_id="policy_loop",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        promotion_policy=PromotionPolicy(loop_id="policy_loop", primary_metric="score"),
        judge_input=bundle,
    )

    structural = result.judge_verdict.per_judge["structural"]
    metadata = result.readiness_contract.metadata

    assert result.readiness_contract.readiness_level == DecisionReadiness.ANALYST_ADVISORY
    assert any(card.failure_type == "dp_release_bounded" for card in structural.warnings)
    assert metadata["readiness_cap_reason"] == "dp_bounds_only"
    assert metadata["dp_effective_status"] == "bounded"
    assert metadata["dp_distortion_radius"] == 0.021
    assert metadata["dp_effect_interval"] == [-0.12, -0.03]


def test_promotion_coordinator_publishes_canonical_n9_refusal_to_voi_scheduler(
    tmp_path, monkeypatch
) -> None:
    class _Scheduler:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def observe_promotion_outcome(self, **kwargs) -> None:
            self.calls.append(kwargs)

    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "search_registry", store=store)
    coordinator = PolicyPromotionCoordinator(champion_registry=registry, store=store)
    candidate = _candidate(evidence_depth="replicated")
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    selection_eval, hidden_holdout = _benchmark(candidate_ref, holdout_score=0.94)
    evaluation_ref = persist_benchmark_evaluation(
        store, selection_eval, return_selected_profile=True
    )
    scheduler = _Scheduler()
    replay_ref, replay_verification_ref = _persist_replay_support(
        store,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        monkeypatch=monkeypatch,
    )

    bundle = coordinator.build_input_bundle(
        candidate=candidate,
        phase3_gate=_phase3_passed(),
        benchmark_evaluation=selection_eval,
        hidden_holdout_evaluation=hidden_holdout,
        evaluation_vector=_evaluation_vector(candidate),
        distributional_report=_distributional_report(),
        causal_effect_report=_causal_effect_report(),
        data_readiness_report=build_data_readiness_report(
            sample_size=120,
            measurement_quality="known_good",
            fallback_data_available=True,
        ),
        cross_graph_profile=_cross_graph_profile(),
        prior_knowledge_bundle=_prior_knowledge_bundle(status="ok", coverage_complete=True),
        governance_report={"verdict": "approve", "issues": []},
        uncertainty_envelope=_uncertainty(0.1),
        replay_bundle_ref=replay_ref,
        replay_verification_ref=replay_verification_ref,
        budget_state=BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("10.0"))},
            spent={"run": Decimal("1.0")},
        ),
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        state={
            "current_pareto_position": "frontier",
            "checkpoints": [
                {"stage": "data_loaded", "timestamp": "2026-03-25T10:00:00Z"},
                {"stage": "estimation_complete", "timestamp": "2026-03-25T10:01:00Z"},
            ],
            "verified_claims": [{"source_ref": "source:1", "confidence": 0.9}],
            "data_sources": [{"name": "dataset", "last_updated": "2026-03-01T00:00:00+00:00"}],
            "knowledge_metadata": {"last_updated": "2026-03-01T00:00:00+00:00"},
            "pii_scan_results": {"max_severity": "none", "total_entities_found": 0},
            "audit_lineage_complete": True,
        },
        voi_scheduler=scheduler,
        compute_cost_usd=1.0,
        replay_cost_usd=0.5,
        expected_improvement=2.0,
        timeout_risk=0.1,
    )

    result = coordinator.coordinate_promotion(
        loop_id="policy_loop",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        promotion_policy=PromotionPolicy(loop_id="policy_loop", primary_metric="score"),
        judge_input=bundle,
    )

    assert result.promotion_decision.promoted is False
    assert result.promotion_decision.reason == "canonical_n9_promotion_sequence_required"
    assert scheduler.calls
    assert scheduler.calls[0]["candidate_id"] == candidate.candidate_id
    assert scheduler.calls[0]["promoted"] is False
    assert registry.get("policy_loop") is None


def test_search_controller_policy_mode_updates_registry(tmp_path) -> None:
    candidate = _candidate()
    stack = ObjectiveStack()
    registry = ParetoRegistry(root=tmp_path / "pareto_registry")

    class StaticGenerator:
        def generate(self, history, current_best, context):
            return {"candidate_id": "candidate_b"}

    def stage_a(candidate_payload, context):
        return 0.0, True

    def stage_b(candidate_payload, context):
        return {
            "simulation_results": {},
            "feedback": {"verdict": "APPROVE"},
            "_policy_candidate_schema": candidate,
            "policy_evaluation_bundle": PolicyEvaluationBundle(
                candidate=candidate,
                simulation_metrics={"policy_value": 11.0, "employment_rate": 0.9, "welfare": 12.0},
                distributional_report=_distributional_report(),
                causal_effect_report=_causal_effect_report(),
                cross_graph_profile=_cross_graph_profile(),
                uncertainty_envelope=_uncertainty(0.2),
            ),
        }

    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(1),
            objective=CompositeObjective([]),
            policy_objective_stack=stack,
            pareto_registry=registry,
        ),
        candidate_generator=StaticGenerator(),
        stage_a_evaluator=stage_a,
        stage_b_evaluator=stage_b,
    )

    result = controller.run(initial_context={})

    assert len(result.history) == 1
    assert result.history[0].policy_evaluation is not None
    assert result.pareto_front == []
    assert result.pareto_projection is not None
    assert result.pareto_projection.assessment.status == "basis_limited"
    assert result.pareto_projection.candidate_frontier_hashes
    assert result.pareto_projection.unassessed_candidate_hashes

    persisted = registry.get_snapshot(controller._search_id)
    assert persisted.loop_id == controller._search_id
    assert persisted.entries
    assert registry.as_legacy_frontier_payload(controller._search_id) == result.pareto_front


def test_typed_objective_reaches_best_frontier_and_candidate_transfer_only_when_valid(
    tmp_path,
) -> None:
    """Exercise ObjectiveStack, controller state, durable frontier, and seed consumer."""
    candidate = _candidate()
    candidate_seed_payload = {
        "candidate_id": candidate.candidate_id,
        "metadata": {"domain": candidate.trinity_bundle.problem_frame.domain.value},
    }
    stack = ObjectiveStack()
    registry = ParetoRegistry(root=tmp_path / "valid-pareto")

    class StaticGenerator:
        def generate(self, history, current_best, context):
            del history, current_best, context
            return dict(candidate_seed_payload)

    def typed_stage_b(candidate_payload, context):
        del candidate_payload, context
        return {
            "simulation_results": {"policy_value": -1_000_000.0},
            "feedback": {"verdict": "APPROVE"},
            "_policy_candidate_schema": candidate,
            "policy_evaluation_bundle": PolicyEvaluationBundle(
                candidate=candidate,
                simulation_metrics={
                    "policy_value": 11.0,
                    "employment_rate": 0.9,
                    "welfare": 12.0,
                },
                distributional_report=_distributional_report(),
                causal_effect_report=_causal_effect_report(),
                cross_graph_profile=_cross_graph_profile(),
                uncertainty_envelope=_uncertainty(0.2),
            ),
        }

    valid_controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(1),
            objective=CompositeObjective([]),
            policy_objective_stack=stack,
            pareto_registry=registry,
        ),
        candidate_generator=StaticGenerator(),
        stage_a_evaluator=lambda _candidate, _context: (0.0, True),
        stage_b_evaluator=typed_stage_b,
    )
    valid_result = valid_controller.run(initial_context={})

    assert valid_result.best_candidate == candidate_seed_payload
    assert valid_result.history[0].objective_value != -1_000_000.0
    assert valid_result.history[0].policy_evaluation_status == "valid"
    assert valid_result.pareto_projection is not None
    assert valid_result.pareto_projection.candidate_frontier_hashes
    valid_reopened = ParetoRegistry(root=tmp_path / "valid-pareto")
    persisted = valid_reopened.get_snapshot(valid_result.search_id)
    assert len(persisted.entries) == 1
    persisted_entry = next(iter(persisted.entries.values()))
    assert persisted_entry.evaluation.model_dump(mode="json") == (
        valid_result.history[0].policy_evaluation.model_dump(mode="json")
    )
    assert persisted_entry.candidate_id == candidate.candidate_id
    assert persisted_entry.seed_payload == candidate_seed_payload
    assert persisted_entry.domain == "fiscal"

    target_context = TransferContext(
        task_family=persisted_entry.task_family,
        domain=persisted_entry.domain,
        run_id="next-candidate-search",
    )
    assert target_context.tenant_hash is None
    transferred = valid_reopened.get_seed_bundle(target_context)
    assert len(transferred.entries) == 1
    assert transferred.entries[0].candidate_id == candidate.candidate_id
    assert transferred.entries[0].seed_only is True
    assert transferred.entries[0].provenance_weight > 0.0
    foreign_tenant_context = target_context.model_copy(update={"tenant_hash": "foreign-tenant"})
    assert valid_reopened.get_seed_bundle(foreign_tenant_context).entries == []
    warm_starts = valid_reopened.build_warm_start_evaluations(target_context)
    assert len(warm_starts) == 1
    assert warm_starts[0]["candidate"] == candidate_seed_payload
    assert warm_starts[0]["metadata"]["seed_only"] is True
    assert warm_starts[0]["stage_b_result"]["policy_evaluation"]["candidate_id"] == (
        candidate.candidate_id
    )

    class NextCandidateGenerator:
        def generate(self, history, current_best, context):
            del history, current_best, context
            return {"candidate_id": "unused-next-candidate"}

    receiving_controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(1),
            objective=CompositeObjective([]),
            initial_evaluations=warm_starts,
        ),
        candidate_generator=NextCandidateGenerator(),
        stage_a_evaluator=lambda _candidate, _context: (0.0, False),
        stage_b_evaluator=lambda _candidate, _context: {},
    )
    received_result = receiving_controller.run(initial_context={})
    assert received_result.telemetry["training_evaluations"] == 1
    assert received_result.history[0].candidate == candidate_seed_payload
    received_stage_b = received_result.history[0].stage_b_result
    assert received_stage_b is not None
    assert received_stage_b["policy_evaluation"]["candidate_id"] == candidate.candidate_id

    invalid_registry = ParetoRegistry(root=tmp_path / "invalid-pareto")

    def malformed_stage_b(candidate_payload, context):
        del candidate_payload, context
        return {
            "simulation_results": {"policy_value": -1_000_000.0},
            "feedback": {"verdict": "APPROVE"},
            "_policy_candidate_schema": candidate,
            "policy_evaluation": {"primary": {"policy_value": "not-a-number"}},
        }

    invalid_controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(1),
            objective=CompositeObjective([]),
            policy_objective_stack=ObjectiveStack(),
            pareto_registry=invalid_registry,
        ),
        candidate_generator=StaticGenerator(),
        stage_a_evaluator=lambda _candidate, _context: (0.0, True),
        stage_b_evaluator=malformed_stage_b,
    )
    invalid_result = invalid_controller.run(initial_context={})

    assert invalid_result.best_candidate is None
    assert invalid_result.history[0].objective_value == float("inf")
    assert invalid_result.history[0].policy_evaluation_status == "invalid"
    assert invalid_result.history[0].is_promising is False
    invalid_reopened = ParetoRegistry(root=tmp_path / "invalid-pareto")
    invalid_snapshot = invalid_reopened.get_snapshot(invalid_result.search_id)
    assert invalid_snapshot.entries == {}
    assert invalid_reopened.get_seed_bundle(target_context).entries == []
    assert invalid_reopened.build_warm_start_evaluations(target_context) == []


@pytest.mark.parametrize(
    "candidate_order",
    [
        (
            "front_a",
            "front_equal_identity",
            "incomparable",
            "dominated_equal_secondary",
            "dominated",
            "infeasible",
            "malformed",
        ),
        (
            "malformed",
            "infeasible",
            "dominated",
            "dominated_equal_secondary",
            "incomparable",
            "front_equal_identity",
            "front_a",
        ),
    ],
    ids=["front-to-back", "back-to-front"],
)
def test_search_controller_persists_pareto_membership_for_fresh_reader(
    tmp_path, candidate_order
) -> None:
    metrics = {
        "front_a": (10.0, 0.90),
        "front_equal_identity": (10.0, 0.90),
        "incomparable": (11.0, 0.80),
        "dominated_equal_secondary": (9.0, 0.90),
        "dominated": (8.0, 0.70),
        "infeasible": (12.0, 0.95),
        "malformed": (13.0, 1.0),
    }
    candidates = {
        candidate_id: _candidate().model_copy(update={"candidate_id": candidate_id})
        for candidate_id in metrics
    }
    registry_root = tmp_path / "pareto_registry"
    registry = ParetoRegistry(root=registry_root)

    class SequenceGenerator:
        def __init__(self):
            self._candidate_ids = iter(candidate_order)

        def generate(self, history, current_best, context):
            del history, current_best, context
            return {"candidate_id": next(self._candidate_ids)}

    def stage_b(candidate_payload, context):
        del context
        candidate_id = candidate_payload["candidate_id"]
        candidate = candidates[candidate_id]
        if candidate_id == "malformed":
            return {
                "simulation_results": {},
                "feedback": {"verdict": "APPROVE"},
                "_policy_candidate_schema": candidate,
                "policy_evaluation_bundle": {"unexpected_field": "present but invalid"},
            }
        policy_value, employment_rate = metrics[candidate_id]
        bundle = PolicyEvaluationBundle(
            candidate=candidate,
            simulation_metrics={
                "policy_value": policy_value,
                "employment_rate": employment_rate,
                "welfare": policy_value,
            },
            distributional_report=_distributional_report(),
            causal_effect_report=_causal_effect_report(),
            cross_graph_profile=_cross_graph_profile(),
            uncertainty_envelope=_uncertainty(0.2),
            governance_report=(
                GovernanceReport(verdict="reject", issues=[])
                if candidate_id == "infeasible"
                else None
            ),
        )
        return {
            "simulation_results": {},
            "feedback": {"verdict": "APPROVE"},
            "_policy_candidate_schema": candidate,
            "policy_evaluation_bundle": bundle,
        }

    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(len(candidate_order)),
            objective=CompositeObjective([]),
            max_iterations_hard_limit=len(candidate_order),
            policy_objective_stack=ObjectiveStack(),
            pareto_registry=registry,
            pareto_objective_basis_by_view={"global_feasible": _declared_global_pareto_basis()},
        ),
        candidate_generator=SequenceGenerator(),
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=stage_b,
    )

    result = controller.run(initial_context={})

    assert len(result.history) == len(candidate_order)
    history_by_id = {row.candidate["candidate_id"]: row for row in result.history}
    assert set(history_by_id) == set(candidate_order)
    assert all(
        row.policy_evaluation_status == "valid"
        for candidate_id, row in history_by_id.items()
        if candidate_id != "malformed"
    )
    malformed = history_by_id["malformed"]
    assert malformed.policy_evaluation_status == "invalid"
    assert malformed.policy_evaluation_error == "policy_evaluation_bundle_parse_failed"
    assert malformed.policy_evaluation is None
    assert malformed.objective_value == float("inf")
    assert malformed.is_promising is False
    assert result.telemetry["policy_evaluation_errors"] == 1
    infeasible = history_by_id["infeasible"].policy_evaluation
    assert infeasible is not None
    assert infeasible.feasible is False
    assert "governance:verdict_reject" in infeasible.blocking_reasons
    assert "verdict_reject" not in infeasible.blocking_reasons

    fresh_reader = ParetoRegistry(root=registry_root)
    snapshot = fresh_reader.get_snapshot(result.search_id)
    projection = snapshot.project_view(ParetoView.GLOBAL_FEASIBLE)
    frontier = fresh_reader.get_frontier(result.search_id, ParetoView.GLOBAL_FEASIBLE)
    frontier_ids = {entry.candidate_id for entry in frontier}
    entries_by_id = {entry.candidate_id: entry for entry in snapshot.entries.values()}
    expected_ids = {"front_a", "front_equal_identity", "incomparable"}
    feasible_hashes = {
        entry.candidate_hash
        for entry in snapshot.entries.values()
        if entry.evaluation.feasible and not entry.seed_only
    }

    assert set(entries_by_id) == set(candidate_order) - {"malformed"}
    assert entries_by_id["infeasible"].evaluation.feasible is False
    assert entries_by_id["infeasible"].candidate_hash not in projection.eligible_candidate_hashes
    assert set(projection.eligible_candidate_hashes) == feasible_hashes
    assert projection.assessment.status == "complete"
    assert projection.assessment.coverage_status == "complete"
    assert projection.assessment.input_count == len(feasible_hashes) == 5
    assert projection.assessment.assessed_count == len(feasible_hashes) == 5
    assert frontier_ids == expected_ids
    assert "dominated_equal_secondary" not in frontier_ids
    assert "dominated" not in frontier_ids
    assert len({entry.candidate_hash for entry in frontier}) == len(expected_ids)


@pytest.mark.parametrize(
    ("policy_direction", "employment_direction"),
    [
        pytest.param(
            ObjectiveDirection.MAXIMIZE,
            ObjectiveDirection.MINIMIZE,
            id="maximize-minimize",
        ),
        pytest.param(
            ObjectiveDirection.MINIMIZE,
            ObjectiveDirection.MAXIMIZE,
            id="minimize-maximize",
        ),
    ],
)
def test_pareto_registry_persists_directional_axes_for_fresh_reader(
    tmp_path, policy_direction, employment_direction
) -> None:
    normalized_rows = {
        "front": (10.0, -5.0),
        "front_duplicate_identity": (10.0, -5.0),
        "dominated_equal_secondary": (9.0, -5.0),
        "incomparable_lower_policy_value": (9.0, -4.0),
        "incomparable_higher_policy_value": (11.0, -8.0),
        "dominated": (8.0, -6.0),
    }
    expected_ids = {
        "front",
        "front_duplicate_identity",
        "incomparable_lower_policy_value",
        "incomparable_higher_policy_value",
    }
    declared_basis = ParetoBasisScope(
        scope="declared",
        coordinate_ids=["policy_value", "employment"],
        basis_ref="test:directional-policy-objectives.v1",
    )

    for order_index, order in enumerate((list(normalized_rows), list(reversed(normalized_rows)))):
        registry_root = tmp_path / f"direction_order_{order_index}"
        writer = ParetoRegistry(root=registry_root)
        for index, candidate_id in enumerate(order, start=1):
            policy_value, employment = normalized_rows[candidate_id]
            policy_raw = (
                policy_value if policy_direction is ObjectiveDirection.MAXIMIZE else -policy_value
            )
            employment_raw = (
                employment if employment_direction is ObjectiveDirection.MAXIMIZE else -employment
            )
            evaluation = PolicyEvaluationVector(
                candidate_id=candidate_id,
                primary={
                    "policy_value": ObjectiveChannelValue(
                        name="policy_value",
                        kind=ObjectiveKind.PRIMARY,
                        value=policy_raw,
                        direction=policy_direction,
                        source="typed_stage_b_evaluation",
                    ),
                    "employment": ObjectiveChannelValue(
                        name="employment",
                        kind=ObjectiveKind.PRIMARY,
                        value=employment_raw,
                        direction=employment_direction,
                        source="typed_stage_b_evaluation",
                    ),
                },
            )
            writer.update(
                "directional-policy-run",
                candidate_hash=f"sha256:{index:064x}",
                evaluation=evaluation,
                objective_basis_by_view={"global_feasible": declared_basis},
            )

        fresh_reader = ParetoRegistry(root=registry_root)
        snapshot = fresh_reader.get_snapshot("directional-policy-run")
        projection = snapshot.project_view(ParetoView.GLOBAL_FEASIBLE)
        frontier = fresh_reader.get_frontier("directional-policy-run", ParetoView.GLOBAL_FEASIBLE)

        assert {entry.candidate_id for entry in frontier} == expected_ids
        assert projection.assessment.status == "complete"
        assert projection.assessment.coverage_status == "complete"
        assert projection.assessment.basis_scope == declared_basis
        assert projection.assessment.input_count == len(normalized_rows)
        assert projection.assessment.assessed_count == len(normalized_rows)
        assert all(
            entry.evaluation.primary["policy_value"].direction is policy_direction
            and entry.evaluation.primary["employment"].direction is employment_direction
            for entry in snapshot.entries.values()
        )


def test_search_controller_accepts_policy_bundle_after_module_reload(tmp_path) -> None:
    candidate = _candidate()
    stack = ObjectiveStack()
    registry = ParetoRegistry(root=tmp_path / "pareto_registry")

    stale_bundle_cls = PolicyEvaluationBundle
    sys.modules.pop("polisyos.scientist.policy_design.objectives", None)
    reloaded = importlib.import_module("polisyos.scientist.policy_design.objectives")
    assert reloaded.PolicyEvaluationBundle is not stale_bundle_cls

    class StaticGenerator:
        def generate(self, history, current_best, context):
            return {"candidate_id": "candidate_b"}

    def stage_a(candidate_payload, context):
        return 0.0, True

    def stage_b(candidate_payload, context):
        return {
            "simulation_results": {},
            "feedback": {"verdict": "APPROVE"},
            "_policy_candidate_schema": candidate,
            "policy_evaluation_bundle": stale_bundle_cls(
                candidate=candidate,
                simulation_metrics={"policy_value": 11.0, "employment_rate": 0.9, "welfare": 12.0},
                distributional_report=_distributional_report(),
                causal_effect_report=_causal_effect_report(),
                cross_graph_profile=_cross_graph_profile(),
                uncertainty_envelope=_uncertainty(0.2),
            ),
        }

    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(1),
            objective=CompositeObjective([]),
            policy_objective_stack=stack,
            pareto_registry=registry,
        ),
        candidate_generator=StaticGenerator(),
        stage_a_evaluator=stage_a,
        stage_b_evaluator=stage_b,
    )

    result = controller.run(initial_context={})

    assert len(result.history) == 1
    evaluation = result.history[0].policy_evaluation
    assert isinstance(evaluation, reloaded.PolicyEvaluationVector)
    assert result.pareto_front == []
    assert result.pareto_projection is not None
    assert result.pareto_projection.assessment.status == "basis_limited"
    assert result.pareto_projection.ranked_frontier_hashes == ()
    assert len(result.pareto_projection.unassessed_candidate_hashes) == 1
    reopened = ParetoRegistry(root=tmp_path / "pareto_registry")
    entries = reopened.get_snapshot(result.search_id).entries
    assert len(entries) == 1
    persisted = next(iter(entries.values())).evaluation
    assert isinstance(persisted, PolicyEvaluationVector)
    assert persisted.model_dump(mode="json") == evaluation.model_dump(mode="json")


def test_search_controller_revalidates_reloaded_objective_result() -> None:
    stale_vector_cls = PolicyEvaluationVector
    sys.modules.pop("polisyos.scientist.policy_design.objectives", None)
    reloaded = importlib.import_module("polisyos.scientist.policy_design.objectives")
    assert reloaded.PolicyEvaluationVector is not stale_vector_cls

    class ForeignVector(BaseModel):
        candidate_id: str = "candidate_b"

    class ReturningStack:
        def __init__(self, result: object) -> None:
            self.result = result

        def evaluate(self, bundle: object) -> object:
            return self.result

    config = SearchConfig(
        stopping=MaxIterations(1),
        objective=CompositeObjective([]),
        policy_objective_stack=ReturningStack(reloaded.PolicyEvaluationVector()),
    )
    controller = SearchController(
        config=config,
        candidate_generator=MagicMock(),
        stage_a_evaluator=MagicMock(),
        stage_b_evaluator=MagicMock(),
    )
    stage_b_result = {"policy_evaluation_bundle": reloaded.PolicyEvaluationBundle()}

    ordinary = controller._resolve_policy_evaluation_with_status({}, stage_b_result)
    assert ordinary.status == "valid"
    assert isinstance(ordinary.value, reloaded.PolicyEvaluationVector)

    config.policy_objective_stack = ReturningStack(
        stale_vector_cls.model_construct(primary={"value": "not-a-channel"})
    )
    malformed = controller._resolve_policy_evaluation_with_status({}, stage_b_result)
    assert malformed.status == "invalid"
    assert malformed.value is None
    assert malformed.reason == "objective_stack_returned_invalid_vector"

    for untyped in ({"candidate_id": "candidate_b"}, ForeignVector()):
        config.policy_objective_stack = ReturningStack(untyped)
        rejected = controller._resolve_policy_evaluation_with_status({}, stage_b_result)
        assert rejected.status == "invalid"
        assert rejected.value is None
        assert rejected.reason == "objective_stack_returned_untyped_result"


def test_policy_vector_consumers_revalidate_across_module_reload() -> None:
    design_search = importlib.import_module("polisyos.scientist.policy_design.search")
    runtime_support = importlib.import_module(
        "polisyos.scientist.nodes.builtins.decide.policy_runtime_support"
    )
    hierarchical_search = importlib.import_module(
        "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search"
    )
    sys.modules.pop("polisyos.scientist.policy_design.objectives", None)
    current = importlib.import_module("polisyos.scientist.policy_design.objectives")
    vector = current.PolicyEvaluationVector(
        candidate_id="candidate_b",
        primary={
            "policy_value": current.ObjectiveChannelValue(
                name="policy_value",
                kind="primary",
                value=11.0,
                direction="maximize",
                source="measured_panel",
                metadata={"basis": "exact"},
            )
        },
        feasible=False,
        blocking_reasons=["hard_constraint"],
    )

    class ForeignVector(BaseModel):
        candidate_id: str = "candidate_b"

    for parse in (
        design_search._coerce_policy_evaluation,
        runtime_support._parse_policy_evaluation,
        hierarchical_search._coerce_policy_evaluation,
    ):
        restored = parse(vector)
        assert restored is not None
        assert restored.candidate_id == "candidate_b"
        assert restored.primary["policy_value"].source == "measured_panel"
        assert restored.primary["policy_value"].metadata == {"basis": "exact"}
        assert restored.feasible is False
        assert restored.blocking_reasons == ["hard_constraint"]

        serialized = parse(vector.model_dump(mode="json"))
        assert serialized is not None
        assert serialized.primary["policy_value"].source == "measured_panel"
        assert serialized.feasible is False
        assert parse(ForeignVector()) is None


def test_pareto_registry_rejects_malformed_owner_vector_before_write(tmp_path) -> None:
    registry = ParetoRegistry(root=tmp_path / "pareto_registry")
    malformed = PolicyEvaluationVector.model_construct(primary={"value": "not-a-channel"})
    schema_valid_raw = PolicyEvaluationVector(candidate_id="candidate_b").model_dump(mode="json")

    with pytest.raises(ValueError):
        registry.update("loop", candidate_hash="candidate_hash", evaluation=malformed)
    with pytest.raises(TypeError):
        registry.update("loop", candidate_hash="candidate_hash", evaluation=schema_valid_raw)

    assert registry.get_snapshot("loop").entries == {}


def test_direct_policy_runtime_workflow_engine_cannot_bypass_eval_safety_owner(
    monkeypatch,
) -> None:
    """Direct engine use is rejected by the production owner before evaluation work."""
    import polisyos.scientist.nodes.builtins.decide.policy_runtime_support as owner

    work_spy = MagicMock(side_effect=AssertionError("evaluation work must remain unreachable"))
    monkeypatch.setattr(owner, "_build_evidence_driven_simulation_metrics", work_spy)
    engine = _PolicyRuntimeWorkflowEngine(
        fidelity="selection",
        backend=ProductionPolicyEvaluationBackend(),
    )

    with pytest.raises(PolicyRuntimeEvaluationSafetyError) as exc_info:
        engine.run(
            {
                "policy_candidate_schema": _candidate(),
                "simulation_metrics": {"policy_value": 1.0},
            }
        )

    assert exc_info.value.blocker_codes == ("polisyos.eval_safety.execution_context_missing@1.0.0",)
    work_spy.assert_not_called()
