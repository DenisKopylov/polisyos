"""Public governance data plane gate module API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import isfinite
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
)

from polisyos.core.artifacts import CoreArtifactOwnerProfile, SchemaInfo
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.fabric import DataSnapshot, RetrievalSummary
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.connectors import QualityTier
from polisyos.scientist.governance.passes.pii_check_pass import PIICheckPass
from polisyos.scientist.governance.passes.quality_gate_pass import QualityGatePass
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_INPUT_BINDINGS_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state

_DATA_PLANE_GATE_LOAD_ERRORS = (
    AttributeError,
    KeyError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)

_QUALITY_TIER_MAP: dict[str, QualityTier] = {
    "unverified": QualityTier.UNVERIFIED,
    "bronze": QualityTier.BRONZE,
    "silver": QualityTier.SILVER,
    "gold": QualityTier.GOLD,
    "platinum": QualityTier.PLATINUM,
}
_QUALITY_REPORT_OWNER = CoreArtifactOwnerProfile(
    kind="fabric.quality_report",
    media_type="application/json",
    schema_variants=(
        SchemaInfo(name="polisyos.fabric.DataQualityReport", version="1.0"),
        SchemaInfo(name="polisyos.fabric.DataQualityReport", version="1.1"),
    ),
    payload_schema_version_by_manifest="not_applicable",
)
_RETRIEVAL_SUMMARY_OWNER = CoreArtifactOwnerProfile(
    kind=RetrievalSummary.ARTIFACT_KIND,
    media_type=RetrievalSummary.ARTIFACT_MEDIA_TYPE,
    schema_variants=(
        SchemaInfo(
            name=RetrievalSummary.ARTIFACT_SCHEMA_NAME,
            version=RetrievalSummary.ARTIFACT_SCHEMA_VERSION,
        ),
    ),
    payload_schema_version_by_manifest="not_applicable",
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_data_plane_gate@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Data Plane Gate",
    description="Apply quality and PII gates before expensive Foundry execution.",
    tags=["builtin", "governance", "data"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "run_id",
        "artifacts_index",
        f"inputs.{INPUT_DATA_SNAPSHOT_REF}",
        f"inputs.{INPUT_INPUT_BINDINGS_REF}",
        "params.governance_profile",
        "params.tenant_tier",
        "params.pii_scan_results",
    ],
    state_writes=[
        "params.data_plane_gate_profile",
        "params.data_plane_gate_issues",
        "params.data_plane_gate_blocked",
        "params.pii_scan_results",
    ],
    produces=[],
)


@dataclass(frozen=True)
class DataPlaneGateNode:
    """Data plane gate node implementation."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        from polisyos.core.artifacts import validate_core_model_json_artifact

        data_snapshot_ref = state.inputs.get(INPUT_DATA_SNAPSHOT_REF)
        if data_snapshot_ref is None:
            error = NodeError(
                code=node_errors.ERROR_MISSING_INPUT,
                message="Missing data_snapshot_ref for data-plane gate",
                details={"required": [INPUT_DATA_SNAPSHOT_REF]},
            )
            return NodeOutcome(status="fail", state=state, error=error)

        try:
            snapshot = validate_core_model_json_artifact(
                DataSnapshot,
                ctx.store,
                data_snapshot_ref,
            )
        except _DATA_PLANE_GATE_LOAD_ERRORS as exc:
            error = NodeError(
                code=node_errors.ERROR_INVALID_STATE,
                message=f"Unable to load DataSnapshot: {exc}",
                details={
                    "error_type": exc.__class__.__name__,
                    "artifact_id": str(data_snapshot_ref.artifact_id),
                },
            )
            return NodeOutcome(status="fail", state=state, error=error)

        try:
            profile = _resolve_validation_profile(state.params.get("governance_profile"))
        except (TypeError, ValueError) as exc:
            error = NodeError(
                code=node_errors.ERROR_INVALID_STATE,
                message=f"Invalid supplied governance profile: {exc}",
                details={"error_type": exc.__class__.__name__},
            )
            return NodeOutcome(status="fail", state=state, error=error)
        pii_scan = _extract_pii_summary(state, snapshot)
        try:
            quality_report, quality_report_degraded, quality_not_assessed = _load_quality_report(
                ctx, state, snapshot
            )
        except _DATA_PLANE_GATE_LOAD_ERRORS as exc:
            error = NodeError(
                code=node_errors.ERROR_INVALID_STATE,
                message=f"Unable to admit selected Fabric quality report: {exc}",
                details={
                    "error_type": exc.__class__.__name__,
                    "artifact_id": str(snapshot.quality_report_ref.artifact_id)
                    if snapshot.quality_report_ref is not None
                    else None,
                },
            )
            return NodeOutcome(status="fail", state=state, error=error)

        pass_state: dict[str, Any] = {
            "_store": ctx.store,
            "artifacts_index": state.artifacts_index,
            "tenant_tier": str(state.params.get("tenant_tier", "shared")),
            "pii_scan_results": pii_scan,
            "input_bindings_ref": (
                str(state.inputs[INPUT_INPUT_BINDINGS_REF].artifact_id)
                if INPUT_INPUT_BINDINGS_REF in state.inputs
                else None
            ),
        }
        if quality_report is not None:
            pass_state["data_quality_report"] = quality_report

        pass_ctx = PassContext(
            ir=None,
            state=pass_state,
            registry_bundle=None,
            profile=profile,
            run_id=state.run_id,
        )

        issues: list[ComplianceIssue] = []
        issues.extend(QualityGatePass(force_run=True).validate(pass_ctx))
        issues.extend(PIICheckPass().validate(pass_ctx))
        if quality_not_assessed:
            issues.append(
                ComplianceIssue(
                    pass_id="quality",
                    path=["data", "quality"],
                    message=("A retrieval summary is present, but data quality was not assessed."),
                    severity=(
                        IssueSeverity.BLOCKER
                        if profile.level.value == "strict"
                        else IssueSeverity.WARNING
                    ),
                    code="QUALITY_ASSESSMENT_NOT_ESTABLISHED",
                    suggestion=(
                        "Provide an owner-validated DataQualityReport for quality-gated use."
                    ),
                )
            )

        blocker_count = sum(1 for issue in issues if issue.severity == IssueSeverity.BLOCKER)
        issue_payload = [_issue_to_payload(issue) for issue in issues]

        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.params["data_plane_gate_profile"] = profile.level.value
        new_state.params["data_plane_gate_issues"] = issue_payload
        new_state.params["data_plane_gate_blocked"] = blocker_count > 0
        if pii_scan is not None:
            new_state.params["pii_scan_results"] = pii_scan

        events: list[NodeEvent] = []
        if quality_report_degraded is not None:
            events.append(
                NodeEvent(
                    level="warn",
                    code="data_plane_gate.quality_report_degraded",
                    message="Data-plane gate quality report degraded",
                    attrs={
                        "reason": str(
                            quality_report_degraded.get(
                                "reason",
                                "quality_report_load_failed",
                            )
                        ),
                        "error_type": str(
                            quality_report_degraded.get("error_type", "runtime_error")
                        ),
                    },
                )
            )
        if issues:
            events.append(
                NodeEvent(
                    level="warn",
                    message=(
                        f"Data-plane gate produced {len(issues)} issue(s), blockers={blocker_count}"
                    ),
                )
            )
        else:
            events.append(NodeEvent(level="info", message="Data-plane gate passed with no issues"))

        if blocker_count > 0:
            error = NodeError(
                code=node_errors.ERROR_DATA_PLANE_GATE_BLOCKED,
                message="Data-plane gate blocked workflow before simulation",
                details={
                    "blockers": blocker_count,
                    "profile": profile.level.value,
                },
            )
            return NodeOutcome(status="fail", state=new_state, error=error, events=events)

        return NodeOutcome(status="ok", state=new_state, events=events)


