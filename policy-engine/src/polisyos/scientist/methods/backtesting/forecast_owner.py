"""Produce one CAS-bound predictive calibration result from a real forecast method.

This module is the narrow owner for the first FRC-02 empirical slice.  It
executes the registered exponential-smoothing method on an explicit training
slice, evaluates the resulting predictive intervals against a held-out slice,
and persists every handoff through the existing CAS/IR owners.  The result is
deliberately predictive-only and bridge-pending: no value from this owner is a
causal-effect confidence interval or an S10 promotion.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from datetime import date, datetime
from typing import Annotated, Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator

from polisyos.calibration import evaluate_continuous
from polisyos.core.artifacts import FileSystemCAS, artifact_manifest_profile_sha256
from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.contracts import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.forecast_profile_member import (
    FORECAST_PROFILE_MEMBER_KIND,
    FORECAST_PROFILE_MEMBER_SCHEMA,
    FORECAST_PROFILE_MEMBER_SCHEMA_VERSION,
    VALUE_DATA_PROFILE_KIND,
    ForecastProfileMemberV1,
    forecast_profile_observed_series_sha256,
)
from polisyos.foundry.methods import (
    BackendSpec,
    ComputeBackend,
    MethodArtifact,
    MethodDispatcher,
    MethodRegistry,
    ShapeSpec,
    Specialization,
    compute_static_params_hash,
    ensure_forecasting_methods_registered,
    store_method_artifact,
)
from polisyos.ir import (
    ArtifactID,
    ArtifactRefModel,
    ArtifactStore,
    BacktestReport,
    BacktestReportRef,
    CanonSpec,
    ForecastingUncertaintyBundle,
    ForecastingUncertaintyBundleRef,
    ForecastIntervalSemantics,
    InputRef,
    get_json_artifact,
    load_backtest_report,
    load_forecasting_uncertainty_bundle,
    normalize_artifact_ref,
    persist_forecasting_uncertainty_bundle,
    put_json_artifact,
)
from polisyos.ir.analytics.calibration_diagnostics import CalibrationDiagnosticsReport
from polisyos.scientist.methods.backtesting.orchestrator import (
    BacktestOrchestrator,
    TrustScreeningMode,
)
from polisyos.scientist.methods.backtesting.plan import (
    HistoricalValidationPlan,
    PredictionSource,
)

METHOD_FQN = "forecasting.univariate.exponential_smoothing@1.0.0"
PREDICTIVE_INTERVAL_COVERAGE = "predictive_interval_coverage"
CALIBRATION_RULE_ID = "rolling-origin-residual-conformal.v1"
CALIBRATION_RULE_KIND = "ir.forecast_calibration_rule"
MODEL_SPEC_KIND = "ir.model_spec"
POLICY_SPEC_KIND = "ir.policy_spec"
SOURCE_RECEIPT_KIND = "scientist.forecast_source_receipt"
SOURCE_RECEIPT_SCHEMA = "polisyos.scientist.ForecastSourceReceipt"
SOURCE_RECEIPT_SCHEMA_VERSION = "1.0"
_ETS_PARAMETER_FLOOR = 1e-6
_MIN_TRAIN_OBSERVATIONS = 8


class TrainHoldoutSplit(BaseModel):
    """Explicit, contiguous source positions used for training and evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    train_start: int = Field(default=0, ge=0)
    train_end: int = Field(ge=1)
    holdout_start: int = Field(ge=1)
    holdout_end: int = Field(ge=2)
    horizon: int = Field(ge=1)

    @model_validator(mode="after")
    def _validate_split(self) -> TrainHoldoutSplit:
        if self.train_start >= self.train_end:
            raise ValueError("train_start must be before train_end")
        if self.holdout_start != self.train_end:
            raise ValueError("train and holdout slices must be contiguous")
        if self.holdout_start >= self.holdout_end:
            raise ValueError("holdout_start must be before holdout_end")
        if self.horizon != self.holdout_end - self.holdout_start:
            raise ValueError("horizon must match the explicit holdout length")
        return self


class ForecastMethodParams(BaseModel):
    """The exact static/dynamic parameters accepted by the chosen ETS method."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    horizon: int = Field(ge=1)
    alpha: float = Field(ge=_ETS_PARAMETER_FLOOR, le=1.0, default=0.3)
    beta: float = Field(ge=_ETS_PARAMETER_FLOOR, le=1.0, default=0.1)

    @model_validator(mode="after")
    def _validate_finite(self) -> ForecastMethodParams:
        if not math.isfinite(self.alpha) or not math.isfinite(self.beta):
            raise ValueError("exponential-smoothing parameters must be finite")
        return self


class ForecastTemporalRoles(BaseModel):
    """Six distinct timezone-aware times carried across the predictive handoff."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    data_valid_time: datetime
    calibration_window_start: datetime
    calibration_window_end: datetime
    policy_effective_time: datetime
    prediction_time: datetime
    observation_time: datetime

    @model_validator(mode="after")
    def _validate_temporal_roles(self) -> ForecastTemporalRoles:
        values = (
            self.data_valid_time,
            self.calibration_window_start,
            self.calibration_window_end,
            self.policy_effective_time,
            self.prediction_time,
            self.observation_time,
        )
        if any(value.tzinfo is None or value.utcoffset() is None for value in values):
            raise ValueError("all forecast temporal roles must be timezone-aware")
        if len(set(values)) != len(values):
            raise ValueError("forecast temporal roles must be distinct")
        if not (
            self.data_valid_time
            < self.calibration_window_start
            < self.calibration_window_end
            <= self.prediction_time
            < self.observation_time
        ):
            raise ValueError("forecast temporal roles must preserve their temporal order")
        if self.policy_effective_time > self.prediction_time:
            raise ValueError("policy_effective_time cannot follow prediction_time")
        return self


class _SourceReceiptBase(BaseModel):
    """Common exact source, series, unit, shape, and values binding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"]
    observed_source_ref: ArtifactRefModel
    physical_data_ref: ArtifactRefModel
    selected_projection_schema_id: str = Field(min_length=1)
    selected_projection_schema_version: str = Field(min_length=1)
    series_id: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    selected_field_id: str = Field(min_length=1)
    selected_period_field_id: str = Field(min_length=1)
    selected_series_shape: tuple[Annotated[int, Field(strict=True)], ...] = Field(min_length=1)
    selected_series_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_rows_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_selected_series(self) -> _SourceReceiptBase:
        if str(self.observed_source_ref.artifact_id) == str(self.physical_data_ref.artifact_id):
            raise ValueError("snapshot and physical data must be distinct source artifacts")
        for ref, expected_kind in (
            (self.observed_source_ref, "fabric.data_snapshot"),
            (self.physical_data_ref, None),
        ):
            if (
                ref.media_type != "application/json"
                or ref.manifest_profile_sha256 is None
                or (expected_kind is not None and ref.kind != expected_kind)
            ):
                raise ValueError("source receipt references must select exact JSON views")
        if len(self.selected_series_shape) != 1 or self.selected_series_shape[0] < 1:
            raise ValueError("source receipt must bind one non-empty univariate series")
        if any(type(size) is not int or size < 1 for size in self.selected_series_shape):
            raise ValueError("source receipt series shape must contain positive integers")
        for value in (
            self.selected_projection_schema_id,
            self.selected_projection_schema_version,
            self.series_id,
            self.unit_id,
            self.selected_field_id,
            self.selected_period_field_id,
        ):
            if value != value.strip():
                raise ValueError("source receipt identifiers must be clean strings")
        if self.selected_field_id == self.selected_period_field_id:
            raise ValueError("selected value and period fields must be distinct")
        return self


class _PublishedVintageReceipt(_SourceReceiptBase):
    """Typed evidence for one captured published data revision."""

    source_kind: Literal["published_vintage"]
    source_payload_ref: ArtifactRefModel
    source_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_capture_receipt_ref: ArtifactRefModel
    source_capture_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalized_records_ref: ArtifactRefModel
    normalized_records_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalized_records_schema_id: str = Field(min_length=1)
    normalized_records_schema_version: str = Field(min_length=1)
    source_adapter_id: str = Field(min_length=1)
    source_adapter_version: str = Field(min_length=1)
    source_adapter_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    calendar_years: tuple[Annotated[int, Field(strict=True)], ...] = Field(min_length=1)
    dataset_updated_on: date
    retrieved_at: datetime

    @model_validator(mode="after")
    def _validate_published_vintage(self) -> _PublishedVintageReceipt:
        ref = self.source_payload_ref
        if (
            ref.media_type != "application/octet-stream"
            or ref.manifest_profile_sha256 is None
            or str(ref.artifact_id) in {
                str(self.observed_source_ref.artifact_id),
                str(self.physical_data_ref.artifact_id),
            }
            or self.source_capture_receipt_ref.media_type != "application/octet-stream"
            or self.source_capture_receipt_ref.manifest_profile_sha256 is None
            or str(self.source_capture_receipt_ref.artifact_id) in {
                str(self.observed_source_ref.artifact_id),
                str(self.physical_data_ref.artifact_id),
                str(self.source_payload_ref.artifact_id),
            }
            or self.normalized_records_ref.media_type != "application/json"
            or self.normalized_records_ref.manifest_profile_sha256 is None
            or str(self.normalized_records_ref.artifact_id) in {
                str(self.observed_source_ref.artifact_id),
                str(self.physical_data_ref.artifact_id),
                str(self.source_payload_ref.artifact_id),
                str(self.source_capture_receipt_ref.artifact_id),
            }
            or self.calendar_years != tuple(sorted(set(self.calendar_years)))
            or len(self.calendar_years) != self.selected_series_shape[0]
            or self.calendar_years
            != tuple(range(self.calendar_years[0], self.calendar_years[0] + len(self.calendar_years)))
        ):
            raise ValueError("published receipt must bind contiguous ordered calendar rows")
        if any(type(year) is not int or year < 1 for year in self.calendar_years):
            raise ValueError("published receipt calendar years must be positive integers")
        if any(
            value != value.strip()
            for value in (
                self.source_adapter_id,
                self.source_adapter_version,
                self.normalized_records_schema_id,
                self.normalized_records_schema_version,
            )
        ):
            raise ValueError("published receipt schema and adapter identifiers must be clean")
        if self.retrieved_at.tzinfo is None or self.retrieved_at.utcoffset() is None:
            raise ValueError("published receipt retrieval time must be timezone-aware")
        if self.dataset_updated_on > self.retrieved_at.date():
            raise ValueError("dataset update cannot follow its recorded retrieval")
        return self


class _ControlledKnownProcessReceipt(_SourceReceiptBase):
    """Typed receipt for a separately scoped controlled known-process cohort."""

    source_kind: Literal["controlled_known_process"]
    process_spec_ref: ArtifactRefModel
    process_spec_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generator_id: str = Field(min_length=1)
    generator_version: str = Field(min_length=1)
    generator_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parameters_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    seed: int = Field(strict=True)
    logical_steps: tuple[Annotated[int, Field(strict=True)], ...] = Field(min_length=1)
    generated_at: datetime
    dataset_update_status: Literal["not_applicable"]
    dataset_update_reason: Literal["controlled_known_process"]
    retrieval_status: Literal["not_applicable"]
    retrieval_reason: Literal["controlled_known_process"]

    @model_validator(mode="after")
    def _validate_controlled_process(self) -> _ControlledKnownProcessReceipt:
        ref = self.process_spec_ref
        if (
            ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
            or str(ref.artifact_id) in {
                str(self.observed_source_ref.artifact_id),
                str(self.physical_data_ref.artifact_id),
            }
            or self.logical_steps != tuple(sorted(set(self.logical_steps)))
            or len(self.logical_steps) != self.selected_series_shape[0]
            or self.logical_steps
            != tuple(range(self.logical_steps[0], self.logical_steps[0] + len(self.logical_steps)))
        ):
            raise ValueError("controlled receipt must bind contiguous ordered process steps")
        if any(type(step) is not int or step < 0 for step in self.logical_steps):
            raise ValueError("controlled receipt logical steps must be non-negative integers")
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("controlled receipt generation time must be timezone-aware")
        return self


_RetrospectiveSourceReceipt = Annotated[
    _PublishedVintageReceipt | _ControlledKnownProcessReceipt,
    Field(discriminator="source_kind"),
]
_RETROSPECTIVE_SOURCE_RECEIPT_ADAPTER = TypeAdapter(_RetrospectiveSourceReceipt)


class _RetrospectiveForecastContext(BaseModel):
    """Private source-receipt selection and explicit policy-time limitation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_vintage_receipt_ref: ArtifactRefModel
    policy_effective_time_status: Literal["not_applicable"]
    policy_effective_time_reason: Literal[
        "no_policy_action_in_retrospective_predictive_screening"
    ]

    @model_validator(mode="after")
    def _validate_receipt_ref(self) -> _RetrospectiveForecastContext:
        ref = self.source_vintage_receipt_ref
        if (
            ref.kind != SOURCE_RECEIPT_KIND
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
        ):
            raise ValueError("retrospective screening requires an exact source-receipt view")
        return self


