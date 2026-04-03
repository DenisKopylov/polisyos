"""Public pipeline linear module API."""
from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Any, Generic, TypeVar

from .base import DuplicateStageError, PipelineRun, StageExecutionError, UnknownStageError

StageT = TypeVar("StageT")
StateT = TypeVar("StateT")


class LinearPipeline(Generic[StageT]):
    """
    Generic linear pipeline orchestrator.

    The class stores named stages and executes them in a selected order with
    optional sorting, error handling, and short-circuiting.
    """

    def __init__(
        self,
        stages: Sequence[StageT] | None = None,
        *,
        stage_id: Callable[[StageT], str],
    ) -> None:
        self._stage_id = stage_id
        self._stages: dict[str, StageT] = {}
        for stage in stages or []:
            self.add_stage(stage)

    def add_stage(self, stage: StageT, *, override: bool = False) -> str:
        stage_name = self._stage_id(stage)
        if stage_name in self._stages and not override:
            raise DuplicateStageError(f"Stage '{stage_name}' already exists")
        self._stages[stage_name] = stage
        return stage_name

    def remove_stage(self, stage_id: str) -> StageT | None:
        return self._stages.pop(stage_id, None)

    def get_stage(self, stage_id: str) -> StageT | None:
        return self._stages.get(stage_id)

    def stage_ids(self) -> list[str]:
        return list(self._stages.keys())

    def select(
        self,
        stage_ids: Iterable[str] | None = None,
        *,
        sort_key: Callable[[StageT], Any] | None = None,
        strict: bool = False,
    ) -> list[StageT]:
        if stage_ids is None:
            selected = list(self._stages.values())
        else:
            selected: list[StageT] = []
            missing: list[str] = []
            for stage_id in stage_ids:
                stage = self._stages.get(stage_id)
                if stage is None:
                    missing.append(stage_id)
                    continue
                selected.append(stage)
            if strict and missing:
                raise UnknownStageError(
                    f"Unknown stage ids: {sorted(set(missing))}. "
                    f"Available: {self.stage_ids()}"
                )

        if sort_key is not None:
            return sorted(selected, key=sort_key)
        return selected

    def run(
        self,
        *,
        initial_state: StateT,
        run_stage: Callable[[StageT, StateT], StateT],
        stage_ids: Iterable[str] | None = None,
        sort_key: Callable[[StageT], Any] | None = None,
        strict_stage_ids: bool = False,
        on_stage_error: Callable[[StageT, Exception, StateT], StateT] | None = None,
        stop_after: Callable[[StageT, StateT], bool] | None = None,
    ) -> PipelineRun[StateT]:
        selected = self.select(stage_ids, sort_key=sort_key, strict=strict_stage_ids)
        state = initial_state
        executed: list[str] = []

        for stage in selected:
            stage_name = self._stage_id(stage)
            try:
                state = run_stage(stage, state)
            except Exception as exc:
                if on_stage_error is None:
                    raise StageExecutionError(stage_id=stage_name, cause=exc) from exc
                state = on_stage_error(stage, exc, state)
            executed.append(stage_name)

            if stop_after is not None and stop_after(stage, state):
                return PipelineRun(
                    state=state,
                    executed_stage_ids=executed,
                    short_circuited=True,
                )

        return PipelineRun(state=state, executed_stage_ids=executed, short_circuited=False)
