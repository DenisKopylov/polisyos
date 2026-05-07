"""Public analytics abstraction module API."""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from itertools import product
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.references import (
    AbstractionCertificateRef,
    ArtifactRefModel,
    FiniteStateAbstractionMapRef,
)

if TYPE_CHECKING:
    from polisyos.ir.analytics.structural_causal_model import (
        NodeMechanism,
        StructuralCausalModelSpec,
    )

_FINITE_STATE_ABSTRACTION_MAP_SCHEMA_NAME = "ir.finite_state_abstraction_map"
_FINITE_STATE_ABSTRACTION_MAP_SCHEMA_VERSION = "1.0"
_ABSTRACTION_CERTIFICATE_SCHEMA_NAME = "ir.abstraction_certificate"
_ABSTRACTION_CERTIFICATE_SCHEMA_VERSION = "1.0"
_EXACT_MATCH_TOLERANCE = 1e-9
APPROXIMATE_TRANSPORT_ABSTRACTION_FAMILIES = frozenset(
    (
        "type_mean_affine",
        "spatial_eep_linear",
        "continuous_linear_gaussian",
        "continuous_lipschitz_dag",
    )
)
CONTINUOUS_APPROXIMATE_TRANSPORT_ABSTRACTION_FAMILIES = frozenset(
    ("continuous_linear_gaussian", "continuous_lipschitz_dag")
)
CONTINUOUS_ABSTRACTION_TIGHTNESS_STATUSES = frozenset(
    ("exact_on_linear_gaussian", "upper_bound_only", "unknown")
)


def _ensure_non_empty(value: str, *, field_name: str) -> str:
    candidate = str(value).strip()
    if not candidate:
        raise ValueError(f"{field_name} must be non-empty")
    return candidate


def _ensure_finite(value: float | None, *, field_name: str) -> float | None:
    if value is None:
        return None
    casted = float(value)
    if not math.isfinite(casted):
        raise ValueError(f"{field_name} must be finite")
    return casted


def _ensure_non_negative_finite(value: float | None, *, field_name: str) -> float | None:
    casted = _ensure_finite(value, field_name=field_name)
    if casted is not None and casted < 0.0:
        raise ValueError(f"{field_name} must be non-negative")
    return casted


def _validate_artifact_ref(ref: ArtifactRefModel, *, field_name: str) -> ArtifactRefModel:
    if not str(ref.kind).strip():
        raise ValueError(f"{field_name}.kind must be non-empty")
    if not str(ref.media_type).strip():
        raise ValueError(f"{field_name}.media_type must be non-empty")
    return ref


def _metadata_string(metadata: dict[str, Any], key: str) -> str:
    raw = metadata.get(key)
    if not isinstance(raw, str):
        raise ValueError(f"metadata.{key} must be a non-empty string")
    return _ensure_non_empty(raw, field_name=f"metadata.{key}")


def _optional_metadata_string(metadata: dict[str, Any], key: str) -> str | None:
    raw = metadata.get(key)
    if raw is None:
        return None
    return _metadata_string(metadata, key)


def _metadata_string_tuple(metadata: dict[str, Any], key: str) -> tuple[str, ...]:
    raw = metadata.get(key)
    if not isinstance(raw, (tuple, list)):
        raise ValueError(f"metadata.{key} must be a non-empty tuple/list of strings")
    normalized = tuple(_ensure_non_empty(str(item), field_name=f"metadata.{key}") for item in raw)
    if not normalized:
        raise ValueError(f"metadata.{key} must be non-empty")
    return normalized


def _metadata_true(metadata: dict[str, Any], key: str) -> None:
    if metadata.get(key) is not True:
        raise ValueError(f"metadata.{key} must be true")


def _metadata_mapping(metadata: dict[str, Any], key: str) -> dict[str, Any]:
    raw = metadata.get(key)
    if not isinstance(raw, dict) or not raw:
        raise ValueError(f"metadata.{key} must be a non-empty mapping")
    return raw


def _validate_estimand_error_bounds(
    metadata: dict[str, Any],
    preserved_queries: tuple[str, ...],
) -> None:
    raw = metadata.get("estimand_error_bounds")
    if not isinstance(raw, dict) or not raw:
        raise ValueError("metadata.estimand_error_bounds must be a non-empty mapping")
    missing = sorted(set(preserved_queries) - set(raw))
    if missing:
        raise ValueError(
            f"metadata.estimand_error_bounds must cover every preserved_query; missing={missing}"
        )
    for query, bound in raw.items():
        _ensure_non_empty(str(query), field_name="metadata.estimand_error_bounds.query")
        _ensure_non_negative_finite(
            bound,
            field_name=f"metadata.estimand_error_bounds.{query}",
        )


def _query_matches_family(query: str, family: str) -> bool:
    normalized_query = _ensure_non_empty(query, field_name="query")
    normalized_family = _ensure_non_empty(family, field_name="family")
    return normalized_query == normalized_family or normalized_query.startswith(
        f"{normalized_family}:"
    )


def _normalize_error_bound_spec(
    metadata: dict[str, Any],
    *,
    error_bound: float | None,
    preserved_queries: tuple[str, ...],
    abstraction_family: str | None = None,
) -> dict[str, Any]:
    spec = _metadata_mapping(metadata, "error_bound_spec")
    scope = spec.get("scope")
    if not isinstance(scope, dict) or not scope:
        raise ValueError("metadata.error_bound_spec.scope must be a non-empty mapping")

    query_family = _ensure_non_empty(
        str(scope.get("query_family")),
        field_name="metadata.error_bound_spec.scope.query_family",
    )
    interventions = _ensure_non_empty(
        str(scope.get("interventions")),
        field_name="metadata.error_bound_spec.scope.interventions",
    )
    action_domain = _ensure_non_empty(
        str(scope.get("action_domain")),
        field_name="metadata.error_bound_spec.scope.action_domain",
    )
    if preserved_queries and not any(
        _query_matches_family(query, query_family) for query in preserved_queries
    ):
        raise ValueError(
            "metadata.error_bound_spec.scope.query_family must match at least one preserved_query"
        )

    state_metric = _ensure_non_empty(
        str(spec.get("state_metric")),
        field_name="metadata.error_bound_spec.state_metric",
    )
    raw_distribution_metric = spec.get("distribution_metric")
    distribution_metric = (
        None
        if raw_distribution_metric is None
        else _ensure_non_empty(
            str(raw_distribution_metric),
            field_name="metadata.error_bound_spec.distribution_metric",
        )
    )
    value_lipschitz_constant = _ensure_non_negative_finite(
        spec.get("value_lipschitz_constant"),
        field_name="metadata.error_bound_spec.value_lipschitz_constant",
    )
    global_state_bound = _ensure_non_negative_finite(
        spec.get("global_state_bound"),
        field_name="metadata.error_bound_spec.global_state_bound",
    )
    recommendation_margin_required = _ensure_non_negative_finite(
        spec.get("recommendation_margin_required"),
        field_name="metadata.error_bound_spec.recommendation_margin_required",
    )
    gain_matrix_spectral_radius = _ensure_non_negative_finite(
        spec.get("gain_matrix_spectral_radius"),
        field_name="metadata.error_bound_spec.gain_matrix_spectral_radius",
    )
    tightness_status = _ensure_non_empty(
        str(spec.get("tightness_status")),
        field_name="metadata.error_bound_spec.tightness_status",
    )
    if tightness_status not in CONTINUOUS_ABSTRACTION_TIGHTNESS_STATUSES:
        allowed = sorted(CONTINUOUS_ABSTRACTION_TIGHTNESS_STATUSES)
        raise ValueError(f"metadata.error_bound_spec.tightness_status must be one of {allowed}")
    if (
        abstraction_family is not None
        and abstraction_family != "continuous_linear_gaussian"
        and tightness_status == "exact_on_linear_gaussian"
    ):
        raise ValueError(
            "metadata.error_bound_spec.tightness_status=exact_on_linear_gaussian "
            "requires abstraction_family=continuous_linear_gaussian"
        )
    if (
        abstraction_family in CONTINUOUS_APPROXIMATE_TRANSPORT_ABSTRACTION_FAMILIES
        and distribution_metric is None
    ):
        raise ValueError(
            "continuous approximate abstraction certificates must declare "
            "metadata.error_bound_spec.distribution_metric"
        )
    if (
        abstraction_family in CONTINUOUS_APPROXIMATE_TRANSPORT_ABSTRACTION_FAMILIES
        and gain_matrix_spectral_radius is not None
        and gain_matrix_spectral_radius >= 1.0
    ):
        raise ValueError(
            "continuous approximate abstraction certificates require "
            "metadata.error_bound_spec.gain_matrix_spectral_radius < 1.0"
        )
    if (
        error_bound is not None
        and recommendation_margin_required is not None
        and recommendation_margin_required + _EXACT_MATCH_TOLERANCE < (2.0 * error_bound)
    ):
        raise ValueError(
            "metadata.error_bound_spec.recommendation_margin_required must be >= 2 * error_bound"
        )

    normalized: dict[str, Any] = {
        "scope": {
            "query_family": query_family,
            "interventions": interventions,
            "action_domain": action_domain,
        },
        "state_metric": state_metric,
        "tightness_status": tightness_status,
    }
    if distribution_metric is not None:
        normalized["distribution_metric"] = distribution_metric
    if value_lipschitz_constant is not None:
        normalized["value_lipschitz_constant"] = float(value_lipschitz_constant)
    if global_state_bound is not None:
        normalized["global_state_bound"] = float(global_state_bound)
    if recommendation_margin_required is not None:
        normalized["recommendation_margin_required"] = float(recommendation_margin_required)
    if gain_matrix_spectral_radius is not None:
        normalized["gain_matrix_spectral_radius"] = float(gain_matrix_spectral_radius)

    for optional_key in (
        "bound_kind",
        "error_metric",
        "error_scope",
        "confidence_level",
        "computation_artifact_ref",
        "local_defect_artifact_ref",
    ):
        if optional_key not in spec:
            continue
        raw_value = spec.get(optional_key)
        if optional_key == "confidence_level":
            normalized_confidence = _ensure_non_negative_finite(
                raw_value,
                field_name=f"metadata.error_bound_spec.{optional_key}",
            )
            if normalized_confidence is None:
                raise ValueError(f"metadata.error_bound_spec.{optional_key} must be non-negative")
            normalized[optional_key] = float(normalized_confidence)
            continue
        normalized[optional_key] = _ensure_non_empty(
            str(raw_value),
            field_name=f"metadata.error_bound_spec.{optional_key}",
        )

    return normalized


