"""Exercise a changed candidate input after a blocked scientific frontier."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.integration.core_runtime.test_candidate_experiment_action_served import (
    run_candidate_experiment_action_oracle,
    run_genuine_candidate_experiment_scenario,
)
from tests.integration.core_runtime.test_candidate_experiment_generations_served import (
    _assert_changed_candidate_n5_numeric_outcomes,
)

pytest_plugins = ("tests._helpers.acquisition_served_history",)


def test_changed_input_detector_distinguishes_seed_and_other_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The source scalar alone cannot decide whether the numeric request changed."""
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.quality.acquisition_evaluation import ResolvedAcquisitionEvaluation
    from polisyos.runtime.quality.candidate_source_basis import (
        candidate_experiment_input_changed,
        prepare_candidate_source_basis_values,
    )
    from tests.unit.runtime.quality.test_candidate_acquisition_world import CELL_ID, TENANT_ID
    from tests.unit.runtime.quality.test_candidate_source_basis import (
        _case_with_explicit_empty_prior,
        _inputs,
    )

    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = _case_with_explicit_empty_prior(tmp_path, monkeypatch)
        prepared = prepare_candidate_source_basis_values(
            store=case.store, problem=case.problem, inputs=_inputs(case)
        )
        model = prepared.prospective_model
        assert model is not None
        declared_values = model.declared_model_values
        declaration = model.original_declaration.model_copy(
            update={
                "target_baseline": declared_values.target_baseline,
                "outcome_baseline": declared_values.outcome_baseline,
            }
        )
        prior = ResolvedAcquisitionEvaluation(
            selected=None,
            source=None,
            input_record=SimpleNamespace(
                n5=model.n5_config, profile=SimpleNamespace(rule=model.rule)
            ),
            execution=None,
            result=None,
            handoff=SimpleNamespace(model_declaration=declaration),
        )
        source = case.source_case.source

        def changed(candidate: object) -> bool:
            return candidate_experiment_input_changed(
                prior=prior, previous_source=source, current_source=source, prepared=candidate
            )

        assert changed(prepared) is False
        changed_seed = model.n5_config.model_copy(update={"seed": model.n5_config.seed + 1})
        assert changed(replace(prepared, prospective_model=replace(model, n5_config=changed_seed)))
        baseline = dict(model.n5_config.baseline_state)
        baseline["government.balance"] += 1.0
        changed_baseline = model.n5_config.model_copy(update={"baseline_state": baseline})
        assert changed(
            replace(prepared, prospective_model=replace(model, n5_config=changed_baseline))
        )
        changed_declaration = replace(
            declared_values, outcome_per_target_unit=declared_values.outcome_per_target_unit * 2
        )
        assert changed(
            replace(
                prepared,
                prospective_model=replace(model, declared_model_values=changed_declaration),
            )
        )


