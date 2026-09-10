"""Behavioral GY-CR2 witnesses against the real CR1 custody boundary."""

from __future__ import annotations

import importlib
import importlib.util
import itertools
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest


def _api():
    name = "polisyos.runtime.quality.constrained_response"
    assert importlib.util.find_spec(name), "CR2 constrained durable response engine is absent"
    return importlib.import_module(name)


def _event(api, **changes):
    payload = {
        "event_id": "event-0",
        "aggregate_id": "response-1",
        "sequence": 0,
        "observed_at": "2026-09-09T08:00:00Z",
        "valid_at": "2026-09-09T08:00:00Z",
        "contract_ref": "contract-v1",
        "claim_ref": "claim-1",
        "population_ref": "population-1",
        "intervention_version": "v1",
        "measurement_epoch": "m1",
        "current": {"E": "E0", "X": "X0", "V": "V0", "C": "C0"},
        "requested": {"E": "E1", "X": "X1", "V": "V0", "C": "C1"},
        "operation": "early_warning",
        "movement": "diagnosis_unresolved",
        "observation": {
            "movement": 1.0,
            "maturity": "mature",
            "health": "valid",
            "expected_denominator": 100,
            "observed_denominator": 100,
        },
        "charter_ref": "charter-candidate-v1",
    }
    payload.update(changes)
    return api.ResponseEvent.model_validate(payload)


def test_every_forbidden_product_and_pairwise_three_way_mutation_is_refused() -> None:
    api = _api()
    domains = (range(5), range(5), range(5), range(4))
    first = set(itertools.product(*domains))
    second = {(e, x, v, c) for e in range(5) for x in range(5) for v in range(5) for c in range(4)}
    assert first == second and len(first) == 500
    counts = {"FCT-01": 0, "FCT-02": 0, "FCT-03": 0, "redesign_claim_inheritance": 0}
    for e, x, v, c in sorted(first):
        event = _event(api, requested={"E": f"E{e}", "X": f"X{x}", "V": f"V{v}", "C": f"C{c}"})
        expected = set()
        if v == 2 and c == 0:
            expected.add("FCT-01")
        if e == 4 and x == 4 and c == 0:
            expected.add("FCT-02")
        if v == 4 and x == 0:
            expected.add("FCT-03")
        if v == 3 and c == 0:
            expected.add("redesign_claim_inheritance")
        result = api.assess_response(event)
        assert set(result.product_violations) == expected
        if expected:
            assert not result.candidate_admissible
            assert result.custody_factors == event.current
        for reason in expected:
            counts[reason] += 1
    # Independent arithmetic over the complete four-factor denominator.
    assert counts == {"FCT-01": 25, "FCT-02": 5, "FCT-03": 20, "redesign_claim_inheritance": 25}
    base = (0, 1, 0, 1)
    for width in (2, 3):
        for axes in itertools.combinations(range(4), width):
            for values in itertools.product(*(domains[i] for i in axes)):
                candidate = list(base)
                for index, value in zip(axes, values, strict=True):
                    candidate[index] = value
                assert tuple(candidate) in first
                e, x, v, c = candidate
                event = _event(
                    api,
                    requested=dict(zip("EXVC", (f"E{e}", f"X{x}", f"V{v}", f"C{c}"), strict=True)),
                )
                result = api.assess_response(event)
                assert bool(result.product_violations) == (
                    (v == 2 and c == 0)
                    or (e == 4 and x == 4 and c == 0)
                    or (v == 4 and x == 0)
                    or (v == 3 and c == 0)
                )


def test_real_intake_refuses_forbidden_state_without_persisting_it_as_current(tmp_path: Path):
    api = _api()
    runtime = api.ConstrainedResponseRuntime.open(root=tmp_path, tenant_id="t", cell_id="c")
    event = _event(api, requested={"E": "E3", "X": "X1", "V": "V2", "C": "C0"})
    receipt = runtime.append(event)
    assert "FCT-01" in receipt.assessment.product_violations
    assert receipt.assessment.custody_factors == event.current
    assert receipt.status == "failed_safe" and not receipt.execution_authorized
    assert runtime.read(receipt.ticket).assessment == receipt.assessment


