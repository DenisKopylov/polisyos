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
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import (
    ArtifactRefModel,
    InteractionComplexRef,
    InterferenceCertificateRef,
    MAUPInvarianceCertificateRef,
    SpatialHodgeDiagnosticsRef,
)

_INTERACTION_COMPLEX_SCHEMA_NAME = "ir.interaction_complex"
_INTERACTION_COMPLEX_SCHEMA_VERSION = "1.0"
_INTERFERENCE_CERTIFICATE_SCHEMA_NAME = "ir.interference_certificate"
_INTERFERENCE_CERTIFICATE_SCHEMA_VERSION = "1.0"
_MAUP_INVARIANCE_CERTIFICATE_SCHEMA_NAME = "ir.maup_invariance_certificate"
_MAUP_INVARIANCE_CERTIFICATE_SCHEMA_VERSION = "1.0"
_SPATIAL_HODGE_DIAGNOSTICS_SCHEMA_NAME = "ir.spatial_hodge_diagnostics"
_SPATIAL_HODGE_DIAGNOSTICS_SCHEMA_VERSION = "1.0"


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
        groups.append(_coerce_string_tuple(group, field_name=f"{field_name}[{index}]"))
    return tuple(groups)


def _coerce_estimability_checks(
    value: Any,
    *,
    field_name: str,
) -> dict[str, Literal["pass", "fail", "not_applicable"]]:
    if value in (None, {}):
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dict of gate -> status")
    normalized: dict[str, Literal["pass", "fail", "not_applicable"]] = {}
    for raw_key, raw_status in value.items():
        key = _ensure_non_empty_string(raw_key, field_name=f"{field_name}.key")
        status = _ensure_non_empty_string(raw_status, field_name=f"{field_name}[{key}]")
        if status not in {"pass", "fail", "not_applicable"}:
            raise ValueError(f"{field_name}[{key}] must be one of pass, fail, not_applicable")
        normalized[key] = status  # type: ignore[assignment]
    return normalized


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
    def _validate_contract(self) -> InteractionComplex:
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
    """Disclosure contract for topology-to-pairwise/cluster reduction behavior.

    ``fallback_mode`` is retained as the legacy degraded-mode signal consumed by
    older code paths. Stage 10.2 adds ``mode_requested``/``mode_used`` and the
    estimability metadata below as the source of truth for honest reduction.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    supported_query_family: str = Field(min_length=1)
    exposure_assumptions: tuple[str, ...] = ()
    reduction_error_bound: float | None = Field(default=None, ge=0.0)
    fallback_mode: Literal["pairwise", "clustered", "unsupported"]
    mode_requested: Literal["pairwise", "clustered", "complex"] | None = None
    mode_used: Literal["pairwise", "clustered", "complex", "unsupported"] | None = None
    fallback_triggered: bool = False
    fallback_reason_codes: tuple[str, ...] = ()
    estimability_checks: dict[str, Literal["pass", "fail", "not_applicable"]] = Field(
        default_factory=dict
    )

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

    @field_validator("fallback_reason_codes", mode="before")
    @classmethod
    def _validate_fallback_reason_codes(cls, value: Any) -> tuple[str, ...]:
        reasons = _coerce_string_tuple(
            () if value is None else value,
            field_name="fallback_reason_codes",
        )
        deduped: list[str] = []
        seen: set[str] = set()
        for reason in reasons:
            if reason in seen:
                continue
            seen.add(reason)
            deduped.append(reason)
        return tuple(deduped)

    @field_validator("estimability_checks", mode="before")
    @classmethod
    def _validate_estimability_checks(
        cls,
        value: Any,
    ) -> dict[str, Literal["pass", "fail", "not_applicable"]]:
        return _coerce_estimability_checks(value, field_name="estimability_checks")

    @field_validator("reduction_error_bound", mode="before")
    @classmethod
    def _validate_reduction_error_bound(cls, value: Any) -> float | None:
        if value is None:
            return None
        casted = float(value)
        if not math.isfinite(casted):
            raise ValueError("reduction_error_bound must be finite when provided")
        return casted

    @model_validator(mode="after")
    def _validate_fallback_certificate(self) -> InterferenceCertificate:
        if self.fallback_triggered and not self.fallback_reason_codes:
            raise ValueError(
                "fallback_reason_codes must be non-empty when fallback_triggered is true"
            )
        if not self.fallback_triggered and self.fallback_reason_codes:
            raise ValueError("fallback_reason_codes must be empty when fallback_triggered is false")
        if (
            self.mode_requested is not None
            and self.mode_used is not None
            and not self.fallback_triggered
            and self.mode_requested != self.mode_used
        ):
            raise ValueError("mode_requested must equal mode_used when fallback_triggered is false")
        if (
            self.mode_requested is not None
            and self.mode_used is not None
            and self.fallback_triggered
            and self.mode_requested == self.mode_used
        ):
            raise ValueError(
                "mode_requested must differ from mode_used when fallback_triggered is true"
            )
        if self.mode_used == "unsupported" and self.fallback_mode != "unsupported":
            raise ValueError("fallback_mode must be unsupported when mode_used is unsupported")
        if self.mode_used in {"pairwise", "clustered"} and self.fallback_mode != self.mode_used:
            raise ValueError("fallback_mode must match mode_used for pairwise/clustered execution")
        if self.mode_used == "complex" and self.fallback_mode != "unsupported":
            raise ValueError("fallback_mode must be unsupported when mode_used is complex")
        if self.mode_used == "complex" and any(
            status == "fail" for status in self.estimability_checks.values()
        ):
            raise ValueError(
                "complex mode cannot be used when any estimability check is marked fail"
            )
        return self


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


def persist_maup_invariance_certificate(
    store: ArtifactStore,
    certificate: MAUPInvarianceCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _MAUP_INVARIANCE_CERTIFICATE_SCHEMA_NAME,
    schema_version: str = _MAUP_INVARIANCE_CERTIFICATE_SCHEMA_VERSION,
) -> MAUPInvarianceCertificateRef:
    """Persist a MAUP invariance certificate helper."""
    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.maup_invariance_certificate",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return MAUPInvarianceCertificateRef.model_validate(ref)


def load_maup_invariance_certificate(
    store: ArtifactStore,
    ref: MAUPInvarianceCertificateRef,
) -> MAUPInvarianceCertificate:
    """Load a persisted MAUP invariance certificate."""
    payload = get_json_artifact(store, ref.artifact_id)
    return MAUPInvarianceCertificate.model_validate(payload)


def persist_spatial_hodge_diagnostics(
    store: ArtifactStore,
    diagnostics: SpatialHodgeDiagnostics,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _SPATIAL_HODGE_DIAGNOSTICS_SCHEMA_NAME,
    schema_version: str = _SPATIAL_HODGE_DIAGNOSTICS_SCHEMA_VERSION,
) -> SpatialHodgeDiagnosticsRef:
    """Persist multiscale spatial Hodge diagnostics."""
    ref = put_json_artifact(
        store,
        diagnostics.model_dump(mode="json"),
        kind="ir.spatial_hodge_diagnostics",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return SpatialHodgeDiagnosticsRef.model_validate(ref)


def load_spatial_hodge_diagnostics(
    store: ArtifactStore,
    ref: SpatialHodgeDiagnosticsRef,
) -> SpatialHodgeDiagnostics:
    """Load persisted multiscale spatial Hodge diagnostics."""
    payload = get_json_artifact(store, ref.artifact_id)
    return SpatialHodgeDiagnostics.model_validate(payload)


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
    def _check_consistency(self) -> InterferenceEffectDecomposition:
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
    def _check_effects_on_success(self) -> NetworkInterferenceReport:
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


class MAUPPartitionCheck(BaseModel):
    """Per-partition evidence for aggregation-invariance checks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    partition_id: str = Field(min_length=1)
    n_blocks: int = Field(ge=0)
    scale_label: str | None = None
    zoning_label: str | None = None
    lumpability_residual: float | None = Field(default=None, ge=0.0)
    exact_lumpable: bool | None = None
    theta_partition: float | None = None
    se_partition: float | None = Field(default=None, ge=0.0)
    hausman_stat: float | None = Field(default=None, ge=0.0)
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    adjusted_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    ess_min: float | None = Field(default=None, ge=0.0)
    blocker_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @field_validator("partition_id", mode="before")
    @classmethod
    def _validate_partition_id(cls, value: Any) -> str:
        return _ensure_non_empty_string(value, field_name="partition_id")

    @field_validator("scale_label", "zoning_label", mode="before")
    @classmethod
    def _validate_optional_labels(cls, value: Any, info: Any) -> str | None:
        if value is None:
            return None
        return _ensure_non_empty_string(value, field_name=str(info.field_name))

    @field_validator("blocker_codes", "warnings", mode="before")
    @classmethod
    def _validate_string_tuples(cls, value: Any, info: Any) -> tuple[str, ...]:
        return _coerce_string_tuple(
            () if value in (None, ()) else value,
            field_name=str(info.field_name),
        )


