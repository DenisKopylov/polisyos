#!/usr/bin/env python3
"""Fail-closed Phase 6.1 package, public-surface, and import gates."""

from __future__ import annotations

import argparse
import ast
import copy
import json
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import repo_root_from
from tools.quality.validation import architecture_report_only_contracts

REPO_ROOT = repo_root_from(__file__)
DEFAULT_CONTRACT = REPO_ROOT / "architecture" / "gates" / "package_import.toml"
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
    "single-file-shell-package",
    "cross-cutting-concern-home",
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
    "scientist_root_facade",
    "scientist_root_files",
    "single_file_shell_packages",
    "ir_refs_references_collision",
    "module_size_ratchet",
    "cross_cutting_concerns",
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
SCHEMA_DATA_SUFFIXES = {".json", ".md", ".toml", ".yaml", ".yml"}
SCHEMA_PYTHON_CACHE_SUFFIXES = {".pyc", ".pyo"}


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


@dataclass(frozen=True)
class ConcernHome:
    name: str
    file_name: str
    canonical_home: str


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
    scientist_layout_findings = _check_scientist_first_level_roots(repo_root)
    scientist_root_file_findings = _check_scientist_root_python_files(repo_root)
    extension_checks = {
        "importable_roots": _check_importable_root_contracts(repo_root),
        "schema_only": _check_schema_only_root(repo_root),
        "root_file_exceptions": _check_root_file_exceptions(repo_root),
        "scientist_layout": scientist_layout_findings,
        "scientist_root_files": scientist_root_file_findings,
        "single_file_shell_packages": _check_single_file_shell_packages(repo_root),
        "ir_refs_references_collision": _check_ir_refs_references_collision(repo_root),
        "module_size_ratchet": _check_module_size_ratchet(repo_root),
        "cross_cutting_concerns": _check_cross_cutting_concern_homes(repo_root),
    }
    for key, check_findings in extension_checks.items():
        summary[key] = _finding_summary(check_findings)
        findings.extend(check_findings)
    summary["scientist_root_facade"] = _scientist_root_facade_summary(
        repo_root,
        layout_findings=scientist_layout_findings,
        root_file_findings=scientist_root_file_findings,
    )
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
                "architecture/baselines/imports/deep_import.json",
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
                "architecture/public_surface/contract.toml",
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
                "architecture/packages/boundaries.toml",
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
                "architecture/imports/dynamic.toml",
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
                "architecture/packages/layout.toml",
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
    contracts_path = repo_root / "architecture" / "policies" / "directory_contracts.toml"
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
        if name in IGNORED_TOP_LEVEL_ROOTS or (
            name.startswith(".") and name != ".polisyos"
        ):
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
                    "importable Python root outside src/polisyos lacks "
                    "non_product_python_root policy",
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
    for path in sorted(item for item in schema_root.rglob("__pycache__") if item.is_dir()):
        findings.append(
            Finding(
                "schema-only-root",
                _relative(path, repo_root),
                "top-level schemas/ must not contain Python cache residue",
            )
        )
    for path in sorted(item for item in schema_root.rglob("*") if item.is_file()):
        if "__pycache__" in path.parts:
            continue
        if path.name == "__init__.py":
            findings.append(
                Finding(
                    "schema-only-root",
                    _relative(path, repo_root),
                    "top-level schemas/ must not become an importable Python package",
                )
            )
        elif path.suffix == ".py":
            findings.append(
                Finding(
                    "schema-only-root",
                    _relative(path, repo_root),
                    "top-level schemas/ may contain schemas and generated snapshots, not Python code",
                )
            )
        elif path.suffix in SCHEMA_PYTHON_CACHE_SUFFIXES:
            findings.append(
                Finding(
                    "schema-only-root",
                    _relative(path, repo_root),
                    "top-level schemas/ must not contain Python cache residue",
                )
            )
        elif path.suffix not in SCHEMA_DATA_SUFFIXES:
            findings.append(
                Finding(
                    "schema-only-root",
                    _relative(path, repo_root),
                    "top-level schemas/ may contain only schema data, manifests, snapshots, "
                    "and schema documentation",
                )
            )
        if path.suffix == ".py":
            for module in _python_product_imports(path):
                findings.append(
                    Finding(
                        "schema-only-root",
                        _relative(path, repo_root),
                        "top-level schemas/ Python residue must not import product modules",
                        module,
                    )
                )
    return findings


