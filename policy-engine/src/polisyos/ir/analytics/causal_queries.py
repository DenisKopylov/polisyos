"""Define persisted causal query requests and their Monte-Carlo result payloads."""

from __future__ import annotations

import math
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import CausalQueryResultRef


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
    def _coerce_optional_float(cls, value: Any) -> Any:
        if value is None:
            return None
        casted = float(value)
        if not math.isfinite(casted):
            raise ValueError("value must be finite")
        return casted

    @field_validator("bounds", mode="before")
    @classmethod
    def _coerce_bounds(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise ValueError("bounds must be a tuple/list of length 2")
        lo = float(value[0])
        hi = float(value[1])
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

        if self.type is InterventionType.STOCHASTIC:
            if not self.distribution or not self.distribution.strip():
                raise ValueError("distribution is required for stochastic interventions")

        return self


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

    @field_validator("treatment_variable", "outcome_variable")
    @classmethod
    def _validate_variable_name(cls, value: str) -> str:
        candidate = str(value).strip()
        if not candidate:
            raise ValueError("variable names must be non-empty")
        return candidate

    @field_validator("treatment_value", mode="before")
    @classmethod
    def _coerce_treatment_value(cls, value: Any) -> Any:
        if value is None:
            return None
        casted = float(value)
        if not math.isfinite(casted):
            raise ValueError("treatment_value must be finite")
        return casted

    @field_validator("condition", mode="before")
    @classmethod
    def _coerce_condition(cls, value: Any) -> Any:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("condition must be a mapping")
        normalized: dict[str, float] = {}
        for key, raw in value.items():
            name = str(key).strip()
            if not name:
                raise ValueError("condition keys must be non-empty")
            item = float(raw)
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

        effective_intervention = self.intervention_spec.type if self.intervention_spec else None
        if effective_intervention is None:
            if self.query_type in {QueryType.INTERVENTIONAL, QueryType.COUNTERFACTUAL}:
                if self.treatment_value is None:
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
        if self.treatment_value is not None:
            return float(self.treatment_value)
        return None


class CausalQueryResult(BaseModel):
    """Result payload returned for a persisted or in-memory causal query."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    query: CausalQuery
    result_mean: float
    result_std: float = Field(ge=0.0)
    result_ci: tuple[float, float]
    result_distribution: list[float] | None = None
    computation_time_seconds: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("result_mean", "result_std", "computation_time_seconds", mode="before")
    @classmethod
    def _coerce_scalar(cls, value: Any) -> Any:
        casted = float(value)
        if not math.isfinite(casted):
            raise ValueError("numeric values must be finite")
        return casted

    @field_validator("result_ci", mode="before")
    @classmethod
    def _coerce_ci(cls, value: Any) -> Any:
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise ValueError("result_ci must be a tuple/list of length 2")
        lo = float(value[0])
        hi = float(value[1])
        if not math.isfinite(lo) or not math.isfinite(hi):
            raise ValueError("result_ci bounds must be finite")
        return (lo, hi)

    @field_validator("result_distribution", mode="before")
    @classmethod
    def _coerce_distribution(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, list):
            raise ValueError("result_distribution must be a list of floats")
        normalized: list[float] = []
        for item in value:
            casted = float(item)
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
        return self

    def to_uncertainty_envelope(self) -> UncertaintyEnvelope:
        return UncertaintyEnvelope(
            point_estimate=float(self.result_mean),
            confidence_interval=(
                float(self.result_ci[0]),
                float(self.result_ci[1]),
            ),
            confidence_level=0.95,
            distribution_family=DistributionFamily.BOOTSTRAP,
            source=UncertaintySource.CAUSAL,
            propagation_method=PropagationMethod.MONTE_CARLO,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            sample_size=int(self.query.n_samples),
            is_heuristic_ci=False,
            gate_eligible=True,
            metadata={
                "query_type": self.query.query_type.value,
                "treatment_variable": self.query.treatment_variable,
                "outcome_variable": self.query.outcome_variable,
                **dict(self.metadata),
            },
        )


class CausalInterventionSpec(InterventionSpec):
    """Expose the causal-query intervention payload under the legacy public name.

    The semantics are identical to :class:`InterventionSpec`; this alias exists
    so older callers can migrate without changing payload structure.
    """


def persist_causal_query_result(
    store: ArtifactStore,
    result: CausalQueryResult,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.causal_query_result",
    schema_version: str = "1.0",
) -> CausalQueryResultRef:
    """Persist a causal query result and return a typed artifact reference."""
    ref = put_json_artifact(
        store,
        result.model_dump(mode="json"),
        kind="ir.causal_query_result",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CausalQueryResultRef.model_validate(ref)


def load_causal_query_result(
    store: ArtifactStore,
    ref: CausalQueryResultRef,
) -> CausalQueryResult:
    """Load causal query result."""
    payload = get_json_artifact(store, ref.artifact_id)
    return CausalQueryResult.model_validate(payload)


__all__ = [
    "CausalInterventionSpec",
    "CausalQuery",
    "CausalQueryResult",
    "InterventionSpec",
    "InterventionType",
    "QueryType",
    "load_causal_query_result",
    "persist_causal_query_result",
]
