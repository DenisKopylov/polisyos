#!/usr/bin/env python3
"""Generate the Fabric best-in-class baseline inventory.

The inventory is intentionally read-only: it inspects repository files, emits a
machine-readable manifest, and renders the matching reference page. Phase 0 is
report-only, so ``--check`` only detects artifact drift and malformed accepted
risk records; it does not fail on ``missing`` or ``partial`` surfaces.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from tools._lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.fabric.io.atomic import atomic_write_text  # noqa: E402

SCHEMA_VERSION = "fabric.best_in_class_manifest.v1"
GENERATED_AT = "2026-04-26T00:00:00Z"
PHASE = 0
OWNER = "@fabric-owners"

STATUS_VALUES = (
    "implemented",
    "partial",
    "missing",
    "not_applicable",
    "accepted_risk",
    "blocked_by_research",
)
PRIORITY_VALUES = ("P0", "P1", "P2", "P3")
PLANES = ("source", "evidence", "semantics", "world", "trust")

DEFAULT_MANIFEST = (
    REPO_ROOT / "tools" / "quality" / "validation" / "fabric_best_in_class_manifest.json"
)
DEFAULT_REPORT = REPO_ROOT / "docs" / "reference" / "fabric" / "best-in-class-inventory.md"

FOLLOW_UP_PLACEHOLDER = "Follow-up placeholder: create a tracked issue before ratchet mode."


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--docs-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--check", action="store_true", help="Fail if generated artifacts drift")
    parser.add_argument("--update", action="store_true", help="Rewrite manifest and report")
    return parser.parse_args(argv)


def _resolve_path(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _contract_ids(path: Path) -> list[str]:
    return sorted(_contract_records(path))


def _contract_records(path: Path) -> dict[str, dict[str, Any]]:
    contracts = _load_json(path).get("contracts", {})
    if not isinstance(contracts, dict):
        return {}
    return {
        str(contract_id): meta
        for contract_id, meta in contracts.items()
        if isinstance(meta, dict)
    }


def _snapshot_records(path: Path, key: str) -> dict[str, dict[str, Any]]:
    records = _load_json(path).get(key, {})
    if not isinstance(records, dict):
        return {}
    return {
        str(record_id): meta
        for record_id, meta in records.items()
        if isinstance(meta, dict)
    }


def _source_contract_files(contract_id: str, connector_id: str) -> list[str]:
    module_by_connector = {
        "eurostat.data": ("eurostat.py", "eurostat_contracts.py"),
        "sdmx.source": ("sdmx_source.py", "sdmx_contracts.py"),
        "ukons.datasets": ("ukons.py", "ukons_contracts.py"),
        "worldbank.wdi": ("world_bank.py", "world_bank_contracts.py"),
        "wvs.wave7": ("wvs.py", "wvs_contracts.py"),
    }
    source_module, contract_module = module_by_connector.get(
        connector_id, ("__init__.py", "__init__.py")
    )
    return [
        f"src/polisyos/fabric/connectors/sources/{source_module}",
        f"src/polisyos/fabric/connectors/sources/_contracts/{contract_module}",
        "schemas/snapshots/fabric/connector_contract_registry.json",
    ]


def _parse_ast(path: Path) -> ast.Module | None:
    if not path.exists():
        return None
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return None


def _string_list_assignment(path: Path, name: str) -> list[str]:
    tree = _parse_ast(path)
    if tree is None:
        return []

    def _matches(target: ast.AST) -> bool:
        return isinstance(target, ast.Name) and target.id == name

    for node in tree.body:
        value: ast.AST | None = None
        is_named_assign = isinstance(node, ast.Assign) and any(
            _matches(target) for target in node.targets
        )
        is_named_annotated_assign = isinstance(node, ast.AnnAssign) and _matches(
            node.target
        )
        if is_named_assign or is_named_annotated_assign:
            value = node.value
        if isinstance(value, (ast.List, ast.Tuple)):
            return [
                item.value
                for item in value.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            ]
    return []


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _source_profile_ids(path: Path) -> list[str]:
    tree = _parse_ast(path)
    if tree is None:
        return []
    profile_ids: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _call_name(node.func) != "SourceProfile":
            continue
        for keyword in node.keywords:
            if keyword.arg == "profile_id" and isinstance(keyword.value, ast.Constant):
                if isinstance(keyword.value.value, str):
                    profile_ids.append(keyword.value.value)
                    break
    return sorted(profile_ids)


def _fabric_connector_entrypoints(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return {}
    project = payload.get("project", {})
    if not isinstance(project, dict):
        return {}
    entry_points = project.get("entry-points", {})
    if not isinstance(entry_points, dict):
        return {}
    raw = entry_points.get("polisyos.fabric_connectors", {})
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in sorted(raw.items())}


def _existing_paths(repo_root: Path, paths: Iterable[str]) -> list[str]:
    return [path for path in paths if (repo_root / path).exists()]


def _python_files(repo_root: Path, directory: str) -> list[str]:
    root = repo_root / directory
    if not root.exists():
        return []
    return [
        _rel(path, repo_root)
        for path in sorted(root.glob("*.py"))
        if path.name != "__init__.py"
    ]


def _python_files_recursive(repo_root: Path, directory: str) -> list[str]:
    root = repo_root / directory
    if not root.exists():
        return []
    return [_rel(path, repo_root) for path in sorted(root.rglob("*.py"))]


def _has_token(path: Path, token: str) -> bool:
    return token in _read_text(path)


def _surface(
    *,
    surface_id: str,
    plane: str,
    status: str,
    priority: str,
    title: str,
    description: str,
    source_files: Iterable[str] = (),
    tests: Iterable[str] = (),
    docs: Iterable[str] = (),
    evidence: Mapping[str, Any] | None = None,
    follow_up: str | None = None,
    accepted_risk: Mapping[str, Any] | None = None,
    owner: str = OWNER,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": surface_id,
        "plane": plane,
        "status": status,
        "priority": priority,
        "severity": priority,
        "phase": PHASE,
        "owner": owner,
        "title": title,
        "description": description,
        "source_files": sorted(source_files),
        "tests": sorted(tests),
        "docs": sorted(docs),
        "evidence": dict(evidence or {}),
    }
    if status in {"partial", "missing", "blocked_by_research"}:
        row["follow_up"] = follow_up or FOLLOW_UP_PLACEHOLDER
    elif follow_up:
        row["follow_up"] = follow_up
    if status == "accepted_risk":
        row["accepted_risk"] = dict(accepted_risk or {})
    return row


def _status_if(condition: bool, *, partial_when_false: bool = False) -> str:
    if condition:
        return "implemented"
    return "partial" if partial_when_false else "missing"


def _status_counts(surfaces: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = dict.fromkeys(STATUS_VALUES, 0)
    for surface in surfaces:
        status = str(surface.get("status", ""))
        if status in counts:
            counts[status] += 1
    return counts


def _plane_counts(surfaces: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = dict.fromkeys(PLANES, 0)
    for surface in surfaces:
        plane = str(surface.get("plane", ""))
        if plane in counts:
            counts[plane] += 1
    return counts


def _paths(repo_root: Path) -> dict[str, Path]:
    return {
        "pyproject": repo_root / "pyproject.toml",
        "fabric_contract_snapshot": repo_root
        / "schemas"
        / "snapshots"
        / "fabric"
        / "connector_contract_registry.json",
        "legacy_contract_snapshot": repo_root
        / "schemas"
        / "snapshots"
        / "connectors"
        / "contracts.json",
        "source_contract_v2": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "connectors"
        / "contracts"
        / "source_contract.py",
        "source_contract_schema": repo_root
        / "schemas"
        / "fabric"
        / "source_contract.schema.json",
        "source_scorecard_schema": repo_root
        / "schemas"
        / "fabric"
        / "source_scorecard.schema.json",
        "source_contract_snapshot_v2": repo_root
        / "schemas"
        / "snapshots"
        / "fabric"
        / "source_contracts_v2.json",
        "source_scorecard_snapshot": repo_root
        / "schemas"
        / "snapshots"
        / "fabric"
        / "source_scorecards.json",
        "source_contracts_validator": repo_root
        / "tools"
        / "quality"
        / "validation"
        / "fabric_source_contracts.py",
        "connector_sdk": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "connectors"
        / "sdk",
        "conformance_v2": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "connectors"
        / "testing"
        / "conformance.py",
        "scorecard": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "connectors"
        / "scorecard.py",
        "decision_data": repo_root / "src" / "polisyos" / "fabric" / "decision_data.py",
        "trust_envelope_schema": repo_root
        / "schemas"
        / "fabric"
        / "trust_envelope.schema.json",
        "decision_data_coverage": repo_root
        / "tools"
        / "quality"
        / "validation"
        / "fabric_decision_data_coverage.py",
        "decision_data_coverage_report": repo_root
        / "tools"
        / "quality"
        / "validation"
        / "fabric_decision_data_coverage.json",
        "source_platform_doc": repo_root
        / "docs"
        / "reference"
        / "fabric"
        / "source-platform.md",
        "source_init": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "connectors"
        / "sources"
        / "__init__.py",
        "builtin_profiles": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "connectors"
        / "profiles"
        / "builtin_profiles.py",
        "quality": repo_root / "src" / "polisyos" / "fabric" / "quality.py",
        "fitness_report": repo_root / "src" / "polisyos" / "fabric" / "fitness_report.py",
        "observability": repo_root / "src" / "polisyos" / "fabric" / "observability.py",
        "core_metrics_base": repo_root
        / "src"
        / "polisyos"
        / "core"
        / "observability"
        / "_metrics_registry_base.py",
        "core_metrics_parts": repo_root
        / "src"
        / "polisyos"
        / "core"
        / "observability"
        / "metrics_parts.py",
        "connector_governance_metadata": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "connectors"
        / "governance_metadata.py",
        "connector_quality": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "connectors"
        / "quality",
        "quality_evidence": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "connectors"
        / "quality"
        / "evidence.py",
        "scientist_quality_gate": repo_root
        / "src"
        / "polisyos"
        / "scientist"
        / "governance"
        / "passes"
        / "quality_gate_pass.py",
        "schema_governance": repo_root
        / "tools"
        / "quality"
        / "validation"
        / "fabric_schema_governance.py",
        "replay_store": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "data_plane"
        / "replay_store.py",
        "quarantine": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "data_plane"
        / "quarantine.py",
        "evidence": repo_root / "src" / "polisyos" / "fabric" / "evidence.py",
        "lineage": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "provenance"
        / "lineage.py",
        "provo": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "provenance"
        / "export_provo.py",
        "world_query": repo_root / "src" / "polisyos" / "fabric" / "world_query.py",
        "snapshots": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "world"
        / "store"
        / "snapshots.py",
        "temporal_route": repo_root
        / "src"
        / "polisyos"
        / "runtime"
        / "http"
        / "routes"
        / "temporal.py",
        "temporal_service": repo_root
        / "src"
        / "polisyos"
        / "runtime"
        / "http"
        / "services"
        / "temporal.py",
        "runs_route": repo_root
        / "src"
        / "polisyos"
        / "runtime"
        / "http"
        / "routes"
        / "runs.py",
        "lineage_route": repo_root
        / "src"
        / "polisyos"
        / "runtime"
        / "http"
        / "routes"
        / "lineage.py",
        "lineage_service": repo_root
        / "src"
        / "polisyos"
        / "runtime"
        / "http"
        / "services"
        / "lineage.py",
        "access_control": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "security"
        / "access_control.py",
        "column_mask": repo_root
        / "src"
        / "polisyos"
        / "fabric"
        / "security"
        / "column_mask.py",
        "pii_stage": repo_root / "src" / "polisyos" / "fabric" / "pii" / "stage.py",
        "fabric_facade": repo_root / "src" / "polisyos" / "fabric" / "__init__.py",
        "ir_connectors": repo_root / "src" / "polisyos" / "ir" / "connectors.py",
    }


def _tests_by_plane(repo_root: Path) -> dict[str, list[str]]:
    raw = {
        "source": [
            "tests/fabric/connectors/test_contract_system.py",
            "tests/fabric/connectors/test_protocol_compliance.py",
            "tests/fabric/connectors/test_registry.py",
            "tests/fabric/connectors/test_source_contract_v2.py",
            "tests/fabric/connectors/profiles/test_source_profiles.py",
            "tests/tools/test_fabric_schema_governance.py",
            "tests/tools/test_fabric_source_contracts.py",
        ],
        "evidence": [
            "tests/fabric/data_plane/test_record_replay.py",
            "tests/fabric/data_plane/test_quarantine.py",
            "tests/fabric/test_ingestion_quarantine.py",
            "tests/fabric/test_provenance.py",
            "tests/fabric/connectors/test_source_contract_v2.py",
            "tests/tools/test_fabric_source_contracts.py",
        ],
        "semantics": [
            "tests/fabric/test_quality_indicators.py",
            "tests/fabric/connectors/test_quality_system.py",
            "tests/fabric/connectors/test_quality_statistics.py",
            "tests/fabric/connectors/test_schema_system.py",
            "tests/fabric/connectors/test_source_contract_v2.py",
            "tests/tools/test_fabric_schema_governance.py",
            "tests/tools/test_fabric_source_contracts.py",
        ],
        "world": [
            "tests/fabric/test_world_time_travel.py",
            "tests/fabric/test_world_materialization.py",
            "tests/fabric/test_world_query_multibackend.py",
            "tests/runtime/http/test_temporal_api.py",
            "tests/runtime/http/test_temporal_routes.py",
        ],
        "trust": [
            "tests/fabric/test_lineage.py",
            "tests/fabric/test_decision_data_envelope.py",
            "tests/fabric/test_fabric_observability.py",
            "tests/fabric/test_observability_governance_quality_phase4.py",
            "tests/fabric/test_provenance.py",
            "tests/fabric/test_access_control.py",
            "tests/fabric/test_duckdb_storage_access_control.py",
            "tests/fabric/test_world_query_column_masking.py",
            "tests/fabric/connectors/test_source_contract_v2.py",
            "tests/runtime/http/test_lineage_api.py",
            "tests/runtime/http/test_lineage_routes.py",
            "tests/tools/test_fabric_source_contracts.py",
            "tests/tools/test_fabric_decision_data_coverage.py",
        ],
    }
    return {plane: _existing_paths(repo_root, paths) for plane, paths in raw.items()}


def _build_surfaces(repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    paths = _paths(repo_root)
    fabric_contract_records = _contract_records(paths["fabric_contract_snapshot"])
    fabric_contract_ids = _contract_ids(paths["fabric_contract_snapshot"])
    legacy_contract_ids = _contract_ids(paths["legacy_contract_snapshot"])
    source_contract_v2_records = _contract_records(paths["source_contract_snapshot_v2"])
    source_contract_v2_ids = sorted(source_contract_v2_records)
    source_scorecard_records = _snapshot_records(paths["source_scorecard_snapshot"], "scorecards")
    source_contract_v2_payloads = [
        record.get("contract", {}) for record in source_contract_v2_records.values()
    ]
    source_v2_replay_fixture_count = sum(
        1
        for contract in source_contract_v2_payloads
        if isinstance(contract, Mapping)
        and isinstance(contract.get("replay"), Mapping)
        and contract["replay"].get("fixture_ref")
    )
    source_v2_non_replayable_reason_count = sum(
        1
        for contract in source_contract_v2_payloads
        if isinstance(contract, Mapping)
        and isinstance(contract.get("replay"), Mapping)
        and contract["replay"].get("non_replayable_reason")
    )
    source_v2_classification_count = sum(
        1
        for contract in source_contract_v2_payloads
        if isinstance(contract, Mapping)
        and isinstance(contract.get("security"), Mapping)
        and contract["security"].get("classification")
    )
    source_v2_bounded_read_count = sum(
        1
        for contract in source_contract_v2_payloads
        if isinstance(contract, Mapping)
        and isinstance(contract.get("quality"), Mapping)
        and "bounded_reads"
        in {
            str(check).casefold()
            for check in contract["quality"].get("required_checks", [])
        }
    )
    source_v2_owner_reviewer_count = sum(
        1
        for contract in source_contract_v2_payloads
        if isinstance(contract, Mapping)
        and contract.get("owner")
        and contract.get("reviewer")
    )
    entrypoints = _fabric_connector_entrypoints(paths["pyproject"])
    source_exports = _string_list_assignment(paths["source_init"], "__all__")
    source_tree_files = _python_files_recursive(
        repo_root, "src/polisyos/fabric/connectors/sources"
    )
    concrete_connectors = sorted(
        export
        for export in source_exports
        if export not in {"HTTPConnectorBase", "HTTPResilienceProfile"}
    )
    profile_ids = _source_profile_ids(paths["builtin_profiles"])
    quality_modules = _python_files(
        repo_root, "src/polisyos/fabric/connectors/quality"
    )
    public_exports = _string_list_assignment(paths["fabric_facade"], "__all__")
    tests_by_plane = _tests_by_plane(repo_root)

    source_contract_tests = _existing_paths(
        repo_root,
        [
            "tests/fabric/connectors/test_contract_system.py",
            "tests/fabric/connectors/test_schema_system.py",
            "tests/fabric/connectors/test_source_contract_v2.py",
            "tests/tools/test_fabric_schema_governance.py",
            "tests/tools/test_fabric_source_contracts.py",
        ],
    )
    source_platform_tests = _existing_paths(
        repo_root,
        [
            "tests/fabric/connectors/test_source_contract_v2.py",
            "tests/tools/test_fabric_source_contracts.py",
        ],
    )
    profile_tests = _existing_paths(
        repo_root, ["tests/fabric/connectors/profiles/test_source_profiles.py"]
    )
    quality_tests = _existing_paths(
        repo_root,
        [
            "tests/fabric/test_quality_indicators.py",
            "tests/fabric/connectors/test_quality_system.py",
            "tests/fabric/connectors/test_quality_statistics.py",
        ],
    )
    phase4_tests = _existing_paths(
        repo_root,
        ["tests/fabric/test_observability_governance_quality_phase4.py"],
    )
    lineage_tests = _existing_paths(
        repo_root,
        [
            "tests/fabric/test_lineage.py",
            "tests/fabric/test_fabric_observability.py",
        ],
    )
    temporal_tests = _existing_paths(
        repo_root,
        [
            "tests/fabric/test_world_time_travel.py",
            "tests/fabric/test_world_materialization.py",
            "tests/runtime/http/test_temporal_api.py",
            "tests/runtime/http/test_temporal_routes.py",
        ],
    )
    replay_tests = _existing_paths(
        repo_root,
        [
            "tests/fabric/data_plane/test_record_replay.py",
            "tests/fabric/data_plane/test_quarantine.py",
            "tests/fabric/test_ingestion_quarantine.py",
        ],
    )
    access_tests = _existing_paths(
        repo_root,
        [
            "tests/fabric/test_access_control.py",
            "tests/fabric/test_duckdb_storage_access_control.py",
            "tests/fabric/test_world_query_column_masking.py",
        ],
    )
    facade_tests = _existing_paths(
        repo_root,
        [
            "tests/fabric/test_connector_bridge.py",
            "tests/fabric/test_world_query_multibackend.py",
            "tests/runtime/http/test_e2e_ingestion.py",
        ],
    )
    decision_data_tests = _existing_paths(
        repo_root,
        [
            "tests/fabric/test_decision_data_envelope.py",
            "tests/runtime/http/test_lineage_routes.py",
            "tests/runtime/http/test_temporal_routes.py",
            "tests/tools/test_fabric_decision_data_coverage.py",
        ],
    )
    decision_data_report = _load_json(paths["decision_data_coverage_report"])
    decision_data_status = (
        "implemented"
        if paths["decision_data"].exists()
        and paths["trust_envelope_schema"].exists()
        and paths["decision_data_coverage"].exists()
        and decision_data_report.get("summary", {}).get("status") == "implemented"
        else "missing"
    )

    surfaces = [
        _surface(
            surface_id="source_contracts.fabric_registry_snapshot",
            plane="source",
            status=_status_if(bool(fabric_contract_ids)),
            priority="P1",
            title="Fabric connector contract registry snapshot",
            description="Committed source-contract snapshot used by schema governance.",
            source_files=[
                _rel(paths["fabric_contract_snapshot"], repo_root),
                "src/polisyos/fabric/connectors/sources/_contracts/__init__.py",
            ],
            tests=source_contract_tests,
            docs=["docs/reference/fabric/schema-compatibility.md"],
            evidence={
                "contract_snapshot": _rel(paths["fabric_contract_snapshot"], repo_root),
                "contract_count": len(fabric_contract_ids),
                "contract_ids": fabric_contract_ids,
            },
        ),
        _surface(
            surface_id="source_contracts.legacy_connector_snapshot",
            plane="source",
            status=_status_if(bool(legacy_contract_ids)),
            priority="P2",
            title="Legacy connector contract snapshot",
            description="Compatibility snapshot still checked by legacy connector tooling.",
            source_files=[_rel(paths["legacy_contract_snapshot"], repo_root)],
            tests=source_contract_tests,
            docs=["docs/reference/fabric/schema-compatibility.md"],
            evidence={
                "contract_snapshot": _rel(paths["legacy_contract_snapshot"], repo_root),
                "contract_count": len(legacy_contract_ids),
                "contract_ids": legacy_contract_ids,
            },
        ),
        _surface(
            surface_id="source.source_contract_v2_platform",
            plane="source",
            status=_status_if(
                paths["source_contract_v2"].exists()
                and paths["source_contract_schema"].exists()
                and bool(source_contract_v2_ids)
                and source_v2_bounded_read_count == len(source_contract_v2_ids)
                and paths["source_contracts_validator"].exists()
                and bool(source_platform_tests)
            ),
            priority="P1",
            title="SourceContract v2 production source platform",
            description=(
                "Contract-first source evidence covering schema, profile, quality, replay, "
                "lineage, access, retention, SLO, owner, reviewer, and docs."
            ),
            source_files=[
                _rel(paths["source_contract_v2"], repo_root),
                _rel(paths["source_contract_schema"], repo_root),
                _rel(paths["source_contract_snapshot_v2"], repo_root),
                _rel(paths["source_contracts_validator"], repo_root),
            ],
            tests=source_platform_tests,
            docs=[
                "docs/reference/fabric/source-platform.md",
                "docs/reference/fabric/connectors.md",
            ],
            evidence={
                "schema": _rel(paths["source_contract_schema"], repo_root),
                "snapshot": _rel(paths["source_contract_snapshot_v2"], repo_root),
                "source_contract_v2_count": len(source_contract_v2_ids),
                "source_contract_v2_ids": source_contract_v2_ids,
                "bounded_read_evidence_count": source_v2_bounded_read_count,
            },
        ),
        _surface(
            surface_id="source.connector_sdk_authoring_helpers",
            plane="source",
            status=_status_if(paths["connector_sdk"].exists() and bool(source_platform_tests)),
            priority="P1",
            title="Connector SDK authoring helpers",
            description=(
                "Scaffold helpers derive source, profile, contract, replay, quality, "
                "and docs ids before a connector becomes production-visible."
            ),
            source_files=_python_files_recursive(
                repo_root, "src/polisyos/fabric/connectors/sdk"
            ),
            tests=source_platform_tests,
            docs=["docs/reference/fabric/source-platform.md"],
            evidence={
                "sdk_package": _rel(paths["connector_sdk"], repo_root),
                "profile_matrix": "build_source_profile_matrix",
            },
        ),
        _surface(
            surface_id="source.conformance_harness_v2",
            plane="source",
            status=_status_if(paths["conformance_v2"].exists() and bool(source_platform_tests)),
            priority="P1",
            title="Connector conformance harness v2",
            description=(
                "Harness reuses connector testing v1 and checks SourceContract v2, profile, "
                "schema, quality, replay, lineage, access, retention, and SLO evidence."
            ),
            source_files=[_rel(paths["conformance_v2"], repo_root)],
            tests=source_platform_tests
            + _existing_paths(repo_root, ["tests/fabric/connectors/test_protocol_compliance.py"]),
            docs=["docs/reference/fabric/source-platform.md"],
            evidence={
                "validator": "validate_source_conformance_v2",
                "harness": "ConnectorConformanceHarnessV2",
                "bounded_read_check": _has_token(paths["conformance_v2"], "bounded_reads"),
                "report_count": len(source_contract_v2_ids),
            },
        ),
        _surface(
            surface_id="source.connector_entrypoints",
            plane="source",
            status=_status_if(bool(entrypoints)),
            priority="P1",
            title="Production connector entry points",
            description="Install-time discovery surface for production connector components.",
            source_files=["pyproject.toml"],
            tests=_existing_paths(
                repo_root,
                [
                    "tests/fabric/connectors/test_registry.py",
                    "tests/fabric/connectors/test_protocol_compliance.py",
                ],
            ),
            docs=["docs/reference/fabric/connectors.md"],
            evidence={
                "entrypoint_group": "polisyos.fabric_connectors",
                "entrypoint_count": len(entrypoints),
                "entrypoints": entrypoints,
            },
        ),
        _surface(
            surface_id="source.connector_public_exports",
            plane="source",
            status=_status_if(bool(concrete_connectors)),
            priority="P1",
            title="Concrete connector public exports",
            description="Concrete connector classes exported from the source package.",
            source_files=[_rel(paths["source_init"], repo_root)],
            tests=_existing_paths(
                repo_root,
                [
                    "tests/fabric/connectors/test_protocol_compliance.py",
                    "tests/fabric/connectors/test_registry.py",
                ],
            ),
            docs=["docs/reference/fabric/connectors.md"],
            evidence={
                "export_count": len(source_exports),
                "concrete_connector_count": len(concrete_connectors),
                "concrete_connectors": concrete_connectors,
            },
        ),
        _surface(
            surface_id="source.connector_source_modules",
            plane="source",
            status=_status_if(bool(source_tree_files)),
            priority="P2",
            title="Connector source module tree",
            description="Recursive inventory of source connector modules and source-contract modules.",
            source_files=source_tree_files,
            tests=_existing_paths(
                repo_root,
                [
                    "tests/fabric/connectors/test_protocol_compliance.py",
                    "tests/fabric/connectors/test_registry.py",
                    "tests/fabric/connectors/test_contract_system.py",
                ],
            ),
            docs=[
                "docs/reference/fabric/connectors.md",
                "docs/reference/fabric/schema-compatibility.md",
            ],
            evidence={
                "source_tree": "src/polisyos/fabric/connectors/sources/**",
                "source_module_count": len(source_tree_files),
                "source_modules": source_tree_files,
            },
        ),
        _surface(
            surface_id="source.entrypoint_coverage.direct_import_families",
            plane="source",
            status="partial"
            if len(concrete_connectors) > len(entrypoints)
            else _status_if(bool(entrypoints)),
            priority="P2",
            title="Entry-point coverage for direct-import connector families",
            description=(
                "The entry-point group covers production HTTP/open-data components; "
                "additional connector families are currently direct-import/registry surfaces."
            ),
            source_files=["pyproject.toml", _rel(paths["source_init"], repo_root)],
            tests=_existing_paths(
                repo_root,
                [
                    "tests/fabric/connectors/test_connector_family_expansion.py",
                    "tests/fabric/connectors/test_registry.py",
                ],
            ),
            docs=["docs/reference/fabric/connectors.md"],
            evidence={
                "entrypoint_count": len(entrypoints),
                "concrete_connector_count": len(concrete_connectors),
                "direct_import_family_count": max(
                    0, len(concrete_connectors) - len(entrypoints)
                ),
            },
            follow_up="Phase 5: decide which direct-import families require entry-point registration.",
        ),
        _surface(
            surface_id="source.builtin_source_profiles",
            plane="source",
            status=_status_if(bool(profile_ids)),
            priority="P1",
            title="Built-in source profile catalog",
            description="Curated profile catalog for source execution policies and connector defaults.",
            source_files=[_rel(paths["builtin_profiles"], repo_root)],
            tests=profile_tests,
            docs=["docs/reference/fabric/profiles.md"],
            evidence={
                "profile_count": len(profile_ids),
                "profile_ids": profile_ids,
            },
        ),
        _surface(
            surface_id="source.http_runtime_base_contract",
            plane="source",
            status="not_applicable",
            priority="P3",
            title="Shared HTTP runtime as production source",
            description=(
                "HTTPConnectorBase and HTTPResilienceProfile are exported runtime primitives, "
                "not standalone production source connectors."
            ),
            source_files=[_rel(paths["source_init"], repo_root)],
            tests=[],
            docs=["docs/reference/fabric/connectors.md"],
            evidence={
                "non_connector_exports": [
                    export
                    for export in source_exports
                    if export in {"HTTPConnectorBase", "HTTPResilienceProfile"}
                ]
            },
        ),
        _surface(
            surface_id="evidence.record_replay_store",
            plane="evidence",
            status=_status_if(paths["replay_store"].exists() and bool(replay_tests)),
            priority="P1",
            title="Record/replay persistence surface",
            description="Data-plane replay store and tests for deterministic ingestion replay.",
            source_files=[_rel(paths["replay_store"], repo_root)],
            tests=replay_tests,
            docs=["docs/reference/fabric/data-plane.md"],
            evidence={
                "replay_store": paths["replay_store"].exists(),
                "record_replay_tests": "tests/fabric/data_plane/test_record_replay.py"
                in replay_tests,
            },
        ),
        _surface(
            surface_id="evidence.quarantine_replay_surface",
            plane="evidence",
            status=_status_if(paths["quarantine"].exists() and bool(replay_tests)),
            priority="P1",
            title="Quarantine/DLQ replay surface",
            description="Quarantine records, replay hooks, and DLQ operational coverage.",
            source_files=[_rel(paths["quarantine"], repo_root)],
            tests=replay_tests,
            docs=[
                "docs/reference/fabric/data-plane.md",
                "docs/runbooks/fabric-quarantine-dlq-and-data-plane-recovery.md",
            ],
            evidence={
                "quarantine_module": paths["quarantine"].exists(),
                "quarantine_tests": "tests/fabric/data_plane/test_quarantine.py"
                in replay_tests,
            },
        ),
        _surface(
            surface_id="evidence.production_source_replay_fixtures",
            plane="evidence",
            status=_status_if(
                bool(source_contract_v2_ids)
                and (
                    source_v2_replay_fixture_count
                    + source_v2_non_replayable_reason_count
                )
                == len(source_contract_v2_ids),
                partial_when_false=True,
            ),
            priority="P1",
            title="Replay fixture or explicit non-replayable matrix",
            description=(
                "SourceContract v2 records either replay fixtures or explicit "
                "non-replayable reasons for production source contracts."
            ),
            source_files=[
                _rel(paths["replay_store"], repo_root),
                _rel(paths["source_contract_snapshot_v2"], repo_root),
            ],
            tests=replay_tests + source_platform_tests,
            docs=[
                "docs/reference/fabric/data-plane.md",
                "docs/reference/fabric/source-platform.md",
            ],
            evidence={
                "production_entrypoint_count": len(entrypoints),
                "contract_snapshot_count": len(fabric_contract_ids),
                "source_contract_v2_count": len(source_contract_v2_ids),
                "replay_fixture_count": source_v2_replay_fixture_count,
                "non_replayable_reason_count": source_v2_non_replayable_reason_count,
                "record_replay_tests_present": bool(replay_tests),
            },
            follow_up=(
                "Phase 5: add replay fixtures for sources currently carrying "
                "explicit non-replayable reasons."
            ),
        ),
        _surface(
            surface_id="evidence.cas_evidence_bundle",
            plane="evidence",
            status="implemented"
            if paths["evidence"].exists()
            and "tests/fabric/test_provenance.py" in tests_by_plane["evidence"]
            else "partial",
            priority="P2",
            title="CAS-backed evidence bundle persistence",
            description="Evidence bundle helpers that persist provenance payloads into governed artifact storage.",
            source_files=[_rel(paths["evidence"], repo_root)],
            tests=_existing_paths(repo_root, ["tests/fabric/test_provenance.py"]),
            docs=["docs/reference/fabric/lineage.md"],
            evidence={
                "evidence_module": paths["evidence"].exists(),
                "provenance_bundle_tests": "tests/fabric/test_provenance.py"
                in tests_by_plane["evidence"],
            },
        ),
        _surface(
            surface_id="semantics.quality_indicators",
            plane="semantics",
            status=_status_if(paths["quality"].exists() and bool(quality_tests)),
            priority="P1",
            title="Metric-level quality indicators",
            description="Quality indicator scoring, finite-value guards, and metric fitness reports.",
            source_files=[_rel(paths["quality"], repo_root), _rel(paths["fitness_report"], repo_root)],
            tests=quality_tests,
            docs=["docs/reference/fabric/quality.md"],
            evidence={
                "quality_module": paths["quality"].exists(),
                "fitness_report_module": paths["fitness_report"].exists(),
                "quality_tests": quality_tests,
            },
        ),
        _surface(
            surface_id="semantics.connector_quality_validators",
            plane="semantics",
            status=_status_if(bool(quality_modules) and bool(quality_tests)),
            priority="P1",
            title="Connector-level quality validators",
            description="Completeness, consistency, freshness, statistics, and validator modules for source outputs.",
            source_files=quality_modules,
            tests=quality_tests,
            docs=["docs/reference/fabric/quality.md"],
            evidence={
                "quality_module_count": len(quality_modules),
                "quality_modules": quality_modules,
            },
        ),
        _surface(
            surface_id="semantics.source_quality_contract_coverage",
            plane="semantics",
            status=_status_if(
                bool(source_contract_v2_ids)
                and paths["source_contracts_validator"].exists()
                and bool(source_platform_tests),
                partial_when_false=True,
            ),
            priority="P1",
            title="Quality-contract coverage by source contract/profile",
            description=(
                "SourceContract v2 snapshot carries quality-contract refs and "
                "required quality checks for production source contracts."
            ),
            source_files=[
                _rel(paths["quality"], repo_root),
                _rel(paths["builtin_profiles"], repo_root),
                _rel(paths["fabric_contract_snapshot"], repo_root),
                _rel(paths["source_contract_snapshot_v2"], repo_root),
            ],
            tests=quality_tests + source_contract_tests + source_platform_tests,
            docs=[
                "docs/reference/fabric/quality.md",
                "docs/reference/fabric/profiles.md",
                "docs/reference/fabric/source-platform.md",
            ],
            evidence={
                "contract_count": len(fabric_contract_ids),
                "source_contract_v2_count": len(source_contract_v2_ids),
                "profile_count": len(profile_ids),
                "quality_validator_module_count": len(quality_modules),
            },
            follow_up=(
                "Phase 6: propagate source quality states into decision-data envelopes."
            ),
        ),
        _surface(
            surface_id="semantics.source_scorecards",
            plane="semantics",
            status=_status_if(
                paths["scorecard"].exists()
                and paths["source_scorecard_schema"].exists()
                and bool(source_scorecard_records)
                and bool(source_platform_tests)
            ),
            priority="P1",
            title="Generated source scorecards",
            description=(
                "Scorecards summarize freshness, reliability, schema drift, quality, "
                "contract violations, quarantine, replay, latency, and source trust."
            ),
            source_files=[
                _rel(paths["scorecard"], repo_root),
                _rel(paths["source_scorecard_schema"], repo_root),
                _rel(paths["source_scorecard_snapshot"], repo_root),
            ],
            tests=source_platform_tests,
            docs=["docs/reference/fabric/source-platform.md"],
            evidence={
                "schema": _rel(paths["source_scorecard_schema"], repo_root),
                "snapshot": _rel(paths["source_scorecard_snapshot"], repo_root),
                "scorecard_count": len(source_scorecard_records),
                "required_dimensions": [
                    "freshness",
                    "reliability",
                    "schema_drift",
                    "quality",
                    "replay_success",
                ],
            },
        ),
        _surface(
            surface_id="semantics.schema_governance_snapshot_gate",
            plane="semantics",
            status=_status_if(paths["schema_governance"].exists() and bool(source_contract_tests)),
            priority="P1",
            title="Schema governance snapshot gate",
            description="Governance check for connector contract evolution and committed snapshots.",
            source_files=[
                _rel(paths["schema_governance"], repo_root),
                _rel(paths["fabric_contract_snapshot"], repo_root),
            ],
            tests=source_contract_tests,
            docs=["docs/reference/fabric/schema-compatibility.md"],
            evidence={
                "validator": _rel(paths["schema_governance"], repo_root),
                "contract_snapshot": _rel(paths["fabric_contract_snapshot"], repo_root),
            },
        ),
        _surface(
            surface_id="semantics.fabric_quality_governance_evidence",
            plane="semantics",
            status=_status_if(
                paths["quality_evidence"].exists()
                and paths["scientist_quality_gate"].exists()
                and bool(phase4_tests)
            ),
            priority="P1",
            title="Fabric quality evidence propagation",
            description=(
                "Normalized Fabric quality evidence is exported from quality reports "
                "and attached to Scientist governance state."
            ),
            source_files=[
                _rel(paths["quality_evidence"], repo_root),
                _rel(paths["scientist_quality_gate"], repo_root),
            ],
            tests=phase4_tests,
            docs=[
                "docs/reference/fabric/quality.md",
                "docs/reference/fabric/observability-governance.md",
            ],
            evidence={
                "quality_evidence_builder": _has_token(
                    paths["quality_evidence"],
                    "build_fabric_quality_governance_evidence",
                ),
                "scientist_state_key": _has_token(
                    paths["scientist_quality_gate"],
                    "fabric_quality_evidence",
                ),
            },
        ),
        _surface(
            surface_id="world.bitemporal_world_query",
            plane="world",
            status=_status_if(
                paths["world_query"].exists()
                and _has_token(paths["world_query"], "as_of_tx_time")
                and _has_token(paths["world_query"], "as_of_valid_time")
                and bool(temporal_tests)
            ),
            priority="P1",
            title="Bitemporal world-query support",
            description="World queries support transaction-time and valid-time filters.",
            source_files=[_rel(paths["world_query"], repo_root)],
            tests=temporal_tests,
            docs=["docs/reference/fabric/time-travel.md"],
            evidence={
                "as_of_tx_time": _has_token(paths["world_query"], "as_of_tx_time"),
                "as_of_valid_time": _has_token(paths["world_query"], "as_of_valid_time"),
                "temporal_tests": temporal_tests,
            },
        ),
        _surface(
            surface_id="world.snapshot_branch_surface",
            plane="world",
            status=_status_if(
                paths["snapshots"].exists()
                and _has_token(paths["snapshots"], "create_world_branch")
                and _has_token(paths["snapshots"], "merge_world_branch")
            ),
            priority="P1",
            title="Snapshot, branch, merge, and retention surface",
            description="World snapshot store supports retained snapshots, branches, merge policy, and GC metadata.",
            source_files=[_rel(paths["snapshots"], repo_root)],
            tests=temporal_tests,
            docs=["docs/reference/fabric/time-travel.md"],
            evidence={
                "create_world_branch": _has_token(paths["snapshots"], "create_world_branch"),
                "merge_world_branch": _has_token(paths["snapshots"], "merge_world_branch"),
                "gc_world_snapshots": _has_token(paths["snapshots"], "gc_world_snapshots"),
            },
        ),
        _surface(
            surface_id="world.temporal_runtime_adapter",
            plane="world",
            status=_status_if(
                paths["temporal_route"].exists()
                and paths["temporal_service"].exists()
                and "tests/runtime/http/test_temporal_api.py" in temporal_tests
            ),
            priority="P1",
            title="Runtime temporal API adapter",
            description="HTTP service/route adapter maps API temporal scopes to Fabric world-query kwargs.",
            source_files=[
                _rel(paths["temporal_route"], repo_root),
                _rel(paths["temporal_service"], repo_root),
            ],
            tests=_existing_paths(repo_root, ["tests/runtime/http/test_temporal_api.py"]),
            docs=["docs/reference/fabric/time-travel.md", "docs/reference/api/index.md"],
            evidence={
                "route": paths["temporal_route"].exists(),
                "service": paths["temporal_service"].exists(),
            },
        ),
        _surface(
            surface_id="world.future_table_snapshot_adapters",
            plane="world",
            status="accepted_risk",
            priority="P2",
            title="Future table-format snapshot adapters",
            description=(
                "Iceberg/Delta-style external adapters are metadata-visible but fail closed "
                "until runtime support is implemented."
            ),
            source_files=[_rel(paths["snapshots"], repo_root), _rel(paths["world_query"], repo_root)],
            tests=temporal_tests,
            docs=["docs/reference/fabric/time-travel.md"],
            evidence={
                "adapter_registry_present": _has_token(
                    paths["snapshots"], "list_world_snapshot_adapters"
                ),
                "runtime_rejection_test": "tests/fabric/test_world_time_travel.py"
                in temporal_tests,
            },
            accepted_risk={
                "owner": OWNER,
                "reason": (
                    "External table-format adapters are discoverable for planning, "
                    "while runtime query/create paths reject unsupported adapters."
                ),
                "review_date": "2026-05-31",
                "expiry_date": "2026-07-31",
            },
        ),
        _surface(
            surface_id="world.temporal_graph_reasoning",
            plane="world",
            status="blocked_by_research",
            priority="P2",
            title="Temporal graph reasoning over world snapshots",
            description=(
                "Advanced temporal graph semantics are intentionally deferred to the "
                "research wave before being converted into runtime acceptance gates."
            ),
            source_files=[_rel(paths["world_query"], repo_root), _rel(paths["lineage"], repo_root)],
            tests=[],
            docs=["docs/plans/active/FABRIC_BEST_IN_CLASS_PLAN.md"],
            evidence={"research_wave": "Wave R / R3 temporal graph semantics"},
            follow_up="Wave R R3: define acceptance semantics before implementation.",
        ),
        _surface(
            surface_id="trust.fabric_slo_error_budget_gate",
            plane="trust",
            status=_status_if(
                paths["observability"].exists()
                and paths["core_metrics_base"].exists()
                and paths["core_metrics_parts"].exists()
                and bool(phase4_tests)
            ),
            priority="P1",
            title="Fabric SLI/SLO and error-budget gate",
            description=(
                "Fabric defines the release-blocking SLI set, evaluates SLO burn, "
                "records SLI/burn metrics, and blocks P0/P1 feature expansion."
            ),
            source_files=[
                _rel(paths["observability"], repo_root),
                _rel(paths["core_metrics_base"], repo_root),
                _rel(paths["core_metrics_parts"], repo_root),
            ],
            tests=phase4_tests + _existing_paths(repo_root, ["tests/fabric/test_fabric_observability.py"]),
            docs=["docs/reference/fabric/observability-governance.md"],
            evidence={
                "sli_enum": _has_token(paths["observability"], "class FabricSLIName"),
                "slo_targets": _has_token(paths["observability"], "DEFAULT_FABRIC_SLO_TARGETS"),
                "error_budget_gate": _has_token(
                    paths["observability"],
                    "assert_fabric_feature_expansion_allowed",
                ),
                "sli_metric": _has_token(paths["core_metrics_base"], "polisyos_fabric_sli_value"),
                "burn_metric": _has_token(
                    paths["core_metrics_base"],
                    "polisyos_fabric_error_budget_burn_ratio",
                ),
            },
        ),
        _surface(
            surface_id="trust.connector_governance_metadata",
            plane="trust",
            status=_status_if(
                paths["connector_governance_metadata"].exists()
                and paths["ir_connectors"].exists()
                and bool(phase4_tests)
            ),
            priority="P1",
            title="Production connector governance metadata",
            description=(
                "Production connectors expose schema, quality, SLA, access classification, "
                "and owner metadata with a validator-backed inventory check."
            ),
            source_files=[
                _rel(paths["connector_governance_metadata"], repo_root),
                _rel(paths["ir_connectors"], repo_root),
            ],
            tests=phase4_tests + _existing_paths(
                repo_root,
                ["tests/fabric/connectors/test_protocol_compliance.py"],
            ),
            docs=[
                "docs/reference/fabric/connectors.md",
                "docs/reference/fabric/observability-governance.md",
            ],
            evidence={
                "metadata_validator": _has_token(
                    paths["connector_governance_metadata"],
                    "validate_connector_governance_metadata",
                ),
                "schema_governance": _has_token(paths["ir_connectors"], "schema_governance"),
                "quality_governance": _has_token(paths["ir_connectors"], "quality_governance"),
                "sla": _has_token(paths["ir_connectors"], "ConnectorSLASpec"),
            },
        ),
        _surface(
            surface_id="trust.source_contract_access_retention_slo",
            plane="trust",
            status=_status_if(
                bool(source_contract_v2_ids)
                and source_v2_classification_count == len(source_contract_v2_ids)
                and source_v2_owner_reviewer_count == len(source_contract_v2_ids)
                and bool(source_platform_tests)
            ),
            priority="P1",
            title="SourceContract access, retention, owner, reviewer, and SLO metadata",
            description=(
                "Production SourceContract v2 records carry classification, retention, "
                "owner/reviewer, and source SLO metadata before production visibility."
            ),
            source_files=[
                _rel(paths["source_contract_v2"], repo_root),
                _rel(paths["source_contract_snapshot_v2"], repo_root),
                _rel(paths["source_contracts_validator"], repo_root),
            ],
            tests=source_platform_tests + phase4_tests,
            docs=[
                "docs/reference/fabric/source-platform.md",
                "docs/reference/fabric/observability-governance.md",
            ],
            evidence={
                "source_contract_v2_count": len(source_contract_v2_ids),
                "classification_count": source_v2_classification_count,
                "owner_reviewer_count": source_v2_owner_reviewer_count,
            },
        ),
        _surface(
            surface_id="trust.source_deprecation_sunset_policy",
            plane="trust",
            status=_status_if(
                _has_token(paths["source_contract_v2"], "SourceDeprecationPolicy")
                and _has_token(paths["source_platform_doc"], "Deprecation And Sunset Policy")
                and bool(source_platform_tests)
            ),
            priority="P2",
            title="Source deprecation and sunset policy",
            description=(
                "SourceContract v2 models deprecated/sunset status with owner-reviewed "
                "reason, migration note, replacement, and retained historical replay."
            ),
            source_files=[
                _rel(paths["source_contract_v2"], repo_root),
                _rel(paths["source_platform_doc"], repo_root),
            ],
            tests=source_platform_tests,
            docs=["docs/reference/fabric/source-platform.md"],
            evidence={
                "deprecation_model": _has_token(
                    paths["source_contract_v2"], "SourceDeprecationPolicy"
                ),
                "sunset_doc": _has_token(
                    paths["source_platform_doc"], "Deprecation And Sunset Policy"
                ),
            },
        ),
        _surface(
            surface_id="trust.lineage_nodes_edges",
            plane="trust",
            status=_status_if(paths["lineage"].exists() and bool(lineage_tests)),
            priority="P1",
            title="Lineage graph nodes, edges, trace, and impact APIs",
            description="FabricLineageTracker records source, schema, dataset, transform, query, and claim lineage.",
            source_files=[_rel(paths["lineage"], repo_root)],
            tests=lineage_tests,
            docs=["docs/reference/fabric/lineage.md"],
            evidence={
                "trace_value_origin": _has_token(paths["lineage"], "trace_value_origin"),
                "trace_column_lineage": _has_token(paths["lineage"], "trace_column_lineage"),
                "impact_analysis": _has_token(paths["lineage"], "impact_analysis"),
            },
        ),
        _surface(
            surface_id="trust.openlineage_export",
            plane="trust",
            status=_status_if(
                paths["lineage"].exists()
                and _has_token(paths["lineage"], "export_openlineage_json")
                and "tests/fabric/test_lineage.py" in lineage_tests
            ),
            priority="P2",
            title="OpenLineage export",
            description="OpenLineage-shaped export for Fabric provenance graphs.",
            source_files=[_rel(paths["lineage"], repo_root)],
            tests=_existing_paths(repo_root, ["tests/fabric/test_lineage.py"]),
            docs=["docs/reference/fabric/lineage.md"],
            evidence={
                "export_openlineage_json": _has_token(
                    paths["lineage"], "export_openlineage_json"
                )
            },
        ),
        _surface(
            surface_id="trust.prov_export",
            plane="trust",
            status=_status_if(
                paths["provo"].exists()
                and "tests/fabric/test_provenance.py" in tests_by_plane["trust"]
            ),
            priority="P2",
            title="W3C PROV export",
            description="PROV-O JSON-LD and PROV-JSON export surface for governed provenance.",
            source_files=[_rel(paths["provo"], repo_root)],
            tests=_existing_paths(repo_root, ["tests/fabric/test_provenance.py"]),
            docs=["docs/reference/fabric/lineage.md"],
            evidence={
                "prov_o_export": _has_token(paths["provo"], "PROV-O"),
                "prov_json_export": _has_token(paths["provo"], "PROV-JSON"),
            },
        ),
        _surface(
            surface_id="trust.runtime_lineage_adapter",
            plane="trust",
            status=_status_if(
                paths["lineage_route"].exists()
                and paths["lineage_service"].exists()
                and "tests/runtime/http/test_lineage_api.py" in tests_by_plane["trust"]
            ),
            priority="P1",
            title="Runtime lineage API adapter",
            description="HTTP route/service adapter for trace and impact lookup over Fabric lineage.",
            source_files=[
                _rel(paths["lineage_route"], repo_root),
                _rel(paths["lineage_service"], repo_root),
            ],
            tests=_existing_paths(repo_root, ["tests/runtime/http/test_lineage_api.py"]),
            docs=["docs/reference/fabric/lineage.md", "docs/reference/api/index.md"],
            evidence={
                "route": paths["lineage_route"].exists(),
                "service": paths["lineage_service"].exists(),
            },
        ),
        _surface(
            surface_id="trust.access_classification",
            plane="trust",
            status="partial",
            priority="P1",
            title="Access classification and masking inventory",
            description=(
                "Access policies, column masking, and PII staging exist; source contracts "
                "do not yet prove classification coverage for every decision-bearing field."
            ),
            source_files=[
                _rel(paths["access_control"], repo_root),
                _rel(paths["column_mask"], repo_root),
                _rel(paths["pii_stage"], repo_root),
            ],
            tests=access_tests,
            docs=["docs/reference/fabric/time-travel.md", "docs/reference/fabric/quality.md"],
            evidence={
                "access_control_module": paths["access_control"].exists(),
                "column_mask_module": paths["column_mask"].exists(),
                "pii_stage_module": paths["pii_stage"].exists(),
                "access_tests": access_tests,
            },
            follow_up="Phase 5/6: require contract/profile-level classification coverage for decision-bearing fields.",
        ),
        _surface(
            surface_id="trust.fabric_decision_envelope",
            plane="trust",
            status=decision_data_status,
            priority="P1",
            title="Fabric decision envelope",
            description=(
                "Fabric-level envelope binding source, quality, lineage, replay, temporal, "
                "and access state into a single decision-bearing contract."
            ),
            source_files=[
                _rel(paths["decision_data"], repo_root),
                _rel(paths["trust_envelope_schema"], repo_root),
                _rel(paths["runs_route"], repo_root),
                _rel(paths["lineage_service"], repo_root),
            ],
            tests=decision_data_tests,
            docs=[
                "docs/plans/active/FABRIC_BEST_IN_CLASS_PLAN.md",
                "docs/reference/fabric/best-in-class-inventory.md",
            ],
            evidence={
                "coverage_report": _rel(paths["decision_data_coverage_report"], repo_root),
                "required_contracts": decision_data_report.get("required_contracts", {}),
            },
            follow_up=(
                None
                if decision_data_status == "implemented"
                else "Phase 6: define and gate Fabric decision-envelope contract."
            ),
        ),
        _surface(
            surface_id="trust.fabric_decision_reason_codes",
            plane="trust",
            status=decision_data_status,
            priority="P2",
            title="Reason codes for decision-bearing unknown states",
            description=(
                "Decision-bearing untraced, unknown_quality, restricted, non_replayable, "
                "and unsupported_temporal_scope states carry required reason metadata."
            ),
            source_files=[
                _rel(paths["decision_data"], repo_root),
                _rel(paths["decision_data_coverage"], repo_root),
            ],
            tests=decision_data_tests,
            docs=["docs/plans/active/FABRIC_BEST_IN_CLASS_PLAN.md"],
            evidence={
                "typed_gap_states": decision_data_report.get("typed_gap_states", []),
                "naked_decision_values": decision_data_report.get(
                    "naked_decision_values", []
                ),
            },
            follow_up=(
                None
                if decision_data_status == "implemented"
                else "Phase 6 ratchet: add reason-code taxonomy and CI check."
            ),
        ),
        _surface(
            surface_id="trust.public_facade_exports",
            plane="trust",
            status=_status_if(
                {
                    "WorldQueryError",
                    "WorldQueryRequest",
                    "execute_world_query",
                    "fabric_get_data",
                    "query_claims",
                    "query_events",
                    "query_world_table",
                    "run_connectors_ingestion",
                    "world",
                }.issubset(public_exports)
            ),
            priority="P2",
            title="Stable public facade exports",
            description="Root Fabric package exports the supported ingestion and world-query facade.",
            source_files=[_rel(paths["fabric_facade"], repo_root)],
            tests=facade_tests,
            docs=["docs/reference/fabric/index.md"],
            evidence={
                "export_count": len(public_exports),
                "exports": public_exports,
            },
        ),
    ]

    for contract_id, meta in sorted(fabric_contract_records.items()):
        connector_id = str(meta.get("connector_id", "unknown"))
        dataset_id = str(meta.get("dataset_id", "unknown"))
        surfaces.append(
            _surface(
                surface_id=f"source_contracts.{contract_id}",
                plane="source",
                status="implemented",
                priority="P1",
                title=f"Source contract: {contract_id}",
                description=(
                    "Addressable committed connector contract from the Fabric governance "
                    "snapshot."
                ),
                source_files=_existing_paths(
                    repo_root, _source_contract_files(contract_id, connector_id)
                ),
                tests=source_contract_tests,
                docs=[
                    "docs/reference/fabric/connectors.md",
                    "docs/reference/fabric/schema-compatibility.md",
                    "docs/reference/fabric/best-in-class-inventory.md",
                ],
                evidence={
                    "contract_snapshot": _rel(paths["fabric_contract_snapshot"], repo_root),
                    "contract_id": contract_id,
                    "connector_id": connector_id,
                    "dataset_id": dataset_id,
                    "schema_id": str(meta.get("schema_id", contract_id)),
                    "schema_version": str(meta.get("schema_version", "unknown")),
                    "content_hash": str(meta.get("content_hash", "")),
                },
            )
        )

    coverage = {
        "source_contracts": {
            "status": "implemented" if fabric_contract_ids and legacy_contract_ids else "missing",
            "fabric_registry_contracts": len(fabric_contract_ids),
            "legacy_connector_contracts": len(legacy_contract_ids),
            "source_contract_v2_contracts": len(source_contract_v2_ids),
            "contract_ids": sorted(set(fabric_contract_ids) | set(legacy_contract_ids)),
            "tests": source_contract_tests,
        },
        "source_platform": {
            "status": "implemented"
            if source_contract_v2_ids
            and len(source_scorecard_records) == len(source_contract_v2_ids)
            and source_v2_bounded_read_count == len(source_contract_v2_ids)
            and paths["source_contracts_validator"].exists()
            else "missing",
            "source_contract_v2_count": len(source_contract_v2_ids),
            "source_scorecard_count": len(source_scorecard_records),
            "replay_fixture_count": source_v2_replay_fixture_count,
            "non_replayable_reason_count": source_v2_non_replayable_reason_count,
            "classification_count": source_v2_classification_count,
            "bounded_read_evidence_count": source_v2_bounded_read_count,
            "tests": source_platform_tests,
        },
        "source_profiles": {
            "status": "implemented" if profile_ids else "missing",
            "profile_count": len(profile_ids),
            "profile_ids": profile_ids,
            "tests": profile_tests,
        },
        "replay_fixtures": {
            "status": "implemented"
            if source_contract_v2_ids
            and (
                source_v2_replay_fixture_count + source_v2_non_replayable_reason_count
            )
            == len(source_contract_v2_ids)
            else "partial",
            "record_replay_store": paths["replay_store"].exists(),
            "quarantine_module": paths["quarantine"].exists(),
            "production_entrypoint_count": len(entrypoints),
            "contract_snapshot_count": len(fabric_contract_ids),
            "source_contract_v2_count": len(source_contract_v2_ids),
            "replay_fixture_count": source_v2_replay_fixture_count,
            "non_replayable_reason_count": source_v2_non_replayable_reason_count,
            "tests": replay_tests + source_platform_tests,
        },
        "quality_contracts": {
            "status": "implemented" if source_contract_v2_ids else "partial",
            "quality_module": paths["quality"].exists(),
            "connector_quality_module_count": len(quality_modules),
            "profile_count": len(profile_ids),
            "contract_count": len(fabric_contract_ids),
            "source_contract_v2_count": len(source_contract_v2_ids),
            "tests": quality_tests + source_platform_tests,
        },
        "lineage_nodes_edges": {
            "status": "implemented" if paths["lineage"].exists() else "missing",
            "lineage_module": paths["lineage"].exists(),
            "openlineage_export": _has_token(paths["lineage"], "export_openlineage_json"),
            "prov_export": paths["provo"].exists(),
            "tests": lineage_tests + _existing_paths(repo_root, ["tests/fabric/test_provenance.py"]),
        },
        "temporal_support": {
            "status": "implemented"
            if paths["world_query"].exists() and paths["snapshots"].exists()
            else "missing",
            "world_query": paths["world_query"].exists(),
            "snapshot_store": paths["snapshots"].exists(),
            "runtime_temporal_adapter": paths["temporal_route"].exists()
            and paths["temporal_service"].exists(),
            "tests": temporal_tests,
        },
        "access_classification": {
            "status": "partial",
            "access_control_module": paths["access_control"].exists(),
            "column_mask_module": paths["column_mask"].exists(),
            "pii_stage_module": paths["pii_stage"].exists(),
            "tests": access_tests,
        },
        "observability_governance": {
            "status": "implemented"
            if paths["observability"].exists()
            and paths["connector_governance_metadata"].exists()
            and paths["quality_evidence"].exists()
            else "missing",
            "slo_contract": paths["observability"].exists(),
            "connector_governance_metadata": paths["connector_governance_metadata"].exists(),
            "quality_evidence": paths["quality_evidence"].exists(),
            "tests": phase4_tests,
        },
        "decision_data_envelope": {
            "status": decision_data_status,
            "decision_data_module": paths["decision_data"].exists(),
            "trust_envelope_schema": paths["trust_envelope_schema"].exists(),
            "coverage_report": paths["decision_data_coverage_report"].exists(),
            "naked_decision_values": decision_data_report.get(
                "summary", {}
            ).get("naked_decision_value_count"),
            "typed_gap_states": [
                row.get("state")
                for row in decision_data_report.get("typed_gap_states", [])
                if isinstance(row, Mapping)
            ],
            "tests": decision_data_tests,
        },
        "public_facade_exports": {
            "status": "implemented" if public_exports else "missing",
            "export_count": len(public_exports),
            "exports": public_exports,
            "tests": facade_tests,
        },
        "tests_by_plane": tests_by_plane,
    }
    return (sorted(surfaces, key=lambda row: str(row["id"])), coverage)


def build_manifest(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    surfaces, coverage = _build_surfaces(repo_root)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": GENERATED_AT,
        "phase": PHASE,
        "phase_owner": OWNER,
        "status_model": {
            "allowed_statuses": list(STATUS_VALUES),
            "allowed_priorities": list(PRIORITY_VALUES),
            "allowed_severities": list(PRIORITY_VALUES),
            "planes": list(PLANES),
            "accepted_risk_required_fields": [
                "owner",
                "reason",
                "review_date",
                "expiry_date",
            ],
            "report_only_until": "Wave 1 hardening ratchet",
        },
        "ratchet_mode": {
            "phase_0": "report_only",
            "after_wave_1": (
                "P0/P1 missing entries fail CI unless they carry accepted_risk metadata."
            ),
            "after_phase_6": (
                "decision-bearing untraced, unknown_quality, and non_replayable statuses "
                "require reason codes."
            ),
        },
        "summary": {
            "surface_count": len(surfaces),
            "status_counts": _status_counts(surfaces),
            "plane_counts": _plane_counts(surfaces),
        },
        "coverage": coverage,
        "surfaces": surfaces,
    }


def validate_manifest_payload(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be fabric.best_in_class_manifest.v1")
    if payload.get("phase") != PHASE:
        errors.append("phase must be 0")

    status_model = payload.get("status_model", {})
    if not isinstance(status_model, Mapping):
        errors.append("status_model must be an object")
    else:
        statuses = status_model.get("allowed_statuses", [])
        priorities = status_model.get("allowed_priorities", [])
        severities = status_model.get("allowed_severities", [])
        planes = status_model.get("planes", [])
        if list(statuses) != list(STATUS_VALUES):
            errors.append("status_model.allowed_statuses is out of date")
        if list(priorities) != list(PRIORITY_VALUES):
            errors.append("status_model.allowed_priorities is out of date")
        if list(severities) != list(PRIORITY_VALUES):
            errors.append("status_model.allowed_severities is out of date")
        if list(planes) != list(PLANES):
            errors.append("status_model.planes is out of date")

    surfaces = payload.get("surfaces", [])
    if not isinstance(surfaces, list):
        return errors + ["surfaces must be a list"]

    seen_ids: set[str] = set()
    required_surface_fields = {
        "id",
        "plane",
        "status",
        "priority",
        "severity",
        "phase",
        "owner",
        "source_files",
        "tests",
        "docs",
        "evidence",
    }
    for index, surface in enumerate(surfaces):
        if not isinstance(surface, Mapping):
            errors.append(f"surfaces[{index}] must be an object")
            continue
        surface_id = str(surface.get("id", f"surfaces[{index}]"))
        missing_fields = sorted(required_surface_fields - set(surface))
        if missing_fields:
            errors.append(f"{surface_id}: missing fields: {', '.join(missing_fields)}")
        if surface_id in seen_ids:
            errors.append(f"{surface_id}: duplicate surface id")
        seen_ids.add(surface_id)

        status = surface.get("status")
        priority = surface.get("priority")
        severity = surface.get("severity")
        plane = surface.get("plane")
        if status not in STATUS_VALUES:
            errors.append(f"{surface_id}: invalid status {status!r}")
        if priority not in PRIORITY_VALUES:
            errors.append(f"{surface_id}: invalid priority {priority!r}")
        if severity not in PRIORITY_VALUES:
            errors.append(f"{surface_id}: invalid severity {severity!r}")
        if plane not in PLANES:
            errors.append(f"{surface_id}: invalid plane {plane!r}")
        if surface.get("phase") != PHASE:
            errors.append(f"{surface_id}: phase must be 0")

        for field in ("source_files", "tests", "docs"):
            if not isinstance(surface.get(field), list):
                errors.append(f"{surface_id}: {field} must be a list")
        if not isinstance(surface.get("evidence"), Mapping):
            errors.append(f"{surface_id}: evidence must be an object")

        if status in {"partial", "missing", "blocked_by_research"}:
            if not surface.get("owner") and not surface.get("follow_up"):
                errors.append(f"{surface_id}: gap surfaces require owner or follow_up")
            if not surface.get("follow_up"):
                errors.append(f"{surface_id}: gap surfaces require a follow_up placeholder")

        if status == "accepted_risk":
            risk = surface.get("accepted_risk")
            if not isinstance(risk, Mapping):
                errors.append(f"{surface_id}: accepted_risk metadata is required")
            else:
                for field in ("owner", "reason", "review_date", "expiry_date"):
                    if not risk.get(field):
                        errors.append(f"{surface_id}: accepted_risk.{field} is required")

    summary = payload.get("summary", {})
    if isinstance(summary, Mapping):
        status_counts = summary.get("status_counts", {})
        if isinstance(status_counts, Mapping):
            for status in STATUS_VALUES:
                if status not in status_counts:
                    errors.append(f"summary.status_counts missing {status}")
    return errors


def dump_json(data: Mapping[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, indent=2) + "\n"


def _md_escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _md_code_list(values: Iterable[str], *, limit: int = 5) -> str:
    rows = [f"`{value}`" for value in values]
    if not rows:
        return "-"
    if len(rows) <= limit:
        return ", ".join(rows)
    return ", ".join(rows[:limit]) + f", +{len(rows) - limit} more"


def _evidence_summary(evidence: Mapping[str, Any]) -> str:
    rows: list[str] = []
    for key, value in evidence.items():
        if isinstance(value, bool):
            rows.append(f"{key}={str(value).lower()}")
        elif isinstance(value, int):
            rows.append(f"{key}={value}")
        elif isinstance(value, str):
            rows.append(f"{key}=`{value}`")
        elif isinstance(value, (Mapping, list)):
            rows.append(f"{key}={len(value)}")
        if len(rows) == 4:
            break
    return _md_escape("; ".join(rows) if rows else "-")


def _plane_title(plane: str) -> str:
    return {
        "source": "Source",
        "evidence": "Evidence",
        "semantics": "Semantics",
        "world": "World",
        "trust": "Trust",
    }[plane]


def render_markdown(manifest: Mapping[str, Any]) -> str:
    surfaces = [
        surface
        for surface in manifest.get("surfaces", [])
        if isinstance(surface, Mapping)
    ]
    summary = manifest.get("summary", {})
    coverage = manifest.get("coverage", {})
    status_counts = summary.get("status_counts", {}) if isinstance(summary, Mapping) else {}
    plane_counts = summary.get("plane_counts", {}) if isinstance(summary, Mapping) else {}

    lines = [
        "# Fabric Best-in-Class Inventory",
        "",
        "Freshness: 2026-04-26.",
        f"Owner: `{OWNER}`",
        "Phase: 0 baseline inventory.",
        "",
        "This page is generated from "
        "`tools/quality/validation/fabric_best_in_class_manifest.json` by "
        "`tools/quality/validation/fabric_best_in_class_inventory.py`.",
        "",
        "Phase 0 is report-only: `--check` fails only when the committed manifest "
        "or report drift from the current repository inventory. It does not fail "
        "because a surface is `partial`, `missing`, `accepted_risk`, or "
        "`blocked_by_research`.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| ------ | ----- |",
        f"| Schema version | `{manifest.get('schema_version')}` |",
        f"| Generated at | `{manifest.get('generated_at')}` |",
        f"| Surface count | {summary.get('surface_count', 0) if isinstance(summary, Mapping) else 0} |",
    ]
    for status in STATUS_VALUES:
        lines.append(f"| `{status}` | {status_counts.get(status, 0)} |")
    for plane in PLANES:
        lines.append(f"| `{plane}` plane surfaces | {plane_counts.get(plane, 0)} |")

    lines.extend(
        [
            "",
            "## Coverage Report",
            "",
            "| Coverage Area | Status | Evidence |",
            "| ------------- | ------ | -------- |",
        ]
    )
    if isinstance(coverage, Mapping):
        for key in (
            "source_contracts",
            "source_platform",
            "source_profiles",
            "replay_fixtures",
            "quality_contracts",
            "lineage_nodes_edges",
            "temporal_support",
            "access_classification",
            "observability_governance",
            "public_facade_exports",
        ):
            item = coverage.get(key, {})
            if not isinstance(item, Mapping):
                continue
            lines.append(
                f"| `{key}` | `{item.get('status', 'missing')}` | "
                f"{_evidence_summary(item)} |"
            )

        tests_by_plane = coverage.get("tests_by_plane", {})
        if isinstance(tests_by_plane, Mapping):
            lines.extend(
                [
                    "",
                    "## Tests By Plane",
                    "",
                    "| Plane | Tests |",
                    "| ----- | ----- |",
                ]
            )
            for plane in PLANES:
                tests = tests_by_plane.get(plane, [])
                values = [str(test) for test in tests] if isinstance(tests, list) else []
                lines.append(f"| {_plane_title(plane)} | {_md_code_list(values, limit=8)} |")

    for plane in PLANES:
        plane_surfaces = [
            surface for surface in surfaces if surface.get("plane") == plane
        ]
        lines.extend(
            [
                "",
                f"## {_plane_title(plane)} Plane",
                "",
                "| ID | Status | Priority | Title | Evidence | Follow-up |",
                "| -- | ------ | -------- | ----- | -------- | --------- |",
            ]
        )
        for surface in plane_surfaces:
            follow_up = surface.get("follow_up", "")
            if surface.get("status") == "accepted_risk":
                risk = surface.get("accepted_risk", {})
                if isinstance(risk, Mapping):
                    follow_up = (
                        f"accepted risk: {risk.get('reason', '-')}; "
                        f"review {risk.get('review_date', '-')}; "
                        f"expires {risk.get('expiry_date', '-')}"
                    )
            lines.append(
                "| "
                f"`{surface.get('id')}` | "
                f"`{surface.get('status')}` | "
                f"`{surface.get('priority')}` | "
                f"{_md_escape(surface.get('title', ''))} | "
                f"{_evidence_summary(surface.get('evidence', {}))} | "
                f"{_md_escape(follow_up or '-')} |"
            )

    gap_surfaces = [
        surface
        for surface in surfaces
        if surface.get("status")
        in {"partial", "missing", "accepted_risk", "blocked_by_research"}
    ]
    gap_surfaces.sort(
        key=lambda surface: (
            str(surface.get("priority", "")),
            str(surface.get("status", "")),
            str(surface.get("id", "")),
        )
    )
    lines.extend(
        [
            "",
            "## Gaps By Phase And Priority",
            "",
            "| Priority | Phase | Status | ID | Owner | Follow-up / Risk |",
            "| -------- | ----- | ------ | -- | ----- | ---------------- |",
        ]
    )
    for surface in gap_surfaces:
        follow_up = surface.get("follow_up", "")
        if surface.get("status") == "accepted_risk":
            risk = surface.get("accepted_risk", {})
            if isinstance(risk, Mapping):
                follow_up = (
                    f"{risk.get('reason', '-')}; review {risk.get('review_date', '-')}; "
                    f"expires {risk.get('expiry_date', '-')}"
                )
        lines.append(
            "| "
            f"`{surface.get('priority')}` | "
            f"{surface.get('phase')} | "
            f"`{surface.get('status')}` | "
            f"`{surface.get('id')}` | "
            f"`{surface.get('owner')}` | "
            f"{_md_escape(follow_up or FOLLOW_UP_PLACEHOLDER)} |"
        )

    lines.extend(
        [
            "",
            "## Ratchet Mode",
            "",
            "| Stage | Behavior |",
            "| ----- | -------- |",
            "| First PR | Report-only drift check for manifest/report freshness. |",
            "| After Wave 1 hardening | P0/P1 `missing` entries fail CI unless they carry `accepted_risk`. |",
            "| After Phase 6 | Decision-bearing `untraced`, `unknown_quality`, and `non_replayable` statuses require reason codes. |",
            "",
            "## Validation",
            "",
            "```bash",
            "uv run python tools/quality/validation/fabric_best_in_class_inventory.py --check",
            "uv run bash tools/quality/validation/run_fabric_best_in_class_inventory.sh",
            "uv run pytest tests/tools/test_fabric_best_in_class_inventory.py -q",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def check_artifacts(
    *,
    repo_root: Path,
    manifest_path: Path,
    docs_path: Path,
) -> list[str]:
    manifest = build_manifest(repo_root)
    errors = validate_manifest_payload(manifest)
    if errors:
        return errors

    expected_manifest = dump_json(manifest)
    expected_report = render_markdown(manifest)

    drift: list[str] = []
    if not manifest_path.exists():
        drift.append(f"manifest missing: {_rel(manifest_path, repo_root)}")
    elif manifest_path.read_text(encoding="utf-8") != expected_manifest:
        drift.append(f"manifest out of date: {_rel(manifest_path, repo_root)}")

    if not docs_path.exists():
        drift.append(f"report missing: {_rel(docs_path, repo_root)}")
    elif docs_path.read_text(encoding="utf-8") != expected_report:
        drift.append(f"report out of date: {_rel(docs_path, repo_root)}")
    return drift


def update_artifacts(
    *,
    repo_root: Path,
    manifest_path: Path,
    docs_path: Path,
) -> dict[str, Any]:
    manifest = build_manifest(repo_root)
    errors = validate_manifest_payload(manifest)
    if errors:
        raise ValueError("\n".join(errors))
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(manifest_path, dump_json(manifest))
    atomic_write_text(docs_path, render_markdown(manifest))
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.check and args.update:
        print("ERROR: --check and --update are mutually exclusive")
        return 2

    repo_root = args.repo_root.resolve()
    manifest_path = _resolve_path(args.manifest, repo_root)
    docs_path = _resolve_path(args.docs_out, repo_root)

    if args.update:
        try:
            update_artifacts(
                repo_root=repo_root,
                manifest_path=manifest_path,
                docs_path=docs_path,
            )
        except ValueError as exc:
            print("Fabric best-in-class inventory update FAILED")
            print(exc)
            return 1
        print(f"Updated Fabric best-in-class manifest: {_rel(manifest_path, repo_root)}")
        print(f"Updated Fabric best-in-class report: {_rel(docs_path, repo_root)}")
        return 0

    if args.check:
        drift = check_artifacts(
            repo_root=repo_root,
            manifest_path=manifest_path,
            docs_path=docs_path,
        )
        if drift:
            print("Fabric best-in-class inventory check FAILED")
            for row in drift:
                print(f"- {row}")
            print(
                "Run: uv run python tools/quality/validation/"
                "fabric_best_in_class_inventory.py --update"
            )
            return 1
        print("Fabric best-in-class inventory check PASSED (report-only)")
        return 0

    manifest = build_manifest(repo_root)
    errors = validate_manifest_payload(manifest)
    if errors:
        print("Fabric best-in-class inventory is invalid", file=sys.stderr)
        for row in errors:
            print(f"- {row}", file=sys.stderr)
        return 1
    print(dump_json(manifest), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