def _python_product_imports(path: Path) -> list[str]:
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


def _check_root_file_exceptions(repo_root: Path) -> list[Finding]:
    layout_path = repo_root / "architecture" / "packages" / "layout.toml"
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
                Finding("root-file-exception", "architecture/packages/layout.toml", "empty path")
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
                "package root Python file is neither an allowed facade, registered shim, "
                "nor dated root-file exception",
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
                "Scientist first-level root is not canonical, registered compatibility debt, "
                "or explicitly ignored",
            )
        )
    return findings


def _check_scientist_root_python_files(repo_root: Path) -> list[Finding]:
    scientist_root = repo_root / "src" / "polisyos" / "scientist"
    contract_path = repo_root / "architecture" / "packages" / "scientist.toml"
    if not scientist_root.exists() or not contract_path.exists():
        return []

    contract = _read_toml(contract_path)
    layout = contract.get("layout", {})
    status = str(layout.get("status", ""))
    allowed_names = _allowed_root_py_filenames(repo_root)
    compatibility_paths = {str(item) for item in layout.get("compatibility_shim_roots", [])}
    registered_shims = _registered_shim_paths(repo_root)
    wave2_debt = _scientist_root_facade_debt(contract)

    findings: list[Finding] = _check_scientist_root_facade_debt_entries(
        repo_root,
        contract,
        registered_shims=registered_shims,
        compatibility_paths=compatibility_paths,
    )
    if status == "resolved_root_facade" and wave2_debt:
        findings.append(
            Finding(
                "scientist-root-file",
                "architecture/packages/scientist.toml",
                "resolved_root_facade may not retain Scientist Wave 2 root file debt",
                f"debt_count={len(wave2_debt)}",
            )
        )
    for path in sorted(scientist_root.glob("*.py")):
        rel = _relative(path, repo_root)
        if path.name in allowed_names:
            continue
        if status == "resolved_root_facade" and rel in registered_shims:
            continue
        if rel in wave2_debt and rel in registered_shims:
            continue
        findings.append(
            Finding(
                "scientist-root-file",
                rel,
                "Scientist root Python file is neither an allowed facade nor a registered "
                "compatibility shim",
            )
        )
    return findings


def _check_scientist_root_facade_debt_entries(
    repo_root: Path,
    contract: dict[str, Any],
    *,
    registered_shims: set[str],
    compatibility_paths: set[str],
) -> list[Finding]:
    findings: list[Finding] = []
    for item in contract.get("root_facade_wave2_debt", []):
        if not isinstance(item, dict):
            findings.append(
                Finding(
                    "scientist-root-file",
                    "architecture/packages/scientist.toml",
                    "Scientist root-facade debt entry must be a table",
                )
            )
            continue
        rel = str(item.get("path", ""))
        subject = rel or "architecture/packages/scientist.toml"
        for field in ("path", "target_path", "owner", "wave", "sunset", "reason"):
            if not str(item.get(field, "")).strip():
                findings.append(
                    Finding(
                        "scientist-root-file",
                        subject,
                        f"Scientist root-facade Wave 2 debt missing `{field}`",
                    )
                )
        if not rel:
            continue
        if not rel.startswith("src/polisyos/scientist/") or not rel.endswith(".py"):
            findings.append(
                Finding(
                    "scientist-root-file",
                    rel,
                    "Scientist root-facade Wave 2 debt must point at a root Python file",
                )
            )
        path = repo_root / rel
        if not path.exists():
            findings.append(
                Finding(
                    "scientist-root-file",
                    rel,
                    "Scientist root-facade Wave 2 debt path is missing",
                )
            )
        elif path.parent != repo_root / "src" / "polisyos" / "scientist":
            findings.append(
                Finding(
                    "scientist-root-file",
                    rel,
                    "Scientist root-facade Wave 2 debt must remain at the package root",
                )
            )
        sunset = str(item.get("sunset", ""))
        if sunset and not _date_is_today_or_future(sunset):
            findings.append(
                Finding(
                    "scientist-root-file",
                    rel,
                    "Scientist root-facade Wave 2 debt sunset is expired or invalid",
                    sunset,
                )
            )
        if rel not in registered_shims:
            findings.append(
                Finding(
                    "scientist-root-file",
                    rel,
                    "Scientist root-facade Wave 2 debt must be backed by a registered shim",
                )
            )
        if rel in compatibility_paths:
            findings.append(
                Finding(
                    "scientist-root-file",
                    rel,
                    "Scientist root-facade Wave 2 debt must not be listed as a "
                    "compatibility shim root",
                )
            )
    return findings


