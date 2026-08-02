#!/usr/bin/env python3
"""Validate the GY generated/public lifecycle audit artifact.

This check protects the GY-M1 hard gate: every committed GY artifact must
resolve to exactly one generated-artifact family output, and registered family
outputs must dereference to files on disk.

Usage:
    python3 tools/quality/validation/check_layer3_gy_generated_public_lifecycle_audit.py [--json]
"""
from __future__ import annotations

from time import perf_counter as _timing_perf_counter

_TIMING_STARTED_AT = _timing_perf_counter()

import argparse
import contextlib
import hashlib
import importlib.util
import json
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from tools.lib.timing import run_timed_entrypoint

DEFAULT_AUDIT = (
    Path(__file__).resolve().parents[3]
    / "architecture"
    / "policy_design_case"
    / "layer3_gy_task0_audit"
    / "layer3_gy_generated_public_lifecycle_audit.json"
)

REQUIRED_PATTERNS = {
    "P01",
    "P03",
    "P05",
    "P07",
    "P10",
    "P13",
    "P15",
    "P25",
    "P29",
    "P31",
    "P32",
    "P33",
}
REQUIRED_NEGATIVES = {
    "do_not_count_projection_refs_as_api_dashboard_enforcement",
    "unregistered_gy_artifact_probe_fails_class_gate",
    "missing_registered_gy_output_fails_class_gate",
    "duplicate_gy_family_claim_fails_class_gate",
}
REQUIRED_ROWS = {
    "layer3_g1_to_g8_and_gl",
    "layer3_gx_hardening",
    "layer3_gy_task0_audit_artifacts",
    "runtime_openapi_snapshot",
    "runtime_api_client",
    "runtime_dashboard_api_types",
    "public_surface_inventory",
    "policy_design_case_inventory",
}
REQUIRED_SURFACES = {
    "policy_design_case_generated_audit_surfaces_section",
    "layer3_public_export_projection_refs",
    "runtime_api_dashboard_public_export_routes",
}
REQUIRED_ACCEPTANCE_PHRASES = {
    "producer write-closure",
    "deny-by-default output-root accounting",
    "exactly one generated-artifacts family",
    "missing registered outputs",
    "duplicate family claims",
    "stale_output_behavior",
    "unregistered GY output-root artifacts",
    "may_not_use_for/candidate_only/not_publishable",
}
GY_LIFECYCLE_ALLOWED_CLASSIFICATIONS = {
    "generated_committed",
    "source_committed",
    "surface_out_of_scope",
}
GY_OUTPUT_ROOT_EXTENSIONS = {
    ".json",
    ".md",
    ".toml",
}
GY_SCHEMA_PREFIXES = (
    "policyos.policy_design_case.layer3_gy",
    "layer3_gy",
)
FAMILY_LIFECYCLE_SCHEMA_PREFIX_NAMESPACE = (
    "policyos",
    "policy_design_case",
)
FAMILY_LIFECYCLE_SCHEMA_PREFIX_LAYER3_FLOOR = "layer3_g"
FAMILY_LIFECYCLE_SCHEMA_PREFIX_MIN_SEGMENTS = 3
GY_LIFECYCLE_MARKER_KEY = "gy_lifecycle_marker"
ScanExclusions = tuple[set[str], set[str]]


def _rows_by_id(rows: object, key: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get(key), str):
            out[str(row[key])] = row
    return out


