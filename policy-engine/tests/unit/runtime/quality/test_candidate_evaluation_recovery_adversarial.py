"""Adversarial decision recovery through real selected CAS and SQLite events.

The existing decision fixture supplies component parents, not a real action,
world producer, or N5. Only the current action, route, prior-owner and world
intent closure are unit adapters. Evaluation persistence, authority/event
verification, CAS profile inventory and selected pointer files remain real.
These tests do not establish the WIP @3 acquisition route or a live lease.
"""

from __future__ import annotations

import errno
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core import artifacts
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality import acquisition_evaluation_dispatch as dispatch
from polisyos.runtime.quality.acquisition_evaluation import (
    PRODUCER,
    CandidateAcquisitionEvaluationDecision,
    _candidate_evaluation_event_id,
    persist_acquisition_evaluation_artifact,
    read_acquisition_evaluation_artifact,
)
from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
from polisyos.runtime.quality.diagnostic_events import (
    DiagnosticEventContractError,
    load_diagnostic_event_type_registry,
    validate_diagnostic_event,
)
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.generation_cycle import JointSimulationPort
from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_hash
from tests.unit.runtime.quality.test_candidate_evaluation_artifact import _decision_fixture
from tests.unit.runtime.quality.test_candidate_source_receipt_recovery import (
    _alternate as _same_bytes_profile,
)


def _bind_unit_closure(
    case: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    *,
    store: Any = None,
    events: RuntimeDiagnosticEventLog | None = None,
) -> AcquisitionWorldGrowthBridge:
    bridge = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
    bridge.artifact_store = store or case.cas
    bridge.event_log = events or case.events
    monkeypatch.setattr(bridge, "_require_selected_candidate_action", lambda **_: case.action)
    monkeypatch.setattr(bridge, "candidate_source_selection", lambda _: object())
    monkeypatch.setattr(bridge, "_candidate_source_prior_owner", lambda **_: (None, None, None))
    monkeypatch.setattr(
        bridge,
        "_candidate_world_materialization_intent",
        lambda **_: (case.decision.candidate_world_intent_ref, object()),
    )
    monkeypatch.setattr(bridge, "_paths", lambda *_args, **_kwargs: (case.overlay, None))
    return bridge


