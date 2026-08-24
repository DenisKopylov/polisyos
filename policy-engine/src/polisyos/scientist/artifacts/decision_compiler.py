"""Public decision artifact compiler for final policy outputs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from polisyos.core import contracts as core_contracts

build_policy_design_case_projection_from_runtime_graph = (
    core_contracts.build_policy_design_case_projection_from_runtime_graph
)
build_policy_design_case_projection_semantics = (
    core_contracts.build_policy_design_case_projection_semantics
)
detect_source_truth_conflict = core_contracts.detect_source_truth_conflict

DECISION_ARTIFACT_SCHEMA_VERSION = "policyos.scientist.decision_artifact.v1"
DRAFT_DECISION_PACKET_ARTIFACT_KIND = "draft_decision_packet"
PUBLISHABLE_DECISION_ARTIFACT_KIND = "publishable_decision_artifact"
POLICY_DESIGN_CASE_CLAIM_CONTRACT_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.claim_compiler_runtime_contract.v1"
)

REQUIRED_MAJOR_RECOMMENDATION_SECTIONS: tuple[str, ...] = (
    "support_summary",
    "uncertainty",
    "policy_tradeoffs",
    "distributional_impact",
    "implementation_feasibility",
    "budget_implication",
    "stakeholder_impact",
    "implementation_risks",
    "residual_uncertainty",
    "monitoring_plan",
    "withdrawal_reissue_triggers",
)

PUBLIC_FORBIDDEN_KEY_TOKENS: tuple[str, ...] = (
    "access_token",
    "api_key",
    "bearer_token",
    "benchmark_answer",
    "credential",
    "credentials",
    "developer_prompt",
    "hidden_benchmark",
    "hidden_eval",
    "hidden_holdout",
    "password",
    "private_eval",
    "private_reviewer",
    "raw_records",
    "raw_sensitive",
    "raw_transcript",
    "reviewer_private",
    "secret",
    "sensitive_data",
    "system_prompt",
)

_RECOMMENDATION_FAMILIES = {
    "advice",
    "policy_recommendation",
    "recommendation",
}
_PASS_STATUSES = {"clear", "ok", "pass", "passed"}
_CONFLICT_STATUSES = {"blocked", "conflict", "fail", "failed"}
_APPROVAL_READY_STATES = {"approved", "approval_ready", "override_approved", "ready"}
_PUBLISHABLE_REQUIRED_SECTION_STATEMENTS: dict[str, str] = {
    "budget_implication": "budget_statement",
    "distributional_impact": "distributional_impact_statement",
    "implementation_feasibility": "feasibility_statement",
    "implementation_risks": "implementation_risk_statement",
    "monitoring_plan": "monitoring_statement",
    "policy_tradeoffs": "tradeoff_statement",
    "residual_uncertainty": "residual_uncertainty_statement",
    "withdrawal_reissue_triggers": "contestability_statement",
}
_SECTION_REF_ALIASES: dict[str, tuple[str, ...]] = {
    "budget_implication": (
        "budget_refs",
        "budget_evidence_refs",
        "fiscal_refs",
        "fiscal_evidence_refs",
    ),
    "distributional_impact": (
        "distributional_refs",
        "distributional_evidence_refs",
        "equity_refs",
        "equity_evidence_refs",
    ),
    "implementation_feasibility": (
        "feasibility_refs",
        "feasibility_evidence_refs",
        "implementation_feasibility_refs",
    ),
    "implementation_risks": (
        "risk_refs",
        "risk_evidence_refs",
        "implementation_risk_refs",
    ),
    "monitoring_plan": (
        "monitoring_refs",
        "monitoring_evidence_refs",
        "monitoring_signal_refs",
    ),
    "policy_tradeoffs": (
        "tradeoff_refs",
        "tradeoff_evidence_refs",
        "policy_tradeoff_refs",
    ),
    "residual_uncertainty": (
        "uncertainty_refs",
        "residual_uncertainty_refs",
        "uncertainty_evidence_refs",
    ),
    "withdrawal_reissue_triggers": (
        "contestability_refs",
        "contestability_evidence_refs",
        "appeals_refs",
        "appeals_evidence_refs",
        "withdrawal_reissue_trigger_refs",
    ),
}
_CLAIM_FAMILY_STATEMENT_SCOPES: dict[str, str] = {
    "budget": "budget_statement",
    "budget_implication": "budget_statement",
    "distributional": "distributional_impact_statement",
    "distributional_impact": "distributional_impact_statement",
    "feasibility": "feasibility_statement",
    "forecast": "major_claim",
    "implementation_risk": "implementation_risk_statement",
    "legal": "legal_assertion",
    "legal_assertion": "legal_assertion",
    "monitoring": "monitoring_statement",
    "normative": "legal_assertion",
    "policy_recommendation": "recommendation",
    "recommendation": "recommendation",
    "residual_uncertainty": "residual_uncertainty_statement",
    "risk": "implementation_risk_statement",
    "tradeoff": "tradeoff_statement",
}
_NESTED_STATEMENT_FIELDS: dict[str, str] = {
    "budget_statements": "budget_statement",
    "distributional_impact_statements": "distributional_impact_statement",
    "feasibility_statements": "feasibility_statement",
    "implementation_risk_statements": "implementation_risk_statement",
    "legal_assertions": "legal_assertion",
    "monitoring_statements": "monitoring_statement",
    "residual_uncertainties": "residual_uncertainty_statement",
    "tradeoffs": "tradeoff_statement",
}
_PDC_CLAIM_REQUIRED_REF_SPECS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("concept_refs", ("concept_refs", "policy_concept_refs"), "policy concept refs"),
    ("legal_norm_refs", ("legal_norm_refs", "norm_refs", "legal_refs"), "legal norm refs"),
    (
        "source_data_refs",
        ("source_data_refs", "data_refs", "source_refs", "dataset_refs"),
        "source/data refs",
    ),
    ("method_refs", ("method_refs", "foundry_method_refs"), "method refs"),
    (
        "portfolio_refs",
        ("portfolio_refs", "portfolio_design_refs", "evidence_portfolio_refs"),
        "portfolio refs",
    ),
    (
        "independence_refs",
        ("independence_refs", "independence_map_refs"),
        "independence refs",
    ),
    (
        "specification_curve_refs",
        (
            "specification_curve_refs",
            "multiverse_specification_curve_refs",
            "multiverse_curve_refs",
        ),
        "specification-curve refs",
    ),
    (
        "disconfirming_refs",
        ("disconfirming_refs", "disconfirming_evidence_refs", "disconfirming_ledger_refs"),
        "disconfirming refs",
    ),
    (
        "synthesis_refs",
        ("synthesis_refs", "synthesis_report_refs", "evidence_synthesis_refs"),
        "synthesis refs",
    ),
    (
        "objective_tradeoff_refs",
        ("objective_tradeoff_refs", "objective_refs", "tradeoff_refs"),
        "objective/tradeoff refs",
    ),
    (
        "uncertainty_refs",
        ("uncertainty_refs", "residual_uncertainty_refs", "foundry_uncertainty_refs"),
        "uncertainty refs",
    ),
    (
        "numerical_semantics_refs",
        ("numerical_semantics_refs", "number_semantics_refs", "unit_semantics_refs"),
        "numerical semantics refs",
    ),
    (
        "monitoring_refs",
        ("monitoring_refs", "monitoring_plan_refs", "implementation_monitoring_refs"),
        "monitoring refs",
    ),
)
_PDC_CLAIM_SCHOLAR_REF_KEYS = (
    "scholar_refs",
    "literature_refs",
    "scholar_literature_refs",
    "academic_evidence_refs",
)
_PDC_CLAIM_SCHOLAR_DEFICIT_KEYS = (
    "scholar_deficit_refs",
    "literature_deficit_refs",
    "accepted_literature_deficit_refs",
)
_PDC_CLAIM_PRODUCER_REF_SPECS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("lex", ("legal_norm_refs", "norm_refs", "legal_refs")),
    ("fabric", ("source_data_refs", "data_refs", "source_refs", "dataset_refs")),
    ("data_forge", ("source_data_refs", "data_refs", "source_refs", "dataset_refs")),
    ("scholar", _PDC_CLAIM_SCHOLAR_REF_KEYS),
    ("foundry", ("method_refs", "uncertainty_refs", "foundry_uncertainty_refs")),
    ("options_objectives", ("objective_tradeoff_refs", "objective_refs", "tradeoff_refs")),
)
_PDC_CLAIM_PROSE_BACKFILL_KEYS = (
    "support_summary",
    "evidence_summary",
    "grounding_summary",
    "claim_rationale",
    "rationale",
    "policy_tradeoffs",
    "residual_uncertainty",
    "monitoring_plan",
)


class DecisionArtifactCompilationError(ValueError):
    """Raised when a publishable decision artifact would violate closeout gates."""

    def __init__(
        self,
        message: str,
        *,
        issues: Sequence[Mapping[str, Any]],
        draft_artifact: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.issues = [dict(issue) for issue in issues]
        self.draft_artifact = dict(draft_artifact or {})


_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "support_summary": (
        "support_summary",
        "evidence_summary",
        "grounding_summary",
    ),
    "uncertainty": ("uncertainty", "uncertainty_language", "uncertainty_summary"),
    "policy_tradeoffs": ("policy_tradeoffs", "tradeoffs", "tradeoff_summary"),
    "distributional_impact": (
        "distributional_impact",
        "distributional_impacts",
        "equity_impact",
    ),
    "implementation_feasibility": (
        "implementation_feasibility",
        "feasibility",
        "delivery_feasibility",
    ),
    "budget_implication": (
        "budget_implication",
        "budget_implications",
        "fiscal_implication",
    ),
    "stakeholder_impact": (
        "stakeholder_impact",
        "stakeholder_impacts",
        "affected_stakeholders",
    ),
    "implementation_risks": (
        "implementation_risks",
        "implementation_risk",
        "delivery_risks",
    ),
    "residual_uncertainty": (
        "residual_uncertainty",
        "residual_uncertainties",
        "remaining_uncertainty",
    ),
    "monitoring_plan": (
        "monitoring_plan",
        "monitoring_requirement",
        "monitoring_requirements",
    ),
    "withdrawal_reissue_triggers": (
        "withdrawal_reissue_triggers",
        "withdrawal_triggers",
        "reissue_triggers",
    ),
}
_REF_KEYS = (
    "approval_packet_ref",
    "causal_statistical_validity_report_ref",
    "citation_faithfulness_report_ref",
    "claim_support_report_ref",
    "conflict_check_ref",
    "data_quality_report_ref",
    "decision_artifact_ref",
    "fabric_retrieval_trace_ref",
    "foundry_method_report_ref",
    "human_review_calibration_report_ref",
    "normative_applicability_report_ref",
    "policy_grounding_matrix_ref",
    "privacy_compliance_report_ref",
    "production_data_quality_report_ref",
    "quality_scorecard_ref",
    "resilience_report_ref",
    "security_assurance_report_ref",
    "source_quality_report_ref",
)


def compile_public_decision_artifact(
    *,
    run_id: str,
    final_claims: Sequence[Mapping[str, Any]],
    policy_grounding_matrix: Mapping[str, Any] | None,
    quality_scorecard: Mapping[str, Any] | None,
    conflict_check: Mapping[str, Any] | None,
    approval_state: Mapping[str, Any] | str | None,
    title: str | None = None,
    performance_warnings: Sequence[Mapping[str, Any] | str] | None = None,
    assurance_refs: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    spine_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile a structured public decision candidate from final policy outputs.

    The compiler is deterministic and public-only: it preserves citation refs and
    selected quality refs while recursively dropping known private benchmark,
    credential, reviewer-note, and raw-sensitive-data fields. Use
    ``compile_draft_decision_packet`` for projection-only review packets and
    ``compile_publishable_decision_artifact`` for fail-closed final artifacts.
    """

    claims = [dict(claim) for claim in final_claims if isinstance(claim, Mapping)]
    recommendations = [
        _compile_recommendation(claim) for claim in claims if _is_recommendation_claim(claim)
    ]
    supporting_claims = [
        _compile_supporting_claim(claim) for claim in claims if not _is_recommendation_claim(claim)
    ]
    refs = _collect_refs(
        policy_grounding_matrix=policy_grounding_matrix,
        quality_scorecard=quality_scorecard,
        conflict_check=conflict_check,
        assurance_refs=assurance_refs,
    )
    source_truth_conflicts = _source_truth_conflicts(quality_scorecard)
    decision_context = {
        "grounding_status": _report_status(policy_grounding_matrix),
        "quality_status": _scorecard_quality_status(quality_scorecard),
        "conflict_status": _report_status(conflict_check),
        "approval_state": _approval_state(approval_state, quality_scorecard),
        "performance_status": _scorecard_performance_status(quality_scorecard),
        "public_export_status": "blocked" if source_truth_conflicts else "publishable",
    }
    public_export_conflict = _public_export_source_truth_conflict(
        quality_scorecard=quality_scorecard,
        decision_context=decision_context,
        refs=refs,
    )
    if public_export_conflict is not None:
        source_truth_conflicts.append(public_export_conflict)
    if source_truth_conflicts:
        decision_context["public_export_status"] = "blocked"
    artifact = {
        "schema_version": DECISION_ARTIFACT_SCHEMA_VERSION,
        "run_id": _text(run_id) or "unknown",
        "title": _text(title) or "Public policy decision artifact",
        "decision_context": decision_context,
        "recommendations": recommendations,
        "supporting_claims": supporting_claims,
        "scorecard": _scorecard_summary(quality_scorecard),
        "conflict_status": _public_report_summary(conflict_check),
        "approval": _public_approval_summary(approval_state),
        "performance_warnings": _performance_warnings(
            quality_scorecard=quality_scorecard,
            performance_warnings=performance_warnings,
        ),
        "assurance_refs": _sanitize_public_payload(dict(assurance_refs or {})),
        "refs": refs,
        "metadata": _sanitize_public_payload(dict(metadata or {})),
        "public_export_constraints": {
            "citations_preserved": True,
            "hidden_benchmark_answers_omitted": True,
            "credentials_omitted": True,
            "reviewer_private_notes_omitted": True,
            "raw_sensitive_data_omitted": True,
            "source_truth_conflicts_block_publication": bool(source_truth_conflicts),
        },
    }
    if spine_context is not None:
        artifact["producer_spine_context"] = dict(spine_context)
    if source_truth_conflicts:
        artifact["source_truth_conflicts"] = source_truth_conflicts
    return _sanitize_public_payload(artifact)


