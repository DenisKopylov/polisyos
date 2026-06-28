from __future__ import annotations

from pathlib import Path

import pytest

REQUIRED_G6_NEGATIVES = {
    "agent_fluent_output_as_authority",
    "tool_choice_bias_hides_counterevidence",
    "agent_loop_trace_missing",
    "search_ledger_missing",
    "search_ledger_authority_boundary_leak",
    "tool_loop_transcript_only_not_audit",
    "llm_client_unavailable",
    "policy_grammar_compile_blocked",
    "policy_grammar_concept_refs_missing",
    "runtime_imports_policy_grammar",
    "hardcoded_template_classifier_only",
    "design_record_candidate_as_authority",
    "design_record_candidate_as_g4_source_record",
    "g5_bypass_attempt",
    "g5_may_not_use_for_ignored",
    "non_allowlisted_tool_attempt",
    "candidate_without_hypothesis_ledger",
    "public_raw_prompt_leak",
    "outside_envelope_abstention_without_search_health",
    "cheap_refusal_without_demand_signal",
    "out_of_envelope_g5_widening_attempt",
    "prompt_tool_ledger_missing",
    "prompt_tool_ledger_misread_as_authority",
    "orchestration_continuity_missing",
    "orchestration_continuity_refs_missing",
    "replay_manifest_missing",
    "replay_drift_unexplained",
    "orchestration_choice_audit_missing",
    "g7_region_widening_attempt",
}


def test_layer3_g6_constants_define_candidate_only_boundary() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    assert g6.G6_SCHEMA_VERSION == "policyos.policy_design_case.layer3_g6_bounded_agent.v1"
    assert g6.G6_RULE_VERSION == "policyos.layer3.g6.bounded_agent.v1"
    assert "claim_authority" in g6.G6_MAY_NOT_USE_FOR
    assert "policy_recommendation" in g6.G6_MAY_NOT_USE_FOR
    assert "layer3_g6_agent_orchestration_audit" in g6.G6_AUTHORITATIVE_FOR


def _policy_grammar_projection_fixture(
    request_id: str,
    *,
    fixture_id: str = "ua-msme",
    status: str = "pass",
    compiled_case_status: str = "compiled",
    issue_codes: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "projection_id": f"layer3-g6-policy-grammar:{request_id}",
        "request_id": request_id,
        "intent_ref": f"policy-grammar-intent://layer3-g6/{request_id}",
        "compiled_case_ref": (
            f"universal-policy-design-case:layer3-g6:{fixture_id}"
            if status == "pass"
            else None
        ),
        "compiled_case_status": compiled_case_status,
        "status": status,
        "authority_state": "compilation_facets_only" if status == "pass" else "blocked",
        "facet_summary": {
            "jurisdiction": "UA" if fixture_id == "ua-msme" else "outside_g5",
            "policy_family": "ua_msme_support"
            if fixture_id == "ua-msme"
            else "outside_g5_pinned_class",
            "instrument": "concessional_credit"
            if fixture_id == "ua-msme"
            else "unemployment_insurance",
        },
        "concept_spine_refs": {
            "concept_spine_ref": f"cas://concept-spine/layer3-g6/{fixture_id}",
            "jurisdiction_spine_ref": f"cas://jurisdiction-spine/layer3-g6/{fixture_id}",
        },
        "issue_codes": issue_codes,
        "authoritative_for": ("layer3_g6_policy_grammar_routing_facets",),
        "may_not_use_for": ("legal_authority", "claim_authority", "closeout_authority"),
    }


def test_g6_request_envelope_classifies_msme_request_without_authority() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    grammar = g6.validate_g6_policy_grammar_projection(
        _policy_grammar_projection_fixture("req-msme-1")
    )
    envelope = g6.build_g6_request_envelope(
        "Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-msme-1",
        policy_grammar_projection=grammar,
    )
    candidate = g6.build_g6_grammar_expansion_candidate(envelope)

    assert grammar.status == "pass"
    assert grammar.compiled_case_status == "compiled"
    assert grammar.authority_state == "compilation_facets_only"
    assert "legal_authority" in grammar.may_not_use_for
    assert envelope.request_class == "ua_msme_support"
    assert envelope.envelope_match_status == "same_class_as_g5_pinned_case"
    assert envelope.raw_request_fingerprint.startswith("sha256:")
    assert envelope.matched_envelope_refs
    assert candidate.authority_state == "candidate_unverified"
    assert "claim_authority" in candidate.may_not_use_for