def _resolve_validation_profile(raw: Any) -> ValidationProfile:
    if raw is None:
        return ValidationProfile.mvp()
    if isinstance(raw, ValidationProfile):
        return raw
    if isinstance(raw, dict):
        allowed_fields = {"level", "pass_ids", "thresholds", "short_circuit_on_blocker"}
        unexpected_fields = sorted(set(raw) - allowed_fields)
        if unexpected_fields:
            raise ValueError(f"unsupported fields: {', '.join(unexpected_fields)}")
        if raw.get("level") not in {"fast", "mvp", "strict"}:
            raise ValueError("level must be one of fast, mvp, or strict")
        pass_ids = raw.get("pass_ids", [])
        if not isinstance(pass_ids, (list, tuple, set, frozenset)) or any(
            not isinstance(pass_id, str) for pass_id in pass_ids
        ):
            raise ValueError("pass_ids must be a sequence of strings")
        thresholds = raw.get("thresholds", {})
        if not isinstance(thresholds, dict) or any(
            not isinstance(name, str)
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
            for name, value in thresholds.items()
        ):
            raise ValueError("thresholds must map strings to numbers")
        if "short_circuit_on_blocker" in raw and not isinstance(
            raw["short_circuit_on_blocker"], bool
        ):
            raise ValueError("short_circuit_on_blocker must be a boolean")
        try:
            return ValidationProfile.from_dict(raw)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("profile dictionary is malformed") from exc
    if isinstance(raw, str):
        token = raw.strip().lower()
        builders = {
            "fast": ValidationProfile.fast,
            "mvp": ValidationProfile.mvp,
            "strict": ValidationProfile.strict,
        }
        builder = builders.get(token)
        if builder is not None:
            return builder()
        raise ValueError("profile name must be fast, mvp, or strict")
    raise TypeError("profile must be absent, a ValidationProfile, a name, or a mapping")


