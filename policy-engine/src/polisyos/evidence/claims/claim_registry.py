"""Read-only claim-registry normalization shared outside runtime persistence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

SCHEMA_VERSION = "policyos.runtime.claim_registry.v1"
REPORT_KIND = "runtime.claim_registry"
REPORT_REF_KEY = "runtime_claim_registry_ref"

_REF_KEYS = (
    "scenario_requirement_refs",
    "data_refs",
    "selected_norm_refs",
    "rejected_norm_refs",
    "legal_authority_record_refs",
    "legal_authority_blocker_refs",
    "method_output_refs",
    "portfolio_refs",
    "argument_refs",
    "warrant_refs",
    "rebuttal_refs",
    "counter_evidence_refs",
    "limitation_refs",
    "accepted_deficit_refs",
    "blocker_refs",
    "independence_refs",
    "synthesis_refs",
    "ir_analytics_refs",
    "ir_certificate_refs",
    "negative_certificate_refs",
    "proof_composability_refs",
    "uncertainty_refs",
    "baseline_refs",
    "alternative_refs",
    "comparison_refs",
    "conflict_refs",
)


def normalize_runtime_claim_registry(
    claim_registry: Mapping[str, Any] | None,
    *,
    claims: Sequence[Mapping[str, Any]] | None = None,
    normative_evidence: Mapping[str, Any] | None = None,
    fabric_retrieval_trace: Mapping[str, Any] | None = None,
    foundry_method_report: Mapping[str, Any] | None = None,
    ir_analytics_bridge: Mapping[str, Any] | None = None,
    run_id: str | None = None,
    hypothesis_ledger: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize a runtime claim registry without runtime-only enrichment."""

    _ = (
        normative_evidence,
        fabric_retrieval_trace,
        foundry_method_report,
        ir_analytics_bridge,
        hypothesis_ledger,
    )
    payload = dict(claim_registry or {})
    rows = [
        _normalize_entry_row(dict(row), index=index, run_id=run_id)
        for index, row in enumerate(_claim_rows(payload))
    ]
    rows_by_id = {str(row["claim_id"]): row for row in rows if row.get("claim_id")}
    issues: list[dict[str, Any]] = []
    for index, claim in enumerate(claims or ()):
        if not isinstance(claim, Mapping) or not _is_major_claim(claim):
            continue
        claim_id = _claim_id(claim, index)
        if claim_id not in rows_by_id:
            issues.append(
                {
                    "code": "runtime_claim_registry_entry_missing",
                    "claim_id": claim_id,
                    "missing_evidence_type": "claim_registry_entry",
                    "severity": "fail",
                    "message": (
                        f"Major claim {claim_id} has no runtime claim registry entry."
                    ),
                }
            )
        if bool(claim.get("requires_ir_analytics")) and not _bridge_payload(
            payload,
            ir_analytics_bridge,
        ):
            issues.append(
                {
                    "code": "runtime_claim_registry_ir_analytics_bridge_missing",
                    "claim_id": claim_id,
                    "missing_evidence_type": "ir_analytics_bridge",
                    "severity": "fail",
                    "message": (
                        f"Major claim {claim_id} requires IR analytics but no "
                        "claim bridge is attached."
                    ),
                }
            )
    bridge = _bridge_payload(payload, ir_analytics_bridge)
    existing_summary = (
        dict(payload.get("summary")) if isinstance(payload.get("summary"), Mapping) else {}
    )
    bridge_summary = {}
    if isinstance(bridge, Mapping) and isinstance(bridge.get("summary"), Mapping):
        bridge_summary = dict(bridge.get("summary") or {})
    summary = {
        **existing_summary,
        "claim_count": len(rows),
        "major_claim_count": sum(
            1 for claim in claims or () if isinstance(claim, Mapping) and _is_major_claim(claim)
        ),
        "entry_count": len(rows),
        "issue_count": len(issues),
        "global_norm_ref_count": len(_global_norm_refs(normative_evidence)),
        "global_method_ref_count": len(_global_method_refs(foundry_method_report)),
        "generic_global_method_ref_count": len(
            [
                ref
                for ref in _global_method_refs(foundry_method_report)
                if _is_generic_method_ref(ref)
            ]
        ),
        "selected_data_ref_count": len(_global_data_refs(fabric_retrieval_trace)),
    }
    if bridge_summary:
        summary.update(
            {
                "ir_analytics_binding_count": int(bridge_summary.get("binding_count") or 0),
                "ir_analytics_blocked_claim_count": int(
                    bridge_summary.get("blocked_claim_count") or 0
                ),
                "ir_analytics_bridge_status": bridge.get("status"),
            }
        )
    result = {
        **payload,
        "schema_version": SCHEMA_VERSION,
        "registry_kind": REPORT_KIND,
        "status": "blocked" if issues else "pass",
        "claims": rows,
        "summary": summary,
        "issues": issues,
    }
    registry_ref = _text(payload.get(REPORT_REF_KEY) or payload.get("registry_ref"))
    if registry_ref:
        result[REPORT_REF_KEY] = registry_ref
    return result


