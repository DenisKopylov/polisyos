from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path

import pytest
from pydantic import BaseModel

from polisyos.schemas.abi_models import ABIModelEntry, CompatMode, Lifecycle, Priority
from tools.quality.diagnostics import abi_diff, gen_schema
from tools.quality.lint import lint_foundry, lint_imports
from tools.quality.lint.rules import iter_rules


def _write_policy(path: Path, src_root: Path) -> None:
    path.write_text(
        textwrap.dedent(
            f"""
            [policy]
            version = "1.0"
            internal_prefix = "polisyos"
            src_root = "{src_root.as_posix()}"

            [roots]
            known = ["ir", "foundry"]

            [internal.allow]
            ir = []
            foundry = ["ir"]

            [external.allow]
            ir = []
            foundry = []
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _write_valid_exceptions(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            """
            [[exception]]
            source_glob = "src/polisyos/ir/*.py"
            id = "second"
            owner = "arch"
            reason = "second"
            expires = "2099-01-01"
            external_module = "pandas"

            [[exception]]
            source_glob = "src/polisyos/ir/*.py"
            id = "first"
            owner = "arch"
            reason = "first"
            expires = "2099-01-01"
            external_module = "numpy"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _commit_git_fixture(worktree_root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(worktree_root)], check=True)
    subprocess.run(
        ["git", "-C", str(worktree_root), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(worktree_root), "config", "user.name", "PolicyOS Tests"],
        check=True,
    )
    subprocess.run(["git", "-C", str(worktree_root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(worktree_root), "commit", "-qm", "fixture"],
        check=True,
    )


def test_lint_imports_reuses_parse_cache(tmp_path: Path) -> None:
    src_root = tmp_path / "src"
    module_path = src_root / "polisyos" / "ir" / "sample.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("from typing import TYPE_CHECKING\n", encoding="utf-8")

    policy = tmp_path / "import_policy.toml"
    _write_policy(policy, src_root)
    cache_dir = tmp_path / "cache"

    first_output = tmp_path / "first.json"
    first_exit = lint_imports.main(
        [
            "--policy",
            str(policy),
            "--exceptions",
            str(tmp_path / "missing_exceptions.toml"),
            "--cache-dir",
            str(cache_dir),
            "--output-format",
            "json",
            "--output",
            str(first_output),
        ]
    )
    second_output = tmp_path / "second.json"
    second_exit = lint_imports.main(
        [
            "--policy",
            str(policy),
            "--exceptions",
            str(tmp_path / "missing_exceptions.toml"),
            "--cache-dir",
            str(cache_dir),
            "--output-format",
            "json",
            "--output",
            str(second_output),
        ]
    )

    first_payload = json.loads(first_output.read_text(encoding="utf-8"))
    second_payload = json.loads(second_output.read_text(encoding="utf-8"))
    assert first_exit == 0
    assert second_exit == 0
    assert first_payload["data"]["cache_misses"] >= 1
    assert first_payload["data"]["cache_hits"] == 0
    assert second_payload["data"]["cache_hits"] >= 1


def test_lint_imports_changed_only_skips_without_python_changes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    src_root = tmp_path / "src"
    module_path = src_root / "polisyos" / "ir" / "sample.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("from typing import TYPE_CHECKING\n", encoding="utf-8")

    policy = tmp_path / "import_policy.toml"
    _write_policy(policy, src_root)
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        lint_imports,
        "_git_changed_files_fail_closed",
        lambda *args, **kwargs: [],
    )

    exit_code = lint_imports.main(
        [
            "--policy",
            str(policy),
            "--exceptions",
            str(tmp_path / "missing_exceptions.toml"),
            "--changed-only",
            "--output-format",
            "json",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["status"] == "skipped"
    assert payload["data"]["changed_file_count"] == 0


def test_lint_imports_changed_only_resolves_nested_product_paths(tmp_path: Path) -> None:
    worktree_root = tmp_path / "repo"
    product_root = worktree_root / "policy-engine"
    src_root = product_root / "src"
    module_path = src_root / "polisyos" / "ir" / "sample.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("import pandas\n", encoding="utf-8")

    policy = product_root / "architecture" / "imports" / "policy.toml"
    policy.parent.mkdir(parents=True)
    _write_policy(policy, src_root)
    _commit_git_fixture(worktree_root)
    policy.write_text(policy.read_text(encoding="utf-8") + "# sentinel change\n", encoding="utf-8")

    output = tmp_path / "report.json"
    exit_code = lint_imports.main(
        [
            "--policy",
            str(policy),
            "--exceptions",
            str(product_root / "architecture" / "imports" / "missing.toml"),
            "--changed-only",
            "--git-base-ref",
            "HEAD",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--output-format",
            "json",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["data"]["scan_mode"] == "full"
    assert payload["data"]["violation_count"] == 1


def test_lint_imports_changed_only_normalizes_nested_source_path(tmp_path: Path) -> None:
    worktree_root = tmp_path / "repo"
    product_root = worktree_root / "policy-engine"
    src_root = product_root / "src"
    module_path = src_root / "polisyos" / "ir" / "sample.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("from typing import TYPE_CHECKING\n", encoding="utf-8")

    policy = product_root / "architecture" / "imports" / "policy.toml"
    policy.parent.mkdir(parents=True)
    _write_policy(policy, src_root)
    _commit_git_fixture(worktree_root)
    module_path.write_text("import pandas\n", encoding="utf-8")

    output = tmp_path / "report.json"
    exit_code = lint_imports.main(
        [
            "--policy",
            str(policy),
            "--exceptions",
            str(product_root / "architecture" / "imports" / "missing.toml"),
            "--changed-only",
            "--git-base-ref",
            "HEAD",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--output-format",
            "json",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["data"]["scan_mode"] == "changed-only"
    assert payload["data"]["changed_file_count"] == 1
    assert payload["data"]["violation_count"] == 1
    assert payload["messages"][0]["message"].startswith(
        "src/polisyos/ir/sample.py:1 [ARCH002]"
    )


def test_lint_imports_changed_only_rejects_unresolvable_base_ref(tmp_path: Path) -> None:
    worktree_root = tmp_path / "repo"
    src_root = worktree_root / "policy-engine" / "src"
    module_path = src_root / "polisyos" / "ir" / "sample.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("from typing import TYPE_CHECKING\n", encoding="utf-8")
    policy = worktree_root / "policy-engine" / "import_policy.toml"
    policy.parent.mkdir(parents=True, exist_ok=True)
    _write_policy(policy, src_root)
    subprocess.run(["git", "init", "-q", str(worktree_root)], check=True)

    output = tmp_path / "report.json"
    exit_code = lint_imports.main(
        [
            "--policy",
            str(policy),
            "--exceptions",
            str(tmp_path / "missing.toml"),
            "--changed-only",
            "--git-base-ref",
            "does-not-exist",
            "--output-format",
            "json",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert payload["status"] == "failed"
    assert payload["summary"].endswith(
        "changed-only Git base ref is not a commit: does-not-exist"
    )


def test_changed_only_converts_later_git_launch_error_to_gate_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def _run(args, **kwargs):
        if "diff" in args:
            raise OSError("synthetic launch failure")
        if "--show-toplevel" in args:
            return subprocess.CompletedProcess(args, 0, stdout=f"{tmp_path}\n", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="fixture-commit\n", stderr="")

    monkeypatch.setattr(lint_imports.subprocess, "run", _run)

    with pytest.raises(
        ValueError,
        match="changed-only Git command failed: synthetic launch failure",
    ):
        lint_imports._git_changed_files_fail_closed(tmp_path, base_ref="HEAD")


@pytest.mark.parametrize(
    ("failing_command", "stderr", "expected"),
    [
        ("diff", "synthetic diff error", "changed-only Git diff failed: synthetic diff error"),
        (
            "ls-files",
            "synthetic ls-files error",
            "changed-only Git untracked-file census failed: synthetic ls-files error",
        ),
    ],
)
def test_changed_only_rejects_indeterminate_git_census(
    tmp_path: Path,
    monkeypatch,
    failing_command: str,
    stderr: str,
    expected: str,
) -> None:
    def _run(args, **kwargs):
        if "--show-toplevel" in args:
            return subprocess.CompletedProcess(args, 0, stdout=f"{tmp_path}\n", stderr="")
        if failing_command in args:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr=stderr)
        return subprocess.CompletedProcess(args, 0, stdout="fixture-commit\n", stderr="")

    monkeypatch.setattr(lint_imports.subprocess, "run", _run)

    with pytest.raises(ValueError) as exc_info:
        lint_imports._git_changed_files_fail_closed(tmp_path, base_ref="HEAD")
    assert str(exc_info.value) == expected


def test_lint_imports_fix_canonicalizes_exceptions_and_persists_baseline(tmp_path: Path) -> None:
    src_root = tmp_path / "src"
    module_path = src_root / "polisyos" / "ir" / "sample.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("from typing import TYPE_CHECKING\n", encoding="utf-8")

    policy = tmp_path / "import_policy.toml"
    _write_policy(policy, src_root)
    exceptions = tmp_path / "import_exceptions.toml"
    _write_valid_exceptions(exceptions)

    cache_dir = tmp_path / "cache"
    first_output = tmp_path / "first.json"
    first_exit = lint_imports.main(
        [
            "--policy",
            str(policy),
            "--exceptions",
            str(exceptions),
            "--fix",
            "--cache-dir",
            str(cache_dir),
            "--skip-if-unchanged",
            "--baseline-label",
            "ci",
            "--output-format",
            "json",
            "--output",
            str(first_output),
        ]
    )

    second_output = tmp_path / "second.json"
    second_exit = lint_imports.main(
        [
            "--policy",
            str(policy),
            "--exceptions",
            str(exceptions),
            "--cache-dir",
            str(cache_dir),
            "--skip-if-unchanged",
            "--baseline-label",
            "ci",
            "--output-format",
            "json",
            "--output",
            str(second_output),
        ]
    )

    first_payload = json.loads(first_output.read_text(encoding="utf-8"))
    second_payload = json.loads(second_output.read_text(encoding="utf-8"))
    expected_toml = lint_imports._canonical_exception_file(lint_imports.read_exceptions(exceptions))

    assert first_exit == 0
    assert second_exit == 0
    assert first_payload["data"]["fixes_applied"] == 1
    assert exceptions.read_text(encoding="utf-8") == expected_toml
    assert second_payload["status"] == "skipped"


def test_lint_foundry_fix_removes_standalone_print(tmp_path: Path) -> None:
    repo_root = tmp_path
    foundry_file = repo_root / "src" / "polisyos" / "foundry" / "demo.py"
    foundry_file.parent.mkdir(parents=True)
    foundry_file.write_text("print('debug')\nvalue = 1\n", encoding="utf-8")
    output = tmp_path / "foundry.json"

    exit_code = lint_foundry.main(
        [
            "--repo-root",
            str(repo_root),
            "--fix",
            "--output-format",
            "json",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["data"]["applied_fix_count"] == 1
    assert "print" not in foundry_file.read_text(encoding="utf-8")
    assert any(rule.rule_id == "foundry.banned-builtin-call" for rule in iter_rules("foundry."))


def test_lint_foundry_reports_unfixed_banned_import(tmp_path: Path) -> None:
    repo_root = tmp_path
    foundry_file = repo_root / "src" / "polisyos" / "foundry" / "demo.py"
    foundry_file.parent.mkdir(parents=True)
    foundry_file.write_text("import pandas\n", encoding="utf-8")
    output = tmp_path / "foundry.json"

    exit_code = lint_foundry.main(
        [
            "--repo-root",
            str(repo_root),
            "--output-format",
            "json",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["status"] == "failed"
    assert payload["messages"][0]["rule_id"] == "foundry.banned-import-root"


def test_gen_schema_changed_only_skips_without_selected_entry_changes(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    class DemoModel(BaseModel):
        schema_version: str = "1.0"
        value: int

    source_path = tmp_path / "src" / "polisyos" / "ir" / "demo_model.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("class DemoModel:\n    pass\n", encoding="utf-8")
    entry = ABIModelEntry(
        abi_key="demo_model",
        fqn="demo.models.DemoModel",
        module="ir",
        schema_file="demo_model.schema.json",
        priority=Priority.P1,
        compat_mode=CompatMode.STRICT,
        version_field="schema_version",
        lifecycle=Lifecycle.ACTIVE,
    )
    resolved = gen_schema.ResolvedABIEntry(
        entry=entry,
        cls=DemoModel,
        source_path=source_path,
        source_hash=gen_schema.file_sha256(source_path),
    )

    monkeypatch.setattr(gen_schema, "select_abi_entries", lambda *args, **kwargs: [entry])
    monkeypatch.setattr(gen_schema, "_resolve_entries", lambda entries: (resolved,))
    monkeypatch.setattr(gen_schema, "generate_reference_docs", lambda check: [])
    monkeypatch.setattr(gen_schema, "git_changed_files", lambda *args, **kwargs: [])

    exit_code = gen_schema.main(
        [
            "--output-dir",
            str(tmp_path / "snapshots"),
            "--changed-only",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "skipped" in captured.out.lower()


def test_gen_schema_persists_baseline_and_skips_unchanged_run(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    class DemoModel(BaseModel):
        schema_version: str = "1.0"
        value: int

    source_path = tmp_path / "src" / "polisyos" / "ir" / "demo_model.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("class DemoModel:\n    pass\n", encoding="utf-8")
    entry = ABIModelEntry(
        abi_key="demo_model",
        fqn="demo.models.DemoModel",
        module="ir",
        schema_file="demo_model.schema.json",
        priority=Priority.P1,
        compat_mode=CompatMode.STRICT,
        version_field="schema_version",
        lifecycle=Lifecycle.ACTIVE,
    )
    resolved = gen_schema.ResolvedABIEntry(
        entry=entry,
        cls=DemoModel,
        source_path=source_path,
        source_hash=gen_schema.file_sha256(source_path),
    )

    monkeypatch.setattr(gen_schema, "select_abi_entries", lambda *args, **kwargs: [entry])
    monkeypatch.setattr(gen_schema, "_resolve_entries", lambda entries: (resolved,))
    monkeypatch.setattr(gen_schema, "generate_reference_docs", lambda check: [])

    cache_dir = tmp_path / "cache"
    first_exit = gen_schema.main(
        [
            "--output-dir",
            str(tmp_path / "snapshots"),
            "--cache-dir",
            str(cache_dir),
            "--baseline-label",
            "ci",
            "--skip-if-unchanged",
        ]
    )
    first_output = capsys.readouterr().out

    second_exit = gen_schema.main(
        [
            "--output-dir",
            str(tmp_path / "snapshots"),
            "--cache-dir",
            str(cache_dir),
            "--baseline-label",
            "ci",
            "--skip-if-unchanged",
        ]
    )
    second_output = capsys.readouterr().out

    assert first_exit == 0
    assert second_exit == 0
    assert "Generated ABI schema snapshots" in first_output
    assert "skipped" in second_output.lower()


def test_abi_diff_matches_alias_based_renames() -> None:
    baseline_only = {
        "ir:legacy_name": abi_diff.ModelSnapshot(
            abi_key="legacy_name",
            module="ir",
            schema_path=Path("baseline.schema.json"),
            schema={"type": "object", "properties": {"value": {"type": "string"}}},
            schema_version="1.0",
            priority="p1",
            compat_mode="strict",
            version_field="schema_version",
            aliases=(),
            lifecycle="active",
            sha256_full="legacy-full",
            sha256_semantic="legacy-semantic",
        )
    }
    current_only = {
        "ir:current_name": abi_diff.ModelSnapshot(
            abi_key="current_name",
            module="ir",
            schema_path=Path("current.schema.json"),
            schema={"type": "object", "properties": {"value": {"type": "string"}}},
            schema_version="2.0",
            priority="p1",
            compat_mode="strict",
            version_field="schema_version",
            aliases=("legacy_name",),
            lifecycle="active",
            sha256_full="current-full",
            sha256_semantic="current-semantic",
        )
    }

    matches = abi_diff._match_renamed_models(
        baseline_only=baseline_only,
        current_only=current_only,
    )

    assert len(matches) == 1
    assert matches[0][2] == "alias"
