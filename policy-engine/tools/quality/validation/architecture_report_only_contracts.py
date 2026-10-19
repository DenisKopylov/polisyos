#!/usr/bin/env python3
"""Build report-only evidence for Architecture Phase 1.3 contracts."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tools.lib.fs import AdmittedPathError as AdmittedPathError
from tools.lib.fs import resolve_admitted_path, write_scoped_report_text
from tools.lib.imports import repo_root_from
from tools.quality.validation.architecture_package_contracts import (
    _MISSING_VALUE,
    PACKAGE_MIRROR_FAMILY_ID,
    ArchitectureReportServices,
    _MirrorFieldDomain,
    _PackageMirrorFamilyAdmission,
)
from tools.quality.validation.architecture_package_contracts import (
    PACKAGE_MIRROR_CHECK_COMMAND as PACKAGE_MIRROR_CHECK_COMMAND,
)
from tools.quality.validation.architecture_package_contracts import (
    PACKAGE_MIRROR_OUTPUTS as PACKAGE_MIRROR_OUTPUTS,
)
from tools.quality.validation.architecture_package_contracts import (
    PACKAGE_MIRROR_SOURCE_OF_TRUTH as PACKAGE_MIRROR_SOURCE_OF_TRUTH,
)
from tools.quality.validation.architecture_package_contracts import (
    REQUIRED_PACKAGE_TABLES as REQUIRED_PACKAGE_TABLES,
)

if TYPE_CHECKING:
    from tools.quality.lint import lint_imports
from tools.quality.validation import (
    architecture_artifact_contracts as _architecture_artifact_contracts,
)
from tools.quality.validation import (
    architecture_directory_contracts as _architecture_directory_contracts,
)
from tools.quality.validation import (
    architecture_import_graph as _architecture_import_graph,
)
from tools.quality.validation import (
    architecture_module_size_contracts as _architecture_module_size_contracts,
)
from tools.quality.validation import (
    architecture_package_contracts as _architecture_package_contracts,
)
from tools.quality.validation import (
    architecture_package_mirror_projection as _architecture_package_mirror_projection,
)
from tools.quality.validation import (
    architecture_report_surface as _architecture_report_surface,
)

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
    report: str = "all",
    enforce_import_boundary_deltas: bool = False,
) -> dict[str, Any]:
    return _architecture_report_surface.build_report(
        repo_root=repo_root,
        report=report,
        enforce_import_boundary_deltas=enforce_import_boundary_deltas,
        _services=_report_services(),
    )


def _read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _dispatch_report_function(name: str, *args: object, **kwargs: object) -> object:
    """Dispatch through the facade so existing private monkeypatch seams remain live."""
    return globals()[name](*args, **kwargs)


def _report_services() -> ArchitectureReportServices:
    """Capture the facade's current readers and path admissions for one owner call."""
    return ArchitectureReportServices(
        finding=Finding,
        read_toml=_read_toml,
        path_pattern_exists=_path_pattern_exists,
        resolve_admitted_path=resolve_admitted_path,
        dispatch=_dispatch_report_function,
        reports=REPORTS,
    )


def _admit_package_mirror_family_registry(
    repo_root: Path,
) -> _PackageMirrorFamilyAdmission:
    return _architecture_package_contracts._admit_package_mirror_family_registry(
        repo_root=repo_root, _services=_report_services()
    )


def _family_registry_findings(
    admission: _PackageMirrorFamilyAdmission, *, check: str
) -> list[Finding]:
    return _architecture_package_contracts._family_registry_findings(
        admission=admission, check=check, _services=_report_services()
    )


def _relative(path: Path, repo_root: Path) -> str:
    return _architecture_package_contracts._relative(
        path=path, repo_root=repo_root, _services=_report_services()
    )


def _package_mirror_family(
    family_admission: _PackageMirrorFamilyAdmission,
) -> dict[str, Any] | None:
    return _architecture_package_contracts._package_mirror_family(
        family_admission=family_admission, _services=_report_services()
    )


def _package_mirror_output_paths(
    family_admission: _PackageMirrorFamilyAdmission,
) -> set[str]:
    return _architecture_package_contracts._package_mirror_output_paths(
        family_admission=family_admission, _services=_report_services()
    )


def _package_contract_paths(
    repo_root: Path,
    *,
    family_admission: _PackageMirrorFamilyAdmission | None = None,
) -> list[Path]:
    return _architecture_package_contracts._package_contract_paths(
        repo_root=repo_root, family_admission=family_admission, _services=_report_services()
    )


