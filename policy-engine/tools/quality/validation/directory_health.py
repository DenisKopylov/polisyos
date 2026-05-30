#!/usr/bin/env python3
"""Build the Phase 6.2 directory-health dashboard and ratchet report."""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import repo_root_from
from tools.quality.validation import directory_hygiene_assets

REPO_ROOT = repo_root_from(__file__)
DEFAULT_CONTRACT = REPO_ROOT / "architecture" / "policies" / "directory_health.toml"
GENERATED_ARTIFACTS = REPO_ROOT / "architecture" / "generated_artifacts.toml"
DOC_FILENAMES = {"README.md", "AUTHORING.md", "index.md"}
SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".hypothesis",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".venv_codex",
    "_build",
    "_cache",
    ".polisyos",
    "node_modules",
    ".next",
    ".turbo",
    "__pycache__",
}
UI_COMPONENT_DIR_NAMES = {"components", "component", "ui"}
GENERATED_API_PATTERNS = (
    "*runtimeApiClient.ts",
    "*runtimeApiClient.js",
    "*src/api/types.ts",
)
PHASE_LOCAL_JUNK_PATTERN = "phase*-local-junk-*"
PHASE_LOCAL_JUNK_EXCEPTION_KIND = "phase_local_junk_residue"
PHASE_LOCAL_JUNK_SCRATCH_POLICY = "explicitly_ignored"
SCHEMA_DATA_SUFFIXES = {".json", ".md", ".toml", ".yaml", ".yml"}


@dataclass(frozen=True)
class Finding:
    check: str
    severity: str
    subject: str
    message: str
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "check": self.check,
            "severity": self.severity,
            "subject": self.subject,
            "message": self.message,
            "detail": self.detail,
        }


