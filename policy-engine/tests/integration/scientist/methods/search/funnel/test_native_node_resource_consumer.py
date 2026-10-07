"""Bounded full Node consumer. Scientific/authority boundaries controlled.

Literal existing Node/Funnel/adapter, controlled producer addition in adapter,
real native worker configured factory,
Gateway decoder and B1.2 persisted owner. Native draw/permit positives UNRUN.
"""

import importlib.util
import json
import logging
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.scientist.methods.search.funnel.level3_medium import Level3MediumFidelity
from polisyos.scientist.nodes.builtins.decide import (
    run_policy_blueprint_runtime as runtime,
)
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.adversary import (
    ScenarioAdversaryConfig,
    ScenarioAdversaryWorker,
    ScenarioAttackSurface,
)
from polisyos.scientist.policy_design.translator import (
    PolicyTranslatorConfig,
    PolicyTranslatorWorker,
)

ROOT = Path(runtime.__file__).resolve().parents[6]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fun3 = load("e02_current_fun3", "tests/unit/remediation/test_fun_03.py")
paid = load(
    "e02_current_paid",
    "tests/integration/scientist/methods/search/funnel/test_orchestrator.py",
)


def execute(
    monkeypatch,
    tmp_path,
    *,
    cost=1.0,
    split=False,
    width=0.4,
    empty=None,
    optional_verdict=True,
    tiny=None,
):
    ledger_path, owner, _, calls, _, _ = paid.configured_workflow(
        tmp_path / "native-resources", monkeypatch, cost=cost, cost_lexeme=tiny
    )
    canonical_workflow_run = runtime._PolicyRuntimeWorkflowEngine.run
    canonical_orchestrator = runtime.FunnelOrchestrator
    harness = fun3._install_actual_runtime_node_dependencies(
        monkeypatch, tmp_path / "node", mode="normal"
    )
    monkeypatch.setattr(runtime, "Level3MediumFidelity", Level3MediumFidelity)
    scientific_backend = runtime.ProductionPolicyEvaluationBackend
    observations = {"stage_contexts": [], "advance_calls": 0, "split_partial": None}

    class Backend(scientific_backend):
        def evaluate(self, candidate, **kwargs):
            result = super().evaluate(candidate, **kwargs)
            result.simulation_results.update(
                {"gdp_change": 0.0, "ate": 0.0, "bootstrap": {"ci_width": width}}
            )
            return result

    def native_run(adapter, initial_state):
        # Actual stage event ID/owner reach existing native caller, not a guessed ID.
        context = initial_state
        assert context["_resource_evaluation_id"]
        # Fallback retains the fixture-owned physical producer in the removal
        # control; it is not proof the default scientific backend issues paid calls.
        middleware = context.get("_resource_budget_middleware", owner)
        observations["stage_contexts"].append(
            {
                "fidelity": adapter._fidelity,
                "evaluation_id": context["_resource_evaluation_id"],
                "budget_owner_same": middleware is owner,
                "effective_estimation_config": dict(context.get("estimation_config", {})),
            }
        )
        if adapter._fidelity == "medium":
            value = ScenarioAdversaryWorker(
                ScenarioAdversaryConfig(
                    model_name="gpt-3.5-turbo",
                    fallback_on_error=False,
                    budget_keys=["run"],
                ),
                budget_middleware=middleware,
            ).propose(
                ScenarioAttackSurface(candidate_id="candidate_fun_03"),
                run_id=harness["state"].run_id,
                evaluation_id=context["_resource_evaluation_id"],
            )
            assert not value.fallback_used
        else:
            value = PolicyTranslatorWorker(
                PolicyTranslatorConfig(
                    model_name="gpt-4", fallback_on_error=False, budget_keys=["run"]
                ),
                budget_middleware=middleware,
            ).translate(
                paid.translator_input().model_copy(update={"run_id": harness["state"].run_id}),
                evaluation_id=context["_resource_evaluation_id"],
            )
            assert value.title == "Provider brief"
        return canonical_workflow_run(adapter, initial_state)

    class ObservedOrchestrator(canonical_orchestrator):
        def __init__(self, **kwargs):
            if empty == "stages":
                kwargs["stages"] = []
            elif empty == "cap":
                kwargs["stages"] = [s for s in kwargs["stages"] if s.fidelity_level == 4]
                kwargs["max_level"] = 2
            if not optional_verdict:
                stage = next(s for s in kwargs["stages"] if s.fidelity_level == 2)
                original = stage.evaluate

                def omit(candidate, context):
                    from dataclasses import replace

                    return replace(original(candidate, context), feedback={})

                stage.evaluate = omit
            super().__init__(**kwargs)
            observations["orchestrator"] = self

        def advance(self, ticket, **kwargs):
            observations["advance_calls"] += 1
            if split:
                observations["split_partial"] = super().advance(ticket, policy="stage_a")
                observations["split_partial_calls"] = list(calls)
                observations["split_partial_snapshot"] = FileBudgetLedger(ledger_path).snapshot()
            result = super().advance(ticket, **kwargs)
            observations["outcome"] = result
            return result

    monkeypatch.setattr(runtime, "ProductionPolicyEvaluationBackend", Backend)
    monkeypatch.setattr(runtime._PolicyRuntimeWorkflowEngine, "run", native_run)
    monkeypatch.setattr(runtime, "FunnelOrchestrator", ObservedOrchestrator)
    ctx = runtime.PolicyBudgetExecutionContext(
        store=harness["store"],
        run=None,
        logger=logging.getLogger("e02_native_node"),
        budget_middleware=owner,
    )
    output = runtime.RunPolicyBlueprintRuntimeNode().execute(ctx, harness["state"])
    assert output.status == "ok" and observations["advance_calls"] == 1
    assert harness["runner_calls"] == harness["promotion_writes"] == []
    fresh_ledger = FileBudgetLedger(ledger_path).snapshot()
    cas = tmp_path / "cas"
    ref = FileSystemCAS(cas).put_bytes(
        output.state.model_dump_json().encode(),
        PutOptions(kind="scientist.experiment_state", media_type="application/json"),
    )
    fresh_state = ExperimentState.model_validate_json(FileSystemCAS(cas).get_bytes(ref))
    projected = fresh_state.params["_funnel_outcome"]
    # Compare the canonical JSON-safe returned view: failed stage sentinels
    # become null in ExperimentState serialization, rather than JSON Infinity.
    canonical_returned = json.loads(output.state.model_dump_json())["params"]["_funnel_outcome"]
    assert projected == canonical_returned
    (tmp_path / "node-consumer-observations.json").write_text(
        json.dumps(
            {
                "literal_caller": "RunPolicyBlueprintRuntimeNode.execute",
                "calls": calls,
                "stage_contexts": observations["stage_contexts"],
                "node_projection": projected,
                "fresh_state_ref": ref.model_dump(mode="json"),
                "authority_positive": "UNRUN/not_established",
                "native_draw_positive": "UNRUN/producer_missing",
            },
            indent=2,
            default=str,
        )
    )
    return projected, observations, fresh_ledger, calls


