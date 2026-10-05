"""Cross-run transfer learning for search strategies.

Finds similar past runs via vector similarity and extracts warm-start
evaluations for new searches.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.strategies.types import Evaluation, EvaluationStatus

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.scientist.agent.vector_memory import VectorMemoryStore

logger = logging.getLogger(__name__)


class TransferHistoryError(ValueError):
    """An addressed history could not be restored without losing its identity."""

    def __init__(self, reason: str, artifact_id: str | None = None) -> None:
        self.reason = reason
        self.artifact_id = artifact_id
        super().__init__(f"Transfer history {artifact_id or '<unbound>'}: {reason}")


@dataclass(frozen=True)
class TransferRestoreReport:
    """Reconciled counts for the most recent bounded restore operation."""

    loaded_rows: int = 0
    accepted_rows: int = 0
    rejected_rows: int = 0
    selected_rows: int = 0
    excluded_run_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class TransferDiscoveryIssue:
    """One discovered record excluded before an exact history read."""

    run_id: str
    reason: str


@dataclass(frozen=True)
class TransferRecordIssue:
    """An addressed row rejected independently of the bounded response quota."""

    run_id: str
    candidate_id: str
    history_ref: str | None
    reason: str


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

    def numeric_context_fingerprint(self) -> str:
        """Bind numeric reuse to the complete experiment basis, excluding run aliases."""
        basis = self.model_dump(
            mode="json",
            include={
                "space_hash",
                "objective_names",
                "bounds",
                "split",
                "units",
                "origin",
                "tenant_id",
                "objective_directions",
            },
        )
        basis["objective_names"] = sorted(basis["objective_names"])
        return (
            "sha256:"
            + hashlib.sha256(
                json.dumps(basis, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            ).hexdigest()
        )


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
        self._history_bindings: dict[str, dict[str, Any]] = {}
        self.last_restore_report = TransferRestoreReport()
        self.last_discovery_issues: tuple[TransferDiscoveryIssue, ...] = ()
        self.last_restore_rejections: tuple[TransferRecordIssue, ...] = ()

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
        from polisyos.core.canon.canon_json import CanonSpec

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
            canon_spec=CanonSpec(forbid_floats=False),
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
        self.last_discovery_issues = ()
        if not fingerprint.embedding:
            return []

        results = self._index.query(fingerprint.embedding, top_k=top_k * 2)
        similar: list[RunFingerprint] = []
        issues: list[TransferDiscoveryIssue] = []

        for key, _, meta in results:
            if key == fingerprint.run_id:
                continue
            history_ref = self._history_ref_from_metadata(meta)
            if history_ref is None:
                issues.append(
                    TransferDiscoveryIssue(
                        key,
                        "history_ref_absent"
                        if meta.get("artifact_id") is None
                        else "history_ref_invalid",
                    )
                )
                logger.warning("Skipping run %s without a valid history ArtifactRef", key)
                continue
            # Similarity is discovery only; numeric reuse requires full binding.
            obj_names = meta.get("objective_names", [])
            if set(obj_names) != set(fingerprint.objective_names):
                issues.append(TransferDiscoveryIssue(key, "objective_binding_mismatch"))
                continue
            if meta.get("space_hash") != fingerprint.space_hash:
                issues.append(TransferDiscoveryIssue(key, "space_binding_mismatch"))
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
                issues.append(TransferDiscoveryIssue(key, "numeric_binding_mismatch"))
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

        self.last_discovery_issues = tuple(issues)
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
        self.last_restore_report = TransferRestoreReport()
        self.last_restore_rejections = ()
        if max_evals <= 0 or not similar_runs:
            return []

        prepared: list[list[Evaluation]] = []
        rejected_evaluations: list[Evaluation] = []
        issues: list[TransferRecordIssue] = []
        loaded_rows = rejected_rows = accepted_rows = 0
        excluded_runs: list[str] = []
        for fp in similar_runs:
            if target_fingerprint is not None and not self._binding_matches(target_fingerprint, fp):
                excluded_runs.append(fp.run_id)
                continue

            rows = self._load_run_evaluations(fp, require_binding=target_fingerprint is not None)
            evaluations = []
            for row in rows:
                evaluation = self._deserialize_evaluation(row, fp.run_id)
                reason = (
                    evaluation.metadata.get("transfer_error") if not evaluation.is_valid else None
                )
                if reason is None:
                    reason = (
                        self._numeric_rejection(evaluation, fp)
                        if target_fingerprint is not None
                        else "Numeric restore requires an explicit target fingerprint"
                    )
                if reason is not None:
                    evaluation.status = EvaluationStatus.STAGE_B_ERROR
                    evaluation.stage_a_passed = False
                    evaluation.metadata["transfer_status"] = "rejected"
                    evaluation.metadata["transfer_error"] = reason
                    rejected_rows += 1
                    issues.append(
                        TransferRecordIssue(
                            fp.run_id,
                            evaluation.candidate_id,
                            str(fp.history_ref.artifact_id) if fp.history_ref is not None else None,
                            reason,
                        )
                    )
                else:
                    accepted_rows += 1
                    evaluation.metadata["source_history_ref"] = str(fp.history_ref.artifact_id)
                evaluations.append(evaluation)
            loaded_rows += len(rows)
            evaluations.sort(key=self._evaluation_sort_key)
            valid = [evaluation for evaluation in evaluations if evaluation.is_valid]
            rejected_evaluations.extend(
                evaluation for evaluation in evaluations if not evaluation.is_valid
            )
            if valid:
                prepared.append(valid)

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

        # Rejections stay visible, but never consume capacity while another
        # source has an admissible numeric observation available.
        rejected_evaluations.sort(key=self._evaluation_sort_key)
        all_evals.extend(rejected_evaluations[: max_evals - len(all_evals)])

        self.last_restore_report = TransferRestoreReport(
            loaded_rows, accepted_rows, rejected_rows, len(all_evals), tuple(excluded_runs)
        )
        self.last_restore_rejections = tuple(issues)
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
            and bool(target.bounds)
            and target.split == "selection"
            and bool(target.origin and target.origin.strip())
            and bool(target.tenant_id and target.tenant_id.strip())
            and bool(target.objective_names)
            and set(target.units) == set(target.objective_names)
            and all(isinstance(unit, str) and unit.strip() for unit in target.units.values())
            and set(target.objective_directions) == set(target.objective_names)
            and all(
                direction in {"minimize", "maximize"}
                for direction in target.objective_directions.values()
            )
            and target.space_hash == source.space_hash
            and set(target.objective_names) == set(source.objective_names)
            and target.bounds == source.bounds
            and target.split == source.split
            and target.units == source.units
            and target.origin == source.origin
            and target.tenant_id == source.tenant_id
            and target.objective_directions == source.objective_directions
        )

    def _numeric_rejection(self, evaluation: Evaluation, source: RunFingerprint) -> str | None:
        """Resolve and content-bind an observation before numeric reuse."""
        if not evaluation.is_valid:
            return evaluation.metadata.get("transfer_error", "invalid source outcome")
        if evaluation.metadata.get("source_run_id") != source.run_id:
            return "source run identity differs from the addressed snapshot"
        if evaluation.metadata.get("source_candidate_id") != evaluation.candidate_id:
            return "source candidate identity differs from the observation"
        if {objective.name for objective in evaluation.objectives} != set(source.objective_names):
            return "objective names differ from the bound experiment"
        if any(
            source.objective_directions[obj.name] != obj.direction.value
            for obj in evaluation.objectives
        ):
            return "objective directions differ from the bound experiment"
        if any(not math.isfinite(obj.weight) for obj in evaluation.objectives):
            return "objective weights must be finite"
        compatibility = evaluation.metadata.get("warm_start_compatibility")
        if not isinstance(compatibility, dict) or (
            compatibility.get("search_space_fingerprint") != source.space_hash
            or compatibility.get("context_fingerprint") != source.numeric_context_fingerprint()
        ):
            return "missing or incompatible persisted model/context basis"
        if not evaluation.provenance_ref:
            return "missing original evaluation reference"
        try:
            from polisyos.core.canon import from_canonical_bytes

            candidate_ref = ArtifactRef(
                artifact_id=evaluation.candidate_id,
                kind="search.candidate",
                media_type="application/json",
            )
            candidate_payload = from_canonical_bytes(
                self._store.get_bytes(candidate_ref.artifact_id)
            )
            ref = ArtifactRef(
                artifact_id=evaluation.provenance_ref,
                kind="search.evaluation",
                media_type="application/json",
            )
            payload = from_canonical_bytes(self._store.get_bytes(ref.artifact_id))
        except (TypeError, ValueError, OSError, KeyError) as exc:
            return f"original evaluation unavailable or corrupt: {exc}"
        rejection = self._candidate_parameter_rejection(candidate_payload, evaluation.params)
        if rejection is not None:
            return rejection
        rejection = self._source_coordinate_rejection(evaluation, source)
        if rejection is not None:
            return rejection
        expected = self._serialize_evaluation(evaluation)
        fields = (
            "candidate_id",
            "params",
            "params_normalized",
            "objectives",
            "scalar_score",
            "stage_a_passed",
            "status",
            "timestamp",
        )
        if (
            isinstance(payload, dict)
            and all(payload.get(key) == expected[key] for key in fields)
            and isinstance(payload.get("metadata"), dict)
            and payload["metadata"].get("warm_start_compatibility") == compatibility
            and payload["metadata"].get("source_run_id") == source.run_id
        ):
            return None
        if isinstance(payload, dict) and "candidate_ref" in payload:
            from polisyos.scientist.methods.autotune.models import (
                BenchmarkEvaluation,
                BenchmarkSplit,
            )

            try:
                benchmark = BenchmarkEvaluation.model_validate(payload)
            except ValueError:
                return "original benchmark schema is incompatible"
            if any(obj.weight != 1.0 for obj in evaluation.objectives) or not math.isclose(
                evaluation.scalar_score,
                math.fsum(obj.normalized_value for obj in evaluation.objectives),
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                return "benchmark scalarization is not the declared unweighted minimization"
            source_directions = benchmark.metadata.get("directions")
            if not isinstance(source_directions, dict):
                return "original benchmark lacks typed objective directions"
            if (
                str(benchmark.candidate_ref.artifact_id) == evaluation.candidate_id
                and benchmark.loop_id == source.run_id
                and benchmark.metadata.get("warm_start_compatibility") == compatibility
                and benchmark.matches_runtime_split(BenchmarkSplit.SELECTION)
                and benchmark.metadata.get("params") == evaluation.params
                and all(
                    benchmark.selection_metrics.get(obj.name) == obj.raw_value
                    for obj in evaluation.objectives
                )
                and all(
                    source_directions.get(obj.name) == obj.direction.value
                    for obj in evaluation.objectives
                )
                and not benchmark.metadata.get("warm_start")
            ):
                return None
        return "original evaluation content does not match the transferred observation"

    @staticmethod
    def _candidate_parameter_rejection(payload: Any, params: dict[str, Any]) -> str | None:
        """Bind supported nested strategy or flat mutation inputs to physical params."""
        if not isinstance(payload, dict) or not params:
            return "unsupported actual candidate parameter basis"
        if "params" in payload:
            actual = payload["params"]
            if not isinstance(actual, dict):
                return "unsupported actual candidate parameter basis"
        elif all(name in payload for name in params):
            actual = {name: payload[name] for name in params}
        else:
            return "unsupported actual candidate parameter basis"
        if actual != params:
            return "actual candidate parameters differ from the transferred observation"
        return None

    @staticmethod
    def _source_coordinate_rejection(evaluation: Evaluation, source: RunFingerprint) -> str | None:
        """Reconstruct only explicit native bounds whose space identity reconciles."""
        from polisyos.scientist.methods.search.strategies.space import SearchSpace
        from polisyos.scientist.methods.search.strategies.types import (
            ParameterBounds,
            ParameterType,
        )

        try:
            bounds = []
            for name, specification in source.bounds.items():
                if isinstance(specification, (list, tuple)) and len(specification) == 2:
                    lower, upper = specification
                    options = {}
                elif isinstance(specification, dict) and set(specification) <= {
                    "lower", "upper", "dtype", "log_scale", "categories"
                }:
                    options = dict(specification)
                    lower, upper = options.pop("lower"), options.pop("upper")
                    options["dtype"] = ParameterType(options.get("dtype", "continuous"))
                    if options.get("categories") is not None:
                        options["categories"] = tuple(options["categories"])
                else:
                    return "unsupported source parameter basis"
                bound = ParameterBounds.explicit(name=name, lower=lower, upper=upper, **options)
                bounds.append(bound)
            space = SearchSpace(bounds)
            if space.sobol_space_fingerprint() != source.space_hash:
                return "unsupported source parameter basis: space identity differs"
            if set(evaluation.params) != set(source.bounds):
                return "physical parameters differ from the persisted source basis"
            for bound in bounds:
                raw = evaluation.params[bound.name]
                if bound.dtype != ParameterType.CATEGORICAL and (
                    isinstance(raw, bool)
                    or not math.isfinite(float(raw))
                    or not bound.lower <= float(raw) <= bound.upper
                ):
                    return "physical parameters differ from the persisted source basis"
            expected = space.normalize(evaluation.params)
            if len(expected) != len(evaluation.params_normalized) or any(
                not math.isfinite(float(actual))
                or not math.isclose(float(actual), wanted, rel_tol=0.0, abs_tol=1e-12)
                for actual, wanted in zip(evaluation.params_normalized, expected, strict=True)
            ):
                return "normalized parameters differ from the persisted source basis"
        except (KeyError, TypeError, ValueError, OverflowError):
            return "unsupported source parameter basis"
        return None

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
        if not math.isfinite(evaluation.scalar_score):
            return (1, 0.0)
        if not evaluation.is_valid:
            return (1, evaluation.scalar_score)
        return (0, evaluation.scalar_score)

    @classmethod
    def _deserialize_evaluation(cls, row: dict[str, Any], run_id: str) -> Evaluation:
        """Rehydrate one row, returning a visible rejection for malformed data."""
        if not isinstance(row, dict):
            row = {"metadata": {"transfer_error": "evaluation row must be an object"}}
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
                **(
                    {"timestamp": datetime.fromisoformat(row["timestamp"])}
                    if "timestamp" in row
                    else {}
                ),
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
        *,
        require_binding: bool = False,
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
        if not hasattr(self, "_history_bindings"):
            self._history_bindings = {}
        if require_binding and history_ref is None:
            raise TransferHistoryError("missing exact snapshot reference")
        if cache_key in self._eval_cache:
            if require_binding:
                binding = self._history_bindings.get(cache_key)
                if binding is None:
                    raise TransferHistoryError(
                        "cached snapshot has no experiment binding", cache_key
                    )
                self._validate_history_binding(binding, source, history_ref)
            return deepcopy(self._eval_cache[cache_key])

        if history_ref is not None:
            evals = self._read_history(history_ref, source if require_binding else None)
            self._eval_cache[cache_key] = evals
            return deepcopy(evals)

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
                return deepcopy(evals)
        return []

    def _read_history(
        self, ref: ArtifactRef, source: RunFingerprint | None = None
    ) -> list[dict[str, Any]]:
        """Read one validated JSON history payload from its exact CAS ref."""
        from polisyos.core.canon import from_canonical_bytes

        try:
            raw = self._store.get_bytes(ref.artifact_id)
        except (OSError, KeyError) as exc:
            raise TransferHistoryError("snapshot unavailable", str(ref.artifact_id)) from exc
        try:
            data = from_canonical_bytes(raw)
        except (TypeError, ValueError) as exc:
            raise TransferHistoryError("snapshot corrupt", str(ref.artifact_id)) from exc
        if not isinstance(data, dict):
            raise TransferHistoryError("snapshot is not an object", str(ref.artifact_id))
        evals = data.get("evaluations")
        if not isinstance(evals, list):
            raise TransferHistoryError("snapshot has no evaluations list", str(ref.artifact_id))
        if source is not None:
            self._validate_history_binding(data, source, ref)
        self._history_bindings[str(ref.artifact_id)] = {
            key: deepcopy(value) for key, value in data.items() if key != "evaluations"
        }
        return list(evals)

    @staticmethod
    def _validate_history_binding(
        payload: dict[str, Any], source: RunFingerprint, ref: ArtifactRef
    ) -> None:
        """Reconcile discovery declarations against the selected immutable bytes."""
        fields = (
            "run_id",
            "space_hash",
            "objective_names",
            "bounds",
            "split",
            "units",
            "origin",
            "tenant_id",
            "objective_directions",
        )
        if any(payload.get(field) != getattr(source, field) for field in fields):
            raise TransferHistoryError("snapshot experiment binding differs", str(ref.artifact_id))
