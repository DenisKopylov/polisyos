"""Define persisted causal query requests and their Monte-Carlo result payloads."""

from __future__ import annotations

import math
from collections.abc import Mapping
from enum import Enum
from typing import Any, Literal, TypeGuard, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir._internal.validation import coerce_float
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef  # noqa: TC001
from polisyos.ir.artifacts.contracts import ArtifactOwnerDeclaration, CanonInfo
from polisyos.ir.artifacts.io import _get_owned_json_artifact, _put_owned_json_artifact
from polisyos.ir.migrations.base import (
    CompatibilityMode,
    IRRepresentationKey,
    IRRepresentationRegistration,
    ResolvedSchemaAdmission,
    register_ir_representation,
    register_schema_version,
)
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import CausalQueryResultRef


def _is_json_number_primitive(value: object) -> TypeGuard[int | float]:
    """Match the JSON-number admission check without admitting booleans."""

    return type(value) in {int, float}


class QueryType(str, Enum):
    """High-level family of causal query requested from the engine."""

    INTERVENTIONAL = "interventional"
    COUNTERFACTUAL = "counterfactual"
    ATTRIBUTION = "attribution"
    SOFT_INTERVENTION = "soft_intervention"


class InterventionType(str, Enum):
    """Mechanics of the treatment perturbation encoded in a query."""

    ATOMIC = "atomic"
    TRUNCATED = "truncated"
    SHIFTED = "shifted"
    STOCHASTIC = "stochastic"


class InterventionSpec(BaseModel):
    """Treatment perturbation attached to a causal query."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: InterventionType = InterventionType.ATOMIC
    value: float | None = None
    distribution: str | None = None
    bounds: tuple[float, float] | None = None
    shift: float | None = None
    legal_constraint_id: str | None = None

    @field_validator("value", "shift", mode="before")
    @classmethod
    def _coerce_optional_float(cls, value: object) -> float | None:
        if value is None:
            return None
        casted = coerce_float(value)
        if not math.isfinite(casted):
            raise ValueError("value must be finite")
        return casted

    @field_validator("bounds", mode="before")
    @classmethod
    def _coerce_bounds(cls, value: object) -> tuple[float, float] | None:
        if value is None:
            return None
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise ValueError("bounds must be a tuple/list of length 2")
        lo = coerce_float(value[0])
        hi = coerce_float(value[1])
        if not math.isfinite(lo) or not math.isfinite(hi):
            raise ValueError("bounds must be finite")
        return (lo, hi)

    @model_validator(mode="after")
    def _validate_payload(self) -> InterventionSpec:
        if self.type is InterventionType.TRUNCATED:
            if self.bounds is None:
                raise ValueError("bounds are required for truncated interventions")
            lo, hi = self.bounds
            if lo > hi:
                raise ValueError("bounds lower cannot exceed upper")

        if self.type is InterventionType.SHIFTED and self.shift is None:
            raise ValueError("shift is required for shifted interventions")

        if self.type is InterventionType.STOCHASTIC and (
            not self.distribution or not self.distribution.strip()
        ):
            raise ValueError("distribution is required for stochastic interventions")

        return self


class CausalRegime(BaseModel):
    """Describe an attribution comparator without conflating observation and intervention."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["observational", "interventional"]
    intervention: InterventionSpec | None = None

    @model_validator(mode="after")
    def _validate_regime(self) -> CausalRegime:
        if self.kind == "interventional" and self.intervention is None:
            raise ValueError("intervention is required for an interventional regime")
        if (
            self.kind == "interventional"
            and self.intervention is not None
            and self.intervention.type is InterventionType.ATOMIC
            and self.intervention.value is None
        ):
            raise ValueError("interventional comparator atomic value is required")
        if self.kind == "observational" and self.intervention is not None:
            raise ValueError("observational regime must not carry an intervention")
        return self


