"""Focused architecture report validator owner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from typing import Any


class FindingLike(Protocol):
    severity: str
    subject: str
    message: str
    detail: str

    def as_dict(self) -> dict[str, str]: ...


@dataclass(frozen=True)
class ArchitectureReportServices:
    """Per-call facade bindings used by architecture report owner modules."""

    finding: Callable[..., FindingLike]
    read_toml: Callable[[Path], dict[str, Any]]
    path_pattern_exists: Callable[[Path, str], bool]
    resolve_admitted_path: Callable[..., Path]
    dispatch: Callable[..., Any]
    reports: set[str]


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
class _PackageMirrorFamilyAdmission:
    rows: tuple[dict[str, Any], ...]
    findings: tuple[FindingLike, ...]


import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


def _admit_package_mirror_family_registry(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> _PackageMirrorFamilyAdmission:
    family_path = "architecture/generated_artifacts.toml"
    family_document = _services.read_toml(repo_root / family_path)
    if type(family_document) is not dict:
        return _PackageMirrorFamilyAdmission(
            (),
            (
                _services.finding(
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
                _services.finding(
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
        findings: list[FindingLike] = []
        for index, family_row in enumerate(family_rows):
            try:
                _validate_generated_artifact_toml_data({"family": [family_row]})
            except GeneratedArtifactManifestSchemaError as error:
                findings.append(
                    _services.finding(
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
    admission: _PackageMirrorFamilyAdmission,
    *,
    check: str,
    _services: ArchitectureReportServices,
) -> list[FindingLike]:
    return [
        _services.finding(check, finding.severity, finding.subject, finding.message, finding.detail)
        for finding in admission.findings
    ]


def _relative(path: Path, repo_root: Path, *, _services: ArchitectureReportServices) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _package_mirror_family(
    family_admission: _PackageMirrorFamilyAdmission,
    *,
    _services: ArchitectureReportServices,
) -> dict[str, Any] | None:
    matches = [
        family_row
        for family_row in family_admission.rows
        if family_row.get("id") == PACKAGE_MIRROR_FAMILY_ID
    ]
    return matches[0] if len(matches) == 1 else None


def _package_mirror_output_paths(
    family_admission: _PackageMirrorFamilyAdmission,
    *,
    _services: ArchitectureReportServices,
) -> set[str]:
    family = _services.dispatch("_package_mirror_family", family_admission)
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
    _services: ArchitectureReportServices,
) -> list[Path]:
    admission = family_admission or _services.dispatch(
        "_admit_package_mirror_family_registry", repo_root
    )
    registered_outputs = _services.dispatch("_package_mirror_output_paths", admission)
    package_root = repo_root / "architecture" / "packages"
    return sorted(
        path
        for path in package_root.glob("*.toml")
        if _services.dispatch("_relative", path, repo_root) not in registered_outputs
    )


def _load_package_contracts(
    repo_root: Path,
    *,
    family_admission: _PackageMirrorFamilyAdmission | None = None,
    _services: ArchitectureReportServices,
) -> list[tuple[Path, dict[str, Any]]]:
    return [
        (path, _services.read_toml(path))
        for path in _services.dispatch(
            "_package_contract_paths", repo_root, family_admission=family_admission
        )
    ]


def _aggregate_package_modules(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> list[str]:
    modules: set[str] = set()
    for relative_path in (
        "architecture/packages/boundaries.toml",
        "architecture/public_surface/contract.toml",
    ):
        data = _services.read_toml(repo_root / relative_path)
        modules.update(
            str(item.get("module", "")).strip()
            for item in data.get("package", [])
            if str(item.get("module", "")).strip()
        )
    test_topology = _services.read_toml(repo_root / "architecture" / "tests" / "topology.toml")
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
    _services: ArchitectureReportServices,
) -> list[FindingLike]:
    errors: list[FindingLike] = []
    expected_modules = set(_services.dispatch("_aggregate_package_modules", repo_root))
    primary_contracts_by_module: dict[str, list[str]] = {}
    for path, data in _services.dispatch(
        "_load_package_contracts", repo_root, family_admission=family_admission
    ):
        subject = _services.dispatch("_relative", path, repo_root)
        missing_tables = [table for table in REQUIRED_PACKAGE_TABLES if table not in data]
        for table in missing_tables:
            errors.append(
                _services.finding("package-contract", "error", subject, f"missing [{table}] table")
            )
        if missing_tables:
            continue
        package = data["package"]
        module = str(package.get("module", ""))
        if not module:
            errors.append(
                _services.finding("package-contract", "error", subject, "missing package.module")
            )
        if package.get("primary_contract") is not True:
            errors.append(
                _services.finding(
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
                _services.finding(
                    "package-contract",
                    "error",
                    subject,
                    "primary package contract is not mirrored by aggregate package TOML",
                    module,
                )
            )
        if package.get("gate_mode") != "report_only":
            errors.append(
                _services.finding(
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
                    _services.finding(
                        "package-contract", "error", subject, f"[{table}] has no owner"
                    )
                )
        for field in ("id", "module", "name", "owner", "contract_status"):
            if package.get(field) in (None, "", []):
                errors.append(
                    _services.finding(
                        "package-contract", "error", subject, f"[package] missing `{field}`"
                    )
                )
        if package.get("legacy_aggregate_mirrors") in (None, "", []):
            errors.append(
                _services.finding(
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
                    _services.finding(
                        "package-contract", "error", subject, f"[layout] missing `{field}`"
                    )
                )
        for field in ("source_root", "readme"):
            value = str(layout.get(field, ""))
            if value and not _services.path_pattern_exists(repo_root, value):
                errors.append(
                    _services.finding(
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
                    _services.finding(
                        "package-contract", "error", subject, f"[boundaries] missing `{field}`"
                    )
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
                    _services.finding(
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
                    _services.finding(
                        "package-contract", "error", subject, f"[tests] missing `{field}`"
                    )
                )
        slo_runbook = data.get("slo_runbook", {})
        for field in ("status", "slo_files", "runbooks", "runbook_expectation"):
            if slo_runbook.get(field) in (None, "", []):
                errors.append(
                    _services.finding(
                        "package-contract",
                        "error",
                        subject,
                        f"[slo_runbook] missing `{field}`",
                    )
                )
        extension_host = data.get("extension_host", {})
        if "status" not in extension_host or "extension_points" not in extension_host:
            errors.append(
                _services.finding(
                    "package-contract",
                    "error",
                    subject,
                    "[extension_host] must declare status and extension_points",
                )
            )
        _services.dispatch(
            "_validate_package_extension_points", repo_root, subject, extension_host, errors
        )
        for aggregate in package.get("legacy_aggregate_mirrors", []):
            if not _services.path_pattern_exists(repo_root, str(aggregate)):
                errors.append(
                    _services.finding(
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
                if raw_date is not None and not _services.dispatch(
                    "_valid_future_or_today", str(raw_date)
                ):
                    errors.append(
                        _services.finding(
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
                _services.finding(
                    "package-contract",
                    "error",
                    module,
                    "aggregate package has no primary package contract file",
                )
            )
        if len(subjects) > 1:
            errors.append(
                _services.finding(
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
    errors: list[FindingLike],
    *,
    _services: ArchitectureReportServices,
) -> None:
    status = str(extension_host.get("status", ""))
    extension_points = extension_host.get("extension_points", [])
    if status == "active" and not extension_points:
        errors.append(
            _services.finding(
                "package-contract",
                "error",
                subject,
                "active extension host must list extension_points",
            )
        )
    declared = {
        str(item.get("name"))
        for item in _services.read_toml(repo_root / "architecture" / "extension_points.toml").get(
            "extension_point", []
        )
    }
    for extension_point in extension_points or []:
        if str(extension_point) not in declared:
            errors.append(
                _services.finding(
                    "package-contract",
                    "error",
                    subject,
                    "extension point is not declared in architecture/extension_points.toml",
                    str(extension_point),
                )
            )


def _valid_iso_date(raw: object, *, _services: ArchitectureReportServices) -> bool:
    if not isinstance(raw, str):
        return False
    try:
        parsed = dt.date.fromisoformat(raw)
    except ValueError:
        return False
    return parsed.isoformat() == raw


def _valid_future_or_today(raw: str, *, _services: ArchitectureReportServices) -> bool:
    try:
        return dt.date.fromisoformat(raw) >= dt.date.today()
    except ValueError:
        return False


def _mirror_value_type(value: object, *, _services: ArchitectureReportServices) -> str:
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
    _services: ArchitectureReportServices,
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
    findings: list[FindingLike],
    subject: str,
    field: str,
    value: object,
    *,
    domain: _MirrorFieldDomain,
    side: str,
    optional: bool = False,
    _services: ArchitectureReportServices,
) -> bool:
    if _services.dispatch("_mirror_value_matches_domain", value, domain, optional=optional):
        return True
    optional_suffix = " or absent" if optional else ""
    findings.append(
        _services.finding(
            "package-mirror",
            "error",
            subject,
            f"{field} has malformed {side} value",
            f"expected {domain}{optional_suffix}; got {_services.dispatch('_mirror_value_type', value)}",
        )
    )
    return False


def _record_malformed_mirror_value(
    findings: list[FindingLike],
    subject: str,
    field: str,
    value: object,
    *,
    domain: _MirrorFieldDomain,
    side: str,
    optional: bool = False,
    _services: ArchitectureReportServices,
) -> None:
    _services.dispatch(
        "_validate_mirror_value",
        findings,
        subject,
        field,
        value,
        domain=domain,
        side=side,
        optional=optional,
    )


def _compare_typed_value(
    findings: list[FindingLike],
    subject: str,
    field: str,
    *,
    expected: object,
    observed: object,
    domain: _MirrorFieldDomain,
    optional: bool = False,
    _services: ArchitectureReportServices,
) -> None:
    expected_valid = _services.dispatch(
        "_validate_mirror_value",
        findings,
        subject,
        field,
        expected,
        domain=domain,
        side="source",
        optional=optional,
    )
    observed_valid = _services.dispatch(
        "_validate_mirror_value",
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
            _services.finding(
                "package-mirror",
                "error",
                subject,
                f"{field} drift",
                f"expected={expected!r} observed={observed!r}",
            )
        )


def _compare_scalar(
    findings: list[FindingLike],
    subject: str,
    field: str,
    *,
    expected: object,
    observed: object,
    _services: ArchitectureReportServices,
) -> None:
    _services.dispatch(
        "_compare_typed_value",
        findings,
        subject,
        field,
        expected=expected,
        observed=observed,
        domain="string",
    )


def _compare_boolean(
    findings: list[FindingLike],
    subject: str,
    field: str,
    *,
    expected: object,
    observed: object,
    _services: ArchitectureReportServices,
) -> None:
    _services.dispatch(
        "_compare_typed_value",
        findings,
        subject,
        field,
        expected=expected,
        observed=observed,
        domain="boolean",
    )


def _compare_list(
    findings: list[FindingLike],
    subject: str,
    field: str,
    *,
    expected: object,
    observed: object,
    _services: ArchitectureReportServices,
) -> None:
    _services.dispatch(
        "_compare_typed_value",
        findings,
        subject,
        field,
        expected=expected,
        observed=observed,
        domain="string_list",
    )


def _compare_optional_scalar(
    findings: list[FindingLike],
    subject: str,
    field: str,
    *,
    expected: object,
    observed: object,
    _services: ArchitectureReportServices,
) -> None:
    _services.dispatch(
        "_compare_typed_value",
        findings,
        subject,
        field,
        expected=expected,
        observed=observed,
        domain="string",
        optional=True,
    )


def _compare_optional_list(
    findings: list[FindingLike],
    subject: str,
    field: str,
    *,
    expected: object,
    observed: object,
    _services: ArchitectureReportServices,
) -> None:
    _services.dispatch(
        "_compare_typed_value",
        findings,
        subject,
        field,
        expected=expected,
        observed=observed,
        domain="string_list",
        optional=True,
    )
