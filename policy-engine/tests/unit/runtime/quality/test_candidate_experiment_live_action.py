"""Owner-bound refusal and one-operation outcome-reuse tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.runtime.http.services.control_plane_store import (
    ControlJobExecutionAdmission,
    ControlJobExecutionScope,
)
from polisyos.runtime.quality import acquisition_route_loop as route_loop
from polisyos.runtime.quality import candidate_acquisition_action as action
from polisyos.runtime.quality.acquisition_route_loop import _ResolvedCurrentCandidateExperiment
from tests._helpers.lane01_candidate_action_served import build_candidate_port_owners


def _candidate_action_case(
    *,
    final_outcomes: tuple[object, ...] | None = None,
    final_error: Exception | None = None,
) -> dict[str, object]:
    """Build a bounded consumer seam; values here do not establish runtime authority."""

    class CandidatePhase(SimpleNamespace):
        pass

    phase_type = CandidatePhase
    phase_ref = "sha256:" + "a" * 64
    head = SimpleNamespace(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="source-a",
        route_id="route-a",
        action_generation=1,
        job_id="action-job",
        receipt_ref=phase_ref,
    )
    phase = phase_type(
        tenant_id=head.tenant_id,
        cell_id=head.cell_id,
        run_id=head.run_id,
        source_job_id=head.source_job_id,
        route_id=head.route_id,
        source_payload_ref="source-payload",
        capability_manifest_ref="manifest",
        request_content_hash="request-hash",
        policy_scope=SimpleNamespace(),
        policy_ref="policy-ref",
        action_generation=head.action_generation,
        job_id=head.job_id,
        receipt_phase="executing",
    )
    outcome = SimpleNamespace(
        head=head,
        latest_receipt=phase,
        executing_phase_ref=phase_ref,
        executing_phase=phase,
        phase_chain=(SimpleNamespace(receipt_ref=phase_ref, receipt=phase),),
    )
    outcomes = (outcome,)
    origin = SimpleNamespace(
        tenant_id=phase.tenant_id,
        cell_id=phase.cell_id,
        run_id=phase.run_id,
        source_job_id=phase.source_job_id,
        route_id=phase.route_id,
        source_payload_ref=phase.source_payload_ref,
        capability_manifest_ref=phase.capability_manifest_ref,
        request_content_hash=phase.request_content_hash,
        policy_scope=phase.policy_scope,
        policy_ref=phase.policy_ref,
    )
    current_origin = SimpleNamespace(**vars(origin), current_action_head=head)
    sink_calls: list[object] = []

    class Sink:
        def __init__(self) -> None:
            self.final_outcomes = final_outcomes
            self.final_error = final_error
            self.final_callback = None

        def experiment_action_outcomes(self, **kwargs: object) -> tuple[object, ...]:
            sink_calls.append(kwargs.get("verified_origin"))
            if len(sink_calls) == 1:
                return outcomes
            if self.final_callback is not None:
                self.final_callback()
            if self.final_error is not None:
                raise self.final_error
            if self.final_outcomes is None:
                return outcomes
            return self.final_outcomes

    sink = Sink()

    class Loop:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def _resolve_current_candidate_experiment_resolution(
            self, *, run_id: str
        ) -> _ResolvedCurrentCandidateExperiment:
            assert run_id == origin.run_id
            verified_outcomes = sink.experiment_action_outcomes(verified_origin=origin)
            return _ResolvedCurrentCandidateExperiment(
                origin=current_origin,
                outcomes=verified_outcomes,
            )

    service = SimpleNamespace(
        acquisition_route_sink=sink,
        resolve_completed_control_job_core_run_source=lambda *_args, **_kwargs: None,
    )
    job = SimpleNamespace(
        kind="acquisition",
        state="running",
        run_id=origin.run_id,
        job_id=head.job_id,
        attempt=1,
    )
    job.same_execution_inputs = lambda other: other is job
    scope = ControlJobExecutionScope(
        status="established",
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        actor_subject="candidate-operator",
        actor_authenticated=True,
        actor_roles=("acquisition-operator",),
    )
    admission = ControlJobExecutionAdmission(
        job=job,
        scope=scope,
        admission_capability_manifest_ref=None,
        attempt=1,
        manifest_pointer_state="admission_current",
    )

    class ControlStore:
        current_head = head

        def current_execution_job_admission(self) -> ControlJobExecutionAdmission:
            return admission

        def get_acquisition_action_head(self, **_scope: object) -> object:
            return self.current_head

    selections = [object()]
    selection_calls = 0

    def select_source(_bridge: object, _origin: object) -> object:
        nonlocal selection_calls
        selection_calls += 1
        return selections[min(selection_calls - 1, len(selections) - 1)]

    return {
        "bridge": SimpleNamespace(
            control_store=ControlStore(), artifact_store=object(), event_log=object()
        ),
        "admission": admission,
        "current_origin": current_origin,
        "head": head,
        "loop_class": Loop,
        "origin": origin,
        "outcomes": outcomes,
        "phase": phase,
        "phase_ref": phase_ref,
        "phase_type": phase_type,
        "route_loop": route_loop,
        "select_source": select_source,
        "selections": selections,
        "service": service,
        "sink": sink,
        "sink_calls": sink_calls,
    }


def _install_candidate_action_case(
    monkeypatch: pytest.MonkeyPatch, case: dict[str, object]
) -> None:
    monkeypatch.setattr(action, "_require_canonical_action_bridge", lambda _bridge: case["service"])
    monkeypatch.setattr(case["route_loop"], "AcquisitionRouteLoop", case["loop_class"])
    monkeypatch.setattr(
        case["route_loop"],
        "AcquisitionCandidateExperimentPhaseReceipt",
        case["phase_type"],
    )
    monkeypatch.setattr(
        action,
        "_same_candidate_experiment_origin_source",
        lambda _supplied, _current: True,
    )

    def select_outcome(outcomes: tuple[object, ...], **_kwargs: object) -> object:
        if not outcomes:
            raise ValueError("candidate_experiment_action_history_not_current")
        if outcomes is not case["outcomes"]:
            raise ValueError("candidate_experiment_action_phase_not_current")
        return outcomes[-1]

    monkeypatch.setattr(action, "_select_current_candidate_experiment_outcome", select_outcome)
    monkeypatch.setattr(action, "_candidate_experiment_source_selection", case["select_source"])


def _pending_candidate_action_case(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, object], object, object, list[str]]:
    """Add typed pending/action records for the scoped historical-read test."""
    from polisyos.core import artifacts as artifact_module
    from polisyos.core.artifacts import ArtifactRef

    case = _candidate_action_case()
    _install_candidate_action_case(monkeypatch, case)
    pending = case["phase"]
    pending.receipt_phase = "candidate_input_reentry_pending"
    action_ref = ArtifactRef(
        artifact_id="sha256:" + "c" * 64,
        kind=action.CANDIDATE_ACTION_KIND,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "d" * 64,
    )
    pending.candidate_receipt_ref = action_ref
    pending.coarse_phase = "candidate_input_prepared"
    pending.recovery_state = "reentry_recovery_required"
    pending.owner_receipt_refs = (str(action_ref.artifact_id),)
    executing = case["phase_type"](**vars(pending))
    executing.receipt_phase = "executing"
    executing.coarse_phase = "executing"
    executing.recovery_state = "none"
    executing.candidate_receipt_ref = None
    executing.owner_receipt_refs = ()
    executing.receipt_id = "executing-action-phase"
    executing_ref = "sha256:" + "b" * 64
    case["outcomes"][0].phase_chain = (
        SimpleNamespace(receipt_ref=executing_ref, receipt=executing),
        SimpleNamespace(receipt_ref=case["phase_ref"], receipt=pending),
    )

    class CandidateReceipt:
        def __init__(self) -> None:
            self.action_phase_ref = executing_ref
            self.selection = case["selections"][0]

        def __eq__(self, other: object) -> bool:
            return (
                type(other) is CandidateReceipt
                and self.action_phase_ref == other.action_phase_ref
                and self.selection == other.selection
            )

        @classmethod
        def model_validate(cls, _payload: object) -> CandidateReceipt:
            return cls()

    monkeypatch.setattr(action, "CandidateAcquisitionActionReceipt", CandidateReceipt)
    monkeypatch.setattr(
        artifact_module,
        "artifact_ref_for_manifest",
        lambda _manifest: SimpleNamespace(artifact_id=executing_ref),
    )
    monkeypatch.setattr(
        artifact_module, "load_core_json_artifact", lambda *_args, **_kwargs: object()
    )
    case["bridge"].artifact_store = SimpleNamespace(get_manifest=lambda _ref: object())
    history_calls: list[str] = []

    def historical_reader(**kwargs: object) -> tuple[object, object, object]:
        history_calls.append("historical")
        assert kwargs["receipt_ref"] == action_ref
        assert kwargs["executing_phase"] is executing
        assert kwargs["executing_phase_ref"] == executing_ref
        return CandidateReceipt(), object(), object()

    monkeypatch.setattr(
        action, "read_candidate_experiment_acquisition_action_historical", historical_reader
    )
    return case, action_ref, executing, history_calls


def test_candidate_reentry_defers_only_the_redundant_historical_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the reentry consumer may defer; ordinary phase resolution still verifies history."""
    case, action_ref, _executing, history_calls = _pending_candidate_action_case(monkeypatch)

    context = action._current_candidate_experiment_action_context(
        case["bridge"],
        case["origin"],
        case["phase_ref"],
        required_phase="candidate_input_reentry_pending",
        candidate_action_ref=action_ref,
        defer_historical_reentry=True,
    )

    assert context.action is not None
    assert context.phase is case["phase"]
    assert context.outcome is case["outcomes"][0]
    assert history_calls == []

    action._current_candidate_experiment_action_context(
        case["bridge"],
        case["origin"],
        case["phase_ref"],
        required_phase="candidate_input_reentry_pending",
        candidate_action_ref=action_ref,
    )
    assert history_calls == ["historical"]


