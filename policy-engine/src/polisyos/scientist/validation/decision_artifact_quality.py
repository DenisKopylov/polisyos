"""Deterministic quality gate for public decision artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from polisyos.evidence import normalize_runtime_claim_registry
from polisyos.scientist.artifacts.decision_compiler import (
    DECISION_ARTIFACT_SCHEMA_VERSION,
    PUBLIC_FORBIDDEN_KEY_TOKENS,
    REQUIRED_MAJOR_RECOMMENDATION_SECTIONS,
)

SCHEMA_VERSION = "policyos.scientist.decision_artifact_quality.v1"
SERIOUS_PROFILES = {"governed", "high_stakes", "production", "research", "serious"}

_APPROVAL_READY_STATES = {"approved", "approval_ready", "override_approved", "ready"}
_UNCERTAINTY_QUALIFIERS = (
    "assumption",
    "confidence",
    "estimate",
    "estimated",
    "interval",
    "likely",
    "may",
    "range",
    "residual",
    "risk",
    "scenario",
    "sensitivity",
    "uncertain",
    "uncertainty",
)
_UNQUALIFIED_UNCERTAINTY_PATTERNS = (
    re.compile(r"\bno uncertainty\b", re.IGNORECASE),
    re.compile(r"\bwithout uncertainty\b", re.IGNORECASE),
    re.compile(r"\bzero residual risk\b", re.IGNORECASE),
)
_CERTAINTY_PATTERNS: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    (
        "causal",
        (
            re.compile(r"\b(definitely|certainly|guaranteed to)\s+cause\b", re.IGNORECASE),
            re.compile(r"\bwill\s+definitely\s+cause\b", re.IGNORECASE),
            re.compile(r"\bproves?\s+.*\bcaus", re.IGNORECASE),
        ),
    ),
    (
        "legal",
        (
            re.compile(r"\blegally\s+certain\b", re.IGNORECASE),
            re.compile(r"\bguarantees?\s+legal\b", re.IGNORECASE),
            re.compile(r"\bfully\s+lawful\b", re.IGNORECASE),
        ),
    ),
    (
        "empirical",
        (
            re.compile(r"\bconclusive\s+evidence\b", re.IGNORECASE),
            re.compile(r"\bempirically\s+certain\b", re.IGNORECASE),
            re.compile(r"\bproves?\s+beyond\s+doubt\b", re.IGNORECASE),
        ),
    ),
    (
        "model",
        (
            re.compile(r"\bmodel\s+(proves?|guarantees?|will\s+definitely)\b", re.IGNORECASE),
            re.compile(r"\bmodel\s+certainty\b", re.IGNORECASE),
        ),
    ),
    (
        "benchmark",
        (
            re.compile(r"\bbenchmark\s+proves?\b", re.IGNORECASE),
            re.compile(r"\bgold\s+answer\b", re.IGNORECASE),
            re.compile(r"\bbenchmark\s+answer\b", re.IGNORECASE),
        ),
    ),
    (
        "compliance",
        (
            re.compile(r"\bfully\s+compliant\b", re.IGNORECASE),
            re.compile(r"\bguarantees?\s+compliance\b", re.IGNORECASE),
            re.compile(r"\bcompliance\s+certainty\b", re.IGNORECASE),
        ),
    ),
)
_PUBLIC_READY_SECTION_BINDINGS: tuple[
    tuple[str, tuple[str, ...], tuple[str, ...]],
    ...,
] = (
    ("recommendation", ("recommendation",), ()),
    ("legal_authority", (), ("norm_refs", "legal_refs")),
    ("data_basis", (), ("data_refs", "source_refs")),
    ("method_basis", (), ("method_refs", "foundry_method_refs")),
    ("uncertainty", ("residual_uncertainty",), ("uncertainty_refs",)),
    ("implementation_feasibility", ("implementation_feasibility",), ()),
    ("monitoring", ("monitoring_plan",), ("monitoring_refs",)),
    ("risks", ("implementation_risks",), ("risk_refs",)),
    ("contestability", ("withdrawal_reissue_triggers",), ("contestability_refs",)),
)


def build_decision_artifact_quality_report(
    *,
    compiled_artifact: Mapping[str, Any],
    final_claims: Sequence[Mapping[str, Any]] | None = None,
    profile: str = "standard",
    policy_grounding_matrix: Mapping[str, Any] | None = None,
    quality_scorecard: Mapping[str, Any] | None = None,
    conflict_check: Mapping[str, Any] | None = None,
    claim_registry: Mapping[str, Any] | None = None,
    approval_state: Mapping[str, Any] | str | None = None,
    assurance_refs: Mapping[str, Any] | None = None,
    policy_grounding_matrix_ref: str | None = None,
    quality_scorecard_ref: str | None = None,
    conflict_check_ref: str | None = None,
    approval_packet_ref: str | None = None,
) -> dict[str, Any]:
    """Build the fail-closed quality report for a compiled public artifact."""

    artifact = dict(compiled_artifact or {})
    claims = [dict(claim) for claim in final_claims or [] if isinstance(claim, Mapping)]
    serious = _is_serious_profile(profile)
    input_refs = _collect_input_refs(
        artifact=artifact,
        policy_grounding_matrix=policy_grounding_matrix,
        quality_scorecard=quality_scorecard,
        conflict_check=conflict_check,
        assurance_refs=assurance_refs,
        policy_grounding_matrix_ref=policy_grounding_matrix_ref,
        quality_scorecard_ref=quality_scorecard_ref,
        conflict_check_ref=conflict_check_ref,
        approval_packet_ref=approval_packet_ref,
    )
    issues: list[dict[str, Any]] = []
    normalized_claim_registry = (
        normalize_runtime_claim_registry(claim_registry, claims=claims)
        if claim_registry is not None
        else None
    )
    if isinstance(normalized_claim_registry, Mapping):
        issues.extend(
            _runtime_claim_registry_issues(
                normalized_claim_registry,
                serious=serious,
            )
        )
        registry_ref = _text(
            normalized_claim_registry.get("runtime_claim_registry_ref")
            or normalized_claim_registry.get("registry_ref")
        )
        if registry_ref:
            input_refs.setdefault("runtime_claim_registry_ref", registry_ref)

    if artifact.get("schema_version") != DECISION_ARTIFACT_SCHEMA_VERSION:
        issues.append(
            _issue(
                code="decision_artifact_schema_mismatch",
                severity="fail" if serious else "warn",
                message="Compiled decision artifact has an unexpected schema version.",
                next_action=(
                    "Recompile the final policy output with the public decision "
                    "artifact compiler before approval."
                ),
                observed_schema=artifact.get("schema_version"),
                expected_schema=DECISION_ARTIFACT_SCHEMA_VERSION,
            )
        )

    issues.extend(_required_section_issues(artifact, serious=serious))
    issues.extend(_uncertainty_language_issues(artifact, serious=serious))
    issues.extend(_certainty_overstatement_issues(artifact))
    issues.extend(_forbidden_public_export_issues(artifact))
    issues.extend(_citation_preservation_issues(artifact, final_claims=claims))
    issues.extend(_compiler_contract_issues(artifact))
    issues.extend(_claim_evidence_binding_issues(artifact, serious=serious))
    issues.extend(
        _status_context_issues(
            artifact=artifact,
            quality_scorecard=quality_scorecard,
            conflict_check=conflict_check,
            approval_state=approval_state,
            serious=serious,
        )
    )

    status = _status_from_issues(issues)
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "profile": profile,
        "decision_artifact_schema_version": artifact.get("schema_version"),
        "input_refs": input_refs,
        "parallel_evaluation": {
            "uses_compiled_output": bool(artifact),
            "requires_live_llm": False,
            "can_run_before_wave6": True,
            "wave5_ref_name": "decision_artifact_quality_report_ref",
        },
        "claim_evidence_contract": (
            dict(artifact["claim_evidence_contract"])
            if isinstance(artifact.get("claim_evidence_contract"), Mapping)
            else None
        ),
        "runtime_claim_registry": (
            dict(normalized_claim_registry)
            if isinstance(normalized_claim_registry, Mapping)
            else None
        ),
        "summary": {
            "recommendation_count": len(_recommendations(artifact)),
            "major_recommendation_count": sum(
                1 for recommendation in _recommendations(artifact) if _is_major(recommendation)
            ),
            "input_ref_count": len(input_refs),
            "required_section_count": len(REQUIRED_MAJOR_RECOMMENDATION_SECTIONS),
            "claim_evidence_contract_present": isinstance(
                artifact.get("claim_evidence_contract"),
                Mapping,
            ),
            "runtime_claim_registry_entry_count": (
                int(
                    normalized_claim_registry.get("summary", {}).get("entry_count", 0)
                )
                if isinstance(normalized_claim_registry, Mapping)
                else 0
            ),
            "runtime_claim_registry_status": (
                normalized_claim_registry.get("status")
                if isinstance(normalized_claim_registry, Mapping)
                else None
            ),
            "issue_count": len(issues),
        },
        "issues": issues,
        "blocking_issue_count": sum(
            1 for issue in issues if issue.get("severity") == "fail"
        ),
    }
    report["decision_artifact_quality_report_ref"] = _stable_report_ref(report)
    return report


def _compiler_contract_issues(artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for item in artifact.get("compiler_issues") or []:
        if not isinstance(item, Mapping):
            continue
        issues.append(
            _issue(
                code=str(item.get("code") or "decision_artifact_compiler_issue"),
                severity="fail",
                message=str(
                    item.get("message")
                    or "Publishable decision artifact compiler blocked this output."
                ),
                next_action=str(
                    item.get("next_action")
                    or "Resolve publishable compiler issues before closeout."
                ),
                compiler_issue=dict(item),
            )
        )
    return issues


def _claim_evidence_binding_issues(
    artifact: Mapping[str, Any],
    *,
    serious: bool,
) -> list[dict[str, Any]]:
    recommendations = [
        recommendation
        for recommendation in _recommendations(artifact)
        if _is_major(recommendation)
    ]
    if not recommendations:
        return []

    severity = "fail" if serious else "warn"
    contract = artifact.get("claim_evidence_contract")
    if not isinstance(contract, Mapping):
        return [
            _issue(
                code="decision_artifact_claim_evidence_contract_missing",
                severity=severity,
                message=(
                    "Public-ready decision artifacts must carry the runtime claim "
                    "evidence contract."
                ),
                next_action=(
                    "Compile the artifact through the publishable decision compiler "
                    "or attach the runtime claim_evidence_contract before approval."
                ),
                phase="decision_artifact_evidence_binding",
            )
        ]

    issues: list[dict[str, Any]] = []
    contract_status = _text(contract.get("status")).casefold()
    if contract_status in {"blocked", "fail", "failed"}:
        for item in contract.get("issues") or []:
            if not isinstance(item, Mapping):
                continue
            issues.append(
                _issue(
                    code="decision_artifact_claim_evidence_contract_blocked",
                    severity="fail",
                    claim_id=_text(item.get("claim_id")),
                    public_section=_text(item.get("statement_scope")),
                    message=str(
                        item.get("message")
                        or "Runtime claim evidence contract blocks publication."
                    ),
                    next_action=str(
                        item.get("next_action")
                        or "Resolve runtime claim evidence contract issues."
                    ),
                    phase="decision_artifact_evidence_binding",
                    contract_issue=dict(item),
                )
            )

    statements = _bound_statement_scopes_by_claim(contract)
    for recommendation in recommendations:
        claim_id = _claim_id(recommendation)
        for public_section, statement_scopes, support_keys in _PUBLIC_READY_SECTION_BINDINGS:
            if _public_section_bound(
                recommendation,
                claim_id=claim_id,
                statements=statements,
                statement_scopes=statement_scopes,
                support_keys=support_keys,
            ):
                continue
            issues.append(
                _issue(
                    code="decision_artifact_public_section_unbound",
                    severity=severity,
                    claim_id=claim_id,
                    public_section=public_section,
                    message=(
                        f"Public-ready section {public_section!r} is not bound to "
                        "runtime evidence refs or typed blockers."
                    ),
                    next_action=(
                        "Regenerate the public artifact from the evidence graph, or "
                        "attach typed blockers for unavailable public sections."
                    ),
                    phase="decision_artifact_evidence_binding",
                )
            )
    return issues


def _runtime_claim_registry_issues(
    runtime_claim_registry: Mapping[str, Any],
    *,
    serious: bool,
) -> list[dict[str, Any]]:
    severity = "fail" if serious else "warn"
    issues: list[dict[str, Any]] = []
    for item in runtime_claim_registry.get("issues") or []:
        if not isinstance(item, Mapping):
            continue
        issues.append(
            _issue(
                code=_text(item.get("code")) or "runtime_claim_registry_issue",
                severity=severity if item.get("severity") == "fail" else "warn",
                claim_id=_text(item.get("claim_id")),
                message=str(
                    item.get("message")
                    or "Runtime claim registry does not bind a public claim."
                ),
                next_action=str(
                    item.get("next_action")
                    or "Regenerate the runtime claim registry before publication."
                ),
                phase="runtime_claim_registry",
                missing_evidence_type=_text(item.get("missing_evidence_type"))
                or "claim_registry_entry",
                runtime_claim_registry_issue=dict(item),
            )
        )
    if _text(runtime_claim_registry.get("status")).casefold() in {
        "blocked",
        "fail",
        "failed",
    } and not issues:
        issues.append(
            _issue(
                code="runtime_claim_registry_failed",
                severity=severity,
                message="Runtime claim registry failed without detailed issues.",
                next_action="Inspect and regenerate the runtime claim registry.",
                phase="runtime_claim_registry",
            )
        )
    return issues


def _bound_statement_scopes_by_claim(
    contract: Mapping[str, Any],
) -> dict[str, set[str]]:
    scopes_by_claim: dict[str, set[str]] = {}
    raw_statements = contract.get("statements")
    if not isinstance(raw_statements, Sequence) or isinstance(
        raw_statements,
        str | bytes | bytearray,
    ):
        return scopes_by_claim
    for statement in raw_statements:
        if not isinstance(statement, Mapping):
            continue
        claim_id = _text(statement.get("claim_id"))
        scope = _text(statement.get("statement_scope"))
        if not claim_id or not scope:
            continue
        if statement.get("has_text") is False:
            continue
        if _refs_from_value(statement.get("evidence_refs")) or _typed_blockers(statement):
            scopes_by_claim.setdefault(claim_id, set()).add(scope)
    return scopes_by_claim


def _public_section_bound(
    recommendation: Mapping[str, Any],
    *,
    claim_id: str,
    statements: Mapping[str, set[str]],
    statement_scopes: tuple[str, ...],
    support_keys: tuple[str, ...],
) -> bool:
    if any(scope in statements.get(claim_id, set()) for scope in statement_scopes):
        return True
    if any(_support_refs(recommendation, key) for key in support_keys):
        return True
    if "recommendation" in statement_scopes and _citation_refs(recommendation):
        return True
    return False


def _support_refs(recommendation: Mapping[str, Any], key: str) -> list[str]:
    refs: list[str] = []
    support_refs = recommendation.get("support_refs")
    if isinstance(support_refs, Mapping):
        refs.extend(_refs_from_value(support_refs.get(key)))
    refs.extend(_refs_from_value(recommendation.get(key)))
    return sorted(set(refs))


def _refs_from_value(value: object) -> list[str]:
    if isinstance(value, str):
        text = _text(value)
        return [text] if text else []
    if isinstance(value, Mapping):
        refs: list[str] = []
        for key in (
            "evidence_refs",
            "refs",
            "citation_refs",
            "source_refs",
            "data_refs",
            "method_refs",
            "norm_refs",
            "legal_refs",
            "uncertainty_refs",
            "authority_refs",
            "ref",
            "id",
        ):
            refs.extend(_refs_from_value(value.get(key)))
        return sorted(set(refs))
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        refs: list[str] = []
        for item in value:
            refs.extend(_refs_from_value(item))
        return sorted(set(refs))
    return []


def _typed_blockers(value: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    blockers = value.get("typed_blockers")
    if not isinstance(blockers, Sequence) or isinstance(blockers, str | bytes | bytearray):
        return []
    return [blocker for blocker in blockers if isinstance(blocker, Mapping)]


def normalize_decision_artifact_quality_report(
    report: Mapping[str, Any] | None,
    *,
    compiled_artifact: Mapping[str, Any] | None = None,
    final_claims: Sequence[Mapping[str, Any]] | None = None,
    claim_registry: Mapping[str, Any] | None = None,
    profile: str = "standard",
) -> dict[str, Any]:
    """Recompute quality status from a stored report and compiled artifact."""

    payload = dict(report or {})
    artifact = compiled_artifact
    if artifact is None and isinstance(payload.get("compiled_artifact"), Mapping):
        artifact = payload["compiled_artifact"]
    normalized = build_decision_artifact_quality_report(
        compiled_artifact=artifact or {},
        final_claims=final_claims,
        claim_registry=(
            claim_registry
            if claim_registry is not None
            else payload.get("runtime_claim_registry")
            if isinstance(payload.get("runtime_claim_registry"), Mapping)
            else None
        ),
        profile=profile,
    )
    return {**payload, **normalized}


def _required_section_issues(
    artifact: Mapping[str, Any],
    *,
    serious: bool,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for recommendation in _recommendations(artifact):
        if not _is_major(recommendation):
            continue
        sections = recommendation.get("sections")
        section_map = sections if isinstance(sections, Mapping) else {}
        for section in REQUIRED_MAJOR_RECOMMENDATION_SECTIONS:
            if _text(section_map.get(section)):
                continue
            issues.append(
                _issue(
                    code="major_recommendation_missing_required_section",
                    severity="fail" if serious else "warn",
                    claim_id=_text(recommendation.get("claim_id")),
                    section=section,
                    message=(
                        "Major public recommendations must include "
                        f"{section.replace('_', ' ')}."
                    ),
                    next_action=(
                        "Add the missing decision-artifact section or demote the "
                        "claim from a major recommendation with reviewer rationale."
                    ),
                )
            )
    return issues


def _uncertainty_language_issues(
    artifact: Mapping[str, Any],
    *,
    serious: bool,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for recommendation in _recommendations(artifact):
        if not _is_major(recommendation):
            continue
        sections = recommendation.get("sections")
        section_map = sections if isinstance(sections, Mapping) else {}
        for section in ("uncertainty", "residual_uncertainty"):
            text = _text(section_map.get(section))
            if not text:
                continue
            lowered = text.casefold()
            if any(pattern.search(text) for pattern in _UNQUALIFIED_UNCERTAINTY_PATTERNS):
                issues.append(
                    _issue(
                        code="uncertainty_language_overconfident",
                        severity="fail" if serious else "warn",
                        claim_id=_text(recommendation.get("claim_id")),
                        section=section,
                        message="Uncertainty language denies residual uncertainty.",
                        next_action=(
                            "Replace absolute uncertainty language with calibrated "
                            "residual uncertainty, assumptions, and monitoring bounds."
                        ),
                    )
                )
                continue
            if not any(token in lowered for token in _UNCERTAINTY_QUALIFIERS):
                issues.append(
                    _issue(
                        code="uncertainty_language_not_qualified",
                        severity="fail" if serious else "warn",
                        claim_id=_text(recommendation.get("claim_id")),
                        section=section,
                        message="Uncertainty section lacks calibrated qualifier language.",
                        next_action=(
                            "Describe estimates, assumptions, ranges, sensitivity, "
                            "or residual risk before publication."
                        ),
                    )
                )
    return issues


def _certainty_overstatement_issues(artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    text = "\n".join(_public_text_values(artifact))
    issues: list[dict[str, Any]] = []
    for dimension, patterns in _CERTAINTY_PATTERNS:
        if not any(pattern.search(text) for pattern in patterns):
            continue
        issues.append(
            _issue(
                code=f"overstated_{dimension}_certainty",
                severity="fail",
                certainty_dimension=dimension,
                message=(
                    f"Public decision artifact overstates {dimension} certainty."
                ),
                next_action=(
                    "Rewrite the public artifact to use calibrated claims, cite the "
                    "supporting refs, and state residual uncertainty."
                ),
            )
        )
    return issues


def _forbidden_public_export_issues(artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for path, key in _forbidden_paths(artifact):
        issues.append(
            _issue(
                code="public_export_contains_forbidden_data",
                severity="fail",
                field_path=path,
                forbidden_key=key,
                message="Public decision artifact contains private or sensitive data.",
                next_action=(
                    "Recompile the artifact with public redaction and keep hidden "
                    "benchmark answers, credentials, reviewer notes, and raw "
                    "sensitive data out of public exports."
                ),
            )
        )
    return issues


def _citation_preservation_issues(
    artifact: Mapping[str, Any],
    *,
    final_claims: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    expected = {
        _claim_id(claim): set(_citation_refs(claim))
        for claim in final_claims
        if _citation_refs(claim)
    }
    if not expected:
        return []
    exported = {
        _claim_id(item): set(_citation_refs(item))
        for item in [*_recommendations(artifact), *_supporting_claims(artifact)]
    }
    issues: list[dict[str, Any]] = []
    for claim_id, expected_refs in expected.items():
        missing = sorted(expected_refs - exported.get(claim_id, set()))
        if not missing:
            continue
        issues.append(
            _issue(
                code="citation_refs_dropped",
                severity="fail",
                claim_id=claim_id,
                missing_citation_refs=missing,
                message="Public decision artifact dropped citation refs from final claims.",
                next_action=(
                    "Recompile the public decision artifact preserving citation_refs "
                    "for every visible final claim."
                ),
            )
        )
    return issues


def _status_context_issues(
    *,
    artifact: Mapping[str, Any],
    quality_scorecard: Mapping[str, Any] | None,
    conflict_check: Mapping[str, Any] | None,
    approval_state: Mapping[str, Any] | str | None,
    serious: bool,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    context = artifact.get("decision_context")
    context_map = context if isinstance(context, Mapping) else {}
    quality_status = _status_from_context(
        context_map.get("quality_status"),
        quality_scorecard,
        fallback_key="quality_status",
    )
    conflict_status = _status_from_context(
        context_map.get("conflict_status"),
        conflict_check,
        fallback_key="status",
    )
    resolved_approval = _approval_state(approval_state, context_map, quality_scorecard)
    if quality_status in {"fail", "failed", "blocked"}:
        issues.append(
            _issue(
                code="decision_artifact_quality_scorecard_not_passing",
                severity="fail",
                message="Decision artifact cites a non-passing quality scorecard.",
                next_action="Resolve scorecard failures before public approval.",
                observed_status=quality_status,
            )
        )
    if conflict_status in {"conflict", "fail", "failed", "blocked"}:
        issues.append(
            _issue(
                code="decision_artifact_conflict_status_not_clear",
                severity="fail",
                message="Decision artifact cites unresolved conflict status.",
                next_action="Resolve or disclose policy conflicts before publication.",
                observed_status=conflict_status,
            )
        )
    if resolved_approval not in _APPROVAL_READY_STATES:
        issues.append(
            _issue(
                code="decision_artifact_not_approval_ready",
                severity="fail" if serious else "warn",
                message="Decision artifact is not in an approval-ready state.",
                next_action=(
                    "Complete approval, attach an accepted override, or keep the "
                    "artifact out of public release."
                ),
                observed_status=resolved_approval,
            )
        )
    return issues


def _collect_input_refs(
    *,
    artifact: Mapping[str, Any],
    policy_grounding_matrix: Mapping[str, Any] | None,
    quality_scorecard: Mapping[str, Any] | None,
    conflict_check: Mapping[str, Any] | None,
    assurance_refs: Mapping[str, Any] | None,
    policy_grounding_matrix_ref: str | None,
    quality_scorecard_ref: str | None,
    conflict_check_ref: str | None,
    approval_packet_ref: str | None,
) -> dict[str, str]:
    refs: dict[str, str] = {}
    for key, value in {
        "policy_grounding_matrix_ref": policy_grounding_matrix_ref,
        "quality_scorecard_ref": quality_scorecard_ref,
        "conflict_check_ref": conflict_check_ref,
        "approval_packet_ref": approval_packet_ref,
    }.items():
        if _text(value):
            refs[key] = _text(value)
    for payload in (
        artifact.get("refs"),
        policy_grounding_matrix,
        quality_scorecard,
        conflict_check,
        assurance_refs,
    ):
        if not isinstance(payload, Mapping):
            continue
        for key, value in payload.items():
            if not str(key).endswith("_ref") and not str(key).endswith("_trace"):
                continue
            ref_value = _text(value)
            if ref_value:
                normalized_key = str(key) if str(key).endswith("_ref") else f"{key}_ref"
                refs.setdefault(normalized_key, ref_value)
    return dict(sorted(refs.items()))


def _issue(
    *,
    code: str,
    severity: str,
    message: str,
    next_action: str,
    **extra: object,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "layer": "scientist_decision_artifacts",
        "phase": "decision_artifact_quality",
        "message": message,
        "next_action": next_action,
        **extra,
    }


def _status_from_issues(issues: Sequence[Mapping[str, Any]]) -> str:
    if any(issue.get("severity") == "fail" for issue in issues):
        return "fail"
    if any(issue.get("severity") == "warn" for issue in issues):
        return "warn"
    return "pass"


def _stable_report_ref(report: Mapping[str, Any]) -> str:
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _recommendations(artifact: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = artifact.get("recommendations")
    if not isinstance(raw, Sequence) or isinstance(raw, str | bytes | bytearray):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _supporting_claims(artifact: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = artifact.get("supporting_claims")
    if not isinstance(raw, Sequence) or isinstance(raw, str | bytes | bytearray):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _is_major(claim: Mapping[str, Any]) -> bool:
    value = claim.get("major")
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() not in {"0", "false", "minor", "no"}
    return bool(value)


def _claim_id(claim: Mapping[str, Any]) -> str:
    return _text(claim.get("claim_id") or claim.get("id") or "claim")


def _citation_refs(claim: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("citation_refs", "citations", "source_refs", "norm_refs"):
        value = claim.get(key)
        if isinstance(value, str):
            if _text(value):
                refs.append(_text(value))
        elif isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
            refs.extend(_text(item) for item in value if _text(item))
    return sorted(set(refs))


def _public_text_values(value: object) -> list[str]:
    if isinstance(value, Mapping):
        found: list[str] = []
        for item in value.values():
            found.extend(_public_text_values(item))
        return found
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        found: list[str] = []
        for item in value:
            found.extend(_public_text_values(item))
        return found
    if isinstance(value, str):
        text = _text(value)
        return [text] if text else []
    return []


def _forbidden_paths(value: object, *, path: str = "compiled_artifact") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            if _is_forbidden_key(key_text):
                found.append((child_path, key_text))
                continue
            found.extend(_forbidden_paths(item, path=child_path))
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for index, item in enumerate(value):
            found.extend(_forbidden_paths(item, path=f"{path}[{index}]"))
    return found


def _is_forbidden_key(key: str) -> bool:
    lowered = key.casefold()
    return any(token in lowered for token in PUBLIC_FORBIDDEN_KEY_TOKENS)


def _status_from_context(
    context_value: object,
    report: Mapping[str, Any] | None,
    *,
    fallback_key: str,
) -> str:
    context_status = _text(context_value).casefold()
    if context_status and context_status != "present":
        return context_status
    if isinstance(report, Mapping):
        return _text(report.get(fallback_key) or report.get("status")).casefold()
    return context_status or "missing"


def _approval_state(
    approval_state: Mapping[str, Any] | str | None,
    context: Mapping[str, Any],
    quality_scorecard: Mapping[str, Any] | None,
) -> str:
    if isinstance(approval_state, Mapping):
        explicit = _text(
            approval_state.get("state")
            or approval_state.get("approval_state")
            or approval_state.get("decision")
        )
        if explicit:
            return explicit.casefold()
    elif _text(approval_state):
        return _text(approval_state).casefold()
    context_state = _text(context.get("approval_state"))
    if context_state:
        return context_state.casefold()
    if isinstance(quality_scorecard, Mapping):
        return _text(quality_scorecard.get("approval_state")).casefold()
    return "missing"


def _is_serious_profile(profile: str) -> bool:
    return _text(profile).casefold() in SERIOUS_PROFILES


def _text(value: object) -> str:
    return str(value or "").strip()


__all__ = [
    "SCHEMA_VERSION",
    "SERIOUS_PROFILES",
    "build_decision_artifact_quality_report",
    "normalize_decision_artifact_quality_report",
]
