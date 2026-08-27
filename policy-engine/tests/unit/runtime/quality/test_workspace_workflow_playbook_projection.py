from __future__ import annotations

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.pdc import OperationClass, SearchTerminalKind
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.workspace.loop import WorkspaceLoop
from polisyos.runtime.quality.workspace.workflow_playbook_projection import (
    build_workflow_playbook_registry,
    select_playbook_for_intent,
)


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
    assert causal_step.node_id == "scientist.node_run_causal_evaluation@1.2.0"
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


def test_phase2_value_advisor_receives_the_owner_design_problem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not reconstruct a shaped problem after the typed WorkspaceLoop intake."""

    problem = _design_problem(
        causal_variables=["credit_access", "firm_survival"],
        observational_data_ref="measurement-root-ref",
    )
    observed: list[object] = []

    def _select(**kwargs: object) -> dict[str, object]:
        observed.append(kwargs["problem"])
        return {"selected_method_fqn": "econometrics.panel.fixed_effects@1.0.0"}

    monkeypatch.setattr(
        "polisyos.foundry.methods.selection.select_value_method_for_problem",
        _select,
    )

    WorkspaceLoop()._phase2_state(
        workspace_id="workspace-owner-problem",
        intent=problem.to_workspace_intent(),
        design_problem=problem,
    )

    assert observed == [problem]


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
    assert [blocker.blocker_id for blocker in result.search_blockers] == [
        "blocker-missing-bound"
    ]
    assert result.terminal_state.blocking_obligations == [
        "blocker-missing-bound"
    ]
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
