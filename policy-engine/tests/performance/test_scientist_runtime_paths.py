from __future__ import annotations

import asyncio

import pytest

from polisyos.common.async_tools import run_coro_sync
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.agent.failure_index import FailurePatternIndex, build_failure_signature
from polisyos.scientist.autotune.models import (
    BenchmarkEvaluation,
    MetricDirection,
    PromotionPolicy,
)
from polisyos.scientist.autotune.pareto import ParetoPromoter
from polisyos.scientist.engine.checkpoint import (
    CASCheckpointHook,
    create_checkpoint,
    restore_checkpoint_hook_from_runtime_metadata,
    serialize_checkpoint_hook_runtime_metadata,
)
from polisyos.scientist.engine.executor import WorkflowExecutor
from polisyos.scientist.engine.protocol import NodeOutcome
from polisyos.scientist.engine.runner.serialization import serialize_state
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_branching import branch_state
from polisyos.scientist.engine.state_merge import merge_parallel_outcomes
from polisyos.scientist.llm.gateway_client import (
    GatewayLLMResponse,
    GatewayToolCall,
    GatewayUsage,
)
from polisyos.scientist.llm.prompt_cache import InMemoryPromptCache
from polisyos.scientist.search.controller import SearchConfig, SearchController
from polisyos.scientist.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.search.stopping import MaxIterations
from tests.fixtures.scientist_runtime import (
    build_execution_context,
    build_initial_state,
    build_linear_registry,
    build_linear_workflow_spec,
    default_actual_rows,
)

pytestmark = [pytest.mark.performance, pytest.mark.benchmark]


class _NoopGenerator:
    def generate(self, history, current_best, context):
        del history, current_best, context
        return {"candidate_id": "noop"}


def _build_benchmark_state() -> ExperimentState:
    return ExperimentState(
        run_id="R_bench_state",
        params={
            "phase": "SIMULATION",
            "items": list(range(16)),
            "metrics": {"policy_cost": 100.0, "fairness": 0.02},
        },
    )


def _build_parallel_merge_payload(
) -> tuple[ExperimentState, dict[str, NodeOutcome], dict[str, list[str]]]:
    base_state = ExperimentState(run_id="R_merge", params={"baseline": True})
    outcomes: dict[str, NodeOutcome] = {}
    write_specs: dict[str, list[str]] = {}
    for index in range(12):
        alias = f"branch_{index:02d}"
        outcome_state = base_state.model_copy(deep=True)
        outcome_state.params[f"metric_{index:02d}"] = index
        outcomes[alias] = NodeOutcome(status="ok", state=outcome_state)
        write_specs[alias] = ["params"]
    return base_state, outcomes, write_specs


def _benchmark_eval(seed: int) -> BenchmarkEvaluation:
    return BenchmarkEvaluation(
        loop_id="loop-bench",
        suite_id="suite-bench",
        candidate_ref={
            "artifact_id": f"sha256:{seed:064x}",
            "kind": "scientist.test",
            "media_type": "application/json",
        },
        holdout_metrics={
            "acc": round(0.55 + ((seed * 13) % 40) / 100.0, 4),
            "speed": round(0.25 + ((seed * 7) % 55) / 100.0, 4),
            "fairness": round(0.30 + ((seed * 5) % 45) / 100.0, 4),
        },
        promotable=True,
    )


