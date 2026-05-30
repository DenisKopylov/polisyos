"""Governance adapter for latent discovery artifacts.

Historically this adapter enforced ``readiness_cap="proof_only"`` for every
latent bundle. Stage 9.3 turns the readiness cap into a judge-derived outcome:
the adapter still enforces research-surface hygiene (assumption cards, scope
regime, falsification hooks) but now delegates the promotion decision to
:func:`evaluate_latent_promotion`, which inspects the structured
``LatentPromotionEvidence`` block and emits a machine-readable verdict.

Bundles without a ``promotion_evidence`` block keep ``proof_only`` semantics
(the judge defaults to research-only), preserving the existing behaviour for
every caller that hasn't started emitting the Stage 9.3 evidence payload yet.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.causal_discovery import (
    LatentDiscoveryBundle,
    LatentPromotionEvidence,
    LatentPromotionVerdict,
    LatentTrustLevel,
)
from polisyos.ir.analytics.latent_bridge_synthesis import (
    LatentBridgeHypothesis,
    LatentBridgeStatus,
)
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.scientist.methods.causal.latent_separation import (
    SEPARATION_DIAGNOSTICS_KEY,
    certified_latent_separation_pairs,
    certify_latent_separation_trust,
    latent_separation_assumption_surfaces,
    latent_separation_falsification_surfaces,
    metadata_with_computed_latent_separation,
    separation_diagnostics_payload,
)
from polisyos.scientist.methods.search.latent_promotion import evaluate_latent_promotion

_CARDINALITY_CONDITION_PREFIXES = (
    "class:",
    "atomic_block:",
    "env_shift:",
    "minimality:",
    "role_rule:",
    "moderator_extension:",
)
_CARDINALITY_METADATA_KEYS = {
    "model_class",
    "identifiability_status",
    "latent_blocks",
    "latent_candidates",
    "ambiguity_notes",
}
_SUPPORTED_CARDINALITY_MODEL_CLASSES = {
    "ME-LiNGLaH-S",
    "ME-LiNGLaH-S-Int",
    "multi_environment_linear_nongaussian_latent_sem",
}


class LatentGovernanceAssessment(BaseModel):
    """Normalized latent-governance decision used by search runtime."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    active: bool = True
    valid: bool
    claim_mode: Literal["proof_only", "bounded_latent", "validated_measurement_latent"] = (
        "proof_only"
    )
    degradation_mode: Literal["research_only", "bounds_only", "measurement_ready"] = "research_only"
    readiness_cap: Literal["proof_only", "bounds_ready", "estimation_ready"] = "proof_only"
    promotion_allowed: bool = False
    human_gate_required: bool = True
    not_for_decision_support: bool = True
    missing_requirements: list[str] = Field(default_factory=list)
    surfaced_assumptions: list[str] = Field(default_factory=list)
    surfaced_falsification_tests: list[str] = Field(default_factory=list)
    no_promotion_reasons: list[str] = Field(default_factory=list)
    promotion_verdict: LatentPromotionVerdict | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def assess_latent_governance(
    bundle: LatentDiscoveryBundle | None,
) -> LatentGovernanceAssessment | None:
    """Assess latent governance helper."""
    if bundle is None:
        return None
    bundle_metadata = metadata_with_computed_latent_separation(bundle.metadata)

    verdict = evaluate_latent_promotion(bundle)

    missing_requirements: list[str] = []
    if not bundle.proposed_latent_nodes:
        missing_requirements.append("proposed_latent_nodes_missing")
    if not bundle.inducing_environments:
        missing_requirements.append("inducing_environments_missing")
    if not bundle.identification_conditions:
        missing_requirements.append("identification_conditions_missing")
    if not bundle.assumption_cards:
        missing_requirements.append("assumption_cards_missing")
    if not bundle.human_gate_required:
        missing_requirements.append("human_gate_required_false")
    if bundle.promotion_allowed != verdict.promotion_allowed:
        missing_requirements.append("promotion_allowed_inconsistent_with_judge")
    if bundle.not_for_decision_support != verdict.not_for_decision_support:
        missing_requirements.append("not_for_decision_support_inconsistent_with_judge")
    if bundle.readiness_cap != verdict.derived_readiness_cap:
        missing_requirements.append(
            f"readiness_cap_inconsistent_with_judge:{bundle.readiness_cap}"
            f"!={verdict.derived_readiness_cap}"
        )
    cardinality_failures = _latent_cardinality_failures(bundle)
    missing_requirements.extend(cardinality_failures)
    separation_tests = _latent_separation_falsification_tests(bundle_metadata)

    surfaced_assumptions = _dedupe_strings(
        [
            *(card.description for card in bundle.assumption_cards),
            *(f"latent_environment_assumption:{value}" for value in bundle.inducing_environments),
            *(
                f"latent_identification_condition:{value}"
                for value in bundle.identification_conditions
            ),
            *_proxy_boundary_notes(bundle_metadata),
            *_latent_cardinality_assumption_notes(bundle_metadata),
            *_latent_separation_assumptions(bundle_metadata),
        ]
    )
    surfaced_falsification_tests = _dedupe_strings(
        [
            *list(bundle.falsification_tests),
            *separation_tests,
        ]
    )
    if not surfaced_falsification_tests:
        missing_requirements.append("falsification_tests_missing")
    proof_only_reason = (
        "latent_discovery_proof_only" if verdict.derived_readiness_cap == "proof_only" else None
    )
    no_promotion_reasons = _dedupe_strings(
        [
            *list(bundle.no_promotion_reasons),
            *(f"latent_cardinality_condition_failed:{value}" for value in cardinality_failures),
            *_latent_cardinality_no_promotion_reasons(bundle_metadata),
            *_proxy_boundary_no_promotion_reasons(bundle_metadata),
            *(f"latent_promotion_blocker:{value}" for value in verdict.blockers),
            *([proof_only_reason] if proof_only_reason is not None else []),
        ]
    )
    certified_trust_level = certify_latent_separation_trust(
        bundle_metadata,
        fallback=bundle.trust_level,
    )
    diagnostics = separation_diagnostics_payload(bundle_metadata)
    certified_pairs = certified_latent_separation_pairs(diagnostics)
    metadata: dict[str, Any] = {
        "trust_level": certified_trust_level.value,
        "declared_trust_level": bundle.trust_level.value,
        "readiness_cap": verdict.derived_readiness_cap,
        "bundle_readiness_cap": bundle.readiness_cap,
        "claim_mode": verdict.claim_mode,
        "degradation_mode": verdict.degradation_mode,
        "promotion_allowed": verdict.promotion_allowed,
        "target_trust_level": verdict.target_trust_level.value,
        "derived_trust_level": verdict.derived_trust_level.value,
        "proposed_latent_nodes": list(bundle.proposed_latent_nodes),
        "inducing_environments": list(bundle.inducing_environments),
        "identification_conditions": list(bundle.identification_conditions),
        "promotion_passed_gates": list(verdict.passed_gates),
        "promotion_blockers": list(verdict.blockers),
        "promotion_warnings": list(verdict.warnings),
        "promotion_scope_regime": list(verdict.scope_regime),
    }
    if diagnostics is not None:
        metadata[SEPARATION_DIAGNOSTICS_KEY] = diagnostics
        metadata["resolution_label"] = diagnostics.get("resolution_label", "unresolved")
        metadata["separated_pairs"] = list(diagnostics.get("separated_pairs", []) or [])
        metadata["certified_pairs"] = certified_pairs
        metadata["pairwise_separation_certified"] = bool(certified_pairs)
    metadata.update(_latent_cardinality_metadata(bundle_metadata, cardinality_failures))

    return LatentGovernanceAssessment(
        valid=not missing_requirements,
        claim_mode=verdict.claim_mode,
        degradation_mode=verdict.degradation_mode,
        readiness_cap=verdict.derived_readiness_cap,
        promotion_allowed=verdict.promotion_allowed,
        human_gate_required=bool(bundle.human_gate_required),
        not_for_decision_support=verdict.not_for_decision_support,
        missing_requirements=missing_requirements,
        surfaced_assumptions=surfaced_assumptions,
        surfaced_falsification_tests=surfaced_falsification_tests,
        no_promotion_reasons=no_promotion_reasons,
        promotion_verdict=verdict,
        metadata=metadata,
    )


