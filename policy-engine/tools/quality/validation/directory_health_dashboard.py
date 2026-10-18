"""Assemble directory-health dashboard metrics and inventory views."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class DashboardFinding(Protocol):
    """Expose the finding field required by dashboard aggregation."""

    check: str


@dataclass(frozen=True)
class DashboardDependencies:
    """Bind dashboard aggregation to the active directory-health facade."""

    read_toml: Callable[[Path], dict[str, Any]]
    rel: Callable[[Path, Path], str]
    tracked_files: Callable[[Path], list[str]]
    ignored_files: Callable[[Path], list[str]]
    walk_files: Callable[..., list[Path]]
    walk_dirs: Callable[..., list[Path]]
    path_matches_any: Callable[[str, list[str]], bool]
    collect_closure_findings: Callable[..., list[Any]]
    closure_counts: Callable[..., dict[str, int]]
    local_residue_by_class: Callable[..., dict[str, int]]
    stable_residue_key: Callable[[str], str]
    asset_counts: Callable[[dict[str, Any]], dict[str, int]]
    empty_dirs_outside_ignored_roots: Callable[..., list[str]]
    high_volume_subtrees: Callable[..., list[dict[str, Any]]]
    non_product_python_root_inventory: Callable[[Path], list[dict[str, Any]]]
    undocumented_frontend_subtrees: Callable[..., list[str]]
    max_directory_depth_by_root: Callable[[Path], dict[str, int]]
    largest_subtrees_by_tracked_file_count: Callable[..., list[dict[str, Any]]]
    percent: Callable[[int, int], float]
    doc_filenames: frozenset[str]
    skip_dir_names: frozenset[str]
    generated_artifacts: Path


def build_dashboard(
    repo_root: Path,
    contract: dict[str, Any],
    directory_contracts: dict[str, Any],
    hygiene: dict[str, Any],
    dependencies: DashboardDependencies,
) -> dict[str, Any]:
    thresholds = contract.get("thresholds", {})
    tracked = [
        path for path in dependencies.tracked_files(repo_root) if (repo_root / path).exists()
    ]
    contracts = {
        str(item.get("path", "")): item for item in directory_contracts.get("contract", [])
    }
    actual_top_level_dirs = sorted(
        path.name
        for path in repo_root.iterdir()
        if path.is_dir() and path.name not in dependencies.skip_dir_names and path.name != ".git"
    )
    covered_top_level_dirs = [root for root in actual_top_level_dirs if root in contracts]
    high_volume = dependencies.high_volume_subtrees(repo_root, thresholds)
    documented_high_volume = [item for item in high_volume if item["documented"]]
    closure_findings = dependencies.collect_closure_findings(
        repo_root,
        contract,
        directory_contracts,
        dependencies.read_toml(dependencies.generated_artifacts),
    )
    closure_counts = dependencies.closure_counts(closure_findings)
    local_residue_by_class = dependencies.local_residue_by_class(repo_root, hygiene, thresholds)
    asset_counts = dependencies.asset_counts(hygiene)
    empty_dirs = dependencies.empty_dirs_outside_ignored_roots(repo_root, thresholds)
    frontend_undocumented = dependencies.undocumented_frontend_subtrees(repo_root, thresholds)
    max_depth_by_root = dependencies.max_directory_depth_by_root(repo_root)
    max_depth = max(max_depth_by_root.values(), default=0)
    largest_subtrees = dependencies.largest_subtrees_by_tracked_file_count(
        repo_root, tracked, thresholds
    )

    metrics: dict[str, int | float] = {
        "top_level_directory_contract_coverage_percent": dependencies.percent(
            len(covered_top_level_dirs), len(actual_top_level_dirs)
        ),
        "high_volume_subtree_documentation_coverage_percent": dependencies.percent(
            len(documented_high_volume), len(high_volume)
        ),
        "non_product_python_root_count": len(
            dependencies.non_product_python_root_inventory(repo_root)
        ),
        "source_local_residue_count": local_residue_by_class.get(
            "ignored_source_docs_schemas_tests", 0
        ),
        "empty_directory_count_outside_ignored_roots": len(empty_dirs),
        "product_asset_count": asset_counts.get("product_seed_assets", 0),
        "test_fixture_count": asset_counts.get("test_fixtures", 0),
        "golden_record_count": asset_counts.get("golden_records", 0),
        "example_asset_count": asset_counts.get("examples_tutorial_assets", 0),
        "undocumented_frontend_subtree_count": len(frontend_undocumented),
        "archive_report_promotion_backlog": (
            local_residue_by_class.get("local_reports", 0)
            + local_residue_by_class.get("generated_benchmark_reports", 0)
        ),
        "max_directory_depth": max_depth,
        **closure_counts,
    }
    return {
        "metrics": metrics,
        "top_level_directories": {
            "present": actual_top_level_dirs,
            "covered": covered_top_level_dirs,
            "missing_contract": sorted(set(actual_top_level_dirs) - set(covered_top_level_dirs)),
        },
        "high_volume_subtrees": high_volume,
        "non_product_python_roots": dependencies.non_product_python_root_inventory(repo_root),
        "local_residue_by_class": local_residue_by_class,
        "empty_directories_outside_ignored_roots": empty_dirs,
        "asset_counts": asset_counts,
        "undocumented_frontend_subtrees": frontend_undocumented,
        "max_directory_depth_by_root": max_depth_by_root,
        "largest_subtrees_by_tracked_file_count": largest_subtrees,
    }


def percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 100.0
    return round((numerator / denominator) * 100.0, 2)


def closure_counts(findings: list[DashboardFinding]) -> dict[str, int]:
    by_check: dict[str, int] = {}
    for finding in findings:
        by_check[finding.check] = by_check.get(finding.check, 0) + 1
    return {
        "closure_top_level_loose_file_count": by_check.get("top-level-loose-file-allow-list", 0),
        "closure_forbidden_lifecycle_commit_count": by_check.get("forbidden-lifecycle-commits", 0),
        "closure_non_product_init_count": by_check.get("non-product-init-files", 0),
        "closure_forbidden_product_import_count": by_check.get(
            "product-imports-tests-benchmarks", 0
        ),
        "closure_data_only_pytest_count": by_check.get("data-only-pytest-collectable", 0),
        "closure_unregistered_frontend_fixture_count": by_check.get(
            "frontend-src-fixture-registration", 0
        ),
        "closure_unregistered_generated_api_count": by_check.get("generated-api-placement", 0),
        "closure_empty_ui_component_directory_count": by_check.get(
            "empty-ui-component-directory", 0
        ),
        "closure_over_threshold_feature_without_owner_count": by_check.get(
            "feature-module-owner-threshold", 0
        ),
        "closure_phase_local_junk_count": by_check.get("phase-local-junk-residue", 0),
    }


def local_residue_by_class(
    repo_root: Path,
    hygiene: dict[str, Any],
    thresholds: dict[str, Any],
    dependencies: DashboardDependencies,
) -> dict[str, int]:
    classes = dict(hygiene.get("classes", {}).get("counts", {}))
    residue_roots = {str(item).rstrip("/") for item in thresholds.get("source_residue_roots", [])}
    ignored_source = {
        dependencies.stable_residue_key(relative)
        for relative in dependencies.ignored_files(repo_root)
        if relative.split("/", 1)[0] in residue_roots and "__pycache__" not in Path(relative).parts
    }
    residue_dirs = [
        dependencies.rel(path, repo_root)
        for root in residue_roots
        for path in dependencies.walk_dirs(repo_root, root)
        if path.name == ".DS_Store"
    ]
    classes["ignored_source_docs_schemas_tests"] = len(set(ignored_source).union(residue_dirs))
    return {key: int(value) for key, value in sorted(classes.items())}


def stable_residue_key(relative: str) -> str:
    parts = Path(relative).parts
    if "__pycache__" in parts:
        index = parts.index("__pycache__")
        return "/".join(parts[: index + 1])
    return relative


def asset_counts(hygiene: dict[str, Any]) -> dict[str, int]:
    classes = hygiene.get("classes", {}).get("counts", {})
    return {
        key: int(classes.get(key, 0))
        for key in (
            "product_seed_assets",
            "test_fixtures",
            "golden_records",
            "examples_tutorial_assets",
        )
    }


def empty_dirs_outside_ignored_roots(
    repo_root: Path, thresholds: dict[str, Any], *, dependencies: DashboardDependencies
) -> list[str]:
    ignored_roots = [
        str(item).rstrip("/") for item in thresholds.get("ignored_empty_directory_roots", [])
    ]
    empty: list[str] = []
    for directory in dependencies.walk_dirs(repo_root):
        relative = dependencies.rel(directory, repo_root)
        if relative == "." or dependencies.path_matches_any(relative, ignored_roots):
            continue
        try:
            next(directory.iterdir())
        except StopIteration:
            empty.append(relative)
    return sorted(empty)


def high_volume_subtrees(
    repo_root: Path, thresholds: dict[str, Any], *, dependencies: DashboardDependencies
) -> list[dict[str, Any]]:
    tracked_threshold = int(thresholds.get("high_volume_tracked_files", 20))
    child_threshold = int(thresholds.get("high_volume_child_directories", 10))
    tracked = [
        path for path in dependencies.tracked_files(repo_root) if (repo_root / path).exists()
    ]
    counts: dict[str, int] = {}
    for relative in tracked:
        parts = Path(relative).parts
        for index in range(1, min(len(parts), 5)):
            subtree = "/".join(parts[:index])
            counts[subtree] = counts.get(subtree, 0) + 1
    rows: list[dict[str, Any]] = []
    for subtree, file_count in sorted(counts.items()):
        path = repo_root / subtree
        if not path.is_dir():
            continue
        child_count = len([child for child in path.iterdir() if child.is_dir()])
        if file_count < tracked_threshold and child_count <= child_threshold:
            continue
        rows.append(
            {
                "path": subtree,
                "tracked_file_count": file_count,
                "immediate_child_directory_count": child_count,
                "documented": any((path / doc).exists() for doc in dependencies.doc_filenames),
            }
        )
    return rows


def non_product_python_root_inventory(
    repo_root: Path, *, dependencies: DashboardDependencies
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    contracts = dependencies.read_toml(
        repo_root / "architecture" / "policies" / "directory_contracts.toml"
    )
    roots = sorted(
        str(item.get("path", ""))
        for item in contracts.get("non_product_python_root", [])
        if str(item.get("path", ""))
    )
    for root in roots:
        path = repo_root / root
        if not path.exists():
            continue
        init_files = sorted(dependencies.rel(item, repo_root) for item in path.rglob("__init__.py"))
        rows.append(
            {
                "root": root,
                "exists": path.exists(),
                "init_file_count": len(init_files),
                "sample_init_files": init_files[:10],
            }
        )
    return rows


def undocumented_frontend_subtrees(
    repo_root: Path, thresholds: dict[str, Any], *, dependencies: DashboardDependencies
) -> list[str]:
    tracked_threshold = int(thresholds.get("high_volume_tracked_files", 20))
    rows: list[str] = []
    for frontend_root in thresholds.get("frontend_subtree_doc_roots", []):
        root = repo_root / str(frontend_root)
        if not root.exists():
            continue
        for src_root in sorted(root.glob("*/src")):
            for child in sorted(path for path in src_root.iterdir() if path.is_dir()):
                files = dependencies.walk_files(repo_root, dependencies.rel(child, repo_root))
                if len(files) < tracked_threshold:
                    continue
                if not any((child / doc).exists() for doc in dependencies.doc_filenames):
                    rows.append(dependencies.rel(child, repo_root))
    return sorted(rows)


def max_directory_depth_by_root(
    repo_root: Path, *, dependencies: DashboardDependencies
) -> dict[str, int]:
    depths: dict[str, int] = {}
    for directory in dependencies.walk_dirs(repo_root):
        relative = dependencies.rel(directory, repo_root)
        if relative == ".":
            continue
        parts = Path(relative).parts
        root = parts[0]
        depths[root] = max(depths.get(root, 0), len(parts))
    return depths


def largest_subtrees_by_tracked_file_count(
    repo_root: Path,
    tracked: list[str],
    thresholds: dict[str, Any],
) -> list[dict[str, Any]]:
    limit = int(thresholds.get("dashboard_largest_subtree_limit", 10))
    counts: dict[str, int] = {}
    for relative in tracked:
        parts = Path(relative).parts
        max_depth = min(len(parts), 4)
        for depth in range(1, max_depth):
            subtree = "/".join(parts[:depth])
            if (repo_root / subtree).is_dir():
                counts[subtree] = counts.get(subtree, 0) + 1
    return [
        {"path": path, "tracked_file_count": count}
        for path, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def metric_regressions[FindingT](
    contract: dict[str, Any],
    metrics: dict[str, int | float],
    *,
    finding_factory: Callable[[str, str, str, str, str], FindingT],
) -> list[FindingT]:
    exceptions = {
        str(item.get("metric", ""))
        for item in contract.get("health_exception", [])
        if item.get("metric")
    }
    regressions: list[FindingT] = []
    for baseline in contract.get("metric_baseline", []):
        metric_id = str(baseline.get("id", ""))
        if not metric_id or metric_id not in metrics:
            continue
        observed = float(metrics[metric_id])
        expected = float(baseline.get("value", 0))
        direction = str(baseline.get("direction", "not_increase"))
        if metric_id in exceptions:
            continue
        if direction == "not_decrease" and observed < expected:
            regressions.append(
                finding_factory(
                    "directory-health-regression",
                    "blocker",
                    metric_id,
                    "metric decreased below baseline",
                    f"observed={observed} baseline={expected}",
                )
            )
        if direction == "not_increase" and observed > expected:
            regressions.append(
                finding_factory(
                    "directory-health-regression",
                    "blocker",
                    metric_id,
                    "metric increased above baseline",
                    f"observed={observed} baseline={expected}",
                )
            )
    return regressions
