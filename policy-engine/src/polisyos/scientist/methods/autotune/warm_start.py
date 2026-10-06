"""Warm-start bridge for autotune using transfer learning."""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from .models import BenchmarkEvaluation, BenchmarkSplit

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from polisyos.scientist.methods.search.strategies.transfer import (
        NumericTransferBasis,
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
        self._last_load_report: dict[str, Any] = {}

    def load_warm_start(
        self,
        fingerprint: RunFingerprint,
    ) -> list[Evaluation]:
        """Find similar runs and retrieve their evaluations for warm-start."""
        similar = self._manager.find_similar_runs(fingerprint, top_k=self._top_k_runs)
        if not similar:
            self._last_load_report = self._manager._report()
            logger.info("WarmStartBridge: no similar runs found for %s", fingerprint.run_id)
            return []

        evals = self._manager.get_warm_start_evaluations(
            similar,
            max_evals=self._max_evals,
            target_fingerprint=fingerprint,
        )
        self._last_load_report = deepcopy(self._manager.last_admission_report)
        logger.info(
            "WarmStartBridge: loaded %d warm-start evaluations from %d similar runs",
            len(evals),
            len(similar),
        )
        return evals

    @property
    def last_load_report(self) -> dict[str, Any]:
        """Keep source-load refusals visible after receiving callbacks run."""
        return deepcopy(self._last_load_report)

    @property
    def last_admission_report(self) -> dict:
        """Expose row refusals from the same canonical admission reader."""
        return self._manager.last_admission_report

    def target_basis(self, fingerprint: RunFingerprint) -> NumericTransferBasis:
        """Read and snapshot the explicit owner-configured numerical target."""
        return self._manager.target_basis(fingerprint)

    def admit_warm_start(
        self, evaluations: list[Evaluation], target_basis: NumericTransferBasis
    ) -> list[Evaluation]:
        """Re-resolve source content for initialization and checkpoint restoration."""
        return self._manager.admit_warm_start(evaluations, target_basis)

    def evaluations_to_benchmarks(
        self,
        evaluations: list[Evaluation],
        *,
        target_basis: NumericTransferBasis,
        loop_id: str,
        suite_id: str = "warm_start",
        primary_metric: str = "score",
    ) -> list[BenchmarkEvaluation]:
        """Rehydrate original measured values without creating promotion evidence."""
        if primary_metric != target_basis.metric:
            raise ValueError("Reverse replay metric disagrees with configured basis")
        results = []
        for evaluation in self.admit_warm_start(evaluations, target_basis):
            original = self._manager._original_benchmark(evaluation, target_basis)
            metadata = dict(original.metadata)
            metadata.update(
                warm_start=True,
                source_candidate_id=evaluation.candidate_id,
                source_run_id=evaluation.metadata.get("source_run_id"),
                provenance_ref=evaluation.provenance_ref,
                source_loop_id=original.loop_id,
                source_suite_id=original.suite_id,
                transfer_history_ref=evaluation.metadata["transfer_history_ref"],
                source_row_index=evaluation.metadata["source_row_index"],
            )
            results.append(
                original.model_copy(
                    deep=True,
                    update={
                        "loop_id": loop_id,
                        "suite_id": suite_id,
                        "holdout_metrics": {},
                        "promotable": False,
                        "status": "warm_start_limited",
                        "runtime_split_type": BenchmarkSplit.SELECTION,
                        "metadata": metadata,
                    },
                )
            )
        return results
