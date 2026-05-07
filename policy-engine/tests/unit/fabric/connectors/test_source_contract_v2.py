from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from polisyos.fabric.connectors.contracts import (
    SOURCE_CONTRACT_SCHEMA_VERSION,
    SourceContract,
    SourceContractQuality,
    SourceContractReplay,
    SourceContractSchema,
    SourceContractSecurity,
    SourceDeprecationPolicy,
    SourceFieldAccessPolicy,
    source_contracts_compatibility_evidence,
)
from polisyos.fabric.connectors.scorecard import (
    build_source_scorecard,
    render_scorecards_markdown,
)
from polisyos.fabric.connectors.sdk import (
    SourceScaffoldSpec,
    scaffold_source_artifacts,
)
from polisyos.fabric.connectors.sources._contracts import WDI_GENERIC_CONTRACT
from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
from polisyos.fabric.connectors.testing.conformance import validate_source_conformance_v2
from polisyos.fabric.processing_guarantees import ProcessingGuarantee
from tools.quality.validation import fabric_source_contracts

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_source_contract_v2_wraps_existing_connector_schema_contract() -> None:
    contract = SourceContract.from_connector_schema_contract(
        WDI_GENERIC_CONTRACT,
        metadata=WorldBankConnector.metadata,
        profile_id="worldbank_wdi",
        reviewer="@fabric-reviewers",
    )

    assert contract.schema_version == SOURCE_CONTRACT_SCHEMA_VERSION
    assert contract.id == "worldbank.wdi.generic"
    assert contract.schema.schema_id == "worldbank.wdi.generic"
    assert contract.schema.fields
    assert contract.quality.contract_ref == "fabric.quality.worldbank.wdi.default.v1"
    assert "safe_filters" in contract.quality.required_checks
    assert "bounded_reads" in contract.quality.required_checks
    assert contract.replay.non_replayable_reason
    assert contract.lineage.seed_node_kind == "source_dataset"
    assert {policy.field_id for policy in contract.security.field_policies} == {
        field.stable_id for field in contract.schema.fields
    }
    assert contract.processing.guarantee_value == ProcessingGuarantee.BATCH_ATOMIC.value
    assert contract.processing.idempotency.dedupe_window_seconds > 0
    assert (
        contract.processing.idempotency.replay_retention_days
        >= contract.retention.min_retention_days
    )
    assert contract.content_hash.startswith("sha256:")


def test_source_contract_replay_requires_fixture_or_reason() -> None:
    with pytest.raises(ValueError, match="fixture_ref"):
        SourceContractReplay(required=True)

    with pytest.raises(ValueError, match="non_replayable_reason"):
        SourceContractReplay(required=False)


def test_source_contract_schema_requires_evidence_for_active_contract() -> None:
    base = SourceContract.from_connector_schema_contract(
        WDI_GENERIC_CONTRACT,
        metadata=WorldBankConnector.metadata,
        profile_id="worldbank_wdi",
    )
    payload = base.model_dump(mode="json", by_alias=True)
    payload["schema"] = SourceContractSchema().model_dump(mode="json")

    with pytest.raises(ValueError, match="schema evidence"):
        SourceContract.model_validate(payload)


def test_source_contract_requires_complete_field_access_policies() -> None:
    base = SourceContract.from_connector_schema_contract(
        WDI_GENERIC_CONTRACT,
        metadata=WorldBankConnector.metadata,
        profile_id="worldbank_wdi",
    )
    payload = base.model_dump(mode="json", by_alias=True)
    payload["security"]["field_policies"] = []

    with pytest.raises(ValueError, match="field access policies"):
        SourceContract.model_validate(payload)

    payload = base.model_dump(mode="json", by_alias=True)
    payload["security"]["field_policies"] = payload["security"]["field_policies"][:-1]

    with pytest.raises(ValueError, match="missing field access policies"):
        SourceContract.model_validate(payload)