def test_g6_request_envelope_marks_outside_envelope_request() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    grammar = g6.validate_g6_policy_grammar_projection(
        _policy_grammar_projection_fixture(
            "req-outside-1",
            fixture_id="outside-envelope",
        )
    )
    envelope = g6.build_g6_request_envelope(
        "Design a national unemployment insurance program for a different country.",
        request_id="req-outside-1",
        policy_grammar_projection=grammar,
    )

    assert envelope.envelope_match_status == "outside_g5_envelope"
    assert envelope.request_class == "outside_g5_pinned_class"


def test_g6_request_envelope_blocks_when_policy_grammar_cannot_compile() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    grammar = g6.validate_g6_policy_grammar_projection(
        _policy_grammar_projection_fixture(
            "req-ambiguous-no-spine",
            fixture_id="ambiguous",
            status="fail",
            compiled_case_status="blocked",
            issue_codes=("layer3_g6_policy_grammar_concept_refs_missing",),
        )
    )
    envelope = g6.build_g6_request_envelope(
        "Do something beneficial someday.",
        request_id="req-ambiguous-no-spine",
        policy_grammar_projection=grammar,
    )

    assert envelope.envelope_match_status == "ambiguous_requires_abstention"
    assert grammar.status == "fail"
    assert "layer3_g6_policy_grammar_concept_refs_missing" in grammar.issue_codes
    assert "layer3_g6_policy_grammar_compile_blocked" in envelope.issue_codes


def test_g6_classifier_only_match_without_g5_refs_is_not_authority() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    envelope = g6.build_g6_request_envelope(
        "Ukraine MSME loans",
        request_id="req-msme-no-refs",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-msme-no-refs"),
        matched_envelope_refs=(),
    )

    assert envelope.envelope_match_status == "ambiguous_requires_abstention"
    assert "layer3_g6_classifier_only_match_not_authority" in envelope.issue_codes


def test_g6_policy_grammar_projection_rejects_authority_scope_leak() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    payload = {
        **_policy_grammar_projection_fixture("req-authority-leak"),
        "authoritative_for": ("claim_authority",),
    }

    with pytest.raises(ValueError, match="authoritative_for"):
        g6.validate_g6_policy_grammar_projection(payload)


def test_g6_runtime_module_does_not_import_policy_grammar() -> None:
    module_text = Path("src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py").read_text(
        encoding="utf-8"
    )

    assert "polisyos.policy_grammar" not in module_text


def test_g6_grounding_demand_names_g5_required_families() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    envelope = g6.build_g6_request_envelope(
        "Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-msme-1",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-msme-1"),
    )
    demand = g6.build_g6_grounding_demand_record(envelope)

    assert demand.status == "route_to_g5"
    assert set(demand.required_grounding_families) >= {
        "g1_source_contracts",
        "g4_promotion_handoff",
        "g5_conversion_record",
        "search_recall_freshness",
    }
    assert "new_agent_authority" not in demand.required_grounding_families


def test_g6_tool_contract_summary_requires_strict_allowlisted_tools() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    registry = g6.build_g6_tool_registry(repo_root=g6.DEFAULT_REPO_ROOT)
    summary = g6.build_g6_tool_contract_summary(registry)

    assert summary.status == "pass"
    assert summary.tool_contract_summary.default_enable_ready is True
    assert "layer3_g6_build_g5_bundle" in summary.allowed_tool_names


def test_g6_tool_contract_summary_blocks_open_schema_tool() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6
    from polisyos.scientist.agent.tools.registry import ToolRegistry
    from polisyos.scientist.agent.tools.schema import ToolDefinition

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="unsafe_tool",
            description="Unsafe open schema",
            parameters={"type": "object", "properties": {}, "additionalProperties": True},
            timeout_s=5.0,
            response_max_chars=4096,
        ),
        lambda: {},
    )

    summary = g6.build_g6_tool_contract_summary(registry)

    assert summary.status == "fail"
    assert "tool_schema_not_ready" in summary.blocker_codes


