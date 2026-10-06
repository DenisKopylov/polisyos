"""Available configured workflow: native policy callers and persisted accounting.

The transport supplies provider reports, not billing authority. The Foundry
consumer is the existing bootstrap estimator, not the native policy backend;
native raw-sample/estimand wiring remains an integration boundary.
"""

import hashlib
import json
from dataclasses import replace
from decimal import Decimal

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.simulation.inference import BootstrapInferenceEstimator
from polisyos.scientist.methods.search.funnel.level3_medium import Level3MediumFidelity
from polisyos.scientist.methods.search.funnel.level4_full import Level4FullFidelity
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import CheapSignalVector
from polisyos.scientist.methods.search.readiness import DecisionReadiness, DecisionReadinessContract
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient
from polisyos.scientist.orchestration.workflows.engine_simple import SimpleLoopEngine
from polisyos.scientist.policy_design.adversary import (
    ScenarioAdversaryConfig,
    ScenarioAdversaryWorker,
    ScenarioAttackSurface,
)
from polisyos.scientist.policy_design.output import (
    ChampionPolicyDossier,
    ConstraintSatisfactionReport,
    SubgroupImpactReport,
    UncertaintyReport,
)
from polisyos.scientist.policy_design.translator import (
    PolicyTranslatorConfig,
    PolicyTranslatorWorker,
    TranslatorInputBundle,
)


def translator_input():
    readiness = DecisionReadinessContract(
        readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
        required_judges_passed=[],
        required_uncertainty_bounds={},
        mandatory_human_gate=True,
        assumptions_must_be_surfaced=[],
        expiry_conditions=[],
        evidence_depth_required="fixture_observations",
    )
    return TranslatorInputBundle(
        dossier=ChampionPolicyDossier(
            candidate_id="candidate-1",
            candidate_hash="sha256:" + "a" * 64,
            readiness_level=readiness.readiness_level.value,
            executive_summary="Observed candidate.",
        ),
        readiness_contract=readiness,
        constraint_report=ConstraintSatisfactionReport(candidate_id="candidate-1", feasible=True),
        subgroup_report=SubgroupImpactReport(candidate_id="candidate-1"),
        uncertainty_report=UncertaintyReport(
            candidate_id="candidate-1",
            readiness_level=readiness.readiness_level.value,
        ),
        run_id="run-1",
    )


def configured_workflow(tmp_path, monkeypatch, *, cost=1.0, fail_after_paid=False, levels=(3, 4)):
    path = tmp_path / "budget.json"
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))})
    owner = BudgetMiddleware(state, ledger=FileBudgetLedger(path))
    calls = []
    observed = []

    class HTTPResponse:
        status = 200

        def __init__(self, kind):
            calls.append(kind)
            self.headers = {"x-request-id": f"request-{len(calls)}"}
            payload = (
                {"scenarios": [{"scenario_id": "scenario-1", "scenario_type": "bounded_shift"}]}
                if kind == "adversary"
                else {
                    "title": "Provider brief",
                    "executive_summary": "Observed candidate.",
                    "readiness_level": "research_artifact",
                }
            )
            self.body = json.dumps(
                {
                    "choices": [{"message": {"content": json.dumps(payload)}}],
                    "provider": "provider-a",
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost_usd": cost},
                }
            )

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def text(self):
            return self.body

    class HTTPSession:
        def post(self, *args, **kwargs):
            payload = kwargs["json"]
            assert all(not key.startswith("_") for key in payload)
            return HTTPResponse(
                "adversary" if payload["model"] == "gpt-3.5-turbo" else "translator"
            )

        async def close(self):
            pass

    async def transport_only(self, timeout_s):
        return HTTPSession()

    # Real configured factory -> TracedLLMClient -> budget owner -> native Gateway
    # decoder. Only the physical HTTP exchange is controlled by this fixture.
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", "https://fixture.invalid")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-fixture-native-transport")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "0")
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "false")
    monkeypatch.setattr(GatewayLLMClient, "_ensure_session", transport_only)

    def estimate(runtime_state):
        assert runtime_state["_resource_budget_middleware"] is owner
        evaluation_id = runtime_state["_resource_evaluation_id"]
        params = runtime_state["estimation_config"]
        if params["n_bootstrap"] == 20:
            worker = ScenarioAdversaryWorker(
                ScenarioAdversaryConfig(
                    model_name="gpt-3.5-turbo", budget_keys=["run"], fallback_on_error=False
                ),
                budget_middleware=runtime_state["_resource_budget_middleware"],
            )
            result = worker.propose(
                ScenarioAttackSurface(candidate_id=runtime_state["ir"]["candidate_id"]),
                run_id=runtime_state["run_id"],
                evaluation_id=evaluation_id,
            )
            assert not result.fallback_used
        else:
            worker = PolicyTranslatorWorker(
                PolicyTranslatorConfig(
                    model_name="gpt-4", budget_keys=["run"], fallback_on_error=False
                ),
                budget_middleware=runtime_state["_resource_budget_middleware"],
            )
            result = worker.translate(translator_input(), evaluation_id=evaluation_id)
            assert result.title == "Provider brief"
        if fail_after_paid:
            raise RuntimeError("failed after native paid response")
        actual = BootstrapInferenceEstimator.pure_step(
            {"data": runtime_state["observations"]}, params
        )["result"]
        observed.append(actual)
        runtime_state["simulation_results"] = {
            "gdp_change": actual["point_estimate"],
            "ate": actual["point_estimate"],
            "bootstrap": {"ci_width": actual["ci_upper"] - actual["ci_lower"]},
        }
        return runtime_state

    def feedback(runtime_state):
        return {**runtime_state, "feedback": {"verdict": "APPROVE"}}

    engine = SimpleLoopEngine([("estimate", estimate), ("feedback", feedback)], "feedback")
    stages = []
    if 3 in levels:
        stages.append(Level3MediumFidelity(engine, bootstrap_draws=20))
    if 4 in levels:
        stages.append(Level4FullFidelity(engine))
    funnel = FunnelOrchestrator(stages, stage_a_max_level=3, budget_middleware=owner)
    context = {
        "run_id": "run-1",
        "observations": list(range(1, 21)),
        "estimation_config": {"n_bootstrap": 80, "confidence_level": 0.95, "seed": 17},
    }
    return path, owner, funnel, calls, observed, context


