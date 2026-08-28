"""Proof-aware, cost-aware scheduling for sequential simulation-based inference.

CP-BASIS (Certified Proof-aware Budgeted Active Simulation-based Inference)
chooses the next simulator design with the acquisition rule described in the
Phase 4 research plan:

    EIG(design) * proof_validity_multiplier
    ---------------------------------------------------------------
    estimated_cost + lambda_timeout * timeout_risk
                   + lambda_calibration * calibration_debt

The scheduler is deliberately lightweight. It owns the adaptive design decision
and hands the selected SBI family to the existing Foundry NPE/NLE/NRE methods
instead of depending on the optional neural SBI runtime itself.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics.simulation_proof_bridge import (
    SimulationCertificationStatus,
    SimulationProofBridge,
)
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.scientist.methods.search.voi_scheduler import ComputeEconomicsDecision

_SCHEMA_VERSION = "1.0"
_UNSPECIFIED_ASSUMPTIONS: dict[str, Literal["unspecified"]] = {
    "cost_model": "unspecified",
    "noise_model": "unspecified",
    "allowed_adaptive_designs": "unspecified",
}
_DEFAULT_DIAGNOSTICS: tuple[Literal["sbc", "expected_coverage", "tarp"], ...] = (
    "sbc",
    "expected_coverage",
    "tarp",
)
_STATUS_MULTIPLIERS = {
    "IDENTIFIED": 1.0,
    "BOUNDED": 0.65,
    "SCENARIO": 0.25,
    "BLOCKED": 0.0,
}


class SBIInferenceFamily(str, Enum):
    """Foundry-compatible neural SBI estimator families."""

    NPE = "npe"
    NLE = "nle"
    NRE = "nre"

    @property
    def foundry_namespace(self) -> str:
        return "bayesian.sbi"

    @property
    def foundry_method_name(self) -> str:
        return self.value

    @property
    def foundry_method_id(self) -> str:
        return f"{self.foundry_namespace}.{self.foundry_method_name}"


class ProofGateStatus(str, Enum):
    """Causal proof feasibility status used before spending simulator budget."""

    IDENTIFIED = "IDENTIFIED"
    BOUNDED = "BOUNDED"
    SCENARIO = "SCENARIO"
    BLOCKED = "BLOCKED"


class SBICalibrationPolicy(BaseModel):
    """Declare the posterior diagnostics expected before decision-grade claims."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    diagnostics: tuple[Literal["sbc", "expected_coverage", "tarp"], ...] = _DEFAULT_DIAGNOSTICS
    max_expected_coverage_error: float = Field(default=0.1, ge=0.0, le=1.0)
    min_rank_ks_pvalue: float = Field(default=0.05, ge=0.0, le=1.0)
    min_tarp_ks_pvalue: float = Field(default=0.05, ge=0.0, le=1.0)
    debt_increment_on_failure: float = Field(default=1.0, ge=0.0)
    debt_decay_on_pass: float = Field(default=0.25, ge=0.0, le=1.0)


