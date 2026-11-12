"""Exercise a producer-issued N5 witness in an ordinary served acquisition."""

from __future__ import annotations

import struct
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import artifact_ref_identity_key
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.quality.joint_simulation_horizon import (
    JointSimulationResult,
    build_content_bound_simulation_receipt,
    verify_simulation_receipt,
)
from tests._helpers import acquisition_served_history as fixture
from tests._helpers.candidate_cycle_source_profile import (
    build_candidate_cycle_substrate_route_inputs,
)
from tests.integration.core_runtime.test_acquisition_retained_sequential_served import (
    _OwnerCallMonitor,
    _SequentialOracle,
)

pytest_plugins = ("tests._helpers.acquisition_served_history",)
_KEY = "candidate_n5_execution_content_observation"


def _replace_payload(
    result: JointSimulationResult, payload: dict[str, Any], *, rebuild_receipt: bool
) -> JointSimulationResult:
    """Create an adversarial copy of a real result, never a positive fixture."""
    receipt = result.receipt
    if rebuild_receipt:
        receipt = build_content_bound_simulation_receipt(
            engine_kind=receipt.engine_kind,
            payload=payload,
            diagnostics=payload["diagnostics"],
        )
    altered = JointSimulationResult.model_validate(
        {**payload, "receipt": receipt.model_dump(mode="json")}
    )
    altered._content_payload = payload
    verify_simulation_receipt(altered.receipt, altered.content_bound_payload())
    return altered


def test_served_actual_v5_n5_witness_reconciles_owner_quantities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway: Any,
) -> None:
    """Compare the actual V5 request with its owned numerical projection."""
    from polisyos.runtime.quality.acquisition_evaluation import (
        rebuild_selected_candidate_n5_request,
    )
    from polisyos.runtime.quality.n5_candidate_content import (
        read_candidate_n5_content_observation,
        read_candidate_n5_declared_implementation,
    )

    checked: list[str] = []

    def check_real_result(
        *,
        ctx: Any,
        oracle: Any,
        actual_b: Any,
        selected_b: Any,
        witness: Any,
        capture: Any,
        issue_equal_source: Any,
    ) -> None:
        del oracle, issue_equal_source
        with tenant_scope(None, tenant_id=fixture.TENANT, cell_id=fixture.CELL):
            result = actual_b.result
            input_ref = selected_b.n5_input_ref
            candidate, problem = actual_b.source.candidate, actual_b.source.problem
            assert capture.request is not None
            assert artifact_ref_identity_key(capture.input_ref) == artifact_ref_identity_key(
                input_ref
            )
            assert read_candidate_n5_content_observation(result, input_ref=input_ref) == witness
            assert witness.protected_use_allowed is False
            assert witness.independent_verification == "not_established"
            assert witness.completion.status == "recomputed"
            removed = deepcopy(result.content_bound_payload())
            removed["diagnostics"].pop(_KEY)
            without_observation = _replace_payload(result, removed, rebuild_receipt=True)
            with pytest.raises(ValueError, match="candidate_n5_content_observation_missing"):
                read_candidate_n5_content_observation(without_observation, input_ref=input_ref)
            from fastapi.testclient import TestClient

            with TestClient(ctx.app()) as client:
                source_store = client.app.state.runtime_container.control_service._artifact_store
                expected_request = rebuild_selected_candidate_n5_request(
                    store=source_store,
                    input_ref=input_ref,
                    run_id=selected_b.evaluation_run_id,
                    job_id=selected_b.evaluation_job_id,
                    tenant_id=fixture.TENANT,
                    cell_id=fixture.CELL,
                )
            from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes

            assert exact_n5_content_bytes(expected_request) == exact_n5_content_bytes(
                capture.request
            )
            assert read_candidate_n5_declared_implementation(
                result,
                input_ref=input_ref,
                prepared_configuration=capture.controller._prepared_configuration,
                expected_request=expected_request,
            )
            # This is the ordinary acquired-observation V5 producer, not the
            # candidate-source reentry route. Compare the native request its
            # actual builder supplied with the same numerical role projection.
            from polisyos.runtime.quality.candidate_simulation import (
                prepare_candidate_n5_request_projection_v2,
            )
            from polisyos.runtime.quality.generation_cycle import (
                JointSimulationPort,
                _value_outcome_variable,
            )

            request = capture.request
            configured = actual_b.input_record.n5
            projected = prepare_candidate_n5_request_projection_v2(configured)
            numerical = projected.numerical
            assert numerical.horizon == tuple(request.horizon.model_dump().items())
            assert numerical.seed == request.seed
            assert numerical.replications == request.replications
            assert numerical.baseline_state_ieee754_hex == tuple(
                (name, struct.pack("!d", value).hex())
                for name, value in sorted(request.baseline_state.items())
            )
            assert len(request.engine_plan) == 1
            plan = request.engine_plan[0]
            assert plan.engine_kind == numerical.engine_kind
            atom = actual_b.input_record.materialization.derived_n5_atom
            assert request.intervention_atoms == (atom,)
            outcome = _value_outcome_variable(candidate, problem)
            assert request.selected_outcomes == (outcome,)
            assert plan.variable_map == JointSimulationPort._joint_simulation_variable_map(
                atoms=(atom,), outcome=outcome, raw_hint=None
            )
            from polisyos.core.artifacts import load_core_json_artifact
            from polisyos.ir import NCMSpec

            with TestClient(ctx.app()) as client:
                store = client.app.state.runtime_container.control_service._artifact_store
                selected_ncm = NCMSpec.model_validate(
                    load_core_json_artifact(store, actual_b.input_record.ncm_ref)
                )
            assert plan.ncm_spec == selected_ncm
            for name in (
                "evidence_state",
                "comparator_profile",
                "coupling_graph",
                "world_credal_state_before",
                "candidate_intent",
                "member_basis",
                "source_candidate_relationship",
                "composition_status",
                "composition_limitation_code",
                "child_to_parent_refinement_status",
                "child_to_parent_refinement_limitation_code",
            ):
                assert getattr(request, name) == type(request).model_fields[name].get_default(
                    call_default_factory=True
                )
            assert projected.operational.budget_ref == request.budget_ref
            assert projected.output_labels.comparator_evidence_refs == request.comparator_refs
            assert (
                prepare_candidate_n5_request_projection_v2(
                    configured.model_copy(update={"budget_ref": configured.budget_ref + ".other"})
                ).numerical
                == numerical
            )
            assert (
                prepare_candidate_n5_request_projection_v2(
                    configured.model_copy(update={"replications": configured.replications + 1})
                ).numerical
                != numerical
            )
            checked.append(actual_b.input_record.content_hash)

    source = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "candidate-source",
        include_owner_slot_manifest=True,
    )
    with _OwnerCallMonitor() as monitor:
        oracle = _SequentialOracle(monkeypatch, monitor, after_real_b=check_real_result)
        produced = fixture._produce_served_acquisition_history(
            tmp_path,
            monkeypatch,
            served_recorded_candidate_gateway,
            source_owner_root=source.root,
            sequential_oracle=oracle,
            provider_mode="synthetic_settled_candidate",
        )
    assert produced is not None and produced["run_id"] and produced["candidate_id"]
    assert len(checked) == 1


