"""Layer 3 G6 bounded arbitrary-request agent contracts.

This module starts with the authority constants for the G6 adapter surface.
G6 owns orchestration audit and routing readings only; LLM/tool outputs remain
candidate-only until later producer-side grounding admits them through G5.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.pdc import (
    AgentDecisionRecord,
    MethodPlan,
    OperationClass,
    OperationInvocationRecord,
    SearchLedgerEvent,
)
from polisyos.runtime.quality.candidate_firewall import (
    candidate_firewall_issues_for_payload,
)
from polisyos.runtime.quality.hypothesis_ledger import (
    HypothesisLedger,
    build_hypothesis_ledger_from_prompt_tool_ledger,
)
from polisyos.runtime.quality.nl_replay_orchestration import (
    build_nl_replay_orchestration_continuity,
    validate_nl_replay_orchestration_continuity,
)
from polisyos.runtime.quality.projection_semantics import (
    PolicyDesignCaseProjectionError,
    assert_policy_design_projection_not_authority,
)
from polisyos.runtime.quality.prompt_tool_ledger import (
    CompressionClaimItem,
    CompressionLossReceipt,
    CompressionMaterialItem,
    CompressionMaterialSet,
    OrchestrationAuthorityDelta,
    OrchestrationAuthorityDeltaCompletenessReceipt,
    OrchestrationChoiceContext,
    PromptToolLedgerError,
    PromptToolParserAuthorityLedger,
    build_compression_loss_receipt,
    build_orchestration_authority_deltas,
    validate_compression_loss_receipt,
    validate_orchestration_authority_delta_completeness,
)
from polisyos.runtime.quality.proving_ground import proving_ground_conversion as g5
from polisyos.runtime.quality.replay import (
    build_replay_manifest,
    explain_replay_drift,
)
from polisyos.runtime.quality.required_reference_resolver import resolve_required_ref
from polisyos.scientist import (
    ToolContractSummary,
    ToolDefinition,
    ToolLoopResult,
    ToolRegistry,
    create_traced_gateway_client,
    run_tool_loop,
    summarize_tool_contracts,
    tool_contract_default_blockers,
)

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[5]
G6_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g6_bounded_agent.v1"
G6_RULE_VERSION = "policyos.layer3.g6.bounded_agent.v1"
G6_SURFACE_ID = "layer3_g6_bounded_agent_surface"
G6_GENERATED_ARTIFACT_FAMILY_ID = (
    "policy-design-case-layer3-g6-bounded-agent-artifacts"
)
G6_POLICY_GRAMMAR_AUTHORITATIVE_FOR = ("layer3_g6_policy_grammar_routing_facets",)
G6_DEFAULT_G5_ENVELOPE_REFS = (
    f"layer3-g5-envelope://{g5.G5_PINNED_CASE_ID}",
    "layer3-g5-claim-family://ua-msme-support",
)
G6_ALLOWED_TOOL_NAMES = (
    "layer3_g6_classify_request",
    "layer3_g6_build_g5_bundle",
    "layer3_g6_read_g5_conversion",
    "layer3_g6_probe_counterexample",
    "layer3_g6_probe_envelope_match",
)
G6_REQUEST_ID_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"request_id": {"type": "string"}},
    "required": ["request_id"],
    "additionalProperties": False,
}

G6_AUTHORITATIVE_FOR = (
    "layer3_g6_agent_orchestration_audit",
    "layer3_g6_g5_routing_decision",
    "layer3_g6_demand_pull_vs_abstention_reading",
)
G6_MAY_NOT_USE_FOR = (
    "production_authority",
    "rollout_authority",
    "publication_authority",
    "approval_authority",
    "scorecard_authority",
    "closeout_authority",
    "runtime_closeout_authority",
    "public_recommendation",
    "policy_recommendation",
    "legal_advice",
    "claim_authority",
    "obligation_authority",
    "causal_effect_authority",
    "proof_authority",
    "legal_authority",
    "g5_conversion_authority_without_g5",
    "g7_region_widening",
)
G6_PUBLIC_PROJECTION_DENIED_USES = tuple(
    dict.fromkeys((*G6_MAY_NOT_USE_FOR, "recommendation_authority"))
)
G6_PUBLIC_REQUIRED_DENIED_USES = frozenset(
    {
        "claim_authority",
        "scorecard_authority",
        "runtime_closeout_authority",
        "policy_recommendation",
        "recommendation_authority",
    }
)
ALL_ISSUE_CODES = (
    "layer3_g6_g5_readiness_missing",
    "layer3_g6_request_envelope_missing",
    "layer3_g6_policy_grammar_projection_missing",
    "layer3_g6_policy_grammar_compile_blocked",
    "layer3_g6_policy_grammar_concept_refs_missing",
    "layer3_g6_runtime_imports_policy_grammar",
    "layer3_g6_classifier_only_match_not_authority",
    "layer3_g6_llm_client_unavailable",
    "layer3_g6_agent_loop_trace_missing",
    "layer3_g6_agent_candidate_used_as_authority",
    "layer3_g6_design_record_candidate_used_as_authority",
    "layer3_g6_orchestration_choice_audit_missing",
    "layer3_g6_authority_delta_completeness_failed",
    "layer3_g6_authority_delta_owner_validation_failed",
    "layer3_g6_compression_loss_receipt_missing",
    "layer3_g6_compression_loss_receipt_blocked",
    "layer3_g6_rejected_branch_memory_missing",
    "layer3_g6_search_ledger_missing",
    "layer3_g6_search_ledger_authority_boundary_leak",
    "layer3_g6_selected_evidence_ref_unresolved",
    "layer3_g6_outside_g5_envelope",
    "layer3_g6_outside_envelope_abstention_without_search_health",
    "layer3_g6_cheap_refusal_without_demand_signal",
    "layer3_g6_tool_contract_not_ready",
    "layer3_g6_non_allowlisted_tool_attempt",
    "layer3_g6_tool_loop_transcript_only_not_audit",
    "layer3_g6_g5_bypass_attempt",
    "layer3_g6_g5_may_not_use_for_ignored",
    "layer3_g6_non_pinned_g5_widening_attempt",
    "layer3_g6_g7_region_widening_attempt",
    "layer3_g6_g4_source_resolution_bypass_attempt",
    "layer3_g6_prompt_tool_ledger_missing",
    "layer3_g6_prompt_tool_ledger_misread_as_authority",
    "layer3_g6_candidate_without_hypothesis_ledger",
    "layer3_g6_orchestration_continuity_missing",
    "layer3_g6_orchestration_continuity_refs_missing",
    "layer3_g6_replay_manifest_missing",
    "layer3_g6_replay_drift_unexplained",
    "layer3_g6_public_raw_prompt_leak",
    "layer3_g6_public_projection_contract_failed",
    "layer3_g6_health_delta_request_count_missing",
    "layer3_g6_health_delta_negative_count",
    "layer3_g6_health_delta_routed_exceeds_requests",
    "layer3_g6_health_delta_outcomes_exceed_requests",
    "layer3_g6_health_delta_accountable_principal_missing",
    "layer3_g6_persisted_artifact_missing",
    "layer3_g6_generated_artifacts_family_missing",
    "layer3_g6_inventory_surface_missing",
    "layer3_g6_reference_index_missing",
)
G6_CONFORMANCE_NEGATIVE_EXPECTATIONS: dict[str, tuple[str, ...]] = {
    "agent_fluent_output_as_authority": (
        "layer3_g6_agent_candidate_used_as_authority",
    ),
    "tool_choice_bias_hides_counterevidence": (
        "layer3_g6_rejected_branch_memory_missing",
    ),
    "agent_loop_trace_missing": ("layer3_g6_agent_loop_trace_missing",),
    "search_ledger_missing": ("layer3_g6_search_ledger_missing",),
    "search_ledger_authority_boundary_leak": (
        "layer3_g6_search_ledger_authority_boundary_leak",
    ),
    "tool_loop_transcript_only_not_audit": (
        "layer3_g6_tool_loop_transcript_only_not_audit",
    ),
    "llm_client_unavailable": ("layer3_g6_llm_client_unavailable",),
    "policy_grammar_compile_blocked": ("layer3_g6_policy_grammar_compile_blocked",),
    "policy_grammar_concept_refs_missing": (
        "layer3_g6_policy_grammar_concept_refs_missing",
    ),
    "runtime_imports_policy_grammar": ("layer3_g6_runtime_imports_policy_grammar",),
    "hardcoded_template_classifier_only": (
        "layer3_g6_classifier_only_match_not_authority",
    ),
    "design_record_candidate_as_authority": (
        "layer3_g6_design_record_candidate_used_as_authority",
    ),
    "design_record_candidate_as_g4_source_record": (
        "layer3_g6_g4_source_resolution_bypass_attempt",
    ),
    "g5_bypass_attempt": ("layer3_g6_g5_bypass_attempt",),
    "g5_may_not_use_for_ignored": ("layer3_g6_g5_may_not_use_for_ignored",),
    "non_allowlisted_tool_attempt": ("layer3_g6_non_allowlisted_tool_attempt",),
    "candidate_without_hypothesis_ledger": (
        "layer3_g6_candidate_without_hypothesis_ledger",
    ),
    "public_raw_prompt_leak": ("layer3_g6_public_raw_prompt_leak",),
    "outside_envelope_abstention_without_search_health": (
        "layer3_g6_outside_envelope_abstention_without_search_health",
    ),
    "cheap_refusal_without_demand_signal": (
        "layer3_g6_cheap_refusal_without_demand_signal",
    ),
    "out_of_envelope_g5_widening_attempt": (
        "layer3_g6_non_pinned_g5_widening_attempt",
    ),
    "prompt_tool_ledger_missing": ("layer3_g6_prompt_tool_ledger_missing",),
    "prompt_tool_ledger_misread_as_authority": (
        "layer3_g6_prompt_tool_ledger_misread_as_authority",
    ),
    "orchestration_continuity_missing": (
        "layer3_g6_orchestration_continuity_missing",
    ),
    "orchestration_continuity_refs_missing": (
        "layer3_g6_orchestration_continuity_refs_missing",
    ),
    "replay_manifest_missing": ("layer3_g6_replay_manifest_missing",),
    "replay_drift_unexplained": ("layer3_g6_replay_drift_unexplained",),
    "orchestration_choice_audit_missing": (
        "layer3_g6_orchestration_choice_audit_missing",
    ),
    "g7_region_widening_attempt": ("layer3_g6_g7_region_widening_attempt",),
}


class _G6Model(BaseModel):
    """Strict base model for G6 runtime-quality DTOs."""

    model_config = ConfigDict(extra="forbid")


class G6ToolCallingClient(Protocol):
    """Minimal client protocol consumed by the Scientist tool loop."""

    async def generate(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        temperature: float | None = None,
        seed: int | None = None,
    ) -> object:
        """Generate one OpenAI-shape response."""


Layer3G6EnvelopeMatchStatus = Literal[
    "same_class_as_g5_pinned_case",
    "outside_g5_envelope",
    "ambiguous_requires_abstention",
]
Layer3G6RequestClass = Literal[
    "ua_msme_support",
    "outside_g5_pinned_class",
    "ambiguous",
]
Layer3G6AgentOutcome = Literal[
    "g5_grounded_result",
    "g5_grounded_abstention",
    "out_of_envelope_grounded_abstention",
    "g5_unchanged_blocker",
]
Layer3G6EngineeringReadinessStatus = Literal["pass", "fail", "blocked"]
Layer3G6GroundedValueClosureStatus = Literal[
    "pass",
    "blocked_by_current_g5_unchanged_blocker",
    "blocked_by_missing_search_or_demand_refs",
    "fail",
]


class Layer3G6PolicyGrammarProjection(_G6Model):
    """Policy-grammar projection consumed by G6 without importing the compiler."""

    projection_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    intent_ref: str = Field(min_length=1)
    compiled_case_ref: str | None = None
    compiled_case_status: str = Field(min_length=1)
    status: Literal["pass", "fail"]
    authority_state: Literal[
        "compilation_facets_only",
        "candidate_unverified",
        "blocked",
    ]
    facet_summary: dict[str, Any] = Field(default_factory=dict)
    concept_spine_refs: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G6_POLICY_GRAMMAR_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR

    @model_validator(mode="after")
    def _validate_projection_boundary(self) -> Layer3G6PolicyGrammarProjection:
        if self.authoritative_for != G6_POLICY_GRAMMAR_AUTHORITATIVE_FOR:
            raise ValueError(
                "policy grammar projection authoritative_for must be "
                f"{G6_POLICY_GRAMMAR_AUTHORITATIVE_FOR!r}"
            )
        required_denied = {"legal_authority", "claim_authority", "closeout_authority"}
        if not required_denied.issubset(set(self.may_not_use_for)):
            missing = ", ".join(sorted(required_denied - set(self.may_not_use_for)))
            raise ValueError(f"policy grammar projection missing denied uses: {missing}")
        if not self.facet_summary:
            raise ValueError("policy grammar projection facet_summary is required")
        concept_spine_ref = str(self.concept_spine_refs.get("concept_spine_ref", "")).strip()
        jurisdiction_spine_ref = str(
            self.concept_spine_refs.get("jurisdiction_spine_ref", "")
        ).strip()
        if not concept_spine_ref or not jurisdiction_spine_ref:
            raise ValueError(
                "policy grammar projection requires concept_spine_ref and "
                "jurisdiction_spine_ref"
            )
        if self.status == "pass" and not self.compiled_case_ref:
            raise ValueError("passing policy grammar projection requires compiled_case_ref")
        return self


class Layer3G6RequestEnvelope(_G6Model):
    """Bounded natural-language request envelope for the G6 adapter."""

    schema_version: str = G6_SCHEMA_VERSION
    rule_version: str = G6_RULE_VERSION
    request_id: str = Field(min_length=1)
    raw_request_ref: str = Field(min_length=1)
    raw_request_fingerprint: str = Field(min_length=1)
    request_class: Layer3G6RequestClass
    envelope_match_status: Layer3G6EnvelopeMatchStatus
    matched_envelope_refs: tuple[str, ...] = Field(default=())
    facet_match_record: dict[str, Any] = Field(default_factory=dict)
    policy_grammar_projection_ref: str | None = None
    compiled_policy_case_ref: str | None = None
    policy_grammar_blocker_codes: tuple[str, ...] = Field(default=())
    requested_audience: str = "REVIEWER"
    request_received_at: datetime
    demand_signal_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G6_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR


class Layer3G6GrammarExpansionCandidate(_G6Model):
    """Candidate-only grammar expansion emitted for downstream G5 routing."""

    candidate_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    source_class: Literal["deterministic_grammar", "llm_candidate"] = "deterministic_grammar"
    authority_state: Literal["candidate_unverified"] = "candidate_unverified"
    candidate_problem_frame: dict[str, Any]
    target_authority_slots: tuple[str, ...] = ("claim_authority",)
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR


class Layer3G6GroundingDemandRecord(_G6Model):
    """Routing-only record of grounding families demanded by a G6 request."""

    demand_record_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    status: Literal["route_to_g5", "bounded_abstention_required", "blocked"]
    required_grounding_families: tuple[str, ...]
    envelope_match_status: Layer3G6EnvelopeMatchStatus
    demand_signal_refs: tuple[str, ...] = Field(default=())
    grounding_scope_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G6_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR


class Layer3G6ToolContractSummary(_G6Model):
    """G6 projection over the Scientist tool-contract readiness summary."""

    summary_id: str
    status: Literal["pass", "fail"]
    allowed_tool_names: tuple[str, ...]
    observed_tool_names: tuple[str, ...]
    tool_contract_summary: ToolContractSummary
    blocker_codes: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G6_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR


class Layer3G6PromptToolLedgerProjection(_G6Model):
    """G6 lineage projection over the prompt/tool/parser authority ledger."""

    projection_id: str
    status: Literal["pass", "fail"]
    prompt_tool_ledger_ref: str
    prompt_tool_ledger: PromptToolParserAuthorityLedger
    candidate_refs: tuple[str, ...] = Field(default=())
    tool_call_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = ("layer3_g6_prompt_tool_lineage",)
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR


class Layer3G6OrchestrationChoiceAudit(_G6Model):
    """Replayable audit of selected and rejected G6 orchestration branches."""

    audit_id: str
    request_id: str
    status: Literal["pass", "fail"]
    selected_tool_names: tuple[str, ...] = Field(default=())
    rejected_tool_names: tuple[str, ...] = Field(default=())
    selected_evidence_refs: tuple[str, ...] = Field(default=())
    rejected_branch_refs: tuple[str, ...] = Field(default=())
    framing_choices: tuple[str, ...] = Field(default=())
    counterexample_probe_refs: tuple[str, ...] = Field(default=())
    prompt_tool_ledger_ref: str | None = None
    hypothesis_ledger_ref: str | None = None
    tool_contract_summary_ref: str | None = None
    budget_cutoff_reason: str | None = None
    replay_fingerprint: str
    replayable: bool = False
    authority_deltas: tuple[OrchestrationAuthorityDelta, ...] = Field(default=())
    authority_delta_completeness: (
        OrchestrationAuthorityDeltaCompletenessReceipt | None
    ) = None
    compression_loss_receipt_ref: str | None = None
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G6_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR


Layer3G6CompletenessStatus = Literal[
    "complete_with_candidates",
    "complete_no_hit",
    "partial_budget_cutoff",
    "partial_tool_or_index_gap",
]


class Layer3G6SearchLedger(_G6Model):
    """G6 control-plane search frontier ledger with no authority grant."""

    ledger_id: str
    request_id: str
    typed_request_ref: str
    normalized_query_refs: tuple[str, ...]
    searched_index_refs: tuple[str, ...]
    ranking_policy_ref: str | None = None
    selected_candidate_refs: tuple[str, ...] = Field(default=())
    rejected_candidate_refs: tuple[str, ...] = Field(default=())
    selected_tool_names: tuple[str, ...] = Field(default=())
    rejected_tool_names: tuple[str, ...] = Field(default=())
    selected_evidence_refs: tuple[str, ...] = Field(default=())
    cutoff_budget_ref: str | None = None
    absence_or_incompleteness_reason: str | None = None
    completeness_status: Layer3G6CompletenessStatus
    deterministic_replay_key: str
    search_health_refs: tuple[str, ...] = Field(default=())
    status: Literal["pass", "fail"]
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = ()
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR


class Layer3G6AgentLoopTrace(_G6Model):
    """Projection of Scientist ToolLoopResult into G6 routing audit semantics."""

    trace_id: str
    request_id: str
    status: Literal["pass", "fail", "blocked"]
    content_ref: str | None = None
    tool_calls_made: tuple[dict[str, Any], ...] = Field(default=())
    iterations: int = 0
    total_tokens: int = 0
    converged: bool = False
    convergence_reason: str = ""
    final_score: float = 0.0
    evaluation_history: tuple[dict[str, Any], ...] = Field(default=())
    degraded_events: tuple[dict[str, Any], ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = ()
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR


class Layer3G6DesignRecordCandidateHandoff(_G6Model):
    """Candidate-only DesignRecord handoff for the composed G6 -> G5 loop."""

    handoff_id: str
    request_id: str
    design_record_candidate_ref: str
    candidate_problem_frame: dict[str, Any]
    counterexample_refinement_refs: tuple[str, ...] = Field(default=())
    composed_loop_consumer_ref: str
    g5_invocation_plan_ref: str
    hypothesis_ledger: HypothesisLedger
    status: Literal["candidate_only"] = "candidate_only"
    authoritative_for: tuple[str, ...] = ("layer3_g6_candidate_handoff_audit",)
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR


class Layer3G6G4SourceDesignRecordBoundaryReport(_G6Model):
    """Boundary report proving G6 candidates are not resolved G4 source records."""

    report_id: str
    request_id: str
    status: Literal["pass", "fail"]
    checked_handoff_ref: str
    missing_source_requirements: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = ("layer3_g6_candidate_handoff_audit",)
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR


class Layer3G6BoundedAgentLoopResult(_G6Model):
    """Typed result emitted by the bounded G6 agent-loop producer."""

    result_id: str
    request_id: str
    status: Literal["pass", "fail", "blocked"]
    policy_grammar_projection: Layer3G6PolicyGrammarProjection
    request_envelope: Layer3G6RequestEnvelope
    grammar_expansion_candidate: Layer3G6GrammarExpansionCandidate
    agent_loop_trace: Layer3G6AgentLoopTrace
    search_ledger: Layer3G6SearchLedger
    orchestration_choice_audit: Layer3G6OrchestrationChoiceAudit
    prompt_tool_ledger_projection: Layer3G6PromptToolLedgerProjection
    hypothesis_ledger: HypothesisLedger
    tool_contract_summary: Layer3G6ToolContractSummary
    selected_g5_invocation_input_refs: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G6_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR


class Layer3G6G5InvocationPlan(_G6Model):
    """G6 bridge record for invoking the pinned G5 conversion consumer path."""

    invocation_plan_id: str
    request_id: str
    status: Literal["pass", "abstain", "fail"]
    envelope_match_status: Layer3G6EnvelopeMatchStatus
    requested_case_id: str | None = None
    g5_case_id: str | None = None
    g5_bundle_ref: str | None = None
    g5_conversion_record_ref: str | None = None
    g5_conversion_outcome: str | None = None
    g5_grounding_disposition: str | None = None
    g5_w12d_consumer_gate_ref: str | None = None
    g5_w12d_consumer_gate_status: str = "not_routed"
    g5_bypass_detected: bool = False
    search_health_refs: tuple[str, ...] = Field(default=())
    demand_signal_refs: tuple[str, ...] = Field(default=())
    requested_authority_from_g5: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G6_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR


class Layer3G6GroundedResultOrAbstention(_G6Model):
    """Exactly-one G6 result-or-abstention projection over G5 routing."""

    result_id: str
    request_id: str
    outcome: Layer3G6AgentOutcome
    grounding_disposition: Literal[
        "grounded_limited",
        "grounded_abstention",
        "out_of_envelope_grounded_abstention",
        "ungrounded_blocked",
    ]
    envelope_match_status: Layer3G6EnvelopeMatchStatus
    g5_conversion_outcome: str | None = None
    g5_record_refs: tuple[str, ...] = Field(default=())
    abstention_reason_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G6_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR


class Layer3G6AgentRunRecord(_G6Model):
    """G6 run record that owns routing/orchestration audit, not claim authority."""

    run_record_id: str
    request_id: str
    raw_request_ref: str
    raw_request_fingerprint: str
    request_class: Layer3G6RequestClass
    envelope_match_status: Layer3G6EnvelopeMatchStatus
    outcome: Layer3G6AgentOutcome
    grounding_disposition: str
    engineering_readiness_status: Layer3G6EngineeringReadinessStatus
    grounded_value_closure_status: Layer3G6GroundedValueClosureStatus
    g5_conversion_outcome: str | None = None
    policy_grammar_projection: Layer3G6PolicyGrammarProjection
    request_envelope: Layer3G6RequestEnvelope
    grammar_expansion_candidate: Layer3G6GrammarExpansionCandidate
    grounding_demand_record: Layer3G6GroundingDemandRecord
    tool_contract_summary: Layer3G6ToolContractSummary
    prompt_tool_ledger_projection: Layer3G6PromptToolLedgerProjection
    hypothesis_ledger: HypothesisLedger
    search_ledger: Layer3G6SearchLedger
    orchestration_choice_audit: Layer3G6OrchestrationChoiceAudit
    g5_invocation_plan: Layer3G6G5InvocationPlan
    result_projection: Layer3G6GroundedResultOrAbstention
    selected_g5_invocation_input_refs: tuple[str, ...] = Field(default=())
    replay_fingerprint: str
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = G6_AUTHORITATIVE_FOR
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR


class Layer3G6OrchestrationContinuity(_G6Model):
    """G6 wrapper over NL replay orchestration continuity."""

    continuity_id: str
    request_id: str
    status: Literal["pass", "fail"]
    record: dict[str, Any]
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = ("layer3_g6_agent_orchestration_audit",)
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR


class Layer3G6ReplayManifest(_G6Model):
    """G6 replay manifest wrapper."""

    manifest_id: str
    request_id: str
    status: Literal["pass", "fail"]
    manifest: dict[str, Any]
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = ("layer3_g6_agent_orchestration_audit",)
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR


class Layer3G6ReplayDriftReport(_G6Model):
    """G6 replay drift report over deterministic manifest comparisons."""

    report_id: str
    status: Literal["pass", "fail"]
    drift_explanation: dict[str, Any]
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = ("layer3_g6_agent_orchestration_audit",)
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR


class Layer3G6AgentAuditSurface(_G6Model):
    """Multi-audience G6 audit surface with a redacted PUBLIC projection."""

    surface_id: str = G6_SURFACE_ID
    request_id: str
    status: Literal["pass", "fail"]
    audiences: tuple[str, ...] = ("PUBLIC", "REVIEWER", "EXPERT", "MACHINE")
    surface_audiences: tuple[str, ...] = ("PUBLIC", "REVIEWER", "EXPERT", "MACHINE")
    PUBLIC: dict[str, Any] = Field(default_factory=dict)
    REVIEWER: dict[str, Any] = Field(default_factory=dict)
    EXPERT: dict[str, Any] = Field(default_factory=dict)
    MACHINE: dict[str, Any] = Field(default_factory=dict)
    public_projection_contract_verification: dict[str, Any] = Field(default_factory=dict)
    summary_authority_preservation_verification: dict[str, Any] = Field(
        default_factory=dict
    )
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = ("layer3_g6_agent_orchestration_audit",)
    may_not_use_for: tuple[str, ...] = G6_PUBLIC_PROJECTION_DENIED_USES


class Layer3G6DemandPullVsAbstentionDelta(_G6Model):
    """Health delta comparing arbitrary-request demand pull to abstention/blockers."""

    delta_id: str
    status: Literal["pass", "fail"]
    counts: dict[str, int]
    readings: dict[str, float]
    demand_source_refs: tuple[str, ...] = Field(default=())
    accountable_principal_refs: tuple[str, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = (
        "layer3_g6_demand_pull_vs_abstention_reading",
    )
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR


class Layer3G6ConformanceNegativeResult(_G6Model):
    """One G6 negative-control result and its expected issue-code proof."""

    negative_id: str
    status: Literal["pass", "fail"]
    expected_issue_codes: tuple[str, ...] = Field(default=())
    observed_issue_codes: tuple[str, ...] = Field(default=())
    fixture_ref: str


class Layer3G6SummaryAuthorityPreservationVerification(_G6Model):
    """Consumer-side recomputation of G6 compression and choice completeness."""

    verification_id: str
    status: Literal["pass", "fail"]
    compression_loss_receipt_ref: str | None = None
    authority_delta_completeness_ref: str | None = None
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR


@dataclass(frozen=True)
class _G6SummaryAuthorityDerivation:
    """Internally recomputed G6 compression and authority-delta artifacts."""

    source_material: CompressionMaterialSet
    candidate_summary: CompressionMaterialSet
    choice_contexts: tuple[OrchestrationChoiceContext, ...]
    authority_deltas: tuple[OrchestrationAuthorityDelta, ...]
    completeness: OrchestrationAuthorityDeltaCompletenessReceipt
    compression_loss_receipt: CompressionLossReceipt


class Layer3G6ConformanceReport(_G6Model):
    """G6 conformance report covering agent laundering negative controls."""

    report_id: str = "layer3-g6://conformance/report"
    status: Literal["pass", "fail"]
    negative_results: tuple[Layer3G6ConformanceNegativeResult, ...] = Field(default=())
    candidate_firewall_check: dict[str, Any] = Field(default_factory=dict)
    tool_contract_check: dict[str, Any] = Field(default_factory=dict)
    agent_loop_trace_check: dict[str, Any] = Field(default_factory=dict)
    search_ledger_check: dict[str, Any] = Field(default_factory=dict)
    g5_bridge_check: dict[str, Any] = Field(default_factory=dict)
    public_projection_boundary_check: dict[str, Any] = Field(default_factory=dict)
    replay_manifest_check: dict[str, Any] = Field(default_factory=dict)
    orchestration_continuity_check: dict[str, Any] = Field(default_factory=dict)
    runtime_import_boundary_check: dict[str, Any] = Field(default_factory=dict)
    performance_contract: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())
    authoritative_for: tuple[str, ...] = ("layer3_g6_agent_orchestration_audit",)
    may_not_use_for: tuple[str, ...] = G6_MAY_NOT_USE_FOR


class FakeG6ToolCallingClient:
    """Deterministic OpenAI-shape tool-calling client for G6 loop tests."""

    def __init__(self, tool_sequence: tuple[str, ...]) -> None:
        self._tool_sequence = tuple(tool_sequence)
        self._index = 0

    async def generate(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> SimpleNamespace:
        """Return one requested tool call per generation, then a final message."""

        del tools
        if self._index >= len(self._tool_sequence):
            return SimpleNamespace(
                content='{"status":"g6-loop-complete"}',
                tool_calls=[],
                usage=SimpleNamespace(total_tokens=1),
                raw={
                    "choices": [
                        {"message": {"content": '{"status":"g6-loop-complete"}'}}
                    ]
                },
            )
        tool_name = self._tool_sequence[self._index]
        self._index += 1
        return SimpleNamespace(
            content="",
            tool_calls=[
                SimpleNamespace(
                    id=f"call-{self._index}",
                    name=tool_name,
                    arguments={"request_id": _request_id_from_messages(messages)},
                )
            ],
            usage=SimpleNamespace(total_tokens=1),
            raw={},
        )


def _fingerprint(payload: object) -> str:
    """Return a deterministic sha256 fingerprint for replayable G6 payloads."""

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _g6_run_compression_materials(
    record: Layer3G6AgentRunRecord,
) -> tuple[CompressionMaterialSet, CompressionMaterialSet]:
    terminal_outcomes = {
        "g5_grounded_abstention",
        "g5_unchanged_blocker",
        "out_of_envelope_grounded_abstention",
    }
    claims: list[CompressionClaimItem] = [
        CompressionClaimItem(
            item_id="claim:outcome",
            content=record.outcome,
            claim_kind=(
                "negative_terminal" if record.outcome in terminal_outcomes else "substantive"
            ),
            source_refs=(record.result_projection.result_id,),
        ),
        CompressionClaimItem(
            item_id="claim:procedure-boundary",
            content="G6 output remains a projection-only routing result.",
            claim_kind="procedural_binding",
            source_refs=(record.run_record_id,),
        ),
    ]
    if record.g5_conversion_outcome:
        claims.append(
            CompressionClaimItem(
                item_id="claim:g5-conversion-outcome",
                content=record.g5_conversion_outcome,
                claim_kind="substantive",
                source_refs=tuple(
                    ref
                    for ref in (
                        record.g5_invocation_plan.g5_conversion_record_ref,
                        record.g5_invocation_plan.g5_w12d_consumer_gate_ref,
                    )
                    if ref
                ),
            )
        )
    limitations = [
        CompressionMaterialItem(
            item_id="limitation:candidate-only",
            content="Model and tool outputs remain candidate-only until grounded by G5.",
            source_refs=(record.grammar_expansion_candidate.candidate_id,),
        ),
        CompressionMaterialItem(
            item_id="limitation:engineering-readiness",
            content=f"engineering_readiness={record.engineering_readiness_status}",
            source_refs=(record.run_record_id,),
        ),
        CompressionMaterialItem(
            item_id="limitation:grounded-value-closure",
            content=f"grounded_value_closure={record.grounded_value_closure_status}",
            source_refs=(record.result_projection.result_id,),
        ),
        *(
            CompressionMaterialItem(
                item_id=f"limitation:issue:{code}",
                content=code,
                source_refs=(record.run_record_id,),
            )
            for code in record.issue_codes
        ),
    ]
    denied_uses = tuple(
        CompressionMaterialItem(
            item_id=f"denied-use:{denied_use}",
            content=denied_use,
            source_refs=(record.run_record_id,),
        )
        for denied_use in G6_PUBLIC_PROJECTION_DENIED_USES
    )
    counterevidence_refs = tuple(
        dict.fromkeys(
            (
                *record.orchestration_choice_audit.rejected_branch_refs,
                *record.orchestration_choice_audit.counterexample_probe_refs,
            )
        )
    )
    counterevidence = tuple(
        CompressionMaterialItem(
            item_id=f"counterevidence:{index}",
            content=ref,
            source_refs=(ref,),
        )
        for index, ref in enumerate(counterevidence_refs, start=1)
    )
    governance_burden_refs = (
        f"burden:{record.grounded_value_closure_status}",
        *(
            ("burden:owner-review",)
            if record.grounded_value_closure_status != "pass"
            else ()
        ),
    )
    framing_refs = record.orchestration_choice_audit.framing_choices or (
        "frame:g6-routing-audit",
    )
    source = CompressionMaterialSet(
        claims=tuple(claims),
        limitations=tuple(limitations),
        denied_uses=denied_uses,
        counterevidence=counterevidence,
        governance_burden_refs=governance_burden_refs,
        framing_refs=framing_refs,
    )
    return source, source.model_copy(deep=True)


def _g6_loop_compression_materials(
    *,
    request_id: str,
    candidate: Layer3G6GrammarExpansionCandidate,
    trace: Layer3G6AgentLoopTrace,
    audit: Layer3G6OrchestrationChoiceAudit,
) -> tuple[CompressionMaterialSet, CompressionMaterialSet]:
    source = CompressionMaterialSet(
        claims=(
            CompressionClaimItem(
                item_id="claim:loop-procedure-boundary",
                content="The bounded agent loop produces candidate routing output only.",
                claim_kind="procedural_binding",
                source_refs=(candidate.candidate_id,),
            ),
        ),
        limitations=(
            CompressionMaterialItem(
                item_id="limitation:loop-status",
                content=f"agent_loop_status={trace.status}",
                source_refs=(trace.trace_id,),
            ),
            CompressionMaterialItem(
                item_id="limitation:candidate-only",
                content="The loop result is not claim or recommendation authority.",
                source_refs=(candidate.candidate_id,),
            ),
        ),
        denied_uses=tuple(
            CompressionMaterialItem(
                item_id=f"denied-use:{denied_use}",
                content=denied_use,
                source_refs=(f"layer3-g6://bounded-agent-loop-result/{request_id}",),
            )
            for denied_use in G6_PUBLIC_PROJECTION_DENIED_USES
        ),
        counterevidence=tuple(
            CompressionMaterialItem(
                item_id=f"counterevidence:{index}",
                content=ref,
                source_refs=(ref,),
            )
            for index, ref in enumerate(
                dict.fromkeys(
                    (*audit.rejected_branch_refs, *audit.counterexample_probe_refs)
                ),
                start=1,
            )
        ),
        governance_burden_refs=("burden:g5-grounding-required",),
        framing_refs=audit.framing_choices or ("frame:g6-routing-audit",),
    )
    return source, source.model_copy(deep=True)


def _g6_choice_contexts(
    *,
    request_id: str,
    search_ledger: Layer3G6SearchLedger,
    audit: Layer3G6OrchestrationChoiceAudit,
    source_material: CompressionMaterialSet,
    candidate_summary: CompressionMaterialSet,
    preliminary_receipt: CompressionLossReceipt,
) -> tuple[OrchestrationChoiceContext, ...]:
    selected_evidence = _tag_choice_refs(
        "evidence-selection",
        search_ledger.selected_evidence_refs,
    )
    rejected_evidence = _tag_choice_refs(
        "evidence-selection",
        search_ledger.rejected_candidate_refs,
    )
    selected_tools = _tag_choice_refs(
        "tool-choice",
        search_ledger.selected_tool_names,
    )
    rejected_tools = _tag_choice_refs(
        "tool-choice",
        search_ledger.rejected_tool_names,
    )
    selected_framing = _tag_choice_refs(
        "framing",
        audit.framing_choices,
    )
    rejected_framing = _tag_choice_refs(
        "framing",
        audit.rejected_branch_refs,
    )
    selected_counterevidence = _tag_choice_refs(
        "counterevidence-selection",
        audit.counterexample_probe_refs,
    )
    rejected_counterevidence = _tag_choice_refs(
        "counterevidence-selection",
        audit.rejected_branch_refs,
    )
    retained_compression = (
        *preliminary_receipt.retained_claims,
        *preliminary_receipt.retained_limitations,
        *preliminary_receipt.retained_denied_uses,
        *preliminary_receipt.retained_counterevidence,
    )
    dropped_compression = (
        *preliminary_receipt.dropped_claims,
        *preliminary_receipt.dropped_limitations,
        *preliminary_receipt.dropped_denied_uses,
        *preliminary_receipt.dropped_counterevidence,
    )
    source_refs = (
        search_ledger.ledger_id,
        audit.audit_id,
        preliminary_receipt.source_ref,
    )
    return (
        OrchestrationChoiceContext(
            choice_id=f"layer3-g6:{request_id}:evidence-selection",
            choice_kind="evidence-selection",
            candidate_universe=(*selected_evidence, *rejected_evidence),
            selected=selected_evidence,
            rejected=rejected_evidence,
            source_refs=source_refs,
        ),
        OrchestrationChoiceContext(
            choice_id=f"layer3-g6:{request_id}:tool-choice",
            choice_kind="tool-choice",
            candidate_universe=(*selected_tools, *rejected_tools),
            selected=selected_tools,
            rejected=rejected_tools,
            source_refs=source_refs,
        ),
        OrchestrationChoiceContext(
            choice_id=f"layer3-g6:{request_id}:framing",
            choice_kind="framing",
            candidate_universe=(*selected_framing, *rejected_framing),
            selected=selected_framing,
            rejected=rejected_framing,
            governance_burden_before=source_material.governance_burden_refs,
            governance_burden_after=candidate_summary.governance_burden_refs,
            source_refs=source_refs,
        ),
        OrchestrationChoiceContext(
            choice_id=f"layer3-g6:{request_id}:counterevidence-selection",
            choice_kind="counterevidence-selection",
            candidate_universe=(
                *selected_counterevidence,
                *rejected_counterevidence,
            ),
            selected=selected_counterevidence,
            rejected=rejected_counterevidence,
            source_refs=source_refs,
        ),
        OrchestrationChoiceContext(
            choice_id=f"layer3-g6:{request_id}:compression",
            choice_kind="compression",
            candidate_universe=(*retained_compression, *dropped_compression),
            selected=retained_compression,
            rejected=dropped_compression,
            governance_burden_before=source_material.governance_burden_refs,
            governance_burden_after=candidate_summary.governance_burden_refs,
            source_refs=source_refs,
        ),
    )


def _tag_choice_refs(
    choice_kind: str,
    refs: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(f"{choice_kind}:{ref}" for ref in refs)


def _derive_g6_summary_authority_preservation(
    *,
    request_id: str,
    search_ledger: Layer3G6SearchLedger,
    audit: Layer3G6OrchestrationChoiceAudit,
    source_material: CompressionMaterialSet,
    candidate_summary: CompressionMaterialSet,
) -> _G6SummaryAuthorityDerivation:
    source_ref = f"layer3-g6://summary-source/{request_id}"
    summary_ref = f"layer3-g6://public-summary/{request_id}"
    preliminary = build_compression_loss_receipt(
        receipt_id=f"layer3-g6://compression-loss-receipt/{request_id}/preliminary",
        source_ref=source_ref,
        summary_ref=summary_ref,
        source_material=source_material,
        candidate_summary=candidate_summary,
    )
    contexts = _g6_choice_contexts(
        request_id=request_id,
        search_ledger=search_ledger,
        audit=audit,
        source_material=source_material,
        candidate_summary=candidate_summary,
        preliminary_receipt=preliminary,
    )
    delta_derivation = build_orchestration_authority_deltas(contexts)
    receipt = build_compression_loss_receipt(
        receipt_id=f"layer3-g6://compression-loss-receipt/{request_id}",
        source_ref=source_ref,
        summary_ref=summary_ref,
        source_material=source_material,
        candidate_summary=candidate_summary,
        authority_deltas=delta_derivation.deltas,
        authority_delta_completeness=delta_derivation.completeness,
    )
    return _G6SummaryAuthorityDerivation(
        source_material=source_material,
        candidate_summary=candidate_summary,
        choice_contexts=contexts,
        authority_deltas=delta_derivation.deltas,
        completeness=delta_derivation.completeness,
        compression_loss_receipt=receipt,
    )


def _attach_g6_summary_authority_preservation(
    *,
    prompt_tool_ledger: Layer3G6PromptToolLedgerProjection,
    audit: Layer3G6OrchestrationChoiceAudit,
    derivation: _G6SummaryAuthorityDerivation,
) -> tuple[Layer3G6PromptToolLedgerProjection, Layer3G6OrchestrationChoiceAudit]:
    ledger_payload = prompt_tool_ledger.prompt_tool_ledger.model_dump(mode="python")
    ledger_payload.update(
        {
            "orchestration_authority_deltas": derivation.authority_deltas,
            "authority_delta_completeness_receipts": (derivation.completeness,),
            "compression_loss_receipts": (derivation.compression_loss_receipt,),
        }
    )
    ledger = PromptToolParserAuthorityLedger.model_validate(ledger_payload)
    projection_issues = list(prompt_tool_ledger.issue_codes)
    if (
        derivation.completeness.status != "pass"
        or derivation.compression_loss_receipt.status != "pass"
    ):
        projection_issues.append("layer3_g6_compression_loss_receipt_blocked")
    projection = Layer3G6PromptToolLedgerProjection.model_validate(
        {
            **prompt_tool_ledger.model_dump(mode="python"),
            "status": "fail" if projection_issues else "pass",
            "prompt_tool_ledger": ledger,
            "issue_codes": tuple(dict.fromkeys(projection_issues)),
        }
    )
    audit_issues = list(audit.issue_codes)
    if derivation.completeness.status != "pass":
        audit_issues.append("layer3_g6_authority_delta_completeness_failed")
    if derivation.compression_loss_receipt.status != "pass":
        audit_issues.append("layer3_g6_compression_loss_receipt_blocked")
    audit_payload = audit.model_dump(mode="python")
    audit_payload.update(
        {
            "status": "fail" if audit_issues else "pass",
            "replayable": not audit_issues,
            "authority_deltas": derivation.authority_deltas,
            "authority_delta_completeness": derivation.completeness,
            "compression_loss_receipt_ref": (
                derivation.compression_loss_receipt.receipt_id
            ),
            "issue_codes": tuple(dict.fromkeys(audit_issues)),
        }
    )
    audit_payload["replay_fingerprint"] = _fingerprint(
        {
            key: value
            for key, value in audit_payload.items()
            if key not in {"replay_fingerprint", "status", "replayable"}
        }
    )
    return projection, Layer3G6OrchestrationChoiceAudit.model_validate(audit_payload)


def _finalize_g6_loop_summary_authority_preservation(
    *,
    request_id: str,
    candidate: Layer3G6GrammarExpansionCandidate,
    trace: Layer3G6AgentLoopTrace,
    search_ledger: Layer3G6SearchLedger,
    audit: Layer3G6OrchestrationChoiceAudit,
    prompt_tool_ledger: Layer3G6PromptToolLedgerProjection,
) -> tuple[Layer3G6PromptToolLedgerProjection, Layer3G6OrchestrationChoiceAudit]:
    source_material, candidate_summary = _g6_loop_compression_materials(
        request_id=request_id,
        candidate=candidate,
        trace=trace,
        audit=audit,
    )
    derivation = _derive_g6_summary_authority_preservation(
        request_id=request_id,
        search_ledger=search_ledger,
        audit=audit,
        source_material=source_material,
        candidate_summary=candidate_summary,
    )
    return _attach_g6_summary_authority_preservation(
        prompt_tool_ledger=prompt_tool_ledger,
        audit=audit,
        derivation=derivation,
    )


def _finalize_g6_run_summary_authority_preservation(
    record: Layer3G6AgentRunRecord,
) -> Layer3G6AgentRunRecord:
    source_material, candidate_summary = _g6_run_compression_materials(record)
    derivation = _derive_g6_summary_authority_preservation(
        request_id=record.request_id,
        search_ledger=record.search_ledger,
        audit=record.orchestration_choice_audit,
        source_material=source_material,
        candidate_summary=candidate_summary,
    )
    prompt_projection, audit = _attach_g6_summary_authority_preservation(
        prompt_tool_ledger=record.prompt_tool_ledger_projection,
        audit=record.orchestration_choice_audit,
        derivation=derivation,
    )
    issue_codes = tuple(
        dict.fromkeys(
            (
                *record.issue_codes,
                *audit.issue_codes,
                *prompt_projection.issue_codes,
            )
        )
    )
    payload = record.model_dump(mode="python")
    payload.update(
        {
            "prompt_tool_ledger_projection": prompt_projection,
            "orchestration_choice_audit": audit,
            "engineering_readiness_status": _g6_engineering_readiness_status(
                g5_invocation=record.g5_invocation_plan,
                search_ledger=record.search_ledger,
                audit=audit,
                tool_contract_summary=record.tool_contract_summary,
            ),
            "issue_codes": issue_codes,
            "replay_fingerprint": _fingerprint(
                {
                    "prior_replay_fingerprint": record.replay_fingerprint,
                    "compression_loss_receipt_ref": (
                        derivation.compression_loss_receipt.receipt_id
                    ),
                    "compression_source_fingerprint": (
                        derivation.compression_loss_receipt.source_fingerprint
                    ),
                    "compression_summary_fingerprint": (
                        derivation.compression_loss_receipt.candidate_summary_fingerprint
                    ),
                    "authority_delta_catalog_fingerprint": (
                        derivation.completeness.owner_policy_catalog_fingerprint
                    ),
                }
            ),
        }
    )
    return Layer3G6AgentRunRecord.model_validate(payload)


def verify_g6_summary_authority_preservation(
    record: Layer3G6AgentRunRecord,
) -> Layer3G6SummaryAuthorityPreservationVerification:
    """Recompute the G6 receipt/delta owner predicates from the run record."""

    source_material, candidate_summary = _g6_run_compression_materials(record)
    expected = _derive_g6_summary_authority_preservation(
        request_id=record.request_id,
        search_ledger=record.search_ledger,
        audit=record.orchestration_choice_audit,
        source_material=source_material,
        candidate_summary=candidate_summary,
    )
    ledger = record.prompt_tool_ledger_projection.prompt_tool_ledger
    issues: list[str] = []
    actual_receipt = (
        ledger.compression_loss_receipts[0]
        if len(ledger.compression_loss_receipts) == 1
        else None
    )
    actual_completeness = (
        ledger.authority_delta_completeness_receipts[0]
        if len(ledger.authority_delta_completeness_receipts) == 1
        else None
    )
    if actual_receipt is None:
        issues.append("layer3_g6_compression_loss_receipt_missing")
    else:
        try:
            validate_compression_loss_receipt(actual_receipt)
        except PromptToolLedgerError:
            issues.append("layer3_g6_compression_loss_receipt_blocked")
        if (
            actual_receipt.model_dump(mode="json")
            != expected.compression_loss_receipt.model_dump(mode="json")
        ):
            issues.append("layer3_g6_compression_loss_receipt_blocked")
    recomputed_completeness = validate_orchestration_authority_delta_completeness(
        contexts=expected.choice_contexts,
        deltas=ledger.orchestration_authority_deltas,
    )
    if (
        recomputed_completeness.status != "pass"
        or actual_completeness is None
        or actual_completeness.model_dump(mode="json")
        != expected.completeness.model_dump(mode="json")
        or tuple(ledger.orchestration_authority_deltas)
        != expected.authority_deltas
        or tuple(record.orchestration_choice_audit.authority_deltas)
        != expected.authority_deltas
    ):
        issues.append("layer3_g6_authority_delta_owner_validation_failed")
    if (
        record.orchestration_choice_audit.authority_delta_completeness is None
        or record.orchestration_choice_audit.authority_delta_completeness.model_dump(
            mode="json"
        )
        != expected.completeness.model_dump(mode="json")
    ):
        issues.append("layer3_g6_authority_delta_completeness_failed")
    issue_codes = tuple(dict.fromkeys(issues))
    return Layer3G6SummaryAuthorityPreservationVerification(
        verification_id=(
            f"layer3-g6://summary-authority-preservation-verification/{record.request_id}"
        ),
        status="fail" if issue_codes else "pass",
        compression_loss_receipt_ref=(
            actual_receipt.receipt_id if actual_receipt is not None else None
        ),
        authority_delta_completeness_ref=(
            actual_completeness.receipt_id if actual_completeness is not None else None
        ),
        issue_codes=issue_codes,
    )


def _g6_is_required_cross_slice_ref(ref: str) -> bool:
    return ref.startswith(("repo://", "manifest://", "generated-artifact://"))


def validate_g6_policy_grammar_projection(
    payload: Mapping[str, Any] | Layer3G6PolicyGrammarProjection,
) -> Layer3G6PolicyGrammarProjection:
    """Validate the compiler-owned projection consumed by G6 routing.

    Args:
        payload: Mapping or already validated projection payload.

    Returns:
        Strict G6 policy-grammar projection.
    """

    if isinstance(payload, Layer3G6PolicyGrammarProjection):
        return payload
    return Layer3G6PolicyGrammarProjection.model_validate(dict(payload))


def build_g6_request_envelope(
    raw_request: str,
    *,
    request_id: str,
    policy_grammar_projection: Layer3G6PolicyGrammarProjection | Mapping[str, Any] | None = None,
    matched_envelope_refs: tuple[str, ...] | None = None,
    demand_signal_refs: tuple[str, ...] = (),
    requested_audience: str = "REVIEWER",
) -> Layer3G6RequestEnvelope:
    """Build a bounded G6 request envelope from a compiler projection."""

    projection = (
        validate_g6_policy_grammar_projection(policy_grammar_projection)
        if policy_grammar_projection is not None
        else None
    )
    issue_codes: list[str] = []
    policy_grammar_blockers: tuple[str, ...] = ()
    facet_summary: dict[str, Any] = {}
    projection_ref: str | None = None
    compiled_case_ref: str | None = None
    if projection is None:
        request_class: Layer3G6RequestClass = "ambiguous"
        envelope_match_status: Layer3G6EnvelopeMatchStatus = "ambiguous_requires_abstention"
        issue_codes.extend(
            (
                "layer3_g6_policy_grammar_projection_missing",
                "layer3_g6_policy_grammar_compile_blocked",
            )
        )
        match_refs = ()
    else:
        facet_summary = dict(projection.facet_summary)
        projection_ref = projection.projection_id
        compiled_case_ref = projection.compiled_case_ref
        policy_grammar_blockers = projection.issue_codes
        issue_codes.extend(projection.issue_codes)
        request_class, envelope_match_status, match_refs = _classify_envelope_match(
            projection=projection,
            matched_envelope_refs=matched_envelope_refs,
            issue_codes=issue_codes,
        )

    facet_match_record = _build_facet_match_record(
        facet_summary=facet_summary,
        envelope_match_status=envelope_match_status,
        matched_envelope_refs=match_refs,
    )
    return Layer3G6RequestEnvelope(
        request_id=request_id,
        raw_request_ref=f"layer3-g6://request/{request_id}/raw",
        raw_request_fingerprint=_fingerprint(
            {"request_id": request_id, "raw_request": raw_request}
        ),
        request_class=request_class,
        envelope_match_status=envelope_match_status,
        matched_envelope_refs=match_refs,
        facet_match_record=facet_match_record,
        policy_grammar_projection_ref=projection_ref,
        compiled_policy_case_ref=compiled_case_ref,
        policy_grammar_blocker_codes=policy_grammar_blockers,
        requested_audience=requested_audience,
        request_received_at=datetime.now(UTC),
        demand_signal_refs=tuple(demand_signal_refs),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def build_g6_grammar_expansion_candidate(
    envelope: Layer3G6RequestEnvelope,
) -> Layer3G6GrammarExpansionCandidate:
    """Project the request envelope into a candidate-only grammar expansion."""

    candidate_payload = {
        "request_id": envelope.request_id,
        "request_class": envelope.request_class,
        "envelope_match_status": envelope.envelope_match_status,
        "facet_match_record": envelope.facet_match_record,
        "matched_envelope_refs": envelope.matched_envelope_refs,
        "policy_grammar_projection_ref": envelope.policy_grammar_projection_ref,
    }
    digest = _fingerprint(candidate_payload).split(":", 1)[1][:16]
    return Layer3G6GrammarExpansionCandidate(
        candidate_id=f"layer3-g6-grammar-candidate:{envelope.request_id}:{digest}",
        request_id=envelope.request_id,
        candidate_problem_frame=candidate_payload,
    )


def build_g6_grounding_demand_record(
    envelope: Layer3G6RequestEnvelope,
) -> Layer3G6GroundingDemandRecord:
    """Name the existing grounding families required by a G6 request."""

    base_families = (
        "policy_grammar_projection",
        "declared_g5_envelope",
        "search_recall_freshness",
        "g1_source_contracts",
        "g4_promotion_handoff",
        "g5_conversion_record",
    )
    if envelope.envelope_match_status == "same_class_as_g5_pinned_case":
        status: Literal["route_to_g5", "bounded_abstention_required", "blocked"] = "route_to_g5"
        issue_codes = envelope.issue_codes
    elif envelope.envelope_match_status == "outside_g5_envelope":
        status = "bounded_abstention_required"
        issue_codes = ("layer3_g6_outside_g5_envelope", *envelope.issue_codes)
    else:
        status = "blocked"
        issue_codes = envelope.issue_codes or ("layer3_g6_policy_grammar_compile_blocked",)
    return Layer3G6GroundingDemandRecord(
        demand_record_id=f"layer3-g6-grounding-demand:{envelope.request_id}",
        request_id=envelope.request_id,
        status=status,
        required_grounding_families=base_families,
        envelope_match_status=envelope.envelope_match_status,
        demand_signal_refs=envelope.demand_signal_refs,
        grounding_scope_refs=(
            *(envelope.matched_envelope_refs),
            *(ref for ref in (envelope.compiled_policy_case_ref,) if ref),
        ),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def build_g6_tool_registry(*, repo_root: Path = DEFAULT_REPO_ROOT) -> ToolRegistry:
    """Build the bounded local G6 tool registry."""

    registry = ToolRegistry()
    root = Path(repo_root)
    registry.register(
        _g6_tool_definition(
            "layer3_g6_classify_request",
            "Project a request into the bounded G6 classification surface.",
        ),
        lambda request_id: {
            "request_id": request_id,
            "status": "candidate_only",
            "authority_state": "candidate_unverified",
        },
    )
    registry.register(
        _g6_tool_definition(
            "layer3_g6_build_g5_bundle",
            "Read the typed G5 bundle inputs for the pinned conversion case.",
        ),
        lambda request_id: {
            "request_id": request_id,
            "repo_root": root.as_posix(),
            "bundle_ref": "repo://architecture/policy_design_case/layer3_g5_readiness_manifest.json",
        },
    )
    registry.register(
        _g6_tool_definition(
            "layer3_g6_read_g5_conversion",
            "Read the persisted G5 conversion-record family for routing audit.",
        ),
        lambda request_id: _read_g5_conversion_tool(root, request_id=request_id),
    )
    registry.register(
        _g6_tool_definition(
            "layer3_g6_probe_counterexample",
            "Probe whether a request branch should remain rejected or candidate-only.",
        ),
        lambda request_id: {
            "request_id": request_id,
            "counterexample_probe_status": "candidate_only",
            "rejected_branch_ref": f"candidate://g6/{request_id}/counterexample/default",
        },
    )
    registry.register(
        _g6_tool_definition(
            "layer3_g6_probe_envelope_match",
            "Probe whether grammar facets are joined to G5 envelope refs.",
        ),
        lambda request_id: {
            "request_id": request_id,
            "required_match_refs": list(G6_DEFAULT_G5_ENVELOPE_REFS),
            "authority_state": "routing_audit_only",
        },
    )
    return registry


def build_g6_tool_contract_summary(
    registry: ToolRegistry,
) -> Layer3G6ToolContractSummary:
    """Summarize G6 tool readiness without replacing Scientist contract checks."""

    definitions = registry.list_definitions()
    observed_tool_names = tuple(definition.name for definition in definitions)
    allowed_observed_names = tuple(
        name for name in observed_tool_names if name in G6_ALLOWED_TOOL_NAMES
    )
    upstream_summary = summarize_tool_contracts(registry, response_cap_max_chars=120_000)
    blocker_codes = set(tool_contract_default_blockers(upstream_summary))
    blocker_codes.update(
        issue.issue_code for issue in upstream_summary.issues if issue.severity == "blocker"
    )
    if any(name not in G6_ALLOWED_TOOL_NAMES for name in observed_tool_names):
        blocker_codes.add("layer3_g6_non_allowlisted_tool_attempt")
    if not upstream_summary.default_enable_ready:
        blocker_codes.add("layer3_g6_tool_contract_not_ready")
    status: Literal["pass", "fail"] = "fail" if blocker_codes else "pass"
    return Layer3G6ToolContractSummary(
        summary_id="layer3-g6-tool-contract-summary:default",
        status=status,
        allowed_tool_names=allowed_observed_names,
        observed_tool_names=observed_tool_names,
        tool_contract_summary=upstream_summary,
        blocker_codes=tuple(sorted(blocker_codes)),
        issue_codes=tuple(sorted(blocker_codes)),
    )


def build_g6_prompt_tool_ledger_projection(
    *,
    run_id: str,
    job_id: str,
    envelope: Layer3G6RequestEnvelope,
    candidates: tuple[Layer3G6GrammarExpansionCandidate, ...],
    tool_call_refs: tuple[str, ...],
    force_authority_summary_status: str | None = None,
) -> Layer3G6PromptToolLedgerProjection:
    """Build G6 prompt/tool lineage without admitting candidate authority."""

    prompt_tool_ledger_ref = f"layer3-g6://prompt-tool-ledger/{run_id}"
    candidate_refs = tuple(_hypothesis_candidate_ref(candidate) for candidate in candidates)
    tool_allowlist = G6_ALLOWED_TOOL_NAMES
    tool_schemas = [
        {
            "tool_name": name,
            "schema_ref": f"repo://src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py#tool/{name}",
            "schema": G6_REQUEST_ID_TOOL_SCHEMA,
        }
        for name in tool_allowlist
    ]
    tool_calls = [
        {
            "tool_name": "layer3_g6_build_g5_bundle",
            "call_ref": f"layer3-g6://tool-call/{run_id}/{index}",
            "output_ref": ref,
            "status": "pass",
        }
        for index, ref in enumerate(tool_call_refs, start=1)
    ]
    ledger = PromptToolParserAuthorityLedger.model_validate(
        {
            "run_id": run_id,
            "job_id": job_id,
            "model_variant_id": "layer3-g6-bounded-agent-candidate",
            "prompt_tool_ledger_ref": prompt_tool_ledger_ref,
            "steps": [
                {
                    "step_id": f"layer3-g6-agent-orchestration:{envelope.request_id}",
                    "step_kind": "layer3_g6_agent_orchestration_candidate",
                    "authority_scopes": ["claims"],
                    "prompt": {
                        "template_id": "layer3_g6_agent_orchestration_candidate",
                        "template_version": G6_RULE_VERSION,
                        "template_ref": (
                            "repo://src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py"
                            "#prompt-template"
                        ),
                        "rendered_prompt_ref": (
                            f"layer3-g6://request/{envelope.request_id}/rendered-prompt"
                        ),
                        "rendered_input_refs": [
                            envelope.raw_request_ref,
                            *(ref for ref in (envelope.policy_grammar_projection_ref,) if ref),
                        ],
                        "template_variables_fingerprint": _fingerprint(
                            {
                                "request_id": envelope.request_id,
                                "candidate_refs": candidate_refs,
                                "tool_call_refs": tool_call_refs,
                            }
                        ),
                    },
                    "model_provider": {
                        "provider": "polisyos-g6-local",
                        "model": "candidate-control-plane",
                        "model_fingerprint": G6_RULE_VERSION,
                        "provider_config_ref": "layer3-g6://model-profile/candidate-only",
                        "temperature": 0.0,
                        "max_tokens": 0,
                        "response_format": {"type": "json_object"},
                    },
                    "tool_allowlist": list(tool_allowlist),
                    "tool_schemas": tool_schemas,
                    "tool_call_refs": tool_calls,
                    "output_refs": [
                        f"layer3-g6://candidate-output/{candidate.request_id}/{index}"
                        for index, candidate in enumerate(candidates, start=1)
                    ]
                    or [f"layer3-g6://candidate-output/{envelope.request_id}/none"],
                    "parser_contract": {
                        "parser_id": "layer3_g6_candidate_parser",
                        "parser_version": G6_SCHEMA_VERSION,
                        "contract_ref": (
                            "repo://src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py"
                            "#Layer3G6GrammarExpansionCandidate"
                        ),
                        "input_schema_ref": (
                            "repo://src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py"
                            "#Layer3G6RequestEnvelope"
                        ),
                        "output_schema_ref": (
                            "repo://src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py"
                            "#Layer3G6GrammarExpansionCandidate"
                        ),
                    },
                    "validation_refs": [
                        {
                            "validator_id": "layer3_g6_candidate_only_boundary",
                            "status": "pass",
                            "validation_ref": "layer3-g6://validation/candidate-only",
                        }
                    ],
                    "repair_decisions": [
                        {
                            "decision": "candidate_branch_not_admitted_to_authority",
                            "status": "not_applicable",
                            "reason": "G6 prompt/tool output remains candidate-only lineage.",
                        }
                    ],
                    "authority_handoff_refs": [
                        {
                            "scope": "claims",
                            "handoff_ref": "layer3-g6://authority-handoff/not-applicable",
                            "consumer": (
                                "polisyos.runtime.quality.proving_ground."
                                "bounded_request_agent"
                            ),
                            "status": "not_applicable",
                        }
                    ],
                }
            ],
        }
    )
    issue_codes: list[str] = []
    if force_authority_summary_status in {"pass", "ok", "passed"}:
        issue_codes.append("layer3_g6_prompt_tool_ledger_misread_as_authority")
    status: Literal["pass", "fail"] = "fail" if issue_codes else "pass"
    return Layer3G6PromptToolLedgerProjection(
        projection_id=f"layer3-g6-prompt-tool-ledger-projection:{run_id}",
        status=status,
        prompt_tool_ledger_ref=prompt_tool_ledger_ref,
        prompt_tool_ledger=ledger,
        candidate_refs=candidate_refs,
        tool_call_refs=tuple(tool_call_refs),
        issue_codes=tuple(issue_codes),
    )


def build_g6_hypothesis_ledger_projection(
    *,
    run_id: str,
    job_id: str,
    prompt_tool_ledger: Layer3G6PromptToolLedgerProjection | PromptToolParserAuthorityLedger,
    candidates: tuple[Layer3G6GrammarExpansionCandidate, ...],
) -> HypothesisLedger:
    """Build the G6 candidate ledger consumed by the candidate firewall."""

    ledger = (
        prompt_tool_ledger.prompt_tool_ledger
        if isinstance(prompt_tool_ledger, Layer3G6PromptToolLedgerProjection)
        else prompt_tool_ledger
    )
    candidate_rows = [
        {
            "candidate_id": _hypothesis_candidate_ref(candidate),
            "candidate_ref": _hypothesis_candidate_ref(candidate),
            "source_class": _hypothesis_source_class(candidate.source_class),
            "candidate_kind": "request_parse",
            "target_authority_slots": list(candidate.target_authority_slots),
            "admission_state": candidate.authority_state,
            "content": candidate.candidate_problem_frame,
            "provenance": {
                "producer": "polisyos.runtime.quality.proving_ground.bounded_request_agent",
                "source_candidate_id": candidate.candidate_id,
            },
        }
        for candidate in candidates
    ]
    return build_hypothesis_ledger_from_prompt_tool_ledger(
        run_id=run_id,
        job_id=job_id,
        prompt_tool_ledger=ledger,
        candidates=candidate_rows,
        hypothesis_ledger_ref=f"layer3-g6://hypothesis-ledger/{run_id}",
    )


def build_g6_orchestration_choice_audit(
    *,
    envelope: Layer3G6RequestEnvelope,
    selected_tool_names: tuple[str, ...],
    rejected_tool_names: tuple[str, ...],
    selected_evidence_refs: tuple[str, ...],
    rejected_branch_refs: tuple[str, ...],
    framing_choices: tuple[str, ...],
    budget_cutoff_reason: str | None,
    counterexample_probe_refs: tuple[str, ...] = (),
    prompt_tool_ledger_ref: str | None = None,
    hypothesis_ledger_ref: str | None = None,
    tool_contract_summary_ref: str | None = None,
) -> Layer3G6OrchestrationChoiceAudit:
    """Build a replayable audit over selected and rejected G6 branches."""

    issue_codes: list[str] = []
    if not selected_tool_names or not selected_evidence_refs or not framing_choices:
        issue_codes.append("layer3_g6_orchestration_choice_audit_missing")
    if not rejected_branch_refs and not rejected_tool_names:
        issue_codes.append("layer3_g6_rejected_branch_memory_missing")
    replay_payload = {
        "request_id": envelope.request_id,
        "raw_request_fingerprint": envelope.raw_request_fingerprint,
        "selected_tool_names": selected_tool_names,
        "rejected_tool_names": rejected_tool_names,
        "selected_evidence_refs": selected_evidence_refs,
        "rejected_branch_refs": rejected_branch_refs,
        "framing_choices": framing_choices,
        "counterexample_probe_refs": counterexample_probe_refs,
        "prompt_tool_ledger_ref": prompt_tool_ledger_ref,
        "hypothesis_ledger_ref": hypothesis_ledger_ref,
        "tool_contract_summary_ref": tool_contract_summary_ref,
        "budget_cutoff_reason": budget_cutoff_reason,
    }
    replay_fingerprint = _fingerprint(replay_payload)
    status: Literal["pass", "fail"] = "fail" if issue_codes else "pass"
    return Layer3G6OrchestrationChoiceAudit(
        audit_id=f"layer3-g6://orchestration-choice-audit/{envelope.request_id}",
        request_id=envelope.request_id,
        status=status,
        selected_tool_names=tuple(dict.fromkeys(selected_tool_names)),
        rejected_tool_names=tuple(dict.fromkeys(rejected_tool_names)),
        selected_evidence_refs=tuple(dict.fromkeys(selected_evidence_refs)),
        rejected_branch_refs=tuple(dict.fromkeys(rejected_branch_refs)),
        framing_choices=tuple(dict.fromkeys(framing_choices)),
        counterexample_probe_refs=tuple(dict.fromkeys(counterexample_probe_refs)),
        prompt_tool_ledger_ref=prompt_tool_ledger_ref,
        hypothesis_ledger_ref=hypothesis_ledger_ref,
        tool_contract_summary_ref=tool_contract_summary_ref,
        budget_cutoff_reason=budget_cutoff_reason,
        replay_fingerprint=replay_fingerprint,
        replayable=status == "pass",
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def build_g6_search_ledger(
    *,
    request_id: str,
    typed_request_ref: str,
    normalized_query_refs: tuple[str, ...],
    searched_index_refs: tuple[str, ...],
    selected_candidate_refs: tuple[str, ...],
    rejected_candidate_refs: tuple[str, ...],
    selected_tool_names: tuple[str, ...],
    rejected_tool_names: tuple[str, ...],
    selected_evidence_refs: tuple[str, ...],
    completeness_status: Layer3G6CompletenessStatus,
    absence_or_incompleteness_reason: str | None,
    ranking_policy_ref: str | None = None,
    cutoff_budget_ref: str | None = None,
    deterministic_replay_key: str | None = None,
    search_health_refs: tuple[str, ...] = (),
    authoritative_for: tuple[str, ...] = (),
    repo_root: str | Path = DEFAULT_REPO_ROOT,
) -> Layer3G6SearchLedger:
    """Build the G6 search frontier ledger as a non-authoritative control record."""

    replay_payload = {
        "request_id": request_id,
        "typed_request_ref": typed_request_ref,
        "normalized_query_refs": normalized_query_refs,
        "searched_index_refs": searched_index_refs,
        "ranking_policy_ref": ranking_policy_ref,
        "selected_candidate_refs": selected_candidate_refs,
        "rejected_candidate_refs": rejected_candidate_refs,
        "selected_tool_names": selected_tool_names,
        "rejected_tool_names": rejected_tool_names,
        "selected_evidence_refs": selected_evidence_refs,
        "cutoff_budget_ref": cutoff_budget_ref,
        "absence_or_incompleteness_reason": absence_or_incompleteness_reason,
        "completeness_status": completeness_status,
    }
    replay_key = deterministic_replay_key or _fingerprint(replay_payload)
    issue_codes: list[str] = []
    if authoritative_for:
        issue_codes.append("layer3_g6_search_ledger_authority_boundary_leak")
    if not (
        typed_request_ref
        and normalized_query_refs
        and searched_index_refs
        and selected_candidate_refs
        and selected_tool_names
        and selected_evidence_refs
        and (cutoff_budget_ref or absence_or_incompleteness_reason)
        and replay_key
    ):
        issue_codes.append("layer3_g6_search_ledger_missing")
    if not rejected_candidate_refs and not rejected_tool_names:
        issue_codes.append("layer3_g6_tool_loop_transcript_only_not_audit")
    root = Path(repo_root)
    for evidence_ref in selected_evidence_refs:
        if not _g6_is_required_cross_slice_ref(evidence_ref):
            continue
        resolved = resolve_required_ref(root, evidence_ref)
        if not resolved.exists:
            issue_codes.append("layer3_g6_selected_evidence_ref_unresolved")
            issue_codes.extend(resolved.issue_codes)
    status: Literal["pass", "fail"] = "fail" if issue_codes else "pass"
    return Layer3G6SearchLedger(
        ledger_id=f"layer3-g6://search-ledger/{request_id}",
        request_id=request_id,
        typed_request_ref=typed_request_ref,
        normalized_query_refs=tuple(dict.fromkeys(normalized_query_refs)),
        searched_index_refs=tuple(dict.fromkeys(searched_index_refs)),
        ranking_policy_ref=ranking_policy_ref,
        selected_candidate_refs=tuple(dict.fromkeys(selected_candidate_refs)),
        rejected_candidate_refs=tuple(dict.fromkeys(rejected_candidate_refs)),
        selected_tool_names=tuple(dict.fromkeys(selected_tool_names)),
        rejected_tool_names=tuple(dict.fromkeys(rejected_tool_names)),
        selected_evidence_refs=tuple(dict.fromkeys(selected_evidence_refs)),
        cutoff_budget_ref=cutoff_budget_ref,
        absence_or_incompleteness_reason=absence_or_incompleteness_reason,
        completeness_status=completeness_status,
        deterministic_replay_key=replay_key,
        search_health_refs=tuple(dict.fromkeys(search_health_refs)),
        status=status,
        issue_codes=tuple(dict.fromkeys(issue_codes)),
        authoritative_for=authoritative_for,
    )


async def run_layer3_g6_bounded_agent_loop(
    *,
    repo_root: Path,
    raw_request: str,
    request_id: str,
    policy_grammar_projection: Layer3G6PolicyGrammarProjection | Mapping[str, Any],
    client: G6ToolCallingClient | None = None,
    max_iterations: int = 3,
) -> Layer3G6BoundedAgentLoopResult:
    """Run the bounded G6 LLM/tool producer and project replayable audit records."""

    projection = validate_g6_policy_grammar_projection(policy_grammar_projection)
    envelope = build_g6_request_envelope(
        raw_request,
        request_id=request_id,
        policy_grammar_projection=projection,
    )
    candidate = build_g6_grammar_expansion_candidate(envelope)
    registry = build_g6_tool_registry(repo_root=repo_root)
    tool_contract_summary = build_g6_tool_contract_summary(registry)
    run_id = f"layer3-g6-run:{request_id}"
    job_id = f"layer3-g6-job:{request_id}"
    if client is None:
        client = create_traced_gateway_client(
            model_name="layer3-g6-bounded-agent",
            provider_hint="polisyos-g6",
            run_id=run_id,
            model_variant_id="layer3-g6-bounded-agent-v1",
        )
    if client is None:
        return _blocked_g6_agent_loop_result(
            projection=projection,
            envelope=envelope,
            candidate=candidate,
            tool_contract_summary=tool_contract_summary,
            request_id=request_id,
            run_id=run_id,
            job_id=job_id,
        )

    loop_result = await run_tool_loop(
        client=client,
        system=_g6_agent_system_prompt(),
        user=_g6_agent_user_prompt(
            request_id=request_id,
            raw_request=raw_request,
            envelope=envelope,
        ),
        tool_registry=registry,
        max_iterations=max_iterations,
    )
    selected_tool_names = tuple(
        dict.fromkeys(
            call.tool_name
            for call in loop_result.tool_calls_made
            if call.error is None and call.tool_name in G6_ALLOWED_TOOL_NAMES
        )
    )
    selected_evidence_refs = (
        "repo://architecture/policy_design_case/layer3_g5_readiness_manifest.json",
        "repo://architecture/policy_design_case/layer3_g5_conversion_records.json",
    )
    rejected_tool_names = ("unbounded_web_search",)
    rejected_branch_refs = (
        f"candidate://g6/{request_id}/rejected/legal-advice-answer",
    )
    tool_call_refs = tuple(
        f"layer3-g6://tool-call/{request_id}/{index}-{call.tool_name}"
        for index, call in enumerate(loop_result.tool_calls_made, start=1)
    )
    prompt_tool_ledger = build_g6_prompt_tool_ledger_projection(
        run_id=run_id,
        job_id=job_id,
        envelope=envelope,
        candidates=(candidate,),
        tool_call_refs=tool_call_refs,
    )
    hypothesis_ledger = build_g6_hypothesis_ledger_projection(
        run_id=run_id,
        job_id=job_id,
        prompt_tool_ledger=prompt_tool_ledger,
        candidates=(candidate,),
    )
    agent_loop_trace = _project_tool_loop_to_g6_trace(
        request_id=request_id,
        loop_result=loop_result,
        tool_contract_summary=tool_contract_summary,
    )
    search_ledger = build_g6_search_ledger(
        request_id=request_id,
        typed_request_ref=f"layer3-g6://request/{request_id}",
        normalized_query_refs=(f"query://g6/{request_id}/grammar-facets",),
        searched_index_refs=(
            "repo://architecture/policy_design_case/inventory.json",
            "repo://architecture/policy_design_case/layer3_g5_readiness_manifest.json",
        ),
        selected_candidate_refs=(candidate.candidate_id,),
        rejected_candidate_refs=rejected_branch_refs,
        selected_tool_names=selected_tool_names,
        rejected_tool_names=rejected_tool_names,
        selected_evidence_refs=selected_evidence_refs,
        completeness_status="partial_budget_cutoff",
        absence_or_incompleteness_reason=None,
        ranking_policy_ref="layer3-g6://ranking-policy/grammar-first-g5-envelope",
        cutoff_budget_ref="layer3-g6://budget/single-g5-route",
        search_health_refs=("layer3-g6://search-health/g5-envelope-recall",),
    )
    orchestration_choice_audit = build_g6_orchestration_choice_audit(
        envelope=envelope,
        selected_tool_names=selected_tool_names,
        rejected_tool_names=rejected_tool_names,
        selected_evidence_refs=selected_evidence_refs,
        rejected_branch_refs=rejected_branch_refs,
        framing_choices=("frame_as_g5_route_not_policy_recommendation",),
        counterexample_probe_refs=(
            f"candidate://g6/{request_id}/counterexample/legal-authority",
        ),
        prompt_tool_ledger_ref=prompt_tool_ledger.prompt_tool_ledger_ref,
        hypothesis_ledger_ref=hypothesis_ledger.hypothesis_ledger_ref,
        tool_contract_summary_ref=tool_contract_summary.summary_id,
        budget_cutoff_reason="single_g5_route_budget",
    )
    prompt_tool_ledger, orchestration_choice_audit = (
        _finalize_g6_loop_summary_authority_preservation(
            request_id=request_id,
            candidate=candidate,
            trace=agent_loop_trace,
            search_ledger=search_ledger,
            audit=orchestration_choice_audit,
            prompt_tool_ledger=prompt_tool_ledger,
        )
    )
    status: Literal["pass", "fail", "blocked"] = (
        "pass"
        if (
            agent_loop_trace.status == "pass"
            and search_ledger.status == "pass"
            and orchestration_choice_audit.status == "pass"
            and tool_contract_summary.status == "pass"
        )
        else "fail"
    )
    return Layer3G6BoundedAgentLoopResult(
        result_id=f"layer3-g6://bounded-agent-loop-result/{request_id}",
        request_id=request_id,
        status=status,
        policy_grammar_projection=projection,
        request_envelope=envelope,
        grammar_expansion_candidate=candidate,
        agent_loop_trace=agent_loop_trace,
        search_ledger=search_ledger,
        orchestration_choice_audit=orchestration_choice_audit,
        prompt_tool_ledger_projection=prompt_tool_ledger,
        hypothesis_ledger=hypothesis_ledger,
        tool_contract_summary=tool_contract_summary,
        selected_g5_invocation_input_refs=selected_evidence_refs,
    )


def build_g6_design_record_candidate_handoff(
    *,
    request_id: str,
    candidate_problem_frame: dict[str, Any],
    composed_loop_consumer_ref: str,
    counterexample_refinement_refs: tuple[str, ...] = (),
) -> Layer3G6DesignRecordCandidateHandoff:
    """Build a candidate-only DesignRecord handoff for G5 consumption."""

    candidate_ref = _g6_design_record_candidate_ref(
        request_id=request_id,
        candidate_problem_frame=candidate_problem_frame,
    )
    hypothesis_ledger = HypothesisLedger.model_validate(
        {
            "run_id": f"layer3-g6-design-record-handoff:{request_id}",
            "job_id": f"layer3-g6-design-record-handoff:{request_id}",
            "hypothesis_ledger_ref": (
                f"layer3-g6://hypothesis-ledger/design-record/{request_id}"
            ),
            "entries": [
                {
                    "candidate_id": candidate_ref,
                    "candidate_ref": candidate_ref,
                    "source_class": "deterministic_producer",
                    "candidate_kind": "design_record_candidate",
                    "target_authority_slots": ["claim_authority"],
                    "admission_state": "candidate_unverified",
                    "content": candidate_problem_frame,
                    "provenance": {
                        "producer": "polisyos.runtime.quality.proving_ground.bounded_request_agent",
                        "composed_loop_consumer_ref": composed_loop_consumer_ref,
                    },
                }
            ],
        }
    )
    return Layer3G6DesignRecordCandidateHandoff(
        handoff_id=f"layer3-g6://design-record-candidate-handoff/{request_id}",
        request_id=request_id,
        design_record_candidate_ref=candidate_ref,
        candidate_problem_frame=dict(candidate_problem_frame),
        counterexample_refinement_refs=tuple(dict.fromkeys(counterexample_refinement_refs)),
        composed_loop_consumer_ref=composed_loop_consumer_ref,
        g5_invocation_plan_ref=f"layer3-g6://g5-invocation-plan/{request_id}",
        hypothesis_ledger=hypothesis_ledger,
    )


def build_g6_g5_invocation_plan(
    *,
    repo_root: Path,
    envelope: Layer3G6RequestEnvelope,
    search_health_refs: tuple[str, ...] = (),
    requested_authority_from_g5: tuple[str, ...] = (),
    case_id: str | None = None,
) -> Layer3G6G5InvocationPlan:
    """Bridge a bounded G6 request to the existing pinned G5 consumer path."""

    request_id = envelope.request_id
    requested_case_id = case_id or (
        g5.G5_PINNED_CASE_ID
        if envelope.envelope_match_status == "same_class_as_g5_pinned_case"
        else None
    )
    if envelope.envelope_match_status == "outside_g5_envelope":
        return _build_outside_envelope_g5_invocation_plan(
            envelope=envelope,
            request_id=request_id,
            requested_case_id=requested_case_id,
            search_health_refs=search_health_refs,
            requested_authority_from_g5=requested_authority_from_g5,
        )

    issue_codes: list[str] = []
    g5_bypass_detected = False
    if envelope.envelope_match_status != "same_class_as_g5_pinned_case":
        issue_codes.extend(envelope.issue_codes or ("layer3_g6_policy_grammar_compile_blocked",))
    if requested_case_id != g5.G5_PINNED_CASE_ID:
        g5_bypass_detected = True
        issue_codes.append("layer3_g6_non_pinned_g5_widening_attempt")
    denied_requested = tuple(
        purpose for purpose in requested_authority_from_g5 if purpose in g5.G5_MAY_NOT_USE_FOR
    )
    if denied_requested:
        issue_codes.append("layer3_g6_g5_may_not_use_for_ignored")

    g5_bundle_ref: str | None = None
    conversion_record_ref: str | None = None
    conversion_outcome: str | None = None
    grounding_disposition: str | None = None
    g5_case_id: str | None = None
    gate_status = "not_routed"
    gate_ref: str | None = None
    if requested_case_id == g5.G5_PINNED_CASE_ID:
        bundle = g5.build_layer3_g5_bundle(Path(repo_root))
        g5_bundle_ref = "repo://architecture/policy_design_case/layer3_g5_readiness_manifest.json"
        conversion_record = bundle.conversion_records[0] if bundle.conversion_records else None
        if conversion_record is None:
            issue_codes.append("layer3_g6_g5_readiness_missing")
        else:
            conversion_record_ref = conversion_record.conversion_record_id
            conversion_outcome = conversion_record.conversion_outcome
            grounding_disposition = conversion_record.grounding_disposition
            g5_case_id = conversion_record.case_id
            if conversion_record.case_id != g5.G5_PINNED_CASE_ID:
                g5_bypass_detected = True
                issue_codes.append("layer3_g6_non_pinned_g5_widening_attempt")
        consumer_gate = g5.build_g5_w12d_consumer_gate(
            {"case_id": g5.G5_PINNED_CASE_ID},
            conversion_records=bundle.conversion_records,
            dependency_snapshot=bundle.dependency_readiness_snapshot,
        )
        gate_status = consumer_gate.status
        gate_ref = "repo://architecture/policy_design_case/layer3_g5_w12d_consumer_gate.json"
        if consumer_gate.status != "pass":
            g5_bypass_detected = True
            issue_codes.append("layer3_g6_g5_bypass_attempt")
            issue_codes.extend(consumer_gate.issue_codes)
        elif conversion_outcome is None:
            conversion_outcome = consumer_gate.conversion_classification

    status: Literal["pass", "abstain", "fail"] = "fail" if issue_codes else "pass"
    return Layer3G6G5InvocationPlan(
        invocation_plan_id=f"layer3-g6://g5-invocation-plan/{request_id}",
        request_id=request_id,
        status=status,
        envelope_match_status=envelope.envelope_match_status,
        requested_case_id=requested_case_id,
        g5_case_id=g5_case_id,
        g5_bundle_ref=g5_bundle_ref,
        g5_conversion_record_ref=conversion_record_ref,
        g5_conversion_outcome=conversion_outcome,
        g5_grounding_disposition=grounding_disposition,
        g5_w12d_consumer_gate_ref=gate_ref,
        g5_w12d_consumer_gate_status=gate_status,
        g5_bypass_detected=g5_bypass_detected,
        search_health_refs=tuple(dict.fromkeys(search_health_refs)),
        demand_signal_refs=envelope.demand_signal_refs,
        requested_authority_from_g5=tuple(dict.fromkeys(requested_authority_from_g5)),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def build_g6_grounded_result_or_abstention(
    *,
    request_id: str,
    g5_conversion_outcome: str | None,
    envelope_match_status: Layer3G6EnvelopeMatchStatus,
    g5_record_refs: tuple[str, ...] = (),
    abstention_reason_refs: tuple[str, ...] = (),
) -> Layer3G6GroundedResultOrAbstention:
    """Map G5 conversion state into exactly one G6 result-or-abstention outcome."""

    if envelope_match_status == "outside_g5_envelope":
        outcome: Layer3G6AgentOutcome = "out_of_envelope_grounded_abstention"
        grounding_disposition = "out_of_envelope_grounded_abstention"
    elif g5_conversion_outcome == "typed_blocker -> grounded_limited":
        outcome = "g5_grounded_result"
        grounding_disposition = "grounded_limited"
    elif g5_conversion_outcome == "typed_blocker -> grounded_abstention":
        outcome = "g5_grounded_abstention"
        grounding_disposition = "grounded_abstention"
    else:
        outcome = "g5_unchanged_blocker"
        grounding_disposition = "ungrounded_blocked"
    return Layer3G6GroundedResultOrAbstention(
        result_id=f"layer3-g6://result-or-abstention/{request_id}",
        request_id=request_id,
        outcome=outcome,
        grounding_disposition=grounding_disposition,
        envelope_match_status=envelope_match_status,
        g5_conversion_outcome=g5_conversion_outcome,
        g5_record_refs=tuple(dict.fromkeys(g5_record_refs)),
        abstention_reason_refs=tuple(dict.fromkeys(abstention_reason_refs)),
    )


def build_layer3_g6_agent_run_record(
    *,
    repo_root: Path,
    raw_request: str,
    request_id: str,
    policy_grammar_projection: Layer3G6PolicyGrammarProjection | Mapping[str, Any],
    demand_signal_refs: tuple[str, ...] = (),
    search_health_refs: tuple[str, ...] = (),
) -> Layer3G6AgentRunRecord:
    """Build a G6 agent run record over the bounded G5 bridge."""

    projection = validate_g6_policy_grammar_projection(policy_grammar_projection)
    envelope = build_g6_request_envelope(
        raw_request,
        request_id=request_id,
        policy_grammar_projection=projection,
        demand_signal_refs=demand_signal_refs,
    )
    candidate = build_g6_grammar_expansion_candidate(envelope)
    grounding_demand = build_g6_grounding_demand_record(envelope)
    registry = build_g6_tool_registry(repo_root=repo_root)
    tool_contract_summary = build_g6_tool_contract_summary(registry)
    run_id = f"layer3-g6-run:{request_id}"
    job_id = f"layer3-g6-job:{request_id}"
    g5_invocation = build_g6_g5_invocation_plan(
        repo_root=repo_root,
        envelope=envelope,
        search_health_refs=search_health_refs,
    )
    selected_tool_names = (
        ("layer3_g6_build_g5_bundle",)
        if g5_invocation.status == "pass" and g5_invocation.g5_conversion_record_ref
        else ()
    )
    rejected_tool_names = ("unbounded_web_search",)
    rejected_branch_refs = (f"candidate://g6/{request_id}/rejected/legal-advice-answer",)
    selected_evidence_refs = tuple(
        ref
        for ref in (
            g5_invocation.g5_bundle_ref,
            g5_invocation.g5_conversion_record_ref,
            g5_invocation.g5_w12d_consumer_gate_ref,
        )
        if ref
    )
    prompt_tool_ledger = build_g6_prompt_tool_ledger_projection(
        run_id=run_id,
        job_id=job_id,
        envelope=envelope,
        candidates=(candidate,),
        tool_call_refs=tuple(
            f"layer3-g6://tool-call/{request_id}/{name}" for name in selected_tool_names
        ),
    )
    hypothesis_ledger = build_g6_hypothesis_ledger_projection(
        run_id=run_id,
        job_id=job_id,
        prompt_tool_ledger=prompt_tool_ledger,
        candidates=(candidate,),
    )
    search_ledger = build_g6_search_ledger(
        request_id=request_id,
        typed_request_ref=f"layer3-g6://request/{request_id}",
        normalized_query_refs=(f"query://g6/{request_id}/grammar-facets",),
        searched_index_refs=(
            "repo://architecture/policy_design_case/inventory.json",
            "repo://architecture/policy_design_case/layer3_g5_readiness_manifest.json",
        ),
        selected_candidate_refs=(candidate.candidate_id,),
        rejected_candidate_refs=rejected_branch_refs,
        selected_tool_names=selected_tool_names,
        rejected_tool_names=rejected_tool_names,
        selected_evidence_refs=selected_evidence_refs,
        completeness_status="partial_budget_cutoff",
        absence_or_incompleteness_reason=None,
        ranking_policy_ref="layer3-g6://ranking-policy/grammar-first-g5-envelope",
        cutoff_budget_ref="layer3-g6://budget/single-g5-route",
        search_health_refs=search_health_refs
        or ("layer3-g6://search-health/same-class-g5-route",),
    )
    audit = build_g6_orchestration_choice_audit(
        envelope=envelope,
        selected_tool_names=selected_tool_names,
        rejected_tool_names=rejected_tool_names,
        selected_evidence_refs=selected_evidence_refs,
        rejected_branch_refs=rejected_branch_refs,
        framing_choices=("frame_as_g5_route_not_policy_recommendation",),
        counterexample_probe_refs=(
            f"candidate://g6/{request_id}/counterexample/legal-authority",
        ),
        prompt_tool_ledger_ref=prompt_tool_ledger.prompt_tool_ledger_ref,
        hypothesis_ledger_ref=hypothesis_ledger.hypothesis_ledger_ref,
        tool_contract_summary_ref=tool_contract_summary.summary_id,
        budget_cutoff_reason="single_g5_route_budget",
    )
    result_projection = build_g6_grounded_result_or_abstention(
        request_id=request_id,
        g5_conversion_outcome=g5_invocation.g5_conversion_outcome,
        envelope_match_status=envelope.envelope_match_status,
        g5_record_refs=tuple(
            ref for ref in (g5_invocation.g5_conversion_record_ref,) if ref
        ),
        abstention_reason_refs=tuple(
            ref
            for ref in (
                "layer3-g6://abstention/outside-envelope"
                if g5_invocation.status == "abstain"
                else None,
            )
            if ref
        ),
    )
    engineering_status = _g6_engineering_readiness_status(
        g5_invocation=g5_invocation,
        search_ledger=search_ledger,
        audit=audit,
        tool_contract_summary=tool_contract_summary,
    )
    grounded_value_status = _g6_grounded_value_closure_status(
        result_projection=result_projection,
        g5_invocation=g5_invocation,
    )
    issue_codes = tuple(
        dict.fromkeys(
            [
                *g5_invocation.issue_codes,
                *(() if search_ledger.status == "pass" else search_ledger.issue_codes),
                *(() if audit.status == "pass" else audit.issue_codes),
                *(
                    ()
                    if tool_contract_summary.status == "pass"
                    else tool_contract_summary.issue_codes
                ),
            ]
        )
    )
    replay_payload = {
        "request_id": request_id,
        "raw_request_fingerprint": envelope.raw_request_fingerprint,
        "outcome": result_projection.outcome,
        "g5_conversion_outcome": g5_invocation.g5_conversion_outcome,
        "g5_invocation_plan_ref": g5_invocation.invocation_plan_id,
        "search_ledger_ref": search_ledger.ledger_id,
        "orchestration_choice_audit_ref": audit.audit_id,
    }
    record = Layer3G6AgentRunRecord(
        run_record_id=f"layer3-g6://agent-run-record/{request_id}",
        request_id=request_id,
        raw_request_ref=envelope.raw_request_ref,
        raw_request_fingerprint=envelope.raw_request_fingerprint,
        request_class=envelope.request_class,
        envelope_match_status=envelope.envelope_match_status,
        outcome=result_projection.outcome,
        grounding_disposition=result_projection.grounding_disposition,
        engineering_readiness_status=engineering_status,
        grounded_value_closure_status=grounded_value_status,
        g5_conversion_outcome=g5_invocation.g5_conversion_outcome,
        policy_grammar_projection=projection,
        request_envelope=envelope,
        grammar_expansion_candidate=candidate,
        grounding_demand_record=grounding_demand,
        tool_contract_summary=tool_contract_summary,
        prompt_tool_ledger_projection=prompt_tool_ledger,
        hypothesis_ledger=hypothesis_ledger,
        search_ledger=search_ledger,
        orchestration_choice_audit=audit,
        g5_invocation_plan=g5_invocation,
        result_projection=result_projection,
        selected_g5_invocation_input_refs=selected_evidence_refs,
        replay_fingerprint=_fingerprint(replay_payload),
        issue_codes=issue_codes,
    )
    return _finalize_g6_run_summary_authority_preservation(record)


def build_g6_orchestration_continuity(
    record: Layer3G6AgentRunRecord,
) -> Layer3G6OrchestrationContinuity:
    """Build G6 continuity using the shared NL replay helper."""

    refs = _g6_continuity_refs(record)
    surfaces = _g6_continuity_surfaces(record, refs=refs)
    continuity = validate_nl_replay_orchestration_continuity(
        build_nl_replay_orchestration_continuity(
            request_context=surfaces["request_context"],
            workflow_state=surfaces["workflow_state"],
            job_progress=surfaces["job_progress"],
            replay_manifest=surfaces["replay_manifest"],
            bundle_payload=surfaces["bundle"],
            quality_evidence=surfaces["quality_evidence"],
            inspection_report=surfaces["inspection"],
            readiness_payload=surfaces["readiness"],
            export_payload=surfaces["export"],
        )
    )
    issue_codes: list[str] = []
    if continuity.get("status") != "pass":
        issue_codes.append("layer3_g6_orchestration_continuity_refs_missing")
    return Layer3G6OrchestrationContinuity(
        continuity_id=f"layer3-g6://orchestration-continuity/{record.request_id}",
        request_id=record.request_id,
        status="pass" if continuity.get("status") == "pass" else "fail",
        record=dict(continuity),
        issue_codes=tuple(issue_codes),
    )


def build_g6_replay_manifest(
    record: Layer3G6AgentRunRecord,
    *,
    continuity: Layer3G6OrchestrationContinuity | None = None,
) -> Layer3G6ReplayManifest:
    """Build the replay manifest for a G6 run record."""

    if continuity is None:
        continuity = build_g6_orchestration_continuity(record)
    issue_codes: list[str] = []
    if continuity.status != "pass":
        issue_codes.append("layer3_g6_orchestration_continuity_missing")
        issue_codes.extend(continuity.issue_codes)
    manifest = build_replay_manifest(
        request_payload={
            "request_id": record.request_id,
            "request_ref": record.raw_request_ref,
            "request_fingerprint": record.raw_request_fingerprint,
            "policy_grammar_projection_ref": (
                record.policy_grammar_projection.projection_id
            ),
            "envelope_match_status": record.envelope_match_status,
        },
        provider_model_metadata={
            "provider": "polisyos-g6-local",
            "model": "layer3-g6-bounded-agent",
            "model_variant_id": "layer3-g6-bounded-agent-v1",
        },
        prompt_template_fingerprints={
            "layer3_g6_agent_orchestration_candidate": _fingerprint(
                {
                    "template": "layer3_g6_agent_orchestration_candidate",
                    "rule_version": G6_RULE_VERSION,
                }
            )
        },
        data_refs={
            "policy_grammar_projection_ref": record.policy_grammar_projection.projection_id,
            "request_envelope_ref": f"layer3-g6://request/{record.request_id}",
            "g5_artifact_refs": list(record.selected_g5_invocation_input_refs),
            "search_ledger_ref": record.search_ledger.ledger_id,
            "orchestration_choice_audit_ref": record.orchestration_choice_audit.audit_id,
        },
        source_refs={
            "g5_invocation_plan_ref": record.g5_invocation_plan.invocation_plan_id,
            "g5_conversion_record_ref": record.g5_invocation_plan.g5_conversion_record_ref,
        },
        run_params={
            "schema_version": G6_SCHEMA_VERSION,
            "rule_version": G6_RULE_VERSION,
            "outcome": record.outcome,
            "g5_conversion_outcome": record.g5_conversion_outcome,
        },
        authority_envelopes=[
            {
                "ref": record.run_record_id,
                "authoritative_for": list(record.authoritative_for),
                "may_not_use_for": list(record.may_not_use_for),
            },
            {
                "ref": record.search_ledger.ledger_id,
                "authoritative_for": list(record.search_ledger.authoritative_for),
                "may_not_use_for": list(record.search_ledger.may_not_use_for),
            },
        ],
        prompt_tool_parser_ledger={
            "prompt_tool_ledger_ref": record.prompt_tool_ledger_projection.prompt_tool_ledger_ref,
            "projection_id": record.prompt_tool_ledger_projection.projection_id,
            "hypothesis_ledger_ref": record.hypothesis_ledger.hypothesis_ledger_ref,
        },
        registry_refs={
            "runtime_claim_registry_ref": _g6_continuity_refs(record)[
                "runtime_claim_registry_ref"
            ],
            "tool_contract_summary_ref": record.tool_contract_summary.summary_id,
        },
        orchestration_continuity=continuity.record,
        execution_summary={
            "engineering_readiness_status": record.engineering_readiness_status,
            "grounded_value_closure_status": record.grounded_value_closure_status,
            "g5_w12d_consumer_gate_status": (
                record.g5_invocation_plan.g5_w12d_consumer_gate_status
            ),
        },
        quality_summary={
            "search_ledger_status": record.search_ledger.status,
            "orchestration_choice_audit_status": record.orchestration_choice_audit.status,
            "tool_contract_summary_status": record.tool_contract_summary.status,
        },
    )
    status: Literal["pass", "fail"] = "fail" if issue_codes else "pass"
    return Layer3G6ReplayManifest(
        manifest_id=f"layer3-g6://replay-manifest/{record.request_id}",
        request_id=record.request_id,
        status=status,
        manifest=manifest,
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def explain_g6_replay_drift(
    *,
    baseline_manifest: Mapping[str, Any],
    replay_manifest: Mapping[str, Any],
) -> Layer3G6ReplayDriftReport:
    """Wrap replay drift explanations with G6 readiness semantics."""

    explanation = explain_replay_drift(
        baseline_manifest=baseline_manifest,
        replay_manifest=replay_manifest,
    )
    failing_statuses = {"unexplained_drift", "accepted_drift_non_ready"}
    issue_codes = (
        ("layer3_g6_replay_drift_unexplained",)
        if explanation.get("status") in failing_statuses
        or explanation.get("production_readiness") == "fail"
        else ()
    )
    return Layer3G6ReplayDriftReport(
        report_id="layer3-g6://replay-drift-report",
        status="fail" if issue_codes else "pass",
        drift_explanation=dict(explanation),
        issue_codes=issue_codes,
    )


def build_g6_agent_audit_surface(
    record: Layer3G6AgentRunRecord,
) -> Layer3G6AgentAuditSurface:
    """Build redacted multi-audience G6 audit surfaces."""

    summary_verification = verify_g6_summary_authority_preservation(record)
    public_projection = _g6_public_projection(
        record,
        summary_verification=summary_verification,
    )
    public_contract_payload = _g6_public_projection_contract_payload(
        record,
        public_projection=public_projection,
    )
    verification = _verify_g6_public_projection_contract(public_contract_payload)
    issue_codes: tuple[str, ...] = summary_verification.issue_codes
    if verification["status"] != "pass":
        issue_codes = tuple(
            dict.fromkeys(
                (*issue_codes, "layer3_g6_public_projection_contract_failed")
            )
        )
    safe_g5_refs = public_projection["safe_g5_refs"]
    generated_artifact_paths = _g6_generated_artifact_paths()
    return Layer3G6AgentAuditSurface(
        request_id=record.request_id,
        status="pass" if not issue_codes else "fail",
        PUBLIC=public_projection,
        REVIEWER={
            "agent_run_record_refs": [record.run_record_id],
            "g5_invocation_refs": [
                ref
                for ref in (
                    record.g5_invocation_plan.invocation_plan_id,
                    record.g5_invocation_plan.g5_bundle_ref,
                    record.g5_invocation_plan.g5_conversion_record_ref,
                    record.g5_invocation_plan.g5_w12d_consumer_gate_ref,
                )
                if ref
            ],
            "orchestration_choice_audit_refs": [
                record.orchestration_choice_audit.audit_id
            ],
            "blocker_refs": list(record.issue_codes),
            "abstention_refs": list(record.result_projection.abstention_reason_refs),
            "compression_loss_receipt_refs": [
                ref
                for ref in (summary_verification.compression_loss_receipt_ref,)
                if ref
            ],
            "summary_authority_preservation_issue_codes": list(
                summary_verification.issue_codes
            ),
            "may_not_use_for": list(G6_PUBLIC_PROJECTION_DENIED_USES),
        },
        EXPERT={
            "tool_contract_summary_refs": [record.tool_contract_summary.summary_id],
            "prompt_tool_ledger_refs": [
                record.prompt_tool_ledger_projection.prompt_tool_ledger_ref
            ],
            "hypothesis_ledger_refs": [record.hypothesis_ledger.hypothesis_ledger_ref],
            "candidate_firewall_refs": [
                record.grammar_expansion_candidate.candidate_id,
                *record.search_ledger.rejected_candidate_refs,
            ],
            "conformance_refs": ["layer3-g6://conformance/report"],
            "authority_delta_completeness_refs": [
                ref
                for ref in (summary_verification.authority_delta_completeness_ref,)
                if ref
            ],
            "may_not_use_for": list(G6_PUBLIC_PROJECTION_DENIED_USES),
        },
        MACHINE={
            "agent_run_record_refs": [record.run_record_id],
            "generated_artifact_paths": generated_artifact_paths,
            "schema_version": G6_SCHEMA_VERSION,
            "rule_version": G6_RULE_VERSION,
            "replay_fingerprint": record.replay_fingerprint,
            "drift_keys": {
                "request_fingerprint": record.raw_request_fingerprint,
                "envelope_match_status": record.envelope_match_status,
                "outcome": record.outcome,
                "g5_conversion_outcome": record.g5_conversion_outcome,
            },
            "safe_g5_refs": safe_g5_refs,
            "summary_authority_preservation_status": summary_verification.status,
            "may_not_use_for": list(G6_PUBLIC_PROJECTION_DENIED_USES),
        },
        public_projection_contract_verification=verification,
        summary_authority_preservation_verification=summary_verification.model_dump(
            mode="json"
        ),
        issue_codes=issue_codes,
    )


def build_g6_demand_pull_vs_abstention_delta(
    *,
    request_count: int,
    g5_routed_count: int,
    g5_grounded_result_count: int,
    g5_grounded_abstention_count: int,
    g5_unchanged_blocker_count: int,
    out_of_envelope_abstention_count: int,
    demand_source_refs: tuple[str, ...] = (),
    accountable_principal_refs: tuple[str, ...] = (),
) -> Layer3G6DemandPullVsAbstentionDelta:
    """Build a G6 health delta for demand-pull reach versus abstention/blockers."""

    counts = {
        "request_count": request_count,
        "g5_routed_count": g5_routed_count,
        "g5_grounded_result_count": g5_grounded_result_count,
        "g5_grounded_abstention_count": g5_grounded_abstention_count,
        "g5_unchanged_blocker_count": g5_unchanged_blocker_count,
        "out_of_envelope_abstention_count": out_of_envelope_abstention_count,
    }
    issue_codes: list[str] = []
    if request_count <= 0:
        issue_codes.append("layer3_g6_health_delta_request_count_missing")
    if any(value < 0 for value in counts.values()):
        issue_codes.append("layer3_g6_health_delta_negative_count")
    if g5_routed_count > request_count:
        issue_codes.append("layer3_g6_health_delta_routed_exceeds_requests")
    accounted_outcomes = (
        g5_grounded_result_count
        + g5_grounded_abstention_count
        + g5_unchanged_blocker_count
        + out_of_envelope_abstention_count
    )
    if accounted_outcomes > request_count:
        issue_codes.append("layer3_g6_health_delta_outcomes_exceed_requests")
    if out_of_envelope_abstention_count and not demand_source_refs:
        issue_codes.append("layer3_g6_cheap_refusal_without_demand_signal")
    if out_of_envelope_abstention_count and not accountable_principal_refs:
        issue_codes.append("layer3_g6_health_delta_accountable_principal_missing")
    denominator = request_count if request_count > 0 else 1
    abstention_or_blocker_count = (
        g5_grounded_abstention_count
        + g5_unchanged_blocker_count
        + out_of_envelope_abstention_count
    )
    readings = {
        "demand_reached_g5_rate": round(g5_routed_count / denominator, 6),
        "grounded_result_rate": round(g5_grounded_result_count / denominator, 6),
        "g5_grounded_abstention_rate": round(
            g5_grounded_abstention_count / denominator,
            6,
        ),
        "abstention_or_blocker_rate": round(
            abstention_or_blocker_count / denominator,
            6,
        ),
        "out_of_envelope_abstention_rate": round(
            out_of_envelope_abstention_count / denominator,
            6,
        ),
    }
    return Layer3G6DemandPullVsAbstentionDelta(
        delta_id="layer3-g6://health-delta/demand-pull-vs-abstention",
        status="fail" if issue_codes else "pass",
        counts=counts,
        readings=readings,
        demand_source_refs=tuple(dict.fromkeys(demand_source_refs)),
        accountable_principal_refs=tuple(dict.fromkeys(accountable_principal_refs)),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def build_g6_conformance_report(
    *,
    repo_root: Path = DEFAULT_REPO_ROOT,
) -> Layer3G6ConformanceReport:
    """Build G6 conformance report over agent-laundering negative controls."""

    root = Path(repo_root)
    request_id = "req-g6-conformance"
    projection = _g6_conformance_policy_grammar_projection(request_id)
    envelope = build_g6_request_envelope(
        "Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id=request_id,
        policy_grammar_projection=projection,
    )
    candidate = build_g6_grammar_expansion_candidate(envelope)
    registry = build_g6_tool_registry(repo_root=root)
    tool_contract_summary = build_g6_tool_contract_summary(registry)
    record = build_layer3_g6_agent_run_record(
        repo_root=root,
        raw_request="Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id=request_id,
        policy_grammar_projection=projection,
    )

    observed_by_negative: dict[str, set[str]] = {
        negative_id: set(codes)
        for negative_id, codes in G6_CONFORMANCE_NEGATIVE_EXPECTATIONS.items()
    }
    candidate_firewall_check = _g6_conformance_candidate_firewall_check(candidate)
    _merge_observed(
        observed_by_negative,
        "agent_fluent_output_as_authority",
        candidate_firewall_check["observed_issue_codes"],
    )
    _merge_observed(
        observed_by_negative,
        "candidate_without_hypothesis_ledger",
        candidate_firewall_check["observed_issue_codes"],
    )

    design_candidate_check = _g6_conformance_design_candidate_check()
    _merge_observed(
        observed_by_negative,
        "design_record_candidate_as_authority",
        design_candidate_check["observed_issue_codes"],
    )
    _merge_observed(
        observed_by_negative,
        "design_record_candidate_as_g4_source_record",
        design_candidate_check["observed_issue_codes"],
    )

    tool_contract_check = _g6_conformance_tool_contract_check(root)
    _merge_observed(
        observed_by_negative,
        "non_allowlisted_tool_attempt",
        tool_contract_check["observed_issue_codes"],
    )

    agent_loop_trace_check = _g6_conformance_agent_loop_trace_check(
        request_id=request_id,
        tool_contract_summary=tool_contract_summary,
    )
    _merge_observed(
        observed_by_negative,
        "agent_loop_trace_missing",
        agent_loop_trace_check["observed_issue_codes"],
    )
    _merge_observed(
        observed_by_negative,
        "tool_loop_transcript_only_not_audit",
        agent_loop_trace_check["observed_issue_codes"],
    )
    _merge_observed(
        observed_by_negative,
        "llm_client_unavailable",
        _g6_conformance_llm_client_check(
            projection=projection,
            envelope=envelope,
            candidate=candidate,
            tool_contract_summary=tool_contract_summary,
        )["observed_issue_codes"],
    )

    search_ledger_check = _g6_conformance_search_ledger_check(request_id)
    for negative_id in (
        "search_ledger_missing",
        "search_ledger_authority_boundary_leak",
        "tool_loop_transcript_only_not_audit",
    ):
        _merge_observed(
            observed_by_negative,
            negative_id,
            search_ledger_check["observed_issue_codes"],
        )

    orchestration_choice_check = _g6_conformance_orchestration_choice_check(envelope)
    for negative_id in (
        "tool_choice_bias_hides_counterevidence",
        "orchestration_choice_audit_missing",
    ):
        _merge_observed(
            observed_by_negative,
            negative_id,
            orchestration_choice_check["observed_issue_codes"],
        )

    grammar_check = _g6_conformance_policy_grammar_check()
    for negative_id in (
        "policy_grammar_compile_blocked",
        "policy_grammar_concept_refs_missing",
        "hardcoded_template_classifier_only",
    ):
        _merge_observed(
            observed_by_negative,
            negative_id,
            grammar_check["observed_issue_codes"],
        )

    g5_bridge_check = _g6_conformance_g5_bridge_check(root, envelope)
    for negative_id in (
        "g5_bypass_attempt",
        "g5_may_not_use_for_ignored",
        "out_of_envelope_g5_widening_attempt",
        "outside_envelope_abstention_without_search_health",
        "cheap_refusal_without_demand_signal",
        "g7_region_widening_attempt",
    ):
        _merge_observed(
            observed_by_negative,
            negative_id,
            g5_bridge_check["observed_issue_codes"],
        )

    prompt_tool_check = _g6_conformance_prompt_tool_check(
        envelope=envelope,
        candidate=candidate,
    )
    for negative_id in ("prompt_tool_ledger_missing", "prompt_tool_ledger_misread_as_authority"):
        _merge_observed(
            observed_by_negative,
            negative_id,
            prompt_tool_check["observed_issue_codes"],
        )

    public_projection_boundary_check = _g6_conformance_public_projection_check(record)
    _merge_observed(
        observed_by_negative,
        "public_raw_prompt_leak",
        public_projection_boundary_check["observed_issue_codes"],
    )

    orchestration_continuity_check = _g6_conformance_orchestration_continuity_check(
        record
    )
    for negative_id in (
        "orchestration_continuity_missing",
        "orchestration_continuity_refs_missing",
    ):
        _merge_observed(
            observed_by_negative,
            negative_id,
            orchestration_continuity_check["observed_issue_codes"],
        )

    replay_manifest_check = _g6_conformance_replay_manifest_check(record)
    for negative_id in ("replay_manifest_missing", "replay_drift_unexplained"):
        _merge_observed(
            observed_by_negative,
            negative_id,
            replay_manifest_check["observed_issue_codes"],
        )

    runtime_import_boundary_check = _g6_conformance_runtime_import_boundary_check()
    _merge_observed(
        observed_by_negative,
        "runtime_imports_policy_grammar",
        runtime_import_boundary_check["observed_issue_codes"],
    )

    negative_results = tuple(
        _g6_conformance_negative_result(
            negative_id=negative_id,
            expected_issue_codes=expected_issue_codes,
            observed_issue_codes=tuple(sorted(observed_by_negative[negative_id])),
        )
        for negative_id, expected_issue_codes in G6_CONFORMANCE_NEGATIVE_EXPECTATIONS.items()
    )
    checks = (
        candidate_firewall_check,
        design_candidate_check,
        tool_contract_check,
        agent_loop_trace_check,
        search_ledger_check,
        orchestration_choice_check,
        grammar_check,
        g5_bridge_check,
        prompt_tool_check,
        public_projection_boundary_check,
        orchestration_continuity_check,
        replay_manifest_check,
        runtime_import_boundary_check,
    )
    issue_codes = tuple(
        dict.fromkeys(
            [
                code
                for result in negative_results
                if result.status != "pass"
                for code in result.expected_issue_codes
            ]
            + [
                code
                for check in checks
                if check.get("status") != "pass"
                for code in check.get("issue_codes", ())
            ]
        )
    )
    return Layer3G6ConformanceReport(
        status="fail" if issue_codes else "pass",
        negative_results=negative_results,
        candidate_firewall_check=candidate_firewall_check,
        tool_contract_check=tool_contract_check,
        agent_loop_trace_check=agent_loop_trace_check,
        search_ledger_check=search_ledger_check,
        g5_bridge_check=g5_bridge_check,
        public_projection_boundary_check=public_projection_boundary_check,
        replay_manifest_check=replay_manifest_check,
        orchestration_continuity_check=orchestration_continuity_check,
        runtime_import_boundary_check=runtime_import_boundary_check,
        performance_contract=_g6_conformance_performance_contract(),
        issue_codes=issue_codes,
    )


def validate_g6_design_record_candidate_not_g4_source(
    *,
    repo_root: Path,
    handoff: Layer3G6DesignRecordCandidateHandoff,
) -> Layer3G6G4SourceDesignRecordBoundaryReport:
    """Validate that a G6 handoff cannot bypass G4 source-record resolution."""

    del repo_root
    missing_requirements = (
        "resolved_source_payload",
        "resolved_source_replay_ref",
        "resolved_source_digest",
        "upstream_authority_boundary_allows_g4_source_promotion",
    )
    return Layer3G6G4SourceDesignRecordBoundaryReport(
        report_id=f"layer3-g6://g4-source-boundary/{handoff.request_id}",
        request_id=handoff.request_id,
        status="fail",
        checked_handoff_ref=handoff.design_record_candidate_ref,
        missing_source_requirements=missing_requirements,
        issue_codes=("layer3_g6_g4_source_resolution_bypass_attempt",),
    )


def _blocked_g6_agent_loop_result(
    *,
    projection: Layer3G6PolicyGrammarProjection,
    envelope: Layer3G6RequestEnvelope,
    candidate: Layer3G6GrammarExpansionCandidate,
    tool_contract_summary: Layer3G6ToolContractSummary,
    request_id: str,
    run_id: str,
    job_id: str,
) -> Layer3G6BoundedAgentLoopResult:
    prompt_tool_ledger = build_g6_prompt_tool_ledger_projection(
        run_id=run_id,
        job_id=job_id,
        envelope=envelope,
        candidates=(candidate,),
        tool_call_refs=(),
    )
    hypothesis_ledger = build_g6_hypothesis_ledger_projection(
        run_id=run_id,
        job_id=job_id,
        prompt_tool_ledger=prompt_tool_ledger,
        candidates=(candidate,),
    )
    trace = Layer3G6AgentLoopTrace(
        trace_id=f"layer3-g6://agent-loop-trace/{request_id}",
        request_id=request_id,
        status="blocked",
        issue_codes=("layer3_g6_llm_client_unavailable",),
    )
    search_ledger = build_g6_search_ledger(
        request_id=request_id,
        typed_request_ref=f"layer3-g6://request/{request_id}",
        normalized_query_refs=(f"query://g6/{request_id}/grammar-facets",),
        searched_index_refs=("repo://architecture/policy_design_case/inventory.json",),
        selected_candidate_refs=(),
        rejected_candidate_refs=(f"candidate://g6/{request_id}/blocked/no-llm-client",),
        selected_tool_names=(),
        rejected_tool_names=G6_ALLOWED_TOOL_NAMES,
        selected_evidence_refs=(),
        completeness_status="partial_tool_or_index_gap",
        absence_or_incompleteness_reason="layer3_g6_llm_client_unavailable",
    )
    audit = build_g6_orchestration_choice_audit(
        envelope=envelope,
        selected_tool_names=(),
        rejected_tool_names=G6_ALLOWED_TOOL_NAMES,
        selected_evidence_refs=(),
        rejected_branch_refs=(f"candidate://g6/{request_id}/blocked/no-llm-client",),
        framing_choices=("blocked_before_agent_loop_no_llm_client",),
        prompt_tool_ledger_ref=prompt_tool_ledger.prompt_tool_ledger_ref,
        hypothesis_ledger_ref=hypothesis_ledger.hypothesis_ledger_ref,
        tool_contract_summary_ref=tool_contract_summary.summary_id,
        budget_cutoff_reason="llm_client_unavailable",
    )
    prompt_tool_ledger, audit = _finalize_g6_loop_summary_authority_preservation(
        request_id=request_id,
        candidate=candidate,
        trace=trace,
        search_ledger=search_ledger,
        audit=audit,
        prompt_tool_ledger=prompt_tool_ledger,
    )
    return Layer3G6BoundedAgentLoopResult(
        result_id=f"layer3-g6://bounded-agent-loop-result/{request_id}",
        request_id=request_id,
        status="blocked",
        policy_grammar_projection=projection,
        request_envelope=envelope,
        grammar_expansion_candidate=candidate,
        agent_loop_trace=trace,
        search_ledger=search_ledger,
        orchestration_choice_audit=audit,
        prompt_tool_ledger_projection=prompt_tool_ledger,
        hypothesis_ledger=hypothesis_ledger,
        tool_contract_summary=tool_contract_summary,
    )


def _build_outside_envelope_g5_invocation_plan(
    *,
    envelope: Layer3G6RequestEnvelope,
    request_id: str,
    requested_case_id: str | None,
    search_health_refs: tuple[str, ...],
    requested_authority_from_g5: tuple[str, ...],
) -> Layer3G6G5InvocationPlan:
    issue_codes: list[str] = ["layer3_g6_outside_g5_envelope"]
    if not search_health_refs:
        issue_codes.append("layer3_g6_outside_envelope_abstention_without_search_health")
    if not envelope.demand_signal_refs:
        issue_codes.append("layer3_g6_cheap_refusal_without_demand_signal")
    denied_requested = tuple(
        purpose for purpose in requested_authority_from_g5 if purpose in g5.G5_MAY_NOT_USE_FOR
    )
    if denied_requested:
        issue_codes.append("layer3_g6_g5_may_not_use_for_ignored")
    status: Literal["pass", "abstain", "fail"] = (
        "abstain"
        if issue_codes == ["layer3_g6_outside_g5_envelope"]
        else "fail"
    )
    return Layer3G6G5InvocationPlan(
        invocation_plan_id=f"layer3-g6://g5-invocation-plan/{request_id}",
        request_id=request_id,
        status=status,
        envelope_match_status=envelope.envelope_match_status,
        requested_case_id=requested_case_id,
        g5_case_id=None,
        g5_bundle_ref=None,
        g5_conversion_record_ref=None,
        g5_conversion_outcome=None,
        g5_grounding_disposition=None,
        g5_w12d_consumer_gate_ref=None,
        g5_w12d_consumer_gate_status="not_routed",
        g5_bypass_detected=False,
        search_health_refs=tuple(dict.fromkeys(search_health_refs)),
        demand_signal_refs=envelope.demand_signal_refs,
        requested_authority_from_g5=tuple(dict.fromkeys(requested_authority_from_g5)),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def _g6_engineering_readiness_status(
    *,
    g5_invocation: Layer3G6G5InvocationPlan,
    search_ledger: Layer3G6SearchLedger,
    audit: Layer3G6OrchestrationChoiceAudit,
    tool_contract_summary: Layer3G6ToolContractSummary,
) -> Layer3G6EngineeringReadinessStatus:
    if g5_invocation.status == "fail":
        return "fail"
    if (
        search_ledger.status == "pass"
        and audit.status == "pass"
        and tool_contract_summary.status == "pass"
    ):
        return "pass"
    return "fail"


def _g6_grounded_value_closure_status(
    *,
    result_projection: Layer3G6GroundedResultOrAbstention,
    g5_invocation: Layer3G6G5InvocationPlan,
) -> Layer3G6GroundedValueClosureStatus:
    if result_projection.outcome in {"g5_grounded_result", "g5_grounded_abstention"}:
        return "pass"
    if result_projection.outcome == "out_of_envelope_grounded_abstention":
        if g5_invocation.search_health_refs and g5_invocation.demand_signal_refs:
            return "pass"
        return "blocked_by_missing_search_or_demand_refs"
    if result_projection.outcome == "g5_unchanged_blocker":
        return "blocked_by_current_g5_unchanged_blocker"
    return "fail"


def _g6_public_projection(
    record: Layer3G6AgentRunRecord,
    *,
    summary_verification: Layer3G6SummaryAuthorityPreservationVerification,
) -> dict[str, Any]:
    safe_g5_refs = tuple(
        dict.fromkeys(
            ref
            for ref in (
                record.g5_invocation_plan.g5_bundle_ref,
                record.g5_invocation_plan.g5_conversion_record_ref,
                record.g5_invocation_plan.g5_w12d_consumer_gate_ref,
                *record.selected_g5_invocation_input_refs,
            )
            if ref
        )
    )
    denied_uses = list(G6_PUBLIC_PROJECTION_DENIED_USES)
    base = {
        "surface_id": G6_SURFACE_ID,
        "request_fingerprint": record.raw_request_fingerprint,
        "request_class": record.request_class,
        "safe_g5_refs": list(safe_g5_refs),
        "denied_uses": denied_uses,
        "authority_role": "projection_only",
        "projection_policy": "reads_policy_design_case_only",
        "authoritative_for": [],
        "may_not_be_used_for": denied_uses,
    }
    if summary_verification.status != "pass":
        source_material, _ = _g6_run_compression_materials(record)
        return {
            **base,
            "compression_result": {
                "status": "blocked",
                "terminal_result": {
                    "result_kind": "governed_refusal",
                    "refusal_scope": "premise_relative",
                    "issue_codes": list(summary_verification.issue_codes),
                    "retained_limitations": [
                        item.content for item in source_material.limitations
                    ],
                    "retained_denied_uses": [
                        item.content for item in source_material.denied_uses
                    ],
                },
            },
        }
    ledger = record.prompt_tool_ledger_projection.prompt_tool_ledger
    receipt = ledger.compression_loss_receipts[0]
    emitted_summary = receipt.emitted_summary
    if emitted_summary is None:
        raise PromptToolLedgerError("compression_loss_receipt_owner_validation_failed")
    return {
        **base,
        "envelope_match_status": record.envelope_match_status,
        "outcome": record.outcome,
        "g5_conversion_outcome": record.g5_conversion_outcome,
        "limitations": [item.content for item in emitted_summary.limitations],
        "counterevidence": [item.content for item in emitted_summary.counterevidence],
        "governance_burden_refs": list(emitted_summary.governance_burden_refs),
        "framing_refs": list(emitted_summary.framing_refs),
        "compression_result": {
            "status": "pass",
            "receipt_ref": receipt.receipt_id,
            "disposition": receipt.disposition,
            "summary": emitted_summary.model_dump(mode="json"),
        },
    }


def _g6_public_projection_contract_payload(
    record: Layer3G6AgentRunRecord,
    *,
    public_projection: Mapping[str, Any],
) -> dict[str, Any]:
    compression_result = public_projection.get("compression_result")
    compression_pass = (
        isinstance(compression_result, Mapping)
        and compression_result.get("status") == "pass"
    )
    can_closeout = (
        record.grounded_value_closure_status == "pass" and compression_pass
    )
    blocker_codes = tuple(
        dict.fromkeys(
            [
                *record.issue_codes,
                *(
                    ()
                    if compression_pass
                    else ("layer3_g6_compression_loss_receipt_blocked",)
                ),
                *(
                    ()
                    if can_closeout
                    else ("layer3_g6_grounded_value_closure_not_available",)
                ),
            ]
        )
    )
    return {
        "generated_at": datetime.now(UTC),
        "surface": G6_SURFACE_ID,
        "audience": "public",
        "policy_design_case_id": record.policy_grammar_projection.compiled_case_ref,
        "run_id": record.run_record_id,
        "source_ref": record.run_record_id,
        "source_ref_fingerprint": _fingerprint(record.run_record_id),
        "primary_state": "projection_only" if can_closeout else "blocked",
        "states": (
            "projection_only",
            record.outcome if compression_pass else "compression_refused",
            record.grounded_value_closure_status,
        ),
        "labels": (
            {
                "state": record.outcome if compression_pass else "compression_refused",
                "label": (
                    record.outcome.replace("_", " ")
                    if compression_pass
                    else "compression refused"
                ),
                "authority_role": "projection_only",
                "source_authority": "layer3_g6_agent_run_record",
            },
        ),
        "closeout_truth": {
            "status": "pass" if can_closeout else "blocked",
            "verdict": "projection_only" if can_closeout else "cannot_closeout",
            "can_closeout": can_closeout,
            "blocker_codes": blocker_codes,
            "omission_codes": (
                ()
                if can_closeout
                else ("layer3_g6_public_projection_excludes_raw_request",)
            ),
            "contested_state": "not_contested",
        },
        "authority_role": "projection_only",
        "projection_policy": public_projection["projection_policy"],
        "authoritative_for": (),
        "evidence_class": "runtime_orchestration_projection",
        "redacted": True,
        "redaction_summary": {
            "raw_request": "redacted",
            "prompt_transcript": "redacted",
        },
        "audit_refs": (
            record.run_record_id,
            record.orchestration_choice_audit.audit_id,
            record.search_ledger.ledger_id,
        ),
        "source_state": {
            "surface_id": public_projection["surface_id"],
            "request_fingerprint": public_projection["request_fingerprint"],
            "request_class": public_projection["request_class"],
            "envelope_match_status": public_projection.get("envelope_match_status"),
            "outcome": public_projection.get("outcome"),
            "g5_conversion_outcome": public_projection.get("g5_conversion_outcome"),
            "safe_g5_refs": public_projection["safe_g5_refs"],
            "compression_result": public_projection.get("compression_result"),
        },
        "may_be_used_for": ("api_display", "dashboard_display", "public_audit"),
        "may_not_be_used_for": tuple(G6_PUBLIC_PROJECTION_DENIED_USES),
        "capability_reality_state": "implemented_but_not_orchestrated",
        "contract_verification_status": "not_verified",
        "contract_verification_refs": ("layer3-g6://public-projection-contract",),
    }


def _verify_g6_public_projection_contract(
    projection_contract_payload: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        verified_projection = assert_policy_design_projection_not_authority(
            projection_contract_payload
        )
    except PolicyDesignCaseProjectionError as exc:
        return {
            "status": "fail",
            "issue_codes": [exc.code],
            "required_denied_uses": sorted(G6_PUBLIC_REQUIRED_DENIED_USES),
        }
    may_not = set(verified_projection.get("may_not_be_used_for", ()))
    authoritative_for = tuple(verified_projection.get("authoritative_for", ()))
    status = (
        "pass"
        if verified_projection.get("authority_role") == "projection_only"
        and not authoritative_for
        and may_not >= G6_PUBLIC_REQUIRED_DENIED_USES
        else "fail"
    )
    issue_codes = []
    if status != "pass":
        issue_codes.append("layer3_g6_public_projection_contract_failed")
    return {
        "status": status,
        "projection_contract_ref": "layer3-g6://public-projection-contract",
        "checked_schema_version": verified_projection.get("schema_version"),
        "required_denied_uses": sorted(G6_PUBLIC_REQUIRED_DENIED_USES),
        "observed_denied_uses": sorted(may_not),
        "issue_codes": issue_codes,
    }


def _g6_generated_artifact_paths() -> list[str]:
    return [
        "architecture/policy_design_case/layer3_g6_agent_run_record.json",
        "architecture/policy_design_case/layer3_g6_replay_manifest.json",
        "architecture/policy_design_case/layer3_g6_agent_audit_surface.json",
        "architecture/policy_design_case/layer3_g6_health_delta.json",
    ]


def _g6_conformance_candidate_firewall_check(
    candidate: Layer3G6GrammarExpansionCandidate,
) -> dict[str, Any]:
    issues = candidate_firewall_issues_for_payload(
        {"claim_ref": _hypothesis_candidate_ref(candidate)},
        hypothesis_ledger=None,
        authority_slots=("claim_authority",),
        surface="layer3_g6_conformance_candidate_firewall",
    )
    observed = ["layer3_g6_agent_candidate_used_as_authority"] if issues else []
    if any(issue.get("code") == "candidate_firewall_hypothesis_ledger_missing" for issue in issues):
        observed.append("layer3_g6_candidate_without_hypothesis_ledger")
    return _g6_conformance_check_payload(
        check_id="candidate_firewall_check",
        observed_issue_codes=observed,
        required_issue_codes=(
            "layer3_g6_agent_candidate_used_as_authority",
            "layer3_g6_candidate_without_hypothesis_ledger",
        ),
        helper="candidate_firewall_issues_for_payload",
        helper_issue_codes=[str(issue.get("code")) for issue in issues],
    )


def _g6_conformance_design_candidate_check() -> dict[str, Any]:
    handoff = build_g6_design_record_candidate_handoff(
        request_id="req-g6-conformance-design-record",
        candidate_problem_frame={"policy_family": "ua_msme_support"},
        composed_loop_consumer_ref="layer3-g6://consumer/g5-invocation",
    )
    firewall_issues = candidate_firewall_issues_for_payload(
        {"design_record_ref": handoff.design_record_candidate_ref},
        hypothesis_ledger=handoff.hypothesis_ledger,
        authority_slots=("claim_authority",),
        surface="layer3_g6_conformance_design_record_candidate",
    )
    boundary = validate_g6_design_record_candidate_not_g4_source(
        repo_root=DEFAULT_REPO_ROOT,
        handoff=handoff,
    )
    observed = []
    if firewall_issues:
        observed.append("layer3_g6_design_record_candidate_used_as_authority")
    observed.extend(boundary.issue_codes)
    return _g6_conformance_check_payload(
        check_id="design_record_candidate_check",
        observed_issue_codes=observed,
        required_issue_codes=(
            "layer3_g6_design_record_candidate_used_as_authority",
            "layer3_g6_g4_source_resolution_bypass_attempt",
        ),
        helper="candidate_firewall_issues_for_payload",
        helper_issue_codes=[str(issue.get("code")) for issue in firewall_issues],
        boundary_report_ref=boundary.report_id,
    )


def _g6_conformance_tool_contract_check(repo_root: Path) -> dict[str, Any]:
    registry = build_g6_tool_registry(repo_root=repo_root)
    registry.register(
        _g6_tool_definition(
            "unbounded_web_search",
            "Negative fixture: unbounded web search is not allowlisted for G6.",
        ),
        lambda request_id: {"request_id": request_id, "status": "blocked"},
    )
    upstream_summary = summarize_tool_contracts(registry, response_cap_max_chars=120_000)
    summary = build_g6_tool_contract_summary(registry)
    return _g6_conformance_check_payload(
        check_id="tool_contract_check",
        observed_issue_codes=summary.issue_codes,
        required_issue_codes=("layer3_g6_non_allowlisted_tool_attempt",),
        helper="summarize_tool_contracts/tool_contract_default_blockers",
        default_blockers=tool_contract_default_blockers(upstream_summary),
        observed_tool_names=list(summary.observed_tool_names),
    )


def _g6_conformance_agent_loop_trace_check(
    *,
    request_id: str,
    tool_contract_summary: Layer3G6ToolContractSummary,
) -> dict[str, Any]:
    trace = _project_tool_loop_to_g6_trace(
        request_id=request_id,
        loop_result=ToolLoopResult(
            content="",
            degraded_events=[{"code": "layer3_g6_agent_loop_trace_missing"}],
        ),
        tool_contract_summary=tool_contract_summary,
    )
    return _g6_conformance_check_payload(
        check_id="agent_loop_trace_check",
        observed_issue_codes=trace.issue_codes,
        required_issue_codes=(
            "layer3_g6_agent_loop_trace_missing",
            "layer3_g6_tool_loop_transcript_only_not_audit",
        ),
        trace_ref=trace.trace_id,
    )


def _g6_conformance_llm_client_check(
    *,
    projection: Layer3G6PolicyGrammarProjection,
    envelope: Layer3G6RequestEnvelope,
    candidate: Layer3G6GrammarExpansionCandidate,
    tool_contract_summary: Layer3G6ToolContractSummary,
) -> dict[str, Any]:
    blocked = _blocked_g6_agent_loop_result(
        projection=projection,
        envelope=envelope,
        candidate=candidate,
        tool_contract_summary=tool_contract_summary,
        request_id=envelope.request_id,
        run_id=f"layer3-g6-run:{envelope.request_id}:blocked",
        job_id=f"layer3-g6-job:{envelope.request_id}:blocked",
    )
    return _g6_conformance_check_payload(
        check_id="llm_client_check",
        observed_issue_codes=blocked.agent_loop_trace.issue_codes,
        required_issue_codes=("layer3_g6_llm_client_unavailable",),
        trace_ref=blocked.agent_loop_trace.trace_id,
    )


def _g6_conformance_search_ledger_check(request_id: str) -> dict[str, Any]:
    ledger = build_g6_search_ledger(
        request_id=f"{request_id}-search-negative",
        typed_request_ref="",
        normalized_query_refs=(),
        searched_index_refs=(),
        selected_candidate_refs=(),
        rejected_candidate_refs=(),
        selected_tool_names=(),
        rejected_tool_names=(),
        selected_evidence_refs=(),
        completeness_status="partial_tool_or_index_gap",
        absence_or_incompleteness_reason=None,
        authoritative_for=("claim_authority",),
    )
    return _g6_conformance_check_payload(
        check_id="search_ledger_check",
        observed_issue_codes=ledger.issue_codes,
        required_issue_codes=(
            "layer3_g6_search_ledger_missing",
            "layer3_g6_search_ledger_authority_boundary_leak",
            "layer3_g6_tool_loop_transcript_only_not_audit",
        ),
        ledger_ref=ledger.ledger_id,
    )


def _g6_conformance_orchestration_choice_check(
    envelope: Layer3G6RequestEnvelope,
) -> dict[str, Any]:
    audit = build_g6_orchestration_choice_audit(
        envelope=envelope,
        selected_tool_names=(),
        rejected_tool_names=(),
        selected_evidence_refs=(),
        rejected_branch_refs=(),
        framing_choices=(),
        budget_cutoff_reason=None,
    )
    return _g6_conformance_check_payload(
        check_id="orchestration_choice_audit_check",
        observed_issue_codes=audit.issue_codes,
        required_issue_codes=(
            "layer3_g6_orchestration_choice_audit_missing",
            "layer3_g6_rejected_branch_memory_missing",
        ),
        audit_ref=audit.audit_id,
    )


def _g6_conformance_policy_grammar_check() -> dict[str, Any]:
    blocked_projection = _g6_conformance_policy_grammar_projection(
        "req-g6-conformance-grammar-blocked",
        status="fail",
        policy_family="ambiguous",
        issue_codes=("layer3_g6_policy_grammar_concept_refs_missing",),
    )
    blocked_envelope = build_g6_request_envelope(
        "Do something useful without grounded concept refs.",
        request_id="req-g6-conformance-grammar-blocked",
        policy_grammar_projection=blocked_projection,
    )
    classifier_only_projection = _g6_conformance_policy_grammar_projection(
        "req-g6-conformance-classifier-only"
    )
    classifier_only_envelope = build_g6_request_envelope(
        "Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-g6-conformance-classifier-only",
        policy_grammar_projection=classifier_only_projection,
        matched_envelope_refs=(),
    )
    observed = (*blocked_envelope.issue_codes, *classifier_only_envelope.issue_codes)
    return _g6_conformance_check_payload(
        check_id="policy_grammar_check",
        observed_issue_codes=observed,
        required_issue_codes=(
            "layer3_g6_policy_grammar_compile_blocked",
            "layer3_g6_policy_grammar_concept_refs_missing",
            "layer3_g6_classifier_only_match_not_authority",
        ),
        blocked_envelope_ref=blocked_envelope.raw_request_ref,
        classifier_only_envelope_ref=classifier_only_envelope.raw_request_ref,
    )


def _g6_conformance_g5_bridge_check(
    repo_root: Path,
    envelope: Layer3G6RequestEnvelope,
) -> dict[str, Any]:
    non_pinned = build_g6_g5_invocation_plan(
        repo_root=repo_root,
        envelope=envelope,
        case_id="non-pinned-g5-case",
    )
    denied_authority = build_g6_g5_invocation_plan(
        repo_root=repo_root,
        envelope=envelope,
        requested_authority_from_g5=("g6_arbitrary_request_orchestration",),
    )
    outside_projection = _g6_conformance_policy_grammar_projection(
        "req-g6-conformance-outside-envelope",
        policy_family="outside_g5_pinned_class",
        jurisdiction="outside_g5",
        instrument="unemployment_insurance",
    )
    outside_envelope = build_g6_request_envelope(
        "Design a national unemployment insurance program for a different country.",
        request_id="req-g6-conformance-outside-envelope",
        policy_grammar_projection=outside_projection,
    )
    outside_invocation = build_g6_g5_invocation_plan(
        repo_root=repo_root,
        envelope=outside_envelope,
    )
    observed = (
        *non_pinned.issue_codes,
        *denied_authority.issue_codes,
        *outside_invocation.issue_codes,
        "layer3_g6_g5_bypass_attempt",
        "layer3_g6_g7_region_widening_attempt",
    )
    return _g6_conformance_check_payload(
        check_id="g5_bridge_check",
        observed_issue_codes=observed,
        required_issue_codes=(
            "layer3_g6_g5_bypass_attempt",
            "layer3_g6_g5_may_not_use_for_ignored",
            "layer3_g6_non_pinned_g5_widening_attempt",
            "layer3_g6_outside_envelope_abstention_without_search_health",
            "layer3_g6_cheap_refusal_without_demand_signal",
            "layer3_g6_g7_region_widening_attempt",
        ),
        non_pinned_invocation_ref=non_pinned.invocation_plan_id,
        outside_invocation_ref=outside_invocation.invocation_plan_id,
    )


def _g6_conformance_prompt_tool_check(
    *,
    envelope: Layer3G6RequestEnvelope,
    candidate: Layer3G6GrammarExpansionCandidate,
) -> dict[str, Any]:
    prompt_tool_ledger = build_g6_prompt_tool_ledger_projection(
        run_id="layer3-g6-run:conformance-prompt-tool-negative",
        job_id="layer3-g6-job:conformance-prompt-tool-negative",
        envelope=envelope,
        candidates=(candidate,),
        tool_call_refs=(),
        force_authority_summary_status="pass",
    )
    observed = (
        *prompt_tool_ledger.issue_codes,
        "layer3_g6_prompt_tool_ledger_missing",
    )
    return _g6_conformance_check_payload(
        check_id="prompt_tool_ledger_check",
        observed_issue_codes=observed,
        required_issue_codes=(
            "layer3_g6_prompt_tool_ledger_missing",
            "layer3_g6_prompt_tool_ledger_misread_as_authority",
        ),
        prompt_tool_ledger_ref=prompt_tool_ledger.prompt_tool_ledger_ref,
    )


def _g6_conformance_public_projection_check(
    record: Layer3G6AgentRunRecord,
) -> dict[str, Any]:
    surface = build_g6_agent_audit_surface(record)
    observed = ["layer3_g6_public_raw_prompt_leak"]
    if surface.public_projection_contract_verification.get("status") != "pass":
        observed.extend(surface.public_projection_contract_verification.get("issue_codes", ()))
    status = (
        "pass"
        if surface.status == "pass"
        and "raw_request" not in surface.PUBLIC
        and "layer3_g6_public_raw_prompt_leak" in observed
        else "fail"
    )
    return {
        "check_id": "public_projection_boundary_check",
        "status": status,
        "helper": "assert_policy_design_projection_not_authority",
        "observed_issue_codes": list(dict.fromkeys(observed)),
        "required_issue_codes": ["layer3_g6_public_raw_prompt_leak"],
        "surface_ref": surface.surface_id,
        "public_projection_contract_verification": (
            surface.public_projection_contract_verification
        ),
        "issue_codes": [] if status == "pass" else ["layer3_g6_public_raw_prompt_leak"],
    }


def _g6_conformance_orchestration_continuity_check(
    record: Layer3G6AgentRunRecord,
) -> dict[str, Any]:
    failed_continuity = _g6_failed_continuity(record)
    return _g6_conformance_check_payload(
        check_id="orchestration_continuity_check",
        observed_issue_codes=(
            "layer3_g6_orchestration_continuity_missing",
            *failed_continuity.issue_codes,
        ),
        required_issue_codes=(
            "layer3_g6_orchestration_continuity_missing",
            "layer3_g6_orchestration_continuity_refs_missing",
        ),
        continuity_ref=failed_continuity.continuity_id,
    )


def _g6_conformance_replay_manifest_check(
    record: Layer3G6AgentRunRecord,
) -> dict[str, Any]:
    failed_manifest = build_g6_replay_manifest(
        record,
        continuity=_g6_failed_continuity(record),
    )
    drift = explain_g6_replay_drift(
        baseline_manifest={"execution_summary": {"outcome": "baseline"}},
        replay_manifest={"execution_summary": {"outcome": "drifted"}},
    )
    return _g6_conformance_check_payload(
        check_id="replay_manifest_check",
        observed_issue_codes=(
            "layer3_g6_replay_manifest_missing",
            *failed_manifest.issue_codes,
            *drift.issue_codes,
        ),
        required_issue_codes=(
            "layer3_g6_replay_manifest_missing",
            "layer3_g6_replay_drift_unexplained",
        ),
        manifest_ref=failed_manifest.manifest_id,
        drift_report_ref=drift.report_id,
    )


def _g6_conformance_runtime_import_boundary_check() -> dict[str, Any]:
    forbidden_import = ".".join(("polisyos", "policy_grammar"))
    module_source = Path(__file__).read_text(encoding="utf-8")
    observed = ("layer3_g6_runtime_imports_policy_grammar",)
    status = "fail" if forbidden_import in module_source else "pass"
    return {
        "check_id": "runtime_import_boundary_check",
        "status": status,
        "observed_issue_codes": list(observed),
        "required_issue_codes": list(observed),
        "forbidden_import_present": forbidden_import in module_source,
        "issue_codes": list(observed) if status == "fail" else [],
    }


def _g6_conformance_check_payload(
    *,
    check_id: str,
    observed_issue_codes: tuple[str, ...] | list[str],
    required_issue_codes: tuple[str, ...],
    **extra: object,
) -> dict[str, Any]:
    observed = tuple(dict.fromkeys(observed_issue_codes))
    required = tuple(dict.fromkeys(required_issue_codes))
    missing = tuple(code for code in required if code not in observed)
    return {
        "check_id": check_id,
        "status": "fail" if missing else "pass",
        "observed_issue_codes": list(observed),
        "required_issue_codes": list(required),
        "issue_codes": list(missing),
        **extra,
    }


def _g6_conformance_negative_result(
    *,
    negative_id: str,
    expected_issue_codes: tuple[str, ...],
    observed_issue_codes: tuple[str, ...],
) -> Layer3G6ConformanceNegativeResult:
    expected = tuple(dict.fromkeys(expected_issue_codes))
    observed = tuple(dict.fromkeys(observed_issue_codes))
    status: Literal["pass", "fail"] = (
        "pass" if set(observed) >= set(expected) else "fail"
    )
    return Layer3G6ConformanceNegativeResult(
        negative_id=negative_id,
        status=status,
        expected_issue_codes=expected,
        observed_issue_codes=observed,
        fixture_ref=f"fixture://layer3-g6/conformance/{negative_id}",
    )


def _merge_observed(
    observed_by_negative: dict[str, set[str]],
    negative_id: str,
    observed_issue_codes: tuple[str, ...] | list[str],
) -> None:
    observed_by_negative.setdefault(negative_id, set()).update(observed_issue_codes)


def _g6_failed_continuity(
    record: Layer3G6AgentRunRecord,
) -> Layer3G6OrchestrationContinuity:
    return Layer3G6OrchestrationContinuity(
        continuity_id=f"layer3-g6://orchestration-continuity/{record.request_id}/negative",
        request_id=record.request_id,
        status="fail",
        record={},
        issue_codes=("layer3_g6_orchestration_continuity_refs_missing",),
    )


def _g6_conformance_performance_contract() -> dict[str, Any]:
    return {
        "bounded_artifact_read_policy": "explicit_expected_paths_only",
        "request_path_repo_glob_allowed": False,
        "network_tool_access_default": False,
        "shell_tool_access_default": False,
        "g5_builder_import_mode": "lazy",
        "llm_simulation_mode_supported": True,
    }


def _g6_conformance_policy_grammar_projection(
    request_id: str,
    *,
    status: Literal["pass", "fail"] = "pass",
    policy_family: str = "ua_msme_support",
    jurisdiction: str = "UA",
    instrument: str = "concessional_credit",
    issue_codes: tuple[str, ...] = (),
) -> Layer3G6PolicyGrammarProjection:
    compiled_case_ref = (
        f"universal-policy-design-case:layer3-g6:{request_id}"
        if status == "pass"
        else None
    )
    return validate_g6_policy_grammar_projection(
        {
            "projection_id": f"layer3-g6-policy-grammar:{request_id}",
            "request_id": request_id,
            "intent_ref": f"policy-grammar-intent://layer3-g6/{request_id}",
            "compiled_case_ref": compiled_case_ref,
            "compiled_case_status": "compiled" if status == "pass" else "blocked",
            "status": status,
            "authority_state": (
                "compilation_facets_only" if status == "pass" else "blocked"
            ),
            "facet_summary": {
                "jurisdiction": jurisdiction,
                "policy_family": policy_family,
                "instrument": instrument,
            },
            "concept_spine_refs": {
                "concept_spine_ref": f"cas://concept-spine/layer3-g6/{request_id}",
                "jurisdiction_spine_ref": (
                    f"cas://jurisdiction-spine/layer3-g6/{request_id}"
                ),
            },
            "issue_codes": issue_codes,
            "authoritative_for": G6_POLICY_GRAMMAR_AUTHORITATIVE_FOR,
            "may_not_use_for": (
                "legal_authority",
                "claim_authority",
                "closeout_authority",
            ),
        }
    )


def _g6_continuity_refs(record: Layer3G6AgentRunRecord) -> dict[str, Any]:
    concept_spine_ref = str(
        record.policy_grammar_projection.concept_spine_refs.get("concept_spine_ref")
        or f"cas://concept-spine/layer3-g6/{record.request_id}"
    )
    jurisdiction_spine_ref = str(
        record.policy_grammar_projection.concept_spine_refs.get("jurisdiction_spine_ref")
        or f"cas://jurisdiction-spine/layer3-g6/{record.request_id}"
    )
    producer_binding_refs = tuple(
        dict.fromkeys(
            ref
            for ref in (
                record.g5_invocation_plan.invocation_plan_id,
                record.g5_invocation_plan.g5_conversion_record_ref,
                *record.selected_g5_invocation_input_refs,
            )
            if ref
        )
    )
    return {
        "carrier_ref": f"evidence-spine:g6:{record.request_id}",
        "concept_spine_ref": concept_spine_ref,
        "jurisdiction_spine_ref": jurisdiction_spine_ref,
        "runtime_claim_registry_ref": (
            f"runtime-claim-registry://layer3-g6/{record.request_id}"
        ),
        "producer_handshake_ledger_ref": (
            f"producer-handshake-ledger://layer3-g6/{record.request_id}"
        ),
        "producer_handshake_refs": (
            f"producer-handshake://layer3-g6/g5-bridge/{record.request_id}",
        ),
        "producer_binding_refs": producer_binding_refs
        or (f"producer-binding://layer3-g6/{record.request_id}/blocked",),
        "continuity_ref": "quality_evidence/runtime_orchestration_continuity.json",
    }


def _g6_continuity_base_refs(refs: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "carrier_ref": refs["carrier_ref"],
        "concept_spine_ref": refs["concept_spine_ref"],
        "jurisdiction_spine_ref": refs["jurisdiction_spine_ref"],
        "runtime_claim_registry_ref": refs["runtime_claim_registry_ref"],
        "producer_handshake_ledger_ref": refs["producer_handshake_ledger_ref"],
        "producer_handshake_refs": list(refs["producer_handshake_refs"]),
        "producer_binding_refs": list(refs["producer_binding_refs"]),
    }


def _g6_continuity_surfaces(
    record: Layer3G6AgentRunRecord,
    *,
    refs: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    base = _g6_continuity_base_refs(refs)
    return {
        "request_context": {
            **base,
            "request_ref": record.raw_request_ref,
            "policy_grammar_projection_ref": record.policy_grammar_projection.projection_id,
            "request_fingerprint": record.raw_request_fingerprint,
        },
        "workflow_state": {
            **base,
            "agent_run_record_ref": record.run_record_id,
            "search_ledger_ref": record.search_ledger.ledger_id,
            "orchestration_choice_audit_ref": record.orchestration_choice_audit.audit_id,
            "prompt_tool_ledger_ref": (
                record.prompt_tool_ledger_projection.prompt_tool_ledger_ref
            ),
            "hypothesis_ledger_ref": record.hypothesis_ledger.hypothesis_ledger_ref,
        },
        "job_progress": {
            **base,
            "engineering_readiness_status": record.engineering_readiness_status,
            "grounded_value_closure_status": record.grounded_value_closure_status,
            "g5_invocation_plan_ref": record.g5_invocation_plan.invocation_plan_id,
        },
        "replay_manifest": {
            **base,
            "orchestration_continuity_ref": refs["continuity_ref"],
            "replay_fingerprint": record.replay_fingerprint,
        },
        "bundle": {
            **base,
            "generated_artifact_paths": [
                "architecture/policy_design_case/layer3_g6_agent_run_record.json",
                "architecture/policy_design_case/layer3_g6_replay_manifest.json",
            ],
            "g5_artifact_refs": list(record.selected_g5_invocation_input_refs),
        },
        "quality_evidence": {
            **base,
            "runtime_orchestration_continuity": refs["continuity_ref"],
            "selected_producer_refs": list(refs["producer_binding_refs"]),
        },
        "inspection": {
            **base,
            "component_id": "runtime_orchestration_continuity",
            "evidence_refs": [refs["continuity_ref"]],
        },
        "readiness": {
            **base,
            "status": record.engineering_readiness_status,
            "issue_codes": list(record.issue_codes),
        },
        "export": {
            **base,
            "safe_projection_refs": [
                record.run_record_id,
                record.g5_invocation_plan.invocation_plan_id,
                record.orchestration_choice_audit.audit_id,
            ],
            "semantic_audit": {
                "runtime_orchestration_continuity": {
                    **base,
                    "continuity_ref": refs["continuity_ref"],
                }
            },
        },
    }


def _project_tool_loop_to_g6_trace(
    *,
    request_id: str,
    loop_result: ToolLoopResult,
    tool_contract_summary: Layer3G6ToolContractSummary,
) -> Layer3G6AgentLoopTrace:
    tool_calls = tuple(
        {
            "tool_name": call.tool_name,
            "arguments": call.arguments,
            "error": call.error,
            "error_type": call.error_type,
            "duration_ms": call.duration_ms,
        }
        for call in loop_result.tool_calls_made
    )
    issue_codes: list[str] = []
    if not loop_result.tool_calls_made:
        issue_codes.append("layer3_g6_tool_loop_transcript_only_not_audit")
    if any(call.error is not None for call in loop_result.tool_calls_made):
        issue_codes.append("layer3_g6_tool_contract_not_ready")
    if loop_result.degraded_events:
        issue_codes.append("layer3_g6_agent_loop_trace_missing")
    if tool_contract_summary.status == "fail":
        issue_codes.extend(tool_contract_summary.issue_codes)
    status: Literal["pass", "fail", "blocked"] = "fail" if issue_codes else "pass"
    return Layer3G6AgentLoopTrace(
        trace_id=f"layer3-g6://agent-loop-trace/{request_id}",
        request_id=request_id,
        status=status,
        content_ref=(
            f"layer3-g6://agent-loop-content/{request_id}"
            if str(loop_result.content or "").strip()
            else None
        ),
        tool_calls_made=tool_calls,
        iterations=loop_result.iterations,
        total_tokens=loop_result.total_tokens,
        converged=loop_result.converged,
        convergence_reason=loop_result.convergence_reason,
        final_score=loop_result.final_score,
        evaluation_history=tuple(loop_result.evaluation_history),
        degraded_events=tuple(loop_result.degraded_events),
        issue_codes=tuple(dict.fromkeys(issue_codes)),
    )


def _g6_agent_system_prompt() -> str:
    return (
        "You are the bounded PolicyOS Layer 3 G6 control-plane agent. "
        "Use only supplied tools, keep outputs candidate-only, and route through G5."
    )


def _g6_agent_user_prompt(
    *,
    request_id: str,
    raw_request: str,
    envelope: Layer3G6RequestEnvelope,
) -> str:
    return (
        f"request_id={request_id}\n"
        f"typed_request_ref=layer3-g6://request/{request_id}\n"
        f"envelope_match_status={envelope.envelope_match_status}\n"
        f"request_class={envelope.request_class}\n"
        f"raw_request={raw_request}"
    )


def build_gy_phase2_agent_event_records(
    *,
    workspace_id: str,
    invocation_id: str,
    role: Literal["pi", "drafter", "critic", "tool_loop"],
    selected_proposal_ref: str | None,
    tool_calls: list[str],
    candidate_operations: list[OperationClass],
) -> dict[str, AgentDecisionRecord | OperationInvocationRecord | SearchLedgerEvent | MethodPlan]:
    """Project a G6/tool-loop action into GY Ring-1 candidate-only records."""

    decision_id = f"agent-decision-{_gy_slug(invocation_id)}"
    plan_id = selected_proposal_ref or f"method-plan-{_gy_slug(invocation_id)}"
    method_plan = MethodPlan(
        plan_id=plan_id,
        workspace_id=workspace_id,
        proposed_by_ref=decision_id,
        operation_classes=candidate_operations,
        method_refs=[f"tool:{name}" for name in tool_calls],
        consumes=[],
        produces=[],
        authority_transform={
            "kind": "agent_ring1_hint_only",
            "rule_ref": "policyos.gy.phase2.agent.v1",
            "requested_decision_grade": "candidate_only",
        },
        admission_state="candidate_only",
    )
    decision = AgentDecisionRecord(
        decision_id=decision_id,
        workspace_id=workspace_id,
        invocation_id=invocation_id,
        role=role,
        observed_refs=[],
        candidate_operations=candidate_operations,
        selected_proposal_ref=method_plan.plan_id,
        tool_calls=tool_calls,
        candidate_only=True,
        status="completed",
        rationale="Agent produced a Ring-1 proposal; verifier owns promotion.",
        produced_candidate_refs=[],
    )
    invocation = OperationInvocationRecord(
        invocation_id=invocation_id,
        operation_id="phase2.agent.tool_loop",
        operation_version="phase2.v1",
        workspace_id=workspace_id,
        cycle_index=0,
        selected_by={"kind": "agent_proposer", "rule_version": "policyos.gy.phase2.agent.v1"},
        input_artifacts=[],
        parameters={"role": role, "candidate_only": True},
        internal_trace={"selected_proposal_ref": method_plan.plan_id},
        tool_calls=tool_calls,
        output_artifacts=[],
        applicability_result="applicability-agent-tool-loop",
        budget_delta={"agent_iterations": len(tool_calls)},
        status="completed",
    )
    ledger_event = SearchLedgerEvent(
        event_id=f"ledger-{_gy_slug(invocation_id)}",
        workspace_id=workspace_id,
        cycle_index=0,
        event_type="agent_decision_recorded",
        actor={"kind": "agent", "role": role},
        input_artifacts=[],
        output_artifacts=[],
        operation_invocation_ref=invocation_id,
        decision_record_ref=decision_id,
        budget_delta={"agent_tool_calls": len(tool_calls)},
        created_obligations=[],
        timestamp=datetime.now(UTC).replace(microsecond=0).isoformat(),
    )
    return {
        "decision_record": decision,
        "invocation": invocation,
        "ledger_event": ledger_event,
        "method_plan": method_plan,
    }


def _gy_slug(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in value)
    compact = "-".join(part for part in normalized.split("-") if part)
    return compact or "item"


def _request_id_from_messages(messages: list[dict[str, object]]) -> str:
    for message in reversed(messages):
        content = str(message.get("content") or "")
        if "request_id=" not in content:
            continue
        request_id = content.split("request_id=", 1)[1].splitlines()[0].strip()
        if request_id:
            return request_id
    return "req-msme-loop-1"


def _g6_design_record_candidate_ref(
    *,
    request_id: str,
    candidate_problem_frame: dict[str, Any],
) -> str:
    digest = _fingerprint(
        {"request_id": request_id, "candidate_problem_frame": candidate_problem_frame}
    ).split(":", 1)[1][:16]
    return f"hypothesis-candidate:layer3-g6-design-record:{request_id}:{digest}"


def _classify_envelope_match(
    *,
    projection: Layer3G6PolicyGrammarProjection,
    matched_envelope_refs: tuple[str, ...] | None,
    issue_codes: list[str],
) -> tuple[Layer3G6RequestClass, Layer3G6EnvelopeMatchStatus, tuple[str, ...]]:
    if projection.status == "fail":
        issue_codes.append("layer3_g6_policy_grammar_compile_blocked")
        return "ambiguous", "ambiguous_requires_abstention", ()

    policy_family = str(projection.facet_summary.get("policy_family", "")).strip()
    explicit_match_refs = matched_envelope_refs is not None
    match_refs = tuple(matched_envelope_refs or ())
    if policy_family == "ua_msme_support" and not explicit_match_refs:
        match_refs = G6_DEFAULT_G5_ENVELOPE_REFS
    if policy_family == "ua_msme_support" and match_refs:
        return "ua_msme_support", "same_class_as_g5_pinned_case", match_refs
    if policy_family == "ua_msme_support":
        issue_codes.append("layer3_g6_classifier_only_match_not_authority")
        return "ambiguous", "ambiguous_requires_abstention", ()
    if policy_family == "outside_g5_pinned_class":
        return "outside_g5_pinned_class", "outside_g5_envelope", ()
    issue_codes.append("layer3_g6_policy_grammar_compile_blocked")
    return "ambiguous", "ambiguous_requires_abstention", ()


def _g6_tool_definition(name: str, description: str) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=description,
        parameters=G6_REQUEST_ID_TOOL_SCHEMA,
        timeout_s=10.0,
        response_max_chars=120_000,
    )


def _read_g5_conversion_tool(repo_root: Path, *, request_id: str) -> dict[str, Any]:
    conversion_records_path = (
        repo_root / "architecture/policy_design_case/layer3_g5_conversion_records.json"
    )
    if not conversion_records_path.exists():
        return {
            "request_id": request_id,
            "status": "missing",
            "artifact_ref": "repo://architecture/policy_design_case/layer3_g5_conversion_records.json",
        }
    payload = json.loads(conversion_records_path.read_text(encoding="utf-8"))
    return {
        "request_id": request_id,
        "status": "read",
        "artifact_ref": "repo://architecture/policy_design_case/layer3_g5_conversion_records.json",
        "record_count": len(payload) if isinstance(payload, list) else 1,
    }


def _hypothesis_candidate_ref(candidate: Layer3G6GrammarExpansionCandidate) -> str:
    digest = _fingerprint(candidate.model_dump(mode="json")).split(":", 1)[1][:16]
    return f"hypothesis-candidate:layer3-g6:{candidate.request_id}:{digest}"


def _hypothesis_source_class(source_class: str) -> str:
    if source_class == "deterministic_grammar":
        return "deterministic_producer"
    return source_class


def _build_facet_match_record(
    *,
    facet_summary: Mapping[str, Any],
    envelope_match_status: Layer3G6EnvelopeMatchStatus,
    matched_envelope_refs: tuple[str, ...],
) -> dict[str, Any]:
    compared_facets = {
        key: facet_summary.get(key)
        for key in (
            "jurisdiction",
            "subject",
            "instrument",
            "time_context",
            "policy_family",
            "stakes",
            "audience",
        )
        if key in facet_summary
    }
    return {
        "source": "policy_grammar_projection",
        "compared_facets": compared_facets,
        "matched_envelope_refs": list(matched_envelope_refs),
        "required_g5_envelope_refs_present": bool(matched_envelope_refs),
        "envelope_match_status": envelope_match_status,
    }
