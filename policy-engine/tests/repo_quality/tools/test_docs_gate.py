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


@pytest.mark.parametrize(
    "path",
    [
        "architecture/tooling/mkdocs/nav/30-reference.yml",
        "architecture/tooling/mkdocs/base.yml",
        "architecture/tooling/mkdocs/validation.yml",
        "architecture/tooling/mkdocs/exclude_docs.yml",
        "architecture/tooling/mkdocs/generated.yml",
        "mkdocs.yml",
    ],
)
def test_publication_config_changes_run_accuracy_and_strict_build(path: str) -> None:
    plan = build_gate_plan((path,))

    assert tuple(command.key for command in plan.commands) == (
        "docs_lifecycle",
        "tool_configs",
        "docs_accuracy",
        "strict_docs_build",
    )
    assert plan.findings == ()


@pytest.mark.parametrize(
    "path",
    [
        "architecture/tooling/ruff/workspace_root.toml",
        "architecture/tooling/mypy/workspace_root.ini",
        "architecture/tooling/tool_config_split.toml",
    ],
)
def test_unrelated_tooling_config_changes_keep_their_existing_gate_plan(path: str) -> None:
    plan = build_gate_plan((path,))

    assert tuple(command.key for command in plan.commands) == ("tool_configs",)
    assert plan.findings == ()


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


@pytest.mark.parametrize(
    "path",
    [
        "tools/research/demos/run_mechanism_design.py",
        "tools/devx/workspace/assign_candidate.py",
        "tools/design/check-composition-rules.ts",
    ],
)
def test_security_gate_does_not_match_security_terms_inside_unrelated_words(path: str) -> None:
    plan = build_gate_plan((path,))

    assert "security_docs" not in _finding_ids(plan)
    assert "security_runbooks" not in _finding_ids(plan)


@pytest.mark.parametrize(
    "path",
    [
        "src/polisyos/runtime/http/routes/auth.py",
        "src/polisyos/fabric/storage/tenant_cas.py",
        "src/polisyos/core/audit/verifier.py",
        "src/polisyos/core/artifacts/signing.py",
        "tools/devx/foundry/update_signature_baseline.py",
        "src/polisyos/data_forge/read_api/compliance.py",
    ],
)
def test_security_gate_keeps_lexical_security_path_tokens(path: str) -> None:
    plan = build_gate_plan((path,))

    assert "security_docs" in _finding_ids(plan)
    assert "security_runbooks" in _finding_ids(plan)


def test_frontend_api_client_changes_run_contract_check_and_require_docs() -> None:
    missing_docs = build_gate_plan(("packages/runtime-api-client/canonicalRuntimeApiClient.ts",))
    with_docs = build_gate_plan(
        (
            "packages/runtime-api-client/canonicalRuntimeApiClient.ts",
            "packages/runtime-api-client/README.md",
        )
    )

    assert "runtime_api" in _command_keys(missing_docs)
    assert "frontend_docs" in _finding_ids(missing_docs)
    assert "runtime_api" in _command_keys(with_docs)
    assert "frontend_docs" not in _finding_ids(with_docs)


def test_production_quality_maturity_reference_is_published_in_nav() -> None:
    nav_source = REPO_ROOT / "architecture" / "tooling" / "mkdocs" / "nav" / "30-reference.yml"

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