@pytest.mark.performance
@pytest.mark.benchmark
def test_scientist_node_chain_latency(benchmark, tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    counter = {"run": 0}

    def _run_once() -> str:
        counter["run"] += 1
        run_id = f"R_bench_chain_{counter['run']}"
        ctx, registry_bundle_ref = build_execution_context(store, run_id=run_id)
        state = build_initial_state(
            store,
            run_id=run_id,
            registry_bundle_ref=registry_bundle_ref,
            actual_rows=default_actual_rows(),
        )
        registry, _nodes = build_linear_registry(store)
        result = WorkflowExecutor(ctx, registry).execute(build_linear_workflow_spec(), state)
        return result.report.status

    assert benchmark(_run_once) == "ok"


@pytest.mark.performance
@pytest.mark.benchmark
def test_scientist_checkpoint_io_hot_path(benchmark, tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    state = _build_benchmark_state()
    sequence = {"value": 0}

    def _write_checkpoint() -> str:
        sequence["value"] += 1
        created = create_checkpoint(
            store,
            run_id=state.run_id,
            state=state.model_dump(mode="python", by_alias=True, exclude_none=False),
            sequence_number=sequence["value"],
            completed_node_alias="simulation",
            completed_node_id="scientist.test_simulation@1.0.0",
            completed_nodes=["agent", "search", "simulation"],
            workflow_id="scientist_benchmark",
            workflow_fingerprint="f" * 64,
            fsm_phase="SIMULATION",
            cache_entry_refs=[],
        )
        return str(created.checkpoint_ref.artifact_id)

    assert benchmark(_write_checkpoint).startswith("sha256:")


@pytest.mark.performance
@pytest.mark.benchmark
def test_scientist_async_checkpoint_io_hot_path(benchmark, tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    run_dir = tmp_path / "runs" / "R_bench_async_hook"
    hook = CASCheckpointHook(store=store, run_dir=run_dir, checkpoint_policy="strict")
    state = _build_benchmark_state()
    sequence = {"value": 0}

    def _write_checkpoint_async() -> int:
        async def _exercise() -> int:
            index = sequence["value"]
            sequence["value"] += 1
            result = await hook.on_node_complete_async(
                state=state.model_copy(
                    update={"params": {**state.params, "step": index, "phase": "SIMULATION"}}
                ),
                alias=f"async_{index}",
                node_id=f"scientist.node_async_{index}@1.0.0",
                completed_nodes=[f"async_{item}" for item in range(index + 1)],
                workflow_id="scientist_benchmark",
                workflow_fingerprint="a" * 64,
                cache_entry_ref=None,
            )
            assert result is not None
            return result.sequence_number

        return run_coro_sync(_exercise())

    assert benchmark(_write_checkpoint_async) >= 0


@pytest.mark.performance
def test_scientist_async_checkpoint_io_soak_smoke(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    run_dir = tmp_path / "runs" / "R_async_checkpoint_soak"
    hook = CASCheckpointHook(store=store, run_dir=run_dir, checkpoint_policy="strict")
    state = _build_benchmark_state()

    async def _exercise() -> list[int]:
        sequence_numbers: list[int] = []
        for index in range(64):
            result = await hook.on_node_complete_async(
                state=state.model_copy(
                    update={"params": {**state.params, "step": index, "phase": "SIMULATION"}}
                ),
                alias=f"async_soak_{index}",
                node_id=f"scientist.node_async_soak_{index}@1.0.0",
                completed_nodes=[f"async_soak_{item}" for item in range(index + 1)],
                workflow_id="scientist_benchmark",
                workflow_fingerprint="b" * 64,
                cache_entry_ref=None,
            )
            assert result is not None
            sequence_numbers.append(result.sequence_number)
        return sequence_numbers

    assert run_coro_sync(_exercise()) == list(range(64))


@pytest.mark.performance
def test_scientist_async_checkpoint_restore_cycle_soak_smoke(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    state = _build_benchmark_state()
    current_hook: CASCheckpointHook = CASCheckpointHook(
        store=store,
        run_dir=tmp_path / "runs" / "R_async_checkpoint_restore",
        checkpoint_policy="strict",
    )

    async def _exercise() -> list[int]:
        nonlocal current_hook
        sequence_numbers: list[int] = []
        for index in range(96):
            result = await current_hook.on_node_complete_async(
                state=state.model_copy(
                    update={"params": {**state.params, "step": index, "phase": "SIMULATION"}}
                ),
                alias=f"restore_soak_{index}",
                node_id=f"scientist.node_restore_soak_{index}@1.0.0",
                completed_nodes=[f"restore_soak_{item}" for item in range(index + 1)],
                workflow_id="scientist_benchmark",
                workflow_fingerprint="c" * 64,
                cache_entry_ref=None,
            )
            assert result is not None
            metadata = serialize_checkpoint_hook_runtime_metadata(current_hook)
            assert metadata is not None
            restored = restore_checkpoint_hook_from_runtime_metadata(metadata)
            assert restored is not None
            current_hook = restored
            sequence_numbers.append(result.sequence_number)
        return sequence_numbers

    assert run_coro_sync(_exercise()) == list(range(96))


@pytest.mark.performance
def test_scientist_async_checkpoint_concurrent_restore_cycle_long_soak_smoke(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)

    async def _exercise_run(run_index: int) -> list[int]:
        state = _build_benchmark_state().model_copy(
            update={"run_id": f"R_async_checkpoint_concurrent_{run_index}"}
        )
        current_hook: CASCheckpointHook = CASCheckpointHook(
            store=store,
            run_dir=tmp_path / "runs" / f"R_async_checkpoint_concurrent_{run_index}",
            checkpoint_policy="strict",
        )
        sequence_numbers: list[int] = []
        for index in range(72):
            result = await current_hook.on_node_complete_async(
                state=state.model_copy(
                    update={
                        "params": {
                            **state.params,
                            "step": index,
                            "phase": "SIMULATION",
                            "run_index": run_index,
                        }
                    }
                ),
                alias=f"concurrent_restore_{run_index}_{index}",
                node_id=f"scientist.node_concurrent_restore_{run_index}_{index}@1.0.0",
                completed_nodes=[
                    f"concurrent_restore_{run_index}_{item}"
                    for item in range(index + 1)
                ],
                workflow_id="scientist_benchmark",
                workflow_fingerprint=f"{run_index:x}".rjust(64, "d"),
                cache_entry_ref=None,
            )
            assert result is not None
            metadata = serialize_checkpoint_hook_runtime_metadata(current_hook)
            assert metadata is not None
            restored = restore_checkpoint_hook_from_runtime_metadata(metadata)
            assert restored is not None
            current_hook = restored
            sequence_numbers.append(result.sequence_number)
        return sequence_numbers

    async def _exercise() -> list[list[int]]:
        return await asyncio.gather(*(_exercise_run(index) for index in range(4)))

    results = run_coro_sync(_exercise(), timeout_seconds=120)
    assert results == [list(range(72)) for _ in range(4)]


@pytest.mark.performance
@pytest.mark.benchmark
def test_scientist_state_serialization_hot_path(benchmark) -> None:
    state = _build_benchmark_state()

    payload = benchmark(lambda: serialize_state(state))

    assert isinstance(payload, bytes)
    assert payload


@pytest.mark.performance
@pytest.mark.benchmark
def test_scientist_state_branch_hot_path(benchmark) -> None:
    state = _build_benchmark_state()

    cloned = benchmark(
        lambda: branch_state(
            state,
            write_paths=("params.metrics.policy_cost", "artifacts_index.result_ref"),
        ).state
    )

    assert cloned.run_id == state.run_id
    assert cloned.params is not state.params


@pytest.mark.performance
@pytest.mark.benchmark
def test_scientist_fan_out_merge_hot_path(benchmark) -> None:
    base_state, outcomes, write_specs = _build_parallel_merge_payload()

    result = benchmark(
        lambda: merge_parallel_outcomes(base_state, outcomes, write_specs),
    )

    assert result.applied is True
    assert len(result.applied_paths) == 12


@pytest.mark.performance
@pytest.mark.benchmark
def test_scientist_failure_index_search_hot_path(benchmark) -> None:
    index = FailurePatternIndex()
    for idx in range(400):
        index.add_failure(
            signature_id=build_failure_signature(
                error_code=f"ERR_{idx % 8}",
                category="feasibility",
                location=f"policy_spec.interventions[{idx % 5}].target",
                message=f"Target matches {idx % 3} agents",
                source_step="critic",
                domain="fiscal",
            ),
            error_code=f"ERR_{idx % 8}",
            category="feasibility",
            domain="fiscal",
            source_step="critic",
            normalized_location="policy_spec.interventions[].target",
            normalized_message="target matches <n> agents",
            remediation_advice="Broaden selector",
            card_ref=f"sha256:{idx:064d}",
        )

    results = benchmark(
        lambda: index.search(
            domain="fiscal",
            error_code="ERR_2",
            category="feasibility",
            location="policy_spec.interventions[9].target",
            message="Target matches 2 agents",
            min_occurrence=3,
        )
    )

    assert results


@pytest.mark.performance
@pytest.mark.benchmark
def test_scientist_search_pareto_hot_path(benchmark) -> None:
    config = SearchConfig(
        stopping=MaxIterations(2),
        objective=object(),  # type: ignore[arg-type]
    )
    controller = SearchController(
        config,
        candidate_generator=_NoopGenerator(),
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=lambda candidate, context: {"objective": 0.0},
    )
    controller._pareto_front = []
    for idx in range(64):
        controller._update_pareto_front(
            {"candidate_id": f"seed-{idx}"},
            [
                ObjectiveValue(
                    name="policy_cost",
                    raw_value=float(idx % 11),
                    direction=OptimizationDirection.MINIMIZE,
                ),
                ObjectiveValue(
                    name="benefit",
                    raw_value=float(100 - (idx % 17)),
                    direction=OptimizationDirection.MAXIMIZE,
                ),
            ],
        )
    counter = {"value": 0}

    def _update_once() -> int:
        counter["value"] += 1
        controller._update_pareto_front(
            {"candidate_id": f"bench-{counter['value']}"},
            [
                ObjectiveValue(
                    name="policy_cost",
                    raw_value=float(counter["value"] % 13),
                    direction=OptimizationDirection.MINIMIZE,
                ),
                ObjectiveValue(
                    name="benefit",
                    raw_value=float(120 - (counter["value"] % 19)),
                    direction=OptimizationDirection.MAXIMIZE,
                ),
            ],
        )
        return len(controller._pareto_front)

    assert benchmark(_update_once) >= 1


@pytest.mark.performance
@pytest.mark.benchmark
def test_scientist_autotune_pareto_front_hot_path(benchmark) -> None:
    promoter = ParetoPromoter(
        [
            PromotionPolicy(
                loop_id="loop-bench",
                primary_metric="acc",
                direction=MetricDirection.MAXIMIZE,
            ),
            PromotionPolicy(
                loop_id="loop-bench",
                primary_metric="speed",
                direction=MetricDirection.MAXIMIZE,
            ),
            PromotionPolicy(
                loop_id="loop-bench",
                primary_metric="fairness",
                direction=MetricDirection.MAXIMIZE,
            ),
        ]
    )
    evaluations = [_benchmark_eval(index) for index in range(256)]

    front = benchmark(lambda: promoter.compute_front(evaluations))

    assert front.size >= 1
    assert front.hypervolume >= 0.0


@pytest.mark.performance
@pytest.mark.benchmark
def test_scientist_prompt_cache_hit_hot_path(benchmark) -> None:
    cache = InMemoryPromptCache(maxsize=16, default_ttl_s=3600)
    cache.put(
        "resp",
        GatewayLLMResponse(
            content="cached",
            usage=GatewayUsage(prompt_tokens=12, completion_tokens=8, total_tokens=20),
            raw={"nested": [{"value": "cached"}], "labels": ["a", "b", "c"]},
            tool_calls=[
                GatewayToolCall(
                    id="call_1",
                    name="lookup",
                    arguments={"items": ["alpha", "beta"]},
                    error_envelope={"warnings": ["none"]},
                )
            ],
        ),
    )

    cached = benchmark(lambda: cache.get("resp"))

    assert cached is not None
    assert cached.content == "cached"
