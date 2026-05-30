"""Policy-claim grounding checks for production canary quality evidence."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from polisyos.evidence import (
    apply_runtime_claim_registry_to_claim,
    claim_registry_rows_by_id,
    normalize_runtime_claim_registry,
)
from polisyos.scientist.validation.claim_support import evaluate_claim_support

SCHEMA_VERSION = "policyos.scientist.policy_grounding_matrix.v1"
CLAIM_FAMILIES = frozenset(
    {
        "recommendation",
        "empirical",
        "numerical",
        "causal",
        "normative",
        "forecast",
        "distributional",
        "implementation",
        "caveat",
    }
)
_CLAIM_FAMILY_REQUIRED_GROUNDING: dict[str, tuple[str, ...]] = {
    "empirical": ("data",),
    "causal": ("method",),
    "forecast": ("method",),
    "distributional": ("method",),
}
_CLAIM_FAMILY_ALIASES = {
    "advice": "recommendation",
    "claim": "empirical",
    "compliance": "normative",
    "distribution": "distributional",
    "equity": "distributional",
    "evidence": "empirical",
    "factual": "empirical",
    "impact": "causal",
    "legal": "normative",
    "number": "numerical",
    "numeric": "numerical",
    "operational": "implementation",
    "policy_recommendation": "recommendation",
    "quantitative": "numerical",
    "risk": "caveat",
    "scenario": "forecast",
}
_CLAIM_SUPPORT_FAMILY_BY_GROUNDING_FAMILY: dict[str, str] = {
    "empirical": "factual",
    "normative": "legal",
    "causal": "causal",
    "numerical": "numerical",
    "forecast": "forecast",
    "distributional": "distributional",
    "implementation": "implementation",
}
_MAJOR_CLAIM_EVIDENCE_GRAPH_REF_SPECS: tuple[
    tuple[str, tuple[str, ...], str, str],
    ...,
] = (
    (
        "portfolio_refs",
        ("portfolio_refs", "portfolio_design_refs", "evidence_portfolio_refs"),
        "portfolio",
        "major_claim_portfolio_refs_missing",
    ),
    (
        "independence_refs",
        ("independence_refs", "independence_map_refs"),
        "independence",
        "major_claim_independence_refs_missing",
    ),
    (
        "synthesis_refs",
        ("synthesis_refs", "synthesis_report_refs", "evidence_synthesis_refs"),
        "synthesis",
        "major_claim_synthesis_refs_missing",
    ),
    (
        "argument_refs",
        ("argument_refs", "claim_argument_refs", "argument_evidence_refs"),
        "argument",
        "major_claim_argument_refs_missing",
    ),
    (
        "warrant_refs",
        (
            "warrant_refs",
            "claim_warrant_refs",
            "warrant_evidence_refs",
            "berl_warrant_refs",
            "berl_reliability_refs",
        ),
        "warrant",
        "major_claim_warrant_refs_missing",
    ),
)
_REBUTTAL_COUNTER_REF_ALIASES = (
    "rebuttal_refs",
    "counter_evidence_refs",
    "counterevidence_refs",
    "disconfirming_refs",
    "disconfirming_evidence_refs",
    "disconfirming_ledger_refs",
)
_LIMITATION_DEFICIT_REF_ALIASES = (
    "accepted_deficit_refs",
    "accepted_deficits",
    "limitation_refs",
    "accepted_limitation_refs",
    "claim_limitation_refs",
    "data_quality_limitation_refs",
    "degrade_reason_refs",
)
_MAJOR_CLAIM_EVIDENCE_GRAPH_MISSING_CODES = frozenset(
    {
        "major_claim_portfolio_refs_missing",
        "major_claim_independence_refs_missing",
        "major_claim_synthesis_refs_missing",
        "major_claim_argument_refs_missing",
        "major_claim_warrant_refs_missing",
        "major_claim_rebuttal_or_counter_evidence_refs_missing",
        "major_claim_limitation_or_deficit_refs_missing",
    }
)


def _text(value: object) -> str:
    return str(value or "").strip()


def _as_refs(value: object) -> list[str]:
    if isinstance(value, str):
        return [_text(value)] if _text(value) else []
    if not isinstance(value, list):
        return []
    return [_text(item) for item in value if _text(item)]


def _as_graph_refs(value: object) -> list[str]:
    if isinstance(value, str):
        return [_text(value)] if _text(value) else []
    if isinstance(value, Mapping):
        refs: list[str] = []
        for key in (
            "evidence_ref",
            "artifact_ref",
            "cas_ref",
            "ref",
            "id",
            "finding_ref",
            "deficit_ref",
            "limitation_ref",
            "candidate_ref",
            "candidate_refs",
            "source_id",
            "source_ref",
            "claim_id",
            "claim_ids",
            "code",
        ):
            refs.extend(_as_graph_refs(value.get(key)))
        return _dedupe(refs)
    if isinstance(value, list | tuple | set):
        refs: list[str] = []
        for item in value:
            refs.extend(_as_graph_refs(item))
        return _dedupe(refs)
    return []


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def _claim_id(claim: dict[str, Any], index: int) -> str:
    return _text(claim.get("claim_id") or claim.get("id") or f"claim_{index + 1}")


def _claim_type(claim: dict[str, Any]) -> str:
    return _claim_family(claim)


def _normalize_family_token(value: object) -> str:
    token = re.sub(r"[^a-z0-9_]+", "_", _text(value).casefold()).strip("_")
    token = re.sub(r"_+", "_", token)
    return _CLAIM_FAMILY_ALIASES.get(token, token)


def _claim_family(claim: dict[str, Any]) -> str:
    raw = (
        claim.get("claim_family")
        or claim.get("family")
        or claim.get("claim_type")
        or claim.get("type")
    )
    family = _normalize_family_token(raw)
    if family:
        return family
    if _is_numerical_claim(claim):
        return "numerical"
    return "recommendation"


def _claim_text(claim: dict[str, Any]) -> str:
    return _text(claim.get("text") or claim.get("claim") or claim.get("statement"))


def _normalize_signature_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _is_major_claim(claim: dict[str, Any]) -> bool:
    value = claim.get("major")
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() not in {"false", "0", "no", "minor"}
    return bool(value)


def _documented_no_grounding_rationale(claim: dict[str, Any]) -> str:
    return _text(
        claim.get("no_grounding_rationale")
        or claim.get("grounding_rationale")
        or claim.get("not_grounded_rationale")
    )


def _data_refs(claim: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in (
        "data_refs",
        "data_source_refs",
        "source_refs",
        "fabric_refs",
        "data_snapshot_refs",
    ):
        refs.extend(_as_refs(claim.get(key)))
    return refs


def _method_refs(claim: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("method_refs", "foundry_method_refs", "analysis_refs"):
        refs.extend(_as_refs(claim.get(key)))
    return refs


def _norm_refs(claim: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("norm_refs", "normative_refs", "norm_ids", "legal_refs"):
        refs.extend(_as_refs(claim.get(key)))
    return refs


def _graph_refs_for_aliases(claim: dict[str, Any], aliases: tuple[str, ...]) -> list[str]:
    refs: list[str] = []
    for key in aliases:
        refs.extend(_as_graph_refs(claim.get(key)))
    graph = claim.get("evidence_graph")
    if isinstance(graph, Mapping):
        for key in aliases:
            refs.extend(_as_graph_refs(graph.get(key)))
    return _dedupe(refs)


def _major_claim_evidence_graph(claim: dict[str, Any]) -> dict[str, list[str]]:
    graph: dict[str, list[str]] = {
        "portfolio_refs": [],
        "independence_refs": [],
        "synthesis_refs": [],
        "argument_refs": [],
        "warrant_refs": [],
        "ir_analytics_refs": _graph_refs_for_aliases(claim, ("ir_analytics_refs",)),
        "ir_certificate_refs": _graph_refs_for_aliases(claim, ("ir_certificate_refs",)),
        "negative_certificate_refs": _graph_refs_for_aliases(
            claim,
            ("negative_certificate_refs",),
        ),
        "proof_composability_refs": _graph_refs_for_aliases(
            claim,
            ("proof_composability_refs",),
        ),
        "uncertainty_refs": _graph_refs_for_aliases(claim, ("uncertainty_refs",)),
        "baseline_refs": _graph_refs_for_aliases(claim, ("baseline_refs",)),
        "conflict_refs": _graph_refs_for_aliases(claim, ("conflict_refs",)),
        "rebuttal_or_counter_evidence_refs": _graph_refs_for_aliases(
            claim,
            _REBUTTAL_COUNTER_REF_ALIASES,
        ),
        "limitation_refs": _graph_refs_for_aliases(
            claim,
            _LIMITATION_DEFICIT_REF_ALIASES,
        ),
    }
    for canonical_key, aliases, _label, _code in _MAJOR_CLAIM_EVIDENCE_GRAPH_REF_SPECS:
        graph[canonical_key] = _graph_refs_for_aliases(claim, aliases)
    return graph


def _major_claim_evidence_graph_issues(
    *,
    claim_id: str,
    claim_text: str,
    graph: Mapping[str, list[str]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for canonical_key, _aliases, label, code in _MAJOR_CLAIM_EVIDENCE_GRAPH_REF_SPECS:
        if graph.get(canonical_key):
            continue
        issues.append(
            _issue(
                code=code,
                claim_id=claim_id,
                claim_text=claim_text,
                missing_evidence_type=label,
                message=f"Major policy claim {claim_id} has no {label} refs.",
                next_action=(
                    "Bind the claim to the runtime evidence graph before approval."
                ),
            )
        )
    if not graph.get("rebuttal_or_counter_evidence_refs"):
        issues.append(
            _issue(
                code="major_claim_rebuttal_or_counter_evidence_refs_missing",
                claim_id=claim_id,
                claim_text=claim_text,
                missing_evidence_type="rebuttal_or_counter_evidence",
                message=(
                    f"Major policy claim {claim_id} has no rebuttal or "
                    "counter-evidence refs."
                ),
                next_action=(
                    "Attach rebuttal, counter-evidence, or disconfirming evidence refs."
                ),
            )
        )
    if not graph.get("limitation_refs"):
        issues.append(
            _issue(
                code="major_claim_limitation_or_deficit_refs_missing",
                claim_id=claim_id,
                claim_text=claim_text,
                missing_evidence_type="limitation_or_deficit",
                message=(
                    f"Major policy claim {claim_id} has no accepted limitation or "
                    "deficit refs."
                ),
                next_action=(
                    "Attach accepted deficits, limitations, or typed degrade reasons "
                    "from runtime quality producers."
                ),
            )
        )
    return issues


def _production_data_quality_findings(
    report: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(report, dict):
        return []
    raw_findings = (
        report.get("findings")
        or report.get("issues")
        or report.get("scenario_binding_findings")
        or []
    )
    if not isinstance(raw_findings, list):
        return []
    return [dict(item) for item in raw_findings if isinstance(item, dict)]


def _data_quality_limitations_for_claim(
    *,
    claim_id: str,
    data_refs: list[str],
    limitation_refs: list[str],
    production_data_quality_report: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not limitation_refs:
        return []
    claim_ref_set = set(data_refs)
    limitation_ref_set = set(limitation_refs)
    matched: list[dict[str, Any]] = []
    for finding in _production_data_quality_findings(production_data_quality_report):
        finding_claim_ids = set(_as_graph_refs(finding.get("claim_ids")))
        finding_refs = set(
            _as_graph_refs(
                {
                    "evidence_ref": finding.get("evidence_ref"),
                    "finding_ref": finding.get("finding_ref"),
                    "ref": finding.get("ref"),
                    "id": finding.get("id"),
                    "code": finding.get("code"),
                }
            )
        )
        candidate_refs = set(
            _as_graph_refs(
                {
                    "candidate_ref": finding.get("candidate_ref"),
                    "candidate_refs": finding.get("candidate_refs"),
                    "source_id": finding.get("source_id"),
                    "source_ref": finding.get("source_ref"),
                }
            )
        )
        if finding_refs.intersection(limitation_ref_set) or (
            claim_id in finding_claim_ids and candidate_refs.intersection(claim_ref_set)
        ):
            matched.append(finding)
    return matched


def _to_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _issue(
    *,
    code: str,
    message: str,
    claim_id: str | None = None,
    claim_text: str | None = None,
    missing_evidence_type: str | None = None,
    severity: str = "fail",
    next_action: str,
    **extra: object,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "layer": "scientist_policy_artifacts",
        "phase": "policy_grounding",
        "claim_id": claim_id,
        "claim_text": claim_text,
        "missing_evidence_type": missing_evidence_type,
        "message": message,
        "next_action": next_action,
        **extra,
    }


def _status_from_issues(issues: list[dict[str, Any]]) -> str:
    if any(issue.get("severity") == "fail" for issue in issues):
        return "fail"
    if any(issue.get("severity") == "warn" for issue in issues):
        return "warn"
    return "pass"


def _ordered_policy_grounding_issues(
    issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not any(issue.get("code") == "multi_model_policy_disagreement" for issue in issues):
        return issues

    def _rank(indexed_issue: tuple[int, dict[str, Any]]) -> tuple[int, int]:
        index, issue = indexed_issue
        code = _text(issue.get("code"))
        if code in _MAJOR_CLAIM_EVIDENCE_GRAPH_MISSING_CODES:
            return (2, index)
        if code == "multi_model_policy_disagreement":
            return (1, index)
        return (0, index)

    return [issue for _index, issue in sorted(enumerate(issues), key=_rank)]


def _claim_extraction_issues(
    claim_extraction_report: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(claim_extraction_report, dict):
        return []
    status = _text(
        claim_extraction_report.get("extraction_status")
        or claim_extraction_report.get("status")
    ).casefold()
    if status in {"", "pass", "passed", "ok", "success"}:
        return []
    review_required = bool(
        claim_extraction_report.get("human_review_required")
        or claim_extraction_report.get("review_required")
        or status in {"review", "review_required", "requires_review"}
    )
    raw_issues = claim_extraction_report.get("issues")
    issue_codes: list[str] = []
    if isinstance(raw_issues, list):
        issue_codes = [
            _text(issue.get("code"))
            for issue in raw_issues
            if isinstance(issue, dict) and _text(issue.get("code"))
        ]
    if review_required:
        return [
            _issue(
                code="policy_claim_extraction_requires_review",
                severity="warn",
                missing_evidence_type="policy_claim",
                message=(
                    "Final policy claim extraction did not pass automatically and "
                    "requires human review."
                ),
                next_action=(
                    "Review the final policy claims sidecar, confirm major/minor "
                    "status and claim families, then rerun grounding."
                ),
                extraction_status=status,
                extraction_issue_codes=issue_codes,
            )
        ]
    return [
        _issue(
            code="policy_claim_extraction_failed",
            missing_evidence_type="policy_claim",
            message="Final policy claim extraction failed.",
            next_action=(
                "Regenerate the final policy artifact with structured claims or "
                "route it to human review before approving serious quality."
            ),
            extraction_status=status,
            extraction_issue_codes=issue_codes,
        )
    ]


def _applied_norm_refs(normative_evidence: dict[str, Any] | None) -> set[str]:
    if not isinstance(normative_evidence, dict):
        return set()
    refs: set[str] = set()
    for norm in normative_evidence.get("applied_norms") or []:
        if not isinstance(norm, dict):
            continue
        for key in ("norm_id", "id", "artifact_id"):
            value = _text(norm.get(key))
            if value:
                refs.add(value)
    return refs


def _selected_data_refs(fabric_retrieval_trace: dict[str, Any] | None) -> set[str]:
    if not isinstance(fabric_retrieval_trace, dict):
        return set()
    refs: set[str] = set()
    for source in fabric_retrieval_trace.get("selected_sources") or []:
        if not isinstance(source, dict):
            continue
        for key in (
            "source_id",
            "id",
            "binding_id",
            "source_family",
            "data_source_family",
            "artifact_id",
            "data_snapshot_ref",
            "input_bindings_ref",
        ):
            value = _text(source.get(key))
            if value:
                refs.add(value)
    return refs


def _selected_methods(
    foundry_method_report: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(foundry_method_report, dict):
        return []
    return [
        method
        for method in foundry_method_report.get("selected_methods") or []
        if isinstance(method, dict)
    ]


def _method_ref_values(method: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for key in (
        "method_id",
        "id",
        "method_fqn",
        "artifact_id",
        "output_ref",
        "method_output_ref",
        "result_ref",
    ):
        value = _text(method.get(key))
        if value:
            refs.add(value)
    return refs


def _selected_method_refs(foundry_method_report: dict[str, Any] | None) -> set[str]:
    refs: set[str] = set()
    for method in _selected_methods(foundry_method_report):
        refs.update(_method_ref_values(method))
    return refs


def _runtime_claim_registry_method_refs(
    claim_registry: Mapping[str, Any] | None,
) -> set[str]:
    refs: set[str] = set()
    if not isinstance(claim_registry, Mapping):
        return refs
    rows = claim_registry.get("claims")
    if not isinstance(rows, list):
        return refs
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        refs.update(_as_graph_refs(row.get("method_output_refs")))
        refs.update(_as_graph_refs(row.get("method_refs")))
        selected = row.get("selected_producer_refs")
        if isinstance(selected, Mapping):
            refs.update(_as_graph_refs(selected.get("ir_analytics")))
            refs.update(_as_graph_refs(selected.get("foundry")))
    return refs


def _numeric_claim_parts(claim: dict[str, Any]) -> tuple[str, float | None, float | None]:
    nested = claim.get("numeric_claim")
    if not isinstance(nested, dict):
        nested = {}
    metric = _text(claim.get("metric") or nested.get("metric"))
    value = _to_float(
        claim.get("value")
        if "value" in claim
        else (
            claim.get("numeric_value")
            if "numeric_value" in claim
            else claim.get("claim_value", nested.get("value"))
        )
    )
    tolerance = _to_float(claim.get("tolerance") or nested.get("tolerance"))
    return metric, value, tolerance


def _is_numerical_claim(claim: dict[str, Any]) -> bool:
    raw_family = (
        claim.get("claim_family")
        or claim.get("family")
        or claim.get("claim_type")
        or claim.get("type")
    )
    if _normalize_family_token(raw_family) == "numerical":
        return True
    metric, value, _tolerance = _numeric_claim_parts(claim)
    return bool(metric and value is not None)


def _is_recommendation_claim(claim: dict[str, Any]) -> bool:
    return _claim_family(claim) == "recommendation"


def _recommendation_signature(claim: dict[str, Any]) -> str | None:
    if not _is_recommendation_claim(claim) or not _is_major_claim(claim):
        return None
    action = _text(
        claim.get("policy_action")
        or claim.get("action")
        or claim.get("intervention")
        or claim.get("intervention_type")
    )
    if action:
        return _normalize_signature_text(action)
    text = _claim_text(claim)
    return _normalize_signature_text(text) if text else None


def _variant_id(variant: dict[str, Any], index: int) -> str:
    return _text(
        variant.get("model_variant_id")
        or variant.get("variant_id")
        or variant.get("model")
        or f"variant_{index + 1}"
    )


def _variant_claims(variant: dict[str, Any]) -> list[dict[str, Any]]:
    raw_claims = (
        variant.get("claims")
        or variant.get("policy_claims")
        or variant.get("recommendations")
        or []
    )
    if not isinstance(raw_claims, list):
        return []
    return [claim for claim in raw_claims if isinstance(claim, dict)]


def _variant_recommendation_signatures(variant: dict[str, Any]) -> list[str]:
    signatures = [
        signature
        for signature in (
            _recommendation_signature(claim) for claim in _variant_claims(variant)
        )
        if signature
    ]
    return sorted(set(signatures))


def _variant_ref(variant: dict[str, Any], index: int) -> dict[str, str]:
    ref: dict[str, str] = {"model_variant_id": _variant_id(variant, index)}
    for key in (
        "model",
        "provider",
        "trinity_bundle_ref",
        "final_policy_claims_ref",
        "policy_grounding_matrix_ref",
        "llm_model_adjudication_ref",
    ):
        value = _text(variant.get(key))
        if value:
            ref[key] = value
    return ref


def _multi_model_disagreements(
    model_variants: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if len(model_variants) < 2:
        return []
    signatures_by_variant: dict[str, list[str]] = {}
    variant_refs: list[dict[str, str]] = []
    for index, variant in enumerate(model_variants):
        signatures = _variant_recommendation_signatures(variant)
        if signatures:
            variant_id = _variant_id(variant, index)
            signatures_by_variant[variant_id] = signatures
            variant_refs.append(_variant_ref(variant, index))
    if len(signatures_by_variant) < 2:
        return []
    unique_signatures = {tuple(signatures) for signatures in signatures_by_variant.values()}
    if len(unique_signatures) <= 1:
        return []
    return [
        {
            "code": "multi_model_policy_disagreement",
            "severity": "fail",
            "message": (
                "LLM model variants produced materially different major "
                "recommendation actions."
            ),
            "missing_evidence_type": "model_consensus",
            "next_action": (
                "Run policy adjudication across model variants and persist the "
                "chosen recommendation with disagreement rationale."
            ),
            "variant_refs": variant_refs,
            "variant_signatures": signatures_by_variant,
        }
    ]


def _normalize_adjudication_decision(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if isinstance(value.get("decision"), dict):
        decision = dict(value["decision"])
        artifact_ref = _text(
            value.get("artifact_ref")
            or value.get("llm_model_adjudication_ref")
            or decision.get("artifact_ref")
        )
        if artifact_ref:
            decision["artifact_ref"] = artifact_ref
        if not decision.get("disagreements") and isinstance(value.get("disagreements"), list):
            decision["disagreements"] = [
                dict(item) for item in value["disagreements"] if isinstance(item, dict)
            ]
        return decision
    return dict(value)


def _adjudication_covers_disagreements(
    *,
    adjudication_decision: dict[str, Any] | None,
    disagreements: list[dict[str, Any]],
    model_variants: list[dict[str, Any]],
) -> tuple[bool, str]:
    if not disagreements:
        return True, "not_required"
    if not isinstance(adjudication_decision, dict):
        return False, "missing"
    variant_ids = {
        _variant_id(variant, index) for index, variant in enumerate(model_variants)
    }
    selected_variant_id = _text(
        adjudication_decision.get("selected_variant_id")
        or adjudication_decision.get("model_variant_id")
        or adjudication_decision.get("variant_id")
    )
    rationale = _text(
        adjudication_decision.get("rationale")
        or adjudication_decision.get("selected_variant_rationale")
    )
    evidence_refs = _as_refs(
        adjudication_decision.get("evidence_refs")
        or adjudication_decision.get("selected_variant_evidence_refs")
    )
    decision_code = _text(adjudication_decision.get("code"))
    covered_codes = set(_as_refs(adjudication_decision.get("disagreement_codes")))
    if not covered_codes and isinstance(adjudication_decision.get("disagreements"), list):
        covered_codes = {
            _text(item.get("code"))
            for item in adjudication_decision["disagreements"]
            if isinstance(item, dict) and _text(item.get("code"))
        }
    disagreement_codes = {_text(item.get("code")) for item in disagreements}
    if selected_variant_id not in variant_ids:
        return False, "selected_variant_missing"
    if not rationale:
        return False, "rationale_missing"
    if not evidence_refs:
        return False, "evidence_refs_missing"
    if decision_code != "llm_model_variant_adjudication":
        return False, "decision_code_invalid"
    if not disagreement_codes.issubset(covered_codes):
        return False, "disagreement_codes_missing"
    return True, "covered"


def _multi_model_disagreement_issues(
    model_variants: list[dict[str, Any]],
    *,
    adjudication_decision: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    disagreements = _multi_model_disagreements(model_variants)
    covered, adjudication_status = _adjudication_covers_disagreements(
        adjudication_decision=adjudication_decision,
        disagreements=disagreements,
        model_variants=model_variants,
    )
    if covered:
        return disagreements, []
    issues = [
        _issue(
            code=str(disagreement.get("code") or "multi_model_policy_disagreement"),
            severity="fail",
            missing_evidence_type="model_consensus",
            message=str(
                disagreement.get("message")
                or "LLM model variants produced materially different recommendations."
            ),
            next_action=str(
                disagreement.get("next_action")
                or "Persist a model-variant adjudication decision before approval."
            ),
            variant_refs=list(disagreement.get("variant_refs") or []),
            variant_signatures=dict(disagreement.get("variant_signatures") or {}),
            adjudication_status=adjudication_status,
        )
        for disagreement in disagreements
    ]
    return disagreements, issues


def _matching_methods(
    methods: list[dict[str, Any]],
    *,
    method_refs: list[str],
) -> list[dict[str, Any]]:
    if not method_refs:
        return methods
    wanted = set(method_refs)
    return [method for method in methods if _method_ref_values(method).intersection(wanted)]


def _method_evidence_ref(method: dict[str, Any]) -> str | None:
    for key in (
        "output_ref",
        "method_output_ref",
        "result_ref",
        "artifact_id",
        "method_id",
        "id",
        "method_fqn",
    ):
        value = _text(method.get(key))
        if value:
            return value
    return None


def _method_metric_output(
    methods: list[dict[str, Any]],
    *,
    method_refs: list[str],
    metric: str,
) -> tuple[float | None, str | None]:
    for method in _matching_methods(methods, method_refs=method_refs):
        result_summary = method.get("result_summary")
        if not isinstance(result_summary, dict) or metric not in result_summary:
            continue
        value = _to_float(result_summary.get(metric))
        if value is not None:
            return value, _method_evidence_ref(method)
    return None, None


def _has_grounding_refs(
    *,
    data_refs: list[str],
    method_refs: list[str],
    norm_refs: list[str],
) -> bool:
    return bool(data_refs or method_refs or norm_refs)


def _missing_family_grounding(
    *,
    claim_family: str,
    data_refs: list[str],
    method_refs: list[str],
    norm_refs: list[str],
) -> list[str]:
    missing: list[str] = []
    for required in _CLAIM_FAMILY_REQUIRED_GROUNDING.get(claim_family, ()):
        if (
            (required == "data" and not data_refs)
            or (required == "method" and not method_refs)
            or (required == "norm" and not norm_refs)
        ):
            missing.append(required)
    return missing


def _missing_evidence_label(missing: list[str]) -> str:
    return "_and_".join(missing) if missing else ""


def _validate_ref_set(
    *,
    claim_id: str,
    claim_text: str,
    refs: list[str],
    allowed_refs: set[str],
    code: str,
    message_prefix: str,
    next_action: str,
) -> list[dict[str, Any]]:
    missing = [ref for ref in refs if ref not in allowed_refs]
    if not missing:
        return []
    return [
        _issue(
            code=code,
            claim_id=claim_id,
            claim_text=claim_text,
            message=f"{message_prefix}: {', '.join(missing)}.",
            next_action=next_action,
            missing_refs=missing,
        )
    ]


def _allows_no_grounding_rationale(*, claim_family: str, rationale: str) -> bool:
    if claim_family in {"implementation", "caveat"}:
        return True
    lowered = rationale.casefold()
    return (
        "no new empirical" in lowered
        or "no empirical" in lowered
        or "no legal" in lowered
        or "operational" in lowered
        or "procedural" in lowered
    )


def _validate_claim(
    claim: dict[str, Any],
    *,
    index: int,
    applied_norm_refs: set[str],
    selected_data_refs: set[str],
    selected_method_refs: set[str],
    selected_methods: list[dict[str, Any]],
    default_numeric_tolerance: float,
    production_data_quality_report: dict[str, Any] | None = None,
    enforce_claim_support_semantics: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    claim_id = _claim_id(claim, index)
    claim_text = _claim_text(claim)
    claim_family = _claim_family(claim)
    data_refs = _data_refs(claim)
    method_refs = _method_refs(claim)
    norm_refs = _norm_refs(claim)
    no_grounding_rationale = _documented_no_grounding_rationale(claim)
    claim_is_major = _is_major_claim(claim)
    evidence_graph = _major_claim_evidence_graph(claim)
    evidence_graph["data_refs"] = data_refs
    evidence_graph["method_refs"] = method_refs
    evidence_graph["norm_refs"] = norm_refs
    evidence_graph["data_quality_limitations"] = _data_quality_limitations_for_claim(
        claim_id=claim_id,
        data_refs=data_refs,
        limitation_refs=evidence_graph["limitation_refs"],
        production_data_quality_report=production_data_quality_report,
    )
    has_grounding = _has_grounding_refs(
        data_refs=data_refs,
        method_refs=method_refs,
        norm_refs=norm_refs,
    )
    issues: list[dict[str, Any]] = []

    if claim_family not in CLAIM_FAMILIES:
        issues.append(
            _issue(
                code="policy_claim_family_invalid",
                claim_id=claim_id,
                claim_text=claim_text,
                missing_evidence_type="claim_family",
                message=f"Policy claim {claim_id} has unsupported family {claim_family!r}.",
                next_action=(
                    "Classify the claim as recommendation, empirical, numerical, "
                    "causal, normative, forecast, distributional, implementation, "
                    "or caveat."
                ),
                claim_family=claim_family,
            )
        )

    if _is_recommendation_claim(claim) and claim_is_major:
        if not has_grounding and not no_grounding_rationale:
            issues.append(
                _issue(
                    code="major_claim_missing_grounding",
                    claim_id=claim_id,
                    claim_text=claim_text,
                    missing_evidence_type="data_or_method_or_norm",
                    message=f"Major policy claim {claim_id} has no grounding refs.",
                    next_action=(
                        "Attach data_refs, method_refs, norm_refs, or document why "
                        "the claim makes no empirical/legal assertion."
                    ),
                )
            )
        elif (
            not has_grounding
            and no_grounding_rationale
            and not _allows_no_grounding_rationale(
                claim_family=claim_family,
                rationale=no_grounding_rationale,
            )
        ):
            issues.append(
                _issue(
                    code="no_grounding_rationale_not_allowed",
                    claim_id=claim_id,
                    claim_text=claim_text,
                    missing_evidence_type="data_or_method_or_norm",
                    message=(
                        f"Major policy claim {claim_id} uses a no-grounding rationale "
                        "that does not explain why evidence is unnecessary."
                    ),
                    next_action=(
                        "Attach data_refs, method_refs, norm_refs, or revise the "
                        "rationale to show the claim is purely operational/caveated."
                    ),
                )
            )

    if claim_is_major and has_grounding:
        issues.extend(
            _major_claim_evidence_graph_issues(
                claim_id=claim_id,
                claim_text=claim_text,
                graph=evidence_graph,
            )
        )

    missing_required_grounding = _missing_family_grounding(
        claim_family=claim_family,
        data_refs=data_refs,
        method_refs=method_refs,
        norm_refs=norm_refs,
    )
    if missing_required_grounding:
        missing_evidence_type = _missing_evidence_label(missing_required_grounding)
        issues.append(
            _issue(
                code="claim_family_missing_required_grounding",
                severity="fail" if claim_is_major else "warn",
                claim_id=claim_id,
                claim_text=claim_text,
                missing_evidence_type=missing_evidence_type,
                message=(
                    f"{claim_family.title()} claim {claim_id} is missing required "
                    f"{missing_evidence_type} grounding."
                ),
                next_action=(
                    "Attach the evidence refs required for this claim family or "
                    "downgrade/remove the unsupported claim."
                ),
                claim_family=claim_family,
                required_grounding=list(
                    _CLAIM_FAMILY_REQUIRED_GROUNDING.get(claim_family, ())
                ),
            )
        )

    if (
        not has_grounding
        and not no_grounding_rationale
        and (not claim_is_major or claim_family in {"implementation", "caveat"})
    ):
        issues.append(
            _issue(
                code=(
                    "major_claim_missing_grounding_rationale"
                    if claim_is_major
                    else "minor_claim_missing_grounding_rationale"
                ),
                severity="fail" if claim_is_major else "warn",
                claim_id=claim_id,
                claim_text=claim_text,
                missing_evidence_type="data_or_method_or_norm",
                message=(
                    f"{'Major' if claim_is_major else 'Minor'} policy claim {claim_id} "
                    "has no grounding refs or no-grounding rationale."
                ),
                next_action=(
                    "Attach grounding refs or document why the claim makes no "
                    "empirical/legal assertion."
                ),
            )
        )

    issues.extend(
        _validate_ref_set(
            claim_id=claim_id,
            claim_text=claim_text,
            refs=data_refs,
            allowed_refs=selected_data_refs,
            code="data_claim_refs_not_selected",
            message_prefix=f"Claim {claim_id} references unselected data refs",
            next_action="Ground data claims in selected Fabric sources or snapshots.",
        )
    )
    issues.extend(
        _validate_ref_set(
            claim_id=claim_id,
            claim_text=claim_text,
            refs=method_refs,
            allowed_refs=selected_method_refs,
            code="method_claim_refs_not_selected",
            message_prefix=f"Claim {claim_id} references unselected Foundry methods",
            next_action="Ground method claims in selected Foundry method outputs.",
        )
    )
    issues.extend(
        _validate_ref_set(
            claim_id=claim_id,
            claim_text=claim_text,
            refs=norm_refs,
            allowed_refs=applied_norm_refs,
            code="normative_claim_refs_not_applicable",
            message_prefix=f"Claim {claim_id} references non-applicable norms",
            next_action="Replace norm refs with applied Lex norms or revise the claim.",
        )
    )

    if claim_family == "normative" and not norm_refs:
        issues.append(
            _issue(
                code="normative_claim_missing_applicable_norm",
                claim_id=claim_id,
                claim_text=claim_text,
                missing_evidence_type="norm",
                message=f"Normative claim {claim_id} has no applicable norm refs.",
                next_action="Attach applicable Lex norm refs or remove the legal claim.",
            )
        )

    if _is_numerical_claim(claim):
        metric, value, declared_tolerance = _numeric_claim_parts(claim)
        if value is None or not metric:
            issues.append(
                _issue(
                    code="numeric_claim_unreadable",
                    claim_id=claim_id,
                    claim_text=claim_text,
                    missing_evidence_type="method_output",
                    message=f"Numerical claim {claim_id} is missing metric or value.",
                    next_action="Persist numerical claims with metric, value, and tolerance.",
                )
            )
        else:
            tolerance = (
                declared_tolerance
                if declared_tolerance is not None
                else default_numeric_tolerance
            )
            expected, evidence_ref = _method_metric_output(
                selected_methods,
                method_refs=method_refs,
                metric=metric,
            )
            if expected is None:
                issues.append(
                    _issue(
                        code="numeric_claim_missing_method_output",
                        claim_id=claim_id,
                        claim_text=claim_text,
                        missing_evidence_type="method_output",
                        message=(
                            f"Numerical claim {claim_id} has no matching Foundry "
                            f"output for metric {metric}."
                        ),
                        next_action=(
                            "Reference the Foundry method output used for the numeric "
                            "claim or recompute the policy artifact."
                        ),
                    )
                )
            elif abs(value - expected) > tolerance:
                issues.append(
                    _issue(
                        code="numeric_claim_mismatch",
                        claim_id=claim_id,
                        claim_text=claim_text,
                        message=(
                            f"Numerical claim {claim_id} value {value:g} differs "
                            f"from Foundry output {expected:g} for {metric}."
                        ),
                        next_action="Regenerate the claim from Foundry outputs or fix refs.",
                        metric=metric,
                        expected=expected,
                        observed=value,
                        evidence_ref=evidence_ref,
                        claimed_value=value,
                        foundry_value=expected,
                        tolerance=tolerance,
                    )
                )

    claim_support_payload: dict[str, Any] | None = None
    if enforce_claim_support_semantics:
        claim_support_payload, claim_support_issues = _claim_support_assessment_for_claim(
            claim,
            claim_id=claim_id,
            claim_text=claim_text,
            claim_family=claim_family,
            claim_is_major=claim_is_major,
        )
        issues.extend(claim_support_issues)

    normalized_claim = {
        **claim,
        "claim_id": claim_id,
        "claim_family": claim_family,
        "claim_type": claim_family,
        "major": claim_is_major,
        "text": claim_text,
        "grounding": {
            "data_refs": data_refs,
            "method_refs": method_refs,
            "norm_refs": norm_refs,
            "no_grounding_rationale": no_grounding_rationale or None,
        },
        "evidence_graph": evidence_graph,
        "grounding_status": _status_from_issues(issues),
    }
    if claim_support_payload is not None:
        normalized_claim["claim_support"] = claim_support_payload
    return normalized_claim, issues


def _claim_support_assessment_for_claim(
    claim: dict[str, Any],
    *,
    claim_id: str,
    claim_text: str,
    claim_family: str,
    claim_is_major: bool,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    support_family = _CLAIM_SUPPORT_FAMILY_BY_GROUNDING_FAMILY.get(claim_family)
    if support_family is None:
        return None, []
    support_claim = {
        **claim,
        "claim_id": claim_id,
        "claim_family": support_family,
        "text": claim_text,
    }
    try:
        assessment = evaluate_claim_support(support_claim)
    except ValueError:
        return None, []

    payload = {
        "schema_version": assessment.schema_version,
        "claim_id": assessment.claim_id,
        "claim_family": assessment.claim_family.value,
        "support_strength": assessment.support_strength.value,
        "publishability": assessment.publishability.value,
        "readiness_level": assessment.readiness_level.value,
        "satisfied_predicates": [
            predicate.value for predicate in assessment.satisfied_predicates
        ],
        "missing_predicates": [
            predicate.value for predicate in assessment.missing_predicates
        ],
        "required_predicates": [
            predicate.value for predicate in assessment.required_predicates
        ],
        "counterevidence_actions": [
            action.value for action in assessment.counterevidence_actions
        ],
        "lifecycle_transition": assessment.lifecycle_transition.value,
        "grounding_matrix_family": assessment.grounding_matrix_family,
        "grounding_matrix_checks": list(assessment.grounding_matrix_checks),
    }
    issues: list[dict[str, Any]] = []
    for issue in assessment.issues:
        copied = dict(issue)
        copied["claim_family"] = support_family
        copied["claim_id"] = claim_id
        copied["claim_text"] = claim_text
        copied.setdefault("layer", "scientist_policy_artifacts")
        copied["phase"] = "claim_support"
        if claim_is_major and copied.get("severity") == "warn":
            copied["severity"] = "fail"
        issues.append(copied)
    return payload, issues


def _fold_quality_report_issues(
    report: dict[str, Any] | None,
    *,
    phase: str,
    missing_evidence_type: str,
) -> list[dict[str, Any]]:
    if not isinstance(report, dict):
        return []
    status = str(report.get("status") or "pass")
    if status == "pass":
        return []
    raw_issues = report.get("issues")
    if not isinstance(raw_issues, list) or not raw_issues:
        return [
            _issue(
                code=f"{phase}_failed",
                missing_evidence_type=missing_evidence_type,
                severity="fail" if status == "fail" else "warn",
                message=f"{phase} report returned status {status}.",
                next_action="Inspect the quality report and repair the failing evidence gate.",
            )
        ]
    folded: list[dict[str, Any]] = []
    for item in raw_issues:
        if not isinstance(item, dict):
            continue
        severity = item.get("severity")
        if severity not in {"fail", "warn"}:
            severity = "fail" if status == "fail" else "warn"
        copied = {
            **item,
            "severity": severity,
            "layer": item.get("layer") or "scientist_policy_artifacts",
            "phase": phase,
            "missing_evidence_type": item.get("missing_evidence_type")
            or missing_evidence_type,
            "message": item.get("message") or f"{phase} report issue.",
            "next_action": item.get("next_action")
            or "Repair the underlying quality report issue before publication.",
        }
        folded.append(copied)
    return folded


def _causal_statistical_validity_issues(
    report: dict[str, Any] | None,
    *,
    normalized_claims: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(report, dict):
        return []
    status = _text(report.get("status") or "pass").casefold()
    if status == "pass":
        return []

    relying_claims = [
        claim
        for claim in normalized_claims
        if _is_major_claim(claim)
        and _claim_family(claim) in {"causal", "numerical"}
        and _method_refs(claim)
    ]
    if not relying_claims:
        return []

    claim_ids = [_claim_id(claim, index) for index, claim in enumerate(relying_claims)]
    method_refs = sorted({ref for claim in relying_claims for ref in _method_refs(claim)})
    raw_issues = report.get("issues")
    if not isinstance(raw_issues, list) or not raw_issues:
        return [
            _issue(
                code="causal_statistical_validity_failed",
                severity="fail" if status == "fail" else "warn",
                missing_evidence_type="causal_statistical_validity",
                message=(
                    "Causal/statistical validity report failed for a final major "
                    "causal or numerical claim."
                ),
                next_action=(
                    "Repair the Foundry causal/statistical validity benchmark report "
                    "or downgrade the unsupported final claim."
                ),
                phase="causal_statistical_validity",
                claim_ids=claim_ids,
                method_refs=method_refs,
            )
        ]

    folded: list[dict[str, Any]] = []
    for item in raw_issues:
        if not isinstance(item, dict):
            continue
        code = _text(item.get("code")) or "causal_statistical_validity_failed"
        severity = item.get("severity")
        if code in {
            "power_failure",
            "sample_adequacy_failure",
            "sensitivity_failure",
            "missingness_stress_failure",
            "uncertainty_calibration_failure",
        }:
            severity = "fail"
        elif severity not in {"fail", "warn"}:
            severity = "fail" if status == "fail" else "warn"
        copied = {
            **item,
            "code": code,
            "severity": severity,
            "layer": item.get("layer") or "scientist_policy_artifacts",
            "phase": "causal_statistical_validity",
            "missing_evidence_type": item.get("missing_evidence_type")
            or "causal_statistical_validity",
            "message": item.get("message")
            or "Causal/statistical validity report failed.",
            "next_action": item.get("next_action")
            or "Repair the causal/statistical validity benchmark before publication.",
            "claim_ids": claim_ids,
            "method_refs": method_refs,
        }
        folded.append(copied)
    return folded


def build_policy_grounding_matrix_report(
    *,
    claims: list[dict[str, Any]],
    model_variants: list[dict[str, Any]] | None = None,
    adjudication_decision: dict[str, Any] | None = None,
    claim_extraction_report: dict[str, Any] | None = None,
    normative_evidence: dict[str, Any] | None = None,
    fabric_retrieval_trace: dict[str, Any] | None = None,
    foundry_method_report: dict[str, Any] | None = None,
    citation_faithfulness_report: dict[str, Any] | None = None,
    source_quality_report: dict[str, Any] | None = None,
    production_data_quality_report: dict[str, Any] | None = None,
    causal_statistical_validity_report: dict[str, Any] | None = None,
    claim_registry: Mapping[str, Any] | None = None,
    ir_analytics_bridge: Mapping[str, Any] | None = None,
    enforce_claim_support_semantics: bool = False,
    default_numeric_tolerance: float = 1e-6,
    spine_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a strict grounding report for final policy claims."""
    applied_norm_refs = _applied_norm_refs(normative_evidence)
    selected_data_refs = _selected_data_refs(fabric_retrieval_trace)
    selected_method_refs = _selected_method_refs(foundry_method_report)
    selected_methods = _selected_methods(foundry_method_report)
    normalized_claim_registry = (
        normalize_runtime_claim_registry(
            claim_registry,
            claims=claims,
            normative_evidence=normative_evidence,
            fabric_retrieval_trace=fabric_retrieval_trace,
            foundry_method_report=foundry_method_report,
            ir_analytics_bridge=ir_analytics_bridge,
        )
        if claim_registry is not None
        else None
    )
    claim_registry_rows = claim_registry_rows_by_id(normalized_claim_registry)
    selected_method_refs = {
        *selected_method_refs,
        *_runtime_claim_registry_method_refs(normalized_claim_registry),
    }

    normalized_claims: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    issues.extend(_claim_extraction_issues(claim_extraction_report))
    if normalized_claim_registry is not None:
        issues.extend(
            [
                {
                    **dict(issue),
                    "layer": dict(issue).get("layer") or "runtime_quality",
                    "phase": "runtime_claim_registry",
                }
                for issue in normalized_claim_registry.get("issues", [])
                if isinstance(issue, dict)
            ]
        )
    if not claims:
        issues.append(
            _issue(
                code="no_policy_claims",
                missing_evidence_type="policy_claim",
                message="Policy grounding matrix has no policy claims.",
                next_action=(
                    "Persist final recommendations and numeric/legal claims before "
                    "judging grounding quality."
                ),
            )
        )

    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            continue
        claim_for_validation = apply_runtime_claim_registry_to_claim(
            claim,
            claim_registry_rows.get(_claim_id(claim, index)),
        )
        normalized_claim, claim_issues = _validate_claim(
            claim_for_validation,
            index=index,
            applied_norm_refs=applied_norm_refs,
            selected_data_refs=selected_data_refs,
            selected_method_refs=selected_method_refs,
            selected_methods=selected_methods,
            default_numeric_tolerance=default_numeric_tolerance,
            production_data_quality_report=production_data_quality_report,
            enforce_claim_support_semantics=enforce_claim_support_semantics,
        )
        normalized_claims.append(normalized_claim)
        issues.extend(claim_issues)
    if normalized_claims and not any(_is_major_claim(claim) for claim in normalized_claims):
        issues.append(
            _issue(
                code="no_major_policy_claims",
                missing_evidence_type="policy_claim",
                message="Final policy artifact has no machine-readable major claims.",
                next_action=(
                    "Mark at least one final recommendation or decision claim as major, "
                    "or route the artifact for human review before approval."
                ),
            )
        )
    normalized_model_variants = [
        dict(variant)
        for variant in (model_variants or [])
        if isinstance(variant, dict)
    ]
    normalized_adjudication_decision = _normalize_adjudication_decision(
        adjudication_decision
    )
    disagreements, disagreement_issues = _multi_model_disagreement_issues(
        normalized_model_variants,
        adjudication_decision=normalized_adjudication_decision,
    )
    issues.extend(disagreement_issues)
    issues.extend(
        _fold_quality_report_issues(
            citation_faithfulness_report,
            phase="citation_faithfulness",
            missing_evidence_type="citation_faithfulness",
        )
    )
    issues.extend(
        _fold_quality_report_issues(
            source_quality_report,
            phase="source_quality",
            missing_evidence_type="source_quality",
        )
    )
    issues.extend(
        _causal_statistical_validity_issues(
            causal_statistical_validity_report,
            normalized_claims=normalized_claims,
        )
    )
    issues = _ordered_policy_grounding_issues(issues)

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": _status_from_issues(issues),
        "claims": normalized_claims,
        "model_variants": normalized_model_variants,
        "disagreements": disagreements,
        "adjudication_decision": normalized_adjudication_decision,
        "citation_faithfulness": (
            dict(citation_faithfulness_report)
            if isinstance(citation_faithfulness_report, dict)
            else None
        ),
        "source_quality": (
            dict(source_quality_report)
            if isinstance(source_quality_report, dict)
            else None
        ),
        "production_data_quality": (
            dict(production_data_quality_report)
            if isinstance(production_data_quality_report, dict)
            else None
        ),
        "causal_statistical_validity": (
            dict(causal_statistical_validity_report)
            if isinstance(causal_statistical_validity_report, dict)
            else None
        ),
        "claim_extraction": (
            dict(claim_extraction_report)
            if isinstance(claim_extraction_report, dict)
            else None
        ),
        "runtime_claim_registry": normalized_claim_registry,
        "issues": issues,
        "blocking_issue_count": sum(1 for issue in issues if issue.get("severity") == "fail"),
        "summary": {
            "claim_count": len(normalized_claims),
            "major_claim_count": sum(
                1 for claim in normalized_claims if _is_major_claim(claim)
            ),
            "applied_norm_ref_count": len(applied_norm_refs),
            "selected_data_ref_count": len(selected_data_refs),
            "selected_method_ref_count": len(selected_method_refs),
            "disagreement_count": len(disagreements),
            "adjudicated_disagreement_count": (
                len(disagreements) if disagreements and not disagreement_issues else 0
            ),
            "runtime_claim_registry_entry_count": (
                int(
                    (normalized_claim_registry or {})
                    .get("summary", {})
                    .get("entry_count", 0)
                )
                if normalized_claim_registry is not None
                else 0
            ),
            "runtime_claim_registry_status": (
                normalized_claim_registry.get("status")
                if isinstance(normalized_claim_registry, dict)
                else None
            ),
        },
    }
    if spine_context is not None:
        from polisyos.core import contracts as core_contracts

        report.update(
            core_contracts.build_producer_spine_binding_fields(
                component="scientist",
                spine_context=spine_context,
                candidate_refs=[_claim_id(claim, index) for index, claim in enumerate(claims)],
                blocker_refs=[issue.get("code") for issue in issues],
            )
        )
    return report