def test_non_public_field_access_policy_requires_policy_ref() -> None:
    with pytest.raises(ValueError, match="policy_ref"):
        SourceFieldAccessPolicy(
            field_id="worldbank.wdi.generic.value",
            classification="confidential",
        )

    policy = SourceFieldAccessPolicy(
        field_id="worldbank.wdi.generic.value",
        classification="confidential",
        policy_ref="fabric.access.policy.confidential",
        reason="Decision-bearing restricted field.",
    )
    security = SourceContractSecurity(
        classification="confidential",
        field_policies=(policy,),
    )
    assert security.field_policies[0].policy_ref == "fabric.access.policy.confidential"


def test_deprecated_source_contract_requires_sunset_policy() -> None:
    base = SourceContract.from_connector_schema_contract(
        WDI_GENERIC_CONTRACT,
        metadata=WorldBankConnector.metadata,
        profile_id="worldbank_wdi",
    )
    payload = base.model_dump(mode="json", by_alias=True)
    payload["status"] = "deprecated"

    with pytest.raises(ValueError, match="deprecation policy"):
        SourceContract.model_validate(payload)

    payload["deprecation"] = SourceDeprecationPolicy(
        reason="Superseded by a profile-specific World Bank WDI contract.",
        migration_note="Keep historical replay pinned to worldbank.wdi.generic.",
        replacement_contract_id="worldbank.wdi.profile_specific",
        sunset_at=datetime(2026, 12, 31, tzinfo=UTC),
    ).model_dump(mode="json")

    deprecated = SourceContract.model_validate(payload)
    assert deprecated.status == "deprecated"
    assert deprecated.deprecation is not None
    assert deprecated.deprecation.migration_note


def test_sdk_scaffold_emits_contract_quality_fixture_and_docs_stub() -> None:
    artifacts = scaffold_source_artifacts(
        metadata=WorldBankConnector.metadata,
        schema_contract=WDI_GENERIC_CONTRACT,
        spec=SourceScaffoldSpec(
            connector_id="worldbank.wdi",
            profile_id="worldbank_wdi",
            contract_id="worldbank.wdi.generic",
        ),
    )

    assert artifacts.contract.source.profile_id == "worldbank_wdi"
    assert artifacts.quality_contract["source_contract_id"] == artifacts.contract.id
    assert artifacts.replay_fixture_id.endswith("worldbank.wdi.generic.replay.json")
    assert "World Bank" in artifacts.documentation_stub
    assert "Processing guarantee" in artifacts.documentation_stub


def test_conformance_v2_passes_for_scaffolded_worldbank_source() -> None:
    contract = SourceContract.from_connector_schema_contract(
        WDI_GENERIC_CONTRACT,
        metadata=WorldBankConnector.metadata,
        profile_id="worldbank_wdi",
        replay_fixture_ref=(
            "tests/_data/fabric/shared/source_contracts/worldbank.wdi.generic.replay.json"
        ),
    )
    profiles = tuple(fabric_source_contracts.SourceProfileRegistry.get_instance().list_all())

    report = validate_source_conformance_v2(
        connector_class=WorldBankConnector,
        source_contract=contract,
        profiles=profiles,
        schema_contracts=(WDI_GENERIC_CONTRACT,),
        replay_fixture_exists=True,
    )

    assert report.passed
    assert report.issues == ()


def test_conformance_v2_rejects_missing_bounded_read_evidence() -> None:
    contract = SourceContract.from_connector_schema_contract(
        WDI_GENERIC_CONTRACT,
        metadata=WorldBankConnector.metadata,
        profile_id="worldbank_wdi",
        replay_fixture_ref=(
            "tests/_data/fabric/shared/source_contracts/worldbank.wdi.generic.replay.json"
        ),
    )
    contract = contract.model_copy(
        update={
            "quality": SourceContractQuality(
                contract_ref=contract.quality.contract_ref,
                required_checks=(
                    "schema_compliance",
                    "finite_values",
                    "freshness",
                    "safe_filters",
                ),
            )
        }
    )
    profiles = tuple(fabric_source_contracts.SourceProfileRegistry.get_instance().list_all())

    report = validate_source_conformance_v2(
        connector_class=WorldBankConnector,
        source_contract=contract,
        profiles=profiles,
        schema_contracts=(WDI_GENERIC_CONTRACT,),
        replay_fixture_exists=True,
    )

    assert not report.passed
    assert "bounded_reads" in report.issues_by_check()


