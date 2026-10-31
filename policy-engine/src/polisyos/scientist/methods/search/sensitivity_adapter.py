"""Public search sensitivity adapter module API."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from polisyos.core import artifacts as core_artifacts
    from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits

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
        factor = float(exploration_factor)
        if not math.isfinite(factor) or factor <= 0.0:
            raise ValueError("exploration_factor must be finite and > 0")
        self._base = base_generator
        self._result = sensitivity_result
        self._focus_top_n = focus_top_n
        self._exploration_factor = factor
        self._focus_parameters = set(sensitivity_result.ranking[:focus_top_n])
        self._analysis_ref: core_artifacts.ArtifactRef | None = None

    @classmethod
    def from_artifact(
        cls,
        base_generator: object,
        store: core_artifacts.ArtifactReader,
        ref: core_artifacts.ArtifactRef,
        *,
        focus_top_n: int = 3,
        exploration_factor: float = 1.5,
        read_limits: CoreJsonReadLimits | None = None,
    ) -> SensitivityAwareCandidateGenerator:
        """Reproduce an exact persisted experiment before enriching candidates.

        This supplies an exploratory snapshot only. It neither authenticates the
        evaluator/world nor grants ranking, promotion or publication authority.

        Args:
            base_generator: Existing candidate generator to decorate.
            store: Actual selected-profile Core artifact reader.
            ref: Full selected reference to a stored DOE experiment.
            focus_top_n: Number of reproduced parameter ranks to expose as focus metadata.
            exploration_factor: Positive exploratory metadata value.
            read_limits: Optional explicit resource bounds for artifact admission.

        Returns:
            A candidate-only adapter carrying the reproduced snapshot and exact selector.

        Raises:
            ValueError: Selected bytes, experiment or numerical result do not reconcile.
        """
        from polisyos.scientist.methods.doe._receipt import _load_analysis

        instance = cls(
            base_generator,
            _load_analysis(store, ref, limits=read_limits),
            focus_top_n=focus_top_n,
            exploration_factor=exploration_factor,
        )
        instance._analysis_ref = ref.model_copy(deep=True)
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
            "evaluator_provenance": "not_established",
            "transitive_environment_status": "not_established",
            "source_currentness": "not_established",
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
