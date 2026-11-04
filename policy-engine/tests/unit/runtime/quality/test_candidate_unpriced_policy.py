"""Actual selected policy/event and resource-owner checks, with component source refs.

The four parent CAS payloads are typed test fixtures, not a verified N7 cycle.
This does not prove a protected action, source rights, an external tariff, or a
live fetch. The route consumer must independently replay those real owners.
"""

from __future__ import annotations

import hashlib
import socket
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core import artifacts
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.fabric.data_plane import build_live_execution_authorization
from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
from polisyos.runtime.http.services.control_registry_providers import (
    resolve_control_registry_providers,
)
from polisyos.runtime.quality import acquisition_executor
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRoutePhaseReceipt
from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
    POLICY_KIND,
    POLICY_PRODUCER,
    POLICY_SCHEMA,
    CandidateUnpricedLiveContext,
    CandidateUnpricedPolicyBinding,
    CandidateUnpricedPolicyScope,
    issue_candidate_unpriced_policy,
    persist_candidate_unpriced_policy,
    read_candidate_unpriced_policy,
    reconcile_candidate_unpriced_work,
    resolve_current_candidate_unpriced_policy,
)
from polisyos.runtime.quality.agent_action_authority import agent_action_content_hash
from polisyos.scientist.orchestration.engine import ProducerBudgetSourceError
from tests._helpers.lane01_wdi_profiles import UNEMPLOYMENT_PROFILE, build_fixture_wdi_authority
from tests._helpers.runtime_http import _build_control_service
from tests.unit.fabric.data_plane.test_evidence_journal import (
    _authorization_request,
    _harness_receipt,
    _source_profile,
)
from tests.unit.runtime.quality.test_lane01_wdi_transport import _constraints
from tests.unit.scientist.orchestration.engine.test_invocation_capacity_observation import _owner
from tests.unit.scientist.orchestration.engine.test_producer_budget_c49 import _settle


def _live_authorization():
    request = _authorization_request()
    return build_live_execution_authorization(
        attempt_id="n13b-worldbank-cpi-001",
        connector_id="worldbank.wdi",
        request_dataset_id="FP.CPI.TOTL",
        request=request,
        schema_contract=request["schema_contract"],
        source_profile=_source_profile(),
        baseline_sha256="sha256:" + "f" * 64,
        family_receipt=_harness_receipt(),
        max_response_bytes=65_536,
        max_decompressed_bytes=65_536,
    )


def _parent(cas: artifacts.FileSystemCAS, kind: str, label: str) -> artifacts.ArtifactRef:
    return cas.put_json(
        {"component_input": label, "real_route_not_established": True},
        artifacts.ArtifactWriteOptions(kind=kind, media_type="application/json"),
        return_selected_profile=True,
    )


def _component_policy(cas: artifacts.FileSystemCAS, profile, authorization=None):
    """Build selected component parents and a real owner-derived HTTP authorization."""
    authorization = authorization or _live_authorization()
    planner = _parent(cas, "runtime.acquisition_planner_report", "planner")
    scope = CandidateUnpricedPolicyScope(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="job-run-a",
        design_problem_ref="sha256:" + "1" * 64,
        design_problem_basis_ref="sha256:" + "2" * 64,
        source_cycle_index=0,
        candidate_id="candidate-component",
        candidate_content_hash="sha256:" + "3" * 64,
        requirement_id="requirement-component",
        compiled_requirement_ref="compiled-requirement-component",
        candidate_digest="sha256:" + "4" * 64,
        planner_report_hash=agent_action_content_hash(
            artifacts.load_core_json_artifact(cas, planner)
        ),
        compiled_ref=_parent(cas, "runtime.compiled_recursive_generation_cycle", "compiled"),
        planner_report_ref=planner,
        compiler_report_ref=_parent(cas, "runtime.data_requirement_compilation_report", "compiler"),
        configured_port_source_ref=_parent(
            cas, "runtime.quality.n7_configured_candidate_port_source", "ports"
        ),
    )
    policy = issue_candidate_unpriced_policy(
        scope=scope,
        live_authorization=authorization,
        n5_quota_profile=profile,
        limitations=(
            "acquisition_monetary_cost_not_established",
            "n5_monetary_cost_not_established",
            "per_call_usd_reservation_not_established",
            "candidate_only_no_publication_authority",
        ),
    )
    return scope, policy, authorization


