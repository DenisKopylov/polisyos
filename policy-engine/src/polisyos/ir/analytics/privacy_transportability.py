"""Privacy-aware transportability certificates for DP-distorted multi-domain causal work.

This module complements :mod:`polisyos.ir.analytics.transportability`,
:mod:`polisyos.ir.analytics.dp_robustness`, and
:mod:`polisyos.ir.analytics.recoverability` without changing the public
``TransportabilityResult`` contract. The key distinction is between:

- latent transportability/recoverability on the true domain distributions; and
- observed validity on the released DP-distorted statistics.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics.transportability import (
    TransportabilityResult,
    TransportabilityStatus,
    TransportMode,
)
from polisyos.ir.analytics.uncertainty import (
    EnvelopeCombinationMethod,
    IntervalSemantics,
    UncertaintyEnvelope,
    UncertaintySource,
    combine_envelopes,
    persist_uncertainty_envelope,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import PrivacyAwareTransportCertificateRef, UncertaintyEnvelopeRef


class PrivacyObservedMode(str, Enum):
    """What claim strength is still valid on the published private release."""

    EXACT = "exact"
    INTERVAL = "interval"
    BOUNDS_ONLY = "bounds_only"
    BLOCKED = "blocked"


class PrivateFactorMetric(str, Enum):
    """Metric used to bound error on one transport/recovery factor."""

    TV = "tv"
    L1 = "l1"
    LINF = "linf"
    WASSERSTEIN = "wasserstein"
    INTERVAL = "interval"


class ValidityPredicateKind(str, Enum):
    """Predicate families that gate privacy-aware transport claims."""

    SUPPORT = "support"
    INVARIANCE = "invariance"
    THRESHOLD = "threshold"
    FORMULA_ERROR = "formula_error"


class DPMechanismScope(BaseModel):
    """Publicly known DP mechanism scope for one domain."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    domain_id: str
    mechanism_id: str
    mechanism_family: str
    privacy_model: str
    epsilon: float | None = Field(default=None, gt=0.0)
    delta: float | None = Field(default=None, ge=0.0, lt=1.0)
    protected_variables: tuple[str, ...] = ()
    released_statistics: tuple[str, ...] = ()
    clipping: dict[str, float] = Field(default_factory=dict)
    public_channel_spec: dict[str, Any] = Field(default_factory=dict)
    composition_group_id: str | None = None

    @model_validator(mode="after")
    def _validate_clipping(self) -> DPMechanismScope:
        for key, value in self.clipping.items():
            if value < 0.0:
                raise ValueError(f"clipping[{key!r}] must be >= 0")
        return self


class PrivateFactorBound(BaseModel):
    """Mechanism-aware error bound for one factor in a transport/recovery formula."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    factor_id: str
    factor_expression: str
    domain_id: str
    metric: PrivateFactorMetric
    error_bound: float = Field(ge=0.0)
    confidence_level: float = Field(gt=0.0, le=1.0)
    support_floor: float | None = Field(default=None, ge=0.0)
    estimator_kind: str
    debiasing_required: bool = False


class ValidityPredicate(BaseModel):
    """Margin-bearing predicate that must remain satisfied under DP distortion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    predicate_id: str
    predicate_kind: ValidityPredicateKind
    expression: str
    margin: float = Field(ge=0.0)
    sensitivity_by_factor: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_sensitivities(self) -> ValidityPredicate:
        for factor_id, value in self.sensitivity_by_factor.items():
            if value < 0.0:
                raise ValueError(f"sensitivity_by_factor[{factor_id!r}] must be >= 0")
        return self


