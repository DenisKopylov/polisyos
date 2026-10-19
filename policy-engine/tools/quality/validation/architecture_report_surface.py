"""Architecture report assembly and public-surface validator owner."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tools.lib.imports import repo_root_from
from tools.quality.validation.architecture_package_contracts import PACKAGE_MIRROR_FAMILY_ID

if TYPE_CHECKING:
    from tools.quality.validation.architecture_package_contracts import (
        ArchitectureReportServices,
        FindingLike,
        _PackageMirrorFamilyAdmission,
    )

import datetime as dt
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


def _validate_public_surface_import_contracts(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> list[FindingLike]:
    errors: list[FindingLike] = []
    public_packages = _services.dispatch("_load_public_surface_packages", repo_root)
    package_modules = sorted(public_packages, key=len, reverse=True)
    boundaries = _services.read_toml(repo_root / "architecture" / "packages" / "boundaries.toml")
    for package in boundaries.get("package", []):
        subject = str(package.get("module", ""))
        entrypoints = public_packages.get(subject, {subject})
        public_facade = str(package.get("public_facade", ""))
        if public_facade and public_facade not in entrypoints:
            errors.append(
                _services.finding(
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
                target_package = _services.dispatch(
                    "_package_for_module", dependency, package_modules
                )
                if target_package is None:
                    continue
                if dependency not in public_packages.get(target_package, {target_package}):
                    errors.append(
                        _services.finding(
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

    import_contracts = _services.read_toml(
        repo_root / "architecture" / "imports" / "contracts.toml"
    )
    for contract in import_contracts.get("importlinter", {}).get("contracts", []):
        for ignored in contract.get("ignore_imports", []):
            ignored = str(ignored)
            if not ignored.startswith("polisyos."):
                continue
            normalized = ignored.removesuffix(".*")
            target_package = _services.dispatch("_package_for_module", normalized, package_modules)
            if target_package is None:
                continue
            if normalized not in public_packages.get(target_package, {target_package}):
                errors.append(
                    _services.finding(
                        "public-surface-import-contract",
                        "error",
                        str(contract.get("name", "importlinter contract")),
                        "import_contracts.ignore_imports path is not a supported public entrypoint",
                        ignored,
                    )
                )
    return errors


def _validate_public_surface_inventory_contract(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> list[FindingLike]:
    manifest_path = repo_root / "architecture" / "public_surface" / "contract.toml"
    inventory_path = repo_root / "architecture" / "public_surface" / "inventory.json"
    relative_path = "architecture/public_surface/inventory.json"
    if not inventory_path.exists():
        return [
            _services.finding(
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
            _services.finding(
                "public-surface-inventory",
                "error",
                relative_path,
                "public-surface inventory is not valid JSON",
                str(exc),
            )
        ]

    manifest_packages = {
        str(item.get("module", "")): item
        for item in _services.read_toml(manifest_path).get("package", [])
        if str(item.get("module", ""))
    }
    inventory_packages = {
        str(item.get("module", "")): item
        for item in inventory.get("packages", [])
        if str(item.get("module", ""))
    }
    errors: list[FindingLike] = []
    missing = sorted(set(manifest_packages) - set(inventory_packages))
    extra = sorted(set(inventory_packages) - set(manifest_packages))
    for module in missing:
        errors.append(
            _services.finding(
                "public-surface-inventory",
                "error",
                module,
                "manifest package is missing from public-surface inventory",
            )
        )
    for module in extra:
        errors.append(
            _services.finding(
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
                    _services.finding(
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
                _services.finding(
                    "public-surface-inventory",
                    "error",
                    module,
                    "supported_entrypoints drift",
                    f"manifest={manifest_entries!r} inventory={inventory_entries!r}",
                )
            )
    return errors


def _shim_debt_summary(repo_root: Path, *, _services: ArchitectureReportServices) -> dict[str, Any]:
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
    shims = _services.read_toml(path).get("shim", [])
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


def _validate_static_analysis_overrides(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> list[FindingLike]:
    from tools.ops_runners.reports import dead_overrides

    findings: list[FindingLike] = []
    data = _services.read_toml(
        repo_root / "architecture" / "tooling" / "static_analysis_overrides.toml"
    )
    header = data.get("static_analysis_overrides", {})
    if header.get("status") != "report_only":
        findings.append(
            _services.finding(
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
                    _services.finding(
                        "static-analysis-overrides",
                        "report_only",
                        field,
                        "tool config split field is missing",
                    )
                )
            elif not (repo_root / value).exists():
                findings.append(
                    _services.finding(
                        "static-analysis-overrides",
                        "report_only",
                        value,
                        "tool config split path is missing",
                    )
                )
        if split.get("check_command") != "uv run polisyos-tools workspace tool-configs --check":
            findings.append(
                _services.finding(
                    "static-analysis-overrides",
                    "report_only",
                    "tool_config_split.check_command",
                    "tool config split check command is not canonical",
                    str(split.get("check_command", "")),
                )
            )
    counts = _services.dispatch("_inline_override_counts", repo_root)
    for key, observed in counts.items():
        baseline = int(baselines.get(key, 0))
        if observed > baseline:
            findings.append(
                _services.finding(
                    "static-analysis-overrides",
                    "report_only",
                    key,
                    "inline override count exceeds report-only baseline",
                    f"observed={observed} baseline={baseline}",
                )
            )
        elif observed < baseline:
            findings.append(
                _services.finding(
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
                _services.finding(
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
                _services.finding(
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
            _services.finding(
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


def _inline_override_counts(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> dict[str, int]:
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


REPO_ROOT = repo_root_from(__file__)


def build_report(
    repo_root: Path = REPO_ROOT,
    *,
    report: str = "all",
    enforce_import_boundary_deltas: bool = False,
    _services: ArchitectureReportServices,
) -> dict[str, Any]:
    if report not in _services.reports:
        raise ValueError(f"unsupported report: {report}")

    findings: list[FindingLike] = []
    contract_errors: list[FindingLike] = []
    import_boundary_summary: dict[str, Any] | None = None
    package_boundary_summary: dict[str, Any] | None = None
    package_contract_findings: list[FindingLike] | None = None
    package_mirror_summary: dict[str, Any] | None = None
    legacy_operability_route_summary: dict[str, Any] | None = None

    def selected(name: str) -> bool:
        return report in {"all", name}

    def selected_any(*names: str) -> bool:
        return report == "all" or report in set(names)

    family_admission = _services.dispatch("_admit_package_mirror_family_registry", repo_root)
    if selected("packages"):
        package_contract_findings = _services.dispatch(
            "_validate_package_contracts", repo_root, family_admission=family_admission
        )
        contract_errors.extend(package_contract_findings)
        if not selected("package-mirrors"):
            contract_errors.extend(
                _services.dispatch(
                    "_family_registry_findings", family_admission, check="package-mirror"
                )
            )
    if selected("package-mirrors"):
        if package_contract_findings is None:
            package_contract_findings = _services.dispatch(
                "_validate_package_contracts", repo_root, family_admission=family_admission
            )
            contract_errors.extend(package_contract_findings)
        mirror_findings, package_mirror_summary = _services.dispatch(
            "_validate_package_mirror_projection", repo_root, family_admission=family_admission
        )
        contract_errors.extend(mirror_findings)
        scoped_errors = mirror_findings
        package_mirror_summary["status"] = "passed" if not scoped_errors else "failed"
        package_mirror_summary["error_count"] = len(scoped_errors)
        package_mirror_summary["errors"] = [finding.as_dict() for finding in scoped_errors]
    if selected("module-size"):
        module_size_findings = _services.dispatch("_validate_module_size_budget", repo_root)
        contract_errors.extend(
            finding for finding in module_size_findings if finding.severity == "error"
        )
        findings.extend(finding for finding in module_size_findings if finding.severity != "error")
    if selected("generated-artifacts"):
        contract_errors.extend(
            _services.dispatch(
                "_validate_generated_artifact_contracts",
                repo_root,
                family_admission=family_admission,
            )
        )
    if selected("extension-points"):
        contract_errors.extend(_services.dispatch("_validate_extension_points_contract", repo_root))
    if selected("runbook-coverage"):
        contract_errors.extend(
            _services.dispatch(
                "_validate_list_contract",
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
            _services.dispatch(
                "_validate_list_contract",
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
        route_findings, legacy_operability_route_summary = _services.dispatch(
            "_validate_legacy_operability_routes", repo_root
        )
        contract_errors.extend(route_findings)
    if selected("runtime-state-layout"):
        contract_errors.extend(
            _services.dispatch(
                "_validate_list_contract",
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
            _services.dispatch(
                "_validate_list_contract",
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
        contract_errors.extend(_services.dispatch("_validate_directory_contracts", repo_root))
    if selected("directory-hygiene-assets"):
        contract_errors.extend(_services.dispatch("_validate_directory_hygiene_assets", repo_root))
    if selected_any("dependency-graph", "phase6-1"):
        contract_errors.extend(_services.dispatch("_validate_import_reports", repo_root))
        import_boundary_summary = _services.dispatch("_build_import_boundary_summary", repo_root)
        package_boundary_summary = _services.dispatch(
            "_package_boundary_forbidden_summary", repo_root
        )
        contract_errors.extend(_services.dispatch("_validate_import_exception_metadata", repo_root))
        contract_errors.extend(
            _services.dispatch("_validate_public_surface_import_contracts", repo_root)
        )
        contract_errors.extend(
            _services.dispatch("_validate_public_surface_inventory_contract", repo_root)
        )
        if enforce_import_boundary_deltas:
            contract_errors.extend(
                _services.dispatch("_import_boundary_delta_errors", import_boundary_summary)
            )
            contract_errors.extend(
                _services.dispatch("_package_boundary_forbidden_errors", package_boundary_summary)
            )
        findings.extend(_services.dispatch("_import_boundary_findings", import_boundary_summary))
        findings.extend(_services.dispatch("_package_boundary_findings", package_boundary_summary))
    if selected_any("dynamic-imports", "phase6-1"):
        contract_errors.extend(_services.dispatch("_validate_dynamic_imports_contract", repo_root))
        contract_errors.extend(_services.dispatch("_validate_dynamic_imports_gate", repo_root))
        findings.extend(_services.dispatch("_summarize_dynamic_imports", repo_root))
    if selected_any("import-cycles", "phase6-1"):
        contract_errors.extend(_services.dispatch("_validate_import_cycles_gate", repo_root))
    if selected_any("package-layout", "phase6-1"):
        findings.extend(
            _services.dispatch("_structure_gate_findings", repo_root, gate="loose_files")
        )
    if selected_any("name-collisions", "phase6-1"):
        findings.extend(
            _services.dispatch("_structure_gate_findings", repo_root, gate="name_collision")
        )
    if selected_any("shim-expiry", "phase6-1"):
        contract_errors.extend(_services.dispatch("_validate_shim_expiry_contract", repo_root))
        contract_errors.extend(_services.dispatch("_validate_reexport_shim_shape_gate", repo_root))
    if selected("static-analysis-overrides"):
        findings.extend(_services.dispatch("_validate_static_analysis_overrides", repo_root))

    gate_errors = _services.dispatch("_validate_report_only_gates", repo_root)
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

    summary = _services.dispatch("_summary", repo_root, family_admission=family_admission)
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
        summary["dynamic_imports"] = _services.dispatch("_dynamic_imports_summary", repo_root)
    if selected_any("import-cycles", "phase6-1"):
        summary["import_cycles"] = _services.dispatch("_import_cycles_summary", repo_root)
    if selected_any("package-layout", "phase6-1"):
        summary["package_layout"] = _services.dispatch(
            "_structure_gate_summary", repo_root, gate="loose_files"
        )
    if selected_any("name-collisions", "phase6-1"):
        summary["name_collisions"] = _services.dispatch(
            "_structure_gate_summary", repo_root, gate="name_collision"
        )
    if (
        selected("dependency-graph")
        or selected("package-mirrors")
        or selected_any("shim-expiry", "phase6-1")
    ):
        summary["shim_debt"] = _services.dispatch("_shim_debt_summary", repo_root)
    if selected("phase6-1"):
        summary["phase6_1"] = _services.dispatch(
            "_phase6_1_summary",
        )

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


def _summary(
    repo_root: Path,
    *,
    family_admission: _PackageMirrorFamilyAdmission | None = None,
    _services: ArchitectureReportServices,
) -> dict[str, Any]:
    from tools.ops_runners.reports import dead_overrides

    packages = _services.dispatch(
        "_load_package_contracts", repo_root, family_admission=family_admission
    )
    gates = _services.read_toml(repo_root / "architecture" / "gates" / "report_only.toml").get(
        "gate", []
    )
    module_budget = _services.read_toml(repo_root / "architecture" / "module_size_budget.toml")
    return {
        "package_contract_count": len(packages),
        "package_contracts": [
            _services.dispatch("_package_contract_summary_id", path, data, repo_root)
            for path, data in packages
        ],
        "report_only_gate_count": len(gates),
        "module_size_budget_count": len(module_budget.get("budget", [])),
        "static_analysis_counts": _services.dispatch("_inline_override_counts", repo_root),
        "dead_override_report": dead_overrides.build_report(repo_root)["summary"],
    }


def _package_contract_summary_id(
    path: Path, data: dict[str, Any], repo_root: Path, *, _services: ArchitectureReportServices
) -> str:
    package = data.get("package", {})
    if isinstance(package, dict):
        return str(package.get("id", _services.dispatch("_relative", path, repo_root)))
    if isinstance(package, list) and package and isinstance(package[0], dict):
        return str(package[0].get("id", _services.dispatch("_relative", path, repo_root)))
    return _services.dispatch("_relative", path, repo_root)


def _phase6_1_summary(*, _services: ArchitectureReportServices) -> dict[str, Any]:
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
