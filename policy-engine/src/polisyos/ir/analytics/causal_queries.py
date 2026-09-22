"""Define persisted causal query requests and their Monte-Carlo result payloads."""

from __future__ import annotations

import math
from collections.abc import Mapping
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import CausalQueryResultRef


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
    def _reject_observational_target(cls, value: Any) -> Any:
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
    def _normalize_legacy_attribution(cls, value: Any) -> Any:
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
        elif isinstance(legacy_intervention, InterventionSpec):
            if (
                legacy_intervention.type is InterventionType.ATOMIC
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

        if self.query_type is QueryType.ATTRIBUTION:
            if self.contrast is None:
                raise ValueError("attribution queries require a target/comparator contrast")
            target_intervention = self.contrast.target
            if self.intervention_spec is not None and self.intervention_spec != target_intervention:
                raise ValueError("intervention_spec conflicts with the explicit attribution target")
            if (
                self.treatment_value is not None
                and (
                    target_intervention.type is not InterventionType.ATOMIC
                    or target_intervention.value is None
                    or not math.isclose(
                        float(self.treatment_value), float(target_intervention.value), rel_tol=0.0
                    )
                )
            ):
                raise ValueError("treatment_value must match the attribution target intervention")
        elif self.contrast is not None:
            raise ValueError("contrast is only valid for attribution queries")

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
        if (
            self.contrast is not None
            and self.contrast.target.value is not None
        ):
            return float(self.contrast.target.value)
        if self.treatment_value is not None:
            return float(self.treatment_value)
        return None


_CAUSAL_QUERY_RESULT_SCHEMA_VERSION = "1.1"
_LEGACY_CAUSAL_QUERY_RESULT_SCHEMA_VERSION = "1.0"


class CausalQueryResult(BaseModel):
    """Result payload returned for a persisted or in-memory causal query."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(_CAUSAL_QUERY_RESULT_SCHEMA_VERSION, pattern=r"^\d+\.\d+$")
    query: CausalQuery
    result_mean: float
    result_std: float = Field(ge=0.0)
    result_ci: tuple[float, float]
    result_distribution: list[float] | None = None
    computation_time_seconds: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_schema(cls, value: Any) -> Any:
        """Normalize legacy payloads without trusting unbound source provenance."""
        if not isinstance(value, Mapping):
            return value
        payload = dict(value)
        if payload.get("schema_version") is None:
            return payload
        source_version = str(payload["schema_version"])
        if source_version == _LEGACY_CAUSAL_QUERY_RESULT_SCHEMA_VERSION:
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
            payload["schema_version"] = _CAUSAL_QUERY_RESULT_SCHEMA_VERSION
        return payload

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
            return self.model_copy(update={"metadata": metadata})
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
                **metadata,
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
    schema_version: str | None = None,
) -> CausalQueryResultRef:
    """Persist a causal query result and return a typed artifact reference."""
    resolved_schema_version = schema_version or result.schema_version
    if resolved_schema_version != result.schema_version:
        raise ValueError(
            "causal query result payload and CAS schema versions must match: "
            f"payload={result.schema_version}, requested={resolved_schema_version}"
        )
    if resolved_schema_version != _CAUSAL_QUERY_RESULT_SCHEMA_VERSION:
        raise ValueError(
            "new causal query results must use schema version "
            f"{_CAUSAL_QUERY_RESULT_SCHEMA_VERSION}"
        )
    ref = put_json_artifact(
        store,
        result.model_dump(mode="json"),
        kind="ir.causal_query_result",
        schema_name=schema_name,
        schema_version=resolved_schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CausalQueryResultRef.model_validate(ref)


def load_causal_query_result(
    store: ArtifactStore,
    ref: CausalQueryResultRef,
) -> CausalQueryResult:
    """Load a causal query result with CAS/payload version reconciliation."""
    payload = get_json_artifact(store, ref.artifact_id)
    manifest = store.get_manifest(ref.artifact_id)
    schema = getattr(manifest, "artifact_schema", None)
    if schema is None:
        raise ValueError(
            "causal query result CAS manifest is missing artifact schema metadata"
        )
    payload_version = payload.get("schema_version") if isinstance(payload, Mapping) else None
    manifest_version = getattr(schema, "version", None)
    if manifest_version is not None and payload_version not in (None, manifest_version):
        raise ValueError(
            "causal query result payload/CAS schema version mismatch: "
            f"payload={payload_version}, manifest={manifest_version}"
        )
    source_version = str(manifest_version or payload_version or _LEGACY_CAUSAL_QUERY_RESULT_SCHEMA_VERSION)
    if source_version not in {
        _LEGACY_CAUSAL_QUERY_RESULT_SCHEMA_VERSION,
        _CAUSAL_QUERY_RESULT_SCHEMA_VERSION,
    }:
        raise ValueError(f"unsupported causal query result schema version: {source_version}")
    if not isinstance(payload, Mapping):
        raise TypeError("causal query result payload must be a mapping")
    normalized_payload = dict(payload)
    normalized_payload["schema_version"] = source_version
    metadata = dict(normalized_payload.get("metadata") or {})
    claimed_source_version = metadata.get("source_schema_version")
    claimed_schema_name = metadata.get("source_schema_name")
    if schema is None and (
        claimed_source_version is not None or claimed_schema_name is not None
    ):
        raise ValueError("causal query result source provenance requires a CAS manifest")
    authoritative_schema_name = str(getattr(schema, "name", "")) if schema is not None else None
    if schema is not None:
        if claimed_source_version is not None and claimed_source_version != source_version:
            raise ValueError(
                "causal query result provenance conflicts with CAS manifest version: "
                f"payload={claimed_source_version}, manifest={source_version}"
            )
        if claimed_schema_name is not None and claimed_schema_name != authoritative_schema_name:
            raise ValueError(
                "causal query result provenance conflicts with CAS manifest name: "
                f"payload={claimed_schema_name}, manifest={authoritative_schema_name}"
            )
        if claimed_source_version is not None:
            metadata["source_schema_version"] = source_version
        if claimed_schema_name is not None:
            metadata["source_schema_name"] = authoritative_schema_name
    if source_version == _LEGACY_CAUSAL_QUERY_RESULT_SCHEMA_VERSION:
        metadata["source_schema_version"] = source_version
        if authoritative_schema_name is not None:
            metadata["source_schema_name"] = authoritative_schema_name
        normalized_payload["schema_version"] = _CAUSAL_QUERY_RESULT_SCHEMA_VERSION
    if metadata:
        normalized_payload["metadata"] = metadata
    return CausalQueryResult.model_validate(normalized_payload)


__all__ = [
    "CausalAttributionSpec",
    "CausalInterventionSpec",
    "CausalContrastRegime",
    "CausalContrastSpec",
    "CausalQuery",
    "CausalQueryResult",
    "CausalRegime",
    "InterventionSpec",
    "InterventionType",
    "QueryType",
    "load_causal_query_result",
    "persist_causal_query_result",
]
