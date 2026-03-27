from __future__ import annotations

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import from_canonical_bytes
from decimal import Decimal

from polisyos.ir.governance.policy_spec import InterventionSpec, ParameterSpec, PolicySpec
from polisyos.ir.governance.problem_frame import (
    ConstraintSpec,
    ConstraintType,
    ObjectiveSpec,
    ProblemDomain,
    ProblemFrame,
)
from polisyos.ir.kernel.values import MoneyValue
from polisyos.ir.model_spec import AssumptionSpec, AssumptionType, ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import OptimizationDirection, SelectorOperator
from polisyos.scientist.nodes.builtins.decide.build_decision_packet import BuildDecisionPacketNode
from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
    BuildPolicyOutputBundleNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_POLICY_BRIEF_REF,
    ARTIFACT_POLICY_OUTPUT_BUNDLE_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
from polisyos.scientist.policy_design.output import load_policy_artifact_bundle
from polisyos.scientist.policy_design.output import PolicyBrief, load_replayable_audit_bundle
from polisyos.scientist.policy_design.translator import TranslatorComplianceResult
from polisyos.scientist.search import (
    ActionableSideInformation,
    persist_actionable_side_information,
)
from polisyos.scientist.search.funnel.orchestrator import FunnelOutcome
from polisyos.scientist.search.funnel.types import FunnelStageResult, UncertaintyEnvelope
from polisyos.scientist.search.readiness import DecisionReadiness

from polisyos.scientist.policy_design.objectives import (
    ConstraintStatus,
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    PolicyEvaluationVector,
)

from polisyos.scientist.policy_design.schema import TargetPopulationSpec

from polisyos.scientist.search.readiness import DecisionReadinessContract


def _bundle() -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="problem_policy",
            domain=ProblemDomain.FISCAL,
            objectives=[
                ObjectiveSpec(
                    objective_id="welfare",
                    metric_id="welfare_metric",
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
            policy_id="policy_policy",
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
                    schedule={"start_step": 0, "duration_steps": 2},
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
            model_id="model_policy",
            data_snapshot_ref="sha256:" + "1" * 64,
            assumptions=[
                AssumptionSpec(
                    assumption_id="elasticity",
                    assumption_type=AssumptionType.PARAMETRIC,
                    description="Elasticity remains stable in the policy horizon.",
                )
            ],
        ),
    )


def _candidate() -> PolicyCandidateSchema:
    return PolicyCandidateSchema.from_trinity_bundle(
        _bundle(),
        candidate_id="candidate_policy",
        metadata={"policy_family": "core_family", "evidence_depth": "replicated"},
    ).model_copy(
        update={
            "target_population": TargetPopulationSpec(
                population_id="population_policy",
                description="General population",
                geography="national",
            )
        }
    )


def _evaluation_vector(candidate: PolicyCandidateSchema) -> PolicyEvaluationVector:
    return PolicyEvaluationVector(
        candidate_id=candidate.candidate_id,
        primary={
            "policy_value": ObjectiveChannelValue(
                name="policy_value",
                kind=ObjectiveKind.PRIMARY,
                value=1.2,
                direction=ObjectiveDirection.MAXIMIZE,
            )
        },
        hard_constraints={
            "policy_budget_constraint": ObjectiveChannelValue(
                name="policy_budget_constraint",
                kind=ObjectiveKind.HARD_CONSTRAINT,
                value=0.95,
                direction=ObjectiveDirection.MINIMIZE,
                threshold=1.0,
                status=ConstraintStatus.NEAR_BINDING,
            )
        },
        feasible=True,
        metadata={"candidate_hash": candidate.candidate_hash()},
    )


def _readiness_contract() -> DecisionReadinessContract:
    return DecisionReadinessContract(
        readiness_level=DecisionReadiness.RECOMMENDATION_READY,
        required_judges_passed=["structural"],
        required_uncertainty_bounds={},
        mandatory_human_gate=False,
        assumptions_must_be_surfaced=["Elasticity remains stable in the policy horizon."],
        expiry_conditions=["freshness_violation"],
        evidence_depth_required="replicated",
    )


def _policy_brief() -> PolicyBrief:
    return PolicyBrief(
        title="Policy brief for candidate_policy",
        executive_summary="Candidate improves welfare while keeping the budget constraint near binding.",
        readiness_level=DecisionReadiness.RECOMMENDATION_READY.value,
        surfaced_assumptions=["Elasticity remains stable in the policy horizon."],
        subgroup_harms=["Low income"],
        hard_constraint_notes=["policy_budget_constraint"],
    )


