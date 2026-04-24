from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from tools.quality.ci.check_workflow_policy import collect_findings
from tools.quality.testing import mutation
from tools.registry import LEGACY_ENTRYPOINTS, TOOL_SPECS_BY_KEY

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = REPO_ROOT / "tools"

HELP_SAFE_SCRIPT_WRAPPERS = (
    "acceptance-audit",
    "benchmark_lex_llm_steady_state.py",
    "benchmark_lex_llm_sweep.py",
    "bootstrap",
    "build_academic_gold_candidates.py",
    "build_expert_review_bundle.py",
    "ci-parity",
    "core-runtime-closeout",
    "doctor",
    "generate_stubs.py",
    "generate_wvs_registry.py",
    "record_fixtures.py",
    "remote-acceptance",
    "update_signature_baseline.py",
    "verify",
)

HELP_SAFE_BENCHMARK_WRAPPERS = (
    "build_release_summary.py",
    "prepare_real_benchmark_data.py",
)

LEGACY_SCRIPT_PATTERN = re.compile(r"(?:\\./scripts/)|(?<![\\w/.-])scripts/")


def test_registry_discovers_phase4_consolidation_commands() -> None:
    expected = {
        ("data", "build-academic-gold-candidates"),
        ("data", "build-expert-review-bundle"),
        ("data", "generate-wvs-registry"),
        ("data", "record-fixtures"),
        ("benchmarks", "run-all"),
        ("cloud", "deploy-to-server"),
        ("cloud", "prepare-shards"),
        ("cloud", "run-pipeline"),
        ("cloud", "run-datasets-validation"),
        ("foundry", "generate-stubs"),
        ("foundry", "update-signature-baseline"),
        ("testing", "mutation"),
    }

    missing = sorted(key for key in expected if key not in TOOL_SPECS_BY_KEY)
    assert missing == []
    assert TOOL_SPECS_BY_KEY[("cloud", "run-remaining-stages")].status.value == "deprecated"


def test_no_unmanifested_top_level_tool_directories_exist() -> None:
    allowed = {
        "_deprecated",
        "_lib",
        "devx",
        "quality",
        "ops",
        "research",
        "workspace",
        "architecture",
        "connectors",
        "foundry",
        "lint",
        "diagnostics",
        "validation",
        "testing",
        "ci",
        "cloud",
        "release",
        "migrations",
        "runtime",
        "data",
        "design",
        "ukraine_data",
        "calibration",
        "benchmarks",
        "demos",
        "__pycache__",
    }

    unexpected = sorted(
        path.name for path in TOOLS_ROOT.iterdir() if path.is_dir() and path.name not in allowed
    )
    assert unexpected == []


