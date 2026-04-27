#!/usr/bin/env python3
"""Validate Fabric SourceContract v2 coverage and source scorecards."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools._lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from polisyos.fabric.connectors.components import __polisyos_components__  # noqa: E402
from polisyos.fabric.connectors.contracts import (  # noqa: E402
    SOURCE_CONTRACT_SCHEMA_VERSION,
    SourceContract,
    source_contracts_compatibility_evidence,
    source_contracts_snapshot_payload,
)
from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry  # noqa: E402
from polisyos.fabric.connectors.scorecard import (  # noqa: E402
    build_source_scorecards,
    render_scorecards_markdown,
    source_scorecards_snapshot_payload,
)
from polisyos.fabric.connectors.sdk import (  # noqa: E402
    SourceScaffoldSpec,
    build_source_contract_scaffold,
    build_source_profile_matrix,
    make_source_contract_id,
)
from polisyos.fabric.connectors.sources._contracts import ALL_SOURCE_CONTRACTS  # noqa: E402
from polisyos.fabric.connectors.testing.conformance import (  # noqa: E402
    ConformanceReport,
    validate_source_conformance_v2,
)
from polisyos.fabric.io.atomic import atomic_write_text  # noqa: E402

REPORT_SCHEMA_VERSION = "fabric.source_platform_report.v1"
GENERATED_AT = "2026-04-27T00:00:00Z"
SOURCE_CONTRACT_SNAPSHOT = (
    REPO_ROOT / "schemas" / "snapshots" / "fabric" / "source_contracts_v2.json"
)
SOURCE_SCORECARD_SNAPSHOT = (
    REPO_ROOT / "schemas" / "snapshots" / "fabric" / "source_scorecards.json"
)
SOURCE_PLATFORM_DOC = REPO_ROOT / "docs" / "reference" / "fabric" / "source-platform.md"
GENERATED_AT_DT = datetime(2026, 4, 27, tzinfo=UTC)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true", help="Print report JSON")
    parser.add_argument("--check", action="store_true", help="Check generated artifacts")
    parser.add_argument("--update", action="store_true", help="Update generated artifacts")
    parser.add_argument(
        "--fail-closed",
        action="store_true",
        help=(
            "Fail when production source conformance errors are present "
            "or generated evidence artifacts drift"
        ),
    )
    parser.add_argument("--snapshot", type=Path, default=SOURCE_CONTRACT_SNAPSHOT)
    parser.add_argument("--scorecards", type=Path, default=SOURCE_SCORECARD_SNAPSHOT)
    parser.add_argument("--docs", type=Path, default=SOURCE_PLATFORM_DOC)
    return parser.parse_args(argv)


def _schema_contract_by_connector() -> dict[str, Any]:
    return {
        contract.connector_id: contract
        for contract in sorted(ALL_SOURCE_CONTRACTS, key=lambda item: item.contract_id)
    }


def production_connector_classes() -> tuple[type, ...]:
    """Return production-visible connector classes from component metadata."""

    return tuple(
        component.connector_class
        for component in sorted(
            __polisyos_components__,
            key=lambda item: item.connector_class.metadata.fully_qualified_id,
        )
    )


def build_source_contracts() -> tuple[SourceContract, ...]:
    """Build SourceContract v2 coverage for every production-visible connector."""

    schema_contracts = _schema_contract_by_connector()
    contracts: list[SourceContract] = []
    for connector_class in production_connector_classes():
        metadata = connector_class.metadata
        connector_id = f"{metadata.namespace}.{metadata.connector_id}"
        schema_contract = schema_contracts.get(connector_id)
        contract_id = (
            schema_contract.contract_id
            if schema_contract is not None
            else make_source_contract_id(connector_id, "*")
        )
        contract = build_source_contract_scaffold(
            metadata=metadata,
            schema_contract=schema_contract,
            spec=SourceScaffoldSpec(
                connector_id=connector_id,
                contract_id=contract_id,
                dataset_pattern=schema_contract.dataset_id if schema_contract else "*",
                owner=metadata.owner,
                quality_contract_id=metadata.quality_contract_id,
            ),
        )
        contracts.append(contract)
    return tuple(sorted(contracts, key=lambda item: item.id))


def build_conformance_reports(
    contracts: tuple[SourceContract, ...],
) -> tuple[ConformanceReport, ...]:
    """Run conformance v2 over every production connector."""

    profiles = tuple(SourceProfileRegistry.get_instance().list_all())
    schema_contracts = tuple(ALL_SOURCE_CONTRACTS)
    by_connector = {contract.source.connector_id: contract for contract in contracts}
    reports: list[ConformanceReport] = []
    for connector_class in production_connector_classes():
        metadata = connector_class.metadata
        connector_id = f"{metadata.namespace}.{metadata.connector_id}"
        contract = by_connector[connector_id]
        reports.append(
            validate_source_conformance_v2(
                connector_class=connector_class,
                source_contract=contract,
                profiles=profiles,
                schema_contracts=schema_contracts,
                replay_fixture_exists=(
                    (REPO_ROOT / contract.replay.fixture_ref).exists()
                    if contract.replay.fixture_ref
                    else None
                ),
            )
        )
    return tuple(sorted(reports, key=lambda item: item.source_contract_id))


def build_report() -> dict[str, Any]:
    """Build the Phase 5 Source Platform report."""

    contracts = build_source_contracts()
    profiles = tuple(SourceProfileRegistry.get_instance().list_all())
    reports = build_conformance_reports(contracts)
    scorecards = build_source_scorecards(
        contracts,
        generated_at=GENERATED_AT_DT,
    )
    issue_rows = [
        {
            "source_contract_id": report.source_contract_id,
            "connector_id": report.connector_id,
            "check_id": issue.check_id,
            "severity": issue.severity,
            "message": issue.message,
        }
        for report in reports
        for issue in report.issues
    ]
    errors = [issue for issue in issue_rows if issue["severity"] == "error"]
    warnings = [issue for issue in issue_rows if issue["severity"] != "error"]
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": GENERATED_AT,
        "source_contract_schema_version": SOURCE_CONTRACT_SCHEMA_VERSION,
        "summary": {
            "production_connector_count": len(production_connector_classes()),
            "source_contract_count": len(contracts),
            "conformance_passed_count": sum(1 for report in reports if report.passed),
            "conformance_error_count": len(errors),
            "conformance_warning_count": len(warnings),
            "scorecard_count": len(scorecards),
        },
        "compatibility_evidence": source_contracts_compatibility_evidence(contracts),
        "profile_compatibility_matrix": build_source_profile_matrix(contracts, profiles),
        "contracts": [contract.to_snapshot_record() for contract in contracts],
        "conformance": [
            {
                "connector_id": report.connector_id,
                "source_contract_id": report.source_contract_id,
                "passed": report.passed,
                "issues": [
                    {
                        "check_id": issue.check_id,
                        "severity": issue.severity,
                        "message": issue.message,
                        "evidence": dict(issue.evidence or {}),
                    }
                    for issue in report.issues
                ],
            }
            for report in reports
        ],
        "scorecards": [scorecard.model_dump(mode="json") for scorecard in scorecards],
    }


def source_contract_snapshot_json() -> str:
    return dump_json(
        source_contracts_snapshot_payload(
            build_source_contracts(),
            generated_at=GENERATED_AT,
        )
    )


def source_scorecard_snapshot_json() -> str:
    generated_at = "2026-04-27T00:00:00+00:00"
    scorecards = build_source_scorecards(
        build_source_contracts(),
        generated_at=GENERATED_AT_DT,
    )
    return dump_json(
        source_scorecards_snapshot_payload(scorecards, generated_at=generated_at)
    )


def render_source_platform_markdown(report: dict[str, Any] | None = None) -> str:
    """Render the generated Fabric source-platform reference page."""

    report = report or build_report()
    contracts = build_source_contracts()
    scorecards = build_source_scorecards(
        contracts,
        generated_at=GENERATED_AT_DT,
    )
    matrix = report["profile_compatibility_matrix"]
    lines = [
        "# Fabric Source Platform",
        "",
        "Related explanation: [Data Fabric](../../explanation/data-fabric.md).",
        "",
        "Best-in-class inventory: [best-in-class-inventory.md](best-in-class-inventory.md).",
        "",
        "Phase 5 makes production source admission contract-first. A connector is",
        "production-visible only when SourceContract v2, profile compatibility,",
        "quality, replay or non-replayable reason, lineage, access, owner/reviewer,",
        "SLO, scorecard, and docs evidence are present.",
        "",
        "## Generated Artifacts",
        "",
        "| Artifact | Purpose |",
        "| -------- | ------- |",
        "| `schemas/fabric/source_contract.schema.json` | SourceContract v2 schema |",
        "| `schemas/fabric/source_scorecard.schema.json` | Source scorecard schema |",
        "| `schemas/snapshots/fabric/source_contracts_v2.json` | Production SourceContract snapshot |",
        "| `schemas/snapshots/fabric/source_scorecards.json` | Generated source scorecards |",
        "| `tools/quality/validation/fabric_source_contracts.py` | CI report/fail-closed gate |",
        "",
        "## CI Gate",
        "",
        "Report-only mode:",
        "",
        "```bash",
        "uv run python tools/quality/validation/fabric_source_contracts.py --report",
        "```",
        "",
        "Artifact check:",
        "",
        "```bash",
        "uv run python tools/quality/validation/fabric_source_contracts.py --check",
        "```",
        "",
        "Fail-closed mode rejects production connectors without SourceContract v2",
        "and conformance evidence:",
        "",
        "```bash",
        "uv run python tools/quality/validation/fabric_source_contracts.py --fail-closed",
        "```",
        "",
        "## Source Scorecards",
        "",
        render_scorecards_markdown(scorecards),
        "",
        "## Profile Compatibility Matrix",
        "",
        "| Source contract | Connector | Profile | Present | Family | Schema preflight | Async fetch |",
        "| --------------- | --------- | ------- | ------- | ------ | ---------------- | ----------- |",
    ]
    for row in matrix:
        lines.append(
            "| "
            f"`{row['source_contract_id']}` | "
            f"`{row['connector_id']}` | "
            f"`{row['profile_id']}` | "
            f"{row['profile_present']} | "
            f"`{row['connector_family']}` | "
            f"{row['schema_preflight']} | "
            f"{row['supports_async_fetch']} |"
        )
    lines.extend(
        [
            "",
            "## Source Contract Catalog",
            "",
            "| Contract | Connector | Profile | Quality | Replay | Classification | Owner | Reviewer |",
            "| -------- | --------- | ------- | ------- | ------ | -------------- | ----- | -------- |",
        ]
    )
    for contract in contracts:
        replay = contract.replay.fixture_ref or contract.replay.non_replayable_reason or ""
        lines.append(
            "| "
            f"`{contract.id}` | "
            f"`{contract.source.connector_id}` | "
            f"`{contract.source.profile_id}` | "
            f"`{contract.quality.contract_ref}` | "
            f"{replay} | "
            f"`{contract.security.classification}` | "
            f"`{contract.owner}` | "
            f"`{contract.reviewer}` |"
        )
    lines.extend(
        [
            "",
            "## Deprecation And Sunset Policy",
            "",
            "A production source moves from `active` to `deprecated` only with an owner,",
            "reviewer, reason, migration note, replacement contract when available,",
            "and a sunset date. During deprecation, scorecards remain generated and",
            "the CI gate continues to require replay, lineage, access, and SLO evidence.",
            "A `sunset` source remains in snapshots for historical replay but must not",
            "be selected for new production fetch plans.",
            "",
            "## Validation Anchors",
            "",
            "- `tests/fabric/connectors/test_source_contract_v2.py` validates the model,",
            "  scaffold, conformance harness, scorecards, and generated snapshots.",
            "- `tests/tools/test_fabric_source_contracts.py` validates CI report/check",
            "  behavior and source-platform docs generation.",
        ]
    )
    return "\n".join(lines) + "\n"


def dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def check_artifacts(
    *,
    snapshot_path: Path = SOURCE_CONTRACT_SNAPSHOT,
    scorecard_path: Path = SOURCE_SCORECARD_SNAPSHOT,
    docs_path: Path = SOURCE_PLATFORM_DOC,
) -> list[str]:
    """Return artifact drift errors."""

    errors: list[str] = []
    expected_snapshot = source_contract_snapshot_json()
    expected_scorecards = source_scorecard_snapshot_json()
    expected_docs = render_source_platform_markdown()
    if not snapshot_path.exists() or snapshot_path.read_text(encoding="utf-8") != expected_snapshot:
        errors.append(f"source contract snapshot out of date: {snapshot_path}")
    if not scorecard_path.exists() or scorecard_path.read_text(encoding="utf-8") != expected_scorecards:
        errors.append(f"source scorecard snapshot out of date: {scorecard_path}")
    if not docs_path.exists() or docs_path.read_text(encoding="utf-8") != expected_docs:
        errors.append(f"source platform docs out of date: {docs_path}")
    return errors


def validate_report(report: dict[str, Any], *, fail_closed: bool = False) -> list[str]:
    """Validate report semantics for CI."""

    errors: list[str] = []
    summary = report.get("summary", {})
    if summary.get("production_connector_count") != summary.get("source_contract_count"):
        errors.append("production connector count does not match SourceContract count")
    if fail_closed and int(summary.get("conformance_error_count", 0)) > 0:
        errors.append("conformance errors present in fail-closed mode")
    return errors


def update_artifacts(
    *,
    snapshot_path: Path = SOURCE_CONTRACT_SNAPSHOT,
    scorecard_path: Path = SOURCE_SCORECARD_SNAPSHOT,
    docs_path: Path = SOURCE_PLATFORM_DOC,
) -> None:
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    scorecard_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(snapshot_path, source_contract_snapshot_json())
    atomic_write_text(scorecard_path, source_scorecard_snapshot_json())
    atomic_write_text(docs_path, render_source_platform_markdown())


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    report = build_report()

    report_errors = validate_report(report, fail_closed=args.fail_closed)
    if args.report:
        print(dump_json(report), end="")

    if args.update:
        update_artifacts(
            snapshot_path=args.snapshot,
            scorecard_path=args.scorecards,
            docs_path=args.docs,
        )
        print(f"Updated SourceContract snapshot: {args.snapshot}")
        print(f"Updated source scorecards: {args.scorecards}")
        print(f"Updated source platform docs: {args.docs}")

    artifact_errors: list[str] = []
    if args.check or args.fail_closed:
        artifact_errors = check_artifacts(
            snapshot_path=args.snapshot,
            scorecard_path=args.scorecards,
            docs_path=args.docs,
        )

    errors = report_errors + artifact_errors
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    if args.check:
        print("Fabric SourceContract v2 artifacts check PASSED")
    if args.fail_closed:
        print("Fabric SourceContract v2 fail-closed gate PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