def test_late_event_appends_correction_and_duplicate_preserves_prior_bytes(tmp_path: Path):
    api = _api()
    runtime = api.ConstrainedResponseRuntime.open(root=tmp_path, tenant_id="t", cell_id="c")
    first = runtime.append(_event(api))
    prior = runtime.read(first.ticket).model_dump(mode="json")
    event = _event(
        api,
        event_id="late-1",
        sequence=1,
        previous_ticket=first.ticket,
        observed_at="2026-09-08T08:00:00Z",
        current=first.assessment.custody_factors.model_dump(),
        operation="refresh",
    )
    late = runtime.append(event)
    assert late.reaction == "correction_opened"
    assert late.previous_ticket == first.ticket
    assert runtime.read(first.ticket).model_dump(mode="json") == prior
    assert runtime.append(event).ticket == late.ticket
    reopened = api.ConstrainedResponseRuntime.open(root=tmp_path, tenant_id="t", cell_id="c")
    assert reopened.read(late.ticket).reaction == "correction_opened"


def test_head_gap_claim_and_conflicting_duplicate_forks_refuse(tmp_path: Path):
    api = _api()
    runtime = api.ConstrainedResponseRuntime.open(root=tmp_path, tenant_id="t", cell_id="c")
    first = runtime.append(_event(api))
    good = _event(
        api,
        event_id="event-1",
        sequence=1,
        previous_ticket=first.ticket,
        current=first.assessment.custody_factors.model_dump(),
    )
    with pytest.raises(ValueError, match="response_sequence_gap"):
        runtime.append(good.model_copy(update={"sequence": 2}))
    with pytest.raises(ValueError, match="response_claim_identity_fork"):
        runtime.append(good.model_copy(update={"claim_ref": "foreign"}))
    with pytest.raises(ValueError, match="response_predecessor_mismatch"):
        runtime.append(good.model_copy(update={"previous_ticket": "foreign-ticket"}))
    second = runtime.append(good)
    assert second.ticket != first.ticket
    with pytest.raises(ValueError, match="response_identity_conflict"):
        runtime.append(good.model_copy(update={"event_id": "competing"}))
    with pytest.raises(ValueError, match="response_predecessor_mismatch"):
        runtime.append(good.model_copy(update={"sequence": 2, "event_id": "stale"}))


def test_concurrent_head_writers_publish_one_exact_slot(tmp_path: Path):
    api = _api()
    roots = [
        api.ConstrainedResponseRuntime.open(root=tmp_path, tenant_id="t", cell_id="c")
        for _ in range(2)
    ]

    def append(i):
        try:
            return roots[i].append(_event(api, event_id=f"competitor-{i}"))
        except ValueError as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(append, range(2)))
    assert sum(isinstance(item, str) for item in results) == 1
    assert "response_identity_conflict" in results


def test_withdrawal_preserves_external_state_but_never_claim_dependent_permission():
    api = _api()
    base = _event(api, requested={"E": "E3", "X": "X0", "V": "V0", "C": "C3"})
    missing = api.assess_response(base)
    declared = api.assess_response(
        base.model_copy(update={"external_continuation_ref": "legal-act"})
    )
    assert missing.custody_factors.X == "X0" and declared.custody_factors.X == "X0"
    assert not missing.claim_dependent_continuation and not declared.claim_dependent_continuation
    assert "external_continuation_basis_not_established" in missing.reasons
    assert "external_continuation_basis_unverified" in declared.reasons
    assert declared.external_continuation_observed


