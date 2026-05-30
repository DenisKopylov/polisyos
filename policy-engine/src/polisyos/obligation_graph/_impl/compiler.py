"""Compiler for C38 obligation ledgers and bounded blocking frontiers."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import (
    BundleKey,
    CandidateLedgerEntry,
    ComplexityBudget,
    DeadlineBinding,
    DeferredObligationRecord,
    DeferredState,
    FacetSnapshot,
    FrontierItem,
    GovernedObligationRule,
    ObligationBundle,
    ObligationCandidateInput,
    ObligationGraph,
    PriorityClass,
    SourceClass,
)

_PRIORITY_RANK: dict[PriorityClass, int] = {
    PriorityClass.AUTHORITY_LEVEL_MANDATORY: 0,
    PriorityClass.MANDATORY: 1,
    PriorityClass.CONDITIONAL: 2,
    PriorityClass.REVIEW_REQUIRED: 3,
    PriorityClass.CANDIDATE: 4,
    PriorityClass.OPTIONAL: 5,
    PriorityClass.DEFERRED: 6,
    PriorityClass.REJECTED: 7,
}
_FRONTIER_PRIORITIES = frozenset(
    {
        PriorityClass.AUTHORITY_LEVEL_MANDATORY,
        PriorityClass.MANDATORY,
        PriorityClass.CONDITIONAL,
        PriorityClass.REVIEW_REQUIRED,
    }
)
_REJECTING_BLOCKERS = frozenset(
    {
        "authority_allowance_failed",
        "legal_privacy_admissibility_failed",
    }
)
_BLOCKER_PRECEDENCE = (
    "legal_requirement_proof_missing",
    "authority_allowance_failed",
    "legal_privacy_admissibility_failed",
    "current_run_relevance_failed",
    "material_public_risk_failed",
    "source_ceiling_candidate_not_blocking",
    "source_ceiling_optional_not_blocking",
)


class ObligationGraphCompileError(ValueError):
    """Raised when the obligation graph cannot be compiled truthfully."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def compile_obligation_graph(
    *,
    run_id: str,
    facets: Sequence[FacetSnapshot | Mapping[str, Any]],
    governed_rules: Sequence[GovernedObligationRule | Mapping[str, Any]] = (),
    candidate_sources: Sequence[ObligationCandidateInput | Mapping[str, Any]] = (),
    complexity_budget: ComplexityBudget | Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
    graph_id: str | None = None,
    intent_text: str | None = None,
) -> ObligationGraph:
    """Compile raw obligation candidates into a three-tier W6.C graph.

    Args:
        run_id: Runtime case/run id.
        facets: W6.A facet snapshots. At least one facet is required because
            W6.C must not invent obligations without grammar grounding.
        governed_rules: W6.B governed rule snapshots. Only ``status=governed``
            rules whose facet requirements match the supplied facets are
            converted into candidates.
        candidate_sources: Raw producer, critic, reviewer, public, legal, or
            LLM candidates.
        complexity_budget: Governed frontier budget.
        generated_at: Deterministic timestamp for tests/replay.
        graph_id: Optional stable graph id.

    Returns:
        A typed, persistable :class:`ObligationGraph`.
    """

    normalized_run_id = _required_text(run_id)
    now = _utc(generated_at)
    facet_rows = tuple(_coerce_facet(facet) for facet in facets)
    if not facet_rows:
        raise ObligationGraphCompileError(
            "facet_derivation_missing",
            "W6.C cannot compile an ObligationGraph without W6.A facet derivation.",
        )
    budget = _coerce_budget(complexity_budget)
    rule_rows = tuple(_coerce_rule(rule) for rule in governed_rules)
    source_rows = tuple(_coerce_candidate(candidate) for candidate in candidate_sources)
    candidates = (
        *_candidates_from_governed_rules(
            rule_rows,
            facets=facet_rows,
            intent_text=intent_text,
        ),
        *source_rows,
    )

    candidate_ledger = tuple(
        _ledger_entry(candidate, index=index, observed_at=now)
        for index, candidate in enumerate(candidates)
    )
    bundle_ledger = _bundle_ledger(candidate_ledger)
    blocking_frontier, deferred_or_rejected = _promote_frontier(
        bundle_ledger,
        candidate_ledger=candidate_ledger,
        budget=budget,
        observed_at=now,
    )
    graph_identifier = graph_id or f"obligation-graph-{_slug(normalized_run_id)}"
    graph = ObligationGraph(
        graph_id=graph_identifier,
        run_id=normalized_run_id,
        generated_at=now,
        facets=facet_rows,
        candidate_ledger=candidate_ledger,
        bundle_ledger=bundle_ledger,
        blocking_frontier=blocking_frontier,
        deferred_or_rejected=deferred_or_rejected,
        complexity_budget=budget,
        telemetry=_telemetry(
            candidate_ledger=candidate_ledger,
            bundle_ledger=bundle_ledger,
            blocking_frontier=blocking_frontier,
            deferred_or_rejected=deferred_or_rejected,
        ),
        runtime_event_ref=f"event://runtime/obligation-graph/{_slug(normalized_run_id)}",
        evidence_ref=f"artifact://policy-design-case/{_slug(normalized_run_id)}/obligation-graph",
        authority_boundary={
            "authoritative_for": (
                "obligation_candidate_visibility",
                "obligation_bundle_deduplication",
                "obligation_frontier_selection",
            ),
            "may_not_use_for": (
                "domain_evidence",
                "claim_support",
                "legal_authority_without_lex_validation",
                "method_validity",
                "participation_legitimacy",
                "projection_authority",
            ),
        },
    )
    _assert_no_llm_authority_leakage(graph)
    return graph


