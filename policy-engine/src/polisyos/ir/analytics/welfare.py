"""Decision-layer welfare contracts and identifiable channel-decomposition artifacts."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import (
    ArtifactRefModel,
    ChannelDecompositionArtifactRef,
    DependenceStructureRef,
    GEUncertaintyBundleRef,
    UncertaintyEnvelopeRef,
    WelfareBundleRef,
    WelfareSampleBundleRef,
)

_CHANNEL_DECOMPOSITION_ARTIFACT_SCHEMA_NAME = "ir.channel_decomposition_artifact"
_CHANNEL_DECOMPOSITION_ARTIFACT_SCHEMA_VERSION = "1.0"
_GE_UNCERTAINTY_BUNDLE_SCHEMA_NAME = "ir.ge_uncertainty_bundle"
_GE_UNCERTAINTY_BUNDLE_SCHEMA_VERSION = "1.0"
_WELFARE_BUNDLE_SCHEMA_NAME = "ir.welfare_bundle"
_WELFARE_BUNDLE_SCHEMA_VERSION = "1.0"
_WELFARE_SAMPLE_BUNDLE_SCHEMA_NAME = "ir.welfare_sample_bundle"
_WELFARE_SAMPLE_BUNDLE_SCHEMA_VERSION = "1.0"
_FIRST_STAGE_OK_THRESHOLD = 10.0
_DEFAULT_REMAINDER_TOLERANCE_RATIO = 0.25


class ChannelDecompositionTargetKind(str, Enum):
    """Target quantity whose channels are being decomposed."""

    NET_REVENUE = "net_revenue"
    SOCIAL_WELFARE = "social_welfare"
    MVPF_NUMERATOR = "mvpf_numerator"
    MVPF_DENOMINATOR = "mvpf_denominator"
    MDCF_COMPONENT = "mdcf_component"


class ChannelPolicyClass(str, Enum):
    """Policy-portfolio class used to interpret the decomposition."""

    LOCAL_AFFINE_TAX_TRANSFER = "local_affine_tax_transfer"
    BUDGET_NEUTRAL_AFFINE = "budget_neutral_affine"
    SPARSE_SHOCK_SET = "sparse_shock_set"


class ChannelIdentificationStatus(str, Enum):
    """Machine-readable verdict for channel identifiability."""

    IDENTIFIED = "identified"
    BOUNDED = "bounded"
    BLOCKED = "blocked"


class WelfareIntervalSemantics(str, Enum):
    """Declare the semantics of the interval fields attached to a welfare bundle."""

    CREDIBLE = "credible"
    PREDICTION = "prediction"
    ROBUST_OUTER = "robust_outer"
    MIXED_NESTED = "mixed_nested"
    NONE = "none"


class WelfareMethod(str, Enum):
    """Declare how the welfare summary was propagated or bounded."""

    ANALYTICAL = "analytical"
    DELTA = "delta"
    MONTE_CARLO = "monte_carlo"
    INTERVAL_OUTER = "interval_outer"
    ROBUST_SET = "robust_set"
    MIXED_NESTED = "mixed_nested"
    DETERMINISTIC = "deterministic"


class WelfareStatus(str, Enum):
    """Bundle-level execution quality used by decision and governance layers."""

    OK = "ok"
    PARTIAL = "partial"
    DEGRADED = "degraded"
    FAILED = "failed"


class GEUncertaintyRepresentation(str, Enum):
    """Declare how GE uncertainty is represented inside the supporting bundle."""

    MULTIPLIER_SAMPLES = "multiplier_samples"
    MULTIPLIER_INTERVALS = "multiplier_intervals"
    COEFFICIENT_INTERVALS = "coefficient_intervals"
    COVARIANCE_ON_A = "covariance_on_A"
    COVARIANCE_ON_J = "covariance_on_J"
    ELLIPSOIDAL_SET = "ellipsoidal_set"


class ChannelDecompositionArtifact(BaseModel):
    """Persisted channel-level decomposition with identifiability diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    target_kind: ChannelDecompositionTargetKind
    policy_class: ChannelPolicyClass
    basis_labels: tuple[str, ...] = Field(min_length=1)
    step_vector: tuple[float, ...] = Field(min_length=1)

    mechanical_vector: tuple[float, ...] | None = None
    behavioral_vector: tuple[float, ...] | None = None
    fiscal_feedback_vector: tuple[float, ...] | None = None
    total_vector: tuple[float, ...] | None = None

    identification_status: ChannelIdentificationStatus
    blocking_reasons: list[str] = Field(default_factory=list)

    baseline_microdata_ref: ArtifactRefModel
    policy_basis_ref: ArtifactRefModel
    mechanical_inputs_ref: ArtifactRefModel
    behavior_model_ref: ArtifactRefModel | None = None
    fiscal_state_model_ref: ArtifactRefModel | None = None
    instrument_set_ref: ArtifactRefModel | None = None
    proof_ref: ArtifactRefModel | None = None
    uncertainty_ref: ArtifactRefModel | None = None

    first_stage_stats: dict[str, float] = Field(default_factory=dict)
    overid_stats: dict[str, float] = Field(default_factory=dict)
    overlap_stats: dict[str, float] = Field(default_factory=dict)
    local_remainder_bound: float | None = Field(default=None, ge=0.0)
    timing_assumptions: list[str] = Field(default_factory=list)
    observability_notes: list[str] = Field(default_factory=list)
    diagnostic_summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_payload(self) -> ChannelDecompositionArtifact:
        if len(self.basis_labels) != len(self.step_vector):
            raise ValueError("basis_labels and step_vector must have equal length")

        channel_lengths = {
            len(vector)
            for vector in (
                self.mechanical_vector,
                self.behavioral_vector,
                self.fiscal_feedback_vector,
                self.total_vector,
            )
            if vector is not None
        }
        if len(channel_lengths) > 1:
            raise ValueError("all present channel vectors must share the same length")

        if self.identification_status is ChannelIdentificationStatus.IDENTIFIED:
            if self.mechanical_vector is None:
                raise ValueError("identified decompositions require mechanical_vector")
            if self.behavioral_vector is None:
                raise ValueError("identified decompositions require behavioral_vector")
            if self.fiscal_feedback_vector is None:
                raise ValueError("identified decompositions require fiscal_feedback_vector")
            if self.total_vector is None:
                raise ValueError("identified decompositions require total_vector")

        if self.identification_status is ChannelIdentificationStatus.BOUNDED:
            if self.mechanical_vector is None:
                raise ValueError("bounded decompositions require mechanical_vector")
            if self.total_vector is None:
                raise ValueError("bounded decompositions require total_vector")

        if (
            self.identification_status is ChannelIdentificationStatus.BLOCKED
            and not self.blocking_reasons
        ):
            raise ValueError("blocked decompositions require at least one blocking reason")

        return self


