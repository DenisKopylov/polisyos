"""Adapter bridging SearchStrategy and SearchController CandidateGenerator protocol."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from polisyos.scientist.methods.search.controller import SearchIteration
from polisyos.scientist.methods.search.objective import ObjectiveValue
from polisyos.scientist.methods.search.strategies.base import SearchStrategy
from polisyos.scientist.methods.search.strategies.codec import ParameterCodec, ScalarParameterCodec
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    Evaluation,
    EvaluationStatus,
)


class StrategyAdapter:
    """
    Adapts `SearchStrategy` to `CandidateGenerator` protocol.

    Supports both single-candidate (`generate`) and batch (`generate_batch`) flows.
    """

    def __init__(
        self,
        strategy: SearchStrategy,
        space: SearchSpace,
        codec: ParameterCodec | None = None,
        objective_extractor: Callable[[SearchIteration], list[ObjectiveValue]] | None = None,
    ):
        self._strategy = strategy
        self._space = space
        self._codec = codec or ScalarParameterCodec()
        self._objective_extractor = objective_extractor or (
            lambda iteration: list(iteration.objective_details)
        )
        self._evaluations: list[Evaluation] = []
        self._synced_len = 0

    def generate(
        self,
        history: list[SearchIteration],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        del current_best
        self._sync_history(history)
        candidate = self._strategy.suggest(self._evaluations)
        return self._candidate_to_payload(candidate, context=context)

    def generate_batch(
        self,
        history: list[SearchIteration],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
        batch_size: int,
    ) -> list[dict[str, Any]]:
        del current_best
        self._sync_history(history)
        candidates = self._strategy.suggest_batch(self._evaluations, batch_size=batch_size)
        return [self._candidate_to_payload(candidate, context=context) for candidate in candidates]

    def _sync_history(self, history: list[SearchIteration]) -> None:
        if self._synced_len > len(history):
            self._evaluations = []
            self._synced_len = 0

        for iteration in history[self._synced_len :]:
            evaluation = self._to_evaluation(iteration)
            self._evaluations.append(evaluation)
            self._strategy.update(evaluation)
        self._synced_len = len(history)

    def _to_evaluation(self, iteration: SearchIteration) -> Evaluation:
        params = self._codec.encode(iteration.candidate)
        normalized = self._space.normalize(params)

        if not iteration.stage_a_passed:
            status = EvaluationStatus.STAGE_A_REJECT
        elif iteration.stage_b_result is None:
            status = EvaluationStatus.STAGE_B_ERROR
        else:
            status = EvaluationStatus.SUCCESS

        return Evaluation(
            candidate_id=f"iter_{iteration.iteration}",
            params=params,
            params_normalized=normalized,
            objectives=self._objective_extractor(iteration),
            scalar_score=float(iteration.objective_value),
            stage_a_passed=iteration.stage_a_passed,
            stage_b_result=iteration.stage_b_result,
            status=status,
            timestamp=iteration.timestamp,
            wall_time_seconds=iteration.duration_seconds,
        )

    def _candidate_to_payload(self, candidate, context: dict[str, Any]) -> dict[str, Any]:
        payload = self._codec.decode(
            candidate.params,
            context=context,
            template=context.get("candidate_template") if isinstance(context, dict) else None,
        )
        payload.setdefault("semantic", candidate.semantic)
        payload["_strategy_metadata"] = {
            "candidate_id": candidate.candidate_id,
            "acquisition_value": candidate.acquisition_value,
            "predicted_mean": candidate.predicted_mean,
            "predicted_std": candidate.predicted_std,
            "source": candidate.source_strategy,
            **candidate.metadata,
        }
        return payload
