from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("jax")

from polisyos.scientist.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.nodes.builtins.decide.run_policy_translation import (
    RunPolicyTranslationNode,
)
from polisyos.scientist.nodes.builtins.decide.run_translator_compliance import (
    RunTranslatorComplianceNode,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_POLICY_BRIEF_REF
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
from polisyos.scientist.search.readiness import (
    DecisionReadiness,
    DecisionReadinessContract,
)


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
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with (
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
        outcome = RunPolicyTranslationNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "params.policy_brief",
        "policy_brief_ref",
        "artifacts_index.policy_brief_ref",
    )
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

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with (
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
            side_effect=[brief, promotion_result],
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
        outcome = RunTranslatorComplianceNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == ("params.translator_compliance",)
    assert state.params["nested"] == {"baseline": True}
    assert outcome.state.params["translator_compliance"] == {"passed": True}
