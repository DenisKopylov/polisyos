"""Persist and revisit advisory custody evidence for public signatures.

This module watches only an explicitly supplied population.  Its production
default is an unappointed provider, so the absence of a population is a
persisted ``not_established`` nonreceipt rather than an all-clear.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts as core_artifacts
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.scientist.governance.continuous.monitors import (
    GovernanceMonitorEvent,
    monitor_event_id,
    persist_governance_monitor_event,
)

PUBLIC_SIGNATURE_POPULATION_KIND = "scientist.public_signature_population"
PUBLIC_SIGNATURE_POPULATION_SCHEMA_NAME = "polisyos.scientist.PublicSignaturePopulation"
PUBLIC_SIGNATURE_CUSTODY_SCAN_KIND = "scientist.published_signature_custody_scan"
PUBLIC_SIGNATURE_CUSTODY_SCAN_SCHEMA_NAME = "polisyos.scientist.PublishedSignatureCustodyScan"
_SCHEMA_VERSION = "1.0"
_CANON = CanonSpec(forbid_floats=False)


class PublicSignaturePopulationMember(BaseModel):
    """One public signature whose freshness must remain under custody."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    signature_ref: core_artifacts.ArtifactRef
    decision_packet_ref: core_artifacts.ArtifactRef
    affected_claim_ids: tuple[str, ...] = Field(min_length=1)
    published_at: datetime
    staleness_after_seconds: int = Field(gt=0)


class PublicSignaturePopulationSnapshot(BaseModel):
    """A resolved, non-vacuous population supplied by an appointed producer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    population_id: str = Field(min_length=1)
    population_provenance: Literal["institutionally_supplied", "synthetic_test"]
    members: tuple[PublicSignaturePopulationMember, ...] = Field(min_length=1)
    captured_at: datetime


class PersistedPublicSignaturePopulation(BaseModel):
    """Exact persisted population handle; no unverified snapshot crosses the watcher boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    population_ref: core_artifacts.ArtifactRef
    population_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    snapshot: PublicSignaturePopulationSnapshot


class PublicSignaturePopulationNonReceipt(BaseModel):
    """Fail-closed population result for an unappointed or unresolved provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["not_established"] = "not_established"
    predicate_provenance: Literal["not_established"] = "not_established"
    reason: str = Field(min_length=1)


class PublicSignaturePopulationProvider(Protocol):
    """Resolve the whole signed population or a typed nonreceipt."""

    def resolve(
        self,
    ) -> PersistedPublicSignaturePopulation | PublicSignaturePopulationNonReceipt:
        """Return one exact population result without inventing an appointment."""


class UnappointedPublicSignaturePopulationProvider:
    """Production default: no public-signature population authority is appointed."""

    def resolve(self) -> PublicSignaturePopulationNonReceipt:
        """Return the explicit nonreceipt instead of treating absence as an empty set."""

        return PublicSignaturePopulationNonReceipt(
            reason="public_signature_population_provider_unappointed"
        )


class StaticPublicSignaturePopulationProvider:
    """Return one already-persisted population; intended for integration embeddings and tests."""

    def __init__(self, population: PersistedPublicSignaturePopulation) -> None:
        self._population = population

    def resolve(self) -> PersistedPublicSignaturePopulation:
        """Return the exact persisted population supplied at construction."""

        return self._population


class PublishedSignatureCustodyScan(BaseModel):
    """Persisted watcher outcome that never projects population absence as a pass."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    status: Literal["watched", "not_established", "blocked"]
    scanned_at: datetime
    predicate_provenance: Literal[
        "institutionally_supplied", "synthetic_test", "not_established"
    ]
    population_ref: core_artifacts.ArtifactRef | None = None
    population_content_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    population_provenance: Literal["institutionally_supplied", "synthetic_test"] | None = None
    member_count: int = Field(ge=0)
    monitor_event_refs: tuple[core_artifacts.ArtifactRef, ...] = ()
    lifecycle_bridge_result_refs: tuple[core_artifacts.ArtifactRef, ...] = ()
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_nonreceipt_boundary(self) -> PublishedSignatureCustodyScan:
        if self.status == "not_established":
            if self.predicate_provenance != "not_established" or self.member_count != 0:
                raise ValueError("population nonreceipt cannot carry a watched denominator")
            return self
        if self.population_ref is None or self.population_content_hash is None:
            raise ValueError("watched custody scans require a persisted population")
        return self


