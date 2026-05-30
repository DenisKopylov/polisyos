"""Rule-evolution replay execution for closed Policy Design Cases.

The engine is the W9.F bridge between the W2.B rule registry, research-DAG
public replay, and claim lifecycle revalidation. It preserves closed-case
meaning under original rules while evaluating the same claim facts under new
rule or taxonomy semantics for C33 public revalidation decisions.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from polisyos.core import canon
from polisyos.runtime.quality.case_lifecycle import build_lifecycle_reissue_report
from polisyos.runtime.quality.replay import sanitize_for_replay
from polisyos.runtime.quality.rule_evolution import (
    build_rule_evolution_replay_context,
)

RULE_REPLAY_EXECUTION_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.rule_replay_execution.v1"
)
RULE_REPLAY_COMPARISON_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.rule_replay_comparison.v1"
)
RULE_REPLAY_PUBLIC_REPORT_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.rule_replay_public_report.v1"
)
RULE_REPLAY_COMPARISON_KIND = "runtime.rule_replay_comparison_report"
RULE_REPLAY_COMPARISON_SCHEMA = "polisyos.runtime.RuleReplayComparisonReport"
RULE_REPLAY_CONTRACT_ID = "policy_design_case.rule_replay_engine.v1"
RULE_REPLAY_PRODUCER_OWNER = "team-runtime-quality"

C33_RULE_CHANGE_CLASS_TABLE: dict[str, dict[str, Any]] = {
    "editorial": {
        "mandatory_revalidation": False,
        "public_effect": "no_notice",
        "lifecycle_action": "none",
        "grandfathering_policy": "historical_validity_preserved",
    },
    "schema_compatible": {
        "mandatory_revalidation": False,
        "public_effect": "internal_migration",
        "lifecycle_action": "none",
        "grandfathering_policy": "lossless_migration_allowed",
    },
    "threshold_change": {
        "mandatory_revalidation": True,
        "public_effect": "mandatory_revalidation",
        "lifecycle_action": "partial_reissue",
        "grandfathering_policy": "historical_validity_preserved_current_guidance_reviewed",
    },
    "stricter_admissibility": {
        "mandatory_revalidation": True,
        "public_effect": "mandatory_revalidation",
        "lifecycle_action": "partial_reissue",
        "grandfathering_policy": "historical_validity_preserved_current_guidance_reviewed",
    },
    "weaker_admissibility": {
        "mandatory_revalidation": False,
        "public_effect": "public_annotation",
        "lifecycle_action": "review_required",
        "grandfathering_policy": "historical_validity_preserved_optional_reissue",
    },
    "new_blocker": {
        "mandatory_revalidation": True,
        "public_effect": "mandatory_revalidation",
        "lifecycle_action": "partial_reissue",
        "grandfathering_policy": "historical_validity_preserved_current_guidance_reviewed",
    },
    "retired_blocker": {
        "mandatory_revalidation": False,
        "public_effect": "public_annotation",
        "lifecycle_action": "review_required",
        "grandfathering_policy": "historical_validity_preserved_optional_reissue",
    },
    "taxonomy_split_merge": {
        "mandatory_revalidation": True,
        "public_effect": "mandatory_revalidation",
        "lifecycle_action": "partial_reissue",
        "grandfathering_policy": "historical_validity_preserved_scope_review_required",
    },
    "authority_profile_change": {
        "mandatory_revalidation": True,
        "public_effect": "mandatory_revalidation",
        "lifecycle_action": "partial_reissue",
        "grandfathering_policy": "historical_validity_preserved_authority_review_required",
    },
}


class _JsonArtifactStore(Protocol):
    """Minimal CAS writer protocol used by rule replay persistence."""

    def put_json(
        self,
        payload: object,
        options: object,
        canon_spec: object | None = None,
    ) -> object:
        """Persist JSON-like payloads and return an artifact reference."""


@dataclass(frozen=True)
class _ArtifactWriteOptions:
    """Local write options shape consumed by CAS stores."""

    kind: str
    media_type: str
    schema: Mapping[str, str]
    producer: object | None = None
    env: object | None = None
    inputs: tuple[object, ...] = ()
    canon: object | None = None


def replay_under_original_rules(
    closed_pdc: Mapping[str, Any],
    rule_change_record: Mapping[str, Any],
    *,
    replay_time: str | datetime | None = None,
) -> dict[str, Any]:
    """Replay a closed PDC using the rule registry that originally closed it.

    Args:
        closed_pdc: Closed Policy Design Case payload carrying claims, closure
            time, and the closed rule registry.
        rule_change_record: C33 rule or taxonomy change record with the new
            registry and change class.
        replay_time: Runtime replay time. Defaults to current UTC time.

    Returns:
        A rule replay execution report that must match closed semantic outputs
        when those outputs are present.
    """

    closed_registry = _closed_registry(closed_pdc, rule_change_record)
    current_registry = _current_registry(rule_change_record, fallback=closed_registry)
    context = _rule_replay_context(
        closed_pdc=closed_pdc,
        rule_change_record=rule_change_record,
        closed_registry=closed_registry,
        current_registry=current_registry,
        replay_time=replay_time,
    )
    return _replay_with_registry(
        closed_pdc=closed_pdc,
        rule_change_record=rule_change_record,
        registry=closed_registry,
        replay_context=context,
        replay_mode="original_rules",
        replay_time=replay_time,
        alias_map={},
    )


def replay_under_new_rules(
    closed_pdc: Mapping[str, Any],
    rule_change_record: Mapping[str, Any],
    *,
    replay_time: str | datetime | None = None,
) -> dict[str, Any]:
    """Replay a closed PDC using the new rule registry for comparison.

    Args:
        closed_pdc: Closed Policy Design Case payload carrying claims, closure
            time, and the closed rule registry.
        rule_change_record: C33 rule or taxonomy change record with the new
            registry and change class.
        replay_time: Runtime replay time. Defaults to current UTC time.

    Returns:
        A rule replay execution report that exposes changed current-rule
        admissibility without rewriting closed-case historical meaning.
    """

    closed_registry = _closed_registry(closed_pdc, rule_change_record)
    current_registry = _current_registry(rule_change_record, fallback=closed_registry)
    context = _rule_replay_context(
        closed_pdc=closed_pdc,
        rule_change_record=rule_change_record,
        closed_registry=closed_registry,
        current_registry=current_registry,
        replay_time=replay_time,
    )
    return _replay_with_registry(
        closed_pdc=closed_pdc,
        rule_change_record=rule_change_record,
        registry=current_registry,
        replay_context=context,
        replay_mode="new_rules",
        replay_time=replay_time,
        alias_map=_alias_map(current_registry),
    )


def build_rule_replay_comparison_report(
    closed_pdc: Mapping[str, Any],
    rule_change_record: Mapping[str, Any],
    *,
    replay_time: str | datetime | None = None,
) -> dict[str, Any]:
    """Replay a closed PDC under old and new rules and emit C33 revalidation.

    Args:
        closed_pdc: Closed Policy Design Case payload.
        rule_change_record: Rule/taxonomy change record with a C33 change class.
        replay_time: Runtime replay time. Defaults to current UTC time.

    Returns:
        A comparison report carrying original replay, new replay, semantic diff,
        C33 trigger, public comparison projection, and lifecycle reissue report
        when review or mandatory revalidation is required.
    """

    generated = _iso_time(replay_time)
    original = replay_under_original_rules(
        closed_pdc,
        rule_change_record,
        replay_time=generated,
    )
    new = replay_under_new_rules(
        closed_pdc,
        rule_change_record,
        replay_time=generated,
    )
    comparison = _compare_semantic_outputs(
        original.get("semantic_outputs"),
        new.get("semantic_outputs"),
    )
    trigger = _c33_revalidation_trigger(
        rule_change_record=rule_change_record,
        comparison=comparison,
    )
    lifecycle_report = _lifecycle_report_for_trigger(
        closed_pdc=closed_pdc,
        original_replay=original,
        trigger=trigger,
        generated_at=generated,
    )
    public_report = _public_comparison_report(
        closed_pdc=closed_pdc,
        rule_change_record=rule_change_record,
        comparison=comparison,
        trigger=trigger,
        generated_at=generated,
    )
    report_ref = _stable_ref(
        {
            "case_id": _case_id(closed_pdc),
            "change_id": _text(rule_change_record.get("change_id")),
            "generated_at": generated,
            "comparison": comparison,
            "trigger": trigger,
        }
    )
    status = _comparison_status(trigger=trigger, comparison=comparison)
    payload = {
        "schema_version": RULE_REPLAY_COMPARISON_SCHEMA_VERSION,
        "contract_id": RULE_REPLAY_CONTRACT_ID,
        "report_id": f"rule-replay:{_case_id(closed_pdc)}:{_change_id(rule_change_record)}",
        "case_id": _case_id(closed_pdc),
        "change_id": _change_id(rule_change_record),
        "generated_at": generated,
        "status": status,
        "original_replay": original,
        "new_replay": new,
        "comparison": comparison,
        "revalidation_trigger": trigger,
        "public_comparison_report": public_report,
        "lifecycle_reissue_report": lifecycle_report,
        "evidence_ref": report_ref,
        "runtime_event_ref": f"event://rule-replay/{_case_id(closed_pdc)}/{_change_id(rule_change_record)}",
        "runtime_authority_envelope": _authority_envelope(report_ref=report_ref),
        "capability_reality": {
            "typed_contract": RULE_REPLAY_CONTRACT_ID,
            "producer": (
                "polisyos.runtime.quality.rule_replay_engine."
                "build_rule_replay_comparison_report"
            ),
            "artifact": report_ref,
            "orchestration_bridge": "W2.B rule registry -> research-DAG replay -> claim lifecycle",
            "consumer": "polisyos.runtime.quality.case_lifecycle.build_lifecycle_reissue_report",
            "verification": "tests/unit/runtime/quality/test_rule_replay_engine.py",
            "surface": "public_comparison_report",
            "semantic_test": "stricter admissibility triggers mandatory revalidation",
        },
    }
    return sanitize_for_replay(payload)


def persist_rule_replay_comparison_report(
    report: Mapping[str, Any],
    *,
    store: _JsonArtifactStore,
) -> object:
    """Persist a rule replay comparison report and return its CAS ref.

    Args:
        report: Report returned by `build_rule_replay_comparison_report`.
        store: CAS-compatible JSON artifact store.

    Returns:
        The artifact reference returned by the store.
    """

    return store.put_json(
        sanitize_for_replay(dict(report)),
        _ArtifactWriteOptions(
            kind=RULE_REPLAY_COMPARISON_KIND,
            media_type="application/json",
            schema={"name": RULE_REPLAY_COMPARISON_SCHEMA, "version": "1.0"},
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )


def _replay_with_registry(
    *,
    closed_pdc: Mapping[str, Any],
    rule_change_record: Mapping[str, Any],
    registry: Mapping[str, Any],
    replay_context: Mapping[str, Any],
    replay_mode: str,
    replay_time: str | datetime | None,
    alias_map: Mapping[str, str],
) -> dict[str, Any]:
    generated = _iso_time(replay_time)
    claims = _claim_rows(closed_pdc)
    rule_index = _rules_by_requirement(registry)
    semantic_outputs: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for claim in claims:
        claim_id = _claim_id(claim)
        for requirement_id in _claim_requirement_refs(claim):
            current_requirement_id = alias_map.get(requirement_id, requirement_id)
            rule = rule_index.get(current_requirement_id)
            if rule is None:
                issues.append(
                    _issue(
                        "rule_replay_rule_missing",
                        "Closed claim requirement has no rule in replay registry.",
                        severity="fail",
                        claim_id=claim_id,
                        requirement_id=requirement_id,
                    )
                )
                semantic_outputs.append(
                    _missing_rule_output(
                        claim_id=claim_id,
                        requirement_id=requirement_id,
                        current_requirement_id=current_requirement_id,
                    )
                )
                continue
            output = _evaluate_claim_rule(
                claim=claim,
                rule=rule,
                requirement_id=requirement_id,
                current_requirement_id=current_requirement_id,
            )
            semantic_outputs.append(output)
            if output["evaluation_status"] == "unsupported_logic":
                issues.append(
                    _issue(
                        "rule_replay_logic_unexecutable",
                        "Rule replay requires executable rule logic, not only a hash.",
                        severity="fail",
                        claim_id=claim_id,
                        requirement_id=requirement_id,
                    )
                )
    semantic_outputs = sorted(
        semantic_outputs,
        key=lambda row: (str(row["claim_id"]), str(row["requirement_id"])),
    )
    closed_outputs = _closed_semantic_outputs(closed_pdc)
    replay_status, reproduces_closed_outputs = _semantic_replay_status(
        replay_mode=replay_mode,
        semantic_outputs=semantic_outputs,
        closed_outputs=closed_outputs,
    )
    if replay_mode == "original_rules" and replay_status == "mismatch":
        issues.append(
            _issue(
                "closed_rule_replay_output_mismatch",
                "Original-rule replay did not reproduce the closed PDC semantic outputs.",
                severity="fail",
            )
        )
    research_replay = _research_replay(closed_pdc)
    report = {
        "schema_version": RULE_REPLAY_EXECUTION_SCHEMA_VERSION,
        "contract_id": RULE_REPLAY_CONTRACT_ID,
        "case_id": _case_id(closed_pdc),
        "change_id": _change_id(rule_change_record),
        "generated_at": generated,
        "replay_mode": replay_mode,
        "semantic_replay_status": replay_status,
        "reproduces_closed_outputs": reproduces_closed_outputs,
        "closed_case_historical_meaning": "preserved",
        "rule_registry_ref": _registry_ref(registry),
        "rule_registry_version": _text(registry.get("version")),
        "rule_evolution_replay_context": dict(replay_context),
        "research_replay": research_replay,
        "research_replay_status": _text(research_replay.get("replay_status"))
        if isinstance(research_replay, Mapping)
        else "legacy_missing",
        "semantic_outputs": semantic_outputs,
        "closed_semantic_outputs_ref": _closed_outputs_ref(closed_pdc, closed_outputs),
        "summary": {
            "claim_count": len(claims),
            "semantic_output_count": len(semantic_outputs),
            "issue_count": len(issues),
        },
        "issues": issues,
        "authoritative_for": ["rule_replay_execution"],
        "may_not_use_for": [
            "claim_evidence_authority",
            "silent_current_logic_upgrade",
            "projection_authority",
        ],
    }
    return sanitize_for_replay(report)


def _evaluate_claim_rule(
    *,
    claim: Mapping[str, Any],
    rule: Mapping[str, Any],
    requirement_id: str,
    current_requirement_id: str,
) -> dict[str, Any]:
    logic = rule.get("logic")
    if not isinstance(logic, Mapping):
        return {
            "claim_id": _claim_id(claim),
            "requirement_id": requirement_id,
            "current_requirement_id": current_requirement_id,
            "rule_id": _text(rule.get("rule_id")) or current_requirement_id,
            "logic_hash": _text(rule.get("logic_hash")),
            "taxonomy_refs": _text_values(rule.get("taxonomy_refs")),
            "authority_purpose": _text(rule.get("authority_purpose")) or "admissibility",
            "evaluation_status": "unsupported_logic",
            "passed": False,
            "reason": "executable_rule_logic_missing",
        }
    field = _logic_field(logic)
    observed = _claim_fact(claim, field)
    operator = _logic_operator(logic)
    threshold = _logic_threshold(logic)
    passed = _apply_operator(observed=observed, operator=operator, threshold=threshold)
    status = _evaluation_status(
        passed=passed,
        authority_purpose=_text(rule.get("authority_purpose")) or "admissibility",
    )
    reason = (
        "observed_value_satisfies_threshold"
        if passed
        else "observed_value_fails_threshold"
        if observed is not None
        else "observed_value_missing"
    )
    return {
        "claim_id": _claim_id(claim),
        "requirement_id": requirement_id,
        "current_requirement_id": current_requirement_id,
        "rule_id": _text(rule.get("rule_id")) or current_requirement_id,
        "logic_hash": _text(rule.get("logic_hash")),
        "taxonomy_refs": _text_values(rule.get("taxonomy_refs")),
        "authority_purpose": _text(rule.get("authority_purpose")) or "admissibility",
        "evaluation_status": status,
        "passed": passed,
        "observed_value": observed,
        "operator": operator,
        "threshold": threshold,
        "reason": reason,
    }


def _rule_replay_context(
    *,
    closed_pdc: Mapping[str, Any],
    rule_change_record: Mapping[str, Any],
    closed_registry: Mapping[str, Any],
    current_registry: Mapping[str, Any],
    replay_time: str | datetime | None,
) -> dict[str, Any]:
    context = build_rule_evolution_replay_context(
        case_id=_case_id(closed_pdc),
        closed_case_rule_registry=closed_registry,
        current_rule_registry=current_registry,
        closure_time=_closure_time(closed_pdc),
        replay_time=_iso_time(replay_time),
    )
    affected = _dedupe_texts(
        [
            *_text_values(rule_change_record.get("affected_requirement_ids")),
            *_text_values(rule_change_record.get("affected_rule_ids")),
            *_text_values(rule_change_record.get("affected_taxonomy_requirement_ids")),
            *_text_values(
                _first_mapping(context.get("revalidation_state"), {}).get(
                    "affected_requirement_ids"
                )
            ),
        ]
    )
    if affected:
        context = dict(context)
        revalidation = dict(_first_mapping(context.get("revalidation_state"), {}))
        revalidation["affected_requirement_ids"] = affected
        if _c33_change_class(rule_change_record) in _mandatory_change_classes():
            revalidation["state"] = "mandatory_revalidation_required"
        context["revalidation_state"] = revalidation
    return context


def _compare_semantic_outputs(
    original_outputs: object,
    new_outputs: object,
) -> dict[str, Any]:
    original_by_key = _outputs_by_key(original_outputs)
    new_by_key = _outputs_by_key(new_outputs)
    diffs: list[dict[str, Any]] = []
    changed_claim_ids: list[str] = []
    changed_requirement_ids: list[str] = []
    for key in sorted(set(original_by_key) | set(new_by_key)):
        original = original_by_key.get(key)
        new = new_by_key.get(key)
        if original == new:
            continue
        claim_id, requirement_id = key
        changed_claim_ids.append(claim_id)
        changed_requirement_ids.append(requirement_id)
        diffs.append(
            {
                "claim_id": claim_id,
                "requirement_id": requirement_id,
                "original_status": _text(original.get("evaluation_status"))
                if isinstance(original, Mapping)
                else None,
                "new_status": _text(new.get("evaluation_status"))
                if isinstance(new, Mapping)
                else None,
                "original_fingerprint": _stable_ref(original or {}),
                "new_fingerprint": _stable_ref(new or {}),
            }
        )
    return {
        "status": "changed" if diffs else "unchanged",
        "changed_claim_ids": _dedupe_texts(changed_claim_ids),
        "changed_requirement_ids": _dedupe_texts(changed_requirement_ids),
        "diffs": diffs,
        "summary": {
            "difference_count": len(diffs),
            "changed_claim_count": len(set(changed_claim_ids)),
            "changed_requirement_count": len(set(changed_requirement_ids)),
        },
    }


def _c33_revalidation_trigger(
    *,
    rule_change_record: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> dict[str, Any]:
    change_class = _c33_change_class(rule_change_record)
    policy = dict(C33_RULE_CHANGE_CLASS_TABLE[change_class])
    mandatory = bool(policy["mandatory_revalidation"])
    changed = bool(comparison.get("changed_claim_ids"))
    return {
        "change_class": change_class,
        "mandatory_revalidation": mandatory,
        "public_effect": policy["public_effect"],
        "lifecycle_action": policy["lifecycle_action"],
        "grandfathering_policy": policy["grandfathering_policy"],
        "triggered": mandatory or (
            changed and policy["lifecycle_action"] in {"review_required", "partial_reissue"}
        ),
        "changed_claim_ids": _text_values(comparison.get("changed_claim_ids")),
        "changed_requirement_ids": _text_values(comparison.get("changed_requirement_ids")),
        "silent_upgrade_allowed": False,
    }


def _lifecycle_report_for_trigger(
    *,
    closed_pdc: Mapping[str, Any],
    original_replay: Mapping[str, Any],
    trigger: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any] | None:
    if not trigger.get("triggered"):
        return None
    claim_ids = [_claim_id(row) for row in _claim_rows(closed_pdc)]
    return build_lifecycle_reissue_report(
        report_id=f"rule-replay-lifecycle:{_case_id(closed_pdc)}",
        case_id=_case_id(closed_pdc),
        claim_ids=claim_ids,
        rule_evolution_replay_context=_first_mapping(
            original_replay.get("rule_evolution_replay_context")
        ),
        claim_requirement_bindings=_claim_requirement_bindings(closed_pdc),
        generated_at=generated_at,
        runtime_event_ref=f"event://rule-replay/lifecycle/{_case_id(closed_pdc)}",
    )


def _public_comparison_report(
    *,
    closed_pdc: Mapping[str, Any],
    rule_change_record: Mapping[str, Any],
    comparison: Mapping[str, Any],
    trigger: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": RULE_REPLAY_PUBLIC_REPORT_SCHEMA_VERSION,
        "case_id": _case_id(closed_pdc),
        "change_id": _change_id(rule_change_record),
        "generated_at": generated_at,
        "change_class": trigger["change_class"],
        "public_effect": trigger["public_effect"],
        "mandatory_revalidation": trigger["mandatory_revalidation"],
        "closed_case_historical_meaning": "preserved",
        "current_guidance_publishability": (
            "revalidation_required"
            if trigger["mandatory_revalidation"]
            else "review_required"
            if trigger["lifecycle_action"] == "review_required"
            else "current"
        ),
        "changed_claim_ids": list(comparison.get("changed_claim_ids") or []),
        "changed_requirement_ids": list(comparison.get("changed_requirement_ids") or []),
        "public_diff_required": bool(comparison.get("diffs")),
        "silent_upgrade_allowed": False,
        "authoritative_for": ["public_rule_replay_comparison"],
        "may_not_use_for": [
            "claim_evidence_authority",
            "mandatory_public_revalidation_policy",
            "silent_current_logic_upgrade",
        ],
    }


def _semantic_replay_status(
    *,
    replay_mode: str,
    semantic_outputs: Sequence[Mapping[str, Any]],
    closed_outputs: Sequence[Mapping[str, Any]],
) -> tuple[str, bool]:
    if not closed_outputs:
        return "closed_output_baseline_missing", False
    if list(semantic_outputs) == list(closed_outputs):
        return "match", True
    if replay_mode == "original_rules":
        return "mismatch", False
    return "changed_from_closed_outputs", False


def _missing_rule_output(
    *,
    claim_id: str,
    requirement_id: str,
    current_requirement_id: str,
) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "requirement_id": requirement_id,
        "current_requirement_id": current_requirement_id,
        "rule_id": current_requirement_id,
        "logic_hash": None,
        "taxonomy_refs": [],
        "authority_purpose": "admissibility",
        "evaluation_status": "unsupported_logic",
        "passed": False,
        "reason": "rule_missing",
    }


def _logic_field(logic: Mapping[str, Any]) -> str:
    explicit = _text(logic.get("field") or logic.get("metric") or logic.get("fact_key"))
    if explicit:
        return explicit
    predicate = _text(logic.get("predicate")) or "value"
    for suffix in ("_at_least", "_at_most", "_gte", "_lte"):
        if predicate.endswith(suffix):
            return predicate[: -len(suffix)]
    return predicate


def _logic_operator(logic: Mapping[str, Any]) -> str:
    operator = (_text(logic.get("operator")) or ">=").lower()
    return {
        "gte": ">=",
        "ge": ">=",
        "at_least": ">=",
        "lte": "<=",
        "le": "<=",
        "at_most": "<=",
        "gt": ">",
        "lt": "<",
        "eq": "==",
        "=": "==",
        "equals": "==",
        "ne": "!=",
    }.get(operator, operator)


def _logic_threshold(logic: Mapping[str, Any]) -> object:
    if "threshold" in logic:
        return logic["threshold"]
    if "value" in logic:
        return logic["value"]
    if "expected" in logic:
        return logic["expected"]
    return True


def _apply_operator(*, observed: object, operator: str, threshold: object) -> bool:
    if observed is None:
        return False
    if operator == "exists":
        return True
    if operator == "not_exists":
        return False
    if operator == "in":
        return observed in threshold if isinstance(threshold, Sequence) else False
    if operator == "not_in":
        return observed not in threshold if isinstance(threshold, Sequence) else True
    comparable = _numeric_pair(observed, threshold)
    left, right = comparable if comparable is not None else (observed, threshold)
    try:
        if operator == ">=":
            return bool(left >= right)
        if operator == "<=":
            return bool(left <= right)
        if operator == ">":
            return bool(left > right)
        if operator == "<":
            return bool(left < right)
        if operator == "!=":
            return bool(left != right)
        return bool(left == right)
    except TypeError:
        return False


def _evaluation_status(*, passed: bool, authority_purpose: str) -> str:
    if authority_purpose == "admissibility":
        return "admissible" if passed else "blocked"
    return "satisfied" if passed else "blocked"


def _claim_fact(claim: Mapping[str, Any], field: str) -> object | None:
    search: list[Mapping[str, Any]] = []
    for key in ("facts", "metrics", "admissibility", "observations", "inputs"):
        value = claim.get(key)
        if isinstance(value, Mapping):
            search.append(value)
    search.append(claim)
    candidates = [field]
    if field.endswith("_ratio"):
        candidates.append(field.removesuffix("_ratio"))
    else:
        candidates.append(f"{field}_ratio")
    for mapping in search:
        for candidate in candidates:
            if candidate in mapping:
                return mapping[candidate]
    return None


def _research_replay(closed_pdc: Mapping[str, Any]) -> dict[str, Any]:
    dag = closed_pdc.get("research_dag") or closed_pdc.get("research_dag_artifact")
    if dag is None:
        return {
            "run_id": None,
            "workflow_id": None,
            "replay_status": "legacy_missing",
            "hidden_content_redacted": True,
            "steps": [],
        }
    if isinstance(dag, Mapping):
        return dict(dag)
    try:
        from polisyos.scientist.methods.research_dag import public_replay_export

        return public_replay_export(dag)
    except (AttributeError, TypeError, ValueError):
        return {
            "run_id": None,
            "workflow_id": None,
            "replay_status": "legacy_minimal",
            "hidden_content_redacted": True,
            "steps": [],
        }


def _comparison_status(
    *,
    trigger: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> str:
    if trigger.get("mandatory_revalidation"):
        return "mandatory_revalidation_required"
    if trigger.get("triggered"):
        return "review_required"
    if comparison.get("status") == "changed":
        return "changed_no_mandatory_revalidation"
    return "compatible"


def _authority_envelope(*, report_ref: str) -> dict[str, Any]:
    return {
        "authority_role": "runtime_reader",
        "provenance_kind": "runtime_emitted",
        "cas_ref": report_ref,
        "authoritative_for": ["rule_replay_comparison", "public_rule_replay_comparison"],
        "may_not_use_for": [
            "claim_evidence_authority",
            "mandatory_public_revalidation_policy",
            "scorecard_authority",
            "silent_upgrade_approval",
        ],
    }


def _closed_registry(
    closed_pdc: Mapping[str, Any],
    rule_change_record: Mapping[str, Any],
) -> Mapping[str, Any]:
    registry = (
        closed_pdc.get("rule_evolution_registry")
        or closed_pdc.get("closed_rule_registry")
        or rule_change_record.get("from_rule_registry")
    )
    if not isinstance(registry, Mapping):
        raise ValueError("closed PDC must carry a closed rule evolution registry")
    return registry


def _current_registry(
    rule_change_record: Mapping[str, Any],
    *,
    fallback: Mapping[str, Any],
) -> Mapping[str, Any]:
    registry = (
        rule_change_record.get("to_rule_registry")
        or rule_change_record.get("current_rule_registry")
        or rule_change_record.get("rule_evolution_registry")
    )
    return registry if isinstance(registry, Mapping) else fallback


def _claim_rows(closed_pdc: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    claims = closed_pdc.get("claims") or closed_pdc.get("claim_records") or ()
    if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes, bytearray)):
        return []
    return [claim for claim in claims if isinstance(claim, Mapping)]


def _claim_id(claim: Mapping[str, Any]) -> str:
    return _text(claim.get("claim_id") or claim.get("id")) or "claim_0"


def _claim_requirement_refs(claim: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in (
        "scenario_requirement_refs",
        "requirement_refs",
        "rule_requirement_refs",
        "affected_requirement_ids",
    ):
        refs.extend(_text_values(claim.get(key)))
    return _dedupe_texts(refs)


def _claim_requirement_bindings(closed_pdc: Mapping[str, Any]) -> dict[str, list[str]]:
    return {
        _claim_id(claim): _claim_requirement_refs(claim)
        for claim in _claim_rows(closed_pdc)
    }


def _rules_by_requirement(registry: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(row["requirement_id"]): row
        for row in _mapping_rows(registry.get("rule_refs"))
        if _text(row.get("requirement_id"))
    }


def _alias_map(registry: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(row["from_requirement_id"]): str(row["to_requirement_id"])
        for row in _mapping_rows(registry.get("alias_remaps"))
        if _text(row.get("from_requirement_id")) and _text(row.get("to_requirement_id"))
    }


def _closed_semantic_outputs(closed_pdc: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    for key in (
        "closed_semantic_outputs",
        "closed_rule_replay_outputs",
        "rule_replay_semantic_outputs",
    ):
        rows = closed_pdc.get(key)
        if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes, bytearray)):
            return [row for row in rows if isinstance(row, Mapping)]
    return []


def _closed_outputs_ref(
    closed_pdc: Mapping[str, Any],
    closed_outputs: Sequence[Mapping[str, Any]],
) -> str | None:
    return _text(closed_pdc.get("closed_semantic_outputs_ref")) or (
        _stable_ref(closed_outputs) if closed_outputs else None
    )


def _outputs_by_key(value: object) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {
        (str(row["claim_id"]), str(row["requirement_id"])): row
        for row in _mapping_rows(value)
        if _text(row.get("claim_id")) and _text(row.get("requirement_id"))
    }


def _c33_change_class(rule_change_record: Mapping[str, Any]) -> str:
    change_class = _text(
        rule_change_record.get("change_class")
        or rule_change_record.get("c33_change_class")
        or rule_change_record.get("public_revalidation_effect")
    )
    if change_class in C33_RULE_CHANGE_CLASS_TABLE:
        return change_class
    return "schema_compatible"


def _mandatory_change_classes() -> set[str]:
    return {
        change_class
        for change_class, policy in C33_RULE_CHANGE_CLASS_TABLE.items()
        if policy["mandatory_revalidation"]
    }


def _case_id(closed_pdc: Mapping[str, Any]) -> str:
    return _text(closed_pdc.get("case_id") or closed_pdc.get("pdc_id")) or "pdc_unknown"


def _change_id(rule_change_record: Mapping[str, Any]) -> str:
    return _text(rule_change_record.get("change_id") or rule_change_record.get("id")) or (
        "rule_change_unknown"
    )


def _closure_time(closed_pdc: Mapping[str, Any]) -> str:
    return _text(
        closed_pdc.get("closed_at")
        or closed_pdc.get("closure_time")
        or closed_pdc.get("published_at")
    ) or _iso_time(None)


def _registry_ref(registry: Mapping[str, Any]) -> str | None:
    return _text(
        registry.get("rule_registry_ref")
        or registry.get("registry_ref")
        or registry.get("evidence_ref")
        or registry.get("cas_ref")
    )


def _mapping_rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _first_mapping(*values: object) -> Mapping[str, Any]:
    for value in values:
        if isinstance(value, Mapping):
            return value
    return {}


def _text_values(value: object) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if not isinstance(value, Iterable) or isinstance(value, (bytes, bytearray, Mapping)):
        return []
    return [text for item in value if (text := _text(item)) is not None]


def _dedupe_texts(values: Iterable[object]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if text is None or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _numeric_pair(left: object, right: object) -> tuple[float, float] | None:
    if isinstance(left, bool) or isinstance(right, bool):
        return None
    try:
        return float(left), float(right)
    except (TypeError, ValueError):
        return None


def _issue(
    code: str,
    message: str,
    *,
    severity: str,
    claim_id: str | None = None,
    requirement_id: str | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "phase": "rule_replay_engine",
        "message": message,
        "claim_id": claim_id,
        "requirement_id": requirement_id,
        "next_action": (
            "Replay the closed case under original rule logic, compare against "
            "new logic, and route affected claims through lifecycle revalidation."
        ),
    }


def _stable_ref(value: object) -> str:
    data = json.dumps(
        sanitize_for_replay(value),
        default=str,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _iso_time(value: str | datetime | None) -> str:
    if isinstance(value, datetime):
        resolved = value
    elif value is not None:
        return str(value)
    else:
        resolved = datetime.now(UTC)
    if resolved.tzinfo is None:
        resolved = resolved.replace(tzinfo=UTC)
    return resolved.isoformat()


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "C33_RULE_CHANGE_CLASS_TABLE",
    "RULE_REPLAY_COMPARISON_SCHEMA_VERSION",
    "RULE_REPLAY_EXECUTION_SCHEMA_VERSION",
    "RULE_REPLAY_PUBLIC_REPORT_SCHEMA_VERSION",
    "build_rule_replay_comparison_report",
    "persist_rule_replay_comparison_report",
    "replay_under_new_rules",
    "replay_under_original_rules",
]
