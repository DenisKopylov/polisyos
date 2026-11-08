"""Serve the candidate-only UKR CPI level through source reentry and a fresh N5 reader."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

pytest_plugins = ("tests._helpers.acquisition_served_history",)


@pytest.mark.integration
def test_x03_cpi_level_reenters_fresh_served_n5_and_api_reader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway,
) -> None:
    """Bind the real 2010=100 CPI source and distinguish its N5 response from baseline."""
    from dataclasses import replace

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.contracts import DataSnapshot
    from polisyos.core.contracts.fabric import CandidateAcquisitionSourceDataSnapshotLineage
    from polisyos.core.contracts.runtime import (
        RunCandidateSimulationAcquisitionHistoryEntryV5,
        RunDetailsResponse,
    )
    from polisyos.fabric.connectors.profiles import SourceProfileRegistry
    from polisyos.foundry.execute.executor import get_state_path, load_state_snapshot
    from polisyos.runtime.quality import generation_cycle
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        CandidateUnpricedExperimentPolicyTemplate,
        read_candidate_unpriced_policy,
        resolve_current_candidate_unpriced_policy,
    )
    from polisyos.runtime.quality.candidate_acquisition_source import (
        CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V3,
        _selected_compiler_candidate,
    )
    from polisyos.runtime.quality.candidate_experiment_policy_issuer import (
        prepare_candidate_experiment_policies_for_completed_job,
    )
    from polisyos.runtime.quality.data_snapshot_lineage import (
        DataSnapshotSourceRowNotEstablishedError,
        validate_data_snapshot_owner_lineage,
    )
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views
    from polisyos.scientist.orchestration.engine import BudgetInvocationQuotaPolicy
    from tests._helpers import acquisition_served_history as served
    from tests._helpers import generic_n4_served_replay
    from tests._helpers.annual_gdp_candidate import annual_gdp_catalog_source
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
    )
    from tests._helpers.candidate_experiment_served_execution import (
        bind_candidate_test_execution_port_factory,
        run_candidate_experiment_served_execution,
    )
    from tests._helpers.lane01_candidate_action_served import (
        build_candidate_experiment_issuer_port,
    )
    from tests._helpers.lane01_wdi_profiles import CPI_PROFILE
    from tests._helpers.lane01_x03_cpi_served import (
        CPI_BASE_YEAR,
        CPI_OUTCOME_SLOT,
        CPI_SCENARIO_PROFILE_ID,
        build_x03_cpi_candidate_profile,
        build_x03_cpi_candidate_provider,
        build_x03_cpi_design_problem,
    )
    from tests.integration.core_runtime.test_candidate_experiment_action_served import (
        run_candidate_experiment_action_oracle,
    )
    from tests.integration.runtime_quality.test_lane01_x03_cpi_candidate import (
        CPI_LEVEL_RESPONSE,
    )

    monkeypatch.setattr(generation_cycle, "_N7_SOURCE_SEMANTIC_EMISSION_ENABLED", True)
    source_inputs = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "x03-cpi-source",
        outcome_variable=CPI_OUTCOME_SLOT,
        include_owner_slot_manifest=True,
        owner_knob_dictionary=generic_n4_served_replay._declared_generic_component_knobs(
            "controlled_overlay"
        ),
    )
    problem = build_x03_cpi_design_problem()
    quota = BudgetInvocationQuotaPolicy(
        allocation_id="lane01-x03-cpi-candidate-experiment",
        total_units=5,
        protected_units=1,
    )
    observed: dict[str, Any] = {}

    def serve_action(**values: Any) -> None:
        control = values["control"]
        run_id = str(values["run_id"])
        assert values["job"].kind == "natural_language_run"
        assert values["job"].state == "completed"
        issuer = build_candidate_experiment_issuer_port(
            tmp_path=tmp_path / "x03-cpi-issuer",
            artifact_store=control._artifact_store,
            source_profile=CPI_PROFILE,
        )
        quota_snapshot = control._llm_producer_settlement_store.snapshot_safe()
        quota_profile = quota_snapshot.invocation_profiles[run_id]
        assert quota_profile.allocation_id == quota.allocation_id
        assert any(
            reservation.run_id == run_id
            and reservation.profile_digest == quota_profile.profile_digest
            and reservation.purpose == "standard"
            and reservation.status == "completed"
            for reservation in quota_snapshot.invocation_reservations.values()
        )
        template = CandidateUnpricedExperimentPolicyTemplate(
            tenant_id=served.TENANT,
            cell_id=served.CELL,
            authority_entry_id=issuer.entry.entry_id,
            authority_registry_sha256=issuer.registry.content_sha256,
            authority_provision_sha256=issuer.authority.provision_content_sha256,
            attempt_id=issuer.port._provision.live_harness_receipts[0].attempt_id,
            max_http_response_bytes=65_536,
            max_http_decompressed_bytes=65_536,
            max_http_timeout_seconds=15.0,
            max_standard_n5_invocations=quota_profile.total_units - quota_profile.protected_units,
            max_metered_reentry_usd=Decimal("1.00"),
        )
        policy_owner = SimpleNamespace(
            issuer=issuer,
            template=template,
            source_profiles=SourceProfileRegistry.get_instance(),
        )
        original_providers = control._registry_providers
        control._registry_providers = replace(
            original_providers,
            source_profiles=policy_owner.source_profiles,
            candidate_unpriced_policy_bindings=(),
            candidate_unpriced_policy_templates=(template,),
        )
        try:
            with monkeypatch.context() as scoped:
                bind_candidate_test_execution_port_factory(
                    monkeypatch=scoped,
                    control_service=control,
                    fixture_port=issuer.port,
                )
                refs = prepare_candidate_experiment_policies_for_completed_job(
                    control_service=control,
                    source_job_id=values["job"].job_id,
                )
                assert len(refs) == 1
                _, policy = resolve_current_candidate_unpriced_policy(
                    control_service=control,
                    scope=read_candidate_unpriced_policy(
                        store=control._artifact_store,
                        event_log=control._diagnostic_event_log,
                        ref=refs[0],
                    ).scope,
                )
                assert policy.observed_admission is False
                assert policy.publication_authority is False
                assert policy.information_value == policy.monetary_cost == "not_established"

                def fresh_numeric_reader(**reader_values: Any) -> None:
                    reader_control = reader_values["control"]
                    history = reader_values["history"]
                    assert reader_control is not control
                    assert reader_control._artifact_store is not control._artifact_store
                    assert history.terminal.terminal_outcome == "candidate_reentry_completed"
                    assert history.action.observed_admission is False
                    assert history.action.publication_authority is False
                    assert history.action.admitted_observation_delta == 0
                    assert history.source.schema_version == CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V3
                    assert history.source.observation_class == "observed"
                    assert history.source.status == "candidate_only"
                    assert history.source.source_currentness == "source_currentness_not_established"
                    assert history.source.observation == pytest.approx(
                        CPI_PROFILE.fixture_value, rel=0, abs=1e-12
                    )
                    assert history.source.year == 2024
                    assert history.source.country_code == "UKR"
                    assert history.source.canonical_unit == "index"
                    assert history.source.target_slot_id == CPI_OUTCOME_SLOT
                    assert history.source.denominator is None
                    assert (
                        reader_control._artifact_store.get_bytes(history.source.raw_source_ref)
                        == CPI_LEVEL_RESPONSE
                    )

                    selected = _selected_compiler_candidate(
                        reader_control._artifact_store,
                        binding=history.source.requirement_basis_binding,
                        compiler_report_ref=history.source.compiler_report_ref,
                        requirement_id=history.source.requirement_id,
                        candidate_digest=history.source.candidate_digest,
                    )[-1]
                    descriptor_metadata = selected.source_assets[0]["metadata"]
                    assert selected.content_digest == history.source.candidate_digest
                    assert descriptor_metadata["indicator_id"] == "FP.CPI.TOTL"
                    assert descriptor_metadata["index_base_year"] == CPI_BASE_YEAR
                    assert descriptor_metadata["target_world_slot"] == CPI_OUTCOME_SLOT
                    assert (
                        descriptor_metadata["raw_unit"]
                        == descriptor_metadata["canonical_unit"]
                        == "index"
                    )

                    evaluation = history.evaluation or history.reentry_evaluation
                    assert evaluation is not None
                    n5_input = evaluation.input_record
                    world = n5_input.profile.context_inputs.world_model_record
                    binding = world.slot_binding(CPI_OUTCOME_SLOT)
                    assert binding is not None and binding.state_path == "market.avg_price"
                    assert binding.unit == "index"
                    assert n5_input.outcome_variable == CPI_OUTCOME_SLOT
                    assert n5_input.profile.profile_id == CPI_SCENARIO_PROFILE_ID
                    assert n5_input.profile.n5.baseline_state[CPI_OUTCOME_SLOT] == pytest.approx(
                        CPI_PROFILE.fixture_value, rel=0, abs=1e-5
                    )
                    assert n5_input.profile.n5.baseline_state[CPI_OUTCOME_SLOT] != 0.0
                    assert n5_input.profile.rule.operator_kind == "tax_relief_rate"
                    assert n5_input.profile.rule.parameter_id == "rate"
                    assert n5_input.profile.rule.target_world_slot == "global.tax_rate"
                    assert n5_input.profile.rule.unit_id == "ratio"
                    assert n5_input.profile.n5.baseline_state["global.tax_rate"] == 1.0
                    assert n5_input.materialization.value == 0.0

                    views = world_model_artifact_views(world)
                    assert views.bound_state_snapshot_ref is not None
                    state = load_state_snapshot(
                        reader_control._artifact_store,
                        snapshot_ref=views.bound_state_snapshot_ref,
                    )
                    physical_cpi = np.asarray(get_state_path(state, binding.state_path))
                    assert physical_cpi.size == 1
                    assert float(physical_cpi.item()) == pytest.approx(
                        CPI_PROFILE.fixture_value, rel=0, abs=1e-5
                    )
                    snapshot = DataSnapshot.model_validate(
                        load_core_json_artifact(
                            reader_control._artifact_store, views.data_snapshot_ref
                        )
                    )
                    assert (
                        type(snapshot.source_lineage)
                        is CandidateAcquisitionSourceDataSnapshotLineage
                    )
                    payload = load_core_json_artifact(
                        reader_control._artifact_store, snapshot.data_ref
                    )
                    selected_source = payload["acquisition"]["selected"]
                    assert selected_source["canonical_variable_id"] == CPI_OUTCOME_SLOT
                    assert selected_source["value"] == pytest.approx(
                        CPI_PROFILE.fixture_value, rel=0, abs=1e-12
                    )
                    assert selected_source["canonical_unit"] == "index"
                    with pytest.raises(DataSnapshotSourceRowNotEstablishedError):
                        validate_data_snapshot_owner_lineage(
                            reader_control._artifact_store,
                            views.data_snapshot_ref,
                            snapshot,
                        )

                    if history.evaluation is None:
                        assert history.reentry is not None
                        assert history.reentry.n5_result_ref is not None
                        assert history.selected_basis is not None
                        assert history.selected_basis.basis_role == "blocked"
                        assert history.terminal.selected_evaluation is None
                        assert history.frontier_after == history.frontier_before
                        from polisyos.runtime.http.services.acquisition_action_service import (
                            CandidateExperimentRouteProjection,
                        )

                        source_job = reader_control._control_store.get_job(
                            history.origin.source_job_id
                        )
                        assert source_job is not None
                        response = reader_values["client"].get(
                            f"/api/v1/runs/{source_job.progress['core_run_id']}"
                            "/candidate-acquisition-experiment",
                            headers=reader_values["headers"],
                        )
                        assert response.status_code == 200, response.text
                        action = CandidateExperimentRouteProjection.model_validate(
                            response.json()
                        ).current_action
                        assert action.status == "completed"
                        assert action.candidate_n5_result is not None
                        result_ref = history.reentry.n5_result_ref
                        result = action.candidate_n5_result
                        assert result.authority_purpose == "candidate_observation_only"
                        body = result.result_body
                        assert body.artifact_ref == result_ref
                        assert body.authority_purpose == "candidate_scenario_n5_only"
                        assert body.publication_authority is False
                        assert body.outcome_units == {CPI_OUTCOME_SLOT: "index"}
                        assert body.unit_provenance == "declared_candidate_model"
                    else:
                        result_ref = history.evaluation.selected.n5_result_ref
                        source_job = reader_control._control_store.get_job(
                            history.origin.source_job_id
                        )
                        assert source_job is not None
                        response = reader_values["client"].get(
                            f"/api/v1/runs/{source_job.progress['core_run_id']}",
                            headers=reader_values["headers"],
                        )
                        assert response.status_code == 200, response.text
                        projection = RunDetailsResponse.model_validate_json(
                            response.content
                        ).run.candidate_simulation
                        assert projection is not None and projection.artifact_status == "resolved"
                        assert projection.publication_authority is False
                        entries = tuple(
                            entry
                            for entry in projection.acquisition_history
                            if type(entry) is RunCandidateSimulationAcquisitionHistoryEntryV5
                            and entry.candidate_source_ref == history.action.candidate_source_ref
                            and entry.selected_evaluation is not None
                            and entry.selected_evaluation.n5_result_ref == result_ref
                        )
                        assert len(entries) == 1
                        body = entries[0].selected_n5_observation.result_body
                        assert body is not None and body.artifact_ref == result_ref
                        assert body.publication_authority is False

                    expected_effect = 0.5 * (0.0 - 1.0)
                    expected_outcome = np.float32(float(physical_cpi.item()) + expected_effect)
                    tolerance = 2.0 * float(np.spacing(expected_outcome))
                    assert expected_effect < -100 * tolerance
                    assert np.float32(float(physical_cpi.item())) != expected_outcome
                    assert any(row.run_level == "joint" for row in body.trajectories)
                    for trajectory in body.trajectories:
                        assert len(trajectory.points) == 1
                        point = trajectory.points[0]
                        assert point.step == 0
                        assert point.outcomes[CPI_OUTCOME_SLOT] == pytest.approx(
                            float(expected_outcome), rel=0, abs=tolerance
                        )
                        assert point.effects[CPI_OUTCOME_SLOT] == pytest.approx(
                            expected_effect, rel=0, abs=tolerance
                        )
                    observed["fresh_numeric_body"] = body

                def execute_after_replay(**execution_values: Any) -> None:
                    origin = execution_values["origin"]
                    report = origin.planner_report
                    routing = origin.source_cycle.value_port.candidate_n5_l1_routing
                    assert report.schema_version == "policyos.runtime.acquisition_planner.v2"
                    assert origin.source_cycle.acquisition_routing_report == report
                    assert origin.source_cycle.acquisition_cost_basis_record is None
                    assert report.candidate_lineage is not None
                    assert routing is not None
                    gap = routing.requirement_gap
                    assert gap.metadata["availability"]["variable_id"] == CPI_OUTCOME_SLOT
                    assert origin.planner_record in report.acquisition_records
                    assert origin.planner_record.requirement_gap_ref == gap.requirement_gap_id
                    execution = run_candidate_experiment_served_execution(
                        values=execution_values["values"],
                        origin=origin,
                        request=execution_values["request"],
                        decision_ref=execution_values["decision_ref"],
                        policy_owner=policy_owner,
                        monkeypatch=scoped,
                        source_profile=CPI_PROFILE,
                        wdi_response_bytes=CPI_LEVEL_RESPONSE,
                        fresh_reader_observer=fresh_numeric_reader,
                    )
                    history = execution.terminal_history
                    assert history.terminal.terminal_outcome == "candidate_reentry_completed"
                    assert execution.current_action.status == "completed"
                    assert history.action.admitted_observation_delta == 0
                    assert history.action.observed_admission is False
                    assert history.action.publication_authority is False
                    assert history.source.observation == pytest.approx(
                        CPI_PROFILE.fixture_value, rel=0, abs=1e-12
                    )
                    assert execution.execution_owner.transport_calls == [
                        (
                            "GET",
                            "https://api.worldbank.org/v2/country/UKR/indicator/FP.CPI.TOTL",
                            {
                                "date": "2024:2024",
                                "format": "json",
                                "page": "1",
                                "per_page": "1000",
                            },
                        )
                    ]
                    observed["execution"] = execution

                observed.update(
                    run_candidate_experiment_action_oracle(
                        tmp_path=tmp_path,
                        values=values,
                        policy_ref=refs[0],
                        monkeypatch=scoped,
                        idempotency_key="lane01-x03-cpi-candidate-experiment",
                        after_replay=execute_after_replay,
                    )
                )
        finally:
            control._registry_providers = original_providers

    with annual_gdp_catalog_source(source_inputs.root, monkeypatch) as prepared:
        result = served._produce_served_acquisition_history(
            tmp_path,
            monkeypatch,
            served_recorded_candidate_gateway,
            source_owner_root=source_inputs.root,
            prepared_catalog=prepared,
            provider_mode="synthetic_settled_candidate",
            seed_only_context_observer=serve_action,
            run_budget_usd=5.0,
            run_budget_scope="metered_paid_producers_and_bounded_candidate",
            candidate_acquisition_intent="bounded_experiment_voi_unknown",
            invocation_quota_policy=quota,
            seed_problem=problem,
            candidate_profile_builder=build_x03_cpi_candidate_profile,
            candidate_provider_builder=build_x03_cpi_candidate_provider,
        )
    assert result is not None
    assert "fresh_numeric_body" in observed and "execution" in observed
