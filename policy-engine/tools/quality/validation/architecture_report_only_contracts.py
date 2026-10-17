#!/usr/bin/env python3
"""Build report-only evidence for Architecture Phase 1.3 contracts."""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import re
import stat
import sys
import tomllib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from tools.lib.fs import AdmittedPathError, resolve_admitted_path, write_scoped_report_text
from tools.lib.imports import repo_root_from
from tools.quality.lint import lint_imports

REPO_ROOT = repo_root_from(__file__)
REPORTS = {
    "all",
    "packages",
    "package-mirrors",
    "module-size",
    "generated-artifacts",
    "extension-points",
    "runbook-coverage",
    "component-observability",
    "runtime-state-layout",
    "test-ratchets",
    "directory-contracts",
    "directory-hygiene-assets",
    "dependency-graph",
    "dynamic-imports",
    "import-cycles",
    "package-layout",
    "name-collisions",
    "shim-expiry",
    "phase6-1",
    "static-analysis-overrides",
}
PACKAGE_MIRROR_FAMILY_ID = "architecture-package-contract-aggregates"
PACKAGE_MIRROR_OUTPUTS = {
    "boundaries": "architecture/packages/boundaries.toml",
    "layout": "architecture/packages/layout.toml",
    "public_surface": "architecture/public_surface/contract.toml",
    "test_topology": "architecture/tests/topology.toml",
}
PACKAGE_MIRROR_SOURCE_OF_TRUTH = (
    "primary package contracts in architecture/packages/*.toml; "
    "registered family outputs are excluded"
)
PACKAGE_MIRROR_CHECK_COMMAND = (
    "uv",
    "run",
    "python",
    "tools/quality/validation/architecture_report_only_contracts.py",
    "--repo-root",
    ".",
    "--report",
    "package-mirrors",
    "--fail-on-package-mirror-errors",
)
_MISSING_VALUE = object()
_MirrorFieldDomain = Literal["string", "boolean", "string_list", "table"]
REQUIRED_PACKAGE_TABLES = (
    "package",
    "layout",
    "boundaries",
    "public_surface",
    "tests",
    "slo_runbook",
    "observability",
    "name_collisions",
    "exceptions",
    "sunsets",
    "extension_host",
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


@dataclass(frozen=True)
class _PackageMirrorFamilyAdmission:
    rows: tuple[dict[str, Any], ...]
    findings: tuple[Finding, ...]


def build_report(
    repo_root: Path = REPO_ROOT,
    *,
    report: str = "all",
    enforce_import_boundary_deltas: bool = False,
) -> dict[str, Any]:
    if report not in REPORTS:
        raise ValueError(f"unsupported report: {report}")

    findings: list[Finding] = []
    contract_errors: list[Finding] = []
    import_boundary_summary: dict[str, Any] | None = None
    package_boundary_summary: dict[str, Any] | None = None
    package_contract_findings: list[Finding] | None = None
    package_mirror_summary: dict[str, Any] | None = None
    legacy_operability_route_summary: dict[str, Any] | None = None

    def selected(name: str) -> bool:
        return report in {"all", name}

    def selected_any(*names: str) -> bool:
        return report == "all" or report in set(names)

    family_admission = _admit_package_mirror_family_registry(repo_root)
    if selected("packages"):
        package_contract_findings = _validate_package_contracts(
            repo_root, family_admission=family_admission
        )
        contract_errors.extend(package_contract_findings)
        if not selected("package-mirrors"):
            contract_errors.extend(
                _family_registry_findings(family_admission, check="package-mirror")
            )
    if selected("package-mirrors"):
        if package_contract_findings is None:
            package_contract_findings = _validate_package_contracts(
                repo_root, family_admission=family_admission
            )
            contract_errors.extend(package_contract_findings)
        mirror_findings, package_mirror_summary = _validate_package_mirror_projection(
            repo_root, family_admission=family_admission
        )
        contract_errors.extend(mirror_findings)
        scoped_errors = mirror_findings
        package_mirror_summary["status"] = "passed" if not scoped_errors else "failed"
        package_mirror_summary["error_count"] = len(scoped_errors)
        package_mirror_summary["errors"] = [finding.as_dict() for finding in scoped_errors]
    if selected("module-size"):
        module_size_findings = _validate_module_size_budget(repo_root)
        contract_errors.extend(
            finding for finding in module_size_findings if finding.severity == "error"
        )
        findings.extend(finding for finding in module_size_findings if finding.severity != "error")
    if selected("generated-artifacts"):
        contract_errors.extend(
            _validate_generated_artifact_contracts(repo_root, family_admission=family_admission)
        )
    if selected("extension-points"):
        contract_errors.extend(_validate_extension_points_contract(repo_root))
    if selected("runbook-coverage"):
        contract_errors.extend(
            _validate_list_contract(
                repo_root,
                relative_path="architecture/runbook_coverage.toml",
                header="runbook_coverage",
                entries="coverage",
                required_fields=("id", "owner", "package", "status", "contract", "runbooks"),
                path_fields=("contract",),
                list_path_fields=("runbooks", "slo_files"),
                allowed_header_statuses=("report_only", "contract_only"),
            )
        )
    if selected("component-observability"):
        contract_errors.extend(
            _validate_list_contract(
                repo_root,
                relative_path="architecture/component_observability.toml",
                header="component_observability",
                entries="component",
                required_fields=("id", "owner", "package", "contract", "mode"),
                path_fields=("contract",),
                list_path_fields=("slo_files",),
                allowed_header_statuses=("report_only", "contract_only"),
            )
        )
    if selected_any("runbook-coverage", "component-observability"):
        route_findings, legacy_operability_route_summary = _validate_legacy_operability_routes(
            repo_root
        )
        contract_errors.extend(route_findings)
    if selected("runtime-state-layout"):
        contract_errors.extend(
            _validate_list_contract(
                repo_root,
                relative_path="architecture/runtime_state_layout.toml",
                header="runtime_state_layout",
                entries="state_surface",
                required_fields=("id", "owner", "paths", "commit_policy", "mode"),
                allowed_header_statuses=("report_only", "contract_only", "active"),
                allowed_entry_modes=("report_only", "fail_closed"),
            )
        )
    if selected("test-ratchets"):
        contract_errors.extend(
            _validate_list_contract(
                repo_root,
                relative_path="architecture/tests/ratchets.toml",
                header="test_ratchets",
                entries="ratchet",
                required_fields=("id", "owner", "package", "contract", "required_roots", "mode"),
                path_fields=("contract",),
                list_path_fields=("required_roots",),
                allowed_header_statuses=("report_only", "active"),
                allowed_entry_modes=("report_only", "fail_closed_contract"),
            )
        )
    if selected("directory-contracts"):
        contract_errors.extend(_validate_directory_contracts(repo_root))
    if selected("directory-hygiene-assets"):
        contract_errors.extend(_validate_directory_hygiene_assets(repo_root))
    if selected_any("dependency-graph", "phase6-1"):
        contract_errors.extend(_validate_import_reports(repo_root))
        import_boundary_summary = _build_import_boundary_summary(repo_root)
        package_boundary_summary = _package_boundary_forbidden_summary(repo_root)
        contract_errors.extend(_validate_import_exception_metadata(repo_root))
        contract_errors.extend(_validate_public_surface_import_contracts(repo_root))
        contract_errors.extend(_validate_public_surface_inventory_contract(repo_root))
        if enforce_import_boundary_deltas:
            contract_errors.extend(_import_boundary_delta_errors(import_boundary_summary))
            contract_errors.extend(_package_boundary_forbidden_errors(package_boundary_summary))
        findings.extend(_import_boundary_findings(import_boundary_summary))
        findings.extend(_package_boundary_findings(package_boundary_summary))
    if selected_any("dynamic-imports", "phase6-1"):
        contract_errors.extend(_validate_dynamic_imports_contract(repo_root))
        contract_errors.extend(_validate_dynamic_imports_gate(repo_root))
        findings.extend(_summarize_dynamic_imports(repo_root))
    if selected_any("import-cycles", "phase6-1"):
        contract_errors.extend(_validate_import_cycles_gate(repo_root))
    if selected_any("package-layout", "phase6-1"):
        findings.extend(_structure_gate_findings(repo_root, gate="loose_files"))
    if selected_any("name-collisions", "phase6-1"):
        findings.extend(_structure_gate_findings(repo_root, gate="name_collision"))
    if selected_any("shim-expiry", "phase6-1"):
        contract_errors.extend(_validate_shim_expiry_contract(repo_root))
        contract_errors.extend(_validate_reexport_shim_shape_gate(repo_root))
    if selected("static-analysis-overrides"):
        findings.extend(_validate_static_analysis_overrides(repo_root))

    gate_errors = _validate_report_only_gates(repo_root)
    if report == "all" or report in {
        "packages",
        "package-mirrors",
        "module-size",
        "generated-artifacts",
        "extension-points",
        "runbook-coverage",
        "component-observability",
        "runtime-state-layout",
        "test-ratchets",
        "directory-contracts",
        "directory-hygiene-assets",
        "dependency-graph",
        "dynamic-imports",
        "import-cycles",
        "package-layout",
        "name-collisions",
        "shim-expiry",
        "phase6-1",
        "static-analysis-overrides",
    }:
        contract_errors.extend(gate_errors)

    summary = _summary(repo_root, family_admission=family_admission)
    if legacy_operability_route_summary is not None:
        summary["legacy_operability_routes"] = legacy_operability_route_summary
    if package_mirror_summary is not None:
        summary.setdefault("generated_family_checks", {})[PACKAGE_MIRROR_FAMILY_ID] = (
            package_mirror_summary
        )
    if selected_any("dependency-graph", "phase6-1") and import_boundary_summary is not None:
        summary["import_boundary"] = import_boundary_summary
        summary["package_boundary"] = package_boundary_summary or {}
    if selected_any("dynamic-imports", "phase6-1"):
        summary["dynamic_imports"] = _dynamic_imports_summary(repo_root)
    if selected_any("import-cycles", "phase6-1"):
        summary["import_cycles"] = _import_cycles_summary(repo_root)
    if selected_any("package-layout", "phase6-1"):
        summary["package_layout"] = _structure_gate_summary(repo_root, gate="loose_files")
    if selected_any("name-collisions", "phase6-1"):
        summary["name_collisions"] = _structure_gate_summary(repo_root, gate="name_collision")
    if (
        selected("dependency-graph")
        or selected("package-mirrors")
        or selected_any("shim-expiry", "phase6-1")
    ):
        summary["shim_debt"] = _shim_debt_summary(repo_root)
    if selected("phase6-1"):
        summary["phase6_1"] = _phase6_1_summary()

    return {
        "phase": "repository-best-in-class-phase-1.3",
        "mode": "report_only",
        "report": report,
        "status": "contract_errors" if contract_errors else "reported",
        "contract_error_count": len(contract_errors),
        "finding_count": len(findings),
        "contract_errors": [finding.as_dict() for finding in contract_errors],
        "findings": [finding.as_dict() for finding in findings],
        "summary": summary,
    }


def _read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _admit_package_mirror_family_registry(
    repo_root: Path,
) -> _PackageMirrorFamilyAdmission:
    family_path = "architecture/generated_artifacts.toml"
    family_document = _read_toml(repo_root / family_path)
    if type(family_document) is not dict:
        return _PackageMirrorFamilyAdmission(
            (),
            (
                Finding(
                    "package-mirror",
                    "error",
                    family_path,
                    "generated-artifact family registry must be a table",
                ),
            ),
        )
    family_rows = family_document.get("family", _MISSING_VALUE)
    if type(family_rows) is not list:
        return _PackageMirrorFamilyAdmission(
            (),
            (
                Finding(
                    "package-mirror",
                    "error",
                    family_path,
                    "family registry rows must be an array",
                ),
            ),
        )

    from tools.devx.architecture.guardrails import (
        GeneratedArtifactManifestSchemaError,
        _validate_generated_artifact_toml_data,
    )

    try:
        _validate_generated_artifact_toml_data(family_document)
    except GeneratedArtifactManifestSchemaError:
        admitted_rows: list[dict[str, Any]] = []
        findings: list[Finding] = []
        for index, family_row in enumerate(family_rows):
            try:
                _validate_generated_artifact_toml_data({"family": [family_row]})
            except GeneratedArtifactManifestSchemaError as error:
                findings.append(
                    Finding(
                        "package-mirror",
                        "error",
                        family_path,
                        "family registry row does not satisfy generated-artifact schema",
                        f"index={index} {error}",
                    )
                )
            else:
                admitted_rows.append(family_row)
        return _PackageMirrorFamilyAdmission(tuple(admitted_rows), tuple(findings))

    return _PackageMirrorFamilyAdmission(tuple(family_rows), ())


def _family_registry_findings(
    admission: _PackageMirrorFamilyAdmission, *, check: str
) -> list[Finding]:
    return [
        Finding(check, finding.severity, finding.subject, finding.message, finding.detail)
        for finding in admission.findings
    ]


def _relative(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _package_mirror_family(
    family_admission: _PackageMirrorFamilyAdmission,
) -> dict[str, Any] | None:
    matches = [
        family_row
        for family_row in family_admission.rows
        if family_row.get("id") == PACKAGE_MIRROR_FAMILY_ID
    ]
    return matches[0] if len(matches) == 1 else None


def _package_mirror_output_paths(
    family_admission: _PackageMirrorFamilyAdmission,
) -> set[str]:
    family = _package_mirror_family(family_admission)
    if family is None:
        return set(PACKAGE_MIRROR_OUTPUTS.values())
    outputs = family.get("outputs", _MISSING_VALUE)
    if type(outputs) is not list or any(type(output) is not str for output in outputs):
        return set(PACKAGE_MIRROR_OUTPUTS.values())
    return set(outputs)


def _package_contract_paths(
    repo_root: Path,
    *,
    family_admission: _PackageMirrorFamilyAdmission | None = None,
) -> list[Path]:
    admission = family_admission or _admit_package_mirror_family_registry(repo_root)
    registered_outputs = _package_mirror_output_paths(admission)
    package_root = repo_root / "architecture" / "packages"
    return sorted(
        path
        for path in package_root.glob("*.toml")
        if _relative(path, repo_root) not in registered_outputs
    )


def _load_package_contracts(
    repo_root: Path,
    *,
    family_admission: _PackageMirrorFamilyAdmission | None = None,
) -> list[tuple[Path, dict[str, Any]]]:
    return [
        (path, _read_toml(path))
        for path in _package_contract_paths(repo_root, family_admission=family_admission)
    ]


def _aggregate_package_modules(repo_root: Path) -> list[str]:
    modules: set[str] = set()
    for relative_path in (
        "architecture/packages/boundaries.toml",
        "architecture/public_surface/contract.toml",
    ):
        data = _read_toml(repo_root / relative_path)
        modules.update(
            str(item.get("module", "")).strip()
            for item in data.get("package", [])
            if str(item.get("module", "")).strip()
        )
    test_topology = _read_toml(repo_root / "architecture" / "tests" / "topology.toml")
    modules.update(
        f"polisyos.{str(item.get('name', '')).strip()}"
        for item in test_topology.get("package", [])
        if str(item.get("name", "")).strip()
    )
    return sorted(modules)


def _validate_package_contracts(
    repo_root: Path,
    *,
    family_admission: _PackageMirrorFamilyAdmission | None = None,
) -> list[Finding]:
    errors: list[Finding] = []
    expected_modules = set(_aggregate_package_modules(repo_root))
    primary_contracts_by_module: dict[str, list[str]] = {}
    for path, data in _load_package_contracts(repo_root, family_admission=family_admission):
        subject = _relative(path, repo_root)
        missing_tables = [table for table in REQUIRED_PACKAGE_TABLES if table not in data]
        for table in missing_tables:
            errors.append(Finding("package-contract", "error", subject, f"missing [{table}] table"))
        if missing_tables:
            continue
        package = data["package"]
        module = str(package.get("module", ""))
        if not module:
            errors.append(Finding("package-contract", "error", subject, "missing package.module"))
        if package.get("primary_contract") is not True:
            errors.append(
                Finding(
                    "package-contract",
                    "error",
                    subject,
                    "package.primary_contract must be true",
                    str(package.get("primary_contract")),
                )
            )
        else:
            primary_contracts_by_module.setdefault(module, []).append(subject)
        if module and module not in expected_modules:
            errors.append(
                Finding(
                    "package-contract",
                    "error",
                    subject,
                    "primary package contract is not mirrored by aggregate package TOML",
                    module,
                )
            )
        if package.get("gate_mode") != "report_only":
            errors.append(
                Finding(
                    "package-contract",
                    "error",
                    subject,
                    "package gate_mode must be report_only",
                    str(package.get("gate_mode")),
                )
            )
        for table in REQUIRED_PACKAGE_TABLES:
            owner = (
                data[table].get("owner") or data[table].get("layout_owner") or package.get("owner")
            )
            if not str(owner or "").strip():
                errors.append(
                    Finding("package-contract", "error", subject, f"[{table}] has no owner")
                )
        for field in ("id", "module", "name", "owner", "contract_status"):
            if package.get(field) in (None, "", []):
                errors.append(
                    Finding("package-contract", "error", subject, f"[package] missing `{field}`")
                )
        if package.get("legacy_aggregate_mirrors") in (None, "", []):
            errors.append(
                Finding(
                    "package-contract",
                    "error",
                    subject,
                    "[package] missing `legacy_aggregate_mirrors`",
                )
            )
        layout = data.get("layout", {})
        for field in ("status", "source_root", "readme", "root_facade_policy"):
            if layout.get(field) in (None, "", []):
                errors.append(
                    Finding("package-contract", "error", subject, f"[layout] missing `{field}`")
                )
        for field in ("source_root", "readme"):
            value = str(layout.get(field, ""))
            if value and not _path_pattern_exists(repo_root, value):
                errors.append(
                    Finding(
                        "package-contract",
                        "error",
                        subject,
                        f"[layout].{field} path is missing",
                        value,
                    )
                )
        boundaries = data.get("boundaries", {})
        for field in ("public_facade", "allowed_dependencies", "forbidden_dependencies"):
            if field not in boundaries:
                errors.append(
                    Finding("package-contract", "error", subject, f"[boundaries] missing `{field}`")
                )
        surface = data.get("public_surface", {})
        for field in (
            "classification",
            "facade_mode",
            "registry_owner",
            "reference_doc",
            "supported_entrypoints",
            "major_subsystem",
        ):
            if surface.get(field) in (None, "", []):
                errors.append(
                    Finding(
                        "package-contract",
                        "error",
                        subject,
                        f"[public_surface] missing `{field}`",
                    )
                )
        tests = data.get("tests", {})
        for field in ("status", "unit_roots", "integration_required", "property_required"):
            if tests.get(field) in (None, "", []):
                errors.append(
                    Finding("package-contract", "error", subject, f"[tests] missing `{field}`")
                )
        slo_runbook = data.get("slo_runbook", {})
        for field in ("status", "slo_files", "runbooks", "runbook_expectation"):
            if slo_runbook.get(field) in (None, "", []):
                errors.append(
                    Finding(
                        "package-contract",
                        "error",
                        subject,
                        f"[slo_runbook] missing `{field}`",
                    )
                )
        extension_host = data.get("extension_host", {})
        if "status" not in extension_host or "extension_points" not in extension_host:
            errors.append(
                Finding(
                    "package-contract",
                    "error",
                    subject,
                    "[extension_host] must declare status and extension_points",
                )
            )
        _validate_package_extension_points(repo_root, subject, extension_host, errors)
        for aggregate in package.get("legacy_aggregate_mirrors", []):
            if not _path_pattern_exists(repo_root, str(aggregate)):
                errors.append(
                    Finding(
                        "package-contract",
                        "error",
                        subject,
                        "legacy aggregate mirror path is missing",
                        str(aggregate),
                    )
                )
        for section in ("exception", "sunset"):
            for item in data.get(section, []):
                raw_date = item.get("sunset") or item.get("date")
                if raw_date is not None and not _valid_future_or_today(str(raw_date)):
                    errors.append(
                        Finding(
                            "package-contract",
                            "error",
                            subject,
                            f"{section} has invalid or expired date",
                            str(raw_date),
                        )
                    )
    for module in expected_modules:
        subjects = primary_contracts_by_module.get(module, [])
        if not subjects:
            errors.append(
                Finding(
                    "package-contract",
                    "error",
                    module,
                    "aggregate package has no primary package contract file",
                )
            )
        if len(subjects) > 1:
            errors.append(
                Finding(
                    "package-contract",
                    "error",
                    module,
                    "aggregate package has multiple primary package contract files",
                    ", ".join(subjects),
                )
            )
    return errors


def _validate_package_extension_points(
    repo_root: Path,
    subject: str,
    extension_host: dict[str, Any],
    errors: list[Finding],
) -> None:
    status = str(extension_host.get("status", ""))
    extension_points = extension_host.get("extension_points", [])
    if status == "active" and not extension_points:
        errors.append(
            Finding(
                "package-contract",
                "error",
                subject,
                "active extension host must list extension_points",
            )
        )
    declared = {
        str(item.get("name"))
        for item in _read_toml(repo_root / "architecture" / "extension_points.toml").get(
            "extension_point", []
        )
    }
    for extension_point in extension_points or []:
        if str(extension_point) not in declared:
            errors.append(
                Finding(
                    "package-contract",
                    "error",
                    subject,
                    "extension point is not declared in architecture/extension_points.toml",
                    str(extension_point),
                )
            )


def _valid_future_or_today(raw: str) -> bool:
    try:
        return dt.date.fromisoformat(raw) >= dt.date.today()
    except ValueError:
        return False


def _validate_package_mirrors(repo_root: Path) -> list[Finding]:
    findings, _ = _validate_package_mirror_projection(repo_root)
    return findings


def _validate_package_mirror_projection(
    repo_root: Path,
    *,
    family_admission: _PackageMirrorFamilyAdmission | None = None,
) -> tuple[list[Finding], dict[str, Any]]:
    admission = family_admission or _admit_package_mirror_family_registry(repo_root)
    errors = _family_registry_findings(admission, check="package-mirror")
    family_path = "architecture/generated_artifacts.toml"
    family_matches = [
        family_row
        for family_row in admission.rows
        if family_row.get("id") == PACKAGE_MIRROR_FAMILY_ID
    ]
    family = family_matches[0] if len(family_matches) == 1 else {}
    if len(family_matches) != 1:
        errors.append(
            Finding(
                "package-mirror",
                "error",
                family_path,
                "package-mirror family must be registered exactly once",
                f"matches={len(family_matches)}",
            )
        )
    raw_outputs = family.get("outputs", _MISSING_VALUE)
    outputs = (
        [value for value in raw_outputs if type(value) is str] if type(raw_outputs) is list else []
    )
    output_set = set(outputs)
    expected_outputs = set(PACKAGE_MIRROR_OUTPUTS.values())
    if type(raw_outputs) is not list or len(outputs) != len(raw_outputs):
        errors.append(
            Finding(
                "package-mirror",
                "error",
                family_path,
                "package-mirror outputs must be a list of repository-relative paths",
            )
        )
    if len(outputs) != len(output_set):
        errors.append(
            Finding(
                "package-mirror",
                "error",
                family_path,
                "package-mirror outputs contain duplicate paths",
            )
        )
    if output_set != expected_outputs:
        errors.append(
            Finding(
                "package-mirror",
                "error",
                family_path,
                "registered outputs differ from the package projection schema",
                f"missing={sorted(expected_outputs - output_set)!r} "
                f"extra={sorted(output_set - expected_outputs)!r}",
            )
        )
    for output in outputs:
        path = PurePosixPath(output)
        if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
            errors.append(
                Finding(
                    "package-mirror",
                    "error",
                    family_path,
                    "output path is not repository-relative and traversal-free",
                    output,
                )
            )
    source_basis = family.get("source_of_truth", _MISSING_VALUE)
    if type(source_basis) is not str or source_basis != PACKAGE_MIRROR_SOURCE_OF_TRUTH:
        errors.append(
            Finding(
                "package-mirror",
                "error",
                family_path,
                "source basis must exclude registered family outputs",
                f"type={_mirror_value_type(source_basis)} value={source_basis!r}",
            )
        )
    command = family.get("check_command", _MISSING_VALUE)
    if type(command) is not list or command != list(PACKAGE_MIRROR_CHECK_COMMAND):
        errors.append(
            Finding(
                "package-mirror",
                "error",
                family_path,
                "family check_command must match the canonical verifier route",
                f"expected={list(PACKAGE_MIRROR_CHECK_COMMAND)!r} observed={command!r}",
            )
        )

    source_contracts = _load_package_contracts(repo_root, family_admission=admission)
    primary = [
        (p, d)
        for p, d in source_contracts
        if isinstance(d.get("package"), dict) and d["package"].get("primary_contract") is True
    ]
    by_module: dict[str, tuple[Path, dict[str, Any]]] = {}
    by_name: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path, data in primary:
        package = data["package"]
        raw_module = package.get("module", _MISSING_VALUE)
        raw_name = package.get("name", _MISSING_VALUE)
        subject = _relative(path, repo_root)
        identity_is_valid = True
        for field, value in (("package.module", raw_module), ("package.name", raw_name)):
            if type(value) is not str or not value.strip() or value != value.strip():
                errors.append(
                    Finding(
                        "package-mirror",
                        "error",
                        subject,
                        f"{field} has malformed source value",
                        f"expected non-empty trimmed string; got {_mirror_value_type(value)}",
                    )
                )
                identity_is_valid = False
        if not identity_is_valid:
            continue
        module, name = raw_module, raw_name
        if module in by_module:
            errors.append(
                Finding(
                    "package-mirror",
                    "error",
                    subject,
                    "primary contracts duplicate package.module",
                    module,
                )
            )
        else:
            by_module[module] = (path, data)
        if name in by_name:
            errors.append(
                Finding(
                    "package-mirror",
                    "error",
                    subject,
                    "primary contracts duplicate package.name",
                    name,
                )
            )
        else:
            by_name[name] = (path, data)
    if not primary:
        errors.append(
            Finding(
                "package-mirror",
                "error",
                "architecture/packages",
                "no primary package source contracts were discovered",
            )
        )

    def projection(relative: str) -> dict[str, Any]:
        try:
            return _read_toml(repo_root / relative)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            errors.append(
                Finding(
                    "package-mirror",
                    "error",
                    relative,
                    "package projection is missing or malformed",
                    str(exc),
                )
            )
            return {}

    def rows_index(rows: object, identity: str, subject: str) -> dict[str, dict[str, Any]]:
        if not isinstance(rows, list):
            errors.append(
                Finding("package-mirror", "error", subject, "projection rows must be an array")
            )
            return {}
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                errors.append(
                    Finding("package-mirror", "error", subject, "projection row must be a table")
                )
                continue
            raw_key = row.get(identity, _MISSING_VALUE)
            if type(raw_key) is not str:
                errors.append(
                    Finding(
                        "package-mirror",
                        "error",
                        subject,
                        f"projection row `{identity}` has malformed identity value",
                        f"expected string; got {_mirror_value_type(raw_key)}",
                    )
                )
                continue
            key = raw_key
            if not key.strip() or key != key.strip():
                errors.append(
                    Finding(
                        "package-mirror", "error", subject, f"projection row lacks `{identity}`"
                    )
                )
            elif key in result:
                errors.append(
                    Finding(
                        "package-mirror",
                        "error",
                        subject,
                        f"projection rows duplicate `{identity}`",
                        key,
                    )
                )
            else:
                result[key] = row
        return result

    def source_table(data: dict[str, Any], table: str, subject: str) -> dict[str, Any]:
        value = data.get(table, _MISSING_VALUE)
        if type(value) is dict:
            return value
        _record_malformed_mirror_value(
            errors,
            subject,
            table,
            value,
            domain="table",
            side="source",
        )
        return {}

    def check_set(label: str, expected: set[str], observed: set[str], subject: str) -> None:
        for item in sorted(expected - observed):
            errors.append(
                Finding(
                    "package-mirror",
                    "error",
                    subject,
                    f"{label} is missing a source-derived row",
                    item,
                )
            )
        for item in sorted(observed - expected):
            errors.append(
                Finding(
                    "package-mirror",
                    "error",
                    label,
                    "projection row has no matching source declaration",
                    item,
                )
            )

    expected_modules = set(by_module)
    boundary_path = PACKAGE_MIRROR_OUTPUTS["boundaries"]
    boundaries = rows_index(projection(boundary_path).get("package"), "module", boundary_path)
    check_set("package boundaries", expected_modules, set(boundaries), boundary_path)
    for module, (path, data) in by_module.items():
        row = boundaries.get(module)
        if row is None:
            continue
        subject = _relative(path, repo_root)
        package = source_table(data, "package", subject)
        source = source_table(data, "boundaries", subject)
        for field, expected in (
            ("owner", package.get("owner", _MISSING_VALUE)),
            ("public_facade", source.get("public_facade", _MISSING_VALUE)),
        ):
            _compare_scalar(
                errors,
                subject,
                f"package_boundaries.{field}",
                expected=expected,
                observed=row.get(field, _MISSING_VALUE),
            )
        for field in ("allowed_dependencies", "forbidden_dependencies"):
            _compare_list(
                errors,
                subject,
                f"package_boundaries.{field}",
                expected=source.get(field, _MISSING_VALUE),
                observed=row.get(field, _MISSING_VALUE),
            )
        for field in ("compatibility_shim", "shim_id"):
            _compare_optional_scalar(
                errors,
                subject,
                f"package_boundaries.{field}",
                expected=source.get(field),
                observed=row.get(field),
            )
        _compare_optional_list(
            errors,
            subject,
            "package_boundaries.runtime_allowed_submodules",
            expected=source.get("runtime_allowed_submodules"),
            observed=row.get("runtime_allowed_submodules"),
        )

    public_path = PACKAGE_MIRROR_OUTPUTS["public_surface"]
    public_rows = rows_index(projection(public_path).get("package"), "module", public_path)
    public_sources: dict[str, tuple[Path, dict[str, Any]]] = {}
    declared_entrypoints: set[str] = set()
    for source_path, source_data in source_contracts:
        source_subject = _relative(source_path, repo_root)
        source_package = source_table(source_data, "package", source_subject)
        source_surface = source_table(source_data, "public_surface", source_subject)
        source_module = source_package.get("module", _MISSING_VALUE)
        if (
            type(source_module) is not str
            or not source_module.strip()
            or source_module != source_module.strip()
        ):
            continue
        if source_module in public_sources:
            errors.append(
                Finding(
                    "package-mirror",
                    "error",
                    _relative(source_path, repo_root),
                    "public surface source contracts duplicate package.module",
                    source_module,
                )
            )
            continue
        public_sources[source_module] = (source_path, source_data)
        raw_entrypoints = source_surface.get("supported_entrypoints", _MISSING_VALUE)
        if type(raw_entrypoints) is list:
            declared_entrypoints.update(
                entry for entry in raw_entrypoints if type(entry) is str and entry
            )

    public_source_modules = set(public_sources)
    check_set(
        "public surface",
        public_source_modules,
        public_source_modules & set(public_rows),
        public_path,
    )
    unmapped_public_surface_rows: dict[str, dict[str, Any]] = {}
    for extra in sorted(set(public_rows) - public_source_modules):
        row = public_rows[extra]
        unverified_fields = sorted(field for field in row if field != "module")
        parent_entrypoint_declared = extra in declared_entrypoints
        unmapped_public_surface_rows[extra] = {
            "status": "not_established",
            "parent_entrypoint_declared": parent_entrypoint_declared,
            "unverified_fields": unverified_fields,
        }
        errors.append(
            Finding(
                "package-mirror",
                "error",
                public_path,
                "public surface row has no complete source contract",
                f"module={extra!r} status=not_established "
                f"parent_entrypoint_declared={parent_entrypoint_declared} "
                f"unverified_fields={unverified_fields!r}",
            )
        )

    for module, (path, data) in public_sources.items():
        row = public_rows.get(module)
        if row is None:
            continue
        surface = source_table(data, "public_surface", _relative(path, repo_root))
        layout = source_table(data, "layout", _relative(path, repo_root))
        source_values = (
            ("classification", surface.get("classification", _MISSING_VALUE)),
            ("facade_mode", surface.get("facade_mode", _MISSING_VALUE)),
            ("owner", surface.get("registry_owner", _MISSING_VALUE)),
            ("readme", layout.get("readme", _MISSING_VALUE)),
            ("reference_doc", surface.get("reference_doc", _MISSING_VALUE)),
            ("notes", surface.get("notes", _MISSING_VALUE)),
        )
        for field, expected in source_values:
            _compare_scalar(
                errors,
                _relative(path, repo_root),
                f"public_surface.{field}",
                expected=expected,
                observed=row.get(field, _MISSING_VALUE),
            )
        _compare_boolean(
            errors,
            _relative(path, repo_root),
            "public_surface.major_subsystem",
            expected=surface.get("major_subsystem", _MISSING_VALUE),
            observed=row.get("major_subsystem", _MISSING_VALUE),
        )
        _compare_list(
            errors,
            _relative(path, repo_root),
            "public_surface.supported_entrypoints",
            expected=surface.get("supported_entrypoints", _MISSING_VALUE),
            observed=row.get("supported_entrypoints", _MISSING_VALUE),
        )

    layout_path = PACKAGE_MIRROR_OUTPUTS["layout"]
    layout_rows = rows_index(projection(layout_path).get("package"), "name", layout_path)
    expected_layout: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path, data in primary:
        layout = source_table(data, "layout", _relative(path, repo_root))
        mirror_value = layout.get("legacy_layout_mirror", _MISSING_VALUE)
        if type(mirror_value) is not str:
            _record_malformed_mirror_value(
                errors,
                _relative(path, repo_root),
                "layout.legacy_layout_mirror",
                mirror_value,
                domain="string",
                side="source",
            )
            continue
        mirror = mirror_value
        if mirror != mirror.strip():
            errors.append(
                Finding(
                    "package-mirror",
                    "error",
                    _relative(path, repo_root),
                    "layout.legacy_layout_mirror has malformed source value",
                    "expected an exact unpadded repository-relative path",
                )
            )
        if mirror and mirror not in output_set:
            errors.append(
                Finding(
                    "package-mirror",
                    "error",
                    _relative(path, repo_root),
                    "layout mirror path is not registered by its generated family",
                    mirror,
                )
            )
        if mirror == layout_path:
            package = source_table(data, "package", _relative(path, repo_root))
            name = package.get("name", _MISSING_VALUE)
            if type(name) is str and name.strip() and name == name.strip():
                expected_layout[name] = (path, data)
            else:
                _record_malformed_mirror_value(
                    errors,
                    _relative(path, repo_root),
                    "package.name",
                    name,
                    domain="string",
                    side="source",
                )
    check_set("package layout", set(expected_layout), set(layout_rows), layout_path)
    for name, (path, data) in expected_layout.items():
        row = layout_rows.get(name)
        if row is not None:
            _compare_scalar(
                errors,
                _relative(path, repo_root),
                "package_layout.current_status",
                expected=data.get("layout", {}).get("legacy_layout_status", _MISSING_VALUE),
                observed=row.get("current_status", _MISSING_VALUE),
            )

    topology_path = PACKAGE_MIRROR_OUTPUTS["test_topology"]
    topology = projection(topology_path)
    topology_rows = rows_index(topology.get("package"), "name", topology_path)
    exception_rows = rows_index(
        topology.get("source_package_exception"),
        "name",
        f"{topology_path}#source_package_exception",
    )
    dispositions = {"direct": 0, "explicit_source_exception": 0, "nested_coverage": 0}
    for name in sorted(set(topology_rows) - set(by_name) - set(exception_rows)):
        errors.append(
            Finding(
                "package-mirror",
                "error",
                topology_path,
                "topology row has neither a primary source contract nor explicit source exception",
                name,
            )
        )
    for name in sorted(set(by_name) & set(exception_rows) & set(topology_rows)):
        errors.append(
            Finding(
                "package-mirror",
                "error",
                topology_path,
                "primary package is both a direct topology row and source exception",
                name,
            )
        )

    def strict_descendant(parent: object, child: object) -> bool:
        if type(parent) is not str or type(child) is not str:
            return False
        p, c = PurePosixPath(parent), PurePosixPath(child)
        if (
            p.is_absolute()
            or c.is_absolute()
            or any(part in {".", ".."} for part in p.parts + c.parts)
        ):
            return False
        try:
            relative = c.relative_to(p)
        except ValueError:
            return False
        return bool(relative.parts)

    def nearest_topology_ancestor(data: dict[str, Any]) -> tuple[str, Path, dict[str, Any]] | None:
        package = data.get("package")
        if not isinstance(package, dict):
            return None
        module = package.get("module", _MISSING_VALUE)
        if type(module) is not str:
            return None
        candidates: list[tuple[str, Path, dict[str, Any]]] = []
        for candidate_module, (path, candidate) in by_module.items():
            candidate_package = candidate.get("package")
            candidate_name = (
                candidate_package.get("name", _MISSING_VALUE)
                if isinstance(candidate_package, dict)
                else _MISSING_VALUE
            )
            if (
                module.startswith(candidate_module + ".")
                and type(candidate_name) is str
                and candidate_name in topology_rows
            ):
                candidates.append((candidate_module, path, candidate))
        return max(candidates, key=lambda item: len(item[0].split("."))) if candidates else None

    for name, (path, data) in by_name.items():
        subject = _relative(path, repo_root)
        row = topology_rows.get(name)
        if row is not None:
            dispositions["direct"] += 1
            tests = source_table(data, "tests", subject)
            layout = source_table(data, "layout", subject)
            _compare_scalar(
                errors,
                subject,
                "test_topology.source_path",
                expected=layout.get("source_root", _MISSING_VALUE),
                observed=row.get("source_path", _MISSING_VALUE),
            )
            _compare_list(
                errors,
                subject,
                "test_topology.unit_path",
                expected=tests.get("unit_roots", _MISSING_VALUE),
                observed=[row.get("unit_path", _MISSING_VALUE)],
            )
            for kind in ("integration", "property"):
                source_required = tests.get(f"{kind}_required", _MISSING_VALUE)
                observed_table = row.get(kind, _MISSING_VALUE)
                if type(observed_table) is not dict:
                    _record_malformed_mirror_value(
                        errors,
                        subject,
                        f"test_topology.{kind}",
                        observed_table,
                        domain="table",
                        side="projection",
                    )
                    observed_required = _MISSING_VALUE
                    observed_path = _MISSING_VALUE
                else:
                    observed_required = observed_table.get("required", _MISSING_VALUE)
                    observed_path = observed_table.get("path", _MISSING_VALUE)
                _compare_boolean(
                    errors,
                    subject,
                    f"test_topology.{kind}.required",
                    expected=source_required,
                    observed=observed_required,
                )
                if type(source_required) is bool and type(observed_required) is bool:
                    source_roots = tests.get(f"{kind}_roots", _MISSING_VALUE)
                    if source_required is False and source_roots is _MISSING_VALUE:
                        source_roots = []
                    if observed_required is False and observed_path is _MISSING_VALUE:
                        observed_roots = []
                    else:
                        observed_roots = [observed_path]
                    _compare_list(
                        errors,
                        subject,
                        f"test_topology.{kind}.path",
                        expected=source_roots,
                        observed=observed_roots,
                    )
            continue
        exception = exception_rows.get(name)
        if exception is not None:
            dispositions["explicit_source_exception"] += 1
            layout = source_table(data, "layout", subject)
            _compare_scalar(
                errors,
                subject,
                "test_topology.source_package_exception.source_path",
                expected=layout.get("source_root", _MISSING_VALUE),
                observed=exception.get("source_path", _MISSING_VALUE),
            )
            continue
        ancestor = nearest_topology_ancestor(data)
        if ancestor is None:
            errors.append(
                Finding(
                    "package-mirror",
                    "error",
                    subject,
                    "package has no direct topology row, exact source exception, "
                    "or structural parent",
                    name,
                )
            )
            continue
        _, _, ancestor_data = ancestor
        ancestor_name = ancestor_data["package"]["name"]
        ancestor_row = topology_rows[ancestor_name]
        child_layout = source_table(data, "layout", subject)
        parent_layout = source_table(ancestor_data, "layout", _relative(ancestor[1], repo_root))
        child_source = child_layout.get("source_root", _MISSING_VALUE)
        parent_source = parent_layout.get("source_root", _MISSING_VALUE)
        _validate_mirror_value(
            errors,
            subject,
            "layout.source_root",
            child_source,
            domain="string",
            side="source",
        )
        _validate_mirror_value(
            errors,
            _relative(ancestor[1], repo_root),
            "layout.source_root",
            parent_source,
            domain="string",
            side="source",
        )
        if not strict_descendant(parent_source, child_source):
            errors.append(
                Finding(
                    "package-mirror",
                    "error",
                    subject,
                    "nested source is not strictly contained by its nearest module ancestor",
                    f"parent={parent_source!r} child={child_source!r}",
                )
            )
        child_tests = source_table(data, "tests", subject)
        unit_roots = child_tests.get("unit_roots", _MISSING_VALUE)
        parent_unit = ancestor_row.get("unit_path", _MISSING_VALUE)
        source_roots_valid = _validate_mirror_value(
            errors, subject, "tests.unit_roots", unit_roots, domain="string_list", side="source"
        )
        parent_unit_valid = _validate_mirror_value(
            errors,
            _relative(ancestor[1], repo_root),
            "test_topology.unit_path",
            parent_unit,
            domain="string",
            side="projection",
        )
        if (
            not source_roots_valid
            or not parent_unit_valid
            or not unit_roots
            or not all(strict_descendant(parent_unit, child) for child in unit_roots)
        ):
            errors.append(
                Finding(
                    "package-mirror",
                    "error",
                    subject,
                    "nested unit roots are not strictly covered by nearest ancestor topology",
                    f"parent={parent_unit!r} children={unit_roots!r}",
                )
            )
        for kind in ("integration", "property"):
            child_required = child_tests.get(f"{kind}_required", _MISSING_VALUE)
            if not _validate_mirror_value(
                errors,
                subject,
                f"tests.{kind}_required",
                child_required,
                domain="boolean",
                side="source",
            ):
                continue
            child_roots = child_tests.get(f"{kind}_roots", _MISSING_VALUE)
            if child_required is False and child_roots is _MISSING_VALUE:
                child_roots = []
            child_roots_valid = _validate_mirror_value(
                errors,
                subject,
                f"tests.{kind}_roots",
                child_roots,
                domain="string_list",
                side="source",
            )
            if not child_required:
                continue
            parent_table = ancestor_row.get(kind, _MISSING_VALUE)
            if not _validate_mirror_value(
                errors,
                _relative(ancestor[1], repo_root),
                f"test_topology.{kind}",
                parent_table,
                domain="table",
                side="projection",
            ):
                continue
            parent_required = parent_table.get("required", _MISSING_VALUE)
            parent_required_valid = _validate_mirror_value(
                errors,
                _relative(ancestor[1], repo_root),
                f"test_topology.{kind}.required",
                parent_required,
                domain="boolean",
                side="projection",
            )
            parent_root = parent_table.get("path", _MISSING_VALUE)
            parent_root_valid = _validate_mirror_value(
                errors,
                _relative(ancestor[1], repo_root),
                f"test_topology.{kind}.path",
                parent_root,
                domain="string",
                side="projection",
            )
            if (
                not child_roots_valid
                or not parent_required_valid
                or not parent_root_valid
                or parent_required is not True
                or not child_roots
                or not all(strict_descendant(parent_root, child) for child in child_roots)
            ):
                errors.append(
                    Finding(
                        "package-mirror",
                        "error",
                        subject,
                        f"nested {kind} roots are not covered by nearest ancestor topology",
                        f"parent={parent_root!r} children={child_roots!r}",
                    )
                )
        dispositions["nested_coverage"] += 1

    summary = {
        "family_id": PACKAGE_MIRROR_FAMILY_ID,
        "source_contract_file_count": len(source_contracts),
        "primary_source_contract_count": len(primary),
        "projection_row_counts": {
            "boundaries": len(boundaries),
            "public_surface": len(public_rows),
            "layout": len(layout_rows),
            "topology": len(topology_rows),
        },
        "topology_source_dispositions": dispositions,
        "unmapped_public_surface_rows": unmapped_public_surface_rows,
        "registered_output_count": len(output_set),
    }
    return errors, summary


def _mirror_value_type(value: object) -> str:
    if value is _MISSING_VALUE:
        return "missing"
    if type(value) is list:
        item_types = sorted({type(item).__name__ for item in value})
        return f"list[{', '.join(item_types)}]"
    return type(value).__name__


def _mirror_value_matches_domain(
    value: object,
    domain: _MirrorFieldDomain,
    *,
    optional: bool = False,
) -> bool:
    if optional and value is None:
        return True
    if domain == "string":
        return type(value) is str
    if domain == "boolean":
        return type(value) is bool
    if domain == "string_list":
        return type(value) is list and all(type(item) is str for item in value)
    if domain == "table":
        return type(value) is dict
    return False


def _validate_mirror_value(
    findings: list[Finding],
    subject: str,
    field: str,
    value: object,
    *,
    domain: _MirrorFieldDomain,
    side: str,
    optional: bool = False,
) -> bool:
    if _mirror_value_matches_domain(value, domain, optional=optional):
        return True
    optional_suffix = " or absent" if optional else ""
    findings.append(
        Finding(
            "package-mirror",
            "error",
            subject,
            f"{field} has malformed {side} value",
            f"expected {domain}{optional_suffix}; got {_mirror_value_type(value)}",
        )
    )
    return False


def _record_malformed_mirror_value(
    findings: list[Finding],
    subject: str,
    field: str,
    value: object,
    *,
    domain: _MirrorFieldDomain,
    side: str,
    optional: bool = False,
) -> None:
    _validate_mirror_value(
        findings,
        subject,
        field,
        value,
        domain=domain,
        side=side,
        optional=optional,
    )


def _compare_typed_value(
    findings: list[Finding],
    subject: str,
    field: str,
    *,
    expected: object,
    observed: object,
    domain: _MirrorFieldDomain,
    optional: bool = False,
) -> None:
    expected_valid = _validate_mirror_value(
        findings,
        subject,
        field,
        expected,
        domain=domain,
        side="source",
        optional=optional,
    )
    observed_valid = _validate_mirror_value(
        findings,
        subject,
        field,
        observed,
        domain=domain,
        side="projection",
        optional=optional,
    )
    if expected_valid and observed_valid and expected != observed:
        findings.append(
            Finding(
                "package-mirror",
                "error",
                subject,
                f"{field} drift",
                f"expected={expected!r} observed={observed!r}",
            )
        )


def _compare_scalar(
    findings: list[Finding],
    subject: str,
    field: str,
    *,
    expected: object,
    observed: object,
) -> None:
    _compare_typed_value(
        findings,
        subject,
        field,
        expected=expected,
        observed=observed,
        domain="string",
    )


def _compare_boolean(
    findings: list[Finding],
    subject: str,
    field: str,
    *,
    expected: object,
    observed: object,
) -> None:
    _compare_typed_value(
        findings,
        subject,
        field,
        expected=expected,
        observed=observed,
        domain="boolean",
    )


def _compare_list(
    findings: list[Finding],
    subject: str,
    field: str,
    *,
    expected: object,
    observed: object,
) -> None:
    _compare_typed_value(
        findings,
        subject,
        field,
        expected=expected,
        observed=observed,
        domain="string_list",
    )


def _compare_optional_scalar(
    findings: list[Finding],
    subject: str,
    field: str,
    *,
    expected: object,
    observed: object,
) -> None:
    _compare_typed_value(
        findings,
        subject,
        field,
        expected=expected,
        observed=observed,
        domain="string",
        optional=True,
    )


def _compare_optional_list(
    findings: list[Finding],
    subject: str,
    field: str,
    *,
    expected: object,
    observed: object,
) -> None:
    _compare_typed_value(
        findings,
        subject,
        field,
        expected=expected,
        observed=observed,
        domain="string_list",
        optional=True,
    )


def _validate_module_size_budget(repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    data = _read_toml(repo_root / "architecture" / "module_size_budget.toml")
    header = data.get("module_size_budget", {})
    validation_header = data.get("validation_tooling_size_budget", {})
    if int(header.get("default_warning_lines", 0)) != 1000:
        findings.append(
            Finding(
                "module-size",
                "error",
                "architecture/module_size_budget.toml",
                "default warning line budget is not 1000",
                str(header.get("default_warning_lines")),
            )
        )
    if int(header.get("default_fail_closed_target_lines", 0)) != 2500:
        findings.append(
            Finding(
                "module-size",
                "report_only",
                "architecture/module_size_budget.toml",
                "default fail-closed target is not 2500",
                str(header.get("default_fail_closed_target_lines")),
            )
        )
    if not validation_header:
        findings.append(
            Finding(
                "module-size",
                "error",
                "architecture/module_size_budget.toml",
                "validation tooling size budget is missing",
            )
        )
    else:
        findings.extend(_validate_validation_tooling_defaults(validation_header))

    budgets = data.get("budget", [])
    validation_scope = [
        str(item) for item in validation_header.get("scope", []) if str(item).strip()
    ]
    budget_by_path = {
        str(budget.get("path", "")): budget
        for budget in budgets
        if str(budget.get("path", "")).strip()
    }
    if validation_header:
        findings.extend(
            _validate_validation_tooling_budget_coverage(
                repo_root,
                budget_by_path=budget_by_path,
                validation_header=validation_header,
                validation_scope=validation_scope,
            )
        )

    for budget in budgets:
        relative = str(budget.get("path", ""))
        if _matches_any_validation_scope(relative, validation_scope):
            findings.extend(
                _validate_validation_tooling_budget_entry(
                    repo_root,
                    budget,
                    validation_header=validation_header,
                    validation_scope=validation_scope,
                )
            )
            continue
        path = repo_root / relative
        subject = relative or "architecture/module_size_budget.toml"
        for field in (
            "owner",
            "current_lines",
            "target_lines",
            "shrink_plan",
            "extraction_sequence",
            "risk_notes",
        ):
            if field not in budget or budget[field] in ("", [], None):
                findings.append(
                    Finding(
                        "module-size",
                        "report_only",
                        subject,
                        "budget is missing Phase 4.3 shrink metadata",
                        field,
                    )
                )
        extraction_sequence = budget.get("extraction_sequence", [])
        if extraction_sequence and (
            not isinstance(extraction_sequence, list)
            or any(not str(item).strip() for item in extraction_sequence)
        ):
            findings.append(
                Finding(
                    "module-size",
                    "report_only",
                    subject,
                    "extraction sequence must be a non-empty list of responsibility names",
                )
            )
        if not path.exists():
            findings.append(
                Finding("module-size", "report_only", relative, "budgeted module is missing")
            )
            continue
        current_lines = _count_lines(path)
        current_budget = int(budget.get("current_lines", 0))
        limit = int(budget.get("report_only_limit_lines", 0))
        target = int(budget.get("target_lines", 0))
        baseline = int(budget.get("baseline_lines", 0))
        if current_budget and current_lines > current_budget:
            findings.append(
                Finding(
                    "module-size",
                    "report_only",
                    relative,
                    "module grew above Phase 4.3 current-line budget",
                    f"current={current_lines} current_budget={current_budget}",
                )
            )
        if current_lines > limit:
            findings.append(
                Finding(
                    "module-size",
                    "report_only",
                    relative,
                    "module exceeds report-only limit",
                    f"current={current_lines} limit={limit}",
                )
            )
        if target > int(header.get("default_fail_closed_target_lines", 2500)):
            findings.append(
                Finding(
                    "module-size",
                    "report_only",
                    relative,
                    "target is above default fail-closed target",
                    str(target),
                )
            )
        if baseline < target:
            findings.append(
                Finding(
                    "module-size",
                    "report_only",
                    relative,
                    "baseline is already below target; budget should be removed or tightened",
                    f"baseline={baseline} target={target}",
                )
            )
    return findings


def _validate_validation_tooling_defaults(header: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    subject = "architecture/module_size_budget.toml"
    scope = header.get("scope", [])
    if scope != ["tools/quality/validation/**/*.py"]:
        findings.append(
            Finding(
                "module-size",
                "error",
                subject,
                "validation tooling size budget must cover tools/quality/validation/**/*.py",
                str(scope),
            )
        )
    if int(header.get("warning_lines", 0)) != 1000:
        findings.append(
            Finding(
                "module-size",
                "error",
                subject,
                "validation tooling warning line budget is not 1000",
                str(header.get("warning_lines")),
            )
        )
    if int(header.get("fail_closed_lines", 0)) != 2000:
        findings.append(
            Finding(
                "module-size",
                "error",
                subject,
                "validation tooling fail-closed line budget is not 2000",
                str(header.get("fail_closed_lines")),
            )
        )
    return findings


def _validate_validation_tooling_budget_coverage(
    repo_root: Path,
    *,
    budget_by_path: dict[str, dict[str, Any]],
    validation_header: dict[str, Any],
    validation_scope: list[str],
) -> list[Finding]:
    findings: list[Finding] = []
    warning = int(validation_header.get("require_budget_above_lines", 0)) or int(
        validation_header.get("warning_lines", 1000)
    )
    for path in _validation_tooling_paths(repo_root, validation_scope):
        relative = _relative(path, repo_root)
        logical_lines = _count_lines(path)
        if logical_lines <= warning or relative in budget_by_path:
            continue
        findings.append(
            Finding(
                "module-size",
                "error",
                relative,
                "validation tooling above warning threshold lacks a module-size budget",
                f"logical_lines={logical_lines} warning={warning}",
            )
        )
    return findings


def _validate_validation_tooling_budget_entry(
    repo_root: Path,
    budget: dict[str, Any],
    *,
    validation_header: dict[str, Any],
    validation_scope: list[str],
) -> list[Finding]:
    findings: list[Finding] = []
    relative = str(budget.get("path", ""))
    path = repo_root / relative
    subject = relative or "architecture/module_size_budget.toml"
    if not _matches_any_validation_scope(relative, validation_scope):
        return findings
    warning = int(validation_header.get("warning_lines", 1000))
    fail_closed = int(validation_header.get("fail_closed_lines", 2000))
    if int(budget.get("warning_lines", 0)) != warning:
        findings.append(
            Finding(
                "module-size",
                "error",
                subject,
                "validation tooling budget warning_lines must match validation default",
                str(budget.get("warning_lines")),
            )
        )
    if int(budget.get("fail_closed_lines", 0)) != fail_closed:
        findings.append(
            Finding(
                "module-size",
                "error",
                subject,
                "validation tooling budget fail_closed_lines must match validation default",
                str(budget.get("fail_closed_lines")),
            )
        )
    if not path.exists():
        findings.append(Finding("module-size", "error", subject, "budgeted module is missing"))
        return findings

    current_lines = _count_lines(path)
    current_budget = int(budget.get("current_lines", 0))
    baseline = int(budget.get("baseline_lines", 0))
    limit = int(budget.get("report_only_limit_lines", 0))
    if current_budget and current_lines > current_budget:
        findings.append(
            Finding(
                "module-size",
                "error",
                subject,
                "validation tooling grew above its ratcheted current_lines budget",
                f"current={current_lines} budget={current_budget}",
            )
        )
    if limit and current_lines > limit:
        findings.append(
            Finding(
                "module-size",
                "error",
                subject,
                "validation tooling grew above its report_only_limit_lines ratchet",
                f"current={current_lines} limit={limit}",
            )
        )
    if current_lines <= warning:
        return findings

    if not str(budget.get("owner", "")).startswith("team-"):
        findings.append(
            Finding(
                "module-size",
                "error",
                subject,
                "validation tooling above warning threshold must declare a team owner",
                str(budget.get("owner", "")),
            )
        )
    if not baseline:
        findings.append(
            Finding(
                "module-size",
                "error",
                subject,
                "validation tooling above warning threshold must pin baseline_lines",
            )
        )
    elif current_lines > baseline:
        findings.append(
            Finding(
                "module-size",
                "error",
                subject,
                "validation tooling grew above its pinned baseline",
                f"current={current_lines} baseline={baseline}",
            )
        )
    if limit != baseline:
        findings.append(
            Finding(
                "module-size",
                "error",
                subject,
                "validation tooling above warning threshold must use a no-growth ratchet",
                f"baseline={baseline} report_only_limit_lines={limit}",
            )
        )
    extraction_sequence = budget.get("extraction_sequence", [])
    if (
        not isinstance(extraction_sequence, list)
        or not extraction_sequence
        or any(not str(item).strip() for item in extraction_sequence)
    ):
        findings.append(
            Finding(
                "module-size",
                "error",
                subject,
                "validation tooling above warning threshold must declare extraction sequence",
            )
        )
    target_date = str(budget.get("target_date", ""))
    if not target_date:
        findings.append(
            Finding(
                "module-size",
                "error",
                subject,
                "validation tooling above warning threshold must declare extraction target date",
            )
        )
    elif not _valid_future_or_today(target_date):
        findings.append(
            Finding(
                "module-size",
                "error",
                subject,
                "validation tooling extraction target date must be today or future",
                target_date,
            )
        )
    target = int(budget.get("target_lines", 0))
    if target and target > warning:
        findings.append(
            Finding(
                "module-size",
                "error",
                subject,
                "validation tooling extraction target must be at or below warning threshold",
                str(target),
            )
        )
    return findings


def _validation_tooling_paths(repo_root: Path, validation_scope: list[str]) -> list[Path]:
    paths: set[Path] = set()
    for pattern in validation_scope:
        paths.update(path for path in repo_root.glob(pattern) if path.is_file())
    return sorted(paths)


def _matches_any_validation_scope(relative: str, validation_scope: list[str]) -> bool:
    return any(_matches_validation_scope(relative, pattern) for pattern in validation_scope)


def _matches_validation_scope(relative: str, pattern: str) -> bool:
    if fnmatch.fnmatch(relative, pattern):
        return True
    if pattern == "tools/quality/validation/**/*.py":
        return relative.startswith("tools/quality/validation/") and relative.endswith(".py")
    return False


def _count_lines(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip() and not line.lstrip().startswith("#"))


def _validate_generated_artifact_contracts(
    repo_root: Path,
    *,
    family_admission: _PackageMirrorFamilyAdmission | None = None,
) -> list[Finding]:
    relative_path = "architecture/generated_artifacts.toml"
    path = repo_root / relative_path
    if not path.exists():
        return [Finding("generated-artifacts", "error", relative_path, "contract file is missing")]
    admission = family_admission or _admit_package_mirror_family_registry(repo_root)
    errors: list[Finding] = _family_registry_findings(admission, check="generated-artifacts")
    allowed_lifecycles = {
        "source_committed",
        "generated_committed",
        "generated_ignored",
        "runtime_ignored",
        "scratch_ignored",
    }
    allowed_stale_behaviors = {
        "fail",
        "warn",
        "cleanup_eligible",
        "ignored_by_policy",
        "block_release",
    }
    required_fields = (
        "id",
        "owner",
        "lifecycle",
        "generator",
        "verifier",
        "promotion_target",
        "stale_output_behavior",
    )
    for family in admission.rows:
        subject = str(family.get("id") or "family")
        for field in required_fields:
            if family.get(field) in (None, "", []):
                errors.append(
                    Finding(
                        "generated-artifacts",
                        "error",
                        subject,
                        f"missing required field `{field}`",
                    )
                )
        lifecycle = str(family.get("lifecycle", ""))
        if lifecycle and lifecycle not in allowed_lifecycles:
            errors.append(
                Finding(
                    "generated-artifacts",
                    "error",
                    subject,
                    "invalid lifecycle",
                    lifecycle,
                )
            )
        stale = str(family.get("stale_output_behavior", ""))
        if stale and stale not in allowed_stale_behaviors:
            errors.append(
                Finding(
                    "generated-artifacts",
                    "error",
                    subject,
                    "invalid stale_output_behavior",
                    stale,
                )
            )
        commit_policy = str(family.get("commit_policy", ""))
        if commit_policy == "local_ignored" and lifecycle == "generated_committed":
            errors.append(
                Finding(
                    "generated-artifacts",
                    "error",
                    subject,
                    "local_ignored family cannot use generated_committed lifecycle",
                )
            )
        if commit_policy == "committed" and lifecycle in {"generated_ignored", "runtime_ignored"}:
            errors.append(
                Finding(
                    "generated-artifacts",
                    "error",
                    subject,
                    "committed family must not use ignored lifecycle without splitting the family",
                    lifecycle,
                )
            )
    return errors


def _validate_list_contract(
    repo_root: Path,
    *,
    relative_path: str,
    header: str,
    entries: str,
    required_fields: tuple[str, ...],
    path_fields: tuple[str, ...] = (),
    list_path_fields: tuple[str, ...] = (),
    allowed_header_statuses: tuple[str, ...] = ("report_only",),
    allowed_entry_modes: tuple[str, ...] = ("report_only",),
) -> list[Finding]:
    errors: list[Finding] = []
    path = repo_root / relative_path
    if not path.exists():
        return [Finding("contract", "error", relative_path, "contract file is missing")]
    data = _read_toml(path)
    header_data = data.get(header, {})
    if header_data.get("status") not in allowed_header_statuses:
        errors.append(
            Finding(
                "contract",
                "error",
                relative_path,
                f"[{header}].status must be one of {allowed_header_statuses}",
                str(header_data.get("status")),
            )
        )
    for item in data.get(entries, []):
        subject = str(item.get("id") or item.get("path") or entries)
        if item.get("mode") not in {None, *allowed_entry_modes}:
            errors.append(
                Finding(
                    "contract",
                    "error",
                    subject,
                    f"entry mode must be one of {allowed_entry_modes}",
                    str(item.get("mode")),
                )
            )
        for field in required_fields:
            if item.get(field) in (None, "", []):
                errors.append(
                    Finding("contract", "error", subject, f"missing required field `{field}`")
                )
        for field in path_fields:
            value = item.get(field)
            if value and not _path_pattern_exists(repo_root, str(value)):
                errors.append(
                    Finding(
                        "contract", "error", subject, f"path field `{field}` is missing", str(value)
                    )
                )
        for field in list_path_fields:
            for value in item.get(field, []):
                if str(value).startswith("_build/"):
                    continue
                if not _path_pattern_exists(repo_root, str(value)):
                    errors.append(
                        Finding(
                            "contract",
                            "error",
                            subject,
                            f"path list `{field}` contains a missing path",
                            str(value),
                        )
                    )
    return errors


def _read_declared_active_component_index(
    repo_root: Path,
    relative_path: str,
) -> tuple[dict[str, Any] | None, Finding | None]:
    """Read the declared active index through one typed, root-bound byte snapshot.

    Args:
        repo_root: Product root containing the declared component index.
        relative_path: Validated repository-relative index path.

    Returns:
        The parsed index and no finding, or no index and one typed input finding.
    """
    path = repo_root / Path(*PurePosixPath(relative_path).parts)
    try:
        resolved_path = resolve_admitted_path(path, repo_root)
    except AdmittedPathError as error:
        return None, Finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index resolves outside repository root",
            f"error={type(error).__name__}",
        )
    except FileNotFoundError as error:
        return None, Finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index file is missing",
            f"error={type(error).__name__}",
        )
    except PermissionError as error:
        return None, Finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index is not readable",
            f"error={type(error).__name__}",
        )
    except (OSError, RuntimeError) as error:
        return None, Finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index could not be resolved",
            f"error={type(error).__name__}",
        )

    try:
        file_stat = resolved_path.stat()
    except FileNotFoundError as error:
        return None, Finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index file is missing",
            f"error={type(error).__name__}",
        )
    except PermissionError as error:
        return None, Finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index is not readable",
            f"error={type(error).__name__}",
        )
    except OSError as error:
        return None, Finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index could not be inspected",
            f"error={type(error).__name__}",
        )

    if not stat.S_ISREG(file_stat.st_mode):
        return None, Finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index is not a regular file",
        )

    try:
        return _read_toml(resolved_path), None
    except FileNotFoundError as error:
        return None, Finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index file is missing",
            f"error={type(error).__name__}",
        )
    except IsADirectoryError as error:
        return None, Finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index is not a regular file",
            f"error={type(error).__name__}",
        )
    except PermissionError as error:
        return None, Finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index is not readable",
            f"error={type(error).__name__}",
        )
    except UnicodeDecodeError as error:
        return None, Finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index is not valid UTF-8",
            f"error={type(error).__name__}",
        )
    except tomllib.TOMLDecodeError as error:
        return None, Finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index is not valid TOML",
            f"error={type(error).__name__}",
        )
    except OSError as error:
        return None, Finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index could not be read",
            f"error={type(error).__name__}",
        )


