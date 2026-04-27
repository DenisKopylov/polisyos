"""Distribution-shift diagnostics and readiness downgrade contracts."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir._validation import ensure_finite_numeric, ensure_unique_ids
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import ShiftDiagnosticReportRef

SeverityBucket = Literal["none", "low", "moderate", "high", "severe", "unassessable"]
ShiftStatus = Literal[
    "not_detected",
    "detected",
    "suspected",
    "confirmed",
    "unassessable_until_labels",
    "insufficient_power",
]
ReadinessBand = Literal["ready", "monitor", "restricted", "blocked"]
TaskType = Literal["classification", "regression", "ranking", "forecasting"]
ShiftModality = Literal["tabular_administrative", "longitudinal_panel", "sparse_survey"]
ReferenceComparisonType = Literal[
    "training_vs_current",
    "validation_vs_current",
    "stable_recent_vs_current",
    "seasonal_historical_vs_current",
]
DetectorFamily = Literal[
    "schema",
    "univariate",
    "multivariate",
    "classifier_two_sample",
    "mmd",
    "density_ratio",
    "prediction_output",
    "panel_temporal",
    "delayed_label_concept",
    "subgroup",
]
ShiftGlobalVerdict = Literal[
    "no_shift_detected",
    "marginal_shift",
    "support_shift",
    "label_prior_shift",
    "concept_shift",
    "mixed_shift",
    "schema_shift",
    "insufficient_power",
]
LabelAvailability = Literal["none", "proxy", "delayed", "current"]
DecisionContext = Literal["standard", "high_stakes"]


READINESS_ORDER: tuple[ReadinessBand, ...] = ("ready", "monitor", "restricted", "blocked")


class OperatingCharacteristicKey(BaseModel):
    """Lookup key for calibrated detector operating characteristics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    modality: ShiftModality
    task_type: TaskType
    n_reference_bucket: str = Field(min_length=1)
    n_current_bucket: str = Field(min_length=1)
    feature_count_bucket: str = Field(min_length=1)
    categorical_cardinality_bucket: str = Field(min_length=1)
    sparsity_missingness_bucket: str = Field(min_length=1)
    label_lag_bucket: str = Field(min_length=1)
    detector_family: DetectorFamily
    reference_comparison_type: ReferenceComparisonType
    windowing_strategy: str = Field(min_length=1)
    calibration_version: str = Field(min_length=1)

    def to_cache_key(self) -> str:
        """Return a stable string form suitable for detector records."""

        return "|".join(
            (
                self.modality,
                self.task_type,
                self.n_reference_bucket,
                self.n_current_bucket,
                self.feature_count_bucket,
                self.categorical_cardinality_bucket,
                self.sparsity_missingness_bucket,
                self.label_lag_bucket,
                self.detector_family,
                self.reference_comparison_type,
                self.windowing_strategy,
                self.calibration_version,
            )
        )


