from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

import polisyos.runtime.quality.acquisition_route_loop as acquisition_route_loop
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.run.context import RunContext
from polisyos.pdc import gy_content_hash
from polisyos.runtime.http.services.adapters.core_run import (
    TerminalCoreRunSource,
    derive_control_job_core_run_id,
    load_completed_control_job_core_run_source,
)
from polisyos.runtime.http.services.control.generation_cycle import (
    COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
    CompiledRecursiveGenerationCycleRun,
)
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobRecord,
    ControlPlaneStore,
)
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionPlannerReport,
    persist_acquisition_planner_report,
    validate_persisted_acquisition_planner_report,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionRouteClosureError,
    AcquisitionRouteLoop,
)
from polisyos.runtime.quality.design_axes.coupling_composition import (
    derive_recursive_design_graph,
)
from polisyos.runtime.quality.diagnostic_events import DiagnosticEvent
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.generation_cycle import GenerationCycleController
from polisyos.runtime.quality.model_input_routing import (
    MODEL_INPUT_ROUTING_REPORT_KIND,
    MODEL_INPUT_ROUTING_REPORT_SCHEMA_NAME,
)
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveCycleBudget,
    RecursiveGenerationCycleController,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from tests.unit.runtime.quality.test_generation_cycle import (
    _CgfGenerationPort,
    _CostedDataGapValuePort,
    _problem,
)

pytest_plugins = ("tests.unit.runtime.quality.test_generation_cycle",)

NOW = datetime(2026, 8, 28, 12, tzinfo=UTC)


def _options(*, kind: str, schema_name: str) -> ArtifactWriteOptions:
    return ArtifactWriteOptions(
        kind=kind,
        media_type="application/json",
        schema=SchemaInfo(name=schema_name, version="1.0"),
    )


