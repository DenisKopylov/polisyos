"""Model-proposed legal claims cannot become verified source findings by assertion."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import cast

import pytest

from polisyos.core.artifacts import FileSystemCAS, input_ref_from_artifact_ref
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.lex.knowledge.types import LegalFactResult, LegalSourceAnchor, LegalSourceBundle
from polisyos.scientist.evidence.claims.models import (
    ClaimPublishability,
    ClaimSourceClass,
    ClaimSupportStatus,
    ClaimUse,
)
from polisyos.scientist.governance.human_review.models import (
    FundamentalRightsChecklist,
    ReviewRiskTier,
)
from polisyos.scientist.governance.human_review.packets import (
    build_review_packet,
    review_packet_summary,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet_support import (
    _populate_optional_report_projections,
)
from polisyos.scientist.nodes.builtins.planning.run_source_verification import (
    RunSourceVerificationNode,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_SOURCE_VERIFICATION_REPORT_REF
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
from polisyos.scientist.validation.policy_verified.models import (
    LegalCandidatePack,
    LegalSourcePack,
    PolicyRequestFrame,
    SourceCoverageGap,
    SourceVerificationReport,
    VerifiedLegalClaim,
    load_source_verification_report,
    persist_legal_candidate_pack,
    persist_legal_source_pack,
    persist_policy_request_frame,
    persist_source_verification_report,
)
from polisyos.scientist.validation.policy_verified.service import (
    build_verified_policy_report,
    draft_policy_option_set,
    recover_source_gaps,
    review_source_gaps,
    verify_source_pack,
)


@pytest.mark.parametrize("quote", ["A fabricated quotation.", "A synthetic source sentence."])
def test_model_claim_does_not_become_verified_finding(tmp_path, monkeypatch, quote: str) -> None:
    """Neither an invented quote nor a real quote proves the model's legal conclusion."""
    import polisyos.scientist.validation.policy_verified.service as service

    class CandidateModel:
        async def generate(self, **_kwargs):
            return SimpleNamespace(
                content=json.dumps(
                    {
                        "claims": [
                            {
                                "anchor": "article:1",
                                "quote": quote,
                                "claim_text": "All transport is prohibited.",
                                "claim_type": "prohibition",
                                "extra": {"explicit_null": None},
                            }
                        ]
                    }
                )
            )

    monkeypatch.setattr(service, "create_traced_gateway_client", lambda **_kwargs: CandidateModel())
    store = FileSystemCAS(tmp_path / "cas")
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    state = ExperimentState(run_id="synthetic-legal-model-candidate")
    frame = PolicyRequestFrame(
        schema_version="1.1",
        request_id="synthetic",
        policy_question="Synthetic?",
        jurisdiction="synthetic",
        jurisdiction_source="policy_request_jurisdiction",
    )
    candidate_pack = LegalCandidatePack(request_id=frame.request_id)
    source_pack = LegalSourcePack(
        request_id=frame.request_id,
        source_bundles=[
            LegalSourceBundle(
                bundle_id="synthetic-bundle",
                doc_id="synthetic-document",
                primary_anchors=[
                    LegalSourceAnchor(
                        doc_id="synthetic-document",
                        anchor="article:1",
                        provision_text="A synthetic source sentence.",
                    )
                ],
            )
        ],
    )
    report = verify_source_pack(ctx, state, frame, candidate_pack, source_pack)
    assert not report.verified_claims
    assert report.legal_verification_status == "not_established"
    assert report.needs_expert_review is True
    assert len(report.legal_claim_candidates) == 1
    claim = report.legal_claim_candidates[0]
    assert claim.decomposition_source_class is ClaimSourceClass.LLM_CANDIDATE
    assert claim.claim_use is ClaimUse.CONTEXT_ONLY
    assert claim.support_status is ClaimSupportStatus.NOT_EVALUABLE
    assert claim.publishability is ClaimPublishability.INTERNAL_ONLY
    assert claim.metadata["legal_source_candidate"]["quote"] == quote
    selected = persist_source_verification_report(store, report)
    reopened = load_source_verification_report(FileSystemCAS(tmp_path / "cas"), selected)
    assert reopened.legal_claim_candidates == report.legal_claim_candidates
    assert reopened.legal_verification_status == "not_established"
    assert (
        reopened.legal_claim_candidates[0].metadata["legal_source_candidate"]["raw_model_item"][
            "extra"
        ]["explicit_null"]
        is None
    )
    options = draft_policy_option_set(state, frame, report)
    assert not options.verified_options
    assert options.hypothesis_options
    body = build_verified_policy_report(state, frame, report, options)
    assert not body.verified_legal_basis
    assert not body.verified_findings
    assert body.needs_expert_review