class OperatingCharacteristicRecord(BaseModel):
    """Declared false-alert, power, delay, and invalid-regime behavior."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: OperatingCharacteristicKey
    false_positive_rate_by_no_shift_regime: dict[str, float] = Field(default_factory=dict)
    feature_family_false_discovery_rate: dict[str, float] = Field(default_factory=dict)
    power_curve_by_shift_type_and_severity: dict[str, dict[str, float]] = Field(
        default_factory=dict
    )
    minimum_detectable_effect: dict[str, Any] = Field(default_factory=dict)
    expected_detection_delay: dict[str, Any] = Field(default_factory=dict)
    shift_type_attribution_confusion_matrix: dict[str, dict[str, float]] = Field(
        default_factory=dict
    )
    localization_precision_recall: dict[str, float] = Field(default_factory=dict)
    subgroup_power_summary: dict[str, Any] = Field(default_factory=dict)
    support_overlap_error_profile: dict[str, Any] = Field(default_factory=dict)
    compute_cost_profile: dict[str, Any] = Field(default_factory=dict)
    recommended_thresholds: dict[str, float] = Field(default_factory=dict)
    known_invalid_regimes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_operating_characteristics(self) -> OperatingCharacteristicRecord:
        bounded_maps = (
            ("false_positive_rate_by_no_shift_regime", self.false_positive_rate_by_no_shift_regime),
            ("feature_family_false_discovery_rate", self.feature_family_false_discovery_rate),
            ("localization_precision_recall", self.localization_precision_recall),
        )
        for field_name, mapping in bounded_maps:
            for key, value in mapping.items():
                if not key.strip():
                    raise ValueError(f"{field_name} keys must be non-empty")
                ensure_finite_numeric(value, field_name=f"{field_name}.{key}")
                if not (0.0 <= value <= 1.0):
                    raise ValueError(f"{field_name}.{key} must be in [0,1]")
        for threshold_name, threshold in self.recommended_thresholds.items():
            if not threshold_name.strip():
                raise ValueError("recommended_thresholds keys must be non-empty")
            ensure_finite_numeric(threshold, field_name=f"recommended_thresholds.{threshold_name}")
        ensure_unique_ids(
            self.known_invalid_regimes,
            key_fn=lambda item: item,
            label="known_invalid_regime",
        )
        return self


class OperatingCharacteristicLibrary(BaseModel):
    """Versioned, queryable library of detector operating characteristics."""

    contract_id: ClassVar[str] = "foundry.shift_operating_characteristic_library.v1"
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = Field(min_length=1)
    records: tuple[OperatingCharacteristicRecord, ...] = ()
    generated_at: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_library(self) -> OperatingCharacteristicLibrary:
        ensure_unique_ids(
            self.records,
            key_fn=lambda item: item.key.to_cache_key(),
            label="operating characteristic record",
        )
        return self

    def lookup(
        self,
        key: OperatingCharacteristicKey | str,
    ) -> OperatingCharacteristicRecord | None:
        """Return the record for a full OCL key, if present."""

        cache_key = key if isinstance(key, str) else key.to_cache_key()
        for record in self.records:
            if record.key.to_cache_key() == cache_key:
                return record
        return None

    def by_detector_family(self, family: DetectorFamily) -> tuple[OperatingCharacteristicRecord, ...]:
        """Return all records declared for a detector family."""

        return tuple(record for record in self.records if record.key.detector_family == family)


class CalibrationInfo(BaseModel):
    """Calibration metadata carried with every shift report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operating_characteristic_library_version: str = Field(min_length=1)
    calibration_id: str = Field(min_length=1)
    reference_comparison_type: ReferenceComparisonType
    target_report_fpr: float = Field(ge=0.0, le=1.0)
    multiplicity_method: str | None = "benjamini_hochberg"
    null_regime: str = Field(min_length=1)
    min_detectable_effect_summary: dict[str, Any] = Field(default_factory=dict)
    power_summary: dict[str, Any] = Field(default_factory=dict)


class ShiftComponent(BaseModel):
    """One subtype verdict with calibrated severity and evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ShiftStatus
    severity_score: float | None = Field(default=None, ge=0.0, le=1.0)
    severity_bucket: SeverityBucket
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    q_value: float | None = Field(default=None, ge=0.0, le=1.0)
    effect_size: float | None = None
    confidence_interval: tuple[float, float] | None = None
    power: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_component(self) -> ShiftComponent:
        if self.effect_size is not None:
            ensure_finite_numeric(self.effect_size, field_name="effect_size")
        if self.confidence_interval is not None:
            lower, upper = self.confidence_interval
            ensure_finite_numeric(lower, field_name="confidence_interval.lower")
            ensure_finite_numeric(upper, field_name="confidence_interval.upper")
            if lower > upper:
                raise ValueError("confidence_interval lower bound cannot exceed upper bound")
        if self.status == "unassessable_until_labels" and self.severity_bucket != "unassessable":
            raise ValueError(
                "unassessable_until_labels components must use severity_bucket='unassessable'"
            )
        return self


class DetectorResult(BaseModel):
    """Raw detector evidence retained for audit and localization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    detector_name: str = Field(min_length=1)
    detector_family: DetectorFamily
    data_view: str = Field(min_length=1)
    statistic: float | None = None
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    q_value: float | None = Field(default=None, ge=0.0, le=1.0)
    effect_size: float | None = None
    null_percentile: float | None = Field(default=None, ge=0.0, le=1.0)
    calibrated_threshold: float | None = None
    operating_characteristic_key: str = Field(min_length=1)
    implicated_features: tuple[str, ...] = ()
    implicated_subgroups: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_detector_result(self) -> DetectorResult:
        for field_name in ("statistic", "effect_size", "calibrated_threshold"):
            value = getattr(self, field_name)
            if value is not None:
                ensure_finite_numeric(value, field_name=field_name)
        ensure_unique_ids(
            self.implicated_features,
            key_fn=lambda item: item,
            label="detector implicated_feature",
        )
        ensure_unique_ids(
            self.implicated_subgroups,
            key_fn=lambda item: item,
            label="detector implicated_subgroup",
        )
        return self