def _validate_legacy_operability_routes(
    repo_root: Path,
) -> tuple[list[Finding], dict[str, Any]]:
    """Reconcile every legacy runbook/SLO occurrence with the active component index.

    Args:
        repo_root: Product root containing the legacy declarations and active component index.

    Returns:
        Route findings and a report-only summary preserving each source occurrence.
    """
    source_specs = (
        (
            "architecture/runbook_coverage.toml",
            "coverage",
            ("runbooks", "slo_files"),
        ),
        (
            "architecture/component_observability.toml",
            "component",
            ("slo_files",),
        ),
    )
    findings: list[Finding] = []
    route_map: dict[str, list[dict[str, str]]] = {}
    source_documents = {
        source_path: _read_toml(repo_root / source_path) for source_path, _, _ in source_specs
    }
    runbook_source_path = "architecture/runbook_coverage.toml"
    runbook_header = source_documents[runbook_source_path].get("runbook_coverage", _MISSING_VALUE)
    active_index_path = runbook_source_path
    active_components: Any = []
    route_index_available = False
    if type(runbook_header) is not dict:
        findings.append(
            Finding(
                "operability-route",
                "error",
                runbook_source_path,
                "runbook coverage must name its active component index",
            )
        )
    else:
        declared_index = runbook_header.get("component_index", _MISSING_VALUE)
        if type(declared_index) is not str or not declared_index:
            findings.append(
                Finding(
                    "operability-route",
                    "error",
                    runbook_source_path,
                    "runbook coverage component_index must be a nonempty repository-relative path",
                )
            )
        else:
            index_relative = PurePosixPath(declared_index)
            if "\x00" in declared_index:
                findings.append(
                    Finding(
                        "operability-route",
                        "error",
                        runbook_source_path,
                        "runbook coverage component_index must not contain NUL",
                        repr(declared_index),
                    )
                )
            elif index_relative.is_absolute() or ".." in index_relative.parts:
                findings.append(
                    Finding(
                        "operability-route",
                        "error",
                        runbook_source_path,
                        "runbook coverage component_index must stay within the repository",
                        declared_index,
                    )
                )
            else:
                active_index_path = index_relative.as_posix()
                active_index, index_finding = _read_declared_active_component_index(
                    repo_root, active_index_path
                )
                if index_finding is not None:
                    findings.append(index_finding)
                elif active_index is not None:
                    active_components = active_index.get("component", _MISSING_VALUE)
                    if type(active_components) is list:
                        route_index_available = True
                    else:
                        findings.append(
                            Finding(
                                "operability-route",
                                "error",
                                active_index_path,
                                "active component registry must contain a component array",
                            )
                        )
                        active_components = []

    registry_validation_start = len(findings)
    for index, component in enumerate(active_components):
        if type(component) is not dict:
            findings.append(
                Finding(
                    "operability-route",
                    "error",
                    active_index_path,
                    "active component registry row must be a table",
                    f"index={index}",
                )
            )
            continue
        component_id = component.get("id")
        owner = component.get("owner")
        if type(component_id) is not str or not component_id:
            findings.append(
                Finding(
                    "operability-route",
                    "error",
                    active_index_path,
                    "active route row must declare a string component id",
                    f"index={index}",
                )
            )
            continue
        if type(owner) is not str or not owner:
            findings.append(
                Finding(
                    "operability-route",
                    "error",
                    active_index_path,
                    "active route row must declare a string owner",
                    f"component={component_id}",
                )
            )
            continue

        for field in ("runbooks", "slo_file", "legacy_slo_files"):
            raw_paths = component.get(field, _MISSING_VALUE)
            if raw_paths is _MISSING_VALUE:
                if field == "legacy_slo_files":
                    continue
                expected = "a string" if field == "slo_file" else "an array"
                findings.append(
                    Finding(
                        "operability-route",
                        "error",
                        active_index_path,
                        f"active route row must declare `{field}` {expected}",
                        f"component={component_id}",
                    )
                )
                continue
            if field == "slo_file":
                if type(raw_paths) is not str or not raw_paths:
                    findings.append(
                        Finding(
                            "operability-route",
                            "error",
                            active_index_path,
                            "active route field `slo_file` must be a nonempty string",
                            f"component={component_id}",
                        )
                    )
                    continue
                paths = [raw_paths]
            elif type(raw_paths) is list:
                paths = raw_paths
                if field == "runbooks" and not paths:
                    findings.append(
                        Finding(
                            "operability-route",
                            "error",
                            active_index_path,
                            "active route field `runbooks` must be a nonempty array",
                            f"component={component_id}",
                        )
                    )
                    continue
            else:
                findings.append(
                    Finding(
                        "operability-route",
                        "error",
                        active_index_path,
                        f"active route field `{field}` must be an array",
                        f"component={component_id}",
                    )
                )
                continue
            for path_index, path in enumerate(paths):
                if type(path) is not str or not path:
                    findings.append(
                        Finding(
                            "operability-route",
                            "error",
                            active_index_path,
                            f"active route field `{field}` must contain nonempty strings",
                            f"component={component_id} index={path_index}",
                        )
                    )
                    continue
                route_map.setdefault(path, []).append({"component": component_id, "owner": owner})

    if len(findings) > registry_validation_start:
        # A partial route map cannot establish absence for any legacy reference.
        route_index_available = False

    occurrences: list[dict[str, Any]] = []
    for source_path, entry_table, fields in source_specs:
        contract = _read_toml(repo_root / source_path)
        rows = contract.get(entry_table, _MISSING_VALUE)
        if type(rows) is not list:
            findings.append(
                Finding(
                    "operability-route",
                    "error",
                    source_path,
                    f"legacy route source must contain a `{entry_table}` array",
                )
            )
            continue
        for row_index, row in enumerate(rows):
            if type(row) is not dict:
                findings.append(
                    Finding(
                        "operability-route",
                        "error",
                        source_path,
                        "legacy route source row must be a table",
                        f"index={row_index}",
                    )
                )
                continue
            row_id = row.get("id", row.get("component", _MISSING_VALUE))
            if type(row_id) is not str or not row_id:
                row_id = f"{entry_table}[{row_index}]"
            for field in fields:
                raw_paths = row.get(field, _MISSING_VALUE)
                if raw_paths is _MISSING_VALUE:
                    continue
                if type(raw_paths) is not list:
                    findings.append(
                        Finding(
                            "operability-route",
                            "error",
                            source_path,
                            f"legacy route field `{field}` must be an array",
                            f"row={row_id}",
                        )
                    )
                    continue
                for path_index, path in enumerate(raw_paths):
                    if type(path) is not str or not path:
                        findings.append(
                            Finding(
                                "operability-route",
                                "error",
                                source_path,
                                f"legacy route field `{field}` must contain nonempty strings",
                                f"row={row_id} index={path_index}",
                            )
                        )
                        continue
                    active_routes = (
                        sorted(
                            route_map.get(path, []),
                            key=lambda item: (item["component"], item["owner"]),
                        )
                        if route_index_available
                        else None
                    )
                    routed = bool(active_routes) if route_index_available else None
                    occurrence = {
                        "source_file": source_path,
                        "source_row": row_id,
                        "field": field,
                        "path": path,
                        "active_routes": active_routes,
                        "routed": routed,
                    }
                    occurrences.append(occurrence)
                    if routed is False:
                        findings.append(
                            Finding(
                                "operability-route",
                                "error",
                                path,
                                "legacy operational reference has no active component route",
                                f"source={source_path} row={row_id} field={field}",
                            )
                        )

    by_source: dict[str, dict[str, dict[str, int]]] = {}
    for source_path, _, fields in source_specs:
        by_source[source_path] = {}
        for field in fields:
            field_occurrences = [
                occurrence
                for occurrence in occurrences
                if occurrence["source_file"] == source_path and occurrence["field"] == field
            ]
            routed_count = sum(
                1 for occurrence in field_occurrences if occurrence["routed"] is True
            )
            unrouted_count = sum(
                1 for occurrence in field_occurrences if occurrence["routed"] is False
            )
            unresolved_count = sum(
                1 for occurrence in field_occurrences if occurrence["routed"] is None
            )
            by_source[source_path][field] = {
                "occurrence_count": len(field_occurrences),
                "routed_occurrence_count": routed_count,
                "unrouted_occurrence_count": unrouted_count,
            }
            if unresolved_count:
                by_source[source_path][field]["unresolved_occurrence_count"] = unresolved_count

    unrouted = [occurrence for occurrence in occurrences if occurrence["routed"] is False]
    unresolved = [occurrence for occurrence in occurrences if occurrence["routed"] is None]
    summary = {
        "status": "failed" if findings else "passed",
        "occurrence_count": len(occurrences),
        "routed_occurrence_count": sum(
            1 for occurrence in occurrences if occurrence["routed"] is True
        ),
        "unrouted_occurrence_count": len(unrouted),
        "by_source": by_source,
        "missing_occurrences": unrouted,
        "occurrences": occurrences,
    }
    if not route_index_available:
        summary["route_index_available"] = False
        summary["unresolved_occurrences"] = unresolved
    return findings, summary


