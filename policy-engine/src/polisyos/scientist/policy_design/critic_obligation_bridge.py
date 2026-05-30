"""Bridge critic consensus into review-required obligation candidates."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from polisyos.obligation_graph import (
    FacetSnapshot,
    ObligationCandidateInput,
    PriorityClass,
    SourceClass,
)
from polisyos.scientist.policy_design.critic_contracts import CriticEnsembleReport
from polisyos.scientist.policy_design.critic_ensemble import project_critic_consensus
from polisyos.scientist.policy_design.formulator import (
    FormulatorCandidate,
    LLMFormulatorOutput,
    mapping_from_any,
    sequence_from_any,
)


def critic_consensus_to_obligation_candidates(
    *,
    formulator_output: LLMFormulatorOutput,
    critic_report: CriticEnsembleReport,
    facets: Sequence[FacetSnapshot | Mapping[str, Any]] | Mapping[str, Any],
    intent_text: str,
    authority_profile_ref: str,
    consensus_threshold: int = 6,
) -> tuple[ObligationCandidateInput, ...]:
    """Convert high-consensus critic support into bounded obligation candidates.

    The emitted candidates are review-required signals. They are visible to the
    obligation graph, but their source ceiling prevents them from becoming
    mandatory production authority without a later human admission path.
    """

    candidates_by_id = {
        candidate.candidate_id: candidate for candidate in formulator_output.candidates
    }
    consensus = project_critic_consensus(
        critic_report,
        candidate_ids=tuple(candidates_by_id),
        consensus_threshold=consensus_threshold,
    )
    scope = _scope_from_facets(facets)
    temporal_window = _temporal_window_from_facets(facets)
    emitted: list[ObligationCandidateInput] = []
    for row in consensus.candidates:
        candidate = candidates_by_id.get(row.candidate_id)
        if candidate is None or _speculation_flagged(critic_report, candidate.candidate_id):
            continue
        emitted.append(
            ObligationCandidateInput(
                candidate_id=f"critic-consensus:{_slug(candidate.candidate_id)}",
                family=_family_for_candidate(candidate),
                obligation_text=_obligation_text(candidate, intent_text=intent_text),
                source_class=SourceClass.LLM_CRITIC_CONSENSUS,
                source_ref=f"critic-consensus://{_slug(critic_report.run_id)}/{_slug(candidate.candidate_id)}",
                owner="team-policy-semantics",
                scope=scope,
                authority_profile=authority_profile_ref,
                temporal_window=temporal_window,
                remedy_path=_remedy_path(candidate),
                priority_hint=PriorityClass.REVIEW_REQUIRED,
                authority_allowance_passed=True,
                admissibility_passed=True,
                current_run_relevance_passed=True,
                material_public_risk_passed=True,
                marginal_assurance_value=float(row.support_count),
                expected_cost=0.0,
                degradation_risk=0.0,
                reviewer_burden_minutes=15.0,
                complexity_cost=1.0,
                lineage_refs=(candidate.candidate_id, *row.verdict_refs),
                escalation_owner="team-policy-semantics",
                metadata={
                    "formulator_candidate_ref": candidate.candidate_id,
                    "critic_verdict_refs": list(row.verdict_refs),
                    "critic_verdict_types": list(row.verdict_types),
                    "support_count": row.support_count,
                    "consensus_threshold": row.consensus_threshold,
                    "prompt_fingerprint": formulator_output.prompt_fingerprint,
                    "admission_state": "candidate_unverified",
                    "candidate_kind": "candidate_capability",
                    "construct_ref": _candidate_construct_ref(candidate),
                    "capability_candidate_ref": (
                        f"candidate-capability:{_slug(candidate.candidate_id)}"
                    ),
                    "may_not_use_for": [
                        "production_closeout_authority",
                        "claim_evidence_authority",
                        "producer_domain_truth",
                        "data_authority",
                        "legal_authority",
                        "method_authority",
                        "participation_authority",
                    ],
                    "next_required_steps": [
                        "human_reviewer_admission_required",
                        "producer_backed_admission_required",
                    ],
                },
            )
        )
    return tuple(emitted)


def _speculation_flagged(report: CriticEnsembleReport, candidate_id: str) -> bool:
    return any(
        verdict.verdict == "flag_speculation"
        and candidate_id in verdict.target_candidate_ids
        for verdict in report.verdicts
    )


def _family_for_candidate(candidate: FormulatorCandidate) -> str:
    if candidate.kind == "method_need":
        return "method"
    if candidate.kind == "missing_question":
        return "participation"
    if candidate.kind == "risk":
        return "implementation"
    text = candidate.text.casefold()
    if "legal" in text or "competence" in text:
        return "legal"
    if "data" in text or "source" in text or "registry" in text:
        return "data"
    if "fiscal" in text or "budget" in text:
        return "fiscal"
    if "equity" in text or "exclusion" in text:
        return "equity"
    return "implementation"


def _obligation_text(candidate: FormulatorCandidate, *, intent_text: str) -> str:
    prefix = "Review critic-consensus candidate before publication"
    if candidate.kind == "obligation":
        return f"{prefix}: {candidate.text}"
    return f"{prefix} for {_clip(intent_text, 120)}: {candidate.text}"


def _remedy_path(candidate: FormulatorCandidate) -> str:
    if candidate.method_need_kind:
        return candidate.method_need_kind
    if candidate.question_use:
        return f"answer_{candidate.question_use}"
    if candidate.risk_tags:
        return f"review_{candidate.risk_tags[0]}"
    if candidate.obligation_refs:
        return f"review_{candidate.obligation_refs[0]}"
    return f"review_{candidate.kind}"


def _candidate_construct_ref(candidate: FormulatorCandidate) -> str | None:
    for key in ("construct_ref", "construct", "target_construct"):
        value = candidate.metadata.get(key)
        if isinstance(value, str) and value.strip():
            text = value.strip()
            return text if text.startswith("construct:") else f"construct:{_slug(text)}"
    if candidate.method_need_kind:
        return f"construct:{_slug(candidate.method_need_kind)}"
    if candidate.field_name:
        return f"construct:{_slug(candidate.field_name)}"
    return None


def _scope_from_facets(
    facets: Sequence[FacetSnapshot | Mapping[str, Any]] | Mapping[str, Any],
) -> str:
    rows = _facet_rows(facets)
    geography = _first_facet_value(rows, "geography_predicate")
    population = _first_facet_value(rows, "population_predicate")
    if geography and population:
        return f"{geography}:{population}"
    return geography or population or "case_scope"


def _temporal_window_from_facets(
    facets: Sequence[FacetSnapshot | Mapping[str, Any]] | Mapping[str, Any],
) -> str:
    return _first_facet_value(_facet_rows(facets), "time_predicate") or "case_lifecycle"


def _facet_rows(
    facets: Sequence[FacetSnapshot | Mapping[str, Any]] | Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    if isinstance(facets, Mapping):
        snapshots = facets.get("snapshots")
        if snapshots is not None:
            return tuple(mapping_from_any(row) for row in sequence_from_any(snapshots))
        return tuple(
            {"facet_type": str(key), "value": value}
            for key, value in facets.items()
        )
    return tuple(mapping_from_any(row) for row in facets)


def _first_facet_value(rows: Sequence[Mapping[str, Any]], facet_type: str) -> str | None:
    for row in rows:
        if str(row.get("facet_type") or "") == facet_type:
            value = str(row.get("value") or "").strip()
            if value:
                return value
    return None


def _slug(value: object) -> str:
    text = re.sub(r"[^a-zA-Z0-9_.:-]+", "-", str(value).strip())
    return text.strip("-").casefold() or "unknown"


def _clip(text: str, limit: int) -> str:
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


__all__ = ["critic_consensus_to_obligation_candidates"]
