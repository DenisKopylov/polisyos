"""Machine-readable report contract for formal metric-comparison validation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics._owner_admission import (
    OwnedJSONRepresentation as _OwnedJSONRepresentation,
)
from polisyos.ir.analytics._owner_admission import (
    declare_model_owner as _declare_model_owner,
)
from polisyos.ir.analytics._owner_admission import (
    owner_profile_for_spec as _owner_profile_for_spec,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef  # noqa: TC001
from polisyos.ir.artifacts.io import _get_owned_json_artifact, _put_owned_json_artifact
from polisyos.ir.migrations.base import CompatibilityMode as _CompatibilityMode
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import MetricValidationReportRef


class ValidationIssue(BaseModel):
    """Machine-readable issue emitted while validating a metric-comparison family."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    field_path: str | None = None
    hint: str | None = None


class SignificanceRecord(BaseModel):
    """Significance metadata for a single baseline-vs-candidate metric comparison."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    test_id: str
    null_hypothesis: str
    alternative: str
    statistic: float | None = None
    effect_size: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    ci_level: float | None = None
    p_value_raw: float | None = None
    p_value_adj: float | None = None
    alpha: float
    reject_null_raw: bool | None = None
    reject_null_adj: bool | None = None
    assumption_flags: tuple[str, ...] = ()
    calibration_flags: tuple[str, ...] = ()


class MetricComparisonResult(BaseModel):
    """Structured result for one metric comparison inside a validation family."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_id: str
    metric_direction: Literal["higher_is_better", "lower_is_better"]
    baseline_model_id: str
    candidate_model_id: str
    baseline_value: float
    candidate_value: float
    delta_value: float
    significance: SignificanceRecord
    resampling_method: str | None = None
    sample_size_effective: int | None = None
    family_id: str
    family_scope: str


class FamilyAdjustment(BaseModel):
    """Family-level multiplicity metadata applied to raw p-values."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: str
    alpha: float
    hypotheses_total: int
    error_rate_target: Literal["FWER", "FDR"]
    dependency_assumption: str | None = None


class MetricValidationReport(BaseModel):
    """Persisted formal validation report for metric-comparison hypotheses."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    kind: Literal["scientist.metric_validation_report"] = "scientist.metric_validation_report"
    report_id: str
    run_id: str | None = None
    dataset_id: str
    task: str
    is_valid: bool = True
    checked_at: str
    errors: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()
    family_adjustment: FamilyAdjustment
    comparisons: tuple[MetricComparisonResult, ...]
    notes: tuple[str, ...] = ()


_METRIC_VALIDATION_REPORT_OWNER = _declare_model_owner(
    MetricValidationReport,
    contract_id="ir.analytics.metric_validation_report.owner.v1",
    dto_fqn="polisyos.ir.analytics.metric_validation_report.MetricValidationReport",
    abi_key="ir.analytics.metric_validation_report.owner.v1.dto-abi.v1",
    registry_key="polisyos.scientist.metric_validation_report",
    kind="scientist.metric_validation_report",
    media_type="application/json",
    purpose="metric_validation_report",
    policy_revision="ir.analytics.metric_validation_report.owner.v1.admission.v1",
    accepted_wire_policies=(("ir.analytics.metric_validation_report.wire-law", "1"),),
    payload_version_field="schema_version",
    validate_profile=_owner_profile_for_spec(
        CanonSpec(forbid_floats=False),
        profile_ref=None,
    ),
    representations=(
        _OwnedJSONRepresentation(
            schema_name="polisyos.scientist.metric_validation_report",
            schema_version="1.0",
            payload_version="1.0",
            wire_policy_ref="ir.analytics.metric_validation_report.wire-law",
            wire_policy_revision="1",
            profile_ref=None,
            compatibility=_CompatibilityMode.NONE,
            notes=("Exact owner-bound metric-validation report tuple.",),
            readable=True,
            writable=True,
            current=True,
            default_write=True,
            readable_from=(),
        ),
    ),
)


def persist_metric_validation_report(
    store: ArtifactStore,
    report: MetricValidationReport,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "polisyos.scientist.metric_validation_report",
    schema_version: str = "1.0",
) -> MetricValidationReportRef:
    """Persist a metric validation report and return its typed CAS reference."""

    ref = _put_owned_json_artifact(
        store,
        report.model_dump(mode="json"),
        owner=_METRIC_VALIDATION_REPORT_OWNER,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return MetricValidationReportRef.model_validate(ref)


def load_metric_validation_report(
    store: ArtifactStore,
    ref: MetricValidationReportRef,
) -> MetricValidationReport:
    """Load a persisted metric validation report from CAS."""

    return _get_owned_json_artifact(store, ref, owner=_METRIC_VALIDATION_REPORT_OWNER)


__all__ = [
    "FamilyAdjustment",
    "MetricComparisonResult",
    "MetricValidationReport",
    "SignificanceRecord",
    "ValidationIssue",
    "load_metric_validation_report",
    "persist_metric_validation_report",
]
