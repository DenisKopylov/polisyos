"""A fixed restricted consumer gets live source facts, never predecessor access."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, replace

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
)
from polisyos.core.components import ComponentId
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.trinity import persist_trinity_bundle_artifact
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
from polisyos.scientist.orchestration.engine import component_identity, input_ports
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.protocol import InputAwareNodeSpec, NodeOutcome
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
from tests.unit.scientist.search.test_phase_b_policy_runtime import _candidate

_SPEC = EvaluateVerifiedPolicyPhase5Node().spec.model_copy(update={"state_writes": []})
_COMPONENT = str(_SPEC.metadata.component_id)
_SEEN: list[input_ports.VerifiedPolicyPhase5Admission] = []
_HANDLES: list[tuple[ExecutionContext, ExperimentState]] = []


class _SourceProbe:
    @property
    def spec(self) -> InputAwareNodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        selected = input_ports.read_input_port_basis(ctx, state)
        admission = input_ports.read_verified_policy_phase5_admission(ctx, state)
        assert admission.run_id == state.run_id
        assert admission.attempt_id == selected.attempt_id
        assert admission.input_state_ref == selected.input_state_ref
        assert state.params == state.inputs == {}
        assert set(state.artifacts_index) <= {
            "verified_policy_body_ref",
            "verified_policy_candidate_ref",
        }
        assert set(state.reports_index) <= {"governance_report_ref"}
        for name in ("run_manifest", "trace_path"):
            with pytest.raises(AttributeError):
                getattr(ctx.run, name)
        with pytest.raises(AttributeError):
            ctx.run.read_runtime_invocation_attempts()
        for name in ("fabric", "foundry", "lex", "memory", "prepared_skg_read", "audit"):
            assert getattr(ctx, name) is None
        for name in ("predecessor_state_ref", "store", "run", "history"):
            assert not hasattr(admission, name)
        assert admission.governance_report is None or admission.governance_status == "current"
        for ref, status in (
            (admission.body_ref, admission.body_status),
            (admission.candidate_ref, admission.candidate_status),
            (admission.governance_ref, admission.governance_status),
        ):
            if ref is None:
                continue
            if status != "current":
                with pytest.raises(input_ports.NodeInputPortError, match="read_not_selected"):
                    ctx.store.get_bytes(ref)
                continue
            assert ctx.store.get_bytes(ref)
            # Admitted source lineage is visible, but its earlier state/attempt
            # must not become an implicit CAS read capability.
            for edge in ctx.store.get_manifest(ref).inputs:
                if edge.role not in {"selected_input", "selected_attempt"}:
                    continue
                hidden = ArtifactRef(
                    artifact_id=edge.artifact_id,
                    manifest_profile_sha256=edge.manifest_profile_sha256,
                    kind="scientist.experiment_state",
                    media_type="application/json",
                )
                with pytest.raises(input_ports.NodeInputPortError, match="read_not_selected"):
                    ctx.store.get_bytes(hidden)
        changed = ExperimentState.model_validate(state.model_dump(mode="python"))
        changed.params["undeclared"] = "changed after persistence"
        with pytest.raises(input_ports.NodeInputPortError, match="port_state_changed"):
            input_ports.read_verified_policy_phase5_admission(ctx, changed)
        for unappointed in (None, object()):
            with pytest.raises(input_ports.NodeInputPortError, match="source_view_not_installed"):
                input_ports.read_verified_policy_phase5_admission(
                    replace(ctx, _verified_policy_phase5_admission_owner=unappointed), state
                )
        _SEEN.append(admission)
        _HANDLES.append((ctx, state.model_copy(deep=True)))
        if admission.governance_report is not None:
            admission.governance_report.notes.append("caller mutation is detached")
            fresh = input_ports.read_verified_policy_phase5_admission(ctx, state)
            assert fresh.governance_report is not None
            assert "caller mutation is detached" not in fresh.governance_report.notes
        return NodeOutcome(status="ok", state=state)

    async def execute_async(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        return self.execute(ctx, state)


_CHANGE_SPEC = _SPEC.model_copy(
    update={
        "metadata": _SPEC.metadata.model_copy(
            update={"component_id": ComponentId.parse("scientist.node_source_view_change@1.0.0")}
        ),
        "state_reads": [],
        "state_writes": ["params", "artifacts_index", "reports_index", "policy_option_set_ref"],
    }
)


@dataclass(frozen=True)
class _ChangeSource:
    mode: str

    def bind(self, params):
        return replace(self, mode=params.get("mode", self.mode))

    @property
    def spec(self):
        # This is an ordinary full-state predecessor, not a restricted consumer.
        from polisyos.scientist.orchestration.engine.protocol import NodeSpec

        return NodeSpec.model_validate(
            _CHANGE_SPEC.model_dump(mode="python", exclude={"input_contract"})
        )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        changed = branch_state(state, write_paths=self.spec.state_writes).state
        if self.mode.startswith("missing_"):
            role = self.mode.removeprefix("missing_")
            mapping, key = (
                (changed.reports_index, "governance_report_ref")
                if role == "governance"
                else (changed.artifacts_index, f"verified_policy_{role}_ref")
            )
            del mapping[key]
        elif self.mode == "governance_source":
            changed.params["hidden"] = "changed after governance"
        elif self.mode == "body_source":
            ref = state.policy_option_set_ref
            assert ref is not None
            manifest = ctx.store.get_manifest(ref)
            changed.policy_option_set_ref = ctx.store.put_bytes(
                ctx.store.get_bytes(ref),
                PutOptions(
                    kind=manifest.kind,
                    media_type=manifest.media_type,
                    schema=manifest.artifact_schema,
                    canon=manifest.canon,
                    inputs=[
                        *manifest.inputs,
                        input_ref_from_artifact_ref(ref, role="new_selected_occurrence"),
                    ],
                ),
                return_selected_profile=True,
            )
        elif self.mode == "predecessor_as_body":
            binding = ctx._engine_invocation
            assert binding is not None
            attempt = next(
                item
                for item in ctx.run.read_runtime_invocation_attempts()
                if item.basis.attempt_id == binding.attempt_id
            )
            changed.artifacts_index["verified_policy_body_ref"] = attempt.basis.input_state_ref
        elif self.mode == "body_helper":
            import polisyos.scientist.nodes.builtins.decide.build_verified_policy_body as body

            body._build_candidate_body = lambda *_args, **_kwargs: None
        elif self.mode == "candidate_helper":
            import polisyos.scientist.nodes.builtins.decide.select_policy_candidate as candidate

            candidate._selected_candidate = lambda *_args, **_kwargs: None
        elif self.mode in {"invalid_body_input", "different_body_input", "restore_body_input"}:
            first = next(
                item
                for item in ctx.run.read_runtime_invocation_attempts()
                if item.basis.component_id
                == str(BuildVerifiedPolicyBodyNode().spec.metadata.component_id)
                and item.outcome is not None
                and item.outcome.status == "ok"
            )
            original = ExperimentState.model_validate(
                load_core_json_artifact(ctx.store, first.basis.input_state_ref)
            )
            if self.mode == "invalid_body_input":
                changed.policy_option_set_ref = state.inputs["registry_bundle_ref"]
            elif self.mode == "different_body_input":
                assert original.policy_request_ref is not None
                assert original.source_verification_report_ref is not None
                changed.policy_option_set_ref = persist_policy_option_set(
                    ctx.store,
                    PolicyOptionSet(request_id="view", notes=["a later selected option set"]),
                    inputs=[
                        input_ref_from_artifact_ref(
                            original.policy_request_ref, role="policy_request_frame"
                        ),
                        input_ref_from_artifact_ref(
                            original.source_verification_report_ref,
                            role="source_verification_report",
                        ),
                    ],
                )
            else:
                changed.policy_option_set_ref = original.policy_option_set_ref
                changed.artifacts_index["verified_policy_body_ref"] = next(
                    ref
                    for ref in first.outcome.output_refs
                    if ref.kind == "scientist.verified_policy_body"
                )
        else:
            raise AssertionError(self.mode)
        return NodeOutcome(status="ok", state=changed)


def _case(
    tmp_path,
    monkeypatch,
    *,
    change: str,
    route: str,
    replay_body: bool = False,
    later_body_outcome: str | None = None,
):
    _SEEN.clear()
    _HANDLES.clear()
    monkeypatch.setitem(
        component_identity._OWNERS, _COMPONENT, component_identity._owner(_SourceProbe)
    )
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
            request_id="view",
            policy_question="Synthetic source view?",
            jurisdiction="synthetic",
            jurisdiction_source="policy_request_jurisdiction",
        ),
    )
    source_ref = persist_source_verification_report(
        store,
        SourceVerificationReport(request_id="view"),
        inputs=[input_ref_from_artifact_ref(request_ref, role="policy_request_frame")],
    )
    option_ref = persist_policy_option_set(
        store,
        PolicyOptionSet(request_id="view"),
        inputs=[
            input_ref_from_artifact_ref(request_ref, role="policy_request_frame"),
            input_ref_from_artifact_ref(source_ref, role="source_verification_report"),
        ],
    )
    state = ExperimentState(
        run_id=f"source-view-{change}-{route}",
        inputs={"registry_bundle_ref": registry_ref, "trinity_bundle_ref": trinity_ref},
        params={
            "policy_candidate_schema": candidate.model_dump(mode="json"),
            "hidden": {"archive": ["old-result"]},
        },
        policy_request_ref=request_ref,
        policy_option_set_ref=option_ref,
        source_verification_report_ref=source_ref,
    )
    run = RunContext.start(store, registry_ref, run_id=state.run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    registry = NodeRegistry()
    body, selected, gov = (
        BuildVerifiedPolicyBodyNode(),
        SelectPolicyCandidateNode(),
        RunGovernanceNode(),
    )
    for node in (body, selected, gov, _SourceProbe()):
        registry.register(node)
    nodes = [
        NodeInvocation(alias="body", node_id=body.spec.metadata.component_id),
        NodeInvocation(alias="candidate", node_id=selected.spec.metadata.component_id),
    ]
    dependencies = ["body", "candidate"]
    if replay_body:
        nodes.append(
            NodeInvocation(
                alias="body_again", node_id=body.spec.metadata.component_id, depends_on=dependencies
            )
        )
        dependencies = ["body_again"]
    if later_body_outcome is not None:
        registry.register(_ChangeSource("invalid_body_input"))
        nodes.extend(
            [
                NodeInvocation(
                    alias="input_change",
                    node_id=_CHANGE_SPEC.metadata.component_id,
                    depends_on=dependencies,
                    params={
                        "mode": "invalid_body_input"
                        if later_body_outcome == "failed"
                        else "different_body_input"
                    },
                ),
                NodeInvocation(
                    alias="body_later",
                    node_id=body.spec.metadata.component_id,
                    depends_on=["input_change"],
                ),
                # Recovery is independent of the deliberately failing attempt;
                # the Engine's stable order runs body_later before recovery.
                NodeInvocation(
                    alias="restore",
                    node_id=_CHANGE_SPEC.metadata.component_id,
                    depends_on=["input_change"],
                    params={"mode": "restore_body_input"},
                ),
            ]
        )
        dependencies = ["restore"]
    after_governance = change in {"missing_governance", "governance_source"}
    if change != "none" and not after_governance:
        registry.register(_ChangeSource(change))
        nodes.append(
            NodeInvocation(
                alias="change", node_id=_CHANGE_SPEC.metadata.component_id, depends_on=dependencies
            )
        )
        dependencies = ["change"]
    nodes.append(
        NodeInvocation(
            alias="governance", node_id=gov.spec.metadata.component_id, depends_on=dependencies
        )
    )
    dependencies = ["governance"]
    if after_governance:
        registry.register(_ChangeSource(change))
        nodes.append(
            NodeInvocation(
                alias="change", node_id=_CHANGE_SPEC.metadata.component_id, depends_on=dependencies
            )
        )
        dependencies = ["change"]
    nodes.append(
        NodeInvocation(alias="probe", node_id=_SPEC.metadata.component_id, depends_on=dependencies)
    )
    workflow = WorkflowSpec(
        workflow_id="source_view",
        nodes=nodes,
        error_policy="continue" if later_body_outcome is not None else "fail_fast",
    )
    result = (
        WorkflowExecutor(ctx, registry).execute(workflow, state)
        if route == "sync"
        else asyncio.run(AsyncWorkflowExecutor(ctx, registry).execute(workflow, state))
    )
    assert all(
        item.status
        == ("fail" if item.alias == "body_later" and later_body_outcome == "failed" else "ok")
        for item in result.report.nodes
    ), [(item.alias, item.status, item.error) for item in result.report.nodes]
    assert len(_SEEN) == 1
    if change != "governance_source":
        assert result.state.params["hidden"] == {"archive": ["old-result"]}
    return ctx, result, _SEEN[0]


@pytest.mark.parametrize("route", ["sync", "async"])
def test_real_source_owner_channel_exposes_only_detached_currentness(tmp_path, monkeypatch, route):
    ctx, _result, view = _case(tmp_path, monkeypatch, change="none", route=route)
    assert view.status == "current"
    assert view.body_attempt_id and view.candidate_attempt_id and view.governance_attempt_id
    consumer = ctx.run.read_runtime_invocation_attempts()[-1]
    assert consumer.basis.attempt_id == view.attempt_id
    held_context, held_input = _HANDLES[0]
    with pytest.raises(input_ports.NodeInputPortError, match="source_view_attempt_mismatch"):
        input_ports.read_verified_policy_phase5_admission(held_context, held_input)


@pytest.mark.parametrize("route", ["sync", "async"])
@pytest.mark.parametrize(
    ("change", "role", "expected"),
    [
        ("missing_body", "body", "not_established"),
        ("missing_candidate", "candidate", "not_established"),
        ("missing_governance", "governance", "not_established"),
        ("body_source", "body", "stale"),
        ("governance_source", "governance", "stale"),
        ("predecessor_as_body", "body", "not_established"),
    ],
)
def test_source_gaps_never_enroll_hidden_or_stale_cas_refs(
    tmp_path, monkeypatch, change, role, expected, route
):
    _ctx, _result, view = _case(tmp_path, monkeypatch, change=change, route=route)
    assert getattr(view, f"{role}_status") == expected
    assert view.status != "current"


@pytest.mark.parametrize("role", ["body", "candidate"])
def test_changed_producer_helper_cannot_keep_prior_source_current(tmp_path, monkeypatch, role):
    if role == "body":
        import polisyos.scientist.nodes.builtins.decide.build_verified_policy_body as module

        monkeypatch.setattr(module, "_build_candidate_body", module._build_candidate_body)
    else:
        import polisyos.scientist.nodes.builtins.decide.select_policy_candidate as module

        monkeypatch.setattr(module, "_selected_candidate", module._selected_candidate)
    _ctx, _result, view = _case(tmp_path, monkeypatch, change=f"{role}_helper", route="sync")
    assert getattr(view, f"{role}_status") == "not_established"


@pytest.mark.parametrize("route", ["sync", "async"])
def test_latest_actual_cache_replay_retains_physical_producer_lineage(tmp_path, monkeypatch, route):
    ctx, _result, view = _case(tmp_path, monkeypatch, change="none", route=route, replay_body=True)
    assert view.status == "current"
    replay = next(
        item
        for item in ctx.run.read_runtime_invocation_attempts()
        if item.basis.node_alias == "body_again"
    )
    basis = input_ports._basis_from_input(ctx.store, replay.basis.input_state_ref)
    assert basis is not None and basis.execution_kind == "cache_replay"
    assert view.body_attempt_id == replay.basis.attempt_id


@pytest.mark.parametrize(
    "definition", ["method", "helper", "wrapped_loader", "pass_method", "profile"]
)
def test_actual_phase5_refuses_changed_judge_definition_before_callback(
    tmp_path, monkeypatch, definition
):
    import polisyos.scientist.governance.passes.quality_gate_pass as quality
    import polisyos.scientist.methods.search.judge_stack as judges

    calls = []

    def counterfeit(*_args, **_kwargs):
        calls.append("unadmitted")
        raise AssertionError("changed definition ran before admission")

    if definition == "method":
        monkeypatch.setattr(judges.JudgeStack, "_structural", counterfeit)
    elif definition == "helper":
        monkeypatch.setattr(judges, "_judge_result", counterfeit)
    elif definition == "wrapped_loader":
        monkeypatch.setattr(judges, "load_quality_gate_pass_type", counterfeit)
    elif definition == "pass_method":
        monkeypatch.setattr(quality.QualityGatePass, "validate", counterfeit)
    else:
        key = next(iter(judges._STRICT_PROFILE.thresholds))
        monkeypatch.setitem(judges._STRICT_PROFILE.thresholds, key, 1_000_000.0)
    store = FileSystemCAS(tmp_path / "cas")
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(store, registry_ref, run_id="changed-judge")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    registry = NodeRegistry()
    registry.register(EvaluateVerifiedPolicyPhase5Node())
    workflow = WorkflowSpec(
        workflow_id="changed_judge",
        nodes=[NodeInvocation(alias="phase5", node_id=_SPEC.metadata.component_id)],
    )
    result = WorkflowExecutor(ctx, registry).execute(
        workflow, ExperimentState(run_id="changed-judge")
    )
    assert result.report.nodes[0].status == "fail"
    assert result.report.nodes[0].error is not None
    assert result.report.nodes[0].error.code == "node.input_port_refused"
    assert calls == []
    assert run.read_runtime_invocation_attempts() == []


def test_governance_role_revalidates_real_helper_after_success(tmp_path, monkeypatch):
    import polisyos.scientist.nodes.builtins.governance.run_governance as governance
    from polisyos.scientist.governance.report_currentness import resolve_current_governance_report

    ctx, result, view = _case(tmp_path, monkeypatch, change="none", route="sync")
    assert view.governance_status == "current"
    assert resolve_current_governance_report(ctx, result.state).is_current
    calls = []

    def counterfeit(*_args, **_kwargs):
        calls.append("changed governance helper")
        raise AssertionError("currentness must not execute the producer helper")

    monkeypatch.setattr(governance, "_run_governance_checks", counterfeit)
    current = resolve_current_governance_report(ctx, result.state)
    assert current.status == "not_established"
    assert calls == []


@pytest.mark.parametrize("later_outcome", ["failed", "successful"])
def test_an_older_current_body_cannot_replace_the_latest_selected_attempt(
    tmp_path, monkeypatch, later_outcome
):
    from polisyos.scientist.orchestration.engine.producer_currentness import (
        resolve_engine_produced_artifact,
    )

    ctx, result, view = _case(
        tmp_path, monkeypatch, change="none", route="sync", later_body_outcome=later_outcome
    )
    body = BuildVerifiedPolicyBodyNode()
    by_alias = {item.alias: item for item in result.report.nodes}
    assert by_alias["body_later"].status == ("fail" if later_outcome == "failed" else "ok")
    if later_outcome == "failed":
        assert by_alias["body_later"].error is not None
        assert by_alias["body_later"].error.code == "policy_body_source_invalid"
    assert all(by_alias[alias].status == "ok" for alias in ("restore", "governance", "probe"))
    assert len(_SEEN) == 1
    later_attempt = next(
        item
        for item in ctx.run.read_runtime_invocation_attempts()
        if item.basis.node_alias == "body_later"
    )
    assert view.body_attempt_id == later_attempt.basis.attempt_id
    assert view.body_status == ("not_established" if later_outcome == "failed" else "stale")
    assert view.body_reason_code == (
        "selected_body_latest_attempt_not_successful"
        if later_outcome == "failed"
        else "selected_body_occurrence_not_latest"
    )
    # The original physical output is independently source-current. Its later
    # superseding attempt is the actual reason the fixed view must refuse it.
    assert resolve_engine_produced_artifact(
        ctx,
        result.state,
        result.state.artifacts_index["verified_policy_body_ref"],
        expected_component_id=str(body.spec.metadata.component_id),
        expected_node_spec=body.spec,
        source_read_paths=tuple(body.spec.state_reads),
    ).is_current
