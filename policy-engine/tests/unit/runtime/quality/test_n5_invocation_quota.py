"""Real N5 physical-call quota, journal, and fresh candidate-result witnesses.

The external cost wire is controlled. NCM, USD admission, invocation admission,
the durable ledger, receipt encoding, and fresh CAS readers remain real. These
checks establish invocation accounting, not a USD price or scientific authority.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import pytest

from polisyos.core.artifacts import read_core_json_artifact
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
from polisyos.runtime.quality.generation_cycle import (
    _joint_simulation_port_outcome,
    load_joint_simulation_result,
    persist_joint_simulation_result,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    JointSimulationHorizonController,
    JointSimulationRequest,
    JointSimulationResult,
    NCMConditionalComparatorProfile,
    verify_simulation_receipt,
)
from polisyos.scientist.orchestration.engine import (
    BudgetInvocationQuotaPolicy,
    BudgetLedgerInvocationProfile,
)
from polisyos.scientist.orchestration.engine.budget import BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerProducerRunBinding,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.producer_budget import (
    ProducerBudgetObserver,
    ProducerBudgetSourceError,
)
from tests.unit.runtime.quality.test_c49_native_stopping_budget import (
    _native_request,
    _producer_owner,
    _real_provider_charge,
)

_Purpose = Literal["standard", "diagnostic", "counterevidence"]


def _quota_owner(
    path: Path, *, total: int, protected: int
) -> tuple[
    BudgetMiddleware,
    BudgetLedgerProducerRunBinding,
    BudgetState,
    BudgetLedgerInvocationProfile,
]:
    middleware, binding, state = _producer_owner(path, cap="10")
    _real_provider_charge(middleware, binding, 0.2, "settled-before-native-quota-work")
    profile = BudgetLedgerInvocationProfile.from_policy(
        binding,
        BudgetInvocationQuotaPolicy(
            allocation_id="native-n5-invocation-allocation",
            total_units=total,
            protected_units=protected,
        ),
    )
    return middleware, binding, state, profile


def _observer(
    middleware: BudgetMiddleware,
    binding: BudgetLedgerProducerRunBinding,
    state: BudgetState,
    profile: BudgetLedgerInvocationProfile | None,
    *,
    purpose: _Purpose = "standard",
) -> ProducerBudgetObserver:
    return ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
        invocation_quota_profile=profile,
        invocation_purpose=purpose,
    )


def _one_call_request(*, seed: int = 31) -> JointSimulationRequest:
    request = _native_request()
    return request.model_copy(
        update={
            "intervention_atoms": (request.intervention_atoms[0],),
            "replications": 1,
            "seed": seed,
        }
    )


def _record_native_calls(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    original = NCMEngineMethod.pure_step
    calls: list[int] = []

    def actual_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        calls.append(int(params["__seed__"]))
        return original(state, params)

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(actual_step))
    return calls


def _fresh_result(
    path: Path, result: JointSimulationResult, request: JointSimulationRequest | None
) -> JointSimulationResult:
    ref = persist_joint_simulation_result(result, store=FileSystemCAS(path))
    reader = FileSystemCAS.open_existing_read_only(path)
    assert ref.manifest_profile_sha256 is not None
    if request is not None:
        fresh = load_joint_simulation_result(ref, store=reader, expected_request=request)
    else:
        # Interrupted reports remain readable audit bytes; the numerical
        # result reader does not admit an incomplete trajectory as success.
        selected = read_core_json_artifact(reader, ref)
        assert selected.status == "declared_bytes_conformant"
        assert selected.selected_manifest_profile_sha256 == ref.manifest_profile_sha256
        payload = selected.value
        assert isinstance(payload, dict)
        fresh = JointSimulationResult.model_validate(payload)
        verify_simulation_receipt(
            fresh.receipt, {key: value for key, value in payload.items() if key != "receipt"}
        )
    assert fresh.physical_work_observations == result.physical_work_observations
    assert fresh.engine_decisions == result.engine_decisions
    assert [row.model_dump(mode="json") for row in fresh.trajectories] == [
        row.model_dump(mode="json") for row in result.trajectories
    ]
    return fresh


def test_native_seed_calls_and_cached_roles_preserve_protected_partition_and_fresh_joins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each real comparator/spec/seed costs one unit; reused roles leave protected work available."""
    owner_path = tmp_path / "owner"
    middleware, binding, state, profile = _quota_owner(owner_path, total=10, protected=2)
    usd_before = FileBudgetLedger(owner_path / "ledger.json").snapshot().state
    standard = _observer(middleware, binding, state, profile)
    calls = _record_native_calls(monkeypatch)
    request = _native_request().model_copy(
        update={
            "evidence_state": {"income_delta": 0.0, "balance_delta": 0.0},
            "comparator_profile": NCMConditionalComparatorProfile(
                outcome_units={"firm_survival": "synthetic_score"}
            ),
        }
    )

    result = JointSimulationHorizonController(producer_budget_observer=standard).run(request)

    # Comparator, left, right, and pair specifications each run at two seeds.
    # Joint is a projection of the pair, never a ninth/tenth physical call.
    assert Counter(calls) == {11: 4, 12: 4}
    assert len(result.physical_work_observations) == 8
    assert len({work.physical_spec_ref for work in result.physical_work_observations}) == 4
    assert result.diagnostics["physical_work_units"] == 8
    assert result.diagnostics["invocation_quota_capacity"] == "protected_profile_configured"
    assert result.diagnostics["invocation_quota_verification"] == "fresh_ledger_read_required"
    pair = result.trajectory_for("pairwise", result.atom_ids)
    joint = result.trajectory_for("joint", result.atom_ids)
    assert pair.diagnostics["physical_run_ref"] == joint.diagnostics["physical_run_ref"]
    assert (
        pair.diagnostics["physical_work_event_ids"] == joint.diagnostics["physical_work_event_ids"]
    )
    assert joint.diagnostics["physical_run_reused"] is True
    # The fixture's SCM is 1 + 2*a + 3*b + 5*a*b + u. Shared-seed
    # comparator subtraction removes u, giving 10 for a=b=1.
    assert joint.points[0].effect["firm_survival"] == pytest.approx(10.0)
    assert result.diagnostics["effect_basis_status"] == "established"
    fresh = _fresh_result(tmp_path / "standard-cas", result, request)
    assert _joint_simulation_port_outcome(fresh, request=request)[0] == "joint_simulated"

    snapshot = FileBudgetLedger(owner_path / "ledger.json").snapshot()
    assert snapshot.invocation_profiles[binding.run_id] == profile
    assert len(snapshot.invocation_reservations) == 8 < profile.total_units
    exhausted = JointSimulationHorizonController(producer_budget_observer=standard).run(request)
    assert exhausted.diagnostics["physical_work_interruption"] == "n5_invocation_quota_exhausted"
    assert exhausted.physical_work_observations == ()
    assert exhausted.trajectories == ()
    assert len(calls) == 8

    results = [fresh]
    for purpose, seed in (("diagnostic", 31), ("counterevidence", 47)):
        protected_observer = _observer(middleware, binding, state, profile, purpose=purpose)
        protected_request = _one_call_request(seed=seed)
        protected_result = JointSimulationHorizonController(
            producer_budget_observer=protected_observer
        ).run(protected_request)
        assert len(protected_result.physical_work_observations) == 1
        assert protected_result.physical_work_observations[0].invocation_quota_purpose == purpose
        assert protected_result.trajectory_for("joint", protected_result.atom_ids).points[0].effect[
            "firm_survival"
        ] == pytest.approx(2.0)
        results.append(
            _fresh_result(tmp_path / f"{purpose}-cas", protected_result, protected_request)
        )
        if purpose == "diagnostic":
            still_refused = JointSimulationHorizonController(producer_budget_observer=standard).run(
                _one_call_request(seed=43)
            )
            assert still_refused.diagnostics["physical_work_interruption"] == (
                "n5_invocation_quota_exhausted"
            )
            assert still_refused.physical_work_observations == ()
            assert len(calls) == 9

    assert len(calls) == 10
    diagnostic = _observer(middleware, binding, state, profile, purpose="diagnostic")
    stopped = JointSimulationHorizonController(producer_budget_observer=diagnostic).run(
        _one_call_request(seed=59)
    )
    assert stopped.diagnostics["physical_work_interruption"] == "n5_invocation_quota_exhausted"
    assert stopped.physical_work_observations == ()
    assert len(calls) == 10
    fresh_ledger = FileBudgetLedger(owner_path / "ledger.json").snapshot()
    work = [item for produced in results for item in produced.physical_work_observations]
    assert set(fresh_ledger.invocation_reservations) == {
        item.invocation_quota_operation_id for item in work
    }
    assert Counter(record.purpose for record in fresh_ledger.invocation_reservations.values()) == {
        "standard": 8,
        "diagnostic": 1,
        "counterevidence": 1,
    }
    for item in work:
        record = fresh_ledger.invocation_reservations[item.invocation_quota_operation_id]
        assert record.request_digest == item.invocation_quota_request_digest
        assert (
            record.profile_digest == item.invocation_quota_profile_digest == profile.profile_digest
        )
        assert record.run_id == binding.run_id
        assert record.units == item.work_units == 1
        assert record.status == item.invocation_quota_status == "completed"
        assert record.purpose == item.invocation_quota_purpose
        assert item.usd_cost is None and item.usd_cost_status == "not_established"
    assert fresh_ledger.state == usd_before
    assert state.spent["run"] == Decimal("0.2")
    assert profile.price_origin == "unknown"


