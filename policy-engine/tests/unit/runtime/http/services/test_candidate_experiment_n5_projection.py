"""Candidate-experiment N5 output stays bound to its blocked terminal and route head."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core import artifacts
from polisyos.core.contracts.runtime import RunCandidateSimulationN5ResultBody
from polisyos.runtime.http.errors import RuntimeHTTPError
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionActionServiceError,
    CandidateExperimentN5ResultProjection,
)
from polisyos.runtime.http.services.control_plane_store import AcquisitionActionHeadRecord


def _ref(kind: str, fill: str, *, profile: str = "f") -> artifacts.ArtifactRef:
    """Create an exact selected test view."""
    return artifacts.ArtifactRef(
        artifact_id="sha256:" + fill * 64,
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + profile * 64,
    )


def _head(generation: int) -> AcquisitionActionHeadRecord:
    """Create one route head with distinct action generations."""
    receipt_ref = "sha256:" + str(generation) * 64
    return AcquisitionActionHeadRecord(
        tenant_id="tenant-projection-test",
        cell_id="cell-projection-test",
        run_id="run-projection-test",
        source_job_id="source-job-stable",
        route_id="sha256:" + "a" * 64,
        action_generation=generation,
        head_generation=generation,
        receipt_ref=receipt_ref,
        receipt_sha256=receipt_ref,
        durable_event_id=f"event-projection-{generation}",
        coarse_phase="terminal",
        receipt_phase="terminal",
        recovery_state="complete",
        job_id=f"action-job-{generation}",
        predecessor_receipt_ref=None,
        created_at=datetime(2026, 11, 7, tzinfo=UTC),
        receipt_manifest_profile_sha256="sha256:" + "f" * 64,
    )


def _history() -> tuple[SimpleNamespace, RunCandidateSimulationN5ResultBody]:
    """Build a typed selected result at the already-verified history boundary."""
    from tests.unit.core.contracts.test_runtime_n5_bodies import _result_body_payload

    head = _head(1)
    terminal_ref = artifacts.ArtifactRef(
        artifact_id=head.receipt_ref,
        kind="runtime_quality.acquisition_route_loop_receipt",
        media_type="application/json",
        manifest_profile_sha256=head.receipt_manifest_profile_sha256,
    )
    reentry_ref = _ref("runtime_quality.candidate_source_reentry_receipt", "e")
    result_ref = _ref("polisyos.runtime.joint_simulation_result", "d", profile="b")
    result_body_payload = _result_body_payload(candidate=True)
    result_body_payload["artifact_ref"] = result_ref
    result_body_payload["selected_manifest_profile_sha256"] = result_ref.manifest_profile_sha256
    result_body = RunCandidateSimulationN5ResultBody.model_validate(result_body_payload)

    n4_ref = _ref("runtime.quality.n4_candidate_scenario_source", "4")
    context_ref = _ref("runtime.quality.cycle_substrate_context_job", "5")
    input_ref = _ref("runtime.quality.candidate_simulation_n5_input", "6")
    execution_ref = _ref("runtime.quality.candidate_simulation_execution", "7")
    selected = SimpleNamespace(
        design_problem_ref="sha256:" + "2" * 64,
        evaluation_job_id="action-job-1",
        evaluation_run_id="run-projection-test",
        generation_run_id="generation-run-1",
        cycle_index=1,
        n5_result_ref=result_ref,
        n5_input_ref=input_ref,
        n4_source_ref=n4_ref,
        context_job_ref=context_ref,
        n5_execution_ref=execution_ref,
    )
    execution = SimpleNamespace(
        job_id="action-job-1",
        run_id="run-projection-test",
        n5_result_ref=result_ref,
    )
    result = SimpleNamespace(
        physical_work_observations=(object(),),
        diagnostics={"physical_work_capture_status": "observed"},
    )
    evaluation = SimpleNamespace(
        selected=selected,
        execution=execution,
        result=result,
        source=SimpleNamespace(),
    )
    design_problem_basis_ref = selected.design_problem_ref
    reentry = SimpleNamespace(
        action_job_id="action-job-1",
        run_id="run-projection-test",
        design_problem_basis_ref=design_problem_basis_ref,
        new_cycle=SimpleNamespace(
            design_problem_basis_ref=design_problem_basis_ref,
            design_problem_ref="sha256:" + "3" * 64,
            cycle_index=1,
            simulation=SimpleNamespace(status="joint_simulated"),
        ),
        continued_generation_run=SimpleNamespace(run_id="generation-run-1"),
        n5_result_ref=result_ref,
        limitations=("currentness_not_established",),
    )
    terminal = SimpleNamespace(
        terminal_outcome="candidate_reentry_completed",
        selected_evaluation=None,
        candidate_reentry_ref=reentry_ref,
    )
    basis = SimpleNamespace(
        basis_role="blocked",
        reason_codes=("n5_prior_live_implementation_not_established",),
        prepared_n5_configuration=object(),
        limitations=("evaluation_basis_not_established",),
    )
    history = SimpleNamespace(
        head=head,
        terminal_ref=terminal_ref,
        terminal=terminal,
        reentry=reentry,
        reentry_evaluation=evaluation,
        selected_basis=basis,
        origin=SimpleNamespace(
            tenant_id="tenant-projection-test",
            cell_id="cell-projection-test",
        ),
    )
    return history, result_body


def _service(*, latest_heads: list[AcquisitionActionHeadRecord]) -> AcquisitionActionService:
    """Make a service adapter with a controlled post-read head set."""
    service = object.__new__(AcquisitionActionService)
    service.control_service = SimpleNamespace(
        _artifact_store=object(),
        _control_store=SimpleNamespace(
            list_acquisition_action_heads_for_source=lambda **_: tuple(latest_heads),
        ),
    )
    return service


def _patch_supported_observation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep this test at the already-resolved history boundary."""
    from polisyos.runtime.http.services import acquisition_n5_projection
    from polisyos.runtime.quality import n5_execution_basis

    monkeypatch.setattr(
        n5_execution_basis,
        "read_n5_execution_implementation_witness",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        n5_execution_basis,
        "_candidate_n5_experiment_observation_supported",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        acquisition_n5_projection,
        "build_candidate_n5_result_body",
        lambda **_kwargs: _history()[1],
    )


