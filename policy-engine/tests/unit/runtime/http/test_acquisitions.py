from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from polisyos.core import artifacts, canon
from polisyos.core.run.context import RunContext
from polisyos.core.security.identity import PolicyOSRole
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.data_forge.read_api import catalog as catalog_api
from polisyos.runtime.http import deployment_security as security
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.services import acquisition_surface_execution
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionRouteMutationRequest,
)
from polisyos.runtime.quality import substrate_registry
from polisyos.runtime.quality.agent_action_authority import (
    AGENT_ACTION_DECISION_ARTIFACT_KIND,
    AgentActionAuthorityDecision,
)
from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref
from tests._helpers import acquisition_chain
from tests._helpers import acquisition_served_history as served_fixture
from tests._helpers.acquisition_chain import make_wdi_port_case
from tests._helpers.acquisition_human_decision import persist_signed, prepare_human_decision
from tests._helpers.acquisition_production import (
    install_fixture_wdi_cost_basis,
    intercepted_wdi_transport,
    persist_wdi_route,
    resolve_completed_wdi_route,
)
from tests.unit.runtime.quality.test_agent_action_authority import _mandate_authority_evidence

RUN_ID = "run-runtime-mirror-acquisition-route"


def _decision_refs(control: Any) -> frozenset[str]:
    snapshot = served_fixture._within_fixture_owner(
        control._artifact_store.manifest_inventory_snapshot,
        kind=AGENT_ACTION_DECISION_ARTIFACT_KIND,
    )
    assert snapshot.verdict == "pass"
    return frozenset(str(entry.manifest.artifact_id) for entry in snapshot.entries)


def _job_events(control: Any, *, run_id: str, job_id: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        (record.event.event_id, record.event.event_type)
        for record in control._diagnostic_event_log.list_events(
            run_id=run_id,
            job_id=job_id,
            limit=200,
        )
    )


