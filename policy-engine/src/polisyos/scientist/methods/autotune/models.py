"""Core autotune contracts for benchmark splits, promotion rules, and CAS persistence."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from math import isfinite
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic, Literal, Protocol, TypeVar

from pydantic import (
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
)

from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    ProducerInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import fingerprint
from polisyos.core.canon.canon_json import CanonSpec
from polisyos.core.contracts import DataSnapshot

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pydantic import BaseModel as _PydanticBaseModel
    from pydantic import model_validator

    from polisyos.core.artifacts.protocol import ArtifactStore
else:
    from pydantic import BaseModel as _PydanticBaseModel
    from pydantic import model_validator


_BENCHMARK_EVALUATION_KIND_PREFIX = "scientist.autotune."
_BENCHMARK_EVALUATION_KIND_SUFFIX = ".evaluation"
_BENCHMARK_EVALUATION_SCHEMA_NAME = "polisyos.scientist.methods.autotune.BenchmarkEvaluation"


def _benchmark_evaluation_artifact_kind(loop_id: str) -> str:
    """Return the canonical artifact kind for one benchmark evaluation loop."""
    return f"{_BENCHMARK_EVALUATION_KIND_PREFIX}{loop_id}{_BENCHMARK_EVALUATION_KIND_SUFFIX}"


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

    def partition_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        suite: BenchmarkSuite,
    ) -> dict[BenchmarkSplit, list[dict[str, Any]]]:
        """Partition actual dataset rows against this suite's complete assignments.

        Args:
            rows: Dataset rows carrying the declared string identity field.
            suite: Persisted suite whose identity selected this split manifest.

        Returns:
            Rows grouped by their verified manifest assignments.

        Raises:
            ValueError: The suite, row identities, or complete assignment basis differs.
        """
        if self.suite_id != suite.suite_id:
            raise ValueError("benchmark_split_suite_id_mismatch")
        if self.suite_version != suite.suite_version:
            raise ValueError("benchmark_split_suite_version_mismatch")
        assignments: dict[str, BenchmarkSplit] = {}
        for split in BenchmarkSplit:
            for item_id in self.ids_for_split(split):
                if item_id in assignments:
                    raise ValueError("benchmark_split_duplicate_assignment")
                assignments[item_id] = split
        partitions: dict[BenchmarkSplit, list[dict[str, Any]]] = {
            split: [] for split in BenchmarkSplit
        }
        seen: set[str] = set()
        for row in rows:
            if self.id_field not in row:
                raise ValueError("benchmark_split_row_id_missing")
            item_id = row[self.id_field]
            if not isinstance(item_id, str) or not item_id:
                raise ValueError("benchmark_split_row_id_invalid")
            if item_id in seen:
                raise ValueError("benchmark_split_duplicate_row_id")
            seen.add(item_id)
            split = assignments.get(item_id)
            if split is None:
                raise ValueError("benchmark_split_dataset_ids_mismatch")
            partitions[split].append(row)
        if seen != set(assignments):
            raise ValueError("benchmark_split_dataset_ids_mismatch")
        return partitions


class BenchmarkSuite(_PydanticBaseModel):
    """Benchmark suite public type."""

    model_config = ConfigDict(extra="forbid")

    suite_id: str = Field(..., min_length=1, max_length=128)
    suite_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    kind: str = Field(default="generic", min_length=1, max_length=128)
    dataset_path: str | None = None
    split_manifest_path: str | None = None
    data_snapshot_ref: ArtifactRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_serializer(mode="wrap")
    def _serialize_legacy_suite_shape(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, Any]:
        """Keep historical suite bytes when no source snapshot is selected."""
        raw_payload = handler(self)
        if not isinstance(raw_payload, dict):
            raise TypeError("benchmark suite serializer must return an object")
        payload: dict[str, Any] = {}
        for key, value in raw_payload.items():
            if not isinstance(key, str):
                raise TypeError("benchmark suite serializer keys must be strings")
            payload[key] = value
        if self.data_snapshot_ref is None:
            payload.pop("data_snapshot_ref", None)
        return payload


class BayesianSourceProfile(_PydanticBaseModel):
    """Measured profile of the optimizer that proposed one search candidate."""

    model_config = ConfigDict(extra="forbid")

    profile_kind: Literal["configured_native_gp", "injected_optimizer", "fallback"]
    optimizer_fqn: str | None = None
    optimizer_config_fingerprint: str | None = None
    proposal_source: str = Field(..., min_length=1, max_length=128)
    search_space_fingerprint: str | None = None
    input_transform_fingerprint: str | None = None
    input_transform_state_fingerprint: str | None = None
    outcome_transform_fingerprint: str | None = None
    outcome_transform_state_fingerprint: str | None = None
    noise_model_fingerprint: str | None = None
    noise_model_state_fingerprint: str | None = None
    objective_fingerprint: str | None = None
    context_fingerprint: str | None = None
    training_corpus_fingerprint: str | None = None
    training_observation_count: int | None = Field(default=None, ge=0)
    gp_model_fqn: str | None = None
    warm_start_eligible: bool = False

    @model_validator(mode="after")
    def _validate_warm_start_profile(self) -> BayesianSourceProfile:
        compatibility_fields = (
            self.search_space_fingerprint,
            self.input_transform_fingerprint,
            self.input_transform_state_fingerprint,
            self.outcome_transform_fingerprint,
            self.outcome_transform_state_fingerprint,
            self.noise_model_fingerprint,
            self.noise_model_state_fingerprint,
            self.objective_fingerprint,
            self.context_fingerprint,
        )
        if self.warm_start_eligible and (
            self.profile_kind != "configured_native_gp"
            or self.proposal_source != "bayesian_acquisition"
            or not self.optimizer_fqn
            or not self.optimizer_config_fingerprint
            or not all(value and value.strip() for value in compatibility_fields)
            or not self.gp_model_fqn
            or not self.training_corpus_fingerprint
            or self.training_observation_count is None
            or self.training_observation_count < 1
        ):
            raise ValueError(
                "Only a complete configured native GP profile can admit warm-start data"
            )
        return self


class SearchGPFitBound(_PydanticBaseModel):
    """One exact search-space dimension used to recompute a native GP fit."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: str = Field(..., min_length=1, max_length=128)
    lower: float
    upper: float
    dtype: Literal["continuous", "integer", "categorical", "log_continuous"]
    log_scale: bool
    categories: list[Any] | None = None