class MAUPInvarianceCertificate(BaseModel):
    """Certificate describing whether spatial effects survive zoning changes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    status: Literal["pass", "warn", "block", "not_tested", "not_identified"]
    estimand: Literal["direct", "spillover", "total", "dose_response", "policy_effect"]
    effect_scale: Literal["risk_difference", "mean_difference", "log_rr", "custom"]
    micro_effect: float | None = None
    micro_se: float | None = Field(default=None, ge=0.0)
    partitions_tested: int = Field(ge=0)
    max_lumpability_residual: float | None = Field(default=None, ge=0.0)
    min_adjusted_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    min_positivity: float | None = Field(default=None, ge=0.0, le=1.0)
    min_ess: float | None = Field(default=None, ge=0.0)
    exact_invariance: bool = False
    near_invariance: bool = False
    recommended_mode: Literal[
        "micro_only",
        "micro_plus_safe_aggregate",
        "block_aggregate",
    ]
    partition_checks: tuple[MAUPPartitionCheck, ...] = ()
    blocker_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    interaction_complex_ref: ArtifactRefModel | None = None
    interference_certificate_ref: ArtifactRefModel | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("partition_checks", mode="before")
    @classmethod
    def _validate_partition_checks(
        cls,
        value: Any,
    ) -> tuple[MAUPPartitionCheck, ...]:
        if value in (None, ()):
            return ()
        if not isinstance(value, (list, tuple)):
            raise ValueError("partition_checks must be a list/tuple of partition checks")
        return tuple(
            item
            if isinstance(item, MAUPPartitionCheck)
            else MAUPPartitionCheck.model_validate(item)
            for item in value
        )

    @field_validator("blocker_codes", "warnings", mode="before")
    @classmethod
    def _validate_string_tuples(cls, value: Any, info: Any) -> tuple[str, ...]:
        return _coerce_string_tuple(
            () if value in (None, ()) else value,
            field_name=str(info.field_name),
        )

    @field_validator("interaction_complex_ref", "interference_certificate_ref", mode="before")
    @classmethod
    def _validate_optional_refs(
        cls,
        value: Any,
        info: Any,
    ) -> ArtifactRefModel | None:
        if value is None:
            return None
        ref = (
            value if isinstance(value, ArtifactRefModel) else ArtifactRefModel.model_validate(value)
        )
        return _validate_artifact_ref(ref, field_name=str(info.field_name))

    @model_validator(mode="after")
    def _validate_certificate(self) -> MAUPInvarianceCertificate:
        if self.partitions_tested != len(self.partition_checks):
            raise ValueError("partitions_tested must equal len(partition_checks)")
        if self.status in {"pass", "warn"} and self.partitions_tested == 0:
            raise ValueError("pass/warn certificates require at least one partition check")
        if self.exact_invariance and not self.near_invariance:
            raise ValueError("exact_invariance implies near_invariance")
        return self


class SpatialHodgeScaleProfile(BaseModel):
    """Per-scale graph-Hodge energy profile for areal spillover diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scale_id: str = Field(min_length=1)
    zoning_id: str = Field(min_length=1)
    aggregation_rule: str = Field(min_length=1)
    weight_spec: str = Field(min_length=1)
    zoning_hash: str = Field(min_length=1)
    weight_hash: str = Field(min_length=1)
    aggregation_hash: str = Field(min_length=1)
    n_zones: int = Field(ge=1)
    n_edges: int = Field(ge=0)
    n_triangles: int = Field(default=0, ge=0)
    total_energy: float = Field(ge=0.0)
    gradient_energy: float = Field(ge=0.0)
    curl_energy: float = Field(ge=0.0)
    harmonic_energy: float = Field(ge=0.0)
    eta_grad: float = Field(ge=0.0, le=1.0)
    eta_curl: float = Field(ge=0.0, le=1.0)
    eta_harm: float = Field(ge=0.0, le=1.0)
    dominant_component: Literal["grad", "curl", "harm", "mixed"] = "mixed"
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "scale_id",
        "zoning_id",
        "aggregation_rule",
        "weight_spec",
        "zoning_hash",
        "weight_hash",
        "aggregation_hash",
        mode="before",
    )
    @classmethod
    def _validate_required_strings(cls, value: Any, info: Any) -> str:
        return _ensure_non_empty_string(value, field_name=str(info.field_name))

    @field_validator("warnings", mode="before")
    @classmethod
    def _validate_warnings(cls, value: Any) -> tuple[str, ...]:
        return _coerce_string_tuple(() if value in (None, ()) else value, field_name="warnings")

    @model_validator(mode="after")
    def _validate_energy_profile(self) -> SpatialHodgeScaleProfile:
        total_components = self.gradient_energy + self.curl_energy + self.harmonic_energy
        if self.total_energy + 1.0e-9 < total_components:
            raise ValueError("total_energy must dominate component energies")
        total_eta = self.eta_grad + self.eta_curl + self.eta_harm
        if total_eta > 1.0 + 1.0e-6:
            raise ValueError("eta_grad + eta_curl + eta_harm must not exceed 1")
        return self


