"""Persist the source-selected producer basis for a candidate N5 replay.

These artifacts and the unsigned producer statement grant no replay authority.
"""

from __future__ import annotations

import fcntl
import json
import os
import signal
import subprocess
import time
import uuid
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Self

import psutil
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts, security
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.runtime.quality.n5_replay_appointment import (
    N5BlindReplayLaunchSpecV2,
    N5OriginalProducerSeal,
    N5OriginalProducerSealV2,
    N5ReplayDeploymentConfig,
    N5ReplayNumericalIntentV2,
    N5ReplayScope,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from polisyos.core.artifacts import CoreJSONArtifactStore
    from polisyos.runtime.quality.acquisition_route_loop import VerifiedAcquisitionRouteClosure
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationRequest,
        JointSimulationResult,
        PreparedJointSimulationConfiguration,
    )
    from polisyos.runtime.quality.n5_candidate_content import (
        CandidateN5ContentObservation,
        CandidateN5ContentRun,
    )
    from polisyos.runtime.quality.n5_replay_appointment import (
        N5ReplayAppointmentResolver,
        N5ReplayUseQuery,
    )
    from polisyos.scientist.orchestration.engine import (
        BudgetLedgerSnapshot,
        BudgetMiddleware,
        N5DiagnosticCapacityObservation,
        ProducerBudgetObserver,
    )


class N5ReplayProducerBasis(BaseModel):
    """Unsigned candidate statement and its source-selected result."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    statement: N5OriginalProducerSealV2 | N5OriginalProducerSeal
    original_result_ref: artifacts.ArtifactRef
    projection_document_ref: artifacts.ArtifactRef
    protected_use_allowed: Literal[False] = False


class N5BlindReplayAction(BaseModel):
    """Action-only child input; it contains no original result or projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["policyos.n5_replay.child_action.v1"] = (
        "policyos.n5_replay.child_action.v1"
    )
    launch_spec: N5BlindReplayLaunchSpecV2
    demonstration_trust: N5ReplayDeploymentConfig
    component_provenance_ref: artifacts.ArtifactRef
    cas_root: str = Field(min_length=1)
    diagnostic_ledger_path: str = Field(min_length=1)
    quota_units: int = Field(ge=1, strict=True)
    attempt_number: int = Field(ge=1, strict=True)
    diagnostic_limit_usd: Decimal = Field(default=Decimal(0), ge=0, le=0)
    demonstration_only: Literal[True] = True


def _blind_action_bytes(action: N5BlindReplayAction) -> bytes:
    """Canonicalize the action actually consumed by the child."""
    return to_canonical_bytes(
        action.model_dump(mode="json"),
        CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False),
    )


def _read_blind_action(
    store: CoreJSONArtifactStore, ref: artifacts.ArtifactRef, expected_hash: str
) -> N5BlindReplayAction:
    """Reopen exact candidate action bytes without an original result reference."""
    if (
        ref.kind != "runtime.quality.n5_blind_replay_action"
        or ref.media_type != "application/json"
        or ref.manifest_profile_sha256 is None
        or str(ref.artifact_id) != expected_hash
    ):
        raise ValueError("n5_replay_action_ref_invalid")
    manifest, _ = artifacts.read_core_manifest_profile(store, ref)
    if (
        manifest.artifact_schema is None
        or manifest.artifact_schema.name != "policyos.n5_replay.child_action.v1"
        or manifest.artifact_schema.version != "1.0"
        or not store.verify(ref).ok
    ):
        raise ValueError("n5_replay_action_schema_invalid")
    raw = store.get_bytes(ref)
    if security.raw_content_hash(raw) != expected_hash:
        raise ValueError("n5_replay_action_hash_mismatch")
    payload = artifacts.load_core_json_artifact(store, ref, raw_payload_bytes=raw)
    action = N5BlindReplayAction.model_validate(payload)
    if _blind_action_bytes(action) != raw:
        raise ValueError("n5_replay_action_content_mismatch")
    return action


class N5OriginalProducerAction(BaseModel):
    """Candidate source input and a distinct bounded original-producer job."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["policyos.runtime.n5_replay.original_producer_action.v1"] = (
        "policyos.runtime.n5_replay.original_producer_action.v1"
    )
    authority_purpose: Literal["candidate_original_n5_only"] = "candidate_original_n5_only"
    source_input_ref: artifacts.ArtifactRef
    source_run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    producer_run_id: str = Field(min_length=1)
    producer_job_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    cas_root: str = Field(min_length=1)
    ledger_path: str = Field(min_length=1)
    quota_units: int = Field(ge=1, strict=True)

    @model_validator(mode="after")
    def _distinct_source_and_producer(self) -> Self:
        if (
            self.source_run_id == self.producer_run_id
            or self.source_job_id == self.producer_job_id
            or self.source_input_ref.kind != "runtime.quality.candidate_simulation_n5_input"
            or self.source_input_ref.media_type != "application/json"
            or self.source_input_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("n5_original_source_producer_scope_invalid")
        return self


class N5OriginalProducerExecution(BaseModel):
    """Parent-only actual original execution; never included in child action."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["policyos.n5_replay.original_execution.v1"] = (
        "policyos.n5_replay.original_execution.v1"
    )
    authority_purpose: Literal["candidate_original_n5_only"] = "candidate_original_n5_only"
    source_input_ref: artifacts.ArtifactRef
    source_run_id: str
    source_job_id: str
    producer_run_id: str
    producer_job_id: str
    tenant_id: str
    cell_id: str
    pid: int = Field(gt=0)
    action_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    action_ref: artifacts.ArtifactRef
    result_ref: artifacts.ArtifactRef
    numerical_intent_ref: artifacts.ArtifactRef
    execution_profile_ref: artifacts.ArtifactRef
    ledger_owner: tuple[str, str, str]
    ledger_revision: int = Field(ge=0)
    ledger_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    ledger_snapshot_ref: artifacts.ArtifactRef
    operation_ids: tuple[str, ...] = Field(min_length=1)
    budget_admission: Literal["diagnostic_invocation_only"] = "diagnostic_invocation_only"
    usd_cost_status: Literal["not_established"] = "not_established"
    declared_closure: Literal["not_established"] = "not_established"
    protected_use_allowed: Literal[False] = False

    @model_validator(mode="after")
    def _execution_scope(self) -> Self:
        if (
            self.source_run_id == self.producer_run_id
            or self.source_job_id == self.producer_job_id
            or self.source_input_ref.kind != "runtime.quality.candidate_simulation_n5_input"
            or self.source_input_ref.media_type != "application/json"
            or self.source_input_ref.manifest_profile_sha256 is None
            or self.result_ref.kind != "polisyos.runtime.joint_simulation_result"
            or self.result_ref.media_type != "application/json"
            or self.result_ref.manifest_profile_sha256 is None
            or self.numerical_intent_ref.kind != "runtime.quality.n5_replay_numerical_intent"
            or self.numerical_intent_ref.media_type != "application/json"
            or self.numerical_intent_ref.manifest_profile_sha256 is None
            or self.execution_profile_ref.kind != "runtime.quality.n5_execution_profile"
            or self.execution_profile_ref.media_type != "application/json"
            or self.execution_profile_ref.manifest_profile_sha256 is None
            or self.ledger_snapshot_ref.kind != "runtime.quality.n5_diagnostic_ledger_snapshot"
            or self.ledger_snapshot_ref.media_type != "application/octet-stream"
            or self.ledger_snapshot_ref.manifest_profile_sha256 is None
            or self.action_ref.kind != "runtime.quality.n5_original_producer_action"
            or self.action_ref.media_type != "application/json"
            or self.action_ref.manifest_profile_sha256 is None
            or len(set(self.operation_ids)) != len(self.operation_ids)
        ):
            raise ValueError("n5_original_execution_scope_invalid")
        return self


class N5OriginalProducerOutcome(BaseModel):
    """Candidate original execution and its persisted parent-only artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    execution: N5OriginalProducerExecution
    execution_ref: artifacts.ArtifactRef


def _read_original_action(
    store: CoreJSONArtifactStore, ref: artifacts.ArtifactRef, expected_hash: str
) -> N5OriginalProducerAction:
    """Verify exact selected Core bytes before adapting the original action."""
    from polisyos.runtime.quality.n5_replay_appointment import _read_n5_versioned_core_json

    action, raw = _read_n5_versioned_core_json(
        store,
        ref,
        N5OriginalProducerAction,
        kind="runtime.quality.n5_original_producer_action",
        schema_name="policyos.runtime.n5_replay.original_producer_action.v1",
        schema_version="1.0",
    )
    if security.raw_content_hash(raw) != expected_hash:
        raise ValueError("n5_original_action_hash_mismatch")
    return action


class N5ReplayNativePreflightAction(BaseModel):
    """Source-only input to the assigned no-kernel launcher."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    launch_spec: N5BlindReplayLaunchSpecV2
    cas_root: str


class N5ReplayNativePreflightObservation(BaseModel):
    """Actual selected native identity observed without numerical calls."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    pid: int = Field(gt=0)
    action_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    native_profile: dict[str, object]
    production_image: dict[str, object]
    callable_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    numerical_intent_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    seed_schedule_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    planned_units: int = Field(ge=1)


def observe_n5_replay_native_preflight(
    action: N5ReplayNativePreflightAction,
) -> N5ReplayNativePreflightObservation:
    """Rebuild and observe the selected owner seam without calling the kernel."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.foundry.methods import MethodRegistry
    from polisyos.runtime.quality.acquisition_evaluation import (
        rebuild_selected_candidate_n5_request,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
        PreparedJointSimulationConfiguration,
    )
    from polisyos.runtime.quality.n5_candidate_content import CandidateN5ContentRun
    from polisyos.runtime.quality.n5_execution_basis import snapshot_n5_callable_content_v3
    from polisyos.runtime.quality.n5_replay_appointment import (
        N5_REPLAY_PREPARED_CONFIGURATION_KIND,
        _read_n5_versioned_core_json,
    )

    if type(action) is not N5ReplayNativePreflightAction:
        raise ValueError("n5_replay_native_preflight_untyped")
    spec = action.launch_spec
    store = FileSystemCAS(Path(action.cas_root)).for_tenant(spec.tenant_id, spec.cell_id)
    config, _ = _read_n5_versioned_core_json(
        store,
        spec.prepared_configuration_ref,
        PreparedJointSimulationConfiguration,
        kind=N5_REPLAY_PREPARED_CONFIGURATION_KIND,
        schema_version="1.0",
    )
    request = rebuild_selected_candidate_n5_request(
        store=store,
        input_ref=spec.selected_candidate_simulation_n5_input_ref,
        run_id=spec.source_run_id,
        job_id=spec.source_job_id,
        tenant_id=spec.tenant_id,
        cell_id=spec.cell_id,
    )
    controller = JointSimulationHorizonController(
        method_registry=MethodRegistry._create_fresh(),
        _prepared_configuration=config,
    )
    selected = controller._select_engine(request)
    if (
        selected.decision.decision != "selected"
        or selected.decision.engine_kind != "ncm_parallel_worlds"
        or selected.decision.method_fqn is None
    ):
        raise ValueError("n5_replay_native_preflight_engine_unsupported")
    scope = CandidateN5ContentRun(
        controller=controller,
        request=request,
        input_ref=spec.selected_candidate_simulation_n5_input_ref,
    )
    scope.selected_callable = controller._registry.get(selected.decision.method_fqn).pure_step
    scope.prepare(selected.plan, selected.decision)
    callable_content = snapshot_n5_callable_content_v3(scope.selected_callable)
    if (
        scope.profile is None
        or scope.production_image is None
        or scope.capture is None
        or scope.capture.numerical_intent_content_hash is None
        or callable_content is None
    ):
        raise ValueError("n5_replay_native_preflight_not_established")
    return N5ReplayNativePreflightObservation(
        pid=os.getpid(),
        action_hash=security.raw_content_hash(action.model_dump_json().encode()),
        native_profile=scope.profile.model_dump(mode="json"),
        production_image=scope.production_image.model_dump(mode="json"),
        callable_hash=security.raw_content_hash(callable_content.encode()),
        numerical_intent_hash=scope.capture.numerical_intent_content_hash,
        seed_schedule_hash=n5_replay_seed_schedule_hash(request),
        planned_units=len(scope.planned_units),
    )


def _verify_n5_replay_native_preflight(
    *,
    action: N5ReplayNativePreflightAction,
    observation: N5ReplayNativePreflightObservation,
    recorded_profile: object,
    recorded_image: object,
) -> None:
    """Reconcile the actual launcher observation to the recorded selected basis."""
    from polisyos.runtime.quality.n5_execution_basis import (
        N5ProductionImage,
        exact_n5_content_bytes,
    )
    from polisyos.runtime.quality.n5_execution_profile import (
        N5NativeExecutionProfile,
        reconcile_recorded_n5_profile_current_bytes,
    )

    if (
        type(recorded_profile) is not N5NativeExecutionProfile
        or type(recorded_image) is not N5ProductionImage
    ):
        raise ValueError("n5_replay_native_preflight_recorded_basis_invalid")
    spec = action.launch_spec
    fresh_profile = N5NativeExecutionProfile.model_validate_json(
        json.dumps(observation.native_profile)
    )
    fresh_image = N5ProductionImage.model_validate_json(json.dumps(observation.production_image))
    if (
        observation.action_hash != security.raw_content_hash(action.model_dump_json().encode())
        or observation.callable_hash != spec.declared_callable_content_hash
        or observation.numerical_intent_hash != spec.declared_numerical_intent_content_hash
        or observation.seed_schedule_hash != spec.seed_schedule_hash
        or observation.planned_units != spec.planned_physical_units
        or exact_n5_content_bytes(fresh_image) != exact_n5_content_bytes(recorded_image)
        or reconcile_recorded_n5_profile_current_bytes(
            recorded_profile,
            fresh_profile,
            recorded_source_image=recorded_image,
            current_source_image=fresh_image,
        ).status
        != "recomputed"
    ):
        raise ValueError("n5_replay_native_preflight_mismatch")


