from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.audit import AuditPackageAssembler
from polisyos.core.audit.assembler import AuditAssemblyError


def _write_manifest(runs_dir: Path, run_id: str, payload: dict[str, object]) -> None:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")


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
