"""Served candidate experiments retain equivalent evaluations and advance changed bases."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

pytest_plugins = ("tests._helpers.acquisition_served_history",)


def test_genuine_candidate_experiment_generations_retain_then_advance_frontier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway,
) -> None:
    """Run A→B→B→B→C through fresh signed decisions and the real served worker."""
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
    )
    from tests._helpers.candidate_experiment_served_execution import (
        _standard_invocation_units,
        candidate_experiment_served_execution_owner,
        run_candidate_experiment_served_execution,
    )
    from tests.integration.core_runtime.test_candidate_experiment_action_served import (
        run_candidate_experiment_action_oracle,
        run_genuine_candidate_experiment_scenario,
    )

    observed: dict[str, object] = {}

    def after_first_execution(**first_values: object) -> None:
        from polisyos.runtime.quality.acquisition_evaluation_history import (
            verify_candidate_experiment_terminal_history,
        )

        first = first_values["execution"]
        values = first_values["values"]
        policy_ref = first_values["policy_ref"]
        policy_owner = first_values["policy_owner"]
        policy = first_values["policy"]
        origin = first_values["origin"]
        quota = first_values["quota"]

        assert first.standard_invocation_units_before == 2
        assert first.standard_invocation_units_after == 4
        assert quota.total_units == 7
        assert quota.protected_units == 1
        assert policy_owner.template.max_standard_n5_invocations == 6
        assert origin.policy_ref == policy_ref
        assert origin.action_authority == "not_established"
        assert policy.scope == origin.policy_scope
        assert policy.observed_admission is False
        assert policy.publication_authority is False
        assert policy.information_value == policy.monetary_cost == "not_established"

        initial_history = first.terminal_history
        initial_terminal = initial_history.terminal
        initial_evaluation = initial_terminal.selected_evaluation
        initial_current_basis = initial_history.current_basis
        initial_basis = initial_history.selected_basis
        assert initial_terminal.terminal_outcome == "candidate_reentry_completed"
        assert initial_evaluation is not None
        assert initial_current_basis is not None
        assert initial_basis is not None
        assert initial_history.source.observation == pytest.approx(0.175)
        assert initial_history.source.status == "candidate_only"
        assert initial_history.source.observation_class == "model_output"
        assert initial_history.source.source_currentness == "source_currentness_not_established"
        assert initial_current_basis.basis_role == "prospective"
        assert initial_current_basis.predicate_provenance == "recomputed"
        assert initial_current_basis.observed_admission is False
        assert initial_current_basis.publication_authority is False
        assert initial_basis.basis_role == "evaluated"
        assert initial_basis.predicate_provenance == "recomputed"
        assert initial_basis.observed_admission is False
        assert initial_basis.publication_authority is False
        assert initial_history.frontier_after is not None
        assert initial_history.reentry is not None
        assert initial_current_basis.preparation_inputs.base_world_model_ref is None
        assert initial_basis.preparation_inputs.base_world_model_ref is None
        root_policy_scope = origin.policy_scope
        initial_frontier = initial_history.frontier_after
        initial_selected_evaluation = initial_evaluation

        def assert_exact_retry_and_fresh_get(
            *, action_values: dict[str, object], execution: object
        ) -> None:
            action_context = action_values["values"]
            action_origin = action_values["origin"]
            action_request = action_values["request"]
            action_decision_ref = action_values["decision_ref"]
            action_control = action_context["control"]
            action_service = action_context["action_service"]
            action_client = action_context["client"]
            action_trust = action_context["trust"]
            retry_owner_args = {
                "action_service": action_service,
                "origin": action_origin,
                "policy_owner": policy_owner,
                "monkeypatch": monkeypatch,
            }
            run_id = action_origin.run_id
            route_id = action_origin.route_id
            execute_path = (
                f"/api/v1/runs/{run_id}/candidate-acquisition-experiment/{route_id}/execute"
            )
            execute_route = (
                "/api/v1/runs/{run_id}/candidate-acquisition-experiment/{route_id}/execute"
            )
            get_path = f"/api/v1/runs/{run_id}/candidate-acquisition-experiment"
            read_headers = {
                "Authorization": (f"Bearer {action_trust.tokens['acquisition-operator']}"),
                "X-Tenant-ID": action_origin.tenant_id,
            }
            execute_body = {
                "request": action_request.model_dump(mode="json"),
                "decision_ref": str(action_decision_ref),
            }
            units_before = _standard_invocation_units(control=action_control, run_id=run_id)
            assert units_before == execution.standard_invocation_units_after

            def forbid_n5(*_args: object, **_kwargs: object) -> object:
                raise AssertionError("candidate experiment duplicate retry or GET attempted N5")

            with candidate_experiment_served_execution_owner(**retry_owner_args) as retry_owner:
                with monkeypatch.context() as no_n5:
                    no_n5.setattr(JointSimulationHorizonController, "run", forbid_n5)
                    retry_response, retry_digest = action_trust.post(
                        action_client,
                        execute_path,
                        execute_body,
                        route=execute_route,
                    )
                    assert retry_response.status_code in {200, 202}, retry_response.text
                    assert retry_response.json()["job_id"] == execution.job_id
                    assert retry_digest == execution.response_digest

                    current_response = action_client.get(get_path, headers=read_headers)
                    assert current_response.status_code == 200, current_response.text
                    current = current_response.json()["current_action"]
                    assert current["status"] == "completed"
                    assert current["job_id"] == execution.job_id
                    assert current["action_generation"] == (
                        execution.terminal_history.head.action_generation
                    )
                    assert current["receipt_phase"] == "terminal"
                    assert current["terminal_outcome"] == (
                        execution.terminal_history.terminal.terminal_outcome
                    )
                    assert current["evaluation_disposition"] == (
                        execution.current_action.evaluation_disposition
                    )
                    selected_receipt = current["selected_receipt_ref"]
                    assert selected_receipt["artifact_id"] == str(
                        execution.terminal_ref.artifact_id
                    )
                    assert selected_receipt["manifest_profile_sha256"] == (
                        execution.terminal_ref.manifest_profile_sha256
                    )

                assert retry_owner.transport_calls == []
            units_after = _standard_invocation_units(control=action_control, run_id=run_id)
            assert units_after == units_before

        assert_exact_retry_and_fresh_get(
            action_values=first_values,
            execution=first,
        )

        def run_followup(
            *,
            generation: int,
            wdi_response_value: float | None = None,
        ) -> object:
            result: dict[str, object] = {}

            def execute_after_replay(**action_values: object) -> None:
                execution_kwargs = {
                    "values": action_values["values"],
                    "origin": action_values["origin"],
                    "request": action_values["request"],
                    "decision_ref": action_values["decision_ref"],
                    "policy_owner": policy_owner,
                    "monkeypatch": monkeypatch,
                }
                if wdi_response_value is not None:
                    execution_kwargs["wdi_response_value"] = wdi_response_value
                execution = run_candidate_experiment_served_execution(**execution_kwargs)
                assert_exact_retry_and_fresh_get(
                    action_values=action_values,
                    execution=execution,
                )
                result["execution"] = execution

            action_result = run_candidate_experiment_action_oracle(
                tmp_path=tmp_path / f"candidate-generation-{generation}",
                values=values,
                policy_ref=policy_ref,
                monkeypatch=monkeypatch,
                idempotency_key=(f"served-labor-candidate-experiment-generation-{generation}"),
                exercise_controls=False,
                after_replay=execute_after_replay,
            )
            assert action_result["policy_ref"] == str(policy_ref.artifact_id)
            execution = result.get("execution")
            assert execution is not None, f"generation {generation} did not execute"
            return execution

        second = run_followup(generation=2)
        third = run_followup(generation=3)
        fourth = run_followup(generation=4, wdi_response_value=21.0)
        executions = (first, second, third, fourth)

        # A later frontier advance must not invalidate the immutable history of
        # an earlier committed terminal. The last terminal still has to match
        # the live selected frontier.
        control = first_values["control"]
        for execution in executions:
            reopened = verify_candidate_experiment_terminal_history(
                control_service=control,
                head=execution.terminal_history.head,
                terminal_ref=execution.terminal_ref,
            )
            assert reopened.frontier_after == execution.terminal_history.frontier_after

        latest = executions[-1]
        latest_frontier = latest.terminal_history.frontier_after
        assert latest_frontier is not None
        read_frontier = control._control_store.read_acquisition_evaluation_frontier

        def read_stale_frontier(key: object) -> object:
            if key == latest_frontier.key:
                return initial_frontier
            return read_frontier(key)

        with monkeypatch.context() as stale_current:
            stale_current.setattr(
                control._control_store,
                "read_acquisition_evaluation_frontier",
                read_stale_frontier,
            )
            with pytest.raises(
                ValueError,
                match="candidate_experiment_terminal_frontier_after_mismatch",
            ):
                verify_candidate_experiment_terminal_history(
                    control_service=control,
                    head=latest.terminal_history.head,
                    terminal_ref=latest.terminal_ref,
                )

        foreign_frontier = replace(
            latest_frontier,
            key=replace(latest_frontier.key, candidate_id="foreign-candidate"),
        )

        def read_foreign_frontier(key: object) -> object:
            if key == latest_frontier.key:
                return foreign_frontier
            return read_frontier(key)

        with monkeypatch.context() as foreign_current:
            foreign_current.setattr(
                control._control_store,
                "read_acquisition_evaluation_frontier",
                read_foreign_frontier,
            )
            with pytest.raises(
                ValueError,
                match="candidate_experiment_terminal_frontier_after_mismatch",
            ):
                verify_candidate_experiment_terminal_history(
                    control_service=control,
                    head=latest.terminal_history.head,
                    terminal_ref=latest.terminal_ref,
                )

        assert tuple(item.terminal_history.head.action_generation for item in executions) == (
            1,
            2,
            3,
            4,
        )
        assert second.standard_invocation_units_before == 4
        assert second.standard_invocation_units_after == 4
        assert third.standard_invocation_units_before == 4
        assert third.standard_invocation_units_after == 4
        assert fourth.standard_invocation_units_before == 4
        assert fourth.standard_invocation_units_after == 6

        # Each later request is based on the exact ordered history and current source.
        for prior_count, execution in enumerate(executions[1:], start=1):
            current_origin = execution.terminal_history.origin
            current_chain = current_origin.candidate_terminal_history_chain
            assert tuple(item.head.action_generation for item in current_chain) == tuple(
                range(1, prior_count + 1)
            )
            assert len(current_chain) == prior_count
            for prior_execution, current_history in zip(
                executions[:prior_count], current_chain, strict=True
            ):
                prior_history = prior_execution.terminal_history
                assert current_history.head == prior_history.head
                assert current_history.terminal_ref == prior_history.terminal_ref
                assert current_history.terminal == prior_history.terminal
                assert current_history.frontier_after == prior_history.frontier_after
            assert current_origin.policy_scope == root_policy_scope
            assert current_origin.policy_ref == policy_ref
            assert current_origin.action_authority == "not_established"
            assert execution.terminal_history.current_basis is not None
            assert (
                execution.terminal_history.current_basis.preparation_inputs.base_world_model_ref
                == initial_history.reentry.world_model_ref
            )
            assert execution.terminal_history.source.status == "candidate_only"
            assert execution.terminal_history.source.observation_class == "model_output"
            assert (
                execution.terminal_history.source.source_currentness
                == "source_currentness_not_established"
            )
            assert current_origin.effective_generation_run == (
                initial_history.reentry.continued_generation_run
            )
            assert current_origin.effective_source_cycle == initial_history.reentry.new_cycle

        # B2 and B3 recompute current cheap consequences while retaining the
        # exact prior N5 witness and atomically advancing the selected frontier.
        retained_frontiers = []
        retained_continuations = []
        for index, execution in enumerate((second, third), start=1):
            history = execution.terminal_history
            terminal = history.terminal
            basis = history.current_basis
            selected_basis = history.selected_basis
            continuation = history.continuation
            assert terminal.terminal_outcome == "candidate_evaluation_retained"
            assert history.decision is not None
            assert history.decision.comparison_result == "equivalent"
            assert history.decision.predicate_provenance == "recomputed"
            assert history.decision.observed_admission is False
            assert history.decision.publication_authority is False
            assert history.reentry is None
            assert basis is not None
            assert basis.basis_role == "prospective"
            assert basis.predicate_provenance == "recomputed"
            assert basis.effective_values_sha256 == initial_basis.effective_values_sha256
            assert basis.observed_admission is False
            assert basis.publication_authority is False
            assert selected_basis == initial_basis
            assert terminal.selected_evaluation == initial_selected_evaluation
            assert terminal.selected_evaluation_witness_ref == (
                initial_terminal.selected_evaluation_witness_ref
            )
            assert terminal.current_continuation_ref is not None
            assert continuation is not None
            assert continuation.action_generation == index + 1
            assert continuation.action_job_id == execution.job_id
            assert continuation.retained_evaluation == initial_selected_evaluation
            assert continuation.predicate_provenance == "recomputed"
            assert continuation.observed_admission is False
            assert continuation.publication_authority is False
            assert history.source.observation == initial_history.source.observation
            assert execution.current_action.evaluation_disposition == "retained"
            assert execution.current_action.selected_receipt_ref is not None
            assert execution.current_action.selected_receipt_ref.manifest_profile_sha256
            assert execution.current_action.selected_receipt_ref == execution.terminal_ref
            assert len(execution.execution_owner.transport_calls) == 1
            assert history.frontier_before is not None
            assert history.frontier_after is not None
            assert history.frontier_after.revision == history.frontier_before.revision + 1
            assert history.frontier_after.selected_evaluation_witness_ref == (
                initial_frontier.selected_evaluation_witness_ref
            )
            retained_frontiers.append(history.frontier_after)
            retained_continuations.append(terminal.current_continuation_ref)

        assert second.terminal_history.frontier_before == initial_frontier
        assert third.terminal_history.frontier_before == retained_frontiers[0]
        assert retained_frontiers[0].frontier_ref != retained_frontiers[1].frontier_ref
        assert retained_continuations[0] != retained_continuations[1]

        # C changes the actual WDI observation, so it must produce a new basis,
        # N5 witness, and model transition instead of retaining the old result.
        changed_history = fourth.terminal_history
        changed_terminal = changed_history.terminal
        changed_current_basis = changed_history.current_basis
        changed_basis = changed_history.selected_basis
        assert changed_history.decision is not None
        assert changed_history.decision.comparison_result == "different"
        assert changed_history.decision.predicate_provenance == "recomputed"
        assert changed_history.decision.observed_admission is False
        assert changed_history.decision.publication_authority is False
        assert changed_current_basis is not None
        assert changed_current_basis.basis_role == "prospective"
        assert changed_current_basis.observed_admission is False
        assert changed_current_basis.publication_authority is False
        assert changed_current_basis.effective_values_sha256 != (
            initial_basis.effective_values_sha256
        )
        assert changed_basis is not None
        assert changed_basis.basis_role == "evaluated"
        assert changed_basis.predicate_provenance == "recomputed"
        assert changed_basis.effective_values_sha256 != initial_basis.effective_values_sha256
        assert changed_history.source.observation == pytest.approx(0.21)
        assert changed_history.source.observation != initial_history.source.observation
        assert changed_basis.selected_data_snapshot_ref != initial_basis.selected_data_snapshot_ref
        assert changed_basis.selected_world_model_ref != initial_basis.selected_world_model_ref
        assert changed_basis.selected_data_snapshot_ref is not None
        assert changed_basis.selected_world_model_ref is not None
        assert changed_basis.observed_admission is False
        assert changed_basis.publication_authority is False
        assert changed_terminal.terminal_outcome == "candidate_reentry_completed"
        assert changed_terminal.current_continuation_ref is None
        assert changed_history.reentry is not None
        transition = changed_history.reentry.basis_transition
        assert transition.to_cycle_index == transition.from_cycle_index + 1
        assert transition.data_snapshot_ref.artifact_id == (
            changed_basis.selected_data_snapshot_ref.artifact_id
        )
        assert transition.data_snapshot_ref.manifest_profile_sha256 == (
            changed_basis.selected_data_snapshot_ref.manifest_profile_sha256
        )
        assert transition.world_model_ref.artifact_id == (
            changed_basis.selected_world_model_ref.artifact_id
        )
        assert transition.world_model_ref.manifest_profile_sha256 == (
            changed_basis.selected_world_model_ref.manifest_profile_sha256
        )
        assert changed_terminal.selected_evaluation is not None
        assert transition.n5_input_ref is not None
        assert transition.n5_execution_ref is not None
        assert transition.n5_result_ref is not None
        assert transition.n5_input_ref.artifact_id == (
            changed_terminal.selected_evaluation.n5_input_ref.artifact_id
        )
        assert transition.n5_input_ref.manifest_profile_sha256 == (
            changed_terminal.selected_evaluation.n5_input_ref.manifest_profile_sha256
        )
        assert transition.n5_execution_ref.artifact_id == (
            changed_terminal.selected_evaluation.n5_execution_ref.artifact_id
        )
        assert transition.n5_execution_ref.manifest_profile_sha256 == (
            changed_terminal.selected_evaluation.n5_execution_ref.manifest_profile_sha256
        )
        assert transition.n5_result_ref.artifact_id == (
            changed_terminal.selected_evaluation.n5_result_ref.artifact_id
        )
        assert transition.n5_result_ref.manifest_profile_sha256 == (
            changed_terminal.selected_evaluation.n5_result_ref.manifest_profile_sha256
        )
        assert changed_terminal.selected_evaluation.n5_input_ref != (
            initial_selected_evaluation.n5_input_ref
        )
        assert changed_terminal.selected_evaluation.n5_execution_ref != (
            initial_selected_evaluation.n5_execution_ref
        )
        assert changed_terminal.selected_evaluation.n5_result_ref != (
            initial_selected_evaluation.n5_result_ref
        )
        assert changed_terminal.selected_evaluation.world_model_record_hash != (
            initial_selected_evaluation.world_model_record_hash
        )
        assert changed_history.frontier_before == retained_frontiers[-1]
        assert changed_history.frontier_after is not None
        assert changed_history.frontier_after.revision == (
            changed_history.frontier_before.revision + 1
        )
        assert changed_history.frontier_after.selected_evaluation_witness_ref == str(
            changed_terminal.selected_evaluation_witness_ref.artifact_id
        )
        assert fourth.current_action.evaluation_disposition == "new"
        assert fourth.current_action.selected_receipt_ref is not None
        assert fourth.current_action.selected_receipt_ref.manifest_profile_sha256
        assert fourth.current_action.selected_receipt_ref == fourth.terminal_ref
        assert len(fourth.execution_owner.transport_calls) == 1

        snapshot = control._llm_producer_settlement_store.snapshot_safe()
        profile = snapshot.invocation_profiles[origin.run_id]
        standard_units = sum(
            row.units
            for row in snapshot.invocation_reservations.values()
            if row.run_id == origin.run_id
            and row.profile_digest == profile.profile_digest
            and row.purpose == "standard"
        )
        protected_used = sum(
            row.units
            for row in snapshot.invocation_reservations.values()
            if row.run_id == origin.run_id
            and row.profile_digest == profile.profile_digest
            and row.purpose in {"diagnostic", "counterevidence"}
        )
        standard_remaining = profile.total_units - profile.protected_units - standard_units
        protected_remaining = profile.protected_units - protected_used
        assert profile.total_units == 7
        assert profile.protected_units == 1
        assert standard_units == 6
        assert standard_remaining == 0
        assert protected_used == 0
        assert protected_remaining == 1

        observed["executions"] = executions
        observed["policy_scope"] = root_policy_scope

    scenario = run_genuine_candidate_experiment_scenario(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        gateway=served_recorded_candidate_gateway,
        total_units=7,
        after_execution=after_first_execution,
    )
    assert scenario["source_status"] == "completed"
    assert len(observed["executions"]) == 4
