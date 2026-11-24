"""Verify the historical quota evidence required by a partial N5 projection."""

from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core import artifacts, canon
from polisyos.runtime.quality.candidate_source_reentry_history import (
    CandidateExperimentQuotaInterruptionWitness,
    _candidate_quota_witness_options,
    _read_candidate_quota_witness,
    _recheck_candidate_quota_custody_ledger,
    _require_historical_candidate_quota_stop,
)
from polisyos.scientist.orchestration.engine import (
    BudgetLedgerReentryBudgetScope,
    ProducerBudgetSourceError,
    producer_budget,
)
from tests.unit.scientist.orchestration.engine.test_producer_budget_c49 import (
    _diagnostic_owner,
    _digest,
    _finish_invocation,
    _settle,
)


def _served_quota_cut(tmp_path: Path):
    ledger, settlement, binding, policy, observer = _diagnostic_owner(
        tmp_path, total=4, protected=1, purpose="standard"
    )
    _finish_invocation(observer, policy, "prior-seed-17", "standard")
    _finish_invocation(observer, policy, "prior-seed-18", "standard")
    _settle(settlement, binding, "original-source", "0.1")
    window = settlement.open_reentry_budget_window_safe(
        BudgetLedgerReentryBudgetScope(
            run_binding=binding,
            action_job_id="partial-action",
            action_generation=1,
            route_id="sha256:" + _digest("partial-route"),
            action_phase_ref="sha256:" + _digest("executing-phase"),
            source_payload_ref="sha256:" + _digest("partial-source"),
            profile_selection_ref="sha256:" + _digest("selected-profile"),
        ),
        fresh_limit_usd=Decimal("1"),
        global_limit_usd=Decimal("1"),
    )
    earlier = observer.observe_standard_invocation_capacity()
    assert earlier.status == "available" and earlier.standard_remaining_units == 1
    assert earlier.source_revision == window.revision
    last = _finish_invocation(observer, policy, "partial-seed-17", "standard")
    exhausted = observer.observe_standard_invocation_capacity()
    assert exhausted.status == "exhausted" and exhausted.protected_remaining_units == 1
    owner, resource, _ = settlement.continuation_binding()
    assert owner == exhausted.settlement_owner
    return (
        ledger,
        earlier,
        window,
        {
            "settlement_store": settlement,
            "binding": binding,
            "policy": policy,
            "budget_owner": owner,
            "budget_resource": resource,
            "invocations": ((last.operation_id, last.request_digest, last.profile_digest),),
            "after_revision": earlier.source_revision,
            "cut": exhausted.source_revision,
        },
    )


def test_partial_candidate_quota_is_reconciled_at_the_producer_cut(tmp_path: Path) -> None:
    ledger, earlier, _, arguments = _served_quota_cut(tmp_path)
    original = ledger.snapshot()

    _require_historical_candidate_quota_stop(**arguments)
    with pytest.raises(ValueError, match=r"^partial_candidate_quota_exhaustion_not_established$"):
        _require_historical_candidate_quota_stop(**{**arguments, "cut": earlier.source_revision})
    assert ledger.snapshot() == original


def test_partial_candidate_quota_requires_its_bound_completion_and_ledger(tmp_path: Path) -> None:
    ledger, _, _, arguments = _served_quota_cut(tmp_path)
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


def test_sealed_partial_quota_cut_survives_unrelated_ledger_rollover(tmp_path: Path) -> None:
    ledger, _, _, arguments = _served_quota_cut(tmp_path)
    sealed = _require_historical_candidate_quota_stop(**arguments)
    original = ledger.snapshot()
    for _ in range(33):
        ledger.record_spend("unrelated", Decimal("0.01"))
    later = ledger.snapshot()
    assert later.revision == original.revision + 33
    assert later.invocation_reservations == original.invocation_reservations
    assert min(row.revision for row in later.recent_mutations) > arguments["cut"]

    with pytest.raises(ValueError, match=r"^partial_candidate_quota_exhaustion_not_established$"):
        _require_historical_candidate_quota_stop(**arguments)
    assert _require_historical_candidate_quota_stop(**arguments, sealed_cut=sealed) == sealed
    with pytest.raises(ValueError, match=r"^partial_candidate_quota_exhaustion_not_established$"):
        _require_historical_candidate_quota_stop(
            **arguments, sealed_cut=sealed.model_copy(update={"active_at_cut": 1})
        )
    assert ledger.snapshot() == later