class DistortionToleranceMap(BaseModel):
    """Factor-level tolerance region that preserves a transport certificate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query_id: str
    latent_formula_ref: str | None = None
    factor_ids: tuple[str, ...] = ()
    factor_metrics: dict[str, PrivateFactorMetric] = Field(default_factory=dict)
    factor_error_bounds: dict[str, float] = Field(default_factory=dict)
    support_floors: dict[str, float] = Field(default_factory=dict)
    predicate_margins: dict[str, float] = Field(default_factory=dict)
    sensitivity_matrix: dict[str, dict[str, float]] = Field(default_factory=dict)
    utility_maps: dict[str, dict[str, Any]] = Field(default_factory=dict)
    feasible_region: dict[str, Any] = Field(default_factory=dict)
    epsilon_projection: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_maps(self) -> DistortionToleranceMap:
        factor_id_set = set(self.factor_ids)
        if len(factor_id_set) != len(self.factor_ids):
            raise ValueError("factor_ids must be unique")
        for factor_id, value in self.factor_error_bounds.items():
            if value < 0.0:
                raise ValueError(f"factor_error_bounds[{factor_id!r}] must be >= 0")
            factor_id_set.add(factor_id)
        for event_id, value in self.support_floors.items():
            if value < 0.0:
                raise ValueError(f"support_floors[{event_id!r}] must be >= 0")
        for predicate_id, value in self.predicate_margins.items():
            if value < 0.0:
                raise ValueError(f"predicate_margins[{predicate_id!r}] must be >= 0")
        for predicate_id, factor_weights in self.sensitivity_matrix.items():
            for factor_id, weight in factor_weights.items():
                if weight < 0.0:
                    raise ValueError(
                        f"sensitivity_matrix[{predicate_id!r}][{factor_id!r}] must be >= 0"
                    )
                factor_id_set.add(factor_id)
        unknown_metric_factors = set(self.factor_metrics) - factor_id_set
        if unknown_metric_factors:
            unknown = ", ".join(sorted(unknown_metric_factors))
            raise ValueError(f"factor_metrics reference unknown factor ids: {unknown}")
        return self


class DPGraphSourceKind(str, Enum):
    """How the transport/recoverability graph was obtained relative to DP data."""

    FIXED_EX_ANTE = "fixed_ex_ante"
    INFERRED_NONPRIVATE = "inferred_nonprivate"
    INFERRED_PRIVATE = "inferred_private"
    UNKNOWN = "unknown"


class DPUtilityManifest(BaseModel):
    """Factor-level utility contract supplied by composition/observation stages."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    manifest_id: str
    query_id: str
    source_domains: tuple[str, ...] = ()
    target_domain: str
    dp_scope: tuple[DPMechanismScope, ...] = ()
    private_factor_bounds: tuple[PrivateFactorBound, ...] = ()
    validity_predicates: tuple[ValidityPredicate, ...] = ()
    distortion_tolerance_map: DistortionToleranceMap | None = None
    privacy_mismatch_variables: tuple[str, ...] = ()
    graph_source_kind: DPGraphSourceKind = DPGraphSourceKind.UNKNOWN
    graph_uncertainty_accounted: bool = False
    requires_public_channel_spec: bool = True
    fallback_queries: tuple[dict[str, Any], ...] = ()
    assumptions: tuple[str, ...] = ()
    composition_evidence: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_contract(self) -> DPUtilityManifest:
        if len({scope.domain_id for scope in self.dp_scope}) != len(self.dp_scope):
            raise ValueError("dp_scope domain_id values must be unique")
        known_domains = set(self.source_domains) | {self.target_domain}
        for bound in self.private_factor_bounds:
            if bound.domain_id not in known_domains:
                raise ValueError(
                    f"private factor bound domain_id={bound.domain_id!r} is not in source/target domains"
                )
        if len(set(self.privacy_mismatch_variables)) != len(self.privacy_mismatch_variables):
            raise ValueError("privacy_mismatch_variables must be unique")
        return self


