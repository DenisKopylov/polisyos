from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from polisyos.core import artifacts
from polisyos.core.canon import CanonSpec
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.mutation_policy import RuntimeIdempotencyStore
from polisyos.runtime.http.services import (
    acquisition_action_service as action_service_module,
)
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionActionServiceError,
    AcquisitionExecutionResponse,
    AcquisitionRouteMutationRequest,
    CandidateExperimentCurrentActionProjection,
    CandidateExperimentReuseActionExecutionRequest,
    CandidateExperimentRouteExecutionRequest,
    CandidateExperimentRouteMutationRequest,
    CandidateExperimentRouteReplayPins,
)
from polisyos.runtime.http.services.control_plane_store import (
    AcquisitionActionHeadRecord,
    ControlJobExecutionScope,
)
from polisyos.runtime.quality.acquisition_evaluation import AcquisitionSelectedEvaluation
from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
    CandidateUnpricedPolicyScope,
)
from polisyos.runtime.quality.agent_action_authority import (
    AGENT_ACTION_AUTHORITY_SCHEMA_VERSION,
    AGENT_ACTION_DECISION_ARTIFACT_KIND,
    CANDIDATE_EXPERIMENT_ACTION_KIND,
    AgentActionAuthorityGateway,
    AgentActionAuthorityWriteContext,
    agent_action_content_hash,
)
from tests._helpers.acquisition_production import (
    _baseline,
    bind_fixture_l1_catalog_source,
    install_fixture_wdi_cost_basis,
    persist_wdi_route,
)
from tests.unit.runtime.quality.test_substrate_registry import _write_substrate_catalog_fixture

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class _NeverExecutionPort:
    def execute(self, closure):  # pragma: no cover - replay must stop before owner execution
        del closure
        raise AssertionError("terminal replay must not invoke the owner effect")

    def reenter(self, closure, result):  # pragma: no cover - terminal replay has no re-entry
        del closure, result
        raise AssertionError("terminal replay must not re-enter")

    def resume_reentry(self, closure, owner_receipt_refs):  # pragma: no cover
        del closure, owner_receipt_refs
        raise AssertionError("terminal replay must not resume re-entry")


class _NeverAuthorityProvider:
    def for_job(self, **_kwargs):  # pragma: no cover - terminal replay must stop before authority
        raise AssertionError("terminal replay must not request authority")

    def for_request(self, **_kwargs):  # pragma: no cover
        raise AssertionError("terminal replay must not create a new decision")