def assert_receipts(path, outcome, expected):
    reopened = FileBudgetLedger(path).snapshot()
    assert reopened.state.spent.get("run", Decimal(0)) == Decimal(str(expected))
    assert reopened.state.remaining("run") == Decimal("5") - Decimal(str(expected))
    assert reopened.state.reserved["run"] == 0
    assert outcome.provider_spend_usd == Decimal(str(expected))
    assert outcome.compute_cost_source == "provider_reported_only"
    assert len(outcome.resource_event_ids) == len(reopened.spend_receipts)
    assert all(
        any(
            receipt.event_id.startswith(event_id + ":budget:")
            for receipt in reopened.spend_receipts.values()
        )
        for event_id in outcome.resource_event_ids
    )
    assert sum(
        (receipt.amount for receipt in reopened.spend_receipts.values()), Decimal(0)
    ) == Decimal(str(expected))
    assert all(
        receipt.provider == "provider-a" and receipt.key == "run"
        for receipt in reopened.spend_receipts.values()
    )
    return reopened


def test_native_policy_callers_full_split_actual_events_and_fresh_reopen(tmp_path, monkeypatch):
    completed = []
    for mode in ("full", "split"):
        path, _, funnel, calls, observed, context = configured_workflow(
            tmp_path / mode, monkeypatch
        )
        ticket = funnel.submit({"candidate_id": "candidate-1"}, context)
        empty = funnel.get_outcome(ticket)
        assert empty.evaluation_status == "not_evaluated"
        assert empty.provider_spend_usd is None and empty.resource_event_ids == ()
        if mode == "split":
            partial = funnel.advance(ticket, policy="stage_a")
            assert partial.evaluation_status == "partial"
            assert len(partial.trace) == 1
            assert_receipts(path, partial, 1)
        outcome = funnel.advance(ticket, policy="full")
        assert outcome.completed and outcome.evaluation_status == "evaluated"
        assert calls == ["adversary", "translator"]
        snapshot = assert_receipts(path, outcome, 2)
        assert [step.provider_spend_usd for step in outcome.trace] == [Decimal("1"), Decimal("1")]
        assert [result["n_bootstrap"] for result in observed] == [20, 80]
        # Current B receipt persists key/provider/digest, not evaluation/run scope.
        assert all(
            len(receipt.payload_digest) == 64 for receipt in snapshot.spend_receipts.values()
        )
        cached = funnel.submit({"candidate_id": "candidate-1"}, context)
        assert cached is ticket
        assert funnel.advance(cached, policy="full").provider_spend_usd == Decimal("2")
        assert calls == ["adversary", "translator"]
        completed.append(
            [
                (receipt.key, receipt.provider, receipt.amount)
                for receipt in snapshot.spend_receipts.values()
            ]
        )
    assert completed[0] == completed[1]