class PrivacyAwareTransportCertificate(BaseModel):
    """Typed artifact splitting latent transportability from observed DP validity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    certificate_id: str
    query: str
    selection_diagram_ref: str
    latent_transport_status: TransportabilityStatus
    privacy_observed_mode: PrivacyObservedMode
    transport_formula_ref: str | None = None
    source_domains: tuple[str, ...] = ()
    target_domain: str
    dp_scope: tuple[DPMechanismScope, ...] = ()
    private_factor_bounds: tuple[PrivateFactorBound, ...] = ()
    validity_predicates: tuple[ValidityPredicate, ...] = ()
    distortion_tolerance_map: DistortionToleranceMap | None = None
    composed_uncertainty_envelope_ref: UncertaintyEnvelopeRef | None = None
    fallback_queries: tuple[dict[str, Any], ...] = ()
    blocking_reasons: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_contract(self) -> PrivacyAwareTransportCertificate:
        if len({scope.domain_id for scope in self.dp_scope}) != len(self.dp_scope):
            raise ValueError("dp_scope domain_id values must be unique")
        if self.privacy_observed_mode is PrivacyObservedMode.BLOCKED and not self.blocking_reasons:
            raise ValueError(
                "blocked privacy-aware transport certificates require blocking_reasons"
            )
        if self.privacy_observed_mode is PrivacyObservedMode.EXACT and self.blocking_reasons:
            raise ValueError(
                "exact privacy-aware transport certificates must not carry blocking_reasons"
            )

        known_domains = set(self.source_domains) | {self.target_domain}
        for bound in self.private_factor_bounds:
            if bound.domain_id not in known_domains:
                raise ValueError(
                    f"private factor bound domain_id={bound.domain_id!r} is not in source/target domains"
                )
        if self.privacy_observed_mode is not PrivacyObservedMode.BLOCKED and not self.dp_scope:
            raise ValueError("non-blocked privacy-aware transport certificates require dp_scope")
        return self

    def to_summary_dict(self) -> dict[str, Any]:
        """Return a compact summary suitable for transport metadata surfaces."""

        return {
            "schema_version": self.schema_version,
            "certificate_id": self.certificate_id,
            "query": self.query,
            "latent_transport_status": self.latent_transport_status.value,
            "privacy_observed_mode": self.privacy_observed_mode.value,
            "source_domains": list(self.source_domains),
            "target_domain": self.target_domain,
            "blocking_reasons": list(self.blocking_reasons),
            "factor_bounds": [
                {
                    "factor_id": bound.factor_id,
                    "domain_id": bound.domain_id,
                    "metric": bound.metric.value,
                    "error_bound": bound.error_bound,
                    "confidence_level": bound.confidence_level,
                    "support_floor": bound.support_floor,
                    "estimator_kind": bound.estimator_kind,
                    "debiasing_required": bound.debiasing_required,
                }
                for bound in self.private_factor_bounds
            ],
            "dp_scope": [
                {
                    "domain_id": scope.domain_id,
                    "mechanism_id": scope.mechanism_id,
                    "mechanism_family": scope.mechanism_family,
                    "privacy_model": scope.privacy_model,
                    "epsilon": scope.epsilon,
                    "delta": scope.delta,
                    "protected_variables": list(scope.protected_variables),
                }
                for scope in self.dp_scope
            ],
        }


class TransportPrivacyContext(BaseModel):
    """Typed carrier for privacy-aware transport gating inputs."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        arbitrary_types_allowed=True,
    )

    utility_manifest: DPUtilityManifest | None = None
    privacy_transport_certificate: PrivacyAwareTransportCertificate | None = None
    store: ArtifactStore | None = Field(default=None, exclude=True, repr=False)
    inputs: tuple[InputRef, ...] = Field(default=(), exclude=True, repr=False)
    certificate_id: str | None = None
    selection_diagram_ref: str | None = None

    @model_validator(mode="after")
    def _validate_sources(self) -> TransportPrivacyContext:
        if self.utility_manifest is None and self.privacy_transport_certificate is None:
            raise ValueError(
                "TransportPrivacyContext requires utility_manifest or privacy_transport_certificate"
            )
        if self.utility_manifest is not None and self.privacy_transport_certificate is not None:
            raise ValueError(
                "TransportPrivacyContext accepts either utility_manifest or privacy_transport_certificate, not both"
            )
        return self


