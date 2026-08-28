from datetime import UTC, datetime
from unittest.mock import MagicMock

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.components import ComponentId
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
)
from polisyos.ir.analytics.causal_discovery import (
    AlgebraicConstraintReport,
    CausalDiscoveryReport,
    LatentAssumptionCard,
    LatentDiscoveryBundle,
    LatentTrustLevel,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.pdc import ArtifactRef as EvaluationArtifactRef
from polisyos.runtime.quality.evaluation_safety import (
    EvalSafetyAdmissionChallenge,
    EvalSafetyConsumerAdmissionReceipt,
    EvaluationExecutionContext,
    EvaluationInputProvenance,
    evaluation_execution_context_hash,
)
from polisyos.scientist.methods.discovery.aggregator import EvidenceWeightedAggregator
from polisyos.scientist.methods.discovery.output import (
    DiscoveryArtifactBuilder,
    DiscoveryArtifactBuildInput,
)
from polisyos.scientist.methods.discovery.portfolio import PortfolioCandidate, PortfolioRunResult
from polisyos.scientist.methods.discovery.priors import GraphPriorBuilder, PriorKnowledgeBundle
from polisyos.scientist.methods.discovery.schema import graph_hypothesis_from_report
from polisyos.scientist.methods.discovery.stability import (
    BootstrapMode,
    BootstrapStabilityConfig,
    BootstrapStabilityReport,
    HypothesisStabilitySummary,
)
from polisyos.scientist.methods.discovery.utility_judge import (
    DownstreamUtilityJudge,
    UtilityJudgeInput,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    load_effective_latent_discovery_bundle_for_state,
    resolve_effective_latent_discovery_bundle_for_state,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DISCOVERY_ARTIFACT_BUNDLE_REF,
)
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema


def _query() -> CausalQuery:
    return CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="X",
        treatment_value=1.0,
        outcome_variable="Y",
    )


def _graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y", "Z"],
        edges=[CausalEdge(src="X", dst="Y", combined_confidence=0.9)],
        discovery_method="pc",
    )


