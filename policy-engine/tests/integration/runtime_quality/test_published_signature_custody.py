"""Integration closure for the published-signature custody watcher."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.decision_validity import (
    DecisionValidityEnvelope,
    DecisionValidityEvaluation,
    DecisionValidityStatus,
)
from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
from polisyos.runtime.http.services.control import ControlPlaneService
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.http.services.control_registry_providers import ControlRegistryProviders
from polisyos.scientist.evidence.claims import (
    AppendOnlyClaimLedger,
    ClaimPublishability,
    ClaimRecord,
    ClaimSupportStatus,
    ClaimType,
)
from polisyos.scientist.evidence.claims.audit import _persist_append_only_claim_ledger
from polisyos.scientist.methods.search.readiness import DecisionReadiness


class _NoOpRetrievalService:
    """Avoid unrelated retrieval composition in this custody integration fixture."""

    def list_promotion_candidates(self) -> list[object]:
        """Return no candidates because this test owns no promotion path."""

        return []


def _put_json(store: FileSystemCAS, payload: object, *, kind: str) -> ArtifactRef:
    return store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=kind, version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _build_control_service(tmp_path) -> ControlPlaneService:
    store = FileSystemCAS(tmp_path / "cas")
    control_store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    return ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        artifact_store=store,
        control_store=control_store,
        retrieval_service=_NoOpRetrievalService(),
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="dev",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=cast("ControlRegistryProviders", SimpleNamespace()),
    )


def test_every_public_signature_is_watched_for_staleness(tmp_path) -> None:
    """A populated custody scan persists advisory lifecycle/outbox evidence; absence is a nonreceipt."""

    from polisyos.scientist.governance.continuous.published_signature_custody import (
        PersistedPublicSignaturePopulation,
        PublicSignaturePopulationMember,
        PublishedSignatureCustodyWatcher,
        StaticPublicSignaturePopulationProvider,
        persist_public_signature_population,
    )

    service = _build_control_service(tmp_path)
    try:
        claim = ClaimRecord(
            claim_id="claim-published-signature-custody",
            run_id="run-published-signature-custody",
            claim_type=ClaimType.FACTUAL,
            text="A publicly signed claim remains visible until its custody scan is refreshed.",
            support_status=ClaimSupportStatus.SUPPORTED,
            publishability=ClaimPublishability.PUBLISHABLE,
            readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
        )
        ledger_ref = _persist_append_only_claim_ledger(
            service._artifact_store,
            AppendOnlyClaimLedger(run_id=claim.run_id, current_claims=[claim]),
        )
        envelope = DecisionValidityEnvelope(
            decision_lineage_key="published-signature-custody-lineage",
            policy_fingerprint="published-signature-custody-v1",
        )
        packet_ref = _put_json(
            service._artifact_store,
            {
                "schema_version": "3.4",
                "run_id": claim.run_id,
                "claim_ledger_v2_ref": ledger_ref.model_dump(mode="json"),
                "decision_validity_envelope": envelope.model_dump(mode="json"),
                "decision_validity_baseline": DecisionValidityEvaluation(
                    decision_lineage_key=envelope.decision_lineage_key,
                    status=DecisionValidityStatus.ACTIVE,
                ).model_dump(mode="json"),
            },
            kind="scientist.decision_packet",
        )
        service._decision_validity_service.register_decision_packet(
            packet_ref=str(packet_ref.artifact_id),
            envelope=envelope,
            baseline=DecisionValidityEvaluation(
                decision_lineage_key=envelope.decision_lineage_key,
                status=DecisionValidityStatus.ACTIVE,
            ),
        )
        signature_ref = _put_json(
            service._artifact_store,
            {"signature": "synthetic-test-public-signature"},
            kind="policyos.public.signature",
        )
        now = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
        population: PersistedPublicSignaturePopulation = persist_public_signature_population(
            service._artifact_store,
            population_id="synthetic-published-signatures",
            population_provenance="synthetic_test",
            members=(
                PublicSignaturePopulationMember(
                    signature_ref=signature_ref,
                    decision_packet_ref=packet_ref,
                    affected_claim_ids=(claim.claim_id,),
                    published_at=now - timedelta(days=2),
                    staleness_after=timedelta(days=1),
                ),
            ),
            captured_at=now - timedelta(days=2),
        )
        watcher = PublishedSignatureCustodyWatcher(
            store=service._artifact_store,
            population_provider=StaticPublicSignaturePopulationProvider(population),
            lifecycle_publisher=service.publish_published_signature_custody_event,
        )

        watched = watcher.scan_once(now=now)

        assert watched.status == "watched"
        assert watched.population_provenance == "synthetic_test"
        assert watched.scan_receipt_ref is not None
        assert watched.monitor_event_refs
        assert watched.lifecycle_bridge_result_refs
        outbox = service.list_control_outbox(limit=10)
        assert any(
            event.topic == "control.decision_validity.published_signature_custody"
            for event in outbox.events
        )

        unappointed = PublishedSignatureCustodyWatcher(
            store=service._artifact_store,
            lifecycle_publisher=service.publish_published_signature_custody_event,
        ).scan_once(now=now)

        assert unappointed.status == "not_established"
        assert unappointed.predicate_provenance == "not_established"
        assert unappointed.scan_receipt_ref is not None
        assert not unappointed.monitor_event_refs
        assert "all_clear" not in unappointed.model_dump(mode="json")
    finally:
        service.close()