class FeatureShiftDiagnostic(BaseModel):
    """Human-readable feature localization output with model relevance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_name: str = Field(min_length=1)
    feature_type: Literal[
        "numeric",
        "categorical",
        "binary",
        "text",
        "embedding",
        "missingness_indicator",
    ]
    severity_score: float = Field(ge=0.0, le=1.0)
    q_value: float | None = Field(default=None, ge=0.0, le=1.0)
    effect_size: float | None = None
    model_relevance: float | None = Field(default=None, ge=0.0, le=1.0)
    direction_summary: str | None = Field(default=None, min_length=1)
    example_changes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_feature_diagnostic(self) -> FeatureShiftDiagnostic:
        if self.effect_size is not None:
            ensure_finite_numeric(self.effect_size, field_name="effect_size")
        return self


class ReadinessImpact(BaseModel):
    """Deterministic readiness consequence of a shift report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_readiness: ReadinessBand
    downgrade_level: int = Field(ge=0, le=3)
    resulting_readiness: ReadinessBand
    downgrade_reasons: tuple[str, ...]
    required_actions: tuple[str, ...]
    expires_at: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_readiness_impact(self) -> ReadinessImpact:
        expected = readiness_after_downgrade(self.base_readiness, self.downgrade_level)
        if self.resulting_readiness != expected:
            raise ValueError(
                "resulting_readiness must equal base_readiness after downgrade_level is applied"
            )
        return self


class ShiftDiagnosticReport(BaseModel):
    """Calibrated, modality-aware distribution-shift diagnostic report."""

    contract_id: ClassVar[str] = "foundry.shift_diagnostic_report.v1"
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["foundry.shift_diagnostic.v1"] = "foundry.shift_diagnostic.v1"
    report_id: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)

    prediction_result_id: str | None = Field(default=None, min_length=1)
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    task_type: TaskType
    modality: ShiftModality

    training_reference_id: str = Field(min_length=1)
    validation_reference_id: str | None = Field(default=None, min_length=1)
    current_window_id: str = Field(min_length=1)
    current_window_start: str = Field(min_length=1)
    current_window_end: str = Field(min_length=1)

    n_reference: int = Field(ge=0)
    n_current: int = Field(ge=0)
    effective_n_reference: float | None = Field(default=None, ge=0.0)
    effective_n_current: float | None = Field(default=None, ge=0.0)

    label_availability: LabelAvailability
    label_lag_days: int | None = Field(default=None, ge=0)
    decision_context: DecisionContext = "standard"
    power_status: Literal["sufficient", "insufficient", "unknown"] = "unknown"

    calibration: CalibrationInfo

    schema_shift: ShiftComponent
    marginal_shift: ShiftComponent
    support_shift: ShiftComponent
    label_prior_shift: ShiftComponent
    concept_shift: ShiftComponent
    prediction_output_shift: ShiftComponent
    harmful_shift_risk: ShiftComponent

    global_verdict: ShiftGlobalVerdict

    detector_results: tuple[DetectorResult, ...]
    feature_diagnostics: tuple[FeatureShiftDiagnostic, ...] = ()
    subgroup_diagnostics: tuple[dict[str, Any], ...] = ()

    readiness_impact: ReadinessImpact

    human_summary: str = Field(min_length=1)
    machine_summary: dict[str, Any] = Field(default_factory=dict)
    limitations: tuple[str, ...]
    recommended_next_checks: tuple[str, ...]

    @model_validator(mode="after")
    def validate_report(self) -> ShiftDiagnosticReport:
        ensure_unique_ids(
            self.detector_results,
            key_fn=lambda item: (item.detector_name, item.data_view),
            label="detector result",
        )
        ensure_unique_ids(
            self.feature_diagnostics,
            key_fn=lambda item: item.feature_name,
            label="feature diagnostic",
        )
        if self.concept_shift.status == "confirmed" and self.label_availability == "none":
            raise ValueError("confirmed concept shift requires current, delayed, or proxy labels")
        if (
            self.label_availability == "none"
            and self.concept_shift.status == "not_detected"
            and self.concept_shift.severity_bucket != "unassessable"
        ):
            raise ValueError(
                "label-free reports cannot mark concept_shift as not_detected; use "
                "unassessable_until_labels or suspected"
            )
        if self.global_verdict == "no_shift_detected":
            if self.power_status != "sufficient":
                raise ValueError("no_shift_detected requires power_status='sufficient'")
            if not self.calibration.power_summary:
                raise ValueError("no_shift_detected requires a non-empty power_summary")
        expected_downgrade = readiness_downgrade(self)
        if self.readiness_impact.downgrade_level != expected_downgrade:
            raise ValueError(
                "readiness_impact.downgrade_level must match deterministic shift rules"
            )
        return self