class CausalContrastSpec(BaseModel):
    """Typed target/comparator arms for an attribution query.

    The target is deliberately an :class:`InterventionSpec`, making an
    interventional target impossible to confuse with an observational regime.
    The comparator remains a tagged regime because observational and explicit
    interventional baselines have materially different semantics.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: InterventionSpec
    comparator: CausalRegime

    @model_validator(mode="before")
    @classmethod
    def _reject_observational_target(cls, value: object) -> object:
        if isinstance(value, Mapping):
            target = value.get("target")
            if isinstance(target, Mapping) and target.get("kind") == "observational":
                raise ValueError("target regime must be interventional")
        return value

    @model_validator(mode="after")
    def _validate_target(self) -> CausalContrastSpec:
        if self.target.type is InterventionType.ATOMIC and self.target.value is None:
            raise ValueError("target intervention value is required")
        return self


# Compatibility names used by early E02 callers.  They intentionally resolve
# to the canonical typed contract rather than retaining a second wire shape.
CausalContrastRegime = CausalRegime
CausalAttributionSpec = CausalContrastSpec


class CausalQuery(BaseModel):
    """Fully specified causal query contract for execution or persistence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query_type: QueryType
    treatment_variable: str
    treatment_value: float | None = None
    outcome_variable: str
    condition: dict[str, float] = Field(default_factory=dict)
    n_samples: int = Field(default=1000, ge=1)
    intervention_spec: InterventionSpec | None = None
    contrast: CausalContrastSpec | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_attribution(cls, value: object) -> object:
        """Map legacy ATTRIBUTION fields to explicit target/comparator arms."""
        if not isinstance(value, Mapping):
            return value
        payload = dict(value)
        query_type = payload.get("query_type")
        if query_type != QueryType.ATTRIBUTION and query_type != QueryType.ATTRIBUTION.value:
            return payload
        if payload.get("contrast") is not None:
            return payload

        legacy_intervention = payload.get("intervention_spec")
        if legacy_intervention is None:
            legacy_intervention = {
                "type": InterventionType.ATOMIC.value,
                "value": payload.get("treatment_value"),
            }
        elif isinstance(legacy_intervention, Mapping):
            legacy_intervention = dict(legacy_intervention)
            intervention_type = legacy_intervention.get("type")
            if (
                intervention_type in {InterventionType.ATOMIC, InterventionType.ATOMIC.value}
                and legacy_intervention.get("value") is None
                and payload.get("treatment_value") is not None
            ):
                legacy_intervention["value"] = payload["treatment_value"]
                payload["intervention_spec"] = legacy_intervention
        elif (
            isinstance(legacy_intervention, InterventionSpec)
            and legacy_intervention.type is InterventionType.ATOMIC
            and legacy_intervention.value is None
            and payload.get("treatment_value") is not None
        ):
            legacy_intervention = InterventionSpec.model_validate(
                {
                    **legacy_intervention.model_dump(mode="python"),
                    "value": payload["treatment_value"],
                }
            )
            payload["intervention_spec"] = legacy_intervention
        payload["contrast"] = {
            "target": legacy_intervention,
            "comparator": {"kind": "observational"},
        }
        return payload

    @field_validator("treatment_variable", "outcome_variable")
    @classmethod
    def _validate_variable_name(cls, value: str) -> str:
        candidate = str(value).strip()
        if not candidate:
            raise ValueError("variable names must be non-empty")
        return candidate

    @field_validator("treatment_value", mode="before")
    @classmethod
    def _coerce_treatment_value(cls, value: object) -> float | None:
        if value is None:
            return None
        casted = coerce_float(value)
        if not math.isfinite(casted):
            raise ValueError("treatment_value must be finite")
        return casted

    @field_validator("condition", mode="before")
    @classmethod
    def _coerce_condition(cls, value: object) -> dict[str, float]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("condition must be a mapping")
        normalized: dict[str, float] = {}
        for key, raw in value.items():
            name = str(key).strip()
            if not name:
                raise ValueError("condition keys must be non-empty")
            item = coerce_float(raw)
            if not math.isfinite(item):
                raise ValueError("condition values must be finite")
            normalized[name] = item
        return normalized

    @model_validator(mode="after")
    def _validate_semantics(self) -> CausalQuery:
        if self.query_type is QueryType.COUNTERFACTUAL and not self.condition:
            raise ValueError("counterfactual queries require non-empty condition")

        if self.query_type is QueryType.SOFT_INTERVENTION:
            if self.intervention_spec is None:
                raise ValueError("soft_intervention queries require intervention_spec")
            if self.intervention_spec.type is InterventionType.ATOMIC:
                raise ValueError("soft_intervention queries require non-atomic intervention_spec")

        if self.query_type is QueryType.ATTRIBUTION:
            if self.contrast is None:
                raise ValueError("attribution queries require a target/comparator contrast")
            target_intervention = self.contrast.target
            if self.intervention_spec is not None and self.intervention_spec != target_intervention:
                raise ValueError("intervention_spec conflicts with the explicit attribution target")
            if self.treatment_value is not None and (
                target_intervention.type is not InterventionType.ATOMIC
                or target_intervention.value is None
                or not math.isclose(
                    float(self.treatment_value), float(target_intervention.value), rel_tol=0.0
                )
            ):
                raise ValueError("treatment_value must match the attribution target intervention")
        elif self.contrast is not None:
            raise ValueError("contrast is only valid for attribution queries")

        effective_intervention = self.intervention_spec.type if self.intervention_spec else None
        if (
            effective_intervention is None
            and self.query_type in {QueryType.INTERVENTIONAL, QueryType.COUNTERFACTUAL}
            and self.treatment_value is None
        ):
            raise ValueError("treatment_value is required for atomic interventions")
        elif effective_intervention is InterventionType.ATOMIC:
            if self.intervention_spec is None:
                raise ValueError("internal validation error: intervention_spec missing")
            if self.intervention_spec.value is None and self.treatment_value is None:
                raise ValueError("treatment_value is required for atomic interventions")

        return self

    @property
    def effective_treatment_value(self) -> float | None:
        if self.intervention_spec is not None and self.intervention_spec.value is not None:
            return float(self.intervention_spec.value)
        if self.contrast is not None and self.contrast.target.value is not None:
            return float(self.contrast.target.value)
        if self.treatment_value is not None:
            return float(self.treatment_value)
        return None