@pytest.mark.parametrize("quote", ["A fabricated quotation.", "A synthetic source sentence."])
def test_search_candidate_fact_does_not_become_verified_finding(
    tmp_path, monkeypatch, quote: str
) -> None:
    """A search-candidate label and quotation do not independently admit its meaning."""
    import polisyos.scientist.validation.policy_verified.service as service

    monkeypatch.setattr(service, "create_traced_gateway_client", lambda **_kwargs: None)
    ctx = cast("ExecutionContext", SimpleNamespace(store=FileSystemCAS(tmp_path / "cas")))
    state = ExperimentState(run_id="synthetic-legal-search-candidate")
    frame = PolicyRequestFrame(
        schema_version="1.1",
        request_id="synthetic",
        policy_question="Synthetic?",
        jurisdiction="synthetic",
        jurisdiction_source="policy_request_jurisdiction",
    )
    fact = LegalFactResult(
        fact_id="synthetic-fact",
        subject_name="synthetic subject",
        predicate="prohibits",
        object_name="transport",
        fact_text="All transport is prohibited.",
        confidence=0.9,
        norm_type="prohibition",
        source_quote_uk=quote,
        doc_id="synthetic-document",
        doc_name="Synthetic source",
        doc_reestr_code="synthetic",
        provision_anchor="article:1",
        provision_citation="article 1",
        similarity=1.0,
    )
    candidate_pack = LegalCandidatePack(request_id=frame.request_id, fact_hits=[fact])
    source_pack = LegalSourcePack(
        request_id=frame.request_id,
        source_bundles=[
            LegalSourceBundle(
                bundle_id="synthetic-bundle",
                doc_id="synthetic-document",
                candidate_fact_ids=[fact.fact_id],
                primary_anchors=[
                    LegalSourceAnchor(
                        doc_id="synthetic-document",
                        anchor="article:1",
                        provision_text="A synthetic source sentence.",
                    )
                ],
            )
        ],
    )
    report = verify_source_pack(ctx, state, frame, candidate_pack, source_pack)
    assert not report.verified_claims
    assert report.legal_verification_status == "not_established"
    assert report.needs_expert_review is True
    assert len(report.legal_claim_candidates) == 1
    claim = report.legal_claim_candidates[0]
    assert claim.claim_use is ClaimUse.CONTEXT_ONLY
    assert claim.support_status is ClaimSupportStatus.NOT_EVALUABLE
    assert claim.publishability is ClaimPublishability.INTERNAL_ONLY
    assert claim.metadata["legal_source_candidate"]["quote"] == quote