class SBICalibrationSummary(BaseModel):
    """Small receipt-like summary for updating calibration debt in SBI design loops."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    diagnostics_run: tuple[str, ...] = ()
    calibration_debt: float = Field(default=0.0, ge=0.0)
    sbc_rank_ks_pvalue: float | None = Field(default=None, ge=0.0, le=1.0)
    expected_coverage_error: float | None = Field(default=None, ge=0.0)
    tarp_ks_pvalue: float | None = Field(default=None, ge=0.0, le=1.0)
    degradation_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_diagnostics(
        cls,
        *,
        policy: SBICalibrationPolicy | None = None,
        sbc_rank_ks_pvalue: float | None = None,
        expected_coverage_error: float | None = None,
        tarp_ks_pvalue: float | None = None,
        previous_debt: float = 0.0,
        metadata: Mapping[str, Any] | None = None,
    ) -> SBICalibrationSummary:
        """Evaluate SBC / expected-coverage / TARP diagnostics into calibration debt."""

        active_policy = policy or SBICalibrationPolicy()
        reasons: list[str] = []
        diagnostics_run: list[str] = []

        if "sbc" in active_policy.diagnostics:
            if sbc_rank_ks_pvalue is None:
                reasons.append("sbc_missing")
            else:
                diagnostics_run.append("sbc")
                if sbc_rank_ks_pvalue < active_policy.min_rank_ks_pvalue:
                    reasons.append("sbc_rank_ks_failed")
        if "expected_coverage" in active_policy.diagnostics:
            if expected_coverage_error is None:
                reasons.append("expected_coverage_missing")
            else:
                diagnostics_run.append("expected_coverage")
                if expected_coverage_error > active_policy.max_expected_coverage_error:
                    reasons.append("expected_coverage_failed")
        if "tarp" in active_policy.diagnostics:
            if tarp_ks_pvalue is None:
                reasons.append("tarp_missing")
            else:
                diagnostics_run.append("tarp")
                if tarp_ks_pvalue < active_policy.min_tarp_ks_pvalue:
                    reasons.append("tarp_ks_failed")

        accepted = not reasons
        debt = max(0.0, float(previous_debt))
        if accepted:
            debt *= 1.0 - active_policy.debt_decay_on_pass
        else:
            debt += active_policy.debt_increment_on_failure

        return cls(
            accepted=accepted,
            diagnostics_run=tuple(diagnostics_run),
            calibration_debt=debt,
            sbc_rank_ks_pvalue=sbc_rank_ks_pvalue,
            expected_coverage_error=expected_coverage_error,
            tarp_ks_pvalue=tarp_ks_pvalue,
            degradation_reasons=tuple(dict.fromkeys(reasons)),
            metadata=dict(metadata or {}),
        )


class ProofGateReceipt(BaseModel):
    """Proof/validity gate result for one candidate design."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ProofGateStatus = ProofGateStatus.SCENARIO
    validity_multiplier: float | None = Field(default=None, ge=0.0, le=1.0)
    reasons: tuple[str, ...] = ()
    proof_bundle_ref: ArtifactRefModel | None = None
    calibration_receipt_ref: ArtifactRefModel | None = None
    interface_mapping_ref: ArtifactRefModel | None = None
    causal_readiness_bundle_ref: ArtifactRefModel | None = None
    causal_validity_bundle_ref: ArtifactRefModel | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def effective_validity_multiplier(self) -> float:
        if self.validity_multiplier is not None:
            return float(self.validity_multiplier)
        return _STATUS_MULTIPLIERS[self.status.value]

    @property
    def blocked(self) -> bool:
        return self.status is ProofGateStatus.BLOCKED or self.effective_validity_multiplier <= 0.0


class SBIDesignCandidate(BaseModel):
    """Candidate simulator design considered by the CP-BASIS acquisition rule."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1)
    design: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    fidelity: str | int | float | None = None
    expected_information_gain: float = Field(ge=0.0)
    estimated_cost_usd: float = Field(ge=0.0)
    timeout_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    calibration_debt: float = Field(default=0.0, ge=0.0)
    proof_gate: ProofGateReceipt = Field(default_factory=ProofGateReceipt)
    posterior_family: SBIInferenceFamily = SBIInferenceFamily.NPE
    predicted_summary: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CPBASISConfig(BaseModel):
    """Configuration for proof-aware budgeted active SBI scheduling."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(_SCHEMA_VERSION, pattern=r"^\d+\.\d+$")
    lambda_timeout: float = Field(default=1.0, ge=0.0)
    lambda_calibration: float = Field(default=1.0, ge=0.0)
    min_denominator: float = Field(default=1e-9, gt=0.0)
    min_advance_score: float = Field(default=0.0, ge=0.0)
    retry_timeout_risk_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    default_posterior_family: SBIInferenceFamily = SBIInferenceFamily.NPE
    allowed_posterior_families: tuple[SBIInferenceFamily, ...] = (
        SBIInferenceFamily.NPE,
        SBIInferenceFamily.NLE,
        SBIInferenceFamily.NRE,
    )
    calibration_policy: SBICalibrationPolicy = Field(default_factory=SBICalibrationPolicy)
    unspecified_assumptions: dict[str, Literal["unspecified"]] = Field(
        default_factory=lambda: dict(_UNSPECIFIED_ASSUMPTIONS)
    )

    @model_validator(mode="after")
    def _default_family_must_be_allowed(self) -> CPBASISConfig:
        if self.default_posterior_family not in self.allowed_posterior_families:
            raise ValueError("default_posterior_family must be listed in allowed_posterior_families")
        return self