@pytest.mark.parametrize("cost", [1.0, 0.0])
@pytest.mark.parametrize("split", [False, True])
def test_literal_node_configured_paid_or_zero_settlement_fresh_cas(
    monkeypatch, tmp_path, cost, split
):
    projected, observations, snapshot, calls = execute(
        monkeypatch, tmp_path, cost=cost, split=split
    )
    assert calls == ["adversary", "translator"]
    expected = Decimal(str(cost)) * 2  # Independent physical-event denominator.
    assert snapshot.state.spent["run"] == expected and len(snapshot.spend_receipts) == 2
    assert snapshot.state.reserved["run"] == 0
    assert projected["provider_spend_usd"] is not None, (
        "full native Node lost real owner settlement at returned projection"
    )
    assert Decimal(projected["provider_spend_usd"]) == expected
    assert len(projected["resource_event_ids"]) == 2
    assert all(
        any(
            receipt.event_id.startswith(event_id + ":budget:")
            for receipt in snapshot.spend_receipts.values()
        )
        for event_id in projected["resource_event_ids"]
    )
    assert projected["final_action"] == "defer_to_human"
    if split:
        assert observations["split_partial"].evaluation_status == "partial"
        # The ordinary Node uses its default Stage A cap of L2. The physical
        # L3/L4 workers have not run at that boundary; absent debit stays None.
        assert observations["split_partial"].provider_spend_usd is None
        assert observations["split_partial"].resource_event_ids == ()
        assert observations["split_partial_calls"] == []
        assert observations["split_partial_snapshot"].state.spent == {}
        assert observations["split_partial_snapshot"].spend_receipts == {}


