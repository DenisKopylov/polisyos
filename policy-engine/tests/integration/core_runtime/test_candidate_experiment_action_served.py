"""The served candidate policy reaches a signed, replayed decision without effect."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core import artifacts, canon
from polisyos.runtime.quality.agent_action_authority import (
    CANDIDATE_EXPERIMENT_ACTION_KIND,
    AgentActionAuthorityDecision,
    agent_action_content_hash,
)

pytest_plugins = ("tests._helpers.acquisition_served_history",)


def _install_candidate_mandate(
    *,
    control,
    trust,
    signers,
    identities,
    origin,
    action_service,
    client,
    request,
    resource_digest,
    tmp_path,
    key_root: Path,
):
    """Sign exact candidate action/currentness inputs through existing fixture owners."""
    from polisyos.runtime.http import deployment_security as security
    from polisyos.runtime.http.services.acquisition_action_service import (
        AcquisitionActionService,
    )
    from polisyos.runtime.http.services.acquisition_authority_provider import (
        ProductionAcquisitionAuthorityProvider,
    )
    from polisyos.runtime.quality import agent_action_authority as authority
    from tests._helpers import acquisition_human_decision as human_fixture
    from tests._helpers import acquisition_served_history as served

    now = datetime.now(UTC)
    contract = served._contract()
    envelope = contract.action_envelopes[0].model_copy(
        update={
            "mandate_owner_ref": identities["owner"],
            "action_kind": CANDIDATE_EXPERIMENT_ACTION_KIND,
            "operation_id": CANDIDATE_EXPERIMENT_ACTION_KIND,
            "operation_version": "v1",
            "authorized_subject": "acquisition-operator",
            "authorized_runtime_roles": contract.action_envelopes[0].authorized_runtime_roles,
            "required_tenant_id": origin.tenant_id,
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
        "tenant_id": origin.tenant_id,
        "cell_id": origin.cell_id,
        "run_id": origin.run_id,
        "job_id": AcquisitionActionService._candidate_experiment_job_id(origin, request),
        "now": now,
    }
    contract_ref = served._within_fixture_owner(
        human_fixture.persist_signed,
        payload=contract,
        kind=authority.DELEGATION_CONTRACT_ARTIFACT_KIND,
        schema_name="polisyos.runtime.DelegationContract",
        schema_version=authority.LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
        signer=signers["owner"],
        signer_identity=identities["owner"],
        **context,
    )
    current = human_fixture._mandate_authority_evidence(
        owner_ref=identities["owner"],
        signer_identity=identities["current"],
        rule_version_ref=contract.rule_version_ref,
        effective_from=now - timedelta(minutes=1),
        effective_until=now + timedelta(hours=1),
    )
    current_ref = served._within_fixture_owner(
        human_fixture.persist_signed,
        payload=current,
        kind=authority.CURRENT_MANDATE_OWNER_ARTIFACT_KIND,
        schema_name="polisyos.runtime.CurrentMandateOwnerEvidence",
        schema_version=authority.CURRENT_MANDATE_OWNER_SCHEMA_VERSION,
        signer=signers["current"],
        signer_identity=identities["current"],
        **context,
    )
    info = control._artifact_store.put_json(
        {"limitation": "modeled candidate only; measurement and causal validity remain unknown"},
        artifacts.ArtifactWriteOptions(
            kind="test.acquisition.candidate-experiment-information",
            media_type="application/json",
        ),
    )
    slot = {
        "tenant_id": origin.tenant_id,
        "cell_id": origin.cell_id,
        "run_id": origin.run_id,
        "route_id": origin.route_id,
        "resource_digest": resource_digest,
        "delegation_contract_ref": contract_ref,
        "mandate_owner_ref": identities["owner"],
        "delegation_public_key_path": str(key_root / "owner.pub"),
        "current_mandate_evidence_ref": current_ref,
        "current_mandate_signer_identity": identities["current"],
        "current_mandate_public_key_path": str(key_root / "current.pub"),
        "verifier_provenance_ref": "fixture://candidate-experiment/independent-appointment",
        "decision_information_refs": [info.model_dump(mode="json")],
        "decision_disconfirming_refs": [info.model_dump(mode="json")],
    }
    trust.raw["acquisition_authority"]["mandates"] = [slot]

    def install_provider():
        old = action_service._authority_provider
        deployment = security.build_deployment_security(
            security.DeploymentSecurityConfig.from_mapping(trust.raw)
        )
        container = client.app.state.runtime_container
        provider = ProductionAcquisitionAuthorityProvider(
            deployment_security=deployment,
            artifact_store=control._artifact_store,
            event_log=control._diagnostic_event_log,
            idempotency_store=old._idempotency,
            execution_profile=old._execution_profile,
            human_decision_service=container.human_decision_service,
            production_approval_resolver=old._approval_resolver,
        )
        action_service._authority_provider = provider
        return provider

    return slot, install_provider


def _candidate_experiment_issuer_port(*, fixture_root: Path, artifact_store):
    """Build once, then reopen the same test-owned WDI issuer for retained retries."""
    from types import SimpleNamespace

    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
    )
    from polisyos.data_forge.read_api import catalog
    from polisyos.runtime.http.services import acquisition_surface_execution
    from tests._helpers.lane01_candidate_action_served import (
        build_candidate_experiment_issuer_port,
    )

    repo_root = fixture_root / "repo"
    registry_path = repo_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY
    if not registry_path.is_file():
        return build_candidate_experiment_issuer_port(
            tmp_path=fixture_root,
            artifact_store=artifact_store,
        )
    authority = catalog.CanonicalAcquisitionAuthority.from_provision(
        repo_root=repo_root,
        baseline_path=repo_root / "catalog" / "catalog.duckdb",
    )
    registry = catalog.AcquisitionAuthorityRegistry.model_validate_json(registry_path.read_bytes())
    if len(registry.entries) != 1:
        raise AssertionError("candidate experiment fixture authority is not unique")
    entry = registry.entries[0]
    port = acquisition_surface_execution.WorldBankWDIAcquisitionExecutionPort(
        authority=authority,
        registry=registry,
        provision=authority.provision,
        provision_content_sha256=authority.provision_content_sha256,
        runtime_state_root=fixture_root / "runtime",
        artifact_store=artifact_store,
    )
    return SimpleNamespace(authority=authority, entry=entry, registry=registry, port=port)


def _candidate_experiment_policy_owner(*, control, fixture_root: Path, run_id: str):
    """Compose the shared test-owned WDI issuer and current quota template."""
    from types import SimpleNamespace

    from polisyos.fabric.connectors.profiles import SourceProfileRegistry
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        CandidateUnpricedExperimentPolicyTemplate,
    )
    from tests._helpers import acquisition_served_history as served

    issuer = _candidate_experiment_issuer_port(
        fixture_root=fixture_root,
        artifact_store=control._artifact_store,
    )
    quota_profile = control._llm_producer_settlement_store.snapshot_safe().invocation_profiles[
        run_id
    ]
    template = CandidateUnpricedExperimentPolicyTemplate(
        tenant_id=served.TENANT,
        cell_id=served.CELL,
        authority_entry_id=issuer.entry.entry_id,
        authority_registry_sha256=issuer.registry.content_sha256,
        authority_provision_sha256=issuer.authority.provision_content_sha256,
        attempt_id=issuer.port._provision.live_harness_receipts[0].attempt_id,
        max_http_response_bytes=65_536,
        max_http_decompressed_bytes=65_536,
        max_http_timeout_seconds=15.0,
        max_standard_n5_invocations=quota_profile.total_units - quota_profile.protected_units,
        max_metered_reentry_usd=Decimal("1.00"),
    )
    return SimpleNamespace(
        issuer=issuer,
        template=template,
        source_profiles=SourceProfileRegistry.get_instance(),
    )


def _validate_candidate_experiment_fixture_owners(*, key_root: Path) -> None:
    """Fail early if signed-authority fixture owners and keys are unavailable."""
    from tests._helpers import acquisition_human_decision as human_fixture
    from tests._helpers import acquisition_served_history as served

    required = {
        "human_decision.persist_signed": human_fixture.persist_signed,
        "human_decision.mandate_evidence": human_fixture._mandate_authority_evidence,
        "human_decision.prepare": human_fixture.prepare_human_decision,
        "served.contract": served._contract,
        "served.external_trust": served._ExternalTrust,
        "served.key_config": served._key_config,
    }
    missing = sorted(name for name, owner in required.items() if not callable(owner))
    if missing:
        raise AssertionError(f"candidate experiment fixture owners unavailable: {missing}")
    missing_keys = [
        str(path)
        for path in (key_root / "owner.pub", key_root / "current.pub")
        if not path.is_file()
    ]
    if missing_keys:
        raise AssertionError(
            f"candidate experiment fixture public keys unavailable: {missing_keys}"
        )


def run_candidate_experiment_action_oracle(
    *,
    tmp_path: Path,
    values: dict[str, object],
    policy_ref,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, str]:
    """Run the fresh HTTP/PA2/DS9 consumer against an already-served source.

    ``values`` is the observer payload from ``seed_only_context_observer``. A
    retained-source runner can provide the same control, client, trust, and
    signer owners after reopening the existing CAS and SQLite paths.
    """
    from polisyos.runtime.http.services.acquisition_action_service import (
        AcquisitionActionService,
        AcquisitionActionServiceError,
        CandidateExperimentRouteMutationRequest,
        CandidateExperimentRouteProjection,
    )
    from polisyos.runtime.http.services.human_decisions import (
        HumanDecisionOperationalResolutionError,
    )
    from tests._helpers import acquisition_served_history as served
    from tests._helpers.acquisition_human_decision import prepare_human_decision

    key_root = Path(values["key_root"])
    _validate_candidate_experiment_fixture_owners(key_root=key_root)
    control = values["control"]
    run_id = str(values["run_id"])
    client, trust = values["client"], values["trust"]
    action_service = values["action_service"]
    projection = action_service.get_candidate_experiment_route(
        tenant_id=served.TENANT,
        cell_id=served.CELL,
        run_id=run_id,
    )
    read_headers = {
        "Authorization": f"Bearer {trust.tokens['acquisition-operator']}",
        "X-Tenant-ID": served.TENANT,
    }
    get_path = f"/api/v1/runs/{run_id}/candidate-acquisition-experiment"
    public_before = client.get(get_path, headers=read_headers)
    assert public_before.status_code == 200, public_before.text
    public_projection = CandidateExperimentRouteProjection.model_validate(public_before.json())
    assert public_projection.route_id == projection.route_id
    assert public_projection.replay_pins == projection.replay_pins
    assert public_projection.action_authority == "not_established"
    assert public_projection.publication_authority is False
    assert public_projection.monetary_cost == "not_established"
    assert public_projection.information_value == "not_established"
    request = CandidateExperimentRouteMutationRequest(
        route_id=projection.route_id,
        replay_pins=projection.replay_pins,
        idempotency_key="served-labor-candidate-experiment-authority",
    )
    path = (
        f"/api/v1/runs/{run_id}/candidate-acquisition-experiment/"
        f"{projection.route_id}/decision-request"
    )
    route_template = (
        "/api/v1/runs/{run_id}/candidate-acquisition-experiment/{route_id}/decision-request"
    )
    body = request.model_dump(mode="json")
    initial, resource_digest = trust.post(client, path, body, route=route_template)
    assert initial.status_code == 200, initial.text
    assert initial.json()["outcome"] == "decision_required"

    origin = action_service._resolve_candidate_experiment_origin(
        tenant_id=served.TENANT, cell_id=served.CELL, run_id=run_id
    )
    slot, install_provider = _install_candidate_mandate(
        control=control,
        trust=trust,
        signers=values["signers"],
        identities=values["identities"],
        origin=origin,
        action_service=action_service,
        client=client,
        request=request,
        resource_digest=resource_digest,
        tmp_path=tmp_path,
        key_root=key_root,
    )
    install_provider()

    source_response, source_digest = trust.post(client, path, body, route=route_template)
    assert source_response.status_code == 200 and source_digest == resource_digest
    source_payload = source_response.json()
    assert source_payload["outcome"] == "decision_required"
    source_ref = source_payload["authority_decision_ref"]
    source_decision = AgentActionAuthorityDecision.model_validate(
        canon.from_canonical_bytes(control._artifact_store.get_bytes(source_ref))
    )
    assert source_decision.outcome == "refused"
    assert source_decision.human_decision_request is not None

    gate = served._within_fixture_owner(
        prepare_human_decision,
        control,
        client.app.state.runtime_container.human_decision_service,
        source_ref,
        tenant_id=served.TENANT,
        cell_id=served.CELL,
        run_id=run_id,
        signers=values["signers"],
        identities=values["identities"],
        now=datetime.now(UTC),
        audit_path=Path(values["cas_root"]) / "runtime" / "audit" / "access.jsonl",
    )
    human_body = {
        name: value
        for name, value in gate.model_dump(mode="json").items()
        if name not in {"tenant_id", "run_id", "exposure_session_ref"}
    }
    human_body.update(
        action="approve",
        decision_mode="ordinary",
        accountability_statement="I approve this limited candidate-only acquisition request.",
        dissent_statement="Measurement, causal validity, and value remain unestablished.",
    )
    human_response, _ = trust.post(
        client,
        f"/api/v1/runs/{run_id}/human-decisions",
        human_body,
        route="/api/v1/runs/{run_id}/human-decisions",
        subject="human-reviewer-1",
        extra_headers={"X-PolicyOS-Human-Decision-Exposure": gate.exposure_session_ref},
    )
    assert human_response.status_code == 201, human_response.text
    human_ref = human_response.json()["record_ref"]
    slot["human_decision_record_ref"] = human_ref
    trust.raw["acquisition_authority"]["mandates"] = [slot]
    install_provider()

    allowed_response, allowed_digest = trust.post(client, path, body, route=route_template)
    assert allowed_response.status_code == 200 and allowed_digest == resource_digest
    allowed_payload = allowed_response.json()
    assert allowed_payload["outcome"] == "decision_available"
    decision_ref = allowed_payload["authority_decision_ref"]
    public_after = client.get(get_path, headers=read_headers)
    assert public_after.status_code == 200, public_after.text
    assert public_after.json() == public_before.json()
    caller_selected_human = request.model_copy(update={"human_decision_record_ref": human_ref})
    caller_ref_response, caller_ref_digest = trust.post(
        client,
        path,
        caller_selected_human.model_dump(mode="json"),
        route=route_template,
    )
    assert caller_ref_response.status_code == 200, caller_ref_response.text
    assert caller_ref_digest != resource_digest
    caller_ref_decision = AgentActionAuthorityDecision.model_validate(
        canon.from_canonical_bytes(
            control._artifact_store.get_bytes(caller_ref_response.json()["authority_decision_ref"])
        )
    )
    assert caller_ref_decision.outcome == "refused"
    assert "delegation_contract_not_persisted" in caller_ref_decision.refusal_reasons
    job_id = AcquisitionActionService._candidate_experiment_job_id(origin, request)
    install_provider()
    effects: list[object] = []
    replay = action_service.replay_candidate_experiment_authority(
        tenant_id=served.TENANT,
        cell_id=served.CELL,
        run_id=run_id,
        route_id=projection.route_id,
        request=request,
        job_id=job_id,
        decision_ref=decision_ref,
        effect_handler=lambda call: effects.append(call),
    )
    loaded = replay.load_persisted_decision(decision_ref)
    operation, invocation, intent = action_service._candidate_experiment_action_tuple(
        origin, request
    )
    assert loaded.decision.outcome == "allowed"
    assert loaded.decision.action_kind == CANDIDATE_EXPERIMENT_ACTION_KIND
    assert loaded.decision.human_decision_record_ref == human_ref
    assert loaded.decision.operation_content_hash == agent_action_content_hash(operation)
    assert loaded.decision.invocation_content_hash == agent_action_content_hash(invocation)
    assert loaded.decision.intent_content_hash == agent_action_content_hash(intent)
    assert loaded.decision.permission_snapshot is not None
    assert loaded.decision.permission_snapshot.body_sha256 == (
        "sha256:"
        + hashlib.sha256(
            json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
    )
    assert effects == []

    history = action_service.load_candidate_experiment_decision_history(
        tenant_id=served.TENANT,
        cell_id=served.CELL,
        run_id=run_id,
        route_id=projection.route_id,
        request=request,
        job_id=job_id,
        decision_ref=decision_ref,
    )
    assert history.decision == loaded.decision
    assert history.current_authority == "not_revalidated"

    store = control._artifact_store
    original_get_bytes = store.get_bytes
    policy_id = str(policy_ref.artifact_id)
    with monkeypatch.context() as blocked_policy:

        def deny_policy(ref, *args, **kwargs):
            if str(getattr(ref, "artifact_id", ref)) == policy_id:
                raise FileNotFoundError("candidate policy removed")
            return original_get_bytes(ref, *args, **kwargs)

        blocked_policy.setattr(store, "get_bytes", deny_policy)
        with pytest.raises(AcquisitionActionServiceError):
            action_service.replay_candidate_experiment_authority(
                tenant_id=served.TENANT,
                cell_id=served.CELL,
                run_id=run_id,
                route_id=projection.route_id,
                request=request,
                job_id=job_id,
                decision_ref=decision_ref,
                effect_handler=lambda call: effects.append(call),
            )
    with pytest.raises(AcquisitionActionServiceError):
        action_service.replay_candidate_experiment_authority(
            tenant_id=served.TENANT,
            cell_id="foreign-cell",
            run_id=run_id,
            route_id=projection.route_id,
            request=request,
            job_id=job_id,
            decision_ref=decision_ref,
            effect_handler=lambda call: effects.append(call),
        )
    changed_request = request.model_copy(
        update={"idempotency_key": "served-labor-candidate-experiment-changed"}
    )
    with pytest.raises(AcquisitionActionServiceError):
        action_service.replay_candidate_experiment_authority(
            tenant_id=served.TENANT,
            cell_id=served.CELL,
            run_id=run_id,
            route_id=projection.route_id,
            request=changed_request,
            job_id=job_id,
            decision_ref=decision_ref,
            effect_handler=lambda call: effects.append(call),
        )
    human_id = str(human_ref)
    with monkeypatch.context() as blocked_human:

        def deny_human(ref, *args, **kwargs):
            if str(getattr(ref, "artifact_id", ref)) == human_id:
                raise FileNotFoundError("signed DS9 record removed")
            return original_get_bytes(ref, *args, **kwargs)

        blocked_human.setattr(store, "get_bytes", deny_human)
        with pytest.raises(HumanDecisionOperationalResolutionError):
            action_service.replay_candidate_experiment_authority(
                tenant_id=served.TENANT,
                cell_id=served.CELL,
                run_id=run_id,
                route_id=projection.route_id,
                request=request,
                job_id=job_id,
                decision_ref=decision_ref,
                effect_handler=lambda call: effects.append(call),
            )
    decision_id = str(decision_ref)
    with monkeypatch.context() as blocked_decision:

        def deny_decision(ref, *args, **kwargs):
            if str(getattr(ref, "artifact_id", ref)) == decision_id:
                raise FileNotFoundError("persisted PA2 decision removed")
            return original_get_bytes(ref, *args, **kwargs)

        blocked_decision.setattr(store, "get_bytes", deny_decision)
        with pytest.raises(FileNotFoundError):
            action_service.replay_candidate_experiment_authority(
                tenant_id=served.TENANT,
                cell_id=served.CELL,
                run_id=run_id,
                route_id=projection.route_id,
                request=request,
                job_id=job_id,
                decision_ref=decision_ref,
                effect_handler=lambda call: effects.append(call),
            )
    assert effects == []
    return {
        "run_id": run_id,
        "policy_ref": str(policy_ref.artifact_id),
        "decision_ref": str(decision_ref),
        "human_ref": str(human_ref),
        "resource_digest": resource_digest,
        "request_body_sha256": "sha256:"
        + hashlib.sha256(
            json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest(),
        "source_status": "completed",
    }


def run_retained_r8_candidate_experiment_oracle(
    *,
    fixture_root: Path,
    cas_root: Path,
    sqlite_path: Path,
    run_id: str,
    job_id: str,
) -> dict[str, str]:
    """Reopen the retained R8 source in a fresh authenticated runtime and consume it.

    This is an explicit retained-input runner entrypoint. It does not create a
    source, copy CAS/SQLite, or call the N5 simulation kernel. The app rebuilds
    its guarded runtime context and control owner over the supplied paths.
    """
    import sqlite3
    import sys
    from collections import Counter
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http import deployment_security as security
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.services import acquisition_surface_execution
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        POLICY_EVENT,
        list_current_candidate_unpriced_policy_bindings,
        read_candidate_unpriced_policy,
        resolve_current_candidate_unpriced_policy,
    )
    from polisyos.runtime.quality.candidate_experiment_policy_issuer import (
        prepare_candidate_experiment_policies_for_completed_job,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
    )

    tests_path = str(Path.cwd() / "tests")
    if tests_path not in sys.path:
        sys.path.insert(0, tests_path)
    from tests._helpers import acquisition_served_history as served

    fixture_root.mkdir(parents=True, exist_ok=True)
    monkeypatch = pytest.MonkeyPatch()
    for name, value in (
        ("POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS", "3"),
        ("POLISYOS_EXECUTION_PROFILE", "dev"),
        ("POLISYOS_CONTROL_WORKER_BACKEND", "external"),
        ("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite"),
        ("POLISYOS_CONTROL_SQLITE_PATH", str(sqlite_path)),
    ):
        monkeypatch.setenv(name, value)

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    original_artifacts = {
        path: digest(path)
        for path in (cas_root / "artifacts").rglob("*")
        if path.is_file() and (path.name.endswith(".blob") or path.name.endswith(".manifest.json"))
    }
    tables = (
        "control_jobs",
        "control_job_events",
        "control_pre_admission_attempt_events",
        "control_outbox_events",
        "control_diagnostic_events",
    )

    def rows() -> dict[str, Counter[tuple[object, ...]]]:
        queries = {
            "control_jobs": "SELECT * FROM control_jobs",
            "control_job_events": "SELECT * FROM control_job_events",
            "control_pre_admission_attempt_events": (
                "SELECT * FROM control_pre_admission_attempt_events"
            ),
            "control_outbox_events": "SELECT * FROM control_outbox_events",
            "control_diagnostic_events": "SELECT * FROM control_diagnostic_events",
        }
        with sqlite3.connect(sqlite_path) as connection:
            return {
                table: Counter(tuple(row) for row in connection.execute(query))
                for table, query in queries.items()
            }

    original_rows = rows()
    ledger_path = cas_root / "runs" / ".runtime" / "llm-cost-ledger.json"
    ledger_digest = digest(ledger_path) if ledger_path.is_file() else None
    trust_root = fixture_root / "trust"
    trust_root.mkdir(parents=True, exist_ok=True)
    key_root = fixture_root / "keys"
    key_root.mkdir(parents=True, exist_ok=True)
    trust = served._ExternalTrust(trust_root)
    signers, identities = served._key_config(key_root, trust)
    _validate_candidate_experiment_fixture_owners(key_root=key_root)
    original_n5_run = JointSimulationHorizonController.run

    def forbid_n5(*args, **kwargs):
        raise AssertionError("retained-source consumer attempted N5")

    monkeypatch.setattr(JointSimulationHorizonController, "run", forbid_n5)
    result: dict[str, str] | None = None
    try:
        app = create_runtime_api_app(
            cas_root=cas_root,
            core_runs_root=cas_root / "runs",
            deployment_security=security.build_deployment_security(
                security.DeploymentSecurityConfig.from_mapping(trust.raw)
            ),
            enable_security_middlewares=True,
            enable_csrf_protection=False,
        )
        with TestClient(app) as client:
            container = client.app.state.runtime_container
            control = container.control_service
            job = control._control_store.get_job(job_id)
            assert job is not None and job.run_id == run_id and job.state == "completed"
            policy_owner = _candidate_experiment_policy_owner(
                control=control,
                fixture_root=fixture_root / "candidate-issuer",
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
            values = {
                "control": control,
                "action_service": container.acquisition_action_service,
                "job": job,
                "run_id": run_id,
                "cas_root": cas_root,
                "profile_selection_ref": "retained-r8",
                "client": client,
                "trust": trust,
                "signers": signers,
                "identities": identities,
                "key_root": key_root,
            }
            action_service = container.acquisition_action_service
            policy_event_type = POLICY_EVENT
            try:
                with tenant_scope(None, tenant_id=served.TENANT, cell_id=served.CELL):
                    loop = action_service._candidate_experiment_loop(
                        tenant_id=served.TENANT,
                        cell_id=served.CELL,
                        run_id=run_id,
                    )
                    source_origin = loop._resolve_verified_origin(run_id=run_id, experiment=True)
                    canonical_before = list_current_candidate_unpriced_policy_bindings(
                        control_service=control,
                        tenant_id=served.TENANT,
                        cell_id=served.CELL,
                        run_id=run_id,
                        source_job_id=job_id,
                        candidate_id=source_origin.source_cycle.selected_candidate_ref,
                    )
                    provider_count = len(
                        control._registry_providers.candidate_unpriced_policy_bindings
                    )
                    template_count = len(
                        control._registry_providers.candidate_unpriced_policy_templates
                    )
                    event_rows_before = control._diagnostic_event_log.list_events(
                        run_id=run_id, job_id=job_id, limit=500
                    )
                    policy_events_before = sum(
                        row.event.event_type == policy_event_type for row in event_rows_before
                    )
                    assert len(canonical_before) <= 1
                    assert provider_count == 0 and template_count == 1
                    monkeypatch.setattr(
                        acquisition_surface_execution,
                        "build_production_world_bank_wdi_execution_port",
                        lambda *, control_service: issuer.port
                        if control_service is control
                        else pytest.fail("retained issuer reopened an unrelated control service"),
                    )
                    policy_refs = prepare_candidate_experiment_policies_for_completed_job(
                        control_service=control,
                        source_job_id=job_id,
                    )
                    assert len(policy_refs) == 1
                    if canonical_before:
                        assert policy_refs[0] == canonical_before[0].policy_ref
                    issued = read_candidate_unpriced_policy(
                        store=control._artifact_store,
                        event_log=control._diagnostic_event_log,
                        ref=policy_refs[0],
                    )
                    selected_ref, selected_policy = resolve_current_candidate_unpriced_policy(
                        control_service=control,
                        scope=issued.scope,
                    )
                    assert selected_ref == policy_refs[0]
                    assert selected_policy == issued
                    event_rows_after = control._diagnostic_event_log.list_events(
                        run_id=run_id, job_id=job_id, limit=500
                    )
                    policy_events_after = sum(
                        row.event.event_type == policy_event_type for row in event_rows_after
                    )
                    assert policy_events_after == policy_events_before + (
                        0 if canonical_before else 1
                    )
                    origin = action_service._resolve_candidate_experiment_origin(
                        tenant_id=served.TENANT,
                        cell_id=served.CELL,
                        run_id=run_id,
                    )
                    selected_bindings = list_current_candidate_unpriced_policy_bindings(
                        control_service=control,
                        tenant_id=served.TENANT,
                        cell_id=served.CELL,
                        run_id=run_id,
                        source_job_id=job_id,
                        candidate_id=origin.source_cycle.selected_candidate_ref,
                    )
                    assert len(selected_bindings) == 1
                    assert selected_bindings[0].policy_ref == origin.policy_ref
                    assert selected_bindings[0].policy_ref == selected_ref
                    assert len(selected_bindings) == 1
                    print("retained_cas_profile POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS=3", flush=True)
                    print(
                        "retained_policy_selection "
                        f"templates={template_count} bindings={provider_count} "
                        f"canonical_before={len(canonical_before)} "
                        f"canonical_after={len(selected_bindings)} "
                        f"policy_events_before={policy_events_before} "
                        f"policy_events_after={policy_events_after}"
                    )
                    result = run_candidate_experiment_action_oracle(
                        tmp_path=fixture_root / "candidate-oracle",
                        values=values,
                        policy_ref=selected_ref,
                        monkeypatch=monkeypatch,
                    )
                    result["canonical_policy_binding_count"] = str(len(selected_bindings))
                    result["configured_template_count"] = str(template_count)
                    result["configured_binding_count"] = str(provider_count)
                    result["policy_template_registry_sha256"] = template.authority_registry_sha256
                    result["policy_template_provision_sha256"] = template.authority_provision_sha256
                    result["policy_template_attempt_id"] = template.attempt_id
                    result["policy_template_standard_n5_max"] = str(
                        template.max_standard_n5_invocations
                    )
                    result["policy_template_reentry_usd_max"] = str(
                        template.max_metered_reentry_usd
                    )
                    result["policy_events_before"] = str(policy_events_before)
                    result["policy_events_after"] = str(policy_events_after)
            finally:
                control._registry_providers = original_providers
    finally:
        trust.close()
        monkeypatch.undo()
        current_rows = rows()
        assert all(not (original_rows[table] - current_rows[table]) for table in tables)
        changed = [
            str(path)
            for path, expected in original_artifacts.items()
            if not path.is_file() or digest(path) != expected
        ]
        assert not changed, f"retained source CAS inputs changed: {changed[:5]}"
        if ledger_digest is not None:
            assert digest(ledger_path) == ledger_digest, "retained N5 ledger changed"
        assert JointSimulationHorizonController.run is original_n5_run
        print(
            "retained_r8_preservation "
            f"cas_artifact_files={len(original_artifacts)} "
            f"sql_rows={sum(sum(rows.values()) for rows in original_rows.values())} "
            f"ledger={'unchanged' if ledger_digest is not None else 'absent'} "
            "n5_guard=restored"
        )
    assert result is not None
    return result


def test_genuine_labor_policy_gets_signed_candidate_decision_and_fresh_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, served_recorded_candidate_gateway
) -> None:
    """Join genuine completed Labor/N5 source, current policy, HTTP PA2, and DS9 replay."""
    from dataclasses import replace

    from polisyos.runtime.http.services import acquisition_surface_execution
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        read_candidate_unpriced_policy,
        resolve_current_candidate_unpriced_policy,
    )
    from polisyos.runtime.quality.candidate_experiment_policy_issuer import (
        prepare_candidate_experiment_policies_for_completed_job,
    )
    from polisyos.scientist.orchestration.engine import BudgetInvocationQuotaPolicy
    from tests._helpers import acquisition_served_history as served
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
        complete_candidate_cycle_catalog_source,
    )

    monkeypatch.setenv("POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS", "3")
    source = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "labor-source", include_owner_slot_manifest=True
    )
    quota = BudgetInvocationQuotaPolicy(
        allocation_id="served-labor-candidate-experiment", total_units=3, protected_units=1
    )
    observed: dict[str, object] = {}

    def serve_action(**values) -> None:
        control = values["control"]
        run_id = str(values["run_id"])
        assert values["job"].kind == "natural_language_run"
        assert values["job"].state == "completed"
        client, trust = values["client"], values["trust"]
        action_service = values["action_service"]
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
            monkeypatch.setattr(
                acquisition_surface_execution,
                "build_production_world_bank_wdi_execution_port",
                lambda *, control_service: issuer.port
                if control_service is control
                else pytest.fail("candidate issuer reopened an unrelated control service"),
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
            assert policy.scope.tenant_id == served.TENANT
            assert policy.scope.cell_id == served.CELL
            assert policy.scope.run_id == run_id
            assert policy.scope.source_job_id == values["job"].job_id

            observed.update(
                run_candidate_experiment_action_oracle(
                    tmp_path=tmp_path,
                    values=values,
                    policy_ref=policy_ref,
                    monkeypatch=monkeypatch,
                )
            )
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
    assert result is not None and observed["source_status"] == "completed"
