from __future__ import annotations

import graphlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from .base import (
    DuplicateStageError,
    PipelineCycleError,
    PipelineRun,
    StageExecutionError,
    UnknownStageError,
)

StageT = TypeVar("StageT")
StateT = TypeVar("StateT")


@dataclass(slots=True)
class DagStage(Generic[StageT]):
    """A named stage with explicit DAG dependencies."""

    name: str
    stage: StageT
    dependencies: tuple[str, ...]
    order_index: int


@dataclass(slots=True)
class CompiledDagPipeline(Generic[StageT]):
    """A topologically ordered DAG ready for execution."""

    stages: list[DagStage[StageT]]
    execution_order: list[str]

    def run(
        self,
        *,
        initial_state: StateT,
        run_stage: Callable[[DagStage[StageT], StateT], StateT],
        on_stage_error: Callable[[DagStage[StageT], Exception, StateT], StateT] | None = None,
        stop_after: Callable[[DagStage[StageT], StateT], bool] | None = None,
    ) -> PipelineRun[StateT]:
        state = initial_state
        executed: list[str] = []

        for stage in self.stages:
            try:
                state = run_stage(stage, state)
            except Exception as exc:
                if on_stage_error is None:
                    raise StageExecutionError(stage_id=stage.name, cause=exc) from exc
                state = on_stage_error(stage, exc, state)
            executed.append(stage.name)

            if stop_after is not None and stop_after(stage, state):
                return PipelineRun(
                    state=state,
                    executed_stage_ids=executed,
                    short_circuited=True,
                )

        return PipelineRun(state=state, executed_stage_ids=executed, short_circuited=False)


class DagPipeline(Generic[StageT]):
    """
    Generic DAG pipeline builder.

    Supports both stage registration (`add_stage`) and low-level graph
    mutations (`add_node`/`add_edge`) for compatibility with legacy callers.
    """

    def __init__(
        self,
        *,
        auto_chain: bool = True,
        name_factory: Callable[[StageT, int], str] | None = None,
    ) -> None:
        self._auto_chain = auto_chain
        self._name_factory = name_factory
        self._deps: dict[str, list[str]] = {}
        self._stages: dict[str, DagStage[StageT]] = {}
        self._tail: list[str] = []

    def _build_stage_name(self, stage: StageT, *, index: int) -> str:
        if self._name_factory is not None:
            return self._name_factory(stage, index)
        return f"stage_{index}"

    def add_node(self, name: str) -> None:
        if name not in self._deps:
            self._deps[name] = []

    def add_edge(self, dependency: str, node: str) -> None:
        if node not in self._deps:
            self._deps[node] = []
        self._deps[node].append(dependency)

    def has_node(self, name: str) -> bool:
        return name in self._deps

    def nodes(self) -> list[str]:
        return list(self._deps.keys())

    def add_stage(
        self,
        stage: StageT,
        *,
        name: str | None = None,
        depends_on: Sequence[str] | None = None,
    ) -> DagStage[StageT]:
        stage_name = name or self._build_stage_name(stage, index=len(self._stages))
        if self.has_node(stage_name):
            raise DuplicateStageError(f"Stage '{stage_name}' already exists")

        if depends_on is None:
            if self._auto_chain and self._tail:
                resolved_dependencies = list(self._tail)
            else:
                resolved_dependencies = []
        else:
            resolved_dependencies = list(depends_on)

        missing = [dep for dep in resolved_dependencies if dep not in self._deps]
        if missing:
            raise UnknownStageError(
                f"Dependency '{missing[0]}' not found. Available stages: {self.nodes()}"
            )

        dag_stage = DagStage(
            name=stage_name,
            stage=stage,
            dependencies=tuple(resolved_dependencies),
            order_index=len(self._stages),
        )
        self._stages[stage_name] = dag_stage
        self.add_node(stage_name)
        for dep in resolved_dependencies:
            self.add_edge(dep, stage_name)
        self._tail = [stage_name]
        return dag_stage

    def branch(
        self,
        builder: Callable[[DagPipeline[StageT]], object],
        *,
        depends_on: Sequence[str] | None = None,
    ) -> list[str]:
        start = list(depends_on) if depends_on is not None else list(self._tail)
        original_tail = list(self._tail)
        self._tail = start
        builder(self)
        branch_tail = list(self._tail)
        self._tail = original_tail
        return branch_tail

    def fork(
        self,
        builders: Sequence[Callable[[DagPipeline[StageT]], object]],
        *,
        depends_on: Sequence[str] | None = None,
    ) -> list[str]:
        tails: list[str] = []
        for builder in builders:
            tails.extend(self.branch(builder, depends_on=depends_on))
        return tails

    def join(
        self,
        stage: StageT,
        *,
        name: str | None = None,
        depends_on: Sequence[str] | None = None,
    ) -> DagStage[StageT]:
        return self.add_stage(stage, name=name, depends_on=depends_on)

    def topological_sort(self) -> list[str]:
        try:
            sorter = graphlib.TopologicalSorter(self._deps)
            return list(sorter.static_order())
        except graphlib.CycleError as exc:
            cycle = exc.args[1] if len(exc.args) > 1 else []
            raise PipelineCycleError(
                f"Pipeline contains cycles: {cycle}. Pipeline must be a directed acyclic graph."
            ) from exc

    def compile(self) -> CompiledDagPipeline[StageT]:
        execution_order = self.topological_sort()
        ordered_stages: list[DagStage[StageT]] = []
        for stage_name in execution_order:
            stage = self._stages.get(stage_name)
            if stage is None:
                raise UnknownStageError(
                    f"Node '{stage_name}' has no registered stage payload. "
                    "Use add_stage() for executable nodes."
                )
            ordered_stages.append(stage)
        return CompiledDagPipeline(stages=ordered_stages, execution_order=execution_order)