class CPBASISScore(BaseModel):
    """Explain one CP-BASIS acquisition score and routing action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(_SCHEMA_VERSION, pattern=r"^\d+\.\d+$")
    candidate_id: str = Field(min_length=1)
    acquisition_score: float = Field(ge=0.0)
    numerator: float = Field(ge=0.0)
    denominator: float = Field(gt=0.0)
    expected_information_gain: float = Field(ge=0.0)
    validity_multiplier: float = Field(ge=0.0, le=1.0)
    estimated_cost_usd: float = Field(ge=0.0)
    timeout_risk: float = Field(ge=0.0, le=1.0)
    calibration_debt: float = Field(ge=0.0)
    posterior_family: SBIInferenceFamily
    foundry_method_id: str = Field(min_length=1)
    proof_status: ProofGateStatus
    recommended_action: Literal["advance", "defer", "reject", "retry_cheaper"]
    reason: str = Field(min_length=1)
    proof_gate: ProofGateReceipt
    economics: ComputeEconomicsDecision
    metadata: dict[str, Any] = Field(default_factory=dict)


class CPBASISPlan(BaseModel):
    """Ranked adaptive-design plan for the next SBI simulator call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(_SCHEMA_VERSION, pattern=r"^\d+\.\d+$")
    selected_candidate_id: str | None = None
    selected_foundry_method_id: str | None = None
    ranked_scores: tuple[CPBASISScore, ...] = ()
    blocked_candidate_ids: tuple[str, ...] = ()
    deferred_candidate_ids: tuple[str, ...] = ()
    total_candidate_count: int = Field(ge=0)
    calibration_policy: SBICalibrationPolicy
    unspecified_assumptions: dict[str, Literal["unspecified"]]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def selected_score(self) -> CPBASISScore | None:
        if self.selected_candidate_id is None:
            return None
        return next(
            (
                score
                for score in self.ranked_scores
                if score.candidate_id == self.selected_candidate_id
            ),
            None,
        )


