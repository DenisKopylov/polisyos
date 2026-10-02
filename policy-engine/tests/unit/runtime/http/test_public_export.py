"""Actual HTTP publication and installed custody with explicit synthetic authority."""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

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
from polisyos.core.security.tenant_context import tenant_scope
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
    GovernedPublicRecordError,
    GovernedPublicRecordOwner,
    PublicationMandateStatement,
)
from polisyos.scientist.governance.continuous.lifecycle_bridge import load_lifecycle_bridge_result
from polisyos.scientist.validation.decision_validity import DecisionValidityService
from tests._helpers.artifacts import overwrite_signature_sidecar_for_test
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
        synthetic_owner = (
            app.state.runtime_container.public_decision_verification_service.governed_owner
        )
        if synthetic_owner is not None:
            synthetic_owner._synthetic_public_read_root_custody_for_tests = True
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
        with tenant_scope(None, tenant_id=_TENANT, cell_id=self.cell_id):
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


def _build_publication_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    selected_profile_evidence: bool = False,
) -> _PublicationCase:
    """Install real owners and independently signed synthetic test prerequisites."""
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.delenv("POLISYOS_PUBLIC_VERIFICATION_CONFIG", raising=False)
    context = build_runtime_api_context(
        cas_root=tmp_path / "cas", core_runs_root=tmp_path / "cas" / "runs"
    )
    registry = CellRegistry()
    cell = CellSpec(tier=CellTier.SHARED, region="us-gov-west-1", max_tenants=50)
    registry.register_cell(cell)
    evidence_refs = None
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
    with tenant_scope(None, tenant_id=_TENANT, cell_id=cell.cell_id):
        validity = ControlPlaneService.build_decision_validity_owner(context.store)
        if selected_profile_evidence:
            data = b"Synthetic evidence with two selected manifest profiles."

            def options(version: str) -> ArtifactWriteOptions:
                return ArtifactWriteOptions(
                    kind="fixture.claim_evidence",
                    media_type="text/plain",
                    schema=SchemaInfo(name="fixture.claim_evidence", version=version),
                )

            context.store.put_bytes(data, options("1"))
            evidence_refs = (
                context.store.put_bytes(data, options("2")),
                context.store.put_bytes(data, options("3")),
            )
        owner, _, packet_ref, _ = _build_packet_bound_owner_case(
            store=context.store,
            head_index_root=tmp_path / "heads",
            completed_batches=validity,
            evidence_refs=evidence_refs,
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


@pytest.fixture
def publication_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _PublicationCase:
    return _build_publication_case(tmp_path, monkeypatch)


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
    with tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id):
        snapshot = case.claim_owner.resolve_current_for_packet(
            decision_packet_ref=case.packet_ref
        )
        assert isinstance(snapshot, PacketBoundClaimLedgerSnapshot)
        now = datetime.now(UTC)
        public_document = draft["public_document"]
        assert isinstance(public_document, dict)
        version = public_document["schema_version"].rsplit(".", maxsplit=1)[1]
        mandate = PublicationMandateStatement(
            schema_version=f"polisyos.publication_mandate.{version}",
            profile=public_document["profile"],
            rule_version=f"governed-public-record.{version}",
            authority_issuer_id="synthetic-appointing-institution",
            authority_key_id=case.institution.key_id,
            issuer_id="synthetic-publication-issuer",
            signing_key_id=case.publisher.key_id,
            public_document_digest=draft["public_document_digest"],
            decision_packet_ref=case.packet_ref,
            owner_scope_ref=snapshot.head.statement.owner_key.scope_ref,
            ledger_artifact_ref=snapshot.head.statement.ledger_artifact_ref,
            authority_basis=(
                "Explicit synthetic test appointment; no real institution is represented."
            ),
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
                schema=SchemaInfo(
                    name="polisyos.publication_mandate",
                    version=mandate.schema_version.rsplit(".", maxsplit=1)[1].removeprefix("v"),
                ),
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
        with tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id):
            snapshot = case.claim_owner.resolve_current_for_packet(
                decision_packet_ref=case.packet_ref
            )
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
        with tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id):
            control = client.app.state.runtime_container.control_service
            watched = control.run_published_signature_custody_maintenance()
            assert watched.status == "watched"
            scan = custody.PublishedSignatureCustodyScan.model_validate(
                from_canonical_bytes(
                    case.context.store.get_bytes(watched.scan_receipt_ref.artifact_id)
                )
            )
            verification_service = client.app.state.runtime_container.public_decision_verification_service
            owner = verification_service.governed_owner
            assert owner is not None
            population = custody.resolve_public_signature_population(
                case.context.store,
                scan.population_ref,
                governed_owner=owner,
                governed_record_ids=(record_id,),
            )
            binding = owner.resolve_custody_binding(record_id)
        assert population.snapshot.members[0].signature_ref == binding.signature_ref
        assert population.snapshot.members[0].decision_packet_ref == case.packet_ref
        assert population.snapshot.members[0].affected_claim_ids == ("snapshot-claim",)


