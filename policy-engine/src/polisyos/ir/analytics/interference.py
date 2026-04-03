"""IR models for interference and network causal inference.

Covers partial interference (Hudgens & Halloran 2008), general network AIPW
(Aronow & Samii 2017), spatial spillovers, and bipartite interference
(Zigler & Papadogeorgou 2021).
"""
from __future__ import annotations

import math
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import (
    ArtifactRefModel,
    InteractionComplexRef,
    InterferenceCertificateRef,
)

_INTERACTION_COMPLEX_SCHEMA_NAME = "ir.interaction_complex"
_INTERACTION_COMPLEX_SCHEMA_VERSION = "1.0"
_INTERFERENCE_CERTIFICATE_SCHEMA_NAME = "ir.interference_certificate"
_INTERFERENCE_CERTIFICATE_SCHEMA_VERSION = "1.0"


def _ensure_non_empty_string(value: Any, *, field_name: str) -> str:
    candidate = str(value).strip()
    if not candidate:
        raise ValueError(f"{field_name} must be non-empty")
    return candidate


def _validate_artifact_ref(ref: ArtifactRefModel, *, field_name: str) -> ArtifactRefModel:
    if not str(ref.kind).strip():
        raise ValueError(f"{field_name}.kind must be non-empty")
    if not str(ref.media_type).strip():
        raise ValueError(f"{field_name}.media_type must be non-empty")
    return ref


