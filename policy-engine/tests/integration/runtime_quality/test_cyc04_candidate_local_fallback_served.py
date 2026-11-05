"""Served candidate-local N5 fallback from a real profile-domain refusal."""

from __future__ import annotations

import uuid
from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest


@pytest.fixture
def controlled_candidate_gateway(monkeypatch: pytest.MonkeyPatch):
    """Serve the real compiler and recorded N4 stages from a local fixture gateway."""
    from tests._helpers.controlled_candidate_profile import ControlledCandidateGateway

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-synthetic-local-gateway-key")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_MAX_RETRIES", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_TTL_S", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "0")
    monkeypatch.setenv("POLISYOS_LLM_PROMPT_SANITIZER", "false")
    with ControlledCandidateGateway() as gateway:
        monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", gateway.base_url)
        yield gateway


@pytest.mark.integration
@pytest.mark.asyncio
async def test_served_candidate_local_n5_domain_refusal_retries_grounded_sibling(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> None:
    """Persist a real first-candidate L6 refusal, then execute its grounded sibling."""
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts import (
        ArtifactRef,
        ArtifactWriteOptions,
        ProducerInfo,
        ensure_ir_artifact_store,
    )
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.ir.analytics.ncm import NCMSpecRef, load_ncm_spec_default_view
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.services.control import (
        generation_cycle as generation_cycle_service,
    )
    from polisyos.runtime.http.services.control import (
        run_lifecycle,
    )
    from polisyos.runtime.quality.candidate_simulation import CandidateScenarioDecimalSetToRuleV2
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextOwnerError
    from polisyos.runtime.quality.design_generation import DesignGenerationOrganRun
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        JointSimulationPort,
        N4GenerationPort,
        _candidate_id,
        _ranking_by_candidate,
        load_joint_simulation_result,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleN5RequestProfileV3,
        GenericCycleSimulationAdmissionOwner,
        GenericCycleSimulationN5InputV1,
    )
    from polisyos.runtime.quality.intervention_substrate import InterventionSubstrateError
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
    )
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveCycleNode,
        RecursiveGenerationCycleError,
        RecursiveLeafContextOwner,
    )
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetInvocationQuotaPolicy,
    )
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests._helpers.generic_n4_served_replay import (
        _hashed_model,
        prepare_generic_n4_served_replay,
    )
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
    )

    tenant_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cell_id = "cyc04-served-candidate-local-fallback"
    prepared = await prepare_generic_n4_served_replay(
        tmp_path=tmp_path,
        controlled_candidate_gateway=controlled_candidate_gateway,
        monkeypatch=monkeypatch,
        tenant_id=tenant_id,
        cell_id=cell_id,
        child_count=2,
        recording_mode="original_second_capture",
        materialize_source_parameters=True,
        synthetic_settled_provider=True,
        condition_synthetic_provider_on_child_sources=False,
    )
    assert len(prepared.children) == 2
    assert len(prepared.organ_run.result.candidates) == 2
    assert len(prepared.root_profile.n5.component_rules) == 2
    assert type(prepared.root_profile.n5) is GenericCycleN5RequestProfileV3
    assert all(child.source_atom_refs for child in prepared.children)
    assert len({child.semantic_ref for child in prepared.children}) == 2

    prepared_rankings = _ranking_by_candidate(prepared.organ_run.result)
    prepared_top_candidate = max(
        prepared.organ_run.result.candidates,
        key=lambda candidate: prepared_rankings.get(_candidate_id(candidate), (0.0, 0.0))[0],
    )

    def semantic_key(candidate: object) -> tuple[str, tuple[str, ...]]:
        atom = candidate.atom
        operator_kind = atom.operator_kind.trinity_kind
        if hasattr(operator_kind, "value"):
            operator_kind = operator_kind.value
        return str(operator_kind), tuple(atom.target_world_slots)

    prepared_top_semantic = semantic_key(prepared_top_candidate)
    prepared_grounded_candidate = max(
        enumerate(prepared.organ_run.result.candidates),
        key=lambda row: (
            prepared_rankings.get(_candidate_id(row[1]), (0.0, 0.0))[1],
            prepared_rankings.get(_candidate_id(row[1]), (0.0, 0.0))[0],
            -row[0],
        ),
    )[1]
    prepared_grounded_semantic = semantic_key(prepared_grounded_candidate)
    matching_rules = tuple(
        rule
        for rule in prepared.root_profile.n5.component_rules
        if (str(rule.operator_kind), (rule.target_world_slot,)) == prepared_grounded_semantic
    )
    assert len(matching_rules) == 1
    selected_rule = matching_rules[0]
    assert type(selected_rule) is CandidateScenarioDecimalSetToRuleV2
    literal = Decimal(
        str(
            prepared_grounded_candidate.atom.direct_effect_bundle.params[selected_rule.parameter_id]
        )
    )
    original_minimum = selected_rule.minimum
    original_maximum = selected_rule.maximum
    assert original_minimum <= literal <= original_maximum
    domain_width = original_maximum - original_minimum
    assert domain_width > 0
    margin = domain_width / Decimal("1000000")
    if literal - original_minimum >= original_maximum - literal:
        narrowed_maximum = literal - margin
        if narrowed_maximum < original_minimum:
            narrowed_minimum = literal + margin
            narrowed_maximum = original_maximum
        else:
            narrowed_minimum = original_minimum
    else:
        narrowed_minimum = literal + margin
        if narrowed_minimum > original_maximum:
            narrowed_minimum = original_minimum
            narrowed_maximum = literal - margin
        else:
            narrowed_maximum = original_maximum
    assert narrowed_minimum <= narrowed_maximum
    assert not narrowed_minimum <= literal <= narrowed_maximum
    narrowed_rule = selected_rule.model_copy(
        update={"minimum": narrowed_minimum, "maximum": narrowed_maximum}
    )
    narrowed_rules = tuple(
        narrowed_rule if rule is selected_rule else rule
        for rule in prepared.root_profile.n5.component_rules
    )

    quota_policy = BudgetInvocationQuotaPolicy(
        allocation_id=f"cyc04-candidate-fallback-{uuid.uuid4().hex}",
        total_units=3,
        protected_units=1,
    )
    assert quota_policy.work_unit == "n5_physical_invocation"
    assert prepared.root_profile.n5.replications == 2
    n5_fields = prepared.root_profile.n5.model_dump(mode="python")
    n5_fields.update(
        component_rules=narrowed_rules,
        invocation_quota_policy=quota_policy,
        invocation_purpose="standard",
    )
    configured_n5 = GenericCycleN5RequestProfileV3.model_validate(n5_fields)
    profile_fields = prepared.root_profile.model_dump(mode="python", exclude={"content_hash"})
    profile_fields["n5"] = configured_n5
    configured_root_profile = _hashed_model(
        type(prepared.root_profile), profile_fields, hash_fn=gy_content_hash
    )
    assert configured_root_profile.profile_selection_kind == "problem"
    assert (
        configured_root_profile.n5.component_rules[0]
        != (configured_root_profile.n5.component_rules[1])
    )
    assert (
        configured_root_profile.profile_selection_ref == prepared.root_profile.profile_selection_ref
    )
    assert tuple(
        rule
        for rule in configured_root_profile.n5.component_rules
        if (str(rule.operator_kind), (rule.target_world_slot,)) != prepared_grounded_semantic
    ) == tuple(
        rule
        for rule in prepared.root_profile.n5.component_rules
        if (str(rule.operator_kind), (rule.target_world_slot,)) != prepared_grounded_semantic
    )
    assert configured_root_profile.content_hash != prepared.root_profile.content_hash

    prepared = replace(
        prepared,
        request_json={
            **prepared.request_json,
            "max_iterations": 1,
            "run_budget_usd": 10.0,
        },
    )
    # This served app has the single immutable root profile. The helper's
    # derived child profiles are source material for the additive root only.
    prepared.app_kwargs["generic_cycle_simulation_profiles"] = (configured_root_profile,)
    assert prepared.app_kwargs["generic_cycle_simulation_profiles"] == (configured_root_profile,)

    compiler_owner = generation_cycle_service
    original_compiler = compiler_owner.build_design_problem_from_nl_request

    async def compile_with_deterministic_spans(**kwargs: Any) -> Any:
        kwargs.setdefault("span_support_client", _DeterministicSpanSupportClient())
        return await original_compiler(**kwargs)

    monkeypatch.setattr(
        compiler_owner,
        "build_design_problem_from_nl_request",
        compile_with_deterministic_spans,
    )

    initial_generations: list[dict[str, Any]] = []
    materialization_attempts: list[dict[str, Any]] = []
    materialization_refusals: list[dict[str, Any]] = []
    root_n5_inputs: list[tuple[GenericCycleSimulationN5InputV1, Any]] = []
    physical_n5_requests: list[Any] = []
    n4_port_calls: list[dict[str, Any]] = []
    actual_n4_organs: list[DesignGenerationOrganRun] = []
    root_currentness_observations: list[tuple[Any, Any, Any, Any, Any]] = []
    provider_call_counts_at_materialization: list[int] = []
    foreign_profile_probes: list[str] = []
    temporal_read_refusal_probes: list[str] = []

    def is_configured_root(controller: GenerationCycleController) -> bool:
        handoff = controller._generic_cycle_simulation_handoff
        return bool(
            handoff is not None
            and handoff.profile.profile_id == configured_root_profile.profile_id
            and handoff.profile.profile_selection_kind == "problem"
        )

    original_generate = GenerationCycleController._generate_node

    async def observe_actual_root_generation(
        controller: GenerationCycleController,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        generated = await original_generate(controller, state)
        if is_configured_root(controller) and int(state["cycle_index"]) == 0:
            candidates = tuple(generated["candidates"])
            rankings = generated["rankings"]
            top = generated["selected_candidate"]
            maximum_score = max(
                rankings.get(_candidate_id(candidate), (0.0, 0.0))[0] for candidate in candidates
            )
            assert rankings.get(_candidate_id(top), (0.0, 0.0))[0] == maximum_score
            initial_generations.append(
                {
                    "candidate_ids": tuple(_candidate_id(candidate) for candidate in candidates),
                    "candidate_semantics": {
                        _candidate_id(candidate): semantic_key(candidate)
                        for candidate in candidates
                    },
                    "rankings": dict(rankings),
                    "top_candidate_id": _candidate_id(top),
                    "top_semantic": semantic_key(top),
                }
            )
        return generated

    monkeypatch.setattr(
        GenerationCycleController,
        "_generate_node",
        observe_actual_root_generation,
    )

    original_n4_call = N4GenerationPort.__call__

    async def observe_n4_port_call(
        port: N4GenerationPort,
        problem: object,
        *,
        cycle_index: int,
    ) -> object:
        used_prefetched_organ = port._prefetched_organ_run is not None
        if used_prefetched_organ:
            assert n4_port_calls
            assert port._llm_client is n4_port_calls[0]["llm_client"]
        result = await original_n4_call(port, problem, cycle_index=cycle_index)
        n4_port_calls.append(
            {
                "used_prefetched_organ": used_prefetched_organ,
                "result": result,
                "llm_client": port._llm_client,
            }
        )
        if not used_prefetched_organ and type(result) is DesignGenerationOrganRun:
            actual_n4_organs.append(result)
        return result

    monkeypatch.setattr(N4GenerationPort, "__call__", observe_n4_port_call)

    original_currentness_resolver = RecursiveLeafContextOwner.generic_root_currentness_resolver

    def observe_root_currentness_resolver(
        owner: RecursiveLeafContextOwner,
        *,
        handoff: Any,
        problem: Any,
        currentness: Any,
    ) -> Any:
        callback = original_currentness_resolver(
            owner,
            handoff=handoff,
            problem=problem,
            currentness=currentness,
        )
        root_currentness_observations.append((owner, handoff, problem, currentness, callback))
        return callback

    monkeypatch.setattr(
        RecursiveLeafContextOwner,
        "generic_root_currentness_resolver",
        observe_root_currentness_resolver,
    )

    original_materialize = GenericCycleSimulationAdmissionOwner.materialize_source_atoms

    def observe_actual_materialization(
        owner: GenericCycleSimulationAdmissionOwner,
        **kwargs: Any,
    ) -> Any:
        if not foreign_profile_probes:
            # Exercise the selected-view fence while the real lease is current;
            # a stale lease must not mask a foreign manifest rejection.
            assert len(root_currentness_observations) == 1
            root_owner, handoff, problem, currentness, callback = root_currentness_observations[0]
            assert currentness() is True
            assert callback() is True
            assert not physical_n5_requests
            assert not materialization_attempts
            selected = handoff.profile_ref
            store = owner.store
            manifest = store.get_manifest(selected)
            foreign = store.put_bytes(
                store.get_bytes(selected),
                ArtifactWriteOptions(
                    kind=selected.kind,
                    media_type=selected.media_type,
                    schema=manifest.artifact_schema,
                    producer=ProducerInfo(component="test.foreign-root-profile", version="1"),
                    env=manifest.env,
                    inputs=manifest.inputs,
                    canon=manifest.canon,
                    governance=manifest.governance,
                    tenant_context=manifest.tenant_context,
                    same_input_closure=manifest.same_input_closure,
                    authority=manifest.authority,
                    warnings=manifest.warnings,
                ),
                return_selected_profile=True,
            )
            foreign = ArtifactRef.model_validate(foreign.model_dump(mode="python"))
            assert foreign.artifact_id == selected.artifact_id
            assert foreign.manifest_profile_sha256 != selected.manifest_profile_sha256
            foreign_callback = original_currentness_resolver(
                root_owner,
                handoff=handoff.model_copy(update={"profile_ref": foreign}),
                problem=problem,
                currentness=currentness,
            )
            with pytest.raises(CycleSubstrateContextOwnerError) as refused:
                foreign_callback()
            assert (
                refused.value.code == "generic_cycle_simulation_profile_manifest_binding_mismatch"
            )
            assert callback() is True
            assert not physical_n5_requests
            assert not materialization_attempts
            foreign_profile_probes.append(refused.value.code)
        row = {
            "candidate_ids": tuple(kwargs["candidate_ids"]),
            "source_ref": kwargs["source_ref"],
        }
        materialization_attempts.append(row)
        provider_call_counts_at_materialization.append(
            sum(len(organ.result.llm_calls) for organ in actual_n4_organs)
        )
        try:
            return original_materialize(owner, **kwargs)
        except InterventionSubstrateError as exc:
            row["error_code"] = exc.code
            if exc.code == "candidate_scenario_value_outside_profile_domain":
                assert not physical_n5_requests
                materialization_refusals.append(dict(row))
            raise

    monkeypatch.setattr(
        GenericCycleSimulationAdmissionOwner,
        "materialize_source_atoms",
        observe_actual_materialization,
    )

    original_joint_simulation_call = JointSimulationPort.__call__

    def observe_joint_simulation(
        simulation_port: JointSimulationPort,
        **kwargs: Any,
    ) -> Any:
        n5_input = kwargs.get("generic_cycle_simulation_input")
        if (
            type(n5_input) is GenericCycleSimulationN5InputV1
            and n5_input.profile.profile_id == configured_root_profile.profile_id
        ):
            if not temporal_read_refusal_probes:
                currentness_resolver = kwargs.get("generic_cycle_simulation_currentness_resolver")
                controller = getattr(currentness_resolver, "__self__", None)
                assert type(controller) is GenerationCycleController
                assert (
                    getattr(currentness_resolver, "__func__", None)
                    is GenerationCycleController._require_current_generic_cycle_simulation_handoff
                )
                assert controller._generic_cycle_simulation_handoff is not None
                assert (
                    controller._generic_cycle_simulation_handoff.context_job_ref
                    == n5_input.context_job_ref
                )
                assert len(root_currentness_observations) == 1
                context_owner = controller._candidate_cycle_context_artifact_owner
                assert context_owner is root_currentness_observations[0][0]._context_owner
                original_context_admission_verifier = context_owner._context_admission_verifier
                assert original_context_admission_verifier is None or callable(
                    original_context_admission_verifier
                )
                assert not materialization_attempts
                assert not physical_n5_requests
                assert not root_n5_inputs
                input_ref = kwargs.get("generic_cycle_simulation_input_ref")
                assert type(input_ref) is ArtifactRef
                assert kwargs["candidate"].candidate_id == n5_input.candidate_id
                counts_before_refusal_probe = (
                    len(materialization_attempts),
                    len(physical_n5_requests),
                    len(root_n5_inputs),
                    len(actual_n4_organs),
                    sum(len(organ.result.llm_calls) for organ in actual_n4_organs),
                )

                def refuse_selected_context_job(ref: ArtifactRef, context: Any) -> bool:
                    if ref == n5_input.context_job_ref:
                        return False
                    assert callable(original_context_admission_verifier)
                    return original_context_admission_verifier(ref, context)

                context_owner._context_admission_verifier = refuse_selected_context_job
                try:
                    with pytest.raises(CycleSubstrateContextOwnerError) as refused_read:
                        simulation_port._build_generic_cycle_simulation_request(
                            candidate=kwargs["candidate"],
                            problem=kwargs["problem"],
                            input_record=n5_input,
                            input_ref=input_ref,
                            currentness_resolver=currentness_resolver,
                        )
                finally:
                    context_owner._context_admission_verifier = original_context_admission_verifier
                assert refused_read.value.code == (
                    "cycle_substrate_context_temporal_read_not_established"
                )
                assert counts_before_refusal_probe == (
                    len(materialization_attempts),
                    len(physical_n5_requests),
                    len(root_n5_inputs),
                    len(actual_n4_organs),
                    sum(len(organ.result.llm_calls) for organ in actual_n4_organs),
                )
                temporal_read_refusal_probes.append(refused_read.value.code)
        result = original_joint_simulation_call(simulation_port, **kwargs)
        if (
            type(n5_input) is GenericCycleSimulationN5InputV1
            and n5_input.profile.profile_id == configured_root_profile.profile_id
        ):
            root_n5_inputs.append((n5_input, result))
        return result

    monkeypatch.setattr(JointSimulationPort, "__call__", observe_joint_simulation)

    original_horizon_run = JointSimulationHorizonController.run

    def observe_physical_n5(
        controller: JointSimulationHorizonController,
        request: Any,
    ) -> Any:
        physical_n5_requests.append(request)
        return original_horizon_run(controller, request)

    monkeypatch.setattr(JointSimulationHorizonController, "run", observe_physical_n5)

    observed_budget_owners: list[Any] = []
    original_budget_owner_builder = run_lifecycle._build_control_nl_producer_budget_reconciler

    def capture_budget_owner(**kwargs: Any) -> Any:
        observer = original_budget_owner_builder(**kwargs)
        observed_budget_owners.append(observer)
        return observer

    monkeypatch.setattr(
        run_lifecycle,
        "_build_control_nl_producer_budget_reconciler",
        capture_budget_owner,
    )

    app = create_runtime_api_app(**prepared.app_kwargs)
    idempotency_key = uuid.uuid4().hex

    def execution_counts() -> tuple[int, int, int, int, int]:
        return (
            len(initial_generations),
            len(n4_port_calls),
            len(actual_n4_organs),
            sum(len(organ.result.llm_calls) for organ in actual_n4_organs),
            len(physical_n5_requests),
        )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/control/runs/nl",
            headers={"Idempotency-Key": idempotency_key},
            json=prepared.request_json,
        )
        assert response.status_code == 200, response.text
        accepted = response.json()
        assert accepted.get("status") == "accepted"
        service = app.state._control_service
        dispatched = dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=accepted["job_id"],
        )
        assert dispatched == accepted["job_id"]
        job = service._control_store.get_job(accepted["job_id"])
        assert job is not None and job.state == "completed"

        assert len(root_currentness_observations) == 1
        owner, handoff, problem, currentness, callback = root_currentness_observations[0]
        assert type(owner) is RecursiveLeafContextOwner
        assert handoff.profile.profile_id == configured_root_profile.profile_id
        assert handoff.profile.profile_selection_kind == "problem"
        assert problem is not None and callable(currentness) and callable(callback)
        stale_counts = (
            len(materialization_attempts),
            len(physical_n5_requests),
            len(actual_n4_organs),
            sum(len(organ.result.llm_calls) for organ in actual_n4_organs),
        )
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            assert currentness() is False
            with pytest.raises(RecursiveGenerationCycleError) as stale_callback_error:
                callback()
        assert stale_callback_error.value.code == "recursive_generic_root_lease_not_current"
        assert stale_counts == (
            len(materialization_attempts),
            len(physical_n5_requests),
            len(actual_n4_organs),
            sum(len(organ.result.llm_calls) for organ in actual_n4_organs),
        )

        run_id = str(job.progress["core_run_id"])
        get_response = client.get(f"/api/v1/runs/{run_id}")
        assert get_response.status_code == 200, get_response.text
        projected_run = get_response.json()["run"]
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            compiled_payload = service._load_payload_ref(
                job.progress["compiled_recursive_generation_cycle_ref"],
                kind="runtime.compiled_recursive_generation_cycle",
            )

        counts_before_idempotent_retry = (
            *execution_counts(),
            len(root_n5_inputs),
        )
        materializations_before_idempotent_retry = len(materialization_attempts)
        retry_response = client.post(
            "/api/v1/control/runs/nl",
            headers={"Idempotency-Key": idempotency_key},
            json=prepared.request_json,
        )
        assert retry_response.status_code == 200, retry_response.text
        assert retry_response.json()["job_id"] == accepted["job_id"]
        assert len(materialization_attempts) == materializations_before_idempotent_retry
        retry_get_response = client.get(f"/api/v1/runs/{run_id}")
        assert retry_get_response.status_code == 200, retry_get_response.text
        retry_projected_run = retry_get_response.json()["run"]
        assert counts_before_idempotent_retry == (
            *execution_counts(),
            len(root_n5_inputs),
        )

    compiled = generation_cycle_service.CompiledRecursiveGenerationCycleRun.model_validate(
        compiled_payload
    )
    assert len(initial_generations) == 1
    assert len(n4_port_calls) == 2
    assert tuple(call["used_prefetched_organ"] for call in n4_port_calls) == (False, True)
    assert len(actual_n4_organs) == 1
    assert len(actual_n4_organs[0].result.llm_calls) == len(prepared.organ_run.result.llm_calls)
    assert all(
        count == len(actual_n4_organs[0].result.llm_calls)
        for count in provider_call_counts_at_materialization
    )
    assert foreign_profile_probes == ["generic_cycle_simulation_profile_manifest_binding_mismatch"]
    assert temporal_read_refusal_probes == ["cycle_substrate_context_temporal_read_not_established"]
    assert len(materialization_refusals) == 1
    assert len(materialization_refusals[0]["candidate_ids"]) == 1
    failed_candidate_id = materialization_refusals[0]["candidate_ids"][0]
    assert materialization_refusals[0]["error_code"] == (
        "candidate_scenario_value_outside_profile_domain"
    )
    assert len(physical_n5_requests) == 1
    assert physical_n5_requests[0].replications == 2
    assert len(root_n5_inputs) == 1
    root_n5_input, root_n5_observation = root_n5_inputs[0]
    assert root_n5_input.profile == configured_root_profile
    assert root_n5_input.profile_ref.manifest_profile_sha256 is not None
    assert root_n5_observation.status == "joint_simulated"
    assert initial_generations[0]["top_semantic"] == prepared_top_semantic
    assert initial_generations[0]["candidate_semantics"][failed_candidate_id] == (
        prepared_grounded_semantic
    )

    root_node = next(
        node
        for node in compiled.recursive_run.nodes
        if isinstance(node, RecursiveCycleNode)
        and node.node_ref == compiled.recursive_run.root_node_ref
    )
    assert root_node.cycle_run is not None
    root_run = root_node.cycle_run
    assert len(root_run.cycles) == 1
    cycle = root_run.cycles[0]
    failed_summaries = tuple(
        summary
        for summary in root_run.candidate_summaries
        if summary.evaluation_attempt is not None
    )
    assert len(failed_summaries) == 1
    failed_summary = failed_summaries[0]
    failed_attempt = failed_summary.evaluation_attempt
    assert failed_attempt is not None
    assert failed_attempt.candidate_id == failed_candidate_id
    assert failed_attempt.failure_stage == "n5"
    assert failed_summary.grounding_status == "grounded_shadow"
    assert failed_attempt.simulation.authority_blockers == (
        "candidate_scenario_value_outside_profile_domain",
    )
    selected_candidate_id = cycle.selected_candidate_ref
    assert selected_candidate_id != failed_attempt.candidate_id
    assert root_n5_input.candidate_id == selected_candidate_id
    summaries_by_id = {summary.candidate_id: summary for summary in root_run.candidate_summaries}
    selected_summary = summaries_by_id[selected_candidate_id]
    assert selected_summary.evaluation_attempt is None
    assert selected_summary.grounding_status == "grounded_shadow"
    assert cycle.simulation.status == "joint_simulated"
    assert cycle.simulation.generic_n5_input_ref is not None
    assert cycle.simulation.simulation_result_ref is not None
    assert cycle.simulation.generic_profile_selection_ref == (
        configured_root_profile.profile_selection_ref
    )
    assert compiled.generic_n4_child_profile_status == "not_established"
    assert compiled.n4_child_profile_set_ref is None
    assert compiled.n4_child_profile_bindings == ()

    generic_projection = projected_run["generic_cycle_simulation"]
    assert generic_projection["child_profile_status"] == "not_established"
    assert generic_projection["child_profile_set_ref"] is None
    assert generic_projection["child_profile_bindings"] == []
    assert generic_projection["candidate_evaluation_attempts_limitation_code"] is None
    projected_attempts = generic_projection["candidate_evaluation_attempts"]
    assert len(projected_attempts) == 1
    assert projected_attempts[0]["candidate_id"] == failed_attempt.candidate_id
    assert projected_attempts[0]["failure_stage"] == "n5"
    assert projected_attempts[0]["simulation_status"] == "simulation_blocked"
    projected_n5_observations = generic_projection["n5_observations"]
    assert len(projected_n5_observations) == 1
    assert projected_n5_observations[0]["candidate_id"] == selected_candidate_id
    assert projected_n5_observations[0]["status"] == "joint_simulated"
    retry_generic_projection = retry_projected_run["generic_cycle_simulation"]
    assert retry_generic_projection["child_profile_status"] == "not_established"
    assert retry_generic_projection["child_profile_set_ref"] is None
    assert retry_generic_projection["candidate_evaluation_attempts"][0]["failure_stage"] == "n5"

    counts_before_fresh_app_get = (*execution_counts(), len(root_n5_inputs))
    fresh_app = create_runtime_api_app(**prepared.app_kwargs)
    with TestClient(fresh_app) as fresh_client:
        fresh_get_response = fresh_client.get(f"/api/v1/runs/{run_id}")
        assert fresh_get_response.status_code == 200, fresh_get_response.text
        fresh_projected_run = fresh_get_response.json()["run"]
    fresh_generic_projection = fresh_projected_run["generic_cycle_simulation"]
    assert counts_before_fresh_app_get == (*execution_counts(), len(root_n5_inputs))
    assert fresh_generic_projection["child_profile_status"] == "not_established"
    assert fresh_generic_projection["child_profile_set_ref"] is None
    assert fresh_generic_projection["child_profile_bindings"] == []
    fresh_attempts = fresh_generic_projection["candidate_evaluation_attempts"]
    assert len(fresh_attempts) == 1
    assert fresh_attempts[0]["candidate_id"] == failed_attempt.candidate_id
    assert fresh_attempts[0]["attempt_ref"] == projected_attempts[0]["attempt_ref"]
    assert fresh_attempts[0]["failure_stage"] == "n5"
    assert fresh_attempts[0]["simulation_status"] == "simulation_blocked"
    fresh_n5_observations = fresh_generic_projection["n5_observations"]
    assert len(fresh_n5_observations) == 1
    assert fresh_n5_observations[0]["candidate_id"] == selected_candidate_id
    assert fresh_n5_observations[0]["status"] == "joint_simulated"
    assert fresh_n5_observations[0]["n5_input_ref"] == projected_n5_observations[0]["n5_input_ref"]
    assert (
        fresh_n5_observations[0]["simulation_result_ref"]
        == (projected_n5_observations[0]["simulation_result_ref"])
    )

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        simulation_result = load_joint_simulation_result(
            cycle.simulation.simulation_result_ref,
            store=service._artifact_store,
        )
        selected_ncm = load_ncm_spec_default_view(
            ensure_ir_artifact_store(service._artifact_store),
            NCMSpecRef.model_validate(
                root_n5_input.profile.selected_ncm_ref.model_dump(mode="python")
            ),
        )

    profile_world_model = root_n5_input.profile.context_inputs.world_model_record
    assert simulation_result.world_model_record_content_hash == profile_world_model.content_hash
    assert simulation_result.selected_outcomes == (root_n5_input.outcome_variable,)
    outcome = root_n5_input.outcome_variable
    assert type(root_n5_input.n5) is GenericCycleN5RequestProfileV3
    assert len(root_n5_input.component_materializations) == 1
    (materialization,) = root_n5_input.component_materializations
    assert materialization.candidate_id == selected_candidate_id
    assignments = tuple(materialization.derived_n5_atom.causal_do_expr.assignments)
    assert len(assignments) == 1
    (assignment,) = assignments
    assert assignment.value_expr is None
    request_binding = root_n5_observation.generic_n5_request_binding
    assert request_binding is not None
    request = request_binding.request
    assert request.evidence_state is None
    assert request.baseline_state == root_n5_input.n5.baseline_state
    assert tuple(request.intervention_atoms) == (materialization.derived_n5_atom,)
    assert request.selected_outcomes == (root_n5_input.outcome_variable,)
    assert request.seed == root_n5_input.n5.seed
    assert request.replications == root_n5_input.n5.replications == 2
    target_slots = {rule.target_world_slot for rule in root_n5_input.n5.component_rules}
    outcome_equations = tuple(
        equation for equation in selected_ncm.structural_equations if equation.variable == outcome
    )
    assert len(outcome_equations) == 1
    outcome_equation = outcome_equations[0]
    coefficients = outcome_equation.equation_params["coefficients"]
    assert selected_ncm.scm_spec is None
    assert selected_ncm.fit_method == "declared_additive_joint_candidate_fixture_not_empirical"
    assert set(selected_ncm.endogenous_vars) == set(request.baseline_state)
    assert set(coefficients) == target_slots
    assert coefficients == dict.fromkeys(target_slots, 0.5)
    assert outcome_equation.equation_params["intercept"] == pytest.approx(
        request.baseline_state[outcome], abs=1e-12
    )
    assert assignment.variable in target_slots
    expected_effect = float(coefficients[assignment.variable]) * (
        float(assignment.value) - request.baseline_state[assignment.variable]
    )
    selected_world_model = request.world_model_record
    assert selected_world_model.content_hash == profile_world_model.content_hash
    assert {equation.variable for equation in selected_ncm.structural_equations} == set(
        selected_ncm.endogenous_vars
    )
    selected_units = {slot.slot_id: slot.unit for slot in selected_world_model.policy_slot_map}
    outcome_unit = selected_units[outcome]
    target_unit = selected_units[assignment.variable]
    assert isinstance(outcome_unit, str) and outcome_unit.strip()
    assert isinstance(target_unit, str) and target_unit.strip()

    cas_joint_trajectories = tuple(
        trajectory
        for trajectory in simulation_result.trajectories
        if trajectory.run_level == "joint"
    )
    assert len(cas_joint_trajectories) == 1
    (cas_joint_trajectory,) = cas_joint_trajectories
    assert len(cas_joint_trajectory.points) == 1
    (cas_joint_point,) = cas_joint_trajectory.points
    sampling = cas_joint_point.replication_sampling
    assert sampling is not None
    expected_seeds = tuple(range(request.seed, request.seed + request.replications))
    assert sampling.status == "estimated"
    assert sampling.replicate_count == request.replications == 2
    assert sampling.seeds == expected_seeds
    assert tuple(sample.seed for sample in sampling.samples) == expected_seeds
    effect_samples = tuple(float(sample.effects[outcome]) for sample in sampling.samples)
    outcome_samples = tuple(float(sample.outcomes[outcome]) for sample in sampling.samples)
    # The actual bound request uses its complete baseline as factual evidence;
    # the declared symbolic linear model therefore has zero residual noise for
    # every seed, so this is an exact fixture arithmetic oracle.
    assert effect_samples == pytest.approx(
        (expected_effect,) * request.replications,
        abs=1e-12,
    )
    assert outcome_samples == pytest.approx(
        (request.baseline_state[outcome] + expected_effect,) * request.replications,
        abs=1e-12,
    )
    effect_mean = sum(effect_samples) / len(effect_samples)
    outcome_mean = sum(outcome_samples) / len(outcome_samples)
    effect_standard_error = (
        sum((value - effect_mean) ** 2 for value in effect_samples)
        / (len(effect_samples) - 1)
        / len(effect_samples)
    ) ** 0.5
    outcome_standard_error = (
        sum((value - outcome_mean) ** 2 for value in outcome_samples)
        / (len(outcome_samples) - 1)
        / len(outcome_samples)
    ) ** 0.5
    assert cas_joint_point.effect[outcome] == pytest.approx(effect_mean, abs=1e-12)
    assert cas_joint_point.outcomes[outcome] == pytest.approx(outcome_mean, abs=1e-12)
    assert sampling.effects_standard_error[outcome] == pytest.approx(
        effect_standard_error, abs=1e-12
    )
    assert sampling.outcomes_standard_error[outcome] == pytest.approx(
        outcome_standard_error, abs=1e-12
    )

    fresh_n5_observation = fresh_n5_observations[0]
    assert fresh_n5_observation["simulation_result_body_status"] == "resolved"
    assert fresh_n5_observation["simulation_result_body_limitation_code"] is None
    fresh_result_body = fresh_n5_observation["simulation_result_body"]
    assert fresh_result_body["artifact_ref"] == fresh_n5_observation["simulation_result_ref"]
    assert fresh_result_body["world_model_record_content_hash"] == (
        selected_world_model.content_hash
    )
    assert fresh_result_body["world_model_record_ref"] == (
        selected_world_model.world_model_record_id
    )
    assert fresh_result_body["selected_outcomes"] == [outcome]
    public_joint_trajectories = tuple(
        trajectory
        for trajectory in fresh_result_body["trajectories"]
        if trajectory["run_level"] == "joint"
    )
    assert len(public_joint_trajectories) == 1
    (public_joint_trajectory,) = public_joint_trajectories
    assert len(public_joint_trajectory["points"]) == 1
    (public_joint_point,) = public_joint_trajectory["points"]
    assert public_joint_point["step"] == cas_joint_point.step
    assert public_joint_point["effects"][outcome] == pytest.approx(
        cas_joint_point.effect[outcome], abs=1e-12
    )
    assert public_joint_point["outcomes"][outcome] == pytest.approx(
        cas_joint_point.outcomes[outcome], abs=1e-12
    )
    # The generic result body exposes its exact finite trajectory row only;
    # replication samples/SE and outcome units remain unavailable on this DTO.
    assert set(public_joint_point) == {"step", "outcomes", "effects"}
    assert "outcome_units" not in fresh_result_body
    assert "effects_standard_error" not in fresh_result_body

    physical_work = tuple(simulation_result.physical_work_observations)
    assert len(physical_work) == 2
    assert all(
        row.status == "completed"
        and row.invocation_quota_status == "completed"
        and row.invocation_quota_purpose == "standard"
        and row.invocation_quota_operation_id is not None
        and row.invocation_quota_request_digest is not None
        for row in physical_work
    )
    assert len(observed_budget_owners) == 1
    budget_owner = observed_budget_owners[0]
    assert budget_owner.invocation_purpose == "standard"
    capacity = budget_owner.observe_standard_invocation_capacity()
    assert capacity.status == "exhausted"
    assert capacity.predicate_basis == "independently_reconciled"
    assert capacity.standard_limit_units == 2
    assert capacity.standard_remaining_units == 0
    assert capacity.protected_limit_units == 1
    assert capacity.protected_remaining_units == 1
    assert len(capacity.terminal_witnesses) == 2