def test_legacy_verified_labels_remain_readable_but_are_not_readmitted(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    claim = VerifiedLegalClaim(
        claim_id="synthetic-legacy",
        bundle_id="synthetic-bundle",
        doc_id="synthetic-document",
        anchor="article:1",
        claim_type="prohibition",
        claim_text="All transport is prohibited.",
        quote="A synthetic source sentence.",
    )
    historical = SourceVerificationReport(request_id="synthetic", verified_claims=[claim])
    selected = persist_source_verification_report(store, historical)
    reopened = load_source_verification_report(FileSystemCAS(tmp_path / "cas"), selected)
    assert reopened.schema_version == "1.0" and reopened.verified_claims == [claim]
    assert reopened.legal_verification_status == "not_established"
    frame = PolicyRequestFrame(
        schema_version="1.1",
        request_id="synthetic",
        policy_question="Synthetic?",
        jurisdiction="synthetic",
        jurisdiction_source="policy_request_jurisdiction",
    )
    state = ExperimentState(run_id="synthetic-legacy-legal-report")
    options = draft_policy_option_set(state, frame, reopened)
    body = build_verified_policy_report(state, frame, reopened, options)
    assert not options.verified_options
    assert options.hypothesis_options
    assert not body.verified_legal_basis and not body.verified_findings
    assert body.needs_expert_review
    caller_status = reopened.model_copy(update={"legal_verification_status": "current"})
    caller_options = draft_policy_option_set(state, frame, caller_status)
    caller_body = build_verified_policy_report(state, frame, caller_status, caller_options)
    assert not caller_options.verified_options
    assert not caller_body.verified_legal_basis and not caller_body.verified_findings
    assert caller_body.needs_expert_review
    state.artifacts_index[ARTIFACT_SOURCE_VERIFICATION_REPORT_REF] = selected
    packet_payload: dict[str, object] = {}
    _populate_optional_report_projections(
        cast("ExecutionContext", SimpleNamespace(store=store)), state, packet_payload
    )
    legal = cast("dict[str, object]", packet_payload["legal_verification"])
    assert legal["verification_status"] == "not_established"
    assert legal["verified_claim_count"] is None
    assert legal["reported_unbound_claim_count"] == 1
    review = build_review_packet(
        run_id=state.run_id,
        decision_payload=packet_payload,
        risk_tier=ReviewRiskTier.PUBLIC_SECTOR_HIGH,
    )
    assert not review.fundamental_rights_checklist.legal_basis_documented
    assert "legal_basis_documented" in review.fundamental_rights_checklist.unresolved_items


@pytest.mark.parametrize(("severity", "resolved"), [("warning", False), ("critical", True)])
def test_packet_recomputes_open_legal_gap_when_historical_gap_is_not_current(
    tmp_path, severity: str, resolved: bool
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    report = SourceVerificationReport(
        request_id="synthetic",
        unresolved_critical_gaps=[
            SourceCoverageGap.model_validate(
                {
                    "gap_id": "historical-legal-gap",
                    "category": "legal_claim_verification_not_established",
                    "description": "Historical source status.",
                    "severity": severity,
                    "resolved": resolved,
                }
            )
        ],
    )
    selected = persist_source_verification_report(store, report)
    state = ExperimentState(run_id="synthetic-historical-gap")
    state.artifacts_index[ARTIFACT_SOURCE_VERIFICATION_REPORT_REF] = selected
    payload: dict[str, object] = {}
    _populate_optional_report_projections(
        cast("ExecutionContext", SimpleNamespace(store=store)), state, payload
    )
    coverage = cast("dict[str, object]", payload["source_coverage"])
    gaps = cast("list[dict[str, object]]", coverage["unresolved_critical_gaps"])
    assert any(
        gap.get("category") == "legal_claim_verification_not_established"
        and gap.get("severity") == "critical"
        and not gap.get("resolved", False)
        and gap.get("provenance") == "consumer_recomputed"
        for gap in gaps
    )


def test_gap_review_reissues_legacy_claims_as_unbound_candidates(tmp_path, monkeypatch) -> None:
    """A legacy label cannot suppress the real legal-verification gap."""
    import polisyos.scientist.validation.policy_verified.service as service

    monkeypatch.setattr(service, "_build_legal_toolkit", lambda *_args: None)
    store = FileSystemCAS(tmp_path / "cas")
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    state = ExperimentState(run_id="synthetic-legacy-source-review")
    frame = PolicyRequestFrame(
        schema_version="1.1",
        request_id="synthetic",
        policy_question="Synthetic?",
        jurisdiction="synthetic",
        jurisdiction_source="policy_request_jurisdiction",
    )
    source_pack = LegalSourcePack(
        request_id=frame.request_id,
        source_bundles=[LegalSourceBundle(bundle_id="synthetic", doc_id="synthetic")],
    )
    historical = SourceVerificationReport(
        request_id=frame.request_id,
        verified_claims=[
            VerifiedLegalClaim(
                claim_id="old-claim",
                bundle_id="synthetic",
                doc_id="synthetic",
                anchor="article:1",
                claim_type="prohibition",
                claim_text="All transport is prohibited.",
                quote="A synthetic source sentence.",
            )
        ],
        needs_expert_review=False,
    )
    historical_ref = persist_source_verification_report(store, historical)
    reviewed = review_source_gaps(state, frame, source_pack, historical)
    assert reviewed.schema_version == "1.1"
    assert not reviewed.verified_claims
    assert len(reviewed.legal_claim_candidates) == 1
    assert reviewed.legal_claim_candidates[0].text == historical.verified_claims[0].claim_text
    assert (
        reviewed.legal_claim_candidates[0].metadata["legal_source_candidate"]["source"]
        == "legacy_unbound"
    )
    assert reviewed.needs_expert_review
    assert any(
        gap.category == "legal_claim_verification_not_established" and gap.severity == "critical"
        for gap in reviewed.unresolved_critical_gaps
    )
    selected = persist_source_verification_report(store, reviewed)
    reopened = load_source_verification_report(FileSystemCAS(tmp_path / "cas"), selected)
    assert reopened.legal_claim_candidates == reviewed.legal_claim_candidates
    assert load_source_verification_report(store, historical_ref) == historical
    _, _, recovered = recover_source_gaps(
        ctx, state, frame, LegalCandidatePack(request_id=frame.request_id), source_pack, historical
    )
    assert recovered.schema_version == "1.1"
    assert not recovered.verified_claims and recovered.needs_expert_review
    assert any(
        gap.category == "legal_claim_verification_not_established"
        for gap in recovered.unresolved_critical_gaps
    )


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("support_status", ClaimSupportStatus.SUPPORTED, "legal_claim_candidate_authority_invalid"),
        ("publishability", ClaimPublishability.PUBLISHABLE, "publishable claims must be supported"),
    ],
)
def test_candidate_report_writer_refuses_a_promoted_claim_before_persistence(
    tmp_path, monkeypatch, field: str, value: object, reason: str
) -> None:
    import polisyos.scientist.validation.policy_verified.service as service

    class CandidateModel:
        async def generate(self, **_kwargs):
            return SimpleNamespace(
                content=json.dumps(
                    {"claims": [{"claim_text": "A synthetic proposed interpretation."}]}
                )
            )

    monkeypatch.setattr(service, "create_traced_gateway_client", lambda **_kwargs: CandidateModel())
    store = FileSystemCAS(tmp_path / "cas")
    state = ExperimentState(run_id="synthetic-promoted-claim")
    frame = PolicyRequestFrame(
        schema_version="1.1",
        request_id="synthetic",
        policy_question="Synthetic?",
        jurisdiction="synthetic",
        jurisdiction_source="policy_request_jurisdiction",
    )
    source_pack = LegalSourcePack(
        request_id=frame.request_id,
        source_bundles=[LegalSourceBundle(bundle_id="synthetic", doc_id="synthetic")],
    )
    report = verify_source_pack(
        cast("ExecutionContext", SimpleNamespace(store=store)),
        state,
        frame,
        LegalCandidatePack(request_id=frame.request_id),
        source_pack,
    )
    candidate = report.legal_claim_candidates[0].model_copy(update={field: value})
    forged = report.model_copy(update={"legal_claim_candidates": [candidate]})
    before = store.iter_artifact_ids()
    with pytest.raises(ValueError, match=reason):
        persist_source_verification_report(store, forged)
    assert store.iter_artifact_ids() == before
    forged_verified = report.model_copy(
        update={
            "verified_claims": [
                VerifiedLegalClaim(
                    claim_id="synthetic-forgery",
                    bundle_id="synthetic",
                    doc_id="synthetic",
                    anchor="synthetic",
                    claim_type="prohibition",
                    claim_text="A caller-supplied legal conclusion.",
                    quote="A caller-supplied quote.",
                )
            ]
        }
    )
    with pytest.raises(ValueError, match="legal_claim_verification_not_established"):
        persist_source_verification_report(store, forged_verified)
    assert store.iter_artifact_ids() == before