def test_direct_backend_promotion_state_injection_cannot_bypass_eval_safety(
    monkeypatch,
) -> None:
    """Direct production calls fail before metrics or objective evaluation."""

    import inspect

    import polisyos.scientist.nodes.builtins.decide.policy_runtime_support as runtime_support

    candidate = PolicyCandidateSchema.from_trinity_bundle(
        TrinityBundle(
            problem_frame=ProblemFrame(
                problem_id="problem_direct_eval_safety",
                domain=ProblemDomain.FISCAL,
            ),
            policy_spec=PolicySpec(policy_id="policy_direct_eval_safety"),
            model_spec=ModelSpec(
                model_id="model_direct_eval_safety",
                data_snapshot_ref="sha256:" + "1" * 64,
            ),
        ),
        candidate_id="candidate_direct_eval_safety",
    )
    vector = PolicyEvaluationVector(candidate_id=candidate.candidate_id)
    metrics_spy = MagicMock(
        return_value=(
            {"policy_value": 1.0},
            ("simulation_metrics",),
            (),
        )
    )
    objective_spy = MagicMock(return_value=vector)
    monkeypatch.setattr(
        runtime_support,
        "_build_evidence_driven_simulation_metrics",
        metrics_spy,
    )
    monkeypatch.setattr(runtime_support.ObjectiveStack, "evaluate", objective_spy)

    backend = runtime_support.ProductionPolicyEvaluationBackend()
    signature = inspect.signature(backend.evaluate)
    assert not any("promotion" in name for name in signature.parameters)
    assert all(
        parameter.kind is not inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )

    promotion_variants = (
        None,
        {"status": "certified", "promotable": True},
        {"status": "passed", "certificate": "forged"},
    )
    simulation_metrics = {"policy_value": 1.0}
    candidate_ref = EvaluationArtifactRef.from_payload(
        artifact_id="polisyos.test.policy_runtime_candidate",
        artifact_type="candidate",
        payload=candidate.model_dump(mode="json"),
        schema_ref="polisyos.scientist.policy_candidate@1.0",
        uri="runtime://candidate/policy-runtime",
        version="1.0.0",
    )
    metrics_ref = EvaluationArtifactRef.from_payload(
        artifact_id="polisyos.test.policy_runtime_metrics",
        artifact_type="simulation_metrics",
        payload=simulation_metrics,
        schema_ref="polisyos.scientist.simulation_metrics@1.0",
        uri="runtime://scientist/policy-runtime-metrics",
        version="1.0.0",
    )
    certificate_ref = EvaluationArtifactRef.from_payload(
        artifact_id="polisyos.test.policy_runtime_certificate",
        artifact_type="eval_safety_certificate",
        payload={"certificate": "foreign"},
        schema_ref="policyos.runtime.eval_safety.certificate.v1",
        uri="runtime://eval-safety/policy-runtime-certificate",
        version="1.0.0",
    )
    revision_ref = EvaluationArtifactRef.from_payload(
        artifact_id="polisyos.test.policy_runtime_revision",
        artifact_type="eval_safety_certificate_revision",
        payload={"revision": "foreign"},
        schema_ref="policyos.runtime.eval_safety.certificate_revision.v1",
        uri="runtime://eval-safety/policy-runtime-revision",
        version="1.0.0",
    )
    safety_context = EvaluationExecutionContext(
        intake_ref=EvaluationArtifactRef.from_payload(
            artifact_id="polisyos.test.policy_runtime_intake",
            artifact_type="evaluation_attempt_intake",
            payload={"attempt": "policy-runtime"},
            schema_ref="policyos.runtime.eval_safety.intake.v1",
            uri="runtime://eval-safety/policy-runtime-intake",
            version="1.0.0",
        ),
        evaluator_owner_id=ComponentId.parse(
            "scientist.production_policy_evaluation_backend@1.0.0"
        ),
        design_problem_ref="sha256:" + "5" * 64,
        evaluation_mode="field_pilot",
        candidate_ref=candidate_ref,
        world_model_record_ref=EvaluationArtifactRef.from_payload(
            artifact_id="polisyos.test.policy_runtime_wmr",
            artifact_type="world_model_record",
            payload=candidate.trinity_bundle.model_spec.model_dump(mode="json"),
            schema_ref="polisyos.ir.model_spec@1.0",
            uri="runtime://world-model/policy-runtime",
            version="1.0.0",
        ),
        target_population_scope_ref=EvaluationArtifactRef.from_payload(
            artifact_id="polisyos.test.policy_runtime_population",
            artifact_type="target_population_scope",
            payload=candidate.target_population.model_dump(mode="json"),
            schema_ref="polisyos.scientist.target_population@1.0",
            uri="runtime://population/policy-runtime",
            version="1.0.0",
        ),
        rule_version="polisyos.runtime.eval_safety@1.0.0",
        intended_start_at=datetime(2026, 8, 28, tzinfo=UTC),
        evaluation_input_refs=(candidate_ref, metrics_ref),
        evaluation_input_provenance=(
            EvaluationInputProvenance(
                input_ref=candidate_ref,
                input_class="real_world",
                predicate_provenance="recomputed",
            ),
            EvaluationInputProvenance(
                input_ref=metrics_ref,
                input_class="real_world",
                predicate_provenance="recomputed",
            ),
        ),
        eval_safety_certificate_ref=certificate_ref,
        eval_safety_revision_head_ref=revision_ref,
    )

    class ForeignPositiveVerifier:
        def __init__(self) -> None:
            self.calls = 0

        def require_admission(
            self,
            context: EvaluationExecutionContext,
            challenge: EvalSafetyAdmissionChallenge,
        ) -> EvalSafetyConsumerAdmissionReceipt:
            self.calls += 1
            return EvalSafetyConsumerAdmissionReceipt(
                status="verified",
                intake_ref=context.intake_ref,
                certificate_ref=context.eval_safety_certificate_ref,
                current_revision_head_ref=context.eval_safety_revision_head_ref,
                execution_context_hash=evaluation_execution_context_hash(context),
                challenge=challenge,
                blocker_codes=(),
                verified_at=datetime(2026, 8, 28, tzinfo=UTC),
            )

    foreign_verifier = ForeignPositiveVerifier()
    foreign_backend = runtime_support.ProductionPolicyEvaluationBackend(
        eval_safety_execution_context=safety_context,
        eval_safety_verifier=foreign_verifier,
    )

    results = []
    errors: list[RuntimeError] = []
    for active_backend in (backend, foreign_backend):
        for promotion_state in promotion_variants:
            del promotion_state
            try:
                results.append(
                    active_backend.evaluate(
                        candidate,
                        fidelity="selection",
                        simulation_metrics=simulation_metrics,
                        uncertainty=None,
                        distributional_report=None,
                        causal_effect_report=None,
                        cross_graph_profile=None,
                        governance_report=None,
                        ambiguity_certificate=None,
                    )
                )
            except RuntimeError as exc:
                errors.append(exc)

    assert metrics_spy.call_count == 0
    assert objective_spy.call_count == 0
    assert results == []
    error_type = getattr(runtime_support, "PolicyRuntimeEvaluationSafetyError", RuntimeError)
    assert {type(error) for error in errors} == {error_type}
    assert {error.blocker_codes for error in errors if hasattr(error, "blocker_codes")} == {
        ("polisyos.eval_safety.execution_context_missing@1.0.0",),
        ("polisyos.eval_safety.consumer_admission_blocked@1.0.0",),
    }
    assert foreign_verifier.calls == 3


