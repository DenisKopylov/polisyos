from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tools.quality.validation import check_layer3_gy_promotion_contract as checker

POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[3]


def test_rederived_n9_contract_accounts_fixed_time_refusal_through_n11() -> None:
    payload = checker.build_payload(POLICY_ENGINE_ROOT)

    receipt = payload["contract_lane_anytime_refusal"]
    projection = receipt["confidence_ledger_projection"]
    calibration = next(
        item for item in receipt["obligations"] if item["obligation_class"] == "calibration"
    )

    assert receipt["promoted"] is False
    assert receipt["authority_derivation_trace"] is None
    assert receipt["risk_spend"]["total_declared_delta"] == 0.0
    assert receipt["risk_spend"]["within_budget"] is True
    assert projection["projection_scope"] == "n9_promotion_certificate"
    assert projection["total_spend"] == {"denominator": 1, "numerator": 0}
    assert projection["maintained_assumptions"] == [
        "obligation_completeness",
        "validator_soundness",
    ]
    assert len(projection["promotion_rows"]) == 1
    row = projection["promotion_rows"][0]
    assert row["instrument_id"] == "fixed_time_confidence_interval"
    assert row["outcome"] == "preflight_refusal"
    assert row["anytime_valid"] is False
    assert row["eligible_for_promotion"] is False
    assert row["spend"] == {"denominator": 1, "numerator": 0}
    assert calibration["risk_spend"]["n11_confidence_ledger_ref"] == row["check_id"]
    assert checker.validate_payload(payload) == {"status": "pass", "issues": []}


def test_n9_contract_writer_is_byte_stable_without_canonical_ledger_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _forbid_from_repo(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("N9 checker touched the checkout confidence ledger")

    monkeypatch.setattr(
        checker.ConfidenceLedgerSession,
        "from_repo",
        _forbid_from_repo,
    )

    first = checker.build_contract_json_for_write(POLICY_ENGINE_ROOT)
    second = checker.build_contract_json_for_write(POLICY_ENGINE_ROOT)

    assert first == second
    assert "capture_wall_time_seconds" not in first
    payload = json.loads(first)
    receipt = payload["contract_lane_anytime_refusal"]
    assert receipt["confidence_ledger_projection"]["authority_provenance"] == ("verification")
    assert receipt["consumer_promotable"] is False
    assert receipt["non_promotable_reason"] == "verification_only_replay"


def test_n9_contract_rejects_deleted_projection_conditionality() -> None:
    payload = checker.build_payload(POLICY_ENGINE_ROOT)
    corrupted = copy.deepcopy(payload)
    del corrupted["contract_lane_anytime_refusal"]["confidence_ledger_projection"][
        "conditionality_clause"
    ]
    corrupted["contract_content_hash"] = checker._contract_content_hash(corrupted)

    report = checker.validate_payload(corrupted)

    assert report["status"] == "fail"
    assert "contract_lane_anytime_refusal_invalid" in {item["code"] for item in report["issues"]}


def test_n9_source_flip_harness_targets_current_n11_guards_and_tests() -> None:
    cases = checker._source_flip_cases()

    assert "source_flip_non_anytime_preflight_guard" in {item.mutation_id for item in cases}
    assert "source_flip_confidence_projection_recompute_guard" in {
        item.mutation_id for item in cases
    }
    assert "source_flip_ledger_bypass_guard" in {item.mutation_id for item in cases}
    for case in cases:
        for replacement in case.replacements:
            source = (POLICY_ENGINE_ROOT / replacement.relative_path).read_text(encoding="utf-8")
            assert replacement.old in source, case.mutation_id
        for node_id in case.probe_command:
            if "::" not in node_id:
                continue
            relative_path, test_name = node_id.split("::", 1)
            test_source = (POLICY_ENGINE_ROOT / relative_path).read_text(encoding="utf-8")
            assert f"def {test_name}(" in test_source, case.mutation_id
