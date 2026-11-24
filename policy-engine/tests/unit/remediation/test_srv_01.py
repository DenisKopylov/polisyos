"""Regression witnesses for the SRV-01 search contract extraction."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.scientist.methods.search import transfer_context
from polisyos.scientist.methods.search.adapters import LegacySearchServiceAdapter
from polisyos.scientist.methods.search.contracts import (
    CandidateProposal,
    EvaluationBundle,
    SearchStatus,
)
from polisyos.scientist.methods.search.controller import (
    SearchConfig,
    SearchController,
    TracedLLMCandidateGenerator,
)
from polisyos.scientist.methods.search.frontier import materialize_candidate_proposal
from polisyos.scientist.methods.search.objective import (
    BudgetDeficitObjective,
    CompositeObjective,
    ObjectiveValue,
)
from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry
from polisyos.scientist.methods.search.stopping import MaxIterations
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector


def _budget_deficit_source(value: float) -> dict[str, Any]:
    return {
        "budget_deficit": value,
        "metric_units": {"budget_deficit": "EUR"},
    }


def _budget_deficit_evaluation(value: float, *, policy_evaluation: Any = None) -> EvaluationBundle:
    return EvaluationBundle(
        objective_value=value,
        is_promising=True,
        stage_b_result={"simulation_results": _budget_deficit_source(value)},
        policy_evaluation=policy_evaluation,
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
    pareto_registry: ParetoRegistry | None = None,
) -> tuple[LegacySearchServiceAdapter, _Generator]:
    generator = _Generator()
    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(max_iterations),
            objective=CompositeObjective([BudgetDeficitObjective(expected_unit="EUR")]),
            enable_stage_a=enable_stage_a,
            pareto_registry=pareto_registry,
        ),
        candidate_generator=generator,
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": _budget_deficit_source(float(candidate.get("x", 1.0))),
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
        _budget_deficit_evaluation(2.0),
    )

    assert first_result.history_length == 1
    assert first_result.best_candidate == first[0].payload
    assert first_result.best_objective == 2.0
    assert first_result.frontier_delta

    second = adapter.ask(goal=None, search_space=None, context={})
    second_result = adapter.tell(
        second[0].candidate_id,
        _budget_deficit_evaluation(1.0),
    )

    assert second_result.history_length == 2
    assert second_result.best_candidate == second[0].payload
    assert second_result.best_objective == 1.0
    assert first_result.best_candidate == first[0].payload


def test_explicit_ask_goal_and_space_reach_the_traced_producer_and_selected_record() -> None:
    class PromptClient:
        def __init__(self) -> None:
            self.contexts: list[dict[str, Any]] = []

        async def generate(self, **kwargs: Any) -> Any:
            wire = kwargs["user"].partition("Search inputs JSON:\n")[2]
            context = json.loads(wire)["context"]
            self.contexts.append(context)
            bound = context["goal"]["choose"] if "goal" in context else None
            x = context["search_space"]["x"][bound] if bound is not None else 7
            return SimpleNamespace(content=json.dumps({"x": x}))

    client = PromptClient()
    controller = SearchController(
        SearchConfig(
            MaxIterations(4), CompositeObjective([BudgetDeficitObjective(expected_unit="EUR")])
        ),
        candidate_generator=TracedLLMCandidateGenerator(
            client=client,  # type: ignore[arg-type]
            system_prompt="Choose the requested endpoint in the search bounds.",
        ),
        stage_a_evaluator=lambda *_: (0.0, True),
        stage_b_evaluator=lambda *_: {},
    )
    adapter = LegacySearchServiceAdapter(controller)
    context = {"subject": "fiscal"}
    first_goal = {"choose": "minimum"}
    first_space = {"x": {"minimum": 2, "maximum": 3}}
    second_goal = {"choose": "maximum"}
    second_space = {"x": {"minimum": 8, "maximum": 9}}

    with pytest.raises(ValueError, match="search_ask_goal_conflict"):
        adapter.ask(first_goal, first_space, {**context, "goal": second_goal})
    with pytest.raises(ValueError, match="search_ask_search_space_invalid"):
        adapter.ask(first_goal, {"x": {"minimum": float("nan")}}, context)
    with pytest.raises(ValueError, match="search_ask_goal_conflict"):
        adapter.ask({"choose": 1}, first_space, {**context, "goal": {"choose": True}})
    assert controller._status is SearchStatus.NOT_STARTED and client.contexts == []

    first = adapter.ask(first_goal, first_space, context)[0]
    assert materialize_candidate_proposal(first) == {"x": 2}
    assert first.service_request is not None and first.service_request.goal is not None
    first.service_request.goal["choose"] = "outside"
    first_goal["choose"] = "outside"
    first_space["x"]["minimum"] = 99
    first_result = adapter.tell(first.candidate_id, _budget_deficit_evaluation(2))
    assert first_result.best_candidate == {"x": 2}
    first_record = controller._history[-1].candidate_proposal
    assert first_record is not None and first_record.service_request is not None
    restored = CandidateProposal.model_validate_json(first_record.model_dump_json())
    assert restored.service_request is not None
    assert restored.service_request.model_dump(exclude_none=True) == {
        "goal": {"choose": "minimum"},
        "search_space": {"x": {"minimum": 2, "maximum": 3}},
    }
    unbound = restored.model_copy(update={"metadata": {}, "service_iteration": None})
    with pytest.raises(ValueError, match="candidate_service_request_unbound"):
        materialize_candidate_proposal(unbound)

    second = adapter.ask(second_goal, second_space, context)[0]
    assert materialize_candidate_proposal(second) == {"x": 9}
    second_result = adapter.tell(second.candidate_id, _budget_deficit_evaluation(9))
    assert second_result.history_length == 2 and second_result.best_candidate == {"x": 2}
    assert client.contexts[0]["goal"] == {"choose": "minimum"}
    assert client.contexts[0]["search_space"] == {"x": {"minimum": 2, "maximum": 3}}
    assert client.contexts[1]["goal"] == second_goal
    assert client.contexts[1]["search_space"] == second_space

    ordinary = adapter.ask(None, None, context)[0]
    assert materialize_candidate_proposal(ordinary) == {"x": 7}
    assert "service_request" not in ordinary.model_dump()
    assert "goal" not in client.contexts[2] and "search_space" not in client.contexts[2]
    assert context == {"subject": "fiscal"}


def test_explicit_ask_refuses_a_generator_without_a_declared_context_profile() -> None:
    adapter, generator = _build_adapter()
    with pytest.raises(ValueError, match="search_ask_explicit_request_unsupported"):
        adapter.ask({"choose": "minimum"}, {"x": {"minimum": 2}}, {})
    assert generator.calls == 0 and adapter.controller._status is SearchStatus.NOT_STARTED


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
        _budget_deficit_evaluation(100.0, policy_evaluation={"unexpected": "typed payload"}),
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


def test_prior_generation_tell_leaves_replacement_run_unchanged() -> None:
    adapter, _ = _build_adapter(max_iterations=1)
    prior = adapter.ask(goal=None, search_space=None, context={})[0]
    prior_state = adapter.owner._run_state
    prior_id = prior_state.search_id
    prior_generation = getattr(adapter.owner, "_run_generation", 0)

    finished = adapter.controller.run({}, {"candidate_id": "replacement", "x": 3.0})
    current = adapter.owner._run_state
    assert current.search_id != prior_id

    with pytest.raises(ValueError, match="stale search generation"):
        adapter.tell(prior.candidate_id, EvaluationBundle(objective_value=1.0, is_promising=True))

    assert adapter.owner._run_generation > prior_generation > 0
    assert adapter.owner._run_state is current
    assert [row.candidate["candidate_id"] for row in current.history] == ["replacement"]
    assert current.stage_b_evaluations == 1
    assert prior_state.history == []
    assert [row.candidate["candidate_id"] for row in finished.history] == ["replacement"]


def test_refused_full_run_keeps_same_generation_pending() -> None:
    adapter, _ = _build_adapter(max_iterations=1)
    pending = adapter.ask(goal=None, search_space=None, context={})[0]
    prior_state = adapter.owner._run_state

    assert adapter.owner._run_lock.acquire(blocking=False)
    try:
        with pytest.raises(RuntimeError, match="not reentrant"):
            adapter.run_search(initial_context={})
    finally:
        adapter.owner._run_lock.release()

    accepted = adapter.tell(
        pending.candidate_id, EvaluationBundle(objective_value=1.0, is_promising=True)
    )
    assert adapter.owner._run_state is prior_state
    assert accepted.registry_update["search_id"] == prior_state.search_id
    assert accepted.history_length == 1


def test_same_adapter_cannot_reissue_ambiguous_bare_candidate_id() -> None:
    adapter, generator = _build_adapter(max_iterations=1)
    old = adapter.ask(goal=None, search_space=None, context={})[0]
    result = adapter.run_search(
        initial_context={}, initial_candidate={"candidate_id": "replacement", "x": 3.0}
    )
    generator.calls = 0

    with pytest.raises(ValueError, match="candidate ID was issued in an earlier search generation"):
        adapter.ask(goal=None, search_space=None, context={})
    with pytest.raises(ValueError, match="stale search generation"):
        adapter.tell(old.candidate_id, EvaluationBundle(objective_value=1.0, is_promising=True))

    fresh_adapter = LegacySearchServiceAdapter(adapter.controller)
    generator.calls = 0
    fresh = fresh_adapter.ask(goal=None, search_space=None, context={})[0]
    assert fresh.candidate_id == old.candidate_id
    assert fresh.payload == old.payload
    accepted = fresh_adapter.tell(
        fresh.candidate_id, EvaluationBundle(objective_value=1.0, is_promising=True)
    )
    assert accepted.registry_update["search_id"] == result.search_id
    assert accepted.history_length == 2
    assert len(result.history) == 1


def test_same_candidate_overlapping_tell_is_refused_before_owner_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, _ = _build_adapter()
    candidate = adapter.ask(goal=None, search_space=None, context={})[0]
    evaluation = _budget_deficit_evaluation(2.0)
    entered = Event()
    release = Event()
    evaluate = BudgetDeficitObjective.evaluate

    def pause_first(self: BudgetDeficitObjective, results: dict[str, Any]) -> ObjectiveValue:
        if not entered.is_set():
            lock = adapter.controller._lifecycle_owner._run_lock
            assert lock.acquire(blocking=False)
            lock.release()
            entered.set()
            assert release.wait(5)
        return evaluate(self, results)

    monkeypatch.setattr(BudgetDeficitObjective, "evaluate", pause_first)
    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(adapter.tell, candidate.candidate_id, evaluation)
        try:
            assert entered.wait(5)
            with pytest.raises(RuntimeError, match="in flight"):
                adapter.tell(candidate.candidate_id, evaluation)
            with pytest.raises(RuntimeError, match="not reentrant"):
                adapter.controller.run({}, {"candidate_id": "replacement", "x": 3.0})
            assert adapter.owner._run_state.history == []
        finally:
            release.set()
        accepted = first.result(timeout=5)

    with pytest.raises(ValueError, match="duplicate search evaluation"):
        adapter.tell(candidate.candidate_id, evaluation)
    assert accepted.history_length == 1
    assert adapter.owner._run_state.stage_b_evaluations == 1


def test_reentrant_tell_from_objective_is_refused_before_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, _ = _build_adapter()
    candidate = adapter.ask(goal=None, search_space=None, context={})[0]
    evaluation = _budget_deficit_evaluation(2.0)
    evaluate = BudgetDeficitObjective.evaluate
    attempted = False

    def reenter_once(self: BudgetDeficitObjective, results: dict[str, Any]) -> ObjectiveValue:
        nonlocal attempted
        if not attempted:
            attempted = True
            with pytest.raises(RuntimeError, match="in flight"):
                adapter.tell(candidate.candidate_id, evaluation)
            assert adapter.owner._run_state.history == []
        return evaluate(self, results)

    monkeypatch.setattr(BudgetDeficitObjective, "evaluate", reenter_once)

    accepted = adapter.tell(candidate.candidate_id, evaluation)
    assert attempted
    assert accepted.history_length == 1
    assert adapter.owner._run_state.stage_b_evaluations == 1


def test_precommit_failure_can_retry_after_later_candidate_completes() -> None:
    adapter, _ = _build_adapter()
    first = adapter.ask(goal=None, search_space=None, context={})[0]
    second = adapter.ask(goal=None, search_space=None, context={})[0]
    evaluation = _budget_deficit_evaluation(2.0)

    with pytest.raises(TypeError, match="simulation_results must be a mapping"):
        adapter.tell(
            first.candidate_id,
            EvaluationBundle(
                objective_value=2.0,
                is_promising=True,
                stage_b_result={"simulation_results": []},
            ),
        )

    assert adapter.owner._run_state.history == []
    later = adapter.tell(second.candidate_id, evaluation)
    earlier = adapter.tell(first.candidate_id, evaluation)

    assert later.history_length == 1
    assert earlier.history_length == 2
    assert [row.candidate["candidate_id"] for row in adapter.owner._run_state.history] == [
        second.candidate_id,
        first.candidate_id,
    ]
    assert later.registry_update["search_id"] == earlier.registry_update["search_id"]


def test_same_adapter_rolls_over_generated_ids_without_changing_subject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, generator = _build_adapter(max_iterations=1)
    monkeypatch.setattr(generator, "generate", lambda history, current_best, context: {"x": 1.0})
    old = adapter.ask(goal=None, search_space=None, context={})[0]
    assert old.candidate_id == "candidate_0_0"
    next_generation = adapter.controller._lifecycle_owner._run_generation + 1
    occupied_id = f"{old.candidate_id}_run_{next_generation}"
    with monkeypatch.context() as explicit_generator:
        explicit_generator.setattr(
            generator,
            "generate",
            lambda history, current_best, context: {"candidate_id": occupied_id, "x": 2.0},
        )
        assert adapter.ask(goal=None, search_space=None, context={})[0].candidate_id == occupied_id

    result = adapter.run_search(
        initial_context={}, initial_candidate={"candidate_id": "replacement", "x": 3.0}
    )
    new = adapter.ask(goal=None, search_space=None, context={})[0]
    assert new.candidate_id not in {old.candidate_id, occupied_id}
    assert new.payload == old.payload == {"x": 1.0}
    assert new.service_iteration == old.service_iteration == 0
    with pytest.raises(ValueError, match="stale search generation"):
        adapter.tell(old.candidate_id, _budget_deficit_evaluation(1.0))

    accepted = adapter.tell(new.candidate_id, _budget_deficit_evaluation(1.0))
    assert accepted.registry_update["search_id"] == result.search_id
    assert accepted.history_length == 2
    assert accepted.best_candidate == new.payload
    assert result.best_objective == 3.0
    assert len(result.history) == 1


def test_failed_prepublication_resolution_leaves_service_evaluation_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = ParetoRegistry(root=tmp_path)
    adapter, _ = _build_adapter(pareto_registry=registry)
    owner = adapter.controller._lifecycle_owner
    proposal = adapter.ask(goal=None, search_space=None, context={})[0]
    evaluation = _budget_deficit_evaluation(
        2.0, policy_evaluation=PolicyEvaluationVector(candidate_id=proposal.candidate_id)
    )

    def fail_context_resolution(**_: Any) -> None:
        raise RuntimeError("transfer context unavailable")

    with monkeypatch.context() as faults:
        faults.setattr(transfer_context, "resolve_transfer_context", fail_context_resolution)
        with pytest.raises(RuntimeError, match="transfer context unavailable"):
            adapter.tell(proposal.candidate_id, evaluation)

    assert not ParetoRegistry(root=tmp_path).get_snapshot(owner._run_state.search_id).entries
    assert owner._run_state.history == []
    accepted = adapter.tell(proposal.candidate_id, evaluation)
    assert accepted.history_length == 1
    assert accepted.best_candidate is None
    assert owner._run_state.history[0].policy_evaluation_status == "source_unverified"
    reader = ParetoRegistry(root=tmp_path)
    saved = list(reader.get_snapshot(owner._run_state.search_id).entries.values())
    assert len(saved) == 1
    assert saved[0].seed_only
    assert saved[0].seed_payload == proposal.payload


def test_partial_registry_publication_cannot_replay_the_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = ParetoRegistry(root=tmp_path)
    adapter, _ = _build_adapter(pareto_registry=registry)
    owner = adapter.controller._lifecycle_owner
    proposal = adapter.ask(goal=None, search_space=None, context={})[0]
    evaluation = _budget_deficit_evaluation(
        2.0, policy_evaluation=PolicyEvaluationVector(candidate_id=proposal.candidate_id)
    )
    publish_attempts: list[str] = []

    def interrupt_transfer_publish(loop_id: str, **_: Any) -> None:
        publish_attempts.append(loop_id)
        raise OSError("transfer publication interrupted")

    monkeypatch.setattr(registry, "publish_transfer_surface", interrupt_transfer_publish)
    run_id = owner._run_state.search_id
    with pytest.raises(OSError, match="transfer publication interrupted"):
        adapter.tell(proposal.candidate_id, evaluation)

    reader = ParetoRegistry(root=tmp_path)
    saved = list(reader.get_snapshot(run_id).entries.values())
    assert len(saved) == 1
    assert saved[0].seed_only
    assert saved[0].seed_payload == proposal.payload
    with pytest.raises(RuntimeError, match="publication is unconfirmed"):
        adapter.tell(proposal.candidate_id, evaluation)

    assert publish_attempts == [run_id]
    assert list(reader.get_snapshot(run_id).entries.values()) == saved
    assert owner._run_state.history == []
    assert owner._run_state.stage_b_evaluations == 0
    assert owner._run_state.best_candidate is None
    assert owner._run_state.pareto_front == []


def test_reply_failure_after_commit_cannot_replay_the_evaluation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, _ = _build_adapter()
    owner = adapter.controller._lifecycle_owner
    proposal = adapter.ask(goal=None, search_space=None, context={})[0]
    evaluation = _budget_deficit_evaluation(2.0)

    def fail_reply() -> None:
        raise RuntimeError("reply snapshot unavailable")

    with monkeypatch.context() as faults:
        faults.setattr(owner, "_service_tell_snapshot", fail_reply)
        with pytest.raises(RuntimeError, match="reply snapshot unavailable"):
            adapter.tell(proposal.candidate_id, evaluation)

    with pytest.raises(ValueError, match="duplicate search evaluation"):
        adapter.tell(proposal.candidate_id, evaluation)
    assert owner._run_state.history_size == owner._run_state.stage_b_evaluations == 1
    assert owner._run_state.best_candidate == proposal.payload
    assert owner._run_state.best_objective == 2.0
