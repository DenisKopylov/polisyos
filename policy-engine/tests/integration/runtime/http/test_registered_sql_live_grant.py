"""UNRUN proposal: the served source route must consume a real service grant."""

from __future__ import annotations

import copy
import json
import sqlite3
import time
from datetime import UTC, datetime

import pytest
from fastapi import Depends, Request
from fastapi.testclient import TestClient

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.contracts.decision_validity import (
    RegisteredSQLUseContract,
    SourceAdmissionCarrier,
)
from polisyos.core.security import tenant_scope
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.sources.sql_query import SQLQueryConnector
from polisyos.ir.model_layer.queries import DataViewRequest
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.deployment_security import (
    DeploymentSecurityConfig,
    build_deployment_security,
)
from polisyos.runtime.http.errors import RuntimeHTTPError
from polisyos.runtime.http.services import control_registry_providers
from polisyos.runtime.http.services.registered_sql_live_grant import (
    RegisteredSQLLiveGrantWitness,
)
from polisyos.runtime.http.services.registered_sql_service import (
    REGISTERED_SQL_ADMIT_AUTHZ,
)
from polisyos.runtime.http.services.registered_sql_service_contracts import (
    RegisteredSQLMaterializationRequest,  # noqa: TC001 - FastAPI resolves this at runtime.
)
from polisyos.scientist.adapters.registered_sql_admission import (
    RegisteredSQLViewContract,
)
from polisyos.scientist.validation.source_admission_port import (
    SourceIssuerCall,
    _bind_runtime_source_admission_authority,
    _require_source_admission_call,
)
from tests._helpers.acquisition_served_history import CELL, TENANT, _ExternalTrust


@pytest.fixture
def source_grant_env(tmp_path, monkeypatch):
    """Create actual JWT/JWKS/OPA deployment; no fabricated bound proof."""
    from unit.runtime.quality.test_catalog_source_identity import _selected_fixture

    from polisyos.runtime.quality.substrate_registry import (
        CatalogServingSourceSelection,
    )

    external = _ExternalTrust(tmp_path)
    code_root, owner_root, selected_catalog = _selected_fixture(tmp_path / "source-catalog")
    catalog = CatalogServingSourceSelection(
        snapshot_root=selected_catalog.snapshot_root,
        source_owner_root=owner_root,
        database_relative_path=selected_catalog.database_relative_path,
        catalog_run_profile="prod_full",
    )
    cas_root = tmp_path / "cas"
    database = tmp_path / "policy.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE policy_inputs(baseline REAL NOT NULL, scenario REAL NOT NULL, note TEXT)"
        )
        connection.executemany(
            "INSERT INTO policy_inputs VALUES (?, ?, NULL)",
            [(10.0, 11.0), (20.0, 18.0), (40.0, 44.0)],
        )
    config = ConnectionConfig(url=f"sqlite:///{database}", headers={"X-SQL-Table": "policy_inputs"})
    registry = ConnectorRegistry()
    registry.register(SQLQueryConnector, config)
    monkeypatch.setattr(control_registry_providers, "_default_connectors", lambda: registry)
    store = FileSystemCAS(cas_root, tenant_id=TENANT, cell_id=CELL)
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        view = RegisteredSQLViewContract(
            provider_id="provider-a",
            connector_id="sql.query",
            dataset_id="policy_inputs",
            config_fingerprint=config.cache_scope_fingerprint,
            statement='SELECT * FROM "policy_inputs" LIMIT 100',
            page_size=100,
        )
        use = RegisteredSQLUseContract(use_key="foundry.selected_basis")

        def put(value, kind, name, version):
            return store.put_json(
                value,
                ArtifactWriteOptions(
                    kind=kind,
                    media_type="application/json",
                    schema=SchemaInfo(name=name, version=version),
                ),
                return_selected_profile=True,
            )

        view_ref = put(view, view.ARTIFACT_KIND, view.ARTIFACT_SCHEMA_NAME, "1.0")
        use_ref = put(use, use.ARTIFACT_KIND, use.ARTIFACT_SCHEMA_NAME, "1.0")
        request_ref = put(
            DataViewRequest(
                schema_version="1.0",
                request_id="grant-test",
                view_type="table",
                metrics=["policy_inputs"],
            ),
            "ir.data_view_request",
            "polisyos.ir.DataViewRequest",
            "1.0",
        )

    service_identity = {
        "issuer": "https://idp.example",
        "audience": "polisyos-runtime",
        "subject": "sql-materializer",
        "tenant_id": TENANT,
        "cell_id": CELL,
    }
    external.raw["service_principals"].append(
        {
            **service_identity,
            "permissions": [
                "sources.registered_sql.admit",
                "sources.registered_sql.register",
                "sources.registered_sql.withdraw",
            ],
        }
    )
    external.raw["registered_sql_sources"] = [
        {
            "slot_id": "source-a",
            **service_identity,
            "provider_id": "provider-a",
            "connector_id": "sql.query",
            "registration_key": "registered-a",
            "registration_event_id": "source-genesis-a",
            "issuer_key": "deployed-sql-service-a",
            "effective_view_contract_ref": view_ref.model_dump(mode="json"),
            "use_contract_ref": use_ref.model_dump(mode="json"),
        }
    ]
    for subject, permission in (
        ("admit-only", "sources.registered_sql.admit"),
        ("register-only", "sources.registered_sql.register"),
        ("withdraw-only", "sources.registered_sql.withdraw"),
    ):
        identity = {**service_identity, "subject": subject}
        external.raw["service_principals"].append({**identity, "permissions": [permission]})
        external.raw["registered_sql_sources"].append(
            {
                **external.raw["registered_sql_sources"][0],
                **identity,
                "slot_id": subject,
            }
        )
    now = int(time.time())
    token = external.encode(
        {
            "iss": service_identity["issuer"],
            "aud": service_identity["audience"],
            "sub": service_identity["subject"],
            "tenant_id": TENANT,
            "cell_id": CELL,
            "iat": now,
            "exp": now + 3600,
            "jti": "sql-grant-test",
            "realm_access": {"roles": ["polisyos_viewer"]},
        }
    )
    monkeypatch.delenv("POLISYOS_CELL_ID", raising=False)
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "research")
    monkeypatch.setenv("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "embedded")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    deployment = build_deployment_security(DeploymentSecurityConfig.from_mapping(external.raw))
    app = create_runtime_api_app(
        cas_root=cas_root,
        deployment_security=deployment,
        enable_security_middlewares=True,
        repo_root=code_root,
        catalog_source_selection=catalog,
    )
    captured = []

    @app.post(
        "/api/v1/control/registered-sql/test-live-grant",
        dependencies=[Depends(REGISTERED_SQL_ADMIT_AUTHZ)],
    )
    async def test_only_live_grant(request: Request, body: RegisteredSQLMaterializationRequest):
        owner = request.app.state.runtime_container.decision_validity_service
        verifier = owner._registered_sql_issuer_verifier
        witness = verifier.witness(request, command=body, body_bytes=await request.body())
        call = SourceIssuerCall(
            operation="acquire",
            event_id=body.event_id,
            expected_predecessor=body.expected_predecessor,
        )
        authority = _bind_runtime_source_admission_authority(
            owner=owner, verifier=verifier, witness=witness, initial_call=call
        )
        state = _require_source_admission_call(authority, owner=owner, call=call)
        captured.append((owner, verifier, witness, authority, call))
        return {"issuer_key": state.issuer_key, "provider_id": state.provider_id}

    body = {
        "slot_id": "source-a",
        "request_ref": request_ref.model_dump(mode="json"),
        "event_id": "event-a",
        "occurrence_id": "occurrence-a",
        "expected_predecessor": "sha256:" + "b" * 64,
    }
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield external, deployment, client, token, body, captured
    finally:
        external.close()


def _post(client, token, body):
    return client.post(
        "/api/v1/control/registered-sql/materializations",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": TENANT},
        json=body,
    )


def test_exact_live_service_grant_reaches_fail_closed_owner_boundary(source_grant_env):
    _, _, client, token, body, _ = source_grant_env
    response = _post(client, token, body)
    # The grant was accepted but a configured string is not a committed genesis.
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "registered_sql_registration_missing"


def test_acquisition_permission_is_not_sql_source_authority(source_grant_env):
    external, _, client, _, body, _ = source_grant_env
    response = _post(client, external.tokens["acquisition-operator"], body)
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "action_permission_denied"


def test_granted_service_cannot_select_unappointed_source(source_grant_env):
    _, _, client, token, body, _ = source_grant_env
    changed = {**body, "slot_id": "another-source"}
    response = _post(client, token, changed)
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "registered_sql_slot_not_authorized"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("iss", "https://untrusted.example"),
        ("aud", "untrusted-audience"),
        ("sub", "unappointed-service"),
        ("tenant_id", "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        ("cell_id", "018f47a0-0000-7000-8000-000000000002"),
    ],
)
def test_service_token_scope_is_not_interchangeable(source_grant_env, field, value):
    external, _, client, _, body, _ = source_grant_env
    now = int(time.time())
    claims = {
        "iss": "https://idp.example",
        "aud": "polisyos-runtime",
        "sub": "sql-materializer",
        "tenant_id": TENANT,
        "cell_id": CELL,
        "iat": now,
        "exp": now + 3600,
        "jti": "sql-grant-variant",
        "realm_access": {"roles": ["polisyos_admin"]},
    }
    claims[field] = value
    response = _post(client, external.encode(claims), body)
    assert response.status_code in {401, 403}, response.text


