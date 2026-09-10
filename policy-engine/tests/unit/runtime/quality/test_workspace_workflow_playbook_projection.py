from __future__ import annotations

from types import SimpleNamespace

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.pdc import OperationClass, SearchTerminalKind
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.workspace.loop import WorkspaceLoop
from polisyos.runtime.quality.workspace.workflow_playbook_projection import (
    PlaybookStep,
    _step_from_invocation,
    admit_playbook_step,
    build_workflow_playbook_registry,
    select_playbook_for_intent,
)


def test_unexecuted_nonproducing_node_is_not_an_admitted_playbook_step() -> None:
    """The census counterexample cannot enter the executable step population."""
    from tests.unit.runtime.quality.test_workspace_scientist_node_adapters import _node

    node = _node()
    invocation = SimpleNamespace(
        alias="run_causal_evaluation",
        node_id=node.spec.metadata.component_id,
    )
    registry = SimpleNamespace(get=lambda node_id: node)

    description = _step_from_invocation(
        workflow_id="c1-census-counterexample",
        invocation=invocation,
        node_registry=registry,
    )

    assert not isinstance(description, PlaybookStep), (
        "A declared-but-unproduced output was admitted without real-input conformance."
    )


def _admission_candidate(node):
    registry = SimpleNamespace(get=lambda node_id: node)
    candidate = _step_from_invocation(
        workflow_id="c1-census-counterexample",
        invocation=SimpleNamespace(
            alias="run_causal_evaluation",
            node_id=node.spec.metadata.component_id,
        ),
        node_registry=registry,
    )
    return candidate, registry


def test_playbook_admission_requires_produced_output_and_reuses_checked_execution(tmp_path):
    from tests.unit.runtime.quality.test_workspace_scientist_node_adapters import (
        _node,
        _ProducingNode,
        _station,
    )

    ctx, state = _station(tmp_path)
    original = state.model_dump(mode="json")
    for node, expected in ((_node(), False), (_ProducingNode(_node().spec), True)):
        candidate, registry = _admission_candidate(node)
        admission = admit_playbook_step(
            candidate,
            node_registry=registry,
            ctx=ctx,
            state=state,
            workspace_id="ws-c1",
            invocation_id="invoke-c1",
            cycle_index=1,
        )
        assert admission.conformance.passed is expected
        assert (admission.step is not None) is expected
        assert admission.smoke_attempted is True
        assert state.model_dump(mode="json") == original
        if expected:
            assert admission.step.conformance.execution is admission.conformance.execution
            assert admission.conformance.node_spec_hash == candidate.node_spec_hash
            assert admission.conformance.contract_hash == candidate.adapter_contract_hash
        else:
            assert admission.blocker is not None
            assert "output_not_preserved:causal_report_ref" in admission.conformance.failures
    assert ctx.calls == ["execute"]


def test_playbook_admission_rechecks_current_node_signature_before_smoke(tmp_path):
    from tests.unit.runtime.quality.test_workspace_scientist_node_adapters import (
        _node,
        _ProducingNode,
        _station,
    )

    node = _ProducingNode(_node().spec)
    candidate, _ = _admission_candidate(node)
    replacement = _ProducingNode(node.spec.model_copy(update={"produces": ["new_output"]}))
    ctx, state = _station(tmp_path)
    admission = admit_playbook_step(
        candidate,
        node_registry=SimpleNamespace(get=lambda node_id: replacement),
        ctx=ctx,
        state=state,
        workspace_id="ws-c1",
        invocation_id="invoke-c1",
        cycle_index=1,
    )
    assert admission.step is None
    assert admission.conformance.failures == ["node_signature_changed"]
    assert admission.smoke_attempted is False
    assert ctx.calls == []


def test_playbook_admission_refuses_node_removed_after_selection(tmp_path):
    from polisyos.scientist.orchestration.engine.errors import UnknownNodeError
    from tests.unit.runtime.quality.test_workspace_scientist_node_adapters import _node, _station

    candidate, _ = _admission_candidate(_node())

    def missing(node_id):
        raise UnknownNodeError("removed")

    ctx, state = _station(tmp_path)
    admission = admit_playbook_step(
        candidate,
        node_registry=SimpleNamespace(get=missing),
        ctx=ctx,
        state=state,
        workspace_id="ws-c1",
        invocation_id="invoke-c1",
        cycle_index=1,
    )
    assert admission.step is None
    assert admission.conformance.failures == ["node_signature_unavailable:UnknownNodeError"]
    assert ctx.calls == []


