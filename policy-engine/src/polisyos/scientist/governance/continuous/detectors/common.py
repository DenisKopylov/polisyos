"""Shared contracts for continuous-governance drift detectors."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from polisyos.scientist.governance.continuous.monitors import (
    GovernanceMonitorEvent,
    MonitorEventType,
    MonitorSeverity,
    monitor_event_id,
)

if TYPE_CHECKING:
    from polisyos.core import artifacts

DetectorFamily = Literal[
    "calibration_drift",
    "fairness_drift",
    "policy_context_drift",
    "source_invalidation",
]
SparseHistoryBand = Literal["Insufficient", "Thin", "Forming", "Mature adverse"]

DETECTOR_FEATURE_FLAGS: dict[DetectorFamily, str] = {
    "calibration_drift": "policy_design_case.drift_detector.calibration_drift",
    "fairness_drift": "policy_design_case.drift_detector.fairness_drift",
    "policy_context_drift": "policy_design_case.drift_detector.policy_context_drift",
    "source_invalidation": "policy_design_case.drift_detector.source_invalidation",
}
SPARSE_NON_BLOCKING_BANDS: tuple[SparseHistoryBand, ...] = ("Insufficient", "Thin")


class DetectorConfig(BaseModel):
    """Feature-flag posture for one detector family."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    detector_id: str = Field(min_length=1)
    feature_flag: str = Field(min_length=1)
    enabled: bool = True

    @field_validator("detector_id", "feature_flag")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("detector config text fields cannot be blank")
        return text


