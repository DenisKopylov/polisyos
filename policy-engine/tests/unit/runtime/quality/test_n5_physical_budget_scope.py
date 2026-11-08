"""Exercise signed NL scope and real per-invocation N5 quota accounting."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.control import NaturalLanguageRunRequest
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.quality.candidate_simulation import CandidateScenarioN5Config
from polisyos.runtime.quality.generation_cycle import _bind_scoped_n5_invocation_policy
from polisyos.runtime.quality.generic_simulation_admission import (
    GenericCycleN5ProgramGraphRequestProfileV4,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    HorizonSpec,
    JointSimulationHorizonController,
)
from polisyos.scientist.orchestration.engine import BudgetInvocationQuotaPolicy
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerInvocationProfile,
    BudgetLedgerProducerRunBinding,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.producer_budget import (
    ProducerBudgetObserver,
    ProducerBudgetSourceError,
)
from tests._helpers.runtime_http import _build_control_service, _valid_intake_for_mode
from tests.unit.runtime.http.control_service_test_support import bound_nl_authorization_proof
from tests.unit.runtime.http.test_control_service_di import _fixture_claims
from tests.unit.runtime.quality.test_n5_invocation_quota import (
    _one_call_request,
    _record_native_calls,
)
from tests.unit.scientist.orchestration.engine.test_producer_budget_c49 import _settle


def _profile(policy: BudgetInvocationQuotaPolicy | None) -> CandidateScenarioN5Config:
    fields = (
        {"invocation_quota_policy": policy, "invocation_purpose": "standard"}
        if policy is not None
        else {}
    )
    return CandidateScenarioN5Config(
        budget_ref="budget://test/n5-physical-scope",
        horizon=HorizonSpec(start=0, end=0, step=1),
        replications=1,
        **fields,
    )


async def _issued_owner(tmp_path: Path, *, mode: str | None):
    """Launch a real signed job, install its durable ledger, and lease it."""
    store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-fixture", "cell-fixture")
    with tenant_scope(None, tenant_id="tenant-fixture", cell_id="cell-fixture"):
        service = _build_control_service(tmp_path / "control", artifact_store=store)
    middleware = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(tmp_path / "ledger.json"))
    service.bind_llm_producer_settlement_store(middleware)
    request_fields = {
        "request": "Evaluate a bounded candidate simulation.",
        "llm_model": "simulated-qwen",
        "context": {
            "evaluation_safety_attempt": _valid_intake_for_mode("simulate_only").model_dump(
                mode="json"
            )
        },
        "run_budget_usd": 5.0,
        "max_iterations": 1,
    }
    if mode != "omitted":
        request_fields["run_budget_scope"] = mode
    request = NaturalLanguageRunRequest.model_validate(request_fields)
    claims = _fixture_claims()
    launch = await service.launch_nl_run(
        request,
        principal=RuntimePrincipal.from_user_claims(claims),
        authorization_proof=bound_nl_authorization_proof(claims, request),
    )
    job = service._control_store.lease_next_job(worker_id="n5-scope-test", lease_seconds=600)
    assert job is not None and job.job_id == launch.job_id
    binding = BudgetLedgerProducerRunBinding(
        run_id=str(job.run_id),
        tenant_id="tenant-fixture",
        cell_id="cell-fixture",
        profile_id=job.effective_execution_profile,
        control_job_id=job.job_id,
    )
    _settle(middleware, binding, "signed-scope-test-provider", "0.2")
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))})
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
        invocation_selection_pending=True,
    )
    return service, middleware, observer, job


def _with_scope(observer: ProducerBudgetObserver, scope: object) -> ProducerBudgetObserver:
    """Keep the real store/state while attaching the Control-issued scope."""
    return ProducerBudgetObserver(
        settlement_store=observer._store,
        producer_run_binding=observer._binding,
        budget_state=observer._state,
        invocation_selection_pending=True,
        invocation_guard_binding=scope,
    )


@pytest.mark.asyncio
async def test_program_graph_profile_binds_quota_under_real_signed_scope(tmp_path: Path) -> None:
    service, _middleware, observer, job = await _issued_owner(
        tmp_path, mode="metered_paid_producers_and_bounded_candidate"
    )
    policy = BudgetInvocationQuotaPolicy(
        allocation_id="graph-scope-test", total_units=3, protected_units=1
    )
    profile = GenericCycleN5ProgramGraphRequestProfileV4(
        budget_ref="budget://test/program-graph-scope",
        horizon=HorizonSpec(start=0, end=0, step=1),
        baseline_state={"outcome": 0.0},
        compile_report_ref=ArtifactRef(
            artifact_id="sha256:" + "a" * 64,
            kind="compiler.compile_report",
            media_type="application/json",
            manifest_profile_sha256="sha256:" + "b" * 64,
        ),
        invocation_quota_policy=policy,
    )
    try:
        with service._control_store.job_execution_fence(
            job_id=job.job_id, worker_id=job.lease_owner, attempt=job.attempt
        ):
            admission = service._control_store.current_execution_job_admission()
            with service._install_execution_scope(admission.scope):
                scope = service._current_verified_nl_budget_scope()
                observer = _with_scope(observer, scope)
                with pytest.raises(ProducerBudgetSourceError, match="scope_binding_mismatch"):
                    _bind_scoped_n5_invocation_policy(
                        observer, n5_profile=profile, physical_n5_budget_scope=None
                    )
                with _bind_scoped_n5_invocation_policy(
                    observer, n5_profile=profile, physical_n5_budget_scope=scope
                ):
                    assert observer.invocation_quota_profile == (
                        BudgetLedgerInvocationProfile.from_policy(observer._binding, policy)
                    )
    finally:
        service.close()


@pytest.mark.asyncio
async def test_signed_limited_scope_requires_selected_quota_and_real_owner_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Actual NCM work is charged once to the same run-bound finite quota."""
    service, middleware, observer, job = await _issued_owner(
        tmp_path, mode="metered_paid_producers_and_bounded_candidate"
    )
    policy = BudgetInvocationQuotaPolicy(
        allocation_id="scope-test", total_units=2, protected_units=1
    )
    try:
        with service._control_store.job_execution_fence(
            job_id=job.job_id, worker_id=job.lease_owner, attempt=job.attempt
        ):
            admission = service._control_store.current_execution_job_admission()
            with service._install_execution_scope(admission.scope):
                scope = service._current_verified_nl_budget_scope()
                observer = _with_scope(observer, scope)
                before = middleware._ledger.snapshot()
                with pytest.raises(ProducerBudgetSourceError, match="scope_binding_mismatch"):
                    _bind_scoped_n5_invocation_policy(
                        observer, n5_profile=_profile(policy), physical_n5_budget_scope=None
                    )
                damaged = _with_scope(observer, scope)
                damaged._invocation_guard_binding = None
                with pytest.raises(ProducerBudgetSourceError, match="budget_scope_not_established"):
                    _bind_scoped_n5_invocation_policy(
                        damaged, n5_profile=_profile(policy), physical_n5_budget_scope=scope
                    )
                with pytest.raises(
                    ProducerBudgetSourceError, match="selected_profile_not_established"
                ):
                    _bind_scoped_n5_invocation_policy(
                        observer, n5_profile=None, physical_n5_budget_scope=scope
                    )
                with pytest.raises(
                    ProducerBudgetSourceError, match="quota_profile_not_established"
                ):
                    _bind_scoped_n5_invocation_policy(
                        observer, n5_profile=_profile(None), physical_n5_budget_scope=scope
                    )
                forged = scope.model_copy(update={"run_budget_scope": "hard_total_usd"})
                with pytest.raises(ProducerBudgetSourceError, match="scope_binding_mismatch"):
                    _bind_scoped_n5_invocation_policy(
                        observer, n5_profile=_profile(policy), physical_n5_budget_scope=forged
                    )
                foreign_store = BudgetMiddleware(
                    BudgetState(), ledger=FileBudgetLedger(tmp_path / "foreign-ledger.json")
                )
                foreign = ProducerBudgetObserver(
                    settlement_store=foreign_store,
                    producer_run_binding=observer._binding,
                    budget_state=BudgetState(
                        limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))}
                    ),
                    invocation_selection_pending=True,
                    invocation_guard_binding=scope,
                )
                with pytest.raises(ProducerBudgetSourceError, match="settlement_owner_mismatch"):
                    _bind_scoped_n5_invocation_policy(
                        foreign, n5_profile=_profile(policy), physical_n5_budget_scope=scope
                    )
                wrong_cap = ProducerBudgetObserver(
                    settlement_store=middleware,
                    producer_run_binding=observer._binding,
                    budget_state=BudgetState(
                        limits={"run": BudgetLimit(key="run", max_usd=Decimal("6"))}
                    ),
                    invocation_selection_pending=True,
                    invocation_guard_binding=scope,
                )
                with pytest.raises(ProducerBudgetSourceError, match="budget_cap_mismatch"):
                    _bind_scoped_n5_invocation_policy(
                        wrong_cap, n5_profile=_profile(policy), physical_n5_budget_scope=scope
                    )
                assert middleware._ledger.snapshot() == before

                calls = _record_native_calls(monkeypatch)
                with _bind_scoped_n5_invocation_policy(
                    observer, n5_profile=_profile(policy), physical_n5_budget_scope=scope
                ):
                    result = JointSimulationHorizonController(
                        producer_budget_observer=observer, physical_n5_budget_scope=scope
                    ).run(_one_call_request())
                assert len(calls) == len(result.physical_work_observations) == 1
                work = result.physical_work_observations[0]
                assert work.invocation_quota_purpose == "standard"
                assert work.invocation_quota_status == "completed"
                ledger = middleware._ledger.snapshot()
                assert ledger.invocation_reservations[
                    work.invocation_quota_operation_id
                ].status == ("completed")
        with pytest.raises(ProducerBudgetSourceError, match="budget_scope_not_established"):
            _bind_scoped_n5_invocation_policy(
                observer, n5_profile=_profile(policy), physical_n5_budget_scope=scope
            )
    finally:
        service.close()


