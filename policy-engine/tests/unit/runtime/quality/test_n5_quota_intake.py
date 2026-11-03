"""N5 invocation quota intake through the owner-selected generic input path."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import ArtifactRef, load_core_json_artifact
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.generation_cycle import (
    JointSimulationPort,
    load_joint_simulation_result,
)
from polisyos.runtime.quality.generic_simulation_admission import (
    _PROFILE_CANON,
    GenericCycleN5RequestProfileV3,
    GenericCycleSimulationAdmissionOwner,
    GenericCycleSimulationContextHandoffV1,
    GenericCycleSimulationN5InputV1,
)
from polisyos.scientist.orchestration.engine import (
    BudgetInvocationQuotaPolicy,
    BudgetLedgerInvocationProfile,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerProducerRunBinding,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.producer_budget import ProducerBudgetObserver
from tests.unit.runtime.quality.test_c49_native_stopping_budget import _real_provider_charge
from tests.unit.runtime.quality.test_cycle_substrate import (
    _authenticated_tenant_scope,
    _TestCurrentJobExecutionOwner,
)
from tests.unit.runtime.quality.test_generic_n5_v3_binding import (
    _assert_generic_facade_execution,
    _prepare_generic_facade_owner_case,
)
from tests.unit.runtime.quality.test_n5_invocation_quota import _record_native_calls


def _owner_selected_v3_case(
    base: dict[str, Any],
    *,
    policy: BudgetInvocationQuotaPolicy | None,
    purpose: str | None,
    source_run_id: str,
) -> dict[str, Any]:
    """Persist a fresh V3 N5 input from the real N4 member and selected profile."""
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextArtifactOwner
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    prepared = base["prepared"]
    store = base["store"]
    problem = base["problem"]
    candidate = base["candidate"]
    original_profile = prepared.root_profile
    if type(original_profile.n5) is not GenericCycleN5RequestProfileV3:
        raise AssertionError("n5_quota_fixture_requires_source_materialized_v3_profile")
    n5_fields = original_profile.n5.model_dump(mode="python")
    n5_fields.update(invocation_quota_policy=policy, invocation_purpose=purpose)
    n5 = GenericCycleN5RequestProfileV3.model_validate(n5_fields)
    profile_fields = original_profile.model_dump(mode="python", exclude={"content_hash"})
    profile_fields["n5"] = n5
    profile_draft = type(original_profile).model_construct(
        **profile_fields,
        content_hash="sha256:" + "0" * 64,
    )
    profile = type(original_profile).model_validate(
        {
            **profile_fields,
            "content_hash": gy_content_hash(
                profile_draft.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    owner = GenericCycleSimulationAdmissionOwner(profiles=(profile,), store=store)
    context = owner.context_for_profile(profile, problem)
    job_id = base["handoff"].job_id
    run_id = base["handoff"].run_id
    tenant_id = base["tenant_id"]
    cell_id = base["cell_id"]
    with _authenticated_tenant_scope(tenant_id=tenant_id, cell_id=cell_id):
        context_owner = CycleSubstrateContextArtifactOwner(
            store=store,
            control_store=_TestCurrentJobExecutionOwner(job_id, run_id),
        )
        context_ref = context_owner.persist_for_current_job(context, problem=problem)
        profile_ref = store.put_json(
            profile.model_dump(mode="json"),
            owner._profile_write_options(
                profile=profile,
                job_id=job_id,
                run_id=run_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
            ),
            canon_spec=_PROFILE_CANON,
            return_selected_profile=True,
        )
        profile_ref = ArtifactRef.model_validate(profile_ref.model_dump(mode="python"))
        owner.resolve_profile_historical(
            profile_ref,
            expected_profile=profile,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        handoff = GenericCycleSimulationContextHandoffV1(
            context=context,
            context_job_ref=context_ref,
            profile=profile,
            profile_ref=profile_ref,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        organ = replace(base["organ"], cycle_substrate_context=context)
        repository = GenerationSourceRepository(store)
        source_ref = repository.persist_ref(
            run_id=source_run_id,
            expected_run_id=run_id,
            cycle_index=0,
            problem=problem,
            organ=organ,
            execution_scope="contract_testing",
            job_id=job_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            context_job_ref=context_ref,
            profile_ref=profile_ref,
        )
        input_ref = owner.persist_n5_input(
            handoff=handoff,
            source_ref=source_ref,
            source_run_id=source_run_id,
            child_profile_family_ref=None,
            child_profile_set_ref=None,
            problem=problem,
            cycle_index=0,
            candidate_id=candidate.candidate_id,
            candidate_atom_hash=candidate.atom.content_hash,
            outcome_variable=problem.outcome_of_interest.target_variable,
        )
        input_record = GenericCycleSimulationN5InputV1.model_validate(
            load_core_json_artifact(store, input_ref)
        )
    return {
        **base,
        "owner": owner,
        "context": context,
        "handoff": handoff,
        "organ": organ,
        "source_ref": source_ref,
        "input_ref": input_ref,
        "input_record": input_record,
    }


def _quota_observer(
    path: Path, case: dict[str, Any]
) -> tuple[
    ProducerBudgetObserver,
    BudgetMiddleware,
    FileBudgetLedger,
    BudgetLedgerProducerRunBinding,
    BudgetState,
]:
    """Create the real observer in the selected generic run scope."""
    from tests.unit.runtime.quality.test_n5_invocation_quota import _observer

    ledger = FileBudgetLedger(path / "ledger.json")
    middleware = BudgetMiddleware(BudgetState(), ledger=ledger)
    handoff = case["handoff"]
    binding = BudgetLedgerProducerRunBinding(
        run_id=handoff.run_id,
        tenant_id=handoff.tenant_id,
        cell_id=handoff.cell_id,
        profile_id=handoff.profile.profile_id,
        control_job_id=handoff.job_id,
    )
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    _real_provider_charge(middleware, binding, 0.2, "settled-before-selected-n5-quota")
    return _observer(middleware, binding, state, None), middleware, ledger, binding, state


def _call_port(case: dict[str, Any], *, observer: ProducerBudgetObserver | None) -> Any:
    """Invoke the actual generic owner-selected input through JointSimulationPort."""
    port = JointSimulationPort(
        repo_root=case["prepared"].source_root,
        artifact_store=case["store"],
        cycle_substrate_context=case["context"],
        generic_cycle_simulation_admission_owner=case["owner"],
        generic_cycle_simulation_handoff=case["handoff"],
        producer_budget_observer=observer,
    )
    return port(
        candidate=case["candidate"],
        problem=case["problem"],
        cycle_index=0,
        generic_cycle_simulation_input=case["input_record"],
        generic_cycle_simulation_input_ref=case["input_ref"],
        generic_cycle_simulation_currentness_resolver=lambda: True,
    )


def _result(case: dict[str, Any], observation: Any) -> Any:
    """Resolve the actual persisted N5 result against its bound request."""
    assert observation.simulation_result_ref is not None
    binding = observation.generic_n5_request_binding
    assert binding is not None
    return load_joint_simulation_result(
        observation.simulation_result_ref,
        store=case["store"],
        expected_request=binding.request,
    )


@pytest.mark.asyncio
async def test_joint_port_enforces_selected_generic_invocation_quota_and_no_guarantee_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finite owner policy blocks absent admission, while real calls journal under one observer."""
    from tests._helpers import generic_n4_served_replay

    prepare = generic_n4_served_replay.prepare_generic_n4_served_replay

    async def prepare_materialized(**kwargs: Any) -> Any:
        kwargs.update(
            materialize_source_parameters=True,
            synthetic_settled_provider=True,
            recording_mode="original_second_capture",
            child_count=2,
        )
        return await prepare(**kwargs)

    monkeypatch.setattr(
        generic_n4_served_replay,
        "prepare_generic_n4_served_replay",
        prepare_materialized,
    )
    base = await _prepare_generic_facade_owner_case(tmp_path, monkeypatch)
    calls = _record_native_calls(monkeypatch)
    policy = BudgetInvocationQuotaPolicy(
        allocation_id="generic-owner-selected-n5-quota",
        total_units=100,
        protected_units=20,
    )

    finite_standard = _owner_selected_v3_case(
        base,
        policy=policy,
        purpose="standard",
        source_run_id="source-n5-quota-standard",
    )
    no_policy = _owner_selected_v3_case(
        base,
        policy=None,
        purpose=None,
        source_run_id="source-n5-quota-unconfigured",
    )
    with _authenticated_tenant_scope(tenant_id=base["tenant_id"], cell_id=base["cell_id"]):
        refused = _call_port(finite_standard, observer=None)
        refused_execution = _assert_generic_facade_execution(finite_standard, refused)
        assert refused.status == refused_execution.status == "simulation_blocked"
        assert "n5_invocation_quota_owner_not_established" in refused.authority_blockers
        assert refused_execution.limitation_code == "n5_invocation_quota_owner_not_established"
        assert refused.simulation_result_ref is None
        assert calls == []

        (
            unconfigured_observer,
            _,
            no_policy_ledger,
            _,
            no_policy_state,
        ) = _quota_observer(tmp_path / "no-policy-ledger", no_policy)
        no_policy_usd_before = no_policy_ledger.snapshot().state
        unconfigured = _call_port(no_policy, observer=unconfigured_observer)
        _assert_generic_facade_execution(no_policy, unconfigured)
        no_policy_result = _result(no_policy, unconfigured)
        assert unconfigured.status == "joint_simulated"
        assert unconfigured_observer.invocation_guarantee == "no_guarantee"
        assert no_policy_result.diagnostics["invocation_quota_capacity"] == "no_guarantee"
        assert no_policy_result.physical_work_observations
        assert all(
            item.invocation_quota_operation_id is None
            for item in no_policy_result.physical_work_observations
        )
        no_policy_snapshot = FileBudgetLedger(
            tmp_path / "no-policy-ledger" / "ledger.json"
        ).snapshot()
        assert no_policy_snapshot.invocation_profiles == {}
        assert no_policy_snapshot.invocation_reservations == {}
        assert no_policy_snapshot.state == no_policy_usd_before
        assert no_policy_state.spent["run"] == Decimal("0.2")
        assert calls

        quota_observer, _, ledger, producer_binding, budget_state = _quota_observer(
            tmp_path / "configured-ledger", finite_standard
        )
        usd_before = ledger.snapshot().state
        standard = _call_port(finite_standard, observer=quota_observer)
        _assert_generic_facade_execution(finite_standard, standard)
        standard_result = _result(finite_standard, standard)
        assert standard.status == "joint_simulated"
        assert standard_result.physical_work_observations
        assert all(
            item.invocation_quota_purpose == "standard"
            and item.invocation_quota_status == "completed"
            for item in standard_result.physical_work_observations
        )

        diagnostic_case = _owner_selected_v3_case(
            base,
            policy=policy,
            purpose="diagnostic",
            source_run_id="source-n5-quota-diagnostic",
        )
        diagnostic = _call_port(diagnostic_case, observer=quota_observer)
        _assert_generic_facade_execution(diagnostic_case, diagnostic)
        diagnostic_result = _result(diagnostic_case, diagnostic)
        assert diagnostic.status == "joint_simulated"
        assert diagnostic_result.physical_work_observations
        assert all(
            item.invocation_quota_purpose == "diagnostic"
            and item.invocation_quota_status == "completed"
            for item in diagnostic_result.physical_work_observations
        )

    assert calls
    ledger = FileBudgetLedger(tmp_path / "configured-ledger" / "ledger.json")
    snapshot = ledger.snapshot()
    quota_profile = BudgetLedgerInvocationProfile.from_policy(producer_binding, policy)
    assert snapshot.invocation_profiles[producer_binding.run_id] == quota_profile
    work = standard_result.physical_work_observations + diagnostic_result.physical_work_observations
    records = snapshot.invocation_reservations
    assert set(records) == {item.invocation_quota_operation_id for item in work}
    assert Counter(record.purpose for record in records.values()) == {
        "standard": len(standard_result.physical_work_observations),
        "diagnostic": len(diagnostic_result.physical_work_observations),
    }
    for item in work:
        record = records[item.invocation_quota_operation_id]
        assert record.request_digest == item.invocation_quota_request_digest
        assert record.profile_digest == item.invocation_quota_profile_digest
        assert record.profile_digest == quota_profile.profile_digest
        assert record.run_id == producer_binding.run_id
        assert record.units == item.work_units == 1
        assert record.status == item.invocation_quota_status == "completed"
        assert record.purpose == item.invocation_quota_purpose
        assert item.usd_cost is None and item.usd_cost_status == "not_established"
    assert snapshot.state == usd_before
    assert budget_state.spent["run"] == Decimal("0.2")
    assert quota_profile.price_origin == "unknown"
