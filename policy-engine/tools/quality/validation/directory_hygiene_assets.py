#!/usr/bin/env python3
"""Report Phase 2.9 directory hygiene, asset placement, and local residue state."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
CONTRACT_PATH = Path("architecture/asset_placement.toml")
SOURCE_ADJACENT_ROOTS = (
    "apps",
    "architecture",
    "benchmarks",
    "data",
    "docs",
    "examples",
    "frontend",
    "ops",
    "packages",
    "release",
    "release-fragments",
    "schemas",
    "src",
    "tests",
    "tools",
)
SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".hypothesis",
    ".benchmarks",
    ".basedpyright",
    ".cache",
    ".uv-cache",
    ".venv",
    ".venv_codex",
    ".tmp_c7_venv",
    "node_modules",
    ".next",
    ".turbo",
    "_build",
    "_cache",
    ".polisyos",
}
RESIDUE_SKIP_DIR_NAMES = SKIP_DIR_NAMES - {"_build", "_cache", ".polisyos"}
ASSET_HINT_PARTS = {"assets", "fixtures", "resources", "seeds", "seed_data"}
DATA_SUFFIXES = {
    ".csv",
    ".json",
    ".jsonl",
    ".md",
    ".toml",
    ".tsv",
    ".txt",
    ".yaml",
    ".yml",
}
AMBIGUOUS_FIXTURE_DIR_NAMES = {"cache", "errors", "raw"}
LOCAL_REPORT_PREFIXES = (
    ".polisyos/reports/",
    ".polisyos/audits/",
    "benchmarks/_reports/",
    "_build/benchmark-results/",
)


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


def build_report(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    contract = _read_toml(repo_root / CONTRACT_PATH)
    contract_errors = _validate_contract(repo_root, contract)
    inventory = _collect_inventory(repo_root, contract)
    findings = _validate_inventory(repo_root, contract, inventory)
    return {
        "phase": "2.9",
        "mode": "report_only",
        "status": "contract_errors" if contract_errors else "reported",
        "contract_error_count": len(contract_errors),
        "finding_count": len(findings),
        "contract_errors": [finding.as_dict() for finding in contract_errors],
        "findings": [finding.as_dict() for finding in findings],
        "classes": {
            "counts": {
                key: len(value)
                for key, value in sorted(inventory["classes"].items())
                if isinstance(value, list)
            },
            "rows": inventory["classes"],
        },
        "budgets": inventory["budgets"],
        "cleanup": inventory["cleanup"],
    }


def dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Directory Hygiene And Asset Placement Report",
        "",
        f"- Phase: `{payload['phase']}`",
        f"- Mode: `{payload['mode']}`",
        f"- Status: `{payload['status']}`",
        f"- Contract errors: {payload['contract_error_count']}",
        f"- Findings: {payload['finding_count']}",
        "",
        "## Classes",
        "",
        "| Class | Count |",
        "| --- | ---: |",
    ]
    for name, count in payload["classes"]["counts"].items():
        lines.append(f"| `{name}` | {count} |")
    lines.extend(
        [
            "",
            "## Product Asset Budgets",
            "",
            f"- Total bytes: {payload['budgets']['product_assets']['total_bytes']}",
            f"- Max file bytes: {payload['budgets']['product_assets']['max_file_bytes']}",
            f"- Max total bytes: {payload['budgets']['product_assets']['max_total_bytes']}",
            "",
            "## Cleanup",
            "",
            f"- Residue candidates: {payload['cleanup']['residue_count']}",
            f"- Local report candidates: {payload['cleanup']['local_report_count']}",
            f"- Owner-approved audit candidates: {payload['cleanup']['owner_approved_audit_count']}",
            "",
            "## Findings",
            "",
        ]
    )
    if not payload["contract_errors"] and not payload["findings"]:
        lines.append("- none")
    for item in payload["contract_errors"] + payload["findings"]:
        detail = f" ({item['detail']})" if item.get("detail") else ""
        lines.append(
            f"- `{item['severity']}` `{item['check']}` `{item['subject']}`: {item['message']}{detail}"
        )
    lines.append("")
    return "\n".join(lines)


def run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--fail-on-contract-errors", action="store_true")
    parser.add_argument("--fail-on-findings", action="store_true")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    payload = build_report(repo_root)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(dump_json(payload), encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(payload), encoding="utf-8")

    print(
        "directory-hygiene-assets: "
        f"{payload['status']} "
        f"contract_errors={payload['contract_error_count']} "
        f"findings={payload['finding_count']}"
    )
    if args.fail_on_contract_errors and payload["contract_error_count"]:
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
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _walk_files(root: Path, *, skip_dir_names: set[str] = SKIP_DIR_NAMES) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in skip_dir_names]
        for filename in filenames:
            files.append(Path(current) / filename)
    return sorted(files)


def _walk_dirs(root: Path, *, skip_dir_names: set[str] = SKIP_DIR_NAMES) -> list[Path]:
    if not root.exists():
        return []
    dirs: list[Path] = []
    for current, dirnames, _filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in skip_dir_names]
        dirs.append(Path(current))
    return sorted(dirs)


def _source_adjacent_paths(repo_root: Path) -> list[Path]:
    roots = [repo_root / root for root in SOURCE_ADJACENT_ROOTS if (repo_root / root).exists()]
    paths: list[Path] = []
    for root in roots:
        paths.extend(_walk_files(root, skip_dir_names=RESIDUE_SKIP_DIR_NAMES))
    return sorted(paths)


def _source_adjacent_dirs(repo_root: Path) -> list[Path]:
    roots = [repo_root / root for root in SOURCE_ADJACENT_ROOTS if (repo_root / root).exists()]
    dirs: list[Path] = []
    for root in roots:
        dirs.extend(_walk_dirs(root, skip_dir_names=RESIDUE_SKIP_DIR_NAMES))
    return sorted(dirs)


def _path_matches_root(relative: str, pattern: str) -> bool:
    normalized = pattern.rstrip("/")
    normalized = normalized.replace("<package>", "*").replace("<example-name>", "*")
    if any(token in normalized for token in "*?["):
        return fnmatch.fnmatch(relative, normalized) or fnmatch.fnmatch(
            relative, f"{normalized}/**"
        )
    return relative == normalized or relative.startswith(f"{normalized}/")


def _path_matches_any(relative: str, patterns: list[str]) -> bool:
    return any(_path_matches_root(relative, pattern) for pattern in patterns)


def _file_has_asset_hint(relative: str) -> bool:
    path = Path(relative)
    if path.suffix.lower() not in DATA_SUFFIXES:
        return False
    parts = {part.lower() for part in relative.split("/")}
    if parts & ASSET_HINT_PARTS:
        return True
    lowered = path.name.lower()
    return any(token in lowered for token in ("fixture", "golden", "seed", "snapshot"))


def _tracked_files(repo_root: Path) -> list[str]:
    return sorted(_git_lines(repo_root, "ls-files"))


def _ignored_files(repo_root: Path) -> list[str]:
    return sorted(_git_lines(repo_root, "ls-files", "-o", "-i", "--exclude-standard"))


def _asset_classes(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id", "")): item for item in contract.get("asset_class", [])}


def _registered_product_fixtures(contract: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in contract.get("registered_product_fixture", [])]


def _validate_contract(repo_root: Path, contract: dict[str, Any]) -> list[Finding]:
    errors: list[Finding] = []
    header = contract.get("asset_placement", {})
    for field in (
        "version",
        "status",
        "phase",
        "owner",
        "directory_contracts_source",
        "test_ratchets_source",
        "generated_artifacts_source",
        "local_runtime_state_source",
        "validator_command",
        "cleanup_command",
    ):
        if header.get(field) in (None, "", []):
            errors.append(Finding("contract", "error", "asset_placement", f"missing `{field}`"))
    if header.get("status") != "report_only":
        errors.append(
            Finding(
                "contract",
                "error",
                "asset_placement",
                "status must be report_only",
                str(header.get("status")),
            )
        )
    for field in (
        "directory_contracts_source",
        "test_ratchets_source",
        "generated_artifacts_source",
        "local_runtime_state_source",
    ):
        value = str(header.get(field, ""))
        if value and not (repo_root / value).exists():
            errors.append(Finding("contract", "error", value, "source contract is missing"))

    budgets = contract.get("budgets", {})
    for field in (
        "default_max_product_asset_file_bytes",
        "default_max_product_asset_total_bytes",
        "local_report_stale_days",
        "benchmark_report_stale_days",
    ):
        if int(budgets.get(field, 0) or 0) <= 0:
            errors.append(Finding("contract", "error", "budgets", f"`{field}` must be positive"))
    if not budgets.get("allowed_product_asset_suffixes"):
        errors.append(Finding("contract", "error", "budgets", "missing allowed suffixes"))

    classes = _asset_classes(contract)
    required_classes = {
        "product_seed_assets",
        "test_fixtures",
        "golden_records",
        "examples_tutorial_assets",
        "local_reports",
        "generated_benchmark_reports",
    }
    for class_id in sorted(required_classes - set(classes)):
        errors.append(Finding("contract", "error", class_id, "missing asset class"))
    for class_id, item in classes.items():
        for field in ("owner", "review_class", "commit_policy", "promotion_rule"):
            if item.get(field) in (None, "", []):
                errors.append(Finding("contract", "error", class_id, f"missing `{field}`"))
        if not item.get("allowed_roots") and not item.get("local_roots"):
            errors.append(Finding("contract", "error", class_id, "missing roots"))

    for item in _registered_product_fixtures(contract):
        subject = str(item.get("id") or item.get("path") or "registered_product_fixture")
        for field in ("path", "owner", "rename_decision", "contract_reason", "source_contracts"):
            if item.get(field) in (None, "", []):
                errors.append(Finding("contract", "error", subject, f"missing `{field}`"))
        path = repo_root / str(item.get("path", ""))
        if not path.exists():
            errors.append(Finding("contract", "error", subject, "registered path is missing"))
        for source in item.get("source_contracts", []):
            if not (repo_root / str(source)).exists():
                errors.append(
                    Finding("contract", "error", subject, "source contract is missing", str(source))
                )

    for item in contract.get("cleanup_surface", []):
        subject = str(item.get("id") or "cleanup_surface")
        for field in ("owner", "paths", "dry_run_command", "promotion_target"):
            if item.get(field) in (None, "", []):
                errors.append(Finding("contract", "error", subject, f"missing `{field}`"))
    return errors


def _collect_inventory(repo_root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    tracked = _tracked_files(repo_root)
    ignored = _ignored_files(repo_root)
    classes = {
        "product_seed_assets": [],
        "test_fixtures": [],
        "golden_records": [],
        "examples_tutorial_assets": [],
        "local_reports": [],
        "generated_benchmark_reports": [],
        "source_adjacent_residue": [],
        "ambiguous_fixture_directories": [],
    }

    for relative in tracked:
        if relative.startswith("src/polisyos/") and _file_has_asset_hint(relative):
            classes["product_seed_assets"].append(relative)
        if relative.startswith("tests/_data/") or (
            relative.startswith("tests/") and "/fixtures/" in relative
        ):
            classes["test_fixtures"].append(relative)
        if relative.startswith("tests/_golden/") or (
            relative.startswith("tests/") and ("/golden/" in relative or "/snapshots/" in relative)
        ):
            classes["golden_records"].append(relative)
        if relative.startswith("examples/"):
            classes["examples_tutorial_assets"].append(relative)

    for relative in ignored:
        if relative.startswith(".polisyos/reports/") or relative.startswith(".polisyos/audits/"):
            classes["local_reports"].append(relative)
        if relative.startswith("benchmarks/_reports/") or relative.startswith(
            "_build/benchmark-results/"
        ):
            classes["generated_benchmark_reports"].append(relative)
        if _is_under_source_adjacent_root(relative) and _is_source_adjacent_residue(relative):
            classes["source_adjacent_residue"].append(relative)

    for path in _source_adjacent_paths(repo_root):
        relative = _rel(path, repo_root)
        if _is_source_adjacent_residue(relative):
            classes["source_adjacent_residue"].append(relative)
    for directory in _source_adjacent_dirs(repo_root):
        relative = _rel(directory, repo_root)
        if _is_ambiguous_fixture_dir(relative):
            classes["ambiguous_fixture_directories"].append(relative)

    classes = {key: sorted(set(value)) for key, value in classes.items()}
    product_budget = _product_asset_budget(repo_root, contract, classes["product_seed_assets"])
    cleanup = {
        "residue_count": len(classes["source_adjacent_residue"]),
        "local_report_count": len(classes["local_reports"])
        + len(classes["generated_benchmark_reports"]),
        "owner_approved_audit_count": len(
            [path for path in classes["local_reports"] if path.startswith(".polisyos/audits/")]
        ),
    }
    return {"classes": classes, "budgets": {"product_assets": product_budget}, "cleanup": cleanup}


def _is_source_adjacent_residue(relative: str) -> bool:
    path = Path(relative)
    return (
        path.name == ".DS_Store"
        or "__pycache__" in path.parts
        or any(part.endswith(".egg-info") for part in path.parts)
    )


def _is_under_source_adjacent_root(relative: str) -> bool:
    parts = relative.split("/")
    return parts[0] in SOURCE_ADJACENT_ROOTS and not any(part in SKIP_DIR_NAMES for part in parts)


def _is_ambiguous_fixture_dir(relative: str) -> bool:
    path = Path(relative)
    parts = {part.lower() for part in path.parts}
    return "fixtures" in parts and path.name.lower() in AMBIGUOUS_FIXTURE_DIR_NAMES


def _product_asset_budget(
    repo_root: Path, contract: dict[str, Any], product_assets: list[str]
) -> dict[str, Any]:
    classes = _asset_classes(contract)
    product_class = classes.get("product_seed_assets", {})
    max_file_bytes = int(
        product_class.get("max_file_bytes")
        or contract.get("budgets", {}).get("default_max_product_asset_file_bytes", 0)
    )
    max_total_bytes = int(
        product_class.get("max_total_bytes")
        or contract.get("budgets", {}).get("default_max_product_asset_total_bytes", 0)
    )
    rows: list[dict[str, Any]] = []
    total = 0
    for relative in product_assets:
        path = repo_root / relative
        size = path.stat().st_size if path.exists() else 0
        total += size
        rows.append({"path": relative, "bytes": size, "suffix": path.suffix.lower()})
    return {
        "file_count": len(product_assets),
        "total_bytes": total,
        "max_file_bytes": max_file_bytes,
        "max_total_bytes": max_total_bytes,
        "files": rows,
    }


def _validate_inventory(
    repo_root: Path,
    contract: dict[str, Any],
    inventory: dict[str, Any],
) -> list[Finding]:
    findings: list[Finding] = []
    classes = _asset_classes(contract)
    product_class = classes.get("product_seed_assets", {})
    allowed_product_roots = [
        *product_class.get("allowed_roots", []),
        *product_class.get("registered_exception_roots", []),
        *(item["path"] for item in _registered_product_fixtures(contract) if item.get("path")),
    ]
    allowed_suffixes = {
        str(suffix).lower() for suffix in product_class.get("allowed_suffixes", [])
    } or {
        str(suffix).lower()
        for suffix in contract.get("budgets", {}).get("allowed_product_asset_suffixes", [])
    }
    forbidden_suffixes = {
        str(suffix).lower()
        for suffix in contract.get("budgets", {}).get("forbidden_product_asset_suffixes", [])
    }

    for relative in inventory["classes"]["product_seed_assets"]:
        path = repo_root / relative
        suffix = path.suffix.lower()
        if not _path_matches_any(relative, allowed_product_roots):
            findings.append(
                Finding(
                    "product-asset-placement",
                    "report_only",
                    relative,
                    "product asset is outside package assets/ and registered product fixture roots",
                )
            )
        if suffix not in allowed_suffixes or suffix in forbidden_suffixes:
            findings.append(
                Finding(
                    "product-asset-budget",
                    "report_only",
                    relative,
                    "product asset suffix is outside the committed budget",
                    suffix or "<none>",
                )
            )
        size = path.stat().st_size if path.exists() else 0
        max_file_bytes = inventory["budgets"]["product_assets"]["max_file_bytes"]
        if size > max_file_bytes:
            findings.append(
                Finding(
                    "product-asset-budget",
                    "report_only",
                    relative,
                    "product asset exceeds max file budget",
                    f"bytes={size} max={max_file_bytes}",
                )
            )

    total = inventory["budgets"]["product_assets"]["total_bytes"]
    max_total = inventory["budgets"]["product_assets"]["max_total_bytes"]
    if total > max_total:
        findings.append(
            Finding(
                "product-asset-budget",
                "report_only",
                "product_seed_assets",
                "product assets exceed total committed budget",
                f"bytes={total} max={max_total}",
            )
        )

    allowed_ambiguous = [
        str(item.get("path_pattern", ""))
        for item in contract.get("ambiguous_fixture_directory", [])
        if item.get("path_pattern")
    ]
    for relative in inventory["classes"]["ambiguous_fixture_directories"]:
        if not _path_matches_any(relative, allowed_ambiguous):
            findings.append(
                Finding(
                    "ambiguous-fixture-directory",
                    "report_only",
                    relative,
                    "cache/raw/errors fixture directory has no explicit contract",
                )
            )

    for relative in inventory["classes"]["source_adjacent_residue"]:
        findings.append(
            Finding(
                "source-adjacent-residue",
                "report_only",
                relative,
                "local residue is cleanup eligible and must not be promoted",
            )
        )
    return findings


if __name__ == "__main__":
    sys.exit(main())
