from __future__ import annotations

from polisyos.runtime.quality.case_lifecycle import build_commitment_profile
from polisyos.runtime.quality.design_axes.epistemic_regime import (
    RegimeEvidenceBasis,
    build_s11_regime_strategy_constraint,
    classify_regime,
    regime_claim_to_axis_position,
)


def test_s11_out_of_scope_constraint_blocks_consumption_without_reclassifying_s4() -> None:
    """A downstream calibration gap constrains use without rewriting the S4 claim."""

    evidence = RegimeEvidenceBasis(
        claim_ref="claim://municipal-bridge/recruitment-effect",
        substrate_binding_status="selected_proxy_with_limitation",
        measurability_present=False,
        calibration_present=False,
        contested_scholar_edges=2,
        expert_disagreement="high",
        value_provenance_present=False,
        rule_version_ref="policyos.layer2.s4.epistemic_regime.v1",
    )
    commitment = build_commitment_profile(
        candidate_ref="candidate://municipal-bridge/pilot",
        reversibility="pilotable",
        option_value="high",
        lifecycle_stage="greenfield",
        transition_cost="low",
        stakes="low",
        rule_version_ref="policyos.layer2.s4.epistemic_regime.v1",
    )
    claim = classify_regime(evidence, commitment)
    position, firewall = regime_claim_to_axis_position(claim)
    constraint = build_s11_regime_strategy_constraint(
        constraint_ref="pdc://municipal-bridge/s11/regime-constraint",
        source_ref="pdc://municipal-bridge/s11/calibration-not-in-scope",
        calibration_status="out_of_scope",
        rule_version_ref="policyos.layer2.s11.predictive_knowledge.v1",
    )

    assert claim.regime == "contested_model"
    assert position.position == claim.regime
    assert firewall.status == "limit"
    assert constraint.status == "block"
    assert constraint.reruns_s4_producer is False
    assert "epistemic_regime_classification" in constraint.authority_boundary.may_not_use_for
