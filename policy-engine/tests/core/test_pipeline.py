from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import pytest

from polisyos.core.pipeline import DagPipeline, LinearPipeline, PipelineCycleError


@dataclass
class _LinearStage:
    name: str
    weight: int
    delta: int


def test_linear_pipeline_sorts_and_short_circuits() -> None:
    pipeline = LinearPipeline(
        [
            _LinearStage(name="slow", weight=100, delta=3),
            _LinearStage(name="fast", weight=1, delta=1),
            _LinearStage(name="medium", weight=10, delta=2),
        ],
        stage_id=lambda stage: stage.name,
    )

    run = pipeline.run(
        initial_state=0,
        stage_ids=["slow", "fast", "medium"],
        sort_key=lambda stage: stage.weight,
        run_stage=lambda stage, state: state + stage.delta,
        stop_after=lambda _stage, state: state >= 3,
    )

    assert run.short_circuited is True
    assert run.executed_stage_ids == ["fast", "medium"]
    assert run.state == 3


def test_linear_pipeline_ignores_missing_stage_ids_by_default() -> None:
    pipeline = LinearPipeline(
        [_LinearStage(name="a", weight=1, delta=1)],
        stage_id=lambda stage: stage.name,
    )

    selected = pipeline.select(["a", "missing"])
    assert [stage.name for stage in selected] == ["a"]

    run = pipeline.run(
        initial_state=0,
        stage_ids=["a", "missing"],
        run_stage=lambda stage, state: state + stage.delta,
    )
    assert run.state == 1
    assert run.executed_stage_ids == ["a"]


def test_dag_pipeline_compile_and_execute_in_topological_order() -> None:
    pipeline = DagPipeline[str](auto_chain=False)
    pipeline.add_stage("extract", name="extract")
    pipeline.add_stage("validate", name="validate", depends_on=["extract"])
    pipeline.add_stage("load", name="load", depends_on=["validate"])

    compiled = pipeline.compile()
    assert compiled.execution_order == ["extract", "validate", "load"]

    run = compiled.run(
        initial_state=[],
        run_stage=lambda stage, state: [*state, stage.name],
    )
    assert run.executed_stage_ids == ["extract", "validate", "load"]
    assert run.state == ["extract", "validate", "load"]


def test_dag_pipeline_cycle_detection() -> None:
    pipeline = DagPipeline[str](auto_chain=False)
    pipeline.add_stage("a", name="a")
    pipeline.add_stage("b", name="b", depends_on=["a"])
    pipeline.add_edge("b", "a")

    with pytest.raises(PipelineCycleError, match="contains cycles"):
        pipeline.compile()


def test_dag_pipeline_branching_is_thread_safe() -> None:
    pipeline = DagPipeline[str](auto_chain=True)
    pipeline.add_stage("root", name="root")

    def _build_branch(prefix: str):
        def _builder(local_pipeline: DagPipeline[str]) -> None:
            local_pipeline.add_stage(f"{prefix}.1", name=f"{prefix}.1")
            time.sleep(0.01)
            local_pipeline.add_stage(f"{prefix}.2", name=f"{prefix}.2")

        return _builder

    threads = [
        threading.Thread(
            target=lambda: pipeline.branch(_build_branch("left"), depends_on=["root"])
        ),
        threading.Thread(
            target=lambda: pipeline.branch(_build_branch("right"), depends_on=["root"])
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    compiled = pipeline.compile()
    stages = {stage.name: stage for stage in compiled.stages}
    assert stages["left.1"].dependencies == ("root",)
    assert stages["left.2"].dependencies == ("left.1",)
    assert stages["right.1"].dependencies == ("root",)
    assert stages["right.2"].dependencies == ("right.1",)
