"""Calibration drift detector over W2.E longitudinal calibration ledgers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .common import (
    DEFAULT_SPARSE_HISTORY_POLICY,
    DetectorConfig,
    DriftDetectionResult,
    SparseHistoryBand,
    SparseHistoryPolicy,
    balanced_memory_context,
    build_detector_event,
    detector_config,
    disabled_result,
    normalize_scope,
    result,
    scope_matches,
    severity_for_band,
    sparse_metadata,
    tuple_to_list,
)

if TYPE_CHECKING:
    from polisyos.core import artifacts
    from polisyos.scientist.governance.continuous.monitors import GovernanceMonitorEvent


def detect_calibration_drift(
    *,
    decision_packet_ref: artifacts.ArtifactRef,
    calibration_ledger: Mapping[str, Any] | object,
    target_scope: Mapping[str, Any] | None = None,
    target_claim_id: str | None = None,
    balanced_memories: Sequence[Any] | None = None,
    sparse_history_policy: SparseHistoryPolicy = DEFAULT_SPARSE_HISTORY_POLICY,
    config: DetectorConfig | None = None,
    sequence: int = 0,
) -> DriftDetectionResult:
    """Emit calibration drift monitor events from longitudinal ledger influence.

    Historical calibration remains future influence. The detector emits review
    or reissue signals, but the event metadata keeps the historical-prior
    boundary explicit so no consumer can treat the ledger as claim evidence.
    """

    active_config = detector_config("calibration_drift", config)
    if not active_config.enabled:
        return disabled_result(family="calibration_drift", config=active_config)

    payload = _ledger_payload(calibration_ledger)
    influence_records = [
        record
        for record in _mapping_rows(payload.get("influence_records"))
        if _record_matches(record, target_scope=target_scope, target_claim_id=target_claim_id)
    ]
    events: list[GovernanceMonitorEvent] = []
    for index, record in enumerate(influence_records):
        status = str(record.get("influence_status") or "no_effect")
        reason_codes = tuple_to_list(_text_values(record.get("reason_codes")))
        if status == "no_effect" and not reason_codes:
            continue
        band = _band_from_record(record, sparse_history_policy)
        blocking_candidate = status == "scoped_block" or bool(record.get("blocking_permitted"))
        severity = severity_for_band(band, blocking_candidate=blocking_candidate)
        scope = normalize_scope(record.get("scope") or target_scope)
        claim_ids = tuple_to_list(
            [target_claim_id or str(record.get("target_claim_id") or "")]
        )
        memory_context = balanced_memory_context(
            balanced_memories,
            scope=scope,
            run_id=str(record.get("target_run_id") or "w9a-calibration-detector"),
        )
        metadata = {
            "detector_family": "calibration_drift",
            "detector_id": active_config.detector_id,
            "feature_flag": active_config.feature_flag,
            "history_state": record.get("history_state"),
            "influence_status": status,
            "reason_codes": reason_codes,
            "source_ledger_ref": record.get("source_ledger_ref")
            or payload.get("calibration_ledger_ref"),
            "source_entry_refs": tuple_to_list(_text_values(record.get("source_entry_refs"))),
            "authority_boundary": record.get("authority_boundary") or {},
            "permitted_effects": tuple_to_list(_text_values(record.get("permitted_effects"))),
            "current_run_evidence_effect": "none",
            "claim_evidence_admissible": False,
            **sparse_metadata(band=band, blocking_candidate=blocking_candidate),
        }
        if memory_context is not None:
            metadata["balanced_memory_context"] = memory_context
        event = build_detector_event(
            decision_packet_ref=decision_packet_ref,
            event_type="calibration_drift",
            severity=severity,
            scope=scope,
            affected_claim_ids=claim_ids,
            reason=_calibration_reason(record, band=band, status=status),
            metadata=metadata,
            occurred_at=_ledger_time(payload),
            sequence=sequence + index,
        )
        events.append(event)

    return result(
        family="calibration_drift",
        config=active_config,
        events=events,
        evaluated_signal_count=len(influence_records),
        metadata={
            "ledger_status": payload.get("status"),
            "calibration_ledger_ref": payload.get("calibration_ledger_ref"),
        },
    )


def _ledger_payload(ledger: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(ledger, Mapping):
        return dict(ledger)
    model_dump = getattr(ledger, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json", exclude_none=True)
        return dict(payload) if isinstance(payload, Mapping) else {}
    try:
        return dict(ledger)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return {}


def _record_matches(
    record: Mapping[str, Any],
    *,
    target_scope: Mapping[str, Any] | None,
    target_claim_id: str | None,
) -> bool:
    if target_claim_id is not None and record.get("target_claim_id") not in {
        None,
        target_claim_id,
    }:
        return False
    record_scope = record.get("scope") if isinstance(record.get("scope"), Mapping) else None
    return scope_matches(record_scope, target_scope)


def _band_from_record(
    record: Mapping[str, Any],
    sparse_history_policy: SparseHistoryPolicy,
) -> SparseHistoryBand:
    history_state = str(record.get("history_state") or "")
    if history_state == "insufficient_history":
        return "Insufficient"
    if history_state == "thin_history":
        return "Thin"
    if history_state == "emerging_history":
        return "Forming"
    if history_state == "mature_history":
        adverse = str(record.get("influence_status") or "no_effect") != "no_effect" or bool(
            _text_values(record.get("reason_codes"))
        )
        if adverse:
            return "Mature adverse"
    return sparse_history_policy.band_for_count(
        len(_text_values(record.get("source_entry_refs"))),
        adverse=True,
    )


def _calibration_reason(
    record: Mapping[str, Any],
    *,
    band: SparseHistoryBand,
    status: str,
) -> str:
    reason_codes = tuple_to_list(_text_values(record.get("reason_codes")))
    joined_codes = ", ".join(reason_codes) if reason_codes else status
    return f"Calibration drift detector observed {band} history: {joined_codes}."


def _ledger_time(payload: Mapping[str, Any]) -> datetime | None:
    raw = payload.get("generated_at")
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.astimezone(UTC)
    return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(UTC)


def _mapping_rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list | tuple):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _text_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


__all__ = ["detect_calibration_drift"]