def _check_single_file_shell_packages(repo_root: Path) -> list[Finding]:
    policy_source, contract = _single_file_shell_policy_contract(repo_root)
    if policy_source is None:
        return []

    policy = contract.get("single_file_shell_package_policy", {})
    if policy.get("status") != "fail_closed":
        return []

    scope_roots = [str(item).rstrip("/") for item in policy.get("scope_roots", []) if item]
    max_python_files = _as_int(policy.get("max_python_files")) or 1
    allowed_facades = {
        str(item).rstrip("/") for item in policy.get("allowed_facade_packages", []) if item
    }
    exception_required_fields = [
        str(item)
        for item in policy.get(
            "exception_required_fields",
            policy.get("required_fields", ["path", "owner", "sunset", "reason"]),
        )
    ]
    latest_allowed_sunset = str(
        policy.get(
            "latest_allowed_sunset",
            policy.get("wrapper_only_created_from_loose_file_disallowed_after", ""),
        )
    )
    exceptions = _single_file_shell_package_exceptions(contract)
    readme_policy = _single_file_shell_local_documentation_policy(repo_root)
    new_contract_message = policy_source.name == "package_import.toml"

    findings: list[Finding] = []
    for rel, item in sorted(exceptions.items()):
        if not rel:
            findings.append(
                Finding(
                    "single-file-shell-package",
                    _relative(policy_source, repo_root),
                    "single-file shell package exception has an empty path",
                )
            )
            continue
        for field in exception_required_fields:
            if not str(item.get(field, "")).strip():
                findings.append(
                    Finding(
                        "single-file-shell-package",
                        rel,
                        f"single-file shell package exception missing `{field}`",
                    )
                )
        sunset = str(item.get("sunset", ""))
        if sunset and not _date_is_today_or_future(sunset):
            findings.append(
                Finding(
                    "single-file-shell-package",
                    rel,
                    "single-file shell package exception sunset is expired or invalid",
                    sunset,
                )
            )
        if sunset and latest_allowed_sunset and _date_is_after(sunset, latest_allowed_sunset):
            findings.append(
                Finding(
                    "single-file-shell-package",
                    rel,
                    "single-file shell package exception sunset must be no later than "
                    "the Wave 3 cutoff",
                    f"sunset={sunset} cutoff={latest_allowed_sunset}",
                )
            )
        smoke_import_test = str(item.get("smoke_import_test", ""))
        if smoke_import_test:
            smoke_finding = _smoke_import_test_finding(repo_root, rel, smoke_import_test)
            if smoke_finding is not None:
                message, detail = smoke_finding
                findings.append(Finding("single-file-shell-package", rel, message, detail))
        if not (repo_root / rel).exists():
            findings.append(
                Finding(
                    "single-file-shell-package",
                    rel,
                    "single-file shell package exception path is missing",
                )
            )

    for scope in scope_roots:
        root = repo_root / scope
        if not root.exists():
            continue
        candidate_dirs = [
            root,
            *sorted(path for path in root.rglob("*") if path.is_dir()),
        ]
        for directory in candidate_dirs:
            if not _is_single_file_shell_package(directory, max_python_files=max_python_files):
                continue
            rel = _relative(directory, repo_root)
            if rel in allowed_facades or rel in exceptions:
                continue
            if _has_intentional_single_file_shell_readme(directory, readme_policy):
                continue
            message = (
                "single-file shell package is neither an allowed facade, locally documented, "
                "nor covered by a dated exception"
                if new_contract_message
                else "single-file shell package is neither an allowed facade nor a dated exception"
            )
            findings.append(
                Finding(
                    "single-file-shell-package",
                    rel,
                    message,
                )
            )
    return findings


def _single_file_shell_policy_contract(repo_root: Path) -> tuple[Path | None, dict[str, Any]]:
    for relative in (
        "architecture/gates/package_import.toml",
        "architecture/packages/layout.toml",
    ):
        path = repo_root / relative
        if not path.exists():
            continue
        contract = _read_toml(path)
        if contract.get("single_file_shell_package_policy"):
            return path, contract
    return None, {}