class N5BlindReplayExecution(BaseModel):
    """Actual candidate child output; not an independently verified finding."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["policyos.n5_replay.child_execution.v1"] = (
        "policyos.n5_replay.child_execution.v1"
    )
    pid: int = Field(gt=0)
    replay_run_id: str
    replay_job_id: str
    attempt_number: int = Field(ge=1, strict=True)
    action_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    action_ref: artifacts.ArtifactRef
    result_ref: artifacts.ArtifactRef
    ledger_owner: tuple[str, str, str]
    ledger_revision: int = Field(ge=0)
    ledger_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    ledger_snapshot_ref: artifacts.ArtifactRef
    operation_ids: tuple[str, ...]
    budget_admission: Literal["diagnostic_invocation_only"] = "diagnostic_invocation_only"
    usd_cost_status: Literal["not_established"] = "not_established"
    declared_closure: Literal["not_established"] = "not_established"
    read_isolation: Literal["same_user_filesystem_access_not_isolated"] = (
        "same_user_filesystem_access_not_isolated"
    )
    protected_use_allowed: Literal[False] = False

    @model_validator(mode="after")
    def _ledger_ref(self) -> Self:
        if (
            self.ledger_snapshot_ref.kind != "runtime.quality.n5_diagnostic_ledger_snapshot"
            or self.ledger_snapshot_ref.media_type != "application/octet-stream"
            or self.ledger_snapshot_ref.manifest_profile_sha256 is None
            or str(self.ledger_snapshot_ref.artifact_id) != self.ledger_hash
            or self.action_ref.kind != "runtime.quality.n5_blind_replay_action"
            or self.action_ref.media_type != "application/json"
            or self.action_ref.manifest_profile_sha256 is None
            or str(self.action_ref.artifact_id) != self.action_hash
        ):
            raise ValueError("n5_replay_ledger_snapshot_ref_invalid")
        return self


class N5ReplayInfrastructureError(OSError):
    """A bounded diagnostic attempt encountered an infrastructure failure."""


class N5ReplayInfrastructureFailure(BaseModel):
    """Child-reported infrastructure failure, independently reconciled by parent."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["policyos.n5_replay.infrastructure_failure.v1"] = (
        "policyos.n5_replay.infrastructure_failure.v1"
    )
    pid: int = Field(gt=0)
    attempt_number: int = Field(ge=1)
    action_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    code: Literal["infrastructure_error"] = "infrastructure_error"


_WORKER_RESULT_PREFIX = "POLISYOS_N5_WORKER_RESULT="
_MAX_WORKER_RESULT_BYTES = 8 * 1024 * 1024


def _worker_result_payload(stdout: str) -> str:
    """Select one bounded result record while preserving ordinary worker logs."""
    matches = [
        line.removeprefix(_WORKER_RESULT_PREFIX)
        for line in stdout.splitlines()
        if line.startswith(_WORKER_RESULT_PREFIX)
    ]
    if len(matches) != 1 or len(matches[0].encode("utf-8")) > _MAX_WORKER_RESULT_BYTES:
        raise ValueError("n5_replay_worker_result_not_established")
    return matches[0]


class _WorkerLaunchError(OSError):
    """The worker process was not launched."""


class _WorkerLifecycleError(ValueError):
    """A launched worker failed its bounded process lifecycle."""

    def __init__(self, reason: str, pid: int) -> None:
        super().__init__(reason)
        self.pid = pid


def _run_managed_worker(
    command: list[str], workspace: Path, suffix: str, *, timeout: float = 600
) -> tuple[int, int, str, dict[int, int]]:
    """Hold the session leader until its owned group is observed empty and reaped."""
    if (
        signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL
        or not callable(getattr(os, "waitid", None))
        or not all(hasattr(os, name) for name in ("P_PID", "WEXITED", "WNOHANG", "WNOWAIT"))
    ):
        raise ValueError("n5_worker_waitid_unavailable")

    def peek(pid: int) -> bool:
        info = os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        return info is not None and info.si_pid != 0

    def live_group(pid: int) -> bool:
        if not peek(pid):
            return True
        try:
            for member in psutil.process_iter(["pid"]):
                member_pid = member.info.get("pid")
                if member_pid is None or member_pid == pid:
                    continue
                try:
                    if (
                        os.getpgid(member_pid) == pid
                        and os.getsid(member_pid) == pid
                        and member.status() != psutil.STATUS_ZOMBIE
                    ):
                        return True
                except (ProcessLookupError, psutil.NoSuchProcess, psutil.ZombieProcess):
                    continue
        except (PermissionError, psutil.Error):
            # Unknown membership still requires bounded cleanup and never admits success.
            return True
        return False

    def signal_group(process: subprocess.Popen[bytes], sig: signal.Signals) -> None:
        exited = peek(process.pid)
        if process.returncode is not None:
            raise RuntimeError("n5_worker_leader_reaped")
        try:
            pgid, sid = os.getpgid(process.pid), os.getsid(process.pid)
        except ProcessLookupError:
            if not exited and not peek(process.pid):
                raise RuntimeError("n5_worker_leader_unavailable") from None
            pgid = sid = process.pid
        if pgid != process.pid or sid != process.pid:
            raise RuntimeError("n5_worker_session_mismatch")
        with suppress(ProcessLookupError):
            os.killpg(process.pid, sig)

    stdout_path = workspace / f"child-stdout{suffix}.log"
    stderr_path = workspace / f"child-stderr{suffix}.log"
    with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
        try:
            process = subprocess.Popen(  # noqa: S603
                command, stdout=out, stderr=err, start_new_session=True
            )
        except OSError as exc:
            raise _WorkerLaunchError(str(exc)) from exc
        reason: str | None = None
        observed: dict[int, int] = {}
        ambiguous: set[int] = set()

        def observe_members() -> None:
            try:
                leader = psutil.Process(process.pid)
                members = [leader, *leader.children(recursive=True)]
                for member in members:
                    try:
                        if (
                            os.getpgid(member.pid) != process.pid
                            or os.getsid(member.pid) != process.pid
                        ):
                            continue
                        created = int(member.create_time() * 1_000_000)
                        if member.pid in observed and observed[member.pid] != created:
                            ambiguous.add(member.pid)
                        else:
                            observed[member.pid] = created
                    except (ProcessLookupError, psutil.NoSuchProcess, psutil.ZombieProcess):
                        continue
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                return

        try:
            deadline = time.monotonic() + timeout
            while not peek(process.pid):
                observe_members()
                if time.monotonic() >= deadline:
                    reason = "timeout"
                    break
                time.sleep(0.05)
            if reason is None and live_group(process.pid):
                reason = "group_not_quiescent"
        finally:
            # Do not reap until after any signals: WNOWAIT reserves this PID.
            try:
                if reason is not None or not peek(process.pid) or live_group(process.pid):
                    for sig in (signal.SIGTERM, signal.SIGKILL):
                        signal_group(process, sig)
                        deadline = time.monotonic() + 1.0
                        while time.monotonic() < deadline:
                            if not live_group(process.pid):
                                break
                            time.sleep(0.05)
                        if not live_group(process.pid):
                            break
                # Two scans are needed; an inaccessible process table fails closed.
                if live_group(process.pid):
                    raise RuntimeError("n5_worker_group_cleanup_unresolved")
                time.sleep(0.05)
                if live_group(process.pid):
                    raise RuntimeError("n5_worker_group_cleanup_unresolved")
            finally:
                process.wait(timeout=2)
    if reason is not None:
        raise _WorkerLifecycleError(reason, process.pid)
    return (
        process.pid,
        process.returncode,
        stdout_path.read_text(encoding="utf-8"),
        {pid: created for pid, created in observed.items() if pid not in ambiguous},
    )


def _require_observed_executor(pid: int, observed: dict[int, int]) -> int:
    """Bind a reported executor to a unique observed member of this session."""
    created = observed.get(pid)
    if created is None or created <= 0 or pid == os.getpid():
        raise ValueError("n5_worker_executor_not_observed")
    return created


@dataclass(frozen=True, slots=True)
class N5ReplayLauncherSigningService:
    """Service-held launcher signer and its existing selected provenance."""

    signer: artifacts.Ed25519Signer
    signing_profile_ref: artifacts.ArtifactRef
    signer_provenance_ref: artifacts.ArtifactRef
    launcher_instance_id: str


class N5ReplayCandidateComparison(BaseModel):
    """Parent-recomputed exact comparison with limited candidate semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["policyos.n5_replay.candidate_comparison.v1"] = (
        "policyos.n5_replay.candidate_comparison.v1"
    )
    status: Literal["equal", "mismatch"]
    parent_pid: int = Field(gt=0)
    child_pid: int = Field(gt=0)
    attempt_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    original_result_ref: artifacts.ArtifactRef
    replay_result_ref: artifacts.ArtifactRef
    child_execution_ref: artifacts.ArtifactRef
    original_projection_hash: str
    replay_projection_hash: str
    diagnostic_ledger_hash: str
    completed_units: int = Field(ge=1)
    mismatch_policy: Literal["final_no_retry"] = "final_no_retry"
    declared_closure: Literal["not_established"] = "not_established"
    scientific_independence: Literal["not_established"] = "not_established"
    read_isolation: Literal["same_user_filesystem_access_not_isolated"] = (
        "same_user_filesystem_access_not_isolated"
    )
    protected_use_allowed: Literal[False] = False


class N5ReplayAttemptEntry(BaseModel):
    """One settled attempt in the local diagnostic lifecycle."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    attempt_number: int = Field(ge=1, strict=True)
    status: Literal["infrastructure_error", "equal", "mismatch", "unknown"]
    child_pid: int | None = Field(default=None, gt=0)
    executor_pid: int | None = Field(default=None, gt=0)
    executor_created_us: int | None = Field(default=None, gt=0)
    execution_ref: artifacts.ArtifactRef | None = None
    comparison_ref: artifacts.ArtifactRef | None = None
    ledger_hash: str | None = None
    ledger_revision: int | None = Field(default=None, ge=0)


