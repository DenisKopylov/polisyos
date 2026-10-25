from __future__ import annotations

import hashlib
import os
import select
import signal
import threading
import time
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    ArtifactRef,
    SchemaInfo,
    artifact_ref_identity_key,
)
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.execution_plan import (
    ExecutionPlan,
    MethodCatalogEntry,
    MethodCatalogSnapshot,
    MethodDagNode,
)
from polisyos.core.security.identity import PolicyOSRole
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.methods.catalog.snapshot import persist_method_catalog_snapshot
from polisyos.scientist.methods.search.uncertainty import (
    SearchInputDependency,
    SearchOwnerSelectedSourceGraph,
    SearchRuntimeStageConfiguration,
    SearchUncertaintyAdmissionError,
    SearchUncertaintyHTERequestProjection,
    SearchUncertaintyOwnerTaskContext,
    SearchUncertaintySemanticScope,
    SearchUncertaintyStore,
    SearchUncertaintyTicketState,
    _canonical_sha256,
    _TicketFileLock,
    _verify_first_assessment_edge,
    derive_search_uncertainty_ticket_id,
    load_search_uncertainty_task_binding,
    persist_search_uncertainty_v2,
    produce_search_task_admission,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.scientist.orchestration.llm.cycle import persist_execution_plan

_REQUEST_ALPHA = 0.05


def test_search_ticket_file_lock_fork_exit_and_exclusion(tmp_path: Path) -> None:
    """Keep nested ticket ownership reentrant and safe across POSIX fork."""
    if not hasattr(os, "fork"):
        pytest.skip("ticket flock fork semantics require os.fork")
    module = __import__(
        "polisyos.scientist.methods.search.uncertainty",
        fromlist=["_TICKET_FILE_LOCK_REGISTRY"],
    )

    def wait_child(pid: int) -> int:
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            waited, status = os.waitpid(pid, os.WNOHANG)
            if waited:
                return status
            time.sleep(0.01)
        os.kill(pid, signal.SIGKILL)
        _, status = os.waitpid(pid, 0)
        raise AssertionError(f"forked lock probe failed to exit: status={status}")

    def child_waits_for_parent_release(
        path: Path,
        *,
        inherited: tuple[_TicketFileLock, ...],
        inherited_fds: tuple[int, ...],
        release_parent: Any,
    ) -> None:
        read_fd, write_fd = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(read_fd)
            try:
                for inherited_fd in inherited_fds:
                    try:
                        os.fstat(inherited_fd)
                    except OSError:
                        pass
                    else:
                        os.write(write_fd, b"INHERITED_FD_OPEN\n")
                        os._exit(3)
                if module._TICKET_FILE_LOCK_REGISTRY:
                    os.write(write_fd, b"CHILD_REGISTRY_NOT_EMPTY\n")
                    os._exit(4)
                for context in reversed(inherited):
                    context.__exit__(None, None, None)
                with _TicketFileLock(path):
                    os.write(write_fd, b"ACQUIRED\n")
                os.close(write_fd)
                os._exit(0)
            except BaseException as exc:
                try:
                    os.write(write_fd, ("ERROR:" + repr(exc) + "\n").encode())
                finally:
                    os._exit(2)

        os.close(write_fd)
        early = False
        early_payload = b""
        acquired = False
        payload = b""
        try:
            readable, _, _ = select.select([read_fd], [], [], 0.2)
            early = bool(readable)
            if early:
                early_payload = os.read(read_fd, 128)
            release_parent()
            readable, _, _ = select.select([read_fd], [], [], 5.0)
            acquired = bool(readable)
            if acquired:
                payload = os.read(read_fd, 128)
            status = wait_child(pid)
        finally:
            os.close(read_fd)
        assert not early, f"child bypassed parent lock: {early_payload!r}"
        assert acquired and payload == b"ACQUIRED\n", payload
        assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0

    nested_path = tmp_path / "nested.lock"
    with _TicketFileLock(nested_path), _TicketFileLock(nested_path):
        pass

    # An inner exception cannot release a lock still owned by the outer frame.
    exception_path = tmp_path / "exception.lock"
    outer = _TicketFileLock(exception_path)
    outer.__enter__()
    exception_competitor_entered = threading.Event()

    def exception_competitor() -> None:
        with _TicketFileLock(exception_path):
            exception_competitor_entered.set()

    exception_thread: threading.Thread | None = None
    try:
        with pytest.raises(RuntimeError, match="nested sentinel"), _TicketFileLock(exception_path):
            raise RuntimeError("nested sentinel")
        exception_thread = threading.Thread(target=exception_competitor)
        exception_thread.start()
        assert not exception_competitor_entered.wait(0.2)
    finally:
        outer.__exit__(None, None, None)
    if exception_thread is not None:
        exception_thread.join(5)
        assert not exception_thread.is_alive()
    assert exception_competitor_entered.is_set()

    thread_path = tmp_path / "thread.lock"
    owner_entered = threading.Event()
    release_owner = threading.Event()
    competitor_entered = threading.Event()

    def owner() -> None:
        with _TicketFileLock(thread_path):
            owner_entered.set()
            if not release_owner.wait(5):
                raise AssertionError("thread owner release timed out")

    def competitor() -> None:
        with _TicketFileLock(thread_path):
            competitor_entered.set()

    owner_thread = threading.Thread(target=owner)
    owner_thread.start()
    assert owner_entered.wait(5)
    competitor_thread = threading.Thread(target=competitor)
    competitor_thread.start()
    try:
        assert not competitor_entered.wait(0.2)
    finally:
        release_owner.set()
        owner_thread.join(5)
        competitor_thread.join(5)
    assert not owner_thread.is_alive() and not competitor_thread.is_alive()
    assert competitor_entered.is_set()

    owner_path = tmp_path / "fork-owner.lock"
    outer_owner = _TicketFileLock(owner_path)
    inner_owner = _TicketFileLock(owner_path)
    outer_owner.__enter__()
    inner_owner.__enter__()
    released = False

    def release_nested_owner() -> None:
        nonlocal released
        if not released:
            inner_owner.__exit__(None, None, None)
            outer_owner.__exit__(None, None, None)
            released = True

    owner_fds = tuple(state.handle.fileno() for state in module._TICKET_FILE_LOCK_REGISTRY.values())
    assert owner_fds
    try:
        child_waits_for_parent_release(
            owner_path,
            inherited=(outer_owner, inner_owner),
            inherited_fds=owner_fds,
            release_parent=release_nested_owner,
        )
    finally:
        release_nested_owner()

    other_path = tmp_path / "fork-other-thread.lock"
    other_entered = threading.Event()
    release_other = threading.Event()
    other_errors: list[str] = []

    def other_owner() -> None:
        try:
            with _TicketFileLock(other_path):
                other_entered.set()
                if not release_other.wait(5):
                    other_errors.append("parent owner timeout")
        except BaseException as exc:
            other_errors.append(repr(exc))

    other_thread = threading.Thread(target=other_owner)
    other_thread.start()
    assert other_entered.wait(5)
    other_fds = tuple(state.handle.fileno() for state in module._TICKET_FILE_LOCK_REGISTRY.values())
    assert other_fds
    try:
        child_waits_for_parent_release(
            other_path,
            inherited=(),
            inherited_fds=other_fds,
            release_parent=release_other.set,
        )
    finally:
        release_other.set()
        other_thread.join(5)
    assert not other_thread.is_alive()
    assert not other_errors
    assert not module._TICKET_FILE_LOCK_REGISTRY


def _put_selected_ref(
    store: SearchUncertaintyStore,
    *,
    name: str,
    kind: str,
) -> ArtifactRef:
    return ArtifactRef.model_validate(
        store.put_json(
            {"fixture": name},
            PutOptions(kind=kind, media_type="application/json"),
            return_selected_profile=True,
        ),
        strict=True,
    )


def _put_v2_hte_source(
    store: Any,
    *,
    tenant_id: str,
    cell_id: str,
) -> ArtifactRef:
    row_count = 40
    payload = {
        "outcome": [float(index) / 10 + (index % 2) * 0.5 for index in range(row_count)],
        "treatment": [index % 2 for index in range(row_count)],
        "covariates": [[float(index), float(index % 5)] for index in range(row_count)],
        "confounders": [[float(index % 7)] for index in range(row_count)],
        "feature_names": ["age", "baseline"],
        "confounder_names": ["risk"],
        "sample_ids": [f"candidate-{index}" for index in range(row_count)],
        "metadata": {"source": "controlled_candidate_fixture"},
    }
    ref = store.put_json(
        {
            "schema_version": "policyos.ir.observation.method_input_envelope.v1",
            "contract_target": {
                "contract_id": "foundry.causal.hte_observational_data.v1",
                "contract_fqn": (
                    "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
                ),
            },
            "contract_payload": payload,
        },
        PutOptions(
            kind="ir.observation_method_input",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.ir.ObservationMethodInputEnvelope",
                version="1.0",
            ),
            governance=ArtifactGovernanceInfo(classification="public"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return ArtifactRef.model_validate(ref, strict=True)


def _publish_complete_search_task(
    *,
    store: SearchUncertaintyStore,
    service: Any,
    source_ref: ArtifactRef,
    tenant_id: str,
    cell_id: str,
    run_id: str,
) -> tuple[SearchUncertaintyTicketState, str, ArtifactRef]:
    method_fqn = "causal.hte.causal_forest@2.0.0"
    registration = service._resolve_observational_method_registration(
        fqn=method_fqn,
        version=None,
    )
    method_params = service._resolve_observational_method_params(
        registration.signature,
        {"alpha": _REQUEST_ALPHA},
    )
    assert registration.signature.fqn == method_fqn
    assert registration.signature.version == "2.0.0"
    assert registration.method_profile_id == "econml.causal_forest_dml.native_mean@2.0"
    assert registration.method_profile_id is not None
    params_sha256 = _canonical_sha256(method_params)

    plan_ref = persist_execution_plan(
        store,
        ExecutionPlan(
            plan_id=f"plan-{run_id}",
            run_id=run_id,
            method_dag=[
                MethodDagNode(
                    node_id="selected-hte",
                    method_fqn=method_fqn,
                    method_version="2.0.0",
                    params=method_params,
                )
            ],
        ),
    )
    catalog_ref = persist_method_catalog_snapshot(
        store,
        MethodCatalogSnapshot(
            snapshot_id=f"catalog-{run_id}",
            run_id=run_id,
            entries=[
                MethodCatalogEntry(
                    fqn=method_fqn,
                    namespace="polisyos.methods.causal.hte",
                    name="CausalForest",
                    version="2.0.0",
                    backend="python",
                    execution_backend="python",
                    kind="causal",
                    family="hte",
                    variant="causal_forest",
                    fidelity_tier="standard",
                )
            ],
        ),
    )

    subject_ref = _put_selected_ref(
        store,
        name=f"candidate-{run_id}",
        kind="scientist.search.controlled_candidate",
    )
    quantity_ref = _put_selected_ref(
        store,
        name="causal-treatment-effect-contrast",
        kind="scientist.search.controlled_quantity",
    )
    contrast_ref = _put_selected_ref(
        store,
        name="treatment-control-contrast",
        kind="scientist.search.controlled_contrast",
    )
    population_ref = _put_selected_ref(
        store,
        name="selected-evaluation-rows",
        kind="scientist.search.controlled_population",
    )
    outcome_ref = _put_selected_ref(
        store,
        name="employment-outcome",
        kind="scientist.search.controlled_outcome",
    )
    rule_ref = _put_selected_ref(
        store,
        name="selected-rule",
        kind="scientist.search.controlled_rule",
    )
    profile_ref = _put_selected_ref(
        store,
        name="selected-inference-profile",
        kind="scientist.search.controlled_profile",
    )
    procedure_ref = _put_selected_ref(
        store,
        name="selected-procedure",
        kind="scientist.search.controlled_procedure",
    )
    selection_ref = _put_selected_ref(
        store,
        name="selected-policy-selection",
        kind="scientist.search.controlled_selection",
    )

    owner_fqn = (
        "polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine."
        "run_runtime_funnel"
    )
    stage_payload = {
        "owner_fqn": owner_fqn,
        "stages": ({"stage_name": "L0", "fidelity_level": 0},),
        "unresolved_bindings": (),
    }
    stage_digest = _canonical_sha256(stage_payload)
    configuration_ref = persist_search_uncertainty_v2(
        store,
        SearchRuntimeStageConfiguration(
            owner_fqn=owner_fqn,
            stages=stage_payload["stages"],
            unresolved_bindings=(),
            configuration_sha256=stage_digest,
        ),
    )
    selected_state_inputs = (
        SearchInputDependency(role_path="method_catalog_snapshot", ref=catalog_ref),
    )
    scope = SearchUncertaintySemanticScope(
        quantity_ref=quantity_ref,
        treatment_contrast_ref=contrast_ref,
        population_ref=population_ref,
        outcome_ref=outcome_ref,
        unit_binding_status="unknown",
        treatment_variable_id="treatment.policy",
        outcome_variable_id="outcome.effect",
        control_value=0.0,
        treated_value=1.0,
        requested_target_scope="selected_evaluation_rows",
    )
    request_projection = SearchUncertaintyHTERequestProjection(
        estimand="mean_effect_over_selected_x",
        target_scope="selected_evaluation_rows",
        outcome_variable_id=scope.outcome_variable_id,
        treatment_variable_id=scope.treatment_variable_id,
        control_value=scope.control_value,
        treated_value=scope.treated_value,
        alpha=_REQUEST_ALPHA,
        requested_guarantee="backend_conditional_interval",
    )
    source_graph_ref = persist_search_uncertainty_v2(
        store,
        SearchOwnerSelectedSourceGraph(
            roots=(
                SearchInputDependency(role_path="candidate", ref=subject_ref),
                SearchInputDependency(role_path="execution_plan", ref=plan_ref),
                SearchInputDependency(role_path="stage_configuration", ref=configuration_ref),
                SearchInputDependency(role_path="selected_rule", ref=rule_ref),
                SearchInputDependency(role_path="selected_profile", ref=profile_ref),
                SearchInputDependency(role_path="selected_procedure", ref=procedure_ref),
                SearchInputDependency(role_path="policy_selection", ref=selection_ref),
                SearchInputDependency(role_path="selected_method_input", ref=source_ref),
                SearchInputDependency(role_path="quantity", ref=quantity_ref),
                SearchInputDependency(role_path="treatment_contrast", ref=contrast_ref),
                SearchInputDependency(role_path="population", ref=population_ref),
                SearchInputDependency(role_path="outcome", ref=outcome_ref),
                *selected_state_inputs,
            )
        ),
    )
    owner_context = SearchUncertaintyOwnerTaskContext(
        owner_fqn=owner_fqn,
        run_id=run_id,
        subject_ref=subject_ref,
        selected_plan_ref=plan_ref,
        selected_configuration_ref=configuration_ref,
        selected_source_graph_ref=source_graph_ref,
        selected_rule_ref=rule_ref,
        selected_profile_ref=profile_ref,
        selected_procedure_ref=procedure_ref,
        selected_selection_ref=selection_ref,
        selected_method_fqn=method_fqn,
        selected_method_abi_version=registration.signature.version,
        selected_method_abi_digest=registration.signature.abi_digest(),
        selected_method_params_sha256=params_sha256,
        selected_method_params=method_params,
        selected_method_seed=0,
        selected_inference_profile_id=registration.method_profile_id,
        selected_method_input_ref=source_ref,
        selected_method_input_content_sha256=source_ref.artifact_id.hex,
        request_projection=request_projection,
        tenant_id=tenant_id,
        cell_id=cell_id,
        semantic_scope=scope,
        selected_stage_config_sha256=stage_digest,
        selected_state_input_refs=selected_state_inputs,
        status="ready",
    )
    ticket_id = derive_search_uncertainty_ticket_id(run_id, subject_ref)
    state = SearchUncertaintyTicketState(store)
    initial = state.initialize(ticket_id)
    _, _, admission_ref, basis_ref = produce_search_task_admission(
        store,
        owner_context,
        ticket_id=ticket_id,
        ticket_generation=initial.ticket_generation,
        selected_at=datetime(2026, 10, 23, tzinfo=UTC),
    )
    assert basis_ref is not None
    admitted = state.record_task_admission(
        ticket_id=ticket_id,
        expected_generation=initial.ticket_generation,
        expected_projection_revision=initial.projection_revision,
        admission_ref=admission_ref,
    )
    assert admitted.task_admission_ref == admission_ref
    binding_ref = state.publish_task_binding(
        ticket_id,
        expected_generation=admitted.ticket_generation,
        expected_projection_revision=admitted.projection_revision,
    )
    assert binding_ref is not None
    return state, ticket_id, binding_ref


def _request_payload(source_ref: ArtifactRef, binding_ref: ArtifactRef) -> dict[str, object]:
    return {
        "observational_input": {
            "protocol": "method_input_envelope_v1",
            "source_ref": source_ref.model_dump(mode="json"),
            "method": {"fqn": "causal.hte.causal_forest@2.0.0"},
            "hte_request": {
                "schema_version": "polisyos.runtime.observational_hte_request.v2",
                "estimand": "mean_effect_over_selected_x",
                "target_scope": "selected_evaluation_rows",
                "outcome_variable_id": "outcome.effect",
                "treatment_variable_id": "treatment.policy",
                "control_value": 0.0,
                "treated_value": 1.0,
                "alpha": _REQUEST_ALPHA,
                "requested_guarantee": "backend_conditional_interval",
                "search_uncertainty_task_binding_ref": binding_ref.model_dump(mode="json"),
            },
        }
    }


def test_search_post_snapshot_survives_same_generation_worker_admission(
    runtime_api_env: dict[str, Any],
    request: pytest.FixtureRequest,
) -> None:
    """Keep admitted snapshots usable while new POSTs remain current-only."""
    pytest.importorskip("econml")

    from _helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker

    from polisyos.core.artifacts.ownership import ArtifactOwnershipError
    from polisyos.core.contracts.runtime import ObservationalRunIntent
    from polisyos.scientist.compute.runner import MethodExecutionWork
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
        _fixture_bearer,
    )

    tenant_id = runtime_api_env["tenant_a"]
    cas_root = runtime_api_env["cas_root"]
    assert isinstance(tenant_id, str)
    assert isinstance(cas_root, Path)
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=True,
    )
    request.addfinalizer(client.close)
    service = runtime_api_env["app"].state._control_service
    assert service is not None
    client.app.state.runtime_container.control_service = service
    client.app.state._control_service = service
    cell_id = cell.cell_id
    bearer = _fixture_bearer("search-admission-handoff")
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=tenant_id,
            cell_id=cell_id,
            jti="jwt-search-admission-handoff",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": tenant_id,
    }
    store = service._require_search_uncertainty_store()
    run_id = "run-search-admission-" + hashlib.sha256(str(cas_root).encode()).hexdigest()[:12]
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        source_ref = _put_v2_hte_source(
            service._artifact_store,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        from _helpers.runtime_http import _record_fixture_owner

        _record_fixture_owner(
            service._artifact_store,
            source_ref,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        state, ticket_id, binding_ref = _publish_complete_search_task(
            store=store,
            service=service,
            source_ref=source_ref,
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
        )
    stop_embedded_control_worker(service)
    request_payload = _request_payload(source_ref, binding_ref)
    first_response = client.post("/api/v1/control/runs", json=request_payload, headers=headers)
    second_response = client.post("/api/v1/control/runs", json=request_payload, headers=headers)
    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 200, second_response.text
    first_job_id = first_response.json()["job_id"]
    second_job_id = second_response.json()["job_id"]
    assert first_job_id != second_job_id

    wrong_tenant_id = str(runtime_api_env["tenant_b"])
    assert wrong_tenant_id != tenant_id
    first_queued_job = service._control_store.get_job(first_job_id)
    assert first_queued_job is not None
    first_payload_ref = service._require_control_job_payload_ref(first_queued_job)
    with (
        tenant_scope(None, tenant_id=wrong_tenant_id, cell_id=cell_id),
        pytest.raises(ArtifactOwnershipError) as refused,
    ):
        service._load_payload_ref(
            first_payload_ref,
            kind="runtime.control_job_payload.workflow_run",
        )
    assert (
        f"payload is not readable by tenant {wrong_tenant_id}/{cell_id} for read_raw_manifest"
    ) in str(refused.value)

    queued: list[tuple[str, ArtifactRef, ObservationalRunIntent]] = []
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        for job_id in (first_job_id, second_job_id):
            job = service._control_store.get_job(job_id)
            assert job is not None
            payload = service._load_payload_ref(
                service._require_control_job_payload_ref(job),
                kind="runtime.control_job_payload.workflow_run",
            )
            source, intent_ref, selection_digest, intent = (
                service._read_validated_observational_method_job_intent(job=job, payload=payload)
            )
            assert type(intent) is ObservationalRunIntent
            assert intent.schema_version == "polisyos.runtime.observational_run_intent.v3"
            assert intent.search_binding_admission is not None
            assert intent.search_binding_admission.binding_ref == binding_ref
            assert intent.search_binding_admission.selected_method_input_ref == source_ref
            assert intent.selection_digest() == selection_digest
            assert source == source_ref
            queued.append((job_id, intent_ref, intent))

    admitted: list[tuple[str, object]] = []

    def inspect_worker_admission(job: Any) -> None:
        current = service._control_store.current_execution_job_admission()
        with service._install_execution_scope(current.scope):
            payload = service._load_payload_ref(
                service._require_control_job_payload_ref(job),
                kind="runtime.control_job_payload.workflow_run",
            )
            source, intent_ref, _selection_digest, _intent = (
                service._read_validated_observational_method_job_intent(
                    job=job,
                    payload=payload,
                )
            )
            work = MethodExecutionWork(
                job_id=job.job_id,
                run_id=str(job.run_id or ""),
                attempt=job.attempt,
                requested_source_ref=source,
                observational_run_intent_ref=intent_ref,
            )
            admission = service.resolve_method_execution_admission(work=work)
            admitted.append((job.job_id, admission.search_binding_admission))

    assert (
        dispatch_one_control_job(
            store=service._control_store,
            handler=inspect_worker_admission,
            expected_job_id=first_job_id,
        )
        == first_job_id
    )
    assert admitted == [(first_job_id, queued[0][2].search_binding_admission)]

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        row = state._read_row(ticket_id)
        assert row is not None
        selected_projection = state._read_projection_for_row(row)
        assert selected_projection is not None
        advanced = state._publish_locked(
            row,
            expected_generation=row.ticket_generation,
            projection=selected_projection.model_copy(
                update={
                    "limitations": tuple(
                        sorted((*selected_projection.limitations, "same_epoch_owner_advance"))
                    )
                }
            ),
        )
    assert advanced.ticket_generation == queued[0][2].search_binding_admission.ticket_generation
    assert advanced.current_binding_ref is None
    assert binding_ref in advanced.historical_binding_refs

    assert (
        dispatch_one_control_job(
            store=service._control_store,
            handler=inspect_worker_admission,
            expected_job_id=second_job_id,
        )
        == second_job_id
    )
    assert admitted[1] == (second_job_id, queued[1][2].search_binding_admission)
    first_snapshot = queued[0][2].search_binding_admission
    second_snapshot = queued[1][2].search_binding_admission
    assert first_snapshot is not None
    assert second_snapshot is not None
    assert first_snapshot.model_dump(
        mode="json", exclude={"resolved_at"}
    ) == second_snapshot.model_dump(mode="json", exclude={"resolved_at"})

    def persisted_jobs_and_created_events() -> tuple[tuple[str, ...], tuple[str, ...]]:
        job_rows = service._control_store._fetchall(
            "SELECT job_id FROM control_jobs ORDER BY created_at, job_id", ()
        )
        created_rows = service._control_store._fetchall(
            "SELECT job_id FROM control_job_events WHERE event_type = ? ORDER BY job_id, event_id",
            ("job_created",),
        )
        return (
            tuple(str(row["job_id"]) for row in job_rows),
            tuple(str(row["job_id"]) for row in created_rows),
        )

    jobs_before_fresh_post = persisted_jobs_and_created_events()
    assert set(jobs_before_fresh_post[0]) == {first_job_id, second_job_id}
    assert set(jobs_before_fresh_post[1]) == {first_job_id, second_job_id}

    fresh_post_response = client.post("/api/v1/control/runs", json=request_payload, headers=headers)
    assert fresh_post_response.status_code == 422, fresh_post_response.text
    fresh_post_problem = fresh_post_response.json()
    assert fresh_post_problem["status"] == 422
    assert fresh_post_problem["code"] == "search_task_binding_request_not_current"
    assert fresh_post_problem["detail"] == (
        "The Search-owned HTE binding is not current for this exact request and input."
    )
    assert persisted_jobs_and_created_events() == jobs_before_fresh_post


def test_owned_hte_outbox_records_first_assessment_without_authority_promotion(
    runtime_api_env: dict[str, Any],
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A real v2 Runtime completion first assesses the selected basis; replay contests it."""
    pytest.importorskip("econml")

    from _helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker

    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
        _fixture_bearer,
    )

    tenant_id = runtime_api_env["tenant_a"]
    cas_root = runtime_api_env["cas_root"]
    assert isinstance(tenant_id, str)
    assert isinstance(cas_root, Path)
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=True,
    )
    request.addfinalizer(client.close)
    service = runtime_api_env["app"].state._control_service
    assert service is not None
    client.app.state.runtime_container.control_service = service
    client.app.state._control_service = service
    cell_id = cell.cell_id
    bearer = _fixture_bearer("search-ad06-first-assessment")
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=tenant_id,
            cell_id=cell_id,
            jti="jwt-search-ad06-first-assessment",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": tenant_id,
    }
    store = service._require_search_uncertainty_store()
    run_id = "run-search-ad06-" + hashlib.sha256(str(cas_root).encode()).hexdigest()[:12]
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        source_ref = _put_v2_hte_source(
            service._artifact_store,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        from _helpers.runtime_http import _record_fixture_owner

        _record_fixture_owner(
            service._artifact_store,
            source_ref,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        state, ticket_id, binding_ref = _publish_complete_search_task(
            store=store,
            service=service,
            source_ref=source_ref,
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
        )
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        admitted = state.read_current_snapshot(ticket_id)
    assert admitted is not None
    assert admitted.status == "available_as_of_task_epoch"
    assert admitted.projection is not None
    assert admitted.projection.live_currentness_status == "not_established"
    assert admitted.resolved_projection is not None
    assert len(admitted.resolved_projection.selected_unassessed_observations) == 1
    predecessor = admitted.resolved_projection.selected_unassessed_observations[0]
    assert predecessor.observation.state == "unassessed"
    assert (
        predecessor.observation.obligation_id in admitted.projection.active_unknown_obligation_ids
    )
    initial_unknown_obligation_ids = set(admitted.projection.active_unknown_obligation_ids)
    initial_historical_observation_keys = {
        artifact_ref_identity_key(ref) for ref in admitted.projection.historical_observation_refs
    }

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        persisted_binding = load_search_uncertainty_task_binding(store, binding_ref)
    assert persisted_binding.tenant_id == tenant_id
    assert persisted_binding.cell_id == cell_id
    assert persisted_binding.request_projection.alpha == _REQUEST_ALPHA
    assert persisted_binding.selected_method_params["alpha"] == _REQUEST_ALPHA
    request_payload = _request_payload(source_ref, binding_ref)
    observational_input = request_payload["observational_input"]
    assert isinstance(observational_input, dict)
    hte_request = observational_input["hte_request"]
    assert isinstance(hte_request, dict)
    assert hte_request["alpha"] == persisted_binding.request_projection.alpha

    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
    from polisyos.foundry.methods.selection.history import SelectionHistoryStore

    history_path = tmp_path / "selection-history" / "executions.jsonl"
    selection_history = SelectionHistoryStore(persist_path=history_path, auto_persist=True)
    monkeypatch.setattr(
        MethodDispatcher,
        "_instance",
        MethodDispatcher(runtime_history=selection_history),
    )
    stop_embedded_control_worker(service)
    first_response = client.post(
        "/api/v1/control/runs",
        json=request_payload,
        headers=headers,
    )
    second_response = client.post(
        "/api/v1/control/runs",
        json=request_payload,
        headers=headers,
    )
    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 200, second_response.text
    first_accepted = first_response.json()
    second_accepted = second_response.json()
    assert first_accepted["job_id"] != second_accepted["job_id"]

    # Both immutable POST intents carry the actual recomputed owner snapshot before
    # either worker can advance the same-generation Search pointer.
    from polisyos.core.contracts.runtime import ObservationalRunIntent

    queued_intents = []
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        for accepted in (first_accepted, second_accepted):
            queued_job = service._control_store.get_job(accepted["job_id"])
            assert queued_job is not None
            queued_payload = service._load_payload_ref(
                service._require_control_job_payload_ref(queued_job),
                kind="runtime.control_job_payload.workflow_run",
            )
            _, queued_intent_ref, queued_digest, queued_intent = (
                service._read_validated_observational_method_job_intent(
                    job=queued_job,
                    payload=queued_payload,
                )
            )
            assert type(queued_intent) is ObservationalRunIntent
            assert queued_intent.schema_version == "polisyos.runtime.observational_run_intent.v3"
            assert queued_intent.selection_digest() == queued_digest
            assert queued_intent.search_binding_admission is not None
            assert queued_intent.search_binding_admission.binding_ref == binding_ref
            assert queued_intent.search_binding_admission.selected_method_input_ref == source_ref
            assert queued_intent_ref.manifest_profile_sha256 is not None
            queued_intents.append((queued_job.job_id, queued_digest, queued_intent))
    assert queued_intents[0][0] == first_accepted["job_id"]
    assert queued_intents[1][0] == second_accepted["job_id"]

    from polisyos.core.security.tenant_context import (
        get_current_cell_id,
        get_current_tenant_id_or_none,
    )

    snapshots = []
    native_lineage = []
    dispatched_job_ids = []
    job_states = []
    for accepted_index, accepted in enumerate((first_accepted, second_accepted)):
        job_id = accepted["job_id"]
        if accepted_index == 1:
            # Resolve the second, already-admitted POST against the first
            # completion through Runtime's genuine historical owner API.
            second_intent = queued_intents[1][2]
            second_snapshot = second_intent.search_binding_admission
            request_context = second_intent.owned_hte_request_context
            assert second_snapshot is not None
            assert request_context is not None
            assert artifact_ref_identity_key(
                request_context.search_uncertainty_task_binding_ref
            ) == artifact_ref_identity_key(binding_ref)

            resolve_second_admission = partial(
                service._resolve_search_uncertainty_binding,
                binding_ref=binding_ref,
                tenant_id=tenant_id,
                cell_id=cell_id,
                request_context=request_context,
                method_fqn=second_intent.method_fqn,
                method_version=second_intent.method_version,
                method_abi_digest=second_intent.method_abi_digest,
                resolved_params=second_intent.resolved_params,
                seed=second_intent.seed,
                inference_profile_id=second_intent.resource_policy.method_profile_id,
                selected_method_input_ref=second_intent.requested_source_ref,
                selected_method_input_content_sha256=(
                    second_intent.requested_source_ref.artifact_id.hex
                ),
                admitted_snapshot=second_snapshot,
            )

            first_snapshot = snapshots[0]
            assert first_snapshot.resolved_projection is not None
            first_successor = (
                first_snapshot.resolved_projection.current_obligations[0].successors[0].observation
            )
            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                successor_anchor_ref = first_successor.owned_attempt_anchor_ref
                assert type(successor_anchor_ref) is ArtifactRef
                owner_association = service.resolve_owned_attempt_anchor_association(
                    anchor_ref=successor_anchor_ref,
                    expected_job_id=first_successor.job_id,
                    expected_completed_event_id=first_successor.completed_event_id,
                    expected_tenant_id=tenant_id,
                    expected_cell_id=cell_id,
                )
                for invalid_anchor_ref in (
                    successor_anchor_ref.model_copy(update={"kind": "runtime.foreign_anchor"}),
                    successor_anchor_ref.model_copy(update={"media_type": "text/plain"}),
                    successor_anchor_ref.model_copy(update={"manifest_profile_sha256": None}),
                ):
                    with pytest.raises(
                        TypeError, match="method_execution_owned_anchor_ref_invalid"
                    ):
                        service.resolve_owned_attempt_anchor_association(
                            anchor_ref=invalid_anchor_ref,
                            expected_job_id=first_successor.job_id,
                            expected_completed_event_id=first_successor.completed_event_id,
                            expected_tenant_id=tenant_id,
                            expected_cell_id=cell_id,
                        )
                wrong_profile_ref = successor_anchor_ref.model_copy(
                    update={"manifest_profile_sha256": "sha256:" + "e" * 64}
                )
                with pytest.raises((OSError, ValueError)):
                    service.resolve_owned_attempt_anchor_association(
                        anchor_ref=wrong_profile_ref,
                        expected_job_id=first_successor.job_id,
                        expected_completed_event_id=first_successor.completed_event_id,
                        expected_tenant_id=tenant_id,
                        expected_cell_id=cell_id,
                    )
                foreign_anchor_ref = ArtifactRef(
                    artifact_id="sha256:" + "f" * 64,
                    kind=successor_anchor_ref.kind,
                    media_type=successor_anchor_ref.media_type,
                    manifest_profile_sha256=successor_anchor_ref.manifest_profile_sha256,
                )
                with pytest.raises((OSError, TypeError, ValueError)):
                    service.resolve_owned_attempt_anchor_association(
                        anchor_ref=foreign_anchor_ref,
                        expected_job_id=first_successor.job_id,
                        expected_completed_event_id=first_successor.completed_event_id,
                        expected_tenant_id=tenant_id,
                        expected_cell_id=cell_id,
                    )
                assert resolve_second_admission() == second_snapshot

                with monkeypatch.context() as missing_owner:
                    missing_owner.setattr(
                        service,
                        "resolve_owned_attempt_anchor_association",
                        lambda **_kwargs: None,
                    )
                    with pytest.raises(SearchUncertaintyAdmissionError) as missing_association:
                        resolve_second_admission()
                    assert (
                        missing_association.value.reason_code
                        == "runtime_attempt_association_unavailable"
                    )

                mismatched_association = owner_association.model_copy(
                    update={"job_id": "foreign-" + owner_association.job_id}
                )
                with monkeypatch.context() as forged_owner:
                    forged_owner.setattr(
                        service,
                        "resolve_owned_attempt_anchor_association",
                        lambda association=mismatched_association, **_kwargs: association,
                    )
                    with pytest.raises(
                        SearchUncertaintyAdmissionError
                    ) as mismatched_association_error:
                        resolve_second_admission()
                    assert (
                        mismatched_association_error.value.reason_code
                        == "runtime_attempt_association_mismatch"
                    )
                from unittest.mock import Mock

                worker_owner_reader = Mock(wraps=service.resolve_owned_attempt_anchor_association)
                monkeypatch.setattr(
                    service,
                    "resolve_owned_attempt_anchor_association",
                    worker_owner_reader,
                )
        assert (
            dispatch_one_control_job(
                store=service._control_store,
                handler=service._process_control_job,
                expected_job_id=job_id,
            )
            == job_id
        )
        dispatched_job_ids.append(job_id)
        record = service._control_store.get_job(job_id)
        assert record is not None
        job_states.append((job_id, record.state, record.error_message))
        if record.state != "completed":
            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                current = SearchUncertaintyTicketState(
                    store,
                    completion_owner=service,
                ).read_current_snapshot(ticket_id)
            assert current is not None
            snapshots.append(current)
            continue
        if accepted_index == 1:
            assert any(
                call.kwargs.get("expected_job_id") == first_successor.job_id
                and call.kwargs.get("expected_completed_event_id")
                == first_successor.completed_event_id
                and call.kwargs.get("expected_tenant_id") == tenant_id
                and call.kwargs.get("expected_cell_id") == cell_id
                for call in worker_owner_reader.call_args_list
            )
        completed_event = service._control_store.get_job_terminal_source_event_record(job_id)
        assert completed_event.event_type == "job_completed"

        # The native HTE basis binds fit/eval rows by ordered row identity;
        # selected_rows_sha256 separately binds the row content set.
        from polisyos.core.artifacts import ensure_ir_artifact_store
        from polisyos.ir.analytics.hte import load_ate_inference_basis, load_hte_outcome
        from polisyos.ir.registry.refs import ATEInferenceBasisRef, HTEOutcomeRef

        selection = completed_event.payload.get("method_execution_selection")
        assert isinstance(selection, dict)
        selected_hte = selection.get("hte")
        assert isinstance(selected_hte, dict)
        assert selected_hte.get("kind") == "interval_estimate"
        outcome_ref = HTEOutcomeRef.model_validate(selection.get("hte_outcome_ref"), strict=True)
        inference_basis_ref = ATEInferenceBasisRef.model_validate(
            selection.get("inference_basis_ref"), strict=True
        )
        ir_store = ensure_ir_artifact_store(service._artifact_store)
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            outcome = load_hte_outcome(ir_store, outcome_ref).root
            inference_basis = load_ate_inference_basis(ir_store, inference_basis_ref)
        native_lineage.append((job_id, outcome_ref, inference_basis_ref, outcome, inference_basis))
        assert get_current_tenant_id_or_none() is None
        assert get_current_cell_id() is None
        service.reconcile_pending_search_hte_completion_events()
        delivery = service._control_store.get_search_hte_completion_outbox_event(
            job_id=job_id,
            completed_event_id=completed_event.event_id,
        )
        assert delivery is not None
        assert delivery.topic == "control.search.hte_completed"
        assert delivery.state == "published"

        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            current = SearchUncertaintyTicketState(
                store,
                completion_owner=service,
            ).read_current_snapshot(ticket_id)
        assert current is not None
        assert current.status == "available_as_of_task_epoch"
        assert current.projection is not None
        assert current.resolved_projection is not None
        assert current.projection.live_currentness_status == "not_established"
        assert any(
            observation.observation_ref == predecessor.observation_ref
            for observation in current.resolved_projection.selected_unassessed_observations
        )
        snapshots.append(current)

    assert dispatched_job_ids == [first_accepted["job_id"], second_accepted["job_id"]]
    lineage_facts = [
        {
            "job_id": job_id,
            "outcome_ref": outcome_ref.model_dump(mode="json"),
            "inference_basis_ref": inference_basis_ref.model_dump(mode="json"),
            "outcome_rows": {
                "n_selected_rows": outcome.n_selected_rows,
                "selected_rows_sha256": outcome.selected_rows_sha256,
                "selected_row_order_sha256": outcome.selected_row_order_sha256,
            },
            "basis_rows": {
                "n_selected_rows": inference_basis.n_selected_rows,
                "selected_rows_sha256": inference_basis.selected_rows_sha256,
                "selected_row_order_sha256": inference_basis.selected_row_order_sha256,
                "fit_rows_sha256": inference_basis.fit_rows_sha256,
                "eval_rows_sha256": inference_basis.eval_rows_sha256,
                "sample_ids_status": inference_basis.sample_ids_status,
                "sample_ids_sha256": inference_basis.sample_ids_sha256,
                "fit_eval_relation": inference_basis.fit_eval_relation,
            },
        }
        for job_id, outcome_ref, inference_basis_ref, outcome, inference_basis in native_lineage
    ]
    snapshot_facts = [
        {
            "ticket_id": snapshot.ticket_id,
            "ticket_generation": snapshot.ticket_generation,
            "projection_revision": snapshot.projection_revision,
            "status": snapshot.status,
            "admission_status": snapshot.admission_status,
            "reason_code": snapshot.reason_code,
        }
        for snapshot in snapshots
    ]
    assert job_states == [
        (first_accepted["job_id"], "completed", None),
        (second_accepted["job_id"], "completed", None),
    ], (
        f"dispatched_job_ids={dispatched_job_ids!r}; job_states={job_states!r}; "
        f"snapshots={snapshot_facts!r}; native_lineage={lineage_facts!r}"
    )
    assert len(native_lineage) == 2
    for job_id, outcome_ref, inference_basis_ref, outcome, inference_basis in native_lineage:
        assert job_id in dispatched_job_ids
        assert type(outcome_ref) is HTEOutcomeRef
        assert type(inference_basis_ref) is ATEInferenceBasisRef
        assert outcome.kind == "interval_estimate"
        assert inference_basis.fit_eval_relation == "same_selected_rows"
        assert inference_basis.fit_rows_sha256 == outcome.selected_row_order_sha256
        assert inference_basis.eval_rows_sha256 == outcome.selected_row_order_sha256
        assert inference_basis.fit_rows_sha256 != outcome.selected_rows_sha256

    first = snapshots[0]
    assert first.projection is not None and first.resolved_projection is not None
    first_obligation = first.resolved_projection.current_obligations[0]
    assert first_obligation.selection.status == "assessed"
    assert len(first_obligation.successors) == 1
    assert first_obligation.basis_ref == predecessor.observation.basis_ref
    assert set(first.projection.active_unknown_obligation_ids) == (
        initial_unknown_obligation_ids - {predecessor.observation.obligation_id}
    )
    assert initial_historical_observation_keys <= {
        artifact_ref_identity_key(ref) for ref in first.projection.historical_observation_refs
    }
    first_assessment = first_obligation.successors[0].observation
    assert first_assessment.state == "assessed"
    assert first_assessment.outcome_kind == "interval_estimate"
    assert first_assessment.unit_binding_status == "unknown"
    assert first_assessment.source_observation_interval_status == "not_established"
    assert first_assessment.routing_score.status == "unavailable"
    assert first_assessment.routing_score.unavailable_reason == "unit_not_bound"
    assert first_assessment.obligation_id == predecessor.observation.obligation_id
    assert predecessor.observation_ref in first.projection.unassessed_observation_refs
    assert (
        predecessor.observation.obligation_id not in first.projection.active_unknown_obligation_ids
    )
    assert first.projection.historical_observation_refs

    contested = snapshots[1]
    assert contested.projection is not None and contested.resolved_projection is not None
    contested_obligation = contested.resolved_projection.current_obligations[0]
    assert contested_obligation.selection.status == "contested"
    assert len(contested_obligation.successors) == 2
    assert contested.projection.incomplete_obligation_ids == (
        predecessor.observation.obligation_id,
    )
    assert predecessor.observation_ref in contested.projection.unassessed_observation_refs
    assert {
        artifact_ref_identity_key(item.observation_ref) for item in contested_obligation.successors
    }.issubset(
        artifact_ref_identity_key(ref) for ref in contested.projection.historical_observation_refs
    )
    assert contested.projection.live_currentness_status == "not_established"

    assessed_successor = first_obligation.successors[0]
    with (
        tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id),
        pytest.raises(ValidationError),
    ):
        SearchUncertaintyTicketState(
            store,
            completion_owner=service,
        ).record_first_assessment(
            ticket_id=ticket_id,
            expected_generation=first.ticket_generation,
            expected_projection_revision=first.projection_revision,
            predecessor_ref=assessed_successor.observation_ref,
            successor_ref=assessed_successor.observation_ref,
            refinement_ref=assessed_successor.refinement_ref,
            completion_owner=service,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )

    # Keep every source marker and the selected ticket context, but change the
    # actual basis ref on one typed successor. The same-basis property must refuse it.
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        actual_refinement = first_obligation.successors[0].refinement
        alternate_outcome_ref = _put_selected_ref(
            store,
            name="same-run-different-outcome-basis",
            kind="scientist.search.controlled_outcome",
        )
        alternate_basis = first_obligation.basis.model_copy(
            update={"outcome_ref": alternate_outcome_ref}
        )
        alternate_basis_ref = persist_search_uncertainty_v2(store, alternate_basis)
        actual_successor = first_obligation.successors[0].observation
        mismatched_successor = actual_successor.model_copy(
            update={"basis_ref": alternate_basis_ref}
        )
        with pytest.raises(ValueError, match="first-assessment relation refs disagree"):
            _verify_first_assessment_edge(
                ticket_id=ticket_id,
                predecessor_ref=predecessor.observation_ref,
                predecessor=predecessor.observation,
                successor_ref=first_obligation.successors[0].observation_ref,
                successor=mismatched_successor,
                refinement_ref=first_obligation.successors[0].refinement_ref,
                refinement=actual_refinement,
                expected_generation=first.ticket_generation,
            )


def test_selected_optional_hte_ref_comparison_preserves_typed_absence_and_identity() -> None:
    """Only schema-valid absence compares equal; present refs remain profile and kind bound."""
    from polisyos.runtime.http.services.control.run_lifecycle import (
        _same_optional_selected_artifact_ref_for_kind,
    )

    expected = ArtifactRef(
        artifact_id="sha256:" + "1" * 64,
        kind="ir.hte_result",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "2" * 64,
    )
    same = expected.model_copy()
    changed_profile = expected.model_copy(update={"manifest_profile_sha256": "sha256:" + "3" * 64})
    changed_kind = expected.model_copy(update={"kind": "ir.hte_point_result"})

    assert _same_optional_selected_artifact_ref_for_kind(
        None,
        None,
        absence_is_valid_for_selected_kind=True,
    )
    assert not _same_optional_selected_artifact_ref_for_kind(
        None,
        None,
        absence_is_valid_for_selected_kind=False,
    )
    assert not _same_optional_selected_artifact_ref_for_kind(
        None,
        expected,
        absence_is_valid_for_selected_kind=True,
    )
    assert not _same_optional_selected_artifact_ref_for_kind(
        expected,
        None,
        absence_is_valid_for_selected_kind=True,
    )
    assert _same_optional_selected_artifact_ref_for_kind(
        expected,
        same,
        absence_is_valid_for_selected_kind=False,
    )
    assert not _same_optional_selected_artifact_ref_for_kind(
        expected,
        changed_profile,
        absence_is_valid_for_selected_kind=False,
    )
    assert not _same_optional_selected_artifact_ref_for_kind(
        expected,
        changed_kind,
        absence_is_valid_for_selected_kind=False,
    )


def test_search_hte_completion_backend_refusal_stays_pending_for_unknown_stores() -> None:
    """Unsupported and self-labeled stores retain the typed pending refusal."""
    from typing import cast

    from polisyos.core.artifacts.backends.s3_store import S3ArtifactStore
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.contracts.runtime import RuntimeSearchHTECompletionDeliveryV1
    from polisyos.runtime.http.services.control.run_lifecycle import (
        ControlPlaneService,
        _injected_artifact_store_backend,
    )
    from polisyos.runtime.http.services.control_plane_store import (
        ControlOutboxRecord,
        ControlPlaneStore,
    )

    class FailureRecorder:
        def __init__(self) -> None:
            self.failures: list[tuple[str, str]] = []

        def record_outbox_delivery_failure(self, *, event_id: str, reason_code: str) -> None:
            self.failures.append((event_id, reason_code))

    class ClaimedFilesystemStore:
        backend = "filesystem"

    binding_ref = ArtifactRef(
        artifact_id="sha256:" + "1" * 64,
        kind="scientist.search.uncertainty_task_binding",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "2" * 64,
    )
    job_id = "job-unknown-search-hte-backend"
    completed_event_id = 1
    payload = RuntimeSearchHTECompletionDeliveryV1(
        job_id=job_id,
        run_id="run-unknown-search-hte-backend",
        attempt=1,
        completed_event_id=completed_event_id,
        completed_event_payload_sha256="sha256:" + "3" * 64,
        search_uncertainty_task_binding_ref=binding_ref,
    ).model_dump(mode="json")
    delivery = ControlOutboxRecord(
        event_id="outbox-unknown-search-hte-backend",
        topic="control.search.hte_completed",
        event_key=f"{job_id}:job_completed:{completed_event_id}",
        state="pending",
        job_id=job_id,
        run_id="run-unknown-search-hte-backend",
        payload=payload,
        created_at=datetime.now(UTC),
        published_at=None,
        attempt=0,
        error_message=None,
    )

    unsupported_stores = (
        cast("ArtifactStore", S3ArtifactStore(bucket="fixture-only")),
        cast("ArtifactStore", ClaimedFilesystemStore()),
        cast("ArtifactStore", object()),
    )
    for store in unsupported_stores:
        backend, verifier = _injected_artifact_store_backend(
            artifact_store=store,
            signature_verifier=None,
        )
        assert backend is None
        assert verifier is None
        recorder = FailureRecorder()
        service = object.__new__(ControlPlaneService)
        service._artifact_store_backend = backend
        service._control_store = cast("ControlPlaneStore", recorder)
        assert service._deliver_search_hte_completion_outbox(delivery) is False
        assert recorder.failures == [(delivery.event_id, "search_hte_backend_not_established")]