def latent_governance_metadata(
    bundle: LatentDiscoveryBundle | None,
) -> dict[str, Any] | None:
    """Latent governance metadata helper."""
    assessment = assess_latent_governance(bundle)
    if assessment is None:
        return None
    return assessment.model_dump(mode="json")


def assess_latent_bridge_governance(
    hypothesis: LatentBridgeHypothesis | None,
) -> LatentGovernanceAssessment | None:
    """Project a latent-bridge hypothesis onto the Stage 9.3 governance surface."""
    if hypothesis is None:
        return None

    evidence = _latent_bridge_promotion_evidence(hypothesis)
    bundle = LatentDiscoveryBundle(
        proposed_latent_nodes=[hypothesis.bridge_id],
        inducing_environments=list(hypothesis.environment_refs),
        identification_conditions=_dedupe_strings(
            [
                f"latent_bridge_mode:{hypothesis.synthesis_mode.value}",
                f"latent_bridge_status:{hypothesis.status.value}",
                *([f"latent_bridge_pair_key:{hypothesis.pair_key}"] if hypothesis.pair_key else []),
            ]
        ),
        falsification_tests=_dedupe_strings(
            [
                f"latent_bridge_falsification:{test.test_family.value}"
                for test in hypothesis.falsification_tests
            ]
        ),
        trust_level=_latent_bridge_target_trust_level(hypothesis, evidence=evidence),
        assumption_cards=_latent_bridge_assumption_cards(hypothesis),
        readiness_cap="proof_only",
        human_gate_required=True,
        promotion_allowed=False,
        no_promotion_reasons=_dedupe_strings(
            [
                *(
                    f"latent_bridge_blocked:{reason.value}"
                    for reason in hypothesis.block_conditions_checked
                ),
                *(
                    ["latent_bridge_status_not_proposed"]
                    if hypothesis.status is not LatentBridgeStatus.PROPOSED
                    else []
                ),
            ]
        ),
        not_for_decision_support=True,
        promotion_evidence=evidence,
        metadata={
            "latent_artifact_kind": "latent_bridge",
            "latent_bridge_pair_key": hypothesis.pair_key,
            "latent_bridge_status": hypothesis.status.value,
            "latent_bridge_synthesis_mode": hypothesis.synthesis_mode.value,
            "latent_bridge_metadata": dict(hypothesis.metadata),
        },
    )
    assessment = assess_latent_governance(bundle)
    if assessment is None:
        return None

    blockers = _latent_artifact_blockers(
        promotion_evidence=evidence,
        promotion_verdict=assessment.promotion_verdict,
    )
    metadata = dict(assessment.metadata)
    metadata.update(
        {
            "latent_artifact_kind": "latent_bridge",
            "latent_artifact_blockers": blockers,
        }
    )
    no_promotion_reasons = _dedupe_strings(
        [
            *assessment.no_promotion_reasons,
            *blockers,
        ]
    )
    return assessment.model_copy(
        update={
            "no_promotion_reasons": no_promotion_reasons,
            "metadata": metadata,
        }
    )