def test_actual_foundry_consumer_uses_reduced_draws_with_independent_numeric_oracle(
    tmp_path, monkeypatch
):
    _, _, funnel, _, observed, context = configured_workflow(tmp_path, monkeypatch)
    ticket = funnel.submit({"candidate_id": "candidate-1"}, context)
    funnel.advance(ticket, policy="full")
    data = np.asarray(context["observations"], dtype=float)
    for actual, draws in zip(observed, (20, 80), strict=True):
        rng = np.random.default_rng(17)
        means = np.asarray(
            [data[rng.integers(0, len(data), size=len(data))].mean() for _ in range(draws)]
        )
        assert actual["n_bootstrap"] == draws
        assert actual["bootstrap_mean"] == pytest.approx(means.mean())
        assert actual["ci_lower"] == pytest.approx(np.percentile(means, 2.5))
        assert actual["ci_upper"] == pytest.approx(np.percentile(means, 97.5))
    assert observed[0]["ci_upper"] != observed[1]["ci_upper"]
    assert context["estimation_config"]["n_bootstrap"] == 80


@pytest.mark.parametrize(("cost", "failed"), [(0.0, False), (1.0, True)])
def test_zero_measurement_and_paid_failed_stage_are_distinct(tmp_path, monkeypatch, cost, failed):
    path, _, funnel, calls, _, context = configured_workflow(
        tmp_path, monkeypatch, cost=cost, fail_after_paid=failed, levels=(4,)
    )
    outcome = funnel.advance(funnel.submit({"candidate_id": "candidate-1"}, context), policy="full")
    assert calls == ["translator"]
    assert_receipts(path, outcome, cost)
    assert outcome.final_result.is_promising is (not failed)
    assert len(outcome.trace) == 1


def test_trace_cost_one_without_settlement_fails_accounting_control(tmp_path, monkeypatch):
    path, owner, funnel, calls, _, context = configured_workflow(tmp_path, monkeypatch, levels=(4,))

    def remove_settlement(event_id, key, amount, *, payload_digest, provider=None):
        from datetime import UTC, datetime

        from polisyos.scientist.orchestration.engine.budget_ledger import BudgetLedgerSpendReceipt

        # Counterfactual ACK retains all new markers but has no durable receipt.
        return BudgetLedgerSpendReceipt(
            event_id=event_id,
            key=key,
            amount=amount,
            payload_digest=payload_digest,
            provider=provider,
            revision=1,
            committed_at=datetime.now(UTC),
        )

    monkeypatch.setattr(owner, "settle_spend_safe", remove_settlement)
    stage = funnel._stages_by_level[4]
    native = stage.evaluate
    monkeypatch.setattr(
        stage,
        "evaluate",
        lambda candidate, ctx: replace(native(candidate, ctx), compute_actual_usd=1.0),
    )
    outcome = funnel.advance(funnel.submit({"candidate_id": "candidate-1"}, context), policy="full")
    assert calls == ["translator"]
    assert outcome.trace[0].compute_actual_usd == 1.0
    assert outcome.final_result.is_promising is False
    assert outcome.stage_results[4].feedback["fidelity_level"] == 4
    assert FileBudgetLedger(path).snapshot().spend_receipts == {}
    with pytest.raises(AssertionError):
        assert_receipts(path, outcome, 1)