def build_report(
    repo_root: Path = REPO_ROOT,
    *,
    contract_path: Path = DEFAULT_CONTRACT,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    contract_path = contract_path if contract_path.is_absolute() else repo_root / contract_path
    contract = _read_toml(contract_path)
    directory_contracts = _read_toml(
        repo_root / "architecture" / "policies" / "directory_contracts.toml"
    )
    generated_artifacts = _read_toml(repo_root / "architecture" / "generated_artifacts.toml")
    hygiene = directory_hygiene_assets.build_report(repo_root)

    contract_errors = _validate_contract(repo_root, contract, directory_contracts)
    closure_findings = _collect_closure_findings(
        repo_root,
        contract,
        directory_contracts,
        generated_artifacts,
    )
    dashboard = _build_dashboard(repo_root, contract, directory_contracts, hygiene)
    metrics = dashboard["metrics"]
    regressions = _metric_regressions(contract, metrics)

    header = contract.get("directory_health", {})
    top_level_path_moves_active = bool(header.get("top_level_path_moves_active", False))
    fail_closed_closure = (
        header.get("mode") == "fail_closed" and not top_level_path_moves_active
    )
    status = (
        "failed"
        if contract_errors or regressions or (fail_closed_closure and closure_findings)
        else "passed"
    )
    return {
        "phase": "6.2",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "contract": _rel(contract_path, repo_root),
        "status": status,
        "mode": header.get("mode", ""),
        "top_level_path_moves_active": top_level_path_moves_active,
        "fail_closed_closure": fail_closed_closure,
        "contract_error_count": len(contract_errors),
        "finding_count": len(closure_findings),
        "regression_count": len(regressions),
        "contract_errors": [finding.as_dict() for finding in contract_errors],
        "findings": [finding.as_dict() for finding in closure_findings],
        "regressions": [finding.as_dict() for finding in regressions],
        "dashboard": dashboard,
    }


def dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_markdown(payload: dict[str, Any]) -> str:
    dashboard = payload["dashboard"]
    metrics = dashboard["metrics"]
    lines = [
        "# Directory Health Dashboard",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Contract: `{payload['contract']}`",
        f"- Mode: `{payload['mode']}`",
        f"- Status: `{payload['status']}`",
        f"- Top-level path moves active: `{payload['top_level_path_moves_active']}`",
        f"- Contract errors: {payload['contract_error_count']}",
        f"- Closure findings: {payload['finding_count']}",
        f"- Metric regressions: {payload['regression_count']}",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    for key in sorted(metrics):
        value = metrics[key]
        rendered = f"{value:.2f}" if isinstance(value, float) else str(value)
        lines.append(f"| `{key}` | {rendered} |")

    lines.extend(
        [
            "",
            "## Local Residue",
            "",
            "| Class | Count |",
            "| --- | ---: |",
        ]
    )
    for name, count in sorted(dashboard["local_residue_by_class"].items()):
        lines.append(f"| `{name}` | {count} |")

    lines.extend(
        [
            "",
            "## Product/Test Asset Counts",
            "",
            "| Class | Count |",
            "| --- | ---: |",
        ]
    )
    for name, count in sorted(dashboard["asset_counts"].items()):
        lines.append(f"| `{name}` | {count} |")

    lines.extend(
        [
            "",
            "## Maximum Directory Depth By Root",
            "",
            "| Root | Depth |",
            "| --- | ---: |",
        ]
    )
    for root, depth in sorted(dashboard["max_directory_depth_by_root"].items()):
        lines.append(f"| `{root}` | {depth} |")

    lines.extend(
        [
            "",
            "## Largest Subtrees",
            "",
            "| Subtree | Tracked files |",
            "| --- | ---: |",
        ]
    )
    for item in dashboard["largest_subtrees_by_tracked_file_count"]:
        lines.append(f"| `{item['path']}` | {item['tracked_file_count']} |")

    lines.extend(["", "## Findings", ""])
    if not payload["contract_errors"] and not payload["findings"] and not payload["regressions"]:
        lines.append("- none")
    for item in payload["contract_errors"] + payload["findings"] + payload["regressions"]:
        detail = f" ({item['detail']})" if item.get("detail") else ""
        lines.append(
            f"- `{item['severity']}` `{item['check']}` `{item['subject']}`: "
            f"{item['message']}{detail}"
        )
    lines.append("")
    return "\n".join(lines)


def run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--fail-on-regression", action="store_true")
    parser.add_argument("--fail-on-findings", action="store_true")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    contract_path = args.contract if args.contract.is_absolute() else repo_root / args.contract
    payload = build_report(repo_root, contract_path=contract_path)
    rendered = dump_json(payload) if args.format == "json" else render_markdown(payload)

    if args.json_output is not None:
        output = (
            args.json_output if args.json_output.is_absolute() else repo_root / args.json_output
        )
        atomic_write_text(output, dump_json(payload))
    if args.markdown_output is not None:
        output = (
            args.markdown_output
            if args.markdown_output.is_absolute()
            else repo_root / args.markdown_output
        )
        atomic_write_text(output, render_markdown(payload))
    if args.json_output is None and args.markdown_output is None:
        print(rendered, end="" if rendered.endswith("\n") else "\n")  # noqa: T201

    if args.fail_on_regression and (
        payload["contract_error_count"]
        or payload["regression_count"]
        or (payload["fail_closed_closure"] and payload["finding_count"])
    ):
        return 1
    if args.fail_on_findings and payload["finding_count"]:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    return run_cli(argv)


def _read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _git_lines(repo_root: Path, *args: str) -> list[str]:
    try:
        completed = subprocess.run(  # noqa: S603
            ["git", *args],  # noqa: S607
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _tracked_files(repo_root: Path) -> list[str]:
    return sorted(_git_lines(repo_root, "ls-files"))


def _ignored_files(repo_root: Path) -> list[str]:
    return sorted(_git_lines(repo_root, "ls-files", "-o", "-i", "--exclude-standard"))


def _walk_files(repo_root: Path, relative_root: str = ".") -> list[Path]:
    root = repo_root / relative_root
    if not root.exists():
        return []
    files: list[Path] = []
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIR_NAMES]
        for filename in filenames:
            files.append(Path(current) / filename)
    return sorted(files)


def _walk_dirs(repo_root: Path, relative_root: str = ".") -> list[Path]:
    root = repo_root / relative_root
    if not root.exists():
        return []
    dirs: list[Path] = []
    for current, dirnames, _filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIR_NAMES]
        dirs.append(Path(current))
    return sorted(dirs)


def _path_matches_pattern(relative: str, pattern: str) -> bool:
    normalized = pattern.rstrip("/")
    if normalized.endswith("/"):
        normalized = normalized[:-1]
    normalized = normalized.replace("<package>", "*").replace("<example-name>", "*")
    return (
        fnmatch.fnmatch(relative, normalized)
        or fnmatch.fnmatch(relative, f"{normalized}/**")
        or relative == normalized
        or relative.startswith(f"{normalized}/")
    )


def _path_matches_any(relative: str, patterns: list[str]) -> bool:
    return any(_path_matches_pattern(relative, pattern) for pattern in patterns)


def _validate_contract(
    repo_root: Path,
    contract: dict[str, Any],
    directory_contracts: dict[str, Any],
) -> list[Finding]:
    errors: list[Finding] = []
    header = contract.get("directory_health", {})
    for field in (
        "version",
        "status",
        "phase",
        "owner",
        "mode",
        "directory_contracts_source",
        "test_ratchets_source",
        "asset_placement_source",
        "generated_artifacts_source",
        "validator_command",
        "dashboard_command",
    ):
        if header.get(field) in (None, "", []):
            errors.append(Finding("contract", "error", "directory_health", f"missing `{field}`"))
    for field in (
        "directory_contracts_source",
        "test_ratchets_source",
        "asset_placement_source",
        "generated_artifacts_source",
    ):
        value = str(header.get(field, ""))
        if value and not (repo_root / value).exists():
            errors.append(Finding("contract", "error", value, "source contract is missing"))

    thresholds = contract.get("thresholds", {})
    for field in (
        "high_volume_tracked_files",
        "high_volume_child_directories",
        "feature_module_file_threshold",
        "dashboard_largest_subtree_limit",
    ):
        if int(thresholds.get(field, 0) or 0) <= 0:
            errors.append(Finding("contract", "error", "thresholds", f"`{field}` must be positive"))
    for field in (
        "allowed_root_loose_files",
        "allowed_non_product_init_roots",
        "source_residue_roots",
        "data_only_roots",
        "registered_frontend_fixture_roots",
    ):
        if thresholds.get(field) in (None, "", []):
            errors.append(Finding("contract", "error", "thresholds", f"missing `{field}`"))

    directory_contract_paths = {
        str(item.get("path", "")) for item in directory_contracts.get("contract", [])
    }
    for root in thresholds.get("allowed_non_product_init_roots", []):
        if root not in directory_contract_paths:
            errors.append(
                Finding(
                    "contract",
                    "error",
                    str(root),
                    "allowed non-product init root has no directory contract",
                )
            )

    gate_ids = {str(item.get("id", "")) for item in contract.get("gate", [])}
    required_gates = {
        "mirror-ratio",
        "no-regression",
        "property-test",
        "fixture-golden",
        "repo-quality",
        "pytest-root",
        "benchmark-role",
        "top-level-directory-contract",
        "top-level-loose-file-allow-list",
        "forbidden-lifecycle-commits",
        "source-local-residue",
        "non-product-init-files",
        "product-imports-tests-benchmarks",
        "data-only-pytest-collectable",
        "frontend-src-fixture-registration",
        "generated-api-placement",
        "empty-ui-component-directory",
        "feature-module-owner-threshold",
        "phase-local-junk-residue",
    }
    for gate_id in sorted(required_gates - gate_ids):
        errors.append(Finding("contract", "error", gate_id, "missing Phase 6.2 gate"))
    for gate in contract.get("gate", []):
        subject = str(gate.get("id", "gate"))
        for field in ("area", "owner", "mode", "command", "evidence"):
            if gate.get(field) in (None, "", []):
                errors.append(Finding("contract", "error", subject, f"missing `{field}`"))
        evidence = str(gate.get("evidence", ""))
        if evidence and not (repo_root / evidence).exists():
            errors.append(
                Finding("contract", "error", subject, "evidence path is missing", evidence)
            )
    if header.get("mode") == "fail_closed":
        if bool(header.get("top_level_path_moves_active", False)):
            errors.append(
                Finding(
                    "contract",
                    "error",
                    "directory_health",
                    "fail_closed mode cannot keep top-level path moves active",
                )
            )
        directory_gate_ids = {
            "top-level-directory-contract",
            "top-level-loose-file-allow-list",
            "forbidden-lifecycle-commits",
            "source-local-residue",
            "non-product-init-files",
            "product-imports-tests-benchmarks",
            "data-only-pytest-collectable",
            "frontend-src-fixture-registration",
            "generated-api-placement",
            "empty-ui-component-directory",
            "feature-module-owner-threshold",
        }
        allowed_non_fail_closed = {"source-local-residue"}
        for gate in contract.get("gate", []):
            gate_id = str(gate.get("id", ""))
            if (
                gate_id in directory_gate_ids - allowed_non_fail_closed
                and gate.get("mode") != "fail_closed"
            ):
                errors.append(
                    Finding(
                        "contract",
                        "error",
                        gate_id,
                        "Phase 6.2 directory gate must be fail_closed",
                        str(gate.get("mode", "")),
                    )
                )

    errors.extend(_validate_health_exceptions(contract))

    baseline_ids = {str(item.get("id", "")) for item in contract.get("metric_baseline", [])}
    required_metrics = {
        "top_level_directory_contract_coverage_percent",
        "high_volume_subtree_documentation_coverage_percent",
        "non_product_python_root_count",
        "source_local_residue_count",
        "empty_directory_count_outside_ignored_roots",
        "product_asset_count",
        "test_fixture_count",
        "golden_record_count",
        "example_asset_count",
        "undocumented_frontend_subtree_count",
        "archive_report_promotion_backlog",
        "max_directory_depth",
        "closure_top_level_loose_file_count",
        "closure_forbidden_lifecycle_commit_count",
        "closure_non_product_init_count",
        "closure_forbidden_product_import_count",
        "closure_data_only_pytest_count",
        "closure_unregistered_frontend_fixture_count",
        "closure_unregistered_generated_api_count",
        "closure_empty_ui_component_directory_count",
        "closure_over_threshold_feature_without_owner_count",
        "closure_phase_local_junk_count",
    }
    for metric_id in sorted(required_metrics - baseline_ids):
        errors.append(Finding("contract", "error", metric_id, "missing metric baseline"))
    return errors


def _validate_health_exceptions(contract: dict[str, Any]) -> list[Finding]:
    errors: list[Finding] = []
    today = date.today()
    for exception in contract.get("health_exception", []):
        subject = str(exception.get("id") or exception.get("metric") or "health_exception")
        for field in ("id", "owner", "reason", "expires"):
            if exception.get(field) in (None, "", []):
                errors.append(
                    Finding(
                        "contract",
                        "error",
                        subject,
                        f"health exception missing `{field}`",
                    )
                )
        if not any(exception.get(field) for field in ("metric", "gate", "source_glob")):
            errors.append(
                Finding(
                    "contract",
                    "error",
                    subject,
                    "health exception must name metric, gate, or source_glob",
                )
            )
        if (
            exception.get("kind") == PHASE_LOCAL_JUNK_EXCEPTION_KIND
            and exception.get("scratch_policy") != PHASE_LOCAL_JUNK_SCRATCH_POLICY
        ):
            errors.append(
                Finding(
                    "contract",
                    "error",
                    subject,
                    "phase-local-junk exception must declare "
                    '`scratch_policy = "explicitly_ignored"`',
                )
            )
        expires = str(exception.get("expires", ""))
        if expires:
            try:
                expiry = date.fromisoformat(expires)
            except ValueError:
                errors.append(
                    Finding("contract", "error", subject, "health exception expires is invalid")
                )
            else:
                if expiry < today:
                    errors.append(
                        Finding("contract", "error", subject, "health exception is expired")
                    )
    return errors


def _collect_closure_findings(
    repo_root: Path,
    contract: dict[str, Any],
    directory_contracts: dict[str, Any],
    generated_artifacts: dict[str, Any],
) -> list[Finding]:
    findings: list[Finding] = []
    thresholds = contract.get("thresholds", {})
    contract_paths = {
        str(item.get("path", "")): item for item in directory_contracts.get("contract", [])
    }
    actual_top_level_dirs = {
        path.name
        for path in repo_root.iterdir()
        if path.is_dir() and path.name not in SKIP_DIR_NAMES and path.name != ".git"
    }
    for dirname in sorted(actual_top_level_dirs - set(contract_paths)):
        findings.append(
            Finding(
                "top-level-directory-contract",
                "report_only",
                dirname,
                "top-level directory has no directory contract",
            )
        )

    allowed_loose = {str(item) for item in thresholds.get("allowed_root_loose_files", [])}
    for relative in _tracked_files(repo_root):
        if "/" in relative or not (repo_root / relative).exists():
            continue
        if relative not in allowed_loose:
            findings.append(
                Finding(
                    "top-level-loose-file-allow-list",
                    "blocker",
                    relative,
                    "tracked root loose file is outside the allow-list",
                )
            )

    forbidden_roots = {
        path
        for path, item in contract_paths.items()
        if item.get("topology_commit_policy") == "ignored"
        or item.get("owner") == "local"
        or item.get("status") == "local_only"
    }
    for relative in _tracked_files(repo_root):
        if not (repo_root / relative).exists():
            continue
        root = relative.split("/", 1)[0]
        if root in forbidden_roots:
            findings.append(
                Finding(
                    "forbidden-lifecycle-commits",
                    "blocker",
                    relative,
                    "tracked file lives under a directory lifecycle that forbids commits",
                )
            )

    findings.extend(_non_product_init_findings(repo_root, thresholds))
    findings.extend(_product_import_findings(repo_root, contract))
    findings.extend(_data_only_test_findings(repo_root, thresholds))
    findings.extend(_frontend_fixture_findings(repo_root, thresholds))
    findings.extend(_generated_api_findings(repo_root, generated_artifacts))
    findings.extend(_empty_ui_component_findings(repo_root, thresholds))
    findings.extend(_feature_owner_findings(repo_root, thresholds))
    findings.extend(_schema_pure_data_findings(repo_root))
    findings.extend(_phase_local_junk_findings(repo_root, contract))
    return findings


def _non_product_init_findings(repo_root: Path, thresholds: dict[str, Any]) -> list[Finding]:
    allowed_roots = {
        str(item).rstrip("/")
        for item in thresholds.get("allowed_non_product_init_roots", [])
    }
    findings: list[Finding] = []
    for path in _walk_files(repo_root):
        if path.name != "__init__.py":
            continue
        relative = _rel(path, repo_root)
        if relative.startswith("src/polisyos/"):
            continue
        root = relative.split("/", 1)[0]
        if root not in allowed_roots:
            findings.append(
                Finding(
                    "non-product-init-files",
                    "blocker",
                    relative,
                    "__init__.py lives outside product and allowed non-product roots",
                )
            )
    return findings


def _product_import_findings(repo_root: Path, contract: dict[str, Any]) -> list[Finding]:
    exception_patterns = [
        str(item.get("source_glob", ""))
        for item in contract.get("health_exception", [])
        if item.get("kind") == "product_import_non_product" and item.get("source_glob")
    ]
    findings: list[Finding] = []
    for path in _walk_files(repo_root, "src/polisyos"):
        if path.suffix != ".py":
            continue
        relative = _rel(path, repo_root)
        if _path_matches_any(relative, exception_patterns):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            findings.append(
                Finding(
                    "product-imports-tests-benchmarks",
                    "blocker",
                    relative,
                    "source file could not be parsed",
                    str(exc),
                )
            )
            continue
        for node in ast.walk(tree):
            module = ""
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
                offenders = [name for name in imported if _is_forbidden_product_import(name)]
                if offenders:
                    module = ", ".join(offenders)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                if _is_forbidden_product_import(node.module):
                    module = node.module
            if module:
                findings.append(
                    Finding(
                        "product-imports-tests-benchmarks",
                        "blocker",
                        relative,
                        "product code imports from tests or benchmarks",
                        module,
                    )
                )
                break
    return findings


def _is_forbidden_product_import(module: str) -> bool:
    return (
        module == "tests"
        or module.startswith("tests.")
        or module == "benchmarks"
        or module.startswith("benchmarks.")
    )


def _data_only_test_findings(repo_root: Path, thresholds: dict[str, Any]) -> list[Finding]:
    roots = [str(item).rstrip("/") for item in thresholds.get("data_only_roots", [])]
    names = {str(item) for item in thresholds.get("data_only_directory_names", [])}
    findings: list[Finding] = []
    for path in _walk_files(repo_root):
        if path.suffix != ".py" or not _is_pytest_collectable(path):
            continue
        relative = _rel(path, repo_root)
        parts = set(Path(relative).parts)
        if _path_matches_any(relative, roots) or parts.intersection(names):
            findings.append(
                Finding(
                    "data-only-pytest-collectable",
                    "blocker",
                    relative,
                    "data-only directory contains a pytest-collectable test",
                )
            )
    return findings


def _is_pytest_collectable(path: Path) -> bool:
    return path.name.startswith("test_") or path.name.endswith("_test.py")


def _frontend_fixture_findings(repo_root: Path, thresholds: dict[str, Any]) -> list[Finding]:
    registered = [
        str(item).rstrip("/")
        for item in thresholds.get("registered_frontend_fixture_roots", [])
        if item
    ]
    findings: list[Finding] = []
    for directory in _walk_dirs(repo_root):
        relative = _rel(directory, repo_root)
        parts = Path(relative).parts
        if len(parts) < 3 or "src" not in parts:
            continue
        if parts[0] not in {"apps", "packages", "frontend"}:
            continue
        if "node_modules" in parts:
            continue
        lowered = {part.lower() for part in parts}
        if {"fixtures", "__fixtures__"}.isdisjoint(lowered):
            continue
        if not _path_matches_any(relative, registered):
            findings.append(
                Finding(
                    "frontend-src-fixture-registration",
                    "blocker",
                    relative,
                    "frontend src fixture directory is not registered",
                )
            )
    return findings


def _generated_api_findings(
    repo_root: Path,
    generated_artifacts: dict[str, Any],
) -> list[Finding]:
    registered_outputs = [
        str(output).rstrip("/")
        for family in generated_artifacts.get("family", [])
        for output in family.get("outputs", [])
        if _looks_like_generated_api_output(str(output))
    ]
    findings: list[Finding] = []
    for path in _walk_files(repo_root):
        relative = _rel(path, repo_root)
        if not relative.startswith(("apps/", "packages/", "frontend/")):
            continue
        if not _looks_like_generated_api_file(relative, path):
            continue
        if not _path_matches_any(relative, registered_outputs):
            findings.append(
                Finding(
                    "generated-api-placement",
                    "blocker",
                    relative,
                    "generated API client or type file is outside registered generated paths",
                )
            )
    return findings


def _looks_like_generated_api_output(relative: str) -> bool:
    return any(fnmatch.fnmatch(relative, pattern) for pattern in GENERATED_API_PATTERNS)


def _looks_like_generated_api_file(relative: str, path: Path) -> bool:
    if _looks_like_generated_api_output(relative):
        return True
    if path.suffix not in {".ts", ".tsx", ".js", ".mjs"}:
        return False
    if "api" not in {part.lower() for part in Path(relative).parts}:
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")[:1000]
    return "GENERATED FILE" in text or "auto-generated by openapi-typescript" in text


def _empty_ui_component_findings(repo_root: Path, thresholds: dict[str, Any]) -> list[Finding]:
    ignored_roots = [
        str(item).rstrip("/") for item in thresholds.get("ignored_empty_directory_roots", [])
    ]
    findings: list[Finding] = []
    for directory in _walk_dirs(repo_root):
        relative = _rel(directory, repo_root)
        if _path_matches_any(relative, ignored_roots):
            continue
        parts = Path(relative).parts
        if len(parts) < 3 or parts[0] not in {"apps", "packages", "frontend"} or "src" not in parts:
            continue
        if directory.name.lower() not in UI_COMPONENT_DIR_NAMES:
            continue
        try:
            next(directory.iterdir())
        except StopIteration:
            findings.append(
                Finding(
                    "empty-ui-component-directory",
                    "blocker",
                    relative,
                    "UI component directory is empty",
                )
            )
    return findings


def _feature_owner_findings(repo_root: Path, thresholds: dict[str, Any]) -> list[Finding]:
    threshold = int(thresholds.get("feature_module_file_threshold", 25))
    owner_files = {str(item) for item in thresholds.get("feature_owner_file_names", [])}
    findings: list[Finding] = []
    for features_root in sorted(repo_root.glob("apps/*/src/features")) + sorted(
        repo_root.glob("frontend/*/src/features")
    ):
        if not features_root.is_dir():
            continue
        for feature in sorted(path for path in features_root.iterdir() if path.is_dir()):
            files = [
                path
                for path in _walk_files(repo_root, _rel(feature, repo_root))
                if not _rel(path, repo_root).startswith("node_modules/")
            ]
            if len(files) <= threshold:
                continue
            if not any((feature / filename).exists() for filename in owner_files):
                findings.append(
                    Finding(
                        "feature-module-owner-threshold",
                        "blocker",
                        _rel(feature, repo_root),
                        "feature module is over threshold without an owner document",
                        f"files={len(files)} threshold={threshold}",
                    )
                )
    return findings


def _schema_pure_data_findings(repo_root: Path) -> list[Finding]:
    schema_root = repo_root / "schemas"
    if not schema_root.exists():
        return []
    findings: list[Finding] = []
    for path in sorted(item for item in schema_root.rglob("__pycache__") if item.is_dir()):
        findings.append(
            Finding(
                "schema-only-root",
                "blocker",
                _rel(path, repo_root),
                "top-level schemas/ must not contain Python code or cache residue",
            )
        )
    for path in sorted(item for item in schema_root.rglob("*") if item.is_file()):
        if "__pycache__" in path.parts:
            continue
        if (
            path.name == "__init__.py"
            or path.suffix == ".py"
            or path.suffix in {".pyc", ".pyo"}
        ):
            findings.append(
                Finding(
                    "schema-only-root",
                    "blocker",
                    _rel(path, repo_root),
                    "top-level schemas/ must not contain Python code or cache residue",
                )
            )
        elif path.suffix not in SCHEMA_DATA_SUFFIXES:
            findings.append(
                Finding(
                    "schema-only-root",
                    "blocker",
                    _rel(path, repo_root),
                    "top-level schemas/ may contain only schema data, manifests, "
                    "snapshots, and schema documentation",
                )
            )
        if path.suffix == ".py":
            for module in _schema_python_product_imports(path):
                findings.append(
                    Finding(
                        "schema-only-root",
                        "blocker",
                        _rel(path, repo_root),
                        "top-level schemas/ Python residue must not import product modules",
                        module,
                    )
                )
    return findings


def _schema_python_product_imports(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    except SyntaxError:
        return []
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(
                alias.name
                for alias in node.names
                if alias.name == "polisyos" or alias.name.startswith("polisyos.")
            )
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module == "polisyos" or node.module.startswith("polisyos."):
                imports.add(node.module)
    return sorted(imports)


def _phase_local_junk_findings(repo_root: Path, contract: dict[str, Any]) -> list[Finding]:
    exception_patterns = [
        str(item.get("source_glob", "")).rstrip("/")
        for item in contract.get("health_exception", [])
        if item.get("kind") == PHASE_LOCAL_JUNK_EXCEPTION_KIND
        and item.get("scratch_policy") == PHASE_LOCAL_JUNK_SCRATCH_POLICY
        and item.get("source_glob")
    ]
    findings: list[Finding] = []
    build_root = repo_root / "_build"
    if not build_root.exists():
        return findings
    for directory in sorted(
        path for path in build_root.glob(PHASE_LOCAL_JUNK_PATTERN) if path.is_dir()
    ):
        relative = _rel(directory, repo_root)
        if _path_matches_any(relative, exception_patterns):
            continue
        findings.append(
            Finding(
                "phase-local-junk-residue",
                "blocker",
                relative,
                "phase-local-junk build residue must be deleted or registered as a dated "
                "scratch exception",
            )
        )
    return findings


def _build_dashboard(
    repo_root: Path,
    contract: dict[str, Any],
    directory_contracts: dict[str, Any],
    hygiene: dict[str, Any],
) -> dict[str, Any]:
    thresholds = contract.get("thresholds", {})
    tracked = [path for path in _tracked_files(repo_root) if (repo_root / path).exists()]
    contracts = {
        str(item.get("path", "")): item for item in directory_contracts.get("contract", [])
    }
    actual_top_level_dirs = sorted(
        path.name
        for path in repo_root.iterdir()
        if path.is_dir() and path.name not in SKIP_DIR_NAMES and path.name != ".git"
    )
    covered_top_level_dirs = [root for root in actual_top_level_dirs if root in contracts]
    high_volume = _high_volume_subtrees(repo_root, thresholds)
    documented_high_volume = [item for item in high_volume if item["documented"]]
    closure_findings = _collect_closure_findings(
        repo_root,
        contract,
        directory_contracts,
        _read_toml(GENERATED_ARTIFACTS),
    )
    closure_counts = _closure_counts(closure_findings)
    local_residue_by_class = _local_residue_by_class(repo_root, hygiene, thresholds)
    asset_counts = _asset_counts(hygiene)
    empty_dirs = _empty_dirs_outside_ignored_roots(repo_root, thresholds)
    frontend_undocumented = _undocumented_frontend_subtrees(repo_root, thresholds)
    max_depth_by_root = _max_directory_depth_by_root(repo_root)
    max_depth = max(max_depth_by_root.values(), default=0)
    largest_subtrees = _largest_subtrees_by_tracked_file_count(repo_root, tracked, thresholds)

    metrics: dict[str, int | float] = {
        "top_level_directory_contract_coverage_percent": _percent(
            len(covered_top_level_dirs), len(actual_top_level_dirs)
        ),
        "high_volume_subtree_documentation_coverage_percent": _percent(
            len(documented_high_volume), len(high_volume)
        ),
        "non_product_python_root_count": len(_non_product_python_root_inventory(repo_root)),
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
        "non_product_python_roots": _non_product_python_root_inventory(repo_root),
        "local_residue_by_class": local_residue_by_class,
        "empty_directories_outside_ignored_roots": empty_dirs,
        "asset_counts": asset_counts,
        "undocumented_frontend_subtrees": frontend_undocumented,
        "max_directory_depth_by_root": max_depth_by_root,
        "largest_subtrees_by_tracked_file_count": largest_subtrees,
    }


def _percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 100.0
    return round((numerator / denominator) * 100.0, 2)


def _closure_counts(findings: list[Finding]) -> dict[str, int]:
    by_check: dict[str, int] = {}
    for finding in findings:
        by_check[finding.check] = by_check.get(finding.check, 0) + 1
    return {
        "closure_top_level_loose_file_count": by_check.get(
            "top-level-loose-file-allow-list", 0
        ),
        "closure_forbidden_lifecycle_commit_count": by_check.get(
            "forbidden-lifecycle-commits", 0
        ),
        "closure_non_product_init_count": by_check.get("non-product-init-files", 0),
        "closure_forbidden_product_import_count": by_check.get(
            "product-imports-tests-benchmarks", 0
        ),
        "closure_data_only_pytest_count": by_check.get("data-only-pytest-collectable", 0),
        "closure_unregistered_frontend_fixture_count": by_check.get(
            "frontend-src-fixture-registration", 0
        ),
        "closure_unregistered_generated_api_count": by_check.get(
            "generated-api-placement", 0
        ),
        "closure_empty_ui_component_directory_count": by_check.get(
            "empty-ui-component-directory", 0
        ),
        "closure_over_threshold_feature_without_owner_count": by_check.get(
            "feature-module-owner-threshold", 0
        ),
        "closure_phase_local_junk_count": by_check.get("phase-local-junk-residue", 0),
    }


def _local_residue_by_class(
    repo_root: Path,
    hygiene: dict[str, Any],
    thresholds: dict[str, Any],
) -> dict[str, int]:
    classes = dict(hygiene.get("classes", {}).get("counts", {}))
    residue_roots = {str(item).rstrip("/") for item in thresholds.get("source_residue_roots", [])}
    ignored_source = {
        _stable_residue_key(relative)
        for relative in _ignored_files(repo_root)
        if relative.split("/", 1)[0] in residue_roots
        and "__pycache__" not in Path(relative).parts
    }
    residue_dirs = [
        _rel(path, repo_root)
        for root in residue_roots
        for path in _walk_dirs(repo_root, root)
        if path.name == ".DS_Store"
    ]
    classes["ignored_source_docs_schemas_tests"] = len(
        set(ignored_source).union(residue_dirs)
    )
    return {key: int(value) for key, value in sorted(classes.items())}


def _stable_residue_key(relative: str) -> str:
    parts = Path(relative).parts
    if "__pycache__" in parts:
        index = parts.index("__pycache__")
        return "/".join(parts[: index + 1])
    return relative


def _asset_counts(hygiene: dict[str, Any]) -> dict[str, int]:
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


def _empty_dirs_outside_ignored_roots(repo_root: Path, thresholds: dict[str, Any]) -> list[str]:
    ignored_roots = [
        str(item).rstrip("/") for item in thresholds.get("ignored_empty_directory_roots", [])
    ]
    empty: list[str] = []
    for directory in _walk_dirs(repo_root):
        relative = _rel(directory, repo_root)
        if relative == "." or _path_matches_any(relative, ignored_roots):
            continue
        try:
            next(directory.iterdir())
        except StopIteration:
            empty.append(relative)
    return sorted(empty)


def _high_volume_subtrees(repo_root: Path, thresholds: dict[str, Any]) -> list[dict[str, Any]]:
    tracked_threshold = int(thresholds.get("high_volume_tracked_files", 20))
    child_threshold = int(thresholds.get("high_volume_child_directories", 10))
    tracked = [path for path in _tracked_files(repo_root) if (repo_root / path).exists()]
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
                "documented": any((path / doc).exists() for doc in DOC_FILENAMES),
            }
        )
    return rows