def test_an_admit_grant_does_not_authorize_another_operation(source_grant_env):
    _, _, client, token, body, _ = source_grant_env
    response = _post(client, token, {**body, "operation": "withdraw"})
    assert response.status_code == 422, response.text


def test_selected_request_profile_cannot_be_changed_or_faked(source_grant_env):
    _, _, client, token, body, _ = source_grant_env
    changed = copy.deepcopy(body)
    changed["request_ref"]["manifest_profile_sha256"] = "sha256:" + "0" * 64
    response = _post(client, token, changed)
    assert response.status_code in {403, 422}, response.text


@pytest.mark.parametrize(
    "field", ["provider_id", "effective_view_contract_ref", "use_contract_ref"]
)
def test_mutated_deployment_slot_is_not_an_attested_grant(source_grant_env, field):
    _, deployment, client, token, body, _ = source_grant_env
    slot = deployment.config.registered_sql_sources[0]
    if field == "provider_id":
        value = "provider-b"
    else:
        value = getattr(slot, field).model_copy(
            update={"manifest_profile_sha256": "sha256:" + "f" * 64}
        )
    object.__setattr__(slot, field, value)
    response = _post(client, token, body)
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "deployment_security_attestation_invalid"


def test_existing_noop_mint_must_not_be_accepted(source_grant_env):
    # The bare seam remains compatible, but the installed owner must refuse it.
    _, deployment, client, _, _, _ = source_grant_env
    slot = deployment.config.registered_sql_sources[0]
    from polisyos.scientist.validation.source_admission_port import (
        _bind_source_admission_authority,
    )

    authority = _bind_source_admission_authority(
        issuer_key=slot.issuer_key,
        tenant_id=slot.tenant_id,
        cell_id=slot.cell_id,
        provider_id=slot.provider_id,
        registration_key=slot.registration_key,
        effective_view_contract_ref=slot.effective_view_contract_ref,
        use_contract_ref=slot.use_contract_ref,
        permitted_operations=frozenset({"genesis", "read_event"}),
        validate_issuer=lambda: None,
    )
    owner = client.app.state.runtime_container.decision_validity_service
    with pytest.raises(ValueError, match="source_admission_owner_not_established"):
        owner.register_materialization_source(
            authority,
            event_id=slot.registration_event_id,
            registration_key=slot.registration_key,
            effective_view_contract_ref=slot.effective_view_contract_ref,
            use_contract_ref=slot.use_contract_ref,
        )


def _probe(client, token, body):
    return client.post(
        "/api/v1/control/registered-sql/test-live-grant",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": TENANT},
        json=body,
    )


def test_genuine_jwt_deployment_slot_produces_owner_pinned_live_authority(
    source_grant_env,
):
    _, _, client, token, body, captured = source_grant_env
    response = _probe(client, token, body)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "issuer_key": "deployed-sql-service-a",
        "provider_id": "provider-a",
    }
    assert len(captured) == 1
    owner, _, _, authority, call = captured[0]
    state = _require_source_admission_call(authority, owner=owner, call=call)
    assert state.tenant_id == TENANT
    assert state.cell_id == CELL
    assert state.permitted_operations == frozenset({"admit", "read_event"})


