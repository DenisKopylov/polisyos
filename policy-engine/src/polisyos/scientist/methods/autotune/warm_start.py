"""Warm-start bridge for autotune using transfer learning."""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from .models import BenchmarkEvaluation, BenchmarkSplit

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from polisyos.scientist.methods.search.strategies.transfer import (
        RunFingerprint,
        TransferLearningManager,
    )
    from polisyos.scientist.methods.search.strategies.types import Evaluation


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

        evals = self._manager.get_warm_start_evaluations(
            similar,
            max_evals=self._max_evals,
            target_fingerprint=fingerprint,
        )
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
            try:
                ref = ArtifactRef(
                    artifact_id=ev.candidate_id,
                    kind="search.candidate",
                    media_type="application/json",
                )
            except (TypeError, ValueError) as exc:
                logger.warning(
                    "WarmStartBridge: skipping candidate without an artifact reference %s: %s",
                    ev.candidate_id,
                    exc,
                )
                continue

            metrics: dict[str, float] = {}
            directions: dict[str, str] = {}
            for objective in ev.objectives:
                if not math.isfinite(objective.raw_value):
                    continue
                metrics[objective.name] = objective.raw_value
                directions[objective.name] = objective.direction.value
            if primary_metric not in metrics:
                logger.warning(
                    "WarmStartBridge: skipping candidate %s without measured %s",
                    ev.candidate_id,
                    primary_metric,
                )
                continue

            source_run_id = ev.metadata.get("source_run_id", "unknown")
            metadata = {
                "warm_start": True,
                "source_candidate_id": ev.candidate_id,
                "params": dict(ev.params),
                "directions": directions,
                "direction": directions[primary_metric],
            }
            if source_run_id != "unknown":
                metadata["source_run_id"] = source_run_id
            if ev.provenance_ref is not None:
                metadata["provenance_ref"] = ev.provenance_ref

            results.append(
                BenchmarkEvaluation(
                    loop_id=loop_id,
                    suite_id=suite_id,
                    candidate_ref=ref,
                    selection_metrics=metrics,
                    holdout_metrics={},
                    promotable=False,
                    status="warm_start_limited",
                    notes=[f"transferred from {source_run_id}"],
                    runtime_split_type=BenchmarkSplit.SELECTION,
                    metadata=metadata,
                )
            )
        return results
