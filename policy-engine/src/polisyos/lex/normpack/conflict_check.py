"""Normative corpus compatibility checks for policy canary evidence."""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "policyos.lex.policy_conflict_check.v1"
BLOCKING_SEVERITIES = {"critical", "high", "blocker", "fail", "failed"}
WARN_SEVERITIES = {"medium", "moderate", "low", "warn", "warning"}
INFO_SEVERITIES = {"info", "informational", "notice", "none"}
DIRECT_CONFLICT_TYPES = {"direct_prohibition", "direct_prohibition_conflict"}
INDIRECT_REVIEWABLE_TYPES = {
    "indirect_conflict",
    "indirect_policy_conflict",
    "indirect_review",
    "indirect_reviewable_conflict",
    "reviewable_conflict",
    "reviewable_indirect_conflict",
}
INFORMATIONAL_OVERLAP_TYPES = {
    "informational",
    "informational_overlap",
    "overlap",
    "policy_overlap",
    "related_norm_overlap",
}
NESTED_CONSTRAINT_KEYS = (
    "constraints",
    "corpus_constraints",
    "normative_constraints",
    "policy_constraints",
    "requirements",
    "rules",
    "conflict_constraints",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_refs(value: Any) -> list[str]:
    if isinstance(value, str):
        return [_text(value)] if _text(value) else []
    if not isinstance(value, list):
        return []
    return [_text(item) for item in value if _text(item)]


def _as_set(value: Any) -> set[str]:
    return {_text(item).casefold() for item in _as_refs(value)}


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _claim_id(claim: dict[str, Any], index: int) -> str:
    return _text(claim.get("claim_id") or claim.get("id") or f"claim_{index + 1}")


def _claim_text(claim: dict[str, Any]) -> str:
    return _text(claim.get("text") or claim.get("claim") or claim.get("statement"))


def _claim_action(claim: dict[str, Any]) -> str:
    return _text(
        claim.get("action")
        or claim.get("policy_action")
        or claim.get("intervention")
        or claim.get("intervention_type")
    )


def _claim_budget(claim: dict[str, Any]) -> float | None:
    for key in ("budget_usd", "budget", "estimated_budget_usd", "proposed_budget_usd"):
        if key in claim:
            return _to_float(claim.get(key))
    return None


def _claim_eligibility_tags(claim: dict[str, Any]) -> set[str]:
    tags = set()
    for key in ("eligibility_tags", "eligible_population_tags", "target_tags"):
        tags.update(_as_set(claim.get(key)))
    target_population = claim.get("target_population")
    if isinstance(target_population, dict):
        tags.update(_as_set(target_population.get("eligibility_tags")))
    return tags


def _constraint_id(constraint: dict[str, Any], index: int) -> str:
    return _text(
        constraint.get("constraint_id")
        or constraint.get("id")
        or constraint.get("norm_id")
        or f"constraint_{index + 1}"
    )


def _constraint_type(constraint: dict[str, Any]) -> str:
    raw_type = _text(
        constraint.get("constraint_type")
        or constraint.get("type")
        or constraint.get("category")
        or constraint.get("conflict_type")
        or constraint.get("fact_class")
    ).casefold()
    aliases = {
        "budget_cap": "budget_rule",
        "budget_cap_rule": "budget_rule",
        "budget_rule_constraint": "budget_rule",
        "credit_eligibility_rule": "eligibility_constraint",
        "eligibility_rule": "eligibility_constraint",
        "equity_access_rule": "equity_access_requirement",
        "prohibition": "direct_prohibition",
        "prohibition_rule": "direct_prohibition",
        "direct_prohibition_rule": "direct_prohibition",
        "reviewable_policy_conflict": "indirect_policy_conflict",
        "soft_policy_conflict": "indirect_policy_conflict",
        "related_policy_overlap": "informational_overlap",
    }
    return aliases.get(raw_type, raw_type)


def _constraint_norm_refs(constraint: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("norm_ref", "norm_refs", "norm_id", "affected_norm_refs"):
        refs.extend(_as_refs(constraint.get(key)))
    return refs


def _severity(value: Any, *, default: str = "high") -> str:
    severity = _text(value).casefold()
    return severity if severity else default


def _classification_for(
    *,
    code: str,
    conflict_type: str,
    severity: str,
    blocking: bool,
) -> str:
    if (
        code in INFORMATIONAL_OVERLAP_TYPES
        or conflict_type in INFORMATIONAL_OVERLAP_TYPES
        or severity in INFO_SEVERITIES
    ):
        return "informational_overlap"
    if code in INDIRECT_REVIEWABLE_TYPES or conflict_type in INDIRECT_REVIEWABLE_TYPES:
        return "indirect_reviewable_conflict"
    if blocking:
        if code in DIRECT_CONFLICT_TYPES or conflict_type in DIRECT_CONFLICT_TYPES:
            return "direct_blocking_conflict"
        return "blocking_conflict"
    return "reviewable_conflict"


def _is_blocking(*, code: str, conflict_type: str, severity: str, blocking: Any = None) -> bool:
    if isinstance(blocking, bool):
        return blocking
    if code in INFORMATIONAL_OVERLAP_TYPES or conflict_type in INFORMATIONAL_OVERLAP_TYPES:
        return False
    if code in DIRECT_CONFLICT_TYPES or conflict_type in DIRECT_CONFLICT_TYPES:
        return True
    return severity in BLOCKING_SEVERITIES


def _status_from_conflicts(conflicts: list[dict[str, Any]]) -> str:
    if any(conflict.get("blocking") is True for conflict in conflicts):
        return "fail"
    if conflicts:
        return "warn"
    return "pass"


def _code_for_type(conflict_type: str) -> str:
    mapping = {
        "direct_prohibition": "direct_prohibition_conflict",
        "eligibility": "eligibility_mismatch",
        "eligibility_constraint": "eligibility_mismatch",
        "budget": "budget_rule_mismatch",
        "budget_rule": "budget_rule_mismatch",
        "equity": "equity_access_conflict",
        "equity_access": "equity_access_conflict",
        "equity_access_requirement": "equity_access_conflict",
    }
    return mapping.get(conflict_type, conflict_type or "policy_corpus_conflict")


def _next_action_for_code(code: str) -> str:
    mapping = {
        "direct_prohibition_conflict": (
            "Revise or remove the proposed action, or add a formal legal change path."
        ),
        "eligibility_mismatch": (
            "Constrain the target population to eligible groups or change the legal basis."
        ),
        "budget_rule_mismatch": (
            "Reduce the proposed budget, identify valid budget authority, or fail the policy."
        ),
        "equity_access_conflict": (
            "Add mitigation, narrow rollout, or run equity/access review before approval."
        ),
        "indirect_policy_conflict": (
            "Route the compatibility finding to an operator for review before approval."
        ),
        "informational_overlap": (
            "Keep the overlap in the evidence packet; no blocking operator action is required."
        ),
    }
    return mapping.get(
        code,
        "Resolve the conflict or document an explicit governance escalation.",
    )


def _conflict(
    *,
    code: str,
    conflict_type: str,
    severity: str,
    claim_id: str | None,
    claim_text: str | None,
    constraint_id: str | None,
    norm_refs: list[str],
    message: str,
    blocking: bool | None = None,
    **extra: Any,
) -> dict[str, Any]:
    resolved_blocking = _is_blocking(
        code=code,
        conflict_type=conflict_type,
        severity=severity,
        blocking=blocking,
    )
    classification = _classification_for(
        code=code,
        conflict_type=conflict_type,
        severity=severity,
        blocking=resolved_blocking,
    )
    requires_operator_action = bool(
        resolved_blocking or classification == "indirect_reviewable_conflict"
    )
    return {
        "conflict_id": extra.pop("conflict_id", None) or f"{code}:{claim_id or constraint_id}",
        "code": code,
        "severity": severity,
        "blocking": resolved_blocking,
        "classification": classification,
        "requires_operator_action": requires_operator_action,
        "retryable": False,
        "layer": "normative_conflict",
        "phase": "corpus_compatibility",
        "conflict_type": conflict_type,
        "claim_id": claim_id,
        "claim_text": claim_text,
        "constraint_id": constraint_id,
        "norm_refs": norm_refs,
        "message": message,
        "next_action": _next_action_for_code(code),
        **extra,
    }


def _claim_norm_refs(claim: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("norm_ref", "norm_refs", "normative_refs", "norm_ids", "legal_refs"):
        refs.extend(_as_refs(claim.get(key)))
    grounding = claim.get("grounding")
    if isinstance(grounding, dict):
        for key in ("norm_ref", "norm_refs", "normative_refs", "norm_ids", "legal_refs"):
            refs.extend(_as_refs(grounding.get(key)))
    deduped: list[str] = []
    for ref in refs:
        if ref not in deduped:
            deduped.append(ref)
    return deduped


def _claim_action_tokens(claim: dict[str, Any]) -> set[str]:
    actions = {
        _claim_action(claim),
        _text(claim.get("recommended_action")),
        _text(claim.get("mechanism")),
        _text(claim.get("mechanism_type")),
        _text(claim.get("intervention_id")),
    }
    return {action.casefold() for action in actions if action}


def _constraint_related_actions(constraint: dict[str, Any]) -> set[str]:
    actions: set[str] = set()
    for key in (
        "related_actions",
        "review_actions",
        "affected_actions",
        "covered_actions",
        "trigger_actions",
        "actions",
        "policy_actions",
    ):
        actions.update(_as_set(constraint.get(key)))
    return actions


def _constraint_keywords(constraint: dict[str, Any]) -> set[str]:
    keywords: set[str] = set()
    for key in ("keywords", "topics", "subjects", "terms"):
        keywords.update(_as_set(constraint.get(key)))
    return keywords


def _constraint_target_tags(constraint: dict[str, Any]) -> set[str]:
    tags: set[str] = set()
    for key in (
        "eligibility_tags",
        "target_tags",
        "affected_groups",
        "protected_groups",
        "covered_groups",
    ):
        tags.update(_as_set(constraint.get(key)))
    return tags


def _claim_matches_constraint(
    claim: dict[str, Any],
    *,
    claim_id: str,
    claim_text: str,
    constraint: dict[str, Any],
) -> bool:
    raw_claim_ids = (
        constraint.get("claim_ids")
        or constraint.get("applies_to_claim_ids")
        or constraint.get("review_claim_ids")
    )
    constraint_claim_ids = _as_set(raw_claim_ids)
    has_criteria = bool(constraint_claim_ids)
    if constraint_claim_ids:
        return claim_id.casefold() in constraint_claim_ids

    claim_norm_refs = set(_claim_norm_refs(claim))
    constraint_norm_refs = set(_constraint_norm_refs(constraint))
    has_criteria = has_criteria or bool(constraint_norm_refs)
    if claim_norm_refs and constraint_norm_refs and claim_norm_refs.intersection(
        constraint_norm_refs
    ):
        return True

    claim_actions = _claim_action_tokens(claim)
    constraint_actions = _constraint_related_actions(constraint)
    has_criteria = has_criteria or bool(constraint_actions)
    if claim_actions and constraint_actions and claim_actions.intersection(constraint_actions):
        return True

    claim_tags = _claim_eligibility_tags(claim)
    constraint_tags = _constraint_target_tags(constraint)
    has_criteria = has_criteria or bool(constraint_tags)
    if claim_tags and constraint_tags and claim_tags.intersection(constraint_tags):
        return True

    keywords = _constraint_keywords(constraint)
    has_criteria = has_criteria or bool(keywords)
    if keywords:
        haystack = f"{claim_text} {' '.join(claim_actions)}".casefold()
        if any(keyword in haystack for keyword in keywords):
            return True

    if not has_criteria:
        return bool(
            constraint.get("applies_to_all_claims")
            or constraint.get("global")
            or constraint.get("always_review")
        )
    return False


def _direct_conflicts(
    claim: dict[str, Any],
    *,
    claim_id: str,
    claim_text: str,
    constraint: dict[str, Any],
    constraint_id: str,
) -> list[dict[str, Any]]:
    action = _claim_action(claim).casefold()
    prohibited = _as_set(
        constraint.get("prohibited_actions") or constraint.get("blocked_actions")
    )
    if not action or action not in prohibited:
        return []
    severity = _severity(constraint.get("severity"), default="critical")
    return [
        _conflict(
            code="direct_prohibition_conflict",
            conflict_type="direct_prohibition",
            severity=severity,
            claim_id=claim_id,
            claim_text=claim_text,
            constraint_id=constraint_id,
            norm_refs=_constraint_norm_refs(constraint),
            message=f"Claim {claim_id} proposes prohibited action {_claim_action(claim)}.",
        )
    ]


def _eligibility_conflicts(
    claim: dict[str, Any],
    *,
    claim_id: str,
    claim_text: str,
    constraint: dict[str, Any],
    constraint_id: str,
) -> list[dict[str, Any]]:
    claim_tags = _claim_eligibility_tags(claim)
    allowed = _as_set(constraint.get("allowed_eligibility_tags"))
    required = _as_set(constraint.get("required_eligibility_tags"))
    broad_tags = {"all", "all_businesses", "universal", "uncapped"}
    mismatch = False
    if required and not required.issubset(claim_tags):
        mismatch = True
    if allowed and claim_tags and not claim_tags.intersection(allowed):
        mismatch = True
    if allowed and claim_tags.intersection(broad_tags):
        mismatch = True
    if not mismatch:
        return []
    severity = _severity(constraint.get("severity"), default="high")
    return [
        _conflict(
            code="eligibility_mismatch",
            conflict_type="eligibility_constraint",
            severity=severity,
            claim_id=claim_id,
            claim_text=claim_text,
            constraint_id=constraint_id,
            norm_refs=_constraint_norm_refs(constraint),
            message=f"Claim {claim_id} eligibility does not match corpus constraints.",
            claim_eligibility_tags=sorted(claim_tags),
            allowed_eligibility_tags=sorted(allowed),
            required_eligibility_tags=sorted(required),
        )
    ]


def _budget_conflicts(
    claim: dict[str, Any],
    *,
    claim_id: str,
    claim_text: str,
    constraint: dict[str, Any],
    constraint_id: str,
) -> list[dict[str, Any]]:
    budget = _claim_budget(claim)
    cap = _to_float(
        constraint.get("max_budget_usd")
        or constraint.get("budget_cap_usd")
        or constraint.get("max_budget")
    )
    if budget is None or cap is None or budget <= cap:
        return []
    severity = _severity(constraint.get("severity"), default="high")
    return [
        _conflict(
            code="budget_rule_mismatch",
            conflict_type="budget_rule",
            severity=severity,
            claim_id=claim_id,
            claim_text=claim_text,
            constraint_id=constraint_id,
            norm_refs=_constraint_norm_refs(constraint),
            message=f"Claim {claim_id} budget {budget:g} exceeds cap {cap:g}.",
            proposed_budget=budget,
            max_budget=cap,
        )
    ]


def _equity_conflicts(
    claim: dict[str, Any],
    *,
    claim_id: str,
    claim_text: str,
    constraint: dict[str, Any],
    constraint_id: str,
) -> list[dict[str, Any]]:
    impact = claim.get("equity_access_impact") or claim.get("equity_impact")
    if not isinstance(impact, dict):
        return []
    impact_status = _text(impact.get("status") or impact.get("quality_status")).casefold()
    affected = _as_set(
        impact.get("affected_groups")
        or impact.get("worsens_access_for")
        or impact.get("harmed_groups")
    )
    protected = _as_set(
        constraint.get("protected_groups") or constraint.get("covered_groups")
    )
    bad_status = impact_status in {"fail", "failed", "negative", "blocked", "degraded"}
    group_overlap = not protected or bool(affected.intersection(protected))
    if not bad_status or not group_overlap:
        return []
    severity = _severity(constraint.get("severity"), default="high")
    return [
        _conflict(
            code="equity_access_conflict",
            conflict_type="equity_access_requirement",
            severity=severity,
            claim_id=claim_id,
            claim_text=claim_text,
            constraint_id=constraint_id,
            norm_refs=_constraint_norm_refs(constraint),
            message=f"Claim {claim_id} has adverse equity/access impact.",
            affected_groups=sorted(affected),
            protected_groups=sorted(protected),
            blocking=severity in BLOCKING_SEVERITIES,
        )
    ]


def _indirect_reviewable_conflicts(
    claim: dict[str, Any],
    *,
    claim_id: str,
    claim_text: str,
    constraint: dict[str, Any],
    constraint_id: str,
) -> list[dict[str, Any]]:
    if not _claim_matches_constraint(
        claim,
        claim_id=claim_id,
        claim_text=claim_text,
        constraint=constraint,
    ):
        return []
    severity = _severity(constraint.get("severity"), default="medium")
    code = _text(
        constraint.get("code")
        or constraint.get("reason_code")
        or constraint.get("conflict_code")
    ) or "indirect_policy_conflict"
    return [
        _conflict(
            code=code,
            conflict_type="indirect_policy_conflict",
            severity=severity,
            claim_id=claim_id,
            claim_text=claim_text,
            constraint_id=constraint_id,
            norm_refs=_constraint_norm_refs(constraint),
            message=_text(constraint.get("message"))
            or f"Claim {claim_id} overlaps a reviewable corpus constraint.",
            blocking=constraint.get("blocking"),
            review_required=True,
        )
    ]


def _informational_overlaps(
    claim: dict[str, Any],
    *,
    claim_id: str,
    claim_text: str,
    constraint: dict[str, Any],
    constraint_id: str,
) -> list[dict[str, Any]]:
    if not _claim_matches_constraint(
        claim,
        claim_id=claim_id,
        claim_text=claim_text,
        constraint=constraint,
    ):
        return []
    severity = _severity(constraint.get("severity"), default="info")
    code = _text(
        constraint.get("code")
        or constraint.get("reason_code")
        or constraint.get("overlap_code")
    ) or "informational_overlap"
    return [
        _conflict(
            code=code,
            conflict_type="informational_overlap",
            severity=severity,
            claim_id=claim_id,
            claim_text=claim_text,
            constraint_id=constraint_id,
            norm_refs=_constraint_norm_refs(constraint),
            message=_text(constraint.get("message"))
            or f"Claim {claim_id} overlaps an active corpus norm without blocking.",
            blocking=False,
        )
    ]


def _detect_constraint_conflicts(
    claim: dict[str, Any],
    *,
    claim_id: str,
    claim_text: str,
    constraint: dict[str, Any],
    constraint_id: str,
) -> list[dict[str, Any]]:
    constraint_type = _constraint_type(constraint)
    if constraint_type in {"direct_prohibition", "prohibition"}:
        return _direct_conflicts(
            claim,
            claim_id=claim_id,
            claim_text=claim_text,
            constraint=constraint,
            constraint_id=constraint_id,
        )
    if constraint_type in {"eligibility", "eligibility_constraint"}:
        return _eligibility_conflicts(
            claim,
            claim_id=claim_id,
            claim_text=claim_text,
            constraint=constraint,
            constraint_id=constraint_id,
        )
    if constraint_type in {"budget", "budget_rule"}:
        return _budget_conflicts(
            claim,
            claim_id=claim_id,
            claim_text=claim_text,
            constraint=constraint,
            constraint_id=constraint_id,
        )
    if constraint_type in {"equity", "equity_access", "equity_access_requirement"}:
        return _equity_conflicts(
            claim,
            claim_id=claim_id,
            claim_text=claim_text,
            constraint=constraint,
            constraint_id=constraint_id,
        )
    if constraint_type in INDIRECT_REVIEWABLE_TYPES:
        return _indirect_reviewable_conflicts(
            claim,
            claim_id=claim_id,
            claim_text=claim_text,
            constraint=constraint,
            constraint_id=constraint_id,
        )
    if constraint_type in INFORMATIONAL_OVERLAP_TYPES:
        return _informational_overlaps(
            claim,
            claim_id=claim_id,
            claim_text=claim_text,
            constraint=constraint,
            constraint_id=constraint_id,
        )
    return []


def _looks_like_constraint(constraint: dict[str, Any]) -> bool:
    if _constraint_type(constraint):
        return True
    return any(
        key in constraint
        for key in (
            "prohibited_actions",
            "blocked_actions",
            "allowed_eligibility_tags",
            "required_eligibility_tags",
            "max_budget_usd",
            "budget_cap_usd",
            "protected_groups",
            "related_actions",
            "review_actions",
        )
    )


def _constraint_parent_refs(constraint: dict[str, Any]) -> list[str]:
    refs = _constraint_norm_refs(constraint)
    if refs:
        return refs
    return _as_refs(constraint.get("norm_id") or constraint.get("artifact_id"))


def _inherit_constraint_metadata(
    child: dict[str, Any],
    *,
    parent: dict[str, Any],
    parent_id: str,
    index: int,
) -> dict[str, Any]:
    inherited = dict(child)
    if not _text(
        inherited.get("constraint_id")
        or inherited.get("id")
        or inherited.get("norm_id")
    ):
        inherited["constraint_id"] = f"{parent_id}:constraint_{index + 1}"
    parent_refs = _constraint_parent_refs(parent)
    if parent_refs and not _constraint_norm_refs(inherited):
        inherited["norm_refs"] = parent_refs
    for key in (
        "jurisdiction",
        "policy_domain",
        "source_authority",
        "authority_level",
        "effective_from",
        "effective_to",
    ):
        if key not in inherited and key in parent:
            inherited[key] = parent[key]
    return inherited


def _expanded_corpus_constraints(
    corpus_constraints: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for constraint_index, raw_constraint in enumerate(corpus_constraints):
        if not isinstance(raw_constraint, dict):
            continue
        constraint = dict(raw_constraint)
        parent_id = _constraint_id(constraint, constraint_index)
        nested_added = False
        for key in NESTED_CONSTRAINT_KEYS:
            raw_children = constraint.get(key)
            if not isinstance(raw_children, list):
                continue
            for child_index, raw_child in enumerate(raw_children):
                if not isinstance(raw_child, dict):
                    continue
                expanded.append(
                    _inherit_constraint_metadata(
                        dict(raw_child),
                        parent=constraint,
                        parent_id=parent_id,
                        index=child_index,
                    )
                )
                nested_added = True
        if not nested_added or _looks_like_constraint(constraint):
            expanded.append(constraint)
    return expanded


def _normalize_existing_conflict(conflict: dict[str, Any], index: int) -> dict[str, Any]:
    conflict_type = _constraint_type(conflict)
    code = _text(conflict.get("code") or conflict.get("reason_code")) or _code_for_type(
        conflict_type
    )
    severity = _severity(conflict.get("severity"), default="high")
    norm_refs: list[str] = []
    for key in ("norm_refs", "norm_ref", "affected_norm_refs", "norm_id"):
        norm_refs.extend(_as_refs(conflict.get(key)))
    return {
        **conflict,
        **_conflict(
            conflict_id=_text(conflict.get("conflict_id") or conflict.get("id"))
            or f"conflict_{index + 1}",
            code=code,
            conflict_type=conflict_type or code,
            severity=severity,
            claim_id=_text(conflict.get("claim_id")) or None,
            claim_text=_text(conflict.get("claim_text") or conflict.get("text")) or None,
            constraint_id=_text(conflict.get("constraint_id")) or None,
            norm_refs=norm_refs,
            message=_text(conflict.get("message"))
            or f"Policy conflict {code} was reported.",
            blocking=conflict.get("blocking"),
        ),
    }


def build_policy_conflict_check_report(
    *,
    policy_claims: list[dict[str, Any]],
    corpus_constraints: list[dict[str, Any]],
    existing_conflicts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a corpus compatibility report for proposed policy claims."""
    findings = [
        _normalize_existing_conflict(conflict, index)
        for index, conflict in enumerate(existing_conflicts or [])
        if isinstance(conflict, dict)
    ]
    conflicts = [
        finding
        for finding in findings
        if finding.get("classification") != "informational_overlap"
    ]
    informational_overlaps = [
        finding
        for finding in findings
        if finding.get("classification") == "informational_overlap"
    ]
    expanded_constraints = _expanded_corpus_constraints(corpus_constraints)

    for claim_index, claim in enumerate(policy_claims):
        if not isinstance(claim, dict):
            continue
        claim_id = _claim_id(claim, claim_index)
        claim_text = _claim_text(claim)
        for constraint_index, constraint in enumerate(expanded_constraints):
            if not isinstance(constraint, dict):
                continue
            detected_findings = _detect_constraint_conflicts(
                claim,
                claim_id=claim_id,
                claim_text=claim_text,
                constraint=constraint,
                constraint_id=_constraint_id(constraint, constraint_index),
            )
            for finding in detected_findings:
                findings.append(finding)
                if finding.get("classification") == "informational_overlap":
                    informational_overlaps.append(finding)
                else:
                    conflicts.append(finding)

    status = _status_from_conflicts(conflicts)
    blocking_conflict_count = sum(
        1 for conflict in conflicts if conflict.get("blocking") is True
    )
    reviewable_conflict_count = sum(
        1
        for conflict in conflicts
        if conflict.get("classification") == "indirect_reviewable_conflict"
    )
    operator_action_required_count = sum(
        1
        for conflict in conflicts
        if conflict.get("requires_operator_action") is True
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "policy_claims": list(policy_claims),
        "corpus_constraints": expanded_constraints,
        "conflicts": conflicts,
        "informational_overlaps": informational_overlaps,
        "findings": findings,
        "issues": conflicts,
        "blocking_conflict_count": blocking_conflict_count,
        "reviewable_conflict_count": reviewable_conflict_count,
        "informational_overlap_count": len(informational_overlaps),
        "operator_action_required": operator_action_required_count > 0,
        "operator_action_required_count": operator_action_required_count,
        "review_required": reviewable_conflict_count > 0,
        "summary": {
            "policy_claim_count": len(policy_claims),
            "corpus_constraint_count": len(expanded_constraints),
            "conflict_count": len(conflicts),
            "blocking_conflict_count": blocking_conflict_count,
            "reviewable_conflict_count": reviewable_conflict_count,
            "informational_overlap_count": len(informational_overlaps),
        },
    }


def normalize_policy_conflict_check_report(report: dict[str, Any]) -> dict[str, Any]:
    """Recompute conflict-check status from declared conflicts and constraints."""
    if not isinstance(report, dict):
        report = {}
    raw_claims = report.get("policy_claims") or report.get("claims") or []
    policy_claims = [claim for claim in raw_claims if isinstance(claim, dict)] if isinstance(
        raw_claims,
        list,
    ) else []
    raw_constraints = (
        report.get("corpus_constraints")
        or report.get("constraints")
        or report.get("normative_constraints")
        or []
    )
    corpus_constraints = [
        constraint for constraint in raw_constraints if isinstance(constraint, dict)
    ] if isinstance(raw_constraints, list) else []
    raw_conflicts = report.get("conflicts") or []
    raw_overlaps = report.get("informational_overlaps") or []
    existing_conflicts = [
        conflict for conflict in raw_conflicts if isinstance(conflict, dict)
    ] if isinstance(raw_conflicts, list) else []
    if isinstance(raw_overlaps, list):
        existing_conflicts.extend(
            conflict for conflict in raw_overlaps if isinstance(conflict, dict)
        )
    normalized = build_policy_conflict_check_report(
        policy_claims=policy_claims,
        corpus_constraints=corpus_constraints,
        existing_conflicts=existing_conflicts,
    )
    return {**report, **normalized}


__all__ = [
    "SCHEMA_VERSION",
    "build_policy_conflict_check_report",
    "normalize_policy_conflict_check_report",
]