def test_caller_built_witness_cannot_mint_an_issuer_authority(source_grant_env):
    _, _, client, token, body, captured = source_grant_env
    assert _probe(client, token, body).status_code == 200
    owner, verifier, _, _, call = captured[0]
    fake = object.__new__(RegisteredSQLLiveGrantWitness)
    with pytest.raises(RuntimeHTTPError) as exc:
        _bind_runtime_source_admission_authority(
            owner=owner, verifier=verifier, witness=fake, initial_call=call
        )
    assert exc.value.code == "registered_sql_grant_invalid"


def test_expired_service_grant_is_rejected_on_a_subsequent_owner_check(
    source_grant_env, monkeypatch
):
    _, _, client, token, body, captured = source_grant_env
    assert _probe(client, token, body).status_code == 200
    owner, _, witness, authority, call = captured[0]
    expires_at = witness.request.state.user_claims.exp
    monkeypatch.setattr(time, "time", lambda: expires_at + 1)
    with pytest.raises(RuntimeHTTPError) as exc:
        _require_source_admission_call(authority, owner=owner, call=call)
    assert exc.value.code == "registered_sql_action_proof_not_established"


def test_owner_pin_replacement_cannot_install_an_arbitrary_verifier(source_grant_env, monkeypatch):
    _, _, client, token, body, captured = source_grant_env
    assert _probe(client, token, body).status_code == 200
    owner, verifier, witness, authority, call = captured[0]
    monkeypatch.setattr(owner, "_registered_sql_issuer_verifier", object())
    with pytest.raises((RuntimeHTTPError, ValueError)):
        _require_source_admission_call(authority, owner=owner, call=call)
    with pytest.raises((RuntimeHTTPError, ValueError)):
        _bind_runtime_source_admission_authority(
            owner=owner,
            verifier=owner._registered_sql_issuer_verifier,
            witness=witness,
            initial_call=call,
        )
    assert verifier is not owner._registered_sql_issuer_verifier


def test_actual_command_cannot_be_substituted_after_live_authorization(
    source_grant_env,
):
    _, _, client, token, body, captured = source_grant_env
    assert _probe(client, token, body).status_code == 200
    owner, _, _, authority, call = captured[0]
    changed = SourceIssuerCall(
        operation="acquire",
        event_id="other-event",
        expected_predecessor=call.expected_predecessor,
    )
    with pytest.raises(RuntimeHTTPError) as exc:
        _require_source_admission_call(authority, owner=owner, call=changed)
    assert exc.value.code == "registered_sql_grant_scope_mismatch"


