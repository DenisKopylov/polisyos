"""Real current-job method reseal and its hosted paired Generic observation.

The served Control/N4/input writers and registered source/WMR producers are
real. The preflight target stops before physical work. The explicit recorded
host target executes the actual empty/treatment pair and reads its seed;
neither target grants protected-use or publication authority.
"""

from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from polisyos.core import artifacts
from polisyos.core.contracts import (
    load_model_input_obligation_set,
    load_resolved_input_binding_manifest,
)
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.data_plane import load_input_bindings, replay_selected_method_input_facts
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.ir.trinity import load_trinity_bundle_artifact
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.container import RuntimeContainerOverrides
from polisyos.runtime.http.dependencies import build_runtime_api_context
from polisyos.runtime.http.deployment_security import (
    DeploymentSecurityConfig,
    build_deployment_security,
)
from polisyos.runtime.http.services.control import generation_cycle as generation_owner
from polisyos.runtime.quality.candidate_simulation import CandidateSimulationContextInputs
from polisyos.runtime.quality.cycle_substrate import cycle_job_profile_selection_ref
from polisyos.runtime.quality.data_state_substrate import (
    build_derived_model_input_candidate_world,
)
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.generic_simulation_admission import (
    GenericCycleN5PairedProgramGraphRequestProfileV5,
    GenericCycleSimulationAdmissionOwner,
    GenericCycleSimulationN5InputV1,
    GenericCycleSimulationProfileV1,
    GenericN5ExecutionJoinExpectation,
    GenericN5InitialMethodInputRequest,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    HorizonSpec,
    JointSimulationControllerError,
    JointSimulationHorizonController,
    JointSimulationRequest,
    _require_program_graph_input_preflight,
)
from polisyos.runtime.quality.model_input_requirements import preflight_program_graph_inputs
from polisyos.runtime.quality.world_model_record import world_model_artifact_views
from polisyos.scientist.orchestration.engine import BudgetInvocationQuotaPolicy
from tests._helpers import acquisition_served_history as served
from tests._helpers import world_model_record as world_fixture
from tests._helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker
from tests._helpers.derived_input_world import build_selected_method_base_world
from tests._helpers.registered_derived_method_input import materialize_registered_method_input_case
from tests._helpers.runtime_http import _DeterministicSpanSupportClient, _valid_intake_for_mode
from tests._helpers.selected_method_input import (
    prepare_selected_method_input_case,
    selected_method_tax_subsidy_policy,
)
from tests.integration.runtime_quality.test_generic_n4_child_profile_set_served import (
    controlled_candidate_gateway as _gateway_fixture,
)
from tests.integration.runtime_quality.test_program_graph_model_input_served import (
    _fiscal_problem,
    _stock_grounding_source,
)
from tests.integration.runtime_quality.test_program_graph_stock_n7_served import (
    _configure_stock_provider,
    _provision_empty_stock_catalog,
)
from tests.unit.runtime.quality.test_generic_simulation_admission_program_graph import _with_hash

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from polisyos.runtime.quality.world_model_record import SkgCausalPriorRef
    from tests._helpers.controlled_candidate_profile import ControlledCandidateGateway

controlled_candidate_gateway = _gateway_fixture


class _InitialPreflightObserved(BaseException):
    """End the real job after strict current intake and before physical work."""


@pytest.mark.integration
def test_current_job_reseals_real_method_world_before_its_first_n5(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: ControlledCandidateGateway,
) -> None:
    """Use real job/N4/context refs rather than relabeling the source invocation."""
    _run_current_job_real_method_world(
        tmp_path, monkeypatch, controlled_candidate_gateway, preflight_only=True
    )