def abstraction_estimand_error_bounds(
    certificate: AbstractionCertificate,
) -> dict[str, float]:
    raw = certificate.metadata.get("estimand_error_bounds")
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, float] = {}
    for query, bound in raw.items():
        normalized_bound = _ensure_non_negative_finite(
            bound,
            field_name=f"estimand_error_bounds.{query}",
        )
        if normalized_bound is None:
            raise ValueError(f"estimand_error_bounds.{query} must be non-negative")
        normalized[_ensure_non_empty(str(query), field_name="estimand_error_bounds.query")] = float(
            normalized_bound
        )
    return normalized


def abstraction_allowed_intervention_family(
    certificate: AbstractionCertificate,
) -> str | None:
    return _optional_metadata_string(certificate.metadata, "allowed_intervention_family")


def abstraction_error_bound_spec(
    certificate: AbstractionCertificate,
) -> dict[str, Any]:
    if "error_bound_spec" not in certificate.metadata:
        return {}
    abstraction_family = None
    raw_family = certificate.metadata.get("abstraction_family")
    if isinstance(raw_family, str) and raw_family.strip():
        abstraction_family = raw_family.strip()
    return _normalize_error_bound_spec(
        certificate.metadata,
        error_bound=certificate.error_bound,
        preserved_queries=tuple(certificate.preserved_queries),
        abstraction_family=abstraction_family,
    )


def abstraction_recommendation_margin_required(
    certificate: AbstractionCertificate,
) -> float | None:
    spec = abstraction_error_bound_spec(certificate)
    raw = spec.get("recommendation_margin_required")
    if raw is None:
        return None
    normalized = _ensure_non_negative_finite(
        raw,
        field_name="error_bound_spec.recommendation_margin_required",
    )
    if normalized is None:
        return None
    return float(normalized)


def abstraction_preserves_query(
    certificate: AbstractionCertificate,
    query: str,
    *,
    allow_prefix_match: bool = False,
) -> bool:
    target = _ensure_non_empty(query, field_name="query")
    preserved = tuple(certificate.preserved_queries)
    if target in preserved:
        return True
    if not allow_prefix_match:
        return False
    return any(item.startswith(target) for item in preserved)


class AbstractionPreservationType(str, Enum):
    """Abstraction preservation type public type."""

    EXACT = "exact"
    APPROXIMATE = "approximate"
    POLICY_VALUE_ONLY = "policy_value_only"
    INVALID = "invalid"


class VariableStateAbstraction(BaseModel):
    """One-to-one variable/state quotient used by the exact finite-state verifier."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    micro_variable: str
    macro_variable: str
    state_map: dict[str, str]

    @field_validator("micro_variable", "macro_variable", mode="before")
    @classmethod
    def _validate_strings(cls, value: Any, info: Any) -> str:
        return _ensure_non_empty(str(value), field_name=str(info.field_name))

    @model_validator(mode="after")
    def _validate_state_map(self) -> VariableStateAbstraction:
        if not self.state_map:
            raise ValueError("state_map must be non-empty")
        for micro_state, macro_state in self.state_map.items():
            _ensure_non_empty(micro_state, field_name="state_map.micro_state")
            _ensure_non_empty(macro_state, field_name="state_map.macro_state")
        return self


class FiniteStateAbstractionMap(BaseModel):
    """Exact finite-state variable/state quotient map for micro-to-macro verification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    variable_maps: tuple[VariableStateAbstraction, ...]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_unique_variables(self) -> FiniteStateAbstractionMap:
        if not self.variable_maps:
            raise ValueError("variable_maps must be non-empty")
        micro_vars = [item.micro_variable for item in self.variable_maps]
        macro_vars = [item.macro_variable for item in self.variable_maps]
        if len(set(micro_vars)) != len(micro_vars):
            raise ValueError("micro_variable values must be unique")
        if len(set(macro_vars)) != len(macro_vars):
            raise ValueError("macro_variable values must be unique")
        return self

    @property
    def micro_to_macro(self) -> dict[str, str]:
        return {item.micro_variable: item.macro_variable for item in self.variable_maps}

    @property
    def by_micro_variable(self) -> dict[str, VariableStateAbstraction]:
        return {item.micro_variable: item for item in self.variable_maps}

    @property
    def by_macro_variable(self) -> dict[str, VariableStateAbstraction]:
        return {item.macro_variable: item for item in self.variable_maps}


