"""Core autotune contracts for benchmark splits, promotion rules, and CAS persistence."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, Self, TypeVar, cast

from pydantic import ConfigDict, Field

from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.canon.canon_json import CanonSpec

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.core.artifacts.protocol import ArtifactStore

    _ValidatorFunc = TypeVar("_ValidatorFunc", bound=Callable[..., object])

    class _PydanticBaseModel:
        model_config: ClassVar[ConfigDict]

        def __init__(self, /, **data: object) -> None: ...

        @classmethod
        def model_validate(cls, obj: object) -> Self: ...

        @classmethod
        def model_validate_json(cls, json_data: str) -> Self: ...

    def model_validator(*, mode: str) -> Callable[[_ValidatorFunc], _ValidatorFunc]: ...
else:
    from pydantic import BaseModel as _PydanticBaseModel
    from pydantic import model_validator


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


class MutationArtifact(_PydanticBaseModel):
    """Mutation artifact public type."""

    model_config = ConfigDict(extra="forbid")

    loop_id: str = Field(..., min_length=1, max_length=128)
    artifact_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    search_space_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    notes: list[str] = Field(default_factory=list)


class BenchmarkSplitManifest(_PydanticBaseModel):
    """Assignment manifest for benchmark split ids."""

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
    def _validate_unique_assignments(self) -> BenchmarkSplitManifest:
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


class BenchmarkSuite(_PydanticBaseModel):
    """Benchmark suite public type."""

    model_config = ConfigDict(extra="forbid")

    suite_id: str = Field(..., min_length=1, max_length=128)
    suite_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    kind: str = Field(default="generic", min_length=1, max_length=128)
    dataset_path: str | None = None
    split_manifest_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkEvaluation(_PydanticBaseModel):
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


class PromotionPolicy(_PydanticBaseModel):
    """Promotion rule that decides when a candidate may replace the current champion."""

    model_config = ConfigDict(extra="forbid")

    loop_id: str = Field(..., min_length=1, max_length=128)
    primary_metric: str = Field(..., min_length=1, max_length=128)
    direction: MetricDirection = MetricDirection.MAXIMIZE
    compare_split: BenchmarkSplit = BenchmarkSplit.HOLDOUT
    min_improvement: float = 0.0
    min_sample_count: int = Field(default=0, ge=0)
    required_guardrails: list[str] = Field(default_factory=list)


class ChampionPointer(_PydanticBaseModel):
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


class PromotionDecision(_PydanticBaseModel):
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
    ) -> dict[str, Any]: ...


class BenchmarkedEvaluator(Protocol):
    """Benchmarked evaluator public type."""

    def evaluate(
        self,
        candidate_ref: ArtifactRef,
        suite_ref: ArtifactRef,
        context: dict[str, Any],
    ) -> BenchmarkEvaluation: ...


class MutationCodec(Protocol):
    """Mutation codec public type."""

    def encode(self, payload: MutationArtifact) -> MutationArtifact: ...

    def decode(self, payload: dict[str, Any]) -> MutationArtifact: ...


class RuntimeLoader(Protocol):
    """Protocol for loading the latest mutation artifact or baseline runtime state."""

    def load(self, context: dict[str, Any] | None = None) -> MutationArtifact | None: ...


@dataclass(frozen=True)
class SearchLoopSpec:
    """Wiring contract for one autotune loop."""

    loop_id: str
    mutation_codec: MutationCodec | None
    candidate_generator: Any | None
    benchmark_evaluator: BenchmarkedEvaluator
    promotion_policy: PromotionPolicy
    runtime_loader: RuntimeLoader | None = None


def default_cas_root() -> Path:
    """Return the default CAS root used by autotune persistence helpers."""
    return Path(os.environ.get("POLISYOS_CAS_ROOT", ".polisyos/cas"))


def default_search_registry_root() -> Path:
    """Return the default filesystem root for autotune search registries."""
    return Path(os.environ.get("POLISYOS_SEARCH_REGISTRY_ROOT", ".polisyos/search_registry"))


def default_store(root: Path | None = None) -> ArtifactStore:
    """Construct the default autotune artifact store from the storage factory boundary."""
    return cast(
        "ArtifactStore",
        build_artifact_store(
            ArtifactStoreConfig(
                backend="filesystem",
                root=str(root or default_cas_root()),
            )
        ),
    )


def load_json_artifact(store: ArtifactStore, ref: ArtifactRef | str) -> object:
    """Load json artifact."""
    artifact_id = ref.artifact_id if isinstance(ref, ArtifactRef) else ArtifactID(ref)
    return from_canonical_bytes(store.get_bytes(artifact_id))


def load_model_artifact(
    store: ArtifactStore,
    ref: ArtifactRef | str,
    model_cls: type[_PydanticBaseModel],
) -> _PydanticBaseModel:
    """Load model artifact."""
    payload = load_json_artifact(store, ref)
    return model_cls.model_validate(payload)


def _producer(component: str) -> str:
    return component


def persist_mutation_artifact(
    store: ArtifactStore,
    artifact: MutationArtifact,
    *,
    kind: str | None = None,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a mutation artifact to CAS and return its typed artifact reference."""
    return store.put_json(
        artifact,
        ArtifactWriteOptions(
            kind=kind or f"scientist.autotune.{artifact.loop_id}.candidate",
            media_type="application/json",
            schema=SchemaInfo(
                name=f"polisyos.scientist.methods.autotune.{artifact.__class__.__name__}",
                version=artifact.artifact_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def persist_benchmark_suite(
    store: ArtifactStore,
    suite: BenchmarkSuite,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a benchmark suite definition to CAS and return its typed artifact reference."""
    return store.put_json(
        suite,
        ArtifactWriteOptions(
            kind=f"scientist.autotune.{suite.kind}.suite",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.methods.autotune.BenchmarkSuite",
                version=suite.suite_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def persist_split_manifest(
    store: ArtifactStore,
    split_manifest: BenchmarkSplitManifest,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a benchmark split manifest so the loop can replay its evaluation partitions."""
    return store.put_json(
        split_manifest,
        ArtifactWriteOptions(
            kind="scientist.autotune.split_manifest",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.methods.autotune.BenchmarkSplitManifest",
                version=split_manifest.suite_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def persist_benchmark_evaluation(
    store: ArtifactStore,
    evaluation: BenchmarkEvaluation,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a benchmark evaluation record and return its typed artifact reference."""
    merged_inputs = list(inputs or [])
    merged_inputs.append(
        InputRef(
            artifact_id=evaluation.candidate_ref.artifact_id,
            role="candidate",
        )
    )
    return store.put_json(
        evaluation,
        ArtifactWriteOptions(
            kind=f"scientist.autotune.{evaluation.loop_id}.evaluation",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.methods.autotune.BenchmarkEvaluation",
                version=evaluation.suite_version,
            ),
            inputs=merged_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def read_split_manifest(path: Path) -> BenchmarkSplitManifest:
    """Load a benchmark split manifest from disk and validate its split assignments."""
    return BenchmarkSplitManifest.model_validate_json(path.read_text(encoding="utf-8"))


def resolve_item_split(
    item_id: str,
    split_manifest: BenchmarkSplitManifest,
) -> BenchmarkSplit | None:
    """Resolve item split."""
    return split_manifest.split_for(item_id)
