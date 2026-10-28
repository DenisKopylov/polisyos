"""Cross-run transfer learning for search strategies.

Finds similar past runs via vector similarity and extracts warm-start
evaluations for new searches.
"""

from __future__ import annotations

import json
import logging
import math
from collections import OrderedDict
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.canon import CanonSpec, fingerprint
from polisyos.scientist.methods.search.objective import (
    ObjectiveScoreAssessment,
    ObjectiveScoreStatus,
    ObjectiveValue,
    OptimizationDirection,
    _evaluation_matches_selected_objectives,
    _unestablished_score_assessment,
    configured_objective_unit,
    objective_value_matches_rule,
    score_assessment_matches_source,
)
from polisyos.scientist.methods.search.strategies.types import (
    Evaluation,
    EvaluationStatus,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.scientist.agent.vector_memory import VectorMemoryStore

logger = logging.getLogger(__name__)

_HISTORY_BINDING_FIELDS = (
    "run_id",
    "space_hash",
    "objective_names",
    "bounds",
    "split",
    "units",
    "origin",
    "tenant_id",
    "objective_directions",
    "objective_rule_specs",
)
_HISTORY_INDEX_FIELDS = tuple(field for field in _HISTORY_BINDING_FIELDS if field != "run_id")
_HISTORY_NULLABLE_FIELDS = ("split", "origin", "tenant_id")
_HISTORY_DIRECTIONS = frozenset(direction.value for direction in OptimizationDirection)


class RunFingerprint(BaseModel):
    """Identifies a search run for cross-run transfer matching."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    space_hash: str = Field(..., min_length=1)
    objective_names: list[str]
    bounds: dict[str, Any] = Field(default_factory=dict)
    split: str | None = None
    units: dict[str, StrictStr] = Field(
        default_factory=dict,
        description="Exact selected objective name to unit identity bindings; conversions are not inferred.",
    )
    origin: str | None = None
    tenant_id: str | None = None
    objective_directions: dict[str, str] = Field(default_factory=dict)
    objective_rule_specs: dict[str, str] = Field(default_factory=dict)
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

    _MAX_HISTORY_CACHE_ENTRIES = 128
    _MAX_HISTORY_CACHE_BYTES = 32 * 1024 * 1024

    def __init__(self, store: ArtifactStore, index: VectorMemoryStore) -> None:
        self._store = store
        self._index = index
        self._eval_cache: OrderedDict[str, bytes] = OrderedDict()
        self._eval_cache_bytes = 0

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
        if not self._has_complete_binding_basis(fingerprint):
            raise ValueError(
                "transfer history requires an explicitly supplied complete run fingerprint"
            )

        # Persist evaluations
        eval_dicts = [
            self._serialize_evaluation(e)
            for e in evaluations
            if self._evaluation_matches_fingerprint(e, fingerprint)
        ]

        if not eval_dicts:
            return None

        ref = self._store.put_json(
            {
                "history_schema_version": "5",
                "run_id": fingerprint.run_id,
                "space_hash": fingerprint.space_hash,
                "objective_names": fingerprint.objective_names,
                "bounds": fingerprint.bounds,
                "split": fingerprint.split,
                "units": fingerprint.units,
                "origin": fingerprint.origin,
                "tenant_id": fingerprint.tenant_id,
                "objective_directions": fingerprint.objective_directions,
                "objective_rule_specs": fingerprint.objective_rule_specs,
                "evaluations": eval_dicts,
                "best_score": fingerprint.best_score,
                "num_evaluations": fingerprint.num_evaluations,
            },
            PutOptions(
                kind="search.transfer.history",
                media_type="application/json",
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
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
                    "objective_rule_specs": fingerprint.objective_rule_specs,
                    "best_score": fingerprint.best_score,
                    "artifact_id": str(ref.artifact_id),
                    "manifest_profile_sha256": ref.manifest_profile_sha256,
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
        if not fingerprint.embedding or not self._has_complete_binding_basis(fingerprint):
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
            # Similarity is discovery only; numeric reuse requires the complete
            # typed index basis and a later payload-header reconciliation.
            try:
                source = self._fingerprint_from_index_metadata(key, meta, history_ref)
            except (TypeError, ValueError) as exc:
                logger.warning("Skipping run %s with invalid transfer metadata: %s", key, exc)
                continue
            if not self._binding_matches(fingerprint, source):
                continue
            similar.append(source)
            if len(similar) >= top_k:
                break

        return similar

    def get_warm_start_evaluations(
        self,
        similar_runs: list[RunFingerprint],
        max_evals: int = 50,
        *,
        target_fingerprint: RunFingerprint,
    ) -> list[Evaluation]:
        """Reuse compatible history only after a complete target identity is supplied.

        Collects the best evaluations from each binding-compatible run, up to
        ``max_evals`` total. Incomplete or malformed target identities are
        refused before any history read. The result remains a list so rejected
        history rows stay visible to compatible callers.
        """
        if max_evals <= 0 or not similar_runs:
            return []
        if not isinstance(
            target_fingerprint, RunFingerprint
        ) or not self._has_complete_binding_basis(target_fingerprint):
            return []

        prepared: list[list[Evaluation]] = []
        for fp in similar_runs:
            if not self._binding_matches(target_fingerprint, fp):
                continue

            rows = self._load_run_evaluations(fp)
            evaluations = [
                self._deserialize_evaluation(row, fp.run_id, expected_fingerprint=fp)
                for row in rows
            ]
            evaluations.sort(
                key=lambda evaluation: self._evaluation_sort_key(evaluation, target_fingerprint)
            )
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
            "history_schema_version": "5",
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
                    "score_status": objective.score_status.value,
                    "score_assessment": (
                        None
                        if objective.score_assessment is None
                        else objective.score_assessment.to_payload()
                    ),
                }
                for objective in evaluation.objectives
            ],
            "scalar_score": evaluation.scalar_score,
            "score_status": evaluation.score_status.value,
            "score_assessment": (
                None
                if evaluation.score_assessment is None
                else evaluation.score_assessment.to_payload()
            ),
            "stage_a_passed": evaluation.stage_a_passed,
            "stage_b_result": evaluation.stage_b_result,
            "status": evaluation.status.value,
            "timestamp": evaluation.timestamp.isoformat(),
            "wall_time_seconds": evaluation.wall_time_seconds,
            "provenance_ref": evaluation.provenance_ref,
            "metadata": dict(evaluation.metadata),
        }

    @classmethod
    def _binding_matches(cls, target: RunFingerprint, source: RunFingerprint) -> bool:
        """Return whether both complete, typed run bases identify reusable observations."""
        if not cls._has_complete_binding_basis(target) or not cls._has_complete_binding_basis(
            source
        ):
            return False
        return (
            target.space_hash == source.space_hash
            and set(target.objective_names) == set(source.objective_names)
            and target.bounds == source.bounds
            and target.split == source.split
            and target.units == source.units
            and target.origin == source.origin
            and target.tenant_id == source.tenant_id
            and target.objective_directions == source.objective_directions
            and target.objective_rule_specs == source.objective_rule_specs
        )

    @classmethod
    def _has_complete_binding_basis(cls, run_fingerprint: RunFingerprint) -> bool:
        """Require every identity field to have been supplied and retain its declared type."""
        if not set(_HISTORY_BINDING_FIELDS).issubset(run_fingerprint.model_fields_set):
            return False
        if set(run_fingerprint.objective_rule_specs) != set(run_fingerprint.objective_names) or set(
            run_fingerprint.objective_directions
        ) != set(run_fingerprint.objective_names):
            return False
        expected_units: dict[str, str] = {}
        for name, rule_spec in run_fingerprint.objective_rule_specs.items():
            expected_unit = configured_objective_unit(rule_spec)
            if expected_unit is None:
                return False
            expected_units[name] = expected_unit
        if run_fingerprint.units != expected_units:
            return False
        try:
            cls._fingerprint_from_identity_fields(cls._identity_payload(run_fingerprint))
        except (TypeError, ValueError):
            return False
        return True

    @staticmethod
    def _identity_payload(run_fingerprint: RunFingerprint) -> dict[str, Any]:
        """Project only the complete source/run identity carried by a history row."""
        return {field: getattr(run_fingerprint, field) for field in _HISTORY_BINDING_FIELDS}

    @staticmethod
    def _fingerprint_from_identity_fields(fields: dict[str, Any]) -> RunFingerprint:
        """Validate a complete run identity without coercing malformed JSON fields."""
        if "objective_rule_specs" not in fields:
            fields["objective_rule_specs"] = {}
        missing = [field for field in _HISTORY_BINDING_FIELDS if field not in fields]
        if missing:
            raise ValueError(f"transfer history identity is missing {', '.join(missing)}")
        for field in ("run_id", "space_hash"):
            value = fields[field]
            if not isinstance(value, str) or not value.strip():
                raise TypeError(f"transfer history identity {field} must be a non-empty string")
        names = fields["objective_names"]
        if (
            not isinstance(names, list)
            or not names
            or any(not isinstance(name, str) or not name.strip() for name in names)
            or len(set(names)) != len(names)
        ):
            raise TypeError("transfer history identity objective_names must be unique strings")
        for field in ("bounds", "units", "objective_directions", "objective_rule_specs"):
            value = fields[field]
            if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
                raise TypeError(
                    f"transfer history identity {field} must be an object with string keys"
                )
        units = fields["units"]
        if any(not isinstance(value, str) or not value.strip() for value in units.values()):
            raise TypeError("transfer history identity units must be non-empty strings")
        for field in _HISTORY_NULLABLE_FIELDS:
            value = fields[field]
            if value is not None and not isinstance(value, str):
                raise TypeError(f"transfer history identity {field} must be a string or null")
        directions = fields["objective_directions"]
        if any(value not in _HISTORY_DIRECTIONS for value in directions.values()):
            raise ValueError(
                "transfer history identity objective_directions contains an unknown value"
            )
        if not set(directions).issubset(names):
            raise ValueError(
                "transfer history identity objective_directions names an unknown objective"
            )
        rule_specs = fields["objective_rule_specs"]
        if not set(rule_specs).issubset(names):
            raise ValueError(
                "transfer history identity objective_rule_specs names an unknown objective"
            )
        for name, rule_spec in rule_specs.items():
            if not isinstance(rule_spec, str) or not rule_spec.strip():
                raise TypeError(
                    f"transfer history identity objective_rule_specs[{name!r}] must be a string"
                )
            try:
                parsed = json.loads(rule_spec)
                if not isinstance(parsed, dict) or not parsed:
                    raise ValueError("objective rule spec must be a non-empty object")
                canonical = json.dumps(
                    parsed, sort_keys=True, separators=(",", ":"), allow_nan=False
                )
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"transfer history identity objective_rule_specs[{name!r}] is malformed"
                ) from exc
            if canonical != rule_spec:
                raise ValueError(
                    f"transfer history identity objective_rule_specs[{name!r}] is not canonical"
                )
        return RunFingerprint(**{field: fields[field] for field in _HISTORY_BINDING_FIELDS})

    @classmethod
    def _fingerprint_from_index_metadata(
        cls, run_id: str, metadata: dict[str, Any], history_ref: ArtifactRef
    ) -> RunFingerprint:
        """Build a source fingerprint only from complete, typed index metadata."""
        if not isinstance(run_id, str) or not run_id.strip():
            raise TypeError("transfer history index key must be a non-empty run id")
        if not isinstance(metadata, dict):
            raise TypeError("transfer history index metadata must be an object")
        if "objective_rule_specs" not in metadata:
            metadata = {**metadata, "objective_rule_specs": {}}
        missing = [field for field in _HISTORY_INDEX_FIELDS if field not in metadata]
        if missing:
            raise ValueError(f"transfer history index metadata is missing {', '.join(missing)}")
        fields = {
            "run_id": run_id,
            **{field: metadata[field] for field in _HISTORY_INDEX_FIELDS},
        }
        indexed_fingerprint = cls._fingerprint_from_identity_fields(fields)
        return indexed_fingerprint.model_copy(
            update={
                "best_score": metadata.get("best_score"),
                "history_ref": history_ref,
            }
        )

    @classmethod
    def _history_cache_key(cls, history_ref: ArtifactRef, run_fingerprint: RunFingerprint) -> str:
        """Bind cache entries to the full selected ref and complete run identity."""
        artifact_id, kind, media_type, profile_sha256 = artifact_ref_identity_key(history_ref)
        return fingerprint(
            {
                "artifact_ref": {
                    "artifact_id": artifact_id,
                    "kind": kind,
                    "media_type": media_type,
                    "manifest_profile_sha256": profile_sha256,
                },
                "run_identity": cls._identity_payload(run_fingerprint),
            },
            canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        )

    @staticmethod
    def _history_ref_from_metadata(meta: dict[str, Any]) -> ArtifactRef | None:
        """Convert indexed history metadata into its exact typed immutable reference."""
        artifact_id = meta.get("artifact_id")
        if artifact_id is None:
            return None
        try:
            return ArtifactRef(
                artifact_id=artifact_id,
                kind="search.transfer.history",
                media_type="application/json",
                manifest_profile_sha256=meta.get("manifest_profile_sha256"),
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _evaluation_matches_fingerprint(
        evaluation: Evaluation, fingerprint: RunFingerprint
    ) -> bool:
        """Admit a history row only when each score coordinate matches selected rules."""
        if not TransferLearningManager._has_complete_binding_basis(fingerprint):
            return False
        return TransferLearningManager._evaluation_matches_objective_rules(
            evaluation.objectives,
            evaluation.stage_b_result,
            fingerprint,
            require_scalar_score=len(fingerprint.objective_names) == 1,
            evaluation=evaluation,
        )

    @staticmethod
    def _evaluation_sort_key(
        evaluation: Evaluation, target_fingerprint: RunFingerprint
    ) -> tuple[int, float]:
        """Sort only a single selected, rule-bound coordinate; preserve multi-score order."""
        if len(target_fingerprint.objective_names) != 1:
            return (1, 0.0)
        name = target_fingerprint.objective_names[0]
        if not _evaluation_matches_selected_objectives(
            evaluation,
            objective_names=target_fingerprint.objective_names,
            objective_directions={
                name: OptimizationDirection(target_fingerprint.objective_directions[name])
            },
            objective_rule_specs=target_fingerprint.objective_rule_specs,
            require_scalar_score=True,
        ):
            return (1, 0.0)
        objective = next(item for item in evaluation.objectives if item.name == name)
        normalized = objective.normalized_value
        if not math.isfinite(normalized):
            return (1, 0.0)
        return (0, normalized)

    @classmethod
    def _deserialize_evaluation(
        cls,
        row: dict[str, Any],
        run_id: str,
        *,
        expected_fingerprint: RunFingerprint | None = None,
    ) -> Evaluation:
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
            source_result = row.get("stage_b_result")
            objectives = [
                cls._deserialize_objective(
                    payload,
                    source_result,
                    expected_rule_spec=(
                        expected_fingerprint.objective_rule_specs.get(str(payload.get("name")))
                        if expected_fingerprint is not None and isinstance(payload, dict)
                        else None
                    ),
                    expected_direction=(
                        expected_fingerprint.objective_directions.get(str(payload.get("name")))
                        if expected_fingerprint is not None and isinstance(payload, dict)
                        else None
                    ),
                )
                for payload in objectives_payload
            ]
            raw_scalar_score = row.get("scalar_score")
            if raw_scalar_score is None:
                scalar_score = None
            else:
                if isinstance(raw_scalar_score, bool):
                    raise TypeError("scalar_score must be numeric or null")
                scalar_score = float(raw_scalar_score)
                if not math.isfinite(scalar_score):
                    raise ValueError("scalar_score must be finite")
            status = EvaluationStatus(row.get("status", EvaluationStatus.SUCCESS.value))
            assessment_payload = row.get("score_assessment")
            assessment = (
                ObjectiveScoreAssessment.from_payload(assessment_payload)
                if assessment_payload is not None
                else None
            )
            if assessment is not None and not score_assessment_matches_source(
                assessment, source_result
            ):
                assessment = _unestablished_score_assessment("source_reconciliation_failed")
                metadata["transfer_score_assessment"] = "source_reconciliation_failed"
            if expected_fingerprint is None or not cls._evaluation_matches_objective_rules(
                objectives, source_result, expected_fingerprint
            ):
                assessment = _unestablished_score_assessment(
                    "selected_objective_rule_not_reconciled"
                )
                metadata["transfer_score_assessment"] = "selected_objective_rule_not_reconciled"
            score_status = (
                assessment.status
                if assessment is not None
                else ObjectiveScoreStatus.NOT_ESTABLISHED
            )
            if assessment is None:
                metadata.setdefault("transfer_score_assessment", "legacy_basis_not_established")
            normalized = row.get("params_normalized", [])
            if not isinstance(normalized, (list, tuple)):
                raise TypeError("params_normalized must be a list or tuple")
            evaluation = Evaluation(
                candidate_id=candidate_id,
                params=params,
                params_normalized=tuple(normalized),
                objectives=objectives,
                scalar_score=scalar_score,
                stage_a_passed=bool(row.get("stage_a_passed", False)),
                stage_b_result=source_result,
                status=status,
                provenance_ref=provenance_ref,
                wall_time_seconds=float(row.get("wall_time_seconds", 0.0)),
                metadata=metadata,
                score_status=score_status,
                score_assessment=assessment,
            )
            return evaluation
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
                scalar_score=None,
                stage_a_passed=False,
                status=EvaluationStatus.STAGE_B_ERROR,
                provenance_ref=provenance_ref,
                metadata=metadata,
            )

    @staticmethod
    def _evaluation_matches_objective_rules(
        objectives: list[ObjectiveValue],
        source: Any,
        fingerprint: RunFingerprint,
        *,
        require_scalar_score: bool = False,
        evaluation: Evaluation | None = None,
    ) -> bool:
        return _evaluation_matches_selected_objectives(
            evaluation if evaluation is not None else objectives,
            objective_names=fingerprint.objective_names,
            objective_directions={
                name: OptimizationDirection(fingerprint.objective_directions[name])
                for name in fingerprint.objective_names
            },
            objective_rule_specs=fingerprint.objective_rule_specs,
            source_result=source,
            require_scalar_score=require_scalar_score,
        )

    @staticmethod
    def _deserialize_objective(
        payload: Any,
        source_result: Any,
        *,
        expected_rule_spec: str | None = None,
        expected_direction: str | None = None,
    ) -> ObjectiveValue:
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
        assessment_payload = payload.get("score_assessment")
        assessment = (
            ObjectiveScoreAssessment.from_payload(assessment_payload)
            if assessment_payload is not None
            else None
        )
        if assessment is not None and not score_assessment_matches_source(
            assessment, source_result
        ):
            assessment = _unestablished_score_assessment("source_reconciliation_failed")
        score_status = (
            assessment.status if assessment is not None else ObjectiveScoreStatus.NOT_ESTABLISHED
        )
        weight = float(payload.get("weight", 1.0))
        threshold = float(payload["threshold"]) if payload.get("threshold") is not None else None
        objective = ObjectiveValue(
            name=str(name),
            raw_value=raw_value,
            direction=direction,
            weight=weight,
            is_satisfied=bool(payload.get("is_satisfied", True)),
            threshold=threshold,
            score_status=score_status,
            score_assessment=assessment,
        )
        if (
            expected_rule_spec is None
            or expected_direction is None
            or not objective_value_matches_rule(
                objective,
                source_result,
                expected_name=str(name),
                expected_direction=OptimizationDirection(expected_direction),
                expected_rule_spec=expected_rule_spec,
            )
        ):
            return ObjectiveValue(
                name=str(name),
                raw_value=raw_value,
                direction=direction,
                weight=weight,
                is_satisfied=bool(payload.get("is_satisfied", True)),
                threshold=threshold,
                score_status=ObjectiveScoreStatus.NOT_ESTABLISHED,
                score_assessment=_unestablished_score_assessment(
                    "selected_objective_rule_not_reconciled"
                ),
            )
        return objective

    def _load_run_evaluations(
        self,
        source: RunFingerprint | str,
    ) -> list[dict[str, Any]]:
        """Load evaluations from a verified, exact immutable history reference.

        Legacy callers without a reference resolve the current indexed reference, then
        use the same full-reference byte cache as direct snapshot callers.
        """
        if isinstance(source, RunFingerprint):
            run_id = source.run_id
            history_ref = source.history_ref
            expected_fingerprint = source
        else:
            run_id = source
            history_ref = None
            expected_fingerprint = None

        if history_ref is not None:
            if expected_fingerprint is None or not self._has_complete_binding_basis(
                expected_fingerprint
            ):
                raise ValueError("exact history ref requires a complete expected run fingerprint")
            cache_key = self._history_cache_key(history_ref, expected_fingerprint)
            cached_bytes = self._cached_history_bytes(cache_key)
            if cached_bytes is not None:
                try:
                    rows, _ = self._read_history(
                        history_ref,
                        expected_fingerprint,
                        raw_payload_bytes=cached_bytes,
                    )
                except ValueError:
                    self._discard_cached_history(cache_key)
                    raise
                return rows
            rows, raw_payload_bytes = self._read_history(history_ref, expected_fingerprint)
            self._remember_history_bytes(cache_key, raw_payload_bytes)
            return rows

        # Exact key lookup is independent of ANN ranking and binds this generation's
        # owned metadata to the selected ref; missing keys do not become nearest hits.
        meta = self._index.lookup_metadata(run_id)
        if meta is None:
            return []
        selected_ref = self._history_ref_from_metadata(meta)
        if selected_ref is None:
            raise ValueError(f"Indexed transfer history for {run_id} has no valid reference")
        try:
            indexed_fingerprint = self._fingerprint_from_index_metadata(run_id, meta, selected_ref)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid indexed transfer history for {run_id}: {exc}") from exc
        if expected_fingerprint is not None and not self._binding_matches(
            expected_fingerprint, indexed_fingerprint
        ):
            return []
        cache_key = self._history_cache_key(selected_ref, indexed_fingerprint)
        cached_bytes = self._cached_history_bytes(cache_key)
        if cached_bytes is not None:
            try:
                rows, _ = self._read_history(
                    selected_ref, indexed_fingerprint, raw_payload_bytes=cached_bytes
                )
            except ValueError:
                self._discard_cached_history(cache_key)
                raise
            return rows
        rows, raw_payload_bytes = self._read_history(selected_ref, indexed_fingerprint)
        self._remember_history_bytes(cache_key, raw_payload_bytes)
        return rows

    def _cached_history_bytes(self, key: str) -> bytes | None:
        """Return one immutable LRU payload without exposing cached decoded objects."""
        payload = self._eval_cache.get(key)
        if payload is None:
            return None
        if type(payload) is not bytes:
            self._discard_cached_history(key)
            raise ValueError("transfer history cache payload is not immutable bytes")
        self._eval_cache.move_to_end(key)
        return payload

    def _discard_cached_history(self, key: str) -> None:
        """Remove one cached payload and maintain the exact retained-byte counter."""
        payload = self._eval_cache.pop(key, None)
        if payload is not None:
            self._eval_cache_bytes -= len(payload)

    def _remember_history_bytes(self, key: str, payload: bytes) -> None:
        """Retain verified canonical payload bytes within the declared LRU budget."""
        if type(payload) is not bytes:
            raise TypeError("transfer history cache accepts only immutable bytes")
        self._discard_cached_history(key)
        if len(payload) > self._MAX_HISTORY_CACHE_BYTES:
            return
        self._eval_cache[key] = payload
        self._eval_cache_bytes += len(payload)
        while (
            len(self._eval_cache) > self._MAX_HISTORY_CACHE_ENTRIES
            or self._eval_cache_bytes > self._MAX_HISTORY_CACHE_BYTES
        ):
            _, evicted = self._eval_cache.popitem(last=False)
            self._eval_cache_bytes -= len(evicted)

    def _read_history(
        self,
        ref: ArtifactRef,
        expected_fingerprint: RunFingerprint,
        *,
        raw_payload_bytes: bytes | None = None,
    ) -> tuple[list[dict[str, Any]], bytes]:
        """Verify the selected Core bytes and bind their complete history identity."""
        from polisyos.core.artifacts import read_core_json_artifact

        if ref.kind != "search.transfer.history" or ref.media_type != "application/json":
            raise ValueError("Transfer history ref has an unexpected kind or media type")
        if not self._has_complete_binding_basis(expected_fingerprint):
            raise ValueError("Transfer history read requires a complete expected run fingerprint")
        try:
            read = read_core_json_artifact(
                self._store,
                ref,
                raw_payload_bytes=raw_payload_bytes,
                manifest_profile_sha256=ref.manifest_profile_sha256,
            )
            data = read.value
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Malformed transfer history artifact {ref.artifact_id}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"Transfer history artifact {ref.artifact_id} is not an object")
        history_schema_version = data.get("history_schema_version", "3")
        if history_schema_version not in {"3", "4", "5"}:
            raise ValueError(
                f"Transfer history artifact {ref.artifact_id} has an unsupported schema version"
            )
        if history_schema_version in {"4", "5"} and "objective_rule_specs" not in data:
            raise ValueError(
                f"Transfer history artifact {ref.artifact_id} is missing identity field "
                "objective_rule_specs"
            )
        if history_schema_version == "5" and "units" not in data:
            raise ValueError(
                f"Transfer history artifact {ref.artifact_id} is missing selected objective units"
            )
        fields: dict[str, Any] = {}
        for field in _HISTORY_BINDING_FIELDS:
            if field == "objective_rule_specs" and field not in data:
                fields[field] = {}
            elif field in data:
                fields[field] = data[field]
            elif field in _HISTORY_NULLABLE_FIELDS and getattr(expected_fingerprint, field) is None:
                # CanonSpec excludes null values; only an explicitly null index
                # field permits this known wire omission.
                fields[field] = None
            else:
                raise ValueError(
                    f"Transfer history artifact {ref.artifact_id} is missing identity field {field}"
                )
        try:
            stored_fingerprint = self._fingerprint_from_identity_fields(fields)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Transfer history artifact {ref.artifact_id} has invalid identity: {exc}"
            ) from exc
        if stored_fingerprint.run_id != expected_fingerprint.run_id:
            raise ValueError("Transfer history run_id does not match its selected index entry")
        if not self._binding_matches(expected_fingerprint, stored_fingerprint):
            mismatched = [
                field
                for field in _HISTORY_BINDING_FIELDS
                if field != "run_id"
                and getattr(stored_fingerprint, field) != getattr(expected_fingerprint, field)
            ]
            field = mismatched[0] if mismatched else "identity"
            raise ValueError(f"Transfer history {field} does not match its selected index entry")
        evaluations = data.get("evaluations")
        if not isinstance(evaluations, list) or any(
            not isinstance(row, dict) for row in evaluations
        ):
            raise ValueError(f"Transfer history artifact {ref.artifact_id} has invalid evaluations")
        return list(evaluations), read.raw_payload_bytes
