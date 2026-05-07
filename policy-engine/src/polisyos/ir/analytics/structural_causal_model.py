"""Describe serializable SCM graph-plus-mechanism contracts and persistence helpers."""

from __future__ import annotations

import json
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.references import StructuralCausalModelSpecRef

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal_graph import CausalGraphModel
else:
    from polisyos.ir.analytics.causal_graph import CausalGraphModel


def _normalize_json_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _normalize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_json_value(item) for item in value]
    return value


def _ensure_json_serializable(field_name: str, value: Any) -> Any:
    normalized = _normalize_json_value(value)
    try:
        json.dumps(normalized, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be JSON-serializable: {exc}") from exc
    return normalized


class MechanismFamily(str, Enum):
    """Allowed mechanism families for SCM node equations."""

    LINEAR = "linear"
    ADDITIVE_NOISE = "additive_noise"
    POST_NONLINEAR = "post_nonlinear"
    CLASSIFIER = "classifier"
    EMPIRICAL = "empirical"
    PARAMETRIC_PRIOR = "parametric_prior"


class MechanismSource(str, Enum):
    """Where a node mechanism was sourced from."""

    DATA_FITTED = "data_fitted"
    LITERATURE_PRIOR = "literature_prior"
    HYBRID = "hybrid"
    DEFAULT = "default"


class NodeMechanism(BaseModel):
    """Structural equation metadata for one variable in an SCM."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    variable: str
    parents: list[str] = Field(default_factory=list)
    family: MechanismFamily
    family_params: dict[str, Any] = Field(default_factory=dict)
    noise_distribution: str = "empirical"
    source: MechanismSource = MechanismSource.DATA_FITTED
    literature_prior: dict[str, Any] | None = None
    sensitivity_to_latent: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        payload["family_params"] = _ensure_json_serializable(
            "family_params",
            payload.get("family_params", {}),
        )
        prior = payload.get("literature_prior")
        if prior is not None:
            payload["literature_prior"] = _ensure_json_serializable("literature_prior", prior)
        return payload

    @model_validator(mode="after")
    def _validate_json_only(self) -> NodeMechanism:
        _ensure_json_serializable("family_params", self.family_params)
        if self.literature_prior is not None:
            _ensure_json_serializable("literature_prior", self.literature_prior)
        return self


class StructuralCausalModelSpec(BaseModel):
    """Serializable structural causal model with graph and node mechanisms."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    graph: CausalGraphModel
    mechanisms: list[NodeMechanism] = Field(default_factory=list)
    fitted: bool = False
    fit_method: Literal["auto", "manual", "gcm", "hybrid"] | None = None
    fit_metrics: dict[str, float] = Field(default_factory=dict)
    mechanism_source_summary: dict[str, int] = Field(default_factory=dict)
    skg_snapshot_ref: str | None = None

    @model_validator(mode="after")
    def _validate_mechanisms_cover_graph(self) -> StructuralCausalModelSpec:
        mech_vars = {m.variable for m in self.mechanisms}
        graph_vars = set(self.graph.nodes)

        unknown_mechanisms = sorted(mech_vars - graph_vars)
        if unknown_mechanisms:
            raise ValueError(f"Mechanisms reference unknown variables: {unknown_mechanisms}")

        missing = graph_vars - mech_vars
        non_roots = {edge.dst for edge in self.graph.edges}
        missing_non_roots = sorted(missing & non_roots)
        if missing_non_roots:
            raise ValueError(f"Non-root nodes without mechanisms: {missing_non_roots}")
        return self


def persist_structural_causal_model_spec(
    store: ArtifactStore,
    scm_spec: StructuralCausalModelSpec,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.structural_causal_model_spec",
    schema_version: str = "1.0",
) -> StructuralCausalModelSpecRef:
    """Persist a structural causal model spec and return its typed artifact ref."""
    ref = put_json_artifact(
        store,
        scm_spec.model_dump(mode="json"),
        kind="ir.structural_causal_model_spec",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return StructuralCausalModelSpecRef.model_validate(ref)


def load_structural_causal_model_spec(
    store: ArtifactStore,
    ref: StructuralCausalModelSpecRef,
) -> StructuralCausalModelSpec:
    """Load structural causal model spec."""
    payload = get_json_artifact(store, ref.artifact_id)
    return StructuralCausalModelSpec.model_validate(payload)


__all__ = [
    "MechanismFamily",
    "MechanismSource",
    "NodeMechanism",
    "StructuralCausalModelSpec",
    "load_structural_causal_model_spec",
    "persist_structural_causal_model_spec",
]
