"""Core autotune contracts for benchmark splits, promotion rules, and CAS persistence."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Protocol, Self, TypeVar, cast

from pydantic import (
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
)

from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    ProducerInfo,
    SchemaInfo,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.canon.canon_json import CanonSpec

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from polisyos.core.artifacts.protocol import ArtifactStore

    _ValidatorFunc = TypeVar("_ValidatorFunc", bound=Callable[..., object])

    class _PydanticBaseModel:
        model_config: ClassVar[ConfigDict]

        def __init__(self, /, **data: object) -> None: ...

        def model_dump(
            self, *, mode: str = "python", exclude: set[str] | None = None
        ) -> dict[str, Any]: ...

        def model_dump_json(
            self, *, indent: int | None = None, exclude_none: bool = False
        ) -> str: ...

        def model_copy(
            self, *, update: Mapping[str, Any] | None = None, deep: bool = False
        ) -> Self: ...

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
    data_basis: Literal["unbound", "candidate_only", "dataset"] = "unbound"
    dataset_ref: ArtifactRef | None = None
    split_manifest_ref: ArtifactRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_input_refs(self) -> Self:
        if self.data_basis == "dataset":
            if self.dataset_ref is None or self.split_manifest_ref is None:
                raise ValueError("benchmark_immutable_inputs_required")
        elif self.dataset_ref is not None or self.split_manifest_ref is not None:
            raise ValueError("benchmark_data_basis_mismatch")
        return self


class BenchmarkComparisonBasis(_PydanticBaseModel):
    """Bind a technical comparison to consumed inputs and the executed evaluator build.

    This record establishes reproducible comparison identity, not appointment
    of an evaluator or permission to publish an authoritative policy claim.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["benchmark-comparison.v1"] = "benchmark-comparison.v1"
    suite_ref: ArtifactRef
    data_basis: Literal["candidate_only", "dataset"]
    dataset_ref: ArtifactRef | None = None
    split_manifest_ref: ArtifactRef | None = None
    evaluator_profile: SchemaInfo
    policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_input_refs(self) -> Self:
        if (self.data_basis == "dataset") != (
            self.dataset_ref is not None and self.split_manifest_ref is not None
        ) or ((self.dataset_ref is None) != (self.split_manifest_ref is None)):
            raise ValueError("benchmark_comparison_input_refs_mismatch")
        return self


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
    comparison_basis: BenchmarkComparisonBasis | None = None
    incumbent_evaluation_ref: ArtifactRef | None = None
    comparison_predecessor_candidate_ref: ArtifactRef | None = None
    comparison_predecessor_evaluation_ref: ArtifactRef | None = None
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
    unit: str | None = Field(default=None, min_length=1, max_length=64)
    direction: MetricDirection = MetricDirection.MAXIMIZE
    compare_split: BenchmarkSplit = BenchmarkSplit.HOLDOUT
    min_improvement: float = 0.0
    min_sample_count: int = Field(default=0, ge=0)
    required_guardrails: list[str] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def _serialize_canonical_policy(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Preserve the historical policy shape while retaining explicit units."""
        payload = cast("dict[str, Any]", handler(self))
        if self.unit is None:
            payload.pop("unit", None)
        return payload


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


class _ChampionReader(Protocol):
    def get(self, loop_id: str) -> ChampionPointer | None: ...


def resolve_comparison_incumbent(
    registry: _ChampionReader | None, context: Mapping[str, Any], loop_id: str
) -> ChampionPointer | None:
    """Capture the exact incumbent used by both primary metrics and guardrails.

    Native comparison supplies a detached snapshot before either evaluation.
    Direct evaluator callers retain the existing canonical registry read.
    """
    if "benchmark_comparison_incumbent" in context:
        incumbent = context["benchmark_comparison_incumbent"]
        if incumbent is not None and (
            not isinstance(incumbent, ChampionPointer) or incumbent.loop_id != loop_id
        ):
            raise ValueError("benchmark_comparison_incumbent_invalid")
        return incumbent
    return registry.get(loop_id) if registry is not None else None


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
    return build_artifact_store(
        ArtifactStoreConfig(backend="filesystem", root=str(root or default_cas_root()))
    )


def load_json_artifact(store: ArtifactStore, ref: ArtifactRef | str) -> object:
    """Load json artifact."""
    artifact_id = ref if isinstance(ref, ArtifactRef) else ArtifactID(ref)
    return from_canonical_bytes(store.get_bytes(artifact_id))


def load_model_artifact[ArtifactModel: _PydanticBaseModel](
    store: ArtifactStore,
    ref: ArtifactRef | str,
    model_cls: type[ArtifactModel],
) -> ArtifactModel:
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
    merged_inputs = list(inputs or [])
    if (
        suite.data_basis != "dataset"
        and suite.dataset_path is not None
        and suite.split_manifest_path is not None
    ):
        dataset_ref = store.put_bytes(
            Path(suite.dataset_path).read_bytes(),
            ArtifactWriteOptions(
                kind="scientist.autotune.benchmark_dataset",
                media_type="application/x-ndjson",
            ),
        )
        split = read_split_manifest(Path(suite.split_manifest_path))
        if split.suite_id != suite.suite_id or split.suite_version != suite.suite_version:
            raise ValueError("benchmark_split_suite_mismatch")
        split_ref = persist_split_manifest(
            store,
            split,
            inputs=[input_ref_from_artifact_ref(dataset_ref, role="benchmark_dataset")],
        )
        suite = suite.model_copy(
            update={
                "data_basis": "dataset",
                "dataset_ref": dataset_ref,
                "split_manifest_ref": split_ref,
            }
        )
    elif (suite.dataset_path is None) != (suite.split_manifest_path is None):
        raise ValueError("benchmark_inputs_incomplete")
    if suite.data_basis == "dataset":
        load_benchmark_inputs(store, suite)
        assert suite.dataset_ref is not None
        assert suite.split_manifest_ref is not None
        merged_inputs.extend(
            [
                input_ref_from_artifact_ref(suite.dataset_ref, role="benchmark_dataset"),
                input_ref_from_artifact_ref(suite.split_manifest_ref, role="benchmark_split"),
            ]
        )
    elif suite.dataset_ref is not None or suite.split_manifest_ref is not None:
        raise ValueError("benchmark_data_basis_mismatch")
    return store.put_json(
        suite,
        ArtifactWriteOptions(
            kind=f"scientist.autotune.{suite.kind}.suite",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.methods.autotune.BenchmarkSuite",
                version=suite.suite_version,
            ),
            inputs=merged_inputs,
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
    merged_inputs.append(input_ref_from_artifact_ref(evaluation.candidate_ref, role="candidate"))
    if evaluation.comparison_basis is not None:
        basis = evaluation.comparison_basis
        merged_inputs.append(input_ref_from_artifact_ref(basis.suite_ref, role="benchmark_suite"))
        if basis.dataset_ref is not None:
            merged_inputs.append(
                input_ref_from_artifact_ref(basis.dataset_ref, role="benchmark_dataset")
            )
        if basis.split_manifest_ref is not None:
            merged_inputs.append(
                input_ref_from_artifact_ref(basis.split_manifest_ref, role="benchmark_split")
            )
    if evaluation.incumbent_evaluation_ref is not None:
        merged_inputs.append(
            input_ref_from_artifact_ref(
                evaluation.incumbent_evaluation_ref,
                role="comparison_incumbent_evaluation",
            )
        )
    for ref, role in (
        (evaluation.comparison_predecessor_candidate_ref, "comparison_predecessor_candidate"),
        (evaluation.comparison_predecessor_evaluation_ref, "comparison_predecessor_evaluation"),
    ):
        if ref is not None:
            merged_inputs.append(input_ref_from_artifact_ref(ref, role=role))
    return store.put_json(
        evaluation,
        ArtifactWriteOptions(
            kind=f"scientist.autotune.{evaluation.loop_id}.evaluation",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.methods.autotune.BenchmarkEvaluation",
                version=evaluation.suite_version,
            ),
            producer=ProducerInfo(
                component="polisyos.scientist.methods.autotune.benchmark_evaluator",
                version="1.0",
            ),
            inputs=merged_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def read_split_manifest(path: Path) -> BenchmarkSplitManifest:
    """Load a benchmark split manifest from disk and validate its split assignments."""
    return BenchmarkSplitManifest.model_validate_json(path.read_text(encoding="utf-8"))


def load_benchmark_inputs(
    store: ArtifactStore,
    suite: BenchmarkSuite,
) -> tuple[list[dict[str, Any]], BenchmarkSplitManifest]:
    """Resolve the immutable dataset and split actually consumed by an evaluator."""
    if (
        suite.data_basis != "dataset"
        or suite.dataset_ref is None
        or suite.split_manifest_ref is None
    ):
        raise ValueError("benchmark_immutable_inputs_required")
    if (
        suite.dataset_ref.kind != "scientist.autotune.benchmark_dataset"
        or suite.dataset_ref.media_type != "application/x-ndjson"
    ):
        raise ValueError("benchmark_dataset_type_mismatch")
    if suite.split_manifest_ref.kind != "scientist.autotune.split_manifest":
        raise ValueError("benchmark_split_type_mismatch")
    require_benchmark_input(
        store, suite.split_manifest_ref, suite.dataset_ref, role="benchmark_dataset"
    )
    rows = [
        json.loads(line)
        for line in store.get_bytes(suite.dataset_ref).decode().splitlines()
        if line.strip()
    ]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("benchmark_dataset_rows_must_be_objects")
    split = load_model_artifact(store, suite.split_manifest_ref, BenchmarkSplitManifest)
    if split.suite_id != suite.suite_id or split.suite_version != suite.suite_version:
        raise ValueError("benchmark_split_suite_mismatch")
    ids = [str(row[split.id_field]) for row in rows]
    assigned = [item for value in BenchmarkSplit for item in split.ids_for_split(value)]
    if (
        len(ids) != len(set(ids))
        or len(assigned) != len(set(assigned))
        or set(ids) != set(assigned)
    ):
        raise ValueError("benchmark_split_dataset_denominator_mismatch")
    return rows, split


def require_benchmark_input(
    store: ArtifactStore,
    ref: ArtifactRef,
    expected: ArtifactRef,
    *,
    role: str,
) -> None:
    """Require one exact upstream manifest view for a benchmark lineage role."""
    manifest = store.get_manifest(ref)
    views = {
        (str(item.artifact_id), item.manifest_profile_sha256)
        for item in manifest.inputs
        if item.role == role
    }
    identity = artifact_ref_identity_key(expected)
    if views != {(identity[0], identity[3])}:
        raise ValueError(f"benchmark_input_mismatch:{role}")
    store.get_bytes(expected)


def benchmark_policy_sha256(policy: PromotionPolicy) -> str:
    """Return the canonical policy identity, including metric units and split."""
    return hashlib.sha256(
        json.dumps(
            policy.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def benchmark_evaluator_profile(evaluator: BenchmarkedEvaluator) -> SchemaInfo:
    """Identify the executed evaluator module bytes without claiming appointment."""
    cls = type(evaluator)
    path = inspect.getsourcefile(cls)
    if path is None:
        raise ValueError("benchmark_evaluator_source_unavailable")
    return SchemaInfo(
        name=f"{cls.__module__}.{cls.__qualname__}",
        version=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
    )


def benchmark_comparison_basis(
    store: ArtifactStore,
    suite_ref: ArtifactRef,
    policy: PromotionPolicy,
    evaluator_profile: SchemaInfo,
) -> BenchmarkComparisonBasis:
    """Build one comparison identity from content-resolved suite/input references."""
    suite = load_model_artifact(store, suite_ref, BenchmarkSuite)
    if suite_ref.kind != f"scientist.autotune.{suite.kind}.suite":
        raise ValueError("benchmark_suite_type_mismatch")
    manifest = store.get_manifest(suite_ref)
    if (
        manifest.artifact_schema is None
        or manifest.artifact_schema.name != "polisyos.scientist.methods.autotune.BenchmarkSuite"
        or manifest.artifact_schema.version != suite.suite_version
    ):
        raise ValueError("benchmark_suite_schema_mismatch")
    if suite.data_basis == "dataset":
        load_benchmark_inputs(store, suite)
        assert suite.dataset_ref is not None
        assert suite.split_manifest_ref is not None
        require_benchmark_input(store, suite_ref, suite.dataset_ref, role="benchmark_dataset")
        require_benchmark_input(store, suite_ref, suite.split_manifest_ref, role="benchmark_split")
    elif suite.data_basis != "candidate_only":
        raise ValueError("benchmark_comparison_basis_unbound")
    return BenchmarkComparisonBasis(
        suite_ref=suite_ref,
        data_basis=suite.data_basis,
        dataset_ref=suite.dataset_ref,
        split_manifest_ref=suite.split_manifest_ref,
        evaluator_profile=evaluator_profile,
        policy_sha256=benchmark_policy_sha256(policy),
    )


def resolve_item_split(
    item_id: str,
    split_manifest: BenchmarkSplitManifest,
) -> BenchmarkSplit | None:
    """Resolve item split."""
    return split_manifest.split_for(item_id)