def test_projection_preserves_cr1_status_and_forged_authority_refuses(tmp_path: Path):
    api = _api()
    runtime = api.ConstrainedResponseRuntime.open(root=tmp_path, tenant_id="t", cell_id="c")
    receipt = runtime.append(_event(api))
    from polisyos.runtime.quality.adaptation_transition import KPIControlStateSnapshot

    statuses = set(KPIControlStateSnapshot.model_json_schema()["properties"]["status"]["enum"])
    assert receipt.status in statuses
    assert set(api.ResponseReceipt.model_json_schema()["properties"]["status"]["enum"]) == statuses
    with pytest.raises(ValueError):
        runtime.append(_event(api).model_copy(update={"appointed_signer": "owner"}))
    with pytest.raises(ValueError, match="movement"):
        runtime.append(_event(api).model_copy(update={"movement_vocabulary": "local-cause-v1"}))
    assert datetime.now(UTC).tzinfo is not None


def test_direct_cr1_injection_cannot_forge_chain_or_affected_claim(tmp_path: Path):
    api = _api()
    runtime = api.ConstrainedResponseRuntime.open(root=tmp_path, tenant_id="t", cell_id="c")
    event = _event(api)
    forged = _event(api, requested={"E": "E4", "X": "X4", "V": "V0", "C": "C0"})
    forged = forged.model_copy(update={"claim_depends_on_unacceptable_basis": False})
    assert "FCT-02" in runtime.append(forged).assessment.product_violations
    event = event.model_copy(update={"aggregate_id": "direct-injection"})
    request = runtime._request(event).model_copy(update={"request_id": "not-the-bound-slot"})
    ticket = runtime.custody.submit(request)
    runtime.custody.process(ticket)
    with pytest.raises(ValueError, match="response_ticket_identity_invalid"):
        runtime.read(ticket)


def test_operation_synonym_cannot_reopen_protected_exposure():
    api = _api()
    event = _event(
        api,
        operation="observe",
        current={"E": "E2", "X": "X3", "V": "V0", "C": "C1"},
        requested={"E": "E2", "X": "X0", "V": "V0", "C": "C1"},
    )
    result = api.assess_response(event)
    assert not result.candidate_admissible
    assert "exposure_expansion_without_restart" in result.reasons
    assert result.custody_factors.X == "X3"


def test_removing_product_semantics_keeps_markers_and_turns_battery_red(monkeypatch):
    api = _api()
    original = api.assess_response

    def erased(event):
        return original(event).model_copy(
            update={
                "product_violations": (),
                "candidate_admissible": True,
                "custody_factors": event.requested,
            }
        )

    monkeypatch.setattr(api, "assess_response", erased)
    with pytest.raises(AssertionError) as red:
        test_every_forbidden_product_and_pairwise_three_way_mutation_is_refused()
    sys.stdout.write("product_semantics_removal_battery_red: " + str(red.value) + "\n")


def test_direct_cr1_forbidden_genesis_is_refused_by_shared_history_validation(tmp_path: Path):
    api = _api()
    runtime = api.ConstrainedResponseRuntime.open(root=tmp_path, tenant_id="t", cell_id="c")
    event = _event(api, current={"E": "E0", "X": "X0", "V": "V4", "C": "C1"})
    ticket = runtime.custody.submit(runtime._request(event))
    runtime.custody.process(ticket)
    with pytest.raises(ValueError, match="response_initial_state_forbidden"):
        runtime.read(ticket)
    for e, x, v, c in itertools.product(range(5), range(5), range(5), range(4)):
        origin = _event(api, current={"E": f"E{e}", "X": f"X{x}", "V": f"V{v}", "C": f"C{c}"})
        forbidden = (
            (v == 2 and c == 0)
            or (e == 4 and x == 4 and c == 0)
            or (v == 4 and x == 0)
            or (v == 3 and c == 0)
        )
        if forbidden:
            with pytest.raises(ValueError, match="response_initial_state_forbidden"):
                runtime._check_predecessor(origin, None)
        else:
            runtime._check_predecessor(origin, None)