def test_execute_route_binds_current_tuple_and_persists_allowed_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real protected POST admits only the selected route and records its reservation."""
    tenant_id = served_fixture.TENANT
    cell_id = served_fixture.CELL
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_METRICS_PORT", "0")
    # The whole fenced fixture write takes ~1.6s; retain a bounded local budget.
    monkeypatch.setenv("POLISYOS_RUNTIME_CONTROL_STORE_TIMEOUT_SECONDS", "10")
    install_fixture_wdi_cost_basis(monkeypatch)

    catalog_root = tmp_path / "retrieval-catalog"
    catalog_api.build_slice0_fixture_catalog_graph(catalog_root).close()
    default_catalog_paths = substrate_registry.default_substrate_catalog_paths
    startup_root = Path.cwd().resolve()
    monkeypatch.setattr(
        substrate_registry,
        "default_substrate_catalog_paths",
        lambda root: (
            replace(default_catalog_paths(root), l1_dcat_path=catalog_root / "catalog.duckdb")
            if Path(root).resolve() == startup_root
            else default_catalog_paths(root)
        ),
    )

    trust = served_fixture._ExternalTrust(tmp_path)
    port_patch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        acquisition_chain,
        "intercepted_wdi_transport",
        lambda patch: intercepted_wdi_transport(patch, allow_loopback=True),
    )
    cases: list[Any] = []
    signers, identities = served_fixture._key_config(tmp_path, trust)
    cas_root = tmp_path / "cas"
    closure = None
    route_request: AcquisitionRouteMutationRequest | None = None
    route_path = ""
    route_template = "/api/v1/runs/{run_id}/acquisition-routes/{route_id}"

    def app():
        return create_runtime_api_app(
            cas_root=cas_root,
            core_runs_root=cas_root / "runs",
            deployment_security=security.build_deployment_security(
                security.DeploymentSecurityConfig.from_mapping(trust.raw)
            ),
            enable_security_middlewares=True,
            enable_csrf_protection=False,
        )

    try:
        with TestClient(app()) as client:
            container = client.app.state.runtime_container
            control = container.control_service
            asyncio.run(
                persist_wdi_route(
                    control,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                    run_id=RUN_ID,
                    job_id="job-runtime-mirror-route-source",
                )
            )
            closure, route_request = served_fixture._within_fixture_owner(
                resolve_completed_wdi_route,
                control,
                run_id=RUN_ID,
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                registry = control._artifact_store.put_json(
                    {"fixture": "synthetic acquisition route owner"},
                    artifacts.ArtifactWriteOptions(
                        kind="test.registry",
                        media_type="application/json",
                    ),
                )
                RunContext.start(
                    store=control._artifact_store,
                    registry_bundle=registry,
                    run_dir=cas_root / "runs" / RUN_ID,
                    run_id=RUN_ID,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                ).finalize()
            route_path = f"{route_template.format(run_id=RUN_ID, route_id=closure.route_id)}"
            job_id = AcquisitionActionService._job_id(closure, route_request)
            decision_refs_before = _decision_refs(control)
            events_before = _job_events(control, run_id=RUN_ID, job_id=job_id)
            assert control._control_store.get_job(job_id) is None
            assert events_before == ()

            missing_step_up = client.post(
                route_path + "/execute",
                content=route_request.model_dump_json().encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {trust.tokens['acquisition-operator']}",
                    "X-Tenant-ID": tenant_id,
                    "Content-Type": "application/json",
                },
            )
            assert missing_step_up.status_code == 403
            assert missing_step_up.json()["code"] == "step_up_required"
            assert _decision_refs(control) == decision_refs_before
            assert _job_events(control, run_id=RUN_ID, job_id=job_id) == events_before
            assert control._control_store.get_job(job_id) is None

            mismatched_request = route_request.model_copy(
                update={"route_projection_hash": "sha256:" + "f" * 64}
            )
            mismatch, _ = trust.post(
                client,
                route_path + "/execute",
                mismatched_request.model_dump(mode="json"),
                route=route_template + "/execute",
            )
            assert mismatch.status_code == 409, mismatch.text
            assert mismatch.json()["code"] == "acquisition_route_revalidation_required"
            assert _decision_refs(control) == decision_refs_before
            assert _job_events(control, run_id=RUN_ID, job_id=job_id) == events_before
            assert control._control_store.get_job(job_id) is None

            preflight, resource_digest = trust.post(
                client,
                route_path + "/decision-request",
                route_request.model_dump(mode="json"),
                route=route_template + "/decision-request",
            )
            assert preflight.status_code == 200, preflight.text
            source_ref = preflight.json()["authority_decision_ref"]
            source = AgentActionAuthorityDecision.model_validate(
                canon.from_canonical_bytes(
                    served_fixture._within_fixture_owner(
                        control._artifact_store.get_bytes,
                        source_ref,
                    )
                )
            )
            assert source.outcome == "refused"
            assert "delegation_contract_not_persisted" in source.refusal_reasons

            now = datetime.now(UTC)
            job_id = AcquisitionActionService._job_id(closure, route_request)
            contract = served_fixture._contract()
            envelope = contract.action_envelopes[0].model_copy(
                update={
                    "mandate_owner_ref": identities["owner"],
                    "authorized_subject": "acquisition-operator",
                    "authorized_runtime_roles": (PolicyOSRole.ANALYST,),
                    "required_tenant_id": tenant_id,
                    "required_resource_digest": resource_digest,
                    "valid_from": now - timedelta(minutes=1),
                    "valid_until": now + timedelta(hours=1),
                }
            )
            contract = contract.model_copy(
                update={
                    "mandate_owner_ref": identities["owner"],
                    "action_envelopes": (envelope,),
                }
            )
            context = {
                "tenant_id": tenant_id,
                "cell_id": cell_id,
                "run_id": RUN_ID,
                "job_id": job_id,
                "now": now,
            }
            contract_ref = served_fixture._within_fixture_owner(
                persist_signed,
                control,
                contract,
                kind=served_fixture.authority.DELEGATION_CONTRACT_ARTIFACT_KIND,
                schema_name="polisyos.runtime.DelegationContract",
                schema_version=(
                    served_fixture.authority.LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION
                ),
                signer=signers["owner"],
                signer_identity=identities["owner"],
                **context,
            )
            currentness = _mandate_authority_evidence(
                owner_ref=identities["owner"],
                signer_identity=identities["current"],
                rule_version_ref=contract.rule_version_ref,
                effective_from=now - timedelta(minutes=1),
                effective_until=now + timedelta(hours=1),
            )
            currentness_ref = served_fixture._within_fixture_owner(
                persist_signed,
                control,
                currentness,
                kind=served_fixture.authority.CURRENT_MANDATE_OWNER_ARTIFACT_KIND,
                schema_name="polisyos.runtime.CurrentMandateOwnerEvidence",
                schema_version=served_fixture.authority.CURRENT_MANDATE_OWNER_SCHEMA_VERSION,
                signer=signers["current"],
                signer_identity=identities["current"],
                **context,
            )
            information = served_fixture._within_fixture_owner(
                control._artifact_store.put_json,
                {
                    "fixture_scope": "synthetic_acquisition_review",
                    "limitation": "The route fixture is not an external WDI observation.",
                },
                artifacts.ArtifactWriteOptions(
                    kind="test.acquisition.disconfirming",
                    media_type="application/json",
                ),
            )
            slot = {
                "tenant_id": tenant_id,
                "cell_id": cell_id,
                "run_id": RUN_ID,
                "route_id": closure.route_id,
                "resource_digest": resource_digest,
                "delegation_contract_ref": contract_ref,
                "mandate_owner_ref": identities["owner"],
                "delegation_public_key_path": str(tmp_path / "owner.pub"),
                "current_mandate_evidence_ref": currentness_ref,
                "current_mandate_signer_identity": identities["current"],
                "current_mandate_public_key_path": str(tmp_path / "current.pub"),
                "verifier_provenance_ref": "fixture://appointment-registry",
                "decision_information_refs": [information.model_dump(mode="json")],
                "decision_disconfirming_refs": [information.model_dump(mode="json")],
            }
            trust.raw["acquisition_authority"]["mandates"] = [slot]

        def build_fixture_port(
            *,
            control_service,
            world_growth_config=None,
            epoch_deployment=None,
        ):
            del world_growth_config, epoch_deployment
            case = served_fixture._within_fixture_owner(
                make_wdi_port_case,
                tmp_path / "wdi",
                port_patch,
                control=control_service,
                closure=closure,
                previous_case=cases[-1] if cases else None,
            )
            cases.append(case)
            return case.port

        monkeypatch.setattr(
            acquisition_surface_execution,
            "build_production_world_bank_wdi_execution_port",
            build_fixture_port,
        )

        with TestClient(app()) as client:
            container = client.app.state.runtime_container
            control = container.control_service
            source_response, selected_digest = trust.post(
                client,
                route_path + "/decision-request",
                route_request.model_dump(mode="json"),
                route=route_template + "/decision-request",
            )
            assert source_response.status_code == 200, source_response.text
            assert selected_digest == resource_digest
            source_ref = source_response.json()["authority_decision_ref"]
            source = AgentActionAuthorityDecision.model_validate(
                canon.from_canonical_bytes(
                    served_fixture._within_fixture_owner(
                        control._artifact_store.get_bytes,
                        source_ref,
                    )
                )
            )
            assert source.refusal_reasons == ("human_decision_missing",)

            gate = served_fixture._within_fixture_owner(
                prepare_human_decision,
                control,
                container.human_decision_service,
                source_ref,
                tenant_id=tenant_id,
                cell_id=cell_id,
                run_id=RUN_ID,
                signers=signers,
                identities=identities,
                now=datetime.now(UTC),
                audit_path=cas_root / "runtime" / "audit" / "access.jsonl",
            )
            decision_body = {
                name: value
                for name, value in gate.model_dump(mode="json").items()
                if name not in {"tenant_id", "run_id", "exposure_session_ref"}
            }
            decision_body.update(
                action="approve",
                decision_mode="ordinary",
                accountability_statement="I accept this bounded synthetic acquisition fixture.",
                dissent_statement="Its non-production measurement limitation remains explicit.",
            )
            human_response, _ = trust.post(
                client,
                f"/api/v1/runs/{RUN_ID}/human-decisions",
                decision_body,
                route="/api/v1/runs/{run_id}/human-decisions",
                subject="human-reviewer-1",
                extra_headers={"X-PolicyOS-Human-Decision-Exposure": gate.exposure_session_ref},
            )
            assert human_response.status_code == 201, human_response.text
            human_ref = human_response.json()["record_ref"]
            slot["human_decision_record_ref"] = human_ref

        with TestClient(app()) as client:
            container = client.app.state.runtime_container
            control = container.control_service
            response, selected_digest = trust.post(
                client,
                route_path + "/execute",
                route_request.model_dump(mode="json"),
                route=route_template + "/execute",
            )
            assert response.status_code in {200, 202}, response.text
            from polisyos.runtime.http.services.acquisition_action_service import (
                AcquisitionExecutionResponse,
            )

            execution = AcquisitionExecutionResponse.model_validate(response.json())
            assert execution.run_id == RUN_ID
            assert execution.route_id == closure.route_id
            assert execution.job_id == job_id
            assert selected_digest == resource_digest

            job = control._control_store.get_job(job_id)
            assert job is not None and job.state == "pending"
            payload = canon.from_canonical_bytes(
                served_fixture._within_fixture_owner(
                    control._artifact_store.get_bytes,
                    job.payload_ref,
                )
            )
            assert payload["route_id"] == closure.route_id
            assert payload["tenant_id"] == tenant_id
            assert payload["cell_id"] == cell_id
            decision_ref = payload["decision_ref"]
            decision = AgentActionAuthorityDecision.model_validate(
                canon.from_canonical_bytes(
                    served_fixture._within_fixture_owner(
                        control._artifact_store.get_bytes,
                        decision_ref,
                    )
                )
            )
            assert decision.outcome == "allowed"
            assert decision.human_decision_record_ref == human_ref
            assert decision.bound_resource_digest == resource_digest
            report = served_fixture._within_fixture_owner(
                reconcile_authority_ref,
                artifact_store=control._artifact_store,
                event_log=control._diagnostic_event_log,
                cas_ref=decision_ref,
                expected_tenant_id=tenant_id,
                expected_cell_id=cell_id,
                expected_run_id=RUN_ID,
                expected_job_id=job_id,
            )
            assert report.status == "pass"
            assert report.durable_event_id is not None
            job_events = control._diagnostic_event_log.list_events(
                run_id=RUN_ID,
                job_id=job_id,
                limit=200,
            )
            assert any(row.event.event_id == report.durable_event_id for row in job_events)
            # The queued action is intentionally nonterminal until its worker runs.
            # Resolve the persisted phase history directly against the selected closure.
            action_generation = served_fixture._within_fixture_owner(
                container.acquisition_action_service._action_generation,
                closure,
                job_id,
            )
            phase_seed = container.acquisition_action_service._phase_receipt(
                action_generation=action_generation,
                closure=closure,
                job_id=job_id,
                decision_ref=decision_ref,
                receipt_phase="requested",
                predecessor_receipt_ref=None,
                owner_receipt_refs=(),
            )
            head = served_fixture._within_fixture_owner(
                control.acquisition_route_sink.get_head, phase_seed
            )
            assert head is not None and head.receipt_phase == "requested"
            assert any(row.event.event_id == head.durable_event_id for row in job_events)
            assert cases[-1].transport_calls == []
    finally:
        port_patch.undo()
        trust.close()
        trust.close()


def test_configured_ordinary_offers_keep_signed_acceptance_after_expiry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Accept two real offers through PA2, then reopen them as historical evidence."""
    from polisyos.pdc import OperationInvocationRecord
    from polisyos.runtime.http.services.acquisition_action_service import (
        AcquisitionActionServiceError,
    )
    from polisyos.runtime.quality import acquisition_route_loop as route_owner
    from polisyos.runtime.quality import generation_cycle
    from polisyos.runtime.quality.acquisition_planner import (
        OrdinaryAcquisitionOffer,
        OrdinaryAcquisitionOfferScope,
    )
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthBridge,
        AcquisitionWorldGrowthConfig,
        AcquisitionWorldGrowthRoute,
    )
    from polisyos.scientist import BudgetState
    from tests._helpers.acquisition_epoch_production import production_admission_inputs
    from tests.unit.runtime.quality.test_acquisition_planner_source_offers import (
        _controlled_supplier_refs,
    )
    from tests.unit.runtime.quality.test_substrate_registry import _write_substrate_catalog_fixture

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_METRICS_PORT", "0")
    monkeypatch.setenv("POLISYOS_RUNTIME_CONTROL_STORE_TIMEOUT_SECONDS", "10")
    monkeypatch.setattr(generation_cycle, "_N7_SOURCE_SEMANTIC_EMISSION_ENABLED", True)
    install_fixture_wdi_cost_basis(monkeypatch)
    substrate = tmp_path / "substrate"
    _write_substrate_catalog_fixture(substrate)
    trust = served_fixture._ExternalTrust(tmp_path)
    subjects = ("acquisition-operator", "acquisition-operator-2")
    trust.raw["service_principals"].append(
        {**trust.raw["service_principals"][0], "subject": subjects[1]}
    )
    trust.tokens[subjects[1]] = trust.authorization_header(subjects[1]).removeprefix("Bearer ")
    signers, identities = served_fixture._key_config(tmp_path, trust)
    cas_root = tmp_path / "cas"
    run_id = "run-ordinary-signed-offers"
    tenant_id, cell_id = served_fixture.TENANT, served_fixture.CELL
    route_template = "/api/v1/runs/{run_id}/acquisition-routes/{route_id}"
    now = datetime.now(UTC)
    expiry = now + timedelta(hours=1)
    transport_calls = intercepted_wdi_transport(monkeypatch, allow_loopback=True)

    def app():
        return create_runtime_api_app(
            cas_root=cas_root,
            core_runs_root=cas_root / "runs",
            deployment_security=security.build_deployment_security(
                security.DeploymentSecurityConfig.from_mapping(trust.raw)
            ),
            enable_security_middlewares=True,
            enable_csrf_protection=False,
        )

    def reader(control, **kwargs):
        return route_owner.AcquisitionRouteLoop(
            control_store=control._control_store,
            artifact_store=control._artifact_store,
            event_log=control._diagnostic_event_log,
            core_source_resolver=control.resolve_completed_control_job_core_run_source,
            tenant_id=tenant_id,
            cell_id=cell_id,
            action_outcome_reader=control.acquisition_route_sink,
            **kwargs,
        )

    def assert_same_offer(
        actual: OrdinaryAcquisitionOffer | None, expected: OrdinaryAcquisitionOffer
    ) -> None:
        assert actual is not None
        assert actual.content_hash == expected.content_hash
        assert actual.model_dump(mode="json") == expected.model_dump(mode="json")

    try:
        with TestClient(app()) as client:
            control = client.app.state.runtime_container.control_service
            original, original_request = asyncio.run(
                persist_wdi_route(
                    control,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                    run_id=run_id,
                    generation_cycle_repo_root=substrate,
                )
            )
            store = control._artifact_store
            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                authority, (left_ref, right_ref, _, _) = _controlled_supplier_refs(
                    tmp_path / "offers", store
                )
                legacy = reader(control).resolve_current_ordinary_route(run_id=run_id)
                assert legacy.route_id == original.route_id and legacy.ordinary_offer is None
                origin = reader(control)._resolve_verified_origin(run_id=run_id)
                gap = origin.source_requirement
                assert gap is not None and origin.planner_record.compiled_requirement_ref
                constraints = acquisition_surface_execution._constraints_from_live_variable_route(
                    original
                )
                scope = OrdinaryAcquisitionOfferScope(
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                    run_id=run_id,
                    source_job_id=original.source_job_id,
                    design_problem_ref=original.design_problem_ref,
                    candidate_id=original.route_source_cycle.selected_candidate_ref,
                    compiled_ref=origin.selected_compiled_ref,
                    scenario_id=original.design_problem.design_problem_id,
                    planner_report_ref=artifacts.artifact_ref_for_manifest(
                        store.get_manifest(origin.report_ref)
                    ),
                    planner_record_id=origin.planner_record.acquisition_id,
                    compiled_requirement_ref=origin.planner_record.compiled_requirement_ref,
                    source_gap_id=gap.requirement_gap_id,
                    canonical_variable_id="government.balance",
                    canonical_unit="percent_gdp",
                    country_code=constraints.country_code,
                    year=constraints.start_year,
                )
                offers = tuple(
                    OrdinaryAcquisitionOffer(
                        scope=scope,
                        supplier_ref=ref,
                        cost_basis_hash=original.cost_basis_hash,
                        effective_at=now - timedelta(minutes=1),
                        expires_at=expiry,
                    )
                    for ref in (left_ref, right_ref)
                )
                configuration = route_owner.OrdinaryAcquisitionOfferConfiguration(
                    authority=authority,
                    canonical_unit="percent_gdp",
                    constraints=constraints,
                    offers=offers,
                )
                selected = reader(
                    control, ordinary_offer_configuration=configuration
                ).resolve_current_ordinary_routes(run_id=run_id)
                # The no-effect enqueue witness never activates either prepared epoch.
                epoch = production_admission_inputs(
                    tmp_path / "owners",
                    store=store,
                    authority=authority,
                    overlay_path=tmp_path / "unused-overlay.duckdb",
                    epoch_history_root=tmp_path / "unused-history",
                )
                routes = tuple(
                    AcquisitionWorldGrowthRoute(
                        tenant_id=tenant_id,
                        cell_id=cell_id,
                        run_id=run_id,
                        route_id=closure.route_id,
                        design_problem_ref=closure.design_problem_ref,
                        epoch_id=index,
                        epoch_scope_identity=epoch["epoch_scope_identity"],
                        authority_purpose=epoch["authority_purpose"],
                        valid_effect_coordinate_evidence_ref=epoch[
                            "valid_effect_coordinate_evidence_ref"
                        ],
                        visibility_knowledge_cutoff_evidence_ref=epoch[
                            "visibility_knowledge_cutoff_evidence_ref"
                        ],
                        purpose_admission_cutoff_evidence_ref=epoch[
                            "purpose_admission_cutoff_evidence_ref"
                        ],
                        facet_source_refs=epoch["facet_source_refs"],
                        reentry_budget_usd=Decimal("0.10"),
                    )
                    for index, closure in enumerate(selected, 1)
                )
                config = AcquisitionWorldGrowthConfig(routes=routes, ordinary_offers=offers)
                registry = store.put_json(
                    {"fixture": "synthetic ordinary acquisition source"},
                    artifacts.ArtifactWriteOptions(
                        kind="test.registry", media_type="application/json"
                    ),
                )
                RunContext.start(
                    store=store,
                    registry_bundle=registry,
                    run_dir=cas_root / "runs" / run_id,
                    run_id=run_id,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                ).finalize()

        def installed_port(*, control_service, world_growth_config=None, epoch_deployment=None):
            del world_growth_config
            bridge = AcquisitionWorldGrowthBridge(
                config=config,
                repo_root=authority.repo_root,
                runtime_root=cas_root,
                authority=authority,
                artifact_store=control_service._artifact_store,
                event_log=control_service._diagnostic_event_log,
                control_store=control_service._control_store,
                action_head_sink=control_service.acquisition_route_sink,
                source_control_service=control_service,
                epoch_deployment=epoch_deployment,
            )
            return acquisition_surface_execution.WorldBankWDIAcquisitionExecutionPort(
                authority=authority,
                registry=catalog_api.AcquisitionAuthorityRegistry.model_validate_json(
                    authority.registry_path.read_bytes()
                ),
                provision=authority.provision,
                provision_content_sha256=authority.provision_content_sha256,
                runtime_state_root=cas_root,
                artifact_store=control_service._artifact_store,
                world_growth_bridge=bridge,
            )

        monkeypatch.setattr(
            acquisition_surface_execution,
            "build_production_world_bank_wdi_execution_port",
            installed_port,
        )
        selections = tuple(
            (
                closure,
                original_request.model_copy(update={"route_projection_hash": closure.route_id}),
                route_template.format(run_id=run_id, route_id=closure.route_id),
                subject,
            )
            for closure, subject in zip(selected, subjects, strict=True)
        )
        mandates, digests = [], []
        with TestClient(app()) as client:
            control = client.app.state.runtime_container.control_service
            routes_response = client.get(
                f"/api/v1/runs/{run_id}/acquisition-routes",
                headers={
                    "Authorization": trust.authorization_header("acquisition-operator"),
                    "X-Tenant-ID": tenant_id,
                },
            )
            assert routes_response.status_code == 200, routes_response.text
            assert {route["route_id"] for route in routes_response.json()["routes"]} == {
                closure.route_id for closure in selected
            }
            for closure, request, path, subject in selections:
                refused, digest = trust.post(
                    client,
                    path + "/decision-request",
                    request.model_dump(mode="json"),
                    route=route_template + "/decision-request",
                    subject=subject,
                )
                assert refused.status_code == 200, refused.text
                slot, _ = served_fixture._appoint_served_acquisition_mandate(
                    control,
                    closure,
                    request,
                    digest,
                    tmp_path=tmp_path,
                    signers=signers,
                    identities=identities,
                    actor_subject=subject,
                )
                mandates.append(slot)
                digests.append(digest)
        trust.raw["acquisition_authority"]["mandates"] = mandates

        with TestClient(app()) as client:
            for (closure, request, _path, subject), digest, slot in zip(
                selections, digests, mandates, strict=True
            ):
                _refusal, human_ref = served_fixture._approve_served_acquisition_request(
                    client,
                    request,
                    digest,
                    closure=closure,
                    trust=trust,
                    signers=signers,
                    identities=identities,
                    cas_root=cas_root,
                    actor_subject=subject,
                )
                slot["human_decision_record_ref"] = human_ref

        accepted = []
        with TestClient(app()) as client:
            container = client.app.state.runtime_container
            control = container.control_service
            for (closure, request, path, subject), offer in zip(selections, offers, strict=True):
                allowed, _ = trust.post(
                    client,
                    path + "/execute",
                    request.model_dump(mode="json"),
                    route=route_template + "/execute",
                    subject=subject,
                )
                assert allowed.status_code in {200, 202}, allowed.text
                job_id = allowed.json()["job_id"]
                assert_same_offer(closure.ordinary_offer, offer)
                job = control._control_store.get_job(job_id)
                assert job is not None and job.state == "pending"
                with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                    actor_scope, _ = control._control_store._reconcile_control_job_creation_envelope(
                        job
                    )
                    assert actor_scope.actor_authenticated and actor_scope.actor_subject == subject
                    assert job.payload_ref is not None
                    payload = control._load_payload_ref(
                        job.payload_ref, kind="runtime.control_job_payload.acquisition"
                    )
                    invocation = OperationInvocationRecord.model_validate(payload["invocation"])
                    assert invocation.parameters["ordinary_acquisition_offer_hash"] == (
                        offer.content_hash
                    )
                    assert "ordinary_acquisition_offer" not in invocation.parameters
                    assert_same_offer(
                        AcquisitionActionService._read_job_ordinary_offer(payload, invocation),
                        offer,
                    )
                    without_offer = dict(payload)
                    del without_offer["ordinary_acquisition_offer"]
                    foreign_offer = next(
                        other for other in offers if other.content_hash != offer.content_hash
                    )
                    with_foreign_offer = {
                        **payload,
                        "ordinary_acquisition_offer": foreign_offer.model_dump(mode="json"),
                    }
                    for wrong_payload in (without_offer, with_foreign_offer):
                        with pytest.raises(
                            AcquisitionActionServiceError,
                            match="acquisition_job_ordinary_offer_binding_mismatch",
                        ):
                            AcquisitionActionService._read_job_ordinary_offer(
                                wrong_payload, invocation
                            )
                    (head,) = control._control_store.list_acquisition_action_heads(
                        tenant_id=tenant_id,
                        cell_id=cell_id,
                        run_id=run_id,
                        source_job_id=closure.source_job_id,
                        route_id=closure.route_id,
                    )
                    assert head.job_id == job_id and head.receipt_phase == "requested"
                    assert head.action_generation == 1
                    identity = (
                        tenant_id,
                        cell_id,
                        run_id,
                        closure.source_job_id,
                        closure.route_id,
                        job_id,
                    )
                    digest = sha256(canon.to_canonical_bytes(identity)).hexdigest()
                    assert head.durable_event_id == f"evt_acquisition_1_ordinary_{digest}_requested"
                    assert_same_offer(
                        reader(control).resolve_recorded_ordinary_route(head=head).ordinary_offer,
                        offer,
                    )
                accepted.append(head)
            assert accepted[0].job_id != accepted[1].job_id
            assert accepted[0].durable_event_id != accepted[1].durable_event_id

        class ExpiredQuoteClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return expiry if tz is None else expiry.astimezone(tz)

        monkeypatch.setattr(route_owner, "datetime", ExpiredQuoteClock)
        with TestClient(app()) as client:
            control = client.app.state.runtime_container.control_service
            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                owner = reader(control)
                assert owner.resolve_current_ordinary_routes(run_id=run_id) == ()
                with pytest.raises(
                    route_owner.AcquisitionRouteClosureError, match="acquisition_route_not_current"
                ):
                    owner.resolve_current_ordinary_route(run_id=run_id, route_id=original.route_id)
                for head, offer in zip(accepted, offers, strict=True):
                    assert_same_offer(
                        owner.resolve_recorded_ordinary_route(head=head).ordinary_offer, offer
                    )
                with pytest.raises(
                    route_owner.AcquisitionRouteClosureError,
                    match="ordinary_acquisition_recorded_offer_refused",
                ):
                    owner.resolve_recorded_ordinary_route(
                        head=replace(accepted[0], route_id=accepted[1].route_id)
                    )
                selected_blob, _ = control._artifact_store._paths(
                    offers[0].supplier_ref.artifact_id
                )
                assert selected_blob.is_relative_to(tmp_path)
                assert selected_blob.is_file() and not selected_blob.is_symlink()
                parked = selected_blob.with_suffix(".offer-proof-removed")
                assert not parked.exists()
                selected_blob.rename(parked)
                try:
                    with pytest.raises(
                        route_owner.AcquisitionRouteClosureError,
                        match="ordinary_acquisition_recorded_offer_refused",
                    ):
                        owner.resolve_recorded_ordinary_route(head=accepted[0])
                    assert_same_offer(
                        owner.resolve_recorded_ordinary_route(head=accepted[1]).ordinary_offer,
                        offers[1],
                    )
                finally:
                    parked.rename(selected_blob)
                assert_same_offer(
                    owner.resolve_recorded_ordinary_route(head=accepted[0]).ordinary_offer,
                    offers[0],
                )
            _closure, request, path, subject = selections[0]
            refused, _ = trust.post(
                client,
                path + "/execute",
                request.model_dump(mode="json"),
                route=route_template + "/execute",
                subject=subject,
            )
            assert refused.status_code == 404, refused.text
            assert refused.json()["code"] == "acquisition_route_not_current"
            assert all(
                control._control_store.get_job(head.job_id).state == "pending" for head in accepted
            )
        # Use the actual creator envelope and a real lease to distinguish the
        # offered route at the next owner boundary. All branches stop before
        # an overlay or numerical owner can be entered.
        with monkeypatch.context() as clock, TestClient(app()) as client:
            clock.setattr(route_owner, "datetime", datetime)
            control = client.app.state.runtime_container.control_service
            store = control._control_store
            worker_id = "fixture-ordinary-route-reentry"
            lease = store.lease_next_job(worker_id=worker_id, lease_seconds=60)
            assert lease is not None and lease.kind == "acquisition"
            selected_index = next(
                index for index, head in enumerate(accepted) if head.job_id == lease.job_id
            )
            selected_route = selections[selected_index][0]
            other_route = selections[1 - selected_index][0]
            controller = object.__new__(generation_cycle.GenerationCycleController)
            controller._artifact_store = control._artifact_store
            problem = selected_route.design_problem_basis
            different_problem = problem.model_copy(
                update={"design_problem_id": problem.design_problem_id + "-different"}
            )
            kwargs = {
                "original_run": selected_route.generation_run,
                "source_cycle": selected_route.source_cycle,
                "problem": different_problem,
                "overlay_receipt": None,
                "observation_projection": None,
                "baseline_path": tmp_path / "not-opened-baseline.duckdb",
                "overlay_path": tmp_path / "not-opened-overlay.duckdb",
                "budget_state": BudgetState(),
            }
            with (
                tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id),
                store.job_execution_fence(
                    job_id=lease.job_id, worker_id=worker_id, attempt=lease.attempt
                ),
            ):
                for route_id, code in (
                    (selected_route.route_id, "acquisition_reentry_route_source_mismatch"),
                    (other_route.route_id, "acquisition_reentry_ordinary_route_not_admitted"),
                    (None, "acquisition_reentry_route_owner_not_established"),
                ):
                    with pytest.raises(generation_cycle.GenerationCycleError, match=code):
                        asyncio.run(
                            controller.reenter_after_active_acquisition_overlay(
                                **kwargs, source_control_service=control, action_route_id=route_id
                            )
                        )
                assert selected_route.ordinary_offer is not None
                with pytest.raises(
                    generation_cycle.GenerationCycleError,
                    match="native_derivation_reentry_selection_incomplete",
                ):
                    asyncio.run(
                        controller.reenter_after_active_acquisition_overlay(
                            **kwargs,
                            source_control_service=control,
                            native_input_collection_ref=(
                                selected_route.ordinary_offer.scope.compiled_ref
                            ),
                        )
                    )
                with pytest.raises(
                    generation_cycle.GenerationCycleError,
                    match="acquisition_reentry_case_binding_mismatch",
                ):
                    asyncio.run(controller.reenter_after_active_acquisition_overlay(**kwargs))
        assert transport_calls == []
    finally:
        trust.close()