class PersistedPublishedSignatureCustodyScan(BaseModel):
    """Exact handle for a persisted watcher result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scan_receipt_ref: core_artifacts.ArtifactRef
    scan_receipt_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    scan: PublishedSignatureCustodyScan


class PublishedSignatureCustodyResult(BaseModel):
    """Runtime return value with the receipt ref required for audit and outbox consumers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["watched", "not_established", "blocked"]
    predicate_provenance: Literal[
        "institutionally_supplied", "synthetic_test", "not_established"
    ]
    population_provenance: Literal["institutionally_supplied", "synthetic_test"] | None = None
    scan_receipt_ref: core_artifacts.ArtifactRef | None = None
    monitor_event_refs: tuple[core_artifacts.ArtifactRef, ...] = ()
    lifecycle_bridge_result_refs: tuple[core_artifacts.ArtifactRef, ...] = ()
    reason: str = Field(min_length=1)


class PublishedSignatureCustodyLifecyclePublication(Protocol):
    """Narrow result returned after advisory custody lifecycle publication."""

    @property
    def lifecycle_bridge_result_ref(self) -> core_artifacts.ArtifactRef:
        """Return the persisted result of the real claim-lifecycle bridge."""


class PublishedSignatureCustodyLifecyclePublisher(Protocol):
    """Narrow runtime bridge for advisory custody events."""

    def __call__(
        self, monitor_event_ref: core_artifacts.ArtifactRef
    ) -> PublishedSignatureCustodyLifecyclePublication:
        """Persist the claim-lifecycle and control-outbox consequence for one event."""


def _population_inputs(snapshot: PublicSignaturePopulationSnapshot) -> list[core_artifacts.InputRef]:
    """Return the exact signature and packet inputs carried by a population snapshot."""

    inputs: list[core_artifacts.InputRef] = []
    for index, member in enumerate(snapshot.members):
        inputs.extend(
            (
                core_artifacts.InputRef(
                    artifact_id=member.signature_ref.artifact_id,
                    role=f"signature[{index}]",
                ),
                core_artifacts.InputRef(
                    artifact_id=member.decision_packet_ref.artifact_id,
                    role=f"decision_packet[{index}]",
                ),
            )
        )
    return inputs


def _assert_exact_artifact(
    store: core_artifacts.ArtifactStore,
    ref: core_artifacts.ArtifactRef,
) -> None:
    """Verify a referenced artifact exists, verifies, and agrees with its manifest identity."""

    report = store.verify(ref.artifact_id)
    manifest = store.get_manifest(ref.artifact_id)
    if (
        not report.ok
        or manifest.artifact_id != ref.artifact_id
        or manifest.kind != ref.kind
        or manifest.media_type != ref.media_type
    ):
        raise ValueError("public_signature_custody_ref_unresolvable")


def persist_public_signature_population(
    store: core_artifacts.ArtifactStore,
    *,
    population_id: str,
    population_provenance: Literal["institutionally_supplied", "synthetic_test"],
    members: tuple[PublicSignaturePopulationMember, ...],
    captured_at: datetime,
) -> PersistedPublicSignaturePopulation:
    """Persist and exactly reload one non-vacuous public-signature population."""

    snapshot = PublicSignaturePopulationSnapshot(
        population_id=population_id,
        population_provenance=population_provenance,
        members=members,
        captured_at=captured_at,
    )
    for member in snapshot.members:
        _assert_exact_artifact(store, member.signature_ref)
        _assert_exact_artifact(store, member.decision_packet_ref)
    ref = store.put_json(
        snapshot,
        core_artifacts.PutOptions(
            kind=PUBLIC_SIGNATURE_POPULATION_KIND,
            media_type="application/json",
            schema=core_artifacts.SchemaInfo(
                name=PUBLIC_SIGNATURE_POPULATION_SCHEMA_NAME,
                version=_SCHEMA_VERSION,
            ),
            inputs=_population_inputs(snapshot),
        ),
        canon_spec=_CANON,
    )
    return resolve_public_signature_population(store, ref)


def resolve_public_signature_population(
    store: core_artifacts.ArtifactStore,
    ref: core_artifacts.ArtifactRef,
) -> PersistedPublicSignaturePopulation:
    """Resolve a snapshot and reject manifest, input, or canonical-byte drift."""

    raw = store.get_bytes(ref.artifact_id)
    report = store.verify(ref.artifact_id)
    manifest = store.get_manifest(ref.artifact_id)
    snapshot = PublicSignaturePopulationSnapshot.model_validate(from_canonical_bytes(raw))
    if (
        not report.ok
        or "sha256:" + hashlib.sha256(raw).hexdigest() != str(ref.artifact_id)
        or ref.kind != PUBLIC_SIGNATURE_POPULATION_KIND
        or ref.media_type != "application/json"
        or manifest.artifact_id != ref.artifact_id
        or manifest.kind != PUBLIC_SIGNATURE_POPULATION_KIND
        or manifest.media_type != "application/json"
        or manifest.artifact_schema
        != core_artifacts.SchemaInfo(
            name=PUBLIC_SIGNATURE_POPULATION_SCHEMA_NAME,
            version=_SCHEMA_VERSION,
        )
        or manifest.canon != core_artifacts.CanonInfo.from_spec(_CANON)
        or manifest.inputs != _population_inputs(snapshot)
        or to_canonical_bytes(snapshot, _CANON) != raw
    ):
        raise ValueError("public_signature_population_artifact_binding_mismatch")
    for member in snapshot.members:
        _assert_exact_artifact(store, member.signature_ref)
        _assert_exact_artifact(store, member.decision_packet_ref)
    return PersistedPublicSignaturePopulation(
        population_ref=ref,
        population_content_hash="sha256:" + hashlib.sha256(raw).hexdigest(),
        snapshot=snapshot,
    )


