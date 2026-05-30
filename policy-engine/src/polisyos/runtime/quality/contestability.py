"""Contestability and recourse guards for Policy Design Case publication."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

RECOURSE_POINTER_SCHEMA_VERSION = "policyos.runtime.policy_design_case.recourse_pointer.v1"
VERIFIED_REACHABLE_RECOURSE_STATUSES = frozenset({"reachable", "verified", "verified_reachable"})
CONTESTED_STATUSES = frozenset({"contested", "conflict", "disputed"})
PRODUCTION_AUTHORITY_LEVELS = frozenset({"production"})
HIGH_STAKES_MARKERS = frozenset(
    {
        "critical",
        "high",
        "high_stakes",
        "rights_affecting",
        "safety_critical",
        "serious",
    }
)


@dataclass(frozen=True)
class PolicyDesignContestabilityError(ValueError):
    """Fail-closed contestability or recourse publication violation."""

    code: str
    message: str
    field: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def verified_recourse_pointer_for_publication(
    *,
    policy_design_case: Mapping[str, Any],
    projection_payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Return a verified recourse pointer required for contested publication.

    The guard is intentionally narrow. It only blocks high-stakes contested
    production publication attempts; it does not make PolicyOS the owner of
    appeal intake, adjudication, or SLA authority.
    """

    if not _requires_verified_recourse_pointer(policy_design_case, projection_payload):
        return None
    pointer = _find_recourse_pointer(projection_payload) or _find_recourse_pointer(
        policy_design_case
    )
    return _normalize_verified_recourse_pointer(pointer)


def _requires_verified_recourse_pointer(
    policy_design_case: Mapping[str, Any],
    projection_payload: Mapping[str, Any],
) -> bool:
    return (
        _is_publication_attempt(projection_payload)
        and _is_production(policy_design_case, projection_payload)
        and _is_high_stakes(policy_design_case, projection_payload)
        and (_is_contested(policy_design_case) or _is_contested(projection_payload))
    )


def _normalize_verified_recourse_pointer(pointer: object) -> dict[str, Any]:
    if not isinstance(pointer, Mapping):
        raise PolicyDesignContestabilityError(
            "public_export_recourse_pointer_unreachable",
            (
                "High-stakes contested production publication requires a "
                "verified-reachable recourse pointer."
            ),
            "recourse_pointer",
        )
    if _is_llm_or_unverified_candidate(pointer):
        raise PolicyDesignContestabilityError(
            "public_export_recourse_pointer_unreachable",
            "LLM-generated or candidate recourse pointers cannot satisfy reachability.",
            "recourse_pointer.source_kind",
        )
    uri = _text(pointer.get("uri") or pointer.get("url") or pointer.get("href"))
    if not _is_public_recourse_uri(uri):
        raise PolicyDesignContestabilityError(
            "public_export_recourse_pointer_unreachable",
            "Recourse pointer must use a public https URI.",
            "recourse_pointer.uri",
        )
    status = _normalized_status(
        pointer.get("verification_status")
        or pointer.get("reachability_status")
        or pointer.get("status")
    )
    if status not in VERIFIED_REACHABLE_RECOURSE_STATUSES:
        raise PolicyDesignContestabilityError(
            "public_export_recourse_pointer_unreachable",
            "Recourse pointer must carry verified reachable status.",
            "recourse_pointer.verification_status",
        )
    verified_at = _text(pointer.get("verified_at"))
    verification_ref = _text(
        pointer.get("verification_ref")
        or pointer.get("verification_event_ref")
        or pointer.get("evidence_ref")
    )
    if not verified_at or not verification_ref:
        raise PolicyDesignContestabilityError(
            "public_export_recourse_pointer_unreachable",
            "Recourse pointer reachability requires verified_at and verification_ref.",
            "recourse_pointer.verification_ref",
        )
    return {
        "schema_version": RECOURSE_POINTER_SCHEMA_VERSION,
        "uri": uri,
        "verification_status": "verified_reachable",
        "verified_at": verified_at,
        "verification_ref": verification_ref,
        "owner": _text(pointer.get("owner") or pointer.get("deployment_owner")),
        "authority_boundary": "deployment_owned_recourse_process",
    }