def materialize_latent_bridge_governance(
    hypothesis: LatentBridgeHypothesis,
) -> LatentBridgeHypothesis:
    """Attach the canonical Stage 9.3 governance summary to a bridge artifact."""
    assessment = assess_latent_bridge_governance(hypothesis)
    if assessment is None:
        return hypothesis
    promotion_evidence = _latent_bridge_promotion_evidence(hypothesis)
    metadata = dict(hypothesis.metadata)
    metadata["latent_governance"] = assessment.model_dump(mode="json")
    metadata["latent_artifact_blockers"] = list(
        assessment.metadata.get("latent_artifact_blockers", [])
    )
    return hypothesis.model_copy(
        update={
            "promotion_evidence": promotion_evidence,
            "promotion_verdict": (
                assessment.promotion_verdict if promotion_evidence is not None else None
            ),
            "readiness_cap": assessment.readiness_cap,
            "promotion_allowed": assessment.promotion_allowed,
            "not_for_decision_support": assessment.not_for_decision_support,
            "human_gate_required": assessment.human_gate_required,
            "metadata": metadata,
        }
    )


def _proxy_boundary_notes(metadata: dict[str, Any]) -> list[str]:
    payload = metadata.get("proxy_boundary")
    if not isinstance(payload, dict):
        return []
    notes = payload.get("boundary_notes", [])
    if not isinstance(notes, list):
        return []
    return [str(item) for item in notes if str(item).strip()]


