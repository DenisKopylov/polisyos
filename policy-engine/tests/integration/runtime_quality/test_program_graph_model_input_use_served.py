"""Serve a held-out opening stock from its signed activation through numerical N5."""

from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    ensure_ir_artifact_store,
    read_core_json_artifact,
)
from polisyos.core.artifacts.manifest import WarningRecord
from polisyos.core.contracts.epoch import load_verified_epoch_statement
from polisyos.core.contracts.model_input_requirements import (
    load_model_input_obligation_set,
    load_model_input_port_declaration,
)
from polisyos.core.contracts.runtime import RunModelInputUseN5SuccessorResponse
from polisyos.core.security.identity import PolicyOSRole
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.data_forge.read_api.catalog import AcquisitionAuthorityError, build_authority_registry
from polisyos.foundry.execute import admit_semantic_horizon_step_chain, load_state_snapshot
from polisyos.ir.trinity import load_trinity_bundle_artifact
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.deployment_security import (
    DeploymentSecurityConfig,
    build_deployment_security,
)
from polisyos.runtime.http.services.control import generation_cycle as generation_owner
from polisyos.runtime.http.services.control.generation_cycle import (
    CompiledRecursiveGenerationCycleRun,
)
from polisyos.runtime.http.services.model_input_successor_action import (
    MODEL_INPUT_USE_PERMISSION,
    ModelInputSuccessorActionRequest,
    ModelInputUseActionCheckpoint,
)
from polisyos.runtime.quality import agent_action_authority as authority
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.generation_cycle import load_joint_simulation_result
from polisyos.runtime.quality.generic_simulation_admission import (
    GenericCycleSimulationAdmissionOwner,
    GenericCycleSimulationN5ExecutionV4,
    GenericCycleSimulationN5ExecutionV5,
    parse_generic_cycle_simulation_n5_execution,
)
from polisyos.runtime.quality.model_input_routing import read_model_input_routing_report
from polisyos.runtime.quality.substrate_registry import default_substrate_catalog_paths
from tests._helpers import acquisition_served_history as served
from tests._helpers.acquisition_human_decision import (
    _mandate_authority_evidence,
    persist_signed,
)
from tests._helpers.acquisition_production import bind_fixture_l1_catalog_source
from tests._helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker
from tests._helpers.lane01_candidate_action_served import _approve_candidate_action
from tests._helpers.program_graph_tax_subsidy_input import (
    prepare_program_graph_tax_subsidy_input_case,
)
from tests._helpers.runtime_http import _DeterministicSpanSupportClient, _valid_intake_for_mode
from tests.integration.runtime_quality.test_generic_n4_child_profile_set_served import (
    controlled_candidate_gateway as _gateway_fixture,
)
from tests.integration.runtime_quality.test_program_graph_held_out_fund_binding import (
    _activated_fund,
    _held_out_declaration,
)
from tests.integration.runtime_quality.test_program_graph_model_input_served import (
    _INCOME,
    _OUTCOME,
    _fiscal_problem,
    _selected_profile,
    _stock_grounding_source,
    world_fixture,
)
from tests.integration.runtime_quality.test_program_graph_stock_n7_served import (
    _configure_stock_provider,
)

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from polisyos.data_forge.read_api.catalog import CanonicalAcquisitionAuthority
    from polisyos.runtime.http.services.control import ControlPlaneService
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationProfileV1,
    )
    from tests._helpers.controlled_candidate_profile import ControlledCandidateGateway

controlled_candidate_gateway = _gateway_fixture
_ROUTE_TEMPLATE = "/api/v1/runs/{run_id}/model-input-use"
_OPENING_CASH = 640.0
# The scheduled 1/8 subsidy debits the sum of the two eligible incomes.
_EXPECTED_BALANCES = (_OPENING_CASH, _OPENING_CASH, _OPENING_CASH - (100 + 200) / 8)