def _validate_extension_points_contract(repo_root: Path) -> list[Finding]:
    relative_path = "architecture/extension_points.toml"
    path = repo_root / relative_path
    if not path.exists():
        return [Finding("extension-points", "error", relative_path, "contract file is missing")]
    data = _read_toml(path)
    errors: list[Finding] = []
    header = data.get("extension_points", {})
    if not header.get("owner"):
        errors.append(Finding("extension-points", "error", relative_path, "missing owner"))
    overlay = data.get("phase_1_3_report_only_overlay", {})
    if overlay.get("status") != "report_only":
        errors.append(
            Finding(
                "extension-points",
                "error",
                relative_path,
                "Phase 1.3 overlay must be report_only",
                str(overlay.get("status")),
            )
        )
    for item in data.get("extension_point", []):
        subject = str(item.get("name") or item.get("id") or "extension_point")
        for field in ("owner", "contract", "contract_version"):
            if not item.get(field):
                errors.append(Finding("extension-points", "error", subject, f"missing `{field}`"))
    for item in data.get("phase_1_3_extension_point", []):
        subject = str(item.get("id") or "phase_1_3_extension_point")
        for field in ("id", "owner", "package", "surface", "boundary_contract", "mode"):
            if not item.get(field):
                errors.append(Finding("extension-points", "error", subject, f"missing `{field}`"))
        if item.get("mode") != "report_only":
            errors.append(
                Finding(
                    "extension-points",
                    "error",
                    subject,
                    "Phase 1.3 extension point mode must be report_only",
                    str(item.get("mode")),
                )
            )
        contract = str(item.get("boundary_contract", ""))
        if contract and not _path_pattern_exists(repo_root, contract):
            errors.append(
                Finding(
                    "extension-points",
                    "error",
                    subject,
                    "boundary contract is missing",
                    contract,
                )
            )
    return errors


