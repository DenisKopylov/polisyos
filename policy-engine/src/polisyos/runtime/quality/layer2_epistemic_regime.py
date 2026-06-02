"""Layer 2 S4 A-owned epistemic-regime classification."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.pdc import (
    AuthorityBoundary,
    AxisFirewallStatus,
    AxisPositionDeclaration,
    EpistemicRegime,
)
from polisyos.runtime.quality.case_lifecycle import (
    CommitmentProfileRecord,
    P23StakesFloorError,
)

LAYER2_S4_EPISTEMIC_REGIME_SCHEMA_VERSION = (
    "policyos.policy_design_case.layer2_s4_epistemic_regime.v1"
)

DesignStrategy = Literal[
    "expected_welfare_optimization",
    "robust_satisficing",
    "frame_indexed_portfolio",
    "precautionary_adaptive_pathway",
]
S11PredictiveCalibrationStatus = Literal[
    "pass",
    "absent",
    "stale",
    "poor",
    "out_of_scope",
]

_EXACT_BINDING_STATUSES = frozenset({"selected_exact", "selected_derived"})
_BLOCKED_BINDING_STATUSES = frozenset(
    {
        "blocked_construct_not_observed",
        "blocked_acquisition_required",
    }
)
_HARD_COMMITMENT = frozenset({"lock_in", "irreversible"})
_NON_RISK_REGIMES = frozenset({"uncertainty", "ambiguity", "ignorance", "contested_model"})
_FALSE_RISK_WEIGHT = 3.0
_FALSE_CAUTION_WEIGHT = 1.0


class P16OverconfidenceError(ValueError):
    """Risk-regime authority claimed without risk-regime evidence."""


class P16PrecautionLaunderingError(ValueError):
    """Non-risk regime claimed when risk-regime evidence is available."""


class _S4Model(BaseModel):
    """Strict base model for S4 regime artifacts."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["policyos.policy_design_case.layer2_s4_epistemic_regime.v1"] = (
        LAYER2_S4_EPISTEMIC_REGIME_SCHEMA_VERSION
    )


class RegimeEvidenceBasis(_S4Model):
    """Recorded evidence basis that makes regime a claim, not a setting."""

    claim_ref: str = Field(min_length=1)
    substrate_binding_status: str = Field(min_length=1)
    measurability_present: bool
    calibration_present: bool
    method_boundary_conditions_met: bool | None = None
    precedent_strength: Literal["none", "weak", "strong"] = "none"
    expert_disagreement: Literal["none", "some", "high"] = "none"
    contested_scholar_edges: int = Field(default=0, ge=0)
    robustness_sensitivity_available: bool = False
    value_provenance_present: bool = False
    frame_plurality: bool = False
    rule_version_ref: str = Field(min_length=1)

    @property
    def has_risk_evidence(self) -> bool:
        """Return whether the evidence basis can support risk-regime authority."""

        return (
            self.substrate_binding_status in _EXACT_BINDING_STATUSES
            and self.measurability_present
            and self.calibration_present
            and self.method_boundary_conditions_met is not False
        )


class EpistemicRegimeClaim(_S4Model):
    """A-side per-claim regime classification and strategy consequence."""

    claim_ref: str = Field(min_length=1)
    regime: EpistemicRegime
    evidence_basis: RegimeEvidenceBasis
    firewall_disposition: Literal["pass", "limit", "block"]
    asymmetry_penalty: float = Field(ge=0.0)
    decision_reason: str = Field(min_length=1)
    strategy_consequence: DesignStrategy
    classified_by: Literal["A_gate"] = "A_gate"
    b_side_preference_honored: bool = False
    authority_boundary: AuthorityBoundary


class S11RegimeStrategyConstraint(_S4Model):
    """Consumer-side S11 constraint on regime strategy without reclassifying S4."""

    constraint_ref: str = Field(min_length=1)
    cell_ref: Literal["KNOWLEDGE.epistemic_regime"] = "KNOWLEDGE.epistemic_regime"
    source_ref: str = Field(min_length=1)
    calibration_status: S11PredictiveCalibrationStatus
    status: Literal["pass", "limit", "block"]
    reruns_s4_producer: bool = False
    reason: str = Field(min_length=1)
    authority_boundary: AuthorityBoundary