def test_runtime_loads_latent_bundle_from_discovery_artifact_and_merges_proxy_boundary(
    execution_context,
    minimal_state,
) -> None:
    discovery_report = CausalDiscoveryReport(
        method="pc",
        graph=_graph(),
        algebraic_constraints=AlgebraicConstraintReport(severity="warning"),
        latent_discovery=LatentDiscoveryBundle(
            proposed_latent_nodes=["U_income"],
            inducing_environments=["region"],
            identification_conditions=["proxy_quality"],
            falsification_tests=["negative_control_outcome"],
            trust_level=LatentTrustLevel.RESEARCH,
            assumption_cards=[
                LatentAssumptionCard(
                    assumption_id="latent_card",
                    title="Latent confounding remains research-only",
                    description="Observed proxies may still mask latent confounding.",
                )
            ],
            no_promotion_reasons=["latent_discovery_proof_only"],
        ),
        metadata={"algebraic_constraint_severity": "warning"},
    )
    hypothesis = graph_hypothesis_from_report(discovery_report, hypothesis_id="pc_main")
    stability = BootstrapStabilityReport(
        bootstrap_mode=BootstrapMode.ROW,
        config=BootstrapStabilityConfig(n_resamples=3),
        summaries=[
            HypothesisStabilitySummary(
                hypothesis_id="pc_main",
                edge_selection_frequency={"X->Y": 0.9},
                mean_edge_stability=0.9,
                adjustment_set_stability=0.8,
                completed_resamples=3,
            )
        ],
    )
    utility = DownstreamUtilityJudge().evaluate(
        UtilityJudgeInput(
            hypotheses=[hypothesis],
            stability_report=stability,
            causal_query=_query(),
        )
    )
    matrix = EvidenceWeightedAggregator().aggregate([hypothesis], stability, utility)
    bundle_ref = DiscoveryArtifactBuilder().build(
        execution_context.store,
        DiscoveryArtifactBuildInput(
            run_id="R_phase_e_runtime",
            task_id="task_phase_e_runtime",
            variable_names=["X", "Y", "Z"],
            causal_query=_query(),
            hypotheses=[hypothesis],
            portfolio_result=PortfolioRunResult(
                candidates=[
                    PortfolioCandidate(
                        hypothesis=hypothesis,
                        source_report=discovery_report,
                        method_params={"significance_level": 0.05},
                    )
                ]
            ),
            edge_confidence_matrix=matrix,
            bootstrap_stability_report=stability,
            downstream_utility_report=utility,
            graph_prior_bundle=GraphPriorBuilder().build(matrix, utility),
            prior_knowledge_bundle=PriorKnowledgeBundle(),
        ),
    )
    state = minimal_state.model_copy(
        update={
            "artifacts_index": {
                **minimal_state.artifacts_index,
                ARTIFACT_DISCOVERY_ARTIFACT_BUNDLE_REF: bundle_ref,
            }
        }
    )
    causal_report = CausalEffectReport(
        method=CausalMethod.DOWHY_BACKDOOR,
        status=EstimationStatus.SUCCESS,
        estimand="ATE(X,Y)",
        point_estimate=0.4,
        confidence_interval=(0.1, 0.7),
        inference_method="bootstrap",
        sample_size=120,
        n_treated=60,
        n_control=60,
        pre_periods=0,
        post_periods=1,
        metadata={
            "proxy_boundary": {
                "boundary_notes": [
                    "Observed proxy path may still explain the effect without latent promotion."
                ],
                "no_promotion_reasons": ["proxy_explanation_not_ruled_out"],
            }
        },
    )

    latent_bundle = load_effective_latent_discovery_bundle_for_state(
        execution_context,
        state,
        causal_report=causal_report,
    )

    assert latent_bundle is not None
    assert latent_bundle.readiness_cap == "proof_only"
    assert latent_bundle.promotion_allowed is False
    assert latent_bundle.human_gate_required is True
    assert latent_bundle.metadata["source_hypothesis_ids"] == ["pc_main"]
    assert latent_bundle.metadata["proxy_boundary"]["boundary_notes"] == [
        "Observed proxy path may still explain the effect without latent promotion."
    ]
    assert "proxy_explanation_not_ruled_out" in latent_bundle.no_promotion_reasons