def test_candidate_reentry_uses_one_late_fresh_owner_fold_and_historical_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reentry folds owner history once after source selection, then reads its bound window."""
    case, action_ref, _executing, events = _pending_candidate_action_case(monkeypatch)
    case["bridge"].action_head_sink = case["sink"]

    def record_owner_read(**kwargs: object) -> tuple[object, ...]:
        if kwargs.get("verified_origin") is not None:
            events.append("initial-owner")
        else:
            events.append("reentry-fresh-owner")
        return case["outcomes"]

    case["sink"].experiment_action_outcomes = record_owner_read
    context = action._current_candidate_experiment_reentry_action_context(
        case["bridge"], case["origin"], case["phase_ref"], action_ref
    )

    assert context.action.action_phase_ref == "sha256:" + "b" * 64
    assert context.phase is case["phase"]
    assert events == ["initial-owner", "reentry-fresh-owner", "historical"]


def test_candidate_reentry_rejects_fresh_outcome_drift_before_historical_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A changed execution-phase pointer cannot reuse the earlier owner snapshot."""
    case, action_ref, _executing, events = _pending_candidate_action_case(monkeypatch)
    case["bridge"].action_head_sink = case["sink"]
    monkeypatch.setattr(
        action,
        "_select_current_candidate_experiment_outcome",
        lambda outcomes, **_kwargs: outcomes[-1],
    )

    def record_owner_read(**kwargs: object) -> tuple[object, ...]:
        if kwargs.get("verified_origin") is not None:
            events.append("initial-owner")
            return case["outcomes"]
        events.append("reentry-fresh-owner")
        drifted = SimpleNamespace(
            **{
                **vars(case["outcomes"][0]),
                "executing_phase_ref": "sha256:" + "e" * 64,
            }
        )
        return (drifted,)

    case["sink"].experiment_action_outcomes = record_owner_read
    with pytest.raises(ValueError, match="candidate_experiment_action_live_owner_changed"):
        action._current_candidate_experiment_reentry_action_context(
            case["bridge"], case["origin"], case["phase_ref"], action_ref
        )

    assert events == ["initial-owner", "reentry-fresh-owner"]