def compile_draft_decision_packet(
    *,
    run_id: str,
    final_claims: Sequence[Mapping[str, Any]],
    policy_grounding_matrix: Mapping[str, Any] | None,
    quality_scorecard: Mapping[str, Any] | None,
    conflict_check: Mapping[str, Any] | None,
    approval_state: Mapping[str, Any] | str | None,
    title: str | None = None,
    performance_warnings: Sequence[Mapping[str, Any] | str] | None = None,
    assurance_refs: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    spine_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile a non-authoritative draft packet for review and iteration."""

    artifact = compile_public_decision_artifact(
        run_id=run_id,
        final_claims=final_claims,
        policy_grounding_matrix=policy_grounding_matrix,
        quality_scorecard=quality_scorecard,
        conflict_check=conflict_check,
        approval_state=approval_state,
        title=title,
        performance_warnings=performance_warnings,
        assurance_refs=assurance_refs,
        metadata=metadata,
        spine_context=spine_context,
    )
    artifact["artifact_kind"] = DRAFT_DECISION_PACKET_ARTIFACT_KIND
    artifact["authority_role"] = "projection"
    artifact["publishability"] = "not_publishable"
    context = artifact.setdefault("decision_context", {})
    if isinstance(context, dict):
        context["public_export_status"] = "draft_projection"
    artifact["claim_evidence_contract"] = _build_claim_evidence_contract(
        final_claims,
        spine_context=spine_context,
    )
    constraints = artifact.setdefault("public_export_constraints", {})
    if isinstance(constraints, dict):
        constraints["draft_projection_only"] = True
    return _sanitize_public_payload(artifact)


def compile_publishable_decision_artifact(
    *,
    run_id: str,
    final_claims: Sequence[Mapping[str, Any]],
    policy_grounding_matrix: Mapping[str, Any] | None,
    quality_scorecard: Mapping[str, Any] | None,
    conflict_check: Mapping[str, Any] | None,
    approval_state: Mapping[str, Any] | str | None,
    title: str | None = None,
    performance_warnings: Sequence[Mapping[str, Any] | str] | None = None,
    assurance_refs: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    spine_context: Mapping[str, Any] | None = None,
    claim_registry: Mapping[str, Any] | None = None,
    runtime_authority: Mapping[str, Any] | None = None,
    policy_design_case: Mapping[str, Any] | None = None,
    runtime_pdc_graph: Mapping[str, Any] | None = None,
    production_approval_packet_ref: str | None = None,
    production_approval_resolver: object | None = None,
    production_approval_tenant_id: str | None = None,
    production_approval_audience: str = "polisyos-runtime",
) -> dict[str, Any]:
    """Compile a publishable decision artifact, failing closed on missing authority."""

    claim_contract = _compile_policy_design_claim_contract(
        final_claims,
        run_id=run_id,
        claim_registry=claim_registry,
        runtime_authority=runtime_authority,
    )
    final_claims_for_artifact = claim_contract["major_claims"] or [
        dict(claim) for claim in final_claims if isinstance(claim, Mapping)
    ]
    artifact = compile_public_decision_artifact(
        run_id=run_id,
        final_claims=final_claims_for_artifact,
        policy_grounding_matrix=policy_grounding_matrix,
        quality_scorecard=quality_scorecard,
        conflict_check=conflict_check,
        approval_state=approval_state,
        title=title,
        performance_warnings=performance_warnings,
        assurance_refs=assurance_refs,
        metadata=metadata,
        spine_context=spine_context,
    )
    artifact["artifact_kind"] = PUBLISHABLE_DECISION_ARTIFACT_KIND
    artifact["authority_role"] = "final_decision_artifact"
    artifact["publishability"] = "publishable"
    if runtime_pdc_graph is not None:
        artifact["projection_semantics"] = build_policy_design_case_projection_from_runtime_graph(
            runtime_pdc_graph=runtime_pdc_graph,
            surface="final_artifact",
        )
    elif policy_design_case is not None:
        artifact["projection_semantics"] = build_policy_design_case_projection_semantics(
            policy_design_case=policy_design_case,
            surface="final_artifact",
            source_payload=artifact,
            source_ref=_text(artifact.get("refs", {}).get("decision_artifact_ref"))
            if isinstance(artifact.get("refs"), Mapping)
            else None,
        )
    contract = _build_claim_evidence_contract(
        final_claims_for_artifact,
        spine_context=spine_context,
    )
    contract["policy_design_case_claim_contract"] = claim_contract
    gate_issues = _publishable_gate_issues(
        artifact=artifact,
        policy_grounding_matrix=policy_grounding_matrix,
        quality_scorecard=quality_scorecard,
        conflict_check=conflict_check,
        approval_state=approval_state,
        assurance_refs=assurance_refs,
        approval_currentness=_resolve_production_approval_currentness(
            resolver=production_approval_resolver,
            packet_ref=production_approval_packet_ref,
            tenant_id=production_approval_tenant_id,
            run_id=run_id,
            expected_consumer="polisyos.scientist.decision_compiler",
            expected_audience=production_approval_audience,
        ),
    )
    issues = [*claim_contract["issues"], *contract["issues"], *gate_issues]
    if issues:
        blocked_artifact = dict(artifact)
        blocked_artifact["publishability"] = "blocked"
        if runtime_pdc_graph is not None:
            blocked_artifact["projection_semantics"] = (
                build_policy_design_case_projection_from_runtime_graph(
                    runtime_pdc_graph=runtime_pdc_graph,
                    surface="final_artifact",
                )
            )
        elif policy_design_case is not None:
            blocked_artifact["projection_semantics"] = (
                build_policy_design_case_projection_semantics(
                    policy_design_case=policy_design_case,
                    surface="final_artifact",
                    source_payload=blocked_artifact,
                    source_ref=_text(blocked_artifact.get("refs", {}).get("decision_artifact_ref"))
                    if isinstance(blocked_artifact.get("refs"), Mapping)
                    else None,
                )
            )
        blocked_artifact["policy_design_case_claim_nodes"] = claim_contract["nodes"]
        blocked_artifact["final_major_claims"] = claim_contract["major_claims"]
        blocked_artifact["claim_evidence_contract"] = {
            **contract,
            "status": "blocked",
            "issues": issues,
        }
        raise DecisionArtifactCompilationError(
            "Publishable decision artifact compilation blocked.",
            issues=issues,
            draft_artifact=blocked_artifact,
        )

    artifact["policy_design_case_claim_nodes"] = claim_contract["nodes"]
    artifact["final_major_claims"] = claim_contract["major_claims"]
    artifact["claim_evidence_contract"] = contract
    context = artifact.setdefault("decision_context", {})
    if isinstance(context, dict):
        context["public_export_status"] = "publishable"
    return _sanitize_public_payload(artifact)


def _compile_policy_design_claim_contract(
    final_claims: Sequence[Mapping[str, Any]],
    *,
    run_id: str,
    claim_registry: Mapping[str, Any] | None,
    runtime_authority: Mapping[str, Any] | None,
) -> dict[str, Any]:
    major_claims = [
        dict(claim) for claim in final_claims if isinstance(claim, Mapping) and _is_major(claim)
    ]
    issues: list[dict[str, Any]] = []
    normalized_claims: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []

    if not major_claims:
        return {
            "schema_version": POLICY_DESIGN_CASE_CLAIM_CONTRACT_SCHEMA_VERSION,
            "status": "pass",
            "requirement": "major_claims_are_runtime_owned_policy_design_case_nodes",
            "major_claims": [],
            "nodes": [],
            "issues": [],
        }
    if not isinstance(claim_registry, Mapping):
        for claim in major_claims:
            issues.append(
                _claim_compiler_runtime_issue(
                    code="claim_compiler_runtime_registry_missing",
                    claim_id=_claim_id(claim),
                    message=(
                        "Publishable major claims require a runtime claim registry "
                        "that selects Policy Design Case refs."
                    ),
                    next_action=(
                        "Route final major claims through the Policy Design Case "
                        "claim registry before publication."
                    ),
                )
            )
        return _policy_design_claim_contract_payload(
            normalized_claims=major_claims,
            nodes=[],
            issues=issues,
        )

    registry_rows = _policy_design_claim_registry_rows(claim_registry)
    for claim in major_claims:
        claim_id = _claim_id(claim)
        row = registry_rows.get(claim_id)
        if row is None:
            issues.append(
                _claim_compiler_runtime_issue(
                    code="claim_compiler_registry_claim_missing",
                    claim_id=claim_id,
                    message=f"Claim registry has no selected refs for major claim {claim_id!r}.",
                    next_action=(
                        "Add a claim registry row with assurance node, producer, "
                        "portfolio, challenge, synthesis, and monitoring refs."
                    ),
                )
            )
            normalized_claims.append(dict(claim))
            continue

        normalized, node, claim_issues = _policy_design_claim_from_registry(
            claim,
            row,
            run_id=run_id,
            runtime_authority=runtime_authority,
        )
        normalized_claims.append(normalized)
        if node is not None:
            nodes.append(node)
        issues.extend(claim_issues)

    return _policy_design_claim_contract_payload(
        normalized_claims=normalized_claims,
        nodes=nodes,
        issues=issues,
    )


def _policy_design_claim_contract_payload(
    *,
    normalized_claims: Sequence[Mapping[str, Any]],
    nodes: Sequence[Mapping[str, Any]],
    issues: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": POLICY_DESIGN_CASE_CLAIM_CONTRACT_SCHEMA_VERSION,
        "status": "pass" if not issues else "blocked",
        "requirement": "major_claims_are_runtime_owned_policy_design_case_nodes",
        "major_claims": [dict(claim) for claim in normalized_claims],
        "nodes": [dict(node) for node in nodes],
        "issues": [dict(issue) for issue in issues],
    }


def _policy_design_claim_registry_rows(
    claim_registry: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    raw_claims = claim_registry.get("claims") or claim_registry.get("major_claims")
    if isinstance(raw_claims, Mapping):
        for claim_id, row in raw_claims.items():
            if isinstance(row, Mapping):
                merged = dict(row)
                merged.setdefault("claim_id", str(claim_id))
                rows.append(merged)
    elif isinstance(raw_claims, Sequence) and not isinstance(
        raw_claims,
        str | bytes | bytearray,
    ):
        rows.extend(row for row in raw_claims if isinstance(row, Mapping))
    rows.extend(
        row
        for row in _nested_statements(claim_registry.get("claim_registry_rows"))
        if isinstance(row, Mapping)
    )
    return {
        claim_id: row for row in rows if (claim_id := _text(row.get("claim_id") or row.get("id")))
    }


def _policy_design_claim_from_registry(
    claim: Mapping[str, Any],
    row: Mapping[str, Any],
    *,
    run_id: str,
    runtime_authority: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any] | None, list[dict[str, Any]]]:
    claim_id = _claim_id(claim)
    issues: list[dict[str, Any]] = []
    normalized = dict(claim)

    assurance_node_id = _text(
        row.get("assurance_node_id") or row.get("claim_node_id") or row.get("node_id")
    )
    claim_ref = _safe_ref(row.get("claim_ref") or row.get("cas_ref"))
    runtime_event_ref = _text(
        row.get("runtime_event_ref") or (runtime_authority or {}).get("runtime_event_ref")
    )
    authority_role = _text(
        row.get("authority_role") or (runtime_authority or {}).get("authority_role")
    )
    provenance_kind = _text(
        row.get("provenance_kind") or (runtime_authority or {}).get("provenance_kind")
    )

    if not assurance_node_id or not claim_ref:
        issues.append(
            _claim_compiler_runtime_issue(
                code="claim_compiler_assurance_node_missing",
                claim_id=claim_id,
                message=(
                    "Claim registry row must select an assurance node id and runtime claim ref."
                ),
                next_action="Mint the claim as a Policy Design Case assurance node.",
            )
        )
    if not _runtime_artifact_ref(claim_ref) or not _runtime_event_ref(runtime_event_ref):
        issues.append(
            _claim_compiler_runtime_issue(
                code="claim_compiler_runtime_authority_missing",
                claim_id=claim_id,
                message="Claim registry row must carry CAS/artifact and runtime event refs.",
                next_action="Persist the claim node through runtime CAS and event log.",
            )
        )
    if authority_role != "producer_authority" or provenance_kind != "runtime_emitted":
        issues.append(
            _claim_compiler_runtime_issue(
                code="claim_compiler_runtime_authority_missing",
                claim_id=claim_id,
                message=("Claim registry row must be runtime_emitted producer authority."),
                next_action="Use runtime-quality authority metadata for the claim node.",
            )
        )

    missing_ref = False
    for canonical_key, aliases, label in _PDC_CLAIM_REQUIRED_REF_SPECS:
        values = _registry_refs(row, aliases)
        if values:
            normalized[canonical_key] = values
            continue
        missing_ref = True
        issues.append(
            _claim_compiler_runtime_issue(
                code=f"claim_compiler_{canonical_key}_missing",
                claim_id=claim_id,
                message=f"Claim registry row must select {label}.",
                next_action="Select the missing refs in the claim registry.",
            )
        )

    scholar_refs = _registry_refs(row, _PDC_CLAIM_SCHOLAR_REF_KEYS)
    scholar_deficit_refs = _registry_refs(row, _PDC_CLAIM_SCHOLAR_DEFICIT_KEYS)
    if scholar_refs:
        normalized["scholar_refs"] = scholar_refs
    if scholar_deficit_refs:
        normalized["scholar_deficit_refs"] = scholar_deficit_refs
    if not scholar_refs and not scholar_deficit_refs:
        missing_ref = True
        issues.append(
            _claim_compiler_runtime_issue(
                code="claim_compiler_scholar_refs_or_deficit_missing",
                claim_id=claim_id,
                message=(
                    "Claim registry row must select Scholar refs or accepted "
                    "literature deficit refs."
                ),
                next_action="Add Scholar evidence refs or accepted literature deficits.",
            )
        )

    selected_producer_refs = _registry_selected_producer_refs(row)
    normalized["selected_producer_refs"] = selected_producer_refs
    for producer, aliases in _PDC_CLAIM_PRODUCER_REF_SPECS:
        if producer == "scholar" and not scholar_refs:
            continue
        if not _registry_refs(row, aliases):
            continue
        if selected_producer_refs.get(producer):
            continue
        issues.append(
            _claim_compiler_runtime_issue(
                code="claim_compiler_producer_refs_missing",
                claim_id=claim_id,
                producer=producer,
                message=(f"Claim registry row must select producer refs for {producer!r}."),
                next_action="Bind claim refs to producer-selected runtime evidence.",
            )
        )

    if missing_ref and _claim_uses_prose_backfill(claim):
        issues.append(
            _claim_compiler_runtime_issue(
                code="claim_compiler_prose_backfill_not_authority",
                claim_id=claim_id,
                message=("Narrative claim prose cannot backfill missing producer refs."),
                next_action="Replace prose backfill with producer-selected refs.",
            )
        )

    if assurance_node_id:
        normalized["assurance_node_id"] = assurance_node_id
    if claim_ref:
        normalized["claim_ref"] = claim_ref
    node = None
    if assurance_node_id and claim_ref:
        node = {
            "node_type": "claim",
            "node_id": assurance_node_id,
            "claim_id": claim_id,
            "claim_ref": claim_ref,
            "cas_ref": claim_ref,
            "runtime_event_ref": runtime_event_ref,
            "diagnostic_event_ref": runtime_event_ref,
            "run_id": _text(run_id) or "unknown",
            "runtime_authority_envelope": {
                "authority_role": authority_role,
                "provenance_kind": provenance_kind,
            },
            "selected_producer_refs": selected_producer_refs,
        }
        for canonical_key, _aliases, _label in _PDC_CLAIM_REQUIRED_REF_SPECS:
            if canonical_key in normalized:
                node[canonical_key] = normalized[canonical_key]
        if scholar_refs:
            node["scholar_refs"] = scholar_refs
        if scholar_deficit_refs:
            node["scholar_deficit_refs"] = scholar_deficit_refs
    return normalized, node, issues


def _registry_refs(row: Mapping[str, Any], aliases: tuple[str, ...]) -> list[str]:
    refs: list[str] = []
    for key in aliases:
        refs.extend(_evidence_refs_from_value(row.get(key)))
    return _dedupe_preserving_order(refs)


def _registry_selected_producer_refs(row: Mapping[str, Any]) -> dict[str, list[str]]:
    selected = row.get("selected_producer_refs") or row.get("producer_refs")
    if not isinstance(selected, Mapping):
        return {}
    refs: dict[str, list[str]] = {}
    for producer, _aliases in _PDC_CLAIM_PRODUCER_REF_SPECS:
        aliases = {
            producer,
            producer.replace("_", "-"),
            producer.replace("_", "."),
        }
        values: list[str] = []
        for alias in aliases:
            values.extend(_evidence_refs_from_value(selected.get(alias)))
        if values:
            refs[producer] = _dedupe_preserving_order(values)
    return refs


def _claim_uses_prose_backfill(claim: Mapping[str, Any]) -> bool:
    return any(_text(claim.get(key)) for key in _PDC_CLAIM_PROSE_BACKFILL_KEYS)


def _runtime_artifact_ref(value: object) -> bool:
    text = _safe_ref(value)
    if not text:
        return False
    if text.startswith("sha256:"):
        digest = text.removeprefix("sha256:")
        return len(digest) == 64 and all(char in "0123456789abcdefABCDEF" for char in digest)
    if text.startswith("cas://sha256/"):
        digest = text.removeprefix("cas://sha256/")
        return len(digest) == 64 and all(char in "0123456789abcdefABCDEF" for char in digest)
    return text.startswith("artifact://")


def _runtime_event_ref(value: object) -> bool:
    text = _text(value)
    return bool(text) and (text.startswith("event://") or _runtime_artifact_ref(text))


def _claim_compiler_runtime_issue(
    *,
    code: str,
    claim_id: str,
    message: str,
    next_action: str,
    **extra: object,
) -> dict[str, Any]:
    return _compiler_issue(
        code=code,
        claim_id=claim_id,
        statement_scope="policy_design_case_claim",
        statement_type="major_claim",
        message=message,
        next_action=next_action,
        **extra,
    )


def _build_claim_evidence_contract(
    final_claims: Sequence[Mapping[str, Any]],
    *,
    spine_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    statements: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    claims = [dict(claim) for claim in final_claims if isinstance(claim, Mapping)]
    if not any(_is_major(claim) for claim in claims):
        issues.append(
            _compiler_issue(
                code="publishable_artifact_major_claims_missing",
                statement_scope="artifact_gate",
                statement_type="major_claim",
                message="Publishable decision artifact has no major claims.",
                next_action=(
                    "Compile publishable artifacts from final major claims, or keep "
                    "the output as a draft projection."
                ),
            )
        )
    for claim in claims:
        claim_id = _claim_id(claim)
        if _is_major(claim):
            scope = _claim_statement_scope(claim)
            _append_statement_contract(
                statements,
                issues,
                claim_id=claim_id,
                statement_scope=scope,
                statement_type=_statement_type_for_scope(scope),
                text=_claim_text(claim),
                evidence_refs=_claim_evidence_refs(claim),
                typed_blockers=_typed_blockers_for_scope(claim, scope),
            )
            if _is_recommendation_claim(claim):
                for section, statement_type in _PUBLISHABLE_REQUIRED_SECTION_STATEMENTS.items():
                    _append_statement_contract(
                        statements,
                        issues,
                        claim_id=claim_id,
                        statement_scope=section,
                        statement_type=statement_type,
                        text=_section_text(claim, section),
                        evidence_refs=_section_evidence_refs(claim, section),
                        typed_blockers=_typed_blockers_for_scope(claim, section),
                    )
        for field, statement_type in _NESTED_STATEMENT_FIELDS.items():
            for index, statement in enumerate(_nested_statements(claim.get(field))):
                statement_scope = _text(statement.get("statement_scope")) or statement_type
                _append_statement_contract(
                    statements,
                    issues,
                    claim_id=claim_id,
                    statement_scope=statement_scope,
                    statement_type=statement_type,
                    text=_statement_text(statement),
                    evidence_refs=_evidence_refs_from_value(statement),
                    typed_blockers=_typed_blockers_from_value(statement),
                    statement_id=_text(statement.get("statement_id"))
                    or f"{claim_id}:{field}:{index}",
                )
    contract = {
        "status": "pass" if not issues else "blocked",
        "requirement": "every_major_statement_has_evidence_refs_or_typed_blocker",
        "statements": statements,
        "issues": issues,
    }
    if spine_context is not None:
        from polisyos.core import contracts as core_contracts

        evidence_refs = [
            ref
            for statement in statements
            for ref in statement.get("evidence_refs", [])
            if isinstance(ref, str)
        ]
        candidate_refs = evidence_refs or [
            str(statement["statement_id"])
            for statement in statements
            if isinstance(statement.get("statement_id"), str)
        ]
        blocker_refs = [
            str(issue.get("code")) for issue in issues if isinstance(issue.get("code"), str)
        ]
        contract.update(
            core_contracts.build_producer_spine_binding_fields(
                component="final_compiler",
                spine_context=spine_context,
                candidate_refs=candidate_refs,
                blocker_refs=blocker_refs,
            )
        )
    return contract


def _append_statement_contract(
    statements: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    *,
    claim_id: str,
    statement_scope: str,
    statement_type: str,
    text: str,
    evidence_refs: Sequence[str],
    typed_blockers: Sequence[Mapping[str, Any]],
    statement_id: str | None = None,
) -> None:
    evidence = _dedupe_preserving_order([ref for ref in evidence_refs if _safe_ref(ref)])
    blockers = [dict(blocker) for blocker in typed_blockers if _is_typed_blocker(blocker)]
    record = {
        "claim_id": claim_id,
        "statement_id": statement_id or f"{claim_id}:{statement_scope}",
        "statement_scope": statement_scope,
        "statement_type": statement_type,
        "has_text": bool(_text(text)),
        "evidence_refs": evidence,
        "typed_blockers": blockers,
    }
    statements.append(record)
    if not record["has_text"]:
        issues.append(
            _compiler_issue(
                code="claim_statement_missing_text",
                claim_id=claim_id,
                statement_scope=statement_scope,
                statement_type=statement_type,
                message="Publishable decision statement is missing text.",
                next_action=(
                    "Add the statement text or remove the empty statement from the "
                    "publishable artifact."
                ),
            )
        )
        return
    if evidence or blockers:
        return
    issues.append(
        _compiler_issue(
            code="claim_statement_missing_evidence_or_blocker",
            claim_id=claim_id,
            statement_scope=statement_scope,
            statement_type=statement_type,
            message=("Publishable decision statement has no evidence refs and no typed blocker."),
            next_action=(
                "Attach runtime-owned evidence refs or a typed blocker explaining why "
                "the statement cannot be grounded."
            ),
        )
    )


def _publishable_gate_issues(
    *,
    artifact: Mapping[str, Any],
    policy_grounding_matrix: Mapping[str, Any] | None,
    quality_scorecard: Mapping[str, Any] | None,
    conflict_check: Mapping[str, Any] | None,
    approval_state: Mapping[str, Any] | str | None,
    assurance_refs: Mapping[str, Any] | None,
    approval_currentness: bool,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    grounding_status = _report_status(policy_grounding_matrix).casefold()
    if grounding_status not in _PASS_STATUSES:
        issues.append(
            _compiler_issue(
                code="publishable_artifact_grounding_not_passing",
                statement_scope="artifact_gate",
                observed_status=grounding_status,
                upstream_issue_codes=_report_issue_codes(policy_grounding_matrix),
                message="Policy grounding must pass before artifact publication.",
                next_action="Resolve grounding failures or emit typed blockers before publication.",
            )
        )
    scorecard_status = _scorecard_quality_status(quality_scorecard).casefold()
    if scorecard_status not in _PASS_STATUSES:
        issues.append(
            _compiler_issue(
                code="publishable_artifact_scorecard_not_passing",
                statement_scope="artifact_gate",
                observed_status=scorecard_status,
                upstream_issue_codes=_scorecard_blocking_codes(quality_scorecard),
                message="Quality scorecard must pass before artifact publication.",
                next_action="Resolve scorecard failures before compiling a publishable artifact.",
            )
        )
    resolved_approval = _approval_state(approval_state, quality_scorecard).casefold()
    if resolved_approval not in _APPROVAL_READY_STATES:
        issues.append(
            _compiler_issue(
                code="publishable_artifact_not_approval_ready",
                statement_scope="artifact_gate",
                observed_status=resolved_approval,
                message="Publishable artifacts require approval-ready runtime state.",
                next_action="Complete approval or keep this output as a draft projection.",
            )
        )
    if not approval_currentness:
        issues.append(
            _compiler_issue(
                code="publishable_artifact_approval_currentness_unresolved",
                statement_scope="artifact_gate",
                observed_status="producer_missing",
                message=(
                    "A raw approval state or packet projection cannot authorize "
                    "publishable artifact creation."
                ),
                next_action=(
                    "Supply a signed V2 packet ref and the deployment-issued concrete resolver."
                ),
            )
        )
    conflict_status = _report_status(conflict_check).casefold()
    if conflict_status not in _PASS_STATUSES or conflict_status in _CONFLICT_STATUSES:
        issues.append(
            _compiler_issue(
                code="publishable_artifact_conflict_not_clear",
                statement_scope="artifact_gate",
                observed_status=conflict_status,
                upstream_issue_codes=_report_issue_codes(conflict_check),
                message="Conflict checks must be clear before artifact publication.",
                next_action="Resolve policy/legal conflicts or publish only a draft projection.",
            )
        )
    issues.extend(
        _quality_layer_gate_issues(
            quality_scorecard,
            layer_token="security",
            code="publishable_artifact_security_not_passing",
            message="Security assurance must pass before artifact publication.",
            next_action="Resolve security assurance failures before public artifact creation.",
        )
    )
    issues.extend(
        _quality_layer_gate_issues(
            quality_scorecard,
            layer_token="privacy",
            code="publishable_artifact_privacy_not_passing",
            message="Privacy compliance must pass before artifact publication.",
            next_action="Resolve privacy compliance failures before public artifact creation.",
        )
    )
    security_report = _assurance_report(assurance_refs, "security_assurance_report")
    if _report_status(security_report).casefold() not in _PASS_STATUSES and security_report:
        issues.append(
            _compiler_issue(
                code="publishable_artifact_security_not_passing",
                statement_scope="artifact_gate",
                observed_status=_report_status(security_report).casefold(),
                upstream_issue_codes=_report_issue_codes(security_report),
                message="Security assurance must pass before artifact publication.",
                next_action="Resolve security assurance failures before public artifact creation.",
            )
        )
    privacy_report = _assurance_report(assurance_refs, "privacy_compliance_report")
    if _report_status(privacy_report).casefold() not in _PASS_STATUSES and privacy_report:
        issues.append(
            _compiler_issue(
                code="publishable_artifact_privacy_not_passing",
                statement_scope="artifact_gate",
                observed_status=_report_status(privacy_report).casefold(),
                upstream_issue_codes=_report_issue_codes(privacy_report),
                message="Privacy compliance must pass before artifact publication.",
                next_action="Resolve privacy compliance failures before public artifact creation.",
            )
        )
    source_truth_conflicts = artifact.get("source_truth_conflicts")
    if (
        isinstance(source_truth_conflicts, Sequence)
        and not isinstance(
            source_truth_conflicts,
            str | bytes | bytearray,
        )
        and source_truth_conflicts
    ):
        issues.append(
            _compiler_issue(
                code="publishable_artifact_source_truth_conflict",
                statement_scope="artifact_gate",
                message="Source-truth conflicts block publishable artifact creation.",
                next_action="Resolve runtime/source-truth conflicts before publication.",
            )
        )
    return _dedupe_issues(issues)


def _compile_recommendation(claim: Mapping[str, Any]) -> dict[str, Any]:
    sections = {
        section: _section_text(claim, section) for section in REQUIRED_MAJOR_RECOMMENDATION_SECTIONS
    }
    return {
        "claim_id": _claim_id(claim),
        "claim_family": _claim_family(claim),
        "major": _is_major(claim),
        "text": _claim_text(claim),
        "citation_refs": _refs_from_claim(claim),
        "support_refs": _support_refs_from_claim(claim),
        "sections": sections,
    }


def _compile_supporting_claim(claim: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": _claim_id(claim),
        "claim_family": _claim_family(claim),
        "major": _is_major(claim),
        "text": _claim_text(claim),
        "citation_refs": _refs_from_claim(claim),
        "support_refs": _support_refs_from_claim(claim),
    }


def _scorecard_summary(scorecard: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(scorecard, Mapping):
        return {"quality_status": "missing", "approval_state": "missing"}
    summary: dict[str, Any] = {}
    for key in (
        "schema_version",
        "execution_status",
        "quality_status",
        "performance_status",
        "approval_state",
        "overall_score",
        "blocking_quality_failures",
        "warnings",
        "approval_eligibility",
    ):
        if key in scorecard:
            summary[key] = scorecard[key]
    return _sanitize_public_payload(summary)


def _public_report_summary(report: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(report, Mapping):
        return {"status": "missing"}
    summary: dict[str, Any] = {"status": _report_status(report)}
    for key in ("summary", "blocking_issue_count", "issues", "warnings"):
        if key in report:
            summary[key] = report[key]
    return _sanitize_public_payload(summary)


def _public_approval_summary(
    approval_state: Mapping[str, Any] | str | None,
) -> dict[str, Any]:
    if isinstance(approval_state, Mapping):
        return _sanitize_public_payload(dict(approval_state))
    return {"state": _text(approval_state) or "missing"}


def _performance_warnings(
    *,
    quality_scorecard: Mapping[str, Any] | None,
    performance_warnings: Sequence[Mapping[str, Any] | str] | None,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    if isinstance(quality_scorecard, Mapping):
        raw_scorecard_warnings = quality_scorecard.get("warnings")
        if isinstance(raw_scorecard_warnings, Sequence) and not isinstance(
            raw_scorecard_warnings,
            str | bytes | bytearray,
        ):
            warnings.extend(_warning_payload(item) for item in raw_scorecard_warnings)
    if isinstance(performance_warnings, Sequence) and not isinstance(
        performance_warnings,
        str | bytes | bytearray,
    ):
        warnings.extend(_warning_payload(item) for item in performance_warnings)
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for warning in warnings:
        key = (_text(warning.get("code")), _text(warning.get("message")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(_sanitize_public_payload(warning))
    return deduped


def _source_truth_conflicts(quality_scorecard: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(quality_scorecard, Mapping):
        return []
    raw_conflicts = quality_scorecard.get("source_truth_conflicts")
    if not isinstance(raw_conflicts, Sequence) or isinstance(
        raw_conflicts,
        str | bytes | bytearray,
    ):
        return []
    return [dict(item) for item in raw_conflicts if isinstance(item, Mapping)]


def _public_export_source_truth_conflict(
    *,
    quality_scorecard: Mapping[str, Any] | None,
    decision_context: Mapping[str, Any],
    refs: Mapping[str, str],
) -> dict[str, Any] | None:
    if not isinstance(quality_scorecard, Mapping):
        return None
    scorecard_ref = (
        _safe_ref(quality_scorecard.get("quality_scorecard_ref"))
        or _safe_ref(quality_scorecard.get("authoritative_scorecard_ref"))
        or refs.get("quality_scorecard_ref")
    )
    expected_public_export_status = (
        "publishable"
        if _scorecard_quality_status(quality_scorecard) == "pass"
        and _text(quality_scorecard.get("approval_state")) == "approval_ready"
        else "blocked"
    )
    return detect_source_truth_conflict(
        field_family="approval_readiness_public_status",
        authoritative_source="runtime.scorecard",
        authoritative_surface="runtime.scorecard",
        authoritative_values={
            "quality_status": _scorecard_quality_status(quality_scorecard),
            "approval_state": _text(quality_scorecard.get("approval_state")) or "missing",
            "public_export_status": expected_public_export_status,
            "scorecard_identity": scorecard_ref,
        },
        conflicting_source="runtime.public_export",
        conflicting_surface="runtime.public_export",
        conflicting_values={
            "quality_status": decision_context.get("quality_status"),
            "approval_state": decision_context.get("approval_state"),
            "public_export_status": decision_context.get("public_export_status"),
            "scorecard_identity": refs.get("quality_scorecard_ref"),
        },
        fields=(
            "quality_status",
            "approval_state",
            "public_export_status",
            "scorecard_identity",
        ),
        downstream_impact="Public export publication is blocked until runtime authority agrees.",
        cas_refs=[ref for ref in refs.values() if ref],
        authoritative_ref=scorecard_ref,
        conflicting_ref=refs.get("decision_artifact_ref"),
        details={
            "reader": "scientist.public_decision_artifact",
            "projection_source": "runtime.public_export",
        },
    )


def _warning_payload(value: Mapping[str, Any] | str | object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {"code": "performance_warning", "message": _text(value)}


def _collect_refs(
    *,
    policy_grounding_matrix: Mapping[str, Any] | None,
    quality_scorecard: Mapping[str, Any] | None,
    conflict_check: Mapping[str, Any] | None,
    assurance_refs: Mapping[str, Any] | None,
) -> dict[str, str]:
    refs: dict[str, str] = {}
    for payload in (
        policy_grounding_matrix,
        quality_scorecard,
        conflict_check,
        assurance_refs,
    ):
        refs.update(_refs_from_mapping(payload))
    if isinstance(quality_scorecard, Mapping):
        evidence_refs = quality_scorecard.get("evidence_refs")
        if isinstance(evidence_refs, Mapping):
            refs.update(_refs_from_mapping(evidence_refs))
    return dict(sorted(refs.items()))


def _refs_from_mapping(payload: Mapping[str, Any] | None) -> dict[str, str]:
    if not isinstance(payload, Mapping):
        return {}
    refs: dict[str, str] = {}
    for key, value in payload.items():
        if key == "evidence_refs":
            continue
        ref_key = _normalize_ref_key(key)
        if ref_key is None:
            continue
        ref_value = _safe_ref(value)
        if ref_value:
            refs[ref_key] = ref_value
    return refs


def _normalize_ref_key(key: object) -> str | None:
    text = _text(key)
    if not text:
        return None
    if text in _REF_KEYS:
        return text
    if text.endswith("_ref"):
        return text
    if text.endswith("_report") or text.endswith("_trace"):
        return f"{text}_ref"
    return None


def _safe_ref(value: object) -> str | None:
    if isinstance(value, Mapping):
        for key in ("artifact_id", "ref", "uri", "path"):
            if key in value:
                return _safe_ref(value[key])
        return None
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return None
    text = _text(value)
    if not text or _is_forbidden_value(text):
        return None
    return text


def _section_text(claim: Mapping[str, Any], section: str) -> str:
    for key in _SECTION_ALIASES[section]:
        if key in claim:
            return _text(claim.get(key))
    return ""


def _claim_id(claim: Mapping[str, Any]) -> str:
    return _text(claim.get("claim_id") or claim.get("id") or "claim")


def _claim_family(claim: Mapping[str, Any]) -> str:
    raw = (
        claim.get("claim_family")
        or claim.get("family")
        or claim.get("claim_type")
        or claim.get("type")
    )
    token = _text(raw).casefold().replace("-", "_").replace(" ", "_")
    return token or "recommendation"


def _claim_text(claim: Mapping[str, Any]) -> str:
    return _text(claim.get("text") or claim.get("claim") or claim.get("statement"))


def _is_recommendation_claim(claim: Mapping[str, Any]) -> bool:
    return _claim_family(claim) in _RECOMMENDATION_FAMILIES


def _is_major(claim: Mapping[str, Any]) -> bool:
    value = claim.get("major")
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() not in {"0", "false", "minor", "no"}
    return bool(value)


def _refs_from_claim(claim: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("citation_refs", "citations", "source_refs", "norm_refs"):
        refs.extend(_as_text_list(claim.get(key)))
    return _dedupe_preserving_order(refs)


def _support_refs_from_claim(claim: Mapping[str, Any]) -> dict[str, list[str]]:
    support_refs = {
        "data_refs": _as_text_list(
            claim.get("data_refs") or claim.get("data_source_refs") or claim.get("fabric_refs")
        ),
        "method_refs": _as_text_list(
            claim.get("method_refs")
            or claim.get("foundry_method_refs")
            or claim.get("analysis_refs")
        ),
        "norm_refs": _as_text_list(
            claim.get("norm_refs") or claim.get("normative_refs") or claim.get("legal_refs")
        ),
    }
    return {key: values for key, values in support_refs.items() if values}


def _claim_statement_scope(claim: Mapping[str, Any]) -> str:
    family = _claim_family(claim)
    return _CLAIM_FAMILY_STATEMENT_SCOPES.get(family, "major_claim")


def _statement_type_for_scope(scope: str) -> str:
    return _CLAIM_FAMILY_STATEMENT_SCOPES.get(scope, scope)


def _claim_evidence_refs(claim: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    refs.extend(_refs_from_claim(claim))
    for key in (
        "evidence_refs",
        "claim_evidence_refs",
        "authority_refs",
        "data_refs",
        "method_refs",
        "norm_refs",
        "legal_refs",
        "uncertainty_refs",
    ):
        refs.extend(_evidence_refs_from_value(claim.get(key)))
    support_refs = claim.get("support_refs")
    if isinstance(support_refs, Mapping):
        refs.extend(_evidence_refs_from_value(support_refs))
    return _dedupe_preserving_order(refs)


def _section_evidence_refs(claim: Mapping[str, Any], section: str) -> list[str]:
    refs: list[str] = []
    for mapping_key in (
        "section_evidence_refs",
        "statement_evidence_refs",
        "evidence_by_section",
        "section_refs",
    ):
        mapping = claim.get(mapping_key)
        if not isinstance(mapping, Mapping):
            continue
        refs.extend(_evidence_refs_from_value(mapping.get(section)))
        for alias in _SECTION_ALIASES.get(section, ()):
            refs.extend(_evidence_refs_from_value(mapping.get(alias)))
    for alias in _SECTION_REF_ALIASES.get(section, ()):
        refs.extend(_evidence_refs_from_value(claim.get(alias)))
    support_refs = claim.get("support_refs")
    if isinstance(support_refs, Mapping):
        refs.extend(_evidence_refs_from_value(support_refs.get(section)))
        for alias in _SECTION_REF_ALIASES.get(section, ()):
            refs.extend(_evidence_refs_from_value(support_refs.get(alias)))
    return _dedupe_preserving_order(refs)


def _typed_blockers_for_scope(
    claim: Mapping[str, Any],
    scope: str,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for mapping_key in ("typed_blockers", "section_blockers", "statement_blockers"):
        mapping = claim.get(mapping_key)
        if isinstance(mapping, Mapping):
            blockers.extend(_typed_blockers_from_value(mapping.get(scope)))
            for alias in _SECTION_ALIASES.get(scope, ()):
                blockers.extend(_typed_blockers_from_value(mapping.get(alias)))
        else:
            blockers.extend(
                blocker
                for blocker in _typed_blockers_from_value(mapping)
                if _blocker_scope_matches(blocker, scope)
            )
    for key in ("blockers", "typed_blocker_refs"):
        blockers.extend(
            blocker
            for blocker in _typed_blockers_from_value(claim.get(key))
            if _blocker_scope_matches(blocker, scope)
        )
    return _dedupe_blockers(blockers)


def _nested_statements(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, str):
        return [{"text": _text(value)}]
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        statements: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, Mapping):
                statements.append(dict(item))
            elif _text(item):
                statements.append({"text": _text(item)})
        return statements
    return []


def _statement_text(statement: Mapping[str, Any]) -> str:
    return _text(statement.get("text") or statement.get("statement") or statement.get("claim"))


def _evidence_refs_from_value(value: object) -> list[str]:
    if value is None:
        return []
    ref = _safe_ref(value)
    if ref:
        return [ref]
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
        ):
            refs.extend(_evidence_refs_from_value(value.get(key)))
        return _dedupe_preserving_order(refs)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        refs = []
        for item in value:
            refs.extend(_evidence_refs_from_value(item))
        return _dedupe_preserving_order(refs)
    return []


def _typed_blockers_from_value(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        if _is_typed_blocker(value):
            return [dict(value)]
        blockers: list[dict[str, Any]] = []
        for key in ("typed_blockers", "blockers", "blocker_refs"):
            blockers.extend(_typed_blockers_from_value(value.get(key)))
        return blockers
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        blockers: list[dict[str, Any]] = []
        for item in value:
            blockers.extend(_typed_blockers_from_value(item))
        return blockers
    return []


def _is_typed_blocker(value: Mapping[str, Any]) -> bool:
    return bool(
        _text(
            value.get("blocker_type")
            or value.get("type")
            or value.get("code")
            or value.get("reason_code")
        )
    )


def _blocker_scope_matches(blocker: Mapping[str, Any], scope: str) -> bool:
    raw_scope = _text(
        blocker.get("statement_scope")
        or blocker.get("scope")
        or blocker.get("section")
        or blocker.get("field")
    )
    return not raw_scope or raw_scope == scope or raw_scope in _SECTION_ALIASES.get(scope, ())


def _dedupe_blockers(blockers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for blocker in blockers:
        key = _text(
            blocker.get("blocker_type")
            or blocker.get("type")
            or blocker.get("code")
            or blocker.get("reason_code")
        )
        scope = _text(blocker.get("statement_scope") or blocker.get("scope"))
        fingerprint = f"{scope}:{key}:{_text(blocker.get('reason'))}"
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped.append(dict(blocker))
    return deduped


def _compiler_issue(
    *,
    code: str,
    statement_scope: str,
    message: str,
    next_action: str,
    claim_id: str | None = None,
    statement_type: str | None = None,
    **extra: object,
) -> dict[str, Any]:
    issue = {
        "code": code,
        "severity": "fail",
        "layer": "scientist_decision_artifacts",
        "phase": "decision_artifact_compilation",
        "statement_scope": statement_scope,
        "message": message,
        "next_action": next_action,
        **extra,
    }
    if claim_id is not None:
        issue["claim_id"] = claim_id
    if statement_type is not None:
        issue["statement_type"] = statement_type
    return issue


def _report_issue_codes(report: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(report, Mapping):
        return []
    raw_issues = report.get("issues") or report.get("blockers") or []
    if not isinstance(raw_issues, Sequence) or isinstance(
        raw_issues,
        str | bytes | bytearray,
    ):
        return []
    codes: list[str] = []
    for issue in raw_issues:
        if not isinstance(issue, Mapping):
            continue
        code = _text(issue.get("code") or issue.get("reason_code"))
        if code:
            codes.append(code)
    return _dedupe_preserving_order(codes)


def _scorecard_blocking_codes(scorecard: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(scorecard, Mapping):
        return []
    raw_failures = scorecard.get("blocking_quality_failures") or []
    if not isinstance(raw_failures, Sequence) or isinstance(
        raw_failures,
        str | bytes | bytearray,
    ):
        return []
    codes: list[str] = []
    for failure in raw_failures:
        if not isinstance(failure, Mapping):
            continue
        code = _text(failure.get("code") or failure.get("gate"))
        if code:
            codes.append(code)
    return _dedupe_preserving_order(codes)


def _quality_layer_gate_issues(
    scorecard: Mapping[str, Any] | None,
    *,
    layer_token: str,
    code: str,
    message: str,
    next_action: str,
) -> list[dict[str, Any]]:
    if not isinstance(scorecard, Mapping):
        return []
    raw_failures = scorecard.get("blocking_quality_failures") or []
    if not isinstance(raw_failures, Sequence) or isinstance(
        raw_failures,
        str | bytes | bytearray,
    ):
        return []
    issues: list[dict[str, Any]] = []
    for failure in raw_failures:
        if not isinstance(failure, Mapping):
            continue
        haystack = " ".join(
            _text(failure.get(key)).casefold() for key in ("gate", "code", "layer", "phase")
        )
        if layer_token not in haystack:
            continue
        issues.append(
            _compiler_issue(
                code=code,
                statement_scope="artifact_gate",
                upstream_issue_codes=[_text(failure.get("code") or failure.get("gate"))],
                message=message,
                next_action=next_action,
            )
        )
    return issues


def _resolve_production_approval_currentness(
    *,
    resolver: object | None,
    packet_ref: str | None,
    tenant_id: str | None,
    run_id: str,
    expected_consumer: str,
    expected_audience: str,
) -> bool:
    """Invoke the concrete resolver; mappings, DTOs, and callbacks fail closed."""

    from polisyos.runtime.quality.approval import ProductionApprovalPacketResolver

    if type(resolver) is not ProductionApprovalPacketResolver or not packet_ref or not tenant_id:
        return False
    try:
        resolver.require_currentness(
            packet_ref=packet_ref,
            tenant_id=tenant_id,
            run_id=run_id,
            expected_consumer=expected_consumer,
            expected_audience=expected_audience,
        )
    except ValueError:
        return False
    return True


def _assurance_report(
    assurance_refs: Mapping[str, Any] | None,
    key: str,
) -> Mapping[str, Any] | None:
    if not isinstance(assurance_refs, Mapping):
        return None
    value = assurance_refs.get(key)
    if isinstance(value, Mapping):
        return value
    return None


def _dedupe_issues(issues: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for issue in issues:
        key = (
            _text(issue.get("code")),
            _text(issue.get("claim_id")),
            _text(issue.get("statement_scope")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(issue))
    return deduped


def _as_text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = _text(value)
        return [text] if text and not _is_forbidden_value(text) else []
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return [text for item in value if (text := _text(item)) and not _is_forbidden_value(text)]
    text = _text(value)
    return [text] if text and not _is_forbidden_value(text) else []


def _dedupe_preserving_order(values: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _report_status(report: Mapping[str, Any] | None) -> str:
    if not isinstance(report, Mapping):
        return "missing"
    return _text(report.get("status") or report.get("quality_status") or "present")


def _scorecard_quality_status(scorecard: Mapping[str, Any] | None) -> str:
    if not isinstance(scorecard, Mapping):
        return "missing"
    return _text(scorecard.get("quality_status") or scorecard.get("status") or "present")


def _scorecard_performance_status(scorecard: Mapping[str, Any] | None) -> str:
    if not isinstance(scorecard, Mapping):
        return "missing"
    return _text(scorecard.get("performance_status") or "unknown")


def _approval_state(
    approval_state: Mapping[str, Any] | str | None,
    scorecard: Mapping[str, Any] | None,
) -> str:
    if isinstance(approval_state, Mapping):
        return (
            _text(
                approval_state.get("state")
                or approval_state.get("approval_state")
                or approval_state.get("decision")
            )
            or "present"
        )
    explicit = _text(approval_state)
    if explicit:
        return explicit
    if isinstance(scorecard, Mapping):
        return _text(scorecard.get("approval_state")) or "missing"
    return "missing"


def _sanitize_public_payload(value: object) -> object:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = _text(key)
            if _is_forbidden_key(key_text):
                continue
            sanitized_value = _sanitize_public_payload(item)
            if sanitized_value is not None:
                sanitized[key_text] = sanitized_value
        return sanitized
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [
            sanitized_item
            for item in value
            if (sanitized_item := _sanitize_public_payload(item)) is not None
        ]
    if isinstance(value, str) and _is_forbidden_value(value):
        return None
    return value


def _is_forbidden_key(key: str) -> bool:
    lowered = key.casefold()
    return any(token in lowered for token in PUBLIC_FORBIDDEN_KEY_TOKENS)


def _is_forbidden_value(value: str) -> bool:
    lowered = value.casefold()
    forbidden_value_tokens = (
        "access_token",
        "api_key",
        "bearer ",
        "benchmark_answer",
        "hidden_benchmark",
        "password",
        "raw_sensitive",
        "secret-key",
        "system_prompt",
    )
    return any(token in lowered for token in forbidden_value_tokens)


def _text(value: object) -> str:
    return str(value or "").strip()


__all__ = [
    "DECISION_ARTIFACT_SCHEMA_VERSION",
    "DRAFT_DECISION_PACKET_ARTIFACT_KIND",
    "PUBLIC_FORBIDDEN_KEY_TOKENS",
    "PUBLISHABLE_DECISION_ARTIFACT_KIND",
    "REQUIRED_MAJOR_RECOMMENDATION_SECTIONS",
    "DecisionArtifactCompilationError",
    "compile_draft_decision_packet",
    "compile_public_decision_artifact",
    "compile_publishable_decision_artifact",
]
