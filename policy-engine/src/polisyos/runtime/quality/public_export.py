"""Public export redaction and authority-boundary helpers."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from polisyos.runtime.quality.authority import (
    AuthorityEnvelopeInput,
    deserialize_authority_envelope,
)
from polisyos.runtime.quality.projection_semantics import (
    build_policy_design_case_projection_semantics,
)

PUBLIC_EXPORT_SCHEMA_VERSION = "policyos.runtime.public_export_bundle.v1"
PUBLIC_EXPORT_REDACTION_POLICY_REF = "redaction-policy/public-export-v1"

_PUBLIC_EXPORT_EVIDENCE_CLASSES = {
    "diagnostic_supporting",
    "public_exported",
    "redacted_derived",
}
_PUBLIC_EXPORT_AUTHORITY_ROLES = {
    "diagnostic_only",
    "not_authoritative",
    "packaging_only",
    "projection_only",
}
_AUTHORITY_ROLES = {
    "approval_input",
    "producer_authority",
    "readiness_input",
    "runtime_blocker",
    "scorecard_input",
}
_AUTHORITY_PROVENANCE_KINDS = {
    "runtime_blocker",
    "runtime_emitted",
    "runtime_fallback",
}
_OFFICIAL_USE_LIMITS = {
    "official_use": "public_audit_only",
    "may_be_used_for": [
        "public_audit",
        "operator_triage",
        "external_explanation",
    ],
    "may_not_be_used_for": [
        "scorecard_authority",
        "approval_authority",
        "runtime_closeout_authority",
        "provider_credential_validation",
        "tenant_identity_resolution",
    ],
    "authority_limitation": (
        "This bundle is a redacted projection. Use the referenced runtime "
        "authority graph for scorecard, readiness, approval, or closeout."
    ),
}
_FORBIDDEN_KEY_TOKENS = (
    "access_token",
    "api_key",
    "answer_key",
    "bearer_token",
    "benchmark_answer",
    "credential",
    "credentials",
    "developer_prompt",
    "hidden_answer",
    "hidden_benchmark",
    "hidden_eval",
    "hidden_holdout",
    "password",
    "private_prompt",
    "private_reviewer",
    "provider_config",
    "provider_credential",
    "raw_records",
    "raw_sensitive",
    "raw_source",
    "raw_transcript",
    "restricted_source",
    "reviewer_private",
    "secret",
    "sensitive_data",
    "source_material",
    "system_prompt",
    "tenant",
    "tenant_id",
)
_FORBIDDEN_VALUE_TOKENS = (
    "access_token",
    "api_key",
    "bearer ",
    "benchmark_answer",
    "gold answer",
    "hidden_benchmark",
    "password",
    "private system prompt",
    "raw_sensitive",
    "restricted source",
    "secret-key",
    "sk-",
    "system_prompt",
)
_SHA256_REF_RE = re.compile(r"^sha256:[0-9a-f]{64}$", re.IGNORECASE)
_CAS_SHA256_REF_RE = re.compile(r"^cas://sha256/[0-9a-f]{64}$", re.IGNORECASE)


class PublicExportRedactionError(ValueError):
    """Typed public-export redaction or authority-boundary violation."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