def test_partial_quota_witness_requires_the_selected_profile(tmp_path: Path) -> None:
    ledger, _, window, arguments = _served_quota_cut(tmp_path)
    cut = _require_historical_candidate_quota_stop(**arguments)
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    binding = arguments["binding"]
    scope = {"tenant_id": binding.tenant_id, "cell_id": binding.cell_id}
    canon_spec = canon.CanonSpec(forbid_floats=False)

    def parent(kind: str) -> artifacts.ArtifactRef:
        return store.put_json(
            {"fixture_kind": kind},
            artifacts.ArtifactWriteOptions(kind=kind, media_type="application/json"),
            return_selected_profile=True,
        )

    witness = CandidateExperimentQuotaInterruptionWitness(
        reentry_ref=parent("runtime_quality.candidate_source_reentry_receipt"),
        action_ref=parent("runtime_quality.acquisition_candidate_action_receipt"),
        n5_input_ref=parent("runtime.quality.candidate_simulation_n5_input"),
        n5_result_ref=parent("polisyos.runtime.joint_simulation_result"),
        window_id=window.window_id,
        window_digest=window.record_digest,
        budget_owner=arguments["budget_owner"],
        budget_resource=arguments["budget_resource"],
        quota_cut=cut,
    )
    options = _candidate_quota_witness_options(witness, **scope)
    payload = witness.model_dump(mode="json")
    selected = store.put_json(payload, options, canon_spec, return_selected_profile=True)
    sibling = store.put_json(
        payload,
        artifacts.ArtifactWriteOptions(
            kind=options.kind,
            media_type=options.media_type,
            producer=artifacts.ProducerInfo(component="test.other-witness-view", version="1.0"),
        ),
        canon_spec,
        return_selected_profile=True,
    )
    assert selected.artifact_id == sibling.artifact_id
    assert selected.manifest_profile_sha256 != sibling.manifest_profile_sha256
    assert _read_candidate_quota_witness(store, selected, **scope) == witness

    recheck = {
        "settlement_store": arguments["settlement_store"],
        "window": window,
        "witness": witness,
    }
    _recheck_candidate_quota_custody_ledger(**recheck)
    ((operation, _, _),) = arguments["invocations"]
    latest = ledger.snapshot()
    assert latest is not None
    reservations = dict(latest.invocation_reservations)
    del reservations[operation]
    snapshot_path = tmp_path / "diagnostic-ledger.json"
    original = snapshot_path.read_bytes()
    snapshot_path.write_text(
        latest.model_copy(update={"invocation_reservations": reservations}).model_dump_json()
    )
    try:
        with pytest.raises(ValueError, match="candidate_quota_custody_ledger_changed"):
            _recheck_candidate_quota_custody_ledger(**recheck)
    finally:
        snapshot_path.write_bytes(original)
    _recheck_candidate_quota_custody_ledger(**recheck)

    path = store._manifest_path_for_ref(selected.artifact_id, selected.manifest_profile_sha256)
    withheld = path.with_name(path.name + ".withheld")
    path.rename(withheld)
    try:
        reader = artifacts.FileSystemCAS.open_existing_read_only(store.root)
        assert reader.verify(sibling).ok
        with pytest.raises(ValueError, match="candidate_reentry_history_selected_profile_invalid"):
            _read_candidate_quota_witness(reader, selected, **scope)
    finally:
        withheld.rename(path)
    assert _read_candidate_quota_witness(store, selected, **scope) == witness


@pytest.mark.parametrize("sealed", [False, True])
def test_partial_candidate_rejects_replaced_operation_between_owner_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sealed: bool
) -> None:
    ledger, _, _, arguments = _served_quota_cut(tmp_path)
    original = ledger.snapshot()
    proof = _require_historical_candidate_quota_stop(**arguments) if sealed else None
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
        _require_historical_candidate_quota_stop(**arguments, sealed_cut=proof)
    assert reads == 2 and ledger.snapshot() == original
