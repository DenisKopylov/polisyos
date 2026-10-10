"""Human-gate request context and replay-summary construction."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.registry import RegistryBundlePayload
from polisyos.core.canon.canon_json import from_canonical_bytes
from polisyos.core.canon.hashing import content_hash
from polisyos.core.contracts import (
    DataSnapshot,
    DataSnapshotRef,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    Metrics,
    ResearchIntent,
    ResearchIntentRef,
    StateSnapshot,
    StateSnapshotRef,
    TrinityBundleRef,
)
from polisyos.core.registry import load_registry_bundle_content
from polisyos.ir import ArtifactRefModel, NormPack, TrinityBundle
from polisyos.ir.governance.gate import (
    GATE_REQUEST_SCHEMA_VERSION,
    GateContext,
    GatePriority,
    GateRequest,
)
from polisyos.scholar import KnowledgeBundlePayloadV1
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_METRICS_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_INPUT_BINDINGS_REF,
    INPUT_KNOWLEDGE_BUNDLE_REF,
    INPUT_NORM_PACK_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_RESEARCH_INTENT_REF,
    INPUT_STATE_SNAPSHOT_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_CHANGE_PROPOSAL_REF,
    REPORT_LEGAL_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.engine.protocol import NodeEvent
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.kernel.gate_protocol import HumanGateProtocol

logger = get_logger("polisyos.scientist.nodes.builtins.governance.run_governance")

_GOVERNANCE_HELPER_ERRORS = (
    AttributeError,
    KeyError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)


@dataclass(frozen=True)
class _ReplayArtifactContract:
    """Describe the persisted format used by one replay input."""

    kind: str
    ref_model: type[ArtifactRef]
    payload_model: type[BaseModel]
    schema: tuple[str, str] | None
    legacy_schemas: frozenset[tuple[str, str] | None] = frozenset()
    payload_schema_versions: dict[str, str] | None = None


@dataclass(frozen=True)
class _GateRequestSpec:
    """Carry the current request fields used for persistence and cache admission."""

    reason: str
    context: GateContext
    priority: GatePriority
    timeout_seconds: int | None
    requested_by: str = "scientist.node_run_governance"


_REPLAY_INPUT_CONTRACTS: dict[str, _ReplayArtifactContract] = {
    INPUT_TRINITY_BUNDLE_REF: _ReplayArtifactContract(
        kind="ir.trinity_bundle",
        ref_model=TrinityBundleRef,
        payload_model=TrinityBundle,
        schema=("polisyos.ir.TrinityBundle", "1.0"),
    ),
    INPUT_REGISTRY_BUNDLE_REF: _ReplayArtifactContract(
        kind="core.registry_bundle",
        ref_model=ArtifactRef,
        payload_model=RegistryBundlePayload,
        # build_registry_bundle() currently persists this typed payload without
        # artifact_schema metadata; do not invent a schema version here.
        schema=None,
    ),
    INPUT_DATA_SNAPSHOT_REF: _ReplayArtifactContract(
        kind="fabric.data_snapshot",
        ref_model=DataSnapshotRef,
        payload_model=DataSnapshot,
        schema=("polisyos.core.DataSnapshot", "0.2.0"),
        # Existing Foundry quickstart and Ukraine source builders omit the
        # manifest schema while writing the typed DataSnapshot payload.
        legacy_schemas=frozenset({None}),
    ),
    INPUT_STATE_SNAPSHOT_REF: _ReplayArtifactContract(
        kind="foundry.state_snapshot",
        ref_model=StateSnapshotRef,
        payload_model=StateSnapshot,
        schema=None,
        payload_schema_versions={"2.0": "1.0", "2.1": "2.1.0", "2.2": "2.2.0"},
    ),
    INPUT_INPUT_BINDINGS_REF: _ReplayArtifactContract(
        kind="foundry.input_bindings",
        ref_model=FoundryInputBindingsRef,
        payload_model=FoundryInputBindings,
        schema=("polisyos.core.FoundryInputBindings", "1.0"),
        # prepare_trivial_input_bindings() is an existing producer that omits
        # the manifest schema while retaining the typed payload schema_version.
        legacy_schemas=frozenset({None}),
    ),
    INPUT_NORM_PACK_REF: _ReplayArtifactContract(
        kind="lex.norm_pack",
        ref_model=ArtifactRef,
        payload_model=NormPack,
        schema=("polisyos.ir.NormPack", "1.0"),
    ),
    INPUT_KNOWLEDGE_BUNDLE_REF: _ReplayArtifactContract(
        kind="scholar.knowledge_bundle",
        ref_model=ArtifactRef,
        payload_model=KnowledgeBundlePayloadV1,
        schema=("polisyos.scholar.KnowledgeBundlePayloadV1", "1.0"),
    ),
    INPUT_RESEARCH_INTENT_REF: _ReplayArtifactContract(
        kind="scholar.research_intent",
        ref_model=ResearchIntentRef,
        payload_model=ResearchIntent,
        # ResearchIntent is a strict typed payload but has no schema_version
        # field or in-repo persisted writer; do not attest a made-up manifest ABI.
        schema=None,
    ),
}
_REPLAY_INPUT_KEYS_BY_KIND = {
    contract.kind: key for key, contract in _REPLAY_INPUT_CONTRACTS.items()
}


def _create_gate_request(
    *,
    ctx: ExecutionContext,
    protocol: HumanGateProtocol,
    state: ExperimentState,
) -> tuple[GateRequest, ArtifactRef | None]:
    spec = _gate_request_spec(ctx=ctx, state=state)
    return _persist_gate_request(protocol=protocol, state=state, spec=spec)


def _gate_request_spec(*, ctx: ExecutionContext, state: ExperimentState) -> _GateRequestSpec:
    iteration = _as_int(state.params.get("gate_iteration"))
    is_escalated = bool(state.params.get("gate_escalated"))
    phase = str(state.params.get("phase", "POSTFLIGHT_GOV"))
    governance_profile_raw = state.params.get("governance_profile")
    governance_profile = (
        str(governance_profile_raw) if isinstance(governance_profile_raw, str) else None
    )
    timeout_seconds = _optional_int(state.params.get("gate_timeout_seconds"))

    context = _build_gate_context(
        ctx=ctx,
        state=state,
        phase=phase,
        iteration=iteration,
        governance_profile=governance_profile,
        is_escalated=is_escalated,
        risk_indicators=[],
        issue_summary=None,
    )
    priority = GatePriority.CRITICAL if is_escalated else GatePriority.NORMAL
    return _GateRequestSpec(
        reason="governance_profile_requires_approval",
        context=context,
        priority=priority,
        timeout_seconds=timeout_seconds,
    )


def _persist_gate_request(
    *,
    protocol: HumanGateProtocol,
    state: ExperimentState,
    spec: _GateRequestSpec,
) -> tuple[GateRequest, ArtifactRef | None]:
    return protocol.request_gate(
        run_id=state.run_id,
        reason=spec.reason,
        context=spec.context,
        priority=spec.priority,
        timeout_seconds=spec.timeout_seconds,
        requested_by=spec.requested_by,
    )


def _ensure_human_review_gate_request(
    *,
    ctx: ExecutionContext,
    protocol: HumanGateProtocol,
    state: ExperimentState,
    pass_state: dict[str, Any],
    events: list[NodeEvent],
) -> None:
    payload = pass_state.get("human_review_request")
    items: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        raw_items = payload.get("items")
        if isinstance(raw_items, list):
            items = [item for item in raw_items if isinstance(item, dict)]

    spec = _human_review_gate_request_spec(
        ctx=ctx,
        state=state,
        review_items=items,
    )
    if (
        _resolve_cached_gate_request(
            ctx=ctx,
            protocol=protocol,
            state=state,
            raw_request=state.params.get("human_review_request"),
            raw_ref=state.params.get("human_review_request_ref"),
            spec=spec,
        )
        is not None
    ):
        return

    request, request_ref = _persist_gate_request(protocol=protocol, state=state, spec=spec)
    state.params["human_review_request"] = request.model_dump(mode="json")
    if request_ref is None:
        raise RuntimeError("HumanGateProtocol did not return a persisted gate request reference")
    state.params["human_review_request_ref"] = _serialize_gate_request_ref(request_ref)
    events.append(
        NodeEvent(
            level="info",
            message=f"Human review request created: {request.request_id}",
        )
    )


def _create_human_review_gate_request(
    *,
    ctx: ExecutionContext,
    protocol: HumanGateProtocol,
    state: ExperimentState,
    review_items: list[dict[str, Any]],
) -> tuple[GateRequest, ArtifactRef]:
    spec = _human_review_gate_request_spec(ctx=ctx, state=state, review_items=review_items)
    request, request_ref = _persist_gate_request(protocol=protocol, state=state, spec=spec)
    if request_ref is None:
        raise RuntimeError("HumanGateProtocol did not return a persisted gate request reference")
    return request, request_ref


def _human_review_gate_request_spec(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    review_items: list[dict[str, Any]],
) -> _GateRequestSpec:
    governance_profile_raw = state.params.get("governance_profile")
    governance_profile = (
        str(governance_profile_raw) if isinstance(governance_profile_raw, str) else None
    )
    timeout_seconds = _optional_int(state.params.get("human_review_timeout_seconds"))
    if timeout_seconds is None:
        timeout_seconds = 72 * 3600

    risk_indicators: list[str] = []
    for item in review_items:
        kind = item.get("kind")
        if kind is not None:
            risk_indicators.append(str(kind))

    issue_summary = {
        "requested_items": len(review_items),
        "risk_indicator_count": len(sorted(set(risk_indicators))),
    }
    context = _build_gate_context(
        ctx=ctx,
        state=state,
        phase=str(state.params.get("human_review_phase", "POSTFLIGHT_GOV_REVIEW")),
        iteration=_as_int(state.params.get("human_review_iteration")),
        governance_profile=governance_profile,
        is_escalated=bool(state.params.get("gate_escalated")),
        risk_indicators=sorted(set(risk_indicators)),
        issue_summary=issue_summary,
    )
    reason = _human_review_reason(ctx=ctx, state=state, review_items=review_items)
    return _GateRequestSpec(
        reason=reason,
        context=context,
        priority=GatePriority.HIGH,
        timeout_seconds=timeout_seconds,
    )


def _build_gate_context(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    phase: str,
    iteration: int,
    governance_profile: str | None,
    is_escalated: bool,
    risk_indicators: list[str],
    issue_summary: dict[str, int] | None,
) -> GateContext:
    return GateContext(
        workflow_id=str(state.params.get("workflow_id", "scientist_default")),
        node_alias="run_governance",
        phase=phase,
        governance_profile=governance_profile,
        iteration=iteration,
        is_escalated=is_escalated,
        policy_summary=_policy_summary_from_state(ctx, state),
        simulation_results=_simulation_results_from_state(ctx, state),
        risk_indicators=risk_indicators,
        issue_summary=issue_summary,
        artifact_refs=_collect_gate_artifact_refs(state),
        selected_replay_refs=_collect_gate_selected_replay_refs(state),
        transport_summary=_transport_summary_from_state(ctx, state),
        replay_summary=_gate_replay_summary(ctx, state),
    )


def _policy_summary_from_state(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> str | None:
    trinity_ref = state.inputs.get(INPUT_TRINITY_BUNDLE_REF)
    if trinity_ref is None:
        return None
    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(trinity_ref))
    except _GOVERNANCE_HELPER_ERRORS as exc:
        emit_degraded_path(
            component="scientist.run_governance",
            operation="policy_summary_from_state",
            reason="trinity_bundle_load_failed",
            exc=exc,
            details={"run_id": state.run_id},
            log=logger,
            metrics=ctx.metrics,
        )
        return None
    if not isinstance(payload, dict):
        return None
    policy_spec = payload.get("policy_spec")
    if not isinstance(policy_spec, dict):
        return "Policy data attached"
    interventions = policy_spec.get("interventions")
    if isinstance(interventions, list):
        return f"Policy with {len(interventions)} intervention(s)"
    return "Policy data attached"


def _simulation_results_from_state(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> dict[str, Any] | None:
    metrics_ref = state.artifacts_index.get(ARTIFACT_METRICS_REF)
    if metrics_ref is None:
        return None
    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(metrics_ref))
        metrics = Metrics.model_validate(payload)
    except _GOVERNANCE_HELPER_ERRORS as exc:
        emit_degraded_path(
            component="scientist.run_governance",
            operation="simulation_results_from_state",
            reason="metrics_preview_load_failed",
            exc=exc,
            details={"run_id": state.run_id},
            log=logger,
            metrics=ctx.metrics,
        )
        return None

    preview: dict[str, Any] = {}
    for key in sorted(metrics.values)[:5]:
        preview[key] = metrics.values[key]
    return preview or None


def _collect_gate_artifact_refs(state: ExperimentState) -> dict[str, str] | None:
    refs: dict[str, str] = {}
    for key in (
        INPUT_TRINITY_BUNDLE_REF,
        INPUT_DATA_SNAPSHOT_REF,
        ARTIFACT_METRICS_REF,
        ARTIFACT_CAUSAL_REPORT_REF,
        ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
        REPORT_LEGAL_REPORT_REF,
        REPORT_CHANGE_PROPOSAL_REF,
    ):
        ref = (
            state.inputs.get(key) or state.artifacts_index.get(key) or state.reports_index.get(key)
        )
        if ref is not None:
            artifact_id = getattr(ref, "artifact_id", None)
            if artifact_id is None:
                continue
            try:
                refs[key] = str(ArtifactID.model_validate(artifact_id))
            except _GOVERNANCE_HELPER_ERRORS:
                continue
    return refs or None


def _collect_gate_selected_replay_refs(
    state: ExperimentState,
) -> dict[str, ArtifactRefModel]:
    """Retain each typed input's complete selected-view reference."""
    selected: dict[str, ArtifactRefModel] = {}
    for key, raw_ref in state.inputs.items():
        try:
            if isinstance(raw_ref, ArtifactRef):
                payload: Any = raw_ref.model_dump(mode="json")
            elif isinstance(raw_ref, Mapping):
                payload = dict(raw_ref)
            else:
                raise TypeError("input is not an artifact reference")
            selected[key] = ArtifactRefModel.model_validate(payload)
        except _GOVERNANCE_HELPER_ERRORS as exc:
            # Replay inputs have an independent completeness record that carries
            # malformed-present refs as invalid_refs. Keep request creation
            # available so the gate can expose that typed limitation; any other
            # malformed state input cannot be represented by the typed binding.
            if key in _REPLAY_INPUT_CONTRACTS:
                continue
            raise ValueError(f"Malformed gate input reference for {key!r}") from exc
    return selected