def coerce_dp_utility_manifest(payload: Any | None) -> DPUtilityManifest | None:
    """Normalize DP utility manifests from dicts or nested metadata payloads."""

    if payload is None:
        return None
    if isinstance(payload, DPUtilityManifest):
        return payload

    candidate = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
    if not isinstance(candidate, dict):
        return None

    nested = candidate.get("dp_utility_manifest")
    if isinstance(nested, dict):
        candidate = nested

    required_keys = {"manifest_id", "query_id", "target_domain"}
    if not required_keys.issubset(candidate):
        return None

    try:
        return DPUtilityManifest.model_validate(candidate)
    except (TypeError, ValueError):
        return None


def coerce_privacy_aware_transport_certificate(
    payload: Any | None,
) -> PrivacyAwareTransportCertificate | None:
    """Normalize privacy-aware transport payloads from nested dicts or instances."""

    if payload is None:
        return None
    if isinstance(payload, PrivacyAwareTransportCertificate):
        return payload

    candidate = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
    if not isinstance(candidate, dict):
        return None

    nested = candidate.get("privacy_transport_certificate")
    if isinstance(nested, dict):
        candidate = nested

    required_keys = {
        "certificate_id",
        "query",
        "selection_diagram_ref",
        "latent_transport_status",
        "privacy_observed_mode",
        "target_domain",
    }
    if not required_keys.issubset(candidate):
        return None

    try:
        return PrivacyAwareTransportCertificate.model_validate(candidate)
    except (TypeError, ValueError):
        return None


def coerce_transport_privacy_context(
    payload: Any | None,
) -> TransportPrivacyContext | None:
    """Normalize transport privacy context payloads from dicts or nested payloads."""

    if payload is None:
        return None
    if isinstance(payload, TransportPrivacyContext):
        return payload

    candidate = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
    if not isinstance(candidate, Mapping):
        manifest = coerce_dp_utility_manifest(payload)
        if manifest is not None:
            return TransportPrivacyContext(utility_manifest=manifest)
        certificate = coerce_privacy_aware_transport_certificate(payload)
        if certificate is not None:
            return TransportPrivacyContext(privacy_transport_certificate=certificate)
        return None

    nested = candidate.get("transport_privacy_context")
    if isinstance(nested, Mapping):
        candidate = nested

    if candidate.get("utility_manifest") is not None:
        try:
            return TransportPrivacyContext(
                utility_manifest=DPUtilityManifest.model_validate(candidate["utility_manifest"]),
                certificate_id=candidate.get("certificate_id"),
                selection_diagram_ref=candidate.get("selection_diagram_ref"),
            )
        except (TypeError, ValueError):
            return None
    if candidate.get("privacy_transport_certificate") is not None:
        try:
            return TransportPrivacyContext(
                privacy_transport_certificate=PrivacyAwareTransportCertificate.model_validate(
                    candidate["privacy_transport_certificate"]
                ),
                certificate_id=candidate.get("certificate_id"),
                selection_diagram_ref=candidate.get("selection_diagram_ref"),
            )
        except (TypeError, ValueError):
            return None

    manifest = coerce_dp_utility_manifest(candidate)
    if manifest is not None:
        return TransportPrivacyContext(
            utility_manifest=manifest,
            certificate_id=candidate.get("certificate_id"),
            selection_diagram_ref=candidate.get("selection_diagram_ref"),
        )
    certificate = coerce_privacy_aware_transport_certificate(candidate)
    if certificate is not None:
        return TransportPrivacyContext(
            privacy_transport_certificate=certificate,
            certificate_id=candidate.get("certificate_id"),
            selection_diagram_ref=candidate.get("selection_diagram_ref"),
        )
    return None


