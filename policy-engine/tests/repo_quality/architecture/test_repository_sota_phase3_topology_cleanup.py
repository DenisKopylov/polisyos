from __future__ import annotations

import fnmatch
import os
import subprocess
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = REPO_ROOT.parent

FORBIDDEN_PRODUCT_ROOTS = {
    ".github",
    "cloud_deploy",
    "deploy",
    "docker",
    "gcp",
    "scripts",
}

FINAL_TOOL_DIRS = {
    "architecture",
    "archive",
    "ci",
    "cli.py",
    "connectors",
    "demos",
    "design",
    "devx",
    "foundry",
    "lib",
    "migrations",
    "ops",
    "ops_runners",
    "quality",
    "README.md",
    "registry.py",
    "research",
    "__init__.py",
}

FORBIDDEN_TOOL_DIRS = {
    "_deprecated",
    "_lib",
    "benchmarks",
    "calibration",
    "cloud",
    "data",
    "diagnostics",
    "lint",
    "release",
    "runtime",
    "testing",
    "ukraine_data",
    "validation",
    "workspace",
}

FINAL_TEST_ROOTS = {
    "_data",
    "_golden",
    "_helpers",
    "architecture",
    "contract",
    "conftest.py",
    "e2e",
    "fixtures",
    "FIXTURE_CATALOG.md",
    "golden",
    "integration",
    "lint",
    "performance",
    "property",
    "quarantine.toml",
    "README.md",
    "repo_quality",
    "TESTING_POLICY.md",
    "tools",
    "unit",
}

FORBIDDEN_TEST_ROOTS = {
    "berl",
    "calibration",
    "common",
    "core",
    "data_forge",
    "ddm_15_7",
    "demos",
    "docs",
    "fabric",
    "foundry",
    "ir",
    "lex",
    "runtime",
    "scholar",
    "scientist",
    "synthetic_world",
}

FINAL_OPS_ROOTS = {
    "ci",
    "cloud",
    "components",
    "deploy",
    "docker",
    "migrations",
    "observability",
    "policy",
    "release",
    "runtime",
    "security",
}

DOCS_ROOT_ALLOWLIST = {"README.md", "index.md", "style-guide.md", "key-rotation.md"}

PHASE2A_FORBIDDEN_OUTER_ROOT_ENTRIES = {
    "README.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "SUPPORT.md",
    "lefthook.yml",
    "data",
    "design",
    ".venv",
    ".venv-spatial-tests",
    ".mypy_cache",
    ".polisyos",
    ".pytest_cache",
    ".ruff_cache",
    ".hypothesis",
    ".benchmarks",
    ".tmp",
    "tmp",
}

PHASE2A_SINGLETON_DIRS = {".venv", ".polisyos", "_build", "_cache"}

PHASE2B_RETIRED_PRODUCT_EPHEMERAL_ROOTS = {
    ".benchmarks",
    ".cache",
    ".hypothesis",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".uv-cache",
    ".basedpyright",
    ".polisyos-tools",
    ".tmp",
    "benchmark-results",
    "dist",
    "logs",
    "out",
    "output",
    "site",
    "tmp",
}

PHASE2B_CANONICAL_IGNORED_ROOTS = {
    "_build",
    "_cache",
    ".polisyos",
    ".venv",
}


def test_phase3_topology_gate_has_no_unclassified_visible_root_paths() -> None:
    topology = tomllib.loads((REPO_ROOT / "architecture" / "topology.toml").read_text())

    assert topology["topology"]["status"] == "final"

    repo_paths = _topology_paths(topology, scope="repo_root")
    product_paths = _topology_paths(topology, scope="product_root")

    assert product_paths == set()
    assert (
        _unclassified_entries(
            REPO_ROOT,
            path_entries=repo_paths,
            loose_files=topology["loose_files"]["repo_root"],
        )
        == []
    )


