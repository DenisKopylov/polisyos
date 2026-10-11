from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tests._helpers.controlled_candidate_profile import (
    _configured_procurement_profile,
    _controlled_procurement_recording,
    _current_compiler_problem,
    _materialize_controlled_world_model_record,
)
from tools.quality.validation import (
    check_layer3_gy_design_generation_contract as n4_contract,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
_RECORDING_ID = "gy_n4_cgf_decisive_capture_1_20260704_092222_049411"


@pytest.fixture
def controlled_candidate_gateway(monkeypatch: pytest.MonkeyPatch):
    """Route the served compiler and N4 calls through the local recording gateway."""
    from tests._helpers.controlled_candidate_profile import ControlledCandidateGateway

    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-synthetic-local-gateway-key")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_MAX_RETRIES", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_TTL_S", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "0")
    monkeypatch.setenv("POLISYOS_LLM_PROMPT_SANITIZER", "false")
    with ControlledCandidateGateway() as gateway:
        monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", gateway.base_url)
        yield gateway


def _hashed_model(model_type: type[Any], fields: dict[str, Any], *, hash_fn: Any):
    draft = model_type.model_construct(
        **fields,
        content_hash="sha256:" + "0" * 64,
    )
    body = draft.model_dump(mode="json", exclude={"content_hash"})
    return model_type.model_validate({**body, "content_hash": hash_fn(body)})


def _persist_compiled_run_with_incomplete_child_set(
    *,
    store: Any,
    compiled_ref: Any,
    tenant_id: str,
    cell_id: str,
):
    """Persist a self-consistent compiled ref to a source-incomplete child-set artifact."""
    from polisyos.core import canon
    from polisyos.core.artifacts import ArtifactWriteOptions
    from polisyos.core.artifacts.manifest import ArtifactTenantContextInfo, SchemaInfo
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.pdc import gy_artifact_self_identity_projection, gy_content_hash
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveLeafContextOwner,
        RecursiveN4ChildProfileSetV1,
    )

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        compiled = CompiledRecursiveGenerationCycleRun.model_validate(
            canon.from_canonical_bytes(store.get_bytes(compiled_ref))
        )
        child_set_ref = compiled.n4_child_profile_set_ref
        assert child_set_ref is not None
        original_set = RecursiveN4ChildProfileSetV1.model_validate(
            canon.from_canonical_bytes(store.get_bytes(child_set_ref))
        )
    assert len(original_set.children) == 2
    incomplete_set = _hashed_model(
        RecursiveN4ChildProfileSetV1,
        {
            **original_set.model_dump(mode="python", exclude={"content_hash"}),
            "children": original_set.children[:-1],
        },
        hash_fn=gy_content_hash,
    )
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        incomplete_set_ref = store.put_json(
            incomplete_set.model_dump(mode="json"),
            RecursiveLeafContextOwner._n4_child_profile_set_write_options(incomplete_set),
            canon_spec=canon.CanonSpec(forbid_floats=False),
        )

    compiled_fields = compiled.model_dump(mode="python", exclude={"content_hash"})
    compiled_fields["n4_child_profile_set_ref"] = incomplete_set_ref
    draft = compiled.model_copy(
        update={
            "n4_child_profile_set_ref": incomplete_set_ref,
            "content_hash": "sha256:" + "0" * 64,
        },
    )
    identity_payload = gy_artifact_self_identity_projection(draft)
    recursive_payload = dict(identity_payload["recursive_run"])
    recursive_payload.pop("leaf_nodes", None)
    identity_payload["recursive_run"] = recursive_payload
    compiled_fields["content_hash"] = gy_content_hash(identity_payload)
    incomplete_compiled = CompiledRecursiveGenerationCycleRun.model_validate(
        compiled_fields
    )
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        incomplete_compiled_ref = store.put_json(
            incomplete_compiled.model_dump(mode="json"),
            ArtifactWriteOptions(
                kind="runtime.compiled_recursive_generation_cycle",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
                    version="1.0",
                ),
                tenant_context=ArtifactTenantContextInfo(
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                ),
            ),
            canon_spec=canon.CanonSpec(forbid_floats=False),
        )
    return incomplete_compiled_ref, incomplete_set_ref


