"""Legacy quarantine migration sandbox for honest diagnostics."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.core.canon import CanonSpec
from polisyos.core.canon.canon_json import to_canonical_bytes
from polisyos.runtime.quality.authority import (
    AuthorityEnvelopeError,
    assert_runtime_emitted,
    deserialize_authority_envelope,
)
from polisyos.runtime.quality.schema_compat import (
    COMPATIBLE_DECISIONS,
    SCORECARD_REPORT_SCHEMA_FAMILY_ALIASES,
    evaluate_schema_compatibility,
)

LEGACY_MIGRATION_SANDBOX_SCHEMA_VERSION = (
    "policyos.runtime.quality.legacy_migration_sandbox.v1"
)
LEGACY_MIGRATION_SEMANTIC_LOSS = "legacy_migration_semantic_loss"
LEGACY_MIGRATION_SANDBOX_RELATIVE_DIR = Path(
    "_build/honest-diagnostics/migration-sandbox"
)
REQUIRED_WEEKLY_BASELINE_COUNT = 2
SERIOUS_CANARY_KINDS = frozenset({"governed", "production", "research"})

LEGACY_AUTHORITY_BLOCKED_CODES = frozenset(
    {
        LEGACY_MIGRATION_SEMANTIC_LOSS,
        "legacy_migration_authority_missing",
        "legacy_migration_authority_envelope_missing",
        "legacy_migration_authority_invalid",
        "legacy_migration_payload_mismatch",
        "legacy_migration_redaction_gap",
        "legacy_migration_ref_conflict",
        "legacy_migration_schema_incompatible",
        "legacy_migration_source_truth_conflict",
        "legacy_migration_status_mismatch",
    }
)
AUTHORITY_ONLY_KEYS = frozenset(
    {
        "attestation_ref",
        "authority_envelope",
        "cas_artifact_refs",
        "degradation_ledger_ref",
        "diagnostic_event",
        "diagnostic_event_ref",
        "diagnostic_event_refs",
        "effective_mode_ref",
        "fallback_degradation_ref",
        "redaction_policy_ref",
        "runtime_event_ref",
        "runtime_event_refs",
        "schema_compatibility",
        "source_payload_sha256",
        "source_runtime_event_ref",
    }
)
DEFAULT_SEMANTIC_FIELDS = (
    "status",
    "quality_status",
    "production_readiness",
    "issues",
    "diagnostics",
    "summary",
    "claims",
    "applied_norms",
    "candidate_norms",
    "recommendation_claims",
    "candidate_sources",
    "selected_source_ids",
    "rejected_sources",
    "selected_methods",
    "result_summary",
    "deterministic_fingerprint",
    "differences",
    "operator_findings",
    "lifecycle_decision",
    "decision_status",
    "source_truth_conflicts",
)
PASS_STATUSES = frozenset({"accepted_drift", "match", "ok", "pass", "passed", "success"})
FAIL_STATUSES = frozenset({"blocked", "error", "fail", "failed", "missing"})
WARN_STATUSES = frozenset({"degraded", "warn", "warning"})
SECRET_MARKERS = (
    "access_token",
    "api_key",
    "authorization",
    "bearer ",
    "credential",
    "hidden_answer",
    "password",
    "refresh_token",
    "secret",
    "token",
)
REPO_ROOT = Path(__file__).resolve().parents[4]


def build_legacy_migration_sandbox(
    *,
    canary_kind: str,
    run_id: object,
    job_id: object,
    comparisons: Sequence[Mapping[str, object]],
    baseline_history: Sequence[Mapping[str, object]] = (),
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a serious-run dual-write comparison report.

    Legacy-compatible payloads are intentionally marked as quarantined.  The
    authority side must remain runtime-emitted envelope/event-backed evidence
    for production closeout.
    """

    generated = _utc(generated_at).replace(microsecond=0).isoformat()
    comparison_rows = [_compare_pair(item) for item in comparisons]
    failure_codes = sorted(
        {
            code
            for comparison in comparison_rows
            for code in _comparison_failure_codes(comparison)
        }
    )
    serious = str(canary_kind).casefold() in SERIOUS_CANARY_KINDS
    blocking_codes = sorted(
        code for code in failure_codes if code in LEGACY_AUTHORITY_BLOCKED_CODES
    )
    observed_baselines = _consecutive_weekly_baseline_count(baseline_history)
    production_closeout_allowed = not (serious and blocking_codes)

    return {
        "schema_version": LEGACY_MIGRATION_SANDBOX_SCHEMA_VERSION,
        "generated_at": generated,
        "canary_kind": str(canary_kind),
        "run_id": None if run_id is None else str(run_id),
        "job_id": None if job_id is None else str(job_id),
        "status": "fail" if blocking_codes else "pass",
        "production_closeout_allowed": production_closeout_allowed,
        "failure_codes": failure_codes,
        "blocking_failure_codes": blocking_codes,
        "comparisons": comparison_rows,
        "closeout_policy": {
            "authority_bearing_files_only": True,
            "legacy_satisfies_serious_gates": False,
            "legacy_allowed_roles": [
                "diagnostic_supporting",
                "legacy_quarantined",
                "public_exported",
            ],
        },
        "dual_write_policy": {
            "status": "active",
            "required_consecutive_weekly_closeout_baselines": (
                REQUIRED_WEEKLY_BASELINE_COUNT
            ),
            "observed_consecutive_weekly_closeout_baselines": observed_baselines,
            "cutoff_allowed": observed_baselines >= REQUIRED_WEEKLY_BASELINE_COUNT,
        },
    }


