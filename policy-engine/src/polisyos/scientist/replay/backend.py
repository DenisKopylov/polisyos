"""Public scientist replay backend module API."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, cast

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts.environment import EnvironmentDiff, RiskLevel
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    ExecuteRequest,
    FoundryExecConfig,
    FoundryInputBindingsRef,
    SimulationResultRef,
)
from polisyos.foundry.execute import admit_execution_source
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
from polisyos.scientist.orchestration.engine.executor import (
    WorkflowExecutionResult,
    WorkflowExecutionStatus,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.workflows.builder import run_selected_workflow
from polisyos.scientist.replay.deterministic import (
    CompletenessLevel,
    CompletenessReport,
    ReplayStrategy,
    VerificationConfig,
    VerificationResult,
    _selected_replay_reference,
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
_DEAD_LETTER_SCHEMA_NAME = "polisyos.scientist.orchestration.engine.DeadLetter"


class DeadLetterError(RuntimeError):
    """Base error for scientist dead-letter inspection and replay."""


class DeadLetterNotFoundError(DeadLetterError):
    """Raised when a requested dead-letter artifact cannot be found."""


class DeadLetterCorruptedError(DeadLetterError):
    """Raised when a dead-letter artifact payload is malformed."""


@dataclass
class ReplayBackendResult:
    """Capture the outcome fields returned by a replay backend call.

    ``success`` is true when no replay errors were recorded, including plan, execution,
    or verification errors. Verification may be absent when disabled or when an earlier
    replay error prevents it from running; a skipped verification does not add an error.
    Therefore, ``success`` alone does not mean that verification ran or passed.

    Attributes:
        success: Whether the replay call recorded no errors.
        run_id: Identifier assigned to this replay attempt.
        strategy: Strategy selected for the replay attempt.
        original_packet_ref: String form of the source decision-packet reference.
        replay_decision_packet_ref: Optional produced decision-packet reference.
        replay_simulation_result_ref: Optional produced simulation-result reference.
        completeness: Completeness assessment for the source replay plan.
        verification: Optional verification result for the replayed output.
        environment_diffs: Differences found against the current environment.
        errors: Replay-planning, execution, or verification errors recorded by the
            backend.
        warnings: Non-fatal replay limitations and environment warnings.
        replay_artifact_refs: Produced artifact references keyed by output role.
    """

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
    replay_artifact_refs: dict[str, ArtifactRef] = field(default_factory=dict)


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
    dispatch_basis_status: Literal["selected", "not_established"] = "not_established"
    dispatch_basis_ref: ArtifactRef | None = None


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
    """Replay a decision packet using its planned or explicitly selected strategy.

    Builds a replay plan from the packet and its referenced artifacts, sets the
    process-wide random seeds from that plan, and executes the Foundry or Scientist
    path. When verification is enabled and execution records no errors, the replayed
    output is checked against the original payload and selected reference bindings.
    An incomplete plan returns a failed result without dispatching a replay. Execution
    and verification failures captured by the backend are returned in the result.

    Args:
        store: Artifact store containing the packet and its referenced inputs.
        packet_ref: Artifact identifier of the decision packet to replay.
        verify: Whether to verify a replayed output after execution.
        verification_config: Optional settings for replay verification; defaults to
            ``VerificationConfig()`` when omitted.
        force_strategy: Optional strategy that overrides the strategy in the replay
            plan.

    Returns:
        The replay outcome, including completeness, optional verification, artifact
        references, warnings, and recorded errors. A successful result does not imply
        that verification ran when it was disabled or skipped.
    """
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

    if plan.legacy_reference_roles:
        warnings.append(
            "legacy_payload_reference_profiles_not_established:"
            + ",".join(plan.legacy_reference_roles)
        )
    env_diffs = compare_current_environment(
        store, plan.payload, reference_bindings=plan.reference_bindings
    )
    for diff in env_diffs:
        if diff.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
            warnings.append(f"environment_mismatch:{diff.field_path}:{diff.risk_level.value}")

    set_global_seeds(plan.seed.value)
    replay_decision_packet_ref: ArtifactID | ArtifactRef | None = None
    replay_simulation_result_ref: ArtifactID | ArtifactRef | None = None
    try:
        if strategy == ReplayStrategy.FOUNDRY:
            request, source_limitations = _foundry_replay_request(
                store=store,
                payload=plan.payload,
                seed=plan.seed.value,
                reference_bindings=plan.reference_bindings or None,
            )
            warnings.extend(source_limitations)
            replay_simulation_result_ref = _execute_foundry_replay(
                store=store,
                request=request,
            )
        elif strategy == ReplayStrategy.SCIENTIST:
            scientist_result = _execute_scientist_replay(
                store=store,
                payload=plan.payload,
                run_id=run_id,
                seed=plan.seed.value,
                reference_bindings=plan.reference_bindings or None,
            )
            replay_decision_packet_ref = scientist_result.state.artifacts_index.get(
                ARTIFACT_DECISION_PACKET_REF
            )
            replay_simulation_result_ref = scientist_result.state.artifacts_index.get(
                ARTIFACT_SIMULATION_RESULT_REF
            )
            if scientist_result.report.status != WorkflowExecutionStatus.OK:
                errors.append(f"replay_scientist_execution_status:{scientist_result.report.status}")
            if replay_decision_packet_ref is None and replay_simulation_result_ref is None:
                errors.append("replay_scientist_output_missing")
        else:
            errors.append("strategy_unresolved")
    except Exception as exc:
        errors.append(f"replay_execution_failed:{type(exc).__name__}:{exc}")

    verification = None
    if verify and not errors:
        try:
            verification = verify_replay(
                store,
                original_payload=plan.payload,
                replay_simulation_ref=replay_simulation_result_ref,
                config=config,
                original_reference_bindings=plan.reference_bindings,
            )
            if not verification.passed and not verification.skipped:
                errors.append("verification_failed")
        except (OSError, TypeError, ValueError, RuntimeError) as exc:
            errors.append(f"replay_verification_failed:{type(exc).__name__}:{exc}")

    replay_refs = {
        role: ref
        for role, ref in (
            ("decision_packet", replay_decision_packet_ref),
            ("simulation_result", replay_simulation_result_ref),
        )
        if isinstance(ref, ArtifactRef)
    }
    warnings.extend(
        f"replay_output_profile_not_established:{role}"
        for role, ref in replay_refs.items()
        if ref.manifest_profile_sha256 is None
    )

    return ReplayBackendResult(
        success=len(errors) == 0,
        run_id=run_id,
        strategy=strategy,
        original_packet_ref=str(packet_ref),
        replay_decision_packet_ref=(
            str(_replay_artifact_id(replay_decision_packet_ref))
            if replay_decision_packet_ref
            else None
        ),
        replay_simulation_result_ref=(
            str(_replay_artifact_id(replay_simulation_result_ref))
            if replay_simulation_result_ref
            else None
        ),
        completeness=plan.completeness,
        verification=verification,
        environment_diffs=env_diffs,
        errors=errors,
        warnings=warnings,
        replay_artifact_refs=replay_refs,
    )


def _replay_artifact_id(ref: ArtifactID | ArtifactRef) -> ArtifactID:
    return ref.artifact_id if isinstance(ref, ArtifactRef) else ref


def load_dead_letter(
    store: ArtifactStore,
    artifact_id: ArtifactID,
) -> DeadLetterRecord:
    """Load one persisted dead-letter artifact."""
    from polisyos.core.artifacts import load_core_json_artifact

    try:
        manifest = store.get_manifest(artifact_id)
    except FileNotFoundError as exc:
        raise DeadLetterNotFoundError(f"dead-letter artifact {artifact_id} was not found") from exc

    if manifest.kind != "scientist.dead_letter":
        raise DeadLetterCorruptedError(
            f"artifact {artifact_id} is not a scientist.dead_letter payload",
        )

    try:
        payload = load_core_json_artifact(store, artifact_id)
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

    schema = manifest.artifact_schema
    dispatch_basis_status: Literal["selected", "not_established"] = "not_established"
    dispatch_basis_ref: ArtifactRef | None = None
    if schema is not None:
        if schema.name != _DEAD_LETTER_SCHEMA_NAME or schema.version not in {"1.0", "2.0"}:
            raise DeadLetterCorruptedError(
                f"dead-letter artifact {artifact_id} has an unsupported schema",
            )
        if schema.version == "2.0":
            raw_status = payload.get("dispatch_basis_status")
            raw_ref = payload.get("dispatch_basis_ref")
            if raw_status == "selected":
                try:
                    dispatch_basis_ref = ArtifactRef.model_validate(raw_ref)
                except Exception as exc:
                    raise DeadLetterCorruptedError(
                        f"dead-letter artifact {artifact_id} has an invalid dispatch basis ref",
                    ) from exc
                if (
                    dispatch_basis_ref.kind != "core.run_invocation_attempt"
                    or dispatch_basis_ref.media_type != "application/json"
                    or dispatch_basis_ref.manifest_profile_sha256 is None
                ):
                    raise DeadLetterCorruptedError(
                        f"dead-letter artifact {artifact_id} has an incomplete dispatch basis ref",
                    )
                expected_input = input_ref_from_artifact_ref(
                    dispatch_basis_ref,
                    role="dispatch_basis",
                )
                if manifest.inputs != [expected_input]:
                    raise DeadLetterCorruptedError(
                        f"dead-letter artifact {artifact_id} dispatch basis lineage does not match",
                    )
                dispatch_basis_status = "selected"
            elif raw_status == "not_established" and raw_ref is None and not manifest.inputs:
                dispatch_basis_status = "not_established"
            else:
                raise DeadLetterCorruptedError(
                    f"dead-letter artifact {artifact_id} has inconsistent dispatch basis fields",
                )

    return DeadLetterRecord(
        artifact_ref=ArtifactRef(
            artifact_id=artifact_id,
            kind=manifest.kind,
            media_type=manifest.media_type,
            manifest_profile_sha256=artifact_manifest_profile_sha256(manifest),
        ),
        run_id=str(payload.get("run_id") or ""),
        alias=str(payload.get("alias") or ""),
        node_id=str(payload.get("node_id") or ""),
        error_type=str(payload.get("error_type") or "unknown"),
        error_message=str(payload.get("error_message") or ""),
        attempts=max(1, int(payload.get("attempts", 1) or 1)),
        policy=dict(payload.get("policy") or {}),
        created_at=created_at.astimezone(UTC),
        dispatch_basis_status=dispatch_basis_status,
        dispatch_basis_ref=dispatch_basis_ref,
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


def _dead_letter_dispatch_params(
    ctx: Any, record: DeadLetterRecord, *, state: ExperimentState
) -> dict[str, object]:
    """Resolve the exact owner-linked workflow invocation for one dead letter."""
    basis_ref = record.dispatch_basis_ref
    if record.dispatch_basis_status != "selected" or basis_ref is None:
        raise DeadLetterError("dead_letter_dispatch_basis_not_established")
    try:
        verification = ctx.store.verify(record.artifact_ref)
        if not verification.ok:
            raise DeadLetterError("dead_letter_current_access_verification_failed")
        run_id = ctx.run.run_manifest.run_id
        if run_id != record.run_id or state.run_id != record.run_id:
            raise DeadLetterError("dead_letter_dispatch_run_mismatch")
        attempts = ctx.run.read_runtime_invocation_attempts()
    except DeadLetterError:
        raise
    except Exception as exc:
        raise DeadLetterError("dead_letter_dispatch_basis_not_established") from exc

    matches = [
        attempt
        for attempt in attempts
        if artifact_ref_identity_key(attempt.basis_ref) == artifact_ref_identity_key(basis_ref)
    ]
    if len(matches) != 1:
        raise DeadLetterError("dead_letter_dispatch_basis_not_established")
    attempt = matches[0]
    basis = attempt.basis
    if (
        basis.run_id != record.run_id
        or basis.node_alias != record.alias
        or basis.component_id != record.node_id
        or attempt.outcome is None
        or attempt.outcome.status != "unknown"
    ):
        raise DeadLetterError("dead_letter_dispatch_basis_mismatch")
    try:
        from polisyos.scientist.orchestration.engine.producer_currentness import (
            _workflow_invocation_params,
        )

        return _workflow_invocation_params(ctx, basis)
    except Exception as exc:
        raise DeadLetterError("dead_letter_dispatch_basis_unavailable") from exc


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
    """Replay only from the selected owner-linked workflow invocation."""
    from polisyos.scientist.orchestration.engine.retry import (
        RetryPolicy,
        execute_with_retry_async,
    )

    record = load_dead_letter(store, artifact_id)
    dispatch_params = _dead_letter_dispatch_params(ctx, record, state=state)

    resolved_node = node
    if resolved_node is None:
        if registry is None:
            raise DeadLetterError("registry or node must be provided for dead-letter replay")
        resolved_node = registry.get(record.node_id)

    node_spec = getattr(resolved_node, "spec", None)
    node_component_id = str(getattr(getattr(node_spec, "metadata", None), "component_id", ""))
    if node_component_id != record.node_id:
        raise DeadLetterError("dead_letter_replay_node_binding_mismatch")
    from polisyos.scientist.orchestration.engine.executor import bind_node_params

    resolved_node = bind_node_params(resolved_node, dict(dispatch_params))
    rebound_spec = getattr(resolved_node, "spec", None)
    rebound_component_id = str(getattr(getattr(rebound_spec, "metadata", None), "component_id", ""))
    if rebound_component_id != record.node_id:
        raise DeadLetterError("dead_letter_replay_node_binding_mismatch")

    from polisyos.scientist.orchestration.engine.skg_snapshot import (
        SNAPSHOT_INPUT_KEY,
        bind_retained_skg_workflow_input,
    )

    if SNAPSHOT_INPUT_KEY in state.inputs:
        from polisyos.common import async_tools as common_async_tools

        state = await common_async_tools.run_blocking_async(
            bind_retained_skg_workflow_input,
            ctx,
            state,
            unbounded=True,
        )

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
        alias=record.alias,
        dispatch_params=dispatch_params,
    )


def _foundry_replay_request(
    *,
    store: ArtifactStore,
    payload: dict[str, Any],
    seed: int,
    reference_bindings: Mapping[str, ArtifactRef] | None = None,
) -> tuple[ExecuteRequest, list[str]]:
    """Reuse stronger original source admission or retain explicit candidate replay."""
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
        exec_plan_ref=ExecPlanRef.model_validate(
            _replay_input_ref(
                reference_bindings, "artifact.exec_plan_ref", exec_plan_id, "foundry.exec_plan"
            ).model_dump(mode="python")
        ),
        input_bindings_ref=FoundryInputBindingsRef.model_validate(
            _replay_input_ref(
                reference_bindings,
                "input.input_bindings_ref",
                input_bindings_id,
                "foundry.input_bindings",
            ).model_dump(mode="python")
        ),
        registry_bundle_ref=_replay_input_ref(
            reference_bindings, "input.registry_bundle_ref", registry_id, "core.registry_bundle"
        ),
        exec_config=FoundryExecConfig(schema_version="1.0", seed=seed, capture_env=True),
    )
    original_result = (reference_bindings or {}).get("artifact.simulation_result_ref")
    if original_result is None:
        return request, ["original_execution_source_not_established:legacy_candidate"]
    admitted = admit_execution_source(
        store,
        SimulationResultRef.model_validate(original_result.model_dump(mode="python")),
    )
    if admitted.mode == "legacy_profileless":
        return request, ["original_execution_source_not_established:legacy_candidate"]
    if admitted.mode != "single_step_basis" or admitted.basis is None:
        raise ValueError("replay_execution_source_uncomposed")
    original_request = admitted.basis.request
    for expected, recorded in (
        (request.exec_plan_ref, original_request.exec_plan_ref),
        (request.input_bindings_ref, original_request.input_bindings_ref),
        (request.registry_bundle_ref, original_request.registry_bundle_ref),
    ):
        if (
            expected is None
            or recorded is None
            or artifact_ref_identity_key(expected) != artifact_ref_identity_key(recorded)
        ):
            raise ValueError("replay_packet_execution_source_binding_mismatch")
    if seed != admitted.basis.effective_seed:
        raise ValueError("replay_seed_disagrees_with_execution_source")
    replay_request = original_request.model_copy(deep=True)
    replay_request.exec_config = FoundryExecConfig.model_construct(
        _fields_set=set(admitted.basis.request_exec_config_fields_set),
        **original_request.exec_config.model_dump(mode="python"),
    )
    return replay_request, []


def _execute_foundry_replay(
    *,
    store: ArtifactStore,
    request: ExecuteRequest,
) -> ArtifactRef:
    result = execute_foundry(
        _require_filesystem_store(store, operation="scientist.replay_backend.execute_foundry"),
        request,
    )
    if not result.ok or result.simulation_result_ref is None:
        raise RuntimeError(f"Foundry replay failed: {result.notes}")
    return result.simulation_result_ref


def _execute_scientist_replay(
    *,
    store: ArtifactStore,
    payload: dict[str, Any],
    run_id: str,
    seed: int,
    reference_bindings: Mapping[str, ArtifactRef] | None = None,
) -> WorkflowExecutionResult:
    state_inputs = _build_replay_state_inputs(payload, reference_bindings=reference_bindings)
    state = ExperimentState(
        schema_version="1.0",
        run_id=run_id,
        inputs=state_inputs,
        params={"random_seed": seed, "replay_mode": True},
    )
    return run_selected_workflow(state, store=store, foundry=DefaultFoundryPort())


def _build_replay_state_inputs(
    payload: dict[str, Any],
    *,
    reference_bindings: Mapping[str, ArtifactRef] | None = None,
) -> dict[str, ArtifactRef]:
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
        state_inputs[key] = _replay_input_ref(
            reference_bindings, f"input.{key}", artifact_id, kind, media_type=media_type
        )
    return state_inputs


def _replay_input_ref(
    bindings: Mapping[str, ArtifactRef] | None,
    role: str,
    artifact_id: ArtifactID,
    kind: str,
    *,
    media_type: str = "application/json",
) -> ArtifactRef:
    """Preserve one admitted selected view; only the declared legacy path lacks one."""
    if bindings is not None and role not in bindings:
        raise ValueError(f"replay_input_binding_mismatch:{role}")
    selected = _selected_replay_reference(bindings, role, artifact_id)
    if isinstance(selected, ArtifactRef):
        return selected
    return ArtifactRef(artifact_id=artifact_id, kind=kind, media_type=media_type)


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
