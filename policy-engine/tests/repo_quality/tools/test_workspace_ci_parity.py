# ruff: noqa: S101, TC001, TC002

from __future__ import annotations

from pathlib import Path

import pytest

from tools.devx.workspace import ci_parity, repository_sota_closeout, verify
from tools.devx.workspace._common import CommandSpec

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = REPO_ROOT.parent


def _labels_for(module: object, argv: list[str], monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[CommandSpec] = []

    monkeypatch.setattr(module, "uv_command", lambda: ("uv",), raising=False)
    monkeypatch.setattr(module, "run_command", lambda spec: seen.append(spec), raising=False)

    assert module.main(argv) == 0
    return [spec.label for spec in seen]


def test_workspace_verify_owns_fast_last_mile_gates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[CommandSpec] = []
    monkeypatch.setattr(verify, "uv_command", lambda: ("uv",), raising=False)
    monkeypatch.setattr(verify, "run_command", lambda spec: seen.append(spec), raising=False)

    assert verify.main(["--backend-only", "--skip-doctor", "--pytest-workers", "1"]) == 0
    labels = [spec.label for spec in seen]
    argv_by_label = {spec.label: spec.argv for spec in seen}

    assert argv_by_label["lint foundry"] == (
        "uv",
        "run",
        "python",
        "-m",
        "tools.quality.lint.lint_foundry",
        "--repo-root",
        ".",
    )

    for spec in seen:
        assert "tools/quality/lint/lint_foundry.py" not in spec.argv

    assert "check package import gates (shell-package closure)" in labels
    assert "check last-mile inventory baseline" in labels
    assert "build honest diagnostics coverage dashboard" in labels
    assert "check extension example contract coverage" in labels
    assert "check schemas pure-data closure" in labels
    assert "Last-mile fail-fast gates:" in verify._build_parser().format_help()


def test_workspace_verify_owns_fast_last_mile_gate_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    labels = _labels_for(
        verify,
        ["--backend-only", "--skip-doctor", "--pytest-workers", "1"],
        monkeypatch,
    )

    assert "check package import gates (shell-package closure)" in labels
    assert "check last-mile inventory baseline" in labels
    assert "build honest diagnostics coverage dashboard" in labels
    assert "check extension example contract coverage" in labels
    assert "check schemas pure-data closure" in labels
    assert "Last-mile fail-fast gates:" in verify._build_parser().format_help()


def test_workspace_ci_parity_owns_broad_last_mile_policy_gates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    labels = _labels_for(
        ci_parity,
        [
            "--backend-only",
            "--skip-doctor",
            "--skip-runtime-http",
        ],
        monkeypatch,
    )

    assert "verify backend fast gate" in labels
    assert "check directory health ratchet" in labels
    assert "check test ratchets and helper topology" in labels
    assert "check architecture phase6-1 report-only contracts" in labels
    assert "check validator module-size budget" in labels
    assert "check extension example installability" in labels
    assert "check ADR thematic index freshness" in labels
    assert "Last-mile CI-parity gates:" in ci_parity._build_parser().format_help()


def test_repository_sota_closeout_declares_final_acceptance_owners() -> None:
    owner_by_gate = {
        gate["id"]: gate["owner"] for gate in repository_sota_closeout.LAST_MILE_GATE_OWNERSHIP
    }

    assert {
        "repository-structure",
        "repository-last-mile-inventory",
        "shell-package-closure",
        "directory-health",
        "test-ratchets-helper-topology",
        "dead-overrides",
        "extension-examples",
        "adr-thematic-index",
        "validator-module-size",
        "schema-purity",
        "operability-release",
        "compatibility-release",
        "acceptance-audit",
    } <= set(owner_by_gate)
    assert owner_by_gate["repository-last-mile-inventory"] == "workspace verify"
    assert owner_by_gate["directory-health"] == "workspace ci-parity"
    assert owner_by_gate["operability-release"] == "release workflow"


def test_last_mile_ci_precommit_and_docs_reachability_are_documented() -> None:
    abi = (WORKSPACE_ROOT / ".github" / "workflows" / "abi.yml").read_text(encoding="utf-8")
    ci = (WORKSPACE_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    release = (WORKSPACE_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    pre_commit = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    quality_gates = (REPO_ROOT / "docs" / "reference" / "quality-gates.md").read_text(
        encoding="utf-8"
    )

    assert "repository_last_mile_inventory.py" in abi
    assert "generate_adr_index.py --check" in abi
    assert "schemas-python-residue.txt" in abi
    assert "architecture_report_only_contracts.py --report module-size" in abi
    assert "directory_health.py" in ci
    assert "report_test_ratchets.py" in ci
    assert "--fail-on-regression" in ci
    assert "check-compatibility-release-gates" in release
    assert "repository_last_mile_inventory.py --check" in pre_commit
    assert "generate_adr_index.py --check" in pre_commit
    assert "schemas-python-residue.txt" in pre_commit

    for gate_name in (
        "repository_last_mile_inventory.py",
        "check_extension_examples.py",
        "generate_adr_index.py",
        "architecture_report_only_contracts.py",
        "schema purity",
        "operability bundle",
        "shell-package",
        "helper topology",
        "cross-cutting/name-collision",
    ):
        assert gate_name in quality_gates