def _proxy_boundary_no_promotion_reasons(metadata: dict[str, Any]) -> list[str]:
    payload = metadata.get("proxy_boundary")
    if not isinstance(payload, dict):
        return []
    reasons = payload.get("no_promotion_reasons", [])
    if not isinstance(reasons, list):
        return []
    return [str(item) for item in reasons if str(item).strip()]


def _latent_bridge_target_trust_level(
    hypothesis: LatentBridgeHypothesis,
    *,
    evidence: LatentPromotionEvidence | None,
) -> LatentTrustLevel:
    raw_target = str(hypothesis.metadata.get("target_trust_level", "")).strip().lower()
    if raw_target:
        try:
            return LatentTrustLevel(raw_target)
        except ValueError:
            pass
    if evidence is None:
        return LatentTrustLevel.RESEARCH
    if hypothesis.status is LatentBridgeStatus.HUMAN_VERIFIED and evidence.measurement_scope:
        return LatentTrustLevel.VALIDATED
    return LatentTrustLevel.CONDITIONAL


def _latent_bridge_assumption_cards(
    hypothesis: LatentBridgeHypothesis,
) -> list:
    evidence_basis = _dedupe_strings(
        [
            *hypothesis.measurement_side_a_refs,
            *hypothesis.measurement_side_b_refs,
            *hypothesis.environment_refs,
            *hypothesis.proxy_refs,
            *hypothesis.baseline_model_refs,
            *([hypothesis.bridge_model_ref] if hypothesis.bridge_model_ref else []),
        ]
    )
    falsification_hook = (
        f"latent_bridge_falsification:{hypothesis.falsification_tests[0].test_family.value}"
        if hypothesis.falsification_tests
        else None
    )
    from polisyos.ir.analytics.causal_discovery import LatentAssumptionCard

    return [
        LatentAssumptionCard(
            assumption_id=f"latent_bridge::{hypothesis.synthesis_mode.value}",
            title="Latent bridge construct coherence",
            description=(
                "The stitched interface pair is treated as a shared latent construct "
                "only within the evidence mode declared by the bridge hypothesis."
            ),
            evidence_basis=evidence_basis,
            falsification_hook=falsification_hook,
            metadata={
                "latent_artifact_kind": "latent_bridge",
                "pair_key": hypothesis.pair_key,
                "synthesis_mode": hypothesis.synthesis_mode.value,
            },
        )
    ]