def test_workspace_shell_wrapper_routes_through_unified_cli() -> None:
    result = subprocess.run(  # noqa: S603 - trusted repo-local wrapper smoke test
        ["/bin/bash", str(REPO_ROOT / "scripts" / "bootstrap"), "--help"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "DEPRECATED:" in result.stderr
    assert "--profile" in result.stdout


@pytest.mark.parametrize("script_name", HELP_SAFE_SCRIPT_WRAPPERS)
def test_help_safe_script_wrappers_emit_deprecation_and_help(script_name: str) -> None:
    script_path = REPO_ROOT / "scripts" / script_name
    runner = (
        [sys.executable, str(script_path)]
        if script_name.endswith(".py")
        else ["bash", str(script_path)]
    )

    result = subprocess.run(  # noqa: S603 - trusted repo-local wrapper smoke test
        [*runner, "--help"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "DEPRECATED:" in result.stderr
    assert "usage:" in result.stdout.lower()


@pytest.mark.parametrize("wrapper_name", HELP_SAFE_BENCHMARK_WRAPPERS)
def test_help_safe_root_benchmark_wrappers_emit_deprecation_and_help(wrapper_name: str) -> None:
    wrapper_path = REPO_ROOT / "benchmarks" / wrapper_name
    runner = (
        [sys.executable, str(wrapper_path)]
        if wrapper_name.endswith(".py")
        else ["bash", str(wrapper_path)]
    )

    result = subprocess.run(  # noqa: S603 - trusted repo-local wrapper smoke test
        [*runner, "--help"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "DEPRECATED:" in result.stderr
    assert "usage:" in result.stdout.lower()


def test_legacy_entrypoints_are_documented_in_tools_reference() -> None:
    reference = (REPO_ROOT / "docs" / "reference" / "tools.md").read_text(encoding="utf-8")

    for legacy_path, replacement in LEGACY_ENTRYPOINTS.items():
        assert legacy_path in reference
        assert replacement in reference


def test_ci_policy_flags_legacy_benchmark_and_deprecated_tool_usage(tmp_path: Path) -> None:
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "legacy.yml").write_text(
        "\n".join(
            [
                "name: legacy",
                "on: push",
                "permissions: {}",
                "jobs:",
                "  test:",
                "    runs-on: ubuntu-latest",
                "    steps:",
                "      - run: bash benchmarks/run_all_benchmarks.sh",
                (
                    "      - run: uv run polisyos-tools cloud "
                    "run-remaining-stages --yes --snapshot-root /tmp/snapshot"
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    findings = collect_findings(tmp_path)
    messages = [finding.message for finding in findings]

    assert any("benchmarks/run_all_benchmarks.sh" in message for message in messages)
    assert any("run-remaining-stages" in message for message in messages)


def test_cloud_deploy_bridge_points_to_canonical_assets_surface() -> None:
    wrapper = (REPO_ROOT / "cloud_deploy" / "deploy_to_server.sh").read_text(encoding="utf-8")

    assert "POLISYOS_CLOUD_ASSETS_DIR" in wrapper
    assert "tools/cloud/deploy/deploy_to_server.sh" in wrapper


def test_prepare_shards_defaults_to_canonical_assets_dir() -> None:
    wrapper = (REPO_ROOT / "tools" / "cloud" / "shards" / "prepare_shards.sh").read_text(
        encoding="utf-8"
    )
    script = (REPO_ROOT / "tools" / "ops" / "cloud" / "shards" / "prepare_shards.sh").read_text(
        encoding="utf-8"
    )

    assert "tools/ops/cloud/shards/prepare_shards.sh" in wrapper
    assert "../deploy/assets" in script


def test_root_benchmark_shell_wrapper_routes_through_unified_cli() -> None:
    wrapper = (REPO_ROOT / "benchmarks" / "run_all_benchmarks.sh").read_text(encoding="utf-8")

    assert "python3 -m tools.cli benchmarks run-all" in wrapper
    assert "DEPRECATED:" in wrapper


def test_local_sota_profile_shell_wrapper_routes_to_canonical_benchmark_surface() -> None:
    wrapper = (REPO_ROOT / "benchmarks" / "run_local_sota_profile.sh").read_text(encoding="utf-8")

    assert "tools/research/benchmarks/run_local_sota_profile.sh" in wrapper
    assert "DEPRECATED:" in wrapper


def test_foundry_legacy_scripts_are_thin_wrappers() -> None:
    generate = (REPO_ROOT / "scripts" / "generate_stubs.py").read_text(encoding="utf-8")
    baseline = (REPO_ROOT / "scripts" / "update_signature_baseline.py").read_text(encoding="utf-8")

    assert "warn_legacy_entrypoint" in generate
    assert "tools.foundry.generate_stubs" in generate
    assert "warn_legacy_entrypoint" in baseline
    assert "tools.foundry.update_signature_baseline" in baseline


def test_live_docs_do_not_reference_legacy_scripts_paths() -> None:
    doc_roots = [
        REPO_ROOT / "docs" / "how-to",
        REPO_ROOT / "docs" / "runbooks",
        REPO_ROOT / "docs" / "tutorials",
        REPO_ROOT / "docs" / "reference" / "operations",
    ]
    doc_files = [
        REPO_ROOT / "docs" / "reference" / "dependency-platform.md",
        REPO_ROOT / "docs" / "reference" / "ratchet-policy.md",
        REPO_ROOT / "docs" / "connectors" / "CONTRIBUTING.md",
        REPO_ROOT / "tests" / "FIXTURE_CATALOG.md",
        REPO_ROOT / "README.md",
        REPO_ROOT.parent / "README.md",
    ]
    candidates: list[Path] = []
    for root in doc_roots:
        if root.exists():
            candidates.extend(root.rglob("*.md"))
    for path in doc_files:
        if path.exists():
            candidates.append(path)

    hits: list[str] = []
    for path in sorted(set(candidates)):
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if LEGACY_SCRIPT_PATTERN.search(line):
                hits.append(f"{path}:{line_no}: {line.strip()}")

    assert hits == []


def test_mutation_tool_scientist_all_aggregates_failures(monkeypatch) -> None:
    calls: list[str] = []

    def _fake_run_target(_repo_root: Path, *, name: str, target: mutation.MutationTarget) -> int:
        calls.append(name)
        return 1 if name == "budget" else 0

    monkeypatch.setattr(mutation, "_run_target", _fake_run_target)

    exit_code = mutation.main(["--suite", "scientist", "--target", "all"])

    assert exit_code == 1
    assert calls == list(mutation.SCIENTIST_TARGETS)


def test_remote_acceptance_imports_are_normalized() -> None:
    shim = (REPO_ROOT / "tools" / "workspace" / "remote_acceptance.py").read_text(encoding="utf-8")
    source = (REPO_ROOT / "tools" / "devx" / "workspace" / "remote_acceptance.py").read_text(
        encoding="utf-8"
    )

    assert "tools.devx.workspace.remote_acceptance" in shim
    assert "ModuleNotFoundError" not in source
    assert "from _common" not in source
    assert "from ._common import" in source


def test_root_benchmark_support_code_is_owned_by_benchmarks_package() -> None:
    harness = (REPO_ROOT / "benchmarks" / "harness.py").read_text(encoding="utf-8")
    shim = (REPO_ROOT / "tools" / "research" / "benchmarks" / "harness.py").read_text(
        encoding="utf-8"
    )

    assert "from benchmarks.metrics import" in harness
    assert '_TARGET = "benchmarks.harness"' in shim
