"""Claim argument, warrant, rebuttal, and deficit surfaces for Policy Design Cases."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from polisyos.runtime.quality.explanation_reliability import (
    evaluate_warrant_berl_reliability,
    warrant_berl_reliability_refs,
    warrant_requires_berl_reliability,
)

CLAIM_ARGUMENT_VALIDATION_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.claim_argument.validation.v1"
)
CLAIM_ARGUMENT_MAPPING_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.claim_argument.mapping.v1"
)
CLAIM_ARGUMENT_CONTRACT_ID = "policy_design_case.claim_argument_evidence_case.v1"
PRE_PUBLICATION_CHALLENGE_NODE_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.pre_publication_challenge_node.v1"
)

CLAIM_ARGUMENT_NODE_MAPPING = {
    "claim": {"sacm": "SACM.claim", "cae": "CAE.claim", "gsn": "goal"},
    "argument": {"sacm": "SACM.argument_reasoning", "cae": "CAE.argument", "gsn": "strategy"},
    "warrant": {"sacm": "SACM.asserted_inference", "cae": "CAE.warrant", "gsn": "justification"},
    "rebuttal": {"sacm": "SACM.defeated_claim", "cae": "CAE.rebuttal", "gsn": "away_goal"},
    "counter_evidence": {
        "sacm": "SACM.artifact_reference",
        "cae": "CAE.defeater",
        "gsn": "context",
    },
    "deficit": {
        "sacm": "SACM.assurance_deficit",
        "cae": "CAE.assumption_or_gap",
        "gsn": "assumption",
    },
    "requester_capture_challenge": {
        "sacm": "SACM.context",
        "cae": "CAE.challenge",
        "gsn": "context",
    },
    "blocker": {"sacm": "SACM.assurance_deficit", "cae": "CAE.blocker", "gsn": "undeveloped"},
}

_SURFACE_TOP_LEVEL_KEYS = {
    "argument": ("arguments", "argument_records", "claim_arguments"),
    "warrant": ("warrants", "warrant_records", "claim_warrants"),
    "rebuttal": ("rebuttals", "rebuttal_records", "claim_rebuttals"),
    "counter_evidence": (
        "counter_evidence",
        "counter_evidence_nodes",
        "counter_evidence_records",
        "counter_evidence_assessments",
    ),
    "deficit": (
        "assurance_deficits",
        "accepted_deficits",
        "deficits",
        "accepted_assurance_deficits",
    ),
    "requester_capture_challenge": (
        "requester_capture_challenges",
        "requester_capture_challenge_results",
        "challenge_results",
    ),
    "blocker": (
        "claim_argument_blockers",
        "blockers",
        "runtime_blockers",
        "authority_blockers",
    ),
}
_SURFACE_REF_KEYS = {
    "argument": ("argument_refs", "argument_ref", "argument_node_refs"),
    "warrant": ("warrant_refs", "warrant_ref", "warrant_node_refs"),
    "rebuttal": ("rebuttal_refs", "rebuttal_ref", "rebuttal_node_refs"),
    "counter_evidence": (
        "counter_evidence_refs",
        "counter_evidence_ref",
        "counter_evidence_node_refs",
    ),
    "deficit": (
        "assurance_deficit_refs",
        "accepted_deficit_refs",
        "deficit_refs",
        "accepted_assurance_deficit_refs",
    ),
    "requester_capture_challenge": (
        "requester_capture_challenge_refs",
        "requester_capture_challenge_ref",
        "challenge_result_refs",
    ),
    "blocker": ("blocker_refs", "blocker_ref", "claim_argument_blocker_refs"),
}
_SURFACE_ID_KEYS = {
    "argument": ("argument_id", "record_id", "node_id", "id", "cas_ref", "evidence_ref"),
    "warrant": ("warrant_id", "record_id", "node_id", "id", "cas_ref", "evidence_ref"),
    "rebuttal": ("rebuttal_id", "record_id", "node_id", "id", "cas_ref", "evidence_ref"),
    "counter_evidence": (
        "counter_evidence_id",
        "counterevidence_id",
        "record_id",
        "node_id",
        "id",
        "cas_ref",
        "evidence_ref",
    ),
    "deficit": ("deficit_id", "record_id", "node_id", "id", "cas_ref", "evidence_ref"),
    "requester_capture_challenge": (
        "challenge_id",
        "requester_capture_challenge_id",
        "record_id",
        "node_id",
        "id",
        "cas_ref",
        "evidence_ref",
    ),
    "blocker": ("blocker_id", "record_id", "node_id", "id", "cas_ref", "evidence_ref"),
}
_REQUIRED_SURFACES = (
    "argument",
    "warrant",
    "rebuttal",
    "counter_evidence",
    "deficit",
    "requester_capture_challenge",
)
_MISSING_CODES = {
    "argument": "policy_design_major_claim_argument_missing",
    "warrant": "policy_design_major_claim_warrant_missing",
    "rebuttal": "policy_design_major_claim_rebuttal_missing",
    "counter_evidence": "policy_design_major_claim_counter_evidence_missing",
    "deficit": "policy_design_major_claim_deficit_missing",
    "requester_capture_challenge": (
        "policy_design_requester_capture_challenge_missing"
    ),
}
_SEMANTIC_BINDING_MISSING_CODES = {
    "policy_design_major_claim_argument_missing": (
        "semantic_major_claim_argument_refs_missing"
    ),
    "policy_design_major_claim_warrant_missing": (
        "semantic_major_claim_warrant_refs_missing"
    ),
    "policy_design_major_claim_rebuttal_missing": (
        "semantic_major_claim_rebuttal_refs_missing"
    ),
    "policy_design_major_claim_counter_evidence_missing": (
        "semantic_major_claim_counter_evidence_refs_missing"
    ),
    "policy_design_major_claim_deficit_missing": (
        "semantic_major_claim_limitation_refs_missing"
    ),
}
_MISSING_MESSAGES = {
    "argument": "Major claims must cite an explicit argument strategy record.",
    "warrant": "Major claims must cite a warrant explaining why refs support the claim.",
    "rebuttal": "Major claims must cite a rebuttal assessment.",
    "counter_evidence": "Major claims must cite visible counter-evidence assessment nodes.",
    "deficit": "Major claims must expose an assurance-deficit surface, even when empty.",
    "requester_capture_challenge": (
        "Major claims must cite a requester-capture challenge result."
    ),
}
_SCIENTIST_CHALLENGE_REF_REQUIREMENTS = (
    (
        "policy_design_adversary",
        (
            "policy_design_adversary_refs",
            "policy_design_adversary_ref",
            "adversary_refs",
            "scenario_adversary_refs",
            "adversary_bundle_refs",
        ),
        "policy_design_challenge_policy_adversary_ref_missing",
        "Requester-capture challenges must cite Scientist policy-design adversary output.",
    ),
    (
        "policy_design_critic",
        (
            "policy_design_critic_refs",
            "policy_design_critic_ref",
            "critic_refs",
            "constraint_critic_refs",
            "constraint_critique_refs",
        ),
        "policy_design_challenge_policy_critic_ref_missing",
        "Requester-capture challenges must cite Scientist policy-design critic output.",
    ),
    (
        "policy_design_objectives",
        (
            "policy_design_objective_refs",
            "policy_design_objectives_refs",
            "policy_design_objective_ref",
            "objective_refs",
            "objectives_refs",
            "policy_evaluation_refs",
        ),
        "policy_design_challenge_policy_objectives_ref_missing",
        "Requester-capture challenges must cite Scientist policy-design objective output.",
    ),
    (
        "policy_design_search",
        (
            "policy_design_search_refs",
            "policy_design_search_ref",
            "search_refs",
            "hierarchical_search_refs",
            "parameter_search_refs",
            "pareto_frontier_refs",
        ),
        "policy_design_challenge_policy_search_ref_missing",
        "Requester-capture challenges must cite Scientist policy-design search output.",
    ),
    (
        "backtesting_adversarial",
        (
            "backtesting_adversarial_refs",
            "backtesting_adversarial_ref",
            "adversarial_backtesting_refs",
            "stress_test_report_refs",
            "challenge_suite_result_refs",
            "phase_d4_challenge_suite_refs",
        ),
        "policy_design_challenge_backtesting_adversarial_ref_missing",
        "Requester-capture challenges must cite adversarial backtesting output.",
    ),
)


@dataclass(frozen=True)
class ClaimArgumentIssue:
    """One deterministic claim-argument validation issue."""

    code: str
    claim_id: str | None
    field: str
    message: str
    evidence_ref: str | None = None
    severity: str = "error"

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "code": self.code,
            "severity": self.severity,
            "field": self.field,
            "message": self.message,
        }
        semantic_code = _SEMANTIC_BINDING_MISSING_CODES.get(self.code)
        if semantic_code:
            payload["semantic_binding_issue_code"] = semantic_code
        if self.claim_id is not None:
            payload["claim_id"] = self.claim_id
        if self.evidence_ref is not None:
            payload["evidence_ref"] = self.evidence_ref
        return payload


@dataclass(frozen=True)
class ClaimArgumentValidationResult:
    """Validated per-claim reasoning surfaces."""

    status: str
    major_claims: tuple[dict[str, Any], ...]
    issues: tuple[ClaimArgumentIssue, ...]

    def as_dict(self) -> dict[str, object]:
        issue_payloads = [issue.as_dict() for issue in self.issues]
        semantic_binding_issues = [
            {
                **dict(issue),
                "code": issue["semantic_binding_issue_code"],
                "claim_argument_issue_code": issue["code"],
            }
            for issue in issue_payloads
            if "semantic_binding_issue_code" in issue
        ]
        return {
            "schema_version": CLAIM_ARGUMENT_VALIDATION_SCHEMA_VERSION,
            "contract_id": CLAIM_ARGUMENT_CONTRACT_ID,
            "status": self.status,
            "summary": {
                "major_claim_count": len(self.major_claims),
                "issue_count": len(self.issues),
                "semantic_binding_issue_count": len(semantic_binding_issues),
            },
            "major_claims": list(self.major_claims),
            "issues": issue_payloads,
            "semantic_binding_issues": semantic_binding_issues,
        }


def build_pre_publication_challenge_node(
    *,
    challenge_id: str,
    claim_id: str,
    requester_preferred_conclusion: str | None,
    independent_analysis_conclusion: str,
    independent_alternative_analyses: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    policy_design_adversary_refs: list[str] | tuple[str, ...],
    policy_design_critic_refs: list[str] | tuple[str, ...],
    policy_design_objective_refs: list[str] | tuple[str, ...],
    policy_design_search_refs: list[str] | tuple[str, ...],
    backtesting_adversarial_refs: list[str] | tuple[str, ...],
    evidence_ref: str | None = None,
    runtime_event_ref: str | None = None,
    challenge_result: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a challenge node from Scientist adversarial policy-design outputs."""

    scientist_output_refs = {
        "policy_design_adversary_refs": _dedupe_texts(policy_design_adversary_refs),
        "policy_design_critic_refs": _dedupe_texts(policy_design_critic_refs),
        "policy_design_objective_refs": _dedupe_texts(policy_design_objective_refs),
        "policy_design_search_refs": _dedupe_texts(policy_design_search_refs),
        "backtesting_adversarial_refs": _dedupe_texts(backtesting_adversarial_refs),
    }
    adversarial_output_refs = _dedupe_texts(
        [
            ref
            for refs in scientist_output_refs.values()
            for ref in refs
        ]
    )
    alternatives = [
        dict(item)
        for item in independent_alternative_analyses
        if isinstance(item, Mapping)
    ]
    resolved_result = _text(challenge_result)
    if resolved_result is None:
        preferred = _text(requester_preferred_conclusion)
        independent = _text(independent_analysis_conclusion)
        minimum_alternatives = 2 if preferred is not None else 1
        meaningful_alternatives = sum(
            1
            for item in alternatives
            if _meaningful_alternative(item, preferred_conclusion=preferred)
        )
        resolved_result = (
            "passed"
            if independent is not None
            and _normalized_text(independent) != _normalized_text(preferred)
            and meaningful_alternatives >= minimum_alternatives
            and all(scientist_output_refs.values())
            else "failed"
        )
    node: dict[str, Any] = {
        "schema_version": PRE_PUBLICATION_CHALLENGE_NODE_SCHEMA_VERSION,
        "node_type": "requester_capture_challenge",
        "node_family": "pre_publication_challenge",
        "challenge_id": str(challenge_id),
        "claim_id": str(claim_id),
        "challenge_result": resolved_result,
        "requester_preferred_conclusion": (
            str(requester_preferred_conclusion)
            if requester_preferred_conclusion is not None
            else None
        ),
        "independent_analysis_conclusion": str(independent_analysis_conclusion),
        "independent_alternative_analyses": alternatives,
        "scientist_output_refs": scientist_output_refs,
        "adversarial_output_refs": adversarial_output_refs,
    }
    if evidence_ref is not None:
        node["evidence_ref"] = str(evidence_ref)
    if runtime_event_ref is not None:
        node["runtime_event_ref"] = str(runtime_event_ref)
    if metadata:
        node["metadata"] = dict(metadata)
    return node


