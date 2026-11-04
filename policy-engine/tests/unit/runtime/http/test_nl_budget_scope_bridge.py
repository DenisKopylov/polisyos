from __future__ import annotations

import pytest

import polisyos.runtime.http.services.control.generation_cycle as generation_bridge
from polisyos.core.contracts.control import NaturalLanguageRunRequest
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.quality.joint_simulation_horizon import (
    ProducerBudgetSourceError,
    _require_nl_physical_budget_scope,
)
from polisyos.scientist.orchestration.engine.budget import BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from tests._helpers.control_worker import dispatch_one_control_job
from tests._helpers.runtime_http import _build_control_service
from tests.unit.runtime.http.control_service_test_support import bound_nl_authorization_proof
from tests.unit.runtime.http.test_control_service_di import _fixture_claims


@pytest.mark.asyncio
async def test_control_bound_observer_refuses_removed_physical_scope(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real NL Control observer retains the owner scope across its bridge."""
    service = _build_control_service(tmp_path)
    store = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(tmp_path / "ledger.json"))
    service.bind_llm_producer_settlement_store(store)
    observed: list[object] = []
    original_compile = service.compile_and_run_recursive_generation_cycle

    async def inspect_bridge(**kwargs: object) -> object:
        scope = kwargs["physical_n5_budget_scope"]
        observer = kwargs["_producer_budget_reconciler"]
        assert scope is not None and observer is not None
        assert observer.invocation_guard_binding is scope
        assert observer._store is store
        with pytest.raises(
            ProducerBudgetSourceError, match="n5_physical_budget_scope_binding_mismatch"
        ):
            _require_nl_physical_budget_scope(None, observer, require_selected_quota=False)
        observed.append(scope)
        raise RuntimeError("scope_removal_probe_complete")

    async def enter_actual_control_bridge(**kwargs: object) -> object:
        return await original_compile(**kwargs)

    monkeypatch.setattr(
        generation_bridge, "compile_and_run_recursive_generation_cycle", inspect_bridge
    )
    monkeypatch.setattr(
        service, "compile_and_run_recursive_generation_cycle", enter_actual_control_bridge
    )
    try:
        request = NaturalLanguageRunRequest(
            request="Explore a policy option as a candidate.",
            llm_model="simulated-qwen",
            run_budget_usd=2.0,
        )
        claims = _fixture_claims()
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(claims),
            authorization_proof=bound_nl_authorization_proof(claims, request),
        )
        dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=launch.job_id,
        )
        completed = service._control_store.get_job(launch.job_id)
        assert completed is not None and completed.error_message == "scope_removal_probe_complete"
        assert len(observed) == 1
    finally:
        service.close()
