"""Public native runner consumes actual canonical accounting across CAS resume."""

import asyncio
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from runpy import run_path

import pytest
from test_service_persistence import _runner as _fixture_runner

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.llm.settlement import producer_settlement
from polisyos.core.llm.traced_client import LLMAccountingError, TracedLLMClient
from polisyos.scientist.methods.autotune.runtime import SearchLoopRunner
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerCompletionRequiredError,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer

_text = run_path(
    str(
        Path(__file__).resolve().parents[5]
        / "tests/integration/core/llm/test_gateway_response_text_cost.py"
    )
)


def _actual_operation(tmp_path, lexeme, *, key="run"):
    gateway = _text["TextGateway"](_text["response_text"]("usage", "cost_usd", lexeme))
    path = tmp_path / "resource-budget.json"
    owner = BudgetMiddleware(
        BudgetState(limits={key: BudgetLimit(key=key, max_usd=Decimal("5"))}),
        ledger=FileBudgetLedger(path),
    )
    enforcer = LLMBudgetEnforcer(
        client=TracedLLMClient(gateway, model_name="test-model"),
        budget_state=owner.budget_state,
        budget_middleware=owner,
        budget_keys=[key],
        model_name="test-model",
        run_id="factory-resource-run",
    )
    return gateway, path, enforcer


def _fresh_owner(path):
    return BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path))


def _runner(tmp_path, path, *, key="run", limit=100):
    _, store, registry, suite, evaluator, spec = _fixture_runner(tmp_path)
    runner = SearchLoopRunner(
        store=store,
        registry=registry,
        budget_middleware=_fresh_owner(path),
        budget_key=key,
        cost_budget_usd=limit,
    )
    return runner, store, suite, evaluator, spec


def _physical_call(enforcer):
    return asyncio.run(
        enforcer.generate(user="actual resource operation", max_tokens=1, _prompt_tokens_estimate=1)
    )


@pytest.mark.parametrize("lexeme", ["0", "1"])
@pytest.mark.parametrize("key", ["run", "native-resource"])
def test_public_runner_consumes_true_zero_or_paid_fresh_owner_snapshot(tmp_path, lexeme, key):
    gateway, path, enforcer = _actual_operation(tmp_path, lexeme, key=key)
    response = _physical_call(enforcer)
    settlement = producer_settlement(response)
    before = FileBudgetLedger(path).snapshot()
    assert gateway.transport.calls == 1 and settlement.event.amount == Decimal(lexeme)
    assert before.state.spent[key] == Decimal(lexeme)
    assert tuple(before.spend_receipts.values()) == settlement.ack.receipts
    runner, store, suite, evaluator, spec = _runner(tmp_path, path, key=key)
    service = runner.create_service(spec, suite_ref=suite, max_iterations=3)
    proposal = service.ask(None, None, {})[0]
    assert proposal.payload["value"] == 1 and evaluator.calls == []
    assert service.controller._run_state.budget_spent == float(lexeme)
    assert service.controller._run_state.budget_available is True
    assert service.controller._run_state.budget_evidence["admission"] == "admitted"
    old_ref = service.checkpoint_ref
    assert isinstance(old_ref, ArtifactRef)
    old_bytes = store.get_bytes(old_ref)
    fresh_runner, fresh_store, _, fresh_evaluator, fresh_spec = _runner(tmp_path, path, key=key)
    observer = fresh_runner.create_service(fresh_spec, suite_ref=suite, max_iterations=3)
    observer.restore(old_ref)
    assert observer.controller._run_state.budget_spent == float(lexeme)
    assert (
        observer.controller._run_state.budget_snapshot
        == service.controller._run_state.budget_snapshot
    )
    assert set(observer._pending_candidates) == {proposal.candidate_id}
    assert fresh_evaluator.calls == [] and fresh_store.get_bytes(old_ref) == old_bytes
    assert FileBudgetLedger(path).snapshot() == before


def test_public_runner_paid_cutoff_refuses_before_actual_generator_and_evaluator(tmp_path):
    gateway, path, enforcer = _actual_operation(tmp_path, "1")
    _physical_call(enforcer)
    before = FileBudgetLedger(path).snapshot()
    runner, _, suite, evaluator, spec = _runner(tmp_path, path, limit=1)
    result = runner.run(spec, suite_ref=suite, max_iterations=3)
    assert "Cost budget" in result.stopping_reason and "exhausted" in result.stopping_reason
    assert result.iterations_completed == result.stage_b_evaluations == 0
    assert result.best_candidate is None and evaluator.calls == []
    assert spec.candidate_generator.get_state()["index"] == 0
    assert result.telemetry["budget_spent"] == 1 and result.telemetry["budget_available"] is True
    assert FileBudgetLedger(path).snapshot() == before and gateway.transport.calls == 1


