"""Stage 9.3 latent promotion judge.

Policy-level decision whether a ``LatentDiscoveryBundle`` can be promoted above
``readiness_cap="proof_only"``. The judge never promotes on behalf of the
frontier module: it only confirms that the structured ``LatentPromotionEvidence``
block carries enough replayable artifacts to exit research-only status, and
maps the evidence surface onto the ``claim_mode`` / ``degradation_mode`` pair
consumed by the readiness stack.

Conservative invariants:

* Absence of a promotion-evidence block is equivalent to declaring the bundle
  research-only: the verdict keeps ``derived_readiness_cap == "proof_only"``
  regardless of ``trust_level`` hints supplied by upstream discovery.
* ``validated + estimation_ready`` is reserved for narrow reflective
  measurement scopes where the structural interpretation has not been
  rejected; all other ``validated`` bundles stay capped at ``bounds_ready``.
* The ``human_gate_required`` flag stays true at every trust level; only the
  downstream semantics change.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from polisyos.ir.analytics.causal_discovery import (
    LatentDiscoveryBundle,
    LatentPromotionEvidence,
    LatentPromotionVerdict,
    LatentTrustLevel,
)
from polisyos.ir.refs import ArtifactRefModel

TrustLevelCap = Literal["proof_only", "bounds_ready", "estimation_ready"]
ClaimMode = Literal["proof_only", "bounded_latent", "validated_measurement_latent"]
DegradationMode = Literal["research_only", "bounds_only", "measurement_ready"]

_READINESS_CAP_ORDER: dict[TrustLevelCap, int] = {
    "proof_only": 0,
    "bounds_ready": 1,
    "estimation_ready": 2,
}

_INVARIANCE_RANK: dict[str, int] = {
    "none": 0,
    "configural": 1,
    "metric": 2,
    "approximate": 2,
    "scalar": 3,
    "strict": 4,
}

_TRUST_LEVEL_CAP: dict[LatentTrustLevel, TrustLevelCap] = {
    LatentTrustLevel.RESEARCH: "proof_only",
    LatentTrustLevel.CONDITIONAL: "bounds_ready",
    LatentTrustLevel.VALIDATED: "bounds_ready",
}


class LatentPromotionJudgeInput(BaseModel):
    """Bundle the inputs the judge needs when running outside a bundle context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    trust_level: LatentTrustLevel = LatentTrustLevel.RESEARCH
    evidence: LatentPromotionEvidence | None = None
    target_trust_level: LatentTrustLevel | None = None


def readiness_cap_rank(cap: TrustLevelCap) -> int:
    """Return the monotonic rank of a readiness cap."""
    return _READINESS_CAP_ORDER[cap]


def min_readiness_cap(*caps: TrustLevelCap) -> TrustLevelCap:
    """Return the most conservative readiness cap across the given values."""
    if not caps:
        return "proof_only"
    return min(caps, key=readiness_cap_rank)


def trust_level_cap(
    trust: LatentTrustLevel,
    *,
    measurement_scope: bool = False,
) -> TrustLevelCap:
    """Return the trust-level readiness cap.

    ``validated`` caps at ``bounds_ready`` by default; only narrow reflective
    measurement scopes can open ``estimation_ready``.
    """
    if trust is LatentTrustLevel.VALIDATED and measurement_scope:
        return "estimation_ready"
    return _TRUST_LEVEL_CAP[trust]


