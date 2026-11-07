"""A later blocked candidate action keeps an earlier N5 result explicitly prior."""

from __future__ import annotations

import copy
from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from polisyos.core import artifacts
from polisyos.core.contracts.runtime import RunCandidateSimulationN5ResultBody
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionActionServiceError,
    CandidateExperimentCurrentActionProjection,
    CandidateExperimentN5ResultProjection,
    CandidateExperimentPriorN5ResultProjection,
)
from polisyos.runtime.http.services.control_plane_store import AcquisitionActionHeadRecord
from polisyos.runtime.quality.acquisition_evaluation import CandidateExperimentTerminalHistory


def _ref(kind: str, fill: str, *, profile: str = "f") -> artifacts.ArtifactRef:
    """Create a selected ref with an exact manifest profile."""
    return artifacts.ArtifactRef(
        artifact_id="sha256:" + fill * 64,
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + profile * 64,
    )


def _head(generation: int, *, route_fill: str = "a") -> AcquisitionActionHeadRecord:
    """Create one exact source action-head view."""
    receipt_ref = "sha256:" + str(generation) * 64
    return AcquisitionActionHeadRecord(
        tenant_id="tenant-prior-n5-test",
        cell_id="cell-prior-n5-test",
        run_id="run-prior-n5-test",
        source_job_id="source-job-stable",
        route_id="sha256:" + route_fill * 64,
        action_generation=generation,
        head_generation=generation,
        receipt_ref=receipt_ref,
        receipt_sha256=receipt_ref,
        durable_event_id=f"event-prior-n5-{generation}",
        coarse_phase="terminal",
        receipt_phase="terminal",
        recovery_state="complete",
        job_id=f"action-job-{generation}",
        predecessor_receipt_ref=None,
        created_at=datetime(2026, 11, 7, tzinfo=UTC),
        receipt_manifest_profile_sha256="sha256:" + "f" * 64,
    )


def _prior_n5_result() -> CandidateExperimentPriorN5ResultProjection:
    """Bind actual displayed N5 bytes to the earlier action, terminal, and reentry."""
    from tests.unit.core.contracts.test_runtime_n5_bodies import _result_body_payload

    result_ref = _ref("polisyos.runtime.joint_simulation_result", "d", profile="b")
    body_payload = _result_body_payload(candidate=True)
    body_payload["artifact_ref"] = result_ref
    body_payload["selected_manifest_profile_sha256"] = result_ref.manifest_profile_sha256
    body = RunCandidateSimulationN5ResultBody.model_validate(body_payload)
    result = CandidateExperimentN5ResultProjection(
        terminal_receipt_ref=_ref(
            "runtime_quality.acquisition_route_loop_receipt", "a", profile="c"
        ),
        reentry_receipt_ref=_ref(
            "runtime_quality.candidate_source_reentry_receipt", "e", profile="1"
        ),
        result_body=body,
        reason_codes=("candidate_evaluation_prior_basis_not_established",),
        limitations=("controller_wide_configuration_use_not_established",),
    )
    return CandidateExperimentPriorN5ResultProjection(
        prior_action_ref=_ref(
            "runtime_quality.acquisition_candidate_action_receipt", "2", profile="3"
        ),
        prior_action_generation=1,
        n5_result=result,
    )


def _blocked_current_payload() -> dict[str, object]:
    """Build a current unknown-comparison blocker with a separate prior result."""
    return {
        "status": "blocked",
        "action_generation": 2,
        "job_id": "candidate-action-current",
        "job_state": "completed",
        "coarse_phase": "terminal",
        "receipt_phase": "terminal",
        "recovery_state": "complete",
        "selected_receipt_ref": _ref(
            "runtime_quality.acquisition_route_loop_receipt", "9", profile="8"
        ),
        "terminal_outcome": "candidate_blocked",
        "evaluation_disposition": "blocked",
        "selected_evaluation": None,
        "candidate_n5_result": None,
        "prior_candidate_n5_result": _prior_n5_result().model_dump(mode="python"),
        "blocker_reason": "candidate_experiment_input_change_not_established",
    }


def test_blocked_current_action_serializes_prior_n5_as_a_separate_candidate_observation() -> None:
    """The latest blocker remains current while earlier numerical output stays displayable."""
    projection = CandidateExperimentCurrentActionProjection.model_validate(
        _blocked_current_payload()
    )

    assert projection.status == "blocked"
    assert projection.terminal_outcome == "candidate_blocked"
    assert projection.evaluation_disposition == "blocked"
    assert projection.blocker_reason == "candidate_experiment_input_change_not_established"
    assert projection.candidate_n5_result is None
    assert projection.selected_evaluation is None
    assert projection.prior_candidate_n5_result is not None
    assert projection.prior_candidate_n5_result.prior_action_generation == 1
    assert projection.prior_candidate_n5_result.n5_result.result_body.candidate_status == (
        "candidate_unverified"
    )
    assert (
        projection.prior_candidate_n5_result.n5_result.result_body.currentness_status
        == "not_established"
    )
    assert not projection.prior_candidate_n5_result.n5_result.result_body.publication_authority

    payload = projection.model_dump(mode="json", exclude_none=True)
    assert "candidate_n5_result" not in payload
    assert (
        payload["selected_receipt_ref"]["artifact_id"]
        != payload["prior_candidate_n5_result"]["n5_result"]["terminal_receipt_ref"]["artifact_id"]
    )


