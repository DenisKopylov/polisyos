from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("jax")

from polisyos.scientist.methods.search.readiness import (
    DecisionReadiness,
    DecisionReadinessContract,
)
from polisyos.scientist.nodes.builtins.decide.run_policy_translation import (
    RunPolicyTranslationNode,
)
from polisyos.scientist.nodes.builtins.decide.run_translator_compliance import (
    RunTranslatorComplianceNode,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_POLICY_BRIEF_REF
from polisyos.scientist.orchestration.engine.state_branching import (
    branch_state as real_branch_state,
)
from polisyos.scientist.policy_design.output import (
    ChampionPolicyDossier,
    ConstraintSatisfactionEntry,
    ConstraintSatisfactionReport,
    ImplementationPlan,
    PolicyBrief,
    RecommendedAction,
    SubgroupImpactEntry,
    SubgroupImpactReport,
    UncertaintyReport,
)

_POLICY_PROMOTION_PROJECTION_WRITE_PATHS = (
    "params.policy_promotion_result",
    "params.judge_verdict",
    "params.decision_readiness_contract",
    "params.promotion_decision",
    "params.policy_promotion_projection_status",
    "params.policy_brief",
    "params.translator_compliance",
    "params.reported_policy_promotion_history",
    "policy_output_bundle_ref",
    "policy_brief_ref",
    "champion_policy_dossier_ref",
    "artifacts_index.champion_policy_dossier_ref",
    "artifacts_index.claims_ref",
    "artifacts_index.constraint_satisfaction_report_ref",
    "artifacts_index.decision_readiness_contract_ref",
    "artifacts_index.governance_gate_packet_ref",
    "artifacts_index.implementation_plan_ref",
    "artifacts_index.judge_verdict_ref",
    "artifacts_index.policy_brief_ref",
    "artifacts_index.policy_frontier_report_ref",
    "artifacts_index.policy_output_bundle_ref",
    "artifacts_index.policy_transportability_report_ref",
    "artifacts_index.policy_uncertainty_report_ref",
    "artifacts_index.rejected_alternatives_summary_ref",
    "artifacts_index.replayable_audit_bundle_ref",
    "artifacts_index.subgroup_impact_report_ref",
    "artifacts_index.validation_report_ref",
    "reports_index.governance_report_ref",
    "params.reported_governance_report_history",
)


def _expected_branch_write_paths(*output_paths: str) -> tuple[str, ...]:
    """Return the explicit output contract plus complete promotion invalidation scope."""
    return (
        *output_paths,
        *(
            path
            for path in _POLICY_PROMOTION_PROJECTION_WRITE_PATHS
            if path not in output_paths
        ),
    )


def _passing_judge_verdict() -> dict[str, object]:
    return {
        "per_judge": {
            name: {"judge_name": name, "passed": True, "is_fatal": True}
            for name in (
                "structural",
                "statistical",
                "robustness",
                "governance",
                "reproducibility",
                "compute",
            )
        },
        "composite_decision": "promote",
        "blocking_failures": [],
        "warnings": [],
    }


def _readiness_contract() -> DecisionReadinessContract:
    return DecisionReadinessContract(
        readiness_level=DecisionReadiness.SIMULATION_READY,
        required_judges_passed=["structural"],
        required_uncertainty_bounds={},
        mandatory_human_gate=False,
        assumptions_must_be_surfaced=["Elasticity remains stable in the policy horizon."],
        expiry_conditions=["freshness_violation"],
        evidence_depth_required="single_study",
    )


def _constraint_report(candidate_id: str) -> ConstraintSatisfactionReport:
    return ConstraintSatisfactionReport(
        candidate_id=candidate_id,
        feasible=True,
        constraints=[
            ConstraintSatisfactionEntry(
                constraint_name="policy_budget_constraint",
                status="near_binding",
                observed_value=0.95,
                threshold=1.0,
            )
        ],
    )


def _subgroup_report(candidate_id: str) -> SubgroupImpactReport:
    return SubgroupImpactReport(
        candidate_id=candidate_id,
        harmed_subgroups=[
            SubgroupImpactEntry(
                subgroup_id="low_income",
                label="Low income",
                direction="negative",
                net_impact=-1.0,
                vulnerable=True,
            )
        ],
    )


def _uncertainty_report(candidate_id: str) -> UncertaintyReport:
    return UncertaintyReport(
        candidate_id=candidate_id,
        readiness_level=DecisionReadiness.SIMULATION_READY.value,
        uncertainties={"statistical": 0.2, "structural": 0.3},
        binding_types=[],
    )


def _implementation_plan(candidate_id: str) -> ImplementationPlan:
    return ImplementationPlan(
        candidate_id=candidate_id,
        recommended_actions=[
            RecommendedAction(
                title="Review rollout safeguards",
                description="Confirm monitoring and rollback triggers before deployment.",
                priority="high",
            )
        ],
    )


def _dossier(candidate_id: str, candidate_hash: str) -> ChampionPolicyDossier:
    return ChampionPolicyDossier(
        candidate_id=candidate_id,
        candidate_hash=candidate_hash,
        readiness_level=DecisionReadiness.SIMULATION_READY.value,
        executive_summary="Candidate is simulation ready with bounded uncertainty.",
        objective_summary={"policy_value": 1.2, "employment": 0.4},
        constraint_summary=_constraint_report(candidate_id).constraints,
        subgroup_harms=["Low income"],
        surfaced_assumptions=_readiness_contract().assumptions_must_be_surfaced,
        uncertainty_summary={"statistical": 0.2, "structural": 0.3},
        transport_summary={},
        governance_summary={},
        stress_summary={},
    )


def _policy_brief() -> PolicyBrief:
    return PolicyBrief(
        title="Policy brief for cand-123",
        executive_summary="Candidate is simulation ready with bounded uncertainty.",
        readiness_level=DecisionReadiness.SIMULATION_READY.value,
        surfaced_assumptions=["Elasticity remains stable in the policy horizon."],
        uncertainty_highlights=["statistical: 0.200", "structural: 0.300"],
        subgroup_harms=["Low income"],
        hard_constraint_notes=["policy_budget_constraint"],
    )


def test_policy_translation_uses_branch_state_for_declared_outputs(
    execution_context, minimal_state, artifact_ref_factory
):
    candidate_ref = artifact_ref_factory(kind="scientist.policy_candidate")
    brief_ref = artifact_ref_factory(kind="scientist.policy_brief")
    candidate = MagicMock()
    candidate.candidate_hash.return_value = "cand-123"
    brief = _policy_brief()
    promotion_result = SimpleNamespace(
        promotion_decision=SimpleNamespace(promoted=True),
        readiness_ref=None,
        judge_verdict=MagicMock(),
    )
    readiness = _readiness_contract()
    builder = MagicMock()
    builder._build_constraint_report.return_value = _constraint_report("cand-123")
    builder._build_subgroup_report.return_value = _subgroup_report("cand-123")
    builder._build_uncertainty_report.return_value = _uncertainty_report("cand-123")
    builder._build_transportability_report.return_value = MagicMock()
    builder._build_governance_gate_packet.return_value = MagicMock()
    builder._build_implementation_plan.return_value = _implementation_plan("cand-123")
    builder._build_dossier.return_value = _dossier("cand-123", candidate.candidate_hash())

    state = minimal_state.model_copy(deep=True)
    state.params["nested"] = {"baseline": True}
    state.params["judge_verdict"] = _passing_judge_verdict()
    observed: dict[str, tuple[str, ...]] = {}
    expected_write_paths = _expected_branch_write_paths(
        "params.policy_brief",
        "policy_brief_ref",
        "artifacts_index.policy_brief_ref",
        "artifacts_index.validation_report_ref",
        "artifacts_index.judge_verdict_ref",
    )
    node = RunPolicyTranslationNode()
    assert tuple(node.spec.state_writes) == expected_write_paths

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with (
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_policy_translation._resolve_current_policy_promotion_result",
            return_value=(promotion_result, None),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_policy_translation.branch_state",
            _spy_branch,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_policy_translation._is_policy_mode",
            return_value=True,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_policy_translation._resolve_readiness_contract",
            return_value=readiness,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_policy_translation._brief_required",
            return_value=True,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_policy_translation._parse_model",
            return_value=promotion_result,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_policy_translation._resolve_candidate",
            return_value=(candidate, candidate_ref),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_policy_translation._policy_build_input",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_policy_translation.PolicyArtifactBuilder",
            return_value=builder,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_policy_translation.PolicyTranslatorWorker",
        ) as worker_cls,
    ):
        worker_cls.return_value.translate_and_persist.return_value = (brief, brief_ref)
        outcome = node.execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == expected_write_paths
    assert outcome.state.params is not state.params
    assert outcome.state.params["nested"] is state.params["nested"]
    assert state.params["nested"] == {"baseline": True}
    assert ARTIFACT_POLICY_BRIEF_REF not in state.artifacts_index
    assert outcome.state.policy_brief_ref == brief_ref