def _latent_bridge_promotion_evidence(
    hypothesis: LatentBridgeHypothesis,
) -> LatentPromotionEvidence | None:
    if hypothesis.promotion_evidence is not None:
        return hypothesis.promotion_evidence

    for key in ("promotion_evidence", "latent_promotion_evidence"):
        payload = hypothesis.metadata.get(key)
        if hasattr(payload, "model_dump") and not isinstance(payload, dict):
            payload = payload.model_dump(mode="json")
        if isinstance(payload, dict):
            try:
                return LatentPromotionEvidence.model_validate(payload)
            except Exception:
                continue

    observable_implication_refs = _artifact_ref_list(
        hypothesis.metadata.get("observable_implication_refs"),
        hypothesis.measurement_side_a_refs,
        hypothesis.measurement_side_b_refs,
    )
    local_misspecification_test_refs = _artifact_ref_list(
        hypothesis.metadata.get("local_misspecification_test_refs")
    )
    environment_stability_ref = _artifact_ref_from_candidates(
        hypothesis.metadata.get("environment_stability_ref"),
        hypothesis.environment_refs,
    )
    rival_explanation_audit_ref = _artifact_ref_from_candidates(
        hypothesis.metadata.get("rival_explanation_audit_ref"),
        hypothesis.bridge_model_ref,
    )
    external_evidence_refs = _artifact_ref_list(
        hypothesis.metadata.get("external_evidence_refs"),
        hypothesis.proxy_refs,
        hypothesis.baseline_model_refs,
    )
    replication_refs = _artifact_ref_list(hypothesis.metadata.get("replication_refs"))
    hidden_benchmark_ref = _artifact_ref_from_candidates(
        hypothesis.metadata.get("hidden_benchmark_ref")
    )
    reviewer_decision_ref = _artifact_ref_from_candidates(
        hypothesis.metadata.get("reviewer_decision_ref"),
        hypothesis.metadata.get("human_review_ref"),
    )
    exclusion_test_refs = _artifact_ref_list(hypothesis.metadata.get("exclusion_test_refs"))
    external_anchor_refs = _artifact_ref_list(
        hypothesis.metadata.get("external_anchor_refs"),
        hypothesis.anchor_items,
    )
    cross_model_robustness_refs = _artifact_ref_list(
        hypothesis.metadata.get("cross_model_robustness_refs"),
        hypothesis.baseline_model_refs,
    )
    scope_regime = _dedupe_strings(
        [
            "latent_bridge",
            f"latent_bridge_mode:{hypothesis.synthesis_mode.value}",
            *(
                str(item)
                for item in hypothesis.metadata.get("scope_regime", [])
                if str(item).strip()
            ),
        ]
    )
    invariance_level = (
        str(
            hypothesis.metadata.get("invariance_level")
            or hypothesis.metadata.get("promotion_invariance_level")
            or (
                "scalar"
                if hypothesis.synthesis_mode.value == "hybrid"
                else "metric"
                if hypothesis.synthesis_mode.value == "measurement_model"
                else "none"
            )
        )
        .strip()
        .lower()
    )
    if invariance_level not in {"none", "configural", "metric", "scalar", "strict", "approximate"}:
        invariance_level = "none"

    evidence = LatentPromotionEvidence(
        observable_implication_refs=observable_implication_refs,
        local_misspecification_test_refs=local_misspecification_test_refs,
        environment_stability_ref=environment_stability_ref,
        rival_explanation_audit_ref=rival_explanation_audit_ref,
        external_evidence_refs=external_evidence_refs,
        replication_refs=replication_refs,
        hidden_benchmark_ref=hidden_benchmark_ref,
        reviewer_decision_ref=reviewer_decision_ref,
        exclusion_test_refs=exclusion_test_refs,
        external_anchor_refs=external_anchor_refs,
        cross_model_robustness_refs=cross_model_robustness_refs,
        scope_regime=scope_regime,
        invariance_level=invariance_level,
        measurement_scope=hypothesis.synthesis_mode.value in {"measurement_model", "hybrid"},
        structural_interpretation_rejected=bool(
            hypothesis.metadata.get("structural_interpretation_rejected", False)
        ),
        notes=_dedupe_strings(
            [
                f"latent_bridge_status:{hypothesis.status.value}",
                f"latent_bridge_pair_key:{hypothesis.pair_key}",
            ]
        ),
    )
    if not any(
        (
            evidence.observable_implication_refs,
            evidence.local_misspecification_test_refs,
            evidence.environment_stability_ref is not None,
            evidence.rival_explanation_audit_ref is not None,
            evidence.external_evidence_refs,
            evidence.replication_refs,
            evidence.hidden_benchmark_ref is not None,
            evidence.reviewer_decision_ref is not None,
            evidence.exclusion_test_refs,
            evidence.external_anchor_refs,
            evidence.cross_model_robustness_refs,
        )
    ):
        return None
    return evidence


def _artifact_ref_from_candidates(*payloads: object) -> ArtifactRefModel | None:
    for payload in payloads:
        if payload in (None, ""):
            continue
        if hasattr(payload, "model_dump") and not isinstance(payload, dict):
            payload = payload.model_dump(mode="json")
        if isinstance(payload, (list, tuple)):
            for item in payload:
                ref = _artifact_ref_from_candidates(item)
                if ref is not None:
                    return ref
            continue
        try:
            return ArtifactRefModel.model_validate(payload)
        except Exception:
            continue
    return None


def _artifact_ref_list(*payloads: object) -> list[ArtifactRefModel]:
    refs: list[ArtifactRefModel] = []
    seen: set[tuple[str, str, str]] = set()
    for payload in payloads:
        items = payload if isinstance(payload, (list, tuple)) else [payload]
        for item in items:
            ref = _artifact_ref_from_candidates(item)
            if ref is None:
                continue
            signature = (ref.artifact_id, ref.kind, ref.media_type)
            if signature in seen:
                continue
            seen.add(signature)
            refs.append(ref)
    return refs


