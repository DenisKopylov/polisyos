"""Focused architecture report validator owner."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tools.quality.validation.architecture_package_contracts import (
    _MISSING_VALUE,
)

if TYPE_CHECKING:
    from tools.quality.validation.architecture_package_contracts import (
        ArchitectureReportServices,
        FindingLike,
        _PackageMirrorFamilyAdmission,
    )

import stat
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

from tools.lib.fs import AdmittedPathError


def _validate_generated_artifact_contracts(
    repo_root: Path,
    *,
    family_admission: _PackageMirrorFamilyAdmission | None = None,
    _services: ArchitectureReportServices,
) -> list[FindingLike]:
    relative_path = "architecture/generated_artifacts.toml"
    path = repo_root / relative_path
    if not path.exists():
        return [
            _services.finding(
                "generated-artifacts", "error", relative_path, "contract file is missing"
            )
        ]
    admission = family_admission or _services.dispatch(
        "_admit_package_mirror_family_registry", repo_root
    )
    errors: list[FindingLike] = _services.dispatch(
        "_family_registry_findings", admission, check="generated-artifacts"
    )
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
                    _services.finding(
                        "generated-artifacts",
                        "error",
                        subject,
                        f"missing required field `{field}`",
                    )
                )
        lifecycle = str(family.get("lifecycle", ""))
        if lifecycle and lifecycle not in allowed_lifecycles:
            errors.append(
                _services.finding(
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
                _services.finding(
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
                _services.finding(
                    "generated-artifacts",
                    "error",
                    subject,
                    "local_ignored family cannot use generated_committed lifecycle",
                )
            )
        if commit_policy == "committed" and lifecycle in {"generated_ignored", "runtime_ignored"}:
            errors.append(
                _services.finding(
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
    _services: ArchitectureReportServices,
) -> list[FindingLike]:
    errors: list[FindingLike] = []
    path = repo_root / relative_path
    if not path.exists():
        return [_services.finding("contract", "error", relative_path, "contract file is missing")]
    data = _services.read_toml(path)
    header_data = data.get(header, {})
    if header_data.get("status") not in allowed_header_statuses:
        errors.append(
            _services.finding(
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
                _services.finding(
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
                    _services.finding(
                        "contract", "error", subject, f"missing required field `{field}`"
                    )
                )
        for field in path_fields:
            value = item.get(field)
            if value and not _services.path_pattern_exists(repo_root, str(value)):
                errors.append(
                    _services.finding(
                        "contract", "error", subject, f"path field `{field}` is missing", str(value)
                    )
                )
        for field in list_path_fields:
            for value in item.get(field, []):
                if str(value).startswith("_build/"):
                    continue
                if not _services.path_pattern_exists(repo_root, str(value)):
                    errors.append(
                        _services.finding(
                            "contract",
                            "error",
                            subject,
                            f"path list `{field}` contains a missing path",
                            str(value),
                        )
                    )
    return errors


def _read_declared_active_component_index(
    repo_root: Path, relative_path: str, *, _services: ArchitectureReportServices
) -> tuple[dict[str, Any] | None, FindingLike | None]:
    """Read the declared active index through one typed, root-bound byte snapshot.

    Args:
        repo_root: Product root containing the declared component index.
        relative_path: Validated repository-relative index path.

    Returns:
        The parsed index and no finding, or no index and one typed input finding.
    """
    path = repo_root / Path(*PurePosixPath(relative_path).parts)
    try:
        resolved_path = _services.resolve_admitted_path(path, repo_root)
    except AdmittedPathError as error:
        return None, _services.finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index resolves outside repository root",
            f"error={type(error).__name__}",
        )
    except FileNotFoundError as error:
        return None, _services.finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index file is missing",
            f"error={type(error).__name__}",
        )
    except PermissionError as error:
        return None, _services.finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index is not readable",
            f"error={type(error).__name__}",
        )
    except (OSError, RuntimeError) as error:
        return None, _services.finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index could not be resolved",
            f"error={type(error).__name__}",
        )

    try:
        file_stat = resolved_path.stat()
    except FileNotFoundError as error:
        return None, _services.finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index file is missing",
            f"error={type(error).__name__}",
        )
    except PermissionError as error:
        return None, _services.finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index is not readable",
            f"error={type(error).__name__}",
        )
    except OSError as error:
        return None, _services.finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index could not be inspected",
            f"error={type(error).__name__}",
        )

    if not stat.S_ISREG(file_stat.st_mode):
        return None, _services.finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index is not a regular file",
        )

    try:
        return _services.read_toml(resolved_path), None
    except FileNotFoundError as error:
        return None, _services.finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index file is missing",
            f"error={type(error).__name__}",
        )
    except IsADirectoryError as error:
        return None, _services.finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index is not a regular file",
            f"error={type(error).__name__}",
        )
    except PermissionError as error:
        return None, _services.finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index is not readable",
            f"error={type(error).__name__}",
        )
    except UnicodeDecodeError as error:
        return None, _services.finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index is not valid UTF-8",
            f"error={type(error).__name__}",
        )
    except tomllib.TOMLDecodeError as error:
        return None, _services.finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index is not valid TOML",
            f"error={type(error).__name__}",
        )
    except OSError as error:
        return None, _services.finding(
            "operability-route",
            "error",
            relative_path,
            "declared active component index could not be read",
            f"error={type(error).__name__}",
        )


def _validate_legacy_operability_routes(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> tuple[list[FindingLike], dict[str, Any]]:
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
    findings: list[FindingLike] = []
    route_map: dict[str, list[dict[str, str]]] = {}
    source_documents = {
        source_path: _services.read_toml(repo_root / source_path)
        for source_path, _, _ in source_specs
    }
    runbook_source_path = "architecture/runbook_coverage.toml"
    runbook_header = source_documents[runbook_source_path].get("runbook_coverage", _MISSING_VALUE)
    active_index_path = runbook_source_path
    active_components: Any = []
    route_index_available = False
    if type(runbook_header) is not dict:
        findings.append(
            _services.finding(
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
                _services.finding(
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
                    _services.finding(
                        "operability-route",
                        "error",
                        runbook_source_path,
                        "runbook coverage component_index must not contain NUL",
                        repr(declared_index),
                    )
                )
            elif index_relative.is_absolute() or ".." in index_relative.parts:
                findings.append(
                    _services.finding(
                        "operability-route",
                        "error",
                        runbook_source_path,
                        "runbook coverage component_index must stay within the repository",
                        declared_index,
                    )
                )
            else:
                active_index_path = index_relative.as_posix()
                active_index, index_finding = _services.dispatch(
                    "_read_declared_active_component_index", repo_root, active_index_path
                )
                if index_finding is not None:
                    findings.append(index_finding)
                elif active_index is not None:
                    active_components = active_index.get("component", _MISSING_VALUE)
                    if type(active_components) is list:
                        route_index_available = True
                    else:
                        findings.append(
                            _services.finding(
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
                _services.finding(
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
                _services.finding(
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
                _services.finding(
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
                    _services.finding(
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
                        _services.finding(
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
                        _services.finding(
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
                    _services.finding(
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
                        _services.finding(
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
        contract = _services.read_toml(repo_root / source_path)
        rows = contract.get(entry_table, _MISSING_VALUE)
        if type(rows) is not list:
            findings.append(
                _services.finding(
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
                    _services.finding(
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
                        _services.finding(
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
                            _services.finding(
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
                            _services.finding(
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


def _validate_extension_points_contract(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> list[FindingLike]:
    relative_path = "architecture/extension_points.toml"
    path = repo_root / relative_path
    if not path.exists():
        return [
            _services.finding(
                "extension-points", "error", relative_path, "contract file is missing"
            )
        ]
    data = _services.read_toml(path)
    errors: list[FindingLike] = []
    header = data.get("extension_points", {})
    if not header.get("owner"):
        errors.append(
            _services.finding("extension-points", "error", relative_path, "missing owner")
        )
    overlay = data.get("phase_1_3_report_only_overlay", {})
    if overlay.get("status") != "report_only":
        errors.append(
            _services.finding(
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
                errors.append(
                    _services.finding("extension-points", "error", subject, f"missing `{field}`")
                )
    for item in data.get("phase_1_3_extension_point", []):
        subject = str(item.get("id") or "phase_1_3_extension_point")
        for field in ("id", "owner", "package", "surface", "boundary_contract", "mode"):
            if not item.get(field):
                errors.append(
                    _services.finding("extension-points", "error", subject, f"missing `{field}`")
                )
        if item.get("mode") != "report_only":
            errors.append(
                _services.finding(
                    "extension-points",
                    "error",
                    subject,
                    "Phase 1.3 extension point mode must be report_only",
                    str(item.get("mode")),
                )
            )
        contract = str(item.get("boundary_contract", ""))
        if contract and not _services.path_pattern_exists(repo_root, contract):
            errors.append(
                _services.finding(
                    "extension-points",
                    "error",
                    subject,
                    "boundary contract is missing",
                    contract,
                )
            )
    return errors