def test_g6_tool_contract_summary_blocks_missing_timeout() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6
    from polisyos.scientist.agent.tools.registry import ToolRegistry
    from polisyos.scientist.agent.tools.schema import ToolDefinition

    definition = ToolDefinition(
        name="layer3_g6_build_g5_bundle",
        description="Missing timeout fixture",
        parameters=g6.G6_REQUEST_ID_TOOL_SCHEMA,
        timeout_s=1.0,
        response_max_chars=4096,
    )
    definition.timeout_s = 0.0
    registry = ToolRegistry()
    registry.register(definition, lambda request_id: {"request_id": request_id})

    summary = g6.build_g6_tool_contract_summary(registry)

    assert summary.status == "fail"
    assert "runtime_missing_timeout" in summary.blocker_codes


def test_g6_tool_contract_summary_blocks_missing_response_cap() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6
    from polisyos.scientist.agent.tools.registry import ToolRegistry
    from polisyos.scientist.agent.tools.schema import ToolDefinition

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="layer3_g6_build_g5_bundle",
            description="Missing response cap fixture",
            parameters=g6.G6_REQUEST_ID_TOOL_SCHEMA,
            timeout_s=5.0,
            response_max_chars=None,
        ),
        lambda request_id: {"request_id": request_id},
    )

    summary = g6.build_g6_tool_contract_summary(registry)

    assert summary.status == "fail"
    assert "runtime_missing_response_cap" in summary.blocker_codes


def test_g6_tool_contract_summary_blocks_non_allowlisted_tool_name() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6
    from polisyos.scientist.agent.tools.registry import ToolRegistry
    from polisyos.scientist.agent.tools.schema import ToolDefinition

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="unbounded_web_search",
            description="Non-allowlisted search fixture",
            parameters=g6.G6_REQUEST_ID_TOOL_SCHEMA,
            timeout_s=5.0,
            response_max_chars=4096,
        ),
        lambda request_id: {"request_id": request_id},
    )

    summary = g6.build_g6_tool_contract_summary(registry)

    assert summary.status == "fail"
    assert "layer3_g6_non_allowlisted_tool_attempt" in summary.blocker_codes


def test_g6_candidate_ledgers_block_agent_parse_as_claim_authority() -> None:
    from polisyos.runtime.quality.candidate_firewall import (
        candidate_firewall_issues_for_payload,
    )
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    envelope = g6.build_g6_request_envelope(
        "Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-msme-1",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-msme-1"),
    )
    candidate = g6.build_g6_grammar_expansion_candidate(envelope)
    prompt_ledger = g6.build_g6_prompt_tool_ledger_projection(
        run_id="g6-run-1",
        job_id="g6-job-1",
        envelope=envelope,
        candidates=(candidate,),
        tool_call_refs=(),
    )
    hypothesis = g6.build_g6_hypothesis_ledger_projection(
        run_id="g6-run-1",
        job_id="g6-job-1",
        prompt_tool_ledger=prompt_ledger,
        candidates=(candidate,),
    )

    issues = candidate_firewall_issues_for_payload(
        {"selected_claim_refs": [hypothesis.entries[0].candidate_ref]},
        hypothesis_ledger=hypothesis,
        authority_slots=("claim_authority",),
        surface="layer3_g6_agent_run_record",
    )

    assert {issue["code"] for issue in issues} == {
        "candidate_firewall_candidate_unverified"
    }


def test_g6_prompt_tool_ledger_pass_cannot_be_read_as_claim_authority() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    projection = g6.build_g6_prompt_tool_ledger_projection(
        run_id="g6-run-ledger-authority-negative",
        job_id="g6-job-ledger-authority-negative",
        envelope=g6.build_g6_request_envelope(
            "Can Ukraine improve affordable loans for wartime MSMEs?",
            request_id="req-ledger-negative",
            policy_grammar_projection=_policy_grammar_projection_fixture(
                "req-ledger-negative"
            ),
        ),
        candidates=(),
        tool_call_refs=("tool-call://fixture/g5-bundle",),
        force_authority_summary_status="pass",
    )

    assert projection.status == "fail"
    assert "layer3_g6_prompt_tool_ledger_misread_as_authority" in projection.issue_codes