class N5ReplayAttemptState(BaseModel):
    """Durable local lifecycle; this is neither permission nor a cache verdict."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["policyos.n5_replay.attempt_state.v1"] = (
        "policyos.n5_replay.attempt_state.v1"
    )
    key: str = Field(pattern=r"^[0-9a-f]{64}$")
    replay_run_id: str
    replay_job_id: str
    quota_units: int = Field(ge=1, strict=True)
    attempt_limit: int = Field(ge=1, strict=True)
    attempt_number: int = Field(ge=0, strict=True)
    status: Literal["active", "infrastructure_error", "executed", "equal", "mismatch", "unknown"]
    started_at: datetime | None = None
    finished_at: datetime | None = None
    child_pid: int | None = Field(default=None, gt=0)
    executor_pid: int | None = Field(default=None, gt=0)
    executor_created_us: int | None = Field(default=None, gt=0)
    execution_ref: artifacts.ArtifactRef | None = None
    comparison_ref: artifacts.ArtifactRef | None = None
    ledger_hash: str | None = None
    ledger_revision: int | None = Field(default=None, ge=0)
    history: tuple[N5ReplayAttemptEntry, ...] = ()

    @model_validator(mode="after")
    def _attempt_history(self) -> Self:
        if (
            self.attempt_number > self.attempt_limit
            or tuple(entry.attempt_number for entry in self.history)
            != tuple(range(1, len(self.history) + 1))
            or len(self.history) > self.attempt_number
            or (
                self.status in {"active", "executed"}
                and len(self.history) != self.attempt_number - 1
            )
            or (
                self.status not in {"active", "executed"}
                and len(self.history) != self.attempt_number
            )
            or (
                self.status not in {"active", "executed"}
                and (
                    not self.history
                    or self.history[-1].status != self.status
                    or self.history[-1].child_pid != self.child_pid
                    or self.history[-1].executor_pid != self.executor_pid
                    or self.history[-1].executor_created_us != self.executor_created_us
                    or self.history[-1].execution_ref != self.execution_ref
                    or self.history[-1].comparison_ref != self.comparison_ref
                    or self.history[-1].ledger_hash != self.ledger_hash
                    or self.history[-1].ledger_revision != self.ledger_revision
                )
            )
            or (
                self.status == "infrastructure_error"
                and (self.ledger_hash is None or self.ledger_revision is None)
            )
            or (
                self.status == "executed"
                and (
                    self.child_pid is None
                    or self.executor_pid is None
                    or self.executor_created_us is None
                    or self.execution_ref is None
                    or self.ledger_hash is None
                    or self.ledger_revision is None
                )
            )
            or (
                self.status in {"equal", "mismatch"}
                and (
                    self.child_pid is None
                    or self.executor_pid is None
                    or self.executor_created_us is None
                    or self.execution_ref is None
                    or self.comparison_ref is None
                    or self.ledger_hash is None
                    or self.ledger_revision is None
                )
            )
        ):
            raise ValueError("n5_replay_attempt_history_invalid")
        return self


@contextmanager
def _attempt_lock(directory: Path) -> Iterator[None]:
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink():
        raise ValueError("n5_replay_attempt_owner_invalid")
    lock_path = directory / "owner.lock"
    if lock_path.is_symlink():
        raise ValueError("n5_replay_attempt_owner_invalid")
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _write_attempt_state(directory: Path, state: N5ReplayAttemptState) -> None:
    artifacts.write_bytes_atomic(
        directory / "state.json", state.model_dump_json().encode("utf-8"), durable_parent=True
    )


def _fenced_ledger_snapshot(path: Path) -> tuple[BudgetLedgerSnapshot, bytes]:
    """Capture the actual ledger bytes under its native owner lock."""
    from polisyos.scientist.orchestration.engine import FileBudgetLedger

    return FileBudgetLedger(path).snapshot_with_raw_bytes()


def _process_group_quiescent(pid: int) -> bool:
    """Check the launched process group after its leader has been reaped."""
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return False


def _existing_execution_precondition(
    workspace: Path, *, key: str, spec: N5BlindReplayLaunchSpecV2, publishing: bool
) -> tuple[bool, bool]:
    """Check the untrusted pointer, journal and ledger before current identity work.

    Returns whether a signed pointer exists and whether an existing execution
    must pass the assigned-launcher identity check before it may be reused.
    """
    pointer = workspace / "completed-evidence.json"
    state_path = workspace / "state.json"
    if pointer.is_symlink() or state_path.is_symlink():
        raise ValueError("n5_replay_attempt_owner_invalid")
    has_pointer = pointer.exists()
    if not has_pointer and not state_path.exists():
        return False, False
    with _attempt_lock(workspace):
        if pointer.is_symlink() or state_path.is_symlink():
            raise ValueError("n5_replay_attempt_owner_invalid")
        has_pointer = pointer.exists()
        if has_pointer:
            artifacts.ArtifactRef.model_validate_json(pointer.read_bytes())
        if not state_path.exists():
            if has_pointer:
                raise ValueError("n5_replay_completed_attempt_not_established")
            return False, False
        state = N5ReplayAttemptState.model_validate_json(state_path.read_bytes())
        if has_pointer and state.status not in {"equal", "mismatch"}:
            raise ValueError("n5_replay_completed_attempt_not_established")
        reuse = state.status == "executed" or (
            state.status in {"equal", "mismatch"} and (has_pointer or publishing)
        )
        if not reuse:
            return has_pointer, False
        if (
            state.key != key
            or state.execution_ref is None
            or state.ledger_hash is None
            or state.ledger_revision is None
            or (
                not has_pointer
                and (
                    state.replay_run_id != spec.replay_run_id
                    or state.replay_job_id != spec.replay_job_id
                )
            )
            or (
                state.status in {"equal", "mismatch"}
                and (state.started_at is None or state.finished_at is None)
            )
        ):
            raise ValueError("n5_replay_completed_publication_not_recoverable")
        snapshot, raw = _fenced_ledger_snapshot(workspace / "diagnostic-ledger.json")
        if (
            snapshot.revision != state.ledger_revision
            or security.raw_content_hash(raw) != state.ledger_hash
        ):
            raise ValueError("n5_replay_attempt_ledger_changed")
        return has_pointer, True


def _preflight_existing_execution(
    workspace: Path,
    *,
    attempt: N5ReplayAttemptState,
    spec: N5BlindReplayLaunchSpecV2,
    cas_root: str,
    recorded_profile: object,
    recorded_image: object,
) -> None:
    """Gate the execution actually selected by the attempt owner."""
    if attempt.status in {"executed", "equal", "mismatch"}:
        snapshot, raw = _fenced_ledger_snapshot(workspace / "diagnostic-ledger.json")
        if (
            snapshot.revision != attempt.ledger_revision
            or security.raw_content_hash(raw) != attempt.ledger_hash
        ):
            raise ValueError("n5_replay_attempt_ledger_changed")
        native_action = N5ReplayNativePreflightAction(launch_spec=spec, cas_root=cas_root)
        native_action_path = workspace / f"native-preflight-{uuid.uuid4().hex}.json"
        native_action_path.write_text(native_action.model_dump_json(), encoding="utf-8")
        executable = Path(__file__).resolve().parents[4] / "tools" / "authority"
        _leader, exit_code, output, processes = _run_managed_worker(
            [
                str(executable),
                "runtime",
                "scientist",
                "n5-replay-profile-preflight",
                "--action",
                str(native_action_path),
            ],
            workspace,
            "-native-preflight",
        )
        if exit_code != 0:
            raise ValueError("n5_replay_native_preflight_failed")
        observed_native = N5ReplayNativePreflightObservation.model_validate_json(
            _worker_result_payload(output)
        )
        _require_observed_executor(observed_native.pid, processes)
        _verify_n5_replay_native_preflight(
            action=native_action,
            observation=observed_native,
            recorded_profile=recorded_profile,
            recorded_image=recorded_image,
        )


def _begin_attempt(
    directory: Path, *, key: str, spec: N5BlindReplayLaunchSpecV2, quota: int, limit: int
) -> N5ReplayAttemptState:
    """Issue one attempt only after durable terminal accounting permits it."""
    with _attempt_lock(directory):
        path = directory / "state.json"
        if path.is_symlink():
            raise ValueError("n5_replay_attempt_owner_invalid")
        if not path.exists():
            state = N5ReplayAttemptState(
                key=key,
                replay_run_id=spec.replay_run_id,
                replay_job_id=spec.replay_job_id,
                quota_units=quota,
                attempt_limit=limit,
                attempt_number=1,
                status="active",
            )
        else:
            prior = N5ReplayAttemptState.model_validate_json(path.read_bytes())
            if (
                prior.key != key
                or prior.replay_run_id != spec.replay_run_id
                or prior.replay_job_id != spec.replay_job_id
                or prior.quota_units != quota
                or prior.attempt_limit != limit
            ):
                raise ValueError("n5_replay_attempt_binding_changed")
            if prior.status == "executed":
                return prior
            if prior.status != "infrastructure_error" or prior.attempt_number >= limit:
                raise ValueError("n5_replay_attempt_not_retryable")
            ledger_path = directory / "diagnostic-ledger.json"
            if ledger_path.is_symlink() or not ledger_path.is_file():
                raise ValueError("n5_replay_attempt_ledger_changed")
            snapshot, ledger_bytes = _fenced_ledger_snapshot(ledger_path)
            if prior.ledger_hash != security.raw_content_hash(ledger_bytes):
                raise ValueError("n5_replay_attempt_ledger_changed")
            records = tuple(snapshot.invocation_reservations.values())
            if (
                snapshot.revision != prior.ledger_revision
                or any(row.status not in {"completed", "failed"} for row in records)
                or any(
                    row.run_id != spec.replay_run_id or row.purpose != "diagnostic"
                    for row in records
                )
                or quota - sum(row.units for row in records) < spec.planned_physical_units
            ):
                raise ValueError("n5_replay_attempt_capacity_not_established")
            state = prior.model_copy(
                update={
                    "status": "active",
                    "started_at": None,
                    "finished_at": None,
                    "attempt_number": prior.attempt_number + 1,
                    "child_pid": None,
                    "executor_pid": None,
                    "executor_created_us": None,
                    "execution_ref": None,
                    "ledger_hash": None,
                    "ledger_revision": None,
                }
            )
        _write_attempt_state(directory, state)
        return state


def _settle_attempt(
    directory: Path, prior: N5ReplayAttemptState, **changes: object
) -> N5ReplayAttemptState:
    """Compare-and-set the active or executed attempt under the owner lock."""
    with _attempt_lock(directory):
        state_path = directory / "state.json"
        if state_path.is_symlink():
            raise ValueError("n5_replay_attempt_owner_invalid")
        current = N5ReplayAttemptState.model_validate_json(state_path.read_bytes())
        if current != prior:
            raise ValueError("n5_replay_attempt_state_changed")
        payload = {**current.model_dump(mode="python"), **changes}
        if payload["status"] in {"infrastructure_error", "equal", "mismatch", "unknown"}:
            entry = N5ReplayAttemptEntry(
                attempt_number=current.attempt_number,
                status=payload["status"],
                child_pid=payload["child_pid"],
                executor_pid=payload["executor_pid"],
                executor_created_us=payload["executor_created_us"],
                execution_ref=payload["execution_ref"],
                comparison_ref=payload["comparison_ref"],
                ledger_hash=payload["ledger_hash"],
                ledger_revision=payload["ledger_revision"],
            )
            payload["history"] = (*current.history, entry)
        next_state = N5ReplayAttemptState.model_validate(payload)
        _write_attempt_state(directory, next_state)
        return next_state


def _open_diagnostic_budget(
    spec: N5BlindReplayLaunchSpecV2, ledger_path: Path, quota: int
) -> tuple[ProducerBudgetObserver, BudgetMiddleware]:
    """Open the one job ledger, refusing foreign or unresolved records."""
    return _open_diagnostic_owner(
        run_id=spec.replay_run_id,
        job_id=spec.replay_job_id,
        tenant_id=spec.tenant_id,
        cell_id=spec.cell_id,
        ledger_path=ledger_path,
        quota=quota,
    )


def _open_diagnostic_owner(
    *, run_id: str, job_id: str, tenant_id: str, cell_id: str, ledger_path: Path, quota: int
) -> tuple[ProducerBudgetObserver, BudgetMiddleware]:
    """Bind one actual job to the canonical invocation-only owner."""
    from polisyos.scientist.orchestration.engine import (
        BudgetInvocationQuotaPolicy,
        BudgetLedgerInvocationProfile,
        BudgetLedgerProducerRunBinding,
        BudgetLimit,
        BudgetMiddleware,
        BudgetState,
        FileBudgetLedger,
        ProducerBudgetObserver,
    )

    if ledger_path.is_symlink():
        raise ValueError("n5_replay_diagnostic_ledger_invalid")
    binding = BudgetLedgerProducerRunBinding(
        run_id=run_id,
        control_job_id=job_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
        profile_id="n5-replay-diagnostic-v1",
    )
    policy = BudgetInvocationQuotaPolicy(
        allocation_id=f"n5-replay-{job_id}",
        total_units=quota,
        protected_units=quota,
    )
    profile = BudgetLedgerInvocationProfile.from_policy(binding, policy)
    ledger = FileBudgetLedger(ledger_path)
    if ledger_path.exists():
        snapshot = ledger.snapshot()
        if (
            snapshot.invocation_profiles != {binding.run_id: profile}
            or snapshot.producer_settlements
            or any(
                row.status not in {"completed", "failed"} or row.purpose != "diagnostic"
                for row in snapshot.invocation_reservations.values()
            )
        ):
            raise ValueError("n5_replay_diagnostic_ledger_binding_mismatch")
    middleware = BudgetMiddleware(BudgetState(), ledger=ledger)
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal(0))})
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
        invocation_quota_profile=profile,
        invocation_purpose="diagnostic",
    )
    return observer, middleware


class N5ReplayPreflight:
    """Source, budget, and action binding for the canonical producer seam."""

    def __init__(
        self,
        *,
        spec: N5BlindReplayLaunchSpecV2,
        store: CoreJSONArtifactStore,
        budget: ProducerBudgetObserver,
    ) -> None:
        from polisyos.scientist.orchestration.engine import ProducerBudgetObserver

        if type(spec) is not N5BlindReplayLaunchSpecV2:
            raise ValueError("n5_replay_preflight_spec_untyped")
        if type(budget) is not ProducerBudgetObserver:
            raise ValueError("n5_replay_preflight_budget_untyped")
        self.spec = spec
        self.store = store
        self.budget = budget

    def check(self, scope: CandidateN5ContentRun) -> N5DiagnosticCapacityObservation:
        """Reopen current source and capacity at the actual selected-plan seam."""
        return preflight_candidate_n5_replay(
            scope=scope, spec=self.spec, store=self.store, budget=self.budget
        )


class N5OriginalPreflight:
    """Canonical preflight for an original candidate producer operation."""

    def __init__(self, *, action: N5OriginalProducerAction, budget: ProducerBudgetObserver) -> None:
        from polisyos.scientist.orchestration.engine import ProducerBudgetObserver

        if (
            type(action) is not N5OriginalProducerAction
            or type(budget) is not ProducerBudgetObserver
        ):
            raise ValueError("n5_original_preflight_input_untyped")
        self.action = action
        self.budget = budget

    def check(self, scope: CandidateN5ContentRun) -> N5DiagnosticCapacityObservation:
        """Observe actual plan and capacity without inventing a prior result."""
        from polisyos.runtime.quality.n5_execution_basis import snapshot_n5_callable_content_v3

        action = self.action
        if (
            scope.controller._producer_budget_observer is not self.budget
            or artifacts.artifact_ref_identity_key(scope.input_ref)
            != artifacts.artifact_ref_identity_key(action.source_input_ref)
            or scope.capture is None
            or scope.capture.numerical_intent_content_hash is None
            or scope.profile is None
            or scope.profile.profile_identity_predicate != "recomputed"
            or scope.production_image is None
            or scope.production_image.provenance != "recomputed"
            or scope.configuration is None
            or not scope.planned_units
            or snapshot_n5_callable_content_v3(scope.selected_callable) is None
        ):
            raise ValueError("n5_original_selected_basis_not_established")
        capacity = self.budget.admit_diagnostic_invocation_only()
        if (
            capacity.protected_remaining_units is None
            or capacity.protected_remaining_units < len(scope.planned_units)
            or capacity.run_binding.run_id != action.producer_run_id
            or capacity.run_binding.control_job_id != action.producer_job_id
            or capacity.run_binding.tenant_id != action.tenant_id
            or capacity.run_binding.cell_id != action.cell_id
        ):
            raise ValueError("n5_original_diagnostic_capacity_not_established")
        return capacity


def n5_replay_seed_schedule_hash(request: JointSimulationRequest) -> str:
    """Hash the actual ordered replication seeds without occurrence labels."""
    from polisyos.runtime.quality.joint_simulation_horizon import _replication_seeds
    from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_hash

    return exact_n5_content_hash(
        {"schema_version": "n5_replay.seed_schedule.v1", "seeds": _replication_seeds(request)}
    )


def execute_original_n5_producer(
    action: N5OriginalProducerAction,
) -> tuple[N5OriginalProducerExecution, artifacts.ArtifactRef]:
    """Produce an actual candidate original using a distinct zero-USD job ledger."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.foundry.methods import MethodRegistry
    from polisyos.runtime.quality.generation_cycle import persist_joint_simulation_result
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController
    from polisyos.runtime.quality.n5_candidate_content import (
        bind_candidate_n5_content_observation,
        observe_source_rebuilt_original_n5_input,
        read_candidate_n5_content_observation,
    )

    if type(action) is not N5OriginalProducerAction:
        raise ValueError("n5_original_action_untyped")
    action = N5OriginalProducerAction.model_validate(action.model_dump(mode="python"))
    ledger_path = Path(action.ledger_path)
    if ledger_path.exists() or ledger_path.is_symlink():
        raise ValueError("n5_original_ledger_not_fresh")
    store = FileSystemCAS(Path(action.cas_root)).for_tenant(action.tenant_id, action.cell_id)
    tenant = artifacts.ArtifactTenantContextInfo(tenant_id=action.tenant_id, cell_id=action.cell_id)
    canon = CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False)
    action_ref = store.put_json(
        action.model_dump(mode="json"),
        artifacts.PutOptions(
            kind="runtime.quality.n5_original_producer_action",
            media_type="application/json",
            schema=artifacts.SchemaInfo(name=action.schema_version, version="1.0"),
            inputs=[
                artifacts.input_ref_from_artifact_ref(action.source_input_ref, role="source_input")
            ],
            tenant_context=tenant,
        ),
        canon_spec=canon,
        return_selected_profile=True,
    )
    budget, middleware = _open_diagnostic_owner(
        run_id=action.producer_run_id,
        job_id=action.producer_job_id,
        tenant_id=action.tenant_id,
        cell_id=action.cell_id,
        ledger_path=ledger_path,
        quota=action.quota_units,
    )
    controller = JointSimulationHorizonController(
        method_registry=MethodRegistry._create_fresh(),
        producer_budget_observer=budget,
    )
    with observe_source_rebuilt_original_n5_input(
        store=store, controller=controller, action=action, budget=budget
    ) as (request, scope):
        result = bind_candidate_n5_content_observation(controller.run(request), scope=scope)
    observation = read_candidate_n5_content_observation(
        result, input_ref=action.source_input_ref, expected_request=request
    )
    if observation.completion.status != "recomputed":
        raise ValueError("n5_original_completion_not_established")
    snapshot = middleware.snapshot_safe()
    records = snapshot.invocation_reservations
    work = result.physical_work_observations
    operation_ids = tuple(item.invocation_quota_operation_id for item in work)
    if (
        len(work) != len(scope.planned_units)
        or len(set(operation_ids)) != len(work)
        or len(records) != len(work)
        or any(
            item.invocation_quota_operation_id not in records
            or records[item.invocation_quota_operation_id].status != "completed"
            or records[item.invocation_quota_operation_id].purpose != "diagnostic"
            or records[item.invocation_quota_operation_id].request_digest
            != item.invocation_quota_request_digest
            or records[item.invocation_quota_operation_id].profile_digest
            != item.invocation_quota_profile_digest
            for item in work
        )
    ):
        raise ValueError("n5_original_accounting_not_established")
    result_ref = persist_joint_simulation_result(result, store=store, tenant_context=tenant)
    fenced_snapshot, ledger_bytes = _fenced_ledger_snapshot(ledger_path)
    if fenced_snapshot != snapshot:
        raise ValueError("n5_original_ledger_changed_during_capture")
    ledger_ref = store.put_bytes(
        ledger_bytes,
        artifacts.PutOptions(
            kind="runtime.quality.n5_diagnostic_ledger_snapshot",
            media_type="application/octet-stream",
            schema=artifacts.SchemaInfo(
                name="polisyos.scientist.budget_ledger.snapshot",
                version=fenced_snapshot.schema_version,
            ),
            tenant_context=tenant,
            inputs=[artifacts.input_ref_from_artifact_ref(result_ref, role="original_result")],
        ),
        return_selected_profile=True,
    )
    intent_ref, profile_ref = _persist_declared_basis(
        store=store,
        input_ref=action.source_input_ref,
        source_run_id=action.source_run_id,
        source_job_id=action.source_job_id,
        original_run_id=action.producer_run_id,
        original_job_id=action.producer_job_id,
        tenant_id=action.tenant_id,
        cell_id=action.cell_id,
        request=request,
        result=result,
    )
    execution = N5OriginalProducerExecution(
        source_input_ref=action.source_input_ref,
        source_run_id=action.source_run_id,
        source_job_id=action.source_job_id,
        producer_run_id=action.producer_run_id,
        producer_job_id=action.producer_job_id,
        tenant_id=action.tenant_id,
        cell_id=action.cell_id,
        pid=os.getpid(),
        action_ref=action_ref,
        action_hash=security.raw_content_hash(store.get_bytes(action_ref)),
        result_ref=result_ref,
        numerical_intent_ref=intent_ref,
        execution_profile_ref=profile_ref,
        ledger_owner=middleware.settlement_owner_identity,
        ledger_revision=snapshot.revision,
        ledger_hash=security.raw_content_hash(ledger_bytes),
        ledger_snapshot_ref=ledger_ref,
        operation_ids=tuple(item for item in operation_ids if item is not None),
    )
    kind = "runtime.quality.n5_original_producer_execution"
    spec = CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False)
    execution_ref = store.put_json(
        execution.model_dump(mode="json"),
        artifacts.PutOptions(
            kind=kind,
            media_type="application/json",
            schema=artifacts.SchemaInfo(name=kind, version="1.0"),
            inputs=[
                artifacts.input_ref_from_artifact_ref(action.source_input_ref, role="source_input"),
                artifacts.input_ref_from_artifact_ref(action_ref, role="original_action"),
                artifacts.input_ref_from_artifact_ref(result_ref, role="original_result"),
                artifacts.input_ref_from_artifact_ref(ledger_ref, role="diagnostic_ledger"),
                artifacts.input_ref_from_artifact_ref(intent_ref, role="numerical_intent"),
                artifacts.input_ref_from_artifact_ref(profile_ref, role="execution_profile"),
            ],
            tenant_context=tenant,
        ),
        canon_spec=spec,
        return_selected_profile=True,
    )
    return execution, execution_ref


