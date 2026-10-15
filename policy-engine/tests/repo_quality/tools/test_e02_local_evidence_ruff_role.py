from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path
from unittest.mock import patch

from tools.devx.workspace import _repo_hygiene as repo_hygiene
from tools.devx.workspace import format_check, lint_fast
from tools.devx.workspace._repo_hygiene import (
    ACTIVE_IGNORED_EVIDENCE_PYTHON_SCOPE,
    EVIDENCE_PYTHON_SCOPE,
    evidence_python_files,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
LOCAL_TEST = (
    "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
    "q2-packaging/raw/test_timeout_driver.py"
)
LOCAL_SCRIPT = (
    "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
    "q2-packaging/raw/timeout_driver.py"
)
ROLE_MATCHER = "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/**/test_*.py"
WORKER_TEST = "workers/dowhy-014/tests/test_worker.py"
WORKER_SCRIPT = "workers/dowhy-014/worker.py"
WORKER_TEST_MATCHER = '"workers/**/tests/**" = ["ANN", "E501", "PT011", "PT018", "S101", "T201"]\n'


def _ruff_diagnostics(config: Path, filename: str, source: str) -> list[dict[str, object]]:
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "ruff",
            "check",
            "--no-cache",
            "--output-format=json",
            "--config",
            str(config),
            "--stdin-filename",
            filename,
            "-",
        ],
        cwd=REPO_ROOT,
        input=source,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise AssertionError(f"Ruff failed unexpectedly: {result.stderr}")
    diagnostics = json.loads(result.stdout)
    if not isinstance(diagnostics, list):
        raise AssertionError("Ruff returned a non-list JSON result")
    return diagnostics


def test_local_evidence_assertions_are_limited_to_test_modules(tmp_path: Path) -> None:
    source = "\n".join("assert True" for _ in range(82)) + "\n"
    generated = (REPO_ROOT / "ruff.generated.toml").read_text(encoding="utf-8")
    matcher_entry = f'"{ROLE_MATCHER}" = ["S101"]\n'
    if generated.count(matcher_entry) != 1:
        raise AssertionError("the generated Ruff config must contain one local test-role matcher")

    test_diagnostics = _ruff_diagnostics(REPO_ROOT / "ruff.toml", LOCAL_TEST, source)
    if test_diagnostics:
        raise AssertionError(f"test-role assertions should be accepted: {test_diagnostics!r}")

    script_diagnostics = _ruff_diagnostics(REPO_ROOT / "ruff.toml", LOCAL_SCRIPT, source)
    script_codes = [row.get("code") for row in script_diagnostics]
    if script_codes != ["S101"] * 82:
        raise AssertionError(f"sibling scripts must retain S101: {script_codes!r}")

    removed_root = tmp_path / "ruff.toml"
    removed_generated = tmp_path / "ruff.generated.toml"
    removed_root.write_text((REPO_ROOT / "ruff.toml").read_text(encoding="utf-8"), encoding="utf-8")
    removed_generated.write_text(generated.replace(matcher_entry, ""), encoding="utf-8")
    removed_codes = [row.get("code") for row in _ruff_diagnostics(removed_root, LOCAL_TEST, source)]
    if removed_codes != ["S101"] * 82:
        raise AssertionError(
            f"removing the matcher must restore all 82 findings: {removed_codes!r}"
        )


def test_evidence_role_is_enumerated_and_wired_to_lint_and_format_routes() -> None:
    selected = evidence_python_files()
    if not selected:
        raise AssertionError("active E02 evidence role must not select an empty set")
    if LOCAL_TEST not in selected or LOCAL_SCRIPT not in selected:
        raise AssertionError("tracked ignored Q2 sources must stay in the evidence role")
    if any(
        not any(
            path == root or path.startswith(f"{root.rstrip('/')}/")
            for root in EVIDENCE_PYTHON_SCOPE
        )
        for path in selected
    ):
        raise AssertionError("evidence selector returned a path outside its declared role")
    if not ACTIVE_IGNORED_EVIDENCE_PYTHON_SCOPE:
        raise AssertionError("active Q2 ignored source root must remain explicitly declared")

    with patch("tools.devx.workspace.lint_fast.run_command") as run:
        lint_fast.main(["--skip-frontend", "--skip-docs"])
    lint_commands = [call.args[0] for call in run.call_args_list]
    lint_route = next(
        command for command in lint_commands if "current E02 evidence Python role" in command.label
    )
    assert lint_route.argv[-len(selected) :] == tuple(selected)

    with patch("tools.devx.workspace.format_check.run_command") as run:
        format_check.main(["--skip-frontend", "--skip-rego"])
    format_commands = [call.args[0] for call in run.call_args_list]
    format_route = next(
        command
        for command in format_commands
        if "current E02 evidence Python role" in command.label
    )
    assert format_route.argv[-len(selected) :] == tuple(selected)