def test_changed_source_after_blocked_candidate_executes_new_n5(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway: object,
) -> None:
    """B remains candidate-only while C uses a different selected world and N5."""
    from polisyos.runtime.quality.acquisition_evaluation_history import (
        verify_candidate_experiment_terminal_history,
    )
    from tests._helpers.candidate_experiment_served_execution import (
        run_candidate_experiment_served_execution,
    )
    from tests.integration.core_runtime.test_candidate_experiment_generations_served import (
        _forbid_retained_generation_n5,
    )

    observed: dict[str, object] = {}

    def after_first_execution(**first_values: object) -> None:
        first = first_values["execution"]
        first_history = first.terminal_history
        quota = first_values["quota"]
        assert (quota.total_units, quota.protected_units) == (7, 1)
        assert first.standard_invocation_units_before == 2
        assert first.standard_invocation_units_after == 4
        assert first_history.terminal.selected_evaluation is None
        assert first_history.selected_basis.basis_role == "blocked"
        assert first_history.selected_basis.predicate_provenance == "not_established"
        assert first_history.reentry_evaluation is not None
        assert first_history.frontier_before is first_history.frontier_after is None
        assert first.current_action.evaluation_disposition == "blocked"
        assert first.current_action.candidate_n5_result is not None

        def execute_same(**action_values: object) -> None:
            with _forbid_retained_generation_n5() as n5_entries:
                same = run_candidate_experiment_served_execution(
                    values=action_values["values"],
                    origin=action_values["origin"],
                    request=action_values["request"],
                    decision_ref=action_values["decision_ref"],
                    policy_owner=first_values["policy_owner"],
                    monkeypatch=monkeypatch,
                )
            assert n5_entries == []
            assert (
                same.standard_invocation_units_before == same.standard_invocation_units_after == 4
            )
            assert same.terminal_history.terminal.terminal_outcome == "candidate_blocked"
            assert same.terminal_history.terminal.blocker_reason == (
                "candidate_experiment_input_change_not_established"
            )
            assert same.terminal_history.terminal.selected_evaluation is None
            assert (
                same.terminal_history.frontier_before
                is same.terminal_history.frontier_after
                is None
            )
            assert same.current_action.status == "blocked"
            assert same.current_action.candidate_n5_result is None
            prior_result = same.current_action.prior_candidate_n5_result
            assert prior_result is not None
            assert prior_result.prior_action_ref == first_history.terminal.candidate_action_ref
            assert prior_result.prior_action_generation == first_history.head.action_generation
            assert prior_result.n5_result.terminal_receipt_ref == first.terminal_ref
            assert (
                prior_result.n5_result.reentry_receipt_ref
                == first_history.terminal.candidate_reentry_ref
            )
            assert prior_result.n5_result.result_body.artifact_ref == (
                first_history.reentry_evaluation.selected.n5_result_ref
            )
            assert same.current_action.selected_receipt_ref == same.terminal_ref
            observed["same"] = same

        run_candidate_experiment_action_oracle(
            tmp_path=tmp_path / "candidate-same",
            values=first_values["values"],
            policy_ref=first_values["policy_ref"],
            monkeypatch=monkeypatch,
            idempotency_key="served-blocked-candidate-same-source",
            exercise_controls=False,
            after_replay=execute_same,
        )

        def execute_changed(**action_values: object) -> None:
            changed = run_candidate_experiment_served_execution(
                values=action_values["values"],
                origin=action_values["origin"],
                request=action_values["request"],
                decision_ref=action_values["decision_ref"],
                policy_owner=first_values["policy_owner"],
                monkeypatch=monkeypatch,
                wdi_response_value=21.0,
            )
            changed_history = changed.terminal_history
            assert changed.standard_invocation_units_before == 4
            assert changed.standard_invocation_units_after == 6
            assert changed_history.origin.candidate_terminal_history_chain == (
                first_history,
                observed["same"].terminal_history,
            )
            assert changed_history.decision.comparison_result == "not_established"
            assert changed_history.decision.predicate_provenance == "not_established"
            assert changed_history.terminal.selected_evaluation is None
            assert changed_history.selected_basis.basis_role == "blocked"
            assert changed_history.frontier_before is changed_history.frontier_after is None
            assert changed_history.reentry_evaluation is not None
            assert changed.current_action.evaluation_disposition == "blocked"
            assert changed.current_action.candidate_n5_result is not None
            assert changed.current_action.candidate_n5_result.publication_authority is False

            previous = first_history.reentry_evaluation
            current = changed_history.reentry_evaluation
            slot = changed_history.action.selection.target_slot_id
            assert slot == first_history.action.selection.target_slot_id
            assert slot == "global.unemployment_rate"
            assert previous.input_record.n5.baseline_state[slot] == pytest.approx(0.175)
            assert current.input_record.n5.baseline_state[slot] == pytest.approx(0.21)
            assert current.selected.n5_input_ref != previous.selected.n5_input_ref
            assert current.selected.n5_execution_ref != previous.selected.n5_execution_ref
            assert current.selected.n5_result_ref != previous.selected.n5_result_ref
            _assert_changed_candidate_n5_numeric_outcomes(
                control=first_values["control"], first=first, changed=changed, allow_blocked=True
            )
            for execution in (first, observed["same"], changed):
                replayed = verify_candidate_experiment_terminal_history(
                    control_service=first_values["control"],
                    head=execution.terminal_history.head,
                    terminal_ref=execution.terminal_ref,
                )
                assert replayed == execution.terminal_history
            observed["changed"] = changed

        run_candidate_experiment_action_oracle(
            tmp_path=tmp_path / "candidate-changed",
            values=first_values["values"],
            policy_ref=first_values["policy_ref"],
            monkeypatch=monkeypatch,
            idempotency_key="served-blocked-candidate-changed-source",
            exercise_controls=False,
            after_replay=execute_changed,
        )

    scenario = run_genuine_candidate_experiment_scenario(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        gateway=served_recorded_candidate_gateway,
        total_units=7,
        expected_blocked=True,
        after_execution=after_first_execution,
    )
    assert scenario["source_status"] == "completed"
    assert "changed" in observed