def run_original_n5_producer(
    *, action: N5OriginalProducerAction, workspace: Path
) -> N5OriginalProducerOutcome:
    """Launch and independently reopen one candidate original producer result."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.runtime.quality.acquisition_evaluation import (
        rebuild_selected_candidate_n5_request,
    )
    from polisyos.runtime.quality.generation_cycle import load_joint_simulation_result
    from polisyos.runtime.quality.n5_candidate_content import read_candidate_n5_content_observation
    from polisyos.runtime.quality.n5_replay_appointment import _read_n5_versioned_core_json

    if type(action) is not N5OriginalProducerAction:
        raise ValueError("n5_original_action_untyped")
    action = N5OriginalProducerAction.model_validate(action.model_dump(mode="python"))
    if Path(action.ledger_path).absolute() != (workspace / "original-ledger.json").absolute():
        raise ValueError("n5_original_ledger_workspace_mismatch")
    workspace.mkdir(parents=True, exist_ok=False)
    action_path = workspace / "original-action.json"
    action_path.write_text(action.model_dump_json(), encoding="utf-8")
    executable = Path(__file__).resolve().parents[4] / "tools" / "authority"
    # The executable and argument layout are fixed; no shell is used.
    try:
        _launcher_pid, returncode, stdout, observed_processes = _run_managed_worker(
            [
                str(executable),
                "runtime",
                "scientist",
                "n5-original-producer",
                "--action",
                str(action_path),
            ],
            workspace,
            "",
        )
    except _WorkerLaunchError as exc:
        (workspace / "child-launch-error.log").write_text(repr(exc), encoding="utf-8")
        raise
    except _WorkerLifecycleError as exc:
        raise ValueError(f"n5_original_child_{exc}") from exc
    if returncode != 0:
        raise ValueError("n5_original_child_failed")
    outcome = N5OriginalProducerOutcome.model_validate_json(_worker_result_payload(stdout))
    store = FileSystemCAS(Path(action.cas_root)).for_tenant(action.tenant_id, action.cell_id)
    persisted, _ = _read_n5_versioned_core_json(
        store,
        outcome.execution_ref,
        N5OriginalProducerExecution,
        kind="runtime.quality.n5_original_producer_execution",
        schema_version="1.0",
    )
    _require_observed_executor(persisted.pid, observed_processes)
    if (
        persisted != outcome.execution
        or _read_original_action(store, persisted.action_ref, persisted.action_hash) != action
        or persisted.source_input_ref != action.source_input_ref
        or persisted.source_run_id != action.source_run_id
        or persisted.source_job_id != action.source_job_id
        or persisted.producer_run_id != action.producer_run_id
        or persisted.producer_job_id != action.producer_job_id
        or persisted.tenant_id != action.tenant_id
        or persisted.cell_id != action.cell_id
    ):
        raise ValueError("n5_original_execution_not_reconciled")
    request = rebuild_selected_candidate_n5_request(
        store=store,
        input_ref=action.source_input_ref,
        run_id=action.source_run_id,
        job_id=action.source_job_id,
        tenant_id=action.tenant_id,
        cell_id=action.cell_id,
    )
    result = load_joint_simulation_result(
        persisted.result_ref, store=store, expected_request=request
    )
    observation = read_candidate_n5_content_observation(
        result, input_ref=action.source_input_ref, expected_request=request
    )
    snapshot, ledger_bytes = _fenced_ledger_snapshot(Path(action.ledger_path))
    if (
        observation.completion.status != "recomputed"
        or snapshot.revision != persisted.ledger_revision
        or persisted.ledger_owner
        != (snapshot.ledger_id, snapshot.canonical_contract, snapshot.coordination_mode)
        or persisted.ledger_hash != security.raw_content_hash(ledger_bytes)
        or store.get_bytes(persisted.ledger_snapshot_ref) != ledger_bytes
        or not store.verify(persisted.ledger_snapshot_ref).ok
        or set(persisted.operation_ids) != set(snapshot.invocation_reservations)
        or len(persisted.operation_ids) != len(result.physical_work_observations)
        or any(
            row.status != "completed"
            or row.purpose != "diagnostic"
            or row.run_id != action.producer_run_id
            for row in snapshot.invocation_reservations.values()
        )
    ):
        raise ValueError("n5_original_accounting_not_reconciled")
    _verify_declared_basis(store=store, execution=persisted, request=request, result=result)
    return outcome


def execute_blind_n5_replay(action: N5BlindReplayAction) -> N5BlindReplayExecution:
    """Execute one demonstration action using the actual controller and ledger.

    This function accepts no original result. Its caller must establish the
    current appointment before launching the separate process.
    """
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.foundry.methods import MethodRegistry
    from polisyos.runtime.quality.generation_cycle import persist_joint_simulation_result
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
        PreparedJointSimulationConfiguration,
    )
    from polisyos.runtime.quality.n5_candidate_content import (
        bind_candidate_n5_content_observation,
        observe_source_rebuilt_candidate_n5_input,
        read_candidate_n5_content_observation,
    )
    from polisyos.runtime.quality.n5_replay_appointment import (
        N5_REPLAY_PREPARED_CONFIGURATION_KIND,
        N5ReplayAppointment,
        N5ReplayAppointmentResolver,
        N5ReplayAppointmentVerification,
        _read_n5_versioned_core_json,
        _trust,
    )

    if type(action) is not N5BlindReplayAction:
        raise ValueError("n5_replay_child_action_untyped")
    action = N5BlindReplayAction.model_validate(action.model_dump(mode="python"))
    spec = action.launch_spec
    config = action.demonstration_trust
    if (
        config.trust_root_class != "demonstration_test_root"
        or config.appointment_evidence_ref is None
        or config.verification_evidence_ref is None
        or spec.scope not in config.authorized_scopes
    ):
        raise ValueError("n5_replay_child_demonstration_trust_not_established")
    store = FileSystemCAS(Path(action.cas_root)).for_tenant(spec.tenant_id, spec.cell_id)
    trust = _trust(config)
    verifier = N5ReplayAppointmentResolver(store=store)
    appointment, appointment_ref, issuer_key, issuer = verifier._signed(
        config.appointment_evidence_ref, N5ReplayAppointment, "appointment_issuer", trust
    )
    check, _, admin_key, admin = verifier._signed(
        config.verification_evidence_ref,
        N5ReplayAppointmentVerification,
        "deployment_administrator",
        trust,
    )
    launcher = trust.by_key.get(appointment.launcher_key_id)
    now = datetime.now(UTC)
    if (
        launcher is None
        or appointment.launcher_key_id in config.revoked_key_ids
        or set(issuer.roles) != {"appointment_issuer"}
        or set(admin.roles) != {"deployment_administrator"}
        or set(launcher.roles) != {"appointed_launcher"}
        or len({issuer_key, admin_key, appointment.launcher_key_id}) != 3
        or len({issuer.identity, admin.identity, launcher.identity}) != 3
        or len(
            {
                (issuer.organization, issuer.function),
                (admin.organization, admin.function),
                (launcher.organization, launcher.function),
            }
        )
        != 3
        or issuer.organization != spec.scope.accepting_organization
        or appointment.scope != spec.scope
        or check.scope != spec.scope
        or not (
            appointment.valid_from <= now < appointment.valid_until
            and check.valid_from <= now < check.valid_until
        )
        or check.appointment_ref != appointment_ref
        or check.appointment_content_hash != str(appointment_ref.artifact_id)
        or check.current_trust_snapshot_hash != trust.snapshot_hash
        or check.launcher_profile_ref != spec.launcher_profile_ref
        or check.deployed_component_provenance_ref != action.component_provenance_ref
        or appointment.launcher_profile_ref != spec.launcher_profile_ref
        or appointment.launcher_identity != launcher.identity
        or appointment.comparator_ref != spec.comparator_ref
        or appointment.comparator_content_hash != str(spec.comparator_ref.artifact_id)
        or spec.tier not in appointment.supported_tiers
        or spec.planned_physical_units > appointment.allocated_capacity_units
        or action.quota_units != appointment.allocated_capacity_units
        or action.attempt_number > appointment.attempt_limit
    ):
        raise ValueError("n5_replay_child_appointment_not_established")
    action_bytes = _blind_action_bytes(action)
    action_ref = store.put_json(
        action.model_dump(mode="json"),
        artifacts.PutOptions(
            kind="runtime.quality.n5_blind_replay_action",
            media_type="application/json",
            schema=artifacts.SchemaInfo(name=action.schema_version, version="1.0"),
            inputs=[
                artifacts.input_ref_from_artifact_ref(
                    spec.selected_candidate_simulation_n5_input_ref, role="source_input"
                )
            ],
            tenant_context=artifacts.ArtifactTenantContextInfo(
                tenant_id=spec.tenant_id, cell_id=spec.cell_id
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False),
        return_selected_profile=True,
    )
    if store.get_bytes(action_ref) != action_bytes:
        raise ValueError("n5_replay_child_action_persist_mismatch")
    config, _ = _read_n5_versioned_core_json(
        store,
        spec.prepared_configuration_ref,
        PreparedJointSimulationConfiguration,
        kind=N5_REPLAY_PREPARED_CONFIGURATION_KIND,
        schema_version="1.0",
    )
    ledger_path = Path(action.diagnostic_ledger_path)
    if ledger_path.name != "diagnostic-ledger.json" or ledger_path.is_symlink():
        raise ValueError("n5_replay_diagnostic_ledger_invalid")
    with _attempt_lock(ledger_path.parent):
        if (ledger_path.parent / "state.json").is_symlink():
            raise ValueError("n5_replay_attempt_owner_invalid")
        journal = N5ReplayAttemptState.model_validate_json(
            (ledger_path.parent / "state.json").read_bytes()
        )
        if (
            journal.status != "active"
            or journal.replay_run_id != spec.replay_run_id
            or journal.replay_job_id != spec.replay_job_id
            or journal.attempt_number != action.attempt_number
            or journal.quota_units != action.quota_units
            or journal.attempt_limit != appointment.attempt_limit
        ):
            raise ValueError("n5_replay_child_attempt_not_established")
    if not ledger_path.exists() and action.attempt_number != 1:
        raise ValueError("n5_replay_diagnostic_ledger_unavailable")
    budget, middleware = _open_diagnostic_budget(spec, ledger_path, action.quota_units)
    controller = JointSimulationHorizonController(
        method_registry=MethodRegistry._create_fresh(),
        _prepared_configuration=config,
        producer_budget_observer=budget,
    )
    with observe_source_rebuilt_candidate_n5_input(
        store=store,
        controller=controller,
        spec=spec,
        budget=budget,
    ) as (request, scope):
        result = controller.run(request)
        if result.diagnostics.get("physical_work_interruption") and any(
            item.error_type in {"OSError", "FileNotFoundError", "TimeoutError", "ConnectionError"}
            for item in result.physical_work_observations
        ):
            raise N5ReplayInfrastructureError("n5_replay_physical_infrastructure_error")
        result = bind_candidate_n5_content_observation(result, scope=scope)
    observation = read_candidate_n5_content_observation(
        result, input_ref=spec.selected_candidate_simulation_n5_input_ref, expected_request=request
    )
    if observation.completion.status != "recomputed":
        raise ValueError("n5_replay_child_completion_not_established")
    snapshot = middleware.snapshot_safe()
    reservations = snapshot.invocation_reservations
    operation_ids = tuple(
        item.invocation_quota_operation_id for item in result.physical_work_observations
    )
    if (
        len(operation_ids) != spec.planned_physical_units
        or len(set(operation_ids)) != len(operation_ids)
        or any(item is None or item not in reservations for item in operation_ids)
        or any(
            item.invocation_quota_operation_id is None
            or reservations[item.invocation_quota_operation_id].status != "completed"
            or reservations[item.invocation_quota_operation_id].purpose != "diagnostic"
            or reservations[item.invocation_quota_operation_id].run_id != spec.replay_run_id
            or reservations[item.invocation_quota_operation_id].request_digest
            != item.invocation_quota_request_digest
            or reservations[item.invocation_quota_operation_id].profile_digest
            != item.invocation_quota_profile_digest
            for item in result.physical_work_observations
        )
    ):
        raise ValueError("n5_replay_child_accounting_not_established")
    result_ref = persist_joint_simulation_result(
        result,
        store=store,
        tenant_context=artifacts.ArtifactTenantContextInfo(
            tenant_id=spec.tenant_id, cell_id=spec.cell_id
        ),
    )
    fenced_snapshot, ledger_bytes = _fenced_ledger_snapshot(ledger_path)
    if fenced_snapshot != snapshot:
        raise ValueError("n5_replay_child_ledger_changed_during_capture")
    ledger_ref = store.put_bytes(
        ledger_bytes,
        artifacts.PutOptions(
            kind="runtime.quality.n5_diagnostic_ledger_snapshot",
            media_type="application/octet-stream",
            schema=artifacts.SchemaInfo(
                name="polisyos.scientist.budget_ledger.snapshot",
                version=fenced_snapshot.schema_version,
            ),
            inputs=[artifacts.input_ref_from_artifact_ref(result_ref, role="replay_result")],
            tenant_context=artifacts.ArtifactTenantContextInfo(
                tenant_id=spec.tenant_id, cell_id=spec.cell_id
            ),
        ),
        return_selected_profile=True,
    )
    return N5BlindReplayExecution(
        pid=os.getpid(),
        replay_run_id=spec.replay_run_id,
        replay_job_id=spec.replay_job_id,
        attempt_number=action.attempt_number,
        action_hash=security.raw_content_hash(action_bytes),
        action_ref=action_ref,
        result_ref=result_ref,
        ledger_owner=middleware.settlement_owner_identity,
        ledger_revision=snapshot.revision,
        ledger_hash=security.raw_content_hash(ledger_bytes),
        ledger_snapshot_ref=ledger_ref,
        operation_ids=tuple(item for item in operation_ids if item is not None),
    )


def run_appointed_n5_replay(
    *,
    resolver: N5ReplayAppointmentResolver,
    query: N5ReplayUseQuery,
    workspace: Path | None = None,
    launcher_signing_service: N5ReplayLauncherSigningService | None = None,
) -> tuple[N5ReplayCandidateComparison, artifacts.ArtifactRef]:
    """Launch one appointed demonstration child and reproject both real results.

    The workspace is created exclusively and retains the action and diagnostic
    ledger. A mismatch is final; this function makes no retry or authority claim.
    """
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.runtime.quality.generation_cycle import load_joint_simulation_result
    from polisyos.runtime.quality.joint_simulation_horizon import (
        PreparedJointSimulationConfiguration,
        _physical_invocation_binding,
    )
    from polisyos.runtime.quality.n5_candidate_content import _prepared_image_descriptor
    from polisyos.runtime.quality.n5_execution_basis import (
        N5ProductionImage,
        capture_n5_production_image,
        exact_n5_content_bytes,
        exact_n5_content_hash,
    )
    from polisyos.runtime.quality.n5_execution_profile import N5NativeExecutionProfile
    from polisyos.runtime.quality.n5_replay_appointment import (
        N5_REPLAY_EXECUTION_PROFILE_KIND,
        N5_REPLAY_PREPARED_CONFIGURATION_KIND,
        N5_REPLAY_PRODUCTION_IMAGE_KIND,
        N5AppointedReplayRecordV2,
        N5ReplayAppointment,
        N5ReplayAppointmentResolver,
        N5ReplayAppointmentVerification,
        N5ReplayComparatorProfile,
        _read_n5_versioned_core_json,
        _trust,
        build_n5_replay_verification_cache_key_v2,
    )
    from polisyos.runtime.quality.n5_replay_numerical_projection import (
        compare_n5_numerical_projection_bytes,
        project_n5_numerical_result_v1,
    )

    if type(resolver) is not N5ReplayAppointmentResolver:
        raise ValueError("n5_replay_resolver_not_canonical")
    store = resolver._store
    if type(store) is not FileSystemCAS:
        raise ValueError("n5_replay_source_store_not_bound")
    admission = resolver.resolve_executable(query)
    if (
        admission.status != "appointed"
        or admission.launch_spec is None
        or admission.appointment_resolution.trust_root_class != "demonstration_test_root"
    ):
        raise ValueError("n5_replay_demonstration_appointment_not_established")
    spec = admission.launch_spec
    current_spec = spec
    started_at = resolver._clock()
    state = resolver._current_state()
    if (
        state.component is None
        or state.config.trust_root_class != "demonstration_test_root"
        or _trust(state.config).snapshot_hash
        != admission.appointment_resolution.trust_snapshot_hash
    ):
        raise ValueError("n5_replay_deployment_changed_before_launch")
    producer, _, _, _ = resolver._signed(
        query.original_producer_evidence_ref,
        N5OriginalProducerSealV2,
        "original_producer",
        _trust(state.config),
    )
    original_execution, request, original = _reopen_verified_original(
        store=store, original_execution_ref=producer.original_execution_ref, scope=spec.scope
    )
    if (
        artifacts.artifact_ref_identity_key(original_execution.source_input_ref)
        != artifacts.artifact_ref_identity_key(spec.selected_candidate_simulation_n5_input_ref)
        or original_execution.source_run_id != spec.source_run_id
        or original_execution.source_job_id != spec.source_job_id
        or original_execution.producer_run_id != spec.original_run_id
        or original_execution.producer_job_id != spec.original_job_id
    ):
        raise ValueError("n5_replay_selected_source_mismatch")
    if n5_replay_seed_schedule_hash(request) != spec.seed_schedule_hash:
        raise ValueError("n5_replay_seed_schedule_mismatch")
    config, _ = _read_n5_versioned_core_json(
        store,
        spec.prepared_configuration_ref,
        PreparedJointSimulationConfiguration,
        kind=N5_REPLAY_PREPARED_CONFIGURATION_KIND,
        schema_version="1.0",
    )
    original_bytes = project_n5_numerical_result_v1(
        original,
        input_ref=original_execution.source_input_ref,
        expected_request=request,
        prepared_configuration=config,
        store=store,
    ).numerical_bytes()
    appointment, _, _, _ = resolver._signed(
        state.config.appointment_evidence_ref,
        N5ReplayAppointment,
        "appointment_issuer",
        _trust(state.config),
    )
    if launcher_signing_service is not None and (
        type(launcher_signing_service) is not N5ReplayLauncherSigningService
        or launcher_signing_service.signer.key_id != appointment.launcher_key_id
        or not launcher_signing_service.launcher_instance_id
        or launcher_signing_service.launcher_instance_id == producer.producer_instance_id
    ):
        raise ValueError("n5_replay_launcher_signing_service_not_appointed")
    if (
        security.raw_content_hash(original_bytes) != producer.numerical_result_projection_hash
        or store.get_bytes(producer.numerical_result_projection_ref) != original_bytes
    ):
        raise ValueError("n5_replay_original_projection_not_reconciled")
    profile, _ = _read_n5_versioned_core_json(
        store,
        spec.execution_profile_ref,
        N5NativeExecutionProfile,
        kind=N5_REPLAY_EXECUTION_PROFILE_KIND,
        schema_version="1.0",
    )
    image, _ = _read_n5_versioned_core_json(
        store,
        spec.production_image_ref,
        N5ProductionImage,
        kind=N5_REPLAY_PRODUCTION_IMAGE_KIND,
        schema_version="1.0",
    )
    current_image = capture_n5_production_image(
        root=Path(__file__).resolve().parents[4],
        admitted_profile=_prepared_image_descriptor(config),
    )
    if exact_n5_content_bytes(current_image) != exact_n5_content_bytes(image):
        raise ValueError("n5_replay_current_source_image_changed")
    cache_key = build_n5_replay_verification_cache_key_v2(
        declared_numerical_intent_content_hash=spec.declared_numerical_intent_content_hash,
        declared_callable_content_hash=spec.declared_callable_content_hash,
        native_profile=profile,
        production_image=image,
        comparator_ref=spec.comparator_ref,
        tier=spec.tier,
        seed_schedule_hash=spec.seed_schedule_hash,
        numerical_result_projection_hash=security.raw_content_hash(original_bytes),
    )
    comparator = N5ReplayComparatorProfile.model_validate(
        artifacts.load_core_json_artifact(store, spec.comparator_ref)
    )
    claim_key = exact_n5_content_hash(
        {"scope": spec.scope.model_dump(mode="json"), "key": cache_key.model_dump(mode="json")}
    ).removeprefix("sha256:")
    claim_root = store.root.parent / ".n5-replay-attempts"
    if claim_root.is_symlink():
        raise ValueError("n5_replay_attempt_owner_invalid")
    actual_workspace = claim_root / claim_key
    if workspace is not None and workspace.absolute() != actual_workspace.absolute():
        raise ValueError("n5_replay_attempt_workspace_mismatch")
    workspace = actual_workspace
    # The pointer is only discovery: cheaply reject missing or changed owner
    # state before the common assigned-launcher identity gate.
    historical_record = None
    pointer_path = workspace / "completed-evidence.json"
    has_pointer, _ = _existing_execution_precondition(
        workspace,
        key=claim_key,
        spec=current_spec,
        publishing=launcher_signing_service is not None,
    )
    if has_pointer:
        with _attempt_lock(workspace):
            if pointer_path.is_symlink():
                raise ValueError("n5_replay_completed_pointer_invalid")
            evidence_ref = artifacts.ArtifactRef.model_validate_json(pointer_path.read_bytes())
        trust = _trust(state.config)
        historical_record, _, launcher_key, launcher = resolver._signed(
            evidence_ref, N5AppointedReplayRecordV2, "appointed_launcher", trust
        )
        old_appointment, old_appointment_ref, issuer_key, issuer = resolver._signed(
            historical_record.appointment_evidence_ref,
            N5ReplayAppointment,
            "appointment_issuer",
            trust,
        )
        old_check, _, admin_key, admin = resolver._signed(
            historical_record.appointment_verification_evidence_ref,
            N5ReplayAppointmentVerification,
            "deployment_administrator",
            trust,
        )
        old_producer, _, producer_key, old_producer_role = resolver._signed(
            historical_record.original_producer_evidence_ref,
            N5OriginalProducerSealV2,
            "original_producer",
            trust,
        )
        historical_execution = artifacts.validate_core_model_json_artifact(
            N5BlindReplayExecution, store, historical_record.child_execution_ref
        )
        historical_action = _read_blind_action(
            store, historical_execution.action_ref, historical_execution.action_hash
        )
        old_spec = historical_action.launch_spec
        if (
            historical_record.scope != current_spec.scope
            or old_appointment.scope != current_spec.scope
            or old_check.scope != current_spec.scope
            or old_producer.scope != current_spec.scope
            or old_spec.scope != current_spec.scope
            or old_appointment_ref != historical_record.appointment_ref
            or old_check.appointment_ref != old_appointment_ref
            or old_check.appointment_content_hash != str(old_appointment_ref.artifact_id)
            or old_check.launcher_profile_ref != old_spec.launcher_profile_ref
            or old_check.deployed_component_provenance_ref
            != historical_action.component_provenance_ref
            or old_check.current_trust_snapshot_hash
            != _trust(historical_action.demonstration_trust).snapshot_hash
            or historical_action.demonstration_trust.appointment_evidence_ref
            != historical_record.appointment_evidence_ref
            or historical_action.demonstration_trust.verification_evidence_ref
            != historical_record.appointment_verification_evidence_ref
            or launcher_key != old_appointment.launcher_key_id
            or launcher.identity != old_appointment.launcher_identity
            or issuer.organization != current_spec.scope.accepting_organization
            or len({launcher_key, issuer_key, admin_key, producer_key}) != 4
            or len({launcher.identity, issuer.identity, admin.identity, old_producer_role.identity})
            != 4
            or any(
                (left.organization, left.function) == (right.organization, right.function)
                for left, right in (
                    (issuer, admin),
                    (issuer, launcher),
                    (admin, launcher),
                    (issuer, old_producer_role),
                    (admin, old_producer_role),
                    (launcher, old_producer_role),
                )
            )
            or old_producer.original_execution_ref != historical_record.original_execution_ref
            or old_producer.original_run_id != old_spec.original_run_id
            or old_producer.original_job_id != old_spec.original_job_id
            or old_producer.numerical_intent_ref != old_spec.numerical_intent_ref
            or old_producer.numerical_intent_hash != old_spec.numerical_intent_hash
            or old_producer.execution_profile_ref != old_spec.execution_profile_ref
            or old_producer.seed_schedule_hash != old_spec.seed_schedule_hash
            or old_producer.numerical_projection_schema != comparator.numerical_projection_schema
            or old_producer.produced_at > historical_record.started_at
            or set(issuer.roles) != {"appointment_issuer"}
            or set(admin.roles) != {"deployment_administrator"}
            or set(launcher.roles) != {"appointed_launcher"}
            or any(
                row.identity in {issuer.identity, admin.identity, launcher.identity}
                or (row.organization, row.function)
                in {
                    (issuer.organization, issuer.function),
                    (admin.organization, admin.function),
                    (launcher.organization, launcher.function),
                }
                for row in trust.by_key.values()
                if "result_user" in row.roles
            )
            or old_appointment.launcher_profile_ref != old_spec.launcher_profile_ref
            or old_appointment.comparator_ref != old_spec.comparator_ref
            or old_appointment.comparator_content_hash != str(old_spec.comparator_ref.artifact_id)
            or old_spec.tier not in old_appointment.supported_tiers
            or historical_record.launch_spec_hash
            != security.raw_content_hash(security.canonical_statement_bytes(old_spec))
            or historical_record.numerical_intent_hash != old_spec.numerical_intent_hash
            or historical_record.execution_profile_ref != old_spec.execution_profile_ref
            or historical_record.comparator_ref != old_spec.comparator_ref
            or historical_record.tier != old_spec.tier
            or historical_record.seed_schedule_hash != old_spec.seed_schedule_hash
            or historical_record.replay_run_id != old_spec.replay_run_id
            or historical_record.replay_job_id != old_spec.replay_job_id
            or historical_record.launcher_instance_id == old_producer.producer_instance_id
            or historical_record.attempt_number > old_appointment.attempt_limit
            or historical_record.planned_physical_units != old_spec.planned_physical_units
            or historical_record.completed_physical_units != old_spec.planned_physical_units
            or historical_action.quota_units != old_appointment.allocated_capacity_units
            or not (
                old_appointment.valid_from
                <= historical_record.started_at
                <= historical_record.finished_at
                < old_appointment.valid_until
            )
            or not (
                old_check.valid_from
                <= historical_record.started_at
                <= historical_record.finished_at
                < old_check.valid_until
            )
            or historical_record.finished_at > resolver._clock()
        ):
            raise ValueError("n5_replay_historical_record_not_reconciled")
        old_execution, old_request, old_original = _reopen_verified_original(
            store=store,
            original_execution_ref=historical_record.original_execution_ref,
            scope=old_spec.scope,
        )
        old_config, _ = _read_n5_versioned_core_json(
            store,
            old_spec.prepared_configuration_ref,
            PreparedJointSimulationConfiguration,
            kind=N5_REPLAY_PREPARED_CONFIGURATION_KIND,
            schema_version="1.0",
        )
        old_original_bytes = project_n5_numerical_result_v1(
            old_original,
            input_ref=old_execution.source_input_ref,
            expected_request=old_request,
            prepared_configuration=old_config,
            store=store,
        ).numerical_bytes()
        old_profile, _ = _read_n5_versioned_core_json(
            store,
            old_spec.execution_profile_ref,
            N5NativeExecutionProfile,
            kind=N5_REPLAY_EXECUTION_PROFILE_KIND,
            schema_version="1.0",
        )
        old_image, _ = _read_n5_versioned_core_json(
            store,
            old_spec.production_image_ref,
            N5ProductionImage,
            kind=N5_REPLAY_PRODUCTION_IMAGE_KIND,
            schema_version="1.0",
        )
        old_key = build_n5_replay_verification_cache_key_v2(
            declared_numerical_intent_content_hash=old_spec.declared_numerical_intent_content_hash,
            declared_callable_content_hash=old_spec.declared_callable_content_hash,
            native_profile=old_profile,
            production_image=old_image,
            comparator_ref=old_spec.comparator_ref,
            tier=old_spec.tier,
            seed_schedule_hash=n5_replay_seed_schedule_hash(old_request),
            numerical_result_projection_hash=security.raw_content_hash(old_original_bytes),
        )
        if (
            old_key != cache_key
            or old_spec.seed_schedule_hash != n5_replay_seed_schedule_hash(old_request)
            or old_producer.numerical_result_projection_hash
            != security.raw_content_hash(old_original_bytes)
            or store.get_bytes(old_producer.numerical_result_projection_ref) != old_original_bytes
            or old_execution.source_input_ref != old_spec.selected_candidate_simulation_n5_input_ref
            or old_execution.source_run_id != old_spec.source_run_id
            or old_execution.source_job_id != old_spec.source_job_id
            or old_execution.producer_run_id != old_spec.original_run_id
            or old_execution.producer_job_id != old_spec.original_job_id
            or old_execution.numerical_intent_ref != old_spec.numerical_intent_ref
            or old_execution.execution_profile_ref != old_spec.execution_profile_ref
        ):
            raise ValueError("n5_replay_historical_semantic_identity_mismatch")
        spec, appointment, producer = old_spec, old_appointment, old_producer
        original_execution, request, original = old_execution, old_request, old_original
        config, original_bytes = old_config, old_original_bytes
    terminal_attempt = None
    state_path = workspace / "state.json"
    if (
        launcher_signing_service is not None or historical_record is not None
    ) and state_path.exists():
        with _attempt_lock(workspace):
            if state_path.is_symlink():
                raise ValueError("n5_replay_attempt_owner_invalid")
            previous = N5ReplayAttemptState.model_validate_json(state_path.read_bytes())
            if previous.status in {"equal", "mismatch"}:
                if (
                    previous.key != claim_key
                    or previous.replay_run_id != spec.replay_run_id
                    or previous.replay_job_id != spec.replay_job_id
                    or previous.started_at is None
                    or previous.finished_at is None
                ):
                    raise ValueError("n5_replay_completed_publication_not_recoverable")
                terminal_attempt = previous
    if historical_record is not None and terminal_attempt is None:
        raise ValueError("n5_replay_completed_attempt_not_established")
    attempt = terminal_attempt or _begin_attempt(
        workspace,
        key=claim_key,
        spec=spec,
        quota=appointment.allocated_capacity_units,
        limit=appointment.attempt_limit,
    )
    _preflight_existing_execution(
        workspace,
        attempt=attempt,
        spec=current_spec,
        cas_root=str(store.root),
        recorded_profile=profile,
        recorded_image=image,
    )
    if attempt.status == "active":
        attempt = _settle_attempt(workspace, attempt, started_at=started_at)
    budget, _middleware = _open_diagnostic_budget(
        spec, workspace / "diagnostic-ledger.json", appointment.allocated_capacity_units
    )
    if attempt.status == "active":
        capacity = budget.admit_diagnostic_invocation_only()
        if (
            capacity.protected_remaining_units is None
            or capacity.protected_remaining_units < spec.planned_physical_units
        ):
            _settle_attempt(workspace, attempt, status="unknown")
            raise ValueError("n5_replay_attempt_capacity_not_established")
    action = N5BlindReplayAction(
        launch_spec=spec,
        demonstration_trust=state.config,
        component_provenance_ref=state.component.component_provenance_ref,
        cas_root=str(store.root),
        diagnostic_ledger_path=str(workspace / "diagnostic-ledger.json"),
        quota_units=appointment.allocated_capacity_units,
        attempt_number=attempt.attempt_number,
    )
    action_path = workspace / f"blind-action-{attempt.attempt_number}.json"
    if attempt.status in {"executed", "equal", "mismatch"}:
        if attempt.execution_ref is None or attempt.child_pid is None:
            raise ValueError("n5_replay_executed_receipt_missing")
        execution = artifacts.validate_core_model_json_artifact(
            N5BlindReplayExecution, store, attempt.execution_ref
        )
        action = _read_blind_action(store, execution.action_ref, execution.action_hash)
        if (
            action.launch_spec != spec
            or action.quota_units != appointment.allocated_capacity_units
            or action.attempt_number != attempt.attempt_number
            or action.diagnostic_ledger_path != str(workspace / "diagnostic-ledger.json")
        ):
            raise ValueError("n5_replay_recovered_action_mismatch")
        child_pid = attempt.child_pid
        observed_processes = {attempt.executor_pid: attempt.executor_created_us}
    else:
        action_path.write_text(action.model_dump_json(), encoding="utf-8")
        executable = Path(__file__).resolve().parents[4] / "tools" / "authority"
        # Fixed repository authority executable and argv; no shell or caller command.
        try:
            child_pid, returncode, stdout, observed_processes = _run_managed_worker(
                [
                    str(executable),
                    "runtime",
                    "scientist",
                    "n5-blind-replay",
                    "--action",
                    str(action_path),
                ],
                workspace,
                f"-{attempt.attempt_number}",
            )
        except _WorkerLaunchError as exc:
            (workspace / f"child-launch-error-{attempt.attempt_number}.log").write_text(
                repr(exc), encoding="utf-8"
            )
            failed_snapshot, failed_bytes = _fenced_ledger_snapshot(
                workspace / "diagnostic-ledger.json"
            )
            if failed_snapshot.revision != capacity.source_revision:
                _settle_attempt(workspace, attempt, status="unknown")
            else:
                _settle_attempt(
                    workspace,
                    attempt,
                    status="infrastructure_error",
                    ledger_hash=security.raw_content_hash(failed_bytes),
                    ledger_revision=failed_snapshot.revision,
                )
            raise
        except _WorkerLifecycleError as exc:
            _settle_attempt(workspace, attempt, status="unknown", child_pid=exc.pid)
            raise ValueError(f"n5_replay_child_{exc}") from exc
        except BaseException:
            _settle_attempt(workspace, attempt, status="unknown")
            raise
        if returncode != 0:
            try:
                failure = N5ReplayInfrastructureFailure.model_validate_json(
                    _worker_result_payload(stdout)
                )
                _require_observed_executor(failure.pid, observed_processes)
                if (
                    failure.attempt_number != attempt.attempt_number
                    or failure.action_hash != security.raw_content_hash(_blind_action_bytes(action))
                ):
                    raise ValueError("n5_replay_infrastructure_failure_unbound")
                recovered_budget, _ = _open_diagnostic_budget(
                    spec, workspace / "diagnostic-ledger.json", appointment.allocated_capacity_units
                )
                remaining = recovered_budget.admit_diagnostic_invocation_only()
                if (
                    remaining.protected_remaining_units is None
                    or remaining.protected_remaining_units < spec.planned_physical_units
                ):
                    raise ValueError("n5_replay_attempt_capacity_not_established")
                failed_snapshot, failed_bytes = _fenced_ledger_snapshot(
                    workspace / "diagnostic-ledger.json"
                )
                if failed_snapshot.revision != remaining.source_revision:
                    raise ValueError("n5_replay_attempt_ledger_changed")
            except (OSError, RuntimeError, TypeError, ValueError):
                _settle_attempt(workspace, attempt, status="unknown", child_pid=child_pid)
            else:
                _settle_attempt(
                    workspace,
                    attempt,
                    status="infrastructure_error",
                    child_pid=child_pid,
                    ledger_hash=security.raw_content_hash(failed_bytes),
                    ledger_revision=failed_snapshot.revision,
                )
            raise ValueError("n5_replay_child_execution_failed")
        execution = N5BlindReplayExecution.model_validate_json(_worker_result_payload(stdout))
    executor_created_us = _require_observed_executor(execution.pid, observed_processes)
    if (
        execution.replay_run_id != spec.replay_run_id
        or execution.replay_job_id != spec.replay_job_id
        or execution.attempt_number != attempt.attempt_number
        or execution.action_hash != security.raw_content_hash(_blind_action_bytes(action))
        or _read_blind_action(store, execution.action_ref, execution.action_hash) != action
        or artifacts.artifact_ref_identity_key(execution.result_ref)
        == artifacts.artifact_ref_identity_key(original_execution.result_ref)
    ):
        raise ValueError("n5_replay_child_execution_not_bound")
    current = resolver.resolve_executable(query)
    if (
        current.status != "appointed"
        or current.launch_spec != current_spec
        or current.appointment_resolution.trust_snapshot_hash
        != admission.appointment_resolution.trust_snapshot_hash
        or current.appointment_resolution.appointment_ref
        != admission.appointment_resolution.appointment_ref
        or current.appointment_resolution.verification_ref
        != admission.appointment_resolution.verification_ref
    ):
        raise ValueError("n5_replay_appointment_changed_during_execution")
    replay = load_joint_simulation_result(
        execution.result_ref, store=store, expected_request=request
    )
    snapshot, ledger_bytes = _fenced_ledger_snapshot(workspace / "diagnostic-ledger.json")
    ledger_manifest = store.get_manifest(execution.ledger_snapshot_ref)
    observed = replay.physical_work_observations
    if (
        snapshot.revision != execution.ledger_revision
        or (
            attempt.status in {"executed", "equal", "mismatch"}
            and attempt.ledger_hash != security.raw_content_hash(ledger_bytes)
        )
        or execution.ledger_snapshot_ref.kind != "runtime.quality.n5_diagnostic_ledger_snapshot"
        or execution.ledger_snapshot_ref.media_type != "application/octet-stream"
        or execution.ledger_snapshot_ref.manifest_profile_sha256 is None
        or ledger_manifest.artifact_schema is None
        or ledger_manifest.artifact_schema.name != "polisyos.scientist.budget_ledger.snapshot"
        or ledger_manifest.artifact_schema.version != snapshot.schema_version
        or not store.verify(execution.ledger_snapshot_ref).ok
        or execution.ledger_hash != security.raw_content_hash(ledger_bytes)
        or str(execution.ledger_snapshot_ref.artifact_id) != execution.ledger_hash
        or store.get_bytes(execution.ledger_snapshot_ref) != ledger_bytes
        or execution.ledger_owner
        != (snapshot.ledger_id, snapshot.canonical_contract, snapshot.coordination_mode)
        or snapshot.producer_settlements
        or len(snapshot.invocation_reservations) > appointment.allocated_capacity_units
        or any(
            row.status not in {"completed", "failed"}
            for row in snapshot.invocation_reservations.values()
        )
        or len(observed) != spec.planned_physical_units
        or len(set(execution.operation_ids)) != len(observed)
        or set(execution.operation_ids) != {row.invocation_quota_operation_id for row in observed}
        or any(
            row.invocation_quota_operation_id not in snapshot.invocation_reservations
            or snapshot.invocation_reservations[row.invocation_quota_operation_id].status
            != "completed"
            or snapshot.invocation_reservations[row.invocation_quota_operation_id].purpose
            != "diagnostic"
            or snapshot.invocation_reservations[row.invocation_quota_operation_id].run_id
            != spec.replay_run_id
            or snapshot.invocation_reservations[row.invocation_quota_operation_id].request_digest
            != row.invocation_quota_request_digest
            or snapshot.invocation_reservations[row.invocation_quota_operation_id].profile_digest
            != row.invocation_quota_profile_digest
            or _physical_invocation_binding(
                row.invocation_id, row.physical_spec_ref, row.effective_seed
            )
            != (row.invocation_quota_operation_id, row.invocation_quota_request_digest)
            for row in observed
        )
    ):
        raise ValueError("n5_replay_parent_accounting_not_reconciled")
    inputs = [
        artifacts.input_ref_from_artifact_ref(
            original_execution.result_ref, role="original_result"
        ),
        artifacts.input_ref_from_artifact_ref(execution.result_ref, role="replay_result"),
        artifacts.input_ref_from_artifact_ref(
            execution.ledger_snapshot_ref, role="diagnostic_ledger"
        ),
        artifacts.input_ref_from_artifact_ref(execution.action_ref, role="blind_action"),
    ]
    canon = CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False)
    tenant = artifacts.ArtifactTenantContextInfo(tenant_id=spec.tenant_id, cell_id=spec.cell_id)

    def persist(kind: str, payload: object) -> artifacts.ArtifactRef:
        return store.put_json(
            payload,
            artifacts.PutOptions(
                kind=kind,
                media_type="application/json",
                inputs=inputs,
                schema=artifacts.SchemaInfo(name=kind, version="1.0"),
                tenant_context=tenant,
            ),
            canon_spec=canon,
            return_selected_profile=True,
        )

    execution_ref = attempt.execution_ref
    if attempt.status == "active":
        execution_ref = persist(
            "runtime.quality.n5_blind_replay_execution", execution.model_dump(mode="json")
        )
        attempt = _settle_attempt(
            workspace,
            attempt,
            status="executed",
            finished_at=resolver._clock(),
            child_pid=child_pid,
            executor_pid=execution.pid,
            executor_created_us=executor_created_us,
            execution_ref=execution_ref,
            ledger_hash=security.raw_content_hash(ledger_bytes),
            ledger_revision=snapshot.revision,
        )
    if execution_ref is None:
        raise ValueError("n5_replay_executed_receipt_missing")
    reopened_execution, reopened_request, reopened_original = _reopen_verified_original(
        store=store, original_execution_ref=producer.original_execution_ref, scope=spec.scope
    )
    if reopened_execution != original_execution or exact_n5_content_bytes(
        reopened_request
    ) != exact_n5_content_bytes(request):
        raise ValueError("n5_replay_original_execution_changed")
    refreshed_original_bytes = project_n5_numerical_result_v1(
        reopened_original,
        input_ref=reopened_execution.source_input_ref,
        expected_request=reopened_request,
        prepared_configuration=config,
        store=store,
    ).numerical_bytes()
    if refreshed_original_bytes != original_bytes:
        raise ValueError("n5_replay_original_projection_changed")
    replay_bytes = project_n5_numerical_result_v1(
        replay,
        input_ref=original_execution.source_input_ref,
        expected_request=request,
        prepared_configuration=config,
        store=store,
    ).numerical_bytes()
    comparison = compare_n5_numerical_projection_bytes(
        refreshed_original_bytes, replay_bytes, comparator=comparator
    )
    result = N5ReplayCandidateComparison(
        status=comparison.status,
        parent_pid=os.getpid(),
        child_pid=execution.pid,
        attempt_key=claim_key,
        original_result_ref=original_execution.result_ref,
        replay_result_ref=execution.result_ref,
        child_execution_ref=execution_ref,
        original_projection_hash=comparison.original_hash,
        replay_projection_hash=comparison.replay_hash,
        diagnostic_ledger_hash=security.raw_content_hash(ledger_bytes),
        completed_units=len(observed),
    )
    inputs.append(artifacts.input_ref_from_artifact_ref(execution_ref, role="child_execution"))
    if terminal_attempt is None:
        result_ref = persist(
            "runtime.quality.n5_replay_candidate_comparison", result.model_dump(mode="json")
        )
        attempt = _settle_attempt(
            workspace, attempt, status=comparison.status, comparison_ref=result_ref
        )
    else:
        if terminal_attempt.comparison_ref is None:
            raise ValueError("n5_replay_completed_comparison_missing")
        result_ref = terminal_attempt.comparison_ref
        saved = artifacts.validate_core_model_json_artifact(
            N5ReplayCandidateComparison, store, result_ref
        )
        if saved.model_copy(update={"parent_pid": result.parent_pid}) != result:
            raise ValueError("n5_replay_completed_comparison_changed")
        result = saved
    if historical_record is not None:
        if (
            terminal_attempt is None
            or historical_record.candidate_comparison_ref != result_ref
            or historical_record.child_execution_ref != execution_ref
            or historical_record.diagnostic_ledger_snapshot_ref != execution.ledger_snapshot_ref
            or historical_record.replay_result_projection_hash
            != security.raw_content_hash(replay_bytes)
            or historical_record.replay_result_projection_ref is None
            or not store.verify(historical_record.replay_result_projection_ref).ok
            or store.get_bytes(historical_record.replay_result_projection_ref) != replay_bytes
            or historical_record.attempt_number != attempt.attempt_number
            or historical_record.started_at != attempt.started_at
            or historical_record.finished_at != attempt.finished_at
            or resolver.resolve_executable(query) != admission
        ):
            raise ValueError("n5_replay_completed_evidence_not_reconciled")
        return result, result_ref
    if launcher_signing_service is not None:
        from polisyos.core import FileSystemSignedArtifactEvidenceRepository

        service = launcher_signing_service
        if (
            type(service) is not N5ReplayLauncherSigningService
            or service.signer.key_id != appointment.launcher_key_id
            or not service.launcher_instance_id
            or attempt.attempt_number > appointment.attempt_limit
            or resolver.resolve_executable(query) != admission
        ):
            raise ValueError("n5_replay_launcher_signing_service_not_appointed")
        replay_projection_ref = store.put_bytes(
            replay_bytes,
            artifacts.PutOptions(
                kind="runtime.quality.n5_numerical_result_projection_bytes",
                media_type="application/octet-stream",
                inputs=inputs,
                schema=artifacts.SchemaInfo(
                    name="runtime.quality.n5_numerical_result_projection_bytes", version="1.0"
                ),
                tenant_context=tenant,
            ),
            return_selected_profile=True,
        )
        record = N5AppointedReplayRecordV2(
            scope=spec.scope,
            appointment_ref=admission.appointment_resolution.appointment_ref,
            launch_spec_hash=security.raw_content_hash(security.canonical_statement_bytes(spec)),
            replay_run_id=spec.replay_run_id,
            replay_job_id=spec.replay_job_id,
            launcher_instance_id=service.launcher_instance_id,
            numerical_intent_hash=spec.numerical_intent_hash,
            execution_profile_ref=spec.execution_profile_ref,
            comparator_ref=spec.comparator_ref,
            tier=spec.tier,
            seed_schedule_hash=spec.seed_schedule_hash,
            attempt_number=attempt.attempt_number,
            planned_physical_units=spec.planned_physical_units,
            completed_physical_units=len(observed),
            outcome="completed",
            replay_result_projection_ref=replay_projection_ref,
            replay_result_projection_hash=security.raw_content_hash(replay_bytes),
            publication_id=uuid.uuid4().hex,
            original_producer_evidence_ref=query.original_producer_evidence_ref,
            original_execution_ref=producer.original_execution_ref,
            appointment_evidence_ref=state.config.appointment_evidence_ref,
            appointment_verification_evidence_ref=state.config.verification_evidence_ref,
            candidate_comparison_ref=result_ref,
            child_execution_ref=execution_ref,
            diagnostic_ledger_snapshot_ref=execution.ledger_snapshot_ref,
            started_at=attempt.started_at,
            finished_at=attempt.finished_at,
        )
        signed = FileSystemSignedArtifactEvidenceRepository(store).persist_signed(
            blob_bytes=security.canonical_statement_bytes(record),
            write_options=artifacts.ArtifactWriteOptions(
                kind="runtime.quality.n5_appointed_replay_record",
                media_type="application/octet-stream",
            ),
            signer=service.signer,
            signing_profile_ref=service.signing_profile_ref,
            signer_provenance_ref=service.signer_provenance_ref,
        )
        evidence_ref = artifacts.profile_bound_ref(store, signed.evidence_record_ref)
        if resolver.verify_launcher_record(query, evidence_ref).status != "authenticated_record":
            raise ValueError("n5_replay_published_record_not_authenticated")
        with _attempt_lock(workspace):
            artifacts.write_bytes_atomic(
                workspace / "completed-evidence.json",
                evidence_ref.model_dump_json().encode("utf-8"),
                durable_parent=True,
            )
    return result, result_ref


def preflight_candidate_n5_replay(
    *,
    scope: CandidateN5ContentRun,
    spec: N5BlindReplayLaunchSpecV2,
    store: CoreJSONArtifactStore,
    budget: ProducerBudgetObserver,
) -> N5DiagnosticCapacityObservation:
    """Reconcile actual selected inputs and whole-plan capacity before a call.

    This observation is not a permit; actual calls must still reserve and
    settle through the controller's diagnostic budget observer.
    """
    from polisyos.runtime.quality.joint_simulation_horizon import (
        PreparedJointSimulationConfiguration,
    )
    from polisyos.runtime.quality.n5_candidate_content import CandidateN5ContentRun
    from polisyos.runtime.quality.n5_execution_basis import (
        N5ProductionImage,
        exact_n5_content_bytes,
        exact_n5_content_hash,
        snapshot_n5_callable_content_v3,
    )
    from polisyos.runtime.quality.n5_execution_profile import (
        N5NativeExecutionProfile,
        reconcile_recorded_n5_profile_current_bytes,
    )
    from polisyos.runtime.quality.n5_replay_appointment import (
        N5_REPLAY_EXECUTION_PROFILE_KIND,
        N5_REPLAY_PREPARED_CONFIGURATION_KIND,
        N5_REPLAY_PRODUCTION_IMAGE_KIND,
        N5BlindReplayLaunchSpecV2,
        _read_n5_versioned_core_json,
    )
    from polisyos.scientist.orchestration.engine import ProducerBudgetObserver

    if type(scope) is not CandidateN5ContentRun or type(spec) is not N5BlindReplayLaunchSpecV2:
        raise ValueError("n5_replay_preflight_input_untyped")
    spec = N5BlindReplayLaunchSpecV2.model_validate(spec.model_dump(mode="python"))
    if (
        type(budget) is not ProducerBudgetObserver
        or scope.controller._producer_budget_observer is not budget
    ):
        raise ValueError("n5_replay_budget_owner_not_established")
    if (
        artifacts.artifact_ref_identity_key(scope.input_ref)
        != artifacts.artifact_ref_identity_key(spec.selected_candidate_simulation_n5_input_ref)
        or scope.capture is None
        or scope.configuration is None
        or scope.production_image is None
        or scope.profile is None
        or len(scope.planned_units) != spec.planned_physical_units
        or n5_replay_seed_schedule_hash(scope.request) != spec.seed_schedule_hash
        or scope.capture.numerical_intent_content_hash
        != spec.declared_numerical_intent_content_hash
    ):
        raise ValueError("n5_replay_selected_plan_mismatch")
    callable_content = snapshot_n5_callable_content_v3(scope.selected_callable)
    if (
        callable_content is None
        or security.raw_content_hash(callable_content.encode())
        != spec.declared_callable_content_hash
    ):
        raise ValueError("n5_replay_selected_callable_mismatch")

    image, image_raw = _read_n5_versioned_core_json(
        store,
        spec.production_image_ref,
        N5ProductionImage,
        kind=N5_REPLAY_PRODUCTION_IMAGE_KIND,
        schema_version="1.0",
    )
    config, config_raw = _read_n5_versioned_core_json(
        store,
        spec.prepared_configuration_ref,
        PreparedJointSimulationConfiguration,
        kind=N5_REPLAY_PREPARED_CONFIGURATION_KIND,
        schema_version="1.0",
    )
    profile, _ = _read_n5_versioned_core_json(
        store,
        spec.execution_profile_ref,
        N5NativeExecutionProfile,
        kind=N5_REPLAY_EXECUTION_PROFILE_KIND,
        schema_version="1.0",
    )
    if (
        security.raw_content_hash(image_raw) != spec.production_image_content_hash
        or security.raw_content_hash(config_raw) != spec.prepared_configuration_content_hash
        or exact_n5_content_hash(config) != spec.prepared_configuration_hash
        or exact_n5_content_bytes(image) != exact_n5_content_bytes(scope.production_image)
        or exact_n5_content_bytes(config) != exact_n5_content_bytes(scope.configuration)
        or reconcile_recorded_n5_profile_current_bytes(
            profile,
            scope.profile,
            recorded_source_image=image,
            current_source_image=scope.production_image,
        ).status
        != "recomputed"
    ):
        raise ValueError("n5_replay_execution_basis_mismatch")
    capacity = budget.admit_diagnostic_invocation_only()
    if (
        capacity.status != "available"
        or capacity.protected_remaining_units is None
        or capacity.protected_remaining_units < len(scope.planned_units)
        or capacity.run_binding.run_id != spec.replay_run_id
        or capacity.run_binding.control_job_id != spec.replay_job_id
        or capacity.run_binding.tenant_id != spec.tenant_id
        or capacity.run_binding.cell_id != spec.cell_id
    ):
        raise ValueError("n5_replay_diagnostic_capacity_not_established")
    return capacity


def produce_n5_replay_basis(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    closure: VerifiedAcquisitionRouteClosure,
    scope: N5ReplayScope,
    producer_instance_id: str,
    produced_at: datetime,
) -> N5ReplayProducerBasis:
    """Reopen actual selected source and emit its limited producer statement."""
    from polisyos.runtime.quality.acquisition_evaluation import (
        rebuild_selected_candidate_n5_request,
        resolve_selected_acquisition_evaluation,
    )
    from polisyos.runtime.quality.generation_cycle import load_joint_simulation_result

    if scope.tenant_id != closure.tenant_id or scope.cell_id != closure.cell_id:
        raise ValueError("n5_replay_producer_scope_mismatch")
    store = bridge.artifact_store
    selected = resolve_selected_acquisition_evaluation(bridge=bridge, closure=closure).selected
    request = rebuild_selected_candidate_n5_request(
        store=store,
        input_ref=selected.n5_input_ref,
        run_id=selected.evaluation_run_id,
        job_id=selected.evaluation_job_id,
        tenant_id=scope.tenant_id,
        cell_id=scope.cell_id,
    )
    result = load_joint_simulation_result(
        selected.n5_result_ref, store=store, expected_request=request
    )
    return _write_n5_replay_basis(
        store=store,
        input_ref=selected.n5_input_ref,
        result_ref=selected.n5_result_ref,
        source_run_id=selected.evaluation_run_id,
        source_job_id=selected.evaluation_job_id,
        original_run_id=selected.evaluation_run_id,
        original_job_id=selected.evaluation_job_id,
        original_execution_ref=None,
        request=request,
        result=result,
        scope=scope,
        producer_instance_id=producer_instance_id,
        produced_at=produced_at,
    )


def _reopen_verified_original(
    *,
    store: CoreJSONArtifactStore,
    original_execution_ref: artifacts.ArtifactRef,
    scope: N5ReplayScope,
) -> tuple[N5OriginalProducerExecution, JointSimulationRequest, JointSimulationResult]:
    """Reconcile an original producer's selected source, result, and ledger."""
    from polisyos.runtime.quality.acquisition_evaluation import (
        rebuild_selected_candidate_n5_request,
    )
    from polisyos.runtime.quality.generation_cycle import load_joint_simulation_result
    from polisyos.runtime.quality.joint_simulation_horizon import _physical_invocation_binding
    from polisyos.runtime.quality.n5_replay_appointment import _read_n5_versioned_core_json
    from polisyos.scientist.orchestration.engine import decode_budget_ledger_snapshot

    execution, _ = _read_n5_versioned_core_json(
        store,
        original_execution_ref,
        N5OriginalProducerExecution,
        kind="runtime.quality.n5_original_producer_execution",
        schema_version="1.0",
    )
    if (
        execution.tenant_id != scope.tenant_id
        or execution.cell_id != scope.cell_id
        or not store.verify(execution.ledger_snapshot_ref).ok
    ):
        raise ValueError("n5_original_producer_scope_not_established")
    action = _read_original_action(store, execution.action_ref, execution.action_hash)
    if (
        action.source_input_ref != execution.source_input_ref
        or action.source_run_id != execution.source_run_id
        or action.source_job_id != execution.source_job_id
        or action.producer_run_id != execution.producer_run_id
        or action.producer_job_id != execution.producer_job_id
        or action.tenant_id != execution.tenant_id
        or action.cell_id != execution.cell_id
    ):
        raise ValueError("n5_original_action_binding_mismatch")
    ledger_bytes = store.get_bytes(execution.ledger_snapshot_ref)
    if (
        security.raw_content_hash(ledger_bytes) != execution.ledger_hash
        or str(execution.ledger_snapshot_ref.artifact_id) != execution.ledger_hash
    ):
        raise ValueError("n5_original_ledger_snapshot_mismatch")
    snapshot = decode_budget_ledger_snapshot(ledger_bytes)
    ledger_manifest = store.get_manifest(execution.ledger_snapshot_ref)
    if (
        ledger_manifest.artifact_schema is None
        or ledger_manifest.artifact_schema.name != "polisyos.scientist.budget_ledger.snapshot"
        or ledger_manifest.artifact_schema.version != snapshot.schema_version
    ):
        raise ValueError("n5_original_ledger_schema_mismatch")
    if (
        snapshot.revision != execution.ledger_revision
        or execution.ledger_owner
        != (snapshot.ledger_id, snapshot.canonical_contract, snapshot.coordination_mode)
        or snapshot.producer_settlements
        or set(snapshot.invocation_reservations) != set(execution.operation_ids)
        or any(
            row.status != "completed"
            or row.purpose != "diagnostic"
            or row.run_id != execution.producer_run_id
            for row in snapshot.invocation_reservations.values()
        )
    ):
        raise ValueError("n5_original_accounting_not_reconciled")
    profile = snapshot.invocation_profiles.get(execution.producer_run_id)
    if (
        profile is None
        or profile.run_binding.control_job_id != execution.producer_job_id
        or profile.run_binding.tenant_id != execution.tenant_id
        or profile.run_binding.cell_id != execution.cell_id
        or profile.total_units != action.quota_units
        or profile.protected_units != action.quota_units
    ):
        raise ValueError("n5_original_budget_binding_not_established")
    request = rebuild_selected_candidate_n5_request(
        store=store,
        input_ref=execution.source_input_ref,
        run_id=execution.source_run_id,
        job_id=execution.source_job_id,
        tenant_id=execution.tenant_id,
        cell_id=execution.cell_id,
    )
    result = load_joint_simulation_result(
        execution.result_ref, store=store, expected_request=request
    )
    if set(execution.operation_ids) != {
        row.invocation_quota_operation_id for row in result.physical_work_observations
    } or any(
        snapshot.invocation_reservations[row.invocation_quota_operation_id].request_digest
        != row.invocation_quota_request_digest
        or _physical_invocation_binding(
            row.invocation_id, row.physical_spec_ref, row.effective_seed
        )
        != (row.invocation_quota_operation_id, row.invocation_quota_request_digest)
        for row in result.physical_work_observations
    ):
        raise ValueError("n5_original_result_accounting_mismatch")
    _verify_declared_basis(store=store, execution=execution, request=request, result=result)
    return execution, request, result