_CAUSAL_QUERY_RESULT_SCHEMA_VERSION = "1.2"
_LEGACY_CAUSAL_QUERY_RESULT_SCHEMA_VERSION = "1.0"


class CausalResultKind(str, Enum):
    """Meaning of draws from a fixed SCM, distinct from estimator sampling."""

    OUTCOME_DISTRIBUTION = "outcome_distribution"
    ITE_DISTRIBUTION = "ite_distribution"
    POSTERIOR_CREDIBLE_INTERVAL = "posterior_credible_interval"


class CausalEstimatorInterval(BaseModel):
    """An iid-unit bootstrap interval from refitted replicate estimators.

    The record describes sampling inference under its declared iid/model scope.
    Source custody, graph identification and domain authority remain separate.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    result_kind: Literal["estimator_confidence_interval"] = "estimator_confidence_interval"
    method: Literal["iid_unit_refit_bootstrap"] = "iid_unit_refit_bootstrap"
    resampling_unit: Literal["iid_observation_row"] = "iid_observation_row"
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    point_estimate: float
    interval: tuple[float, float]
    source_artifact_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    data_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    row_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    graph_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    resample_indices_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    target_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    n_units: int = Field(ge=2, strict=True)
    replicate_count: int = Field(ge=2, strict=True)
    seed: int = Field(strict=True)
    refit_scope: tuple[str, ...] = Field(min_length=1)
    fit_profile: str = Field(min_length=1)
    fit_request_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    refit_worker_response: dict[str, Any]
    replicate_estimates: tuple[float, ...]
    coverage_profile: Literal["approximate_iid_percentile_fixed_identified_graph"] = (
        "approximate_iid_percentile_fixed_identified_graph"
    )

    @field_validator("point_estimate", "confidence_level", mode="before")
    @classmethod
    def _require_numeric_scalar(cls, value: object) -> int | float:
        if not _is_json_number_primitive(value):
            raise ValueError("estimator inference requires finite JSON number primitives")
        return value

    @field_validator("interval", "replicate_estimates", mode="before")
    @classmethod
    def _require_numeric_vector(cls, value: object) -> list[int | float] | tuple[int | float, ...]:
        if not isinstance(value, (list, tuple)) or any(
            not _is_json_number_primitive(item) for item in value
        ):
            raise ValueError("estimator inference requires arrays of finite JSON number primitives")
        return cast("list[int | float] | tuple[int | float, ...]", value)

    @model_validator(mode="after")
    def _validate_replicates(self) -> CausalEstimatorInterval:
        values = (self.point_estimate, *self.interval, *self.replicate_estimates)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("estimator interval and replicate estimates must be finite")
        if len(self.replicate_estimates) != self.replicate_count:
            raise ValueError("replicate count must match refitted estimator count")
        if self.interval[0] > self.interval[1]:
            raise ValueError("estimator interval bounds must be ordered")
        if not self.interval[0] <= self.point_estimate <= self.interval[1]:
            raise ValueError("estimator interval must contain its point estimate")
        return self

    def to_uncertainty_envelope(self) -> UncertaintyEnvelope:
        """Project estimator inference without admitting domain authority."""
        return UncertaintyEnvelope(
            point_estimate=self.point_estimate,
            confidence_interval=self.interval,
            confidence_level=self.confidence_level,
            distribution_family=DistributionFamily.BOOTSTRAP,
            source=UncertaintySource.CAUSAL,
            propagation_method=PropagationMethod.MONTE_CARLO,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            sample_size=self.n_units,
            gate_eligible=False,
            metadata={
                **self.model_dump(mode="json", exclude={"refit_worker_response"}),
                "authority_limitation": "iid law and causal graph require separate admission",
            },
        )


def _causal_distribution_envelope(
    *,
    kind: CausalResultKind,
    point: float,
    bounds: tuple[float, float],
    n_samples: int | None,
    level: float,
    metadata: dict[str, Any],
) -> UncertaintyEnvelope:
    """Use the current shared IR conservatively for fixed-model distributions."""
    posterior = kind is CausalResultKind.POSTERIOR_CREDIBLE_INTERVAL
    return UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=bounds,
        confidence_level=level if posterior else None,
        distribution_family=DistributionFamily.BAYESIAN
        if posterior
        else DistributionFamily.UNKNOWN,
        source=UncertaintySource.CAUSAL,
        propagation_method=PropagationMethod.MONTE_CARLO,
        interval_semantics=IntervalSemantics.CREDIBLE_INTERVAL
        if posterior
        else IntervalSemantics.HEURISTIC_RANGE,
        sample_size=n_samples,
        is_heuristic_ci=not posterior,
        gate_eligible=False,
        metadata={
            **metadata,
            "result_kind": kind.value,
            "authority_limitation": "fixed-model distribution is not estimator sampling inference",
        },
    )


class CausalQueryResult(BaseModel):
    """Result payload returned for a persisted or in-memory causal query."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(_CAUSAL_QUERY_RESULT_SCHEMA_VERSION, pattern=r"^\d+\.\d+$")
    query: CausalQuery
    result_kind: CausalResultKind = CausalResultKind.OUTCOME_DISTRIBUTION
    interval_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    estimator_interval: CausalEstimatorInterval | None = None
    result_mean: float
    result_std: float = Field(ge=0.0)
    result_ci: tuple[float, float]
    result_distribution: list[float] | None = None
    computation_time_seconds: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_schema(cls, value: object) -> object:
        """Normalize legacy payloads without trusting unbound source provenance."""
        if not isinstance(value, Mapping):
            return value
        payload = dict(value)
        if payload.get("schema_version") is None:
            return payload
        source_version = str(payload["schema_version"])
        if source_version in {_LEGACY_CAUSAL_QUERY_RESULT_SCHEMA_VERSION, "1.1"}:
            metadata = dict(payload.get("metadata") or {})
            if any(
                metadata.get(key) is not None
                for key in ("source_schema_version", "source_schema_name")
            ):
                raise ValueError(
                    "legacy causal query result source provenance requires a CAS manifest"
                )
            metadata.pop("source_schema_version", None)
            metadata.pop("source_schema_name", None)
            if metadata:
                payload["metadata"] = metadata
            else:
                payload.pop("metadata", None)
            payload["result_kind"] = CausalResultKind.OUTCOME_DISTRIBUTION.value
            payload["estimator_interval"] = None
            payload["schema_version"] = _CAUSAL_QUERY_RESULT_SCHEMA_VERSION
        return payload

    @field_validator("result_mean", "result_std", "computation_time_seconds", mode="before")
    @classmethod
    def _coerce_scalar(cls, value: object) -> float:
        casted = coerce_float(value)
        if not math.isfinite(casted):
            raise ValueError("numeric values must be finite")
        return casted

    @field_validator("result_ci", mode="before")
    @classmethod
    def _coerce_ci(cls, value: object) -> tuple[float, float]:
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise ValueError("result_ci must be a tuple/list of length 2")
        lo = coerce_float(value[0])
        hi = coerce_float(value[1])
        if not math.isfinite(lo) or not math.isfinite(hi):
            raise ValueError("result_ci bounds must be finite")
        return (lo, hi)

    @field_validator("result_distribution", mode="before")
    @classmethod
    def _coerce_distribution(cls, value: object) -> list[float] | None:
        if value is None:
            return None
        if not isinstance(value, list):
            raise ValueError("result_distribution must be a list of floats")
        normalized: list[float] = []
        for item in value:
            casted = coerce_float(item)
            if not math.isfinite(casted):
                raise ValueError("result_distribution values must be finite")
            normalized.append(casted)
        return normalized

    @model_validator(mode="after")
    def _validate_result(self) -> CausalQueryResult:
        lo, hi = self.result_ci
        if lo > hi:
            raise ValueError("result_ci lower cannot exceed upper")
        if not (lo <= self.result_mean <= hi):
            raise ValueError("result_mean must lie inside result_ci")
        if self.query.contrast is not None:
            metadata = dict(self.metadata)
            target_payload = self.query.contrast.target.model_dump(mode="json")
            comparator_payload = self.query.contrast.comparator.model_dump(mode="json")
            for key, expected in (
                ("contrast_target", target_payload),
                ("contrast_comparator", comparator_payload),
            ):
                if key in metadata and metadata[key] != expected:
                    raise ValueError(f"{key} metadata conflicts with query contrast")
                metadata[key] = expected
            object.__setattr__(self, "metadata", metadata)
        return self

    def to_uncertainty_envelope(self) -> UncertaintyEnvelope:
        metadata = dict(self.metadata)
        if self.query.contrast is not None:
            target_payload = self.query.contrast.target.model_dump(mode="json")
            comparator_payload = self.query.contrast.comparator.model_dump(mode="json")
            for key, expected in (
                ("contrast_target", target_payload),
                ("contrast_comparator", comparator_payload),
            ):
                if key in metadata and metadata[key] != expected:
                    raise ValueError(f"{key} metadata conflicts with query contrast")
                metadata[key] = expected
        return _causal_distribution_envelope(
            kind=self.result_kind,
            point=float(self.result_mean),
            bounds=self.result_ci,
            level=self.interval_level,
            n_samples=self.query.n_samples,
            metadata={
                "query_type": self.query.query_type.value,
                "treatment_variable": self.query.treatment_variable,
                "outcome_variable": self.query.outcome_variable,
                **metadata,
            },
        )

    def to_estimator_uncertainty_envelope(self) -> UncertaintyEnvelope | None:
        """Return a separate estimator CI only when a refit record exists."""
        return (
            self.estimator_interval.to_uncertainty_envelope() if self.estimator_interval else None
        )