def test_anonymous_publication_refuses_after_only_current_closure_is_withdrawn(
    publication_case: _PublicationCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The served reader refuses with intact publication markers and before CAS replay."""
    case = publication_case
    _prepare_and_authorize(case)
    with case.client() as client:
        record_id, _ = _issue_and_read(case, client)
        owner = (
            client.app.state.runtime_container.public_decision_verification_service.governed_owner
        )
        assert owner is not None
        with tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id):
            binding = owner.resolve_custody_binding(record_id)
        locator = owner._index(record_id)
        assert owner._revoke_public_read_closure_for_test(record_id) is True
        closure = owner.store._ownership_index._get_public_read_closure(record_id)
        assert closure is not None
        assert closure["status"] == "revoked"

        def protected_replay_must_not_start(_index: object) -> None:
            pytest.fail("protected CAS replay began after closure withdrawal")

        monkeypatch.setattr(owner, "_resolve_index", protected_replay_must_not_start)
        protected_ids = {
            str(binding.signature_ref.artifact_id),
            str(binding.decision_packet_ref.artifact_id),
        }
        protected_reads: list[str] = []
        for operation in ("verify", "get_bytes", "get_manifest", "get_signature_bytes"):
            original = getattr(owner.store, operation)

            def observe_protected_read(
                artifact_id: object,
                *args: object,
                _operation: str = operation,
                _original: Callable[..., object] = original,
                **kwargs: object,
            ) -> object:
                identity = str(getattr(artifact_id, "artifact_id", artifact_id))
                if identity in protected_ids:
                    protected_reads.append(_operation)
                return _original(artifact_id, *args, **kwargs)

            monkeypatch.setattr(owner.store, operation, observe_protected_read)
        response = client.get(
            "/api/v1/public-decisions/verification", params={"record_id": record_id}
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["report_authentication"] == "not_established"
        assert body["cryptographic_signature"] == "not_established"
        assert body["reason_codes"] == ["public_read_closure_not_established"]
        assert body["public_document"] is None
        assert owner._index(record_id) == locator
        with tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id):
            control_service = client.app.state.runtime_container.control_service
            watched = control_service.run_published_signature_custody_maintenance()
        assert watched.status == "not_established", watched
        assert not watched.monitor_event_refs
        assert protected_reads == []


def test_private_reconciler_closes_retained_locator_without_rewriting_signed_record(
    publication_case: _PublicationCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy issuance gets an exact owner closure only through private maintenance."""
    case = publication_case
    _prepare_and_authorize(case)
    with case.client() as client:
        owner = (
            client.app.state.runtime_container.public_decision_verification_service.governed_owner
        )
        assert owner is not None
        original_persist = owner._persist_issuance_transaction
        original_complete = owner._complete_issuance_transaction

        def old_persist_without_intent(index_raw: bytes):
            index_data = json.loads(index_raw)
            index = SimpleNamespace(record_id=index_data["record_id"])
            return SimpleNamespace(record_id=index_data["record_id"]), b"legacy", index

        def old_publication_without_closure(
            _transaction: object,
            _transaction_raw: bytes,
            index_raw: bytes,
            index: SimpleNamespace,
        ) -> None:
            owner._atomic_new(
                owner.index_root / "issued" / (index.record_id + ".json"), index_raw
            )

        monkeypatch.setattr(owner, "_persist_issuance_transaction", old_persist_without_intent)
        monkeypatch.setattr(
            owner,
            "_complete_issuance_transaction",
            old_publication_without_closure,
        )
        with tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id):
            record_id = owner.issue(
                decision_id="packet-snapshot",
                decision_packet_ref=case.packet_ref,
                issued_at=datetime.now(UTC),
            )
        monkeypatch.setattr(owner, "_persist_issuance_transaction", original_persist)
        monkeypatch.setattr(owner, "_complete_issuance_transaction", original_complete)

        locator_path = owner.index_root / "issued" / (record_id + ".json")
        locator_before = locator_path.read_bytes()
        with tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id):
            index = owner._index(record_id)
            _record, _draft, _mandate, _key, admission = owner._resolve_index(index)
            publication_ref = admission.publication.artifact_ref
            record_bytes_before = owner.store.get_bytes(publication_ref)
            signature_bytes_before = owner.store.get_signature_bytes(publication_ref)
        assert owner.store._ownership_index._get_public_read_closure(record_id) is None

        original_index = owner._index

        def locator_must_not_be_read(_record_id: str):
            pytest.fail("anonymous verification read the locator before closure admission")

        monkeypatch.setattr(owner, "_index", locator_must_not_be_read)
        refused = owner.verify(record_id)
        assert refused.report_authentication == "not_established"
        assert refused.reason_codes == ("public_read_closure_not_established",)
        monkeypatch.setattr(owner, "_index", original_index)

        with tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id):
            control_service = client.app.state.runtime_container.control_service
            watched = control_service.run_published_signature_custody_maintenance()
        assert watched.status == "watched", watched
        assert locator_path.read_bytes() == locator_before
        closure = owner.store._ownership_index._get_public_read_closure(record_id)
        assert closure is not None and closure["status"] == "active"
        with (
            tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id),
            owner.store._authorize_governed_public_read(
                record_id, owner_token=owner._public_read_owner_token
            ),
        ):
            record_bytes_after = owner.store.get_bytes(publication_ref)
            signature_bytes_after = owner.store.get_signature_bytes(publication_ref)
        assert record_bytes_after == record_bytes_before
        assert signature_bytes_after == signature_bytes_before
        served = client.get(
            "/api/v1/public-decisions/verification", params={"record_id": record_id}
        )
        assert served.status_code == 200, served.text
        assert served.json()["report_authentication"] == "verified"


