"""Authenticated singleton ProgramGraph producer and fresh model-input routing read."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    ensure_ir_artifact_store,
    read_core_json_artifact,
)
from polisyos.core.contracts.model_input_requirements import load_model_input_obligation_set
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.ir.trinity import TrinityBundle, load_trinity_bundle_artifact
from polisyos.pdc import gy_content_hash
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.container import RuntimeContainerOverrides
from polisyos.runtime.http.dependencies import build_runtime_api_context
from polisyos.runtime.http.deployment_security import RuntimeDeploymentSecurity
from polisyos.runtime.http.security import build_fixture_identity_claims
from polisyos.runtime.http.services.control import generation_cycle as generation_owner
from polisyos.runtime.http.services.control.generation_cycle import (
    CompiledRecursiveGenerationCycleRun,
)
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteLoop
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.generation_cycle import (
    _GENERATION_CYCLE_MODEL_INPUT_ACQUISITION_SCHEMA_VERSION,
    GenerationCycleRecord,
    GenerationCycleRun,
)
from polisyos.runtime.quality.generation_source import GenerationSourceHandoff
from polisyos.runtime.quality.generic_simulation_admission import (
    GenericCycleSimulationAdmissionOwner,
    GenericCycleSimulationN5ExecutionV4,
    GenericCycleSimulationN5InputV1,
    GenericCycleSimulationN5RequestBindingV2,
    parse_generic_cycle_simulation_n5_execution,
)
from tests._helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker
from tests._helpers.controlled_candidate_profile import (
    ControlledCandidateGateway,
    synthetic_controlled_candidate_provider_profile,
)
from tests._helpers.generic_n4_served_replay import (
    _ORIGINAL_SECOND_CAPTURE_RECORDING_ID,
    _replace_recording_response_payload,
)
from tests._helpers.program_graph_tax_subsidy_input import (
    ProgramGraphTaxSubsidyInputCase,
    prepare_program_graph_tax_subsidy_input_case,
)
from tests._helpers.runtime_http import _DeterministicSpanSupportClient, _valid_intake_for_mode
from tests.integration.runtime_quality.test_generic_n4_child_profile_set_served import (
    controlled_candidate_gateway as _gateway_fixture,
)
from tests.integration.runtime_quality.test_program_graph_model_input_served import (
    _INCOME,
    _fiscal_problem,
    _selected_profile,
    _stock_grounding_source,
    world_fixture,
)
from tests.unit.runtime.quality.test_model_input_requirements import _stock_declaration
from tools.quality.validation.check_layer3_gy_design_generation_contract import _load_recordings

controlled_candidate_gateway = _gateway_fixture


def _configure_stock_provider(
    gateway: ControlledCandidateGateway,
    *,
    problem: DesignProblem,
    trinity: TrinityBundle,
    evidence_root: Path,
) -> str:
    """Serve declared candidate-only stage responses through the real gateway client."""
    recording = next(
        row
        for row in _load_recordings(Path(__file__).resolve().parents[3])
        if row["recording_id"] == _ORIGINAL_SECOND_CAPTURE_RECORDING_ID
    )
    controlled = deepcopy(recording)
    controlled.update(
        {
            "recording_id": "controlled-stock-program-graph",
            "derived_from_recording_id": recording["recording_id"],
            "derived_from_content_hash": recording["recording_content_hash"],
        }
    )
    (intervention,) = trinity.policy_spec.interventions
    stage_inputs = (
        (
            0,
            {
                "draft_id": "controlled-stock-draft",
                "narrative": "Evaluate one bounded income subsidy against the declared world.",
                "interventions": [intervention.model_dump(mode="json")],
                "rationale": "A test of the compiled opening-balance input requirement.",
                "confidence": 0.88,
            },
        ),
        (1, {"findings": [], "confidence_adjustment": 0.0}),
        (8, trinity.model_dump(mode="json")),
        (
            9,
            {
                "verdict": "APPROVE",
                "issues": [],
                "alignment_score": 0.9,
                "completeness_score": 0.9,
                "overall_quality": 0.9,
            },
        ),
    )
    for index, payload in stage_inputs:
        _replace_recording_response_payload(controlled, response_index=index, payload=payload)
    controlled["recording_content_hash"] = gy_content_hash(
        {key: value for key, value in controlled.items() if key != "recording_content_hash"}
    )
    provider = synthetic_controlled_candidate_provider_profile(
        recording, controlled, problem=problem, evidence_root=evidence_root
    )
    gateway.set_fixture(controlled, problem=problem, provider_profile=provider)
    return provider.model_id


def _provision_empty_stock_catalog(root: Path) -> None:
    from polisyos.data_forge.read_api.catalog import build_authority_registry
    from polisyos.runtime.quality.substrate_registry import default_substrate_catalog_paths
    from tests._helpers.acquisition_production import (
        DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
        _sha,
        _write_l5,
        _write_provision,
    )

    baseline = default_substrate_catalog_paths(root).l1_dcat_path
    l5 = _write_l5(root)
    _write_provision(
        root,
        baseline=baseline,
        l5_path=l5,
        baseline_owner_ref="repo://" + baseline.relative_to(root).as_posix(),
    )
    registry = build_authority_registry(
        baseline_content_sha256=_sha(baseline),
        l5_measurement_registry_sha256=_sha(l5),
        entries=(),
    )
    (root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY).write_text(
        registry.model_dump_json(), encoding="utf-8"
    )


@dataclass(frozen=True)
class ServedBlockedGenericSourceCase:
    """One real selected blocked Generic run kept alive for API assertions."""

    client: Any
    app_factory: Callable[[], Any]
    service: Any
    store: Any
    compiled: CompiledRecursiveGenerationCycleRun
    compiled_ref: ArtifactRef
    cycle_run: GenerationCycleRun
    cycle: GenerationCycleRecord
    job: Any
    job_id: str
    control_run_id: str
    core_run_id: str
    cas_root: Path
    runs_root: Path
    root: Path
    claims: Any
    profile: Any
    case: ProgramGraphTaxSubsidyInputCase
    trinity: TrinityBundle
    problem: DesignProblem
    semantic_kernel_entries: list[str]


@contextmanager
def served_blocked_generic_source_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: ControlledCandidateGateway,
    *,
    prepare_case: Callable[..., ProgramGraphTaxSubsidyInputCase] | None = None,
    prepare_catalog: Callable[..., None] | None = None,
    profile_factory: Callable[..., Any] | None = None,
    problem: DesignProblem | None = None,
    before_dispatch: Callable[..., None] | None = None,
    deployment_security: RuntimeDeploymentSecurity | None = None,
    deployment_security_factory: Callable[[], RuntimeDeploymentSecurity] | None = None,
    claims: Any | None = None,
    request_headers: dict[str, str] | None = None,
) -> Iterator[ServedBlockedGenericSourceCase]:
    """Persist and yield a genuine blocked Generic run with its controller client open."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("POLISYOS_RUNTIME_EXECUTION_PROFILE", "development")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", str(tmp_path / "control.sqlite3"))
    monkeypatch.setenv("POLISYOS_CACHE_HOME", str(tmp_path / "runtime-cache"))
    root = tmp_path / "knowledge"
    skg_prior = _stock_grounding_source(root)
    _provision_empty_stock_catalog(root)
    selected_problem = problem
    if selected_problem is None:
        problem_data = _fiscal_problem().model_dump(mode="json")
        problem_data["nl_provenance"]["raw_request"] = (
            "Evaluate one bounded tax subsidy and estimate the FY2026 opening balance in USD. "
            "Do not promote generated candidates."
        )
        selected_problem = DesignProblem.model_validate(problem_data)
    if deployment_security is not None and deployment_security_factory is not None:
        raise ValueError("served_security_bundle_and_factory_are_mutually_exclusive")
    external_security = deployment_security is not None or deployment_security_factory is not None
    if not external_security and (claims is not None or request_headers is not None):
        raise ValueError("served_explicit_identity_requires_external_security")
    if external_security and (claims is None or not request_headers):
        raise ValueError("served_external_security_requires_claims_and_request_headers")
    claims = claims if claims is not None else build_fixture_identity_claims()
    assert claims.tenant_id and claims.cell_id
    cas_root = tmp_path / "cas"
    runs_root = cas_root / "runs"
    runtime_context = build_runtime_api_context(cas_root=cas_root, core_runs_root=runs_root)
    prepare_case_fn = prepare_case or prepare_program_graph_tax_subsidy_input_case
    profile_factory_fn = profile_factory or _selected_profile
    with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
        case = prepare_case_fn(
            tmp_path / "graph",
            opening_balance_usd=None,
            mechanism_start_step=2,
            intervention_notes=("do.target=agents.income",),
            intervention_measurement_expectations={
                "sign": "increase",
                "outcome": [_INCOME],
                "effect_path": ["tax_subsidy", _INCOME, _INCOME],
                "estimand": "average_treatment_effect",
            },
            model_input_port_declaration_builder=_stock_declaration,
            store=runtime_context.store,
            snapshot_id=world_fixture.SNAPSHOT_ID,
        )
        trinity = load_trinity_bundle_artifact(
            ensure_ir_artifact_store(case.store), case.trinity_ref
        )
        if prepare_catalog is not None:
            prepare_catalog(
                store=case.store,
                claims=claims,
                case=case,
                trinity=trinity,
                problem=selected_problem,
                root=root,
            )
        profile = profile_factory_fn(
            case,
            trinity,
            selected_problem,
            tmp_path / "world",
            skg_prior=skg_prior,
        )
    model_id = _configure_stock_provider(
        controlled_candidate_gateway,
        problem=selected_problem,
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

    def app_factory() -> Any:
        selected_security = (
            deployment_security_factory()
            if deployment_security_factory is not None
            else deployment_security
        )
        return create_runtime_api_app(
            cas_root=cas_root,
            core_runs_root=runs_root,
            container_overrides=RuntimeContainerOverrides(runtime_api_context=runtime_context),
            allow_fixture_identity=not external_security,
            deployment_security=selected_security,
            enable_security_middlewares=external_security,
            enable_csrf_protection=False if external_security else None,
            generic_cycle_simulation_profiles=(profile,),
            generic_cycle_simulation_root_profile_id=profile.profile_id,
            repo_root=root,
        )

    app = app_factory()
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
    )

    semantic_kernel_entries: list[str] = []

    def reject_semantic_kernel_entry(_controller: object, *args: object, **kwargs: object) -> None:
        semantic_kernel_entries.append("program_graph")
        raise AssertionError("blocked model-input preflight entered the N5 kernel")

    monkeypatch.setattr(
        JointSimulationHorizonController,
        "_run_semantic_program_graph_horizon",
        reject_semantic_kernel_entry,
    )
    store = FileSystemCAS(cas_root).for_tenant(claims.tenant_id, claims.cell_id)
    with TestClient(app) as client:
        service = app.state._control_service
        stop_embedded_control_worker(service)
        if before_dispatch is not None:
            before_dispatch(
                service=service,
                store=store,
                claims=claims,
                profile=profile,
                case=case,
                trinity=trinity,
                problem=selected_problem,
                root=root,
            )
        response = client.post(
            "/api/v1/control/runs/nl",
            headers={
                "Idempotency-Key": "stock-program-graph-missing-input",
                **(request_headers or {}),
            },
            json={
                "request": selected_problem.nl_provenance.raw_request,
                "llm_model": model_id,
                "max_iterations": 1,
                "run_budget_usd": 5.0,
                "run_budget_scope": "metered_paid_producers_and_bounded_candidate",
                "context": {
                    "evaluation_safety_attempt": _valid_intake_for_mode("simulate_only").model_dump(
                        mode="json"
                    )
                },
            },
        )
        assert response.status_code == 200, response.text
        accepted = response.json()
        assert accepted["status"] == "accepted"
        job_id = accepted["job_id"]
        assert (
            dispatch_one_control_job(
                store=service._control_store,
                handler=service._process_control_job,
                expected_job_id=job_id,
            )
            == job_id
        )
        job = service._control_store.get_job(job_id)
        assert job is not None
        assert job.state == "completed", job.error_message
        assert semantic_kernel_entries == []
        control_run_id = job.run_id
        assert control_run_id is not None
        run_id = job.progress["core_run_id"]
        compiled_ref = ArtifactRef.model_validate(
            job.progress["compiled_recursive_generation_cycle_artifact_ref"]
        )
        assert not service.llm_producer_settlement_store._ledger.snapshot().invocation_reservations
        compiled = CompiledRecursiveGenerationCycleRun.model_validate(
            read_core_json_artifact(store, compiled_ref).value
        )
        (root_node,) = compiled.recursive_run.leaf_nodes
        cycle_run = root_node.cycle_run
        assert cycle_run is not None
        (cycle,) = cycle_run.cycles
        try:
            yield ServedBlockedGenericSourceCase(
                client=client,
                app_factory=app_factory,
                service=service,
                store=store,
                compiled=compiled,
                compiled_ref=compiled_ref,
                cycle_run=cycle_run,
                cycle=cycle,
                job=job,
                job_id=job_id,
                control_run_id=control_run_id,
                core_run_id=run_id,
                cas_root=cas_root,
                runs_root=runs_root,
                root=root,
                claims=claims,
                profile=profile,
                case=case,
                trinity=trinity,
                problem=selected_problem,
                semantic_kernel_entries=semantic_kernel_entries,
            )
        finally:
            case.close()


