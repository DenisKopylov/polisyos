"""Crash recovery through the real served candidate experiment route."""

from __future__ import annotations

import copy
import hashlib
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

pytest_plugins = ("tests._helpers.acquisition_served_history",)


@pytest.mark.integration
def test_candidate_bridge_uses_selected_catalog_root_not_issuer_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bind the real served bridge to its runtime Catalog while retaining issuer ownership."""
    from fastapi.testclient import TestClient

    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.quality.substrate_registry import (
        SubstrateRegistryError,
        catalog_serving_source_scope,
        require_catalog_source_registry_binding,
    )
    from tests._helpers.candidate_experiment_served_execution import (
        _build_candidate_experiment_world_growth_bridge,
    )
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
        candidate_cycle_catalog_registry_providers,
        complete_candidate_cycle_catalog_source,
    )
    from tests._helpers.lane01_candidate_action_served import (
        build_candidate_experiment_issuer_port,
    )

    source_inputs = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "labor-source", include_owner_slot_manifest=True
    )
    cas_root = tmp_path / "cas"
    sqlite_path = tmp_path / "control.sqlite3"
    for name, value in (
        ("POLISYOS_EXECUTION_PROFILE", "dev"),
        ("POLISYOS_CONTROL_WORKER_BACKEND", "external"),
        ("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite"),
        ("POLISYOS_CONTROL_SQLITE_PATH", str(sqlite_path)),
        ("POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS", "3"),
    ):
        monkeypatch.setenv(name, value)

    with complete_candidate_cycle_catalog_source(
        source_inputs.root,
        monkeypatch,
        synthetic_usa_labor_scope=True,
    ) as (selection, selected_source, substrate_registry):
        with candidate_cycle_catalog_registry_providers(
            selection, selected_source
        ) as providers:
            app = create_runtime_api_app(
                cas_root=cas_root,
                core_runs_root=cas_root / "runs",
                enable_security_middlewares=False,
                enable_csrf_protection=False,
                container_overrides=RuntimeContainerOverrides(
                    control_registry_providers=providers
                ),
                repo_root=source_inputs.root,
                catalog_source_selection=selection,
                catalog_run_profile=selection.catalog_run_profile,
            )
            with TestClient(app) as client:
                control = client.app.state._control_service
                issuer = build_candidate_experiment_issuer_port(
                    tmp_path=tmp_path / "candidate-issuer",
                    artifact_store=control._artifact_store,
                )
                bridge = _build_candidate_experiment_world_growth_bridge(
                    control_service=control,
                    authority=issuer.authority,
                )
                catalog = control.catalog_serving_source

                assert catalog is not None
                assert catalog.repo_root == source_inputs.root
                assert bridge.repo_root == catalog.repo_root
                assert bridge.authority is issuer.authority
                assert issuer.authority.repo_root != catalog.repo_root

                with catalog_serving_source_scope(catalog):
                    require_catalog_source_registry_binding(
                        bridge.repo_root,
                        substrate_registry,
                        catalog,
                    )
                    with pytest.raises(
                        SubstrateRegistryError,
                        match="catalog_source_repo_root_mismatch",
                    ):
                        require_catalog_source_registry_binding(
                            issuer.authority.repo_root,
                            substrate_registry,
                            catalog,
                        )


@pytest.mark.integration
def test_candidate_execution_port_factory_reopens_service_without_n5(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh actual action service delegates to its native no-port dev profile."""
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from polisyos.fabric.connectors.profiles import SourceProfileRegistry
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.services import acquisition_surface_execution
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        CandidateUnpricedExperimentPolicyTemplate,
    )
    from tests._helpers import acquisition_served_history as served
    from tests._helpers.candidate_experiment_served_execution import (
        _candidate_experiment_fresh_registry_providers,
        bind_candidate_test_execution_port_factory,
    )
    from tests._helpers.lane01_candidate_action_served import build_candidate_experiment_issuer_port

    cas_root = tmp_path / "cas"
    sqlite_path = tmp_path / "control.sqlite3"
    for name, value in (
        ("POLISYOS_EXECUTION_PROFILE", "dev"),
        ("POLISYOS_CONTROL_WORKER_BACKEND", "external"),
        ("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite"),
        ("POLISYOS_CONTROL_SQLITE_PATH", str(sqlite_path)),
        ("POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS", "3"),
    ):
        monkeypatch.setenv(name, value)

    def app(*, providers=None):
        return create_runtime_api_app(
            cas_root=cas_root,
            core_runs_root=cas_root / "runs",
            enable_security_middlewares=False,
            enable_csrf_protection=False,
            repo_root=Path.cwd(),
            container_overrides=(
                RuntimeContainerOverrides(control_registry_providers=providers)
                if providers is not None
                else None
            ),
        )

    with TestClient(app()) as original_client:
        original_control = original_client.app.state._control_service
        issuer = build_candidate_experiment_issuer_port(
            tmp_path=tmp_path / "original-issuer",
            artifact_store=original_control._artifact_store,
        )
        original_port = issuer.port
        source_profiles = SourceProfileRegistry.get_instance()
        source_profile_payload = tuple(
            profile.model_dump(mode="json") for profile in source_profiles.snapshot_all()
        )
        assert any(profile["profile_id"] == "worldbank_wdi" for profile in source_profile_payload)
        attempt_id = original_port._provision.live_harness_receipts[0].attempt_id
        template = CandidateUnpricedExperimentPolicyTemplate(
            tenant_id=served.TENANT,
            cell_id=served.CELL,
            authority_entry_id=issuer.entry.entry_id,
            authority_registry_sha256=issuer.registry.content_sha256,
            authority_provision_sha256=issuer.authority.provision_content_sha256,
            attempt_id=attempt_id,
            max_http_response_bytes=65_536,
            max_http_decompressed_bytes=65_536,
            max_http_timeout_seconds=15.0,
            max_standard_n5_invocations=1,
            max_metered_reentry_usd=Decimal("1.00"),
        )
        original_control._registry_providers = replace(
            original_control._registry_providers,
            source_profiles=source_profiles,
            candidate_unpriced_policy_bindings=(),
            candidate_unpriced_policy_templates=(template,),
        )
        bind_candidate_test_execution_port_factory(
            monkeypatch=monkeypatch,
            control_service=original_control,
            fixture_port=original_port,
        )
        assert (
            acquisition_surface_execution.build_production_world_bank_wdi_execution_port(
                control_service=original_control,
                world_growth_config=None,
                epoch_deployment=None,
            )
            is original_port
        )

        fresh_providers = _candidate_experiment_fresh_registry_providers(original_control)
        assert fresh_providers.source_profiles is source_profiles
        assert (
            tuple(
                profile.model_dump(mode="json")
                for profile in fresh_providers.source_profiles.snapshot_all()
            )
            == source_profile_payload
        )
        assert fresh_providers.candidate_unpriced_policy_templates == (template,)
        assert fresh_providers.candidate_unpriced_policy_templates is (
            original_control._registry_providers.candidate_unpriced_policy_templates
        )
        with TestClient(app(providers=fresh_providers)) as fresh_client:
            fresh_control = fresh_client.app.state._control_service
            fresh_action_service = fresh_client.app.state._acquisition_action_service
            assert fresh_control is not original_control
            assert fresh_control._artifact_store is not original_control._artifact_store
            assert fresh_control._control_store is not original_control._control_store
            assert fresh_control._diagnostic_event_log is not original_control._diagnostic_event_log
            assert fresh_control._resolve_control_sqlite_path() == sqlite_path
            assert fresh_control._registry_providers is fresh_providers
            assert fresh_control._registry_providers.source_profiles is source_profiles
            assert fresh_control._registry_providers.candidate_unpriced_policy_templates == (
                template,
            )
            assert fresh_action_service.control_service is fresh_control
            assert fresh_action_service._execution_port is None
            assert fresh_action_service._production_execution_port is None
            assert (
                acquisition_surface_execution.build_production_world_bank_wdi_execution_port(
                    control_service=fresh_control,
                    world_growth_config=None,
                    epoch_deployment=None,
                )
                is None
            )


