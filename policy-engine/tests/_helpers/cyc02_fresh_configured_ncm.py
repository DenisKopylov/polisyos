"""Separate-process procurement N5 production and limited historical consumption.

The producer keeps its N5-only purpose. The reader derives a conditional,
receipt-free analytical projection; it does not execute a new N8 control job.
All transport/model inputs are explicitly synthetic and remain below the
caller's temporary root. No environment, fixture archive or CAS is copied.
"""

from __future__ import annotations

import json
import math
import os
import sys
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from typing import Any


def _environment(root: Path) -> None:
    values = {
        "POLISYOS_EXECUTION_PROFILE": "dev",
        "POLISYOS_CONTROL_WORKER_BACKEND": "external",
        "POLISYOS_CONTROL_STATE_STORE_BACKEND": "sqlite",
        "POLISYOS_CAS_BACKEND": "filesystem",
        "POLISYOS_CONTROL_SQLITE_PATH": str(root / "control.sqlite3"),
        "POLISYOS_CACHE_HOME": str(root / "runtime-cache"),
        "POLISYOS_LLM_GATEWAY_API_KEY": "sk-synthetic-local-gateway-key",
        "POLISYOS_LLM_GATEWAY_BASE_URL": "http://127.0.0.1:1/v1",
        "POLISYOS_LLM_GATEWAY_MAX_RETRIES": "0",
        "POLISYOS_LLM_CACHE_TTL_S": "0",
        "POLISYOS_LLM_CACHE_MAXSIZE": "0",
        "POLISYOS_LLM_PROMPT_SANITIZER": "false",
        "JAX_PLATFORMS": "cpu",
    }
    os.environ.update(values)


def _app(root: Path, **kwargs: Any) -> Any:
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.http.services.control_registry_providers import (
        resolve_control_registry_providers,
    )
    from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver

    cas_root = root / ".polisyos"
    context = build_runtime_api_context(cas_root=cas_root, core_runs_root=cas_root / "runs")
    providers = resolve_control_registry_providers(
        capability_resolver=RequirementToCapabilityResolver.governed_fixture(
            Path(__file__).resolve().parents[2]
        ),
        catalog_source_selection=kwargs.get("catalog_source_selection"),
        catalog_run_profile=kwargs.get("catalog_run_profile"),
    )
    return create_runtime_api_app(
        cas_root=cas_root,
        container_overrides=RuntimeContainerOverrides(
            runtime_api_context=context, control_registry_providers=providers
        ),
        allow_fixture_identity=True,
        **kwargs,
    )


def _read_selected(service: Any, handoff: dict[str, Any]) -> Any:
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    return GenerationSourceRepository(
        service._artifact_store
    )._read_candidate_simulation_v5_numerical_output(
        ref=ArtifactRef.model_validate(handoff["execution_ref"]),
        expected_run_id=handoff["control_run_id"],
        expected_job_id=handoff["job_id"],
        expected_tenant_id=handoff["tenant_id"],
        expected_cell_id=handoff["cell_id"],
    )


def _witness(read: Any) -> dict[str, Any]:
    """Preserve every numerical trajectory, selected ref and model unit binding."""
    from polisyos.pdc import gy_content_hash

    record = read.input_record
    declaration = read.source.source_record.model_declaration
    result = read.result
    expected = Fraction(str(declaration.outcome_per_target_unit)) * (
        Fraction(record.materialization.value) - Fraction(str(declaration.target_baseline))
    )
    assert expected == Fraction(1, 2)
    scale = max(1.0, abs(declaration.target_baseline), abs(declaration.outcome_baseline))
    bound = 8 * math.ulp(scale)
    outcome = record.outcome_variable
    samples = []
    for trajectory in result.trajectories:
        for point in trajectory.points:
            assert point.effect[outcome] == _absolute_approx(float(expected), bound)
            if point.replication_sampling is not None:
                assert point.replication_sampling.seeds == (11, 12)
                assert point.replication_sampling.replicate_count == record.n5.replications == 2
                for sample in point.replication_sampling.samples:
                    assert sample.effects[outcome] == _absolute_approx(float(expected), bound)
                    samples.append([sample.seed, sample.effects[outcome]])
    assert samples
    return {
        "result_payload_hash": gy_content_hash(result.content_bound_payload()),
        "result_ref": read.execution.n5_result_ref.model_dump(mode="json"),
        "input_ref": read.execution.n5_input_ref.model_dump(mode="json"),
        "n4_ref": read.execution.n4_source_ref.model_dump(mode="json"),
        "context_ref": read.execution.context_job_ref.model_dump(mode="json"),
        "ncm_ref": record.ncm_ref.model_dump(mode="json"),
        "model_declaration_ref": record.model_declaration_ref.model_dump(mode="json"),
        "world_model_record_hash": result.world_model_record_content_hash,
        "atom_ids": list(result.atom_ids),
        "selected_outcomes": list(result.selected_outcomes),
        "horizon": result.horizon.model_dump(mode="json"),
        "trajectories": [item.model_dump(mode="json") for item in result.trajectories],
        "persisted_blockers": list(result.promotion_ready_value_packet["authority_blockers"]),
        "outcome": outcome,
        "outcome_unit": declaration.outcome_unit_id,
        "expected_effect": float(expected),
        "absolute_error_bound": bound,
        "sample_effects": samples,
    }


