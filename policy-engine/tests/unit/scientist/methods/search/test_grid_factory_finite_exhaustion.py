"""Actual configured finite Grid factory, pending subject and exhausted fresh view."""

from dataclasses import replace

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    load_model_artifact,
)
from polisyos.scientist.methods.search.strategies.adapter import StrategyAdapter
from polisyos.scientist.methods.search.strategies.codec import ScalarParameterCodec
from polisyos.scientist.methods.search.strategies.grid import GridSearchStrategy
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    ParameterBounds,
    ParameterType,
)
from tests.unit.scientist.methods.search.test_service_persistence import _runner


def _finite_factory(root):
    runner, store, registry, suite, evaluator, spec = _runner(root)
    space = SearchSpace([ParameterBounds("value", 1, 4, ParameterType.INTEGER)])
    generator = StrategyAdapter(
        GridSearchStrategy(space, seed=11, points_per_dim=4, max_candidates=4),
        space,
        ScalarParameterCodec(parameter_paths={"value": "value"}),
    )
    spec = replace(spec, candidate_generator=generator)
    service = runner.create_service(spec, suite_ref=suite, max_iterations=10)
    # This is the actual declared product batch policy, bound in the native
    # checkpoint configuration. It does not limit processes or test workers.
    service.controller._config.batch_size = 3
    return service, store, registry, suite, evaluator


def test_actual_finite_grid_factory_retains_short_last_batch_and_exhausted_fresh_resume(
    tmp_path,
):
    source, store, _, _, first_evaluator = _finite_factory(tmp_path)
    batch = source.ask(None, None, {})
    assert [item.payload["value"] for item in batch] == [1, 2, 3]
    assert len(source._pending_candidates) == 3
    for iteration, proposal in enumerate(batch):
        actual = source.controller._evaluate_for_tell(
            proposal.payload, iteration=iteration, context={}
        )
        source.tell(proposal.candidate_id, actual)
    assert [row.candidate["value"] for row in source.controller._history] == [1, 2, 3]
    assert len(source._completed_candidate_ids) == 3 and source._pending_candidates == {}
    assert first_evaluator.calls == [1, 2, 1, 3, 2]
    # The existing adaptive policy may request more than three after cheap
    # evaluations; the native Grid must retain its one remaining physical row.
    remaining = source.ask(None, None, {})
    assert [item.payload["value"] for item in remaining] == [4]
    assert len(source._pending_candidates) == 1
    adapter = source.controller._generator
    assert adapter._strategy.get_state().metadata["cursor"] == 4
    assert adapter._synced_len == 3
    pending_ref = source.checkpoint_ref
    pending_bytes = store.get_bytes(pending_ref)

    fresh, fresh_store, fresh_registry, _, fresh_evaluator = _finite_factory(tmp_path)
    fresh.restore(pending_ref, context={})
    assert fresh._pending_candidates == source._pending_candidates
    assert fresh._completed_candidate_ids == source._completed_candidate_ids
    assert fresh.controller._generator._strategy.get_state().metadata["cursor"] == 4
    result = fresh.resume_search(context={})
    assert fresh_evaluator.calls == [4, 3]
    assert [row.candidate["value"] for row in result.history] == [1, 2, 3, 4]
    assert result.iterations_completed == result.stage_b_evaluations == 4
    assert result.best_candidate["value"] == 4
    assert result.stopping_reason == "generation_exhausted"
    assert result.telemetry["generation_transition"]["kind"] == "exhausted"
    assert fresh.controller._run_state.empty_generation_attempts == 3
    assert len(fresh._completed_candidate_ids) == 4 and fresh._pending_candidates == {}
    assert fresh.controller._generator._strategy.get_state().metadata["cursor"] == 4
    assert fresh_registry.get("resume").metrics == {"score": 4.0}
    assert fresh_store.get_bytes(pending_ref) == pending_bytes
    for row in result.history:
        ref = ArtifactRef.model_validate(
            row.stage_b_result["simulation_results"]["evaluation_artifact_ref"]
        )
        evaluation = load_model_artifact(fresh_store, ref, BenchmarkEvaluation)
        assert evaluation.holdout_metrics == {"score": float(row.candidate["value"])}
    terminal_ref = ArtifactRef.model_validate(result.telemetry["checkpoint_ref"])
    terminal, _, _, _, terminal_evaluator = _finite_factory(tmp_path)
    terminal.restore(terminal_ref, context={})
    observed = terminal.resume_search(context={})
    assert observed.history == result.history and observed.pareto_front == result.pareto_front
    assert observed.best_candidate == result.best_candidate
    assert observed.stopping_reason == "generation_exhausted"
    assert terminal._completed_candidate_ids == fresh._completed_candidate_ids
    assert terminal._pending_candidates == {} and terminal_evaluator.calls == []
