from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
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
