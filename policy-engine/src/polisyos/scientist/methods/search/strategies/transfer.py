"""Cross-run transfer learning for search strategies.

Finds similar past runs via vector similarity and extracts warm-start
evaluations for new searches.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.strategies.types import Evaluation, EvaluationStatus

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.scientist.agent.vector_memory import VectorMemoryStore

logger = logging.getLogger(__name__)


class RunFingerprint(BaseModel):
    """Identifies a search run for cross-run transfer matching."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    space_hash: str = Field(..., min_length=1)
    objective_names: list[str]
    bounds: dict[str, Any] = Field(default_factory=dict)
    split: str | None = None
    units: dict[str, Any] = Field(default_factory=dict)
    origin: str | None = None
    tenant_id: str | None = None
    objective_directions: dict[str, str] = Field(default_factory=dict)
    embedding: list[float] = Field(default_factory=list)
    best_params: dict[str, Any] | None = None
    best_score: float | None = None
    num_evaluations: int = 0
    history_ref: ArtifactRef | None = None


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
        eval_dicts = [self._serialize_evaluation(e) for e in evaluations if e.is_valid]

        if not eval_dicts:
            return None

        ref = self._store.put_json(
            {
                "run_id": fingerprint.run_id,
                "space_hash": fingerprint.space_hash,
                "objective_names": fingerprint.objective_names,
                "bounds": fingerprint.bounds,
                "split": fingerprint.split,
                "units": fingerprint.units,
                "origin": fingerprint.origin,
                "tenant_id": fingerprint.tenant_id,
                "objective_directions": fingerprint.objective_directions,
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
                    "bounds": fingerprint.bounds,
                    "split": fingerprint.split,
                    "units": fingerprint.units,
                    "origin": fingerprint.origin,
                    "tenant_id": fingerprint.tenant_id,
                    "objective_directions": fingerprint.objective_directions,
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

        for key, _, meta in results:
            if key == fingerprint.run_id:
                continue
            history_ref = self._history_ref_from_metadata(meta)
            if history_ref is None:
                logger.warning("Skipping run %s without a valid history ArtifactRef", key)
                continue
            # Similarity is discovery only; numeric reuse requires full binding.
            obj_names = meta.get("objective_names", [])
            if set(obj_names) != set(fingerprint.objective_names):
                continue
            if meta.get("space_hash") != fingerprint.space_hash:
                continue
            if not self._binding_matches(
                fingerprint,
                RunFingerprint(
                    run_id=key,
                    space_hash=meta.get("space_hash", ""),
                    objective_names=obj_names,
                    bounds=meta.get("bounds", {}),
                    split=meta.get("split"),
                    units=meta.get("units", {}),
                    origin=meta.get("origin"),
                    tenant_id=meta.get("tenant_id"),
                    objective_directions=meta.get("objective_directions", {}),
                    best_score=meta.get("best_score"),
                    history_ref=history_ref,
                ),
            ):
                continue
            similar.append(
                RunFingerprint(
                    run_id=key,
                    space_hash=meta.get("space_hash", ""),
                    objective_names=obj_names,
                    bounds=meta.get("bounds", {}),
                    split=meta.get("split"),
                    units=meta.get("units", {}),
                    origin=meta.get("origin"),
                    tenant_id=meta.get("tenant_id"),
                    objective_directions=meta.get("objective_directions", {}),
                    best_score=meta.get("best_score"),
                    history_ref=history_ref,
                )
            )
            if len(similar) >= top_k:
                break

        return similar

    def get_warm_start_evaluations(
        self,
        similar_runs: list[RunFingerprint],
        max_evals: int = 50,
        *,
        target_fingerprint: RunFingerprint | None = None,
    ) -> list[Evaluation]:
        """Retrieve evaluations from similar runs for warm-start.

        Collects the best evaluations from each similar run, up to
        ``max_evals`` total.
        """
        if max_evals <= 0 or not similar_runs:
            return []

        prepared: list[list[Evaluation]] = []
        for fp in similar_runs:
            if target_fingerprint is not None and not self._binding_matches(
                target_fingerprint, fp
            ):
                continue

            rows = self._load_run_evaluations(fp)
            evaluations = [self._deserialize_evaluation(row, fp.run_id) for row in rows]
            evaluations.sort(key=self._evaluation_sort_key)
            if evaluations:
                prepared.append(evaluations)

        # Give every compatible source its first observation, then redistribute
        # the remaining capacity round-robin.  This avoids the old floor quota
        # dropping unused capacity from short histories while retaining source
        # diversity for the initial warm-start corpus.
        all_evals: list[Evaluation] = []
        offsets = [0] * len(prepared)
        while len(all_evals) < max_evals:
            progressed = False
            for index, evaluations in enumerate(prepared):
                offset = offsets[index]
                if offset >= len(evaluations):
                    continue
                all_evals.append(evaluations[offset])
                offsets[index] += 1
                progressed = True
                if len(all_evals) >= max_evals:
                    break
            if not progressed:
                break

        return all_evals

    @staticmethod
    def _serialize_evaluation(evaluation: Evaluation) -> dict[str, Any]:
        """Persist the typed evaluation fields needed for faithful rehydration."""
        return {
            "candidate_id": evaluation.candidate_id,
            "params": dict(evaluation.params),
            "params_normalized": list(evaluation.params_normalized),
            "objectives": [
                {
                    "name": objective.name,
                    "raw_value": objective.raw_value,
                    "direction": objective.direction.value,
                    "weight": objective.weight,
                    "is_satisfied": objective.is_satisfied,
                    "threshold": objective.threshold,
                }
                for objective in evaluation.objectives
            ],
            "scalar_score": evaluation.scalar_score,
            "stage_a_passed": evaluation.stage_a_passed,
            "stage_b_result": evaluation.stage_b_result,
            "status": evaluation.status.value,
            "timestamp": evaluation.timestamp.isoformat(),
            "wall_time_seconds": evaluation.wall_time_seconds,
            "provenance_ref": evaluation.provenance_ref,
            "metadata": dict(evaluation.metadata),
        }

    @staticmethod
    def _binding_matches(target: RunFingerprint, source: RunFingerprint) -> bool:
        """Return whether source observations are numerically reusable for target."""
        return (
            bool(target.space_hash)
            and target.space_hash == source.space_hash
            and set(target.objective_names) == set(source.objective_names)
            and target.bounds == source.bounds
            and target.split == source.split
            and target.units == source.units
            and target.origin == source.origin
            and target.tenant_id == source.tenant_id
            and target.objective_directions == source.objective_directions
        )

    @staticmethod
    def _history_ref_from_metadata(meta: dict[str, Any]) -> ArtifactRef | None:
        """Convert indexed history metadata into a typed immutable reference."""
        artifact_id = meta.get("artifact_id")
        if artifact_id is None:
            return None
        try:
            return ArtifactRef(
                artifact_id=artifact_id,
                kind="search.transfer.history",
                media_type="application/json",
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _evaluation_sort_key(evaluation: Evaluation) -> tuple[int, float]:
        """Sort valid normalized scores first; retain rejected rows for visibility."""
        if not evaluation.is_valid or not math.isfinite(evaluation.scalar_score):
            return (1, 0.0)
        return (0, evaluation.scalar_score)

    @classmethod
    def _deserialize_evaluation(cls, row: dict[str, Any], run_id: str) -> Evaluation:
        """Rehydrate one row, returning a visible rejection for malformed data."""
        candidate_id = str(row.get("candidate_id", "transfer"))
        source_metadata = row.get("metadata", {})
        metadata = dict(source_metadata) if isinstance(source_metadata, dict) else {}
        metadata.setdefault("source_run_id", run_id)
        metadata.setdefault("source_candidate_id", candidate_id)
        provenance_ref = row.get("provenance_ref")

        try:
            params = row.get("params", {})
            if not isinstance(params, dict):
                raise TypeError("params must be an object")
            objectives_payload = row["objectives"]
            if not isinstance(objectives_payload, list) or not objectives_payload:
                raise ValueError("objectives must be a non-empty list")
            objectives = [cls._deserialize_objective(payload) for payload in objectives_payload]
            scalar_score = float(row["scalar_score"])
            if not math.isfinite(scalar_score):
                raise ValueError("scalar_score must be finite")
            status = EvaluationStatus(row.get("status", EvaluationStatus.SUCCESS.value))
            normalized = row.get("params_normalized", [])
            if not isinstance(normalized, (list, tuple)):
                raise TypeError("params_normalized must be a list or tuple")
            return Evaluation(
                candidate_id=candidate_id,
                params=params,
                params_normalized=tuple(normalized),
                objectives=objectives,
                scalar_score=scalar_score,
                stage_a_passed=bool(row.get("stage_a_passed", False)),
                stage_b_result=row.get("stage_b_result"),
                status=status,
                provenance_ref=provenance_ref,
                wall_time_seconds=float(row.get("wall_time_seconds", 0.0)),
                metadata=metadata,
            )
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            metadata["transfer_status"] = "rejected"
            metadata["transfer_error"] = str(exc)
            return Evaluation(
                candidate_id=candidate_id,
                params=row.get("params", {}) if isinstance(row.get("params", {}), dict) else {},
                params_normalized=tuple(row.get("params_normalized", []))
                if isinstance(row.get("params_normalized", []), (list, tuple))
                else (),
                objectives=[],
                scalar_score=0.0,
                stage_a_passed=False,
                status=EvaluationStatus.STAGE_B_ERROR,
                provenance_ref=provenance_ref,
                metadata=metadata,
            )

    @staticmethod
    def _deserialize_objective(payload: Any) -> ObjectiveValue:
        """Rehydrate one objective without guessing legacy scalar semantics."""
        if not isinstance(payload, dict):
            raise TypeError("objective must be an object")
        name = payload["name"]
        raw_value = float(payload["raw_value"])
        if not math.isfinite(raw_value):
            raise ValueError("objective raw_value must be finite")
        direction_value = payload["direction"]
        if isinstance(direction_value, OptimizationDirection):
            direction = direction_value
        else:
            direction = OptimizationDirection(str(direction_value))
        return ObjectiveValue(
            name=str(name),
            raw_value=raw_value,
            direction=direction,
            weight=float(payload.get("weight", 1.0)),
            is_satisfied=bool(payload.get("is_satisfied", True)),
            threshold=(
                float(payload["threshold"]) if payload.get("threshold") is not None else None
            ),
        )

    def _load_run_evaluations(
        self,
        source: RunFingerprint | str,
    ) -> list[dict[str, Any]]:
        """Load persisted evaluations from an exact snapshot reference.

        The string form is retained for legacy callers and old in-memory cache
        entries.  Discovery results carry ``history_ref`` and never use the
        ANN fallback, so changing ``top_k`` cannot change addressability.
        """
        if isinstance(source, RunFingerprint):
            run_id = source.run_id
            history_ref = source.history_ref
        else:
            run_id = source
            history_ref = None

        cache_key = str(history_ref.artifact_id) if history_ref is not None else run_id
        if cache_key in self._eval_cache:
            return list(self._eval_cache[cache_key])

        if history_ref is not None:
            evals = self._read_history(history_ref)
            self._eval_cache[cache_key] = evals
            return list(evals)

        # Legacy callers may only have a run_id.  Keep this compatibility path
        # while ensuring newly discovered snapshots use the direct path above.
        results = self._index.query(
            [0.0] * self._index.dim,
            top_k=1000,
        )
        for key, _, meta in results:
            if key == run_id:
                history_ref = self._history_ref_from_metadata(meta)
                if history_ref is None:
                    continue
                evals = self._read_history(history_ref)
                self._eval_cache[str(history_ref.artifact_id)] = evals
                return list(evals)
        return []

    def _read_history(self, ref: ArtifactRef) -> list[dict[str, Any]]:
        """Read one validated JSON history payload from its exact CAS ref."""
        import json as _json

        raw = self._store.get_bytes(ref.artifact_id)
        try:
            data = _json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Malformed transfer history artifact {ref.artifact_id}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"Transfer history artifact {ref.artifact_id} is not an object")
        evals = data.get("evaluations")
        if not isinstance(evals, list):
            raise ValueError(
                f"Transfer history artifact {ref.artifact_id} has no evaluations list"
            )
        return list(evals)
