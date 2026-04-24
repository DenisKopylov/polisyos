"""Cross-run transfer learning for search strategies.

Finds similar past runs via vector similarity and extracts warm-start
evaluations for new searches.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.search.strategies.types import Evaluation

if TYPE_CHECKING:
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.scientist.agent.vector_memory import VectorMemoryStore

logger = logging.getLogger(__name__)


class RunFingerprint(BaseModel):
    """Identifies a search run for cross-run transfer matching."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    space_hash: str
    objective_names: list[str]
    embedding: list[float] = Field(default_factory=list)
    best_params: dict[str, Any] | None = None
    best_score: float | None = None
    num_evaluations: int = 0


class TransferLearningManager:
    """Finds similar past runs and extracts warm-start data.

    Uses a ``VectorMemoryStore`` to index run configurations by their
    embeddings.  When a new search starts, the manager finds the most
    similar historical runs and retrieves their evaluations for warm-start.

    Parameters
    ----------
    store:
        Artifact store for persisting evaluation histories.
    index:
        Vector memory store for run similarity search.
    """

    def __init__(self, store: ArtifactStore, index: VectorMemoryStore) -> None:
        self._store = store
        self._index = index
        self._eval_cache: dict[str, list[dict[str, Any]]] = {}

    def register_run(
        self,
        fingerprint: RunFingerprint,
        evaluations: list[Evaluation],
    ) -> ArtifactRef | None:
        """Register a completed run for future transfer.

        Stores the evaluations in the artifact store and indexes the
        run fingerprint for similarity search.
        """
        from polisyos.core.artifacts.store import PutOptions

        if not evaluations:
            return None

        # Persist evaluations
        eval_dicts = [
            {
                "candidate_id": e.candidate_id,
                "params": e.params,
                "params_normalized": list(e.params_normalized) if e.params_normalized else [],
                "scalar_score": e.scalar_score,
                "stage_a_passed": e.stage_a_passed,
                "status": e.status.value if hasattr(e.status, "value") else str(e.status),
            }
            for e in evaluations
            if e.is_valid
        ]

        if not eval_dicts:
            return None

        ref = self._store.put_json(
            {
                "run_id": fingerprint.run_id,
                "space_hash": fingerprint.space_hash,
                "objective_names": fingerprint.objective_names,
                "evaluations": eval_dicts,
                "best_score": fingerprint.best_score,
                "num_evaluations": fingerprint.num_evaluations,
            },
            PutOptions(
                kind="search.transfer.history",
                media_type="application/json",
            ),
        )

        # Index the run in vector memory
        if fingerprint.embedding:
            self._index.add(
                key=fingerprint.run_id,
                embedding=fingerprint.embedding,
                metadata={
                    "space_hash": fingerprint.space_hash,
                    "objective_names": fingerprint.objective_names,
                    "best_score": fingerprint.best_score,
                    "artifact_id": ref.artifact_id,
                },
            )

        return ref

    def find_similar_runs(
        self,
        fingerprint: RunFingerprint,
        top_k: int = 5,
    ) -> list[RunFingerprint]:
        """Find the most similar past runs based on embedding similarity.

        Returns up to ``top_k`` fingerprints, sorted by similarity (most
        similar first).  Only returns runs with the same objective names.
        """
        if not fingerprint.embedding:
            return []

        results = self._index.query(fingerprint.embedding, top_k=top_k * 2)
        similar: list[RunFingerprint] = []

        for key, distance, meta in results:
            if key == fingerprint.run_id:
                continue
            # Filter by matching objectives
            obj_names = meta.get("objective_names", [])
            if set(obj_names) != set(fingerprint.objective_names):
                continue
            similar.append(
                RunFingerprint(
                    run_id=key,
                    space_hash=meta.get("space_hash", ""),
                    objective_names=obj_names,
                    best_score=meta.get("best_score"),
                )
            )
            if len(similar) >= top_k:
                break

        return similar

    def get_warm_start_evaluations(
        self,
        similar_runs: list[RunFingerprint],
        max_evals: int = 50,
    ) -> list[Evaluation]:
        """Retrieve evaluations from similar runs for warm-start.

        Collects the best evaluations from each similar run, up to
        ``max_evals`` total.
        """
        from polisyos.scientist.search.objective import ObjectiveValue
        from polisyos.scientist.search.strategies.types import EvaluationStatus

        all_evals: list[Evaluation] = []
        per_run = max(1, max_evals // max(len(similar_runs), 1))

        for fp in similar_runs:
            evals = self._load_run_evaluations(fp.run_id)
            # Sort by score descending and take top-k
            evals.sort(key=lambda e: e.get("scalar_score", 0), reverse=True)

            for e_dict in evals[:per_run]:
                try:
                    eval_obj = Evaluation(
                        candidate_id=e_dict.get("candidate_id", "transfer"),
                        params=e_dict.get("params", {}),
                        params_normalized=tuple(e_dict.get("params_normalized", [])),
                        objectives=[
                            ObjectiveValue(name="transferred", value=e_dict.get("scalar_score", 0))
                        ],
                        scalar_score=e_dict.get("scalar_score", 0),
                        stage_a_passed=True,
                        status=EvaluationStatus.SUCCESS,
                        metadata={"source_run_id": fp.run_id},
                    )
                    all_evals.append(eval_obj)
                except Exception:
                    continue

            if len(all_evals) >= max_evals:
                break

        return all_evals[:max_evals]

    def _load_run_evaluations(self, run_id: str) -> list[dict[str, Any]]:
        """Load persisted evaluations for a run."""
        if run_id in self._eval_cache:
            return self._eval_cache[run_id]

        # Find the artifact via vector memory metadata
        results = self._index.query(
            [0.0] * self._index.dim,
            top_k=1000,
        )
        for key, _, meta in results:
            if key == run_id and "artifact_id" in meta:
                try:
                    import json as _json

                    data = _json.loads(self._store.get_bytes(meta["artifact_id"]))
                    evals = data.get("evaluations", [])
                    self._eval_cache[run_id] = evals
                    return evals
                except Exception:
                    pass
        return []
