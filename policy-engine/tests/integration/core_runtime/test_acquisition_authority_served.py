"""Real deployment/HTTP/DS9/durable-worker acquisition authority bridge."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from polisyos.core import artifacts, canon
from polisyos.core.run.context import RunContext
from polisyos.core.security.identity import PolicyOSRole
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.data_forge.read_api import catalog as catalog_api
from polisyos.runtime.http import deployment_security as security
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.quality import agent_action_authority as authority
from polisyos.runtime.quality import substrate_registry
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteLoopReceipt
from tests._helpers.acquisition_production import persist_wdi_route
from tests.integration.core_runtime.test_acquisition_admission_bundle import _contract
from tests.unit.runtime.http.deployment_security_test_support import LocalJWKSStub
from tests.unit.runtime.http.test_runtime_deployment_security import _config_mapping
from tests.unit.runtime.quality.test_agent_action_authority import _mandate_authority_evidence

TENANT = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
CELL = "018f47a0-0000-7000-8000-000000000001"
RUN = "run-acquisition"


def _within_fixture_owner(call, *args, **kwargs):
    """Emit external fixture inputs under their actual tenant/cell ownership."""
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        return call(*args, **kwargs)


def _read_owned_terminal(store, ref):
    """Read the actual terminal schema through scoped immutable CAS ownership."""
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        assert store.get_manifest(ref).kind == "runtime_quality.acquisition_route_loop_receipt"
        return AcquisitionRouteLoopReceipt.model_validate(
            canon.from_canonical_bytes(store.get_bytes(ref))
        )


class _ExternalTrust:
    """Fixture institutional JWT/JWKS/OPA endpoints; runtime verifiers remain real."""

    def __init__(self, tmp_path):
        self.inputs = []
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.jwks = LocalJWKSStub(self.key)
        uri = self.jwks.start()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                outer.inputs.append(
                    json.loads(self.rfile.read(int(self.headers["content-length"])))["input"]
                )
                body = b'{"result":{"allow":true}}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.opa = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.opa.serve_forever, daemon=True)
        self.thread.start()
        self.raw = _config_mapping(tmp_path)
        self.raw["identity_verifier"]["jwks_uri"] = uri
        self.raw["step_up_verifier"]["jwks_uri"] = uri
        self.raw["step_up_verifier"]["allowed_key_ids"] = ["identity-2026-07"]
        self.raw["opa"]["url"] = f"http://127.0.0.1:{self.opa.server_port}"
        self.raw["service_principals"] = [
            {
                "issuer": "https://idp.example",
                "audience": "polisyos-runtime",
                "subject": subject,
                "tenant_id": TENANT,
                "cell_id": CELL,
                "permissions": permissions,
            }
            for subject, permissions in (
                ("acquisition-operator", ["evidence.acquire", "runs.review", "runs.view"]),
                ("human-reviewer-1", ["runs.human_decisions.create", "runs.review", "runs.view"]),
            )
        ]
        now = int(time.time())
        self.tokens = {
            subject: self.encode(
                {
                    "iss": "https://idp.example",
                    "aud": "polisyos-runtime",
                    "sub": subject,
                    "tenant_id": TENANT,
                    "cell_id": CELL,
                    "realm_access": {"roles": ["polisyos_analyst"]},
                    "amr": ["pwd", "mfa"],
                    "iat": now,
                    "exp": now + 3600,
                    "jti": f"jwt-{subject}",
                }
            )
            for subject in ("acquisition-operator", "human-reviewer-1")
        }

    def encode(self, payload):
        return jwt.encode(payload, self.key, algorithm="RS256", headers={"kid": "identity-2026-07"})

    def close(self):
        self.opa.shutdown()
        self.opa.server_close()
        self.thread.join(timeout=5)
        self.jwks.close()

    def post(
        self, client, path, body, *, route, subject="acquisition-operator", extra_headers=None
    ):
        payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
        headers = {
            "Authorization": f"Bearer {self.tokens[subject]}",
            "X-Tenant-ID": TENANT,
            "Content-Type": "application/json",
            **(extra_headers or {}),
        }
        # First request reaches real authorization and intentionally lacks step-up.
        refused = client.post(path, content=payload, headers=headers)
        assert refused.status_code == 403 and refused.json()["code"] == "step_up_required", (
            refused.text
        )
        observed = self.inputs[-1]
        resource = observed["resource"]
        resource_id = resource["artifact_id"]
        digest = "sha256:" + resource_id.rsplit("sha256:", 1)[1]
        now = int(time.time())
        headers["X-PolicyOS-Step-Up"] = self.encode(
            {
                "iss": "https://step-up.example",
                "aud": "polisyos-runtime-step-up",
                "sub": subject,
                "tenant_id": TENANT,
                "jti": str(uuid.uuid4()),
                "iat": now,
                "exp": now + 240,
                "mfa_verified": True,
                "assurance": "fixture-real-signature",
                "method": "POST",
                "route": route,
                "permission": observed["action"]["permission"],
                "resource_id": resource_id,
                "resource_digest": digest,
                "resource_kind": resource["kind"],
                "binding_authority": resource["binding_authority"],
                "body_sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
                "step_up_class": "human_decision"
                if subject == "human-reviewer-1"
                else "acquisition_approval",
            }
        )
        return client.post(path, content=payload, headers=headers), digest


def _key_config(tmp_path, trust):
    families = (
        "owner",
        "current",
        "admission",
        "source",
        "principal",
        "separation",
        "presentation",
        "custody",
    )
    pairs = {name: artifacts.KeyPair.generate() for name in families}
    signers = {name: artifacts.Ed25519Signer(pair.private_key) for name, pair in pairs.items()}
    identities = {name: f"institution://acquisition-fixture/{name}" for name in families}
    for name, pair in pairs.items():
        (tmp_path / f"{name}.pem").write_bytes(pair.private_pem())
        (tmp_path / f"{name}.pub").write_bytes(pair.public_pem())
    from polisyos.runtime.http.services import human_decision_contracts as hdc

    rows = [
        (
            "source",
            authority.AGENT_ACTION_DECISION_ARTIFACT_KIND,
            "AgentActionAuthorityDecision",
            authority.AGENT_ACTION_AUTHORITY_SCHEMA_VERSION,
        ),
        (
            "owner",
            authority.DELEGATION_CONTRACT_ARTIFACT_KIND,
            "DelegationContract",
            authority.LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
        ),
        (
            "admission",
            authority.AGENT_ACTION_ADMISSION_ARTIFACT_KIND,
            "AgentActionAdmissionBundle",
            authority.AGENT_ACTION_ADMISSION_SCHEMA_VERSION,
        ),
        (
            "principal",
            hdc.HUMAN_DECISION_PRINCIPAL_BINDING_ARTIFACT_KIND,
            "HumanDecisionPrincipalBinding",
            hdc.HUMAN_DECISION_PRINCIPAL_BINDING_MANIFEST_VERSION,
        ),
        (
            "separation",
            hdc.REVIEWER_SEPARATION_CREDENTIAL_ARTIFACT_KIND,
            "ReviewerSeparationCredential",
            hdc.REVIEWER_SEPARATION_CREDENTIAL_MANIFEST_VERSION,
        ),
        (
            "presentation",
            hdc.HUMAN_DECISION_PRESENTATION_CONTRACT_ARTIFACT_KIND,
            "HumanDecisionPresentationContract",
            hdc.HUMAN_DECISION_PRESENTATION_CONTRACT_MANIFEST_VERSION,
        ),
        (
            "custody",
            hdc.HUMAN_DECISION_EXPOSURE_SESSION_ARTIFACT_KIND,
            "HumanDecisionExposureSession",
            hdc.HUMAN_DECISION_EXPOSURE_SESSION_MANIFEST_VERSION,
        ),
        (
            "custody",
            hdc.HUMAN_DECISION_EXPOSURE_EVENT_ARTIFACT_KIND,
            "HumanDecisionExposureAuditEvent",
            hdc.HUMAN_DECISION_EXPOSURE_EVENT_MANIFEST_VERSION,
        ),
        (
            "custody",
            hdc.HUMAN_DECISION_RECORD_ARTIFACT_KIND,
            "HumanDecisionRecord",
            hdc.HUMAN_DECISION_RECORD_MANIFEST_VERSION,
        ),
    ]
    trust.raw["human_decision_custody"] = {
        "signer_identity": identities["custody"],
        "private_key_path": str(tmp_path / "custody.pem"),
        "public_key_path": str(tmp_path / "custody.pub"),
        "verifier_epoch": "acquisition-served-epoch",
        "provenance": {"source": "fixture_external_institution", "reference": "served-acquisition"},
        "revoked_key_ids": [],
        "trusted_producers": [
            {
                "artifact_kind": kind,
                "schema_name": f"polisyos.runtime.{schema}",
                "schema_version": version,
                "signer_identity": identities[name],
                "public_key_path": str(tmp_path / f"{name}.pub"),
            }
            for name, kind, schema, version in rows
        ],
    }
    trust.raw["acquisition_authority"] = {
        "mandates": [],
        **{
            field: {
                "signer_identity": identities[name],
                "private_key_path": str(tmp_path / f"{name}.pem"),
                "public_key_path": str(tmp_path / f"{name}.pub"),
                "verifier_provenance_ref": "fixture://appointments",
            }
            for field, name in (("admission_signer", "admission"), ("decision_signer", "source"))
        },
    }
    return signers, identities


def test_served_acquisition_selects_committed_human_authority_and_reopens_worker(
    tmp_path, monkeypatch
):
    from polisyos.runtime.http.services import (
        acquisition_action_service,
        acquisition_surface_execution,
    )
    from tests._helpers import acquisition_chain
    from tests._helpers.acquisition_human_decision import persist_signed, prepare_human_decision
    from tests._helpers.acquisition_production import (
        install_fixture_wdi_cost_basis,
        intercepted_wdi_transport,
    )

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    install_fixture_wdi_cost_basis(monkeypatch)
    # The isolated checkout has no production catalog. Supply actual persisted
    # catalog input; every container still opens and hashes it through its owner.
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
    trust = _ExternalTrust(tmp_path)
    port_patch = pytest.MonkeyPatch()
    signers, identities = _key_config(tmp_path, trust)
    cas_root = tmp_path / "cas"

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

    def appoint_mandate(control, request, resource_digest):
        store = control._artifact_store
        now = datetime.now(UTC)
        job_id = acquisition_action_service.AcquisitionActionService._job_id(closure, request)
        contract = _contract()
        envelope = contract.action_envelopes[0].model_copy(
            update={
                "mandate_owner_ref": identities["owner"],
                "authorized_subject": "acquisition-operator",
                "authorized_runtime_roles": (PolicyOSRole.ANALYST,),
                "required_tenant_id": TENANT,
                "required_resource_digest": resource_digest,
                "valid_from": now - timedelta(minutes=1),
                "valid_until": now + timedelta(hours=1),
            }
        )
        contract = contract.model_copy(
            update={"mandate_owner_ref": identities["owner"], "action_envelopes": (envelope,)}
        )
        context = {
            "control": control,
            "tenant_id": TENANT,
            "cell_id": CELL,
            "run_id": RUN,
            "job_id": job_id,
            "now": now,
        }
        contract_ref = _within_fixture_owner(
            persist_signed,
            payload=contract,
            kind=authority.DELEGATION_CONTRACT_ARTIFACT_KIND,
            schema_name="polisyos.runtime.DelegationContract",
            schema_version=authority.LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
            signer=signers["owner"],
            signer_identity=identities["owner"],
            **context,
        )
        evidence = _mandate_authority_evidence(
            owner_ref=identities["owner"],
            signer_identity=identities["current"],
            rule_version_ref=contract.rule_version_ref,
            effective_from=now - timedelta(minutes=1),
            effective_until=now + timedelta(hours=1),
        )
        evidence_ref = _within_fixture_owner(
            persist_signed,
            payload=evidence,
            kind=authority.CURRENT_MANDATE_OWNER_ARTIFACT_KIND,
            schema_name="polisyos.runtime.CurrentMandateOwnerEvidence",
            schema_version=authority.CURRENT_MANDATE_OWNER_SCHEMA_VERSION,
            signer=signers["current"],
            signer_identity=identities["current"],
            **context,
        )
        info = _within_fixture_owner(
            store.put_json,
            {"risk": "Fiscal measurement excludes unreported balances; review required."},
            artifacts.ArtifactWriteOptions(
                kind="test.acquisition.disconfirming", media_type="application/json"
            ),
        )
        slot = {
            "tenant_id": TENANT,
            "cell_id": CELL,
            "run_id": RUN,
            "route_id": closure.route_id,
            "resource_digest": resource_digest,
            "delegation_contract_ref": contract_ref,
            "mandate_owner_ref": identities["owner"],
            "delegation_public_key_path": str(tmp_path / "owner.pub"),
            "current_mandate_evidence_ref": evidence_ref,
            "current_mandate_signer_identity": identities["current"],
            "current_mandate_public_key_path": str(tmp_path / "current.pub"),
            "verifier_provenance_ref": "fixture://appointment-registry",
            "decision_information_refs": [info.model_dump(mode="json")],
            "decision_disconfirming_refs": [info.model_dump(mode="json")],
        }
        return slot, job_id

    def approve_request(client, request, resource_digest):
        container = client.app.state.runtime_container
        response, digest = trust.post(
            client,
            path + "/decision-request",
            request.model_dump(mode="json"),
            route=route_prefix + "/decision-request",
        )
        assert response.status_code == 200 and digest == resource_digest, response.text
        source_ref = response.json()["authority_decision_ref"]
        source = authority.AgentActionAuthorityDecision.model_validate(
            canon.from_canonical_bytes(
                _within_fixture_owner(
                    container.control_service._artifact_store.get_bytes, source_ref
                )
            )
        )
        assert source.refusal_reasons == ("human_decision_missing",), source.refusal_reasons
        gate = _within_fixture_owner(
            prepare_human_decision,
            container.control_service,
            container.human_decision_service,
            source_ref,
            tenant_id=TENANT,
            cell_id=CELL,
            run_id=RUN,
            signers=signers,
            identities=identities,
            now=datetime.now(UTC),
            audit_path=cas_root / "runtime" / "audit" / "access.jsonl",
        )
        body = {
            name: value
            for name, value in gate.model_dump(mode="json").items()
            if name not in {"tenant_id", "run_id", "exposure_session_ref"}
        }
        body.update(
            action="approve",
            decision_mode="ordinary",
            accountability_statement="I accept this bounded acquisition.",
            dissent_statement="The measurement limitations remain material and were reviewed.",
        )
        response, _ = trust.post(
            client,
            f"/api/v1/runs/{RUN}/human-decisions",
            body,
            route="/api/v1/runs/{run_id}/human-decisions",
            subject="human-reviewer-1",
            extra_headers={"X-PolicyOS-Human-Decision-Exposure": gate.exposure_session_ref},
        )
        assert response.status_code == 201, response.text
        return source, response.json()["record_ref"]

    path = None
    try:
        with TestClient(app()) as client:
            container = client.app.state.runtime_container
            control = container.control_service
            closure, request = _within_fixture_owner(
                asyncio.run, persist_wdi_route(control, tenant_id=TENANT, cell_id=CELL)
            )
            store = control._artifact_store
            registry = store.put_json(
                {"fixture": "registry"},
                artifacts.ArtifactWriteOptions(kind="test.registry", media_type="application/json"),
            )
            RunContext.start(
                store=store,
                registry_bundle=registry,
                run_dir=cas_root / "runs" / RUN,
                run_id=RUN,
                tenant_id=TENANT,
                cell_id=CELL,
            ).finalize()
            path = f"/api/v1/runs/{RUN}/acquisition-routes/{closure.route_id}"
            route_prefix = "/api/v1/runs/{run_id}/acquisition-routes/{route_id}"
            response, resource_digest = trust.post(
                client,
                path + "/decision-request",
                request.model_dump(mode="json"),
                route=route_prefix + "/decision-request",
            )
            assert response.status_code == 200, response.text
            empty = authority.AgentActionAuthorityDecision.model_validate(
                canon.from_canonical_bytes(
                    _within_fixture_owner(
                        store.get_bytes, response.json()["authority_decision_ref"]
                    )
                )
            )
            assert empty.outcome == "refused"
            assert "delegation_contract_not_persisted" in empty.refusal_reasons
            slot, job_id = appoint_mandate(control, request, resource_digest)
            trust.raw["acquisition_authority"]["mandates"] = [slot]

        with TestClient(app()) as client:
            source, human_ref = approve_request(client, request, resource_digest)
            slot["human_decision_record_ref"] = human_ref

        # Controlled development composition selects a genuine production WDI
        # port with explicit external owner fixtures. All route/gateway/DS9/job
        # owners run unchanged; production PostgreSQL bootstrap is separate.
        cases = []
        monkeypatch.setattr(
            acquisition_chain,
            "intercepted_wdi_transport",
            lambda patch: intercepted_wdi_transport(patch, allow_loopback=True),
        )

        def select_fixture_port(*, control_service, **kwargs):
            # Each restart discards the prior transport/candidate fixture hooks
            # and reopens the same external inputs with a fresh owner bridge.
            port_patch.undo()
            case = _within_fixture_owner(
                acquisition_chain.make_wdi_port_case,
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
            select_fixture_port,
        )
        with TestClient(app()) as client:
            container = client.app.state.runtime_container
            response, _ = trust.post(
                client,
                path + "/execute",
                request.model_dump(mode="json"),
                route=route_prefix + "/execute",
            )
            assert response.status_code in {200, 202}, response.text
            control = container.control_service
            job = control._control_store.get_job(job_id)
            assert job is not None
            persisted_payload = canon.from_canonical_bytes(
                _within_fixture_owner(control._artifact_store.get_bytes, job.payload_ref)
            )
            decision_ref = persisted_payload["decision_ref"]
            allowed = authority.AgentActionAuthorityDecision.model_validate(
                canon.from_canonical_bytes(
                    _within_fixture_owner(control._artifact_store.get_bytes, decision_ref)
                )
            )
            assert allowed.outcome == "allowed"
            assert allowed.human_decision_record_ref == slot["human_decision_record_ref"]
            assert allowed.permission_snapshot == source.permission_snapshot
            assert not cases[-1].transport_calls

        # Fresh container/provider: actual durable job replay has no live DS20 proof.
        with TestClient(app()) as client:
            container = client.app.state.runtime_container
            control = container.control_service
            job = control._control_store.get_job(job_id)
            control._process_control_job(job)
            completed_job = control._control_store.get_job(job_id)
            assert completed_job.state == "completed", completed_job
            result = completed_job.progress
            assert result["state"] == "completed", result
            assert result["receipt_phase"] == "terminal", result
            assert cases[-1].transport_calls
            receipt = _read_owned_terminal(control._artifact_store, result["terminal_receipt_ref"])
            assert receipt.receipt_phase == "terminal"
            assert receipt.action_generation == 1
            assert receipt.terminal_outcome == "quarantined_no_growth"
            first_terminal_ref = result["terminal_receipt_ref"]
            first_job_id = job_id
            first_progress = dict(completed_job.progress)
            retained_refs = (first_terminal_ref, *receipt.owner_receipt_refs)
            retained_bytes = {
                ref: _within_fixture_owner(control._artifact_store.get_bytes, ref)
                for ref in retained_refs
            }
            assert not any(
                _within_fixture_owner(control._artifact_store.get_manifest, ref).kind
                == "runtime_quality.acquisition_world_growth_receipt"
                for ref in receipt.owner_receipt_refs
            )
            assert _within_fixture_owner(cases[-1].bridge.has_deferred_admission, closure)
            before = tuple(cases[-1].transport_calls)
            _within_fixture_owner(cases[-1].appoint_native_policy)
            assert tuple(cases[-1].transport_calls) == before

            # A new action changes the exact request/resource and needs its own
            # mandate, currentness evidence, human decision and durable allow.
            request = request.model_copy(
                update={"idempotency_key": "served-acquisition-admission-after-appointment"}
            )
            response, resource_digest = trust.post(
                client,
                path + "/decision-request",
                request.model_dump(mode="json"),
                route=route_prefix + "/decision-request",
            )
            assert response.status_code == 200, response.text
            new_slot, job_id = appoint_mandate(control, request, resource_digest)
            assert job_id != first_job_id
            assert new_slot["resource_digest"] != slot["resource_digest"]
            assert new_slot["delegation_contract_ref"] != slot["delegation_contract_ref"]
            trust.raw["acquisition_authority"]["mandates"].append(new_slot)
            slot = new_slot

        with TestClient(app()) as client:
            source, human_ref = approve_request(client, request, resource_digest)
            slot["human_decision_record_ref"] = human_ref

        with TestClient(app()) as client:
            container = client.app.state.runtime_container
            response, _ = trust.post(
                client,
                path + "/execute",
                request.model_dump(mode="json"),
                route=route_prefix + "/execute",
            )
            assert response.status_code in {200, 202}, response.text
            control = container.control_service
            job = control._control_store.get_job(job_id)
            assert job is not None
            payload = canon.from_canonical_bytes(
                _within_fixture_owner(control._artifact_store.get_bytes, job.payload_ref)
            )
            second_decision_ref = payload["decision_ref"]
            assert second_decision_ref != decision_ref
            allowed = authority.AgentActionAuthorityDecision.model_validate(
                canon.from_canonical_bytes(
                    _within_fixture_owner(control._artifact_store.get_bytes, second_decision_ref)
                )
            )
            assert allowed.outcome == "allowed"
            assert allowed.human_decision_record_ref == human_ref
            assert allowed.permission_snapshot == source.permission_snapshot
            assert not cases[-1].transport_calls

        with TestClient(app()) as client:
            container = client.app.state.runtime_container
            control = container.control_service
            control._process_control_job(control._control_store.get_job(job_id))
            completed_job = control._control_store.get_job(job_id)
            assert completed_job.state == "completed", completed_job
            result = completed_job.progress
            assert result["receipt_phase"] == "terminal", result
            receipt = _read_owned_terminal(control._artifact_store, result["terminal_receipt_ref"])
            assert receipt.action_generation == 2
            assert receipt.terminal_outcome == "reentry_completed"
            assert not cases[-1].transport_calls
            assert control._control_store.get_job(first_job_id).progress == first_progress
            assert all(
                _within_fixture_owner(control._artifact_store.get_bytes, ref) == blob
                for ref, blob in retained_bytes.items()
            )
            growth_refs = [
                ref
                for ref in receipt.owner_receipt_refs
                if _within_fixture_owner(control._artifact_store.get_manifest, ref).kind
                == "runtime_quality.acquisition_world_growth_receipt"
            ]
            assert growth_refs, receipt
            growth = _within_fixture_owner(cases[-1].port.project_world_growth, closure)
            assert growth.admitted_observation_delta == 1

    finally:
        port_patch.undo()
        trust.close()
