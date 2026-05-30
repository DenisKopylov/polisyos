"""Policy-context drift detector over legal, context, and governance streams."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from polisyos.scientist.governance.continuous.monitors import (
    GovernanceMonitorEvent,
)

from .common import (
    DEFAULT_SPARSE_HISTORY_POLICY,
    DetectorConfig,
    DriftDetectionResult,
    SparseHistoryPolicy,
    balanced_memory_context,
    build_detector_event,
    detector_config,
    disabled_result,
    normalize_scope,
    result,
    severity_for_band,
    sparse_metadata,
    tuple_to_list,
)

if TYPE_CHECKING:
    from polisyos.core import artifacts


class PolicyContextSignal(BaseModel):
    """Normalized policy/legal/context drift signal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    signal_id: str = Field(min_length=1)
    change_kind: str = Field(min_length=1)
    description: str = Field(min_length=1)
    severity_score: float = Field(ge=0.0, le=1.0)
    history_count: int = Field(default=0, ge=0)
    blocking_candidate: bool = False
    affected_claim_ids: tuple[str, ...] = Field(default=())
    scope: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("affected_claim_ids", mode="before")
    @classmethod
    def _coerce_text_tuple(cls, value: object) -> tuple[str, ...]:
        return tuple(tuple_to_list(_text_values(value)))

    @field_validator("occurred_at")
    @classmethod
    def _normalize_time(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


def detect_policy_context_drift(
    *,
    decision_packet_ref: artifacts.ArtifactRef,
    signals: Sequence[PolicyContextSignal | GovernanceMonitorEvent | Mapping[str, Any]],
    balanced_memories: Sequence[Any] | None = None,
    sparse_history_policy: SparseHistoryPolicy = DEFAULT_SPARSE_HISTORY_POLICY,
    config: DetectorConfig | None = None,
    warning_threshold: float = 0.4,
    sequence: int = 0,
) -> DriftDetectionResult:
    """Emit policy-context drift monitor events from context monitor streams."""

    active_config = detector_config("policy_context_drift", config)
    if not active_config.enabled:
        return disabled_result(family="policy_context_drift", config=active_config)

    normalized = [_normalize_signal(signal) for signal in signals]
    events: list[GovernanceMonitorEvent] = []
    for index, signal in enumerate(normalized):
        if signal.severity_score < warning_threshold and not signal.blocking_candidate:
            continue
        band = sparse_history_policy.band_for_count(signal.history_count, adverse=True)
        blocking_candidate = signal.blocking_candidate or signal.severity_score >= 0.9
        severity = severity_for_band(band, blocking_candidate=blocking_candidate)
        event_scope = normalize_scope(signal.scope)
        memory_context = balanced_memory_context(
            balanced_memories,
            scope=event_scope,
            run_id="w9a-policy-context-detector",
        )
        metadata = {
            "detector_family": "policy_context_drift",
            "detector_id": active_config.detector_id,
            "feature_flag": active_config.feature_flag,
            "monitor_signal_ids": [signal.signal_id],
            "change_kind": signal.change_kind,
            "severity_score": signal.severity_score,
            "history_count": signal.history_count,
            "description": signal.description,
            **signal.metadata,
            **sparse_metadata(band=band, blocking_candidate=blocking_candidate),
        }
        if memory_context is not None:
            metadata["balanced_memory_context"] = memory_context
        events.append(
            build_detector_event(
                decision_packet_ref=decision_packet_ref,
                event_type="policy_context_drift",
                severity=severity,
                scope=event_scope,
                affected_claim_ids=signal.affected_claim_ids,
                reason=f"Policy context drift detected: {signal.description}",
                metadata=metadata,
                occurred_at=signal.occurred_at,
                sequence=sequence + index,
            )
        )

    return result(
        family="policy_context_drift",
        config=active_config,
        events=events,
        evaluated_signal_count=len(normalized),
        metadata={"input_signal_count": len(signals)},
    )


def _normalize_signal(
    signal: PolicyContextSignal | GovernanceMonitorEvent | Mapping[str, Any],
) -> PolicyContextSignal:
    if isinstance(signal, PolicyContextSignal):
        return signal
    if isinstance(signal, GovernanceMonitorEvent):
        return PolicyContextSignal(
            signal_id=signal.event_id,
            change_kind=str(signal.metadata.get("change_kind") or signal.event_type),
            description=signal.reason,
            severity_score=_severity_score_from_monitor(signal),
            history_count=int(signal.metadata.get("history_count") or 0),
            blocking_candidate=signal.severity == "block",
            affected_claim_ids=tuple(signal.affected_claim_ids),
            scope=normalize_scope(signal.scope),
            occurred_at=signal.occurred_at,
            metadata=dict(signal.metadata),
        )
    raw = dict(signal)
    return PolicyContextSignal(
        signal_id=str(raw.get("signal_id") or raw.get("event_id") or "policy-context-signal"),
        change_kind=str(raw.get("change_kind") or raw.get("context_type") or "context_change"),
        description=str(raw.get("description") or raw.get("reason") or "Policy context changed."),
        severity_score=float(raw.get("severity_score") or raw.get("score") or 0.0),
        history_count=int(raw.get("history_count") or raw.get("sample_count") or 0),
        blocking_candidate=bool(raw.get("blocking_candidate")),
        affected_claim_ids=tuple_to_list(_text_values(raw.get("affected_claim_ids"))),
        scope=normalize_scope(raw.get("scope") if isinstance(raw.get("scope"), Mapping) else None),
        occurred_at=_parse_time(raw.get("occurred_at") or raw.get("timestamp")),
        metadata=(
            dict(raw.get("metadata") or {})
            if isinstance(raw.get("metadata"), Mapping)
            else {}
        ),
    )


def _severity_score_from_monitor(event: GovernanceMonitorEvent) -> float:
    if event.severity == "block":
        return 1.0
    if event.severity == "warning":
        return 0.7
    return 0.1


def _parse_time(value: object) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def _text_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


__all__ = ["PolicyContextSignal", "detect_policy_context_drift"]