def _extract_pii_summary(
    state: ExperimentState,
    snapshot: DataSnapshot,
) -> dict[str, Any] | None:
    if isinstance(snapshot.pii_scan_summary, dict):
        return dict(snapshot.pii_scan_summary)
    return None


def _load_quality_report(
    ctx: ExecutionContext,
    state: ExperimentState,
    snapshot: DataSnapshot,
) -> tuple[Any | None, dict[str, object] | None, bool]:
    from polisyos.core.artifacts import validate_owned_core_model_json_artifact

    if snapshot.quality_report_ref is None:
        return None, None, False
    if snapshot.quality_report_ref.kind == RetrievalSummary.ARTIFACT_KIND:
        validate_owned_core_model_json_artifact(
            RetrievalSummary,
            ctx.store,
            snapshot.quality_report_ref,
            expected_owner=_RETRIEVAL_SUMMARY_OWNER,
        )
        return None, None, True
    selected = validate_owned_core_model_json_artifact(
        _QualityReportArtifact,
        ctx.store,
        snapshot.quality_report_ref,
        expected_owner=_QUALITY_REPORT_OWNER,
    )
    return _quality_report_from_dict(selected.value.model_dump(mode="python")), None, False


@dataclass(frozen=True)
class _FreshnessProxy:
    level: str
    is_fresh: bool
    data_age_seconds: int | None
    cache_age_seconds: int | None
    message: str


class _QualityReportFreshnessArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    is_fresh: bool
    level: Literal["fresh", "stale", "unknown"]
    data_age_seconds: StrictInt | None
    message: StrictStr
    fetched_at: StrictStr

    @model_validator(mode="after")
    def _validate_unknown_freshness(self) -> _QualityReportFreshnessArtifact:
        if self.level == "unknown" and self.is_fresh:
            raise ValueError("unknown_freshness_cannot_be_fresh")
        return self

    @field_validator("fetched_at")
    @classmethod
    def _validate_timestamp(cls, value: str) -> str:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("quality report timestamp must include a timezone")
        return value


class _QualityReportViolationArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    rule_type: StrictStr
    field_name: StrictStr | None
    severity: Literal["warning", "error"]
    message: StrictStr
    expected: StrictStr
    actual: StrictStr


class _QualityReportArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    dataset_id: StrictStr
    schema_id: StrictStr
    score: StrictFloat
    tier: Literal["unverified", "bronze", "silver", "gold", "platinum"]
    grade: Literal["A", "B", "C", "D", "F"]
    freshness_status: _QualityReportFreshnessArtifact
    violations: list[_QualityReportViolationArtifact]
    validated_at: StrictStr
    row_count: StrictInt = Field(ge=0)
    quality_flags: list[StrictStr]

    @field_validator("validated_at")
    @classmethod
    def _validate_timestamp(cls, value: str) -> str:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("quality report timestamp must include a timezone")
        return value


@dataclass(frozen=True)
class _ViolationProxy:
    severity: str
    field_name: str | None
    message: str
    rule_type: str
    expected: Any = None
    actual: Any = None


@dataclass(frozen=True)
class _QualityReportProxy:
    tier: QualityTier
    grade: str
    score: float
    freshness_status: _FreshnessProxy
    violations: list[_ViolationProxy]
    dataset_id: str = "unknown_dataset"
    validated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completeness_score: float = 1.0
    consistency_score: float = 1.0
    row_count: int = 0
    anomaly_report: Any = None