def test_playbook_admission_binds_full_signature_of_the_completed_smoke(tmp_path):
    from tests.unit.runtime.quality.test_workspace_scientist_node_adapters import (
        _node,
        _ProducingNode,
        _station,
    )

    class ChangedSpecNode:
        def __init__(self):
            self.original = _node().spec
            self.changed = self.original.model_copy(
                update={"state_writes": [*self.original.state_writes, "params.after_discovery"]},
            )
            self.armed = False
            self.reads = 0

        @property
        def spec(self):
            if self.armed:
                self.reads += 1
            return self.changed if self.armed and self.reads >= 3 else self.original

        def execute(self, ctx, state):
            outcome = _ProducingNode(self.changed).execute(ctx, state)
            outcome.state.params["after_discovery"] = "changed signature executed"
            return outcome

    node = ChangedSpecNode()
    candidate, registry = _admission_candidate(node)
    node.armed = True
    ctx, state = _station(tmp_path)
    admission = admit_playbook_step(
        candidate,
        node_registry=registry,
        ctx=ctx,
        state=state,
        workspace_id="ws-c1",
        invocation_id="invoke-c1",
        cycle_index=1,
    )
    assert (
        admission.conformance.passed is True
    )  # The actual smoke succeeded under a different spec.
    assert admission.conformance.node_spec_hash != candidate.node_spec_hash
    assert admission.conformance.contract_hash == candidate.adapter_contract_hash
    assert admission.step is None
    assert "conformance_node_signature_mismatch" in admission.blocker.reason
    assert "after_discovery" not in state.params
    assert ctx.calls == ["execute"]


def test_loop_refuses_nonproducing_node_before_operation_or_foundry_consumption(
    tmp_path,
    monkeypatch,
):
    from polisyos.runtime.quality.workspace import loop as loop_module
    from polisyos.runtime.quality.workspace import workflow_playbook_projection as projection
    from polisyos.runtime.quality.workspace.workflow_playbook_projection import (
        PlaybookRegistry,
        PlaybookTrajectory,
    )
    from tests.unit.runtime.quality.test_workspace_scientist_node_adapters import _node, _station

    ctx, state = _station(tmp_path)
    state.params["data_causal_graph"] = {"x": ["y"]}
    candidate, registry = _admission_candidate(_node())
    playbook_id = "scientist_causal_full"
    playbooks = PlaybookRegistry(
        playbooks={
            playbook_id: PlaybookTrajectory(
                playbook_id=playbook_id,
                source_workflow_id=playbook_id,
                default_operation_classes=[OperationClass.ESTIMATE],
                steps=[candidate],
                authority_path_disposition="loop_only",
            )
        }
    )
    monkeypatch.setattr(WorkspaceLoop, "_phase2_context", lambda self, **kwargs: (ctx, None))
    monkeypatch.setattr(WorkspaceLoop, "_phase2_state", lambda self, **kwargs: state)
    monkeypatch.setattr(loop_module, "build_registry_with_builtin_nodes", lambda **kwargs: registry)
    monkeypatch.setattr(loop_module, "build_workflow_playbook_registry", lambda **kwargs: playbooks)
    monkeypatch.setattr(projection, "build_workflow_playbook_registry", lambda **kwargs: playbooks)
    consumed = []

    def consumer_escape(self, **kwargs):
        consumed.append(kwargs)
        raise AssertionError("An unverified adapter output reached Foundry consumption")

    monkeypatch.setattr(
        loop_module.FoundryMethodOutputConsumer, "consume_from_state", consumer_escape
    )
    result = WorkspaceLoop(artifact_store=ctx.store).run_intent(
        _design_problem(causal_variables=["x", "y"]),
    )
    assert result.terminal_state.kind == SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED
    assert result.operation_invocations == []
    assert result.search_ledger_events == []
    assert result.artifact_envelopes == []
    assert consumed == []
    assert result.adapter_admissions[0].conformance.passed is False
    assert result.adapter_admissions[0].smoke_attempted is True
    assert result.phase2_playbook_trace.executed_legacy_aliases == []


