"""Replay actual durable quota completions without running a numerical producer."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.scientist.orchestration.engine import (
    ProducerBudgetSourceError,
    verify_completed_standard_invocations_historical,
)
from tests.unit.scientist.orchestration.engine.test_producer_budget_c49 import (
    _diagnostic_owner,
    _digest,
    _finish_invocation,
)


def _completed(tmp_path: Path, *, purpose: str = "standard", outcome: str = "completed"):
    ledger, middleware, binding, policy, observer = _diagnostic_owner(
        tmp_path, total=4, protected=1, purpose="standard"
    )
    reservation = _finish_invocation(observer, policy, "actual-call", purpose, outcome)
    owner = observer.observe_standard_invocation_capacity().settlement_owner
    rows = ((reservation.operation_id, reservation.request_digest, reservation.profile_digest),)
    return ledger, {
        "settlement_store": middleware,
        "expected_run_binding": binding,
        "expected_policy": policy,
        "expected_settlement_owner": owner,
        "expected_invocations": rows,
    }


def test_completed_standard_replay_reads_exact_durable_rows_without_reserving(tmp_path: Path):
    ledger, arguments = _completed(tmp_path)
    before = ledger.snapshot()
    (record,) = verify_completed_standard_invocations_historical(**arguments)
    assert record == before.invocation_reservations[record.operation_id]
    assert record.status == "completed" and record.purpose == "standard" and record.units == 1
    assert ledger.snapshot() == before


@pytest.mark.parametrize(
    ("purpose", "outcome"),
    [("standard", "failed"), ("diagnostic", "completed")],
)
def test_terminal_count_cannot_replace_completed_standard_proof(
    tmp_path: Path, purpose: str, outcome: str
):
    ledger, arguments = _completed(tmp_path, purpose=purpose, outcome=outcome)
    assert len(ledger.snapshot().invocation_reservations) == 1
    with pytest.raises(ProducerBudgetSourceError, match="^completed_invocation_record_mismatch$"):
        verify_completed_standard_invocations_historical(**arguments)


@pytest.mark.parametrize("field", ["request", "profile", "owner", "run", "policy"])
def test_completed_standard_replay_refuses_foreign_owner_or_selected_content(
    tmp_path: Path, field: str
):
    _ledger, arguments = _completed(tmp_path)
    operation, request, profile = arguments["expected_invocations"][0]
    if field == "request":
        arguments["expected_invocations"] = ((operation, _digest("foreign-request"), profile),)
    elif field == "profile":
        arguments["expected_invocations"] = ((operation, request, _digest("foreign-profile")),)
    elif field == "owner":
        original = arguments["expected_settlement_owner"]
        arguments["expected_settlement_owner"] = ("foreign-ledger", *original[1:])
    elif field == "run":
        arguments["expected_run_binding"] = arguments["expected_run_binding"].model_copy(
            update={"control_job_id": "foreign-job"}
        )
    else:
        original = arguments["expected_policy"]
        arguments["expected_policy"] = original.model_copy(
            update={"total_units": original.total_units + 1}
        )
    with pytest.raises(
        ProducerBudgetSourceError, match="^completed_invocation_(owner|record)_mismatch$"
    ):
        verify_completed_standard_invocations_historical(**arguments)


def test_completed_standard_replay_requires_the_existing_ledger_and_restores(tmp_path: Path):
    ledger, arguments = _completed(tmp_path)
    before = ledger.snapshot()
    selected = tmp_path / "diagnostic-ledger.json"
    hidden = selected.with_suffix(".removed")
    selected.replace(hidden)
    try:
        with pytest.raises(
            ProducerBudgetSourceError, match="^completed_invocation_source_unavailable$"
        ):
            verify_completed_standard_invocations_historical(**arguments)
        assert not selected.exists()
    finally:
        hidden.replace(selected)
    (record,) = verify_completed_standard_invocations_historical(**arguments)
    assert record == before.invocation_reservations[record.operation_id]
    assert ledger.snapshot() == before


def test_completed_standard_replay_rejects_duplicate_operation_denominator(tmp_path: Path):
    _ledger, arguments = _completed(tmp_path)
    arguments["expected_invocations"] *= 2
    with pytest.raises(
        ProducerBudgetSourceError, match="^completed_invocation_selection_duplicate$"
    ):
        verify_completed_standard_invocations_historical(**arguments)