def test_g6_orchestration_choice_audit_records_selected_and_rejected_branches() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    envelope = g6.build_g6_request_envelope(
        "Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-msme-1",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-msme-1"),
    )
    audit = g6.build_g6_orchestration_choice_audit(
        envelope=envelope,
        selected_tool_names=("layer3_g6_build_g5_bundle",),
        rejected_tool_names=("unbounded_web_search",),
        selected_evidence_refs=(
            "repo://architecture/policy_design_case/layer3_g5_conversion_records.json",
        ),
        rejected_branch_refs=("candidate://g6/rejected/legal-advice-answer",),
        framing_choices=("frame_as_g5_route_not_policy_recommendation",),
        budget_cutoff_reason="single_g5_route_budget",
    )

    assert audit.status == "pass"
    assert audit.replayable is True
    assert "unbounded_web_search" in audit.rejected_tool_names
    assert audit.selected_tool_names == ("layer3_g6_build_g5_bundle",)


def test_g6_orchestration_choice_audit_fails_without_rejected_branch_memory() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    envelope = g6.build_g6_request_envelope(
        "MSME loans in Ukraine",
        request_id="req",
        policy_grammar_projection=_policy_grammar_projection_fixture("req"),
    )
    audit = g6.build_g6_orchestration_choice_audit(
        envelope=envelope,
        selected_tool_names=("layer3_g6_build_g5_bundle",),
        rejected_tool_names=(),
        selected_evidence_refs=(
            "repo://architecture/policy_design_case/layer3_g5_conversion_records.json",
        ),
        rejected_branch_refs=(),
        framing_choices=("frame_as_g5_route_not_policy_recommendation",),
        budget_cutoff_reason="single_g5_route_budget",
    )

    assert audit.status == "fail"
    assert "layer3_g6_rejected_branch_memory_missing" in audit.issue_codes


@pytest.mark.asyncio
async def test_g6_agent_loop_uses_llm_tool_loop_and_emits_search_ledger() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    result = await g6.run_layer3_g6_bounded_agent_loop(
        repo_root=Path("."),
        raw_request="Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-msme-loop-1",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-msme-loop-1"),
        client=g6.FakeG6ToolCallingClient(
            tool_sequence=("layer3_g6_classify_request", "layer3_g6_build_g5_bundle"),
        ),
        max_iterations=3,
    )

    assert result.agent_loop_trace.status == "pass"
    assert result.search_ledger.status == "pass"
    assert result.search_ledger.selected_candidate_refs
    assert result.search_ledger.rejected_candidate_refs
    assert result.search_ledger.authoritative_for == ()
    assert result.orchestration_choice_audit.replayable is True


@pytest.mark.asyncio
async def test_g6_agent_loop_fails_closed_when_llm_client_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    monkeypatch.setattr(g6, "create_traced_gateway_client", lambda **_: None)

    result = await g6.run_layer3_g6_bounded_agent_loop(
        repo_root=Path("."),
        raw_request="Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-no-client",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-no-client"),
        client=None,
        max_iterations=3,
    )

    assert result.agent_loop_trace.status == "blocked"
    assert "layer3_g6_llm_client_unavailable" in result.agent_loop_trace.issue_codes


def test_g6_search_ledger_blocks_authority_and_transcript_only_trace() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    ledger = g6.build_g6_search_ledger(
        request_id="req-transcript-only",
        typed_request_ref="layer3-g6://request/req-transcript-only",
        normalized_query_refs=("query://g6/msme",),
        searched_index_refs=("repo://architecture/policy_design_case/inventory.json",),
        selected_candidate_refs=("candidate://g6/msme-route",),
        rejected_candidate_refs=(),
        selected_tool_names=("layer3_g6_build_g5_bundle",),
        rejected_tool_names=(),
        selected_evidence_refs=(
            "repo://architecture/policy_design_case/layer3_g5_conversion_records.json",
        ),
        completeness_status="partial_budget_cutoff",
        absence_or_incompleteness_reason=None,
        authoritative_for=("claim_authority",),
    )

    assert ledger.status == "fail"
    assert "layer3_g6_search_ledger_authority_boundary_leak" in ledger.issue_codes
    assert "layer3_g6_tool_loop_transcript_only_not_audit" in ledger.issue_codes