@pytest.mark.asyncio
async def test_signed_legacy_omission_keeps_existing_unprofiled_native_behavior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An omitted scope does not invent a finite physical-work guarantee."""
    service, _, observer, job = await _issued_owner(tmp_path, mode="omitted")
    try:
        with service._control_store.job_execution_fence(
            job_id=job.job_id, worker_id=job.lease_owner, attempt=job.attempt
        ):
            admission = service._control_store.current_execution_job_admission()
            with service._install_execution_scope(admission.scope):
                scope = service._current_verified_nl_budget_scope()
                assert scope.run_budget_scope_present is False
                observer = _with_scope(observer, scope)
                calls = _record_native_calls(monkeypatch)
                with _bind_scoped_n5_invocation_policy(
                    observer, n5_profile=_profile(None), physical_n5_budget_scope=scope
                ):
                    result = JointSimulationHorizonController(
                        producer_budget_observer=observer, physical_n5_budget_scope=scope
                    ).run(_one_call_request())
                assert len(calls) == len(result.physical_work_observations) == 1
                assert result.physical_work_observations[0].invocation_quota_status is None
                assert "physical_work_interruption" not in result.diagnostics
    finally:
        service.close()


@pytest.mark.asyncio
async def test_lost_worker_after_real_reservation_prevents_physical_n5(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A terminal job cannot spend a reservation obtained under its former lease."""
    service, middleware, observer, job = await _issued_owner(
        tmp_path, mode="metered_paid_producers_and_bounded_candidate"
    )
    policy = BudgetInvocationQuotaPolicy(
        allocation_id="scope-test", total_units=2, protected_units=1
    )
    try:
        with service._control_store.job_execution_fence(
            job_id=job.job_id, worker_id=job.lease_owner, attempt=job.attempt
        ):
            admission = service._control_store.current_execution_job_admission()
            with service._install_execution_scope(admission.scope):
                scope = service._current_verified_nl_budget_scope()
                observer = _with_scope(observer, scope)
                original = ProducerBudgetObserver.reserve_invocation

                def reserve_then_fail_job(self, operation_id, request_digest):
                    reservation = original(self, operation_id, request_digest)
                    service._control_store.fail_job(
                        job_id=job.job_id,
                        error_message="controlled lease-loss test",
                        expected_lease_owner=job.lease_owner,
                        expected_attempt=job.attempt,
                    )
                    return reservation

                monkeypatch.setattr(
                    ProducerBudgetObserver, "reserve_invocation", reserve_then_fail_job
                )
                calls = _record_native_calls(monkeypatch)
                with _bind_scoped_n5_invocation_policy(
                    observer, n5_profile=_profile(policy), physical_n5_budget_scope=scope
                ):
                    result = JointSimulationHorizonController(
                        producer_budget_observer=observer, physical_n5_budget_scope=scope
                    ).run(_one_call_request())
                assert calls == [] and result.physical_work_observations == ()
                assert result.diagnostics["physical_work_interruption"] == (
                    "n5_physical_budget_scope_not_established"
                )
                reservations = tuple(middleware._ledger.snapshot().invocation_reservations.values())
                assert len(reservations) == 1 and reservations[0].status == "failed"
    finally:
        service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_kind", ["denied", "unavailable"])
