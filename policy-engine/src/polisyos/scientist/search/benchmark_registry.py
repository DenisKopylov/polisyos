"""Concrete benchmark registry for blueprint-native Scientist runtime."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    default_search_registry_root,
)

_PHASE_D4_ROTATION_GROUP = "phase_d4_v1"
_PHASE_D4_SUITE_IDS = frozenset(
    {
        "strategic_gaming_v1",
        "multiplicity_disclosure_v1",
        "abstraction_leakage_v1",
    }
)


class BenchmarkRegistryEntry(BaseModel):
    """One persisted benchmark asset binding."""

    model_config = ConfigDict(extra="forbid")

    split_type: str = Field(min_length=1)
    artifact_ref: ArtifactRef
    run_id: str | None = None
    loop_id: str | None = None
    suite_id: str | None = None
    suite_version: str | None = None
    family: str | None = None
    query_type: str | None = None
    estimator_name: str | None = None
    readiness_target: str | None = None
    artifact_kind: str | None = None
    rotation_group: str | None = None
    produced_by_run_id: str | None = None
    validation_contour: str | None = None
    visibility: str | None = None
    holdout_family: str | None = None
    benchmark_revision: str | None = None
    comparator_profile: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class FrontierBenchmarkBundle(BaseModel):
    """Scoped view of benchmark evidence required for one promotion family."""

    model_config = ConfigDict(extra="forbid")

    family: str
    claim_mode: str
    query_type: str | None = None
    estimator_name: str | None = None
    readiness_target: str | None = None
    loop_id: str | None = None
    run_id: str | None = None
    selection_evaluation_ref: ArtifactRef | None = None
    hidden_holdout_evaluation_ref: ArtifactRef | None = None
    rotating_challenge_evaluation_refs: list[ArtifactRef] = Field(default_factory=list)
    sentinel_evaluation_refs: list[ArtifactRef] = Field(default_factory=list)
    adversarial_artifact_refs: list[ArtifactRef] = Field(default_factory=list)

    def missing_for_promotion(self) -> list[str]:
        missing: list[str] = []
        if self.claim_mode == "proof_only":
            return missing
        if self.selection_evaluation_ref is None:
            missing.append("selection_evaluation_ref")
        if self.claim_mode == "bounds":
            if not self.sentinel_evaluation_refs:
                missing.append("sentinel_evaluation_refs")
            if self.family != "causal_core":
                if self.hidden_holdout_evaluation_ref is None:
                    missing.append("hidden_holdout_evaluation_ref")
                if not self.rotating_challenge_evaluation_refs:
                    missing.append("rotating_challenge_evaluation_refs")
            return missing
        if self.hidden_holdout_evaluation_ref is None:
            missing.append("hidden_holdout_evaluation_ref")
        if self.family != "causal_core" and not self.rotating_challenge_evaluation_refs:
            missing.append("rotating_challenge_evaluation_refs")
        return missing


class BenchmarkRegistrySnapshot(BaseModel):
    """Serializable snapshot of benchmark registry contents."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    entries: list[BenchmarkRegistryEntry] = Field(default_factory=list)


def _normalize_split_type(split_type: str) -> str:
    normalized = str(split_type or "").strip().lower()
    if not normalized:
        raise ValueError("split_type must be a non-empty string")
    if normalized == "visible":
        return BenchmarkSplit.SELECTION.value
    if normalized in {item.value for item in BenchmarkSplit}:
        return normalized
    return normalized


