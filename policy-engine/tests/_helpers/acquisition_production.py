"""Persist a real WDI-resolvable case for served acquisition integration witnesses.

The candidate and missing-data observation are explicitly fixture inputs. The
recursive controller, planner, cost owner, durable control store and route reader
are their production implementations; no service or port object is fabricated.
"""

import socket
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlsplit

import aiohttp
import pytest

from polisyos.core.security.tenant_context import tenant_scope
from polisyos.pdc import gy_content_hash
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionRouteMutationRequest,
    AcquisitionRouteReplayPins,
)
from polisyos.runtime.http.services.control.generation_cycle import (
    COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
    CompiledRecursiveGenerationCycleRun,
)
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteLoop
from polisyos.runtime.quality.agent_action_authority import agent_action_content_hash
from polisyos.runtime.quality.design_axes.coupling_composition import derive_recursive_design_graph
from polisyos.runtime.quality.diagnostic_events import DiagnosticEvent
from polisyos.runtime.quality.generation_cycle import GenerationCycleController
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveCycleBudget,
    RecursiveGenerationCycleController,
)
from tests.unit.runtime.quality import test_generation_cycle as fixtures


def install_fixture_wdi_cost_basis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supply hypothetical owner input; this is not a repository cost allocation.

    The default schedule has no WDI row. Downstream witnesses replace only that
    owner's input data, while its real producer, hash and route revalidation run.
    The one expert hour is a synthetic test quantity, not an estimated WDI cost.
    """
    from polisyos.runtime.quality import acquisition_planner

    monkeypatch.setitem(
        acquisition_planner._ACQUISITION_GAP_BASIS,
        "government.balance",
        {
            "basis_ref": "fixture-only:hypothetical-wdi-cost-input:v1",
            "collection_mode": "Fixture-only WDI acquisition costing input",
            "expert_hours": 1,
            "calendar_days": 1,
        },
    )


class _WDIGap:
    def __call__(self, *, candidate, problem, **kwargs):
        return fixtures.ValuePortObservation(
            status="value_blocked",
            candidate_id=candidate.candidate_id,
            authority_blockers=("acquire_data:value_panel_data_missing",),
            reason="Fixture WDI observations are absent before acquisition.",
            decision_grade="blocked",
            acquisition_requirement=fixtures.l1_variable_availability_requirement_gap(
                candidate_id=candidate.candidate_id,
                candidate_content_hash=candidate.atom.content_hash,
                design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
                availability=fixtures.L1VariableAvailability(
                    variable_id="government.balance",
                    status="unavailable",
                    dataset_count=0,
                    metric_binding_count=0,
                    observation_count=0,
                    coverage_ref="repo://production_data/dataset_catalog.duckdb#variable/government.balance",
                ),
                authority_level=problem.authority_profile.requested_authority_level,
            ),
        )


class _RevisedCycleWdiValuePort:
    def __call__(self, **kwargs):
        if kwargs.get("cycle_index") == 1:
            return _WDIGap()(**kwargs)
        return fixtures.PendingN8ValuePort()(**kwargs)


class _RevisedCycleWdiGrounding:
    """Drive revision on cycle 0, then allow the cycle-1 value gap to request N7."""

    def __call__(
        self,
        *,
        candidate,
        problem,
        cycle_index,
        generation_result=None,
    ):
        grounding_port = (
            fixtures._AlwaysLowGrounding()
            if cycle_index == 0
            else fixtures._StableShadowGrounding()
        )
        return grounding_port(
            candidate=candidate,
            problem=problem,
            cycle_index=cycle_index,
            generation_result=generation_result,
        )


async def persist_wdi_route(
    control,
    *,
    tenant_id: str = "tenant-a",
    cell_id: str = "cell-a",
    run_id: str = "run-acquisition",
    job_id: str = "job-natural-language",
    generation_cycle_repo_root: Path | None = None,
    revised_source: bool = False,
    llm_model_id: str = "fixture-model",
):
    """Install a real compiled fixture case into the supplied app's canonical owners."""
    problem = fixtures._problem("served_wdi_acquisition")
    problem = problem.model_copy(
        update={
            "jurisdiction_time": problem.jurisdiction_time.model_copy(
                update={"region": "UKR", "data_time": "2024"}
            )
        }
    )
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    root_ref = "design-problem://" + problem_ref.removeprefix("sha256:")
    graph = derive_recursive_design_graph(
        design_ref=root_ref,
        module_refs=(),
        parent_child_edges=(),
        rule_version_ref="polisyos.runtime.recursive_generation_cycle.v1",
    )
    if revised_source:
        def cycle_controller_factory(
            _node_ref: str, _problem: object
        ) -> GenerationCycleController:
            return GenerationCycleController(
                generation_port=fixtures._SameCandidateNewBasisGenerator(),
                grounding_port=_RevisedCycleWdiGrounding(),
                value_port=_RevisedCycleWdiValuePort(),
                repo_root=generation_cycle_repo_root,
            )

        cycle_budget = RecursiveCycleBudget(
            max_depth=0, max_nodes=1, min_cycles_per_leaf=2, max_cycles_per_leaf=2
        )
    else:
        def cycle_controller_factory(
            _node_ref: str, _problem: object
        ) -> GenerationCycleController:
            return GenerationCycleController(
                generation_port=fixtures._CgfGenerationPort(
                    target_world_slots=("government.balance",)
                ),
                value_port=_WDIGap(),
                repo_root=generation_cycle_repo_root,
            )

        cycle_budget = RecursiveCycleBudget(
            max_depth=0, max_nodes=1, min_cycles_per_leaf=1, max_cycles_per_leaf=1
        )
    controller = RecursiveGenerationCycleController.for_contract_testing(
        cycle_controller_factory=cycle_controller_factory,
        repo_root=generation_cycle_repo_root,
    )
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        manifest_ref = control._put_json_artifact(
            {"capability": "acquisition_fixture"},
            kind="runtime.capability_manifest",
            schema_name="CapabilityManifest",
        )
        source_payload_ref = control._put_json_artifact(
            {
                "tenant_id": tenant_id,
                "cell_id": cell_id,
                "run_id": run_id,
                "llm_models": [llm_model_id],
            },
            kind="runtime.control_job_payload.natural_language_run",
            schema_name="polisyos.runtime.ControlJobPayload",
        )
    store = control._control_store
    actor = "explicit-fixture"
    execution_scope = {
        "schema_version": "polisyos.runtime.control_execution_scope.v1",
        "status": "established",
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "actor_subject": actor,
        "actor_authenticated": True,
        "actor_roles": ["analyst"],
    }
    store.create_job(
        job_id=job_id,
        kind="natural_language_run",
        run_id=run_id,
        pipeline_id=None,
        requested_execution_profile="dev",
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=manifest_ref,
        payload_ref=source_payload_ref,
        submitted_by=actor,
        creation_event_payload={
            "job_id": job_id,
            "run_id": run_id,
            "job_kind": "natural_language_run",
            "pipeline_id": None,
            "payload_ref": source_payload_ref,
            "submitted_by": actor,
            "requested_execution_profile": "dev",
            "effective_execution_profile": "dev",
            "policy_flags": {},
            "capability_manifest_ref": manifest_ref,
            "execution_scope": execution_scope,
        },
    )
    leased = store.lease_next_job(worker_id="acquisition-fixture-worker")
    if leased is None or leased.job_id != job_id:
        raise AssertionError("acquisition fixture did not lease its source job")
    with store.job_execution_fence(
        job_id=leased.job_id,
        worker_id=str(leased.lease_owner),
        attempt=leased.attempt,
    ):
        admission = store.current_execution_job_admission()
        with control._install_execution_scope(admission.scope):
            core_run_id, core_context = control._start_generation_run_context(
                job=admission.job,
                execution_scope=admission.scope,
            )
            run = await controller.run(
                graph,
                problems_by_node={root_ref: problem},
                budget_state=fixtures._budget(),
                recursive_budget=cycle_budget,
            )
            payload = {
                "schema_version": COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
                "design_problem_ref": problem_ref,
                "design_problem": problem.model_dump(mode="json"),
                "cycle_substrate_context_ref": None,
                "recursive_run": run.model_dump(mode="json", exclude={"leaf_nodes"}),
            }
            compiled = CompiledRecursiveGenerationCycleRun.model_validate(
                {**payload, "content_hash": gy_content_hash(payload)}
            )
            compiled_artifact_ref = control._put_json_artifact_ref(
                compiled.model_dump(mode="json"),
                kind="runtime.compiled_recursive_generation_cycle",
                schema_name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
            )
            core_manifest_ref = control._finish_generation_run_context(
                job=admission.job,
                execution_scope=admission.scope,
                core_run_id=core_run_id,
                context=core_context,
                outputs=[compiled_artifact_ref],
                status="ok",
            )
            compiled_ref = str(compiled_artifact_ref.artifact_id)
            progress = {
                "state": "completed",
                "phase": "natural_language_run",
                "run_id": run_id,
                "compiled_recursive_generation_cycle_ref": compiled_ref,
                "compiled_recursive_generation_cycle_artifact_ref": (
                    compiled_artifact_ref.model_dump(mode="json")
                ),
                **control._core_run_progress_fields(
                    job=admission.job,
                    core_run_id=core_run_id,
                    manifest_ref=core_manifest_ref,
                ),
            }
            store.complete_job(
                job_id=leased.job_id,
                run_id=run_id,
                capability_manifest_ref=manifest_ref,
                progress=progress,
                expected_lease_owner=leased.lease_owner,
                expected_attempt=leased.attempt,
            )
    with control._install_execution_scope(admission.scope):
        control._diagnostic_event_log.append(
            DiagnosticEvent(
                event_id=f"evt-{run_id}-nl-terminal",
                event_source="polisyos.runtime.control",
                event_type="polisyos.runtime.diagnostic.phase_transition.v1",
                event_time=datetime.now(UTC),
                event_subject=f"run/{run_id}/job/{job_id}/phase/job_execution",
                schema_name="polisyos.runtime.quality.diagnostic_event",
                schema_version="1.0",
                trace_id=f"trace-{run_id}",
                span_id=f"span-{run_id}",
                parent_span_id=None,
                run_id=run_id,
                job_id=job_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
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
        closure = AcquisitionRouteLoop(
            control_store=store,
            artifact_store=control._artifact_store,
            event_log=control._diagnostic_event_log,
            core_source_resolver=(
                control.resolve_completed_control_job_core_run_source
            ),
            tenant_id=tenant_id,
            cell_id=cell_id,
        ).resolve_current_route(run_id=run_id)
        request = AcquisitionRouteMutationRequest(
            route_projection_hash=closure.route_id,
            planner_report_hash=agent_action_content_hash(closure.planner_report),
            replay_pins=AcquisitionRouteReplayPins(
                source_job_id=closure.source_job_id,
                compiled_ref=closure.compiled_ref,
                compiled_content_hash=closure.compiled_content_hash,
                terminal_event_id=closure.terminal_event_id,
                design_problem_ref=closure.design_problem_ref,
                cost_basis_hash=closure.cost_basis_hash,
            ),
            idempotency_key="served-acquisition-fixture",
        )
        return closure, request


def intercepted_wdi_transport(
    monkeypatch: pytest.MonkeyPatch,
    *,
    allow_loopback: bool = False,
) -> list[tuple[str, str, dict[str, str]]]:
    """Intercept external HTTP bytes while executing the real WDI/Fabric owners."""
    from tests.unit.runtime.quality.test_live_acquisition_executor import (
        _normalized_rows,
        _raw_body,
    )

    original_request = aiohttp.ClientSession._request
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    loopback_hosts = {"127.0.0.1", "::1", "localhost"}
    transport_calls: list[tuple[str, str, dict[str, str]]] = []

    class _InterceptedResponse:
        status = 200
        headers: ClassVar[dict[str, str]] = {"content-type": "application/json"}

        def __init__(self, body: bytes):
            self.body = body

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            del args

        async def read(self) -> bytes:
            return self.body

        def release(self) -> None:
            return None

        async def wait_for_close(self) -> None:
            return None

        def close(self) -> None:
            return None

    async def _intercept_request(_session: object, method: str, url: object, **kwargs: object):
        if allow_loopback and urlsplit(str(url)).hostname in loopback_hosts:
            return await original_request(_session, method, url, **kwargs)
        params = kwargs.get("params")
        assert isinstance(params, Mapping)
        normalized = {str(key): str(value) for key, value in params.items()}
        transport_calls.append((method, str(url), normalized))
        bounds = normalized["date"].split(":")
        start_year, end_year = int(bounds[0]), int(bounds[-1])
        rows = [row for row in _normalized_rows() if start_year <= row["year"] <= end_year]
        return _InterceptedResponse(_raw_body(rows))

    def _connect(sock, address):
        if allow_loopback and isinstance(address, tuple) and address[0] in loopback_hosts:
            return original_connect(sock, address)
        pytest.fail("intercepted integration escaped to a real network socket")

    def _connect_ex(sock, address):
        if allow_loopback and isinstance(address, tuple) and address[0] in loopback_hosts:
            return original_connect_ex(sock, address)
        pytest.fail("intercepted integration escaped to a real network socket")

    monkeypatch.setattr(aiohttp.ClientSession, "_request", _intercept_request)
    monkeypatch.setattr(socket.socket, "connect", _connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _connect_ex)
    return transport_calls