async def test_lost_worker_reservation_cleanup_preserves_access_denial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_kind: str
) -> None:
    """A failed cleanup stays pending; only a real ownership denial propagates."""
    from polisyos.core.artifacts import ArtifactOwnershipError, ArtifactReadOnlyUnavailableError

    service, middleware, observer, job = await _issued_owner(
        tmp_path, mode="metered_paid_producers_and_bounded_candidate"
    )
    policy = BudgetInvocationQuotaPolicy(
        allocation_id="cleanup-test", total_units=2, protected_units=1
    )
    denial = (
        ArtifactOwnershipError("controlled quota owner denial")
        if failure_kind == "denied"
        else ArtifactReadOnlyUnavailableError("controlled unavailable quota owner")
    )
    try:
        with service._control_store.job_execution_fence(
            job_id=job.job_id, worker_id=job.lease_owner, attempt=job.attempt
        ):
            admission = service._control_store.current_execution_job_admission()
            with service._install_execution_scope(admission.scope):
                scope = service._current_verified_nl_budget_scope()
                observer = _with_scope(observer, scope)
                reserve = ProducerBudgetObserver.reserve_invocation

                def reserve_then_fail_job(self, operation_id, request_digest):
                    reservation = reserve(self, operation_id, request_digest)
                    service._control_store.fail_job(
                        job_id=job.job_id,
                        error_message="controlled lease-loss test",
                        expected_lease_owner=job.lease_owner,
                        expected_attempt=job.attempt,
                    )
                    return reservation

                def deny_finish(self, operation_id, request_digest, status):
                    raise ProducerBudgetSourceError("controlled cleanup failure") from denial

                monkeypatch.setattr(
                    ProducerBudgetObserver, "reserve_invocation", reserve_then_fail_job
                )
                monkeypatch.setattr(ProducerBudgetObserver, "finish_invocation", deny_finish)
                calls = _record_native_calls(monkeypatch)
                with _bind_scoped_n5_invocation_policy(
                    observer, n5_profile=_profile(policy), physical_n5_budget_scope=scope
                ):
                    controller = JointSimulationHorizonController(
                        producer_budget_observer=observer, physical_n5_budget_scope=scope
                    )
                    if failure_kind == "denied":
                        with pytest.raises(ArtifactOwnershipError) as captured:
                            controller.run(_one_call_request())
                        assert captured.value is denial
                    else:
                        result = controller.run(_one_call_request())
                        assert result.diagnostics["physical_work_interruption"] == (
                            "n5_physical_budget_scope_not_established"
                        )
                        assert result.physical_work_observations == ()
                assert calls == []
                reservations = tuple(middleware._ledger.snapshot().invocation_reservations.values())
                assert len(reservations) == 1 and reservations[0].status == "reserved"
    finally:
        service.close()


