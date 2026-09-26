from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from polisyos.runtime.quality.promotion_sequence import (
    CANONICAL_PROMOTION_SEQUENCE_SCHEMA_VERSION,
)
from tests.unit.runtime.quality.historical_artifacts import (
    GENERATION_CYCLE_V1_BLOB,
    historical_generation_cycle_v1,
    historical_owner_bytes,
)
from tests.unit.runtime.quality.test_generation_cycle_history import _tracked_n6_runs
from tools.quality.validation import check_layer3_gy_generation_cycle_contract as checker

POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[3]


def _issue_codes(report: dict[str, object]) -> set[str]:
    issues = report.get("issues")
    assert isinstance(issues, list)
    return {
        str(issue.get("code")) for issue in issues if isinstance(issue, dict) and issue.get("code")
    }


def test_generation_cycle_payload_rejects_stale_embedded_promotion_receipt() -> None:
    payload = copy.deepcopy(checker.load_contract_payload(POLICY_ENGINE_ROOT))
    promotion = payload["generation_cycle_run"]["promotion_port"]
    receipts = promotion["receipts"]
    assert isinstance(receipts, list) and receipts
    receipt = receipts[0]
    assert isinstance(receipt, dict)
    receipt["schema_version"] = "policyos.policy_design_case.layer3_gy.n9_promotion.v1"
    payload["contract_content_hash"] = checker._contract_content_hash(payload)

    report = checker.validate_payload(payload)

    assert report["status"] == "fail"
    assert "embedded_promotion_receipt_invalid" in _issue_codes(report)


def test_generation_cycle_payload_rejects_empty_promotion_receipt_denominator() -> None:
    payload = copy.deepcopy(checker.load_contract_payload(POLICY_ENGINE_ROOT))
    payload["generation_cycle_run"]["promotion_port"]["receipts"] = []
    payload["contract_content_hash"] = checker._contract_content_hash(payload)

    report = checker.validate_payload(payload)

    assert report["status"] == "fail"
    assert "embedded_promotion_receipt_denominator_mismatch" in _issue_codes(report)


def test_generation_cycle_writer_reissues_exact_history_with_actual_current_owners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live_session = checker.ConfidenceLedgerSession

    class _SessionProxy:
        @classmethod
        def _for_verification(cls, *args: object, **kwargs: object):
            del cls
            return live_session._for_verification(*args, **kwargs)

        @classmethod
        def from_repo(cls, *args: object, **kwargs: object) -> None:
            del cls, args, kwargs
            raise AssertionError("N6 checker touched the checkout confidence ledger")

    monkeypatch.setattr(
        checker,
        "ConfidenceLedgerSession",
        _SessionProxy,
    )

    emitted = json.loads(checker.build_contract_json_for_write(POLICY_ENGINE_ROOT))
    assert checker.validate_payload(emitted)["status"] == "pass"
    assert emitted["schema_version"] == checker.GENERATION_CYCLE_CONTRACT_SCHEMA_VERSION
    assert emitted["generation_cycle_run"]["source_preservation_receipt"]["status"] == (
        "not_established"
    )
    assert emitted["generation_cycle_run"]["source_handoff_refs"] == []
    assert "synthetic" in emitted, "standalone_report_synthetic_ancestry_absent"
    assert emitted["synthetic"] is emitted["generation_cycle_run"]["synthetic"] is True


def test_generation_cycle_check_reports_historical_reissue_without_traceback() -> None:
    committed = historical_owner_bytes(GENERATION_CYCLE_V1_BLOB).decode()

    report = checker._validate_committed_contract_text(POLICY_ENGINE_ROOT, committed)

    assert report["status"] == "fail"
    issues = report["issues"]
    reissues = [
        issue
        for issue in issues
        if issue.get("code") == "embedded_promotion_open_world_reissue_required"
    ]
    assert [issue["receipt_index"] for issue in reissues] == [0, 1]
    assert {issue["historical_schema_version"] for issue in reissues} == {
        "policyos.policy_design_case.layer3_gy.n9_promotion.v3"
    }
    assert {issue["current_schema_version"] for issue in reissues} == {
        CANONICAL_PROMOTION_SEQUENCE_SCHEMA_VERSION
    }
    assert "schema_version_drift" in _issue_codes(report)