def _latent_artifact_blockers(
    *,
    promotion_evidence: LatentPromotionEvidence | None,
    promotion_verdict: LatentPromotionVerdict | None,
) -> list[str]:
    blockers: list[str] = []
    if promotion_evidence is None:
        blockers.append("latent_promotion_evidence_missing")
    if promotion_verdict is None or promotion_verdict.derived_readiness_cap == "proof_only":
        blockers.append("latent_artifact_proof_only")
    if (
        promotion_evidence is not None
        and promotion_verdict is not None
        and not promotion_verdict.promotion_allowed
    ):
        blockers.append("latent_promotion_denied")
    return _dedupe_strings(blockers)


def _latent_cardinality_failures(bundle: LatentDiscoveryBundle) -> list[str]:
    if not _uses_cardinality_contract(bundle):
        return []

    failures: list[str] = []
    conditions = [str(value).strip() for value in bundle.identification_conditions]
    if not _has_supported_class_condition(bundle.metadata, conditions):
        failures.append("latent_cardinality_class_condition_missing")

    descriptors: list[dict[str, str]] = []
    for node in bundle.proposed_latent_nodes:
        descriptor = _parse_latent_node_descriptor(node)
        if descriptor is None:
            failures.append(f"latent_cardinality_node_descriptor_invalid:{node}")
            continue
        descriptors.append(descriptor)

    metadata_blocks = _metadata_latent_blocks_by_id(bundle.metadata)
    for descriptor in descriptors:
        latent_id = descriptor["latent_id"]
        role = descriptor.get("role", "")
        status = descriptor.get("status", "")
        candidate_role = descriptor.get("candidate_role", "")
        block_size = descriptor.get("block_size", "")

        if not block_size.isdigit() or int(block_size) < 1:
            failures.append(f"latent_cardinality_block_size_invalid:{latent_id}")
        if status == "suspected_only":
            failures.append(f"latent_cardinality_suspected_node_promoted:{latent_id}")
        if status == "identified" and role == "unknown":
            failures.append(f"latent_cardinality_identified_role_unknown:{latent_id}")
        if role not in {"confounder", "mediator", "moderator", "unknown"}:
            failures.append(f"latent_cardinality_role_invalid:{latent_id}")

        if not any(value.startswith(f"atomic_block:{latent_id}:") for value in conditions):
            failures.append(f"latent_cardinality_atomic_block_missing:{latent_id}")
        if not _has_localized_shift_condition(latent_id, conditions):
            failures.append(f"latent_cardinality_localized_shift_missing:{latent_id}")
        if not _has_minimality_condition(latent_id, conditions):
            failures.append(f"latent_cardinality_minimality_missing:{latent_id}")
        if role in {"confounder", "mediator"} and not any(
            value.startswith(f"role_rule:{latent_id}:") for value in conditions
        ):
            failures.append(f"latent_cardinality_role_rule_missing:{latent_id}")
        if role == "moderator" and not _has_verified_moderator_condition(latent_id, conditions):
            failures.append(f"latent_cardinality_moderator_interaction_missing:{latent_id}")
        if (
            role == "unknown"
            and candidate_role == "moderator"
            and not any(
                value.startswith(f"moderator_extension:{latent_id}:") for value in conditions
            )
        ):
            failures.append(f"latent_cardinality_moderator_refusal_missing:{latent_id}")

        metadata_block = metadata_blocks.get(latent_id)
        if metadata_blocks and metadata_block is None:
            failures.append(f"latent_cardinality_metadata_missing:{latent_id}")
        if metadata_block is not None:
            failures.extend(_latent_block_metadata_failures(latent_id, metadata_block))

    return _dedupe_strings(failures)


def _uses_cardinality_contract(bundle: LatentDiscoveryBundle) -> bool:
    return (
        any("|block_size=" in str(value) for value in bundle.proposed_latent_nodes)
        or any(
            str(value).strip().startswith(_CARDINALITY_CONDITION_PREFIXES)
            for value in bundle.identification_conditions
        )
        or any(key in bundle.metadata for key in _CARDINALITY_METADATA_KEYS)
    )