@pytest.mark.parametrize(
    "block_b_implementation_observation",
    [False, True],
    ids=("evaluated", "blocked-reuse"),
)
def test_candidate_terminal_cas_crash_reuses_timestamp_and_n5(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway,
    block_b_implementation_observation: bool,
) -> None:
    """A writer crash reuses terminal CAS without N5, including blocked B reuse."""
    from polisyos.core import canon
    from polisyos.runtime.http.services.control import run_lifecycle
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceipt,
    )
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        read_candidate_unpriced_policy,
        resolve_current_candidate_unpriced_policy,
    )
    from polisyos.runtime.quality.candidate_experiment_policy_issuer import (
        prepare_candidate_experiment_policies_for_completed_job,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController
    from polisyos.runtime.quality.n5_execution_basis import (
        N5ExecutionImplementationWitness,
        N5ImplementationCapture,
        exact_n5_content_bytes,
    )
    from polisyos.scientist.orchestration.engine import BudgetInvocationQuotaPolicy
    from tests._helpers import acquisition_served_history as served
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
        complete_candidate_cycle_catalog_source,
    )
    from tests._helpers.candidate_experiment_served_execution import (
        _candidate_experiment_reopened_runtime,
        _experiment_outcomes,
        _standard_invocation_units,
        bind_candidate_test_execution_port_factory,
        candidate_experiment_served_execution_owner,
        run_candidate_experiment_served_execution,
    )
    from tests.integration.core_runtime.test_candidate_experiment_action_served import (
        _assert_candidate_experiment_n5_uses_current_wmr,
        _candidate_experiment_policy_owner,
        run_candidate_experiment_action_oracle,
    )

    monkeypatch.setenv("POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS", "3")
    source = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "labor-source", include_owner_slot_manifest=True
    )
    quota = BudgetInvocationQuotaPolicy(
        allocation_id="served-labor-candidate-experiment-recovery",
        total_units=5,
        protected_units=1,
    )
    crash: dict[str, object] = {"writer_calls": 0, "interrupted": False}
    observed: dict[str, object] = {}
    implementation_observation: dict[str, object] = {
        "captures": [],
        "calls": {},
        "blocked_calls": 0,
        "reason": "canonical_loaded_runtime_mismatch",
        "detail": "test-owned bounded source qualification refusal: "
        "polisyos.runtime.quality.confidence_ledger",
    }

    def serve_action(**values) -> None:
        control = values["control"]
        run_id = str(values["run_id"])
        assert values["job"].kind == "natural_language_run"
        assert values["job"].state == "completed"
        policy_owner = _candidate_experiment_policy_owner(
            control=control,
            fixture_root=tmp_path / "candidate-issuer",
            run_id=run_id,
        )
        issuer, template = policy_owner.issuer, policy_owner.template
        original_providers = control._registry_providers
        control._registry_providers = replace(
            original_providers,
            source_profiles=policy_owner.source_profiles,
            candidate_unpriced_policy_bindings=(),
            candidate_unpriced_policy_templates=(template,),
        )
        try:
            bind_candidate_test_execution_port_factory(
                monkeypatch=monkeypatch,
                control_service=control,
                fixture_port=issuer.port,
            )
            refs = prepare_candidate_experiment_policies_for_completed_job(
                control_service=control,
                source_job_id=values["job"].job_id,
            )
            assert len(refs) == 1
            policy_ref, policy = resolve_current_candidate_unpriced_policy(
                control_service=control,
                scope=read_candidate_unpriced_policy(
                    store=control._artifact_store,
                    event_log=control._diagnostic_event_log,
                    ref=refs[0],
                ).scope,
            )
            assert policy.observed_admission is False
            assert policy.publication_authority is False
            assert policy.information_value == policy.monetary_cost == "not_established"
            assert policy.purpose == "bounded_candidate_experiment_voi_unknown"

            with _candidate_experiment_reopened_runtime(
                control=control,
                trust=values["trust"],
                monkeypatch=monkeypatch,
            ) as (preflight_client, preflight_control, _sqlite_path, _cas_root):
                preflight_action_service = preflight_client.app.state._acquisition_action_service
                if (
                    preflight_action_service is None
                    or preflight_action_service.control_service is not preflight_control
                ):
                    raise AssertionError(
                        "candidate experiment no-N5 preflight missed fresh actual action service"
                    )
                if (
                    preflight_action_service._execution_port is not None
                    or preflight_action_service._production_execution_port is not None
                ):
                    raise AssertionError(
                        "candidate experiment fresh dev service reused a prior execution port"
                    )
                preflight_policy_owner = _candidate_experiment_policy_owner(
                    control=preflight_control,
                    fixture_root=tmp_path / "candidate-issuer",
                    run_id=run_id,
                )
                if preflight_policy_owner.template != template:
                    raise AssertionError(
                        "candidate experiment no-N5 preflight changed selected policy config"
                    )
                preflight_control._registry_providers = replace(
                    preflight_control._registry_providers,
                    source_profiles=preflight_policy_owner.source_profiles,
                    candidate_unpriced_policy_bindings=(),
                    candidate_unpriced_policy_templates=(preflight_policy_owner.template,),
                )
                preflight_origin = preflight_action_service._resolve_candidate_experiment_origin(
                    tenant_id=served.TENANT,
                    cell_id=served.CELL,
                    run_id=run_id,
                )
                with candidate_experiment_served_execution_owner(
                    action_service=preflight_action_service,
                    origin=preflight_origin,
                    policy_owner=preflight_policy_owner,
                    monkeypatch=monkeypatch,
                ) as preflight_owner:
                    if (
                        preflight_action_service._execution_port is not preflight_owner.port
                        or preflight_owner.port is issuer.port
                        or preflight_owner.port._artifact_store
                        is not preflight_control._artifact_store
                        or preflight_owner.port._artifact_store is control._artifact_store
                        or preflight_owner.transport_calls
                    ):
                        raise AssertionError(
                            "candidate experiment no-N5 preflight did not bind its fresh owner"
                        )

            def arm_terminal_writer_crash(_execution_owner, job_id: str) -> None:
                if block_b_implementation_observation:
                    original_current = N5ImplementationCapture._current_implementation

                    def observe_n5_implementation(capture):
                        captures = implementation_observation["captures"]
                        calls = implementation_observation["calls"]
                        assert isinstance(captures, list) and isinstance(calls, dict)
                        if not any(existing is capture for existing in captures):
                            captures.append(capture)
                        call_count = int(calls.get(id(capture), 0))
                        # The hook is armed after A is complete. Capture only
                        # B, and refuse its seal-time source observation after
                        # the real N5, trajectories and configuration reads.
                        handoff = (
                            None
                            if capture._admission is None
                            else capture._admission.port._candidate_simulation_handoff
                        )
                        if (
                            handoff is not None
                            and handoff.job_id == job_id
                            and capture._trajectory_bytes is not None
                            and capture._trajectory_hash is not None
                            and capture._sealed is None
                            and call_count == 1
                        ):
                            implementation_observation["blocked_calls"] = (
                                int(implementation_observation["blocked_calls"]) + 1
                            )
                            from polisyos.runtime.quality.confidence_ledger import (
                                ConfidenceLedgerError,
                            )

                            raise ConfidenceLedgerError(
                                str(implementation_observation["reason"]),
                                str(implementation_observation["detail"]),
                            )
                        result = original_current(capture)
                        calls[id(capture)] = call_count + 1
                        return result

                    monkeypatch.setattr(
                        N5ImplementationCapture,
                        "_current_implementation",
                        observe_n5_implementation,
                    )
                original_writer = run_lifecycle.write_runtime_authority_artifact

                def write_then_interrupt(artifact_store, event_log, payload, options, **fields):
                    result = original_writer(artifact_store, event_log, payload, options, **fields)
                    schema = options.schema
                    if (
                        options.kind == "runtime_quality.acquisition_route_loop_receipt"
                        and schema is not None
                        and schema.name
                        == "polisyos.runtime.AcquisitionCandidateExperimentTerminalReceipt"
                    ):
                        crash["writer_calls"] = int(crash["writer_calls"]) + 1
                        if not crash["interrupted"]:
                            if not isinstance(payload, dict):
                                raise AssertionError(
                                    "terminal writer payload was not canonical JSON"
                                )
                            crash["saved_ref"] = result.cas_ref
                            crash["saved_payload"] = copy.deepcopy(payload)
                            crash["job_id"] = job_id
                            event_id = (
                                "evt_acquisition_"
                                + str(payload["action_generation"])
                                + "_experiment_terminal_"
                                + hashlib.sha256(str(payload["receipt_id"]).encode()).hexdigest()[
                                    :16
                                ]
                            )
                            event_rows_at_crash = control._diagnostic_event_log.list_events(
                                event_id=event_id,
                                run_id=str(payload["run_id"]),
                                job_id=job_id,
                                limit=10,
                            )
                            if (
                                len(event_rows_at_crash) != 1
                                or event_rows_at_crash[0].event.event_id != event_id
                                or event_rows_at_crash[0].event.payload_ref
                                != str(result.cas_ref.artifact_id)
                            ):
                                raise AssertionError(
                                    "terminal diagnostic event was not durable at crash cut"
                                )
                            pending_outcomes = (
                                control.acquisition_route_sink.experiment_action_outcomes(
                                    tenant_id=str(payload["tenant_id"]),
                                    cell_id=str(payload["cell_id"]),
                                    run_id=str(payload["run_id"]),
                                    source_job_id=str(payload["source_job_id"]),
                                    route_id=str(payload["route_id"]),
                                )
                            )
                            if (
                                not pending_outcomes
                                or pending_outcomes[-1].head.job_id != job_id
                                or pending_outcomes[-1].head.receipt_phase
                                != "candidate_input_reentry_pending"
                            ):
                                raise AssertionError(
                                    "terminal writer changed the SQL head before terminal commit"
                                )
                            crash["event_id"] = event_id
                            crash["event_rows_at_crash"] = tuple(event_rows_at_crash)
                            crash["pending_head_at_crash"] = pending_outcomes[-1].head
                            crash["interrupted"] = True
                            raise KeyboardInterrupt("controlled terminal writer process crash")
                        if result.cas_ref != crash["saved_ref"]:
                            raise AssertionError("terminal retry wrote a different CAS profile")
                        if payload != crash["saved_payload"]:
                            raise AssertionError(
                                "terminal retry changed the saved terminal payload"
                            )
                    return result

                monkeypatch.setattr(
                    run_lifecycle,
                    "write_runtime_authority_artifact",
                    write_then_interrupt,
                )

            def execute_after_replay(**execution_values) -> None:
                def retry_from_fresh_runtime(**retry_values) -> str:
                    from time import sleep

                    from polisyos.core import artifacts
                    from polisyos.runtime.http.services.acquisition_action_service import (
                        CandidateExperimentRouteProjection,
                    )
                    from tests._helpers.control_worker import dispatch_one_control_job

                    retry_control = retry_values["control"]
                    retry_origin = retry_values["origin"]
                    job_id = str(retry_values["job_id"])
                    retry_units = int(retry_values["interrupted_units"])
                    retry_expiry = retry_values["retry_expiry"]
                    values_for_retry = execution_values["values"]
                    trust = values_for_retry["trust"]
                    with _candidate_experiment_reopened_runtime(
                        control=retry_control,
                        trust=trust,
                        monkeypatch=monkeypatch,
                    ) as (reader, fresh_control, _sqlite_path, _cas_root):
                        fresh_action_service = reader.app.state._acquisition_action_service
                        if (
                            fresh_action_service is None
                            or fresh_action_service.control_service is not fresh_control
                        ):
                            raise AssertionError(
                                "candidate experiment fresh runtime lost its actual action owner"
                            )
                        fresh_policy_owner = _candidate_experiment_policy_owner(
                            control=fresh_control,
                            fixture_root=tmp_path / "candidate-issuer",
                            run_id=retry_origin.run_id,
                        )
                        if fresh_policy_owner.template != template:
                            raise AssertionError(
                                "candidate experiment fresh runtime changed selected policy config"
                            )
                        if (
                            fresh_policy_owner.template.authority_registry_sha256
                            != policy_owner.template.authority_registry_sha256
                            or fresh_policy_owner.template.authority_provision_sha256
                            != policy_owner.template.authority_provision_sha256
                            or fresh_policy_owner.template.attempt_id
                            != policy_owner.template.attempt_id
                        ):
                            raise AssertionError(
                                "candidate experiment fresh issuer identity changed"
                            )
                        fresh_control._registry_providers = replace(
                            fresh_control._registry_providers,
                            source_profiles=fresh_policy_owner.source_profiles,
                            candidate_unpriced_policy_bindings=(),
                            candidate_unpriced_policy_templates=(fresh_policy_owner.template,),
                        )
                        fresh_origin = fresh_action_service._resolve_candidate_experiment_origin(
                            tenant_id=retry_origin.tenant_id,
                            cell_id=retry_origin.cell_id,
                            run_id=retry_origin.run_id,
                        )
                        if (
                            fresh_origin.tenant_id != retry_origin.tenant_id
                            or fresh_origin.cell_id != retry_origin.cell_id
                            or fresh_origin.run_id != retry_origin.run_id
                            or fresh_origin.source_job_id != retry_origin.source_job_id
                            or fresh_origin.source_payload_ref != retry_origin.source_payload_ref
                            or fresh_origin.request_content_hash
                            != retry_origin.request_content_hash
                            or fresh_origin.route_id != retry_origin.route_id
                            or fresh_origin.policy_ref != retry_origin.policy_ref
                            or fresh_origin.policy_scope != retry_origin.policy_scope
                        ):
                            raise AssertionError(
                                "candidate experiment fresh runtime changed selected source"
                            )

                        with candidate_experiment_served_execution_owner(
                            action_service=fresh_action_service,
                            origin=fresh_origin,
                            policy_owner=fresh_policy_owner,
                            monkeypatch=monkeypatch,
                        ) as fresh_execution_owner:
                            if (
                                fresh_execution_owner.port is policy_owner.issuer.port
                                or fresh_execution_owner.port._artifact_store
                                is not fresh_control._artifact_store
                            ):
                                raise AssertionError(
                                    "candidate experiment retry reused a port from the old control"
                                )
                            event_id = str(crash["event_id"])
                            event_rows_before = tuple(
                                fresh_control._diagnostic_event_log.list_events(
                                    event_id=event_id,
                                    run_id=retry_origin.run_id,
                                    job_id=job_id,
                                    limit=10,
                                )
                            )
                            if event_rows_before != crash["event_rows_at_crash"]:
                                raise AssertionError(
                                    "candidate experiment event changed before fresh retry"
                                )
                            saved_ref = crash["saved_ref"]
                            saved_payload = crash["saved_payload"]
                            saved_artifact = artifacts.read_core_json_artifact(
                                fresh_control._artifact_store,
                                saved_ref,
                            )
                            if saved_artifact.value != saved_payload:
                                raise AssertionError(
                                    "candidate experiment fresh runtime could not read crash CAS"
                                )
                            pending_before = _experiment_outcomes(
                                control=fresh_control,
                                origin=fresh_origin,
                            )
                            if (
                                not pending_before
                                or pending_before[-1].head
                                != retry_values["interrupted_outcome"].head
                                or pending_before[-1].head.receipt_phase
                                != "candidate_input_reentry_pending"
                            ):
                                raise AssertionError(
                                    "candidate experiment pending head changed before fresh retry"
                                )
                            job_before = fresh_control._control_store.get_job(job_id)
                            if (
                                job_before is None
                                or job_before.state != "running"
                                or job_before.attempt != 1
                            ):
                                raise AssertionError(
                                    "candidate experiment job state changed before fresh retry"
                                )
                            units_before_retry = _standard_invocation_units(
                                control=fresh_control,
                                run_id=retry_origin.run_id,
                            )
                            if units_before_retry != retry_units:
                                raise AssertionError(
                                    "candidate experiment fresh runtime changed physical N5 units"
                                )

                            sink = fresh_control.acquisition_route_sink
                            with pytest.raises(
                                ValueError,
                                match="candidate_experiment_action_source_scope_mismatch",
                            ):
                                sink.experiment_action_outcomes(
                                    tenant_id=fresh_origin.tenant_id,
                                    cell_id=fresh_origin.cell_id,
                                    run_id=fresh_origin.run_id,
                                    source_job_id=fresh_origin.source_job_id,
                                    route_id=fresh_origin.route_id,
                                    verified_origin=replace(
                                        fresh_origin,
                                        cell_id=fresh_origin.cell_id + "-foreign",
                                    ),
                                )
                            if (
                                _experiment_outcomes(
                                    control=fresh_control,
                                    origin=fresh_origin,
                                )[-1].head
                                != pending_before[-1].head
                                or tuple(
                                    fresh_control._diagnostic_event_log.list_events(
                                        event_id=event_id,
                                        run_id=retry_origin.run_id,
                                        job_id=job_id,
                                        limit=10,
                                    )
                                )
                                != event_rows_before
                                or _standard_invocation_units(
                                    control=fresh_control,
                                    run_id=retry_origin.run_id,
                                )
                                != retry_units
                                or fresh_execution_owner.transport_calls
                            ):
                                raise AssertionError(
                                    "candidate experiment scope refusal had durable or N5 side effects"
                                )
                            job_after_scope_refusal = fresh_control._control_store.get_job(job_id)
                            if (
                                job_after_scope_refusal is None
                                or job_after_scope_refusal.state != job_before.state
                                or job_after_scope_refusal.attempt != job_before.attempt
                                or job_after_scope_refusal.lease_expires_at
                                != job_before.lease_expires_at
                            ):
                                raise AssertionError(
                                    "candidate experiment scope refusal changed the persisted job"
                                )

                            remaining = (
                                retry_expiry - datetime.now(retry_expiry.tzinfo)
                            ).total_seconds()
                            if remaining > 0:
                                sleep(remaining)
                            with monkeypatch.context() as no_n5_retry:
                                no_n5_retry.setattr(
                                    JointSimulationHorizonController,
                                    "run",
                                    lambda *_args, **_kwargs: pytest.fail(
                                        "candidate experiment fresh-runtime retry repeated N5"
                                    ),
                                )
                                dispatched = dispatch_one_control_job(
                                    store=fresh_control._control_store,
                                    handler=fresh_control._process_control_job,
                                    expected_job_id=job_id,
                                )
                            if dispatched != job_id:
                                raise AssertionError(
                                    "candidate experiment fresh runtime did not reclaim the job"
                                )
                            final_job = fresh_control._control_store.get_job(job_id)
                            if (
                                final_job is None
                                or final_job.state != "completed"
                                or final_job.attempt != 2
                            ):
                                raise AssertionError(
                                    "candidate experiment fresh-runtime retry did not complete"
                                )
                            final_outcomes = _experiment_outcomes(
                                control=fresh_control,
                                origin=fresh_origin,
                            )
                            if not final_outcomes:
                                raise AssertionError(
                                    "candidate experiment fresh runtime lost terminal history"
                                )
                            final_history = final_outcomes[-1].candidate_experiment_terminal_history
                            if (
                                final_outcomes[-1].head.receipt_phase != "terminal"
                                or final_outcomes[-1].head.job_id != job_id
                                or final_history is None
                                or final_history.terminal_ref != saved_ref
                                or final_history.terminal.model_dump(mode="json") != saved_payload
                            ):
                                raise AssertionError(
                                    "candidate experiment fresh retry changed persisted terminal CAS"
                                )
                            if (
                                tuple(
                                    fresh_control._diagnostic_event_log.list_events(
                                        event_id=event_id,
                                        run_id=retry_origin.run_id,
                                        job_id=job_id,
                                        limit=10,
                                    )
                                )
                                != event_rows_before
                                or _standard_invocation_units(
                                    control=fresh_control,
                                    run_id=retry_origin.run_id,
                                )
                                != retry_units
                                or fresh_execution_owner.transport_calls
                            ):
                                raise AssertionError(
                                    "candidate experiment fresh retry repeated N5 or source fetch"
                                )
                            response = reader.get(
                                f"/api/v1/runs/{retry_origin.run_id}/candidate-acquisition-experiment",
                                headers={
                                    "Authorization": (
                                        f"Bearer {trust.tokens['acquisition-operator']}"
                                    ),
                                    "X-Tenant-ID": served.TENANT,
                                },
                            )
                            if response.status_code != 200:
                                raise AssertionError(response.text)
                            visible = CandidateExperimentRouteProjection.model_validate(
                                response.json()
                            ).current_action
                            if (
                                visible.status != "completed"
                                or visible.job_id != job_id
                                or visible.receipt_phase != "terminal"
                                or visible.selected_receipt_ref != saved_ref
                            ):
                                raise AssertionError(
                                    "candidate experiment fresh retry was not visible to its reader"
                                )
                            if block_b_implementation_observation and (
                                visible.evaluation_disposition != "blocked"
                                or visible.selected_evaluation is not None
                                or not visible.blocker_reason
                            ):
                                raise AssertionError(
                                    "candidate experiment blocked B reuse was not visible without evaluation"
                                )
                            if not block_b_implementation_observation and (
                                visible.evaluation_disposition != "new"
                                or visible.selected_evaluation is None
                            ):
                                raise AssertionError(
                                    "candidate experiment evaluated positive changed disposition"
                                )
                            if len(retry_values["execution_owner"].transport_calls) != int(
                                retry_values["interrupted_transport_call_count"]
                            ):
                                raise AssertionError(
                                    "candidate experiment fresh retry repeated the initial source fetch"
                                )
                    return job_id

                execution = run_candidate_experiment_served_execution(
                    values=execution_values["values"],
                    origin=execution_values["origin"],
                    request=execution_values["request"],
                    decision_ref=execution_values["decision_ref"],
                    policy_owner=policy_owner,
                    monkeypatch=monkeypatch,
                    before_first_delivery=arm_terminal_writer_crash,
                    recover_worker_crash=True,
                    fresh_runtime_recovery=retry_from_fresh_runtime,
                )
                assert crash["interrupted"] is True
                assert crash["job_id"] == execution.job_id
                assert crash["writer_calls"] == 2
                assert execution.attempts == (1, 2)
                assert execution.interrupted_job is not None
                assert execution.interrupted_job.state == "running"
                assert execution.interrupted_job.attempt == 1
                assert execution.final_job.attempt == 2
                assert execution.interrupted_outcome is not None
                assert (
                    execution.interrupted_outcome.head.receipt_phase
                    == "candidate_input_reentry_pending"
                )
                assert execution.interrupted_outcome.head == crash["pending_head_at_crash"]
                assert execution.standard_invocation_units_before == 2
                assert execution.standard_invocation_units_after_interrupted == 4
                assert execution.standard_invocation_units_after == 4
                assert type(execution.terminal_history.terminal) is (
                    AcquisitionCandidateExperimentTerminalReceipt
                )
                saved_ref = crash["saved_ref"]
                assert execution.terminal_ref == saved_ref
                assert (
                    execution.terminal_history.terminal.model_dump(mode="json")
                    == (crash["saved_payload"])
                )
                saved_generated_at = datetime.fromisoformat(
                    str(crash["saved_payload"]["generated_at"])
                )
                assert execution.terminal_history.terminal.generated_at == saved_generated_at
                assert (
                    execution.terminal_history.head.receipt_manifest_profile_sha256
                    == saved_ref.manifest_profile_sha256
                )
                if block_b_implementation_observation:
                    from polisyos.runtime.quality.acquisition_evaluation import (
                        CandidateAcquisitionEvaluationBasis,
                    )

                    terminal = execution.terminal_history.terminal
                    assert terminal.selected_evaluation is None
                    assert terminal.candidate_reentry_ref is not None
                    assert terminal.selected_evaluation_witness_ref == (
                        terminal.candidate_reentry_ref
                    )
                    selected_basis = CandidateAcquisitionEvaluationBasis.model_validate(
                        canon.from_canonical_bytes(
                            control._artifact_store.get_bytes(terminal.selected_basis_ref)
                        )
                    )
                    assert selected_basis.basis_role == "blocked"
                    assert selected_basis.predicate_provenance == "not_established"
                    assert "n5_prior_live_implementation_not_established" in (
                        selected_basis.reason_codes
                    )
                    assert execution.terminal_history.frontier_after == (
                        execution.terminal_history.frontier_before
                    )
                    assert execution.current_action.evaluation_disposition == "blocked"
                    assert execution.current_action.selected_evaluation is None
                    assert int(implementation_observation["blocked_calls"]) == 1
                    captures = implementation_observation["captures"]
                    assert isinstance(captures, list) and len(captures) == 1
                    b_capture = captures[0]
                    assert int(implementation_observation["calls"][id(b_capture)]) == 1
                    reentry = execution.terminal_history.reentry
                    assert reentry is not None and reentry.n5_input_ref is not None
                    from polisyos.core.artifacts import artifact_ref_identity_key
                    from polisyos.runtime.quality.generation_cycle import (
                        load_joint_simulation_result,
                    )

                    assert b_capture._admission is not None
                    assert artifact_ref_identity_key(b_capture._admission.input_ref) == (
                        artifact_ref_identity_key(reentry.n5_input_ref)
                    )
                    b_result = load_joint_simulation_result(
                        reentry.n5_result_ref,
                        store=control._artifact_store,
                    )
                    b_witness = N5ExecutionImplementationWitness.model_validate(
                        b_result.diagnostics["n5_execution_implementation_witness"]
                    )
                    assert b_witness.predicate_provenance == "not_established"
                    assert b_witness.reason_codes[0] == "canonical_loaded_runtime_mismatch"
                    assert (
                        "n5_implementation_failure_target:"
                        "polisyos.runtime.quality.confidence_ledger"
                    ) in b_witness.reason_codes
                    assert b_witness.input_ref_identity == artifact_ref_identity_key(
                        reentry.n5_input_ref
                    )
                    assert exact_n5_content_bytes(b_witness.consumed_configuration_values) == (
                        exact_n5_content_bytes(b_capture._configuration_start)
                    )
                    assert execution.terminal_history.reentry is not None
                    assert execution.terminal_history.reentry.n5_result_ref is not None
                    assert execution.terminal_history.reentry.n5_execution_ref is not None
                    candidate_result = execution.current_action.candidate_n5_result
                    assert candidate_result is not None
                    assert candidate_result.configuration_use == "not_established"
                    assert (
                        "controller_wide_configuration_use_not_established"
                        in candidate_result.limitations
                    )
                    assert candidate_result.authority_purpose == "candidate_observation_only"
                    assert candidate_result.publication_authority is False
                    assert candidate_result.result_body.authority_purpose == (
                        "candidate_scenario_n5_only"
                    )
                    assert candidate_result.result_body.publication_authority is False
                    assert artifact_ref_identity_key(
                        candidate_result.result_body.artifact_ref
                    ) == artifact_ref_identity_key(
                        execution.terminal_history.reentry.n5_result_ref
                    )
                    _assert_candidate_experiment_n5_uses_current_wmr(
                        control=control,
                        origin=execution_values["origin"],
                        execution=execution,
                        resolved_reentry_evaluation=(
                            execution.terminal_history.reentry_evaluation
                        ),
                    )
                else:
                    assert execution.terminal_history.frontier_after is not None
                    assert execution.current_action.evaluation_disposition == "new"
                    assert execution.current_action.selected_evaluation is not None
                    assert int(implementation_observation["blocked_calls"]) == 0
                    _assert_candidate_experiment_n5_uses_current_wmr(
                        control=control,
                        origin=execution_values["origin"],
                        execution=execution,
                    )
                assert template.max_standard_n5_invocations == 4
                assert execution.execution_owner.transport_calls == [
                    (
                        "GET",
                        "https://api.worldbank.org/v2/country/USA/indicator/SL.UEM.TOTL.ZS",
                        {
                            "date": "2024:2024",
                            "format": "json",
                            "page": "1",
                            "per_page": "1000",
                        },
                    )
                ]
                terminal = execution.terminal_history.terminal
                event_id = (
                    "evt_acquisition_"
                    + str(terminal.action_generation)
                    + "_experiment_terminal_"
                    + hashlib.sha256(terminal.receipt_id.encode()).hexdigest()[:16]
                )
                rows = control._diagnostic_event_log.list_events(
                    event_id=event_id,
                    run_id=terminal.run_id,
                    job_id=terminal.job_id,
                    limit=10,
                )
                assert crash["event_id"] == event_id
                assert tuple(rows) == crash["event_rows_at_crash"]
                terminal_head = control._control_store.get_acquisition_action_head_by_receipt(
                    tenant_id=terminal.tenant_id,
                    cell_id=terminal.cell_id,
                    run_id=terminal.run_id,
                    source_job_id=terminal.source_job_id,
                    route_id=terminal.route_id,
                    action_generation=terminal.action_generation,
                    receipt_ref=str(execution.terminal_ref.artifact_id),
                )
                assert terminal_head is not None
                assert terminal_head.head_generation == 5
                assert (
                    terminal_head.receipt_manifest_profile_sha256
                    == execution.terminal_ref.manifest_profile_sha256
                )
                assert terminal_head.receipt_phase == "terminal"
                observed["execution"] = execution

            observed.update(
                run_candidate_experiment_action_oracle(
                    tmp_path=tmp_path,
                    values=values,
                    policy_ref=policy_ref,
                    monkeypatch=monkeypatch,
                    after_replay=execute_after_replay,
                )
            )
            assert observed["source_status"] == "completed"
        finally:
            control._registry_providers = original_providers

    with complete_candidate_cycle_catalog_source(
        source.root, monkeypatch, synthetic_usa_labor_scope=True
    ) as prepared:
        assert prepared[2].resolve(family_id="macro_state")
        result = served._produce_served_acquisition_history(
            tmp_path,
            monkeypatch,
            served_recorded_candidate_gateway,
            source_owner_root=source.root,
            prepared_catalog=prepared,
            provider_mode="synthetic_settled_candidate",
            seed_only_context_observer=serve_action,
            run_budget_usd=5.0,
            run_budget_scope="metered_paid_producers_and_bounded_candidate",
            candidate_acquisition_intent="bounded_experiment_voi_unknown",
            invocation_quota_policy=quota,
            labor_seed=True,
        )
    assert result is not None
    assert observed["source_status"] == "completed"
    execution = observed["execution"]
    assert execution.terminal_history.origin.generation_run.run_id == result["run_id"]