def write_obligation_graph_artifact(
    graph: ObligationGraph | Mapping[str, Any],
    output_dir: str | Path,
) -> Path:
    """Persist an obligation graph artifact as deterministic JSON.

    Args:
        graph: Graph instance or graph payload.
        output_dir: Directory where the artifact should be written.

    Returns:
        Path to the written JSON artifact.
    """

    graph_model = (
        graph if isinstance(graph, ObligationGraph) else ObligationGraph.model_validate(graph)
    )
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{_slug(graph_model.graph_id)}.json"
    path.write_text(
        json.dumps(graph_model.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def obligation_graph_audit_surface(graph: ObligationGraph | Mapping[str, Any]) -> dict[str, Any]:
    """Return the machine/audit projection for the compiled obligation graph."""

    graph_model = (
        graph if isinstance(graph, ObligationGraph) else ObligationGraph.model_validate(graph)
    )
    payload = graph_model.model_dump(mode="json")
    payload["surface"] = "obligation_graph.audit_surface"
    payload["visibility_contract"] = {
        "candidate_ledger": "append_only_unbounded_never_blocks",
        "bundle_ledger": "one_active_bundle_per_family_scope_authority_time_remedy",
        "blocking_frontier": "bounded_by_complexity_budget_after_authority_filters",
        "deferred_or_rejected": "visible_with_reason_owner_time_reopen_trigger",
    }
    return payload


def _candidates_from_governed_rules(
    rules: Sequence[GovernedObligationRule],
    *,
    facets: Sequence[FacetSnapshot],
    intent_text: str | None,
) -> tuple[ObligationCandidateInput, ...]:
    facet_values = {(facet.facet_type, facet.value) for facet in facets}
    candidates: list[ObligationCandidateInput] = []
    for rule in rules:
        if rule.status != "governed":
            continue
        if not _rule_matches_facets(
            rule,
            facets=facets,
            facet_values=facet_values,
            intent_text=intent_text,
        ):
            continue
        metadata = _candidate_metadata_for_rule(rule)
        candidates.append(
            ObligationCandidateInput(
                candidate_id=f"rule:{rule.rule_id}",
                family=rule.rule_family,
                obligation_text=rule.obligation_text,
                source_class=SourceClass.GOVERNED_RULE,
                source_ref=f"rule://{_slug(rule.rule_id)}@{_slug(rule.rule_version)}",
                owner=rule.owner,
                scope=rule.scope,
                authority_profile=rule.authority_profile,
                temporal_window=rule.temporal_window,
                remedy_path=rule.remedy_path,
                priority_hint=rule.priority_ceiling,
                authority_allowance_passed=rule.authority_allowance_passed,
                admissibility_passed=rule.admissibility_passed,
                current_run_relevance_passed=rule.current_run_relevance_passed,
                material_public_risk_passed=rule.material_public_risk_passed,
                marginal_assurance_value=rule.marginal_assurance_value,
                expected_cost=rule.expected_cost,
                degradation_risk=rule.degradation_risk,
                reviewer_burden_minutes=rule.reviewer_burden_minutes,
                complexity_cost=rule.complexity_cost,
                lineage_refs=rule.lineage_refs,
                deadline_at=rule.deadline_at,
                escalation_owner=rule.escalation_owner or rule.owner,
                metadata={
                    "rule_version": rule.rule_version,
                    "logic_hash": rule.logic_hash,
                    "evidence_basis": rule.evidence_basis,
                    "public_revalidation_effect": rule.public_revalidation_effect,
                    **metadata,
                },
            )
        )
    return tuple(candidates)


def _rule_matches_facets(
    rule: GovernedObligationRule,
    *,
    facets: Sequence[FacetSnapshot],
    facet_values: set[tuple[str, str]],
    intent_text: str | None,
) -> bool:
    logic = _model_mapping(rule.logic)
    if _has_structured_facet_pattern(logic):
        return _structured_pattern_matches(
            logic,
            facets=facets,
            intent_text=intent_text,
        )
    for facet_type, value in rule.required_facets.items():
        if (facet_type, value) not in facet_values:
            return False
    return True


def _has_structured_facet_pattern(logic: Mapping[str, Any]) -> bool:
    return any(
        key in logic
        for key in (
            "facet_match_all",
            "facet_match_any",
            "claim_text_contains_any",
            "geography_predicate_eq",
            "population_predicate_eq",
        )
    )


def _structured_pattern_matches(
    logic: Mapping[str, Any],
    *,
    facets: Sequence[FacetSnapshot],
    intent_text: str | None,
) -> bool:
    by_type = {facet.facet_type: facet.value for facet in facets}
    all_predicates = _sequence_of_mappings(logic.get("facet_match_all"))
    any_predicates = _sequence_of_mappings(logic.get("facet_match_any"))
    if any(
        not _facet_predicate_matches(predicate, by_type=by_type)
        for predicate in all_predicates
    ):
        return False
    if any_predicates and not any(
        _facet_predicate_matches(predicate, by_type=by_type)
        for predicate in any_predicates
    ):
        return False
    geography = _text_or_none(logic.get("geography_predicate_eq"))
    if geography and by_type.get("geography_predicate") != geography:
        return False
    population = _text_or_none(logic.get("population_predicate_eq"))
    if population and by_type.get("population_predicate") != population:
        return False
    text_needles = _text_tuple(logic.get("claim_text_contains_any"))
    if text_needles:
        haystack = (intent_text or "").casefold()
        if not any(needle.casefold() in haystack for needle in text_needles):
            return False
    return True


def _facet_predicate_matches(
    predicate: Mapping[str, Any],
    *,
    by_type: Mapping[str, str],
) -> bool:
    facet_type = _text_or_none(predicate.get("facet_type"))
    if not facet_type:
        return False
    actual = by_type.get(facet_type)
    if actual is None:
        return False
    value_eq = _text_or_none(predicate.get("value_eq"))
    if value_eq is not None and actual != value_eq:
        return False
    value_in = _text_tuple(predicate.get("value_in"))
    return not (value_in and actual not in value_in)


def _candidate_metadata_for_rule(rule: GovernedObligationRule) -> dict[str, Any]:
    logic = _model_mapping(rule.logic)
    metadata = dict(rule.metadata)
    for key in (
        "annotation_obligation_id",
        "case_refs",
        "data_family",
        "evidence_family",
        "generated_from_facets",
        "legacy_evidence_family_alias",
        "required_evidence_constructs",
        "required_evidence_family",
        "vertical_rule",
    ):
        if key in logic and key not in metadata:
            metadata[key] = logic[key]
    if "required_evidence_family" in metadata and "evidence_family" not in metadata:
        metadata["evidence_family"] = metadata["required_evidence_family"]
    if "evidence_family" in metadata and "data_family" not in metadata:
        metadata["data_family"] = metadata["evidence_family"]
    return metadata


def _ledger_entry(
    candidate: ObligationCandidateInput,
    *,
    index: int,
    observed_at: datetime,
) -> CandidateLedgerEntry:
    ceiling, ceiling_reason = _source_ceiling(candidate)
    effective_priority = _cap_priority(candidate.priority_hint or ceiling, ceiling)
    blockers = _promotion_blockers(
        candidate,
        effective_priority=effective_priority,
        ceiling_reason=ceiling_reason,
    )
    return CandidateLedgerEntry(
        ledger_entry_id=f"candidate-ledger-{index:06d}-{_slug(candidate.candidate_id)}",
        candidate_id=candidate.candidate_id,
        family=_canonical_token(candidate.family),
        obligation_text=candidate.obligation_text,
        source_class=candidate.source_class,
        source_ref=candidate.source_ref,
        owner=candidate.owner,
        scope=_canonical_token(candidate.scope),
        authority_profile=_canonical_token(candidate.authority_profile),
        temporal_window=_canonical_token(candidate.temporal_window),
        remedy_path=_canonical_token(candidate.remedy_path),
        bundle_key=_bundle_key(candidate),
        priority_hint=candidate.priority_hint,
        source_ceiling=ceiling,
        effective_priority=effective_priority,
        ceiling_reason=ceiling_reason,
        promotion_blockers=blockers,
        authority_allowance_passed=candidate.authority_allowance_passed,
        admissibility_passed=candidate.admissibility_passed,
        current_run_relevance_passed=candidate.current_run_relevance_passed,
        material_public_risk_passed=candidate.material_public_risk_passed,
        marginal_assurance_value=candidate.marginal_assurance_value,
        expected_cost=candidate.expected_cost,
        degradation_risk=candidate.degradation_risk,
        reviewer_burden_minutes=candidate.reviewer_burden_minutes,
        complexity_cost=candidate.complexity_cost,
        lineage_refs=candidate.lineage_refs,
        deadline_at=candidate.deadline_at,
        escalation_owner=candidate.escalation_owner,
        competence_ref=candidate.competence_ref,
        time_scope_ref=candidate.time_scope_ref,
        claim_ref=candidate.claim_ref,
        material=candidate.material,
        authority_envelope_ref=candidate.authority_envelope_ref,
        producer_validation_ref=candidate.producer_validation_ref,
        observed_at=observed_at,
        metadata=candidate.metadata,
    )


def _source_ceiling(candidate: ObligationCandidateInput) -> tuple[PriorityClass, str]:
    match candidate.source_class:
        case SourceClass.GOVERNED_RULE:
            if candidate.priority_hint is PriorityClass.AUTHORITY_LEVEL_MANDATORY:
                return (
                    PriorityClass.AUTHORITY_LEVEL_MANDATORY,
                    "governed_rule_authority_level_mandatory_ceiling",
                )
            return PriorityClass.MANDATORY, "governed_rule_mandatory_ceiling"
        case SourceClass.LEGAL_REQUIREMENT:
            if candidate.competence_ref and candidate.time_scope_ref:
                return (
                    PriorityClass.AUTHORITY_LEVEL_MANDATORY,
                    "legal_requirement_competence_time_scope_proved",
                )
            return PriorityClass.REVIEW_REQUIRED, "legal_requirement_proof_missing"
        case SourceClass.DETERMINISTIC_CRITIC:
            return PriorityClass.CONDITIONAL, "deterministic_critic_conditional_ceiling"
        case SourceClass.PRODUCER_BLOCKER:
            return PriorityClass.MANDATORY, "producer_blocker_mandatory_in_affected_scope"
        case SourceClass.HISTORICAL_FAILURE:
            return PriorityClass.REVIEW_REQUIRED, "historical_failure_review_required_ceiling"
        case SourceClass.LLM_CANDIDATE:
            return PriorityClass.CANDIDATE, "llm_candidate_candidate_only_ceiling"
        case SourceClass.LLM_CRITIC_CONSENSUS:
            return (
                PriorityClass.REVIEW_REQUIRED,
                "llm_critic_consensus_review_required_ceiling",
            )
        case SourceClass.HUMAN_REVIEWER:
            if candidate.authority_envelope_ref and candidate.priority_hint in {
                PriorityClass.AUTHORITY_LEVEL_MANDATORY,
                PriorityClass.MANDATORY,
            }:
                return (
                    candidate.priority_hint,
                    "human_reviewer_authority_envelope_backed_ceiling",
                )
            return PriorityClass.REVIEW_REQUIRED, "human_reviewer_review_required_ceiling"
        case SourceClass.PUBLIC_CONTESTATION:
            if candidate.material and candidate.claim_ref:
                return (
                    PriorityClass.CONDITIONAL,
                    "public_contestation_material_claim_linked_ceiling",
                )
            return PriorityClass.REVIEW_REQUIRED, "public_contestation_review_required_ceiling"


def _cap_priority(priority: PriorityClass, ceiling: PriorityClass) -> PriorityClass:
    if _PRIORITY_RANK[priority] < _PRIORITY_RANK[ceiling]:
        return ceiling
    return priority


def _promotion_blockers(
    candidate: ObligationCandidateInput,
    *,
    effective_priority: PriorityClass,
    ceiling_reason: str,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if ceiling_reason == "legal_requirement_proof_missing":
        blockers.append("legal_requirement_proof_missing")
    if not candidate.authority_allowance_passed:
        blockers.append("authority_allowance_failed")
    if not candidate.admissibility_passed:
        blockers.append("legal_privacy_admissibility_failed")
    if not candidate.current_run_relevance_passed:
        blockers.append("current_run_relevance_failed")
    if not candidate.material_public_risk_passed:
        blockers.append("material_public_risk_failed")
    if effective_priority is PriorityClass.CANDIDATE:
        blockers.append("source_ceiling_candidate_not_blocking")
    if effective_priority is PriorityClass.OPTIONAL:
        blockers.append("source_ceiling_optional_not_blocking")
    return tuple(dict.fromkeys(blockers))


def _bundle_ledger(
    candidate_ledger: Sequence[CandidateLedgerEntry],
) -> tuple[ObligationBundle, ...]:
    groups: dict[tuple[str, str, str, str, str], list[CandidateLedgerEntry]] = defaultdict(list)
    for entry in candidate_ledger:
        groups[_key_tuple(entry.bundle_key)].append(entry)

    bundles: list[ObligationBundle] = []
    for key_tuple in sorted(groups):
        entries = groups[key_tuple]
        key = entries[0].bundle_key
        sorted_entries = sorted(
            entries,
            key=lambda entry: (
                _PRIORITY_RANK[entry.effective_priority],
                -entry.marginal_assurance_value,
                entry.expected_cost + entry.degradation_risk + entry.reviewer_burden_minutes,
                entry.ledger_entry_id,
            ),
        )
        canonical = sorted_entries[0]
        candidate_refs = _unique_sorted(entry.candidate_id for entry in entries)
        ledger_refs = _unique_sorted(entry.ledger_entry_id for entry in entries)
        source_classes = tuple(
            SourceClass(value) for value in sorted({entry.source_class.value for entry in entries})
        )
        lineage_refs = _unique_sorted(
            lineage_ref for entry in entries for lineage_ref in entry.lineage_refs
        )
        dominated = tuple(ref for ref in candidate_refs if ref != canonical.candidate_id)
        bundles.append(
            ObligationBundle(
                bundle_id=f"bundle-{_slug('|'.join(key_tuple))}",
                bundle_key=key,
                canonical_obligation_text=canonical.obligation_text,
                canonical_priority=canonical.effective_priority,
                child_count=len(entries),
                candidate_refs=candidate_refs,
                ledger_entry_refs=ledger_refs,
                source_classes=source_classes,
                source_ceiling_summary={
                    entry.candidate_id: entry.source_ceiling.value for entry in entries
                },
                lineage_refs=lineage_refs,
                dominated_candidate_refs=dominated,
                dominance_reason=(
                    "highest_priority_then_marginal_assurance_value_then_lowest_burden"
                ),
                marginal_assurance_value=max(entry.marginal_assurance_value for entry in entries),
                expected_cost=min(entry.expected_cost for entry in entries),
                degradation_risk=min(entry.degradation_risk for entry in entries),
                reviewer_burden_minutes=min(entry.reviewer_burden_minutes for entry in entries),
                complexity_cost=min(entry.complexity_cost for entry in entries),
                deadline_binding=_deadline_binding(entries),
                metadata=_bundle_metadata(canonical, entries),
            )
        )
    return tuple(bundles)


def _bundle_metadata(
    canonical: CandidateLedgerEntry,
    entries: Sequence[CandidateLedgerEntry],
) -> dict[str, Any]:
    metadata = dict(canonical.metadata)
    metadata["candidate_metadata_refs"] = {
        entry.candidate_id: dict(entry.metadata)
        for entry in entries
        if entry.metadata
    }
    return {key: value for key, value in metadata.items() if value not in ({}, [], ())}


def _deadline_binding(entries: Sequence[CandidateLedgerEntry]) -> DeadlineBinding:
    owner = entries[0].owner
    escalation_owner = entries[0].escalation_owner or entries[0].owner
    dated = [entry.deadline_at for entry in entries if entry.deadline_at is not None]
    deadline = min(dated) if dated else None
    if deadline is not None:
        for entry in entries:
            if entry.deadline_at == deadline:
                owner = entry.owner
                escalation_owner = entry.escalation_owner or entry.owner
                break
    return DeadlineBinding(
        owner=owner,
        escalation_owner=escalation_owner,
        deadline_at=deadline,
        source_refs=_unique_sorted(entry.source_ref for entry in entries),
    )


def _promote_frontier(
    bundle_ledger: Sequence[ObligationBundle],
    *,
    candidate_ledger: Sequence[CandidateLedgerEntry],
    budget: ComplexityBudget,
    observed_at: datetime,
) -> tuple[tuple[FrontierItem, ...], tuple[DeferredObligationRecord, ...]]:
    entries_by_bundle_id = {
        bundle.bundle_id: [
            entry
            for entry in candidate_ledger
            if _key_tuple(entry.bundle_key) == _key_tuple(bundle.bundle_key)
        ]
        for bundle in bundle_ledger
    }
    eligible: list[ObligationBundle] = []
    visibility_records: list[DeferredObligationRecord] = []

    for bundle in bundle_ledger:
        entries = entries_by_bundle_id[bundle.bundle_id]
        blocker = _bundle_blocker(entries)
        if blocker is not None:
            visibility_records.append(
                _visibility_record(bundle, blocker, observed_at=observed_at)
            )
            continue
        if bundle.canonical_priority not in _FRONTIER_PRIORITIES:
            visibility_records.append(
                _visibility_record(
                    bundle,
                    "source_ceiling_candidate_not_blocking",
                    observed_at=observed_at,
                )
            )
            continue
        eligible.append(bundle)

    eligible.sort(
        key=lambda bundle: (
            _PRIORITY_RANK[bundle.canonical_priority],
            -bundle.marginal_assurance_value,
            bundle.expected_cost + bundle.degradation_risk + bundle.reviewer_burden_minutes,
            bundle.bundle_id,
        )
    )

    frontier: list[FrontierItem] = []
    total_complexity = 0.0
    total_reviewer_burden = 0.0
    for bundle in eligible:
        would_count = len(frontier) + 1
        would_complexity = total_complexity + bundle.complexity_cost
        would_reviewer_burden = total_reviewer_burden + bundle.reviewer_burden_minutes
        if (
            would_count > budget.max_frontier_items
            or would_complexity > budget.max_total_complexity_cost
            or would_reviewer_burden > budget.max_reviewer_burden_minutes
        ):
            visibility_records.append(
                _visibility_record(
                    bundle,
                    "complexity_budget_exceeded",
                    observed_at=observed_at,
                )
            )
            continue
        frontier.append(
            FrontierItem(
                frontier_id=f"frontier-{len(frontier) + 1:03d}-{_slug(bundle.bundle_id)}",
                bundle_id=bundle.bundle_id,
                bundle_key=bundle.bundle_key,
                priority_class=bundle.canonical_priority,
                obligation_text=bundle.canonical_obligation_text,
                source_classes=bundle.source_classes,
                candidate_refs=bundle.candidate_refs,
                marginal_assurance_value=bundle.marginal_assurance_value,
                expected_cost=bundle.expected_cost,
                degradation_risk=bundle.degradation_risk,
                reviewer_burden_minutes=bundle.reviewer_burden_minutes,
                complexity_cost=bundle.complexity_cost,
                deadline_binding=bundle.deadline_binding,
                metadata=bundle.metadata,
            )
        )
        total_complexity = would_complexity
        total_reviewer_burden = would_reviewer_burden

    visibility_records.sort(key=lambda record: (record.reason, record.bundle_id))
    return tuple(frontier), tuple(visibility_records)


def _bundle_blocker(entries: Sequence[CandidateLedgerEntry]) -> str | None:
    eligible_entries = [
        entry
        for entry in entries
        if not entry.promotion_blockers and entry.effective_priority in _FRONTIER_PRIORITIES
    ]
    if eligible_entries:
        return None
    blockers = {blocker for entry in entries for blocker in entry.promotion_blockers}
    for blocker in _BLOCKER_PRECEDENCE:
        if blocker in blockers:
            return blocker
    return "source_ceiling_candidate_not_blocking"


def _visibility_record(
    bundle: ObligationBundle,
    reason: str,
    *,
    observed_at: datetime,
) -> DeferredObligationRecord:
    return DeferredObligationRecord(
        bundle_id=bundle.bundle_id,
        bundle_key=bundle.bundle_key,
        state=DeferredState.REJECTED if reason in _REJECTING_BLOCKERS else DeferredState.DEFERRED,
        reason=reason,
        owner=bundle.deadline_binding.owner,
        observed_at=observed_at,
        reopen_trigger=_reopen_trigger(reason),
        candidate_refs=bundle.candidate_refs,
        priority_class=bundle.canonical_priority,
    )


def _reopen_trigger(reason: str) -> str:
    match reason:
        case "legal_requirement_proof_missing":
            return "reopen when competence, time, and scope proof refs are attached"
        case "authority_allowance_failed":
            return "reopen only with a new authority allowance envelope"
        case "legal_privacy_admissibility_failed":
            return "reopen after legal/privacy admissibility repair"
        case "current_run_relevance_failed":
            return "reopen when current-run evidence binds this obligation to the case"
        case "material_public_risk_failed":
            return "reopen when material public risk is established"
        case "complexity_budget_exceeded":
            return "reopen when budget changes or higher-MAV frontier item is resolved"
        case _:
            return "reopen when source class gains producer validation or governed authority"


def _telemetry(
    *,
    candidate_ledger: Sequence[CandidateLedgerEntry],
    bundle_ledger: Sequence[ObligationBundle],
    blocking_frontier: Sequence[FrontierItem],
    deferred_or_rejected: Sequence[DeferredObligationRecord],
) -> dict[str, Any]:
    candidate_count = len(candidate_ledger)
    frontier_count = len(blocking_frontier)
    deferred_count = len(deferred_or_rejected)
    llm_frontier_count = sum(
        1 for item in blocking_frontier if SourceClass.LLM_CANDIDATE in item.source_classes
    )
    collapsed_lineage_count = sum(
        max(0, bundle.child_count - len(bundle.lineage_refs)) for bundle in bundle_ledger
    )
    non_frontier_count = max(0, len(bundle_ledger) - frontier_count)
    return {
        "candidate_count": candidate_count,
        "bundle_count": len(bundle_ledger),
        "active_frontier_count": frontier_count,
        "candidate_to_blocking_ratio": (
            float(candidate_count) / float(frontier_count)
            if frontier_count
            else float(candidate_count)
        ),
        "silent_drop_rate": 0.0,
        "llm_authority_leakage_rate": (
            float(llm_frontier_count) / float(frontier_count) if frontier_count else 0.0
        ),
        "deferred_visibility_rate": (
            float(deferred_count) / float(non_frontier_count) if non_frontier_count else 1.0
        ),
        "rejected_reason_coverage": (
            sum(1 for record in deferred_or_rejected if record.reason) / float(deferred_count)
            if deferred_count
            else 1.0
        ),
        "lineage_collapse_count": collapsed_lineage_count,
        "pattern_refs": ["P02", "P13", "P14", "P15"],
    }


def _assert_no_llm_authority_leakage(graph: ObligationGraph) -> None:
    leaked = [
        item.frontier_id
        for item in graph.blocking_frontier
        if SourceClass.LLM_CANDIDATE in item.source_classes
    ]
    if leaked:
        raise ObligationGraphCompileError(
            "llm_authority_leakage",
            "llm_candidate source class cannot enter the blocking frontier.",
        )


def _bundle_key(candidate: ObligationCandidateInput) -> BundleKey:
    return BundleKey(
        family=_canonical_token(candidate.family),
        scope=_canonical_token(candidate.scope),
        authority_profile=_canonical_token(candidate.authority_profile),
        temporal_window=_canonical_token(candidate.temporal_window),
        remedy_path=_canonical_token(candidate.remedy_path),
    )


def _key_tuple(key: BundleKey) -> tuple[str, str, str, str, str]:
    return (
        key.family,
        key.scope,
        key.authority_profile,
        key.temporal_window,
        key.remedy_path,
    )


def _coerce_facet(value: FacetSnapshot | Mapping[str, Any]) -> FacetSnapshot:
    return value if isinstance(value, FacetSnapshot) else FacetSnapshot.model_validate(value)


def _coerce_rule(value: GovernedObligationRule | Mapping[str, Any]) -> GovernedObligationRule:
    if isinstance(value, GovernedObligationRule):
        return value
    row = _model_mapping(value)
    if "obligation_text" not in row and {"rule_id", "logic", "scope"} <= set(row):
        row = _adapt_obligation_rule_catalog_row(row)
    return GovernedObligationRule.model_validate(row)


def _coerce_candidate(
    value: ObligationCandidateInput | Mapping[str, Any],
) -> ObligationCandidateInput:
    return (
        value
        if isinstance(value, ObligationCandidateInput)
        else ObligationCandidateInput.model_validate(value)
    )


def _coerce_budget(value: ComplexityBudget | Mapping[str, Any] | None) -> ComplexityBudget:
    if value is None:
        return ComplexityBudget()
    return value if isinstance(value, ComplexityBudget) else ComplexityBudget.model_validate(value)


def _adapt_obligation_rule_catalog_row(row: Mapping[str, Any]) -> dict[str, Any]:
    rule_id = _required_text(row.get("rule_id"))
    family = _enum_value(row.get("rule_family") or row.get("family"))
    logic = _model_mapping(row.get("logic"))
    predicate = _text_or_none(logic.get("predicate")) or rule_id
    scope_payload = _model_mapping(row.get("scope"))
    authority_level = _text_or_none(row.get("authority_level")) or "governed"
    authority_profiles = _text_tuple(scope_payload.get("authority_profiles"))
    status = _enum_value(row.get("status") or "governed")
    public_effect = _enum_value(row.get("public_revalidation_effect"))
    source_refs = _text_tuple(row.get("source_refs"))
    provenance_refs = _text_tuple(row.get("provenance_refs"))
    taxonomy_refs = _text_tuple(row.get("taxonomy_refs"))
    lineage_refs = tuple(dict.fromkeys([*source_refs, *provenance_refs, *taxonomy_refs]))
    required_facets = _model_mapping(logic.get("required_facets"))
    evidence_family = _text_or_none(
        logic.get("required_evidence_family") or logic.get("evidence_family")
    )
    vertical_rule = bool(logic.get("vertical_rule"))
    priority = (
        PriorityClass.AUTHORITY_LEVEL_MANDATORY
        if authority_level == "production"
        and not vertical_rule
        else PriorityClass.MANDATORY
    )
    if vertical_rule:
        priority = PriorityClass.AUTHORITY_LEVEL_MANDATORY
    return {
        "rule_id": rule_id,
        "rule_family": family,
        "rule_version": _required_text(row.get("rule_version")),
        "logic_hash": _required_text(row.get("logic_hash")),
        "owner": _required_text(row.get("owner")),
        "scope": _scope_label(scope_payload),
        "authority_level": authority_level,
        "evidence_basis": "; ".join(_text_tuple(row.get("evidence_basis")))
        or "governed_rule_catalog",
        "status": status,
        "public_revalidation_effect": public_effect,
        "obligation_text": (
            _text_or_none(logic.get("obligation_text") or logic.get("reviewer_notes"))
            or f"Comply with governed {family} obligation rule {rule_id}: "
            f"{predicate.replace('_', ' ')}."
        ),
        "authority_profile": authority_profiles[0] if authority_profiles else authority_level,
        "temporal_window": _text_or_none(scope_payload.get("temporal_window"))
        or "case_lifecycle",
        "remedy_path": evidence_family or _remedy_path_for_rule(rule_id),
        "logic": logic,
        "metadata": {
            key: logic[key]
            for key in (
                "annotation_obligation_id",
                "case_refs",
                "data_family",
                "evidence_family",
                "generated_from_facets",
                "legacy_evidence_family_alias",
                "required_evidence_constructs",
                "required_evidence_family",
                "vertical_rule",
            )
            if key in logic
        },
        "required_facets": {
            _required_text(key): _required_text(value)
            for key, value in required_facets.items()
        },
        "priority_ceiling": priority,
        "authority_allowance_passed": True,
        "admissibility_passed": True,
        "current_run_relevance_passed": True,
        "material_public_risk_passed": True,
        "marginal_assurance_value": 20.0 if vertical_rule else 1.0,
        "expected_cost": 0.0,
        "degradation_risk": 0.0,
        "reviewer_burden_minutes": 0.0,
        "complexity_cost": 1.0,
        "lineage_refs": lineage_refs,
        "escalation_owner": _text_or_none(row.get("owner")),
    }


def _model_mapping(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump(mode="python")
        except TypeError:
            dumped = model_dump()
        if isinstance(dumped, Mapping):
            return dict(dumped)
    return {}


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return _required_text(raw)


def _text_or_none(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    raw = getattr(value, "value", value)
    return str(raw).strip() or None


def _text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values: Iterable[object] = (value,)
    elif isinstance(value, Iterable):
        values = value
    else:
        values = (value,)
    refs: list[str] = []
    for item in values:
        text = _text_or_none(item)
        if text and text not in refs:
            refs.append(text)
    return tuple(refs)


def _sequence_of_mappings(value: object) -> tuple[Mapping[str, Any], ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, Iterable) and not isinstance(value, str):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _scope_label(scope_payload: Mapping[str, Any]) -> str:
    jurisdictions = _text_tuple(scope_payload.get("jurisdictions")) or ("global",)
    domains = _text_tuple(scope_payload.get("policy_domains")) or ("universal",)
    return "/".join((*domains, *jurisdictions))


def _remedy_path_for_rule(rule_id: str) -> str:
    parts = [part for part in re.split(r"[.:/]+", rule_id) if part]
    if len(parts) >= 3 and parts[0] == "obligation":
        return ".".join(parts[2:])
    return parts[-1] if parts else "governed_rule"


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _required_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise ObligationGraphCompileError("required_text_missing", "Required text field is empty.")
    return text


def _canonical_token(value: str) -> str:
    text = _required_text(value).casefold().replace("::", ":")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_.:/-]+", "_", text)
    return text.strip("_") or "unknown"


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value).strip())
    return text.strip("-").casefold() or "unknown"


def _unique_sorted(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value).strip()}))


__all__ = [
    "ObligationGraphCompileError",
    "compile_obligation_graph",
    "obligation_graph_audit_surface",
    "write_obligation_graph_artifact",
]