def _assert_stock_n7_routing_reopens_actual_n4_and_n5_from_fresh_get(
    served: ServedBlockedGenericSourceCase, tmp_path: Path
) -> None:
    """Preserve the stock blocked-run, source-lineage, and removal assertions."""
    from fastapi.testclient import TestClient

    store = served.store
    compiled = served.compiled
    compiled_ref = served.compiled_ref
    cycle_run = served.cycle_run
    cycle = served.cycle
    job_id = served.job_id
    control_run_id = served.control_run_id
    run_id = served.core_run_id
    cas_root = served.cas_root
    runs_root = served.runs_root
    root = served.root
    claims = served.claims
    semantic_kernel_entries = served.semantic_kernel_entries
    assert semantic_kernel_entries == []
    assert compiled.n4_recursive_source_result_status == "generated"
    assert cycle_run.schema_version == _GENERATION_CYCLE_MODEL_INPUT_ACQUISITION_SCHEMA_VERSION
    execution_ref = cycle.simulation.generic_n5_execution_ref
    report_ref = cycle.model_input_routing_report_ref
    acquisition_report_ref = cycle.model_input_acquisition_report_ref
    obligation_set_ref = cycle.simulation.model_input_obligation_set_ref
    assert (
        execution_ref is not None
        and report_ref is not None
        and acquisition_report_ref is not None
        and obligation_set_ref is not None
    )
    assert cycle.simulation.status == "simulation_blocked"
    assert cycle.simulation.simulation_result_ref is None
    root_source_ref = compiled.n4_recursive_source_ref
    leaf_source_ref = cycle.simulation.generic_n4_source_ref
    assert root_source_ref is not None and leaf_source_ref is not None
    root_source = GenerationSourceHandoff.model_validate(
        read_core_json_artifact(store, root_source_ref).value
    )
    leaf_source = GenerationSourceHandoff.model_validate(
        read_core_json_artifact(store, leaf_source_ref).value
    )
    assert root_source.run_id == control_run_id
    assert leaf_source.run_id == cycle_run.run_id
    # The reused organ is persisted under the distinct root and leaf run identities.
    source_identity = {"run_id", "content_hash"}
    assert root_source.model_dump(mode="json", exclude=source_identity) == leaf_source.model_dump(
        mode="json", exclude=source_identity
    )
    execution = parse_generic_cycle_simulation_n5_execution(
        read_core_json_artifact(store, execution_ref).value
    )
    assert type(execution) is GenericCycleSimulationN5ExecutionV4
    assert execution.status == "simulation_blocked"
    assert execution.result_ref is None
    assert execution.n4_source_ref == leaf_source_ref
    assert execution.model_input_obligation_set_ref == obligation_set_ref
    selected_obligation_set, model_input_obligations = load_model_input_obligation_set(
        store, obligation_set_ref
    )
    assert len(model_input_obligations) == len(selected_obligation_set.obligation_refs) == 1
    (obligation,) = model_input_obligations
    (dependency,) = obligation.dependencies
    assert dependency.first_required_step == 2
    assert dependency.node_id == "fixture_subsidy"

    reader_app = create_runtime_api_app(
        cas_root=cas_root, core_runs_root=runs_root, allow_fixture_identity=True, repo_root=root
    )
    with TestClient(reader_app) as reader:
        get = reader.get(f"/api/v1/runs/{run_id}")
        assert get.status_code == 200, get.text
        projection = get.json()["run"]["generic_cycle_simulation"]
        (row,) = projection["n5_observations"]
        route = row["model_input_routing"]
        assert row["n5_owner_join_status"] == "resolved"
        assert route["status"] == "candidate_descriptors_limited"
        assert ArtifactRef.model_validate(route["report_ref"]) == report_ref
        assert ArtifactRef.model_validate(route["obligation_set_ref"]) == obligation_set_ref
        assert route["authority_purpose"] == "candidate_acquisition_routing_only"
        assert route["fetch_status"] == "not_attempted"
        assert route["voi_status"] == "unknown"
        (port,) = route["ports"]
        assert port["disposition"] == "absent"
        assert port["reason_code"] == "model_input_source_descriptor_unresolved"

        fresh_service = reader_app.state._control_service
        with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
            origin = AcquisitionRouteLoop(
                control_store=fresh_service._control_store,
                artifact_store=fresh_service._artifact_store,
                event_log=fresh_service._diagnostic_event_log,
                core_source_resolver=fresh_service.resolve_completed_control_job_core_run_source,
                tenant_id=claims.tenant_id,
                cell_id=claims.cell_id,
            ).resolve_model_input_routing_origin(
                run_id=control_run_id, routing_report_ref=report_ref
            )
        assert origin.source_job_id == job_id
        assert origin.compiled_ref == compiled_ref
        assert origin.n5_execution_ref == execution_ref
        assert origin.routing_report.obligation_set_ref == obligation_set_ref
        assert origin.routing_report.schema_version == "2.0"
        (stored_route,) = origin.routing_report.routes
        assert stored_route.query_envelope is not None
        assert stored_route.query_envelope.rows == ()

        blob, _ = store._paths(report_ref.artifact_id)
        withheld_report = tmp_path / "withheld-routing-report"
        blob.replace(withheld_report)
        try:
            removed = reader.get(f"/api/v1/runs/{run_id}")
            assert removed.status_code == 200, removed.text
            (limited_row,) = removed.json()["run"]["generic_cycle_simulation"]["n5_observations"]
            assert limited_row["n5_owner_join_status"] == "resolved"
            limited_route = limited_row["model_input_routing"]
            assert limited_route["status"] == "not_established"
            assert limited_route.get("report_ref") is None
            assert limited_route.get("obligation_set_ref") is None
            assert limited_route["ports"] == []
        finally:
            withheld_report.replace(blob)

        from polisyos.runtime.quality.acquisition_planner import (
            _n7_verify_configured_candidate_report_cycle,
            load_acquisition_planner_report,
        )
        from polisyos.runtime.quality.cycle_substrate import cycle_job_design_problem_ref

        acquisition_report = load_acquisition_planner_report(store, acquisition_report_ref)
        lineage = acquisition_report.candidate_lineage
        assert lineage is not None
        assert lineage.schema_version == "policyos.runtime.n7_candidate_report_lineage.v2"
        assert lineage.model_input_compilation_ref is not None
        assert (
            lineage.model_input_compilation_ref.kind == "data_requirement.model_input_compilation"
        )
        assert acquisition_report.requirement_basis_binding is None
        configured_source_ref = lineage.port_source_ref

        def verify_configured_source():
            with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
                return _n7_verify_configured_candidate_report_cycle(
                    artifact_store=store,
                    control_store=fresh_service._control_store,
                    report=acquisition_report,
                    report_ref=acquisition_report_ref,
                    generation_run=cycle_run,
                    source_cycle=cycle,
                    tenant_id=claims.tenant_id,
                    cell_id=claims.cell_id,
                    # Generic N5 is scoped to the control job's logical run.
                    # The generation child run is separately bound by the source.
                    run_id=control_run_id,
                    source_job_id=job_id,
                    design_problem_ref=cycle_job_design_problem_ref(leaf_source.problem),
                )

        configured_source = verify_configured_source()
        configured_source_wire = configured_source.model_dump(mode="json")
        assert configured_source.schema_version == (
            "policyos.runtime.n7_configured_candidate_port_source.v3"
        )
        assert configured_source.numerical_execution_status == "unrun"
        assert configured_source.n5_result_ref is None
        assert "n5_result_ref" not in configured_source_wire
        assert configured_source.model_input_obligation_set_ref == obligation_set_ref
        assert configured_source.model_input_obligation_ref in (
            selected_obligation_set.obligation_refs
        )
        assert configured_source.model_input_routing_report_ref == report_ref
        assert configured_source.n4_source_ref == leaf_source_ref
        assert configured_source.context_job_ref == cycle.simulation.generic_context_job_ref
        assert configured_source.n5_input_ref == cycle.simulation.generic_n5_input_ref
        assert configured_source.n5_execution_ref == execution_ref
        assert configured_source.grounding_observation == cycle.grounding.model_dump(mode="json")
        assert configured_source.value_observation == cycle.value_port.model_dump(mode="json")
        assert configured_source.value_observation.get("candidate_n5_l1_routing") is None
        if cycle.grounding.report_ref is None:
            assert configured_source.grounding_digest_payload is None
        else:
            assert configured_source.grounding_digest_payload is not None
            assert gy_content_hash(configured_source.grounding_digest_payload) == (
                cycle.grounding.report_ref
            )
        assert configured_source.source_gap.requirement_schema_version == (
            "policyos.runtime.model_input_obligation_gap.v1"
        )
        assert configured_source.source_gap.metadata["source"] == "model_input_obligation"
        assert configured_source.source_gap.metadata["candidate_binding"] == {
            "candidate_id": configured_source.candidate_id,
            "candidate_content_hash": configured_source.candidate_content_hash,
            "design_problem_ref": configured_source.design_problem_basis_ref,
        }
        assert (
            ArtifactRef.model_validate(
                configured_source.source_gap.metadata["model_input_obligation_set_ref"]
            )
            == obligation_set_ref
        )
        assert (
            ArtifactRef.model_validate(
                configured_source.source_gap.metadata["model_input_obligation_ref"]
            )
            == configured_source.model_input_obligation_ref
        )
        assert (
            ArtifactRef.model_validate(
                configured_source.source_gap.metadata["model_input_routing_report_ref"]
            )
            == report_ref
        )
        assert configured_source.source_gap.metadata["historical_catalog_absence"] == (
            "not_established"
        )
        assert configured_source.source_gap.metadata["source_currentness"] == "not_established"

        source_blob, _ = store._paths(configured_source_ref.artifact_id)
        withheld_source = tmp_path / "withheld-configured-candidate-source"
        source_blob.replace(withheld_source)
        try:
            with pytest.raises((FileNotFoundError, PermissionError, ValueError)):
                verify_configured_source()
        finally:
            withheld_source.replace(source_blob)
        assert verify_configured_source() == configured_source

        for selected_ref, withheld_name in (
            (obligation_set_ref, "withheld-model-input-obligation-set"),
            (configured_source.context_job_ref, "withheld-generic-context-job"),
        ):
            selected_blob, _ = store._paths(selected_ref.artifact_id)
            withheld_parent = tmp_path / withheld_name
            selected_blob.replace(withheld_parent)
            try:
                with pytest.raises((FileNotFoundError, PermissionError, ValueError)):
                    verify_configured_source()
            finally:
                withheld_parent.replace(selected_blob)
            assert verify_configured_source() == configured_source

        route_list_response = reader.get(f"/api/v1/runs/{control_run_id}/acquisition-routes")
        assert route_list_response.status_code == 200, route_list_response.text
        route_list = route_list_response.json()
        assert route_list["run_id"] == control_run_id
        (target_route,) = route_list["routes"]
        assert target_route["schema_version"] == "NativeModelInputTargetProjection@1.0"
        assert target_route["run_id"] == control_run_id
        assert target_route["model_goal_status"] == "inputs_pending"
        assert target_route["reason_codes"] == ["native_derivation_plan_not_selected"]
        assert target_route["action_authority"] == "not_established"
        assert target_route["publication_authority"] is False
        assert target_route["source_currentness"] == "not_established"
        assert ArtifactRef.model_validate(target_route["obligation_set_ref"]) == obligation_set_ref
        assert (
            ArtifactRef.model_validate(target_route["model_input_obligation_ref"])
            == configured_source.model_input_obligation_ref
        )
        assert (
            ArtifactRef.model_validate(target_route["configured_port_source_ref"])
            == configured_source_ref
        )
        assert (
            ArtifactRef.model_validate(target_route["planner_report_ref"]) == acquisition_report_ref
        )
        assert target_route["requirement_gap_id"] == (
            configured_source.source_gap.requirement_gap_id
        )
        assert {
            "cost_basis",
            "replay_pins",
            "replay_address",
            "action_job_id",
            "receipt_ref",
            "decision_request_ref",
            "n5_result_ref",
            "fetch_status",
        }.isdisjoint(target_route)
        target_detail_response = reader.get(
            f"/api/v1/runs/{control_run_id}/acquisition-routes/{target_route['route_id']}"
        )
        assert target_detail_response.status_code == 200, target_detail_response.text
        assert target_detail_response.json() == target_route

    # The canonical writer must refuse a self-consistent request for a different
    # seed even with the same selected compilation, N4, and obligation set.
    request = execution.request_binding.request
    wrong_request = GenericCycleSimulationN5RequestBindingV2.from_request(
        request.model_copy(update={"seed": request.seed + 1})
    )
    input_record = GenericCycleSimulationN5InputV1.model_validate(
        read_core_json_artifact(store, execution.input_ref).value
    )
    owner = GenericCycleSimulationAdmissionOwner(profiles=(), store=store)
    with pytest.raises(
        ValueError, match="generic_cycle_simulation_n5_execution_request_profile_mismatch"
    ):
        owner.persist_n5_execution(
            input_ref=execution.input_ref,
            input_record=input_record,
            result_ref=None,
            request_binding=wrong_request,
            status=execution.status,
            world_model_record_content_hash=execution.world_model_record_content_hash,
            limitation_code=execution.limitation_code,
            model_input_obligation_set_ref=obligation_set_ref,
        )


@pytest.mark.integration
def test_stock_n7_routing_reopens_actual_n4_and_n5_from_fresh_get(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: ControlledCandidateGateway,
) -> None:
    """Persist a real blocked selected run and prove fresh routing/source reads."""
    with served_blocked_generic_source_case(
        tmp_path,
        monkeypatch,
        controlled_candidate_gateway,
    ) as served:
        _assert_stock_n7_routing_reopens_actual_n4_and_n5_from_fresh_get(served, tmp_path)