def test_runtime_marks_unreadable_discovery_bundle_ref_as_latent_resolution_error(
    execution_context,
    minimal_state,
) -> None:
    discovery_report = CausalDiscoveryReport(
        method="pc",
        graph=_graph(),
        latent_discovery=LatentDiscoveryBundle(
            proposed_latent_nodes=["U_income"],
            inducing_environments=["region"],
            identification_conditions=["proxy_quality"],
            falsification_tests=["negative_control_outcome"],
            trust_level=LatentTrustLevel.RESEARCH,
            assumption_cards=[
                LatentAssumptionCard(
                    assumption_id="latent_card",
                    title="Latent confounding remains research-only",
                    description="Observed proxies may still mask latent confounding.",
                )
            ],
            no_promotion_reasons=["latent_discovery_proof_only"],
        ),
    )
    hypothesis = graph_hypothesis_from_report(discovery_report, hypothesis_id="pc_main")
    stability = BootstrapStabilityReport(
        bootstrap_mode=BootstrapMode.ROW,
        config=BootstrapStabilityConfig(n_resamples=3),
        summaries=[
            HypothesisStabilitySummary(
                hypothesis_id="pc_main",
                edge_selection_frequency={"X->Y": 0.9},
                mean_edge_stability=0.9,
                adjustment_set_stability=0.8,
                completed_resamples=3,
            )
        ],
    )
    utility = DownstreamUtilityJudge().evaluate(
        UtilityJudgeInput(
            hypotheses=[hypothesis],
            stability_report=stability,
            causal_query=_query(),
        )
    )
    matrix = EvidenceWeightedAggregator().aggregate([hypothesis], stability, utility)
    bundle_ref = DiscoveryArtifactBuilder().build(
        execution_context.store,
        DiscoveryArtifactBuildInput(
            run_id="R_phase_e_runtime_error",
            task_id="task_phase_e_runtime_error",
            variable_names=["X", "Y", "Z"],
            causal_query=_query(),
            hypotheses=[hypothesis],
            portfolio_result=PortfolioRunResult(
                candidates=[
                    PortfolioCandidate(
                        hypothesis=hypothesis,
                        source_report=discovery_report,
                        method_params={"significance_level": 0.05},
                    )
                ]
            ),
            edge_confidence_matrix=matrix,
            bootstrap_stability_report=stability,
            downstream_utility_report=utility,
            graph_prior_bundle=GraphPriorBuilder().build(matrix, utility),
            prior_knowledge_bundle=PriorKnowledgeBundle(),
        ),
    )
    broken_ref = bundle_ref.model_copy(update={"artifact_id": ArtifactID.from_sha256_hex("f" * 64)})
    state = minimal_state.model_copy(
        update={
            "artifacts_index": {
                **minimal_state.artifacts_index,
                ARTIFACT_DISCOVERY_ARTIFACT_BUNDLE_REF: broken_ref,
            }
        }
    )

    resolution = resolve_effective_latent_discovery_bundle_for_state(
        execution_context,
        state,
    )

    assert resolution.status == "unreadable"
    assert resolution.bundle is None
    assert resolution.source_bundle_ref == broken_ref
    assert resolution.error_payload() is not None
    assert resolution.error_payload()["error_code"]