def test_translator_compliance_uses_branch_state_for_declared_outputs(
    execution_context, minimal_state, artifact_ref_factory
):
    candidate_ref = artifact_ref_factory(kind="scientist.policy_candidate")
    candidate = MagicMock()
    candidate.candidate_hash.return_value = "cand-456"
    brief = _policy_brief()
    promotion_result = SimpleNamespace(
        promotion_decision=SimpleNamespace(promoted=True),
        readiness_ref=None,
        judge_verdict=MagicMock(),
    )
    readiness = _readiness_contract()
    builder = MagicMock()
    builder._build_constraint_report.return_value = _constraint_report("cand-456")
    builder._build_subgroup_report.return_value = _subgroup_report("cand-456")
    builder._build_uncertainty_report.return_value = _uncertainty_report("cand-456")
    builder._build_transportability_report.return_value = MagicMock()
    builder._build_governance_gate_packet.return_value = MagicMock()
    builder._build_implementation_plan.return_value = _implementation_plan("cand-456")
    builder._build_dossier.return_value = _dossier("cand-456", candidate.candidate_hash())
    compliance = MagicMock()
    compliance.passed = True
    compliance.findings = []
    compliance.model_dump.return_value = {"passed": True}

    state = minimal_state.model_copy(deep=True)
    state.params["nested"] = {"baseline": True}
    observed: dict[str, tuple[str, ...]] = {}
    expected_write_paths = _expected_branch_write_paths("params.translator_compliance")
    node = RunTranslatorComplianceNode()
    assert tuple(node.spec.state_writes) == expected_write_paths

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with (
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_translator_compliance._resolve_current_policy_promotion_result",
            return_value=(promotion_result, None),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_translator_compliance.branch_state",
            _spy_branch,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_translator_compliance._is_policy_mode",
            return_value=True,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_translator_compliance._resolve_readiness_contract",
            return_value=readiness,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_translator_compliance._brief_required",
            return_value=True,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_translator_compliance._parse_model",
            return_value=brief,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_translator_compliance._resolve_candidate",
            return_value=(candidate, candidate_ref),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_translator_compliance._policy_build_input",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_translator_compliance.PolicyArtifactBuilder",
            return_value=builder,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_translator_compliance.TranslatorCompliancePass",
        ) as compliance_cls,
    ):
        compliance_cls.return_value.evaluate.return_value = compliance
        outcome = node.execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == expected_write_paths
    assert outcome.state.params is not state.params
    assert outcome.state.params["nested"] is state.params["nested"]
    assert state.params["nested"] == {"baseline": True}
    assert outcome.state.params["translator_compliance"] == {"passed": True}