class SearchMethodRunProfile(_PydanticBaseModel):
    """Candidate-grade identity of one configured Search → MethodJob run."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1", "2"] = "1"
    loop_id: str = Field(..., min_length=1, max_length=128)
    suite_ref: ArtifactRef
    method_fqn: str = Field(..., min_length=1, max_length=512)
    method_version: str | None = Field(default=None, max_length=128)
    method_params_fingerprint: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    candidate_input_bindings: dict[str, str]
    data_snapshot_bindings: dict[str, str]
    search_parameter_bindings: dict[str, str] = Field(default_factory=dict)
    search_parameter_bounds: list[SearchGPFitBound] = Field(default_factory=list)
    method_signature_abi_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    data_snapshot_ref: ArtifactRef | None = None
    data_ref: ArtifactRef | None = None
    data_sample_count: int | None = Field(default=None, ge=1)
    method_seed: int
    primary_metric: str = Field(..., min_length=1, max_length=128)
    direction: Literal["minimize", "maximize"]
    split: Literal["selection", "holdout"]
    unit: str | None = Field(default=None, max_length=128)
    search_space_fingerprint: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    context_fingerprint: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    objective_fingerprint: str = Field(..., pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_data_binding(self) -> SearchMethodRunProfile:
        has_bindings = bool(self.data_snapshot_bindings)
        if has_bindings != (self.data_snapshot_ref is not None and self.data_ref is not None):
            raise ValueError("Search GP profile data bindings require exact snapshot and data refs")
        if has_bindings != (self.data_sample_count is not None):
            raise ValueError("Search GP profile data bindings require a recomputed sample count")
        if self.method_seed < 0:
            raise ValueError("Search GP profile seed must be non-negative")
        if len(set(self.candidate_input_bindings) & set(self.data_snapshot_bindings)):
            raise ValueError("Search GP method input slots must have one source")
        if not self.search_parameter_bindings:
            if (
                self.schema_version != "1"
                or self.search_parameter_bounds
                or self.method_signature_abi_digest is not None
            ):
                raise ValueError("Unbound Search GP profiles must retain the schema 1 shape")
            return self
        if self.schema_version != "2":
            raise ValueError("Search parameter bindings require Search GP profile schema 2")
        search_names = set(self.search_parameter_bindings)
        method_names = list(self.search_parameter_bindings.values())
        bound_names = [bound.name for bound in self.search_parameter_bounds]
        if (
            any(not name.strip() for name in search_names)
            or any(not name.strip() for name in method_names)
            or len(set(method_names)) != len(method_names)
            or set(bound_names) != search_names
            or len(bound_names) != len(search_names)
            or self.method_signature_abi_digest is None
        ):
            raise ValueError("Search parameter bindings require exact bounds and method ABI")
        for bound in self.search_parameter_bounds:
            if (
                bound.dtype not in {"continuous", "integer", "log_continuous"}
                or bound.categories is not None
                or not isfinite(bound.lower)
                or not isfinite(bound.upper)
                or bound.lower >= bound.upper
            ):
                raise ValueError("Search method parameter bounds must be finite numeric ranges")
        return self


def _search_method_parameters_match_run_profile(
    *,
    profile: SearchMethodRunProfile,
    candidate: Mapping[str, Any],
    method_params: Mapping[str, Any],
) -> bool:
    """Recompute a declared numeric search-parameter binding against the method ABI."""
    try:
        if not profile.search_parameter_bindings:
            return (
                profile.schema_version == "1"
                and _search_parameter_fingerprint(dict(method_params))
                == profile.method_params_fingerprint
            )
        if profile.schema_version != "2" or profile.method_signature_abi_digest is None:
            return False
        from polisyos.foundry.methods import MethodRegistry

        signature = MethodRegistry.get_instance().get_signature(profile.method_fqn)
        if (
            signature is None
            or signature.version != profile.method_version
            or signature.abi_digest() != profile.method_signature_abi_digest
        ):
            return False
        parameters = {item.name: item for item in signature.parameters}
        bounds = {item.name: item for item in profile.search_parameter_bounds}
        if set(bounds) != set(profile.search_parameter_bindings):
            return False
        method_parameter_names = set(profile.search_parameter_bindings.values())
        if len(method_parameter_names) != len(profile.search_parameter_bindings):
            return False
        for search_name, method_name in profile.search_parameter_bindings.items():
            parameter = parameters.get(method_name)
            bound = bounds.get(search_name)
            if (
                parameter is None
                or bound is None
                or parameter.is_static
                or type(parameter.default) not in {int, float}
                or method_name not in method_params
                or search_name not in candidate
            ):
                return False
            expected_dtype = "integer" if type(parameter.default) is int else None
            if expected_dtype == "integer":
                if (
                    bound.dtype != expected_dtype
                    or not bound.lower.is_integer()
                    or not bound.upper.is_integer()
                ):
                    return False
            elif bound.dtype not in {"continuous", "log_continuous"}:
                return False
            raw_value = candidate[search_name]
            configured_value = method_params[method_name]
            if (
                type(raw_value) is not type(parameter.default)
                or type(configured_value) is not type(parameter.default)
                or raw_value != configured_value
                or not isfinite(float(raw_value))
                or not bound.lower <= float(raw_value) <= bound.upper
            ):
                return False
            declared_lower, declared_upper = parameter.bounds
            if (declared_lower is not None and bound.lower < float(declared_lower)) or (
                declared_upper is not None and bound.upper > float(declared_upper)
            ):
                return False
        base_params = {
            name: value
            for name, value in method_params.items()
            if name not in method_parameter_names
        }
        return _search_parameter_fingerprint(base_params) == profile.method_params_fingerprint
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
        return False


def _search_parameter_fingerprint(value: Any) -> str | None:
    """Return the canonical fixed-parameter fingerprint used by Search run profiles."""
    try:
        return fingerprint(value, canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False))
    except (TypeError, ValueError, OverflowError):
        return None


class SearchGPFitConfig(_PydanticBaseModel):
    """Strict optimizer settings required to recompute the recorded GP view."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    n_initial: int = Field(..., ge=1)
    acquisition: Literal[
        "expected_improvement",
        "upper_confidence_bound",
        "probability_of_improvement",
        "q_expected_improvement",
        "expected_hypervolume_improvement",
        "q_expected_hypervolume_improvement",
    ]
    ucb_beta: float
    num_restarts: int = Field(..., ge=1)
    raw_samples: int = Field(..., ge=1)
    max_train_size: int = Field(..., ge=1)
    invalid_penalty: float
    seed: int
    fallback_on_failure: bool
    adaptive_acquisition: bool
    exploration_switch_threshold: float
    refit_interval: int = Field(..., ge=1)
    warm_start_noise_factor: float