def regime_design_strategy(
    regime: EpistemicRegime,
    commitment: CommitmentProfileRecord,
) -> DesignStrategy:
    """Select the design strategy from the A-owned regime and commitment profile."""

    if commitment.stakes == "catastrophic" and commitment.reversibility in _HARD_COMMITMENT:
        return "precautionary_adaptive_pathway"
    if regime == "ignorance":
        return "precautionary_adaptive_pathway"
    if regime == "ambiguity":
        return "frame_indexed_portfolio"
    if regime in {"uncertainty", "contested_model"}:
        return "robust_satisficing"
    if commitment.is_high_commitment:
        return "robust_satisficing"
    return "expected_welfare_optimization"


def classify_regime(
    evidence: RegimeEvidenceBasis,
    commitment: CommitmentProfileRecord,
    *,
    declared_regime: EpistemicRegime | None = None,
) -> EpistemicRegimeClaim:
    """Classify one claim's epistemic regime with P16 firewalls.

    Args:
        evidence: Recorded substrate, contestability, and absent-signal basis.
        commitment: Reversibility/lifecycle/stakes profile consumed by strategy.
        declared_regime: Optional external declaration used only to test P16 failures.

    Returns:
        A deterministic, A-gate-owned regime claim.

    Raises:
        P16OverconfidenceError: If risk is declared without risk-grade evidence.
        P16PrecautionLaunderingError: If non-risk is declared despite risk-grade evidence.
    """

    if declared_regime == "risk" and not evidence.has_risk_evidence:
        raise P16OverconfidenceError(
            "cannot claim risk-regime authority without risk-regime evidence"
        )
    if declared_regime in _NON_RISK_REGIMES and evidence.has_risk_evidence:
        raise P16PrecautionLaunderingError(
            "cannot downgrade when risk-regime evidence was available"
        )

    if evidence.has_risk_evidence:
        regime: EpistemicRegime = "risk"
        disposition: Literal["pass", "limit", "block"] = "pass"
        penalty = 0.0
        reason = "exact substrate, measurability, calibration, and method boundaries present"
    elif evidence.frame_plurality:
        regime = "ambiguity"
        disposition = "limit"
        penalty = 1.0
        reason = "plural incommensurable frames cap strategy at frame-indexed design"
    elif evidence.contested_scholar_edges > 0 or evidence.expert_disagreement == "high":
        regime = "contested_model"
        disposition = "limit"
        penalty = 1.0
        reason = "models are materially contested by Scholar edges or expert disagreement"
    elif evidence.substrate_binding_status in _BLOCKED_BINDING_STATUSES:
        regime = "ignorance"
        disposition = "limit"
        penalty = 2.0
        reason = "construct is unobserved and no risk-regime evidence is available"
    else:
        regime = "uncertainty"
        disposition = "limit"
        penalty = 1.0
        reason = "risk-regime evidence is incomplete or absent"

    boundary = AuthorityBoundary(
        authoritative_for=["epistemic_regime_classification"],
        may_not_use_for=_may_not_use_for(regime),
        source_authority="deterministic_producer",
        posture="governed",
        rule_version_refs=[evidence.rule_version_ref],
    )
    return EpistemicRegimeClaim(
        claim_ref=evidence.claim_ref,
        regime=regime,
        evidence_basis=evidence,
        firewall_disposition=disposition,
        asymmetry_penalty=penalty,
        decision_reason=reason,
        strategy_consequence=regime_design_strategy(regime, commitment),
        authority_boundary=boundary,
    )


