"""Claim-level legal authority evaluation for Lex NormPack results.

This module is the W3.B adapter layer between broad Lex retrieval and runtime
Policy Design Case authority surfaces. It deliberately treats retrieved legal
material as candidate context until a claim-level competence record satisfies
the requested authority type, jurisdiction fallback policy, actor/instrument
facets, and legal time window.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import date

from polisyos.legal_requirement import (
    LegalAuthorityRequirementSpec,
    compile_legal_authority_requirements,
    normalize_legal_authority_type,
)
from polisyos.lex.common import parse_iso_date

LEGAL_AUTHORITY_REPORT_SCHEMA_VERSION = "policyos.lex.legal_authority_report.v1"
LEGAL_AUTHORITY_RECORD_SCHEMA_VERSION = "policyos.lex.legal_authority_record.v1"
LEGAL_WINDOW_SPLIT_SCHEMA_VERSION = "policyos.lex.legal_authority_window_split.v1"
LEGAL_AUTHORITY_RULE_VERSION = "lex-legal-authority:v1"

LEGAL_ADMISSIBILITY_GRADES = (
    "admissible",
    "context_only",
    "proxy_with_limitation",
    "contested",
    "blocked",
    "out_of_scope",
)
LEGACY_LEGAL_ADMISSIBILITY_GRADES = (
    "context_only",
    "candidate_norm",
    "selected_authority",
    "limited_authority",
    "contested_authority",
    "blocked_no_authority",
)
LEGAL_AUTHORITY_TYPES = (
    "implementing",
    "delegating",
    "enabling",
    "funding",
    "oversight",
    "appeal_or_contestability",
)

_SERIOUS_AUTHORITY_PROFILES = frozenset(
    {
        "governed",
        "official",
        "production",
        "publishable",
        "regulated",
    }
)
_AUTHORITY_REQUIRED_KEYS = frozenset(
    {
        "legal_authority_required",
        "fiscal_authority_required",
        "implementation_authority_required",
        "contestability_authority_required",
    }
)
_LLM_PROVENANCE_KINDS = frozenset(
    {
        "llm_candidate",
        "llm_critic",
        "llm_drafter",
        "llm_summary",
    }
)


def build_legal_authority_report(
    *,
    target_context: Mapping[str, Any],
    candidate_norms: Sequence[Mapping[str, Any]],
    recommendation_claims: Sequence[Mapping[str, Any]],
    legal_requirement_specs: (
        Sequence[Mapping[str, Any] | LegalAuthorityRequirementSpec] | None
    ) = None,
    jurisdiction_fallback_config: Mapping[str, Any] | None = None,
    producer_artifact_ref: str | None = None,
    capability_bindings: Sequence[Mapping[str, Any] | object] = (),
) -> dict[str, Any]:
    """Evaluate retrieved Lex norms as claim-level legal authority records.

    Args:
        target_context: Request-level jurisdiction, domain, as-of, authority,
            and time semantics.
        candidate_norms: Retrieved NormPack candidates. These may be selected,
            rejected, context-only, or blocked after claim-level validation.
        recommendation_claims: Final/recommendation claims that need legal
            authority or explicit no-anchor rationale.
        jurisdiction_fallback_config: Governed jurisdiction fallback rules.
            Absence of a matching rule fails closed; no universal fallback is
            inferred.
        producer_artifact_ref: Optional persisted Lex artifact ref. A stable
            derived ref is emitted when absent.
        capability_bindings: Shared capability graph bindings for Lex normative
            facts, rule thresholds, amendments, and temporal audit refs.

    Returns:
        A report containing legal authority records, per-claim anchors,
        competence-window splits, and scorecard-consumable issues.
    """

    capability_norms = _norms_from_capability_bindings(capability_bindings)
    candidates = [
        *[dict(norm) for norm in candidate_norms if isinstance(norm, Mapping)],
        *capability_norms,
    ]
    claims = [dict(claim) for claim in recommendation_claims if isinstance(claim, Mapping)]
    config = dict(jurisdiction_fallback_config or {})
    requirements = _legal_requirement_specs(
        legal_requirement_specs=legal_requirement_specs,
        target_context=target_context,
        claims=claims,
        jurisdiction_fallback_config=config,
    )
    artifact_ref = producer_artifact_ref or _stable_ref(
        {
            "target_context": dict(target_context),
            "candidate_norm_refs": [_norm_id(norm) for norm in candidates],
            "claim_refs": [_claim_id(claim, index) for index, claim in enumerate(claims)],
            "legal_requirement_refs": [requirement.requirement_id for requirement in requirements],
        }
    )
    records: list[dict[str, Any]] = []
    anchors: list[dict[str, Any]] = []
    splits: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    claim_by_id = {
        _claim_id(claim, index): claim for index, claim in enumerate(claims)
    }

    for index, requirement in enumerate(requirements):
        claim = claim_by_id.get(requirement.claim_id) or _claim_from_requirement(requirement)
        claim_result = _evaluate_claim(
            claim=claim,
            claim_index=index,
            requirement=requirement,
            target_context=target_context,
            candidate_norms=candidates,
            fallback_config=config,
            producer_artifact_ref=artifact_ref,
        )
        records.extend(claim_result["records"])
        anchors.append(claim_result["anchor"])
        splits.extend(claim_result["splits"])
        issues.extend(claim_result["issues"])

    status = _status_from_issues(issues)
    selected_norm_refs = _dedupe(
        [
            ref
            for anchor in anchors
            for ref in _as_text_list(anchor.get("selected_norm_refs"))
        ]
    )
    rejected_norm_refs = _dedupe(
        [
            ref
            for anchor in anchors
            for ref in _as_text_list(anchor.get("rejected_norm_refs"))
        ]
    )
    return {
        "schema_version": LEGAL_AUTHORITY_REPORT_SCHEMA_VERSION,
        "status": status,
        "capability_reality_status": "implemented",
        "runtime_authority_envelope": _authority_envelope(),
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "producer_component": "polisyos.lex.normpack.legal_authority",
        "producer_artifact_ref": artifact_ref,
        "rule_version_ref": LEGAL_AUTHORITY_RULE_VERSION,
        "legal_authority_required": any(
            bool(anchor.get("legal_authority_required")) for anchor in anchors
        ),
        "legal_requirement_specs": [
            requirement.model_dump(mode="json") for requirement in requirements
        ],
        "legal_authority_records": records,
        "claim_legal_anchors": anchors,
        "claim_window_splits": splits,
        "selected_norm_refs": selected_norm_refs,
        "rejected_norm_refs": rejected_norm_refs,
        "issues": issues,
        "issue_codes": [str(issue.get("code")) for issue in issues if issue.get("code")],
        "blocking_issue_count": sum(1 for issue in issues if issue.get("severity") == "fail"),
        "summary": {
            "claim_count": len(claims),
            "legal_requirement_spec_count": len(requirements),
            "candidate_norm_count": len(candidates),
            "capability_binding_count": len(capability_norms),
            "legal_authority_record_count": len(records),
            "claim_window_split_count": len(splits),
            "selected_norm_ref_count": len(selected_norm_refs),
            "rejected_norm_ref_count": len(rejected_norm_refs),
            "issue_count": len(issues),
        },
    }


def _evaluate_claim(
    *,
    claim: Mapping[str, Any],
    claim_index: int,
    requirement: LegalAuthorityRequirementSpec,
    target_context: Mapping[str, Any],
    candidate_norms: Sequence[Mapping[str, Any]],
    fallback_config: Mapping[str, Any],
    producer_artifact_ref: str,
) -> dict[str, Any]:
    claim_id = requirement.claim_id or _claim_id(claim, claim_index)
    required = requirement.mandatory
    required_authority_types = tuple(
        authority_type.value for authority_type in requirement.authority_types
    )
    rationale = _no_anchor_rationale(claim)
    if requirement.out_of_scope or (not required and not required_authority_types):
        return {
            "records": [],
            "splits": [],
            "issues": [],
            "anchor": _claim_anchor(
                claim_id=claim_id,
                required=False,
                legal_admissibility_grade="out_of_scope",
                candidate_norm_refs=[_norm_id(norm) for norm in candidate_norms if _norm_id(norm)],
                selected_norm_refs=[],
                rejected_norm_refs=[],
                context_only_norm_refs=[],
                requirement_ref=requirement.requirement_id,
                no_anchor_rationale=rationale,
            ),
        }

    segments = _claim_segments(
        claim,
        target_context,
        candidate_norms,
        requirement=requirement,
    )
    selected_norm_refs: list[str] = []
    rejected_norm_refs: list[str] = []
    context_only_norm_refs: list[str] = []
    selected_authority_types: list[str] = []
    blocked_authority_types: list[str] = []
    legal_authority_record_refs: list[str] = []
    legal_authority_blocker_refs: list[str] = []
    blocked_segment_refs: list[str] = []
    records: list[dict[str, Any]] = []
    splits: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    for authority_type in required_authority_types:
        authority_type_selected = False
        for segment in segments:
            evaluations = [
                _evaluate_norm_for_segment(
                    norm=dict(norm),
                    claim=claim,
                    claim_id=claim_id,
                    requirement=requirement,
                    target_context=target_context,
                    authority_type=authority_type,
                    segment=segment,
                    fallback_config=fallback_config,
                    producer_artifact_ref=producer_artifact_ref,
                )
                for norm in candidate_norms
            ]
            selected = _select_authority_evaluation(evaluations)
            if selected is None:
                selected = _blocked_record_without_norm(
                    claim=claim,
                    claim_id=claim_id,
                    requirement=requirement,
                    target_context=target_context,
                    authority_type=authority_type,
                    segment=segment,
                    producer_artifact_ref=producer_artifact_ref,
                )
                evaluations.append(selected)
            records.append(selected)
            record_ref = _text(selected.get("legal_authority_record_id"))
            if record_ref:
                legal_authority_record_refs.append(record_ref)
            selected_issues = _mapping_list(selected.get("issues"))
            issues.extend(selected_issues)
            grade = _legal_grade(selected)
            norm_ref = _text(selected.get("norm_ref"))
            if grade in {"admissible", "proxy_with_limitation", "contested"}:
                authority_type_selected = True
                if norm_ref:
                    selected_norm_refs.append(norm_ref)
                selected_authority_types.append(authority_type)
            else:
                if norm_ref:
                    rejected_norm_refs.append(norm_ref)
                if grade in {"context_only", "blocked"} and norm_ref:
                    context_only_norm_refs.append(norm_ref)
                blocker_ref = _text(selected.get("blocker_ref"))
                if blocker_ref:
                    legal_authority_blocker_refs.append(blocker_ref)
                segment_ref = _text(selected.get("claim_segment_ref"))
                if segment_ref:
                    blocked_segment_refs.append(segment_ref)
            for rejected in evaluations:
                if rejected is selected:
                    continue
                rejected_ref = _text(rejected.get("norm_ref"))
                rejected_grade = _legal_grade(rejected)
                if rejected_ref and rejected_ref not in selected_norm_refs:
                    rejected_norm_refs.append(rejected_ref)
                if rejected_grade == "context_only" and rejected_ref:
                    context_only_norm_refs.append(rejected_ref)
            splits.append(
                _claim_window_split(
                    claim_id=claim_id,
                    authority_type=authority_type,
                    segment=segment,
                    selected=selected,
                )
            )
        if not authority_type_selected:
            blocked_authority_types.append(authority_type)

    selected_norm_refs = _dedupe(selected_norm_refs)
    rejected_norm_refs = [
        ref for ref in _dedupe(rejected_norm_refs) if ref not in set(selected_norm_refs)
    ]
    grades = [_legal_grade(record) for record in records]
    if (required and not selected_norm_refs) or any(
        grade == "blocked" for grade in grades
    ):
        anchor_grade = "blocked"
    elif any(grade == "contested" for grade in grades):
        anchor_grade = "contested"
    elif any(grade == "proxy_with_limitation" for grade in grades):
        anchor_grade = "proxy_with_limitation"
    elif selected_norm_refs:
        anchor_grade = "admissible"
    elif context_only_norm_refs:
        anchor_grade = "context_only"
    else:
        anchor_grade = "context_only"
    if anchor_grade == "blocked" and context_only_norm_refs and not selected_norm_refs:
        anchor_grade = "context_only"
    no_anchor_refs = _dedupe(
        [
            ref
            for record in records
            for ref in _as_text_list(record.get("no_anchor_refs"))
        ]
    )
    return {
        "records": records,
        "splits": splits,
        "issues": issues,
        "anchor": _claim_anchor(
            claim_id=claim_id,
            required=required,
            legal_admissibility_grade=anchor_grade,
            candidate_norm_refs=[_norm_id(norm) for norm in candidate_norms if _norm_id(norm)],
            selected_norm_refs=selected_norm_refs,
            rejected_norm_refs=rejected_norm_refs,
            context_only_norm_refs=_dedupe(context_only_norm_refs),
            selected_authority_types=_dedupe(selected_authority_types),
            blocked_authority_types=_dedupe(blocked_authority_types),
            legal_authority_record_refs=_dedupe(legal_authority_record_refs),
            legal_authority_blocker_refs=_dedupe(legal_authority_blocker_refs),
            blocked_segment_refs=_dedupe(blocked_segment_refs),
            no_anchor_refs=no_anchor_refs,
            requirement_ref=requirement.requirement_id,
            no_anchor_rationale=rationale,
        ),
    }


def _evaluate_norm_for_segment(
    *,
    norm: dict[str, Any],
    claim: Mapping[str, Any],
    claim_id: str,
    requirement: LegalAuthorityRequirementSpec,
    target_context: Mapping[str, Any],
    authority_type: str,
    segment: Mapping[str, str | None],
    fallback_config: Mapping[str, Any],
    producer_artifact_ref: str,
) -> dict[str, Any]:
    norm_id = _norm_id(norm)
    window = _window_override(norm, segment)
    norm_for_segment = {**norm, **window}
    missing: list[str] = []
    issues: list[dict[str, Any]] = []
    if _is_llm_candidate(norm_for_segment):
        issues.append(
            _issue(
                code="legal_authority_llm_candidate_not_authority",
                claim_id=claim_id,
                norm_id=norm_id,
                authority_type=authority_type,
                message=(
                    "LLM-generated legal summaries are candidates and cannot satisfy "
                    "claim-level legal authority."
                ),
                next_action=(
                    "Resolve the deterministic Lex norm/version/provenance and "
                    "competence facets before selecting authority."
                ),
            )
        )
        return _authority_record(
            claim=claim,
            claim_id=claim_id,
            norm=norm_for_segment,
            requirement=requirement,
            authority_type=authority_type,
            segment=segment,
            producer_artifact_ref=producer_artifact_ref,
            legal_admissibility_grade="context_only",
            fallback={},
            missing_facets=("deterministic_lex_validation",),
            issues=issues,
            reason_code="legal_authority_llm_candidate_not_authority",
        )
    for field_name in ("norm_version_ref", "source_provenance_ref"):
        if not _text(norm_for_segment.get(field_name)):
            missing.append(field_name)

    claim_jurisdiction = requirement.jurisdiction or _claim_jurisdiction(claim, target_context)
    norm_jurisdiction = _text(norm_for_segment.get("jurisdiction"))
    fallback = _fallback_resolution(
        from_jurisdiction=claim_jurisdiction,
        to_jurisdiction=norm_jurisdiction,
        authority_type=authority_type,
        claim=claim,
        config=fallback_config,
    )
    if fallback.get("blocked"):
        issues.append(
            _issue(
                code="legal_authority_fallback_policy_missing",
                claim_id=claim_id,
                norm_id=norm_id,
                authority_type=authority_type,
                message=(
                    "Jurisdiction fallback is not configured for this claim, norm, "
                    "authority type, and instrument."
                ),
                next_action=(
                    "Add governed per-jurisdiction fallback config or emit a legal "
                    "authority blocker for the affected claim segment."
                ),
            )
        )

    norm_authority_types = {
        _authority_type_value(value)
        for value in _as_text_list(norm_for_segment.get("authority_types"))
        if _authority_type_value(value)
    }
    if authority_type not in norm_authority_types:
        missing.append(f"authority_type:{authority_type}")
        issues.append(
            _issue(
                code="legal_authority_type_not_carried_by_norm",
                claim_id=claim_id,
                norm_id=norm_id,
                authority_type=authority_type,
                message=(
                    f"Norm {norm_id or '<missing>'} does not carry {authority_type} "
                    "authority for the claim."
                ),
                next_action=(
                    "Select a norm carrying the requested authority type or split the "
                    "claim into authority-specific legal blockers."
                ),
            )
        )

    norm_actor_ref = _text(
        norm_for_segment.get("competent_actor_ref")
        or norm_for_segment.get("competent_authority")
        or norm_for_segment.get("competence")
    )
    if not norm_actor_ref:
        missing.append("competent_actor_ref")
    elif requirement.required_actor_refs and norm_actor_ref not in requirement.required_actor_refs:
        missing.append("competent_actor_ref_mismatch")
    if not _instrument_matches(norm_for_segment, claim, requirement=requirement):
        missing.append("instrument_types")
    if _norm_hierarchy_depth(norm_for_segment) < requirement.required_hierarchy_depth:
        missing.append("hierarchy_depth")
    if authority_type in {"implementing", "delegating", "enabling"} and not _text(
        norm_for_segment.get("implementation_authority_ref")
        or norm_for_segment.get("implementation_authority")
    ):
        missing.append("implementation_authority_ref")
    elif authority_type in {"implementing", "delegating", "enabling"}:
        norm_implementation_ref = _text(
            norm_for_segment.get("implementation_authority_ref")
            or norm_for_segment.get("implementation_authority")
        )
        if (
            requirement.required_implementation_authority_refs
            and norm_implementation_ref not in requirement.required_implementation_authority_refs
        ):
            missing.append("implementation_authority_ref_mismatch")
    if authority_type == "funding" and not _text(
        norm_for_segment.get("fiscal_authority_ref") or norm_for_segment.get("fiscal_authority")
    ):
        missing.append("fiscal_authority_ref")
    elif authority_type == "funding":
        norm_fiscal_ref = _text(
            norm_for_segment.get("fiscal_authority_ref") or norm_for_segment.get("fiscal_authority")
        )
        if requirement.required_fiscal_authority_refs and norm_fiscal_ref not in (
            requirement.required_fiscal_authority_refs
        ):
            missing.append("fiscal_authority_ref_mismatch")
    if not _has_effective_window(norm_for_segment):
        missing.append("legal_effective_window")
    elif not _segment_within_norm_window(segment, norm_for_segment):
        missing.append("legal_effective_window_overlap")
    if _text(norm_for_segment.get("source_authority")) == "":
        missing.append("source_authority")
    if missing:
        issues.append(
            _issue(
                code="legal_authority_missing_claim_level_facets",
                claim_id=claim_id,
                norm_id=norm_id,
                authority_type=authority_type,
                message=(
                    "Retrieved legal context is missing claim-level competence, "
                    "instrument, implementation, fiscal, provenance, or time facets."
                ),
                next_action=(
                    "Resolve deterministic Lex facets before using this norm as "
                    "recommendation-level legal authority."
                ),
                missing_facets=missing,
            )
        )

    conflict_state = _text(norm_for_segment.get("conflict_state")).casefold()
    preemption_state = _text(norm_for_segment.get("preemption_state")).casefold()
    supersession_state = _text(norm_for_segment.get("supersession_state")).casefold()
    if supersession_state in {"superseded", "blocked"} or conflict_state in {
        "blocked",
        "conflict",
    }:
        missing.append("conflict_or_supersession_clearance")
    if missing or fallback.get("blocked"):
        grade = _missing_grade(
            missing=missing,
            fallback_blocked=bool(fallback.get("blocked")),
            norm_authority_types=norm_authority_types,
        )
        return _authority_record(
            claim=claim,
            claim_id=claim_id,
            norm=norm_for_segment,
            requirement=requirement,
            authority_type=authority_type,
            segment=segment,
            producer_artifact_ref=producer_artifact_ref,
            legal_admissibility_grade=grade,
            fallback=fallback,
            missing_facets=tuple(_dedupe(missing)),
            issues=issues,
            reason_code=_primary_reason_code(issues, missing),
        )
    if conflict_state in {"contested", "review_required"} or preemption_state == "contested":
        grade = "contested"
    elif (
        conflict_state in {"limited", "partial"}
        or preemption_state == "limited"
        or fallback.get("disposition") == "configured"
    ):
        grade = "proxy_with_limitation"
    else:
        grade = "admissible"
    return _authority_record(
        claim=claim,
        claim_id=claim_id,
        norm=norm_for_segment,
        requirement=requirement,
        authority_type=authority_type,
        segment=segment,
        producer_artifact_ref=producer_artifact_ref,
        legal_admissibility_grade=grade,
        fallback=fallback,
        missing_facets=(),
        issues=issues,
        reason_code="claim_level_legal_authority_selected",
    )


def _authority_record(
    *,
    claim: Mapping[str, Any],
    claim_id: str,
    norm: Mapping[str, Any],
    requirement: LegalAuthorityRequirementSpec,
    authority_type: str,
    segment: Mapping[str, str | None],
    producer_artifact_ref: str,
    legal_admissibility_grade: str,
    fallback: Mapping[str, Any],
    missing_facets: Sequence[str],
    issues: Sequence[Mapping[str, Any]],
    reason_code: str,
) -> dict[str, Any]:
    norm_id = _norm_id(norm)
    start = _text(segment.get("start")) or _text(norm.get("effective_from"))
    end = _text(segment.get("end")) or None
    segment_ref = _segment_ref(claim_id, authority_type, start, end)
    record_id = _record_ref(claim_id, authority_type, norm_id, start, end)
    legacy_grade = _legacy_grade(legal_admissibility_grade)
    blocking = legal_admissibility_grade in {"context_only", "blocked", "out_of_scope"}
    no_anchor_ref = f"legal-authority-no-anchor:{record_id}" if blocking else None
    return {
        "schema_version": LEGAL_AUTHORITY_RECORD_SCHEMA_VERSION,
        "legal_authority_record_id": record_id,
        "legal_requirement_ref": requirement.requirement_id,
        "claim_ref": _text(claim.get("claim_ref")) or claim_id,
        "claim_id": claim_id,
        "claim_segment_ref": segment_ref,
        "norm_ref": norm_id,
        "norm_version_ref": _text(norm.get("norm_version_ref")),
        "source_provenance_ref": _text(norm.get("source_provenance_ref")),
        "jurisdiction": _text(norm.get("jurisdiction")),
        "jurisdiction_fallback_policy_ref": _text(fallback.get("policy_ref")),
        "fallback_path": _as_text_list(fallback.get("path")),
        "fallback_disposition": _text(fallback.get("disposition")) or "none",
        "required_hierarchy_depth": requirement.required_hierarchy_depth,
        "authority_basis": _text(norm.get("authority_basis"))
        or _text(norm.get("source_authority")),
        "authority_type": authority_type,
        "authority_types": [authority_type],
        "competent_actor_ref": _text(
            norm.get("competent_actor_ref")
            or norm.get("competent_authority")
            or norm.get("competence")
        ),
        "hierarchy_position": _text(norm.get("hierarchy_position") or norm.get("authority_level")),
        "instrument_types": _as_text_list(norm.get("instrument_types"))
        or _as_text_list(norm.get("policy_instrument")),
        "implementation_authority_ref": _text(
            norm.get("implementation_authority_ref") or norm.get("implementation_authority")
        ),
        "fiscal_authority_ref": _text(
            norm.get("fiscal_authority_ref") or norm.get("fiscal_authority")
        ),
        "legal_as_of": _text(norm.get("legal_as_of")) or _text(norm.get("as_of")),
        "legal_effective_window": _legal_effective_window(norm),
        "policy_effective_window": _window_payload(
            claim.get("policy_effective_window") or claim.get("implementation_period")
        ),
        "implementation_period": _window_payload(claim.get("implementation_period")),
        "fiscal_period": _window_payload(claim.get("fiscal_period")),
        "publication_time": _text(claim.get("publication_time")),
        "replay_time": _text(claim.get("replay_time")),
        "preemption_state": _text(norm.get("preemption_state")) or "not_assessed",
        "conflict_state": _text(norm.get("conflict_state")) or "clear",
        "supersession_state": _text(norm.get("supersession_state")) or "current",
        "contestability_or_appeal_ref": _text(
            norm.get("contestability_or_appeal_ref") or norm.get("appeal_ref")
        ),
        "legal_admissibility_grade": legal_admissibility_grade,
        "admissibility_grade": legacy_grade,
        "legacy_admissibility_grade": legacy_grade,
        "selected_norm_refs": [norm_id] if norm_id and not blocking else [],
        "rejected_norm_refs": [norm_id] if norm_id and blocking else [],
        "no_anchor_refs": [no_anchor_ref] if no_anchor_ref else [],
        "no_anchor_rationale": _no_anchor_rationale(claim),
        "blocker_ref": f"legal-authority-blocker:{record_id}"
        if legal_admissibility_grade == "blocked"
        else None,
        "limitation_ref": f"legal-authority-limitation:{record_id}"
        if legal_admissibility_grade == "proxy_with_limitation"
        else None,
        "rule_version_ref": _text(norm.get("rule_version_ref")) or LEGAL_AUTHORITY_RULE_VERSION,
        "authority_profile_ref": _text(
            claim.get("authority_profile_ref") or claim.get("authority_profile")
        ),
        "producer_artifact_ref": producer_artifact_ref,
        "reader_effect": _reader_effect(legal_admissibility_grade),
        "missing_facets": list(missing_facets),
        "required_instrument_classes": list(requirement.required_instrument_classes),
        "scope_predicates": requirement.scope_predicates.model_dump(mode="json"),
        "reason_code": reason_code,
        "issues": [dict(issue) for issue in issues],
        "capability_ref": _text(norm.get("capability_ref")),
        "construct_ref": _text(norm.get("construct_ref")),
        "capability_index_ref": _text(norm.get("capability_index_ref")),
        "construct_registry_ref": _text(norm.get("construct_registry_ref")),
        "authority_composition_rule_ref": _text(
            norm.get("authority_composition_rule_ref")
            or norm.get("rule_version_ref")
        ),
        "lex_normative_fact_refs": _as_text_list(norm.get("lex_normative_fact_refs")),
        "lex_rule_threshold_refs": _as_text_list(norm.get("lex_rule_threshold_refs")),
        "lex_amendment_refs": _as_text_list(norm.get("lex_amendment_refs")),
        "lex_temporal_audit_refs": _as_text_list(norm.get("lex_temporal_audit_refs")),
        "legal_hierarchy_constraints": _as_text_list(
            norm.get("legal_hierarchy_constraints")
        ),
    }


def _blocked_record_without_norm(
    *,
    claim: Mapping[str, Any],
    claim_id: str,
    requirement: LegalAuthorityRequirementSpec,
    target_context: Mapping[str, Any],
    authority_type: str,
    segment: Mapping[str, str | None],
    producer_artifact_ref: str,
) -> dict[str, Any]:
    issue = _issue(
        code="legal_authority_no_candidate_norm",
        claim_id=claim_id,
        norm_id=None,
        authority_type=authority_type,
        message="No candidate Lex norm can satisfy this legal authority slot.",
        next_action="Retrieve a claim-level norm or emit an accepted legal deficit.",
    )
    return _authority_record(
        claim=claim,
        claim_id=claim_id,
        norm={
            "norm_id": None,
            "jurisdiction": requirement.jurisdiction or _claim_jurisdiction(claim, target_context),
            "legal_as_of": _text(target_context.get("as_of") or target_context.get("as_of_iso")),
            "rule_version_ref": LEGAL_AUTHORITY_RULE_VERSION,
        },
        requirement=requirement,
        authority_type=authority_type,
        segment=segment,
        producer_artifact_ref=producer_artifact_ref,
        legal_admissibility_grade="blocked",
        fallback={},
        missing_facets=(f"authority_type:{authority_type}",),
        issues=[issue],
        reason_code="legal_authority_no_candidate_norm",
    )


def _claim_window_split(
    *,
    claim_id: str,
    authority_type: str,
    segment: Mapping[str, str | None],
    selected: Mapping[str, Any],
) -> dict[str, Any]:
    start = _text(segment.get("start"))
    end = _text(segment.get("end"))
    return {
        "schema_version": LEGAL_WINDOW_SPLIT_SCHEMA_VERSION,
        "claim_segment_ref": _segment_ref(claim_id, authority_type, start, end),
        "split_reason": _text(segment.get("split_reason")) or "legal_competence_window",
        "source_claim_ref": claim_id,
        "legal_window_start": start,
        "legal_window_end": end,
        "legal_segment_disposition": _legal_grade(selected),
        "segment_disposition": _text(selected.get("admissibility_grade")),
        "segment_authority_types": [authority_type],
        "segment_blocker_ref": _text(selected.get("blocker_ref")),
        "segment_limitation_ref": _text(selected.get("limitation_ref")),
        "rejoin_policy": "preserve_weakest_segment_disposition",
    }


def _claim_anchor(
    *,
    claim_id: str,
    required: bool,
    legal_admissibility_grade: str,
    candidate_norm_refs: Sequence[str],
    selected_norm_refs: Sequence[str],
    rejected_norm_refs: Sequence[str],
    context_only_norm_refs: Sequence[str],
    selected_authority_types: Sequence[str] = (),
    blocked_authority_types: Sequence[str] = (),
    legal_authority_record_refs: Sequence[str] = (),
    legal_authority_blocker_refs: Sequence[str] = (),
    blocked_segment_refs: Sequence[str] = (),
    no_anchor_refs: Sequence[str] = (),
    requirement_ref: str | None = None,
    no_anchor_rationale: str | None = None,
) -> dict[str, Any]:
    legacy_grade = _legacy_anchor_grade(
        legal_admissibility_grade=legal_admissibility_grade,
        required=required,
    )
    return {
        "claim_id": claim_id,
        "major": True,
        "legal_authority_required": required,
        "status": _anchor_status(
            legal_admissibility_grade=legal_admissibility_grade,
            required=required,
        ),
        "legal_admissibility_grade": legal_admissibility_grade,
        "admissibility_grade": legacy_grade,
        "legacy_admissibility_grade": legacy_grade,
        "reason_code": _anchor_reason_code(legal_admissibility_grade),
        "candidate_norm_refs": list(_dedupe(candidate_norm_refs)),
        "selected_norm_refs": list(_dedupe(selected_norm_refs)),
        "rejected_norm_refs": [
            ref for ref in _dedupe(rejected_norm_refs) if ref not in set(selected_norm_refs)
        ],
        "context_only_norm_refs": list(_dedupe(context_only_norm_refs)),
        "no_anchor_refs": list(_dedupe(no_anchor_refs)),
        "selected_authority_types": list(_dedupe(selected_authority_types)),
        "blocked_authority_types": list(_dedupe(blocked_authority_types)),
        "legal_authority_record_refs": list(_dedupe(legal_authority_record_refs)),
        "legal_authority_blocker_refs": list(_dedupe(legal_authority_blocker_refs)),
        "blocked_segment_refs": list(_dedupe(blocked_segment_refs)),
        "legal_requirement_ref": requirement_ref,
        "anchor_mode": "claim_level_legal_authority",
        "no_anchor_rationale": no_anchor_rationale,
    }


def _anchor_status(*, legal_admissibility_grade: str, required: bool) -> str:
    if legal_admissibility_grade in {"admissible", "proxy_with_limitation", "out_of_scope"}:
        return "pass"
    if required:
        return "fail"
    return "pass"


def _claim_requires_legal_authority(
    claim: Mapping[str, Any],
    target_context: Mapping[str, Any],
) -> bool:
    for key in _AUTHORITY_REQUIRED_KEYS:
        if _bool(claim.get(key)):
            return True
    if _as_text_list(claim.get("required_authority_types") or claim.get("authority_types")):
        return True
    profile = _text(
        claim.get("authority_profile")
        or claim.get("requested_authority_level")
        or target_context.get("authority_profile")
        or target_context.get("requested_authority_level")
    ).casefold()
    return bool(profile in _SERIOUS_AUTHORITY_PROFILES and bool(claim.get("major", True)))


def _required_authority_types(
    claim: Mapping[str, Any],
    *,
    required: bool,
) -> tuple[str, ...]:
    raw = _as_text_list(claim.get("required_authority_types") or claim.get("authority_types"))
    if raw:
        return tuple(dict.fromkeys(raw))
    if _bool(claim.get("fiscal_authority_required")):
        return ("funding",)
    return ("implementing",) if required else ()


def _claim_segments(
    claim: Mapping[str, Any],
    target_context: Mapping[str, Any],
    candidate_norms: Sequence[Mapping[str, Any]],
    *,
    requirement: LegalAuthorityRequirementSpec,
) -> tuple[dict[str, str | None], ...]:
    claim_window = {
        "start": requirement.temporal_competence_window.start,
        "end": requirement.temporal_competence_window.end,
    }
    if not claim_window.get("start") and not claim_window.get("end"):
        claim_window = _window_payload(
            claim.get("implementation_period")
            or claim.get("policy_effective_window")
            or target_context.get("implementation_period")
            or target_context.get("policy_effective_window")
        )
    default_start = claim_window.get("start") or _text(target_context.get("as_of"))
    default_end = claim_window.get("end")
    for norm in candidate_norms:
        windows = _mapping_list(norm.get("competence_windows"))
        if not windows:
            continue
        segments: list[dict[str, str | None]] = []
        for window in windows:
            start = _text(window.get("start") or window.get("legal_window_start"))
            end = _text(window.get("end") or window.get("legal_window_end"))
            segments.append(
                {
                    "start": _max_date_text(default_start, start),
                    "end": _min_date_text(default_end, end),
                    "split_reason": "legal_competence_change",
                }
            )
        return tuple(segment for segment in segments if segment.get("start") or segment.get("end"))
    return (
        {
            "start": default_start,
            "end": default_end,
            "split_reason": "single_legal_window",
        },
    )


def _select_authority_evaluation(
    evaluations: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    order = {
        "admissible": 0,
        "proxy_with_limitation": 1,
        "contested": 2,
        "blocked": 3,
        "context_only": 4,
        "out_of_scope": 5,
    }
    if not evaluations:
        return None
    return sorted(
        evaluations,
        key=lambda record: (
            order.get(_legal_grade(record), 99),
            _text(record.get("norm_ref")),
        ),
    )[0]


def _fallback_resolution(
    *,
    from_jurisdiction: str,
    to_jurisdiction: str,
    authority_type: str,
    claim: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    if not from_jurisdiction or not to_jurisdiction or from_jurisdiction == to_jurisdiction:
        return {"disposition": "none", "path": []}
    instrument = _first_text(
        claim.get("policy_instrument"),
        claim.get("instrument_type"),
    )
    for rule in _mapping_list(config.get("rules")):
        if _text(rule.get("from_jurisdiction")) != from_jurisdiction:
            continue
        if _text(rule.get("to_jurisdiction")) != to_jurisdiction:
            continue
        allowed_types = set(_as_text_list(rule.get("authority_types")))
        if allowed_types and authority_type not in allowed_types:
            continue
        allowed_instruments = set(_as_text_list(rule.get("instrument_types")))
        if allowed_instruments and instrument and instrument not in allowed_instruments:
            continue
        if _text(rule.get("disposition")).casefold() not in {"allowed", "configured", "pass"}:
            continue
        return {
            "policy_ref": _text(rule.get("policy_ref") or config.get("config_ref")),
            "path": [from_jurisdiction, to_jurisdiction],
            "disposition": "configured",
            "blocked": False,
        }
    return {
        "path": [from_jurisdiction, to_jurisdiction],
        "disposition": "blocked_no_config",
        "blocked": True,
    }


def _window_override(
    norm: Mapping[str, Any],
    segment: Mapping[str, str | None],
) -> dict[str, Any]:
    windows = _mapping_list(norm.get("competence_windows"))
    start = _text(segment.get("start"))
    end = _text(segment.get("end"))
    for window in windows:
        window_start = _text(window.get("start") or window.get("legal_window_start"))
        window_end = _text(window.get("end") or window.get("legal_window_end"))
        if window_start == start and window_end == end:
            return dict(window)
        if _windows_overlap(
            {"start": start, "end": end},
            {"start": window_start, "end": window_end},
        ):
            return dict(window)
    return {}


def _instrument_matches(
    norm: Mapping[str, Any],
    claim: Mapping[str, Any],
    *,
    requirement: LegalAuthorityRequirementSpec,
) -> bool:
    claim_instrument = _first_text(claim.get("policy_instrument"), claim.get("instrument_type"))
    required_instruments = set(requirement.required_instrument_classes)
    if not claim_instrument and not required_instruments:
        return True
    norm_instruments = _as_text_list(norm.get("instrument_types")) or _as_text_list(
        norm.get("policy_instrument") or norm.get("instrument_type")
    )
    if required_instruments:
        return bool(required_instruments.intersection(norm_instruments))
    return claim_instrument in norm_instruments


def _has_effective_window(norm: Mapping[str, Any]) -> bool:
    window = _legal_effective_window(norm)
    return bool(window.get("start") or _text(norm.get("effective_from")))


def _segment_within_norm_window(
    segment: Mapping[str, str | None],
    norm: Mapping[str, Any],
) -> bool:
    effective = _legal_effective_window(norm)
    effective_start = _parse_date(effective.get("start") or _text(norm.get("effective_from")))
    effective_end = _parse_date(effective.get("end") or _text(norm.get("effective_to")))
    segment_start = _parse_date(_text(segment.get("start")))
    segment_end = _parse_date(_text(segment.get("end")))
    if effective_start and segment_end and segment_end < effective_start:
        return False
    return not (effective_end and segment_start and segment_start > effective_end)


def _legal_effective_window(norm: Mapping[str, Any]) -> dict[str, str | None]:
    return _window_payload(
        norm.get("legal_effective_window")
        or {
            "start": norm.get("effective_from"),
            "end": norm.get("effective_to"),
        }
    )


def _window_payload(value: object) -> dict[str, str | None]:
    if isinstance(value, Mapping):
        return {
            "start": _text(value.get("start") or value.get("valid_from") or value.get("from")),
            "end": _text(value.get("end") or value.get("valid_to") or value.get("to")),
        }
    text = _text(value)
    if not text:
        return {"start": None, "end": None}
    if "/" in text:
        start, end = text.split("/", 1)
        return {"start": _text(start), "end": _text(end)}
    return {"start": text, "end": None}


def _issue(
    *,
    code: str,
    claim_id: str,
    norm_id: str | None,
    authority_type: str,
    message: str,
    next_action: str,
    severity: str = "fail",
    missing_facets: Sequence[str] = (),
) -> dict[str, Any]:
    payload = {
        "code": code,
        "severity": severity,
        "layer": "lex",
        "phase": "legal_authority",
        "claim_id": claim_id,
        "norm_id": norm_id,
        "authority_type": authority_type,
        "message": message,
        "next_action": next_action,
    }
    if missing_facets:
        payload["missing_facets"] = list(missing_facets)
    return payload


def _reader_effect(grade: str) -> str:
    return {
        "admissible": "claim_legal_authority_selected",
        "proxy_with_limitation": "claim_legal_authority_limited",
        "contested": "claim_legal_authority_review_required",
        "blocked": "claim_legal_authority_blocked",
        "out_of_scope": "candidate_context_only",
        "context_only": "candidate_context_only",
    }.get(grade, "candidate_context_only")


def _anchor_reason_code(grade: str) -> str:
    return {
        "admissible": "claim_level_legal_authority_selected",
        "proxy_with_limitation": "claim_level_legal_authority_limited",
        "contested": "claim_level_legal_authority_contested",
        "blocked": "claim_level_legal_authority_blocked",
        "out_of_scope": "legal_authority_out_of_scope",
        "context_only": "generic_legal_context_only",
    }.get(grade, "claim_level_legal_authority_unresolved")


def _primary_reason_code(issues: Sequence[Mapping[str, Any]], missing: Sequence[str]) -> str:
    for issue in issues:
        code = _text(issue.get("code"))
        if code == "legal_authority_type_not_carried_by_norm":
            return code
    for issue in issues:
        code = _text(issue.get("code"))
        if code:
            return code
    if missing:
        return "legal_authority_missing_claim_level_facets"
    return "legal_authority_unresolved"


def _claim_jurisdiction(
    claim: Mapping[str, Any],
    target_context: Mapping[str, Any],
) -> str:
    return _first_text(
        claim.get("jurisdiction"),
        claim.get("jurisdiction_norm"),
        target_context.get("jurisdiction"),
        target_context.get("jurisdiction_norm"),
    )


def _no_anchor_rationale(claim: Mapping[str, Any]) -> str | None:
    return _optional_text(
        claim.get("no_anchor_rationale")
        or claim.get("no_normative_anchor_rationale")
        or claim.get("normative_gap_rationale")
        or claim.get("no_legal_authority_rationale")
    )


def _is_llm_candidate(norm: Mapping[str, Any]) -> bool:
    provenance = _text(norm.get("provenance_kind") or norm.get("source_class")).casefold()
    return provenance in _LLM_PROVENANCE_KINDS or _text(norm.get("norm_id")).startswith(
        "llm-"
    ) or _text(norm.get("norm_id")).startswith("llm:")


def _norms_from_capability_bindings(
    capability_bindings: Sequence[Mapping[str, Any] | object],
) -> list[dict[str, Any]]:
    norms: list[dict[str, Any]] = []
    for raw in capability_bindings:
        binding = _payload(raw)
        if not _lex_capability(binding):
            continue
        metadata = _mapping(binding.get("metadata"))
        capability_ref = _text(
            binding.get("selected_capability_ref") or binding.get("capability_ref")
        )
        norm_ref = (
            _text(metadata.get("norm_ref"))
            or _first_text_from_assets(binding.get("source_assets"))
            or capability_ref
        )
        if not norm_ref:
            continue
        effective_window = _window_payload(
            metadata.get("legal_effective_window")
            or {
                "start": metadata.get("effective_from"),
                "end": metadata.get("effective_to"),
            }
        )
        norms.append(
            {
                "norm_id": norm_ref,
                "norm_version_ref": _text(metadata.get("norm_version_ref"))
                or f"{norm_ref}@capability",
                "source_provenance_ref": _text(metadata.get("source_provenance_ref"))
                or _first_ref(metadata.get("lex_normative_fact_refs"))
                or capability_ref,
                "jurisdiction": _text(metadata.get("jurisdiction"))
                or _text(binding.get("geography"))
                or "UA",
                "authority_types": _as_text_list(metadata.get("authority_types"))
                or ["implementing"],
                "competent_actor_ref": _text(metadata.get("competent_actor_ref")),
                "instrument_types": _as_text_list(metadata.get("instrument_types")),
                "implementation_authority_ref": _text(
                    metadata.get("implementation_authority_ref")
                ),
                "fiscal_authority_ref": _text(metadata.get("fiscal_authority_ref")),
                "hierarchy_position": _text(metadata.get("hierarchy_position"))
                or _text(metadata.get("authority_level")),
                "hierarchy_depth": metadata.get("hierarchy_depth"),
                "source_authority": _text(metadata.get("source_authority"))
                or _text(metadata.get("authority_basis")),
                "authority_basis": _text(metadata.get("authority_basis"))
                or _text(metadata.get("source_authority")),
                "effective_from": effective_window.get("start"),
                "effective_to": effective_window.get("end"),
                "legal_effective_window": effective_window,
                "legal_as_of": _text(metadata.get("legal_as_of")),
                "preemption_state": _text(metadata.get("preemption_state")) or "clear",
                "conflict_state": _text(metadata.get("conflict_state")) or "clear",
                "supersession_state": _text(metadata.get("supersession_state"))
                or "current",
                "rule_version_ref": _text(
                    binding.get("authority_composition_rule_ref")
                    or binding.get("rule_version_ref")
                )
                or LEGAL_AUTHORITY_RULE_VERSION,
                "provenance_kind": "deterministic_producer",
                "capability_ref": capability_ref,
                "construct_ref": _text(binding.get("construct_ref")),
                "capability_index_ref": _text(binding.get("capability_index_ref")),
                "construct_registry_ref": _text(binding.get("construct_registry_ref")),
                "authority_composition_rule_ref": _text(
                    binding.get("authority_composition_rule_ref")
                    or binding.get("rule_version_ref")
                ),
                "lex_normative_fact_refs": _as_text_list(
                    metadata.get("lex_normative_fact_refs")
                ),
                "lex_rule_threshold_refs": _as_text_list(
                    metadata.get("lex_rule_threshold_refs")
                ),
                "lex_amendment_refs": _as_text_list(metadata.get("lex_amendment_refs")),
                "lex_temporal_audit_refs": _as_text_list(
                    metadata.get("lex_temporal_audit_refs")
                ),
                "legal_hierarchy_constraints": _as_text_list(
                    metadata.get("legal_hierarchy_constraints")
                ),
            }
        )
    return norms


def _lex_capability(binding: Mapping[str, Any]) -> bool:
    modalities = {item.casefold() for item in _as_text_list(binding.get("modality"))}
    mode = _text(binding.get("evidence_mode")).casefold()
    metadata = _mapping(binding.get("metadata"))
    if "lex_norm" in modalities:
        return True
    if mode in {"normative_authority", "legal_threshold"}:
        return True
    return bool(
        metadata.get("lex_normative_fact_refs")
        or metadata.get("lex_rule_threshold_refs")
        or metadata.get("norm_ref")
    )


def _payload(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json", exclude_none=True)
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    return {}


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _first_ref(value: object) -> str:
    refs = _as_text_list(value)
    return refs[0] if refs else ""


def _first_text_from_assets(value: object) -> str:
    for asset in _mapping_list(value):
        ref = _text(asset.get("ref"))
        if ref:
            return ref
    return ""


def _record_ref(
    claim_id: str,
    authority_type: str,
    norm_id: str,
    start: str | None,
    end: str | None,
) -> str:
    raw = f"{claim_id}:{authority_type}:{norm_id or 'no_norm'}:{start or 'open'}:{end or 'open'}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"legal-authority-record:{claim_id}:{authority_type}:{digest}"


def _segment_ref(
    claim_id: str,
    authority_type: str,
    start: str | None,
    end: str | None,
) -> str:
    return (
        f"legal-authority-segment:{claim_id}:{authority_type}:"
        f"{start or 'open'}:{end or 'open'}"
    )


def _norm_id(norm: Mapping[str, Any]) -> str:
    return _text(norm.get("norm_id") or norm.get("id") or norm.get("artifact_id"))


def _claim_id(claim: Mapping[str, Any], index: int) -> str:
    return _text(claim.get("claim_id") or claim.get("id") or f"claim_{index + 1}")


def _stable_ref(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _authority_envelope() -> dict[str, tuple[str, ...] | str]:
    return {
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "authoritative_for": (
            "claim_level_legal_admissibility",
            "selected_norm_anchors",
            "rejected_norm_anchors",
            "jurisdiction_fallback_validation",
            "competence_window_splitting",
            "no_anchor_rationale",
        ),
        "may_not_use_for": (
            "recommendation_substance",
            "source_family_satisfaction",
            "method_validity",
            "participation_representativeness",
            "academic_support_strength",
            "closeout_pass",
        ),
    }


def _status_from_issues(issues: Sequence[Mapping[str, Any]]) -> str:
    if any(issue.get("severity") == "fail" for issue in issues):
        return "fail"
    if any(issue.get("severity") == "warn" for issue in issues):
        return "warn"
    return "pass"


def _legal_requirement_specs(
    *,
    legal_requirement_specs: Sequence[
        Mapping[str, Any] | LegalAuthorityRequirementSpec
    ]
    | None,
    target_context: Mapping[str, Any],
    claims: Sequence[Mapping[str, Any]],
    jurisdiction_fallback_config: Mapping[str, Any],
) -> tuple[LegalAuthorityRequirementSpec, ...]:
    if legal_requirement_specs is not None:
        return tuple(
            item
            if isinstance(item, LegalAuthorityRequirementSpec)
            else LegalAuthorityRequirementSpec.model_validate(dict(item))
            for item in legal_requirement_specs
            if isinstance(item, Mapping | LegalAuthorityRequirementSpec)
        )
    if not claims:
        return ()
    return compile_legal_authority_requirements(
        run_id=_text(target_context.get("run_id")) or "lex-legal-authority",
        target_context=target_context,
        claims=claims,
        jurisdiction_fallback_config=jurisdiction_fallback_config,
    )


def _claim_from_requirement(requirement: LegalAuthorityRequirementSpec) -> dict[str, Any]:
    return {
        "claim_id": requirement.claim_id,
        "claim_ref": requirement.claim_ref,
        "legal_authority_required": requirement.mandatory,
        "required_authority_types": [
            authority_type.value for authority_type in requirement.authority_types
        ],
        "jurisdiction": requirement.jurisdiction,
        "policy_instrument": (
            requirement.required_instrument_classes[0]
            if requirement.required_instrument_classes
            else None
        ),
        "implementation_period": {
            "start": requirement.temporal_competence_window.start,
            "end": requirement.temporal_competence_window.end,
        },
        "authority_profile_ref": requirement.authority_profile_ref,
    }


def _legal_grade(record: Mapping[str, Any]) -> str:
    grade = _text(record.get("legal_admissibility_grade"))
    if grade:
        return grade
    return _modern_grade(_text(record.get("admissibility_grade")))


def _modern_grade(legacy_grade: str) -> str:
    return {
        "selected_authority": "admissible",
        "limited_authority": "proxy_with_limitation",
        "contested_authority": "contested",
        "blocked_no_authority": "blocked",
        "candidate_norm": "context_only",
        "context_only": "context_only",
    }.get(legacy_grade, legacy_grade)


def _legacy_grade(legal_admissibility_grade: str) -> str:
    return {
        "admissible": "selected_authority",
        "proxy_with_limitation": "limited_authority",
        "contested": "contested_authority",
        "blocked": "blocked_no_authority",
        "out_of_scope": "context_only",
        "context_only": "context_only",
    }.get(legal_admissibility_grade, "context_only")


def _legacy_anchor_grade(*, legal_admissibility_grade: str, required: bool) -> str:
    if legal_admissibility_grade == "context_only" and required:
        return "blocked_no_authority"
    return _legacy_grade(legal_admissibility_grade)


def _authority_type_value(value: object) -> str:
    try:
        return normalize_legal_authority_type(value).value
    except (TypeError, ValueError):
        return ""


def _missing_grade(
    *,
    missing: Sequence[str],
    fallback_blocked: bool,
    norm_authority_types: set[str],
) -> str:
    if not norm_authority_types:
        return "context_only"
    context_only_facets = {
        "competent_actor_ref",
        "instrument_types",
        "legal_effective_window",
        "source_authority",
        "hierarchy_depth",
    }
    if set(missing) and set(missing).issubset(context_only_facets):
        return "context_only"
    if fallback_blocked and not norm_authority_types:
        return "context_only"
    return "blocked"


def _norm_hierarchy_depth(norm: Mapping[str, Any]) -> int:
    explicit = norm.get("hierarchy_depth")
    try:
        if explicit is not None and explicit != "":
            return int(explicit)
    except (TypeError, ValueError):
        pass
    hierarchy = _text(norm.get("hierarchy_position") or norm.get("authority_level")).casefold()
    if hierarchy in {"local", "municipal", "regional", "oblast"}:
        return 2
    if hierarchy in {"national", "statute", "constitutional", "constitution"}:
        return 1
    return 0 if not hierarchy else 1


def _windows_overlap(
    left: Mapping[str, str | None],
    right: Mapping[str, str | None],
) -> bool:
    left_start = _parse_date(_text(left.get("start")))
    left_end = _parse_date(_text(left.get("end")))
    right_start = _parse_date(_text(right.get("start")))
    right_end = _parse_date(_text(right.get("end")))
    if left_start and right_end and left_start > right_end:
        return False
    return not (right_start and left_end and right_start > left_end)


def _mapping_list(value: object) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _as_text_list(value: object) -> list[str]:
    if isinstance(value, str):
        text = _text(value)
        return [text] if text else []
    if isinstance(value, Mapping):
        refs: list[str] = []
        for key in ("ref", "id", "value", "norm_id", "policy_ref"):
            refs.extend(_as_text_list(value.get(key)))
        return _dedupe(refs)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        refs: list[str] = []
        for item in value:
            refs.extend(_as_text_list(item))
        return _dedupe(refs)
    return []


def _dedupe(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        result.append(text)
        seen.add(text)
    return result


def _first_text(*values: object) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _optional_text(value: object) -> str | None:
    text = _text(value)
    return text or None


def _text(value: object) -> str:
    return str(value or "").strip()


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "required"}
    return bool(value)


def _parse_date(value: str | None) -> date | None:
    return parse_iso_date(value) if value else None


def _max_date_text(left: str | None, right: str | None) -> str | None:
    left_date = _parse_date(left)
    right_date = _parse_date(right)
    if left_date and right_date:
        return max(left_date, right_date).isoformat()
    return left or right


def _min_date_text(left: str | None, right: str | None) -> str | None:
    left_date = _parse_date(left)
    right_date = _parse_date(right)
    if left_date and right_date:
        return min(left_date, right_date).isoformat()
    return left or right


__all__ = [
    "LEGACY_LEGAL_ADMISSIBILITY_GRADES",
    "LEGAL_ADMISSIBILITY_GRADES",
    "LEGAL_AUTHORITY_RECORD_SCHEMA_VERSION",
    "LEGAL_AUTHORITY_REPORT_SCHEMA_VERSION",
    "LEGAL_AUTHORITY_RULE_VERSION",
    "LEGAL_AUTHORITY_TYPES",
    "LEGAL_WINDOW_SPLIT_SCHEMA_VERSION",
    "build_legal_authority_report",
]