def _two_child_recording(recording: dict[str, Any], *, outcome_variable: str) -> dict[str, Any]:
    """Keep two declared intervention families in a separately identified replay fixture."""
    from polisyos.pdc import gy_content_hash

    controlled = _controlled_procurement_recording(
        recording,
        outcome_variable=outcome_variable,
    )
    original_id = str(controlled["recording_id"])
    original_hash = str(controlled["recording_content_hash"])
    responses = controlled["responses"]
    assert isinstance(responses, list)
    for response_index in (4, 8):
        response = responses[response_index]
        assert isinstance(response, dict)
        raw = response.get("raw_response")
        assert isinstance(raw, str)
        payload = json.loads(raw)
        interventions = payload["policy_spec"]["interventions"]
        retained = [row for row in interventions if row.get("kind") != "credit_guarantee"]
        assert {row.get("kind") for row in retained} == {
            "tax_relief_rate",
            "procurement_shock_intensity",
        }
        removed_ids = {
            row.get("intervention_id") for row in interventions if row not in retained
        }
        payload["policy_spec"]["interventions"] = retained
        payload["policy_spec"]["parameters"] = [
            row
            for row in payload["policy_spec"].get("parameters", [])
            if row.get("intervention_id") not in removed_ids
        ]
        rewritten = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        response["raw_response"] = rewritten
        response["raw_response_hash"] = gy_content_hash(rewritten)

    fixture_id = "synthetic_two_n4_children_" + gy_content_hash(
        {
            "base_recording_id": original_id,
            "base_content_hash": original_hash,
            "response_hashes": [
                row.get("raw_response_hash") for row in responses if isinstance(row, dict)
            ],
        }
    ).removeprefix("sha256:")[:20]
    controlled["recording_id"] = fixture_id
    controlled["fixture_id"] = fixture_id
    controlled["recording_source"] = "synthetic_two_child_overlay_of_recorded_capture"
    controlled["derived_from_recording_id"] = original_id
    controlled["derived_from_content_hash"] = original_hash
    controlled["recording_content_hash"] = gy_content_hash(
        {key: value for key, value in controlled.items() if key != "recording_content_hash"}
    )
    n4_contract._validate_recording_fixture(controlled)
    return controlled


