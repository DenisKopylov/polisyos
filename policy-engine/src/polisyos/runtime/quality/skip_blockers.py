"""Scorecard gates for skipped optional analytic nodes."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from polisyos.core.contracts.skip_blockers import (
    SkipBlockerContractError,
    SkippedNodeBlocker,
    classify_optional_analytic_node,
    deserialize_skip_blocker_record,
    evaluate_skip_blocker_policy,
)


@dataclass(frozen=True)
class SkippedAnalyticNode:
    """A skipped workflow node that can affect authority-bearing outputs."""

    alias: str | None
    node_id: str | None
    node_kind: str
    phase: str | None
    reason: str | None
    missing_input: str | None
    skip_blocker: SkippedNodeBlocker | None
    skip_blocker_error: SkipBlockerContractError | None = None


def skip_blocker_gate_from_payloads(
    *,
    canary_kind: str,
    job_payload: Mapping[str, Any] | None,
    run_payload: Mapping[str, Any] | None,
    quality_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build a scorecard gate for skipped optional analytic node semantics."""

    payloads = (job_payload or {}, run_payload or {}, quality_evidence or {})
    for skipped in _iter_skipped_analytic_nodes(payloads):
        if skipped.skip_blocker_error is not None:
            return _skip_gate(
                code=skipped.skip_blocker_error.code,
                phase=skipped.phase or "workflow_report",
                message=skipped.skip_blocker_error.message,
                next_action=(
                    "Persist the full Phase 2.5 skip/blocker contract before scorecard "
                    "or approval consumes this workflow report."
                ),
            )
        if skipped.skip_blocker is None:
            return _skip_gate(
                code="skipped_analytic_node_blocker_missing",
                phase=skipped.phase or "workflow_report",
                message=(
                    f"Skipped {skipped.node_kind} node "
                    f"{skipped.alias or skipped.node_id or 'unknown'} cannot be "
                    "summarized as completed without blocker semantics."
                ),
                next_action=(
                    "Persist reason, missing_input, owner, phase, downstream_impact, "
                    "allowed_profile, and closeout/scorecard/approval/public-export "
                    "blocking policies for the skipped node."
                ),
            )
        decision = evaluate_skip_blocker_policy(
            skipped.skip_blocker,
            active_profile=canary_kind,
            surface="scorecard",
        )
        if decision.blocking:
            return _skip_gate(
                code=decision.code or "skipped_analytic_node_blocks_scorecard",
                phase=skipped.skip_blocker.phase,
                message=decision.reason,
                next_action=(
                    skipped.skip_blocker.next_action
                    or "Provide the missing input before serious scorecard closeout."
                ),
            )
    return None


def _iter_skipped_analytic_nodes(
    payloads: Iterable[Mapping[str, Any]],
) -> Iterable[SkippedAnalyticNode]:
    for payload in payloads:
        yield from _iter_workflow_report_skips(payload)
        yield from _iter_explicit_skipped_nodes(payload)


def _iter_workflow_report_skips(payload: Mapping[str, Any]) -> Iterable[SkippedAnalyticNode]:
    for report in _nested_find_values(payload, "workflow_report"):
        if not isinstance(report, Mapping):
            continue
        nodes = report.get("nodes")
        if not isinstance(nodes, list):
            continue
        for raw in nodes:
            if not isinstance(raw, Mapping):
                continue
            skipped = _skipped_node_from_mapping(raw, default_phase="workflow_report")
            if skipped is not None:
                yield skipped


def _iter_explicit_skipped_nodes(payload: Mapping[str, Any]) -> Iterable[SkippedAnalyticNode]:
    for key in ("skipped_nodes", "skipped_analytic_nodes"):
        for value in _nested_find_values(payload, key):
            if isinstance(value, list):
                for raw in value:
                    if not isinstance(raw, Mapping):
                        continue
                    skipped = _skipped_node_from_mapping(raw, default_phase=key)
                    if skipped is not None:
                        yield skipped
            elif isinstance(value, Mapping):
                for raw in value.values():
                    if not isinstance(raw, Mapping):
                        continue
                    skipped = _skipped_node_from_mapping(raw, default_phase=key)
                    if skipped is not None:
                        yield skipped


def _skipped_node_from_mapping(
    raw: Mapping[str, Any],
    *,
    default_phase: str,
) -> SkippedAnalyticNode | None:
    status = str(raw.get("status") or "").casefold()
    if status not in {"skip", "skipped"}:
        return None
    alias = _string_or_none(raw.get("alias") or raw.get("name"))
    node_id = _string_or_none(raw.get("node_id") or raw.get("id"))
    phase = _string_or_none(raw.get("phase")) or default_phase
    node_kind = classify_optional_analytic_node(
        alias=alias,
        node_id=node_id,
        phase=phase,
        node_kind=_string_or_none(raw.get("node_kind")),
    )
    if node_kind is None:
        return None
    blocker, blocker_error = _coerce_skip_blocker(raw)
    return SkippedAnalyticNode(
        alias=alias,
        node_id=node_id,
        node_kind=node_kind,
        phase=phase,
        reason=_string_or_none(raw.get("skip_reason") or raw.get("reason")),
        missing_input=_string_or_none(raw.get("missing_input")),
        skip_blocker=blocker,
        skip_blocker_error=blocker_error,
    )


def _coerce_skip_blocker(
    raw: Mapping[str, Any],
) -> tuple[SkippedNodeBlocker | None, SkipBlockerContractError | None]:
    for key in ("skip_blocker", "skip_blocker_record", "skipped_node_blocker"):
        candidate = raw.get(key)
        if candidate is None:
            continue
        if not isinstance(candidate, Mapping):
            return None, SkipBlockerContractError(
                "skip_blocker_contract_invalid",
                f"Skipped node blocker must be a mapping under {key}.",
                field=key,
            )
        try:
            return deserialize_skip_blocker_record(candidate), None
        except SkipBlockerContractError as exc:
            return None, exc
        except (TypeError, ValueError) as exc:
            return None, SkipBlockerContractError(
                "skip_blocker_contract_invalid",
                str(exc),
                field=key,
            )
    return None, None


def _nested_find_values(payload: object, key: str) -> Iterable[object]:
    if isinstance(payload, Mapping):
        for payload_key, value in payload.items():
            if str(payload_key) == key:
                yield value
            yield from _nested_find_values(value, key)
    elif isinstance(payload, list):
        for value in payload:
            yield from _nested_find_values(value, key)


def _skip_gate(
    *,
    code: str,
    phase: str,
    message: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "name": "skipped_analytic_nodes_have_blockers",
        "stage": "scientist",
        "code": code,
        "status": "fail",
        "layer": "skip_blocker_semantics",
        "phase": phase,
        "message": message,
        "evidence_ref": "workflow_report",
        "next_action": next_action,
        "blocking": True,
    }


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = ["SkippedAnalyticNode", "skip_blocker_gate_from_payloads"]
