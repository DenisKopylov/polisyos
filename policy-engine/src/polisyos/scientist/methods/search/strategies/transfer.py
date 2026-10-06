"""Cross-run transfer learning for search strategies.

Finds similar past runs via vector similarity and extracts warm-start
evaluations for new searches.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime
from threading import RLock
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import artifacts, canon
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.strategies.types import Evaluation, EvaluationStatus

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.scientist.agent.vector_memory import VectorMemoryStore
    from polisyos.scientist.methods.autotune.models import BenchmarkEvaluation

logger = logging.getLogger(__name__)


class NumericTransferBasis(BaseModel):
    """Complete configured technical basis for direct numerical reuse.

    These exact content identities describe a conditional numerical profile.
    They do not issue institutional source authorization or certify measurements.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile: Literal["numeric_transfer_basis.v1"] = "numeric_transfer_basis.v1"
    search_space_fingerprint: str = Field(min_length=1)
    bounds: dict[str, Any]
    metric: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    direction: OptimizationDirection
    split: Literal["selection"] = "selection"
    scalarizer: Literal["direction_normalized_single_objective.v1"] = (
        "direction_normalized_single_objective.v1"
    )
    replica_policy: Literal["preserve_explicit_identity.v1"] = "preserve_explicit_identity.v1"
    origin: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    data_ref: ArtifactRef
    model_ref: ArtifactRef
    evaluator_ref: ArtifactRef
    split_ref: ArtifactRef
    scalarizer_ref: ArtifactRef
    owner_ref: ArtifactRef

    def identity_digest(self) -> str:
        """Hash the complete serialized basis, including exact manifest views."""
        payload = canon.to_canonical_bytes(
            self.model_dump(mode="json"), canon.CanonSpec(forbid_floats=False)
        )
        return "sha256:" + hashlib.sha256(payload).hexdigest()


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
    numeric_basis: NumericTransferBasis | None = None