def build_s11_regime_strategy_constraint(
    *,
    constraint_ref: str,
    source_ref: str,
    calibration_status: S11PredictiveCalibrationStatus,
    rule_version_ref: str,
) -> S11RegimeStrategyConstraint:
    """Build an S11 regime-strategy consumer constraint without rerunning S4."""

    status: Literal["pass", "limit", "block"]
    if calibration_status == "pass":
        status = "pass"
    elif calibration_status in {"absent", "stale", "poor"}:
        status = "limit"
    else:
        status = "block"
    return S11RegimeStrategyConstraint(
        constraint_ref=constraint_ref,
        source_ref=source_ref,
        calibration_status=calibration_status,
        status=status,
        reason=(
            "S11 predictive calibration constrains regime strategy consumption; "
            "S4 epistemic-regime classification is not rerun or reclassified."
        ),
        authority_boundary=AuthorityBoundary(
            authoritative_for=["s11_regime_strategy_constraint"],
            may_not_use_for=[
                "epistemic_regime_classification",
                "risk_regime_authority",
                "production_claim_authority",
                "production_recommendation",
            ],
            source_authority="deterministic_producer",
            posture="shadow",
            rule_version_refs=[rule_version_ref],
        ),
    )


def regime_claim_to_axis_position(
    claim: EpistemicRegimeClaim,
) -> tuple[AxisPositionDeclaration, AxisFirewallStatus]:
    """Project a regime claim onto the S0 axis declaration and firewall status."""

    position = AxisPositionDeclaration(
        cluster="KNOWLEDGE",
        axis="epistemic_regime",
        position=claim.regime,
        evidence_refs=[claim.evidence_basis.claim_ref],
        authority_purpose="design_strategy_selection",
        rule_version_ref=claim.evidence_basis.rule_version_ref,
    )
    firewall = AxisFirewallStatus(
        cell_ref="KNOWLEDGE.epistemic_regime",
        status="pass" if claim.firewall_disposition == "pass" else "limit",
        pattern_ids=["P16"],
        reason=claim.decision_reason,
        rule_version_ref=claim.evidence_basis.rule_version_ref,
    )
    return position, firewall


def regime_accuracy(
    *,
    predicted: list[str],
    gold: list[str],
) -> dict[str, float | int]:
    """Return accuracy plus asymmetric false-risk penalty counts."""

    if len(predicted) != len(gold):
        raise ValueError("predicted and gold regime lists must have the same length")
    denominator = len(gold) or 1
    correct = sum(
        1
        for predicted_regime, gold_regime in zip(predicted, gold, strict=True)
        if predicted_regime == gold_regime
    )
    false_risk = sum(
        1
        for predicted_regime, gold_regime in zip(predicted, gold, strict=True)
        if predicted_regime == "risk" and gold_regime in _NON_RISK_REGIMES
    )
    false_caution = sum(
        1
        for predicted_regime, gold_regime in zip(predicted, gold, strict=True)
        if predicted_regime in _NON_RISK_REGIMES and gold_regime == "risk"
    )
    accuracy = correct / denominator
    penalized_score = (
        accuracy
        - ((_FALSE_RISK_WEIGHT * false_risk) + (_FALSE_CAUTION_WEIGHT * false_caution))
        / denominator
    )
    return {
        "accuracy": accuracy,
        "false_risk_count": false_risk,
        "false_caution_count": false_caution,
        "penalized_score": penalized_score,
    }


def _may_not_use_for(regime: EpistemicRegime) -> list[str]:
    may_not_use = ["risk_regime_authority", "production_claim_authority"]
    if regime == "ignorance":
        return ["outcome_claim", *may_not_use]
    return may_not_use


__all__ = [
    "LAYER2_S4_EPISTEMIC_REGIME_SCHEMA_VERSION",
    "DesignStrategy",
    "EpistemicRegimeClaim",
    "P16OverconfidenceError",
    "P16PrecautionLaunderingError",
    "P23StakesFloorError",
    "RegimeEvidenceBasis",
    "S11RegimeStrategyConstraint",
    "build_s11_regime_strategy_constraint",
    "classify_regime",
    "regime_accuracy",
    "regime_claim_to_axis_position",
    "regime_design_strategy",
]
