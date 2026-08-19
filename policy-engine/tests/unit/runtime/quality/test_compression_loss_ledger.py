from __future__ import annotations

# ruff: noqa: S101
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from polisyos.runtime.quality import prompt_tool_ledger as ledger_owner
from polisyos.runtime.quality.evidence_independence import (
    build_evidence_independence_map,
)
from polisyos.runtime.quality.evidence_portfolio import (
    EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION,
)
from polisyos.runtime.quality.prompt_tool_ledger import (
    CompressionClaimItem,
    CompressionEvidenceIndependenceBasis,
    CompressionMaterialItem,
    CompressionMaterialSet,
    OrchestrationAuthorityDelta,
    OrchestrationChoiceContext,
    PromptToolLedgerError,
    build_compression_loss_receipt,
    build_orchestration_authority_deltas,
    load_orchestration_choice_policies,
    validate_compression_loss_receipt,
    validate_orchestration_authority_delta_completeness,
)
from tests._helpers.hds_quality import sha

REPO_ROOT = Path(__file__).resolve().parents[4]


def _portfolio_design() -> dict[str, object]:
    return {
        "schema_version": EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION,
        "portfolio_id": "portfolio-compression-consensus",
        "claim_ids": ["claim-consensus"],
        "predeclared": True,
        "declared_at": "2026-08-19T08:00:00+00:00",
        "declared_before_producer_execution": True,
        "authority_level": "production",
        "strands": [
            {
                "strand_id": "data-method-literature",
                "claim_id": "claim-consensus",
                "authority_level": "production",
                "candidate_data_source_families": ["administrative_registry"],
                "candidate_method_families": ["causal_effect_estimation"],
                "defensible_specification_space": {
                    "primary_estimand": "ATT",
                    "allowed_models": ["event_study"],
                },
                "inclusion_rules": ["Include admitted administrative sources."],
                "exclusion_rules": ["Exclude ungrounded candidate sources."],
                "disconfirming_lines": [
                    {
                        "line_id": "negative-control",
                        "required": True,
                        "evidence_family": "negative_control",
                    }
                ],
                "synthesis_rules": {"strategy": "triangulate_independent_lines"},
                "stopping_rules": {
                    "minimum_effective_independent_evidence_count": 2,
                },
                "cost_proportionality": {"budget_tier": "standard"},
            }
        ],
        "candidate_data_source_families": ["administrative_registry"],
        "candidate_method_families": ["causal_effect_estimation"],
        "inclusion_rules": ["Include admitted administrative sources."],
        "exclusion_rules": ["Exclude ungrounded candidate sources."],
        "disconfirming_lines": ["negative-control"],
        "synthesis_rules": {"strategy": "triangulate_independent_lines"},
        "stopping_rules": {"minimum_effective_independent_evidence_count": 2},
        "cost_proportionality": {"budget_tier": "standard"},
        "cas_ref": sha("compression-portfolio"),
        "runtime_event_ref": sha("compression-portfolio-event"),
    }


def _dependent_evidence_line(index: int) -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.evidence_line.v1",
        "line_id": f"compression-line-{index}",
        "portfolio_id": "portfolio-compression-consensus",
        "portfolio_strand_id": "data-method-literature",
        "claim_id": "claim-consensus",
        "evidence_strand": "data",
        "source_lineage": {
            "source_id": "shared-administrative-registry",
            "source_ref": sha("shared-source"),
            "lineage_refs": [sha("shared-lineage")],
            "corpus_id": "shared-corpus",
            "corpus_ancestry": ["shared-corpus-parent"],
        },
        "corpus_ancestry": ["shared-corpus-parent"],
        "author_pool": ["shared-analysis-cell"],
        "institution_pool": ["shared-policy-lab"],
        "preprocessing_pipeline_id": "shared-preprocessing",
        "method_id": "foundry.did.shared",
        "method_assumptions": ["shared parallel-trends assumption"],
        "identification_strategy_id": "shared-did-identification",
        "shared_failure_modes": ["shared-linkage-bias"],
        "specification_id": f"shared-spec-{index}",
        "producer_identity": {
            "component": "polisyos.foundry.methods.causal",
            "version": "2026.08.19+compression-red",
            "owner": "team-science-quality",
        },
        "execution_context": {
            "run_id": "run-compression-red",
            "job_id": f"job-compression-red-{index}",
            "tenant_id": "tenant-prod",
            "trace_id": f"trace-compression-red-{index}",
        },
        "evidence_ref": sha(f"compression-evidence-{index}"),
        "runtime_event_ref": sha(f"compression-event-{index}"),
    }