def test_candidate_reentry_rejects_history_removed_after_final_source_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The late owner fold sees removals made after selection, with no extra earlier replay."""
    case, action_ref, _executing, _history_calls = _pending_candidate_action_case(monkeypatch)
    case["bridge"].action_head_sink = case["sink"]
    events: list[str] = []
    base_select_source = case["select_source"]
    source_selection_calls = 0

    def drift_after_final_source_selection(bridge: object, origin: object) -> object:
        nonlocal source_selection_calls
        source_selection_calls += 1
        selection = base_select_source(bridge, origin)
        events.append(f"source-selection-{source_selection_calls}")
        if source_selection_calls == 2:
            case["sink"].final_outcomes = ()
        return selection

    monkeypatch.setattr(
        action, "_candidate_experiment_source_selection", drift_after_final_source_selection
    )

    def record_owner_read(**kwargs: object) -> tuple[object, ...]:
        if kwargs.get("verified_origin") is not None:
            events.append("initial-owner")
            return case["outcomes"]
        events.append("reentry-fresh-owner")
        final_outcomes = case["sink"].final_outcomes
        return case["outcomes"] if final_outcomes is None else final_outcomes

    case["sink"].experiment_action_outcomes = record_owner_read
    with pytest.raises(ValueError, match="candidate_experiment_action_live_owner_changed"):
        action._current_candidate_experiment_reentry_action_context(
            case["bridge"], case["origin"], case["phase_ref"], action_ref
        )

    assert events == [
        "initial-owner",
        "source-selection-1",
        "source-selection-2",
        "reentry-fresh-owner",
    ]


def test_candidate_action_reuses_owner_outcomes_and_keeps_final_currentness_fold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One verified fold supplies selection; the later no-origin fold remains fresh."""
    case = _candidate_action_case()
    _install_candidate_action_case(monkeypatch, case)

    selected, phase, admission = action._current_candidate_experiment_action(
        case["bridge"], case["origin"], case["phase_ref"]
    )

    assert selected is case["selections"][0]
    assert phase is case["phase"]
    assert admission is case["admission"]
    assert case["sink_calls"] == [case["origin"], None]