def _design_problem(
    *,
    policy_question: str = "Estimate a causal policy effect.",
    causal_variables: list[str] | None = None,
    observational_data_ref: str | None = None,
    force_counterexample: str | None = None,
    verification_required: bool = False,
) -> DesignProblem:
    treatment = (causal_variables or ["credit_access", "firm_survival"])[0]
    outcome = (causal_variables or ["credit_access", "firm_survival"])[1]
    runtime_hints: dict[str, object] = {"verification_required": verification_required}
    if observational_data_ref is not None:
        runtime_hints["observational_data_ref"] = observational_data_ref
    if force_counterexample is not None:
        runtime_hints["force_counterexample"] = force_counterexample
    return DesignProblem.model_validate(
        {
            "design_problem_id": "design_problem_phase2_credit",
            "problem_statement": policy_question,
            "domain": "social",
            "nl_provenance": {
                "raw_request": policy_question,
                "source_surface": "unit.test",
                "source_context": {"run_id": "run-phase2"},
            },
            "authority_profile": {
                "requester_authority": "research",
                "requested_authority_level": "research",
                "mandate": "Phase-2 test mandate.",
            },
            "jurisdiction_time": {
                "region": "UA",
                "valid_time": "2026-05-15",
                "as_of": "2026-05-12",
                "policy_time": "2026-05-15",
                "data_time": "2024-2026",
            },
            "objectives": [
                {
                    "objective_id": "estimate_effect",
                    "description": "Estimate the causal effect.",
                    "metric_id": outcome,
                    "direction": "maximize",
                }
            ],
            "constraints": [],
            "stakeholders": [
                {"stakeholder_id": "wartime_msmes", "name": "wartime MSMEs", "role": "beneficiary"}
            ],
            "outcome_of_interest": {
                "target_variable": outcome,
                "metric_id": outcome,
                "estimand": f"P({outcome} | do({treatment}))",
                "direction": "maximize",
            },
            "candidate_lever_space": {
                "allowed_operator_kinds": ["credit_access"],
                "candidate_levers": [
                    {
                        "lever_id": "credit_access",
                        "operator_kind": "credit_access",
                        "instrument": "credit support",
                        "target_slot": treatment,
                    }
                ],
            },
            "evidence_acquisition_needs": {"needs": []},
            "runtime_hints": runtime_hints,
        }
    )


def test_phase2_playbook_registry_projects_three_serious_workflows() -> None:
    registry = build_workflow_playbook_registry()

    assert set(registry.playbooks) == {
        "scientist_policy_design",
        "scientist_causal_full",
        "scientist_policy_verified",
    }
    assert registry.playbooks["scientist_policy_design"].default_operation_classes[0] == (
        OperationClass.BIND
    )
    assert "run_normative_arbitration" in {
        step.legacy_alias for step in registry.playbooks["scientist_causal_full"].steps
    }
    causal_step = next(
        step
        for step in registry.playbooks["scientist_causal_full"].steps
        if step.legacy_alias == "run_causal_evaluation"
    )
    assert causal_step.source_workflow_id == "scientist_causal_full"
    assert causal_step.node_id == "scientist.node_run_causal_evaluation@2.0.0"
    assert causal_step.adapter_id.startswith("adapter-")


def test_intent_router_ignores_workflow_id_for_authority_selection() -> None:
    selected = select_playbook_for_intent(
        {
            "policy_question": "Can Ukraine offer MSME credit guarantees?",
            "workflow_id": "scientist_discovery",
        }
    )

    assert selected.playbook_id == "scientist_policy_design"
    assert selected.selection_source == "intent"
    assert selected.legacy_workflow_id_disposition == "legacy_shadow_context"


def test_workspace_loop_rejects_untyped_dict_entry() -> None:
    with pytest.raises(TypeError, match="DesignProblem"):
        WorkspaceLoop().run_intent({"policy_question": "Estimate a causal policy effect."})  # type: ignore[arg-type]