def _normalize_scope_text(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _scope_value(entry: BenchmarkRegistryEntry, field_name: str) -> str | None:
    direct = getattr(entry, field_name, None)
    if direct is not None:
        return _normalize_scope_text(direct)
    return _normalize_scope_text(entry.metadata.get(field_name))


def _phase_d4_suite_id(entry: BenchmarkRegistryEntry) -> str | None:
    suite_id = _normalize_scope_text(entry.suite_id) or _normalize_scope_text(
        entry.metadata.get("challenge_suite_id")
    )
    rotation_group = _normalize_scope_text(entry.rotation_group) or _normalize_scope_text(
        entry.metadata.get("rotation_group")
    )
    if suite_id in _PHASE_D4_SUITE_IDS:
        return suite_id
    if rotation_group == _PHASE_D4_ROTATION_GROUP and suite_id is not None:
        return suite_id
    return None


def _dedupe_phase_d4_entries(
    entries: list[BenchmarkRegistryEntry],
) -> list[BenchmarkRegistryEntry]:
    deduped: list[BenchmarkRegistryEntry] = []
    seen_suite_ids: set[str] = set()
    for entry in entries:
        suite_id = _phase_d4_suite_id(entry)
        if suite_id is None:
            deduped.append(entry)
            continue
        if suite_id in seen_suite_ids:
            continue
        seen_suite_ids.add(suite_id)
        deduped.append(entry)
    return deduped


class BenchmarkRegistry:
    """Persistent runtime authority for benchmark assets by split."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = (root or default_search_registry_root() / "benchmarks").resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        split_type: str,
        ref: ArtifactRef,
        *,
        metadata: dict[str, Any] | None = None,
        run_id: str | None = None,
        loop_id: str | None = None,
        suite_id: str | None = None,
        suite_version: str | None = None,
        family: str | None = None,
        query_type: str | None = None,
        estimator_name: str | None = None,
        readiness_target: str | None = None,
        artifact_kind: str | None = None,
        rotation_group: str | None = None,
        produced_by_run_id: str | None = None,
        validation_contour: str | None = None,
        visibility: str | None = None,
        holdout_family: str | None = None,
        benchmark_revision: str | None = None,
        comparator_profile: str | None = None,
    ) -> None:
        normalized = _normalize_split_type(split_type)
        snapshot = self._load_snapshot()
        entry = BenchmarkRegistryEntry(
            split_type=normalized,
            artifact_ref=ref,
            run_id=str(run_id).strip() or None if run_id is not None else None,
            loop_id=str(loop_id).strip() or None if loop_id is not None else None,
            suite_id=str(suite_id).strip() or None if suite_id is not None else None,
            suite_version=str(suite_version).strip() or None
            if suite_version is not None
            else None,
            family=_normalize_scope_text(family),
            query_type=_normalize_scope_text(query_type),
            estimator_name=_normalize_scope_text(estimator_name),
            readiness_target=_normalize_scope_text(readiness_target),
            artifact_kind=_normalize_scope_text(artifact_kind) or ref.kind,
            rotation_group=_normalize_scope_text(rotation_group),
            produced_by_run_id=str(produced_by_run_id).strip() or None
            if produced_by_run_id is not None
            else None,
            validation_contour=_normalize_scope_text(validation_contour),
            visibility=_normalize_scope_text(visibility),
            holdout_family=_normalize_scope_text(holdout_family),
            benchmark_revision=_normalize_scope_text(benchmark_revision),
            comparator_profile=_normalize_scope_text(comparator_profile),
            metadata=dict(metadata or {}),
        )
        deduped = [
            item
            for item in snapshot.entries
            if not (
                item.split_type == entry.split_type
                and item.artifact_ref == entry.artifact_ref
                and item.run_id == entry.run_id
                and item.loop_id == entry.loop_id
                and item.suite_id == entry.suite_id
                and _scope_value(item, "family") == entry.family
                and _scope_value(item, "query_type") == entry.query_type
                and _scope_value(item, "estimator_name") == entry.estimator_name
                and _scope_value(item, "readiness_target") == entry.readiness_target
                and _scope_value(item, "validation_contour") == entry.validation_contour
                and _scope_value(item, "visibility") == entry.visibility
                and _scope_value(item, "holdout_family") == entry.holdout_family
                and _scope_value(item, "benchmark_revision") == entry.benchmark_revision
                and _scope_value(item, "comparator_profile") == entry.comparator_profile
            )
        ]
        deduped.append(entry)
        snapshot = snapshot.model_copy(
            update={
                "updated_at": datetime.now(UTC),
                "entries": deduped,
            }
        )
        self._write_snapshot(snapshot)

    def get(
        self,
        split_type: str,
        *,
        run_id: str | None = None,
        loop_id: str | None = None,
        suite_id: str | None = None,
        family: str | None = None,
        query_type: str | None = None,
        estimator_name: str | None = None,
        readiness_target: str | None = None,
        validation_contour: str | None = None,
        visibility: str | None = None,
        holdout_family: str | None = None,
        benchmark_revision: str | None = None,
        comparator_profile: str | None = None,
    ) -> list[ArtifactRef]:
        return [
            item.artifact_ref
            for item in self._filtered_entries(
                split_type,
                run_id=run_id,
                loop_id=loop_id,
                suite_id=suite_id,
                family=family,
                query_type=query_type,
                estimator_name=estimator_name,
                readiness_target=readiness_target,
                validation_contour=validation_contour,
                visibility=visibility,
                holdout_family=holdout_family,
                benchmark_revision=benchmark_revision,
                comparator_profile=comparator_profile,
            )
        ]

    def _filtered_entries(
        self,
        split_type: str,
        *,
        run_id: str | None = None,
        loop_id: str | None = None,
        suite_id: str | None = None,
        family: str | None = None,
        query_type: str | None = None,
        estimator_name: str | None = None,
        readiness_target: str | None = None,
        validation_contour: str | None = None,
        visibility: str | None = None,
        holdout_family: str | None = None,
        benchmark_revision: str | None = None,
        comparator_profile: str | None = None,
    ) -> list[BenchmarkRegistryEntry]:
        normalized = _normalize_split_type(split_type)
        snapshot = self._load_snapshot()
        family = _normalize_scope_text(family)
        query_type = _normalize_scope_text(query_type)
        estimator_name = _normalize_scope_text(estimator_name)
        readiness_target = _normalize_scope_text(readiness_target)
        validation_contour = _normalize_scope_text(validation_contour)
        visibility = _normalize_scope_text(visibility)
        holdout_family = _normalize_scope_text(holdout_family)
        benchmark_revision = _normalize_scope_text(benchmark_revision)
        comparator_profile = _normalize_scope_text(comparator_profile)
        filtered = [
            item
            for item in snapshot.entries
            if item.split_type == normalized
            and (run_id is None or item.run_id == run_id)
            and (loop_id is None or _scope_value(item, "loop_id") == _normalize_scope_text(loop_id))
            and (suite_id is None or item.suite_id == suite_id)
            and (family is None or _scope_value(item, "family") == family)
            and (query_type is None or _scope_value(item, "query_type") == query_type)
            and (
                estimator_name is None
                or _scope_value(item, "estimator_name") == estimator_name
            )
            and (
                readiness_target is None
                or _scope_value(item, "readiness_target") == readiness_target
            )
            and (
                validation_contour is None
                or _scope_value(item, "validation_contour") == validation_contour
            )
            and (
                visibility is None
                or _scope_value(item, "visibility") == visibility
            )
            and (
                holdout_family is None
                or _scope_value(item, "holdout_family") == holdout_family
            )
            and (
                benchmark_revision is None
                or _scope_value(item, "benchmark_revision") == benchmark_revision
            )
            and (
                comparator_profile is None
                or _scope_value(item, "comparator_profile") == comparator_profile
            )
        ]
        filtered.sort(key=lambda item: item.created_at.timestamp(), reverse=True)
        return filtered

    def latest(
        self,
        split_type: str,
        *,
        run_id: str | None = None,
        loop_id: str | None = None,
        suite_id: str | None = None,
        family: str | None = None,
        query_type: str | None = None,
        estimator_name: str | None = None,
        readiness_target: str | None = None,
        validation_contour: str | None = None,
        visibility: str | None = None,
        holdout_family: str | None = None,
        benchmark_revision: str | None = None,
        comparator_profile: str | None = None,
    ) -> ArtifactRef | None:
        refs = self.get(
            split_type,
            run_id=run_id,
            loop_id=loop_id,
            suite_id=suite_id,
            family=family,
            query_type=query_type,
            estimator_name=estimator_name,
            readiness_target=readiness_target,
            validation_contour=validation_contour,
            visibility=visibility,
            holdout_family=holdout_family,
            benchmark_revision=benchmark_revision,
            comparator_profile=comparator_profile,
        )
        return refs[0] if refs else None

    def record_evaluation(
        self,
        evaluation: BenchmarkEvaluation,
        ref: ArtifactRef,
        *,
        run_id: str | None = None,
        family: str | None = None,
        query_type: str | None = None,
        estimator_name: str | None = None,
        readiness_target: str | None = None,
        rotation_group: str | None = None,
        produced_by_run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        validation_contour: str | None = None,
        visibility: str | None = None,
        holdout_family: str | None = None,
        benchmark_revision: str | None = None,
        comparator_profile: str | None = None,
    ) -> None:
        combined_metadata = dict(evaluation.metadata)
        combined_metadata.update(metadata or {})
        self.record(
            evaluation.resolved_runtime_split_type().value,
            ref,
            run_id=run_id,
            loop_id=evaluation.loop_id,
            suite_id=evaluation.suite_id,
            suite_version=evaluation.suite_version,
            family=family or _normalize_scope_text(combined_metadata.get("family")),
            query_type=query_type or _normalize_scope_text(combined_metadata.get("query_type")),
            estimator_name=estimator_name
            or _normalize_scope_text(combined_metadata.get("estimator_name")),
            readiness_target=readiness_target
            or _normalize_scope_text(combined_metadata.get("readiness_target")),
            artifact_kind="scientist.benchmark_evaluation",
            rotation_group=rotation_group
            or _normalize_scope_text(combined_metadata.get("rotation_group")),
            produced_by_run_id=produced_by_run_id,
            validation_contour=validation_contour
            or _normalize_scope_text(combined_metadata.get("validation_contour")),
            visibility=visibility
            or _normalize_scope_text(combined_metadata.get("visibility")),
            holdout_family=holdout_family
            or _normalize_scope_text(combined_metadata.get("holdout_family")),
            benchmark_revision=benchmark_revision
            or _normalize_scope_text(combined_metadata.get("benchmark_revision")),
            comparator_profile=comparator_profile
            or _normalize_scope_text(combined_metadata.get("comparator_profile")),
            metadata=combined_metadata,
        )

    def resolve_family_bundle(
        self,
        *,
        family: str,
        claim_mode: str,
        run_id: str | None = None,
        loop_id: str | None = None,
        query_type: str | None = None,
        estimator_name: str | None = None,
        readiness_target: str | None = None,
    ) -> FrontierBenchmarkBundle:
        rotating_entries = _dedupe_phase_d4_entries(
            self._filtered_entries(
                BenchmarkSplit.ROTATING_CHALLENGE.value,
                run_id=run_id,
                loop_id=loop_id,
                family=family,
                query_type=query_type,
                estimator_name=estimator_name,
                readiness_target=readiness_target,
            )
        )
        return FrontierBenchmarkBundle(
            family=_normalize_scope_text(family) or "causal_core",
            claim_mode=str(claim_mode or "estimation").strip().lower() or "estimation",
            query_type=_normalize_scope_text(query_type),
            estimator_name=_normalize_scope_text(estimator_name),
            readiness_target=_normalize_scope_text(readiness_target),
            loop_id=_normalize_scope_text(loop_id),
            run_id=_normalize_scope_text(run_id),
            selection_evaluation_ref=self.latest(
                BenchmarkSplit.SELECTION.value,
                run_id=run_id,
                loop_id=loop_id,
                family=family,
                query_type=query_type,
                estimator_name=estimator_name,
                readiness_target=readiness_target,
            ),
            hidden_holdout_evaluation_ref=self.latest(
                BenchmarkSplit.HIDDEN_HOLDOUT.value,
                run_id=run_id,
                loop_id=loop_id,
                family=family,
                query_type=query_type,
                estimator_name=estimator_name,
                readiness_target=readiness_target,
            ),
            rotating_challenge_evaluation_refs=[
                item.artifact_ref for item in rotating_entries
            ],
            sentinel_evaluation_refs=self.get(
                BenchmarkSplit.SENTINEL.value,
                run_id=run_id,
                loop_id=loop_id,
                family=family,
                query_type=query_type,
                estimator_name=estimator_name,
                readiness_target=readiness_target,
            ),
            adversarial_artifact_refs=self.get(
                BenchmarkSplit.ADVERSARIAL.value,
                run_id=run_id,
                loop_id=loop_id,
                family=family,
                query_type=query_type,
                estimator_name=estimator_name,
                readiness_target=readiness_target,
            ),
        )

    def require_promotion_evidence(
        self,
        *,
        family: str,
        claim_mode: str,
        run_id: str | None = None,
        loop_id: str | None = None,
        query_type: str | None = None,
        estimator_name: str | None = None,
        readiness_target: str | None = None,
    ) -> list[str]:
        bundle = self.resolve_family_bundle(
            family=family,
            claim_mode=claim_mode,
            run_id=run_id,
            loop_id=loop_id,
            query_type=query_type,
            estimator_name=estimator_name,
            readiness_target=readiness_target,
        )
        return bundle.missing_for_promotion()

    def snapshot(self) -> BenchmarkRegistrySnapshot:
        return self._load_snapshot()

    def _snapshot_path(self) -> Path:
        return self._root / "benchmark_registry.json"

    def _load_snapshot(self) -> BenchmarkRegistrySnapshot:
        path = self._snapshot_path()
        if not path.exists():
            return BenchmarkRegistrySnapshot()
        return BenchmarkRegistrySnapshot.model_validate_json(path.read_text(encoding="utf-8"))

    def _write_snapshot(self, snapshot: BenchmarkRegistrySnapshot) -> None:
        path = self._snapshot_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = snapshot.model_dump_json(indent=2)
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as tmp:
            tmp.write(payload)
            temp_path = Path(tmp.name)
        temp_path.replace(path)


__all__ = [
    "BenchmarkRegistry",
    "BenchmarkRegistryEntry",
    "FrontierBenchmarkBundle",
    "BenchmarkRegistrySnapshot",
]