def test_source_planner_selector_accepts_only_one_generic_scenario_join() -> None:
    """Resolve the existing fallback join while retaining its refusal controls."""
    from polisyos.runtime.quality import generation_cycle
    from polisyos.runtime.quality.acquisition_planner import (
        l1_variable_availability_requirement_gap,
        plan_evidence_acquisition,
    )
    from polisyos.runtime.quality.data_state_substrate import L1VariableAvailability
    from tests.unit.runtime.quality.test_generation_cycle import _n7_data_requirement_spec

    source = l1_variable_availability_requirement_gap(
        candidate_id="candidate_generic_route",
        candidate_content_hash="sha256:" + "1" * 64,
        design_problem_ref="sha256:" + "2" * 64,
        availability=L1VariableAvailability(
            variable_id="global.gdp",
            status="unavailable",
            dataset_count=0,
            metric_binding_count=0,
            observation_count=0,
            coverage_ref="fixture://unavailable/global.gdp",
        ),
        authority_level="research",
    )
    matching_spec = _n7_data_requirement_spec().model_copy(
        update={
            "requirement_id": "data-requirement:annual-gdp:global.gdp",
            "claim_id": "claim:annual-gdp",
            "required_data_families": ("global.gdp",),
        }
    )
    other_spec = _n7_data_requirement_spec().model_copy(
        update={
            "requirement_id": "data-requirement:annual-gdp:construct",
            "claim_id": "claim:annual-gdp:construct",
            "required_data_families": ("economic.gdp",),
        }
    )
    compiler_gaps, refusal = generation_cycle._n7_unmarked_current_compiler_gaps(
        source_gap=source,
        specs=(matching_spec, other_spec),
        capability_resolutions=None,
    )
    assert refusal is None
    report = plan_evidence_acquisition(
        run_id="n7-cycle:annual-gdp:0",
        gaps=tuple(gap.to_acquisition_gap() for gap in compiler_gaps),
        generated_at=NOW,
    )
    assert len(report.acquisition_records) == 2
    (fallback_record,) = tuple(
        record
        for record in report.acquisition_records
        if source.requirement_gap_id in record.scenario_requirement_refs
    )
    assert fallback_record.requirement_gap_ref != source.requirement_gap_id
    assert generation_cycle._n7_generic_fallback_source_record_matches(source, fallback_record)
    assert acquisition_route_loop._select_source_planner_record(report, source) == fallback_record

    def with_replacement(replacement):
        return report.model_copy(
            update={
                "acquisition_records": tuple(
                    replacement if record is fallback_record else record
                    for record in report.acquisition_records
                )
            }
        )

    invalid_records = (
        fallback_record.model_copy(update={"requirement_family": "policy_requirement"}),
        fallback_record.model_copy(
            update={
                "scenario_requirement_refs": tuple(
                    ref for ref in fallback_record.scenario_requirement_refs if ref != "global.gdp"
                )
            }
        ),
        fallback_record.model_copy(update={"compiled_requirement_ref": None}),
        fallback_record.model_copy(update={"compiled_requirement_ref": "data-requirement:unbound"}),
        fallback_record.model_copy(
            update={
                "missing_requirement_fields": tuple(
                    field
                    for field in fallback_record.missing_requirement_fields
                    if field != "required_data_family:global.gdp"
                )
            }
        ),
    )
    for invalid in invalid_records:
        assert not generation_cycle._n7_generic_fallback_source_record_matches(source, invalid)
        with pytest.raises(AcquisitionRouteClosureError, match="costed_route_not_unique"):
            acquisition_route_loop._select_source_planner_record(with_replacement(invalid), source)

    malformed_duplicates = (invalid_records[0], invalid_records[2], invalid_records[-1])
    for malformed in malformed_duplicates:
        duplicate_malformed = malformed.model_copy(
            update={"acquisition_id": malformed.acquisition_id + ":malformed-duplicate"}
        )
        assert source.requirement_gap_id in duplicate_malformed.scenario_requirement_refs
        ambiguous_malformed_report = report.model_copy(
            update={"acquisition_records": (*report.acquisition_records, duplicate_malformed)}
        )
        with pytest.raises(AcquisitionRouteClosureError, match="costed_route_not_unique"):
            acquisition_route_loop._select_source_planner_record(ambiguous_malformed_report, source)

    foreign_source = l1_variable_availability_requirement_gap(
        candidate_id="candidate_foreign_route",
        candidate_content_hash="sha256:" + "3" * 64,
        design_problem_ref="sha256:" + "4" * 64,
        availability=L1VariableAvailability(
            variable_id="global.gdp",
            status="unavailable",
            dataset_count=0,
            metric_binding_count=0,
            observation_count=0,
            coverage_ref="fixture://foreign/global.gdp",
        ),
        authority_level="research",
    )
    assert not generation_cycle._n7_generic_fallback_source_record_matches(
        foreign_source, fallback_record
    )
    with pytest.raises(AcquisitionRouteClosureError, match="costed_route_not_unique"):
        acquisition_route_loop._select_source_planner_record(report, foreign_source)

    duplicate = fallback_record.model_copy(
        update={"acquisition_id": fallback_record.acquisition_id + ":duplicate"}
    )
    duplicate_report = report.model_copy(
        update={"acquisition_records": (*report.acquisition_records, duplicate)}
    )
    with pytest.raises(AcquisitionRouteClosureError, match="costed_route_not_unique"):
        acquisition_route_loop._select_source_planner_record(duplicate_report, source)

    joined = fallback_record.model_copy(
        update={
            "requirement_gap_ref": source.requirement_gap_id,
            "requirement_schema_version": source.requirement_schema_version,
            "gap_type": source.gap_type,
            "scenario_requirement_refs": tuple(
                dict.fromkeys(
                    (*fallback_record.scenario_requirement_refs, source.compiled_requirement_ref)
                )
            ),
        }
    )
    joined_duplicate = joined.model_copy(
        update={"acquisition_id": joined.acquisition_id + ":duplicate"}
    )
    ambiguous_join_report = report.model_copy(
        update={
            "acquisition_records": (
                joined,
                joined_duplicate,
                *(record for record in report.acquisition_records if record is not fallback_record),
            )
        }
    )
    with pytest.raises(AcquisitionRouteClosureError, match="costed_route_not_unique"):
        acquisition_route_loop._select_source_planner_record(ambiguous_join_report, source)

    with pytest.raises(AcquisitionRouteClosureError, match="costed_route_not_unique"):
        acquisition_route_loop._select_source_planner_record(report, None)
    single_record_report = report.model_copy(update={"acquisition_records": (fallback_record,)})
    assert acquisition_route_loop._select_source_planner_record(single_record_report, None) == (
        fallback_record
    )