@pytest.mark.parametrize(
    "fault",
    ["producer", "finish-single", "finish-partial"],
    ids=["failed", "unknown-retained-role", "unknown-partial-replicates"],
)
def test_failed_or_unresolved_native_call_stays_counted_across_fresh_read_and_reentry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    """An error never refunds an attempted physical call or authorizes a retry."""
    owner_path = tmp_path / "owner"
    middleware, binding, state, profile = _quota_owner(owner_path, total=1, protected=0)
    observer = _observer(middleware, binding, state, profile)
    calls = _record_native_calls(monkeypatch)
    request = _one_call_request()
    if fault == "finish-partial":
        request = request.model_copy(update={"replications": 2})
    with monkeypatch.context() as failure:
        if fault == "producer":

            def fail_selected(
                state: Mapping[str, Any], params: Mapping[str, Any]
            ) -> dict[str, Any]:
                del state
                calls.append(int(params["__seed__"]))
                raise ValueError("controlled selected-producer failure")

            failure.setattr(NCMEngineMethod, "pure_step", staticmethod(fail_selected))
        else:

            def cannot_record_outcome(self: FileBudgetLedger, *args: Any, **kwargs: Any) -> None:
                del self, args, kwargs
                raise OSError("controlled terminal journal write failure")

            failure.setattr(FileBudgetLedger, "finish_invocation", cannot_record_outcome)
        result = JointSimulationHorizonController(producer_budget_observer=observer).run(request)

    assert calls == [request.seed]
    assert len(result.physical_work_observations) == 1
    work = result.physical_work_observations[0]
    expected_code = (
        "n5_physical_work_failed"
        if fault == "producer"
        else "n5_invocation_quota_outcome_unresolved"
    )
    assert result.diagnostics["physical_work_interruption"] == expected_code
    assert work.status == ("failed" if fault == "producer" else "completed")
    assert work.invocation_quota_status == ("failed" if fault == "producer" else "unknown")
    if fault != "producer":
        assert expected_code in result.promotion_ready_value_packet["authority_blockers"]
        assert (
            "simulation_only_k_sim_not_world_evidence"
            in (result.promotion_ready_value_packet["authority_blockers"])
        )
    assert result.diagnostics["requested_replications"] == request.replications
    assert result.diagnostics["replication_seeds"] == [
        request.seed + offset for offset in range(request.replications)
    ]
    if fault == "finish-single":
        retained = result.trajectory_for("individual", result.atom_ids)
        assert retained.points[0].effect["firm_survival"] == pytest.approx(2.0)
        assert retained.diagnostics["requested_replications"] == 1
        assert retained.diagnostics["actual_replications"] == 1
    else:
        # A failed producer or only one of two requested samples cannot be
        # relabeled as a completed role by shrinking the declared denominator.
        assert result.trajectories == ()
    fresh = _fresh_result(tmp_path / "interrupted-cas", result, None)
    record = (
        FileBudgetLedger(owner_path / "ledger.json")
        .snapshot()
        .invocation_reservations[work.invocation_quota_operation_id]
    )
    assert record.request_digest == work.invocation_quota_request_digest
    assert record.status == ("failed" if fault == "producer" else "reserved")
    if fault != "finish-single":
        assert _joint_simulation_port_outcome(fresh, request=request)[0] == "simulation_blocked"
    else:
        _, blockers = _joint_simulation_port_outcome(fresh, request=request)
        assert expected_code in blockers
        assert "simulation_only_k_sim_not_world_evidence" in blockers
    reopened_middleware, reopened_binding, reopened_state = _producer_owner(owner_path, cap="10")
    reopened_observer = _observer(reopened_middleware, reopened_binding, reopened_state, profile)
    retry = JointSimulationHorizonController(producer_budget_observer=reopened_observer).run(
        request
    )
    assert retry.diagnostics["physical_work_interruption"] == "n5_invocation_quota_exhausted"
    assert retry.physical_work_observations == ()
    assert calls == [request.seed]
    assert len(FileBudgetLedger(owner_path / "ledger.json").snapshot().invocation_reservations) == 1