def build_public_export_bundle(
    *,
    run_id: str,
    artifacts: Mapping[str, object],
    authority_envelopes: Sequence[AuthorityEnvelopeInput] = (),
    policy_design_case: Mapping[str, object] | None = None,
    projection_payload: Mapping[str, object] | None = None,
    title: str | None = None,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Build a redacted public projection that cannot satisfy authority gates."""

    _assert_no_unexplained_replay_drift(artifacts)
    redactions: list[dict[str, str]] = []
    sanitized_artifacts = _sanitize_public_payload(
        dict(artifacts),
        path="artifacts",
        redactions=redactions,
    )
    authority_projections = [_authority_projection(envelope) for envelope in authority_envelopes]
    projection_semantics = None
    if policy_design_case is not None:
        projection_source: dict[str, object] = {
            "public_export_classification": "public_redacted_projection",
            "evidence_class": "redacted_derived",
        }
        if projection_payload is not None:
            projection_source.update(dict(projection_payload))
        projection_semantics = build_policy_design_case_projection_semantics(
            policy_design_case=policy_design_case,
            surface="public_export",
            source_payload=projection_source,
            source_ref=projection_source.get("source_ref")
            if isinstance(projection_source.get("source_ref"), str)
            else None,
            generated_at=generated_at,
        )
    bundle = {
        "schema_version": PUBLIC_EXPORT_SCHEMA_VERSION,
        "generated_at": (generated_at or datetime.now(UTC)).replace(microsecond=0).isoformat(),
        "run_id": str(run_id),
        "title": str(title or "Public export bundle"),
        "public_export_classification": "public_redacted_projection",
        "evidence_class": "redacted_derived",
        "authority_role": "projection_only",
        "provenance_kind": "runtime_projection",
        "redaction_policy_ref": PUBLIC_EXPORT_REDACTION_POLICY_REF,
        "allowed_scorecard_authority_role": "not_authoritative",
        "allowed_approval_authority_role": "not_authoritative",
        "official_use_limits": dict(_OFFICIAL_USE_LIMITS),
        "artifacts": sanitized_artifacts,
        "semantic_audit": {
            "artifact_keys": sorted(str(key) for key in artifacts),
            "authority_projection_count": len(authority_projections),
            "authority_projections": authority_projections,
        },
        "redaction_summary": {
            "redaction_policy_ref": PUBLIC_EXPORT_REDACTION_POLICY_REF,
            "redacted_path_count": len(redactions),
            "erased_paths": sorted({item["path"] for item in redactions}),
            "upserted_redactions": redactions,
        },
    }
    if projection_semantics is not None:
        bundle["projection_semantics"] = projection_semantics
    assert_public_export_official_use_limits(bundle)
    return bundle


def _assert_no_unexplained_replay_drift(artifacts: Mapping[str, object]) -> None:
    for explanation in _iter_drift_explanations(artifacts):
        if _is_unexplained_replay_drift(explanation):
            raise PublicExportRedactionError(
                "public_export_replay_drift_unexplained",
                "public exports require typed accepted replay drift or reproduction",
            )
        if _is_unbounded_replay_drift(explanation):
            raise PublicExportRedactionError(
                "public_export_replay_drift_unbounded",
                "public exports require replay drift to stay within production impact bounds",
            )


def _iter_drift_explanations(value: object) -> Sequence[Mapping[str, object]]:
    found: list[Mapping[str, object]] = []
    if isinstance(value, Mapping):
        if _looks_like_drift_explanation(value):
            found.append(value)
        for key, item in value.items():
            if key == "drift_explanation" and isinstance(item, Mapping):
                found.append(item)
            else:
                found.extend(_iter_drift_explanations(item))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            found.extend(_iter_drift_explanations(item))
    return found


def _looks_like_drift_explanation(value: Mapping[str, object]) -> bool:
    return (
        value.get("schema_version") == "policyos.drift_explanation.v1"
        or "drift_sources" in value
        or "unexplained_difference_count" in value
    )


def _is_unexplained_replay_drift(explanation: Mapping[str, object]) -> bool:
    status = str(explanation.get("status") or "").strip().casefold()
    readiness = str(explanation.get("production_readiness") or "").strip().casefold()
    summary = explanation.get("summary")
    unexplained_count = 0
    if isinstance(summary, Mapping):
        try:
            unexplained_count = int(summary.get("unexplained_difference_count") or 0)
        except (TypeError, ValueError):
            unexplained_count = 0
    return status == "unexplained_drift" or (
        readiness in {"blocked", "fail", "failed"} and unexplained_count > 0
    )


def _is_unbounded_replay_drift(explanation: Mapping[str, object]) -> bool:
    status = str(explanation.get("status") or "").strip().casefold()
    readiness = str(explanation.get("production_readiness") or "").strip().casefold()
    summary = explanation.get("summary")
    max_impact = ""
    if isinstance(summary, Mapping):
        max_impact = str(summary.get("max_impact") or "").strip().casefold()
    blocker = explanation.get("blocking_failure")
    blocker_code = str(blocker.get("code") or "").strip() if isinstance(blocker, Mapping) else ""
    return (
        status == "accepted_drift_non_ready"
        or blocker_code == "authority_replay_drift_unbounded"
        or (readiness in {"blocked", "fail", "failed"} and max_impact in {"medium", "high"})
    )


def assert_public_export_official_use_limits(bundle: Mapping[str, object]) -> None:
    """Fail closed if a public export is shaped like authority evidence."""

    evidence_class = str(bundle.get("evidence_class") or "").strip().casefold()
    authority_role = str(bundle.get("authority_role") or "").strip().casefold()
    provenance_kind = str(bundle.get("provenance_kind") or "").strip().casefold()
    if (
        evidence_class not in _PUBLIC_EXPORT_EVIDENCE_CLASSES
        or authority_role in _AUTHORITY_ROLES
        or authority_role not in _PUBLIC_EXPORT_AUTHORITY_ROLES
        or provenance_kind in _AUTHORITY_PROVENANCE_KINDS
    ):
        raise PublicExportRedactionError(
            "public_export_not_authority",
            "public exports must remain redacted projection-only artifacts",
        )

    limits = bundle.get("official_use_limits")
    if not isinstance(limits, Mapping):
        raise PublicExportRedactionError(
            "public_export_official_use_limits_missing",
            "official-use limits are required",
        )
    disallowed = {
        str(item) for item in _as_sequence(limits.get("may_not_be_used_for")) if str(item).strip()
    }
    required = {
        "approval_authority",
        "runtime_closeout_authority",
        "scorecard_authority",
    }
    if limits.get("official_use") != "public_audit_only" or not required <= disallowed:
        raise PublicExportRedactionError(
            "public_export_official_use_limits_missing",
            "public export must forbid scorecard, approval, and closeout authority use",
        )


def _authority_projection(envelope: AuthorityEnvelopeInput) -> dict[str, object]:
    validated = deserialize_authority_envelope(envelope)
    closure = validated.same_input_closure
    source_ref = validated.cas_ref or validated.artifact_ref
    return {
        "evidence_id": validated.evidence_id,
        "artifact_kind": validated.artifact_kind,
        "schema_name": validated.schema_name,
        "schema_version": validated.schema_version,
        "producer_component": validated.producer_component,
        "owner": validated.owner,
        "phase": validated.phase,
        "validation_status": validated.validation_status,
        "source_blocking_status": validated.blocking_status,
        "source_authority_role": validated.authority_role,
        "source_evidence_class": validated.evidence_class,
        "source_provenance_kind": validated.provenance_kind,
        "authority_role": "projection_only",
        "evidence_class": "redacted_derived",
        "provenance_kind": "runtime_projection",
        "allowed_scorecard_authority_role": "not_authoritative",
        "allowed_approval_authority_role": "not_authoritative",
        "runtime_event_ref_fingerprint": _fingerprint(validated.runtime_event_ref),
        "source_authority_ref_fingerprint": _fingerprint(source_ref),
        "same_input_closure_status": closure.status,
        "same_input_closure_fingerprint": _fingerprint(
            closure.closure_sha256 or closure.closure_id
        ),
        "tenant_redacted": True,
        "tenant_fingerprint": _fingerprint(validated.tenant_id),
    }


def _sanitize_public_payload(
    value: object,
    *,
    path: str,
    redactions: list[dict[str, str]],
) -> object | None:
    if isinstance(value, Mapping):
        sanitized: dict[str, object] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            child_path = f"{path}.{key}"
            reason = _forbidden_key_reason(key)
            if reason is not None:
                redactions.append({"path": child_path, "reason": reason})
                continue
            sanitized_value = _sanitize_public_payload(
                item,
                path=child_path,
                redactions=redactions,
            )
            if sanitized_value is not None:
                sanitized[key] = sanitized_value
        return sanitized
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        sanitized_items: list[object] = []
        for index, item in enumerate(value):
            sanitized_item = _sanitize_public_payload(
                item,
                path=f"{path}[{index}]",
                redactions=redactions,
            )
            if sanitized_item is not None:
                sanitized_items.append(sanitized_item)
        return sanitized_items
    if isinstance(value, str):
        reason = _forbidden_value_reason(value)
        if reason is not None:
            redactions.append({"path": path, "reason": reason})
            return {
                "redacted": True,
                "reason": reason,
                "fingerprint": _fingerprint(value),
            }
    return value


def _forbidden_key_reason(key: str) -> str | None:
    lowered = key.casefold().replace("-", "_")
    for token in _FORBIDDEN_KEY_TOKENS:
        if token in lowered:
            return f"forbidden_key:{token}"
    return None


def _forbidden_value_reason(value: str) -> str | None:
    if _is_tenant_private_ref(value):
        return "tenant_private_ref"
    lowered = value.casefold()
    for token in _FORBIDDEN_VALUE_TOKENS:
        if token in lowered:
            return f"forbidden_value:{token}"
    return None


def _is_tenant_private_ref(value: str) -> bool:
    text = value.strip()
    return bool(_SHA256_REF_RE.fullmatch(text) or _CAS_SHA256_REF_RE.fullmatch(text))


def _fingerprint(value: object) -> str:
    return "sha256:" + hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _as_sequence(value: object) -> Sequence[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


__all__ = [
    "PUBLIC_EXPORT_REDACTION_POLICY_REF",
    "PUBLIC_EXPORT_SCHEMA_VERSION",
    "PublicExportRedactionError",
    "assert_public_export_official_use_limits",
    "build_public_export_bundle",
]