def _run_current_job_real_method_world(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: ControlledCandidateGateway,
    *,
    preflight_only: bool,
) -> None:
    """Share real producer setup; only the nonnumerical case installs a stop."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("POLISYOS_RUNTIME_EXECUTION_PROFILE", "development")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", str(tmp_path / "control.sqlite3"))
    monkeypatch.setenv("POLISYOS_CACHE_HOME", str(tmp_path / "runtime-cache"))
    root = tmp_path / "knowledge"
    selected_skg = _stock_grounding_source(root)
    _provision_empty_stock_catalog(root)
    problem_payload = _fiscal_problem().model_dump(mode="json")
    problem_payload["jurisdiction_time"].update(
        region="UA", valid_time="2024", as_of="2024-12-31", policy_time="2024", data_time="2024"
    )
    problem_payload["nl_provenance"]["raw_request"] = (
        "Evaluate the declared bounded 2024 income subsidy and the government balance in USD. "
        "Use the selected registered period-flow observations. Do not promote generated candidates."
    )
    problem = DesignProblem.model_validate(problem_payload)
    assert problem.constraints[0].source_text in problem.nl_provenance.raw_request
    cas_root = tmp_path / "cas"
    runtime_context = build_runtime_api_context(cas_root=cas_root, core_runs_root=cas_root / "runs")
    prepared: list[
        tuple[
            artifacts.ArtifactRef,
            GenericCycleSimulationN5InputV1,
            GenericN5InitialMethodInputRequest,
        ]
    ] = []
    kernel_entries: list[str] = []
    original_prepare = GenericCycleSimulationAdmissionOwner.prepare_initial_method_input_request

    def inspect_preparation(
        owner: GenericCycleSimulationAdmissionOwner,
        *,
        input_ref: artifacts.ArtifactRef,
        input_record: GenericCycleSimulationN5InputV1,
        request: JointSimulationRequest,
    ) -> GenericN5InitialMethodInputRequest | None:
        result = original_prepare(
            owner, input_ref=input_ref, input_record=input_record, request=request
        )
        assert result is not None
        assert type(result.current_method_input_bindings_ref) is artifacts.ArtifactRef
        assert type(result.preflight.obligation_set_ref) is artifacts.ArtifactRef
        invocation = result.preflight.invocation
        with pytest.raises(ValueError, match=r"^model_input_method_selected_obligation_mismatch$"):
            preflight_program_graph_inputs(
                owner.store,
                interface_ref=invocation.interface_ref,
                program_graph_ref=invocation.program_graph_ref,
                exec_plan_ref=invocation.exec_plan_ref,
                registry_bundle_ref=invocation.registry_bundle_ref,
                input_bindings_ref=invocation.input_bindings_ref,
                context=invocation.context,
                steps=invocation.steps,
            )
        views = world_model_artifact_views(request.world_model_record)
        assert result.request.world_model_record == request.world_model_record
        assert artifacts.artifact_ref_identity_key(invocation.input_bindings_ref) == (
            artifacts.artifact_ref_identity_key(views.input_bindings_ref)
        )
        assert artifacts.artifact_ref_identity_key(result.current_method_input_bindings_ref) != (
            artifacts.artifact_ref_identity_key(views.input_bindings_ref)
        )
        bindings = load_input_bindings(owner.store, result.current_method_input_bindings_ref)
        assert artifacts.artifact_ref_identity_key(bindings.bound_state_snapshot_ref) == (
            artifacts.artifact_ref_identity_key(views.bound_state_snapshot_ref)
        )
        assert artifacts.artifact_ref_identity_key(bindings.data_snapshot_ref) != (
            artifacts.artifact_ref_identity_key(views.data_snapshot_ref)
        )
        manifest = load_resolved_input_binding_manifest(
            owner.store, bindings.resolved_binding_manifest_ref
        )
        selected_set, _ = load_model_input_obligation_set(
            owner.store, manifest.model_input_obligation_set_ref
        )
        assert selected_set.schema_version == "1.3"
        assert selected_set.authority_purpose == "candidate_execution_input_revalidation_only"
        assert selected_set.invocation == invocation
        assert invocation.context.run_id == input_record.run_id
        assert invocation.context.candidate_source_ref == input_record.n4_source_ref
        assert invocation.context.context_job_ref == input_record.context_job_ref
        cold_store = artifacts.FileSystemCAS(cas_root).for_tenant(served.TENANT, served.CELL)
        facts = replay_selected_method_input_facts(
            cold_store,
            input_bindings_ref=result.current_method_input_bindings_ref,
            expected_invocation=invocation,
        )
        assert tuple(facts.values) == ("ledger.flow",)
        prepared.append((input_ref, input_record, result))
        return result

    def inspect_preflight(
        controller: JointSimulationHorizonController,
        request: JointSimulationRequest,
        *,
        _program_graph_input_preflight: Callable[..., object],
    ) -> None:
        assert len(prepared) == 1
        current = prepared[0][2]
        assert request is current.request
        selected = controller._select_engine(request)
        assert selected.decision.decision == "selected"
        intake = _require_program_graph_input_preflight(
            request, selected.plan, selected.decision, _program_graph_input_preflight
        )
        assert intake is not None
        assert intake.invocation == current.preflight.invocation
        assert artifacts.artifact_ref_identity_key(intake.request.input_bindings_ref) == (
            artifacts.artifact_ref_identity_key(current.current_method_input_bindings_ref)
        )
        raise _InitialPreflightObserved

    def refuse_kernel(_controller: object, *args: object, **kwargs: object) -> None:
        kernel_entries.append("program_graph")
        raise AssertionError("preflight-only current method test entered a physical kernel")

    if preflight_only:
        monkeypatch.setattr(
            GenericCycleSimulationAdmissionOwner,
            "prepare_initial_method_input_request",
            inspect_preparation,
        )
        monkeypatch.setattr(JointSimulationHorizonController, "run", inspect_preflight)
        monkeypatch.setattr(
            JointSimulationHorizonController, "_run_semantic_program_graph_horizon", refuse_kernel
        )
    case = None
    try:
        with tenant_scope(None, tenant_id=served.TENANT, cell_id=served.CELL):
            policy = selected_method_tax_subsidy_policy()
            intervention = policy.interventions[0].model_copy(
                update={
                    "notes": ["do.target=agents.income"],
                    "measurement_expectations": {
                        "sign": "increase",
                        "outcome": ["agents.income"],
                        "effect_path": ["tax_subsidy", "agents.income", "agents.income"],
                        "estimand": "average_treatment_effect",
                    },
                }
            )
            policy = type(policy).model_validate(
                {**policy.model_dump(mode="python"), "interventions": [intervention]}
            )
            case, metadata = prepare_selected_method_input_case(
                tmp_path / "selected",
                method_class=PeriodFlowToStock,
                mapped=True,
                method_input_slot="ledger.flow",
                snapshot_id=world_fixture.SNAPSHOT_ID,
                policy_spec=policy,
                income_values=(2**26, 2**27),
                store=runtime_context.store,
            )

            def selected_skg_ref(_path: Path, *, snapshot_id: str) -> SkgCausalPriorRef:
                # Select the real fiscal SKG owner above through the shared
                # test publisher; its full reference is verified by WMR.
                assert snapshot_id == selected_skg.source_data_snapshot_id
                return selected_skg

            with monkeypatch.context() as selected_source:
                selected_source.setattr(world_fixture, "_skg_ref", selected_skg_ref)
                base, registry, registry_ref = build_selected_method_base_world(
                    case, tmp_path / "base-world", policy_domain=problem.domain
                )
            materialize_registered_method_input_case(case, metadata)
            built = build_derived_model_input_candidate_world(
                case.store,
                base_world_model=base.record,
                substrate_registry=registry,
                substrate_registry_artifact_ref=registry_ref,
                materialization=metadata["batch_materialization"],
                workspace_dir=tmp_path / "derived-world",
                transaction_time=datetime(2026, 11, 14, 12, tzinfo=UTC),
            )
            profile = _with_hash(
                GenericCycleSimulationProfileV1.model_construct(
                    profile_id="test-current-derived-method",
                    profile_selection_ref=cycle_job_profile_selection_ref(problem),
                    world_model_record_ref=built.world_model.record_ref,
                    substrate_registry_ref=registry_ref,
                    context_inputs=CandidateSimulationContextInputs(
                        substrate_registry=registry,
                        selected_registry_entry_hashes=tuple(
                            entry.entry_content_hash for entry in registry.entries
                        ),
                        world_model_record=built.world_model.record,
                    ),
                    n5=GenericCycleN5PairedProgramGraphRequestProfileV5(
                        budget_ref="budget://test/current-derived-method",
                        horizon=HorizonSpec(start=0, end=0, step=1),
                        baseline_state={"government.balance": 10_000_000_000.0},
                        compile_report_ref=artifacts.ArtifactRef.model_validate(
                            case.compile_report_ref.model_dump(mode="python")
                        ),
                        invocation_quota_policy=BudgetInvocationQuotaPolicy(
                            allocation_id="test-current-derived-method",
                            total_units=5,
                            protected_units=1,
                        ),
                    ),
                    limitations=(
                        "controlled_inputs_only",
                        "currentness_not_established",
                        "n5_simulation_not_world_evidence",
                        "n9_not_admitted",
                        "s8_blocked",
                        "source_truth_not_established",
                    ),
                )
            )
            trinity = load_trinity_bundle_artifact(
                artifacts.ensure_ir_artifact_store(case.store), case.trinity_ref
            )
        model_id = _configure_stock_provider(
            controlled_candidate_gateway,
            problem=problem,
            trinity=trinity,
            evidence_root=tmp_path / "llm",
        )
        original_compiler = generation_owner.build_design_problem_from_nl_request

        async def bind_actual_compiler_output(**kwargs: object) -> DesignProblem:
            compiled = await original_compiler(
                **{**kwargs, "span_support_client": _DeterministicSpanSupportClient()}
            )
            controlled_candidate_gateway.admit_compiled_problem(compiled)
            return compiled

        monkeypatch.setattr(
            generation_owner, "build_design_problem_from_nl_request", bind_actual_compiler_output
        )
        with closing(served._ExternalTrust(tmp_path)) as trust:
            app = create_runtime_api_app(
                cas_root=cas_root,
                core_runs_root=cas_root / "runs",
                container_overrides=RuntimeContainerOverrides(runtime_api_context=runtime_context),
                deployment_security=build_deployment_security(
                    DeploymentSecurityConfig.from_mapping(trust.raw)
                ),
                enable_security_middlewares=True,
                enable_csrf_protection=False,
                generic_cycle_simulation_profiles=(profile,),
                generic_cycle_simulation_root_profile_id=profile.profile_id,
                repo_root=root,
            )
            with TestClient(app) as client:
                control = client.app.state.runtime_container.control_service
                stop_embedded_control_worker(control)
                response = client.post(
                    "/api/v1/control/runs/nl",
                    headers={
                        "Authorization": trust.authorization_header("acquisition-operator"),
                        "X-Tenant-ID": served.TENANT,
                        "Idempotency-Key": "current-derived-method-preflight",
                    },
                    json={
                        "request": problem.nl_provenance.raw_request,
                        "llm_model": model_id,
                        "max_iterations": 1,
                        "run_budget_usd": 5.0,
                        "run_budget_scope": "metered_paid_producers_and_bounded_candidate",
                        "context": {
                            "evaluation_safety_attempt": _valid_intake_for_mode(
                                "simulate_only"
                            ).model_dump(mode="json")
                        },
                    },
                )
                assert response.status_code == 200, response.text
                job_id = response.json()["job_id"]
                observed = False
                try:
                    dispatch_one_control_job(
                        store=control._control_store,
                        handler=control._process_control_job,
                        expected_job_id=job_id,
                    )
                except _InitialPreflightObserved:
                    observed = True
                job = control._control_store.get_job(job_id)
                if preflight_only:
                    assert observed, (
                        "initial_preflight_not_reached",
                        None if job is None else job.state,
                        None if job is None else job.error_message,
                    )
                    assert len(prepared) == 1
                    input_ref, input_record, current = prepared[0]
                    assert input_record.job_id == job_id
                    assert (
                        GenericCycleSimulationAdmissionOwner(
                            profiles=(), store=control._artifact_store
                        ).resolve_n5_input(input_ref, expected=input_record)
                        == input_record
                    )
                    assert current.preflight.invocation.context.run_id == input_record.run_id
                    assert kernel_entries == []
                    assert not (
                        control.llm_producer_settlement_store._ledger.snapshot().invocation_reservations
                    )
                else:
                    assert not observed
                    assert job is not None and job.state == "completed", (
                        "ordinary_method_n5_not_completed",
                        None if job is None else job.state,
                        None if job is None else job.error_message,
                    )
                    with tenant_scope(None, tenant_id=served.TENANT, cell_id=served.CELL):
                        source = control.resolve_completed_control_job_core_run_source(
                            job,
                            expected_control_run_id=job.run_id,
                            tenant_id=served.TENANT,
                            cell_id=served.CELL,
                        )
                    _assert_initial_observation_fresh_reader(
                        control,
                        monkeypatch=monkeypatch,
                        cas_root=cas_root,
                        sqlite_path=tmp_path / "control.sqlite3",
                        job_id=job_id,
                        run_id=str(job.run_id),
                        core_run_id=source.run_id,
                        client=client,
                        authorization=trust.authorization_header("acquisition-operator"),
                    )
    finally:
        if case is not None:
            case.close()


def _selected_method_result_expectation(
    store: artifacts.CoreJSONArtifactStore,
    *,
    input_ref: artifacts.ArtifactRef,
    result_ref: artifacts.ArtifactRef,
) -> GenericN5ExecutionJoinExpectation:
    """Supply the existing Generic owner with the selected source's exact joins."""
    source = GenericCycleSimulationN5InputV1.model_validate(
        artifacts.load_core_json_artifact(store, input_ref)
    )
    return GenericN5ExecutionJoinExpectation(
        input_ref=input_ref,
        result_ref=result_ref,
        status="joint_simulated",
        model_input_obligation_set_ref=None,
        n4_source_ref=source.n4_source_ref,
        context_job_ref=source.context_job_ref,
        profile_ref=source.profile_ref,
        child_family_ref=source.n4_child_profile_family_ref,
        child_set_ref=source.n4_child_profile_set_ref,
        profile_selection_ref=source.profile.profile_selection_ref,
        profile=source.profile,
        child_selection=source.child_selection,
        design_problem_ref=source.design_problem_ref,
        outcome_variable=source.outcome_variable,
        cycle_index=source.cycle_index,
        candidate_id=source.candidate_id,
        candidate_atom_hash=source.candidate_atom_hash,
        world_model_record_content_hash=source.profile.context_inputs.world_model_record.content_hash,
        job_id=source.job_id,
        run_id=source.run_id,
        source_run_id=source.source_run_id,
        tenant_id=source.tenant_id,
        cell_id=source.cell_id,
    )