def _absolute_approx(expected: float, bound: float) -> Any:
    """Use an absolute binary64 bound, with relative tolerance disabled."""
    import pytest

    return pytest.approx(expected, rel=0, abs=bound)


def _produce(root: Path, *, late_fault: bool = False) -> dict[str, Any]:
    import pytest
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts import ArtifactRef, read_core_json_artifact
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.http.services.control import generation_cycle as cycle_service
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.http.services.control_plane_store import (
        _control_job_execution_scope_from_event,
    )
    from tests._helpers.candidate_cycle_source_profile import (
        bind_candidate_cycle_kref_builder_root,
        build_candidate_cycle_catalog_serving_source,
        build_candidate_cycle_substrate_route_inputs,
        install_candidate_cycle_l6_source_root_reader,
    )
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests._helpers.controlled_candidate_profile import (
        ControlledCandidateGateway,
        _configured_procurement_profile,
        _controlled_procurement_recording,
        _current_compiler_problem,
        synthetic_controlled_candidate_provider_profile,
    )
    from tests._helpers.generic_n4_served_replay import _declared_generic_component_knobs
    from tests.unit.runtime.http.test_control_job_execution_intent import _valid_intake_for_mode
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
    )
    from tools.quality.validation import check_layer3_gy_design_generation_contract as n4_contract

    _environment(root)
    product = Path(__file__).resolve().parents[2]
    recording = next(
        item
        for item in n4_contract._load_recordings(product)
        if item.get("design_problem_id") == "gy_n4_cgf_decisive_capture_1_20260704_092222_049411"
    )
    original = _current_compiler_problem(recording)
    controlled = _controlled_procurement_recording(
        recording, outcome_variable=original.outcome_of_interest.target_variable
    )
    problem = _current_compiler_problem(controlled)
    provider = synthetic_controlled_candidate_provider_profile(
        recording, controlled, problem=problem, evidence_root=root / "provider-inputs"
    )
    cas_root = root / ".polisyos"
    context = build_runtime_api_context(cas_root=cas_root, core_runs_root=cas_root / "runs")
    source_inputs = build_candidate_cycle_substrate_route_inputs(
        root / "bounded-source",
        include_owner_slot_manifest=True,
        owner_knob_dictionary=_declared_generic_component_knobs("controlled_overlay"),
    )
    source_root = source_inputs.root
    catalog_selection, catalog_source = build_candidate_cycle_catalog_serving_source(source_root)
    assert catalog_source.database_path.is_relative_to(root)
    compiler = cycle_service.build_design_problem_from_nl_request

    async def compile_with_controlled_transport(**kwargs: Any) -> Any:
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        compiled_problem = await compiler(**kwargs)
        gateway.admit_compiled_problem(compiled_problem)
        return compiled_problem

    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.services.control_registry_providers import (
        resolve_control_registry_providers,
    )
    from polisyos.runtime.quality import credal_reference, design_generation
    from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver
    from polisyos.runtime.quality.substrate_registry import (
        catalog_serving_source_scope,
        current_catalog_serving_source,
    )

    with pytest.MonkeyPatch.context() as patch, ControlledCandidateGateway() as gateway:
        patch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", gateway.base_url)
        gateway.set_fixture(controlled, problem=problem, provider_profile=provider)
        _, bind_l6, assert_l6 = install_candidate_cycle_l6_source_root_reader(
            patch, code_root=product, source_owner_root=source_root
        )
        with catalog_serving_source_scope(catalog_source):
            profile, declaration = _configured_procurement_profile(
                recorded_problem=problem,
                artifact_store=context.store,
                tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                cell_id="cell-a",
                tmp_path=root,
                source_root=source_root,
                repo_root=source_root,
            )
        bind_l6(profile.context_inputs.intervention_substrate)
        assert_l6()
        observed_roots: list[str] = []
        actual_kref = bind_candidate_cycle_kref_builder_root(
            credal_reference.build_credal_reference,
            expected_repo_root=source_root,
            observed_repo_roots=observed_roots,
        )

        def selected_kref(repo_root: Path, *args: Any, **kwargs: Any) -> Any:
            selected = current_catalog_serving_source()
            assert selected is not None
            assert selected.database_path == catalog_source.database_path
            return actual_kref(repo_root, *args, **kwargs)

        patch.setattr(credal_reference, "build_credal_reference", selected_kref)
        patch.setattr(design_generation, "build_credal_reference", selected_kref)
        patch.setattr(
            cycle_service, "build_design_problem_from_nl_request", compile_with_controlled_transport
        )
        late_observations: list[Any] = []
        if late_fault:
            from polisyos.runtime.quality import generation_cycle as generation_module
            from polisyos.runtime.quality.generation_cycle import GenerationCycleError

            original_value = generation_module._configured_candidate_value_observation
            late_error = GenerationCycleError(
                "res03.configured_candidate_late_value_failure",
                "controlled failure after real N5 persistence",
            )
            original_cause = RuntimeError("cyc02 controlled downstream value fault")

            def fail_after_persisted_n5(candidate_id: str, simulation: Any) -> Any:
                if simulation.status == "joint_simulated":
                    assert simulation.candidate_id == candidate_id
                    assert simulation.simulation_result_ref is not None
                    assert simulation.diagnostics["candidate_simulation_execution_selected_ref"]
                    late_observations.append(simulation)
                    raise late_error from original_cause
                return original_value(candidate_id, simulation)

            patch.setattr(
                generation_module,
                "_configured_candidate_value_observation",
                fail_after_persisted_n5,
            )
        app = create_runtime_api_app(
            cas_root=cas_root,
            container_overrides=RuntimeContainerOverrides(
                runtime_api_context=context,
                control_registry_providers=resolve_control_registry_providers(
                    capability_resolver=RequirementToCapabilityResolver.governed_fixture(product),
                    catalog_source_selection=catalog_selection,
                    catalog_run_profile=catalog_selection.catalog_run_profile,
                ),
            ),
            allow_fixture_identity=True,
            candidate_simulation_profiles=(profile,),
            candidate_simulation_model_declarations=(declaration,),
            repo_root=source_root,
            catalog_source_selection=catalog_selection,
            catalog_run_profile=catalog_selection.catalog_run_profile,
        )
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/control/runs/nl",
                headers={"Idempotency-Key": "cyc02-fresh-configured-ncm"},
                json={
                    "request": problem.nl_provenance.raw_request,
                    "llm_model": str(recording["model_id"]),
                    "context": {
                        "evaluation_safety_attempt": _valid_intake_for_mode(
                            "simulate_only"
                        ).model_dump(mode="json")
                    },
                },
            )
            assert response.status_code == 200, response.text
            accepted = response.json()
            service = app.state._control_service
            assert (
                dispatch_one_control_job(
                    store=service._control_store,
                    handler=service._process_control_job,
                    expected_job_id=accepted["job_id"],
                )
                == accepted["job_id"]
            )
            job = service._control_store.get_job(accepted["job_id"])
            expected_state = "failed" if late_fault else "completed"
            assert job is not None and job.state == expected_state, job
            scope = _control_job_execution_scope_from_event(
                service._control_store.get_job_created_event_payload(job.job_id)
            )
            assert scope.status == "established" and scope.tenant_id and scope.cell_id
            with tenant_scope(None, tenant_id=scope.tenant_id, cell_id=scope.cell_id):
                if late_fault:
                    assert job.error_message == str(late_error)
                    return _late_fault_handoff(
                        root, service, job, scope, late_observations, source_root, catalog_selection
                    )
                compiled_ref = ArtifactRef.model_validate(
                    job.progress["compiled_recursive_generation_cycle_artifact_ref"]
                )
                compiled = CompiledRecursiveGenerationCycleRun.model_validate(
                    read_core_json_artifact(service._artifact_store, compiled_ref).value
                )
                (leaf,) = compiled.recursive_run.leaf_nodes
                assert leaf.cycle_run is not None
                completed_cycles = [
                    item
                    for item in leaf.cycle_run.cycles
                    if item.simulation.status == "joint_simulated"
                ]
                assert len(completed_cycles) == 1
                cycle = completed_cycles[0]
                assert observed_roots and set(observed_roots) == {str(source_root)}
                assert cycle.value_port.status == "value_pending_n8"
                assert cycle.value_port.authority_blockers == ("candidate_scenario_n5_only",)
                handoff = {
                    "producer_pid": os.getpid(),
                    "job_id": job.job_id,
                    "control_run_id": str(job.run_id),
                    "core_run_id": job.progress["core_run_id"],
                    "tenant_id": scope.tenant_id,
                    "cell_id": scope.cell_id,
                    "compiled_ref": compiled_ref.model_dump(mode="json"),
                    "execution_ref": cycle.simulation.diagnostics[
                        "candidate_simulation_execution_selected_ref"
                    ],
                    "producer_n8_status": cycle.value_port.status,
                    "provider_input": provider.descriptor(),
                    "source_root": str(source_root),
                    "catalog_selection": catalog_selection.model_dump(mode="json"),
                    "actual_kref_roots": observed_roots,
                }
                read = _read_selected(service, handoff)
                handoff["witness"] = _witness(read)
                handoff["simulation"] = cycle.simulation.model_dump(mode="json")
                return handoff