@pytest.mark.parametrize("lexeme", ["1e-1000", "-1e-1000"])
def test_public_factory_pending_owner_fence_survives_fresh_cas_restore_and_resume(tmp_path, lexeme):
    zero_gateway, path, zero = _actual_operation(tmp_path, "0")
    _physical_call(zero)
    runner, store, suite, evaluator, spec = _runner(tmp_path, path)
    service = runner.create_service(spec, suite_ref=suite, max_iterations=3)
    proposal = service.ask(None, None, {})[0]
    old_ref = service.checkpoint_ref
    old_bytes = store.get_bytes(old_ref)
    old_generator = deepcopy(spec.candidate_generator.get_state())
    old_pending = deepcopy(service._pending_candidates)
    gateway, _, unresolved = _actual_operation(tmp_path, lexeme)
    with pytest.raises(LLMAccountingError) as physical:
        _physical_call(unresolved)
    before = FileBudgetLedger(path).snapshot()
    assert physical.value.event["producer_event"].amount is None
    assert before.state.reserved["run"] > 0 and before.completion_obligations
    with pytest.raises(BudgetLedgerCompletionRequiredError):
        service.ask(None, None, {})
    assert service.checkpoint_ref == old_ref and store.get_bytes(old_ref) == old_bytes
    assert spec.candidate_generator.get_state() == old_generator
    assert service._pending_candidates == old_pending and service.controller._history == []
    assert service.controller._run_state.budget_spent is None
    assert service.controller._stopping_state()["budget_spent"] is None
    fresh_runner, fresh_store, _, fresh_evaluator, fresh_spec = _runner(tmp_path, path)
    result = fresh_runner.resume(
        fresh_spec, suite_ref=suite, checkpoint_ref=old_ref, max_iterations=3
    )
    assert "Cost budget unavailable" in result.stopping_reason
    assert result.iterations_completed == result.stage_b_evaluations == 0
    assert result.best_candidate is None and fresh_evaluator.calls == evaluator.calls == []
    assert (
        result.telemetry["budget_spent"] is None and result.telemetry["budget_available"] is False
    )
    final_ref = ArtifactRef.model_validate(result.telemetry["checkpoint_ref"])
    observer_runner, _, _, _, observer_spec = _runner(tmp_path, path)
    observer = observer_runner.create_service(observer_spec, suite_ref=suite, max_iterations=3)
    observer.restore(final_ref)
    assert observer._pending_candidates == old_pending
    assert observer.controller._run_state.budget_spent is None
    assert observer.controller._run_state.budget_evidence["admission"] == "unavailable"
    assert fresh_store.get_bytes(old_ref) == old_bytes
    assert FileBudgetLedger(path).snapshot() == before
    assert zero_gateway.transport.calls == gateway.transport.calls == 1
    assert proposal.payload["value"] == 1


def test_actual_owner_change_after_ask_preflight_is_not_rolled_back_to_known_zero(
    tmp_path, monkeypatch
):
    zero_gateway, path, zero = _actual_operation(tmp_path, "0")
    _physical_call(zero)
    runner, store, suite, evaluator, spec = _runner(tmp_path, path)
    service = runner.create_service(spec, suite_ref=suite, max_iterations=3)
    proposal = service.ask(None, None, {})[0]
    before_ref = service.checkpoint_ref
    before_bytes = store.get_bytes(before_ref)
    before_pending = deepcopy(service._pending_candidates)
    before_generator = deepcopy(spec.candidate_generator.get_state())
    gateway, _, unresolved = _actual_operation(tmp_path, "1e-1000")
    owner = service.controller._config.budget_middleware
    original = owner.pre_check
    visits = []

    def admit_then_actual_owner_changes(alias, budget_key="run"):
        result = original(alias, budget_key)
        visits.append((alias, budget_key))
        if len(visits) == 1:
            # Exact barrier seam: the real owner admitted preflight, then an
            # obtained physical completion retained its actual unknown amount.
            with pytest.raises(LLMAccountingError):
                _physical_call(unresolved)
        return result

    monkeypatch.setattr(owner, "pre_check", admit_then_actual_owner_changes)
    with pytest.raises(BudgetLedgerCompletionRequiredError):
        service.ask(None, None, {})
    assert len(visits) == 1 and visits[0][1] == "run"
    assert spec.candidate_generator.get_state() == before_generator
    assert (
        service._pending_candidates == before_pending == {proposal.candidate_id: proposal.payload}
    )
    assert evaluator.calls == [] and service.controller._history == []
    assert service.checkpoint_ref == before_ref and store.get_bytes(before_ref) == before_bytes
    assert service.controller._run_state.budget_spent is None
    assert service.controller._stopping_state()["budget_spent"] is None
    assert service.controller._run_state.budget_evidence["admission"] == "unavailable"
    assert FileBudgetLedger(path).snapshot().completion_obligations
    assert FileBudgetLedger(path).snapshot().state.reserved["run"] > 0
    with pytest.raises(BudgetLedgerCompletionRequiredError):
        _fresh_owner(path).pre_check("fresh-native-work", "run")
    assert zero_gateway.transport.calls == gateway.transport.calls == 1


@pytest.mark.parametrize("changed", ["key", "limit"])
def test_public_factory_resume_refuses_changed_cost_scope_or_rule(tmp_path, changed):
    _, path, enforcer = _actual_operation(tmp_path, "0")
    _physical_call(enforcer)
    runner, store, suite, _, spec = _runner(tmp_path, path)
    service = runner.create_service(spec, suite_ref=suite, max_iterations=3)
    service.ask(None, None, {})
    ref = service.checkpoint_ref
    before = store.get_bytes(ref)
    fresh_runner, _, _, evaluator, fresh_spec = _runner(
        tmp_path,
        path,
        key="different" if changed == "key" else "run",
        limit=99 if changed == "limit" else 100,
    )
    with pytest.raises(ValueError, match="configuration_mismatch"):
        fresh_runner.resume(fresh_spec, suite_ref=suite, checkpoint_ref=ref, max_iterations=3)
    assert evaluator.calls == [] and fresh_spec.candidate_generator.get_state()["index"] == 0
    assert store.get_bytes(ref) == before