def test_phase2_contract_selector_receives_the_owner_design_problem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep the whole admitted problem in candidate-selection context."""
    from polisyos.runtime.quality.workspace import loop as owner

    problem = _design_problem(causal_variables=["credit_access", "firm_survival"])
    observed: list[object] = []

    def select(**kwargs):
        observed.append(kwargs["selection_context"]["design_problem"])
        return SimpleNamespace(model_dump=lambda **options: {"status": "blocked"})

    monkeypatch.setattr("polisyos.foundry.select_method_for_input_contract", select)
    owner._phase2_value_method_selection(problem.to_workspace_intent(), design_problem=problem)
    assert observed == [problem.model_dump(mode="json")]


def test_phase2_state_carries_the_real_recorded_binding_without_faking_stage_intake(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from polisyos.runtime.quality.workspace import loop as owner

    problem = _design_problem(causal_variables=["credit_access", "firm_survival"])
    observed: list[dict[str, object]] = []
    original = owner.WorkspaceLoop._phase2_observational_data_ref

    def produce(**kwargs: object) -> object:
        observed.append(kwargs)
        root = original(owner.WorkspaceLoop(), intent={"observational_data_ref": "probe"})
        return SimpleNamespace(observational_data_ref=root, binding_receipt_ref=root)

    monkeypatch.setattr(owner, "produce_recorded_panel_method_input", produce, raising=False)
    monkeypatch.setattr(owner, "_phase2_value_method_selection", lambda *a, **k: {
        "status": "selected", "input_contract_id": "foundry.causal.panel_observational_data.v1",
        "required_output_slots": ["report"],
        "selected_method_fqn": "causal.inference.synthetic_control@2.0.0",
        "denominator_established": True,
        "denominator": ["causal.inference.synthetic_control@2.0.0"],
        "candidates": [{"method_fqn": "causal.inference.synthetic_control@2.0.0", "disposition": "eligible"}],
        "ranked_method_fqns": ["causal.inference.synthetic_control@2.0.0"],
        "context_content_hash": "sha256:" + "3" * 64,
    })
    state = WorkspaceLoop()._phase2_state(
        workspace_id="binding-transport", intent=problem.to_workspace_intent(),
        design_problem=problem,
    )
    assert len(observed) == 1
    assert observed[0]["method_fqn"] == state.causal_method_fqn
    assert state.artifacts_index["foundry_input_binding_receipt_ref"] == state.observational_data_ref
    assert "ukraine_foundry_intake_receipt_ref" not in state.artifacts_index


def test_phase2_recorded_binding_refusal_is_a_typed_terminal(monkeypatch) -> None:
    from polisyos.runtime.quality.data_forge_binding import MeasurementRootBindingError

    def refuse(*args, **kwargs):
        raise MeasurementRootBindingError("selected.method: recorded_input_method_contract_incompatible")

    monkeypatch.setattr(WorkspaceLoop, "_phase2_context", lambda *a, **k: (None, None))
    monkeypatch.setattr(WorkspaceLoop, "_phase2_state", refuse)
    result = WorkspaceLoop().run_intent(_design_problem())
    assert result.terminal_state.kind is SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED
    assert result.authority_boundary is None
    assert result.operation_invocations == []
    assert result.search_blockers[0].producer_missing_label == "verification_missing"
    assert "recorded_input_method_contract_incompatible" in result.search_blockers[0].reason


def test_workspace_loop_phase2_playbook_can_deviate_to_refine_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation_calls: list[object] = []

    def _unexpected_s2_operation(**kwargs: object) -> None:
        operation_calls.append(kwargs)

    monkeypatch.setattr(
        "polisyos.runtime.quality.workspace.s2_design_search_operation."
        "execute_s2_design_search_operation",
        _unexpected_s2_operation,
    )
    result = WorkspaceLoop().run_intent(
        _design_problem(
            causal_variables=["credit_access", "firm_survival"],
            force_counterexample="missing_bounds",
        )
    )

    assert result.terminal_state.kind == SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED
    assert result.phase2_playbook_trace is not None
    assert result.phase2_playbook_trace.deviated_from_default is True
    assert result.phase2_playbook_trace.deviation_operation == OperationClass.REFINE
    assert [blocker.blocker_id for blocker in result.search_blockers] == ["blocker-missing-bound"]
    assert result.terminal_state.blocking_obligations == ["blocker-missing-bound"]
    assert result.phase2_playbook_trace.deviation_reason == "counterexample_missing_bounds"
    assert operation_calls == []


def test_workspace_loop_phase2_executes_real_adapter_event_on_stable_path() -> None:
    result = WorkspaceLoop().run_intent(
        _design_problem(
            causal_variables=["credit_access", "firm_survival"],
            observational_data_ref="measurement-root-ref",
        )
    )

    assert result.terminal_state.kind == SearchTerminalKind.FRONTIER_STABLE
    assert result.operation_invocations
    assert result.search_ledger_events
    assert result.artifact_envelopes
    assert {
        invocation.internal_trace["legacy_alias"] for invocation in result.operation_invocations
    } >= {"run_causal_evaluation", "run_normative_arbitration"}
    assert all(envelope.lifecycle_state == "shadow" for envelope in result.artifact_envelopes)


def test_workspace_loop_phase2_default_consumes_recorded_measurement_root(tmp_path) -> None:
    result = WorkspaceLoop(artifact_store=FileSystemCAS(tmp_path)).run_intent(
        _design_problem(
            causal_variables=["credit_access", "firm_survival"],
            verification_required=True,
        )
    )

    assert result.terminal_state.kind == SearchTerminalKind.FRONTIER_STABLE
    assert result.search_blockers == []
    assert result.foundry_input_provenance == "measurement_rooted"
    assert result.authority_boundary is not None
    assert result.authority_boundary.evidence_kind == "measurement"
    assert result.method_output_consumption_record is not None
    assert result.method_output_consumption_record.measurement_root_refs
    assert result.method_output_consumption_record.consumed_method_output_refs
    assert result.phase2_playbook_trace is not None
    assert set(result.phase2_playbook_trace.executed_legacy_aliases) >= {
        "run_causal_evaluation",
        "run_normative_arbitration",
    }


def test_workspace_loop_phase2_synthetic_probe_stays_separate_simulation(tmp_path) -> None:
    result = WorkspaceLoop(artifact_store=FileSystemCAS(tmp_path)).run_intent(
        _design_problem(
            causal_variables=["credit_access", "firm_survival"],
            observational_data_ref="validator-synthetic-probe",
        )
    )

    assert result.authority_boundary is not None
    assert result.foundry_input_provenance == "synthetic_probe"
    assert result.authority_boundary.evidence_kind == "simulation"
    assert result.method_output_consumption_record is not None
    assert result.method_output_consumption_record.measurement_root_refs == []


def test_workspace_loop_phase2_synthetic_probe_cannot_claim_measurement_authority() -> None:
    result = WorkspaceLoop().run_intent(
        _design_problem(
            causal_variables=["credit_access", "firm_survival"],
            observational_data_ref="validator-measurement-root",
        )
    )

    assert result.authority_boundary is not None
    assert result.authority_boundary.evidence_kind == "simulation"
    assert "measurement_rooted_authority" in result.authority_boundary.may_not_use_for
    assert result.method_output_consumption_record is not None
    assert result.method_output_consumption_record.measurement_root_refs == []
    assert result.authority_boundary.evidence_basis is not None
    assert (
        result.authority_boundary.evidence_basis.producer_roots[0].artifact_type
        == "SyntheticObservationInput"
    )


@pytest.mark.parametrize("emit_unrelated_artifact", [False, True])
def test_playbook_admission_does_not_reuse_prior_output_as_current_production(
    tmp_path, emit_unrelated_artifact
):
    """A real prior CAS value is insufficient when this invocation did not emit it."""
    from polisyos.core.artifacts import PutOptions
    from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
    from tests.unit.runtime.quality.test_workspace_scientist_node_adapters import (
        _FakeNode,
        _node,
        _station,
    )

    class RetainingNonproducer(_FakeNode):
        def execute(self, ctx, state):
            ctx.calls.append("execute")
            current = []
            if emit_unrelated_artifact:
                current.append(ctx.store.put_json(
                    {"unrelated": "current invocation emitted this"},
                    PutOptions(kind="ir.unrelated", media_type="application/json"),
                ))
            return NodeOutcome(status="ok", state=state, artifacts=current)

    ctx, state = _station(tmp_path)
    node = RetainingNonproducer(_node().spec)
    # Derive the full controlled contract, never a sampled output key.
    prior_refs = {
        key: ctx.store.put_json(
            {"output_key": key, "origin": "prior invocation"},
            PutOptions(kind="ir.prior_output", media_type="application/json"),
        )
        for key in node.spec.produces
    }
    state.artifacts_index.update(prior_refs)
    before = state.model_dump(mode="json")
    candidate, registry = _admission_candidate(node)
    admission = admit_playbook_step(
        candidate,
        node_registry=registry,
        ctx=ctx,
        state=state,
        workspace_id="ws-current-attempt",
        invocation_id="invoke-current-attempt",
        cycle_index=2,
    )
    assert admission.conformance.smoke_attempted is True
    assert ctx.calls == ["execute"]
    assert state.model_dump(mode="json") == before
    assert admission.step is None, admission.conformance.model_dump(mode="json")
    assert admission.conformance.passed is False
    failures = set(admission.conformance.failures)
    assert {
        f"output_not_emitted_current_attempt:{key}" for key in node.spec.produces
    } <= failures


def test_phase2_explicit_causal_method_uses_contract_route_not_value_population() -> None:
    """Old helper rejects this real Panel causal method at N8's value boundary."""
    from polisyos.runtime.quality.workspace import loop as owner

    problem_payload = _design_problem().model_dump(mode="json")
    problem_payload["runtime_hints"]["causal_method_fqn"] = "causal.inference.synthetic_control@2.0.0"
    problem = DesignProblem.model_validate(problem_payload)
    result = owner._phase2_value_method_selection(
        problem.to_workspace_intent(), design_problem=problem,
    )
    assert result["status"] == "selected", result
    assert result["selected_method_fqn"] == "causal.inference.synthetic_control@2.0.0"