def combine_private_factor_envelopes(
    factor_bounds: tuple[PrivateFactorBound, ...] | list[PrivateFactorBound],
) -> UncertaintyEnvelope | None:
    """Aggregate factor-level private uncertainty into one deterministic envelope."""

    bounds = tuple(factor_bounds)
    if not bounds:
        return None
    component_envelopes = [
        UncertaintyEnvelope(
            point_estimate=0.0,
            confidence_interval=(-bound.error_bound, bound.error_bound),
            confidence_level=None,
            source=UncertaintySource.CAUSAL,
            interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
            metadata={
                "factor_id": bound.factor_id,
                "domain_id": bound.domain_id,
                "metric": bound.metric.value,
                "estimator_kind": bound.estimator_kind,
            },
        )
        for bound in bounds
    ]
    combined = combine_envelopes(
        component_envelopes,
        method=EnvelopeCombinationMethod.CONSERVATIVE_UNION,
        source=UncertaintySource.CAUSAL,
    )
    total_radius = sum(bound.error_bound for bound in bounds)
    return combined.model_copy(
        update={
            "point_estimate": 0.0,
            "confidence_interval": (-total_radius, total_radius),
            "metadata": {
                **combined.metadata,
                "aggregation": "sum_of_factor_error_bounds",
                "factor_count": len(bounds),
            },
        }
    )