class ContinuousAffineVariableTransform(BaseModel):
    """Affine micro-to-macro variable transform for continuous abstractions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scale: float = 1.0
    shift: float = 0.0

    @field_validator("scale", "shift", mode="before")
    @classmethod
    def _validate_finite(cls, value: Any, info: Any) -> float:
        normalized = _ensure_finite(value, field_name=str(info.field_name))
        if normalized is None:
            raise ValueError(f"{info.field_name} must be finite")
        return float(normalized)


class ContinuousApproximateAbstractionConfig(BaseModel):
    """Configuration for continuous approximate abstraction certificates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    family: Literal["continuous_linear_gaussian", "continuous_lipschitz_dag"]
    preservation_type: AbstractionPreservationType = AbstractionPreservationType.APPROXIMATE
    allowed_intervention_family: str = "hard_or_soft_declared_scope"
    query_family: str = "policy_value"
    action_domain: str = "compact_box"
    intervention_ranges: dict[str, tuple[float, float]] = Field(default_factory=dict)
    state_metric: str = "weighted_l1"
    distribution_metric: str | None = None
    value_lipschitz_constant: float | None = Field(default=None, ge=0.0)
    state_weights: dict[str, float] = Field(default_factory=dict)
    policy_value_weights: dict[str, float] = Field(default_factory=dict)
    non_preserved_queries: tuple[str, ...] = ()
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    proof_obligations_satisfied: tuple[str, ...] = ()
    variable_transforms: dict[str, ContinuousAffineVariableTransform] = Field(default_factory=dict)
    local_mechanism_defects: dict[str, float] = Field(default_factory=dict)
    gain_matrix: dict[str, dict[str, float]] = Field(default_factory=dict)
    confidence_level: float | None = Field(default=None, ge=0.0)
    computation_artifact_ref: str | None = None
    local_defect_artifact_ref: str | None = None

    @field_validator(
        "allowed_intervention_family",
        "query_family",
        "action_domain",
        "state_metric",
        mode="before",
    )
    @classmethod
    def _validate_non_empty_strings(cls, value: Any, info: Any) -> str:
        return _ensure_non_empty(str(value), field_name=str(info.field_name))

    @field_validator("distribution_metric", mode="before")
    @classmethod
    def _validate_distribution_metric(cls, value: Any) -> str | None:
        if value is None:
            return None
        return _ensure_non_empty(str(value), field_name="distribution_metric")

    @field_validator(
        "non_preserved_queries",
        "proof_obligations_satisfied",
        mode="before",
    )
    @classmethod
    def _coerce_string_tuple_fields(cls, value: Any) -> tuple[str, ...]:
        if value in (None, ()):
            return ()
        if not isinstance(value, (tuple, list)):
            raise ValueError("tuple fields must be a tuple/list of strings")
        return tuple(_ensure_non_empty(str(item), field_name="tuple_item") for item in value)

    @field_validator("intervention_ranges", mode="before")
    @classmethod
    def _coerce_intervention_ranges(
        cls,
        value: Any,
    ) -> dict[str, tuple[float, float]]:
        if value in (None, {}):
            return {}
        if not isinstance(value, Mapping):
            raise ValueError("intervention_ranges must be a mapping")
        normalized: dict[str, tuple[float, float]] = {}
        for variable, raw_bounds in value.items():
            name = _ensure_non_empty(str(variable), field_name="intervention_ranges.variable")
            if not isinstance(raw_bounds, (tuple, list)) or len(raw_bounds) != 2:
                raise ValueError("intervention_ranges entries must be length-2 tuples/lists")
            lower = _ensure_finite(raw_bounds[0], field_name=f"intervention_ranges.{name}.lower")
            upper = _ensure_finite(raw_bounds[1], field_name=f"intervention_ranges.{name}.upper")
            if lower is None or upper is None:
                raise ValueError(
                    f"intervention_ranges.{name} must contain finite lower/upper bounds"
                )
            if lower > upper:
                raise ValueError(f"intervention_ranges.{name} must satisfy lower <= upper")
            normalized[name] = (float(lower), float(upper))
        return normalized

    @field_validator("state_weights", mode="before")
    @classmethod
    def _coerce_state_weights(cls, value: Any) -> dict[str, float]:
        if value in (None, {}):
            return {}
        if not isinstance(value, Mapping):
            raise ValueError("state_weights must be a mapping")
        normalized: dict[str, float] = {}
        for variable, raw_weight in value.items():
            name = _ensure_non_empty(str(variable), field_name="state_weights.variable")
            weight = _ensure_non_negative_finite(
                raw_weight,
                field_name=f"state_weights.{name}",
            )
            if weight is None:
                raise ValueError(f"state_weights.{name} must be non-negative")
            normalized[name] = float(weight)
        return normalized

    @field_validator("policy_value_weights", mode="before")
    @classmethod
    def _coerce_policy_value_weights(cls, value: Any) -> dict[str, float]:
        if value in (None, {}):
            return {}
        if not isinstance(value, Mapping):
            raise ValueError("policy_value_weights must be a mapping")
        normalized: dict[str, float] = {}
        for variable, raw_weight in value.items():
            name = _ensure_non_empty(str(variable), field_name="policy_value_weights.variable")
            weight = _ensure_finite(raw_weight, field_name=f"policy_value_weights.{name}")
            if weight is None:
                raise ValueError(f"policy_value_weights.{name} must be finite")
            normalized[name] = float(weight)
        return normalized

    @field_validator("local_mechanism_defects", mode="before")
    @classmethod
    def _coerce_local_mechanism_defects(cls, value: Any) -> dict[str, float]:
        if value in (None, {}):
            return {}
        if not isinstance(value, Mapping):
            raise ValueError("local_mechanism_defects must be a mapping")
        normalized: dict[str, float] = {}
        for variable, raw_bound in value.items():
            name = _ensure_non_empty(str(variable), field_name="local_mechanism_defects.variable")
            bound = _ensure_non_negative_finite(
                raw_bound,
                field_name=f"local_mechanism_defects.{name}",
            )
            if bound is None:
                raise ValueError(f"local_mechanism_defects.{name} must be non-negative")
            normalized[name] = float(bound)
        return normalized

    @field_validator("gain_matrix", mode="before")
    @classmethod
    def _coerce_gain_matrix(cls, value: Any) -> dict[str, dict[str, float]]:
        if value in (None, {}):
            return {}
        if not isinstance(value, Mapping):
            raise ValueError("gain_matrix must be a mapping")
        normalized: dict[str, dict[str, float]] = {}
        for child, raw_parents in value.items():
            child_name = _ensure_non_empty(str(child), field_name="gain_matrix.child")
            if not isinstance(raw_parents, Mapping):
                raise ValueError(f"gain_matrix.{child_name} must be a mapping")
            parent_row: dict[str, float] = {}
            for parent, raw_gain in raw_parents.items():
                parent_name = _ensure_non_empty(str(parent), field_name="gain_matrix.parent")
                gain = _ensure_non_negative_finite(
                    raw_gain,
                    field_name=f"gain_matrix.{child_name}.{parent_name}",
                )
                if gain is None:
                    raise ValueError(f"gain_matrix.{child_name}.{parent_name} must be non-negative")
                parent_row[parent_name] = float(gain)
            normalized[child_name] = parent_row
        return normalized

    @model_validator(mode="after")
    def _validate_family_requirements(self) -> ContinuousApproximateAbstractionConfig:
        if self.family == "continuous_linear_gaussian" and self.distribution_metric is None:
            object.__setattr__(self, "distribution_metric", "wasserstein_2_gaussian")
        if self.family == "continuous_lipschitz_dag":
            if not self.local_mechanism_defects:
                raise ValueError("continuous_lipschitz_dag requires local_mechanism_defects")
            if not self.gain_matrix:
                raise ValueError("continuous_lipschitz_dag requires gain_matrix")
            if self.distribution_metric is None:
                object.__setattr__(self, "distribution_metric", "wasserstein_1")
        if not self.policy_value_weights and self.value_lipschitz_constant is None:
            raise ValueError(
                "continuous approximate abstraction requires either policy_value_weights "
                "or value_lipschitz_constant"
            )
        return self