def evaluate_latent_promotion(
    bundle: LatentDiscoveryBundle | None,
    *,
    target_trust_level: LatentTrustLevel | None = None,
) -> LatentPromotionVerdict:
    """Evaluate the Stage 9.3 promotion gate classes for a latent bundle."""
    if bundle is None:
        return _research_verdict(
            target=LatentTrustLevel.RESEARCH,
            evidence=None,
            blockers=["latent_bundle_missing"],
        )

    declared = bundle.trust_level
    evidence = bundle.promotion_evidence
    target = target_trust_level or declared
    if evidence is None:
        blockers = ["latent_promotion_evidence_missing"]
        if target is not LatentTrustLevel.RESEARCH:
            blockers.append(f"target_trust_level_requires_evidence:{target.value}")
        return _research_verdict(
            target=target,
            evidence=None,
            blockers=blockers,
        )

    if target is LatentTrustLevel.RESEARCH:
        return _research_verdict(target=target, evidence=evidence)

    conditional_gate = _conditional_gate(evidence)
    if target is LatentTrustLevel.CONDITIONAL:
        return _conditional_verdict(
            target=target,
            evidence=evidence,
            gate=conditional_gate,
        )

    # Validated target.
    if not conditional_gate.passed:
        return _conditional_verdict(
            target=target,
            evidence=evidence,
            gate=conditional_gate,
            validated_prerequisite_failed=True,
        )
    validated_gate = _validated_gate(evidence)
    passed = conditional_gate.passed and validated_gate.passed
    measurement_scope_allowed = (
        passed
        and evidence.measurement_scope
        and not evidence.structural_interpretation_rejected
        and _INVARIANCE_RANK.get(evidence.invariance_level, 0) >= _INVARIANCE_RANK["scalar"]
    )
    derived_cap: TrustLevelCap = (
        "estimation_ready"
        if measurement_scope_allowed
        else "bounds_ready"
        if passed
        else "proof_only"
    )
    derived_trust = LatentTrustLevel.VALIDATED if passed else LatentTrustLevel.CONDITIONAL
    claim_mode: ClaimMode
    degradation_mode: DegradationMode
    if derived_cap == "estimation_ready":
        claim_mode = "validated_measurement_latent"
        degradation_mode = "measurement_ready"
    elif derived_cap == "bounds_ready":
        claim_mode = "bounded_latent"
        degradation_mode = "bounds_only"
    else:
        claim_mode = "proof_only"
        degradation_mode = "research_only"

    blockers = list(conditional_gate.blockers) + list(validated_gate.blockers)
    warnings = list(conditional_gate.warnings) + list(validated_gate.warnings)
    if (
        target is LatentTrustLevel.VALIDATED
        and not measurement_scope_allowed
        and evidence.measurement_scope
    ):
        warnings.append("validated_measurement_scope_requires_scalar_invariance_or_stronger")
    passed_gates = list(conditional_gate.passed_gates) + list(validated_gate.passed_gates)

    return LatentPromotionVerdict(
        target_trust_level=target,
        derived_trust_level=derived_trust,
        derived_readiness_cap=derived_cap,
        claim_mode=claim_mode,
        degradation_mode=degradation_mode,
        promotion_allowed=passed and derived_cap != "proof_only",
        not_for_decision_support=not (passed and derived_cap != "proof_only"),
        human_gate_required=True,
        passed_gates=_dedupe_strings(passed_gates),
        blockers=_dedupe_strings(blockers),
        warnings=_dedupe_strings(warnings),
        evidence_refs=_collect_evidence_refs(evidence),
        scope_regime=list(evidence.scope_regime),
    )


class _GateOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    passed_gates: list[str]
    blockers: list[str]
    warnings: list[str]


def _conditional_gate(evidence: LatentPromotionEvidence) -> _GateOutcome:
    passed_gates: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []

    if evidence.observable_implication_refs and evidence.local_misspecification_test_refs:
        passed_gates.append("testable_implications_pass")
    else:
        if not evidence.observable_implication_refs:
            blockers.append("testable_implications_missing:observable_implication_refs")
        if not evidence.local_misspecification_test_refs:
            blockers.append("testable_implications_missing:local_misspecification_test_refs")

    invariance_rank = _INVARIANCE_RANK.get(evidence.invariance_level, 0)
    if (
        evidence.environment_stability_ref is not None
        and invariance_rank >= _INVARIANCE_RANK["metric"]
    ):
        passed_gates.append("environment_stability_pass")
    else:
        if evidence.environment_stability_ref is None:
            blockers.append("environment_stability_missing:environment_stability_ref")
        if invariance_rank < _INVARIANCE_RANK["metric"]:
            blockers.append(
                f"environment_stability_missing:invariance_level_below_metric:{evidence.invariance_level}"
            )

    if evidence.rival_explanation_audit_ref is not None:
        passed_gates.append("rival_explanations_audited")
    else:
        blockers.append("rival_explanation_audit_ref_missing")

    if evidence.external_evidence_refs:
        passed_gates.append("independent_external_evidence_present")
    else:
        blockers.append("external_evidence_refs_missing")

    has_replication = bool(evidence.replication_refs) or evidence.hidden_benchmark_ref is not None
    if has_replication:
        passed_gates.append("reproducibility_pass")
    else:
        blockers.append("replication_or_hidden_benchmark_missing")

    if evidence.reviewer_decision_ref is not None:
        passed_gates.append("human_gate_pass")
    else:
        blockers.append("reviewer_decision_ref_missing")

    if not evidence.scope_regime:
        warnings.append("scope_regime_not_declared")

    return _GateOutcome(
        passed=not blockers,
        passed_gates=passed_gates,
        blockers=blockers,
        warnings=warnings,
    )


