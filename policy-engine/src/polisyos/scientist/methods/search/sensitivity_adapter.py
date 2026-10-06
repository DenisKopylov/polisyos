"""Public search sensitivity adapter module API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactRef, ArtifactStore

from polisyos.scientist.methods.doe.designs import SensitivityResult
from polisyos.scientist.methods.search.controller import SearchIteration


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
        self._analysis_ref: ArtifactRef | None = None

    @classmethod
    def from_artifact(
        cls,
        base_generator: object,
        store: ArtifactStore,
        ref: ArtifactRef,
        *,
        focus_top_n: int = 3,
        exploration_factor: float = 1.5,
    ) -> SensitivityAwareCandidateGenerator:
        """Reproduce a persisted exploratory analysis before using its ranking."""
        from polisyos.scientist.methods.doe._receipt import _load_analysis

        instance = cls(
            base_generator,
            _load_analysis(store, ref),
            focus_top_n=focus_top_n,
            exploration_factor=exploration_factor,
        )
        instance._analysis_ref = ref
        return instance

    def _metadata(self) -> dict[str, Any]:
        return {
            "ranking": list(self._result.ranking),
            "focus_parameters": sorted(self._focus_parameters),
            "exploration_factor": self._exploration_factor,
            "method": self._result.method.value,
            "design_id": self._result.metadata.get("design_id"),
            "analysis_id": self._result.metadata.get("analysis_id"),
            "analysis_ref": (
                self._analysis_ref.model_dump(mode="json") if self._analysis_ref else None
            ),
            "authority_purpose": "exploratory_parameter_experiment",
            "population_law_status": "not_established",
        }

    def generate(
        self,
        history: list[SearchIteration],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        candidate = self._base.generate(history, current_best, context)
        candidate = dict(candidate)
        candidate["_sensitivity"] = self._metadata()
        return candidate

    def generate_batch(
        self,
        history: list[SearchIteration],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
        batch_size: int,
    ) -> list[dict[str, Any]]:
        if hasattr(self._base, "generate_batch") and callable(self._base.generate_batch):
            batch = self._base.generate_batch(history, current_best, context, batch_size)
        else:
            batch = [self._base.generate(history, current_best, context) for _ in range(batch_size)]
        return [
            {
                **dict(candidate),
                "_sensitivity": self._metadata(),
            }
            for candidate in batch
        ]
