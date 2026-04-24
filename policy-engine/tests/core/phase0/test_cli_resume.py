from __future__ import annotations

import json
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components.cli import main
from polisyos.scientist.engine.checkpoint import create_checkpoint, update_checkpoint_head
from polisyos.scientist.engine.state import ExperimentState


def _seed_checkpoint(cas_root: Path, run_id: str) -> None:
    store = FileSystemCAS(cas_root)
    state = ExperimentState(run_id=run_id)
    created = create_checkpoint(
        store,
        run_id=state.run_id,
        state=state.model_dump(mode="python", by_alias=True, exclude_none=False),
        sequence_number=0,
        completed_node_alias="start",
        completed_node_id="scientist.node_noop@1.0.0",
        completed_nodes=["start"],
        workflow_id="scientist_default",
        workflow_fingerprint="a" * 64,
        fsm_phase="INTAKE",
        cache_entry_refs=[],
    )
    update_checkpoint_head(
        cas_root / "runs" / run_id,
        run_id=run_id,
        checkpoint_ref=created.checkpoint_ref,
        sequence_number=0,
        node_alias="start",
        writer_pid=111,
        writer_hostname="localhost",
    )


def test_resume_dry_run(tmp_path: Path, capsys) -> None:
    cas_root = tmp_path / ".polisyos"
    _seed_checkpoint(cas_root, "R_resume_cli")

    code = main(
        [
            "resume",
            "R_resume_cli",
            "--cas-root",
            str(cas_root),
            "--dry-run",
        ]
    )
    out = capsys.readouterr().out

    assert code == 0
    assert "run_id=R_resume_cli" in out
    assert "checkpoint.sequence=0" in out


def test_resume_dry_run_json(tmp_path: Path, capsys) -> None:
    cas_root = tmp_path / ".polisyos"
    _seed_checkpoint(cas_root, "R_resume_json")

    code = main(
        [
            "resume",
            "R_resume_json",
            "--cas-root",
            str(cas_root),
            "--dry-run",
            "--json",
        ]
    )
    out = capsys.readouterr().out

    assert code == 0
    payload = json.loads(out)
    assert payload["run_id"] == "R_resume_json"
    assert payload["sequence_number"] == 0


def test_resume_missing_checkpoint_returns_error(tmp_path: Path) -> None:
    cas_root = tmp_path / ".polisyos"
    cas_root.mkdir(parents=True, exist_ok=True)

    code = main(["resume", "R_missing", "--cas-root", str(cas_root), "--dry-run"])

    assert code == 1