class SearchGPFitBasis(_PydanticBaseModel):
    """Persisted candidate-only basis for a fresh canonical GP refit."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1", "2"] = "1"
    authority_purpose: Literal["candidate_gp_fit_recomputation_basis"] = (
        "candidate_gp_fit_recomputation_basis"
    )
    grade: Literal["candidate_only"] = "candidate_only"
    run_profile: SearchMethodRunProfile
    fit_config: SearchGPFitConfig
    bounds: list[SearchGPFitBound] = Field(..., min_length=1)
    training_evaluation_refs: list[ArtifactRef] = Field(..., min_length=1)
    training_observation_count: int = Field(..., ge=1)
    acquisition_evaluation_refs: list[ArtifactRef] = Field(default_factory=list)
    acquisition_observation_count: int = Field(default=0, ge=0)
    fit_backend: str = Field(..., min_length=1, max_length=128)
    fitted_model_state_fingerprint: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    proposal_source: str = Field(..., min_length=1, max_length=128)
    profile: BayesianSourceProfile

    @model_validator(mode="after")
    def _validate_complete_basis(self) -> SearchGPFitBasis:
        if self.training_observation_count != len(self.training_evaluation_refs):
            raise ValueError("Search GP fit observation count must match its exact source refs")
        if any(not ref.manifest_profile_sha256 for ref in self.training_evaluation_refs):
            raise ValueError("Search GP fit source refs must select exact CAS manifest profiles")
        identities = [
            (str(ref.artifact_id), ref.manifest_profile_sha256)
            for ref in self.training_evaluation_refs
        ]
        if len(set(identities)) != len(identities):
            raise ValueError("Search GP fit basis cannot double-count a source evaluation")
        acquisition_identities = [
            (str(ref.artifact_id), ref.manifest_profile_sha256)
            for ref in self.acquisition_evaluation_refs
        ]
        if self.schema_version == "2":
            if (
                not self.acquisition_evaluation_refs
                or self.acquisition_observation_count != len(self.acquisition_evaluation_refs)
                or self.acquisition_observation_count < self.training_observation_count
            ):
                raise ValueError(
                    "Search GP acquisition corpus must bind its full ordered source rows"
                )
            if any(not ref.manifest_profile_sha256 for ref in self.acquisition_evaluation_refs):
                raise ValueError(
                    "Search GP acquisition refs must select exact CAS manifest profiles"
                )
            if len(set(acquisition_identities)) != len(acquisition_identities):
                raise ValueError(
                    "Search GP acquisition basis cannot double-count a source evaluation"
                )
            if not set(identities).issubset(set(acquisition_identities)):
                raise ValueError(
                    "Search GP fit observations must belong to its effective acquisition corpus"
                )
        elif self.acquisition_evaluation_refs or self.acquisition_observation_count:
            raise ValueError("legacy Search GP fit bases cannot claim acquisition source rows")
        if (
            not self.profile.warm_start_eligible
            or self.profile.training_observation_count != self.training_observation_count
            or self.profile.search_space_fingerprint is None
            or self.profile.context_fingerprint != self.run_profile.context_fingerprint
            or self.profile.objective_fingerprint != self.run_profile.objective_fingerprint
        ):
            raise ValueError("Search GP fit profile does not match its complete run basis")
        if self.run_profile.schema_version == "2":
            fit_bounds = {bound.name: bound for bound in self.bounds}
            if any(
                fit_bounds.get(bound.name) != bound
                for bound in self.run_profile.search_parameter_bounds
            ):
                raise ValueError("Search GP fit bounds do not match the bound MethodJob parameters")
        return self


class SearchGPProposalUncertainty(_PydanticBaseModel):
    """Candidate-only posterior values bound to one persisted native-GP proposal."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1"] = "1"
    authority_purpose: Literal["candidate_search_gp_proposal_uncertainty"] = (
        "candidate_search_gp_proposal_uncertainty"
    )
    grade: Literal["candidate_only"] = "candidate_only"
    quantity: Literal["posterior_mean_std_and_acquisition_at_candidate"] = (
        "posterior_mean_std_and_acquisition_at_candidate"
    )
    producer_optimizer_fqn: str = Field(..., min_length=1, max_length=256)
    proposal_id: str = Field(..., min_length=1, max_length=128)
    proposal_source: Literal["bayesian_acquisition"] = "bayesian_acquisition"
    candidate_ref: ArtifactRef
    suite_ref: ArtifactRef
    method_result_ref: ArtifactRef
    method_evidence_ref: ArtifactRef
    method_job_key: str = Field(..., min_length=1, max_length=256)
    metric: str = Field(..., min_length=1, max_length=128)
    direction: Literal["minimize", "maximize"]
    split: Literal["selection", "holdout"]
    unit: str | None = None
    method_request_basis_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    proposal_params_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    source_profile_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    fit_basis_ref: ArtifactRef
    fit_backend: str = Field(..., min_length=1, max_length=128)
    fitted_model_state_fingerprint: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    optimizer_config_fingerprint: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    search_space_fingerprint: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    training_corpus_fingerprint: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    training_observation_count: int = Field(..., ge=1, strict=True)
    acquisition_evaluation_count: int = Field(..., ge=1, strict=True)
    context_fingerprint: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    objective_fingerprint: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    acquisition_type: Literal[
        "expected_improvement",
        "upper_confidence_bound",
        "probability_of_improvement",
    ]
    predicted_mean: float
    predicted_std: float = Field(..., ge=0)
    acquisition_value: float

    @model_validator(mode="after")
    def _validate_finite_prediction(self) -> SearchGPProposalUncertainty:
        if not all(
            isfinite(value)
            for value in (self.predicted_mean, self.predicted_std, self.acquisition_value)
        ):
            raise ValueError("Search GP proposal uncertainty values must be finite")
        return self


