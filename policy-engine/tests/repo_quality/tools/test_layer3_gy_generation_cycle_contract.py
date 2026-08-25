from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

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


def test_generation_cycle_writer_refuses_historical_v3_to_current_v4_migration(
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

    with pytest.raises(
        ValueError,
        match="generation_cycle_comparison_admission_manifest_drift",
    ):
        checker.build_contract_json_for_write(POLICY_ENGINE_ROOT)


def test_generation_cycle_check_reports_historical_reissue_without_traceback() -> None:
    committed = (POLICY_ENGINE_ROOT / checker.OUTPUT_PATH).read_text(encoding="utf-8")

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
        "policyos.policy_design_case.layer3_gy.n9_promotion.v4"
    }
    assert "generation_cycle_comparison_admission_manifest_drift" in _issue_codes(report)


def test_generation_cycle_check_rejects_forged_historical_receipt_before_reissue() -> None:
    payload = copy.deepcopy(checker.load_contract_payload(POLICY_ENGINE_ROOT))
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
    assert "generation_cycle_comparison_admission_manifest_drift" in _issue_codes(report)
