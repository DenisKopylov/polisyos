from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from tests.unit.runtime.quality.historical_artifacts import (
    GENERATION_CYCLE_V1_BLOB,
    historical_generation_cycle_v1,
    historical_owner_bytes,
)
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
        "policyos.policy_design_case.layer3_gy.n9_promotion.v6"
    }
    assert "generation_cycle_contract_canonical_bytes_drift" in _issue_codes(report)


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
        assert checker.validate_payload(payload)["status"] == "pass"
        assert context.comparison_admissions
        yield payload, context.comparison_plan


def test_source_reissue_preserves_actual_fresh_payload(current_owner_emission, tmp_path):
    """The exact original report reissues to untouched actual fresh owner output."""
    live, plan = current_owner_emission
    destination = tmp_path / checker.OUTPUT_PATH
    destination.parent.mkdir(parents=True)
    original = historical_owner_bytes(GENERATION_CYCLE_V1_BLOB)
    destination.write_bytes(original)
    result = checker._reconcile_frozen_contract(tmp_path, live, plan)
    assert result is live
    assert destination.read_bytes() == original
    assert live["generation_cycle_run"]["synthetic"] is True
    assert all(
        receipt["promoted"] is False
        for receipt in live["generation_cycle_run"]["promotion_port"]["receipts"]
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "historical_inner_hash",
        "historical_body",
        "historical_bytes",
        "current_epoch",
        "admission_omitted",
        "admission_duplicate",
        "unrelated_governing_value",
        "source_status",
    ],
)
def test_source_reissue_rejects_every_changed_binding(current_owner_emission, tmp_path, mutation):
    """Resealing cannot expand the one measured complete-envelope transition."""
    emitted, plan = current_owner_emission
    live = copy.deepcopy(emitted)
    original_bytes = historical_owner_bytes(GENERATION_CYCLE_V1_BLOB)
    historical = json.loads(original_bytes)
    if mutation == "historical_inner_hash":
        historical["comparison_content_hash"] = "sha256:" + "0" * 64
    elif mutation == "historical_body":
        historical["compute_economics"]["owner_io"] = "synthetic_unrelated_change"
    elif mutation == "current_epoch":
        live["schema_version"] = "policyos.synthetic_unknown_generation_cycle.v1"
    elif mutation == "admission_omitted":
        live["comparison_admission_manifest"] = live["comparison_admission_manifest"][:-1]
    elif mutation == "admission_duplicate":
        live["comparison_admission_manifest"].append(
            copy.deepcopy(live["comparison_admission_manifest"][0])
        )
    elif mutation == "unrelated_governing_value":
        live["unrelated_governing_value"] = {"synthetic": True, "value": "changed"}
    elif mutation == "source_status":
        live["generation_cycle_run"]["source_preservation_receipt"]["status"] = "strangled"
    if mutation.startswith("historical_") and mutation != "historical_bytes":
        historical["contract_content_hash"] = checker._contract_content_hash(historical)
        original_bytes = (json.dumps(historical, indent=2, sort_keys=True) + "\n").encode()
    if mutation == "historical_bytes":
        original_bytes += b" "  # Same JSON values do not replace the exact original bytes.
    if mutation not in {"admission_omitted", "admission_duplicate"}:
        checker._set_comparison_identity(live, plan)
    live["contract_content_hash"] = checker._contract_content_hash(live)
    destination = tmp_path / checker.OUTPUT_PATH
    destination.parent.mkdir(parents=True)
    destination.write_bytes(original_bytes)
    with pytest.raises(ValueError, match="generation_cycle_governed_reissue_refused"):
        checker._reconcile_frozen_contract(tmp_path, live, plan)


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
