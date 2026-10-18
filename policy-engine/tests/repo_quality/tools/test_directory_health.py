from __future__ import annotations

from pathlib import Path

import pytest

from tools.devx.workspace import clean_local_reports
from tools.quality.validation import directory_health


def test_phase1_3_phase_local_junk_build_residue_fails_hygiene(
    tmp_path: Path,
) -> None:
    residue = tmp_path / "_build" / "phase7-local-junk-20260505T092233Z"
    residue.mkdir(parents=True)
    (residue / "audit.tar.gz").write_text("local residue\n", encoding="utf-8")

    findings = directory_health._phase_local_junk_findings(tmp_path, {})

    assert findings == [
        directory_health.Finding(
            "phase-local-junk-residue",
            "blocker",
            "_build/phase7-local-junk-20260505T092233Z",
            "phase-local-junk build residue must be deleted or registered as a dated "
            "scratch exception",
        )
    ]


def test_phase1_3_phase_local_junk_exception_requires_explicit_scratch_policy(
    tmp_path: Path,
) -> None:
    residue = tmp_path / "_build" / "phase7-local-junk-20260505T092233Z"
    residue.mkdir(parents=True)
    contract = {
        "health_exception": [
            {
                "kind": "phase_local_junk_residue",
                "source_glob": "_build/phase7-local-junk-20260505T092233Z",
            }
        ]
    }

    findings = directory_health._phase_local_junk_findings(tmp_path, contract)

    assert findings == [
        directory_health.Finding(
            "phase-local-junk-residue",
            "blocker",
            "_build/phase7-local-junk-20260505T092233Z",
            "phase-local-junk build residue must be deleted or registered as a dated "
            "scratch exception",
        )
    ]


def test_phase1_3_registered_phase_local_junk_exception_is_allowed(
    tmp_path: Path,
) -> None:
    residue = tmp_path / "_build" / "phase7-local-junk-20260505T092233Z"
    residue.mkdir(parents=True)
    contract = {
        "health_exception": [
            {
                "kind": "phase_local_junk_residue",
                "scratch_policy": "explicitly_ignored",
                "source_glob": "_build/phase7-local-junk-20260505T092233Z",
            }
        ]
    }

    assert directory_health._phase_local_junk_findings(tmp_path, contract) == []


def test_phase1_3_clean_local_reports_collects_phase_local_junk_roots(
    tmp_path: Path,
) -> None:
    residue = tmp_path / "_build" / "phase7-local-junk-20260505T092233Z"
    residue.mkdir(parents=True)
    (residue / "audit.tar.gz").write_text("local residue\n", encoding="utf-8")
    reviewed_report = tmp_path / "docs" / "archive" / "reports" / "reviewed.md"
    reviewed_report.parent.mkdir(parents=True)
    reviewed_report.write_text("reviewed evidence\n", encoding="utf-8")
    baseline = tmp_path / "architecture" / "baselines" / "reviewed" / "summary.json"
    baseline.parent.mkdir(parents=True)
    baseline.write_text("{}", encoding="utf-8")

    plan = clean_local_reports.build_cleanup_plan(tmp_path)
    candidates = {item["path"]: item for item in plan["candidates"]}

    assert candidates["_build/phase7-local-junk-20260505T092233Z"] == {
        "path": "_build/phase7-local-junk-20260505T092233Z",
        "kind": "phase_local_junk_residue",
        "reason": "ignored phase-local-junk build residue",
        "owner_approval_required": False,
    }
    assert "docs/archive/reports/reviewed.md" not in candidates
    assert "architecture/baselines/reviewed/summary.json" not in candidates


def test_dashboard_facade_uses_current_scanner_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "src"
    source_root.mkdir()
    (source_root / "README.md").write_text("source docs\n", encoding="utf-8")
    for name in ("a.py", "b.py"):
        (source_root / name).write_text("pass\n", encoding="utf-8")
    tracked_roots: list[Path] = []

    def tracked_files(repo_root: Path) -> list[str]:
        tracked_roots.append(repo_root)
        return ["src/a.py", "src/b.py"]

    def walk_dirs(repo_root: Path, relative_root: str = ".") -> list[Path]:
        assert relative_root == "."
        return [repo_root, source_root]

    monkeypatch.setattr(directory_health, "_tracked_files", tracked_files)
    monkeypatch.setattr(directory_health, "_ignored_files", lambda _root: [])
    monkeypatch.setattr(directory_health, "_walk_dirs", walk_dirs)
    monkeypatch.setattr(
        directory_health,
        "_read_toml",
        lambda _path: {"non_product_python_root": []},
    )
    monkeypatch.setattr(directory_health, "_collect_closure_findings", lambda *_args: [])

    dashboard = directory_health._build_dashboard(
        tmp_path,
        {"thresholds": {"high_volume_tracked_files": 1}},
        {"contract": [{"path": "src"}]},
        {"classes": {"counts": {"product_seed_assets": 2}}},
    )

    assert tracked_roots == [tmp_path, tmp_path]
    assert dashboard["top_level_directories"] == {
        "present": ["src"],
        "covered": ["src"],
        "missing_contract": [],
    }
    assert dashboard["high_volume_subtrees"] == [
        {
            "path": "src",
            "tracked_file_count": 2,
            "immediate_child_directory_count": 0,
            "documented": True,
        }
    ]
    assert dashboard["largest_subtrees_by_tracked_file_count"] == [
        {"path": "src", "tracked_file_count": 2}
    ]
    assert dashboard["metrics"]["top_level_directory_contract_coverage_percent"] == 100.0
    assert dashboard["metrics"]["product_asset_count"] == 2