def _validate_common_forecast_owner_request(request: Any) -> None:
    """Validate the shared inputs for operational and retrospective owner calls."""

    if (request.value_data_profile_ref is None) != (request.value_data_unit_id is None):
        raise ValueError("value profile ref and selected unit must be supplied as a pair")
    if request.value_data_profile_ref is not None:
        if (
            request.value_data_profile_ref.kind != VALUE_DATA_PROFILE_KIND
            or request.value_data_profile_ref.media_type != "application/json"
            or request.value_data_profile_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("value profile ref must select an exact JSON manifest view")
        if (
            not request.value_data_unit_id
            or request.value_data_unit_id != request.value_data_unit_id.strip()
        ):
            raise ValueError("selected value profile unit must be a clean identifier")
        member = request.forecast_profile_member
        if (
            member is None
            or member.profile_ref != request.value_data_profile_ref
            or member.unit_id != request.value_data_unit_id
            or member.target_metric != request.target_metric
        ):
            raise ValueError("selected value profile member receipt is incomplete")
    elif request.forecast_profile_member is not None:
        raise ValueError("profile member receipt requires an exact selected profile")
    if request.target_metric != request.target_metric.strip():
        raise ValueError("target_metric must not have surrounding whitespace")
    if request.report_id != request.report_id.strip():
        raise ValueError("report_id must not have surrounding whitespace")
    if (request.model_spec_ref is None) != (request.policy_spec_ref is None):
        raise ValueError("model/policy specification refs must be supplied as a complete pair")
    if (
        request.model_spec_ref is not None
        and request.policy_spec_ref is not None
        and str(getattr(request.model_spec_ref, "artifact_id", request.model_spec_ref))
        == str(getattr(request.policy_spec_ref, "artifact_id", request.policy_spec_ref))
    ):
        raise ValueError("model/policy specification refs must be distinct artifacts")
    if request.method_params.horizon != request.split.horizon:
        raise ValueError("method horizon must match the explicit holdout horizon")
    seen: set[tuple[str, str]] = set()
    for item in request.manifest_inputs:
        role = item.role
        if not role or role != role.strip():
            raise ValueError("manifest input role must be a non-empty clean string")
        key = (str(item.artifact_id), role)
        if key in seen:
            raise ValueError("duplicate manifest input role/artifact pair")
        seen.add(key)


class CalibrationRuleArtifact(BaseModel):
    """Strict internal v1 rule admitted by the ETS predictive owner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"]
    rule_id: Literal["rolling-origin-residual-conformal.v1"]
    rule_version: Literal["1.0"]
    estimand: Literal["predictive_interval_coverage"]
    algorithm: Literal["rolling_origin_residual_conformal"]
    nominal_coverage: float = Field(gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def _validate_nominal_coverage(self) -> CalibrationRuleArtifact:
        if not math.isfinite(self.nominal_coverage):
            raise ValueError("nominal_coverage must be finite")
        return self


class CalibrationRuleBinding(BaseModel):
    """Identity plus CAS artifact for the predictive calibration rule."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: Literal["rolling-origin-residual-conformal.v1"]
    artifact_ref: ArtifactRefModel

    @model_validator(mode="after")
    def _validate_identity(self) -> CalibrationRuleBinding:
        if self.artifact_ref.kind != CALIBRATION_RULE_KIND:
            raise ValueError(f"calibration rule artifact kind must be {CALIBRATION_RULE_KIND!r}")
        if self.artifact_ref.media_type != "application/json":
            raise ValueError("calibration rule artifact must use application/json")
        return self


class ForecastOwnerRequest(BaseModel):
    """Typed CAS-bound request for one empirical ETS predictive evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observed_source_ref: DataSnapshotRef
    value_data_profile_ref: ArtifactRefModel | None = None
    value_data_unit_id: str | None = None
    forecast_profile_member: ForecastProfileMemberV1 | None = None
    split: TrainHoldoutSplit
    target_metric: str = Field(min_length=1)
    method_fqn: Literal["forecasting.univariate.exponential_smoothing@1.0.0"] = METHOD_FQN
    method_params: ForecastMethodParams
    report_id: str = Field(min_length=1)
    estimand: Literal["predictive_interval_coverage"] = PREDICTIVE_INTERVAL_COVERAGE
    calibration_rule: CalibrationRuleBinding
    temporal_roles: ForecastTemporalRoles
    model_spec_ref: ArtifactRefModel | ArtifactID | None = None
    policy_spec_ref: ArtifactRefModel | ArtifactID | None = None
    manifest_inputs: tuple[InputRef, ...] = ()
    seed: int = 0

    @model_validator(mode="after")
    def _validate_request(self) -> ForecastOwnerRequest:
        _validate_common_forecast_owner_request(self)
        return self


class _RetrospectiveForecastOwnerRequest(BaseModel):
    """Private request variant that carries periods without fabricated instants."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observed_source_ref: DataSnapshotRef
    value_data_profile_ref: ArtifactRefModel | None = None
    value_data_unit_id: str | None = None
    forecast_profile_member: ForecastProfileMemberV1 | None = None
    split: TrainHoldoutSplit
    target_metric: str = Field(min_length=1)
    method_fqn: Literal["forecasting.univariate.exponential_smoothing@1.0.0"] = METHOD_FQN
    method_params: ForecastMethodParams
    report_id: str = Field(min_length=1)
    estimand: Literal["predictive_interval_coverage"] = PREDICTIVE_INTERVAL_COVERAGE
    calibration_rule: CalibrationRuleBinding
    retrospective_context: _RetrospectiveForecastContext
    source_unit_id: str = Field(min_length=1)
    model_spec_ref: ArtifactRefModel | ArtifactID | None = None
    policy_spec_ref: ArtifactRefModel | ArtifactID | None = None
    manifest_inputs: tuple[InputRef, ...] = ()
    seed: int = 0

    @model_validator(mode="after")
    def _validate_request(self) -> _RetrospectiveForecastOwnerRequest:
        _validate_common_forecast_owner_request(self)
        context = self.retrospective_context
        if self.source_unit_id != self.source_unit_id.strip():
            raise ValueError("retrospective source unit ID must be a clean identifier")
        if self.model_spec_ref is not None or self.policy_spec_ref is not None:
            raise ValueError("retrospective predictive screening cannot bind a policy action")
        if str(context.source_vintage_receipt_ref.artifact_id) == str(
            self.observed_source_ref.artifact_id
        ):
            raise ValueError("source-vintage receipt must be distinct from the data snapshot")
        if (
            self.value_data_unit_id is not None
            and self.value_data_unit_id != self.source_unit_id
        ):
            raise ValueError("retrospective source unit disagrees with selected value profile")
        receipt_id = str(context.source_vintage_receipt_ref.artifact_id)
        for item in self.manifest_inputs:
            if (
                str(item.artifact_id) == receipt_id
                and item.manifest_profile_sha256
                != context.source_vintage_receipt_ref.manifest_profile_sha256
            ):
                raise ValueError("manifest input selects a conflicting source-vintage profile")
        return self


class _ForecastOwnerResultFields(BaseModel):
    """Common persisted evidence fields shared by private and operational results."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    report_id: str
    method_fqn: str
    estimand: Literal["predictive_interval_coverage"]
    target_metric: str
    point_forecast: tuple[float, ...]
    predictive_intervals: tuple[tuple[float, float], ...]
    nominal_coverage: float
    coverage_numerator: int = Field(ge=0)
    coverage_denominator: int = Field(ge=1)
    empirical_coverage: float = Field(ge=0.0, le=1.0)
    empirical_suitability: Literal["supported", "limited", "blocked"]
    authority_scope: Literal["predictive_only"] = "predictive_only"
    bridge_status: Literal["bridge_pending"] = "bridge_pending"
    observed_source_ref: ArtifactRefModel
    value_data_profile_ref: ArtifactRefModel | None = None
    forecast_profile_member_ref: ArtifactRefModel | None = None
    training_slice_ref: ArtifactRefModel
    method_artifact_ref: ArtifactRefModel
    calibration_rule_ref: ArtifactRefModel
    uncertainty_bundle_ref: ForecastingUncertaintyBundleRef
    calibration_diagnostics_ref: ArtifactRefModel
    backtest_report_ref: BacktestReportRef
    model_spec_ref: ArtifactRefModel | None = None
    policy_spec_ref: ArtifactRefModel | None = None

    @property
    def numerator(self) -> int:
        """Return the recomputed empirical coverage numerator."""

        return self.coverage_numerator

    @property
    def denominator(self) -> int:
        """Return the recomputed empirical coverage denominator."""

        return self.coverage_denominator


class ForecastOwnerResult(_ForecastOwnerResultFields):
    """Persisted predictive evidence and recomputed held-out suitability."""

    temporal_roles: ForecastTemporalRoles


class _RetrospectiveForecastOwnerResult(_ForecastOwnerResultFields):
    """Persisted predictive evidence with the selected retrospective periods."""

    retrospective_context: _RetrospectiveForecastContext


def _input(ref: object, role: str) -> InputRef:
    """Create a lineage edge from the exact selected artifact view."""

    artifact_id = getattr(ref, "artifact_id", ref)
    profile = getattr(ref, "manifest_profile_sha256", None)
    return InputRef(
        artifact_id=str(artifact_id),
        role=role,
        manifest_profile_sha256=profile,
    )


def _manifest_for_profile(store: Any, artifact_id: ArtifactID, profile: str) -> Any:
    """Resolve one manifest profile, failing closed on unsupported non-default views."""

    resolver = getattr(store, "get_manifest_by_profile", None)
    if callable(resolver):
        manifest = resolver(artifact_id, profile)
    else:
        manifest = store.get_manifest(artifact_id)
        if artifact_manifest_profile_sha256(manifest) != profile:
            raise ValueError("artifact store cannot resolve the requested manifest profile")
    if (
        str(manifest.artifact_id) != str(artifact_id)
        or artifact_manifest_profile_sha256(manifest) != profile
    ):
        raise ValueError("selected artifact manifest does not match its profile reference")
    return manifest


def _ref_from_payload(value: object) -> ArtifactRefModel:
    return ArtifactRefModel.model_validate(normalize_artifact_ref(value))


def _exact_ref_key(ref: object) -> tuple[str, str, str, str | None]:
    """Return the artifact identity including its selected manifest profile."""

    normalized = _ref_from_payload(ref)
    return (
        str(normalized.artifact_id),
        normalized.kind,
        normalized.media_type,
        normalized.manifest_profile_sha256,
    )


def _require_exact_manifest_edges(
    manifest: Any,
    required_inputs: tuple[tuple[ArtifactRefModel, str], ...],
    *,
    artifact_label: str,
) -> None:
    """Require exact selected-profile manifest edges for a typed artifact role."""

    expected = sorted(
        (
            str(selected_ref.artifact_id),
            role,
            selected_ref.manifest_profile_sha256,
        )
        for selected_ref, role in required_inputs
    )
    actual = sorted(
        (str(item.artifact_id), item.role, item.manifest_profile_sha256)
        for item in manifest.inputs
    )
    if actual != expected:
        raise ValueError(f"{artifact_label} has non-exact dependency edges")


def _forecast_source_rows_sha256(periods: tuple[int, ...], values: object) -> str:
    """Hash the exact ordered period/value rows selected for retrospective scoring."""

    series = _finite_series(values, field="retrospective selected series")
    if len(periods) != int(series.size):
        raise ValueError("retrospective selected periods do not match the value rows")
    rows = [[period, float(value)] for period, value in zip(periods, series, strict=True)]
    encoded = json.dumps(
        rows,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _resolve_json(
    store: ArtifactStore,
    ref: object,
    *,
    expected_kind: str | None = None,
) -> tuple[ArtifactRefModel, Any]:
    """Resolve, content-verify, and decode one CAS JSON artifact."""

    normalized = _ref_from_payload(ref)
    if expected_kind is not None and normalized.kind != expected_kind:
        raise ValueError(
            f"artifact kind mismatch: expected {expected_kind!r}, got {normalized.kind!r}"
        )
    artifact_id = ArtifactID.model_validate(str(normalized.artifact_id))
    ir_store = _ensure_ir_artifact_store(store)
    if normalized.manifest_profile_sha256 is None:
        manifest = store.get_manifest(str(artifact_id))
        selected_profile = artifact_manifest_profile_sha256(manifest)
    else:
        selected_profile = normalized.manifest_profile_sha256
        manifest = _manifest_for_profile(ir_store, artifact_id, selected_profile)
    if str(manifest.artifact_id) != str(artifact_id):
        raise ValueError("artifact manifest identity does not match the requested reference")
    if manifest.kind != normalized.kind or manifest.media_type != normalized.media_type:
        raise ValueError("artifact reference is not content-bound to its CAS manifest")
    exact_ref = ArtifactRefModel.model_validate(
        {
            **normalized.model_dump(mode="python"),
            "manifest_profile_sha256": selected_profile,
        }
    )
    if _manifest_for_profile(ir_store, artifact_id, selected_profile) != manifest:
        raise ValueError("selected artifact manifest changed during resolution")
    return exact_ref, get_json_artifact(ir_store, exact_ref)


def _resolve_opaque_source_bytes(
    store: ArtifactStore,
    ref: object,
) -> tuple[ArtifactRefModel, bytes]:
    """Resolve one exact raw-source blob without applying the IR JSON codec."""

    normalized = _ref_from_payload(ref)
    if normalized.media_type != "application/octet-stream":
        raise ValueError("raw-source artifact must use the opaque byte media type")
    if normalized.manifest_profile_sha256 is None:
        raise ValueError("raw-source artifact selected profile is missing")
    artifact_id = ArtifactID.model_validate(str(normalized.artifact_id))
    ir_store = _ensure_ir_artifact_store(store)
    selected_profile = normalized.manifest_profile_sha256
    manifest = _manifest_for_profile(ir_store, artifact_id, selected_profile)
    if (
        str(manifest.artifact_id) != str(artifact_id)
        or manifest.kind != normalized.kind
        or manifest.media_type != normalized.media_type
        or _manifest_for_profile(ir_store, artifact_id, selected_profile) != manifest
    ):
        raise ValueError("raw-source selected manifest does not match its exact reference")
    exact_ref = ArtifactRefModel.model_validate(
        {
            **normalized.model_dump(mode="python"),
            "manifest_profile_sha256": selected_profile,
        }
    )
    raw_bytes = store.get_bytes(exact_ref)
    if hashlib.sha256(raw_bytes).hexdigest() != str(artifact_id).removeprefix("sha256:"):
        raise ValueError("raw-source bytes do not match their content address")
    return exact_ref, raw_bytes


def _resolve_input_ref(store: ArtifactStore, item: InputRef) -> InputRef:
    """Resolve one lineage edge without treating its role as artifact metadata."""

    artifact_id = ArtifactID.model_validate(str(item.artifact_id))
    ir_store = _ensure_ir_artifact_store(store)
    if item.manifest_profile_sha256 is None:
        manifest = store.get_manifest(str(artifact_id))
        profile = artifact_manifest_profile_sha256(manifest)
    else:
        profile = item.manifest_profile_sha256
        manifest = _manifest_for_profile(ir_store, artifact_id, profile)
    if str(manifest.artifact_id) != str(artifact_id):
        raise ValueError("manifest input identity does not match the requested artifact")
    selected_ref = ArtifactRefModel(
        artifact_id=artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=profile,
    )
    if _manifest_for_profile(ir_store, artifact_id, profile) != manifest:
        raise ValueError("selected input manifest changed during resolution")
    ir_store.get_bytes(selected_ref)
    return InputRef(
        artifact_id=artifact_id,
        role=item.role,
        manifest_profile_sha256=profile,
    )


def _resolve_spec_ref(
    store: ArtifactStore,
    reference: ArtifactRefModel | ArtifactID,
    *,
    role: Literal["model", "policy"],
    expected_kind: str,
) -> ArtifactRefModel:
    """Resolve one model/policy reference without downgrading a selected profile.

    An ``ArtifactID`` retains the legacy default-manifest behavior for direct
    owner callers. A full ``ArtifactRefModel`` must resolve through its exact
    profile and match its kind and media type before the owner reads bytes.
    """

    selected_input = reference if isinstance(reference, ArtifactRefModel) else None
    resolved_id = ArtifactID.model_validate(
        str(selected_input.artifact_id if selected_input is not None else reference)
    )
    ir_store = _ensure_ir_artifact_store(store)
    try:
        if selected_input is None:
            manifest = store.get_manifest(resolved_id)
        else:
            profile = selected_input.manifest_profile_sha256
            if profile is None:
                raise ValueError(f"{role} specification selected profile is missing")
            manifest = _manifest_for_profile(ir_store, resolved_id, profile)
    except FileNotFoundError as exc:
        raise ValueError(f"{role} specification CAS binding is missing") from exc
    if str(manifest.artifact_id) != str(resolved_id):
        raise ValueError(f"{role} specification manifest identity does not match the requested ID")
    if manifest.kind != expected_kind:
        raise ValueError(
            f"{role} specification manifest kind mismatch: "
            f"expected {expected_kind!r}, got {manifest.kind!r}"
        )
    if manifest.media_type != "application/json":
        raise ValueError(
            f"{role} specification manifest media type mismatch: "
            f"expected 'application/json', got {manifest.media_type!r}"
        )
    profile = artifact_manifest_profile_sha256(manifest)
    selected_ref = ArtifactRefModel(
        artifact_id=resolved_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=profile,
    )
    try:
        if _manifest_for_profile(ir_store, resolved_id, profile) != manifest:
            raise ValueError("selected specification manifest changed during resolution")
        if selected_input is not None and selected_ref != selected_input:
            raise ValueError(f"{role} specification selected reference does not match CAS")
        ir_store.get_bytes(selected_ref)
    except FileNotFoundError as exc:
        raise ValueError(f"{role} specification CAS bytes are missing") from exc
    return selected_ref


def _resolve_model_policy_pair(
    store: ArtifactStore,
    *,
    model_spec_ref: ArtifactRefModel | ArtifactID | None,
    policy_spec_ref: ArtifactRefModel | ArtifactID | None,
) -> tuple[ArtifactRefModel | None, ArtifactRefModel | None]:
    """Resolve a complete, distinct model/policy pair before derived writes."""

    if (model_spec_ref is None) != (policy_spec_ref is None):
        raise ValueError("model/policy specification refs must be supplied as a complete pair")
    if model_spec_ref is None and policy_spec_ref is None:
        return None, None
    if (
        model_spec_ref is not None
        and policy_spec_ref is not None
        and str(getattr(model_spec_ref, "artifact_id", model_spec_ref))
        == str(getattr(policy_spec_ref, "artifact_id", policy_spec_ref))
    ):
        raise ValueError("model/policy specification refs must be distinct artifacts")
    if model_spec_ref is None or policy_spec_ref is None:
        raise ValueError("model/policy specification refs must be supplied as a complete pair")
    return (
        _resolve_spec_ref(
            store,
            model_spec_ref,
            role="model",
            expected_kind=MODEL_SPEC_KIND,
        ),
        _resolve_spec_ref(
            store,
            policy_spec_ref,
            role="policy",
            expected_kind=POLICY_SPEC_KIND,
        ),
    )


def _finite_series(values: object, *, field: str) -> np.ndarray:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{field} must be a numeric sequence")
    try:
        array = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if array.ndim != 1 or array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError(f"{field} must be a non-empty finite vector")
    return array


def _finite_scalar(value: object, *, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not math.isfinite(numeric):
        raise ValueError(f"{field} must be finite")
    return numeric


def _interval_scalar(value: object, *, field: str) -> float:
    if isinstance(value, (list, tuple, np.ndarray)):
        array = np.asarray(value, dtype=float).reshape(-1)
        if array.size != 1:
            raise ValueError(f"{field} must be scalar for the univariate owner")
        value = array[0]
    return _finite_scalar(value, field=field)


def _rule_contract(
    binding: CalibrationRuleBinding,
    payload: object,
    *,
    estimand: str,
) -> CalibrationRuleArtifact:
    if not isinstance(payload, Mapping):
        raise ValueError("calibration rule artifact must decode to an object")
    try:
        rule = CalibrationRuleArtifact.model_validate(payload)
    except (TypeError, ValueError, ValidationError) as exc:
        raise ValueError("calibration rule artifact violates the supported v1 contract") from exc
    if rule.rule_id != binding.rule_id:
        raise ValueError("calibration rule artifact identity does not match the request")
    if rule.estimand != estimand:
        raise ValueError("calibration rule estimand does not match the request")
    return rule


def _method_artifact(
    method_class: type,
    *,
    params: ForecastMethodParams,
    train: np.ndarray,
    backend: ComputeBackend,
) -> MethodArtifact:
    """Build a method artifact from the executed class and actual input shape."""

    specialization = Specialization(
        method_fqn=METHOD_FQN,
        static_params_hash=compute_static_params_hash(params.model_dump(mode="python")),
        input_shapes=(
            (
                "series",
                ShapeSpec(
                    shape=tuple(int(item) for item in train.shape),
                    dtype=str(train.dtype),
                ),
            ),
        ),
        backend=BackendSpec(
            platform=backend.value,
            device_count=1,
            precision=str(train.dtype),
            device_kinds=("cpu",),
        ),
        jit_enabled=False,
    )
    return MethodArtifact.from_method(method_class, specialization)


def _expected_input_pairs(
    *,
    observed_source_ref: ArtifactRefModel,
    observed_data_ref: ArtifactRefModel,
    calibration_rule_ref: ArtifactRefModel,
    training_slice_ref: ArtifactRefModel,
    method_artifact_ref: ArtifactRefModel,
    uncertainty_bundle_ref: ForecastingUncertaintyBundleRef,
    calibration_diagnostics_ref: ArtifactRefModel,
    model_spec_ref: ArtifactRefModel | None,
    policy_spec_ref: ArtifactRefModel | None,
    value_data_profile_ref: ArtifactRefModel | None,
    forecast_profile_member_ref: ArtifactRefModel | None,
    source_vintage_receipt_ref: ArtifactRefModel | None = None,
) -> list[InputRef]:
    required = [
        _input(observed_source_ref, "observed_source"),
        _input(observed_data_ref, "observed_data"),
        _input(calibration_rule_ref, "calibration_rule"),
        _input(training_slice_ref, "training_slice"),
        _input(method_artifact_ref, "method_artifact"),
        _input(uncertainty_bundle_ref, "uncertainty_bundle"),
        _input(calibration_diagnostics_ref, "calibration_diagnostics"),
    ]
    if model_spec_ref is not None and policy_spec_ref is not None:
        required.extend(
            [
                _input(model_spec_ref, "model_spec"),
                _input(policy_spec_ref, "policy_spec"),
            ]
        )
    if (value_data_profile_ref is None) != (forecast_profile_member_ref is None):
        raise ValueError("value profile and member receipt must be supplied as a pair")
    if value_data_profile_ref is not None and forecast_profile_member_ref is not None:
        required.extend(
            [
                _input(value_data_profile_ref, "value_data_profile"),
                _input(forecast_profile_member_ref, "forecast_profile_member"),
            ]
        )
    if source_vintage_receipt_ref is not None:
        required.append(_input(source_vintage_receipt_ref, "source_vintage_receipt"))
    return required


class ForecastOwner:
    """Own one real ETS -> predictive calibration -> backtest artifact chain."""

    def __init__(self, store: FileSystemCAS) -> None:
        self._store = store

    def run(self, request: ForecastOwnerRequest) -> ForecastOwnerResult:
        """Execute and persist one fail-closed predictive owner result."""

        result = self._run(request)
        if not isinstance(result, ForecastOwnerResult):
            raise RuntimeError("operational forecast owner returned a retrospective result")
        return result

    def _run_retrospective(
        self,
        request: _RetrospectiveForecastOwnerRequest,
    ) -> _RetrospectiveForecastOwnerResult:
        """Execute internal predictive screening with periods and no invented instants."""

        result = self._run(request)
        if not isinstance(result, _RetrospectiveForecastOwnerResult):
            raise RuntimeError("retrospective forecast owner returned an operational result")
        return result

    def _run(
        self,
        request: ForecastOwnerRequest | _RetrospectiveForecastOwnerRequest,
    ) -> ForecastOwnerResult | _RetrospectiveForecastOwnerResult:
        if isinstance(request, ForecastOwnerRequest):
            retrospective_context = None
            source_vintage_receipt_ref = None
            temporal_metadata = {
                "temporal_roles": request.temporal_roles.model_dump(mode="json")
            }
        else:
            retrospective_context = request.retrospective_context
            source_vintage_receipt_ref = retrospective_context.source_vintage_receipt_ref
            temporal_metadata = {
                "retrospective_context": retrospective_context.model_dump(mode="json")
            }

        model_spec_ref, policy_spec_ref = _resolve_model_policy_pair(
            self._store,
            model_spec_ref=request.model_spec_ref,
            policy_spec_ref=request.policy_spec_ref,
        )

        observed_source_ref, _snapshot_payload = _resolve_json(
            self._store,
            request.observed_source_ref,
            expected_kind="fabric.data_snapshot",
        )
        try:
            from polisyos.core.artifacts import ArtifactRef as CoreArtifactRef
            from polisyos.core.artifacts import validate_core_model_json_artifact

            snapshot = validate_core_model_json_artifact(
                DataSnapshot,
                self._store,
                CoreArtifactRef.model_validate(observed_source_ref.model_dump(mode="python")),
            )
        except Exception as exc:
            raise ValueError("observed source snapshot is malformed") from exc
        observed_data_ref, observed_payload = _resolve_json(self._store, snapshot.data_ref)
        if not isinstance(observed_payload, Mapping):
            raise ValueError("observed source data must be a JSON object keyed by metric")
        values = _finite_series(
            observed_payload.get(request.target_metric), field="observed source"
        )
        value_data_profile_ref = request.value_data_profile_ref
        profile_member = request.forecast_profile_member
        if value_data_profile_ref is not None:
            if profile_member is None or request.value_data_unit_id is None:
                raise ValueError("selected value profile member receipt is incomplete")
            if (
                profile_member.profile_ref != value_data_profile_ref
                or profile_member.unit_id != request.value_data_unit_id
                or profile_member.target_metric != request.target_metric
                or profile_member.observed_source_ref != observed_source_ref
                or profile_member.observed_data_ref != observed_data_ref
                or profile_member.row_count != int(values.size)
                or forecast_profile_observed_series_sha256(values.tolist())
                != profile_member.observed_series_sha256
            ):
                raise ValueError(
                    "selected profile member does not bind the resolved observed series"
                )
        elif profile_member is not None:
            raise ValueError("profile member receipt requires an exact selected profile")
        if request.split.holdout_end > values.size:
            raise ValueError("explicit train/holdout split exceeds observed source length")
        if request.split.train_end < _MIN_TRAIN_OBSERVATIONS:
            raise ValueError("training slice is too short for empirical ETS calibration")
        if retrospective_context is not None:
            resolved_vintage_ref, receipt_payload = _resolve_json(
                self._store,
                retrospective_context.source_vintage_receipt_ref,
                expected_kind=SOURCE_RECEIPT_KIND,
            )
            if resolved_vintage_ref != retrospective_context.source_vintage_receipt_ref:
                raise ValueError("source-vintage receipt did not resolve to its exact selected view")
            try:
                source_receipt = _RETROSPECTIVE_SOURCE_RECEIPT_ADAPTER.validate_python(
                    receipt_payload
                )
            except (TypeError, ValueError, ValidationError) as exc:
                raise ValueError("source-vintage receipt violates its strict versioned schema") from exc
            receipt_profile = resolved_vintage_ref.manifest_profile_sha256
            if receipt_profile is None:
                raise ValueError("source-vintage receipt selected profile is missing")
            receipt_manifest = _manifest_for_profile(
                _ensure_ir_artifact_store(self._store),
                ArtifactID.model_validate(str(resolved_vintage_ref.artifact_id)),
                receipt_profile,
            )
            if receipt_manifest.artifact_schema is None or (
                receipt_manifest.artifact_schema.name,
                receipt_manifest.artifact_schema.version,
            ) != (SOURCE_RECEIPT_SCHEMA, SOURCE_RECEIPT_SCHEMA_VERSION):
                raise ValueError("source-vintage receipt manifest has the wrong schema")
            snapshot_profile = observed_source_ref.manifest_profile_sha256
            if snapshot_profile is None:
                raise ValueError("observed source snapshot selected profile is missing")
            snapshot_manifest = _manifest_for_profile(
                _ensure_ir_artifact_store(self._store),
                ArtifactID.model_validate(str(observed_source_ref.artifact_id)),
                snapshot_profile,
            )
            _require_exact_manifest_edges(
                snapshot_manifest,
                ((observed_data_ref, "physical_data"),),
                artifact_label="observed source snapshot",
            )
            expected_receipt_inputs = [
                (source_receipt.observed_source_ref, "observed_source"),
                (source_receipt.physical_data_ref, "physical_data"),
            ]
            if isinstance(source_receipt, _PublishedVintageReceipt):
                expected_receipt_inputs.append(
                    (source_receipt.source_payload_ref, "source_payload")
                )
                expected_receipt_inputs.append(
                    (source_receipt.source_capture_receipt_ref, "source_capture_receipt")
                )
                expected_receipt_inputs.append(
                    (source_receipt.normalized_records_ref, "normalized_records")
                )
                source_payload_ref, payload_bytes = _resolve_opaque_source_bytes(
                    self._store,
                    source_receipt.source_payload_ref,
                )
                if (
                    source_payload_ref != source_receipt.source_payload_ref
                    or hashlib.sha256(payload_bytes).hexdigest()
                    != source_receipt.source_payload_sha256
                ):
                    raise ValueError("published receipt raw-source digest does not match CAS bytes")
                capture_receipt_ref, capture_receipt_bytes = _resolve_opaque_source_bytes(
                    self._store,
                    source_receipt.source_capture_receipt_ref,
                )
                if (
                    capture_receipt_ref != source_receipt.source_capture_receipt_ref
                    or hashlib.sha256(capture_receipt_bytes).hexdigest()
                    != source_receipt.source_capture_receipt_sha256
                ):
                    raise ValueError(
                        "published capture-receipt digest does not match CAS bytes"
                    )
                normalized_records_ref, normalized_records_payload = _resolve_json(
                    self._store,
                    source_receipt.normalized_records_ref,
                )
                normalized_records_bytes = self._store.get_bytes(normalized_records_ref)
                normalized_records_manifest = _manifest_for_profile(
                    _ensure_ir_artifact_store(self._store),
                    ArtifactID.model_validate(str(normalized_records_ref.artifact_id)),
                    normalized_records_ref.manifest_profile_sha256,
                )
                _require_exact_manifest_edges(
                    normalized_records_manifest,
                    ((source_receipt.source_payload_ref, "raw_source_payload"),),
                    artifact_label="published normalized records",
                )
                normalized_records_schema = normalized_records_manifest.artifact_schema
                if (
                    normalized_records_ref != source_receipt.normalized_records_ref
                    or hashlib.sha256(normalized_records_bytes).hexdigest()
                    != source_receipt.normalized_records_sha256
                    or not isinstance(normalized_records_payload, list)
                    or normalized_records_schema is None
                    or (
                        normalized_records_schema.name,
                        normalized_records_schema.version,
                    )
                    != (
                        source_receipt.normalized_records_schema_id,
                        source_receipt.normalized_records_schema_version,
                    )
                ):
                    raise ValueError(
                        "published normalized-record source does not match its receipt"
                    )
                selected_periods = source_receipt.calendar_years
                period_kind = "calendar_year"
                source_time_metadata = {
                    "dataset_updated_on": source_receipt.dataset_updated_on.isoformat(),
                    "retrieved_at": source_receipt.retrieved_at.isoformat(),
                    "dataset_update_status": "observed",
                    "retrieval_status": "observed",
                    "source_adapter_id": source_receipt.source_adapter_id,
                    "source_adapter_version": source_receipt.source_adapter_version,
                    "source_adapter_sha256": source_receipt.source_adapter_sha256,
                    "source_payload_ref": source_receipt.source_payload_ref.model_dump(
                        mode="json"
                    ),
                    "source_payload_sha256": source_receipt.source_payload_sha256,
                    "source_capture_receipt_ref": (
                        source_receipt.source_capture_receipt_ref.model_dump(mode="json")
                    ),
                    "source_capture_receipt_sha256": (
                        source_receipt.source_capture_receipt_sha256
                    ),
                    "normalized_records_ref": source_receipt.normalized_records_ref.model_dump(
                        mode="json"
                    ),
                    "normalized_records_sha256": source_receipt.normalized_records_sha256,
                    "normalized_records_schema_id": (
                        source_receipt.normalized_records_schema_id
                    ),
                    "normalized_records_schema_version": (
                        source_receipt.normalized_records_schema_version
                    ),
                }
            else:
                expected_receipt_inputs.append((source_receipt.process_spec_ref, "process_spec"))
                process_spec_ref, process_spec_payload = _resolve_json(
                    self._store,
                    source_receipt.process_spec_ref,
                )
                process_spec_bytes = self._store.get_bytes(process_spec_ref)
                process_parameters = (
                    process_spec_payload.get("parameters")
                    if isinstance(process_spec_payload, Mapping)
                    else None
                )
                try:
                    process_parameters_digest = hashlib.sha256(
                        json.dumps(
                            process_parameters,
                            sort_keys=True,
                            separators=(",", ":"),
                        ensure_ascii=False,
                            allow_nan=False,
                        ).encode("utf-8")
                    ).hexdigest()
                except (TypeError, ValueError):
                    process_parameters_digest = None
                process_steps = (
                    process_spec_payload.get("logical_steps")
                    if isinstance(process_spec_payload, Mapping)
                    else None
                )
                if (
                    process_spec_ref != source_receipt.process_spec_ref
                    or hashlib.sha256(process_spec_bytes).hexdigest()
                    != source_receipt.process_spec_sha256
                    or not isinstance(process_spec_payload, Mapping)
                    or process_spec_payload.get("schema_version") != "1.0"
                    or process_spec_payload.get("generator_id") != source_receipt.generator_id
                    or process_spec_payload.get("generator_version")
                    != source_receipt.generator_version
                    or process_spec_payload.get("generator_sha256")
                    != source_receipt.generator_sha256
                    or process_parameters_digest != source_receipt.parameters_sha256
                    or type(process_spec_payload.get("seed")) is not int
                    or process_spec_payload.get("seed") != source_receipt.seed
                    or not isinstance(process_steps, (list, tuple))
                    or any(type(step) is not int for step in process_steps)
                    or tuple(process_steps) != source_receipt.logical_steps
                ):
                    raise ValueError(
                        "controlled-process specification does not match its receipt"
                    )
                selected_periods = source_receipt.logical_steps
                period_kind = "controlled_step"
                source_time_metadata = {
                    "generated_at": source_receipt.generated_at.isoformat(),
                    "dataset_update_status": source_receipt.dataset_update_status,
                    "dataset_update_reason": source_receipt.dataset_update_reason,
                    "retrieval_status": source_receipt.retrieval_status,
                    "retrieval_reason": source_receipt.retrieval_reason,
                }
            _require_exact_manifest_edges(
                receipt_manifest,
                tuple(expected_receipt_inputs),
                artifact_label="source-vintage receipt",
            )
            if observed_data_ref.manifest_profile_sha256 is None:
                raise ValueError("normalized data selected profile is missing")
            data_manifest = _manifest_for_profile(
                _ensure_ir_artifact_store(self._store),
                ArtifactID.model_validate(str(observed_data_ref.artifact_id)),
                observed_data_ref.manifest_profile_sha256,
            )
            data_schema = data_manifest.artifact_schema
            if isinstance(source_receipt, _PublishedVintageReceipt):
                _require_exact_manifest_edges(
                    data_manifest,
                    ((source_receipt.normalized_records_ref, "normalized_records"),),
                    artifact_label="published selected projection",
                )
            if data_schema is None or (
                data_schema.name,
                data_schema.version,
            ) != (
                source_receipt.selected_projection_schema_id,
                source_receipt.selected_projection_schema_version,
            ):
                raise ValueError("source receipt does not match the normalized data schema")
            raw_periods = observed_payload.get(source_receipt.selected_period_field_id)
            if not isinstance(raw_periods, (list, tuple)) or any(
                type(period) is not int for period in raw_periods
            ):
                raise ValueError("selected source periods are missing or malformed")
            if tuple(raw_periods) != selected_periods:
                raise ValueError("source receipt periods do not match normalized source rows")
            if (
                _exact_ref_key(source_receipt.observed_source_ref)
                != _exact_ref_key(observed_source_ref)
                or _exact_ref_key(source_receipt.physical_data_ref)
                != _exact_ref_key(observed_data_ref)
                or source_receipt.series_id != request.target_metric
                or source_receipt.unit_id != request.source_unit_id
                or source_receipt.selected_field_id != request.target_metric
                or source_receipt.selected_series_shape != (int(values.size),)
                or source_receipt.selected_series_sha256
                != forecast_profile_observed_series_sha256(values.tolist())
                or source_receipt.selected_rows_sha256
                != _forecast_source_rows_sha256(selected_periods, values.tolist())
                or len(selected_periods) != int(values.size)
            ):
                raise ValueError("source-vintage receipt does not bind the selected rows")
            temporal_metadata = {
                "retrospective_context": {
                    **retrospective_context.model_dump(mode="json"),
                    "source_kind": source_receipt.source_kind,
                    "period_kind": period_kind,
                    "observation_periods": list(selected_periods),
                    "logical_origin_period": selected_periods[request.split.train_end - 1],
                    "target_periods": list(
                        selected_periods[request.split.holdout_start : request.split.holdout_end]
                    ),
                    "series_id": source_receipt.series_id,
                    "unit_id": source_receipt.unit_id,
                    "selected_field_id": source_receipt.selected_field_id,
                    "selected_series_shape": list(source_receipt.selected_series_shape),
                    "selected_series_sha256": source_receipt.selected_series_sha256,
                    "selected_projection_schema_id": (
                        source_receipt.selected_projection_schema_id
                    ),
                    "selected_projection_schema_version": (
                        source_receipt.selected_projection_schema_version
                    ),
                    **source_time_metadata,
                }
            }

        calibration_rule_ref, rule_payload = _resolve_json(
            self._store,
            request.calibration_rule.artifact_ref,
            expected_kind=CALIBRATION_RULE_KIND,
        )
        calibration_rule = _rule_contract(
            request.calibration_rule,
            rule_payload,
            estimand=request.estimand,
        )
        nominal_coverage = calibration_rule.nominal_coverage

        train = values[request.split.train_start : request.split.train_end]
        holdout = values[request.split.holdout_start : request.split.holdout_end]
        if train.size < _MIN_TRAIN_OBSERVATIONS or holdout.size != request.split.horizon:
            raise ValueError("train/holdout data does not satisfy the explicit split")

        registry = MethodRegistry.get_instance()
        ensure_forecasting_methods_registered(registry)
        method_class = registry.get(request.method_fqn)
        if method_class.signature.fqn != METHOD_FQN:
            raise ValueError("resolved method does not match the exact ETS owner FQN")

        params = request.method_params.model_dump(mode="python")
        dispatcher_result = MethodDispatcher.get_instance().dispatch(
            method_class=method_class,
            signature=method_class.signature,
            state={
                "series": train,
                "artifact_store": self._store,
                "target_id": request.target_metric,
                "calibration_nominal_coverage": nominal_coverage,
            },
            params=params,
            seed=request.seed,
        )
        if dispatcher_result.reproducibility.backend is not ComputeBackend.NUMPY:
            raise ValueError("ETS owner requires its declared NumPy execution backend")
        output = dispatcher_result.output
        if not isinstance(output, Mapping):
            raise ValueError("ETS owner output must be a mapping")
        result_payload = output.get("result")
        if not isinstance(result_payload, Mapping):
            raise ValueError("ETS owner result payload is missing")
        raw_forecast = result_payload.get("forecast")
        if (
            not isinstance(raw_forecast, (list, tuple))
            or len(raw_forecast) != request.split.horizon
        ):
            raise ValueError("ETS forecast horizon does not match the explicit holdout")
        point_forecast = tuple(
            _finite_scalar(value, field="point forecast") for value in raw_forecast
        )

        raw_bundle = output.get("forecasting_uncertainty_bundle")
        try:
            bundle = (
                raw_bundle
                if isinstance(raw_bundle, ForecastingUncertaintyBundle)
                else ForecastingUncertaintyBundle.model_validate(raw_bundle)
            )
        except Exception as exc:
            raise ValueError("ETS output did not contain a valid uncertainty bundle") from exc
        if bundle.method_fqn != METHOD_FQN:
            raise ValueError("uncertainty bundle method identity is not content-bound")
        if bundle.target_id != request.target_metric:
            raise ValueError("uncertainty bundle target identity disagrees with the request")
        if not math.isclose(bundle.nominal_coverage, nominal_coverage, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("uncertainty bundle nominal coverage disagrees with the rule artifact")
        if (
            bundle.interval_semantics
            is not ForecastIntervalSemantics.CONFORMALIZED_PREDICTION_INTERVAL
        ):
            raise ValueError("ETS owner requires rolling-origin predictive intervals")

        intervals_by_horizon = {item.horizon: item for item in bundle.prediction_interval}
        if set(intervals_by_horizon) != set(range(1, request.split.horizon + 1)):
            raise ValueError("uncertainty bundle horizons do not match the explicit holdout")
        predictive_intervals: list[tuple[float, float]] = []
        for horizon in range(1, request.split.horizon + 1):
            interval = intervals_by_horizon[horizon]
            interval_point = _interval_scalar(interval.point, field="predictive interval point")
            if not math.isclose(
                interval_point,
                point_forecast[horizon - 1],
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ValueError("predictive interval point disagrees with the ETS forecast")
            lower = _interval_scalar(interval.lower, field="predictive interval lower")
            upper = _interval_scalar(interval.upper, field="predictive interval upper")
            if lower > upper:
                raise ValueError("predictive interval lower bound exceeds upper bound")
            predictive_intervals.append((lower, upper))
        if any(
            interval.sample_count is None or interval.sample_count < 1
            for interval in bundle.prediction_interval
        ):
            raise ValueError("ETS predictive intervals lack rolling-origin observations")

        bundle = bundle.model_copy(
            update={
                "metadata": {
                    **bundle.metadata,
                    "target_metric": request.target_metric,
                    "estimand": request.estimand,
                    "authority_scope": "predictive_only",
                    "bridge_status": "bridge_pending",
                    **temporal_metadata,
                },
            }
        )

        forecast_profile_member_ref: ArtifactRefModel | None = None
        if profile_member is not None and value_data_profile_ref is not None:
            forecast_profile_member_ref = _ref_from_payload(
                put_json_artifact(
                    _ensure_ir_artifact_store(self._store),
                    profile_member.model_dump(mode="json"),
                    kind=FORECAST_PROFILE_MEMBER_KIND,
                    schema_name=FORECAST_PROFILE_MEMBER_SCHEMA,
                    schema_version=FORECAST_PROFILE_MEMBER_SCHEMA_VERSION,
                    inputs=[
                        _input(value_data_profile_ref, "value_data_profile"),
                        _input(profile_member.source_projection_ref, "activated_source_projection"),
                        _input(observed_source_ref, "observed_source"),
                        _input(observed_data_ref, "observed_data"),
                    ],
                    canon_spec=CanonSpec(forbid_floats=False),
                    return_selected_profile=True,
                )
            )

        training_slice_ref = _ref_from_payload(
            put_json_artifact(
                _ensure_ir_artifact_store(self._store),
                {
                    "schema_version": "1.0",
                    "source_ref": observed_source_ref.model_dump(mode="json"),
                    "observed_data_ref": observed_data_ref.model_dump(mode="json"),
                    "target_metric": request.target_metric,
                    "split": request.split.model_dump(mode="json"),
                    "method_fqn": request.method_fqn,
                    "method_params": request.method_params.model_dump(mode="json"),
                    "values": train.tolist(),
                    **temporal_metadata,
                    "authority_scope": "predictive_only",
                    "profile_join_status": (
                        "joined_candidate"
                        if value_data_profile_ref is not None
                        else "profileless_legacy"
                    ),
                    **(
                        {}
                        if value_data_profile_ref is None
                        else {
                            "value_data_profile_ref": value_data_profile_ref.model_dump(
                                mode="json"
                            ),
                            "forecast_profile_member_ref": forecast_profile_member_ref.model_dump(
                                mode="json"
                            ),
                        }
                    ),
                },
                kind="ir.forecast_training_slice",
                schema_name="polisyos.ir.ForecastTrainingSlice",
                schema_version="1.0",
                inputs=[
                    _input(observed_source_ref, "observed_source"),
                    _input(observed_data_ref, "observed_data"),
                    *(
                        []
                        if value_data_profile_ref is None
                        else [
                            _input(value_data_profile_ref, "value_data_profile"),
                            _input(forecast_profile_member_ref, "forecast_profile_member"),
                        ]
                    ),
                    *(
                        []
                        if source_vintage_receipt_ref is None
                        else [_input(source_vintage_receipt_ref, "source_vintage_receipt")]
                    ),
                ],
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
        )
        method_artifact = _method_artifact(
            method_class,
            params=request.method_params,
            train=train,
            backend=dispatcher_result.reproducibility.backend,
        )
        method_artifact_ref = _ref_from_payload(
            store_method_artifact(self._store, method_artifact, return_selected_profile=True)
        )

        bundle_ref = persist_forecasting_uncertainty_bundle(
            _ensure_ir_artifact_store(self._store),
            bundle,
            inputs=[
                _input(observed_source_ref, "observed_source"),
                _input(observed_data_ref, "observed_data"),
                _input(training_slice_ref, "training_slice"),
                _input(method_artifact_ref, "method_artifact"),
                _input(calibration_rule_ref, "calibration_rule"),
                *(
                    []
                    if source_vintage_receipt_ref is None
                    else [_input(source_vintage_receipt_ref, "source_vintage_receipt")]
                ),
                *(
                    []
                    if value_data_profile_ref is None
                    else [
                        _input(value_data_profile_ref, "value_data_profile"),
                        _input(forecast_profile_member_ref, "forecast_profile_member"),
                    ]
                ),
            ],
            return_selected_profile=True,
        )
        persisted_bundle = load_forecasting_uncertainty_bundle(
            _ensure_ir_artifact_store(self._store), bundle_ref
        )
        if persisted_bundle.method_fqn != METHOD_FQN:
            raise ValueError("persisted uncertainty bundle lost its method binding")
        if persisted_bundle.target_id != request.target_metric:
            raise ValueError("persisted uncertainty bundle lost its target binding")
        if any(
            persisted_bundle.metadata.get(key) != value
            for key, value in temporal_metadata.items()
        ):
            raise ValueError("persisted uncertainty bundle lost its temporal context")
        pit_ref = persisted_bundle.coverage_diagnostic.pit_summary_ref
        if pit_ref is None:
            raise ValueError("ETS uncertainty bundle lacks persisted PIT evidence")
        _, pit_payload = _resolve_json(
            self._store,
            pit_ref,
            expected_kind="ir.forecasting_pit_summary",
        )
        if (
            not isinstance(pit_payload, Mapping)
            or pit_payload.get("target_id") != request.target_metric
        ):
            raise ValueError("persisted PIT evidence lost its target binding")

        calibration = evaluate_continuous(
            y_true=holdout.tolist(),
            intervals={nominal_coverage: predictive_intervals},
            levels=(nominal_coverage,),
            strict=True,
        )
        coverage_numerator = sum(
            lower <= actual <= upper
            for actual, (lower, upper) in zip(holdout.tolist(), predictive_intervals, strict=True)
        )
        coverage_denominator = len(predictive_intervals)
        if coverage_denominator == 0:
            raise ValueError("predictive calibration denominator must be non-zero")
        empirical_coverage = coverage_numerator / coverage_denominator
        interval_meta = calibration.metadata.get("interval_coverage", {})
        if not isinstance(interval_meta, Mapping):
            raise ValueError("calibration diagnostics lack interval-coverage metadata")
        interval_bins = calibration.curves.get("interval_coverage")
        n_comparisons = interval_meta.get("n_comparisons")
        if (
            interval_meta.get("status") != "evaluated"
            or not isinstance(n_comparisons, int)
            or isinstance(n_comparisons, bool)
            or n_comparisons <= 0
            or not isinstance(interval_bins, (list, tuple))
            or len(interval_bins) != 1
            or n_comparisons != len(interval_bins)
        ):
            raise ValueError(
                "calibration diagnostics did not evaluate exactly one interval-coverage curve"
            )
        if calibration.metrics.n_obs != coverage_denominator:
            raise ValueError("calibration diagnostics observation count disagrees with holdout")
        if any(item.count != coverage_denominator for item in interval_bins):
            raise ValueError("calibration diagnostics bin count disagrees with holdout")
        selected_bin = interval_bins[0]
        if (
            selected_bin.mean_observed is None
            or not math.isclose(
                selected_bin.mean_observed,
                empirical_coverage,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            or selected_bin.mean_predicted is None
            or not math.isclose(
                selected_bin.mean_predicted,
                nominal_coverage,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        ):
            raise ValueError("calibration diagnostics curve values disagree with holdout")

        calibration_payload = calibration.model_dump(mode="json")
        calibration_payload["metadata"] = {
            **calibration_payload.get("metadata", {}),
            "report_id": request.report_id,
            "target_metric": request.target_metric,
            "estimand": request.estimand,
            "authority_scope": "predictive_only",
            "bridge_status": "bridge_pending",
            "coverage_numerator": coverage_numerator,
            "coverage_denominator": coverage_denominator,
            "nominal_coverage": nominal_coverage,
            **temporal_metadata,
            "profile_join_status": (
                "joined_candidate" if value_data_profile_ref is not None else "profileless_legacy"
            ),
            **(
                {}
                if value_data_profile_ref is None
                else {
                    "value_data_profile_ref": value_data_profile_ref.model_dump(mode="json"),
                    "forecast_profile_member_ref": forecast_profile_member_ref.model_dump(
                        mode="json"
                    ),
                }
            ),
        }
        calibration_diagnostics_ref = _ref_from_payload(
            put_json_artifact(
                _ensure_ir_artifact_store(self._store),
                calibration_payload,
                kind="ir.calibration_diagnostics_report",
                schema_name=CalibrationDiagnosticsReport.contract_id,
                schema_version="1.0",
                inputs=[
                    _input(observed_source_ref, "observed_source"),
                    _input(observed_data_ref, "observed_data"),
                    _input(training_slice_ref, "training_slice"),
                    _input(method_artifact_ref, "method_artifact"),
                    _input(calibration_rule_ref, "calibration_rule"),
                    _input(bundle_ref, "uncertainty_bundle"),
                    *(
                        []
                        if source_vintage_receipt_ref is None
                        else [_input(source_vintage_receipt_ref, "source_vintage_receipt")]
                    ),
                    *(
                        []
                        if value_data_profile_ref is None
                        else [
                            _input(value_data_profile_ref, "value_data_profile"),
                            _input(forecast_profile_member_ref, "forecast_profile_member"),
                        ]
                    ),
                ],
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
        )

        uncertainty_bundle_ref = bundle_ref
        required_inputs = _expected_input_pairs(
            observed_source_ref=observed_source_ref,
            observed_data_ref=observed_data_ref,
            calibration_rule_ref=calibration_rule_ref,
            training_slice_ref=training_slice_ref,
            method_artifact_ref=method_artifact_ref,
            uncertainty_bundle_ref=uncertainty_bundle_ref,
            calibration_diagnostics_ref=calibration_diagnostics_ref,
            model_spec_ref=model_spec_ref,
            policy_spec_ref=policy_spec_ref,
            value_data_profile_ref=value_data_profile_ref,
            forecast_profile_member_ref=forecast_profile_member_ref,
            source_vintage_receipt_ref=source_vintage_receipt_ref,
        )
        resolved_manifest_inputs = [
            _resolve_input_ref(self._store, item) for item in request.manifest_inputs
        ]
        report_inputs = list(required_inputs)
        declared_edges = {
            (str(item.artifact_id), item.role, item.manifest_profile_sha256)
            for item in report_inputs
        }
        for item in resolved_manifest_inputs:
            edge = (str(item.artifact_id), item.role, item.manifest_profile_sha256)
            if edge not in declared_edges:
                report_inputs.append(item)
                declared_edges.add(edge)
        required_edges = {
            (str(item.artifact_id), item.role, item.manifest_profile_sha256)
            for item in required_inputs
        }
        if not required_edges.issubset(declared_edges):
            missing = sorted(required_edges - declared_edges)
            raise ValueError(
                f"manifest inputs omit required exact-view content bindings: {missing}"
            )
        for item in report_inputs:
            _resolve_input_ref(self._store, item)

        method_ref, _, method_version = method_class.signature.fqn.rpartition("@")
        method_rule_binding = {
            "method_ref": method_ref,
            "method_version": method_version,
            "rule_version_ref": calibration_rule.rule_id,
            "calibration_rule_version": calibration_rule.rule_version,
            "calibration_rule_ref": calibration_rule_ref.model_dump(mode="json"),
        }
        plan = HistoricalValidationPlan(
            plan_id=f"{request.report_id}:ets",
            plan_label=(
                "FRC-02 empirical ETS predictive calibration"
                if retrospective_context is None
                else "FRC-02 retrospective ETS predictive screening"
            ),
            historical_data_ref=str(observed_data_ref.artifact_id),
            intervention_step=request.split.train_end,
            ground_truth_outcomes={request.target_metric: holdout.tolist()},
            target_metrics=[request.target_metric],
            prediction_source=PredictionSource.PROVIDED,
            predicted_outcomes={request.target_metric: list(point_forecast)},
            prediction_intervals={request.target_metric: predictive_intervals},
            confidence_level=nominal_coverage,
            model_spec_ref=None if model_spec_ref is None else str(model_spec_ref.artifact_id),
            policy_spec_ref=None if policy_spec_ref is None else str(policy_spec_ref.artifact_id),
            metadata={
                **method_rule_binding,
                "estimand": request.estimand,
                "authority_scope": "predictive_only",
                "bridge_status": "bridge_pending",
                **(
                    {}
                    if model_spec_ref is None or policy_spec_ref is None
                    else {
                        "model_spec_ref": str(model_spec_ref.artifact_id),
                        "policy_spec_ref": str(policy_spec_ref.artifact_id),
                    }
                ),
                "observed_source_ref": observed_source_ref.model_dump(mode="json"),
                **temporal_metadata,
                "profile_join_status": (
                    "joined_candidate"
                    if value_data_profile_ref is not None
                    else "profileless_legacy"
                ),
                **(
                    {}
                    if value_data_profile_ref is None
                    else {
                        "value_data_profile_ref": value_data_profile_ref.model_dump(mode="json"),
                        "forecast_profile_member_ref": forecast_profile_member_ref.model_dump(
                            mode="json"
                        ),
                    }
                ),
            },
        )
        report, report_ref = BacktestOrchestrator(cas=self._store).run_with_ref(
            [plan],
            report_id=request.report_id,
            inputs=report_inputs,
            trust_screening=TrustScreeningMode.PREDICTIVE_ONLY_BRIDGE_PENDING,
            metadata={
                **method_rule_binding,
                "estimand": request.estimand,
                "authority_scope": "predictive_only",
                "bridge_status": "bridge_pending",
                **(
                    {}
                    if model_spec_ref is None or policy_spec_ref is None
                    else {
                        "model_spec_ref": str(model_spec_ref.artifact_id),
                        "policy_spec_ref": str(policy_spec_ref.artifact_id),
                    }
                ),
                "calibration_diagnostics_ref": calibration_diagnostics_ref.model_dump(mode="json"),
                "uncertainty_bundle_ref": uncertainty_bundle_ref.model_dump(mode="json"),
                **temporal_metadata,
                "profile_join_status": (
                    "joined_candidate"
                    if value_data_profile_ref is not None
                    else "profileless_legacy"
                ),
                **(
                    {}
                    if value_data_profile_ref is None
                    else {
                        "value_data_profile_ref": value_data_profile_ref.model_dump(mode="json"),
                        "forecast_profile_member_ref": forecast_profile_member_ref.model_dump(
                            mode="json"
                        ),
                    }
                ),
            },
        )
        if report.cas_artifact_id is None:
            raise ValueError("backtest orchestrator did not persist a report")
        if str(report_ref.artifact_id) != report.cas_artifact_id:
            raise ValueError("backtest report result lost its persisted artifact identity")
        if report_ref.manifest_profile_sha256 is None:
            raise ValueError(
                "backtest report producer did not retain its selected manifest profile"
            )
        persisted_report: BacktestReport = load_backtest_report(
            _ensure_ir_artifact_store(self._store), report_ref
        )
        if persisted_report.report_id != request.report_id:
            raise ValueError("persisted backtest report lost its allocated report identity")
        expected_model_id = None if model_spec_ref is None else str(model_spec_ref.artifact_id)
        expected_policy_id = None if policy_spec_ref is None else str(policy_spec_ref.artifact_id)
        if persisted_report.model_spec_ref != expected_model_id:
            raise ValueError("persisted backtest report lost its model specification binding")
        if persisted_report.policy_spec_ref != expected_policy_id:
            raise ValueError("persisted backtest report lost its policy specification binding")
        if any(
            persisted_report.metadata.get(key) != value
            for key, value in temporal_metadata.items()
        ):
            raise ValueError("persisted backtest report lost its temporal context")
        for field_name, expected_id in (
            ("model_spec_ref", expected_model_id),
            ("policy_spec_ref", expected_policy_id),
        ):
            metadata_value = persisted_report.metadata.get(field_name)
            if metadata_value != expected_id:
                raise ValueError(
                    f"persisted backtest report metadata lost its {field_name} binding"
                )
        report_manifest = _manifest_for_profile(
            _ensure_ir_artifact_store(self._store),
            report_ref.artifact_id,
            report_ref.manifest_profile_sha256,
        )
        for role, expected_id in (
            ("model_spec", expected_model_id),
            ("policy_spec", expected_policy_id),
            (
                "value_data_profile",
                None if value_data_profile_ref is None else str(value_data_profile_ref.artifact_id),
            ),
            (
                "forecast_profile_member",
                None
                if forecast_profile_member_ref is None
                else str(forecast_profile_member_ref.artifact_id),
            ),
            (
                "source_vintage_receipt",
                None
                if source_vintage_receipt_ref is None
                else str(source_vintage_receipt_ref.artifact_id),
            ),
        ):
            actual_edges = [
                (str(item.artifact_id), item.role, item.manifest_profile_sha256)
                for item in report_manifest.inputs
                if item.role == role
            ]
            expected_ref = {
                "model_spec": model_spec_ref,
                "policy_spec": policy_spec_ref,
                "value_data_profile": value_data_profile_ref,
                "forecast_profile_member": forecast_profile_member_ref,
                "source_vintage_receipt": source_vintage_receipt_ref,
            }[role]
            expected_edges = (
                []
                if expected_id is None or expected_ref is None
                else [(expected_id, role, expected_ref.manifest_profile_sha256)]
            )
            if actual_edges != expected_edges:
                raise ValueError(f"persisted backtest report manifest has incorrect {role} binding")
        if persisted_report.trust_eligible or persisted_report.trust_score is not None:
            raise ValueError(
                "predictive-only bridge-pending backtest report cannot be trust eligible"
            )
        if (
            "trust_screening:predictive_only_bridge_pending"
            not in persisted_report.degraded_reasons
        ):
            raise ValueError("backtest report is missing the predictive trust limitation")

        suitability: Literal["supported", "limited", "blocked"]
        if calibration.has_errors() or not persisted_bundle.horizon_policy.gate_eligible:
            suitability = "blocked"
        else:
            # This is a finite-sample screening label, never an authority gate.
            # One held-out point changes coverage by 1/n, so a fixed 0.05 gap
            # would call every small, otherwise informative corpus limited.
            coverage_gap_tolerance = max(0.05, 1.0 / math.sqrt(coverage_denominator))
            if abs(empirical_coverage - nominal_coverage) <= coverage_gap_tolerance:
                suitability = "supported"
            else:
                suitability = "limited"

        result_fields: dict[str, object] = {
            "report_id": request.report_id,
            "method_fqn": METHOD_FQN,
            "estimand": request.estimand,
            "target_metric": request.target_metric,
            "point_forecast": point_forecast,
            "predictive_intervals": tuple(predictive_intervals),
            "nominal_coverage": nominal_coverage,
            "coverage_numerator": coverage_numerator,
            "coverage_denominator": coverage_denominator,
            "empirical_coverage": empirical_coverage,
            "empirical_suitability": suitability,
            "observed_source_ref": observed_source_ref,
            "value_data_profile_ref": value_data_profile_ref,
            "forecast_profile_member_ref": forecast_profile_member_ref,
            "training_slice_ref": training_slice_ref,
            "method_artifact_ref": method_artifact_ref,
            "calibration_rule_ref": calibration_rule_ref,
            "uncertainty_bundle_ref": uncertainty_bundle_ref,
            "calibration_diagnostics_ref": calibration_diagnostics_ref,
            "backtest_report_ref": report_ref,
            "model_spec_ref": model_spec_ref,
            "policy_spec_ref": policy_spec_ref,
        }
        if isinstance(request, ForecastOwnerRequest):
            return ForecastOwnerResult(
                **result_fields,
                temporal_roles=request.temporal_roles,
            )
        return _RetrospectiveForecastOwnerResult(
            **result_fields,
            retrospective_context=request.retrospective_context,
        )


def run_forecast_owner(store: FileSystemCAS, request: ForecastOwnerRequest) -> ForecastOwnerResult:
    """Convenience wrapper for the bounded ETS owner."""

    return ForecastOwner(store).run(request)


__all__ = [
    "CalibrationRuleBinding",
    "ForecastMethodParams",
    "ForecastOwner",
    "ForecastOwnerRequest",
    "ForecastOwnerResult",
    "ForecastTemporalRoles",
    "TrainHoldoutSplit",
    "run_forecast_owner",
]