def _sign_model_input_mandate(
    control: ControlPlaneService,
    *,
    trust: served._ExternalTrust,
    key_root: Path,
    signers: dict[str, Any],
    identities: dict[str, str],
    run_id: str,
    job_id: str,
    route_id: str,
    digest: str,
) -> dict[str, Any]:
    """Appoint a current synthetic mandate for this exact signed action resource."""
    now = datetime.now(UTC)
    valid_from = now - timedelta(minutes=1)
    valid_until = now + timedelta(hours=1)
    contract = served._contract()
    (base_envelope,) = contract.action_envelopes
    envelope = authority.DelegatedActionEnvelope.model_validate(
        {
            **base_envelope.model_dump(mode="python"),
            "action_kind": authority.MODEL_INPUT_USE_ACTION_KIND,
            "operation_id": authority.MODEL_INPUT_USE_ACTION_KIND,
            "required_permission": MODEL_INPUT_USE_PERMISSION,
            "mandate_owner_ref": identities["owner"],
            "authorized_subject": "acquisition-operator",
            "authorized_runtime_roles": (PolicyOSRole.ANALYST,),
            "required_tenant_id": served.TENANT,
            "required_resource_digest": digest,
            "valid_from": valid_from,
            "valid_until": valid_until,
        }
    )
    contract = type(contract).model_validate(
        {
            **contract.model_dump(mode="python"),
            "mandate_owner_ref": identities["owner"],
            "action_envelopes": (envelope,),
        }
    )
    context = {
        "tenant_id": served.TENANT,
        "cell_id": served.CELL,
        "run_id": run_id,
        "job_id": job_id,
        "now": now,
    }
    with tenant_scope(None, tenant_id=served.TENANT, cell_id=served.CELL):
        contract_ref = persist_signed(
            control,
            contract,
            kind=authority.DELEGATION_CONTRACT_ARTIFACT_KIND,
            schema_name="polisyos.runtime.DelegationContract",
            schema_version=authority.LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
            signer=signers["owner"],
            signer_identity=identities["owner"],
            **context,
        )
        current_ref = persist_signed(
            control,
            _mandate_authority_evidence(
                owner_ref=identities["owner"],
                signer_identity=identities["current"],
                rule_version_ref=contract.rule_version_ref,
                effective_from=valid_from,
                effective_until=valid_until,
            ),
            kind=authority.CURRENT_MANDATE_OWNER_ARTIFACT_KIND,
            schema_name="polisyos.runtime.CurrentMandateOwnerEvidence",
            schema_version=authority.CURRENT_MANDATE_OWNER_SCHEMA_VERSION,
            signer=signers["current"],
            signer_identity=identities["current"],
            **context,
        )
        limitation_ref = control._artifact_store.put_json(
            {"limitation": "Synthetic local ledger supplies candidate inputs only."},
            PutOptions(kind="test.acquisition.disconfirming", media_type="application/json"),
        )
    slot = {
        "tenant_id": served.TENANT,
        "cell_id": served.CELL,
        "run_id": run_id,
        "route_id": route_id,
        "resource_digest": digest,
        "delegation_contract_ref": contract_ref,
        "mandate_owner_ref": identities["owner"],
        "delegation_public_key_path": str(key_root / "owner.pub"),
        "current_mandate_evidence_ref": current_ref,
        "current_mandate_signer_identity": identities["current"],
        "current_mandate_public_key_path": str(key_root / "current.pub"),
        "verifier_provenance_ref": "fixture://appointment-registry",
        "decision_information_refs": [limitation_ref.model_dump(mode="json")],
        "decision_disconfirming_refs": [limitation_ref.model_dump(mode="json")],
    }
    trust.raw["acquisition_authority"]["mandates"] = [slot]
    return slot