@pytest.mark.parametrize("interrupted_directory", ["issued", "completions"])
def test_private_reconciler_retries_issuance_after_durable_boundaries(
    publication_case: _PublicationCase,
    monkeypatch: pytest.MonkeyPatch,
    interrupted_directory: str,
) -> None:
    """Intent, closure, locator and completion recover without restamping bytes."""
    case = publication_case
    _prepare_and_authorize(case)
    with case.client() as client:
        owner = (
            client.app.state.runtime_container.public_decision_verification_service.governed_owner
        )
        assert owner is not None
        original_atomic_new = GovernedPublicRecordOwner._atomic_new
        injected = False

        def interrupt_once(path: Path, raw: bytes) -> None:
            nonlocal injected
            if path.parent.name == interrupted_directory and not injected:
                injected = True
                raise OSError("injected issuance boundary interruption")
            original_atomic_new(path, raw)

        monkeypatch.setattr(
            GovernedPublicRecordOwner,
            "_atomic_new",
            staticmethod(interrupt_once),
        )
        with (
            tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id),
            pytest.raises(GovernedPublicRecordError),
        ):
            owner.issue(
                decision_id="packet-snapshot",
                decision_packet_ref=case.packet_ref,
                issued_at=datetime.now(UTC),
            )
        assert injected
        monkeypatch.setattr(
            GovernedPublicRecordOwner,
            "_atomic_new",
            staticmethod(original_atomic_new),
        )
        transaction_paths = tuple((owner.index_root / "transactions").glob("*.json"))
        assert len(transaction_paths) == 1
        record_id = transaction_paths[0].stem
        transaction = json.loads(transaction_paths[0].read_bytes())
        locator_bytes = transaction["index_json"].encode("utf-8")

        with tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id):
            assert owner.reconcile_public_read_closures() == (record_id,)
        locator_path = owner.index_root / "issued" / (record_id + ".json")
        completion_path = owner.index_root / "completions" / (record_id + ".json")
        assert locator_path.read_bytes() == locator_bytes
        assert completion_path.is_file()
        closure = owner.store._ownership_index._get_public_read_closure(record_id)
        assert closure is not None and closure["status"] == "active"
        served = client.get(
            "/api/v1/public-decisions/verification", params={"record_id": record_id}
        )
        assert served.status_code == 200, served.text
        assert served.json()["report_authentication"] == "verified"