class ProofAwareSBIScheduler:
    """Select simulator designs with CP-BASIS proof and cost gates."""

    def __init__(self, config: CPBASISConfig | None = None) -> None:
        self.config = config or CPBASISConfig()

    def score_candidate(
        self,
        candidate: SBIDesignCandidate,
        *,
        remaining_budget_usd: float | None = None,
    ) -> CPBASISScore:
        """Score one candidate and return the associated routing decision."""

        family = (
            candidate.posterior_family
            if candidate.posterior_family in self.config.allowed_posterior_families
            else self.config.default_posterior_family
        )
        validity_multiplier = candidate.proof_gate.effective_validity_multiplier
        numerator = candidate.expected_information_gain * validity_multiplier
        denominator = max(
            candidate.estimated_cost_usd
            + (self.config.lambda_timeout * candidate.timeout_risk)
            + (self.config.lambda_calibration * candidate.calibration_debt),
            self.config.min_denominator,
        )
        acquisition_score = 0.0 if candidate.proof_gate.blocked else numerator / denominator
        action, reason = self._recommended_action(
            candidate=candidate,
            score=acquisition_score,
            remaining_budget_usd=remaining_budget_usd,
        )
        economics = ComputeEconomicsDecision(
            candidate_id=candidate.candidate_id,
            recommended_action=action,
            expected_improvement_per_usd=(
                candidate.expected_information_gain / max(candidate.estimated_cost_usd, 1e-9)
            ),
            expected_falsification_value=candidate.expected_information_gain,
            expected_governance_value=validity_multiplier,
            timeout_risk=candidate.timeout_risk,
            replay_cost_usd=candidate.estimated_cost_usd,
            calibration_debt=candidate.calibration_debt,
            current_pareto_position=candidate.proof_gate.status.value.lower(),
            predicted_metric_vector=dict(candidate.predicted_summary),
            promotion_likelihood=validity_multiplier,
            estimated_cost_usd=candidate.estimated_cost_usd,
            predicted_disagreement=float(candidate.metadata.get("predicted_disagreement", 0.0)),
            exploration_bonus=float(candidate.metadata.get("exploration_bonus", 0.0)),
            reserved_calibration_budget_usd=float(
                candidate.metadata.get("reserved_calibration_budget_usd", 0.0)
            ),
            scheduler_mode="cp_basis",
        )
        return CPBASISScore(
            candidate_id=candidate.candidate_id,
            acquisition_score=acquisition_score,
            numerator=numerator,
            denominator=denominator,
            expected_information_gain=candidate.expected_information_gain,
            validity_multiplier=validity_multiplier,
            estimated_cost_usd=candidate.estimated_cost_usd,
            timeout_risk=candidate.timeout_risk,
            calibration_debt=candidate.calibration_debt,
            posterior_family=family,
            foundry_method_id=family.foundry_method_id,
            proof_status=candidate.proof_gate.status,
            recommended_action=action,
            reason=reason,
            proof_gate=candidate.proof_gate,
            economics=economics,
            metadata={
                **dict(candidate.metadata),
                "design": dict(candidate.design),
                "parameters": dict(candidate.parameters),
                "fidelity": candidate.fidelity,
            },
        )

    def rank(
        self,
        candidates: Sequence[SBIDesignCandidate],
        *,
        remaining_budget_usd: float | None = None,
    ) -> list[CPBASISScore]:
        """Return all candidates ranked by proof-aware information per cost."""

        scores = [
            self.score_candidate(candidate, remaining_budget_usd=remaining_budget_usd)
            for candidate in candidates
        ]
        action_rank = {"advance": 0, "retry_cheaper": 1, "defer": 2, "reject": 3}
        return sorted(
            scores,
            key=lambda score: (action_rank[score.recommended_action], -score.acquisition_score),
        )

    def plan(
        self,
        candidates: Sequence[SBIDesignCandidate],
        *,
        remaining_budget_usd: float | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> CPBASISPlan:
        """Build the next-step adaptive design plan."""

        ranked_scores = tuple(self.rank(candidates, remaining_budget_usd=remaining_budget_usd))
        selected = next(
            (score for score in ranked_scores if score.recommended_action == "advance"),
            None,
        )
        return CPBASISPlan(
            selected_candidate_id=selected.candidate_id if selected is not None else None,
            selected_foundry_method_id=(
                selected.foundry_method_id if selected is not None else None
            ),
            ranked_scores=ranked_scores,
            blocked_candidate_ids=tuple(
                score.candidate_id
                for score in ranked_scores
                if score.recommended_action == "reject"
                and score.reason == "proof_gate_blocked"
            ),
            deferred_candidate_ids=tuple(
                score.candidate_id
                for score in ranked_scores
                if score.recommended_action in {"defer", "retry_cheaper"}
            ),
            total_candidate_count=len(candidates),
            calibration_policy=self.config.calibration_policy,
            unspecified_assumptions=dict(self.config.unspecified_assumptions),
            metadata=dict(metadata or {}),
        )

    def select_next(
        self,
        candidates: Sequence[SBIDesignCandidate],
        *,
        remaining_budget_usd: float | None = None,
    ) -> CPBASISScore | None:
        """Return the selected score for the next simulator call, if any."""

        return self.plan(candidates, remaining_budget_usd=remaining_budget_usd).selected_score

    def _recommended_action(
        self,
        *,
        candidate: SBIDesignCandidate,
        score: float,
        remaining_budget_usd: float | None,
    ) -> tuple[Literal["advance", "defer", "reject", "retry_cheaper"], str]:
        if candidate.proof_gate.blocked:
            return "reject", "proof_gate_blocked"
        if remaining_budget_usd is not None and candidate.estimated_cost_usd > remaining_budget_usd:
            return "defer", "budget_insufficient"
        if candidate.timeout_risk >= self.config.retry_timeout_risk_threshold:
            return "retry_cheaper", "timeout_risk_high"
        if score <= self.config.min_advance_score:
            return "defer", "score_below_threshold"
        return "advance", "best_expected_information_per_cost"


def build_cp_basis_design_plan(
    candidates: Sequence[SBIDesignCandidate],
    *,
    config: CPBASISConfig | None = None,
    remaining_budget_usd: float | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> CPBASISPlan:
    """Convenience wrapper for one-shot CP-BASIS planning."""

    return ProofAwareSBIScheduler(config).plan(
        candidates,
        remaining_budget_usd=remaining_budget_usd,
        metadata=metadata,
    )


def proof_gate_from_bridge(
    bridge: SimulationProofBridge | Mapping[str, Any],
    *,
    validity_multiplier: float | None = None,
    extra_reasons: Sequence[str] = (),
    metadata: Mapping[str, Any] | None = None,
) -> ProofGateReceipt:
    """Convert a simulation proof bridge artifact into a scheduler proof gate."""

    payload = (
        bridge.model_dump(mode="python", warnings=False)
        if isinstance(bridge, SimulationProofBridge)
        else bridge
    )
    model = SimulationProofBridge.model_validate(payload)
    status = _proof_gate_status(model.certification_status)
    reasons = tuple(dict.fromkeys((*model.degradation_reasons, *extra_reasons)))
    return ProofGateReceipt(
        status=status,
        validity_multiplier=validity_multiplier,
        reasons=reasons,
        proof_bundle_ref=ArtifactRefModel.model_validate(model.proof_bundle_ref.model_dump(mode="json")),
        calibration_receipt_ref=ArtifactRefModel.model_validate(
            model.calibration_receipt_ref.model_dump(mode="json")
        ),
        interface_mapping_ref=(
            ArtifactRefModel.model_validate(model.interface_mapping_ref.model_dump(mode="json"))
            if model.interface_mapping_ref is not None
            else None
        ),
        causal_readiness_bundle_ref=model.causal_readiness_bundle_ref,
        causal_validity_bundle_ref=model.causal_validity_bundle_ref,
        metadata={
            **dict(metadata or {}),
            "bridge_schema_version": model.schema_version,
            "proof_status": model.proof_status,
            "calibration_status": model.calibration_status,
            "composability_status": model.composability_status,
        },
    )


def _proof_gate_status(status: SimulationCertificationStatus | str) -> ProofGateStatus:
    value = status.value if isinstance(status, SimulationCertificationStatus) else str(status)
    try:
        return ProofGateStatus(value)
    except ValueError:
        return ProofGateStatus.SCENARIO


__all__ = [
    "CPBASISConfig",
    "CPBASISPlan",
    "CPBASISScore",
    "ProofAwareSBIScheduler",
    "ProofGateReceipt",
    "ProofGateStatus",
    "SBICalibrationPolicy",
    "SBICalibrationSummary",
    "SBIDesignCandidate",
    "SBIInferenceFamily",
    "build_cp_basis_design_plan",
    "proof_gate_from_bridge",
]