def test_g6_selected_evidence_refs_must_dereference_before_counting_audit_branch(
    tmp_path: Path,
) -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    ledger = g6.build_g6_search_ledger(
        request_id="g6-missing-evidence",
        typed_request_ref="layer3-g6://request/g6-missing-evidence",
        normalized_query_refs=("query://g6/missing/grammar-facets",),
        searched_index_refs=("repo://architecture/policy_design_case/inventory.json",),
        selected_candidate_refs=("candidate://g6/missing",),
        rejected_candidate_refs=("candidate://g6/rejected",),
        selected_tool_names=("layer3_g6_read_g5_conversion",),
        rejected_tool_names=("unbounded_web_search",),
        selected_evidence_refs=(
            "repo://architecture/policy_design_case/missing_evidence.json#records/0",
        ),
        completeness_status="complete_with_candidates",
        absence_or_incompleteness_reason="fixture",
        repo_root=tmp_path,
    )

    assert ledger.status == "fail"
    assert "layer3_g6_selected_evidence_ref_unresolved" in set(ledger.issue_codes)
    assert "required_ref_missing_artifact" in set(ledger.issue_codes)


def test_g6_design_record_candidate_handoff_stays_candidate_only() -> None:
    from polisyos.runtime.quality.candidate_firewall import (
        candidate_firewall_issues_for_payload,
    )
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    handoff = g6.build_g6_design_record_candidate_handoff(
        request_id="req-msme-1",
        candidate_problem_frame={"policy_family": "ua_msme_support"},
        composed_loop_consumer_ref="layer3-g6://consumer/g5-invocation",
    )

    assert handoff.status == "candidate_only"
    assert "claim_authority" in handoff.may_not_use_for
    issues = candidate_firewall_issues_for_payload(
        {"design_record_ref": handoff.design_record_candidate_ref},
        hypothesis_ledger=handoff.hypothesis_ledger,
        authority_slots=("claim_authority",),
        surface="layer3_g6_composed_loop_candidate_handoff",
    )
    assert {issue["code"] for issue in issues} == {
        "candidate_firewall_candidate_unverified"
    }


def test_g6_design_record_candidate_cannot_be_used_as_g4_source_record() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    handoff = g6.build_g6_design_record_candidate_handoff(
        request_id="req-msme-g4-negative",
        candidate_problem_frame={"policy_family": "ua_msme_support"},
        composed_loop_consumer_ref="layer3-g6://consumer/g5-invocation",
    )
    report = g6.validate_g6_design_record_candidate_not_g4_source(
        repo_root=Path("."),
        handoff=handoff,
    )

    assert report.status == "fail"
    assert "layer3_g6_g4_source_resolution_bypass_attempt" in report.issue_codes


def test_g6_routes_msme_request_to_g5_and_preserves_unchanged_blocker() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    envelope = g6.build_g6_request_envelope(
        "Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-msme-1",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-msme-1"),
    )
    invocation = g6.build_g6_g5_invocation_plan(
        repo_root=Path("."),
        envelope=envelope,
    )

    assert invocation.status == "pass"
    assert invocation.g5_case_id == "ua-msme-affordable-loans-2022"
    assert invocation.g5_conversion_outcome == "unchanged_blocker"
    assert invocation.g5_bypass_detected is False


def test_g6_outside_envelope_request_does_not_call_non_pinned_g5() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    envelope = g6.build_g6_request_envelope(
        "Design national unemployment insurance for a different country.",
        request_id="req-outside-1",
        policy_grammar_projection=_policy_grammar_projection_fixture(
            "req-outside-1",
            fixture_id="outside-envelope",
        ),
        demand_signal_refs=("s12-demand://fixture/outside-envelope",),
    )
    invocation = g6.build_g6_g5_invocation_plan(
        repo_root=Path("."),
        envelope=envelope,
        search_health_refs=(
            "repo://architecture/policy_design_case/layer3_g1_search_recall_freshness.json",
        ),
    )

    assert invocation.status == "abstain"
    assert invocation.g5_case_id is None
    assert "layer3_g6_outside_g5_envelope" in invocation.issue_codes


def test_g6_outside_envelope_abstention_requires_search_health_and_demand_refs() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    envelope = g6.build_g6_request_envelope(
        "Design national unemployment insurance for a different country.",
        request_id="req-outside-no-health",
        policy_grammar_projection=_policy_grammar_projection_fixture(
            "req-outside-no-health",
            fixture_id="outside-envelope",
        ),
    )
    invocation = g6.build_g6_g5_invocation_plan(
        repo_root=Path("."),
        envelope=envelope,
        search_health_refs=(),
    )

    assert invocation.status == "fail"
    assert (
        "layer3_g6_outside_envelope_abstention_without_search_health"
        in invocation.issue_codes
    )
    assert "layer3_g6_cheap_refusal_without_demand_signal" in invocation.issue_codes


