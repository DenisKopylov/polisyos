from __future__ import annotations

from typing import Any

from polisyos.scientist.doe.designs import SensitivityResult
from polisyos.scientist.search.controller import SearchIteration


class SensitivityAwareCandidateGenerator:
    """
    Candidate generator decorator that injects sensitivity priors.

    The adapter is intentionally non-invasive: it does not alter the base generator
    protocol and only enriches the candidate payload with metadata consumed downstream.
    """

    def __init__(
        self,
        base_generator: object,
        sensitivity_result: SensitivityResult,
        *,
        focus_top_n: int = 3,
        exploration_factor: float = 1.5,
    ):
        if focus_top_n < 1:
            raise ValueError("focus_top_n must be >= 1")
        if exploration_factor <= 0.0:
            raise ValueError("exploration_factor must be > 0")
        self._base = base_generator
        self._result = sensitivity_result
        self._focus_top_n = focus_top_n
        self._exploration_factor = float(exploration_factor)
        self._focus_parameters = set(sensitivity_result.ranking[:focus_top_n])

    def generate(
        self,
        history: list[SearchIteration],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        candidate = self._base.generate(history, current_best, context)
        candidate = dict(candidate)
        candidate["_sensitivity"] = {
            "ranking": list(self._result.ranking),
            "focus_parameters": sorted(self._focus_parameters),
            "exploration_factor": self._exploration_factor,
            "method": self._result.method.value,
        }
        return candidate

    def generate_batch(
        self,
        history: list[SearchIteration],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
        batch_size: int,
    ) -> list[dict[str, Any]]:
        if hasattr(self._base, "generate_batch") and callable(getattr(self._base, "generate_batch")):
            batch = getattr(self._base, "generate_batch")(history, current_best, context, batch_size)
        else:
            batch = [self._base.generate(history, current_best, context) for _ in range(batch_size)]
        return [
            {
                **dict(candidate),
                "_sensitivity": {
                    "ranking": list(self._result.ranking),
                    "focus_parameters": sorted(self._focus_parameters),
                    "exploration_factor": self._exploration_factor,
                    "method": self._result.method.value,
                },
            }
            for candidate in batch
        ]

