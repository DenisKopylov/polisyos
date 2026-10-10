from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.devx.workspace import tool_configs
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


def test_dead_override_report_uses_product_caller_root_for_product_config(tmp_path: Path) -> None:
    _write_repo_with_metadata(tmp_path)
    generated = tmp_path / "ruff.generated.toml"
    generated.write_text(
        """
[lint.per-file-ignores]
"src/polisyos/pkg/live.py" = ["ANN401"]
""".lstrip(),
        encoding="utf-8",
    )

    report = dead_overrides.build_report(
        tmp_path,
        ruff_config="ruff.generated.toml",
    )

    ruff_findings = [finding for finding in report["findings"] if finding["tool"] == "ruff"]
    assert ruff_findings == []


def test_dead_override_report_uses_workspace_caller_root_for_workspace_config(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "policy-engine"
    _write_repo_with_metadata(repo_root)
    manifest = repo_root / "architecture" / "tooling" / "tool_config_split.toml"
    manifest.write_text(
        """
[ruff]
generated_config = "ruff.generated.toml"
workspace_root_generated_config = "architecture/tooling/ruff/workspace_root.toml"
workspace_root_prefix = "policy-engine"
""".lstrip(),
        encoding="utf-8",
    )
    metadata = repo_root / "architecture" / "tooling" / "static_analysis_overrides.toml"
    metadata.write_text(
        """
[tool_config_split]
manifest = "architecture/tooling/tool_config_split.toml"

[static_analysis_overrides]
status = "report_only"

[[override_scope]]
id = "pkg-ruff"
tool = "ruff"
pattern = "src/polisyos/pkg/**"
owner = "team-devx"
sunset = "2026-12-31"

[[override_scope]]
id = "pkg-mypy"
tool = "mypy"
pattern = "polisyos.pkg.*"
owner = "team-devx"
sunset = "2026-12-31"
""".lstrip(),
        encoding="utf-8",
    )
    workspace_config = repo_root / "architecture" / "tooling" / "ruff" / "workspace_root.toml"
    workspace_config.parent.mkdir(parents=True, exist_ok=True)
    workspace_config.write_text(
        """
[lint.per-file-ignores]
"policy-engine/src/polisyos/pkg/live.py" = ["ANN401"]
""".lstrip(),
        encoding="utf-8",
    )

    report = dead_overrides.build_report(
        repo_root,
        ruff_config="architecture/tooling/ruff/workspace_root.toml",
    )

    assert report["configs"]["ruff_project_root"] == str(tmp_path.resolve())
    assert report["summary"]["stale_ruff_override_count"] == 0
    assert report["summary"]["missing_metadata_count"] == 0
    assert not [finding for finding in report["findings"] if finding["tool"] == "ruff"]


@pytest.mark.parametrize(
    "config_text",
    [
        "[lint\n",
        '[lint]\nper-file-ignores = "not a mapping"\n',
        '[lint.per-file-ignores]\n"src/polisyos/pkg/live.py" = "ANN401"\n',
    ],
)
def test_dead_override_cli_fails_closed_for_corrupt_ruff_config(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    config_text: str,
) -> None:
    _write_repo_with_metadata(tmp_path)
    generated = tmp_path / "ruff.generated.toml"
    generated.write_text(config_text, encoding="utf-8")
    metadata = tmp_path / "architecture" / "tooling" / "static_analysis_overrides.toml"
    metadata.write_text(
        '[tool_config_split]\nruff_config = "ruff.generated.toml"\n\n'
        + metadata.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    output = tmp_path / "dead_overrides.json"

    with pytest.raises(ValueError, match="invalid Ruff override config"):
        tool_configs.override_report_findings(tmp_path)

    exit_code = dead_overrides.run_cli(
        [
            "--repo-root",
            str(tmp_path),
            "--ruff-config",
            "ruff.generated.toml",
            "--json-output",
            str(output),
        ]
    )

    assert exit_code != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert "ruff" in payload["error"].lower()
    assert payload["inputs"]["ruff_config"] == "ruff.generated.toml"
    assert capsys.readouterr().err


def test_dead_override_cli_fails_closed_when_ruff_config_is_missing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_repo_with_metadata(tmp_path)
    output = tmp_path / "dead_overrides.json"
    missing_config = "ruff.missing-generated.toml"

    exit_code = dead_overrides.run_cli(
        [
            "--repo-root",
            str(tmp_path),
            "--ruff-config",
            missing_config,
            "--json-output",
            str(output),
        ]
    )

    assert exit_code != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert missing_config in payload["error"]
    assert capsys.readouterr().err


def test_dead_override_cli_fails_closed_when_mypy_config_is_missing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_repo_with_metadata(tmp_path)
    output = tmp_path / "dead_overrides.json"
    missing_config = "architecture/tooling/mypy/missing-generated.ini"

    exit_code = dead_overrides.run_cli(
        [
            "--repo-root",
            str(tmp_path),
            "--mypy-config",
            missing_config,
            "--json-output",
            str(output),
        ]
    )

    assert exit_code != 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert missing_config in payload["error"]
    assert capsys.readouterr().err


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