def _coerce_string_tuple(value: Any, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a list/tuple of non-empty strings")
    return tuple(_ensure_non_empty_string(item, field_name=field_name) for item in value)


def _coerce_nested_string_tuples(value: Any, *, field_name: str) -> tuple[tuple[str, ...], ...]:
    if value in (None, ()):
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a list/tuple of node groups")
    groups: list[tuple[str, ...]] = []
    for index, group in enumerate(value):
        groups.append(
            _coerce_string_tuple(group, field_name=f"{field_name}[{index}]")
        )
    return tuple(groups)


class InteractionComplex(BaseModel):
    """Topology contract reserved for future hypergraph interference reasoning."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    nodes: tuple[str, ...]
    hyperedges: tuple[tuple[str, ...], ...] = ()
    simplices: tuple[tuple[str, ...], ...] = ()
    exposure_operator_ref: ArtifactRefModel
    reduction_policy: Literal["pairwise_projection", "cluster_projection", "full_complex"]

    @field_validator("nodes", mode="before")
    @classmethod
    def _validate_nodes(cls, value: Any) -> tuple[str, ...]:
        nodes = _coerce_string_tuple(value, field_name="nodes")
        if not nodes:
            raise ValueError("nodes must be non-empty")
        if len(set(nodes)) != len(nodes):
            raise ValueError("nodes must be unique")
        return nodes

    @field_validator("hyperedges", "simplices", mode="before")
    @classmethod
    def _validate_node_groups(cls, value: Any, info: Any) -> tuple[tuple[str, ...], ...]:
        groups = _coerce_nested_string_tuples(value, field_name=str(info.field_name))
        normalized: list[tuple[str, ...]] = []
        seen: set[tuple[str, ...]] = set()
        for index, group in enumerate(groups):
            if len(set(group)) != len(group):
                raise ValueError(f"{info.field_name}[{index}] must not contain duplicate nodes")
            canonical = tuple(group)
            if canonical in seen:
                raise ValueError(f"{info.field_name} must not contain duplicate groups")
            seen.add(canonical)
            normalized.append(canonical)
        return tuple(normalized)

    @model_validator(mode="after")
    def _validate_contract(self) -> "InteractionComplex":
        _validate_artifact_ref(self.exposure_operator_ref, field_name="exposure_operator_ref")
        declared_nodes = set(self.nodes)
        for field_name in ("hyperedges", "simplices"):
            for index, group in enumerate(getattr(self, field_name)):
                missing = [node for node in group if node not in declared_nodes]
                if missing:
                    raise ValueError(
                        f"{field_name}[{index}] references undeclared nodes: {missing}"
                    )
        return self


class InterferenceCertificate(BaseModel):
    """Disclosure contract for topology-to-pairwise/cluster reduction behavior."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    supported_query_family: str = Field(min_length=1)
    exposure_assumptions: tuple[str, ...] = ()
    reduction_error_bound: float | None = Field(default=None, ge=0.0)
    fallback_mode: Literal["pairwise", "clustered", "unsupported"]

    @field_validator("supported_query_family", mode="before")
    @classmethod
    def _validate_supported_query_family(cls, value: Any) -> str:
        return _ensure_non_empty_string(value, field_name="supported_query_family")

    @field_validator("exposure_assumptions", mode="before")
    @classmethod
    def _validate_exposure_assumptions(cls, value: Any) -> tuple[str, ...]:
        assumptions = _coerce_string_tuple(
            () if value is None else value,
            field_name="exposure_assumptions",
        )
        deduped: list[str] = []
        seen: set[str] = set()
        for assumption in assumptions:
            if assumption in seen:
                continue
            seen.add(assumption)
            deduped.append(assumption)
        return tuple(deduped)

    @field_validator("reduction_error_bound", mode="before")
    @classmethod
    def _validate_reduction_error_bound(cls, value: Any) -> float | None:
        if value is None:
            return None
        casted = float(value)
        if not math.isfinite(casted):
            raise ValueError("reduction_error_bound must be finite when provided")
        return casted


def persist_interaction_complex(
    store: ArtifactStore,
    contract: InteractionComplex,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _INTERACTION_COMPLEX_SCHEMA_NAME,
    schema_version: str = _INTERACTION_COMPLEX_SCHEMA_VERSION,
) -> InteractionComplexRef:
    """Persist interaction complex helper."""
    ref = put_json_artifact(
        store,
        contract.model_dump(mode="json"),
        kind="ir.interaction_complex",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return InteractionComplexRef.model_validate(ref)


def load_interaction_complex(
    store: ArtifactStore,
    ref: InteractionComplexRef,
) -> InteractionComplex:
    """Load interaction complex."""
    payload = get_json_artifact(store, ref.artifact_id)
    return InteractionComplex.model_validate(payload)


def persist_interference_certificate(
    store: ArtifactStore,
    certificate: InterferenceCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _INTERFERENCE_CERTIFICATE_SCHEMA_NAME,
    schema_version: str = _INTERFERENCE_CERTIFICATE_SCHEMA_VERSION,
) -> InterferenceCertificateRef:
    """Persist interference certificate helper."""
    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.interference_certificate",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return InterferenceCertificateRef.model_validate(ref)


def load_interference_certificate(
    store: ArtifactStore,
    ref: InterferenceCertificateRef,
) -> InterferenceCertificate:
    """Load interference certificate."""
    payload = get_json_artifact(store, ref.artifact_id)
    return InterferenceCertificate.model_validate(payload)


class InterferenceMethod(str, Enum):
    """Identifies the interference estimator used."""

    PARTIAL_IPW = "partial_interference_ipw"
    """Clustered partial interference with IPW (Hudgens & Halloran 2008)."""
    NETWORK_AIPW = "network_aipw"
    """General network AIPW via exposure mapping (Aronow & Samii 2017)."""
    SPATIAL_KERNEL = "spatial_kernel"
    """Kernel-weighted geographic spillover estimator."""
    BIPARTITE = "bipartite_interference"
    """Bipartite treatment→outcome graph (Zigler & Papadogeorgou 2021)."""


class ExposureMappingType(str, Enum):
    """How neighborhood treatment is mapped to a unit's exposure level."""

    FRACTIONAL = "fractional"
    """Fraction of cluster/network neighbors who are treated."""
    THRESHOLD = "threshold"
    """Binary: 1 if fractional exposure exceeds a threshold."""
    COUNT = "count"
    """Raw count of treated neighbors."""
    KERNEL = "kernel"
    """Gaussian kernel-weighted sum of neighbor treatments (spatial)."""
    BIPARTITE = "bipartite"
    """Aggregate upstream treatment via bipartite graph."""


class InterferenceEffectDecomposition(BaseModel):
    """Full decomposition of treatment effects under interference.

    Following Hudgens & Halloran (2008) and Tchetgen Tchetgen &
    VanderWeele (2012):

    - direct_effect:   DE(α) = E[Y(1,α)] − E[Y(0,α)]
    - spillover_effect: SE(α₁,α₂) = E[Y(0,α₁)] − E[Y(0,α₂)]
    - total_effect:    TE ≈ DE(α₁) + SE(α₁,α₂)
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")

    # ── Core effect estimates ────────────────────────────────────────────────
    direct_effect: float
    """DE(α) = E[Y(1,α)] − E[Y(0,α)]: effect of own treatment, holding
    neighbours' allocation α fixed."""
    spillover_effect: float
    """SE(α₁,α₂) = E[Y(0,α₁)] − E[Y(0,α₂)]: effect of changing neighbour
    allocation from α₂ to α₁, own treatment held at 0."""
    total_effect: float
    """TE = E[Y(1,α₁)] − E[Y(0,α₂)]: combined direct + spillover contrast."""
    indirect_effect: float | None = None
    """Alias for spillover_effect in some parameterisations."""

    # ── Reference allocation arms ────────────────────────────────────────────
    alpha_high: float = Field(default=0.5, ge=0.0, le=1.0)
    """High-coverage allocation arm α₁ (fraction of neighbours treated)."""
    alpha_low: float = Field(default=0.0, ge=0.0, le=1.0)
    """Low-coverage allocation arm α₂."""

    # ── Standard errors ──────────────────────────────────────────────────────
    se_direct: float | None = Field(default=None, ge=0.0)
    se_spillover: float | None = Field(default=None, ge=0.0)
    se_total: float | None = Field(default=None, ge=0.0)

    # ── Confidence intervals ─────────────────────────────────────────────────
    ci_direct: tuple[float, float] | None = None
    ci_spillover: tuple[float, float] | None = None
    ci_total: tuple[float, float] | None = None

    # ── Sample info ──────────────────────────────────────────────────────────
    n_units: int = Field(ge=2)
    n_treated: int = Field(ge=0)
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    interference_detected: bool = False
    """True when the spillover effect is statistically significant at 5%."""

    @model_validator(mode="after")
    def _check_consistency(self) -> "InterferenceEffectDecomposition":
        if self.n_treated > self.n_units:
            raise ValueError("n_treated must not exceed n_units")
        if not math.isfinite(self.direct_effect):
            raise ValueError("direct_effect must be finite")
        if not math.isfinite(self.spillover_effect):
            raise ValueError("spillover_effect must be finite")
        if not math.isfinite(self.total_effect):
            raise ValueError("total_effect must be finite")
        if self.ci_direct is not None:
            lo, hi = self.ci_direct
            if lo > hi:
                raise ValueError("ci_direct lower bound must not exceed upper")
        if self.ci_spillover is not None:
            lo, hi = self.ci_spillover
            if lo > hi:
                raise ValueError("ci_spillover lower bound must not exceed upper")
        return self


class NetworkInterferenceReport(BaseModel):
    """Top-level result returned by all interference estimation methods.

    Carries the effect decomposition together with diagnostics, exposure
    mapping metadata, and sample statistics.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")

    method: InterferenceMethod
    status: Literal["success", "input_invalid", "assumption_failed", "numerical_failure"]
    status_reason: str | None = None

    effects: InterferenceEffectDecomposition | None = None

    # ── Exposure mapping metadata ─────────────────────────────────────────────
    exposure_mapping: ExposureMappingType
    exposure_mapping_params: dict[str, Any] = Field(default_factory=dict)

    # ── Sample statistics ────────────────────────────────────────────────────
    n_units: int = Field(ge=2)
    n_treated: int = Field(ge=0)
    n_clusters: int | None = Field(default=None, ge=1)
    average_cluster_size: float | None = Field(default=None, gt=0.0)

    # ── Diagnostics ──────────────────────────────────────────────────────────
    warnings: list[str] = Field(default_factory=list)
    assumptions: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_effects_on_success(self) -> "NetworkInterferenceReport":
        if self.status == "success" and self.effects is None:
            raise ValueError("effects must be set when status is 'success'")
        return self

    # ── Convenience properties ───────────────────────────────────────────────
    @property
    def direct_effect(self) -> float | None:
        return self.effects.direct_effect if self.effects else None

    @property
    def spillover_effect(self) -> float | None:
        return self.effects.spillover_effect if self.effects else None

    @property
    def total_effect(self) -> float | None:
        return self.effects.total_effect if self.effects else None

    @property
    def is_success(self) -> bool:
        return self.status == "success"


__all__ = [
    "ExposureMappingType",
    "InteractionComplex",
    "InterferenceEffectDecomposition",
    "InterferenceCertificate",
    "InterferenceMethod",
    "NetworkInterferenceReport",
    "load_interaction_complex",
    "load_interference_certificate",
    "persist_interaction_complex",
    "persist_interference_certificate",
]