def _validate_directory_contracts(repo_root: Path) -> list[Finding]:
    relative_path = "architecture/policies/directory_contracts.toml"
    path = repo_root / relative_path
    if not path.exists():
        return [Finding("directory-contracts", "error", relative_path, "contract file is missing")]
    data = _read_toml(path)
    errors: list[Finding] = []
    header = data.get("directory_contracts", {})
    if not header.get("owner"):
        errors.append(Finding("directory-contracts", "error", relative_path, "missing owner"))
    for field in (
        "topology_source",
        "generated_artifacts_source",
        "local_runtime_state_source",
        "data_policy_source",
    ):
        value = str(header.get(field, ""))
        if not value:
            errors.append(
                Finding("directory-contracts", "error", relative_path, f"missing `{field}`")
            )
        elif not _path_pattern_exists(repo_root, value):
            errors.append(
                Finding(
                    "directory-contracts",
                    "error",
                    relative_path,
                    f"`{field}` path is missing",
                    value,
                )
            )
    threshold = data.get("high_volume_subtree_threshold", {})
    for field in (
        "tracked_file_count_at_least",
        "immediate_child_directory_count_greater_than",
        "module_line_count_warning_source",
        "local_documentation_requirement",
    ):
        if threshold.get(field) in (None, "", []):
            errors.append(
                Finding(
                    "directory-contracts",
                    "error",
                    "high_volume_subtree_threshold",
                    f"missing `{field}`",
                )
            )
    required_contract_fields = (
        "path",
        "status",
        "role",
        "owner",
        "lifecycle_class",
        "topology_category",
        "topology_commit_policy",
        "allowed_file_kinds",
        "allowed_child_directory_kinds",
        "python_import_policy",
        "generated_output_policy",
        "committed_data_policy",
        "readme_index_requirement",
        "max_root_loose_files",
        "root_loose_file_policy",
        "ignored_descendant_retention",
        "evidence_or_generated_artifact_promotion_path",
    )
    contracts = {str(item.get("path", "")): item for item in data.get("contract", [])}
    expected_roots = {
        "architecture",
        "benchmarks",
        "data",
        "design",
        "docs",
        "examples",
        "frontend",
        "apps",
        "ops",
        "packages",
        "release",
        "release-fragments",
        "schemas",
        "src",
        "tests",
        "tools",
        "_build",
        "_cache",
        ".polisyos",
        ".venv",
        "node_modules",
    }
    for root in sorted(expected_roots - set(contracts)):
        errors.append(Finding("directory-contracts", "error", root, "missing top-level contract"))
    for subject, contract in contracts.items():
        for field in required_contract_fields:
            if contract.get(field) in (None, "", []):
                errors.append(
                    Finding(
                        "directory-contracts", "error", subject, f"missing required field `{field}`"
                    )
                )
        if (
            contract.get("status") != "reserved_future"
            and contract.get("owner") != "local"
            and subject
            and not _path_pattern_exists(repo_root, subject)
        ):
            errors.append(
                Finding(
                    "directory-contracts",
                    "error",
                    subject,
                    "contracted top-level path is missing",
                )
            )
    topology_paths = {
        str(item.get("path", "")): item
        for item in _read_toml(repo_root / "architecture" / "topology.toml").get("path", [])
    }
    for subject, contract in contracts.items():
        if subject in topology_paths:
            topology_entry = topology_paths[subject]
            if contract.get("topology_category") != topology_entry.get("category"):
                errors.append(
                    Finding(
                        "directory-contracts",
                        "error",
                        subject,
                        "topology_category contradicts architecture/topology.toml",
                        (
                            f"contract={contract.get('topology_category')} "
                            f"topology={topology_entry.get('category')}"
                        ),
                    )
                )
            if contract.get("topology_commit_policy") != topology_entry.get("commit_policy"):
                errors.append(
                    Finding(
                        "directory-contracts",
                        "error",
                        subject,
                        "topology_commit_policy contradicts architecture/topology.toml",
                        (
                            f"contract={contract.get('topology_commit_policy')} "
                            f"topology={topology_entry.get('commit_policy')}"
                        ),
                    )
                )
    asset_classes = {str(item.get("id", "")): item for item in data.get("asset_class", [])}
    for asset_id in (
        "product_seed_assets",
        "test_fixtures",
        "golden_records",
        "examples_tutorial_assets",
    ):
        if asset_id not in asset_classes:
            errors.append(Finding("directory-contracts", "error", asset_id, "missing asset class"))
    ratchets = _read_toml(repo_root / "architecture" / "tests" / "ratchets.toml")
    fixture_policy = ratchets.get("fixture_policy", {})
    test_fixtures = asset_classes.get("test_fixtures", {})
    golden_records = asset_classes.get("golden_records", {})
    _validate_root_transition(
        errors,
        asset_id="test_fixtures",
        asset=test_fixtures,
        current_root=str(fixture_policy.get("shared_fixture_root", "")),
        target_roots=fixture_policy.get("target_fixture_roots", []),
    )
    _validate_root_transition(
        errors,
        asset_id="golden_records",
        asset=golden_records,
        current_root=str(fixture_policy.get("shared_golden_root", "")),
        target_roots=fixture_policy.get("target_golden_roots", []),
    )
    non_product_roots = {
        str(item.get("path", "")): item for item in data.get("non_product_python_root", [])
    }
    for root in ("tools", "tests", "benchmarks", "schemas"):
        item = non_product_roots.get(root)
        if item is None:
            errors.append(
                Finding(
                    "directory-contracts", "error", root, "missing non-product Python root policy"
                )
            )
            continue
        for field in ("policy", "owner", "allowed_reason", "product_import_policy"):
            if item.get(field) in (None, "", []):
                errors.append(
                    Finding(
                        "directory-contracts", "error", root, f"missing non-product field `{field}`"
                    )
                )
    archive_classes = {str(item.get("id", "")) for item in data.get("archive_class", [])}
    for archive_id in (
        "accepted_plans",
        "historical_plans",
        "release_evidence",
        "local_audit_reports",
        "generated_benchmark_reports",
        "incident_postmortem_records",
    ):
        if archive_id not in archive_classes:
            errors.append(
                Finding("directory-contracts", "error", archive_id, "missing archive class")
            )
    overlay = data.get("phase_1_3_report_only_overlay", {})
    if overlay.get("status") != "report_only":
        errors.append(
            Finding(
                "directory-contracts",
                "error",
                relative_path,
                "Phase 1.3 overlay must be report_only",
                str(overlay.get("status")),
            )
        )
    for item in data.get("phase_1_3_directory", []):
        subject = str(item.get("path") or "phase_1_3_directory")
        for field in ("path", "group", "owner", "physical_status", "mode"):
            if not item.get(field):
                errors.append(
                    Finding("directory-contracts", "error", subject, f"missing `{field}`")
                )
        if item.get("mode") != "report_only":
            errors.append(
                Finding(
                    "directory-contracts",
                    "error",
                    subject,
                    "Phase 1.3 directory mode must be report_only",
                    str(item.get("mode")),
                )
            )
        directory = str(item.get("path", ""))
        if directory and not _path_pattern_exists(repo_root, directory):
            errors.append(
                Finding("directory-contracts", "error", subject, "directory is missing", directory)
            )
        for contract_file in item.get("contract_files", []):
            if not _path_pattern_exists(repo_root, str(contract_file)):
                errors.append(
                    Finding(
                        "directory-contracts",
                        "error",
                        subject,
                        "contract file is missing",
                        str(contract_file),
                    )
                )
    return errors


