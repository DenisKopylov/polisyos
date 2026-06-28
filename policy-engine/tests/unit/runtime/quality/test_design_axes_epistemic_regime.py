from __future__ import annotations

import pytest

# EpistemicRegime literal is REUSED from the S0 narrow waist, not redefined.
from polisyos.pdc import AxisFirewallStatus, AxisPositionDeclaration

# CommitmentProfileRecord is the extend_existing reversibility/lifecycle/stakes record.
from polisyos.runtime.quality.case_lifecycle import (
    CommitmentProfileRecord,
    assert_stakes_floor_consistency,
    build_commitment_profile,
    select_floor,
)
from polisyos.runtime.quality.design_axes.epistemic_regime import (
    EpistemicRegimeClaim,
    P16OverconfidenceError,
    P16PrecautionLaunderingError,
    P23StakesFloorError,
    RegimeEvidenceBasis,
    build_s11_regime_strategy_constraint,
    classify_regime,
    regime_accuracy,
    regime_claim_to_axis_position,
    regime_design_strategy,
)

RULE_REF = "repo://docs/adr/0174-policy-evidence-capability-graph.md"


def _risk_evidence() -> RegimeEvidenceBasis:
    # Full risk-regime evidence present: exact substrate, measurability, calibration.
    return RegimeEvidenceBasis(
        claim_ref="claim:credit_program_enrollment:effect",
        substrate_binding_status="selected_exact",
        measurability_present=True,
        calibration_present=True,
        contested_scholar_edges=0,
        value_provenance_present=True,
        rule_version_ref=RULE_REF,
    )


def _sparse_evidence() -> RegimeEvidenceBasis:
    # S6 measurability / S11 calibration / S8 value provenance not yet built => absent.
    # Proxy binding + no risk evidence => uncertainty.
    return RegimeEvidenceBasis(
        claim_ref="claim:regional_displacement_pressure:effect",
        substrate_binding_status="selected_proxy_with_limitation",
        measurability_present=False,
        calibration_present=False,
        contested_scholar_edges=0,
        value_provenance_present=False,
        rule_version_ref=RULE_REF,
    )


def _blocked_evidence() -> RegimeEvidenceBasis:
    # Construct not observed and no risk evidence => ignorance (outcomes/possibilities problematic).
    return RegimeEvidenceBasis(
        claim_ref="claim:novel_second_order_mechanism:effect",
        substrate_binding_status="blocked_construct_not_observed",
        measurability_present=False,
        calibration_present=False,
        contested_scholar_edges=0,
        value_provenance_present=False,
        rule_version_ref=RULE_REF,
    )


def _reversible_low_stakes() -> CommitmentProfileRecord:
    return build_commitment_profile(
        candidate_ref="cand:001",
        reversibility="reversible",
        option_value="high",
        lifecycle_stage="greenfield",
        transition_cost="low",
        stakes="low",
        rule_version_ref=RULE_REF,
    )


def _irreversible_catastrophic() -> CommitmentProfileRecord:
    return build_commitment_profile(
        candidate_ref="cand:002",
        reversibility="irreversible",
        option_value="none",
        lifecycle_stage="transition",
        transition_cost="high",
        stakes="catastrophic",
        rule_version_ref=RULE_REF,
    )


def test_epistemic_regime_claim_reuses_s0_regime_literal() -> None:
    claim = classify_regime(_risk_evidence(), _reversible_low_stakes())
    assert isinstance(claim, EpistemicRegimeClaim)
    assert claim.regime in {"risk", "uncertainty", "ambiguity", "ignorance", "contested_model"}
    assert claim.evidence_basis.claim_ref  # regime is a claim, not a setting


def test_risk_requires_risk_evidence() -> None:
    # Full evidence + reversible/low-stakes => risk admissible.
    claim = classify_regime(_risk_evidence(), _reversible_low_stakes())
    assert claim.regime == "risk"
    assert claim.firewall_disposition == "pass"


def test_sparse_evidence_defaults_toward_uncertainty_not_risk() -> None:
    # Absent measurability/calibration/value provenance => cannot be risk (default to more uncertainty).
    claim = classify_regime(_sparse_evidence(), _reversible_low_stakes())
    assert claim.regime in {"uncertainty", "ambiguity", "ignorance", "contested_model"}
    assert claim.regime != "risk"


def test_p16_overconfidence_blocks_claimed_risk_without_evidence() -> None:
    # false_risk: declare risk with weak evidence => overconfidence firewall fails closed.
    with pytest.raises(
        P16OverconfidenceError,
        match="risk-regime authority without risk-regime evidence",
    ):
        classify_regime(_sparse_evidence(), _reversible_low_stakes(), declared_regime="risk")


def test_p16_precaution_laundering_blocks_downgrade_when_evidence_available() -> None:
    # false_precaution: risk evidence available, but a downgrade to uncertainty is attempted.
    with pytest.raises(P16PrecautionLaunderingError, match="risk-regime evidence was available"):
        classify_regime(_risk_evidence(), _reversible_low_stakes(), declared_regime="uncertainty")


def test_b_side_may_not_regime_shop() -> None:
    # A generator-preferred regime cannot override the A claim; only A classifies.
    claim = classify_regime(_sparse_evidence(), _reversible_low_stakes())
    assert claim.classified_by == "A_gate"
    assert claim.b_side_preference_honored is False


def test_regime_strategy_mapping() -> None:
    assert (
        regime_design_strategy("risk", _reversible_low_stakes()) == "expected_welfare_optimization"
    )
    assert regime_design_strategy("uncertainty", _reversible_low_stakes()) == "robust_satisficing"
    assert (
        regime_design_strategy("ambiguity", _reversible_low_stakes()) == "frame_indexed_portfolio"
    )
    assert regime_design_strategy("ignorance", _reversible_low_stakes()) == (
        "precautionary_adaptive_pathway"
    )