def test_docs_accuracy_follows_mkdocs_inherit_for_published_nav(tmp_path: Path) -> None:
    repo_root = tmp_path
    docs_root = repo_root / "docs" / "reference"
    generated_config = repo_root / "architecture" / "tooling" / "mkdocs" / "generated.yml"
    docs_root.mkdir(parents=True)
    generated_config.parent.mkdir(parents=True)
    (repo_root / "mkdocs.yml").write_text(
        "INHERIT: architecture/tooling/mkdocs/generated.yml\n",
        encoding="utf-8",
    )
    (docs_root / "generated-artifacts.md").write_text(
        "# Generated Artifacts\n\nCanonical regeneration commands:\n",
        encoding="utf-8",
    )
    generated_config.write_text(
        "\n".join(
            [
                "site_name: Demo",
                "site_url: https://example.test/docs/",
                "nav:",
                "  - Reference:",
                "      - reference/generated-artifacts.md",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    if check_docs_accuracy.yaml is None:
        pytest.skip("PyYAML is not installed in this test environment")

    config, violations = check_docs_accuracy.published_docs_config(repo_root)

    assert violations == []
    assert config.site_url == "https://example.test/docs/"
    assert (docs_root / "generated-artifacts.md").resolve() in config.published_files


def test_docs_accuracy_treats_not_in_nav_as_publishable(tmp_path: Path) -> None:
    repo_root = tmp_path
    docs_root = repo_root / "docs" / "reference"
    generated_config = repo_root / "architecture" / "tooling" / "mkdocs" / "generated.yml"
    docs_root.mkdir(parents=True)
    generated_config.parent.mkdir(parents=True)
    (repo_root / "mkdocs.yml").write_text(
        "INHERIT: architecture/tooling/mkdocs/generated.yml\n",
        encoding="utf-8",
    )
    (docs_root / "generated-artifacts.md").write_text(
        "# Generated Artifacts\n\nCanonical regeneration commands:\n",
        encoding="utf-8",
    )
    generated_config.write_text(
        "\n".join(
            [
                "site_name: Demo",
                "not_in_nav: |",
                "  reference/generated-artifacts.md",
                "nav:",
                "  - Reference:",
                "      - reference/index.md",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (docs_root / "index.md").write_text("# Reference\n", encoding="utf-8")

    if check_docs_accuracy.yaml is None:
        pytest.skip("PyYAML is not installed in this test environment")

    config, violations = check_docs_accuracy.published_docs_config(repo_root)

    assert violations == []
    assert (docs_root / "generated-artifacts.md").resolve() in config.published_files


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
        ref=TargetRef(
            module="polisyos.foundry._internal.quickstart", qualname="QuickstartRunResult"
        ),
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
        '"""Example facade package."""\nfrom . import foo\n\n__all__ = [\'foo\']\n',
        encoding="utf-8",
    )
    (package_root / "foo.py").write_text(
        '"""Foo submodule with semantic documentation."""\n',
        encoding="utf-8",
    )

    subjects = inspect_public_subjects(docs_root=docs_root, src_root=src_root)

    assert any(subject.ref.fqname == "polisyos.example.foo" for subject in subjects)


def test_docs_selector_prunes_excluded_subtrees_before_walking_and_keeps_included_boundary(
    tmp_path: Path, monkeypatch
) -> None:
    import os

    import mkdocs.structure.files as mkdocs_files

    docs_root = tmp_path / "docs"
    research = docs_root / "research"
    (docs_root / "reference").mkdir(parents=True)
    (research / "deep").mkdir(parents=True)
    (docs_root / "index.md").write_text("# Index\n", encoding="utf-8")
    (docs_root / "reference" / "boundary.md").write_text("# Boundary\n", encoding="utf-8")
    (docs_root / "reference" / "unlisted.md").write_text("# Unlisted\n", encoding="utf-8")
    (docs_root / ".hidden.md").write_text("# Hidden\n", encoding="utf-8")
    (docs_root / ".hidden").mkdir()
    (docs_root / ".hidden" / "secret.md").write_text("# Secret\n", encoding="utf-8")
    for group in range(12):
        folder = research / "deep" / f"group-{group:02d}"
        folder.mkdir()
        for index in range(24):
            (folder / f"record-{index:02d}.md").write_text("# excluded\n", encoding="utf-8")
    loop = research / "deep" / "loop"
    try:
        loop.symlink_to(research, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")

    (tmp_path / "mkdocs.yml").write_text(
        "site_name: Demo\n"
        "nav:\n"
        "  - index.md\n"
        "  - reference/boundary.md\n"
        "not_in_nav: |\n"
        "  reference/unlisted.md\n"
        "exclude_docs: |\n"
        "  research/**\n",
        encoding="utf-8",
    )

    real_walk = os.walk
    visited: list[str] = []

    def guarded_walk(top, *args, **kwargs):
        for source_dir, dirnames, filenames in real_walk(top, *args, **kwargs):
            source_path = Path(source_dir).resolve()
            if Path(top).resolve() == docs_root.resolve():
                assert not source_path.is_relative_to(research.resolve())
                visited.append(source_path.relative_to(docs_root.resolve()).as_posix())
            yield source_dir, dirnames, filenames

    monkeypatch.setattr(mkdocs_files.os, "walk", guarded_walk)
    config, violations = check_docs_accuracy.published_docs_config(tmp_path)

    assert violations == []
    assert set(config.published_files) == {
        (docs_root / "index.md").resolve(),
        (docs_root / "reference" / "boundary.md").resolve(),
        (docs_root / "reference" / "unlisted.md").resolve(),
    }
    assert config.not_in_nav_files == ((docs_root / "reference" / "unlisted.md").resolve(),)
    assert config.selection_summary["directory_pruning_enabled"] is True
    assert config.selection_summary["pruned_directories"] == 2
    assert config.selection_summary["pruned_directory_paths"] == [".hidden", "research"]
    assert config.selection_summary["traversed_parent_membership"] == [
        {
            "parent": ".",
            "child_directories_before_pruning": [".hidden", "reference", "research"],
        },
        {"parent": "reference", "child_directories_before_pruning": []},
    ]
    assert "files under traversed directories only" in config.selection_summary["enumeration_scope"]
    assert "included MkDocs files only" in config.selection_summary["containment_scope"]
    assert "research" not in visited
    assert "reference" in visited


def test_pruned_docs_walk_matches_mkdocs_on_negated_rules_and_inclusion_edges(
    tmp_path: Path,
) -> None:
    from mkdocs.config import load_config
    from mkdocs.structure.files import get_files

    docs_root = tmp_path / "docs"
    (docs_root / "private").mkdir(parents=True)
    (docs_root / "nested").mkdir()
    (docs_root / "index.md").write_text("# Index\n", encoding="utf-8")
    (docs_root / "README.md").write_text("# Readme landing page\n", encoding="utf-8")
    (docs_root / "private" / "hidden.md").write_text("# Hidden\n", encoding="utf-8")
    (docs_root / "private" / "published.md").write_text("# Published\n", encoding="utf-8")
    (docs_root / "nested" / "unlisted.md").write_text("# Not in nav\n", encoding="utf-8")
    (docs_root / ".hidden.md").write_text("# Hidden\n", encoding="utf-8")
    mkdocs_path = tmp_path / "mkdocs.yml"
    mkdocs_path.write_text(
        "site_name: Demo\n"
        "nav:\n"
        "  - index.md\n"
        "  - private/published.md\n"
        "not_in_nav: |\n"
        "  nested/unlisted.md\n"
        "exclude_docs: |\n"
        "  private/**\n",
        encoding="utf-8",
    )

    config = load_config(config_file=str(mkdocs_path))
    expected = get_files(config)
    actual, pruned_directory_paths, _, pruning_enabled = (
        check_docs_accuracy._get_files_pruning_excluded_dirs(config)
    )

    def published_signature(files):
        return {(file.src_uri, file.dest_uri) for file in files if file.inclusion.is_included()}

    def complete_signature(files):
        return {(file.src_uri, file.dest_uri, file.inclusion) for file in files}

    assert published_signature(actual) == published_signature(expected)
    assert pruning_enabled is True
    assert pruned_directory_paths == ("private",)

    mkdocs_path.write_text(
        "site_name: Demo\n"
        "nav:\n"
        "  - index.md\n"
        "  - private/published.md\n"
        "not_in_nav: |\n"
        "  nested/unlisted.md\n"
        "exclude_docs: |\n"
        "  private/**\n"
        "  !private/published.md\n",
        encoding="utf-8",
    )

    config = load_config(config_file=str(mkdocs_path))
    expected = get_files(config)
    actual, pruned_directory_paths, _, pruning_enabled = (
        check_docs_accuracy._get_files_pruning_excluded_dirs(config)
    )

    assert complete_signature(actual) == complete_signature(expected)
    assert pruning_enabled is False
    assert pruned_directory_paths == ()


def test_docs_selector_refuses_included_symlink_outside_docs_root(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    outside_file = tmp_path / "outside.md"
    outside_file.write_text("# Outside\n", encoding="utf-8")
    linked_file = docs_root / "linked.md"
    try:
        linked_file.symlink_to(outside_file)
    except OSError as exc:
        pytest.skip(f"file symlinks are unavailable: {exc}")
    (tmp_path / "mkdocs.yml").write_text(
        "site_name: Demo\nnav:\n  - linked.md\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="resolves outside the repository docs root"):
        check_docs_accuracy.published_docs_config(tmp_path)