def test_phase2a_workspace_boundary_is_collapsed_to_policy_engine_root() -> None:
    topology = tomllib.loads((REPO_ROOT / "architecture" / "topology.toml").read_text())

    assert {entry["scope"] for entry in topology["path"]} == {"repo_root"}
    assert "product_root" not in topology.get("loose_files", {})
    assert not any(
        (WORKSPACE_ROOT / name).exists() for name in PHASE2A_FORBIDDEN_OUTER_ROOT_ENTRIES
    )
    assert not any(child.name.startswith(".venv") for child in WORKSPACE_ROOT.iterdir())
    assert (WORKSPACE_ROOT / ".github").exists()
    assert (WORKSPACE_ROOT / ".github" / "renovate.json").exists()
    assert not (WORKSPACE_ROOT / "renovate.json").exists()

    for dirname in PHASE2A_SINGLETON_DIRS:
        assert _named_dirs(WORKSPACE_ROOT, dirname) == [REPO_ROOT / dirname]


def test_phase2b_build_and_cache_umbrellas_are_canonical() -> None:
    topology = tomllib.loads((REPO_ROOT / "architecture" / "topology.toml").read_text())
    repo_entries = {
        entry["path"]: entry for entry in topology["path"] if entry["scope"] == "repo_root"
    }

    ignored_roots = {
        path
        for path, entry in repo_entries.items()
        if entry["commit_policy"] == "ignored"
        and entry["category"] in {"build_output", "cache", "legacy_local_env", "runtime_state"}
    }
    assert ignored_roots == PHASE2B_CANONICAL_IGNORED_ROOTS
    assert {
        path
        for path, entry in repo_entries.items()
        if entry["commit_policy"] == "ignored" and entry["category"] in {"build_output", "cache"}
    } == {"_build", "_cache"}
    assert PHASE2B_RETIRED_PRODUCT_EPHEMERAL_ROOTS.isdisjoint(repo_entries)
    assert not any((REPO_ROOT / name).exists() for name in PHASE2B_RETIRED_PRODUCT_EPHEMERAL_ROOTS)

    assert _git_ignores(REPO_ROOT / "_build" / "phase2b.tmp")
    assert _git_ignores(REPO_ROOT / "_cache" / "phase2b.tmp")

    release_workflow = (WORKSPACE_ROOT / ".github" / "workflows" / "release.yml").read_text()
    docs_pages_workflow = (WORKSPACE_ROOT / ".github" / "workflows" / "docs-pages.yml").read_text()
    assert "uv build --out-dir _build/dist --clear" in release_workflow
    assert "path: policy-engine/_build/site" in docs_pages_workflow


def test_phase3_product_root_has_no_retired_legacy_surfaces() -> None:
    for path_name in FORBIDDEN_PRODUCT_ROOTS:
        assert not (REPO_ROOT / path_name).exists(), path_name

    topology = tomllib.loads((REPO_ROOT / "architecture" / "topology.toml").read_text())
    repo_paths = _topology_paths(topology, scope="repo_root")
    assert FORBIDDEN_PRODUCT_ROOTS.isdisjoint(repo_paths)


def test_phase3_tools_tree_has_only_final_top_level_namespaces() -> None:
    entries = {
        path.name
        for path in (REPO_ROOT / "tools").iterdir()
        if not _git_ignores(path) and path.name != "__pycache__"
    }

    assert FORBIDDEN_TOOL_DIRS.isdisjoint(entries)
    assert entries <= FINAL_TOOL_DIRS


def test_phase3_tests_tree_uses_final_physical_taxonomy() -> None:
    entries = {
        path.name
        for path in (REPO_ROOT / "tests").iterdir()
        if not _git_ignores(path) and path.name != "__pycache__"
    }

    assert FORBIDDEN_TEST_ROOTS.isdisjoint(entries)
    assert entries <= FINAL_TEST_ROOTS

    for package in FORBIDDEN_TEST_ROOTS - {"demos", "docs"}:
        assert (REPO_ROOT / "tests" / "unit" / package).exists(), package
    assert (REPO_ROOT / "tests" / "e2e" / "demos").exists()
    assert (REPO_ROOT / "tests" / "repo_quality" / "architecture" / "docs").exists()