class CausalInterventionSpec(InterventionSpec):
    """Expose the causal-query intervention payload under the legacy public name.

    The semantics are identical to :class:`InterventionSpec`; this alias exists
    so older callers can migrate without changing payload structure.
    """


def _family_payload_version(value: object) -> str | None:
    """Return a strict embedded version, distinguishing absence from malformed null."""
    if not isinstance(value, Mapping):
        raise ValueError("owned family payload must be an object")
    if "schema_version" not in value:
        return None
    version = value["schema_version"]
    if type(version) is not str or not version.strip():
        raise ValueError("owned family payload schema_version must be a nonempty string")
    return version


def _family_source_mapping(value: object, admission: ResolvedSchemaAdmission) -> dict[str, Any]:
    """Bind payload bytes to the exact tuple already selected from the owner snapshot."""
    if not isinstance(value, Mapping):
        raise ValueError("owned family payload must be an object")
    if _family_payload_version(value) != admission.source_registration.payload_version:
        raise ValueError("payload version differs from exact registered tuple")
    return dict(value)


def _family_profile(profile: CanonInfo, row: IRRepresentationRegistration) -> bool:
    """Require the producer's actual canonicalization profile and no profile alias."""
    return (
        profile == CanonInfo.from_spec(CanonSpec(forbid_floats=False)) and row.profile_ref is None
    )


