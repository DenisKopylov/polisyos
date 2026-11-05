"""Compose the real test-owned WDI execution port for served experiments."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import sleep
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    import pytest

    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.http.services.acquisition_action_service import (
        AcquisitionActionService,
        CandidateExperimentCurrentActionProjection,
        CandidateExperimentRouteMutationRequest,
    )
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import (
        ControlPlaneService,
        VerifiedAcquisitionActionOutcome,
    )
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionActionHeadRecord,
        ControlJobRecord,
    )
    from polisyos.runtime.quality.acquisition_evaluation import CandidateExperimentTerminalHistory
    from polisyos.runtime.quality.acquisition_route_loop import (
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionCandidateSourceRoute,
        AcquisitionWorldGrowthBridge,
    )


@dataclass(frozen=True)
class CandidateExperimentServedExecutionOwner:
    """Actual fixture-owned execution owners and controlled WDI calls."""

    bridge: AcquisitionWorldGrowthBridge
    port: WorldBankWDIAcquisitionExecutionPort
    selection: AcquisitionCandidateSourceRoute
    transport_calls: list[tuple[str, str, dict[str, str]]]


@dataclass(frozen=True)
class CandidateExperimentServedExecutionResult:
    """HTTP, worker, terminal, and selected evaluation from one served experiment."""

    job_id: str
    response_body: dict[str, object]
    response_digest: str
    request_head: AcquisitionActionHeadRecord
    request_projection: CandidateExperimentCurrentActionProjection
    final_job: ControlJobRecord
    final_outcome: VerifiedAcquisitionActionOutcome
    terminal_history: CandidateExperimentTerminalHistory
    terminal_ref: ArtifactRef
    current_action: CandidateExperimentCurrentActionProjection
    interrupted_job: ControlJobRecord | None
    interrupted_outcome: VerifiedAcquisitionActionOutcome | None
    attempts: tuple[int, ...]
    standard_invocation_units_before: int
    standard_invocation_units_after_interrupted: int | None
    standard_invocation_units_after: int
    execution_owner: CandidateExperimentServedExecutionOwner


def _standard_invocation_units(*, control: ControlPlaneService, run_id: str) -> int:
    """Count actual standard physical N5 reservations under the selected run profile."""
    snapshot = control._llm_producer_settlement_store.snapshot_safe()
    profile = snapshot.invocation_profiles.get(run_id)
    if profile is None:
        raise AssertionError("candidate experiment run quota profile missing")
    reservations = tuple(
        row
        for row in snapshot.invocation_reservations.values()
        if row.run_id == run_id
        and row.profile_digest == profile.profile_digest
        and row.purpose == "standard"
    )
    return sum(row.units for row in reservations)


def _experiment_outcomes(
    *, control: ControlPlaneService, origin: VerifiedCandidateExperimentOrigin
) -> tuple[VerifiedAcquisitionActionOutcome, ...]:
    """Read current action heads only through the installed lifecycle owner."""
    return control.acquisition_route_sink.experiment_action_outcomes(
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        run_id=origin.run_id,
        source_job_id=origin.source_job_id,
        route_id=origin.route_id,
    )


def _terminal_projection_expectations(
    *, terminal_history: CandidateExperimentTerminalHistory
) -> tuple[str, str, object, str | None]:
    """Derive public status and disposition from the persisted terminal receipt."""
    terminal = terminal_history.terminal
    status = "completed"
    disposition = "new"
    blocker_reason = None
    if terminal.terminal_outcome == "candidate_blocked":
        status = "blocked"
        disposition = "blocked"
        blocker_reason = terminal.blocker_reason
    elif terminal.selected_evaluation is None:
        basis = terminal_history.selected_basis
        if (
            terminal.terminal_outcome != "candidate_reentry_completed"
            or basis is None
            or not basis.reason_codes
        ):
            raise AssertionError(
                "candidate experiment completed without evaluation or selected-basis reasons"
            )
        disposition = "blocked"
        blocker_reason = "; ".join(basis.reason_codes)
    elif terminal.terminal_outcome == "candidate_evaluation_retained":
        disposition = "retained"
    return status, disposition, terminal.selected_evaluation, blocker_reason


def _dispatch_crash_probe_once(
    *, control: ControlPlaneService, expected_job_id: str, lease_seconds: int
) -> str:
    """Deliver one job through the actual ControlWorker with a short test lease."""
    from polisyos.runtime.http.services.control_worker import ControlWorker
    from tests._helpers.control_worker import stop_embedded_control_worker

    stop_embedded_control_worker(control)
    selected: list[str] = []

    def handle(job: ControlJobRecord) -> None:
        selected.append(job.job_id)
        if job.job_id != expected_job_id:
            raise AssertionError(
                f"expected candidate experiment job {expected_job_id}, received {job.job_id}"
            )
        control._process_control_job(job)

    worker = ControlWorker(
        store=control._control_store,
        handler=handle,
        worker_id=f"candidate-experiment-crash-probe-{uuid4().hex[:12]}",
        lease_seconds=lease_seconds,
    )
    try:
        dispatched = worker.dispatch_once()
    finally:
        worker.stop()
    if not dispatched or selected != [expected_job_id]:
        raise AssertionError(
            "candidate experiment crash probe did not dispatch exactly its requested job"
        )
    return expected_job_id


def _read_candidate_experiment_with_reopened_owner(
    *,
    control: ControlPlaneService,
    trust: object,
    origin: VerifiedCandidateExperimentOrigin,
    terminal_head: AcquisitionActionHeadRecord,
    terminal_history: CandidateExperimentTerminalHistory,
    monkeypatch: pytest.MonkeyPatch,
) -> CandidateExperimentCurrentActionProjection:
    """Replay terminal action state through an independent app and storage owner."""
    import sqlite3

    from fastapi.testclient import TestClient

    from polisyos.core import artifacts
    from polisyos.runtime.http import deployment_security as security
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.http.services.acquisition_action_service import (
        CandidateExperimentRouteProjection,
    )
    from polisyos.runtime.quality.acquisition_evaluation import CandidateExperimentTerminalHistory
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController
    from tests._helpers import acquisition_served_history as served

    resolver = control._policy_resolver
    if resolver.state_store_backend != "sqlite":
        raise AssertionError("candidate experiment fresh reader requires the selected SQLite owner")
    sqlite_path = control._resolve_control_sqlite_path()
    cas_root = Path(control._cas_root)
    core_runs_root = Path(control._core_runs_root)
    providers = control._registry_providers
    context_owner = control._cycle_substrate_context_admission_owner
    if context_owner is None:
        raise AssertionError("candidate experiment fresh reader lost configured source profiles")

    with monkeypatch.context() as reader_environment:
        reader_environment.setenv("POLISYOS_EXECUTION_PROFILE", resolver.default_profile)
        reader_environment.setenv("POLISYOS_CONTROL_WORKER_BACKEND", resolver.worker_backend)
        reader_environment.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
        reader_environment.setenv("POLISYOS_CONTROL_SQLITE_PATH", str(sqlite_path))
        reader_context = build_runtime_api_context(
            cas_root=cas_root,
            core_runs_root=core_runs_root,
        )
        reader_app = create_runtime_api_app(
            cas_root=cas_root,
            core_runs_root=core_runs_root,
            deployment_security=security.build_deployment_security(
                security.DeploymentSecurityConfig.from_mapping(trust.raw)
            ),
            enable_security_middlewares=True,
            enable_csrf_protection=False,
            container_overrides=RuntimeContainerOverrides(
                runtime_api_context=reader_context,
                control_registry_providers=providers,
            ),
            candidate_simulation_profiles=tuple(context_owner.profiles),
            candidate_simulation_model_declarations=tuple(context_owner.model_declarations),
            repo_root=control._repo_root,
            catalog_source_selection=providers.catalog_source_selection,
            catalog_run_profile=providers.catalog_run_profile,
        )

        def forbid_n5(*_args: object, **_kwargs: object) -> object:
            raise AssertionError("candidate experiment fresh GET attempted to run N5")

        with monkeypatch.context() as read_only_guard:
            read_only_guard.setattr(JointSimulationHorizonController, "run", forbid_n5)
            with TestClient(reader_app) as reader:
                reader_control = reader.app.state._control_service
                reader_store = reader_control._artifact_store
                if (
                    reader_control is control
                    or reader_store is control._artifact_store
                    or reader_control._control_store is control._control_store
                    or reader_control._registry_providers is not providers
                    or Path(reader_control._cas_root) != cas_root
                    or reader_control._resolve_control_sqlite_path() != sqlite_path
                ):
                    raise AssertionError(
                        "candidate experiment reader did not reopen the same inputs"
                    )

                path = f"/api/v1/runs/{origin.run_id}/candidate-acquisition-experiment"
                headers = {
                    "Authorization": f"Bearer {trust.tokens['acquisition-operator']}",
                    "X-Tenant-ID": served.TENANT,
                }

                def read_current_action() -> CandidateExperimentCurrentActionProjection:
                    response = reader.get(path, headers=headers)
                    if response.status_code != 200:
                        raise AssertionError(response.text)
                    return CandidateExperimentRouteProjection.model_validate(
                        response.json()
                    ).current_action

                reopened_outcomes = _experiment_outcomes(
                    control=reader_control,
                    origin=origin,
                )
                if not reopened_outcomes:
                    raise AssertionError("candidate experiment terminal history not reopened")
                reopened_history = reopened_outcomes[-1].candidate_experiment_terminal_history
                if (
                    type(reopened_history) is not CandidateExperimentTerminalHistory
                    or reopened_history.head != terminal_head
                    or reopened_history.terminal_ref != terminal_history.terminal_ref
                    or reopened_history.phase_chain != terminal_history.phase_chain
                    or reopened_history.terminal.selected_evaluation
                    != terminal_history.terminal.selected_evaluation
                ):
                    raise AssertionError("candidate experiment independent history changed")

                selected_action = read_current_action()
                terminal_ref = artifacts.profile_bound_ref(
                    reader_store, reopened_history.terminal_ref
                )
                phase_heads = []
                for phase in reopened_history.phase_chain:
                    phase_head = (
                        reader_control._control_store.get_acquisition_action_head_by_receipt(
                            tenant_id=terminal_head.tenant_id,
                            cell_id=terminal_head.cell_id,
                            run_id=terminal_head.run_id,
                            source_job_id=terminal_head.source_job_id,
                            route_id=terminal_head.route_id,
                            action_generation=terminal_head.action_generation,
                            receipt_ref=phase.receipt_ref,
                        )
                    )
                    if phase_head is None or phase_head.receipt_manifest_profile_sha256 is None:
                        raise AssertionError(
                            "candidate experiment exact SQL-selected phase profile missing"
                        )
                    if phase.receipt_ref == str(reopened_history.terminal_ref.artifact_id):
                        phase_ref = artifacts.profile_bound_ref(
                            reader_store,
                            reopened_history.terminal_ref,
                        )
                    else:
                        phase_ref = artifacts.profile_bound_ref(
                            reader_store,
                            artifacts.ArtifactRef(
                                artifact_id=artifacts.ArtifactID.model_validate(phase.receipt_ref),
                                kind=(
                                    "runtime_quality.acquisition_candidate_experiment_phase_receipt"
                                ),
                                media_type="application/json",
                                manifest_profile_sha256=phase_head.receipt_manifest_profile_sha256,
                            ),
                        )
                    if (
                        phase_ref.manifest_profile_sha256
                        != phase_head.receipt_manifest_profile_sha256
                    ):
                        raise AssertionError(
                            "candidate experiment selected phase ref profile mismatch"
                        )
                    phase_heads.append((phase, phase_head, phase_ref))
                if len(phase_heads) != 5 or phase_heads[-1][1] != terminal_head:
                    raise AssertionError("candidate experiment full selected phase chain changed")
                expected_status, expected_disposition, expected_evaluation, expected_reason = (
                    _terminal_projection_expectations(terminal_history=reopened_history)
                )
                if (
                    selected_action.status != expected_status
                    or selected_action.job_state != "completed"
                    or selected_action.job_id != terminal_head.job_id
                    or selected_action.receipt_phase != "terminal"
                    or selected_action.terminal_outcome
                    != reopened_history.terminal.terminal_outcome
                    or selected_action.evaluation_disposition != expected_disposition
                    or selected_action.selected_evaluation != expected_evaluation
                    or selected_action.blocker_reason != expected_reason
                    or selected_action.selected_receipt_ref != terminal_ref
                    or selected_action.selected_receipt_ref.manifest_profile_sha256
                    != terminal_head.receipt_manifest_profile_sha256
                ):
                    raise AssertionError("candidate experiment independent terminal GET mismatch")

                wrong_profile = "sha256:" + "0" * 64
                wrong_profile_head = phase_heads[-2][1]
                selected_profile = wrong_profile_head.receipt_manifest_profile_sha256
                if not selected_profile or wrong_profile == selected_profile:
                    raise AssertionError("candidate experiment ancestor profile is not testable")
                head_scope = (
                    wrong_profile_head.tenant_id,
                    wrong_profile_head.cell_id,
                    wrong_profile_head.run_id,
                    wrong_profile_head.source_job_id,
                    wrong_profile_head.route_id,
                    wrong_profile_head.action_generation,
                    wrong_profile_head.head_generation,
                )
                with sqlite3.connect(sqlite_path) as connection:
                    updated = connection.execute(
                        "UPDATE runtime_acquisition_action_heads "
                        "SET receipt_manifest_profile_sha256 = ? "
                        "WHERE tenant_id = ? AND cell_id = ? AND run_id = ? "
                        "AND source_job_id = ? AND route_id = ? "
                        "AND action_generation = ? AND head_generation = ?",
                        (wrong_profile, *head_scope),
                    ).rowcount
                if updated != 1:
                    raise AssertionError(
                        "candidate experiment wrong-profile control missed selected ancestor"
                    )
                try:
                    wrong_profile_response = reader.get(path, headers=headers)
                finally:
                    with sqlite3.connect(sqlite_path) as connection:
                        restored = connection.execute(
                            "UPDATE runtime_acquisition_action_heads "
                            "SET receipt_manifest_profile_sha256 = ? "
                            "WHERE tenant_id = ? AND cell_id = ? AND run_id = ? "
                            "AND source_job_id = ? AND route_id = ? "
                            "AND action_generation = ? AND head_generation = ?",
                            (selected_profile, *head_scope),
                        ).rowcount
                    if restored != 1:
                        raise AssertionError(
                            "candidate experiment wrong-profile control did not restore selected ancestor"
                        )
                if wrong_profile_response.status_code != 409:
                    raise AssertionError(
                        "candidate experiment wrong-profile reader did not fail closed: "
                        f"{wrong_profile_response.status_code} {wrong_profile_response.text}"
                    )
                wrong_profile_code = wrong_profile_response.json().get("code")
                if not isinstance(wrong_profile_code, str) or not wrong_profile_code:
                    raise AssertionError("candidate experiment wrong-profile refusal was untyped")

                terminal_evaluation = reopened_history.evaluation
                if (
                    terminal_evaluation is None
                    or terminal_evaluation.selected.n5_result_ref is None
                ):
                    raise AssertionError("candidate experiment selected N5 result ref missing")
                result_ref = terminal_evaluation.selected.n5_result_ref
                result_blob_path, _result_manifest_path = reader_store._paths(
                    artifacts.ArtifactID.model_validate(result_ref.artifact_id)
                )
                result_payload = result_blob_path.read_bytes()
                result_blob_path.unlink()
                try:
                    missing_result_response = reader.get(path, headers=headers)
                    if missing_result_response.status_code != 409:
                        raise AssertionError(
                            "candidate experiment missing selected N5 result did not fail closed: "
                            f"{missing_result_response.status_code} {missing_result_response.text}"
                        )
                    missing_result_code = missing_result_response.json().get("code")
                    if not isinstance(missing_result_code, str) or not missing_result_code:
                        raise AssertionError(
                            "candidate experiment missing-result refusal was untyped"
                        )
                finally:
                    result_blob_path.write_bytes(result_payload)

                restored_action = read_current_action()
                if (
                    restored_action.status != expected_status
                    or restored_action.evaluation_disposition != expected_disposition
                    or restored_action.selected_evaluation != expected_evaluation
                    or restored_action.blocker_reason != expected_reason
                    or restored_action.selected_receipt_ref != terminal_ref
                ):
                    raise AssertionError(
                        "candidate experiment restored result lost positive selection"
                    )
                return restored_action


def run_candidate_experiment_served_execution(
    *,
    values: Mapping[str, object],
    origin: VerifiedCandidateExperimentOrigin,
    request: CandidateExperimentRouteMutationRequest,
    decision_ref: str,
    policy_owner: object,
    monkeypatch: pytest.MonkeyPatch,
    before_first_delivery: Callable[[CandidateExperimentServedExecutionOwner, str], None]
    | None = None,
    recover_worker_crash: bool = False,
    wdi_response_value: float | None = None,
) -> CandidateExperimentServedExecutionResult:
    """Execute a replayed candidate action through HTTP, the real worker and fresh GET.

    ``before_first_delivery`` runs after the execute POST and its requested head
    have been read back, immediately before the worker claims the queued job.
    Recovery mode is reserved for a test-owned one-shot ``KeyboardInterrupt``
    at a durable writer boundary. The second delivery reclaims the same job
    after the first worker lease expires.
    """
    from polisyos.core import artifacts
    from polisyos.runtime.http.services.acquisition_action_service import (
        AcquisitionActionService,
        CandidateExperimentRouteExecutionRequest,
        CandidateExperimentRouteProjection,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.http.services.control_plane_store import ControlJobRecord
    from polisyos.runtime.quality.acquisition_evaluation import CandidateExperimentTerminalHistory
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceipt,
    )
    from tests._helpers import acquisition_served_history as served
    from tests._helpers.control_worker import dispatch_one_control_job

    control = values["control"]
    client, trust = values["client"], values["trust"]
    action_service = values["action_service"]
    if type(action_service) is not AcquisitionActionService:
        raise TypeError("candidate_experiment_served_action_service_untyped")
    if type(control) is not ControlPlaneService or action_service.control_service is not control:
        raise TypeError("candidate_experiment_served_control_owner_mismatch")
    if recover_worker_crash and before_first_delivery is None:
        raise ValueError("candidate_experiment_crash_probe_hook_missing")

    store = control._artifact_store
    units_before = _standard_invocation_units(control=control, run_id=origin.run_id)
    execute_path = (
        f"/api/v1/runs/{origin.run_id}/candidate-acquisition-experiment/{origin.route_id}/execute"
    )
    execute_route = "/api/v1/runs/{run_id}/candidate-acquisition-experiment/{route_id}/execute"
    get_path = f"/api/v1/runs/{origin.run_id}/candidate-acquisition-experiment"
    read_headers = {
        "Authorization": f"Bearer {trust.tokens['acquisition-operator']}",
        "X-Tenant-ID": served.TENANT,
    }
    body = CandidateExperimentRouteExecutionRequest(
        request=request,
        decision_ref=decision_ref,
    ).model_dump(mode="json")
    interrupted_job: ControlJobRecord | None = None
    interrupted_outcome: VerifiedAcquisitionActionOutcome | None = None
    interrupted_units: int | None = None
    interrupted_transport_call_count: int | None = None
    attempts: tuple[int, ...]

    with candidate_experiment_served_execution_owner(
        action_service=action_service,
        origin=origin,
        policy_owner=policy_owner,
        monkeypatch=monkeypatch,
        wdi_response_value=wdi_response_value,
    ) as execution_owner:
        response, response_digest = trust.post(
            client,
            execute_path,
            body,
            route=execute_route,
        )
        if response.status_code not in {200, 202}:
            try:
                diagnostic_origin = action_service._resolve_candidate_experiment_origin(
                    tenant_id=origin.tenant_id,
                    cell_id=origin.cell_id,
                    run_id=origin.run_id,
                )
                execution_owner.port.preflight_candidate_experiment(origin=diagnostic_origin)
            except Exception as diagnostic_error:
                raise AssertionError(response.text) from diagnostic_error
            raise AssertionError(response.text)
        response_body = response.json()
        job_id = str(response_body["job_id"])
        expected_job_id = AcquisitionActionService._candidate_experiment_job_id(origin, request)
        if job_id != expected_job_id or response_body.get("authority_decision_ref") != decision_ref:
            raise AssertionError("candidate experiment execute response identity mismatch")

        request_outcomes = _experiment_outcomes(control=control, origin=origin)
        if not request_outcomes or request_outcomes[-1].head.job_id != job_id:
            raise AssertionError("candidate experiment requested head not published")
        request_outcome = request_outcomes[-1]
        request_head = request_outcome.head
        if (
            request_head.receipt_phase != "requested"
            or not request_head.receipt_manifest_profile_sha256
        ):
            raise AssertionError("candidate experiment requested receipt profile missing")

        before_delivery_response = client.get(get_path, headers=read_headers)
        if before_delivery_response.status_code != 200:
            raise AssertionError(before_delivery_response.text)
        before_delivery_projection = CandidateExperimentRouteProjection.model_validate(
            before_delivery_response.json()
        )
        request_action = before_delivery_projection.current_action
        expected_request_ref = artifacts.profile_bound_ref(
            store,
            artifacts.ArtifactRef(
                artifact_id=artifacts.ArtifactID.model_validate(request_head.receipt_ref),
                kind="runtime_quality.acquisition_candidate_experiment_phase_receipt",
                media_type="application/json",
                manifest_profile_sha256=request_head.receipt_manifest_profile_sha256,
            ),
        )
        if (
            request_action.status != "in_progress"
            or request_action.job_id != job_id
            or request_action.receipt_phase != "requested"
            or request_action.selected_receipt_ref != expected_request_ref
            or request_action.selected_receipt_ref.manifest_profile_sha256
            != request_head.receipt_manifest_profile_sha256
        ):
            raise AssertionError("candidate experiment requested head fresh readback mismatch")

        if before_first_delivery is not None:
            before_first_delivery(execution_owner, job_id)

        if recover_worker_crash:
            crashed = False
            try:
                _dispatch_crash_probe_once(
                    control=control,
                    expected_job_id=job_id,
                    lease_seconds=1,
                )
            except KeyboardInterrupt:
                crashed = True
            if not crashed:
                raise AssertionError("candidate experiment crash hook did not interrupt delivery")
            interrupted_job = control._control_store.get_job(job_id)
            if (
                type(interrupted_job) is not ControlJobRecord
                or interrupted_job.state != "running"
                or interrupted_job.attempt != 1
                or interrupted_job.lease_expires_at is None
            ):
                raise AssertionError(
                    f"candidate experiment interrupted job state not preserved: {interrupted_job!r}"
                )
            interrupted_outcomes = _experiment_outcomes(control=control, origin=origin)
            if (
                not interrupted_outcomes
                or interrupted_outcomes[-1].head.job_id != job_id
                or interrupted_outcomes[-1].head.receipt_phase != "candidate_input_reentry_pending"
            ):
                raise AssertionError("candidate experiment crash changed its pending action head")
            interrupted_outcome = interrupted_outcomes[-1]
            interrupted_units = _standard_invocation_units(control=control, run_id=origin.run_id)
            interrupted_transport_call_count = len(execution_owner.transport_calls)
            expiry = interrupted_job.lease_expires_at + timedelta(milliseconds=25)
            remaining = (expiry - datetime.now(UTC)).total_seconds()
            if remaining > 0:
                sleep(remaining)
            dispatched = dispatch_one_control_job(
                store=control._control_store,
                handler=control._process_control_job,
                expected_job_id=job_id,
            )
            if dispatched != job_id:
                raise AssertionError("candidate experiment retry did not reclaim requested job")
            attempts = (interrupted_job.attempt, 2)
        else:
            dispatched = dispatch_one_control_job(
                store=control._control_store,
                handler=control._process_control_job,
                expected_job_id=job_id,
            )
            if dispatched != job_id:
                raise AssertionError("candidate experiment worker did not dispatch requested job")
            attempts = (1,)

        final_job = control._control_store.get_job(job_id)
        if type(final_job) is not ControlJobRecord or final_job.state != "completed":
            raise AssertionError(f"candidate experiment worker did not complete: {final_job!r}")
        if recover_worker_crash and final_job.attempt != 2:
            raise AssertionError("candidate experiment retry did not advance the worker attempt")
        final_outcomes = _experiment_outcomes(control=control, origin=origin)
        if not final_outcomes or final_outcomes[-1].head.job_id != job_id:
            raise AssertionError("candidate experiment terminal head missing")
        final_outcome = final_outcomes[-1]
        terminal_history = final_outcome.candidate_experiment_terminal_history
        if (
            type(final_outcome.latest_receipt) is not AcquisitionCandidateExperimentTerminalReceipt
            or type(terminal_history) is not CandidateExperimentTerminalHistory
            or final_outcome.head.receipt_phase != "terminal"
            or terminal_history.head != final_outcome.head
            or terminal_history.terminal != final_outcome.latest_receipt
        ):
            raise AssertionError("candidate experiment terminal history not established")

        after_response = client.get(get_path, headers=read_headers)
        if after_response.status_code != 200:
            raise AssertionError(after_response.text)
        public_projection = CandidateExperimentRouteProjection.model_validate(after_response.json())
        current_action = public_projection.current_action
        terminal = terminal_history.terminal
        (
            expected_status,
            expected_disposition,
            expected_evaluation,
            expected_blocker_reason,
        ) = _terminal_projection_expectations(terminal_history=terminal_history)
        if (
            current_action.status != expected_status
            or current_action.job_state != "completed"
            or current_action.job_id != job_id
            or current_action.receipt_phase != "terminal"
            or current_action.terminal_outcome != terminal.terminal_outcome
            or current_action.evaluation_disposition != expected_disposition
            or current_action.selected_evaluation != expected_evaluation
            or current_action.blocker_reason != expected_blocker_reason
        ):
            raise AssertionError("candidate experiment fresh terminal GET did not resolve")
        current_action = _read_candidate_experiment_with_reopened_owner(
            control=control,
            trust=trust,
            origin=origin,
            terminal_head=final_outcome.head,
            terminal_history=terminal_history,
            monkeypatch=monkeypatch,
        )
        units_after = _standard_invocation_units(control=control, run_id=origin.run_id)
        if recover_worker_crash and units_after != interrupted_units:
            raise AssertionError("candidate experiment retry repeated standard N5 invocations")
        if recover_worker_crash and interrupted_transport_call_count != len(
            execution_owner.transport_calls
        ):
            raise AssertionError("candidate experiment retry repeated source acquisition")

    if recover_worker_crash:
        if interrupted_job is None or interrupted_outcome is None or interrupted_units is None:
            raise AssertionError("candidate experiment interrupted attempt was not captured")
    else:
        interrupted_job = None
        interrupted_outcome = None
        interrupted_units = None

    return CandidateExperimentServedExecutionResult(
        job_id=job_id,
        response_body=response_body,
        response_digest=response_digest,
        request_head=request_head,
        request_projection=request_action,
        final_job=final_job,
        final_outcome=final_outcome,
        terminal_history=terminal_history,
        terminal_ref=terminal_history.terminal_ref,
        current_action=current_action,
        interrupted_job=interrupted_job,
        interrupted_outcome=interrupted_outcome,
        attempts=attempts,
        standard_invocation_units_before=units_before,
        standard_invocation_units_after_interrupted=interrupted_units,
        standard_invocation_units_after=units_after,
        execution_owner=execution_owner,
    )


@contextmanager
def candidate_experiment_served_execution_owner(
    *,
    action_service: AcquisitionActionService,
    origin: VerifiedCandidateExperimentOrigin,
    policy_owner: object,
    monkeypatch: pytest.MonkeyPatch,
    wdi_response_value: float | None = None,
) -> Iterator[CandidateExperimentServedExecutionOwner]:
    """Install a real WDI port and exact source route for one served experiment.

    The WDI authority, registry, provision, source profile, and candidate policy
    template come from the same test-owned policy issuer. The bridge binds to the
    existing Control, CAS, event, and action-head owners. The supported fixture
    transport supplies a declared synthetic WDI response and rejects external
    network access; this helper does not run N5.
    """
    from polisyos.runtime.http.services import acquisition_surface_execution
    from polisyos.runtime.http.services.acquisition_action_service import (
        AcquisitionActionService as AcquisitionActionServiceType,
    )
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import (
        ControlPlaneService as ControlPlaneServiceType,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        VerifiedCandidateExperimentOrigin as VerifiedCandidateExperimentOriginType,
    )
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthBridge,
        AcquisitionWorldGrowthConfig,
    )
    from tests._helpers import lane01_candidate_action_served
    from tests._helpers.lane01_candidate_action_served import _transport

    if type(action_service) is not AcquisitionActionServiceType:
        raise TypeError("candidate_experiment_test_action_service_untyped")
    control = action_service.control_service
    if type(control) is not ControlPlaneServiceType:
        raise TypeError("candidate_experiment_test_control_service_untyped")
    if type(origin) is not VerifiedCandidateExperimentOriginType:
        raise TypeError("candidate_experiment_test_origin_untyped")

    issuer = getattr(policy_owner, "issuer", None)
    template = getattr(policy_owner, "template", None)
    source_profiles = getattr(policy_owner, "source_profiles", None)
    if issuer is None or template is None or source_profiles is None:
        raise TypeError("candidate_experiment_test_policy_owner_incomplete")
    authority = getattr(issuer, "authority", None)
    registry = getattr(issuer, "registry", None)
    issuer_port = getattr(issuer, "port", None)
    if (
        authority is None
        or registry is None
        or type(issuer_port) is not WorldBankWDIAcquisitionExecutionPort
        or issuer_port._authority is not authority
        or issuer_port._registry != registry
        or issuer_port._provision != authority.provision
        or issuer_port._artifact_store is not control._artifact_store
        or issuer_port._executor is not None
        or template.authority_registry_sha256 != registry.content_sha256
        or template.authority_provision_sha256 != authority.provision_content_sha256
    ):
        raise TypeError("candidate_experiment_test_wdi_issuer_owner_mismatch")

    providers = control._registry_providers
    if (
        providers.source_profiles is not source_profiles
        or template not in providers.candidate_unpriced_policy_templates
        or providers.candidate_unpriced_policy_bindings
    ):
        raise ValueError("candidate_experiment_test_policy_owner_not_current")

    bridge = AcquisitionWorldGrowthBridge(
        config=AcquisitionWorldGrowthConfig(candidate_source_routes=()),
        repo_root=Path(authority.repo_root),
        runtime_root=Path(control._cas_root),
        authority=authority,
        artifact_store=control._artifact_store,
        event_log=control._diagnostic_event_log,
        epoch_deployment=None,
        promotion_runtime=control._promotion_runtime,
        cycle_substrate_context_admission_owner=(control._cycle_substrate_context_admission_owner),
        control_store=control._control_store,
        action_head_sink=control.acquisition_route_sink,
        source_control_service=control,
    )
    port = WorldBankWDIAcquisitionExecutionPort(
        world_growth_bridge=bridge,
        authority=authority,
        registry=registry,
        provision=authority.provision,
        provision_content_sha256=authority.provision_content_sha256,
        runtime_state_root=Path(control._cas_root),
        artifact_store=control._artifact_store,
    )
    previous_execution_port = action_service._execution_port
    previous_production_port = action_service._production_execution_port

    with monkeypatch.context() as scoped:
        if wdi_response_value is not None:
            original_fixture_response = lane01_candidate_action_served.fixture_wdi_response
            scoped.setattr(
                lane01_candidate_action_served,
                "fixture_wdi_response",
                lambda profile: original_fixture_response(profile, value=wdi_response_value),
            )

        def build_current_test_port(*, control_service: ControlPlaneService):
            if control_service is not control:
                raise AssertionError("candidate experiment reopened a different Control owner")
            return port

        scoped.setattr(
            acquisition_surface_execution,
            "build_production_world_bank_wdi_execution_port",
            build_current_test_port,
        )
        transport_calls = _transport(scoped)
        try:
            action_service._execution_port = port
            action_service._production_execution_port = port
            from polisyos.runtime.quality.candidate_acquisition_action import (
                _candidate_experiment_source_selection,
            )

            selection = _candidate_experiment_source_selection(bridge, origin)
            if (
                selection.tenant_id != origin.tenant_id
                or selection.cell_id != origin.cell_id
                or selection.run_id != origin.run_id
                or selection.route_id != origin.route_id
                or selection.candidate_digest != origin.policy_scope.candidate_digest
            ):
                raise ValueError("candidate_experiment_test_selection_scope_mismatch")
            bridge.config = AcquisitionWorldGrowthConfig(candidate_source_routes=(selection,))
            yield CandidateExperimentServedExecutionOwner(
                bridge=bridge,
                port=port,
                selection=selection,
                transport_calls=transport_calls,
            )
        finally:
            action_service._execution_port = previous_execution_port
            action_service._production_execution_port = previous_production_port