def build_privacy_aware_transport_certificate(
    *,
    utility_manifest: DPUtilityManifest,
    latent_transport_status: TransportabilityStatus,
    query: str,
    selection_diagram_ref: str,
    transport_formula_ref: str | None = None,
    certificate_id: str | None = None,
    composed_uncertainty_envelope_ref: UncertaintyEnvelopeRef | None = None,
) -> PrivacyAwareTransportCertificate:
    """Construct a privacy-aware certificate from a factor-level utility manifest."""

    blocking_reasons: list[str] = []
    actual_factor_errors: dict[str, float] = {}
    support_floor_failures: list[str] = []
    missing_factor_bounds: list[str] = []
    tolerance_exceeded: list[str] = []
    predicate_failures: list[str] = []

    for bound in utility_manifest.private_factor_bounds:
        actual_factor_errors[bound.factor_id] = max(
            actual_factor_errors.get(bound.factor_id, 0.0),
            bound.error_bound,
        )
        if bound.support_floor is not None and bound.error_bound > (bound.support_floor / 2.0):
            support_floor_failures.append(bound.factor_id)

    if latent_transport_status is TransportabilityStatus.UNSUPPORTED:
        blocking_reasons.append("latent_transport_unsupported")

    if (
        utility_manifest.graph_source_kind is DPGraphSourceKind.INFERRED_PRIVATE
        and not utility_manifest.graph_uncertainty_accounted
    ):
        blocking_reasons.append("graph_private_unaccounted")

    if utility_manifest.requires_public_channel_spec:
        for scope in utility_manifest.dp_scope:
            if not scope.public_channel_spec:
                blocking_reasons.append(f"missing_public_channel_spec:{scope.domain_id}")

    tolerance_map = utility_manifest.distortion_tolerance_map
    if tolerance_map is not None:
        required_factor_ids = set(tolerance_map.factor_ids) | set(tolerance_map.factor_error_bounds)
        for predicate in utility_manifest.validity_predicates:
            required_factor_ids.update(predicate.sensitivity_by_factor)
        for predicate_id, weights in tolerance_map.sensitivity_matrix.items():
            required_factor_ids.update(weights)
            if predicate_id not in tolerance_map.predicate_margins and all(
                pred.predicate_id != predicate_id for pred in utility_manifest.validity_predicates
            ):
                predicate_failures.append(f"missing_predicate_margin:{predicate_id}")
        for factor_id in sorted(required_factor_ids):
            if factor_id not in actual_factor_errors:
                missing_factor_bounds.append(factor_id)
                continue
            max_error = tolerance_map.factor_error_bounds.get(factor_id)
            if max_error is not None and actual_factor_errors[factor_id] > max_error:
                tolerance_exceeded.append(factor_id)

        predicate_catalog: list[tuple[str, float, dict[str, float]]] = []
        if utility_manifest.validity_predicates:
            predicate_catalog.extend(
                (
                    predicate.predicate_id,
                    predicate.margin,
                    dict(predicate.sensitivity_by_factor),
                )
                for predicate in utility_manifest.validity_predicates
            )
        else:
            predicate_catalog.extend(
                (
                    predicate_id,
                    margin,
                    dict(tolerance_map.sensitivity_matrix.get(predicate_id, {})),
                )
                for predicate_id, margin in tolerance_map.predicate_margins.items()
            )
        for predicate_id, margin, sensitivity_by_factor in predicate_catalog:
            if not sensitivity_by_factor:
                continue
            distortion = 0.0
            missing = False
            for factor_id, sensitivity in sensitivity_by_factor.items():
                if factor_id not in actual_factor_errors:
                    missing = True
                    missing_factor_bounds.append(factor_id)
                    continue
                distortion += sensitivity * actual_factor_errors[factor_id]
            if not missing and distortion > margin:
                predicate_failures.append(predicate_id)

    if missing_factor_bounds:
        blocking_reasons.extend(
            f"missing_factor_bound:{factor_id}" for factor_id in sorted(set(missing_factor_bounds))
        )
    if support_floor_failures:
        blocking_reasons.extend(
            f"support_floor_failed:{factor_id}" for factor_id in sorted(set(support_floor_failures))
        )

    if blocking_reasons:
        observed_mode = PrivacyObservedMode.BLOCKED
    elif tolerance_map is None:
        observed_mode = PrivacyObservedMode.INTERVAL
    elif not tolerance_exceeded and not predicate_failures:
        observed_mode = PrivacyObservedMode.EXACT
    elif utility_manifest.fallback_queries or support_floor_failures:
        observed_mode = PrivacyObservedMode.BOUNDS_ONLY
    else:
        observed_mode = PrivacyObservedMode.INTERVAL

    if observed_mode is not PrivacyObservedMode.BLOCKED:
        blocking_reasons = []
    else:
        blocking_reasons.extend(
            f"tolerance_exceeded:{factor_id}" for factor_id in sorted(set(tolerance_exceeded))
        )
        blocking_reasons.extend(
            f"predicate_margin_failed:{predicate_id}"
            for predicate_id in sorted(set(predicate_failures))
        )

    if observed_mode is PrivacyObservedMode.BOUNDS_ONLY:
        blocking_reasons = [
            *blocking_reasons,
            *(f"tolerance_exceeded:{factor_id}" for factor_id in sorted(set(tolerance_exceeded))),
            *(
                f"predicate_margin_failed:{predicate_id}"
                for predicate_id in sorted(set(predicate_failures))
            ),
        ]

    return PrivacyAwareTransportCertificate(
        certificate_id=certificate_id or utility_manifest.manifest_id,
        query=query,
        selection_diagram_ref=selection_diagram_ref,
        latent_transport_status=latent_transport_status,
        privacy_observed_mode=observed_mode,
        transport_formula_ref=transport_formula_ref,
        source_domains=utility_manifest.source_domains,
        target_domain=utility_manifest.target_domain,
        dp_scope=utility_manifest.dp_scope,
        private_factor_bounds=utility_manifest.private_factor_bounds,
        validity_predicates=utility_manifest.validity_predicates,
        distortion_tolerance_map=tolerance_map,
        composed_uncertainty_envelope_ref=composed_uncertainty_envelope_ref,
        fallback_queries=utility_manifest.fallback_queries,
        blocking_reasons=tuple(blocking_reasons),
        assumptions=utility_manifest.assumptions,
        provenance={
            **utility_manifest.provenance,
            "graph_source_kind": utility_manifest.graph_source_kind.value,
            "graph_uncertainty_accounted": utility_manifest.graph_uncertainty_accounted,
            "composition_evidence": utility_manifest.composition_evidence,
        },
    )