def assert_live_initial_a_capture(**values: Any) -> tuple[str, str]:
    import json

    from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, load_core_json_artifact
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality.candidate_simulation import CandidateSimulationN5InputV5
    from polisyos.runtime.quality.generation_cycle import load_joint_simulation_result
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateScenarioSourceRecordV3,
    )

    control, job, run_id = values["control"], values["job"], values["run_id"]
    terminal = control.resolve_completed_control_job_core_run_source(
        job,
        expected_control_run_id=run_id,
        tenant_id=fixture.TENANT,
        cell_id=fixture.CELL,
    )
    assert terminal.manifest.status == "ok"
    outputs = tuple(
        ref
        for ref in terminal.manifest.outputs
        if ref.kind == "runtime.compiled_recursive_generation_cycle"
    )
    assert len(outputs) == 1
    selected = ArtifactRef.model_validate(
        job.progress["compiled_recursive_generation_cycle_artifact_ref"]
    )
    assert artifact_ref_identity_key(outputs[0]) == artifact_ref_identity_key(selected)
    assert str(selected.artifact_id) == job.progress["compiled_recursive_generation_cycle_ref"]

    fresh = FileSystemCAS.open_existing_read_only(values["cas_root"])
    assert fresh is not control._artifact_store
    compiled = CompiledRecursiveGenerationCycleRun.model_validate(
        load_core_json_artifact(fresh, selected)
    )
    cycles = tuple(
        (leaf.cycle_run, cycle)
        for leaf in compiled.recursive_run.leaf_nodes
        if leaf.cycle_run is not None
        for cycle in leaf.cycle_run.cycles
    )
    assert len(cycles) == 1
    _generation, cycle = cycles[0]
    assert cycle.simulation.status == "joint_simulated"
    simulation = cycle.simulation
    input_ref = simulation.candidate_simulation_n5_input_ref
    result_ref = simulation.simulation_result_ref
    source_ref = simulation.candidate_simulation_n4_source_ref
    assert input_ref is not None and result_ref is not None and source_ref is not None

    candidate_source = GenerationSourceRepository(fresh).load_candidate_scenario_source_for_n5(
        source_ref,
        expected_run_id=run_id,
        expected_job_id=job.job_id,
        expected_tenant_id=fixture.TENANT,
        expected_cell_id=fixture.CELL,
    )
    assert type(candidate_source) is N4CandidateScenarioSourceRecordV3
    assert candidate_source.candidate.candidate_id == cycle.selected_candidate_ref
    assert candidate_source.profile_selection_ref == values["profile_selection_ref"]
    l6_bundle = candidate_source.profile.context_inputs.intervention_substrate
    assert l6_bundle is not None
    declared_slots = {
        slot
        for family in l6_bundle.slot_family_manifest["families"].values()
        for slot in family["slots"]
    }
    assert candidate_source.profile.rule.target_world_slot == "government.balance"
    assert "government.balance" in declared_slots

    n5_input = CandidateSimulationN5InputV5.model_validate(
        load_core_json_artifact(fresh, input_ref)
    )
    assert n5_input.original_candidate_id == cycle.selected_candidate_ref
    assert n5_input.original_candidate_hash == cycle.selected_candidate_content_hash
    assert n5_input.profile.profile_selection_ref == values["profile_selection_ref"]
    assert artifact_ref_identity_key(n5_input.n4_source_ref) == artifact_ref_identity_key(
        source_ref
    )
    expected_world_model_hash = n5_input.materialization.world_model_record_hash
    expected_outcome = candidate_source.source_record.model_declaration.outcome_variable
    selected_atom_id = candidate_source.candidate.atom.intervention_id
    assert expected_outcome == n5_input.outcome_variable
    assert selected_atom_id == n5_input.materialization.derived_n5_atom.intervention_id
    result = load_joint_simulation_result(
        result_ref,
        store=fresh,
        expected_world_model_record_content_hash=expected_world_model_hash,
        expected_atom_ids=(selected_atom_id,),
        expected_selected_outcomes=(expected_outcome,),
        expected_receipt_payload_hash=simulation.simulation_ref,
    )
    assert result.receipt.payload_hash == simulation.simulation_ref
    assert len(result.trajectories) == 2
    assert result.receipt.engine_kind == "ncm_parallel_worlds"
    assert result.diagnostics.get("physical_work_capture_status") == "observed"
    assert result.diagnostics.get("physical_work_units") == 2
    from polisyos.runtime.quality.acquisition_evaluation import (
        rebuild_selected_candidate_n5_request,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        PreparedJointSimulationConfiguration,
    )
    from polisyos.runtime.quality.n5_candidate_content import (
        read_candidate_n5_content_observation,
        read_candidate_n5_declared_implementation,
    )

    observation = read_candidate_n5_content_observation(result, input_ref=input_ref)
    assert observation.completion.status == "recomputed"
    assert observation.protected_use_allowed is False
    assert observation.independent_verification == "not_established"
    expected_request = rebuild_selected_candidate_n5_request(
        store=fresh,
        input_ref=input_ref,
        run_id=run_id,
        job_id=job.job_id,
        tenant_id=fixture.TENANT,
        cell_id=fixture.CELL,
    )
    assert read_candidate_n5_declared_implementation(
        result,
        input_ref=input_ref,
        expected_request=expected_request,
        prepared_configuration=PreparedJointSimulationConfiguration.model_validate(
            observation.consumed_configuration
        ),
    )
    result = (run_id, cycle.selected_candidate_ref)
    print(
        json.dumps(
            {
                "initial_a_live_n5": "PASS",
                "run_id": run_id,
                "compiled_cycle_ref": str(selected),
                "n4_source_ref": str(source_ref),
                "n5_input_ref": str(input_ref),
                "n5_result_ref": str(result_ref),
                "n5_input_content_hash": n5_input.content_hash,
                "witness_content_hash": observation.content_hash,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return result


@pytest.mark.integration
def test_served_actual_v5_n5_initial_a_capture_is_live_before_b(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway: Any,
) -> None:
    """The ordinary seed run binds a real N4 source and live N5 capture before B."""
    source = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "candidate-source",
        include_owner_slot_manifest=True,
    )
    observed: list[tuple[str, str]] = []

    def observe_initial_a(**values: Any) -> None:
        observed.append(assert_live_initial_a_capture(**values))

    with _OwnerCallMonitor() as monitor:
        produced = fixture._produce_served_acquisition_history(
            tmp_path,
            monkeypatch,
            served_recorded_candidate_gateway,
            source_owner_root=source.root,
            provider_mode="synthetic_settled_candidate",
            seed_only_observer=observe_initial_a,
        )
        monitor.assert_slots_unchanged()
        counts = monitor.snapshot()

    assert produced is not None and produced["job_id"] and produced["run_id"]
    assert len(observed) == 1 and observed[0][0] == produced["run_id"]
    assert observed[0][1]
    assert counts["n4"] >= 1 and counts["n5"] == 1
