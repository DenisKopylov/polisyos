"""SQLite job-bound guarded CAS consumer; no jobless authorization."""

from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
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
from polisyos.core.run.child_custody import (
    ChildComputationBinding,
    ChildGuardedReadUnknown,
    ChildParentSettlementError,
)
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

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.mark.parametrize(
    "attribute",
    [
        "_dependency_name",
        "_timeout_seconds",
        "_breaker",
        "_executor",
        "_execution",
        "_unavailable_exception_types",
        "_unavailable_exception_predicate",
    ],
)
def test_guard_registration_does_not_revive_after_dependency_aba(
    tmp_path: Path, attribute: str
) -> None:
    from polisyos.runtime.http.resilience import _require_runtime_filesystem_guard

    guarded = guard_runtime_cas(FileSystemCAS(tmp_path / "cas"))
    original = getattr(guarded._guard, attribute)
    try:
        setattr(guarded._guard, attribute, object())
        setattr(guarded._guard, attribute, original)
        with pytest.raises(ValueError, match="registered_sql_guard_binding_changed"):
            _require_runtime_filesystem_guard(guarded)
    finally:
        guarded.close()


@pytest.mark.parametrize(
    "probe",
    [
        "normal",
        "timeout",
        "scope",
        "proxy_aba",
        "guard_aba",
        "guard_closed_aba",
        "registry_aba",
        "service_rebinding",
        "service_slots",
        "publication_aba",
        "publication_transition",
        "publication_root_contention",
        "suspend_inflight",
        "lost_commit_ack",
    ],
)
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
    *,
    fence_factory: Callable[
        [RunContext, object, _BorrowedExecutionGrant, ChildComputationBinding], Any
    ]
    | None = None,
    before_session: Callable[..., None] | None = None,
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
    fence = (
        control.child_computation_publication_fence(grant=grant, binding=binding)
        if fence_factory is None
        else fence_factory(root, control, grant, binding)
    )
    custody, reader = _bootstrap_guarded_child_custody(
        root,
        staging_root=tmp_path / "private",
        closure_resolver=_Resolver(),
        publication_fence=fence,
    )
    _install_child_job_owner(
        custody._ledger.store_identity, control, token=_JOB_OWNER_BOOTSTRAP_TOKEN
    )
    if before_session is not None:
        try:
            before_session(root, control, custody, reader, fence, grant, binding)
        finally:
            reader.close()
            served.close()
        return
    intent = custody.job_session_intent(binding)
    custody.bind_job_intent(intent, fence.begin_session(intent))
    release = threading.Event()
    finished = threading.Event()
    limits = CoreJsonReadLimits(
        max_bytes=4096, max_depth=20, max_elements=100, max_manifest_bytes=100000
    )
    try:
        managed = custody.parent_store(binding, input_refs=(source_ref,))
        if probe == "service_slots":
            for field in type(reader).__slots__:
                with pytest.raises(AttributeError, match="binding is immutable"):
                    setattr(reader, field, getattr(reader, field))
            with pytest.raises(AttributeError, match="binding is immutable"):
                reader.require_registration = lambda: None
            assert managed.has(source_ref)
            return
        if probe == "service_rebinding":
            from polisyos.runtime.http.resilience import _require_runtime_filesystem_guard

            replacement = guard_runtime_cas(raw)
            try:

                def should_not_read(*_args, **_kwargs):
                    raise AssertionError("replacement registration reached the CAS operation")

                def replace_and_read() -> None:
                    reader._served_proxy = replacement
                    reader._served_registration = _require_runtime_filesystem_guard(replacement)
                    reader._served_lifecycle = replacement._guard._runtime_lifecycle_revision
                    managed.has(source_ref)

                monkeypatch.setattr(FileSystemCAS, "has", should_not_read)
                with pytest.raises((AttributeError, ValueError)):
                    replace_and_read()
            finally:
                replacement.close()
            return
        if probe == "publication_transition":
            entered = threading.Event()
            changed = threading.Event()

            def mutate_guard() -> None:
                entered.set()
                served._guard._timeout_seconds += 1
                changed.set()

            with reader.publication_registration():
                worker = threading.Thread(target=mutate_guard)
                worker.start()
                assert entered.wait(2)
                assert not changed.wait(0.1)
                reader.require_registration()
            assert changed.wait(2)
            worker.join()
            with pytest.raises(ValueError, match="registered_sql_guard_binding_changed"):
                managed.has(source_ref)
            return
        if probe in {"proxy_aba", "guard_aba", "guard_closed_aba", "registry_aba"}:
            if probe == "proxy_aba":
                original = served._target
                served._target = FileSystemCAS(tmp_path / "other")
                served._target = original
            elif probe == "guard_aba":
                original = served._guard._timeout_seconds
                served._guard._timeout_seconds = original + 1
                served._guard._timeout_seconds = original
            elif probe == "guard_closed_aba":
                served._guard.close()
                served._guard._closed = False
            else:
                from polisyos.runtime.http import resilience

                original = resilience._RUNTIME_FILESYSTEM_GUARDS.pop(served)
                resilience._RUNTIME_FILESYSTEM_GUARDS[served] = original

            def should_not_read(*_args, **_kwargs):
                raise AssertionError("revoked registration reached the CAS operation")

            monkeypatch.setattr(FileSystemCAS, "has", should_not_read)
            with pytest.raises(
                ValueError,
                match=r"registered_sql_guard_binding_changed|child_read_guard_binding_changed",
            ):
                managed.has(source_ref)
            return
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
        if probe == "suspend_inflight":
            from polisyos.core.run.context import _FinalizeRecoveryError

            entered = threading.Event()
            resume = threading.Event()
            failures: list[BaseException] = []
            original_has = FileSystemCAS.has

            def blocked_has(store, *args, **kwargs):
                if store is custody._stage:
                    entered.set()
                    assert resume.wait(5)
                return original_has(store, *args, **kwargs)

            def suspend_parent() -> None:
                try:
                    assert entered.wait(5)
                    root.suspend_for_resume()
                except BaseException as exc:
                    failures.append(exc)
                finally:
                    resume.set()

            monkeypatch.setattr(FileSystemCAS, "has", blocked_has)
            worker = threading.Thread(target=suspend_parent)
            worker.start()
            with pytest.raises((ChildReleaseUnavailableError, _FinalizeRecoveryError)):
                managed.has(blob)
            worker.join(timeout=5)
            assert not worker.is_alive() and not failures and root._suspended
            with pytest.raises((ChildReleaseUnavailableError, _FinalizeRecoveryError)):
                custody.release_parent((), blob)
            fresh = FileSystemCAS(raw.root, ownership_enforced=False)
            with pytest.raises((FileNotFoundError, ChildReleaseUnavailableError)):
                fresh.get_bytes(blob)
            return
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

        if probe == "lost_commit_ack":
            copies = 0
            commits = 0
            original_copy = FileSystemCAS._publish_child_release_profiles
            original_commit = custody._ledger.commit

            def observe_copy(*args, **kwargs):
                nonlocal copies
                copies += 1
                return original_copy(*args, **kwargs)

            def commit_then_lose_ack(*args, **kwargs):
                nonlocal commits
                commits += 1
                original_commit(*args, **kwargs)
                raise OSError("lost acknowledgement after durable release head")

            monkeypatch.setattr(FileSystemCAS, "_publish_child_release_profiles", observe_copy)
            monkeypatch.setattr(custody._ledger, "commit", commit_then_lose_ack)
            with pytest.raises(ChildParentSettlementError) as unknown:
                custody.release_parent((), blob)
            assert unknown.value.receipt.release_outcome == "release_visible_durability_unknown"
            assert unknown.value.recovery is not None
            fresh = FileSystemCAS(raw.root, ownership_enforced=False)
            assert fresh.get_bytes(blob) == b"private bytes"
            with pytest.raises(ChildParentSettlementError):
                custody.release_parent((), blob)
            assert (copies, commits) == (1, 1)
            return

        if probe == "publication_aba":
            authorize = fence.authorize_release

            def authorize_then_change_guard(candidate):
                locator = authorize(candidate)
                original = served._guard._timeout_seconds
                served._guard._timeout_seconds = original + 1
                served._guard._timeout_seconds = original
                return locator

            monkeypatch.setattr(fence, "authorize_release", authorize_then_change_guard)
            with pytest.raises(ChildParentSettlementError) as unknown:
                custody.release_parent((), blob)
            assert unknown.value.receipt.release_outcome == "release_state_unknown"
            fresh = FileSystemCAS(raw.root, ownership_enforced=False)
            with pytest.raises((FileNotFoundError, ChildReleaseUnavailableError)):
                fresh.get_bytes(blob)
            return

        if probe == "publication_root_contention":
            root_held = threading.Event()
            root_waiting = threading.Event()
            guard_changed = threading.Event()
            failures: list[str] = []
            authorize = fence.authorize_release
            transition = root._parent_state_transition_lease

            def hold_root() -> None:
                with root._worker_merge_lock:
                    root_held.set()
                    if not guard_changed.wait(2):
                        failures.append("guard mutation blocked while waiting for Root")

            def change_guard() -> None:
                if not root_waiting.wait(5):
                    failures.append("publication did not reach Root")
                    return
                served._guard._timeout_seconds += 1
                guard_changed.set()

            holder = threading.Thread(target=hold_root)
            mutator = threading.Thread(target=change_guard)

            @contextmanager
            def observed_transition(*args, **kwargs):
                root_waiting.set()
                with transition(*args, **kwargs):
                    yield

            def authorize_then_contend(candidate):
                locator = authorize(candidate)
                holder.start()
                assert root_held.wait(5)
                monkeypatch.setattr(root, "_parent_state_transition_lease", observed_transition)
                mutator.start()
                return locator

            monkeypatch.setattr(fence, "authorize_release", authorize_then_contend)
            with pytest.raises(ChildParentSettlementError):
                custody.release_parent((), blob)
            holder.join(timeout=5)
            mutator.join(timeout=5)
            assert not holder.is_alive() and not mutator.is_alive()
            assert not failures and guard_changed.is_set()
            fresh = FileSystemCAS(raw.root, ownership_enforced=False)
            with pytest.raises((FileNotFoundError, ChildReleaseUnavailableError)):
                fresh.get_bytes(blob)
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