def _validate_directory_hygiene_assets(repo_root: Path) -> list[Finding]:
    from tools.quality.validation import directory_hygiene_assets

    report = directory_hygiene_assets.build_report(repo_root)
    return [
        Finding(
            "directory-hygiene-assets",
            str(item.get("severity", "error")),
            str(item.get("subject", "unknown")),
            str(item.get("message", "")),
            str(item.get("detail", "")),
        )
        for item in report["contract_errors"]
    ]


def _normalize_contract_root(value: str) -> str:
    return value.removesuffix("/")


def _validate_root_transition(
    errors: list[Finding],
    *,
    asset_id: str,
    asset: dict[str, Any],
    current_root: str,
    target_roots: object,
) -> None:
    current = _normalize_contract_root(current_root)
    current_roots = {
        _normalize_contract_root(str(item)) for item in asset.get("current_wave1_roots", [])
    }
    legacy_roots = {
        _normalize_contract_root(str(item).split(":", 1)[0])
        for item in asset.get("legacy_roots_until_phase", [])
    }
    allowed_roots = {_normalize_contract_root(str(item)) for item in asset.get("allowed_roots", [])}
    targets = (
        {_normalize_contract_root(str(item)) for item in target_roots if str(item)}
        if isinstance(target_roots, list)
        else set()
    )
    if current and current not in current_roots and current not in legacy_roots:
        errors.append(
            Finding(
                "directory-contracts",
                "error",
                asset_id,
                "current Wave 1 root is not declared as current or legacy",
                current,
            )
        )
    missing_targets = sorted(
        root for root in targets if root not in allowed_roots and "<package>" not in root
    )
    for target in missing_targets:
        errors.append(
            Finding(
                "directory-contracts",
                "error",
                asset_id,
                "target root from test_ratchets is not allowed by directory contract",
                target,
            )
        )