def _list_value(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _expected_file_sets(
    repo_root: Path,
    lifecycle_report: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    if lifecycle_report is None:
        lifecycle_report = validate_gy_lifecycle_registry(repo_root)
    return {
        "paths": list(lifecycle_report.get("discovered_artifacts") or []),
        "producer_declared_outputs": list(
            lifecycle_report.get("producer_declared_outputs") or []
        ),
        "source_committed_outputs": list(
            lifecycle_report.get("source_committed_outputs") or []
        ),
        "output_root_files": list(lifecycle_report.get("output_root_files") or []),
        "unaccounted_output_root_files": list(
            lifecycle_report.get("unaccounted_output_root_files") or []
        ),
        "validators": sorted(
            path.relative_to(repo_root).as_posix()
            for path in (repo_root / "tools" / "quality" / "validation").glob(
                "check_layer3_gy*.py"
            )
            if path.is_file()
        ),
        "validator_tests": sorted(
            path.relative_to(repo_root).as_posix()
            for path in (repo_root / "tests" / "repo_quality" / "tools").glob(
                "test_layer3_gy*.py"
            )
            if path.is_file()
        ),
    }


def validate_gy_lifecycle_registry(repo_root: Path) -> dict[str, Any]:
    """Validate that every committed GY artifact belongs to exactly one family."""

    repo_root = repo_root.resolve()
    generated_path = repo_root / "architecture/generated_artifacts.toml"
    if not generated_path.is_file():
        return {
            "status": "fail",
            "issues": [{"code": "generated_artifacts_registry_missing"}],
            "discovered_artifacts": [],
            "registered_artifacts": [],
            "registered_outputs": [],
            "registered_artifact_count": 0,
            "orphan_count": 0,
            "phantom_output_count": 0,
            "duplicate_claim_count": 0,
            "family_ids": [],
        }

    issues: list[dict[str, Any]] = []
    generated = tomllib.loads(generated_path.read_text(encoding="utf-8"))
    marker_scan_exclusions = _marker_scan_exclusions_from_generated(generated, issues)
    families = [
        family for family in generated.get("family", []) if isinstance(family, dict)
    ]
    gy_families = [family for family in families if _is_gy_lifecycle_family(family)]
    producer_outputs_by_family = _producer_declared_gy_outputs(
        repo_root,
        gy_families,
        issues,
        scope_exclusions=marker_scan_exclusions,
    )
    producer_declared_outputs = {
        output
        for outputs in producer_outputs_by_family.values()
        for output in outputs
    }
    source_committed_outputs = {
        str(output)
        for family in gy_families
        if family.get("lifecycle") == "source_committed"
        for output in family.get("outputs") or []
    }
    marker_detected_outputs = set(
        _iter_gy_marked_artifact_files(repo_root, marker_scan_exclusions)
    )
    discovered = sorted(
        producer_declared_outputs | source_committed_outputs | marker_detected_outputs
    )
    output_root_directories = _derive_gy_output_root_directories(
        repo_root,
        gy_families,
        producer_declared_outputs,
        source_committed_outputs,
    )
    raw_output_root_files = set(
        _iter_contract_derived_output_root_files(
            repo_root,
            output_root_directories,
            marker_scan_exclusions,
        )
    )
    owned_non_gy_allowlist = _owned_non_gy_allowlist(
        repo_root,
        gy_paths=producer_declared_outputs | source_committed_outputs | marker_detected_outputs,
        issues=issues,
        scope_exclusions=marker_scan_exclusions,
    )
    output_root_files = raw_output_root_files - owned_non_gy_allowlist
    accounted_output_root_files = producer_declared_outputs | source_committed_outputs
    for output in sorted(accounted_output_root_files):
        if output not in raw_output_root_files:
            issues.append(
                {
                    "code": "layer3_gy_accounted_output_outside_output_root",
                    "path": output,
                }
            )
    for output in sorted(output_root_files - accounted_output_root_files):
        issues.append(
            {
                "code": "layer3_gy_unaccounted_output_root_file",
                "path": output,
            }
        )
        issues.append(
            {
                "code": "layer3_gy_artifact_not_registered",
                "path": output,
            }
        )
    output_claims: dict[str, list[str]] = {}
    family_ids: set[str] = set()

    for family in gy_families:
        family_id = str(family.get("id") or "")
        gy_outputs = [str(output) for output in family.get("outputs") or []]
        if not gy_outputs:
            continue
        family_ids.add(family_id)
        _validate_gy_family_metadata(family, issues)
        family_declared_outputs = producer_outputs_by_family.get(family_id, set())
        lifecycle = str(family.get("lifecycle") or "")
        seen_outputs: set[str] = set()
        for output in gy_outputs:
            if output in seen_outputs:
                issues.append(
                    {
                        "code": "layer3_gy_family_output_listed_more_than_once",
                        "path": output,
                        "family_id": family_id,
                    }
                )
            seen_outputs.add(output)
            output_claims.setdefault(output, []).append(family_id)
            if not (repo_root / output).exists():
                issues.append(
                    {
                        "code": "layer3_gy_registered_output_missing",
                        "path": output,
                        "family_id": family_id,
                    }
                )
            if lifecycle == "generated_committed":
                if output not in family_declared_outputs:
                    issues.append(
                        {
                            "code": "layer3_gy_registered_output_not_declared_by_producer",
                            "path": output,
                            "family_id": family_id,
                        }
                    )
        if lifecycle == "generated_committed":
            family_registered_outputs = set(gy_outputs)
            for output in sorted(family_declared_outputs - family_registered_outputs):
                issues.append(
                    {
                        "code": "layer3_gy_producer_output_not_registered",
                        "path": output,
                        "family_id": family_id,
                    }
                )
            for output in sorted(family_declared_outputs):
                if not (repo_root / output).is_file():
                    issues.append(
                        {
                            "code": "layer3_gy_producer_output_missing",
                            "path": output,
                            "family_id": family_id,
                        }
                    )
                _validate_producer_output_provenance(repo_root, family, output, issues)
        if lifecycle == "source_committed":
            _validate_source_integrity(repo_root, family, gy_outputs, issues)

    orphan_count = 0
    duplicate_claim_count = 0
    for artifact_path in discovered:
        claiming_families = sorted(set(output_claims.get(artifact_path, [])))
        if not claiming_families:
            orphan_count += 1
            issues.append(
                {
                    "code": "layer3_gy_artifact_not_registered",
                    "path": artifact_path,
                }
            )
        elif len(claiming_families) > 1:
            duplicate_claim_count += 1
            issues.append(
                {
                    "code": "layer3_gy_artifact_registered_multiple_families",
                    "path": artifact_path,
                    "family_ids": ",".join(claiming_families),
                }
            )

    phantom_output_count = sum(1 for output in output_claims if not (repo_root / output).exists())
    registered_artifacts = sorted(
        path
        for path in discovered
        if len(set(output_claims.get(path, []))) == 1 and (repo_root / path).is_file()
    )
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "discovered_artifacts": discovered,
        "producer_declared_outputs": sorted(producer_declared_outputs),
        "source_committed_outputs": sorted(source_committed_outputs),
        "marker_detected_outputs": sorted(marker_detected_outputs),
        "marker_scan_excluded_paths": sorted(marker_scan_exclusions[0]),
        "marker_scan_excluded_directories": sorted(marker_scan_exclusions[1]),
        "output_root_files": sorted(output_root_files),
        "unaccounted_output_root_files": sorted(output_root_files - accounted_output_root_files),
        "registered_artifacts": registered_artifacts,
        "registered_outputs": sorted(output_claims),
        "registered_artifact_count": len(registered_artifacts),
        "orphan_count": orphan_count,
        "phantom_output_count": phantom_output_count,
        "duplicate_claim_count": duplicate_claim_count,
        "family_ids": sorted(family_ids),
    }


def _is_gy_lifecycle_family(family: dict[str, Any]) -> bool:
    return family.get("gy_lifecycle_family") is True


def _validate_gy_family_metadata(
    family: dict[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    family_id = str(family.get("id") or "")
    for field in ("id", "owner"):
        if not str(family.get(field) or "").strip():
            issues.append(
                {
                    "code": "layer3_gy_family_lifecycle_metadata_missing",
                    "family_id": family_id,
                    "field": field,
                }
            )
    lifecycle = str(family.get("lifecycle") or "")
    if lifecycle not in GY_LIFECYCLE_ALLOWED_CLASSIFICATIONS:
        issues.append(
            {
                "code": "layer3_gy_family_bad_lifecycle_classification",
                "family_id": family_id,
                "lifecycle": lifecycle,
            }
        )
    if lifecycle == "surface_out_of_scope":
        rationale = str(family.get("surface_out_of_scope_rationale") or "")
        if not rationale.strip():
            issues.append(
                {
                    "code": "layer3_gy_surface_out_of_scope_rationale_missing",
                    "family_id": family_id,
                }
            )
    if lifecycle == "source_committed":
        if not str(family.get("source_committed_rationale") or "").strip():
            issues.append(
                {
                    "code": "layer3_gy_source_committed_rationale_missing",
                    "family_id": family_id,
                }
            )
        if not isinstance(family.get("source_integrity_sha256"), dict):
            issues.append(
                {
                    "code": "layer3_gy_source_integrity_manifest_missing",
                    "family_id": family_id,
                }
            )
    for field, expected in (
        ("gy_lifecycle_family", True),
        ("stale_output_behavior", "fail"),
        ("drift_gate", "automated"),
    ):
        if family.get(field) != expected:
            issues.append(
                {
                    "code": "layer3_gy_family_lifecycle_metadata_bad_value",
                    "family_id": family_id,
                    "field": field,
                    "expected": expected,
                    "actual": str(family.get(field)),
                }
            )
    _family_lifecycle_schema_prefixes(family, issues)
    if not family.get("regenerate_commands"):
        issues.append({"code": "layer3_gy_regenerate_command_missing", "family_id": family_id})
    if not family.get("check_command"):
        issues.append({"code": "layer3_gy_check_command_missing", "family_id": family_id})


def _discover_gy_artifact_paths(repo_root: Path) -> list[str]:
    generated_path = repo_root / "architecture/generated_artifacts.toml"
    if not generated_path.is_file():
        return []
    generated = tomllib.loads(generated_path.read_text(encoding="utf-8"))
    marker_scan_exclusions = _marker_scan_exclusions_from_generated(generated)
    gy_families = [
        family
        for family in generated.get("family", [])
        if isinstance(family, dict) and _is_gy_lifecycle_family(family)
    ]
    producer_declared_outputs = {
        output
        for outputs in _producer_declared_gy_outputs(
            repo_root,
            gy_families,
            scope_exclusions=marker_scan_exclusions,
        ).values()
        for output in outputs
    }
    source_committed_outputs = {
        str(output)
        for family in gy_families
        if family.get("lifecycle") == "source_committed"
        for output in family.get("outputs") or []
    }
    marker_detected_outputs = set(
        _iter_gy_marked_artifact_files(repo_root, marker_scan_exclusions)
    )
    return sorted(producer_declared_outputs | source_committed_outputs | marker_detected_outputs)


def _derive_gy_output_root_directories(
    repo_root: Path,
    gy_families: list[dict[str, Any]],
    producer_declared_outputs: set[str],
    source_committed_outputs: set[str],
) -> set[str]:
    output_paths = set(producer_declared_outputs) | set(source_committed_outputs)
    for family in gy_families:
        output_paths.update(str(output) for output in family.get("outputs") or [])
    output_paths.update(
        _public_surface_gy_generated_artifact_outputs(
            repo_root,
            gy_family_ids={str(family.get("id") or "") for family in gy_families},
        )
    )
    return {
        Path(output).parent.as_posix()
        for output in output_paths
        if Path(output).parent.as_posix() != "."
    }


def _public_surface_gy_generated_artifact_outputs(
    repo_root: Path,
    *,
    gy_family_ids: set[str],
) -> set[str]:
    contract_path = repo_root / "architecture/public_surface/contract.toml"
    if not contract_path.is_file():
        return set()
    try:
        contract = tomllib.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return set()
    outputs: set[str] = set()
    for family in contract.get("generated_artifact_family", []):
        if not isinstance(family, dict):
            continue
        family_id = str(family.get("id") or "")
        family_outputs = {str(output) for output in family.get("outputs") or []}
        if family_id in gy_family_ids or family_id.startswith("policy-design-case-layer3-gy"):
            outputs.update(family_outputs)
    return outputs


def _iter_contract_derived_output_root_files(
    repo_root: Path,
    output_root_directories: set[str],
    scope_exclusions: ScanExclusions,
) -> list[str]:
    paths: set[str] = set()
    for directory in output_root_directories:
        root = repo_root / directory
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in GY_OUTPUT_ROOT_EXTENSIONS:
                paths.add(path.relative_to(repo_root).as_posix())
    return sorted(
        path
        for path in paths
        if _is_committed_artifact_scope_path(path, scope_exclusions=scope_exclusions)
    )


def _iter_gy_marked_artifact_files(
    repo_root: Path,
    scope_exclusions: ScanExclusions,
) -> list[str]:
    paths: set[str] = set()
    for path in _iter_repo_artifact_candidate_files(repo_root, scope_exclusions):
        if _artifact_has_gy_provenance(path):
            paths.add(path.relative_to(repo_root).as_posix())
    return sorted(paths)


def _iter_repo_artifact_candidate_files(
    repo_root: Path,
    scope_exclusions: ScanExclusions,
) -> list[Path]:
    paths: list[Path] = []
    stack = [repo_root]
    while stack:
        root = stack.pop()
        try:
            children = sorted(root.iterdir(), key=lambda child: child.name)
        except OSError:
            continue
        for child in children:
            relative = child.relative_to(repo_root).as_posix()
            if not _is_committed_artifact_scope_path(
                relative,
                scope_exclusions=scope_exclusions,
            ):
                continue
            if child.is_dir():
                stack.append(child)
            elif child.is_file() and child.suffix.lower() in GY_OUTPUT_ROOT_EXTENSIONS:
                paths.append(child)
    return paths


def _owned_non_gy_allowlist(
    repo_root: Path,
    *,
    gy_paths: set[str],
    issues: list[dict[str, Any]] | None = None,
    scope_exclusions: ScanExclusions,
) -> set[str]:
    allowed: set[str] = set()
    allowed.update(
        _policy_design_case_inventory_non_gy_paths(
            repo_root,
            gy_paths=gy_paths,
            scope_exclusions=scope_exclusions,
        )
    )
    allowed.update(_generated_artifact_non_gy_outputs(repo_root, gy_paths=gy_paths))
    allowed.update(
        _generated_artifact_gy_output_root_allowlist(
            repo_root,
            gy_paths=gy_paths,
            issues=issues,
            scope_exclusions=scope_exclusions,
        )
    )
    allowed.update(_public_surface_contract_non_gy_paths(repo_root, gy_paths=gy_paths))
    return allowed


def _policy_design_case_inventory_non_gy_paths(
    repo_root: Path,
    *,
    gy_paths: set[str],
    scope_exclusions: ScanExclusions,
) -> set[str]:
    inventory_path = repo_root / "architecture/policy_design_case/inventory.json"
    if not inventory_path.is_file():
        return set()
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return set()
    allowed: set[str] = set()
    for path in _collect_policy_design_case_paths(inventory):
        if not path or path in gy_paths:
            continue
        if _is_committed_artifact_scope_path(
            path,
            scope_exclusions=scope_exclusions,
        ) and not _artifact_has_gy_provenance(repo_root / path):
            allowed.add(path)
    return allowed


def _collect_policy_design_case_paths(value: object) -> set[str]:
    paths: set[str] = set()
    if isinstance(value, str):
        if value.startswith("architecture/policy_design_case/"):
            paths.add(value)
        return paths
    if isinstance(value, dict):
        for item in value.values():
            paths.update(_collect_policy_design_case_paths(item))
        return paths
    if isinstance(value, list):
        for item in value:
            paths.update(_collect_policy_design_case_paths(item))
    return paths


def _generated_artifact_non_gy_outputs(repo_root: Path, *, gy_paths: set[str]) -> set[str]:
    generated_path = repo_root / "architecture/generated_artifacts.toml"
    if not generated_path.is_file():
        return set()
    try:
        generated = tomllib.loads(generated_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return set()
    allowed: set[str] = set()
    for family in generated.get("family", []):
        if not isinstance(family, dict) or _is_gy_lifecycle_family(family):
            continue
        for output in family.get("outputs") or []:
            path = str(output)
            if path and path not in gy_paths:
                allowed.add(path)
    return allowed


def _generated_artifact_gy_output_root_allowlist(
    repo_root: Path,
    *,
    gy_paths: set[str],
    issues: list[dict[str, Any]] | None,
    scope_exclusions: ScanExclusions,
) -> set[str]:
    generated_path = repo_root / "architecture/generated_artifacts.toml"
    if not generated_path.is_file():
        return set()
    try:
        generated = tomllib.loads(generated_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return set()
    allowed: set[str] = set()
    for entry in generated.get("gy_output_root_allowlist", []):
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id") or "")
        for field in ("id", "owner", "rationale"):
            if not str(entry.get(field) or "").strip() and issues is not None:
                issues.append(
                    {
                        "code": "layer3_gy_output_root_allowlist_metadata_missing",
                        "entry_id": entry_id,
                        "field": field,
                    }
                )
        paths = {str(path) for path in entry.get("paths") or []}
        directories = {str(directory) for directory in entry.get("directories") or []}
        if not paths and not directories and issues is not None:
            issues.append(
                {
                    "code": "layer3_gy_output_root_allowlist_empty",
                    "entry_id": entry_id,
                }
            )
        for path in sorted(paths):
            if _allowlisted_non_gy_path(
                repo_root,
                path,
                gy_paths=gy_paths,
                issues=issues,
                scope_exclusions=scope_exclusions,
            ):
                allowed.add(path)
        for directory in sorted(directories):
            directory_path = repo_root / directory
            if not directory_path.is_dir():
                if issues is not None:
                    issues.append(
                        {
                            "code": "layer3_gy_output_root_allowlist_directory_missing",
                            "entry_id": entry_id,
                            "path": directory,
                        }
                    )
                continue
            for path in directory_path.rglob("*"):
                if not path.is_file() or path.suffix not in GY_OUTPUT_ROOT_EXTENSIONS:
                    continue
                relative = path.relative_to(repo_root).as_posix()
                if _allowlisted_non_gy_path(
                    repo_root,
                    relative,
                    gy_paths=gy_paths,
                    issues=issues,
                    scope_exclusions=scope_exclusions,
                ):
                    allowed.add(relative)
    return allowed


def _allowlisted_non_gy_path(
    repo_root: Path,
    path: str,
    *,
    gy_paths: set[str],
    issues: list[dict[str, Any]] | None,
    scope_exclusions: ScanExclusions,
) -> bool:
    if not _is_committed_artifact_scope_path(
        path,
        scope_exclusions=scope_exclusions,
    ):
        return False
    artifact = repo_root / path
    if not artifact.is_file():
        if issues is not None:
            issues.append(
                {
                    "code": "layer3_gy_output_root_allowlist_file_missing",
                    "path": path,
                }
            )
        return False
    if path in gy_paths or _artifact_has_gy_provenance(artifact):
        if issues is not None:
            issues.append(
                {
                    "code": "layer3_gy_output_root_allowlist_claims_gy_artifact",
                    "path": path,
                }
            )
        return False
    return True


def _public_surface_contract_non_gy_paths(
    repo_root: Path,
    *,
    gy_paths: set[str],
) -> set[str]:
    contract_path = repo_root / "architecture/public_surface/contract.toml"
    if not contract_path.is_file():
        return set()
    try:
        contract = tomllib.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return set()
    allowed: set[str] = {
        "architecture/public_surface/contract.toml",
    }
    public_surface = contract.get("public_surface")
    if isinstance(public_surface, dict):
        for field in ("inventory", "last_mile_shim_caller_report"):
            value = str(public_surface.get(field) or "")
            if value:
                allowed.add(value)
    for package in contract.get("package", []):
        if not isinstance(package, dict):
            continue
        for field in ("readme", "reference_doc"):
            value = str(package.get(field) or "")
            if value:
                allowed.add(value)
    return {path for path in allowed if path not in gy_paths}


def _load_marker_scan_exclusions(
    repo_root: Path,
    issues: list[dict[str, Any]] | None = None,
) -> ScanExclusions:
    generated_path = repo_root / "architecture/generated_artifacts.toml"
    if not generated_path.is_file():
        return set(), set()
    try:
        generated = tomllib.loads(generated_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return set(), set()
    return _marker_scan_exclusions_from_generated(generated, issues)


def _marker_scan_exclusions_from_generated(
    generated: dict[str, Any],
    issues: list[dict[str, Any]] | None = None,
) -> ScanExclusions:
    excluded_paths: set[str] = set()
    excluded_directories: set[str] = set()
    for entry in generated.get("gy_marker_scan_exclusion", []):
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id") or "")
        for field in ("id", "owner", "rationale"):
            if not str(entry.get(field) or "").strip() and issues is not None:
                issues.append(
                    {
                        "code": "layer3_gy_marker_scan_exclusion_metadata_missing",
                        "entry_id": entry_id,
                        "field": field,
                    }
                )
        raw_paths = entry.get("paths") or []
        raw_directories = entry.get("directories") or []
        paths = _normalize_exclusion_values(
            raw_paths,
            entry_id=entry_id,
            field="paths",
            issues=issues,
        )
        directories = _normalize_exclusion_values(
            raw_directories,
            entry_id=entry_id,
            field="directories",
            issues=issues,
        )
        if not paths and not directories and issues is not None:
            issues.append(
                {
                    "code": "layer3_gy_marker_scan_exclusion_empty",
                    "entry_id": entry_id,
                }
            )
        excluded_paths.update(paths)
        excluded_directories.update(directories)
    return excluded_paths, excluded_directories


def _normalize_exclusion_values(
    values: object,
    *,
    entry_id: str,
    field: str,
    issues: list[dict[str, Any]] | None,
) -> set[str]:
    if not isinstance(values, list):
        if issues is not None:
            issues.append(
                {
                    "code": "layer3_gy_marker_scan_exclusion_bad_type",
                    "entry_id": entry_id,
                    "field": field,
                }
            )
        return set()
    normalized: set[str] = set()
    for value in values:
        path = _normalize_repo_relative_path(str(value))
        if not path:
            if issues is not None:
                issues.append(
                    {
                        "code": "layer3_gy_marker_scan_exclusion_bad_path",
                        "entry_id": entry_id,
                        "field": field,
                        "path": str(value),
                    }
                )
            continue
        normalized.add(path)
    return normalized


def _normalize_repo_relative_path(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.strip("/")
    if not normalized:
        return ""
    if normalized == "." or normalized.startswith("../") or "/../" in normalized:
        return ""
    if Path(normalized).is_absolute():
        return ""
    return normalized


def _path_is_marker_scan_excluded(
    relative: str,
    scope_exclusions: ScanExclusions,
) -> bool:
    excluded_paths, excluded_directories = scope_exclusions
    if relative in excluded_paths:
        return True
    return any(
        relative == directory or relative.startswith(f"{directory}/")
        for directory in excluded_directories
    )


def _is_committed_artifact_scope_path(
    relative: str,
    *,
    scope_exclusions: ScanExclusions,
) -> bool:
    normalized = _normalize_repo_relative_path(relative)
    if not normalized:
        return False
    if _path_is_marker_scan_excluded(normalized, scope_exclusions):
        return False
    return True


def _artifact_has_gy_provenance(
    path: Path,
    *,
    schema_prefixes: Sequence[str] = GY_SCHEMA_PREFIXES,
) -> bool:
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return False
        return _contains_gy_provenance(payload, schema_prefixes=schema_prefixes)
    if suffix == ".md":
        return _markdown_has_gy_lifecycle_marker(path)
    if suffix == ".toml":
        return _toml_has_gy_lifecycle_marker(path)
    return False


def _contains_gy_provenance(
    value: object,
    *,
    schema_prefixes: Sequence[str] = GY_SCHEMA_PREFIXES,
) -> bool:
    return _contains_gy_provenance_field(
        value,
        provenance_field=False,
        schema_prefixes=schema_prefixes,
    )


def _contains_gy_provenance_field(
    value: object,
    *,
    provenance_field: bool,
    schema_prefixes: Sequence[str],
) -> bool:
    if isinstance(value, str):
        return provenance_field and _is_lifecycle_marker_value(value, schema_prefixes)
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if key_text in {
                "schema_version",
                "rule_version",
                "producer",
                "generator",
                "proof_source",
                "benchmark_id",
            } and _contains_gy_provenance_field(
                item,
                provenance_field=True,
                schema_prefixes=schema_prefixes,
            ):
                return True
            if _contains_gy_provenance_field(
                item,
                provenance_field=False,
                schema_prefixes=schema_prefixes,
            ):
                return True
    if isinstance(value, list):
        return any(
            _contains_gy_provenance_field(
                item,
                provenance_field=provenance_field,
                schema_prefixes=schema_prefixes,
            )
            for item in value
        )
    return False


def _markdown_has_gy_lifecycle_marker(path: Path) -> bool:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return False
    if not lines or lines[0].strip() != "---":
        return False
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            return False
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, value = stripped.partition(":")
        if separator and key.strip() == GY_LIFECYCLE_MARKER_KEY:
            return _is_gy_marker_value(value.strip().strip("'\""))
    return False


def _toml_has_gy_lifecycle_marker(path: Path) -> bool:
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError):
        return False
    marker = payload.get(GY_LIFECYCLE_MARKER_KEY)
    return isinstance(marker, str) and _is_gy_marker_value(marker)


def _is_gy_marker_value(value: str) -> bool:
    return _is_lifecycle_marker_value(value, GY_SCHEMA_PREFIXES)


def _is_lifecycle_marker_value(value: str, schema_prefixes: Sequence[str]) -> bool:
    return any(value.startswith(prefix) for prefix in schema_prefixes)


def _producer_declared_gy_outputs(
    repo_root: Path,
    gy_families: list[dict[str, Any]],
    issues: list[dict[str, Any]] | None = None,
    *,
    scope_exclusions: ScanExclusions | None = None,
) -> dict[str, set[str]]:
    if scope_exclusions is None:
        scope_exclusions = _load_marker_scan_exclusions(repo_root, issues)
    outputs_by_family: dict[str, set[str]] = {}
    for family in gy_families:
        if family.get("lifecycle") != "generated_committed":
            continue
        family_id = str(family.get("id") or "")
        workflow = str(family.get("workflow") or "")
        if not workflow:
            if issues is not None:
                issues.append(
                    {
                        "code": "layer3_gy_producer_workflow_missing",
                        "family_id": family_id,
                    }
                )
            continue
        workflow_path = repo_root / workflow
        if not workflow_path.is_file():
            if issues is not None:
                issues.append(
                    {
                        "code": "layer3_gy_producer_workflow_missing",
                        "family_id": family_id,
                        "workflow": workflow,
                    }
                )
            continue
        declared = _load_producer_declared_outputs(
            repo_root,
            workflow_path,
            family_id,
            workflow,
            issues,
            scope_exclusions=scope_exclusions,
        )
        outputs_by_family[family_id] = declared
    return outputs_by_family


def _load_producer_declared_outputs(
    repo_root: Path,
    workflow_path: Path,
    family_id: str,
    workflow: str,
    issues: list[dict[str, Any]] | None,
    *,
    scope_exclusions: ScanExclusions,
) -> set[str]:
    module_name = (
        "_policyos_gy_declared_outputs_"
        + hashlib.sha256(str(workflow_path).encode("utf-8")).hexdigest()
    )
    spec = importlib.util.spec_from_file_location(module_name, workflow_path)
    if spec is None or spec.loader is None:
        if issues is not None:
            issues.append(
                {
                    "code": "layer3_gy_producer_declared_outputs_unloadable",
                    "family_id": family_id,
                    "workflow": workflow,
                }
            )
        return set()
    module = importlib.util.module_from_spec(spec)
    inserted_paths = _ensure_repo_import_paths(repo_root)
    previous_module = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover - exercised by malformed probe modules.
        if issues is not None:
            issues.append(
                {
                    "code": "layer3_gy_producer_declared_outputs_unloadable",
                    "family_id": family_id,
                    "workflow": workflow,
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            )
        return set()
    finally:
        if previous_module is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous_module
        for path in reversed(inserted_paths):
            with contextlib.suppress(ValueError):
                sys.path.remove(path)

    declared_outputs = getattr(module, "declared_outputs", None)
    if not callable(declared_outputs):
        if issues is not None:
            issues.append(
                {
                    "code": "layer3_gy_producer_declared_outputs_missing",
                    "family_id": family_id,
                    "workflow": workflow,
                }
            )
        return set()
    try:
        raw_outputs = declared_outputs()
    except Exception as exc:  # pragma: no cover - exercised by malformed probe modules.
        if issues is not None:
            issues.append(
                {
                    "code": "layer3_gy_producer_declared_outputs_failed",
                    "family_id": family_id,
                    "workflow": workflow,
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            )
        return set()
    if not isinstance(raw_outputs, (list, tuple, set)):
        if issues is not None:
            issues.append(
                {
                    "code": "layer3_gy_producer_declared_outputs_bad_type",
                    "family_id": family_id,
                    "workflow": workflow,
                }
            )
        return set()
    outputs: set[str] = set()
    for item in raw_outputs:
        output = str(item).replace("\\", "/")
        if not _is_committed_artifact_scope_path(
            output,
            scope_exclusions=scope_exclusions,
        ):
            if issues is not None:
                issues.append(
                    {
                        "code": "layer3_gy_producer_declared_output_bad_path",
                        "family_id": family_id,
                        "workflow": workflow,
                        "path": output,
                    }
                )
            continue
        outputs.add(output)
    return outputs


def _ensure_repo_import_paths(repo_root: Path) -> list[str]:
    inserted: list[str] = []
    for path in (repo_root, repo_root / "src"):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)
            inserted.append(value)
    return inserted


def _validate_producer_output_provenance(
    repo_root: Path,
    family: dict[str, Any],
    output: str,
    issues: list[dict[str, Any]],
) -> None:
    family_id = str(family.get("id") or "")
    path = repo_root / output
    if not path.exists():
        return
    if not _artifact_has_gy_provenance(
        path,
        schema_prefixes=_family_lifecycle_schema_prefixes(family),
    ):
        issues.append(
            {
                "code": "layer3_gy_producer_output_provenance_missing",
                "family_id": family_id,
                "path": output,
            }
        )


def _family_lifecycle_schema_prefixes(
    family: dict[str, Any],
    issues: list[dict[str, Any]] | None = None,
) -> tuple[str, ...]:
    family_id = str(family.get("id") or "")
    raw_prefixes = family.get("lifecycle_schema_prefixes")
    if raw_prefixes is None:
        return GY_SCHEMA_PREFIXES
    if not isinstance(raw_prefixes, list):
        if issues is not None:
            issues.append(
                {
                    "code": "layer3_gy_family_lifecycle_schema_prefixes_bad_type",
                    "family_id": family_id,
                }
            )
        return ()
    prefixes: list[str] = []
    for raw_prefix in raw_prefixes:
        prefix = str(raw_prefix).strip()
        if not _is_bounded_family_lifecycle_schema_prefix(prefix):
            if issues is not None:
                issues.append(
                    {
                        "code": "layer3_gy_family_lifecycle_schema_prefix_unbounded",
                        "family_id": family_id,
                        "prefix": prefix,
                    }
                )
            continue
        prefixes.append(prefix)
    return tuple(dict.fromkeys(prefixes))


def _is_bounded_family_lifecycle_schema_prefix(prefix: str) -> bool:
    if not prefix or prefix.endswith(".") or ".." in prefix:
        return False
    segments = prefix.split(".")
    if len(segments) < FAMILY_LIFECYCLE_SCHEMA_PREFIX_MIN_SEGMENTS:
        return False
    namespace = tuple(segments[: len(FAMILY_LIFECYCLE_SCHEMA_PREFIX_NAMESPACE)])
    if namespace != FAMILY_LIFECYCLE_SCHEMA_PREFIX_NAMESPACE:
        return False
    layer3_segment = segments[len(FAMILY_LIFECYCLE_SCHEMA_PREFIX_NAMESPACE)]
    return (
        layer3_segment.startswith(FAMILY_LIFECYCLE_SCHEMA_PREFIX_LAYER3_FLOOR)
        and layer3_segment != FAMILY_LIFECYCLE_SCHEMA_PREFIX_LAYER3_FLOOR
    )


def _validate_source_integrity(
    repo_root: Path,
    family: dict[str, Any],
    outputs: list[str],
    issues: list[dict[str, Any]],
) -> None:
    family_id = str(family.get("id") or "")
    integrity = family.get("source_integrity_sha256")
    if not isinstance(integrity, dict):
        return
    for output in outputs:
        expected = str(integrity.get(output) or "")
        if not expected:
            issues.append(
                {
                    "code": "layer3_gy_source_integrity_digest_missing",
                    "family_id": family_id,
                    "path": output,
                }
            )
            continue
        path = repo_root / output
        if not path.is_file():
            issues.append(
                {
                    "code": "layer3_gy_source_output_missing",
                    "family_id": family_id,
                    "path": output,
                }
            )
            continue
        actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            issues.append(
                {
                    "code": "layer3_gy_source_output_integrity_drift",
                    "family_id": family_id,
                    "path": output,
                    "expected": expected,
                    "actual": actual,
                }
            )


def _load_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _lifecycle_facts(
    repo_root: Path,
    lifecycle_report: dict[str, Any],
) -> dict[str, Any]:
    generated = _load_toml(repo_root / "architecture/generated_artifacts.toml")
    families = [family for family in generated.get("family", []) if isinstance(family, dict)]
    layer3_families = [
        family
        for family in families
        if str(family.get("id") or "").startswith("policy-design-case-layer3-")
    ]
    gx_family_ids = {
        str(family.get("id") or "")
        for family in layer3_families
        if str(family.get("id") or "").startswith("policy-design-case-layer3-gx-")
    }
    gy_family_ids = set(lifecycle_report.get("family_ids") or [])
    gy_paths = set(lifecycle_report.get("discovered_artifacts") or []) | set(
        lifecycle_report.get("registered_outputs") or []
    )
    pdc_inventory = _load_json(repo_root / "architecture/policy_design_case/inventory.json")
    pdc_artifacts = [
        artifact
        for artifact in pdc_inventory.get("artifacts", [])
        if isinstance(artifact, dict)
    ]
    pdc_gy_entries = [
        artifact
        for artifact in pdc_artifacts
        if str(artifact.get("path") or "") in gy_paths
    ]
    public_surface = _load_toml(repo_root / "architecture/public_surface/contract.toml")
    public_generated_families = [
        family
        for family in public_surface.get("generated_artifact_family", [])
        if isinstance(family, dict)
    ]
    return {
        "generated_artifact_family_count": len(families),
        "registered_layer3_family_count": len(layer3_families),
        "registered_layer3_family_ids": sorted(
            str(family.get("id") or "") for family in layer3_families
        ),
        "registered_layer3_output_count": sum(
            len(family.get("outputs") or []) for family in layer3_families
        ),
        "gx_generated_family_registered": bool(gx_family_ids),
        "gy_generated_family_registered": bool(gy_family_ids),
        "gy_generated_family_ids": sorted(gy_family_ids),
        "gy_artifact_files_detected": len(lifecycle_report["discovered_artifacts"]),
        "gy_artifact_files_registered_count": lifecycle_report["registered_artifact_count"],
        "gy_producer_declared_output_count": len(
            lifecycle_report["producer_declared_outputs"]
        ),
        "gy_source_committed_output_count": len(lifecycle_report["source_committed_outputs"]),
        "gy_output_root_file_count": len(lifecycle_report["output_root_files"]),
        "gy_unaccounted_output_root_count": len(
            lifecycle_report["unaccounted_output_root_files"]
        ),
        "gy_lifecycle_orphan_count": lifecycle_report["orphan_count"],
        "gy_lifecycle_phantom_output_count": lifecycle_report["phantom_output_count"],
        "gy_lifecycle_duplicate_claim_count": lifecycle_report["duplicate_claim_count"],
        "policy_design_case_inventory_artifact_count": len(pdc_artifacts),
        "policy_design_case_inventory_gy_entries": len(pdc_gy_entries),
        "policy_design_case_inventory_registered_in_generated_artifacts": False,
        "public_surface_generated_artifact_family_count": len(public_generated_families),
        "gy_public_surface_family_registered": any(
            str(family.get("id") or "") in gy_family_ids
            for family in public_generated_families
        ),
    }


def validate(
    audit: dict[str, Any],
    *,
    repo_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Return audit integrity violations."""
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[3]
    repo_root = repo_root.resolve()
    violations: list[dict[str, Any]] = []
    lifecycle_report = validate_gy_lifecycle_registry(repo_root)
    violations.extend(lifecycle_report["issues"])
    facts = _lifecycle_facts(repo_root, lifecycle_report)

    if audit.get("schema_version") != "layer3_gy_generated_public_lifecycle_audit.v1":
        violations.append({"code": "bad_schema_version", "detail": audit.get("schema_version")})

    methodology = audit.get("methodology")
    if not isinstance(methodology, dict):
        violations.append({"code": "missing_methodology", "detail": "methodology missing"})
        methodology = {}
    expected_methodology = {
        "agents_used": False,
        "network_fetches_run": False,
        "runtime_server_started": False,
        "parsed_generated_artifacts_toml": True,
        "parsed_public_surface_contract": True,
        "parsed_public_surface_markdown": True,
        "parsed_policy_design_case_inventory": True,
        "parsed_runtime_openapi_snapshot": True,
        "filesystem_gy_artifact_inventory": True,
        "runtime_route_execution_reused_from_runtime_surface_audit": True,
    }
    for key, expected in expected_methodology.items():
        if methodology.get(key) != expected:
            violations.append({
                "code": "methodology_drift",
                "detail": f"{key}={methodology.get(key)!r}; expected {expected!r}",
            })
    if methodology.get("probe_type") != "source_registry_class_invariant_audit":
        violations.append({"code": "probe_type_drift", "detail": methodology.get("probe_type")})

    classification = audit.get("classification")
    if not isinstance(classification, dict):
        violations.append({"code": "missing_classification", "detail": "classification missing"})
        classification = {}
    expected_classification = {
        "primary": "gy_artifact_lifecycle_registered_and_class_gate_enforced",
        "gap_class": "closed",
        "capability_label": "gy_generated_artifact_lifecycle_class_invariant_complete",
        "route_pinned": True,
        "repair_before_downstream_governance": True,
    }
    for key, expected in expected_classification.items():
        if classification.get(key) != expected:
            violations.append({
                "code": "classification_drift",
                "detail": f"{key}={classification.get(key)!r}; expected {expected!r}",
            })
    patterns = set(_list_value(classification.get("patterns")))
    if not patterns >= REQUIRED_PATTERNS:
        violations.append({"code": "pattern_coverage_drift", "detail": sorted(patterns)})

    summary = audit.get("summary")
    if not isinstance(summary, dict):
        violations.append({"code": "missing_summary", "detail": "summary missing"})
        summary = {}
    expected_files = _expected_file_sets(repo_root, lifecycle_report)
    expected_summary = {
        "generated_artifact_family_count": facts["generated_artifact_family_count"],
        "registered_layer3_family_count": facts["registered_layer3_family_count"],
        "registered_layer3_output_count": facts["registered_layer3_output_count"],
        "gx_generated_family_registered": facts["gx_generated_family_registered"],
        "gy_generated_family_registered": facts["gy_generated_family_registered"],
        "gy_artifact_files_detected": facts["gy_artifact_files_detected"],
        "gy_artifact_files_registered_count": facts["gy_artifact_files_registered_count"],
        "gy_producer_declared_output_count": facts["gy_producer_declared_output_count"],
        "gy_source_committed_output_count": facts["gy_source_committed_output_count"],
        "gy_output_root_file_count": facts["gy_output_root_file_count"],
        "gy_unaccounted_output_root_count": facts["gy_unaccounted_output_root_count"],
        "gy_lifecycle_orphan_count": facts["gy_lifecycle_orphan_count"],
        "gy_lifecycle_phantom_output_count": facts["gy_lifecycle_phantom_output_count"],
        "gy_lifecycle_duplicate_claim_count": facts["gy_lifecycle_duplicate_claim_count"],
        "gy_validators_detected": len(expected_files["validators"]),
        "gy_validator_tests_detected": len(expected_files["validator_tests"]),
        "runtime_openapi_family_registered": True,
        "runtime_api_client_family_registered": True,
        "runtime_dashboard_api_types_family_registered": True,
        "public_surface_inventory_family_registered": True,
        "policy_design_case_inventory_artifact_count": (
            facts["policy_design_case_inventory_artifact_count"]
        ),
        "policy_design_case_inventory_gy_entries": facts[
            "policy_design_case_inventory_gy_entries"
        ],
        "policy_design_case_inventory_registered_in_generated_artifacts": facts[
            "policy_design_case_inventory_registered_in_generated_artifacts"
        ],
        "public_surface_generated_artifact_family_count": facts[
            "public_surface_generated_artifact_family_count"
        ],
        "gy_public_surface_family_registered": facts["gy_public_surface_family_registered"],
        "policy_design_case_public_surface_section_hardcoded_in_renderer": True,
        "policy_design_case_public_surface_section_registered_surface_count": 8,
        "layer3_public_export_projection_ref_family_count": 8,
        "runtime_openapi_interesting_surface_route_count": 41,
        "openapi_policy_design_case_projection_has_authority_boundary_fields": True,
        "dashboard_validators_model_runtime_vs_projection_authority": True,
        "overall_status": "gy_lifecycle_registered_and_class_gate_enforced",
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            violations.append({
                "code": "summary_semantics_drift",
                "detail": f"{key}={summary.get(key)!r}; expected {expected!r}",
            })

    rows = _rows_by_id(audit.get("lifecycle_matrix"), "row_id")
    missing_rows = sorted(REQUIRED_ROWS - set(rows))
    if missing_rows:
        violations.append({"code": "missing_lifecycle_rows", "detail": missing_rows})

    for row_id in (
        "layer3_g1_to_g8_and_gl",
        "layer3_gx_hardening",
        "layer3_gy_task0_audit_artifacts",
        "runtime_openapi_snapshot",
        "runtime_api_client",
        "runtime_dashboard_api_types",
        "public_surface_inventory",
    ):
        row = rows.get(row_id, {})
        if row.get("registered") is not True:
            violations.append({"code": "registered_family_marked_unregistered", "detail": row_id})
        for field in ("source_of_truth", "verifier", "stale_output_behavior"):
            if not str(row.get(field, "")).strip() or row.get(field) == "missing_registry":
                violations.append({
                    "code": "registered_family_missing_lifecycle_metadata",
                    "detail": f"{row_id}.{field}",
                })
        if int(row.get("outputs_registered_count") or 0) <= 0:
            violations.append({
                "code": "registered_family_missing_outputs",
                "detail": row_id,
            })

    gy_row = rows.get("layer3_gy_task0_audit_artifacts", {})
    if gy_row.get("registered") is not True:
        violations.append({"code": "gy_family_registration_drift", "detail": gy_row})
    if gy_row.get("family_id") != "policy-design-case-layer3-gy-task0-audit-artifacts":
        violations.append({"code": "gy_family_id_drift", "detail": gy_row.get("family_id")})
    if gy_row.get("outputs_registered_count") != facts["gy_artifact_files_registered_count"]:
        violations.append({
            "code": "gy_registered_output_count_drift",
            "detail": gy_row.get("outputs_registered_count"),
        })
    if gy_row.get("stale_output_behavior") != "fail":
        violations.append({
            "code": "gy_stale_policy_drift",
            "detail": gy_row.get("stale_output_behavior"),
        })
    if "registered_source_committed" not in str(gy_row.get("authority_boundary_status", "")):
        violations.append({
            "code": "gy_authority_boundary_drift",
            "detail": gy_row.get("authority_boundary_status"),
        })

    pdc_row = rows.get("policy_design_case_inventory", {})
    if pdc_row.get("registered") is not False:
        violations.append({"code": "pdc_inventory_registration_greenwash", "detail": pdc_row})
    if pdc_row.get("contains_gy_entries") is not True:
        violations.append({"code": "pdc_inventory_gy_entry_missing", "detail": pdc_row})
    if pdc_row.get("artifact_count") != facts["policy_design_case_inventory_artifact_count"]:
        violations.append({
            "code": "pdc_inventory_artifact_count_drift",
            "detail": pdc_row.get("artifact_count"),
        })

    surfaces = _rows_by_id(audit.get("public_surface_lifecycle"), "surface_id")
    missing_surfaces = sorted(REQUIRED_SURFACES - set(surfaces))
    if missing_surfaces:
        violations.append({"code": "missing_public_surface_rows", "detail": missing_surfaces})

    pdc_surface = surfaces.get("policy_design_case_generated_audit_surfaces_section", {})
    if pdc_surface.get("gy_surface_registered") is not True:
        violations.append({"code": "gy_public_surface_registration_drift", "detail": pdc_surface})
    if pdc_surface.get("derivation_model") != (
        "hardcoded renderer prose, not derived from policy_design_case/inventory.json"
    ):
        violations.append({"code": "pdc_surface_derivation_drift", "detail": pdc_surface})

    projection_surface = surfaces.get("layer3_public_export_projection_refs", {})
    if projection_surface.get("api_dashboard_enforcement") is not False:
        violations.append({
            "code": "projection_refs_api_enforcement_laundering",
            "detail": projection_surface,
        })
    if projection_surface.get("public_export_route_registered") is not False:
        violations.append({
            "code": "projection_refs_public_export_laundering",
            "detail": projection_surface,
        })

    inventory = audit.get("gy_artifact_inventory")
    if not isinstance(inventory, dict):
        violations.append({"code": "missing_gy_artifact_inventory", "detail": "missing"})
        inventory = {}
    for key, expected in expected_files.items():
        actual = _list_value(inventory.get(key))
        if actual != expected:
            violations.append({
                "code": "gy_detected_artifact_list_drift",
                "detail": {"key": key, "actual": actual, "expected": expected},
            })
    if inventory.get("registered_output_count") != facts["gy_artifact_files_registered_count"]:
        violations.append({
            "code": "gy_inventory_registered_output_count_drift",
            "detail": inventory.get("registered_output_count"),
        })

    negatives = _rows_by_id(audit.get("negative_assertions"), "id")
    missing_negatives = sorted(REQUIRED_NEGATIVES - set(negatives))
    if missing_negatives:
        violations.append({"code": "missing_negative_assertions", "detail": missing_negatives})
    for negative_id in REQUIRED_NEGATIVES & set(negatives):
        if negatives[negative_id].get("assertion_holds") is not True:
            violations.append({
                "code": "negative_assertion_not_enforced",
                "detail": negative_id,
            })

    acceptance = _list_value(audit.get("acceptance_signal"))
    acceptance_text = "\n".join(acceptance)
    for phrase in REQUIRED_ACCEPTANCE_PHRASES:
        if phrase not in acceptance_text:
            violations.append({"code": "missing_acceptance_guardrail", "detail": phrase})

    return violations


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="Repository root containing architecture/ and docs/.",
    )
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--check", action="store_true", help="Run fail-closed validation.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    violations = validate(_load(args.audit), repo_root=args.repo_root)
    report = {
        "status": "pass" if not violations else "fail",
        "violation_count": len(violations),
        "violations": violations,
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif violations:
        print("FAIL layer3_gy_generated_public_lifecycle_audit")
        for violation in violations:
            detail = violation.get("detail", violation)
            print(f"- {violation['code']}: {detail}")
    else:
        print("PASS layer3_gy_generated_public_lifecycle_audit")
    return 0 if not violations else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(
        run_timed_entrypoint(
            main,
            script_path=__file__,
            argv=sys.argv[1:],
            started_perf_counter=_TIMING_STARTED_AT,
        )
    )