@pytest.mark.parametrize(
    ("change", "expected_error"),
    [
        (
            lambda payload: payload["prior_candidate_n5_result"].update(prior_action_generation=2),
            "candidate_experiment_prior_n5_result_current_projection_mismatch",
        ),
        (
            lambda payload: payload.update(blocker_reason="candidate_input_change_unknown"),
            "candidate_experiment_prior_n5_result_current_projection_mismatch",
        ),
        (
            lambda payload: payload.update(
                candidate_n5_result=payload["prior_candidate_n5_result"]["n5_result"]
            ),
            "candidate_experiment_blocked_projection_mismatch",
        ),
    ],
)
def test_prior_n5_result_cannot_be_relabelled_current_or_attached_to_another_blocker(
    change: Callable[[dict[str, object]], None], expected_error: str
) -> None:
    """A prior body cannot fill the current result slot or change the blocker meaning."""
    payload = copy.deepcopy(_blocked_current_payload())
    change(payload)

    with pytest.raises(ValidationError, match=expected_error):
        CandidateExperimentCurrentActionProjection.model_validate(payload)


def test_prior_action_ref_requires_a_selected_profile_identity() -> None:
    """The old action ref must carry a selected CAS profile."""
    prior = _prior_n5_result().model_dump(mode="python")
    prior["prior_action_ref"] = artifacts.ArtifactRef(
        artifact_id="sha256:" + "2" * 64,
        kind="runtime_quality.acquisition_candidate_action_receipt",
        media_type="application/json",
        manifest_profile_sha256=None,
    )
    with pytest.raises(
        ValidationError, match="candidate_experiment_prior_n5_result_action_ref_invalid"
    ):
        CandidateExperimentPriorN5ResultProjection.model_validate(prior)


def test_prior_result_refuses_a_body_from_another_selected_profile() -> None:
    """The selected result body and its CAS ref must retain one exact profile."""
    prior = _prior_n5_result().model_dump(mode="python")
    prior["n5_result"]["result_body"]["selected_manifest_profile_sha256"] = "sha256:" + "4" * 64

    with pytest.raises(ValidationError):
        CandidateExperimentPriorN5ResultProjection.model_validate(prior)


def test_prior_projection_selects_owner_resolved_candidate_and_fences_on_current_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The old N5 belongs to its prior action while the current blocker remains latest."""
    prior_action_ref = _ref("runtime_quality.acquisition_candidate_action_receipt", "2")
    prior_history = CandidateExperimentTerminalHistory(
        head=_head(1),
        terminal_ref=_ref("runtime_quality.acquisition_route_loop_receipt", "a"),
        terminal=SimpleNamespace(
            terminal_outcome="candidate_reentry_completed",
            blocker_reason=None,
            selected_evaluation=None,
            candidate_action_ref=prior_action_ref,
            action_generation=1,
        ),
        origin=SimpleNamespace(candidate_terminal_history_chain=()),
        phase_chain=(),
        action=None,
        source=None,
        budget_window=None,
        decision=None,
        current_basis=None,
        reentry=object(),
        continuation=None,
        frontier_before=None,
        frontier_after=None,
        evaluation=None,
        selected_basis=SimpleNamespace(basis_role="blocked"),
        reentry_evaluation=object(),
    )
    current_head = _head(2)
    current_history = SimpleNamespace(
        head=current_head,
        terminal=SimpleNamespace(
            terminal_outcome="candidate_blocked",
            blocker_reason="candidate_experiment_input_change_not_established",
        ),
        decision=SimpleNamespace(
            comparison_result="not_established",
            predicate_provenance="not_established",
            reason_codes=("candidate_experiment_input_change_not_established",),
        ),
        origin=SimpleNamespace(candidate_terminal_history_chain=(prior_history,)),
    )
    service = object.__new__(AcquisitionActionService)
    expected_projection = _prior_n5_result().n5_result
    calls: list[tuple[object, object]] = []

    def project_prior(
        history: object,
        *,
        expected_latest_head: AcquisitionActionHeadRecord | None = None,
    ) -> CandidateExperimentN5ResultProjection:
        calls.append((history, expected_latest_head))
        return expected_projection

    monkeypatch.setattr(service, "_candidate_experiment_n5_result_projection", project_prior)
    projected = service._candidate_experiment_prior_n5_result_projection(current_history)

    assert projected.prior_action_ref == prior_action_ref
    assert projected.prior_action_generation == 1
    assert projected.n5_result == expected_projection
    assert calls == [(prior_history, current_head)]

    stale_history = SimpleNamespace(
        **{
            **vars(current_history),
            "head": _head(3),
            "origin": SimpleNamespace(candidate_terminal_history_chain=(prior_history,)),
        }
    )
    with pytest.raises(AcquisitionActionServiceError) as stale:
        service._candidate_experiment_prior_n5_result_projection(stale_history)
    assert stale.value.code == "candidate_experiment_prior_n5_result_history_not_established"

    foreign_history = SimpleNamespace(
        **{
            **vars(current_history),
            "head": _head(2, route_fill="b"),
        }
    )
    with pytest.raises(AcquisitionActionServiceError) as foreign:
        service._candidate_experiment_prior_n5_result_projection(foreign_history)
    assert foreign.value.code == "candidate_experiment_prior_n5_result_history_not_established"