@pytest.mark.asyncio
async def test_replayed_terminal_job_reads_cas_head_without_repeating_authority_or_effect(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    install_fixture_wdi_cost_basis(monkeypatch)
    with runtime_api_env["client"]:
        app = runtime_api_env["app"]
        container = app.state.runtime_container
        control = container.control_service
        service = container.acquisition_action_service
        assert type(service) is AcquisitionActionService
        assert service.control_service is control
        tenant_id = str(runtime_api_env["tenant_a"])
        cell_id = str(runtime_api_env["cell_a"])
        run_id = "run-dx0-terminal-replay"
        fixture_repo_root = _prepare_native_n7_catalog_root(tmp_path / "native-n7-fixture-repo")

        async with _fixture_route(
            control,
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            generation_cycle_repo_root=fixture_repo_root,
        ) as closure:
            projection = service._projection(closure)
            request = AcquisitionRouteMutationRequest(
                route_projection_hash=projection.route_projection_hash,
                planner_report_hash=projection.planner_report_hash,
                replay_pins=projection.replay_pins,
                idempotency_key="dx0-terminal-replay",
            )
            operation, invocation, intent = service._action_tuple(closure, request)
            job_id = service._job_id(closure, request)
            payload = {
                "tenant_id": tenant_id,
                "cell_id": cell_id,
                "run_id": run_id,
                "route_id": closure.route_id,
                "decision_ref": "sha256:" + "9" * 64,
                "request": request.model_dump(mode="json"),
                "operation": operation.model_dump(mode="json"),
                "invocation": invocation.model_dump(mode="json"),
                "intent": intent.model_dump(mode="json"),
            }

            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                job = control.enqueue_acquisition_job(
                    job_id=job_id,
                    run_id=run_id,
                    payload=payload,
                    principal=RuntimePrincipal(
                        subject="dx0-terminal-replay",
                        tenant_id=tenant_id,
                        cell_id=cell_id,
                        authenticated=True,
                        roles=frozenset({"analyst"}),
                    ),
                )
                sink = control.acquisition_route_sink
                generation = service._action_generation(closure, job_id)
                requested = service._phase_receipt(
                    action_generation=generation,
                    closure=closure,
                    job_id=job_id,
                    decision_ref=str(payload["decision_ref"]),
                    receipt_phase="requested",
                    predecessor_receipt_ref=None,
                    owner_receipt_refs=(),
                )
                requested_head = sink.persist_phase(requested)
                executing = service._phase_receipt(
                    action_generation=generation,
                    closure=closure,
                    job_id=job_id,
                    decision_ref=str(payload["decision_ref"]),
                    receipt_phase="executing",
                    predecessor_receipt_ref=requested_head.receipt_ref,
                    owner_receipt_refs=(),
                )
                executing_head = sink.persist_phase(executing)
                owner_ref = control._put_json_artifact(
                    {"disposition": "quarantined_no_growth"},
                    kind="runtime_quality.acquisition_owner_receipt",
                    schema_name="polisyos.runtime.AcquisitionOwnerReceipt",
                )
                terminal = service._terminal_receipt(
                    action_generation=generation,
                    closure=closure,
                    job_id=job_id,
                    decision_ref=str(payload["decision_ref"]),
                    predecessor_receipt_ref=executing_head.receipt_ref,
                    owner_receipt_refs=(owner_ref,),
                )
                terminal_head = sink.persist_terminal(terminal)

                original_port = service._execution_port
                original_provider = service._authority_provider
                original_movement = service._movement_service
                service._execution_port = _NeverExecutionPort()
                service._authority_provider = _NeverAuthorityProvider()
                service._movement_service = None
                try:
                    scope = ControlJobExecutionScope(
                        status="established",
                        tenant_id=tenant_id,
                        cell_id=cell_id,
                        actor_subject="dx0-terminal-replay",
                        actor_authenticated=True,
                        actor_roles=("analyst",),
                    )
                    first = service.handle_job(job, payload, scope)
                    second = service.handle_job(job, payload, scope)
                finally:
                    service._execution_port = original_port
                    service._authority_provider = original_provider
                    service._movement_service = original_movement

            assert first == second
            assert first["receipt_phase"] == "terminal"
            assert first["terminal_receipt_ref"] == terminal_head.receipt_ref


@asynccontextmanager
async def _fixture_route(
    control: Any,
    *,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    generation_cycle_repo_root: Path,
) -> AsyncIterator[Any]:
    closure, _source = await persist_wdi_route(
        control,
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_id=run_id,
        job_id="job-dx0-terminal-replay-source",
        generation_cycle_repo_root=generation_cycle_repo_root,
    )
    yield closure


def _prepare_native_n7_catalog_root(repo_root: Path) -> Path:
    """Compose the existing bound L1 fixture and complete N7 catalog metadata."""
    from polisyos.runtime.quality.substrate_registry import (
        build_substrate_registry_from_existing_catalogs,
        default_substrate_catalog_paths,
    )

    baseline = _baseline(repo_root)
    baseline_digest = hashlib.sha256(baseline.read_bytes()).hexdigest()
    bind_fixture_l1_catalog_source(
        repo_root,
        baseline,
        include_n7_dataset_bundle=True,
    )
    _write_substrate_catalog_fixture(repo_root, include_graphs=False)
    if hashlib.sha256(baseline.read_bytes()).hexdigest() != baseline_digest:
        raise AssertionError("native_n7_fixture_catalog_metadata_replaced_owner_l1")
    paths = default_substrate_catalog_paths(repo_root)
    if paths.l1_dcat_path.resolve(strict=True) != baseline.resolve(strict=True):
        raise AssertionError("native_n7_fixture_catalog_source_binding_mismatch")
    build_substrate_registry_from_existing_catalogs(repo_root)
    return repo_root


def _candidate_experiment_action_fixture(
    *,
    tenant_id: str = "tenant-action-test",
    cell_id: str = "cell-action-test",
    run_id: str = "run-action-test",
) -> tuple[Any, CandidateExperimentRouteMutationRequest]:
    """Build typed source pins for tuple-only tests; these are not CAS evidence."""

    def ref(kind: str, digit: str) -> artifacts.ArtifactRef:
        return artifacts.ArtifactRef(
            artifact_id=f"sha256:{digit * 64}",
            kind=kind,
            media_type="application/json",
            manifest_profile_sha256="sha256:" + "f" * 64,
        )

    scope = CandidateUnpricedPolicyScope(
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_id=run_id,
        source_job_id="job-source-test",
        design_problem_ref="sha256:" + "1" * 64,
        design_problem_basis_ref="sha256:" + "2" * 64,
        source_cycle_index=3,
        candidate_id="candidate-test",
        candidate_content_hash="sha256:" + "3" * 64,
        requirement_id="requirement-test",
        compiled_requirement_ref="compiled-requirement-test",
        candidate_digest="sha256:" + "4" * 64,
        planner_report_hash="sha256:" + "5" * 64,
        compiled_ref=ref("runtime.compiled_recursive_generation_cycle", "6"),
        planner_report_ref=ref("runtime.acquisition_planner_report", "7"),
        compiler_report_ref=ref("runtime.data_requirement_compilation_report", "8"),
        configured_port_source_ref=ref("runtime.quality.n7_configured_candidate_port_source", "9"),
    )
    policy_ref = ref("runtime_quality.candidate_unpriced_acquisition_policy", "a")
    origin = SimpleNamespace(
        tenant_id=scope.tenant_id,
        cell_id=scope.cell_id,
        run_id=scope.run_id,
        source_job_id=scope.source_job_id,
        source_payload_ref="sha256:" + "b" * 64,
        request_content_hash="sha256:" + "c" * 64,
        route_id="sha256:" + "d" * 64,
        policy_ref=policy_ref,
        policy_scope=scope,
        source_cycle=SimpleNamespace(
            cycle_index=scope.source_cycle_index,
            voi_decision=SimpleNamespace(
                scheduler_action="acquire",
                scheduler_reason="synthetic tuple fixture",
            ),
        ),
        candidate_terminal_history_chain=(),
    )
    origin.effective_source_cycle = origin.source_cycle
    request = CandidateExperimentRouteMutationRequest(
        route_id=origin.route_id,
        replay_pins=CandidateExperimentRouteReplayPins(
            source_job_id=origin.source_job_id,
            source_payload_ref=origin.source_payload_ref,
            request_content_hash=origin.request_content_hash,
            compiled_ref=scope.compiled_ref,
            planner_report_ref=scope.planner_report_ref,
            compiler_report_ref=scope.compiler_report_ref,
            configured_port_source_ref=scope.configured_port_source_ref,
            policy_ref=policy_ref,
            candidate_digest=scope.candidate_digest,
        ),
        idempotency_key="candidate-action-test",
    )
    return origin, request


def test_candidate_experiment_action_tuple_binds_unpriced_source_and_decision_ref() -> None:
    """Candidate PA2 identity binds selected inputs without borrowing costed fields."""
    origin, request = _candidate_experiment_action_fixture()
    operation, invocation, intent = AcquisitionActionService._candidate_experiment_action_tuple(
        origin, request
    )

    assert operation.operation_id == CANDIDATE_EXPERIMENT_ACTION_KIND
    assert operation.operation_version == "v1"
    assert operation.operation_class.value == "ACQUIRE"
    assert operation.cost_model == {"monetary_cost": "not_established"}
    assert intent.action_kind == CANDIDATE_EXPERIMENT_ACTION_KIND
    assert invocation.parameters["source_payload_ref"] == origin.source_payload_ref
    assert invocation.parameters["request_content_hash"] == origin.request_content_hash
    assert invocation.parameters["candidate_digest"] == request.replay_pins.candidate_digest
    assert invocation.parameters[
        "action_job_id"
    ] == AcquisitionActionService._candidate_experiment_job_id(origin, request)
    assert invocation.parameters["policy_ref"] == request.replay_pins.policy_ref.model_dump(
        mode="json"
    )
    assert "cost_basis_hash" not in invocation.parameters
    assert invocation.parameters["replay_pins"] == request.replay_pins.model_dump(mode="json")

    decision_ref = "sha256:" + "e" * 64
    decision_request = request.model_copy(update={"human_decision_record_ref": decision_ref})
    changed_tuple = AcquisitionActionService._candidate_experiment_action_tuple(
        origin, decision_request
    )
    assert changed_tuple[1].invocation_id != invocation.invocation_id
    assert agent_action_content_hash(changed_tuple[1]) != agent_action_content_hash(invocation)

    changed_policy = request.replay_pins.policy_ref.model_copy(
        update={"artifact_id": "sha256:" + "f" * 64}
    )
    changed_policy_request = request.model_copy(
        update={
            "replay_pins": request.replay_pins.model_copy(update={"policy_ref": changed_policy})
        }
    )
    policy_tuple = AcquisitionActionService._candidate_experiment_action_tuple(
        origin, changed_policy_request
    )
    assert agent_action_content_hash(policy_tuple[1]) != agent_action_content_hash(invocation)


def test_candidate_experiment_worker_payload_is_not_coerced_to_costed_request() -> None:
    """The explicit candidate discriminator reaches its strict owner-scope guard."""
    _, request = _candidate_experiment_action_fixture()
    service = object.__new__(AcquisitionActionService)
    payload = {
        "action_kind": CANDIDATE_EXPERIMENT_ACTION_KIND,
        "tenant_id": "tenant-foreign",
        "cell_id": "cell-action-test",
        "run_id": "run-action-test",
        "route_id": request.route_id,
        "decision_ref": "sha256:" + "e" * 64,
        "request": request.model_dump(mode="json"),
    }
    job = SimpleNamespace(kind="acquisition", run_id="run-action-test", state="running")
    scope = ControlJobExecutionScope(
        status="established",
        tenant_id="tenant-action-test",
        cell_id="cell-action-test",
        actor_subject="candidate-worker-test",
        actor_authenticated=True,
        actor_roles=("analyst",),
    )

    payload["unbound_extra"] = "must not be accepted"
    with pytest.raises(AcquisitionActionServiceError) as extra_field:
        service.handle_job(job, payload, scope)
    assert extra_field.value.code == "candidate_experiment_job_payload_fields_invalid"

    del payload["unbound_extra"]
    with pytest.raises(AcquisitionActionServiceError) as rejected:
        service.handle_job(job, payload, scope)
    assert rejected.value.code == "candidate_experiment_job_payload_scope_mismatch"


@pytest.mark.parametrize("foreign_action_field", [False, True])
def test_candidate_worker_consumes_actual_control_telemetry_envelope(
    foreign_action_field: bool,
) -> None:
    """The real payload producer's diagnostics do not become action parameters."""
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService

    _, request = _candidate_experiment_action_fixture()
    control = object.__new__(ControlPlaneService)
    control._tracer = SimpleNamespace()
    action_payload = {
        "action_kind": CANDIDATE_EXPERIMENT_ACTION_KIND,
        "tenant_id": "foreign-tenant",
        "cell_id": "cell-action-test",
        "run_id": "run-action-test",
        "route_id": request.route_id,
        "decision_ref": "sha256:" + "e" * 64,
        "request": request.model_dump(mode="json"),
    }
    payload = control._enrich_job_payload(action_payload, request_id="actual-envelope-test")
    assert payload["_telemetry"]["request_id"] == "actual-envelope-test"
    assert set(payload["_telemetry"]["runtime_trace"]) == {"trace_id", "span_id", "parent_span_id"}
    assert "_telemetry" not in action_payload
    if foreign_action_field:
        payload["unbound_extra"] = "must still refuse"
    service = object.__new__(AcquisitionActionService)
    job = SimpleNamespace(kind="acquisition", run_id="run-action-test", state="running")
    scope = ControlJobExecutionScope(
        status="established",
        tenant_id="tenant-action-test",
        cell_id="cell-action-test",
        actor_subject="candidate-worker-test",
        actor_authenticated=True,
        actor_roles=("analyst",),
    )
    with pytest.raises(AcquisitionActionServiceError) as rejected:
        service.handle_job(job, payload, scope)
    expected = (
        "candidate_experiment_job_payload_fields_invalid"
        if foreign_action_field
        else "candidate_experiment_job_payload_scope_mismatch"
    )
    assert rejected.value.code == expected
    assert "_telemetry" in payload


def test_candidate_worker_refuses_unknown_control_telemetry_fields() -> None:
    """A reserved diagnostic key is not an escape from strict payload validation."""
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService

    control = object.__new__(ControlPlaneService)
    control._tracer = SimpleNamespace()
    payload = control._enrich_job_payload({}, request_id="malformed-envelope-test")
    payload["_telemetry"]["action_authority"] = "allowed"
    with pytest.raises(ValueError, match="control_job_telemetry_invalid"):
        ControlPlaneService._job_payload_without_telemetry(payload)


@pytest.mark.parametrize("variant", ["canonical", "foreign_job", "missing_job", "extra"])
def test_candidate_worker_consumes_canonical_execution_scope_payload(variant: str) -> None:
    """Actual Control scope enrichment reaches the lease check, never action authority."""
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService

    class LeaseBoundaryReachedError(Exception):
        pass

    class ObservedStore:
        calls = 0

        def current_execution_job_admission(self) -> None:
            self.calls += 1
            raise LeaseBoundaryReachedError

    _, request = _candidate_experiment_action_fixture()
    job = SimpleNamespace(
        job_id="job-current-candidate",
        kind="acquisition",
        run_id="run-action-test",
        state="running",
    )
    scope = ControlJobExecutionScope(
        status="established",
        tenant_id="tenant-action-test",
        cell_id="cell-action-test",
        actor_subject="candidate-worker-test",
        actor_authenticated=True,
        actor_roles=("analyst",),
    )
    control = object.__new__(ControlPlaneService)
    control._tracer = SimpleNamespace()
    original = {
        "action_kind": CANDIDATE_EXPERIMENT_ACTION_KIND,
        "tenant_id": scope.tenant_id,
        "cell_id": scope.cell_id,
        "run_id": job.run_id,
        "route_id": request.route_id,
        "decision_ref": "sha256:" + "e" * 64,
        "request": request.model_dump(mode="json"),
    }
    # Exercise both real producers; telemetry-only coverage missed this job ID.
    payload = control._payload_for_execution_scope(
        control._enrich_job_payload(original, request_id="actual-execution-scope"),
        job=job,
        execution_scope=scope,
    )
    assert payload["job_id"] == job.job_id
    assert "job_id" not in original
    if variant == "foreign_job":
        payload["job_id"] = "job-foreign"
    elif variant == "missing_job":
        del payload["job_id"]
    elif variant == "extra":
        payload["unbound_action_parameter"] = True
    store = ObservedStore()
    control._control_store = store
    service = object.__new__(AcquisitionActionService)
    service.control_service = control
    if variant == "canonical":
        with pytest.raises(LeaseBoundaryReachedError):
            service.handle_job(job, payload, scope)
        assert store.calls == 1
    else:
        with pytest.raises(AcquisitionActionServiceError) as rejected:
            service.handle_job(job, payload, scope)
        expected = (
            "candidate_experiment_job_payload_fields_invalid"
            if variant == "extra"
            else "candidate_experiment_job_payload_scope_mismatch"
        )
        assert rejected.value.code == expected
        assert store.calls == 0


def _candidate_experiment_pending_resume_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    catalog_source: object | None = None,
) -> dict[str, Any]:
    """Build a structural-only worker boundary; no CAS, authority, or N5 is exercised."""
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
    )
    from polisyos.runtime.quality import acquisition_evaluation_dispatch
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentPhaseReceipt,
        _ResolvedCurrentCandidateExperiment,
    )
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
    from polisyos.runtime.quality.generation_cycle import LoopVOIDecision
    from polisyos.runtime.quality.substrate_registry import (
        CatalogServingSourceSelection,
        current_catalog_serving_source,
        resolve_catalog_serving_source,
    )

    if catalog_source is None:
        selected_root = tmp_path / "selected-catalog"
        selected_root.mkdir()
        (selected_root / "dataset_catalog.duckdb").write_bytes(b"selected synthetic catalog")
        catalog_source = resolve_catalog_serving_source(
            tmp_path,
            selection=CatalogServingSourceSelection(
                snapshot_root=selected_root,
                catalog_run_profile="prod_full",
                database_relative_path=Path("dataset_catalog.duckdb"),
            ),
            requested_profile="prod_full",
        )

    origin, request = _candidate_experiment_action_fixture()
    job_id = AcquisitionActionService._candidate_experiment_job_id(origin, request)
    authority_ref = artifacts.ArtifactRef(
        artifact_id="sha256:" + "e" * 64,
        kind="runtime_quality.agent_action_authority_decision",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "f" * 64,
    )
    action_ref = artifacts.ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="runtime_quality.acquisition_candidate_action_receipt",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "b" * 64,
    )
    phase = AcquisitionCandidateExperimentPhaseReceipt(
        receipt_id=f"{job_id}.candidate-experiment.reentry-pending",
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        run_id=origin.run_id,
        source_job_id=origin.source_job_id,
        route_id=origin.route_id,
        action_generation=1,
        job_id=job_id,
        source_payload_ref=origin.source_payload_ref,
        capability_manifest_ref="sha256:" + "c" * 64,
        request_content_hash=origin.request_content_hash,
        policy_scope=origin.policy_scope,
        policy_ref=origin.policy_ref,
        authority_decision_ref=authority_ref,
        voi_decision=LoopVOIDecision(
            candidate_id=origin.policy_scope.candidate_id,
            terminal_kind="candidate_experiment",
            scheduler_action="reject",
            scheduler_reason="roi_below_threshold",
            priority=0.0,
            next_action="stop",
            reason="synthetic worker-phase fixture",
        ),
        predecessor_receipt_ref="sha256:" + "d" * 64,
        owner_receipt_refs=(str(action_ref.artifact_id),),
        coarse_phase="candidate_input_prepared",
        receipt_phase="candidate_input_reentry_pending",
        recovery_state="reentry_recovery_required",
        candidate_receipt_ref=action_ref,
        generated_at=datetime.now(UTC),
    )
    head = SimpleNamespace(
        job_id=job_id,
        receipt_ref="sha256:" + "9" * 64,
        receipt_phase="candidate_input_reentry_pending",
    )
    initial_phase = phase.model_copy(
        update={
            "receipt_id": f"{job_id}.candidate-experiment.requested",
            "receipt_phase": "requested",
            "coarse_phase": "requested",
            "recovery_state": "none",
            "predecessor_receipt_ref": None,
            "owner_receipt_refs": (),
            "candidate_receipt_ref": None,
        }
    )
    outcome = SimpleNamespace(
        head=head,
        latest_receipt=phase,
        phase_chain=(
            SimpleNamespace(receipt=initial_phase, receipt_ref="sha256:" + "8" * 64),
            SimpleNamespace(receipt=phase, receipt_ref=head.receipt_ref),
        ),
    )
    job = SimpleNamespace(job_id=job_id, kind="acquisition", run_id=origin.run_id, state="running")
    execution_scope = ControlJobExecutionScope(
        status="established",
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        actor_subject="candidate-worker-test",
        actor_authenticated=True,
        actor_roles=("analyst",),
    )
    admission = SimpleNamespace(
        job=job,
        scope=execution_scope,
        matches_job_record=lambda candidate: candidate is job,
    )

    class ControlStore:
        def current_execution_job_admission(self) -> object:
            return admission

    calls: list[str] = []
    owner_resolution_calls: list[dict[str, object]] = []
    no_n5_calls: list[object] = []
    terminal_head = object()
    verified_outcome = object()

    class Sink:
        def experiment_action_outcomes(self, **_kwargs: object) -> tuple[object, ...]:
            raise AssertionError("worker must reuse outcomes from its current owner resolution")

        def verify_action_head(self, actual_head: object) -> object:
            assert actual_head is terminal_head
            assert current_catalog_serving_source() is catalog_source
            calls.append("verify")
            return verified_outcome

    sink = Sink()
    bridge = object.__new__(AcquisitionWorldGrowthBridge)
    port = object.__new__(WorldBankWDIAcquisitionExecutionPort)
    port._world_growth_bridge = bridge
    port.execute_candidate_experiment = lambda *_args, **_kwargs: no_n5_calls.append("N5")
    control = SimpleNamespace(
        _control_store=ControlStore(),
        acquisition_route_sink=sink,
        catalog_serving_source=catalog_source,
    )
    service = object.__new__(AcquisitionActionService)
    service.control_service = control
    service._execution_port = port
    service._production_execution_port = port

    def resolve_current(**kwargs: object) -> _ResolvedCurrentCandidateExperiment:
        owner_resolution_calls.append(kwargs)
        return _ResolvedCurrentCandidateExperiment(origin=origin, outcomes=(outcome,))

    service._candidate_experiment_loop = lambda **_kwargs: SimpleNamespace(
        resolve_current_candidate_experiment=lambda **kwargs: resolve_current(**kwargs).origin,
        _resolve_current_candidate_experiment_resolution=resolve_current,
    )
    service._candidate_experiment_terminal_progress = lambda actual: {
        "state": "completed" if actual is verified_outcome else "unexpected"
    }
    payload = {
        "action_kind": CANDIDATE_EXPERIMENT_ACTION_KIND,
        "job_id": job_id,
        "tenant_id": origin.tenant_id,
        "cell_id": origin.cell_id,
        "run_id": origin.run_id,
        "route_id": origin.route_id,
        "decision_ref": str(authority_ref.artifact_id),
        "request": request.model_dump(mode="json"),
    }
    case: dict[str, Any] = {
        "service": service,
        "job": job,
        "payload": payload,
        "execution_scope": execution_scope,
        "catalog_source": catalog_source,
        "foreign_source": replace(catalog_source, snapshot_root=tmp_path / "foreign-source"),
        "bridge": bridge,
        "origin": origin,
        "terminal_head": terminal_head,
        "verified_outcome": verified_outcome,
        "calls": calls,
        "owner_resolution_calls": owner_resolution_calls,
        "no_n5_calls": no_n5_calls,
        "dispatch_error": None,
        "dispatch_check": None,
    }

    def dispatch(*, bridge: object, origin: object) -> object:
        assert bridge is case["bridge"]
        assert origin is case["origin"]
        assert current_catalog_serving_source() is catalog_source
        calls.append("dispatch")
        if case["dispatch_check"] is not None:
            case["dispatch_check"]()
        if case["dispatch_error"] is not None:
            raise case["dispatch_error"]
        return terminal_head

    monkeypatch.setattr(
        acquisition_evaluation_dispatch,
        "dispatch_candidate_experiment_evaluation",
        dispatch,
    )
    return case


