"""Missing or conflicting request scope never becomes a fictional jurisdiction."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.contracts.scholar import ResearchIntent
from polisyos.scientist.nodes.builtins.planning.plan_policy_request import PlanPolicyRequestNode
from polisyos.scientist.nodes.builtins.state_keys import INPUT_RESEARCH_INTENT_REF
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.validation.policy_verified import (
    PolicyRequestFrame,
    load_policy_request_frame,
    service,
)


@pytest.mark.parametrize(
    ("params", "reason"),
    [
        ({"policy_question": "Synthetic question?"}, "policy_request_jurisdiction_not_established"),
        ({"jurisdiction": "synthetic"}, "policy_request_question_not_established"),
        (
            {"policy_question": {"text": "not a declared question"}, "jurisdiction": "synthetic"},
            "policy_request_question_invalid",
        ),
        (
            {
                "policy_question": "Synthetic question?",
                "jurisdiction": "synthetic-a",
                "policy_request_jurisdiction": "synthetic-b",
            },
            "policy_request_jurisdiction_conflict",
        ),
        (
            {"policy_question": "Synthetic question?", "jurisdiction": ["synthetic"]},
            "policy_request_jurisdiction_invalid",
        ),
    ],
)
def test_unknown_scope_refuses_before_legal_retrieval_or_llm(tmp_path, monkeypatch, params, reason):
    store = FileSystemCAS(tmp_path / "cas")
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    state = ExperimentState(run_id="synthetic-unknown-scope", params=params)
    frame = service.build_policy_request_frame(ctx, state)
    assert reason in frame.notes
    if "jurisdiction" in reason:
        assert not frame.jurisdiction
    else:
        assert not frame.policy_question
    outcome = PlanPolicyRequestNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None and outcome.error.code == reason
    assert outcome.state.policy_request_ref is None
    assert store.iter_artifact_ids() == []

    def forbidden(*_args, **_kwargs):
        raise AssertionError("unknown scope must not invoke legal or LLM producers")

    monkeypatch.setattr(service, "_build_legal_toolkit", forbidden)
    monkeypatch.setattr(service, "_maybe_verify_with_llm", forbidden)
    candidate = service.assemble_legal_candidate_pack(ctx, state, frame)
    source = service.expand_legal_source_pack(ctx, state, candidate)
    report = service.verify_source_pack(ctx, state, frame, candidate, source)
    recovered_candidate, recovered_source, reviewed = service.recover_source_gaps(
        ctx, state, frame, candidate, source, report
    )
    assert reason in candidate.notes and reason in source.notes
    assert report.needs_expert_review
    assert any(
        gap.severity == "critical" and gap.category == reason
        for gap in report.unresolved_critical_gaps
    )
    assert not report.verified_claims
    assert recovered_candidate == candidate and recovered_source == source
    assert reviewed.needs_expert_review
    assert any(
        gap.severity == "critical" and gap.category == reason
        for gap in reviewed.unresolved_critical_gaps
    )


@pytest.mark.parametrize("jurisdictions", [["synthetic"], ["synthetic-a", "synthetic-b"]])
def test_research_source_jurisdictions_do_not_supply_target_scope(tmp_path, jurisdictions) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_json(
        ResearchIntent(topic="Synthetic research question", jurisdictions=jurisdictions),
        PutOptions(
            kind="scholar.research_intent",
            media_type="application/json",
            schema=SchemaInfo(name="test.ResearchIntent", version="1.0"),
        ),
        return_selected_profile=True,
    )
    state = ExperimentState(
        run_id="synthetic-intent-scope", inputs={INPUT_RESEARCH_INTENT_REF: ref}
    )
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    outcome = PlanPolicyRequestNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert (
        outcome.error is not None
        and outcome.error.code == "policy_request_jurisdiction_not_established"
    )


def test_singular_research_source_jurisdiction_is_not_policy_target(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_json(
        ResearchIntent(topic="Synthetic question", jurisdiction="synthetic-source"),
        PutOptions(
            kind="scholar.research_intent",
            media_type="application/json",
            schema=SchemaInfo(name="test.ResearchIntent", version="1.0"),
        ),
        return_selected_profile=True,
    )
    state = ExperimentState(
        run_id="synthetic-source-scope", inputs={INPUT_RESEARCH_INTENT_REF: ref}
    )
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    outcome = PlanPolicyRequestNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert (
        outcome.error is not None
        and outcome.error.code == "policy_request_jurisdiction_not_established"
    )


def test_research_source_and_policy_target_jurisdictions_remain_distinct(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_json(
        ResearchIntent(topic="Synthetic question", jurisdiction="synthetic-a"),
        PutOptions(
            kind="scholar.research_intent",
            media_type="application/json",
            schema=SchemaInfo(name="test.ResearchIntent", version="1.0"),
        ),
        return_selected_profile=True,
    )
    state = ExperimentState(
        run_id="synthetic-conflicting-intent",
        inputs={INPUT_RESEARCH_INTENT_REF: ref},
        params={"jurisdiction": "synthetic-b"},
    )
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    outcome = PlanPolicyRequestNode().execute(ctx, state)
    assert outcome.status == "ok" and outcome.state.policy_request_ref is not None
    frame = load_policy_request_frame(store, outcome.state.policy_request_ref)
    assert frame.jurisdiction == "synthetic-b"
    assert frame.schema_version == "1.1"
    assert frame.jurisdiction_source == "jurisdiction"
    assert "policy_request_question_from_research_topic" in frame.notes
    manifest = store.get_manifest(outcome.state.policy_request_ref)
    assert len(manifest.inputs) == 1
    assert manifest.inputs[0].manifest_profile_sha256 == ref.manifest_profile_sha256


def test_research_intent_without_selected_profile_cannot_seed_request(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    selected = store.put_json(
        ResearchIntent(topic="Synthetic question", jurisdiction="synthetic"),
        PutOptions(
            kind="scholar.research_intent",
            media_type="application/json",
            schema=SchemaInfo(name="test.ResearchIntent", version="1.0"),
        ),
        return_selected_profile=True,
    )
    legacy = selected.model_copy(update={"manifest_profile_sha256": None})
    state = ExperimentState(
        run_id="synthetic-legacy-intent",
        inputs={INPUT_RESEARCH_INTENT_REF: legacy},
        params={"policy_request_jurisdiction": "synthetic"},
    )
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    outcome = PlanPolicyRequestNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert (
        outcome.error is not None
        and outcome.error.code == "policy_request_intent_profile_not_established"
    )


@pytest.mark.parametrize(
    "kind,media_type",
    [("foreign.intent", "application/json"), ("scholar.research_intent", "text/plain")],
)
def test_research_intent_wrong_selected_owner_cannot_seed_request(
    tmp_path, kind, media_type
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    selected = store.put_json(
        ResearchIntent(topic="Synthetic question"),
        PutOptions(kind="scholar.research_intent", media_type="application/json"),
        return_selected_profile=True,
    )
    ref = store.put_bytes(
        store.get_bytes(selected),
        PutOptions(kind=kind, media_type=media_type),
        return_selected_profile=True,
    )
    assert ref.artifact_id == selected.artifact_id
    assert ref.manifest_profile_sha256 != selected.manifest_profile_sha256
    state = ExperimentState(
        run_id="synthetic-foreign-intent",
        inputs={INPUT_RESEARCH_INTENT_REF: ref},
        params={"policy_request_jurisdiction": "synthetic"},
    )
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    outcome = PlanPolicyRequestNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "policy_request_intent_profile_not_established"


def test_legacy_frame_omitting_jurisdiction_remains_unscoped(tmp_path, monkeypatch) -> None:
    frame = PolicyRequestFrame.model_validate(
        {"request_id": "legacy-unscoped", "policy_question": "Synthetic question?"}
    )
    assert not frame.jurisdiction
    ctx = cast("ExecutionContext", SimpleNamespace(store=FileSystemCAS(tmp_path / "cas")))
    state = ExperimentState(run_id="legacy-unscoped")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("legacy omitted scope must not invoke legal producers")

    monkeypatch.setattr(service, "_build_legal_toolkit", forbidden)
    candidate = service.assemble_legal_candidate_pack(ctx, state, frame)
    assert "policy_request_jurisdiction_not_established" in candidate.notes


def test_legacy_serialized_ua_is_not_proof_of_declared_target(tmp_path, monkeypatch) -> None:
    frame = PolicyRequestFrame.model_validate(
        {
            "schema_version": "1.0",
            "request_id": "legacy-implicit-ua",
            "policy_question": "Synthetic question?",
            "jurisdiction": "UA",
        }
    )
    ctx = cast("ExecutionContext", SimpleNamespace(store=FileSystemCAS(tmp_path / "cas")))
    state = ExperimentState(run_id="legacy-implicit-ua")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("legacy implicit jurisdiction must not invoke legal producers")

    monkeypatch.setattr(service, "_build_legal_toolkit", forbidden)
    candidate = service.assemble_legal_candidate_pack(ctx, state, frame)
    assert "policy_request_jurisdiction_provenance_not_established" in candidate.notes


def test_legacy_request_writer_keeps_the_original_v1_wire_shape(tmp_path) -> None:
    from polisyos.scientist.validation.policy_verified import persist_policy_request_frame

    store = FileSystemCAS(tmp_path / "cas")
    frame = PolicyRequestFrame(
        request_id="legacy-wire", policy_question="Synthetic?", jurisdiction="synthetic"
    )
    ref = persist_policy_request_frame(store, frame)
    assert store.get_manifest(ref).artifact_schema.version == "1.0"
    assert b'"jurisdiction_source"' not in store.get_bytes(ref)
    restored = load_policy_request_frame(store, ref)
    assert restored.schema_version == "1.0" and restored.jurisdiction_source is None


def test_scope_refusal_preserves_prior_diagnostic_claims_and_sources(tmp_path, monkeypatch) -> None:
    frame = PolicyRequestFrame(request_id="unscoped", policy_question="Question?", jurisdiction="")
    claim = service.VerifiedLegalClaim(
        claim_id="historical-claim",
        bundle_id="historical-bundle",
        doc_id="historical-document",
        anchor="historical-anchor",
        claim_type="candidate",
        claim_text="Earlier diagnostic claim",
        quote="Earlier diagnostic text",
    )
    candidate = service.LegalCandidatePack(request_id=frame.request_id, notes=["old-candidate"])
    source = service.LegalSourcePack(request_id=frame.request_id, notes=["old-source"])
    report = service.SourceVerificationReport(request_id=frame.request_id, verified_claims=[claim])
    ctx = cast("ExecutionContext", SimpleNamespace(store=FileSystemCAS(tmp_path / "cas")))
    state = ExperimentState(run_id="synthetic-preserve")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("scope refusal must not perform recovery")

    monkeypatch.setattr(service, "_build_legal_toolkit", forbidden)
    same_candidate, same_source, reviewed = service.recover_source_gaps(
        ctx, state, frame, candidate, source, report
    )
    assert same_candidate == candidate and same_source == source
    assert not reviewed.verified_claims
    assert len(reviewed.legal_claim_candidates) == 1
    historical = reviewed.legal_claim_candidates[0]
    assert historical.text == claim.claim_text
    assert historical.metadata["legal_source_candidate"] == {
        "source": "legacy_unbound",
        **claim.model_dump(mode="json"),
    }
    assert reviewed.needs_expert_review
    assert any(
        gap.category == "legal_claim_verification_not_established" and gap.severity == "critical"
        for gap in reviewed.unresolved_critical_gaps
    )
    assert any(
        gap.category == "policy_request_jurisdiction_not_established" and gap.severity == "critical"
        for gap in reviewed.unresolved_critical_gaps
    )


def test_failed_scope_producer_does_not_reactivate_a_prior_request_in_engine(
    tmp_path, monkeypatch
) -> None:
    import logging

    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.nodes.builtins.planning.assemble_legal_candidate_pack import (
        AssembleLegalCandidatePackNode,
    )
    from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
    from polisyos.scientist.validation.policy_verified import persist_policy_request_frame

    store = FileSystemCAS(tmp_path / "cas")
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    old_ref = persist_policy_request_frame(
        store,
        PolicyRequestFrame(
            request_id="old", policy_question="Earlier question?", jurisdiction="earlier-scope"
        ),
    )
    state = ExperimentState(
        run_id="synthetic-refusal-with-history",
        policy_request_ref=old_ref,
        params={"policy_question": "New unscoped question?"},
    )
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=state.run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    plan = PlanPolicyRequestNode()
    legal = AssembleLegalCandidatePackNode()
    registry = NodeRegistry()
    registry.register(plan)
    registry.register(legal)
    workflow = WorkflowSpec(
        workflow_id="synthetic_scope_refusal",
        error_policy="continue",
        nodes=[
            NodeInvocation(alias="plan", node_id=plan.spec.metadata.component_id),
            NodeInvocation(
                alias="legal", node_id=legal.spec.metadata.component_id, depends_on=["plan"]
            ),
        ],
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("a prior request cannot reactivate legal retrieval")

    monkeypatch.setattr(service, "_build_legal_toolkit", forbidden)
    result = WorkflowExecutor(ctx, registry).execute(workflow, state)
    nodes = {node.alias: node for node in result.report.nodes}
    assert nodes["plan"].status == "fail"
    assert nodes["plan"].error is not None
    assert nodes["plan"].error.code == "policy_request_jurisdiction_not_established"
    assert nodes["legal"].status == "skip"
    assert result.state.policy_request_ref == old_ref
    assert result.state.legal_candidate_pack_ref is None