def build_pre_publication_challenge_node_from_scientist_outputs(
    *,
    challenge_id: str,
    claim_id: str,
    requester_preferred_conclusion: str | None,
    independent_analysis_conclusion: str,
    independent_alternative_analyses: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    policy_design_adversary_output: object,
    policy_design_critic_output: object,
    policy_design_objectives_output: object,
    policy_design_search_output: object,
    backtesting_adversarial_output: object,
    evidence_ref: str | None = None,
    runtime_event_ref: str | None = None,
    challenge_result: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project existing Scientist challenge outputs into a Policy Design Case node."""

    return build_pre_publication_challenge_node(
        challenge_id=challenge_id,
        claim_id=claim_id,
        requester_preferred_conclusion=requester_preferred_conclusion,
        independent_analysis_conclusion=independent_analysis_conclusion,
        independent_alternative_analyses=independent_alternative_analyses,
        policy_design_adversary_refs=_scientist_output_refs(
            policy_design_adversary_output,
            preferred_fields=(
                "policy_design_adversary_ref",
                "adversary_bundle_ref",
                "scenario_adversary_ref",
                "scenario_bundle_ref",
            ),
        ),
        policy_design_critic_refs=_scientist_output_refs(
            policy_design_critic_output,
            preferred_fields=(
                "policy_design_critic_ref",
                "critic_ref",
                "constraint_critic_ref",
                "constraint_critique_ref",
            ),
        ),
        policy_design_objective_refs=_scientist_output_refs(
            policy_design_objectives_output,
            preferred_fields=(
                "policy_design_objective_ref",
                "policy_design_objectives_ref",
                "objective_ref",
                "objectives_ref",
                "policy_evaluation_ref",
            ),
        ),
        policy_design_search_refs=_scientist_output_refs(
            policy_design_search_output,
            preferred_fields=(
                "policy_design_search_ref",
                "search_ref",
                "hierarchical_search_ref",
                "parameter_search_ref",
                "pareto_frontier_ref",
                "shared_frontier",
            ),
        ),
        backtesting_adversarial_refs=_scientist_output_refs(
            backtesting_adversarial_output,
            preferred_fields=(
                "backtesting_adversarial_ref",
                "adversarial_backtesting_ref",
                "stress_test_report_ref",
                "challenge_suite_result_ref",
                "phase_d4_challenge_suite_ref",
                "stress_test_report",
            ),
        ),
        evidence_ref=evidence_ref,
        runtime_event_ref=runtime_event_ref,
        challenge_result=challenge_result,
        metadata={
            "projection_source": "scientist_policy_design_outputs",
            **dict(metadata or {}),
        },
    )


def validate_claim_argument_case_surfaces(
    case: Mapping[str, Any],
    *,
    effective_authority_profile: str | None = None,
) -> ClaimArgumentValidationResult:
    """Validate explicit argument, warrant, rebuttal, counter-evidence, and deficits."""

    if not isinstance(case, Mapping):
        issue = ClaimArgumentIssue(
            code="policy_design_claim_argument_case_invalid",
            claim_id=None,
            field="policy_design_case",
            message="Policy Design Case claim-argument surface must be a mapping.",
        )
        return ClaimArgumentValidationResult("fail", (), (issue,))

    profile = _text(effective_authority_profile) or _text(
        case.get("effective_execution_profile")
    )
    rows_by_surface = {
        surface: _surface_rows(case, surface)
        for surface in (*_REQUIRED_SURFACES, "blocker")
    }
    issues: list[ClaimArgumentIssue] = []
    summaries: list[dict[str, Any]] = []

    for claim in _final_major_claims(case):
        claim_id = _text(claim.get("claim_id") or claim.get("id"))
        claim_ref = _first_text(
            claim.get("assurance_node_id"),
            claim.get("assurance_node_ref"),
            claim.get("claim_ref"),
            claim.get("cas_ref"),
        )
        surface_refs: dict[str, list[str]] = {}

        for surface in _REQUIRED_SURFACES:
            matched = _matched_surface_rows(
                claim,
                rows_by_surface[surface],
                surface=surface,
                claim_id=claim_id,
            )
            ids = [_surface_identity(row, surface=surface) for row in matched]
            surface_refs[f"{surface}_refs"] = [value for value in ids if value]
            if matched:
                continue
            issues.append(
                ClaimArgumentIssue(
                    code=_MISSING_CODES[surface],
                    claim_id=claim_id,
                    field=f"final_major_claims.{_SURFACE_REF_KEYS[surface][0]}",
                    message=_MISSING_MESSAGES[surface],
                    evidence_ref=claim_ref,
                )
            )

        arguments = _matched_surface_rows(
            claim,
            rows_by_surface["argument"],
            surface="argument",
            claim_id=claim_id,
        )
        if arguments and not any(_argument_strategy(row) for row in arguments):
            issues.append(
                ClaimArgumentIssue(
                    code="policy_design_major_claim_argument_strategy_missing",
                    claim_id=claim_id,
                    field="arguments.strategy",
                    message="Argument records must name the claim argument strategy.",
                    evidence_ref=claim_ref,
                )
            )

        warrants = _matched_surface_rows(
            claim,
            rows_by_surface["warrant"],
            surface="warrant",
            claim_id=claim_id,
        )
        berl_reliability_refs: list[str] = []
        warrant_reliability_records: list[dict[str, Any]] = []
        for warrant in warrants:
            berl_reliability_refs.extend(warrant_berl_reliability_refs(warrant))
            if not _text(warrant.get("warrant_text") or warrant.get("rationale")):
                issues.append(
                    ClaimArgumentIssue(
                        code="policy_design_warrant_text_missing",
                        claim_id=claim_id,
                        field="warrants.warrant_text",
                        message="Warrant records must explain why evidence supports the claim.",
                        evidence_ref=_surface_evidence_ref(warrant),
                    )
                )
            reliability = evaluate_warrant_berl_reliability(
                case,
                warrant,
                claim_id=claim_id,
            )
            warrant_reliability_records.extend(reliability.records)
            for issue in reliability.issues:
                issues.append(
                    ClaimArgumentIssue(
                        code=issue.code,
                        claim_id=claim_id,
                        field=issue.field,
                        message=issue.message,
                        evidence_ref=issue.evidence_ref or _surface_evidence_ref(warrant),
                    )
                )
            if not _text_values(warrant.get("assumptions")):
                issues.append(
                    ClaimArgumentIssue(
                        code="policy_design_warrant_assumptions_missing",
                        claim_id=claim_id,
                        field="warrants.assumptions",
                        message="Warrant records must expose their assumptions.",
                        evidence_ref=_surface_evidence_ref(warrant),
                    )
                )
            if not _text_values(
                warrant.get("applicability_limits")
                or warrant.get("applicability")
                or warrant.get("limits")
            ):
                issues.append(
                    ClaimArgumentIssue(
                        code="policy_design_warrant_applicability_limits_missing",
                        claim_id=claim_id,
                        field="warrants.applicability_limits",
                        message="Warrant records must expose applicability limits.",
                        evidence_ref=_surface_evidence_ref(warrant),
                    )
                )
            if (
                warrant_requires_berl_reliability(warrant)
                and not warrant_berl_reliability_refs(warrant)
            ):
                issues.append(
                    ClaimArgumentIssue(
                        code="policy_design_warrant_berl_refs_missing",
                        claim_id=claim_id,
                        field="warrants.berl_reliability_refs",
                        message=(
                            "Warrants that use explanation reliability for reviewer "
                            "trust, automated claim acceptance, or user-facing confidence "
                            "must cite BERL reliability refs."
                        ),
                        evidence_ref=_surface_evidence_ref(warrant),
                    )
                )

        hidden_counter_evidence = [
            row
            for row in rows_by_surface["counter_evidence"]
            if _row_matches_claim(row, claim_id=claim_id)
            and _counter_evidence_hidden(row)
        ]
        for row in hidden_counter_evidence:
            issues.append(
                ClaimArgumentIssue(
                    code="policy_design_hidden_counter_evidence",
                    claim_id=claim_id,
                    field="counter_evidence.visibility",
                    message=(
                        "Counter-evidence must remain visible to reviewer and "
                        "closeout surfaces."
                    ),
                    evidence_ref=_surface_evidence_ref(row),
                )
            )

        requester_capture_challenges = _matched_surface_rows(
            claim,
            rows_by_surface["requester_capture_challenge"],
            surface="requester_capture_challenge",
            claim_id=claim_id,
        )
        for challenge in requester_capture_challenges:
            issues.extend(
                _requester_capture_challenge_issues(
                    case,
                    challenge,
                    claim_id=claim_id,
                    claim_ref=claim_ref,
                )
            )

        blockers = _matched_surface_rows(
            claim,
            rows_by_surface["blocker"],
            surface="blocker",
            claim_id=claim_id,
        )
        blocker_refs = [
            value
            for row in blockers
            if (value := _surface_identity(row, surface="blocker"))
        ]
        if "blocker_refs" in claim:
            blocker_refs.extend(_text_values(claim.get("blocker_refs")))
        elif blockers:
            pass
        else:
            issues.append(
                ClaimArgumentIssue(
                    code="policy_design_major_claim_blocker_surface_missing",
                    claim_id=claim_id,
                    field="final_major_claims.blocker_refs",
                    message=(
                        "Major claims must expose blocker refs, using an explicit "
                        "empty list when no blockers remain."
                    ),
                    evidence_ref=claim_ref,
                )
            )

        summary = {
            "claim_id": claim_id,
            "claim_ref": claim_ref,
            "effective_authority_profile": profile,
            "argument_strategy": _first_text(
                claim.get("argument_strategy"),
                *(_argument_strategy(row) for row in arguments),
            ),
            **surface_refs,
            "limitation_refs": list(surface_refs.get("deficit_refs", [])),
            "semantic_binding_refs": {
                "argument_refs": list(surface_refs.get("argument_refs", [])),
                "warrant_refs": list(surface_refs.get("warrant_refs", [])),
                "rebuttal_refs": list(surface_refs.get("rebuttal_refs", [])),
                "counter_evidence_refs": list(
                    surface_refs.get("counter_evidence_refs", [])
                ),
                "limitation_refs": list(surface_refs.get("deficit_refs", [])),
            },
            "berl_reliability_refs": list(dict.fromkeys(berl_reliability_refs)),
            "warrant_reliability_records": warrant_reliability_records,
            "blocker_refs": list(dict.fromkeys(blocker_refs)),
        }
        summaries.append(summary)

    return ClaimArgumentValidationResult(
        status="fail" if issues else "pass",
        major_claims=tuple(summaries),
        issues=tuple(issues),
    )


def export_claim_argument_case_mapping(case: Mapping[str, Any]) -> dict[str, Any]:
    """Export major-claim reasoning surfaces as a SACM/CAE/GSN mapping."""

    result = validate_claim_argument_case_surfaces(case)
    exported_claims = []
    for claim, summary in zip(_final_major_claims(case), result.major_claims, strict=False):
        claim_node = _first_text(
            claim.get("assurance_node_id"),
            claim.get("assurance_node_ref"),
            summary.get("claim_ref"),
            claim.get("claim_ref"),
        )
        argument_refs = list(summary.get("argument_refs", []))
        warrant_refs = list(summary.get("warrant_refs", []))
        rebuttal_refs = list(summary.get("rebuttal_refs", []))
        counter_refs = list(summary.get("counter_evidence_refs", []))
        deficit_refs = list(summary.get("deficit_refs", []))
        challenge_refs = list(summary.get("requester_capture_challenge_refs", []))
        blocker_refs = list(summary.get("blocker_refs", []))
        exported_claims.append(
            {
                "claim_id": summary.get("claim_id"),
                "claim_ref": summary.get("claim_ref"),
                "argument_strategy": summary.get("argument_strategy"),
                "sacm": {
                    "claim": claim_node,
                    "argument_reasoning": argument_refs,
                    "asserted_inference": warrant_refs,
                    "defeated_claim": rebuttal_refs,
                    "artifact_reference": counter_refs,
                    "assurance_deficit": [*deficit_refs, *blocker_refs],
                    "context": challenge_refs,
                },
                "cae": {
                    "claim": claim_node,
                    "argument": argument_refs,
                    "warrant": warrant_refs,
                    "rebuttal": rebuttal_refs,
                    "counter_evidence": counter_refs,
                    "assurance_deficit": deficit_refs,
                    "challenge": challenge_refs,
                    "blocker": blocker_refs,
                },
                "gsn": {
                    "goal": claim_node,
                    "strategy": argument_refs,
                    "justification": warrant_refs,
                    "away_goal": rebuttal_refs,
                    "context": [*counter_refs, *challenge_refs],
                    "assumption": deficit_refs,
                    "undeveloped": blocker_refs,
                },
            }
        )

    return {
        "schema_version": CLAIM_ARGUMENT_MAPPING_SCHEMA_VERSION,
        "contract_id": CLAIM_ARGUMENT_CONTRACT_ID,
        "standards": ["SACM", "CAE", "GSN"],
        "node_mapping": dict(CLAIM_ARGUMENT_NODE_MAPPING),
        "summary": {
            "major_claim_count": len(exported_claims),
            "issue_count": len(result.issues),
        },
        "major_claims": exported_claims,
        "issues": [issue.as_dict() for issue in result.issues],
    }


def _final_major_claims(case: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    claims = case.get("final_major_claims") or case.get("major_claims") or ()
    if not isinstance(claims, list):
        return ()
    return tuple(
        claim
        for claim in claims
        if isinstance(claim, Mapping) and claim.get("major") is not False
    )


def _surface_rows(
    case: Mapping[str, Any],
    surface: str,
) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for key in _SURFACE_TOP_LEVEL_KEYS[surface]:
        value = case.get(key)
        if isinstance(value, Mapping):
            rows.append(value)
        elif isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, Mapping))
    nodes = case.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            node_type = _text(node.get("node_type"))
            node_family = _text(node.get("node_family"))
            if (
                node_type == surface
                or node_family == surface
                or (surface == "deficit" and node_type == "deficit")
                or (
                    surface == "blocker"
                    and node_family in {"blocker", "assurance_blocker"}
                )
            ):
                rows.append(node)
    return tuple(rows)


def _matched_surface_rows(
    claim: Mapping[str, Any],
    rows: tuple[Mapping[str, Any], ...],
    *,
    surface: str,
    claim_id: str | None,
) -> tuple[Mapping[str, Any], ...]:
    refs = set(_claim_surface_refs(claim, surface=surface))
    matched: list[Mapping[str, Any]] = []
    for row in rows:
        row_ids = set(_surface_id_values(row, surface=surface))
        if refs and refs.isdisjoint(row_ids):
            continue
        if refs or _row_matches_claim(row, claim_id=claim_id):
            matched.append(row)
    return tuple(matched)


def _claim_surface_refs(claim: Mapping[str, Any], *, surface: str) -> tuple[str, ...]:
    values: list[str] = []
    for key in _SURFACE_REF_KEYS[surface]:
        values.extend(_text_values(claim.get(key)))
    return tuple(dict.fromkeys(values))


def _surface_id_values(row: Mapping[str, Any], *, surface: str) -> tuple[str, ...]:
    values: list[str] = []
    for key in _SURFACE_ID_KEYS[surface]:
        values.extend(_text_values(row.get(key)))
    return tuple(dict.fromkeys(values))


def _surface_identity(row: Mapping[str, Any], *, surface: str) -> str | None:
    values = _surface_id_values(row, surface=surface)
    return values[0] if values else None


def _surface_evidence_ref(row: Mapping[str, Any]) -> str | None:
    return _first_text(row.get("evidence_ref"), row.get("cas_ref"), row.get("artifact_ref"))


def _requester_capture_challenge_issues(
    case: Mapping[str, Any],
    challenge: Mapping[str, Any],
    *,
    claim_id: str | None,
    claim_ref: str | None,
) -> list[ClaimArgumentIssue]:
    issues: list[ClaimArgumentIssue] = []
    evidence_ref = _surface_evidence_ref(challenge) or claim_ref
    case_preferred = _case_requester_preferred_conclusion(case)
    challenge_preferred = _challenge_requester_preferred_conclusion(challenge)
    if case_preferred is not None and challenge_preferred is None:
        issues.append(
            ClaimArgumentIssue(
                code="policy_design_requester_capture_preference_missing",
                claim_id=claim_id,
                field="requester_capture_challenges.requester_preferred_conclusion",
                message=(
                    "Requester-capture challenges must repeat the requester "
                    "preferred conclusion they are testing against."
                ),
                evidence_ref=evidence_ref,
            )
        )
    if (
        case_preferred is not None
        and challenge_preferred is not None
        and _normalized_text(case_preferred) != _normalized_text(challenge_preferred)
    ):
        issues.append(
            ClaimArgumentIssue(
                code="policy_design_requester_capture_preference_mismatch",
                claim_id=claim_id,
                field="requester_capture_challenges.requester_preferred_conclusion",
                message=(
                    "Requester-capture challenges must test the same requester "
                    "preferred conclusion captured in the intent envelope."
                ),
                evidence_ref=evidence_ref,
            )
        )

    challenge_result = _challenge_result(challenge)
    if _normalized_text(challenge_result) in {
        "fail",
        "failed",
        "blocked",
        "reject",
        "rejected",
        "capture_detected",
        "prior_confirmed",
    }:
        issues.append(
            ClaimArgumentIssue(
                code="policy_design_requester_capture_challenge_failed",
                claim_id=claim_id,
                field="requester_capture_challenges.challenge_result",
                message=(
                    "Requester-capture challenges must not be accepted when "
                    "the independent challenge failed."
                ),
                evidence_ref=evidence_ref,
            )
        )

    independent_conclusion = _challenge_independent_analysis_conclusion(challenge)
    if independent_conclusion is None:
        issues.append(
            ClaimArgumentIssue(
                code="policy_design_requester_capture_independent_analysis_missing",
                claim_id=claim_id,
                field="requester_capture_challenges.independent_analysis_conclusion",
                message=(
                    "Requester-capture challenges must state the independent "
                    "analysis conclusion separately from requester preference."
                ),
                evidence_ref=evidence_ref,
            )
        )
    elif (
        (challenge_preferred or case_preferred) is not None
        and _normalized_text(independent_conclusion)
        == _normalized_text(challenge_preferred or case_preferred)
    ):
        issues.append(
            ClaimArgumentIssue(
                code="policy_design_requester_capture_independent_analysis_confirms_prior",
                claim_id=claim_id,
                field="requester_capture_challenges.independent_analysis_conclusion",
                message=(
                    "Requester-capture challenges must separate independent "
                    "analysis from requester-preferred conclusions."
                ),
                evidence_ref=evidence_ref,
            )
        )

    preferred_for_depth = challenge_preferred or case_preferred
    min_alternatives = _challenge_minimum_alternative_count(case, preferred_for_depth)
    alternative_count = _challenge_independent_alternative_count(
        challenge,
        preferred_conclusion=preferred_for_depth,
    )
    if preferred_for_depth is not None and alternative_count < min_alternatives:
        issues.append(
            ClaimArgumentIssue(
                code="policy_design_requester_capture_independent_alternatives_missing",
                claim_id=claim_id,
                field="requester_capture_challenges.independent_alternative_analyses",
                message=(
                    "Requester preferred conclusions cannot be accepted by a "
                    "challenge that merely confirms the prior without independent "
                    "alternative analysis."
                ),
                evidence_ref=evidence_ref,
            )
        )

    for _, fields, code, message in _SCIENTIST_CHALLENGE_REF_REQUIREMENTS:
        if _challenge_scientist_refs(challenge, fields):
            continue
        issues.append(
            ClaimArgumentIssue(
                code=code,
                claim_id=claim_id,
                field=f"requester_capture_challenges.{fields[0]}",
                message=message,
                evidence_ref=evidence_ref,
            )
        )
    return issues


def _row_matches_claim(row: Mapping[str, Any], *, claim_id: str | None) -> bool:
    if claim_id is None:
        return False
    row_claims = set(_text_values(row.get("claim_ids")))
    row_claim = _text(row.get("claim_id") or row.get("major_claim_id"))
    if row_claim is not None:
        row_claims.add(row_claim)
    return claim_id in row_claims


def _argument_strategy(row: Mapping[str, Any]) -> str | None:
    return _text(row.get("strategy") or row.get("argument_strategy"))


def _counter_evidence_hidden(row: Mapping[str, Any]) -> bool:
    if row.get("hidden") is True:
        return True
    for key in ("visibility", "status", "disposition", "reviewer_visibility"):
        text = _text(row.get(key))
        if text is None:
            continue
        normalized = text.casefold().replace("-", "_")
        if any(
            token in normalized
            for token in (
                "hidden",
                "redacted_without_summary",
                "excluded_from_reviewer",
                "suppressed",
                "not_disclosed",
            )
        ):
            return True
    return False


def _case_requester_preferred_conclusion(case: Mapping[str, Any]) -> str | None:
    intent = case.get("intent_envelope")
    if isinstance(intent, Mapping):
        preference = intent.get("requester_preference")
        preferred = _first_text(
            intent.get("requester_preferred_conclusion"),
            preference.get("preferred_conclusion") if isinstance(preference, Mapping) else None,
        )
        if preferred is not None:
            return preferred
    return _first_text(case.get("requester_preferred_conclusion"))


def _challenge_requester_preferred_conclusion(challenge: Mapping[str, Any]) -> str | None:
    preference = challenge.get("requester_preference")
    return _first_text(
        challenge.get("requester_preferred_conclusion"),
        preference.get("preferred_conclusion") if isinstance(preference, Mapping) else None,
    )


def _challenge_result(challenge: Mapping[str, Any]) -> str | None:
    return _first_text(
        challenge.get("challenge_result"),
        challenge.get("status"),
        challenge.get("result"),
    )


def _challenge_independent_analysis_conclusion(challenge: Mapping[str, Any]) -> str | None:
    independent = challenge.get("independent_analysis")
    return _first_text(
        challenge.get("independent_analysis_conclusion"),
        challenge.get("independent_conclusion"),
        challenge.get("analysis_conclusion"),
        independent.get("conclusion") if isinstance(independent, Mapping) else None,
        independent.get("result") if isinstance(independent, Mapping) else None,
        independent.get("summary") if isinstance(independent, Mapping) else None,
    )


def _challenge_minimum_alternative_count(
    case: Mapping[str, Any],
    preferred_conclusion: str | None,
) -> int:
    for source in (case.get("challenge_depth_policy"), _intent_challenge_depth_policy(case)):
        if not isinstance(source, Mapping):
            continue
        count = _coerce_positive_int(source.get("minimum_alternative_count"))
        if count is not None:
            return count
    return 2 if preferred_conclusion is not None else 1


def _intent_challenge_depth_policy(case: Mapping[str, Any]) -> Mapping[str, Any] | None:
    intent = case.get("intent_envelope")
    if not isinstance(intent, Mapping):
        return None
    policy = intent.get("challenge_depth_policy")
    return policy if isinstance(policy, Mapping) else None


def _coerce_positive_int(value: object) -> int | None:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None
    return count if count > 0 else None


def _challenge_independent_alternative_count(
    challenge: Mapping[str, Any],
    *,
    preferred_conclusion: str | None,
) -> int:
    alternatives: list[object] = []
    for key in (
        "independent_alternative_analyses",
        "independent_alternatives",
        "alternative_analyses",
        "alternative_analysis",
        "alternative_options",
        "rejected_alternatives",
    ):
        value = challenge.get(key)
        if isinstance(value, Mapping):
            alternatives.append(value)
        elif isinstance(value, list | tuple | set):
            alternatives.extend(value)
    return sum(
        1
        for alternative in alternatives
        if _meaningful_alternative(alternative, preferred_conclusion=preferred_conclusion)
    )


def _meaningful_alternative(
    alternative: object,
    *,
    preferred_conclusion: str | None,
) -> bool:
    if isinstance(alternative, str):
        text = alternative.strip()
        return bool(text) and _normalized_text(text) != _normalized_text(preferred_conclusion)
    if not isinstance(alternative, Mapping):
        return False
    alternative_id = _first_text(
        alternative.get("alternative_id"),
        alternative.get("option_id"),
        alternative.get("id"),
        alternative.get("name"),
    )
    conclusion = _first_text(
        alternative.get("conclusion"),
        alternative.get("finding"),
        alternative.get("summary"),
        alternative.get("rationale"),
        alternative.get("decision"),
    )
    evidence_refs = _text_values(
        alternative.get("evidence_refs")
        or alternative.get("source_refs")
        or alternative.get("analysis_refs")
    )
    if conclusion is not None and _normalized_text(conclusion) == _normalized_text(
        preferred_conclusion
    ):
        return False
    return bool(alternative_id or conclusion or evidence_refs)


def _challenge_scientist_refs(
    challenge: Mapping[str, Any],
    fields: tuple[str, ...],
) -> list[str]:
    refs: list[str] = []
    nested_sources = (
        challenge,
        challenge.get("scientist_output_refs"),
        challenge.get("challenge_output_refs"),
        challenge.get("source_output_refs"),
    )
    for source in nested_sources:
        if not isinstance(source, Mapping):
            continue
        for field in fields:
            refs.extend(_text_values(source.get(field)))
    return _dedupe_texts(refs)


def _scientist_output_refs(
    source: object,
    *,
    preferred_fields: tuple[str, ...],
) -> list[str]:
    return _dedupe_texts(
        _scientist_ref_values(source, preferred_fields=preferred_fields)
    )


def _scientist_ref_values(
    value: object,
    *,
    preferred_fields: tuple[str, ...],
) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, Mapping):
        for field in preferred_fields:
            if field not in value:
                continue
            values = _scientist_ref_values(value.get(field), preferred_fields=())
            if values:
                return values
        values: list[str] = []
        for field in (
            "artifact_ref",
            "cas_ref",
            "evidence_ref",
            "ref",
            "artifact_id",
            "cas_artifact_id",
            "id",
            "value",
        ):
            if field in value:
                values.extend(
                    _scientist_ref_values(value.get(field), preferred_fields=())
                )
        metadata = value.get("metadata")
        if isinstance(metadata, Mapping):
            values.extend(_scientist_ref_values(metadata, preferred_fields=()))
        return values
    if isinstance(value, list | tuple | set):
        values = []
        for item in value:
            values.extend(
                _scientist_ref_values(item, preferred_fields=preferred_fields)
            )
        return values

    values: list[str] = []
    for field in preferred_fields:
        if not hasattr(value, field):
            continue
        field_values = _scientist_ref_values(getattr(value, field), preferred_fields=())
        if field_values:
            return field_values
    for field in (
        "artifact_ref",
        "cas_ref",
        "evidence_ref",
        "ref",
        "artifact_id",
        "cas_artifact_id",
    ):
        if hasattr(value, field):
            values.extend(
                _scientist_ref_values(getattr(value, field), preferred_fields=())
            )
    if hasattr(value, "root"):
        values.extend(_scientist_ref_values(value.root, preferred_fields=()))
    metadata = getattr(value, "metadata", None)
    if isinstance(metadata, Mapping):
        values.extend(_scientist_ref_values(metadata, preferred_fields=()))
    return values


def _normalized_text(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.strip().casefold().split())


def _dedupe_texts(values: object) -> list[str]:
    return list(dict.fromkeys(_text_values(values)))


def _text_values(value: object) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, Mapping):
        values: list[str] = []
        for key in (
            "ref",
            "id",
            "value",
            "evidence_ref",
            "cas_ref",
            "node_id",
            "record_id",
            "claim_id",
        ):
            values.extend(_text_values(value.get(key)))
        return values
    if isinstance(value, list | tuple | set):
        values = []
        for item in value:
            values.extend(_text_values(item))
        return values
    return []


def _first_text(*values: object) -> str | None:
    for value in values:
        text_values = _text_values(value)
        if text_values:
            return text_values[0]
        text = _text(value)
        if text is not None:
            return text
    return None


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


__all__ = [
    "CLAIM_ARGUMENT_CONTRACT_ID",
    "CLAIM_ARGUMENT_MAPPING_SCHEMA_VERSION",
    "CLAIM_ARGUMENT_NODE_MAPPING",
    "CLAIM_ARGUMENT_VALIDATION_SCHEMA_VERSION",
    "PRE_PUBLICATION_CHALLENGE_NODE_SCHEMA_VERSION",
    "ClaimArgumentIssue",
    "ClaimArgumentValidationResult",
    "build_pre_publication_challenge_node",
    "build_pre_publication_challenge_node_from_scientist_outputs",
    "export_claim_argument_case_mapping",
    "validate_claim_argument_case_surfaces",
]
