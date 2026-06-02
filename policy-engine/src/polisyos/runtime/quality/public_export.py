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
from polisyos.runtime.quality.candidate_firewall import (
    candidate_firewall_issues_for_payload,
)
from polisyos.runtime.quality.case_lifecycle import PUBLIC_REVISION_STATE_SCHEMA_VERSION
from polisyos.runtime.quality.contestability import (
    PolicyDesignContestabilityError,
    verified_recourse_pointer_for_publication,
)
from polisyos.runtime.quality.projection_semantics import (
    build_policy_design_case_projection_from_runtime_graph,
    build_policy_design_case_projection_semantics,
    verify_policy_design_case_projection_consumer_contract,
    verify_s9_projection_faithfulness_for_pdc_consumer_contract,
)
from polisyos.runtime.quality.rule_evolution import (
    RULE_EVOLUTION_PUBLIC_ANNOTATION_SCHEMA_VERSION,
)

PUBLIC_EXPORT_SCHEMA_VERSION = "policyos.runtime.public_export_bundle.v1"
PUBLIC_EXPORT_REDACTION_POLICY_REF = "redaction-policy/public-export-v1"

_SCALAR_WELFARE_KEYS = frozenset(
    {
        "aggregate_welfare",
        "bcr",
        "net_benefit",
        "npv",
        "scalar_aggregate",
        "scalar_welfare",
        "welfare_aggregate",
        "welfare_delta",
        "welfare_score",
    }
)
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
    runtime_pdc_graph: Mapping[str, object] | None = None,
    projection_payload: Mapping[str, object] | None = None,
    title: str | None = None,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Build a redacted public projection that cannot satisfy authority gates."""

    recourse_pointer = None
    if policy_design_case is not None:
        try:
            recourse_pointer = verified_recourse_pointer_for_publication(
                policy_design_case=policy_design_case,
                projection_payload=projection_payload or {},
            )
        except PolicyDesignContestabilityError as exc:
            raise PublicExportRedactionError(exc.code, exc.message) from exc
    _assert_no_unexplained_replay_drift(artifacts)
    _assert_public_export_candidate_firewall(artifacts)
    _assert_public_welfare_frontier_surface(artifacts)
    if projection_payload is not None:
        _assert_public_welfare_frontier_surface(projection_payload)
    redactions: list[dict[str, str]] = []
    sanitized_artifacts = _sanitize_public_payload(
        dict(artifacts),
        path="artifacts",
        redactions=redactions,
    )
    rule_evolution_annotations = _iter_rule_evolution_annotations(sanitized_artifacts)
    public_revision_states = _iter_public_revision_states(sanitized_artifacts)
    orchestration_continuity = _public_orchestration_continuity_projection(
        sanitized_artifacts
    )
    authority_projections = [_authority_projection(envelope) for envelope in authority_envelopes]
    projection_semantics = None
    if runtime_pdc_graph is not None:
        projection_semantics = build_policy_design_case_projection_from_runtime_graph(
            runtime_pdc_graph=runtime_pdc_graph,
            surface="public_export",
            generated_at=generated_at,
        )
        projection_contract_verification = verify_policy_design_case_projection_consumer_contract(
            projections={"public": projection_semantics},
            expected_closeout_truth=projection_semantics["closeout_truth"],
            expected_contested_record_ids=[
                str(record.get("contested_record_id"))
                for record in projection_semantics.get("contested_records", [])
                if isinstance(record, Mapping)
            ],
            runtime_pdc_graph=runtime_pdc_graph,
        )
        projection_semantics = {
            **projection_semantics,
            "contract_verification_status": str(
                projection_contract_verification.get("status") or "fail"
            ),
            "contract_verification_refs": [
                "policyos.runtime.policy_design_case.projection_contract_verification.v1"
            ],
        }
    elif policy_design_case is not None:
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
        projection_contract_verification = verify_policy_design_case_projection_consumer_contract(
            projections={"public": projection_semantics},
            expected_closeout_truth=projection_semantics["closeout_truth"],
            expected_contested_record_ids=[
                str(record.get("contested_record_id"))
                for record in projection_semantics.get("contested_records", [])
                if isinstance(record, Mapping)
            ],
        )
        projection_semantics = {
            **projection_semantics,
            "contract_verification_status": str(
                projection_contract_verification.get("status") or "fail"
            ),
            "contract_verification_refs": [
                "policyos.runtime.policy_design_case.projection_contract_verification.v1"
            ],
        }
    else:
        projection_contract_verification = None
    if projection_semantics is not None and projection_payload is not None:
        projection_semantics, s9_verification = _apply_s9_projection_faithfulness(
            projection_semantics=projection_semantics,
            projection_payload=projection_payload,
        )
        if s9_verification is not None and projection_contract_verification is not None:
            projection_contract_verification = {
                **projection_contract_verification,
                "s9_projection_faithfulness": s9_verification,
                "status": "fail"
                if (
                    projection_contract_verification.get("status") == "fail"
                    or s9_verification.get("status") == "fail"
                )
                else "pass",
            }
    _assert_public_claim_omissions_manifested(sanitized_artifacts, projection_semantics)
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
            "runtime_orchestration_continuity": orchestration_continuity,
            "recourse_pointer": recourse_pointer,
            "rule_evolution_annotations": rule_evolution_annotations,
            "public_revision_states": public_revision_states,
            "omission_manifest": list(
                projection_semantics.get("omission_manifest", [])
                if projection_semantics is not None
                else []
            ),
            "audit_refs": list(
                projection_semantics.get("audit_refs", [])
                if projection_semantics is not None
                else []
            ),
            "projection_contract_verification": projection_contract_verification,
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


def _apply_s9_projection_faithfulness(
    *,
    projection_semantics: Mapping[str, object],
    projection_payload: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object] | None]:
    faithfulness = _s9_faithfulness_record(projection_payload)
    if not faithfulness:
        return dict(projection_semantics), None
    verifier_payload = {
        **dict(projection_semantics),
        "projection_policy": "reads_canonical_design_record",
        "source_revision_ref": _text(
            projection_payload.get("source_revision_ref")
            or faithfulness.get("source_revision_ref")
        ),
        "s9_projection_faithfulness": faithfulness,
    }
    if "omission_manifest" in projection_payload:
        verifier_payload["omission_manifest"] = projection_payload["omission_manifest"]
    verification = verify_s9_projection_faithfulness_for_pdc_consumer_contract(
        projections={"public": verifier_payload},
        expected_closeout_truth=dict(projection_semantics.get("closeout_truth") or {}),
        expected_contested_record_ids=[
            _text(record.get("contested_record_id"))
            for record in _as_sequence(projection_semantics.get("contested_records"))
            if isinstance(record, Mapping)
        ],
    )
    if verification.get("status") != "pass":
        code = _first_s9_issue_code(verification)
        raise PublicExportRedactionError(
            code,
            "S9 projection faithfulness must pass before public release.",
        )
    enriched = dict(projection_semantics)
    audit_refs = _unique_texts(
        [
            *_text_list(enriched.get("audit_refs")),
            *_s9_audit_refs(faithfulness),
            *_text_list(projection_payload.get("s9_lowering_append_refs")),
            *_text_list(projection_payload.get("lowering_append_refs")),
        ]
    )
    source_state = dict(enriched.get("source_state") or {})
    source_state.update(
        {
            "s9_source_revision_ref": _text(faithfulness.get("source_revision_ref")),
            "s9_canonical_design_record_ref": _text(
                faithfulness.get("canonical_design_record_ref")
            ),
            "s9_canonical_design_record_digest": _text(
                faithfulness.get("canonical_design_record_digest")
            ),
            "s9_projection_policy": "reads_canonical_design_record",
        }
    )
    enriched.update(
        {
            "s9_projection_faithfulness": faithfulness,
            "s9_projection_contract_verification_status": verification.get("status"),
            "s9_projection_contract_verification_ref": verification.get(
                "consumer_contract_ref"
            ),
            "audit_refs": audit_refs,
            "source_state": source_state,
        }
    )
    return enriched, verification


def _s9_faithfulness_record(payload: Mapping[str, object]) -> dict[str, object]:
    record = payload.get("s9_projection_faithfulness")
    if record is None and isinstance(payload.get("s9_projection"), Mapping):
        record = dict(payload["s9_projection"]).get("s9_projection_faithfulness")
    if isinstance(record, Mapping):
        return dict(record)
    model_dump = getattr(record, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        if isinstance(dumped, Mapping):
            return dict(dumped)
    return {}


def _s9_audit_refs(faithfulness: Mapping[str, object]) -> list[str]:
    return _unique_texts(
        [
            faithfulness.get("faithfulness_ref"),
            faithfulness.get("render_ref"),
            faithfulness.get("request_ref"),
            faithfulness.get("canonical_design_record_ref"),
            faithfulness.get("source_revision_ref"),
        ]
    )


def _first_s9_issue_code(verification: Mapping[str, object]) -> str:
    for code in _text_list(verification.get("issue_codes")):
        return code
    for issue in _as_sequence(verification.get("issues")):
        if isinstance(issue, Mapping):
            code = _text(issue.get("code"))
            if code:
                return code
    return "s9_projection_faithfulness_failed"


def _assert_public_claim_omissions_manifested(
    artifacts: Mapping[str, object],
    projection_semantics: Mapping[str, object] | None,
) -> None:
    omitted_claim_ids = set(_iter_omitted_claim_ids(artifacts))
    if not omitted_claim_ids:
        return
    manifested_claim_ids: set[str] = set()
    if projection_semantics is not None:
        for row in _as_sequence(projection_semantics.get("omission_manifest")):
            if isinstance(row, Mapping):
                manifested_claim_ids.update(
                    str(value) for value in _as_sequence(row.get("claim_ids"))
                )
    if not omitted_claim_ids <= manifested_claim_ids:
        raise PublicExportRedactionError(
            "public_export_omission_manifest_missing",
            "public exports must manifest omitted blocked claims instead of silently dropping them",
        )


def _assert_public_export_candidate_firewall(artifacts: Mapping[str, object]) -> None:
    hypothesis_ledger = _find_hypothesis_ledger(artifacts)
    issues = candidate_firewall_issues_for_payload(
        artifacts,
        hypothesis_ledger=hypothesis_ledger,
        authority_slots=("projection_authority",),
        surface="public_export",
    )
    if issues:
        issue = issues[0]
        raise PublicExportRedactionError(
            str(issue.get("code") or "candidate_firewall_blocked"),
            str(issue.get("message") or "Candidate content cannot be publicly exported."),
        )


def _assert_public_welfare_frontier_surface(payload: Mapping[str, object]) -> None:
    scalar_keys = {
        key for key, value in payload.items() if key in _SCALAR_WELFARE_KEYS and value is not None
    }
    if not scalar_keys:
        return
    has_frontier = bool(payload.get("frontier") or payload.get("pareto_frontier"))
    has_value_choice = bool(payload.get("value_choice") or payload.get("value_choice_decision"))
    has_provenance = bool(
        payload.get("social_weight_provenance") or payload.get("social_weight_provenance_refs")
    )
    if has_frontier and has_value_choice and has_provenance:
        return
    raise PublicExportRedactionError(
        "scalar_welfare_aggregate_without_frontier",
        "Scalar welfare aggregates cannot be published without Pareto frontier, "
        "value-choice, and social-weight provenance records.",
    )


def _find_hypothesis_ledger(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        ledger = value.get("hypothesis_ledger")
        if isinstance(ledger, Mapping):
            return ledger
        for item in value.values():
            found = _find_hypothesis_ledger(item)
            if found is not None:
                return found
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            found = _find_hypothesis_ledger(item)
            if found is not None:
                return found
    return None


def _iter_omitted_claim_ids(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).casefold()
            if lowered in {"omitted_claim_ids", "omitted_blocked_claim_ids"}:
                found.extend(str(claim_id) for claim_id in _as_sequence(item) if str(claim_id))
                continue
            if lowered in {"omitted_claims", "omitted_blocked_claims"}:
                for claim in _as_sequence(item):
                    if isinstance(claim, Mapping):
                        claim_id = str(claim.get("claim_id") or claim.get("id") or "")
                        if claim_id:
                            found.append(claim_id)
                    elif str(claim):
                        found.append(str(claim))
                continue
            found.extend(_iter_omitted_claim_ids(item))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            found.extend(_iter_omitted_claim_ids(item))
    return sorted(set(found))


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


def _iter_rule_evolution_annotations(value: object) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    if isinstance(value, Mapping):
        if _looks_like_rule_evolution_annotation(value):
            found.append(dict(value))
        for item in value.values():
            found.extend(_iter_rule_evolution_annotations(item))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            found.extend(_iter_rule_evolution_annotations(item))
    return found


def _iter_public_revision_states(value: object) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    if isinstance(value, Mapping):
        if _looks_like_public_revision_state(value):
            found.append(dict(value))
        for item in value.values():
            found.extend(_iter_public_revision_states(item))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            found.extend(_iter_public_revision_states(item))
    return found


def _public_orchestration_continuity_projection(
    artifacts: Mapping[str, object],
) -> dict[str, object] | None:
    value = artifacts.get("runtime_orchestration_continuity")
    if not isinstance(value, Mapping):
        return None
    return {
        "schema_version": value.get("schema_version"),
        "status": value.get("status"),
        "carrier_ref": value.get("carrier_ref"),
        "concept_spine_ref": value.get("concept_spine_ref"),
        "jurisdiction_spine_ref": value.get("jurisdiction_spine_ref"),
        "runtime_claim_registry_ref": value.get("runtime_claim_registry_ref"),
        "producer_handshake_ledger_ref": value.get("producer_handshake_ledger_ref"),
        "handoff_ref_count": _summary_count(value, "handoff_ref_count"),
        "producer_binding_ref_count": _summary_count(value, "producer_binding_ref_count"),
        "authority_role": "projection_only",
        "may_not_use_for": [
            "producer_domain_truth",
            "runtime_closeout_authority",
            "scorecard_authority",
            "approval_authority",
        ],
    }


def _summary_count(value: Mapping[str, object], key: str) -> int:
    summary = value.get("summary")
    if not isinstance(summary, Mapping):
        return 0
    try:
        return int(summary.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _looks_like_rule_evolution_annotation(value: Mapping[str, object]) -> bool:
    return (
        value.get("schema_version") == RULE_EVOLUTION_PUBLIC_ANNOTATION_SCHEMA_VERSION
        or (
            "public_annotation_state" in value
            and "revalidation_state" in value
            and "silent_upgrade_allowed" in value
        )
    )


def _looks_like_public_revision_state(value: Mapping[str, object]) -> bool:
    return (
        value.get("schema_version") == PUBLIC_REVISION_STATE_SCHEMA_VERSION
        or (
            "affected_claim_ids" in value
            and "unaffected_claim_ids" in value
            and "silent_upgrade_allowed" in value
            and value.get("authority_role") == "projection_only"
        )
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


def _text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _text_list(value: object) -> list[str]:
    return _unique_texts(_as_sequence(value))


def _unique_texts(values: Sequence[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in result:
            result.append(text)
    return result


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