def _single_file_shell_package_exceptions(
    contract: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    exceptions: dict[str, dict[str, Any]] = {}
    for item in contract.get("single_file_shell_package_exception", []):
        if not isinstance(item, dict):
            continue
        rel = str(item.get("path", "")).rstrip("/")
        exceptions[rel] = item
    for group in contract.get("single_file_shell_package_exception_group", []):
        if not isinstance(group, dict):
            continue
        for path in group.get("paths", []):
            rel = str(path).rstrip("/")
            expanded = {
                key: value
                for key, value in group.items()
                if key not in {"paths", "id", "description"}
            }
            expanded["path"] = rel
            exceptions[rel] = expanded
    return exceptions


def _single_file_shell_local_documentation_policy(repo_root: Path) -> dict[str, list[str]]:
    path = repo_root / "architecture" / "policies" / "directory_contracts.toml"
    section: dict[str, Any] = {}
    if path.exists():
        section = _read_toml(path).get("single_file_shell_package_local_documentation", {})
    documents = [
        str(item)
        for item in section.get("accepted_local_documents", ["README.md"])
        if str(item).strip()
    ]
    markers = [
        str(item).lower()
        for item in section.get("required_markers", ["single module", "intentional"])
        if str(item).strip()
    ]
    return {
        "accepted_local_documents": documents or ["README.md"],
        "required_markers": markers or ["single module", "intentional"],
    }


def _has_intentional_single_file_shell_readme(
    directory: Path,
    policy: dict[str, list[str]],
) -> bool:
    for document in policy["accepted_local_documents"]:
        path = directory / document
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").lower()
        if all(marker in text for marker in policy["required_markers"]):
            return True
    return False


def _smoke_import_test_finding(
    repo_root: Path,
    package_rel: str,
    nodeid: str,
) -> tuple[str, str] | None:
    path_text = nodeid.split("::", 1)[0]
    path = repo_root / path_text
    if not path.exists():
        return ("single-file shell package exception smoke_import_test path is missing", nodeid)
    if "::" in nodeid and not _pytest_nodeid_exists(path, nodeid.split("::", 1)[1]):
        return (
            "single-file shell package exception smoke_import_test node id is missing",
            nodeid,
        )
    expected_module = _source_package_path_to_module(package_rel)
    if expected_module and expected_module not in path.read_text(encoding="utf-8"):
        return (
            "single-file shell package exception smoke_import_test must reference "
            "the excepted package",
            f"expected={expected_module} nodeid={nodeid}",
        )
    return None


def _pytest_nodeid_exists(path: Path, node_path: str) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    except SyntaxError:
        return False

    body: list[ast.stmt] = list(tree.body)
    parts = [_strip_pytest_param(part) for part in node_path.split("::") if part]
    if not parts:
        return True
    for index, part in enumerate(parts):
        match = next(
            (
                node
                for node in body
                if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
                and node.name == part
            ),
            None,
        )
        if match is None:
            return False
        if index == len(parts) - 1:
            return True
        if isinstance(match, ast.ClassDef):
            body = list(match.body)
            continue
        return False
    return False


def _strip_pytest_param(part: str) -> str:
    return part.split("[", 1)[0]


def _source_package_path_to_module(package_rel: str) -> str:
    path = Path(package_rel)
    try:
        relative = path.relative_to("src")
    except ValueError:
        return ""
    return ".".join(relative.parts)


def _check_ir_refs_references_collision(repo_root: Path) -> list[Finding]:
    refs = repo_root / "src" / "polisyos" / "ir" / "refs"
    references = repo_root / "src" / "polisyos" / "ir" / "references"
    if not refs.exists() or not references.exists():
        return []

    contract_path = repo_root / "architecture" / "packages" / "ir.toml"
    contract = _read_toml(contract_path) if contract_path.exists() else {}
    if _has_dated_ir_refs_resolution(contract):
        return []

    return [
        Finding(
            "name-collision",
            "src/polisyos/ir/{refs,references}",
            "IR contains both refs/ and references/ without a dated collision resolution",
        )
    ]


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


def _check_cross_cutting_concern_homes(repo_root: Path) -> list[Finding]:
    contract_path = repo_root / "architecture" / "policies" / "cross_cutting_concerns.toml"
    source_root = repo_root / "src" / "polisyos"
    if not contract_path.exists() or not source_root.exists():
        return []

    contract = _read_toml(contract_path)
    home_contract = contract.get("canonical_home_contract", {})
    if home_contract.get("fail_closed") is not True:
        return []

    concern_by_file = _cross_cutting_concern_by_file_name(contract)
    blocked_names = {
        str(item)
        for item in home_contract.get("blocked_file_names", [])
        if str(item).strip()
    }
    concern_by_file = {
        file_name: concern
        for file_name, concern in concern_by_file.items()
        if file_name in blocked_names or not blocked_names
    }
    exceptions = _cross_cutting_scoped_exceptions(contract)
    findings = _cross_cutting_exception_findings(repo_root, exceptions)

    for directory in sorted(path for path in source_root.rglob("*") if path.is_dir()):
        rel_parts = directory.relative_to(source_root).parts
        if directory.name not in concern_by_file:
            continue
        if len(rel_parts) not in {1, 2}:
            continue
        concern = concern_by_file[directory.name]
        rel = _relative(directory, repo_root)
        if _is_canonical_concern_path(rel, concern, repo_root):
            continue
        if _has_cross_cutting_exception(exceptions, rel, concern):
            continue
        findings.append(
            Finding(
                "cross-cutting-concern-home",
                rel,
                "cross-cutting concern package is outside its canonical home and lacks "
                "a scoped exception",
                _cross_cutting_detail(concern),
            )
        )

    for path in sorted(source_root.rglob("*.py")):
        file_name = path.stem
        concern = concern_by_file.get(file_name)
        if concern is None:
            continue
        rel_parts = path.relative_to(source_root).parts
        rel = _relative(path, repo_root)
        if _is_canonical_concern_path(rel, concern, repo_root):
            continue
        if len(rel_parts) >= 3 and rel_parts[1] == "_adapters" and len(rel_parts) == 3:
            if not _file_imports_module(path, concern.canonical_home):
                findings.append(
                    Finding(
                        "cross-cutting-concern-adapter",
                        rel,
                        "cross-cutting concern adapter must import its canonical home",
                        _cross_cutting_detail(concern),
                    )
                )
            continue
        if _has_cross_cutting_exception(exceptions, rel, concern):
            continue
        if len(rel_parts) <= 2:
            findings.append(
                Finding(
                    "cross-cutting-concern-home",
                    rel,
                    "cross-cutting concern root is outside its canonical home and lacks "
                    "a scoped exception",
                    _cross_cutting_detail(concern),
                )
            )
            continue
        findings.append(
            Finding(
                "cross-cutting-concern-home",
                rel,
                "group-level cross-cutting concern file must live under "
                "<package>/_adapters/<concern>.py or carry a scoped exception",
                _cross_cutting_detail(concern),
            )
        )
    return findings


def _cross_cutting_concern_by_file_name(contract: dict[str, Any]) -> dict[str, ConcernHome]:
    concerns: dict[str, ConcernHome] = {}
    for raw_concern in contract.get("concern", []):
        if not isinstance(raw_concern, dict):
            continue
        name = str(raw_concern.get("name", "")).strip()
        canonical_home = str(
            raw_concern.get("canonical_home") or raw_concern.get("canonical_interface") or ""
        ).strip()
        if not name or not canonical_home:
            continue
        file_names = raw_concern.get("file_names")
        if not isinstance(file_names, list) or not file_names:
            file_names = [name]
        for raw_file_name in file_names:
            file_name = str(raw_file_name).strip()
            if not file_name:
                continue
            concerns.setdefault(
                file_name,
                ConcernHome(
                    name=name,
                    file_name=file_name,
                    canonical_home=canonical_home,
                ),
            )
    return concerns


def _cross_cutting_scoped_exceptions(contract: dict[str, Any]) -> list[dict[str, str]]:
    exceptions: list[dict[str, str]] = []
    for raw_item in contract.get("scoped_exception", []):
        if not isinstance(raw_item, dict):
            continue
        exceptions.append({str(key): str(value) for key, value in raw_item.items()})
    return exceptions


def _cross_cutting_exception_findings(
    repo_root: Path,
    exceptions: list[dict[str, str]],
) -> list[Finding]:
    findings: list[Finding] = []
    for item in exceptions:
        rel = str(item.get("path", ""))
        subject = rel or "architecture/policies/cross_cutting_concerns.toml"
        for field in ("concern", "path", "owner", "rationale", "sunset"):
            if not str(item.get(field, "")).strip():
                findings.append(
                    Finding(
                        "cross-cutting-concern-home",
                        subject,
                        f"scoped cross-cutting concern exception missing `{field}`",
                    )
                )
        sunset = str(item.get("sunset", "")).strip()
        if sunset and sunset != "none" and not _date_is_today_or_future(sunset):
            findings.append(
                Finding(
                    "cross-cutting-concern-home",
                    subject,
                    "scoped cross-cutting concern exception sunset is expired or invalid",
                    sunset,
                )
            )
        if rel and not (repo_root / rel).exists():
            findings.append(
                Finding(
                    "cross-cutting-concern-home",
                    rel,
                    "scoped cross-cutting concern exception path is missing",
                )
            )
    return findings


def _has_cross_cutting_exception(
    exceptions: list[dict[str, str]],
    rel: str,
    concern: ConcernHome,
) -> bool:
    valid_concern_names = {concern.name, concern.file_name}
    for item in exceptions:
        if str(item.get("path", "")) != rel:
            continue
        if str(item.get("concern", "")) in valid_concern_names:
            return True
    return False


def _is_canonical_concern_path(
    rel: str,
    concern: ConcernHome,
    repo_root: Path,
) -> bool:
    canonical_rel = _canonical_home_source_rel(repo_root, concern.canonical_home)
    return rel == canonical_rel or rel.startswith(f"{canonical_rel}/")


def _canonical_home_source_rel(repo_root: Path, module_name: str) -> str:
    source_root = repo_root / "src" / Path(*module_name.split("."))
    if source_root.with_suffix(".py").exists():
        return _relative(source_root.with_suffix(".py"), repo_root)
    return _relative(source_root, repo_root)


def _cross_cutting_detail(concern: ConcernHome) -> str:
    return f"concern={concern.file_name} canonical_home={concern.canonical_home}"


def _file_imports_module(path: Path, module_name: str) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    except SyntaxError:
        return False

    parent, _, leaf = module_name.rpartition(".")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module_name or alias.name.startswith(f"{module_name}."):
                    return True
        elif isinstance(node, ast.ImportFrom):
            imported_from = node.module or ""
            if imported_from == module_name or imported_from.startswith(f"{module_name}."):
                return True
            if imported_from == parent and any(alias.name == leaf for alias in node.names):
                return True
    return False


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


def _scientist_root_facade_summary(
    repo_root: Path,
    *,
    layout_findings: list[Finding],
    root_file_findings: list[Finding],
) -> dict[str, Any]:
    findings = [*layout_findings, *root_file_findings]
    summary = _finding_summary(findings)
    scientist_root = repo_root / "src" / "polisyos" / "scientist"
    contract_path = repo_root / "architecture" / "packages" / "scientist.toml"
    if not scientist_root.exists() or not contract_path.exists():
        summary.update(
            {
                "root_loose_py_count": 0,
                "canonical_first_level_root_count": 0,
                "compatibility_shim_root_count": 0,
                "registered_root_py_shim_count": 0,
                "registered_root_py_shim_files": [],
                "duplicate_package_file_pair_count": 0,
                "wave2_root_file_debt_count": 0,
                "unregistered_root_py_count": len(root_file_findings),
            }
        )
        return summary

    contract = _read_toml(contract_path)
    layout = contract.get("layout", {})
    allowed_names = _allowed_root_py_filenames(repo_root)
    loose_root_py_files = [
        _relative(path, repo_root)
        for path in sorted(scientist_root.glob("*.py"))
        if path.name not in allowed_names
    ]
    registered_shims = _registered_shim_paths(repo_root)
    registered_root_py_shims = [
        path for path in loose_root_py_files if path in registered_shims
    ]
    canonical_roots = {str(item) for item in layout.get("canonical_first_level_roots", [])}
    canonical_roots.update(_first_level_scientist_roots(layout.get("implementation_roots", [])))
    compatibility_roots = {
        str(item).rstrip("/")
        for item in layout.get("compatibility_shim_roots", [])
        if str(item).strip()
    }
    duplicate_pairs = _existing_scientist_duplicate_package_file_pairs(repo_root, contract)
    summary.update(
        {
            "root_loose_py_count": len(loose_root_py_files),
            "root_loose_py_files": loose_root_py_files,
            "canonical_first_level_root_count": len(canonical_roots),
            "compatibility_shim_root_count": len(compatibility_roots),
            "registered_root_py_shim_count": len(registered_root_py_shims),
            "registered_root_py_shim_files": registered_root_py_shims,
            "compatibility_shim_first_level_root_count": len(
                _first_level_scientist_roots(sorted(compatibility_roots))
            ),
            "duplicate_package_file_pair_count": len(duplicate_pairs),
            "duplicate_package_file_pairs": duplicate_pairs,
            "wave2_root_file_debt_count": len(_scientist_root_facade_debt(contract)),
            "unregistered_root_py_count": len(root_file_findings),
        }
    )
    return summary


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


def _allowed_root_py_filenames(repo_root: Path) -> set[str]:
    layout_path = repo_root / "architecture" / "packages" / "layout.toml"
    if not layout_path.exists():
        return {"__init__.py", "api.py", "_api.py"}
    layout = _read_toml(layout_path)
    defaults = layout.get("defaults", {})
    return {
        str(item)
        for item in defaults.get("allowed_root_py_files", ["__init__.py", "api.py", "_api.py"])
    }


def _root_file_exception_paths(repo_root: Path) -> set[str]:
    layout_path = repo_root / "architecture" / "packages" / "layout.toml"
    if not layout_path.exists():
        return set()
    layout = _read_toml(layout_path)
    return {
        str(item.get("path", ""))
        for item in layout.get("root_file_exception", [])
        if str(item.get("path", ""))
    }


def _scientist_root_facade_debt(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    debt: dict[str, dict[str, Any]] = {}
    for item in contract.get("root_facade_wave2_debt", []):
        if isinstance(item, dict) and str(item.get("path", "")):
            debt[str(item["path"])] = item
    return debt


def _existing_scientist_duplicate_package_file_pairs(
    repo_root: Path,
    contract: dict[str, Any],
) -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    for item in contract.get("duplicate_package_file_pair", []):
        if not isinstance(item, dict):
            continue
        package_path = str(item.get("package_path", ""))
        file_path = str(item.get("file_path", ""))
        if not package_path or not file_path:
            continue
        if not (repo_root / package_path).exists() or not (repo_root / file_path).exists():
            continue
        pairs.append(
            {
                "package_path": package_path,
                "file_path": file_path,
                "owner": str(item.get("owner", "")),
                "wave": str(item.get("wave", "")),
            }
        )
    return pairs


def _is_single_file_shell_package(directory: Path, *, max_python_files: int) -> bool:
    if not (directory / "__init__.py").is_file():
        return False
    python_files = [
        path for path in sorted(directory.glob("*.py")) if not _is_test_module(path)
    ]
    if len(python_files) > max_python_files:
        return False
    child_dirs = [
        child
        for child in directory.iterdir()
        if child.is_dir() and child.name not in {"__pycache__", ".mypy_cache", ".pytest_cache"}
    ]
    return not child_dirs


def _is_test_module(path: Path) -> bool:
    return path.name.startswith("test_") or path.name.endswith("_test.py")


def _has_dated_ir_refs_resolution(contract: dict[str, Any]) -> bool:
    for item in contract.get("allowed_name_collision", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", ""))
        roots = {str(root) for root in item.get("canonical_roots", [])}
        names_collision = name in {"refs-vs-references", "refs/references", "refs"}
        roots_collision = {
            "src/polisyos/ir/refs",
            "src/polisyos/ir/references",
        } <= roots
        if not names_collision and not roots_collision:
            continue
        if all(str(item.get(field, "")).strip() for field in ("owner", "reason", "sunset")):
            return _date_is_today_or_future(str(item["sunset"]))
    return False


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


def _date_is_today_or_future(value: str) -> bool:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return parsed >= date.today()


def _date_is_after(value: str, limit: str) -> bool:
    try:
        parsed = date.fromisoformat(value)
        parsed_limit = date.fromisoformat(limit)
    except ValueError:
        return False
    return parsed > parsed_limit


def _count_lines(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        return sum(
            1
            for line in handle
            if line.strip() and not line.lstrip().startswith("#")
        )


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