def _validated_gate(evidence: LatentPromotionEvidence) -> _GateOutcome:
    passed_gates: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []

    if len(evidence.replication_refs) >= 1 and (
        evidence.hidden_benchmark_ref is not None or len(evidence.replication_refs) >= 2
    ):
        passed_gates.append("multi_environment_replication_pass")
    else:
        blockers.append("multi_environment_replication_missing")

    invariance_rank = _INVARIANCE_RANK.get(evidence.invariance_level, 0)
    if invariance_rank >= _INVARIANCE_RANK["scalar"]:
        passed_gates.append("strengthened_invariance_pass")
    else:
        blockers.append(f"strengthened_invariance_missing:{evidence.invariance_level}")

    if evidence.exclusion_test_refs:
        passed_gates.append("exclusion_test_pass")
    else:
        blockers.append("exclusion_test_refs_missing")

    if evidence.external_anchor_refs:
        passed_gates.append("external_anchor_pass")
    else:
        blockers.append("external_anchor_refs_missing")

    if evidence.cross_model_robustness_refs or len(evidence.scope_regime) >= 1:
        passed_gates.append("cross_model_robustness_pass")
    else:
        blockers.append("cross_model_robustness_or_scope_regime_missing")

    if evidence.hidden_benchmark_ref is not None and evidence.reviewer_decision_ref is not None:
        passed_gates.append("benchmark_governance_pass")
    else:
        if evidence.hidden_benchmark_ref is None:
            blockers.append("hidden_benchmark_ref_missing")
        if evidence.reviewer_decision_ref is None:
            blockers.append("reviewer_decision_ref_missing")

    if evidence.structural_interpretation_rejected:
        warnings.append("structural_interpretation_rejected_downgrades_estimation_cap")

    return _GateOutcome(
        passed=not blockers,
        passed_gates=passed_gates,
        blockers=blockers,
        warnings=warnings,
    )


def _research_verdict(
    *,
    target: LatentTrustLevel,
    evidence: LatentPromotionEvidence | None,
    blockers: list[str] | None = None,
) -> LatentPromotionVerdict:
    return LatentPromotionVerdict(
        target_trust_level=target,
        derived_trust_level=LatentTrustLevel.RESEARCH,
        derived_readiness_cap="proof_only",
        claim_mode="proof_only",
        degradation_mode="research_only",
        promotion_allowed=False,
        not_for_decision_support=True,
        human_gate_required=True,
        passed_gates=[],
        blockers=list(blockers or []),
        warnings=[],
        evidence_refs=_collect_evidence_refs(evidence),
        scope_regime=list(evidence.scope_regime) if evidence is not None else [],
    )


def _conditional_verdict(
    *,
    target: LatentTrustLevel,
    evidence: LatentPromotionEvidence,
    gate: _GateOutcome,
    validated_prerequisite_failed: bool = False,
) -> LatentPromotionVerdict:
    passed = gate.passed
    derived_trust = LatentTrustLevel.CONDITIONAL if passed else LatentTrustLevel.RESEARCH
    derived_cap: TrustLevelCap = "bounds_ready" if passed else "proof_only"
    claim_mode: ClaimMode = "bounded_latent" if passed else "proof_only"
    degradation_mode: DegradationMode = "bounds_only" if passed else "research_only"
    blockers = list(gate.blockers)
    warnings = list(gate.warnings)
    if validated_prerequisite_failed:
        blockers.append("validated_requires_conditional_prerequisites")
    return LatentPromotionVerdict(
        target_trust_level=target,
        derived_trust_level=derived_trust,
        derived_readiness_cap=derived_cap,
        claim_mode=claim_mode,
        degradation_mode=degradation_mode,
        promotion_allowed=passed,
        not_for_decision_support=not passed,
        human_gate_required=True,
        passed_gates=list(gate.passed_gates),
        blockers=_dedupe_strings(blockers),
        warnings=_dedupe_strings(warnings),
        evidence_refs=_collect_evidence_refs(evidence),
        scope_regime=list(evidence.scope_regime),
    )


def _collect_evidence_refs(
    evidence: LatentPromotionEvidence | None,
) -> list[ArtifactRefModel]:
    if evidence is None:
        return []
    refs: list[ArtifactRefModel] = []
    refs.extend(evidence.observable_implication_refs)
    refs.extend(evidence.local_misspecification_test_refs)
    if evidence.environment_stability_ref is not None:
        refs.append(evidence.environment_stability_ref)
    if evidence.rival_explanation_audit_ref is not None:
        refs.append(evidence.rival_explanation_audit_ref)
    refs.extend(evidence.external_evidence_refs)
    refs.extend(evidence.replication_refs)
    if evidence.hidden_benchmark_ref is not None:
        refs.append(evidence.hidden_benchmark_ref)
    if evidence.reviewer_decision_ref is not None:
        refs.append(evidence.reviewer_decision_ref)
    refs.extend(evidence.exclusion_test_refs)
    refs.extend(evidence.external_anchor_refs)
    refs.extend(evidence.cross_model_robustness_refs)
    seen: set[str] = set()
    output: list[ArtifactRefModel] = []
    for ref in refs:
        key = str(ref.artifact_id)
        if key in seen:
            continue
        seen.add(key)
        output.append(ref)
    return output


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


__all__ = [
    "ClaimMode",
    "DegradationMode",
    "LatentPromotionJudgeInput",
    "TrustLevelCap",
    "evaluate_latent_promotion",
    "min_readiness_cap",
    "readiness_cap_rank",
    "trust_level_cap",
]