def produce_n5_replay_basis_for_original(
    *,
    store: CoreJSONArtifactStore,
    original_execution_ref: artifacts.ArtifactRef,
    scope: N5ReplayScope,
    producer_instance_id: str,
    produced_at: datetime,
) -> N5ReplayProducerBasis:
    """Reopen a distinct original producer and create its unsigned V2 statement."""
    execution, request, result = _reopen_verified_original(
        store=store, original_execution_ref=original_execution_ref, scope=scope
    )
    return _write_n5_replay_basis(
        store=store,
        input_ref=execution.source_input_ref,
        result_ref=execution.result_ref,
        source_run_id=execution.source_run_id,
        source_job_id=execution.source_job_id,
        original_run_id=execution.producer_run_id,
        original_job_id=execution.producer_job_id,
        original_execution_ref=original_execution_ref,
        request=request,
        result=result,
        scope=scope,
        producer_instance_id=producer_instance_id,
        produced_at=produced_at,
    )


def prepare_historical_n5_replay_basis(
    *,
    store: CoreJSONArtifactStore,
    input_ref: artifacts.ArtifactRef,
    result_ref: artifacts.ArtifactRef,
    source_run_id: str,
    source_job_id: str,
    scope: N5ReplayScope,
    producer_instance_id: str,
    produced_at: datetime,
) -> N5ReplayProducerBasis:
    """Reopen caller-selected historical bytes as a non-executable V1 statement."""
    from polisyos.runtime.quality.acquisition_evaluation import (
        rebuild_selected_candidate_n5_request,
    )
    from polisyos.runtime.quality.generation_cycle import load_joint_simulation_result

    request = rebuild_selected_candidate_n5_request(
        store=store,
        input_ref=input_ref,
        run_id=source_run_id,
        job_id=source_job_id,
        tenant_id=scope.tenant_id,
        cell_id=scope.cell_id,
    )
    result = load_joint_simulation_result(result_ref, store=store, expected_request=request)
    return _write_n5_replay_basis(
        store=store,
        input_ref=input_ref,
        result_ref=result_ref,
        source_run_id=source_run_id,
        source_job_id=source_job_id,
        original_run_id=source_run_id,
        original_job_id=source_job_id,
        original_execution_ref=None,
        request=request,
        result=result,
        scope=scope,
        producer_instance_id=producer_instance_id,
        produced_at=produced_at,
    )