@pytest.mark.parametrize("write_before_ack", [False, True])
def test_actual_native_unknown_ack_retains_observed_input_and_exact_fresh_readback(
    tmp_path, monkeypatch, write_before_ack
):
    path, owner, funnel, calls, observed, context = configured_workflow(
        tmp_path, monkeypatch, levels=(3,)
    )
    original = owner.settle_spend_safe
    actual_inputs = []

    def lose_ack(*args, **kwargs):
        actual_inputs.append((args, kwargs))
        if write_before_ack:
            original(*args, **kwargs)
        raise OSError("actual settlement acknowledgment unavailable")

    monkeypatch.setattr(owner, "settle_spend_safe", lose_ack)
    outcome = funnel.advance(funnel.submit({"candidate_id": "candidate-1"}, context), policy="full")
    assert calls == ["adversary"] and observed == []
    assert outcome.final_action == "reject" and not outcome.final_result.is_promising
    feedback = outcome.final_result.feedback
    assert feedback["resource_reported_input_usd"] == "1.0"
    reopened = FileBudgetLedger(path).snapshot()
    assert reopened.state.reserved["run"] > 0  # D does not issue release authority.
    args, kwargs = actual_inputs[0]
    if write_before_ack:
        assert feedback["resource_settlement_status"] == "committed_after_unknown_ack"
        assert outcome.provider_spend_usd == Decimal(1)
        receipt = FileBudgetLedger(path).resolve_spend(args[0])
        assert receipt.event_id.startswith(
            feedback["resource_unknown_ack_readback_ids"][0] + ":budget:"
        )
        assert receipt.payload_digest == kwargs["payload_digest"]
        assert original(*args, **kwargs) == receipt
        assert FileBudgetLedger(path).load().spent["run"] == Decimal(1)
    else:
        assert feedback["resource_settlement_status"] == "unknown"
        assert outcome.provider_spend_usd is None
        pending = feedback["resource_settlement_pending"][0]
        assert pending["event"]["amount"] == "1.0" and pending["budget_keys"] == ["run"]
        assert (
            args[0]
            == pending["event"]["event_id"] + ":budget:" + hashlib.sha256(b"run").hexdigest()
        )
        assert (
            kwargs["payload_digest"]
            == hashlib.sha256((pending["payload_digest"] + ":run").encode()).hexdigest()
        )
        assert FileBudgetLedger(path).resolve_spend(args[0]) is None
        assert reopened.state.spent == {} and reopened.spend_receipts == {}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("key", "foreign"),
        ("amount", Decimal(0)),
        ("provider", "foreign"),
        ("payload_digest", "0" * 64),
    ],
)
def test_native_unknown_ack_rejects_mismatched_readback_with_typed_receipt_marker(
    tmp_path, monkeypatch, field, value
):
    path, owner, funnel, calls, observed, context = configured_workflow(
        tmp_path, monkeypatch, levels=(3,)
    )
    settle = owner.settle_spend_safe
    resolve = owner.resolve_spend_safe

    def lose_ack(*args, **kwargs):
        settle(*args, **kwargs)
        raise OSError("actual settlement acknowledgment unavailable")

    def corrupt(event_id):
        receipt = resolve(event_id)
        return receipt.model_copy(update={field: value}) if receipt is not None else None

    monkeypatch.setattr(owner, "settle_spend_safe", lose_ack)
    monkeypatch.setattr(owner, "resolve_spend_safe", corrupt)
    outcome = funnel.advance(funnel.submit({"candidate_id": "candidate-1"}, context), policy="full")
    assert calls == ["adversary"] and observed == []
    assert not outcome.final_result.is_promising
    assert outcome.provider_spend_usd is None
    assert outcome.final_result.feedback["resource_settlement_status"] == "unknown"
    assert FileBudgetLedger(path).load().spent["run"] == Decimal(1)


def test_removing_reduced_config_fails_actual_draw_oracle_with_marker_retained(
    tmp_path, monkeypatch
):
    _, _, funnel, _, observed, context = configured_workflow(tmp_path, monkeypatch)
    reduced = funnel.stages[0]
    original = reduced._build_reduced_state

    def remove_draw_overlay(candidate, ctx):
        state = original(candidate, ctx)
        state["estimation_config"]["n_bootstrap"] = ctx["estimation_config"]["n_bootstrap"]
        return state

    monkeypatch.setattr(reduced, "_build_reduced_state", remove_draw_overlay)
    outcome = funnel.advance(
        funnel.submit({"candidate_id": "candidate-1"}, context), policy="stage_a"
    )
    assert outcome.stage_results[3].fidelity_level == 3
    assert outcome.stage_results[3].feedback["fidelity_config"]["bootstrap_draws"] == 20
    with pytest.raises(AssertionError):
        assert observed[0]["n_bootstrap"] == 20


def test_actual_spend_does_not_resume_but_released_owned_capacity_rechecks_remaining_work(
    tmp_path, monkeypatch
):
    path, owner, funnel, calls, _, context = configured_workflow(tmp_path, monkeypatch)
    # B1.1 exposes scalar reservations. This historical selector does not prove
    # durable reservation ownership; that part of the original criterion is held.
    assert owner.reserve_safe("run", Decimal("3.5"))
    candidate = {"candidate_id": "candidate-1"}
    ticket = funnel.submit(candidate, context)
    paused = funnel.advance(ticket, policy="full")
    assert paused.final_action == "defer" and paused.completed
    assert calls == ["adversary"]
    assert FileBudgetLedger(path).load().remaining("run") == Decimal("0.5")
    unrelated = ScenarioAdversaryWorker(
        ScenarioAdversaryConfig(
            model_name="gpt-3.5-turbo", budget_keys=["run"], fallback_on_error=False
        ),
        budget_middleware=owner,
    )
    unrelated.propose(
        ScenarioAttackSurface(candidate_id="other-candidate"),
        run_id="run-1",
        evaluation_id="other-reported-call",
    )
    assert FileBudgetLedger(path).load().spent["run"] == Decimal("2")
    assert funnel.submit(candidate, context) is ticket
    assert funnel.advance(ticket, policy="full").final_action == "defer"
    assert calls == ["adversary", "adversary"]
    owner.release_safe("run", Decimal("3.5"))
    successor = funnel.submit(candidate, context)
    assert successor is not ticket
    assert successor.parent_ticket_id == ticket.ticket_id
    assert successor.current_level == 3 and len(successor.trace) == 1
    completed = funnel.advance(successor, policy="full")
    assert completed.completed and completed.final_action == "complete"
    assert calls == ["adversary", "adversary", "translator"]
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.state.spent["run"] == Decimal("3")
    assert snapshot.state.remaining("run") == Decimal("2")
    assert completed.provider_spend_usd == Decimal("2")
    assert len(completed.resource_event_ids) == 2
    assert len(snapshot.spend_receipts) == 3


