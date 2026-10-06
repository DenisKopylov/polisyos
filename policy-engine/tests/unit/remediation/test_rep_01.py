"""Ownership witnesses and compatibility controls for the REP-01 relocation."""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"
DYNAMIC_IMPORTS = PROJECT_ROOT / "architecture" / "imports" / "dynamic.toml"

ROOT_EXPORTS = (
    "CompletenessLevel",
    "CompletenessReport",
    "ReplayPlan",
    "ReplayStrategy",
    "VerificationConfig",
    "VerificationMode",
    "VerificationResult",
    "build_replay_plan",
    "completeness_check",
    "verify_replay",
)

COMPATIBILITY_EXPORTS = (
    "CompletenessLevel",
    "CompletenessReport",
    "MissingArtifact",
    "ReplayBundleMeasurement",
    "ReplayPlan",
    "ReplayStrategy",
    "SeedResolution",
    "VerificationConfig",
    "VerificationMode",
    "VerificationResult",
    "build_replay_plan",
    "compare_current_environment",
    "completeness_check",
    "determine_replay_strategy",
    "measure_replayable_audit_bundle",
    "normalize_artifact_id",
    "resolve_effective_seed",
    "set_global_seeds",
    "try_parse_artifact_id",
    "verify_replay",
)


def _isolated_environment() -> dict[str, str]:
    """Return an import environment that resolves this checkout, not an editable sibling."""
    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH")
    paths = [str(SRC_ROOT), str(PROJECT_ROOT)]
    if existing:
        paths.append(existing)
    environment["PYTHONPATH"] = os.pathsep.join(paths)
    return environment


def _run_isolated(code: str) -> subprocess.CompletedProcess[str]:
    """Run one import-boundary probe in a fresh interpreter."""
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=_isolated_environment(),
        capture_output=True,
        text=True,
        check=False,
    )


def test_runtime_root_replay_exports_bind_directly_and_stay_lazy() -> None:
    """The ten-symbol Runtime facade must resolve Scientist without loading the shim."""
    result = _run_isolated(
        f"""
import importlib
import sys

runtime = importlib.import_module('polisyos.runtime')
expected = {ROOT_EXPORTS!r}
assert tuple(runtime.__all__) == expected
assert 'polisyos.scientist.replay.deterministic' not in sys.modules
assert 'polisyos.runtime.replay' not in sys.modules
canonical = importlib.import_module('polisyos.scientist.replay.deterministic')
for name in expected:
    assert getattr(runtime, name) is getattr(canonical, name), name
assert 'polisyos.runtime.replay' not in sys.modules
""",
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"


def test_runtime_replay_compatibility_window_keeps_all_twenty_symbols() -> None:
    """The transitional module keeps its twenty-symbol ABI while callers move away."""
    canonical = importlib.import_module("polisyos.scientist.replay.deterministic")
    compatibility = importlib.import_module("polisyos.runtime.replay")

    assert tuple(compatibility.__all__) == COMPATIBILITY_EXPORTS
    for name in COMPATIBILITY_EXPORTS:
        assert getattr(compatibility, name) is getattr(canonical, name), name


def test_runtime_unknown_replay_symbol_fails_closed() -> None:
    """An unknown root name must not be made importable by the relocation."""
    runtime = importlib.import_module("polisyos.runtime")

    with pytest.raises(AttributeError, match="no attribute"):
        assert runtime.REP_01_UNKNOWN_REPLAY_SYMBOL


def test_core_replay_cli_keeps_delayed_import_on_direct_scientist_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Core CLI keeps lazy loading but changes only its replay owner string."""
    from polisyos.core.components import _cli_replay

    imported: list[str] = []
    real_import_module = _cli_replay.importlib.import_module

    def _recording_import(module_name: str, package: str | None = None):
        imported.append(module_name)
        return real_import_module(module_name, package)

    monkeypatch.setattr(_cli_replay.importlib, "import_module", _recording_import)
    args = SimpleNamespace(
        packet_ref="sha256:" + "a" * 64,
        bundle=None,
        cas_root=tmp_path / "cas",
        check_only=True,
        export=None,
        json=True,
    )

    exit_code = _cli_replay._cmd_replay(args)

    assert exit_code == 1
    assert imported[0] == "polisyos.scientist.replay.deterministic"
    payload = json.loads(capsys.readouterr().out)
    assert payload["level"] == "incomplete"
    assert "packet_unreadable" in payload["reason_codes"]


def test_advanced_benchmark_replay_import_binds_direct_scientist_owner() -> None:
    """The benchmark helper must not keep a hidden dependency on Runtime replay."""
    result = _run_isolated(
        """
import importlib

common = importlib.import_module('benchmarks.advanced.common')
canonical = importlib.import_module('polisyos.scientist.replay.deterministic')
assert common.runtime_replay is canonical
"""
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"


def test_dynamic_inventory_declares_core_replay_owner_at_scientist_path() -> None:
    """The fail-closed dynamic inventory must describe the delayed direct owner."""
    document = tomllib.loads(DYNAMIC_IMPORTS.read_text(encoding="utf-8"))
    replay_entries = [
        entry
        for entry in document["pattern"]
        if entry.get("source_file") == "src/polisyos/core/components/_cli_replay.py"
        and entry.get("call") == "importlib.import_module"
        and entry.get("pattern") in {
            "polisyos.runtime.replay",
            "polisyos.scientist.replay.deterministic",
        }
    ]

    assert len(replay_entries) == 1
    entry = replay_entries[0]
    assert entry["pattern"] == "polisyos.scientist.replay.deterministic"
    assert entry["target"] == "polisyos.scientist.replay.deterministic"
    assert entry["allowed_targets"] == ["polisyos.scientist.replay.deterministic"]


def test_replay_cli_check_only_reads_a_persisted_packet_without_running_it(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Check-only reports a persisted packet's completeness and never starts replay."""
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.components import _cli_replay

    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root)
    packet_ref = store.put_json(
        {
            "schema_version": "3.0",
            "run_id": "R_rep_01_check_only",
            "seed": 7,
            "inputs": {},
            "artifacts": {},
        },
        PutOptions(kind="scientist.decision_packet", media_type="application/json"),
    )
    args = SimpleNamespace(
        packet_ref=str(packet_ref.artifact_id),
        bundle=None,
        cas_root=cas_root,
        check_only=True,
        export=None,
        json=True,
    )

    exit_code = _cli_replay._cmd_replay(args)

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["level"] == "incomplete"
    assert payload["strategy"] == "none"
    assert payload["present_artifacts"] == 1
    assert "strategy_unresolved" in payload["reason_codes"]