def _has_supported_class_condition(
    metadata: dict[str, Any],
    conditions: list[str],
) -> bool:
    model_class = str(metadata.get("model_class", "")).strip()
    if model_class and model_class not in _SUPPORTED_CARDINALITY_MODEL_CLASSES:
        return False
    return any(
        value
        in {
            "class:multi_env_linear_nongaussian_latent_sem",
            "class:ME-LiNGLaH-S",
            "class:ME-LiNGLaH-S-Int",
        }
        for value in conditions
    )


def _parse_latent_node_descriptor(value: str) -> dict[str, str] | None:
    parts = [part.strip() for part in str(value).split("|") if part.strip()]
    if len(parts) < 2:
        return None
    descriptor = {"latent_id": parts[0]}
    for part in parts[1:]:
        key, separator, raw_value = part.partition("=")
        if not separator:
            return None
        descriptor[key.strip()] = raw_value.strip()
    required = {"block_size", "role", "status"}
    if not required.issubset(descriptor):
        return None
    return descriptor


def _has_localized_shift_condition(latent_id: str, conditions: list[str]) -> bool:
    return any(
        value.startswith(f"env_shift:{latent_id}:") and "localized=true" in value
        for value in conditions
    )


def _has_minimality_condition(latent_id: str, conditions: list[str]) -> bool:
    return any(
        value.startswith(f"minimality:{latent_id}:")
        and "minimal_explanation_across_environments=true" in value
        for value in conditions
    )


def _has_verified_moderator_condition(latent_id: str, conditions: list[str]) -> bool:
    return any(
        value.startswith(f"moderator_extension:{latent_id}:")
        and "interaction_signature=verified" in value
        and "failed" not in value
        for value in conditions
    )


def _metadata_latent_blocks_by_id(metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
    blocks = metadata.get("latent_blocks")
    if not isinstance(blocks, list):
        return {}
    output: dict[str, dict[str, Any]] = {}
    for block in blocks:
        if not isinstance(block, dict):
            continue
        latent_id = str(block.get("latent_id", "")).strip()
        if latent_id:
            output[latent_id] = dict(block)
    return output


def _latent_block_metadata_failures(
    latent_id: str,
    block: dict[str, Any],
) -> list[str]:
    if str(block.get("status", "")).strip() != "identified":
        return []
    evidence = block.get("evidence")
    if not isinstance(evidence, dict):
        return [f"latent_cardinality_evidence_missing:{latent_id}"]
    failures = []
    for key in (
        "gin_supported",
        "atomic_structure_supported",
        "shift_localized",
        "minimal_decomposition_supported",
        "role_rule_supported",
    ):
        if not bool(evidence.get(key)):
            failures.append(f"latent_cardinality_evidence_missing:{latent_id}:{key}")
    if str(block.get("role", "")).strip() == "moderator" and not bool(
        evidence.get("interaction_signature_supported")
    ):
        failures.append(f"latent_cardinality_evidence_missing:{latent_id}:interaction")
    return failures


def _latent_cardinality_assumption_notes(metadata: dict[str, Any]) -> list[str]:
    notes = metadata.get("ambiguity_notes", [])
    if not isinstance(notes, list):
        return []
    return [f"latent_cardinality_ambiguity:{item}" for item in notes if str(item).strip()]


def _latent_cardinality_no_promotion_reasons(metadata: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for block in _metadata_latent_blocks_by_id(metadata).values():
        reason = str(block.get("reason_not_identified", "")).strip()
        if reason:
            reasons.append(f"latent_cardinality_not_identified:{reason}")
    return reasons


def _latent_cardinality_metadata(
    metadata: dict[str, Any],
    failures: list[str],
) -> dict[str, Any]:
    payload = {key: metadata[key] for key in _CARDINALITY_METADATA_KEYS if key in metadata}
    if failures:
        payload["cardinality_gate_failures"] = list(failures)
    return payload


def _latent_separation_assumptions(metadata: dict[str, Any]) -> list[str]:
    diagnostics = separation_diagnostics_payload(metadata)
    return latent_separation_assumption_surfaces(diagnostics)


def _latent_separation_falsification_tests(metadata: dict[str, Any]) -> list[str]:
    diagnostics = separation_diagnostics_payload(metadata)
    return latent_separation_falsification_surfaces(diagnostics)


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


__all__ = [
    "LatentGovernanceAssessment",
    "assess_latent_bridge_governance",
    "assess_latent_governance",
    "latent_governance_metadata",
    "materialize_latent_bridge_governance",
]
