"""Actual ObjectiveStack, native publication and fresh invalid/legacy readback."""

from copy import deepcopy

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.autotune.runtime import SequenceCandidateGenerator
from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.objective import (
    BudgetDeficitObjective,
    CompositeObjective,
)
from polisyos.scientist.methods.search.run_state import checkpoint_json
from polisyos.scientist.methods.search.service import NativeSearchService
from polisyos.scientist.methods.search.stopping import MaxIterations
from polisyos.scientist.policy_design.objectives import ObjectiveStack


def _typed_stage_b(candidate, context):
    from polisyos.scientist.policy_design.objectives import PolicyEvaluationBundle

    result = {
        "simulation_results": {"budget_deficit": candidate["cost"]},
        "feedback": {"verdict": "APPROVE"},
    }
    mode = context["typed_mode"]
    if mode == "invalid_vector":
        result["policy_evaluation"] = {"unexpected": "present malformed"}
    elif mode == "invalid_bundle":
        result["policy_evaluation_bundle"] = {"unexpected": "present malformed"}
    elif mode == "typed_bundle":
        result["policy_evaluation_bundle"] = PolicyEvaluationBundle(
            simulation_metrics={"policy_value": 2.0, "employment": 0.5}
        )
    return result


def _service(root):
    return NativeSearchService(
        SearchController(
            SearchConfig(
                stopping=MaxIterations(1),
                objective=CompositeObjective([BudgetDeficitObjective()]),
                enable_stage_a=False,
                policy_objective_stack=ObjectiveStack(),
            ),
            SequenceCandidateGenerator([{"cost": -100}]),
            lambda candidate, context: (0.0, True),
            _typed_stage_b,
        ),
        store=FileSystemCAS(root),
    )


@pytest.mark.parametrize("mode", ["invalid_vector", "invalid_bundle", "legacy", "typed_bundle"])
def test_real_objective_stack_native_cas_preserves_invalid_present_and_legacy_projection(
    tmp_path, monkeypatch, mode
):
    calls = []
    original = ObjectiveStack.evaluate

    def observe(self, bundle):
        calls.append(deepcopy(bundle))
        return original(self, bundle)

    monkeypatch.setattr(ObjectiveStack, "evaluate", observe)
    context = {"typed_mode": mode}
    source = _service(tmp_path / "cas")
    result = source.run_search(initial_context=context)
    assert result.iterations_completed == result.stage_b_evaluations == len(result.history) == 1
    ref = source.checkpoint_ref
    retained = source._store.get_bytes(ref)
    fresh = _service(tmp_path / "cas")
    fresh.restore(ref, context=context)
    restored = fresh.resume_search(context=context)
    # Input bundles have a declared JSON checkpoint projection; the explicit
    # PolicyEvaluationVector remains typed, while raw StageB bundle models are
    # read back as their full original JSON payload rather than arbitrary objects.
    assert checkpoint_json(restored.history) == checkpoint_json(result.history)
    assert restored.history[0].policy_evaluation == result.history[0].policy_evaluation
    assert restored.best_candidate == result.best_candidate
    assert restored.best_objective == result.best_objective
    assert restored.pareto_front == result.pareto_front
    assert fresh._store.get_bytes(ref) == retained
    row = restored.history[0]
    if mode.startswith("invalid"):
        assert calls == []  # Invalid schema is refused before the real stack.
        assert row.policy_evaluation is None and row.policy_evaluation_status == "invalid"
        assert row.policy_evaluation_error == (
            "policy_evaluation_parse_failed"
            if mode == "invalid_vector"
            else "policy_evaluation_bundle_parse_failed"
        )
        assert row.objective_value == float("inf") and row.objective_details == []
        assert row.is_promising is False
        assert restored.best_candidate is None
        assert restored.best_objective == float("inf")
        assert restored.pareto_front == [] and fresh.controller._run_state.pareto_points == []
        assert restored.telemetry["policy_evaluation_errors"] == 1
    elif mode == "legacy":
        assert calls == []
        assert row.policy_evaluation_status == "missing" and row.policy_evaluation is None
        assert row.policy_evaluation_error is None
        assert restored.best_candidate == {"cost": -100}
        assert restored.best_objective == 100
        assert len(restored.pareto_front) == 1
        assert restored.telemetry["policy_evaluation_errors"] == 0
    else:
        assert len(calls) == 1 and calls[0].simulation_metrics["policy_value"] == 2
        assert row.policy_evaluation_status == "valid" and row.policy_evaluation is not None
        assert row.policy_evaluation.primary["policy_value"].value == 2
        assert row.stage_b_result["policy_evaluation_bundle"]["simulation_metrics"] == {
            "employment": 0.5,
            "policy_value": 2.0,
        }
        assert row.objective_value == row.policy_evaluation.legacy_scalar_proxy != 100
        assert row.policy_evaluation_error is None
        assert restored.telemetry["policy_evaluation_errors"] == 0