def _transport_summary_from_state(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> dict[str, Any] | None:
    report_ref = state.artifacts_index.get(ARTIFACT_CAUSAL_REPORT_REF)
    if report_ref is None:
        status = state.params.get("transportability_status")
        mode = state.params.get("transportability_transport_mode")
        engine = state.params.get("transportability_identification_engine")
        capability_hash = state.params.get("transportability_capability_hash")
        degradation_policy = state.params.get("transportability_degradation_policy")
        if isinstance(status, str) or isinstance(engine, str):
            return {
                "status": status if isinstance(status, str) else "not_available",
                "transport_mode": mode if isinstance(mode, str) else "not_available",
                "identification_engine": engine if isinstance(engine, str) else "not_available",
                "capability_hash": capability_hash if isinstance(capability_hash, str) else None,
                "degradation_policy": (
                    degradation_policy if isinstance(degradation_policy, str) else None
                ),
            }
        return None

    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(report_ref))
    except _GOVERNANCE_HELPER_ERRORS as exc:
        emit_degraded_path(
            component="scientist.run_governance",
            operation="transport_summary_from_state",
            reason="causal_report_load_failed",
            exc=exc,
            details={"run_id": state.run_id},
            log=logger,
            metrics=ctx.metrics,
        )
        return None
    if not isinstance(payload, dict):
        return None
    transport = payload.get("transport_result")
    if not isinstance(transport, dict):
        return None
    summary = {
        "status": transport.get("status"),
        "transport_mode": transport.get("transport_mode"),
        "identification_engine": transport.get("identification_engine"),
        "capability_hash": state.params.get("transportability_capability_hash"),
        "degradation_policy": state.params.get("transportability_degradation_policy"),
        "requires_expert_review": bool(transport.get("requires_expert_review", False)),
        "data_gaps_count": len(transport.get("data_gaps", []))
        if isinstance(transport.get("data_gaps"), list)
        else 0,
        "unsupported_cases": list(transport.get("unsupported_cases", []))
        if isinstance(transport.get("unsupported_cases"), list)
        else [],
        "hard_legal_constraints": list(transport.get("hard_legal_constraints", []))
        if isinstance(transport.get("hard_legal_constraints"), list)
        else [],
    }
    return summary