def _load_package_contracts(
    repo_root: Path,
    *,
    family_admission: _PackageMirrorFamilyAdmission | None = None,
) -> list[tuple[Path, dict[str, Any]]]:
    return _architecture_package_contracts._load_package_contracts(
        repo_root=repo_root, family_admission=family_admission, _services=_report_services()
    )


def _aggregate_package_modules(repo_root: Path) -> list[str]:
    return _architecture_package_contracts._aggregate_package_modules(
        repo_root=repo_root, _services=_report_services()
    )


def _validate_package_contracts(
    repo_root: Path,
    *,
    family_admission: _PackageMirrorFamilyAdmission | None = None,
) -> list[Finding]:
    return _architecture_package_contracts._validate_package_contracts(
        repo_root=repo_root, family_admission=family_admission, _services=_report_services()
    )


def _validate_package_extension_points(
    repo_root: Path,
    subject: str,
    extension_host: dict[str, Any],
    errors: list[Finding],
) -> None:
    return _architecture_package_contracts._validate_package_extension_points(
        repo_root=repo_root,
        subject=subject,
        extension_host=extension_host,
        errors=errors,
        _services=_report_services(),
    )


def _valid_iso_date(raw: object) -> bool:
    return _architecture_package_contracts._valid_iso_date(raw=raw, _services=_report_services())


def _valid_future_or_today(raw: str) -> bool:
    return _architecture_package_contracts._valid_future_or_today(
        raw=raw, _services=_report_services()
    )


def _validate_package_mirrors(repo_root: Path) -> list[Finding]:
    findings, _ = _validate_package_mirror_projection(repo_root)
    return findings


def _validate_package_mirror_projection(
    repo_root: Path,
    *,
    family_admission: _PackageMirrorFamilyAdmission | None = None,
) -> tuple[list[Finding], dict[str, Any]]:
    return _architecture_package_mirror_projection._validate_package_mirror_projection(
        repo_root=repo_root, family_admission=family_admission, _services=_report_services()
    )


def _mirror_value_type(value: object) -> str:
    return _architecture_package_contracts._mirror_value_type(
        value=value, _services=_report_services()
    )


