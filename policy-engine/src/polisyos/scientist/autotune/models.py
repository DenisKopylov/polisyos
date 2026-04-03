"""Public autotune models module API."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.canon.canon_json import CanonSpec


class MetricDirection(str, Enum):
    """Metric direction public type."""
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class BenchmarkSplit(str, Enum):
    """Benchmark split public type."""
    SELECTION = "selection"
    HOLDOUT = "holdout"
    HIDDEN_HOLDOUT = "hidden_holdout"
    ROTATING_CHALLENGE = "rotating_challenge"
    ADVERSARIAL = "adversarial"
    SENTINEL = "sentinel"


class MutationArtifact(BaseModel):
    """Mutation artifact public type."""
    model_config = ConfigDict(extra="forbid")

    loop_id: str = Field(..., min_length=1, max_length=128)
    artifact_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    search_space_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    notes: list[str] = Field(default_factory=list)


class BenchmarkSplitManifest(BaseModel):
    """Benchmark split manifest data model."""
    model_config = ConfigDict(extra="forbid")

    suite_id: str = Field(..., min_length=1, max_length=128)
    suite_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    id_field: str = Field(default="id", min_length=1, max_length=128)
    selection_ids: list[str] = Field(default_factory=list)
    holdout_ids: list[str] = Field(default_factory=list)
    hidden_holdout_ids: list[str] = Field(default_factory=list)
    rotating_challenge_ids: list[str] = Field(default_factory=list)
    adversarial_ids: list[str] = Field(default_factory=list)
    sentinel_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_assignments(self) -> "BenchmarkSplitManifest":
        assignments: dict[str, BenchmarkSplit] = {}
        for split in BenchmarkSplit:
            for item_id in self.ids_for_split(split):
                existing = assignments.get(item_id)
                if existing is not None and existing is not split:
                    raise ValueError(
                        f"Benchmark item '{item_id}' is assigned to both "
                        f"'{existing.value}' and '{split.value}'."
                    )
                assignments[item_id] = split
        return self

    def ids_for_split(self, split: BenchmarkSplit) -> list[str]:
        if split is BenchmarkSplit.SELECTION:
            return list(self.selection_ids)
        if split is BenchmarkSplit.HOLDOUT:
            return list(self.holdout_ids)
        if split is BenchmarkSplit.HIDDEN_HOLDOUT:
            return list(self.hidden_holdout_ids)
        if split is BenchmarkSplit.ROTATING_CHALLENGE:
            return list(self.rotating_challenge_ids)
        if split is BenchmarkSplit.ADVERSARIAL:
            return list(self.adversarial_ids)
        if split is BenchmarkSplit.SENTINEL:
            return list(self.sentinel_ids)
        return []

    def split_for(self, item_id: str) -> BenchmarkSplit | None:
        for split in BenchmarkSplit:
            if item_id in set(self.ids_for_split(split)):
                return split
        return None


class BenchmarkSuite(BaseModel):
    """Benchmark suite public type."""
    model_config = ConfigDict(extra="forbid")

    suite_id: str = Field(..., min_length=1, max_length=128)
    suite_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    kind: str = Field(default="generic", min_length=1, max_length=128)
    dataset_path: str | None = None
    split_manifest_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkEvaluation(BaseModel):
    """Benchmark evaluation public type."""
    model_config = ConfigDict(extra="forbid")

    loop_id: str = Field(..., min_length=1, max_length=128)
    suite_id: str = Field(..., min_length=1, max_length=128)
    suite_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    candidate_ref: ArtifactRef
    selection_metrics: dict[str, float] = Field(default_factory=dict)
    holdout_metrics: dict[str, float] = Field(default_factory=dict)
    sample_counts: dict[str, int] = Field(default_factory=dict)
    guardrails: dict[str, bool] = Field(default_factory=dict)
    promotable: bool = False
    status: str = Field(default="ok", min_length=1, max_length=64)
    notes: list[str] = Field(default_factory=list)
    runtime_split_type: BenchmarkSplit | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def metrics_for_split(self, split: BenchmarkSplit) -> dict[str, float]:
        if split == BenchmarkSplit.SELECTION:
            return dict(self.selection_metrics)
        return dict(self.holdout_metrics)

    def resolved_runtime_split_type(self) -> BenchmarkSplit:
        if self.runtime_split_type is not None:
            return self.runtime_split_type
        suite_name = self.suite_id.strip().lower()
        if "hidden_holdout" in suite_name:
            return BenchmarkSplit.HIDDEN_HOLDOUT
        if "rotating" in suite_name or "challenge" in suite_name:
            return BenchmarkSplit.ROTATING_CHALLENGE
        if "adversarial" in suite_name:
            return BenchmarkSplit.ADVERSARIAL
        if "sentinel" in suite_name:
            return BenchmarkSplit.SENTINEL
        if "holdout" in suite_name:
            return BenchmarkSplit.HOLDOUT
        return BenchmarkSplit.SELECTION

    def matches_runtime_split(self, *expected: BenchmarkSplit) -> bool:
        if not expected:
            return True
        return self.resolved_runtime_split_type() in set(expected)

    def primary_value(self, *, split: BenchmarkSplit, metric: str) -> float | None:
        metrics = self.metrics_for_split(split)
        value = metrics.get(metric)
        return float(value) if value is not None else None

    def sample_count(self, *, split: BenchmarkSplit) -> int:
        if split is BenchmarkSplit.HIDDEN_HOLDOUT:
            return int(
                self.sample_counts.get(
                    BenchmarkSplit.HIDDEN_HOLDOUT.value,
                    self.sample_counts.get(BenchmarkSplit.HOLDOUT.value, 0),
                )
            )
        return int(self.sample_counts.get(split.value, 0))


class PromotionPolicy(BaseModel):
    """Promotion policy data model."""
    model_config = ConfigDict(extra="forbid")

    loop_id: str = Field(..., min_length=1, max_length=128)
    primary_metric: str = Field(..., min_length=1, max_length=128)
    direction: MetricDirection = MetricDirection.MAXIMIZE
    compare_split: BenchmarkSplit = BenchmarkSplit.HOLDOUT
    min_improvement: float = 0.0
    min_sample_count: int = Field(default=0, ge=0)
    required_guardrails: list[str] = Field(default_factory=list)


class ChampionPointer(BaseModel):
    """Champion pointer public type."""
    model_config = ConfigDict(extra="forbid")

    loop_id: str = Field(..., min_length=1, max_length=128)
    candidate_ref: ArtifactRef
    evaluation_ref: ArtifactRef
    metrics: dict[str, float] = Field(default_factory=dict)
    suite_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    promoted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    search_space_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromotionDecision(BaseModel):
    """Promotion decision public type."""
    model_config = ConfigDict(extra="forbid")

    loop_id: str = Field(..., min_length=1, max_length=128)
    promoted: bool
    reason: str = Field(..., min_length=1, max_length=256)
    champion: ChampionPointer | None = None
    previous_champion: ChampionPointer | None = None


class CandidateGenerator(Protocol):
    """Protocol for autotune candidate generators."""

    def generate(
        self,
        history: list[Any],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        ...


class BenchmarkedEvaluator(Protocol):
    """Benchmarked evaluator public type."""
    def evaluate(
        self,
        candidate_ref: ArtifactRef,
        suite_ref: ArtifactRef,
        context: dict[str, Any],
    ) -> BenchmarkEvaluation:
        ...


class MutationCodec(Protocol):
    """Mutation codec public type."""
    def encode(self, payload: MutationArtifact) -> MutationArtifact:
        ...

    def decode(self, payload: dict[str, Any]) -> MutationArtifact:
        ...


class RuntimeLoader(Protocol):
    """Runtime loader implementation."""
    def load(self, context: dict[str, Any] | None = None) -> MutationArtifact | None:
        ...


@dataclass(frozen=True)
class SearchLoopSpec:
    """Search loop spec data model."""
    loop_id: str
    mutation_codec: MutationCodec | None
    candidate_generator: Any | None
    benchmark_evaluator: BenchmarkedEvaluator
    promotion_policy: PromotionPolicy
    runtime_loader: RuntimeLoader | None = None


def default_cas_root() -> Path:
    """Default cas root helper."""
    return Path(os.environ.get("POLISYOS_CAS_ROOT", ".polisyos"))


def default_search_registry_root() -> Path:
    """Default search registry root helper."""
    return Path(os.environ.get("POLISYOS_SEARCH_REGISTRY_ROOT", ".polisyos/search_registry"))


def default_store(root: Path | None = None) -> FileSystemCAS:
    """Default store helper."""
    return FileSystemCAS(root or default_cas_root())


def load_json_artifact(store: FileSystemCAS, ref: ArtifactRef | str) -> Any:
    """Load json artifact."""
    artifact_id = ref.artifact_id if isinstance(ref, ArtifactRef) else ref
    return from_canonical_bytes(store.get_bytes(artifact_id))


def load_model_artifact(
    store: FileSystemCAS,
    ref: ArtifactRef | str,
    model_cls: type[BaseModel],
) -> BaseModel:
    """Load model artifact."""
    payload = load_json_artifact(store, ref)
    return model_cls.model_validate(payload)


def _producer(component: str) -> str:
    return component


def persist_mutation_artifact(
    store: FileSystemCAS,
    artifact: MutationArtifact,
    *,
    kind: str | None = None,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist mutation artifact helper."""
    return store.put_json(
        artifact,
        PutOptions(
            kind=kind or f"scientist.autotune.{artifact.loop_id}.candidate",
            media_type="application/json",
            schema=SchemaInfo(
                name=f"polisyos.scientist.autotune.{artifact.__class__.__name__}",
                version=artifact.artifact_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def persist_benchmark_suite(
    store: FileSystemCAS,
    suite: BenchmarkSuite,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist benchmark suite helper."""
    return store.put_json(
        suite,
        PutOptions(
            kind=f"scientist.autotune.{suite.kind}.suite",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.autotune.BenchmarkSuite", version=suite.suite_version),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def persist_split_manifest(
    store: FileSystemCAS,
    split_manifest: BenchmarkSplitManifest,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist split manifest helper."""
    return store.put_json(
        split_manifest,
        PutOptions(
            kind="scientist.autotune.split_manifest",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.autotune.BenchmarkSplitManifest",
                version=split_manifest.suite_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def persist_benchmark_evaluation(
    store: FileSystemCAS,
    evaluation: BenchmarkEvaluation,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist benchmark evaluation helper."""
    merged_inputs = list(inputs or [])
    merged_inputs.append(InputRef(artifact_id=evaluation.candidate_ref.artifact_id, role="candidate"))
    return store.put_json(
        evaluation,
        PutOptions(
            kind=f"scientist.autotune.{evaluation.loop_id}.evaluation",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.autotune.BenchmarkEvaluation",
                version=evaluation.suite_version,
            ),
            inputs=merged_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def read_split_manifest(path: Path) -> BenchmarkSplitManifest:
    """Read split manifest helper."""
    return BenchmarkSplitManifest.model_validate_json(path.read_text(encoding="utf-8"))


def resolve_item_split(
    item_id: str,
    split_manifest: BenchmarkSplitManifest,
) -> BenchmarkSplit | None:
    """Resolve item split."""
    return split_manifest.split_for(item_id)
