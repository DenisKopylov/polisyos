"""Typed calibration-gate reports for Phase 1 microsimulation workflows."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import ConfigDict, Field

from polisyos.ir.artifacts.contracts import ArtifactOwnerDeclaration, CanonInfo
from polisyos.ir.artifacts.io import _get_owned_json_artifact, _put_owned_json_artifact
from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.migrations.base import (
    CompatibilityMode,
    IRRepresentationRegistration,
    ResolvedSchemaAdmission,
    register_ir_representation,
    register_schema_version,
)
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import (
    DynamicMicrosimValidationReportRef,
)

if TYPE_CHECKING:
    from polisyos.ir.artifacts.contracts import ArtifactStore, InputRef
    from polisyos.ir.registry.refs import MicrosimCalibrationReportRef


class MicrosimCalibrationReport(KernelModel):
    """Persisted readiness gate emitted by microsim calibration methods."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    artifact_name: Literal["microsim_calibration_report_v1.json"] = (
        "microsim_calibration_report_v1.json"
    )
    decision: Literal["pass", "warn", "block"]
    can_run_microsim: bool
    compatibility_status: str
    reason_code: str | None = None
    exact_feasible: bool = False
    distance_to_feasibility: float = Field(ge=0.0)
    normalized_distance: float = Field(ge=0.0)
    jacobian_rank: int | None = Field(default=None, ge=0)
    condition_number: float | None = Field(default=None, ge=0.0)
    max_abs_gap: float = Field(default=0.0, ge=0.0)
    dynamic_validation_report_ref: DynamicMicrosimValidationReportRef | None = None
    dynamic_validation_status: Literal["green", "amber", "red", "not_run"] | None = None
    warnings: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def build_microsim_calibration_report(
    *,
    compatibility_status: str,
    reason_code: str | None = None,
    exact_feasible: bool = False,
    distance_to_feasibility: float = 0.0,
    normalized_distance: float = 0.0,
    jacobian_rank: int | None = None,
    condition_number: float | None = None,
    max_abs_gap: float = 0.0,
    warnings: list[str] | None = None,
    blocking_reasons: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> MicrosimCalibrationReport:
    """Construct a readiness report from the calibration compatibility surface."""

    decision, can_run_microsim = _decision_from_status(compatibility_status)
    resolved_warnings = [str(item).strip() for item in warnings or () if str(item).strip()]
    resolved_blocking = [str(item).strip() for item in blocking_reasons or () if str(item).strip()]
    if decision == "warn" and f"compatibility:{compatibility_status}" not in resolved_warnings:
        resolved_warnings.append(f"compatibility:{compatibility_status}")
    if decision == "block" and not resolved_blocking:
        resolved_blocking.append(f"compatibility:{compatibility_status}")
    return MicrosimCalibrationReport(
        decision=decision,
        can_run_microsim=can_run_microsim,
        compatibility_status=str(compatibility_status),
        reason_code=None if reason_code is None else str(reason_code),
        exact_feasible=bool(exact_feasible),
        distance_to_feasibility=max(float(distance_to_feasibility), 0.0),
        normalized_distance=max(float(normalized_distance), 0.0),
        jacobian_rank=jacobian_rank,
        condition_number=condition_number,
        max_abs_gap=max(float(max_abs_gap), 0.0),
        warnings=resolved_warnings,
        blocking_reasons=resolved_blocking,
        metadata=dict(metadata or {}),
    )


def report_from_target_compatibility(
    compatibility: object,
    *,
    max_abs_gap: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> MicrosimCalibrationReport:
    """Map a reweighting compatibility payload into the persisted Phase 1 gate."""

    status = _enum_string(getattr(compatibility, "status", None), default="inconclusive")
    if status is None:
        status = "inconclusive"
    reason_code = _enum_string(getattr(compatibility, "reason_code", None))
    warnings = list(getattr(compatibility, "warnings", ()) or ())
    blocking_reasons: list[str] = []
    if status in {"incompatible", "inconclusive", "numeric_failure"}:
        blocking_reasons.append(f"compatibility:{status}")
    payload = dict(metadata or {})
    test_method = _enum_string(getattr(compatibility, "test_method", None))
    if test_method is not None:
        payload.setdefault("test_method", test_method)
    statistic = getattr(compatibility, "statistic", None)
    if statistic is not None:
        payload.setdefault("statistic", float(statistic))
    df = getattr(compatibility, "df", None)
    if df is not None:
        payload.setdefault("df", int(df))
    p_value = getattr(compatibility, "p_value", None)
    if p_value is not None:
        payload.setdefault("p_value", float(p_value))
    return build_microsim_calibration_report(
        compatibility_status=status,
        reason_code=reason_code,
        exact_feasible=bool(getattr(compatibility, "exact_feasible", False)),
        distance_to_feasibility=float(
            getattr(compatibility, "distance_to_feasibility", 0.0) or 0.0
        ),
        normalized_distance=float(getattr(compatibility, "normalized_distance", 0.0) or 0.0),
        jacobian_rank=getattr(compatibility, "jacobian_rank", None),
        condition_number=getattr(compatibility, "condition_number", None),
        max_abs_gap=float(max_abs_gap),
        warnings=warnings,
        blocking_reasons=blocking_reasons,
        metadata=payload,
    )


def attach_dynamic_validation_report_ref(
    report: MicrosimCalibrationReport,
    *,
    dynamic_validation_report_ref: DynamicMicrosimValidationReportRef,
    dynamic_validation_status: Literal["green", "amber", "red", "not_run"],
) -> MicrosimCalibrationReport:
    """Attach the Phase-4 dynamic validation gate to a microsim calibration report."""

    warnings = list(report.warnings)
    blocking_reasons = list(report.blocking_reasons)
    decision = report.decision
    can_run_microsim = report.can_run_microsim
    if dynamic_validation_status == "red":
        decision = "block"
        can_run_microsim = False
        if "dynamic_microsim_validation_red" not in blocking_reasons:
            blocking_reasons.append("dynamic_microsim_validation_red")
    elif dynamic_validation_status == "amber":
        if decision == "pass":
            decision = "warn"
        if "dynamic_microsim_validation_amber" not in warnings:
            warnings.append("dynamic_microsim_validation_amber")
    return report.model_copy(
        update={
            "decision": decision,
            "can_run_microsim": can_run_microsim,
            "dynamic_validation_report_ref": dynamic_validation_report_ref,
            "dynamic_validation_status": dynamic_validation_status,
            "warnings": warnings,
            "blocking_reasons": blocking_reasons,
        }
    )


_OWNER_SCHEMA_NAME = "ir.microsim_calibration_report"
_OWNER_SCHEMA_VERSION = "1.0"
_OWNER_WIRE_POLICY = ("ir.owner.microsimcalibrationreport.wire", "1")


def _owner_payload_version(payload: object) -> str:
    """Require an embedded source version; a DTO default is not historical evidence."""
    if not isinstance(payload, dict):
        raise TypeError("Owned MicrosimCalibrationReport payload must be a JSON object")
    version = payload.get("schema_version")
    if type(version) is not str or not version.strip():
        raise ValueError(
            "Owned MicrosimCalibrationReport payload requires an explicit schema_version"
        )
    return version


def _validate_owner_source(
    payload: object, admission: ResolvedSchemaAdmission
) -> MicrosimCalibrationReport:
    """Validate bytes only under this owner exact registered source representation."""
    registration = admission.source_registration
    if registration.schema_name != _OWNER_SCHEMA_NAME:
        raise ValueError("Owned MicrosimCalibrationReport source has the wrong schema name")
    if registration.payload_version != _owner_payload_version(payload):
        raise ValueError(
            "Owned MicrosimCalibrationReport payload version disagrees with its representation"
        )
    return MicrosimCalibrationReport.model_validate(payload)


def _project_owner_source(
    source: MicrosimCalibrationReport,
    admission: ResolvedSchemaAdmission,
) -> MicrosimCalibrationReport:
    """Preserve the validated source value when no semantic projection is declared."""
    if not isinstance(source, MicrosimCalibrationReport):
        raise TypeError("Owned MicrosimCalibrationReport source was not validated by its owner")
    if admission.source_registration.payload_version != source.schema_version:
        raise ValueError(
            "Owned MicrosimCalibrationReport projection would change the source version"
        )
    return source


def _validate_owner_profile(
    profile: CanonInfo,
    registration: IRRepresentationRegistration,
) -> bool:
    """Accept only the canonical profile used by this family real writer."""
    expected = CanonInfo.from_spec(CanonSpec(forbid_floats=False))
    return registration.profile_ref is None and profile == expected


_microsimcalibrationreport_owner = ArtifactOwnerDeclaration(
    contract_id="ir.analytics.microsim_calibration_report.v1",
    dto_fqn="polisyos.ir.analytics.microsim_calibration.MicrosimCalibrationReport",
    abi_key="ir.microsim_calibration_report",
    registry_key="ir.microsim_calibration_report",
    kind="ir.microsim_calibration_report",
    media_type="application/json",
    purpose="ir.microsim_calibration_report.typed_consumer",
    policy_revision="ir.analytics.microsim_calibration_report.v1.owner-admission.v1",
    accepted_wire_policies=(_OWNER_WIRE_POLICY,),
    payload_version_of=_owner_payload_version,
    validate_source=_validate_owner_source,
    project_for_consumer=_project_owner_source,
    validate_profile=_validate_owner_profile,
)


register_schema_version(
    _OWNER_SCHEMA_NAME,
    _OWNER_SCHEMA_VERSION,
    compatibility=CompatibilityMode.NONE,
    notes=(
        "MicrosimCalibrationReport current owner-admitted representation; historical predecessors are not registered.",
    ),
)
register_ir_representation(
    registry_key=_microsimcalibrationreport_owner.registry_key,
    owner_ref=_microsimcalibrationreport_owner.contract_id,
    dto_abi=_microsimcalibrationreport_owner.dto_fqn,
    wire_policy_ref=_OWNER_WIRE_POLICY[0],
    wire_policy_revision=_OWNER_WIRE_POLICY[1],
    schema_name=_OWNER_SCHEMA_NAME,
    schema_version=_OWNER_SCHEMA_VERSION,
    payload_version=_OWNER_SCHEMA_VERSION,
    profile_ref=None,
    readable=True,
    writable=True,
    current=True,
    default_write=True,
)


def persist_microsim_calibration_report(
    store: ArtifactStore,
    report: MicrosimCalibrationReport,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.microsim_calibration_report",
    schema_version: str = "1.0",
) -> MicrosimCalibrationReportRef:
    """Persist a source-validated MicrosimCalibrationReport under its exact owned representation."""
    selected = _put_owned_json_artifact(
        store,
        report.model_dump(mode="json"),
        owner=_microsimcalibrationreport_owner,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    from polisyos.ir.registry.refs import MicrosimCalibrationReportRef

    return MicrosimCalibrationReportRef.model_validate(selected)


def load_microsim_calibration_report(
    store: ArtifactStore, ref: MicrosimCalibrationReportRef
) -> MicrosimCalibrationReport:
    """Read MicrosimCalibrationReport only after its trusted owner admits the stored representation."""
    return _get_owned_json_artifact(store, ref, owner=_microsimcalibrationreport_owner)


def _decision_from_status(status: str) -> tuple[Literal["pass", "warn", "block"], bool]:
    normalized = str(status).strip().lower()
    if normalized == "compatible":
        return "pass", True
    if normalized == "approximately_compatible":
        return "warn", True
    return "block", False


def _enum_string(value: object, *, default: str | None = None) -> str | None:
    if value is None:
        return default
    enum_value = getattr(value, "value", value)
    text = str(enum_value).strip()
    return text or default


__all__ = [
    "MicrosimCalibrationReport",
    "attach_dynamic_validation_report_ref",
    "build_microsim_calibration_report",
    "load_microsim_calibration_report",
    "persist_microsim_calibration_report",
    "report_from_target_compatibility",
]