def test_durable_quota_finish_with_lost_ack_retains_unknown_candidate_and_consumed_unit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A lost finish acknowledgement cannot refund durable work or certify its accounting."""
    owner_path = tmp_path / "owner"
    middleware, binding, state, profile = _quota_owner(owner_path, total=1, protected=0)
    observer = _observer(middleware, binding, state, profile)
    calls = _record_native_calls(monkeypatch)
    request = _one_call_request()
    actual_finish = FileBudgetLedger.finish_invocation
    completed_operations: list[str] = []

    def finish_then_lose_ack(
        self: FileBudgetLedger,
        operation_id: str,
        request_digest: str,
        *,
        profile: BudgetLedgerInvocationProfile,
        outcome: Literal["completed", "failed", "unknown"],
    ) -> None:
        record = actual_finish(self, operation_id, request_digest, profile=profile, outcome=outcome)
        completed_operations.append(record.operation_id)
        raise OSError("controlled lost acknowledgement after durable quota finish")

    with monkeypatch.context() as failure:
        failure.setattr(FileBudgetLedger, "finish_invocation", finish_then_lose_ack)
        result = JointSimulationHorizonController(producer_budget_observer=observer).run(request)

    code = "n5_invocation_quota_outcome_unresolved"
    assert result.diagnostics["physical_work_interruption"] == code
    assert calls == [request.seed]
    assert len(result.physical_work_observations) == 1
    work = result.physical_work_observations[0]
    assert completed_operations == [work.invocation_quota_operation_id]
    assert work.status == "completed"
    assert work.invocation_quota_status == "unknown"
    retained = result.trajectory_for("individual", result.atom_ids)
    assert retained.points[0].effect["firm_survival"] == pytest.approx(2.0)
    assert retained.diagnostics["requested_replications"] == 1
    assert retained.diagnostics["actual_replications"] == 1
    fresh = _fresh_result(tmp_path / "lost-ack-cas", result, None)
    _, blockers = _joint_simulation_port_outcome(fresh, request=request)
    assert code in blockers
    assert "simulation_only_k_sim_not_world_evidence" in blockers
    snapshot = FileBudgetLedger(owner_path / "ledger.json").snapshot()
    record = snapshot.invocation_reservations[work.invocation_quota_operation_id]
    assert record.status == "completed"
    assert record.request_digest == work.invocation_quota_request_digest
    assert record.profile_digest == work.invocation_quota_profile_digest == profile.profile_digest
    assert record.units == 1
    assert state.spent["run"] == Decimal("0.2")

    reopened_middleware, reopened_binding, reopened_state = _producer_owner(owner_path, cap="10")
    reopened_observer = _observer(reopened_middleware, reopened_binding, reopened_state, profile)
    retry = JointSimulationHorizonController(producer_budget_observer=reopened_observer).run(
        request
    )
    assert retry.diagnostics["physical_work_interruption"] == "n5_invocation_quota_exhausted"
    assert retry.physical_work_observations == ()
    assert calls == [request.seed]
    assert (
        FileBudgetLedger(owner_path / "ledger.json").snapshot().invocation_reservations
        == snapshot.invocation_reservations
    )


@pytest.mark.parametrize(
    "artifact_denial_first", [True, False], ids=["producer-ownership", "finish-permission"]
)
def test_dual_fault_keeps_actual_access_denial_and_consumed_quota(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, artifact_denial_first: bool
) -> None:
    """Neither producer nor finish failures may mask the actual access denial."""
    from polisyos.core.artifacts.ownership import ArtifactOwnershipError

    owner_path = tmp_path / "owner"
    middleware, binding, state, profile = _quota_owner(owner_path, total=1, protected=0)
    observer = _observer(middleware, binding, state, profile)
    request = _one_call_request()
    calls = _record_native_calls(monkeypatch)
    producer_error = (
        ArtifactOwnershipError("controlled producer ownership denial")
        if artifact_denial_first
        else ValueError("controlled ordinary producer failure")
    )
    finish_error = (
        OSError("controlled ordinary finish failure")
        if artifact_denial_first
        else PermissionError("controlled finish permission denial")
    )
    actual_denial = producer_error if artifact_denial_first else finish_error
    finish_attempts: list[str] = []

    def fail_selected(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        del state
        calls.append(int(params["__seed__"]))
        raise producer_error

    def fail_finish(
        self: FileBudgetLedger,
        operation_id: str,
        request_digest: str,
        *,
        profile: BudgetLedgerInvocationProfile,
        outcome: Literal["completed", "failed", "unknown"],
    ) -> None:
        del self, operation_id, request_digest, profile
        finish_attempts.append(outcome)
        raise finish_error

    with monkeypatch.context() as failure:
        failure.setattr(NCMEngineMethod, "pure_step", staticmethod(fail_selected))
        failure.setattr(FileBudgetLedger, "finish_invocation", fail_finish)
        with pytest.raises(PermissionError) as caught:
            JointSimulationHorizonController(producer_budget_observer=observer).run(request)
    assert caught.value is actual_denial
    assert calls == [request.seed]
    assert finish_attempts == ["failed"]
    snapshot = FileBudgetLedger(owner_path / "ledger.json").snapshot()
    assert len(snapshot.invocation_reservations) == 1
    record = next(iter(snapshot.invocation_reservations.values()))
    assert record.run_id == binding.run_id
    assert record.profile_digest == profile.profile_digest
    assert record.purpose == "standard" and record.units == 1
    assert record.status == "reserved"

    reopened_middleware, reopened_binding, reopened_state = _producer_owner(owner_path, cap="10")
    reopened_observer = _observer(reopened_middleware, reopened_binding, reopened_state, profile)
    retry = JointSimulationHorizonController(producer_budget_observer=reopened_observer).run(
        request
    )
    assert retry.diagnostics["physical_work_interruption"] == "n5_invocation_quota_exhausted"
    assert retry.physical_work_observations == ()
    assert calls == [request.seed]
    assert (
        FileBudgetLedger(owner_path / "ledger.json").snapshot().invocation_reservations
        == snapshot.invocation_reservations
    )


def test_quota_reservation_source_failure_refuses_before_native_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real USD admission cannot stand in for an unavailable invocation admission."""
    owner_path = tmp_path / "owner"
    middleware, binding, state, profile = _quota_owner(owner_path, total=1, protected=0)
    observer = _observer(middleware, binding, state, profile)
    calls = _record_native_calls(monkeypatch)

    def cannot_reserve(self: FileBudgetLedger, *args: Any, **kwargs: Any) -> None:
        del self, args, kwargs
        raise OSError("controlled invocation journal unavailable")

    with monkeypatch.context() as failure:
        failure.setattr(FileBudgetLedger, "reserve_invocation", cannot_reserve)
        result = JointSimulationHorizonController(producer_budget_observer=observer).run(
            _one_call_request()
        )
    assert (
        result.diagnostics["physical_work_interruption"]
        == "n5_invocation_quota_source_not_established"
    )
    assert result.physical_work_observations == ()
    assert result.trajectories == ()
    assert calls == []
    assert FileBudgetLedger(owner_path / "ledger.json").snapshot().invocation_reservations == {}
    fresh = _fresh_result(tmp_path / "refused-cas", result, None)
    assert (
        fresh.diagnostics["physical_work_interruption"]
        == result.diagnostics["physical_work_interruption"]
    )