def _observe_declared_basis(
    *,
    input_ref: artifacts.ArtifactRef,
    request: JointSimulationRequest,
    result: JointSimulationResult,
) -> tuple[CandidateN5ContentObservation, PreparedJointSimulationConfiguration, str]:
    """Recompute one actual result's declared basis from the selected request."""
    from polisyos.runtime.quality.joint_simulation_horizon import (
        PreparedJointSimulationConfiguration,
    )
    from polisyos.runtime.quality.n5_candidate_content import (
        read_candidate_n5_content_observation,
        read_candidate_n5_declared_implementation,
    )

    observed = read_candidate_n5_content_observation(
        result, input_ref=input_ref, expected_request=request
    )
    config = PreparedJointSimulationConfiguration.model_validate_json(
        json.dumps(observed.consumed_configuration, allow_nan=False)
    )
    read_candidate_n5_declared_implementation(
        result,
        input_ref=input_ref,
        prepared_configuration=config,
        expected_request=request,
    )
    if not result.trajectories or any(
        t.engine_kind != "ncm_parallel_worlds" for t in result.trajectories
    ):
        raise ValueError("n5_replay_engine_capture_unsupported")
    witness = observed.witness
    callables = {call.callable_content for call in witness.observed_calls}
    if (
        len(callables) != 1
        or None in callables
        or witness.numerical_intent_content_hash is None
        or observed.completion.status != "recomputed"
        or observed.profile_stability != "recomputed"
        or observed.source_image_stability != "recomputed"
    ):
        raise ValueError("n5_replay_producer_basis_not_established")
    callable_content = next(iter(callables))
    if callable_content is None:
        raise ValueError("n5_replay_callable_not_established")
    return observed, config, callable_content