def _non_product_python_root_inventory(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    contracts = _read_toml(repo_root / "architecture" / "policies" / "directory_contracts.toml")
    roots = sorted(
        str(item.get("path", ""))
        for item in contracts.get("non_product_python_root", [])
        if str(item.get("path", ""))
    )
    for root in roots:
        path = repo_root / root
        if not path.exists():
            continue
        init_files = sorted(_rel(item, repo_root) for item in path.rglob("__init__.py"))
        rows.append(
            {
                "root": root,
                "exists": path.exists(),
                "init_file_count": len(init_files),
                "sample_init_files": init_files[:10],
            }
        )
    return rows


def _undocumented_frontend_subtrees(repo_root: Path, thresholds: dict[str, Any]) -> list[str]:
    tracked_threshold = int(thresholds.get("high_volume_tracked_files", 20))
    rows: list[str] = []
    for frontend_root in thresholds.get("frontend_subtree_doc_roots", []):
        root = repo_root / str(frontend_root)
        if not root.exists():
            continue
        for src_root in sorted(root.glob("*/src")):
            for child in sorted(path for path in src_root.iterdir() if path.is_dir()):
                files = _walk_files(repo_root, _rel(child, repo_root))
                if len(files) < tracked_threshold:
                    continue
                if not any((child / doc).exists() for doc in DOC_FILENAMES):
                    rows.append(_rel(child, repo_root))
    return sorted(rows)


def _max_directory_depth_by_root(repo_root: Path) -> dict[str, int]:
    depths: dict[str, int] = {}
    for directory in _walk_dirs(repo_root):
        relative = _rel(directory, repo_root)
        if relative == ".":
            continue
        parts = Path(relative).parts
        root = parts[0]
        depths[root] = max(depths.get(root, 0), len(parts))
    return depths


def _largest_subtrees_by_tracked_file_count(
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


def _metric_regressions(contract: dict[str, Any], metrics: dict[str, int | float]) -> list[Finding]:
    exceptions = {
        str(item.get("metric", ""))
        for item in contract.get("health_exception", [])
        if item.get("metric")
    }
    regressions: list[Finding] = []
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
                Finding(
                    "directory-health-regression",
                    "blocker",
                    metric_id,
                    "metric decreased below baseline",
                    f"observed={observed} baseline={expected}",
                )
            )
        if direction == "not_increase" and observed > expected:
            regressions.append(
                Finding(
                    "directory-health-regression",
                    "blocker",
                    metric_id,
                    "metric increased above baseline",
                    f"observed={observed} baseline={expected}",
                )
            )
    return regressions


if __name__ == "__main__":
    sys.exit(main())
