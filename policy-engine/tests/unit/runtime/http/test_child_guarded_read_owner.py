"""SQLite job-bound guarded CAS consumer; no jobless authorization."""

from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

import polisyos.common.async_tools as async_tools
import polisyos.core.artifacts.canonical_profile as canonical_profile
from polisyos.common.borrowed_execution import _BorrowedExecutionGrant
from polisyos.core.artifacts.canonical_profile import (
    CoreJsonReadBoundsRefusalError,
    CoreJsonReadLimits,
    read_core_json_artifact_bounded,
    read_core_manifest_profile_bounded,
)
from polisyos.core.artifacts.child_release import (
    _JOB_OWNER_BOOTSTRAP_TOKEN,
    ChildJobReleaseLocator,
    ChildReleaseUnavailableError,
    _install_child_job_owner,
)
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.child_custody import ChildComputationBinding, ChildGuardedReadUnknown
from polisyos.core.run.context import RunContext
from polisyos.fabric.connectors.resilience.circuit_breaker import CircuitBreaker
from polisyos.runtime.http.errors import RuntimeDependencyTimeoutError
from polisyos.runtime.http.resilience import (
    BlockingDependencyGuard,
    _bootstrap_guarded_child_custody,
    guard_runtime_cas,
)
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from tests.unit.runtime.http.test_child_control_authorization import _job, _Resolver


@pytest.mark.parametrize("probe", ["normal", "timeout", "scope"])
def test_sqlite_job_guarded_actual_consumer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, probe: str
) -> None:
    db_path = tmp_path / "control.sqlite3"
    control = ControlPlaneStore(backend="sqlite", sqlite_path=db_path)
    attempt = _job(control)
    shared = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", shared)
    monkeypatch.setenv("POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS", "1" if probe == "timeout" else "5")
    monkeypatch.setenv("POLISYOS_RUNTIME_CAS_BREAKER_FAILURE_THRESHOLD", "1")
    guard = BlockingDependencyGuard(
        dependency_name="parent",
        timeout_seconds=60,
        breaker=CircuitBreaker("test-parent"),
        executor=shared,
    )

    def run(grant: _BorrowedExecutionGrant) -> None:
        _exercise_job(tmp_path, control, grant, monkeypatch, probe)

    try:
        with control.job_execution_fence(job_id="job-a", worker_id="worker-a", attempt=attempt):
            guard.run_with_parent_admission(run, deadline_monotonic=time.monotonic() + 60)
    finally:
        guard.close()
        shared.shutdown(wait=True)