_CAUSAL_QUERY_LEGACY_POLICY = ("causal-query-legacy-json", "1")
_CAUSAL_QUERY_CURRENT_POLICY = ("causal-query-current-json", "1")
_CAUSAL_QUERY_OWNER = ArtifactOwnerDeclaration(
    contract_id="polisyos.ir.analytics.causal_queries.CausalQueryResult",
    dto_fqn="polisyos.ir.analytics.causal_queries.CausalQueryResult",
    abi_key="causal_query_result",
    registry_key="causal_query_result",
    kind="ir.causal_query_result",
    media_type="application/json",
    purpose="causal_query_result",
    policy_revision="1",
    accepted_wire_policies=(_CAUSAL_QUERY_LEGACY_POLICY, _CAUSAL_QUERY_CURRENT_POLICY),
    payload_version_of=_family_payload_version,
    validate_source=_family_source_mapping,
    project_for_consumer=lambda value, admission: _project_causal_query(value, admission),
    validate_profile=_family_profile,
)


def _project_causal_query(
    value: dict[str, Any], admission: ResolvedSchemaAdmission
) -> CausalQueryResult:
    """Run the declared legacy adapter or preserve an admitted current-law representation."""
    row = admission.source_registration
    payload = dict(value)
    if (row.wire_policy_ref, row.wire_policy_revision) == _CAUSAL_QUERY_LEGACY_POLICY:
        metadata = dict(payload.get("metadata") or {})
        source_version = row.schema_version
        if metadata.get("source_schema_version") not in (None, source_version):
            raise ValueError("legacy query provenance conflicts with CAS manifest")
        if metadata.get("source_schema_name") not in (None, row.schema_name):
            raise ValueError("legacy query schema name conflicts with CAS manifest")
        metadata["source_schema_version"] = source_version
        metadata["source_schema_name"] = row.schema_name
        payload.update(
            schema_version=_CAUSAL_QUERY_RESULT_SCHEMA_VERSION,
            result_kind=CausalResultKind.OUTCOME_DISTRIBUTION.value,
            estimator_interval=None,
            metadata=metadata,
        )
    return CausalQueryResult.model_validate(payload)