def _gate_replay_summary(ctx: ExecutionContext, state: ExperimentState) -> dict[str, Any]:
    readiness, missing_refs, invalid_refs = _gate_replay_readiness(ctx, state)
    summary: dict[str, Any] = {
        "readiness": readiness,
        "missing_refs": missing_refs,
        "invalid_refs": invalid_refs,
        "why_partial": _replay_partial_reasons(readiness, missing_refs, invalid_refs),
        "suggested_next_step": _replay_suggested_next_step(missing_refs, invalid_refs),
        "determinism_tier": (
            state.params.get("determinism_tier")
            if isinstance(state.params.get("determinism_tier"), str)
            else None
        ),
        "seed_source": "params.random_seed"
        if isinstance(state.params.get("random_seed"), (int, float, str))
        else None,
    }
    if invalid_refs:
        summary["invalid_input_digests"] = _invalid_replay_input_digests(state, invalid_refs)
    return summary


def _invalid_replay_input_digests(
    state: ExperimentState,
    invalid_refs: Mapping[str, str],
) -> dict[str, str]:
    """Bind each invalid-present replay input's exact canonical value to the request."""
    digests: dict[str, str] = {}
    for key in sorted(invalid_refs):
        if key not in state.inputs:
            raise ValueError(f"Invalid replay input {key!r} is not present in workflow state")
        try:
            identity = {
                "scope": "polisyos.ir.GateRequest.invalid_replay_input",
                "schema_version": GATE_REQUEST_SCHEMA_VERSION,
                "canonicalization": "json-sorted-keys-v1",
                "input_key": key,
                "raw_value": _canonical_json_value(state.inputs[key]),
            }
            canonical = json.dumps(
                identity,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            digests[key] = content_hash(canonical, prefix=True)
        except _GOVERNANCE_HELPER_ERRORS as exc:
            raise ValueError(
                f"Cannot bind invalid replay input {key!r} to the gate request identity"
            ) from exc
    return digests


def _canonical_json_value(
    value: object,
    *,
    depth: int = 0,
    ancestors: frozenset[int] = frozenset(),
) -> object:
    """Return a JSON-only value, refusing cycles and implicit type coercions."""
    if depth > 128:
        raise ValueError("Invalid replay input exceeds the canonical JSON depth limit")
    if isinstance(value, BaseModel):
        return _canonical_json_value(
            value.model_dump(mode="json", by_alias=True, exclude_none=False),
            depth=depth + 1,
            ancestors=ancestors,
        )
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Non-finite numbers cannot identify an invalid replay input")
        return value
    if isinstance(value, Mapping):
        return _canonical_json_mapping(value, depth=depth, ancestors=ancestors)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray, memoryview)):
        return _canonical_json_sequence(value, depth=depth, ancestors=ancestors)
    raise TypeError(f"Unsupported invalid replay input value: {type(value).__name__}")


