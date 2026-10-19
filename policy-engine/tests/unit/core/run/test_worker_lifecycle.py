"""Core-owned worker dispatch and lifecycle boundary tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext, _FinalizeRecoveryError
from polisyos.core.run.worker_lifecycle import (
    WorkerDispatchBinding,
    WorkerLifecycleCapability,
    WorkerRunView,
)
from polisyos.core.trace.record import TraceRecord


class _MemoryTrace:
    """Collect typed trace records without touching the parent's durable sink."""

    def __init__(self) -> None:
        self.records: list[TraceRecord] = []

    def emit(self, record: TraceRecord) -> None:
        self.records.append(record.model_copy(deep=True))

    def emit_many(self, records: list[TraceRecord]) -> None:
        self.records.extend(record.model_copy(deep=True) for record in records)


def test_worker_view_stages_then_parent_capability_merges_once(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    run_id = "R_core_worker_lifecycle"
    run_dir = store.root / "runs" / run_id
    parent_run = RunContext.start(
        store=store,
        registry_bundle=registry.bundle_ref,
        run_id=run_id,
        run_dir=run_dir,
    )
    parent_capability = WorkerLifecycleCapability.for_parent(parent_run)
    parent_snapshot = parent_capability.snapshot()
    invocation_id = "a" * 64
    dispatch_sha256 = "b" * 64
    parent_binding = parent_capability.bind_dispatch(
        invocation_id=invocation_id,
        dispatch_sha256=dispatch_sha256,
    )
    staged = _MemoryTrace()
    with pytest.raises(_FinalizeRecoveryError, match="worker_trace_parent_process_refused"):
        parent_capability.worker_view(trace=staged, binding=parent_binding)
    worker_capability = WorkerLifecycleCapability.for_worker_context(
        store=store,
        trace=staged,
        run_manifest=parent_snapshot.run_manifest,
        trace_path=parent_snapshot.trace_path,
        owner_snapshot_ref=parent_snapshot.owner_snapshot_ref,
        access_scope=parent_snapshot.access_scope,
        tenant_id=parent_snapshot.tenant_id,
        cell_id=parent_snapshot.cell_id,
        invocation_id=invocation_id,
        dispatch_sha256=dispatch_sha256,
    )
    worker_binding = worker_capability.binding
    assert worker_binding == parent_binding
    mutable_owner_ref = worker_binding.owner_snapshot_ref
    mutable_owner_ref.kind = "tampered.worker.owner"
    assert worker_binding.owner_snapshot_ref == parent_binding.owner_snapshot_ref
    worker_view = worker_capability.worker_view()
    assert isinstance(worker_view, WorkerRunView)

    output_ref = store.put_json(
        {"worker": "candidate"},
        PutOptions(
            kind="core.worker_candidate",
            media_type="application/json",
            schema=SchemaInfo(name="core.WorkerCandidate", version="1.0"),
        ),
        return_selected_profile=True,
    )
    trace_before = (run_dir / "trace.jsonl").read_bytes()
    worker_view.emit(
        "worker",
        "NODE_OUTPUT_CANDIDATE",
        outputs=[output_ref],
    )
    assert (run_dir / "trace.jsonl").read_bytes() == trace_before
    assert len(staged.records) == 1
    assert staged.records[0].refs.outputs == [output_ref]

    blob_path, _default_manifest_path = store._paths(output_ref.artifact_id)
    original_blob = blob_path.read_bytes()
    blob_path.write_bytes(b"corrupted candidate bytes")
    with pytest.raises(_FinalizeRecoveryError, match="worker_merge_artifact_verification_failed"):
        parent_capability.admit_worker_events(parent_binding, staged.records)
    assert (run_dir / "trace.jsonl").read_bytes() == trace_before
    blob_path.write_bytes(original_blob)

    parent_capability.admit_worker_events(parent_binding, staged.records)
    records = [
        TraceRecord.model_validate_json(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [record.event for record in records[-3:]] == [
        "WORKER_INVOCATION_STARTED",
        "NODE_OUTPUT_CANDIDATE",
        "WORKER_INVOCATION_COMPLETED",
    ]
    assert all(record.worker_invocation_id == invocation_id for record in records[-3:])
    assert store.verify(output_ref).ok
    with pytest.raises(ValueError, match="worker_lifecycle_dispatch_binding_unissued"):
        parent_capability.admit_worker_events(parent_binding, staged.records)

    stale_binding = parent_capability.bind_dispatch(
        invocation_id="c" * 64,
        dispatch_sha256="d" * 64,
    )
    parent_run.update_manifest(execution_profile="owner-advanced")
    with pytest.raises(_FinalizeRecoveryError, match="worker_merge_owner_snapshot_stale"):
        parent_capability.admit_worker_events(stale_binding, [])
    parent_run.finalize(status="ok")


def test_worker_view_refuses_lifecycle_aliases_and_detaches_mutable_manifest(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    run_id = "R_core_worker_lifecycle_refusal"
    run_dir = store.root / "runs" / run_id
    parent_run = RunContext.start(
        store=store,
        registry_bundle=registry.bundle_ref,
        run_id=run_id,
        run_dir=run_dir,
    )
    parent_capability = WorkerLifecycleCapability.for_parent(parent_run)
    snapshot = parent_capability.snapshot()
    staged = _MemoryTrace()
    worker_capability = WorkerLifecycleCapability.for_worker_context(
        store=store,
        trace=staged,
        run_manifest=snapshot.run_manifest,
        trace_path=snapshot.trace_path,
        owner_snapshot_ref=snapshot.owner_snapshot_ref,
        access_scope=snapshot.access_scope,
        tenant_id=snapshot.tenant_id,
        cell_id=snapshot.cell_id,
    )
    view = worker_capability.worker_view()

    for operation in (view.finalize, view.suspend_for_resume):
        with pytest.raises(_FinalizeRecoveryError, match="timeout_worker_run_lifecycle_not_owned"):
            operation()
    for operation in (RunContext.finalize, RunContext.suspend_for_resume):
        with pytest.raises(_FinalizeRecoveryError, match="timeout_worker_run_lifecycle_not_owned"):
            operation(view)
    with pytest.raises(_FinalizeRecoveryError, match="timeout_worker_run_lifecycle_not_owned"):
        RunContext.merge_worker_events(
            view,
            invocation_id="e" * 64,
            dispatch_sha256="f" * 64,
            owner_snapshot_ref=snapshot.owner_snapshot_ref,
            records=[],
        )

    for field in (
        "_target",
        "_active_lease",
        "_owner_snapshot_ref",
        "_closed",
        "_suspended",
        "_trace_path",
        "_audit_sink",
    ):
        with pytest.raises(AttributeError):
            getattr(view, field)
    for field, value in (
        ("_active_lease", object()),
        ("_owner_snapshot_ref", snapshot.owner_snapshot_ref),
        ("_closed", True),
        ("_suspended", True),
        ("trace_path", Path("/outside/parent")),
        ("run_manifest", snapshot.run_manifest),
    ):
        with pytest.raises(AttributeError):
            setattr(view, field, value)
    assert view.trace_path == snapshot.trace_path
    with pytest.raises(ValueError, match="worker_lifecycle_core_run_required"):
        WorkerLifecycleCapability.for_parent(view)

    view_manifest = view.run_manifest
    view_manifest.execution_profile = "worker-local-edit"
    assert view_manifest.execution_profile == "worker-local-edit"
    assert worker_capability.snapshot().run_manifest.execution_profile is None
    assert parent_capability.snapshot().run_manifest.execution_profile is None
    assert parent_capability.snapshot().owner_snapshot_ref == snapshot.owner_snapshot_ref
    parent_run.suspend_for_resume()


def test_parent_and_worker_snapshots_detach_nested_mutable_projections(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    parent_run = RunContext.start(
        store=store,
        registry_bundle=registry.bundle_ref,
        run_id="R_core_worker_snapshot_projection",
        run_dir=store.root / "runs" / "R_core_worker_snapshot_projection",
    )
    manifest_output_ref = store.put_json(
        {"snapshot": "projection"},
        PutOptions(
            kind="core.worker_snapshot_fixture",
            media_type="application/json",
            schema=SchemaInfo(name="core.WorkerSnapshotFixture", version="1.0"),
        ),
        return_selected_profile=True,
    )
    parent_run.run_manifest.outputs.append(manifest_output_ref)
    parent_capability = WorkerLifecycleCapability.for_parent(parent_run)
    live_parent_owner_ref = parent_run._owner_snapshot_ref
    assert live_parent_owner_ref is not None
    expected_owner_ref = live_parent_owner_ref.model_copy(deep=True)
    expected_parent_manifest = parent_run.run_manifest.model_copy(deep=True)

    parent_snapshot = parent_capability.snapshot()
    assert parent_snapshot.owner_snapshot_ref is not live_parent_owner_ref
    assert parent_snapshot.owner_snapshot_ref.artifact_id is not live_parent_owner_ref.artifact_id
    assert parent_snapshot.run_manifest is not parent_run.run_manifest
    assert parent_snapshot.run_manifest.outputs is not parent_run.run_manifest.outputs
    assert parent_snapshot.run_manifest.outputs[0] is not parent_run.run_manifest.outputs[0]
    assert (
        parent_snapshot.run_manifest.outputs[0].artifact_id
        is not parent_run.run_manifest.outputs[0].artifact_id
    )

    parent_snapshot.owner_snapshot_ref.kind = "tampered.parent.snapshot"
    parent_snapshot.owner_snapshot_ref.artifact_id.root = "sha256:" + "0" * 64
    parent_snapshot.run_manifest.outputs[0].kind = "tampered.parent.manifest"
    parent_snapshot.run_manifest.outputs[0].artifact_id.root = "sha256:" + "1" * 64
    assert live_parent_owner_ref == expected_owner_ref
    assert parent_run.run_manifest == expected_parent_manifest
    fresh_parent_snapshot = parent_capability.snapshot()
    assert fresh_parent_snapshot.owner_snapshot_ref == expected_owner_ref
    assert fresh_parent_snapshot.run_manifest == expected_parent_manifest

    worker_owner_ref = fresh_parent_snapshot.owner_snapshot_ref
    worker_manifest = fresh_parent_snapshot.run_manifest
    assert fresh_parent_snapshot.trace_path is not None
    worker_capability = WorkerLifecycleCapability.for_worker_context(
        store=store,
        trace=_MemoryTrace(),
        run_manifest=worker_manifest,
        trace_path=fresh_parent_snapshot.trace_path,
        owner_snapshot_ref=worker_owner_ref,
        access_scope=fresh_parent_snapshot.access_scope,
        tenant_id=fresh_parent_snapshot.tenant_id,
        cell_id=fresh_parent_snapshot.cell_id,
    )
    expected_worker_owner_ref = worker_owner_ref.model_copy(deep=True)
    expected_worker_manifest = worker_manifest.model_copy(deep=True)
    worker_snapshot = worker_capability.snapshot()
    assert worker_snapshot.owner_snapshot_ref is not worker_owner_ref
    assert worker_snapshot.owner_snapshot_ref.artifact_id is not worker_owner_ref.artifact_id
    assert worker_snapshot.run_manifest is not worker_manifest
    assert worker_snapshot.run_manifest.outputs is not worker_manifest.outputs
    assert worker_snapshot.run_manifest.outputs[0] is not worker_manifest.outputs[0]
    assert (
        worker_snapshot.run_manifest.outputs[0].artifact_id
        is not worker_manifest.outputs[0].artifact_id
    )

    worker_snapshot.owner_snapshot_ref.kind = "tampered.worker.snapshot"
    worker_snapshot.owner_snapshot_ref.artifact_id.root = "sha256:" + "2" * 64
    worker_snapshot.run_manifest.outputs[0].kind = "tampered.worker.manifest"
    worker_snapshot.run_manifest.outputs[0].artifact_id.root = "sha256:" + "3" * 64
    assert worker_owner_ref == expected_worker_owner_ref
    assert worker_manifest == expected_worker_manifest
    fresh_worker_snapshot = worker_capability.snapshot()
    assert fresh_worker_snapshot.owner_snapshot_ref == expected_worker_owner_ref
    assert fresh_worker_snapshot.run_manifest == expected_worker_manifest
    assert parent_run._owner_snapshot_ref == expected_owner_ref
    assert parent_run.run_manifest == expected_parent_manifest
    parent_run.suspend_for_resume()


def test_worker_capability_rejects_fake_or_incomplete_dispatch_bindings(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    run = RunContext.start(store=store, registry_bundle=registry.bundle_ref)
    capability = WorkerLifecycleCapability.for_parent(run)
    with pytest.raises(ValueError, match="worker_lifecycle_invocation_id_invalid"):
        capability.bind_dispatch(invocation_id="not-a-digest", dispatch_sha256="1" * 64)
    issued = capability.bind_dispatch(
        invocation_id="1" * 64,
        dispatch_sha256="2" * 64,
    )
    forged = WorkerDispatchBinding(
        run_id=issued.run_id,
        invocation_id="3" * 64,
        dispatch_sha256=issued.dispatch_sha256,
        owner_snapshot_ref=issued.owner_snapshot_ref,
    )
    with pytest.raises(ValueError, match="worker_lifecycle_dispatch_binding_unissued"):
        capability.admit_worker_events(forged, [])
    run.suspend_for_resume()
