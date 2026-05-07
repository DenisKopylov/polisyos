#!/usr/bin/env python3
"""Fail-closed Phase 6.1 package, public-surface, and import gates."""

from __future__ import annotations

import argparse
import copy
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import repo_root_from
from tools.quality.validation import architecture_report_only_contracts

REPO_ROOT = repo_root_from(__file__)
DEFAULT_CONTRACT = REPO_ROOT / "architecture" / "package_import_gates.toml"
PHASE = "repository-best-in-class-phase-6.1"
GATE_COMMAND = "uv run polisyos-tools validation check-package-import-gates --fail-closed"
REQUIRED_GATE_IDS = {
    "root-facade-package-layout",
    "package-boundary",
    "public-surface",
    "deep-import",
    "dynamic-import",
    "import-cycle",
    "package-layout",
    "name-collision",
    "shim-expiry",
    "importable-root-contracts",
    "schema-only-root",
    "module-size-ratchet",
    "scientist-first-level-package-count",
}
REQUIRED_SUMMARY_KEYS = {
    "import_boundary",
    "package_boundary",
    "dynamic_imports",
    "import_cycles",
    "package_layout",
    "name_collisions",
    "shim_debt",
    "phase6_1",
    "importable_roots",
    "schema_only",
    "root_file_exceptions",
    "scientist_layout",
    "module_size_ratchet",
}
IGNORED_TOP_LEVEL_ROOTS = {
    ".cursor",
    ".devcontainer",
    ".git",
    ".hypothesis",
    ".mypy_cache",
    ".polisyos",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".vscode",
    "_build",
    "_cache",
    "__pycache__",
    "node_modules",
}


@dataclass(frozen=True)
class Finding:
    check: str
    subject: str
    message: str
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "check": self.check,
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
    contract_path = _resolve(repo_root, contract_path)
    contract = _read_toml(contract_path)
    findings: list[Finding] = []

    findings.extend(_check_conversion_contract(repo_root, contract_path, contract))
    legacy_report = architecture_report_only_contracts.build_report(
        repo_root,
        report="phase6-1",
        enforce_import_boundary_deltas=True,
    )
    summary = copy.deepcopy(legacy_report.get("summary", {}))
    _mark_summary_fail_closed(summary)
    findings.extend(_legacy_contract_findings(legacy_report))
    extension_checks = {
        "importable_roots": _check_importable_root_contracts(repo_root),
        "schema_only": _check_schema_only_root(repo_root),
        "root_file_exceptions": _check_root_file_exceptions(repo_root),
        "scientist_layout": _check_scientist_first_level_roots(repo_root),
        "module_size_ratchet": _check_module_size_ratchet(repo_root),
    }
    for key, check_findings in extension_checks.items():
        summary[key] = _finding_summary(check_findings)
        findings.extend(check_findings)
    findings.extend(_check_summary_blockers(summary))

    return {
        "phase": PHASE,
        "mode": "fail_closed",
        "status": "failed" if findings else "passed",
        "contract": _relative(contract_path, repo_root),
        "finding_count": len(findings),
        "findings": [finding.as_dict() for finding in findings],
        "summary": summary,
    }


def dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--fail-closed", action="store_true")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    contract_path = _resolve(repo_root, args.contract)
    payload = build_report(repo_root, contract_path=contract_path)
    rendered = dump_json(payload)

    if args.json_output is not None:
        output = _resolve(repo_root, args.json_output)
        atomic_write_text(output, rendered)
    else:
        print(rendered, end="")  # noqa: T201

    if args.fail_closed and payload["finding_count"]:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    return run_cli(argv)