@pytest.fixture
def decision_recovery_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Reuse the real persisted-decision fixture and disclose its adapted closure."""
    fixture = _decision_fixture(tmp_path)
    decision = fixture.decision
    root = tmp_path / "selector"
    root.mkdir()
    case = SimpleNamespace(
        **vars(fixture),
        action=SimpleNamespace(
            action_job_id=decision.action_job_id,
            action_generation=decision.action_generation,
            candidate_source_ref=decision.candidate_source_ref,
            unit_lease="current-unit-action",
        ),
        closure=SimpleNamespace(
            tenant_id=decision.tenant_id,
            cell_id=decision.cell_id,
            run_id=decision.run_id,
            source_job_id=decision.source_job_id,
            route_id=decision.route_id,
            compiled_ref=decision.compiled_ref,
            design_problem_ref=decision.design_problem_ref,
            design_problem_basis_ref=decision.design_problem_basis_ref,
            source_cycle=SimpleNamespace(
                selected_candidate_ref=decision.candidate_id,
                selected_candidate_content_hash=decision.source_candidate_content_hash,
            ),
        ),
        overlay=root / "overlay.sqlite",
        root=tmp_path,
    )
    try:
        case.ref = persist_acquisition_evaluation_artifact(
            store=case.cas, event_log=case.events, record=decision
        )
        case.store = case.cas  # Shape reused by the real same-bytes CAS profile helper.
        case.manifest = case.cas.get_manifest(case.ref)
        case.body = case.cas.get_bytes(case.ref)
        case.event_id = _candidate_evaluation_event_id(decision)
        case.pointer = root / (case.event_id + ".selected.json")
        case.bridge = _bind_unit_closure(case, monkeypatch)
        assert _read(case, case.ref) == decision
        assert not case.pointer.exists()
        yield case
    finally:
        fixture.events._store.close()


def _read(case: SimpleNamespace, ref: artifacts.ArtifactRef) -> object:
    return read_acquisition_evaluation_artifact(
        store=case.bridge.artifact_store,
        event_log=case.bridge.event_log,
        ref=ref,
        record_type=CandidateAcquisitionEvaluationDecision,
    )


def _recover(case: SimpleNamespace, bridge: Any = None) -> Any:
    return dispatch._candidate_evaluation_artifact_for_recovery(
        bridge=bridge or case.bridge,
        closure=case.closure,
        candidate_action_ref=case.decision.candidate_action_ref,
        role="decision",
    )


def _select(case: SimpleNamespace, bridge: Any = None) -> artifacts.ArtifactRef:
    return dispatch._select_candidate_evaluation_artifact(
        bridge=bridge or case.bridge, closure=case.closure, record=case.decision
    )


def _refuse_repeated_work(monkeypatch: pytest.MonkeyPatch) -> None:
    def refused(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("saved decision recovery attempted producer reissue or N5 work")

    monkeypatch.setattr(dispatch, "persist_acquisition_evaluation_artifact", refused)
    monkeypatch.setattr(JointSimulationPort, "__call__", refused)


def test_persisted_evaluation_event_requires_its_canonical_runtime_contract(
    decision_recovery_case: SimpleNamespace,
) -> None:
    """The real writer's event needs its canonical entry, even for an unknown decision."""
    case = decision_recovery_case
    (saved,) = case.events.list_events(event_id=case.event_id, limit=2)
    event = saved.event
    registry = load_diagnostic_event_type_registry()
    contract = registry.event_types[event.event_type]
    assert event.event_type == "polisyos.runtime.acquisition.evaluation.v1"
    assert event.event_source == event.producer_component == PRODUCER
    assert event.phase == "acquisition_evaluation"
    assert event.state_after == "not_established"
    assert event.payload_ref == str(case.ref.artifact_id)
    assert contract.category == "acquisition_evaluation"
    assert contract.authority_role == "runtime_authority"
    assert contract.phase_required is contract.producer_required is True
    assert contract.serious_no_sampling is True
    assert contract.allowed_event_sources == (PRODUCER,)
    assert contract.payload_ref_policy == "cas_required"
    assert (
        validate_diagnostic_event(
            event, registry=registry, expected_artifact_refs=(str(case.ref.artifact_id),)
        )
        == event
    )

    # Remove only the registration in a local negative input; the on-disk
    # catalog, validator and persisted event remain untouched.
    without_registration = registry.model_copy(
        update={
            "event_types": {
                name: row for name, row in registry.event_types.items() if name != event.event_type
            }
        }
    )
    with pytest.raises(DiagnosticEventContractError) as error:
        validate_diagnostic_event(event, registry=without_registration)
    assert error.value.code == "unknown_diagnostic_event_type"
    assert _read(case, case.ref) == case.decision
    assert not case.pointer.exists()


@pytest.mark.parametrize(
    ("corruption", "code"),
    [
        ({"phase": ""}, "diagnostic_event_phase_missing"),
        (
            {"producer_component": "", "producer_version": ""},
            "diagnostic_event_producer_missing",
        ),
        (
            {"event_source": "polisyos.runtime.foreign_evaluation_owner"},
            "diagnostic_event_source_not_allowed",
        ),
        (
            {"event_source": "polisyos.bundle.unit_recovery"},
            "bundle_event_cannot_mint_runtime_authority",
        ),
        (
            {"sampling_decision": "sampled_away", "sampling_rate": 0.01},
            "serious_diagnostic_event_sampled_away",
        ),
    ],
    ids=["phase", "producer", "foreign-source", "bundle-source", "sampled-away"],
)
def test_persisted_evaluation_event_rejects_corrupted_runtime_envelope(
    decision_recovery_case: SimpleNamespace,
    corruption: dict[str, object],
    code: str,
) -> None:
    """Corrupt only validation inputs derived from the real saved event."""
    case = decision_recovery_case
    (saved,) = case.events.list_events(event_id=case.event_id, limit=2)
    with pytest.raises(DiagnosticEventContractError) as error:
        validate_diagnostic_event(saved.event.model_copy(update=corruption))
    assert error.value.code == code
    assert _read(case, case.ref) == case.decision
    assert not case.pointer.exists()


