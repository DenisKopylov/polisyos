"""Genuine first-B receiver and fresh-constructor acquisition falsifiers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import MethodType
from typing import Any

import pytest
from fastapi.testclient import TestClient

from polisyos.core import canon
from polisyos.runtime.quality import generation_cycle as generation_cycle_owner
from polisyos.runtime.quality import joint_simulation_horizon as horizon_owner
from polisyos.runtime.quality.acquisition_evaluation import (
    AcquisitionEvaluationBasis,
    AcquisitionEvaluationDecision,
    read_acquisition_evaluation_artifact,
)
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteLoopReceiptV2
from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthReceipt
from polisyos.runtime.quality.generation_cycle import (
    AcquisitionOverlayReentryReceipt,
    load_joint_simulation_result,
)
from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController
from polisyos.runtime.quality.n5_execution_basis import (
    _exact_native_content,
    exact_n5_content_bytes,
    read_n5_execution_implementation_witness,
    reconcile_live_n5_implementation,
)
from tests._helpers import acquisition_served_history as fixture
from tests.integration.core_runtime.test_acquisition_retained_sequential_served import (
    _OwnerCallMonitor,
    _SequentialOracle,
)

pytest_plugins = ("tests._helpers.acquisition_served_history",)


def _run_genuine_first_b(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    gateway: Any,
    callback: Callable[..., None],
) -> None:
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
    )

    source = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "candidate-source", include_owner_slot_manifest=True
    )
    called: list[str] = []

    def after_real_b(**values: Any) -> None:
        assert values["witness"].predicate_provenance == "recomputed"
        assert values["actual_b"].result.trajectories
        called.append(values["witness"].content_hash)
        callback(**values)

    with _OwnerCallMonitor() as monitor:
        oracle = _SequentialOracle(monkeypatch, monitor, after_real_b=after_real_b)
        result = fixture._produce_served_acquisition_history(
            tmp_path,
            monkeypatch,
            gateway,
            source_owner_root=source.root,
            sequential_oracle=oracle,
            provider_mode="synthetic_settled_candidate",
        )
    assert result is not None and result["run_id"] and result["candidate_id"]
    assert len(called) == 1, "the callback must follow one genuine first-B witness"


def test_real_b_receiver_dispatch_and_settings_are_consumed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway: Any,
) -> None:
    """Preserve code/registry markers while changing only actual receiver meaning."""

    def check(**values: Any) -> None:
        actual_b, selected, witness = values["actual_b"], values["selected_b"], values["witness"]
        receiver = values["capture"]._controller
        prior_settings = receiver._settings
        baseline = fixture._within_fixture_owner(
            reconcile_live_n5_implementation,
            actual_b.result,
            input_ref=selected.n5_input_ref,
        )
        assert baseline == witness
        # Equal typed settings in a fresh object do not change effective meaning.
        with monkeypatch.context() as mutation:
            mutation.setattr(receiver, "_settings", prior_settings.model_copy(deep=True))
            assert (
                fixture._within_fixture_owner(
                    reconcile_live_n5_implementation,
                    actual_b.result,
                    input_ref=selected.n5_input_ref,
                )
                == witness
            )

        original_runner = JointSimulationHorizonController._run_ncm_horizon
        invoked: list[str] = []

        def changed_runner(self: Any, request: Any, plan: Any, decision: Any) -> list[Any]:
            invoked.append("receiver numerical call")
            return original_runner(self, request, plan, decision)

        def changed_dispatch(self: Any) -> dict[str, Any]:
            invoked.append("receiver dispatcher call")
            return {"ncm_parallel_worlds": MethodType(changed_runner, self)}

        for name, replacement, reason in (
            (
                "_engine_runners",
                MethodType(changed_dispatch, receiver),
                "n5_consumed_receiver_dispatch_not_established",
            ),
            (
                "_run_ncm_horizon",
                MethodType(changed_runner, receiver),
                "n5_consumed_receiver_dispatch_not_established",
            ),
            (
                "_settings",
                prior_settings.model_copy(update={"shrink_world_credal_state": True}),
                "n5_prepared_configuration_not_consumed",
            ),
        ):
            with monkeypatch.context() as mutation:
                mutation.setattr(receiver, name, replacement)
                with pytest.raises(ValueError, match="^" + reason + "$"):
                    fixture._within_fixture_owner(
                        reconcile_live_n5_implementation,
                        actual_b.result,
                        input_ref=selected.n5_input_ref,
                    )
            assert (
                fixture._within_fixture_owner(
                    reconcile_live_n5_implementation,
                    actual_b.result,
                    input_ref=selected.n5_input_ref,
                )
                == witness
            )
        assert not invoked, "a current implementation verifier must not run N5"
        assert receiver._settings is prior_settings

    _run_genuine_first_b(tmp_path, monkeypatch, served_recorded_candidate_gateway, check)


@pytest.mark.parametrize(
    "construction_edge",
    [
        "class_constructor",
        "port_constructor_lookup",
        "model_default_rebuild",
        "unsupported_model_default",
    ],
)
def test_changed_fresh_horizon_constructor_cannot_retain_on_ordinary_equal_source_post(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway: Any,
    construction_edge: str,
) -> None:
    """Bind full fresh configuration or refuse it before NCM on the ordinary route."""

    def check(**values: Any) -> None:
        ctx, oracle = values["ctx"], values["oracle"]
        actual_b, selected, witness = values["actual_b"], values["selected_b"], values["witness"]
        capture = values["capture"]
        old_receiver = capture._controller
        original_method, original_step = capture.method, capture.method.pure_step
        old_request = exact_n5_content_bytes(capture._request)
        old_settings = exact_n5_content_bytes(old_receiver._settings)
        original_init = JointSimulationHorizonController.__init__
        original_lookup = generation_cycle_owner.JointSimulationHorizonController
        assert original_lookup is JointSimulationHorizonController
        original_run = JointSimulationHorizonController.run
        original_ncm = JointSimulationHorizonController._run_ncm_horizon
        settings_type = horizon_owner._RuntimeSettings
        setting_name = "shrink_world_credal_state"
        original_field_default = settings_type.model_fields[setting_name].default
        assert original_field_default is False
        configuration_type = horizon_owner.PreparedJointSimulationConfiguration
        consumed = horizon_owner.read_joint_simulation_configuration(old_receiver)
        assert type(consumed) is configuration_type
        horizon_owner.require_prepared_joint_simulation_configuration(old_receiver, consumed)
        assert consumed.runtime_settings.shrink_world_credal_state is False
        consumed_bytes = exact_n5_content_bytes(consumed)
        assert witness.consumed_configuration_values == _exact_native_content(consumed)
        owner_before = horizon_owner.prepare_joint_simulation_configuration()
        assert type(owner_before) is configuration_type
        assert exact_n5_content_bytes(owner_before) == consumed_bytes
        assert witness.consumed_configuration_values == _exact_native_content(owner_before)
        oracle.monitor.watch("constructor_oracle_ncm", original_step)
        constructed: list[Any] = []

        def change_new_receiver(receiver: Any) -> None:
            receiver._settings = receiver._settings.model_copy(
                update={"shrink_world_credal_state": True},
            )
            constructed.append(receiver)

        def changed_constructor(self: Any, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)
            change_new_receiver(self)

        def changed_constructor_lookup(*args: Any, **kwargs: Any) -> Any:
            receiver = JointSimulationHorizonController(*args, **kwargs)
            change_new_receiver(receiver)
            return receiver

        assert (
            fixture._within_fixture_owner(
                reconcile_live_n5_implementation,
                actual_b.result,
                input_ref=selected.n5_input_ref,
            )
            == witness
        )
        with monkeypatch.context() as mutation:
            try:
                if construction_edge == "class_constructor":
                    mutation.setattr(
                        JointSimulationHorizonController, "__init__", changed_constructor
                    )
                elif construction_edge == "port_constructor_lookup":
                    mutation.setattr(
                        generation_cycle_owner,
                        "JointSimulationHorizonController",
                        changed_constructor_lookup,
                    )
                    assert JointSimulationHorizonController.__init__ is original_init
                else:
                    assert construction_edge in {
                        "model_default_rebuild",
                        "unsupported_model_default",
                    }
                    settings_type.model_fields[setting_name].default = (
                        object() if construction_edge == "unsupported_model_default" else True
                    )
                    settings_type.model_rebuild(force=True)
                    assert horizon_owner._RuntimeSettings is settings_type
                    assert JointSimulationHorizonController.__init__ is original_init
                    assert (
                        generation_cycle_owner.JointSimulationHorizonController is original_lookup
                    )
                assert JointSimulationHorizonController.run is original_run
                assert old_receiver._registry.get(capture._method_fqn) is original_method
                assert original_method.pure_step is original_step
                assert exact_n5_content_bytes(capture._request) == old_request
                assert old_receiver._run_ncm_horizon.__func__ is original_ncm
                assert exact_n5_content_bytes(old_receiver._settings) == old_settings
                assert exact_n5_content_bytes(consumed) == consumed_bytes

                # Decide from complete actual owner values, not model metadata,
                # validator identity or a test-created configuration mapping.
                if construction_edge == "unsupported_model_default":
                    with pytest.raises(
                        ValueError,
                        match=r"^n5_native_content_type_not_established:object$",
                    ):
                        exact_n5_content_bytes(
                            horizon_owner.prepare_joint_simulation_configuration()
                        )
                    fresh_configuration = None
                    expected_worker_error = "acquisition_evaluation_configuration_not_established"
                else:
                    fresh_configuration = horizon_owner.prepare_joint_simulation_configuration()
                    assert type(fresh_configuration) is configuration_type
                    if construction_edge == "model_default_rebuild":
                        assert (
                            fresh_configuration.runtime_settings.shrink_world_credal_state is True
                        )
                        assert exact_n5_content_bytes(fresh_configuration) != consumed_bytes
                        expected_worker_error = None
                    else:
                        assert exact_n5_content_bytes(fresh_configuration) == consumed_bytes
                        expected_worker_error = "n5_prepared_configuration_not_consumed"
                negative, positive = values["issue_equal_source"](
                    expected_worker_error=expected_worker_error,
                )
                assert negative.receipt.terminal_outcome == "quarantined_no_growth"

                if expected_worker_error is None:
                    terminal = positive.receipt
                    assert type(terminal) is AcquisitionRouteLoopReceiptV2
                    assert terminal.terminal_outcome == "reentry_completed"
                    assert terminal.current_continuation_ref is None
                    assert terminal.reentry_receipt_ref is not None
                    assert (
                        positive.after_calls["constructor_oracle_ncm"]
                        > (positive.before_calls["constructor_oracle_ncm"])
                    ), "new prepared values must be consumed by actual unchanged NCM"
                    assert (
                        positive.after_calls["n5_controller"]
                        > positive.before_calls["n5_controller"]
                    )
                    assert (
                        positive.after_calls["reentry_cycle"]
                        > positive.before_calls["reentry_cycle"]
                    )
                else:
                    assert positive.receipt is None
                    assert positive.worker_error == expected_worker_error
                    expected_phase = (
                        "outcome_selected"
                        if construction_edge == "unsupported_model_default"
                        else "world_committed_reentry_pending"
                    )
                    assert positive.selected_head.receipt_phase == expected_phase
                    assert positive.selected_phase.receipt_phase == expected_phase
                    assert (
                        positive.after_calls["constructor_oracle_ncm"]
                        == (positive.before_calls["constructor_oracle_ncm"])
                    )
                    assert (
                        positive.after_calls["n5_controller"]
                        == positive.before_calls["n5_controller"]
                    )
                    assert (
                        positive.after_calls["reentry_cycle"]
                        == positive.before_calls["reentry_cycle"]
                    )
                    if construction_edge != "unsupported_model_default":
                        assert constructed and all(
                            receiver is not old_receiver for receiver in constructed
                        )
                    else:
                        assert positive.after_artifacts == positive.before_artifacts
                        assert not constructed
                assert all(
                    receiver._run_ncm_horizon.__func__ is original_ncm
                    and "_run_ncm_horizon" not in vars(receiver)
                    for receiver in constructed
                )

                with TestClient(ctx.app()) as client:
                    control = client.app.state.runtime_container.control_service
                    store, events = control._artifact_store, control._diagnostic_event_log
                    if expected_worker_error is None:
                        decision_ref = terminal.evaluation_decision_ref
                    elif construction_edge != "unsupported_model_default":
                        decision_refs = tuple(
                            oracle._selected(store, ref)
                            for ref in positive.selected_phase.owner_receipt_refs
                            if fixture._within_fixture_owner(store.get_manifest, ref).kind
                            == "runtime_quality.acquisition_evaluation_decision"
                        )
                        assert len(decision_refs) == 1, decision_refs
                        decision_ref = decision_refs[0]
                    else:
                        # The typed NE decision was durably emitted before the
                        # outcome-selected refusal. Locate it through the real
                        # scoped event index, never by scanning CAS or guessing
                        # "latest" from artifact IDs.
                        records = fixture._within_fixture_owner(
                            events.list_events,
                            run_id=ctx.run_id,
                            job_id=ctx.source_job_id,
                            limit=1000,
                        )
                        assert len(records) < 1000, "test event scope truncated"
                        matched = {}
                        for record in records:
                            event = record.event
                            if event.event_type != "polisyos.runtime.acquisition.evaluation.v1":
                                continue
                            if event.payload_ref is None:
                                continue
                            ref = oracle._selected(store, event.payload_ref)
                            if ref.kind != "runtime_quality.acquisition_evaluation_decision":
                                continue
                            candidate = fixture._within_fixture_owner(
                                read_acquisition_evaluation_artifact,
                                store=store,
                                event_log=events,
                                ref=ref,
                                record_type=AcquisitionEvaluationDecision,
                            )
                            if (
                                candidate.action_job_id == positive.job_id
                                and candidate.action_generation
                                == positive.selected_head.action_generation
                                and candidate.tenant_id == fixture.TENANT
                                and candidate.cell_id == fixture.CELL
                                and candidate.run_id == ctx.run_id
                            ):
                                matched[str(ref.artifact_id)] = ref
                        assert len(matched) == 1, matched
                        decision_ref = next(iter(matched.values()))
                    decision = fixture._within_fixture_owner(
                        read_acquisition_evaluation_artifact,
                        store=store,
                        event_log=events,
                        ref=decision_ref,
                        record_type=AcquisitionEvaluationDecision,
                    )
                    assert decision.action_job_id == positive.job_id
                    assert decision.comparison_result == "not_established"
                    if construction_edge == "unsupported_model_default":
                        assert (
                            "n5_configuration_preparation_not_established" in decision.reason_codes
                        )
                    else:
                        assert "n5_receiver_construction_not_established" in decision.reason_codes
                    current_basis = fixture._within_fixture_owner(
                        read_acquisition_evaluation_artifact,
                        store=store,
                        event_log=events,
                        ref=decision.current_basis_ref,
                        record_type=AcquisitionEvaluationBasis,
                    )
                    if construction_edge == "unsupported_model_default":
                        assert current_basis.predicate_provenance == "not_established"
                        assert current_basis.preparation_inputs.n5_execution_configuration is None
                        assert current_basis.preparation_inputs.n5_configuration_reason_codes
                        assert (
                            "n5_configuration_preparation_not_established"
                            in current_basis.reason_codes
                        )
                    else:
                        assert exact_n5_content_bytes(
                            current_basis.preparation_inputs.n5_execution_configuration
                        ) == exact_n5_content_bytes(fresh_configuration)
                    growth = AcquisitionWorldGrowthReceipt.model_validate(
                        canon.from_canonical_bytes(
                            fixture._within_fixture_owner(
                                store.get_bytes,
                                decision.growth_receipt_ref,
                            )
                        )
                    )
                    assert growth.admitted_observation_delta > 0
                    assert growth.selection.epoch_id == 2
                    if expected_worker_error is None:
                        reentry = AcquisitionOverlayReentryReceipt.model_validate(
                            canon.from_canonical_bytes(
                                fixture._within_fixture_owner(
                                    store.get_bytes,
                                    terminal.reentry_receipt_ref,
                                )
                            )
                        )
                        assert reentry.new_cycle.cycle_index == selected.cycle_index + 1
                        simulation = reentry.new_cycle.simulation
                        assert simulation.simulation_result_ref is not None, simulation
                        fresh_result = fixture._within_fixture_owner(
                            load_joint_simulation_result,
                            simulation.simulation_result_ref,
                            store=store,
                        )
                        assert fresh_result.trajectories
                        assert simulation.candidate_simulation_n5_input_ref is not None
                        produced_witness = fixture._within_fixture_owner(
                            read_n5_execution_implementation_witness,
                            fresh_result,
                            input_ref=simulation.candidate_simulation_n5_input_ref,
                        )
                        # A descriptor is producer-observed even if software
                        # equivalence stays NE; it does not upgrade authority.
                        assert produced_witness.consumed_configuration_values == (
                            _exact_native_content(fresh_configuration)
                        )
                        assert produced_witness.consumed_configuration_values == (
                            _exact_native_content(
                                current_basis.preparation_inputs.n5_execution_configuration
                            )
                        )
                        assert selected.n5_result_ref != simulation.simulation_result_ref
                        assert exact_n5_content_bytes(actual_b.result.world_credal_state_after) == (
                            exact_n5_content_bytes(actual_b.result.world_credal_state_before)
                        )
                        expected_after = horizon_owner._contract_testing_shrunk_credal_state(
                            fresh_result.world_credal_state_before,
                        )
                        assert exact_n5_content_bytes(fresh_result.world_credal_state_after) == (
                            exact_n5_content_bytes(expected_after)
                        )
                        assert (
                            fresh_result.world_credal_state_after
                            != fresh_result.world_credal_state_before
                        )
                    response = client.get(ctx.history_path, headers=ctx.history_headers)
                    assert response.status_code == 200, response.text
                    projection = response.json()["run"]["candidate_simulation"]
                    rows = projection.get("acquisition_history", ())
                    if expected_worker_error is None:
                        row = next(
                            row
                            for row in rows
                            if row["action_generation"] == terminal.action_generation
                        )
                        assert row["terminal_outcome"] == "reentry_completed"
                    else:
                        assert all(
                            row["action_generation"] != positive.selected_head.action_generation
                            for row in rows
                        )
                    assert all(
                        row.get("terminal_outcome") != "source_admitted_evaluation_retained"
                        for row in rows
                        if row["action_generation"]
                        == (
                            terminal.action_generation
                            if expected_worker_error is None
                            else positive.selected_head.action_generation
                        )
                    )
                oracle.monitor.assert_slots_unchanged()
            finally:
                if construction_edge in {"model_default_rebuild", "unsupported_model_default"}:
                    settings_type.model_fields[setting_name].default = original_field_default
                    settings_type.model_rebuild(force=True)
        assert JointSimulationHorizonController.__init__ is original_init
        assert generation_cycle_owner.JointSimulationHorizonController is original_lookup
        assert settings_type.model_fields[setting_name].default is original_field_default
        assert original_method.pure_step is original_step
        assert exact_n5_content_bytes(capture._request) == old_request
        assert exact_n5_content_bytes(old_receiver._settings) == old_settings

    _run_genuine_first_b(tmp_path, monkeypatch, served_recorded_candidate_gateway, check)