@pytest.mark.parametrize("empty", ["stages", "cap"])
def test_literal_node_empty_has_no_numeric_positive_no_resource(monkeypatch, tmp_path, empty):
    projected, _, snapshot, calls = execute(monkeypatch, tmp_path, empty=empty)
    assert calls == [] and snapshot.spend_receipts == {}
    assert projected["evaluation_status"] == "not_evaluated"
    assert projected["provider_spend_usd"] is None and projected["stage_results"] == {}


@pytest.mark.parametrize(
    ("width", "method", "level"),
    [
        (None, "ci_width_missing", 1.0),
        ("broken", "ci_width_invalid", 1.0),
        (float("nan"), "ci_width_invalid", 1.0),
        (0.0, "full_fidelity_bootstrap", 0.0),
        # This full-Node fixture declares ATE=0. A finite positive-width
        # interval is maximally uncertain; true width zero remains measured 0.
        (0.4, "full_fidelity_bootstrap", 1.0),
    ],
)
def test_literal_node_width_retains_available_scores_and_money(
    monkeypatch, tmp_path, width, method, level
):
    projected, observations, snapshot, calls = execute(monkeypatch, tmp_path, width=width)
    assert calls == ["adversary", "translator"] and snapshot.state.spent["run"] == 2
    envelope = observations["outcome"].stage_results[4].uncertainty_envelope
    estimate = next(e for t, e in envelope.uncertainties.items() if t.value == "statistical")
    assert estimate.quantification_method == method and estimate.level == pytest.approx(level)
    assert projected["stage_results"]["4"]["objective_value"] == 0.0
    assert Decimal(projected["provider_spend_usd"]) == 2


@pytest.mark.parametrize("optional_verdict", [False, True])
def test_literal_node_final_aggregate_survives_optional_approve(
    monkeypatch, tmp_path, optional_verdict
):
    projected, _, snapshot, calls = execute(
        monkeypatch, tmp_path, optional_verdict=optional_verdict
    )
    assert calls == ["adversary", "translator"] and snapshot.state.spent["run"] == 2
    assert projected["stage_results"]["4"]["is_promising"] is True
    assert projected["final_action"] == "defer_to_human"


@pytest.mark.parametrize("tiny", ["1e-1000", "-1e-1000"])
def test_literal_node_unknown_cost_preserves_pending_and_no_false_zero(monkeypatch, tmp_path, tiny):
    projected, _, snapshot, calls = execute(monkeypatch, tmp_path, cost=None, tiny=tiny)
    assert calls == ["adversary"] and snapshot.spend_receipts == {}
    assert snapshot.completion_obligations and projected["provider_spend_usd"] is None
    pending = projected["stage_results"]["3"]["feedback"]
    assert (
        pending["resource_reported_input_usd"] is None
        and pending["resource_reported_input_status"] == "unknown"
    )
    assert pending["resource_settlement_pending"]
