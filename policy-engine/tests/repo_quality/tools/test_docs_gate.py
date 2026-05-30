from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tools.cli import main as cli_main
from tools.quality.validation import check_docs_accuracy
from tools.quality.validation.check_docs_gate import build_gate_plan, normalize_changed_paths
from tools.quality.validation.check_docstring_quality import (
    DocstringSubject,
    TargetRef,
    filter_subjects_by_prefix,
    inspect_public_subjects,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _command_keys(plan) -> set[str]:
    return {command.key for command in plan.commands}


def _finding_ids(plan) -> set[str]:
    return {finding.rule_id for finding in plan.findings}


def test_runtime_http_changes_require_runtime_api_evidence() -> None:
    plan = build_gate_plan(("src/polisyos/runtime/http/app.py",))

    assert "runtime_api" in _command_keys(plan)
    assert "runtime_api_evidence" in _finding_ids(plan)
    runtime_command = next(command for command in plan.commands if command.key == "runtime_api")
    assert "--skip-client-drift" not in runtime_command.argv


def test_changed_paths_normalize_nested_product_root(tmp_path: Path) -> None:
    outer = tmp_path / "checkout"
    repo_root = outer / "policy-engine"
    repo_root.mkdir(parents=True)
    subprocess.run(
        ["git", "init"],  # noqa: S607
        cwd=outer,
        check=True,
        capture_output=True,
        text=True,
    )

    normalized = normalize_changed_paths(
        repo_root,
        (
            "policy-engine/src/polisyos/runtime/http/app.py",
            "docs/reference/api/index.md",
        ),
    )

    assert normalized == (
        "docs/reference/api/index.md",
        "src/polisyos/runtime/http/app.py",
    )


def test_runtime_http_openapi_snapshot_counts_as_runtime_evidence() -> None:
    plan = build_gate_plan(
        (
            "src/polisyos/runtime/http/app.py",
            "schemas/runtime_api_v1.openapi.json",
        )
    )

    assert "runtime_api" in _command_keys(plan)
    assert "runtime_api_evidence" not in _finding_ids(plan)


def test_docstring_gate_scopes_non_facade_changes_to_leaf_modules() -> None:
    plan = build_gate_plan(
        (
            "src/polisyos/runtime/http/app.py",
            "src/polisyos/scientist/governance/pass_entrypoints.py",
            "schemas/runtime_api_v1.openapi.json",
        )
    )
    docstring_command = next(
        command for command in plan.commands if command.key == "semantic_docstrings"
    )

    assert "polisyos.runtime.http.app" in docstring_command.argv
    assert "polisyos.runtime" not in docstring_command.argv
    assert "polisyos.runtime.http" not in docstring_command.argv
    assert "polisyos.scientist.governance.pass_entrypoints" not in docstring_command.argv


def test_facade_changes_require_guardrails_docstrings_and_matching_readme() -> None:
    missing_readme = build_gate_plan(("src/polisyos/runtime/__init__.py",))
    with_readme = build_gate_plan(
        (
            "src/polisyos/runtime/__init__.py",
            "src/polisyos/runtime/README.md",
        )
    )

    assert {"public_surface", "semantic_docstrings"} <= _command_keys(missing_readme)
    assert "readme_freshness" in _finding_ids(missing_readme)
    assert "readme_freshness" not in _finding_ids(with_readme)

    docstring_command = next(
        command for command in with_readme.commands if command.key == "semantic_docstrings"
    )
    assert "--module-prefix" in docstring_command.argv
    assert "polisyos.runtime" in docstring_command.argv


def test_security_sensitive_changes_require_docs_and_runbook_evidence() -> None:
    missing_evidence = build_gate_plan(("src/polisyos/core/security/authz.py",))
    with_evidence = build_gate_plan(
        (
            "src/polisyos/core/security/authz.py",
            "docs/reference/security-compliance.md",
            "docs/runbooks/key-rotation.md",
        )
    )

    assert {"security_docs", "security_runbooks"} <= _finding_ids(missing_evidence)
    assert "security_docs" not in _finding_ids(with_evidence)
    assert "security_runbooks" not in _finding_ids(with_evidence)


def test_frontend_api_client_changes_run_contract_check_and_require_docs() -> None:
    missing_docs = build_gate_plan(("packages/runtime-api-client/runtimeApiClient.ts",))
    with_docs = build_gate_plan(
        (
            "packages/runtime-api-client/runtimeApiClient.ts",
            "packages/runtime-api-client/README.md",
        )
    )

    assert "runtime_api" in _command_keys(missing_docs)
    assert "frontend_docs" in _finding_ids(missing_docs)
    assert "runtime_api" in _command_keys(with_docs)
    assert "frontend_docs" not in _finding_ids(with_docs)


def test_production_quality_maturity_reference_is_published_in_nav() -> None:
    nav_source = (
        REPO_ROOT / "architecture" / "tooling" / "mkdocs" / "nav" / "30-reference.yml"
    )

    assert (
        "Production Quality Maturity: reference/runtime/production-quality-maturity.md"
        in nav_source.read_text(encoding="utf-8")
    )


def test_docs_accuracy_rejects_planning_docs_in_nav(tmp_path: Path) -> None:
    repo_root = tmp_path
    docs_root = repo_root / "docs"
    docs_root.mkdir()
    (repo_root / "mkdocs.yml").write_text(
        "\n".join(
            [
                "site_name: Demo",
                "nav:",
                "  - Planning: SCIENTIST_AUDIT_REMEDIATION_PLAN.md",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (docs_root / "SCIENTIST_AUDIT_REMEDIATION_PLAN.md").write_text("# Plan\n", encoding="utf-8")

    if check_docs_accuracy.yaml is None:
        pytest.skip("PyYAML is not installed in this test environment")

    _, violations = check_docs_accuracy.published_docs_config(repo_root)

    assert any("planning/remediation document" in violation.message for violation in violations)


def test_docs_command_check_fails_on_drift(tmp_path: Path, capsys) -> None:
    output = tmp_path / "tools-reference.md"
    output.write_text("stale\n", encoding="utf-8")

    exit_code = cli_main(["docs", "--check", "--output", str(output)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Generated docs drift detected" in captured.err


def test_docstring_filter_scopes_subjects_to_requested_prefixes(tmp_path: Path) -> None:
    matching = DocstringSubject(
        ref=TargetRef(module="polisyos.runtime.http.app", qualname="create_runtime_api_app"),
        file_path=tmp_path / "runtime.py",
        lineno=1,
        kind="function",
        source="facade",
        docstring="Create the runtime API app for tests.",
        pragma_allowed=False,
    )
    non_matching = DocstringSubject(
        ref=TargetRef(module="polisyos.foundry._quickstart", qualname="QuickstartRunResult"),
        file_path=tmp_path / "foundry.py",
        lineno=1,
        kind="class",
        source="docs:reference/foundry/compile-execute.md",
        docstring="Result of a foundry quickstart run.",
        pragma_allowed=False,
    )

    filtered = filter_subjects_by_prefix(
        [matching, non_matching],
        ["polisyos.runtime", "polisyos.runtime.http"],
    )

    assert filtered == [matching]


def test_docstring_quality_resolves_reexported_submodule_without_recursion(
    tmp_path: Path,
) -> None:
    src_root = tmp_path / "src"
    docs_root = tmp_path / "docs" / "reference"
    package_root = src_root / "polisyos" / "example"
    docs_root.mkdir(parents=True)
    package_root.mkdir(parents=True)
    (src_root / "polisyos" / "__init__.py").write_text(
        '"""Root package used by the docstring-quality regression test."""\n',
        encoding="utf-8",
    )
    (package_root / "__init__.py").write_text(
        '"""Example facade package."""\n'
        "from . import foo\n\n"
        "__all__ = ['foo']\n",
        encoding="utf-8",
    )
    (package_root / "foo.py").write_text(
        '"""Foo submodule with semantic documentation."""\n',
        encoding="utf-8",
    )

    subjects = inspect_public_subjects(docs_root=docs_root, src_root=src_root)

    assert any(subject.ref.fqname == "polisyos.example.foo" for subject in subjects)
