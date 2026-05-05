from __future__ import annotations

from pathlib import Path

import pytest
from tools.devx.workspace import (
    _repo_hygiene,
    bootstrap,
    docs_style,
    doctor,
    format_check,
    lint_fast,
    lint_full,
    python_base_basedpyright,
    python_base_mypy,
    verify,
)
from tools.devx.workspace._common import CommandSpec
from tools.devx.workspace._repo_hygiene import expand_markdown_files


def _spec(label: str, *argv: str) -> CommandSpec:
    return CommandSpec(label=label, argv=argv, cwd=Path("."))


def test_bootstrap_builds_expected_command_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[CommandSpec] = []

    monkeypatch.setattr(bootstrap, "_ensure_python_baseline", lambda: None)
    monkeypatch.setattr(bootstrap, "_ensure_uv_available", lambda *, allow_install: None)
    monkeypatch.setattr(bootstrap, "_ensure_node_baseline", lambda *, skip_frontend: None)
    monkeypatch.setattr(bootstrap, "uv_command", lambda: ("uv",))
    monkeypatch.setattr(bootstrap, "run_command", lambda spec: seen.append(spec))

    exit_code = bootstrap.main([])

    assert exit_code == 0
    assert [spec.label for spec in seen] == [
        "uv sync",
        "pre-commit install",
        "npm ci",
        "Playwright browser install",
        "doctor",
    ]


