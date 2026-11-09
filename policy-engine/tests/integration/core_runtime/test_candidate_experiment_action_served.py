"""The served candidate policy reaches a signed, replayed candidate-only reentry."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core import artifacts, canon
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.quality.agent_action_authority import (
    CANDIDATE_EXPERIMENT_ACTION_KIND,
    AgentActionAuthorityDecision,
    agent_action_content_hash,
)

pytest_plugins = ("tests._helpers.acquisition_served_history",)


def _count_selected_n4_source_loads(monkeypatch, source_ref, operation):
    """Count actual owner replays of one selected source during an operation."""
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    source_ref_key = artifacts.artifact_ref_identity_key(source_ref)
    original_source_loader = GenerationSourceRepository.load_candidate_scenario_source_for_n5
    selected_source_loads = 0

    def measured_source_loader(self, ref, **kwargs):
        nonlocal selected_source_loads
        if artifacts.artifact_ref_identity_key(ref) == source_ref_key:
            selected_source_loads += 1
        return original_source_loader(self, ref, **kwargs)

    with monkeypatch.context() as scoped_patch:
        scoped_patch.setattr(
            GenerationSourceRepository,
            "load_candidate_scenario_source_for_n5",
            measured_source_loader,
        )
        result = operation()
    return result, selected_source_loads


def _assert_selected_n4_source_replay_is_consolidated(
    monkeypatch,
    *,
    artifact_store,
    source_ref,
    execution_ref,
    input_ref,
    expected_run_id,
    expected_tenant_id,
    expected_cell_id,
):
    """Check one persisted V5 pair with no N5 invocation or authority reuse."""
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    repository = GenerationSourceRepository(artifact_store)

    def resolve_preconsolidation_sequence():
        source = repository.load_candidate_scenario_source_in_owner_scope(
            source_ref,
            expected_run_id=expected_run_id,
            expected_tenant_id=expected_tenant_id,
            expected_cell_id=expected_cell_id,
        )
        execution = repository.resolve_candidate_simulation_v5(
            ref=execution_ref,
            expected_run_id=expected_run_id,
            expected_job_id=source.job_id,
            expected_tenant_id=expected_tenant_id,
            expected_cell_id=expected_cell_id,
        )
        input_record = repository.resolve_candidate_simulation_v5(
            ref=input_ref,
            expected_run_id=expected_run_id,
            expected_job_id=source.job_id,
            expected_tenant_id=expected_tenant_id,
            expected_cell_id=expected_cell_id,
        )
        return source, execution, input_record

    with tenant_scope(
        None,
        tenant_id=expected_tenant_id,
        cell_id=expected_cell_id,
    ):
        baseline, baseline_source_loads = _count_selected_n4_source_loads(
            monkeypatch,
            source_ref,
            resolve_preconsolidation_sequence,
        )
        resolved, batched_source_loads = _count_selected_n4_source_loads(
            monkeypatch,
            source_ref,
            lambda: repository._resolve_selected_candidate_simulation_v5_pair(
                source_ref=source_ref,
                execution_ref=execution_ref,
                input_ref=input_ref,
                expected_run_id=expected_run_id,
                expected_tenant_id=expected_tenant_id,
                expected_cell_id=expected_cell_id,
            ),
        )
        assert baseline_source_loads == 4
        assert batched_source_loads == 1
        assert tuple(item.model_dump(mode="json") for item in baseline) == tuple(
            item.model_dump(mode="json") for item in resolved
        )
        baseline_source, _, baseline_input = baseline

        bad_source_ref = source_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "0" * 64}
        )
        with pytest.raises(artifacts.ArtifactOwnershipError, match="read_raw_manifest_view"):
            repository._resolve_selected_candidate_simulation_v5_pair(
                source_ref=bad_source_ref,
                execution_ref=execution_ref,
                input_ref=input_ref,
                expected_run_id=expected_run_id,
                expected_tenant_id=expected_tenant_id,
                expected_cell_id=expected_cell_id,
            )
        with pytest.raises(ValueError):
            repository._resolve_selected_candidate_simulation_v5_pair(
                source_ref=source_ref,
                execution_ref=execution_ref,
                input_ref=input_ref,
                expected_run_id=expected_run_id,
                expected_tenant_id="foreign-tenant",
                expected_cell_id=expected_cell_id,
            )
        with pytest.raises(ValueError, match="execution_input_mismatch"):
            repository._resolve_candidate_simulation_v5_record(
                ref=execution_ref,
                expected_run_id=expected_run_id,
                expected_job_id=baseline_source.job_id,
                expected_tenant_id=expected_tenant_id,
                expected_cell_id=expected_cell_id,
                _source_snapshot=baseline_source,
                _source_ref=source_ref,
                _input_snapshot=baseline_input,
                _input_ref=source_ref,
            )
    return {
        "preconsolidation": baseline_source_loads,
        "batched": batched_source_loads,
    }


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
    action_kind: str = CANDIDATE_EXPERIMENT_ACTION_KIND,
    required_permission: RuntimePermission = RuntimePermission.EVIDENCE_ACQUIRE,
    action_job_id: str | None = None,
    authority_valid_until: datetime | None = None,
):
    """Sign exact candidate action/currentness inputs through existing fixture owners.

    ``authority_valid_until`` aligns the signed envelope and current-mandate
    evidence for a bounded long-running test; omitted values keep the existing
    one-hour fixture window.
    """
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
    effective_authority_valid_until = (
        authority_valid_until
        if authority_valid_until is not None
        else now + timedelta(hours=1)
    )
    contract = served._contract()
    envelope = contract.action_envelopes[0].model_copy(
        update={
            "mandate_owner_ref": identities["owner"],
            "action_kind": action_kind,
            "operation_id": action_kind,
            "operation_version": "v1",
            "required_permission": required_permission,
            "authorized_subject": "acquisition-operator",
            "authorized_runtime_roles": contract.action_envelopes[0].authorized_runtime_roles,
            "required_tenant_id": origin.tenant_id,
            "required_resource_digest": resource_digest,
            "valid_from": now - timedelta(minutes=1),
            "valid_until": effective_authority_valid_until,
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
        "job_id": action_job_id
        if action_job_id is not None
        else AcquisitionActionService._candidate_experiment_job_id(origin, request),
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
        effective_until=effective_authority_valid_until,
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


def _candidate_experiment_issuer_port(
    *, fixture_root: Path, artifact_store, subsequent_attempt_ids: tuple[str, ...] = ()
):
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
        if subsequent_attempt_ids:
            from tests._helpers.lane01_wdi_profiles import (
                UNEMPLOYMENT_PROFILE,
                build_fixture_wdi_authority,
            )

            authority, entry = build_fixture_wdi_authority(
                repo_root,
                UNEMPLOYMENT_PROFILE,
                subsequent_attempt_ids=tuple(subsequent_attempt_ids),
            )
            registry = catalog.AcquisitionAuthorityRegistry.model_validate_json(
                registry_path.read_bytes()
            )
            port = acquisition_surface_execution.WorldBankWDIAcquisitionExecutionPort(
                authority=authority,
                registry=registry,
                provision=authority.provision,
                provision_content_sha256=authority.provision_content_sha256,
                runtime_state_root=fixture_root / "runtime",
                artifact_store=artifact_store,
            )
            return SimpleNamespace(authority=authority, entry=entry, registry=registry, port=port)
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


def _candidate_experiment_policy_owner(
    *,
    control,
    fixture_root: Path,
    run_id: str,
    subsequent_attempt_ids: tuple[str, ...] = (),
):
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
        subsequent_attempt_ids=tuple(subsequent_attempt_ids),
    )
    quota_profile = control._llm_producer_settlement_store.snapshot_safe().invocation_profiles[
        run_id
    ]
    template_fields: dict[str, object] = {}
    if subsequent_attempt_ids:
        template_fields = {
            "schema_version": "polisyos.runtime.candidate_unpriced_policy_template.v2",
            "subsequent_attempt_ids": tuple(subsequent_attempt_ids),
        }
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
        **template_fields,
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
    idempotency_key: str = "served-labor-candidate-experiment-authority",
    exercise_controls: bool = True,
    after_replay: Callable[..., object] | None = None,
    authority_valid_until: datetime | None = None,
) -> dict[str, str]:
    """Run one protected exchange with a stable, freshly issued identity proof.

    The scope includes ``after_replay`` so an execute POST remains bound to the
    same exact credential snapshot that was reviewed. Independent GET readers
    still issue fresh credentials through ``authorization_header``.
    """
    trust = values.get("trust")
    authorization_exchange = getattr(trust, "authorization_exchange", None)
    if not callable(authorization_exchange):
        raise TypeError("candidate_experiment_authority_exchange_trust_missing")
    with (
        authorization_exchange("acquisition-operator"),
        authorization_exchange("human-reviewer-1"),
    ):
        return _run_candidate_experiment_action_oracle(
            tmp_path=tmp_path,
            values=values,
            policy_ref=policy_ref,
            monkeypatch=monkeypatch,
            idempotency_key=idempotency_key,
            exercise_controls=exercise_controls,
            after_replay=after_replay,
            authority_valid_until=authority_valid_until,
        )


def _run_candidate_experiment_action_oracle(
    *,
    tmp_path: Path,
    values: dict[str, object],
    policy_ref,
    monkeypatch: pytest.MonkeyPatch,
    idempotency_key: str = "served-labor-candidate-experiment-authority",
    exercise_controls: bool = True,
    after_replay: Callable[..., object] | None = None,
    authority_valid_until: datetime | None = None,
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

    def read_headers() -> dict[str, str]:
        return {
            "Authorization": trust.authorization_header("acquisition-operator"),
            "X-Tenant-ID": served.TENANT,
        }

    get_path = f"/api/v1/runs/{run_id}/candidate-acquisition-experiment"
    public_before = client.get(get_path, headers=read_headers())
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
        idempotency_key=idempotency_key,
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
        authority_valid_until=authority_valid_until,
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
    if authority_valid_until is not None and (
        source_decision.human_decision_request.decision_due_at != authority_valid_until
        or source_decision.human_decision_request.decidable_until != authority_valid_until
    ):
        raise AssertionError(
            "candidate experiment request did not inherit the exact signed authority deadline"
        )

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
        authority_valid_until=authority_valid_until,
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
    if authority_valid_until is not None:
        human_record = served._within_fixture_owner(
            client.app.state.runtime_container.human_decision_service.read_record,
            human_ref,
            tenant_id=served.TENANT,
            run_id=run_id,
        )
        if human_record.valid_until != authority_valid_until:
            raise AssertionError(
                "candidate experiment DS9 record did not inherit the exact test authority deadline"
            )
    slot["human_decision_record_ref"] = human_ref
    trust.raw["acquisition_authority"]["mandates"] = [slot]
    install_provider()

    allowed_response, allowed_digest = trust.post(client, path, body, route=route_template)
    assert allowed_response.status_code == 200 and allowed_digest == resource_digest
    allowed_payload = allowed_response.json()
    assert allowed_payload["outcome"] == "decision_available"
    decision_ref = allowed_payload["authority_decision_ref"]
    public_after = client.get(get_path, headers=read_headers())
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
    assert source_decision.permission_snapshot is not None
    assert loaded.decision.permission_snapshot == source_decision.permission_snapshot
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

    if exercise_controls:
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
    else:
        assert effects == []
    if after_replay is not None:
        after_replay(
            values=values,
            origin=origin,
            request=request,
            decision_ref=decision_ref,
            policy_ref=policy_ref,
        )
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


def _assert_candidate_experiment_n5_uses_current_wmr(
    *, control, origin, execution, resolved_reentry_evaluation=None
) -> None:
    """Reconcile selected or blocked-reentry N5 output with its WMR snapshot."""
    import numpy as np

    from polisyos.core import artifacts
    from polisyos.core.contracts import DataSnapshot, StateSnapshot
    from polisyos.foundry.execute.executor import get_state_path, load_state_snapshot
    from polisyos.runtime.quality.candidate_acquisition_source import (
        CandidateAcquisitionSource,
    )
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationExecutionV5,
        CandidateSimulationN5InputV5,
        CandidateSimulationSyntheticModelDeclarationV1,
    )
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views

    history = execution.terminal_history
    evaluation = history.evaluation
    if evaluation is None:
        evaluation = resolved_reentry_evaluation
    elif resolved_reentry_evaluation is not None and (resolved_reentry_evaluation != evaluation):
        raise AssertionError("candidate experiment reentry evaluation changed selected N5")
    if evaluation is None:
        raise AssertionError("candidate experiment terminal omitted its N5 evaluation evidence")
    source = history.source
    if type(source) is not CandidateAcquisitionSource:
        raise AssertionError(
            "candidate experiment terminal omitted its persisted acquisition source"
        )
    selected = evaluation.selected
    n5_input = evaluation.input_record
    n5_result = evaluation.result
    store = control._artifact_store

    assert history.terminal.terminal_outcome == "candidate_reentry_completed"
    assert selected.evaluation_job_id == n5_input.job_id
    assert selected.n5_input_ref == evaluation.execution.n5_input_ref
    assert selected.n5_result_ref == evaluation.execution.n5_result_ref
    persisted_input = CandidateSimulationN5InputV5.model_validate(
        canon.from_canonical_bytes(store.get_bytes(selected.n5_input_ref))
    )
    persisted_execution = CandidateSimulationExecutionV5.model_validate(
        canon.from_canonical_bytes(store.get_bytes(selected.n5_execution_ref))
    )
    assert persisted_input == n5_input
    assert persisted_execution == evaluation.execution
    assert n5_input.authority_purpose == "candidate_scenario_n5_only"
    assert evaluation.execution.authority_purpose == "candidate_scenario_n5_only"
    assert selected.n4_source_ref == n5_input.n4_source_ref
    assert selected.context_job_ref == n5_input.context_job_ref
    assert selected.n5_input_ref == evaluation.execution.n5_input_ref
    assert selected.n5_execution_ref.kind == "runtime.quality.candidate_simulation_execution"
    assert selected.n5_result_ref == persisted_execution.n5_result_ref
    assert persisted_execution.n4_source_ref == n5_input.n4_source_ref
    assert persisted_execution.context_job_ref == n5_input.context_job_ref
    assert persisted_execution.model_declaration_ref == n5_input.model_declaration_ref
    assert persisted_execution.ncm_ref == n5_input.ncm_ref
    assert persisted_execution.n5_input_ref == selected.n5_input_ref
    assert persisted_execution.n5_result_ref == selected.n5_result_ref
    assert persisted_execution.n5_result_content_hash == n5_result.receipt.payload_hash
    assert selected.world_model_record_hash == n5_input.materialization.world_model_record_hash
    assert (
        persisted_execution.world_model_record_hash
        == n5_input.materialization.world_model_record_hash
    )
    assert (
        n5_result.world_model_record_content_hash
        == n5_input.materialization.world_model_record_hash
    )
    assert n5_input.run_id == origin.run_id
    assert n5_input.job_id != origin.source_job_id
    assert execution.job_id != origin.source_job_id
    if history.evaluation is None:
        reentry = history.reentry
        assert reentry is not None
        assert reentry.source_job_id == origin.source_job_id
        assert reentry.action_job_id != reentry.source_job_id
        assert n5_input.job_id == reentry.action_job_id
        assert selected.evaluation_job_id == reentry.action_job_id
        assert execution.job_id == reentry.action_job_id
        assert selected.design_problem_ref == reentry.design_problem_basis_ref
        assert selected.generation_run_id == reentry.continued_generation_run.run_id
        assert selected.cycle_index == reentry.new_cycle.cycle_index
    else:
        assert selected.generation_run_id == origin.generation_run.run_id
        assert selected.cycle_index == origin.source_cycle.cycle_index + 1

    old_simulation = origin.source_cycle.simulation
    old_n5_input_ref = old_simulation.candidate_simulation_n5_input_ref
    old_result_ref = old_simulation.simulation_result_ref
    old_n4_ref = old_simulation.candidate_simulation_n4_source_ref
    old_context_ref = old_simulation.candidate_simulation_context_job_ref
    old_execution_ref = artifacts.ArtifactRef.model_validate(
        old_simulation.diagnostics["candidate_simulation_execution_selected_ref"]
    )
    new_selected_refs = (
        (selected.n4_source_ref, old_n4_ref),
        (selected.context_job_ref, old_context_ref),
        (selected.n5_input_ref, old_n5_input_ref),
        (selected.n5_execution_ref, old_execution_ref),
        (selected.n5_result_ref, old_result_ref),
    )
    for new_ref, old_ref in new_selected_refs:
        assert new_ref is not None and old_ref is not None
        assert artifacts.artifact_ref_identity_key(new_ref) != (
            artifacts.artifact_ref_identity_key(old_ref)
        )
        assert str(new_ref.artifact_id) != str(old_ref.artifact_id)

    acquired_world = n5_input.profile.context_inputs.world_model_record
    views = world_model_artifact_views(acquired_world)
    data_snapshot_ref = views.data_snapshot_ref
    bound_state_ref = views.bound_state_snapshot_ref
    assert data_snapshot_ref.manifest_profile_sha256 is not None
    assert bound_state_ref is not None and bound_state_ref.manifest_profile_sha256 is not None
    assert (
        str(data_snapshot_ref.artifact_id) == acquired_world.simulation_model_ref.data_snapshot_ref
    )

    data_snapshot = DataSnapshot.model_validate(
        canon.from_canonical_bytes(store.get_bytes(data_snapshot_ref))
    )
    selected_observation = canon.from_canonical_bytes(store.get_bytes(data_snapshot.data_ref))[
        "acquisition"
    ]["selected"]
    assert selected_observation["source_time_status"] == "not_established"
    assert source.status == "candidate_only"
    assert source.observation_class == "model_output"
    assert source.target_slot_id == "global.unemployment_rate"
    assert (
        source.country_code,
        source.year,
        source.population,
        source.canonical_unit,
    ) == ("USA", 2024, "total_labor_force", "ratio")
    assert selected_observation["value"] == source.observation
    assert acquired_world.authority_status == "limited"
    assert {
        "source_time_not_established",
        "source_to_target_measurement_contract_not_established",
        "causal_coupling_not_established",
    }.issubset(acquired_world.limitations.admissibility_blockers)

    state_verification = store.verify(bound_state_ref)
    assert state_verification.ok, state_verification.error
    state_manifest = store.get_manifest(bound_state_ref)
    bound_state_snapshot = StateSnapshot.model_validate(
        canon.from_canonical_bytes(store.get_bytes(bound_state_ref))
    )
    assert state_manifest.inputs == bound_state_snapshot.lineage_inputs
    assert (
        artifacts.input_ref_from_artifact_ref(data_snapshot_ref, role="input.data_snapshot_ref")
        in bound_state_snapshot.lineage_inputs
    )
    bound_state = load_state_snapshot(store, snapshot_ref=bound_state_ref)

    wmr_baseline: dict[str, float] = {}
    for slot_id in sorted(n5_input.profile.n5.baseline_state):
        binding = acquired_world.slot_binding(slot_id)
        assert binding is not None and binding.state_path
        value = np.asarray(get_state_path(bound_state, binding.state_path))
        assert value.size == 1
        wmr_baseline[slot_id] = float(value.item())
    assert n5_input.profile.n5.baseline_state == wmr_baseline

    declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
        canon.from_canonical_bytes(store.get_bytes(n5_input.model_declaration_ref))
    )
    assert declaration.target_world_slot in wmr_baseline
    assert declaration.outcome_variable in wmr_baseline
    assert declaration.target_world_slot == "government.balance"
    assert declaration.outcome_variable == "global.unemployment_rate"
    assert declaration.target_baseline == wmr_baseline[declaration.target_world_slot]
    assert declaration.outcome_baseline == wmr_baseline[declaration.outcome_variable]
    assert declaration.outcome_variable == source.target_slot_id
    assert declaration.outcome_baseline == pytest.approx(source.observation, abs=1e-7)
    target_binding = acquired_world.slot_binding(declaration.target_world_slot)
    outcome_binding = acquired_world.slot_binding(declaration.outcome_variable)
    assert target_binding is not None
    assert (
        target_binding.unit == declaration.target_unit_id == n5_input.profile.rule.unit_id == "usd"
    )
    assert target_binding.temporal_granularity == "stock"
    assert (
        outcome_binding is not None
        and outcome_binding.unit == declaration.outcome_unit_id == "ratio"
    )
    assert declaration.outcome_per_target_unit == pytest.approx(0.001)
    assert declaration.outcome_noise_stddev == 0.0
    assert n5_input.profile.n5.horizon.start == n5_input.profile.n5.horizon.end == 0
    assert n5_input.profile.n5.horizon.step == 1
    assert n5_input.profile.n5.seed == 17
    assert n5_input.profile.n5.replications == 2

    old_n5_input = CandidateSimulationN5InputV5.model_validate(
        canon.from_canonical_bytes(store.get_bytes(old_n5_input_ref))
    )
    assert n5_input.job_id != old_n5_input.job_id
    old_outcome_baseline = old_n5_input.profile.n5.baseline_state[declaration.outcome_variable]
    assert declaration.outcome_baseline != pytest.approx(old_outcome_baseline)
    old_world = old_n5_input.profile.context_inputs.world_model_record
    old_bound_state_ref = world_model_artifact_views(old_world).bound_state_snapshot_ref
    assert old_bound_state_ref is not None
    assert artifacts.artifact_ref_identity_key(bound_state_ref) != (
        artifacts.artifact_ref_identity_key(old_bound_state_ref)
    )

    selected_decisions = tuple(
        item for item in n5_result.engine_decisions if item.decision == "selected"
    )
    assert len(selected_decisions) == 1
    assert (
        n5_result.selected_outcomes and declaration.outcome_variable in n5_result.selected_outcomes
    )
    joint_atom_ids = (n5_input.materialization.derived_n5_atom.intervention_id,)
    joint_trajectories = tuple(
        item
        for item in n5_result.trajectories
        if item.run_level == "joint" and item.atom_ids == joint_atom_ids
    )
    assert len(joint_trajectories) == 1
    target_value = float(n5_input.materialization.value)
    assert target_value == pytest.approx(2.0)
    expected_effect = declaration.outcome_per_target_unit * (
        target_value - wmr_baseline[declaration.target_world_slot]
    )
    expected_outcome = wmr_baseline[declaration.outcome_variable] + expected_effect
    for trajectory in joint_trajectories:
        assert trajectory.engine_kind == selected_decisions[0].engine_kind
        assert (
            trajectory.diagnostics["actual_replications"] == n5_input.profile.n5.replications == 2
        )
        assert trajectory.diagnostics["replication_seeds"] == [17, 18]
        for point in trajectory.points:
            assert point.effect[declaration.outcome_variable] == pytest.approx(
                expected_effect, abs=1e-9
            )
            assert point.outcomes[declaration.outcome_variable] == pytest.approx(
                expected_outcome, abs=1e-9
            )
            assert point.replication_sampling is not None
            assert point.replication_sampling.replicate_count == 2
            for sample in point.replication_sampling.samples:
                assert sample.effects[declaration.outcome_variable] == pytest.approx(
                    expected_effect, abs=1e-9
                )
                assert sample.outcomes[declaration.outcome_variable] == pytest.approx(
                    expected_outcome, abs=1e-9
                )

    assert execution.terminal_ref == history.terminal_ref
    if history.evaluation is None:
        assert history.selected_basis is not None
        assert history.selected_basis.basis_role == "blocked"
        assert history.frontier_after == history.frontier_before
    else:
        assert history.frontier_after is not None


def run_retained_r8_candidate_experiment_oracle(
    *,
    fixture_root: Path,
    cas_root: Path,
    sqlite_path: Path,
    run_id: str,
    job_id: str,
    continue_with_reentry: bool = False,
    idempotency_key: str = "served-labor-candidate-experiment-authority",
) -> dict[str, str]:
    """Reopen a retained source in a fresh authenticated runtime and consume it.

    The default mode is a no-N5 authority guard. Continuation mode skips only
    the separate negative controls and permits one served reentry callback to
    reach the real N5 producer; all other N5 calls remain forbidden. Neither
    mode creates a source or copies CAS/SQLite.
    """
    import sqlite3
    import sys
    from collections import Counter
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http import deployment_security as security
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.quality.acquisition_evaluation import (
        resolve_selected_acquisition_evaluation_parts,
    )
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        POLICY_EVENT,
        list_current_candidate_unpriced_policy_bindings,
        read_candidate_unpriced_policy,
        resolve_current_candidate_unpriced_policy,
    )
    from polisyos.runtime.quality.candidate_experiment_policy_issuer import (
        prepare_candidate_experiment_policies_for_completed_job,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        ConfiguredCandidateSimulationContextAdmissionOwner,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
    )
    from tests._helpers.candidate_experiment_served_execution import (
        bind_candidate_test_execution_port_factory,
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
    callback_active = False
    n5_calls = 0

    def guarded_n5(*args, **kwargs):
        nonlocal n5_calls
        if not continue_with_reentry or not callback_active:
            raise AssertionError("retained-source consumer attempted N5 outside served reentry")
        n5_calls += 1
        return original_n5_run(*args, **kwargs)

    monkeypatch.setattr(JointSimulationHorizonController, "run", guarded_n5)
    result: dict[str, str] | None = None
    retained_execution: list[object] = []
    reentry_delta_verified = [False]
    try:
        deployment = security.build_deployment_security(
            security.DeploymentSecurityConfig.from_mapping(trust.raw)
        )

        def build_app(
            *,
            profiles=(),
            model_declarations=(),
        ):
            return create_runtime_api_app(
                cas_root=cas_root,
                core_runs_root=cas_root / "runs",
                deployment_security=deployment,
                enable_security_middlewares=True,
                enable_csrf_protection=False,
                candidate_simulation_profiles=profiles,
                candidate_simulation_model_declarations=model_declarations,
            )

        # Reopen the actual source cycle once to seed the next app with the
        # already-persisted profile and declaration. This keeps the retained
        # path tied to its exact CAS inputs instead of supplying a test profile.
        bootstrap_app = build_app()
        with TestClient(bootstrap_app) as bootstrap_client:
            bootstrap_container = bootstrap_client.app.state.runtime_container
            bootstrap_control = bootstrap_container.control_service
            bootstrap_job = bootstrap_control._control_store.get_job(job_id)
            assert (
                bootstrap_job is not None
                and bootstrap_job.run_id == run_id
                and bootstrap_job.state == "completed"
            )
            bootstrap_action_service = bootstrap_container.acquisition_action_service
            with tenant_scope(None, tenant_id=served.TENANT, cell_id=served.CELL):
                bootstrap_origin = bootstrap_action_service._resolve_candidate_experiment_origin(
                    tenant_id=served.TENANT,
                    cell_id=served.CELL,
                    run_id=run_id,
                )
            persisted_prior = resolve_selected_acquisition_evaluation_parts(
                artifact_store=bootstrap_control._artifact_store,
                control_store=bootstrap_control._control_store,
                tenant_id=bootstrap_origin.tenant_id,
                cell_id=bootstrap_origin.cell_id,
                run_id=bootstrap_origin.run_id,
                generation_run=bootstrap_origin.effective_generation_run,
                source_cycle=bootstrap_origin.effective_source_cycle,
                design_problem_ref=bootstrap_origin.policy_scope.design_problem_ref,
            )
            source_profile = persisted_prior.input_record.profile
            source_declaration = persisted_prior.handoff.model_declaration
            if (
                persisted_prior.source.profile != source_profile
                or persisted_prior.source.model_declaration != source_declaration
            ):
                raise AssertionError("retained source profile was not selected by its N5 record")

        app = build_app(
            profiles=(source_profile,),
            model_declarations=(source_declaration,),
        )
        with TestClient(app) as client:
            container = client.app.state.runtime_container
            control = container.control_service
            context_owner = control._cycle_substrate_context_admission_owner
            if (
                type(context_owner) is not ConfiguredCandidateSimulationContextAdmissionOwner
                or context_owner.store is not control._artifact_store
                or tuple(context_owner.profiles) != (source_profile,)
                or tuple(context_owner.model_declarations) != (source_declaration,)
            ):
                raise AssertionError("retained source owner was not composed over reopened CAS")
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
                "profile_selection_ref": source_profile.profile_selection_ref,
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
                    bind_candidate_test_execution_port_factory(
                        monkeypatch=monkeypatch,
                        control_service=control,
                        fixture_port=issuer.port,
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
                    if continue_with_reentry:
                        from tests._helpers.candidate_experiment_served_execution import (
                            _standard_invocation_units,
                            run_candidate_experiment_served_execution,
                        )

                        standard_units_before = _standard_invocation_units(
                            control=control,
                            run_id=run_id,
                        )

                        def execute_retained_reentry(**execution_values):
                            nonlocal callback_active
                            callback_active = True
                            try:
                                execution = run_candidate_experiment_served_execution(
                                    values=execution_values["values"],
                                    origin=execution_values["origin"],
                                    request=execution_values["request"],
                                    decision_ref=execution_values["decision_ref"],
                                    policy_owner=policy_owner,
                                    monkeypatch=monkeypatch,
                                )
                            finally:
                                callback_active = False
                            if execution.current_action.evaluation_disposition != "new":
                                raise AssertionError(
                                    "retained R2 candidate reentry did not select a new N5 result"
                                )
                            _assert_candidate_experiment_n5_uses_current_wmr(
                                control=control,
                                origin=execution_values["origin"],
                                execution=execution,
                            )
                            retained_execution.append(execution)

                        reentry_callback = execute_retained_reentry
                    else:
                        standard_units_before = None
                        reentry_callback = None
                    result = run_candidate_experiment_action_oracle(
                        tmp_path=fixture_root / "candidate-oracle",
                        values=values,
                        policy_ref=selected_ref,
                        monkeypatch=monkeypatch,
                        idempotency_key=idempotency_key,
                        exercise_controls=not continue_with_reentry,
                        after_replay=reentry_callback,
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
                    if continue_with_reentry:
                        if len(retained_execution) != 1 or standard_units_before is None:
                            raise AssertionError("retained R2 served reentry did not complete once")
                        execution = retained_execution[0]
                        standard_units_after = _standard_invocation_units(
                            control=control,
                            run_id=run_id,
                        )
                        if (
                            execution.standard_invocation_units_before != standard_units_before
                            or execution.standard_invocation_units_after
                            != standard_units_before + 2
                            or standard_units_after != standard_units_before + 2
                            or n5_calls < 1
                        ):
                            raise AssertionError(
                                "retained R2 reentry did not consume exactly two standard units"
                            )
                        reentry_delta_verified[0] = True
                        result["standard_units_before"] = str(standard_units_before)
                        result["standard_units_after"] = str(standard_units_after)
                        result["reentry_job_id"] = execution.job_id
                        result["terminal_ref"] = str(execution.terminal_ref.artifact_id)
                        result["n5_controller_calls"] = str(n5_calls)
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
        if ledger_digest is not None and not continue_with_reentry:
            assert digest(ledger_path) == ledger_digest, "retained N5 ledger changed"
        assert JointSimulationHorizonController.run is original_n5_run
        mode_label = "retained_r2_served_reentry" if continue_with_reentry else "retained_r2_guard"
        ledger_label = (
            "expected_reentry_delta_verified"
            if reentry_delta_verified[0]
            else "unchanged"
            if ledger_digest is not None and not continue_with_reentry
            else "absent"
            if ledger_digest is None and not continue_with_reentry
            else "reentry_delta_unverified"
        )
        print(
            f"{mode_label}_source_preservation "
            f"cas_artifact_files={len(original_artifacts)} "
            f"sql_rows={sum(sum(rows.values()) for rows in original_rows.values())} "
            f"ledger={ledger_label} "
            "n5_guard=restored"
        )
    assert result is not None
    return result


def run_genuine_candidate_experiment_scenario(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    gateway,
    *,
    total_units: int = 5,
    expected_blocked: bool = False,
    subsequent_attempt_ids: tuple[str, ...] = (),
    after_execution: Callable[..., object] | None = None,
    authority_valid_until: datetime | Callable[[], datetime] | None = None,
    before_action_observer: Callable[..., object] | None = None,
) -> dict[str, object]:
    """Serve the genuine source and first candidate action; optionally continue inline."""
    from dataclasses import replace

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
    from tests._helpers.candidate_experiment_served_execution import (
        bind_candidate_test_execution_port_factory,
    )

    monkeypatch.setenv("POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS", "3")
    source = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "labor-source", include_owner_slot_manifest=True
    )

    def _candidate_experiment_invocation_quota(
        *, total_units: int = 5
    ) -> BudgetInvocationQuotaPolicy:
        return BudgetInvocationQuotaPolicy(
            allocation_id="served-labor-candidate-experiment",
            total_units=total_units,
            protected_units=1,
        )

    quota = _candidate_experiment_invocation_quota(total_units=total_units)
    observed: dict[str, object] = {}
    scenario_context: dict[str, object] = {}

    def serve_action(**values) -> None:
        control = values["control"]
        run_id = str(values["run_id"])
        assert values["job"].kind == "natural_language_run"
        assert values["job"].state == "completed"
        if before_action_observer is not None:
            before_action_observer(**values)
        client, trust = values["client"], values["trust"]
        action_service = values["action_service"]
        policy_owner = _candidate_experiment_policy_owner(
            control=control,
            fixture_root=tmp_path / "candidate-issuer",
            run_id=run_id,
            subsequent_attempt_ids=tuple(subsequent_attempt_ids),
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
            assert policy.scope.tenant_id == served.TENANT
            assert policy.scope.cell_id == served.CELL
            assert policy.scope.run_id == run_id
            assert policy.scope.source_job_id == values["job"].job_id
            scenario_context.update(
                control=control,
                action_service=action_service,
                values=values,
                policy_owner=policy_owner,
                policy=policy,
                policy_ref=policy_ref,
                quota=quota,
            )

            def execute_after_replay(**execution_values) -> None:
                from tests._helpers.candidate_experiment_served_execution import (
                    run_candidate_experiment_served_execution,
                )

                # The persisted evaluation used to replay the same selected N4
                # source once directly, once for the input, and twice while
                # resolving the execution. These records belong to the prior
                # run. Check its exact selected views before spending B quota.
                origin = execution_values["origin"]
                source_cycle = origin.effective_source_cycle
                simulation = source_cycle.simulation
                source_ref = simulation.candidate_simulation_n4_source_ref
                input_ref = simulation.candidate_simulation_n5_input_ref
                result_ref = simulation.simulation_result_ref
                execution_ref = artifacts.ArtifactRef.model_validate(
                    simulation.diagnostics["candidate_simulation_execution_selected_ref"]
                )
                assert source_ref is not None and input_ref is not None and result_ref is not None
                source_replay_counts = _assert_selected_n4_source_replay_is_consolidated(
                    monkeypatch,
                    artifact_store=control._artifact_store,
                    source_ref=source_ref,
                    execution_ref=execution_ref,
                    input_ref=input_ref,
                    expected_run_id=origin.run_id,
                    expected_tenant_id=origin.tenant_id,
                    expected_cell_id=origin.cell_id,
                )
                print(
                    "selected_n4_source_replay_counts "
                    f"baseline={source_replay_counts['preconsolidation']} "
                    f"batched={source_replay_counts['batched']} "
                    "retained_cas=served_candidate"
                )

                execution = run_candidate_experiment_served_execution(
                    values=execution_values["values"],
                    origin=execution_values["origin"],
                    request=execution_values["request"],
                    decision_ref=execution_values["decision_ref"],
                    policy_owner=policy_owner,
                    monkeypatch=monkeypatch,
                    current_action_profile_path=tmp_path / "first-current-action-profile",
                )
                assert execution.standard_invocation_units_before == 2
                assert execution.standard_invocation_units_after == 4
                if expected_blocked:
                    assert execution.current_action.evaluation_disposition == "blocked"
                    assert execution.current_action.selected_evaluation is None
                    assert execution.current_action.candidate_n5_result is not None
                    assert execution.terminal_history.evaluation is None
                    assert execution.terminal_history.reentry_evaluation is not None
                    assert execution.terminal_history.frontier_after is None
                else:
                    assert execution.current_action.evaluation_disposition == "new"
                    assert execution.terminal_history.frontier_after is not None
                assert execution.source_basis_preparations
                assert all(
                    observation.predicate_provenance == "recomputed"
                    and observation.reason_codes == ()
                    and observation.inputs_present
                    and observation.intent_ref_present
                    and observation.intent_present
                    for observation in execution.source_basis_preparations
                )
                assert policy_owner.template.max_standard_n5_invocations == total_units - 1
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
                _assert_candidate_experiment_n5_uses_current_wmr(
                    control=control,
                    origin=execution_values["origin"],
                    execution=execution,
                    resolved_reentry_evaluation=(
                        execution.terminal_history.reentry_evaluation if expected_blocked else None
                    ),
                )
                observed["execution"] = execution
                scenario_context.update(
                    origin=execution_values["origin"],
                    request=execution_values["request"],
                    decision_ref=execution_values["decision_ref"],
                )
                if after_execution is not None:
                    if artifacts.artifact_ref_identity_key(
                        execution_values["policy_ref"]
                    ) != artifacts.artifact_ref_identity_key(policy_ref):
                        raise AssertionError(
                            "after_execution policy ref differs from the selected policy"
                        )
                    scenario_context["after_execution_result"] = after_execution(
                        execution=execution,
                        values=execution_values["values"],
                        policy_ref=policy_ref,
                        policy_owner=policy_owner,
                        policy=policy,
                        origin=execution_values["origin"],
                        quota=quota,
                        request=execution_values["request"],
                        decision_ref=execution_values["decision_ref"],
                        control=control,
                        action_service=action_service,
                        source_owner_root=source.root,
                        prepared_catalog=prepared,
                    )

            resolved_authority_valid_until = (
                authority_valid_until()
                if callable(authority_valid_until)
                else authority_valid_until
            )
            observed.update(
                run_candidate_experiment_action_oracle(
                    tmp_path=tmp_path,
                    values=values,
                    policy_ref=policy_ref,
                    monkeypatch=monkeypatch,
                    after_replay=execute_after_replay,
                    authority_valid_until=resolved_authority_valid_until,
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
            gateway,
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
    return {
        "source_result": result,
        "source_status": observed["source_status"],
        "execution": observed["execution"],
        "observed": observed,
        "quota": quota,
        "source_owner_root": source.root,
        **scenario_context,
    }


def test_genuine_labor_policy_gets_signed_candidate_decision_and_fresh_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, served_recorded_candidate_gateway
) -> None:
    """Join served Labor source, HTTP PA2/DS9, candidate WDI, WMR, N5, and terminal GET."""
    run_genuine_candidate_experiment_scenario(
        tmp_path,
        monkeypatch,
        served_recorded_candidate_gateway,
        total_units=5,
    )
