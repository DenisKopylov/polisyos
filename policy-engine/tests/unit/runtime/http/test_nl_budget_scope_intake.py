"""Signed request snapshot preserves the explicit budget-scope choice."""

from copy import deepcopy

import pytest

from polisyos.core.contracts.control import NaturalLanguageRunRequest
from polisyos.runtime.http.services.control.job_attempt_publication import (
    _nl_request_snapshot_content_hash,
    _nl_request_snapshot_schema,
    _validate_nl_request_snapshot,
)
from tests.unit.runtime.http.test_nl_predictive_basis_intake import _payload_for_snapshot


@pytest.mark.parametrize(
    "mode",
    [None, "hard_total_usd", "metered_paid_producers_and_bounded_candidate"],
)
def test_budget_scope_snapshot_binds_explicit_presence_and_value(mode) -> None:
    request = NaturalLanguageRunRequest(
        request="Assess the candidate",
        llm_model="simulated-qwen",
        run_budget_usd=5.0,
        run_budget_scope=mode,
    )
    assert _nl_request_snapshot_schema(request) == "polisyos.runtime.control_nl_request_snapshot.v4"
    payload = _payload_for_snapshot(request)
    payload["run_budget_scope"] = mode
    snapshot = payload["nl_request_snapshot"]
    receipt = {"request_content_hash": _nl_request_snapshot_content_hash(snapshot)}
    _validate_nl_request_snapshot(payload, receipt)
    for changed_value in ({}, {"run_budget_scope": "hard_total_usd"}, {"run_budget_usd": 6.0}):
        changed = deepcopy(payload)
        if not changed_value:
            changed.pop("run_budget_scope")
        else:
            changed.update(changed_value)
        if changed == payload:
            continue
        with pytest.raises(ValueError, match="nl_authorized_request_payload_mismatch"):
            _validate_nl_request_snapshot(changed, receipt)
    changed = deepcopy(payload)
    changed["nl_request_snapshot"]["request"]["run_budget_scope"] = (
        "hard_total_usd" if mode != "hard_total_usd" else None
    )
    with pytest.raises(ValueError, match="nl_authorized_request_snapshot_receipt_mismatch"):
        _validate_nl_request_snapshot(changed, receipt)


def test_legacy_snapshot_omits_budget_scope_and_rejects_injection() -> None:
    request = NaturalLanguageRunRequest(request="Assess the candidate", llm_model="simulated-qwen")
    payload = _payload_for_snapshot(request)
    assert _nl_request_snapshot_schema(request) == "polisyos.runtime.control_nl_request_snapshot.v1"
    assert "run_budget_scope" not in payload["nl_request_snapshot"]["request"]
    payload["run_budget_scope"] = "metered_paid_producers_and_bounded_candidate"
    with pytest.raises(ValueError, match="nl_authorized_request_payload_mismatch"):
        _validate_nl_request_snapshot(payload, None)


def test_budget_scope_snapshot_preserves_optional_temporal_cursor() -> None:
    request = NaturalLanguageRunRequest.model_validate(
        {
            "request": "Assess the candidate",
            "llm_model": "simulated-qwen",
            "run_budget_usd": 5.0,
            "run_budget_scope": "metered_paid_producers_and_bounded_candidate",
            "temporal_scope": {"branch": "main", "tx_at": None},
        }
    )
    payload = _payload_for_snapshot(request)
    payload["run_budget_scope"] = request.run_budget_scope
    payload["temporal_scope"] = request.model_dump(mode="json")["temporal_scope"]
    snapshot = payload["nl_request_snapshot"]
    receipt = {"request_content_hash": _nl_request_snapshot_content_hash(snapshot)}
    _validate_nl_request_snapshot(payload, receipt)
    changed = deepcopy(payload)
    changed["temporal_scope"]["branch"] = "foreign"
    with pytest.raises(ValueError, match="nl_authorized_request_payload_mismatch"):
        _validate_nl_request_snapshot(changed, receipt)


@pytest.mark.parametrize("intent", [None, "bounded_experiment_voi_unknown"])
def test_experiment_snapshot_v5_binds_original_presence_and_rejects_downgrade(intent) -> None:
    request = NaturalLanguageRunRequest(
        request="Assess the candidate",
        llm_model="simulated-qwen",
        run_budget_usd=5.0,
        run_budget_scope="metered_paid_producers_and_bounded_candidate",
        candidate_acquisition_intent=intent,
    )
    payload = _payload_for_snapshot(request)
    payload["run_budget_scope"] = request.run_budget_scope
    payload["candidate_acquisition_intent"] = intent
    snapshot = payload["nl_request_snapshot"]
    assert snapshot["schema_version"] == "polisyos.runtime.control_nl_request_snapshot.v5"
    receipt = {"request_content_hash": _nl_request_snapshot_content_hash(snapshot)}
    _validate_nl_request_snapshot(payload, receipt)
    for field in ("candidate_acquisition_intent", "run_budget_scope"):
        changed = deepcopy(payload)
        changed.pop(field)
        with pytest.raises(ValueError, match="nl_authorized_request_payload_mismatch"):
            _validate_nl_request_snapshot(changed, receipt)
    downgraded = deepcopy(payload)
    downgraded["nl_request_snapshot"]["schema_version"] = (
        "polisyos.runtime.control_nl_request_snapshot.v4"
    )
    downgraded_receipt = {
        "request_content_hash": _nl_request_snapshot_content_hash(downgraded["nl_request_snapshot"])
    }
    with pytest.raises(ValueError, match="nl_authorized_request_snapshot_not_canonical"):
        _validate_nl_request_snapshot(downgraded, downgraded_receipt)


def test_experiment_snapshot_v5_can_record_absent_budget_scope_without_grant() -> None:
    request = NaturalLanguageRunRequest(
        request="Assess the candidate",
        llm_model="simulated-qwen",
        candidate_acquisition_intent="bounded_experiment_voi_unknown",
    )
    payload = _payload_for_snapshot(request)
    payload["candidate_acquisition_intent"] = request.candidate_acquisition_intent
    snapshot = payload["nl_request_snapshot"]
    assert "run_budget_scope" not in snapshot["request"]
    _validate_nl_request_snapshot(
        payload, {"request_content_hash": _nl_request_snapshot_content_hash(snapshot)}
    )
