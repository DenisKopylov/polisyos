"""Shared Policy Design Case projection labels for non-runtime artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from polisyos.core.contracts.policy_design_case_projection import (
    POLICY_DESIGN_CASE_PROJECTION_SCHEMA_VERSION,
)

_LEGACY_PROJECTION_POLICY = "reads_policy_design_case_only"
_RUNTIME_GRAPH_PROJECTION_POLICY = "reads_runtime_policy_design_case_graph"


class PolicyDesignCaseProjectionError(ValueError):
    """Fail-closed projection-boundary violation."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


def build_policy_design_case_projection_semantics(
    *,
    policy_design_case: Mapping[str, Any],
    surface: str,
    source_payload: Mapping[str, Any] | None = None,
    source_ref: str | None = None,
    generated_at: datetime | None = None,
    audience: str | None = None,
    closeout_verdict: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a projection label that reads case authority without minting it."""

    source = dict(source_payload or {})
    _assert_projection_source_safe(source, surface=surface)
    closeout = (
        dict(closeout_verdict)
        if isinstance(closeout_verdict, Mapping)
        else dict(policy_design_case.get("closeout_verdict") or {})
        if isinstance(policy_design_case.get("closeout_verdict"), Mapping)
        else {}
    )
    states = _states_for_projection(policy_design_case, source, closeout)
    primary_state = _primary_state(states)
    generated = generated_at or datetime.now(UTC)
    return {
        "schema_version": POLICY_DESIGN_CASE_PROJECTION_SCHEMA_VERSION,
        "projection_policy": _LEGACY_PROJECTION_POLICY,
        "authority_role": "projection_only",
        "surface": str(surface),
        "audience": str(audience or "operator"),
        "primary_state": primary_state,
        "states": states,
        "labels": [
            {
                "label": state,
                "authority_role": "projection_only",
                "projection_policy": _LEGACY_PROJECTION_POLICY,
            }
            for state in states
        ],
        "source_state": {
            "source_ref": source_ref,
            "source_status": source.get("status"),
            "source_publishability": source.get("publishability"),
            "policy_design_case_id": policy_design_case.get("case_id")
            or policy_design_case.get("policy_design_case_id"),
        },
        "source_authority_refs": {
            "source_ref": source_ref,
            "closeout_ref": closeout.get("closeout_ref"),
        },
        "generated_at": generated.isoformat(),
        "may_be_used_for": [
            "api_display",
            "dashboard_display",
            "external_explanation",
            "operator_triage",
            "public_audit",
        ],
        "may_not_be_used_for": [
            "approval_authority",
            "claim_authority",
            "runtime_closeout_authority",
            "scorecard_authority",
        ],
    }


def build_policy_design_case_projection_from_runtime_graph(
    *,
    runtime_pdc_graph: Mapping[str, Any] | object,
    surface: str,
    generated_at: datetime | None = None,
    audience: str | None = None,
) -> dict[str, Any]:
    """Build a projection from a graph-like object without importing runtime."""

    graph = _as_mapping(runtime_pdc_graph)
    profile = _as_mapping(graph.get("policy_design_case_profile"))
    if not profile:
        raise PolicyDesignCaseProjectionError(
            "runtime_pdc_graph_policy_design_case_missing",
            "Projection-from-graph requires a Policy Design Case profile.",
        )
    projection = build_policy_design_case_projection_semantics(
        policy_design_case=profile,
        surface=surface,
        source_payload={
            "status": graph.get("status"),
            "closeout_verdict": graph.get("closeout_verdict"),
            "graph_ref": graph.get("graph_ref"),
        },
        source_ref=_text(graph.get("graph_ref")),
        generated_at=generated_at,
        audience=audience,
        closeout_verdict=_as_mapping(graph.get("closeout_verdict")),
    )
    projection["projection_policy"] = _RUNTIME_GRAPH_PROJECTION_POLICY
    for label in projection["labels"]:
        label["projection_policy"] = _RUNTIME_GRAPH_PROJECTION_POLICY
    projection["source_state"] = {
        **dict(projection.get("source_state") or {}),
        "runtime_pdc_graph_ref": graph.get("graph_ref"),
        "runtime_pdc_graph_schema_version": graph.get("schema_version"),
        "runtime_pdc_graph_projection_policy": graph.get("projection_source_policy"),
    }
    projection["source_authority_refs"] = {
        **dict(projection.get("source_authority_refs") or {}),
        "runtime_pdc_graph_ref": graph.get("graph_ref"),
        "runtime_pdc_graph_event_ref": graph.get("runtime_event_ref"),
    }
    return projection


def _states_for_projection(
    policy_design_case: Mapping[str, Any],
    source_payload: Mapping[str, Any],
    closeout_verdict: Mapping[str, Any],
) -> list[str]:
    states: list[str] = []
    if str(source_payload.get("publishability") or "").casefold() == "blocked":
        states.append("blocked")
    if str(closeout_verdict.get("status") or "").casefold() in {"blocked", "fail", "failed"}:
        states.append("blocked")
    if bool(policy_design_case.get("contested")) or bool(source_payload.get("contested")):
        states.append("contested")
    if not states:
        states.append("publishable")
    return list(dict.fromkeys(states))


def _primary_state(states: Sequence[str]) -> str:
    for candidate in ("blocked", "contested", "stale", "draft", "redacted", "publishable"):
        if candidate in states:
            return candidate
    return str(states[0] if states else "projection_only")


def _assert_projection_source_safe(source_payload: Mapping[str, Any], *, surface: str) -> None:
    role = str(source_payload.get("authority_role") or "").casefold()
    if role and role not in {"projection", "projection_only", "final_decision_artifact"}:
        raise PolicyDesignCaseProjectionError(
            "policy_design_projection_source_mints_authority",
            f"Projection source for {surface} has authority_role={role!r}.",
        )


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json", exclude_none=True)
        return dict(payload) if isinstance(payload, Mapping) else {}
    return {}


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None