class SpatialHodgeDiagnostics(BaseModel):
    """Declared-scale multiscale Hodge diagnostics for spatial interference."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    declared_scale_id: str = Field(min_length=1)
    declared_zoning_id: str = Field(min_length=1)
    aggregation_rule: str = Field(min_length=1)
    weight_spec: str = Field(min_length=1)
    exposure_mapping: str = Field(min_length=1)
    zoning_hash: str = Field(min_length=1)
    weight_hash: str = Field(min_length=1)
    aggregation_hash: str = Field(min_length=1)
    eta_grad: float = Field(ge=0.0, le=1.0)
    eta_curl: float = Field(ge=0.0, le=1.0)
    eta_harm: float = Field(ge=0.0, le=1.0)
    dominant_component: Literal["grad", "curl", "harm", "mixed"] = "mixed"
    max_profile_l1_gap: float = Field(default=0.0, ge=0.0)
    scale_instability: float = Field(default=0.0, ge=0.0)
    zoning_instability: float = Field(default=0.0, ge=0.0)
    topology_sensitivity: float | None = Field(default=None, ge=0.0)
    candidate_partition_ids: tuple[str, ...] = ()
    profiles: tuple[SpatialHodgeScaleProfile, ...] = ()
    blocker_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "declared_scale_id",
        "declared_zoning_id",
        "aggregation_rule",
        "weight_spec",
        "exposure_mapping",
        "zoning_hash",
        "weight_hash",
        "aggregation_hash",
        mode="before",
    )
    @classmethod
    def _validate_required_strings(cls, value: Any, info: Any) -> str:
        return _ensure_non_empty_string(value, field_name=str(info.field_name))

    @field_validator("candidate_partition_ids", "blocker_codes", "warnings", mode="before")
    @classmethod
    def _validate_string_tuples(cls, value: Any, info: Any) -> tuple[str, ...]:
        return _coerce_string_tuple(
            () if value in (None, ()) else value,
            field_name=str(info.field_name),
        )

    @field_validator("profiles", mode="before")
    @classmethod
    def _validate_profiles(cls, value: Any) -> tuple[SpatialHodgeScaleProfile, ...]:
        if value in (None, ()):
            return ()
        if not isinstance(value, (list, tuple)):
            raise ValueError("profiles must be a list/tuple of SpatialHodgeScaleProfile")
        return tuple(
            item
            if isinstance(item, SpatialHodgeScaleProfile)
            else SpatialHodgeScaleProfile.model_validate(item)
            for item in value
        )

    @model_validator(mode="after")
    def _validate_diagnostics(self) -> SpatialHodgeDiagnostics:
        total_eta = self.eta_grad + self.eta_curl + self.eta_harm
        if total_eta > 1.0 + 1.0e-6:
            raise ValueError("eta_grad + eta_curl + eta_harm must not exceed 1")
        if self.profiles:
            declared_profile = self.profiles[0]
            if declared_profile.scale_id != self.declared_scale_id:
                raise ValueError("profiles[0].scale_id must match declared_scale_id")
            if declared_profile.zoning_id != self.declared_zoning_id:
                raise ValueError("profiles[0].zoning_id must match declared_zoning_id")
        return self


class SpatialResult(NetworkInterferenceReport):
    """Spatial interference report with optional MAUP certificate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    maup_invariance_certificate: MAUPInvarianceCertificate | None = None
    spatial_hodge_diagnostics: SpatialHodgeDiagnostics | None = None


__all__ = [
    "ExposureMappingType",
    "InteractionComplex",
    "InterferenceCertificate",
    "InterferenceEffectDecomposition",
    "InterferenceMethod",
    "MAUPInvarianceCertificate",
    "MAUPPartitionCheck",
    "NetworkInterferenceReport",
    "SpatialHodgeDiagnostics",
    "SpatialHodgeScaleProfile",
    "SpatialResult",
    "load_interaction_complex",
    "load_interference_certificate",
    "load_maup_invariance_certificate",
    "load_spatial_hodge_diagnostics",
    "persist_interaction_complex",
    "persist_interference_certificate",
    "persist_maup_invariance_certificate",
    "persist_spatial_hodge_diagnostics",
]
