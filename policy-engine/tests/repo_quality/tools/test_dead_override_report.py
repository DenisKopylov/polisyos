from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tools.devx.workspace import tool_configs
from tools.ops_runners.reports import dead_overrides


def test_dead_override_report_warns_on_moved_and_deleted_targets(tmp_path: Path) -> None:
    _write_repo_with_metadata(tmp_path)

    report = dead_overrides.build_report(tmp_path, _fixture_filesystem_fallback=True)
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

    assert (
        dead_overrides.run_cli(
            ["--repo-root", str(tmp_path), "--json-output", str(output)],
            _fixture_filesystem_fallback=True,
        )
        == 0
    )

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
        _fixture_filesystem_fallback=True,
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
        _fixture_filesystem_fallback=True,
    )

    assert report["configs"]["ruff_project_root"] == str(tmp_path.resolve())
    assert report["summary"]["stale_ruff_override_count"] == 0
    assert report["summary"]["missing_metadata_count"] == 0
    assert not [finding for finding in report["findings"] if finding["tool"] == "ruff"]


def test_ruff_override_liveness_uses_current_inputs_and_explicit_fixture_fallback(
    tmp_path: Path,
) -> None:
    archive = (
        "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/archive/test_historical.py"
    )
    active = (
        "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
        "q2-packaging/raw/test_active.py"
    )
    matcher = "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/**/test_*.py"
    for relative in (archive, active):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("VALUE = 1\n", encoding="utf-8")

    active_index = dead_overrides.RepoIndex((), {}, {}, ruff_files=(active,))
    matched = dead_overrides._ruff_entry_existence(tmp_path, matcher, active_index)
    assert matched == {
        "exists": True,
        "detail": "pattern matches 1 current Ruff input path(s)",
    }

    empty_current_index = dead_overrides.RepoIndex((), {}, {}, ruff_files=())
    archived_glob = dead_overrides._ruff_entry_existence(
        tmp_path,
        matcher,
        empty_current_index,
    )
    archived_exact = dead_overrides._ruff_entry_existence(
        tmp_path,
        archive,
        empty_current_index,
    )
    assert archived_glob["exists"] is False
    assert archived_exact["exists"] is False

    fixture_index = dead_overrides.RepoIndex((), {}, {})
    with pytest.raises(ValueError, match="explicit fixture filesystem context"):
        dead_overrides._ruff_entry_existence(tmp_path, matcher, fixture_index)
    fixture_result = dead_overrides._ruff_entry_existence(
        tmp_path,
        matcher,
        fixture_index,
        fixture_filesystem_fallback=True,
    )
    assert fixture_result == {
        "exists": True,
        "detail": "pattern matches 2 fixture path(s)",
    }


def test_ruff_liveness_matches_observed_glob_semantics() -> None:
    paths = (
        "nested/migrate.py",
        "nested/sentinel.py",
        "nested/deep/file.py",
        "nested/a/b/file.py",
        "x/nested/file.py",
        "src/tests/test_source.py",
        "src/tests/deep/test_child.py",
    )

    assert dead_overrides._matching_current_ruff_files(paths, "migrate.py") == (
        "nested/migrate.py",
    )
    assert dead_overrides._matching_current_ruff_files(paths, "nested/*.py") == (
        "nested/migrate.py",
        "nested/sentinel.py",
        "nested/deep/file.py",
        "nested/a/b/file.py",
    )
    assert dead_overrides._matching_current_ruff_files(paths, "nested/*/file.py") == (
        "nested/deep/file.py",
        "nested/a/b/file.py",
    )
    assert dead_overrides._matching_current_ruff_files(paths, "src/tests/*.py") == (
        "src/tests/test_source.py",
        "src/tests/deep/test_child.py",
    )
    assert dead_overrides._matching_current_ruff_files(paths, "src/**/test_*.py") == (
        "src/tests/test_source.py",
        "src/tests/deep/test_child.py",
    )


def test_ruff_current_input_matcher_compiles_once_per_selector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = tuple(f"nested/{index}/test_{index}.py" for index in range(64))
    compiled: list[tuple[str, ...]] = []
    compile_pattern = dead_overrides._ruff_pattern_regex

    def record_compile(pattern_parts: tuple[str, ...]) -> re.Pattern[str]:
        compiled.append(pattern_parts)
        return compile_pattern(pattern_parts)

    monkeypatch.setattr(dead_overrides, "_ruff_pattern_regex", record_compile)

    assert (
        dead_overrides._matching_current_ruff_files(
            paths,
            "nested/**/test_*.py",
        )
        == paths
    )
    assert compiled == [("nested", "**", "test_*.py")]


def test_negated_ruff_pattern_fails_closed_against_real_ruff_semantics(
    tmp_path: Path,
) -> None:
    foo = tmp_path / "foo.py"
    bar = tmp_path / "bar.py"
    foo.write_text("import os\n", encoding="utf-8")
    bar.write_text("import os\n", encoding="utf-8")
    config = tmp_path / "ruff.toml"
    config.write_text(
        '[lint]\nselect = ["F401"]\n\n[lint.per-file-ignores]\n"!foo.py" = ["F401"]\n',
        encoding="utf-8",
    )

    command = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "--no-cache",
        "--config",
        str(config),
        "--output-format",
        "json",
    ]
    for paths in ((foo,), (foo, bar)):
        result = subprocess.run(
            [*command, *(str(path) for path in paths)],
            cwd=tmp_path,
            capture_output=True,
            check=False,
            text=True,
        )
        assert result.returncode == 1, result.stderr
        # Ruff 0.15.0 does not ignore foo.py; with bar.py present, only bar is ignored.
        findings = json.loads(result.stdout)
        assert {Path(item["filename"]).name for item in findings} == {"foo.py"}

    # The current input contains only the path the flawed positive matcher would admit.
    index = dead_overrides.RepoIndex((), {}, {}, ruff_files=("foo.py",))
    with pytest.raises(ValueError, match="unsupported negated Ruff per-file pattern"):
        dead_overrides._ruff_entry_existence(tmp_path, "!foo.py", index)
    with pytest.raises(ValueError, match="unsupported negated Ruff per-file pattern"):
        dead_overrides._matching_current_ruff_files(("foo.py", "bar.py"), "!foo.py")


@pytest.mark.parametrize(
    "pattern",
    ["file?.py", "file[ab].py", "file**name.py", r"nested\file.py", "{a,b}.py"],
)
def test_ruff_current_input_matcher_fails_closed_on_unsupported_syntax(pattern: str) -> None:
    with pytest.raises(ValueError, match="unsupported Ruff per-file pattern"):
        dead_overrides._matching_current_ruff_files(("nested/file.py",), pattern)


def test_noncanonical_root_requires_explicit_fixture_context(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="explicit fixture context"):
        dead_overrides._current_ruff_files(tmp_path)

    assert (
        dead_overrides._current_ruff_files(
            tmp_path,
            fixture_filesystem_fallback=True,
        )
        is None
    )


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
        ],
        _fixture_filesystem_fallback=True,
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
        ],
        _fixture_filesystem_fallback=True,
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
        ],
        _fixture_filesystem_fallback=True,
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
