from __future__ import annotations

import json
from pathlib import Path

from tools.ops_runners.reports import dead_overrides


def test_dead_override_report_warns_on_moved_and_deleted_targets(tmp_path: Path) -> None:
    _write_repo_with_metadata(tmp_path)

    report = dead_overrides.build_report(tmp_path)
    findings = report["findings"]

    assert report["mode"] == "report_only"
    assert report["summary"]["stale_mypy_override_count"] == 2
    assert report["summary"]["stale_ruff_override_count"] == 2
    assert report["summary"]["missing_metadata_count"] == 0
    assert _finding_detail(findings, "mypy", "polisyos.pkg.moved")
    assert "possible moved file candidates" in _finding_detail(
        findings, "mypy", "polisyos.pkg.moved"
    )
    assert "src/polisyos/pkg/new/moved.py" in _finding_detail(
        findings, "ruff", "src/polisyos/pkg/moved.py"
    )
    assert "no live file with matching basename found" in _finding_detail(
        findings, "ruff", "src/polisyos/pkg/deleted.py"
    )


def test_dead_override_report_remains_zero_exit_when_debt_is_visible(tmp_path: Path) -> None:
    _write_repo_without_metadata(tmp_path)
    output = tmp_path / "dead_overrides.json"

    assert dead_overrides.run_cli(["--repo-root", str(tmp_path), "--json-output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "reported"
    assert payload["summary"]["missing_metadata_count"] == 2
    assert {
        (finding["tool"], finding["subject"])
        for finding in payload["findings"]
        if finding["check"] == "override-metadata"
    } == {
        ("mypy", "polisyos.pkg.live"),
        ("ruff", "src/polisyos/pkg/live.py"),
    }


def _write_repo_with_metadata(repo_root: Path) -> None:
    _write_common_configs(
        repo_root,
        metadata="""
[static_analysis_overrides]
status = "report_only"

[[override_scope]]
id = "pkg-mypy"
tool = "mypy"
pattern = "polisyos.pkg.*"
owner = "team-devx"
sunset = "2026-12-31"

[[override_scope]]
id = "pkg-ruff"
tool = "ruff"
pattern = "src/polisyos/pkg/**"
owner = "team-devx"
sunset = "2026-12-31"
""",
    )


def _write_repo_without_metadata(repo_root: Path) -> None:
    _write_common_configs(
        repo_root,
        metadata="""
[static_analysis_overrides]
status = "report_only"
""",
    )
    (repo_root / "mypy.ini").write_text(
        """
[mypy]
strict = true

[mypy-polisyos.pkg.live]
ignore_errors = true
""".lstrip(),
        encoding="utf-8",
    )
    (repo_root / "ruff.toml").write_text(
        """
[lint.per-file-ignores]
"src/polisyos/pkg/live.py" = ["ANN401"]
""".lstrip(),
        encoding="utf-8",
    )


def _write_common_configs(repo_root: Path, *, metadata: str) -> None:
    (repo_root / "src" / "polisyos" / "pkg" / "new").mkdir(parents=True)
    (repo_root / "architecture" / "tooling").mkdir(parents=True)
    (repo_root / "src" / "polisyos" / "pkg" / "live.py").write_text("", encoding="utf-8")
    (repo_root / "src" / "polisyos" / "pkg" / "new" / "moved.py").write_text(
        "",
        encoding="utf-8",
    )
    (repo_root / "mypy.ini").write_text(
        """
[mypy]
strict = true

[mypy-polisyos.pkg.live,polisyos.pkg.moved,polisyos.pkg.deleted]
ignore_errors = true
""".lstrip(),
        encoding="utf-8",
    )
    (repo_root / "ruff.toml").write_text(
        """
[lint.per-file-ignores]
"src/polisyos/pkg/live.py" = ["ANN401"]
"src/polisyos/pkg/moved.py" = ["ANN401"]
"src/polisyos/pkg/deleted.py" = ["ANN401"]
""".lstrip(),
        encoding="utf-8",
    )
    (repo_root / "architecture" / "tooling" / "static_analysis_overrides.toml").write_text(
        metadata.lstrip(),
        encoding="utf-8",
    )


def _finding_detail(findings: list[dict[str, object]], tool: str, subject: str) -> str:
    for finding in findings:
        if finding["tool"] == tool and finding["subject"] == subject:
            return str(finding["detail"])
    return ""