def test_zero_unit_profile_refuses_before_any_native_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A configured zero allocation is a refusal even while the USD budget has capacity."""
    owner_path = tmp_path / "owner"
    middleware, binding, state, profile = _quota_owner(owner_path, total=0, protected=0)
    observer = _observer(middleware, binding, state, profile)
    calls = _record_native_calls(monkeypatch)

    result = JointSimulationHorizonController(producer_budget_observer=observer).run(
        _one_call_request()
    )

    assert result.diagnostics["physical_work_interruption"] == "n5_invocation_quota_exhausted"
    assert result.physical_work_observations == ()
    assert result.trajectories == ()
    assert calls == []
    snapshot = FileBudgetLedger(owner_path / "ledger.json").snapshot()
    assert snapshot.invocation_profiles[binding.run_id] == profile
    assert snapshot.invocation_reservations == {}


@pytest.mark.parametrize("created_before_configuration", [False, True], ids=["fresh", "stale"])
def test_omitted_profile_cannot_bypass_a_durably_exhausted_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, created_before_configuration: bool
) -> None:
    """Omitting a constructor argument cannot remove an existing run allocation."""
    owner_path = tmp_path / "owner"
    middleware, binding, state, profile = _quota_owner(owner_path, total=1, protected=0)
    omitted = _observer(middleware, binding, state, None) if created_before_configuration else None
    configured = _observer(middleware, binding, state, profile)
    request = _one_call_request()
    calls = _record_native_calls(monkeypatch)
    result = JointSimulationHorizonController(producer_budget_observer=configured).run(request)
    assert len(result.physical_work_observations) == 1
    assert calls == [request.seed]

    try:
        if omitted is None:
            fresh_middleware, fresh_binding, fresh_state = _producer_owner(owner_path, cap="10")
            omitted = _observer(fresh_middleware, fresh_binding, fresh_state, None)
        refused = JointSimulationHorizonController(producer_budget_observer=omitted).run(request)
    except ProducerBudgetSourceError:
        # The owner may refuse omission at construction; a later refusal must
        # likewise occur before any producer dispatch or reservation.
        pass
    else:
        assert refused.trajectories == ()
        assert refused.physical_work_observations == ()
        assert _joint_simulation_port_outcome(refused, request=request)[0] == "simulation_blocked"
    assert calls == [request.seed]
    snapshot = FileBudgetLedger(owner_path / "ledger.json").snapshot()
    assert snapshot.invocation_profiles[binding.run_id] == profile
    assert len(snapshot.invocation_reservations) == 1


def test_genuinely_unconfigured_native_run_discloses_no_invocation_guarantee(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Existing unconfigured callers retain useful results without a protected-capacity claim."""
    owner_path = tmp_path / "owner"
    middleware, binding, state = _producer_owner(owner_path, cap="10")
    _real_provider_charge(middleware, binding, 0.2, "before-unconfigured-native-work")
    observer = _observer(middleware, binding, state, None)
    calls = _record_native_calls(monkeypatch)
    request = _one_call_request()

    result = JointSimulationHorizonController(producer_budget_observer=observer).run(request)

    assert observer.invocation_guarantee == "no_guarantee"
    assert result.diagnostics["invocation_quota_capacity"] == "no_guarantee"
    assert calls == [request.seed]
    assert len(result.physical_work_observations) == 1
    assert result.physical_work_observations[0].invocation_quota_operation_id is None
    snapshot = FileBudgetLedger(owner_path / "ledger.json").snapshot()
    assert snapshot.invocation_profiles == {}
    assert snapshot.invocation_reservations == {}
    assert _fresh_result(tmp_path / "unconfigured-cas", result, request).trajectories


def test_model_copy_empty_atoms_refuse_before_native_call_or_quota_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bypassing DTO construction cannot turn the comparator into an admitted empty design."""
    owner_path = tmp_path / "owner"
    middleware, binding, state, profile = _quota_owner(owner_path, total=2, protected=1)
    observer = _observer(middleware, binding, state, profile)
    calls = _record_native_calls(monkeypatch)
    invalid = _native_request().model_copy(
        update={
            "intervention_atoms": (),
            "comparator_profile": NCMConditionalComparatorProfile(
                outcome_units={"firm_survival": "synthetic_score"}
            ),
        }
    )

    with pytest.raises(ValueError, match="intervention_atoms_missing"):
        JointSimulationHorizonController(producer_budget_observer=observer).run(invalid)
    assert calls == []
    assert observer.last_checked is None
    assert FileBudgetLedger(owner_path / "ledger.json").snapshot().invocation_reservations == {}