def test_review_does_not_infer_legal_authority_from_caller_markers() -> None:
    review = build_review_packet(
        run_id="synthetic-marker-only",
        decision_payload={
            "legal_verification": {"verification_status": "current", "verified_claim_count": 99}
        },
        risk_tier=ReviewRiskTier.PUBLIC_SECTOR_HIGH,
    )
    assert not review.fundamental_rights_checklist.legal_basis_documented
    assert "legal_basis_documented" in review.fundamental_rights_checklist.unresolved_items


@pytest.mark.parametrize("declared_public_sector", [True, False])
def test_public_review_summary_keeps_caller_legal_checklist_unverified(
    declared_public_sector: bool,
) -> None:
    from polisyos.scientist.publishing.publisher import _reviewer_controls

    supplied = FundamentalRightsChecklist(
        public_sector_use=declared_public_sector,
        legal_basis_documented=True,
        privacy_impact_considered=True,
    )
    packet = build_review_packet(
        run_id="synthetic-caller-checklist",
        risk_tier=ReviewRiskTier.PUBLIC_SECTOR_HIGH,
        fundamental_rights_checklist=supplied,
    )
    assert packet.fundamental_rights_checklist.legal_basis_documented is True
    summary = review_packet_summary(packet)
    assert "legal_basis_documented" in summary["fundamental_rights_unresolved"]
    assert summary["legal_basis_documentation_status"] == "consumer_asserted"
    assert summary["legal_verification_status"] == "not_established"
    public = _reviewer_controls(packet)
    assert public["legal_verification_status"] == "not_established"
    assert "legal_basis_documented" in public["fundamental_rights_unresolved"]