def _assert_foundry_successor(
    store: FileSystemCAS,
    *,
    original: GenericCycleSimulationN5ExecutionV4,
    mutation: ModelInputSuccessorActionRequest,
    action_job_id: str,
    checkpoint: ModelInputUseActionCheckpoint,
) -> None:
    """Recompute every step through Foundry and check independent cash arithmetic."""
    execution_ref = checkpoint.execution_ref
    result_ref = checkpoint.result_ref
    assert execution_ref is not None and result_ref is not None
    execution = parse_generic_cycle_simulation_n5_execution(
        read_core_json_artifact(store, execution_ref).value
    )
    assert type(execution) is GenericCycleSimulationN5ExecutionV5
    assert execution.input_ref == original.input_ref
    assert execution.n4_source_ref == original.n4_source_ref
    assert execution.action_job_id == action_job_id and execution.result_ref == result_ref
    assert execution.semantic_successor_ref == checkpoint.semantic_successor_ref
    selected = GenericCycleSimulationAdmissionOwner(
        profiles=(), store=store
    ).prepare_semantic_successor_request(
        semantic_successor_ref=checkpoint.semantic_successor_ref,
        expected_blocked_execution_ref=mutation.blocked_execution_ref,
        expected_input_ref=original.input_ref,
    )
    assert selected.selection.activation_receipt_ref == mutation.activation_receipt_ref
    assert selected.selection.observation_id == mutation.observation_id
    request = selected.request
    assert execution.request_binding.request.model_dump(mode="json") == request.model_dump(
        mode="json"
    )
    result = load_joint_simulation_result(result_ref, store=store, expected_request=request)
    (plan,) = request.engine_plan
    selected_bindings = plan.program_semantic_input_bindings_ref
    assert selected_bindings is not None and selected_bindings.manifest_profile_sha256 is not None
    assert len(result.physical_work_observations) == 1
    assert result.physical_work_observations[0].status == "completed"
    assert {trajectory.run_level for trajectory in result.trajectories} == {"individual", "joint"}
    for trajectory in result.trajectories:
        assert trajectory.engine_kind == "program_graph"
        (replication,) = trajectory.semantic_program_graph_replications
        steps = admit_semantic_horizon_step_chain(store, replication.step_result_refs)
        assert len(steps) == len(_EXPECTED_BALANCES)
        for step, expected in zip(steps, _EXPECTED_BALANCES, strict=True):
            assert step.basis is not None
            assert step.basis.input_bindings_ref == selected_bindings
            assert step.simulation_result.state_snapshot_ref is not None
            state = load_state_snapshot(
                store, snapshot_ref=step.simulation_result.state_snapshot_ref
            )
            assert float(state.government_balance) == expected
        assert trajectory.points[-1].outcomes[_OUTCOME] == _EXPECTED_BALANCES[-1]