def test_removing_signal_absent_budget_guard_fails_zero_downstream_effects(tmp_path, monkeypatch):
    path, owner, funnel, calls, _, context = configured_workflow(tmp_path, monkeypatch)
    assert owner.reserve_safe("run", Decimal("3.5"))
    original = funnel._maybe_schedule_transition

    def remove_signal_absent_capacity_guard(ticket, **kwargs):
        if ticket.last_result is not None and ticket.last_result.cheap_signal is None:
            return None
        return original(ticket, **kwargs)

    monkeypatch.setattr(funnel, "_maybe_schedule_transition", remove_signal_absent_capacity_guard)
    outcome = funnel.advance(funnel.submit({"candidate_id": "candidate-1"}, context), policy="full")
    assert outcome.stage_results[3].feedback["fidelity_config"]["bootstrap_draws"] == 20
    assert outcome.stage_results[4].fidelity_level == 4
    assert FileBudgetLedger(path).load().spent["run"] == Decimal("2")
    with pytest.raises(AssertionError):
        assert calls == ["adversary"]


@pytest.mark.parametrize("routing_reject", [False, True])
@pytest.mark.parametrize("cost", [0.0, 1.0])
def test_actual_native_cost_identity_survives_routing_and_compatibility_projections(
    tmp_path, monkeypatch, routing_reject, cost
):
    path, _, funnel, calls, _, context = configured_workflow(tmp_path, monkeypatch, cost=cost)
    if routing_reject:
        stage = funnel._stages_by_level[3]
        native_evaluate = stage.evaluate

        def route_paid_native_result(candidate, context):
            return replace(
                native_evaluate(candidate, context),
                cheap_signal=CheapSignalVector(structural_validity=0.0),
            )

        monkeypatch.setattr(stage, "evaluate", route_paid_native_result)

    candidate = {"candidate_id": "candidate-1"}
    ticket = funnel.submit(candidate, context)
    outcome = funnel.advance(ticket, policy="full")
    expected_calls = ["adversary"] if routing_reject else ["adversary", "translator"]
    assert calls == expected_calls
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.state.spent["run"] == Decimal(str(cost)) * len(expected_calls)
    assert len(snapshot.spend_receipts) == len(expected_calls)
    assert outcome.final_action == ("reject" if routing_reject else "complete")
    assert outcome.provider_spend_usd == snapshot.state.spent["run"]
    assert all(
        any(
            receipt.event_id.startswith(event_id + ":budget:")
            for receipt in snapshot.spend_receipts.values()
        )
        for event_id in outcome.resource_event_ids
    )
    final_stage = outcome.final_result
    assert final_stage.provider_spend_usd == Decimal(str(cost))
    assert final_stage.compute_cost_source == "provider_reported_only"
    assert set(final_stage.resource_event_ids) == set(outcome.trace[-1].resource_event_ids)
    assert final_stage.provider_spend_usd == outcome.trace[-1].provider_spend_usd

    compatibility = funnel.evaluate(candidate, context)
    assert compatibility.is_promising is (not routing_reject)
    assert compatibility.feedback["verdict"] == ("REJECT" if routing_reject else "APPROVE")
    assert compatibility.compute_cost_source == final_stage.compute_cost_source
    assert compatibility.provider_spend_usd == final_stage.provider_spend_usd
    assert compatibility.resource_event_ids == final_stage.resource_event_ids
    native = funnel.as_stage_b_callable()(candidate, context)
    assert native["_funnel_result"].resource_event_ids == final_stage.resource_event_ids
    assert native["_funnel_outcome"].resource_event_ids == outcome.resource_event_ids
    assert calls == expected_calls