async def _compiled(
    *, cas: FileSystemCAS, source_root: Path, catalog_source: object
) -> CompiledRecursiveGenerationCycleRun:
    problem = _problem("ds15_costed_closure")
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    root_ref = f"design-problem://{problem_ref.removeprefix('sha256:')}"
    graph = derive_recursive_design_graph(
        design_ref=root_ref,
        module_refs=(),
        parent_child_edges=(),
        rule_version_ref="polisyos.runtime.recursive_generation_cycle.v1",
    )
    recursive = RecursiveGenerationCycleController.for_contract_testing(
        repo_root=source_root,
        artifact_store=cas,
        cycle_controller_factory=lambda _node_ref, _problem: GenerationCycleController(
            generation_port=_CgfGenerationPort(target_world_slots=("administrative_tax_receipts",)),
            value_port=_CostedDataGapValuePort(),
            authority_scope="contract_testing",
            artifact_store=cas,
            repo_root=source_root,
            catalog_serving_source=catalog_source,
        ),
    )
    recursive_run = await recursive.run(
        graph,
        problems_by_node={root_ref: problem},
        budget_state=BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}),
        recursive_budget=RecursiveCycleBudget(
            max_depth=0,
            max_nodes=1,
            min_cycles_per_leaf=1,
            max_cycles_per_leaf=1,
        ),
    )
    payload = {
        "schema_version": COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
        "design_problem_ref": problem_ref,
        "design_problem": problem.model_dump(mode="json"),
        "cycle_substrate_context_ref": None,
        "recursive_run": recursive_run.model_dump(mode="json", exclude={"leaf_nodes"}),
    }
    return CompiledRecursiveGenerationCycleRun.model_validate(
        {**payload, "content_hash": gy_content_hash(payload)}
    )


def test_route_consumer_refuses_legacy_plan_without_persisted_compiler_basis(
    tmp_path: Path,
) -> None:
    """A persisted legacy plan cannot authorize a new protected route."""

    cas = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
    report = AcquisitionPlannerReport(
        run_id="run-legacy-plan",
        generated_at=NOW,
        acquisition_records=(),
        status="blocked",
        summary={},
        authority_boundary={},
    )
    ref = persist_acquisition_planner_report(cas, report)

    issues = validate_persisted_acquisition_planner_report(
        cas,
        ref,
        report,
        expected_scenario_id="scenario-legacy",
        expected_compiled_requirement_ref="data-requirement:legacy",
    )

    assert "acquisition_requirement_basis_not_established" in {issue["code"] for issue in issues}
    assert "acquisition_planner_report_context_binding_missing" in {
        issue["code"] for issue in issues
    }


