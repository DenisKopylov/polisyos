from __future__ import annotations

from pathlib import Path

from tools.ops_runners.runtime.runtime_state_cleanup import build_cleanup_report, render_text

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_TEXT = (REPO_ROOT / "architecture" / "local_runtime_state.toml").read_text(
    encoding="utf-8"
)


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "architecture").mkdir(parents=True)
    (root / "architecture" / "local_runtime_state.toml").write_text(
        CONTRACT_TEXT,
        encoding="utf-8",
    )
    (root / ".polisyos").mkdir()
    return root


def test_runtime_state_cleanup_dry_run_summarizes_without_deleting(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    run_dir = repo / ".polisyos" / "runs" / "R_123"
    run_dir.mkdir(parents=True)
    (run_dir / "state.json").write_text("{}", encoding="utf-8")

    report = build_cleanup_report(repo_root=repo, slots=("runs",), apply=False)
    text = render_text(report)

    assert report.status == "dry_run"
    assert report.summaries[0].target_count == 1
    assert "slot: runs" in text
    assert run_dir.exists()


def test_runtime_state_cleanup_apply_deletes_slot_contents_not_root(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    report_dir = repo / ".polisyos" / "reports" / "phase-2-3"
    report_dir.mkdir(parents=True)
    (report_dir / "summary.md").write_text("# Summary\n", encoding="utf-8")

    report = build_cleanup_report(repo_root=repo, slots=("reports",), apply=True)

    assert report.status == "applied"
    assert report.summaries[0].deleted_count == 1
    assert not report_dir.exists()
    assert (repo / ".polisyos" / "reports").exists()


def test_runtime_state_cleanup_blocks_production_without_explicit_approval(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    snapshot = repo / ".polisyos" / "production_data" / "snapshot"
    snapshot.mkdir(parents=True)
    (snapshot / "data.json").write_text("{}", encoding="utf-8")

    report = build_cleanup_report(repo_root=repo, slots=("production_data",), apply=True)

    assert report.status == "blocked"
    assert "approve-production-snapshots" in report.blocked_reasons[0]
    assert snapshot.exists()


def test_runtime_state_cleanup_requires_production_approval_to_delete_snapshots(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    snapshot = repo / ".polisyos" / "production_data" / "snapshot"
    snapshot.mkdir(parents=True)
    (snapshot / "data.json").write_text("{}", encoding="utf-8")

    report = build_cleanup_report(
        repo_root=repo,
        slots=("production_data",),
        apply=True,
        approve_production_snapshots=True,
    )

    assert report.status == "applied"
    assert report.summaries[0].deleted_count == 1
    assert not snapshot.exists()
    assert (repo / ".polisyos" / "production_data").exists()
