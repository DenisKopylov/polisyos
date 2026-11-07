"""Unit tests for strict predecessor pins and candidate action tuple binding."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from polisyos.core import artifacts
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    CandidateExperimentRouteMutationRequest,
    CandidateExperimentRouteReplayPins,
)
from polisyos.runtime.quality.agent_action_authority import agent_action_content_hash
from tests.unit.runtime.http.services.test_acquisition_action_service import (
    _candidate_experiment_action_fixture,
)


def _predecessor_ref(
    *,
    kind: str = "runtime_quality.acquisition_route_loop_receipt",
    media_type: str = "application/json",
    profile: str | None = "sha256:" + "a" * 64,
) -> artifacts.ArtifactRef:
    return artifacts.ArtifactRef(
        artifact_id="sha256:" + "e" * 64,
        kind=kind,
        media_type=media_type,
        manifest_profile_sha256=profile,
    )


def _with_predecessor(
    request: CandidateExperimentRouteMutationRequest,
    predecessor: artifacts.ArtifactRef,
) -> CandidateExperimentRouteMutationRequest:
    pins_payload = request.replay_pins.model_dump(mode="python")
    pins_payload["predecessor_terminal_ref"] = predecessor
    pins = CandidateExperimentRouteReplayPins.model_validate(pins_payload)
    return request.model_copy(update={"replay_pins": pins})


def test_none_predecessor_preserves_historical_serialization_and_job_identity() -> None:
    origin, request = _candidate_experiment_action_fixture()
    serialized_pins = request.replay_pins.model_dump(mode="json")
    expected_pins = {
        "source_job_id": request.replay_pins.source_job_id,
        "source_payload_ref": request.replay_pins.source_payload_ref,
        "request_content_hash": request.replay_pins.request_content_hash,
        "compiled_ref": request.replay_pins.compiled_ref.model_dump(mode="json"),
        "planner_report_ref": request.replay_pins.planner_report_ref.model_dump(mode="json"),
        "compiler_report_ref": request.replay_pins.compiler_report_ref.model_dump(mode="json"),
        "configured_port_source_ref": request.replay_pins.configured_port_source_ref.model_dump(
            mode="json"
        ),
        "policy_ref": request.replay_pins.policy_ref.model_dump(mode="json"),
        "candidate_digest": request.replay_pins.candidate_digest,
    }

    assert "predecessor_terminal_ref" not in serialized_pins
    assert serialized_pins == expected_pins

    historical_job_payload = {
        "tenant_id": origin.tenant_id,
        "cell_id": origin.cell_id,
        "run_id": origin.run_id,
        "source_job_id": origin.source_job_id,
        "route_id": origin.route_id,
        "request_content_hash": origin.request_content_hash,
        "replay_pins": expected_pins,
        "idempotency_key": request.idempotency_key,
        "human_decision_record_ref": request.human_decision_record_ref,
    }
    expected_job_id = "candidate-experiment-" + agent_action_content_hash(
        historical_job_payload
    ).removeprefix("sha256:")
    assert AcquisitionActionService._candidate_experiment_job_id(origin, request) == expected_job_id


@pytest.mark.parametrize(
    ("kind", "media_type", "profile"),
    [
        ("runtime_quality.other_receipt", "application/json", "sha256:" + "a" * 64),
        (
            "runtime_quality.acquisition_route_loop_receipt",
            "application/octet-stream",
            "sha256:" + "a" * 64,
        ),
        ("runtime_quality.acquisition_route_loop_receipt", "application/json", None),
    ],
)
def test_malformed_or_profileless_predecessor_is_rejected(
    kind: str,
    media_type: str,
    profile: str | None,
) -> None:
    _, request = _candidate_experiment_action_fixture()
    predecessor = _predecessor_ref(kind=kind, media_type=media_type, profile=profile)
    pins_payload = request.replay_pins.model_dump(mode="python")
    pins_payload["predecessor_terminal_ref"] = predecessor

    with pytest.raises(ValueError):
        CandidateExperimentRouteReplayPins.model_validate(pins_payload)


def test_predecessor_profile_changes_job_and_invocation_identity() -> None:
    origin, request = _candidate_experiment_action_fixture()
    origin.effective_source_cycle = SimpleNamespace(cycle_index=11)
    first_ref = _predecessor_ref(profile="sha256:" + "a" * 64)
    second_ref = first_ref.model_copy(update={"manifest_profile_sha256": "sha256:" + "b" * 64})
    first_request = _with_predecessor(request, first_ref)
    second_request = _with_predecessor(request, second_ref)

    first_job_id = AcquisitionActionService._candidate_experiment_job_id(origin, first_request)
    second_job_id = AcquisitionActionService._candidate_experiment_job_id(origin, second_request)
    first_invocation = AcquisitionActionService._candidate_experiment_action_tuple(
        origin, first_request
    )[1]
    second_invocation = AcquisitionActionService._candidate_experiment_action_tuple(
        origin, second_request
    )[1]

    assert first_ref.artifact_id == second_ref.artifact_id
    assert first_job_id != second_job_id
    assert first_invocation.invocation_id != second_invocation.invocation_id
    assert first_invocation.parameters["replay_pins"]["predecessor_terminal_ref"] == (
        first_ref.model_dump(mode="json")
    )
    assert second_invocation.parameters["replay_pins"]["predecessor_terminal_ref"] == (
        second_ref.model_dump(mode="json")
    )


def test_action_tuple_uses_effective_cycle_index() -> None:
    origin, request = _candidate_experiment_action_fixture()
    origin.effective_source_cycle = SimpleNamespace(cycle_index=12)

    invocation = AcquisitionActionService._candidate_experiment_action_tuple(origin, request)[1]

    assert origin.source_cycle.cycle_index != origin.effective_source_cycle.cycle_index
    assert invocation.cycle_index == origin.effective_source_cycle.cycle_index
