"""Warm-start bridge for autotune using transfer learning."""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from .models import BenchmarkEvaluation, BenchmarkSplit

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
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
        store: ArtifactStore | None = None,
    ) -> list[BenchmarkEvaluation]:
        """Return resolved original selection benchmarks as limited historical views.

        The target loop is recorded as intent. Original loop/suite identity and
        measurements remain attached to their source; no copied score creates a
        new benchmark. An absent source lineage is an explicit refusal.
        """
        from polisyos.core.canon import from_canonical_bytes
        from polisyos.scientist.methods.search.strategies.transfer import (
            TransferHistoryError,
            TransferLearningManager,
        )

        results: list[BenchmarkEvaluation] = []
        for ev in evaluations:
            if store is None or not ev.provenance_ref:
                raise TransferHistoryError("Original benchmark store/reference required")
            try:
                original = BenchmarkEvaluation.model_validate(
                    from_canonical_bytes(store.get_bytes(ev.provenance_ref))
                )
                candidate_payload = from_canonical_bytes(
                    store.get_bytes(original.candidate_ref.artifact_id)
                )
            except (TypeError, ValueError, OSError, KeyError) as exc:
                raise TransferHistoryError(
                    "Original benchmark/candidate unavailable or schema-incompatible",
                    ev.provenance_ref,
                ) from exc
            rejection = TransferLearningManager._candidate_parameter_rejection(
                candidate_payload, ev.params
            )
            if rejection is not None:
                raise TransferHistoryError(rejection, str(original.candidate_ref.artifact_id))
            if (
                not ev.is_valid
                or original.metadata.get("warm_start")
                or not original.matches_runtime_split(BenchmarkSplit.SELECTION)
                or str(original.candidate_ref.artifact_id) != ev.candidate_id
                or primary_metric not in original.selection_metrics
                or original.metadata.get("params") != ev.params
            ):
                raise TransferHistoryError(
                    "Original benchmark identity, split or parameters differ", ev.provenance_ref
                )

            metrics: dict[str, float] = {}
            directions: dict[str, str] = {}
            for objective in ev.objectives:
                if not math.isfinite(objective.raw_value):
                    continue
                metrics[objective.name] = objective.raw_value
                directions[objective.name] = objective.direction.value
            if primary_metric not in metrics:
                raise TransferHistoryError(
                    "Transferred record lacks the measured primary objective", ev.provenance_ref
                )
            if any(
                original.selection_metrics.get(name) != value for name, value in metrics.items()
            ):
                raise TransferHistoryError(
                    "Original benchmark measurements differ", ev.provenance_ref
                )
            source_directions = original.metadata.get("directions")
            if not isinstance(source_directions, dict) or any(
                source_directions.get(name) != direction
                for name, direction in directions.items()
            ):
                raise TransferHistoryError(
                    "Original benchmark directions differ", ev.provenance_ref
                )

            source_run_id = ev.metadata.get("source_run_id", "unknown")
            metadata = {
                **original.metadata,
                "warm_start": True,
                "target_loop_id": loop_id,
                "requested_suite_id": suite_id,
                "source_benchmark_ref": ev.provenance_ref,
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
                original.model_copy(
                    update={
                        "promotable": False,
                        "status": "warm_start_limited",
                        "notes": [*original.notes, f"historical view from {source_run_id}"],
                        "metadata": metadata,
                    },
                    deep=True,
                )
            )
        return results