def _exercise_job(
    tmp_path: Path,
    control: ControlPlaneStore,
    grant: _BorrowedExecutionGrant,
    monkeypatch: pytest.MonkeyPatch,
    probe: str,
) -> None:
    raw = FileSystemCAS(
        tmp_path / "served", tenant_id="tenant-a", cell_id="cell-a", ownership_enforced=False
    )
    registry = build_default_registry_bundle(raw, return_selected_profile=True)
    workflow = raw.put_json(
        {},
        PutOptions(kind="tests.workflow", media_type="application/json"),
        return_selected_profile=True,
    )
    state = raw.put_json(
        {},
        PutOptions(kind="tests.state", media_type="application/json"),
        return_selected_profile=True,
    )
    source_ref = raw.put_json(
        {"source": 2},
        PutOptions(kind="tests.source", media_type="application/json"),
        return_selected_profile=True,
    )
    served = guard_runtime_cas(raw)
    root = RunContext.start(
        served,
        registry.bundle_ref,
        run_id="run-a",
        run_dir=raw.root / "runs" / "run-a",
        tenant_id="tenant-a",
        cell_id="cell-a",
        control_job_id="job-a",
    )
    parent_attempt = str(uuid4())
    basis = root._record_runtime_invocation_started(
        attempt_id=parent_attempt,
        attempt_number=1,
        workflow_spec_ref=workflow,
        node_alias="parent",
        component_id="tests.parent",
        input_state_ref=state,
    )
    binding = ChildComputationBinding(
        root_run_id="run-a",
        control_job_id="job-a",
        parent_attempt_id=parent_attempt,
        parent_basis_ref=basis,
        tenant_id="tenant-a",
        cell_id="cell-a",
        policy_id="tests",
        policy_version="1",
        template_sha256="sha256:" + "1" * 64,
        admission_id="test-owner",
        child_invocation_id="parent",
        admission_generation=1,
        deadline=datetime.now(UTC) + timedelta(seconds=45),
    )
    grant.bind_parent(
        run_id="run-a",
        job_id="job-a",
        attempt_id=parent_attempt,
        basis_ref=json.dumps(
            basis.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ),
    )
    fence = control.child_computation_publication_fence(grant=grant, binding=binding)
    custody, reader = _bootstrap_guarded_child_custody(
        root,
        staging_root=tmp_path / "private",
        closure_resolver=_Resolver(),
        publication_fence=fence,
    )
    _install_child_job_owner(
        custody._ledger.store_identity, control, token=_JOB_OWNER_BOOTSTRAP_TOKEN
    )
    intent = custody.job_session_intent(binding)
    custody.bind_job_intent(intent, fence.begin_session(intent))
    release = threading.Event()
    finished = threading.Event()
    limits = CoreJsonReadLimits(
        max_bytes=4096, max_depth=20, max_elements=100, max_manifest_bytes=100000
    )
    try:
        managed = custody.parent_store(binding, input_refs=(source_ref,))
        if probe == "scope":
            child_binding = binding.model_copy(update={"child_invocation_id": "child"})
            with pytest.raises(
                ChildReleaseUnavailableError, match="direct_child_scope_admission_unsupported"
            ):
                custody.open_scope(child_binding, input_refs=(source_ref,))
            prepared = custody.prepare_scope(child_binding, input_refs=(source_ref,))
            claim = prepared.recompute()
            child = fence.admit_prepared_scope(prepared)
            from polisyos.core.run.context import (
                _FinalizeRecoveryError,
                _validate_run_owner_snapshot_ref,
            )

            class UnappointedStore:
                def __getattr__(self, name):
                    return getattr(child.store, name)

            snapshot_ref = child.run._owner_snapshot_ref
            assert snapshot_ref is not None
            with pytest.raises(
                _FinalizeRecoveryError, match="run_owner_child_release_owner_not_established"
            ):
                _validate_run_owner_snapshot_ref(UnappointedStore(), snapshot_ref)
            row = control._child_event_row("job-a", f"child.release.scope.{claim.scope_id}")
            assert row is not None
            locator = ChildJobReleaseLocator(job_id="job-a", event_id=int(row["event_id"]))
            ControlPlaneStore(backend="sqlite", sqlite_path=control._sqlite_path).verify_scope(
                locator, claim
            )
            with pytest.raises(ChildReleaseUnavailableError):
                prepared.complete(locator)
            selected = child.store.put_json(
                {"candidate": 1},
                PutOptions(kind="tests.child.value", media_type="application/json"),
                return_selected_profile=True,
            )
            assert (
                read_core_json_artifact_bounded(child.store, selected, limits=limits).effective_ref
                == selected
            )
            child.run.add_output(selected)
            child.run.finalize()
            handoff = custody.admit_handoff(child, selected)
            assert (
                read_core_json_artifact_bounded(managed, selected, limits=limits).effective_ref
                == selected
            )
            with pytest.raises(
                ChildReleaseUnavailableError, match="final_projection_not_parent_owned"
            ):
                custody.release_parent((handoff,), selected)
            final = managed.put_json(
                {"selected": selected.model_dump(mode="json")},
                PutOptions(
                    kind="tests.child.projection",
                    media_type="application/json",
                    schema=SchemaInfo(name="tests.ChildProjection", version="1"),
                ),
                return_selected_profile=True,
            )
            fresh = FileSystemCAS(raw.root, ownership_enforced=False)
            with pytest.raises((FileNotFoundError, ChildReleaseUnavailableError)):
                fresh.get_bytes(selected)
            receipt = custody.release_parent((handoff,), final)
            assert receipt.projection_ref == final
            assert fresh.get_bytes(selected)
            assert json.loads(fresh.get_bytes(final))["selected"] == selected.model_dump(
                mode="json"
            )
            return
        ref = managed.put_json(
            {"candidate": 1},
            PutOptions(kind="tests.child.json", media_type="application/json"),
            return_selected_profile=True,
        )
        blob = managed.put_bytes(
            b"private bytes",
            PutOptions(kind="tests.child.value", media_type="application/octet-stream"),
            return_selected_profile=True,
        )
        assert managed.get_bytes(blob) == b"private bytes"
        assert managed.has(blob)
        assert managed.verify(blob).ok
        with pytest.raises(CoreJsonReadBoundsRefusalError, match="canon_profile_absent"):
            read_core_manifest_profile_bounded(managed, blob, max_manifest_bytes=100000)
        assert read_core_json_artifact_bounded(managed, ref, limits=limits).effective_ref == ref
        adapter = ensure_ir_artifact_store(managed)
        assert read_core_json_artifact_bounded(adapter, ref, limits=limits).effective_ref == ref
        wrong = read_core_manifest_profile_bounded(managed, source_ref, max_manifest_bytes=100000)
        with pytest.raises(ChildReleaseUnavailableError, match="guarded_manifest_receipt_mismatch"):
            read_core_json_artifact_bounded(managed, ref, limits=limits, manifest_read=wrong)

        class EqualFake:
            def __eq__(self, _other: object) -> bool:
                return True

            def __hash__(self) -> int:
                return hash(managed)

        with pytest.raises(CoreJsonReadBoundsRefusalError):
            read_core_json_artifact_bounded(EqualFake(), ref, limits=limits)
        with monkeypatch.context() as removal:
            removal.setattr(canonical_profile, "_guarded_canonical_reader", lambda _store: None)
            with pytest.raises(CoreJsonReadBoundsRefusalError) as removed:
                read_core_json_artifact_bounded(managed, ref, limits=limits)
            assert isinstance(removed.value.__cause__, ChildReleaseUnavailableError)
            assert "guarded_direct_read_operation_unavailable" in str(removed.value.__cause__)
        if probe == "normal":
            receipt = custody.release_parent((), blob)
            assert receipt.projection_ref == blob
            fresh = FileSystemCAS(raw.root, ownership_enforced=False)
            assert fresh.get_bytes(blob) == b"private bytes"
            return

        entered = threading.Event()
        original = FileSystemCAS.open_member_bounded

        def blocked_open(self, *args, **kwargs):
            inner = original(self, *args, **kwargs)

            @contextmanager
            def blocked():
                with inner as stream:
                    entered.set()
                    try:
                        assert release.wait(3)
                        yield stream
                    finally:
                        finished.set()

            return blocked()

        monkeypatch.setattr(FileSystemCAS, "open_member_bounded", blocked_open)
        with pytest.raises(ChildGuardedReadUnknown) as outcome:
            read_core_json_artifact_bounded(managed, ref, limits=limits)
        assert isinstance(outcome.value.__cause__, RuntimeDependencyTimeoutError)
        assert entered.is_set()
        assert reader.has_unsettled_operations()
        assert reader._stage_proxy._guard._breaker.is_open()
        release.set()
        assert finished.wait(2)
        reader._stage_proxy._guard._executor.shutdown(wait=True)
        # This owner-issued future confirms physical slot cleanup. It does not
        # change the previously raised unknown read into a successful receipt.
        assert not reader.has_unsettled_operations()
    finally:
        release.set()
        reader.close()
        served.close()
