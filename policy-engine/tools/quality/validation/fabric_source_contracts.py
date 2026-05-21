#!/usr/bin/env python3
"""Validate Fabric SourceContract v2 coverage and source scorecards."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from polisyos.fabric.catalog.source_selection_audit import (  # noqa: E402
    build_fabric_source_selection_trace,
    normalize_fabric_retrieval_trace,
)
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
    make_replay_fixture_id,
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
SOURCE_REPLAY_FIXTURE_DIR = REPO_ROOT / "tests" / "_data" / "fabric" / "shared" / "source_contracts"
GENERATED_AT_DT = datetime(2026, 4, 27, tzinfo=UTC)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root used for resolving a report output path.",
    )
    parser.add_argument(
        "--report",
        nargs="?",
        const="-",
        default=None,
        help="Print report JSON, or write it to the provided path.",
    )
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
    parser.add_argument("--replay-fixtures", type=Path, default=SOURCE_REPLAY_FIXTURE_DIR)
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
                replay_fixture_ref=make_replay_fixture_id(contract_id),
            ),
        )
        contracts.append(contract)
    return tuple(sorted(contracts, key=lambda item: item.id))


def _checksum(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _sample_value(field: Any) -> Any:
    data_type = str(
        getattr(getattr(field, "data_type", ""), "value", getattr(field, "data_type", ""))
    ).lower()
    if "bool" in data_type:
        return True
    if "int" in data_type or "uint" in data_type:
        return 2026
    if "float" in data_type or "decimal" in data_type:
        return 1.0
    if "date" in data_type or "time" in data_type:
        return GENERATED_AT
    if "array" in data_type:
        return []
    if "object" in data_type or "json" in data_type:
        return {}
    return f"{field.name}_sample"


def build_source_replay_fixture(contract: SourceContract) -> dict[str, Any]:
    """Build one deterministic replay fixture for a production SourceContract."""

    fields = tuple(contract.schema.fields)
    normalized_sample_rows = [
        {field.name: _sample_value(field) for field in fields}
        if fields
        else {"source_contract_id": contract.id}
    ]
    schema_payload = {
        "schema_id": contract.schema.schema_id,
        "schema_version": contract.schema.schema_version,
        "fields": [
            {
                "name": field.name,
                "field_id": field.stable_id,
                "data_type": str(getattr(field.data_type, "value", field.data_type)),
                "semantic_type": (
                    None
                    if field.semantic_type is None
                    else str(getattr(field.semantic_type, "value", field.semantic_type))
                ),
            }
            for field in fields
        ],
    }
    payload: dict[str, Any] = {
        "schema_version": "fabric.source_replay_fixture.v1",
        "source_contract_id": contract.id,
        "connector_id": contract.source.connector_id,
        "profile_id": contract.source.profile_id,
        "generated_at": GENERATED_AT,
        "schema_checksum": _checksum(schema_payload),
        "transcript": {
            "request": {
                "method": "GET",
                "url": f"fabric://{contract.source.connector_id}/{contract.source.dataset_pattern}",
                "connector_id": contract.source.connector_id,
                "dataset_pattern": contract.source.dataset_pattern,
                "profile_id": contract.source.profile_id,
            },
            "response": {
                "status": 200,
                "content_type": "application/json",
                "body": {"rows": normalized_sample_rows},
            },
        },
        "normalized_sample_rows": normalized_sample_rows,
        "replay_checksum": "",
    }
    payload["replay_checksum"] = _checksum(
        {key: value for key, value in payload.items() if key != "replay_checksum"}
    )
    return payload


def source_replay_fixture_json(contract: SourceContract) -> str:
    return dump_json(build_source_replay_fixture(contract))


def expected_source_replay_fixtures() -> dict[str, str]:
    """Return expected replay fixture JSON by checked-in fixture file name."""

    return {
        f"{contract.id}.replay.json": source_replay_fixture_json(contract)
        for contract in build_source_contracts()
    }


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
    compatibility = source_contracts_compatibility_evidence(contracts)
    replay_fixture_artifact_count = sum(
        1
        for contract in contracts
        if contract.replay.fixture_ref and (REPO_ROOT / contract.replay.fixture_ref).exists()
    )
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
            "replay_fixture_count": compatibility["replay_fixture_count"],
            "replay_fixture_artifact_count": replay_fixture_artifact_count,
            "non_replayable_reason_count": compatibility["non_replayable_reason_count"],
            "field_access_policy_contract_count": compatibility[
                "field_access_policy_contract_count"
            ],
            "field_access_policy_count": compatibility["field_access_policy_count"],
            "schema_field_policy_coverage_count": compatibility[
                "schema_field_policy_coverage_count"
            ],
        },
        "compatibility_evidence": compatibility,
        "profile_compatibility_matrix": build_source_profile_matrix(contracts, profiles),
        "source_selection_state_machine": build_source_selection_state_machine_report(),
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


def build_source_selection_state_machine_report() -> dict[str, Any]:
    """Build synthetic checks for Fabric scenario source selection semantics."""

    scenario_contract = {
        "schema_version": "policyos.scenario_evidence_contract.v1",
        "contract_id": "scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1",
        "scenario_id": "ukraine_msme_wartime_credit_support",
        "requirements": [
            {
                "requirement_id": (
                    "scenario:ukraine_msme_wartime_credit_support:data:"
                    "production_msme_panel"
                ),
                "domain": "data",
                "expected_family": "production_msme_panel",
                "required_facets": ["dictionary_ref", "schema_ref", "lineage_refs"],
            }
        ],
    }
    broad_trace = build_fabric_source_selection_trace(
        query_intent={"policy_domain": "wartime_msme_support"},
        candidate_sources=[
            {
                "source_id": "production-data-datasets-bundle",
                "source_family": "datasets",
                "source_kind": "production_data",
                "freshness": {"status": "pass"},
                "coverage": {"status": "pass"},
                "schema_compatibility": {"status": "pass"},
                "relevance_rationale": "Context inventory only.",
                "source_rights": "public",
                "dictionary_ref": "dictionary:datasets:v1",
                "schema_ref": "schema:datasets:v1",
                "field_refs": ["field:any"],
                "unit_refs": ["unit:any"],
                "geography_refs": ["UA"],
                "time_coverage_refs": ["2026"],
                "quality_refs": ["quality:datasets:v1"],
                "missingness_refs": ["missingness:datasets:v1"],
                "freshness_refs": ["freshness:datasets:v1"],
                "lineage_refs": ["lineage:datasets:v1"],
                "transformation_refs": ["transform:datasets:v1"],
                "data_forge_snapshot_refs": ["sha256:" + "1" * 64],
                "derived_features": [{"feature_ref": "feature:any"}],
            }
        ],
        selected_source_ids=["production-data-datasets-bundle"],
        rejected_sources=[],
        scenario_evidence_contract=scenario_contract,
        production_data_contract_binding_report={
            "scenario_contract_id": scenario_contract["contract_id"],
            "scenario_binding_findings": [
                {
                    "requirement_id": scenario_contract["requirements"][0][
                        "requirement_id"
                    ],
                    "expected_family": "production_msme_panel",
                    "candidate_ref": None,
                    "status": "blocked",
                    "missing_facets": ["dictionary_ref", "schema_ref", "lineage_refs"],
                }
            ],
        },
    )
    contract_ref = "production_data:curated:production_msme_panel:contract.production_msme_panel"
    selected_trace = build_fabric_source_selection_trace(
        query_intent={"policy_domain": "wartime_msme_support"},
        candidate_sources=[
            {
                "source_id": contract_ref,
                "source_family": "production_msme_panel",
                "source_kind": "production_data_contract",
                "freshness": {"status": "pass", "ref": "freshness:msme:v1"},
                "coverage": {"status": "pass"},
                "schema_compatibility": {"status": "pass"},
                "relevance_rationale": "Matches the scenario family.",
                "source_rights": "public_sector_reuse",
                "dictionary_ref": "dictionary:msme:v1",
                "schema_ref": "schema:msme:v1",
                "field_refs": ["field:msme_survival_rate"],
                "unit_refs": ["unit:rate"],
                "geography_refs": ["UA"],
                "time_coverage_refs": ["2024-2026"],
                "quality_refs": ["quality:msme:v1"],
                "missingness_refs": ["missingness:msme:v1"],
                "freshness_refs": ["freshness:msme:v1"],
                "lineage_refs": ["lineage:msme:v1"],
                "transformation_refs": ["transform:msme:v1"],
                "data_forge_snapshot_refs": ["sha256:" + "2" * 64],
                "derived_features": [{"feature_ref": "feature:msme_survival_rate"}],
            }
        ],
        selected_source_ids=[contract_ref],
        rejected_sources=[
            {
                "source_id": "production-data-datasets-bundle",
                "source_family": "datasets",
                "reason_code": "non_admissible_context_only",
            }
        ],
        scenario_evidence_contract=scenario_contract,
        production_data_contract_binding_report={
            "scenario_contract_id": scenario_contract["contract_id"],
            "scenario_binding_findings": [
                {
                    "requirement_id": scenario_contract["requirements"][0][
                        "requirement_id"
                    ],
                    "expected_family": "production_msme_panel",
                    "candidate_ref": contract_ref,
                    "status": "satisfied",
                    "missing_facets": [],
                }
            ],
        },
    )
    dropped_trace = normalize_fabric_retrieval_trace(
        {
            "status": "pass",
            "query_intent": {"policy_domain": "wartime_msme_support"},
            "scenario_evidence_contract_id": None,
            "selected_sources": selected_trace["selected_sources"],
            "rejected_sources": [],
            "production_data_contract_binding_report": {
                "scenario_contract_id": scenario_contract["contract_id"],
                "scenario_binding_findings": [
                    {
                        "requirement_id": scenario_contract["requirements"][0][
                            "requirement_id"
                        ],
                        "expected_family": "production_msme_panel",
                        "candidate_ref": contract_ref,
                        "status": "satisfied",
                        "missing_facets": [],
                    }
                ],
            },
        },
        expected_source_families=["production_msme_panel"],
    )
    checks = [
        {
            "check_id": "broad_bundle_cannot_satisfy_scenario_family",
            "passed": (
                broad_trace["status"] == "fail"
                and broad_trace["selected_contract_binding"] is None
                and broad_trace["selected_sources"][0]["selection_status"]
                == "non_admissible_context_only"
            ),
            "observed_status": broad_trace["status"],
            "issue_codes": sorted({issue["code"] for issue in broad_trace["issues"]}),
        },
        {
            "check_id": "selected_contract_binding_is_authority_surface",
            "passed": (
                selected_trace["status"] == "pass"
                and selected_trace["selected_contract_binding"]["candidate_ref"]
                == contract_ref
                and selected_trace["selected_sources"][0]["authority_surface"]
                == "claim_admissible_contract"
            ),
            "observed_status": selected_trace["status"],
            "selected_contract_binding_ref": selected_trace["selected_contract_binding"][
                "candidate_ref"
            ],
        },
        {
            "check_id": "scenario_contract_id_drop_fails_closed",
            "passed": (
                dropped_trace["status"] == "fail"
                and "scenario_evidence_contract_id_dropped"
                in {issue["code"] for issue in dropped_trace["issues"]}
            ),
            "observed_status": dropped_trace["status"],
            "issue_codes": sorted({issue["code"] for issue in dropped_trace["issues"]}),
        },
    ]
    return {
        "schema_version": "policyos.fabric.source_selection_state_machine.v1",
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
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
    return dump_json(source_scorecards_snapshot_payload(scorecards, generated_at=generated_at))


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
        "quality, replay fixture, lineage, field-level access, owner/reviewer,",
        "processing guarantee, dedupe/replay-retention policy, SLO, scorecard,",
        "and docs evidence are present.",
        "",
        "## Generated Artifacts",
        "",
        "| Artifact | Purpose |",
        "| -------- | ------- |",
        "| `schemas/fabric/source_contract.schema.json` | SourceContract v2 schema |",
        "| `schemas/fabric/source_scorecard.schema.json` | Source scorecard schema |",
        "| `schemas/snapshots/fabric/source_contracts_v2.json` | Production SourceContract snapshot |",
        "| `schemas/snapshots/fabric/source_scorecards.json` | Generated source scorecards |",
        "| `tests/_data/fabric/shared/source_contracts/*.replay.json` | Deterministic production replay fixtures |",
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
        "## Strict Replay And Access Coverage",
        "",
        f"- Production SourceContracts: `{report['summary']['source_contract_count']}`",
        f"- Replay fixtures: `{report['summary']['replay_fixture_count']}`",
        f"- Production non-replayable sources: `{report['summary']['non_replayable_reason_count']}`",
        f"- Field-policy-covered contracts: `{report['summary']['schema_field_policy_coverage_count']}`",
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
            "| Contract | Connector | Profile | Guarantee | Dedupe window | Replay retention | Quality | Replay | Field policies | Classification | Owner | Reviewer |",
            "| -------- | --------- | ------- | --------- | ------------- | ---------------- | ------- | ------ | -------------- | -------------- | ----- | -------- |",
        ]
    )
    for contract in contracts:
        replay = contract.replay.fixture_ref or contract.replay.non_replayable_reason or ""
        lines.append(
            "| "
            f"`{contract.id}` | "
            f"`{contract.source.connector_id}` | "
            f"`{contract.source.profile_id}` | "
            f"`{contract.processing.guarantee_value}` | "
            f"{contract.processing.idempotency.dedupe_window_seconds}s | "
            f"{contract.processing.idempotency.replay_retention_days}d | "
            f"`{contract.quality.contract_ref}` | "
            f"{replay} | "
            f"{len(contract.security.field_policies)} | "
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
            "- `tests/unit/fabric/connectors/test_source_contract_v2.py` validates the model,",
            "  scaffold, conformance harness, scorecards, and generated snapshots.",
            "- `tests/repo_quality/tools/test_fabric_source_contracts.py` validates CI report/check",
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
    fixture_dir: Path = SOURCE_REPLAY_FIXTURE_DIR,
) -> list[str]:
    """Return artifact drift errors."""

    errors: list[str] = []
    expected_snapshot = source_contract_snapshot_json()
    expected_scorecards = source_scorecard_snapshot_json()
    expected_docs = render_source_platform_markdown()
    if not snapshot_path.exists() or snapshot_path.read_text(encoding="utf-8") != expected_snapshot:
        errors.append(f"source contract snapshot out of date: {snapshot_path}")
    if (
        not scorecard_path.exists()
        or scorecard_path.read_text(encoding="utf-8") != expected_scorecards
    ):
        errors.append(f"source scorecard snapshot out of date: {scorecard_path}")
    if not docs_path.exists() or docs_path.read_text(encoding="utf-8") != expected_docs:
        errors.append(f"source platform docs out of date: {docs_path}")
    for filename, expected_fixture in expected_source_replay_fixtures().items():
        fixture_path = fixture_dir / filename
        if (
            not fixture_path.exists()
            or fixture_path.read_text(encoding="utf-8") != expected_fixture
        ):
            errors.append(f"source replay fixture out of date: {fixture_path}")
    return errors


def validate_report(report: dict[str, Any], *, fail_closed: bool = False) -> list[str]:
    """Validate report semantics for CI."""

    errors: list[str] = []
    summary = report.get("summary", {})
    if summary.get("production_connector_count") != summary.get("source_contract_count"):
        errors.append("production connector count does not match SourceContract count")
    source_contract_count = int(summary.get("source_contract_count", 0) or 0)
    if int(summary.get("replay_fixture_count", 0) or 0) != source_contract_count:
        errors.append("every production SourceContract must carry a replay fixture")
    if int(summary.get("non_replayable_reason_count", 0) or 0) != 0:
        errors.append("production SourceContracts must not carry non-replayable reasons")
    if int(summary.get("field_access_policy_contract_count", 0) or 0) != source_contract_count:
        errors.append("every production SourceContract must carry field access policies")
    if int(summary.get("schema_field_policy_coverage_count", 0) or 0) != source_contract_count:
        errors.append("field access policies must cover every schema field or wildcard")
    state_machine = report.get("source_selection_state_machine")
    if not isinstance(state_machine, dict) or state_machine.get("passed") is not True:
        errors.append("Fabric source-selection state machine contract failed")
    for row in report.get("contracts", []):
        contract = SourceContract.model_validate(row["contract"])
        if contract.status == "active" and not contract.replay.fixture_ref:
            errors.append(f"missing replay fixture: {contract.id}")
        if contract.status == "active" and contract.replay.non_replayable_reason:
            errors.append(
                f"non-replayable reason is forbidden for production source: {contract.id}"
            )
        if not contract.security.field_policies:
            errors.append(f"missing field access policies: {contract.id}")
        if not contract.processing.idempotency.key_fields:
            errors.append(f"missing dedupe key policy: {contract.id}")
        if contract.processing.idempotency.dedupe_window_seconds <= 0:
            errors.append(f"missing dedupe window: {contract.id}")
        if (
            contract.processing.idempotency.replay_retention_days
            < contract.retention.min_retention_days
        ):
            errors.append(f"replay retention below source retention: {contract.id}")
    if fail_closed and int(summary.get("conformance_error_count", 0)) > 0:
        errors.append("conformance errors present in fail-closed mode")
    return errors


def update_artifacts(
    *,
    snapshot_path: Path = SOURCE_CONTRACT_SNAPSHOT,
    scorecard_path: Path = SOURCE_SCORECARD_SNAPSHOT,
    docs_path: Path = SOURCE_PLATFORM_DOC,
    fixture_dir: Path = SOURCE_REPLAY_FIXTURE_DIR,
) -> None:
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    scorecard_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(snapshot_path, source_contract_snapshot_json())
    atomic_write_text(scorecard_path, source_scorecard_snapshot_json())
    atomic_write_text(docs_path, render_source_platform_markdown())
    for filename, fixture_json in expected_source_replay_fixtures().items():
        atomic_write_text(fixture_dir / filename, fixture_json)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    report = build_report()

    report_errors = validate_report(report, fail_closed=args.fail_closed)
    if args.report:
        report_json = dump_json(report)
        if args.report == "-":
            print(report_json, end="")
        else:
            report_path = Path(args.report)
            if not report_path.is_absolute():
                report_path = Path(args.repo_root).expanduser().resolve() / report_path
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(report_json, encoding="utf-8")

    if args.update:
        update_artifacts(
            snapshot_path=args.snapshot,
            scorecard_path=args.scorecards,
            docs_path=args.docs,
            fixture_dir=args.replay_fixtures,
        )
        print(f"Updated SourceContract snapshot: {args.snapshot}")
        print(f"Updated source scorecards: {args.scorecards}")
        print(f"Updated source platform docs: {args.docs}")
        print(f"Updated source replay fixtures: {args.replay_fixtures}")

    artifact_errors: list[str] = []
    if args.check or args.fail_closed:
        artifact_errors = check_artifacts(
            snapshot_path=args.snapshot,
            scorecard_path=args.scorecards,
            docs_path=args.docs,
            fixture_dir=args.replay_fixtures,
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