class TransferLearningManager:
    """Discover history hints and admit only exact content-bound observations.

    Numerical admission is conditional on a configured technical basis. It
    establishes content/configuration consistency, never institutional rights
    or the scientific truth of a persisted measurement.
    """

    _CACHE_ENTRIES = 128
    _CACHE_BYTES = 32 * 1024 * 1024
    _DERIVED = frozenset({"transfer_history_ref", "source_row_index", "warm_start_compatibility"})

    def __init__(
        self,
        store: artifacts.ArtifactStore,
        index: VectorMemoryStore | None,
        *,
        cache_max_entries: int = 128,
        cache_max_bytes: int = 32 * 1024 * 1024,
    ) -> None:
        if (
            type(cache_max_entries) is not int
            or not 0 <= cache_max_entries <= self._CACHE_ENTRIES
            or type(cache_max_bytes) is not int
            or not 0 <= cache_max_bytes <= self._CACHE_BYTES
        ):
            raise ValueError("Cache bounds must be within 128 entries and 32 MiB")
        self._store, self._index = store, index
        self._cache_entries, self._cache_limit = cache_max_entries, cache_max_bytes
        self._eval_cache: OrderedDict[tuple[Any, ...], tuple[int, dict[str, Any]]] = OrderedDict()
        self._cache_bytes = 0
        self._cache_lock = RLock()
        self.last_admission_report: dict[str, Any] = {}

    @property
    def cache_info(self) -> dict[str, int]:
        """Return actual local cache occupancy in serialized-payload units."""
        with self._cache_lock:
            return {"entries": len(self._eval_cache), "serialized_bytes": self._cache_bytes}

    def register_run(
        self, fingerprint: RunFingerprint, evaluations: list[Evaluation]
    ) -> ArtifactRef | None:
        """Persist source rows faithfully; registration itself does not admit them."""
        if not evaluations:
            return None
        payload = {
            "schema_version": "2.0",
            "fingerprint": fingerprint.model_dump(
                mode="json", exclude={"history_ref", "embedding"}
            ),
            "evaluations": [self._serialize_evaluation(e) for e in evaluations],
        }
        ref = self._store.put_json(
            payload,
            artifacts.PutOptions(kind="search.transfer.history", media_type="application/json"),
            canon_spec=canon.CanonSpec(forbid_floats=False),
        )
        if fingerprint.embedding and self._index is not None:
            metadata = fingerprint.model_dump(mode="json", exclude={"history_ref", "embedding"})
            metadata["history_ref"] = ref.model_dump(mode="json")
            self._index.add(fingerprint.run_id, fingerprint.embedding, metadata)
        return ref

    @staticmethod
    def _history_ref_from_metadata(meta: dict[str, Any]) -> ArtifactRef | None:
        try:
            if "history_ref" in meta:
                ref = ArtifactRef.model_validate(meta["history_ref"])
            else:
                ref = ArtifactRef(
                    artifact_id=meta["artifact_id"],
                    kind="search.transfer.history",
                    media_type="application/json",
                )
            if ref.kind != "search.transfer.history" or ref.media_type != "application/json":
                return None
            return ref
        except (KeyError, TypeError, ValueError):
            return None

    def find_similar_runs(
        self, fingerprint: RunFingerprint, top_k: int = 5
    ) -> list[RunFingerprint]:
        """Return bounded ANN discoveries, including ideas that are not numerical matches.

        Filtering a bounded candidate window may return fewer than top_k; this
        does not claim globally best K compatible histories.
        """
        if self._index is None or not fingerprint.embedding or top_k <= 0:
            return []
        discoveries = []
        for key, _, metadata in self._index.query(fingerprint.embedding, top_k=top_k * 2):
            ref = self._history_ref_from_metadata(metadata)
            if key == fingerprint.run_id or ref is None:
                continue
            if set(metadata.get("objective_names", [])) != set(fingerprint.objective_names):
                continue
            try:
                data = {
                    name: metadata[name] for name in RunFingerprint.model_fields if name in metadata
                }
                data.update(run_id=key, history_ref=ref)
                discoveries.append(RunFingerprint.model_validate(data))
            except (TypeError, ValueError):
                continue
            if len(discoveries) >= top_k:
                break
        return discoveries

    def _resolved(self, ref: ArtifactRef) -> bytes:
        # Preserve the selected manifest profile through the existing guarded CAS reader.
        raw = self._store.get_bytes(ref)
        if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != ref.artifact_id.hex:
            raise ValueError("Artifact bytes do not match the exact content reference")
        manifest = self._store.get_manifest(ref)
        if manifest.kind != ref.kind or manifest.media_type != ref.media_type:
            raise ValueError("Artifact manifest does not match the complete typed reference")
        return raw

    def _history(self, ref: ArtifactRef) -> dict[str, Any]:
        if ref.kind != "search.transfer.history" or ref.media_type != "application/json":
            raise ValueError("Unsupported history reference type")
        raw = self._resolved(
            ref
        )  # Verify on cache hits too: altered bytes cannot hide behind a hit.
        key = (*artifacts.artifact_ref_identity_key(ref), "transfer-history-codec.v2")
        with self._cache_lock:
            cached = self._eval_cache.get(key)
            if cached is not None:
                self._eval_cache.move_to_end(key)
                return deepcopy(cached[1])
            data = canon.from_canonical_bytes(raw)
            if not isinstance(data, dict) or not isinstance(data.get("evaluations"), list):
                raise ValueError("Transfer history must contain an evaluations list")
            if data.get("schema_version") != "2.0" or not isinstance(data.get("fingerprint"), dict):
                raise ValueError(
                    "Unsupported transfer history codec: explicit v2 fingerprint required"
                )
            size = len(raw)
            if self._cache_entries and size <= self._cache_limit:
                while self._eval_cache and (
                    len(self._eval_cache) >= self._cache_entries
                    or self._cache_bytes + size > self._cache_limit
                ):
                    _, (old_size, _) = self._eval_cache.popitem(last=False)
                    self._cache_bytes -= old_size
                self._eval_cache[key] = (size, deepcopy(data))
                self._cache_bytes += size
            return deepcopy(data)

    def _load_run_evaluations(self, source: RunFingerprint | str) -> list[dict[str, Any]]:
        """Resolve a pinned discovery ref, or exact known-key alias, without ANN."""
        if isinstance(source, RunFingerprint):
            ref = source.history_ref
        else:
            metadata = self._index.metadata_for_key(source) if self._index is not None else None
            ref = self._history_ref_from_metadata(metadata) if metadata is not None else None
        if ref is None:
            raise ValueError("Exact history reference unavailable")
        return self._history(ref)["evaluations"]

    @staticmethod
    def _number(value: Any, name: str) -> float:
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"{name} must be a finite JSON number")
        return float(value)

    @staticmethod
    def _boolean(value: Any, name: str) -> bool:
        if type(value) is not bool:
            raise ValueError(f"{name} must be a boolean")
        return value

    @staticmethod
    def _serialize_evaluation(evaluation: Evaluation) -> dict[str, Any]:
        return {
            "candidate_id": evaluation.candidate_id,
            "params": deepcopy(evaluation.params),
            "params_normalized": list(evaluation.params_normalized),
            "objectives": [
                {
                    "name": o.name,
                    "raw_value": o.raw_value,
                    "direction": o.direction.value,
                    "weight": o.weight,
                    "is_satisfied": o.is_satisfied,
                    "threshold": o.threshold,
                }
                for o in evaluation.objectives
            ],
            "scalar_score": evaluation.scalar_score,
            "stage_a_passed": evaluation.stage_a_passed,
            "stage_b_result": deepcopy(evaluation.stage_b_result),
            "status": evaluation.status.value,
            "timestamp": evaluation.timestamp.isoformat(),
            "wall_time_seconds": evaluation.wall_time_seconds,
            "provenance_ref": evaluation.provenance_ref,
            "metadata": deepcopy(evaluation.metadata),
        }

    @classmethod
    def _deserialize_evaluation(cls, row: dict[str, Any], run_id: str) -> Evaluation:
        if not isinstance(row, dict):
            raise ValueError("Evaluation row must be an object")
        if not isinstance(row["candidate_id"], str) or not row["candidate_id"]:
            raise ValueError("candidate_id must be a non-empty string")
        if not isinstance(row["params"], dict) or not isinstance(row["metadata"], dict):
            raise ValueError("params and metadata must be objects")
        if not isinstance(row["params_normalized"], list):
            raise ValueError("params_normalized must be a list")
        if not isinstance(row["timestamp"], str):
            raise ValueError("timestamp must be an ISO timestamp string")
        timestamp = datetime.fromisoformat(row["timestamp"])
        if timestamp.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        if not isinstance(row["status"], str):
            raise ValueError("status must be a typed string")
        if row.get("stage_b_result") is not None and not isinstance(row["stage_b_result"], dict):
            raise ValueError("stage_b_result must be an object or null")
        if row.get("provenance_ref") is not None and not isinstance(row["provenance_ref"], str):
            raise ValueError("provenance_ref must be a string or null")
        objectives = row["objectives"]
        if not isinstance(objectives, list) or not objectives:
            raise ValueError("objectives must be a non-empty list")
        values = []
        for item in objectives:
            if not isinstance(item, dict) or not isinstance(item["name"], str) or not item["name"]:
                raise ValueError("objective must have a typed non-empty name")
            values.append(
                ObjectiveValue(
                    name=item["name"],
                    raw_value=cls._number(item["raw_value"], "raw_value"),
                    direction=OptimizationDirection(item["direction"]),
                    weight=cls._number(item["weight"], "weight"),
                    is_satisfied=cls._boolean(item["is_satisfied"], "is_satisfied"),
                    threshold=None
                    if item.get("threshold") is None
                    else cls._number(item["threshold"], "threshold"),
                )
            )
        return Evaluation(
            candidate_id=row["candidate_id"],
            params=deepcopy(row["params"]),
            params_normalized=tuple(
                cls._number(v, "normalized coordinate") for v in row["params_normalized"]
            ),
            objectives=values,
            scalar_score=cls._number(row["scalar_score"], "scalar_score"),
            stage_a_passed=cls._boolean(row["stage_a_passed"], "stage_a_passed"),
            stage_b_result=deepcopy(row.get("stage_b_result")),
            status=EvaluationStatus(row["status"]),
            timestamp=timestamp,
            wall_time_seconds=cls._number(row["wall_time_seconds"], "wall_time_seconds"),
            provenance_ref=row.get("provenance_ref"),
            metadata=deepcopy(row["metadata"]),
        )

    @classmethod
    def _space(cls, basis: NumericTransferBasis) -> Any:
        from polisyos.scientist.methods.search.strategies.space import SearchSpace
        from polisyos.scientist.methods.search.strategies.types import (
            ParameterBounds,
            ParameterType,
        )

        specs = basis.bounds.get("parameters")
        if set(basis.bounds) != {"parameters"} or not isinstance(specs, list) or not specs:
            raise ValueError("Unsupported bounds: ordered parameters required")
        bounds = []
        names = set()
        for spec in specs:
            if (
                not isinstance(spec, dict)
                or set(spec) != {"name", "lower", "upper", "dtype", "log_scale", "categories"}
                or not isinstance(spec.get("name"), str)
                or not spec["name"]
                or spec["name"] in names
            ):
                raise ValueError("Malformed parameter bounds")
            names.add(spec["name"])
            dtype = ParameterType(spec["dtype"])
            lower, upper = cls._number(spec["lower"], "lower"), cls._number(spec["upper"], "upper")
            log_scale = cls._boolean(spec["log_scale"], "log_scale")
            categories = spec.get("categories")
            if categories is not None and not isinstance(categories, list):
                raise ValueError("categories must be a list or null")
            if dtype == ParameterType.LOG_CONTINUOUS and lower <= 0:
                raise ValueError("Log continuous bounds require a positive lower bound")
            bounds.append(
                ParameterBounds(
                    name=spec["name"],
                    lower=lower,
                    upper=upper,
                    dtype=dtype,
                    log_scale=log_scale,
                    categories=None if categories is None else tuple(categories),
                )
            )
        space = SearchSpace(bounds=bounds)
        if space.sobol_space_fingerprint() != basis.search_space_fingerprint:
            raise ValueError("Bounds and actual search-space fingerprint disagree")
        return space

    @classmethod
    def _physical(cls, params: dict[str, Any], basis: NumericTransferBasis) -> tuple[float, ...]:
        from polisyos.scientist.methods.search.strategies.types import ParameterType

        space = cls._space(basis)
        if set(params) != {b.name for b in space.bounds}:
            raise ValueError("Physical parameters must match the complete space")
        for bound in space.bounds:
            value = params[bound.name]
            if bound.dtype == ParameterType.CATEGORICAL:
                if not any(type(value) is type(c) and value == c for c in bound.categories):
                    raise ValueError("Physical category is outside its actual domain")
            else:
                number = cls._number(value, "physical parameter")
                if not bound.lower <= number <= bound.upper:
                    raise ValueError("Physical parameter is outside its actual bounds")
                if bound.dtype == ParameterType.INTEGER and not number.is_integer():
                    raise ValueError("Physical integer parameter is fractional")
        return tuple(space.normalize(params))

    def _original_benchmark(
        self, evaluation: Evaluation, basis: NumericTransferBasis
    ) -> BenchmarkEvaluation:
        from polisyos.scientist.methods.autotune.models import BenchmarkEvaluation, BenchmarkSplit

        metadata = evaluation.metadata
        candidate_ref = ArtifactRef.model_validate(metadata["candidate_ref"])
        evaluation_ref = ArtifactRef.model_validate(metadata["evaluation_ref"])
        declared = NumericTransferBasis.model_validate(metadata["numeric_transfer_basis"])
        if declared.identity_digest() != basis.identity_digest():
            raise ValueError("Declared observation numerical basis disagrees")
        if candidate_ref.media_type != "application/json":
            raise ValueError("Unsupported original candidate media type")
        if (
            str(candidate_ref.artifact_id) != evaluation.candidate_id
            or str(evaluation_ref.artifact_id) != evaluation.provenance_ref
        ):
            raise ValueError("Original candidate/evaluation identities disagree")
        candidate = canon.from_canonical_bytes(self._resolved(candidate_ref))
        if not isinstance(candidate, dict):
            raise ValueError("Unsupported original candidate payload")
        source_params = candidate.get("params", candidate)
        actual_params = {
            spec["name"]: source_params[spec["name"]] for spec in basis.bounds["parameters"]
        }
        if not self._physical_input_matches(actual_params, evaluation.params, basis):
            raise ValueError("Original candidate physical parameters disagree")
        normalized = self._physical(evaluation.params, basis)
        if len(normalized) != len(evaluation.params_normalized) or any(
            not math.isclose(a, b, rel_tol=0, abs_tol=1e-12)
            for a, b in zip(normalized, evaluation.params_normalized)
        ):
            raise ValueError("Physical parameters and declared normalized coordinates disagree")
        payload = canon.from_canonical_bytes(self._resolved(evaluation_ref))
        if not isinstance(payload, dict) or evaluation_ref.media_type != "application/json":
            raise ValueError("Unsupported original measurement profile")
        self._boolean(payload.get("promotable"), "original promotable flag")
        for name in ("selection_metrics", "holdout_metrics"):
            values = payload.get(name)
            if not isinstance(values, dict):
                raise ValueError("Original metric collections must be objects")
            for value in values.values():
                self._number(value, "original metric")
        counts = payload.get("sample_counts")
        if not isinstance(counts, dict) or any(
            type(value) is not int or value < 0 for value in counts.values()
        ):
            raise ValueError("Original sample counts must be nonnegative integers")
        guardrails = payload.get("guardrails")
        if not isinstance(guardrails, dict) or any(
            type(flag) is not bool for flag in guardrails.values()
        ):
            raise ValueError("Original guardrail outcomes must be booleans")
        if not all(guardrails.values()):
            raise ValueError("Original guardrail outcome failed")
        bench = BenchmarkEvaluation.model_validate(payload)
        manifest = self._store.get_manifest(evaluation_ref)
        if (
            evaluation_ref.kind != f"scientist.autotune.{bench.loop_id}.evaluation"
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name
            != "polisyos.scientist.methods.autotune.BenchmarkEvaluation"
            or manifest.artifact_schema.version != bench.suite_version
        ):
            raise ValueError("Unsupported original benchmark producer/schema profile")
        if artifacts.artifact_ref_identity_key(
            bench.candidate_ref
        ) != artifacts.artifact_ref_identity_key(candidate_ref):
            raise ValueError("Original measurement binds a different candidate view")
        if (
            payload.get("runtime_split_type") != BenchmarkSplit.SELECTION.value
            or bench.status != "ok"
        ):
            raise ValueError(
                "Original measurement is not an allowed successful selection observation"
            )
        source_basis = NumericTransferBasis.model_validate(bench.metadata["numeric_transfer_basis"])
        if source_basis.identity_digest() != basis.identity_digest():
            raise ValueError("Original measurement numerical basis disagrees")
        # Generic over all actual role-reference fields in the admitted basis schema.
        for name in NumericTransferBasis.model_fields:
            if name.endswith("_ref"):
                self._resolved(getattr(basis, name))
        if not self._physical_input_matches(bench.metadata.get("params"), evaluation.params, basis):
            raise ValueError("Original measurement physical input disagrees")
        raw = self._number(payload["selection_metrics"][basis.metric], "original metric")
        if len(evaluation.objectives) != 1:
            raise ValueError("Unsupported scalarizer: one original metric required")
        objective = evaluation.objectives[0]
        scalar = raw if basis.direction == OptimizationDirection.MINIMIZE else -raw
        if (
            objective.name != basis.metric
            or objective.direction != basis.direction
            or objective.raw_value != raw
            or objective.weight != 1.0
            or objective.threshold is not None
            or not objective.is_satisfied
            or evaluation.scalar_score != scalar
        ):
            raise ValueError("Original metric, direction or scalarization disagrees")
        return bench

    @classmethod
    def _physical_input_matches(
        cls, actual: Any, declared: dict[str, Any], basis: NumericTransferBasis
    ) -> bool:
        """Bind both original persisted inputs with typed physical domain semantics."""
        if not isinstance(actual, dict):
            raise ValueError("Original physical input must be an object")
        cls._physical(actual, basis)
        return actual == declared and all(
            type(actual[key]) is type(declared[key]) for key in actual
        )

    def target_basis(self, fingerprint: RunFingerprint) -> NumericTransferBasis:
        """Snapshot an explicit configured target; a source row cannot establish it."""
        if fingerprint.numeric_basis is None:
            raise ValueError("Configured target numerical basis unavailable")
        basis = NumericTransferBasis.model_validate(
            fingerprint.numeric_basis.model_dump(mode="json")
        )
        self._check_fingerprint(fingerprint, basis)
        self._space(basis)
        for name in NumericTransferBasis.model_fields:
            if name.endswith("_ref"):
                self._resolved(getattr(basis, name))
        return basis

    @staticmethod
    def _check_fingerprint(source: RunFingerprint, target: NumericTransferBasis) -> None:
        if (
            source.space_hash != target.search_space_fingerprint
            or source.bounds != target.bounds
            or source.objective_names != [target.metric]
            or source.split != target.split
            or source.units != {target.metric: target.unit}
            or source.origin != target.origin
            or source.tenant_id != target.tenant_id
            or source.objective_directions != {target.metric: target.direction.value}
        ):
            raise ValueError("Run fingerprint disagrees with its numerical basis")

    @staticmethod
    def _report() -> dict[str, Any]:
        return {
            "loaded": 0,
            "accepted": 0,
            "rejected": 0,
            "unavailable": 0,
            "selected": 0,
            "rejections": [],
        }

    def _admit(
        self,
        row: dict[str, Any],
        source: RunFingerprint,
        target: NumericTransferBasis,
        history_ref: ArtifactRef,
        row_index: int,
    ) -> Evaluation:
        if (
            source.numeric_basis is None
            or source.numeric_basis.identity_digest() != target.identity_digest()
        ):
            raise ValueError("Source numerical basis is missing or incompatible")
        self._check_fingerprint(source, target)
        evaluation = self._deserialize_evaluation(row, source.run_id)
        if not evaluation.is_valid:
            raise ValueError("Original outcome is invalid for numerical training")
        self._original_benchmark(evaluation, target)
        evaluation.metadata.update(
            {
                "transfer_history_ref": history_ref.model_dump(mode="json"),
                "source_row_index": row_index,
                "warm_start_compatibility": {
                    "search_space_fingerprint": target.search_space_fingerprint,
                    "input_transform_fingerprint": "Normalize[0,1]",
                    "outcome_transform_fingerprint": "Standardize[m=1]",
                    "noise_model_fingerprint": "GaussianLikelihood[inferred]",
                    "objective_fingerprint": "scalar_score[minimize]",
                    "context_fingerprint": target.identity_digest(),
                },
            }
        )
        return evaluation

    def get_warm_start_evaluations(
        self,
        similar_runs: list[RunFingerprint],
        max_evals: int = 50,
        *,
        target_fingerprint: RunFingerprint | None = None,
    ) -> list[Evaluation]:
        """Select admitted normalized minima fairly; diagnostics consume no row quota."""
        report = self._report()
        groups = []
        self.last_admission_report = report
        if max_evals <= 0:
            return []
        target = None if target_fingerprint is None else self.target_basis(target_fingerprint)
        for discovered in similar_runs:
            try:
                if discovered.history_ref is None:
                    raise ValueError("Exact discovered history reference unavailable")
                history = self._history(discovered.history_ref)
                source = RunFingerprint.model_validate(history["fingerprint"])
                if source.run_id != discovered.run_id:
                    raise ValueError("Discovered alias and persisted source identity disagree")
            except Exception as exc:
                report["unavailable"] += 1
                report["rejections"].append({"run_id": discovered.run_id, "reason": str(exc)})
                continue
            accepted = []
            for number, row in enumerate(history["evaluations"]):
                report["loaded"] += 1
                try:
                    if target is None:
                        raise ValueError("Configured target numerical basis unavailable")
                    evaluation = self._admit(row, source, target, discovered.history_ref, number)
                    accepted.append(evaluation)
                    report["accepted"] += 1
                except Exception as exc:
                    report["rejected"] += 1
                    report["rejections"].append(
                        {"run_id": source.run_id, "row_index": number, "reason": str(exc)}
                    )
            accepted.sort(key=lambda e: e.scalar_score)
            groups.append(accepted)
        chosen = []
        while len(chosen) < max_evals and any(groups):
            for group in groups:
                if group:
                    chosen.append(group.pop(0))
                    if len(chosen) == max_evals:
                        break
        report["selected"] = len(chosen)
        return chosen

    def admit_warm_start(
        self, evaluations: list[Evaluation], target_basis: NumericTransferBasis
    ) -> list[Evaluation]:
        """Re-resolve original content for initial warm load and checkpoint replay."""
        report = self._report()
        accepted = []
        self.last_admission_report = report
        for supplied in evaluations:
            report["loaded"] += 1
            try:
                ref = ArtifactRef.model_validate(supplied.metadata["transfer_history_ref"])
                index = supplied.metadata["source_row_index"]
                if type(index) is not int or index < 0:
                    raise ValueError("Invalid source row index")
                history = self._history(ref)
                row = history["evaluations"][index]
                source = RunFingerprint.model_validate(history["fingerprint"])
                restored = self._admit(row, source, target_basis, ref, index)
                left = self._serialize_evaluation(supplied)
                right = self._serialize_evaluation(restored)
                for content in (left, right):
                    content["metadata"] = {
                        k: v for k, v in content["metadata"].items() if k not in self._DERIVED
                    }
                if left != right:
                    raise ValueError(
                        "Supplied warm row differs from original persisted observation"
                    )
                accepted.append(restored)
                report["accepted"] += 1
            except Exception as exc:
                report["rejected"] += 1
                report["rejections"].append(
                    {"candidate_id": supplied.candidate_id, "reason": str(exc)}
                )
        report["selected"] = len(accepted)
        return accepted