def _scan_inputs(scan: PublishedSignatureCustodyScan) -> list[core_artifacts.InputRef]:
    """Return the population and monitor receipts that make one scan replayable."""

    inputs: list[core_artifacts.InputRef] = []
    if scan.population_ref is not None:
        inputs.append(
            core_artifacts.InputRef(
                artifact_id=scan.population_ref.artifact_id,
                role="public_signature_population",
            )
        )
    inputs.extend(
        core_artifacts.InputRef(artifact_id=ref.artifact_id, role=f"monitor_event[{index}]")
        for index, ref in enumerate(scan.monitor_event_refs)
    )
    inputs.extend(
        core_artifacts.InputRef(
            artifact_id=ref.artifact_id,
            role=f"lifecycle_bridge_result[{index}]",
        )
        for index, ref in enumerate(scan.lifecycle_bridge_result_refs)
    )
    return inputs


def persist_published_signature_custody_scan(
    store: core_artifacts.ArtifactStore,
    scan: PublishedSignatureCustodyScan,
) -> PersistedPublishedSignatureCustodyScan:
    """Persist and read back one custody result, including explicit nonreceipts."""

    ref = store.put_json(
        scan,
        core_artifacts.PutOptions(
            kind=PUBLIC_SIGNATURE_CUSTODY_SCAN_KIND,
            media_type="application/json",
            schema=core_artifacts.SchemaInfo(
                name=PUBLIC_SIGNATURE_CUSTODY_SCAN_SCHEMA_NAME,
                version=_SCHEMA_VERSION,
            ),
            inputs=_scan_inputs(scan),
        ),
        canon_spec=_CANON,
    )
    raw = store.get_bytes(ref.artifact_id)
    report = store.verify(ref.artifact_id)
    manifest = store.get_manifest(ref.artifact_id)
    persisted = PublishedSignatureCustodyScan.model_validate(from_canonical_bytes(raw))
    if (
        not report.ok
        or persisted != scan
        or manifest.artifact_id != ref.artifact_id
        or manifest.kind != PUBLIC_SIGNATURE_CUSTODY_SCAN_KIND
        or manifest.media_type != "application/json"
        or manifest.artifact_schema
        != core_artifacts.SchemaInfo(
            name=PUBLIC_SIGNATURE_CUSTODY_SCAN_SCHEMA_NAME,
            version=_SCHEMA_VERSION,
        )
        or manifest.canon != core_artifacts.CanonInfo.from_spec(_CANON)
        or manifest.inputs != _scan_inputs(scan)
        or to_canonical_bytes(persisted, _CANON) != raw
    ):
        raise ValueError("published_signature_custody_scan_readback_mismatch")
    return PersistedPublishedSignatureCustodyScan(
        scan_receipt_ref=ref,
        scan_receipt_content_hash="sha256:" + hashlib.sha256(raw).hexdigest(),
        scan=persisted,
    )