def _register_causal_query_owner() -> None:
    """Register source-established old rows and the current result representation."""
    for version, mode in (
        (_LEGACY_CAUSAL_QUERY_RESULT_SCHEMA_VERSION, CompatibilityMode.NONE),
        ("1.1", CompatibilityMode.NONE),
        (_CAUSAL_QUERY_RESULT_SCHEMA_VERSION, CompatibilityMode.BACKWARD),
    ):
        register_schema_version(
            "causal_query_result",
            version,
            compatibility=mode,
            notes=("Typed owner rows carry the exact query-result wire contract.",),
        )
    old_rows = tuple(
        IRRepresentationKey("ir.causal_query_result", version, version)
        for version in (_LEGACY_CAUSAL_QUERY_RESULT_SCHEMA_VERSION, "1.1")
    )
    for version in (_LEGACY_CAUSAL_QUERY_RESULT_SCHEMA_VERSION, "1.1"):
        register_ir_representation(
            registry_key="causal_query_result",
            owner_ref=_CAUSAL_QUERY_OWNER.contract_id,
            dto_abi=_CAUSAL_QUERY_OWNER.dto_fqn,
            wire_policy_ref=_CAUSAL_QUERY_LEGACY_POLICY[0],
            wire_policy_revision=_CAUSAL_QUERY_LEGACY_POLICY[1],
            schema_name="ir.causal_query_result",
            schema_version=version,
            payload_version=version,
        )
    register_ir_representation(
        registry_key="causal_query_result",
        owner_ref=_CAUSAL_QUERY_OWNER.contract_id,
        dto_abi=_CAUSAL_QUERY_OWNER.dto_fqn,
        wire_policy_ref=_CAUSAL_QUERY_CURRENT_POLICY[0],
        wire_policy_revision=_CAUSAL_QUERY_CURRENT_POLICY[1],
        schema_name="ir.causal_query_result",
        schema_version=_CAUSAL_QUERY_RESULT_SCHEMA_VERSION,
        payload_version=_CAUSAL_QUERY_RESULT_SCHEMA_VERSION,
        writable=True,
        current=True,
        default_write=True,
        readable_from=old_rows,
    )