@pytest.mark.integration
def test_activated_held_out_stock_executes_through_ordinary_signed_model_input_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: ControlledCandidateGateway,
) -> None:
    """Exercise the blocked producer, protected successor, and fresh numerical reader."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("POLISYOS_RUNTIME_EXECUTION_PROFILE", "development")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", str(tmp_path / "control.sqlite3"))
    monkeypatch.setenv("POLISYOS_CACHE_HOME", str(tmp_path / "runtime-cache"))
    cas_root = tmp_path / "cas"
    runs_root = cas_root / "runs"
    problem_data = _fiscal_problem().model_dump(mode="json")
    problem_data["nl_provenance"]["raw_request"] = (
        "Evaluate one bounded tax subsidy using the public-benefit fund's opening cash in USD. "
        "Do not promote generated candidates."
    )
    problem = DesignProblem.model_validate(problem_data)
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

    store = FileSystemCAS(cas_root).for_tenant(served.TENANT, served.CELL)
    with closing(served._ExternalTrust(tmp_path)) as trust:
        signers, identities = served._key_config(tmp_path, trust)
        with tenant_scope(None, tenant_id=served.TENANT, cell_id=served.CELL):
            case = prepare_program_graph_tax_subsidy_input_case(
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
                model_input_port_declaration_builder=_held_out_declaration,
                store=store,
                snapshot_id=world_fixture.SNAPSHOT_ID,
            )
            assert case.model_input_port_declaration_ref is not None
            (port,) = load_model_input_port_declaration(
                store, case.model_input_port_declaration_ref
            ).ports
            trinity = load_trinity_bundle_artifact(
                ensure_ir_artifact_store(store), case.trinity_ref
            )
        model_id = _configure_stock_provider(
            controlled_candidate_gateway,
            problem=problem,
            trinity=trinity,
            evidence_root=tmp_path / "llm",
        )

        def app(root: Path, profile: GenericCycleSimulationProfileV1 | None = None) -> Any:
            # Each app reopens the same tenant-owned bootstrap artifacts.
            with tenant_scope(None, tenant_id=served.TENANT, cell_id=served.CELL):
                return create_runtime_api_app(
                    cas_root=cas_root,
                    core_runs_root=runs_root,
                    deployment_security=build_deployment_security(
                        DeploymentSecurityConfig.from_mapping(trust.raw)
                    ),
                    enable_security_middlewares=True,
                    enable_csrf_protection=False,
                    repo_root=root,
                    generic_cycle_simulation_profiles=() if profile is None else (profile,),
                    generic_cycle_simulation_root_profile_id=None
                    if profile is None
                    else profile.profile_id,
                )

        seeds = []

        def launch_before_activation(catalog: CanonicalAcquisitionAuthority) -> None:
            root = catalog.repo_root
            skg_prior = _stock_grounding_source(root)
            prior_catalog = default_substrate_catalog_paths(root).l1_dcat_path
            prior_catalog.rename(tmp_path / "unused-grounding-only.duckdb")
            bind_fixture_l1_catalog_source(root, catalog.baseline_path)
            assert prior_catalog.resolve(strict=True) == catalog.baseline_path
            with tenant_scope(None, tenant_id=served.TENANT, cell_id=served.CELL):
                profile = _selected_profile(
                    case, trinity, problem, tmp_path / "world", skg_prior=skg_prior
                )
            with TestClient(app(root, profile)) as client:
                control = client.app.state.runtime_container.control_service
                stop_embedded_control_worker(control)
                launched = client.post(
                    "/api/v1/control/runs/nl",
                    headers={
                        "Authorization": trust.authorization_header("acquisition-operator"),
                        "X-Tenant-ID": served.TENANT,
                        "Idempotency-Key": "held-out-fund-before-activation",
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
                assert launched.status_code == 200, launched.text
                job_id = launched.json()["job_id"]
                assert (
                    dispatch_one_control_job(
                        store=control._control_store,
                        handler=control._process_control_job,
                        expected_job_id=job_id,
                    )
                    == job_id
                )
                job = control._control_store.get_job(job_id)
                assert job is not None and job.state == "completed", (
                    None if job is None else job.error_message
                )
                assert not control.llm_producer_settlement_store._ledger.snapshot().invocation_reservations
                seeds.append((job, profile))

        with (
            tenant_scope(None, tenant_id=served.TENANT, cell_id=served.CELL),
            _activated_fund(
                tmp_path / "held-out-activation",
                store=store,
                port=port,
                fund="public-benefit-fund",
                before_activation=launch_before_activation,
            ) as active,
        ):
            root = active.repo_root
            (entry,) = active.entries
            projection = active.projections[entry.target_variable]
            (selected_observation,) = projection.observations
        ((job, profile),) = seeds
        run_id = job.run_id
        assert run_id is not None
        core_run_id = job.progress["core_run_id"]
        compiled_ref = ArtifactRef.model_validate(
            job.progress["compiled_recursive_generation_cycle_artifact_ref"]
        )
        compiled = CompiledRecursiveGenerationCycleRun.model_validate(
            read_core_json_artifact(store, compiled_ref).value
        )
        (node,) = compiled.recursive_run.leaf_nodes
        assert node.cycle_run is not None
        (cycle,) = node.cycle_run.cycles
        execution_ref = cycle.simulation.generic_n5_execution_ref
        report_ref = cycle.model_input_routing_report_ref
        assert execution_ref is not None and report_ref is not None
        original = parse_generic_cycle_simulation_n5_execution(
            read_core_json_artifact(store, execution_ref).value
        )
        assert type(original) is GenericCycleSimulationN5ExecutionV4
        assert original.status == "simulation_blocked" and original.result_ref is None
        _, (obligation,) = load_model_input_obligation_set(
            store, original.model_input_obligation_set_ref
        )
        assert obligation.port == port and obligation.dependencies[0].first_required_step == 2
        report = read_model_input_routing_report(store, report_ref)
        (route,) = report.routes
        descriptor = route.source_descriptor
        assert route.disposition == "resolved" and descriptor is not None
        assert descriptor.authority_entry_id == entry.entry_id
        assert descriptor.source_semantic_definition_ref == port.semantic_definition_ref
        assert selected_observation.observation.value == _OPENING_CASH

        mutation = ModelInputSuccessorActionRequest(
            compiled_ref=compiled_ref,
            blocked_execution_ref=execution_ref,
            routing_report_ref=report_ref,
            activation_receipt_ref=projection.receipt_ref,
            observation_id=selected_observation.observation.observation_id,
            idempotency_key="held-out-fund-opening-cash-use",
        )
        path = f"/api/v1/runs/{run_id}/model-input-use"

        with trust.authorization_exchange("acquisition-operator") as operator_authorization:
            with TestClient(app(root, profile)) as client:
                control = client.app.state.runtime_container.control_service
                stop_embedded_control_worker(control)
                ref = mutation.activation_receipt_ref
                manifest = store.get_manifest(ref)
                sibling = store.put_bytes(
                    store.get_bytes(ref),
                    PutOptions(
                        kind=manifest.kind,
                        media_type=manifest.media_type,
                        schema=manifest.artifact_schema,
                        canon=manifest.canon,
                        producer=manifest.producer,
                        inputs=manifest.inputs,
                        governance=manifest.governance,
                        tenant_context=manifest.tenant_context,
                        warnings=[
                            WarningRecord(code="test.foreign_activation", msg="Same receipt bytes")
                        ],
                    ),
                    return_selected_profile=True,
                )
                assert (
                    sibling.artifact_id == ref.artifact_id
                    and sibling.manifest_profile_sha256 != ref.manifest_profile_sha256
                )
                assert load_verified_epoch_statement(
                    store=store, ref=sibling, expected_kind=ref.kind
                ) == load_verified_epoch_statement(store=store, ref=ref, expected_kind=ref.kind)
                foreign, _ = trust.post(
                    client,
                    path + "/decision-request",
                    mutation.model_copy(update={"activation_receipt_ref": sibling}).model_dump(
                        mode="json"
                    ),
                    route=_ROUTE_TEMPLATE + "/decision-request",
                )
                assert foreign.status_code == 409, foreign.text
                assert foreign.json()["code"] == "active_epoch_receipt_binding_mismatch"
                blob, _ = store._paths(ref.artifact_id)
                withheld = tmp_path / "withheld-activation"
                blob.rename(withheld)
                try:
                    missing, _ = trust.post(
                        client,
                        path + "/decision-request",
                        mutation.model_dump(mode="json"),
                        route=_ROUTE_TEMPLATE + "/decision-request",
                    )
                    assert missing.status_code == 409, missing.text
                    assert missing.json()["code"] == "model_input_use_source_not_established"
                finally:
                    withheld.rename(blob)
                initial, digest = trust.post(
                    client,
                    path + "/decision-request",
                    mutation.model_dump(mode="json"),
                    route=_ROUTE_TEMPLATE + "/decision-request",
                )
                assert initial.status_code == 200, initial.text
                assert initial.json()["outcome"] == "decision_required"
                action_job_id = initial.json()["job_id"]
                route_id = initial.json()["route_id"]
                denied, _ = trust.post(
                    client,
                    path + "/execute",
                    {
                        "request": mutation.model_dump(mode="json"),
                        "decision_ref": initial.json()["authority_decision_ref"],
                    },
                    route=_ROUTE_TEMPLATE + "/execute",
                )
                assert denied.status_code == 409, denied.text
                assert denied.json()["code"] == "model_input_use_live_authority_not_established"
                assert control._control_store.get_job(action_job_id) is None
                assert not control.llm_producer_settlement_store._ledger.snapshot().invocation_reservations
                slot = _sign_model_input_mandate(
                    control,
                    trust=trust,
                    key_root=tmp_path,
                    signers=signers,
                    identities=identities,
                    run_id=run_id,
                    job_id=action_job_id,
                    route_id=route_id,
                    digest=digest,
                )

            with TestClient(app(root, profile)) as client:
                control = client.app.state.runtime_container.control_service
                stop_embedded_control_worker(control)
                _approve_candidate_action(
                    client=client,
                    control=control,
                    closure=SimpleNamespace(
                        tenant_id=served.TENANT, cell_id=served.CELL, run_id=run_id
                    ),
                    path=path,
                    template=_ROUTE_TEMPLATE,
                    mutation=mutation,
                    job_id=action_job_id,
                    slot=slot,
                    cas_root=cas_root,
                    trust=trust,
                    signers=signers,
                    identities=identities,
                )

            with TestClient(app(root, profile)) as client:
                control = client.app.state.runtime_container.control_service
                stop_embedded_control_worker(control)
                allowed, same_digest = trust.post(
                    client,
                    path + "/decision-request",
                    mutation.model_dump(mode="json"),
                    route=_ROUTE_TEMPLATE + "/decision-request",
                )
                assert allowed.status_code == 200 and same_digest == digest, allowed.text
                assert allowed.json()["outcome"] == "decision_available", allowed.text
                execution_body = {
                    "request": mutation.model_dump(mode="json"),
                    "decision_ref": allowed.json()["authority_decision_ref"],
                }
                no_step_up = client.post(
                    path + "/execute",
                    json=execution_body,
                    headers={
                        "Authorization": operator_authorization,
                        "X-Tenant-ID": served.TENANT,
                    },
                )
                assert no_step_up.status_code == 403, no_step_up.text
                assert no_step_up.json()["code"] == "step_up_required"
                assert control._control_store.get_job(action_job_id) is None
                assert not control.llm_producer_settlement_store._ledger.snapshot().invocation_reservations
                execute, _ = trust.post(
                    client,
                    path + "/execute",
                    execution_body,
                    route=_ROUTE_TEMPLATE + "/execute",
                )
                assert execute.status_code == 200, execute.text
                assert execute.json()["job_id"] == action_job_id
                assert (
                    dispatch_one_control_job(
                        store=control._control_store,
                        handler=control._process_control_job,
                        expected_job_id=action_job_id,
                    )
                    == action_job_id
                )
                action = control._control_store.get_job(action_job_id)
                assert action is not None and action.state == "completed", (
                    None if action is None else action.error_message
                )
                checkpoint = ModelInputUseActionCheckpoint.model_validate(
                    action.progress["model_input_use"]
                )
                assert (
                    len(
                        control.llm_producer_settlement_store._ledger.snapshot().invocation_reservations
                    )
                    == 1
                )

        fresh = FileSystemCAS(cas_root).for_tenant(served.TENANT, served.CELL)
        with TestClient(app(root)) as reader:
            stop_embedded_control_worker(reader.app.state.runtime_container.control_service)
            headers = {
                "Authorization": trust.authorization_header("acquisition-operator"),
                "X-Tenant-ID": served.TENANT,
            }
            original_get = reader.get(f"/api/v1/runs/{core_run_id}", headers=headers)
            assert original_get.status_code == 200, original_get.text
            (row,) = original_get.json()["run"]["generic_cycle_simulation"]["n5_observations"]
            assert (
                row["status"] == "simulation_blocked" and row.get("simulation_result_ref") is None
            )
            assert row["n5_owner_join_status"] == "resolved"
            assert (
                ArtifactRef.model_validate(row["model_input_routing"]["report_ref"]) == report_ref
            )
            result_path = path + f"/{action_job_id}/n5-result"
            successor = reader.get(result_path, headers=headers)
            assert successor.status_code == 200, successor.text
            selected = RunModelInputUseN5SuccessorResponse.model_validate(successor.json()).result
            assert selected.action_status == "completed", selected.limitation_code
            assert selected.result_status == "resolved", selected.limitation_code
            assert selected.action_job_id == action_job_id
            assert selected.semantic_successor_ref == checkpoint.semantic_successor_ref
            assert selected.n5_execution_ref == checkpoint.execution_ref
            assert selected.simulation_result_ref == checkpoint.result_ref
            assert selected.authority_purpose == "cycle_input_candidate_only"
            assert (
                selected.currentness_status == "not_established"
                and not selected.publication_authority
            )
            blocked = selected.blocked_source
            assert blocked is not None and blocked.status == "simulation_blocked"
            assert blocked.source_job_id == job.job_id
            assert (
                blocked.blocked_execution_ref == execution_ref
                and blocked.routing_report_ref == report_ref
            )
            assert blocked.model_input_obligation_set_ref == original.model_input_obligation_set_ref
            assert selected.result_body is not None
            for trajectory in selected.result_body.trajectories:
                assert (
                    tuple(point.outcomes[_OUTCOME] for point in trajectory.points)
                    == _EXPECTED_BALANCES
                )
            _assert_foundry_successor(
                fresh,
                original=original,
                mutation=mutation,
                action_job_id=action_job_id,
                checkpoint=checkpoint,
            )
            assert checkpoint.result_ref is not None
            blob, _ = fresh._paths(checkpoint.result_ref.artifact_id)
            withheld = tmp_path / "withheld-successor-result"
            blob.rename(withheld)
            try:
                removed = reader.get(result_path, headers=headers)
                assert removed.status_code == 200, removed.text
                limited = RunModelInputUseN5SuccessorResponse.model_validate(removed.json()).result
                assert limited.action_status == "completed"
                assert limited.result_status == "not_established"
                assert limited.blocked_source == blocked
                assert limited.simulation_result_ref is None and limited.result_body is None
            finally:
                withheld.rename(blob)

        # Withdraw only the current source entry through the canonical registry
        # format. Keep the original activation, signed action and numerical
        # evidence available for historical replay.
        registry_path = active.authority.registry_path
        registry_bytes = registry_path.read_bytes()
        registry = active.authority._load_registry()
        assert entry in registry.entries
        withdrawn = build_authority_registry(
            baseline_content_sha256=registry.baseline_content_sha256,
            l5_measurement_registry_sha256=registry.l5_measurement_registry_sha256,
            entries=tuple(item for item in registry.entries if item.entry_id != entry.entry_id),
        )
        try:
            registry_path.write_text(withdrawn.model_dump_json(), encoding="utf-8")
            with pytest.raises(AcquisitionAuthorityError, match="authority_entry_unresolved"):
                active.authority.resolve(entry.entry_id)

            with (
                trust.authorization_exchange("acquisition-operator") as operator_authorization,
                TestClient(app(root)) as historical_reader,
            ):
                historical_control = historical_reader.app.state.runtime_container.control_service
                stop_embedded_control_worker(historical_control)
                ledger = historical_control.llm_producer_settlement_store._ledger
                reservations = ledger.snapshot().invocation_reservations
                assert len(reservations) == 1
                new_use = mutation.model_copy(update={"idempotency_key": "withdrawn-stock-use"})
                refused, _ = trust.post(
                    historical_reader,
                    path + "/decision-request",
                    new_use.model_dump(mode="json"),
                    route=_ROUTE_TEMPLATE + "/decision-request",
                )
                assert refused.status_code == 409, refused.text
                assert refused.json()["code"] == "model_input_use_source_not_established"

                with tenant_scope(None, tenant_id=served.TENANT, cell_id=served.CELL):
                    _assert_foundry_successor(
                        fresh,
                        original=original,
                        mutation=mutation,
                        action_job_id=action_job_id,
                        checkpoint=checkpoint,
                    )
                historical_headers = {
                    "Authorization": operator_authorization,
                    "X-Tenant-ID": served.TENANT,
                }
                historical = historical_reader.get(result_path, headers=historical_headers)
                assert ledger.snapshot().invocation_reservations == reservations
                assert historical.status_code == 200, historical.text
                replayed = RunModelInputUseN5SuccessorResponse.model_validate(historical.json())
                assert replayed.result == selected, historical.text

                decision_id = ArtifactID.model_validate(execution_body["decision_ref"])
                signature = fresh._sig_path(decision_id)
                withheld_signature = tmp_path / "withheld-successor-approval-signature"
                signature.rename(withheld_signature)
                try:
                    unsigned = historical_reader.get(result_path, headers=historical_headers)
                    assert unsigned.status_code == 200, unsigned.text
                    unverified = RunModelInputUseN5SuccessorResponse.model_validate(
                        unsigned.json()
                    ).result
                    assert unverified.action_status == "completed"
                    assert unverified.result_status == "not_established"
                    assert unverified.limitation_code == (
                        "model_input_use_history_approval_not_established"
                    )
                    assert unverified.simulation_result_ref is None
                    assert unverified.result_body is None
                finally:
                    withheld_signature.rename(signature)
        finally:
            registry_path.write_bytes(registry_bytes)