class GEUncertaintyBundle(BaseModel):
    """Supporting artifact describing GE multiplier uncertainty independently of welfare output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    model_class: str = Field(min_length=1)
    representation: GEUncertaintyRepresentation
    multiplier_shape: tuple[int, int]
    point_multiplier_ref: ArtifactRefModel | None = None
    lower_multiplier_ref: ArtifactRefModel | None = None
    upper_multiplier_ref: ArtifactRefModel | None = None
    sample_ref: ArtifactRefModel | None = None
    confidence_level: float | None = Field(default=None, gt=0.0, lt=1.0)
    calibration_window: str | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_bundle(self) -> GEUncertaintyBundle:
        rows, cols = self.multiplier_shape
        if rows <= 0 or cols <= 0:
            raise ValueError("multiplier_shape must contain positive dimensions")
        if (self.lower_multiplier_ref is None) != (self.upper_multiplier_ref is None):
            raise ValueError(
                "lower_multiplier_ref and upper_multiplier_ref must either both be set or both be null"
            )
        for field_name in (
            "point_multiplier_ref",
            "lower_multiplier_ref",
            "upper_multiplier_ref",
            "sample_ref",
        ):
            ref = getattr(self, field_name)
            if ref is not None and ref.media_type != "application/json":
                raise ValueError(f"{field_name} must reference application/json")
        return self


class WelfareSampleBundle(BaseModel):
    """Leaf artifact carrying welfare draws or extrema outside the summary bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    sample_axis: str = Field(default="draw", min_length=1)
    welfare_draws: tuple[float, ...] = Field(default_factory=tuple)
    welfare_pe_draws: tuple[float, ...] = Field(default_factory=tuple)
    welfare_ge_draws: tuple[float, ...] = Field(default_factory=tuple)
    robust_lower_extrema: tuple[float, ...] = Field(default_factory=tuple)
    robust_upper_extrema: tuple[float, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_bundle(self) -> WelfareSampleBundle:
        payloads = (
            self.welfare_draws,
            self.welfare_pe_draws,
            self.welfare_ge_draws,
            self.robust_lower_extrema,
            self.robust_upper_extrema,
        )
        if not any(payloads):
            raise ValueError("welfare sample bundle requires at least one populated sample payload")
        for payload in payloads:
            for value in payload:
                if not math.isfinite(float(value)):
                    raise ValueError("welfare sample payloads must be finite")
        return self


class WelfareBundle(BaseModel):
    """Top-level welfare bundle that stores refs plus summary welfare outputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    welfare_measure: str = Field(min_length=1)
    model_class: str = Field(default="unspecified", min_length=1)
    ge_multiplier_semantics: str = Field(default="unspecified", min_length=1)

    welfare_ref: ArtifactRefModel | None = None
    social_weight_ref: ArtifactRefModel | None = None
    policy_ref: ArtifactRefModel | None = None
    baseline_ref: ArtifactRefModel | None = None
    pe_model_ref: ArtifactRefModel | None = None
    ge_model_ref: ArtifactRefModel | None = None

    pe_uncertainty_refs: dict[str, UncertaintyEnvelopeRef] = Field(default_factory=dict)
    ge_uncertainty_ref: GEUncertaintyBundleRef | None = None
    dependence_structure_ref: DependenceStructureRef | None = None
    welfare_weights_ref: ArtifactRefModel | None = None
    channel_decomposition_ref: ChannelDecompositionArtifactRef | None = None

    point_estimate: float | None = None
    credible_interval: tuple[float, float] | None = None
    robust_interval: tuple[float, float] | None = None
    interval_semantics: WelfareIntervalSemantics = WelfareIntervalSemantics.NONE

    channel_decomposition: dict[str, float] = Field(default_factory=dict)
    subgroup_welfare: dict[str, float] = Field(default_factory=dict)

    method_used: WelfareMethod = WelfareMethod.DETERMINISTIC
    method_config_ref: ArtifactRefModel | None = None
    sample_bundle_ref: WelfareSampleBundleRef | None = None
    sensitivity_diagnostics_ref: ArtifactRefModel | None = None

    readiness_cap: str = Field(default="research_ready", min_length=1)
    warnings: list[str] = Field(default_factory=list)
    status: WelfareStatus = WelfareStatus.OK
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_payload(self) -> WelfareBundle:
        for field_name in (
            "welfare_ref",
            "social_weight_ref",
            "policy_ref",
            "baseline_ref",
            "pe_model_ref",
            "ge_model_ref",
            "welfare_weights_ref",
            "method_config_ref",
            "sensitivity_diagnostics_ref",
        ):
            ref = getattr(self, field_name)
            if ref is not None and ref.media_type != "application/json":
                raise ValueError(f"{field_name} must reference application/json")
        if self.point_estimate is not None and not math.isfinite(float(self.point_estimate)):
            raise ValueError("point_estimate must be finite")
        for interval_name in ("credible_interval", "robust_interval"):
            interval = getattr(self, interval_name)
            if interval is None:
                continue
            lower = float(interval[0])
            upper = float(interval[1])
            if not math.isfinite(lower) or not math.isfinite(upper):
                raise ValueError(f"{interval_name} must be finite")
            if lower > upper:
                raise ValueError(f"{interval_name} must satisfy lower <= upper")
        for mapping_name in ("channel_decomposition", "subgroup_welfare"):
            for key, value in getattr(self, mapping_name).items():
                if not str(key).strip():
                    raise ValueError(f"{mapping_name} keys must be non-empty")
                if not math.isfinite(float(value)):
                    raise ValueError(f"{mapping_name}.{key} must be finite")
        for key, ref in self.pe_uncertainty_refs.items():
            if not str(key).strip():
                raise ValueError("pe_uncertainty_refs keys must be non-empty")
            if ref.kind != "ir.uncertainty_envelope":
                raise ValueError(
                    f"pe_uncertainty_refs.{key} must reference ir.uncertainty_envelope"
                )
        has_summary = (
            self.point_estimate is not None
            or self.credible_interval is not None
            or self.robust_interval is not None
        )
        has_legacy_ref_payload = any(
            ref is not None
            for ref in (
                self.welfare_ref,
                self.social_weight_ref,
                self.channel_decomposition_ref,
            )
        )
        if not has_summary and not has_legacy_ref_payload:
            raise ValueError("welfare bundle must carry either summary outputs or legacy refs")
        if (
            self.status in {WelfareStatus.PARTIAL, WelfareStatus.DEGRADED, WelfareStatus.FAILED}
            and not self.warnings
        ):
            raise ValueError("non-ok welfare bundle status requires at least one warning")
        return self


def persist_channel_decomposition_artifact(
    store: ArtifactStore,
    artifact: ChannelDecompositionArtifact,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _CHANNEL_DECOMPOSITION_ARTIFACT_SCHEMA_NAME,
    schema_version: str = _CHANNEL_DECOMPOSITION_ARTIFACT_SCHEMA_VERSION,
) -> ChannelDecompositionArtifactRef:
    """Persist a channel-decomposition artifact and return its typed ref."""

    ref = put_json_artifact(
        store,
        artifact.model_dump(mode="json"),
        kind=_CHANNEL_DECOMPOSITION_ARTIFACT_SCHEMA_NAME,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ChannelDecompositionArtifactRef.model_validate(ref)


def load_channel_decomposition_artifact(
    store: ArtifactStore,
    ref: ChannelDecompositionArtifactRef,
) -> ChannelDecompositionArtifact:
    """Load a persisted channel-decomposition artifact."""

    payload = get_json_artifact(store, ref.artifact_id)
    return ChannelDecompositionArtifact.model_validate(payload)


def persist_ge_uncertainty_bundle(
    store: ArtifactStore,
    bundle: GEUncertaintyBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _GE_UNCERTAINTY_BUNDLE_SCHEMA_NAME,
    schema_version: str = _GE_UNCERTAINTY_BUNDLE_SCHEMA_VERSION,
) -> GEUncertaintyBundleRef:
    """Persist a GE uncertainty bundle and return its typed ref."""

    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind=_GE_UNCERTAINTY_BUNDLE_SCHEMA_NAME,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return GEUncertaintyBundleRef.model_validate(ref)


def load_ge_uncertainty_bundle(
    store: ArtifactStore,
    ref: GEUncertaintyBundleRef,
) -> GEUncertaintyBundle:
    """Load a persisted GE uncertainty bundle."""

    payload = get_json_artifact(store, ref.artifact_id)
    return GEUncertaintyBundle.model_validate(payload)


def persist_welfare_sample_bundle(
    store: ArtifactStore,
    bundle: WelfareSampleBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _WELFARE_SAMPLE_BUNDLE_SCHEMA_NAME,
    schema_version: str = _WELFARE_SAMPLE_BUNDLE_SCHEMA_VERSION,
) -> WelfareSampleBundleRef:
    """Persist a welfare sample bundle and return its typed ref."""

    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind=_WELFARE_SAMPLE_BUNDLE_SCHEMA_NAME,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return WelfareSampleBundleRef.model_validate(ref)


def load_welfare_sample_bundle(
    store: ArtifactStore,
    ref: WelfareSampleBundleRef,
) -> WelfareSampleBundle:
    """Load a persisted welfare sample bundle."""

    payload = get_json_artifact(store, ref.artifact_id)
    return WelfareSampleBundle.model_validate(payload)


def persist_welfare_bundle(
    store: ArtifactStore,
    bundle: WelfareBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _WELFARE_BUNDLE_SCHEMA_NAME,
    schema_version: str = _WELFARE_BUNDLE_SCHEMA_VERSION,
) -> WelfareBundleRef:
    """Persist a welfare bundle and return its typed ref."""

    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind=_WELFARE_BUNDLE_SCHEMA_NAME,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return WelfareBundleRef.model_validate(ref)


def load_welfare_bundle(
    store: ArtifactStore,
    ref: WelfareBundleRef,
) -> WelfareBundle:
    """Load a persisted welfare bundle."""

    payload = get_json_artifact(store, ref.artifact_id)
    return WelfareBundle.model_validate(payload)


def build_channel_decomposition_ref(
    store: ArtifactStore,
    *,
    target_kind: ChannelDecompositionTargetKind | str,
    baseline_microdata_ref: ArtifactRefModel,
    policy_basis_ref: ArtifactRefModel,
    mechanical_inputs_ref: ArtifactRefModel,
    behavior_model_ref: ArtifactRefModel | None = None,
    fiscal_state_model_ref: ArtifactRefModel | None = None,
    instrument_set_ref: ArtifactRefModel | None = None,
    proof_ref: ArtifactRefModel | None = None,
    uncertainty_ref: ArtifactRefModel | None = None,
    total_vector: Sequence[float] | None = None,
    block_on_failure: bool = True,
) -> ChannelDecompositionArtifactRef:
    """Persist a normalized channel-decomposition artifact from upstream leaf artifacts.

    The builder expects JSON payloads at the supplied refs with normalized keys such as
    ``basis_labels``, ``step_vector``, ``mechanical_vector`` or ``mechanical_matrix``,
    ``behavioral_vector``, ``fiscal_feedback_vector``, ``total_vector``, ``*_stats`` and
    ``*_ok`` diagnostics. It does not estimate the channels itself; it validates upstream
    replay/estimation outputs, applies the blocking rule, and persists a strict typed artifact.
    """

    baseline_payload = _load_artifact_mapping(
        store,
        baseline_microdata_ref,
        field_name="baseline_microdata_ref",
    )
    policy_basis_payload = _load_artifact_mapping(
        store,
        policy_basis_ref,
        field_name="policy_basis_ref",
    )
    mechanical_payload = _load_artifact_mapping(
        store,
        mechanical_inputs_ref,
        field_name="mechanical_inputs_ref",
    )
    behavior_payload = (
        None
        if behavior_model_ref is None
        else _load_artifact_mapping(
            store,
            behavior_model_ref,
            field_name="behavior_model_ref",
        )
    )
    fiscal_payload = (
        None
        if fiscal_state_model_ref is None
        else _load_artifact_mapping(
            store,
            fiscal_state_model_ref,
            field_name="fiscal_state_model_ref",
        )
    )
    instrument_payload = (
        None
        if instrument_set_ref is None
        else _load_artifact_mapping(
            store,
            instrument_set_ref,
            field_name="instrument_set_ref",
        )
    )

    basis_labels = _coerce_str_tuple(
        policy_basis_payload.get("basis_labels"),
        field_name="policy_basis_ref.basis_labels",
    )
    step_vector_tuple = _coerce_float_tuple(
        policy_basis_payload.get("step_vector"),
        field_name="policy_basis_ref.step_vector",
    )
    policy_class = ChannelPolicyClass(
        str(
            policy_basis_payload.get(
                "policy_class",
                ChannelPolicyClass.LOCAL_AFFINE_TAX_TRANSFER.value,
            )
        )
    )

    mechanical_vector = _resolve_mechanical_vector(mechanical_payload, step_vector_tuple)
    behavioral_candidate = _resolve_optional_vector(
        behavior_payload,
        field_name="behavior_model_ref.behavioral_vector",
        key="behavioral_vector",
    )
    fiscal_candidate = _resolve_optional_vector(
        fiscal_payload,
        field_name="fiscal_state_model_ref.fiscal_feedback_vector",
        key="fiscal_feedback_vector",
    )
    raw_total_vector = _resolve_total_vector(
        explicit=total_vector,
        payloads=(
            instrument_payload,
            fiscal_payload,
            behavior_payload,
            mechanical_payload,
            baseline_payload,
            policy_basis_payload,
        ),
        candidates=(mechanical_vector, behavioral_candidate, fiscal_candidate),
    )

    first_stage_stats = _merge_numeric_maps(
        _resolve_numeric_map(behavior_payload, key="first_stage_stats"),
        _resolve_numeric_map(fiscal_payload, key="first_stage_stats"),
        _resolve_numeric_map(instrument_payload, key="first_stage_stats"),
    )
    overid_stats = _merge_numeric_maps(_resolve_numeric_map(instrument_payload, key="overid_stats"))
    overlap_stats = _merge_numeric_maps(_resolve_numeric_map(baseline_payload, key="overlap_stats"))
    local_remainder_bound = _resolve_local_remainder_bound(
        policy_basis_payload,
        mechanical_payload,
        behavior_payload,
        fiscal_payload,
        instrument_payload,
    )

    policy_rank_ok = _resolve_policy_rank_ok(policy_basis_payload, n_basis=len(step_vector_tuple))
    behavior_stage_ok = _resolve_stage_ok(
        behavior_payload,
        vector=behavioral_candidate,
        stage_name="behavioral",
    )
    fiscal_stage_ok = _resolve_stage_ok(
        fiscal_payload,
        vector=fiscal_candidate,
        stage_name="fiscal",
    )
    overid_ok = _resolve_overid_ok(instrument_payload)
    timing_ok = _resolve_timing_ok(
        policy_basis_payload, behavior_payload, fiscal_payload, instrument_payload
    )
    overlap_ok = _resolve_overlap_ok(baseline_payload, instrument_payload)
    remainder_ok = _resolve_remainder_ok(
        local_remainder_bound,
        raw_total_vector,
        policy_basis_payload,
        mechanical_payload,
        behavior_payload,
        fiscal_payload,
        instrument_payload,
    )

    strict_failures: list[str] = []
    if mechanical_vector is None:
        strict_failures.append("mechanical_map_missing")
    if not policy_rank_ok:
        strict_failures.append("policy_rank_failed")
    if not overid_ok:
        strict_failures.append("exclusion_or_overidentification_failed")
    if not timing_ok:
        strict_failures.append("timing_diagnostics_failed")

    bounds_only_reasons: list[str] = []
    if not overlap_ok:
        bounds_only_reasons.append("support_overlap_insufficient")
    if not remainder_ok:
        bounds_only_reasons.append("local_linearization_invalid")

    degrade_reasons: list[str] = []
    if behavioral_candidate is None or not behavior_stage_ok:
        degrade_reasons.append("behavioral_channel_unidentified")
    if behavior_stage_ok and behavioral_candidate is not None:
        if fiscal_candidate is None or not fiscal_stage_ok:
            degrade_reasons.append("fiscal_feedback_channel_unidentified")

    partial_id_only = bool(bounds_only_reasons)
    strict_failure_present = bool(strict_failures)
    behavior_point_ok = (
        not strict_failure_present
        and not partial_id_only
        and behavioral_candidate is not None
        and behavior_stage_ok
    )
    fiscal_point_ok = behavior_point_ok and fiscal_candidate is not None and fiscal_stage_ok

    if strict_failure_present and block_on_failure:
        identification_status = ChannelIdentificationStatus.BLOCKED
        reasons = strict_failures
    else:
        reasons = []
        if strict_failure_present:
            reasons.extend(strict_failures)
        reasons.extend(degrade_reasons)
        reasons.extend(bounds_only_reasons)
        if (
            fiscal_point_ok
            and not reasons
            and mechanical_vector is not None
            and raw_total_vector is not None
        ):
            identification_status = ChannelIdentificationStatus.IDENTIFIED
        else:
            identification_status = ChannelIdentificationStatus.BOUNDED

    behavioral_vector = behavioral_candidate if behavior_point_ok else None
    fiscal_feedback_vector = fiscal_candidate if fiscal_point_ok else None
    if identification_status is ChannelIdentificationStatus.BLOCKED:
        behavioral_vector = None
        fiscal_feedback_vector = None

    diagnostic_summary = {
        "mechanical_map_ok": mechanical_vector is not None,
        "policy_rank_ok": policy_rank_ok,
        "behavior_stage_ok": behavior_stage_ok,
        "fiscal_stage_ok": fiscal_stage_ok,
        "overid_ok": overid_ok,
        "timing_ok": timing_ok,
        "overlap_ok": overlap_ok,
        "remainder_ok": remainder_ok,
        "block_on_failure": bool(block_on_failure),
        "behavior_point_estimate_admissible": behavior_point_ok,
        "fiscal_point_estimate_admissible": fiscal_point_ok,
    }

    artifact = ChannelDecompositionArtifact(
        target_kind=target_kind,
        policy_class=policy_class,
        basis_labels=basis_labels,
        step_vector=step_vector_tuple,
        mechanical_vector=mechanical_vector,
        behavioral_vector=behavioral_vector,
        fiscal_feedback_vector=fiscal_feedback_vector,
        total_vector=raw_total_vector,
        identification_status=identification_status,
        blocking_reasons=_dedupe_strings(reasons),
        baseline_microdata_ref=baseline_microdata_ref,
        policy_basis_ref=policy_basis_ref,
        mechanical_inputs_ref=mechanical_inputs_ref,
        behavior_model_ref=behavior_model_ref,
        fiscal_state_model_ref=fiscal_state_model_ref,
        instrument_set_ref=instrument_set_ref,
        proof_ref=proof_ref,
        uncertainty_ref=uncertainty_ref,
        first_stage_stats=first_stage_stats,
        overid_stats=overid_stats,
        overlap_stats=overlap_stats,
        local_remainder_bound=local_remainder_bound,
        timing_assumptions=_collect_string_lists(
            policy_basis_payload,
            behavior_payload,
            fiscal_payload,
            instrument_payload,
            key="timing_assumptions",
        ),
        observability_notes=_collect_string_lists(
            baseline_payload,
            mechanical_payload,
            behavior_payload,
            fiscal_payload,
            instrument_payload,
            key="observability_notes",
        ),
        diagnostic_summary=diagnostic_summary,
        metadata={"builder": "build_channel_decomposition_ref"},
    )

    inputs = _input_refs(
        ("baseline_microdata", baseline_microdata_ref),
        ("policy_basis", policy_basis_ref),
        ("mechanical_inputs", mechanical_inputs_ref),
        ("behavior_model", behavior_model_ref),
        ("fiscal_state_model", fiscal_state_model_ref),
        ("instrument_set", instrument_set_ref),
        ("proof", proof_ref),
        ("uncertainty", uncertainty_ref),
    )
    return persist_channel_decomposition_artifact(store, artifact, inputs=inputs)


def _load_artifact_mapping(
    store: ArtifactStore,
    ref: ArtifactRefModel,
    *,
    field_name: str,
) -> dict[str, Any]:
    payload = get_json_artifact(store, ref.artifact_id)
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must reference a JSON object payload")
    return dict(payload)


def _coerce_str_tuple(value: Any, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a non-empty sequence of strings")
    items: list[str] = []
    for raw in value:
        text = str(raw).strip()
        if not text:
            raise ValueError(f"{field_name} must not contain empty values")
        items.append(text)
    if not items:
        raise ValueError(f"{field_name} must not be empty")
    return tuple(items)


def _coerce_float_tuple(value: Any, *, field_name: str) -> tuple[float, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a non-empty sequence of finite numbers")
    items: list[float] = []
    for raw in value:
        number = float(raw)
        if not math.isfinite(number):
            raise ValueError(f"{field_name} must contain only finite numbers")
        items.append(number)
    if not items:
        raise ValueError(f"{field_name} must not be empty")
    return tuple(items)


def _resolve_optional_vector(
    payload: Mapping[str, Any] | None,
    *,
    field_name: str,
    key: str,
) -> tuple[float, ...] | None:
    if payload is None or payload.get(key) is None:
        return None
    return _coerce_float_tuple(payload[key], field_name=field_name)


def _resolve_mechanical_vector(
    payload: Mapping[str, Any],
    step_vector: tuple[float, ...],
) -> tuple[float, ...] | None:
    explicit = _resolve_optional_vector(
        payload,
        field_name="mechanical_inputs_ref.mechanical_vector",
        key="mechanical_vector",
    )
    if explicit is not None:
        return explicit

    matrix_raw = payload.get("mechanical_matrix")
    if matrix_raw is None:
        return None
    if not isinstance(matrix_raw, Sequence) or isinstance(matrix_raw, (str, bytes, bytearray)):
        raise ValueError("mechanical_inputs_ref.mechanical_matrix must be a 2D numeric sequence")

    rows: list[tuple[float, ...]] = []
    for index, row in enumerate(matrix_raw):
        row_tuple = _coerce_float_tuple(
            row,
            field_name=f"mechanical_inputs_ref.mechanical_matrix[{index}]",
        )
        if len(row_tuple) != len(step_vector):
            raise ValueError("mechanical_matrix columns must align with step_vector")
        rows.append(row_tuple)
    if not rows:
        raise ValueError("mechanical_inputs_ref.mechanical_matrix must not be empty")

    return tuple(
        sum(cell * step for cell, step in zip(row, step_vector, strict=False)) for row in rows
    )


def _resolve_total_vector(
    *,
    explicit: Sequence[float] | None,
    payloads: Sequence[Mapping[str, Any] | None],
    candidates: Sequence[tuple[float, ...] | None],
) -> tuple[float, ...] | None:
    if explicit is not None:
        return _coerce_float_tuple(explicit, field_name="total_vector")

    for payload in payloads:
        if payload is not None and payload.get("total_vector") is not None:
            return _coerce_float_tuple(payload["total_vector"], field_name="payload.total_vector")

    return _sum_vectors(*candidates)


def _sum_vectors(*vectors: tuple[float, ...] | None) -> tuple[float, ...] | None:
    present = [vector for vector in vectors if vector is not None]
    if not present:
        return None
    expected_length = len(present[0])
    total = [0.0] * expected_length
    for vector in present:
        if len(vector) != expected_length:
            raise ValueError("all present channel vectors must share the same length")
        for index, value in enumerate(vector):
            total[index] += value
    return tuple(total)


def _resolve_numeric_map(
    payload: Mapping[str, Any] | None,
    *,
    key: str,
) -> dict[str, float]:
    if payload is None or payload.get(key) is None:
        return {}
    raw = payload[key]
    if not isinstance(raw, Mapping):
        raise ValueError(f"{key} must be a mapping of numeric diagnostics")

    normalized: dict[str, float] = {}
    for raw_key, raw_value in raw.items():
        key_text = str(raw_key).strip()
        if not key_text:
            raise ValueError(f"{key} must not contain empty keys")
        number = float(raw_value)
        if not math.isfinite(number):
            raise ValueError(f"{key}[{key_text!r}] must be finite")
        normalized[key_text] = number
    return normalized


def _merge_numeric_maps(*maps: dict[str, float]) -> dict[str, float]:
    merged: dict[str, float] = {}
    for mapping in maps:
        merged.update(mapping)
    return merged


def _resolve_policy_rank_ok(payload: Mapping[str, Any], *, n_basis: int) -> bool:
    if "policy_rank_ok" in payload:
        return _coerce_bool(payload["policy_rank_ok"])
    if "rank" in payload:
        return int(payload["rank"]) >= n_basis
    if "min_singular_value" in payload:
        return float(payload["min_singular_value"]) > 0.0
    return True


def _resolve_stage_ok(
    payload: Mapping[str, Any] | None,
    *,
    vector: tuple[float, ...] | None,
    stage_name: str,
) -> bool:
    if payload is None:
        return False

    for key in (f"{stage_name}_first_stage_ok", "first_stage_ok"):
        if key in payload:
            return _coerce_bool(payload[key])

    if _coerce_bool(payload.get("observed_response", False)) or _coerce_bool(
        payload.get("observed_state", False)
    ):
        return True

    stats = _resolve_numeric_map(payload, key="first_stage_stats")
    for key in (
        "first_stage_f",
        "kleibergen_paap_f",
        "sanderson_windmeijer_f",
        "kp_f",
        "f_stat",
    ):
        if key in stats:
            return stats[key] >= _FIRST_STAGE_OK_THRESHOLD

    return vector is not None


def _resolve_overid_ok(payload: Mapping[str, Any] | None) -> bool:
    if payload is None:
        return True
    if "overid_ok" in payload:
        return _coerce_bool(payload["overid_ok"])
    if "exclusion_ok" in payload:
        return _coerce_bool(payload["exclusion_ok"])
    if _coerce_bool(payload.get("overid_rejected", False)):
        return False
    if _coerce_bool(payload.get("exclusion_failed", False)):
        return False

    stats = _resolve_numeric_map(payload, key="overid_stats")
    hansen_pvalue = stats.get("hansen_pvalue")
    if hansen_pvalue is not None:
        return hansen_pvalue >= 0.01
    return True


def _resolve_timing_ok(*payloads: Mapping[str, Any] | None) -> bool:
    for payload in payloads:
        if payload is None:
            continue
        if "timing_ok" in payload and not _coerce_bool(payload["timing_ok"]):
            return False
        if "pretrends_ok" in payload and not _coerce_bool(payload["pretrends_ok"]):
            return False
    return True


def _resolve_overlap_ok(*payloads: Mapping[str, Any] | None) -> bool:
    for payload in payloads:
        if payload is None:
            continue
        for key in ("overlap_ok", "support_ok", "positivity_ok"):
            if key in payload and not _coerce_bool(payload[key]):
                return False
    return True


def _resolve_remainder_ok(
    local_remainder_bound: float | None,
    total_vector: tuple[float, ...] | None,
    *payloads: Mapping[str, Any] | None,
) -> bool:
    for payload in payloads:
        if payload is None:
            continue
        if "local_linearization_ok" in payload:
            return _coerce_bool(payload["local_linearization_ok"])

    if local_remainder_bound is None or total_vector is None:
        return True

    tolerance_ratio = _DEFAULT_REMAINDER_TOLERANCE_RATIO
    for payload in payloads:
        if payload is None:
            continue
        if "remainder_tolerance_ratio" in payload:
            tolerance_ratio = float(payload["remainder_tolerance_ratio"])
            break

    total_scale = max(sum(abs(value) for value in total_vector), 1.0e-12)
    return local_remainder_bound <= tolerance_ratio * total_scale


def _resolve_local_remainder_bound(*payloads: Mapping[str, Any] | None) -> float | None:
    for payload in payloads:
        if payload is None or payload.get("local_remainder_bound") is None:
            continue
        value = float(payload["local_remainder_bound"])
        if not math.isfinite(value) or value < 0.0:
            raise ValueError("local_remainder_bound must be finite and non-negative")
        return value
    return None


def _collect_string_lists(*payloads: Mapping[str, Any] | None, key: str) -> list[str]:
    collected: list[str] = []
    for payload in payloads:
        if payload is None or payload.get(key) is None:
            continue
        raw_values = payload[key]
        if not isinstance(raw_values, Sequence) or isinstance(raw_values, (str, bytes, bytearray)):
            raise ValueError(f"{key} must be a sequence of strings")
        for raw in raw_values:
            text = str(raw).strip()
            if text:
                collected.append(text)
    return _dedupe_strings(collected)


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "ok", "pass"}:
            return True
        if normalized in {"false", "0", "no", "n", "fail"}:
            return False
    return bool(value)


def _dedupe_strings(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in values:
        text = str(raw).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _input_refs(*entries: tuple[str, ArtifactRefModel | None]) -> list[InputRef]:
    refs: list[InputRef] = []
    for role, ref in entries:
        if ref is None:
            continue
        refs.append(InputRef(artifact_id=ref.artifact_id, role=role))
    return refs


__all__ = [
    "ChannelDecompositionArtifact",
    "ChannelDecompositionTargetKind",
    "ChannelIdentificationStatus",
    "ChannelPolicyClass",
    "GEUncertaintyBundle",
    "GEUncertaintyRepresentation",
    "WelfareBundle",
    "WelfareIntervalSemantics",
    "WelfareMethod",
    "WelfareSampleBundle",
    "WelfareStatus",
    "build_channel_decomposition_ref",
    "load_channel_decomposition_artifact",
    "load_ge_uncertainty_bundle",
    "load_welfare_bundle",
    "load_welfare_sample_bundle",
    "persist_channel_decomposition_artifact",
    "persist_ge_uncertainty_bundle",
    "persist_welfare_bundle",
    "persist_welfare_sample_bundle",
]
