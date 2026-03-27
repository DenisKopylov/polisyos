"""Warm-start bridge for autotune using transfer learning."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .models import BenchmarkEvaluation, BenchmarkSplit, MetricDirection

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from polisyos.scientist.search.strategies.transfer import (
        RunFingerprint,
        TransferLearningManager,
    )
    from polisyos.scientist.search.strategies.types import Evaluation


class WarmStartBridge:
    """Loads historical evaluations from TransferLearningManager for autotune seeding.

    Converts search-strategy ``Evaluation`` objects into
    ``BenchmarkEvaluation`` format suitable for autotune warm-start.
    """

    def __init__(
        self,
        transfer_manager: TransferLearningManager,
        *,
        max_evals: int = 50,
        top_k_runs: int = 5,
    ) -> None:
        self._manager = transfer_manager
        self._max_evals = max_evals
        self._top_k_runs = top_k_runs

    def load_warm_start(
        self,
        fingerprint: RunFingerprint,
    ) -> list[Evaluation]:
        """Find similar runs and retrieve their evaluations for warm-start."""
        similar = self._manager.find_similar_runs(fingerprint, top_k=self._top_k_runs)
        if not similar:
            logger.info("WarmStartBridge: no similar runs found for %s", fingerprint.run_id)
            return []

        evals = self._manager.get_warm_start_evaluations(similar, max_evals=self._max_evals)
        logger.info(
            "WarmStartBridge: loaded %d warm-start evaluations from %d similar runs",
            len(evals),
            len(similar),
        )
        return evals

    @staticmethod
    def evaluations_to_benchmarks(
        evaluations: list[Evaluation],
        *,
        loop_id: str,
        suite_id: str = "warm_start",
        primary_metric: str = "score",
    ) -> list[BenchmarkEvaluation]:
        """Convert search-strategy Evaluations to BenchmarkEvaluations."""
        from polisyos.core.artifacts.manifest import ArtifactRef

        results: list[BenchmarkEvaluation] = []
        for ev in evaluations:
            ref_id = f"sha256:{'0' * 64}"
            ref = ArtifactRef(artifact_id=ref_id, kind="warm_start", media_type="application/json")

            metrics = dict(ev.params) if ev.params else {}
            metrics[primary_metric] = ev.scalar_score

            results.append(
                BenchmarkEvaluation(
                    loop_id=loop_id,
                    suite_id=suite_id,
                    candidate_ref=ref,
                    holdout_metrics=metrics,
                    selection_metrics=metrics,
                    promotable=False,
                    status="warm_start",
                    notes=[f"transferred from {ev.metadata.get('source_run_id', 'unknown')}"],
                    metadata={"warm_start": True, "source_candidate_id": ev.candidate_id},
                )
            )
        return results