def _check_conversion_contract(
    repo_root: Path,
    contract_path: Path,
    contract: dict[str, Any],
) -> list[Finding]:
    findings: list[Finding] = []
    subject = _relative(contract_path, repo_root)
    header = contract.get("package_import_gates", {})
    expected = {
        "status": "fail_closed",
        "phase": PHASE,
        "gate_command": GATE_COMMAND,
    }
    for field, expected_value in expected.items():
        if header.get(field) != expected_value:
            findings.append(
                Finding(
                    "conversion-contract",
                    subject,
                    f"`{field}` must be {expected_value!r}",
                    str(header.get(field, "")),
                )
            )
    if header.get("active_source_move_report_only_blockers") != []:
        findings.append(
            Finding(
                "conversion-contract",
                subject,
                "active source-move blockers must be empty before fail-closed conversion",
                str(header.get("active_source_move_report_only_blockers", "")),
            )
        )
    for field in ("owner", "source_contracts"):
        if not header.get(field):
            findings.append(Finding("conversion-contract", subject, f"`{field}` is required"))
    for raw_path in header.get("source_contracts", []):
        if not _path_or_glob_exists(repo_root, str(raw_path)):
            findings.append(
                Finding(
                    "conversion-contract",
                    subject,
                    "source contract path is missing",
                    str(raw_path),
                )
            )

    gates = {str(gate.get("id", "")): gate for gate in contract.get("gate", [])}
    missing = sorted(REQUIRED_GATE_IDS - set(gates))
    if missing:
        findings.append(
            Finding(
                "conversion-contract",
                subject,
                "missing converted gate ids",
                ", ".join(missing),
            )
        )
    for gate_id, gate in sorted(gates.items()):
        if gate_id not in REQUIRED_GATE_IDS:
            continue
        if gate.get("mode") != "fail_closed":
            findings.append(Finding("conversion-contract", gate_id, "gate is not fail_closed"))
        owner = str(gate.get("owner", ""))
        if not owner.startswith("team-"):
            findings.append(
                Finding("conversion-contract", gate_id, "`owner` must be a team owner", owner)
            )
        for field in ("source_contracts", "blocks"):
            if not gate.get(field):
                findings.append(Finding("conversion-contract", gate_id, f"`{field}` is required"))
        for raw_path in gate.get("source_contracts", []):
            if not _path_or_glob_exists(repo_root, str(raw_path)):
                findings.append(
                    Finding(
                        "conversion-contract",
                        gate_id,
                        "source contract path is missing",
                        str(raw_path),
                    )
                )
    return findings


