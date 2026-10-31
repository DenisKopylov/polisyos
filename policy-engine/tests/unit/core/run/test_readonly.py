"""Real terminal Core reads never reconstruct a writer or trust a detached manifest."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.core.run.readonly import (
    TerminalCoreRunSource,
    TerminalRunSourceError,
    open_terminal_run_source,
)
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.tenant_context import tenant_scope


def _real_terminal(
    tmp_path: Path, *, workflow_finalization: bool = True
) -> tuple[FileSystemCAS, RunContext, ArtifactRef, ArtifactRef | None]:
    store = FileSystemCAS(tmp_path / "cas")
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    run = RunContext.start(
        store=store,
        registry_bundle=registry.bundle_ref,
        run_id="R_terminal_reader",
        run_dir=store.root / "runs" / "R_terminal_reader",
    )
    finalization = None
    if workflow_finalization:
        # Core owns only the exact selected output, not this domain payload's meaning.
        finalization = store.put_json(
            {"source": "actual-core-owner", "domain_fact": "opaque-to-core"},
            PutOptions(
                kind="test.workflow_finalization",
                media_type="application/json",
                schema=SchemaInfo(name="test.WorkflowFinalization", version="1.0"),
            ),
            return_selected_profile=True,
        )
        run.add_output(finalization)
    ref = run.finalize(status="ok", workflow_finalization_ref=finalization)
    return store, run, ref, finalization


def _open(
    store: FileSystemCAS, run: RunContext, ref: ArtifactRef, **scope: str | None
) -> TerminalCoreRunSource:
    expected: dict[str, str | None] = {
        "expected_run_id": run.run_manifest.run_id,
        "expected_tenant_id": None,
        "expected_cell_id": None,
        "expected_control_job_id": None,
    }
    expected.update(scope)
    assert run.trace_path is not None
    return open_terminal_run_source(store, run_ref=ref, trace_path=run.trace_path, **expected)


def test_terminal_source_replays_actual_owner_without_writer_or_mutation(tmp_path: Path) -> None:
    store, run, ref, finalization = _real_terminal(tmp_path)
    assert finalization is not None
    before_paths = {path.relative_to(store.root) for path in store.root.rglob("*")}
    assert run.trace_path is not None
    before_trace = run.trace_path.read_bytes()
    source = _open(store, run, ref)
    assert source.run_manifest.status == "ok"
    assert source.run_ref == ref
    assert source.trace_path == run.trace_path
    assert source.read_runtime_owner_output_refs() == (finalization,)
    assert source.read_runtime_workflow_finalization_ref() == finalization
    assert source.read_runtime_invocation_attempts() == []
    for name in ("resume", "start", "finalize", "emit", "add_output", "update_manifest"):
        assert not hasattr(source, name)
    detached = source.run_manifest
    detached.status = "running"
    detached.outputs.clear()
    selected = source.run_ref
    selected.kind = "fake.run"
    output = source.read_runtime_owner_output_refs()[0]
    output.kind = "fake.output"
    assert source.run_manifest.status == "ok"
    assert source.run_ref == ref
    assert source.read_runtime_owner_output_refs() == (finalization,)
    assert run.trace_path.read_bytes() == before_trace
    assert {path.relative_to(store.root) for path in store.root.rglob("*")} == before_paths


@pytest.mark.parametrize(
    "scope",
    [
        {"expected_run_id": "foreign-run"},
        {"expected_tenant_id": "foreign-tenant"},
        {"expected_cell_id": "foreign-cell"},
        {"expected_control_job_id": "foreign-job"},
    ],
)
def test_terminal_source_refuses_different_current_scope(
    tmp_path: Path, scope: dict[str, str]
) -> None:
    store, run, ref, _ = _real_terminal(tmp_path)
    with pytest.raises(TerminalRunSourceError, match="scope_mismatch"):
        _open(store, run, ref, **scope)


def test_terminal_source_requires_selected_profile_and_actual_terminal_event(
    tmp_path: Path,
) -> None:
    store, run, ref, _ = _real_terminal(tmp_path)
    with pytest.raises(TerminalRunSourceError, match="selected_profile_missing"):
        _open(store, run, ref.model_copy(update={"manifest_profile_sha256": None}))
    assert run.trace_path is not None
    trace_bytes = run.trace_path.read_bytes()
    before_terminal = trace_bytes.rsplit(b"\n", 2)[0] + b"\n"
    run.trace_path.write_bytes(before_terminal)
    with pytest.raises(TerminalRunSourceError, match="terminal_fact_mismatch"):
        _open(store, run, ref)
    run.trace_path.write_bytes(trace_bytes)
    assert _open(store, run, ref).run_manifest.status == "ok"


def test_terminal_source_absent_expected_scope_is_not_a_wildcard(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    scope = AccessScope.for_service(
        tenant_id="tenant-terminal", cell_id="cell-terminal", spiffe_id="spiffe://test/reader"
    )
    scoped_store = store.for_tenant(scope.tenant_id, scope.cell_id)
    run_dir = store.root / "runs" / "R_tenant_terminal"
    with tenant_scope(None, tenant_id=scope.tenant_id, cell_id=scope.cell_id):
        registry = build_default_registry_bundle(scoped_store, return_selected_profile=True)
        run = RunContext.start(
            scoped_store,
            registry.bundle_ref,
            run_dir=run_dir,
            run_id="R_tenant_terminal",
            tenant_id=scope.tenant_id,
            cell_id=scope.cell_id,
            access_scope=scope,
            control_job_id="actual-job",
        )
        ref = run.finalize(status="ok")
        expected = {
            "expected_run_id": "R_tenant_terminal",
            "expected_tenant_id": scope.tenant_id,
            "expected_cell_id": scope.cell_id,
            "expected_control_job_id": "actual-job",
        }
        source = open_terminal_run_source(
            scoped_store, run_ref=ref, trace_path=run_dir / "trace.jsonl", **expected
        )
        assert source.run_manifest.control_job_id == "actual-job"
        for field in ("expected_tenant_id", "expected_cell_id", "expected_control_job_id"):
            with pytest.raises(TerminalRunSourceError, match="scope_mismatch"):
                open_terminal_run_source(
                    scoped_store,
                    run_ref=ref,
                    trace_path=run_dir / "trace.jsonl",
                    **{**expected, field: None},
                )


def test_terminal_source_reconciles_manifest_trace_against_actual_prefix(tmp_path: Path) -> None:
    store, run, ref, _ = _real_terminal(tmp_path)
    assert run.trace_path is not None
    lines = run.trace_path.read_bytes().splitlines(keepends=True)
    inserted = json.loads(lines[-1])
    inserted.update(phase="scientist", event="UNRECORDED_AFTER_CAPTURE", run_terminality=None)
    inserted["refs"] = {"inputs": [], "outputs": []}
    run.trace_path.write_bytes(
        b"".join(lines[:-1]) + json.dumps(inserted).encode() + b"\n" + lines[-1]
    )
    with pytest.raises(TerminalRunSourceError, match="trace_prefix_mismatch"):
        _open(store, run, ref)


def test_terminal_source_rejects_profileless_terminal_input_from_real_owner_output(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    run = RunContext.start(store, registry.bundle_ref, run_id="R_terminal_reader")
    unprofiled = store.put_json(
        {"ordinary": "output"},
        PutOptions(kind="test.ordinary", media_type="application/json"),
    )
    assert unprofiled.manifest_profile_sha256 is None
    selected = store.put_json(
        {"finalization": "selected"},
        PutOptions(kind="test.workflow_finalization", media_type="application/json"),
        return_selected_profile=True,
    )
    run.add_output(unprofiled)
    run.add_output(selected)
    ref = run.finalize(status="ok", workflow_finalization_ref=selected)
    assert run.trace_path is not None
    lines = run.trace_path.read_bytes().splitlines(keepends=True)
    terminal = json.loads(lines[-1])
    terminal["refs"]["inputs"] = [unprofiled.model_dump(mode="json")]
    run.trace_path.write_bytes(b"".join(lines[:-1]) + json.dumps(terminal).encode() + b"\n")
    with pytest.raises(TerminalRunSourceError, match="workflow_finalization_contract_invalid"):
        _open(store, run, ref)


def test_terminal_source_refuses_trace_suffix_and_changed_historical_cas(tmp_path: Path) -> None:
    store, run, ref, _ = _real_terminal(tmp_path)
    source = _open(store, run, ref)
    assert run.trace_path is not None
    trace_bytes = run.trace_path.read_bytes()
    terminal_line = trace_bytes.splitlines()[-1]
    run.trace_path.write_bytes(trace_bytes + terminal_line + b"\n")
    with pytest.raises(TerminalRunSourceError, match="terminal_fact_mismatch"):
        source.read_runtime_owner_output_refs()
    run.trace_path.write_bytes(trace_bytes)
    trace_ref = source.run_manifest.trace_ref
    assert trace_ref is not None
    blob_path, _ = store._paths(trace_ref.artifact_id)
    blob_bytes = blob_path.read_bytes()
    blob_path.write_bytes(b"{}\n")
    with pytest.raises(TerminalRunSourceError, match="trace_artifact_not_established"):
        source.read_runtime_owner_output_refs()
    blob_path.write_bytes(blob_bytes)
    assert source.read_runtime_owner_output_refs() == tuple(run.run_manifest.outputs)


def test_terminal_source_does_not_follow_replaced_trace_symlink(tmp_path: Path) -> None:
    store, run, ref, _ = _real_terminal(tmp_path)
    source = _open(store, run, ref)
    assert run.trace_path is not None
    retained = tmp_path / "retained-trace.jsonl"
    run.trace_path.rename(retained)
    run.trace_path.symlink_to(retained)
    with pytest.raises(TerminalRunSourceError, match="not_established"):
        source.read_runtime_invocation_attempts()


def test_terminal_source_legacy_completion_does_not_invent_workflow_transition(
    tmp_path: Path,
) -> None:
    store, run, ref, _ = _real_terminal(tmp_path, workflow_finalization=False)
    source = _open(store, run, ref)
    assert source.run_manifest.status == "ok"
    with pytest.raises(TerminalRunSourceError, match="workflow_finalization_absent"):
        source.read_runtime_workflow_finalization_ref()


def test_terminal_source_new_process_reads_same_facts_without_writer(tmp_path: Path) -> None:
    store, run, ref, finalization = _real_terminal(tmp_path)
    assert finalization is not None
    assert run.trace_path is not None
    script = """
import json
import sys
from pathlib import Path
from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.run.readonly import open_terminal_run_source
source = open_terminal_run_source(
    FileSystemCAS(Path(sys.argv[1])),
    run_ref=ArtifactRef.model_validate_json(sys.argv[2]),
    trace_path=Path(sys.argv[3]), expected_run_id='R_terminal_reader',
    expected_tenant_id=None, expected_cell_id=None, expected_control_job_id=None,
)
assert not hasattr(source, 'finalize')
print(json.dumps({
    'status': source.run_manifest.status,
    'finalization': source.read_runtime_workflow_finalization_ref().model_dump(mode='json'),
    'attempt_count': len(source.read_runtime_invocation_attempts()),
}))
"""
    before_trace = run.trace_path.read_bytes()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[4] / "src")
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            script,
            str(store.root),
            ref.model_dump_json(),
            str(run.trace_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    actual = json.loads(result.stdout)
    assert actual == {
        "status": "ok",
        "finalization": finalization.model_dump(mode="json"),
        "attempt_count": 0,
    }
    assert run.trace_path.read_bytes() == before_trace