def _translator_compliance() -> TranslatorComplianceResult:
    return TranslatorComplianceResult(passed=True, findings=[])


def test_build_policy_output_bundle_skips_outside_policy_mode(execution_context, minimal_state):
    outcome = BuildPolicyOutputBundleNode().execute(execution_context, minimal_state)
    assert outcome.status == "skip"


def test_build_policy_output_bundle_writes_refs(execution_context, minimal_state, cas_store):
    candidate = _candidate()
    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_schema": candidate.model_dump(mode="json"),
            "policy_evaluation": _evaluation_vector(candidate).model_dump(mode="json"),
            "decision_readiness_contract": _readiness_contract().model_dump(mode="json"),
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": _translator_compliance().model_dump(mode="json"),
        }
    )

    outcome = BuildPolicyOutputBundleNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert ARTIFACT_POLICY_OUTPUT_BUNDLE_REF in outcome.state.artifacts_index
    assert ARTIFACT_POLICY_BRIEF_REF in outcome.state.artifacts_index
    bundle = load_policy_artifact_bundle(
        cas_store,
        outcome.state.artifacts_index[ARTIFACT_POLICY_OUTPUT_BUNDLE_REF],
    )
    assert bundle.policy_brief_ref is not None
    assert outcome.state.policy_output_bundle_ref == outcome.state.artifacts_index[ARTIFACT_POLICY_OUTPUT_BUNDLE_REF]


def test_build_policy_output_bundle_propagates_actionable_side_information(
    execution_context,
    minimal_state,
    cas_store,
):
    candidate = _candidate()
    side_info_ref = persist_actionable_side_information(
        cas_store,
        ActionableSideInformation(candidate_id=candidate.candidate_id),
    )
    funnel_outcome = FunnelOutcome(
        ticket_id="ticket_policy",
        candidate_hash=candidate.candidate_hash(),
        trace=[],
        stage_results={},
        final_result=FunnelStageResult(
            policy_candidate={},
            objective_value=1.0,
            is_promising=True,
            stage_name="funnel_L6_promotion",
            uncertainty_envelope=UncertaintyEnvelope.deterministic(),
        ),
        failure_cards=[],
        uncertainty_envelope=UncertaintyEnvelope.deterministic(),
        compute_actual_usd=0.5,
        degradation_mode="normal",
        final_action="complete",
        completed=True,
        audit_refs=[side_info_ref],
        actionable_side_information_refs=[side_info_ref],
    )

    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_candidate_schema": candidate.model_dump(mode="json"),
            "policy_evaluation": _evaluation_vector(candidate).model_dump(mode="json"),
            "decision_readiness_contract": _readiness_contract().model_dump(mode="json"),
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": _translator_compliance().model_dump(mode="json"),
            "funnel_outcome": funnel_outcome,
        }
    )

    outcome = BuildPolicyOutputBundleNode().execute(execution_context, state)

    assert outcome.status == "ok"
    bundle = load_policy_artifact_bundle(
        cas_store,
        outcome.state.artifacts_index[ARTIFACT_POLICY_OUTPUT_BUNDLE_REF],
    )
    audit_bundle = load_replayable_audit_bundle(cas_store, bundle.replayable_audit_bundle_ref)

    assert [ref.artifact_id for ref in bundle.actionable_side_information_refs] == [
        side_info_ref.artifact_id
    ]
    assert [ref.artifact_id for ref in bundle.audit_refs] == [side_info_ref.artifact_id]
    assert [ref.artifact_id for ref in audit_bundle.actionable_side_information_refs] == [
        side_info_ref.artifact_id
    ]


def test_build_policy_output_bundle_fails_when_required_inputs_missing(execution_context, minimal_state):
    state = minimal_state.model_copy(deep=True)
    state.params.update({"workflow_id": "scientist_policy_design", "policy_mode": True})

    outcome = BuildPolicyOutputBundleNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None


def test_decision_packet_not_mutated_when_policy_bundle_absent(tmp_path) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.engine.context import ExecutionContext
    from polisyos.scientist.engine.state import ExperimentState

    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_no_policy")
    import logging

    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = store.put_json(
        {"trinity": {}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    data_snapshot_ref = store.put_json(
        {"data_ref": None},
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    state = ExperimentState(
        run_id="R_packet_no_policy",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        params={"random_seed": 1},
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    payload = from_canonical_bytes(store.get_bytes(outcome.artifacts[0].artifact_id))

    assert "policy_output_bundle" not in payload