def test_genuine_register_commits_genesis_and_exact_retry_recovers_it(source_grant_env):
    _, _, client, token, body, _ = source_grant_env
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": TENANT}
    request = {"slot_id": "source-a", "event_id": "source-genesis-a"}
    first = client.post(
        "/api/v1/control/registered-sql/registrations", headers=headers, json=request
    )
    assert first.status_code == 200, first.text
    registration = first.json()["registration"]
    assert registration["event_id"] == "source-genesis-a"
    assert registration["issuer_key"] == "deployed-sql-service-a"
    assert registration["provider_id"] == "provider-a"
    assert registration["tenant_id"] == TENANT
    assert registration["cell_id"] == CELL
    retry = client.post(
        "/api/v1/control/registered-sql/registrations", headers=headers, json=request
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["registration"] == registration
    # The separately authorized service now runs actual SQLite and admits its
    # captured occurrence against the owner-issued genesis predecessor.
    selected = {**body, "expected_predecessor": registration["event_ref"]}
    after = _post(client, token, selected)
    assert after.status_code == 200, after.text
    result = after.json()
    assert result["current_use"] == "not_checked"
    assert result["external_database_currentness"] == "not_established"
    receipt = result["receipt"]
    carrier = SourceAdmissionCarrier.model_validate(receipt["carrier"])
    owner = client.app.state.runtime_container.decision_validity_service
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        store = client.app.state.runtime_container.runtime_api_context.store
        binding_ref = ArtifactRef.model_validate(result["binding_ref"])
        original_bytes = store.get_bytes(binding_ref)
        assert owner.read_source_current_use((carrier,), require_selected=False).status == "current"
    retry = _post(client, token, selected)
    assert retry.status_code == 200, retry.text
    assert retry.json() == result

    withdrawn = client.post(
        "/api/v1/control/registered-sql/withdrawals",
        headers=headers,
        json={
            "slot_id": "source-a",
            "event_id": "withdraw-a",
            "expected_predecessor": receipt["event_ref"],
            "target": receipt["carrier"],
        },
    )
    assert withdrawn.status_code == 200, withdrawn.text
    assert withdrawn.json()["receipt"]["operation"] == "withdraw"
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        assert (
            owner.read_source_current_use((carrier,), require_selected=False).status == "withdrawn"
        )
        assert store.get_bytes(binding_ref) == original_bytes
    history_retry = _post(client, token, selected)
    assert history_retry.status_code == 200, history_retry.text
    assert history_retry.json() == result


def test_configured_genesis_event_cannot_be_replaced_by_request_field(source_grant_env):
    _, _, client, token, _, _ = source_grant_env
    response = client.post(
        "/api/v1/control/registered-sql/registrations",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": TENANT},
        json={"slot_id": "source-a", "event_id": "unconfigured-genesis"},
    )
    assert response.status_code == 403, response.text


def test_fake_request_with_copied_sealed_proof_and_invalid_bearer_is_refused(
    source_grant_env,
):
    _, _, client, token, body, captured = source_grant_env
    assert _probe(client, token, body).status_code == 200
    _, verifier, genuine, _, _ = captured[0]
    scope = dict(genuine.request.scope)
    scope["headers"] = [
        (
            name,
            b"Bearer invalid.jwt.value" if name.lower() == b"authorization" else value,
        )
        for name, value in scope["headers"]
    ]
    fake = Request(scope)
    fake._body = genuine.body_bytes
    with pytest.raises(RuntimeHTTPError) as exc:
        verifier.witness(fake, command=genuine.command, body_bytes=genuine.body_bytes)
    assert exc.value.code == "registered_sql_bearer_invalid"


def _token_for(external, subject):
    now = int(time.time())
    return external.encode(
        {
            "iss": "https://idp.example",
            "aud": "polisyos-runtime",
            "sub": subject,
            "tenant_id": TENANT,
            "cell_id": CELL,
            "iat": now,
            "exp": now + 3600,
            "jti": "jwt-" + subject,
            "realm_access": {"roles": ["polisyos_admin"]},
        }
    )


def test_admit_only_service_cannot_create_genesis(source_grant_env):
    external, _, client, _, _, _ = source_grant_env
    token = _token_for(external, "admit-only")
    response = client.post(
        "/api/v1/control/registered-sql/registrations",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": TENANT},
        json={"slot_id": "admit-only", "event_id": "source-genesis-a"},
    )
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "action_permission_denied"


def test_register_only_service_cannot_withdraw(source_grant_env):
    external, _, client, _, body, _ = source_grant_env
    token = _token_for(external, "register-only")
    target = {
        "tenant_id": TENANT,
        "cell_id": CELL,
        "source_incarnation_id": "forged",
        "admission_scope_digest": "sha256:" + "a" * 64,
        "occurrence_id": "event-a",
        "revision_digest": "sha256:" + "b" * 64,
        "admission_epoch": "epoch-a",
        "admission_event_ref": "sha256:" + "c" * 64,
        "snapshot_ref": body["request_ref"],
        "use_contract_ref": body["request_ref"],
    }
    response = client.post(
        "/api/v1/control/registered-sql/withdrawals",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": TENANT},
        json={
            "slot_id": "register-only",
            "event_id": "withdraw-a",
            "expected_predecessor": "sha256:" + "d" * 64,
            "target": target,
        },
    )
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "action_permission_denied"


def test_withdraw_only_service_cannot_admit(source_grant_env):
    external, _, client, _, body, _ = source_grant_env
    token = _token_for(external, "withdraw-only")
    response = _post(client, token, {**body, "slot_id": "withdraw-only"})
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "action_permission_denied"


def test_caller_built_capture_cannot_reach_installed_owner(source_grant_env):
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.core.contracts.decision_validity import (
        RegisteredMaterialization,
        SourceRegistrationReceipt,
    )
    from polisyos.scientist.validation.source_admission_port import (
        _capture_registered_materialization,
    )

    _, _, client, token, body, captured = source_grant_env
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": TENANT}
    registration_response = client.post(
        "/api/v1/control/registered-sql/registrations",
        headers=headers,
        json={"slot_id": "source-a", "event_id": "source-genesis-a"},
    )
    assert registration_response.status_code == 200, registration_response.text
    registration = SourceRegistrationReceipt.model_validate_json(
        json.dumps(registration_response.json()["registration"]), strict=True
    )
    assert _probe(client, token, body).status_code == 200
    owner, _, _, authority, _ = captured[0]
    before = owner.current_source_admission_head(authority, registration)
    ref = ArtifactRef.model_validate_json(json.dumps(body["request_ref"]), strict=True)
    fabricated = RegisteredMaterialization(
        registration=registration,
        occurrence_id=body["occurrence_id"],
        producer_rule_version="policyos.registered-sql-execution.v1",
        producer_capture_ref=ref,
        request_ref=ref,
        snapshot_ref=ref,
        payload_ref=ref,
        schema_ref=ref,
        quality_ref=ref,
        observed_at=datetime.now(UTC),
    )
    fake_capture = _capture_registered_materialization(
        authority=authority, materialization=fabricated, validate_capture=lambda: None
    )
    with pytest.raises(ValueError, match="registered_sql_producer_provenance_not_established"):
        owner.admit_materialization(
            fake_capture, event_id=body["event_id"], expected_predecessor=before
        )
    assert owner.current_source_admission_head(authority, registration) == before


def test_live_grant_retry_waits_for_timed_out_real_owner_admission(
    source_grant_env, tmp_path, monkeypatch
):
    """A source stripe remains held for an unfinished authenticated owner call."""
    import threading
    from pathlib import Path

    from polisyos.runtime.http.errors import RuntimeDependencyTimeoutError
    from polisyos.scientist.adapters.fabric_bridge import DefaultFabricPort
    from polisyos.scientist.adapters.registered_sql_admission import (
        RegisteredSQLProducer,
    )

    _, _, client, token, body, captured = source_grant_env
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": TENANT}
    genesis = client.post(
        "/api/v1/control/registered-sql/registrations",
        headers=headers,
        json={"slot_id": "source-a", "event_id": "source-genesis-a"},
    )
    assert genesis.status_code == 200, genesis.text
    registration_data = genesis.json()["registration"]
    selected = {**body, "expected_predecessor": registration_data["event_ref"]}
    probe = _probe(client, token, selected)
    assert probe.status_code == 200, probe.text
    owner, _, _, authority, _ = captured[-1]
    registration = owner.resolve_source_admission_event(
        authority, event_id="source-genesis-a"
    ).source_registration
    container = client.app.state.runtime_container
    store = container.runtime_api_context.store
    port = DefaultFabricPort(
        connector_registry=container.control_registry_providers.connectors,
        connector_id="sql.query",
        require_fresh_registered_sql=True,
    )
    producer = RegisteredSQLProducer(port=port, owner=owner, authority=authority)
    request_ref = RegisteredSQLMaterializationRequest.model_validate(selected).request_ref
    source = owner._source_admission
    original_admit = source._methods["admit"]
    original_connect = sqlite3.connect
    entered, release, completed = (
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )
    source_opens = []
    database = (tmp_path / "policy.sqlite").resolve()

    def delayed_admit(*args, **kwargs):
        entered.set()
        if not release.wait(10):
            raise AssertionError("test did not release the real owner admission")
        try:
            return original_admit(*args, **kwargs)
        finally:
            completed.set()

    def counted_connect(path, *args, **kwargs):
        if Path(path).resolve() == database:
            source_opens.append(str(path))
        return original_connect(path, *args, **kwargs)

    source._methods["admit"] = delayed_admit
    monkeypatch.setattr(sqlite3, "connect", counted_connect)

    def attempt():
        with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
            return producer.acquire_and_admit(
                store=store,
                request_ref=request_ref,
                registration=registration,
                event_id=selected["event_id"],
                occurrence_id=selected["occurrence_id"],
                expected_predecessor=selected["expected_predecessor"],
            )

    try:
        with pytest.raises(RuntimeDependencyTimeoutError):
            attempt()
        assert entered.is_set()
        with pytest.raises(ValueError, match="source_admission_acquisition_busy"):
            attempt()
        assert len(source_opens) == 1
    finally:
        release.set()
    assert completed.wait(10)
    deadline = time.monotonic() + 10
    try:
        while True:
            try:
                receipt, materialization, binding_ref = attempt()
                break
            except ValueError as exc:
                if str(exc) != "source_admission_acquisition_busy" or time.monotonic() >= deadline:
                    raise
                time.sleep(0.01)
        assert receipt.event_id == selected["event_id"]
        assert materialization.occurrence_id == selected["occurrence_id"]
        assert binding_ref.manifest_profile_sha256 is not None
        assert len(source_opens) == 1
    finally:
        source._methods["admit"] = original_admit


def test_live_source_acquisition_does_not_starve_shared_cas_guard(source_grant_env):
    """A real service grant serializes one event without parking CAS workers."""
    import threading
    from concurrent.futures import ThreadPoolExecutor

    _, _, client, token, body, captured = source_grant_env
    assert _probe(client, token, body).status_code == 200
    owner, _, _, authority, _ = captured[-1]
    store = client.app.state.runtime_container.runtime_api_context.store
    entered, release = threading.Event(), threading.Event()

    def held_action():
        entered.set()
        if not release.wait(10):
            raise AssertionError("test did not release acquisition")
        return "complete"

    def acquire():
        with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
            return owner._run_source_acquisition_serialized(
                authority, event_id=body["event_id"], action=held_action
            )

    with ThreadPoolExecutor(max_workers=6) as pool:
        first = pool.submit(acquire)
        assert entered.wait(10)
        try:
            retries = [pool.submit(acquire) for _ in range(4)]
            for retry in retries:
                with pytest.raises(ValueError, match="source_admission_acquisition_busy"):
                    retry.result(timeout=3)
            with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
                assert (
                    store.get_manifest(ArtifactRef.model_validate(body["request_ref"])) is not None
                )
        finally:
            release.set()
        assert first.result(timeout=10) == "complete"


def test_live_grant_timed_out_cas_write_keeps_source_stripe(source_grant_env, monkeypatch):
    """A pending guarded write cannot overlap a retry of this source event."""
    import threading

    from polisyos.runtime.http.errors import RuntimeDependencyTimeoutError

    _, _, client, token, body, captured = source_grant_env
    assert _probe(client, token, body).status_code == 200
    owner, _, _, authority, _ = captured[-1]
    store = client.app.state.runtime_container.runtime_api_context.store
    original_put = store._target.put_json
    entered, release, wrote = threading.Event(), threading.Event(), threading.Event()
    writes = []
    action_entries = 0

    def delayed_put(*args, **kwargs):
        entered.set()
        if not release.wait(10):
            raise AssertionError("test did not release the guarded write")
        try:
            ref = original_put(*args, **kwargs)
            writes.append(ref)
            return ref
        finally:
            wrote.set()

    monkeypatch.setattr(store._target, "put_json", delayed_put)

    def attempt():
        def action():
            nonlocal action_entries
            action_entries += 1
            return store.put_json(
                {"row": 12.5},
                ArtifactWriteOptions(
                    kind="test.timed_source_payload",
                    media_type="application/json",
                    schema=SchemaInfo(name="test.timed_source_payload", version="1.0"),
                ),
                return_selected_profile=True,
            )

        with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
            return owner._run_source_acquisition_serialized(
                authority, event_id=body["event_id"], action=action
            )

    try:
        with pytest.raises(RuntimeDependencyTimeoutError):
            attempt()
        assert entered.is_set()
        with pytest.raises(ValueError, match="source_admission_acquisition_busy"):
            attempt()
        assert action_entries == 1
    finally:
        release.set()
    assert wrote.wait(10)
    deadline = time.monotonic() + 10
    while True:
        try:
            replay_ref = attempt()
            break
        except ValueError as exc:
            if str(exc) != "source_admission_acquisition_busy" or time.monotonic() >= deadline:
                raise
            time.sleep(0.01)
    assert writes and replay_ref.artifact_id == writes[0].artifact_id
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        assert store.verify(replay_ref).ok


def test_real_sql_workflows_recheck_current_use_on_every_debug_get(
    source_grant_env, tmp_path, monkeypatch
):
    """A and independent I retain their bytes; withdrawing A affects fresh A only."""
    from unit.scientist.nodes.builtins.decide.test_policy_runtime_method_metrics import (
        _exercise_public_execute_method_metric_source,
    )

    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.contracts.control import WorkflowRunRequest
    from polisyos.core.contracts.decision_validity import RegisteredSQLAdmissionBinding
    from polisyos.core.contracts.execution_plan import ExecutionPlan, MethodDagNode
    from polisyos.core.contracts.runtime import GraphMethodExecutionSelection
    from tests._helpers.control_worker import (
        dispatch_one_control_job,
        stop_embedded_control_worker,
    )

    external, _, client, source_token, body, _ = source_grant_env
    source_headers = {"Authorization": f"Bearer {source_token}", "X-Tenant-ID": TENANT}
    analyst_headers = {
        "Authorization": f"Bearer {external.tokens['acquisition-operator']}",
        "X-Tenant-ID": TENANT,
    }
    service = client.app.state._control_service
    store = client.app.state.runtime_container.runtime_api_context.store
    stop_embedded_control_worker(service)
    genesis = client.post(
        "/api/v1/control/registered-sql/registrations",
        headers=source_headers,
        json={"slot_id": "source-a", "event_id": "source-genesis-a"},
    )
    assert genesis.status_code == 200, genesis.text
    selected_a = {
        **body,
        "event_id": "source-event-a",
        "occurrence_id": "source-occurrence-a",
        "expected_predecessor": genesis.json()["registration"]["event_ref"],
    }
    admitted_a = _post(client, source_token, selected_a)
    assert admitted_a.status_code == 200, admitted_a.text
    a = admitted_a.json()
    with sqlite3.connect(tmp_path / "policy.sqlite") as database:
        database.execute("DELETE FROM policy_inputs")
        database.executemany(
            "INSERT INTO policy_inputs VALUES (?, ?, NULL)",
            [(100.0, 101.0), (200.0, 198.0), (400.0, 404.0)],
        )
    selected_i = {
        **body,
        "event_id": "source-event-i",
        "occurrence_id": "source-occurrence-i",
        "expected_predecessor": a["receipt"]["event_ref"],
    }
    admitted_i = _post(client, source_token, selected_i)
    assert admitted_i.status_code == 200, admitted_i.text
    independent = admitted_i.json()
    assert (
        independent["receipt"]["carrier"]["snapshot_ref"] != a["receipt"]["carrier"]["snapshot_ref"]
    )

    def run_source(result, name, *, merge_registry_schema_override=None):
        source_ref = ArtifactRef.model_validate(result["binding_ref"])
        with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
            binding = validate_core_model_json_artifact(
                RegisteredSQLAdmissionBinding, store, source_ref
            )
            prepared = _exercise_public_execute_method_metric_source(
                tmp_path / name,
                monkeypatch,
                artifact_store=store,
                prepare_only=True,
                execution_data_snapshot_ref=binding.materialization.snapshot_ref,
                registered_sql_admission_ref=source_ref,
                merge_registry_schema_override=merge_registry_schema_override,
            )
        plan = ExecutionPlan(
            plan_id=f"{name}-plan",
            run_id="pending",
            method_dag=[
                MethodDagNode(
                    node_id="ex_ante_node",
                    method_fqn=prepared["method_fqn"],
                    method_version=prepared["method_version"],
                    backend=prepared["method_backend"],
                    params={"poverty_line": None},
                    reads_slots=["baseline", "scenario"],
                    writes_slots=["result"],
                )
            ],
        )
        request = WorkflowRunRequest(
            data_source={"registered_sql_admission_ref": source_ref.model_dump(mode="json")},
            trinity_bundle_ref=prepared["trinity_ref"],
            registry_bundle_ref=prepared["registry_ref"],
            params={
                "control_plane_transition": "legacy_shadow",
                "capture_method_metric_environment": True,
                "foundry_input_binding_rules": [
                    {
                        "binding_id": "baseline",
                        "source_path": "baseline",
                        "target_slot_id": "baseline",
                    },
                    {
                        "binding_id": "scenario",
                        "source_path": "scenario",
                        "target_slot_id": "scenario",
                    },
                ],
                "method_metric_bindings": [
                    {
                        "objective_id": "objective_ex_ante_mean_change",
                        "node_id": "ex_ante_node",
                        "output_slot_id": "result",
                    }
                ],
                "execution_plan": plan.model_dump(mode="json"),
            },
        )
        response = client.post(
            "/api/v1/control/runs",
            headers=analyst_headers,
            json=request.model_dump(mode="json", exclude_none=True),
        )
        assert response.status_code == 200, response.text
        launched = response.json()
        assert (
            dispatch_one_control_job(
                store=service._control_store,
                handler=service._process_control_job,
                expected_job_id=launched["job_id"],
            )
            == launched["job_id"]
        )
        job = service._control_store.get_job(launched["job_id"])
        assert job is not None and job.state == "completed", job
        with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
            selection = service.get_method_execution_selection(
                run_id=launched["run_id"], tenant_id=TENANT, cell_id=CELL
            )
        assert isinstance(selection, GraphMethodExecutionSelection), selection
        return launched, selection, source_ref

    run_a, selection_a, ref_a = run_source(a, "sql-a")
    run_i, selection_i, ref_i = run_source(independent, "sql-i")
    run_bad, selection_bad, _ = run_source(
        a, "sql-a-unknown-merge-schema", merge_registry_schema_override="99.0"
    )
    assert run_a["run_id"] != run_i["run_id"]
    context = client.app.state.runtime_container.runtime_api_context
    context.run_index.refresh(force=True)

    # Observe the actual Runtime owner result without substituting its replay.
    import polisyos.foundry.execute as foundry_execute
    from polisyos.runtime.quality import authority as closure_authority
    from polisyos.runtime.quality import owned_execution_identity as owned_identity

    real_issue = owned_identity.issue_debug_execution_input_identity
    captured_identities = []
    captured_budgets = []
    owner_mode = {"omit_source": False}
    real_sources = foundry_execute.execution_input_basis_sources

    def observe_real_owner(**kwargs):
        if owner_mode["omit_source"]:
            with monkeypatch.context() as limited:
                limited.setattr(
                    foundry_execute,
                    "execution_input_basis_sources",
                    lambda basis: real_sources(basis)[:-1],
                )
                return real_issue(**kwargs)
        closure, verified = real_issue(**kwargs)
        # The limited custody fact must not become broad producer authority.
        with pytest.raises(closure_authority.AuthorityEnvelopeError, match="purpose_mismatch"):
            closure_authority._assert_closed_consumed_input_closure(
                closure, verified_closure=verified
            )
        # Removing a decisive edge while retaining the closure digest cannot
        # reuse this actual owner token.
        omitted = closure.model_copy(
            update={
                "evidence_input_refs": closure.evidence_input_refs[:-1],
            }
        )
        with pytest.raises(closure_authority.AuthorityEnvelopeError):
            owned_identity.assert_debug_execution_input_identity(omitted, verified)
        captured_identities.append((closure, verified))
        captured_budgets.append(kwargs["aggregate_read_budget"])
        return closure, verified

    monkeypatch.setattr(owned_identity, "issue_debug_execution_input_identity", observe_real_owner)

    def get_result(run, selection, *, exact=False):
        url = f"/api/v1/debug/runs/{run['run_id']}/nodes/run_simulation/simulation-result"
        params = (
            {"artifact_id": str(selection.simulation_result_ref.artifact_id)} if exact else None
        )
        response = client.get(url, headers=analyst_headers, params=params)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        return response.json()["debug"]

    first_a = get_result(run_a, selection_a)
    exact_a = get_result(run_a, selection_a, exact=True)
    first_i = get_result(run_i, selection_i)
    assert first_a["artifact_ref"] == exact_a["artifact_ref"]
    assert (
        first_a["exante_source_use"]["status"]
        == exact_a["exante_source_use"]["status"]
        == "current"
    )
    assert first_i["exante_source_use"]["status"] == "current"
    assert len(captured_identities) == 3
    closure_a, _ = captured_identities[0]
    closure_a_fresh, _ = captured_identities[1]
    closure_i, _ = captured_identities[2]
    assert closure_a.closure_sha256 == closure_a_fresh.closure_sha256
    assert closure_a.run_id == run_a["run_id"] and closure_a.job_id == run_a["job_id"]
    assert closure_a.tenant_id == TENANT and closure_a.cell_id == CELL
    assert closure_i.closure_sha256 != closure_a.closure_sha256
    assert {item.role for item in closure_a.members} >= {
        "basis.source.registered_sql_admission",
        "basis.source.actual_data_snapshot",
        "basis.source.base_state_snapshot",
        "method.execution_input_identity",
    }
    source_roles = [
        item.role.removeprefix("basis.source.")
        for item in closure_a.members
        if item.role.startswith("basis.source.")
    ]
    # Registered SQL historically precedes registry members in the actual
    # writer's manifest; unifying owner enumeration must preserve that order.
    assert source_roles.index("registered_sql_admission") < next(
        index for index, role in enumerate(source_roles) if "_registry_member." in role
    )
    plan_edge_roles = [
        item.role.removeprefix("basis.edge.exec_plan.")
        for item in closure_a.members
        if item.role.startswith("basis.edge.exec_plan.")
    ]
    assert plan_edge_roles == [
        "program_graph",
        "treasury_plan",
        "method_metric_bindings",
    ]
    actual = next(item for item in closure_a.members if item.name == "restricted_execution")
    # A separate byte oracle computes the captured identities from known fixture
    # rows, not from the producer's claimed digest or input-count markers.
    import hashlib

    import numpy as np

    def expected_input(slot, values):
        array = np.asarray(values, dtype=np.float64)
        digest = hashlib.sha256()
        digest.update(array.dtype.str.encode("ascii"))
        digest.update(json.dumps(tuple(array.shape), separators=(",", ":")).encode("ascii"))
        digest.update(array.tobytes(order="C"))
        return {
            "slot_id": slot,
            "dtype": array.dtype.str,
            "shape": list(array.shape),
            "value_sha256": digest.hexdigest(),
        }

    assert actual.value["inputs"] == [
        expected_input("baseline", [10.0, 20.0, 40.0]),
        expected_input("scenario", [11.0, 18.0, 44.0]),
    ]
    actual_i = next(item for item in closure_i.members if item.name == "restricted_execution")
    # Both executions report mean change 1.0, but their consumed arrays differ.
    # Compare the independent array oracle directly so differing run/job scope
    # cannot masquerade as proof that different input values were captured.
    assert actual_i.value["inputs"] == [
        expected_input("baseline", [100.0, 200.0, 400.0]),
        expected_input("scenario", [101.0, 198.0, 404.0]),
    ]
    assert actual_i.value["inputs"] != actual.value["inputs"]
    assert actual.value["poverty_line"] is None
    assert actual.value["parameter_origin"] == "explicit_parameter"
    # Same registry bytes under a real, unknown selected manifest profile are
    # carried by a real completed worker and must not yield a closed identity.
    assert get_result(run_bad, selection_bad)["exante_source_use"]["status"] == "unknown"

    # Observe actual selected-store receipts and trace os.read bytes separately
    # from the budget under test. A removed charge must change the comparison.
    import os

    from polisyos.runtime.http.services import debug_registered_sql
    from polisyos.runtime.http.services.adapters import core_run
    from polisyos.scientist.nodes.builtins.decide import (
        policy_runtime_method_metrics as metrics,
    )

    observed = {
        "active": False,
        "cas": 0,
        "trace": 0,
        "unknown": False,
        "unbounded": [],
        "inject_unbounded": False,
    }
    trace_fds = set()
    real_service_read = debug_registered_sql.read_registered_sql_source_use
    real_trace_iter = core_run._iter_bounded_terminal_bytes
    real_os_read = os.read
    real_member = FileSystemCAS.open_member_bounded

    def record_usage(usage):
        value = getattr(usage, "observed_source_bytes", None)
        if type(value) is not int or value < 0:
            observed["unknown"] = True
        else:
            observed["cas"] += value

    def observe_manifest(real):
        def run(*args, **kwargs):
            try:
                receipt = real(*args, **kwargs)
            except Exception as exc:
                if observed["active"]:
                    record_usage(getattr(exc, "usage", None))
                raise
            if observed["active"]:
                record_usage(receipt.usage)
            return receipt

        return run

    class MemberAttemptObserver:
        def __init__(self, inner):
            self.inner = inner

        @property
        def usage(self):
            return self.inner.usage

        def __enter__(self):
            try:
                return self.inner.__enter__()
            except BaseException:
                if observed["active"]:
                    record_usage(self.inner.usage)
                raise

        def __exit__(self, *args):
            try:
                return self.inner.__exit__(*args)
            finally:
                if observed["active"]:
                    record_usage(self.inner.usage)

    def observe_member(cas, *args, **kwargs):
        return MemberAttemptObserver(real_member(cas, *args, **kwargs))

    def observe_os_read(fd, count):
        data = real_os_read(fd, count)
        if observed["active"] and fd in trace_fds:
            observed["trace"] += len(data)
        return data

    def observe_trace(fd, budget):
        trace_fds.add(fd)
        try:
            yield from real_trace_iter(fd, budget)
        finally:
            trace_fds.remove(fd)

    def observe_service(**kwargs):
        observed["active"] = True
        try:
            result = real_service_read(**kwargs)
            if observed["inject_unbounded"] == "selected_manifest":
                ref = kwargs["simulation_ref"]
                store.get_manifest_by_profile(ref.artifact_id, ref.manifest_profile_sha256)
            elif observed["inject_unbounded"] == "manifest_inventory":
                # This real public API reads manifest bytes directly, bypassing
                # the get/read/open/verify name family entirely.
                store.manifest_inventory_snapshot(kind="foundry.program_graph")
            return result
        finally:
            observed["active"] = False

    def observe_unbounded(name, real):
        def run(*args, **kwargs):
            if (
                observed["active"]
                and not (
                    # Bounded open_member is the documented owner-internal attempt
                    # and its full usage is recorded by MemberAttemptObserver.
                    name == "open_member" and kwargs.get("_read_attempt") is not None
                )
                and name != "for_tenant"
            ):
                observed["unbounded"].append(name)
            result = real(*args, **kwargs)
            if (
                observed["active"]
                and name == "for_tenant"
                and (type(result) is not FileSystemCAS or result.root != backend.root)
            ):
                observed["unknown"] = True
            return result

        return run

    with monkeypatch.context() as io:
        # C105 constructs scoped FileSystemCAS instances from the same installed
        # backend. Observe the class-owned public entrypoints, not only a proxy
        # instance, so those actual source-use reads cannot disappear from the
        # denominator. Preserve descriptor and guard behavior.
        import inspect

        from polisyos.runtime.http.resilience import _require_runtime_filesystem_guard

        backend = _require_runtime_filesystem_guard(store).backend
        assert type(backend) is FileSystemCAS
        names = {
            name
            for name in dir(FileSystemCAS)
            if not name.startswith("_") and callable(getattr(FileSystemCAS, name))
        }
        measured_methods = {
            "read_raw_manifest_bytes_bounded",
            "read_raw_manifest_bytes_bounded_for_input",
            "open_member_bounded",
        }
        assert measured_methods.issubset(names)
        assert {"get_manifest_by_profile", "manifest_inventory_snapshot", "for_tenant"}.issubset(
            names
        )
        for name in (
            "read_raw_manifest_bytes_bounded",
            "read_raw_manifest_bytes_bounded_for_input",
        ):
            io.setattr(FileSystemCAS, name, observe_manifest(getattr(FileSystemCAS, name)))
        for name in names - measured_methods:
            descriptor = inspect.getattr_static(FileSystemCAS, name)
            if isinstance(descriptor, classmethod):
                wrapped = classmethod(observe_unbounded(name, descriptor.__func__))
            elif isinstance(descriptor, staticmethod):
                wrapped = staticmethod(observe_unbounded(name, descriptor.__func__))
            else:
                wrapped = observe_unbounded(name, descriptor)
            io.setattr(FileSystemCAS, name, wrapped)
        io.setattr(FileSystemCAS, "open_member_bounded", observe_member)
        io.setattr(os, "read", observe_os_read)
        io.setattr(core_run, "_iter_bounded_terminal_bytes", observe_trace)
        io.setattr(debug_registered_sql, "read_registered_sql_source_use", observe_service)
        assert get_result(run_a, selection_a)["exante_source_use"]["status"] == "current"
        assert not observed["unknown"] and not observed["unbounded"]
        assert observed["cas"] > 0 and observed["trace"] > 0
        measured = observed["cas"] + observed["trace"]
        assert captured_budgets[-1].source_usage_established
        assert captured_budgets[-1].observed_bytes == measured
        # Exercise the observer against a real selected but unbudgeted API.
        observed["inject_unbounded"] = "selected_manifest"
        assert get_result(run_a, selection_a)["exante_source_use"]["status"] == "current"
        assert "get_manifest_by_profile" in observed["unbounded"]
        observed["unbounded"].clear()
        observed["inject_unbounded"] = "manifest_inventory"
        assert get_result(run_a, selection_a)["exante_source_use"]["status"] == "current"
        assert "manifest_inventory_snapshot" in observed["unbounded"]

    real_budget_init = metrics._ProjectionReadBudget.__init__

    def run_with_cap(cap):
        with monkeypatch.context() as capped:

            def budget_init(instance, *args, **kwargs):
                if kwargs.get("parent") is None:
                    kwargs["max_bytes"] = cap
                real_budget_init(instance, *args, **kwargs)

            capped.setattr(metrics._ProjectionReadBudget, "__init__", budget_init)
            return get_result(run_a, selection_a)["exante_source_use"]["status"]

    assert run_with_cap(measured - 1) == "unknown"
    # Per-read manifest reserves can conservatively refuse at exact physical
    # usage; exact threshold semantics are tested on the real bounded primitives.
    assert run_with_cap(max(measured * 2, 65_536)) == "current"

    # Keep the same selected payload bytes, but offer an unknown schema at the
    # actual SQL replay seam. The served consumer must refuse this forged view.
    # This is a seam-level adversary; a real reprofiled CAS control is separate.
    from types import SimpleNamespace

    real_bounded_read = metrics._read_bounded_method_metric_artifact

    def unknown_tabular_schema(*args, **kwargs):
        result = real_bounded_read(*args, **kwargs)
        if kwargs["ref"].kind != "fabric.tabular_payload":
            return result
        manifest = result.manifest.model_copy(update={"artifact_schema": None})
        return SimpleNamespace(manifest=manifest, value=result.value)

    with monkeypatch.context() as forged_schema:
        forged_schema.setattr(
            metrics, "_read_bounded_method_metric_artifact", unknown_tabular_schema
        )
        assert get_result(run_a, selection_a)["exante_source_use"]["status"] == "unknown"

    # A caller-supplied non-token cannot authorize the real Debug consumer.
    with monkeypatch.context() as forged:
        forged.setattr(
            owned_identity,
            "issue_debug_execution_input_identity",
            lambda **_kwargs: (closure_a, object()),
        )
        assert get_result(run_a, selection_a)["exante_source_use"]["status"] == "unknown"
    # Remove a decisive owner-enumerated input only inside the new owner replay,
    # after the outer SQL consumer already admitted its own source. The real
    # selected manifest must expose the omission even if success markers remain.
    owner_mode["omit_source"] = True
    try:
        assert get_result(run_a, selection_a)["exante_source_use"]["status"] == "unknown"
    finally:
        owner_mode["omit_source"] = False
    assert get_result(run_a, selection_a)["exante_source_use"]["status"] == "current"
    now = int(time.time())
    other_cell_token = external.encode(
        {
            "iss": "https://idp.example",
            "aud": "polisyos-runtime",
            "sub": "acquisition-operator",
            "tenant_id": TENANT,
            "cell_id": "018f47a0-0000-7000-8000-000000000002",
            "realm_access": {"roles": ["polisyos_analyst"]},
            "iat": now,
            "exp": now + 3600,
            "jti": "jwt-other-cell-source-use",
        }
    )
    wrong_cell = client.get(
        f"/api/v1/debug/runs/{run_a['run_id']}/nodes/run_simulation/simulation-result",
        headers={"Authorization": f"Bearer {other_cell_token}", "X-Tenant-ID": TENANT},
    )
    assert wrong_cell.status_code == 403, wrong_cell.text
    assert wrong_cell.json()["code"] == "cell_binding_mismatch"
    assert get_result(run_a, selection_a)["exante_source_use"]["status"] == "current"
    assert first_a["exante_source_use"]["recomputed_mean_change"] == 1.0
    assert first_i["exante_source_use"]["recomputed_mean_change"] == 1.0
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        original_a, original_i = store.get_bytes(ref_a), store.get_bytes(ref_i)

    withdrawn = client.post(
        "/api/v1/control/registered-sql/withdrawals",
        headers=source_headers,
        json={
            "slot_id": "source-a",
            "event_id": "withdraw-a-after-i",
            "expected_predecessor": independent["receipt"]["event_ref"],
            "target": a["receipt"]["carrier"],
        },
    )
    assert withdrawn.status_code == 200, withdrawn.text
    after_a = get_result(run_a, selection_a)
    after_exact = get_result(run_a, selection_a, exact=True)
    after_i = get_result(run_i, selection_i)
    assert after_a["exante_source_use"]["status"] == "withdrawn"
    assert after_exact["exante_source_use"]["status"] == "withdrawn"
    assert "recomputed_mean_change" not in after_a["exante_source_use"]
    assert after_i["exante_source_use"]["status"] == "current"
    assert after_i["exante_source_use"]["recomputed_mean_change"] == 1.0
    assert after_a["simulation_result"] == first_a["simulation_result"]
    assert after_i["simulation_result"] == first_i["simulation_result"]
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        assert store.get_bytes(ref_a) == original_a
        assert store.get_bytes(ref_i) == original_i