def test_generation_cycle_check_rejects_forged_historical_receipt_before_reissue() -> None:
    payload = historical_generation_cycle_v1()
    receipt = payload["generation_cycle_run"]["promotion_port"]["receipts"][0]
    receipt["risk_spend"]["within_budget"] = False
    payload["contract_content_hash"] = checker._contract_content_hash(payload)
    committed = json.dumps(payload, indent=2, sort_keys=True) + "\n"

    report = checker._validate_committed_contract_text(
        POLICY_ENGINE_ROOT,
        committed,
    )

    assert report["status"] == "fail"
    assert {
        "comparison_content_hash_drift",
        "embedded_promotion_open_world_reissue_required",
    } <= _issue_codes(report)


def test_generation_cycle_check_rejects_rehashed_stale_live_field() -> None:
    payload = copy.deepcopy(checker.load_contract_payload(POLICY_ENGINE_ROOT))
    payload["compute_economics"]["non_cached_run_visibility"] = "stale_but_structurally_allowed"
    payload["contract_content_hash"] = checker._contract_content_hash(payload)
    committed = json.dumps(payload, indent=2, sort_keys=True) + "\n"

    report = checker._validate_committed_contract_text(
        POLICY_ENGINE_ROOT,
        committed,
    )

    assert report["status"] == "fail"
    assert "generation_cycle_contract_canonical_bytes_drift" in _issue_codes(report)


@pytest.fixture(scope="module")
def current_owner_emission():
    """Run and admit the actual current owner once for bounded transition mutations."""
    with TemporaryDirectory(prefix="n6-reissue-test-") as directory:
        payload, context = asyncio.run(
            checker._build_live_payload_in_verification_namespace(
                POLICY_ENGINE_ROOT, state_root=Path(directory)
            )
        )
        report = checker.validate_payload(payload, repo_root=POLICY_ENGINE_ROOT)
        assert report["status"] == "pass", report.get("issues")
        assert context.comparison_admissions
        yield payload, context.comparison_plan


def test_current_v3_requires_authorized_reissue_and_preserves_old_bytes(
    current_owner_emission, tmp_path
):
    """The live v3 run is current, but the old report cannot be restamped as current."""
    from polisyos.runtime.quality.generation_cycle import GENERATION_CYCLE_SCHEMA_VERSION

    live, plan = current_owner_emission
    assert live["generation_cycle_run"]["schema_version"] == GENERATION_CYCLE_SCHEMA_VERSION
    assert checker._persisted_run_currentness_observation(
        live["generation_cycle_run"]
    )["status"] == "pass"
    mismatched_current_run = copy.deepcopy(live["generation_cycle_run"])
    mismatched_identity = "policy-engine-deployment:sha256:" + "f" * 64
    if mismatched_identity == mismatched_current_run["deployment_identity"]:
        mismatched_identity = "policy-engine-deployment:sha256:" + "e" * 64
    mismatched_current_run["deployment_identity"] = mismatched_identity
    assert checker._persisted_run_currentness_observation(
        mismatched_current_run
    )["reason_code"] == "generation_cycle_currentness_deployment_identity_mismatch"
    destination = tmp_path / checker.OUTPUT_PATH
    destination.parent.mkdir(parents=True)
    original = historical_owner_bytes(GENERATION_CYCLE_V1_BLOB)
    destination.write_bytes(original)

    with pytest.raises(ValueError, match="generation_cycle_governed_reissue_refused"):
        checker._reconcile_frozen_contract(tmp_path, live, plan)
    assert destination.read_bytes() == original
    report = checker.validate(tmp_path)
    assert report["status"] == "UNRUN"
    assert _issue_codes(report) == {"generation_cycle_currentness_reissue_required"}


