"""Operation-local reuse controls over an explicitly replaced upstream fold.

The small rows below stand for a completed owner replay. They establish no
authority or numerical result. Actual CAS reads remain in the nested boundary
adapters so removal/corruption is distinguished from merely changing a marker.
The served generation route qualifies the real owner composition separately.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import (
    ArtifactWriteOptions,
    FileSystemCAS,
    SchemaInfo,
    load_core_json_artifact,
)
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobExecutionAdmission,
    ControlJobExecutionScope,
    ControlJobRecord,
)
from polisyos.runtime.quality import candidate_acquisition_action as actions


@dataclass
class _Row:
    label: str
    values: dict[str, object] = field(default_factory=dict)
    action_phase_ref: str = "sha256:" + "a" * 64
    action_generation: int = 1
    phase_chain: tuple[object, ...] = ()

    def same_execution_identity(self, other: object) -> bool:
        return type(other) is _Row and self == other


@dataclass
class _Origin:
    tenant_id: str = "tenant-read-scope"
    cell_id: str = "cell-read-scope"
    run_id: str = "run-read-scope"
    source_job_id: str = "source-read-scope"
    route_id: str = "route-read-scope"
    candidate_terminal_history_chain: tuple[object, ...] = ()


@dataclass
class _PhaseRecord:
    receipt_ref: str
    receipt: _Row


def _case(tmp_path, monkeypatch, *, admission=None):
    store = FileSystemCAS(tmp_path / "cas")

    def persist(label):
        return store.put_json(
            {"label": label},
            ArtifactWriteOptions(kind="fixture.read_operation", media_type="application/json"),
            return_selected_profile=True,
        )

    refs = {name: persist(name) for name in ("action", "phase", "source", "deep-parent")}
    phase = _Row("phase")
    # The production adapter consumes these named fields; no row is promoted
    # to runtime authority by this component-only fixture.
    phase_record = _PhaseRecord(receipt_ref=phase.action_phase_ref, receipt=phase)
    chain = (phase_record,)
    origin = _Origin()
    context = actions._VerifiedCurrentCandidateExperimentReentryAction(
        selection=_Row("selection"),
        phase=phase,
        admission=admission if admission is not None else _Row("admission"),
        action=_Row("action", values={"nested": {"value": "initial"}}),
        head=_Row("head"),
        outcome=_Row("outcome", phase_chain=chain),
        budget_window=_Row("window"),
    )
    state = {
        "source": _Row("source"),
        "created": {"scope": "original"},
        "outbox": _Row("outbox"),
        "heads": (context.head,),
        "admission": context.admission,
        "selection": context.selection,
        "revoked": False,
        "folds": 0,
        "nested_reads": 0,
    }

    class Control:
        def get_job(self, _job_id):
            return state["source"]

        def get_job_created_event_payload(self, _job_id):
            return state["created"]

        def get_job_created_outbox_event(self, _job_id):
            return state["outbox"]

        def list_acquisition_action_heads_for_source(self, **_scope):
            return state["heads"]

        def get_acquisition_action_head(self, **_scope):
            return state["heads"][0]

        def current_execution_job_admission(self):
            return state["admission"]

    def phase_chain(*_args, **kwargs):
        assert kwargs == {"verified_origin": origin, "reuse_verified_origin": True}
        load_core_json_artifact(store, refs["phase"])
        return chain

    service = SimpleNamespace(
        acquisition_route_sink=SimpleNamespace(
            _verified_candidate_experiment_phase_chain=phase_chain
        )
    )
    bridge = SimpleNamespace(control_store=Control(), artifact_store=store)

    def replay(*args):
        assert args == (bridge, origin, "pending-phase", refs["action"])
        state["folds"] += 1
        load_core_json_artifact(store, refs["deep-parent"])
        if state["folds"] == 2 and state.get("on_final_fold") is not None:
            state["on_final_fold"]()
        return context

    def selection(*args):
        assert args == (bridge, origin)
        if state["revoked"]:
            raise ValueError("candidate_experiment_source_policy_not_current")
        return state["selection"]

    def historical(**kwargs):
        assert kwargs["executing_phase"] is phase
        assert kwargs["executing_phase_ref"] == phase.action_phase_ref
        assert kwargs["receipt_ref"] == refs["action"]
        for name in ("action", "phase", "source"):
            load_core_json_artifact(store, refs[name])
        state["nested_reads"] += 1
        return context.action, _Row("source"), context.budget_window

    monkeypatch.setattr(actions, "_require_canonical_action_bridge", lambda selected: service)
    monkeypatch.setattr(actions, "_current_candidate_experiment_reentry_action_context", replay)
    monkeypatch.setattr(actions, "_candidate_experiment_source_selection", selection)
    monkeypatch.setattr(
        actions, "read_candidate_experiment_acquisition_action_historical", historical
    )
    return SimpleNamespace(
        store=store, refs=refs, state=state, origin=origin, bridge=bridge, context=context
    )


def _read(case, context):
    return actions._read_candidate_experiment_action_in_operation(
        bridge=case.bridge,
        origin=case.origin,
        receipt_ref=case.refs["action"],
        context=context,
    )


def test_reentry_read_operation_reuses_only_its_immutable_owner_fold(tmp_path, monkeypatch):
    case = _case(tmp_path, monkeypatch)
    with actions._candidate_experiment_reentry_read_operation(
        case.bridge, case.origin, "pending-phase", case.refs["action"]
    ) as context:
        for _ in range(3):
            assert _read(case, context) is case.context.action
        assert case.state["folds"] == 1
        assert case.state["nested_reads"] == 3
    assert case.state["folds"] == 2
    assert case.state["nested_reads"] == 4
    with pytest.raises(ValueError, match="read_operation_changed"):
        _read(case, context)
    with pytest.raises(ValueError, match="read_operation_not_active"):
        _read(case, case.context)


@pytest.mark.parametrize(
    "change",
    ["head_profile", "new_head", "source", "created", "outbox", "owner", "revoked", "mutable"],
)
def test_reentry_read_operation_refuses_changed_dependencies(tmp_path, monkeypatch, change):
    case = _case(tmp_path, monkeypatch)
    mutated = False

    def mutate_then_read():
        nonlocal mutated
        with actions._candidate_experiment_reentry_read_operation(
            case.bridge, case.origin, "pending-phase", case.refs["action"]
        ) as context:
            assert _read(case, context) is case.context.action
            if change == "head_profile":
                case.state["heads"] = (replace(case.context.head, values={"profile": "foreign"}),)
            elif change == "new_head":
                case.state["heads"] = (*case.state["heads"], _Row("new-head", action_generation=2))
            elif change == "source":
                case.state["source"] = _Row("foreign-source")
            elif change == "created":
                case.state["created"]["scope"] = "foreign"
            elif change == "outbox":
                case.state["outbox"].values["subject"] = "foreign"
            elif change == "owner":
                case.state["admission"] = _Row("other-owner")
            elif change == "revoked":
                case.state["revoked"] = True
            else:
                context.action.values["nested"]["value"] = "mutated-in-place"
            mutated = True
            _read(case, context)

    reason = (
        "read_operation_owner_changed"
        if change == "owner"
        else "source_policy_not_current"
        if change == "revoked"
        else "read_operation_changed"
    )
    with pytest.raises(ValueError, match=reason):
        mutate_then_read()
    assert mutated


@pytest.mark.parametrize("parent", ["action", "phase", "source", "deep-parent"])
def test_reentry_read_operation_reopens_actual_parent_bytes(tmp_path, monkeypatch, parent):
    case = _case(tmp_path, monkeypatch)
    blob, _manifest = case.store._paths(case.refs[parent].artifact_id)
    missing = blob.with_suffix(".held-for-removal-control")

    def remove_then_read():
        with actions._candidate_experiment_reentry_read_operation(
            case.bridge, case.origin, "pending-phase", case.refs["action"]
        ) as context:
            assert _read(case, context) is case.context.action
            blob.replace(missing)
            _read(case, context)

    try:
        with pytest.raises((OSError, RuntimeError, ValueError)):
            remove_then_read()
        assert missing.exists()
    finally:
        if missing.exists():
            missing.replace(blob)
    with actions._candidate_experiment_reentry_read_operation(
        case.bridge, case.origin, "pending-phase", case.refs["action"]
    ) as context:
        assert _read(case, context) is case.context.action


def test_reentry_read_operation_rejects_a_reconstructed_carrier(tmp_path, monkeypatch):
    case = _case(tmp_path, monkeypatch)
    with actions._candidate_experiment_reentry_read_operation(
        case.bridge, case.origin, "pending-phase", case.refs["action"]
    ) as context:
        with pytest.raises(ValueError, match="read_operation_changed"):
            _read(case, replace(context))
        assert _read(case, context) is case.context.action


def test_reentry_read_operation_rechecks_live_admission_after_final_fold(tmp_path, monkeypatch):
    """A normal owner reassignment during the final replay prevents successful close."""
    now = datetime(2026, 11, 13, 12, tzinfo=UTC)
    capability_ref = "sha256:" + "b" * 64
    job = ControlJobRecord(
        job_id="action-read-scope",
        kind="acquisition",
        state="running",
        run_id="run-read-scope",
        pipeline_id=None,
        requested_execution_profile="dev",
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=capability_ref,
        payload_ref="sha256:" + "c" * 64,
        submitted_by="operator-read-scope",
        created_at=now,
        started_at=now,
        finished_at=None,
        lease_owner="worker-original",
        lease_expires_at=now + timedelta(hours=1),
        attempt=1,
        error_message=None,
        progress={},
    )
    admission = ControlJobExecutionAdmission(
        job=job,
        scope=ControlJobExecutionScope(
            status="established",
            tenant_id="tenant-read-scope",
            cell_id="cell-read-scope",
            actor_subject="operator-read-scope",
            actor_authenticated=True,
            actor_roles=("acquisition-operator",),
        ),
        admission_capability_manifest_ref=capability_ref,
        attempt=1,
        manifest_pointer_state="admission_current",
    )
    case = _case(tmp_path, monkeypatch, admission=admission)

    def reassign_during_final_fold():
        # The upstream fold returns its earlier snapshot, while a subsequent
        # live read observes the independently advanced fencing identity.
        case.state["admission"] = replace(
            admission,
            job=replace(job, lease_owner="worker-reassigned", attempt=2),
            attempt=2,
        )

    case.state["on_final_fold"] = reassign_during_final_fold

    def consume_then_close():
        with actions._candidate_experiment_reentry_read_operation(
            case.bridge, case.origin, "pending-phase", case.refs["action"]
        ) as context:
            assert _read(case, context) is case.context.action

    with pytest.raises(ValueError, match="read_operation_owner_changed"):
        consume_then_close()
    assert case.state["folds"] == 2
    assert case.state["admission"].job.lease_owner == "worker-reassigned"
    assert not case.state["admission"].same_execution_identity(admission)


def test_reentry_read_operation_refuses_same_bytes_foreign_selected_profile(tmp_path, monkeypatch):
    case = _case(tmp_path, monkeypatch)
    foreign = case.store.put_json(
        {"label": "action"},
        ArtifactWriteOptions(
            kind="fixture.read_operation",
            media_type="application/json",
            schema=SchemaInfo(name="fixture.foreign.view", version="1"),
        ),
        return_selected_profile=True,
    )
    assert foreign.artifact_id == case.refs["action"].artifact_id
    assert foreign.manifest_profile_sha256 != case.refs["action"].manifest_profile_sha256
    with actions._candidate_experiment_reentry_read_operation(
        case.bridge, case.origin, "pending-phase", case.refs["action"]
    ) as context:
        with pytest.raises(ValueError, match="read_operation_changed"):
            actions._read_candidate_experiment_action_in_operation(
                bridge=case.bridge, origin=case.origin, receipt_ref=foreign, context=context
            )
        assert _read(case, context) is case.context.action


def test_reentry_read_operation_detects_corrupt_action_bytes_then_restoration(
    tmp_path, monkeypatch
):
    case = _case(tmp_path, monkeypatch)
    blob, _manifest = case.store._paths(case.refs["action"].artifact_id)
    original = blob.read_bytes()
    try:
        with actions._candidate_experiment_reentry_read_operation(
            case.bridge, case.origin, "pending-phase", case.refs["action"]
        ) as context:
            assert _read(case, context) is case.context.action
            blob.write_bytes(original + b"corrupt")
            with pytest.raises((OSError, RuntimeError, ValueError)):
                _read(case, context)
            blob.write_bytes(original)
            assert _read(case, context) is case.context.action
    finally:
        blob.write_bytes(original)
