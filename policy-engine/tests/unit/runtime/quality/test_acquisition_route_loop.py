from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

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


def test_historical_initial_policy_requires_the_selected_action_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stored policy locator needs the exact durable phase and action job."""
    from types import SimpleNamespace

    from polisyos.runtime.http.services.control.run_lifecycle import (
        AcquisitionRouteLoopAuthoritySink,
    )
    from tests._helpers.runtime_http import _build_control_service
    from tests.unit.runtime.http.test_control_plane_store_evaluation_frontier import _create_job
    from tests.unit.runtime.quality.test_candidate_experiment_terminal_history import (
        _persist_requested_phase,
        _requested_phase,
    )

    service = _build_control_service(tmp_path)
    phase = _requested_phase()
    sink = service.acquisition_route_sink
    monkeypatch.setattr(
        AcquisitionRouteLoopAuthoritySink,
        "_verify_candidate_experiment_live_authority",
        lambda *_: None,
    )
    # This component test exercises the stored SQL/event/profile anchor. PA2
    # history is independently checked in the composed terminal test.
    monkeypatch.setattr(
        AcquisitionRouteLoopAuthoritySink,
        "_verify_candidate_experiment_phase_owner",
        lambda *_args, **_kwargs: None,
    )
    try:
        _create_job(
            service._control_store,
            job_id=phase.job_id,
            kind="acquisition",
            run_id=phase.run_id,
        )
        assert service._control_store.get_job(phase.job_id) is not None
        head = _persist_requested_phase(sink, phase)
        loop = AcquisitionRouteLoop(
            control_store=service._control_store,
            artifact_store=service._artifact_store,
            event_log=service._diagnostic_event_log,
            core_source_resolver=service.resolve_completed_control_job_core_run_source,
            tenant_id=phase.tenant_id,
            cell_id=phase.cell_id,
            action_outcome_reader=sink,
        )
        origin = SimpleNamespace(source_job_id=phase.source_job_id, route_id=phase.route_id)
        monkeypatch.setattr(loop, "_resolve_candidate_experiment_source", lambda **_: origin)

        def historical(policy_ref, job_id):
            return loop.resolve_candidate_experiment_predecessor_origin(
                run_id=phase.run_id,
                predecessor_terminal_ref=None,
                expected_action_generation=1,
                historical_policy_ref=policy_ref,
                historical_action_job_id=job_id,
            )

        assert historical(phase.policy_ref, phase.job_id) is origin
        with pytest.raises(AcquisitionRouteClosureError, match="historical_anchor_missing"):
            historical(phase.policy_ref, "foreign-job")
        alternate = phase.policy_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "1" * 64}
        )
        with pytest.raises(AcquisitionRouteClosureError, match="historical_policy_changed"):
            historical(alternate, phase.job_id)
        with monkeypatch.context() as patch:
            patch.setattr(service._control_store, "get_acquisition_action_head", lambda **_: None)
            with pytest.raises(AcquisitionRouteClosureError, match="historical_policy_changed"):
                historical(phase.policy_ref, phase.job_id)
        assert (
            service._control_store.get_acquisition_action_head(
                tenant_id=phase.tenant_id,
                cell_id=phase.cell_id,
                run_id=phase.run_id,
                source_job_id=phase.source_job_id,
                route_id=phase.route_id,
                action_generation=phase.action_generation,
            )
            == head
        )
    finally:
        service.close()


def _reuse_terminal_payload(outcome: str) -> dict[str, object]:
    from tests.unit.runtime.quality.test_candidate_experiment_route_receipts import (
        _hash,
        _ref,
        _terminal_base,
    )

    payload: dict[str, Any] = {
        **_terminal_base(),
        "schema_version": "AcquisitionCandidateExperimentTerminalReceipt@2.0",
        "receipt_id": "reuse-action-a.terminal",
        "action_generation": 2,
        "job_id": "reuse-action-a",
        "reuse_occurrence_ref": _ref("runtime_quality.candidate_experiment_reuse_occurrence", "a"),
        "terminal_outcome": outcome,
    }
    action_ref = payload["candidate_action_ref"]
    occurrence_ref = payload["reuse_occurrence_ref"]
    owner_refs = [str(action_ref.artifact_id), str(occurrence_ref.artifact_id)]
    if outcome == "candidate_blocked":
        blocker_ref = _ref("runtime_quality.candidate_experiment_reuse_blocker", "b")
        owner_refs.append(str(blocker_ref.artifact_id))
        payload.update(
            {
                "blocker_ref": blocker_ref,
                "blocker_reason": "reuse_candidate_only",
            }
        )
    else:
        from polisyos.runtime.quality.acquisition_evaluation import (
            AcquisitionSelectedEvaluation,
        )

        decision_ref = _ref("runtime_quality.acquisition_evaluation_decision", "c")
        basis_ref = _ref("runtime_quality.acquisition_evaluation_basis", "d")
        execution_ref = _ref("runtime.quality.candidate_simulation_execution", "2")
        owner_refs.append(str(decision_ref.artifact_id))
        payload.update(
            {
                "evaluation_decision_ref": decision_ref,
                "selected_basis_ref": basis_ref,
                "selected_evaluation_witness_ref": execution_ref,
                "selected_evaluation": AcquisitionSelectedEvaluation(
                    candidate_id="candidate-a",
                    candidate_content_hash=_hash("3"),
                    design_problem_ref=_hash("2"),
                    world_model_record_hash=_hash("6"),
                    evaluation_job_id="evaluation-a",
                    evaluation_run_id="run-a",
                    generation_run_id="generation-a",
                    cycle_index=0,
                    n4_source_ref=_ref("runtime.quality.n4_candidate_scenario_source", "3"),
                    context_job_ref=_ref("runtime.quality.cycle_substrate_context_job", "4"),
                    n5_input_ref=_ref("runtime.quality.candidate_simulation_n5_input", "5"),
                    n5_execution_ref=execution_ref,
                    n5_result_ref=_ref("polisyos.runtime.joint_simulation_result", "6"),
                    basis_ref=basis_ref,
                ),
                "current_continuation_ref": _ref(
                    "runtime_quality.candidate_acquisition_retained_continuation", "7"
                ),
            }
        )
    payload["owner_receipt_refs"] = tuple(owner_refs)
    return payload


@pytest.mark.parametrize("outcome", ["candidate_blocked", "candidate_evaluation_retained"])
def test_candidate_experiment_reuse_terminal_v2_selects_exact_occurrence_and_stays_candidate_only(
    outcome: str,
) -> None:
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceiptV2,
        parse_acquisition_route_loop_receipt,
    )

    payload = _reuse_terminal_payload(outcome)
    terminal = parse_acquisition_route_loop_receipt(payload)

    assert type(terminal) is AcquisitionCandidateExperimentTerminalReceiptV2
    assert isinstance(terminal, AcquisitionCandidateExperimentTerminalReceiptV2)
    assert terminal.terminal_outcome == outcome
    assert terminal.reuse_occurrence_ref == payload["reuse_occurrence_ref"]
    assert terminal.reuse_occurrence_ref.kind == (
        "runtime_quality.candidate_experiment_reuse_occurrence"
    )
    assert terminal.reuse_occurrence_ref.manifest_profile_sha256 == "sha256:" + "f" * 64
    assert str(terminal.candidate_action_ref.artifact_id) in terminal.owner_receipt_refs
    assert str(terminal.reuse_occurrence_ref.artifact_id) in terminal.owner_receipt_refs
    assert terminal.observed_data_authority is False
    assert terminal.publication_authority is False
    wire = terminal.model_dump(mode="json")
    assert wire["schema_version"] == "AcquisitionCandidateExperimentTerminalReceipt@2.0"
    assert wire["candidate_action_ref"] == payload["candidate_action_ref"].model_dump(mode="json")


def test_candidate_experiment_terminal_v1_wire_has_no_reuse_extension() -> None:
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceipt,
        parse_acquisition_route_loop_receipt,
    )

    payload = _reuse_terminal_payload("candidate_blocked")
    payload.pop("reuse_occurrence_ref")
    payload["schema_version"] = "AcquisitionCandidateExperimentTerminalReceipt@1.0"
    payload["owner_receipt_refs"] = (
        str(payload["candidate_action_ref"].artifact_id),
        str(payload["blocker_ref"].artifact_id),
    )

    legacy = parse_acquisition_route_loop_receipt(payload)

    assert type(legacy) is AcquisitionCandidateExperimentTerminalReceipt
    wire = legacy.model_dump(mode="json")
    assert wire["schema_version"] == "AcquisitionCandidateExperimentTerminalReceipt@1.0"
    assert "reuse_occurrence_ref" not in wire
    assert AcquisitionCandidateExperimentTerminalReceipt.model_validate(wire) == legacy


@pytest.mark.parametrize(
    "changed_field",
    ["manifest_profile_sha256", "kind"],
)
def test_candidate_experiment_reuse_terminal_v2_rejects_unselected_or_wrong_kind_occurrence(
    changed_field: str,
) -> None:
    from pydantic import ValidationError

    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceiptV2,
    )

    payload = _reuse_terminal_payload("candidate_blocked")
    occurrence_ref = payload["reuse_occurrence_ref"]
    assert isinstance(occurrence_ref, ArtifactRef)
    update = (
        {"manifest_profile_sha256": None}
        if changed_field == "manifest_profile_sha256"
        else {"kind": "runtime_quality.other_artifact"}
    )
    payload["reuse_occurrence_ref"] = occurrence_ref.model_copy(update=update)
    with pytest.raises(ValidationError, match="candidate_experiment_selected_profile_invalid"):
        AcquisitionCandidateExperimentTerminalReceiptV2.model_validate(payload)


def test_candidate_experiment_reuse_terminal_v2_requires_occurrence_owner_and_forbids_reentry() -> (
    None
):
    from pydantic import ValidationError

    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceiptV2,
    )
    from tests.unit.runtime.quality.test_candidate_experiment_route_receipts import _ref

    payload = _reuse_terminal_payload("candidate_blocked")
    payload["owner_receipt_refs"] = (
        str(payload["candidate_action_ref"].artifact_id),
        str(payload["blocker_ref"].artifact_id),
    )
    with pytest.raises(
        ValidationError,
        match="candidate_experiment_terminal_reuse_occurrence_owner_missing",
    ):
        AcquisitionCandidateExperimentTerminalReceiptV2.model_validate(payload)

    payload = _reuse_terminal_payload("candidate_blocked")
    payload["candidate_reentry_ref"] = _ref("runtime_quality.candidate_source_reentry_receipt", "8")
    with pytest.raises(ValidationError):
        AcquisitionCandidateExperimentTerminalReceiptV2.model_validate(payload)

    payload = _reuse_terminal_payload("candidate_blocked")
    payload["terminal_outcome"] = "candidate_reentry_completed"
    with pytest.raises(ValidationError):
        AcquisitionCandidateExperimentTerminalReceiptV2.model_validate(payload)


def test_source_attempt_prefix_skips_v2_reuse_without_reordering_v1_occurrences() -> None:
    from types import SimpleNamespace
    from typing import cast

    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceipt,
        AcquisitionCandidateExperimentTerminalReceiptV2,
        VerifiedCandidateExperimentOrigin,
    )

    legacy_payload = _reuse_terminal_payload("candidate_blocked")
    legacy_payload.pop("reuse_occurrence_ref")
    legacy_payload["schema_version"] = "AcquisitionCandidateExperimentTerminalReceipt@1.0"
    legacy_payload["owner_receipt_refs"] = (
        str(legacy_payload["candidate_action_ref"].artifact_id),
        str(legacy_payload["blocker_ref"].artifact_id),
    )
    first_source = AcquisitionCandidateExperimentTerminalReceipt.model_validate(legacy_payload)
    second_source = first_source.model_copy(update={"receipt_id": "source-b.terminal"})
    reuse = AcquisitionCandidateExperimentTerminalReceiptV2.model_validate(
        _reuse_terminal_payload("candidate_blocked")
    )

    origin = VerifiedCandidateExperimentOrigin(
        schema_version="polisyos.runtime.candidate_experiment_origin.v1",
        tenant_id=first_source.tenant_id,
        cell_id=first_source.cell_id,
        run_id=first_source.run_id,
        source_job_id=first_source.source_job_id,
        source_payload_ref=first_source.source_payload_ref,
        capability_manifest_ref=first_source.capability_manifest_ref,
        request_content_hash=first_source.request_content_hash,
        route_id=first_source.route_id,
        policy_ref=first_source.policy_ref,
        policy_scope=first_source.policy_scope,
        generation_run=cast("Any", SimpleNamespace()),
        source_cycle=cast("Any", SimpleNamespace()),
        design_problem_basis=cast("Any", SimpleNamespace()),
        planner_report=cast("Any", None),
        planner_record=cast("Any", None),
        candidate_terminal_history_chain=cast(
            "Any",
            (
                SimpleNamespace(
                    terminal=first_source, action=SimpleNamespace(attempt_id="source-a")
                ),
                SimpleNamespace(
                    terminal=reuse, action=SimpleNamespace(attempt_id="reuse-no-fetch")
                ),
                SimpleNamespace(
                    terminal=second_source, action=SimpleNamespace(attempt_id="source-b")
                ),
            ),
        ),
    )

    assert origin.source_attempt_prefix == ("source-a", "source-b")


def _reuse_effective_origin(
    terminal: Any,
    *,
    generation_run: object,
    source_cycle: object,
    history_chain: tuple[object, ...] = (),
):
    from polisyos.runtime.quality.acquisition_route_loop import VerifiedCandidateExperimentOrigin

    return VerifiedCandidateExperimentOrigin(
        schema_version="polisyos.runtime.candidate_experiment_origin.v1",
        tenant_id=terminal.tenant_id,
        cell_id=terminal.cell_id,
        run_id=terminal.run_id,
        source_job_id=terminal.source_job_id,
        source_payload_ref=terminal.source_payload_ref,
        capability_manifest_ref=terminal.capability_manifest_ref,
        request_content_hash=terminal.request_content_hash,
        route_id=terminal.route_id,
        policy_ref=terminal.policy_ref,
        policy_scope=terminal.policy_scope,
        generation_run=cast("Any", generation_run),
        source_cycle=cast("Any", source_cycle),
        design_problem_basis=cast("Any", None),
        planner_report=cast("Any", None),
        planner_record=cast("Any", None),
        candidate_terminal_history_chain=cast("Any", history_chain),
    )


@dataclass(frozen=True)
class _EffectiveFixtureCycle:
    cycle_index: int


@dataclass(frozen=True)
class _EffectiveFixtureRun:
    cycles: tuple[_EffectiveFixtureCycle, ...]


@dataclass(frozen=True)
class _EffectiveFixtureAction:
    attempt_id: str
    candidate_source_ref: object


@dataclass(frozen=True)
class _EffectiveFixtureSource:
    source_ref: object


@dataclass(frozen=True)
class _EffectiveFixtureBudget:
    window_id: str


def _reuse_effective_history(
    terminal: Any,
    *,
    origin: Any,
    generation: int,
    action: Any,
    source: Any,
    evaluation: object | None,
    continuation: object | None,
    frontier_before: object | None,
    frontier_after: object | None,
    budget_window: object | None,
    provenance_budget_window: object | None,
    reuse_occurrence: object | None,
):
    from types import SimpleNamespace

    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.quality.acquisition_evaluation import (
        CandidateExperimentTerminalHistory,
    )
    from tests.unit.runtime.quality.test_candidate_experiment_route_receipts import _ref

    return CandidateExperimentTerminalHistory(
        head=cast("Any", SimpleNamespace(action_generation=generation)),
        terminal_ref=cast(
            "ArtifactRef",
            _ref("runtime_quality.acquisition_route_loop_receipt", str(generation)),
        ),
        terminal=terminal,
        origin=origin,
        phase_chain=cast("Any", ()),
        action=action,
        source=source,
        budget_window=cast("Any", budget_window),
        decision=None,
        current_basis=None,
        selected_basis=None,
        evaluation=cast("Any", evaluation),
        reentry=None,
        continuation=cast("Any", continuation),
        frontier_before=cast("Any", frontier_before),
        frontier_after=cast("Any", frontier_after),
        reentry_evaluation=None,
        provenance_budget_window=cast("Any", provenance_budget_window),
        reuse_occurrence=cast("Any", reuse_occurrence),
        reuse_occurrence_ref=(
            terminal.reuse_occurrence_ref if hasattr(terminal, "reuse_occurrence_ref") else None
        ),
    )


def _reuse_action_selection(prior, prior_history, prior_action):
    from polisyos.runtime.quality.candidate_experiment_reuse import (
        CandidateExperimentReuseActionRequest,
        CandidateExperimentReuseActionSelection,
        _candidate_experiment_reuse_job_id,
    )

    selected = prior.selected_evaluation
    assert selected is not None
    request = CandidateExperimentReuseActionRequest(
        route_id=prior.route_id,
        predecessor_terminal_ref=prior_history.terminal_ref,
        predecessor_action_ref=prior.candidate_action_ref,
        source_ref=prior_action.candidate_source_ref,
        n5_input_ref=selected.n5_input_ref,
        n5_execution_ref=selected.n5_execution_ref,
        n5_result_ref=selected.n5_result_ref,
        policy_ref=prior.policy_ref,
        idempotency_key="reuse-request-a",
    )
    job_id = _candidate_experiment_reuse_job_id(
        tenant_id=prior.tenant_id,
        cell_id=prior.cell_id,
        run_id=prior.run_id,
        source_job_id=prior.source_job_id,
        source_payload_ref=prior.source_payload_ref,
        request_content_hash=prior.request_content_hash,
        route_id=prior.route_id,
        predecessor_action_generation=prior.action_generation,
        action_generation=prior.action_generation + 1,
        policy_ref=prior.policy_ref,
        policy_scope=prior.policy_scope,
        request=request,
        authority_provision_content_sha256="sha256:" + "9" * 64,
        catalog_source_selection_basis="legacy_default_candidate_only",
        catalog_source_content_ref=None,
    )
    return CandidateExperimentReuseActionSelection(
        tenant_id=prior.tenant_id,
        cell_id=prior.cell_id,
        run_id=prior.run_id,
        source_job_id=prior.source_job_id,
        source_payload_ref=prior.source_payload_ref,
        request_content_hash=prior.request_content_hash,
        route_id=prior.route_id,
        predecessor_action_generation=prior.action_generation,
        action_generation=prior.action_generation + 1,
        action_job_id=job_id,
        predecessor_terminal_ref=prior_history.terminal_ref,
        predecessor_action_ref=prior.candidate_action_ref,
        source_ref=prior_action.candidate_source_ref,
        n5_input_ref=selected.n5_input_ref,
        n5_execution_ref=selected.n5_execution_ref,
        n5_result_ref=selected.n5_result_ref,
        policy_ref=prior.policy_ref,
        policy_scope=prior.policy_scope,
        authority_provision_content_sha256="sha256:" + "9" * 64,
        catalog_source_selection_basis="legacy_default_candidate_only",
        catalog_source_content_ref=None,
        request=request,
    )


def _reuse_v1_terminal(outcome: str):
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceipt,
    )

    payload = _reuse_terminal_payload(outcome)
    payload.pop("reuse_occurrence_ref")
    payload["schema_version"] = "AcquisitionCandidateExperimentTerminalReceipt@1.0"
    payload["action_generation"] = 1
    payload["job_id"] = "source-action-a"
    payload["receipt_id"] = "source-a.terminal"
    owner_refs = [str(payload["candidate_action_ref"].artifact_id)]
    if outcome == "candidate_evaluation_retained":
        owner_refs.append(str(payload["evaluation_decision_ref"].artifact_id))
    else:
        owner_refs.append(str(payload["blocker_ref"].artifact_id))
    payload["owner_receipt_refs"] = tuple(owner_refs)
    return AcquisitionCandidateExperimentTerminalReceipt.model_validate(payload)


def _reuse_effective_source_case(outcome: str):
    from dataclasses import replace

    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceiptV2,
    )
    from polisyos.runtime.quality.candidate_experiment_reuse_occurrence import (
        CandidateExperimentReuseOccurrence,
    )

    prior = _reuse_v1_terminal("candidate_evaluation_retained")
    current = AcquisitionCandidateExperimentTerminalReceiptV2.model_validate(
        _reuse_terminal_payload(outcome)
    )
    from tests.unit.runtime.quality.test_candidate_experiment_route_receipts import _ref

    selected_source_ref = _ref("runtime.quality.candidate_acquisition_source", "9")
    prior_action = _EffectiveFixtureAction(
        attempt_id="source-attempt", candidate_source_ref=selected_source_ref
    )
    prior_source = _EffectiveFixtureSource(source_ref=selected_source_ref)
    prior_frontier = SimpleNamespace(frontier_ref="selected-frontier")
    physical_budget = _EffectiveFixtureBudget(window_id="last-physical-acquisition")
    generation_run = _EffectiveFixtureRun(cycles=(_EffectiveFixtureCycle(cycle_index=0),))
    source_cycle = generation_run.cycles[0]
    base_origin = _reuse_effective_origin(
        prior,
        generation_run=generation_run,
        source_cycle=source_cycle,
    )
    selected = prior.selected_evaluation
    assert selected is not None and selected.basis_ref is not None
    # The numerical owner returns the raw selection. The terminal adds the
    # selected basis profile without changing the underlying N5 selection.
    numerical_selection = selected.model_copy(update={"basis_ref": None})
    prior_history = _reuse_effective_history(
        prior,
        origin=base_origin,
        generation=1,
        action=prior_action,
        source=prior_source,
        evaluation=SimpleNamespace(selected=numerical_selection),
        continuation=SimpleNamespace(),
        frontier_before=None,
        frontier_after=prior_frontier,
        budget_window=physical_budget,
        provenance_budget_window=None,
        reuse_occurrence=None,
    )
    reuse_selection = _reuse_action_selection(prior, prior_history, prior_action)
    reuse_occurrence = CandidateExperimentReuseOccurrence(
        selection=reuse_selection,
        executing_phase_ref=_ref(
            "runtime_quality.acquisition_candidate_experiment_phase_receipt", "a"
        ),
        control_payload_ref=_ref("runtime.control_job_payload.acquisition", "b"),
        pa2_decision_ref=_ref("runtime_quality.agent_action_authority_decision", "c"),
    )
    current_origin = replace(
        base_origin,
        candidate_terminal_history_chain=(prior_history,),
    )
    current_history = _reuse_effective_history(
        current,
        origin=current_origin,
        generation=2,
        action=prior_action,
        source=prior_source,
        evaluation=(
            SimpleNamespace(selected=numerical_selection)
            if outcome == "candidate_evaluation_retained"
            else None
        ),
        continuation=SimpleNamespace() if outcome == "candidate_evaluation_retained" else None,
        frontier_before=prior_frontier,
        frontier_after=prior_frontier,
        budget_window=None,
        provenance_budget_window=physical_budget,
        reuse_occurrence=reuse_occurrence,
    )
    origin = replace(
        base_origin,
        candidate_terminal_history_chain=(prior_history, current_history),
    )
    return origin, generation_run, source_cycle, current_history, prior_frontier


@pytest.mark.parametrize("outcome", ["candidate_evaluation_retained", "candidate_blocked"])
def test_effective_source_reuse_preserves_exact_predecessor_source_and_frontier(
    outcome: str,
) -> None:
    from polisyos.runtime.quality.acquisition_route_loop import (
        _candidate_experiment_effective_source,
    )

    origin, generation_run, source_cycle, _history, _frontier = _reuse_effective_source_case(
        outcome
    )

    effective_run, effective_cycle = _candidate_experiment_effective_source(origin)

    assert effective_run is generation_run
    assert effective_cycle is source_cycle


def test_effective_source_reuse_blocked_requires_unchanged_selected_frontier() -> None:
    import polisyos.runtime.quality.acquisition_route_loop as route_loop

    origin, _generation_run, _source_cycle, current_history, _frontier = (
        _reuse_effective_source_case("candidate_blocked")
    )
    object.__setattr__(current_history, "frontier_after", None)

    with pytest.raises(
        ValueError, match="candidate_experiment_effective_source_reuse_blocker_mismatch"
    ):
        route_loop._candidate_experiment_effective_source(origin)


def test_effective_source_reuse_rejects_changed_prior_action_profile() -> None:
    import polisyos.runtime.quality.acquisition_route_loop as route_loop
    from polisyos.core.artifacts import ArtifactRef

    origin, _generation_run, _source_cycle, current_history, _frontier = (
        _reuse_effective_source_case("candidate_blocked")
    )
    terminal = current_history.terminal
    changed_action_ref = terminal.candidate_action_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "e" * 64}
    )
    assert isinstance(changed_action_ref, ArtifactRef)
    object.__setattr__(
        current_history,
        "terminal",
        terminal.model_copy(update={"candidate_action_ref": changed_action_ref}),
    )

    with pytest.raises(
        ValueError, match="candidate_experiment_effective_source_reuse_source_mismatch"
    ):
        route_loop._candidate_experiment_effective_source(origin)


def test_effective_source_reuse_rejects_alternate_selected_n5_profile() -> None:
    import polisyos.runtime.quality.acquisition_route_loop as route_loop
    from polisyos.core.artifacts import ArtifactRef

    origin, _generation_run, _source_cycle, current_history, _frontier = (
        _reuse_effective_source_case("candidate_blocked")
    )
    occurrence = current_history.reuse_occurrence
    selection = occurrence.selection
    changed_result_ref = selection.n5_result_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "e" * 64}
    )
    assert isinstance(changed_result_ref, ArtifactRef)
    changed_selection = selection.model_copy(update={"n5_result_ref": changed_result_ref})
    object.__setattr__(
        current_history,
        "reuse_occurrence",
        occurrence.model_copy(update={"selection": changed_selection}),
    )

    with pytest.raises(
        ValueError, match="candidate_experiment_effective_source_reuse_selection_mismatch"
    ):
        route_loop._candidate_experiment_effective_source(origin)


def test_effective_source_reuse_rejects_mismatched_occurrence_profile() -> None:
    import polisyos.runtime.quality.acquisition_route_loop as route_loop
    from polisyos.core.artifacts import ArtifactRef

    origin, _generation_run, _source_cycle, current_history, _frontier = (
        _reuse_effective_source_case("candidate_blocked")
    )
    occurrence_ref = current_history.reuse_occurrence_ref
    changed_ref = occurrence_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "e" * 64}
    )
    assert isinstance(changed_ref, ArtifactRef)
    object.__setattr__(current_history, "reuse_occurrence_ref", changed_ref)

    with pytest.raises(
        ValueError, match="candidate_experiment_effective_source_reuse_occurrence_mismatch"
    ):
        route_loop._candidate_experiment_effective_source(origin)


@pytest.mark.parametrize("changed_basis", ["terminal", "numerical"])
def test_effective_source_reuse_rejects_an_alternate_selected_basis_profile(
    changed_basis: str,
) -> None:
    import polisyos.runtime.quality.acquisition_route_loop as route_loop

    origin, _run, _cycle, current_history, _frontier = _reuse_effective_source_case(
        "candidate_evaluation_retained"
    )
    terminal = current_history.terminal
    selected = terminal.selected_evaluation
    assert selected is not None and selected.basis_ref is not None
    alternate_basis = selected.basis_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "e" * 64}
    )
    if changed_basis == "terminal":
        alternate_terminal = type(terminal).model_validate(
            {
                **terminal.model_dump(mode="python"),
                "selected_basis_ref": alternate_basis,
                "selected_evaluation": selected.model_copy(update={"basis_ref": alternate_basis}),
            }
        )
        object.__setattr__(current_history, "terminal", alternate_terminal)
    else:
        prior = origin.candidate_terminal_history_chain[0]
        alternate_evaluation = SimpleNamespace(
            selected=selected.model_copy(update={"basis_ref": alternate_basis})
        )
        object.__setattr__(prior, "evaluation", alternate_evaluation)
        object.__setattr__(current_history, "evaluation", alternate_evaluation)

    with pytest.raises(
        ValueError, match="candidate_experiment_effective_source_reuse_retention_mismatch"
    ):
        route_loop._candidate_experiment_effective_source(origin)


def test_effective_source_preserves_v1_blocked_all_empty_frontier_behavior() -> None:
    from dataclasses import replace

    from polisyos.runtime.quality.acquisition_route_loop import (
        _candidate_experiment_effective_source,
    )

    terminal = _reuse_v1_terminal("candidate_blocked")
    generation_run = _EffectiveFixtureRun(cycles=(_EffectiveFixtureCycle(cycle_index=0),))
    source_cycle = generation_run.cycles[0]
    origin = _reuse_effective_origin(
        terminal, generation_run=generation_run, source_cycle=source_cycle
    )
    history = _reuse_effective_history(
        terminal,
        origin=origin,
        generation=1,
        action=SimpleNamespace(attempt_id="source-attempt"),
        source=SimpleNamespace(source_ref="selected-source"),
        evaluation=None,
        continuation=None,
        frontier_before=None,
        frontier_after=None,
        budget_window=SimpleNamespace(window_id="physical-acquisition"),
        provenance_budget_window=None,
        reuse_occurrence=None,
    )
    origin = replace(origin, candidate_terminal_history_chain=(history,))

    effective_run, effective_cycle = _candidate_experiment_effective_source(origin)

    assert effective_run is generation_run
    assert effective_cycle is source_cycle