def _generic_profile_for_selection(
    *,
    tmp_path: Path,
    base_profile: Any,
    base_declaration: Any,
    profile_id: str,
    profile_selection_ref: str,
    profile_selection_kind: str,
    target_world_slot: str,
    operator_kind: str,
    store: Any,
    substrate_registry_ref: Any,
    tenant_id: str,
    cell_id: str,
):
    """Build a typed candidate-only profile and persist its exact WMRv2/NCM basis."""
    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.ir.analytics.ncm import (
        candidate_ncm_spec_from_declaration,
        persist_ncm_spec,
    )
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateScenarioSetToRule,
        CandidateSimulationScenarioProfile,
        candidate_simulation_profile_ref,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleN5RequestProfileV1,
        GenericCycleSimulationProfileV1,
    )
    from polisyos.runtime.quality.world_model_record import (
        derive_candidate_scenario_world_model_record,
        load_world_model_record,
        persist_world_model_record,
    )

    outcome_variable = base_declaration.outcome_variable
    baseline_state = {
        key: float(value) for key, value in base_profile.n5.baseline_state.items()
    }
    baseline_state.setdefault(target_world_slot, 0.0)
    baseline_state.setdefault(outcome_variable, 0.0)
    rule = CandidateScenarioSetToRule(
        operator_kind=operator_kind,
        parameter_id="controlled_value",
        target_world_slot=target_world_slot,
        unit_id=base_profile.rule.unit_id,
        minimum=base_profile.rule.minimum,
        maximum=base_profile.rule.maximum,
    )
    candidate_n5 = base_profile.n5.model_copy(update={"baseline_state": baseline_state})
    candidate_fields = base_profile.model_dump(mode="python", exclude={"content_hash"})
    candidate_fields.update(
        {
            "profile_id": "v6-synthetic-model-" + profile_id,
            "profile_selection_ref": profile_selection_ref,
            "context_inputs": base_profile.context_inputs,
            "rule": rule,
            "n5": candidate_n5,
        }
    )
    synthetic_profile = _hashed_model(
        CandidateSimulationScenarioProfile,
        candidate_fields,
        hash_fn=gy_content_hash,
    )
    declaration_fields = base_declaration.model_dump(mode="python", exclude={"content_hash"})
    declaration_fields.update(
        {
            "profile_config_ref": candidate_simulation_profile_ref(synthetic_profile),
            "profile_content_hash": synthetic_profile.content_hash,
            "profile_selection_ref": profile_selection_ref,
            "target_world_slot": target_world_slot,
            "target_unit_id": synthetic_profile.rule.unit_id,
            "target_baseline": baseline_state[target_world_slot],
            "outcome_baseline": baseline_state[outcome_variable],
        }
    )
    declaration = _hashed_model(
        type(base_declaration),
        declaration_fields,
        hash_fn=gy_content_hash,
    )
    ncm = candidate_ncm_spec_from_declaration(declaration)

    base_context_inputs = base_profile.context_inputs
    base_world = base_context_inputs.world_model_record
    materialized_base_world = _materialize_controlled_world_model_record(
        source_world_model_record=base_world,
        artifact_store=store,
        tmp_path=tmp_path,
        substrate_registry=base_context_inputs.substrate_registry,
        selected_registry_entry_hashes=base_context_inputs.selected_registry_entry_hashes,
        substrate_registry_ref=substrate_registry_ref,
        policy_slot_ids=tuple(
            dict.fromkeys(
                [item.slot_id for item in base_world.policy_slot_map]
                + [target_world_slot, outcome_variable]
            )
        ),
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        ncm_ref = persist_ncm_spec(ensure_ir_artifact_store(store), ncm)
        ncm_ref = ArtifactRef.model_validate(ncm_ref.model_dump(mode="python"))
        world = derive_candidate_scenario_world_model_record(
            materialized_base_world,
            ncm_artifact_ref=ncm_ref,
            declaration_content_hash=declaration.content_hash,
            substrate_registry_view_ref=substrate_registry_ref,
        )
        world_ref = persist_world_model_record(store, world)
        world_ref = ArtifactRef.model_validate(world_ref.model_dump(mode="python"))
        if load_world_model_record(store, world_ref) != world:
            raise ValueError("controlled_generic_profile_wmr_readback_mismatch")

    context_inputs = base_context_inputs.model_copy(update={"world_model_record": world})
    generic_n5 = GenericCycleN5RequestProfileV1(
        budget_ref=base_profile.n5.budget_ref,
        horizon=base_profile.n5.horizon,
        baseline_state=baseline_state,
        comparator_refs=base_profile.n5.comparator_refs,
        seed=base_profile.n5.seed,
        replications=base_profile.n5.replications,
    )
    profile_fields = {
        "profile_id": profile_id,
        "profile_selection_ref": profile_selection_ref,
        "profile_selection_kind": profile_selection_kind,
        "world_model_record_ref": world_ref,
        "substrate_registry_ref": substrate_registry_ref,
        "selected_ncm_ref": ncm_ref,
        "context_inputs": context_inputs,
        "n5": generic_n5,
        "limitations": (
            "controlled_inputs_only",
            "currentness_not_established",
            "n5_simulation_not_world_evidence",
            "n9_not_admitted",
            "s8_blocked",
            "source_truth_not_established",
        ),
    }
    return _hashed_model(
        GenericCycleSimulationProfileV1,
        profile_fields,
        hash_fn=gy_content_hash,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_served_real_n4_children_keep_first_n5_after_later_sibling_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> None:
    """A real N4 source, full child family, first N5 and fresh GET survive sibling failure."""
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.http.services.control import generation_cycle as generation_cycle_service
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextOwnerError,
        build_cycle_substrate_context,
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
        generic_n4_child_profile_selection_ref,
    )
    from polisyos.runtime.quality.design_generation import derive_n4_candidate_child_problems
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        GenerationCycleError,
        N4GenerationPort,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
    )
    from polisyos.runtime.quality.substrate_registry import persist_substrate_registry
    from polisyos.scientist.orchestration.llm import factory as llm_factory
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests.unit.runtime.http.test_control_job_execution_intent import (
        _valid_intake_for_mode,
    )
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
    )

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", (tmp_path / "control.sqlite3").as_posix())
    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "runtime-cache").as_posix())
    monkeypatch.setenv("JAX_PLATFORMS", "cpu")
    monkeypatch.setenv("OMP_NUM_THREADS", "1")

    recording = next(
        item
        for item in n4_contract._load_recordings(REPO_ROOT)
        if item.get("design_problem_id") == _RECORDING_ID
    )
    original_problem = _current_compiler_problem(recording)
    controlled_recording = _two_child_recording(
        recording,
        outcome_variable=original_problem.outcome_of_interest.target_variable,
    )
    recorded_problem = _current_compiler_problem(controlled_recording)
    controlled_candidate_gateway.set_fixture(controlled_recording, problem=recorded_problem)
    model_id = str(recording["model_id"])
    tenant_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cell_id = "cell-v6-generic-n4"
    cas_root = tmp_path / ".polisyos"
    runtime_api_context = build_runtime_api_context(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
    )
    base_profile, base_declaration = _configured_procurement_profile(
        recorded_problem=recorded_problem,
        artifact_store=runtime_api_context.store,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    base_inputs = base_profile.context_inputs
    preflight_context = build_cycle_substrate_context(
        design_problem_ref=cycle_job_design_problem_ref(recorded_problem),
        domain=recorded_problem.domain,
        substrate_registry=base_inputs.substrate_registry,
        selected_registry_entry_hashes=base_inputs.selected_registry_entry_hashes,
        world_model_record=base_inputs.world_model_record,
        intervention_substrate=base_inputs.intervention_substrate,
        candidate_levers=base_inputs.candidate_levers,
        transport_context=base_inputs.transport_context,
        source_pack_content_hash=base_inputs.source_pack_content_hash,
        substrate_input_content_hash=base_inputs.substrate_input_content_hash,
    )
    preflight = N4GenerationPort(
        model_id=model_id,
        llm_client=n4_contract.RecordedGenerationReplayClient(controlled_recording),
        repo_root=REPO_ROOT,
        cycle_substrate_context=preflight_context,
    )
    organ_run = await preflight(recorded_problem, cycle_index=0)
    generation_result = getattr(organ_run, "result", None)
    assert generation_result is not None
    children = derive_n4_candidate_child_problems(
        recorded_problem,
        generation_result,
        model_id=model_id,
    )
    assert len(children) == 2
    assert len({child.semantic_ref for child in children}) == 2
    parent_problem_ref = cycle_job_design_problem_ref(recorded_problem)
    child_keys = tuple(
        generic_n4_child_profile_selection_ref(
            child.problem,
            parent_problem_ref=parent_problem_ref,
            source_result_ref=child.source_result_ref,
            source_atom_refs=child.source_atom_refs,
            semantic_ref=child.semantic_ref,
        )
        for child in children
    )
    assert len(set(child_keys)) == len(children)
    with pytest.raises(ValueError, match="generic_cycle_child_profile_selection_lineage_mismatch"):
        generic_n4_child_profile_selection_ref(
            children[0].problem,
            parent_problem_ref=parent_problem_ref,
            source_result_ref=children[0].source_result_ref,
            source_atom_refs=("sha256:" + "f" * 64,),
            semantic_ref=children[0].semantic_ref,
        )

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        substrate_registry_ref = persist_substrate_registry(
            runtime_api_context.store,
            base_inputs.substrate_registry,
        )
    generic_child_profiles = tuple(
        _generic_profile_for_selection(
            tmp_path=tmp_path,
            base_profile=base_profile,
            base_declaration=base_declaration,
            profile_id=f"v6-n4-child-{index}",
            profile_selection_ref=child_key,
            profile_selection_kind="n4_candidate_child",
            target_world_slot=child.problem.candidate_lever_space.candidate_levers[0].target_slot,
            operator_kind=child.problem.candidate_lever_space.candidate_levers[0].operator_kind,
            store=runtime_api_context.store,
            substrate_registry_ref=substrate_registry_ref,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        for index, (child, child_key) in enumerate(zip(children, child_keys, strict=True))
    )
    root_profile_fields = generic_child_profiles[0].model_dump(
        mode="python",
        exclude={"content_hash"},
    )
    root_profile_fields.update(
        {
            "profile_id": "v6-generic-root",
            "profile_selection_ref": cycle_job_profile_selection_ref(recorded_problem),
            "profile_selection_kind": "problem",
        }
    )
    root_profile = _hashed_model(
        type(generic_child_profiles[0]),
        root_profile_fields,
        hash_fn=gy_content_hash,
    )
    generic_profiles = (root_profile, *generic_child_profiles)

    original_compiler = generation_cycle_service.build_design_problem_from_nl_request
    compiled_problems: list[Any] = []

    async def run_real_compiler(**kwargs: Any):
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        compiled = await original_compiler(**kwargs)
        compiled_problems.append(compiled)
        return compiled

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        run_real_compiler,
    )
    gateway_factory = llm_factory.create_traced_gateway_client
    gateway_clients: list[Any] = []

    def observe_gateway(**kwargs: Any):
        client = gateway_factory(**kwargs)
        gateway_clients.append(client)
        return client

    monkeypatch.setattr(llm_factory, "create_traced_gateway_client", observe_gateway)
    controller_run = GenerationCycleController.run
    child_attempts: list[str] = []
    successful_child_runs: list[Any] = []
    failure_code = "v6_controlled_second_n4_child_failure"

    async def fail_after_first_child(self, *args: Any, **kwargs: Any):
        handoff = getattr(self, "_generic_cycle_simulation_handoff", None)
        if (
            handoff is None
            or handoff.profile.profile_selection_kind != "n4_candidate_child"
        ):
            return await controller_run(self, *args, **kwargs)
        child_attempts.append(handoff.profile.profile_id)
        if len(child_attempts) == 2:
            raise GenerationCycleError(failure_code, "controlled later N4 sibling failure")
        run = await controller_run(self, *args, **kwargs)
        successful_child_runs.append(run)
        return run

    monkeypatch.setattr(GenerationCycleController, "run", fail_after_first_child)
    profile_handoff_receipts: list[tuple[str, ArtifactRef, ArtifactRef]] = []
    original_persist_handoff = GenericCycleSimulationAdmissionOwner.persist_handoff

    def persist_handoff_and_replay_profile_ref(owner: Any, **kwargs: Any) -> Any:
        offer = kwargs["offer"]
        assert type(offer.profile_ref) is ArtifactRef
        assert (
            owner.resolve_profile(
                offer.profile_ref,
                expected_profile=offer.profile,
                job_id=kwargs["job_id"],
                run_id=kwargs["run_id"],
                tenant_id=kwargs["tenant_id"],
                cell_id=kwargs["cell_id"],
            )
            == offer.profile
        )
        handoff = original_persist_handoff(owner, **kwargs)
        fresh_reader = GenericCycleSimulationAdmissionOwner(
            profiles=generic_profiles,
            store=owner.store,
        )
        assert fresh_reader is not owner
        assert type(handoff.profile_ref) is ArtifactRef
        assert handoff.profile_ref is offer.profile_ref
        assert (
            fresh_reader.resolve_profile(
                handoff.profile_ref,
                expected_profile=handoff.profile,
                job_id=handoff.job_id,
                run_id=handoff.run_id,
                tenant_id=handoff.tenant_id,
                cell_id=handoff.cell_id,
            )
            == offer.profile
        )
        profile_handoff_receipts.append(
            (offer.profile.profile_id, offer.profile_ref, handoff.profile_ref)
        )
        if offer.profile.profile_selection_kind == "problem":
            wrong_profile = generic_child_profiles[0]
            with pytest.raises(CycleSubstrateContextOwnerError) as refusal:
                fresh_reader.resolve_profile(
                    handoff.profile_ref,
                    expected_profile=wrong_profile,
                    job_id=handoff.job_id,
                    run_id=handoff.run_id,
                    tenant_id=handoff.tenant_id,
                    cell_id=handoff.cell_id,
                )
            assert refusal.value.code in {
                "generic_cycle_simulation_profile_manifest_binding_mismatch",
                "generic_cycle_simulation_profile_content_binding_mismatch",
            }
            family_ref = handoff.n4_child_profile_family_ref
            assert family_ref is not None
            family = fresh_reader.resolve_child_profile_family(
                family_ref,
                parent_handoff=handoff,
                parent_problem=kwargs["problem"],
                verified_nl_job_scope=kwargs["verified_nl_job_scope"],
                context_owner=kwargs["context_owner"],
            )
            assert {member.profile_id for member in family.children} == {
                profile.profile_id for profile in generic_child_profiles
            }
        return handoff

    monkeypatch.setattr(
        GenericCycleSimulationAdmissionOwner,
        "persist_handoff",
        persist_handoff_and_replay_profile_ref,
    )
    app = create_runtime_api_app(
        cas_root=cas_root,
        container_overrides=RuntimeContainerOverrides(runtime_api_context=runtime_api_context),
        allow_fixture_identity=True,
        generic_cycle_simulation_profiles=generic_profiles,
        generic_cycle_simulation_root_profile_id=root_profile.profile_id,
    )
    with TestClient(app) as client:
        accepted_response = client.post(
            "/api/v1/control/runs/nl",
            json={
                "request": recorded_problem.nl_provenance.raw_request,
                "llm_model": model_id,
                "context": {
                    "evaluation_safety_attempt": _valid_intake_for_mode(
                        "simulate_only"
                    ).model_dump(mode="json")
                },
            },
        )
        assert accepted_response.status_code == 200, accepted_response.text
        accepted = accepted_response.json()
        assert accepted["status"] == "accepted"
        service = app.state._control_service
        assert dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=accepted["job_id"],
        ) == accepted["job_id"]
        job = service._control_store.get_job(accepted["job_id"])
        assert job is not None and job.state == "completed"
        assert {profile_id for profile_id, _, _ in profile_handoff_receipts} == {
            profile.profile_id for profile in generic_profiles
        }
        assert all(
            offer_ref is handoff_ref for _, offer_ref, handoff_ref in profile_handoff_receipts
        )
        assert len(profile_handoff_receipts) == len(generic_profiles)
        assert len(compiled_problems) == 1
        assert cycle_job_profile_selection_ref(compiled_problems[0]) == (
            root_profile.profile_selection_ref
        )
        assert len(child_attempts) == len(successful_child_runs) + 1 == 2
        assert successful_child_runs
        assert gateway_clients

        details_response = client.get(f"/api/v1/runs/{job.progress['core_run_id']}")
        assert details_response.status_code == 200, details_response.text
        details = details_response.json()["run"]
        projection = details["generic_cycle_simulation"]
        assert projection["artifact_status"] == "resolved"
        assert projection["authority_purpose"] == "cycle_input_candidate_only"
        assert projection["publication_authority"] is False
        assert projection["currentness_status"] == "not_established"
        assert projection["child_profile_status"] == "resolved"
        assert projection["child_profile_limitation_code"] is None
        assert len(projection["child_profile_bindings"]) == 2
        assert {
            row["profile_selection_ref"] for row in projection["child_profile_bindings"]
        } == set(child_keys)
        assert all(
            row["currentness_status"] == "not_established"
            for row in projection["child_profile_bindings"]
        )
        successful_observations = [
            row
            for row in projection["n5_observations"]
            if row["status"] == "joint_simulated"
        ]
        assert successful_observations
        successful = successful_observations[0]
        assert successful["simulation_result_ref"]["kind"] == (
            "polisyos.runtime.joint_simulation_result"
        )
        assert successful["n5_request_binding_status"] == "resolved"
        assert successful["n5_request_content_hash"].startswith("sha256:")
        assert successful["n8_status"] == "value_conditional"
        assert successful["n8_lineage_status"] == "resolved"
        assert successful["n8_value_ref"] == successful["simulation_result_ref"]["artifact_id"]
        assert successful["child_profile_set_ref"] == projection["child_profile_set_ref"]
        checkpoint = projection["recursive_cycle_checkpoint"]
        assert checkpoint["status"] == "partial"
        assert checkpoint["publication_authority"] is False
        assert checkpoint["budget_stop_node_ref"] is None
        assert checkpoint["failed_branches"]
        assert checkpoint["failed_branches"][0]["error_code"] == failure_code
        assert successful["node_ref"] in checkpoint["completed_design_refs"]

        corrupt_ref = successful["simulation_result_ref"]
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            blob_path, _manifest_path = service._artifact_store._paths(
                ArtifactID.model_validate(corrupt_ref["artifact_id"])
            )
            blob_path.write_bytes(b"controlled-corrupt-result")

        corrupt_response = client.get(f"/api/v1/runs/{job.progress['core_run_id']}")
        assert corrupt_response.status_code == 200, corrupt_response.text
        corrupt_projection = corrupt_response.json()["run"]["generic_cycle_simulation"]
        assert corrupt_projection["child_profile_status"] == "resolved"
        assert corrupt_projection["recursive_cycle_checkpoint"] == checkpoint
        assert corrupt_projection["n5_limitation_code"] == (
            "generic_n5_persisted_lineage_not_established"
        )
        assert all(
            row["simulation_result_ref"] != corrupt_ref
            for row in corrupt_projection["n5_observations"]
        )

        indexed_run = runtime_api_context.run_index.get_run(job.progress["core_run_id"])
        assert indexed_run is not None
        compiled_ref = next(
            ref
            for ref in indexed_run.details.root_artifacts
            if ref.kind == "runtime.compiled_recursive_generation_cycle"
        )
        incomplete_compiled_ref, incomplete_set_ref = (
            _persist_compiled_run_with_incomplete_child_set(
                store=runtime_api_context.store,
                compiled_ref=compiled_ref,
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
        )
        original_get_run = runtime_api_context.run_index.get_run

        def run_with_incomplete_child_set(run_id: str):
            indexed = original_get_run(run_id)
            if run_id != job.progress["core_run_id"] or indexed is None:
                return indexed
            altered_roots = tuple(
                incomplete_compiled_ref if ref == compiled_ref else ref
                for ref in indexed.details.root_artifacts
            )
            return replace(
                indexed,
                details=indexed.details.model_copy(
                    update={"root_artifacts": altered_roots}
                ),
            )

        monkeypatch.setattr(
            runtime_api_context.run_index,
            "get_run",
            run_with_incomplete_child_set,
        )
        altered_denominator_response = client.get(
            f"/api/v1/runs/{job.progress['core_run_id']}"
        )
        assert altered_denominator_response.status_code == 200, (
            altered_denominator_response.text
        )
        altered_denominator = altered_denominator_response.json()["run"][
            "generic_cycle_simulation"
        ]
        assert altered_denominator["child_profile_status"] == "not_established"
        assert altered_denominator["child_profile_limitation_code"] == (
            "generic_n4_child_profile_set_reference_not_established"
        )
        assert altered_denominator["child_profile_set_ref"]["artifact_id"] == str(
            incomplete_set_ref.artifact_id
        )
        assert altered_denominator["n5_observations"] == []
        assert altered_denominator["recursive_cycle_checkpoint"] == checkpoint