def legacy_compatible_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return the quarantined legacy-compatible projection of an authority payload."""

    projected = _strip_authority_only(deepcopy(dict(payload)))
    projected["evidence_class"] = "legacy_quarantined"
    projected["authority_role"] = "diagnostic_only"
    projected["provenance_kind"] = "legacy_supported"
    return projected


def comparison_failure_codes(report: Mapping[str, Any]) -> set[str]:
    """Return all normalized failure codes from a sandbox report."""

    codes = {
        str(code)
        for code in report.get("failure_codes", [])
        if str(code or "").strip()
    }
    comparisons = report.get("comparisons")
    if isinstance(comparisons, list):
        for comparison in comparisons:
            if isinstance(comparison, Mapping):
                codes.update(_comparison_failure_codes(comparison))
    return codes


def persist_legacy_migration_sandbox_report(
    report: Mapping[str, Any],
    *,
    repo_root: str | Path = REPO_ROOT,
    validation_id: str | None = None,
) -> Path:
    """Persist local validation output under ``_build/honest-diagnostics``."""

    root = Path(repo_root)
    output_dir = root / LEGACY_MIGRATION_SANDBOX_RELATIVE_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    report_id = validation_id or _report_file_stem(report)
    path = output_dir / f"{_safe_file_stem(report_id)}.json"
    path.write_text(
        json.dumps(dict(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _compare_pair(item: Mapping[str, Any]) -> dict[str, Any]:
    report_key = _text(item.get("report_key")) or "quality_report"
    ref_key = _text(item.get("ref_key"))
    authority_payload = _mapping(item.get("authority_payload"))
    legacy_payload = _mapping(item.get("legacy_payload"))
    semantic_fields = _semantic_fields(item, authority_payload, legacy_payload, ref_key)
    authority_ref = _text(
        item.get("authority_ref")
        or _ref_from_payload(authority_payload, ref_key)
        or _envelope_ref(authority_payload)
    )
    legacy_ref = _text(item.get("legacy_ref") or _ref_from_payload(legacy_payload, ref_key))

    authority_identity_payload = _strip_authority_only(authority_payload)
    legacy_identity_payload = _strip_legacy_only(legacy_payload)
    payload_identity = _payload_identity_result(
        legacy_payload=legacy_identity_payload,
        authority_payload=authority_identity_payload,
    )
    semantic_result = _semantic_field_result(
        semantic_fields=semantic_fields,
        legacy_payload=legacy_payload,
        authority_payload=authority_payload,
    )
    status_result = _status_interpretation_result(
        legacy_payload=legacy_payload,
        authority_payload=authority_payload,
    )
    refs_result = _refs_result(
        ref_key=ref_key,
        legacy_ref=legacy_ref,
        authority_ref=authority_ref,
    )
    redaction_result = _redaction_result(legacy_payload)
    schema_result = _schema_result(report_key, legacy_payload, authority_payload)
    source_truth_result = _source_truth_result(legacy_payload, authority_payload)
    authority_result = _authority_result(authority_payload, authority_ref=authority_ref)

    failure_codes = sorted(
        {
            code
            for result in (
                payload_identity,
                semantic_result,
                status_result,
                refs_result,
                redaction_result,
                schema_result,
                source_truth_result,
                authority_result,
            )
            for code in result.get("failure_codes", [])
            if str(code).strip()
        }
    )
    return {
        "report_key": report_key,
        "ref_key": ref_key,
        "status": "fail" if failure_codes else "pass",
        "failure_codes": failure_codes,
        "legacy": {
            "evidence_class": "legacy_quarantined",
            "authority_role": "diagnostic_only",
            "provenance_kind": "legacy_supported",
            "ref": legacy_ref,
        },
        "authority": {
            "evidence_class": authority_result.get("evidence_class", "authority_bearing"),
            "authority_role": authority_result.get("authority_role"),
            "provenance_kind": authority_result.get("provenance_kind"),
            "ref": authority_ref,
        },
        "payload_identity": payload_identity,
        "semantic_fields": semantic_result,
        "status_interpretation": status_result,
        "refs": refs_result,
        "redaction": redaction_result,
        "schema_compatibility": schema_result,
        "source_truth": source_truth_result,
        "authority_validation": authority_result,
    }


def _payload_identity_result(
    *,
    legacy_payload: Mapping[str, Any],
    authority_payload: Mapping[str, Any],
) -> dict[str, Any]:
    legacy_digest = _digest(legacy_payload)
    authority_digest = _digest(authority_payload)
    matched = legacy_digest == authority_digest
    return {
        "status": "pass" if matched else "fail",
        "legacy_sha256": legacy_digest,
        "authority_sha256": authority_digest,
        "failure_codes": [] if matched else ["legacy_migration_payload_mismatch"],
    }


def _semantic_field_result(
    *,
    semantic_fields: tuple[str, ...],
    legacy_payload: Mapping[str, Any],
    authority_payload: Mapping[str, Any],
) -> dict[str, Any]:
    lost_fields = [
        field
        for field in semantic_fields
        if _present(_field_value(authority_payload, field))
        and _fingerprint(_field_value(legacy_payload, field))
        != _fingerprint(_field_value(authority_payload, field))
    ]
    return {
        "status": "pass" if not lost_fields else "fail",
        "checked_fields": list(semantic_fields),
        "lost_fields": lost_fields,
        "failure_codes": [] if not lost_fields else [LEGACY_MIGRATION_SEMANTIC_LOSS],
    }


def _status_interpretation_result(
    *,
    legacy_payload: Mapping[str, Any],
    authority_payload: Mapping[str, Any],
) -> dict[str, Any]:
    legacy_status = _normalized_status(legacy_payload)
    authority_status = _normalized_status(authority_payload)
    matched = legacy_status == authority_status
    return {
        "status": "pass" if matched else "fail",
        "legacy_status": legacy_status,
        "authority_status": authority_status,
        "failure_codes": [] if matched else ["legacy_migration_status_mismatch"],
    }


def _refs_result(
    *,
    ref_key: str | None,
    legacy_ref: str | None,
    authority_ref: str | None,
) -> dict[str, Any]:
    legacy_claims_authority_ref = (
        legacy_ref is not None
        and authority_ref is not None
        and _looks_like_authority_ref(legacy_ref)
        and legacy_ref != authority_ref
    )
    authority_missing = authority_ref is None
    failure_codes: list[str] = []
    if authority_missing:
        failure_codes.append("legacy_migration_authority_missing")
    if legacy_claims_authority_ref:
        failure_codes.append("legacy_migration_ref_conflict")
    return {
        "status": "pass" if not failure_codes else "fail",
        "ref_key": ref_key,
        "legacy_ref": legacy_ref,
        "authority_ref": authority_ref,
        "legacy_claims_authority_ref": legacy_claims_authority_ref,
        "failure_codes": failure_codes,
    }


def _redaction_result(payload: Mapping[str, Any]) -> dict[str, Any]:
    leaked_fields = _sensitive_paths(payload)
    return {
        "status": "pass" if not leaked_fields else "fail",
        "leaked_fields": leaked_fields,
        "failure_codes": [] if not leaked_fields else ["legacy_migration_redaction_gap"],
    }


def _schema_result(
    report_key: str,
    legacy_payload: Mapping[str, Any],
    authority_payload: Mapping[str, Any],
) -> dict[str, Any]:
    expected_schema = SCORECARD_REPORT_SCHEMA_FAMILY_ALIASES.get(report_key)
    legacy = evaluate_schema_compatibility(
        legacy_payload,
        reader="scorecard",
        expected_schema_family=expected_schema,
    )
    authority = evaluate_schema_compatibility(
        authority_payload,
        reader="scorecard",
        expected_schema_family=expected_schema,
    )
    if expected_schema is None:
        return {
            "status": "pass",
            "declared_scorecard_schema_family": False,
            "legacy_decision": legacy.decision,
            "legacy_reason": legacy.reason,
            "legacy_diagnostic_readable": legacy.diagnostic_readable,
            "legacy_production_closeout_allowed": False,
            "authority_decision": authority.decision,
            "authority_reason": authority.reason,
            "authority_production_closeout_allowed": authority.production_closeout_allowed,
            "failure_codes": [],
        }
    authority_ok = authority.decision in COMPATIBLE_DECISIONS
    return {
        "status": "pass" if authority_ok else "fail",
        "declared_scorecard_schema_family": True,
        "legacy_decision": legacy.decision,
        "legacy_reason": legacy.reason,
        "legacy_diagnostic_readable": legacy.diagnostic_readable,
        "legacy_production_closeout_allowed": False,
        "authority_decision": authority.decision,
        "authority_reason": authority.reason,
        "authority_production_closeout_allowed": authority.production_closeout_allowed,
        "failure_codes": [] if authority_ok else ["legacy_migration_schema_incompatible"],
    }


def _source_truth_result(
    legacy_payload: Mapping[str, Any],
    authority_payload: Mapping[str, Any],
) -> dict[str, Any]:
    legacy_conflicts = legacy_payload.get("source_truth_conflicts")
    authority_conflicts = authority_payload.get("source_truth_conflicts")
    legacy_fp = _fingerprint(legacy_conflicts or [])
    authority_fp = _fingerprint(authority_conflicts or [])
    matched = legacy_fp == authority_fp
    return {
        "status": "pass" if matched else "fail",
        "legacy_conflict_count": len(legacy_conflicts) if isinstance(legacy_conflicts, list) else 0,
        "authority_conflict_count": (
            len(authority_conflicts) if isinstance(authority_conflicts, list) else 0
        ),
        "failure_codes": [] if matched else ["legacy_migration_source_truth_conflict"],
    }


def _authority_result(
    authority_payload: Mapping[str, Any],
    *,
    authority_ref: str | None,
) -> dict[str, Any]:
    envelope = authority_payload.get("authority_envelope")
    if not isinstance(envelope, Mapping):
        return {
            "status": "fail",
            "failure_codes": ["legacy_migration_authority_envelope_missing"],
            "authority_ref": authority_ref,
        }
    try:
        validated = assert_runtime_emitted(deserialize_authority_envelope(envelope))
    except Exception as exc:
        code = (
            exc.code if isinstance(exc, AuthorityEnvelopeError) else "authority_invalid"
        )
        return {
            "status": "fail",
            "error_code": str(code),
            "failure_codes": ["legacy_migration_authority_invalid"],
        }
    return {
        "status": "pass",
        "evidence_class": validated.evidence_class,
        "authority_role": validated.authority_role,
        "provenance_kind": validated.provenance_kind,
        "failure_codes": [],
    }


def _semantic_fields(
    item: Mapping[str, Any],
    authority_payload: Mapping[str, Any],
    legacy_payload: Mapping[str, Any],
    ref_key: str | None,
) -> tuple[str, ...]:
    explicit = item.get("semantic_fields")
    if isinstance(explicit, Sequence) and not isinstance(explicit, str):
        fields = [str(field).strip() for field in explicit if str(field).strip()]
    else:
        declared = authority_payload.get("migration_semantic_fields") or legacy_payload.get(
            "migration_semantic_fields"
        )
        fields = (
            [str(field).strip() for field in declared if str(field).strip()]
            if isinstance(declared, Sequence) and not isinstance(declared, str)
            else list(DEFAULT_SEMANTIC_FIELDS)
        )
    if ref_key:
        fields.append(ref_key)
    return tuple(dict.fromkeys(fields))


def _strip_authority_only(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _strip_top_level_keys(payload, AUTHORITY_ONLY_KEYS)


def _strip_legacy_only(payload: Mapping[str, Any]) -> dict[str, Any]:
    stripped = _strip_top_level_keys(
        payload,
        {"evidence_class", "authority_role", "provenance_kind"},
    )
    return _strip_authority_only(stripped)


def _strip_top_level_keys(
    payload: Mapping[str, Any],
    keys: set[str] | frozenset[str],
) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in payload.items()
        if str(key) not in keys
    }


def _strip_keys(payload: Mapping[str, Any], keys: set[str] | frozenset[str]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in payload.items():
        key_text = str(key)
        if key_text in keys:
            continue
        if isinstance(value, Mapping):
            clean[key_text] = _strip_keys(value, keys)
        elif isinstance(value, list):
            clean[key_text] = [
                _strip_keys(item, keys) if isinstance(item, Mapping) else item for item in value
            ]
        else:
            clean[key_text] = value
    return clean


def _comparison_failure_codes(comparison: Mapping[str, Any]) -> set[str]:
    codes = {
        str(code)
        for code in comparison.get("failure_codes", [])
        if str(code or "").strip()
    }
    for value in comparison.values():
        if isinstance(value, Mapping):
            codes.update(
                str(code)
                for code in value.get("failure_codes", [])
                if str(code or "").strip()
            )
    return codes


def _consecutive_weekly_baseline_count(
    baseline_history: Sequence[Mapping[str, object]],
) -> int:
    count = 0
    for baseline in reversed(tuple(baseline_history)):
        if str(baseline.get("status") or "").casefold() != "pass":
            break
        if str(baseline.get("cadence") or "").casefold() not in {
            "week",
            "weekly",
            "weekly-closeout",
        }:
            break
        count += 1
    return count


def _field_value(payload: Mapping[str, Any], dotted_path: str) -> object:
    current: object = payload
    for part in dotted_path.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _normalized_status(payload: Mapping[str, Any]) -> str:
    raw = str(
        payload.get("status")
        or payload.get("quality_status")
        or payload.get("production_readiness")
        or ""
    ).casefold()
    if raw in PASS_STATUSES:
        return "pass"
    if raw in WARN_STATUSES:
        return "warn"
    if raw in FAIL_STATUSES:
        return "fail"
    return raw or "missing"


def _sensitive_paths(value: object, *, path: str = "$") -> list[str]:
    leaked: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            lowered = key_text.casefold()
            if any(marker in lowered for marker in SECRET_MARKERS):
                leaked.append(child_path)
                continue
            leaked.extend(_sensitive_paths(item, path=child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            leaked.extend(_sensitive_paths(item, path=f"{path}[{index}]"))
    elif isinstance(value, str):
        lowered = value.casefold()
        if any(marker in lowered for marker in SECRET_MARKERS):
            leaked.append(path)
    return leaked


def _digest(payload: object) -> str:
    data = to_canonical_bytes(payload, CanonSpec(forbid_floats=False))
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _fingerprint(value: object) -> str:
    return _digest(_json_safe(value))


def _json_safe(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping | Sequence) and not isinstance(value, str):
        return bool(value)
    return True


def _ref_from_payload(payload: Mapping[str, Any], ref_key: str | None) -> str | None:
    if ref_key is not None:
        text = _text(payload.get(ref_key))
        if text is not None:
            return text
    for key in ("cas_ref", "artifact_ref", "ref"):
        text = _text(payload.get(key))
        if text is not None:
            return text
    return None


def _envelope_ref(payload: Mapping[str, Any]) -> str | None:
    envelope = payload.get("authority_envelope")
    if not isinstance(envelope, Mapping):
        return None
    return _text(envelope.get("cas_ref") or envelope.get("artifact_ref"))


def _looks_like_authority_ref(value: str) -> bool:
    return value.startswith("sha256:") or value.startswith("cas://")


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_file_stem(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip(".-")
    return cleaned or "legacy-migration-sandbox"


def _report_file_stem(report: Mapping[str, Any]) -> str:
    run_id = _text(report.get("run_id")) or "no-run"
    job_id = _text(report.get("job_id")) or "no-job"
    return f"{run_id}-{job_id}-legacy-migration-sandbox"


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = [
    "LEGACY_MIGRATION_SANDBOX_RELATIVE_DIR",
    "LEGACY_MIGRATION_SANDBOX_SCHEMA_VERSION",
    "LEGACY_MIGRATION_SEMANTIC_LOSS",
    "REQUIRED_WEEKLY_BASELINE_COUNT",
    "build_legacy_migration_sandbox",
    "comparison_failure_codes",
    "legacy_compatible_payload",
    "persist_legacy_migration_sandbox_report",
]
