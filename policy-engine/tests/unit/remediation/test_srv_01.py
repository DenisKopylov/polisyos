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
    """Canonical imports keep runtime code deferred until the facade is used."""
    source_root = Path(__file__).resolve().parents[3] / "src"
    script = """
import importlib
import sys
import traceback

blocked = {
    'polisyos.scientist.methods.search.controller',
    'polisyos.scientist.methods.search.funnel.orchestrator',
}
class _Trap:
    def __init__(self):
        self.attempts = []
    def find_spec(self, fullname, path=None, target=None):
        if fullname in blocked:
            self.attempts.append({'fullname': fullname, 'stack': traceback.format_stack()})
            raise AssertionError(f'eager runtime import: {fullname}')
        return None

trap = _Trap()
sys.meta_path.insert(0, trap)
contracts = importlib.import_module('polisyos.scientist.methods.search.contracts')
search = importlib.import_module('polisyos.scientist.methods.search')
autotune = importlib.import_module('polisyos.scientist.methods.autotune')
runtime_module = 'polisyos.scientist.methods.autotune.runtime'
assert runtime_module not in sys.modules
assert contracts.CandidateProposal.__name__ == 'CandidateProposal'
assert contracts.SearchService.__name__ == 'SearchService'
lazy_exports = {
    'polisyos.scientist.methods.search.adversarial': (
        'NegatedCompositeObjective', 'PlatformAttackResult', 'PlatformMetaEvaluationConfig',
        'PlatformMetaEvaluationInput', 'PlatformMetaEvaluationReport', 'PlatformMetaEvaluator',
        'VulnerabilityFound', 'load_platform_meta_evaluation_report',
        'persist_platform_meta_evaluation_report', 'run_stress_test',
    ),
    'polisyos.scientist.methods.search.sensitivity_adapter': (
        'SensitivityAwareCandidateGenerator',
    ),
    'polisyos.scientist.methods.search.cold_start': (
        'BurnInCohort', 'BurnInConfig', 'BurnInRunReport', 'build_default_burn_in_orchestrator',
        'load_burn_in_report', 'persist_burn_in_report', 'run_burn_in',
    ),
    'polisyos.scientist.methods.search.calibration_report': (
        'AcceptanceCriterionStatus', 'FunnelCalibrationReport', 'build_calibration_report',
        'load_funnel_calibration_report', 'persist_funnel_calibration_report',
        'render_calibration_report',
    ),
    'polisyos.scientist.methods.search.strategies': (
        'AcquisitionType', 'BaseSearchStrategy', 'Evaluation', 'EvaluationStatus',
        'GridSearchStrategy', 'ParameterBounds', 'ParameterType', 'PolicyCandidate',
        'RandomSearchStrategy', 'ScalarParameterCodec', 'SearchSpace', 'StrategyAdapter',
        'StrategyState',
    ),
}
assert trap.attempts == []
assert not (blocked & set(sys.modules))
for owner, names in lazy_exports.items():
    assert owner not in sys.modules
    assert all(name in search.__all__ for name in names)
sys.meta_path.remove(trap)
runtime = importlib.import_module(runtime_module)
runtime_exports = (
    'ChampionBackedRuntimeLoader', 'MethodJobBenchmarkEvaluator',
    'PydanticMutationCodec', 'SearchLoopRunner', 'SequenceCandidateGenerator',
    'read_method_job_execution_work_packet', 'seed_loop_baseline',
)
assert all(name in autotune.__all__ for name in runtime_exports)
assert all(getattr(autotune, name) is getattr(runtime, name) for name in runtime_exports)
for owner, names in lazy_exports.items():
    module = importlib.import_module(owner)
    for name in names:
        assert getattr(search, name) is getattr(module, name)
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(source_root), env.get("PYTHONPATH", "")) if value
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_autotune_runtime_export_is_loaded_on_cold_first_use() -> None:
    """Resolve a runtime facade export only on its first access in a fresh process."""
    source_root = Path(__file__).resolve().parents[3] / "src"
    script = """
import importlib
import sys

facade_name = 'polisyos.scientist.methods.autotune'
runtime_name = facade_name + '.runtime'
export_name = 'ChampionBackedRuntimeLoader'
facade = importlib.import_module(facade_name)
assert runtime_name not in sys.modules
assert export_name in facade.__all__
assert export_name not in facade.__dict__
resolved = getattr(facade, export_name)
assert runtime_name in sys.modules
runtime = sys.modules[runtime_name]
assert resolved is runtime.ChampionBackedRuntimeLoader
assert facade.__dict__[export_name] is resolved
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(source_root), env.get("PYTHONPATH", "")) if value
    )
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
