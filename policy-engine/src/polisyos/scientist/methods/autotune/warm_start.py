"""Warm-start bridge for autotune using transfer learning."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from polisyos.scientist.methods.search.objective import OptimizationDirection

from .models import BenchmarkEvaluation

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from polisyos.scientist.methods.search.strategies.transfer import (
        RunFingerprint,
        TransferLearningManager,
    )
    from polisyos.scientist.methods.search.strategies.types import Evaluation


class WarmStartBridge:
    """Loads historical evaluations from TransferLearningManager for autotune seeding.

    The target consumes typed historical ``Evaluation`` records. A fresh
    benchmark measurement belongs to its selected source producer.
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
        eligible_quota: int | None = None,
    ) -> list[Evaluation]:
        """Load indexed evaluations, optionally using an already-resolved source set.

        The manager rechecks the full fingerprint binding before reading each
        selected history, so callers may retain the exact index result and its
        immutable history reference without repeating discovery. An explicit
        ``eligible_quota`` bounds source-eligible rows separately from diagnostics
        within the bridge's total row limit. The target still verifies its own
        admission and compatibility.
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
            eligible_quota=eligible_quota,
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
        """Preserve the legacy entry point with explicit source-bound refusal.

        Raises:
            NotImplementedError: A nonempty history requires an actual selected
                benchmark source for the candidate, suite, and split.
        """
        if evaluations:
            raise NotImplementedError(
                "warm_start_benchmark_source_unestablished: use historical evaluations "
                "or obtain a selected result from the benchmark producer"
            )
        return []