class BenchmarkEvaluation(_PydanticBaseModel):
    """Benchmark evaluation public type."""

    model_config = ConfigDict(extra="forbid")

    loop_id: str = Field(..., min_length=1, max_length=128)
    suite_id: str = Field(..., min_length=1, max_length=128)
    suite_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    candidate_ref: ArtifactRef
    method_result_ref: ArtifactRef | None = None
    method_evidence_ref: ArtifactRef | None = None
    method_job_key: str | None = Field(default=None, min_length=1, max_length=256)
    execution_work_packet_ref: ArtifactRef | None = None
    execution_work_packet_status: Literal["available", "unavailable", "rejected"] = "unavailable"
    execution_work_packet_note: str | None = Field(default=None, max_length=512)
    search_source_profile: BayesianSourceProfile | None = None
    selection_metrics: dict[str, float] = Field(default_factory=dict)
    holdout_metrics: dict[str, float] = Field(default_factory=dict)
    sample_counts: dict[str, int] = Field(default_factory=dict)
    guardrails: dict[str, bool] = Field(default_factory=dict)
    promotable: bool = False
    status: str = Field(default="ok", min_length=1, max_length=64)
    notes: list[str] = Field(default_factory=list)
    runtime_split_type: BenchmarkSplit | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_execution_work_packet(self) -> BenchmarkEvaluation:
        if self.execution_work_packet_status == "available" and (
            self.execution_work_packet_ref is None
        ):
            raise ValueError("available MethodJob work requires its persisted packet ref")
        if self.execution_work_packet_status == "unavailable" and (
            self.execution_work_packet_ref is not None
        ):
            raise ValueError("unavailable MethodJob work cannot carry a packet ref")
        return self

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
        serialized: object = handler(self)
        if not isinstance(serialized, dict):
            raise TypeError("PromotionPolicy serializer must return an object")
        payload: dict[str, Any] = {}
        for key, value in serialized.items():
            if not isinstance(key, str):
                raise TypeError("PromotionPolicy serializer keys must be strings")
            payload[key] = value
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