def _validate_import_reports(repo_root: Path) -> list[Finding]:
    errors = _validate_list_contract(
        repo_root,
        relative_path="architecture/imports/reports.toml",
        header="import_reports",
        entries="report",
        required_fields=("id", "owner", "mode", "source_contracts", "output", "command"),
        list_path_fields=("source_contracts",),
    )
    data = _read_toml(repo_root / "architecture" / "imports" / "reports.toml")
    for item in data.get("report", []):
        if item.get("mode") != "report_only":
            errors.append(
                Finding(
                    "import-reports",
                    "error",
                    str(item.get("id", "unknown")),
                    "import report mode must be report_only",
                    str(item.get("mode")),
                )
            )
    return errors


def _summarize_dynamic_imports(repo_root: Path) -> list[Finding]:
    summary = _dynamic_imports_summary(repo_root)
    return [
        Finding(
            "dynamic-imports",
            "report_only",
            "architecture/imports/dynamic.toml",
            "dynamic import registry summary",
            (
                f"patterns={summary['pattern_count']} "
                f"missing_target_slots={summary['missing_target_slots']}"
            ),
        )
    ]


def _dynamic_imports_summary(repo_root: Path) -> dict[str, Any]:
    data = _read_toml(repo_root / "architecture" / "imports" / "dynamic.toml")
    patterns = data.get("pattern", [])
    missing_targets = [
        str(item.get("id", "unknown"))
        for item in patterns
        if not item.get("target") and not item.get("allowed_targets")
    ]
    registered_targets = [
        str(target)
        for item in patterns
        for target in (item.get("target"), *item.get("allowed_targets", []))
        if target
    ]
    return {
        "status": str(data.get("dynamic_imports", {}).get("status", "")),
        "pattern_count": len(patterns),
        "missing_target_slots": len(missing_targets),
        "missing_target_ids": missing_targets,
        "registered_target_count": len(set(registered_targets)),
    }


def _validate_dynamic_imports_contract(repo_root: Path) -> list[Finding]:
    relative_path = "architecture/imports/dynamic.toml"
    path = repo_root / relative_path
    if not path.exists():
        return [Finding("dynamic-imports", "error", relative_path, "contract file is missing")]
    data = _read_toml(path)
    errors: list[Finding] = []
    header = data.get("dynamic_imports", {})
    for field in ("owner", "extension_points", "new_entry_required_fields"):
        if header.get(field) in (None, "", []):
            errors.append(Finding("dynamic-imports", "error", relative_path, f"missing `{field}`"))
    extension_points = str(header.get("extension_points", ""))
    if extension_points and not _path_pattern_exists(repo_root, extension_points):
        errors.append(
            Finding(
                "dynamic-imports",
                "error",
                relative_path,
                "extension_points path is missing",
                extension_points,
            )
        )
    for item in data.get("pattern", []):
        subject = str(item.get("id") or item.get("pattern") or "pattern")
        for field in ("id", "pattern", "source_file", "call", "owner", "verifier"):
            if item.get(field) in (None, "", []):
                errors.append(
                    Finding(
                        "dynamic-imports", "error", subject, f"missing required field `{field}`"
                    )
                )
        if item.get("target") in (None, "", []) and item.get("allowed_targets") in (None, "", []):
            errors.append(
                Finding(
                    "dynamic-imports",
                    "error",
                    subject,
                    "missing target or allowed_targets",
                )
            )
        source_file = str(item.get("source_file", ""))
        if source_file and not _path_pattern_exists(repo_root, source_file):
            errors.append(
                Finding("dynamic-imports", "error", subject, "source_file is missing", source_file)
            )
    return errors


def _validate_dynamic_imports_gate(repo_root: Path) -> list[Finding]:
    from tools.quality.validation import decomposition_preflight

    return _preflight_errors(
        check="dynamic-imports",
        findings=decomposition_preflight.validate_dynamic_imports(),
        repo_root=repo_root,
    )


def _validate_import_cycles_gate(repo_root: Path) -> list[Finding]:
    from tools.quality.validation import decomposition_preflight

    return _preflight_errors(
        check="import-cycle",
        findings=decomposition_preflight.validate_import_cycles(),
        repo_root=repo_root,
    )


def _validate_reexport_shim_shape_gate(repo_root: Path) -> list[Finding]:
    from tools.quality.validation import decomposition_preflight

    return _preflight_errors(
        check="reexport-shim-shape",
        findings=decomposition_preflight.validate_reexport_shim_shapes(),
        repo_root=repo_root,
    )


def _preflight_errors(
    *,
    check: str,
    findings: list[Any],
    repo_root: Path,
) -> list[Finding]:
    return [
        Finding(
            check,
            "error",
            str(getattr(finding, "gate", check)),
            str(getattr(finding, "message", "")),
            str(getattr(finding, "detail", "")),
        )
        for finding in findings
    ]


def _import_cycles_summary(repo_root: Path) -> dict[str, Any]:
    from tools.quality.validation import decomposition_preflight

    findings = decomposition_preflight.validate_import_cycles()
    lazy_path = repo_root / "architecture" / "imports" / "lazy.toml"
    allowed_cycle_count = 0
    if lazy_path.exists():
        allowed_cycle_count = len(_read_toml(lazy_path).get("allowed_cycle", []))
    return {
        "status": "fail_closed",
        "allowed_cycle_count": allowed_cycle_count,
        "new_cycle_count": len(findings),
        "new_cycle_examples": [str(getattr(finding, "detail", "")) for finding in findings[:25]],
    }


def _structure_gate_summary(repo_root: Path, *, gate: str) -> dict[str, Any]:
    from tools.quality.validation import repository_structure_phase0

    findings = repository_structure_phase0.collect_gate_findings(repo_root, gate)
    return {
        "mode": "report_only",
        "parallel_safety": (
            "active package move branches can keep layout/name-collision drift visible "
            "without making Phase 6.1 fail-closed"
        ),
        "finding_count": len(findings),
        "findings": findings[:25],
    }


def _structure_gate_findings(repo_root: Path, *, gate: str) -> list[Finding]:
    summary = _structure_gate_summary(repo_root, gate=gate)
    check = "package-layout" if gate == "loose_files" else "name-collision"
    findings: list[Finding] = []
    for item in summary["findings"]:
        subject = str(item.get("package") or item.get("name") or gate)
        findings.append(
            Finding(
                check,
                "report_only",
                subject,
                str(item.get("message", "")),
                json.dumps(item, sort_keys=True),
            )
        )
    return findings


def _validate_shim_expiry_contract(repo_root: Path) -> list[Finding]:
    relative_path = "architecture/shims.toml"
    path = repo_root / relative_path
    if not path.exists():
        return [Finding("shim-expiry", "error", relative_path, "shim registry is missing")]
    errors: list[Finding] = []
    today = dt.date.today()
    for shim in _read_toml(path).get("shim", []):
        subject = str(shim.get("id", "unknown"))
        for field in ("id", "source_path", "target_path", "type", "owner", "reason", "sunset_date"):
            if shim.get(field) in (None, "", []):
                errors.append(Finding("shim-expiry", "error", subject, f"missing `{field}`"))
        raw_sunset = str(shim.get("sunset_date", ""))
        try:
            sunset = dt.date.fromisoformat(raw_sunset)
        except ValueError:
            errors.append(
                Finding("shim-expiry", "error", subject, "invalid sunset_date", raw_sunset)
            )
            continue
        if sunset < today:
            errors.append(
                Finding("shim-expiry", "error", subject, "shim sunset has expired", raw_sunset)
            )
        path_fields = ["target_path"]
        if str(shim.get("type", "")) in {"python_reexport", "wrapper_only"}:
            path_fields.append("source_path")
        for field in path_fields:
            value = str(shim.get(field, ""))
            if value and not _path_pattern_exists(repo_root, value):
                errors.append(
                    Finding("shim-expiry", "error", subject, f"{field} path is missing", value)
                )
    return errors


def _load_public_surface_packages(repo_root: Path) -> dict[str, set[str]]:
    data = _read_toml(repo_root / "architecture" / "public_surface" / "contract.toml")
    packages: dict[str, set[str]] = {}
    for item in data.get("package", []):
        module = str(item.get("module", "")).strip()
        if not module:
            continue
        entrypoints = {module}
        entrypoints.update(str(entry) for entry in item.get("supported_entrypoints", []))
        packages[module] = entrypoints
    return packages


def _package_for_module(module: str, package_modules: list[str]) -> str | None:
    for package_module in package_modules:
        if module == package_module or module.startswith(f"{package_module}."):
            return package_module
    if module.startswith("polisyos."):
        parts = module.split(".")
        if len(parts) >= 2:
            return ".".join(parts[:2])
    return None


def _is_public_target(
    target_module: str,
    target_package: str,
    public_packages: dict[str, set[str]],
) -> bool:
    return target_module in public_packages.get(target_package, {target_package})


def _load_deep_import_baseline(repo_root: Path) -> dict[str, dict[str, str]]:
    path = repo_root / "architecture" / "baselines" / "imports" / "deep_import.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    baseline: dict[str, dict[str, str]] = {}
    for item in payload.get("edges", []):
        source_module = str(item.get("source_module", ""))
        target_module = str(item.get("target_module", ""))
        if not source_module or not target_module:
            continue
        baseline[f"{source_module}->{target_module}"] = {
            "source_module": source_module,
            "source_file": str(item.get("source_file", "")),
            "target_module": target_module,
        }
    return baseline


def _read_import_exceptions(repo_root: Path) -> list[lint_imports.ImportException]:
    try:
        return lint_imports.read_exceptions(
            repo_root / "architecture" / "imports" / "exceptions.toml"
        )
    except ValueError:
        return []


