from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.audit import AuditPackageAssembler
from polisyos.core.audit.assembler import AuditAssemblyError
from polisyos.core.run.context import RunContext

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

    def _failing_put_json(obj, opts=None, canon_spec=None):
        nonlocal should_fail
        if should_fail and getattr(opts, "kind", None) == "core.run_manifest":
            should_fail = False
            raise OSError("simulated finalize crash")
        return original_put_json(obj, opts, canon_spec=canon_spec)

    monkeypatch.setattr(store, "put_json", _failing_put_json)
    with pytest.raises(OSError, match="simulated finalize crash"):
        ctx.finalize(status="ok")

    monkeypatch.setattr(store, "put_json", original_put_json)
    journal_path = run_dir / ".finalize-journal.json"
    assert journal_path.exists()

    assembler = AuditPackageAssembler(cas=store, runs_dir=runs_dir)
    result = assembler.export("R_recover_for_audit")

    assert result.run_id == "R_recover_for_audit"
    assert result.archive_path.exists()
    assert journal_path.exists() is False
