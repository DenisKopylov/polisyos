"""Public policy verified service module API."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from polisyos.common.serialization import extract_llm_json_object
from polisyos.core.artifacts import ArtifactStore, profile_bound_ref
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.scholar import ResearchIntent, ResearchIntentRef
from polisyos.core.contracts.trinity import TrinityBundleRef
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    EvidenceSourceKind,
    EvidenceSourceState,
    EvidenceSourceStatus,
)
from polisyos.lex.knowledge.search import LegalKnowledgeGraph
from polisyos.lex.knowledge.types import LegalFactResult, LegalSourceBundle
from polisyos.scientist.agent.knowledge_tools import KnowledgeToolkit
from polisyos.scientist.agent.prompts import get_source_verifier_prompt
from polisyos.scientist.evidence.claims.models import (
    ClaimPublishability,
    ClaimRecord,
    ClaimSourceClass,
    ClaimSupportStatus,
    ClaimType,
    ClaimUse,
)
from polisyos.scientist.evidence.decision_readiness import DecisionReadiness
from polisyos.scientist.evidence.sources import (
    build_path_source_status,
    normalize_evidence_sources_config,
    update_source_status,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_METRICS_REF,
    INPUT_RESEARCH_INTENT_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.llm.factory import create_traced_gateway_client
from polisyos.scientist.policy_design.option_program_contracts import (
    OPTION_PROGRAM_CORRESPONDENCE_NOT_ESTABLISHED,
)
from polisyos.scientist.validation.policy_verified.models import (
    LegalCandidatePack,
    LegalRetrievalStatus,
    LegalSourcePack,
    PolicyEvidenceLink,
    PolicyOption,
    PolicyOptionSet,
    PolicyRequestFrame,
    SourceCoverageGap,
    SourceVerificationReport,
    VerifiedLegalClaim,
    VerifiedPolicyReport,
)

_POLICY_VERIFIED_MODEL_ERRORS = (TypeError, ValueError, ValidationError)
_POLICY_VERIFIED_ARTIFACT_LOAD_ERRORS = (
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    ValidationError,
)
_POLICY_VERIFIED_TOOLKIT_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_POLICY_VERIFIED_JSON_ERRORS = (TypeError, ValueError, json.JSONDecodeError)
_POLICY_VERIFIED_ASYNC_RUN_ERRORS = (RuntimeError, TypeError, ValueError)
POLICY_VERIFIED_HARDCODED_FORMALIZER_STRANGLED = "policy_verified_hardcoded_formalizer_strangled"
_POLICY_SCOPE_FAILURES = (
    "policy_request_intent_profile_not_established",
    "policy_request_question_invalid",
    "policy_request_question_not_established",
    "policy_request_jurisdiction_invalid",
    "policy_request_jurisdiction_conflict",
    "policy_request_jurisdiction_not_established",
    "policy_request_jurisdiction_provenance_not_established",
)


def build_policy_request_frame(ctx: ExecutionContext, state: ExperimentState) -> PolicyRequestFrame:
    """Build a request from declared inputs without inventing target scope."""
    intent_ref = state.inputs.get(INPUT_RESEARCH_INTENT_REF)
    intent = None
    params = state.params
    notes = _string_list(params.get("notes"))
    if intent_ref is not None:
        try:
            if (
                intent_ref.kind != "scholar.research_intent"
                or intent_ref.media_type != "application/json"
                or intent_ref.manifest_profile_sha256 is None
                or profile_bound_ref(ctx.store, intent_ref) != intent_ref
            ):
                raise ValueError("policy_request_intent_profile_not_established")
            intent = _load_research_intent(ctx.store, intent_ref)
            if intent is None:
                raise ValueError("policy_request_intent_profile_not_established")
        except _POLICY_VERIFIED_ARTIFACT_LOAD_ERRORS:
            notes.append("policy_request_intent_profile_not_established")

    raw_question = ""
    for key in ("policy_question", "policy_request", "problem_statement", "research_question"):
        value = params.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            notes.append("policy_request_question_invalid")
            break
        if value.strip():
            raw_question = value.strip()
            break
    if not raw_question and "policy_request_question_invalid" not in notes:
        if intent is not None and intent.topic and intent.topic.strip():
            raw_question = intent.topic.strip()
            notes.append("policy_request_question_from_research_topic")
        else:
            notes.append("policy_request_question_not_established")

    target = params.get("policy_request_jurisdiction")
    generic = params.get("jurisdiction")
    jurisdiction = ""
    jurisdiction_source: Literal["policy_request_jurisdiction", "jurisdiction"] | None = None
    if any(value is not None and not isinstance(value, str) for value in (target, generic)):
        notes.append("policy_request_jurisdiction_invalid")
    else:
        target_text = target.strip() if isinstance(target, str) else ""
        generic_text = generic.strip() if isinstance(generic, str) else ""
        if target_text and generic_text and target_text != generic_text:
            notes.append("policy_request_jurisdiction_conflict")
        elif target_text:
            jurisdiction, jurisdiction_source = target_text, "policy_request_jurisdiction"
        elif generic_text:
            jurisdiction, jurisdiction_source = generic_text, "jurisdiction"
            notes.append("policy_request_jurisdiction_from_generic_field")
        else:
            notes.append("policy_request_jurisdiction_not_established")
    as_of = (
        str(params.get("policy_request_as_of") or "").strip()
        or str(params.get("as_of") or "").strip()
        or None
    )
    domain = (
        str(params.get("policy_request_domain") or "").strip()
        or str(params.get("domain") or "").strip()
        or str(getattr(intent, "domain", "") or "").strip()
        or None
    )
    goals = _string_list(params.get("goals")) or _string_list(params.get("policy_goals"))
    constraints = _string_list(params.get("constraints")) or _string_list(
        params.get("policy_constraints")
    )
    evaluation_criteria = _string_list(params.get("evaluation_criteria")) or _string_list(
        params.get("success_criteria")
    )
    if intent is not None:
        notes.extend(list(getattr(intent, "notes", []) or []))
    request_id = _stable_id("policy_request", raw_question, jurisdiction, as_of or "", domain or "")
    return PolicyRequestFrame(
        schema_version="1.1",
        request_id=request_id,
        policy_question=raw_question,
        jurisdiction=jurisdiction,
        jurisdiction_source=jurisdiction_source,
        as_of=as_of,
        policy_domain=domain,
        target_context=dict(params.get("target_context") or {})
        if isinstance(params.get("target_context"), dict)
        else {},
        evaluation_criteria=evaluation_criteria,
        goals=goals,
        constraints=constraints,
        notes=notes,
    )


def policy_request_scope_reason(frame: PolicyRequestFrame) -> str | None:
    """Return a declared request-scope limitation, without granting authority."""
    for reason in _POLICY_SCOPE_FAILURES:
        if reason in frame.notes:
            return reason
    if not frame.policy_question.strip():
        return "policy_request_question_not_established"
    if not frame.jurisdiction.strip():
        return "policy_request_jurisdiction_not_established"
    if frame.schema_version != "1.1" or frame.jurisdiction_source is None:
        return "policy_request_jurisdiction_provenance_not_established"
    return None


def _scope_reason_from_notes(notes: list[str]) -> str | None:
    return next((reason for reason in _POLICY_SCOPE_FAILURES if reason in notes), None)


def _scope_blocked_report(
    report: SourceVerificationReport, reason: str
) -> SourceVerificationReport:
    gap = SourceCoverageGap(
        gap_id=_stable_id("gap", report.request_id, reason),
        category=reason,
        description="The policy question or target jurisdiction is not established for legal sourcing.",
        severity="critical",
    )
    return report.model_copy(
        update={
            "unresolved_critical_gaps": _merge_gaps(report.unresolved_critical_gaps, [gap]),
            "needs_expert_review": True,
            "notes": list(dict.fromkeys([*report.notes, reason])),
        }
    )


def assemble_legal_candidate_pack(
    ctx: ExecutionContext,
    state: ExperimentState,
    frame: PolicyRequestFrame,
) -> LegalCandidatePack:
    """Build candidate legal recall hits for a policy request frame."""
    reason = policy_request_scope_reason(frame)
    if reason is not None:
        return LegalCandidatePack(
            request_id=frame.request_id,
            queries=[frame.policy_question] if frame.policy_question else [],
            notes=[reason],
        )
    toolkit = _build_legal_toolkit(ctx, state)
    legal_status = _resolve_legal_source_status(ctx, state, toolkit=toolkit)
    if toolkit is None:
        return LegalCandidatePack(
            request_id=frame.request_id,
            queries=[frame.policy_question],
            source_statuses={"legal": legal_status},
            legal_retrieval_status=[
                LegalRetrievalStatus(
                    query=frame.policy_question,
                    route="hybrid_facts",
                    limitation_code=f"legal_graph_unavailable:{legal_status.status.value}",
                )
            ],
            notes=[f"legal_graph_unavailable:{legal_status.status.value}"],
        )
    queries = _plan_recall_queries(frame, state)
    max_queries = _int_param(state, "max_candidate_queries", 40)
    merged = LegalCandidatePack(request_id=frame.request_id, queries=queries[:max_queries])
    fact_map: dict[str, LegalFactResult] = {}
    provision_map: dict[str, Any] = {}
    for query in queries[:max_queries]:
        pack = toolkit.assemble_legal_candidate_pack(
            query,
            jurisdiction=frame.jurisdiction,
            domain=frame.policy_domain,
            as_of=frame.as_of,
        )
        merged.legal_retrieval_status.extend(pack.legal_retrieval_status)
        for fact in pack.fact_hits:
            fact_map[fact.fact_id] = fact
            merged.hit_reasons.setdefault(fact.fact_id, "legal_recall")
            merged.source_family_hints.setdefault(
                fact.fact_id,
                fact.legal_unit_subtype or fact.top_domain or "",
            )
            if fact.provision_anchor or fact.provision_citation:
                merged.anchor_coverage_hints.setdefault(
                    fact.fact_id,
                    [fact.provision_anchor or fact.provision_citation],
                )
        for provision in pack.provision_hits:
            provision_map[provision.provision_id] = provision
            merged.hit_reasons.setdefault(provision.provision_id, "provision_recall")
            if provision.anchor_path:
                merged.anchor_coverage_hints.setdefault(
                    provision.provision_id, [provision.anchor_path]
                )
    merged.fact_hits = list(fact_map.values())
    merged.provision_hits = list(provision_map.values())
    merged.source_statuses["legal"] = legal_status
    return merged


def expand_legal_source_pack(
    ctx: ExecutionContext,
    state: ExperimentState,
    candidate_pack: LegalCandidatePack,
) -> LegalSourcePack:
    """Resolve candidate hits into legal source bundles and anchor coverage."""
    reason = _scope_reason_from_notes(candidate_pack.notes)
    if reason is not None:
        return LegalSourcePack(
            request_id=candidate_pack.request_id,
            source_statuses=dict(candidate_pack.source_statuses),
            notes=[reason],
        )
    toolkit = _build_legal_toolkit(ctx, state)
    legal_status = _resolve_legal_source_status(ctx, state, toolkit=toolkit)
    if toolkit is None:
        return LegalSourcePack(
            request_id=candidate_pack.request_id,
            unresolved_anchor_hints=["legal_graph_unavailable"],
            source_statuses={"legal": legal_status},
            notes=[f"legal_graph_unavailable:{legal_status.status.value}"],
        )
    pack = toolkit.expand_legal_source_pack(
        candidate_pack,
        max_source_docs=_int_param(state, "max_source_docs", 120),
        max_reference_hops=_int_param(state, "max_reference_hops", 2),
    )
    if not pack.source_bundles:
        pack.unresolved_anchor_hints.extend(
            hint
            for values in candidate_pack.anchor_coverage_hints.values()
            for hint in values
            if hint
        )
    return pack.model_copy(
        update={
            "source_statuses": {
                **dict(candidate_pack.source_statuses),
                "legal": legal_status,
            }
        }
    )


def _candidate_only_source_report(
    state: ExperimentState,
    source_pack: LegalSourcePack,
    report: SourceVerificationReport,
) -> SourceVerificationReport:
    """Reissue historical legal labels as unverified candidate evidence."""
    legacy_candidates = [
        _legal_claim_candidate(
            state=state,
            claim_id=_stable_id(
                "claim_candidate", "legacy_unbound", claim.claim_id, str(index), claim.claim_text
            ),
            text=claim.claim_text or "Unspecified historical legal claim",
            source="legacy_unbound",
            details=claim.model_dump(mode="json"),
        )
        for index, claim in enumerate(report.verified_claims)
    ]
    verification_gap = SourceCoverageGap(
        gap_id=_stable_id("gap", report.request_id, "legal_claim_verification_not_established"),
        category="legal_claim_verification_not_established",
        description="Independent legal claim verification and current source authority are not established.",
        severity="critical",
        related_bundle_ids=[bundle.bundle_id for bundle in source_pack.source_bundles],
    )
    return report.model_copy(
        update={
            "schema_version": "1.1",
            "verified_claims": [],
            "legal_claim_candidates": _merge_candidate_claims(
                report.legal_claim_candidates, legacy_candidates
            ),
            "legal_verification_status": "not_established",
            "verified_claim_citation_coverage_pct": 0.0,
            "unresolved_critical_gaps": _merge_gaps(
                report.unresolved_critical_gaps, [verification_gap]
            ),
            "needs_expert_review": True,
            "notes": list(
                dict.fromkeys([*report.notes, "legal_claim_verification_not_established"])
            ),
        }
    )


def verify_source_pack(
    ctx: ExecutionContext,
    state: ExperimentState,
    frame: PolicyRequestFrame,
    candidate_pack: LegalCandidatePack,
    source_pack: LegalSourcePack,
) -> SourceVerificationReport:
    """Retain legal-source proposals without asserting unestablished verification."""
    reason = (
        policy_request_scope_reason(frame)
        or _scope_reason_from_notes(candidate_pack.notes)
        or _scope_reason_from_notes(source_pack.notes)
    )
    if reason is not None:
        return _scope_blocked_report(
            _candidate_only_source_report(
                state,
                source_pack,
                SourceVerificationReport(
                    schema_version="1.1",
                    request_id=frame.request_id,
                    source_statuses={
                        **candidate_pack.source_statuses,
                        **source_pack.source_statuses,
                    },
                ),
            ),
            reason,
        )
    baseline_claims = _baseline_claim_candidates(state, candidate_pack, source_pack)
    report = _candidate_only_source_report(
        state,
        source_pack,
        SourceVerificationReport(
            schema_version="1.1",
            request_id=frame.request_id,
            legal_claim_candidates=baseline_claims,
            unresolved_critical_gaps=_initial_gaps(source_pack, []),
            verification_cycles_completed=max(
                1, _int_param(state, "verification_cycles_completed", 0) + 1
            ),
            source_statuses={
                **dict(candidate_pack.source_statuses),
                **dict(source_pack.source_statuses),
            },
        ),
    )
    llm_claims, llm_gaps, verifier_calls, adjudicator_calls, disagreement_rate = (
        _maybe_verify_with_llm(
            state=state,
            frame=frame,
            source_pack=source_pack,
            baseline_claims=baseline_claims,
        )
    )
    if llm_claims or llm_gaps or verifier_calls:
        merged = _merge_candidate_claims(report.legal_claim_candidates, llm_claims)
        report = report.model_copy(
            update={
                "legal_claim_candidates": merged,
                "unresolved_critical_gaps": _merge_gaps(report.unresolved_critical_gaps, llm_gaps),
                "verifier_calls_total": verifier_calls,
                "adjudicator_calls_total": adjudicator_calls,
                "verifier_disagreement_rate": disagreement_rate,
                "needs_expert_review": True,
                "notes": [*report.notes, "llm_legal_claim_candidates"],
            }
        )
    return report


def review_source_gaps(
    state: ExperimentState,
    frame: PolicyRequestFrame,
    source_pack: LegalSourcePack,
    report: SourceVerificationReport,
) -> SourceVerificationReport:
    """Augment source verification with bundle-level coverage gap review."""
    report = _candidate_only_source_report(state, source_pack, report)
    reason = policy_request_scope_reason(frame) or _scope_reason_from_notes(source_pack.notes)
    if reason is not None:
        return _scope_blocked_report(report, reason)
    gaps = list(report.unresolved_critical_gaps)
    extra_gaps = []
    for bundle in source_pack.source_bundles:
        extra_gaps.append(
            SourceCoverageGap(
                gap_id=_stable_id("gap", bundle.bundle_id, "bundle_without_claims"),
                category="bundle_without_claims",
                description=f"No verified claim extracted for {bundle.doc_name or bundle.doc_id}.",
                severity="critical"
                if bundle.source_family in {"approval_bundle", "amendment_bundle"}
                else "warning",
                related_bundle_ids=[bundle.bundle_id],
                suggested_queries=[
                    frame.policy_question,
                    f"{bundle.doc_name} {bundle.doc_reestr_code}".strip(),
                ],
            )
        )
    merged = _merge_gaps(gaps, extra_gaps)
    needs_expert_review = report.needs_expert_review or any(
        g.severity == "critical" for g in merged
    )
    return report.model_copy(
        update={
            "unresolved_critical_gaps": merged,
            "needs_expert_review": needs_expert_review,
            "notes": [*report.notes, "gap_review_completed"],
        }
    )


def recover_source_gaps(
    ctx: ExecutionContext,
    state: ExperimentState,
    frame: PolicyRequestFrame,
    candidate_pack: LegalCandidatePack,
    source_pack: LegalSourcePack,
    report: SourceVerificationReport,
) -> tuple[LegalCandidatePack, LegalSourcePack, SourceVerificationReport]:
    """Run one bounded recovery cycle for unresolved legal source gaps."""
    report = _candidate_only_source_report(state, source_pack, report)
    reason = (
        policy_request_scope_reason(frame)
        or _scope_reason_from_notes(candidate_pack.notes)
        or _scope_reason_from_notes(source_pack.notes)
    )
    if reason is not None:
        return candidate_pack, source_pack, _scope_blocked_report(report, reason)
    reviewed_report = review_source_gaps(state, frame, source_pack, report)
    if not reviewed_report.unresolved_critical_gaps:
        return candidate_pack, source_pack, reviewed_report

    completed_cycles = max(0, int(reviewed_report.verification_cycles_completed))
    if completed_cycles >= 2:
        exhausted = reviewed_report.model_copy(
            update={
                "notes": [*reviewed_report.notes, "recovery_budget_exhausted"],
                "needs_expert_review": reviewed_report.needs_expert_review
                or bool(reviewed_report.unresolved_critical_gaps),
            }
        )
        return candidate_pack, source_pack, exhausted

    toolkit = _build_legal_toolkit(ctx, state)
    if toolkit is None:
        unavailable = reviewed_report.model_copy(
            update={
                "notes": [*reviewed_report.notes, "recovery_skipped_legal_graph_unavailable"],
            }
        )
        return candidate_pack, source_pack, unavailable

    retry_queries = _plan_gap_recovery_queries(frame, source_pack, reviewed_report)
    retry_limit = _int_param(state, "max_gap_review_calls", 80)
    retry_queries = retry_queries[:retry_limit]
    if not retry_queries:
        no_queries = reviewed_report.model_copy(
            update={"notes": [*reviewed_report.notes, "recovery_skipped_no_queries"]}
        )
        return candidate_pack, source_pack, no_queries

    retry_candidate_pack = LegalCandidatePack(
        request_id=candidate_pack.request_id, queries=retry_queries
    )
    fact_map = {fact.fact_id: fact for fact in candidate_pack.fact_hits}
    provision_map = {
        provision.provision_id: provision for provision in candidate_pack.provision_hits
    }
    hit_reasons = dict(candidate_pack.hit_reasons)
    source_family_hints = dict(candidate_pack.source_family_hints)
    anchor_coverage_hints = {
        key: list(values) for key, values in candidate_pack.anchor_coverage_hints.items()
    }
    retry_retrieval_status = []
    for query in retry_queries:
        pack = toolkit.assemble_legal_candidate_pack(
            query,
            jurisdiction=frame.jurisdiction,
            domain=frame.policy_domain,
            as_of=frame.as_of,
        )
        retry_candidate_pack.queries.extend(pack.queries)
        retry_retrieval_status.extend(pack.legal_retrieval_status)
        for fact in pack.fact_hits:
            fact_map[fact.fact_id] = fact
            hit_reasons[fact.fact_id] = "gap_recovery"
            source_family_hints[fact.fact_id] = fact.legal_unit_subtype or fact.top_domain or ""
            if fact.provision_anchor or fact.provision_citation:
                values = anchor_coverage_hints.setdefault(fact.fact_id, [])
                candidate_anchor = fact.provision_anchor or fact.provision_citation
                if candidate_anchor and candidate_anchor not in values:
                    values.append(candidate_anchor)
        for provision in pack.provision_hits:
            provision_map[provision.provision_id] = provision
            hit_reasons[provision.provision_id] = "gap_recovery"
            if provision.anchor_path:
                values = anchor_coverage_hints.setdefault(provision.provision_id, [])
                if provision.anchor_path not in values:
                    values.append(provision.anchor_path)
    merged_candidate_pack = candidate_pack.model_copy(
        update={
            "queries": _dedupe_texts([*candidate_pack.queries, *retry_queries]),
            "fact_hits": list(fact_map.values()),
            "provision_hits": list(provision_map.values()),
            "hit_reasons": hit_reasons,
            "source_family_hints": source_family_hints,
            "anchor_coverage_hints": anchor_coverage_hints,
            "legal_retrieval_status": [
                *candidate_pack.legal_retrieval_status,
                *retry_retrieval_status,
            ],
            "notes": [*candidate_pack.notes, "gap_recovery_queries"],
        }
    )

    expanded_retry_pack = toolkit.expand_legal_source_pack(
        merged_candidate_pack,
        max_source_docs=_int_param(state, "max_source_docs", 120),
        max_reference_hops=_int_param(state, "max_reference_hops", 2),
    )
    merged_source_pack = _merge_source_packs(source_pack, expanded_retry_pack)
    retry_state = state.model_copy(
        deep=True,
        update={
            "params": {
                **state.params,
                "verification_cycles_completed": reviewed_report.verification_cycles_completed,
            }
        },
    )
    retry_report = verify_source_pack(
        ctx,
        retry_state,
        frame,
        merged_candidate_pack,
        merged_source_pack,
    )
    merged_candidates = _merge_candidate_claims(
        reviewed_report.legal_claim_candidates, retry_report.legal_claim_candidates
    )
    recomputed_gaps = _initial_gaps(merged_source_pack, [])
    merged_gaps = _merge_gaps(recomputed_gaps, retry_report.unresolved_critical_gaps)
    final_report = retry_report.model_copy(
        update={
            "legal_claim_candidates": merged_candidates,
            "verified_claims": [],
            "unresolved_critical_gaps": merged_gaps,
            "verification_cycles_completed": max(
                reviewed_report.verification_cycles_completed,
                retry_report.verification_cycles_completed,
            ),
            "verifier_calls_total": reviewed_report.verifier_calls_total
            + retry_report.verifier_calls_total,
            "adjudicator_calls_total": reviewed_report.adjudicator_calls_total
            + retry_report.adjudicator_calls_total,
            "verifier_disagreement_rate": max(
                reviewed_report.verifier_disagreement_rate,
                retry_report.verifier_disagreement_rate,
            ),
            "verified_claim_citation_coverage_pct": 0.0,
            "needs_expert_review": True,
            "notes": list(
                dict.fromkeys(
                    [*reviewed_report.notes, *retry_report.notes, "gap_recovery_cycle_completed"]
                )
            ),
        }
    )
    return merged_candidate_pack, merged_source_pack, final_report


def draft_policy_option_set(
    state: ExperimentState,
    frame: PolicyRequestFrame,
    report: SourceVerificationReport,
) -> PolicyOptionSet:
    """Create policy candidates without promoting unadmitted legal interpretations."""
    # No supported independent legal-verification owner is connected here.
    # A caller-supplied status, including one injected with model_copy, cannot
    # create that authority.
    verified_claims: list[VerifiedLegalClaim] = []
    citations = sorted({claim.citation_label for claim in verified_claims if claim.citation_label})
    constraints = [
        claim.claim_text
        for claim in verified_claims
        if claim.claim_type in {"obligation", "prohibition", "exception", "conflict"}
    ][:8]
    thresholds = [claim.claim_text for claim in verified_claims if claim.claim_type == "threshold"][
        :6
    ]
    timing = [
        claim.claim_text
        for claim in verified_claims
        if claim.claim_type in {"temporal", "enters_into_force"}
    ][:6]
    verified_option = PolicyOption(
        option_id="verified_option_1",
        title="Verified policy option",
        summary=frame.policy_question,
        intervention_outline={
            "policy_question": frame.policy_question,
            "domain": frame.policy_domain or "custom",
        },
        legal_basis_refs=citations,
        evidence_links=[
            PolicyEvidenceLink(option_id="verified_option_1", claim_id=claim.claim_id)
            for claim in verified_claims[:20]
        ],
        constraints=constraints,
        thresholds=thresholds,
        timing=timing,
        notes=["verified_only_option"],
    )
    hypothesis_options: list[PolicyOption] = []
    if bool(state.params.get("allow_hypotheses", True)) and (
        report.unresolved_critical_gaps or report.legal_claim_candidates or not verified_claims
    ):
        hypothesis_options.append(
            PolicyOption(
                option_id="hypothesis_option_1",
                title="Hypothesis-driven revision option",
                summary="Exploratory option that requires additional legal verification before adoption.",
                intervention_outline={
                    "policy_question": frame.policy_question,
                    "mode": "hypothesis",
                },
                hypothesis_basis=True,
                notes=[gap.description for gap in report.unresolved_critical_gaps[:5]],
            )
        )
    return PolicyOptionSet(
        request_id=frame.request_id,
        verified_options=[verified_option] if verified_claims else [],
        hypothesis_options=hypothesis_options,
    )


def formalize_policy_option_set(
    ctx: ExecutionContext,
    state: ExperimentState,
    frame: PolicyRequestFrame,
    option_set: PolicyOptionSet,
) -> TrinityBundleRef | None:
    """Resolve a caller-supplied Trinity bundle without synthesizing policy authority."""

    del ctx, frame, option_set
    existing_ref = state.inputs.get(INPUT_TRINITY_BUNDLE_REF)
    if existing_ref is None:
        return None
    return TrinityBundleRef.model_validate(existing_ref.model_dump())


def build_verified_policy_report(
    state: ExperimentState,
    frame: PolicyRequestFrame,
    report: SourceVerificationReport,
    option_set: PolicyOptionSet,
) -> VerifiedPolicyReport:
    """Build candidate report content without promoting unadmitted legal claims."""
    # Historical labels and mutable caller copies do not establish verification.
    verified_claims: list[VerifiedLegalClaim] = []
    verified_options = option_set.verified_options if verified_claims else []
    candidate_options = list(option_set.hypothesis_options)
    if not verified_claims:
        candidate_options = [
            option.model_copy(
                update={
                    "hypothesis_basis": True,
                    "notes": list(
                        dict.fromkeys([*option.notes, "legal_claim_verification_not_established"])
                    ),
                }
            )
            for option in option_set.verified_options
        ] + candidate_options
    constraints_and_timing = []
    for option in verified_options:
        constraints_and_timing.extend(option.constraints)
        constraints_and_timing.extend(option.thresholds)
        constraints_and_timing.extend(option.timing)
    verified_findings = [_format_verified_finding(claim) for claim in verified_claims[:30]]
    intervention_legal_basis_map = {
        option.option_id: list(option.legal_basis_refs) for option in verified_options
    }
    simulation_notes: list[str] = []
    if ARTIFACT_METRICS_REF in state.artifacts_index:
        simulation_notes.append("Simulation artifacts are available for this policy package.")
    if ARTIFACT_CAUSAL_REPORT_REF in state.artifacts_index:
        simulation_notes.append(
            "Causal evaluation artifacts are available for this policy package."
        )
    missing_evidence = [gap.description for gap in report.unresolved_critical_gaps]
    missing_evidence.append("Independent legal claim verification is not established.")
    missing_evidence.append("The selected policy option has not been matched to the final program.")
    for source_name, source_status in sorted(report.source_statuses.items()):
        if source_status.status is EvidenceSourceState.AVAILABLE:
            continue
        missing_evidence.append(
            f"Evidence source '{source_name}' is unavailable ({source_status.status.value})."
        )
    citation_appendix = sorted(
        {
            f"{claim.citation_label} [{claim.doc_id}:{claim.anchor}]"
            for claim in verified_claims
            if claim.citation_label or claim.anchor
        }
    )
    executive_summary = (
        f"Legal claim verification is not established for '{frame.policy_question}'. "
        f"{len(candidate_options)} candidate option(s) were retained."
    )
    return VerifiedPolicyReport(
        request_id=frame.request_id,
        executive_summary=executive_summary,
        verified_legal_basis=verified_claims,
        policy_options=[*verified_options, *candidate_options],
        constraints_and_timing=constraints_and_timing[:20],
        simulation_and_causal_implications=simulation_notes,
        verified_findings=verified_findings,
        hypotheses=[option.summary for option in candidate_options],
        missing_evidence=missing_evidence,
        unresolved_critical_gaps=report.unresolved_critical_gaps,
        citation_appendix=citation_appendix,
        intervention_legal_basis_map=intervention_legal_basis_map,
        needs_expert_review=True,
        source_statuses=dict(report.source_statuses),
        notes=[
            OPTION_PROGRAM_CORRESPONDENCE_NOT_ESTABLISHED,
            "legal_claim_verification_not_established",
            *(
                f"evidence_source_unavailable:{name}:{status.status.value}"
                for name, status in sorted(report.source_statuses.items())
                if status.status is not EvidenceSourceState.AVAILABLE
            ),
        ],
    )


def _load_research_intent(store: ArtifactStore, raw_ref: Any) -> ResearchIntent | None:
    from polisyos.core.artifacts import load_core_json_artifact

    if raw_ref is None:
        return None
    try:
        ref = ResearchIntentRef.model_validate(
            raw_ref.model_dump() if hasattr(raw_ref, "model_dump") else raw_ref
        )
    except _POLICY_VERIFIED_MODEL_ERRORS:
        return None
    try:
        payload = load_core_json_artifact(store, ref)
    except _POLICY_VERIFIED_ARTIFACT_LOAD_ERRORS:
        return None
    try:
        return ResearchIntent.model_validate(payload)
    except _POLICY_VERIFIED_MODEL_ERRORS:
        return None


def _build_legal_toolkit(ctx: ExecutionContext, state: ExperimentState) -> KnowledgeToolkit | None:
    profile = _load_cross_graph_profile(ctx.store, state)
    evidence_sources = _resolve_evidence_sources(state, profile)
    legal_db_path = str(evidence_sources.legal_db_path or "").strip()
    if not legal_db_path:
        return None
    db_path = Path(legal_db_path)
    if not db_path.exists():
        return None
    try:
        legal_graph = LegalKnowledgeGraph(
            db_path=db_path,
            index_dir=db_path.parent,
            openai_api_key=os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY_1"),
        )
    except _POLICY_VERIFIED_TOOLKIT_ERRORS:
        return None
    return KnowledgeToolkit(legal_graph=legal_graph)


def _resolve_evidence_sources(
    state: ExperimentState,
    profile: CrossGraphEvidenceProfile | None,
):
    params = dict(state.params)
    if profile is not None:
        for field, value in profile.source_refs.model_dump(mode="json").items():
            if value is not None and not params.get(field):
                params[field] = value
    return normalize_evidence_sources_config(params)


def _resolve_legal_source_status(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    toolkit: KnowledgeToolkit | None,
) -> EvidenceSourceStatus:
    profile = _load_cross_graph_profile(ctx.store, state)
    profile_status = None
    if profile is not None:
        profile_status = profile.source_statuses.get(EvidenceSourceKind.LEGAL.value)
    if profile_status is not None and toolkit is not None:
        return update_source_status(
            profile_status,
            state=EvidenceSourceState.AVAILABLE,
            detail=profile_status.detail or "policy_verified_legal_toolkit_ready",
        )
    if profile_status is not None and toolkit is None:
        if profile_status.status in {
            EvidenceSourceState.MISSING_CONFIG,
            EvidenceSourceState.MISSING_PATH,
            EvidenceSourceState.DISABLED,
            EvidenceSourceState.QUERY_FAILED,
        }:
            return profile_status
        return update_source_status(
            profile_status,
            state=EvidenceSourceState.INIT_FAILED,
            detail=profile_status.detail or "policy_verified_legal_toolkit_unavailable",
        )

    evidence_sources = _resolve_evidence_sources(state, profile)
    inferred = build_path_source_status(
        EvidenceSourceKind.LEGAL,
        evidence_sources.legal_db_path,
        detail="policy_verified_legal_toolkit",
    )
    if toolkit is not None:
        return update_source_status(
            inferred,
            state=EvidenceSourceState.AVAILABLE,
            detail="policy_verified_legal_toolkit_ready",
        )
    if inferred.status in {EvidenceSourceState.MISSING_CONFIG, EvidenceSourceState.MISSING_PATH}:
        return inferred
    return update_source_status(
        inferred,
        state=EvidenceSourceState.INIT_FAILED,
        detail="policy_verified_legal_toolkit_unavailable",
    )


def _load_cross_graph_profile(
    store: FileSystemCAS,
    state: ExperimentState,
) -> CrossGraphEvidenceProfile | None:
    from polisyos.core.artifacts import load_core_json_artifact

    raw_ref = state.artifacts_index.get(ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF)
    if raw_ref is None:
        return None
    try:
        return CrossGraphEvidenceProfile.model_validate(load_core_json_artifact(store, raw_ref))
    except (*_POLICY_VERIFIED_ARTIFACT_LOAD_ERRORS, *_POLICY_VERIFIED_MODEL_ERRORS):
        return None


def _plan_recall_queries(frame: PolicyRequestFrame, state: ExperimentState) -> list[str]:
    candidates = [
        frame.policy_question,
        *frame.goals,
        *frame.constraints,
    ]
    if frame.policy_domain:
        candidates.append(f"{frame.policy_domain} {frame.policy_question}")
        candidates.append(f"{frame.policy_domain} пороги винятки строки")
    candidates.extend(
        [
            f"{frame.policy_question} може має право",
            f"{frame.policy_question} крім за винятком",
            f"{frame.policy_question} порядок встановлюється",
            f"{frame.policy_question} набирає чинності",
        ]
    )
    seen: set[str] = set()
    queries: list[str] = []
    for item in candidates:
        text = str(item or "").strip()
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        queries.append(text)
    return queries


def _legal_claim_candidate(
    *,
    state: ExperimentState,
    claim_id: str,
    text: str,
    source: Literal["retrieved_fact", "llm_candidate", "legacy_unbound"],
    details: dict[str, Any],
) -> ClaimRecord:
    """Use the Claim owner for an unadmitted legal interpretation."""
    return ClaimRecord(
        claim_id=claim_id,
        run_id=state.run_id,
        claim_type=ClaimType.LEGAL,
        claim_use=ClaimUse.CONTEXT_ONLY,
        text=text,
        support_status=ClaimSupportStatus.NOT_EVALUABLE,
        publishability=ClaimPublishability.INTERNAL_ONLY,
        readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
        decomposition_source_class=(
            ClaimSourceClass.LLM_CANDIDATE if source == "llm_candidate" else None
        ),
        blocked_reasons=["legal_claim_verification_not_established"],
        metadata={"legal_source_candidate": {"source": source, **details}},
    )


def _baseline_claim_candidates(
    state: ExperimentState,
    candidate_pack: LegalCandidatePack,
    source_pack: LegalSourcePack,
) -> list[ClaimRecord]:
    fact_map = {fact.fact_id: fact for fact in candidate_pack.fact_hits}
    claims: list[ClaimRecord] = []
    for bundle in source_pack.source_bundles:
        for fact_id in bundle.candidate_fact_ids:
            fact = fact_map.get(fact_id)
            if fact is None or not fact.fact_text.strip():
                continue
            claim_type = _claim_type_from_fact(fact)
            claim_id = _stable_id(
                "claim_candidate", "retrieved_fact", bundle.bundle_id, fact.fact_id, fact.fact_text
            )
            claims.append(
                _legal_claim_candidate(
                    state=state,
                    claim_id=claim_id,
                    text=fact.fact_text,
                    source="retrieved_fact",
                    details={
                        "bundle_id": bundle.bundle_id,
                        "doc_id": fact.doc_id,
                        "version_id": fact.version_id,
                        "anchor": fact.provision_anchor,
                        "citation_label": fact.provision_citation,
                        "claim_type": claim_type,
                        "quote": fact.source_quote_uk,
                        "reported_trust_tier": fact.trust_tier,
                        "reported_grounding_status": fact.grounding_status,
                        "reported_confidence": fact.confidence,
                        "raw_retrieved_fact": fact.model_dump(mode="json"),
                    },
                )
            )
    return _merge_candidate_claims([], claims)


def _merge_candidate_claims(
    baseline: list[ClaimRecord], additions: list[ClaimRecord]
) -> list[ClaimRecord]:
    """Deduplicate candidate identities without promoting their content."""
    merged = {claim.claim_id: claim for claim in baseline}
    merged.update({claim.claim_id: claim for claim in additions})
    return list(merged.values())


def _initial_gaps(
    source_pack: LegalSourcePack, claims: list[VerifiedLegalClaim]
) -> list[SourceCoverageGap]:
    claimed_bundle_ids = {claim.bundle_id for claim in claims}
    gaps: list[SourceCoverageGap] = []
    for bundle in source_pack.source_bundles:
        if bundle.bundle_id in claimed_bundle_ids:
            continue
        gaps.append(
            SourceCoverageGap(
                gap_id=_stable_id("gap", bundle.bundle_id, "no_quote_backed_claims"),
                category="no_quote_backed_claims",
                description=f"No quote-backed verified claim extracted for {bundle.doc_name or bundle.doc_id}.",
                severity="critical"
                if bundle.source_family in {"approval_bundle", "amendment_bundle"}
                else "warning",
                related_bundle_ids=[bundle.bundle_id],
                suggested_queries=[bundle.doc_name or bundle.doc_reestr_code or bundle.doc_id],
            )
        )
    return gaps


def _claim_type_from_fact(fact: LegalFactResult) -> str:
    if fact.threshold_bearing or (fact.thresholds_json and fact.thresholds_json != "[]"):
        return "threshold"
    if fact.norm_type_canon:
        return fact.norm_type_canon
    if fact.norm_type:
        return fact.norm_type
    return fact.predicate or "applicability"


def _claim_citation_coverage_pct(claims: list[VerifiedLegalClaim]) -> float:
    if not claims:
        return 0.0
    cited = sum(1 for claim in claims if claim.quote.strip() and claim.anchor.strip())
    return round((cited / max(len(claims), 1)) * 100.0, 2)


def _merge_verified_claims(
    baseline: list[VerifiedLegalClaim],
    additions: list[VerifiedLegalClaim],
) -> list[VerifiedLegalClaim]:
    merged: dict[tuple[str, str, str], VerifiedLegalClaim] = {}
    for claim in [*baseline, *additions]:
        key = (
            claim.claim_type.strip().lower(),
            claim.anchor.strip().lower(),
            claim.claim_text.strip().lower(),
        )
        current = merged.get(key)
        if current is None or claim.confidence > current.confidence:
            merged[key] = claim
    return list(merged.values())


def _merge_gaps(
    baseline: list[SourceCoverageGap],
    additions: list[SourceCoverageGap],
) -> list[SourceCoverageGap]:
    merged: dict[str, SourceCoverageGap] = {}
    for gap in [*baseline, *additions]:
        merged[gap.gap_id] = gap
    return list(merged.values())


def _merge_source_packs(
    baseline: LegalSourcePack,
    additions: LegalSourcePack,
) -> LegalSourcePack:
    bundle_map = {bundle.bundle_id: bundle for bundle in baseline.source_bundles}
    for bundle in additions.source_bundles:
        bundle_map[bundle.bundle_id] = bundle
    return baseline.model_copy(
        update={
            "source_bundles": list(bundle_map.values()),
            "unresolved_anchor_hints": _dedupe_texts(
                [*baseline.unresolved_anchor_hints, *additions.unresolved_anchor_hints]
            ),
            "notes": [
                *baseline.notes,
                *[note for note in additions.notes if note not in baseline.notes],
            ],
        }
    )


def _plan_gap_recovery_queries(
    frame: PolicyRequestFrame,
    source_pack: LegalSourcePack,
    report: SourceVerificationReport,
) -> list[str]:
    candidates: list[str] = [frame.policy_question]
    for gap in report.unresolved_critical_gaps:
        candidates.extend(gap.suggested_queries)
        if gap.related_bundle_ids:
            candidates.extend(gap.related_bundle_ids)
    candidates.extend(source_pack.unresolved_anchor_hints)
    for bundle in source_pack.source_bundles:
        if bundle.source_family in {"approval_bundle", "amendment_bundle", "appendix_heavy"}:
            candidates.append(f"{bundle.doc_name} {bundle.doc_reestr_code}".strip())
    return _dedupe_texts(candidates)


def _dedupe_texts(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for raw in values:
        text = str(raw or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(text)
    return deduped


def _format_verified_finding(claim: VerifiedLegalClaim) -> str:
    citation = claim.citation_label or f"{claim.doc_id}:{claim.anchor}"
    return f"{claim.claim_text} [{citation}]"


def _string_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _stable_id(prefix: str, *parts: str) -> str:
    normalized = "|".join(part.strip() for part in parts if part is not None)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _int_param(state: ExperimentState, key: str, default: int) -> int:
    try:
        return max(0, int(state.params.get(key, default)))
    except (TypeError, ValueError):
        return default


def _maybe_verify_with_llm(
    *,
    state: ExperimentState,
    frame: PolicyRequestFrame,
    source_pack: LegalSourcePack,
    baseline_claims: list[ClaimRecord],
) -> tuple[list[ClaimRecord], list[SourceCoverageGap], int, int, float]:
    client = create_traced_gateway_client(
        model_name=str(state.params.get("source_verifier_model") or "gpt-5.4"),
        run_id=state.run_id,
        provider_hint=str(state.params.get("llm_provider") or "") or None,
    )
    if client is None or not source_pack.source_bundles:
        return [], [], 0, 0, 0.0

    async def _run() -> tuple[list[ClaimRecord], list[SourceCoverageGap], int]:
        sem = asyncio.Semaphore(8)
        max_calls = _int_param(state, "max_verifier_calls", 500)
        bundles = source_pack.source_bundles[:max_calls]
        claims: list[ClaimRecord] = []
        gaps: list[SourceCoverageGap] = []

        async def _verify_bundle(
            bundle: LegalSourceBundle,
        ) -> tuple[list[ClaimRecord], list[SourceCoverageGap]]:
            async with sem:
                user_payload = {
                    "policy_question": frame.policy_question,
                    "jurisdiction": frame.jurisdiction,
                    "as_of": frame.as_of,
                    "source_bundle": bundle.model_dump(mode="json"),
                }
                response = await client.generate(
                    system=get_source_verifier_prompt(),
                    user=json.dumps(user_payload, ensure_ascii=False),
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=1800,
                )
                payload = _parse_json_object(response.content)
                if not isinstance(payload, dict):
                    return [], []
                parsed_claims: list[ClaimRecord] = []
                for item in (
                    payload.get("claims", []) if isinstance(payload.get("claims"), list) else []
                ):
                    if not isinstance(item, dict):
                        continue
                    anchor = str(item.get("anchor") or "").strip()
                    quote = str(item.get("quote") or "").strip()
                    claim_text = str(item.get("claim_text") or "").strip()
                    claim_type = str(item.get("claim_type") or "").strip()
                    if not claim_text:
                        continue
                    parsed_claims.append(
                        _legal_claim_candidate(
                            state=state,
                            claim_id=_stable_id(
                                "claim_candidate",
                                "llm_candidate",
                                bundle.bundle_id,
                                anchor,
                                claim_type,
                                claim_text,
                            ),
                            text=claim_text,
                            source="llm_candidate",
                            details={
                                "bundle_id": bundle.bundle_id,
                                "doc_id": bundle.doc_id,
                                "version_id": bundle.version_id,
                                "anchor": anchor,
                                "citation_label": str(item.get("citation_label") or "").strip(),
                                "claim_type": claim_type,
                                "quote": quote,
                                "reported_confidence": item.get("confidence"),
                                "needs_additional_sources": item.get("needs_additional_sources"),
                                "raw_model_item": dict(item),
                            },
                        )
                    )
                parsed_gaps = [
                    SourceCoverageGap(
                        gap_id=_stable_id(
                            "gap",
                            bundle.bundle_id,
                            str(item.get("category") or ""),
                            str(item.get("description") or ""),
                        ),
                        category=str(item.get("category") or "unresolved"),
                        description=str(item.get("description") or "Unresolved source ambiguity."),
                        severity="warning",
                        related_bundle_ids=[bundle.bundle_id],
                    )
                    for item in payload.get("unresolved", [])
                    if isinstance(item, dict)
                ]
                return parsed_claims, parsed_gaps

        results = await asyncio.gather(
            *[_verify_bundle(bundle) for bundle in bundles],
            return_exceptions=True,
        )
        for outcome in results:
            if isinstance(outcome, BaseException):
                if isinstance(outcome, (AssertionError, KeyboardInterrupt, SystemExit)):
                    raise outcome
                continue
            bundle_claims, bundle_gaps = outcome
            claims.extend(bundle_claims)
            gaps.extend(bundle_gaps)
        return claims, gaps, len(bundles)

    try:
        claims, gaps, verifier_calls = asyncio.run(_run())
    except _POLICY_VERIFIED_ASYNC_RUN_ERRORS:
        return [], [], 0, 0, 0.0
    disagreement_rate = 0.0
    if baseline_claims and claims:

        def claim_key(claim: ClaimRecord) -> tuple[str, str, str]:
            source = claim.metadata.get("legal_source_candidate", {})
            return (str(source.get("anchor", "")), str(source.get("claim_type", "")), claim.text)

        baseline_keys = {claim_key(claim) for claim in baseline_claims}
        llm_keys = {claim_key(claim) for claim in claims}
        disagreement_rate = round(
            1.0 - (len(baseline_keys & llm_keys) / max(len(llm_keys), 1)),
            4,
        )
    return claims, gaps, verifier_calls, 0, disagreement_rate


def _parse_json_object(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        return dict(extract_llm_json_object(raw))
    except _POLICY_VERIFIED_JSON_ERRORS:
        return None


__all__ = [
    "assemble_legal_candidate_pack",
    "build_policy_request_frame",
    "build_verified_policy_report",
    "draft_policy_option_set",
    "expand_legal_source_pack",
    "formalize_policy_option_set",
    "POLICY_VERIFIED_HARDCODED_FORMALIZER_STRANGLED",
    "recover_source_gaps",
    "review_source_gaps",
    "verify_source_pack",
]