def test_engine_source_report_to_packet_and_review_remains_candidate_only(
    tmp_path, monkeypatch
) -> None:
    """Exercise the real Engine producer, selected CAS readback and both consumers."""
    import logging

    import polisyos.scientist.validation.policy_verified.service as service

    class CandidateModel:
        async def generate(self, **_kwargs):
            return SimpleNamespace(
                content=json.dumps(
                    {
                        "claims": [
                            {
                                "anchor": "article:1",
                                "quote": "A synthetic source sentence.",
                                "claim_text": "All transport is prohibited.",
                                "claim_type": "prohibition",
                            }
                        ]
                    }
                )
            )

    monkeypatch.setattr(service, "create_traced_gateway_client", lambda **_kwargs: CandidateModel())
    store = FileSystemCAS(tmp_path / "cas")
    frame = PolicyRequestFrame(
        schema_version="1.1",
        request_id="synthetic",
        policy_question="Synthetic?",
        jurisdiction="synthetic",
        jurisdiction_source="policy_request_jurisdiction",
    )
    request_ref = persist_policy_request_frame(store, frame)
    fact = LegalFactResult(
        fact_id="synthetic-fact",
        subject_name="synthetic subject",
        predicate="prohibits",
        object_name="transport",
        fact_text="All transport is prohibited.",
        confidence=0.9,
        norm_type="prohibition",
        source_quote_uk="A fabricated quotation.",
        doc_id="synthetic-document",
        doc_name="Synthetic source",
        doc_reestr_code="synthetic",
        provision_anchor="article:1",
        provision_citation="article 1",
        similarity=1.0,
    )
    candidate_ref = persist_legal_candidate_pack(
        store,
        LegalCandidatePack(request_id=frame.request_id, fact_hits=[fact]),
        inputs=[input_ref_from_artifact_ref(request_ref, role="policy_request_frame")],
    )
    source_ref = persist_legal_source_pack(
        store,
        LegalSourcePack(
            request_id=frame.request_id,
            source_bundles=[
                LegalSourceBundle(
                    bundle_id="synthetic-bundle",
                    doc_id="synthetic-document",
                    candidate_fact_ids=[fact.fact_id],
                    primary_anchors=[
                        LegalSourceAnchor(
                            doc_id="synthetic-document",
                            anchor="article:1",
                            provision_text="A synthetic source sentence.",
                        )
                    ],
                )
            ],
        ),
        inputs=[input_ref_from_artifact_ref(candidate_ref, role="legal_candidate_pack")],
    )
    state = ExperimentState(
        run_id="synthetic-source-candidate-engine",
        policy_request_ref=request_ref,
        legal_candidate_pack_ref=candidate_ref,
        legal_source_pack_ref=source_ref,
    )
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=state.run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    node = RunSourceVerificationNode()
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="synthetic_source_candidate",
        nodes=[NodeInvocation(alias="verify", node_id=node.spec.metadata.component_id)],
    )
    result = WorkflowExecutor(ctx, registry).execute(workflow, state)
    assert result.report.nodes[0].status == "ok"
    direct_outcome = node.execute(ctx, state)
    event = direct_outcome.events[0]
    assert event.message == (
        "Legal source candidates collected; independent legal verification is not established."
    )
    assert event.attrs["legal_verification_status"] == "not_established"
    assert event.attrs["candidate_claims"] == 2
    assert event.attrs["verified_claims"] == "not_established"
    selected = result.state.source_verification_report_ref
    assert selected is not None and selected.manifest_profile_sha256 is not None
    fresh = FileSystemCAS(tmp_path / "cas")
    report = load_source_verification_report(fresh, selected)
    assert report.schema_version == "1.1"
    assert not report.verified_claims and len(report.legal_claim_candidates) == 2
    assert report.needs_expert_review and report.legal_verification_status == "not_established"
    assert fresh.get_manifest(selected).inputs == [
        input_ref_from_artifact_ref(request_ref, role="policy_request_frame"),
        input_ref_from_artifact_ref(candidate_ref, role="legal_candidate_pack"),
        input_ref_from_artifact_ref(source_ref, role="legal_source_pack"),
    ]
    packet_payload: dict[str, object] = {}
    _populate_optional_report_projections(ctx, result.state, packet_payload)
    legal = cast("dict[str, object]", packet_payload["legal_verification"])
    assert legal["verification_status"] == "not_established"
    assert legal["verified_claim_count"] is None and legal["candidate_claim_count"] == 2
    review = build_review_packet(
        run_id=state.run_id,
        decision_payload=packet_payload,
        risk_tier=ReviewRiskTier.PUBLIC_SECTOR_HIGH,
    )
    assert not review.fundamental_rights_checklist.legal_basis_documented
    assert "legal_basis_documented" in review.fundamental_rights_checklist.unresolved_items
