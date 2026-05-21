"""Public governance data plane gate module API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.connectors import QualityTier
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.governance.passes.pii_check_pass import PIICheckPass
from polisyos.scientist.governance.passes.quality_gate_pass import QualityGatePass
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_INPUT_BINDINGS_REF,
)

logger = get_logger(__name__)
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
        data_snapshot_ref = state.inputs.get(INPUT_DATA_SNAPSHOT_REF)
        if data_snapshot_ref is None:
            error = NodeError(
                code=node_errors.ERROR_MISSING_INPUT,
                message="Missing data_snapshot_ref for data-plane gate",
                details={"required": [INPUT_DATA_SNAPSHOT_REF]},
            )
            return NodeOutcome(status="fail", state=state, error=error)

        try:
            snapshot_payload = from_canonical_bytes(
                ctx.store.get_bytes(data_snapshot_ref.artifact_id)
            )
            snapshot = DataSnapshot.model_validate(snapshot_payload)
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

        profile = _resolve_validation_profile(state.params.get("governance_profile"))
        pii_scan = _extract_pii_summary(state, snapshot)
        quality_report, quality_report_degraded = _load_quality_report(ctx, state, snapshot)

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
    if isinstance(raw, ValidationProfile):
        return raw
    if isinstance(raw, dict):
        try:
            return ValidationProfile.from_dict(raw)
        except (TypeError, ValueError):
            return ValidationProfile.mvp()
    if isinstance(raw, str):
        token = raw.strip().lower()
        if token == "fast":
            return ValidationProfile.fast()
        if token == "strict":
            return ValidationProfile.strict()
    return ValidationProfile.mvp()


def _extract_pii_summary(
    state: ExperimentState,
    snapshot: DataSnapshot,
) -> dict[str, Any] | None:
    existing = state.params.get("pii_scan_results")
    if isinstance(existing, dict):
        return existing
    if isinstance(snapshot.pii_scan_summary, dict):
        return dict(snapshot.pii_scan_summary)
    return None


def _load_quality_report(
    ctx: ExecutionContext,
    state: ExperimentState,
    snapshot: DataSnapshot,
) -> tuple[Any | None, dict[str, object] | None]:
    if snapshot.quality_report_ref is None:
        return None, None
    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(snapshot.quality_report_ref.artifact_id))
    except _DATA_PLANE_GATE_LOAD_ERRORS as exc:
        return None, emit_degraded_path(
            component="scientist.data_plane_gate",
            operation="load_quality_report",
            reason="quality_report_load_failed",
            exc=exc,
            details={
                "run_id": state.run_id,
                "artifact_id": str(snapshot.quality_report_ref.artifact_id),
            },
            log=logger,
            metrics=ctx.metrics,
        )
    if isinstance(payload, dict):
        return _quality_report_from_dict(payload), None
    return payload, None


@dataclass(frozen=True)
class _FreshnessProxy:
    is_fresh: bool
    data_age_seconds: int | None
    cache_age_seconds: int | None
    message: str


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
    completeness_raw = payload.get("completeness_score", 1.0)
    try:
        completeness_score = float(completeness_raw)
    except (TypeError, ValueError):
        completeness_score = 1.0
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
