from __future__ import annotations

from pathlib import Path

from tools.quality.ci.check_workflow_policy import collect_findings
from tools.quality.testing import mutation
from tools.registry import (
    CATEGORY_MANIFEST,
    LEGACY_ENTRYPOINTS,
    TOOL_SPECS_BY_KEY,
    categories,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = REPO_ROOT / "tools"

FINAL_TOOL_DIRS = {
    "archive",
    "ci",
    "design",
    "devx",
    "lib",
    "ops_runners",
    "quality",
    "research",
}

RETIRED_TOOL_DIRS = {
    "_deprecated",
    "_lib",
    "architecture",
    "benchmarks",
    "calibration",
    "cloud",
    "connectors",
    "data",
    "demos",
    "diagnostics",
    "foundry",
    "lint",
    "migrations",
    "ops",
    "release",
    "runtime",
    "testing",
    "ukraine_data",
    "validation",
    "workspace",
}


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
        ("ops-experiments", "run-msme-e2e-showcase"),
        ("research-experiments", "filter-topics"),
        ("research-experiments", "organize-relevant-topics"),
        ("foundry", "generate-stubs"),
        ("foundry", "update-signature-baseline"),
        ("testing", "mutation"),
    }

    missing = sorted(key for key in expected if key not in TOOL_SPECS_BY_KEY)
    assert missing == []
    assert TOOL_SPECS_BY_KEY[("cloud", "run-remaining-stages")].status.value == "deprecated"


def test_no_retired_top_level_tool_directories_exist() -> None:
    directories = {
        path.name for path in TOOLS_ROOT.iterdir() if path.is_dir() and path.name != "__pycache__"
    }

    assert RETIRED_TOOL_DIRS.isdisjoint(directories)
    assert directories >= FINAL_TOOL_DIRS


def test_phase1d_target_nested_directories_are_present_and_unique() -> None:
    expected_nested_dirs = {
        "devx/architecture",
        "devx/connectors",
        "devx/foundry",
        "devx/workspace",
        "ops_runners/calibration",
        "ops_runners/cloud",
        "ops_runners/data",
        "ops_runners/deploy",
        "ops_runners/experiments",
        "ops_runners/migrations",
        "ops_runners/release",
        "ops_runners/runtime",
        "quality/ci",
        "quality/diagnostics",
        "quality/lint",
        "quality/testing",
        "quality/validation",
        "research/benchmarks",
        "research/demos",
        "research/experiments",
    }

    missing = sorted(
        rel_path for rel_path in expected_nested_dirs if not (TOOLS_ROOT / rel_path).is_dir()
    )
    assert missing == []

    discovered_categories = categories()
    assert len(discovered_categories) == len(set(discovered_categories))
    assert CATEGORY_MANIFEST["ops-experiments"].implementation_root == (
        TOOLS_ROOT / "ops_runners" / "experiments"
    )
    assert CATEGORY_MANIFEST["research-experiments"].implementation_root == (
        TOOLS_ROOT / "research" / "experiments"
    )
    assert not (TOOLS_ROOT / "research" / "filter_topics.py").exists()
    assert not (TOOLS_ROOT / "research" / "organize_relevant_topics.py").exists()


def test_no_active_legacy_entrypoints_remain_in_registry() -> None:
    assert LEGACY_ENTRYPOINTS == {}
    assert all(not spec.aliases for spec in TOOL_SPECS_BY_KEY.values())


def test_phase1d_legacy_tool_paths_are_retired() -> None:
    for rel_path in (
        "tools/architecture",
        "tools/connectors",
        "tools/foundry",
        "tools/migrations",
        "tools/demos",
    ):
        assert not (REPO_ROOT / rel_path).exists()


def test_ci_policy_flags_retired_surfaces_and_deprecated_tool_usage(tmp_path: Path) -> None:
    legacy_ops_runner = "tools/" "ops/"
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
                "      - run: bash scripts/bootstrap",
                "      - run: python tools/lint/lint_imports.py",
                f"      - run: python {legacy_ops_runner}runtime/check_runtime_api_contract.py",
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

    assert any("scripts/" in message for message in messages)
    assert any("tools/lint/" in message for message in messages)
    assert any(legacy_ops_runner in message for message in messages)
    assert any("run-remaining-stages" in message for message in messages)


def test_prepare_shards_defaults_to_canonical_assets_dir() -> None:
    script = (
        REPO_ROOT
        / "tools"
        / "ops_runners"
        / "cloud"
        / "shards"
        / "prepare_shards.sh"
    ).read_text(encoding="utf-8")

    assert "ops/cloud/deploy/assets" in script


def test_live_docs_do_not_reference_legacy_scripts_paths() -> None:
    candidates = [
        path
        for root in (
            REPO_ROOT / "docs" / "how-to",
            REPO_ROOT / "docs" / "runbooks",
            REPO_ROOT / "docs" / "tutorials",
            REPO_ROOT / "docs" / "reference",
        )
        if root.exists()
        for path in root.rglob("*.md")
    ]

    hits: list[str] = []
    for path in sorted(candidates):
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if _references_product_root_scripts(line):
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
    source = (REPO_ROOT / "tools" / "devx" / "workspace" / "remote_acceptance.py").read_text(
        encoding="utf-8"
    )

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


def _references_product_root_scripts(line: str) -> bool:
    if "frontend/" in line:
        return False
    if "forbidden paths" in line:
        return False
    return any(
        pattern in line
        for pattern in (
            "policy-engine/scripts/",
            "bash scripts/",
            "python scripts/",
            "uv run python scripts/",
            "./scripts/",
            "`scripts/",
        )
    )
