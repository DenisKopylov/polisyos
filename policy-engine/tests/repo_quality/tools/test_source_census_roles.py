from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from tools.quality.validation.source_census_roles import (
    classify_python_source_role,
    normalize_product_git_path,
    python_source_path_census,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603 - controlled local Git fixture commands.
        ["git", "-C", str(repo), *args],  # noqa: S607 - Git is the sole executable.
        check=True,
        capture_output=True,
    )


def _write(path: Path, text: str = "value = 1\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_product_path_normalization_preserves_exact_repository_boundary() -> None:
    assert normalize_product_git_path("policy-engine/src/module.py", "policy-engine") == (
        "src/module.py"
    )
    assert (
        normalize_product_git_path("policy-engine-sibling/src/module.py", "policy-engine") is None
    )
    double_prefixed = normalize_product_git_path(
        "policy-engine/policy-engine/src/module.py", "policy-engine"
    )
    assert double_prefixed == "policy-engine/src/module.py"
    with pytest.raises(AssertionError, match="unclassified Python/stub path"):
        classify_python_source_role(double_prefixed)


def test_source_roles_cover_current_families_and_keep_research_narrow() -> None:
    roles = {
        "root_module.py": "production_capable",
        "apps/cli.py": "production_capable",
        "architecture/tool.py": "production_capable",
        "benchmarks/runner.py": "benchmark_only",
        "dev-oracles/rdd-cct/compare.py": "production_capable",
        "docs/superpowers/journals/family_probe.py": "production_capable",
        "docs/research/evidence_probe.py": "research_only",
        "examples/minimal.py": "example_only",
        "ops/release.py": "production_capable",
        "src/polisyos/runtime.py": "production_capable",
        "tests/repo_quality/probe.py": "test_only",
        "tools/quality/checker.py": "production_capable",
        "workers/dowhy/family_probe.py": "production_capable",
    }
    assert {path: classify_python_source_role(path) for path in roles} == roles
    with pytest.raises(AssertionError, match="unclassified Python/stub path"):
        classify_python_source_role("unallocated/future.py")


def test_source_census_reconciles_git_and_filesystem_with_ignored_tracked_source(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    product = repo / "policy-engine"
    repo.mkdir()
    _git(repo, "init", "--quiet")
    _git(repo, "config", "user.email", "source-census@example.invalid")
    _git(repo, "config", "user.name", "Source Census Test")
    _write(repo / ".gitignore", "/policy-engine/src/ignored/\n")

    _write(product / "root_module.py")
    _write(product / "src" / "tracked_stub.pyi")
    _write(product / "src" / "ignored" / "tracked_even_ignored.py")
    _write(product / "src" / "ignored" / "untracked_ignored.py")
    _write(product / "untracked_new.py")
    _write(repo / "policy-engine-sibling" / "outside.py")

    _git(
        repo,
        "add",
        ".gitignore",
        "policy-engine/root_module.py",
        "policy-engine/src/tracked_stub.pyi",
    )
    _git(repo, "add", "--force", "policy-engine/src/ignored/tracked_even_ignored.py")
    _git(repo, "add", "policy-engine-sibling/outside.py")

    census = python_source_path_census(product)

    expected = {
        "root_module.py",
        "src/tracked_stub.pyi",
        "src/ignored/tracked_even_ignored.py",
        "untracked_new.py",
    }
    assert set(census.indexed_paths) == {
        "root_module.py",
        "src/tracked_stub.pyi",
        "src/ignored/tracked_even_ignored.py",
    }
    assert set(census.ignored_indexed_paths) == {"src/ignored/tracked_even_ignored.py"}
    assert set(census.git_paths) == expected
    assert set(census.filesystem_paths) == expected

    # A missing indexed source must remain Git-only so the consumer's independent
    # reconciliation fails; the filesystem result must never be filled from Git.
    (product / "src" / "ignored" / "tracked_even_ignored.py").unlink()
    missing_physical = python_source_path_census(product)
    assert "src/ignored/tracked_even_ignored.py" in missing_physical.git_paths
    assert "src/ignored/tracked_even_ignored.py" not in missing_physical.filesystem_paths
