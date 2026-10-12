from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts.manifest import ProducerInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.audit import AuditPackageAssembler
from polisyos.core.audit.assembler import AuditAssemblyError
from polisyos.core.run import context as run_context
from polisyos.core.run.context import RunContext
from polisyos.core.trace import RunTerminality, TraceRecord

if TYPE_CHECKING:
    from pathlib import Path


def _write_manifest(runs_dir: Path, run_id: str, payload: dict[str, object]) -> None:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")


def _bootstrap_registry_bundle(store: FileSystemCAS):
    slot_ref = store.put_json(
        {"slots": {}},
        PutOptions(kind="core.registry.slots", media_type="application/json"),
    )
    merge_ref = store.put_json(
        {"merge_rules": {}},
        PutOptions(kind="core.registry.merge", media_type="application/json"),
    )
    constraints_ref = store.put_json(
        {"constraints": {}},
        PutOptions(kind="core.registry.constraints", media_type="application/json"),
    )
    mechanisms_ref = store.put_json(
        {"mechanisms": {}},
        PutOptions(kind="core.registry.mechanisms", media_type="application/json"),
    )
    trust_ref = store.put_json(
        {"trust_policies": {}},
        PutOptions(kind="core.registry.trust", media_type="application/json"),
    )
    return store.put_json(
        {
            "slot_registry": slot_ref.model_dump(),
            "merge_registry": merge_ref.model_dump(),
            "constraint_registry": constraints_ref.model_dump(),
            "mechanism_registry": mechanisms_ref.model_dump(),
            "trust_registry": trust_ref.model_dump(),
        },
        PutOptions(kind="core.registry.bundle", media_type="application/json"),
    )