def test_external_trust_scopes_fresh_credentials_to_authority_exchange(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refresh identity, preserve DS20 within approval, and scope its JTI."""
    def decode(header: str) -> dict[str, object]:
        return served_fixture.jwt.decode(
            header.removeprefix("Bearer "),
            trust.key.public_key(),
            algorithms=["RS256"],
            audience="polisyos-runtime",
            issuer="https://idp.example",
        )

    expired_issued_at = int(served_fixture.time.time()) - 7200
    with monkeypatch.context() as stale_clock:
        stale_clock.setattr(served_fixture.time, "time", lambda: expired_issued_at)
        trust = served_fixture._ExternalTrust(tmp_path)
    try:
        old_token = trust.tokens["acquisition-operator"]
        old_payload = served_fixture.jwt.decode(
            old_token, options={"verify_signature": False}
        )
        with pytest.raises(served_fixture.jwt.ExpiredSignatureError):
            served_fixture.jwt.decode(
                old_token,
                trust.key.public_key(),
                algorithms=["RS256"],
                audience="polisyos-runtime",
                issuer="https://idp.example",
            )

        assert old_payload["exp"] < int(served_fixture.time.time())
        assert old_payload["jti"] == "jwt-acquisition-operator"
        assert trust._request_authorization_header("acquisition-operator") == (
            f"Bearer {old_token}"
        )

        with trust.authorization_exchange("acquisition-operator") as exchange_header:
            exchange_payload = decode(exchange_header)
            assert exchange_payload["exp"] == exchange_payload["iat"] + 3600
            assert exchange_payload["sub"] == old_payload["sub"]
            assert exchange_payload["tenant_id"] == old_payload["tenant_id"]
            assert exchange_payload["jti"] != old_payload["jti"]
            assert trust._request_authorization_header("acquisition-operator") == (
                exchange_header
            )
            assert trust._request_authorization_header(
                "acquisition-operator", explicit_authorization="Bearer explicit-control"
            ) == "Bearer explicit-control"

            # Independent readers deliberately bypass the protected exchange.
            reader_header = trust.authorization_header("acquisition-operator")
            reader_payload = decode(reader_header)
            assert reader_payload["sub"] == exchange_payload["sub"]
            assert reader_payload["jti"] != exchange_payload["jti"]
            assert reader_header != exchange_header

            with trust.authorization_exchange("human-reviewer-1") as reviewer_header:
                reviewer_payload = decode(reviewer_header)
                assert reviewer_payload["sub"] == "human-reviewer-1"
                assert trust._request_authorization_header("human-reviewer-1") == (
                    reviewer_header
                )

            with trust.authorization_exchange("acquisition-operator") as nested_header:
                nested_payload = decode(nested_header)
                assert nested_header != exchange_header
                assert nested_payload["sub"] == exchange_payload["sub"]
                assert nested_payload["jti"] != exchange_payload["jti"]
                assert trust._request_authorization_header("acquisition-operator") == (
                    nested_header
                )
            assert trust._request_authorization_header("acquisition-operator") == (
                exchange_header
            )

            with pytest.raises(RuntimeError, match="fixture exchange probe"), trust.authorization_exchange(
                "human-reviewer-1"
            ):
                raise RuntimeError("fixture exchange probe")
            assert trust._request_authorization_header("acquisition-operator") == (
                exchange_header
            )
            assert trust._request_authorization_header("human-reviewer-1") == (
                f"Bearer {trust.tokens['human-reviewer-1']}"
            )

        assert trust._request_authorization_header("acquisition-operator") == (
            f"Bearer {old_token}"
        )
        with trust.authorization_exchange("acquisition-operator") as next_header:
            next_payload = decode(next_header)
            assert next_header != exchange_header
            assert next_payload["jti"] != exchange_payload["jti"]
            assert trust._request_authorization_header("acquisition-operator") == (
                next_header
            )
        assert trust._request_authorization_header("acquisition-operator") == (
            f"Bearer {old_token}"
        )
    finally:
        trust.close()