def _item(item_id: str, content: str) -> CompressionMaterialItem:
    return CompressionMaterialItem(item_id=item_id, content=content)


def _choice_contexts() -> tuple[OrchestrationChoiceContext, ...]:
    return tuple(
        OrchestrationChoiceContext(
            choice_id=f"choice:{policy.choice_kind}",
            choice_kind=policy.choice_kind,
            candidate_universe=(
                f"candidate:{policy.choice_kind}:selected",
                f"candidate:{policy.choice_kind}:rejected",
            ),
            selected=(f"candidate:{policy.choice_kind}:selected",),
            rejected=(f"candidate:{policy.choice_kind}:rejected",),
            governance_burden_before=("burden:legal-review",),
            governance_burden_after=("burden:legal-review",),
        )
        for policy in load_orchestration_choice_policies()
    )


def _baseline_material(
    *,
    claims: tuple[CompressionClaimItem, ...] = (),
    limitations: tuple[CompressionMaterialItem, ...] | None = None,
    governance_burden_refs: tuple[str, ...] = ("burden:legal-review",),
    framing_refs: tuple[str, ...] = ("frame:bounded-routing-audit",),
) -> CompressionMaterialSet:
    return CompressionMaterialSet(
        claims=claims,
        limitations=(
            limitations
            if limitations is not None
            else (_item("limitation:candidate-only", "Candidate-only result."),)
        ),
        denied_uses=(
            _item("denied-use:claim-authority", "claim_authority"),
            _item("denied-use:policy-recommendation", "policy_recommendation"),
        ),
        counterevidence=(
            _item("counterevidence:rejected-branch", "Rejected legal-advice branch."),
        ),
        governance_burden_refs=governance_burden_refs,
        framing_refs=framing_refs,
    )


def _policy_grammar_projection(request_id: str) -> dict[str, object]:
    return {
        "projection_id": f"layer3-g6-policy-grammar:{request_id}",
        "request_id": request_id,
        "intent_ref": f"policy-grammar-intent://layer3-g6/{request_id}",
        "compiled_case_ref": "universal-policy-design-case:layer3-g6:ua-msme",
        "compiled_case_status": "compiled",
        "status": "pass",
        "authority_state": "compilation_facets_only",
        "facet_summary": {
            "jurisdiction": "UA",
            "policy_family": "ua_msme_support",
            "instrument": "concessional_credit",
        },
        "concept_spine_refs": {
            "concept_spine_ref": f"cas://concept-spine/layer3-g6/{request_id}",
            "jurisdiction_spine_ref": (
                f"cas://jurisdiction-spine/layer3-g6/{request_id}"
            ),
        },
        "issue_codes": (),
        "authoritative_for": ("layer3_g6_policy_grammar_routing_facets",),
        "may_not_use_for": (
            "legal_authority",
            "claim_authority",
            "closeout_authority",
        ),
    }


def _g6_record(
    request_id: str,
    *,
    additional_load_bearing_choices: tuple[OrchestrationChoiceContext, ...] = (),
) -> Any:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    return g6.build_layer3_g6_agent_run_record(
        repo_root=REPO_ROOT,
        raw_request="Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id=request_id,
        policy_grammar_projection=_policy_grammar_projection(request_id),
        additional_load_bearing_choices=additional_load_bearing_choices,
    )


def test_compression_dropping_retained_limitation_fails_closed() -> None:
    source = _baseline_material(
        limitations=(
            _item("limitation:candidate-only", "Candidate-only result."),
            _item("limitation:scope", "Applies only to the pinned G5 envelope."),
        )
    )
    candidate_summary = _baseline_material()

    receipt = build_compression_loss_receipt(
        receipt_id="compression-loss:retained-limitation-red",
        source_ref="layer3-g6://run/retained-limitation-red",
        summary_ref="layer3-g6://summary/retained-limitation-red",
        source_material=source,
        candidate_summary=candidate_summary,
    )

    assert receipt.status == "blocked"
    assert "compression_retained_limitation_dropped" in receipt.issue_codes
    assert receipt.emitted_summary is None
    assert receipt.terminal_result is not None
    assert receipt.terminal_result.result_kind == "governed_refusal"
    assert "Candidate-only result." in receipt.terminal_result.retained_limitations
    assert "claim_authority" in receipt.terminal_result.retained_denied_uses


