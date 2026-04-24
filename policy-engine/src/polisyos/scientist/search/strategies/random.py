"""Uniform-random search baseline."""

from __future__ import annotations

from polisyos.scientist.search.strategies.base import BaseSearchStrategy
from polisyos.scientist.search.strategies.types import Evaluation, PolicyCandidate


class RandomSearchStrategy(BaseSearchStrategy):
    """Simple random exploration baseline."""

    def suggest(
        self,
        evaluations: list[Evaluation],
        pending: list[PolicyCandidate] | None = None,
    ) -> PolicyCandidate:
        del pending
        self._iteration = len(evaluations)
        return self._random_candidate(source="random")