def privacy_transportability_summary(
    certificate: PrivacyAwareTransportCertificate,
    *,
    ref: PrivacyAwareTransportCertificateRef | None = None,
) -> dict[str, Any]:
    """Return the compact summary stored on operator-facing transport metadata."""

    summary = certificate.to_summary_dict()
    summary["privacy_certificate_ref"] = ref.model_dump(mode="json") if ref is not None else None
    return summary


def attach_privacy_transportability_to_result(
    result: TransportabilityResult,
    ref: PrivacyAwareTransportCertificateRef | None,
    certificate: PrivacyAwareTransportCertificate,
) -> TransportabilityResult:
    """Attach privacy-aware transport metadata without changing transport status semantics."""

    metadata = dict(result.metadata)
    summary = privacy_transportability_summary(certificate, ref=ref)
    metadata["privacy_certificate_ref"] = summary["privacy_certificate_ref"]
    metadata["privacy_observed_mode"] = summary["privacy_observed_mode"]
    metadata["privacy_latent_transport_status"] = summary["latent_transport_status"]
    metadata["privacy_blocking_reasons"] = summary["blocking_reasons"]
    metadata["privacy_factor_bounds"] = summary["factor_bounds"]
    metadata["privacy_dp_scope"] = summary["dp_scope"]
    return result.model_copy(update={"metadata": metadata})


def apply_privacy_transportability_gate(
    result: TransportabilityResult,
    certificate: PrivacyAwareTransportCertificate,
    *,
    ref: PrivacyAwareTransportCertificateRef | None = None,
) -> TransportabilityResult:
    """Project privacy-aware validity back onto the operator-facing result surface."""

    updated = attach_privacy_transportability_to_result(result, ref, certificate)
    if certificate.privacy_observed_mode is PrivacyObservedMode.EXACT:
        return updated
    if certificate.privacy_observed_mode is PrivacyObservedMode.INTERVAL:
        if updated.status is TransportabilityStatus.UNSUPPORTED:
            return updated
        identified_region = updated.identified_region or {
            "privacy_observed_mode": certificate.privacy_observed_mode.value,
            "privacy_interval_only": True,
        }
        return updated.model_copy(
            update={
                "status": TransportabilityStatus.PARTIALLY_IDENTIFIED,
                "identified_region": identified_region,
            }
        )
    if certificate.privacy_observed_mode is PrivacyObservedMode.BOUNDS_ONLY:
        identified_region = updated.identified_region or {
            "privacy_observed_mode": certificate.privacy_observed_mode.value,
            "privacy_bounds_only": True,
        }
        return updated.model_copy(
            update={
                "status": TransportabilityStatus.PARTIALLY_IDENTIFIED,
                "transport_mode": TransportMode.BOUNDS_ONLY,
                "identified_region": identified_region,
            }
        )

    return updated.model_copy(
        update={
            "status": TransportabilityStatus.UNSUPPORTED,
            "transport_mode": TransportMode.NONE,
            "transport_formula": None,
            "identified_region": None,
            "unsupported_reason": (
                certificate.blocking_reasons[0]
                if certificate.blocking_reasons
                else "privacy_transport_blocked"
            ),
        }
    )


def _fallback_selection_diagram_ref(result: TransportabilityResult) -> str:
    source = result.source_context_id or "source"
    target = result.target_context_id or "target"
    query = result.query or "transport_query"
    return f"selection_diagram:{source}->{target}:{query}"


