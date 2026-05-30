"""Fairness drift detector over DDM and subgroup monitor streams."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from polisyos.ddm import ShiftDetectedEvent, ShiftRiskEvent

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
    from polisyos.scientist.governance.continuous.monitors import GovernanceMonitorEvent


class FairnessDriftSignal(BaseModel):
    """Normalized subgroup fairness drift signal consumed by the detector."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    signal_id: str = Field(min_length=1)
    metric_name: str = Field(min_length=1)
    observed_value: float
    threshold: float | None = None
    sample_count: int = Field(default=0, ge=0)
    affected_slices: tuple[str, ...] = Field(default=())
    affected_claim_ids: tuple[str, ...] = Field(default=())
    scope: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_event_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("affected_slices", "affected_claim_ids", mode="before")
    @classmethod
    def _coerce_text_tuple(cls, value: object) -> tuple[str, ...]:
        return tuple(tuple_to_list(_text_values(value)))

    @field_validator("occurred_at")
    @classmethod
    def _normalize_time(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


def detect_fairness_drift(
    *,
    decision_packet_ref: artifacts.ArtifactRef,
    signals: Sequence[
        FairnessDriftSignal | ShiftDetectedEvent | ShiftRiskEvent | Mapping[str, Any]
    ],
    slice_claim_map: Mapping[str, Sequence[str]] | None = None,
    scope: Mapping[str, Any] | None = None,
    balanced_memories: Sequence[Any] | None = None,
    sparse_history_policy: SparseHistoryPolicy = DEFAULT_SPARSE_HISTORY_POLICY,
    config: DetectorConfig | None = None,
    sequence: int = 0,
) -> DriftDetectionResult:
    """Emit fairness drift monitor events from subgroup monitor streams."""

    active_config = detector_config("fairness_drift", config)
    if not active_config.enabled:
        return disabled_result(family="fairness_drift", config=active_config)

    normalized = [
        _normalize_signal(signal, slice_claim_map=slice_claim_map, default_scope=scope)
        for signal in signals
    ]
    events: list[GovernanceMonitorEvent] = []
    for index, signal in enumerate(normalized):
        if not _is_adverse(signal):
            continue
        band = sparse_history_policy.band_for_count(signal.sample_count, adverse=True)
        blocking_candidate = True
        severity = severity_for_band(band, blocking_candidate=blocking_candidate)
        event_scope = normalize_scope(signal.scope or scope)
        memory_context = balanced_memory_context(
            balanced_memories,
            scope=event_scope,
            run_id="w9a-fairness-detector",
        )
        metadata = {
            "detector_family": "fairness_drift",
            "detector_id": active_config.detector_id,
            "feature_flag": active_config.feature_flag,
            "monitor_signal_ids": [signal.signal_id],
            "metric_name": signal.metric_name,
            "observed_value": signal.observed_value,
            "threshold": signal.threshold,
            "sample_count": signal.sample_count,
            "affected_slices": list(signal.affected_slices),
            "source_event_type": signal.source_event_type,
            **signal.metadata,
            **sparse_metadata(band=band, blocking_candidate=blocking_candidate),
        }
        if memory_context is not None:
            metadata["balanced_memory_context"] = memory_context
        events.append(
            build_detector_event(
                decision_packet_ref=decision_packet_ref,
                event_type="fairness_drift",
                severity=severity,
                scope=event_scope,
                affected_claim_ids=signal.affected_claim_ids,
                reason=_fairness_reason(signal),
                metadata=metadata,
                occurred_at=signal.occurred_at,
                sequence=sequence + index,
            )
        )

    return result(
        family="fairness_drift",
        config=active_config,
        events=events,
        evaluated_signal_count=len(normalized),
        metadata={"input_signal_count": len(signals)},
    )


def _normalize_signal(
    signal: FairnessDriftSignal | ShiftDetectedEvent | ShiftRiskEvent | Mapping[str, Any],
    *,
    slice_claim_map: Mapping[str, Sequence[str]] | None,
    default_scope: Mapping[str, Any] | None,
) -> FairnessDriftSignal:
    if isinstance(signal, FairnessDriftSignal):
        return signal
    if isinstance(signal, ShiftDetectedEvent):
        slices = tuple(item.slice for item in signal.affected_slices)
        return FairnessDriftSignal(
            signal_id=signal.event_id,
            metric_name=signal.signal,
            observed_value=signal.shift_severity,
            threshold=signal.threshold if signal.threshold is not None else 0.5,
            sample_count=min(signal.reference_window.n, signal.current_window.n),
            affected_slices=slices,
            affected_claim_ids=_claim_ids_for_slices(slices, slice_claim_map),
            scope=normalize_scope(default_scope),
            occurred_at=signal.timestamp,
            source_event_type=signal.event_type,
            metadata={
                "detector_id": signal.detector_id,
                "detector_family": signal.detector_family,
                "model_id": signal.model_id,
                "model_version": signal.model_version,
                "calibration_id": signal.calibration_id,
                "stationarity_regime_id": signal.stationarity_regime_id,
                "empirical_fp_rate": signal.empirical_fp_rate,
            },
        )
    if isinstance(signal, ShiftRiskEvent):
        slices = tuple(item.slice for item in signal.affected_slices)
        return FairnessDriftSignal(
            signal_id=signal.event_id,
            metric_name=signal.signal,
            observed_value=signal.risk_score,
            threshold=0.65 if signal.risk_level == "investigate" else 0.5,
            sample_count=0,
            affected_slices=slices,
            affected_claim_ids=_claim_ids_for_slices(slices, slice_claim_map),
            scope=normalize_scope(default_scope),
            occurred_at=signal.timestamp,
            source_event_type=signal.event_type,
            metadata={
                "shift_event_id": signal.shift_event_id,
                "risk_level": signal.risk_level,
                "calibration_id": signal.calibration_id,
            },
        )
    raw = dict(signal)
    slices = tuple_to_list(_text_values(raw.get("affected_slices")))
    return FairnessDriftSignal(
        signal_id=str(raw.get("signal_id") or raw.get("event_id") or "fairness-signal"),
        metric_name=str(raw.get("metric_name") or raw.get("metric") or "fairness_metric"),
        observed_value=float(raw.get("observed_value") or raw.get("risk_score") or 0.0),
        threshold=_optional_float(raw.get("threshold")),
        sample_count=int(raw.get("sample_count") or raw.get("history_count") or 0),
        affected_slices=tuple(slices),
        affected_claim_ids=tuple_to_list(
            _text_values(raw.get("affected_claim_ids"))
            or _claim_ids_for_slices(slices, slice_claim_map)
        ),
        scope=normalize_scope(
            raw.get("scope") if isinstance(raw.get("scope"), Mapping) else default_scope
        ),
        occurred_at=_parse_time(raw.get("occurred_at") or raw.get("timestamp")),
        source_event_type=_optional_text(raw.get("event_type")),
        metadata=(
            dict(raw.get("metadata") or {})
            if isinstance(raw.get("metadata"), Mapping)
            else {}
        ),
    )


def _is_adverse(signal: FairnessDriftSignal) -> bool:
    threshold = signal.threshold if signal.threshold is not None else 0.0
    return signal.observed_value > threshold


def _claim_ids_for_slices(
    slices: Sequence[str],
    slice_claim_map: Mapping[str, Sequence[str]] | None,
) -> tuple[str, ...]:
    if not slice_claim_map:
        return ()
    claim_ids: list[str] = []
    for affected_slice in slices:
        claim_ids.extend(str(item) for item in slice_claim_map.get(affected_slice, ()))
    return tuple(tuple_to_list(claim_ids))


def _fairness_reason(signal: FairnessDriftSignal) -> str:
    threshold = "unset" if signal.threshold is None else str(signal.threshold)
    return (
        f"Fairness drift detector observed {signal.metric_name}="
        f"{signal.observed_value} above threshold {threshold}."
    )


def _parse_time(value: object) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


__all__ = ["FairnessDriftSignal", "detect_fairness_drift"]
