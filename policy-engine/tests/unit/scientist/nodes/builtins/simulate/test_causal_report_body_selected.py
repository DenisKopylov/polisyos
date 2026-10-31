from __future__ import annotations

import logging

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    PutOptions,
    SchemaInfo,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.causal import CausalEffectReportRef, load_causal_effect_report
from polisyos.scientist.nodes.builtins.decide.build_verified_policy_body import (
    BuildVerifiedPolicyBodyNode,
)
from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as owner
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_CAUSAL_REPORT_REF
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
from polisyos.scientist.validation.policy_verified import (
    PolicyOptionSet,
    PolicyRequestFrame,
    SourceVerificationReport,
    persist_policy_option_set,
    persist_policy_request_frame,
    persist_source_verification_report,
)
from tests.unit.scientist.nodes.builtins.simulate.test_run_causal_evaluation import (
    causal_recorded_output_case as _recorded_output_fixture,
)


@pytest.fixture
def real_causal_case(tmp_path, monkeypatch):
    return _recorded_output_fixture.__wrapped__(tmp_path, monkeypatch)


def test_causal_report_owner_selected_profile_reaches_candidate_body(real_causal_case):
    """Use a real MethodBackend output, without claiming guarded evaluation authority."""
    ctx, input_state, output_state, _ = real_causal_case
    store = ctx.store
    old_ref = output_state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF]
    report = load_causal_effect_report(
        ensure_ir_artifact_store(store),
        CausalEffectReportRef.model_validate(old_ref.model_dump(mode="json")),
    )
    selected = owner._persist_selected_causal_report(
        ctx,
        report,
        inputs=[
            input_ref_from_artifact_ref(input_state.observational_data_ref, role="observations")
        ],
    )
    assert selected.manifest_profile_sha256 is not None
    assert store.verify(selected).ok
    assert (
        load_causal_effect_report(
            ensure_ir_artifact_store(store),
            CausalEffectReportRef.model_validate(selected.model_dump(mode="json")),
        )
        == report
    )
    request_ref = persist_policy_request_frame(
        store,
        PolicyRequestFrame(
            request_id="synthetic", policy_question="Synthetic?", jurisdiction="synthetic"
        ),
    )
    verification_ref = persist_source_verification_report(
        store,
        SourceVerificationReport(request_id="synthetic", needs_expert_review=True),
        inputs=[input_ref_from_artifact_ref(request_ref, role="policy_request_frame")],
    )
    option_ref = persist_policy_option_set(
        store,
        PolicyOptionSet(request_id="synthetic"),
        inputs=[
            input_ref_from_artifact_ref(request_ref, role="policy_request_frame"),
            input_ref_from_artifact_ref(verification_ref, role="source_verification_report"),
        ],
    )
    state = ExperimentState(
        run_id="synthetic-causal-body",
        policy_request_ref=request_ref,
        policy_option_set_ref=option_ref,
        source_verification_report_ref=verification_ref,
        artifacts_index={ARTIFACT_CAUSAL_REPORT_REF: selected},
    )
    node = BuildVerifiedPolicyBodyNode()
    nodes = NodeRegistry()
    nodes.register(node)
    workflow = WorkflowSpec(
        workflow_id="synthetic_causal_body",
        nodes=[NodeInvocation(alias="body", node_id=node.spec.metadata.component_id)],
    )
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref

    def run_body(selected_state):
        run = RunContext.start(
            store=store, registry_bundle=registry_ref, run_id=selected_state.run_id
        )
        actual_ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
        return WorkflowExecutor(actual_ctx, nodes).execute(workflow, selected_state)

    result = run_body(state)
    assert result.report.nodes[0].status == "ok"
    body_ref = result.state.artifacts_index["verified_policy_body_ref"]
    assert (
        input_ref_from_artifact_ref(selected, role=ARTIFACT_CAUSAL_REPORT_REF)
        in store.get_manifest(body_ref).inputs
    )

    manifest = store.get_manifest(selected)
    counterfeit = ArtifactRef.model_validate(
        store.put_bytes(
            store.get_bytes(selected),
            PutOptions(
                kind=manifest.kind,
                media_type=manifest.media_type,
                schema=SchemaInfo(name="test.ForeignCausalReport", version="1.0"),
                canon=manifest.canon,
                inputs=manifest.inputs,
            ),
            return_selected_profile=True,
        ).model_dump(mode="json")
    )
    assert counterfeit.artifact_id == selected.artifact_id
    changed = state.model_copy(deep=True, update={"run_id": "synthetic-causal-body-foreign"})
    changed.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF] = counterfeit
    refused = run_body(changed)
    assert refused.report.nodes[0].status == "fail"
    assert refused.report.nodes[0].error is not None
    assert refused.report.nodes[0].error.code == "policy_body_source_invalid"
