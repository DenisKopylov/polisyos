"""Public scientist replay backend module API."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from polisyos.core.artifacts.environment import EnvironmentDiff, RiskLevel
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    ExecuteRequest,
    FoundryExecConfig,
    FoundryInputBindingsRef,
)
from polisyos.foundry.execute import execute as execute_foundry
from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DECISION_PACKET_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
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
from polisyos.scientist.orchestration.workflows.builder import run_selected_workflow
from polisyos.scientist.replay.deterministic import (
    CompletenessLevel,
    CompletenessReport,
    ReplayStrategy,
    VerificationConfig,
    VerificationResult,
    build_replay_plan,
    compare_current_environment,
    set_global_seeds,
    try_parse_artifact_id,
    verify_replay,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.artifacts.protocol import ArtifactStore

logger = logging.getLogger(__name__)


class DeadLetterError(RuntimeError):
    """Base error for scientist dead-letter inspection and replay."""


class DeadLetterNotFoundError(DeadLetterError):
    """Raised when a requested dead-letter artifact cannot be found."""


class DeadLetterCorruptedError(DeadLetterError):
    """Raised when a dead-letter artifact payload is malformed."""


@dataclass
class ReplayBackendResult:
    """Replay backend result data model."""

    success: bool
    run_id: str
    strategy: ReplayStrategy
    original_packet_ref: str
    replay_decision_packet_ref: str | None = None
    replay_simulation_result_ref: str | None = None
    completeness: CompletenessReport | None = None
    verification: VerificationResult | None = None
    environment_diffs: list[EnvironmentDiff] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DeadLetterRecord:
    """Typed view over one persisted scientist dead-letter artifact."""

    artifact_ref: ArtifactRef
    run_id: str
    alias: str
    node_id: str
    error_type: str
    error_message: str
    attempts: int
    policy: dict[str, Any]
    created_at: datetime


def _artifact_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return cast("Mapping[str, Any]", value)
    return {}


def _require_filesystem_store(store: ArtifactStore, *, operation: str) -> FileSystemCAS:
    if isinstance(store, FileSystemCAS):
        return store
    raise DeadLetterError(
        f"{operation} requires a filesystem-backed artifact store for the current Foundry path"
    )


def replay_packet(
    store: ArtifactStore,
    packet_ref: ArtifactID,
    *,
    verify: bool = True,
    verification_config: VerificationConfig | None = None,
    force_strategy: ReplayStrategy | None = None,
) -> ReplayBackendResult:
    """Replay packet helper."""
    config = verification_config or VerificationConfig()
    plan = build_replay_plan(store, packet_ref)
    strategy = force_strategy or plan.strategy
    run_id = _new_replay_run_id()
    warnings: list[str] = []
    errors: list[str] = []

    if plan.completeness.level == CompletenessLevel.INCOMPLETE:
        return ReplayBackendResult(
            success=False,
            run_id=run_id,
            strategy=strategy,
            original_packet_ref=str(packet_ref),
            completeness=plan.completeness,
            errors=[plan.completeness.summary()],
        )

    env_diffs = compare_current_environment(store, plan.payload)
    for diff in env_diffs:
        if diff.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
            warnings.append(f"environment_mismatch:{diff.field_path}:{diff.risk_level.value}")

    set_global_seeds(plan.seed.value)
    replay_decision_packet_ref: ArtifactID | None = None
    replay_simulation_result_ref: ArtifactID | None = None
    try:
        if strategy == ReplayStrategy.FOUNDRY:
            replay_simulation_result_ref = _execute_foundry_replay(
                store=store,
                payload=plan.payload,
                seed=plan.seed.value,
            )
        elif strategy == ReplayStrategy.SCIENTIST:
            replay_decision_packet_ref, replay_simulation_result_ref = _execute_scientist_replay(
                store=store,
                payload=plan.payload,
                run_id=run_id,
                seed=plan.seed.value,
            )
        else:
            errors.append("strategy_unresolved")
    except Exception as exc:
        errors.append(f"replay_execution_failed:{type(exc).__name__}:{exc}")

    verification = None
    if verify and not errors:
        verification = verify_replay(
            store,
            original_payload=plan.payload,
            replay_simulation_ref=replay_simulation_result_ref,
            config=config,
        )
        if not verification.passed:
            errors.append("verification_failed")

    return ReplayBackendResult(
        success=len(errors) == 0,
        run_id=run_id,
        strategy=strategy,
        original_packet_ref=str(packet_ref),
        replay_decision_packet_ref=(
            str(replay_decision_packet_ref) if replay_decision_packet_ref else None
        ),
        replay_simulation_result_ref=(
            str(replay_simulation_result_ref) if replay_simulation_result_ref else None
        ),
        completeness=plan.completeness,
        verification=verification,
        environment_diffs=env_diffs,
        errors=errors,
        warnings=warnings,
    )


def load_dead_letter(
    store: ArtifactStore,
    artifact_id: ArtifactID,
) -> DeadLetterRecord:
    """Load one persisted dead-letter artifact."""
    try:
        manifest = store.get_manifest(artifact_id)
    except FileNotFoundError as exc:
        raise DeadLetterNotFoundError(f"dead-letter artifact {artifact_id} was not found") from exc

    if manifest.kind != "scientist.dead_letter":
        raise DeadLetterCorruptedError(
            f"artifact {artifact_id} is not a scientist.dead_letter payload",
        )

    try:
        payload = from_canonical_bytes(store.get_bytes(artifact_id))
    except Exception as exc:
        raise DeadLetterCorruptedError(
            f"dead-letter artifact {artifact_id} could not be decoded",
        ) from exc

    if not isinstance(payload, dict):
        raise DeadLetterCorruptedError(
            f"dead-letter artifact {artifact_id} must decode to a JSON object",
        )

    created_at_raw = payload.get("created_at")
    try:
        created_at = datetime.fromisoformat(str(created_at_raw).replace("Z", "+00:00"))
    except ValueError as exc:
        raise DeadLetterCorruptedError(
            f"dead-letter artifact {artifact_id} has invalid created_at={created_at_raw!r}",
        ) from exc

    return DeadLetterRecord(
        artifact_ref=ArtifactRef(
            artifact_id=artifact_id,
            kind=manifest.kind,
            media_type=manifest.media_type,
        ),
        run_id=str(payload.get("run_id") or ""),
        alias=str(payload.get("alias") or ""),
        node_id=str(payload.get("node_id") or ""),
        error_type=str(payload.get("error_type") or "unknown"),
        error_message=str(payload.get("error_message") or ""),
        attempts=max(1, int(payload.get("attempts", 1) or 1)),
        policy=dict(payload.get("policy") or {}),
        created_at=created_at.astimezone(UTC),
    )


def list_dead_letters(
    store: ArtifactStore,
    *,
    run_id: str | None = None,
    alias: str | None = None,
    node_id: str | None = None,
    limit: int = 100,
) -> list[DeadLetterRecord]:
    """List persisted scientist dead-letter artifacts with optional filters."""
    matches: list[DeadLetterRecord] = []
    for artifact_id in store.iter_artifact_ids():
        try:
            manifest = store.get_manifest(artifact_id)
        except Exception as exc:
            logger.debug("Skipping dead-letter manifest lookup for %s: %s", artifact_id, exc)
            continue
        if manifest.kind != "scientist.dead_letter":
            continue
        try:
            record = load_dead_letter(store, artifact_id)
        except DeadLetterError:
            continue
        if run_id is not None and record.run_id != run_id:
            continue
        if alias is not None and record.alias != alias:
            continue
        if node_id is not None and record.node_id != node_id:
            continue
        matches.append(record)

    matches.sort(key=lambda item: item.created_at, reverse=True)
    return matches[: max(1, int(limit))]


async def replay_dead_letter(
    store: ArtifactStore,
    artifact_id: ArtifactID,
    *,
    ctx: Any,
    state: ExperimentState,
    registry: Any | None = None,
    node: Any | None = None,
    timeout_s: float | None = None,
    max_retries: int | None = None,
) -> Any:
    """Replay a dead-lettered node with caller-supplied execution context/state."""
    from polisyos.scientist.orchestration.engine.retry import RetryPolicy, execute_with_retry_async

    record = load_dead_letter(store, artifact_id)
    resolved_node = node
    if resolved_node is None:
        if registry is None:
            raise DeadLetterError("registry or node must be provided for dead-letter replay")
        resolved_node = registry.get(record.node_id)

    retry_policy = RetryPolicy.model_validate(record.policy or {})
    if max_retries is not None:
        retry_policy = retry_policy.model_copy(
            update={"max_retries": max(0, int(max_retries))},
        )

    effective_timeout = timeout_s
    if effective_timeout is None:
        policy_timeout = record.policy.get("timeout_s")
        if isinstance(policy_timeout, (int, float)):
            effective_timeout = float(policy_timeout)

    return await execute_with_retry_async(
        resolved_node,
        ctx,
        state,
        retry_policy=retry_policy,
        timeout_s=effective_timeout,
        alias=record.alias or str(record.node_id),
    )


def _execute_foundry_replay(
    *,
    store: ArtifactStore,
    payload: dict[str, Any],
    seed: int,
) -> ArtifactID:
    inputs = _artifact_mapping(payload.get("inputs"))
    artifacts = _artifact_mapping(payload.get("artifacts"))

    exec_plan_id = try_parse_artifact_id(artifacts.get("exec_plan_ref"))
    if exec_plan_id is None:
        raise ValueError("Missing artifacts.exec_plan_ref")
    registry_id = try_parse_artifact_id(inputs.get("registry_bundle_ref"))
    if registry_id is None:
        raise ValueError("Missing inputs.registry_bundle_ref")

    input_bindings_id = try_parse_artifact_id(inputs.get("input_bindings_ref"))
    if input_bindings_id is None:
        raise ValueError("Missing inputs.input_bindings_ref")

    request = ExecuteRequest(
        schema_version="1.0",
        exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_id),
        input_bindings_ref=FoundryInputBindingsRef(artifact_id=input_bindings_id),
        registry_bundle_ref=ArtifactRef(
            artifact_id=registry_id,
            kind="core.registry_bundle",
            media_type="application/json",
        ),
        exec_config=FoundryExecConfig(schema_version="1.0", seed=seed, capture_env=True),
    )
    result = execute_foundry(
        _require_filesystem_store(store, operation="scientist.replay_backend.execute_foundry"),
        request,
    )
    if not result.ok or result.simulation_result_ref is None:
        raise RuntimeError(f"Foundry replay failed: {result.notes}")
    return result.simulation_result_ref.artifact_id


def _execute_scientist_replay(
    *,
    store: ArtifactStore,
    payload: dict[str, Any],
    run_id: str,
    seed: int,
) -> tuple[ArtifactID | None, ArtifactID | None]:
    state_inputs = _build_replay_state_inputs(payload)
    state = ExperimentState(
        schema_version="1.0",
        run_id=run_id,
        inputs=state_inputs,
        params={"random_seed": seed, "replay_mode": True},
    )
    result = run_selected_workflow(state, store=store, foundry=DefaultFoundryPort())
    decision_packet = result.state.artifacts_index.get(ARTIFACT_DECISION_PACKET_REF)
    simulation_result = result.state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
    return (
        decision_packet.artifact_id if decision_packet is not None else None,
        simulation_result.artifact_id if simulation_result is not None else None,
    )


def _build_replay_state_inputs(payload: dict[str, Any]) -> dict[str, ArtifactRef]:
    inputs = _artifact_mapping(payload.get("inputs"))
    mapping: dict[str, tuple[str, str]] = {
        INPUT_TRINITY_BUNDLE_REF: ("ir.trinity_bundle", "application/json"),
        INPUT_REGISTRY_BUNDLE_REF: ("core.registry_bundle", "application/json"),
        INPUT_DATA_SNAPSHOT_REF: ("fabric.data_snapshot", "application/json"),
        INPUT_STATE_SNAPSHOT_REF: ("foundry.state_snapshot", "application/json"),
        INPUT_INPUT_BINDINGS_REF: ("foundry.input_bindings", "application/json"),
        INPUT_NORM_PACK_REF: ("lex.norm_pack", "application/json"),
        INPUT_KNOWLEDGE_BUNDLE_REF: ("scholar.knowledge_bundle", "application/json"),
        INPUT_RESEARCH_INTENT_REF: ("scholar.research_intent", "application/json"),
    }
    state_inputs: dict[str, ArtifactRef] = {}
    for key, (kind, media_type) in mapping.items():
        artifact_id = try_parse_artifact_id(inputs.get(key))
        if artifact_id is None:
            continue
        state_inputs[key] = ArtifactRef(
            artifact_id=artifact_id,
            kind=kind,
            media_type=media_type,
        )
    return state_inputs


def _new_replay_run_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"replay_{ts}"


__all__ = [
    "DeadLetterCorruptedError",
    "DeadLetterError",
    "DeadLetterNotFoundError",
    "DeadLetterRecord",
    "ReplayBackendResult",
    "list_dead_letters",
    "load_dead_letter",
    "replay_dead_letter",
    "replay_packet",
]