_MutationModelT = TypeVar("_MutationModelT", bound=MutationArtifact)


class PydanticMutationCodec(Generic[_MutationModelT]):
    """Pydantic mutation codec public type."""

    def __init__(self, model_cls: type[_MutationModelT]) -> None:
        self._model_cls = model_cls

    def encode(self, payload: MutationArtifact) -> MutationArtifact:
        return self._model_cls.model_validate(payload)

    def decode(self, payload: dict[str, Any]) -> MutationArtifact:
        return self._model_cls.model_validate(payload)


PydanticMutationCodec.__module__ = "polisyos.scientist.methods.autotune.runtime"


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
        ArtifactStoreConfig(
            backend="filesystem",
            root=str(root or default_cas_root()),
        )
    )


def load_json_artifact(store: ArtifactStore, ref: ArtifactRef | str) -> object:
    """Load json artifact."""
    from polisyos.core.artifacts import load_core_json_artifact

    selector = ref if isinstance(ref, ArtifactRef) else ArtifactID(ref)
    return load_core_json_artifact(store, selector)


def load_model_artifact[PydanticModelT: _PydanticBaseModel](
    store: ArtifactStore,
    ref: ArtifactRef | str,
    model_cls: type[PydanticModelT],
) -> PydanticModelT:
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
    return_selected_profile: bool = False,
) -> ArtifactRef:
    """Persist a mutation artifact and retain the selected protected source view."""
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
            producer=ProducerInfo(
                component="polisyos.scientist.methods.autotune.mutation_artifact",
                version="1.0",
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=(
            return_selected_profile or artifact.loop_id == "claim_adjudication"
        ),
    )