def test_s11_stale_calibration_creates_regime_strategy_constraint() -> None:
    constraint = build_s11_regime_strategy_constraint(
        constraint_ref="constraint://s11/regime/strategic-response",
        source_ref="pdc://layer2/s11/ua-msme/calibration/strategic-response",
        calibration_status="stale",
        rule_version_ref="policyos.layer2.s11.predictive_knowledge.v1",
    )

    assert constraint.cell_ref == "KNOWLEDGE.epistemic_regime"
    assert constraint.status == "limit"
    assert constraint.reruns_s4_producer is False
    assert "epistemic_regime_classification" in (
        constraint.authority_boundary.may_not_use_for
    )


def test_irreversible_high_stakes_under_ignorance_routes_to_precaution() -> None:
    # Cluster semantic_test: irreversible high-stakes + ignorance => precaution, never risk optimization.
    strategy = regime_design_strategy("ignorance", _irreversible_catastrophic())
    assert strategy == "precautionary_adaptive_pathway"


def test_commitment_profile_overrides_strategy_for_catastrophic_irreversible() -> None:
    # Even a "risk" regime cannot drive point optimization on a catastrophic irreversible commitment.
    strategy = regime_design_strategy("risk", _irreversible_catastrophic())
    assert strategy in {"robust_satisficing", "precautionary_adaptive_pathway"}
    assert strategy != "expected_welfare_optimization"


def test_p23_low_stakes_floor_on_catastrophic_irreversible_fails() -> None:
    with pytest.raises(P23StakesFloorError, match="low-stakes floor"):
        assert_stakes_floor_consistency(_irreversible_catastrophic(), selected_floor="low_stakes")


def test_commitment_profile_derives_from_domain_signals() -> None:
    # First-class producer: domain drives the baseline (no explicit reversibility/stakes given).
    climate = build_commitment_profile(
        candidate_ref="c1",
        rule_version_ref=RULE_REF,
        domain="climate_adaptation",
    )
    assert (climate.reversibility, climate.stakes) == ("irreversible", "catastrophic")
    credit = build_commitment_profile(
        candidate_ref="c2",
        rule_version_ref=RULE_REF,
        domain="msme_credit_grant",
        policy_time="2022",
    )
    assert (credit.reversibility, credit.lifecycle_stage) == ("pilotable", "emergency")
    unknown = build_commitment_profile(candidate_ref="c3", rule_version_ref=RULE_REF, domain="???")
    assert unknown.reversibility == "irreversible"  # conservative default


def test_commitment_annotation_gold_overrides_derivation() -> None:
    prof = build_commitment_profile(
        candidate_ref="c4",
        rule_version_ref=RULE_REF,
        domain="msme_credit_grant",
        annotation={"reversibility": "irreversible", "stakes": "catastrophic"},
    )
    assert (prof.reversibility, prof.stakes) == ("irreversible", "catastrophic")


def test_select_floor_tracks_commitment_profile() -> None:
    assert select_floor(_irreversible_catastrophic()) == "high_stakes"
    assert select_floor(_reversible_low_stakes()) == "low_stakes"


def test_blocked_construct_classifies_as_ignorance_with_no_outcome_claims() -> None:
    # Deterministic ignorance (not a vacuous `if`): blocked construct + no risk evidence.
    claim = classify_regime(_blocked_evidence(), _irreversible_catastrophic())
    assert claim.regime == "ignorance"
    # Ignorance carries process/precaution properties only; outcome claims prohibited (D2.5).
    assert "outcome_claim" in " ".join(claim.authority_boundary.may_not_use_for)
    # End-to-end: classify -> strategy is precautionary, not point optimization.
    assert claim.strategy_consequence == "precautionary_adaptive_pathway"


def test_regime_accuracy_penalizes_false_risk_more_than_false_caution() -> None:
    # predicted vs gold; false-risk (predict risk, gold uncertainty) >> false-caution penalty.
    false_risk = regime_accuracy(predicted=["risk"], gold=["uncertainty"])
    false_caution = regime_accuracy(predicted=["uncertainty"], gold=["risk"])
    assert false_risk["penalized_score"] < false_caution["penalized_score"]
    assert false_risk["false_risk_count"] == 1
    assert false_caution["false_risk_count"] == 0


def test_regime_claim_projects_to_axis_position_and_firewall_status() -> None:
    claim = classify_regime(_sparse_evidence(), _reversible_low_stakes())
    pos, fw = regime_claim_to_axis_position(claim)
    assert isinstance(pos, AxisPositionDeclaration) and pos.cell_ref == "KNOWLEDGE.epistemic_regime"
    assert isinstance(fw, AxisFirewallStatus) and "P16" in fw.pattern_ids


def test_classifier_is_deterministic_replay_safe() -> None:
    # T3: regime is a pure function of the recorded evidence basis (same in => same out).
    a = classify_regime(_sparse_evidence(), _reversible_low_stakes())
    b = classify_regime(_sparse_evidence(), _reversible_low_stakes())
    assert a.model_dump() == b.model_dump()


def test_frame_plurality_yields_ambiguity_and_frame_indexed_strategy() -> None:
    # Ambiguity is reachable only with an explicit frame-plurality signal (reliable detection is S8).
    evidence = _sparse_evidence().model_copy(update={"frame_plurality": True})
    claim = classify_regime(evidence, _reversible_low_stakes())
    assert claim.regime == "ambiguity"
    assert claim.strategy_consequence == "frame_indexed_portfolio"
