"""Source invalidation detector over Data Forge snapshot manifests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .common import (
    DEFAULT_SPARSE_HISTORY_POLICY,
    DetectorConfig,
    DriftDetectionResult,
    SparseHistoryPolicy,
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


def detect_source_invalidation(
    *,
    decision_packet_ref: artifacts.ArtifactRef,
    current_manifest: Mapping[str, Any],
    previous_manifest: Mapping[str, Any] | None = None,
    snapshot_history_count: int = 0,
    required_roles: Sequence[str] = (),
    sparse_history_policy: SparseHistoryPolicy = DEFAULT_SPARSE_HISTORY_POLICY,
    config: DetectorConfig | None = None,
    sequence: int = 0,
) -> DriftDetectionResult:
    """Emit source invalidation monitor events from snapshot manifest changes."""

    active_config = detector_config("source_invalidation", config)
    if not active_config.enabled:
        return disabled_result(family="source_invalidation", config=active_config)

    current_bindings = _bindings_by_role(current_manifest)
    previous_bindings = _bindings_by_role(previous_manifest or {})
    findings: list[dict[str, Any]] = []
    for role, binding in current_bindings.items():
        failed_gates = _failed_quality_gates(binding)
        if failed_gates:
            findings.append(
                _finding(
                    invalidation_type="quality_gate_failed",
                    role=role,
                    binding=binding,
                    failed_gates=failed_gates,
                    blocking_candidate=True,
                )
            )
        previous = previous_bindings.get(role)
        if previous is not None and _optional_text(previous.get("data_hash")) != _optional_text(
            binding.get("data_hash")
        ):
            findings.append(
                _finding(
                    invalidation_type="data_hash_changed",
                    role=role,
                    binding=binding,
                    previous_binding=previous,
                    blocking_candidate=False,
                )
            )
    for role in required_roles:
        if role in current_bindings:
            continue
        findings.append(
            {
                "invalidation_type": "required_snapshot_role_missing",
                "role": role,
                "scope": {"data_forge_role": role},
                "affected_claim_ids": [],
                "blocking_candidate": True,
                "metadata": {
                    "missing_required_role": role,
                    "snapshot_id": current_manifest.get("snapshot_id"),
                },
            }
        )

    events: list[GovernanceMonitorEvent] = []
    for index, item in enumerate(findings):
        band = sparse_history_policy.band_for_count(snapshot_history_count, adverse=True)
        blocking_candidate = bool(item["blocking_candidate"])
        severity = severity_for_band(band, blocking_candidate=blocking_candidate)
        metadata = {
            "detector_family": "source_invalidation",
            "detector_id": active_config.detector_id,
            "feature_flag": active_config.feature_flag,
            "invalidation_type": item["invalidation_type"],
            "snapshot_history_count": snapshot_history_count,
            "snapshot_id": current_manifest.get("snapshot_id"),
            "release_id": current_manifest.get("release_id"),
            **dict(item.get("metadata") or {}),
            **sparse_metadata(band=band, blocking_candidate=blocking_candidate),
        }
        events.append(
            build_detector_event(
                decision_packet_ref=decision_packet_ref,
                event_type="source_invalidation",
                severity=severity,
                scope=item["scope"],
                affected_claim_ids=item["affected_claim_ids"],
                reason=_source_reason(item),
                metadata=metadata,
                occurred_at=_manifest_time(current_manifest),
                sequence=sequence + index,
            )
        )

    return result(
        family="source_invalidation",
        config=active_config,
        events=events,
        evaluated_signal_count=len(findings),
        metadata={
            "snapshot_id": current_manifest.get("snapshot_id"),
            "binding_count": len(current_bindings),
        },
    )


def _finding(
    *,
    invalidation_type: str,
    role: str,
    binding: Mapping[str, Any],
    failed_gates: Sequence[Mapping[str, Any]] = (),
    previous_binding: Mapping[str, Any] | None = None,
    blocking_candidate: bool,
) -> dict[str, Any]:
    scope = normalize_scope(
        {
            "data_forge_role": role,
            "read_api_surface": binding.get("read_api_surface"),
            "authority_level": _authority_level(binding),
            "time_role": _time_role(binding),
        }
    )
    metadata = {
        "role": role,
        "data_hash": binding.get("data_hash"),
        "snapshot_ref": binding.get("snapshot_ref"),
        "manifest_ref": binding.get("manifest_ref"),
        "runtime_event_ref": binding.get("runtime_event_ref"),
        "failed_quality_gates": [dict(gate) for gate in failed_gates],
    }
    if previous_binding is not None:
        metadata["previous_data_hash"] = previous_binding.get("data_hash")
        metadata["previous_snapshot_ref"] = previous_binding.get("snapshot_ref")
    return {
        "invalidation_type": invalidation_type,
        "role": role,
        "scope": scope,
        "affected_claim_ids": _claim_ids(binding),
        "blocking_candidate": blocking_candidate,
        "metadata": metadata,
    }


def _bindings_by_role(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = manifest.get("bindings")
    if not isinstance(rows, list | tuple):
        return {}
    by_role: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        role = _optional_text(row.get("role"))
        if role is None:
            continue
        by_role[role] = row
    return by_role


def _failed_quality_gates(binding: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    gates = binding.get("quality_gates")
    if not isinstance(gates, list | tuple):
        return []
    failed: list[Mapping[str, Any]] = []
    for gate in gates:
        if not isinstance(gate, Mapping):
            continue
        status = str(gate.get("status") or "").casefold()
        if status not in {"pass", "passed", "ok", "success"}:
            failed.append(gate)
    return failed


def _claim_ids(binding: Mapping[str, Any]) -> list[str]:
    rows = binding.get("claim_requirement_bindings")
    if not isinstance(rows, list | tuple):
        return []
    claim_ids: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        claim_ids.extend(_text_values(row.get("claim_id")))
        claim_ids.extend(_text_values(row.get("claim_ids")))
    return tuple_to_list(claim_ids)


def _authority_level(binding: Mapping[str, Any]) -> str | None:
    rows = binding.get("claim_requirement_bindings")
    if not isinstance(rows, list | tuple) or not rows:
        return None
    first = rows[0]
    if not isinstance(first, Mapping):
        return None
    return _optional_text(first.get("authority_level"))


def _time_role(binding: Mapping[str, Any]) -> str | None:
    rows = binding.get("claim_requirement_bindings")
    if not isinstance(rows, list | tuple) or not rows:
        return None
    first = rows[0]
    if not isinstance(first, Mapping):
        return None
    return _optional_text(first.get("time_role"))


def _source_reason(item: Mapping[str, Any]) -> str:
    role = item.get("role")
    invalidation_type = item.get("invalidation_type")
    return f"Data Forge source invalidation detected for {role}: {invalidation_type}."


def _manifest_time(manifest: Mapping[str, Any]) -> datetime | None:
    raw = manifest.get("generated_at")
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.astimezone(UTC)
    return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(UTC)


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


__all__ = ["detect_source_invalidation"]