def normalize_policy_grounding_matrix(
    report: dict[str, Any],
    *,
    normative_evidence: dict[str, Any] | None = None,
    fabric_retrieval_trace: dict[str, Any] | None = None,
    foundry_method_report: dict[str, Any] | None = None,
    citation_faithfulness_report: dict[str, Any] | None = None,
    source_quality_report: dict[str, Any] | None = None,
    production_data_quality_report: dict[str, Any] | None = None,
    causal_statistical_validity_report: dict[str, Any] | None = None,
    claim_registry: Mapping[str, Any] | None = None,
    ir_analytics_bridge: Mapping[str, Any] | None = None,
    enforce_claim_support_semantics: bool = False,
    default_numeric_tolerance: float = 1e-6,
) -> dict[str, Any]:
    """Recompute policy grounding status from claims and evidence refs."""
    if not isinstance(report, dict):
        report = {}
    raw_claims = (
        report.get("claims")
        or report.get("policy_claims")
        or report.get("recommendations")
        or []
    )
    claims = [claim for claim in raw_claims if isinstance(claim, dict)] if isinstance(
        raw_claims,
        list,
    ) else []
    raw_model_variants = (
        report.get("model_variants")
        or report.get("llm_model_variants")
        or report.get("variant_claims")
        or []
    )
    model_variants = (
        [variant for variant in raw_model_variants if isinstance(variant, dict)]
        if isinstance(raw_model_variants, list)
        else []
    )
    raw_adjudication_decision = (
        report.get("adjudication_decision")
        if isinstance(report.get("adjudication_decision"), dict)
        else report.get("llm_model_adjudication")
        if isinstance(report.get("llm_model_adjudication"), dict)
        else report.get("model_adjudication")
        if isinstance(report.get("model_adjudication"), dict)
        else None
    )
    normalized = build_policy_grounding_matrix_report(
        claims=claims,
        model_variants=model_variants,
        adjudication_decision=raw_adjudication_decision,
        claim_extraction_report=(
            report.get("claim_extraction")
            if isinstance(report.get("claim_extraction"), dict)
            else report.get("claim_extraction_report")
            if isinstance(report.get("claim_extraction_report"), dict)
            else None
        ),
        normative_evidence=normative_evidence,
        fabric_retrieval_trace=fabric_retrieval_trace,
        foundry_method_report=foundry_method_report,
        citation_faithfulness_report=(
            citation_faithfulness_report
            if citation_faithfulness_report is not None
            else report.get("citation_faithfulness")
            if isinstance(report.get("citation_faithfulness"), dict)
            else None
        ),
        source_quality_report=(
            source_quality_report
            if source_quality_report is not None
            else report.get("source_quality")
            if isinstance(report.get("source_quality"), dict)
            else None
        ),
        production_data_quality_report=(
            production_data_quality_report
            if production_data_quality_report is not None
            else report.get("production_data_quality")
            if isinstance(report.get("production_data_quality"), dict)
            else None
        ),
        causal_statistical_validity_report=(
            causal_statistical_validity_report
            if causal_statistical_validity_report is not None
            else report.get("causal_statistical_validity")
            if isinstance(report.get("causal_statistical_validity"), dict)
            else None
        ),
        claim_registry=(
            claim_registry
            if claim_registry is not None
            else report.get("runtime_claim_registry")
            if isinstance(report.get("runtime_claim_registry"), Mapping)
            else report.get("claim_registry")
            if isinstance(report.get("claim_registry"), Mapping)
            else None
        ),
        ir_analytics_bridge=(
            ir_analytics_bridge
            if ir_analytics_bridge is not None
            else report.get("ir_analytics_bridge")
            if isinstance(report.get("ir_analytics_bridge"), Mapping)
            else None
        ),
        enforce_claim_support_semantics=enforce_claim_support_semantics,
        default_numeric_tolerance=default_numeric_tolerance,
    )
    return {**report, **normalized}


__all__ = [
    "CLAIM_FAMILIES",
    "SCHEMA_VERSION",
    "build_policy_grounding_matrix_report",
    "normalize_policy_grounding_matrix",
]