def _validate_import_exception_metadata(repo_root: Path) -> list[Finding]:
    errors: list[Finding] = []
    relative_path = "architecture/imports/exceptions.toml"
    path = repo_root / relative_path
    if not path.exists():
        return [Finding("import-exceptions", "error", relative_path, "exception file is missing")]
    try:
        exceptions = lint_imports.read_exceptions(path)
    except ValueError as exc:
        return [
            Finding(
                "import-exceptions",
                "error",
                relative_path,
                "invalid import exception metadata",
                str(exc),
            )
        ]

    today = dt.date.today()
    max_expiry = today + dt.timedelta(days=90)
    for exception in exceptions:
        if exception.expires < today:
            errors.append(
                Finding(
                    "import-exceptions",
                    "error",
                    exception.exception_id,
                    "import exception is expired",
                    exception.expires.isoformat(),
                )
            )
        if exception.expires > max_expiry:
            errors.append(
                Finding(
                    "import-exceptions",
                    "error",
                    exception.exception_id,
                    "import exception exceeds the 90-day expiry window",
                    exception.expires.isoformat(),
                )
            )

    guardrail_path = repo_root / "architecture" / "exceptions" / "guardrails.toml"
    if not guardrail_path.exists():
        return errors
    for exception in _read_toml(guardrail_path).get("exception", []):
        if str(exception.get("check", "")) != "deep_import":
            continue
        subject = str(exception.get("id", "deep_import"))
        for field in ("id", "owner", "reason", "expires"):
            if not str(exception.get(field, "")).strip():
                errors.append(Finding("import-exceptions", "error", subject, f"missing `{field}`"))
        try:
            expires = dt.date.fromisoformat(str(exception.get("expires", "")))
        except ValueError:
            errors.append(
                Finding(
                    "import-exceptions",
                    "error",
                    subject,
                    "deep-import exception has invalid expires date",
                    str(exception.get("expires", "")),
                )
            )
            continue
        if expires < today:
            errors.append(
                Finding(
                    "import-exceptions",
                    "error",
                    subject,
                    "deep-import exception is expired",
                    expires.isoformat(),
                )
            )
    return errors


def _registered_import_exception_id(
    *,
    repo_root: Path,
    ref: lint_imports.ImportRef,
    exceptions: list[lint_imports.ImportException],
    target_root: str | None,
) -> str:
    rel_path = lint_imports.format_path(repo_root, ref.source_file)
    today = dt.date.today()
    for exception in exceptions:
        if exception.expires < today:
            continue
        if not lint_imports.exception_matches(
            exception,
            ref,
            rel_path=rel_path,
            target_module=ref.target_module,
            target_root=target_root,
            external_top=None,
        ):
            continue
        if not exception.owner or not exception.reason or not exception.expires:
            continue
        return exception.exception_id

    guardrail_path = repo_root / "architecture" / "exceptions" / "guardrails.toml"
    if not guardrail_path.exists():
        return ""
    data = _read_toml(guardrail_path)
    for exception in data.get("exception", []):
        if str(exception.get("check", "")) != "deep_import":
            continue
        try:
            expires = dt.date.fromisoformat(str(exception.get("expires", "")))
        except ValueError:
            continue
        if expires < today:
            continue
        if not all(str(exception.get(field, "")).strip() for field in ("owner", "reason")):
            continue
        source_matches = fnmatch.fnmatch(
            ref.source_module,
            str(exception.get("source_module_glob", "*")),
        )
        target_matches = fnmatch.fnmatch(
            ref.target_module,
            str(exception.get("target_module_glob", "*")),
        )
        if source_matches and target_matches:
            return str(exception.get("id", ""))
    return ""


def _import_boundary_rule() -> str:
    return "first-party cross-package imports target supported public entrypoints unless registered"


def _collect_hidden_import_edges(repo_root: Path) -> dict[str, dict[str, Any]]:
    public_packages = _load_public_surface_packages(repo_root)
    package_modules = sorted(public_packages, key=len, reverse=True)
    policy_path = repo_root / "architecture" / "imports" / "policy.toml"
    config = lint_imports.read_policy(policy_path)
    imports, _, _, _, _ = lint_imports.parse_imports(config, cache_root=None)
    exceptions = _read_import_exceptions(repo_root)
    edges: dict[str, dict[str, Any]] = {}

    for ref in imports:
        if not lint_imports.is_internal_module(ref.target_module, config.internal_prefix):
            continue
        source_package = _package_for_module(ref.source_module, package_modules)
        target_package = _package_for_module(ref.target_module, package_modules)
        if source_package is None or target_package is None or source_package == target_package:
            continue
        if _is_public_target(ref.target_module, target_package, public_packages):
            continue

        target_root = lint_imports.root_for_module(ref.target_module, config.internal_prefix)
        key = f"{ref.source_module}->{ref.target_module}"
        edges.setdefault(
            key,
            {
                "key": key,
                "source_module": ref.source_module,
                "source_package": source_package,
                "source_file": lint_imports.format_path(repo_root, ref.source_file),
                "lineno": ref.lineno,
                "target_module": ref.target_module,
                "target_package": target_package,
                "target_root": target_root or "",
                "registered_exception": _registered_import_exception_id(
                    repo_root=repo_root,
                    ref=ref,
                    exceptions=exceptions,
                    target_root=target_root,
                ),
            },
        )
    return edges


def _boundary_packages(repo_root: Path) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("module", "")).strip(): item
        for item in _read_toml(repo_root / "architecture" / "packages" / "boundaries.toml").get(
            "package", []
        )
        if str(item.get("module", "")).strip()
    }


def _matches_dependency(module: str, dependency: str) -> bool:
    dependency = dependency.strip()
    if not dependency:
        return False
    if dependency.endswith(".*"):
        prefix = dependency.removesuffix(".*")
        return module == prefix or module.startswith(f"{prefix}.")
    return module == dependency or module.startswith(f"{dependency}.")


def _collect_forbidden_package_edges(repo_root: Path) -> dict[str, dict[str, Any]]:
    public_packages = _load_public_surface_packages(repo_root)
    boundaries = _boundary_packages(repo_root)
    package_modules = sorted(set(public_packages) | set(boundaries), key=len, reverse=True)
    config = lint_imports.read_policy(repo_root / "architecture" / "imports" / "policy.toml")
    imports, _, _, _, _ = lint_imports.parse_imports(config, cache_root=None)
    exceptions = _read_import_exceptions(repo_root)
    edges: dict[str, dict[str, Any]] = {}

    for ref in imports:
        if not lint_imports.is_internal_module(ref.target_module, config.internal_prefix):
            continue
        source_package = _package_for_module(ref.source_module, package_modules)
        target_package = _package_for_module(ref.target_module, package_modules)
        if source_package is None or target_package is None or source_package == target_package:
            continue
        source_boundary = boundaries.get(source_package, {})
        forbidden = [
            str(item)
            for item in source_boundary.get("forbidden_dependencies", [])
            if str(item).startswith("polisyos.")
        ]
        matched_dependency = next(
            (
                dependency
                for dependency in forbidden
                if _matches_dependency(ref.target_module, dependency)
            ),
            "",
        )
        if not matched_dependency:
            continue
        target_root = lint_imports.root_for_module(ref.target_module, config.internal_prefix)
        key = f"{ref.source_module}->{ref.target_module}"
        edges.setdefault(
            key,
            {
                "key": key,
                "source_module": ref.source_module,
                "source_package": source_package,
                "source_file": lint_imports.format_path(repo_root, ref.source_file),
                "lineno": ref.lineno,
                "target_module": ref.target_module,
                "target_package": target_package,
                "forbidden_dependency": matched_dependency,
                "registered_exception": _registered_import_exception_id(
                    repo_root=repo_root,
                    ref=ref,
                    exceptions=exceptions,
                    target_root=target_root,
                ),
            },
        )
    return edges


def _package_pair(edge: dict[str, str], package_modules: list[str]) -> tuple[str, str]:
    source_package = _package_for_module(str(edge.get("source_module", "")), package_modules) or ""
    target_package = _package_for_module(str(edge.get("target_module", "")), package_modules) or ""
    return source_package, target_package


def _package_edge_sets(
    edges: dict[str, dict[str, Any]],
    package_modules: list[str],
) -> dict[tuple[str, str], set[str]]:
    grouped: dict[tuple[str, str], set[str]] = defaultdict(set)
    for key, edge in edges.items():
        pair = _package_pair(edge, package_modules)
        if not pair[0] or not pair[1] or pair[0] == pair[1]:
            continue
        grouped[pair].add(key)
    return grouped


def _package_boundary_forbidden_summary(repo_root: Path) -> dict[str, Any]:
    public_packages = _load_public_surface_packages(repo_root)
    boundaries = _boundary_packages(repo_root)
    package_modules = sorted(set(public_packages) | set(boundaries), key=len, reverse=True)
    edges = _collect_forbidden_package_edges(repo_root)
    grouped = _package_edge_sets(edges, package_modules)
    rows: list[dict[str, Any]] = []
    registered = 0
    for source_package, target_package in sorted(grouped):
        keys = sorted(grouped[(source_package, target_package)])
        registered_keys = [
            key for key in keys if str(edges.get(key, {}).get("registered_exception", ""))
        ]
        registered += len(registered_keys)
        rows.append(
            {
                "source_package": source_package,
                "target_package": target_package,
                "current_forbidden_edges": len(keys),
                "registered_forbidden_edges": len(registered_keys),
                "unregistered_forbidden_edges": len(keys) - len(registered_keys),
                "edge_keys": keys[:25],
            }
        )
    unregistered_keys = sorted(
        key for key, edge in edges.items() if not str(edge.get("registered_exception", ""))
    )
    return {
        "mode": "report_only",
        "rule": "package_boundaries.forbidden_dependencies cannot grow without exception",
        "current_forbidden_edge_count": len(edges),
        "registered_forbidden_edge_count": registered,
        "unregistered_forbidden_edge_count": len(unregistered_keys),
        "unregistered_forbidden_edge_keys": unregistered_keys[:100],
        "package_level_forbidden_edges": rows,
    }


def _build_import_boundary_summary(repo_root: Path) -> dict[str, Any]:
    public_packages = _load_public_surface_packages(repo_root)
    package_modules = sorted(public_packages, key=len, reverse=True)
    current_edges = _collect_hidden_import_edges(repo_root)
    baseline_edges = _load_deep_import_baseline(repo_root)
    current_by_pair = _package_edge_sets(current_edges, package_modules)
    baseline_by_pair = _package_edge_sets(baseline_edges, package_modules)
    all_pairs = sorted(set(current_by_pair) | set(baseline_by_pair))

    package_level_deltas: list[dict[str, Any]] = []
    total_added = 0
    total_removed = 0
    total_registered_added = 0
    for source_package, target_package in all_pairs:
        current = current_by_pair.get((source_package, target_package), set())
        baseline = baseline_by_pair.get((source_package, target_package), set())
        added = sorted(current - baseline)
        removed = sorted(baseline - current)
        registered_added = [
            key for key in added if str(current_edges.get(key, {}).get("registered_exception", ""))
        ]
        total_added += len(added)
        total_removed += len(removed)
        total_registered_added += len(registered_added)
        package_level_deltas.append(
            {
                "source_package": source_package,
                "target_package": target_package,
                "baseline_hidden_edges": len(baseline),
                "current_hidden_edges": len(current),
                "delta_hidden_edges": len(current) - len(baseline),
                "added_hidden_edges": len(added),
                "removed_hidden_edges": len(removed),
                "registered_added_hidden_edges": len(registered_added),
                "unregistered_added_hidden_edges": len(added) - len(registered_added),
                "added_edge_keys": added[:25],
                "removed_edge_keys": removed[:25],
            }
        )

    unregistered_added_edges = sorted(
        key
        for key in (set(current_edges) - set(baseline_edges))
        if not str(current_edges[key].get("registered_exception", ""))
    )
    registered_added_edges = sorted(
        key
        for key in (set(current_edges) - set(baseline_edges))
        if str(current_edges[key].get("registered_exception", ""))
    )
    return {
        "mode": "report_only",
        "baseline": "architecture/baselines/imports/deep_import.json",
        "rule": _import_boundary_rule(),
        "current_hidden_edge_count": len(current_edges),
        "baseline_hidden_edge_count": len(baseline_edges),
        "added_hidden_edge_count": total_added,
        "removed_hidden_edge_count": total_removed,
        "registered_added_hidden_edge_count": total_registered_added,
        "unregistered_added_hidden_edge_count": len(unregistered_added_edges),
        "registered_added_edge_keys": registered_added_edges[:100],
        "unregistered_added_edge_keys": unregistered_added_edges[:100],
        "package_level_deltas": package_level_deltas,
        "public_surface_import_contract": _public_surface_import_contract_summary(repo_root),
    }