def test_phase3_ops_tree_uses_final_nested_layout() -> None:
    entries = {
        path.name
        for path in (REPO_ROOT / "ops").iterdir()
        if path.is_dir() and not _git_ignores(path)
    }

    assert {"grafana", "prometheus", "opa", "helm", "terraform"}.isdisjoint(entries)
    assert entries <= FINAL_OPS_ROOTS
    assert (REPO_ROOT / "ops" / "observability" / "grafana").exists()
    assert (REPO_ROOT / "ops" / "observability" / "prometheus").exists()
    assert (REPO_ROOT / "ops" / "policy").exists()
    assert (REPO_ROOT / "ops" / "observability" / "otel").exists()
    assert (REPO_ROOT / "ops" / "observability" / "slo").exists()
    assert (REPO_ROOT / "ops" / "cloud" / "gcp").exists()
    assert (REPO_ROOT / "ops" / "cloud" / "helm").exists()
    assert (REPO_ROOT / "ops" / "cloud" / "terraform").exists()


def test_phase3_docs_root_uses_strict_lifecycle_allowlist() -> None:
    top_level_docs = {
        path.name for path in (REPO_ROOT / "docs").glob("*.md") if not _git_ignores(path)
    }

    assert top_level_docs <= DOCS_ROOT_ALLOWLIST
    assert (REPO_ROOT / "docs" / "plans" / "active" / "DOCUMENTATION_SOTA_PLAN.md").exists()
    assert (
        REPO_ROOT / "docs" / "plans" / "archive" / "DATA_FORGE_CONSOLIDATION_PLAN_ROOT_LEGACY.md"
    ).exists()


def test_phase3_migration_shims_do_not_register_retired_clean_cut_sources() -> None:
    shims = tomllib.loads((REPO_ROOT / "architecture" / "shims.toml").read_text(encoding="utf-8"))[
        "shim"
    ]
    sources = {shim["source_path"] for shim in shims}

    assert FORBIDDEN_PRODUCT_ROOTS.isdisjoint(sources)
    assert not any(
        source in {f"tools/{name}" for name in FORBIDDEN_TOOL_DIRS} for source in sources
    )


def _topology_paths(topology: dict[str, object], *, scope: str) -> set[str]:
    return {item["path"] for item in topology["path"] if item["scope"] == scope}


def _unclassified_entries(
    root: Path,
    *,
    path_entries: set[str],
    loose_files: dict[str, list[str]],
    skip_names: set[str] | None = None,
) -> list[str]:
    skip_names = skip_names or set()
    allowed = set(loose_files["allow"])
    denied = tuple(loose_files["deny"])
    problems: list[str] = []

    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if child.name in skip_names:
            continue
        if any(fnmatch.fnmatch(child.name, pattern) for pattern in denied):
            problems.append(f"denied:{child.name}")
            continue
        if _git_ignores(child):
            continue
        if child.name not in path_entries and child.name not in allowed:
            problems.append(child.name)

    return problems


def _git_ignores(path: Path) -> bool:
    result = subprocess.run(  # noqa: S603 - trusted local git query in tests.
        ["git", "check-ignore", "-q", str(path.relative_to(WORKSPACE_ROOT))],
        cwd=WORKSPACE_ROOT,
        check=False,
    )
    return result.returncode == 0


def _named_dirs(root: Path, dirname: str) -> list[Path]:
    matches: list[Path] = []
    pruned_names = {
        ".git",
        ".polisyos",
        "node_modules",
        ".cache",
        ".uv-cache",
        ".pytest_cache",
        ".ruff_cache",
        ".hypothesis",
        ".benchmarks",
        ".tmp",
        "_build",
        "_cache",
        "src",
        "tmp",
    }
    for current, names, _files in os.walk(root):
        current_path = Path(current)
        for name in list(names):
            if name == dirname:
                matches.append(current_path / name)
        names[:] = [
            name
            for name in names
            if name not in pruned_names
            and name != dirname
            and not (name.startswith(".venv") and dirname != name)
        ]
    return sorted(path.resolve() for path in matches)
