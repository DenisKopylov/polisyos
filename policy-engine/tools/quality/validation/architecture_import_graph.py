"""Focused architecture report validator owner."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.quality.validation.architecture_package_contracts import (
        ArchitectureReportServices,
        FindingLike,
    )

import datetime as dt
import fnmatch
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.quality.lint import lint_imports


def _validate_import_reports(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> list[FindingLike]:
    errors = _services.dispatch(
        "_validate_list_contract",
        repo_root,
        relative_path="architecture/imports/reports.toml",
        header="import_reports",
        entries="report",
        required_fields=("id", "owner", "mode", "source_contracts", "output", "command"),
        list_path_fields=("source_contracts",),
    )
    data = _services.read_toml(repo_root / "architecture" / "imports" / "reports.toml")
    for item in data.get("report", []):
        if item.get("mode") != "report_only":
            errors.append(
                _services.finding(
                    "import-reports",
                    "error",
                    str(item.get("id", "unknown")),
                    "import report mode must be report_only",
                    str(item.get("mode")),
                )
            )
    return errors


def _summarize_dynamic_imports(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> list[FindingLike]:
    summary = _services.dispatch("_dynamic_imports_summary", repo_root)
    return [
        _services.finding(
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


def _dynamic_imports_summary(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> dict[str, Any]:
    data = _services.read_toml(repo_root / "architecture" / "imports" / "dynamic.toml")
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


def _validate_dynamic_imports_contract(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> list[FindingLike]:
    relative_path = "architecture/imports/dynamic.toml"
    path = repo_root / relative_path
    if not path.exists():
        return [
            _services.finding("dynamic-imports", "error", relative_path, "contract file is missing")
        ]
    data = _services.read_toml(path)
    errors: list[FindingLike] = []
    header = data.get("dynamic_imports", {})
    for field in ("owner", "extension_points", "new_entry_required_fields"):
        if header.get(field) in (None, "", []):
            errors.append(
                _services.finding("dynamic-imports", "error", relative_path, f"missing `{field}`")
            )
    extension_points = str(header.get("extension_points", ""))
    if extension_points and not _services.path_pattern_exists(repo_root, extension_points):
        errors.append(
            _services.finding(
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
                    _services.finding(
                        "dynamic-imports", "error", subject, f"missing required field `{field}`"
                    )
                )
        if item.get("target") in (None, "", []) and item.get("allowed_targets") in (None, "", []):
            errors.append(
                _services.finding(
                    "dynamic-imports",
                    "error",
                    subject,
                    "missing target or allowed_targets",
                )
            )
        source_file = str(item.get("source_file", ""))
        if source_file and not _services.path_pattern_exists(repo_root, source_file):
            errors.append(
                _services.finding(
                    "dynamic-imports", "error", subject, "source_file is missing", source_file
                )
            )
    return errors


def _validate_dynamic_imports_gate(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> list[FindingLike]:
    from tools.quality.validation import decomposition_preflight

    return _services.dispatch(
        "_preflight_errors",
        check="dynamic-imports",
        findings=decomposition_preflight.validate_dynamic_imports(),
        repo_root=repo_root,
    )


def _validate_import_cycles_gate(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> list[FindingLike]:
    from tools.quality.validation import decomposition_preflight

    return _services.dispatch(
        "_preflight_errors",
        check="import-cycle",
        findings=decomposition_preflight.validate_import_cycles(),
        repo_root=repo_root,
    )


def _validate_reexport_shim_shape_gate(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> list[FindingLike]:
    from tools.quality.validation import decomposition_preflight

    return _services.dispatch(
        "_preflight_errors",
        check="reexport-shim-shape",
        findings=decomposition_preflight.validate_reexport_shim_shapes(),
        repo_root=repo_root,
    )


def _preflight_errors(
    *,
    check: str,
    findings: list[Any],
    repo_root: Path,
    _services: ArchitectureReportServices,
) -> list[FindingLike]:
    return [
        _services.finding(
            check,
            "error",
            str(getattr(finding, "gate", check)),
            str(getattr(finding, "message", "")),
            str(getattr(finding, "detail", "")),
        )
        for finding in findings
    ]


def _import_cycles_summary(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> dict[str, Any]:
    from tools.quality.validation import decomposition_preflight

    findings = decomposition_preflight.validate_import_cycles()
    lazy_path = repo_root / "architecture" / "imports" / "lazy.toml"
    allowed_cycle_count = 0
    if lazy_path.exists():
        allowed_cycle_count = len(_services.read_toml(lazy_path).get("allowed_cycle", []))
    return {
        "status": "fail_closed",
        "allowed_cycle_count": allowed_cycle_count,
        "new_cycle_count": len(findings),
        "new_cycle_examples": [str(getattr(finding, "detail", "")) for finding in findings[:25]],
    }


def _structure_gate_summary(
    repo_root: Path, *, gate: str, _services: ArchitectureReportServices
) -> dict[str, Any]:
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


def _structure_gate_findings(
    repo_root: Path, *, gate: str, _services: ArchitectureReportServices
) -> list[FindingLike]:
    summary = _services.dispatch("_structure_gate_summary", repo_root, gate=gate)
    check = "package-layout" if gate == "loose_files" else "name-collision"
    findings: list[FindingLike] = []
    for item in summary["findings"]:
        subject = str(item.get("package") or item.get("name") or gate)
        findings.append(
            _services.finding(
                check,
                "report_only",
                subject,
                str(item.get("message", "")),
                json.dumps(item, sort_keys=True),
            )
        )
    return findings


def _validate_shim_expiry_contract(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> list[FindingLike]:
    relative_path = "architecture/shims.toml"
    path = repo_root / relative_path
    if not path.exists():
        return [
            _services.finding("shim-expiry", "error", relative_path, "shim registry is missing")
        ]
    errors: list[FindingLike] = []
    today = dt.date.today()
    for shim in _services.read_toml(path).get("shim", []):
        subject = str(shim.get("id", "unknown"))
        for field in ("id", "source_path", "target_path", "type", "owner", "reason", "sunset_date"):
            if shim.get(field) in (None, "", []):
                errors.append(
                    _services.finding("shim-expiry", "error", subject, f"missing `{field}`")
                )
        raw_sunset = str(shim.get("sunset_date", ""))
        try:
            sunset = dt.date.fromisoformat(raw_sunset)
        except ValueError:
            errors.append(
                _services.finding(
                    "shim-expiry", "error", subject, "invalid sunset_date", raw_sunset
                )
            )
            continue
        if sunset < today:
            errors.append(
                _services.finding(
                    "shim-expiry", "error", subject, "shim sunset has expired", raw_sunset
                )
            )
        path_fields = ["target_path"]
        if str(shim.get("type", "")) in {"python_reexport", "wrapper_only"}:
            path_fields.append("source_path")
        for field in path_fields:
            value = str(shim.get(field, ""))
            if value and not _services.path_pattern_exists(repo_root, value):
                errors.append(
                    _services.finding(
                        "shim-expiry", "error", subject, f"{field} path is missing", value
                    )
                )
    return errors


def _load_public_surface_packages(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> dict[str, set[str]]:
    data = _services.read_toml(repo_root / "architecture" / "public_surface" / "contract.toml")
    packages: dict[str, set[str]] = {}
    for item in data.get("package", []):
        module = str(item.get("module", "")).strip()
        if not module:
            continue
        entrypoints = {module}
        entrypoints.update(str(entry) for entry in item.get("supported_entrypoints", []))
        packages[module] = entrypoints
    return packages


def _package_for_module(
    module: str, package_modules: list[str], *, _services: ArchitectureReportServices
) -> str | None:
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
    *,
    _services: ArchitectureReportServices,
) -> bool:
    return target_module in public_packages.get(target_package, {target_package})


def _load_deep_import_baseline(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> dict[str, dict[str, str]]:
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


def _read_import_exceptions(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> list[lint_imports.ImportException]:
    try:
        return lint_imports.read_exceptions(
            repo_root / "architecture" / "imports" / "exceptions.toml"
        )
    except ValueError:
        return []


def _validate_import_exception_metadata(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> list[FindingLike]:
    errors: list[FindingLike] = []
    relative_path = "architecture/imports/exceptions.toml"
    path = repo_root / relative_path
    if not path.exists():
        return [
            _services.finding(
                "import-exceptions", "error", relative_path, "exception file is missing"
            )
        ]
    try:
        exceptions = lint_imports.read_exceptions(path)
    except ValueError as exc:
        return [
            _services.finding(
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
                _services.finding(
                    "import-exceptions",
                    "error",
                    exception.exception_id,
                    "import exception is expired",
                    exception.expires.isoformat(),
                )
            )
        if exception.expires > max_expiry:
            errors.append(
                _services.finding(
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
    for exception in _services.read_toml(guardrail_path).get("exception", []):
        if str(exception.get("check", "")) != "deep_import":
            continue
        subject = str(exception.get("id", "deep_import"))
        for field in ("id", "owner", "reason", "expires"):
            if not str(exception.get(field, "")).strip():
                errors.append(
                    _services.finding("import-exceptions", "error", subject, f"missing `{field}`")
                )
        try:
            expires = dt.date.fromisoformat(str(exception.get("expires", "")))
        except ValueError:
            errors.append(
                _services.finding(
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
                _services.finding(
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
    _services: ArchitectureReportServices,
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
    data = _services.read_toml(guardrail_path)
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


def _import_boundary_rule(*, _services: ArchitectureReportServices) -> str:
    return "first-party cross-package imports target supported public entrypoints unless registered"


def _collect_hidden_import_edges(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> dict[str, dict[str, Any]]:
    public_packages = _services.dispatch("_load_public_surface_packages", repo_root)
    package_modules = sorted(public_packages, key=len, reverse=True)
    policy_path = repo_root / "architecture" / "imports" / "policy.toml"
    config = lint_imports.read_policy(policy_path)
    imports, _, _, _, _ = lint_imports.parse_imports(config, cache_root=None)
    exceptions = _services.dispatch("_read_import_exceptions", repo_root)
    edges: dict[str, dict[str, Any]] = {}

    for ref in imports:
        if not lint_imports.is_internal_module(ref.target_module, config.internal_prefix):
            continue
        source_package = _services.dispatch(
            "_package_for_module", ref.source_module, package_modules
        )
        target_package = _services.dispatch(
            "_package_for_module", ref.target_module, package_modules
        )
        if source_package is None or target_package is None or source_package == target_package:
            continue
        if _services.dispatch(
            "_is_public_target", ref.target_module, target_package, public_packages
        ):
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
                "registered_exception": _services.dispatch(
                    "_registered_import_exception_id",
                    repo_root=repo_root,
                    ref=ref,
                    exceptions=exceptions,
                    target_root=target_root,
                ),
            },
        )
    return edges


def _boundary_packages(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("module", "")).strip(): item
        for item in _services.read_toml(
            repo_root / "architecture" / "packages" / "boundaries.toml"
        ).get("package", [])
        if str(item.get("module", "")).strip()
    }


def _matches_dependency(
    module: str, dependency: str, *, _services: ArchitectureReportServices
) -> bool:
    dependency = dependency.strip()
    if not dependency:
        return False
    if dependency.endswith(".*"):
        prefix = dependency.removesuffix(".*")
        return module == prefix or module.startswith(f"{prefix}.")
    return module == dependency or module.startswith(f"{dependency}.")


def _collect_forbidden_package_edges(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> dict[str, dict[str, Any]]:
    public_packages = _services.dispatch("_load_public_surface_packages", repo_root)
    boundaries = _services.dispatch("_boundary_packages", repo_root)
    package_modules = sorted(set(public_packages) | set(boundaries), key=len, reverse=True)
    config = lint_imports.read_policy(repo_root / "architecture" / "imports" / "policy.toml")
    imports, _, _, _, _ = lint_imports.parse_imports(config, cache_root=None)
    exceptions = _services.dispatch("_read_import_exceptions", repo_root)
    edges: dict[str, dict[str, Any]] = {}

    for ref in imports:
        if not lint_imports.is_internal_module(ref.target_module, config.internal_prefix):
            continue
        source_package = _services.dispatch(
            "_package_for_module", ref.source_module, package_modules
        )
        target_package = _services.dispatch(
            "_package_for_module", ref.target_module, package_modules
        )
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
                if _services.dispatch("_matches_dependency", ref.target_module, dependency)
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
                "registered_exception": _services.dispatch(
                    "_registered_import_exception_id",
                    repo_root=repo_root,
                    ref=ref,
                    exceptions=exceptions,
                    target_root=target_root,
                ),
            },
        )
    return edges


def _package_pair(
    edge: dict[str, str],
    package_modules: list[str],
    *,
    _services: ArchitectureReportServices,
) -> tuple[str, str]:
    source_package = (
        _services.dispatch(
            "_package_for_module", str(edge.get("source_module", "")), package_modules
        )
        or ""
    )
    target_package = (
        _services.dispatch(
            "_package_for_module", str(edge.get("target_module", "")), package_modules
        )
        or ""
    )
    return source_package, target_package


def _package_edge_sets(
    edges: dict[str, dict[str, Any]],
    package_modules: list[str],
    *,
    _services: ArchitectureReportServices,
) -> dict[tuple[str, str], set[str]]:
    grouped: dict[tuple[str, str], set[str]] = defaultdict(set)
    for key, edge in edges.items():
        pair = _services.dispatch("_package_pair", edge, package_modules)
        if not pair[0] or not pair[1] or pair[0] == pair[1]:
            continue
        grouped[pair].add(key)
    return grouped


def _package_boundary_forbidden_summary(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> dict[str, Any]:
    public_packages = _services.dispatch("_load_public_surface_packages", repo_root)
    boundaries = _services.dispatch("_boundary_packages", repo_root)
    package_modules = sorted(set(public_packages) | set(boundaries), key=len, reverse=True)
    edges = _services.dispatch("_collect_forbidden_package_edges", repo_root)
    grouped = _services.dispatch("_package_edge_sets", edges, package_modules)
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


def _build_import_boundary_summary(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> dict[str, Any]:
    public_packages = _services.dispatch("_load_public_surface_packages", repo_root)
    package_modules = sorted(public_packages, key=len, reverse=True)
    current_edges = _services.dispatch("_collect_hidden_import_edges", repo_root)
    baseline_edges = _services.dispatch("_load_deep_import_baseline", repo_root)
    current_by_pair = _services.dispatch("_package_edge_sets", current_edges, package_modules)
    baseline_by_pair = _services.dispatch("_package_edge_sets", baseline_edges, package_modules)
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
        "rule": _services.dispatch(
            "_import_boundary_rule",
        ),
        "current_hidden_edge_count": len(current_edges),
        "baseline_hidden_edge_count": len(baseline_edges),
        "added_hidden_edge_count": total_added,
        "removed_hidden_edge_count": total_removed,
        "registered_added_hidden_edge_count": total_registered_added,
        "unregistered_added_hidden_edge_count": len(unregistered_added_edges),
        "registered_added_edge_keys": registered_added_edges[:100],
        "unregistered_added_edge_keys": unregistered_added_edges[:100],
        "package_level_deltas": package_level_deltas,
        "public_surface_import_contract": _services.dispatch(
            "_public_surface_import_contract_summary", repo_root
        ),
    }


def _import_boundary_findings(
    summary: dict[str, Any], *, _services: ArchitectureReportServices
) -> list[FindingLike]:
    findings: list[FindingLike] = []
    for row in summary["package_level_deltas"]:
        if (
            row["delta_hidden_edges"] == 0
            and row["added_hidden_edges"] == 0
            and row["removed_hidden_edges"] == 0
        ):
            continue
        findings.append(
            _services.finding(
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
            _services.finding(
                "public-surface-import-contract",
                "report_only",
                "architecture/packages/boundaries.toml",
                "public surface and import contracts drift",
                f"drift_count={contract['drift_count']}",
            )
        )
    return findings


def _package_boundary_findings(
    summary: dict[str, Any], *, _services: ArchitectureReportServices
) -> list[FindingLike]:
    findings: list[FindingLike] = []
    for row in summary["package_level_forbidden_edges"]:
        findings.append(
            _services.finding(
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


def _import_boundary_delta_errors(
    summary: dict[str, Any], *, _services: ArchitectureReportServices
) -> list[FindingLike]:
    errors: list[FindingLike] = []
    for row in summary["package_level_deltas"]:
        if row["unregistered_added_hidden_edges"] <= 0:
            continue
        errors.append(
            _services.finding(
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


def _package_boundary_forbidden_errors(
    summary: dict[str, Any], *, _services: ArchitectureReportServices
) -> list[FindingLike]:
    errors: list[FindingLike] = []
    for row in summary["package_level_forbidden_edges"]:
        if row["unregistered_forbidden_edges"] <= 0:
            continue
        errors.append(
            _services.finding(
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


def _public_surface_import_contract_summary(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> dict[str, Any]:
    import_contract_errors = _services.dispatch(
        "_validate_public_surface_import_contracts", repo_root
    )
    inventory_errors = _services.dispatch("_validate_public_surface_inventory_contract", repo_root)
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