def test_low_effective_independence_cannot_be_presented_as_broad_consensus() -> None:
    independence_map = build_evidence_independence_map(
        [_dependent_evidence_line(1), _dependent_evidence_line(2)],
        portfolio_designs=[_portfolio_design()],
        map_id="independence-map:compression-consensus-red",
        producer_execution_started_at="2026-08-19T09:00:00+00:00",
    )
    source_claim = CompressionClaimItem(
        item_id="claim:consensus",
        content="The selected evidence supports the bounded routing result.",
        claim_kind="substantive",
        presentation_scope="bounded",
        evidence_independence_ref=independence_map["map_id"],
    )
    summary_claim = CompressionClaimItem.model_validate(
        {
            **source_claim.model_dump(exclude={"item_fingerprint"}),
            "presentation_scope": "broad_consensus",
        }
    )

    receipt = build_compression_loss_receipt(
        receipt_id="compression-loss:consensus-red",
        source_ref="layer3-g6://run/consensus-red",
        summary_ref="layer3-g6://summary/consensus-red",
        source_material=_baseline_material(claims=(source_claim,)),
        candidate_summary=_baseline_material(claims=(summary_claim,)),
        evidence_independence_bases={
            independence_map["map_id"]: CompressionEvidenceIndependenceBasis(
                independence_map=independence_map,
                evidence_lines=(
                    _dependent_evidence_line(1),
                    _dependent_evidence_line(2),
                ),
                portfolio_designs=(_portfolio_design(),),
                producer_execution_started_at="2026-08-19T09:00:00+00:00",
            )
        },
    )

    assert receipt.status == "blocked"
    assert "compression_broad_consensus_not_supported" in receipt.issue_codes
    assert receipt.emitted_summary is None


def test_framing_narrowing_governance_burden_without_delta_fails_closed() -> None:
    source = _baseline_material(
        governance_burden_refs=(
            "burden:public-consultation",
            "burden:legal-review",
        ),
        framing_refs=("frame:public-policy-choice",),
    )
    candidate_summary = _baseline_material(
        governance_burden_refs=("burden:legal-review",),
        framing_refs=("frame:technical-routing-choice",),
    )

    receipt = build_compression_loss_receipt(
        receipt_id="compression-loss:framing-red",
        source_ref="layer3-g6://run/framing-red",
        summary_ref="layer3-g6://summary/framing-red",
        source_material=source,
        candidate_summary=candidate_summary,
    )

    assert receipt.status == "blocked"
    assert (
        "compression_governance_burden_narrowed_without_delta"
        in receipt.issue_codes
    )
    assert receipt.emitted_summary is None


@pytest.mark.parametrize(
    ("claim_kind", "expected_issue"),
    [
        ("negative_terminal", "compression_hidden_negative_terminal"),
        ("constitutive_step", "compression_missing_constitutive_step"),
    ],
)
def test_full_record_link_does_not_repair_categorical_omission(
    claim_kind: str,
    expected_issue: str,
) -> None:
    protected_claim = CompressionClaimItem(
        item_id=f"claim:{claim_kind}",
        content=f"Protected {claim_kind} result.",
        claim_kind=claim_kind,
    )
    full_record_link = _item(
        "limitation:full-record-link",
        "Full record: layer3-g6://run/categorical-omission",
    )
    source = _baseline_material(
        claims=(protected_claim,),
        limitations=(
            _item("limitation:candidate-only", "Candidate-only result."),
            full_record_link,
        ),
    )
    candidate = _baseline_material(
        limitations=(
            _item("limitation:candidate-only", "Candidate-only result."),
            full_record_link,
        )
    )

    receipt = build_compression_loss_receipt(
        receipt_id=f"compression-loss:{claim_kind}-omission",
        source_ref="layer3-g6://run/categorical-omission",
        summary_ref="layer3-g6://summary/categorical-omission",
        source_material=source,
        candidate_summary=candidate,
    )

    assert receipt.status == "blocked"
    assert expected_issue in receipt.issue_codes
    assert receipt.emitted_summary is None


