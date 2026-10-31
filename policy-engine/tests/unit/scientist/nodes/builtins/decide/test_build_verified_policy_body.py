from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
)
from polisyos.core.contracts.foundry import Metrics
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
    persist_causal_effect_report,
)
from polisyos.scientist.nodes.builtins.decide.build_verified_policy_body import (
    BuildVerifiedPolicyBodyNode,
    _build_candidate_body,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_POLICY_OPTION_SET_REF,
    ARTIFACT_VERIFIED_POLICY_BODY_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.validation.policy_verified import (
    PolicyOptionSet,
    PolicyRequestFrame,
    SourceVerificationReport,
    load_verified_policy_body,
    persist_policy_option_set,
    persist_policy_request_frame,
    persist_source_verification_report,
)


def _body_case(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    request = persist_policy_request_frame(
        store,
        PolicyRequestFrame(
            request_id="synthetic", policy_question="Synthetic?", jurisdiction="synthetic"
        ),
    )
    source = persist_source_verification_report(
        store,
        SourceVerificationReport(request_id="synthetic", needs_expert_review=True),
        inputs=[input_ref_from_artifact_ref(request, role="policy_request_frame")],
    )
    options = persist_policy_option_set(
        store,
        PolicyOptionSet(request_id="synthetic"),
        inputs=[
            input_ref_from_artifact_ref(request, role="policy_request_frame"),
            input_ref_from_artifact_ref(source, role="source_verification_report"),
        ],
    )
    metrics = store.put_json(
        Metrics(values={"synthetic_metric": 1}),
        PutOptions(
            kind=Metrics.ARTIFACT_KIND,
            media_type=Metrics.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=Metrics.ARTIFACT_SCHEMA_NAME, version=Metrics.ARTIFACT_SCHEMA_VERSION
            ),
        ),
        return_selected_profile=True,
    )
    causal = ArtifactRef.model_validate(
        persist_causal_effect_report(
            ensure_ir_artifact_store(store),
            CausalEffectReport(
                method=CausalMethod.DOWHY_BACKDOOR,
                status=EstimationStatus.INPUT_INVALID,
                status_reason="synthetic fixture",
                estimand="synthetic",
                inference_method="not_run",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
            ),
            return_selected_profile=True,
        ).model_dump(mode="json")
    )
    state = ExperimentState(
        run_id="synthetic-body",
        policy_request_ref=request,
        policy_option_set_ref=options,
        source_verification_report_ref=source,
        artifacts_index={ARTIFACT_METRICS_REF: metrics, ARTIFACT_CAUSAL_REPORT_REF: causal},
    )
    return (
        state,
        cast("ExecutionContext", SimpleNamespace(store=store)),
        request,
        options,
        source,
        metrics,
        causal,
    )


def test_restricted_body_producer_persists_all_selected_sources(tmp_path) -> None:
    """The content helper preserves sources without claiming Engine provenance."""
    state, ctx, request, options, source, metrics, causal = _body_case(tmp_path)
    outcome = _build_candidate_body(ctx, state)
    assert outcome.status == "ok"
    body_ref = outcome.state.artifacts_index[ARTIFACT_VERIFIED_POLICY_BODY_REF]
    assert body_ref.kind == "scientist.verified_policy_body"
    assert body_ref.manifest_profile_sha256 is not None
    assert outcome.state.verified_policy_report_ref is None
    assert ctx.store.get_manifest(body_ref).inputs == [
        input_ref_from_artifact_ref(request, role="policy_request_frame"),
        input_ref_from_artifact_ref(options, role="policy_option_set"),
        input_ref_from_artifact_ref(source, role="source_verification_report"),
        input_ref_from_artifact_ref(metrics, role=ARTIFACT_METRICS_REF),
        input_ref_from_artifact_ref(causal, role=ARTIFACT_CAUSAL_REPORT_REF),
    ]
    body = load_verified_policy_body(ctx.store, body_ref)
    assert body.request_id == "synthetic"
    assert body.needs_expert_review is True
    assert len(body.simulation_and_causal_implications) == 2


def test_body_does_not_claim_unproved_option_program_correspondence(tmp_path) -> None:
    """Clean legal diagnostics alone do not bind the final executable program to an option."""
    state, ctx, request, *_ = _body_case(tmp_path)
    state.source_verification_report_ref = persist_source_verification_report(
        ctx.store,
        SourceVerificationReport(request_id="synthetic", needs_expert_review=False),
        inputs=[input_ref_from_artifact_ref(request, role="policy_request_frame")],
    )
    state.policy_option_set_ref = persist_policy_option_set(
        ctx.store,
        PolicyOptionSet(request_id="synthetic"),
        inputs=[
            input_ref_from_artifact_ref(request, role="policy_request_frame"),
            input_ref_from_artifact_ref(
                state.source_verification_report_ref, role="source_verification_report"
            ),
        ],
    )
    outcome = _build_candidate_body(ctx, state)
    assert outcome.status == "ok"
    selected = outcome.state.artifacts_index[ARTIFACT_VERIFIED_POLICY_BODY_REF]
    body = load_verified_policy_body(ctx.store, selected)
    assert body.needs_expert_review is True
    assert "option_program_correspondence_not_established" in body.notes
    assert "legal_claim_verification_not_established" in body.notes
    assert any(
        "option" in item.lower() and "program" in item.lower() for item in body.missing_evidence
    )


def test_body_node_requires_an_engine_selected_attempt(tmp_path) -> None:
    state, ctx, *_ = _body_case(tmp_path)
    outcome = BuildVerifiedPolicyBodyNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None and outcome.error.code == "policy_body_attempt_not_established"
    assert ARTIFACT_VERIFIED_POLICY_BODY_REF not in outcome.state.artifacts_index


@pytest.mark.parametrize("extraneous", ["params", "reports", "artifact"])
def test_body_producer_refuses_unrestricted_input(tmp_path, extraneous: str) -> None:
    """An input outside the port cannot silently become producer-visible data."""
    state, ctx, *_ = _body_case(tmp_path)
    if extraneous == "params":
        state.params["reported_policy_promotion_history"] = [{"judge_verdict": "promote"}]
    elif extraneous == "reports":
        state.reports_index["unrelated"] = state.policy_request_ref
    else:
        state.artifacts_index["unrelated"] = state.policy_request_ref
    outcome = _build_candidate_body(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None and outcome.error.code == "policy_body_port_not_projected"
    assert ARTIFACT_VERIFIED_POLICY_BODY_REF not in outcome.state.artifacts_index


def test_body_producer_refuses_foreign_selected_profile(tmp_path) -> None:
    state, ctx, _request, options, *_ = _body_case(tmp_path)
    manifest = ctx.store.get_manifest(options)
    foreign = ctx.store.put_bytes(
        ctx.store.get_bytes(options),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=SchemaInfo(name="test.ForeignOptions", version="1.0"),
            canon=manifest.canon,
        ),
        return_selected_profile=True,
    )
    assert foreign.artifact_id == options.artifact_id
    assert foreign.manifest_profile_sha256 != options.manifest_profile_sha256
    state.policy_option_set_ref = foreign
    outcome = _build_candidate_body(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None and outcome.error.code == "policy_body_source_invalid"


def test_body_producer_refuses_conflicting_direct_and_index_selection(tmp_path) -> None:
    state, ctx, _request, options, source, *_ = _body_case(tmp_path)
    manifest = ctx.store.get_manifest(options)
    alias = ctx.store.put_bytes(
        ctx.store.get_bytes(options),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            canon=manifest.canon,
            inputs=[input_ref_from_artifact_ref(source, role="other")],
        ),
        return_selected_profile=True,
    )
    assert alias.artifact_id == options.artifact_id
    assert alias.manifest_profile_sha256 != options.manifest_profile_sha256
    state.artifacts_index[ARTIFACT_POLICY_OPTION_SET_REF] = alias
    outcome = _build_candidate_body(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None and outcome.error.code == "policy_source_selection_conflict"


def test_engine_uses_restricted_body_port_and_recomputes_currentness(tmp_path, monkeypatch) -> None:
    """The real Engine hides unrelated state while preserving it in the successor."""
    import logging

    import polisyos.scientist.nodes.builtins.decide.build_verified_policy_body as body_owner
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
    from polisyos.scientist.orchestration.engine.producer_currentness import (
        resolve_engine_produced_artifact,
    )
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

    state, fixture_ctx, _request, options, source, *_ = _body_case(tmp_path)
    store = fixture_ctx.store
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=state.run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    state.inputs["registry_bundle_ref"] = registry_ref
    state.params["reported_policy_promotion_history"] = [{"judge_verdict": "untrusted"}]
    state.reports_index["unrelated_report"] = source
    node = BuildVerifiedPolicyBodyNode()
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="synthetic_restricted_body",
        nodes=[NodeInvocation(alias="candidate_body", node_id=node.spec.metadata.component_id)],
    )

    result = WorkflowExecutor(ctx, registry).execute(workflow, state)
    assert result.report.nodes[0].status == "ok"
    body_ref = result.state.artifacts_index[ARTIFACT_VERIFIED_POLICY_BODY_REF]
    assert result.state.params["reported_policy_promotion_history"] == [
        {"judge_verdict": "untrusted"}
    ]
    assert result.state.reports_index["unrelated_report"] == source
    attempts = run.read_runtime_invocation_attempts()
    assert len(attempts) == 1
    projected_ref = attempts[0].basis.input_state_ref
    body_inputs = store.get_manifest(body_ref).inputs
    assert input_ref_from_artifact_ref(projected_ref, role="selected_input") in body_inputs
    assert (
        input_ref_from_artifact_ref(attempts[0].basis_ref, role="selected_attempt") in body_inputs
    )
    assert projected_ref.manifest_profile_sha256 is not None
    projected = ExperimentState.model_validate(from_canonical_bytes(store.get_bytes(projected_ref)))
    assert projected.params == {}
    assert projected.inputs == {}
    assert projected.reports_index == {}
    assert set(projected.artifacts_index) == {ARTIFACT_METRICS_REF, ARTIFACT_CAUSAL_REPORT_REF}

    def admission(current: ExperimentState, selected_ref=body_ref):
        return resolve_engine_produced_artifact(
            ctx,
            current,
            selected_ref,
            expected_component_id=str(node.spec.metadata.component_id),
            expected_node_spec=node.spec,
            source_read_paths=tuple(node.spec.state_reads),
        )

    assert admission(result.state).is_current
    body_manifest = store.get_manifest(body_ref)
    forged_inputs = [
        input_ref_from_artifact_ref(source, role="selected_attempt")
        if edge.role == "selected_attempt"
        else edge
        for edge in body_manifest.inputs
    ]
    forged = store.put_bytes(
        store.get_bytes(body_ref),
        PutOptions(
            kind=body_manifest.kind,
            media_type=body_manifest.media_type,
            schema=body_manifest.artifact_schema,
            canon=body_manifest.canon,
            inputs=forged_inputs,
        ),
        return_selected_profile=True,
    )
    assert forged.artifact_id == body_ref.artifact_id
    assert forged.manifest_profile_sha256 != body_ref.manifest_profile_sha256
    assert admission(result.state, forged).status == "not_established"
    unrelated = result.state.model_copy(deep=True)
    unrelated.params["new_unrelated_field"] = "no effect on restricted body"
    assert admission(unrelated).is_current
    original_manifest = store.get_manifest(options)
    alias = store.put_bytes(
        store.get_bytes(options),
        PutOptions(
            kind=original_manifest.kind,
            media_type=original_manifest.media_type,
            schema=original_manifest.artifact_schema,
            canon=original_manifest.canon,
            inputs=[input_ref_from_artifact_ref(source, role="different_source")],
        ),
        return_selected_profile=True,
    )
    assert alias.artifact_id == options.artifact_id
    assert alias.manifest_profile_sha256 != options.manifest_profile_sha256
    changed = result.state.model_copy(deep=True)
    changed.policy_option_set_ref = alias
    assert admission(changed).status == "stale"

    actual_builder = body_owner._build_candidate_body
    monkeypatch.setattr(body_owner, "_build_candidate_body", lambda *_args, **_kwargs: None)
    assert admission(result.state).status == "not_established"
    monkeypatch.setattr(body_owner, "_build_candidate_body", actual_builder)
    monkeypatch.setattr(BuildVerifiedPolicyBodyNode, "execute", lambda *_args: None)
    assert admission(result.state).status == "not_established"


def test_engine_refuses_changed_body_helper_before_callback(tmp_path, monkeypatch) -> None:
    """Keeping the class, source file and port intact cannot replace the builder."""
    import logging

    import polisyos.scientist.nodes.builtins.decide.build_verified_policy_body as body_owner
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
    from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

    state, fixture_ctx, *_ = _body_case(tmp_path)
    store = fixture_ctx.store
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=state.run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    node = BuildVerifiedPolicyBodyNode()
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="synthetic_body_helper_removal",
        nodes=[NodeInvocation(alias="candidate_body", node_id=node.spec.metadata.component_id)],
    )
    called = []

    def counterfeit(_ctx, input_state, **_kwargs):
        called.append(True)
        return NodeOutcome(
            status="fail", state=input_state, error=NodeError(code="test.called", message="called")
        )

    monkeypatch.setattr(body_owner, "_build_candidate_body", counterfeit)
    result = WorkflowExecutor(ctx, registry).execute(workflow, state)
    assert result.report.nodes[0].status == "fail"
    assert result.report.nodes[0].error is not None
    assert result.report.nodes[0].error.code == "node.input_port_refused"
    assert called == []


@pytest.mark.parametrize("role", [ARTIFACT_METRICS_REF, ARTIFACT_CAUSAL_REPORT_REF])
def test_body_refuses_a_selected_foreign_optional_source(tmp_path, role: str) -> None:
    """A resolvable unrelated CAS artifact is not a metrics or causal report."""
    state, ctx, request, *_ = _body_case(tmp_path)
    state.artifacts_index[role] = request
    outcome = _build_candidate_body(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None and outcome.error.code == "policy_body_source_invalid"