def test_pending_candidate_experiment_retry_scopes_dispatch_and_sink_to_app_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A genuine pending phase binds the app catalog through dispatch and final readback."""
    from polisyos.runtime.quality.substrate_registry import current_catalog_serving_source

    case = _candidate_experiment_pending_resume_case(tmp_path, monkeypatch)
    result = case["service"].handle_job(case["job"], case["payload"], case["execution_scope"])

    assert result == {"state": "completed"}
    assert case["calls"] == ["dispatch", "verify"]
    assert case["owner_resolution_calls"] == [
        {"run_id": case["origin"].run_id, "action_job_id": case["job"].job_id}
    ]
    assert case["no_n5_calls"] == []
    assert current_catalog_serving_source() is None


def test_pending_candidate_experiment_retry_restores_catalog_scope_after_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The synchronous app-source wrapper restores an absent outer context on failure."""
    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteRecoveryRequired
    from polisyos.runtime.quality.substrate_registry import current_catalog_serving_source

    case = _candidate_experiment_pending_resume_case(tmp_path, monkeypatch)
    case["dispatch_error"] = ValueError("synthetic dispatch refusal")

    with pytest.raises(
        AcquisitionRouteRecoveryRequired,
        match="candidate_experiment_evaluation_recovery_required",
    ):
        case["service"].handle_job(case["job"], case["payload"], case["execution_scope"])

    assert case["calls"] == ["dispatch"]
    assert case["owner_resolution_calls"] == [
        {"run_id": case["origin"].run_id, "action_job_id": case["job"].job_id}
    ]
    assert case["no_n5_calls"] == []
    assert current_catalog_serving_source() is None