def test_candidate_n5_projection_binds_candidate_result_and_refuses_head_advance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A new route generation during the result read prevents a stale current result."""
    history, body = _history()
    _patch_supported_observation(monkeypatch)
    monkeypatch.setattr(
        "polisyos.runtime.http.services.acquisition_n5_projection.build_candidate_n5_result_body",
        lambda **_kwargs: body,
    )
    service = _service(latest_heads=[history.head])

    projection = service._candidate_experiment_n5_result_projection(history)

    assert projection is not None
    assert projection.result_body.artifact_ref == history.reentry.n5_result_ref
    assert projection.configuration_use == "not_established"
    assert projection.implementation_currentness == "not_established"
    assert projection.authoritative_for == ("api_display",)
    assert projection.may_not_use_for == (
        "n5_evaluation_retention",
        "claim_authority",
        "publication_authority",
    )

    payload = projection.model_dump(mode="python")
    payload["implementation_currentness"] = "recomputed"
    with pytest.raises(ValidationError):
        CandidateExperimentN5ResultProjection.model_validate(payload)

    service = _service(latest_heads=[history.head, _head(2)])
    with pytest.raises(AcquisitionActionServiceError) as changed:
        service._candidate_experiment_n5_result_projection(history)
    assert changed.value.code == "candidate_experiment_current_action_head_changed"

    foreign_route = replace(_head(2), route_id="sha256:" + "b" * 64)
    service = _service(latest_heads=[history.head, foreign_route])
    with pytest.raises(AcquisitionActionServiceError) as foreign:
        service._candidate_experiment_n5_result_projection(history)
    assert foreign.value.code == "candidate_experiment_action_history_conflict"


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (
            artifacts.ArtifactOwnershipError("foreign tenant"),
            "candidate_experiment_n5_result_scope_refused",
        ),
        (
            artifacts.ArtifactReadOnlyUnavailableError("CAS reader unavailable"),
            "candidate_experiment_n5_result_storage_unavailable",
        ),
        (
            ValueError("selected manifest mismatch"),
            "candidate_experiment_n5_result_selected_view_not_established",
        ),
    ],
)
def test_candidate_n5_projection_maps_post_history_read_failures(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected_code: str,
) -> None:
    """A raced foreign, unavailable, or invalid result read returns a typed refusal."""
    from polisyos.runtime.http.services import acquisition_n5_projection

    history, _ = _history()
    _patch_supported_observation(monkeypatch)

    def fail_after_history(**_kwargs: Any) -> RunCandidateSimulationN5ResultBody:
        raise error

    monkeypatch.setattr(
        acquisition_n5_projection,
        "build_candidate_n5_result_body",
        fail_after_history,
    )
    service = _service(latest_heads=[history.head])
    with pytest.raises(AcquisitionActionServiceError) as refused:
        service._candidate_experiment_n5_result_projection(history)
    assert refused.value.code == expected_code


def test_unavailable_wrapper_still_surfaces_a_nested_ownership_refusal() -> None:
    """Typed storage unavailability does not hide a nested foreign-owner denial."""
    from polisyos.runtime.http.services.acquisition_action_service import (
        _candidate_experiment_n5_result_read_error_code,
    )

    unavailable = artifacts.ArtifactReadOnlyUnavailableError("wrapped CAS reader failure")
    try:
        raise artifacts.ArtifactOwnershipError("foreign tenant")
    except artifacts.ArtifactOwnershipError as denied:
        unavailable.__cause__ = denied

    assert _candidate_experiment_n5_result_read_error_code(unavailable) == (
        "candidate_experiment_n5_result_scope_refused"
    )

    wrapped_unavailable = ValueError("selected CAS read was not established")
    wrapped_unavailable.__cause__ = artifacts.ArtifactReadOnlyUnavailableError("CAS offline")
    assert _candidate_experiment_n5_result_read_error_code(wrapped_unavailable) == (
        "candidate_experiment_n5_result_storage_unavailable"
    )


@pytest.mark.parametrize(
    ("code", "status_code"),
    [
        ("candidate_experiment_n5_result_scope_refused", 403),
        ("candidate_experiment_n5_result_storage_unavailable", 503),
        ("candidate_experiment_n5_result_selected_view_not_established", 409),
    ],
)
def test_candidate_experiment_result_read_errors_keep_http_classification(
    code: str,
    status_code: int,
) -> None:
    """Foreign scope, unavailable storage, and invalid selected views stay distinct."""
    from polisyos.runtime.http.routes.acquisitions import _raise_service_error

    with pytest.raises(RuntimeHTTPError) as raised:
        _raise_service_error(AcquisitionActionServiceError(code))
    assert raised.value.status_code == status_code
    assert raised.value.code == code