def _persist_declared_basis(
    *,
    store: CoreJSONArtifactStore,
    input_ref: artifacts.ArtifactRef,
    source_run_id: str,
    source_job_id: str,
    original_run_id: str,
    original_job_id: str,
    tenant_id: str,
    cell_id: str,
    request: JointSimulationRequest,
    result: JointSimulationResult,
) -> tuple[artifacts.ArtifactRef, artifacts.ArtifactRef]:
    """Persist only blind-safe source and declared numerical input artifacts."""
    from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_hash
    from polisyos.runtime.quality.n5_replay_appointment import (
        N5_REPLAY_EXECUTION_PROFILE_KIND,
        N5_REPLAY_NUMERICAL_INTENT_KIND,
        N5_REPLAY_PREPARED_CONFIGURATION_KIND,
        N5_REPLAY_PRODUCTION_IMAGE_KIND,
    )

    observed, config, callable_content = _observe_declared_basis(
        input_ref=input_ref, request=request, result=result
    )
    witness = observed.witness
    if witness.numerical_intent_content_hash is None:
        raise ValueError("n5_replay_numerical_intent_not_established")
    inputs = [artifacts.input_ref_from_artifact_ref(input_ref, role="selected_input")]
    canon = CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False)
    tenant = artifacts.ArtifactTenantContextInfo(tenant_id=tenant_id, cell_id=cell_id)

    def write(kind: str, value: object, *, version: str = "1.0") -> artifacts.ArtifactRef:
        return store.put_json(
            value,
            artifacts.PutOptions(
                kind=kind,
                media_type="application/json",
                inputs=inputs,
                schema=artifacts.SchemaInfo(name=kind, version=version),
                canon=artifacts.CanonInfo.from_spec(canon),
                tenant_context=tenant,
            ),
            canon_spec=canon,
            return_selected_profile=True,
        )

    image = write(N5_REPLAY_PRODUCTION_IMAGE_KIND, witness.production_image.model_dump(mode="json"))
    prepared = write(N5_REPLAY_PREPARED_CONFIGURATION_KIND, config.model_dump(mode="json"))
    profile = write(
        N5_REPLAY_EXECUTION_PROFILE_KIND, observed.execution_profile.model_dump(mode="json")
    )
    intent = N5ReplayNumericalIntentV2(
        selected_candidate_simulation_n5_input_ref=input_ref,
        source_run_id=source_run_id,
        source_job_id=source_job_id,
        original_run_id=original_run_id,
        original_job_id=original_job_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
        declared_numerical_intent_content_hash=witness.numerical_intent_content_hash,
        declared_callable_content_hash=security.raw_content_hash(callable_content.encode()),
        production_image_ref=image,
        production_image_content_hash=security.raw_content_hash(store.get_bytes(image)),
        prepared_configuration_ref=prepared,
        prepared_configuration_content_hash=security.raw_content_hash(store.get_bytes(prepared)),
        prepared_configuration_hash=exact_n5_content_hash(config),
    )
    intent_ref = write(
        N5_REPLAY_NUMERICAL_INTENT_KIND, intent.model_dump(mode="json"), version="2.0"
    )
    return intent_ref, profile


