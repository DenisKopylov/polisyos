"""A real budget-blocked acquisition reentry advances its durable frontier."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from polisyos.core import canon
from polisyos.runtime.http.services.control_plane_store import AcquisitionEvaluationFrontierKey
from polisyos.runtime.quality.acquisition_evaluation import (
    AcquisitionEvaluationBasis,
    AcquisitionEvaluationDecision,
    read_acquisition_evaluation_artifact,
    resolve_selected_acquisition_evaluation_parts,
)
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteLoopReceiptV2
from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthReceipt
from polisyos.runtime.quality.generation_cycle import (
    AcquisitionOverlayReentryReceipt,
    GenerationCycleController,
)
from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes
from tests._helpers import acquisition_served_history as fixture
from tests._helpers.candidate_cycle_source_profile import (
    build_candidate_cycle_substrate_route_inputs,
)
from tests.integration.core_runtime.test_acquisition_retained_sequential_served import (
    _OwnerCallMonitor,
    _SequentialOracle,
)

pytest_plugins = ("tests._helpers.acquisition_served_history",)


def test_blocked_acquisition_reentry_replaces_frontier_and_survives_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway: Any,
) -> None:
    """A later genuine admission may finish without inventing an N5 execution."""
    checked: list[str] = []

    def after_real_b(
        *,
        ctx: Any,
        oracle: _SequentialOracle,
        actual_b: Any,
        selected_b: Any,
        witness: Any,
        capture: Any,
        issue_equal_source: Any,
    ) -> None:
        assert witness.predicate_provenance == "recomputed"
        assert actual_b.selected == selected_b
        key = AcquisitionEvaluationFrontierKey(
            tenant_id=fixture.TENANT,
            cell_id=fixture.CELL,
            source_job_id=ctx.source_job_id,
            design_problem_ref=ctx.closure.design_problem_ref,
            candidate_id=selected_b.candidate_id,
        )
        with TestClient(ctx.app()) as client:
            control = client.app.state.runtime_container.control_service
            before = fixture._within_fixture_owner(
                control._control_store.read_acquisition_evaluation_frontier, key
            )
            assert before is not None
            assert before.selected_evaluation_witness_ref == str(
                selected_b.n5_execution_ref.artifact_id
            )
            assert before.selected_evaluation_content_hash == actual_b.execution.content_hash

        # Choose an actual, valid fixture route input below the real default
        # stage-3 estimate; no scheduler/N5 callable or receipt is replaced.
        controller = GenerationCycleController(
            _prepared_n5_configuration=capture._controller._prepared_configuration
        )
        estimated_cost = controller._voi_scheduler._estimated_cost_decimal(3)
        assert isinstance(estimated_cost, Decimal) and estimated_cost > 0
        budget = estimated_cost / Decimal(10)
        old_route = ctx.cases[-1].selected
        ctx.cases[-1].selected = type(old_route).model_validate(
            {**old_route.model_dump(mode="python"), "reentry_budget_usd": budget}
        )
        oracle.value = -9.0  # Genuine newly fetched source differs from B.
        oracle.monitor.watch("reentry_cycle", GenerationCycleController._run_cycle)
        negative, positive = issue_equal_source()
        assert negative.receipt.terminal_outcome == "quarantined_no_growth"
        assert negative.job_id != positive.job_id
        terminal = positive.receipt
        assert type(terminal) is AcquisitionRouteLoopReceiptV2
        assert terminal.terminal_outcome == "reentry_completed"
        assert terminal.reentry_receipt_ref is not None
        assert terminal.current_continuation_ref is None
        assert terminal.selected_evaluation is None
        assert terminal.tenant_id == fixture.TENANT and terminal.cell_id == fixture.CELL
        assert terminal.run_id == ctx.run_id and terminal.source_job_id == ctx.source_job_id
        assert terminal.job_id == positive.job_id
        assert terminal.action_generation == negative.receipt.action_generation + 1
        assert positive.after_calls["n5"] == positive.before_calls["n5"]
        assert positive.after_calls["n5_controller"] == positive.before_calls["n5_controller"]
        assert positive.after_calls["reentry_cycle"] > positive.before_calls["reentry_cycle"]

        def inspect_reopened() -> tuple[bytes, str]:
            # A fresh app/control/store reopens the persisted terminal, basis,
            # prior B and frontier under their real scope; no receipt is made here.
            with TestClient(ctx.app()) as client:
                control = client.app.state.runtime_container.control_service
                store, events = control._artifact_store, control._diagnostic_event_log
                head = fixture._within_fixture_owner(
                    control._control_store.get_acquisition_action_head,
                    tenant_id=fixture.TENANT,
                    cell_id=fixture.CELL,
                    run_id=ctx.run_id,
                    source_job_id=ctx.source_job_id,
                    route_id=terminal.route_id,
                    action_generation=terminal.action_generation,
                )
                assert head is not None and head.receipt_phase == "terminal"
                assert head.job_id == positive.job_id
                assert head.receipt_ref == str(positive.receipt_ref.artifact_id)
                reopened = fixture._read_owned_terminal(store, head.receipt_ref)
                assert reopened == terminal
                raw_terminal = fixture._within_fixture_owner(store.get_bytes, head.receipt_ref)
                reentry = AcquisitionOverlayReentryReceipt.model_validate(
                    canon.from_canonical_bytes(
                        fixture._within_fixture_owner(store.get_bytes, terminal.reentry_receipt_ref)
                    )
                )
                assert reentry.source_run_id == ctx.closure.generation_run.run_id
                assert reentry.source_cycle_index == selected_b.cycle_index
                assert reentry.new_cycle.cycle_index == selected_b.cycle_index + 1
                assert reentry.new_cycle.simulation.status == "simulation_blocked"
                assert (
                    reentry.new_cycle.simulation.diagnostics["reason"]
                    == "budget_exhausted_for_next_level"
                )
                assert reentry.new_cycle.simulation.candidate_simulation_n5_input_ref is None
                assert "candidate_simulation_execution_selected_ref" not in (
                    reentry.new_cycle.simulation.diagnostics
                )
                decision = fixture._within_fixture_owner(
                    read_acquisition_evaluation_artifact,
                    store=store,
                    event_log=events,
                    ref=terminal.evaluation_decision_ref,
                    record_type=AcquisitionEvaluationDecision,
                )
                assert type(decision) is AcquisitionEvaluationDecision
                assert decision.comparison_result == "different"
                assert decision.predicate_provenance == "recomputed"
                growth = AcquisitionWorldGrowthReceipt.model_validate(
                    canon.from_canonical_bytes(
                        fixture._within_fixture_owner(store.get_bytes, decision.growth_receipt_ref)
                    )
                )
                assert growth.selection.epoch_id == 2 and growth.admitted_observation_delta > 0
                assert growth.selection.reentry_budget_usd == budget
                basis = fixture._within_fixture_owner(
                    read_acquisition_evaluation_artifact,
                    store=store,
                    event_log=events,
                    ref=terminal.selected_basis_ref,
                    record_type=AcquisitionEvaluationBasis,
                )
                assert type(basis) is AcquisitionEvaluationBasis
                assert basis.predicate_provenance == "not_established"
                assert "acquisition_prior_execution_not_observed" in basis.reason_codes
                assert basis.evaluation is None
                frontier = fixture._within_fixture_owner(
                    control._control_store.read_acquisition_evaluation_frontier, key
                )
                assert frontier is not None and frontier.frontier_ref != before.frontier_ref
                assert frontier.revision == before.revision + 1
                assert frontier.selected_evaluation_witness_ref == terminal.reentry_receipt_ref
                assert frontier.selected_evaluation_witness_ref == str(
                    terminal.selected_evaluation_witness_ref.artifact_id
                )
                assert frontier.selected_evaluation_content_hash == reentry.content_hash
                assert frontier.basis_ref == str(terminal.selected_basis_ref.artifact_id)
                assert frontier.basis_content_hash == basis.content_hash
                assert frontier.selected_evaluation_witness_ref != str(
                    selected_b.n5_execution_ref.artifact_id
                )
                historical_b = fixture._within_fixture_owner(
                    resolve_selected_acquisition_evaluation_parts,
                    artifact_store=store,
                    control_store=control._control_store,
                    tenant_id=fixture.TENANT,
                    cell_id=fixture.CELL,
                    run_id=ctx.run_id,
                    generation_run=ctx.closure.generation_run,
                    source_cycle=ctx.closure.source_cycle,
                    design_problem_ref=ctx.closure.design_problem_ref,
                )
                assert historical_b.selected == selected_b
                assert exact_n5_content_bytes(
                    historical_b.result.content_bound_payload()
                ) == exact_n5_content_bytes(actual_b.result.content_bound_payload())
                return raw_terminal, frontier.frontier_ref

        first = inspect_reopened()
        second = inspect_reopened()
        assert second == first  # A second cold application reads the same durable commit.
        projection = oracle._fresh_projection(ctx)
        rows = [
            row
            for row in projection["acquisition_history"]
            if row["action_generation"] == terminal.action_generation
        ]
        assert len(rows) == 1 and rows[0]["terminal_outcome"] == "reentry_completed"
        assert rows[0]["expected_origin_source_ref"]["artifact_id"] == str(
            selected_b.n4_source_ref.artifact_id
        )
        checked.append(positive.job_id)

    source = build_candidate_cycle_substrate_route_inputs(tmp_path / "candidate-source")
    with _OwnerCallMonitor() as monitor:
        oracle = _SequentialOracle(monkeypatch, monitor, after_real_b=after_real_b)
        result = fixture._produce_served_acquisition_history(
            tmp_path,
            monkeypatch,
            served_recorded_candidate_gateway,
            source_owner_root=source.root,
            sequential_oracle=oracle,
        )
    assert result is not None and result["run_id"] and result["candidate_id"]
    assert len(checked) == 1, "the real blocked reentry was not reopened"
