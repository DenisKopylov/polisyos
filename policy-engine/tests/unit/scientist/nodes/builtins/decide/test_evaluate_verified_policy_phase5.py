"""Real Engine-selected candidate diagnostics keep source and attempt boundaries."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
)
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.trinity import persist_trinity_bundle_artifact
from polisyos.scientist.methods.search.judge_stack import (
    load_candidate_judge_verdict,
    load_judge_verdict,
)
from polisyos.scientist.methods.search.judge_thresholds import JudgeThresholdRegistry
from polisyos.scientist.nodes.builtins.decide.build_verified_policy_body import (
    BuildVerifiedPolicyBodyNode,
)
from polisyos.scientist.nodes.builtins.decide.evaluate_verified_policy_phase5 import (
    EvaluateVerifiedPolicyPhase5Node,
)
from polisyos.scientist.nodes.builtins.decide.select_policy_candidate import (
    SelectPolicyCandidateNode,
)
from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.producer_currentness import (
    resolve_engine_produced_artifact,
)
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
from polisyos.scientist.validation.policy_verified import (
    PolicyOptionSet,
    PolicyRequestFrame,
    SourceVerificationReport,
    persist_policy_option_set,
    persist_policy_request_frame,
    persist_source_verification_report,
)
from polisyos.scientist.validation.policy_verified.phase5_candidate import (
    load_phase5_candidate_assessment,
)
from tests.unit.scientist.search.test_phase_b_policy_runtime import _candidate


def test_unappointed_phase5_cannot_call_the_judges(tmp_path, monkeypatch) -> None:
    import polisyos.scientist.nodes.builtins.decide.evaluate_verified_policy_phase5 as owner

    def forbidden(*_args, **_kwargs):
        raise AssertionError("unappointed input must not reach judges")

    monkeypatch.setattr(owner, "evaluate_phase5_candidate", forbidden)
    ctx = cast("ExecutionContext", SimpleNamespace(store=FileSystemCAS(tmp_path / "cas")))
    result = EvaluateVerifiedPolicyPhase5Node().execute(ctx, ExperimentState(run_id="unappointed"))
    assert result.status == "fail"
    assert (
        result.error is not None and result.error.code == "phase5_source_admission_not_established"
    )


_TAMPER_SPEC = NodeSpec(
    metadata=ComponentMetadata(
        component_id=ComponentId.parse("scientist.node_test_phase5_source_change@1.0.0"),
        kind=ComponentKind.SCIENTIST_NODE,
        abi_targets={"world_abi": "1.x"},
        display_name="Synthetic Phase-5 source change",
        description="Change a selected source for an Engine refusal control.",
        tags=["test"],
        capabilities=Capability.SCIENTIST_NODE,
    ),
    state_reads=["artifacts_index.verified_policy_body_ref", "params"],
    state_writes=["artifacts_index.verified_policy_body_ref", "params.synthetic_change"],
)


@dataclass(frozen=True)
class _ChangeSelectedSource:
    mode: str

    @property
    def spec(self) -> NodeSpec:
        return _TAMPER_SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        changed = branch_state(state, write_paths=_TAMPER_SPEC.state_writes).state
        if self.mode == "body_profile":
            ref = state.artifacts_index["verified_policy_body_ref"]
            manifest = ctx.store.get_manifest(ref)
            foreign = ctx.store.put_bytes(
                ctx.store.get_bytes(ref),
                PutOptions(
                    kind=manifest.kind,
                    media_type=manifest.media_type,
                    schema=manifest.artifact_schema,
                    canon=manifest.canon,
                    inputs=[
                        *manifest.inputs,
                        input_ref_from_artifact_ref(ref, role="foreign_attempt"),
                    ],
                ),
                return_selected_profile=True,
            )
            assert foreign.artifact_id == ref.artifact_id
            assert foreign.manifest_profile_sha256 != ref.manifest_profile_sha256
            changed.artifacts_index["verified_policy_body_ref"] = foreign
        else:
            changed.params["synthetic_change"] = "after governance"
        return NodeOutcome(status="ok", state=changed)


@pytest.mark.parametrize(
    "change", ["none", "body_profile", "governance_source", "phase5_cache_replay"]
)
def test_actual_engine_admits_selected_attempts_and_refuses_source_changes(
    tmp_path, monkeypatch, change: str
) -> None:
    monkeypatch.setenv("POLISYOS_SEARCH_REGISTRY_ROOT", str(tmp_path / "thresholds"))
    thresholds = JudgeThresholdRegistry()
    thresholds.record(thresholds.snapshot().entries[0])
    store = FileSystemCAS(tmp_path / "cas")
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    candidate = _candidate()
    trinity_ref = ArtifactRef.model_validate(
        persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(store), candidate.trinity_bundle
        ).model_dump(mode="json")
    )
    request_ref = persist_policy_request_frame(
        store,
        PolicyRequestFrame(
            schema_version="1.1",
            request_id="synthetic",
            policy_question="Synthetic?",
            jurisdiction="synthetic",
            jurisdiction_source="policy_request_jurisdiction",
        ),
    )
    source_ref = persist_source_verification_report(
        store,
        SourceVerificationReport(request_id="synthetic", needs_expert_review=True),
        inputs=[input_ref_from_artifact_ref(request_ref, role="policy_request_frame")],
    )
    options_ref = persist_policy_option_set(
        store,
        PolicyOptionSet(request_id="synthetic"),
        inputs=[
            input_ref_from_artifact_ref(request_ref, role="policy_request_frame"),
            input_ref_from_artifact_ref(source_ref, role="source_verification_report"),
        ],
    )
    state = ExperimentState(
        run_id=f"synthetic-phase5-{change}",
        inputs={"registry_bundle_ref": registry_ref, "trinity_bundle_ref": trinity_ref},
        params={
            "policy_candidate_schema": candidate.model_dump(mode="json"),
            "require_human_gate": True,
            "unrelated_history": {"judge_verdict": "caller-approved"},
        },
        policy_request_ref=request_ref,
        policy_option_set_ref=options_ref,
        source_verification_report_ref=source_ref,
    )
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=state.run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    body = BuildVerifiedPolicyBodyNode()
    selected = SelectPolicyCandidateNode()
    governance = RunGovernanceNode()
    phase5 = EvaluateVerifiedPolicyPhase5Node()
    registry = NodeRegistry()
    for node in (body, selected, governance, phase5):
        registry.register(node)
    nodes = [
        NodeInvocation(alias="body", node_id=body.spec.metadata.component_id),
        NodeInvocation(alias="candidate", node_id=selected.spec.metadata.component_id),
    ]
    before_governance = ["body", "candidate"]
    if change == "body_profile":
        registry.register(_ChangeSelectedSource(change))
        nodes.append(
            NodeInvocation(
                alias="change",
                node_id=_TAMPER_SPEC.metadata.component_id,
                depends_on=before_governance,
            )
        )
        before_governance = ["change"]
    nodes.append(
        NodeInvocation(
            alias="governance",
            node_id=governance.spec.metadata.component_id,
            depends_on=before_governance,
        )
    )
    before_phase5 = ["governance"]
    if change == "governance_source":
        registry.register(_ChangeSelectedSource(change))
        nodes.append(
            NodeInvocation(
                alias="change", node_id=_TAMPER_SPEC.metadata.component_id, depends_on=before_phase5
            )
        )
        before_phase5 = ["change"]
    nodes.append(
        NodeInvocation(
            alias="phase5", node_id=phase5.spec.metadata.component_id, depends_on=before_phase5
        )
    )
    if change == "phase5_cache_replay":
        nodes.append(
            NodeInvocation(
                alias="phase5_again",
                node_id=phase5.spec.metadata.component_id,
                depends_on=["phase5"],
            )
        )
    workflow = WorkflowSpec(workflow_id="synthetic_phase5_candidate", nodes=nodes)
    result = WorkflowExecutor(ctx, registry).execute(workflow, state)
    by_alias = {item.alias: item for item in result.report.nodes}
    assert by_alias["body"].status == "ok"
    assert by_alias["candidate"].status == "ok"
    assert by_alias["governance"].status == "ok"
    assert result.state.params["unrelated_history"] == {"judge_verdict": "caller-approved"}
    if change in {"body_profile", "governance_source"}:
        assert by_alias["phase5"].status == "fail"
        assert "phase5_candidate_assessment_ref" not in result.state.artifacts_index
        return
    assert by_alias["phase5"].status == "ok", by_alias["phase5"].error
    if change == "phase5_cache_replay":
        # The first assessment changed governance's full-map source projection.
        # Replaying its cached output would bypass fresh source admission.
        assert by_alias["phase5_again"].status == "fail"
    ref = result.state.artifacts_index["phase5_candidate_assessment_ref"]
    assessment = load_phase5_candidate_assessment(store, ref)
    assert assessment.status == "candidate_diagnostic" and assessment.publishable is False
    assert assessment.option_program_correspondence == "not_established"
    assert assessment.threshold_uses and assessment.validation_profiles
    judge = load_candidate_judge_verdict(store, assessment.judge_verdict_ref)
    assert len(judge.per_judge) == 6 and judge.composite_decision == "defer_to_human"
    with pytest.raises(ValueError):
        load_judge_verdict(store, assessment.judge_verdict_ref)
    assert "judge_verdict_ref" not in result.state.artifacts_index
    attempt = next(
        item for item in run.read_runtime_invocation_attempts() if item.basis.node_alias == "phase5"
    )
    assert assessment.selected_attempt_ref == attempt.basis_ref
    assert assessment.selected_input_ref == attempt.basis.input_state_ref
    assert resolve_engine_produced_artifact(
        ctx,
        result.state,
        ref,
        expected_component_id=str(phase5.spec.metadata.component_id),
        expected_node_spec=phase5.spec,
        source_read_paths=tuple(phase5.spec.state_reads),
    ).is_current
