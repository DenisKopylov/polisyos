"""Replay and support helpers for decision-packet assembly."""

from __future__ import annotations

import json
from enum import Enum
from typing import Final

from polisyos.core.canon import content_hash
from polisyos.core.contracts.decision_validity import DecisionValidityStatus
from polisyos.scientist.engine.state import ExperimentState
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
