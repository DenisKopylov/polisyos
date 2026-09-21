"""Regression witnesses for the SRV-01 search contract extraction."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from polisyos.scientist.methods.search.adapters import LegacySearchServiceAdapter
from polisyos.scientist.methods.search.contracts import (
    CandidateProposal,
    EvaluationBundle,
)
from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.objective import (
    CompositeObjective,
    ObjectiveValue,
    OptimizationDirection,
)
from polisyos.scientist.methods.search.stopping import MaxIterations


class _Objective:
    @property
    def name(self) -> str:
        return "cost"

    def evaluate(self, results: dict[str, Any]) -> ObjectiveValue:
        return ObjectiveValue(
            name=self.name,
            raw_value=float(results.get("objective_value", 0.0)),
            direction=OptimizationDirection.MINIMIZE,
        )


class _Generator:
    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self,
        history: list[Any],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        del history, current_best, context
        candidate_id = f"candidate_{self.calls}"
        self.calls += 1
        return {"candidate_id": candidate_id, "x": self.calls}


def _build_adapter(
    *,
    max_iterations: int = 4,
    enable_stage_a: bool = True,
) -> tuple[LegacySearchServiceAdapter, _Generator]:
    generator = _Generator()
    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(max_iterations),
            objective=CompositeObjective([_Objective()]),
            enable_stage_a=enable_stage_a,
        ),
        candidate_generator=generator,
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": {"objective_value": float(candidate.get("x", 1.0))},
            "feedback": {"verdict": "APPROVE"},
        },
    )
    return LegacySearchServiceAdapter(controller), generator


def test_contracts_import_without_runtime_controller_or_funnel() -> None:
    """Importing DTOs must not load either concrete runtime implementation."""
    contracts_path = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "polisyos"
        / "scientist"
        / "methods"
        / "search"
        / "contracts.py"
    )
    script = """
import importlib.util
import sys
from pathlib import Path

class _Trap:
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {
            'polisyos.scientist.methods.search.controller',
            'polisyos.scientist.methods.search.funnel.orchestrator',
        }:
            raise AssertionError(f'eager runtime import: {fullname}')
        return None

sys.meta_path.insert(0, _Trap())
contracts_path = Path(__CONTRACTS_PATH__)
spec = importlib.util.spec_from_file_location('_contracts_probe', contracts_path)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(module)
CandidateProposal = module.CandidateProposal
SearchService = module.SearchService

assert CandidateProposal.__name__ == 'CandidateProposal'
assert SearchService.__name__ == 'SearchService'
assert 'polisyos.scientist.methods.search.controller' not in sys.modules
assert 'polisyos.scientist.methods.search.funnel.orchestrator' not in sys.modules
"""
    script = script.replace("__CONTRACTS_PATH__", repr(str(contracts_path)))
    env = dict(os.environ)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_legacy_adapter_alias_is_lazy_and_points_to_canonical_bridge() -> None:
    from polisyos.scientist.methods.search.adapters import (
        LegacySearchServiceAdapter as CanonicalAdapter,
    )
    from polisyos.scientist.methods.search.contracts import (
        LegacySearchServiceAdapter as CompatibilityAdapter,
    )

    assert CompatibilityAdapter is CanonicalAdapter


def test_ask_tell_uses_owner_transition_and_resumes_frontier() -> None:
    adapter, _ = _build_adapter()
    first = adapter.ask(goal=None, search_space=None, context={})

    assert len(first) == 1
    assert isinstance(first[0], CandidateProposal)
    first_result = adapter.tell(
        first[0].candidate_id,
        EvaluationBundle(
            objective_value=2.0,
            is_promising=True,
            objective_details=[
                ObjectiveValue(
                    name="cost",
                    raw_value=2.0,
                    direction=OptimizationDirection.MINIMIZE,
                )
            ],
        ),
    )

    assert first_result.history_length == 1
    assert first_result.best_candidate == first[0].payload
    assert first_result.best_objective == 2.0
    assert first_result.frontier_delta

    second = adapter.ask(goal=None, search_space=None, context={})
    second_result = adapter.tell(
        second[0].candidate_id,
        EvaluationBundle(
            objective_value=1.0,
            is_promising=True,
            objective_details=[
                ObjectiveValue(
                    name="cost",
                    raw_value=1.0,
                    direction=OptimizationDirection.MINIMIZE,
                )
            ],
        ),
    )

    assert second_result.history_length == 2
    assert second_result.best_candidate == second[0].payload
    assert second_result.best_objective == 1.0
    assert first_result.best_candidate == first[0].payload


def test_ask_tell_stage_a_rejection_does_not_count_stage_b() -> None:
    adapter, _ = _build_adapter()
    proposal = adapter.ask(goal=None, search_space=None, context={})[0]

    result = adapter.tell(
        proposal.candidate_id,
        EvaluationBundle(
            objective_value=1.0,
            is_promising=False,
            stage_a_passed=False,
        ),
    )

    assert result.history_length == 1
    assert adapter.controller._run_state.stage_a_evaluations == 1
    assert adapter.controller._run_state.stage_b_evaluations == 0


def test_ask_tell_disabled_stage_a_keeps_stage_b_counting() -> None:
    adapter, _ = _build_adapter(enable_stage_a=False)
    proposal = adapter.ask(goal=None, search_space=None, context={})[0]

    result = adapter.tell(
        proposal.candidate_id,
        EvaluationBundle(
            objective_value=1.0,
            is_promising=True,
        ),
    )

    assert result.history_length == 1
    assert adapter.controller._run_state.stage_a_evaluations == 0
    assert adapter.controller._run_state.stage_b_evaluations == 1


def test_unknown_and_duplicate_candidate_ids_do_not_create_history() -> None:
    adapter, _ = _build_adapter()

    with pytest.raises(KeyError):
        adapter.tell("unknown", EvaluationBundle(objective_value=1.0, is_promising=True))

    proposal = adapter.ask(goal=None, search_space=None, context={})[0]
    evaluation = EvaluationBundle(objective_value=1.0, is_promising=True)
    result = adapter.tell(proposal.candidate_id, evaluation)

    with pytest.raises(ValueError):
        adapter.tell(proposal.candidate_id, evaluation)
    assert result.history_length == 1
    assert adapter.controller._run_state.history_size == 1


def test_malformed_typed_feedback_cannot_fall_back_to_scalar_best() -> None:
    adapter, _ = _build_adapter()
    proposal = adapter.ask(goal=None, search_space=None, context={})[0]

    result = adapter.tell(
        proposal.candidate_id,
        EvaluationBundle(
            objective_value=-100.0,
            is_promising=True,
            policy_evaluation={"unexpected": "typed payload"},
        ),
    )

    assert result.best_candidate is None
    assert result.best_objective is None
    assert adapter.controller._run_state.history[0].policy_evaluation_status == "invalid"
    assert adapter.controller._run_state.policy_evaluation_errors == 1


def test_run_search_compatibility_path_remains_available() -> None:
    adapter, _ = _build_adapter(max_iterations=1)

    result = adapter.run_search(
        initial_context={},
        initial_candidate={"candidate_id": "seed", "x": 1.0},
    )

    assert result.best_candidate == {"candidate_id": "seed", "x": 1.0}
    assert result.history
    assert result.stage_a_evaluations == 1
    assert result.stage_b_evaluations == 1