def _append_terminal(
    event_log: RuntimeDiagnosticEventLog,
    *,
    run_id: str,
    job_id: str,
    compiled_ref: str,
    manifest_ref: str,
) -> None:
    event_log.append(
        DiagnosticEvent(
            event_id="evt-ds15-nl-terminal",
            event_source="polisyos.runtime.control",
            event_type="polisyos.runtime.diagnostic.phase_transition.v1",
            event_time=NOW,
            event_subject=f"run/{run_id}/job/{job_id}/phase/job_execution",
            schema_name="polisyos.runtime.quality.diagnostic_event",
            schema_version="1.0",
            trace_id="trace-ds15",
            span_id="span-ds15",
            parent_span_id=None,
            run_id=run_id,
            job_id=job_id,
            tenant_id="tenant-a",
            cell_id="cell-a",
            producer_component="polisyos.runtime.control",
            producer_version="test",
            execution_profile="governed",
            phase="job_execution",
            state_before="running",
            state_after="completed",
            payload_ref=None,
            artifact_refs=(manifest_ref, compiled_ref),
            input_refs=(),
            blocking_status=None,
            redaction_policy_ref=None,
            duplicate_of=None,
            dedupe_key=None,
        ),
        payload={
            "job_kind": "natural_language_run",
            "capability_manifest_ref": manifest_ref,
            "compiled_recursive_generation_cycle_ref": compiled_ref,
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unsupported_schema",
    [False, True],
    ids=("supported-v1", "persisted-v5"),
)
async def test_route_closure_rejects_complete_before_terminal_then_ignores_newer_job(
    tmp_path: Path,
    unsupported_schema: bool,
    n7_complete_catalog_source: tuple[Path, object],
) -> None:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    cas = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
    event_log = RuntimeDiagnosticEventLog(store=store, artifact_store=cas)
    source_root, catalog_source = n7_complete_catalog_source
    compiled = await _compiled(cas=cas, source_root=source_root, catalog_source=catalog_source)
    produced_cycles = [
        cycle
        for leaf in compiled.recursive_run.leaf_nodes
        if leaf.cycle_run is not None
        for cycle in leaf.cycle_run.cycles
    ]
    if not unsupported_schema:
        costed = [cycle for cycle in produced_cycles if cycle.acquisition_cost_basis_record]
        assert len(costed) == 1
        assert costed[0].counterexample.diagnostic.code == (
            "n6.acquisition.n7_execution_scope_not_established"
        )
    compiled_payload = compiled.model_dump(mode="json")
    if unsupported_schema:
        compiled_payload["schema_version"] = (
            "policyos.runtime.http.compiled_recursive_generation_cycle.v5"
        )
        compiled_payload["content_hash"] = gy_content_hash(
            {key: value for key, value in compiled_payload.items() if key != "content_hash"}
        )
    compiled_artifact_ref = cas.put_json(
        compiled_payload,
        _options(
            kind="runtime.compiled_recursive_generation_cycle",
            schema_name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    compiled_ref = str(compiled_artifact_ref.artifact_id)
    manifest_ref = str(
        cas.put_json(
            {"capability": "ds15"},
            _options(kind="runtime.capability_manifest", schema_name="CapabilityManifest"),
        ).artifact_id
    )
    payload_ref = str(
        cas.put_json(
            {"tenant_id": "tenant-a", "cell_id": "cell-a", "run_id": "run-ds15"},
            _options(
                kind="runtime.control_job_payload.natural_language_run",
                schema_name="polisyos.runtime.ControlJobPayload",
            ),
        ).artifact_id
    )
    common = {
        "run_id": "run-ds15",
        "pipeline_id": None,
        "requested_execution_profile": "governed",
        "effective_execution_profile": "governed",
        "policy_flags": {},
        "capability_manifest_ref": manifest_ref,
        "payload_ref": payload_ref,
        "submitted_by": "tester",
    }
    store.create_job(job_id="job-nl", kind="natural_language_run", **common)
    leased = store.lease_next_job(worker_id="route-fixture-worker")
    assert leased is not None and leased.job_id == "job-nl"
    core_runs_root = tmp_path / "core-runs"
    core_run_id = derive_control_job_core_run_id(
        job_id=leased.job_id,
        control_run_id="run-ds15",
        attempt=leased.attempt,
    )
    registry_ref = cas.put_json(
        {"registry": {}},
        ArtifactWriteOptions(kind="core.registry.bundle", media_type="application/json"),
    )
    core_context = RunContext.start(
        store=cas,
        registry_bundle=registry_ref,
        run_id=core_run_id,
        run_dir=core_runs_root / core_run_id,
        tenant_id="tenant-a",
        cell_id="cell-a",
    )
    core_context.run_manifest.control_job_id = leased.job_id
    core_context.add_output(compiled_artifact_ref)
    core_manifest_ref = core_context.finalize(status="ok")
    store.complete_job(
        job_id="job-nl",
        run_id="run-ds15",
        capability_manifest_ref=manifest_ref,
        progress={
            "state": "completed",
            "phase": "natural_language_run",
            "run_id": "run-ds15",
            "compiled_recursive_generation_cycle_ref": compiled_ref,
            "compiled_recursive_generation_cycle_artifact_ref": (
                compiled_artifact_ref.model_dump(mode="json")
            ),
            "core_run_id": core_run_id,
            "core_run_attempt": leased.attempt,
            "core_manifest_artifact_ref": core_manifest_ref.model_dump(mode="json"),
            "manifest_ref": str(core_manifest_ref.artifact_id),
        },
        expected_lease_owner=leased.lease_owner,
        expected_attempt=leased.attempt,
    )

    def resolve_core_source(
        job: ControlJobRecord,
        *,
        expected_control_run_id: str,
        tenant_id: str,
        cell_id: str,
    ) -> TerminalCoreRunSource:
        return load_completed_control_job_core_run_source(
            store=cas,
            core_runs_root=core_runs_root,
            job=job,
            expected_control_run_id=expected_control_run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )

    loop = AcquisitionRouteLoop(
        control_store=store,
        artifact_store=cas,
        event_log=event_log,
        core_source_resolver=resolve_core_source,
        tenant_id="tenant-a",
        cell_id="cell-a",
    )
    unselected_report_ref = cas.put_json(
        {"purpose": "unselected report with no source job output binding"},
        _options(
            kind=MODEL_INPUT_ROUTING_REPORT_KIND,
            schema_name=MODEL_INPUT_ROUTING_REPORT_SCHEMA_NAME,
        ),
        return_selected_profile=True,
    )

    with pytest.raises(AcquisitionRouteClosureError, match="source_terminal_event_missing"):
        loop.resolve_current_route(run_id="run-ds15")
    with pytest.raises(AcquisitionRouteClosureError, match="source_terminal_event_missing"):
        loop.resolve_model_input_routing_origin(
            run_id="run-ds15", routing_report_ref=unselected_report_ref
        )

    _append_terminal(
        event_log,
        run_id="run-ds15",
        job_id="job-nl",
        compiled_ref=compiled_ref,
        manifest_ref=manifest_ref,
    )
    store.create_job(job_id="job-acquisition", kind="acquisition", **common)
    store.complete_job(job_id="job-acquisition", run_id="run-ds15")

    if unsupported_schema:
        with pytest.raises(AcquisitionRouteClosureError) as exc_info:
            loop.resolve_current_route(run_id="run-ds15")
        assert exc_info.value.code == "compiled_run_invalid"
        return

    closure = loop.resolve_current_route(run_id="run-ds15")

    assert closure.source_job_id == "job-nl"
    assert closure.compiled_ref == compiled_ref
    assert closure.cost_basis_record.missing_distribution == "administrative_tax_receipts"
    assert closure.cost_basis_record.record_content_hash == closure.cost_basis_hash
    assert closure.terminal_event_id == "evt-ds15-nl-terminal"
    with pytest.raises(
        AcquisitionRouteClosureError, match="model_input_source_report_not_selected"
    ):
        loop.resolve_model_input_routing_origin(
            run_id="run-ds15", routing_report_ref=unselected_report_ref
        )


def test_candidate_experiment_policy_lookup_refusal_preserves_cause_and_issues_no_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Known configured-policy lookup failures close without issuing an action."""
    from types import SimpleNamespace

    from polisyos.runtime.quality import acquisition_unpriced_candidate_policy as policy_owner
    from tests._helpers.runtime_http import _build_control_service

    service = _build_control_service(tmp_path)
    run_id = "candidate-run"
    source_job_id = "candidate-source-job"
    route = AcquisitionRouteLoop(
        control_store=service._control_store,
        artifact_store=service._artifact_store,
        event_log=service._diagnostic_event_log,
        core_source_resolver=service.resolve_completed_control_job_core_run_source,
        tenant_id="tenant-a",
        cell_id="cell-a",
    )
    origin = SimpleNamespace(
        source_cycle=SimpleNamespace(
            voi_decision=SimpleNamespace(
                scheduler_action="reject", scheduler_reason="roi_below_threshold"
            ),
            selected_candidate_ref="candidate-a",
            acquisition_routing_report_ref=object(),
        ),
        report=SimpleNamespace(
            requirement_basis_binding=object(),
            candidate_lineage=SimpleNamespace(port_source_ref=object()),
        ),
        configured_port_source=SimpleNamespace(design_problem_basis_ref=object()),
        planner_record=SimpleNamespace(compiled_requirement_ref="compiled-requirement-a"),
        job=SimpleNamespace(job_id=source_job_id),
    )
    monkeypatch.setattr(route, "_resolve_verified_origin", lambda **_kwargs: origin)
    events_before = service._diagnostic_event_log.list_events(
        run_id=run_id, job_id=source_job_id, limit=500
    )
    heads_before = service._control_store.list_acquisition_action_heads_for_source(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id=run_id,
        source_job_id=source_job_id,
    )

    failures = (
        FileNotFoundError("policy blob is missing"),
        RuntimeError("policy inventory unavailable"),
        TypeError("policy binding is malformed"),
        ValueError("policy selection is invalid"),
    )
    failure: BaseException | None = None

    def fail_lookup(**_kwargs: object) -> object:
        assert failure is not None
        raise failure

    try:
        for failure in failures:
            with monkeypatch.context() as patch:
                patch.setattr(
                    policy_owner,
                    "list_current_candidate_unpriced_policy_bindings",
                    fail_lookup,
                )
                with pytest.raises(AcquisitionRouteClosureError) as refusal:
                    route.resolve_candidate_experiment_origin(run_id=run_id)
            assert refusal.value.code == "candidate_experiment_policy_binding_unavailable"
            assert refusal.value.__cause__ is failure

            assert (
                service._diagnostic_event_log.list_events(
                    run_id=run_id, job_id=source_job_id, limit=500
                )
                == events_before
            )
            assert (
                service._control_store.list_acquisition_action_heads_for_source(
                    tenant_id="tenant-a",
                    cell_id="cell-a",
                    run_id=run_id,
                    source_job_id=source_job_id,
                )
                == heads_before
            )

        unexpected = KeyboardInterrupt("unexpected control-flow exception")
        failure = unexpected

        with monkeypatch.context() as patch:
            patch.setattr(
                policy_owner,
                "list_current_candidate_unpriced_policy_bindings",
                fail_lookup,
            )
            with pytest.raises(KeyboardInterrupt) as propagated:
                route.resolve_candidate_experiment_origin(run_id=run_id)
        assert propagated.value is unexpected
    finally:
        service.close()
