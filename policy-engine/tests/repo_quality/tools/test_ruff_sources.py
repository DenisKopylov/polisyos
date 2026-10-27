"""Exercise explicit Ruff source admission and its real no-directory-fallback path."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

from tools.devx.workspace import ruff_sources
from tools.devx.workspace._common import PRODUCT_ROOT


def _source(
    path: Path, *, logical: str = "policy-engine/src/polisyos/example.py"
) -> ruff_sources.RuffSource:
    return ruff_sources.RuffSource(logical, path, hashlib.sha256(path.read_bytes()).hexdigest())


def test_empty_post_filter_selection_refuses_before_ruff_launch() -> None:
    paths = (Path("policy-engine/src/polisyos/example.py"),)
    empty = tuple(_source(path) for path in paths if path.parts[2] == "src")
    assert not empty  # The actual incident's incorrect index filters every target out.
    with (
        patch.object(ruff_sources.subprocess, "run") as run,
        pytest.raises(ValueError, match="selection is empty"),
    ):
        ruff_sources.run_sources(empty)
    run.assert_not_called()


@pytest.mark.parametrize(
    "logical",
    [
        ".",
        "--fix",
        "*.py",
        "policy-engine/../x.py",
        "/x.py",
        "policy-engine/./x.py",
        "policy-engine//x.py",
    ],
)
def test_invalid_logical_target_never_launches_ruff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, logical: str
) -> None:
    monkeypatch.setattr(ruff_sources, "GIT_ROOT", tmp_path)
    source = tmp_path / "candidate.py"
    source.write_text("VALUE = 1\n")
    with (
        patch.object(ruff_sources.subprocess, "run") as run,
        pytest.raises(ValueError, match="explicit canonical"),
    ):
        ruff_sources.run_sources([_source(source, logical=logical)])
    run.assert_not_called()


def test_whole_manifest_is_admitted_before_any_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ruff_sources, "GIT_ROOT", tmp_path)
    source = tmp_path / "candidate.py"
    source.write_text("VALUE = 1\n")
    bad = ruff_sources.RuffSource("policy-engine/src/polisyos/second.py", source, "0" * 64)
    with (
        patch.object(ruff_sources.subprocess, "run") as run,
        pytest.raises(ValueError, match="content changed"),
    ):
        ruff_sources.run_sources([_source(source), bad])
    run.assert_not_called()


def test_duplicate_selection_and_unknown_operation_never_launch_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ruff_sources, "GIT_ROOT", tmp_path)
    source = tmp_path / "candidate.py"
    source.write_text("VALUE = 1\n")
    with patch.object(ruff_sources.subprocess, "run") as run:
        with pytest.raises(ValueError, match="duplicate logical"):
            ruff_sources.run_sources([_source(source), _source(source)])
        with pytest.raises(ValueError, match="Unsupported"):
            ruff_sources.run_sources(
                [_source(source)], operation=cast("ruff_sources.Operation", "--fix")
            )
    run.assert_not_called()


def test_directory_symlink_and_outside_source_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "worktree"
    root.mkdir()
    monkeypatch.setattr(ruff_sources, "GIT_ROOT", root)
    outside = tmp_path / "outside.py"
    outside.write_text("VALUE = 1\n")
    alias = root / "alias.py"
    alias.symlink_to(outside)
    for source in [
        ruff_sources.RuffSource("policy-engine/src/x.py", root, "0" * 64),
        ruff_sources.RuffSource("policy-engine/src/x.py", alias, "0" * 64),
        _source(outside),
    ]:
        with patch.object(ruff_sources.subprocess, "run") as run, pytest.raises(ValueError):
            ruff_sources.run_sources([source])
        run.assert_not_called()


def test_real_ruff_rewrites_only_stdin_and_preserves_every_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ruff_sources, "GIT_ROOT", tmp_path)
    selected = tmp_path / "selected.py"
    unrelated = tmp_path / "unrelated.py"
    original = "import os\n\nVALUE = 1\n"
    selected.write_text(original)
    unrelated.write_text(original)
    (result,) = ruff_sources.run_sources([_source(selected)], operation="fix-imports")
    assert result.returncode == 0, result.stderr
    assert "import os" not in result.stdout
    assert "VALUE = 1" in result.stdout
    assert result.command[-3:] == ("--stdin-filename", result.logical_path, "-")
    assert selected.read_text() == unrelated.read_text() == original
    assert result.source_sha256 == hashlib.sha256(selected.read_bytes()).hexdigest()


def test_original_empty_argv_fallback_really_mutates_unselected_fixture(tmp_path: Path) -> None:
    canary = tmp_path / "outside-selection.py"
    canary.write_text("import os\n\nVALUE = 1\n")
    targets: tuple[str, ...] = ()
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "ruff",
            "check",
            "--isolated",
            "--no-cache",
            "--select=F401",
            "--fix",
            *targets,
        ],
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "import os" not in canary.read_text()


def test_logical_test_role_controls_real_ruff_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ruff_sources, "GIT_ROOT", tmp_path)
    source = tmp_path / "candidate.py"
    source.write_text("assert True\n")
    script, test = ruff_sources.run_sources(
        [_source(source), _source(source, logical="policy-engine/tests/unit/test_example.py")]
    )
    assert "S101" in {item["code"] for item in json.loads(script.stdout)}
    assert "S101" not in {item["code"] for item in json.loads(test.stdout)}


def test_cli_empty_manifest_fails_without_touching_worktree(tmp_path: Path) -> None:
    manifest = tmp_path / "empty.json"
    manifest.write_text("[]\n")
    result = subprocess.run(
        [sys.executable, "-B", str(Path(ruff_sources.__file__)), "--manifest", str(manifest)],
        cwd=PRODUCT_ROOT,
        env={**os.environ, "PYTHONPATH": str(PRODUCT_ROOT)},
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert b"selection is empty" in result.stderr


def test_cli_check_carries_actual_selected_input_and_outside_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(ruff_sources, "GIT_ROOT", tmp_path)
    selected = tmp_path / "selected.py"
    selected.write_text("VALUE = 1\n")
    source = _source(selected)
    manifest = tmp_path / "selected.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "logical_path": source.logical_path,
                    "source_path": str(source.source_path),
                    "sha256": source.sha256,
                }
            ]
        )
    )
    assert ruff_sources.main(["--manifest", str(manifest)]) == 0
    payload = json.loads(capsys.readouterr().out)
    (row,) = payload["results"]
    assert row["source_sha256"] == source.sha256
    assert row["command"][-1] == "-"
    assert "unselected_source_files" in payload["unresolved_by_construction"]


def test_product_profile_uses_product_context_and_absolute_filename() -> None:
    logical = "policy-engine/tests/repo_quality/tools/test_ruff_sources.py"
    source = _source(Path(__file__).resolve(), logical=logical)
    (workspace,) = ruff_sources.run_sources([source])
    (product,) = ruff_sources.run_sources([source], config=PRODUCT_ROOT / "ruff.toml")

    assert workspace.returncode == 0, workspace.stderr or workspace.stdout
    assert product.returncode == 0, product.stderr or product.stdout
    assert "S101" not in {item["code"] for item in json.loads(workspace.stdout)}
    assert "S101" not in {item["code"] for item in json.loads(product.stdout)}
    assert workspace.cwd == str(ruff_sources.GIT_ROOT)
    assert workspace.command[-3:] == ("--stdin-filename", logical, "-")
    expected_product_path = PRODUCT_ROOT / "tests/repo_quality/tools/test_ruff_sources.py"
    assert Path(product.command[-2]).is_absolute()
    assert product.command[-2] == str(expected_product_path)
    assert product.cwd == str(PRODUCT_ROOT)
    assert product.config_path == str((PRODUCT_ROOT / "ruff.toml").resolve())

    with (
        patch.object(ruff_sources.subprocess, "run") as run,
        pytest.raises(ValueError, match="does not match the selected profile"),
    ):
        ruff_sources.run_sources(
            [source], config=PRODUCT_ROOT / "ruff.toml", cwd=ruff_sources.GIT_ROOT
        )
    run.assert_not_called()


def test_custom_profile_requires_explicit_cwd_and_uses_absolute_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ruff_sources, "GIT_ROOT", tmp_path)
    source_path = tmp_path / "candidate.py"
    source_path.write_text("assert True" + os.linesep)
    profile = tmp_path / "custom.toml"
    profile.write_text("[lint]" + os.linesep + 'select = ["S101"]' + os.linesep)
    source = _source(source_path)

    with (
        patch.object(ruff_sources.subprocess, "run") as run,
        pytest.raises(ValueError, match="explicit working directory"),
    ):
        ruff_sources.run_sources([source], config=profile)
    run.assert_not_called()

    (result,) = ruff_sources.run_sources([source], config=profile, cwd=tmp_path)
    assert result.returncode == 1, result.stderr
    assert "S101" in {item["code"] for item in json.loads(result.stdout)}
    assert result.cwd == str(tmp_path)
    assert result.command[-3:] == ("--stdin-filename", str(source_path.resolve()), "-")