def _mirror_value_matches_domain(
    value: object,
    domain: _MirrorFieldDomain,
    *,
    optional: bool = False,
) -> bool:
    return _architecture_package_contracts._mirror_value_matches_domain(
        value=value, domain=domain, optional=optional, _services=_report_services()
    )


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
    return _architecture_package_contracts._validate_mirror_value(
        findings=findings,
        subject=subject,
        field=field,
        value=value,
        domain=domain,
        side=side,
        optional=optional,
        _services=_report_services(),
    )


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
    return _architecture_package_contracts._record_malformed_mirror_value(
        findings=findings,
        subject=subject,
        field=field,
        value=value,
        domain=domain,
        side=side,
        optional=optional,
        _services=_report_services(),
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
    return _architecture_package_contracts._compare_typed_value(
        findings=findings,
        subject=subject,
        field=field,
        expected=expected,
        observed=observed,
        domain=domain,
        optional=optional,
        _services=_report_services(),
    )


def _compare_scalar(
    findings: list[Finding],
    subject: str,
    field: str,
    *,
    expected: object,
    observed: object,
) -> None:
    return _architecture_package_contracts._compare_scalar(
        findings=findings,
        subject=subject,
        field=field,
        expected=expected,
        observed=observed,
        _services=_report_services(),
    )


def _compare_boolean(
    findings: list[Finding],
    subject: str,
    field: str,
    *,
    expected: object,
    observed: object,
) -> None:
    return _architecture_package_contracts._compare_boolean(
        findings=findings,
        subject=subject,
        field=field,
        expected=expected,
        observed=observed,
        _services=_report_services(),
    )


def _compare_list(
    findings: list[Finding],
    subject: str,
    field: str,
    *,
    expected: object,
    observed: object,
) -> None:
    return _architecture_package_contracts._compare_list(
        findings=findings,
        subject=subject,
        field=field,
        expected=expected,
        observed=observed,
        _services=_report_services(),
    )


def _compare_optional_scalar(
    findings: list[Finding],
    subject: str,
    field: str,
    *,
    expected: object,
    observed: object,
) -> None:
    return _architecture_package_contracts._compare_optional_scalar(
        findings=findings,
        subject=subject,
        field=field,
        expected=expected,
        observed=observed,
        _services=_report_services(),
    )


def _compare_optional_list(
    findings: list[Finding],
    subject: str,
    field: str,
    *,
    expected: object,
    observed: object,
) -> None:
    return _architecture_package_contracts._compare_optional_list(
        findings=findings,
        subject=subject,
        field=field,
        expected=expected,
        observed=observed,
        _services=_report_services(),
    )


def _validate_module_size_budget(repo_root: Path) -> list[Finding]:
    return _architecture_module_size_contracts._validate_module_size_budget(
        repo_root=repo_root, _services=_report_services()
    )


def _validate_validation_tooling_defaults(header: dict[str, Any]) -> list[Finding]:
    return _architecture_module_size_contracts._validate_validation_tooling_defaults(
        header=header, _services=_report_services()
    )


def _validate_validation_tooling_budget_coverage(
    repo_root: Path,
    *,
    budget_by_path: dict[str, dict[str, Any]],
    validation_header: dict[str, Any],
    validation_scope: list[str],
) -> list[Finding]:
    return _architecture_module_size_contracts._validate_validation_tooling_budget_coverage(
        repo_root=repo_root,
        budget_by_path=budget_by_path,
        validation_header=validation_header,
        validation_scope=validation_scope,
        _services=_report_services(),
    )


def _validate_validation_tooling_budget_entry(
    repo_root: Path,
    budget: dict[str, Any],
    *,
    validation_header: dict[str, Any],
    validation_scope: list[str],
) -> list[Finding]:
    return _architecture_module_size_contracts._validate_validation_tooling_budget_entry(
        repo_root=repo_root,
        budget=budget,
        validation_header=validation_header,
        validation_scope=validation_scope,
        _services=_report_services(),
    )


def _validation_tooling_paths(repo_root: Path, validation_scope: list[str]) -> list[Path]:
    return _architecture_module_size_contracts._validation_tooling_paths(
        repo_root=repo_root, validation_scope=validation_scope, _services=_report_services()
    )


def _matches_any_validation_scope(relative: str, validation_scope: list[str]) -> bool:
    return _architecture_module_size_contracts._matches_any_validation_scope(
        relative=relative, validation_scope=validation_scope, _services=_report_services()
    )


def _matches_validation_scope(relative: str, pattern: str) -> bool:
    return _architecture_module_size_contracts._matches_validation_scope(
        relative=relative, pattern=pattern, _services=_report_services()
    )


def _count_lines(path: Path) -> int:
    return _architecture_module_size_contracts.count_lines(path)


def _validate_generated_artifact_contracts(
    repo_root: Path,
    *,
    family_admission: _PackageMirrorFamilyAdmission | None = None,
) -> list[Finding]:
    return _architecture_artifact_contracts._validate_generated_artifact_contracts(
        repo_root=repo_root, family_admission=family_admission, _services=_report_services()
    )


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
    return _architecture_artifact_contracts._validate_list_contract(
        repo_root=repo_root,
        relative_path=relative_path,
        header=header,
        entries=entries,
        required_fields=required_fields,
        path_fields=path_fields,
        list_path_fields=list_path_fields,
        allowed_header_statuses=allowed_header_statuses,
        allowed_entry_modes=allowed_entry_modes,
        _services=_report_services(),
    )


def _read_declared_active_component_index(
    repo_root: Path,
    relative_path: str,
) -> tuple[dict[str, Any] | None, Finding | None]:
    return _architecture_artifact_contracts._read_declared_active_component_index(
        repo_root=repo_root, relative_path=relative_path, _services=_report_services()
    )


def _validate_legacy_operability_routes(
    repo_root: Path,
) -> tuple[list[Finding], dict[str, Any]]:
    return _architecture_artifact_contracts._validate_legacy_operability_routes(
        repo_root=repo_root, _services=_report_services()
    )


def _validate_extension_points_contract(repo_root: Path) -> list[Finding]:
    return _architecture_artifact_contracts._validate_extension_points_contract(
        repo_root=repo_root, _services=_report_services()
    )


def _validate_directory_contracts(repo_root: Path) -> list[Finding]:
    return _architecture_directory_contracts._validate_directory_contracts(
        repo_root=repo_root, _services=_report_services()
    )


def _validate_directory_hygiene_assets(repo_root: Path) -> list[Finding]:
    return _architecture_directory_contracts._validate_directory_hygiene_assets(
        repo_root=repo_root, _services=_report_services()
    )


def _normalize_contract_root(value: str) -> str:
    return _architecture_directory_contracts._normalize_contract_root(
        value=value, _services=_report_services()
    )


def _validate_root_transition(
    errors: list[Finding],
    *,
    asset_id: str,
    asset: dict[str, Any],
    current_root: str,
    target_roots: object,
) -> None:
    return _architecture_directory_contracts._validate_root_transition(
        errors=errors,
        asset_id=asset_id,
        asset=asset,
        current_root=current_root,
        target_roots=target_roots,
        _services=_report_services(),
    )


def _validate_import_reports(repo_root: Path) -> list[Finding]:
    return _architecture_import_graph._validate_import_reports(
        repo_root=repo_root, _services=_report_services()
    )


def _summarize_dynamic_imports(repo_root: Path) -> list[Finding]:
    return _architecture_import_graph._summarize_dynamic_imports(
        repo_root=repo_root, _services=_report_services()
    )


def _dynamic_imports_summary(repo_root: Path) -> dict[str, Any]:
    return _architecture_import_graph._dynamic_imports_summary(
        repo_root=repo_root, _services=_report_services()
    )


def _validate_dynamic_imports_contract(repo_root: Path) -> list[Finding]:
    return _architecture_import_graph._validate_dynamic_imports_contract(
        repo_root=repo_root, _services=_report_services()
    )


def _validate_dynamic_imports_gate(repo_root: Path) -> list[Finding]:
    return _architecture_import_graph._validate_dynamic_imports_gate(
        repo_root=repo_root, _services=_report_services()
    )


def _validate_import_cycles_gate(repo_root: Path) -> list[Finding]:
    return _architecture_import_graph._validate_import_cycles_gate(
        repo_root=repo_root, _services=_report_services()
    )


def _validate_reexport_shim_shape_gate(repo_root: Path) -> list[Finding]:
    return _architecture_import_graph._validate_reexport_shim_shape_gate(
        repo_root=repo_root, _services=_report_services()
    )


def _preflight_errors(
    *,
    check: str,
    findings: list[Any],
    repo_root: Path,
) -> list[Finding]:
    return _architecture_import_graph._preflight_errors(
        check=check, findings=findings, repo_root=repo_root, _services=_report_services()
    )


def _import_cycles_summary(repo_root: Path) -> dict[str, Any]:
    return _architecture_import_graph._import_cycles_summary(
        repo_root=repo_root, _services=_report_services()
    )


def _structure_gate_summary(repo_root: Path, *, gate: str) -> dict[str, Any]:
    return _architecture_import_graph._structure_gate_summary(
        repo_root=repo_root, gate=gate, _services=_report_services()
    )


def _structure_gate_findings(repo_root: Path, *, gate: str) -> list[Finding]:
    return _architecture_import_graph._structure_gate_findings(
        repo_root=repo_root, gate=gate, _services=_report_services()
    )


def _validate_shim_expiry_contract(repo_root: Path) -> list[Finding]:
    return _architecture_import_graph._validate_shim_expiry_contract(
        repo_root=repo_root, _services=_report_services()
    )


def _load_public_surface_packages(repo_root: Path) -> dict[str, set[str]]:
    return _architecture_import_graph._load_public_surface_packages(
        repo_root=repo_root, _services=_report_services()
    )


def _package_for_module(module: str, package_modules: list[str]) -> str | None:
    return _architecture_import_graph._package_for_module(
        module=module, package_modules=package_modules, _services=_report_services()
    )


def _is_public_target(
    target_module: str,
    target_package: str,
    public_packages: dict[str, set[str]],
) -> bool:
    return _architecture_import_graph._is_public_target(
        target_module=target_module,
        target_package=target_package,
        public_packages=public_packages,
        _services=_report_services(),
    )


def _load_deep_import_baseline(repo_root: Path) -> dict[str, dict[str, str]]:
    return _architecture_import_graph._load_deep_import_baseline(
        repo_root=repo_root, _services=_report_services()
    )


def _read_import_exceptions(repo_root: Path) -> list[lint_imports.ImportException]:
    return _architecture_import_graph._read_import_exceptions(
        repo_root=repo_root, _services=_report_services()
    )


def _validate_import_exception_metadata(repo_root: Path) -> list[Finding]:
    return _architecture_import_graph._validate_import_exception_metadata(
        repo_root=repo_root, _services=_report_services()
    )


def _registered_import_exception_id(
    *,
    repo_root: Path,
    ref: lint_imports.ImportRef,
    exceptions: list[lint_imports.ImportException],
    target_root: str | None,
) -> str:
    return _architecture_import_graph._registered_import_exception_id(
        repo_root=repo_root,
        ref=ref,
        exceptions=exceptions,
        target_root=target_root,
        _services=_report_services(),
    )


def _import_boundary_rule() -> str:
    return _architecture_import_graph._import_boundary_rule(_services=_report_services())


def _collect_hidden_import_edges(repo_root: Path) -> dict[str, dict[str, Any]]:
    return _architecture_import_graph._collect_hidden_import_edges(
        repo_root=repo_root, _services=_report_services()
    )


def _boundary_packages(repo_root: Path) -> dict[str, dict[str, Any]]:
    return _architecture_import_graph._boundary_packages(
        repo_root=repo_root, _services=_report_services()
    )


def _matches_dependency(module: str, dependency: str) -> bool:
    return _architecture_import_graph._matches_dependency(
        module=module, dependency=dependency, _services=_report_services()
    )


def _collect_forbidden_package_edges(repo_root: Path) -> dict[str, dict[str, Any]]:
    return _architecture_import_graph._collect_forbidden_package_edges(
        repo_root=repo_root, _services=_report_services()
    )


def _package_pair(edge: dict[str, str], package_modules: list[str]) -> tuple[str, str]:
    return _architecture_import_graph._package_pair(
        edge=edge, package_modules=package_modules, _services=_report_services()
    )


def _package_edge_sets(
    edges: dict[str, dict[str, Any]],
    package_modules: list[str],
) -> dict[tuple[str, str], set[str]]:
    return _architecture_import_graph._package_edge_sets(
        edges=edges, package_modules=package_modules, _services=_report_services()
    )


def _package_boundary_forbidden_summary(repo_root: Path) -> dict[str, Any]:
    return _architecture_import_graph._package_boundary_forbidden_summary(
        repo_root=repo_root, _services=_report_services()
    )


def _build_import_boundary_summary(repo_root: Path) -> dict[str, Any]:
    return _architecture_import_graph._build_import_boundary_summary(
        repo_root=repo_root, _services=_report_services()
    )


def _import_boundary_findings(summary: dict[str, Any]) -> list[Finding]:
    return _architecture_import_graph._import_boundary_findings(
        summary=summary, _services=_report_services()
    )


def _package_boundary_findings(summary: dict[str, Any]) -> list[Finding]:
    return _architecture_import_graph._package_boundary_findings(
        summary=summary, _services=_report_services()
    )


def _import_boundary_delta_errors(summary: dict[str, Any]) -> list[Finding]:
    return _architecture_import_graph._import_boundary_delta_errors(
        summary=summary, _services=_report_services()
    )


def _package_boundary_forbidden_errors(summary: dict[str, Any]) -> list[Finding]:
    return _architecture_import_graph._package_boundary_forbidden_errors(
        summary=summary, _services=_report_services()
    )


def _public_surface_import_contract_summary(repo_root: Path) -> dict[str, Any]:
    return _architecture_import_graph._public_surface_import_contract_summary(
        repo_root=repo_root, _services=_report_services()
    )


def _validate_public_surface_import_contracts(repo_root: Path) -> list[Finding]:
    return _architecture_report_surface._validate_public_surface_import_contracts(
        repo_root=repo_root, _services=_report_services()
    )


def _validate_public_surface_inventory_contract(repo_root: Path) -> list[Finding]:
    return _architecture_report_surface._validate_public_surface_inventory_contract(
        repo_root=repo_root, _services=_report_services()
    )


def _shim_debt_summary(repo_root: Path) -> dict[str, Any]:
    return _architecture_report_surface._shim_debt_summary(
        repo_root=repo_root, _services=_report_services()
    )


def _validate_static_analysis_overrides(repo_root: Path) -> list[Finding]:
    return _architecture_report_surface._validate_static_analysis_overrides(
        repo_root=repo_root, _services=_report_services()
    )


def _inline_override_counts(repo_root: Path) -> dict[str, int]:
    return _architecture_report_surface._inline_override_counts(
        repo_root=repo_root, _services=_report_services()
    )


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
        raw_date = gate.get("target_fail_closed_not_before", _MISSING_VALUE)
        if not _valid_iso_date(raw_date):
            errors.append(
                Finding(
                    "report-only-gates",
                    "error",
                    gate_id,
                    "target_fail_closed_not_before must be a valid ISO date string",
                    "<missing>" if raw_date is _MISSING_VALUE else str(raw_date),
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
    return _architecture_report_surface._summary(
        repo_root=repo_root, family_admission=family_admission, _services=_report_services()
    )


def _package_contract_summary_id(path: Path, data: dict[str, Any], repo_root: Path) -> str:
    return _architecture_report_surface._package_contract_summary_id(
        path=path, data=data, repo_root=repo_root, _services=_report_services()
    )


def _phase6_1_summary() -> dict[str, Any]:
    return _architecture_report_surface._phase6_1_summary(_services=_report_services())


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