def test_private_reconciler_rejects_symlinked_owner_directory_before_escape(
    publication_case: _PublicationCase,
    tmp_path: Path,
) -> None:
    """A symlinked locator parent cannot redirect owner transitions outside the root."""
    case = publication_case
    _prepare_and_authorize(case)
    with case.client() as client:
        owner = (
            client.app.state.runtime_container.public_decision_verification_service.governed_owner
        )
        assert owner is not None
        with tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id):
            record_id = owner.issue(
                decision_id="packet-snapshot",
                decision_packet_ref=case.packet_ref,
                issued_at=datetime.now(UTC),
            )

        issued_dir = owner.index_root / "issued"
        retained_issued_dir = owner.index_root / "issued-retained"
        locator_path = issued_dir / (record_id + ".json")
        locator_bytes = locator_path.read_bytes()
        transaction_path = owner._issuance_transaction_path(record_id)
        completion_path = owner._issuance_completion_path(record_id)
        transaction_bytes = transaction_path.read_bytes()
        completion_bytes = completion_path.read_bytes()
        closure_before = owner.store._ownership_index._get_public_read_closure(record_id)
        assert closure_before is not None and closure_before["status"] == "active"

        outside_dir = tmp_path / "outside-owner-root"
        outside_dir.mkdir()
        sentinel = outside_dir / "preexisting.marker"
        sentinel.write_bytes(b"outside bytes stay unchanged")
        outside_before = tuple(sorted((path.name, path.read_bytes()) for path in outside_dir.iterdir()))

        issued_dir.rename(retained_issued_dir)
        issued_dir.symlink_to(outside_dir, target_is_directory=True)
        with (
            tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id),
            pytest.raises(
                GovernedPublicRecordError, match="issuance_owner_directory_invalid"
            ),
        ):
            owner.reconcile_public_read_closures()

        outside_after = tuple(sorted((path.name, path.read_bytes()) for path in outside_dir.iterdir()))
        assert outside_after == outside_before
        assert not (outside_dir / (record_id + ".json")).exists()
        assert (retained_issued_dir / (record_id + ".json")).read_bytes() == locator_bytes
        assert transaction_path.read_bytes() == transaction_bytes
        assert completion_path.read_bytes() == completion_bytes
        assert owner.store._ownership_index._get_public_read_closure(record_id) == closure_before


def test_candidate_preparation_remains_available_without_public_root_custody(
    publication_case: _PublicationCase,
) -> None:
    """Unknown root custody limits issuance but does not refuse ordinary candidates."""
    case = publication_case
    _prepare_and_authorize(case)
    with case.client() as client:
        owner = (
            client.app.state.runtime_container.public_decision_verification_service.governed_owner
        )
        assert owner is not None
        owner._synthetic_public_read_root_custody_for_tests = False
        with tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id):
            candidate = owner.prepare(
                decision_id="packet-snapshot",
                decision_packet_ref=case.packet_ref,
                issued_at=datetime.now(UTC),
            )
            assert candidate.candidate_ref is not None
            with pytest.raises(
                GovernedPublicRecordError,
                match="public_read_root_custody_not_established",
            ):
                owner.issue(
                    decision_id="packet-snapshot",
                    decision_packet_ref=case.packet_ref,
                    issued_at=datetime.now(UTC),
                )