def _verify_declared_basis(
    *,
    store: CoreJSONArtifactStore,
    execution: N5OriginalProducerExecution,
    request: JointSimulationRequest,
    result: JointSimulationResult,
) -> None:
    """Reconcile source-bound actual observation with every persisted basis axis."""
    from polisyos.runtime.quality.joint_simulation_horizon import (
        PreparedJointSimulationConfiguration,
    )
    from polisyos.runtime.quality.n5_execution_basis import (
        N5ProductionImage,
        exact_n5_content_bytes,
        exact_n5_content_hash,
    )
    from polisyos.runtime.quality.n5_execution_profile import N5NativeExecutionProfile
    from polisyos.runtime.quality.n5_replay_appointment import (
        N5_REPLAY_EXECUTION_PROFILE_KIND,
        N5_REPLAY_NUMERICAL_INTENT_KIND,
        N5_REPLAY_PREPARED_CONFIGURATION_KIND,
        N5_REPLAY_PRODUCTION_IMAGE_KIND,
        _read_n5_versioned_core_json,
    )

    observed, config, callable_content = _observe_declared_basis(
        input_ref=execution.source_input_ref, request=request, result=result
    )
    intent, _ = _read_n5_versioned_core_json(
        store,
        execution.numerical_intent_ref,
        N5ReplayNumericalIntentV2,
        kind=N5_REPLAY_NUMERICAL_INTENT_KIND,
        schema_version="2.0",
    )
    profile, _ = _read_n5_versioned_core_json(
        store,
        execution.execution_profile_ref,
        N5NativeExecutionProfile,
        kind=N5_REPLAY_EXECUTION_PROFILE_KIND,
        schema_version="1.0",
    )
    image, image_bytes = _read_n5_versioned_core_json(
        store,
        intent.production_image_ref,
        N5ProductionImage,
        kind=N5_REPLAY_PRODUCTION_IMAGE_KIND,
        schema_version="1.0",
    )
    prepared, prepared_bytes = _read_n5_versioned_core_json(
        store,
        intent.prepared_configuration_ref,
        PreparedJointSimulationConfiguration,
        kind=N5_REPLAY_PREPARED_CONFIGURATION_KIND,
        schema_version="1.0",
    )
    expected_input = [
        artifacts.input_ref_from_artifact_ref(execution.source_input_ref, role="selected_input")
    ]
    for ref in (
        execution.numerical_intent_ref,
        execution.execution_profile_ref,
        intent.production_image_ref,
        intent.prepared_configuration_ref,
    ):
        if store.get_manifest(ref).inputs != expected_input:
            raise ValueError("n5_replay_declared_basis_source_closure_mismatch")
    if (
        intent.selected_candidate_simulation_n5_input_ref != execution.source_input_ref
        or intent.source_run_id != execution.source_run_id
        or intent.source_job_id != execution.source_job_id
        or intent.original_run_id != execution.producer_run_id
        or intent.original_job_id != execution.producer_job_id
        or intent.tenant_id != execution.tenant_id
        or intent.cell_id != execution.cell_id
        or intent.declared_numerical_intent_content_hash
        != observed.witness.numerical_intent_content_hash
        or intent.declared_callable_content_hash
        != security.raw_content_hash(callable_content.encode())
        or intent.production_image_content_hash != security.raw_content_hash(image_bytes)
        or intent.prepared_configuration_content_hash != security.raw_content_hash(prepared_bytes)
        or intent.prepared_configuration_hash != exact_n5_content_hash(config)
        or exact_n5_content_bytes(profile) != exact_n5_content_bytes(observed.execution_profile)
        or exact_n5_content_bytes(image)
        != exact_n5_content_bytes(observed.witness.production_image)
        or exact_n5_content_bytes(prepared) != exact_n5_content_bytes(config)
    ):
        raise ValueError("n5_replay_declared_basis_observation_mismatch")


def _write_n5_replay_basis(
    *,
    store: CoreJSONArtifactStore,
    input_ref: artifacts.ArtifactRef,
    result_ref: artifacts.ArtifactRef,
    source_run_id: str,
    source_job_id: str,
    original_run_id: str,
    original_job_id: str,
    original_execution_ref: artifacts.ArtifactRef | None,
    request: JointSimulationRequest,
    result: JointSimulationResult,
    scope: N5ReplayScope,
    producer_instance_id: str,
    produced_at: datetime,
) -> N5ReplayProducerBasis:
    """Write a reopened, source-bound basis without assigning authority."""
    from polisyos.runtime.quality.n5_replay_appointment import _read_n5_versioned_core_json
    from polisyos.runtime.quality.n5_replay_numerical_projection import (
        N5_NUMERICAL_RESULT_PROJECTION_SCHEMA,
        project_n5_numerical_result_v1,
    )

    _, config, _ = _observe_declared_basis(input_ref=input_ref, request=request, result=result)
    if original_execution_ref is None:
        intent_ref, profile = _persist_declared_basis(
            store=store,
            input_ref=input_ref,
            source_run_id=source_run_id,
            source_job_id=source_job_id,
            original_run_id=original_run_id,
            original_job_id=original_job_id,
            tenant_id=scope.tenant_id,
            cell_id=scope.cell_id,
            request=request,
            result=result,
        )
    else:
        execution, _ = _read_n5_versioned_core_json(
            store,
            original_execution_ref,
            N5OriginalProducerExecution,
            kind="runtime.quality.n5_original_producer_execution",
            schema_version="1.0",
        )
        intent_ref, profile = execution.numerical_intent_ref, execution.execution_profile_ref
        _verify_declared_basis(store=store, execution=execution, request=request, result=result)
    inputs = [
        artifacts.input_ref_from_artifact_ref(input_ref, role="selected_input"),
        artifacts.input_ref_from_artifact_ref(result_ref, role="selected_result"),
    ]

    def write(kind: str, value: object, *, version: str = "1.0") -> artifacts.ArtifactRef:
        spec = CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False)
        return store.put_json(
            value,
            artifacts.PutOptions(
                kind=kind,
                media_type="application/json",
                inputs=inputs,
                schema=artifacts.SchemaInfo(name=kind, version=version),
                canon=artifacts.CanonInfo.from_spec(spec),
                tenant_context=artifacts.ArtifactTenantContextInfo(
                    tenant_id=scope.tenant_id, cell_id=scope.cell_id
                ),
            ),
            canon_spec=spec,
            return_selected_profile=True,
        )

    projection = project_n5_numerical_result_v1(
        result,
        input_ref=input_ref,
        expected_request=request,
        prepared_configuration=config,
        store=store,
    )
    document = write(
        "runtime.quality.n5_numerical_result_projection", projection.model_dump(mode="json")
    )
    numerical = projection.numerical_bytes()
    numerical_ref = store.put_bytes(
        numerical,
        artifacts.PutOptions(
            kind="runtime.quality.n5_numerical_result_projection_bytes",
            media_type="application/octet-stream",
            inputs=inputs,
            schema=artifacts.SchemaInfo(
                name="runtime.quality.n5_numerical_result_projection_bytes", version="1.0"
            ),
            tenant_context=artifacts.ArtifactTenantContextInfo(
                tenant_id=scope.tenant_id, cell_id=scope.cell_id
            ),
        ),
        return_selected_profile=True,
    )
    statement_fields = dict(  # noqa: C408
        scope=scope,
        original_job_id=original_job_id,
        original_run_id=original_run_id,
        producer_instance_id=producer_instance_id,
        numerical_intent_ref=intent_ref,
        numerical_intent_hash=security.raw_content_hash(store.get_bytes(intent_ref)),
        execution_profile_ref=profile,
        numerical_projection_schema=N5_NUMERICAL_RESULT_PROJECTION_SCHEMA,
        numerical_result_projection_ref=numerical_ref,
        numerical_result_projection_hash=security.raw_content_hash(numerical),
        seed_schedule_hash=n5_replay_seed_schedule_hash(request),
        produced_at=produced_at,
    )
    statement = (
        N5OriginalProducerSeal(**statement_fields)
        if original_execution_ref is None
        else N5OriginalProducerSealV2(
            **statement_fields, original_execution_ref=original_execution_ref
        )
    )
    return N5ReplayProducerBasis(
        statement=statement,
        original_result_ref=result_ref,
        projection_document_ref=document,
    )