@pytest.mark.parametrize(
    ("late_change", "expected_error"),
    [
        ("removed_history", "candidate_experiment_action_live_owner_changed"),
        ("rebound_selection", "candidate_experiment_action_live_owner_changed"),
        ("changed_head", "candidate_experiment_action_live_owner_changed"),
    ],
)
def test_candidate_action_still_rejects_late_owner_changes(
    monkeypatch: pytest.MonkeyPatch,
    late_change: str,
    expected_error: str,
) -> None:
    """The final owner fence rejects removed outcomes, source rebinding, or a moved head."""
    case = _candidate_action_case(final_outcomes=() if late_change == "removed_history" else None)
    _install_candidate_action_case(monkeypatch, case)
    if late_change == "rebound_selection":
        case["selections"].append(object())
    elif late_change == "changed_head":
        case["bridge"].control_store.current_head = SimpleNamespace()  # type: ignore[attr-defined]

    with pytest.raises(ValueError, match=expected_error):
        action._current_candidate_experiment_action(
            case["bridge"], case["origin"], case["phase_ref"]
        )

    assert case["sink_calls"][0] is case["origin"]
    assert case["sink_calls"][1:] == ([None] if late_change != "changed_head" else [])


def test_candidate_action_maps_late_owner_replay_errors_to_history_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reused final fold preserves the prior history-reader error boundary."""
    case = _candidate_action_case(final_error=ValueError("underlying owner refusal"))
    _install_candidate_action_case(monkeypatch, case)

    with pytest.raises(ValueError, match="candidate_experiment_action_history_not_verified"):
        action._current_candidate_experiment_action(
            case["bridge"], case["origin"], case["phase_ref"]
        )

    assert case["sink_calls"] == [case["origin"], None]


def test_candidate_action_maps_mid_replay_head_advance_to_live_owner_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A head moved between the explicit read and final fold remains a live-owner error."""
    case = _candidate_action_case()
    _install_candidate_action_case(monkeypatch, case)
    changed_ref = "sha256:" + "b" * 64
    changed_head = SimpleNamespace(**{**vars(case["head"]), "receipt_ref": changed_ref})
    changed_outcome = SimpleNamespace(**{**vars(case["outcomes"][0]), "head": changed_head})
    case["sink"].final_outcomes = (changed_outcome,)
    case["sink"].final_callback = lambda: setattr(
        case["bridge"].control_store, "current_head", changed_head
    )

    with pytest.raises(ValueError, match="candidate_experiment_action_live_owner_changed"):
        action._current_candidate_experiment_action(
            case["bridge"], case["origin"], case["phase_ref"]
        )

    assert case["sink_calls"] == [case["origin"], None]


def test_candidate_experiment_action_requires_canonical_control_owner_before_replay(
    tmp_path: Path,
) -> None:
    """A real SQLite-backed bridge without its composed Control owner cannot admit a phase."""
    owners = build_candidate_port_owners(tmp_path)
    try:
        with pytest.raises(TypeError, match="candidate_action_canonical_bridge_required"):
            action._current_candidate_experiment_action(
                owners.bridge,
                None,
                "sha256:" + "a" * 64,
            )
    finally:
        owners.control_store.close()