def _assert_initial_observation_fresh_reader(
    control: Any,
    *,
    monkeypatch: pytest.MonkeyPatch,
    cas_root: Path,
    sqlite_path: Path,
    job_id: str,
    run_id: str,
    core_run_id: str,
    client: Any,
    authorization: str,
) -> None:
    """Reopen real completed output and test removal without another N5 call."""
    from fractions import Fraction

    import numpy as np

    from polisyos.core.registry import load_registry_bundle_content
    from polisyos.foundry.execute import (
        admit_semantic_horizon_step_chain,
        load_state_snapshot,
        resolve_program_graph_actuation,
    )
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.quality import model_input_requirements, model_input_routing
    from polisyos.runtime.quality.acquisition_evaluation import (
        read_generic_model_input_initial_evaluation_history,
    )
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
    from polisyos.runtime.quality.generic_simulation_admission import (
        parse_generic_cycle_simulation_n5_execution,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        _read_program_graph_paired_comparator,
        _semantic_program_graph_replications,
    )
    from polisyos.runtime.quality.n5_candidate_content import (
        GenericProgramGraphContentObservationV4,
        _read_generic_program_graph_observation_wire,
    )
    from polisyos.scientist.orchestration.engine import (
        BudgetMiddleware,
        BudgetState,
        FileBudgetLedger,
    )

    attempted: list[str] = []

    def refuse_new_work(*_args: object, **_kwargs: object) -> None:
        attempted.append("unexpected_producer_or_physical_call")
        raise AssertionError("historical initial read attempted new producer/physical work")

    monkeypatch.setattr(JointSimulationHorizonController, "run", refuse_new_work)
    monkeypatch.setattr(
        GenericCycleSimulationAdmissionOwner,
        "prepare_initial_method_input_request",
        refuse_new_work,
    )
    monkeypatch.setattr(
        model_input_requirements, "preflight_current_use_method_input_revalidation", refuse_new_work
    )
    monkeypatch.setattr(
        model_input_routing, "materialize_registered_derived_model_inputs", refuse_new_work
    )
    fresh_root = artifacts.FileSystemCAS(cas_root)
    fresh_store = fresh_root.for_tenant(served.TENANT, served.CELL)
    fresh_control = ControlPlaneStore(backend="sqlite", sqlite_path=sqlite_path)
    fresh_events = RuntimeDiagnosticEventLog(store=fresh_control, artifact_store=fresh_store)
    original_budget = control.llm_producer_settlement_store
    owner, resource, anchor = original_budget.continuation_binding()
    fresh_budget = BudgetMiddleware(
        BudgetState(),
        ledger=FileBudgetLedger(original_budget._ledger._path),
        continuation_owner_identity=owner,
        continuation_resource_identity=resource,
        continuation_snapshot_anchor=anchor,
    )
    before = fresh_budget._ledger.snapshot()
    frontiers, truncated = fresh_control.list_generic_model_input_initial_frontiers_by_source(
        tenant_id=served.TENANT,
        cell_id=served.CELL,
        source_job_id=job_id,
    )
    assert not truncated and len(frontiers) == 1
    (frontier,) = frontiers
    arguments = {
        "store": fresh_store,
        "event_log": fresh_events,
        "control_store": fresh_control,
        "frontier_ref": frontier.frontier_ref,
        "expected_tenant_id": served.TENANT,
        "expected_cell_id": served.CELL,
        "expected_run_id": run_id,
        "expected_source_job_id": job_id,
        "settlement_store": fresh_budget,
    }
    basis, decision = read_generic_model_input_initial_evaluation_history(**arguments)
    selected = basis.initial_observation
    assert selected.subject_kind == "initial_observation"
    assert selected.execution_job_id == job_id and selected.run_id == run_id
    assert basis.observed_admission is decision.observed_admission is False
    assert basis.publication_authority is decision.publication_authority is False
    assert frontier.revision == 1 and frontier.selected_evaluation == selected
    assert fresh_control.get_generic_model_input_use(key=frontier.key, action_job_id=job_id) is None
    execution = parse_generic_cycle_simulation_n5_execution(
        artifacts.load_core_json_artifact(fresh_store, selected.execution_ref)
    )
    assert execution.initial_method_input_purpose == "current_use_method_input_revalidation"
    assert artifacts.artifact_ref_identity_key(execution.current_method_input_bindings_ref) == (
        artifacts.artifact_ref_identity_key(selected.current_method_input_bindings_ref)
    )
    expected = _selected_method_result_expectation(
        fresh_store, input_ref=selected.input_ref, result_ref=selected.result_ref
    )
    result_owner = GenericCycleSimulationAdmissionOwner(profiles=(), store=fresh_store)
    joined, resolved = result_owner.resolve_n5_execution_join_with_result(
        selected.execution_ref, expected=expected
    )
    assert joined.status == "resolved" and resolved is not None, joined.code
    assert joined.execution == execution
    result = resolved.result
    assert result.world_model_record_content_hash == execution.world_model_record_content_hash
    assert resolved.request.world_model_record_ref == result.world_model_record_ref
    wrong_profile = selected.result_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "0" * 64}
    )
    refused, refused_result = result_owner.resolve_n5_execution_join_with_result(
        selected.execution_ref, expected=expected.model_copy(update={"result_ref": wrong_profile})
    )
    assert refused.status == "mismatch" and refused_result is None
    assert refused.code == "generic_n5_execution_cycle_join_mismatch"
    wrong_request = resolved.request.model_copy(update={"seed": resolved.request.seed + 1})
    with pytest.raises(JointSimulationControllerError) as wrong_binding:
        JointSimulationHorizonController().validate_selected_result(
            request=wrong_request, result=result
        )
    assert wrong_binding.value.code == "selected_plan_execution_binding_missing"
    assert str(wrong_binding.value.__cause__) == "result_request_binding_mismatch"
    work = result.physical_work_observations
    assert len(work) == 2  # One baseline and one intervention, one actual replication.
    assert len(before.invocation_reservations) == len(work)
    assert all(
        row.status == "completed" and row.purpose == "standard"
        for row in before.invocation_reservations.values()
    )
    assert basis.comparison_profile == "generic_program_graph_paired_numpy_methods_v4"
    observation = _read_generic_program_graph_observation_wire(
        result.diagnostics["candidate_n5_execution_content_observation"]
    )
    assert type(observation) is GenericProgramGraphContentObservationV4
    comparator = _read_program_graph_paired_comparator(result)
    assert comparator is not None and len(comparator.samples) == 1
    (baseline,) = comparator.samples
    groups = _semantic_program_graph_replications(result)
    assert len(groups) == 2  # Empty actuation and T; individual/joint share T.
    assert len(observation.steps) == 2
    assert sorted(len(step.mechanism_calls) for step in observation.steps) == [0, 1]
    assert all(len(step.calls) == 1 for step in observation.steps)
    (mechanism_call,) = tuple(call for step in observation.steps for call in step.mechanism_calls)
    assert mechanism_call.state_matches_base is True
    assert mechanism_call.state_ref is not None
    before_policy = load_state_snapshot(fresh_store, snapshot_ref=mechanism_call.state_ref)
    # The world-method patch and subsidy meet at the shared merge barrier.
    assert float(before_policy.government_balance) == 10_000_000_000.0

    # Independent coupled-account law: TaxSubsidy credits each actual income
    # by rate*income and debits government by their SUM. The method's flow is
    # the SAME exogenous background in both physical units, never an effect.
    incomes = (2**26, 2**27)
    rate = Fraction(1, 8)
    background_flow = -6_000_000_000
    cost = sum(Fraction(value) * rate for value in incomes)
    expected_baseline = Fraction(10_000_000_000 + background_flow)
    expected_treatment = expected_baseline - cost
    expected_income_mean = Fraction(sum(incomes), len(incomes))
    assert cost == 25_165_824
    assert expected_baseline == 4_000_000_000
    assert expected_treatment == 3_974_834_176
    assert expected_income_mean == 100_663_296
    assert expected_income_mean * (1 + rate) == 113_246_208
    assert baseline.outcomes_by_step == ({"government.balance": float(expected_baseline)},)
    assert execution.request_binding is not None
    treatment_ids = tuple(
        sorted(
            atom.intervention_id for atom in execution.request_binding.request.intervention_atoms
        )
    )
    observed_balances = {}
    for physical, replications in groups.items():
        assert len(replications) == 1
        (admission,) = admit_semantic_horizon_step_chain(
            fresh_store, replications[0].step_result_refs
        )
        source = admission.basis
        assert source is not None and source.actuation_selection_ref is not None
        actuation = resolve_program_graph_actuation(
            fresh_store,
            program_ref=source.program_graph_ref,
            exec_plan_ref=source.exec_plan_ref,
            actuation_selection_ref=source.actuation_selection_ref,
        )
        is_baseline = physical == baseline.physical_spec_ref
        assert actuation.selected_intervention_ids == (() if is_baseline else treatment_ids)
        state = load_state_snapshot(
            fresh_store, snapshot_ref=admission.simulation_result.state_snapshot_ref
        )
        expected_stock = expected_baseline if is_baseline else expected_treatment
        assert float(state.government_balance) == float(expected_stock)
        expected_incomes = np.asarray(
            [float(Fraction(value) * (1 if is_baseline else 1 + rate)) for value in incomes],
            dtype=np.float32,
        )
        np.testing.assert_array_equal(np.asarray(state.agents.income), expected_incomes)
        observed_balances[is_baseline] = float(state.government_balance)
    assert observed_balances[False] - observed_balances[True] == -float(cost)
    for trajectory in result.trajectories:
        assert trajectory.points[0].outcomes["government.balance"] == float(expected_treatment)
        assert trajectory.points[0].effect["government.balance"] == -float(cost)
        assert trajectory.points[0].replication_sampling.effects_standard_error == {
            "government.balance": None
        }

    headers = {
        "Authorization": authorization,
        "X-Tenant-ID": served.TENANT,
    }

    def read_run_details() -> dict[str, Any]:
        response = client.get(f"/api/v1/runs/{core_run_id}", headers=headers)
        assert response.status_code == 200, response.text
        return response.json()["run"]

    surfaced = read_run_details()
    initial_projection = surfaced["model_input_initial_observations"]
    assert initial_projection["source_job_id"] == job_id
    assert initial_projection["core_run_id"] == core_run_id
    assert initial_projection["actual_run_id"] == run_id
    assert initial_projection["inventory_status"] == "complete"
    assert initial_projection["inventory_truncated"] is False
    assert initial_projection["limitation_codes"] == []
    assert len(initial_projection["observations"]) == 1
    (initial_row,) = initial_projection["observations"]
    assert initial_row["execution_job_id"] == job_id
    assert initial_row["actual_run_id"] == selected.run_id
    assert initial_row["source_run_id"] == selected.source_run_id
    assert initial_row["frontier_ref"] == frontier.frontier_ref
    assert initial_row["frontier_revision"] == 1
    for field_name, expected_ref in (
        ("basis_ref", frontier.basis_ref),
        ("decision_ref", frontier.selection_decision_ref),
        ("input_ref", selected.input_ref),
        ("execution_ref", selected.execution_ref),
        ("result_ref", selected.result_ref),
        ("current_method_input_bindings_ref", selected.current_method_input_bindings_ref),
        ("model_input_obligation_set_ref", selected.model_input_obligation_set_ref),
        ("context_job_ref", selected.context_job_ref),
        ("n4_source_ref", selected.n4_source_ref),
        ("profile_ref", selected.profile_ref),
    ):
        assert initial_row[field_name] == expected_ref.model_dump(mode="json")
    assert initial_row["candidate_content_hash"] == selected.candidate_content_hash
    assert initial_row["observation_content_hash"] == selected.observation_content_hash
    assert initial_row["authority_purpose"] == "candidate_evaluation_retention_only"
    assert initial_row["historical_replay_status"] == "reconciled"
    assert initial_row["currentness_status"] == "not_established"
    assert initial_row["observed_admission"] is False
    assert initial_row["publication_authority"] is False
    assert initial_row["limitations"] == list(basis.limitations)
    assert initial_row["closure_residuals"] == list(basis.closure_residuals)

    # Reuse the existing candidate-only N5 result-body consumer: its treated
    # absolute outcome plus paired effect preserve the same numerical witness.
    generic_projection = surfaced["generic_cycle_simulation"]
    surfaced_rows = [
        row
        for row in generic_projection["n5_observations"]
        if row.get("simulation_result_ref") == selected.result_ref.model_dump(mode="json")
    ]
    assert len(surfaced_rows) == 1
    result_body = surfaced_rows[0]["simulation_result_body"]
    assert result_body["selected_outcomes"] == ["government.balance"]
    joint = [row for row in result_body["trajectories"] if row["run_level"] == "joint"]
    assert len(joint) == 1
    point = joint[0]["points"][0]
    assert point["outcomes"]["government.balance"] == float(expected_treatment)
    assert point["effects"]["government.balance"] == -float(cost)
    assert point["outcomes"]["government.balance"] - point["effects"][
        "government.balance"
    ] == float(expected_baseline)
    persisted_request = execution.request_binding.request
    selected_registry_ref = world_model_artifact_views(
        persisted_request.world_model_record
    ).registry_bundle_ref
    registry_content = load_registry_bundle_content(fresh_store, selected_registry_ref)
    (persisted_plan,) = persisted_request.engine_plan
    selected_unit_slots = tuple(
        slot
        for slot in registry_content.slot_registry.slots.values()
        if slot.state_path
        == persisted_plan.variable_map.get("government.balance", "government.balance")
    )
    assert len(selected_unit_slots) == 1
    (selected_unit_slot,) = selected_unit_slots
    assert selected_unit_slot.unit is not None
    assert registry_content.units_registry is not None
    assert selected_unit_slot.unit.unit_id in registry_content.units_registry.units
    assert result_body["outcome_units_status"] == "resolved"
    assert result_body["outcome_units"] == {"government.balance": selected_unit_slot.unit.unit_id}
    assert result_body["outcome_unit_registry_ref"] == selected_registry_ref.model_dump(mode="json")
    with pytest.raises(ValueError, match=r"^generic_initial_history_completion_not_established$"):
        read_generic_model_input_initial_evaluation_history(
            **{**arguments, "expected_tenant_id": "foreign-tenant"}
        )
    bindings = load_input_bindings(fresh_store, selected.current_method_input_bindings_ref)
    manifest = load_resolved_input_binding_manifest(
        fresh_store, bindings.resolved_binding_manifest_ref
    )
    current_set, _ = load_model_input_obligation_set(
        fresh_store, manifest.model_input_obligation_set_ref
    )
    facts = replay_selected_method_input_facts(
        fresh_store,
        input_bindings_ref=selected.current_method_input_bindings_ref,
        expected_invocation=current_set.invocation,
    )
    (record,) = facts.records
    physical = fresh_root._paths(record.npy_value_ref.artifact_id)[0]
    removed = physical.with_suffix(".removed-for-initial-reader-control")
    assert physical.is_file() and not removed.exists()
    physical.replace(removed)
    try:
        with pytest.raises(ValueError):
            read_generic_model_input_initial_evaluation_history(**arguments)
        removed_projection = read_run_details()["model_input_initial_observations"]
        assert removed_projection["inventory_status"] == "limited"
        assert removed_projection["inventory_truncated"] is False
        assert removed_projection["limitation_codes"] == ["initial_observation_history_unavailable"]
        assert removed_projection["observations"] == []
    finally:
        removed.replace(physical)
    assert read_generic_model_input_initial_evaluation_history(**arguments) == (basis, decision)
    restored_projection = read_run_details()["model_input_initial_observations"]
    assert restored_projection["inventory_status"] == "complete"
    assert restored_projection["observations"] == initial_projection["observations"]
    actuation_path = fresh_root._paths(baseline.actuation_selection_ref.artifact_id)[0]
    actuation_removed = actuation_path.with_suffix(".removed-for-paired-reader-control")
    assert actuation_path.is_file() and not actuation_removed.exists()
    actuation_path.replace(actuation_removed)
    try:
        with pytest.raises((ValueError, FileNotFoundError)):
            read_generic_model_input_initial_evaluation_history(**arguments)
        removed_selector_projection = read_run_details()["model_input_initial_observations"]
        assert removed_selector_projection["inventory_status"] == "limited"
        assert removed_selector_projection["limitation_codes"] == [
            "initial_observation_history_unavailable"
        ]
        assert removed_selector_projection["observations"] == []
    finally:
        actuation_removed.replace(actuation_path)
    assert read_generic_model_input_initial_evaluation_history(**arguments) == (basis, decision)
    restored_selector_projection = read_run_details()["model_input_initial_observations"]
    assert restored_selector_projection["inventory_status"] == "complete"
    assert restored_selector_projection["observations"] == initial_projection["observations"]
    assert fresh_budget._ledger.snapshot() == before
    assert attempted == []


@pytest.mark.integration
def test_current_method_paired_initial_n5_and_seed_inside_host(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: ControlledCandidateGateway,
    request: pytest.FixtureRequest,
) -> None:
    """Run one genuine initial Generic N5 and read its candidate-only seed cold."""
    import sys

    node = f"{__file__}::test_current_method_paired_initial_n5_and_seed_inside_host"
    if node not in request.config.invocation_params.args:
        pytest.skip("requires explicit source-recorded host invocation")
    session = vars(sys).get("_polisyos_loaded_host_v1")
    assert type(session) is dict and session["phase"] == "collecting"
    assert session["profile"]["native_capture_scope"] == "actually-loaded-locked-wheel-providers/1"
    _run_current_job_real_method_world(
        tmp_path,
        monkeypatch,
        controlled_candidate_gateway,
        preflight_only=False,
    )
