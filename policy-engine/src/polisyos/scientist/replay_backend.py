from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from polisyos.core.artifacts.environment import EnvironmentDiff, RiskLevel
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import ExecuteRequest, ExecPlanRef, FoundryExecConfig, StateSnapshotRef
from polisyos.foundry.execute import execute as execute_foundry
from polisyos.runtime.replay import (
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
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.foundry import DefaultFoundryPort
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DECISION_PACKET_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_KNOWLEDGE_BUNDLE_REF,
    INPUT_NORM_PACK_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_RESEARCH_INTENT_REF,
    INPUT_STATE_SNAPSHOT_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.workflows.builder import run_default_workflow


@dataclass
class ReplayBackendResult:
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


def replay_packet(
    store: FileSystemCAS,
    packet_ref: ArtifactID,
    *,
    verify: bool = True,
    verification_config: VerificationConfig | None = None,
    force_strategy: ReplayStrategy | None = None,
) -> ReplayBackendResult:
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
            warnings.append(
                f"environment_mismatch:{diff.field_path}:{diff.risk_level.value}"
            )

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
        replay_decision_packet_ref=str(replay_decision_packet_ref) if replay_decision_packet_ref else None,
        replay_simulation_result_ref=str(replay_simulation_result_ref) if replay_simulation_result_ref else None,
        completeness=plan.completeness,
        verification=verification,
        environment_diffs=env_diffs,
        errors=errors,
        warnings=warnings,
    )


def _execute_foundry_replay(
    *,
    store: FileSystemCAS,
    payload: dict[str, Any],
    seed: int,
) -> ArtifactID:
    inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), dict) else {}

    exec_plan_id = try_parse_artifact_id(artifacts.get("exec_plan_ref"))
    if exec_plan_id is None:
        raise ValueError("Missing artifacts.exec_plan_ref")
    registry_id = try_parse_artifact_id(inputs.get("registry_bundle_ref"))
    if registry_id is None:
        raise ValueError("Missing inputs.registry_bundle_ref")

    data_snapshot_id = try_parse_artifact_id(inputs.get("data_snapshot_ref"))
    state_snapshot_id = try_parse_artifact_id(inputs.get("state_snapshot_ref"))
    if state_snapshot_id is None:
        state_snapshot_id = try_parse_artifact_id(artifacts.get("state_snapshot_ref"))

    request = ExecuteRequest(
        exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_id),
        data_snapshot_ref=(
            ArtifactRef(
                artifact_id=data_snapshot_id,
                kind="fabric.data_snapshot",
                media_type="application/json",
            )
            if data_snapshot_id is not None
            else None
        ),
        state_snapshot_ref=(
            StateSnapshotRef(artifact_id=state_snapshot_id)
            if state_snapshot_id is not None
            else None
        ),
        registry_bundle_ref=ArtifactRef(
            artifact_id=registry_id,
            kind="core.registry_bundle",
            media_type="application/json",
        ),
        exec_config=FoundryExecConfig(seed=seed, capture_env=True),
    )
    result = execute_foundry(store, request)
    if not result.ok or result.simulation_result_ref is None:
        raise RuntimeError(f"Foundry replay failed: {result.notes}")
    return result.simulation_result_ref.artifact_id


def _execute_scientist_replay(
    *,
    store: FileSystemCAS,
    payload: dict[str, Any],
    run_id: str,
    seed: int,
) -> tuple[ArtifactID | None, ArtifactID | None]:
    state_inputs = _build_replay_state_inputs(payload)
    state = ExperimentState(
        run_id=run_id,
        inputs=state_inputs,
        params={"random_seed": seed, "replay_mode": True},
    )
    result = run_default_workflow(state, store=store, foundry=DefaultFoundryPort())
    decision_packet = result.state.artifacts_index.get(ARTIFACT_DECISION_PACKET_REF)
    simulation_result = result.state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
    return (
        decision_packet.artifact_id if decision_packet is not None else None,
        simulation_result.artifact_id if simulation_result is not None else None,
    )


def _build_replay_state_inputs(payload: dict[str, Any]) -> dict[str, ArtifactRef]:
    inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}
    mapping: dict[str, tuple[str, str]] = {
        INPUT_TRINITY_BUNDLE_REF: ("ir.trinity_bundle", "application/json"),
        INPUT_REGISTRY_BUNDLE_REF: ("core.registry_bundle", "application/json"),
        INPUT_DATA_SNAPSHOT_REF: ("fabric.data_snapshot", "application/json"),
        INPUT_STATE_SNAPSHOT_REF: ("foundry.state_snapshot", "application/json"),
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
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"replay_{ts}"


__all__ = ["ReplayBackendResult", "replay_packet"]