def test_eligible_same_bytes_foreign_lineage_refuses_both_recovery_consumers(
    decision_recovery_case: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A competing eligible view must pass the real record lineage owner."""
    case = decision_recovery_case
    assert _recover(case) == (case.ref, case.decision)
    first, *rest = case.manifest.inputs
    foreign = _same_bytes_profile(
        case, inputs=[first.model_copy(update={"role": "unit_foreign_parent_role"}), *rest]
    )
    assert case.cas.get_bytes(foreign) == case.body
    with pytest.raises(ValueError, match="acquisition_evaluation_artifact_input_lineage_mismatch"):
        _read(case, foreign)
    before = case.cas.inventory_snapshot(artifact_id=case.ref.artifact_id)
    assert before.verdict == "pass"
    _refuse_repeated_work(monkeypatch)
    for consume in (_recover, _select):
        with pytest.raises(
            ValueError, match="acquisition_evaluation_artifact_input_lineage_mismatch"
        ):
            consume(case)
        assert not case.pointer.exists()
    assert case.cas.inventory_snapshot(artifact_id=case.ref.artifact_id) == before
    assert len(case.events.list_events(event_id=case.event_id, limit=2)) == 1


def test_two_individually_owner_readable_views_cannot_repair_a_selected_pointer(
    decision_recovery_case: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Blob identity cannot choose between two actual eligible selected profiles."""
    case = decision_recovery_case
    alternate = _same_bytes_profile(
        case,
        warnings=[
            *case.manifest.warnings,
            artifacts.WarningRecord(code="unit.alternate", msg="view"),
        ],
    )
    assert _read(case, case.ref) == _read(case, alternate) == case.decision
    before = case.cas.inventory_snapshot(artifact_id=case.ref.artifact_id)
    assert before.verdict == "pass"
    profiles = {
        artifacts.artifact_ref_for_manifest(row.manifest).manifest_profile_sha256
        for row in before.entries
        if row.manifest.authority is not None
    }
    assert profiles == {case.ref.manifest_profile_sha256, alternate.manifest_profile_sha256}
    _refuse_repeated_work(monkeypatch)
    for consume in (_recover, _select):
        with pytest.raises(ValueError, match="candidate_source_reentry_profile_not_unique"):
            consume(case)
        assert not case.pointer.exists()
    assert case.cas.inventory_snapshot(artifact_id=case.ref.artifact_id) == before


def test_selected_pointer_with_missing_real_expected_event_refuses_reissue(
    decision_recovery_case: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A saved file cannot substitute for the expected SQLite authority event."""
    case = decision_recovery_case
    assert _select(case) == case.ref
    pointer_bytes = case.pointer.read_bytes()
    original_events = case.bridge.event_log
    with closing(
        ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "empty-events.sqlite3")
    ) as empty:
        case.bridge.event_log = RuntimeDiagnosticEventLog(store=empty, artifact_store=case.cas)
        assert case.bridge.event_log.list_events(event_id=case.event_id, limit=2) == []
        _refuse_repeated_work(monkeypatch)
        for consume in (_recover, _select):
            with pytest.raises(ValueError, match="candidate_evaluation_event_missing"):
                consume(case)
        assert case.pointer.read_bytes() == pointer_bytes
    case.bridge.event_log = original_events
    assert _recover(case) == (case.ref, case.decision)
    assert _select(case) == case.ref


@pytest.mark.parametrize("read_error", ["permission", "io"])
def test_expected_event_lookup_denial_never_becomes_absence_or_reissue(
    decision_recovery_case: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    read_error: str,
) -> None:
    """Inject an operational event-read failure; the underlying event/CAS are real."""
    case = decision_recovery_case
    real_list = case.events.list_events
    failure = (
        PermissionError(errno.EACCES, "unit expected-event lookup denied")
        if read_error == "permission"
        else OSError(errno.EIO, "unit expected-event lookup unavailable")
    )

    def denied_expected_event(**kwargs: Any) -> Any:
        if kwargs.get("event_id") == case.event_id:
            raise failure
        return real_list(**kwargs)

    _refuse_repeated_work(monkeypatch)
    with monkeypatch.context() as denied:
        denied.setattr(case.events, "list_events", denied_expected_event)
        for consume in (_recover, _select):
            with pytest.raises(type(failure)) as refused:
                consume(case)
            assert refused.value is failure
            assert not case.pointer.exists()
    assert _recover(case) == (case.ref, case.decision)
    assert _select(case) == case.ref
    assert len(real_list(event_id=case.event_id, limit=2)) == 1


def test_cold_repeated_recovery_preserves_exact_record_and_does_no_producer_work(
    decision_recovery_case: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reopen both durable owners after the event/pointer crash window."""
    case = decision_recovery_case
    _refuse_repeated_work(monkeypatch)
    before = case.cas.inventory_snapshot(artifact_id=case.ref.artifact_id)
    assert before.verdict == "pass"
    with closing(
        ControlPlaneStore(backend="sqlite", sqlite_path=case.root / "control.sqlite3")
    ) as cold:
        cold_cas = artifacts.FileSystemCAS(case.root / "cas").for_tenant(
            "tenant-a", cell_id="cell-a"
        )
        cold_events = RuntimeDiagnosticEventLog(store=cold, artifact_store=cold_cas)
        bridge = _bind_unit_closure(case, monkeypatch, store=cold_cas, events=cold_events)
        assert _recover(case, bridge) == (case.ref, case.decision)
        assert not case.pointer.exists()
        assert _select(case, bridge) == case.ref
        for _ in range(2):
            assert _recover(case, bridge) == (case.ref, case.decision)
            assert _select(case, bridge) == case.ref
        assert len(cold_events.list_events(event_id=case.event_id, limit=2)) == 1
    assert (
        case.bridge._read_candidate_world_pointer(
            case.pointer,
            candidate_action_ref=case.decision.candidate_action_ref,
            expected_kind=case.decision.ARTIFACT_KIND,
        )
        == case.ref
    )
    assert _read(case, case.ref) == case.decision
    assert case.cas.get_bytes(case.ref) == case.body
    assert case.cas.inventory_snapshot(artifact_id=case.ref.artifact_id) == before


@pytest.mark.parametrize("consumer", ["discover", "select"])
def test_action_movement_after_real_inventory_cannot_repair_the_pointer(
    decision_recovery_case: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    consumer: str,
) -> None:
    """Exercise ordering at an adapted action boundary, without claiming a real lease."""
    case = decision_recovery_case
    original_action = case.action
    real_recover = case.bridge._recover_unique_candidate_owner_view

    def recover_then_move(**kwargs: Any) -> Any:
        result = real_recover(**kwargs)
        case.action = SimpleNamespace(
            **{**vars(original_action), "unit_lease": "changed-unit-action"}
        )
        return result

    _refuse_repeated_work(monkeypatch)
    monkeypatch.setattr(case.bridge, "_recover_unique_candidate_owner_view", recover_then_move)
    with pytest.raises(ValueError, match="candidate_evaluation_selected_action_changed"):
        (_recover if consumer == "discover" else _select)(case)
    assert not case.pointer.exists()
    assert len(case.events.list_events(event_id=case.event_id, limit=2)) == 1


def test_action_movement_after_new_event_cannot_publish_a_pointer(
    decision_recovery_case: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A completed event remains recoverable if the adapted action moves before selection."""
    case = decision_recovery_case
    original_action = case.action
    # The fixture has already persisted the original decision. Give this fresh
    # event log a distinct valid decision so the real writer reaches the new
    # event/pointer window instead of encountering that existing CAS authority.
    payload = case.decision.model_dump(mode="json", exclude={"content_hash"})
    payload["generated_at"] = "2026-11-03T01:00:00+00:00"
    case.decision = CandidateAcquisitionEvaluationDecision.model_validate(
        {**payload, "content_hash": exact_n5_content_hash(payload)}
    )
    with closing(
        ControlPlaneStore(backend="sqlite", sqlite_path=case.root / "fresh-events.sqlite3")
    ) as fresh:
        events = RuntimeDiagnosticEventLog(store=fresh, artifact_store=case.cas)
        bridge = _bind_unit_closure(case, monkeypatch, events=events)
        original_persist = dispatch.persist_acquisition_evaluation_artifact
        written: list[artifacts.ArtifactRef] = []

        def persist_then_move(**kwargs: Any) -> artifacts.ArtifactRef:
            selected = original_persist(**kwargs)
            written.append(selected)
            case.action = SimpleNamespace(
                **{**vars(original_action), "unit_lease": "changed-unit-action"}
            )
            return selected

        monkeypatch.setattr(dispatch, "persist_acquisition_evaluation_artifact", persist_then_move)
        with pytest.raises(ValueError, match="candidate_evaluation_selected_action_changed"):
            _select(case, bridge)
        assert not case.pointer.exists()
        assert len(events.list_events(event_id=case.event_id, limit=2)) == 1

        case.action = original_action
        _refuse_repeated_work(monkeypatch)
        assert len(written) == 1
        assert _select(case, bridge) == written[0]
        assert len(events.list_events(event_id=case.event_id, limit=2)) == 1
