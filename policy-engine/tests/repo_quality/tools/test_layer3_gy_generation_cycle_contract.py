from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from polisyos.runtime.quality.promotion_sequence import CanonicalPromotionReceipt
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


def test_generation_cycle_writer_never_opens_checkout_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _forbid_from_repo(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("N6 checker touched the checkout confidence ledger")

    monkeypatch.setattr(
        checker.ConfidenceLedgerSession,
        "from_repo",
        _forbid_from_repo,
    )

    first = checker.build_contract_json_for_write(POLICY_ENGINE_ROOT)
    second = checker.build_contract_json_for_write(POLICY_ENGINE_ROOT)

    assert first == second
    payload = json.loads(first)
    receipts = payload["generation_cycle_run"]["promotion_port"]["receipts"]
    assert len(receipts) == 2
    assert all(CanonicalPromotionReceipt.model_validate(item) for item in receipts)
    assert all(
        item["confidence_ledger_projection"]["authority_provenance"] == "verification"
        for item in receipts
    )
    assert all(item["consumer_promotable"] is False for item in receipts)


def test_generation_cycle_check_revalidates_forged_embedded_receipt() -> None:
    payload = json.loads(checker.build_contract_json_for_write(POLICY_ENGINE_ROOT))
    receipt = payload["generation_cycle_run"]["promotion_port"]["receipts"][0]
    receipt["risk_spend"]["within_budget"] = False
    payload["contract_content_hash"] = checker._contract_content_hash(payload)
    committed = json.dumps(payload, indent=2, sort_keys=True) + "\n"

    report = checker._validate_committed_contract_text(
        POLICY_ENGINE_ROOT,
        committed,
    )

    assert report["status"] == "fail"
    assert "embedded_promotion_receipt_semantic_projection_drift" in _issue_codes(
        report
    )


def test_generation_cycle_check_rejects_rehashed_stale_live_field() -> None:
    payload = json.loads(checker.build_contract_json_for_write(POLICY_ENGINE_ROOT))
    payload["compute_economics"]["non_cached_run_visibility"] = "stale_but_structurally_allowed"
    payload["contract_content_hash"] = checker._contract_content_hash(payload)
    committed = json.dumps(payload, indent=2, sort_keys=True) + "\n"

    report = checker._validate_committed_contract_text(
        POLICY_ENGINE_ROOT,
        committed,
    )

    assert report["status"] == "fail"
    assert "generation_cycle_contract_canonical_bytes_drift" in _issue_codes(report)