def test_pending_candidate_experiment_retry_uses_app_catalog_and_restores_equivalent_outer_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The app source wins for its call while an equivalent outer source is restored."""
    from polisyos.runtime.quality.substrate_registry import (
        catalog_serving_source_scope,
        current_catalog_serving_source,
    )

    case = _candidate_experiment_pending_resume_case(tmp_path, monkeypatch)
    app_source = case["catalog_source"]
    outer_source = replace(app_source)
    assert outer_source is not app_source
    assert outer_source == app_source

    with catalog_serving_source_scope(outer_source):
        assert current_catalog_serving_source() is outer_source
        result = case["service"].handle_job(case["job"], case["payload"], case["execution_scope"])
        assert result == {"state": "completed"}
        assert current_catalog_serving_source() is outer_source

    assert case["calls"] == ["dispatch", "verify"]
    assert case["owner_resolution_calls"] == [
        {"run_id": case["origin"].run_id, "action_job_id": case["job"].job_id}
    ]
    assert case["no_n5_calls"] == []
    assert current_catalog_serving_source() is None


def test_pending_candidate_experiment_retry_restores_foreign_outer_catalog_after_app_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The service owns its source during the call and restores any caller context."""
    from polisyos.runtime.quality.substrate_registry import (
        catalog_serving_source_scope,
        current_catalog_serving_source,
    )

    case = _candidate_experiment_pending_resume_case(tmp_path, monkeypatch)
    with catalog_serving_source_scope(case["foreign_source"]):
        assert current_catalog_serving_source() is case["foreign_source"]
        result = case["service"].handle_job(case["job"], case["payload"], case["execution_scope"])
        assert result == {"state": "completed"}
        assert current_catalog_serving_source() is case["foreign_source"]

    assert case["calls"] == ["dispatch", "verify"]
    assert case["owner_resolution_calls"] == [
        {"run_id": case["origin"].run_id, "action_job_id": case["job"].job_id}
    ]
    assert case["no_n5_calls"] == []
    assert current_catalog_serving_source() is None


