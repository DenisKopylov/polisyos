"""Actual registered control decisions for a private child producer."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from threading import Thread

import pytest

from polisyos.core.artifacts.child_release import ChildReleaseUnavailableError
from polisyos.core.artifacts.store import PutOptions
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobExecutionAdmissionError,
    ControlJobLeaseLostError,
    ControlPlaneStore,
)
from tests.unit.runtime.http.test_guarded_child_control_bridge import _run_owned_fixture


@pytest.mark.parametrize(
    "probe", ["normal", "stale", "foreign_scope", "foreign_thread", "revoked", "registry_aba"]
)
def test_registered_worker_admits_only_the_current_child_producer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, probe: str
) -> None:
    """Resolve a real Core scope before the registered SQLite decision."""

    def exercise(root, control, custody, reader, fence, grant, binding):
        del root, reader, grant
        intent = custody.job_session_intent(binding)
        custody.bind_job_intent(intent, fence.begin_session(intent))
        custody.parent_store(binding, input_refs=())
        child_binding = binding.model_copy(update={"child_invocation_id": "producer-test"})
        prepared = custody.prepare_scope(child_binding, input_refs=())
        scope = fence.admit_prepared_scope(prepared)

        if probe == "stale":
            original = ControlPlaneStore._admit_child_producer

            def expire_before_decision(store, *, control_operation):
                with closing(sqlite3.connect(tmp_path / "control.sqlite3")) as connection:
                    connection.execute(
                        "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
                        ("2000-01-01T00:00:00+00:00", "job-a"),
                    )
                    connection.commit()
                return original(store, control_operation=control_operation)

            monkeypatch.setattr(ControlPlaneStore, "_admit_child_producer", expire_before_decision)
            with pytest.raises(ControlJobLeaseLostError):
                fence.admit_producer(scope)
            return

        if probe in {"revoked", "registry_aba"}:
            original = ControlPlaneStore._admit_child_producer

            def change_before_decision(store, *, control_operation):
                if probe == "revoked":
                    custody.revoke(scope, reason="producer-test-revocation")
                else:
                    from polisyos.runtime.http import resilience

                    registration = resilience._RUNTIME_CONTROL_STORE_GUARDS.pop(control)
                    resilience._RUNTIME_CONTROL_STORE_GUARDS[control] = registration
                return original(store, control_operation=control_operation)

            monkeypatch.setattr(ControlPlaneStore, "_admit_child_producer", change_before_decision)
            expected = ControlJobExecutionAdmissionError if probe == "revoked" else ValueError
            with pytest.raises(expected) as refusal:
                fence.admit_producer(scope)
            if probe == "revoked":
                assert isinstance(refusal.value.__cause__, ChildReleaseUnavailableError)
            return

        if probe == "foreign_scope":
            with pytest.raises(
                ChildReleaseUnavailableError, match="child_producer_scope_not_current"
            ):
                fence.admit_producer(replace(scope))
            return

        if probe == "foreign_thread":
            errors: list[BaseException] = []

            def attempt() -> None:
                try:
                    fence.admit_producer(scope)
                except BaseException as exc:
                    errors.append(exc)

            other = Thread(target=attempt)
            other.start()
            other.join(timeout=5)
            assert not other.is_alive()
            assert len(errors) == 1
            assert "guarded_child_control_parent_thread_mismatch" in str(errors[0])
            return

        fence.admit_producer(scope)
        selected = scope.store.put_json(
            {"actual": "child work"},
            PutOptions(kind="test.child_producer", media_type="application/json"),
            return_selected_profile=True,
        )
        assert scope.store.get_bytes(selected)
        fence.admit_producer(scope)
        assert not any(item._retired_producer() for item in custody._control_operations.values())

    _run_owned_fixture(tmp_path, monkeypatch, "runtime_core_appointment", before_session=exercise)


@pytest.mark.parametrize("probe", ["normal", "expired", "forged_scope", "wrong_store"])
def test_guarded_foundry_port_uses_the_selected_child_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, probe: str
) -> None:
    """The port reaches its private store only after the actual job decision."""
    from polisyos.core.contracts import CompileRequest
    from polisyos.scientist.orchestration.engine.child_foundry import (
        _CHILD_FOUNDRY_DISPATCH_TOKEN,
        _COMPILE_NODE,
        _ScopedChildFoundryPort,
    )
    from tests.unit.scientist.orchestration.engine.test_child_foundry import _LocalFoundry

    producer_entries: list[str] = []

    class ObservedFoundry(_LocalFoundry):
        def compile(self, store, request):
            # Observe the effect boundary before the first CAS write. A later
            # independent store refusal must not hide an early producer entry.
            producer_entries.append("compile")
            return super().compile(store, request)

    def exercise(root, control, custody, reader, fence, grant, binding):
        del root, control, reader
        intent = custody.job_session_intent(binding)
        custody.bind_job_intent(intent, fence.begin_session(intent))
        parent_store = custody.parent_store(binding, input_refs=())
        child_binding = binding.model_copy(update={"child_invocation_id": "foundry-test"})
        scope = fence.admit_prepared_scope(custody.prepare_scope(child_binding, input_refs=()))
        fence.admit_producer(scope)
        policy = scope.store.put_json(
            {"policy": 1},
            PutOptions(kind="ir.trinity_bundle", media_type="application/json"),
            return_selected_profile=True,
        )
        if probe == "wrong_store":
            with pytest.raises(ValueError, match="child_foundry_scope_store_mismatch"):
                _ScopedChildFoundryPort(
                    delegate=ObservedFoundry(),
                    store=parent_store,
                    scope=scope,
                    grant=grant,
                    fence=fence,
                    reconcile_owner=lambda: None,
                )
            assert producer_entries == []
            return
        port = _ScopedChildFoundryPort(
            delegate=ObservedFoundry(),
            store=scope.store,
            scope=replace(scope) if probe == "forged_scope" else scope,
            grant=grant,
            fence=fence,
            reconcile_owner=lambda: None,
        )
        with pytest.raises(AttributeError, match="child Foundry binding is immutable"):
            port._binding = replace(port._binding, scope=None)
        with pytest.raises(AttributeError):
            port._binding.scope = None
        if probe == "expired":
            original_admit = ControlPlaneStore._admit_child_producer

            def expire_after_preflight(store, *, control_operation):
                # Change the real row only after Core/Runtime preflight. An
                # earlier expiry could be caught by a different owner check
                # and leave the actual producer decision untested.
                with closing(sqlite3.connect(tmp_path / "control.sqlite3")) as connection:
                    connection.execute(
                        "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
                        ("2000-01-01T00:00:00+00:00", "job-a"),
                    )
                    connection.commit()
                return original_admit(store, control_operation=control_operation)

            monkeypatch.setattr(ControlPlaneStore, "_admit_child_producer", expire_after_preflight)
        request = CompileRequest(input_kind="trinity", policy_ref=policy)
        with port._producer_scope(_COMPILE_NODE, _token=_CHILD_FOUNDRY_DISPATCH_TOKEN):
            if probe == "expired":
                with pytest.raises(ControlJobLeaseLostError):
                    port.compile(scope.store, request)
            elif probe == "forged_scope":
                with pytest.raises(
                    ChildReleaseUnavailableError, match="child_producer_scope_not_current"
                ):
                    port.compile(scope.store, request)
            else:
                result = port.compile(scope.store, request)
                assert result.compile_report_ref is not None
                assert scope.store.get_bytes(result.compile_report_ref)
        assert producer_entries == (["compile"] if probe == "normal" else [])

    _run_owned_fixture(tmp_path, monkeypatch, "runtime_core_appointment", before_session=exercise)


@pytest.mark.parametrize("probe", ["progress", "older_snapshot", "basis"])
def test_child_history_reuses_only_a_complete_live_owned_readset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, probe: str
) -> None:
    """Reuse parsing while freshly checking historical bytes and real progress."""
    from uuid import uuid4

    from polisyos.core.run import context as run_context
    from polisyos.core.trace.record import TraceRecord
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from tests.unit.scientist.orchestration.engine.test_admitted_subworkflow_custody import (
        _COMPONENT,
        _parent_inputs,
    )

    def exercise(root, control, custody, reader, fence, grant, binding):
        del root, control, reader, grant
        intent = custody.job_session_intent(binding)
        custody.bind_job_intent(intent, fence.begin_session(intent))
        custody.parent_store(binding, input_refs=())
        child_binding = binding.model_copy(update={"child_invocation_id": "history-test"})
        scope = fence.admit_prepared_scope(custody.prepare_scope(child_binding, input_refs=()))
        fence.admit_producer(scope)
        workflow, state, _ = _parent_inputs(
            scope.store, _COMPONENT, state=ExperimentState(run_id=scope.run.run_manifest.run_id)
        )
        attempt_id = str(uuid4())
        basis = scope.run._record_runtime_invocation_started(
            attempt_id=attempt_id,
            attempt_number=1,
            workflow_spec_ref=workflow,
            node_alias="parent",
            component_id=str(_COMPONENT),
            input_state_ref=state,
        )
        complete_reads: list[str] = []
        original_read = run_context._read_run_owner_records

        def observe_complete_read(store, trace_path, *, run_id):
            if run_id == scope.run.run_manifest.run_id:
                complete_reads.append(run_id)
            return original_read(store, trace_path, run_id=run_id)

        monkeypatch.setattr(run_context, "_read_run_owner_records", observe_complete_read)
        first = scope.run.read_runtime_invocation_attempts()
        assert len(first) == 1 and first[0].basis_ref == basis and first[0].outcome is None
        # Mutating a returned object must not alter the reusable detached proof.
        object.__setattr__(first[0].basis, "node_alias", "counterfeit")
        second = scope.run.read_runtime_invocation_attempts()
        assert second[0].basis.node_alias == "parent"
        assert len(complete_reads) == 1
        if probe == "progress":
            scope.run._record_runtime_invocation_completed(
                attempt_id=attempt_id,
                attempt_number=1,
                basis_ref=basis,
                status="ok",
                outcome_state_ref=state,
                output_refs=[],
            )
            completed = scope.run.read_runtime_invocation_attempts()
            assert len(completed) == 1 and completed[0].outcome is not None
            assert completed[0].outcome.status == "ok"
            assert len(complete_reads) == 2
            return

        owner_before = scope.run._owner_snapshot_ref.model_copy(deep=True)
        tail_before = scope.run._runtime_invocation_tail_ref.model_copy(deep=True)
        assert scope.run.trace_path is not None
        trace_before = scope.run.trace_path.read_bytes()
        selected = basis
        if probe == "older_snapshot":
            initial = TraceRecord.model_validate_json(trace_before.splitlines()[0])
            selected = initial.refs.outputs[0]
            assert selected != owner_before
        blob, _ = custody._stage._paths(selected.artifact_id)
        original = blob.read_bytes()
        try:
            blob.write_bytes(b"corrupted-child-history")
            # Current selected markers and the entire trace stay identical.
            assert scope.run._owner_snapshot_ref == owner_before
            assert scope.run._runtime_invocation_tail_ref == tail_before
            assert scope.run.trace_path.read_bytes() == trace_before
            with pytest.raises(ChildReleaseUnavailableError):
                scope.run.read_runtime_invocation_attempts()
        finally:
            blob.write_bytes(original)
        assert scope.run.read_runtime_invocation_attempts()[0].outcome is None

    _run_owned_fixture(tmp_path, monkeypatch, "runtime_core_appointment", before_session=exercise)