def _canonical_json_mapping(
    value: Mapping[object, object],
    *,
    depth: int,
    ancestors: frozenset[int],
) -> dict[str, object]:
    """Normalize a JSON object while requiring string keys and acyclic values."""
    identity = id(value)
    if identity in ancestors:
        raise ValueError("Cyclic values cannot identify an invalid replay input")
    child_ancestors = ancestors | {identity}
    normalized: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError("Invalid replay input JSON object keys must be strings")
        normalized[key] = _canonical_json_value(
            item,
            depth=depth + 1,
            ancestors=child_ancestors,
        )
    return normalized


def _canonical_json_sequence(
    value: Sequence[object],
    *,
    depth: int,
    ancestors: frozenset[int],
) -> list[object]:
    """Normalize a JSON array while refusing cycles."""
    identity = id(value)
    if identity in ancestors:
        raise ValueError("Cyclic values cannot identify an invalid replay input")
    child_ancestors = ancestors | {identity}
    return [
        _canonical_json_value(item, depth=depth + 1, ancestors=child_ancestors) for item in value
    ]


def _replay_partial_reasons(
    readiness: str,
    missing_refs: list[str],
    invalid_refs: dict[str, str],
) -> list[str]:
    reasons: list[str] = []
    if readiness == "partial":
        if invalid_refs:
            reasons.append("invalid_replay_inputs")
        if missing_refs:
            reasons.append("missing_optional_inputs")
    elif readiness == "incomplete":
        if "state_source_ref" in missing_refs:
            reasons.append("missing_state_source")
        if any(key in missing_refs for key in ("trinity_bundle_ref", "registry_bundle_ref")):
            reasons.append("missing_required_inputs")
        if invalid_refs:
            reasons.append("invalid_replay_inputs")
    return reasons