def test_evidence_role_uses_index_plus_active_ignored_sources(tmp_path: Path) -> None:
    git_root = tmp_path / "repo"
    product_root = git_root / "policy-engine"
    for root in (*EVIDENCE_PYTHON_SCOPE, *ACTIVE_IGNORED_EVIDENCE_PYTHON_SCOPE):
        (product_root / root).mkdir(parents=True, exist_ok=True)

    local_root = EVIDENCE_PYTHON_SCOPE[0]
    (product_root / local_root / "reviews").mkdir(parents=True, exist_ok=True)
    tracked_source = f"{local_root}/reviews/tracked_source.py"
    staged_source = f"{local_root}/reviews/staged_source.py"
    untracked_history = f"{local_root}/reviews/untracked_history.py"
    active_q2_root = ACTIVE_IGNORED_EVIDENCE_PYTHON_SCOPE[0]
    ignored_q2_sources = tuple(f"{active_q2_root}/q2_caller_{index}.py" for index in range(6))

    ignore_file = product_root / ".gitignore"
    ignore_file.write_text(f"/{active_q2_root}/\n", encoding="utf-8")
    (product_root / tracked_source).write_text("VALUE = 1\n", encoding="utf-8")

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(git_root), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    git_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(git_root)], check=True)
    git("config", "user.name", "PolicyOS role test")
    git("config", "user.email", "policyos-role-test@example.invalid")
    git("add", "policy-engine/.gitignore", f"policy-engine/{tracked_source}")
    git("commit", "-m", "seed evidence source role")

    (product_root / staged_source).write_text("VALUE = 2\n", encoding="utf-8")
    git("add", f"policy-engine/{staged_source}")
    (product_root / untracked_history).write_text("VALUE = 3\n", encoding="utf-8")
    for relative_path in ignored_q2_sources:
        (product_root / relative_path).write_text("VALUE = 4\n", encoding="utf-8")
        git("add", "-f", f"policy-engine/{relative_path}")

    with patch.multiple(
        repo_hygiene,
        GIT_ROOT=git_root,
        PRODUCT_ROOT=product_root,
        _WORKSPACE_PREFIX="policy-engine",
    ):
        selected = repo_hygiene.evidence_python_files()
        assert tracked_source in selected
        assert staged_source in selected
        assert set(ignored_q2_sources).issubset(selected)
        assert untracked_history not in selected

        default_untracked_selection = repo_hygiene.current_python_files((local_root,))
        assert untracked_history in default_untracked_selection


def test_worker_test_style_is_generic_and_test_only(tmp_path: Path) -> None:
    source = "assert True\n"
    generated = (REPO_ROOT / "ruff.generated.toml").read_text(encoding="utf-8")
    if generated.count(WORKER_TEST_MATCHER) != 1:
        raise AssertionError("the generated Ruff config must contain one worker test-role matcher")

    if not (REPO_ROOT / "workers/dowhy-014/pyproject.toml").is_file():
        raise AssertionError("the isolated worker profile must remain present")
    worker_config = tomllib.loads(
        (REPO_ROOT / "workers/dowhy-014/pyproject.toml").read_text(encoding="utf-8")
    )
    worker_ruff = worker_config.get("tool", {}).get("ruff", {})
    if "per-file-ignores" in worker_ruff.get("lint", {}):
        raise AssertionError("the worker must consume the generic root test role")

    metadata = tomllib.loads(
        (REPO_ROOT / "architecture/tooling/static_analysis_overrides.toml").read_text(
            encoding="utf-8"
        )
    )
    if any(
        row.get("id") == "dowhy-worker-ruff-test-ratchet"
        for row in metadata.get("override_scope", [])
    ):
        raise AssertionError("retired nested worker suppression must leave no stale override row")

    test_diagnostics = _ruff_diagnostics(REPO_ROOT / "ruff.toml", WORKER_TEST, source)
    if test_diagnostics:
        raise AssertionError(
            f"worker test role should accept test assertions: {test_diagnostics!r}"
        )

    script_codes = [
        row.get("code") for row in _ruff_diagnostics(REPO_ROOT / "ruff.toml", WORKER_SCRIPT, source)
    ]
    if script_codes != ["S101"]:
        raise AssertionError(f"worker production code must retain S101: {script_codes!r}")

    removed_root = tmp_path / "ruff.toml"
    removed_generated = tmp_path / "ruff.generated.toml"
    removed_root.write_text((REPO_ROOT / "ruff.toml").read_text(encoding="utf-8"), encoding="utf-8")
    removed_generated.write_text(generated.replace(WORKER_TEST_MATCHER, ""), encoding="utf-8")
    removed_codes = [
        row.get("code") for row in _ruff_diagnostics(removed_root, WORKER_TEST, source)
    ]
    if removed_codes != ["S101"]:
        raise AssertionError(f"removing the generic test role must restore S101: {removed_codes!r}")