def _build_result_scoped_privacy_certificate(
    result: TransportabilityResult,
    context: TransportPrivacyContext,
) -> PrivacyAwareTransportCertificate:
    if context.privacy_transport_certificate is not None:
        update: dict[str, Any] = {}
        certificate = context.privacy_transport_certificate
        if certificate.latent_transport_status is not result.status:
            update["latent_transport_status"] = result.status
        if certificate.transport_formula_ref is None and result.transport_formula is not None:
            update["transport_formula_ref"] = result.transport_formula.formula_str
        if context.selection_diagram_ref is not None:
            update["selection_diagram_ref"] = context.selection_diagram_ref
        return certificate if not update else certificate.model_copy(update=update)

    utility_manifest = context.utility_manifest
    if utility_manifest is None:  # pragma: no cover - guarded by model validation
        raise ValueError("missing utility_manifest for privacy-aware transport build")

    combined_envelope_ref = None
    if context.store is not None:
        combined_envelope = combine_private_factor_envelopes(utility_manifest.private_factor_bounds)
        if combined_envelope is not None:
            combined_envelope_ref = persist_uncertainty_envelope(
                context.store,
                combined_envelope,
                inputs=list(context.inputs),
            )

    selection_diagram_ref = (
        context.selection_diagram_ref
        or result.selection_diagram_ref
        or _fallback_selection_diagram_ref(result)
    )
    return build_privacy_aware_transport_certificate(
        utility_manifest=utility_manifest,
        latent_transport_status=result.status,
        query=result.query or "P*(Y|do(X))",
        selection_diagram_ref=selection_diagram_ref,
        transport_formula_ref=(
            result.transport_formula.formula_str if result.transport_formula is not None else None
        ),
        certificate_id=context.certificate_id,
        composed_uncertainty_envelope_ref=combined_envelope_ref,
    )


def apply_transport_privacy_context(
    result: TransportabilityResult,
    privacy_context: TransportPrivacyContext | Mapping[str, Any] | None,
) -> TransportabilityResult:
    """Apply privacy-aware transport gating and persistence for one result."""

    context = coerce_transport_privacy_context(privacy_context)
    if context is None:
        return result

    certificate = _build_result_scoped_privacy_certificate(result, context)
    ref = (
        persist_privacy_aware_transport_certificate(
            context.store,
            certificate,
            inputs=list(context.inputs),
        )
        if context.store is not None
        else None
    )
    return apply_privacy_transportability_gate(result, certificate, ref=ref)


def persist_privacy_aware_transport_certificate(
    store: ArtifactStore,
    certificate: PrivacyAwareTransportCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.privacy_aware_transport_certificate",
    schema_version: str = "1.0",
) -> PrivacyAwareTransportCertificateRef:
    """Persist a privacy-aware transport certificate and return its typed artifact ref."""

    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.privacy_aware_transport_certificate",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return PrivacyAwareTransportCertificateRef.model_validate(ref)


def load_privacy_aware_transport_certificate(
    store: ArtifactStore,
    ref: PrivacyAwareTransportCertificateRef,
) -> PrivacyAwareTransportCertificate:
    """Load a persisted privacy-aware transport certificate."""

    payload = get_json_artifact(store, ref.artifact_id)
    return PrivacyAwareTransportCertificate.model_validate(payload)


__all__ = [
    "DPGraphSourceKind",
    "DPMechanismScope",
    "DPUtilityManifest",
    "DistortionToleranceMap",
    "PrivacyAwareTransportCertificate",
    "PrivacyObservedMode",
    "PrivateFactorBound",
    "PrivateFactorMetric",
    "TransportPrivacyContext",
    "ValidityPredicate",
    "ValidityPredicateKind",
    "apply_privacy_transportability_gate",
    "apply_transport_privacy_context",
    "attach_privacy_transportability_to_result",
    "build_privacy_aware_transport_certificate",
    "coerce_dp_utility_manifest",
    "coerce_privacy_aware_transport_certificate",
    "coerce_transport_privacy_context",
    "combine_private_factor_envelopes",
    "load_privacy_aware_transport_certificate",
    "persist_privacy_aware_transport_certificate",
    "privacy_transportability_summary",
]