class PublishedSignatureCustodyWatcher:
    """Recompute public-signature staleness and send only advisory lifecycle signals."""

    def __init__(
        self,
        *,
        store: core_artifacts.ArtifactStore,
        population_provider: PublicSignaturePopulationProvider | None = None,
        lifecycle_publisher: PublishedSignatureCustodyLifecyclePublisher,
    ) -> None:
        self._store = store
        self._population_provider = population_provider or UnappointedPublicSignaturePopulationProvider()
        self._lifecycle_publisher = lifecycle_publisher

    def scan_once(self, *, now: datetime | None = None) -> PublishedSignatureCustodyResult:
        """Run one fail-closed scan; a missing population remains a persisted nonreceipt."""

        scanned_at = now or datetime.now(UTC)
        population = self._population_provider.resolve()
        if isinstance(population, PublicSignaturePopulationNonReceipt):
            persisted = persist_published_signature_custody_scan(
                self._store,
                PublishedSignatureCustodyScan(
                    status="not_established",
                    scanned_at=scanned_at,
                    predicate_provenance="not_established",
                    member_count=0,
                    reason=population.reason,
                ),
            )
            return PublishedSignatureCustodyResult(
                status="not_established",
                predicate_provenance="not_established",
                scan_receipt_ref=persisted.scan_receipt_ref,
                reason=population.reason,
            )

        try:
            population = resolve_public_signature_population(
                self._store,
                population.population_ref,
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            persisted = persist_published_signature_custody_scan(
                self._store,
                PublishedSignatureCustodyScan(
                    status="blocked",
                    scanned_at=scanned_at,
                    predicate_provenance="not_established",
                    member_count=0,
                    reason=f"public_signature_population_unresolvable:{type(exc).__name__}",
                ),
            )
            return PublishedSignatureCustodyResult(
                status="blocked",
                predicate_provenance="not_established",
                scan_receipt_ref=persisted.scan_receipt_ref,
                reason=persisted.scan.reason,
            )

        monitor_refs: list[core_artifacts.ArtifactRef] = []
        lifecycle_refs: list[core_artifacts.ArtifactRef] = []
        try:
            for member in population.snapshot.members:
                _assert_exact_artifact(self._store, member.signature_ref)
                _assert_exact_artifact(self._store, member.decision_packet_ref)
                if scanned_at < member.published_at + timedelta(
                    seconds=member.staleness_after_seconds
                ):
                    continue
                persisted_event = persist_governance_monitor_event(
                    self._store,
                    GovernanceMonitorEvent(
                        event_id=monitor_event_id(
                            decision_packet_ref=member.decision_packet_ref,
                            event_type="policy_context_drift",
                            reason="published_signature_custody_stale",
                            sequence=len(monitor_refs),
                        ),
                        decision_packet_ref=member.decision_packet_ref,
                        event_type="policy_context_drift",
                        severity="warning",
                        scope={"custody_subject": "published_signature"},
                        affected_claim_ids=list(member.affected_claim_ids),
                        reason=(
                            "Published signature exceeded its declared custody staleness interval."
                        ),
                        occurred_at=scanned_at,
                        advisory_posture="review_required",
                        metadata={
                            "published_signature_ref": str(member.signature_ref.artifact_id),
                            "population_provenance": population.snapshot.population_provenance,
                            "published_signature_custody": "advisory",
                        },
                    ),
                )
                monitor_refs.append(persisted_event.event_ref)
                publication = self._lifecycle_publisher(persisted_event.event_ref)
                lifecycle_refs.append(publication.lifecycle_bridge_result_ref)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            scan = PublishedSignatureCustodyScan(
                status="blocked",
                scanned_at=scanned_at,
                predicate_provenance=population.snapshot.population_provenance,
                population_ref=population.population_ref,
                population_content_hash=population.population_content_hash,
                population_provenance=population.snapshot.population_provenance,
                member_count=len(population.snapshot.members),
                monitor_event_refs=tuple(monitor_refs),
                lifecycle_bridge_result_refs=tuple(lifecycle_refs),
                reason=f"published_signature_custody_blocked:{type(exc).__name__}",
            )
        else:
            scan = PublishedSignatureCustodyScan(
                status="watched",
                scanned_at=scanned_at,
                predicate_provenance=population.snapshot.population_provenance,
                population_ref=population.population_ref,
                population_content_hash=population.population_content_hash,
                population_provenance=population.snapshot.population_provenance,
                member_count=len(population.snapshot.members),
                monitor_event_refs=tuple(monitor_refs),
                lifecycle_bridge_result_refs=tuple(lifecycle_refs),
                reason="published_signature_custody_scan_completed",
            )
        persisted = persist_published_signature_custody_scan(self._store, scan)
        return PublishedSignatureCustodyResult(
            status=scan.status,
            predicate_provenance=scan.predicate_provenance,
            population_provenance=scan.population_provenance,
            scan_receipt_ref=persisted.scan_receipt_ref,
            monitor_event_refs=scan.monitor_event_refs,
            lifecycle_bridge_result_refs=scan.lifecycle_bridge_result_refs,
            reason=scan.reason,
        )


__all__ = [
    "PersistedPublicSignaturePopulation",
    "PersistedPublishedSignatureCustodyScan",
    "PublicSignaturePopulationMember",
    "PublicSignaturePopulationNonReceipt",
    "PublicSignaturePopulationProvider",
    "PublicSignaturePopulationSnapshot",
    "PublishedSignatureCustodyResult",
    "PublishedSignatureCustodyScan",
    "PublishedSignatureCustodyWatcher",
    "StaticPublicSignaturePopulationProvider",
    "UnappointedPublicSignaturePopulationProvider",
    "persist_public_signature_population",
    "persist_published_signature_custody_scan",
    "resolve_public_signature_population",
]
