"""Actual HTTP publication and installed custody with explicit synthetic authority."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from polisyos.core.artifacts import ArtifactRef, ArtifactWriteOptions, KeyPair, SchemaInfo
from polisyos.core.artifacts.signing import Ed25519Signer
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.decision_validity import (
    DecisionValidityEnvelope,
    DecisionValidityEvaluation,
    DecisionValidityStatus,
)
from polisyos.core.run.context import RunContext
from polisyos.core.security.cell import CellSpec, CellTier, TenantSpec
from polisyos.core.security.identity import PolicyOSRole
from polisyos.core.security.registry import CellRegistry
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.container import RuntimeContainerOverrides
from polisyos.runtime.http.dependencies import RuntimeApiContext, build_runtime_api_context
from polisyos.runtime.http.services.control import ControlPlaneService
from polisyos.scientist.evidence.claims.head_index import (
    ClaimLedgerOwnerPort,
    PacketBoundClaimLedgerSnapshot,
    UnappointedClaimLedgerOwner,
)
from polisyos.scientist.evidence.claims.lifecycle import ClaimLifecycleAction
from polisyos.scientist.evidence.claims.models import ClaimLedger, ClaimRecord
from polisyos.scientist.governance.continuous import published_signature_custody as custody
from polisyos.scientist.governance.continuous.governed_public_record import (
    PublicationMandateStatement,
)
from polisyos.scientist.governance.continuous.lifecycle_bridge import load_lifecycle_bridge_result
from polisyos.scientist.validation.decision_validity import DecisionValidityService
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _claims,
    _fixture_bearer,
    _IdentityProvider,
)
from tests.unit.scientist.evidence.claims.test_head_index import _build_packet_bound_owner_case

_TENANT = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_FOREIGN_TENANT = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


@dataclass
class _PublicationCase:
    context: RuntimeApiContext
    claim_owner: ClaimLedgerOwnerPort
    decision_validity: DecisionValidityService
    packet_ref: ArtifactRef
    registry: CellRegistry
    provider: _IdentityProvider
    cell_id: str
    bearer: str
    foreign_bearer: str
    config_path: Path
    config: dict[str, object]
    publisher: KeyPair
    institution: KeyPair

    @contextmanager
    def client(self, *, appointed: bool = True) -> Iterator[TestClient]:
        app = create_runtime_api_app(
            cas_root=self.context.cas_root,
            core_runs_root=self.context.cas_root / "runs",
            enable_security_middlewares=True,
            identity_provider=self.provider,
            cell_registry=self.registry,
            opa_client=_AllowOPA(),
            container_overrides=RuntimeContainerOverrides(
                runtime_api_context=self.context,
                decision_validity_service=self.decision_validity,
                claim_ledger_owner=(
                    self.claim_owner
                    if appointed
                    else UnappointedClaimLedgerOwner(store=self.context.store)
                ),
            ),
        )
        try:
            with TestClient(app) as client:
                yield client
        finally:
            # Application shutdown closes the guarded CAS. Reopen the real
            # persisted composition before the external institution signs or
            # the next application loads its deployment configuration.
            self.context = build_runtime_api_context(
                cas_root=self.context.cas_root,
                core_runs_root=self.context.cas_root / "runs",
            )
            self.decision_validity = ControlPlaneService.build_decision_validity_owner(
                self.context.store
            )
            self.claim_owner = replace(
                self.claim_owner,
                store=self.context.store,
                root_issuer=replace(self.claim_owner.root_issuer, store=self.context.store),
                issuance_verifier=replace(
                    self.claim_owner.issuance_verifier, store=self.context.store
                ),
                decision_packets=replace(
                    self.claim_owner.decision_packets, store=self.context.store
                ),
                independent_walk=replace(
                    self.claim_owner.independent_walk, store=self.context.store
                ),
                completed_batches=self.decision_validity,
            )

    def own_artifacts(self) -> None:
        for artifact_id in self.context.store.iter_artifact_ids():
            self.context.store.record_artifact_owner(
                artifact_id,
                tenant_id=_TENANT,
                cell_id=self.cell_id,
                writer="tests.synthetic.publication",
            )

    def post(self, client: TestClient, publication_class: str, **kwargs):
        return client.post(
            "/api/v1/runs/packet-snapshot/public-verification-record",
            params={"publication_class": publication_class},
            headers={"Authorization": f"Bearer {self.bearer}"},
            **kwargs,
        )


@pytest.fixture
def publication_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _PublicationCase:
    """Install real owners and independently signed synthetic test prerequisites."""
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.delenv("POLISYOS_PUBLIC_VERIFICATION_CONFIG", raising=False)
    context = build_runtime_api_context(
        cas_root=tmp_path / "cas", core_runs_root=tmp_path / "cas" / "runs"
    )
    validity = ControlPlaneService.build_decision_validity_owner(context.store)
    owner, _, packet_ref, _ = _build_packet_bound_owner_case(
        store=context.store,
        head_index_root=tmp_path / "heads",
        completed_batches=validity,
    )
    registry = CellRegistry()
    cell = CellSpec(tier=CellTier.SHARED, region="us-gov-west-1", max_tenants=50)
    registry.register_cell(cell)
    bearer = _fixture_bearer("governed-public-admin")
    foreign_bearer = _fixture_bearer("governed-public-foreign")
    provider = _IdentityProvider({})
    for tenant_id, token in ((_TENANT, bearer), (_FOREIGN_TENANT, foreign_bearer)):
        registry.register_tenant(
            TenantSpec(tenant_id=tenant_id, name=tenant_id, region="us-gov-west-1"),
            cell.cell_id,
        )
        provider.put_claim(
            token,
            _claims(
                tenant_id=tenant_id,
                cell_id=cell.cell_id,
                jti=token,
                roles=frozenset({PolicyOSRole.ADMIN}),
            ),
        )
    registry_ref = context.store.put_json(
        {"purpose": "explicit synthetic governed-public HTTP fixture"},
        ArtifactWriteOptions(kind="core.registry_bundle", media_type="application/json"),
    )
    run = RunContext.start(
        store=context.store,
        registry_bundle=registry_ref,
        run_id="packet-snapshot",
        tenant_id=_TENANT,
        cell_id=cell.cell_id,
    )
    run.add_output(packet_ref)
    run.finalize(status="completed")
    envelope = DecisionValidityEnvelope(
        decision_lineage_key="synthetic-governed-public-lineage",
        policy_fingerprint="synthetic-governed-public-v1",
    )
    validity.register_decision_packet(
        packet_ref=str(packet_ref.artifact_id),
        envelope=envelope,
        baseline=DecisionValidityEvaluation(
            decision_lineage_key=envelope.decision_lineage_key,
            status=DecisionValidityStatus.ACTIVE,
        ),
    )
    publisher, institution = KeyPair.generate(), KeyPair.generate()
    private_path = tmp_path / "publisher-private.pem"
    private_path.write_bytes(publisher.private_pem())
    private_path.chmod(0o600)
    (tmp_path / "publisher-public.pem").write_bytes(publisher.public_pem())
    (tmp_path / "institution-public.pem").write_bytes(institution.public_pem())
    config: dict[str, object] = {
        "issuer_id": "synthetic-publication-issuer",
        "private_key_path": private_path.name,
        "publisher_trusted_keys": [
            {
                "public_key_path": "publisher-public.pem",
                "issuer_id": "synthetic-publication-issuer",
                "purposes": ["governed_public_record"],
            }
        ],
        "mandate_trusted_keys": [
            {
                "public_key_path": "institution-public.pem",
                "issuer_id": "synthetic-appointing-institution",
                "purposes": ["governed_public_record_mandate"],
            }
        ],
    }
    config_path = tmp_path / "publication-config.json"
    config_path.write_text(json.dumps(config))
    monkeypatch.setenv("POLISYOS_PUBLIC_PUBLICATION_CONFIG", str(config_path))
    case = _PublicationCase(
        context,
        owner,
        validity,
        packet_ref,
        registry,
        provider,
        cell.cell_id,
        bearer,
        foreign_bearer,
        config_path,
        config,
        publisher,
        institution,
    )
    case.own_artifacts()
    return case


def _prepare_and_authorize(case: _PublicationCase) -> dict[str, object]:
    """Review the real HTTP draft, then sign it outside the publication owner."""
    with case.client() as client:
        container = client.app.state.runtime_container
        service = container.public_decision_verification_service
        assert service.issued_record_ids() == ()
        prepared = case.post(client, "governed_public_record_candidate")
        assert prepared.status_code == 201, prepared.text
        draft = prepared.json()
        assert draft["publication_class"] == "governed_public_record_candidate"
        assert "record_id" not in draft and "public_path" not in draft
        assert service.issued_record_ids() == ()
        not_authorized = case.post(client, "governed_public_record")
        assert not_authorized.status_code == 409, not_authorized.text
        assert not_authorized.json()["detail"] == "publication_mandate_not_configured"
        verifier_epoch = service.governed_owner.slot.verifier_epoch
    snapshot = case.claim_owner.resolve_current_for_packet(decision_packet_ref=case.packet_ref)
    assert isinstance(snapshot, PacketBoundClaimLedgerSnapshot)
    now = datetime.now(UTC)
    mandate = PublicationMandateStatement(
        authority_issuer_id="synthetic-appointing-institution",
        authority_key_id=case.institution.key_id,
        issuer_id="synthetic-publication-issuer",
        signing_key_id=case.publisher.key_id,
        public_document_digest=draft["public_document_digest"],
        decision_packet_ref=case.packet_ref,
        owner_scope_ref=snapshot.head.statement.owner_key.scope_ref,
        ledger_artifact_ref=snapshot.head.statement.ledger_artifact_ref,
        authority_basis="Explicit synthetic test appointment; no real institution is represented.",
        issued_at=now,
        valid_from=now - timedelta(minutes=1),
        valid_until=now + timedelta(days=1),
        staleness_after_seconds=5,
        verifier_epoch=verifier_epoch,
    )
    raw = json.dumps(
        mandate.model_dump(mode="json", exclude_none=False),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    mandate_ref = case.context.store.put_bytes(
        raw,
        ArtifactWriteOptions(
            kind="polisyos.publication_mandate",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.publication_mandate", version="1"),
        ),
    )
    case.context.store.sign_artifact(
        mandate_ref.artifact_id,
        Ed25519Signer(case.institution.private_key),
        signer_identity=mandate.authority_issuer_id,
    )
    case.config["mandate_ref"] = mandate_ref.model_dump(mode="json")
    case.config_path.write_text(json.dumps(case.config))
    case.own_artifacts()
    return draft


def _issue_and_read(case: _PublicationCase, client: TestClient):
    issued = case.post(client, "governed_public_record")
    assert issued.status_code == 201, issued.text
    locator = issued.json()
    assert locator["publication_class"] == "governed_public_record"
    assert locator["public_path"] == f"/public/decisions/{locator['record_id']}"
    verified = client.get(
        "/api/v1/public-decisions/verification", params={"record_id": locator["record_id"]}
    )
    assert verified.status_code == 200, verified.text
    assert verified.headers["cache-control"] == "no-store"
    result = verified.json()
    assert result["report_authentication"] == "verified", result
    assert result["cryptographic_signature"] == "valid"
    assert result["promoted_record"] == locator["promoted_record"]
    return locator["record_id"], result


def test_public_decision_projection_is_custody_bound(publication_case: _PublicationCase) -> None:
    """The actual public projection is exact, limited and bound to admitted custody."""
    case = publication_case
    draft = _prepare_and_authorize(case)
    with case.client() as client:
        record_id, result = _issue_and_read(case, client)
        assert result["public_document"] == draft["public_document"]
        document = result["public_document"]
        claim = document["ledger"]["current_claims"][0]
        assert claim["text"] == "The synthetic source contains this assertion."
        assert claim["support_status"] == "supported"
        assert claim["publishability"] == "publishable"
        assert document["ledger"]["events"][0]["action"] == "created"
        assert document["permitted_uses"] == ["bounded_public_custody"]
        assert "policy_performance" in document["denied_uses"]
        assert "first_publication" in document["denied_uses"]
        assert document["limitations"]
        assert result["dimensions"]["issuer_issuance"] == "established"
        assert result["dimensions"]["projection_faithfulness"] == "established"
        assert result["dimensions"]["current_authority"] == "not_established"
        assert result["dimensions"]["public_history_establishment"] == "not_established"
        snapshot = case.claim_owner.resolve_current_for_packet(decision_packet_ref=case.packet_ref)
        serialized = json.dumps(result)
        for private in (
            str(case.packet_ref.artifact_id),
            str(snapshot.head.head_ref.artifact_id),
            str(snapshot.head.statement.ledger_artifact_ref.artifact_id),
            "packet-snapshot",
            "snapshot-claim",
            snapshot.ledger.events[0].event_id,
        ):
            assert private not in serialized
        control = client.app.state.runtime_container.control_service
        watched = control.run_published_signature_custody_maintenance()
        assert watched.status == "watched"
        scan = custody.PublishedSignatureCustodyScan.model_validate(
            from_canonical_bytes(case.context.store.get_bytes(watched.scan_receipt_ref.artifact_id))
        )
        population = custody.resolve_public_signature_population(
            case.context.store, scan.population_ref
        )
        owner = (
            client.app.state.runtime_container.public_decision_verification_service.governed_owner
        )
        binding = owner.resolve_custody_binding(record_id)
        assert population.snapshot.members[0].signature_ref == binding.signature_ref
        assert population.snapshot.members[0].decision_packet_ref == case.packet_ref
        assert population.snapshot.members[0].affected_claim_ids == ("snapshot-claim",)


def test_first_governed_public_signature_is_custody_bound(
    publication_case: _PublicationCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """First issuance in this empty controlled store reaches advisory lifecycle and outbox."""
    case = publication_case
    _prepare_and_authorize(case)
    with case.client() as client:
        container = client.app.state.runtime_container
        assert container.public_decision_verification_service.issued_record_ids() == ()
        record_id, result = _issue_and_read(case, client)
        assert container.public_decision_verification_service.issued_record_ids() == (record_id,)
        assert result["dimensions"]["public_history_establishment"] == "not_established"
        binding = (
            container.public_decision_verification_service.governed_owner.resolve_custody_binding(
                record_id
            )
        )
        due = binding.published_at + timedelta(seconds=binding.staleness_after_seconds + 1)

        class DueCustodyClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return due if tz is None else due.astimezone(tz)

        monkeypatch.setattr(custody, "datetime", DueCustodyClock)
        watched = container.control_service.run_published_signature_custody_maintenance()
        assert watched.status == "watched", watched
        assert watched.scan_receipt_ref is not None
        assert watched.monitor_event_refs and watched.lifecycle_bridge_result_refs
        bridge = load_lifecycle_bridge_result(
            case.context.store, watched.lifecycle_bridge_result_refs[0]
        )
        assert bridge.decision_packet_ref == case.packet_ref
        assert bridge.monitor_projection_authority == "advisory"
        assert bridge.updated_ledger.events[-1].action is ClaimLifecycleAction.REVIEW_REQUIRED
        outbox = container.control_service.list_control_outbox(limit=100)
        matching = [
            event
            for event in outbox.events
            if event.topic == "control.decision_validity.published_signature_custody"
        ]
        assert matching
        assert matching[0].payload[
            "lifecycle_bridge_result_ref"
        ] == watched.lifecycle_bridge_result_refs[0].model_dump(mode="json")


def test_governed_http_rejects_foreign_tenant_body_and_unappointed_source(
    publication_case: _PublicationCase,
) -> None:
    case = publication_case
    with case.client() as client:
        foreign = client.post(
            "/api/v1/runs/packet-snapshot/public-verification-record",
            params={"publication_class": "governed_public_record_candidate"},
            headers={"Authorization": f"Bearer {case.foreign_bearer}"},
        )
        assert foreign.status_code == 403
        body = case.post(client, "governed_public_record_candidate", json={"verified": True})
        assert body.status_code == 422
        assert (
            client.app.state.runtime_container.public_decision_verification_service.issued_record_ids()
            == ()
        )
    with case.client(appointed=False) as client:
        refused = case.post(client, "governed_public_record_candidate")
        assert refused.status_code == 409, refused.text
        assert refused.json()["detail"] == "source_owner_not_admitted"


def test_governed_http_rejects_a_candidate_ledger_source(
    publication_case: _PublicationCase,
) -> None:
    case = publication_case
    store = case.context.store
    snapshot = case.claim_owner.resolve_current_for_packet(decision_packet_ref=case.packet_ref)
    candidate_run_id = "candidate-only"
    claim_payload = snapshot.ledger.current_claims[0].model_dump()
    claim_payload["run_id"] = candidate_run_id
    candidate_ref = case.claim_owner.persist_candidate_ledger(
        ledger=ClaimLedger(
            run_id=candidate_run_id, claims=[ClaimRecord.model_validate(claim_payload)]
        )
    )
    packet_ref = store.put_json(
        {"run_id": candidate_run_id, "claims_ref": candidate_ref.model_dump(mode="json")},
        ArtifactWriteOptions(kind="scientist.decision_packet", media_type="application/json"),
    )
    registry_ref = store.put_json(
        {"purpose": "candidate negative"},
        ArtifactWriteOptions(kind="core.registry_bundle", media_type="application/json"),
    )
    run = RunContext.start(
        store=store,
        registry_bundle=registry_ref,
        run_id=candidate_run_id,
        tenant_id=_TENANT,
        cell_id=case.cell_id,
    )
    run.add_output(packet_ref)
    run.finalize(status="completed")
    case.own_artifacts()
    with case.client() as client:
        refused = client.post(
            f"/api/v1/runs/{candidate_run_id}/public-verification-record",
            params={"publication_class": "governed_public_record_candidate"},
            headers={"Authorization": f"Bearer {case.bearer}"},
        )
        assert refused.status_code == 409, refused.text
        assert refused.json()["detail"] == "source_owner_not_admitted"
        assert (
            client.app.state.runtime_container.public_decision_verification_service.issued_record_ids()
            == ()
        )


@pytest.mark.parametrize("corruption", ["signature", "source"])
def test_governed_http_corruption_removes_public_content_and_custody_membership(
    publication_case: _PublicationCase,
    corruption: str,
) -> None:
    case = publication_case
    _prepare_and_authorize(case)
    with case.client() as client:
        record_id, _ = _issue_and_read(case, client)
        container = client.app.state.runtime_container
        binding = (
            container.public_decision_verification_service.governed_owner.resolve_custody_binding(
                record_id
            )
        )
        store = case.context.store
        if corruption == "signature":
            signature = store.get_signature(binding.signature_ref.artifact_id)
            store.put_signature(
                binding.signature_ref.artifact_id,
                signature.model_copy(update={"signature_hex": "00" * 64}),
            )
        else:
            snapshot = case.claim_owner.resolve_current_for_packet(
                decision_packet_ref=case.packet_ref
            )
            blob, _ = store.get_paths(snapshot.head.statement.ledger_artifact_ref.artifact_id)
            blob.write_bytes(blob.read_bytes() + b" ")
        refused = client.get(
            "/api/v1/public-decisions/verification", params={"record_id": record_id}
        ).json()
        assert refused["report_authentication"] == "invalid", refused
        assert refused["public_document"] is None and refused["promoted_record"] is None
        watched = container.control_service.run_published_signature_custody_maintenance()
        assert watched.status == "not_established"
        assert not watched.monitor_event_refs


def test_governed_http_rejects_invalid_mandate_signature_before_issuance(
    publication_case: _PublicationCase,
) -> None:
    """Capturing a present but invalid signature must not grant publication authority."""
    case = publication_case
    _prepare_and_authorize(case)
    mandate_ref = ArtifactRef.model_validate(case.config["mandate_ref"])
    signature = case.context.store.get_signature(mandate_ref.artifact_id)
    assert signature is not None
    case.context.store.put_signature(
        mandate_ref.artifact_id, signature.model_copy(update={"signature_hex": "00" * 64})
    )
    with case.client() as client:
        refused = case.post(client, "governed_public_record")
        assert refused.status_code == 409, refused.text
        assert refused.json()["detail"] == "record_signature_invalid"
        assert (
            client.app.state.runtime_container.public_decision_verification_service.issued_record_ids()
            == ()
        )