def readiness_after_downgrade(
    base_readiness: ReadinessBand,
    downgrade_level: int,
) -> ReadinessBand:
    """Apply a 0-3 downgrade to the readiness ladder."""

    if not 0 <= int(downgrade_level) <= 3:
        raise ValueError("downgrade_level must be in [0,3]")
    index = READINESS_ORDER.index(base_readiness)
    return READINESS_ORDER[min(index + int(downgrade_level), len(READINESS_ORDER) - 1)]


def readiness_downgrade(report: ShiftDiagnosticReport | Any) -> int:
    """Map shift subtype evidence to the Phase-5 readiness downgrade ladder."""

    if report.schema_shift.severity_bucket in {"high", "severe"}:
        return 3

    if report.concept_shift.status == "confirmed":
        return 3

    if report.support_shift.severity_bucket == "severe":
        return 3

    if report.support_shift.severity_bucket == "high":
        return 2

    if (
        report.concept_shift.status == "suspected"
        and report.harmful_shift_risk.severity_bucket in {"high", "severe"}
    ):
        return 2

    if report.marginal_shift.severity_bucket in {"high", "severe"}:
        return 2

    if report.label_prior_shift.severity_bucket in {"high", "severe"}:
        return 2

    if report.marginal_shift.severity_bucket == "moderate":
        return 1

    if report.power_status == "insufficient" and report.decision_context == "high_stakes":
        return 2

    if report.power_status == "insufficient":
        return 1

    return 0


def build_readiness_impact(
    *,
    base_readiness: ReadinessBand,
    downgrade_level: int,
    downgrade_reasons: tuple[str, ...] = (),
    required_actions: tuple[str, ...] = (),
    expires_at: str | None = None,
) -> ReadinessImpact:
    """Create a readiness impact using the canonical downgrade ladder."""

    return ReadinessImpact(
        base_readiness=base_readiness,
        downgrade_level=downgrade_level,
        resulting_readiness=readiness_after_downgrade(base_readiness, downgrade_level),
        downgrade_reasons=downgrade_reasons,
        required_actions=required_actions,
        expires_at=expires_at,
    )


def persist_shift_diagnostic_report(
    store: ArtifactStore,
    report: ShiftDiagnosticReport,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.shift_diagnostic_report",
    schema_version: str = "1.0",
) -> ShiftDiagnosticReportRef:
    """Persist a shift report for audit and PredictionResult consumers."""

    ref = put_json_artifact(
        store,
        report.model_dump(mode="json"),
        kind="ir.shift_diagnostic_report",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ShiftDiagnosticReportRef.model_validate(ref)


def load_shift_diagnostic_report(
    store: ArtifactStore,
    ref: ShiftDiagnosticReportRef,
) -> ShiftDiagnosticReport:
    """Load and validate a persisted shift diagnostic report."""

    payload = get_json_artifact(store, ref.artifact_id)
    return ShiftDiagnosticReport.model_validate(payload)


__all__ = [
    "CalibrationInfo",
    "DecisionContext",
    "DetectorFamily",
    "DetectorResult",
    "FeatureShiftDiagnostic",
    "LabelAvailability",
    "OperatingCharacteristicKey",
    "OperatingCharacteristicLibrary",
    "OperatingCharacteristicRecord",
    "ReadinessBand",
    "ReadinessImpact",
    "ReferenceComparisonType",
    "SeverityBucket",
    "ShiftComponent",
    "ShiftDiagnosticReport",
    "ShiftGlobalVerdict",
    "ShiftModality",
    "ShiftStatus",
    "TaskType",
    "build_readiness_impact",
    "load_shift_diagnostic_report",
    "persist_shift_diagnostic_report",
    "readiness_after_downgrade",
    "readiness_downgrade",
]