def _quality_report_from_dict(payload: dict[str, Any]) -> _QualityReportProxy:
    tier_raw = payload.get("tier")
    if isinstance(tier_raw, int):
        try:
            tier = QualityTier(tier_raw)
        except (TypeError, ValueError):
            tier = QualityTier.UNVERIFIED
    elif isinstance(tier_raw, str):
        tier = _QUALITY_TIER_MAP.get(tier_raw.strip().lower(), QualityTier.UNVERIFIED)
    else:
        tier = QualityTier.UNVERIFIED

    freshness_raw = payload.get("freshness_status")
    if not isinstance(freshness_raw, dict):
        freshness_raw = payload.get("freshness")
    if not isinstance(freshness_raw, dict):
        freshness_raw = {}
    level = str(freshness_raw.get("level", "")).strip().lower()
    is_fresh = bool(freshness_raw.get("is_fresh"))
    if "is_fresh" not in freshness_raw:
        is_fresh = level in {"fresh", "healthy", "ok"}
    data_age_raw = freshness_raw.get("data_age_seconds")
    try:
        data_age = int(data_age_raw) if data_age_raw is not None else None
    except (TypeError, ValueError):
        data_age = None
    cache_age_raw = freshness_raw.get("cache_age_seconds")
    try:
        cache_age = int(cache_age_raw) if cache_age_raw is not None else None
    except (TypeError, ValueError):
        cache_age = None
    message = str(freshness_raw.get("message") or "freshness status unavailable")

    violations_raw = payload.get("violations")
    violations: list[_ViolationProxy] = []
    if isinstance(violations_raw, list):
        for item in violations_raw:
            if not isinstance(item, dict):
                continue
            violations.append(
                _ViolationProxy(
                    severity=str(item.get("severity", "warning")),
                    field_name=(
                        str(item.get("field_name")) if item.get("field_name") is not None else None
                    ),
                    message=str(item.get("message", "")),
                    rule_type=str(item.get("rule_type", "quality")),
                    expected=item.get("expected"),
                    actual=item.get("actual"),
                )
            )

    score_raw = payload.get("score", 0.0)
    try:
        score = float(score_raw)
    except (TypeError, ValueError):
        score = 0.0
    # An absent metric is not proof of complete external source coverage.
    # Preserve the legacy default for other reports, but not the explicit
    # unknown signal emitted by bounded SQL capture.
    flags = payload.get("quality_flags", [])
    default_completeness = (
        0.0 if isinstance(flags, list) and "source_completeness_unknown" in flags else 1.0
    )
    completeness_raw = payload.get("completeness_score", default_completeness)
    try:
        completeness_score = float(completeness_raw)
    except (TypeError, ValueError):
        completeness_score = default_completeness
    consistency_raw = payload.get("consistency_score", 1.0)
    try:
        consistency_score = float(consistency_raw)
    except (TypeError, ValueError):
        consistency_score = 1.0
    row_count_raw = payload.get("row_count", 0)
    try:
        row_count = int(row_count_raw)
    except (TypeError, ValueError):
        row_count = 0
    validated_at_raw = payload.get("validated_at")
    validated_at = datetime.now(UTC)
    if isinstance(validated_at_raw, str) and validated_at_raw.strip():
        try:
            validated_at = datetime.fromisoformat(validated_at_raw.replace("Z", "+00:00"))
        except ValueError:
            validated_at = datetime.now(UTC)
    elif isinstance(validated_at_raw, datetime):
        validated_at = validated_at_raw

    return _QualityReportProxy(
        tier=tier,
        grade=str(payload.get("grade", "N/A")),
        score=score,
        freshness_status=_FreshnessProxy(
            level=level,
            is_fresh=is_fresh,
            data_age_seconds=data_age,
            cache_age_seconds=cache_age,
            message=message,
        ),
        violations=violations,
        dataset_id=str(payload.get("dataset_id") or payload.get("source_id") or "unknown_dataset"),
        validated_at=validated_at,
        completeness_score=completeness_score,
        consistency_score=consistency_score,
        row_count=max(row_count, 0),
        anomaly_report=None,
    )


def _issue_to_payload(issue: ComplianceIssue) -> dict[str, Any]:
    return {
        "pass_id": issue.pass_id,
        "path": issue.path,
        "message": issue.message,
        "severity": issue.severity.value,
        "code": issue.code,
        "suggestion": issue.suggestion,
        "input_value": issue.input_value,
    }


__all__ = ["DataPlaneGateNode"]
