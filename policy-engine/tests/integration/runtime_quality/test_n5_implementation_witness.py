"""Exercise a producer-issued N5 witness in an ordinary served acquisition."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from numpy._core import _methods as numpy_methods

from polisyos.core.artifacts import artifact_ref_identity_key
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.methods.catalog.causal import ncm_engine
from polisyos.runtime.quality import joint_simulation_horizon as horizon_module
from polisyos.runtime.quality import n5_execution_basis as basis
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
from tests.integration.runtime_quality._n5_consumed_binding_falsifiers import (
    assert_real_n5_instance_entry_shadows_refused,
    assert_unconsumed_slots_do_not_change_real_n5_witness,
)

pytest_plugins = ("tests._helpers.acquisition_served_history",)
_KEY = "n5_execution_implementation_witness"


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
    """The actual served B owns its witness; changed inputs, results and owners do not."""
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
        del ctx, issue_equal_source
        with tenant_scope(None, tenant_id=fixture.TENANT, cell_id=fixture.CELL):
            result = actual_b.result
            input_ref = selected_b.n5_input_ref
            result_ref = selected_b.n5_result_ref
            candidate, problem = actual_b.source.candidate, actual_b.source.problem
            assert capture._admission is not None
            port = capture._admission.port
            assert capture._admission.controller is capture._controller is port._controller
            assert capture._admission.request is capture._request
            assert artifact_ref_identity_key(capture._admission.input_ref) == (
                artifact_ref_identity_key(input_ref)
            )
            assert capture._admission.input_content_hash == actual_b.input_record.content_hash
            assert basis.reconcile_live_n5_implementation(result, input_ref=input_ref) == witness
            assert witness.predicate_provenance == "recomputed" and not witness.reason_codes
            assert witness.input_ref_identity == artifact_ref_identity_key(input_ref)
            assert input_ref.manifest_profile_sha256 is not None
            assert result.trajectories
            consumed_configuration = horizon_module.read_joint_simulation_configuration(
                capture._controller
            )
            prepared_configuration = horizon_module.prepare_joint_simulation_configuration()
            assert (
                type(consumed_configuration) is horizon_module.PreparedJointSimulationConfiguration
            )
            assert witness.consumed_configuration_values == basis._exact_native_content(
                consumed_configuration
            )
            assert witness.consumed_configuration_values == basis._exact_native_content(
                prepared_configuration
            )
            observed = {
                (row[0], row[1]) for row in witness.implementation["source"]["executed_code"]
            }
            controller_run = horizon_module.JointSimulationHorizonController.run
            numerical_entry = ncm_engine.NCMEngineMethod.pure_step
            assert (controller_run.__module__, controller_run.__code__.co_qualname) in observed
            assert (numerical_entry.__module__, numerical_entry.__code__.co_qualname) in observed
            # Capture-only configuration introspection is not numerical work.
            # No production callable is swapped to manufacture this context.
            for introspection in (
                horizon_module.read_joint_simulation_configuration,
                horizon_module.prepare_joint_simulation_configuration,
            ):
                assert (
                    introspection.__module__,
                    introspection.__code__.co_qualname,
                ) not in observed
            monitor_callback = oracle.monitor._on_start.__func__
            assert (
                monitor_callback.__module__,
                monitor_callback.__code__.co_qualname,
            ) not in observed
            assert any(
                row[0] == ncm_engine.__name__ and row[1] == "_parallel_worlds"
                for row in witness.implementation["source"]["executed_code"]
            ), "the selected NCM helper was not observed"

            # Reconstruct only the unbound copy of this actual result, for
            # adversarial relabeling checks; never use it as a positive witness.
            original_payload = deepcopy(result.content_bound_payload())
            del original_payload["diagnostics"][_KEY]
            original = _replace_payload(result, original_payload, rebuild_receipt=True)
            assert basis.exact_n5_content_bytes(original.content_bound_payload()) == (
                capture._result_bytes
            )

            # Both selectors name real CAS artifacts from this execution.
            assert artifact_ref_identity_key(result_ref) != artifact_ref_identity_key(input_ref)
            with pytest.raises(ValueError, match="n5_execution_witness_input_mismatch"):
                basis.reconcile_live_n5_implementation(result, input_ref=result_ref)
            with pytest.raises(ValueError, match="n5_execution_capture_input_relabelled"):
                basis.bind_n5_execution_implementation(
                    original, input_ref=result_ref, capture=capture
                )

            # This input changes the actual result's world state. GY's legacy
            # hash drops the key recursively and cannot decide this equality.
            changed_request = capture._request.model_copy(deep=True)
            assert changed_request.world_credal_state_before.get("runtime_metrics") != {
                "witness_probe": 1
            }
            changed_request.world_credal_state_before["runtime_metrics"] = {"witness_probe": 1}
            with (
                pytest.raises(ValueError, match="n5_implementation_input_request_mismatch"),
                basis.observe_candidate_n5_execution_input(
                    port=port,
                    candidate=candidate,
                    problem=problem,
                    request=changed_request,
                    input_ref=input_ref,
                ),
            ):
                pass
            # A receipt digest is not the equality predicate: force a collision.
            with monkeypatch.context() as mutation:
                mutation.setattr(
                    basis, "exact_n5_content_hash", lambda _value: "sha256:" + "0" * 64
                )
                with (
                    pytest.raises(ValueError, match="n5_implementation_input_request_mismatch"),
                    basis.observe_candidate_n5_execution_input(
                        port=port,
                        candidate=candidate,
                        problem=problem,
                        request=changed_request,
                        input_ref=input_ref,
                    ),
                ):
                    pass

            # The legacy GY receipt ignores this field. A witness must bind the
            # complete actual result even when that ordinary receipt still verifies.
            altered_payload = deepcopy(result.content_bound_payload())
            for key in ("world_credal_state_before", "world_credal_state_after"):
                altered_payload[key]["runtime_metrics"] = {"witness_probe": 1}
            altered = _replace_payload(result, altered_payload, rebuild_receipt=False)
            with pytest.raises(ValueError, match="n5_execution_witness_result_mismatch"):
                basis.reconcile_live_n5_implementation(altered, input_ref=input_ref)
            unbound_payload = deepcopy(original.content_bound_payload())
            for key in ("world_credal_state_before", "world_credal_state_after"):
                unbound_payload[key]["runtime_metrics"] = {"witness_probe": 1}
            altered_original = _replace_payload(original, unbound_payload, rebuild_receipt=False)
            with pytest.raises(ValueError, match="n5_execution_capture_result_relabelled"):
                basis.bind_n5_execution_implementation(
                    altered_original, input_ref=input_ref, capture=capture
                )

            # A rehashed caller witness is structurally valid, but was not issued
            # by the real producer's registry.
            forged_payload = deepcopy(result.content_bound_payload())
            forged_witness = forged_payload["diagnostics"][_KEY]
            forged_witness["request_content_hash"] = "sha256:" + "e" * 64
            forged_witness["content_hash"] = basis.exact_n5_content_hash(
                {name: value for name, value in forged_witness.items() if name != "content_hash"}
            )
            forged = _replace_payload(result, forged_payload, rebuild_receipt=True)
            with pytest.raises(ValueError, match="n5_execution_witness_not_producer_observed"):
                basis.reconcile_live_n5_implementation(forged, input_ref=input_ref)

            # Independent controls keep genuine selected output/source markers
            # intact while changing the actual next-call entry binding.
            assert_real_n5_instance_entry_shadows_refused(
                port=port,
                result=result,
                request=capture._request,
                input_ref=input_ref,
                monkeypatch=monkeypatch,
            )
            assert_unconsumed_slots_do_not_change_real_n5_witness(
                result=result,
                input_ref=input_ref,
                monkeypatch=monkeypatch,
            )

            real_helper = ncm_engine._parallel_worlds
            with monkeypatch.context() as mutation:
                mutation.setattr(ncm_engine, "_parallel_worlds", lambda *a, **k: [])
                with pytest.raises(ValueError):
                    basis.reconcile_live_n5_implementation(result, input_ref=input_ref)
            assert ncm_engine._parallel_worlds is real_helper

            # NCM reads np.mean for each actual outcome. This transitive Python
            # helper is called by NumPy without changing np.mean or native images.
            real_numpy_mean = numpy_methods._mean
            sample = np.asarray([0.0, 2.0])
            assert float(np.mean(sample)) == 1.0

            def shifted_numpy_mean(*args: Any, **kwargs: Any) -> Any:
                return real_numpy_mean(*args, **kwargs) + 1.0

            with monkeypatch.context() as mutation:
                mutation.setattr(numpy_methods, "_mean", shifted_numpy_mean)
                assert float(np.mean(sample)) == 2.0
                with pytest.raises(ValueError):
                    basis.reconcile_live_n5_implementation(result, input_ref=input_ref)
            assert numpy_methods._mean is real_numpy_mean

            # The already-active numerical caller resolves this imported class to
            # construct the actual NCM query. Keep the original type admissible to
            # NCM while changing the evidence supplied to its constructor.
            original_query_type = horizon_module.NCMQueryData
            ncm_spec = capture._request.engine_plan[0].ncm_spec
            evidence = dict(capture._request.baseline_state)
            assert ncm_spec is not None and evidence

            class ChangedQueryData(original_query_type):
                def __init__(self, **values: Any) -> None:
                    values["evidence"] = {
                        name: value + 1.0 for name, value in values["evidence"].items()
                    }
                    super().__init__(**values)

            original_query = original_query_type(ncm_spec=ncm_spec, evidence=evidence)
            with monkeypatch.context() as mutation:
                mutation.setattr(horizon_module, "NCMQueryData", ChangedQueryData)
                changed_query = horizon_module.NCMQueryData(ncm_spec=ncm_spec, evidence=evidence)
                assert isinstance(changed_query, original_query_type)
                assert changed_query.evidence != original_query.evidence
                with pytest.raises(ValueError):
                    basis.reconcile_live_n5_implementation(result, input_ref=input_ref)
            assert horizon_module.NCMQueryData is original_query_type

            # Replace the actual registry entry while retaining its FQN and
            # signature. The original historical NCM class remains live.
            registry = port._controller._registry
            decision = next(item for item in result.engine_decisions if item.decision == "selected")
            assert decision.method_fqn is not None
            entry = registry.get_entry(decision.method_fqn)
            assert entry is not None
            original_method = registry.get(decision.method_fqn)

            class SameFQNReplacement:
                signature = original_method.signature
                metadata = original_method.metadata

                @staticmethod
                def pure_step(*args: Any, **kwargs: Any) -> dict[str, Any]:
                    return {"counterfactual_result": {"world_summaries": []}}

            with monkeypatch.context() as mutation:
                mutation.setattr(entry, "_cached_class", SameFQNReplacement)
                assert registry.get(decision.method_fqn) is SameFQNReplacement
                with pytest.raises(ValueError):
                    basis.reconcile_live_n5_implementation(result, input_ref=input_ref)
            assert registry.get(decision.method_fqn) is original_method
            assert basis.reconcile_live_n5_implementation(result, input_ref=input_ref) == witness
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
    assert len(checked) == 1, "no genuine served B result reached the witness oracle"


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
    witness = basis.reconcile_live_n5_implementation(result, input_ref=input_ref)
    assert witness.predicate_provenance == "recomputed" and not witness.reason_codes
    assert witness.input_ref_identity == artifact_ref_identity_key(input_ref)
    with basis._LOCK:
        issued = basis._ISSUED.get(witness.content_hash)
    assert issued is not None and issued.witness == witness
    capture = issued.capture
    assert capture._admission is not None
    assert artifact_ref_identity_key(capture._admission.input_ref) == (
        artifact_ref_identity_key(input_ref)
    )
    assert capture._admission.input_content_hash == n5_input.content_hash
    executed = {(row[0], row[1]) for row in witness.implementation["source"]["executed_code"]}
    assert (
        horizon_module.JointSimulationHorizonController.run.__module__,
        horizon_module.JointSimulationHorizonController.run.__code__.co_qualname,
    ) in executed
    assert (
        ncm_engine.NCMEngineMethod.pure_step.__module__,
        ncm_engine.NCMEngineMethod.pure_step.__code__.co_qualname,
    ) in executed
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
                "witness_content_hash": witness.content_hash,
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