def test_validator_types_persisted_historical_run_as_currentness_unrun(tmp_path):
    """Old valid history remains replayable but needs an authorized current reissue."""

    historical_run = historical_generation_cycle_v1()["generation_cycle_run"]
    from polisyos.runtime.quality.generation_cycle import validate_generation_cycle_run_history

    assert validate_generation_cycle_run_history(historical_run) == ()
    destination = tmp_path / checker.OUTPUT_PATH
    destination.parent.mkdir(parents=True)
    destination.write_text(
        json.dumps({"generation_cycle_run": historical_run}),
        encoding="utf-8",
    )

    report = checker.validate(tmp_path)

    assert report["status"] == "UNRUN"
    assert _issue_codes(report) == {"generation_cycle_currentness_reissue_required"}
    assert report["measurement"]["predicate"]["result"] == "not_run"
    replay = report["measurement"]["selector_denominator"]["n6_n9_replay"]
    assert replay["callback_attempt_count"] == 0
    assert replay["currentness"]["historical_replay"] == {
        "status": "pass",
        "predicate": "recomputed",
    }


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    [
        ("historical_schema", "generation_cycle_historical_replay_invalid"),
        ("identity_unknown", "generation_cycle_currentness_reissue_required"),
        ("identity_mismatch", "generation_cycle_currentness_deployment_identity_mismatch"),
    ],
)
def test_currentness_gate_refuses_historical_or_mismatched_identity(
    current_owner_emission, mutation, expected_reason
):
    """Run schema and owner identity, not markers alone, determine currentness."""
    emitted, _plan = current_owner_emission
    run_payload = copy.deepcopy(emitted["generation_cycle_run"])
    if mutation == "historical_schema":
        run_payload["schema_version"] = "policyos.runtime.generation_cycle_controller.v2"
        run_payload.pop("deployment_identity_status", None)
        run_payload.pop("deployment_identity", None)
        run_payload.pop("deployment_identity_reason", None)
    if mutation == "identity_unknown":
        run_payload["deployment_identity_status"] = "not_established"
        run_payload["deployment_identity"] = None
        run_payload["deployment_identity_reason"] = "canonical_loaded_runtime_mismatch"
    elif mutation == "identity_mismatch":
        run_payload["deployment_identity"] = "policy-engine-deployment:sha256:" + "f" * 64
        if run_payload["deployment_identity"] == emitted["generation_cycle_run"]["deployment_identity"]:
            run_payload["deployment_identity"] = "policy-engine-deployment:sha256:" + "e" * 64

    observed = checker._persisted_run_currentness_observation(run_payload)
    if mutation == "historical_schema":
        assert observed["status"] == "fail"
        assert observed["reason_code"] == expected_reason
        assert observed["historical_replay_status"] == "fail"
    else:
        assert observed["status"] == "UNRUN"
        assert observed["reason_code"] == expected_reason


def test_genuine_v2_run_replays_but_currentness_requires_reissue() -> None:
    """One repository v2 record remains historically valid and currentness-unrun."""
    _tracked_file_count, occurrences = _tracked_n6_runs()
    run = next(
        payload
        for _path, _pointer, payload in occurrences
        if payload.get("schema_version") == "policyos.runtime.generation_cycle_controller.v2"
    )

    observed = checker._persisted_run_currentness_observation(run)

    assert observed["status"] == "UNRUN"
    assert observed["reason_code"] == "generation_cycle_currentness_reissue_required"
    assert observed["historical_replay"] == {"status": "pass", "predicate": "recomputed"}


def test_current_epoch_keeps_strict_complete_projection(current_owner_emission):
    """The real canonical freshness owner rejects a changed full report envelope."""
    emitted, plan = current_owner_emission
    changed = copy.deepcopy(emitted)
    changed.pop("capture_wall_time_seconds", None)
    changed["unrelated_governing_value"] = {"synthetic": True, "value": "changed"}
    checker._set_comparison_identity(changed, plan)
    changed["contract_content_hash"] = checker._contract_content_hash(changed)
    report = checker._validate_committed_contract_text(
        POLICY_ENGINE_ROOT, json.dumps(changed, indent=2, sort_keys=True) + "\n"
    )
    assert report["status"] == "fail"
    assert "generation_cycle_contract_canonical_bytes_drift" in _issue_codes(report)
