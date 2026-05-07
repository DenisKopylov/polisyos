from __future__ import annotations

import json
from pathlib import Path

from polisyos.fabric.connectors.contracts import SourceContract, load_source_contracts
from tools.quality.validation import fabric_source_contracts

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_source_platform_report_is_fail_closed_ready() -> None:
    report = fabric_source_contracts.build_report()
    summary = report["summary"]

    assert report["schema_version"] == fabric_source_contracts.REPORT_SCHEMA_VERSION
    assert summary["production_connector_count"] == 20
    assert summary["source_contract_count"] == summary["production_connector_count"]
    assert summary["conformance_passed_count"] == summary["source_contract_count"]
    assert summary["conformance_error_count"] == 0
    assert summary["conformance_warning_count"] == 0
    assert summary["scorecard_count"] == summary["source_contract_count"]
    assert summary["replay_fixture_count"] == summary["source_contract_count"]
    assert summary["replay_fixture_artifact_count"] == summary["source_contract_count"]
    assert summary["non_replayable_reason_count"] == 0
    assert summary["field_access_policy_contract_count"] == summary["source_contract_count"]
    assert summary["schema_field_policy_coverage_count"] == summary["source_contract_count"]
    assert fabric_source_contracts.validate_report(report, fail_closed=True) == []
    assert all(row["profile_present"] for row in report["profile_compatibility_matrix"])


def test_source_contract_snapshot_carries_phase5_evidence() -> None:
    payload = json.loads(fabric_source_contracts.source_contract_snapshot_json())
    contracts = load_source_contracts(payload)

    assert len(contracts) == 20
    assert {contract.schema_version for contract in contracts} == {
        fabric_source_contracts.SOURCE_CONTRACT_SCHEMA_VERSION
    }
    assert all(contract.owner and contract.reviewer for contract in contracts)
    assert all(contract.source.profile_id for contract in contracts)
    assert all(contract.quality.contract_ref for contract in contracts)
    assert all(contract.quality.required_checks for contract in contracts)
    assert all("bounded_reads" in contract.quality.required_checks for contract in contracts)
    assert all(contract.replay.required for contract in contracts)
    assert all(contract.replay.fixture_ref for contract in contracts)
    assert not any(contract.replay.non_replayable_reason for contract in contracts)
    assert all(contract.lineage.seed_node_kind for contract in contracts)
    assert all(contract.security.classification for contract in contracts)
    assert all(contract.security.field_policies for contract in contracts)
    assert all(contract.processing.guarantee_value for contract in contracts)
    assert all(contract.processing.idempotency.key_fields for contract in contracts)
    assert all(contract.processing.idempotency.dedupe_window_seconds > 0 for contract in contracts)
    assert all(contract.processing.idempotency.replay_retention_days >= 30 for contract in contracts)
    assert all(contract.retention.artifact_retention_days >= 30 for contract in contracts)
    assert all(contract.sla.availability_target > 0.0 for contract in contracts)


def test_scorecard_snapshot_covers_required_dimensions() -> None:
    payload = json.loads(fabric_source_contracts.source_scorecard_snapshot_json())
    scorecards = payload["scorecards"]

    assert len(scorecards) == 20
    for scorecard in scorecards.values():
        assert scorecard["window"] == "rolling_30d"
        assert {metric["name"] for metric in scorecard["metrics"]} == {
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
    markdown = fabric_source_contracts.render_source_platform_markdown()
    assert "| Source contract | Window | Freshness | Reliability |" in markdown
    assert "| Contract | Connector | Profile | Guarantee | Dedupe window |" in (
        markdown
    )


def test_checked_in_source_platform_artifacts_are_current() -> None:
    assert (
        fabric_source_contracts.SOURCE_CONTRACT_SNAPSHOT.read_text(encoding="utf-8")
        == fabric_source_contracts.source_contract_snapshot_json()
    )
    assert (
        fabric_source_contracts.SOURCE_SCORECARD_SNAPSHOT.read_text(encoding="utf-8")
        == fabric_source_contracts.source_scorecard_snapshot_json()
    )
    assert (
        fabric_source_contracts.SOURCE_PLATFORM_DOC.read_text(encoding="utf-8")
        == fabric_source_contracts.render_source_platform_markdown()
    )
    for filename, expected in fabric_source_contracts.expected_source_replay_fixtures().items():
        fixture_path = fabric_source_contracts.SOURCE_REPLAY_FIXTURE_DIR / filename
        assert fixture_path.read_text(encoding="utf-8") == expected
    assert fabric_source_contracts.check_artifacts() == []


def test_source_contract_gate_updates_and_checks_temp_artifacts(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "source_contracts_v2.json"
    scorecard_path = tmp_path / "source_scorecards.json"
    docs_path = tmp_path / "source-platform.md"
    fixture_dir = tmp_path / "fixtures"

    fabric_source_contracts.update_artifacts(
        snapshot_path=snapshot_path,
        scorecard_path=scorecard_path,
        docs_path=docs_path,
        fixture_dir=fixture_dir,
    )

    assert (
        fabric_source_contracts.check_artifacts(
            snapshot_path=snapshot_path,
            scorecard_path=scorecard_path,
            docs_path=docs_path,
            fixture_dir=fixture_dir,
        )
        == []
    )
    parsed = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert len([SourceContract.model_validate(row["contract"]) for row in parsed["contracts"].values()]) == 20
    assert "## Source Scorecards" in docs_path.read_text(encoding="utf-8")
    assert len(list(fixture_dir.glob("*.replay.json"))) == 20


def test_source_contract_gate_detects_drift(tmp_path: Path) -> None:
    manifest_path = tmp_path / "source_contracts_v2.json"
    scorecard_path = tmp_path / "source_scorecards.json"
    docs_path = tmp_path / "source-platform.md"
    manifest_path.write_text("{}", encoding="utf-8")
    scorecard_path.write_text(
        fabric_source_contracts.source_scorecard_snapshot_json(),
        encoding="utf-8",
    )
    docs_path.write_text(
        fabric_source_contracts.render_source_platform_markdown(),
        encoding="utf-8",
    )

    drift = fabric_source_contracts.check_artifacts(
        snapshot_path=manifest_path,
        scorecard_path=scorecard_path,
        docs_path=docs_path,
    )

    assert drift == [f"source contract snapshot out of date: {manifest_path}"]


def test_fail_closed_main_checks_committed_evidence() -> None:
    assert fabric_source_contracts.main(["--fail-closed"]) == 0


def test_validate_report_rejects_count_and_fail_closed_errors() -> None:
    assert fabric_source_contracts.validate_report(
        {
            "summary": {
                "production_connector_count": 2,
                "source_contract_count": 1,
                "conformance_error_count": 0,
                "replay_fixture_count": 1,
                "non_replayable_reason_count": 0,
                "field_access_policy_contract_count": 1,
                "schema_field_policy_coverage_count": 1,
            }
        }
    ) == ["production connector count does not match SourceContract count"]

    assert fabric_source_contracts.validate_report(
        {
            "summary": {
                "production_connector_count": 1,
                "source_contract_count": 1,
                "conformance_error_count": 1,
                "replay_fixture_count": 1,
                "non_replayable_reason_count": 0,
                "field_access_policy_contract_count": 1,
                "schema_field_policy_coverage_count": 1,
            }
        },
        fail_closed=True,
    ) == ["conformance errors present in fail-closed mode"]