@pytest.mark.asyncio
async def test_lost_worker_during_native_n5_preserves_work_but_blocks_both_consumers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A completed physical call is auditable but cannot advance on a stale lease."""
    from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
    from polisyos.runtime.quality.generation_cycle import _joint_simulation_port_outcome
    from polisyos.runtime.quality.recursive_generation_cycle import (
        _joint_simulation_is_unsupported,
    )

    service, middleware, observer, job = await _issued_owner(
        tmp_path, mode="metered_paid_producers_and_bounded_candidate"
    )
    policy = BudgetInvocationQuotaPolicy(
        allocation_id="scope-test", total_units=2, protected_units=1
    )
    try:
        with service._control_store.job_execution_fence(
            job_id=job.job_id, worker_id=job.lease_owner, attempt=job.attempt
        ):
            admission = service._control_store.current_execution_job_admission()
            with service._install_execution_scope(admission.scope):
                scope = service._current_verified_nl_budget_scope()
                observer = _with_scope(observer, scope)
                original = NCMEngineMethod.pure_step
                calls = []

                def finish_then_lose_lease(state, params):
                    value = original(state, params)
                    calls.append(params["__seed__"])
                    service._control_store.fail_job(
                        job_id=job.job_id,
                        error_message="controlled loss during N5",
                        expected_lease_owner=job.lease_owner,
                        expected_attempt=job.attempt,
                    )
                    return value

                monkeypatch.setattr(
                    NCMEngineMethod, "pure_step", staticmethod(finish_then_lose_lease)
                )
                with _bind_scoped_n5_invocation_policy(
                    observer, n5_profile=_profile(policy), physical_n5_budget_scope=scope
                ):
                    result = JointSimulationHorizonController(
                        producer_budget_observer=observer, physical_n5_budget_scope=scope
                    ).run(_one_call_request())
                assert len(calls) == 1
                assert result.diagnostics["physical_work_interruption"] == (
                    "n5_physical_budget_scope_lost_after_work"
                )
                (work,) = result.physical_work_observations
                assert work.status == work.invocation_quota_status == "completed"
                assert (
                    middleware._ledger.snapshot()
                    .invocation_reservations[work.invocation_quota_operation_id]
                    .status
                    == "completed"
                )
                assert _joint_simulation_port_outcome(result)[0] == "simulation_blocked"
                assert _joint_simulation_is_unsupported(result)
    finally:
        service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["hard_total_usd", None])
async def test_signed_hard_or_null_scope_refuses_before_quota_or_physical_work(
    tmp_path: Path, mode: str | None
) -> None:
    """An explicit unpriced hard/null request cannot select physical N5 work."""
    service, middleware, observer, job = await _issued_owner(tmp_path, mode=mode)
    policy = BudgetInvocationQuotaPolicy(
        allocation_id="scope-test", total_units=2, protected_units=1
    )
    try:
        with service._control_store.job_execution_fence(
            job_id=job.job_id, worker_id=job.lease_owner, attempt=job.attempt
        ):
            admission = service._control_store.current_execution_job_admission()
            with service._install_execution_scope(admission.scope):
                scope = service._current_verified_nl_budget_scope()
                observer = _with_scope(observer, scope)
                before = middleware._ledger.snapshot()
                with pytest.raises(
                    ProducerBudgetSourceError, match="usd_reservation_not_established"
                ):
                    _bind_scoped_n5_invocation_policy(
                        observer, n5_profile=_profile(policy), physical_n5_budget_scope=scope
                    )
                assert middleware._ledger.snapshot() == before
    finally:
        service.close()


@pytest.mark.asyncio
async def test_recursive_parent_refuses_unbound_physical_scope_before_native_n5(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The direct parent path cannot use the unscoped fallback for an NL job.

    Leaf generation is the existing contract-test adapter. The parent request,
    controller and NCM engine are real; the matching legacy control proves the
    graph would otherwise reach physical work.
    """
    from polisyos.core.artifacts import ArtifactOwnershipError
    from polisyos.runtime.quality import recursive_generation_cycle as recursive_owner
    from polisyos.runtime.quality.design_axes.coupling_composition import (
        derive_recursive_design_graph,
    )
    from polisyos.runtime.quality.generation_cycle import generation_cycle_terminal_state
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveCycleBudget,
        RecursiveGenerationCycleController,
        _blocked_parent_terminal,
        _fold_uncomposed_parent_terminal,
    )
    from tests.unit.runtime.quality.test_depth_n_universality import (
        REPO_ROOT,
        _lane0_coupled_request,
        _lane0_cycle_controller_factory,
        _lane0_subdesigns,
        _Lane0GenerationPort,
        _recursive_budget_state,
        _recursive_problem,
    )

    service, _, _, job = await _issued_owner(
        tmp_path, mode="metered_paid_producers_and_bounded_candidate"
    )
    root = "design://physical-budget/root"
    children = ("design://physical-budget/a", "design://physical-budget/b")
    graph = derive_recursive_design_graph(
        design_ref=root,
        module_refs=children,
        parent_child_edges=((root, children[0]), (root, children[1])),
        rule_version_ref="repo://rules/physical-budget-test",
    )
    problems = {node_ref: _recursive_problem(node_ref) for node_ref in (root, *children)}
    request = _lane0_coupled_request(parent_ref=root, child_refs=children, problem=problems[root])

    class StopAfterOneCandidate(_Lane0GenerationPort):
        async def __call__(self, problem, *, cycle_index):
            generated = await super().__call__(problem, cycle_index=cycle_index)
            generated.surrogate_rankings[0].score = 0.0
            generated.surrogate_rankings[0].voi_estimate = 0.0
            return generated

    def leaf_factory(node_ref, problem):
        controller = _lane0_cycle_controller_factory(node_ref, problem)
        controller._generation_port = StopAfterOneCandidate()
        return controller

    # Build each subdesign against the terminal the real N6 leaf owner emits;
    # the scripted adapter supplies a single candidate with no asserted VOI.
    from polisyos.pdc import gy_content_hash

    terminals = {}
    for child in children:
        leaf = await leaf_factory(child, problems[child]).run(
            problems[child],
            budget_state=_recursive_budget_state(),
            min_cycles=1,
            max_cycles=1,
            stable_design_problem_ref=gy_content_hash(problems[child].model_dump(mode="json")),
        )
        terminals[child] = generation_cycle_terminal_state(leaf)
    subdesigns = tuple(
        row.model_copy(
            update={
                "search_exit": row.search_exit.model_copy(
                    update={"terminal_state": terminals[row.workspace_id]}
                )
            }
        )
        for row in _lane0_subdesigns(parent_ref=root, child_refs=children)
    )
    calls = []
    original_run = JointSimulationHorizonController.run

    def record_real_parent_run(controller, request):
        calls.append(request)
        return original_run(controller, request)

    monkeypatch.setattr(JointSimulationHorizonController, "run", record_real_parent_run)

    async def run(scope: object | None, parent_request=request):
        controller = RecursiveGenerationCycleController.for_contract_testing(
            cycle_controller_factory=leaf_factory,
            repo_root=REPO_ROOT,
            artifact_store=FileSystemCAS(tmp_path / "recursive-cas"),
        )
        return await controller.run(
            graph,
            problems_by_node=problems,
            budget_state=_recursive_budget_state(),
            recursive_budget=RecursiveCycleBudget(
                max_depth=1, max_nodes=3, min_cycles_per_leaf=1, max_cycles_per_leaf=1
            ),
            joint_simulation_requests_by_node={root: parent_request},
            subdesign_contracts_by_node={root: subdesigns},
            execution_intents_by_node=dict.fromkeys(children, "candidate_only"),
            physical_n5_budget_scope=scope,
        )

    try:
        with service._control_store.job_execution_fence(
            job_id=job.job_id, worker_id=job.lease_owner, attempt=job.attempt
        ):
            admission = service._control_store.current_execution_job_admission()
            with service._install_execution_scope(admission.scope):
                scope = service._current_verified_nl_budget_scope()
                limited = await run(scope)
                root_node = next(node for node in limited.nodes if node.node_ref == root)
                assert root_node.joint_simulation is None
                assert "n5_invocation_quota_owner_not_established" in (
                    root_node.terminal.blocking_obligations
                )
                assert calls == []
                with pytest.raises(ValueError, match="recursive_parent_not_conservatively_blocked"):
                    _fold_uncomposed_parent_terminal(
                        _blocked_parent_terminal("fabricated_physical_scope_reason")
                    )

        legacy = await run(None)
        root_node = next(node for node in legacy.nodes if node.node_ref == root)
        assert root_node.joint_simulation is not None
        assert len(calls) == 1
        assert root_node.joint_simulation.physical_work_observations
        assert all(
            work.status == "completed"
            for work in root_node.joint_simulation.physical_work_observations
        )

        from tests.unit.runtime.quality.test_joint_simulation_horizon import _request

        unsupported_request = request.model_copy(update={"engine_plan": _request().engine_plan})
        unsupported = await run(None, unsupported_request)
        root_node = next(node for node in unsupported.nodes if node.node_ref == root)
        assert root_node.joint_simulation is not None
        assert root_node.terminal.blocking_obligations == ["unsupported_coupling_gated"]
        assert root_node.joint_simulation.physical_work_observations == ()
        assert len(calls) == 2

        # A wrapped storage denial at the parent admission boundary must keep
        # its actual cause, not become a generic budget diagnostic.
        denied = ArtifactOwnershipError("controlled selected-profile denial")

        def deny_selected_profile(*args, **kwargs):
            raise ProducerBudgetSourceError("selected_profile_unavailable") from denied

        with monkeypatch.context() as isolated:
            isolated.setattr(
                recursive_owner, "_bind_scoped_n5_invocation_policy", deny_selected_profile
            )
            with pytest.raises(ArtifactOwnershipError) as captured:
                await run(None)
        assert captured.value is denied
        assert len(calls) == 2
    finally:
        service.close()