def test_scorecard_tracks_required_phase5_dimensions() -> None:
    contract = SourceContract.from_connector_schema_contract(
        WDI_GENERIC_CONTRACT,
        metadata=WorldBankConnector.metadata,
        profile_id="worldbank_wdi",
    )

    scorecard = build_source_scorecard(
        contract,
        {
            "freshness_age_seconds": 3600,
            "fetch_success": 0.999,
            "schema_drift_rate": 0.0,
            "quality_score": 0.97,
            "contract_violation_rate": 0.0,
            "quarantine_rate": 0.0,
            "replay_success": 1.0,
            "p95_latency_ms": 250,
        },
    )

    assert scorecard.grade == "A"
    assert {metric.name for metric in scorecard.metrics} == {
        "freshness",
        "reliability",
        "schema_drift",
        "quality",
        "contract_violations",
        "quarantine_rate",
        "replay_success",
        "latency",
        "source_trust",
    }
    scorecard_markdown = render_scorecards_markdown((scorecard,))
    assert "worldbank.wdi.generic" in scorecard_markdown
    assert "Freshness" in scorecard_markdown
    assert "Replay" in scorecard_markdown


def test_generated_source_contract_snapshot_covers_all_production_connectors() -> None:
    contracts = fabric_source_contracts.build_source_contracts()
    report = fabric_source_contracts.build_report()
    evidence = source_contracts_compatibility_evidence(contracts)

    assert len(contracts) == 20
    assert report["summary"]["conformance_error_count"] == 0
    assert report["summary"]["source_contract_count"] == len(contracts)
    assert evidence["contract_count"] == len(contracts)
    assert evidence["replay_fixture_count"] == len(contracts)
    assert evidence["non_replayable_reason_count"] == 0
    assert evidence["schema_field_policy_coverage_count"] == len(contracts)
    assert all(contract.owner and contract.reviewer for contract in contracts)
    assert all(contract.quality.contract_ref for contract in contracts)
    assert all("bounded_reads" in contract.quality.required_checks for contract in contracts)
    assert all(contract.lineage.seed_node_kind for contract in contracts)
    assert all(contract.replay.fixture_ref for contract in contracts)
    assert not any(contract.replay.non_replayable_reason for contract in contracts)
    assert all(contract.security.field_policies for contract in contracts)
    assert all(contract.processing.idempotency.key_fields for contract in contracts)
    assert all(contract.processing.idempotency.dedupe_window_seconds > 0 for contract in contracts)


def test_checked_in_source_contract_schemas_and_snapshots_are_parseable() -> None:
    contract_schema = json.loads(
        (REPO_ROOT / "schemas/fabric/source_contract.schema.json").read_text(encoding="utf-8")
    )
    scorecard_schema = json.loads(
        (REPO_ROOT / "schemas/fabric/source_scorecard.schema.json").read_text(encoding="utf-8")
    )
    processing_schema = json.loads(
        (REPO_ROOT / "schemas/fabric/processing_guarantee.schema.json").read_text(encoding="utf-8")
    )
    source_snapshot = json.loads(
        (REPO_ROOT / "schemas/snapshots/fabric/source_contracts_v2.json").read_text(
            encoding="utf-8"
        )
    )

    assert contract_schema["title"] == "Fabric SourceContract v2"
    assert scorecard_schema["title"] == "Fabric Source Scorecard"
    assert processing_schema["title"] == "Fabric Processing Guarantee Contract"
    parsed = [
        SourceContract.model_validate(row["contract"])
        for row in source_snapshot["contracts"].values()
    ]
    assert len(parsed) == 20