def claim_registry_rows_by_id(
    claim_registry: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Return normalized registry rows keyed by claim id."""

    if not isinstance(claim_registry, Mapping):
        return {}
    rows = {}
    for index, row in enumerate(_claim_rows(claim_registry)):
        normalized = _normalize_entry_row(dict(row), index=index, run_id=None)
        claim_id = _text(normalized.get("claim_id"))
        if claim_id:
            rows[claim_id] = normalized
    return rows


def apply_runtime_claim_registry_to_claim(
    claim: Mapping[str, Any],
    registry_entry: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Project a registry entry onto a claim for downstream validators."""

    merged = dict(claim)
    if not isinstance(registry_entry, Mapping):
        return merged
    entry = _normalize_entry_row(dict(registry_entry), index=0, run_id=None)
    evidence_graph = (
        dict(merged.get("evidence_graph"))
        if isinstance(merged.get("evidence_graph"), Mapping)
        else {}
    )
    for key in _REF_KEYS:
        refs = _as_refs(entry.get(key))
        if refs:
            merged[key] = refs
            evidence_graph[key] = refs
    if entry.get("selected_norm_refs"):
        merged["norm_refs"] = _as_refs(entry.get("selected_norm_refs"))
    if entry.get("method_output_refs"):
        merged["method_refs"] = _as_refs(entry.get("method_output_refs"))
    if evidence_graph:
        merged["evidence_graph"] = evidence_graph
    merged["runtime_claim_registry_entry"] = {
        key: value
        for key, value in entry.items()
        if key in {"claim_id", "claim_ref", "runtime_event_ref", *_REF_KEYS}
    }
    return merged


def _claim_rows(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    for key in ("claims", "entries", "claim_registry_entries"):
        rows = payload.get(key)
        if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes, bytearray)):
            return tuple(row for row in rows if isinstance(row, Mapping))
    return ()


def _bridge_payload(
    payload: Mapping[str, Any],
    bridge: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    if isinstance(bridge, Mapping):
        return bridge
    embedded = payload.get("ir_analytics_bridge")
    return embedded if isinstance(embedded, Mapping) else None


def _global_norm_refs(value: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    refs: list[str] = []
    for key in ("applied_norms", "selected_norms", "norms"):
        rows = value.get(key)
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
            continue
        for row in rows:
            if isinstance(row, Mapping):
                ref = _text(row.get("norm_id")) or _text(row.get("id")) or _text(row.get("ref"))
                if ref:
                    refs.append(ref)
    return list(dict.fromkeys(refs))


def _global_method_refs(value: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    refs: list[str] = []
    for key in ("selected_methods", "methods", "method_outputs"):
        rows = value.get(key)
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
            continue
        for row in rows:
            if isinstance(row, Mapping):
                ref = (
                    _text(row.get("method_id"))
                    or _text(row.get("id"))
                    or _text(row.get("method_ref"))
                )
                if ref:
                    refs.append(ref)
    return list(dict.fromkeys(refs))


def _global_data_refs(value: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    refs: list[str] = []
    rows = value.get("selected_sources")
    if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes, bytearray)):
        for row in rows:
            if isinstance(row, Mapping):
                ref = _text(row.get("source_id")) or _text(row.get("source_ref"))
                if ref:
                    refs.append(ref)
    return list(dict.fromkeys(refs))


def _is_generic_method_ref(value: str) -> bool:
    lowered = value.casefold()
    return (
        "generic" in lowered
        or lowered in {"foundry.execute", "foundry.method", "foundry.run"}
        or lowered.startswith("foundry.execute.")
    )


def _normalize_entry_row(
    row: Mapping[str, Any],
    *,
    index: int,
    run_id: str | None,
) -> dict[str, Any]:
    normalized = dict(row)
    normalized["claim_id"] = _claim_id(normalized, index)
    if run_id and "run_id" not in normalized:
        normalized["run_id"] = run_id
    for key in _REF_KEYS:
        if key in normalized:
            normalized[key] = _as_refs(normalized.get(key))
    return normalized


def _claim_id(claim: Mapping[str, Any], index: int) -> str:
    return (
        _text(claim.get("claim_id"))
        or _text(claim.get("id"))
        or _text(claim.get("claim_ref"))
        or f"claim_{index + 1}"
    )


def _is_major_claim(claim: Mapping[str, Any]) -> bool:
    return bool(claim.get("major", True))


def _as_refs(value: object) -> list[str]:
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [str(item) for item in value if str(item)]
    return []


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
