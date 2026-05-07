"""Fail-closed automatic latent bridge synthesis (Stage 2.4).

This module is the **only** path through which a ``LATENT_BRIDGE`` alignment
type may be proposed automatically.  It implements the synthesis algorithm
described in the research result for Stage 2.4:

    PermitAutoBridge(L) = T(L) ∧ F(L) ∧ I(L) ∧ S(L) ∧ U(L) ∧ H(L)

where T is testability, F is falsification-pack completeness, I is
improvement-over-no-bridge, S is stability, U is uniqueness against equivalent
competitors, H is hard-compatibility with metadata and measurement contracts.

The engine is deterministic: callers bundle the observable evidence they have
(indicators, environments, proxy families, held-out metrics, bootstrap
stability, alternative-model challenge results) in a :class:`LatentBridgeEvidence`
input, and the engine either returns a ``PROPOSED`` hypothesis with an attached
falsification pack or blocks the synthesis with a machine-readable list of
reasons.  Semantically loaded labels are **never** coined automatically - the
default ``latent_label`` is ``None`` and the ``opaque_label_required`` guard in
``metadata`` is on by default.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.references import LatentBridgeHypothesisRef

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.ir.analytics.causal_discovery import (
        LatentPromotionEvidence,
        LatentPromotionVerdict,
    )
else:
    from polisyos.ir.analytics.causal_discovery import (
        LatentPromotionEvidence,
        LatentPromotionVerdict,
    )

_LATENT_BRIDGE_HYPOTHESIS_SCHEMA_NAME = "ir.latent_bridge_hypothesis"
_LATENT_BRIDGE_HYPOTHESIS_SCHEMA_VERSION = "1.0"


class LatentBridgeStatus(str, Enum):
    """Terminal state of a latent-bridge hypothesis."""

    PROPOSED = "proposed"
    BLOCKED = "blocked"
    BLOCKED_AMBIGUOUS = "blocked_ambiguous"
    FALSIFIED = "falsified"
    HUMAN_VERIFIED = "human_verified"


class LatentBridgeSynthesisMode(str, Enum):
    """Evidence mode that carried the hypothesis (or attempted to)."""

    MEASUREMENT_MODEL = "measurement_model"
    MULTI_ENVIRONMENT = "multi_environment"
    PROXY = "proxy"
    HYBRID = "hybrid"
    NONE = "none"


class LatentBridgeInvarianceLevel(str, Enum):
    """Psychometric invariance hierarchy reached for multi-environment evidence."""

    NONE = "none"
    CONFIGURAL = "configural"
    METRIC = "metric"
    SCALAR = "scalar"
    STRICT = "strict"


_INVARIANCE_RANK: dict[LatentBridgeInvarianceLevel, int] = {
    LatentBridgeInvarianceLevel.NONE: 0,
    LatentBridgeInvarianceLevel.CONFIGURAL: 1,
    LatentBridgeInvarianceLevel.METRIC: 2,
    LatentBridgeInvarianceLevel.SCALAR: 3,
    LatentBridgeInvarianceLevel.STRICT: 4,
}


class LatentBridgeFalsificationTestFamily(str, Enum):
    """Falsification-test family attached to the hypothesis."""

    CTA = "cta"
    LOCAL_DEPENDENCE = "local_dependence"
    INVARIANCE = "invariance"
    DIF = "dif"
    PROXY_RANK = "proxy_rank"
    ALTERNATIVE_MODEL = "alternative_model"
    STABILITY = "stability"


class LatentBridgeFalsificationTestStatus(str, Enum):
    """Outcome of one falsification test."""

    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


class LatentBridgeBlockReason(str, Enum):
    """Machine-readable reasons why synthesis was blocked."""

    AUTO_SYNTHESIS_DISABLED = "auto_synthesis_disabled"
    HARD_METADATA_MISMATCH = "hard_metadata_mismatch"
    NO_OVERIDENTIFYING_IMPLICATIONS = "no_overidentifying_implications"
    INSUFFICIENT_INDICATORS = "insufficient_indicators"
    INSUFFICIENT_INDICATORS_PER_SIDE = "insufficient_indicators_per_side"
    DIRECTION_AMBIGUITY_UNRESOLVED = "direction_ambiguity_unresolved"
    ENVIRONMENT_ONLY_EVIDENCE = "environment_only_evidence"
    INSUFFICIENT_ENVIRONMENTS = "insufficient_environments"
    MISSING_METRIC_INVARIANCE = "missing_metric_invariance"
    MISSING_SCALAR_INVARIANCE = "missing_scalar_invariance"
    INSUFFICIENT_ANCHOR_ITEMS = "insufficient_anchor_items"
    ANCHOR_SET_UNSTABLE = "anchor_set_unstable"
    DIF_IN_ANCHOR_SET = "dif_in_anchor_set"
    PROXY_MODE_DISABLED = "proxy_mode_disabled"
    INSUFFICIENT_PROXY_FAMILIES = "insufficient_proxy_families"
    PROXY_RANK_CONDITION_FAILED = "proxy_rank_condition_failed"
    BRIDGE_OPERATOR_NOT_BUILT = "bridge_operator_not_built"
    HELDOUT_IMPROVEMENT_NONPOSITIVE = "heldout_improvement_nonpositive"
    HELDOUT_METRICS_MISSING = "heldout_metrics_missing"
    BOOTSTRAP_INSTABILITY = "bootstrap_instability"
    ALTERNATIVE_MODEL_NOT_BEATEN = "alternative_model_not_beaten"
    POST_HOC_MODIFICATIONS = "post_hoc_modifications"
    AMBIGUOUS_COMPETING_LATENTS = "ambiguous_competing_latents"
    NO_ADMISSIBLE_CANDIDATE = "no_admissible_candidate"
    FALSIFICATION_TEST_FAILED = "falsification_test_failed"
    HEYWOOD_IMPROPER_SOLUTION = "heywood_improper_solution"
    REFLECTIVE_DIRECTION_REJECTED = "reflective_direction_rejected"


class LatentBridgeFalsificationTest(BaseModel):
    """Single entry in the falsification pack attached to the hypothesis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    test_family: LatentBridgeFalsificationTestFamily
    status: LatentBridgeFalsificationTestStatus
    statistic: float | None = None
    p_value: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("p_value")
    @classmethod
    def _validate_p_value(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if not 0.0 <= value <= 1.0:
            raise ValueError("p_value must be in [0, 1]")
        return value


class LatentBridgeHeldoutMetrics(BaseModel):
    """Held-out improvement of the bridge model versus the best no-bridge competitor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    delta_cv: float
    lower_ci: float
    upper_ci: float | None = None
    scoring_rule: str = Field(default="loglik", min_length=1)

    @model_validator(mode="after")
    def _validate_ci(self) -> LatentBridgeHeldoutMetrics:
        if self.lower_ci > self.delta_cv:
            raise ValueError("lower_ci must not exceed delta_cv")
        if self.upper_ci is not None and self.upper_ci < self.delta_cv:
            raise ValueError("upper_ci must not be below delta_cv")
        return self


class LatentBridgeProxyFamily(BaseModel):
    """One proxy family on one side of the candidate bridge."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    family_id: str = Field(min_length=1)
    side: str = Field(min_length=1)
    proxy_refs: list[str] = Field(default_factory=list)
    rank_condition_satisfied: bool = False
    bridge_operator_built: bool = False


class LatentBridgeCandidate(BaseModel):
    """Single admissible candidate scored by the engine."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1)
    synthesis_mode: LatentBridgeSynthesisMode
    heldout_metrics: LatentBridgeHeldoutMetrics | None = None
    stability_frequency: float = Field(default=0.0, ge=0.0, le=1.0)
    alternative_model_beaten: bool = False
    post_hoc_modifications: bool = False
    heywood_improper_solution: bool = False
    reflective_direction_supported: bool = True
    falsification_tests: list[LatentBridgeFalsificationTest] = Field(default_factory=list)


class LatentBridgeEvidence(BaseModel):
    """Observable evidence callers supply for one interface pair.

    The engine does not itself fit measurement models: it evaluates whether the
    evidence declared here is strong enough to **permit** an automatic latent
    bridge proposal.  Every field has a conservative default that makes
    synthesis fail-closed.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    measurement_side_a_refs: list[str] = Field(default_factory=list)
    measurement_side_b_refs: list[str] = Field(default_factory=list)
    tetrad_tests_available: bool = False
    local_dependence_controlled: bool = True
    reflective_direction_supported: bool = True

    environment_refs: list[str] = Field(default_factory=list)
    invariance_level: LatentBridgeInvarianceLevel = LatentBridgeInvarianceLevel.NONE
    anchor_items: list[str] = Field(default_factory=list)
    dif_free_anchor_set: bool = False
    leave_one_anchor_out_stable: bool = False

    proxy_families: list[LatentBridgeProxyFamily] = Field(default_factory=list)

    candidates: list[LatentBridgeCandidate] = Field(default_factory=list)

    bridge_model_ref: str | None = None
    baseline_model_refs: list[str] = Field(default_factory=list)

    hard_metadata_mismatch: bool = False
    direction_ambiguity_resolved: bool = True
    post_hoc_modifications: bool = False


class LatentBridgeSynthesisPolicy(BaseModel):
    """Policy gates controlling when an automatic latent bridge may be proposed.

    Defaults are intentionally conservative: synthesis is **disabled** unless
    the caller explicitly opts in, and every admit rule runs as a hard gate.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    enable_auto_latent_bridge: bool = False

    require_overidentified_model: bool = True
    min_indicators_per_side: int = Field(default=2, ge=1)
    min_total_indicators: int = Field(default=4, ge=2)

    allow_environment_only_mode: bool = False
    min_environments: int = Field(default=2, ge=1)
    require_metric_invariance: bool = True
    require_scalar_invariance: bool = False
    min_anchor_items: int = Field(default=2, ge=1)
    require_leave_one_anchor_out_stable: bool = True
    require_dif_free_anchor_set: bool = True

    allow_proxy_only_mode: bool = True
    require_two_proxy_families: bool = True
    require_proxy_rank_condition: bool = True
    require_proxy_bridge_operator: bool = True

    min_stability_frequency: float = Field(default=0.8, ge=0.0, le=1.0)
    heldout_lower_ci_strictly_positive: bool = True
    require_alternative_model_challenge: bool = True
    block_on_post_hoc_modifications: bool = True
    block_on_heywood_improper_solution: bool = True
    require_reflective_direction_support: bool = True
    block_on_ambiguity: bool = True

    opaque_label_required: bool = True


class LatentBridgeHypothesis(BaseModel):
    """Persisted typed artifact for an automatic latent-bridge hypothesis.

    Carries the provenance of the synthesis decision (mode, supporting
    evidence, held-out metrics, falsification pack) together with a
    machine-readable list of block conditions that tripped when synthesis was
    rejected.  Downstream consumers must treat ``status != PROPOSED`` as an
    explicit refusal, not a soft hint.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(
        default=_LATENT_BRIDGE_HYPOTHESIS_SCHEMA_VERSION, pattern=r"^\d+\.\d+$"
    )
    bridge_id: str = Field(min_length=1)
    pair_key: str = Field(min_length=1)
    status: LatentBridgeStatus
    synthesis_mode: LatentBridgeSynthesisMode = LatentBridgeSynthesisMode.NONE
    latent_label: str | None = None
    measurement_side_a_refs: list[str] = Field(default_factory=list)
    measurement_side_b_refs: list[str] = Field(default_factory=list)
    environment_refs: list[str] = Field(default_factory=list)
    proxy_refs: list[str] = Field(default_factory=list)
    anchor_items: list[str] = Field(default_factory=list)
    baseline_model_refs: list[str] = Field(default_factory=list)
    bridge_model_ref: str | None = None
    heldout_metrics: LatentBridgeHeldoutMetrics | None = None
    falsification_tests: list[LatentBridgeFalsificationTest] = Field(default_factory=list)
    block_conditions_checked: list[LatentBridgeBlockReason] = Field(default_factory=list)
    negative_certificate_ref: str | None = None
    promotion_evidence: LatentPromotionEvidence | None = None
    promotion_verdict: LatentPromotionVerdict | None = None
    readiness_cap: Literal["proof_only", "bounds_ready", "estimation_ready"] = "proof_only"
    promotion_allowed: bool = False
    not_for_decision_support: bool = True
    human_gate_required: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _enforce_status_invariants(self) -> LatentBridgeHypothesis:
        if self.status is LatentBridgeStatus.PROPOSED:
            if self.block_conditions_checked:
                raise ValueError(
                    "PROPOSED latent bridge must not carry block_conditions_checked entries"
                )
            if self.heldout_metrics is None:
                raise ValueError("PROPOSED latent bridge must include heldout_metrics")
            if not self.falsification_tests:
                raise ValueError("PROPOSED latent bridge must attach a falsification pack")
            if any(
                test.status is LatentBridgeFalsificationTestStatus.FAIL
                for test in self.falsification_tests
            ):
                raise ValueError(
                    "PROPOSED latent bridge must not carry failing falsification tests"
                )
        if self.status in {LatentBridgeStatus.BLOCKED, LatentBridgeStatus.BLOCKED_AMBIGUOUS}:
            if not self.block_conditions_checked:
                raise ValueError("BLOCKED latent bridge must list at least one block condition")
        if (
            self.latent_label is not None
            and self.metadata.get("opaque_label_required", True)
            and self.metadata.get("semantic_interpretation_confidence", "none") == "none"
        ):
            raise ValueError(
                "latent_label is only permitted when opaque_label_required is off "
                "or semantic_interpretation_confidence > 'none'"
            )
        if self.promotion_verdict is not None:
            if self.promotion_evidence is None:
                raise ValueError(
                    "promotion_verdict requires promotion_evidence on LatentBridgeHypothesis"
                )
            if self.readiness_cap != self.promotion_verdict.derived_readiness_cap:
                raise ValueError("readiness_cap must match promotion_verdict.derived_readiness_cap")
            if self.promotion_allowed != self.promotion_verdict.promotion_allowed:
                raise ValueError("promotion_allowed must match promotion_verdict.promotion_allowed")
            if self.not_for_decision_support != self.promotion_verdict.not_for_decision_support:
                raise ValueError(
                    "not_for_decision_support must match promotion_verdict.not_for_decision_support"
                )
            if self.human_gate_required != self.promotion_verdict.human_gate_required:
                raise ValueError(
                    "human_gate_required must match promotion_verdict.human_gate_required"
                )
        if self.readiness_cap == "proof_only" and self.promotion_allowed:
            raise ValueError("proof_only latent bridge cannot set promotion_allowed=True")
        return self


def build_pair_key(
    fragment_a_id: str,
    variable_a: str,
    fragment_b_id: str,
    variable_b: str,
) -> str:
    """Return a deterministic ``fragment:variable|fragment:variable`` pair key."""
    left = f"{str(fragment_a_id).strip()}:{str(variable_a).strip()}"
    right = f"{str(fragment_b_id).strip()}:{str(variable_b).strip()}"
    ordered = sorted((left, right))
    return "|".join(ordered)


def _derive_bridge_id(pair_key: str, synthesis_mode: LatentBridgeSynthesisMode) -> str:
    digest = hashlib.sha256(f"{pair_key}|{synthesis_mode.value}".encode()).hexdigest()
    return f"latent::bridge::{digest[:16]}"


def _available_modes(
    evidence: LatentBridgeEvidence,
    policy: LatentBridgeSynthesisPolicy,
) -> set[LatentBridgeSynthesisMode]:
    available: set[LatentBridgeSynthesisMode] = set()
    total_indicators = len(evidence.measurement_side_a_refs) + len(evidence.measurement_side_b_refs)
    if (
        len(evidence.measurement_side_a_refs) >= policy.min_indicators_per_side
        and len(evidence.measurement_side_b_refs) >= policy.min_indicators_per_side
        and total_indicators >= policy.min_total_indicators
    ):
        available.add(LatentBridgeSynthesisMode.MEASUREMENT_MODEL)
    if policy.allow_proxy_only_mode and len(evidence.proxy_families) >= 2:
        available.add(LatentBridgeSynthesisMode.PROXY)
    if len(evidence.environment_refs) >= policy.min_environments:
        available.add(LatentBridgeSynthesisMode.MULTI_ENVIRONMENT)
    if (
        LatentBridgeSynthesisMode.MEASUREMENT_MODEL in available
        and LatentBridgeSynthesisMode.MULTI_ENVIRONMENT in available
    ):
        available.add(LatentBridgeSynthesisMode.HYBRID)
    return available


def _check_hard_compatibility(
    evidence: LatentBridgeEvidence,
) -> list[LatentBridgeBlockReason]:
    reasons: list[LatentBridgeBlockReason] = []
    if evidence.hard_metadata_mismatch:
        reasons.append(LatentBridgeBlockReason.HARD_METADATA_MISMATCH)
    if not evidence.direction_ambiguity_resolved:
        reasons.append(LatentBridgeBlockReason.DIRECTION_AMBIGUITY_UNRESOLVED)
    return reasons


def _check_measurement_mode(
    evidence: LatentBridgeEvidence,
    policy: LatentBridgeSynthesisPolicy,
) -> list[LatentBridgeBlockReason]:
    reasons: list[LatentBridgeBlockReason] = []
    total_indicators = len(evidence.measurement_side_a_refs) + len(evidence.measurement_side_b_refs)
    if (
        len(evidence.measurement_side_a_refs) < policy.min_indicators_per_side
        or len(evidence.measurement_side_b_refs) < policy.min_indicators_per_side
    ):
        reasons.append(LatentBridgeBlockReason.INSUFFICIENT_INDICATORS_PER_SIDE)
    if total_indicators < policy.min_total_indicators:
        reasons.append(LatentBridgeBlockReason.INSUFFICIENT_INDICATORS)
    if policy.require_overidentified_model and not evidence.tetrad_tests_available:
        reasons.append(LatentBridgeBlockReason.NO_OVERIDENTIFYING_IMPLICATIONS)
    if policy.require_reflective_direction_support and not evidence.reflective_direction_supported:
        reasons.append(LatentBridgeBlockReason.REFLECTIVE_DIRECTION_REJECTED)
    return reasons


def _check_environment_mode(
    evidence: LatentBridgeEvidence,
    policy: LatentBridgeSynthesisPolicy,
) -> list[LatentBridgeBlockReason]:
    reasons: list[LatentBridgeBlockReason] = []
    if len(evidence.environment_refs) < policy.min_environments:
        reasons.append(LatentBridgeBlockReason.INSUFFICIENT_ENVIRONMENTS)
    if (
        policy.require_metric_invariance
        and _INVARIANCE_RANK[evidence.invariance_level]
        < _INVARIANCE_RANK[LatentBridgeInvarianceLevel.METRIC]
    ):
        reasons.append(LatentBridgeBlockReason.MISSING_METRIC_INVARIANCE)
    if (
        policy.require_scalar_invariance
        and _INVARIANCE_RANK[evidence.invariance_level]
        < _INVARIANCE_RANK[LatentBridgeInvarianceLevel.SCALAR]
    ):
        reasons.append(LatentBridgeBlockReason.MISSING_SCALAR_INVARIANCE)
    if len(evidence.anchor_items) < policy.min_anchor_items:
        reasons.append(LatentBridgeBlockReason.INSUFFICIENT_ANCHOR_ITEMS)
    if policy.require_dif_free_anchor_set and not evidence.dif_free_anchor_set:
        reasons.append(LatentBridgeBlockReason.DIF_IN_ANCHOR_SET)
    if policy.require_leave_one_anchor_out_stable and not evidence.leave_one_anchor_out_stable:
        reasons.append(LatentBridgeBlockReason.ANCHOR_SET_UNSTABLE)
    return reasons


def _check_proxy_mode(
    evidence: LatentBridgeEvidence,
    policy: LatentBridgeSynthesisPolicy,
) -> list[LatentBridgeBlockReason]:
    reasons: list[LatentBridgeBlockReason] = []
    if not policy.allow_proxy_only_mode:
        reasons.append(LatentBridgeBlockReason.PROXY_MODE_DISABLED)
    if policy.require_two_proxy_families and len(evidence.proxy_families) < 2:
        reasons.append(LatentBridgeBlockReason.INSUFFICIENT_PROXY_FAMILIES)
    if policy.require_proxy_rank_condition and not all(
        family.rank_condition_satisfied for family in evidence.proxy_families
    ):
        reasons.append(LatentBridgeBlockReason.PROXY_RANK_CONDITION_FAILED)
    if policy.require_proxy_bridge_operator and not all(
        family.bridge_operator_built for family in evidence.proxy_families
    ):
        reasons.append(LatentBridgeBlockReason.BRIDGE_OPERATOR_NOT_BUILT)
    return reasons


def _check_candidate(
    candidate: LatentBridgeCandidate,
    policy: LatentBridgeSynthesisPolicy,
) -> list[LatentBridgeBlockReason]:
    reasons: list[LatentBridgeBlockReason] = []
    if candidate.heldout_metrics is None:
        reasons.append(LatentBridgeBlockReason.HELDOUT_METRICS_MISSING)
    else:
        lower_ci = candidate.heldout_metrics.lower_ci
        if policy.heldout_lower_ci_strictly_positive and lower_ci <= 0.0:
            reasons.append(LatentBridgeBlockReason.HELDOUT_IMPROVEMENT_NONPOSITIVE)
    if candidate.stability_frequency < policy.min_stability_frequency:
        reasons.append(LatentBridgeBlockReason.BOOTSTRAP_INSTABILITY)
    if policy.require_alternative_model_challenge and not candidate.alternative_model_beaten:
        reasons.append(LatentBridgeBlockReason.ALTERNATIVE_MODEL_NOT_BEATEN)
    if policy.block_on_post_hoc_modifications and candidate.post_hoc_modifications:
        reasons.append(LatentBridgeBlockReason.POST_HOC_MODIFICATIONS)
    if policy.block_on_heywood_improper_solution and candidate.heywood_improper_solution:
        reasons.append(LatentBridgeBlockReason.HEYWOOD_IMPROPER_SOLUTION)
    if policy.require_reflective_direction_support and not candidate.reflective_direction_supported:
        reasons.append(LatentBridgeBlockReason.REFLECTIVE_DIRECTION_REJECTED)
    if any(
        test.status is LatentBridgeFalsificationTestStatus.FAIL
        for test in candidate.falsification_tests
    ):
        reasons.append(LatentBridgeBlockReason.FALSIFICATION_TEST_FAILED)
    return reasons


def _dedupe_reasons(
    values: Sequence[LatentBridgeBlockReason],
) -> list[LatentBridgeBlockReason]:
    seen: set[LatentBridgeBlockReason] = set()
    output: list[LatentBridgeBlockReason] = []
    for reason in values:
        if reason in seen:
            continue
        seen.add(reason)
        output.append(reason)
    return output


def _dedupe_strings(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _base_metadata(policy: LatentBridgeSynthesisPolicy) -> dict[str, Any]:
    return {
        "semantic_interpretation_confidence": "none",
        "opaque_label_required": policy.opaque_label_required,
    }


def synthesize_latent_bridge(
    *,
    pair_key: str,
    evidence: LatentBridgeEvidence,
    policy: LatentBridgeSynthesisPolicy | None = None,
) -> LatentBridgeHypothesis:
    """Run the fail-closed latent-bridge synthesis algorithm for one pair.

    Returns a :class:`LatentBridgeHypothesis` with status ``PROPOSED`` only if
    every mandatory condition in :class:`LatentBridgeSynthesisPolicy` passes
    against the caller-supplied evidence; otherwise the hypothesis carries
    ``BLOCKED`` or ``BLOCKED_AMBIGUOUS`` together with the machine-readable
    reasons that tripped.
    """
    resolved_policy = policy or LatentBridgeSynthesisPolicy()
    metadata = _base_metadata(resolved_policy)
    metadata["policy_snapshot"] = resolved_policy.model_dump(mode="json")
    candidate_ids = [candidate.candidate_id for candidate in evidence.candidates]
    if candidate_ids:
        metadata["candidate_ids"] = list(candidate_ids)

    if not resolved_policy.enable_auto_latent_bridge:
        return _blocked_hypothesis(
            pair_key=pair_key,
            synthesis_mode=LatentBridgeSynthesisMode.NONE,
            reasons=[LatentBridgeBlockReason.AUTO_SYNTHESIS_DISABLED],
            evidence=evidence,
            metadata=metadata,
        )

    hard_reasons = _check_hard_compatibility(evidence)
    if hard_reasons:
        return _blocked_hypothesis(
            pair_key=pair_key,
            synthesis_mode=LatentBridgeSynthesisMode.NONE,
            reasons=hard_reasons,
            evidence=evidence,
            metadata=metadata,
        )

    available_modes = _available_modes(evidence, resolved_policy)
    if not available_modes and not evidence.candidates:
        return _blocked_hypothesis(
            pair_key=pair_key,
            synthesis_mode=LatentBridgeSynthesisMode.NONE,
            reasons=[LatentBridgeBlockReason.NO_ADMISSIBLE_CANDIDATE],
            evidence=evidence,
            metadata=metadata,
        )

    measurement_reasons = (
        _check_measurement_mode(evidence, resolved_policy)
        if LatentBridgeSynthesisMode.MEASUREMENT_MODEL in available_modes
        else [LatentBridgeBlockReason.INSUFFICIENT_INDICATORS]
    )
    environment_reasons = (
        _check_environment_mode(evidence, resolved_policy)
        if LatentBridgeSynthesisMode.MULTI_ENVIRONMENT in available_modes
        else [LatentBridgeBlockReason.INSUFFICIENT_ENVIRONMENTS]
    )
    proxy_reasons = (
        _check_proxy_mode(evidence, resolved_policy)
        if LatentBridgeSynthesisMode.PROXY in available_modes
        else [LatentBridgeBlockReason.INSUFFICIENT_PROXY_FAMILIES]
    )

    admissible_measurement = not measurement_reasons
    admissible_environment = not environment_reasons and (
        admissible_measurement or not _environment_only_refused(evidence, resolved_policy)
    )
    admissible_proxy = not proxy_reasons and resolved_policy.allow_proxy_only_mode

    if (
        not admissible_measurement
        and not admissible_proxy
        and LatentBridgeSynthesisMode.MULTI_ENVIRONMENT in available_modes
        and not resolved_policy.allow_environment_only_mode
    ):
        return _blocked_hypothesis(
            pair_key=pair_key,
            synthesis_mode=LatentBridgeSynthesisMode.MULTI_ENVIRONMENT,
            reasons=[LatentBridgeBlockReason.ENVIRONMENT_ONLY_EVIDENCE, *environment_reasons],
            evidence=evidence,
            metadata=metadata,
        )

    if not (admissible_measurement or admissible_proxy or admissible_environment):
        combined = _dedupe_reasons(
            [*measurement_reasons, *environment_reasons, *proxy_reasons]
            or [LatentBridgeBlockReason.NO_ADMISSIBLE_CANDIDATE]
        )
        return _blocked_hypothesis(
            pair_key=pair_key,
            synthesis_mode=_guess_primary_mode(available_modes),
            reasons=combined,
            evidence=evidence,
            metadata=metadata,
        )

    primary_mode = _select_primary_mode(
        admissible_measurement=admissible_measurement,
        admissible_environment=admissible_environment,
        admissible_proxy=admissible_proxy,
        available_modes=available_modes,
    )

    if not evidence.candidates:
        return _blocked_hypothesis(
            pair_key=pair_key,
            synthesis_mode=primary_mode,
            reasons=[LatentBridgeBlockReason.NO_ADMISSIBLE_CANDIDATE],
            evidence=evidence,
            metadata=metadata,
        )

    surviving: list[LatentBridgeCandidate] = []
    candidate_block_reasons: dict[str, list[LatentBridgeBlockReason]] = {}
    for candidate in evidence.candidates:
        reasons = _check_candidate(candidate, resolved_policy)
        if reasons:
            candidate_block_reasons[candidate.candidate_id] = reasons
            continue
        surviving.append(candidate)

    metadata["candidate_block_reasons"] = {
        candidate_id: [reason.value for reason in reasons]
        for candidate_id, reasons in sorted(candidate_block_reasons.items())
    }

    if not surviving:
        aggregated_reasons = _dedupe_reasons(
            [reason for reasons in candidate_block_reasons.values() for reason in reasons]
            or [LatentBridgeBlockReason.NO_ADMISSIBLE_CANDIDATE]
        )
        return _blocked_hypothesis(
            pair_key=pair_key,
            synthesis_mode=primary_mode,
            reasons=aggregated_reasons,
            evidence=evidence,
            metadata=metadata,
        )

    if len(surviving) > 1 and resolved_policy.block_on_ambiguity:
        metadata["surviving_candidate_ids"] = [candidate.candidate_id for candidate in surviving]
        return _blocked_hypothesis(
            pair_key=pair_key,
            synthesis_mode=primary_mode,
            reasons=[LatentBridgeBlockReason.AMBIGUOUS_COMPETING_LATENTS],
            evidence=evidence,
            metadata=metadata,
            status=LatentBridgeStatus.BLOCKED_AMBIGUOUS,
        )

    chosen = surviving[0]
    resolved_mode = (
        chosen.synthesis_mode
        if chosen.synthesis_mode is not LatentBridgeSynthesisMode.NONE
        else primary_mode
    )
    metadata["selected_candidate_id"] = chosen.candidate_id
    metadata["semantic_interpretation_confidence"] = "none"
    metadata["opaque_label_required"] = resolved_policy.opaque_label_required
    return LatentBridgeHypothesis(
        bridge_id=_derive_bridge_id(pair_key, resolved_mode),
        pair_key=pair_key,
        status=LatentBridgeStatus.PROPOSED,
        synthesis_mode=resolved_mode,
        latent_label=None,
        measurement_side_a_refs=_dedupe_strings(evidence.measurement_side_a_refs),
        measurement_side_b_refs=_dedupe_strings(evidence.measurement_side_b_refs),
        environment_refs=_dedupe_strings(evidence.environment_refs),
        proxy_refs=_dedupe_strings(
            [ref for family in evidence.proxy_families for ref in family.proxy_refs]
        ),
        anchor_items=_dedupe_strings(evidence.anchor_items),
        baseline_model_refs=_dedupe_strings(evidence.baseline_model_refs),
        bridge_model_ref=evidence.bridge_model_ref,
        heldout_metrics=chosen.heldout_metrics,
        falsification_tests=list(chosen.falsification_tests),
        block_conditions_checked=[],
        metadata=metadata,
    )


def _environment_only_refused(
    evidence: LatentBridgeEvidence,
    policy: LatentBridgeSynthesisPolicy,
) -> bool:
    if policy.allow_environment_only_mode:
        return False
    total_indicators = len(evidence.measurement_side_a_refs) + len(evidence.measurement_side_b_refs)
    has_measurement_scaffold = total_indicators >= policy.min_total_indicators
    has_proxy_scaffold = len(evidence.proxy_families) >= 2
    return not (has_measurement_scaffold or has_proxy_scaffold)


def _select_primary_mode(
    *,
    admissible_measurement: bool,
    admissible_environment: bool,
    admissible_proxy: bool,
    available_modes: set[LatentBridgeSynthesisMode],
) -> LatentBridgeSynthesisMode:
    if admissible_measurement and admissible_environment:
        return LatentBridgeSynthesisMode.HYBRID
    if admissible_measurement:
        return LatentBridgeSynthesisMode.MEASUREMENT_MODEL
    if admissible_proxy:
        return LatentBridgeSynthesisMode.PROXY
    if admissible_environment:
        return LatentBridgeSynthesisMode.MULTI_ENVIRONMENT
    return _guess_primary_mode(available_modes)


def _guess_primary_mode(
    available_modes: set[LatentBridgeSynthesisMode],
) -> LatentBridgeSynthesisMode:
    for mode in (
        LatentBridgeSynthesisMode.MEASUREMENT_MODEL,
        LatentBridgeSynthesisMode.PROXY,
        LatentBridgeSynthesisMode.MULTI_ENVIRONMENT,
        LatentBridgeSynthesisMode.HYBRID,
    ):
        if mode in available_modes:
            return mode
    return LatentBridgeSynthesisMode.NONE


def _blocked_hypothesis(
    *,
    pair_key: str,
    synthesis_mode: LatentBridgeSynthesisMode,
    reasons: Sequence[LatentBridgeBlockReason],
    evidence: LatentBridgeEvidence,
    metadata: dict[str, Any],
    status: LatentBridgeStatus = LatentBridgeStatus.BLOCKED,
) -> LatentBridgeHypothesis:
    return LatentBridgeHypothesis(
        bridge_id=_derive_bridge_id(pair_key, synthesis_mode),
        pair_key=pair_key,
        status=status,
        synthesis_mode=synthesis_mode,
        latent_label=None,
        measurement_side_a_refs=_dedupe_strings(evidence.measurement_side_a_refs),
        measurement_side_b_refs=_dedupe_strings(evidence.measurement_side_b_refs),
        environment_refs=_dedupe_strings(evidence.environment_refs),
        proxy_refs=_dedupe_strings(
            [ref for family in evidence.proxy_families for ref in family.proxy_refs]
        ),
        anchor_items=_dedupe_strings(evidence.anchor_items),
        baseline_model_refs=_dedupe_strings(evidence.baseline_model_refs),
        bridge_model_ref=evidence.bridge_model_ref,
        heldout_metrics=None,
        falsification_tests=[],
        block_conditions_checked=_dedupe_reasons(reasons),
        metadata=metadata,
    )


def persist_latent_bridge_hypothesis(
    store: ArtifactStore,
    hypothesis: LatentBridgeHypothesis,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _LATENT_BRIDGE_HYPOTHESIS_SCHEMA_NAME,
    schema_version: str = _LATENT_BRIDGE_HYPOTHESIS_SCHEMA_VERSION,
) -> LatentBridgeHypothesisRef:
    """Persist a latent-bridge hypothesis and return its typed ref."""
    ref = put_json_artifact(
        store,
        hypothesis.model_dump(mode="json"),
        kind=_LATENT_BRIDGE_HYPOTHESIS_SCHEMA_NAME,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return LatentBridgeHypothesisRef.model_validate(ref)


def load_latent_bridge_hypothesis(
    store: ArtifactStore,
    ref: LatentBridgeHypothesisRef,
) -> LatentBridgeHypothesis:
    """Load a persisted latent-bridge hypothesis."""
    payload = get_json_artifact(store, ref.artifact_id)
    return LatentBridgeHypothesis.model_validate(payload)


__all__ = [
    "LatentBridgeBlockReason",
    "LatentBridgeCandidate",
    "LatentBridgeEvidence",
    "LatentBridgeFalsificationTest",
    "LatentBridgeFalsificationTestFamily",
    "LatentBridgeFalsificationTestStatus",
    "LatentBridgeHeldoutMetrics",
    "LatentBridgeHypothesis",
    "LatentBridgeHypothesisRef",
    "LatentBridgeInvarianceLevel",
    "LatentBridgeProxyFamily",
    "LatentBridgeStatus",
    "LatentBridgeSynthesisMode",
    "LatentBridgeSynthesisPolicy",
    "build_pair_key",
    "load_latent_bridge_hypothesis",
    "persist_latent_bridge_hypothesis",
    "synthesize_latent_bridge",
]