def test_resume_dry_run_reads_persisted_checkpoint_head(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Resume dry-run preserves the old persisted checkpoint/run-directory contract."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.components import _cli_replay
    from polisyos.scientist.orchestration.engine.checkpoint import (
        create_checkpoint,
        update_checkpoint_head,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    cas_root = tmp_path / "cas"
    run_id = "R_rep_01_resume"
    store = FileSystemCAS(cas_root)
    created = create_checkpoint(
        store,
        run_id=run_id,
        state=ExperimentState(run_id=run_id, params={"phase": "PLAN"}).model_dump(
            mode="python", by_alias=True, exclude_none=False
        ),
        sequence_number=0,
        completed_node_alias="start",
        completed_node_id="scientist.node_noop@1.0.0",
        completed_nodes=["start"],
        workflow_id="wf_rep_01",
        workflow_fingerprint="1" * 64,
        fsm_phase="PLAN",
        cache_entry_refs=[],
    )
    update_checkpoint_head(
        cas_root / "runs" / run_id,
        run_id=run_id,
        checkpoint_ref=created.checkpoint_ref,
        sequence_number=0,
        node_alias="start",
        writer_pid=os.getpid(),
        writer_hostname="rep-01-test",
    )
    args = SimpleNamespace(
        cas_root=cas_root,
        run_id=run_id,
        checkpoint_policy="strict",
        json=True,
        dry_run=True,
        force=False,
    )

    exit_code = _cli_replay._cmd_resume(args)

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == run_id
    assert payload["sequence_number"] == 0
    assert payload["node_alias"] == "start"
    assert payload["workflow_id"] == "wf_rep_01"


def test_run_manifest_and_quality_replay_contracts_remain_available(tmp_path: Path) -> None:
    """REP-01 must not retire the independent historical RunManifest or quality replay path."""
    from polisyos.runtime.api import log_artifact, start_run
    from polisyos.runtime.manifest import RunManifest

    runs_root = tmp_path / "runs"
    manifest = start_run(run_id="R_rep_01_manifest", base_dir=runs_root)
    log_artifact(
        run_id=manifest.run_id,
        artifact_type="rep_01_probe",
        payload={"stable": True},
        base_dir=runs_root,
    )

    persisted = RunManifest.model_validate_json(
        (runs_root / manifest.run_id / "manifest.json").read_text(encoding="utf-8")
    )
    assert persisted.run_id == manifest.run_id
    assert any(item.artifact_type == "rep_01_probe" for item in persisted.artifacts)

    quality_replay = importlib.import_module("polisyos.runtime.quality.replay")
    assert callable(quality_replay.build_replay_manifest)
