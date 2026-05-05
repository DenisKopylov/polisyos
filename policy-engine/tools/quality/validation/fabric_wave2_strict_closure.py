#!/usr/bin/env python3
"""Validate strict Fabric Wave 2 best-in-class closure without Wave R scope."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from tools.quality.validation import (
    fabric_best_in_class_inventory,
    fabric_source_contracts,
)

REPORT_SCHEMA_VERSION = "fabric.wave2_strict_closure_report.v1"
R_EXCLUDED_SURFACES = frozenset(
    {
        "world.kuzu_temporal_scope_capability",
        "world.temporal_graph_reasoning",
    }
)
STRICT_ALLOWED_STATUSES = frozenset({"implemented", "not_applicable"})


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--report", action="store_true", help="Print report JSON")
    parser.add_argument("--check", action="store_true", help="Fail on strict Wave 2 gaps")
    return parser.parse_args(argv)


def _surface_by_id(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    surfaces = manifest.get("surfaces", [])
    if not isinstance(surfaces, list):
        return {}
    return {
        str(surface.get("id")): dict(surface)
        for surface in surfaces
        if isinstance(surface, Mapping)
    }


def build_report(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Build a strict closeout report from generated Fabric Wave 2 evidence."""

    manifest = fabric_best_in_class_inventory.build_manifest(repo_root)
    source_platform = fabric_source_contracts.build_report()
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": fabric_best_in_class_inventory.GENERATED_AT,
        "scope": {
            "wave": "Wave 2",
            "research_excluded_surfaces": sorted(R_EXCLUDED_SURFACES),
            "allowed_non_r_statuses": sorted(STRICT_ALLOWED_STATUSES),
        },
        "manifest": manifest,
        "source_platform": source_platform,
        "checks": {
            "source_contract_artifacts": fabric_source_contracts.check_artifacts(),
            "source_contract_report": fabric_source_contracts.validate_report(
                source_platform,
                fail_closed=True,
            ),
            "inventory_manifest": fabric_best_in_class_inventory.validate_manifest_payload(
                manifest
            ),
        },
    }


def validate_report(report: Mapping[str, Any]) -> list[str]:
    """Return strict Wave 2 closure violations."""

    errors: list[str] = []
    manifest = report.get("manifest", {})
    if not isinstance(manifest, Mapping):
        return ["strict closure report missing manifest"]
    surfaces = _surface_by_id(manifest)

    for error in report.get("checks", {}).get("inventory_manifest", []):
        errors.append(f"inventory manifest invalid: {error}")
    for error in report.get("checks", {}).get("source_contract_report", []):
        errors.append(f"source platform report invalid: {error}")
    for error in report.get("checks", {}).get("source_contract_artifacts", []):
        errors.append(f"source platform artifact drift: {error}")

    for surface_id, surface in sorted(surfaces.items()):
        if surface_id in R_EXCLUDED_SURFACES:
            continue
        status = str(surface.get("status"))
        if status not in STRICT_ALLOWED_STATUSES:
            errors.append(
                f"non-R surface {surface_id} is {status}; strict closure allows only "
                "implemented or not_applicable"
            )

    coverage = manifest.get("coverage", {})
    if not isinstance(coverage, Mapping):
        errors.append("manifest coverage is missing")
        return errors
    source_platform = coverage.get("source_platform", {})
    replay = coverage.get("replay_fixtures", {})
    access = coverage.get("access_classification", {})
    if not isinstance(source_platform, Mapping):
        errors.append("source_platform coverage is missing")
        source_platform = {}
    if not isinstance(replay, Mapping):
        errors.append("replay_fixtures coverage is missing")
        replay = {}
    if not isinstance(access, Mapping):
        errors.append("access_classification coverage is missing")
        access = {}

    contract_count = int(source_platform.get("source_contract_v2_count") or 0)
    replay_fixture_count = int(source_platform.get("replay_fixture_count") or 0)
    non_replayable_count = int(source_platform.get("non_replayable_reason_count") or 0)
    if replay_fixture_count != contract_count:
        errors.append(
            "strict replay coverage requires replay_fixture_count == source_contract_v2_count"
        )
    if non_replayable_count != 0:
        errors.append("strict replay coverage requires non_replayable_reason_count == 0")
    if replay.get("status") != "implemented":
        errors.append("replay_fixtures coverage must be implemented")
    if access.get("status") != "implemented":
        errors.append("access_classification coverage must be implemented")

    entrypoint_surface = surfaces.get("source.entrypoint_coverage.direct_import_families")
    if not entrypoint_surface or entrypoint_surface.get("status") != "implemented":
        errors.append("production connector entrypoint/internal governance is incomplete")
    else:
        evidence = entrypoint_surface.get("evidence", {})
        if isinstance(evidence, Mapping):
            governed = int(evidence.get("governed_component_count") or 0)
            concrete = int(evidence.get("concrete_connector_count") or 0)
            if governed != concrete:
                errors.append(
                    "production connector governance requires governed_component_count "
                    "to match concrete_connector_count"
                )

    future_surface = surfaces.get("world.future_table_snapshot_adapters")
    if not future_surface or future_surface.get("status") != "not_applicable":
        errors.append("future table snapshot adapters must be not_applicable for strict Wave 2")
    else:
        evidence = future_surface.get("evidence", {})
        if isinstance(evidence, Mapping) and evidence.get("production_visible") is not False:
            errors.append("future table snapshot adapters must not be production-visible")

    for research_surface in R_EXCLUDED_SURFACES:
        surface = surfaces.get(research_surface)
        if not surface:
            errors.append(f"missing research-excluded surface: {research_surface}")
            continue
        if surface.get("status") not in {"partial", "blocked_by_research"}:
            errors.append(
                f"research-excluded surface {research_surface} must remain explicitly "
                "partial or blocked_by_research"
            )

    return errors


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    report = build_report(args.repo_root.resolve())
    if args.report:
        print(json.dumps(report, indent=2, sort_keys=True), end="\n")
    errors = validate_report(report) if args.check else []
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    if args.check:
        print("Fabric Wave 2 strict closure PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