def _consume(
    root: Path, handoff: dict[str, Any], *, read_failed_terminal: bool = False
) -> dict[str, Any]:
    import pytest
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts import ArtifactOwnershipError, ArtifactRef, FileSystemCAS
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextArtifactOwner
    from polisyos.runtime.quality.generation_cycle import (
        SimulationPortObservation,
        _DefaultSimulationBoundFoundryValuePort,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController
    from polisyos.runtime.quality.substrate_registry import CatalogServingSourceSelection

    _environment(root)

    def no_new_n5(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("fresh historical consumption must not execute N5")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(JointSimulationHorizonController, "run", no_new_n5)
        selection = CatalogServingSourceSelection.model_validate(handoff["catalog_selection"])
        app = _app(
            root,
            candidate_simulation_profiles=(),
            candidate_simulation_model_declarations=(),
            repo_root=Path(handoff["source_root"]),
            catalog_source_selection=selection,
            catalog_run_profile=selection.catalog_run_profile,
        )
        with TestClient(app) as client:
            response = client.get("/api/v1/runs/" + handoff["core_run_id"])
            assert response.status_code == 200, response.text
            projection = response.json()["run"]["candidate_simulation"]
            assert projection["artifact_status"] == "resolved", projection
            service = app.state._control_service
            with tenant_scope(None, tenant_id=handoff["tenant_id"], cell_id=handoff["cell_id"]):
                read = _read_selected(service, handoff)
                witness = _witness(read)
                assert witness == handoff["witness"]
                expected = {
                    "expected_run_id": handoff["control_run_id"],
                    "expected_job_id": handoff["job_id"],
                    "expected_tenant_id": handoff["tenant_id"],
                    "expected_cell_id": handoff["cell_id"],
                }
                context = CycleSubstrateContextArtifactOwner(
                    store=service._artifact_store
                ).resolve_historical_job_artifact(
                    read.execution.context_job_ref, problem=read.source.problem, **expected
                )
                atom = read.input_record.materialization.derived_n5_atom
                candidate = SimpleNamespace(
                    candidate_id=read.input_record.original_candidate_id,
                    atom=atom,
                    intervention_atoms=(atom,),
                )
                simulation = SimulationPortObservation.model_validate(handoff["simulation"])
                simulation = simulation.model_copy(
                    update={"world_model_record": context.context.world_model_record}
                )
                value_port = _DefaultSimulationBoundFoundryValuePort(
                    repo_root=Path(__file__).resolve().parents[2],
                    cycle_substrate_context=context.context,
                    artifact_store=service._artifact_store,
                )

                def consume(observation: SimulationPortObservation) -> Any:
                    return value_port(
                        candidate=candidate,
                        simulation=observation,
                        problem=read.source.problem,
                        cycle_index=0,
                    )

                value = consume(simulation)
                assert value.status == "value_conditional", value.model_dump(mode="json")
                value_payload = value.model_dump(mode="json")
                wrong_world = consume(
                    simulation.model_copy(
                        update={
                            "world_model_record": context.context.world_model_record.model_copy(
                                update={"content_hash": "sha256:" + "e" * 64}
                            )
                        }
                    )
                )
                assert wrong_world.status == "value_blocked"
                assert wrong_world.authority_blockers == ("joint_simulation_result_wmr_mismatch",)
                result_ref = ArtifactRef.model_validate(witness["result_ref"])
                foreign = FileSystemCAS(root / ".polisyos").for_tenant(
                    "foreign-cyc02-tenant", cell_id=handoff["cell_id"]
                )
                assert foreign.root == service._artifact_store.root
                with pytest.raises(ArtifactOwnershipError):
                    foreign.get_bytes(result_ref)
                if read_failed_terminal:
                    from polisyos.core.contracts.control import ControlJobResponse

                    try:
                        os.kill(handoff["producer_pid"], 0)
                    except ProcessLookupError:
                        pass
                    else:
                        raise AssertionError("late-fault producer must have exited")
                    job_response = client.get("/api/v1/control/jobs/" + handoff["job_id"])
                    assert job_response.status_code == 200, job_response.text
                    public_job = ControlJobResponse.model_validate(job_response.json())
                    assert public_job.state == "failed"
                    assert public_job.error_message.startswith(handoff["fault_code"] + ":")
                    job = service._control_store.get_job(handoff["job_id"])
                    assert job is not None and job.state == "failed"
                    terminal = _failed_terminal_read(service, root, handoff)
                    with pytest.raises(
                        ValueError, match=r"^control_job_core_run_source_not_completed$"
                    ) as protected_refusal:
                        service.resolve_completed_control_job_core_run_source(
                            job,
                            expected_control_run_id=handoff["control_run_id"],
                            tenant_id=handoff["tenant_id"],
                            cell_id=handoff["cell_id"],
                        )
                    assert projection["cycle_completed"] is False
                    assert projection["failed_stage"] == "value_projection"
                    return {
                        "consumer_pid": os.getpid(),
                        "witness": witness,
                        "projection": projection,
                        "conditional_value": value_payload,
                        "job_state": public_job.state,
                        "terminal_status": terminal.manifest.status,
                        "terminal_manifest_ref": terminal.manifest_ref.model_dump(mode="json"),
                        "terminal_selected_outputs_verified": True,
                        "fault_code": public_job.progress["failure"]["code"],
                        "cycle_completed": projection["cycle_completed"],
                        "protected_completed_source_refusal": str(protected_refusal.value),
                        "no_new_n5": True,
                        "nonmutating_controls": {
                            "wrong_world": wrong_world.model_dump(mode="json"),
                            "foreign_tenant": "refused",
                        },
                    }
                blob_path, _ = service._artifact_store._paths(result_ref.artifact_id)
                assert not blob_path.is_symlink() and blob_path.stat().st_nlink == 1
                original = blob_path.read_bytes()
                try:
                    blob_path.write_bytes(original + b"corrupt")
                    with pytest.raises((ValueError, RuntimeError)):
                        _read_selected(service, handoff)
                    corrupt = consume(simulation)
                    assert corrupt.status == "value_blocked"
                    assert corrupt.authority_blockers == (
                        "joint_simulation_result_integrity_invalid",
                    )
                finally:
                    blob_path.write_bytes(original)
                manifest_path = service._artifact_store._manifest_path_for_ref(
                    result_ref.artifact_id, result_ref.manifest_profile_sha256
                )
                assert not manifest_path.is_symlink() and manifest_path.stat().st_nlink == 1
                hidden = manifest_path.with_suffix(".cyc02-withdrawn")
                assert not hidden.exists()
                try:
                    manifest_path.rename(hidden)
                    with pytest.raises((ValueError, RuntimeError, OSError)):
                        _read_selected(service, handoff)
                    missing = consume(simulation)
                    assert missing.status == "value_blocked"
                    assert missing.authority_blockers == ("joint_simulation_result_unavailable",)
                finally:
                    hidden.rename(manifest_path)
                assert _witness(_read_selected(service, handoff)) == witness
                return {
                    "consumer_pid": os.getpid(),
                    "witness": witness,
                    "projection": projection,
                    "conditional_value": value_payload,
                    "controls": {
                        "foreign_tenant": "refused",
                        "wrong_world": wrong_world.model_dump(mode="json"),
                        "corrupt_blob": corrupt.model_dump(mode="json"),
                        "missing_selected_manifest": missing.model_dump(mode="json"),
                        "restored": "resolved",
                    },
                }


def _failed_terminal_read(service: Any, root: Path, handoff: dict[str, Any]) -> Any:
    """Read the real terminal trace/head, keeping the failed attempt distinct."""
    from polisyos.core.artifacts import ArtifactRef, artifact_ref_identity_key
    from polisyos.runtime.http.services.adapters.core_run import load_terminal_core_run_source

    terminal = load_terminal_core_run_source(
        store=service._artifact_store,
        core_runs_root=root / ".polisyos/runs",
        run_id=handoff["core_run_id"],
    )
    manifest = terminal.manifest
    assert manifest.run_id == handoff["core_run_id"]
    assert manifest.control_job_id == handoff["job_id"]
    assert (manifest.tenant_id, manifest.cell_id) == (handoff["tenant_id"], handoff["cell_id"])
    assert manifest.status == "error"
    job = service._control_store.get_job(handoff["job_id"])
    assert job is not None and job.state == "failed"
    expected = ArtifactRef.model_validate(job.progress["core_manifest_artifact_ref"])
    assert artifact_ref_identity_key(terminal.manifest_ref) == artifact_ref_identity_key(expected)
    linked = {artifact_ref_identity_key(ref) for ref in manifest.outputs}
    for reference in (
        handoff["execution_ref"],
        handoff["witness"]["result_ref"],
        handoff["witness"]["input_ref"],
        handoff["witness"]["n4_ref"],
    ):
        assert artifact_ref_identity_key(ArtifactRef.model_validate(reference)) in linked
    # Context is an upstream selected input, not an additional Core root.
    context_ref = ArtifactRef.model_validate(handoff["witness"]["context_ref"])
    execution_manifest = service._artifact_store.get_manifest(
        ArtifactRef.model_validate(handoff["execution_ref"])
    )
    assert [
        (str(edge.artifact_id), edge.manifest_profile_sha256)
        for edge in execution_manifest.inputs
        if edge.role == "cycle_substrate_context_job"
    ] == [(str(context_ref.artifact_id), context_ref.manifest_profile_sha256)]
    assert manifest.errors[0]["code"] == handoff["fault_code"]
    assert manifest.errors[0]["stage"] == "value_projection"
    assert manifest.errors[0]["cause"] == {
        "exception_type": "RuntimeError",
        "message": "cyc02 controlled downstream value fault",
    }
    return terminal


def _late_fault_handoff(
    root: Path,
    service: Any,
    job: Any,
    scope: Any,
    observed: list[Any],
    source_root: Path,
    catalog_selection: Any,
) -> dict[str, Any]:
    """Reopen the failed leaf's actual owner-persisted partial, never a cycle."""
    assert job.state == "failed"
    assert len(observed) == 1
    partial = job.progress["partial_candidate_simulation"]
    assert partial["completed_stage"] == "n5_simulation"
    assert partial["failed_stage"] == "value_projection"
    assert partial["cycle_completed"] is partial["publication_authority"] is False
    assert "compiled_recursive_generation_cycle_artifact_ref" not in job.progress
    handoff = {
        "producer_pid": os.getpid(),
        "job_id": job.job_id,
        "control_run_id": str(job.run_id),
        "core_run_id": job.progress["core_run_id"],
        "tenant_id": scope.tenant_id,
        "cell_id": scope.cell_id,
        "execution_ref": partial["execution_ref"],
        "source_root": str(source_root),
        "catalog_selection": catalog_selection.model_dump(mode="json"),
        "simulation": observed[0].model_dump(mode="json"),
        "job_state": job.state,
        "fault_stage": partial["failed_stage"],
        "fault_code": job.progress["failure"]["code"],
        "cycle_completed": False,
    }
    assert handoff["fault_code"] == "res03.configured_candidate_late_value_failure"
    read = _read_selected(service, handoff)
    handoff["witness"] = _witness(read)
    assert partial["simulation_result_ref"] == handoff["witness"]["result_ref"]
    terminal = _failed_terminal_read(service, root, handoff)
    handoff["terminal_manifest_ref"] = terminal.manifest_ref.model_dump(mode="json")
    handoff["physical_work_units"] = read.result.diagnostics["physical_work_units"]
    return handoff


def _semantic_consume(root: Path, handoff: dict[str, Any]) -> dict[str, Any]:
    """Exercise new-artifact semantic mutations without repeating or editing N5."""
    import copy

    import duckdb
    import pytest
    from fastapi.testclient import TestClient

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.data_forge.read_api.catalog import build_slice0_fixture_catalog_graph
    from polisyos.ir import candidate_ncm_spec_from_declaration
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.candidate_simulation import CandidateSimulationContextHandoff
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextArtifactOwner
    from polisyos.runtime.quality.generation_cycle import (
        JointSimulationPort,
        RealValueOwnerGateway,
        SimulationPortObservation,
        _DefaultSimulationBoundFoundryValuePort,
        _resolve_owner_scope_region,
        load_joint_simulation_result,
        persist_joint_simulation_result,
        simulation_value_execution_context,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationControllerError,
        JointSimulationHorizonController,
        build_content_bound_simulation_receipt,
    )
    from polisyos.runtime.quality.substrate_registry import (
        CatalogServingSourceSelection,
        catalog_serving_source_scope,
    )
    from tests._helpers.catalog_source_admission import admit_fixture_catalog_source

    _environment(root)

    def no_new_n5(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("semantic mutation controls must not execute N5")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(JointSimulationHorizonController, "run", no_new_n5)
        selection = CatalogServingSourceSelection.model_validate(handoff["catalog_selection"])
        app = _app(
            root,
            candidate_simulation_profiles=(),
            candidate_simulation_model_declarations=(),
            repo_root=Path(handoff["source_root"]),
            catalog_source_selection=selection,
            catalog_run_profile=selection.catalog_run_profile,
        )
        with TestClient(app):
            service = app.state._control_service
            with tenant_scope(None, tenant_id=handoff["tenant_id"], cell_id=handoff["cell_id"]):
                read = _read_selected(service, handoff)
                original_witness = _witness(read)
                assert original_witness == handoff["witness"]
                expected = {
                    "expected_run_id": handoff["control_run_id"],
                    "expected_job_id": handoff["job_id"],
                    "expected_tenant_id": handoff["tenant_id"],
                    "expected_cell_id": handoff["cell_id"],
                }
                context = (
                    CycleSubstrateContextArtifactOwner(store=service._artifact_store)
                    .resolve_historical_job_artifact(
                        read.execution.context_job_ref, problem=read.source.problem, **expected
                    )
                    .context
                )
                atom = read.input_record.materialization.derived_n5_atom
                candidate = SimpleNamespace(
                    candidate_id=read.input_record.original_candidate_id,
                    atom=atom,
                    intervention_atoms=(atom,),
                )
                simulation = SimulationPortObservation.model_validate(
                    handoff["simulation"]
                ).model_copy(update={"world_model_record": context.world_model_record})
                value_port = _DefaultSimulationBoundFoundryValuePort(
                    repo_root=Path(__file__).resolve().parents[2],
                    cycle_substrate_context=context,
                    artifact_store=service._artifact_store,
                )
                declaration = read.source.source_record.model_declaration
                record = read.input_record
                bound_handoff = CandidateSimulationContextHandoff(
                    context=context,
                    context_job_ref=read.execution.context_job_ref,
                    profile=record.profile,
                    profile_config_ref=record.profile_config_ref,
                    job_id=record.job_id,
                    run_id=record.run_id,
                    tenant_id=record.tenant_id,
                    cell_id=record.cell_id,
                    model_declaration=declaration,
                    model_declaration_ref=record.model_declaration_ref,
                    ncm_ref=record.ncm_ref,
                )
                n5_port = JointSimulationPort(
                    repo_root=Path(__file__).resolve().parents[2],
                    cycle_substrate_context=context,
                    artifact_store=service._artifact_store,
                    candidate_simulation_handoff=bound_handoff,
                )
                request = n5_port._build_candidate_simulation_request(
                    candidate=read.source.candidate,
                    problem=read.source.problem,
                    input_record=record,
                )
                controller = JointSimulationHorizonController()
                controller.validate_selected_result(request=request, result=read.result)
                (plan,) = request.engine_plan
                assert plan.ncm_spec == candidate_ncm_spec_from_declaration(declaration)
                model_fields = declaration.model_dump(mode="json", exclude={"content_hash"})
                model_fields["outcome_per_target_unit"] += 0.25
                wrong_declaration = type(declaration).model_validate(
                    {**model_fields, "content_hash": gy_content_hash(model_fields)}
                )
                wrong_model_request = request.model_copy(
                    update={
                        "engine_plan": (
                            plan.model_copy(
                                update={
                                    "ncm_spec": candidate_ncm_spec_from_declaration(
                                        wrong_declaration
                                    )
                                }
                            ),
                        )
                    }
                )
                with pytest.raises(JointSimulationControllerError) as model_refusal:
                    controller.validate_selected_result(
                        request=wrong_model_request, result=read.result
                    )
                assert model_refusal.value.code == "selected_plan_execution_binding_missing"
                assert "trajectory is not content-bound" in str(model_refusal.value)
                wrong_baseline_request = request.model_copy(
                    update={
                        "baseline_state": {
                            **request.baseline_state,
                            record.outcome_variable: request.baseline_state[record.outcome_variable]
                            + 1.0,
                        }
                    }
                )
                with pytest.raises(JointSimulationControllerError) as baseline_refusal:
                    controller.validate_selected_result(
                        request=wrong_baseline_request, result=read.result
                    )
                assert baseline_refusal.value.code == "selected_plan_execution_binding_missing"
                assert "trajectory is not content-bound" in str(baseline_refusal.value)

                def persist_mutation(payload: dict[str, Any]) -> tuple[Any, Any]:
                    receipt = build_content_bound_simulation_receipt(
                        engine_kind=read.result.receipt.engine_kind,
                        payload=payload,
                        diagnostics=payload["diagnostics"],
                    )
                    mutated = type(read.result).model_validate(
                        {**payload, "receipt": receipt.model_dump(mode="json")}
                    )
                    mutated._content_payload = payload
                    selected_ref = persist_joint_simulation_result(
                        mutated, store=service._artifact_store
                    )
                    assert selected_ref != read.execution.n5_result_ref
                    loaded = load_joint_simulation_result(
                        selected_ref,
                        store=service._artifact_store,
                        expected_world_model_record_content_hash=context.world_model_record.content_hash,
                        expected_atom_ids=read.result.atom_ids,
                        expected_selected_outcomes=read.result.selected_outcomes,
                        expected_receipt_payload_hash=receipt.payload_hash,
                    )
                    return selected_ref, loaded

                trajectory_payload = copy.deepcopy(read.result.content_bound_payload())
                # Preserve valid replication means and same-physical-run role
                # companions; only the effect's relation to outcome/baseline is false.
                for trajectory in trajectory_payload["trajectories"]:
                    for point in trajectory["points"]:
                        point["effect"][record.outcome_variable] += 0.25
                        for sample in point["replication_sampling"]["samples"]:
                            sample["effects"][record.outcome_variable] += 0.25
                trajectory_ref, wrong_trajectory = persist_mutation(trajectory_payload)
                with pytest.raises(JointSimulationControllerError) as trajectory_refusal:
                    controller.validate_selected_result(request=request, result=wrong_trajectory)
                assert trajectory_refusal.value.code == "selected_plan_execution_binding_missing"
                assert "selected_effect_basis_mismatch" in str(trajectory_refusal.value)
                with pytest.raises(AssertionError):
                    _witness(
                        SimpleNamespace(
                            input_record=read.input_record,
                            source=read.source,
                            result=wrong_trajectory,
                            execution=read.execution,
                        )
                    )
                unknown_payload = copy.deepcopy(read.result.content_bound_payload())
                packet = unknown_payload["promotion_ready_value_packet"]
                packet["authority_blockers"] = [
                    *packet["authority_blockers"],
                    "cyc02_unknown_persisted_limitation",
                ]
                unknown_ref, unknown = persist_mutation(unknown_payload)
                unknown_value = value_port(
                    candidate=candidate,
                    simulation=simulation.model_copy(
                        update={
                            "simulation_result_ref": unknown_ref,
                            "simulation_ref": unknown.receipt.payload_hash,
                        }
                    ),
                    problem=read.source.problem,
                    cycle_index=0,
                )
                assert unknown_value.status == "value_blocked"
                assert unknown_value.authority_blockers == (
                    "n8_persisted_blocker_not_candidate_allowlisted",
                )
                assert unknown_value.value_ref is unknown_value.value_receipt is None

                # A distinct, small owner-built synthetic Catalog proves the
                # empirical refusal; it supplies no treatment or real authority.
                empirical_root = root / f"empirical-owner-source-{os.getpid()}"
                catalog = build_slice0_fixture_catalog_graph(empirical_root / "catalog")
                catalog.close()
                database = empirical_root / "catalog/catalog.duckdb"
                region = _resolve_owner_scope_region(
                    read.source.problem.jurisdiction_time.region,
                    owner_access_ref="test://cyc02-synthetic-owner-rows",
                )
                assert region
                with duckdb.connect(str(database)) as connection:
                    connection.executemany(
                        """INSERT INTO ds_observations (
                            observation_id, dataset_id, raw_variable, canonical_var,
                            country_code, year, survey_year, wave, value, condition_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        [
                            (
                                f"cyc02-synthetic-employment-{index}",
                                "cyc02.synthetic.owner.rows",
                                record.outcome_variable,
                                record.outcome_variable,
                                region,
                                1800 + index,
                                None,
                                None,
                                float(index % 2),
                                json.dumps({"unit": declaration.outcome_unit_id}),
                            )
                            for index in range(8)
                        ],
                    )
                catalog_source = admit_fixture_catalog_source(
                    repo_root=empirical_root, database_path=database
                )
                gateway = RealValueOwnerGateway(
                    repo_root=empirical_root,
                    catalog_serving_source=catalog_source,
                )
                with catalog_serving_source_scope(catalog_source):
                    profile = gateway.load_value_data_profile(
                        candidate=candidate,
                        problem=read.source.problem,
                        world_record=context.world_model_record,
                    )
                    assert profile.owner_row_count == 8
                    assert profile.measurement_unit == declaration.outcome_unit_id
                    assert profile.treatment_assignment_status == "owner_assignment_unresolved"
                    # A limited N5 cannot establish the ordinary evaluation
                    # intake. Do not fabricate a context or remove its limits
                    # merely to reach a later owner-treatment gate.
                    with pytest.raises(
                        ValueError, match=r"^eval_safety_simulation_input_unresolved$"
                    ) as empirical_refusal:
                        simulation_value_execution_context(
                            candidate=candidate,
                            simulation=simulation,
                            problem=read.source.problem,
                            artifact_store=service._artifact_store,
                        )
                empirical = {
                    "context_status": "refused",
                    "code": str(empirical_refusal.value),
                    "value_port_status": "not_run",
                    "value_receipt": None,
                }
                restored = value_port(
                    candidate=candidate,
                    simulation=simulation,
                    problem=read.source.problem,
                    cycle_index=0,
                )
                assert restored.status == "value_conditional"
                assert _witness(_read_selected(service, handoff)) == original_witness
                return {
                    "consumer_pid": os.getpid(),
                    "no_new_n5": True,
                    "original_selected_result_unchanged": True,
                    "original_request_selected_verifier": "accepted",
                    "wrong_model": model_refusal.value.code,
                    "wrong_baseline": baseline_refusal.value.code,
                    "wrong_trajectory": trajectory_refusal.value.code,
                    "mutation_reasons": {
                        "model": str(model_refusal.value),
                        "baseline": str(baseline_refusal.value),
                        "trajectory": str(trajectory_refusal.value),
                    },
                    "wrong_trajectory_ref": trajectory_ref.model_dump(mode="json"),
                    "independent_numeric_oracle_rejected_drift": True,
                    "unknown_blocker_ref": unknown_ref.model_dump(mode="json"),
                    "unknown_blocker": unknown_value.model_dump(mode="json"),
                    "empirical_no_treatment": empirical,
                    "empirical_input_scope": "eight synthetic owner rows; no owner treatment",
                    "empirical_owner_assignment_status": profile.treatment_assignment_status,
                    "empirical_treatment_gate": "not_reached: actual limited N5 cannot establish ordinary evaluation input",
                    "original_conditional_restored": restored.model_dump(mode="json"),
                }


def _main() -> None:
    import faulthandler

    root = Path(sys.argv[2]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    diagnose = os.environ.get("POLISYOS_TEST_CYC02_STACK_DIAG") == "1" and sys.argv[1] == "produce"
    if diagnose:
        # One opt-in stack locates an unknown expensive profile before its
        # resource ceiling; it neither changes the numerical route nor retries.
        faulthandler.dump_traceback_later(15, repeat=False)
    try:
        if sys.argv[1] == "produce":
            result = _produce(root)
        elif sys.argv[1] == "produce_late_fault":
            result = _produce(root, late_fault=True)
        elif sys.argv[1] == "consume":
            result = _consume(root, json.load(sys.stdin))
        elif sys.argv[1] == "consume_late_fault":
            result = _consume(root, json.load(sys.stdin), read_failed_terminal=True)
        elif sys.argv[1] == "semantic_controls":
            result = _semantic_consume(root, json.load(sys.stdin))
        else:
            raise SystemExit("unknown CYC02 child mode")
    finally:
        if diagnose:
            faulthandler.cancel_dump_traceback_later()
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))


if __name__ == "__main__":
    _main()