def _job(control, job_id: str = "job-action-a"):
    scope = {
        "schema_version": "polisyos.runtime.control_execution_scope.v1",
        "status": "established",
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "actor_subject": "configured-operator",
        "actor_authenticated": True,
        "actor_roles": ["operator"],
    }
    creation = {
        "job_id": job_id,
        "run_id": "run-a",
        "job_kind": "acquisition",
        "pipeline_id": None,
        "payload_ref": None,
        "submitted_by": "configured-operator",
        "requested_execution_profile": None,
        "effective_execution_profile": "dev",
        "policy_flags": {"candidate": True},
        "capability_manifest_ref": None,
        "execution_scope": scope,
    }
    return control.create_job(
        job_id=job_id,
        kind="acquisition",
        run_id="run-a",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={"candidate": True},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="configured-operator",
        creation_event_payload=creation,
    )


def test_selected_unpriced_policy_requires_real_config_and_resource_owners(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No server selection, changed Fabric request or exhausted quota is permission."""
    cas = artifacts.FileSystemCAS(tmp_path / "cas")
    base = _build_control_service(tmp_path / "control", artifact_store=cas)
    ledger, middleware, observer = _owner(tmp_path / "quota-ledger.json", total=2, protected=1)
    profile = observer.invocation_quota_profile
    assert profile is not None
    with pytest.raises(
        ProducerBudgetSourceError, match="control_nl_budget_producer_events_not_established"
    ):
        observer.admit()
    assert observer.last_checked is None
    # The quota-only helper has no producer settlement. Record an explicit
    # component-fixture paid event through the real owner; this is not an N5
    # or acquisition price and does not establish a real source-run budget.
    _settle(middleware, profile.run_binding, "fixture-paid-producer", "0.20")
    authority, entry = build_fixture_wdi_authority(tmp_path / "source", UNEMPLOYMENT_PROFILE)
    providers_source = resolve_control_registry_providers()
    resolved = authority.resolve(entry.entry_id)
    constraints = _constraints(UNEMPLOYMENT_PROFILE)
    source_profile = providers_source.source_profiles.get(resolved.registration.source_profile_id)
    assert source_profile is not None
    request = acquisition_executor._live_request_projection(resolved, constraints=constraints)
    harness = authority.resolve_live_harness_receipt(entry.entry_id, "lane01-fixture-wdi-001")
    authorization = build_live_execution_authorization(
        attempt_id="lane01-fixture-wdi-001",
        connector_id=resolved.registration.connector_id,
        request_dataset_id=resolved.registration.request_dataset_id,
        request=request,
        schema_contract=entry.schema_projection(),
        source_profile=source_profile,
        baseline_sha256=resolved.baseline_content_sha256,
        family_receipt=harness.family_receipt,
        timeout_cap_seconds=constraints.timeout_cap_seconds,
        heartbeat_cap_seconds=constraints.heartbeat_cap_seconds,
        max_response_bytes=constraints.max_response_bytes,
        max_decompressed_bytes=constraints.max_decompressed_bytes,
    )
    bound: ControlPlaneService | None = None
    try:
        with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
            scope, policy, authorization = _component_policy(cas, profile, authorization)
            ref = persist_candidate_unpriced_policy(
                store=cas, event_log=base._diagnostic_event_log, policy=policy
            )
            assert (
                read_candidate_unpriced_policy(
                    store=cas, event_log=base._diagnostic_event_log, ref=ref
                )
                == policy
            )
            with pytest.raises(ValueError, match="candidate_unpriced_policy_not_selected"):
                resolve_current_candidate_unpriced_policy(control_service=base, scope=scope)

            providers = replace(
                providers_source,
                candidate_unpriced_policy_bindings=(
                    CandidateUnpricedPolicyBinding(scope=scope, policy_ref=ref),
                ),
            )
            bound = ControlPlaneService(
                cas_root=tmp_path / "cas",
                core_runs_root=tmp_path / "control" / "runs",
                artifact_store=cas,
                control_store=base._control_store,
                registry_providers=providers,
                policy_resolver=base._policy_resolver,
            )
            selected, reopened = resolve_current_candidate_unpriced_policy(
                control_service=bound, scope=scope
            )
            assert selected == ref and reopened == policy
            assert policy.monetary_cost == "not_established"
            assert policy.hard_usd_reservation is False

            foreign_scope = scope.model_copy(update={"candidate_id": "different-candidate"})
            with pytest.raises(ValueError, match="candidate_unpriced_policy_not_selected"):
                resolve_current_candidate_unpriced_policy(
                    control_service=bound, scope=foreign_scope
                )

            manifest = cas.get_manifest(ref)
            foreign = cas.put_bytes(
                cas.get_bytes(ref),
                artifacts.ArtifactWriteOptions(
                    kind=POLICY_KIND,
                    media_type="application/json",
                    schema=artifacts.SchemaInfo(name=POLICY_SCHEMA, version="1.0"),
                    producer=artifacts.ProducerInfo(component="foreign.test.policy", version="1"),
                    canon=manifest.canon,
                    inputs=manifest.inputs,
                    governance=manifest.governance,
                    tenant_context=manifest.tenant_context,
                ),
                return_selected_profile=True,
            )
            assert foreign.artifact_id == ref.artifact_id
            assert foreign.manifest_profile_sha256 != ref.manifest_profile_sha256
            with pytest.raises(ValueError, match="candidate_unpriced_policy_owner_mismatch"):
                read_candidate_unpriced_policy(
                    store=cas, event_log=base._diagnostic_event_log, ref=foreign
                )
            assert cas.get_manifest(ref).producer.component == POLICY_PRODUCER

            # Remove a real selected source view while preserving its bytes and
            # restore it regardless of the refusal outcome.
            missing = scope.compiler_report_ref
            manifest_path = cas._manifest_path_for_ref(
                missing.artifact_id, missing.manifest_profile_sha256
            )
            held = manifest_path.with_name(manifest_path.name + ".held")
            manifest_path.rename(held)
            try:
                cold = artifacts.FileSystemCAS.open_existing_read_only(cas.root)
                with pytest.raises((FileNotFoundError, ValueError)):
                    read_candidate_unpriced_policy(
                        store=cold, event_log=base._diagnostic_event_log, ref=ref
                    )
            finally:
                held.rename(manifest_path)
            assert (
                read_candidate_unpriced_policy(
                    store=cas, event_log=base._diagnostic_event_log, ref=ref
                )
                == policy
            )

            _job(base._control_store)
            lease = base._control_store.lease_next_job(
                worker_id="candidate-worker", lease_seconds=30
            )
            assert lease is not None
            with base._control_store.job_execution_fence(
                job_id="job-action-a", worker_id="candidate-worker", attempt=lease.attempt
            ):
                requested = AcquisitionRoutePhaseReceipt(
                    receipt_id="component-requested",
                    tenant_id=scope.tenant_id,
                    cell_id=scope.cell_id,
                    run_id=scope.run_id,
                    source_job_id=scope.source_job_id,
                    route_id="sha256:" + "9" * 64,
                    action_generation=1,
                    job_id="job-action-a",
                    compiled_ref=str(scope.compiled_ref.artifact_id),
                    planner_report_hash=scope.planner_report_hash,
                    cost_basis_hash="sha256:" + "a" * 64,
                    decision_ref="sha256:" + "b" * 64,
                    coarse_phase="requested",
                    receipt_phase="requested",
                    recovery_state="none",
                    predecessor_receipt_ref=None,
                    generated_at=datetime.now(UTC),
                )
                requested_head = bound.acquisition_route_sink.persist_phase(requested)
                executing = requested.model_copy(
                    update={
                        "receipt_id": "component-executing",
                        "coarse_phase": "executing",
                        "receipt_phase": "executing",
                        "predecessor_receipt_ref": requested_head.receipt_ref,
                    }
                )
                executing_head = bound.acquisition_route_sink.persist_phase(executing)
                before = ledger.snapshot()
                budget, capacity = reconcile_candidate_unpriced_work(
                    control_service=bound,
                    scope=scope,
                    policy_ref=ref,
                    action_phase_ref=executing_head.receipt_ref,
                    live_authorization=authorization,
                    budget_observer=observer,
                    budget_state=observer._state,
                )
                assert capacity.status == "available" and capacity.not_a_permit is True
                assert capacity.standard_remaining_units == 1
                assert budget.run_binding == profile.run_binding
                assert ledger.snapshot() == before
                context = CandidateUnpricedLiveContext(
                    control_service=bound,
                    scope=scope,
                    policy_ref=ref,
                    action_phase_ref=executing_head.receipt_ref,
                    budget_observer=observer,
                    budget_state=observer._state,
                )

                def forbid_socket(*_args: object, **_kwargs: object) -> None:
                    pytest.fail("unpriced candidate refusal reached network transport")

                monkeypatch.setattr(socket.socket, "connect", forbid_socket)
                monkeypatch.setattr(socket.socket, "connect_ex", forbid_socket)
                journal = tmp_path / "unpriced-refused-journal.jsonl"
                with pytest.raises(
                    acquisition_executor.LiveAcquisitionExecutionError,
                    match="candidate_unpriced_budget_scope_not_established",
                ):
                    acquisition_executor.execute_live_catalog_acquisition(
                        authority=authority,
                        entry_id=entry.entry_id,
                        attempt_id="lane01-fixture-wdi-001",
                        constraints=constraints,
                        journal_path=journal,
                        cas_root=tmp_path / "cas",
                        artifact_store=cas,
                        registry_providers=providers,
                        candidate_unpriced_context=context,
                    )
                assert not journal.exists()
                forged = authorization.model_copy(update={"request_sha256": "sha256:" + "a" * 64})
                with pytest.raises(
                    ValueError, match="candidate_unpriced_policy_live_owner_mismatch"
                ):
                    reconcile_candidate_unpriced_work(
                        control_service=bound,
                        scope=scope,
                        policy_ref=ref,
                        action_phase_ref=executing_head.receipt_ref,
                        live_authorization=forged,
                        budget_observer=observer,
                        budget_state=observer._state,
                    )
                operation = hashlib.sha256(b"candidate-policy-quota").hexdigest()
                request_digest = hashlib.sha256(b"candidate-policy-request").hexdigest()
                reservation = observer.reserve_invocation(operation, request_digest)
                assert reservation is not None
                observer.finish_invocation(operation, request_digest, "completed")
                with pytest.raises(
                    ValueError, match="candidate_unpriced_policy_n5_capacity_not_established"
                ):
                    reconcile_candidate_unpriced_work(
                        control_service=bound,
                        scope=scope,
                        policy_ref=ref,
                        action_phase_ref=executing_head.receipt_ref,
                        live_authorization=authorization,
                        budget_observer=observer,
                        budget_state=observer._state,
                    )
            # A separately leased acquisition job in the same run/cell cannot
            # borrow the first job's actual owner-persisted executing phase.
            _job(base._control_store, "job-action-b")
            foreign_lease = base._control_store.lease_next_job(
                worker_id="foreign-candidate-worker", lease_seconds=30
            )
            assert foreign_lease is not None and foreign_lease.job_id == "job-action-b"
            with (
                base._control_store.job_execution_fence(
                    job_id="job-action-b",
                    worker_id="foreign-candidate-worker",
                    attempt=foreign_lease.attempt,
                ),
                pytest.raises(ValueError, match="candidate_unpriced_policy_action_scope_mismatch"),
            ):
                reconcile_candidate_unpriced_work(
                    control_service=bound,
                    scope=scope,
                    policy_ref=ref,
                    action_phase_ref=executing_head.receipt_ref,
                    live_authorization=authorization,
                    budget_observer=observer,
                    budget_state=observer._state,
                )
    finally:
        if bound is not None:
            bound.close()
        base.close()
