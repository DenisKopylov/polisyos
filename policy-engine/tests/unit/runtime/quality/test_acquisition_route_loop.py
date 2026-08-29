from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.pdc import gy_content_hash
from polisyos.runtime.http.services.control.generation_cycle import (
    COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
    CompiledRecursiveGenerationCycleRun,
)
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
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

NOW = datetime(2026, 8, 28, 12, tzinfo=UTC)


def _options(*, kind: str, schema_name: str) -> ArtifactWriteOptions:
    return ArtifactWriteOptions(
        kind=kind,
        media_type="application/json",
        schema=SchemaInfo(name=schema_name, version="1.0"),
    )


async def _compiled() -> CompiledRecursiveGenerationCycleRun:
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
        cycle_controller_factory=lambda _node_ref, _problem: GenerationCycleController(
            generation_port=_CgfGenerationPort(target_world_slots=("administrative_tax_receipts",)),
            value_port=_CostedDataGapValuePort(),
        )
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
async def test_route_closure_rejects_complete_before_terminal_then_ignores_newer_job(
    tmp_path: Path,
) -> None:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    cas = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
    event_log = RuntimeDiagnosticEventLog(store=store, artifact_store=cas)
    compiled = await _compiled()
    compiled_ref = str(
        cas.put_json(
            compiled.model_dump(mode="json"),
            _options(
                kind="runtime.compiled_recursive_generation_cycle",
                schema_name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        ).artifact_id
    )
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
    store.complete_job(
        job_id="job-nl",
        run_id="run-ds15",
        capability_manifest_ref=manifest_ref,
        progress={
            "state": "completed",
            "phase": "natural_language_run",
            "run_id": "run-ds15",
            "compiled_recursive_generation_cycle_ref": compiled_ref,
        },
    )
    loop = AcquisitionRouteLoop(
        control_store=store,
        artifact_store=cas,
        event_log=event_log,
        tenant_id="tenant-a",
        cell_id="cell-a",
    )

    with pytest.raises(AcquisitionRouteClosureError, match="source_terminal_event_missing"):
        loop.resolve_current_route(run_id="run-ds15")

    _append_terminal(
        event_log,
        run_id="run-ds15",
        job_id="job-nl",
        compiled_ref=compiled_ref,
        manifest_ref=manifest_ref,
    )
    store.create_job(job_id="job-acquisition", kind="acquisition", **common)
    store.complete_job(job_id="job-acquisition", run_id="run-ds15")

    closure = loop.resolve_current_route(run_id="run-ds15")

    assert closure.source_job_id == "job-nl"
    assert closure.compiled_ref == compiled_ref
    assert closure.cost_basis_record.missing_distribution == "administrative_tax_receipts"
    assert closure.cost_basis_record.record_content_hash == closure.cost_basis_hash
    assert closure.terminal_event_id == "evt-ds15-nl-terminal"