def test_phase2_default_method_accepts_actual_recorded_input_and_report_port() -> None:
    """Selection must fit the actual recorded owner, not merely be a value method."""
    from polisyos.foundry import method_accepts_input_contract
    from polisyos.foundry.methods import MethodRegistry
    from polisyos.runtime.quality.workspace import loop as owner

    problem = _design_problem()
    result = owner._phase2_value_method_selection(
        problem.to_workspace_intent(), design_problem=problem,
    )
    assert result["status"] == "selected", result
    method = MethodRegistry.get_instance().get(result["selected_method_fqn"])
    assert method_accepts_input_contract(method, "foundry.causal.panel_observational_data.v1"), result
    assert "report" in {slot.name for slot in method.signature.output_slots}, result


def test_phase2_selection_refusal_stops_before_binding_and_retains_result(monkeypatch) -> None:
    from polisyos.runtime.quality.data_forge_binding import MeasurementRootBindingError
    from polisyos.runtime.quality.workspace import loop as owner

    refusal = {
        "status": "blocked", "input_contract_id": "foundry.causal.panel_observational_data.v1",
        "required_output_slots": ["report"], "selected_method_fqn": None,
        "denominator_established": True, "denominator": [], "candidates": [],
        "context_content_hash": "sha256:" + "3" * 64,
        "blockers": ["input_contract_method_no_eligible_candidate"],
    }
    monkeypatch.setattr(owner, "_phase2_value_method_selection", lambda *a, **k: refusal)

    def forbidden_binding(**kwargs):
        raise AssertionError(f"binding called after typed refusal: {kwargs['method_fqn']!r}")

    monkeypatch.setattr(owner, "produce_recorded_panel_method_input", forbidden_binding)
    problem = _design_problem()
    with pytest.raises(MeasurementRootBindingError) as caught:
        WorkspaceLoop()._phase2_state(
            workspace_id="refused-selection", intent=problem.to_workspace_intent(),
            design_problem=problem,
        )
    receipt = caught.value.selection
    assert receipt.selected_method_fqn is None
    assert receipt.blockers == tuple(refusal["blockers"])


@pytest.mark.parametrize("supplied", [None, "unbound-observation-marker"])
def test_phase2_supplied_observation_without_contract_is_not_recorded_default(monkeypatch, supplied) -> None:
    from polisyos.runtime.quality.data_forge_binding import MeasurementRootBindingError
    from polisyos.runtime.quality.workspace import loop as owner

    def forbidden_default(*args, **kwargs):
        raise AssertionError("supplied input was silently replaced with the recorded/synthetic default")

    monkeypatch.setattr(owner, "produce_recorded_panel_method_input", forbidden_default)
    monkeypatch.setattr(WorkspaceLoop, "_phase2_observational_data_ref", forbidden_default)
    problem_payload = _design_problem().model_dump(mode="json")
    problem_payload["runtime_hints"]["observational_data_ref"] = supplied
    problem = DesignProblem.model_validate(problem_payload)
    with pytest.raises(MeasurementRootBindingError, match="supplied_observation"):
        WorkspaceLoop()._phase2_state(
            workspace_id="unbound-input", intent=problem.to_workspace_intent(),
            design_problem=problem,
        )