def _replay_suggested_next_step(
    missing_refs: list[str], invalid_refs: dict[str, str]
) -> str | None:
    if invalid_refs:
        return "Repair the invalid replay refs listed in replay_summary.invalid_refs."
    if "input_bindings_ref" in missing_refs:
        return "Persist input_bindings_ref for replay-grade completeness."
    if "state_source_ref" in missing_refs:
        return "Attach data_snapshot_ref, state_snapshot_ref, or input_bindings_ref."
    if missing_refs:
        return "Persist the missing replay refs listed in replay_summary.missing_refs."
    return None


def _gate_replay_readiness(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> tuple[str, list[str], dict[str, str]]:
    """Resolve replay refs by their selected persisted view and typed payload."""
    required_keys = (INPUT_TRINITY_BUNDLE_REF, INPUT_REGISTRY_BUNDLE_REF)
    snapshot_keys = (
        INPUT_INPUT_BINDINGS_REF,
        INPUT_DATA_SNAPSHOT_REF,
        INPUT_STATE_SNAPSHOT_REF,
    )
    optional_keys = (
        INPUT_INPUT_BINDINGS_REF,
        INPUT_NORM_PACK_REF,
        INPUT_KNOWLEDGE_BUNDLE_REF,
        INPUT_RESEARCH_INTENT_REF,
    )
    required_missing, required_invalid, _ = _resolve_replay_keys(ctx, state, required_keys)
    _, snapshot_invalid, resolved_snapshots = _resolve_replay_keys(
        ctx, state, snapshot_keys, include_missing=False
    )
    optional_missing, optional_invalid, _ = _resolve_replay_keys(
        ctx,
        state,
        optional_keys,
        already_checked=resolved_snapshots | set(snapshot_invalid),
    )

    missing_refs = list(required_missing)
    if not resolved_snapshots:
        missing_refs.append("state_source_ref")
    missing_refs.extend(optional_missing)
    invalid_refs = {**required_invalid, **snapshot_invalid, **optional_invalid}
    if required_missing or required_invalid or not resolved_snapshots:
        return "incomplete", missing_refs, invalid_refs
    if missing_refs or invalid_refs:
        return "partial", missing_refs, invalid_refs
    return "complete", missing_refs, invalid_refs


def _resolve_replay_keys(
    ctx: ExecutionContext,
    state: ExperimentState,
    keys: tuple[str, ...],
    *,
    include_missing: bool = True,
    already_checked: set[str] | None = None,
) -> tuple[list[str], dict[str, str], set[str]]:
    missing: list[str] = []
    invalid: dict[str, str] = {}
    resolved: set[str] = set()
    for key in keys:
        if already_checked is not None and key in already_checked:
            continue
        if key not in state.inputs:
            if include_missing:
                missing.append(key)
            continue
        reason = _resolve_replay_input(ctx, key, state.inputs[key], seen=set())
        if reason is None:
            resolved.add(key)
        else:
            invalid[key] = reason
    return missing, invalid, resolved


def _resolve_replay_input(
    ctx: ExecutionContext,
    key: str,
    raw_ref: Any,
    *,
    seen: set[tuple[str, str | None, str]],
) -> str | None:
    """Validate one replay artifact and recursively resolve typed replay members."""
    contract = _REPLAY_INPUT_CONTRACTS[key]
    ref, reason = _normalize_replay_ref(contract, raw_ref)
    if reason is not None:
        return reason
    assert ref is not None
    identity = (str(ref.artifact_id), ref.manifest_profile_sha256, ref.kind)
    if identity in seen:
        return None
    seen.add(identity)

    payload, reason = _read_replay_payload(ctx, contract, ref)
    if reason is not None:
        return reason
    assert payload is not None
    return _resolve_nested_replay_refs(ctx, payload, seen=seen)


def _normalize_replay_ref(
    contract: _ReplayArtifactContract,
    raw_ref: Any,
) -> tuple[ArtifactRef | None, str | None]:
    try:
        if isinstance(raw_ref, ArtifactRef):
            ref_payload: Any = raw_ref.model_dump(mode="python")
        elif isinstance(raw_ref, Mapping):
            ref_payload = dict(raw_ref)
        else:
            return None, "malformed_ref"
        ref = contract.ref_model.model_validate(ref_payload)
    except _GOVERNANCE_HELPER_ERRORS:
        return None, "malformed_ref"
    if ref.kind != contract.kind or ref.media_type != "application/json":
        return None, "wrong_kind"
    return ref, None


def _read_replay_payload(
    ctx: ExecutionContext,
    contract: _ReplayArtifactContract,
    ref: ArtifactRef,
) -> tuple[BaseModel | None, str | None]:
    try:
        manifest = ctx.store.get_manifest(ref)
        payload = contract.payload_model.model_validate(
            from_canonical_bytes(ctx.store.get_bytes(ref))
        )
    except _GOVERNANCE_HELPER_ERRORS:
        return None, "unresolvable_ref_or_invalid_payload"
    if not _replay_schema_matches(contract, manifest.artifact_schema, payload):
        return None, "wrong_schema"
    if isinstance(payload, RegistryBundlePayload):
        try:
            # Existing Core loader resolves each member registry by its exact
            # typed ref and validates its actual content model.
            load_registry_bundle_content(ctx.store, ref)
        except _GOVERNANCE_HELPER_ERRORS:
            return None, "invalid_bundle_content"
    return payload, None


def _resolve_nested_replay_refs(
    ctx: ExecutionContext,
    payload: BaseModel,
    *,
    seen: set[tuple[str, str | None, str]],
) -> str | None:
    for nested_ref in _nested_artifact_refs(payload):
        nested_key = _REPLAY_INPUT_KEYS_BY_KIND.get(nested_ref.kind)
        if nested_key is None:
            try:
                if not ctx.store.verify(nested_ref).ok:
                    return "unavailable_nested_ref"
            except _GOVERNANCE_HELPER_ERRORS:
                return "unavailable_nested_ref"
            continue
        nested_reason = _resolve_replay_input(
            ctx,
            nested_key,
            nested_ref,
            seen=seen,
        )
        if nested_reason is not None:
            return nested_reason
    return None


def _replay_schema_matches(
    contract: _ReplayArtifactContract,
    actual_schema: Any,
    payload: BaseModel,
) -> bool:
    if contract.payload_schema_versions is not None:
        payload_version = getattr(payload, "schema_version", None)
        manifest_version = contract.payload_schema_versions.get(payload_version)
        if manifest_version is None:
            return False
        expected_schema = ("polisyos.core.StateSnapshot", manifest_version)
    else:
        expected_schema = contract.schema
    actual = (actual_schema.name, actual_schema.version) if actual_schema is not None else None
    return actual == expected_schema or actual in contract.legacy_schemas


def _nested_artifact_refs(value: Any) -> list[ArtifactRef]:
    """Return every typed CAS ref embedded in a validated replay payload."""
    if isinstance(value, ArtifactRef):
        return [value]
    if isinstance(value, BaseModel):
        return [
            ref
            for field_name in type(value).model_fields
            for ref in _nested_artifact_refs(getattr(value, field_name))
        ]
    if isinstance(value, Mapping):
        return [ref for item in value.values() for ref in _nested_artifact_refs(item)]
    if isinstance(value, (list, tuple, set)):
        return [ref for item in value for ref in _nested_artifact_refs(item)]
    return []


def _human_review_reason(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    review_items: list[dict[str, Any]],
) -> str:
    transport = _transport_summary_from_state(ctx, state)
    if isinstance(transport, dict) and transport.get("requires_expert_review") is True:
        return "expert_review_required_for_transportability"
    if review_items:
        return "strict_human_review"
    return "governance_human_review_required"


def _parse_gate_request(raw: Any) -> GateRequest | None:
    if isinstance(raw, GateRequest):
        return raw if "schema_version" in raw.model_fields_set else None
    if isinstance(raw, Mapping):
        if "schema_version" not in raw:
            return None
        try:
            return GateRequest.model_validate(dict(raw))
        except _GOVERNANCE_HELPER_ERRORS:
            return None
    return None


def _resolve_cached_gate_request(
    *,
    ctx: ExecutionContext,
    protocol: HumanGateProtocol,
    state: ExperimentState,
    raw_request: Any,
    raw_ref: Any,
    spec: _GateRequestSpec,
) -> tuple[GateRequest, ArtifactRef] | None:
    """Admit a cached request only when its persisted body matches current state."""
    request = _parse_gate_request(raw_request)
    ref = _parse_gate_request_ref(raw_ref)
    if request is None or ref is None:
        return None
    try:
        manifest = ctx.store.get_manifest(ref)
        if manifest.kind != "ir.gate_request":
            return None
        persisted_payload = from_canonical_bytes(ctx.store.get_bytes(ref))
        persisted = _parse_gate_request(persisted_payload)
        if persisted is None:
            return None
        expected_schema = SchemaInfo(
            name="polisyos.ir.GateRequest",
            version=persisted.schema_version,
        )
        if manifest.artifact_schema != expected_schema:
            return None
    except _GOVERNANCE_HELPER_ERRORS:
        return None

    # Historical 1.1 requests remain readable, but cannot authorize a new
    # decision because they lack the selected-view binding. A current request
    # ref must also remain typed in state so a non-default profile is not lost.
    if (
        request.schema_version != GATE_REQUEST_SCHEMA_VERSION
        or persisted.schema_version != GATE_REQUEST_SCHEMA_VERSION
        or persisted.context.selected_replay_refs is None
        or not isinstance(raw_ref, (ArtifactRef, Mapping))
    ):
        return None

    expected_request_id = protocol._generate_deterministic_request_id(
        run_id=state.run_id,
        reason=spec.reason,
        context=spec.context,
        priority=spec.priority,
        timeout_seconds=spec.timeout_seconds,
        requested_by=spec.requested_by,
    )
    if (
        persisted != request
        or persisted.request_id != expected_request_id
        or persisted.run_id != state.run_id
        or persisted.reason != spec.reason
        or persisted.context != spec.context
        or persisted.priority != spec.priority
        or persisted.timeout_seconds != spec.timeout_seconds
        or persisted.requested_by != spec.requested_by
    ):
        return None
    return persisted, ref


def _parse_gate_request_ref(raw: Any) -> ArtifactRef | None:
    if isinstance(raw, ArtifactRef):
        ref = raw
    elif isinstance(raw, Mapping):
        try:
            ref = ArtifactRef.model_validate(dict(raw))
        except _GOVERNANCE_HELPER_ERRORS:
            return None
    elif isinstance(raw, str):
        try:
            artifact_id = ArtifactID.model_validate(raw)
        except _GOVERNANCE_HELPER_ERRORS:
            return None
        ref = ArtifactRef(
            artifact_id=artifact_id,
            kind="ir.gate_request",
            media_type="application/json",
        )
    else:
        return None
    if ref.kind != "ir.gate_request" or ref.media_type != "application/json":
        return None
    return ref


def _serialize_gate_request_ref(ref: ArtifactRef) -> dict[str, Any]:
    """Persist the full CAS-returned request view in node state."""
    return ref.model_dump(mode="json")


def _as_int(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 1
    return value if value >= 1 else 1


def _optional_int(raw: Any) -> int | None:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None
