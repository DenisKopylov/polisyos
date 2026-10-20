"""Produce one CAS-bound predictive calibration result from a real forecast method.

This module is the narrow owner for the first FRC-02 empirical slice.  It
executes the registered exponential-smoothing method on an explicit training
slice, evaluates the resulting predictive intervals against a held-out slice,
and persists every handoff through the existing CAS/IR owners.  The result is
deliberately predictive-only and bridge-pending: no value from this owner is a
causal-effect confidence interval or an S10 promotion.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from polisyos.calibration import evaluate_continuous
from polisyos.core.artifacts import FileSystemCAS, artifact_manifest_profile_sha256
from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.contracts import (
    FORECAST_PROFILE_MEMBER_KIND,
    FORECAST_PROFILE_MEMBER_SCHEMA,
    FORECAST_PROFILE_MEMBER_SCHEMA_VERSION,
    VALUE_DATA_PROFILE_KIND,
    DataSnapshot,
    DataSnapshotRef,
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
        if (self.value_data_profile_ref is None) != (self.value_data_unit_id is None):
            raise ValueError("value profile ref and selected unit must be supplied as a pair")
        if self.value_data_profile_ref is not None:
            if (
                self.value_data_profile_ref.kind != VALUE_DATA_PROFILE_KIND
                or self.value_data_profile_ref.media_type != "application/json"
                or self.value_data_profile_ref.manifest_profile_sha256 is None
            ):
                raise ValueError("value profile ref must select an exact JSON manifest view")
            if (
                not self.value_data_unit_id
                or self.value_data_unit_id != self.value_data_unit_id.strip()
            ):
                raise ValueError("selected value profile unit must be a clean identifier")
            member = self.forecast_profile_member
            if (
                member is None
                or member.profile_ref != self.value_data_profile_ref
                or member.unit_id != self.value_data_unit_id
                or member.target_metric != self.target_metric
            ):
                raise ValueError("selected value profile member receipt is incomplete")
        elif self.forecast_profile_member is not None:
            raise ValueError("profile member receipt requires an exact selected profile")
        if self.target_metric != self.target_metric.strip():
            raise ValueError("target_metric must not have surrounding whitespace")
        if self.report_id != self.report_id.strip():
            raise ValueError("report_id must not have surrounding whitespace")
        if (self.model_spec_ref is None) != (self.policy_spec_ref is None):
            raise ValueError("model/policy specification refs must be supplied as a complete pair")
        if (
            self.model_spec_ref is not None
            and self.policy_spec_ref is not None
            and str(getattr(self.model_spec_ref, "artifact_id", self.model_spec_ref))
            == str(getattr(self.policy_spec_ref, "artifact_id", self.policy_spec_ref))
        ):
            raise ValueError("model/policy specification refs must be distinct artifacts")
        if self.method_params.horizon != self.split.horizon:
            raise ValueError("method horizon must match the explicit holdout horizon")
        seen: set[tuple[str, str]] = set()
        for item in self.manifest_inputs:
            role = item.role
            if not role or role != role.strip():
                raise ValueError("manifest input role must be a non-empty clean string")
            key = (str(item.artifact_id), role)
            if key in seen:
                raise ValueError("duplicate manifest input role/artifact pair")
            seen.add(key)
        return self


class ForecastOwnerResult(BaseModel):
    """Persisted predictive evidence and recomputed held-out suitability."""

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
    temporal_roles: ForecastTemporalRoles

    @property
    def numerator(self) -> int:
        """Return the recomputed empirical coverage numerator."""

        return self.coverage_numerator

    @property
    def denominator(self) -> int:
        """Return the recomputed empirical coverage denominator."""

        return self.coverage_denominator


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
    return required


class ForecastOwner:
    """Own one real ETS -> predictive calibration -> backtest artifact chain."""

    def __init__(self, store: FileSystemCAS) -> None:
        self._store = store

    def run(self, request: ForecastOwnerRequest) -> ForecastOwnerResult:
        """Execute and persist one fail-closed predictive owner result."""

        model_spec_ref, policy_spec_ref = _resolve_model_policy_pair(
            self._store,
            model_spec_ref=request.model_spec_ref,
            policy_spec_ref=request.policy_spec_ref,
        )

        observed_source_ref, snapshot_payload = _resolve_json(
            self._store,
            request.observed_source_ref,
            expected_kind="fabric.data_snapshot",
        )
        try:
            snapshot = DataSnapshot.model_validate(snapshot_payload)
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
                    "temporal_roles": request.temporal_roles.model_dump(mode="json"),
                },
            }
        )

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
                    "temporal_roles": request.temporal_roles.model_dump(mode="json"),
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
            "temporal_roles": request.temporal_roles.model_dump(mode="json"),
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
            plan_label="FRC-02 empirical ETS predictive calibration",
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
                "temporal_roles": request.temporal_roles.model_dump(mode="json"),
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
                "temporal_roles": request.temporal_roles.model_dump(mode="json"),
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

        return ForecastOwnerResult(
            report_id=request.report_id,
            method_fqn=METHOD_FQN,
            estimand=request.estimand,
            target_metric=request.target_metric,
            point_forecast=point_forecast,
            predictive_intervals=tuple(predictive_intervals),
            nominal_coverage=nominal_coverage,
            coverage_numerator=coverage_numerator,
            coverage_denominator=coverage_denominator,
            empirical_coverage=empirical_coverage,
            empirical_suitability=suitability,
            observed_source_ref=observed_source_ref,
            value_data_profile_ref=value_data_profile_ref,
            forecast_profile_member_ref=forecast_profile_member_ref,
            training_slice_ref=training_slice_ref,
            method_artifact_ref=method_artifact_ref,
            calibration_rule_ref=calibration_rule_ref,
            uncertainty_bundle_ref=uncertainty_bundle_ref,
            calibration_diagnostics_ref=calibration_diagnostics_ref,
            backtest_report_ref=report_ref,
            model_spec_ref=model_spec_ref,
            policy_spec_ref=policy_spec_ref,
            temporal_roles=request.temporal_roles,
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