def test_bare_delta_blocks_summary_even_when_other_material_is_retained() -> None:
    candidate = _baseline_material(
        claims=(
            CompressionClaimItem(
                item_id="claim:bare-delta",
                content="Approval changed from blocked to pass.",
                claim_kind="delta",
            ),
        )
    )

    receipt = build_compression_loss_receipt(
        receipt_id="compression-loss:bare-delta",
        source_ref="layer3-g6://run/bare-delta",
        summary_ref="layer3-g6://summary/bare-delta",
        source_material=_baseline_material(),
        candidate_summary=candidate,
    )

    assert receipt.status == "blocked"
    assert "compression_bare_delta" in receipt.issue_codes


def test_procedural_binding_survives_conservative_claim_reduction() -> None:
    procedural = CompressionClaimItem(
        item_id="claim:procedure",
        content="Owner review remains binding before publication.",
        claim_kind="procedural_binding",
    )
    ordinary = CompressionClaimItem(
        item_id="claim:ordinary",
        content="One non-constitutive explanatory claim.",
    )
    source = _baseline_material(claims=(procedural, ordinary))
    candidate = _baseline_material(claims=(procedural,))

    receipt = build_compression_loss_receipt(
        receipt_id="compression-loss:procedural-binding",
        source_ref="layer3-g6://run/procedural-binding",
        summary_ref="layer3-g6://summary/procedural-binding",
        source_material=source,
        candidate_summary=candidate,
    )

    assert receipt.status == "pass"
    assert receipt.disposition == "lossy_but_safe"
    assert receipt.summary_reconstruction == "proved_conservative"
    assert receipt.emitted_summary is not None
    assert receipt.emitted_summary.claims == (procedural,)


def test_authority_delta_completeness_walks_the_full_owner_population() -> None:
    contexts = _choice_contexts()
    policies = load_orchestration_choice_policies()

    derivation = build_orchestration_authority_deltas(contexts)

    assert derivation.completeness.status == "pass"
    assert derivation.completeness.owner_policy_count == len(policies)
    assert derivation.completeness.observed_choice_count == len(contexts)
    assert derivation.completeness.emitted_delta_count == len(derivation.deltas)
    assert set(derivation.completeness.owner_choice_kinds) == {
        policy.choice_kind for policy in policies
    }
    assert set(derivation.completeness.observed_choice_kinds) == {
        context.choice_kind for context in contexts
    }
    assert all(not delta.authoritative_for for delta in derivation.deltas)


def test_fake_or_missing_choice_kind_fails_owner_validation() -> None:
    contexts = _choice_contexts()
    fake = OrchestrationChoiceContext(
        choice_id="choice:fake-unowned",
        choice_kind="fake-unowned",
        candidate_universe=("candidate:fake:selected", "candidate:fake:rejected"),
        selected=("candidate:fake:selected",),
        rejected=("candidate:fake:rejected",),
    )

    with_fake = build_orchestration_authority_deltas((*contexts, fake))
    with_missing = build_orchestration_authority_deltas(contexts[:-1])

    assert with_fake.completeness.status == "fail"
    assert "orchestration_choice_kind_unowned" in with_fake.completeness.issue_codes
    assert with_missing.completeness.status == "fail"
    assert (
        "orchestration_choice_owner_population_incomplete"
        in with_missing.completeness.issue_codes
    )