def _legacy_contract_findings(report: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for item in report.get("contract_errors", []):
        findings.append(
            Finding(
                str(item.get("check", "contract")),
                str(item.get("subject", "architecture_report_only_contracts")),
                str(item.get("message", "contract error")),
                str(item.get("detail", "")),
            )
        )
    return findings


def _check_summary_blockers(summary: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    missing = sorted(REQUIRED_SUMMARY_KEYS - set(summary))
    if missing:
        return [
            Finding(
                "phase6-1-summary",
                "architecture_report_only_contracts",
                "missing Phase 6.1 summary sections",
                ", ".join(missing),
            )
        ]

    import_boundary = summary["import_boundary"]
    hidden_growth = _as_int(import_boundary.get("unregistered_added_hidden_edge_count"))
    if hidden_growth:
        findings.append(
            Finding(
                "deep-import",
                "architecture/deep_import_baseline.json",
                "unregistered hidden cross-package import growth",
                str(hidden_growth),
            )
        )
    surface_contract = import_boundary.get("public_surface_import_contract", {})
    surface_drift = _as_int(surface_contract.get("drift_count"))
    inventory_drift = _as_int(surface_contract.get("inventory_drift_count"))
    if surface_drift or inventory_drift:
        findings.append(
            Finding(
                "public-surface",
                "architecture/public_surface.toml",
                "public-surface inventory and import contracts disagree",
                f"drift={surface_drift} inventory_drift={inventory_drift}",
            )
        )

    package_boundary = summary["package_boundary"]
    forbidden_growth = _as_int(package_boundary.get("unregistered_forbidden_edge_count"))
    if forbidden_growth:
        findings.append(
            Finding(
                "package-boundary",
                "architecture/package_boundaries.toml",
                "unregistered forbidden package edges",
                str(forbidden_growth),
            )
        )

    dynamic_imports = summary["dynamic_imports"]
    missing_dynamic_targets = _as_int(dynamic_imports.get("missing_target_slots"))
    if missing_dynamic_targets:
        findings.append(
            Finding(
                "dynamic-import",
                "architecture/dynamic_imports.toml",
                "registered dynamic import slots are missing target ids",
                str(missing_dynamic_targets),
            )
        )

    import_cycles = summary["import_cycles"]
    new_cycles = _as_int(import_cycles.get("new_cycle_count"))
    if new_cycles:
        findings.append(
            Finding(
                "import-cycle",
                "architecture/imports/lazy.toml",
                "new import cycles outside the allow-list",
                str(new_cycles),
            )
        )

    package_layout = summary["package_layout"]
    layout_findings = _as_int(package_layout.get("finding_count"))
    if layout_findings:
        findings.append(
            Finding(
                "package-layout",
                "architecture/package_layout.toml",
                "package layout findings remain outside registered exceptions",
                _render_examples(package_layout.get("findings", [])),
            )
        )

    name_collisions = summary["name_collisions"]
    collision_findings = _as_int(name_collisions.get("finding_count"))
    if collision_findings:
        findings.append(
            Finding(
                "name-collision",
                "architecture/name_registry.toml",
                "name collision findings remain outside registry/backlog",
                _render_examples(name_collisions.get("findings", [])),
            )
        )

    shim_debt = summary["shim_debt"]
    expired_shims = _as_int(shim_debt.get("expired_count"))
    if expired_shims:
        findings.append(
            Finding(
                "shim-expiry",
                "architecture/shims.toml",
                "expired shims remain without owner-approved renewal",
                str(expired_shims),
            )
        )
    return findings


def _check_importable_root_contracts(repo_root: Path) -> list[Finding]:
    contracts_path = repo_root / "architecture" / "directory_contracts.toml"
    if not contracts_path.exists():
        return []
    data = _read_toml(contracts_path)
    contracts = {str(item.get("path", "")): item for item in data.get("contract", [])}
    non_product_roots = {
        str(item.get("path", "")): item for item in data.get("non_product_python_root", [])
    }
    findings: list[Finding] = []
    for child in sorted(path for path in repo_root.iterdir() if path.is_dir()):
        name = child.name
        if name in IGNORED_TOP_LEVEL_ROOTS or name.startswith(".") and name != ".polisyos":
            continue
        if name not in contracts:
            findings.append(
                Finding(
                    "importable-root-contracts",
                    name,
                    "top-level importable or namespace-capable root lacks a directory contract",
                )
            )
            continue
        if name == "src":
            continue
        py_files = sorted(child.rglob("*.py"))
        init_files = sorted(child.rglob("__init__.py"))
        if (py_files or init_files) and name not in non_product_roots:
            findings.append(
                Finding(
                    "importable-root-contracts",
                    name,
                    "importable Python root outside src/polisyos lacks non_product_python_root policy",
                    f"python_files={len(py_files)} init_files={len(init_files)}",
                )
            )
    for root, item in sorted(non_product_roots.items()):
        path = repo_root / root
        if not path.exists():
            findings.append(
                Finding(
                    "importable-root-contracts",
                    root,
                    "non_product_python_root policy points at a missing root",
                )
            )
        for field in ("policy", "owner", "allowed_reason", "product_import_policy"):
            if not str(item.get(field, "")).strip():
                findings.append(
                    Finding(
                        "importable-root-contracts",
                        root,
                        f"non_product_python_root policy missing `{field}`",
                    )
                )
    return findings


def _check_schema_only_root(repo_root: Path) -> list[Finding]:
    schema_root = repo_root / "schemas"
    if not schema_root.exists():
        return []
    findings: list[Finding] = []
    for path in sorted(schema_root.rglob("*.py")):
        findings.append(
            Finding(
                "schema-only-root",
                _relative(path, repo_root),
                "top-level schemas/ may contain schemas and generated snapshots, not Python code",
            )
        )
    for path in sorted(schema_root.rglob("__init__.py")):
        findings.append(
            Finding(
                "schema-only-root",
                _relative(path, repo_root),
                "top-level schemas/ must not become an importable Python package",
            )
        )
    return findings


def _check_root_file_exceptions(repo_root: Path) -> list[Finding]:
    layout_path = repo_root / "architecture" / "package_layout.toml"
    if not layout_path.exists():
        return []
    layout = _read_toml(layout_path)
    defaults = layout.get("defaults", {})
    allowed_names = {
        str(item) for item in defaults.get("allowed_root_py_files", ["__init__.py", "api.py"])
    }
    exceptions = {
        str(item.get("path", "")): item for item in layout.get("root_file_exception", [])
    }
    registered_shims = _registered_shim_paths(repo_root)
    findings: list[Finding] = []
    for rel, item in sorted(exceptions.items()):
        if not rel:
            findings.append(
                Finding("root-file-exception", "architecture/package_layout.toml", "empty path")
            )
            continue
        for field in ("owner", "sunset", "reason"):
            if not str(item.get(field, "")).strip():
                findings.append(
                    Finding("root-file-exception", rel, f"root-file exception missing `{field}`")
                )
        if not (repo_root / rel).exists():
            findings.append(
                Finding("root-file-exception", rel, "root-file exception path is missing")
            )

    source_root = repo_root / "src" / "polisyos"
    if not source_root.exists():
        return findings
    for path in sorted(source_root.glob("*/*.py")):
        rel = _relative(path, repo_root)
        if path.name in allowed_names:
            continue
        if rel in registered_shims:
            continue
        if rel in exceptions:
            continue
        findings.append(
            Finding(
                "root-file-exception",
                rel,
                "package root Python file is neither an allowed facade, registered shim, nor dated root-file exception",
            )
        )
    return findings


def _check_scientist_first_level_roots(repo_root: Path) -> list[Finding]:
    scientist_root = repo_root / "src" / "polisyos" / "scientist"
    contract_path = repo_root / "architecture" / "packages" / "scientist.toml"
    if not scientist_root.exists() or not contract_path.exists():
        return []
    contract = _read_toml(contract_path)
    layout = contract.get("layout", {})
    canonical = set(layout.get("canonical_first_level_roots", []))
    canonical.update(_first_level_scientist_roots(layout.get("implementation_roots", [])))
    compatibility = set(_first_level_scientist_roots(layout.get("compatibility_shim_roots", [])))
    ignored = {str(item) for item in layout.get("ignored_first_level_roots", [])}
    cap = _as_int(layout.get("canonical_first_level_root_cap")) or len(canonical)
    findings: list[Finding] = []
    if len(canonical) > cap:
        findings.append(
            Finding(
                "scientist-layout",
                "architecture/packages/scientist.toml",
                "Scientist canonical first-level root count exceeds the configured cap",
                f"canonical={len(canonical)} cap={cap}",
            )
        )
    for path in sorted(item for item in scientist_root.iterdir() if item.is_dir()):
        rel = _relative(path, repo_root)
        if path.name in ignored:
            continue
        if rel in canonical or rel in compatibility:
            continue
        findings.append(
            Finding(
                "scientist-layout",
                rel,
                "Scientist first-level root is not canonical, registered compatibility debt, or explicitly ignored",
            )
        )
    return findings


def _check_module_size_ratchet(repo_root: Path) -> list[Finding]:
    budget_path = repo_root / "architecture" / "module_size_budget.toml"
    if not budget_path.exists():
        return []
    data = _read_toml(budget_path)
    findings: list[Finding] = []
    for budget in data.get("budget", []):
        relative = str(budget.get("path", ""))
        if not relative:
            continue
        path = repo_root / relative
        if not path.exists():
            findings.append(
                Finding("module-size-ratchet", relative, "budgeted module is missing")
            )
            continue
        current = _count_lines(path)
        current_budget = _as_int(budget.get("current_lines"))
        if current_budget and current > current_budget:
            findings.append(
                Finding(
                    "module-size-ratchet",
                    relative,
                    "module grew above its ratcheted current_lines budget",
                    f"current={current} budget={current_budget}",
                )
            )
        report_only_limit = _as_int(budget.get("report_only_limit_lines"))
        if report_only_limit and current > report_only_limit:
            findings.append(
                Finding(
                    "module-size-ratchet",
                    relative,
                    "module grew above its report_only_limit_lines ratchet",
                    f"current={current} limit={report_only_limit}",
                )
            )
    return findings


def _mark_summary_fail_closed(summary: dict[str, Any]) -> None:
    for key in ("import_boundary", "package_boundary", "package_layout", "name_collisions"):
        if isinstance(summary.get(key), dict):
            summary[key]["mode"] = "fail_closed"
    if isinstance(summary.get("phase6_1"), dict):
        summary["phase6_1"]["status"] = "fail_closed_conversion"
        summary["phase6_1"]["gate_command"] = GATE_COMMAND
        summary["phase6_1"]["active_source_move_report_only_blockers"] = []


def _finding_summary(findings: list[Finding]) -> dict[str, Any]:
    return {
        "mode": "fail_closed",
        "finding_count": len(findings),
        "findings": [finding.as_dict() for finding in findings],
    }


def _registered_shim_paths(repo_root: Path) -> set[str]:
    path = repo_root / "architecture" / "shims.toml"
    if not path.exists():
        return set()
    data = _read_toml(path)
    paths: set[str] = set()
    for item in data.get("shim", []):
        for field in ("source_path", "target_path"):
            value = str(item.get(field, ""))
            if value.endswith(".py"):
                paths.add(value)
    return paths


def _first_level_scientist_roots(values: object) -> set[str]:
    roots: set[str] = set()
    if not isinstance(values, list):
        return roots
    prefix = Path("src/polisyos/scientist")
    for value in values:
        path = Path(str(value))
        try:
            relative = path.relative_to(prefix)
        except ValueError:
            continue
        if not relative.parts:
            continue
        roots.add((prefix / relative.parts[0]).as_posix())
    return roots


def _render_examples(value: object) -> str:
    if not isinstance(value, list) or not value:
        return ""
    return json.dumps(value[:5], sort_keys=True)


def _as_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _count_lines(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for _line in handle)


def _read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _relative(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _path_or_glob_exists(repo_root: Path, pattern: str) -> bool:
    if any(char in pattern for char in "*?["):
        return bool(list(repo_root.glob(pattern)))
    path = Path(pattern)
    if path.is_absolute():
        return path.exists()
    return (repo_root / path).exists()


if __name__ == "__main__":
    raise SystemExit(main())