class SparseHistoryPolicy(BaseModel):
    """Governed sparse-history bands shared by W9.A detectors.

    The policy is intentionally local to detector emission. Downstream lifecycle
    gates may make stricter choices, but detectors never emit blocking severity
    while history is `Insufficient` or `Thin`.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    insufficient_count: int = Field(default=30, ge=1)
    thin_count: int = Field(default=100, ge=1)
    mature_count: int = Field(default=200, ge=1)

    def band_for_count(self, count: int | None, *, adverse: bool = True) -> SparseHistoryBand:
        """Return the sparse-history band for an observed count."""

        resolved_count = max(0, int(count or 0))
        if resolved_count < self.insufficient_count:
            return "Insufficient"
        if resolved_count < self.thin_count:
            return "Thin"
        if resolved_count < self.mature_count or not adverse:
            return "Forming"
        return "Mature adverse"


class DriftDetectionResult(BaseModel):
    """Detector run output containing typed monitor events and audit metadata."""

    model_config = ConfigDict(extra="forbid")

    detector_family: DetectorFamily
    detector_id: str = Field(min_length=1)
    feature_flag: str = Field(min_length=1)
    enabled: bool = True
    events: tuple[GovernanceMonitorEvent, ...] = Field(default=())
    evaluated_signal_count: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


DEFAULT_SPARSE_HISTORY_POLICY = SparseHistoryPolicy()


def detector_config(
    family: DetectorFamily,
    config: DetectorConfig | None = None,
) -> DetectorConfig:
    """Return the explicit or default detector config for a family."""

    if config is not None:
        return config
    return DetectorConfig(
        detector_id=f"w9a.{family}",
        feature_flag=DETECTOR_FEATURE_FLAGS[family],
    )


def severity_for_band(
    band: SparseHistoryBand,
    *,
    blocking_candidate: bool,
    warning_candidate: bool = True,
) -> MonitorSeverity:
    """Map sparse-history band and detector signal into monitor severity."""

    if band in SPARSE_NON_BLOCKING_BANDS:
        return "warning" if warning_candidate else "info"
    if band == "Mature adverse" and blocking_candidate:
        return "block"
    return "warning" if warning_candidate else "info"


def blocking_permitted(
    band: SparseHistoryBand,
    *,
    blocking_candidate: bool,
) -> bool:
    """Return whether a detector may emit blocking consequences."""

    return band == "Mature adverse" and blocking_candidate


def build_detector_event(
    *,
    decision_packet_ref: artifacts.ArtifactRef,
    event_type: MonitorEventType,
    severity: MonitorSeverity,
    reason: str,
    scope: Mapping[str, Any] | None = None,
    affected_claim_ids: Iterable[str] = (),
    affected_dag_node_ids: Iterable[str] = (),
    metadata: Mapping[str, Any] | None = None,
    occurred_at: datetime | None = None,
    sequence: int = 0,
) -> GovernanceMonitorEvent:
    """Build a scoped continuous-governance monitor event."""

    normalized_scope = normalize_scope(scope)
    return GovernanceMonitorEvent(
        event_id=monitor_event_id(
            decision_packet_ref=decision_packet_ref,
            event_type=event_type,
            reason=reason,
            sequence=sequence,
        ),
        decision_packet_ref=decision_packet_ref,
        event_type=event_type,
        severity=severity,
        scope=normalized_scope,
        affected_claim_ids=tuple_to_list(affected_claim_ids),
        affected_dag_node_ids=tuple_to_list(affected_dag_node_ids),
        reason=reason,
        occurred_at=(occurred_at or datetime.now(UTC)).astimezone(UTC),
        metadata=dict(metadata or {}),
    )


def normalize_scope(scope: Mapping[str, Any] | BaseModel | None) -> dict[str, Any]:
    """Return a JSON-friendly scope dict with blank values removed."""

    if scope is None:
        return {}
    if isinstance(scope, BaseModel):
        raw = scope.model_dump(mode="json", exclude_none=True)
    else:
        raw = dict(scope)
    normalized: dict[str, Any] = {}
    for key, value in raw.items():
        text_key = str(key)
        serialized = _json_safe(value)
        if serialized is None or serialized == "":
            continue
        normalized[text_key] = serialized
    return normalized


def tuple_to_list(values: Iterable[str]) -> list[str]:
    """Return deterministic, non-empty string values without duplicates."""

    return list(dict.fromkeys(str(value) for value in values if str(value).strip()))


def scope_matches(candidate: Mapping[str, Any] | None, expected: Mapping[str, Any] | None) -> bool:
    """Return whether a candidate scope contains every expected non-empty value."""

    if expected is None:
        return True
    candidate_scope = normalize_scope(candidate)
    expected_scope = normalize_scope(expected)
    for key, expected_value in expected_scope.items():
        if key not in candidate_scope:
            continue
        if candidate_scope[key] != expected_value:
            return False
    return True


def sparse_metadata(
    *,
    band: SparseHistoryBand,
    blocking_candidate: bool,
) -> dict[str, Any]:
    """Return common sparse-history metadata for monitor events."""

    permitted = blocking_permitted(band, blocking_candidate=blocking_candidate)
    return {
        "sparse_history_band": band,
        "sparse_history_non_blocking": band in SPARSE_NON_BLOCKING_BANDS,
        "blocking_consequence_permitted": permitted,
    }


def balanced_memory_context(
    memories: Sequence[Any] | None,
    *,
    scope: Mapping[str, Any] | None = None,
    run_id: str = "w9a-detector",
) -> dict[str, Any] | None:
    """Project applicable balanced memory as future-influence-only context."""

    if not memories:
        return None

    from polisyos.scientist.orchestration.memory import (
        MEMORY_FORBIDDEN_CURRENT_USES,
        MEMORY_FUTURE_AUTHORITY_USES,
        MemoryApplicabilityContext,
        evaluate_balanced_memory_applicability,
    )

    normalized_scope = normalize_scope(scope)
    context = MemoryApplicabilityContext(
        run_id=run_id,
        domain=str(normalized_scope.get("domain") or "general"),
        workflow_id=_optional_text(normalized_scope.get("workflow_id")),
        method_family=_optional_text(normalized_scope.get("method_family")),
    )
    applicable_ids: list[str] = []
    blocked: list[dict[str, Any]] = []
    influence_modes: list[str] = []
    for memory in memories:
        applicability = evaluate_balanced_memory_applicability(memory, context)
        if applicability.applies:
            applicable_ids.append(memory.memory_id)
            influence_modes.extend(
                mode.value if hasattr(mode, "value") else str(mode)
                for mode in applicability.influence_modes
            )
        else:
            blocked.append(
                {
                    "memory_id": memory.memory_id,
                    "reasons": list(applicability.reasons),
                }
            )
    return {
        "evaluated_memory_count": len(memories),
        "applicable_memory_ids": applicable_ids,
        "blocked_memories": blocked,
        "influence_modes": tuple_to_list(influence_modes),
        "authority_boundary": {
            "authoritative_for": list(MEMORY_FUTURE_AUTHORITY_USES),
            "may_not_use_for": list(MEMORY_FORBIDDEN_CURRENT_USES),
            "current_run_evidence_effect": "none",
            "claim_evidence_admissible": False,
        },
    }


def result(
    *,
    family: DetectorFamily,
    config: DetectorConfig,
    events: Sequence[GovernanceMonitorEvent],
    evaluated_signal_count: int,
    metadata: Mapping[str, Any] | None = None,
) -> DriftDetectionResult:
    """Build a detector result with consistent audit metadata."""

    return DriftDetectionResult(
        detector_family=family,
        detector_id=config.detector_id,
        feature_flag=config.feature_flag,
        enabled=config.enabled,
        events=tuple(events),
        evaluated_signal_count=evaluated_signal_count,
        metadata=dict(metadata or {}),
    )


def disabled_result(*, family: DetectorFamily, config: DetectorConfig) -> DriftDetectionResult:
    """Return an empty detector result for a disabled family."""

    return result(
        family=family,
        config=config,
        events=(),
        evaluated_signal_count=0,
        metadata={"disabled_by_feature_flag": config.feature_flag},
    )


def _json_safe(value: object) -> object:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
            if item is not None and item != ""
        }
    if isinstance(value, list | tuple | set):
        return [_json_safe(item) for item in value if item is not None and item != ""]
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "DEFAULT_SPARSE_HISTORY_POLICY",
    "DETECTOR_FEATURE_FLAGS",
    "SPARSE_NON_BLOCKING_BANDS",
    "DetectorConfig",
    "DetectorFamily",
    "DriftDetectionResult",
    "SparseHistoryBand",
    "SparseHistoryPolicy",
    "balanced_memory_context",
    "blocking_permitted",
    "build_detector_event",
    "detector_config",
    "disabled_result",
    "normalize_scope",
    "result",
    "scope_matches",
    "severity_for_band",
    "sparse_metadata",
    "tuple_to_list",
]
