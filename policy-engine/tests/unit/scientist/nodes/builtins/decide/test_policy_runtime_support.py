import inspect
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.ids import ArtifactID
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
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality import WorldModelRecord, world_model_record_content_hash
from polisyos.runtime.quality.evaluation_safety import (
    EvalSafetyAdmissionChallenge,
    EvalSafetyConsumerAdmissionReceipt,
    EvaluationExecutionContext,
    EvaluationInputProvenance,
    evaluation_execution_context_hash,
)
from polisyos.runtime.quality.world_model_record import (
    BranchMode,
    DataForgeBindingRef,
    FabricWorldRef,
    FoundryBindingRef,
    PolicySlotBinding,
    ResolvedSubstrateEntryRef,
    SimulationModelRef,
    SkgCausalPriorRef,
    SubstrateRegistryRef,
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
    PRODUCTION_POLICY_EVALUATION_BACKEND_ID,
    PolicyRuntimeEvaluationSafetyError,
    ProductionPolicyEvaluationBackend,
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


def _policy_candidate() -> PolicyCandidateSchema:
    return PolicyCandidateSchema.from_trinity_bundle(
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


def _digest(char: str) -> str:
    return "sha256:" + char * 64


def _world_model_record() -> WorldModelRecord:
    fields: dict[str, Any] = {
        "schema_version": "policyos.runtime.world_model_record.v1",
        "authority_status": "bound",
        "producer_ref": "test.gy_o0.scientist",
        "region_or_jurisdiction": "UA-30",
        "population_scope": "wartime_msme",
        "policy_domain": "fiscal_credit",
        "valid_time_scope": "2026-08-28/2026-12-31",
        "tx_time_scope": "2026-08-28T00:00:00+00:00",
        "resolution": "firm_month",
        "branch_mode": BranchMode.OBSERVED,
        "fabric_world_ref": FabricWorldRef(
            snapshot_root="/tmp/policyos-test-world",
            snapshot_id="snapshot-2026-08-28",
            branch="main",
            world_query_policy="as_of_valid_and_tx_time",
            provenance_manifest_ref="manifest://fabric/gy-o0",
            content_query_digest=_digest("1"),
            content_query_row_count=2,
        ),
        "data_forge_binding_ref": DataForgeBindingRef(
            snapshot_id="snapshot-2026-08-28",
            release_id="release-gy-o0",
            role="academic",
            read_api_identity="data_forge.read_api.gy_o0",
            snapshot_ref="snapshot://data-forge/gy-o0",
            merkle_root="merkle:gy-o0",
            data_hash=_digest("2"),
            provenance_manifest_ref="manifest://data-forge/gy-o0",
        ),
        "simulation_model_ref": SimulationModelRef(
            model_spec_ref=_digest("3"),
            model_spec_hash=_digest("4"),
            model_id="model_gy_o0",
            data_snapshot_ref=_digest("5"),
            registry_bundle_ref=_digest("6"),
            fidelity_level="high",
            calibrated=True,
            calibration_ref=_digest("7"),
        ),
        "foundry_binding_ref": FoundryBindingRef(
            input_bindings_ref=_digest("8"),
            bound_state_snapshot_ref=_digest("9"),
            mapping_rules_ref=_digest("a"),
            state_slot_digest=_digest("b"),
        ),
        "skg_causal_prior_ref": SkgCausalPriorRef(
            skg_snapshot_ref="skg://gy-o0",
            skg_version_id="skg-v1",
            source_data_snapshot_id="snapshot-2026-08-28",
        ),
        "substrate_registry_ref": SubstrateRegistryRef(
            substrate_version_id="substrate_version_1111111111111111",
            content_hash=_digest("c"),
            resolved_entries=(
                ResolvedSubstrateEntryRef(
                    source_id="l5_measurement_registry",
                    family_id="firm_fundamentals",
                    layer="L5",
                    coverage_score=0.8,
                    trust_tier="authoritative_partial_coverage",
                    trust_cap=0.85,
                    identification_mode="point_identified",
                    schema_regime_id="ukraine_schema_v2",
                    data_version="l5-calibration-d2",
                    snapshot_id="snapshot-2026-08-28",
                    source_snapshot_id="snapshot-2026-08-28",
                    entry_content_hash=_digest("d"),
                ),
            ),
        ),
        "policy_slot_map": (
            PolicySlotBinding(
                slot_id="agents.income",
                state_path="agents.income",
                entity_scope="agent",
                temporal_granularity="month",
            ),
        ),
    }
    draft = WorldModelRecord.model_construct(
        world_model_record_id="world_model_record_0000000000000000",
        content_hash=_digest("0"),
        **fields,
    )
    content_hash = world_model_record_content_hash(draft)
    return WorldModelRecord(
        world_model_record_id=f"world_model_record_{content_hash.removeprefix('sha256:')[:16]}",
        content_hash=content_hash,
        **fields,
    )


def _production_safety_context(
    candidate: PolicyCandidateSchema,
    world_model_record: WorldModelRecord,
    simulation_metrics: dict[str, float],
) -> EvaluationExecutionContext:
    candidate_ref = EvaluationArtifactRef.from_payload(
        artifact_id=candidate.candidate_id,
        artifact_type="candidate",
        payload=candidate.model_dump(mode="json"),
        schema_ref="polisyos.scientist.policy_candidate@1.0",
        uri="runtime://candidate/policy-runtime",
        version="1.0.0",
    )
    metrics_ref = EvaluationArtifactRef.from_payload(
        artifact_id="polisyos.test.policy-runtime-metrics",
        artifact_type="simulation_metrics",
        payload=simulation_metrics,
        schema_ref="polisyos.scientist.simulation_metrics@1.0",
        uri="runtime://scientist/policy-runtime-metrics",
        version="1.0.0",
    )
    world_ref = EvaluationArtifactRef(
        artifact_id=world_model_record.world_model_record_id,
        artifact_type="world_model_record",
        content_hash=world_model_record.content_hash,
        schema_ref="policyos.runtime.world_model_record.v1",
        uri="runtime://world-model/policy-runtime",
        version="1.0.0",
    )
    return EvaluationExecutionContext(
        intake_ref=EvaluationArtifactRef(
            artifact_id="polisyos.test.policy-runtime-intake",
            artifact_type="evaluation_attempt_intake",
            content_hash=_digest("e"),
            schema_ref="policyos.runtime.eval_safety.intake.v1",
            uri="runtime://eval-safety/policy-runtime-intake",
            version="1.0.0",
        ),
        evaluator_owner_id=PRODUCTION_POLICY_EVALUATION_BACKEND_ID,
        design_problem_ref=_digest("f"),
        evaluation_mode="field_pilot",
        candidate_ref=candidate_ref,
        world_model_record_ref=world_ref,
        target_population_scope_ref=EvaluationArtifactRef.from_payload(
            artifact_id="polisyos.test.policy-runtime-population",
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
                predicate_provenance="independently_reconciled",
            ),
        ),
        eval_safety_certificate_ref=EvaluationArtifactRef(
            artifact_id="polisyos.test.policy-runtime-certificate",
            artifact_type="eval_safety_certificate",
            content_hash=_digest("1"),
            schema_ref="policyos.runtime.eval_safety.certificate.v1",
            uri="runtime://eval-safety/policy-runtime-certificate",
            version="1.0.0",
        ),
        eval_safety_revision_head_ref=EvaluationArtifactRef(
            artifact_id="polisyos.test.policy-runtime-revision",
            artifact_type="eval_safety_certificate_revision",
            content_hash=_digest("2"),
            schema_ref="policyos.runtime.eval_safety.certificate_revision.v1",
            uri="runtime://eval-safety/policy-runtime-revision",
            version="1.0.0",
        ),
    )


class _ForeignPositiveVerifier:
    def __init__(self) -> None:
        self.calls: list[tuple[EvaluationExecutionContext, EvalSafetyAdmissionChallenge]] = []

    def require_admission(
        self,
        context: EvaluationExecutionContext,
        challenge: EvalSafetyAdmissionChallenge,
    ) -> EvalSafetyConsumerAdmissionReceipt:
        self.calls.append((context, challenge))
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


def test_direct_backend_promotion_state_injection_cannot_bypass_eval_safety(
    monkeypatch,
) -> None:
    """Promotion state cannot alter the production owner's missing-context refusal."""
    import polisyos.scientist.nodes.builtins.decide.policy_runtime_support as runtime_support

    candidate = _policy_candidate()
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

    errors: list[RuntimeError] = []
    results = []
    for promotion_state in (
        None,
        {"status": "certified", "promotable": True},
        {"status": "passed", "certificate": "forged"},
    ):
        del promotion_state
        try:
            results.append(
                backend.evaluate(
                    candidate,
                    fidelity="selection",
                    simulation_metrics={"policy_value": 1.0},
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

    assert results == []
    assert len(errors) == 3
    assert {error.blocker_codes for error in errors if hasattr(error, "blocker_codes")} == {
        ("polisyos.eval_safety.execution_context_missing@1.0.0",)
    }
    assert metrics_spy.call_count == 0
    assert objective_spy.call_count == 0


def test_production_backend_binds_actual_world_model_record_not_model_spec_hash(
    monkeypatch,
) -> None:
    """An honest typed WMR reaches verification even when ModelSpec hashes differ."""
    import polisyos.scientist.nodes.builtins.decide.policy_runtime_support as runtime_support

    candidate = _policy_candidate()
    world_model_record = _world_model_record()
    simulation_metrics = {"policy_value": 1.0}
    context = _production_safety_context(candidate, world_model_record, simulation_metrics)
    verifier = _ForeignPositiveVerifier()
    metrics_spy = MagicMock()
    objective_spy = MagicMock()
    monkeypatch.setattr(
        runtime_support,
        "_build_evidence_driven_simulation_metrics",
        metrics_spy,
    )
    monkeypatch.setattr(runtime_support.ObjectiveStack, "evaluate", objective_spy)

    model_spec_hash = gy_content_hash(candidate.trinity_bundle.model_spec.model_dump(mode="json"))
    assert world_model_record.content_hash != model_spec_hash

    backend = ProductionPolicyEvaluationBackend(
        eval_safety_execution_context=context,
        eval_safety_verifier=verifier,
        world_model_record=world_model_record,
    )
    with pytest.raises(PolicyRuntimeEvaluationSafetyError) as exc_info:
        backend.evaluate(
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

    assert exc_info.value.blocker_codes == (
        "polisyos.eval_safety.consumer_admission_blocked@1.0.0",
    )
    assert len(verifier.calls) == 1
    assert verifier.calls[0][0] is context
    assert verifier.calls[0][1].consumer_component_id == PRODUCTION_POLICY_EVALUATION_BACKEND_ID
    assert metrics_spy.call_count == 0
    assert objective_spy.call_count == 0


@pytest.mark.parametrize("mutation", ["content", "identity", "schema_family"])
def test_mutated_world_model_record_blocks_before_policy_runtime_work(
    monkeypatch,
    mutation: str,
) -> None:
    """WMR bytes, identity, and canonical family all bind before verification."""
    import polisyos.scientist.nodes.builtins.decide.policy_runtime_support as runtime_support

    candidate = _policy_candidate()
    world_model_record = _world_model_record()
    simulation_metrics = {"policy_value": 1.0}
    context = _production_safety_context(candidate, world_model_record, simulation_metrics)
    active_record = world_model_record
    active_context = context
    if mutation == "content":
        active_record = world_model_record.model_copy(update={"policy_domain": "changed-domain"})
    elif mutation == "identity":
        active_record = world_model_record.model_copy(
            update={"world_model_record_id": "world_model_record_deadbeefdeadbeef"}
        )
    else:
        active_context = context.model_copy(
            update={
                "world_model_record_ref": context.world_model_record_ref.model_copy(
                    update={"schema_ref": "polisyos.ir.model_spec@1.0"}
                )
            }
        )

    verifier = _ForeignPositiveVerifier()
    metrics_spy = MagicMock()
    objective_spy = MagicMock()
    monkeypatch.setattr(
        runtime_support,
        "_build_evidence_driven_simulation_metrics",
        metrics_spy,
    )
    monkeypatch.setattr(runtime_support.ObjectiveStack, "evaluate", objective_spy)
    backend = ProductionPolicyEvaluationBackend(
        eval_safety_execution_context=active_context,
        eval_safety_verifier=verifier,
        world_model_record=active_record,
    )

    with pytest.raises(PolicyRuntimeEvaluationSafetyError) as exc_info:
        backend.evaluate(
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

    assert exc_info.value.blocker_codes == (
        "polisyos.eval_safety.world_model_record_binding_mismatch@1.0.0",
    )
    assert verifier.calls == []
    assert metrics_spy.call_count == 0
    assert objective_spy.call_count == 0


@pytest.mark.parametrize(
    "mutation",
    ["actual_input_changed", "candidate_identity_changed", "consumer_asserted"],
)
def test_actual_input_or_untrusted_provenance_blocks_before_policy_runtime_work(
    monkeypatch,
    mutation: str,
) -> None:
    """Production input identities and predicate provenance are owner-recomputed."""
    import polisyos.scientist.nodes.builtins.decide.policy_runtime_support as runtime_support

    candidate = _policy_candidate()
    world_model_record = _world_model_record()
    bound_metrics = {"policy_value": 1.0}
    active_metrics = {"policy_value": 9.0} if mutation == "actual_input_changed" else bound_metrics
    context = _production_safety_context(candidate, world_model_record, bound_metrics)
    if mutation == "candidate_identity_changed":
        forged_candidate_ref = context.candidate_ref.model_copy(
            update={"artifact_id": "polisyos.test.same-candidate-bytes-wrong-identity"}
        )
        context = context.model_copy(
            update={
                "candidate_ref": forged_candidate_ref,
                "evaluation_input_refs": (
                    forged_candidate_ref,
                    context.evaluation_input_refs[1],
                ),
                "evaluation_input_provenance": (
                    context.evaluation_input_provenance[0].model_copy(
                        update={"input_ref": forged_candidate_ref}
                    ),
                    context.evaluation_input_provenance[1],
                ),
            }
        )
    elif mutation == "consumer_asserted":
        context = context.model_copy(
            update={
                "evaluation_input_provenance": (
                    context.evaluation_input_provenance[0].model_copy(
                        update={"predicate_provenance": "consumer_asserted"}
                    ),
                    context.evaluation_input_provenance[1],
                )
            }
        )

    verifier = _ForeignPositiveVerifier()
    metrics_spy = MagicMock()
    objective_spy = MagicMock()
    monkeypatch.setattr(
        runtime_support,
        "_build_evidence_driven_simulation_metrics",
        metrics_spy,
    )
    monkeypatch.setattr(runtime_support.ObjectiveStack, "evaluate", objective_spy)
    backend = ProductionPolicyEvaluationBackend(
        eval_safety_execution_context=context,
        eval_safety_verifier=verifier,
        world_model_record=world_model_record,
    )

    with pytest.raises(PolicyRuntimeEvaluationSafetyError) as exc_info:
        backend.evaluate(
            candidate,
            fidelity="selection",
            simulation_metrics=active_metrics,
            uncertainty=None,
            distributional_report=None,
            causal_effect_report=None,
            cross_graph_profile=None,
            governance_report=None,
            ambiguity_certificate=None,
        )

    assert exc_info.value.blocker_codes == (
        "polisyos.eval_safety.execution_context_binding_mismatch@1.0.0",
    )
    assert verifier.calls == []
    assert metrics_spy.call_count == 0
    assert objective_spy.call_count == 0


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
