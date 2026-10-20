"""Warm-start bridge for autotune using transfer learning."""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from polisyos.scientist.methods.search.objective import (
    OptimizationDirection,
    _evaluation_matches_selected_objectives,
)

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
        *,
        similar_runs: list[RunFingerprint] | None = None,
    ) -> list[Evaluation]:
        """Load indexed evaluations, optionally using an already-resolved source set.

        The manager rechecks the full fingerprint binding before reading each
        selected history, so callers may retain the exact index result and its
        immutable history reference without repeating discovery.
        """
        similar = (
            self._manager.find_similar_runs(fingerprint, top_k=self._top_k_runs)
            if similar_runs is None
            else similar_runs
        )
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
        objective_direction: OptimizationDirection | None = None,
        objective_rule_spec: str | None = None,
    ) -> list[BenchmarkEvaluation]:
        """Convert only evaluations recomputed under the supplied selected rule."""
        from polisyos.core.artifacts.manifest import ArtifactRef

        results: list[BenchmarkEvaluation] = []
        if objective_direction is None or not objective_rule_spec:
            return results
        for ev in evaluations:
            if not _evaluation_matches_selected_objectives(
                ev,
                objective_names=[primary_metric],
                objective_directions={primary_metric: objective_direction},
                objective_rule_specs={primary_metric: objective_rule_spec},
                require_scalar_score=True,
            ):
                logger.warning(
                    "WarmStartBridge: skipping candidate %s with unreconciled %s basis",
                    getattr(ev, "candidate_id", "unknown"),
                    primary_metric,
                )
                continue
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

            selected = next(
                objective for objective in ev.objectives if objective.name == primary_metric
            )
            metrics = {primary_metric: selected.raw_value}
            directions = {primary_metric: selected.direction.value}
            if not math.isfinite(selected.raw_value):
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