def test_choice_kind_catalog_grows_by_data_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_catalog = ledger_owner._ORCHESTRATION_CHOICE_POLICY_PATH
    target_catalog = (
        tmp_path
        / "architecture/production_quality/orchestration_choice_policies.toml"
    )
    target_catalog.parent.mkdir(parents=True)
    target_catalog.write_text(
        source_catalog.read_text(encoding="utf-8")
        + """

[[choice_policy]]
choice_kind = "data-only-novel-choice"
decision_policy_ref = "policyos://orchestration-choice-policy/data-only-novel-choice/v1"
authority_effect = "narrows a novel candidate universe without granting authority"
governance_burden_change_allowed = false
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        ledger_owner,
        "_ORCHESTRATION_CHOICE_POLICY_PATH",
        target_catalog,
    )

    novel_choice = OrchestrationChoiceContext(
        choice_id="layer3-g6:req-data-only-growth:data-only-novel-choice",
        choice_kind="data-only-novel-choice",
        candidate_universe=(
            "data-only-novel-choice:candidate:selected",
            "data-only-novel-choice:candidate:rejected",
        ),
        selected=("data-only-novel-choice:candidate:selected",),
        rejected=("data-only-novel-choice:candidate:rejected",),
        source_refs=("runtime-event://g6/data-only-novel-choice",),
    )
    record = _g6_record(
        "req-data-only-growth",
        additional_load_bearing_choices=(novel_choice,),
    )
    policies = load_orchestration_choice_policies()
    ledger = record.prompt_tool_ledger_projection.prompt_tool_ledger
    completeness = ledger.authority_delta_completeness_receipts[0]

    assert completeness.status == "pass"
    assert completeness.owner_policy_count == len(policies)
    assert completeness.observed_choice_count == len(policies)
    assert {delta.choice_kind for delta in ledger.orchestration_authority_deltas} == {
        policy.choice_kind for policy in policies
    }


def test_candidate_partition_is_validated_before_delta_emission() -> None:
    contexts = _choice_contexts()
    first = contexts[0]
    overlapping = first.model_copy(
        update={"rejected": (*first.rejected, first.selected[0])}
    )

    derivation = build_orchestration_authority_deltas((overlapping, *contexts[1:]))

    assert derivation.completeness.status == "fail"
    assert (
        "orchestration_choice_candidate_partition_invalid"
        in derivation.completeness.issue_codes
    )


def test_completeness_contract_rejects_owner_validation_bypass() -> None:
    contexts = _choice_contexts()
    valid = build_orchestration_authority_deltas(contexts)
    forged = valid.deltas[0].model_copy(
        update={
            "decision_policy_ref": (
                "policyos://orchestration-choice-policy/attacker-supplied/v1"
            )
        }
    )

    validation = validate_orchestration_authority_delta_completeness(
        contexts=contexts,
        deltas=(forged, *valid.deltas[1:]),
    )

    assert valid.completeness.status == "pass"
    assert validation.status == "fail"
    assert (
        "orchestration_authority_delta_owner_validation_failed"
        in validation.issue_codes
    )
    assert isinstance(forged, OrchestrationAuthorityDelta)


def test_compression_rejects_detached_completeness_receipt() -> None:
    contexts = _choice_contexts()
    derivation = build_orchestration_authority_deltas(contexts)
    detached = derivation.completeness.model_copy(
        update={"emitted_delta_count": 0}
    )

    receipt = build_compression_loss_receipt(
        receipt_id="compression-loss:detached-completeness",
        source_ref="layer3-g6://run/detached-completeness",
        summary_ref="layer3-g6://summary/detached-completeness",
        source_material=_baseline_material(),
        candidate_summary=_baseline_material(),
        authority_deltas=derivation.deltas,
        authority_delta_completeness=detached,
        orchestration_choice_contexts=contexts,
    )

    assert receipt.status == "blocked"
    assert "compression_authority_delta_completeness_failed" in receipt.issue_codes


def test_compression_rejects_forged_observed_choice_population() -> None:
    contexts = _choice_contexts()
    derivation = build_orchestration_authority_deltas(contexts)
    forged = derivation.completeness.model_copy(
        update={
            "observed_choice_count": len(contexts) + 1,
            "observed_choice_kinds": (
                *derivation.completeness.observed_choice_kinds,
                "forged-observed-choice",
            ),
            "observed_choice_population_fingerprint": "sha256:" + "0" * 64,
        }
    )

    receipt = build_compression_loss_receipt(
        receipt_id="compression-loss:forged-observed-population",
        source_ref="layer3-g6://run/forged-observed-population",
        summary_ref="layer3-g6://summary/forged-observed-population",
        source_material=_baseline_material(),
        candidate_summary=_baseline_material(),
        authority_deltas=derivation.deltas,
        authority_delta_completeness=forged,
        orchestration_choice_contexts=contexts,
    )

    assert receipt.status == "blocked"
    assert "compression_authority_delta_completeness_failed" in receipt.issue_codes


@pytest.mark.parametrize(
    "category",
    ["claims", "limitations", "denied_uses", "counterevidence"],
)
def test_typed_material_copy_cannot_reuse_stale_content_fingerprint(
    category: str,
) -> None:
    negative_terminal = CompressionClaimItem(
        item_id="claim:negative-terminal",
        content="The governed result is an abstention.",
        claim_kind="negative_terminal",
    )
    source = _baseline_material(claims=(negative_terminal,))
    valid = build_compression_loss_receipt(
        receipt_id=f"compression-loss:typed-copy:{category}",
        source_ref=f"layer3-g6://run/typed-copy/{category}",
        summary_ref=f"layer3-g6://summary/typed-copy/{category}",
        source_material=source,
        candidate_summary=source,
    )
    items = getattr(source, category)
    tampered_item = items[0].model_copy(
        update={"content": f"{items[0].content} attacker-authored"}
    )
    tampered_source = source.model_copy(
        update={category: (tampered_item, *items[1:])}
    )

    with pytest.raises(PromptToolLedgerError):
        build_compression_loss_receipt(
            receipt_id=f"compression-loss:typed-copy-build:{category}",
            source_ref=f"layer3-g6://run/typed-copy-build/{category}",
            summary_ref=f"layer3-g6://summary/typed-copy-build/{category}",
            source_material=tampered_source,
            candidate_summary=source,
        )
    forged_receipt = valid.model_copy(update={"source_material": tampered_source})
    with pytest.raises(PromptToolLedgerError):
        validate_compression_loss_receipt(forged_receipt)


def test_governed_refusal_preserves_all_public_safe_protected_material() -> None:
    negative_terminal = CompressionClaimItem(
        item_id="claim:negative-terminal",
        content="The governed result is an abstention.",
        claim_kind="negative_terminal",
    )
    source = _baseline_material(claims=(negative_terminal,))
    candidate = _baseline_material()

    receipt = build_compression_loss_receipt(
        receipt_id="compression-loss:protected-terminal-material",
        source_ref="layer3-g6://run/protected-terminal-material",
        summary_ref="layer3-g6://summary/protected-terminal-material",
        source_material=source,
        candidate_summary=candidate,
    )

    assert receipt.status == "blocked"
    assert receipt.terminal_result is not None
    protected = receipt.terminal_result.protected_material
    assert protected.claims == (negative_terminal,)
    assert protected.limitations == source.limitations
    assert protected.denied_uses == source.denied_uses
    assert protected.counterevidence == source.counterevidence


def test_g6_run_record_produces_and_bridges_compression_receipt() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    record = _g6_record("req-compression-ledger-green")
    ledger = record.prompt_tool_ledger_projection.prompt_tool_ledger

    assert len(ledger.compression_loss_receipts) == 1
    assert ledger.compression_loss_receipts[0].status == "pass"
    assert ledger.compression_loss_receipts[0].authoritative_for == ()
    assert ledger.orchestration_authority_deltas
    assert all(not delta.authoritative_for for delta in ledger.orchestration_authority_deltas)
    assert ledger.authority_delta_completeness_receipts[0].status == "pass"
    assert record.orchestration_choice_audit.authority_delta_completeness.status == "pass"
    assert (
        record.orchestration_choice_audit.compression_loss_receipt_ref
        == ledger.compression_loss_receipts[0].receipt_id
    )
    assert g6.verify_g6_summary_authority_preservation(record).status == "pass"


def test_g6_public_export_emits_refusal_not_clean_summary_for_tampered_receipt() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    record = _g6_record("req-compression-public-refusal")
    projection = record.prompt_tool_ledger_projection
    ledger = projection.prompt_tool_ledger
    receipt = ledger.compression_loss_receipts[0]
    tampered = receipt.model_copy(update={"retained_limitations": ()})
    tampered_ledger = ledger.model_copy(
        update={"compression_loss_receipts": (tampered,)}
    )
    tampered_projection = projection.model_copy(
        update={"prompt_tool_ledger": tampered_ledger}
    )
    tampered_record = record.model_copy(
        update={"prompt_tool_ledger_projection": tampered_projection}
    )

    surface = g6.build_g6_agent_audit_surface(tampered_record)
    bundle = g6.build_g6_authority_preserving_public_export(
        tampered_record,
        generated_at=datetime(2026, 8, 19, 12, 0, tzinfo=UTC),
    )

    assert surface.status == "fail"
    assert surface.PUBLIC["compression_result"]["status"] == "blocked"
    assert "summary" not in surface.PUBLIC["compression_result"]
    exported = bundle["artifacts"]["g6_summary_authority_preservation"]
    assert exported["compression_result"]["terminal_result"]["result_kind"] == (
        "governed_refusal"
    )
    protected = exported["compression_result"]["terminal_result"][
        "protected_material"
    ]
    assert protected["counterevidence"]
    assert protected["limitations"]
    assert protected["denied_uses"]


def test_g6_consumer_rejects_owner_validation_bypass() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    record = _g6_record("req-compression-owner-bypass")
    projection = record.prompt_tool_ledger_projection
    ledger = projection.prompt_tool_ledger
    forged = ledger.orchestration_authority_deltas[0].model_copy(
        update={
            "decision_policy_ref": (
                "policyos://orchestration-choice-policy/attacker-supplied/v1"
            )
        }
    )
    bypassed_ledger = ledger.model_copy(
        update={
            "orchestration_authority_deltas": (
                forged,
                *ledger.orchestration_authority_deltas[1:],
            )
        }
    )
    bypassed_projection = projection.model_copy(
        update={"prompt_tool_ledger": bypassed_ledger}
    )
    bypassed_record = record.model_copy(
        update={"prompt_tool_ledger_projection": bypassed_projection}
    )

    clean_verification = g6.verify_g6_summary_authority_preservation(record)
    verification = g6.verify_g6_summary_authority_preservation(bypassed_record)
    surface = g6.build_g6_agent_audit_surface(bypassed_record)

    assert clean_verification.status == "pass"
    assert verification.status == "fail"
    assert (
        "layer3_g6_authority_delta_owner_validation_failed"
        in verification.issue_codes
    )
    assert surface.status == "fail"


@pytest.mark.asyncio
async def test_g6_bounded_loop_emits_compression_and_choice_receipts() -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    result = await g6.run_layer3_g6_bounded_agent_loop(
        repo_root=REPO_ROOT,
        raw_request="Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-compression-bounded-loop",
        policy_grammar_projection=_policy_grammar_projection(
            "req-compression-bounded-loop"
        ),
        client=g6.FakeG6ToolCallingClient(
            tool_sequence=(
                "layer3_g6_classify_request",
                "layer3_g6_build_g5_bundle",
            )
        ),
        max_iterations=3,
    )

    ledger = result.prompt_tool_ledger_projection.prompt_tool_ledger
    assert ledger.compression_loss_receipts[0].status == "pass"
    assert ledger.authority_delta_completeness_receipts[0].status == "pass"
    assert result.orchestration_choice_audit.authority_delta_completeness is not None
    assert result.orchestration_choice_audit.authority_delta_completeness.status == "pass"
    assert g6.verify_g6_loop_summary_authority_preservation(result).status == "pass"


@pytest.mark.asyncio
async def test_g6_blocked_loop_emits_governed_compression_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality.proving_ground import bounded_request_agent as g6

    monkeypatch.setattr(g6, "create_traced_gateway_client", lambda **_: None)
    result = await g6.run_layer3_g6_bounded_agent_loop(
        repo_root=REPO_ROOT,
        raw_request="Can Ukraine improve affordable loans for wartime MSMEs?",
        request_id="req-compression-blocked-loop",
        policy_grammar_projection=_policy_grammar_projection(
            "req-compression-blocked-loop"
        ),
        client=None,
        max_iterations=3,
    )

    ledger = result.prompt_tool_ledger_projection.prompt_tool_ledger
    assert result.status == "blocked"
    assert ledger.compression_loss_receipts[0].status == "pass"
    assert ledger.compression_loss_receipts[0].authoritative_for == ()
    assert ledger.authority_delta_completeness_receipts[0].status == "pass"
    assert g6.verify_g6_loop_summary_authority_preservation(result).status == "pass"