def persist_benchmark_suite(
    store: ArtifactStore,
    suite: BenchmarkSuite,
    *,
    inputs: list[InputRef] | None = None,
    return_selected_profile: bool = False,
) -> ArtifactRef:
    """Persist a benchmark suite and retain a protected producer's selected view."""
    method_job_suite = suite.kind == "method_job"
    snapshot_ref = suite.data_snapshot_ref
    method_job_data_bound = snapshot_ref is not None
    if snapshot_ref is not None:
        if not method_job_suite:
            raise ValueError("methodjob_suite_source_kind_mismatch")
        if suite.suite_version != "2.0":
            raise ValueError("methodjob_suite_source_schema_version_mismatch")
        if (
            snapshot_ref.kind != "fabric.data_snapshot"
            or snapshot_ref.media_type != "application/json"
            or snapshot_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("methodjob_suite_selected_snapshot_required")
        snapshot_manifest = store.get_manifest(snapshot_ref)
        snapshot = validate_core_model_json_artifact(DataSnapshot, store, snapshot_ref)
        if (
            snapshot_manifest.kind != "fabric.data_snapshot"
            or snapshot_manifest.media_type != "application/json"
            or snapshot_manifest.artifact_schema is None
            or snapshot_manifest.artifact_schema.name != DataSnapshot.ARTIFACT_SCHEMA_NAME
            or snapshot_manifest.artifact_schema.version != DataSnapshot.ARTIFACT_SCHEMA_VERSION
            or not isinstance(snapshot, DataSnapshot)
            or snapshot.data_ref.manifest_profile_sha256 is None
            or len(snapshot_manifest.inputs) != 1
            or snapshot_manifest.inputs[0]
            != input_ref_from_artifact_ref(snapshot.data_ref, role="data_ref")
        ):
            raise ValueError("methodjob_suite_snapshot_data_binding_mismatch")
        suite_inputs = list(inputs or [])
        existing_snapshot_edges = [item for item in suite_inputs if item.role == "data_snapshot"]
        expected_snapshot_edge = input_ref_from_artifact_ref(snapshot_ref, role="data_snapshot")
        if existing_snapshot_edges and (
            len(existing_snapshot_edges) != 1
            or existing_snapshot_edges[0] != expected_snapshot_edge
        ):
            raise ValueError("methodjob_suite_snapshot_input_mismatch")
        if not existing_snapshot_edges:
            suite_inputs.append(expected_snapshot_edge)
    else:
        suite_inputs = list(inputs or [])
        if method_job_suite:
            if suite.suite_version != "1.0":
                raise ValueError("methodjob_suite_source_snapshot_required")
            if any(item.role in {"data_snapshot", "data"} for item in suite_inputs):
                raise ValueError("methodjob_suite_unselected_data_source")
    return store.put_json(
        suite,
        ArtifactWriteOptions(
            kind=f"scientist.autotune.{suite.kind}.suite",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.methods.autotune.BenchmarkSuite",
                version=suite.suite_version,
            ),
            inputs=suite_inputs,
            producer=(
                ProducerInfo(
                    component="polisyos.scientist.methods.autotune.benchmark_suite",
                    version="2.0" if method_job_data_bound else "1.0",
                )
                if method_job_suite or suite.kind == "claim_adjudication"
                else None
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=(
            return_selected_profile or method_job_suite or suite.kind == "claim_adjudication"
        ),
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


def _benchmark_evaluation_input_refs(
    evaluation: BenchmarkEvaluation,
    *,
    inputs: list[InputRef] | None = None,
    suite_ref: ArtifactRef | None = None,
) -> list[InputRef]:
    """Bind evaluation source roles to the complete references returned by producers."""
    protected = evaluation.loop_id == "claim_adjudication"
    merged = list(inputs or [])
    bindings: dict[str, ArtifactRef | None] = {
        "candidate": evaluation.candidate_ref,
        "benchmark_suite": suite_ref,
        "method_result": evaluation.method_result_ref,
        "method_evidence": evaluation.method_evidence_ref,
        "execution_work_packet": evaluation.execution_work_packet_ref,
        "search_gp_fit_basis": None,
    }
    raw_fit_basis = evaluation.metadata.get("search_gp_fit_basis_ref")
    if raw_fit_basis is not None:
        try:
            bindings["search_gp_fit_basis"] = ArtifactRef.model_validate(raw_fit_basis)
        except Exception as exc:
            raise ValueError("benchmark_evaluation_fit_basis_ref_invalid") from exc

    for role, ref in bindings.items():
        edge_bindings = [(index, item) for index, item in enumerate(merged) if item.role == role]
        if len(edge_bindings) > 1:
            raise ValueError(f"benchmark_evaluation_duplicate_input_role:{role}")
        if ref is None:
            if protected and edge_bindings:
                selected_suite_edge = (
                    role == "benchmark_suite"
                    and len(edge_bindings) == 1
                    and edge_bindings[0][1].manifest_profile_sha256 is not None
                )
                if not selected_suite_edge:
                    raise ValueError(f"claim_adjudication_unbound_input_role:{role}")
            continue
        if protected and ref.manifest_profile_sha256 is None:
            raise ValueError(f"claim_adjudication_selected_profile_required:{role}")
        expected = input_ref_from_artifact_ref(ref, role=role)
        if not edge_bindings:
            merged.append(expected)
            continue
        index, existing = edge_bindings[0]
        if existing.artifact_id != expected.artifact_id:
            raise ValueError(f"benchmark_evaluation_input_binding_mismatch:{role}")
        if protected and existing != expected:
            raise ValueError(f"claim_adjudication_input_profile_mismatch:{role}")
        if (
            existing.manifest_profile_sha256 is not None
            and expected.manifest_profile_sha256 is not None
            and existing.manifest_profile_sha256 != expected.manifest_profile_sha256
        ):
            raise ValueError(f"benchmark_evaluation_input_profile_mismatch:{role}")
        if expected.manifest_profile_sha256 is not None:
            merged[index] = expected

    if protected:
        for role in ("candidate", "benchmark_suite"):
            role_edges = [item for item in merged if item.role == role]
            if len(role_edges) != 1 or role_edges[0].manifest_profile_sha256 is None:
                raise ValueError(f"claim_adjudication_selected_profile_required:{role}")
        for role in (
            "method_result",
            "method_evidence",
            "execution_work_packet",
            "search_gp_fit_basis",
        ):
            ref = bindings.get(role)
            role_edges = [item for item in merged if item.role == role]
            if ref is not None and (
                len(role_edges) != 1 or role_edges[0] != input_ref_from_artifact_ref(ref, role=role)
            ):
                raise ValueError(f"claim_adjudication_input_profile_mismatch:{role}")
    return merged


def persist_benchmark_evaluation(
    store: ArtifactStore,
    evaluation: BenchmarkEvaluation,
    *,
    inputs: list[InputRef] | None = None,
    return_selected_profile: bool = False,
) -> ArtifactRef:
    """Persist an evaluation with its producer-selected source references."""
    protected = evaluation.loop_id == "claim_adjudication"
    merged_inputs = _benchmark_evaluation_input_refs(evaluation, inputs=inputs)
    return store.put_json(
        evaluation,
        ArtifactWriteOptions(
            kind=_benchmark_evaluation_artifact_kind(evaluation.loop_id),
            media_type="application/json",
            schema=SchemaInfo(
                name=_BENCHMARK_EVALUATION_SCHEMA_NAME,
                version=evaluation.suite_version,
            ),
            producer=ProducerInfo(
                component="polisyos.scientist.methods.autotune.benchmark_evaluator",
                version="1.0",
            ),
            inputs=merged_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=return_selected_profile or protected,
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