def test_stale_positive_promotion_and_cached_brief_remain_report_only(
    execution_context, minimal_state, artifact_ref_factory
):
    from polisyos.scientist.methods.autotune.models import PromotionDecision
    from polisyos.scientist.methods.search.judge_stack import JudgeVerdict, PolicyPromotionResult
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
        _resolve_current_policy_promotion_result,
    )

    typed_result = PolicyPromotionResult(
        judge_verdict=JudgeVerdict.model_validate(_passing_judge_verdict()),
        readiness_contract=_readiness_contract(),
        promotion_decision=PromotionDecision(
            loop_id="stale-positive",
            promoted=True,
            reason="caller supplied",
        ),
    )
    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "workflow_id": "scientist_policy_design",
            "policy_mode": True,
            "policy_promotion_result": typed_result.model_dump(mode="json"),
            "policy_promotion_projection_status": {
                "status": "available",
                "authority_status": "verified",
                "owner_receipt_ref": {"artifact_id": "caller-controlled"},
            },
            "policy_brief": _policy_brief().model_dump(mode="json"),
            "translator_compliance": {"passed": True},
        }
    )
    stale_brief_ref = artifact_ref_factory(kind="scientist.policy_brief")
    state.policy_brief_ref = stale_brief_ref
    state.artifacts_index[ARTIFACT_POLICY_BRIEF_REF] = stale_brief_ref

    current, reason = _resolve_current_policy_promotion_result(state)
    assert current is None
    assert reason == "protected_owner_receipt_not_established"

    with (
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_policy_translation._is_policy_mode",
            return_value=True,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_policy_translation._resolve_readiness_contract",
            side_effect=AssertionError("stale promotion must be rejected before readiness use"),
        ),
    ):
        translated = RunPolicyTranslationNode().execute(execution_context, state)
    assert translated.status == "skip"
    assert state.params["policy_brief"]["title"] == _policy_brief().title

    with (
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_translator_compliance._is_policy_mode",
            return_value=True,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.run_translator_compliance._brief_required",
            side_effect=AssertionError("stale promotion must be rejected before compliance"),
        ),
    ):
        compliance = RunTranslatorComplianceNode().execute(execution_context, state)
    assert compliance.status == "skip"
    assert state.params["translator_compliance"] == {"passed": True}

    for projected_state in (translated.state, compliance.state):
        projection_status = projected_state.params["policy_promotion_projection_status"]
        assert projection_status["status"] == "reported_only"
        assert projection_status["authority_status"] == "not_established"
        assert "policy_brief" not in projected_state.params
        assert "translator_compliance" not in projected_state.params
        assert projected_state.policy_brief_ref is None
        assert ARTIFACT_POLICY_BRIEF_REF not in projected_state.artifacts_index
        archived_projection = next(
            entry
            for entry in projected_state.params["reported_policy_promotion_history"]
            if entry.get("record_type") == "prior_current_projection"
        )
        assert archived_projection["params"]["policy_brief"]["title"] == _policy_brief().title
        assert archived_projection["refs"]["artifacts_index"][ARTIFACT_POLICY_BRIEF_REF]
