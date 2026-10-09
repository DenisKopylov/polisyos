"""Replay and support helpers for decision-packet assembly."""

from __future__ import annotations

import json
from enum import Enum
from typing import TYPE_CHECKING, Final

from polisyos.core.canon import content_hash
from polisyos.core.contracts.decision_validity import DecisionValidityStatus
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ENVIRONMENT_MANIFEST_REF,
    ARTIFACT_EXEC_PLAN_REF,
    ARTIFACT_LOWERED_IR_REF,
    ARTIFACT_STATE_SNAPSHOT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_INPUT_BINDINGS_REF,
    INPUT_KNOWLEDGE_BUNDLE_REF,
    INPUT_NORM_PACK_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_RESEARCH_INTENT_REF,
    INPUT_STATE_SNAPSHOT_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState

if TYPE_CHECKING:
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

__all__ = [
    "ReplayReadiness",
    "_build_replay_section",
    "_compute_replay_readiness",
    "_dedupe_strings",
    "_describe_replay_gaps",
    "_determine_strategy_hint",
    "_extract_context_payload",
    "_fingerprint_payload",
    "_path_get",
    "_recommended_action",
]


class ReplayReadiness(str, Enum):
    """Replay readiness public type."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    INCOMPLETE = "incomplete"


_REQUIRED_INPUT_KEYS: Final[frozenset[str]] = frozenset(
    {
        INPUT_TRINITY_BUNDLE_REF,
        INPUT_REGISTRY_BUNDLE_REF,
    }
)

_OPTIONAL_INPUT_KEYS: Final[frozenset[str]] = frozenset(
    {
        INPUT_INPUT_BINDINGS_REF,
        INPUT_NORM_PACK_REF,
        INPUT_KNOWLEDGE_BUNDLE_REF,
        INPUT_RESEARCH_INTENT_REF,
        ARTIFACT_ENVIRONMENT_MANIFEST_REF,
    }
)


def _compute_replay_readiness(inputs_section: dict[str, str | None]) -> ReplayReadiness:
    missing_required = [key for key in _REQUIRED_INPUT_KEYS if inputs_section.get(key) is None]
    has_snapshot = bool(
        inputs_section.get(INPUT_INPUT_BINDINGS_REF)
        or inputs_section.get(INPUT_DATA_SNAPSHOT_REF)
        or inputs_section.get(INPUT_STATE_SNAPSHOT_REF)
    )
    if missing_required or not has_snapshot:
        return ReplayReadiness.INCOMPLETE
    missing_optional = [key for key in _OPTIONAL_INPUT_KEYS if inputs_section.get(key) is None]
    if missing_optional:
        return ReplayReadiness.PARTIAL
    return ReplayReadiness.COMPLETE


def _build_replay_section(
    *,
    inputs_section: dict[str, str | None],
    artifacts_section: dict[str, str | None],
    readiness: ReplayReadiness,
    strategy_hint: str,
    seed: int,
    determinism_tier: object,
) -> dict[str, object]:
    missing_refs, why_partial, suggested_next_step = _describe_replay_gaps(inputs_section)
    return {
        "readiness": readiness.value,
        "strategy_hint": strategy_hint,
        "effective_seed": seed,
        "seed_source": "params.random_seed",
        "determinism_tier": determinism_tier if isinstance(determinism_tier, str) else None,
        "missing_refs": missing_refs,
        "why_partial": why_partial,
        "suggested_next_step": suggested_next_step,
        "fallback_from_decision_packet": False,
        "has_exec_plan_ref": artifacts_section.get(ARTIFACT_EXEC_PLAN_REF) is not None,
        "has_lowered_ir_ref": artifacts_section.get(ARTIFACT_LOWERED_IR_REF) is not None,
    }


def _describe_replay_gaps(
    inputs_section: dict[str, str | None],
) -> tuple[list[str], list[str], str | None]:
    missing_required = sorted(
        key for key in _REQUIRED_INPUT_KEYS if inputs_section.get(key) is None
    )
    missing_optional = sorted(
        key for key in _OPTIONAL_INPUT_KEYS if inputs_section.get(key) is None
    )
    has_snapshot = bool(
        inputs_section.get(INPUT_INPUT_BINDINGS_REF)
        or inputs_section.get(INPUT_DATA_SNAPSHOT_REF)
        or inputs_section.get(INPUT_STATE_SNAPSHOT_REF)
    )
    missing_refs = list(missing_required)
    why_partial: list[str] = []
    if not has_snapshot:
        missing_refs.append("state_source_ref")
        why_partial.append("missing_state_source")
    if missing_required:
        why_partial.append("missing_required_inputs")
    if missing_optional:
        why_partial.append("missing_optional_inputs")

    suggested: str | None
    if INPUT_INPUT_BINDINGS_REF in missing_optional:
        suggested = "Persist input_bindings_ref for replay-grade completeness."
    elif not has_snapshot:
        suggested = "Attach data_snapshot_ref, state_snapshot_ref, or input_bindings_ref."
    elif INPUT_NORM_PACK_REF in missing_optional:
        suggested = "Persist norm_pack_ref to make legal context replayable."
    elif missing_optional:
        suggested = "Persist the missing optional replay references listed in replay.missing_refs."
    elif missing_required:
        suggested = "Persist the missing required replay references listed in replay.missing_refs."
    else:
        suggested = None

    missing_refs.extend(missing_optional)
    return missing_refs, why_partial, suggested


def _determine_strategy_hint(
    inputs_section: dict[str, str | None],
    artifacts_section: dict[str, str | None],
) -> str:
    has_registry = inputs_section.get(INPUT_REGISTRY_BUNDLE_REF) is not None
    has_snapshot = bool(
        inputs_section.get(INPUT_DATA_SNAPSHOT_REF)
        or inputs_section.get(INPUT_INPUT_BINDINGS_REF)
        or inputs_section.get(INPUT_STATE_SNAPSHOT_REF)
        or artifacts_section.get(ARTIFACT_STATE_SNAPSHOT_REF)
    )
    has_exec_plan = artifacts_section.get(ARTIFACT_EXEC_PLAN_REF) is not None
    has_trinity = inputs_section.get(INPUT_TRINITY_BUNDLE_REF) is not None
    if has_exec_plan and has_registry and has_snapshot:
        return "foundry"
    if has_trinity and has_registry and has_snapshot:
        return "scientist"
    return "none"


def _extract_context_payload(state: ExperimentState, *keys: str) -> object | None:
    for key in keys:
        if key in state.params:
            return state.params.get(key)
    return None


def _fingerprint_payload(value: object) -> str | None:
    if value is None:
        return None
    return content_hash(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str))


def _path_get(payload: dict[str, object], path: tuple[str, ...]) -> object | None:
    current: object = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped


def _recommended_action(status: DecisionValidityStatus) -> str:
    if status == DecisionValidityStatus.ACTIVE:
        return "none"
    if status == DecisionValidityStatus.WARNING:
        return "monitor"
    if status == DecisionValidityStatus.STALE:
        return "refresh_decision"
    if status == DecisionValidityStatus.SUPERSEDED:
        return "review_superseded"
    if status == DecisionValidityStatus.REVOKED:
        return "record_revocation"
    return "human_review"


def _populate_optional_report_projections(
    ctx: ExecutionContext,
    state: ExperimentState,
    packet_payload: dict[str, object],
) -> None:
    """Load optional verification and policy-output reports into the packet."""

    from polisyos.core.contracts.scientist import (
        SourceVerificationReportRef,
        VerifiedPolicyReportRef,
    )
    from polisyos.scientist.nodes.builtins.decide.decision_packet.validation import (
        _DECISION_PACKET_LOAD_ERRORS,
        _decision_packet_degraded,
        _record_decision_packet_degraded,
    )
    from polisyos.scientist.nodes.builtins.state_keys import (
        ARTIFACT_POLICY_OUTPUT_BUNDLE_REF,
        ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
        ARTIFACT_VERIFIED_POLICY_REPORT_REF,
    )
    from polisyos.scientist.validation.policy_verified import (
        load_source_verification_report,
        load_verified_policy_report,
    )

    source_verification_ref = state.artifacts_index.get(ARTIFACT_SOURCE_VERIFICATION_REPORT_REF)
    if source_verification_ref is not None:
        try:
            report = load_source_verification_report(
                ctx.store,
                SourceVerificationReportRef.model_validate(source_verification_ref.model_dump()),
            )
            packet_payload["legal_verification"] = {
                "verified_claim_count": len(report.verified_claims),
                "citation_coverage_pct": report.verified_claim_citation_coverage_pct,
                "needs_expert_review": report.needs_expert_review,
                "verification_cycles_completed": report.verification_cycles_completed,
            }
            packet_payload["source_coverage"] = {
                "unresolved_critical_gaps": [
                    gap.model_dump(mode="json") for gap in report.unresolved_critical_gaps
                ],
                "verifier_calls_total": report.verifier_calls_total,
                "adjudicator_calls_total": report.adjudicator_calls_total,
                "verifier_disagreement_rate": report.verifier_disagreement_rate,
            }
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            _record_decision_packet_degraded(
                packet_payload,
                _decision_packet_degraded(
                    operation="load_source_verification_report",
                    reason="source_verification_report_load_failed",
                    exc=exc,
                    ref=source_verification_ref,
                    artifact_key=ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
                ),
            )

    verified_policy_ref = state.artifacts_index.get(ARTIFACT_VERIFIED_POLICY_REPORT_REF)
    if verified_policy_ref is not None:
        try:
            verified_report = load_verified_policy_report(
                ctx.store,
                VerifiedPolicyReportRef.model_validate(verified_policy_ref.model_dump()),
            )
            packet_payload["policy_answer"] = {
                "executive_summary": verified_report.executive_summary,
                "missing_evidence": list(verified_report.missing_evidence),
                "needs_expert_review": verified_report.needs_expert_review,
            }
            packet_payload["verified_findings"] = list(verified_report.verified_findings)
            packet_payload["hypotheses"] = list(verified_report.hypotheses)
            packet_payload["intervention_legal_basis_map"] = dict(
                verified_report.intervention_legal_basis_map
            )
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            _record_decision_packet_degraded(
                packet_payload,
                _decision_packet_degraded(
                    operation="load_verified_policy_report",
                    reason="verified_policy_report_load_failed",
                    exc=exc,
                    ref=verified_policy_ref,
                    artifact_key=ARTIFACT_VERIFIED_POLICY_REPORT_REF,
                ),
            )

    policy_bundle_ref = state.artifacts_index.get(ARTIFACT_POLICY_OUTPUT_BUNDLE_REF)
    if policy_bundle_ref is not None:
        try:
            from polisyos.scientist.policy_design.output import load_policy_artifact_bundle

            policy_bundle = load_policy_artifact_bundle(ctx.store, policy_bundle_ref)
            packet_payload["policy_output_bundle"] = {
                "bundle_ref": policy_bundle_ref.artifact_id,
                "policy_brief_ref": policy_bundle.policy_brief_ref.artifact_id,
                "champion_policy_dossier_ref": (
                    policy_bundle.champion_policy_dossier_ref.artifact_id
                ),
                "decision_readiness_contract_ref": (
                    policy_bundle.decision_readiness_contract_ref.artifact_id
                    if policy_bundle.decision_readiness_contract_ref is not None
                    else None
                ),
                "phase3_gate": policy_bundle.phase3_gate.model_dump(mode="json"),
            }
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            _record_decision_packet_degraded(
                packet_payload,
                _decision_packet_degraded(
                    operation="load_policy_output_bundle",
                    reason="policy_output_bundle_load_failed",
                    exc=exc,
                    ref=policy_bundle_ref,
                    artifact_key=ARTIFACT_POLICY_OUTPUT_BUNDLE_REF,
                ),
            )