def test_pending_candidate_experiment_retry_preserves_real_catalog_readmission_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Binding the app scope does not override a catalog that changed after selection."""
    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteRecoveryRequired
    from polisyos.runtime.quality.substrate_registry import (
        CatalogServingSourceSelection,
        current_catalog_serving_source,
        require_catalog_serving_source_unchanged,
        resolve_catalog_serving_source,
    )

    selected_root = tmp_path / "selected-catalog"
    selected_root.mkdir()
    database = selected_root / "dataset_catalog.duckdb"
    database.write_bytes(b"selected source bytes")
    source = resolve_catalog_serving_source(
        tmp_path,
        selection=CatalogServingSourceSelection(
            snapshot_root=selected_root,
            catalog_run_profile="prod_full",
            database_relative_path=Path("dataset_catalog.duckdb"),
        ),
        requested_profile="prod_full",
    )
    case = _candidate_experiment_pending_resume_case(
        tmp_path / "worker", monkeypatch, catalog_source=source
    )
    case["dispatch_check"] = lambda: require_catalog_serving_source_unchanged(source)
    database.write_bytes(b"changed after source admission")

    with pytest.raises(AcquisitionRouteRecoveryRequired) as refused:
        case["service"].handle_job(case["job"], case["payload"], case["execution_scope"])

    assert (
        getattr(refused.value.__cause__, "code", None)
        == "catalog_source_content_changed_readmission_required"
    )
    assert case["calls"] == ["dispatch"]
    assert case["no_n5_calls"] == []
    assert current_catalog_serving_source() is None


def _candidate_selected_evaluation() -> AcquisitionSelectedEvaluation:
    def ref(kind: str, digit: str) -> artifacts.ArtifactRef:
        digest = "sha256:" + digit * 64
        return artifacts.ArtifactRef(
            artifact_id=digest,
            kind=kind,
            media_type="application/json",
            manifest_profile_sha256="sha256:" + "f" * 64,
        )

    return AcquisitionSelectedEvaluation(
        candidate_id="candidate-current-action",
        candidate_content_hash="sha256:" + "1" * 64,
        design_problem_ref="sha256:" + "2" * 64,
        world_model_record_hash="sha256:" + "3" * 64,
        evaluation_job_id="job-evaluation-current-action",
        evaluation_run_id="run-current-action",
        generation_run_id="generation-current-action",
        cycle_index=0,
        n4_source_ref=ref("runtime.quality.n4_candidate_scenario_source", "4"),
        context_job_ref=ref("runtime.quality.cycle_substrate_context_job", "5"),
        n5_input_ref=ref("runtime.quality.candidate_simulation_n5_input", "6"),
        n5_execution_ref=ref("runtime.quality.candidate_simulation_execution", "7"),
        n5_result_ref=ref("polisyos.runtime.joint_simulation_result", "8"),
    )


def _candidate_current_action_head(
    *,
    generation: int = 1,
    receipt_phase: str = "candidate_input_reentry_pending",
    coarse_phase: str = "candidate_input_prepared",
    recovery_state: str = "reentry_recovery_required",
) -> AcquisitionActionHeadRecord:
    receipt_ref = "sha256:" + str(generation % 10) * 64
    return AcquisitionActionHeadRecord(
        tenant_id="tenant-current-action",
        cell_id="cell-current-action",
        run_id="run-current-action",
        source_job_id="source-current-action",
        route_id="sha256:" + "a" * 64,
        action_generation=generation,
        head_generation=generation,
        receipt_ref=receipt_ref,
        receipt_sha256=receipt_ref,
        durable_event_id=f"event-current-action-{generation}",
        coarse_phase=coarse_phase,
        receipt_phase=receipt_phase,
        recovery_state=recovery_state,
        job_id=f"job-current-action-{generation}",
        predecessor_receipt_ref=("sha256:" + "b" * 64) if generation > 1 else None,
        created_at=datetime(2026, 11, 4, tzinfo=UTC),
        receipt_manifest_profile_sha256="sha256:" + "f" * 64,
    )


def test_candidate_current_action_formatter_does_not_carry_forward_prior_terminal() -> None:
    """Formatter only: an owner-adapted newer head cannot inherit prior evaluation status."""
    current_head = _candidate_current_action_head(generation=2)
    old_evaluation = _candidate_selected_evaluation()
    selected_receipt_ref = artifacts.ArtifactRef(
        artifact_id=current_head.receipt_ref,
        kind="runtime_quality.acquisition_candidate_experiment_phase_receipt",
        media_type="application/json",
        manifest_profile_sha256=current_head.receipt_manifest_profile_sha256,
    )

    projected = AcquisitionActionService._format_candidate_experiment_current_action(
        head=current_head,
        job_state="running",
        selected_receipt_ref=selected_receipt_ref,
        current_terminal_head=_candidate_current_action_head(generation=1),
        terminal_outcome="candidate_evaluation_retained",
        selected_evaluation=old_evaluation,
        blocker_reason="stale blocker must not survive",
    )

    assert projected.status == "in_progress"
    assert projected.action_generation == 2
    assert projected.receipt_phase == "candidate_input_reentry_pending"
    assert projected.job_state == "running"
    assert projected.terminal_outcome is None
    assert projected.evaluation_disposition == "unknown"
    assert projected.selected_evaluation is None
    assert projected.blocker_reason is None


@pytest.mark.parametrize(
    ("terminal_outcome", "evaluation_disposition"),
    [
        ("candidate_reentry_completed", "new"),
        ("candidate_evaluation_retained", "retained"),
    ],
)
def test_candidate_current_action_formatter_projects_current_selected_evaluation(
    terminal_outcome: str,
    evaluation_disposition: str,
) -> None:
    """Formatter seam only: owner-selected terminal outcomes retain their declared relation."""
    terminal_head = _candidate_current_action_head(
        receipt_phase="terminal",
        coarse_phase="terminal",
        recovery_state="complete",
    )
    selected_receipt_ref = artifacts.ArtifactRef(
        artifact_id=terminal_head.receipt_ref,
        kind="runtime_quality.acquisition_route_loop_receipt",
        media_type="application/json",
        manifest_profile_sha256=terminal_head.receipt_manifest_profile_sha256,
    )
    selected_evaluation = _candidate_selected_evaluation()

    projected = AcquisitionActionService._format_candidate_experiment_current_action(
        head=terminal_head,
        job_state="completed",
        selected_receipt_ref=selected_receipt_ref,
        current_terminal_head=terminal_head,
        terminal_outcome=terminal_outcome,
        selected_evaluation=selected_evaluation,
    )

    assert projected.status == "completed"
    assert projected.terminal_outcome == terminal_outcome
    assert projected.evaluation_disposition == evaluation_disposition
    assert projected.selected_evaluation == selected_evaluation


def test_candidate_current_action_formatter_keeps_blocked_terminal_unpriced_and_unselected() -> (
    None
):
    """Formatter only: a current blocked terminal cannot publish a previous evaluation."""
    terminal_head = _candidate_current_action_head(
        receipt_phase="terminal",
        coarse_phase="terminal",
        recovery_state="complete",
    )
    selected_receipt_ref = artifacts.ArtifactRef(
        artifact_id=terminal_head.receipt_ref,
        kind="runtime_quality.acquisition_route_loop_receipt",
        media_type="application/json",
        manifest_profile_sha256=terminal_head.receipt_manifest_profile_sha256,
    )

    projected = AcquisitionActionService._format_candidate_experiment_current_action(
        head=terminal_head,
        job_state="completed",
        selected_receipt_ref=selected_receipt_ref,
        current_terminal_head=terminal_head,
        terminal_outcome="candidate_blocked",
        selected_evaluation=_candidate_selected_evaluation(),
        blocker_reason="required prior evaluation is unavailable",
    )

    assert projected.status == "blocked"
    assert projected.terminal_outcome == "candidate_blocked"
    assert projected.evaluation_disposition == "blocked"
    assert projected.selected_evaluation is None
    assert projected.blocker_reason == "required prior evaluation is unavailable"


def test_candidate_current_action_projection_keeps_absence_unknown_and_requires_profile() -> None:
    absent = CandidateExperimentCurrentActionProjection()
    assert absent.status == "unknown"
    assert absent.evaluation_disposition == "unknown"
    assert absent.action_generation is None

    head = _candidate_current_action_head()
    with pytest.raises(
        ValueError,
        match="candidate_experiment_current_projection_identity_missing",
    ):
        CandidateExperimentCurrentActionProjection(
            action_generation=head.action_generation,
            job_id=head.job_id,
            job_state="running",
            coarse_phase=head.coarse_phase,
            receipt_phase=head.receipt_phase,
            recovery_state=head.recovery_state,
            selected_receipt_ref=artifacts.ArtifactRef(
                artifact_id=head.receipt_ref,
                kind="runtime_quality.acquisition_candidate_experiment_phase_receipt",
                media_type="application/json",
            ),
        )

    with pytest.raises(
        ValueError,
        match="candidate_experiment_completed_projection_missing_evaluation",
    ):
        CandidateExperimentCurrentActionProjection(
            status="completed",
            action_generation=1,
            job_id="job-current-action-1",
            job_state="completed",
            coarse_phase="terminal",
            receipt_phase="terminal",
            recovery_state="complete",
            selected_receipt_ref=artifacts.ArtifactRef(
                artifact_id="sha256:" + "1" * 64,
                kind="runtime_quality.acquisition_route_loop_receipt",
                media_type="application/json",
                manifest_profile_sha256="sha256:" + "f" * 64,
            ),
            terminal_outcome="candidate_reentry_completed",
        )


def test_candidate_experiment_execution_envelope_is_strict_and_preserves_decision_ref() -> None:
    _, request = _candidate_experiment_action_fixture()
    decision_ref = "sha256:" + "e" * 64
    envelope = CandidateExperimentRouteExecutionRequest(
        request=request,
        decision_ref=decision_ref,
    )
    assert envelope.request is request
    assert envelope.decision_ref == decision_ref
    with pytest.raises(ValueError):
        CandidateExperimentRouteExecutionRequest.model_validate(
            {
                **envelope.model_dump(mode="json"),
                "execution_authority": "allowed",
            }
        )


def test_completed_candidate_retry_response_preserves_terminal_status() -> None:
    decision_ref = "sha256:" + "e" * 64
    common = {
        "run_id": "run-action-test",
        "route_id": "sha256:" + "a" * 64,
        "job_id": "candidate-action-test",
        "authority_decision_ref": decision_ref,
    }
    accepted = AcquisitionExecutionResponse(**common)
    completed = AcquisitionExecutionResponse(
        **common,
        status="completed",
        receipt_phase="terminal",
    )
    assert (accepted.status, accepted.receipt_phase) == ("accepted", "requested")
    assert (completed.status, completed.receipt_phase) == ("completed", "terminal")
    for values in (
        {**common, "status": "completed", "receipt_phase": "requested"},
        {**common, "status": "accepted", "receipt_phase": "terminal"},
    ):
        with pytest.raises(ValueError, match="acquisition_execution_status_phase_mismatch"):
            AcquisitionExecutionResponse(**values)


def test_reuse_retry_binds_existing_job_actor_body_and_decision_before_head_read(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """An immutable reuse payload alone cannot authorize or select a retry."""
    from tests.unit.runtime.quality.test_candidate_experiment_reuse import _reuse_action_selection

    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    runtime_api_env = request.getfixturevalue("runtime_api_env")
    selection = _reuse_action_selection()
    principal = RuntimePrincipal(
        subject="reuse-operator",
        tenant_id=selection.tenant_id,
        cell_id=selection.cell_id,
        roles=frozenset({"analyst"}),
        authenticated=True,
    )
    context = {
        "tenant_id": selection.tenant_id,
        "cell_id": selection.cell_id,
        "run_id": selection.run_id,
        "route_id": selection.route_id,
    }
    with (
        runtime_api_env["client"],
        tenant_scope(None, tenant_id=selection.tenant_id, cell_id=selection.cell_id),
    ):
        service = runtime_api_env["app"].state.runtime_container.acquisition_action_service
        control = service.control_service
        # These fixtures supply only the CAS locator. Without a selected head
        # and authenticated decision history the exact original also refuses.
        options = artifacts.ArtifactWriteOptions(
            kind=AGENT_ACTION_DECISION_ARTIFACT_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="polisyos.runtime.AgentActionAuthorityDecision",
                version=AGENT_ACTION_AUTHORITY_SCHEMA_VERSION,
            ),
            producer=artifacts.ProducerInfo(component="test.reuse_retry", version="1.0"),
            tenant_context=artifacts.ArtifactTenantContextInfo(
                tenant_id=selection.tenant_id, cell_id=selection.cell_id
            ),
            same_input_closure=artifacts.ArtifactSameInputClosureInfo(
                closure_id="test.reuse_retry",
                status="closed",
                run_id=selection.run_id,
                job_id=selection.action_job_id,
                tenant_id=selection.tenant_id,
                cell_id=selection.cell_id,
            ),
        )
        decision, other_decision = (
            str(
                control._artifact_store.put_json(
                    {"locator": label}, options, CanonSpec()
                ).artifact_id
            )
            for label in ("first", "second")
        )
        envelope = CandidateExperimentReuseActionExecutionRequest(
            request=selection.request, decision_ref=decision
        )
        job = control.enqueue_acquisition_job(
            job_id=selection.action_job_id,
            run_id=selection.run_id,
            payload=service._candidate_experiment_reuse_payload(selection, decision),
            request_id="original",
            principal=principal,
        )

        def forbid_enqueue(**_kwargs: object) -> object:
            raise AssertionError("retry attempted to enqueue again")

        monkeypatch.setattr(control, "enqueue_acquisition_job", forbid_enqueue)
        alternative_result = selection.request.n5_result_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "0" * 64}
        )
        for body, actor, expected in (
            (envelope, principal, "candidate_experiment_reuse_retry_head_not_established"),
            (
                envelope,
                replace(principal, subject="different-operator"),
                "candidate_experiment_reuse_source_scope_refused",
            ),
            (
                envelope,
                replace(principal, roles=frozenset({"reviewer"})),
                "candidate_experiment_reuse_source_scope_refused",
            ),
            (
                envelope.model_copy(update={"decision_ref": other_decision}),
                principal,
                "candidate_experiment_reuse_retry_payload_mismatch",
            ),
            (
                envelope.model_copy(
                    update={
                        "request": selection.request.model_copy(
                            update={"idempotency_key": "different-idempotency-key"}
                        )
                    }
                ),
                principal,
                "candidate_experiment_reuse_retry_payload_mismatch",
            ),
            (
                envelope.model_copy(
                    update={
                        "request": selection.request.model_copy(
                            update={"n5_result_ref": alternative_result}
                        )
                    }
                ),
                principal,
                "candidate_experiment_reuse_retry_payload_mismatch",
            ),
        ):
            with pytest.raises(AcquisitionActionServiceError) as error:
                service.execute_candidate_experiment_reuse(
                    **context, request=body, request_id="retry", principal=actor
                )
            assert error.value.code == expected
            assert control._control_store.get_job(job.job_id) == job


@pytest.mark.asyncio
async def test_execute_retries_bound_requested_and_terminal_action_identity(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """HTTP retries bind their deterministic job before selecting route history."""
    from tests.unit.runtime.quality.test_agent_action_authority import _proof

    install_fixture_wdi_cost_basis(monkeypatch)
    decision_ref = "sha256:" + "d" * 64
    monkeypatch.setattr(
        action_service_module,
        "reserve_agent_external_action",
        lambda **_kwargs: SimpleNamespace(
            write_result=SimpleNamespace(cas_ref=SimpleNamespace(artifact_id=decision_ref))
        ),
    )
    with runtime_api_env["client"]:
        app = runtime_api_env["app"]
        container = app.state.runtime_container
        control = container.control_service
        service = container.acquisition_action_service
        tenant_id = str(runtime_api_env["tenant_a"])
        cell_id = str(runtime_api_env["cell_a"])
        run_id = "run-dx0-requested-retry"
        fixture_repo_root = _prepare_native_n7_catalog_root(tmp_path / "native-n7-fixture-repo")

        class _ControlledAuthorityProvider:
            def for_request(
                self,
                *,
                closure,
                job_id: str,
                bound_permission,
                effect_handler,
                request,
            ) -> AgentActionAuthorityGateway:
                del request
                return AgentActionAuthorityGateway(
                    artifact_store=control._artifact_store,
                    event_log=control._diagnostic_event_log,
                    idempotency_store=RuntimeIdempotencyStore(
                        root=tmp_path / "controlled-idempotency"
                    ),
                    artifact_verifier=artifacts.Ed25519Verifier(),
                    bound_permission=bound_permission,
                    admission_producer_identity="controlled-test-seam",
                    write_context=AgentActionAuthorityWriteContext(
                        tenant_id=closure.tenant_id,
                        cell_id=closure.cell_id,
                        run_id=closure.run_id,
                        job_id=job_id,
                        trace_id=job_id,
                        span_id=f"{job_id}.authority",
                        owner="controlled-test-seam",
                        requested_execution_profile="test",
                        effective_execution_profile="test",
                        effective_mode_ref="fixture://controlled-test-seam",
                    ),
                    contract_refs_by_resource_digest={},
                    mandate_authority_evidence_refs_by_owner_ref={},
                    admission_refs_by_invocation_hash={},
                    effect_bindings=(),
                )

            def for_job(self, **_kwargs):  # pragma: no cover - terminal path stops before authority
                raise AssertionError("terminal replay must not request job authority")

        principal = RuntimePrincipal(
            subject="dx0-requested-retry",
            tenant_id=tenant_id,
            cell_id=cell_id,
            authenticated=True,
            roles=frozenset({"analyst"}),
        )

        async with _fixture_route(
            control,
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            generation_cycle_repo_root=fixture_repo_root,
        ) as closure:
            projection = service._projection(closure)
            request = AcquisitionRouteMutationRequest(
                route_projection_hash=projection.route_projection_hash,
                planner_report_hash=projection.planner_report_hash,
                replay_pins=projection.replay_pins,
                idempotency_key="dx0-requested-retry",
            )
            operation, invocation, intent = service._action_tuple(closure, request)
            monkeypatch.setattr(service, "_authority_provider", _ControlledAuthorityProvider())
            monkeypatch.setattr(service, "_execution_port", _NeverExecutionPort())
            monkeypatch.setattr(service, "_production_execution_bridge_installed", lambda: True)
            monkeypatch.setattr(
                service, "_require_production_execution_bridge", lambda _closure: None
            )
            monkeypatch.setattr(service, "_movement_service", None)

            def execute() -> object:
                with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                    return service.execute(
                        tenant_id=tenant_id,
                        cell_id=cell_id,
                        run_id=run_id,
                        route_id=closure.route_id,
                        request=request,
                        bound_permission=_proof(),
                        request_id="dx0-requested-retry",
                        principal=principal,
                    )

            with monkeypatch.context() as interrupted_enqueue:
                interrupted_enqueue.setattr(
                    control,
                    "enqueue_acquisition_job",
                    lambda **_kwargs: (_ for _ in ()).throw(
                        RuntimeError("controlled queue interruption")
                    ),
                )
                with pytest.raises(RuntimeError, match="controlled queue interruption"):
                    execute()

            with (
                tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id),
                pytest.raises(AcquisitionActionServiceError) as pending_route,
            ):
                service.get_route(
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                    run_id=run_id,
                    route_id=closure.route_id,
                )
            assert pending_route.value.code == "acquisition_action_outcome_not_terminal"

            retried = execute()
            job_id = service._job_id(closure, request)
            assert retried.job_id == job_id
            assert retried.authority_decision_ref == decision_ref

            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                sink = control.acquisition_route_sink
                action_generation = service._action_generation(closure, job_id)
                requested = service._phase_receipt(
                    action_generation=action_generation,
                    closure=closure,
                    job_id=job_id,
                    decision_ref=decision_ref,
                    receipt_phase="requested",
                    predecessor_receipt_ref=None,
                    owner_receipt_refs=(),
                )
                requested_head = sink.get_head(requested)
                assert requested_head is not None
                executing = service._phase_receipt(
                    action_generation=action_generation,
                    closure=closure,
                    job_id=job_id,
                    decision_ref=decision_ref,
                    receipt_phase="executing",
                    predecessor_receipt_ref=requested_head.receipt_ref,
                    owner_receipt_refs=(),
                )
                executing_head = sink.persist_phase(executing)
                owner_ref = control._put_json_artifact(
                    {"disposition": "quarantined_no_growth"},
                    kind="runtime_quality.acquisition_owner_receipt",
                    schema_name="polisyos.runtime.AcquisitionOwnerReceipt",
                )
                terminal_head = sink.persist_terminal(
                    service._terminal_receipt(
                        action_generation=action_generation,
                        closure=closure,
                        job_id=job_id,
                        decision_ref=decision_ref,
                        predecessor_receipt_ref=executing_head.receipt_ref,
                        owner_receipt_refs=(owner_ref,),
                    )
                )

            terminal_retry = execute()
            assert terminal_retry.job_id == job_id
            assert terminal_retry.route_id == closure.route_id
            assert terminal_retry.receipt_phase == "requested"

            payload = {
                "tenant_id": tenant_id,
                "cell_id": cell_id,
                "run_id": run_id,
                "route_id": closure.route_id,
                "decision_ref": decision_ref,
                "request": request.model_dump(mode="json"),
                "operation": operation.model_dump(mode="json"),
                "invocation": invocation.model_dump(mode="json"),
                "intent": intent.model_dump(mode="json"),
            }
            job = control._control_store.get_job(job_id)
            assert job is not None
            scope = ControlJobExecutionScope(
                status="established",
                tenant_id=tenant_id,
                cell_id=cell_id,
                actor_subject="dx0-requested-retry",
                actor_authenticated=True,
                actor_roles=("analyst",),
            )
            original_port = service._execution_port
            original_provider = service._authority_provider
            service._execution_port = _NeverExecutionPort()
            service._authority_provider = _NeverAuthorityProvider()
            try:
                with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                    replay = service.handle_job(job, payload, scope)
                    wrong_job = replace(job, job_id=f"{job_id}-sibling")
                    with pytest.raises(AcquisitionActionServiceError) as wrong_identity:
                        service.handle_job(wrong_job, payload, scope)
            finally:
                service._execution_port = original_port
                service._authority_provider = original_provider

            assert replay["receipt_phase"] == "terminal"
            assert replay["terminal_receipt_ref"] == terminal_head.receipt_ref
            assert wrong_identity.value.code == "acquisition_job_identity_mismatch"
            assert payload["request"] == request.model_dump(mode="json")
            assert payload["invocation"] == invocation.model_dump(mode="json")


def test_completed_candidate_reentry_projects_blocked_evaluation() -> None:
    """Physical reentry completion cannot imply a usable evaluation or break its reader."""
    head = _candidate_current_action_head(
        receipt_phase="terminal", coarse_phase="terminal", recovery_state="complete"
    )
    selected_ref = artifacts.ArtifactRef(
        artifact_id=head.receipt_ref,
        kind="runtime_quality.acquisition_route_loop_receipt",
        media_type="application/json",
        manifest_profile_sha256=head.receipt_manifest_profile_sha256,
    )
    inputs = {
        "head": head,
        "job_state": "completed",
        "selected_receipt_ref": selected_ref,
        "current_terminal_head": head,
        "terminal_outcome": "candidate_reentry_completed",
    }
    projected = AcquisitionActionService._format_candidate_experiment_current_action(
        **inputs,
        selected_evaluation=None,
        blocker_reason="candidate_evaluation_basis_not_established",
    )
    assert projected.status == "completed"
    assert projected.terminal_outcome == "candidate_reentry_completed"
    assert projected.evaluation_disposition == "blocked"
    assert projected.selected_evaluation is None
    assert projected.blocker_reason == "candidate_evaluation_basis_not_established"
    with pytest.raises(
        ValueError, match="candidate_experiment_completed_projection_missing_evaluation"
    ):
        AcquisitionActionService._format_candidate_experiment_current_action(
            **inputs, selected_evaluation=None
        )
    with pytest.raises(ValueError, match="candidate_experiment_completed_projection_has_blocker"):
        AcquisitionActionService._format_candidate_experiment_current_action(
            **inputs,
            selected_evaluation=_candidate_selected_evaluation(),
            blocker_reason="candidate_evaluation_basis_not_established",
        )