_register_causal_query_owner()


def persist_causal_query_result(
    store: ArtifactStore,
    result: CausalQueryResult,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.causal_query_result",
    schema_version: str | None = None,
) -> CausalQueryResultRef:
    """Persist a query result through its exact registered owner row."""
    resolved_schema_version = result.schema_version if schema_version is None else schema_version
    if resolved_schema_version != result.schema_version:
        raise ValueError(
            "causal query result payload and CAS schema versions must match: "
            f"payload={result.schema_version}, requested={resolved_schema_version}"
        )
    payload = result.model_dump(mode="json")
    metadata = dict(payload.get("metadata") or {})
    if metadata.get("source_schema_version") in {"1.0", "1.1"}:
        metadata["historical_schema_replay"] = {
            key: metadata.pop(key)
            for key in ("source_schema_version", "source_schema_name")
            if key in metadata
        }
        payload["metadata"] = metadata
    ref = _put_owned_json_artifact(
        store,
        payload,
        owner=_CAUSAL_QUERY_OWNER,
        schema_name=schema_name,
        schema_version=resolved_schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CausalQueryResultRef.from_selected_write(ref)


def load_causal_query_result(
    store: ArtifactStore,
    ref: CausalQueryResultRef,
) -> CausalQueryResult:
    """Load through exact manifest-to-payload owner admission and query adapter."""
    return _get_owned_json_artifact(store, ref, owner=_CAUSAL_QUERY_OWNER)


__all__ = [
    "CausalAttributionSpec",
    "CausalContrastRegime",
    "CausalContrastSpec",
    "CausalEstimatorInterval",
    "CausalInterventionSpec",
    "CausalQuery",
    "CausalQueryResult",
    "CausalRegime",
    "CausalResultKind",
    "InterventionSpec",
    "InterventionType",
    "QueryType",
    "load_causal_query_result",
    "persist_causal_query_result",
]