class AbstractionCertificate(BaseModel):
    """Certificate for query-preserving micro-to-macro abstraction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    micro_graph_ref: ArtifactRefModel
    macro_graph_ref: ArtifactRefModel
    abstraction_map_ref: FiniteStateAbstractionMapRef
    preservation_type: AbstractionPreservationType
    preserved_queries: tuple[str, ...] = ()
    error_bound: float | None = None
    validation_notes: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("preserved_queries", "validation_notes", mode="before")
    @classmethod
    def _coerce_string_tuples(cls, value: Any) -> tuple[str, ...]:
        if value in (None, ()):
            return ()
        if not isinstance(value, (tuple, list)):
            raise ValueError("tuple fields must be a tuple/list of strings")
        return tuple(_ensure_non_empty(str(item), field_name="tuple_item") for item in value)

    @field_validator("error_bound", mode="before")
    @classmethod
    def _validate_error_bound(cls, value: Any) -> Any:
        return _ensure_non_negative_finite(value, field_name="error_bound")

    @model_validator(mode="after")
    def _validate_contract(self) -> AbstractionCertificate:
        _validate_artifact_ref(self.micro_graph_ref, field_name="micro_graph_ref")
        _validate_artifact_ref(self.macro_graph_ref, field_name="macro_graph_ref")
        if (
            self.preservation_type
            in {
                AbstractionPreservationType.EXACT,
                AbstractionPreservationType.INVALID,
            }
            and self.error_bound is not None
        ):
            raise ValueError(
                "exact and invalid abstraction certificates must not publish a numeric error_bound"
            )
        if (
            self.preservation_type is AbstractionPreservationType.EXACT
            and not self.preserved_queries
        ):
            raise ValueError("exact abstraction certificates must list preserved_queries")
        if self.preservation_type is AbstractionPreservationType.INVALID and self.preserved_queries:
            raise ValueError("invalid abstraction certificates must not list preserved_queries")
        if self.preservation_type is AbstractionPreservationType.APPROXIMATE:
            self._validate_approximate_transport_contract()
        if self.preservation_type is AbstractionPreservationType.POLICY_VALUE_ONLY:
            self._validate_policy_value_only_contract()
        return self

    def _validate_approximate_transport_contract(self) -> None:
        if self.error_bound is None:
            raise ValueError("approximate abstraction certificates must publish error_bound")
        if len(self.preserved_queries) < 2:
            raise ValueError(
                "approximate abstraction certificates must preserve a multi-query family; "
                "use policy_value_only for a single scalar welfare bound"
            )
        abstraction_family = _metadata_string(self.metadata, "abstraction_family")
        if abstraction_family not in APPROXIMATE_TRANSPORT_ABSTRACTION_FAMILIES:
            allowed = sorted(APPROXIMATE_TRANSPORT_ABSTRACTION_FAMILIES)
            raise ValueError(
                "approximate abstraction certificates must use a supported "
                f"abstraction_family; allowed={allowed}"
            )
        _metadata_string(self.metadata, "allowed_intervention_family")
        _metadata_true(self.metadata, "intervention_family_verified")
        _metadata_string_tuple(self.metadata, "proof_obligations_satisfied")
        _metadata_string_tuple(self.metadata, "non_preserved_queries")
        diagnostics = self.metadata.get("diagnostics")
        if not isinstance(diagnostics, dict):
            raise ValueError("metadata.diagnostics must be a mapping")
        _validate_estimand_error_bounds(self.metadata, self.preserved_queries)
        if "error_bound_spec" in self.metadata:
            _normalize_error_bound_spec(
                self.metadata,
                error_bound=self.error_bound,
                preserved_queries=self.preserved_queries,
                abstraction_family=abstraction_family,
            )
        if abstraction_family in CONTINUOUS_APPROXIMATE_TRANSPORT_ABSTRACTION_FAMILIES:
            if "error_bound_spec" not in self.metadata:
                raise ValueError(
                    "continuous approximate abstraction certificates must publish "
                    "metadata.error_bound_spec"
                )

    def _validate_policy_value_only_contract(self) -> None:
        if self.error_bound is None:
            raise ValueError("policy_value_only certificates must publish error_bound")
        if len(self.preserved_queries) != 1:
            raise ValueError(
                "policy_value_only certificates must list exactly one preserved policy-value query"
            )
        abstraction_family = None
        raw_family = self.metadata.get("abstraction_family")
        if isinstance(raw_family, str) and raw_family.strip():
            abstraction_family = raw_family.strip()
        raw_bounds = self.metadata.get("estimand_error_bounds")
        if raw_bounds is not None:
            _validate_estimand_error_bounds(self.metadata, self.preserved_queries)
        if "error_bound_spec" in self.metadata:
            _normalize_error_bound_spec(
                self.metadata,
                error_bound=self.error_bound,
                preserved_queries=self.preserved_queries,
                abstraction_family=abstraction_family,
            )
        if abstraction_family in CONTINUOUS_APPROXIMATE_TRANSPORT_ABSTRACTION_FAMILIES:
            if "error_bound_spec" not in self.metadata:
                raise ValueError(
                    "continuous policy_value_only abstraction certificates must publish "
                    "metadata.error_bound_spec"
                )


def persist_finite_state_abstraction_map(
    store: ArtifactStore,
    abstraction_map: FiniteStateAbstractionMap,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _FINITE_STATE_ABSTRACTION_MAP_SCHEMA_NAME,
    schema_version: str = _FINITE_STATE_ABSTRACTION_MAP_SCHEMA_VERSION,
) -> FiniteStateAbstractionMapRef:
    """Persist finite state abstraction map helper."""
    ref = put_json_artifact(
        store,
        abstraction_map.model_dump(mode="json"),
        kind="ir.finite_state_abstraction_map",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return FiniteStateAbstractionMapRef.model_validate(ref)


def load_finite_state_abstraction_map(
    store: ArtifactStore,
    ref: FiniteStateAbstractionMapRef,
) -> FiniteStateAbstractionMap:
    """Load finite state abstraction map."""
    payload = get_json_artifact(store, ref.artifact_id)
    return FiniteStateAbstractionMap.model_validate(payload)


def persist_abstraction_certificate(
    store: ArtifactStore,
    certificate: AbstractionCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _ABSTRACTION_CERTIFICATE_SCHEMA_NAME,
    schema_version: str = _ABSTRACTION_CERTIFICATE_SCHEMA_VERSION,
) -> AbstractionCertificateRef:
    """Persist abstraction certificate helper."""
    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.abstraction_certificate",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return AbstractionCertificateRef.model_validate(ref)


def load_abstraction_certificate(
    store: ArtifactStore,
    ref: AbstractionCertificateRef,
) -> AbstractionCertificate:
    """Load abstraction certificate."""
    payload = get_json_artifact(store, ref.artifact_id)
    return AbstractionCertificate.model_validate(payload)


def _mechanism_by_variable(spec: StructuralCausalModelSpec) -> dict[str, NodeMechanism]:
    return {mechanism.variable: mechanism for mechanism in spec.mechanisms}


def _normalized_distribution(
    distribution: dict[str, Any],
    *,
    state_space: tuple[str, ...],
    field_name: str,
) -> dict[str, float]:
    missing = sorted(set(state_space) - set(distribution))
    extra = sorted(set(distribution) - set(state_space))
    if missing or extra:
        raise ValueError(
            f"{field_name} must align with state_space exactly; missing={missing}, extra={extra}"
        )
    normalized: dict[str, float] = {}
    total = 0.0
    for state in state_space:
        value = _ensure_finite(distribution[state], field_name=f"{field_name}.{state}")
        if value is None or value < 0.0:
            raise ValueError(f"{field_name}.{state} must be non-negative")
        normalized[state] = float(value)
        total += float(value)
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=_EXACT_MATCH_TOLERANCE):
        raise ValueError(f"{field_name} must sum to 1.0, got {total}")
    return normalized


def _conditional_key(
    parents: tuple[str, ...],
    assignment: dict[str, str],
) -> tuple[tuple[str, str], ...]:
    return tuple((parent, assignment[parent]) for parent in parents)


def _extract_finite_state_table(
    mechanism: NodeMechanism,
) -> tuple[tuple[str, ...], dict[tuple[tuple[str, str], ...], dict[str, float]]]:
    params = mechanism.family_params
    if not isinstance(params, dict):
        raise ValueError(f"{mechanism.variable}.family_params must be a mapping")
    raw_state_space = params.get("state_space")
    if not isinstance(raw_state_space, list) or not raw_state_space:
        raise ValueError(f"{mechanism.variable}.family_params.state_space must be a non-empty list")
    state_space = tuple(
        _ensure_non_empty(str(state), field_name=f"{mechanism.variable}.state_space")
        for state in raw_state_space
    )
    if len(set(state_space)) != len(state_space):
        raise ValueError(f"{mechanism.variable}.state_space must be unique")

    root_distribution = params.get("distribution", params.get("probabilities"))
    if not mechanism.parents:
        if not isinstance(root_distribution, dict):
            raise ValueError(
                f"{mechanism.variable}.family_params.distribution must be a mapping for root variables"
            )
        return (
            state_space,
            {
                (): _normalized_distribution(
                    root_distribution,
                    state_space=state_space,
                    field_name=f"{mechanism.variable}.distribution",
                )
            },
        )

    raw_entries = params.get("conditional_distribution", params.get("conditional_probabilities"))
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError(
            f"{mechanism.variable}.family_params.conditional_distribution must be a non-empty list"
        )

    table: dict[tuple[tuple[str, str], ...], dict[str, float]] = {}
    parent_tuple = tuple(mechanism.parents)
    for idx, entry in enumerate(raw_entries):
        if not isinstance(entry, dict):
            raise ValueError(
                f"{mechanism.variable}.conditional_distribution[{idx}] must be a mapping"
            )
        raw_when = entry.get("when")
        raw_distribution = entry.get("distribution")
        if not isinstance(raw_when, dict) or not isinstance(raw_distribution, dict):
            raise ValueError(
                f"{mechanism.variable}.conditional_distribution[{idx}] must contain when and distribution mappings"
            )
        if set(raw_when) != set(parent_tuple):
            raise ValueError(
                f"{mechanism.variable}.conditional_distribution[{idx}].when must match parents exactly"
            )
        assignment = {
            parent: _ensure_non_empty(
                raw_when[parent], field_name=f"{mechanism.variable}.when.{parent}"
            )
            for parent in parent_tuple
        }
        key = _conditional_key(parent_tuple, assignment)
        if key in table:
            raise ValueError(
                f"{mechanism.variable}.conditional_distribution contains duplicate parent assignments"
            )
        table[key] = _normalized_distribution(
            raw_distribution,
            state_space=state_space,
            field_name=f"{mechanism.variable}.conditional_distribution[{idx}].distribution",
        )
    return state_space, table


def _aggregate_distribution(
    distribution: dict[str, float],
    state_map: dict[str, str],
) -> dict[str, float]:
    aggregated: dict[str, float] = {}
    for micro_state, probability in distribution.items():
        macro_state = state_map[micro_state]
        aggregated[macro_state] = aggregated.get(macro_state, 0.0) + float(probability)
    return aggregated


def _distributions_match(
    left: dict[str, float],
    right: dict[str, float],
) -> bool:
    if set(left) != set(right):
        return False
    for key in left:
        if not math.isclose(left[key], right[key], rel_tol=0.0, abs_tol=_EXACT_MATCH_TOLERANCE):
            return False
    return True


def verify_finite_state_exact_abstraction(
    micro_scm: StructuralCausalModelSpec,
    macro_scm: StructuralCausalModelSpec,
    abstraction_map: FiniteStateAbstractionMap,
    *,
    micro_graph_ref: ArtifactRefModel,
    macro_graph_ref: ArtifactRefModel,
    abstraction_map_ref: FiniteStateAbstractionMapRef,
    preserved_queries: tuple[str, ...] | list[str] | None = None,
) -> AbstractionCertificate:
    """Verify a one-to-one finite-state abstraction and return a certificate."""

    notes: list[str] = []
    try:
        if micro_scm.graph.graph_type.value != "dag" or macro_scm.graph.graph_type.value != "dag":
            notes.append("exact_finite_state_abstraction_requires_dag_graphs")
            raise ValueError(notes[-1])

        micro_mechanisms = _mechanism_by_variable(micro_scm)
        macro_mechanisms = _mechanism_by_variable(macro_scm)
        mapping_by_micro = abstraction_map.by_micro_variable
        mapping_by_macro = abstraction_map.by_macro_variable

        if set(mapping_by_micro) != set(micro_mechanisms):
            notes.append("abstraction_map_must_cover_all_micro_variables")
            raise ValueError(notes[-1])
        if set(mapping_by_macro) != set(macro_mechanisms):
            notes.append("abstraction_map_must_cover_all_macro_variables")
            raise ValueError(notes[-1])

        for micro_variable, variable_map in mapping_by_micro.items():
            macro_variable = variable_map.macro_variable
            micro_mechanism = micro_mechanisms[micro_variable]
            macro_mechanism = macro_mechanisms[macro_variable]

            mapped_parents = tuple(
                abstraction_map.micro_to_macro.get(parent, "") for parent in micro_mechanism.parents
            )
            if mapped_parents != tuple(macro_mechanism.parents):
                notes.append(f"parent_structure_mismatch:{micro_variable}->{macro_variable}")
                raise ValueError(notes[-1])

            micro_state_space, micro_table = _extract_finite_state_table(micro_mechanism)
            macro_state_space, macro_table = _extract_finite_state_table(macro_mechanism)

            if set(variable_map.state_map) != set(micro_state_space):
                notes.append(f"state_map_must_cover_micro_state_space:{micro_variable}")
                raise ValueError(notes[-1])
            if not set(variable_map.state_map.values()).issubset(set(macro_state_space)):
                notes.append(
                    f"state_map_targets_unknown_macro_states:{micro_variable}->{macro_variable}"
                )
                raise ValueError(notes[-1])

            for macro_parent_key, macro_distribution in macro_table.items():
                compatible_micro_keys = []
                for micro_parent_key in micro_table:
                    compatible = True
                    for micro_parent, micro_state in micro_parent_key:
                        mapped_macro_parent = abstraction_map.micro_to_macro[micro_parent]
                        expected_macro_state = dict(macro_parent_key)[mapped_macro_parent]
                        parent_map = mapping_by_micro[micro_parent].state_map
                        if parent_map[micro_state] != expected_macro_state:
                            compatible = False
                            break
                    if compatible:
                        compatible_micro_keys.append(micro_parent_key)

                if not compatible_micro_keys:
                    notes.append(
                        f"missing_micro_parent_assignment_for_macro_context:{macro_variable}"
                    )
                    raise ValueError(notes[-1])

                aggregated_candidates = [
                    _aggregate_distribution(micro_table[micro_key], variable_map.state_map)
                    for micro_key in compatible_micro_keys
                ]
                first_candidate = aggregated_candidates[0]
                if not all(
                    _distributions_match(first_candidate, candidate)
                    for candidate in aggregated_candidates[1:]
                ):
                    notes.append(
                        f"micro_conditionals_not_lumpable:{micro_variable}->{macro_variable}"
                    )
                    raise ValueError(notes[-1])
                if not _distributions_match(first_candidate, macro_distribution):
                    notes.append(f"macro_distribution_mismatch:{micro_variable}->{macro_variable}")
                    raise ValueError(notes[-1])

        return AbstractionCertificate(
            micro_graph_ref=micro_graph_ref,
            macro_graph_ref=macro_graph_ref,
            abstraction_map_ref=abstraction_map_ref,
            preservation_type=AbstractionPreservationType.EXACT,
            preserved_queries=tuple(preserved_queries or ("observational", "interventional")),
            error_bound=None,
            validation_notes=tuple(notes)
            if notes
            else ("exact_finite_state_abstraction_verified",),
        )
    except ValueError:
        return AbstractionCertificate(
            micro_graph_ref=micro_graph_ref,
            macro_graph_ref=macro_graph_ref,
            abstraction_map_ref=abstraction_map_ref,
            preservation_type=AbstractionPreservationType.INVALID,
            preserved_queries=(),
            error_bound=None,
            validation_notes=tuple(notes) if notes else ("exact_finite_state_abstraction_invalid",),
        )


@dataclass(frozen=True)
class _GaussianInterventionalSummary:
    order: tuple[str, ...]
    mean: np.ndarray
    covariance: np.ndarray


def _topological_order(scm: StructuralCausalModelSpec) -> tuple[str, ...]:
    if scm.graph.graph_type.value != "dag":
        raise ValueError("continuous abstraction requires DAG SCMs")
    indegree = dict.fromkeys(scm.graph.nodes, 0)
    children: dict[str, list[str]] = {node: [] for node in scm.graph.nodes}
    for edge in scm.graph.edges:
        indegree[edge.dst] += 1
        children[edge.src].append(edge.dst)

    queue = deque(node for node in scm.graph.nodes if indegree[node] == 0)
    order: list[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for child in children[node]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(order) != len(scm.graph.nodes):
        raise ValueError("continuous abstraction requires acyclic SCMs")
    return tuple(order)


def _parents_by_node(scm: StructuralCausalModelSpec) -> dict[str, tuple[str, ...]]:
    parents: dict[str, list[str]] = {node: [] for node in scm.graph.nodes}
    for edge in scm.graph.edges:
        parents[edge.dst].append(edge.src)
    return {node: tuple(items) for node, items in parents.items()}


def _continuous_default_preserved_queries(
    config: ContinuousApproximateAbstractionConfig,
    preserved_queries: tuple[str, ...] | list[str] | None,
) -> tuple[str, ...]:
    if preserved_queries is None:
        if config.preservation_type is AbstractionPreservationType.POLICY_VALUE_ONLY:
            return (f"{config.query_family}:macro",)
        return (f"{config.query_family}:macro", "policy_rank:top2")
    if not isinstance(preserved_queries, (tuple, list)):
        raise ValueError("preserved_queries must be a tuple/list when provided")
    normalized = tuple(
        _ensure_non_empty(str(item), field_name="preserved_queries") for item in preserved_queries
    )
    if not normalized:
        raise ValueError("preserved_queries must be non-empty when provided")
    return normalized


def _continuous_non_preserved_queries(
    config: ContinuousApproximateAbstractionConfig,
) -> tuple[str, ...]:
    if config.non_preserved_queries:
        return tuple(config.non_preserved_queries)
    return ("unit_level_counterfactual",)


def _merge_string_tuple(*values: Sequence[str]) -> tuple[str, ...]:
    merged: list[str] = []
    for value in values:
        for item in value:
            normalized = _ensure_non_empty(str(item), field_name="tuple_item")
            if normalized not in merged:
                merged.append(normalized)
    return tuple(merged)


def _validate_continuous_alignment(
    micro_scm: StructuralCausalModelSpec,
    macro_scm: StructuralCausalModelSpec,
    abstraction_map: FiniteStateAbstractionMap,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    micro_order = _topological_order(micro_scm)
    macro_order = _topological_order(macro_scm)
    mapping_by_micro = abstraction_map.by_micro_variable
    mapping_by_macro = abstraction_map.by_macro_variable

    if set(mapping_by_micro) != set(micro_scm.graph.nodes):
        raise ValueError("continuous_abstraction_map_must_cover_all_micro_variables")
    if set(mapping_by_macro) != set(macro_scm.graph.nodes):
        raise ValueError("continuous_abstraction_map_must_cover_all_macro_variables")

    micro_parents = _parents_by_node(micro_scm)
    macro_parents = _parents_by_node(macro_scm)
    for micro_variable, variable_map in mapping_by_micro.items():
        macro_variable = variable_map.macro_variable
        mapped_parents = tuple(
            abstraction_map.micro_to_macro.get(parent, "")
            for parent in micro_parents[micro_variable]
        )
        if mapped_parents != macro_parents[macro_variable]:
            raise ValueError(
                f"continuous_parent_structure_mismatch:{micro_variable}->{macro_variable}"
            )
    return micro_order, macro_order


def _continuous_transform_for_micro_variable(
    config: ContinuousApproximateAbstractionConfig,
    micro_variable: str,
) -> ContinuousAffineVariableTransform:
    transform = config.variable_transforms.get(micro_variable)
    if transform is not None:
        return transform
    return ContinuousAffineVariableTransform()


def _state_weights_for_order(
    config: ContinuousApproximateAbstractionConfig,
    macro_order: tuple[str, ...],
) -> np.ndarray:
    return np.asarray(
        [float(config.state_weights.get(variable, 1.0)) for variable in macro_order],
        dtype=float,
    )


def _policy_value_weights_for_order(
    config: ContinuousApproximateAbstractionConfig,
    macro_order: tuple[str, ...],
) -> np.ndarray:
    unknown = sorted(set(config.policy_value_weights) - set(macro_order))
    if unknown:
        raise ValueError(
            "policy_value_weights reference unknown macro variables: " + ", ".join(unknown)
        )
    return np.asarray(
        [float(config.policy_value_weights.get(variable, 0.0)) for variable in macro_order],
        dtype=float,
    )


def _weighted_l1_lipschitz_constant(
    policy_weights: np.ndarray,
    state_weights: np.ndarray,
) -> float:
    ratios: list[float] = []
    for policy_weight, state_weight in zip(policy_weights, state_weights, strict=False):
        if abs(policy_weight) <= _EXACT_MATCH_TOLERANCE:
            continue
        if state_weight <= _EXACT_MATCH_TOLERANCE:
            raise ValueError(
                "state_weights must be strictly positive for variables with non-zero "
                "policy_value_weights"
            )
        ratios.append(abs(float(policy_weight)) / float(state_weight))
    if not ratios:
        return 0.0
    return float(max(ratios))


def _linear_gaussian_root_params(mechanism: NodeMechanism) -> tuple[float, float]:
    params = mechanism.family_params
    if not isinstance(params, Mapping):
        raise ValueError(f"{mechanism.variable}.family_params must be a mapping")
    if mechanism.family.value == "linear":
        intercept = _ensure_finite(
            params.get("intercept", 0.0),
            field_name=f"{mechanism.variable}.intercept",
        )
        noise_std = _ensure_non_negative_finite(
            params.get("noise_std", params.get("std", 0.0)),
            field_name=f"{mechanism.variable}.noise_std",
        )
        return float(intercept or 0.0), float(noise_std or 0.0)
    mean = _ensure_finite(params.get("mean", 0.0), field_name=f"{mechanism.variable}.mean")
    std = _ensure_non_negative_finite(
        params.get("std", params.get("noise_std", 0.0)),
        field_name=f"{mechanism.variable}.std",
    )
    return float(mean or 0.0), float(std or 0.0)


def _linear_gaussian_terms(mechanism: NodeMechanism) -> tuple[float, dict[str, float], float]:
    if mechanism.family.value != "linear":
        raise ValueError(
            f"{mechanism.variable} must use MechanismFamily.LINEAR for "
            "continuous_linear_gaussian abstraction"
        )
    params = mechanism.family_params
    if not isinstance(params, Mapping):
        raise ValueError(f"{mechanism.variable}.family_params must be a mapping")
    intercept = _ensure_finite(
        params.get("intercept", 0.0),
        field_name=f"{mechanism.variable}.intercept",
    )
    coefficients_raw = params.get("coefficients", {})
    if not isinstance(coefficients_raw, Mapping):
        raise ValueError(f"{mechanism.variable}.coefficients must be a mapping")
    coefficients: dict[str, float] = {}
    for parent in mechanism.parents:
        coefficients[parent] = float(
            _ensure_finite(
                coefficients_raw.get(parent, 0.0),
                field_name=f"{mechanism.variable}.coefficients.{parent}",
            )
            or 0.0
        )
    extra = sorted(set(coefficients_raw) - set(mechanism.parents))
    if extra:
        raise ValueError(
            f"{mechanism.variable}.coefficients reference non-parent variables: {extra}"
        )
    noise_std = _ensure_non_negative_finite(
        params.get("noise_std", params.get("std", 0.0)),
        field_name=f"{mechanism.variable}.noise_std",
    )
    return float(intercept or 0.0), coefficients, float(noise_std or 0.0)


def _linear_gaussian_interventional_summary(
    scm: StructuralCausalModelSpec,
    *,
    interventions: Mapping[str, float],
    order: tuple[str, ...],
) -> _GaussianInterventionalSummary:
    mechanism_by_variable = _mechanism_by_variable(scm)
    missing = sorted(set(order) - set(mechanism_by_variable))
    if missing:
        raise ValueError(
            f"continuous_linear_gaussian requires mechanisms for every node; missing={missing}"
        )
    index_by_variable = {variable: idx for idx, variable in enumerate(order)}
    mean = np.zeros(len(order), dtype=float)
    covariance = np.zeros((len(order), len(order)), dtype=float)

    for idx, variable in enumerate(order):
        if variable in interventions:
            intervention_value = _ensure_finite(
                interventions[variable],
                field_name=f"interventions.{variable}",
            )
            if intervention_value is None:
                raise ValueError(f"interventions.{variable} must be finite")
            mean[idx] = float(intervention_value)
            continue

        mechanism = mechanism_by_variable[variable]
        if not mechanism.parents:
            root_mean, root_std = _linear_gaussian_root_params(mechanism)
            mean[idx] = root_mean
            covariance[idx, idx] = root_std**2
            continue

        intercept, coefficients, noise_std = _linear_gaussian_terms(mechanism)
        for parent in mechanism.parents:
            parent_idx = index_by_variable[parent]
            if parent_idx >= idx:
                raise ValueError(f"{variable} parents must appear earlier in topological order")

        mean[idx] = intercept + sum(
            coefficients[parent] * mean[index_by_variable[parent]] for parent in mechanism.parents
        )
        for prev_idx in range(idx):
            covariance[idx, prev_idx] = sum(
                coefficients[parent] * covariance[index_by_variable[parent], prev_idx]
                for parent in mechanism.parents
            )
            covariance[prev_idx, idx] = covariance[idx, prev_idx]

        coeff_vector = np.asarray(
            [coefficients[parent] for parent in mechanism.parents],
            dtype=float,
        )
        parent_indices = [index_by_variable[parent] for parent in mechanism.parents]
        parent_cov = covariance[np.ix_(parent_indices, parent_indices)]
        covariance[idx, idx] = float(coeff_vector @ parent_cov @ coeff_vector + (noise_std**2))

    return _GaussianInterventionalSummary(order=order, mean=mean, covariance=covariance)


def _continuous_intervention_vertices(
    ranges: Mapping[str, tuple[float, float]],
) -> tuple[dict[str, float], ...]:
    if not ranges:
        return ({},)
    variables = tuple(ranges)
    corners: list[dict[str, float]] = []
    bounds = [ranges[variable] for variable in variables]
    for vertex in product(*bounds):
        corners.append(
            {variable: float(value) for variable, value in zip(variables, vertex, strict=False)}
        )
    return tuple(corners)


def _abstract_micro_summary_into_macro_space(
    micro_summary: _GaussianInterventionalSummary,
    abstraction_map: FiniteStateAbstractionMap,
    config: ContinuousApproximateAbstractionConfig,
    *,
    macro_order: tuple[str, ...],
) -> _GaussianInterventionalSummary:
    micro_indices = {variable: idx for idx, variable in enumerate(micro_summary.order)}
    mean = np.zeros(len(macro_order), dtype=float)
    covariance = np.zeros((len(macro_order), len(macro_order)), dtype=float)

    micro_by_macro = abstraction_map.by_macro_variable
    transforms_by_macro = {
        macro_variable: _continuous_transform_for_micro_variable(
            config,
            micro_by_macro[macro_variable].micro_variable,
        )
        for macro_variable in macro_order
    }
    for idx, macro_variable in enumerate(macro_order):
        micro_variable = micro_by_macro[macro_variable].micro_variable
        micro_idx = micro_indices[micro_variable]
        transform = transforms_by_macro[macro_variable]
        mean[idx] = transform.scale * micro_summary.mean[micro_idx] + transform.shift
    for row, macro_row in enumerate(macro_order):
        row_micro = micro_by_macro[macro_row].micro_variable
        row_idx = micro_indices[row_micro]
        row_scale = transforms_by_macro[macro_row].scale
        for col, macro_col in enumerate(macro_order):
            col_micro = micro_by_macro[macro_col].micro_variable
            col_idx = micro_indices[col_micro]
            col_scale = transforms_by_macro[macro_col].scale
            covariance[row, col] = (
                row_scale * col_scale * micro_summary.covariance[row_idx, col_idx]
            )
    return _GaussianInterventionalSummary(order=macro_order, mean=mean, covariance=covariance)


def _psd_matrix_sqrt(matrix: np.ndarray) -> np.ndarray:
    sym = 0.5 * (matrix + matrix.T)
    eigenvalues, eigenvectors = np.linalg.eigh(sym)
    clipped = np.clip(eigenvalues, a_min=0.0, a_max=None)
    return eigenvectors @ np.diag(np.sqrt(clipped)) @ eigenvectors.T


def _gaussian_wasserstein_2(
    left_mean: np.ndarray,
    left_covariance: np.ndarray,
    right_mean: np.ndarray,
    right_covariance: np.ndarray,
) -> float:
    mean_term = float(np.sum((left_mean - right_mean) ** 2))
    left_sqrt = _psd_matrix_sqrt(left_covariance)
    inner = left_sqrt @ right_covariance @ left_sqrt
    trace_term = float(
        np.trace(left_covariance + right_covariance - (2.0 * _psd_matrix_sqrt(inner)))
    )
    return float(math.sqrt(max(mean_term + max(trace_term, 0.0), 0.0)))


def _matrix_spectral_radius(matrix: np.ndarray) -> float:
    if matrix.size == 0:
        return 0.0
    eigenvalues = np.linalg.eigvals(matrix)
    radius = float(np.max(np.abs(eigenvalues)))
    if radius <= _EXACT_MATCH_TOLERANCE:
        return 0.0
    return radius


def _continuous_certificate_metadata(
    *,
    config: ContinuousApproximateAbstractionConfig,
    preserved_queries: tuple[str, ...],
    error_bound: float,
    global_state_bound: float,
    gain_matrix_spectral_radius: float,
    tightness_status: str,
    diagnostics: dict[str, Any],
    bound_kind: str,
    value_lipschitz_constant: float,
) -> dict[str, Any]:
    error_bound_spec: dict[str, Any] = {
        "scope": {
            "query_family": config.query_family,
            "interventions": config.allowed_intervention_family,
            "action_domain": config.action_domain,
        },
        "state_metric": config.state_metric,
        "distribution_metric": config.distribution_metric,
        "value_lipschitz_constant": float(value_lipschitz_constant),
        "global_state_bound": float(global_state_bound),
        "recommendation_margin_required": float(2.0 * error_bound),
        "gain_matrix_spectral_radius": float(gain_matrix_spectral_radius),
        "tightness_status": tightness_status,
        "bound_kind": bound_kind,
        "error_metric": "policy_value_upper_bound",
        "error_scope": config.allowed_intervention_family,
    }
    if config.confidence_level is not None:
        error_bound_spec["confidence_level"] = float(config.confidence_level)
    if config.computation_artifact_ref is not None:
        error_bound_spec["computation_artifact_ref"] = config.computation_artifact_ref
    if config.local_defect_artifact_ref is not None:
        error_bound_spec["local_defect_artifact_ref"] = config.local_defect_artifact_ref

    return {
        "abstraction_family": config.family,
        "allowed_intervention_family": config.allowed_intervention_family,
        "intervention_family_verified": True,
        "proof_obligations_satisfied": _merge_string_tuple(
            (
                "approximate_abstraction_bound_verified",
                "decision_margin_gate_materialized",
            ),
            config.proof_obligations_satisfied,
        ),
        "estimand_error_bounds": {query: float(error_bound) for query in preserved_queries},
        "diagnostics": diagnostics,
        "non_preserved_queries": _continuous_non_preserved_queries(config),
        "error_bound_spec": error_bound_spec,
    }


def _verify_continuous_linear_gaussian_abstraction(
    micro_scm: StructuralCausalModelSpec,
    macro_scm: StructuralCausalModelSpec,
    abstraction_map: FiniteStateAbstractionMap,
    *,
    config: ContinuousApproximateAbstractionConfig,
    micro_graph_ref: ArtifactRefModel,
    macro_graph_ref: ArtifactRefModel,
    abstraction_map_ref: FiniteStateAbstractionMapRef,
    preserved_queries: tuple[str, ...],
) -> AbstractionCertificate:
    micro_order, macro_order = _validate_continuous_alignment(
        micro_scm,
        macro_scm,
        abstraction_map,
    )
    macro_variables = set(macro_order)
    unknown_interventions = sorted(set(config.intervention_ranges) - macro_variables)
    if unknown_interventions:
        raise ValueError(
            "intervention_ranges reference unknown macro variables: "
            + ", ".join(unknown_interventions)
        )

    state_weights = _state_weights_for_order(config, macro_order)
    policy_weights = _policy_value_weights_for_order(config, macro_order)
    derived_lipschitz = _weighted_l1_lipschitz_constant(policy_weights, state_weights)
    value_lipschitz_constant = float(max(config.value_lipschitz_constant or 0.0, derived_lipschitz))
    if value_lipschitz_constant <= _EXACT_MATCH_TOLERANCE and not np.any(
        np.abs(policy_weights) > _EXACT_MATCH_TOLERANCE
    ):
        raise ValueError(
            "continuous_linear_gaussian requires non-zero policy_value_weights or "
            "value_lipschitz_constant"
        )

    intervention_vertices = _continuous_intervention_vertices(config.intervention_ranges)
    gain_matrix = np.zeros((len(macro_order), len(macro_order)), dtype=float)
    macro_mechanisms = _mechanism_by_variable(macro_scm)
    macro_indices = {variable: idx for idx, variable in enumerate(macro_order)}
    for variable, mechanism in macro_mechanisms.items():
        if mechanism.parents:
            _, coefficients, _ = _linear_gaussian_terms(mechanism)
            for parent, coefficient in coefficients.items():
                gain_matrix[macro_indices[variable], macro_indices[parent]] = abs(coefficient)
    gain_matrix_spectral_radius = _matrix_spectral_radius(gain_matrix)

    max_state_bound = 0.0
    max_distribution_bound = 0.0
    max_error_bound = 0.0
    maximizing_intervention: dict[str, float] | None = None
    maximizing_mean_error: dict[str, float] = {}

    for intervention in intervention_vertices:
        micro_intervention = {
            abstraction_map.by_macro_variable[macro_variable].micro_variable: value
            for macro_variable, value in intervention.items()
        }
        micro_summary = _linear_gaussian_interventional_summary(
            micro_scm,
            interventions=micro_intervention,
            order=micro_order,
        )
        macro_summary = _linear_gaussian_interventional_summary(
            macro_scm,
            interventions=intervention,
            order=macro_order,
        )
        abstracted_micro = _abstract_micro_summary_into_macro_space(
            micro_summary,
            abstraction_map,
            config,
            macro_order=macro_order,
        )
        mean_difference = abstracted_micro.mean - macro_summary.mean
        state_bound = float(np.sum(state_weights * np.abs(mean_difference)))
        distribution_bound = _gaussian_wasserstein_2(
            abstracted_micro.mean,
            abstracted_micro.covariance,
            macro_summary.mean,
            macro_summary.covariance,
        )
        if np.any(np.abs(policy_weights) > _EXACT_MATCH_TOLERANCE):
            value_bound = float(abs(policy_weights @ mean_difference))
        else:
            value_bound = float(value_lipschitz_constant * distribution_bound)

        if value_bound + _EXACT_MATCH_TOLERANCE >= max_error_bound:
            max_state_bound = state_bound
            max_distribution_bound = distribution_bound
            max_error_bound = value_bound
            maximizing_intervention = dict(intervention)
            maximizing_mean_error = {
                variable: float(delta)
                for variable, delta in zip(macro_order, mean_difference, strict=False)
            }

    tightness_status = (
        "exact_on_linear_gaussian"
        if np.any(np.abs(policy_weights) > _EXACT_MATCH_TOLERANCE)
        else "upper_bound_only"
    )
    bound_kind = (
        "linear_policy_value_exact"
        if tightness_status == "exact_on_linear_gaussian"
        else "policy_value_upper_bound"
    )
    diagnostics = dict(config.diagnostics)
    diagnostics.update(
        {
            "intervention_vertices_evaluated": len(intervention_vertices),
            "maximizing_intervention": maximizing_intervention or {},
            "max_mean_error_by_variable": maximizing_mean_error,
            "global_state_bound": float(max_state_bound),
            "wasserstein_bound": float(max_distribution_bound),
        }
    )

    metadata = _continuous_certificate_metadata(
        config=config,
        preserved_queries=preserved_queries,
        error_bound=float(max_error_bound),
        global_state_bound=float(max_state_bound),
        gain_matrix_spectral_radius=gain_matrix_spectral_radius,
        tightness_status=tightness_status,
        diagnostics=diagnostics,
        bound_kind=bound_kind,
        value_lipschitz_constant=value_lipschitz_constant,
    )
    return AbstractionCertificate(
        micro_graph_ref=micro_graph_ref,
        macro_graph_ref=macro_graph_ref,
        abstraction_map_ref=abstraction_map_ref,
        preservation_type=config.preservation_type,
        preserved_queries=preserved_queries,
        error_bound=float(max_error_bound),
        validation_notes=(
            "approximate_abstraction_bound_verified",
            f"bound_kind={bound_kind}",
            f"underlying_metric={config.distribution_metric}",
            f"tightness_status={tightness_status}",
        ),
        metadata=metadata,
    )


def _verify_continuous_lipschitz_dag_abstraction(
    micro_scm: StructuralCausalModelSpec,
    macro_scm: StructuralCausalModelSpec,
    abstraction_map: FiniteStateAbstractionMap,
    *,
    config: ContinuousApproximateAbstractionConfig,
    micro_graph_ref: ArtifactRefModel,
    macro_graph_ref: ArtifactRefModel,
    abstraction_map_ref: FiniteStateAbstractionMapRef,
    preserved_queries: tuple[str, ...],
) -> AbstractionCertificate:
    _, macro_order = _validate_continuous_alignment(
        micro_scm,
        macro_scm,
        abstraction_map,
    )
    macro_parents = _parents_by_node(macro_scm)
    macro_indices = {variable: idx for idx, variable in enumerate(macro_order)}

    missing_defects = sorted(set(macro_order) - set(config.local_mechanism_defects))
    if missing_defects:
        raise ValueError(
            f"local_mechanism_defects must cover every macro variable; missing={missing_defects}"
        )

    gain_matrix = np.zeros((len(macro_order), len(macro_order)), dtype=float)
    for child, parent_gains in config.gain_matrix.items():
        if child not in macro_indices:
            raise ValueError(f"gain_matrix references unknown child variable '{child}'")
        for parent, gain in parent_gains.items():
            if parent not in macro_indices:
                raise ValueError(f"gain_matrix references unknown parent variable '{parent}'")
            if parent not in macro_parents[child]:
                raise ValueError(
                    f"gain_matrix parent '{parent}' is not a declared parent of '{child}'"
                )
            gain_matrix[macro_indices[child], macro_indices[parent]] = float(gain)

    gain_matrix_spectral_radius = _matrix_spectral_radius(gain_matrix)
    if gain_matrix_spectral_radius >= 1.0 - _EXACT_MATCH_TOLERANCE:
        raise ValueError("continuous_lipschitz_dag requires gain_matrix spectral radius < 1")

    defects = np.asarray(
        [config.local_mechanism_defects[variable] for variable in macro_order],
        dtype=float,
    )
    global_error = np.linalg.solve(np.eye(len(macro_order), dtype=float) - gain_matrix, defects)
    if np.any(global_error < -_EXACT_MATCH_TOLERANCE):
        raise ValueError("continuous_lipschitz_dag produced negative propagated bounds")
    global_error = np.clip(global_error, a_min=0.0, a_max=None)

    state_weights = _state_weights_for_order(config, macro_order)
    policy_weights = _policy_value_weights_for_order(config, macro_order)
    derived_lipschitz = _weighted_l1_lipschitz_constant(policy_weights, state_weights)
    value_lipschitz_constant = float(max(config.value_lipschitz_constant or 0.0, derived_lipschitz))
    if value_lipschitz_constant <= _EXACT_MATCH_TOLERANCE:
        raise ValueError("continuous_lipschitz_dag requires non-zero value_lipschitz_constant")

    global_state_bound = float(state_weights @ global_error)
    error_bound = float(value_lipschitz_constant * global_state_bound)
    diagnostics = dict(config.diagnostics)
    diagnostics.update(
        {
            "local_mechanism_defects": {
                variable: float(config.local_mechanism_defects[variable])
                for variable in macro_order
            },
            "global_error_bound_by_variable": {
                variable: float(bound)
                for variable, bound in zip(macro_order, global_error, strict=False)
            },
            "gain_matrix": {
                child: {parent: float(gain) for parent, gain in row.items()}
                for child, row in config.gain_matrix.items()
            },
            "global_state_bound": global_state_bound,
            "distribution_bound": global_state_bound,
        }
    )

    metadata = _continuous_certificate_metadata(
        config=config,
        preserved_queries=preserved_queries,
        error_bound=error_bound,
        global_state_bound=global_state_bound,
        gain_matrix_spectral_radius=gain_matrix_spectral_radius,
        tightness_status="upper_bound_only",
        diagnostics=diagnostics,
        bound_kind="policy_value_upper_bound",
        value_lipschitz_constant=value_lipschitz_constant,
    )
    return AbstractionCertificate(
        micro_graph_ref=micro_graph_ref,
        macro_graph_ref=macro_graph_ref,
        abstraction_map_ref=abstraction_map_ref,
        preservation_type=config.preservation_type,
        preserved_queries=preserved_queries,
        error_bound=error_bound,
        validation_notes=(
            "approximate_abstraction_bound_verified",
            "bound_kind=policy_value_upper_bound",
            f"underlying_metric={config.distribution_metric}",
            "tightness_status=upper_bound_only",
        ),
        metadata=metadata,
    )


def verify_continuous_approximate_abstraction(
    micro_scm: StructuralCausalModelSpec,
    macro_scm: StructuralCausalModelSpec,
    abstraction_map: FiniteStateAbstractionMap,
    *,
    bound_config: ContinuousApproximateAbstractionConfig | Mapping[str, Any],
    micro_graph_ref: ArtifactRefModel,
    macro_graph_ref: ArtifactRefModel,
    abstraction_map_ref: FiniteStateAbstractionMapRef,
    preserved_queries: tuple[str, ...] | list[str] | None = None,
) -> AbstractionCertificate:
    """Verify a continuous approximate abstraction and return a certificate."""

    try:
        config = (
            bound_config
            if isinstance(bound_config, ContinuousApproximateAbstractionConfig)
            else ContinuousApproximateAbstractionConfig.model_validate(bound_config)
        )
        resolved_queries = _continuous_default_preserved_queries(config, preserved_queries)
        if config.family == "continuous_linear_gaussian":
            return _verify_continuous_linear_gaussian_abstraction(
                micro_scm,
                macro_scm,
                abstraction_map,
                config=config,
                micro_graph_ref=micro_graph_ref,
                macro_graph_ref=macro_graph_ref,
                abstraction_map_ref=abstraction_map_ref,
                preserved_queries=resolved_queries,
            )
        if config.family == "continuous_lipschitz_dag":
            return _verify_continuous_lipschitz_dag_abstraction(
                micro_scm,
                macro_scm,
                abstraction_map,
                config=config,
                micro_graph_ref=micro_graph_ref,
                macro_graph_ref=macro_graph_ref,
                abstraction_map_ref=abstraction_map_ref,
                preserved_queries=resolved_queries,
            )
        raise ValueError(f"unsupported continuous abstraction family '{config.family}'")
    except ValueError as exc:
        note = _ensure_non_empty(
            str(exc) or "continuous_approximate_abstraction_invalid",
            field_name="validation_note",
        )
        return AbstractionCertificate(
            micro_graph_ref=micro_graph_ref,
            macro_graph_ref=macro_graph_ref,
            abstraction_map_ref=abstraction_map_ref,
            preservation_type=AbstractionPreservationType.INVALID,
            preserved_queries=(),
            error_bound=None,
            validation_notes=(note,),
        )


__all__ = [
    "APPROXIMATE_TRANSPORT_ABSTRACTION_FAMILIES",
    "AbstractionCertificate",
    "AbstractionPreservationType",
    "ContinuousAffineVariableTransform",
    "ContinuousApproximateAbstractionConfig",
    "FiniteStateAbstractionMap",
    "VariableStateAbstraction",
    "abstraction_allowed_intervention_family",
    "abstraction_error_bound_spec",
    "abstraction_estimand_error_bounds",
    "abstraction_preserves_query",
    "abstraction_recommendation_margin_required",
    "load_abstraction_certificate",
    "load_finite_state_abstraction_map",
    "persist_abstraction_certificate",
    "persist_finite_state_abstraction_map",
    "verify_continuous_approximate_abstraction",
    "verify_finite_state_exact_abstraction",
]