def test_doctor_lists_optional_surfaces(capsys) -> None:
    exit_code = doctor.main(["--list-surfaces"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "runtime-signing" in captured.out


def test_doctor_fails_for_missing_optional_surface_credentials(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    monkeypatch.setattr(doctor, "_check_python", lambda: doctor.CheckResult("python", True, "ok"))
    monkeypatch.setattr(doctor, "_check_node", lambda: doctor.CheckResult("node", True, "ok"))
    monkeypatch.setattr(doctor, "_check_uv", lambda: doctor.CheckResult("uv", True, "ok"))

    exit_code = doctor.main(
        [
            "--surface",
            "runtime-signing",
            "--skip-playwright",
            "--skip-lockfile-checks",
            "--skip-contract-checks",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "[FAIL] runtime-signing:" in captured.out


def test_verify_rejects_invalid_pytest_worker_setting() -> None:
    with pytest.raises(SystemExit, match="positive integer or 'auto'"):
        verify._resolve_pytest_workers("0")


def test_verify_backend_only_runs_backend_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[CommandSpec] = []

    monkeypatch.setattr(verify, "uv_command", lambda: ("uv",))
    monkeypatch.setattr(verify, "run_command", lambda spec: seen.append(spec))

    exit_code = verify.main(
        [
            "--backend-only",
            "--skip-doctor",
            "--pytest-workers",
            "2",
        ]
    )

    labels = [spec.label for spec in seen]
    assert exit_code == 0
    assert any(label.startswith("pytest fast backend gate") for label in labels)
    assert all(not label.startswith("npm ") for label in labels)


def test_expand_markdown_files_skips_docs_archive() -> None:
    files = expand_markdown_files(["docs"])

    assert "docs/plans/active/REPOSITORY_LINT_AND_FORMAT_PLAN.md" in files
    assert all(not file_path.startswith("docs/archive/") for file_path in files)


def test_pre_commit_hook_uses_git_root_relative_paths() -> None:
    spec = _repo_hygiene.pre_commit_hook(
        "markdownlint-cli2",
        label="markdownlint authored docs",
        files=["docs/plans/active/REPOSITORY_LINT_AND_FORMAT_PLAN.md"],
    )

    assert spec.cwd == _repo_hygiene.GIT_ROOT
    assert "--config" in spec.argv
    assert _repo_hygiene._workspace_relative(".pre-commit-config.yaml") in spec.argv
    assert (
        _repo_hygiene._workspace_relative("docs/plans/active/REPOSITORY_LINT_AND_FORMAT_PLAN.md")
        in spec.argv
    )


def test_pre_commit_install_uses_workspace_local_config() -> None:
    spec = _repo_hygiene.pre_commit_install()

    assert spec.cwd == _repo_hygiene.GIT_ROOT
    assert spec.label == "pre-commit install"
    assert spec.argv[-2:] == (
        "--config",
        _repo_hygiene._workspace_relative(".pre-commit-config.yaml"),
    )


def test_helm_chart_dirs_cover_ops_phase7_surface() -> None:
    assert _repo_hygiene.HELM_CHART_DIRS == (
        "ops/cloud/helm/keycloak",
        "ops/cloud/helm/polisyos-cell",
        "ops/cloud/helm/spire",
    )


def test_helm_lint_command_uses_chart_specific_lint_values() -> None:
    spec = _repo_hygiene.helm_lint_command("ops/cloud/helm/polisyos-cell")

    assert spec.argv == (
        "helm",
        "lint",
        "ops/cloud/helm/polisyos-cell",
        "-f",
        "ops/cloud/helm/polisyos-cell/values.lint.yaml",
    )


def test_pre_commit_plain_yaml_hooks_exclude_helm_templates() -> None:
    config_text = (_repo_hygiene.PRODUCT_ROOT / ".pre-commit-config.yaml").read_text(
        encoding="utf-8"
    )

    assert "id: check-yaml" in config_text
    assert "id: yamllint" in config_text
    assert "policy-engine/ops/cloud/helm/[^/]+/(" in config_text
    assert "templates/.*\\.(yaml|yml)$" in config_text
    assert "tests/.*\\.(yaml|yml)$" in config_text


def test_yamllint_ignores_helm_templated_yaml() -> None:
    config_text = (_repo_hygiene.PRODUCT_ROOT / ".yamllint").read_text(encoding="utf-8")

    assert "ops/cloud/helm/*/templates/" in config_text
    assert "ops/cloud/helm/*/tests/" in config_text


def test_docs_style_targets_specific_markdown_files(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[CommandSpec] = []

    monkeypatch.setattr(docs_style, "run_command", lambda spec: seen.append(spec))

    exit_code = docs_style.main(["docs/plans/active"])

    assert exit_code == 0
    assert seen[0].label == "markdownlint authored docs"
    assert "--files" in seen[0].argv
    assert (
        _repo_hygiene._workspace_relative("docs/plans/active/REPOSITORY_LINT_AND_FORMAT_PLAN.md")
        in seen[0].argv
    )


def test_format_check_skip_frontend_skip_rego(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[CommandSpec] = []

    monkeypatch.setattr(format_check, "run_command", lambda spec: seen.append(spec))
    monkeypatch.setattr(format_check, "ensure_executable", lambda *args, **kwargs: None)
    monkeypatch.setattr(format_check, "uv_run", lambda label, *argv, cwd=None: _spec(label, *argv))
    monkeypatch.setattr(
        format_check,
        "pre_commit_hook",
        lambda hook_id, *, label, files=None: _spec(label, hook_id),
    )

    exit_code = format_check.main(["--skip-frontend", "--skip-rego"])

    assert exit_code == 0
    assert [spec.label for spec in seen] == [
        "ruff format --check",
        "shfmt authored shell",
        "taplo format check",
    ]


def test_lint_fast_default_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[CommandSpec] = []

    monkeypatch.setattr(lint_fast, "run_command", lambda spec: seen.append(spec))
    monkeypatch.setattr(lint_fast, "ensure_executable", lambda *args, **kwargs: None)
    monkeypatch.setattr(lint_fast, "uv_run", lambda label, *argv, cwd=None: _spec(label, *argv))
    monkeypatch.setattr(lint_fast, "npm_run", lambda label, *argv: _spec(label, *argv))
    monkeypatch.setattr(
        lint_fast,
        "pre_commit_hook",
        lambda hook_id, *, label, files=None: _spec(label, hook_id),
    )

    exit_code = lint_fast.main([])

    assert exit_code == 0
    assert [spec.label for spec in seen] == [
        "ruff check",
        "npm lint",
        "markdownlint authored docs",
        "yamllint authored YAML",
        "shellcheck authored shell",
        "actionlint workflows",
    ]


def test_python_base_mypy_default_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[CommandSpec] = []

    monkeypatch.setattr(python_base_mypy, "run_command", lambda spec: seen.append(spec))
    monkeypatch.setattr(
        python_base_mypy, "uv_run", lambda label, *argv, cwd=None: _spec(label, *argv)
    )

    exit_code = python_base_mypy.main([])

    assert exit_code == 0
    assert [spec.label for spec in seen] == [
        "mypy common",
        "mypy ir",
        "mypy core",
    ]


def test_python_base_basedpyright_single_layer(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[CommandSpec] = []

    monkeypatch.setattr(python_base_basedpyright, "run_command", lambda spec: seen.append(spec))
    monkeypatch.setattr(
        python_base_basedpyright,
        "uv_run",
        lambda label, *argv, cwd=None: _spec(label, *argv),
    )

    exit_code = python_base_basedpyright.main(["--layer", "ir"])

    assert exit_code == 0
    assert [spec.label for spec in seen] == ["basedpyright ir"]


def test_lint_full_skip_policy_frontend_and_helm(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[CommandSpec] = []

    monkeypatch.setattr(lint_full, "run_command", lambda spec: seen.append(spec))
    monkeypatch.setattr(lint_full, "ensure_executable", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        lint_full,
        "workspace_command",
        lambda command, *, label, args=(): _spec(label, command, *args),
    )
    monkeypatch.setattr(lint_full, "npm_run", lambda label, *argv: _spec(label, *argv))
    monkeypatch.setattr(lint_full, "uv_run", lambda label, *argv, cwd=None: _spec(label, *argv))

    exit_code = lint_full.main(["--skip-frontend", "--skip-policy", "--skip-helm"])

    assert exit_code == 0
    assert [spec.label for spec in seen] == [
        "workspace lint-fast",
        "workspace format-check",
        "workspace python-base-mypy",
        "workspace python-base-basedpyright",
    ]


def test_lint_full_default_sequence_includes_helm_lint(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[CommandSpec] = []

    monkeypatch.setattr(lint_full, "run_command", lambda spec: seen.append(spec))
    monkeypatch.setattr(lint_full, "ensure_executable", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        lint_full,
        "workspace_command",
        lambda command, *, label, args=(): _spec(label, command, *args),
    )
    monkeypatch.setattr(lint_full, "npm_run", lambda label, *argv: _spec(label, *argv))
    monkeypatch.setattr(lint_full, "uv_run", lambda label, *argv, cwd=None: _spec(label, *argv))
    monkeypatch.setattr(
        lint_full,
        "helm_lint_command",
        lambda chart_path: _spec(f"helm lint {chart_path}", "helm", "lint", chart_path),
    )
    monkeypatch.setattr(
        lint_full,
        "HELM_CHART_DIRS",
        ("ops/cloud/helm/keycloak", "ops/cloud/helm/spire"),
    )

    exit_code = lint_full.main(["--skip-frontend", "--skip-types", "--skip-policy"])

    assert exit_code == 0
    assert [spec.label for spec in seen] == [
        "workspace lint-fast",
        "workspace format-check",
        "helm lint ops/cloud/helm/keycloak",
        "helm lint ops/cloud/helm/spire",
    ]


def test_lint_full_runs_opa_check_per_rego_root(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[CommandSpec] = []

    monkeypatch.setattr(lint_full, "run_command", lambda spec: seen.append(spec))
    monkeypatch.setattr(lint_full, "ensure_executable", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        lint_full,
        "workspace_command",
        lambda command, *, label, args=(): _spec(label, command, *args),
    )
    monkeypatch.setattr(lint_full, "uv_run", lambda label, *argv, cwd=None: _spec(label, *argv))
    monkeypatch.setattr(lint_full, "HELM_CHART_DIRS", ())
    monkeypatch.setattr(
        lint_full, "REGO_SCOPE", ("ops/policy/policies", "ops/cloud/helm/polisyos-cell/policies")
    )

    exit_code = lint_full.main(["--skip-frontend", "--skip-types"])

    assert exit_code == 0
    assert [spec.label for spec in seen] == [
        "workspace lint-fast",
        "workspace format-check",
        "opa check --strict ops/policy/policies",
        "opa check --strict ops/cloud/helm/polisyos-cell/policies",
        "opa test --fail-on-empty",
    ]
