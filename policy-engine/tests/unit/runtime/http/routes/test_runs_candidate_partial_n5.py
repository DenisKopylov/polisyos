"""Verify the historical quota evidence required by a partial N5 projection."""

from pathlib import Path

import pytest

from polisyos.runtime.http.routes.runs import _require_historical_candidate_quota_stop
from polisyos.scientist.orchestration.engine import ProducerBudgetSourceError, producer_budget
from tests.unit.scientist.orchestration.engine.test_producer_budget_c49 import (
    _diagnostic_owner,
    _digest,
    _finish_invocation,
)


def _served_quota_cut(tmp_path: Path):
    ledger, settlement, binding, policy, observer = _diagnostic_owner(
        tmp_path, total=4, protected=1, purpose="standard"
    )
    _finish_invocation(observer, policy, "prior-seed-17", "standard")
    _finish_invocation(observer, policy, "prior-seed-18", "standard")
    earlier = observer.observe_standard_invocation_capacity()
    assert earlier.status == "available" and earlier.standard_remaining_units == 1
    last = _finish_invocation(observer, policy, "partial-seed-17", "standard")
    exhausted = observer.observe_standard_invocation_capacity()
    assert exhausted.status == "exhausted" and exhausted.protected_remaining_units == 1
    owner, resource, _ = settlement.continuation_binding()
    assert owner == exhausted.settlement_owner
    return (
        ledger,
        earlier,
        {
            "settlement_store": settlement,
            "binding": binding,
            "policy": policy,
            "budget_owner": owner,
            "budget_resource": resource,
            "invocations": ((last.operation_id, last.request_digest, last.profile_digest),),
            "cut": exhausted.source_revision,
        },
    )


def test_partial_candidate_quota_is_reconciled_at_the_producer_cut(tmp_path: Path) -> None:
    ledger, earlier, arguments = _served_quota_cut(tmp_path)
    original = ledger.snapshot()

    _require_historical_candidate_quota_stop(**arguments)
    with pytest.raises(ValueError, match=r"^partial_candidate_quota_exhaustion_not_established$"):
        _require_historical_candidate_quota_stop(**{**arguments, "cut": earlier.source_revision})
    assert ledger.snapshot() == original


def test_partial_candidate_quota_requires_its_bound_completion_and_ledger(tmp_path: Path) -> None:
    ledger, _, arguments = _served_quota_cut(tmp_path)
    original = ledger.snapshot()
    ((operation, _, profile),) = arguments["invocations"]
    with pytest.raises(ProducerBudgetSourceError, match=r"^completed_invocation_record_mismatch$"):
        _require_historical_candidate_quota_stop(
            **{**arguments, "invocations": ((operation, _digest("foreign-request"), profile),)}
        )
    selected = tmp_path / "diagnostic-ledger.json"
    withheld = selected.with_suffix(".withheld")
    selected.rename(withheld)
    try:
        with pytest.raises(
            ProducerBudgetSourceError, match=r"^completed_invocation_source_unavailable$"
        ):
            _require_historical_candidate_quota_stop(**arguments)
    finally:
        withheld.rename(selected)
    _require_historical_candidate_quota_stop(**arguments)
    assert ledger.snapshot() == original


def test_partial_candidate_rejects_replaced_operation_between_owner_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger, _, arguments = _served_quota_cut(tmp_path)
    original = ledger.snapshot()
    ((operation, _, _),) = arguments["invocations"]
    read_snapshot = producer_budget._capacity_store_snapshot
    reads = 0

    def changed_second_snapshot(store, **kwargs):
        nonlocal reads
        reads += 1
        owner, resource, anchor, snapshot = read_snapshot(store, **kwargs)
        if reads == 2:
            reservations = dict(snapshot.invocation_reservations)
            reservations[operation] = reservations[operation].model_copy(
                update={"request_digest": _digest("substituted-after-first-proof")}
            )
            snapshot = snapshot.model_copy(update={"invocation_reservations": reservations})
        return owner, resource, anchor, snapshot

    monkeypatch.setattr(producer_budget, "_capacity_store_snapshot", changed_second_snapshot)
    with pytest.raises(ValueError, match=r"^partial_candidate_quota_exhaustion_not_established$"):
        _require_historical_candidate_quota_stop(**arguments)
    assert reads == 2 and ledger.snapshot() == original