def _import_boundary_findings(summary: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for row in summary["package_level_deltas"]:
        if (
            row["delta_hidden_edges"] == 0
            and row["added_hidden_edges"] == 0
            and row["removed_hidden_edges"] == 0
        ):
            continue
        findings.append(
            Finding(
                "import-boundary",
                "report_only",
                f"{row['source_package']} -> {row['target_package']}",
                "package-level hidden import delta",
                (
                    f"baseline={row['baseline_hidden_edges']} "
                    f"current={row['current_hidden_edges']} "
                    f"delta={row['delta_hidden_edges']:+d} "
                    f"added={row['added_hidden_edges']} "
                    f"registered_added={row['registered_added_hidden_edges']} "
                    f"unregistered_added={row['unregistered_added_hidden_edges']}"
                ),
            )
        )
    contract = summary["public_surface_import_contract"]
    if contract["drift_count"]:
        findings.append(
            Finding(
                "public-surface-import-contract",
                "report_only",
                "architecture/packages/boundaries.toml",
                "public surface and import contracts drift",
                f"drift_count={contract['drift_count']}",
            )
        )
    return findings


def _package_boundary_findings(summary: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for row in summary["package_level_forbidden_edges"]:
        findings.append(
            Finding(
                "package-boundary",
                "report_only",
                f"{row['source_package']} -> {row['target_package']}",
                "package-boundary forbidden edge inventory",
                (
                    f"current={row['current_forbidden_edges']} "
                    f"registered={row['registered_forbidden_edges']} "
                    f"unregistered={row['unregistered_forbidden_edges']}"
                ),
            )
        )
    return findings


def _import_boundary_delta_errors(summary: dict[str, Any]) -> list[Finding]:
    errors: list[Finding] = []
    for row in summary["package_level_deltas"]:
        if row["unregistered_added_hidden_edges"] <= 0:
            continue
        errors.append(
            Finding(
                "import-boundary",
                "error",
                f"{row['source_package']} -> {row['target_package']}",
                "unregistered hidden coupling increase",
                (
                    f"unregistered_added={row['unregistered_added_hidden_edges']} "
                    f"examples={row['added_edge_keys'][:5]!r}"
                ),
            )
        )
    return errors


def _package_boundary_forbidden_errors(summary: dict[str, Any]) -> list[Finding]:
    errors: list[Finding] = []
    for row in summary["package_level_forbidden_edges"]:
        if row["unregistered_forbidden_edges"] <= 0:
            continue
        errors.append(
            Finding(
                "package-boundary",
                "error",
                f"{row['source_package']} -> {row['target_package']}",
                "unregistered forbidden package-boundary edge",
                (
                    f"unregistered={row['unregistered_forbidden_edges']} "
                    f"examples={row['edge_keys'][:5]!r}"
                ),
            )
        )
    return errors


def _public_surface_import_contract_summary(repo_root: Path) -> dict[str, Any]:
    import_contract_errors = _validate_public_surface_import_contracts(repo_root)
    inventory_errors = _validate_public_surface_inventory_contract(repo_root)
    return {
        "drift_count": len(import_contract_errors) + len(inventory_errors),
        "import_contract_drift_count": len(import_contract_errors),
        "inventory_drift_count": len(inventory_errors),
        "source_contracts": [
            "architecture/public_surface/contract.toml",
            "architecture/public_surface/inventory.json",
            "architecture/packages/boundaries.toml",
            "architecture/imports/contracts.toml",
        ],
    }


def _validate_public_surface_import_contracts(repo_root: Path) -> list[Finding]:
    errors: list[Finding] = []
    public_packages = _load_public_surface_packages(repo_root)
    package_modules = sorted(public_packages, key=len, reverse=True)
    boundaries = _read_toml(repo_root / "architecture" / "packages" / "boundaries.toml")
    for package in boundaries.get("package", []):
        subject = str(package.get("module", ""))
        entrypoints = public_packages.get(subject, {subject})
        public_facade = str(package.get("public_facade", ""))
        if public_facade and public_facade not in entrypoints:
            errors.append(
                Finding(
                    "public-surface-import-contract",
                    "error",
                    subject,
                    "package_boundaries.public_facade is not a supported public entrypoint",
                    public_facade,
                )
            )
        for field in ("allowed_dependencies", "runtime_allowed_submodules"):
            for dependency in package.get(field, []):
                dependency = str(dependency)
                if dependency == "public_facades_only" or not dependency.startswith("polisyos."):
                    continue
                target_package = _package_for_module(dependency, package_modules)
                if target_package is None:
                    continue
                if dependency not in public_packages.get(target_package, {target_package}):
                    errors.append(
                        Finding(
                            "public-surface-import-contract",
                            "error",
                            subject,
                            (
                                f"package_boundaries.{field} dependency is not a "
                                "supported public entrypoint"
                            ),
                            dependency,
                        )
                    )

    import_contracts = _read_toml(repo_root / "architecture" / "imports" / "contracts.toml")
    for contract in import_contracts.get("importlinter", {}).get("contracts", []):
        for ignored in contract.get("ignore_imports", []):
            ignored = str(ignored)
            if not ignored.startswith("polisyos."):
                continue
            normalized = ignored.removesuffix(".*")
            target_package = _package_for_module(normalized, package_modules)
            if target_package is None:
                continue
            if normalized not in public_packages.get(target_package, {target_package}):
                errors.append(
                    Finding(
                        "public-surface-import-contract",
                        "error",
                        str(contract.get("name", "importlinter contract")),
                        "import_contracts.ignore_imports path is not a supported public entrypoint",
                        ignored,
                    )
                )
    return errors


def _validate_public_surface_inventory_contract(repo_root: Path) -> list[Finding]:
    manifest_path = repo_root / "architecture" / "public_surface" / "contract.toml"
    inventory_path = repo_root / "architecture" / "public_surface" / "inventory.json"
    relative_path = "architecture/public_surface/inventory.json"
    if not inventory_path.exists():
        return [
            Finding(
                "public-surface-inventory",
                "error",
                relative_path,
                "public-surface inventory is missing",
            )
        ]
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [
            Finding(
                "public-surface-inventory",
                "error",
                relative_path,
                "public-surface inventory is not valid JSON",
                str(exc),
            )
        ]

    manifest_packages = {
        str(item.get("module", "")): item
        for item in _read_toml(manifest_path).get("package", [])
        if str(item.get("module", ""))
    }
    inventory_packages = {
        str(item.get("module", "")): item
        for item in inventory.get("packages", [])
        if str(item.get("module", ""))
    }
    errors: list[Finding] = []
    missing = sorted(set(manifest_packages) - set(inventory_packages))
    extra = sorted(set(inventory_packages) - set(manifest_packages))
    for module in missing:
        errors.append(
            Finding(
                "public-surface-inventory",
                "error",
                module,
                "manifest package is missing from public-surface inventory",
            )
        )
    for module in extra:
        errors.append(
            Finding(
                "public-surface-inventory",
                "error",
                module,
                "public-surface inventory package is not in manifest",
            )
        )
    field_pairs = (
        ("classification", "classification"),
        ("facade_mode", "facade_mode_expected"),
        ("owner", "owner"),
        ("readme", "readme"),
        ("reference_doc", "reference_doc"),
        ("major_subsystem", "major_subsystem"),
    )
    for module in sorted(set(manifest_packages) & set(inventory_packages)):
        manifest = manifest_packages[module]
        observed = inventory_packages[module]
        for manifest_field, inventory_field in field_pairs:
            if manifest.get(manifest_field) != observed.get(inventory_field):
                errors.append(
                    Finding(
                        "public-surface-inventory",
                        "error",
                        module,
                        f"{inventory_field} drift",
                        (
                            f"manifest={manifest.get(manifest_field)!r} "
                            f"inventory={observed.get(inventory_field)!r}"
                        ),
                    )
                )
        manifest_entries = [str(item) for item in manifest.get("supported_entrypoints", [])]
        inventory_entries = [str(item) for item in observed.get("supported_entrypoints", [])]
        if manifest_entries != inventory_entries:
            errors.append(
                Finding(
                    "public-surface-inventory",
                    "error",
                    module,
                    "supported_entrypoints drift",
                    f"manifest={manifest_entries!r} inventory={inventory_entries!r}",
                )
            )
    return errors


def _shim_debt_summary(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "architecture" / "shims.toml"
    if not path.exists():
        return {
            "shim_count": 0,
            "python_reexport_count": 0,
            "expired_count": 0,
            "due_within_30_days_count": 0,
            "by_type": {},
            "by_source_package": {},
        }
    today = dt.date.today()
    due = today + dt.timedelta(days=30)
    shims = _read_toml(path).get("shim", [])
    by_type: dict[str, int] = defaultdict(int)
    by_source_package: dict[str, int] = defaultdict(int)
    expired: list[str] = []
    due_soon: list[str] = []
    for shim in shims:
        shim_type = str(shim.get("type", ""))
        by_type[shim_type] += 1
        source_fqn = str(shim.get("source_fqn", ""))
        source_path = str(shim.get("source_path", ""))
        source_package = source_fqn.split(".")[1] if source_fqn.startswith("polisyos.") else ""
        if not source_package and source_path.startswith("src/polisyos/"):
            parts = Path(source_path).parts
            if len(parts) >= 3:
                source_package = parts[2]
        if source_package:
            by_source_package[source_package] += 1
        try:
            sunset = dt.date.fromisoformat(str(shim.get("sunset_date", "")))
        except ValueError:
            continue
        shim_id = str(shim.get("id", "unknown"))
        if sunset < today:
            expired.append(shim_id)
        elif sunset <= due:
            due_soon.append(shim_id)
    return {
        "shim_count": len(shims),
        "python_reexport_count": by_type.get("python_reexport", 0),
        "expired_count": len(expired),
        "expired_ids": expired,
        "due_within_30_days_count": len(due_soon),
        "due_within_30_days_ids": due_soon,
        "by_type": dict(sorted(by_type.items())),
        "by_source_package": dict(sorted(by_source_package.items())),
    }


def _validate_static_analysis_overrides(repo_root: Path) -> list[Finding]:
    from tools.ops_runners.reports import dead_overrides

    findings: list[Finding] = []
    data = _read_toml(repo_root / "architecture" / "tooling" / "static_analysis_overrides.toml")
    header = data.get("static_analysis_overrides", {})
    if header.get("status") != "report_only":
        findings.append(
            Finding(
                "static-analysis-overrides",
                "report_only",
                "architecture/tooling/static_analysis_overrides.toml",
                "status must remain report_only in Phase 1.3",
                str(header.get("status")),
            )
        )
    baselines = data.get("baselines", {})
    split = data.get("tool_config_split", {})
    if split:
        for field in (
            "manifest",
            "mypy_config",
            "ruff_config",
            "mkdocs_config",
            "root_mypy_config",
            "root_ruff_config",
            "root_mkdocs_config",
        ):
            value = str(split.get(field, "")).strip()
            if not value:
                findings.append(
                    Finding(
                        "static-analysis-overrides",
                        "report_only",
                        field,
                        "tool config split field is missing",
                    )
                )
            elif not (repo_root / value).exists():
                findings.append(
                    Finding(
                        "static-analysis-overrides",
                        "report_only",
                        value,
                        "tool config split path is missing",
                    )
                )
        if split.get("check_command") != "uv run polisyos-tools workspace tool-configs --check":
            findings.append(
                Finding(
                    "static-analysis-overrides",
                    "report_only",
                    "tool_config_split.check_command",
                    "tool config split check command is not canonical",
                    str(split.get("check_command", "")),
                )
            )
    counts = _inline_override_counts(repo_root)
    for key, observed in counts.items():
        baseline = int(baselines.get(key, 0))
        if observed > baseline:
            findings.append(
                Finding(
                    "static-analysis-overrides",
                    "report_only",
                    key,
                    "inline override count exceeds report-only baseline",
                    f"observed={observed} baseline={baseline}",
                )
            )
        elif observed < baseline:
            findings.append(
                Finding(
                    "static-analysis-overrides",
                    "report_only",
                    key,
                    "inline override count is below baseline and can be ratcheted",
                    f"observed={observed} baseline={baseline}",
                )
            )
    for scope in data.get("override_scope", []):
        if scope.get("mode") != "report_only":
            findings.append(
                Finding(
                    "static-analysis-overrides",
                    "report_only",
                    str(scope.get("id", "unknown")),
                    "override scope mode must be report_only",
                    str(scope.get("mode")),
                )
            )
        config = str(scope.get("config", ""))
        if config and not (repo_root / config).exists():
            findings.append(
                Finding(
                    "static-analysis-overrides",
                    "report_only",
                    str(scope.get("id", "unknown")),
                    "override config is missing",
                    config,
                )
            )
    dead_override_report = dead_overrides.build_report(repo_root)
    for item in dead_override_report["findings"]:
        findings.append(
            Finding(
                "static-analysis-overrides",
                "report_only",
                str(item.get("subject", "unknown")),
                str(item.get("message", "")),
                (
                    f"tool={item.get('tool')} config={item.get('config')}:"
                    f"{item.get('line')} check={item.get('check')} "
                    f"{item.get('detail', '')}"
                ),
            )
        )
    return findings


def _inline_override_counts(repo_root: Path) -> dict[str, int]:
    type_ignore = re.compile(r"#\s*type:\s*ignore")
    noqa = re.compile(r"#\s*noqa(?::|\b)")
    counts = {
        "inline_type_ignore_count": 0,
        "inline_noqa_count": 0,
    }
    for root_name in ("src", "tests", "tools"):
        root = repo_root / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            counts["inline_type_ignore_count"] += len(type_ignore.findall(text))
            counts["inline_noqa_count"] += len(noqa.findall(text))
    return counts


def _validate_report_only_gates(repo_root: Path) -> list[Finding]:
    errors: list[Finding] = []
    path = repo_root / "architecture" / "gates" / "report_only.toml"
    if not path.exists():
        return [
            Finding(
                "report-only-gates",
                "error",
                "architecture/gates/report_only.toml",
                "report-only gate registry is missing",
            )
        ]
    data = _read_toml(path)
    header = data.get("report_only_gates", {})
    if header.get("status") != "report_only":
        errors.append(
            Finding(
                "report-only-gates",
                "error",
                "architecture/gates/report_only.toml",
                "registry status must be report_only",
                str(header.get("status")),
            )
        )
    for gate in data.get("gate", []):
        gate_id = str(gate.get("id", "unknown"))
        if gate.get("mode") != "report_only":
            errors.append(
                Finding(
                    "report-only-gates",
                    "error",
                    gate_id,
                    "gate mode must be report_only",
                    str(gate.get("mode")),
                )
            )
        for field in ("owner", "command", "evidence"):
            if not str(gate.get(field, "")).strip():
                errors.append(Finding("report-only-gates", "error", gate_id, f"missing `{field}`"))
        evidence = str(gate.get("evidence", ""))
        if evidence and not _path_pattern_exists(repo_root, evidence):
            errors.append(
                Finding(
                    "report-only-gates",
                    "error",
                    gate_id,
                    "evidence path is missing",
                    evidence,
                )
            )
        for source in gate.get("source_contracts", []):
            if not _path_pattern_exists(repo_root, str(source)):
                errors.append(
                    Finding(
                        "report-only-gates",
                        "error",
                        gate_id,
                        "source contract path is missing",
                        str(source),
                    )
                )
        raw_date = str(gate.get("target_fail_closed_not_before", ""))
        if raw_date and not _valid_future_or_today(raw_date):
            errors.append(
                Finding(
                    "report-only-gates",
                    "error",
                    gate_id,
                    "target_fail_closed_not_before must be today or future",
                    raw_date,
                )
            )
    return errors


def _path_pattern_exists(repo_root: Path, pattern: str) -> bool:
    if any(char in pattern for char in "*?["):
        return bool(list(repo_root.glob(pattern)))
    path = Path(pattern)
    if path.is_absolute():
        return path.exists()
    return (repo_root / path).exists()


def _summary(
    repo_root: Path,
    *,
    family_admission: _PackageMirrorFamilyAdmission | None = None,
) -> dict[str, Any]:
    from tools.ops_runners.reports import dead_overrides

    packages = _load_package_contracts(repo_root, family_admission=family_admission)
    gates = _read_toml(repo_root / "architecture" / "gates" / "report_only.toml").get("gate", [])
    module_budget = _read_toml(repo_root / "architecture" / "module_size_budget.toml")
    return {
        "package_contract_count": len(packages),
        "package_contracts": [
            _package_contract_summary_id(path, data, repo_root) for path, data in packages
        ],
        "report_only_gate_count": len(gates),
        "module_size_budget_count": len(module_budget.get("budget", [])),
        "static_analysis_counts": _inline_override_counts(repo_root),
        "dead_override_report": dead_overrides.build_report(repo_root)["summary"],
    }


def _package_contract_summary_id(path: Path, data: dict[str, Any], repo_root: Path) -> str:
    package = data.get("package", {})
    if isinstance(package, dict):
        return str(package.get("id", _relative(path, repo_root)))
    if isinstance(package, list) and package and isinstance(package[0], dict):
        return str(package[0].get("id", _relative(path, repo_root)))
    return _relative(path, repo_root)


def _phase6_1_summary() -> dict[str, Any]:
    return {
        "status": "report_only_conversion",
        "parallel_safety": (
            "Fail-closed package import deltas are opt-in until active Fabric, IR, "
            "Foundry, and Scientist package move branches finish merging."
        ),
        "converted_gates": [
            "root-facade/package-layout",
            "package-boundary",
            "public-surface",
            "deep-import",
            "dynamic-import",
            "import-cycle",
            "name-collision",
            "shim-expiry",
        ],
        "fail_closed_switch": "--enforce-import-boundary-deltas",
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build report-only evidence for Architecture Phase 1.3 contracts."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--report", choices=sorted(REPORTS), default="all")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument(
        "--fail-on-contract-errors",
        action="store_true",
        help="Return non-zero when the report-only contracts are malformed.",
    )
    parser.add_argument(
        "--fail-on-package-mirror-errors",
        action="store_true",
        help=(
            "Return non-zero when the registered package mirror family fails source reconciliation."
        ),
    )
    parser.add_argument(
        "--enforce-import-boundary-deltas",
        action="store_true",
        help=(
            "Promote unregistered package-level hidden-import growth from report-only "
            "findings to contract errors."
        ),
    )
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    payload = build_report(
        repo_root,
        report=args.report,
        enforce_import_boundary_deltas=args.enforce_import_boundary_deltas,
    )
    if args.json_output is not None:
        output = (
            args.json_output if args.json_output.is_absolute() else repo_root / args.json_output
        )
        write_scoped_report_text(
            output,
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            atomic=False,
        )
    else:
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    if args.fail_on_contract_errors and payload["contract_error_count"]:
        return 1
    if args.fail_on_package_mirror_errors:
        family_check = (
            payload["summary"].get("generated_family_checks", {}).get(PACKAGE_MIRROR_FAMILY_ID)
        )
        if family_check is None or family_check.get("error_count", 1):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli(sys.argv[1:]))
