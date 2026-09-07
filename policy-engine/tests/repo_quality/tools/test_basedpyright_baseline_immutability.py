"""Exercise workspace checkers against real basedpyright baseline side effects."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tools.devx.workspace import (
    _common,
    core_runtime_basedpyright,
    lint_full,
    python_base_basedpyright,
    runtime_surface,
)

_LAYERS = ("common", "ir", "core", "runtime", "scientist")


def _baseline_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in (root / "architecture" / "baselines").rglob("*")
        if path.is_file()
    }


@pytest.fixture
def baseline_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    executable = Path(sys.executable).parent / "basedpyright"
    assert executable.is_file(), "Install the lint extra to run native basedpyright regressions"

    # An inherited CI vendor variable would switch upstream from auto to lock,
    # hiding the local write regression. Pass only the process runtime essentials.
    for key in tuple(os.environ):
        if key not in {"HOME", "PATH", "TMPDIR", "SYSTEMROOT"}:
            monkeypatch.delenv(key)
    monkeypatch.setenv("PATH", f"{executable.parent}{os.pathsep}{os.environ.get('PATH', '')}")

    for layer in _LAYERS:
        source = tmp_path / "src" / "polisyos" / layer / "example.py"
        source.parent.mkdir(parents=True)
        source.write_text('value: int = "wrong"\n', encoding="utf-8")
    # Only the analysis target is 3.13: the locked checker's 3.14 typeshed has a
    # separate templatelib diagnostic outside this isolated project.
    (tmp_path / "basedpyright.toml").write_text(
        '[tool.basedpyright]\ninclude = ["src"]\n'
        'baselineFile = "architecture/baselines/basedpyright/baseline.json"\n'
        'pythonVersion = "3.13"\ntypeCheckingMode = "standard"\n',
        encoding="utf-8",
    )
    initial = subprocess.run(
        [str(executable), "--project", "basedpyright.toml", "--writebaseline"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert initial.returncode == 1, initial.stdout + initial.stderr
    assert "5 errors" in initial.stdout
    sibling = tmp_path / "architecture" / "baselines" / "other" / "sentinel.bin"
    sibling.parent.mkdir()
    sibling.write_bytes(b"separate frozen baseline\x00\xff\n")

    monkeypatch.setattr(core_runtime_basedpyright, "PRODUCT_ROOT", tmp_path)
    monkeypatch.setattr(
        core_runtime_basedpyright, "CURATED_EXTRA_SCOPE", ("src/polisyos/scientist",)
    )

    def run_native_command(spec: _common.CommandSpec) -> None:
        if "basedpyright" in spec.argv:
            # Keep the real checker's entire argv; bypass uv's environment setup
            # and unrelated lint/mypy/API/test commands in these composite gates.
            command = spec.argv[spec.argv.index("basedpyright") :]
            _common.run_command(replace(spec, argv=command, cwd=tmp_path))

    monkeypatch.setattr(python_base_basedpyright, "run_command", run_native_command)
    monkeypatch.setattr(runtime_surface, "run_command", run_native_command)

    def run_workspace_command(spec: _common.CommandSpec) -> None:
        # Check lint_full's actual selection and run the selected consumers.
        # This adapter does not verify the generic standalone-file bootstrap.
        for module in (python_base_basedpyright, runtime_surface):
            target = f"tools/devx/workspace/{module.__name__.rsplit('.', 1)[-1]}.py"
            if target in spec.argv:
                module.main(list(spec.argv[spec.argv.index(target) + 1 :]))

    monkeypatch.setattr(lint_full, "run_command", run_workspace_command)
    return tmp_path


def _check(entrypoint: str) -> int:
    try:
        if entrypoint == "core-requested":
            return core_runtime_basedpyright.main(["src/polisyos/common"])
        if entrypoint in {"core-default", "core-curated"}:
            return core_runtime_basedpyright.main([])
        if entrypoint == "python-base":
            return python_base_basedpyright.main([])
        if entrypoint == "runtime-surface":
            return runtime_surface.main(["--skip-openapi", "--skip-tests"])
        if entrypoint in {"lint-full-base", "lint-full-runtime"}:
            return lint_full.main(["--skip-frontend", "--skip-policy", "--skip-helm"])
    except subprocess.CalledProcessError as error:
        return error.returncode
    raise AssertionError(f"Unknown fixture entrypoint: {entrypoint}")


@pytest.mark.parametrize(
    ("entrypoint", "layer"),
    [
        ("core-requested", "common"),
        ("core-default", "runtime"),
        ("core-curated", "scientist"),
        ("python-base", "core"),
        ("runtime-surface", "runtime"),
        ("lint-full-base", "core"),
        ("lint-full-runtime", "runtime"),
    ],
)
def test_checks_preserve_every_baseline_and_reject_new_errors(
    baseline_project: Path, entrypoint: str, layer: str, capfd: pytest.CaptureFixture[str]
) -> None:
    source = baseline_project / "src" / "polisyos" / layer / "example.py"
    source.write_text("value: int = 1\n", encoding="utf-8")
    frozen = _baseline_bytes(baseline_project)

    for run in range(2):
        assert _check(entrypoint) == 0
        assert _baseline_bytes(baseline_project) == frozen, (
            f"baseline mutated after check {run + 1}"
        )

    source.write_text("value: int = 1\nunknown_name()\n", encoding="utf-8")
    capfd.readouterr()
    assert _check(entrypoint) == 1
    assert "reportUndefinedVariable" in capfd.readouterr().out
    assert _baseline_bytes(baseline_project) == frozen


def test_explicit_update_changes_only_the_configured_baseline(baseline_project: Path) -> None:
    frozen = _baseline_bytes(baseline_project)
    for source in (baseline_project / "src").rglob("*.py"):
        source.write_text("value: int = 1\n", encoding="utf-8")

    completed = subprocess.run(
        ["basedpyright", "--project", "basedpyright.toml", "--writebaseline"],
        cwd=baseline_project,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    after = _baseline_bytes(baseline_project)
    assert after.keys() == frozen.keys()
    assert {path for path in after if after[path] != frozen[path]} == {
        "architecture/baselines/basedpyright/baseline.json"
    }
    assert json.loads(after["architecture/baselines/basedpyright/baseline.json"]) == {"files": {}}