def test_http_publication_relocates_selected_manifest_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The served route preserves distinct selected views without publishing digests."""
    case = _build_publication_case(
        tmp_path, monkeypatch, selected_profile_evidence=True
    )
    draft = _prepare_and_authorize(case)
    with tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id):
        snapshot = case.claim_owner.resolve_current_for_packet(
            decision_packet_ref=case.packet_ref
        )
    assert isinstance(snapshot, PacketBoundClaimLedgerSnapshot)
    source_refs = snapshot.ledger.current_claims[0].evidence_refs
    assert len(source_refs) == 2
    assert source_refs[0].artifact_id == source_refs[1].artifact_id
    assert all(ref.manifest_profile_sha256 is not None for ref in source_refs)
    assert source_refs[0].manifest_profile_sha256 != source_refs[1].manifest_profile_sha256

    public_refs = draft["public_document"]["ledger"]["current_claims"][0]["evidence_refs"]
    assert len(public_refs) == 2
    assert public_refs[0]["artifact_id"] == public_refs[1]["artifact_id"]
    assert public_refs[0]["manifest_profile_sha256"].startswith("gph_")
    assert public_refs[1]["manifest_profile_sha256"].startswith("gph_")
    assert public_refs[0]["manifest_profile_sha256"] != public_refs[1]["manifest_profile_sha256"]

    with case.client() as client:
        record_id, result = _issue_and_read(case, client)
    assert result["public_document"] == draft["public_document"]
    serialized = json.dumps(result)
    for ref in source_refs:
        assert str(ref.artifact_id) not in serialized
        assert ref.manifest_profile_sha256 not in serialized
    assert record_id.startswith("gpr_")


def test_governed_owner_rejects_removed_selected_view_and_keeps_tenant_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing selected view cannot fall back to its same-blob default profile."""
    case = _build_publication_case(
        tmp_path, monkeypatch, selected_profile_evidence=True
    )
    _prepare_and_authorize(case)
    with case.client() as client:
        issued = case.post(client, "governed_public_record")
        assert issued.status_code == 201, issued.text
        locator = issued.json()
        assert locator["publication_class"] == "governed_public_record"
        assert locator["public_path"] == f"/public/decisions/{locator['record_id']}"
        container = client.app.state.runtime_container
        owner = container.public_decision_verification_service.governed_owner
        assert owner is not None
        with tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id):
            snapshot = case.claim_owner.resolve_current_for_packet(
                decision_packet_ref=case.packet_ref
            )
            assert isinstance(snapshot, PacketBoundClaimLedgerSnapshot)
            source_refs = snapshot.ledger.current_claims[0].evidence_refs
            assert len(source_refs) == 2
            assert source_refs[0].artifact_id == source_refs[1].artifact_id
            assert (
                source_refs[0].manifest_profile_sha256
                != source_refs[1].manifest_profile_sha256
            )

            selected_ref = source_refs[1]
            raw = b"Synthetic evidence with two selected manifest profiles."
            assert owner._raw(selected_ref) == raw

            present_profiles = {ref.manifest_profile_sha256 for ref in source_refs}
            absent_profile = next(
                f"sha256:{digit * 64}"
                for digit in "0123456789abcdef"
                if f"sha256:{digit * 64}" not in present_profiles
                and not owner.store.has_manifest_view(
                    selected_ref.artifact_id, f"sha256:{digit * 64}"
                )
            )
            assert not owner.store.has_manifest_view(
                selected_ref.artifact_id, absent_profile
            )
            missing_view = selected_ref.model_copy(
                update={"manifest_profile_sha256": absent_profile}
            )
            assert missing_view.artifact_id == selected_ref.artifact_id
            assert missing_view.kind == selected_ref.kind
            assert missing_view.media_type == selected_ref.media_type
            with pytest.raises(GovernedPublicRecordError, match="record_evidence_unavailable"):
                owner._raw(missing_view)

            # The patch adds no permission layer: a tenant still reads its own selected ref.
            assert case.context.store.get_bytes(selected_ref) == raw


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
        with tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id):
            owner = container.public_decision_verification_service.governed_owner
            assert owner is not None
            binding = owner.resolve_custody_binding(record_id)

            candidate_payload = {"candidate_only": True, "scope": "unrelated"}
            candidate_default = case.context.store.put_json(
                candidate_payload,
                ArtifactWriteOptions(
                    kind="tests.synthetic.candidate.default", media_type="application/json"
                ),
            )
            candidate_view = case.context.store.put_json(
                candidate_payload,
                ArtifactWriteOptions(
                    kind="tests.synthetic.candidate.selected", media_type="application/json"
                ),
            )
            case.context.store.record_artifact_owner(
                candidate_view.artifact_id,
                tenant_id=_TENANT,
                cell_id=case.cell_id,
                writer="tests.synthetic.publication_candidate",
            )
            assert candidate_default.artifact_id == candidate_view.artifact_id
            assert case.context.store.get_bytes(candidate_view) == case.context.store.get_bytes(
                candidate_default
            )

            with (
                tenant_scope(None, tenant_id=_FOREIGN_TENANT, cell_id=case.cell_id),
                pytest.raises(GovernedPublicRecordError),
            ):
                owner.verify_custody_binding_artifacts(
                        record_id,
                        signature_ref=binding.signature_ref,
                        decision_packet_ref=binding.decision_packet_ref,
                    )

            owner_reads: list[str] = []
            verify_binding_artifacts = owner.verify_custody_binding_artifacts

            def observe_owner_read(
                observed_record_id: str,
                *,
                signature_ref: ArtifactRef,
                decision_packet_ref: ArtifactRef,
            ) -> None:
                owner_reads.append(observed_record_id)
                verify_binding_artifacts(
                    observed_record_id,
                    signature_ref=signature_ref,
                    decision_packet_ref=decision_packet_ref,
                )

            monkeypatch.setattr(owner, "verify_custody_binding_artifacts", observe_owner_read)
            due = binding.published_at + timedelta(seconds=binding.staleness_after_seconds + 1)

            class DueCustodyClock(datetime):
                @classmethod
                def now(cls, tz=None):
                    return due if tz is None else due.astimezone(tz)

            monkeypatch.setattr(custody, "datetime", DueCustodyClock)
            watched = container.control_service.run_published_signature_custody_maintenance()
            assert watched.status == "watched", watched
            assert owner_reads
            assert set(owner_reads) == {record_id}
            assert watched.scan_receipt_ref is not None
            assert watched.monitor_event_refs
            assert watched.lifecycle_bridge_result_refs
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
    candidate_run_id = "candidate-only"
    with tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id):
        snapshot = case.claim_owner.resolve_current_for_packet(
            decision_packet_ref=case.packet_ref
        )
        claim_payload = snapshot.ledger.current_claims[0].model_dump()
        claim_payload["run_id"] = candidate_run_id
        candidate_ref = case.claim_owner.persist_candidate_ledger(
            ledger=ClaimLedger(
                run_id=candidate_run_id, claims=[ClaimRecord.model_validate(claim_payload)]
            )
        )
        packet_ref = store.put_json(
            {"run_id": candidate_run_id, "claims_ref": candidate_ref.model_dump(mode="json")},
            ArtifactWriteOptions(
                kind="scientist.decision_packet", media_type="application/json"
            ),
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
    tmp_path: Path,
) -> None:
    case = publication_case
    _prepare_and_authorize(case)
    with case.client() as client:
        record_id, _ = _issue_and_read(case, client)
        container = client.app.state.runtime_container
        with tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id):
            binding = (
                container.public_decision_verification_service.governed_owner.resolve_custody_binding(
                    record_id
                )
            )
        store = case.context.store
        if corruption == "signature":
            with tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id):
                signature = store.get_signature(binding.signature_ref)
            overwrite_signature_sidecar_for_test(
                store,
                binding.signature_ref,
                signature.model_copy(update={"signature_hex": "00" * 64}),
                tmp_root=tmp_path,
            )
        else:
            with tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id):
                snapshot = case.claim_owner.resolve_current_for_packet(
                    decision_packet_ref=case.packet_ref
                )
            blob, _ = store._paths(snapshot.head.statement.ledger_artifact_ref.artifact_id)
            blob.write_bytes(blob.read_bytes() + b" ")
        refused = client.get(
            "/api/v1/public-decisions/verification", params={"record_id": record_id}
        ).json()
        assert refused["report_authentication"] == "invalid", refused
        assert refused["public_document"] is None and refused["promoted_record"] is None
        with tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id):
            watched = container.control_service.run_published_signature_custody_maintenance()
        assert watched.status == "not_established"
        assert not watched.monitor_event_refs


def test_governed_http_rejects_invalid_mandate_signature_before_issuance(
    publication_case: _PublicationCase,
    tmp_path: Path,
) -> None:
    """Capturing a present but invalid signature must not grant publication authority."""
    case = publication_case
    _prepare_and_authorize(case)
    mandate_ref = ArtifactRef.model_validate(case.config["mandate_ref"])
    with tenant_scope(None, tenant_id=_TENANT, cell_id=case.cell_id):
        signature = case.context.store.get_signature(mandate_ref)
    assert signature is not None
    overwrite_signature_sidecar_for_test(
        case.context.store,
        mandate_ref,
        signature.model_copy(update={"signature_hex": "00" * 64}),
        tmp_root=tmp_path,
    )
    with case.client() as client:
        refused = case.post(client, "governed_public_record")
        assert refused.status_code == 409, refused.text
        assert refused.json()["detail"] == "record_signature_invalid"
        assert (
            client.app.state.runtime_container.public_decision_verification_service.issued_record_ids()
            == ()
        )