def _is_llm_or_unverified_candidate(pointer: Mapping[str, Any]) -> bool:
    candidates = (
        pointer.get("source_kind"),
        pointer.get("source_class"),
        pointer.get("provenance_kind"),
        pointer.get("authority_role"),
        pointer.get("validation_status"),
    )
    normalized = {_normalized_status(candidate) for candidate in candidates}
    if normalized & {
        "candidate_unverified",
        "llm_candidate",
        "llm_critic",
        "llm_drafter",
        "rejected_speculation",
    }:
        return True
    source = pointer.get("source")
    if isinstance(source, Mapping):
        return _is_llm_or_unverified_candidate(source)
    return False


def _find_recourse_pointer(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    direct = payload.get("recourse_pointer")
    if isinstance(direct, Mapping):
        return direct
    for key in ("contestability", "recourse"):
        nested = payload.get(key)
        if isinstance(nested, Mapping):
            pointer = nested.get("recourse_pointer") or nested.get("pointer")
            if isinstance(pointer, Mapping):
                return pointer
    return None


def _is_publication_attempt(payload: Mapping[str, Any]) -> bool:
    status_values = (
        _text(payload.get("publishability")),
        _nested_text(payload, ("decision_context", "public_export_status")),
        _text(payload.get("publication_status")),
    )
    return any(value.casefold() == "publishable" for value in status_values)


def _is_production(
    policy_design_case: Mapping[str, Any],
    projection_payload: Mapping[str, Any],
) -> bool:
    candidates = (
        _text(policy_design_case.get("effective_execution_profile")),
        _nested_text(policy_design_case, ("intent_envelope", "requested_authority_level")),
        _text(policy_design_case.get("authority_level")),
        _text(projection_payload.get("authority_level")),
        _nested_text(projection_payload, ("decision_context", "authority_level")),
    )
    return any(candidate.casefold() in PRODUCTION_AUTHORITY_LEVELS for candidate in candidates)


def _is_high_stakes(
    policy_design_case: Mapping[str, Any],
    projection_payload: Mapping[str, Any],
) -> bool:
    if (
        policy_design_case.get("high_stakes") is True
        or projection_payload.get("high_stakes") is True
    ):
        return True
    candidates = (
        _text(policy_design_case.get("stakes")),
        _text(policy_design_case.get("risk_level")),
        _text(policy_design_case.get("public_impact")),
        _text(projection_payload.get("stakes")),
        _text(projection_payload.get("risk_level")),
        _text(projection_payload.get("public_impact")),
        _nested_text(projection_payload, ("decision_context", "stakes")),
    )
    return any(candidate.casefold() in HIGH_STAKES_MARKERS for candidate in candidates)


def _is_contested(payload: Mapping[str, Any]) -> bool:
    status_values = (
        _text(payload.get("contestability_status")),
        _text(payload.get("challenge_status")),
        _text(payload.get("dispute_status")),
        _text(payload.get("status")),
    )
    if any(value.casefold() in CONTESTED_STATUSES for value in status_values):
        return True
    for key in ("source_truth_conflicts", "counter_evidence", "rebuttals"):
        if _sequence(payload.get(key)):
            return True
    return False


def _is_public_recourse_uri(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _nested_text(payload: Mapping[str, Any], path: Sequence[str]) -> str:
    value: Any = payload
    for key in path:
        if not isinstance(value, Mapping):
            return ""
        value = value.get(key)
    return _text(value)


def _sequence(value: object) -> Sequence[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def _normalized_status(value: object) -> str:
    return _text(value).casefold().replace("-", "_")


def _text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


__all__ = [
    "RECOURSE_POINTER_SCHEMA_VERSION",
    "VERIFIED_REACHABLE_RECOURSE_STATUSES",
    "PolicyDesignContestabilityError",
    "verified_recourse_pointer_for_publication",
]