def test_audit_assembler_rejects_legacy_runtime_manifest_shape(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    runs_dir = tmp_path / "runs"
    _write_manifest(
        runs_dir,
        "R_legacy",
        {
            "schema_version": "1.0",
            "run_id": "R_legacy",
            "status": "completed",
            "started_at": "2026-02-09T20:00:00Z",
            "finished_at": "2026-02-09T20:01:00Z",
            "generator": {"component": "runtime.api"},
            "budgets": {},
            "budget_usage": {},
            "artifacts": [],
        },
    )

    assembler = AuditPackageAssembler(cas=store, runs_dir=runs_dir)
    with pytest.raises(AuditAssemblyError, match="Unsupported run manifest format"):
        assembler.export("R_legacy")


def test_audit_assembler_reports_unsupported_for_non_legacy_invalid_manifest(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    runs_dir = tmp_path / "runs"
    _write_manifest(runs_dir, "R_invalid", {"bad": "shape"})

    assembler = AuditPackageAssembler(cas=store, runs_dir=runs_dir)
    with pytest.raises(AuditAssemblyError, match="Unsupported run manifest format"):
        assembler.export("R_invalid")


def test_audit_assembler_recovers_pending_finalize_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    runs_dir = tmp_path / "runs"
    bundle_ref = _bootstrap_registry_bundle(store)
    run_dir = runs_dir / "R_recover_for_audit"

    ctx = RunContext.start(
        store=store,
        registry_bundle=bundle_ref,
        run_dir=run_dir,
    )
    ctx.add_output(
        store.put_json(
            {"decision": "approve"},
            PutOptions(kind="scientist.decision_packet", media_type="application/json"),
        )
    )

    original_put_json = store.put_json
    should_fail = True

    def _failing_put_json(obj, opts=None, canon_spec=None, *, return_selected_profile=False):
        nonlocal should_fail
        if should_fail and getattr(opts, "kind", None) == "core.run_manifest":
            should_fail = False
            raise OSError("simulated finalize crash")
        return original_put_json(
            obj,
            opts,
            canon_spec=canon_spec,
            return_selected_profile=return_selected_profile,
        )

    monkeypatch.setattr(store, "put_json", _failing_put_json)
    with pytest.raises(OSError, match="simulated finalize crash"):
        ctx.finalize(status="ok")

    monkeypatch.setattr(store, "put_json", original_put_json)
    journal_path = run_dir / ".finalize-journal.json"
    assert journal_path.exists()

    assembler = AuditPackageAssembler(cas=store, runs_dir=runs_dir)
    result = assembler.export(
        "R_recover_for_audit",
        tmp_path / "audit_recovered_manifest",
    )

    assert result.run_id == "R_recover_for_audit"
    assert result.archive_path.exists()
    finalized = [
        json.loads(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    terminal = next(record for record in finalized if record["event"] == "RUN_FINALIZED")
    manifest_refs = [
        ref for ref in terminal["refs"]["outputs"] if ref["kind"] == "core.run_manifest"
    ]
    assert len(manifest_refs) == 1
    recovered_ref = manifest_refs[0]
    assert recovered_ref["manifest_profile_sha256"].startswith("sha256:")
    recovered_manifest = store.get_manifest_by_profile(
        recovered_ref["artifact_id"], recovered_ref["manifest_profile_sha256"]
    )
    assert recovered_manifest.kind == "core.run_manifest"
    assert journal_path.exists() is False



def test_audit_recovery_preserves_legacy_profileless_terminal_ref(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    runs_dir = tmp_path / "runs"
    bundle_ref = _bootstrap_registry_bundle(store)
    run_dir = runs_dir / "R_legacy_terminal_for_audit"
    ctx = RunContext.start(store=store, registry_bundle=bundle_ref, run_dir=run_dir)
    ctx.add_output(
        store.put_json(
            {"decision": "approve"},
            PutOptions(kind="scientist.decision_packet", media_type="application/json"),
        )
    )
    ctx.run_manifest.status = "ok"
    ctx.run_manifest.finished_at = datetime.now(UTC).replace(microsecond=0)
    trace_ref = store.put_bytes(
        ctx.trace_path.read_bytes(),
        PutOptions(kind="core.trace.jsonl", media_type="application/jsonl"),
    )
    ctx._record_ref_owner(trace_ref, writer="RunContext.finalize.trace")
    ctx.run_manifest.trace_ref = trace_ref
    run_context._write_finalize_journal(run_dir, ctx.run_manifest)
    legacy_ref = store.put_json(
        ctx.run_manifest,
        run_context._run_manifest_write_options(ctx.run_manifest),
    )
    assert legacy_ref.manifest_profile_sha256 is None
    ctx._record_ref_owner(legacy_ref, writer="RunContext.finalize.manifest")
    ctx._emit_record(
        "core",
        "RUN_FINALIZED",
        run_terminality=RunTerminality.TERMINAL,
        outputs=[legacy_ref],
        metrics={"status_ok": 1},
    )

    assembler = AuditPackageAssembler(cas=store, runs_dir=runs_dir)
    result = assembler.export(
        "R_legacy_terminal_for_audit",
        tmp_path / "audit_legacy_terminal",
    )

    assert result.run_id == "R_legacy_terminal_for_audit"
    assert result.archive_path.exists()
    assert (run_dir / ".finalize-journal.json").exists() is False
    records = [
        TraceRecord.model_validate_json(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    terminal_records = [
        record
        for record in records
        if record.phase == "core" and record.event == "RUN_FINALIZED"
    ]
    assert len(terminal_records) == 1
    persisted_ref = next(
        ref for ref in terminal_records[0].refs.outputs if ref.kind == "core.run_manifest"
    )
    assert persisted_ref == legacy_ref
    assert persisted_ref.manifest_profile_sha256 is None

def test_audit_rejects_unjournaled_terminal_ref_with_foreign_manifest_profile(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    runs_dir = tmp_path / "runs"
    bundle_ref = _bootstrap_registry_bundle(store)
    run_dir = runs_dir / "R_foreign_profile_for_audit"
    ctx = RunContext.start(store=store, registry_bundle=bundle_ref, run_dir=run_dir)
    ctx.add_output(
        store.put_json(
            {"decision": "approve"},
            PutOptions(kind="scientist.decision_packet", media_type="application/json"),
        )
    )
    selected_ref = ctx.finalize(status="ok")
    selected_manifest = store.get_manifest(selected_ref)
    foreign_ref = store.put_bytes(
        store.get_bytes(selected_ref),
        PutOptions(
            kind=selected_manifest.kind,
            media_type=selected_manifest.media_type,
            schema=selected_manifest.artifact_schema,
            producer=ProducerInfo(component="tests.foreign-run-manifest", version="0"),
            env=selected_manifest.env,
            inputs=selected_manifest.inputs,
        ),
        return_selected_profile=True,
    )
    assert foreign_ref.artifact_id == selected_ref.artifact_id
    assert foreign_ref.manifest_profile_sha256 != selected_ref.manifest_profile_sha256

    trace_path = run_dir / "trace.jsonl"
    records = [
        TraceRecord.model_validate_json(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    terminal = next(record for record in records if record.event == "RUN_FINALIZED")
    terminal.refs.outputs = [
        foreign_ref if ref.kind == "core.run_manifest" else ref
        for ref in terminal.refs.outputs
    ]
    trace_path.write_text(
        "\n".join(record.model_dump_json(exclude_none=True) for record in records) + "\n",
        encoding="utf-8",
    )
    forged_trace = trace_path.read_bytes()
    assembler = AuditPackageAssembler(cas=store, runs_dir=runs_dir)

    with pytest.raises(AuditAssemblyError, match="manifest profile is not established"):
        assembler.export("R_foreign_profile_for_audit")

    assert trace_path.read_bytes() == forged_trace
    assert (run_dir / ".finalize-journal.json").exists() is False