def test_g6_bridge_rejects_g5_conversion_as_g6_orchestration_authority() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    envelope = g6.build_g6_request_envelope(
        "Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-g5-authority-negative",
        policy_grammar_projection=_policy_grammar_projection_fixture(
            "req-g5-authority-negative"
        ),
    )
    invocation = g6.build_g6_g5_invocation_plan(
        repo_root=Path("."),
        envelope=envelope,
        requested_authority_from_g5=("g6_arbitrary_request_orchestration",),
    )

    assert invocation.status == "fail"
    assert "layer3_g6_g5_may_not_use_for_ignored" in invocation.issue_codes


def test_g6_bridge_rejects_non_pinned_g5_case_id() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    envelope = g6.build_g6_request_envelope(
        "Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-non-pinned-negative",
        policy_grammar_projection=_policy_grammar_projection_fixture(
            "req-non-pinned-negative"
        ),
    )
    invocation = g6.build_g6_g5_invocation_plan(
        repo_root=Path("."),
        envelope=envelope,
        case_id="non-pinned-case",
    )

    assert invocation.status == "fail"
    assert invocation.g5_bypass_detected is True
    assert "layer3_g6_non_pinned_g5_widening_attempt" in invocation.issue_codes


def test_g6_bridge_fails_closed_when_g5_consumer_gate_not_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    envelope = g6.build_g6_request_envelope(
        "Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-g5-gate-negative",
        policy_grammar_projection=_policy_grammar_projection_fixture(
            "req-g5-gate-negative"
        ),
    )

    def _not_routed_gate(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return g6.g5.Layer3G5W12DConsumerGate(
            status="not_routed",
            case_id=g6.g5.G5_PINNED_CASE_ID,
            issue_codes=("layer3_g5_w12d_consumer_gate_missing",),
        )

    monkeypatch.setattr(g6.g5, "build_g5_w12d_consumer_gate", _not_routed_gate)
    invocation = g6.build_g6_g5_invocation_plan(
        repo_root=Path("."),
        envelope=envelope,
    )

    assert invocation.status == "fail"
    assert "layer3_g6_g5_bypass_attempt" in invocation.issue_codes
    assert "layer3_g5_w12d_consumer_gate_missing" in invocation.issue_codes


def test_g6_agent_run_record_maps_current_g5_unchanged_blocker() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    record = g6.build_layer3_g6_agent_run_record(
        repo_root=Path("."),
        raw_request="Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-msme-1",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-msme-1"),
    )

    assert record.outcome == "g5_unchanged_blocker"
    assert record.g5_conversion_outcome == "unchanged_blocker"
    assert record.engineering_readiness_status == "pass"
    assert record.grounded_value_closure_status == (
        "blocked_by_current_g5_unchanged_blocker"
    )
    assert "claim_authority" in record.may_not_use_for
    assert record.orchestration_choice_audit.status == "pass"


def test_g6_result_projection_accepts_future_g5_grounded_abstention_fixture() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    result = g6.build_g6_grounded_result_or_abstention(
        request_id="req-fixture",
        g5_conversion_outcome="typed_blocker -> grounded_abstention",
        envelope_match_status="same_class_as_g5_pinned_case",
        g5_record_refs=("layer3-g5-conversion-record:fixture",),
        abstention_reason_refs=("layer3-g5://abstention/fixture",),
    )

    assert result.outcome == "g5_grounded_abstention"
    assert result.grounding_disposition == "grounded_abstention"


def test_g6_replay_manifest_and_continuity_bind_request_run_g5_and_projection_refs() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    record = g6.build_layer3_g6_agent_run_record(
        repo_root=Path("."),
        raw_request="Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-replay-1",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-replay-1"),
    )
    continuity = g6.build_g6_orchestration_continuity(record)
    replay_manifest = g6.build_g6_replay_manifest(record, continuity=continuity)

    assert continuity.status == "pass"
    assert continuity.record["schema_version"] == (
        "policyos.runtime.nl_replay_orchestration_continuity.v1"
    )
    assert continuity.record["carrier_ref"]
    assert continuity.record["concept_spine_ref"]
    assert continuity.record["runtime_claim_registry_ref"]
    assert replay_manifest.status == "pass"
    assert replay_manifest.manifest["orchestration_continuity"]["continuity_ref"]
    assert replay_manifest.manifest["prompt_tool_parser_ledger"]


def test_g6_replay_drift_blocks_readiness() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    record = g6.build_layer3_g6_agent_run_record(
        repo_root=Path("."),
        raw_request="Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-replay-drift",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-replay-drift"),
    )
    continuity = g6.build_g6_orchestration_continuity(record)
    baseline = g6.build_g6_replay_manifest(record, continuity=continuity)
    replay = {
        **baseline.manifest,
        "orchestration_continuity": {
            **baseline.manifest["orchestration_continuity"],
            "carrier_ref": "evidence-spine:g6-other-carrier",
        },
    }
    drift = g6.explain_g6_replay_drift(
        baseline_manifest=baseline.manifest,
        replay_manifest=replay,
    )

    assert drift.status == "fail"
    assert "layer3_g6_replay_drift_unexplained" in drift.issue_codes


def test_g6_public_surface_hides_raw_prompt_and_denies_recommendation_authority() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    record = g6.build_layer3_g6_agent_run_record(
        repo_root=Path("."),
        raw_request="Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-msme-1",
        policy_grammar_projection=_policy_grammar_projection_fixture("req-msme-1"),
    )
    surface = g6.build_g6_agent_audit_surface(record)

    assert surface.status == "pass"
    assert "raw_request" not in surface.PUBLIC
    assert surface.public_projection_contract_verification["status"] == "pass"
    assert surface.PUBLIC["authority_role"] == "projection_only"
    assert "policy_recommendation" in surface.PUBLIC["may_not_be_used_for"]
    assert surface.MACHINE["agent_run_record_refs"]


def test_g6_health_delta_counts_demand_pull_and_abstention() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    delta = g6.build_g6_demand_pull_vs_abstention_delta(
        request_count=2,
        g5_routed_count=1,
        g5_grounded_result_count=0,
        g5_grounded_abstention_count=0,
        g5_unchanged_blocker_count=1,
        out_of_envelope_abstention_count=1,
        demand_source_refs=("s12-demand://fixture/outside-envelope",),
        accountable_principal_refs=("principal://runtime-quality-reviewer",),
    )

    assert delta.status == "pass"
    assert delta.readings["demand_reached_g5_rate"] == 0.5
    assert delta.readings["abstention_or_blocker_rate"] == 1.0
    assert delta.demand_source_refs


def test_g6_conformance_report_covers_agent_laundering_negatives() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    report = g6.build_g6_conformance_report()
    negative_ids = {item.negative_id for item in report.negative_results}
    observed_codes = {
        code for item in report.negative_results for code in item.observed_issue_codes
    }

    assert report.status == "pass"
    assert negative_ids >= REQUIRED_G6_NEGATIVES
    assert "layer3_g6_agent_candidate_used_as_authority" in observed_codes
    assert "layer3_g6_g5_bypass_attempt" in observed_codes
    assert "layer3_g6_g5_may_not_use_for_ignored" in observed_codes
    assert "layer3_g6_classifier_only_match_not_authority" in observed_codes
    assert "layer3_g6_policy_grammar_compile_blocked" in observed_codes
    assert "layer3_g6_runtime_imports_policy_grammar" in observed_codes
    assert "layer3_g6_non_allowlisted_tool_attempt" in observed_codes
    assert "layer3_g6_candidate_without_hypothesis_ledger" in observed_codes
    assert "layer3_g6_prompt_tool_ledger_missing" in observed_codes
    assert "layer3_g6_search_ledger_authority_boundary_leak" in observed_codes
    assert "layer3_g6_rejected_branch_memory_missing" in observed_codes
    assert "layer3_g6_g4_source_resolution_bypass_attempt" in observed_codes
    assert "layer3_g6_replay_drift_unexplained" in observed_codes
    assert "layer3_g6_outside_envelope_abstention_without_search_health" in observed_codes
    assert "layer3_g6_g7_region_widening_attempt" in observed_codes
