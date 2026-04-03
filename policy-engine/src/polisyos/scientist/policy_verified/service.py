"""Public policy verified service module API."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.scientist import (
    LegalCandidatePackRef,
    LegalSourcePackRef,
    PolicyRequestFrameRef,
    SourceVerificationReportRef,
    VerifiedPolicyReportRef,
)
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
from polisyos.scientist.agent.formalizer import MockFormalizerAgent
from polisyos.scientist.agent.prompts import get_source_verifier_prompt
from polisyos.scientist.agent.protocols import DraftResult
from polisyos.scientist.agent.knowledge_tools import KnowledgeToolkit
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.evidence_sources import (
    build_path_source_status,
    normalize_evidence_sources_config,
    update_source_status,
)
from polisyos.scientist.llm.factory import create_traced_gateway_client
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    INPUT_RESEARCH_INTENT_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.policy_verified.models import (
    LegalCandidatePack,
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


def build_policy_request_frame(ctx: ExecutionContext, state: ExperimentState) -> PolicyRequestFrame:
    """Build policy request frame."""
    intent = _load_research_intent(ctx.store, state.inputs.get(INPUT_RESEARCH_INTENT_REF))
    params = state.params
    raw_question = (
        str(params.get("policy_question") or "").strip()
        or str(params.get("policy_request") or "").strip()
        or str(params.get("problem_statement") or "").strip()
        or str(params.get("research_question") or "").strip()
        or str(getattr(intent, "topic", "") or "").strip()
        or "Design a policy option set grounded in applicable legal sources."
    )
    jurisdiction = (
        str(params.get("policy_request_jurisdiction") or "").strip()
        or str(params.get("jurisdiction") or "").strip()
        or str(getattr(intent, "jurisdiction", "") or "").strip()
        or "UA"
    )
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
    notes = _string_list(params.get("notes"))
    if intent is not None:
        notes.extend(list(getattr(intent, "notes", []) or []))
    request_id = _stable_id("policy_request", raw_question, jurisdiction, as_of or "", domain or "")
    return PolicyRequestFrame(
        request_id=request_id,
        policy_question=raw_question,
        jurisdiction=jurisdiction,
        as_of=as_of,
        policy_domain=domain,
        target_context=dict(params.get("target_context") or {}) if isinstance(params.get("target_context"), dict) else {},
        evaluation_criteria=evaluation_criteria,
        goals=goals,
        constraints=constraints,
        notes=notes,
    )


def assemble_legal_candidate_pack(
    ctx: ExecutionContext,
    state: ExperimentState,
    frame: PolicyRequestFrame,
) -> LegalCandidatePack:
    """Assemble legal candidate pack helper."""
    toolkit = _build_legal_toolkit(ctx, state)
    legal_status = _resolve_legal_source_status(ctx, state, toolkit=toolkit)
    if toolkit is None:
        return LegalCandidatePack(
            request_id=frame.request_id,
            queries=[frame.policy_question],
            source_statuses={"legal": legal_status},
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
                merged.anchor_coverage_hints.setdefault(provision.provision_id, [provision.anchor_path])
    merged.fact_hits = list(fact_map.values())
    merged.provision_hits = list(provision_map.values())
    merged.source_statuses["legal"] = legal_status
    return merged


def expand_legal_source_pack(
    ctx: ExecutionContext,
    state: ExperimentState,
    candidate_pack: LegalCandidatePack,
) -> LegalSourcePack:
    """Expand legal source pack helper."""
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


def verify_source_pack(
    ctx: ExecutionContext,
    state: ExperimentState,
    frame: PolicyRequestFrame,
    candidate_pack: LegalCandidatePack,
    source_pack: LegalSourcePack,
) -> SourceVerificationReport:
    """Verify source pack helper."""
    baseline_claims = _baseline_verified_claims(candidate_pack, source_pack)
    gaps = _initial_gaps(source_pack, baseline_claims)
    report = SourceVerificationReport(
        request_id=frame.request_id,
        verified_claims=baseline_claims,
        unresolved_critical_gaps=gaps,
        verified_claim_citation_coverage_pct=_claim_citation_coverage_pct(baseline_claims),
        verification_cycles_completed=max(1, _int_param(state, "verification_cycles_completed", 0) + 1),
        needs_expert_review=any(gap.severity == "critical" for gap in gaps),
        source_statuses={
            **dict(candidate_pack.source_statuses),
            **dict(source_pack.source_statuses),
        },
        notes=["baseline_source_verification"],
    )
    llm_claims, llm_gaps, verifier_calls, adjudicator_calls, disagreement_rate = _maybe_verify_with_llm(
        state=state,
        frame=frame,
        source_pack=source_pack,
        baseline_claims=baseline_claims,
    )
    if llm_claims:
        merged = _merge_verified_claims(report.verified_claims, llm_claims)
        report = report.model_copy(
            update={
                "verified_claims": merged,
                "unresolved_critical_gaps": _merge_gaps(report.unresolved_critical_gaps, llm_gaps),
                "verifier_calls_total": verifier_calls,
                "adjudicator_calls_total": adjudicator_calls,
                "verifier_disagreement_rate": disagreement_rate,
                "verified_claim_citation_coverage_pct": _claim_citation_coverage_pct(merged),
                "needs_expert_review": report.needs_expert_review or any(
                    gap.severity == "critical" for gap in llm_gaps
                ),
                "notes": [*report.notes, "llm_source_verification"],
            }
        )
    return report


def review_source_gaps(
    state: ExperimentState,
    frame: PolicyRequestFrame,
    source_pack: LegalSourcePack,
    report: SourceVerificationReport,
) -> SourceVerificationReport:
    """Review source gaps helper."""
    gaps = list(report.unresolved_critical_gaps)
    if not gaps and report.verified_claims:
        return report
    extra_gaps = []
    for bundle in source_pack.source_bundles:
        if any(claim.bundle_id == bundle.bundle_id for claim in report.verified_claims):
            continue
        extra_gaps.append(
            SourceCoverageGap(
                gap_id=_stable_id("gap", bundle.bundle_id, "bundle_without_claims"),
                category="bundle_without_claims",
                description=f"No verified claim extracted for {bundle.doc_name or bundle.doc_id}.",
                severity="critical" if bundle.source_family in {"approval_bundle", "amendment_bundle"} else "warning",
                related_bundle_ids=[bundle.bundle_id],
                suggested_queries=[frame.policy_question, f"{bundle.doc_name} {bundle.doc_reestr_code}".strip()],
            )
        )
    merged = _merge_gaps(gaps, extra_gaps)
    needs_expert_review = report.needs_expert_review or any(g.severity == "critical" for g in merged)
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
    """Recover source gaps helper."""
    reviewed_report = review_source_gaps(state, frame, source_pack, report)
    if not reviewed_report.unresolved_critical_gaps:
        return candidate_pack, source_pack, reviewed_report

    completed_cycles = max(0, int(reviewed_report.verification_cycles_completed))
    if completed_cycles >= 2:
        exhausted = reviewed_report.model_copy(
            update={
                "notes": [*reviewed_report.notes, "recovery_budget_exhausted"],
                "needs_expert_review": reviewed_report.needs_expert_review or bool(
                    reviewed_report.unresolved_critical_gaps
                ),
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

    retry_candidate_pack = LegalCandidatePack(request_id=candidate_pack.request_id, queries=retry_queries)
    fact_map = {fact.fact_id: fact for fact in candidate_pack.fact_hits}
    provision_map = {provision.provision_id: provision for provision in candidate_pack.provision_hits}
    hit_reasons = dict(candidate_pack.hit_reasons)
    source_family_hints = dict(candidate_pack.source_family_hints)
    anchor_coverage_hints = {
        key: list(values) for key, values in candidate_pack.anchor_coverage_hints.items()
    }
    for query in retry_queries:
        pack = toolkit.assemble_legal_candidate_pack(
            query,
            jurisdiction=frame.jurisdiction,
            domain=frame.policy_domain,
            as_of=frame.as_of,
        )
        retry_candidate_pack.queries.extend(pack.queries)
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
    merged_claims = _merge_verified_claims(reviewed_report.verified_claims, retry_report.verified_claims)
    recomputed_gaps = _initial_gaps(merged_source_pack, merged_claims)
    merged_gaps = _merge_gaps(recomputed_gaps, retry_report.unresolved_critical_gaps)
    final_report = reviewed_report.model_copy(
        update={
            "verified_claims": merged_claims,
            "unresolved_critical_gaps": merged_gaps,
            "verification_cycles_completed": max(
                reviewed_report.verification_cycles_completed,
                retry_report.verification_cycles_completed,
            ),
            "verifier_calls_total": reviewed_report.verifier_calls_total + retry_report.verifier_calls_total,
            "adjudicator_calls_total": reviewed_report.adjudicator_calls_total
            + retry_report.adjudicator_calls_total,
            "verifier_disagreement_rate": max(
                reviewed_report.verifier_disagreement_rate,
                retry_report.verifier_disagreement_rate,
            ),
            "verified_claim_citation_coverage_pct": _claim_citation_coverage_pct(merged_claims),
            "needs_expert_review": any(gap.severity == "critical" for gap in merged_gaps),
            "notes": [*reviewed_report.notes, "gap_recovery_cycle_completed"],
        }
    )
    return merged_candidate_pack, merged_source_pack, final_report


def draft_policy_option_set(
    state: ExperimentState,
    frame: PolicyRequestFrame,
    report: SourceVerificationReport,
) -> PolicyOptionSet:
    """Draft policy option set helper."""
    verified_claims = report.verified_claims
    citations = sorted({claim.citation_label for claim in verified_claims if claim.citation_label})
    constraints = [
        claim.claim_text
        for claim in verified_claims
        if claim.claim_type in {"obligation", "prohibition", "exception", "conflict"}
    ][:8]
    thresholds = [claim.claim_text for claim in verified_claims if claim.claim_type == "threshold"][:6]
    timing = [
        claim.claim_text
        for claim in verified_claims
        if claim.claim_type in {"temporal", "enters_into_force"}
    ][:6]
    verified_option = PolicyOption(
        option_id="verified_option_1",
        title="Verified policy option",
        summary=frame.policy_question,
        intervention_outline={"policy_question": frame.policy_question, "domain": frame.policy_domain or "custom"},
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
    if bool(state.params.get("allow_hypotheses", True)) and report.unresolved_critical_gaps:
        hypothesis_options.append(
            PolicyOption(
                option_id="hypothesis_option_1",
                title="Hypothesis-driven revision option",
                summary="Exploratory option that requires additional legal verification before adoption.",
                intervention_outline={"policy_question": frame.policy_question, "mode": "hypothesis"},
                hypothesis_basis=True,
                notes=[gap.description for gap in report.unresolved_critical_gaps[:5]],
            )
        )
    return PolicyOptionSet(
        request_id=frame.request_id,
        verified_options=[verified_option],
        hypothesis_options=hypothesis_options,
    )


def formalize_policy_option_set(
    ctx: ExecutionContext,
    state: ExperimentState,
    frame: PolicyRequestFrame,
    option_set: PolicyOptionSet,
) -> TrinityBundleRef | None:
    """Formalize policy option set helper."""
    existing_ref = state.inputs.get(INPUT_TRINITY_BUNDLE_REF)
    if existing_ref is not None:
        return TrinityBundleRef.model_validate(existing_ref.model_dump())
    primary = (option_set.verified_options or option_set.hypothesis_options or [None])[0]
    if primary is None:
        return None
    draft = DraftResult(
        draft_id=_stable_id("draft", frame.request_id, primary.option_id),
        problem_frame_ref=frame.request_id,
        narrative=primary.summary,
        interventions=[
            {
                "name": primary.title,
                "description": primary.summary,
                "mechanism_type": "tax_subsidy",
                "target_population": "all",
                "parameters": {"rate": "0.1"},
                "rationale": primary.summary,
            }
        ],
        rationale="Derived from verified policy option set.",
        confidence=0.7,
    )
    bundle = asyncio.run(MockFormalizerAgent().formalize(draft))
    artifact = ctx.store.put_json(
        bundle,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=str(bundle.schema_version)),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return TrinityBundleRef.model_validate(artifact.model_dump())


def build_verified_policy_report(
    state: ExperimentState,
    frame: PolicyRequestFrame,
    report: SourceVerificationReport,
    option_set: PolicyOptionSet,
) -> VerifiedPolicyReport:
    """Build verified policy report."""
    constraints_and_timing = []
    for option in option_set.verified_options:
        constraints_and_timing.extend(option.constraints)
        constraints_and_timing.extend(option.thresholds)
        constraints_and_timing.extend(option.timing)
    verified_findings = [
        _format_verified_finding(claim)
        for claim in report.verified_claims[:30]
    ]
    intervention_legal_basis_map = {
        option.option_id: list(option.legal_basis_refs)
        for option in [*option_set.verified_options, *option_set.hypothesis_options]
    }
    simulation_notes: list[str] = []
    if ARTIFACT_METRICS_REF in state.artifacts_index:
        simulation_notes.append("Simulation artifacts are available for this policy package.")
    if ARTIFACT_CAUSAL_REPORT_REF in state.artifacts_index:
        simulation_notes.append("Causal evaluation artifacts are available for this policy package.")
    missing_evidence = [gap.description for gap in report.unresolved_critical_gaps]
    for source_name, source_status in sorted(report.source_statuses.items()):
        if source_status.status is EvidenceSourceState.AVAILABLE:
            continue
        missing_evidence.append(
            f"Evidence source '{source_name}' is unavailable ({source_status.status.value})."
        )
    citation_appendix = sorted(
        {
            f"{claim.citation_label} [{claim.doc_id}:{claim.anchor}]"
            for claim in report.verified_claims
            if claim.citation_label or claim.anchor
        }
    )
    executive_summary = (
        f"Scientist verified {len(report.verified_claims)} legal claims for '{frame.policy_question}'. "
        f"{len(option_set.verified_options)} verified option(s) and "
        f"{len(option_set.hypothesis_options)} hypothesis option(s) were prepared."
    )
    return VerifiedPolicyReport(
        request_id=frame.request_id,
        executive_summary=executive_summary,
        verified_legal_basis=report.verified_claims,
        policy_options=[*option_set.verified_options, *option_set.hypothesis_options],
        constraints_and_timing=constraints_and_timing[:20],
        simulation_and_causal_implications=simulation_notes,
        verified_findings=verified_findings,
        hypotheses=[option.summary for option in option_set.hypothesis_options],
        missing_evidence=missing_evidence,
        unresolved_critical_gaps=report.unresolved_critical_gaps,
        citation_appendix=citation_appendix,
        intervention_legal_basis_map=intervention_legal_basis_map,
        needs_expert_review=report.needs_expert_review,
        source_statuses=dict(report.source_statuses),
        notes=[
            f"evidence_source_unavailable:{name}:{status.status.value}"
            for name, status in sorted(report.source_statuses.items())
            if status.status is not EvidenceSourceState.AVAILABLE
        ],
    )


def _load_research_intent(store: FileSystemCAS, raw_ref: Any) -> ResearchIntent | None:
    if raw_ref is None:
        return None
    try:
        ref = ResearchIntentRef.model_validate(raw_ref.model_dump() if hasattr(raw_ref, "model_dump") else raw_ref)
    except Exception:
        return None
    try:
        payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    except Exception:
        return None
    try:
        return ResearchIntent.model_validate(payload)
    except Exception:
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
    except Exception:
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
    raw_ref = state.artifacts_index.get(ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF)
    if raw_ref is None:
        return None
    try:
        return CrossGraphEvidenceProfile.model_validate(
            from_canonical_bytes(store.get_bytes(raw_ref.artifact_id))
        )
    except Exception:
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


def _baseline_verified_claims(
    candidate_pack: LegalCandidatePack,
    source_pack: LegalSourcePack,
) -> list[VerifiedLegalClaim]:
    fact_map = {fact.fact_id: fact for fact in candidate_pack.fact_hits}
    claims: list[VerifiedLegalClaim] = []
    for bundle in source_pack.source_bundles:
        valid_anchors = {anchor.anchor for anchor in bundle.primary_anchors}
        for fact_id in bundle.candidate_fact_ids:
            fact = fact_map.get(fact_id)
            if fact is None or not fact.source_quote_uk.strip():
                continue
            if fact.provision_anchor and valid_anchors and fact.provision_anchor not in valid_anchors:
                continue
            claim_type = _claim_type_from_fact(fact)
            claim_id = _stable_id("claim", bundle.bundle_id, fact.fact_id, claim_type, fact.fact_text)
            claims.append(
                VerifiedLegalClaim(
                    claim_id=claim_id,
                    bundle_id=bundle.bundle_id,
                    doc_id=fact.doc_id,
                    version_id=fact.version_id,
                    anchor=fact.provision_anchor or next(iter(valid_anchors), ""),
                    citation_label=fact.provision_citation,
                    claim_type=claim_type,
                    claim_text=fact.fact_text,
                    quote=fact.source_quote_uk,
                    quote_offsets=None,
                    confidence=max(0.5, min(float(fact.confidence), 0.99)),
                    needs_additional_sources=False,
                )
            )
    return _merge_verified_claims([], claims)


def _initial_gaps(source_pack: LegalSourcePack, claims: list[VerifiedLegalClaim]) -> list[SourceCoverageGap]:
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
                severity="critical" if bundle.source_family in {"approval_bundle", "amendment_bundle"} else "warning",
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
            "notes": [*baseline.notes, *[note for note in additions.notes if note not in baseline.notes]],
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
    baseline_claims: list[VerifiedLegalClaim],
) -> tuple[list[VerifiedLegalClaim], list[SourceCoverageGap], int, int, float]:
    client = create_traced_gateway_client(
        model_name=str(state.params.get("source_verifier_model") or "gpt-5.4"),
        run_id=state.run_id,
        provider_hint=str(state.params.get("llm_provider") or "") or None,
    )
    if client is None or not source_pack.source_bundles:
        return [], [], 0, 0, 0.0

    async def _run() -> tuple[list[VerifiedLegalClaim], list[SourceCoverageGap], int]:
        sem = asyncio.Semaphore(8)
        max_calls = _int_param(state, "max_verifier_calls", 500)
        bundles = source_pack.source_bundles[:max_calls]
        claims: list[VerifiedLegalClaim] = []
        gaps: list[SourceCoverageGap] = []

        async def _verify_bundle(bundle: LegalSourceBundle) -> tuple[list[VerifiedLegalClaim], list[SourceCoverageGap]]:
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
                parsed_claims: list[VerifiedLegalClaim] = []
                for item in payload.get("claims", []) if isinstance(payload.get("claims"), list) else []:
                    if not isinstance(item, dict):
                        continue
                    anchor = str(item.get("anchor") or "").strip()
                    quote = str(item.get("quote") or "").strip()
                    claim_text = str(item.get("claim_text") or "").strip()
                    claim_type = str(item.get("claim_type") or "").strip()
                    if not (anchor and quote and claim_text and claim_type):
                        continue
                    parsed_claims.append(
                        VerifiedLegalClaim(
                            claim_id=_stable_id("claim", bundle.bundle_id, anchor, claim_type, claim_text),
                            bundle_id=bundle.bundle_id,
                            doc_id=bundle.doc_id,
                            version_id=bundle.version_id,
                            anchor=anchor,
                            citation_label=str(item.get("citation_label") or "").strip(),
                            claim_type=claim_type,
                            claim_text=claim_text,
                            quote=quote,
                            confidence=float(item.get("confidence") or 0.7),
                            needs_additional_sources=bool(item.get("needs_additional_sources", False)),
                        )
                    )
                parsed_gaps = [
                    SourceCoverageGap(
                        gap_id=_stable_id("gap", bundle.bundle_id, str(item.get("category") or ""), str(item.get("description") or "")),
                        category=str(item.get("category") or "unresolved"),
                        description=str(item.get("description") or "Unresolved source ambiguity."),
                        severity="warning",
                        related_bundle_ids=[bundle.bundle_id],
                    )
                    for item in payload.get("unresolved", [])
                    if isinstance(item, dict)
                ]
                return parsed_claims, parsed_gaps

        results = await asyncio.gather(*[_verify_bundle(bundle) for bundle in bundles])
        for bundle_claims, bundle_gaps in results:
            claims.extend(bundle_claims)
            gaps.extend(bundle_gaps)
        return claims, gaps, len(bundles)

    try:
        claims, gaps, verifier_calls = asyncio.run(_run())
    except Exception:
        return [], [], 0, 0, 0.0
    disagreement_rate = 0.0
    if baseline_claims and claims:
        baseline_keys = {(c.anchor, c.claim_type, c.claim_text) for c in baseline_claims}
        llm_keys = {(c.anchor, c.claim_type, c.claim_text) for c in claims}
        disagreement_rate = round(
            1.0 - (len(baseline_keys & llm_keys) / max(len(llm_keys), 1)),
            4,
        )
    return claims, gaps, verifier_calls, 0, disagreement_rate


def _parse_json_object(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.split("\n", 1)[-1]
    try:
        payload = json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            payload = json.loads(raw[start : end + 1])
        except Exception:
            return None
    return payload if isinstance(payload, dict) else None


__all__ = [
    "build_policy_request_frame",
    "assemble_legal_candidate_pack",
    "expand_legal_source_pack",
    "verify_source_pack",
    "review_source_gaps",
    "recover_source_gaps",
    "draft_policy_option_set",
    "formalize_policy_option_set",
    "build_verified_policy_report",
]
