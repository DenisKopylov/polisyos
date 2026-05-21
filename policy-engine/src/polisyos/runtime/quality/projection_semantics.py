"""Policy Design Case projection semantics for user-facing surfaces."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from polisyos.runtime.quality.assurance_case import validate_policy_design_case_profile

POLICY_DESIGN_CASE_PROJECTION_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.projection_semantics.v1"
)
PROJECTION_STATES = (
    "draft",
    "projection_only",
    "redacted",
    "stale",
    "contested",
    "blocked",
    "publishable",
)
_PRIMARY_STATE_ORDER = (
    "blocked",
    "contested",
    "stale",
    "draft",
    "redacted",
    "publishable",
    "projection_only",
)
_SOURCE_AUTHORITY_ROLES_THAT_MINT_AUTHORITY = frozenset(
    {
        "approval_input",
        "producer_authority",
        "readiness_input",
        "runtime_blocker",
        "scorecard_input",
    }
)
_ALLOWED_FINAL_ARTIFACT_SOURCE_ROLES = frozenset(
    {
        "",
        "diagnostic_only",
        "final_decision_artifact",
        "not_authoritative",
        "packaging_only",
        "projection",
        "projection_only",
    }
)
_MAY_NOT_BE_USED_FOR = (
    "approval_authority",
    "claim_authority",
    "provider_credential_validation",
    "runtime_closeout_authority",
    "scorecard_authority",
    "tenant_identity_resolution",
)
_MAY_BE_USED_FOR = (
    "api_display",
    "dashboard_display",
    "external_explanation",
    "operator_triage",
    "public_audit",
)


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
) -> dict[str, Any]:
    """Build projection labels that read, but cannot create, case authority."""

    validated_case = validate_policy_design_case_profile(policy_design_case)
    source = dict(source_payload or {})
    _assert_source_is_projection_safe(source)
    states = _projection_states(
        validated_case,
        source_payload=source,
        surface=surface,
    )
    primary_state = _primary_state(states)
    authority_chain = _mapping(validated_case.get("authority_chain"))
    projection = {
        "schema_version": POLICY_DESIGN_CASE_PROJECTION_SCHEMA_VERSION,
        "generated_at": _utc(generated_at).isoformat(),
        "surface": _text(surface) or "unknown_projection_surface",
        "primary_state": primary_state,
        "states": list(states),
        "labels": [
            {
                "state": state,
                "label": _state_label(state),
                "authority_role": "projection_only",
                "source_authority": "policy_design_case",
            }
            for state in states
        ],
        "authority_role": "projection_only",
        "projection_policy": "reads_policy_design_case_only",
        "evidence_class": "redacted_derived" if "redacted" in states else "diagnostic_supporting",
        "provenance_kind": "runtime_projection",
        "redacted": "redacted" in states,
        "policy_design_case_id": _text(validated_case.get("case_id")),
        "run_id": _text(validated_case.get("run_id")),
        "source_ref": _text(source_ref),
        "source_ref_fingerprint": _fingerprint(source_ref) if source_ref else None,
        "source_authority_refs": _source_authority_refs(authority_chain),
        "source_state": {
            "policy_design_case_status": _text(validated_case.get("status")),
            "artifact_publishability": _text(source.get("publishability")),
            "public_export_status": _nested_text(
                source,
                ("decision_context", "public_export_status"),
            ),
        },
        "may_be_used_for": list(_MAY_BE_USED_FOR),
        "may_not_be_used_for": list(_MAY_NOT_BE_USED_FOR),
    }
    return assert_policy_design_projection_not_authority(projection)


def assert_policy_design_projection_not_authority(
    projection: Mapping[str, Any],
) -> dict[str, Any]:
    """Raise if a Policy Design Case projection is shaped like authority."""

    authority_role = _text(projection.get("authority_role")).casefold()
    if authority_role != "projection_only":
        raise PolicyDesignCaseProjectionError(
            "policy_design_projection_mints_authority",
            "Policy Design Case projections must be projection_only.",
        )
    policy = _text(projection.get("projection_policy"))
    if policy != "reads_policy_design_case_only":
        raise PolicyDesignCaseProjectionError(
            "policy_design_projection_policy_invalid",
            "Policy Design Case projections must read the case without issuing authority.",
        )
    for label in _sequence(projection.get("labels")):
        if not isinstance(label, Mapping):
            continue
        label_role = _text(label.get("authority_role")).casefold()
        if label_role != "projection_only":
            raise PolicyDesignCaseProjectionError(
                "policy_design_projection_label_mints_authority",
                "Projection labels cannot carry authority-bearing roles.",
            )
    may_not = {_text(item) for item in _sequence(projection.get("may_not_be_used_for"))}
    if not {"scorecard_authority", "runtime_closeout_authority"} <= may_not:
        raise PolicyDesignCaseProjectionError(
            "policy_design_projection_limits_missing",
            "Projection must forbid scorecard and runtime closeout authority use.",
        )
    return dict(projection)


def _projection_states(
    case: Mapping[str, Any],
    *,
    source_payload: Mapping[str, Any],
    surface: str,
) -> tuple[str, ...]:
    states: set[str] = {"projection_only"}
    surface_name = _text(surface).casefold()
    if surface_name in {"public_export", "public-export"} or _is_redacted(source_payload):
        states.add("redacted")
    if _is_draft(source_payload):
        states.add("draft")
    if _is_blocked(case) or _is_blocked(source_payload):
        states.add("blocked")
    if _is_contested(case) or _is_contested(source_payload):
        states.add("contested")
    if _is_stale(case) or _is_stale(source_payload):
        states.add("stale")
    if _is_publishable(source_payload) and not states & {"blocked", "contested", "stale", "draft"}:
        states.add("publishable")
    return tuple(state for state in PROJECTION_STATES if state in states)


def _assert_source_is_projection_safe(source: Mapping[str, Any]) -> None:
    role = _text(source.get("authority_role")).casefold()
    if role in _SOURCE_AUTHORITY_ROLES_THAT_MINT_AUTHORITY:
        raise PolicyDesignCaseProjectionError(
            "policy_design_projection_source_mints_authority",
            "Projection source must not claim producer, scorecard, readiness, or approval authority.",
        )
    if role not in _ALLOWED_FINAL_ARTIFACT_SOURCE_ROLES:
        raise PolicyDesignCaseProjectionError(
            "policy_design_projection_source_authority_role_invalid",
            f"Unsupported projection source authority_role={role!r}.",
        )


def _source_authority_refs(authority_chain: Mapping[str, Any]) -> dict[str, str]:
    refs: dict[str, str] = {}
    for key in (
        "cas_ref",
        "runtime_event_ref",
        "same_input_closure_ref",
        "effective_mode_ref",
        "schema_compatibility_ref",
    ):
        value = _text(authority_chain.get(key))
        if value:
            out_key = "policy_design_case_ref" if key == "cas_ref" else key
            refs[out_key] = value
    return refs


def _primary_state(states: Sequence[str]) -> str:
    state_set = set(states)
    for state in _PRIMARY_STATE_ORDER:
        if state in state_set:
            return state
    return "projection_only"


def _state_label(state: str) -> str:
    if state == "projection_only":
        return "projection only"
    return state.replace("_", " ")


def _is_publishable(payload: Mapping[str, Any]) -> bool:
    publishability = _text(payload.get("publishability")).casefold()
    export_status = _nested_text(payload, ("decision_context", "public_export_status")).casefold()
    return publishability == "publishable" or export_status == "publishable"


def _is_draft(payload: Mapping[str, Any]) -> bool:
    kind = _text(payload.get("artifact_kind")).casefold()
    publishability = _text(payload.get("publishability")).casefold()
    export_status = _nested_text(payload, ("decision_context", "public_export_status")).casefold()
    return (
        kind == "draft_decision_packet"
        or publishability in {"draft", "not_publishable"}
        or export_status in {"draft", "draft_projection"}
    )


def _is_redacted(payload: Mapping[str, Any]) -> bool:
    return (
        _text(payload.get("evidence_class")).casefold() == "redacted_derived"
        or _text(payload.get("public_export_classification")).casefold()
        == "public_redacted_projection"
        or isinstance(payload.get("redaction_summary"), Mapping)
    )


def _is_blocked(payload: Mapping[str, Any]) -> bool:
    status_values = [
        _text(payload.get("status")),
        _text(payload.get("quality_status")),
        _text(payload.get("approval_state")),
        _text(payload.get("publishability")),
        _nested_text(payload, ("decision_context", "public_export_status")),
    ]
    if any(
        value.casefold() in {"blocked", "fail", "failed", "quality_failed"}
        for value in status_values
    ):
        return True
    for key in (
        "blockers",
        "blocking_quality_failures",
        "compiler_issues",
        "source_truth_conflicts",
    ):
        if _sequence(payload.get(key)):
            return True
    return False


def _is_contested(payload: Mapping[str, Any]) -> bool:
    status_values = [
        _text(payload.get("contestability_status")),
        _text(payload.get("challenge_status")),
        _text(payload.get("dispute_status")),
        _text(payload.get("status")),
    ]
    if any(value.casefold() in {"contested", "conflict", "disputed"} for value in status_values):
        return True
    for key in (
        "source_truth_conflicts",
        "counter_evidence",
        "counter_evidence_nodes",
        "rebuttals",
    ):
        if _sequence(payload.get(key)):
            return True
    return any(
        isinstance(node, Mapping)
        and _text(node.get("status")).casefold() in {"contested", "conflict", "disputed"}
        for node in _sequence(payload.get("nodes"))
    )


def _is_stale(payload: Mapping[str, Any]) -> bool:
    status_values = [
        _text(payload.get("freshness_status")),
        _text(payload.get("decision_validity_status")),
        _text(payload.get("schema_compatibility_status")),
        _text(payload.get("status")),
    ]
    return any("stale" in value.casefold() for value in status_values)


def _nested_text(payload: Mapping[str, Any], path: Sequence[str]) -> str:
    value: Any = payload
    for key in path:
        if not isinstance(value, Mapping):
            return ""
        value = value.get(key)
    return _text(value)


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def _text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(microsecond=0)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC, microsecond=0)
    return value.astimezone(UTC).replace(microsecond=0)


def _fingerprint(value: object) -> str:
    return "sha256:" + hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


__all__ = [
    "POLICY_DESIGN_CASE_PROJECTION_SCHEMA_VERSION",
    "PROJECTION_STATES",
    "PolicyDesignCaseProjectionError",
    "assert_policy_design_projection_not_authority",
    "build_policy_design_case_projection_semantics",
]
