"""Persist and reload policy-free chronology proofs without owning native history."""

from __future__ import annotations

import json
import os
import threading
import weakref
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, NoReturn

from pydantic import BaseModel, ConfigDict

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactManifest,
    ArtifactRef,
    ArtifactStore,
    ArtifactWriteOptions,
    CanonInfo,
    InputRef,
    IntegrityInfo,
    SchemaInfo,
)
from polisyos.core.canon import content_hash
from polisyos.core.contracts import chronology as contract
from polisyos.core.security.full_prefix import FullPrefixVerifier

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

_BUNDLE_KIND = "core.chronology.full_prefix.bundle"
_RESULT_KIND = "core.chronology.full_prefix.verification_result"
_MEDIA_TYPE = "application/octet-stream"
_BUNDLE_SCHEMA = SchemaInfo(
    name="polisyos.chronology.FullPrefixBundle",
    version="1",
)
_RESULT_SCHEMA = SchemaInfo(
    name="polisyos.chronology.FullPrefixVerificationResult",
    version="1",
)
_CANON = CanonInfo.from_spec(contract.CHRONOLOGY_CANON_SPEC)


class _ChronologyProofModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ChronologyProofArtifactNotEstablished(_ChronologyProofModel):
    """Query-bound absence of readable proof artifact evidence."""

    status: Literal["not_established"]
    code: Literal["chronology_proof_artifact_not_established"]
    query: contract.NativeChronologyQuery
    bundle_ref: ArtifactRef


def _raw_cas_hash(payload: bytes) -> contract.Digest:
    return f"sha256:{content_hash(payload)}"


def _hash_mapping(mapping: dict[str, object]) -> contract.Digest:
    raw = contract._canonical_raw_bytes(mapping)
    return contract._sha256_digest(contract._frame_record(raw))


def _manifest_content_hash(manifest: ArtifactManifest) -> contract.Digest:
    return _hash_mapping(manifest.model_dump(mode="json", by_alias=True))


def _report_content_hash(report: object) -> contract.Digest:
    model_dump = getattr(report, "model_dump", None)
    if callable(model_dump):
        raw = model_dump(mode="json")
    else:
        raw = {"report_type": type(report).__name__}
    if not isinstance(raw, dict):
        raw = {"report": raw}
    return _hash_mapping(raw)


def _expected_ref(*, payload: bytes, kind: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex(content_hash(payload)),
        kind=kind,
        media_type=_MEDIA_TYPE,
    )


def _expected_manifest(
    *,
    payload: bytes,
    ref: ArtifactRef,
    schema: SchemaInfo,
    inputs: list[InputRef],
    created_at: datetime,
) -> ArtifactManifest:
    return ArtifactManifest(
        artifact_id=ref.artifact_id,
        kind=ref.kind,
        media_type=ref.media_type,
        byte_size=len(payload),
        created_at=created_at,
        schema=schema,
        canon=_CANON,
        inputs=inputs,
        integrity=IntegrityInfo(sha256=ref.artifact_id.hex),
    )


def _manifest_mismatch(
    *,
    query: contract.NativeChronologyQuery,
    artifact_role: Literal["bundle", "verification_result"],
    artifact_ref: ArtifactRef,
    expected: ArtifactManifest,
    observed: ArtifactManifest,
) -> contract.ChronologyPersistenceManifestMismatch:
    return contract.ChronologyPersistenceManifestMismatch(
        failure_kind="manifest_mismatch",
        disposition="rejected",
        query=query,
        artifact_role=artifact_role,
        artifact_ref=artifact_ref,
        expected_manifest_content_hash=_manifest_content_hash(expected),
        observed_manifest_content_hash=_manifest_content_hash(observed),
    )


def _store_integrity_mismatch(
    *,
    query: contract.NativeChronologyQuery,
    artifact_role: Literal["bundle", "verification_result"],
    artifact_ref: ArtifactRef,
    expected_raw_hash: contract.Digest,
    observed_raw_hash: contract.Digest,
    report: object,
) -> contract.ChronologyPersistenceStoreIntegrityMismatch:
    return contract.ChronologyPersistenceStoreIntegrityMismatch(
        failure_kind="store_integrity_mismatch",
        disposition="rejected",
        query=query,
        artifact_role=artifact_role,
        artifact_ref=artifact_ref,
        expected_raw_cas_hash=expected_raw_hash,
        observed_raw_cas_hash=observed_raw_hash,
        verification_report_content_hash=_report_content_hash(report),
    )


def _not_established(
    *,
    query: contract.NativeChronologyQuery,
    code: Literal[
        "artifact_store_not_established",
        "bundle_write_not_established",
        "verification_result_write_not_established",
        "persistence_process_generation_not_established",
    ],
    evidence_ref: ArtifactRef | None,
) -> contract.ChronologyProofPersistenceFailed:
    return contract.ChronologyProofPersistenceFailed(
        result_kind="persistence_failed",
        failure=contract.ChronologyPersistenceNotEstablished(
            failure_kind="not_established",
            disposition="not_established",
            query=query,
            code=code,
            evidence_ref=evidence_ref,
        ),
    )


class ChronologyProofArtifactReader:
    """Read common bundle bytes and replay the real verifier.

    The reader establishes CAS integrity and commitment verification only. It
    deliberately makes no claim about native lineage, acceptance, currentness,
    completeness, or custody; those require the family owner and consumer.
    """

    def __init__(self, *, store: ArtifactStore) -> None:
        self._store = store

    def load_and_verify(
        self,
        *,
        query: contract.NativeChronologyQuery,
        bundle_ref: ArtifactRef,
        expected_domain: contract.ChronologyProofDomain,
        expected_prefix: contract.ExpectedCommitmentPrefix | None,
        expected_bundle_content_hash: contract.Digest,
    ) -> (
        contract.FullPrefixVerificationResult
        | ChronologyProofArtifactNotEstablished
        | contract.ChronologyPersistenceManifestMismatch
        | contract.ChronologyPersistenceStoreIntegrityMismatch
    ):
        """Reload exact bytes and verify them without trusting a sidecar."""
        try:
            report = self._store.verify(bundle_ref.artifact_id)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return self._missing(query=query, bundle_ref=bundle_ref)
        if not report.ok:
            if report.actual_sha256_hex is None:
                return self._missing(query=query, bundle_ref=bundle_ref)
            return _store_integrity_mismatch(
                query=query,
                artifact_role="bundle",
                artifact_ref=bundle_ref,
                expected_raw_hash=str(bundle_ref.artifact_id),
                observed_raw_hash=f"sha256:{report.actual_sha256_hex}",
                report=report,
            )
        try:
            payload = self._store.get_bytes(bundle_ref.artifact_id)
            manifest = self._store.get_manifest(bundle_ref.artifact_id)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return self._missing(query=query, bundle_ref=bundle_ref)
        observed_raw_hash = _raw_cas_hash(payload)
        if observed_raw_hash != str(bundle_ref.artifact_id):
            return _store_integrity_mismatch(
                query=query,
                artifact_role="bundle",
                artifact_ref=bundle_ref,
                expected_raw_hash=str(bundle_ref.artifact_id),
                observed_raw_hash=observed_raw_hash,
                report=report,
            )
        expected_manifest = _expected_manifest(
            payload=payload,
            ref=ArtifactRef(
                artifact_id=bundle_ref.artifact_id,
                kind=_BUNDLE_KIND,
                media_type=_MEDIA_TYPE,
            ),
            schema=_BUNDLE_SCHEMA,
            inputs=list(manifest.inputs),
            created_at=manifest.created_at,
        )
        if manifest != expected_manifest:
            return _manifest_mismatch(
                query=query,
                artifact_role="bundle",
                artifact_ref=bundle_ref,
                expected=expected_manifest,
                observed=manifest,
            )
        return FullPrefixVerifier().verify_bundle(
            payload,
            expected_domain=expected_domain,
            expected_prefix=expected_prefix,
            expected_bundle_content_hash=expected_bundle_content_hash,
        )

    @staticmethod
    def _missing(
        *, query: contract.NativeChronologyQuery, bundle_ref: ArtifactRef
    ) -> ChronologyProofArtifactNotEstablished:
        return ChronologyProofArtifactNotEstablished(
            status="not_established",
            code="chronology_proof_artifact_not_established",
            query=query,
            bundle_ref=bundle_ref,
        )


@dataclass(frozen=True, slots=True)
class _ChronologyProcessGeneration:
    creator_pid: int
    nonce: object


@dataclass(frozen=True, init=False, eq=False, slots=True, weakref_slot=True)
class _QualificationPersistenceContinuation:
    """Fieldless process-local continuation; never importable or serialized."""

    def __reduce_ex__(self, protocol: int) -> NoReturn:
        del protocol
        raise TypeError("chronology persistence continuations cannot be serialized")


@dataclass(frozen=True, slots=True)
class _PersistencePayload:
    query: contract.NativeChronologyQuery
    reconciliation: contract.NativeChronologyReconciliation
    bundle_bytes: bytes
    expected_domain: contract.ChronologyProofDomain
    expected_prefix: contract.ExpectedCommitmentPrefix | None
    expected_bundle_content_hash: contract.Digest


def _payload_fingerprint(payload: _PersistencePayload) -> contract.Digest:
    mapping: dict[str, object] = {
        "query": payload.query.model_dump(mode="json"),
        "reconciliation": payload.reconciliation.model_dump(mode="json"),
        "bundle_raw_cas_hash": _raw_cas_hash(payload.bundle_bytes),
        "bundle_content_hash": contract._bundle_content_hash(payload.bundle_bytes),
        "expected_domain": payload.expected_domain.model_dump(mode="json"),
        "expected_prefix": (
            None
            if payload.expected_prefix is None
            else payload.expected_prefix.model_dump(mode="json")
        ),
        "expected_bundle_content_hash": payload.expected_bundle_content_hash,
    }
    return _hash_mapping(mapping)


class _OwnerSourceArtifactRejectedError(RuntimeError):
    """Present owner source bytes contradicted the qualified receipt."""


@dataclass(frozen=True, slots=True)
class _StoredArtifact:
    ref: ArtifactRef
    payload: bytes
    manifest: ArtifactManifest


@dataclass(slots=True)
class _ContinuationEntry:
    owner: _ChronologyPersistenceOwner
    payload: _PersistencePayload
    fingerprint: contract.Digest
    state: Literal["issued", "borrowed", "spent"] = "issued"


@dataclass(init=False, eq=False, slots=True, weakref_slot=True)
class _ChronologyPersistenceOwner:
    _registry: _ChronologyPersistenceRegistry
    _store: ArtifactStore
    _verifier: FullPrefixVerifier
    _admission_index: contract.PredicatePolicyAdmissionIndex
    _owner_provenance_verifier: contract.PredicatePolicyOwnerProvenanceVerifier
    _generation: _ChronologyProcessGeneration
    _creator_pid: int
    _valid: bool

    def __reduce_ex__(self, protocol: int) -> NoReturn:
        del protocol
        raise TypeError("chronology persistence owners cannot be serialized")

    def persist(
        self,
        *,
        query: contract.NativeChronologyQuery,
        reconciliation: contract.NativeChronologyReconciliation,
        bundle_bytes: bytes,
        expected_domain: contract.ChronologyProofDomain,
        expected_prefix: contract.ExpectedCommitmentPrefix | None,
        expected_bundle_content_hash: contract.Digest,
    ) -> contract.ChronologyProofPersistenceResult:
        """Issue and consume one continuation in the same owner-held frame."""
        if not self._registry._owner_is_current(self):
            return _not_established(
                query=query,
                code="persistence_process_generation_not_established",
                evidence_ref=None,
            )
        payload = _PersistencePayload(
            query=query,
            reconciliation=reconciliation,
            bundle_bytes=bundle_bytes,
            expected_domain=expected_domain,
            expected_prefix=expected_prefix,
            expected_bundle_content_hash=expected_bundle_content_hash,
        )
        continuation = self._registry._issue(self, payload)
        return self._registry._consume(continuation)

    def _issue_for_test(
        self,
        *,
        payload: _PersistencePayload,
    ) -> _QualificationPersistenceContinuation:
        return self._registry._issue(self, payload)

    def _load_bound_source(
        self,
        *,
        artifact_ref: ArtifactRef,
        expected_raw_cas_hash: contract.Digest,
    ) -> bytes:
        try:
            report = self._store.verify(artifact_ref.artifact_id)
            if not report.ok:
                raise _OwnerSourceArtifactRejectedError("owner source integrity rejected")
            payload = self._store.get_bytes(artifact_ref.artifact_id)
            manifest = self._store.get_manifest(artifact_ref.artifact_id)
        except _OwnerSourceArtifactRejectedError:
            raise
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise _OwnerSourceArtifactRejectedError("owner source unavailable") from exc
        if (
            _raw_cas_hash(payload) != expected_raw_cas_hash
            or str(artifact_ref.artifact_id) != expected_raw_cas_hash
            or manifest.artifact_id != artifact_ref.artifact_id
            or manifest.kind != artifact_ref.kind
            or manifest.media_type != artifact_ref.media_type
        ):
            raise _OwnerSourceArtifactRejectedError("owner source binding rejected")
        return payload

    def _verify_owner_sources(self, payload: _PersistencePayload) -> None:
        qualified = payload.reconciliation.owner_context.owner_qualified_candidate
        candidate = qualified.candidate
        receipt = qualified.owner_relation_verification
        candidate_member_identities = tuple(
            (
                member.member_ref,
                member.native_artifact_ref,
                member.native_content_hash,
                member.native_schema_profile,
                member.member_admission_basis_ref,
                member.member_admission_context_ref,
            )
            for member in candidate.ordered_members
        )
        receipt_member_identities = tuple(
            (
                identity.member_ref,
                identity.native_artifact_ref,
                identity.native_content_hash,
                identity.native_schema_profile,
                identity.member_admission_basis_ref,
                identity.member_admission_context_ref,
            )
            for identity in receipt.member_identities
        )
        if candidate_member_identities != receipt_member_identities:
            raise _OwnerSourceArtifactRejectedError(
                "candidate member subjects differ from owner receipt"
            )
        if (
            receipt.denominator_identity.subject_ref != candidate.declared_denominator_ref
            or receipt.denominator_identity.artifact_ref
            != candidate.native_denominator_artifact_ref
            or receipt.denominator_identity.semantic_content_hash
            != candidate.native_denominator_content_hash
            or receipt.query_context_identity.subject_ref
            != candidate.query.requested_query_context_ref
            or receipt.query_context_identity.artifact_ref != candidate.query_context_artifact_ref
            or receipt.query_context_identity.semantic_content_hash
            != candidate.query_context_content_hash
        ):
            raise _OwnerSourceArtifactRejectedError(
                "candidate native subjects differ from owner receipt"
            )
        owner_receipt_bytes = self._load_bound_source(
            artifact_ref=receipt.verification_receipt_ref,
            expected_raw_cas_hash=receipt.verification_receipt_content_hash,
        )
        denominator_bytes = self._load_bound_source(
            artifact_ref=receipt.denominator_identity.artifact_ref,
            expected_raw_cas_hash=receipt.denominator_identity.raw_cas_hash,
        )
        query_bytes = self._load_bound_source(
            artifact_ref=receipt.query_context_identity.artifact_ref,
            expected_raw_cas_hash=receipt.query_context_identity.raw_cas_hash,
        )
        member_bytes = tuple(
            self._load_bound_source(
                artifact_ref=identity.native_artifact_ref,
                expected_raw_cas_hash=str(identity.native_artifact_ref.artifact_id),
            )
            for identity in receipt.member_identities
        )
        if tuple(member.native_bytes for member in candidate.ordered_members) != (member_bytes):
            raise _OwnerSourceArtifactRejectedError(
                "candidate member bytes differ from owner sources"
            )
        if any(
            contract._native_content_hash(source_bytes) != identity.native_content_hash
            for source_bytes, identity in zip(member_bytes, receipt.member_identities, strict=True)
        ):
            raise _OwnerSourceArtifactRejectedError("owner member content hash rejected")
        if not denominator_bytes or not query_bytes or not owner_receipt_bytes:
            raise _OwnerSourceArtifactRejectedError("owner source bytes are empty")

    @staticmethod
    def _verify_bundle_owner_binding(
        *,
        payload: _PersistencePayload,
        verified: contract.FullPrefixVerified,
    ) -> None:
        reconciliation = payload.reconciliation
        candidate = reconciliation.owner_context.owner_qualified_candidate.candidate
        query = reconciliation.owner_context.query
        header = verified.parsed_header
        expected_members = candidate.ordered_members
        if (
            payload.query != query
            or payload.expected_domain != query.domain
            or header.native_schema_profile != reconciliation.authoritative_native_schema_profile
            or header.declared_denominator_ref != candidate.declared_denominator_ref
            or header.requested_cutoff_ref != query.requested_cutoff_ref
            or header.requested_query_context_ref != query.requested_query_context_ref
            or header.member_count != len(expected_members)
        ):
            raise _OwnerSourceArtifactRejectedError(
                "bundle header differs from owner reconciliation"
            )
        rows = _bundle_member_rows(payload.bundle_bytes)
        comparisons = (
            (
                "bundle member order differs from owner receipt",
                tuple(row.get("member_ref") for row in rows),
                tuple(member.member_ref for member in expected_members),
            ),
            (
                "bundle native hashes differ from owner receipt",
                tuple(row.get("member_content_hash") for row in rows),
                tuple(member.native_content_hash for member in expected_members),
            ),
            (
                "bundle admission bases differ from owner receipt",
                tuple(row.get("member_admission_basis_ref") for row in rows),
                tuple(member.member_admission_basis_ref for member in expected_members),
            ),
            (
                "bundle admission contexts differ from owner receipt",
                tuple(row.get("member_admission_context_ref") for row in rows),
                tuple(member.member_admission_context_ref for member in expected_members),
            ),
        )
        for diagnostic, observed, expected in comparisons:
            if observed != expected:
                raise _OwnerSourceArtifactRejectedError(diagnostic)

    @staticmethod
    def _bundle_inputs(payload: _PersistencePayload) -> list[InputRef]:
        owner_context = payload.reconciliation.owner_context
        receipt = owner_context.owner_qualified_candidate.owner_relation_verification
        return [
            InputRef(
                artifact_id=receipt.verification_receipt_ref.artifact_id,
                role="owner_qualification_receipt",
            ),
            InputRef(
                artifact_id=receipt.denominator_identity.artifact_ref.artifact_id,
                role="native_denominator",
            ),
            InputRef(
                artifact_id=receipt.query_context_identity.artifact_ref.artifact_id,
                role="query_context",
            ),
            *(
                InputRef(
                    artifact_id=identity.native_artifact_ref.artifact_id,
                    role="native_member",
                )
                for identity in receipt.member_identities
            ),
        ]

    def _write_and_reload(
        self,
        *,
        query: contract.NativeChronologyQuery,
        artifact_role: Literal["bundle", "verification_result"],
        payload: bytes,
        kind: str,
        schema: SchemaInfo,
        inputs: list[InputRef],
        missing_code: Literal[
            "bundle_write_not_established",
            "verification_result_write_not_established",
        ],
    ) -> (
        _StoredArtifact
        | contract.ChronologyPersistenceManifestMismatch
        | contract.ChronologyPersistenceStoreIntegrityMismatch
        | contract.ChronologyProofPersistenceFailed
    ):
        if not self._registry._owner_is_current(self):
            return _not_established(
                query=query,
                code="persistence_process_generation_not_established",
                evidence_ref=None,
            )
        expected_ref = _expected_ref(payload=payload, kind=kind)
        options = ArtifactWriteOptions(
            kind=kind,
            media_type=_MEDIA_TYPE,
            schema=schema,
            inputs=inputs,
            canon=_CANON,
        )
        try:
            observed_ref = self._store.put_bytes(payload, options)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return _not_established(query=query, code=missing_code, evidence_ref=None)
        if observed_ref != expected_ref:
            return _not_established(
                query=query,
                code=missing_code,
                evidence_ref=observed_ref,
            )
        try:
            observed_manifest = self._store.get_manifest(expected_ref.artifact_id)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return _not_established(
                query=query,
                code=missing_code,
                evidence_ref=expected_ref,
            )
        expected_manifest = _expected_manifest(
            payload=payload,
            ref=expected_ref,
            schema=schema,
            inputs=inputs,
            created_at=observed_manifest.created_at,
        )
        if observed_manifest != expected_manifest:
            return _manifest_mismatch(
                query=query,
                artifact_role=artifact_role,
                artifact_ref=expected_ref,
                expected=expected_manifest,
                observed=observed_manifest,
            )
        try:
            report = self._store.verify(expected_ref.artifact_id)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return _not_established(
                query=query,
                code=missing_code,
                evidence_ref=expected_ref,
            )
        if not report.ok:
            if report.actual_sha256_hex is None:
                return _not_established(
                    query=query,
                    code=missing_code,
                    evidence_ref=expected_ref,
                )
            return _store_integrity_mismatch(
                query=query,
                artifact_role=artifact_role,
                artifact_ref=expected_ref,
                expected_raw_hash=str(expected_ref.artifact_id),
                observed_raw_hash=f"sha256:{report.actual_sha256_hex}",
                report=report,
            )
        try:
            reloaded = self._store.get_bytes(expected_ref.artifact_id)
            reloaded_manifest = self._store.get_manifest(expected_ref.artifact_id)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return _not_established(
                query=query,
                code=missing_code,
                evidence_ref=expected_ref,
            )
        observed_raw_hash = _raw_cas_hash(reloaded)
        if reloaded != payload or observed_raw_hash != str(expected_ref.artifact_id):
            return _store_integrity_mismatch(
                query=query,
                artifact_role=artifact_role,
                artifact_ref=expected_ref,
                expected_raw_hash=str(expected_ref.artifact_id),
                observed_raw_hash=observed_raw_hash,
                report=report,
            )
        if reloaded_manifest != expected_manifest:
            return _manifest_mismatch(
                query=query,
                artifact_role=artifact_role,
                artifact_ref=expected_ref,
                expected=expected_manifest,
                observed=reloaded_manifest,
            )
        return _StoredArtifact(
            ref=expected_ref,
            payload=reloaded,
            manifest=reloaded_manifest,
        )

    def _persist_payload(
        self,
        payload: _PersistencePayload,
    ) -> contract.ChronologyProofPersistenceResult:
        if not self._registry._owner_is_current(self):
            return _not_established(
                query=payload.query,
                code="persistence_process_generation_not_established",
                evidence_ref=None,
            )
        self._revalidate_payload(payload)
        prewrite = self._verifier.verify_bundle(
            payload.bundle_bytes,
            expected_domain=payload.expected_domain,
            expected_prefix=payload.expected_prefix,
            expected_bundle_content_hash=payload.expected_bundle_content_hash,
        )
        if not isinstance(prewrite, contract.FullPrefixVerified):
            return contract.ChronologyProofPersistenceFailed(
                result_kind="persistence_failed",
                failure=contract.ChronologyPersistenceVerificationMismatch(
                    failure_kind="verification_mismatch",
                    disposition="rejected",
                    query=payload.query,
                    proof_result=prewrite,
                ),
            )
        self._verify_bundle_owner_binding(payload=payload, verified=prewrite)
        self._verify_owner_sources(payload)
        bundle = self._write_and_reload(
            query=payload.query,
            artifact_role="bundle",
            payload=payload.bundle_bytes,
            kind=_BUNDLE_KIND,
            schema=_BUNDLE_SCHEMA,
            inputs=self._bundle_inputs(payload),
            missing_code="bundle_write_not_established",
        )
        if not isinstance(bundle, _StoredArtifact):
            return self._wrap_write_failure(bundle)

        postwrite = self._verifier.verify_bundle(
            bundle.payload,
            expected_domain=payload.expected_domain,
            expected_prefix=payload.expected_prefix,
            expected_bundle_content_hash=payload.expected_bundle_content_hash,
        )
        if not isinstance(postwrite, contract.FullPrefixVerified):
            return contract.ChronologyProofPersistenceFailed(
                result_kind="persistence_failed",
                failure=contract.ChronologyPersistenceVerificationMismatch(
                    failure_kind="verification_mismatch",
                    disposition="rejected",
                    query=payload.query,
                    proof_result=postwrite,
                ),
            )
        if postwrite != prewrite:
            raise RuntimeError("real verifier changed result for identical reloaded bytes")
        statement = contract.FullPrefixVerificationStatement(
            schema_version="polisyos.chronology.full-prefix-verification-result.v1",
            bundle_ref=bundle.ref,
            expected_domain=payload.expected_domain,
            expected_prefix=payload.expected_prefix,
            expected_bundle_content_hash=payload.expected_bundle_content_hash,
            result=postwrite,
        )
        statement_raw = contract._canonical_raw_bytes(contract._raw_model_mapping(statement))
        sidecar = self._write_and_reload(
            query=payload.query,
            artifact_role="verification_result",
            payload=contract._frame_record(statement_raw),
            kind=_RESULT_KIND,
            schema=_RESULT_SCHEMA,
            inputs=[InputRef(artifact_id=bundle.ref.artifact_id, role="verified_bundle")],
            missing_code="verification_result_write_not_established",
        )
        if not isinstance(sidecar, _StoredArtifact):
            return self._wrap_write_failure(sidecar)
        sidecar_records = contract._split_framed_records(sidecar.payload)
        if len(sidecar_records) != 1:
            raise RuntimeError("persisted chronology result sidecar has the wrong frame count")
        reparsed = contract.FullPrefixVerificationStatement.model_validate_json(sidecar_records[0])
        if reparsed != statement:
            raise RuntimeError("persisted chronology result sidecar changed after reload")
        return contract.PersistedChronologyProof(
            result_kind="persisted",
            artifact_ref=bundle.ref,
            cas_raw_bytes_hash=str(bundle.ref.artifact_id),
            protocol_bundle_content_hash=contract._bundle_content_hash(bundle.payload),
            parsed_header=postwrite.parsed_header,
            verifier_result_ref=sidecar.ref,
            verifier_result_content_hash=contract._verification_statement_content_hash(reparsed),
            verification_statement=reparsed,
        )

    @staticmethod
    def _revalidate_payload(payload: _PersistencePayload) -> None:
        try:
            query = contract.NativeChronologyQuery.model_validate(
                payload.query.model_dump(mode="python")
            )
            reconciliation = contract.NativeChronologyReconciliation.model_validate(
                payload.reconciliation.model_dump(mode="python")
            )
            expected_domain = contract.ChronologyProofDomain.model_validate(
                payload.expected_domain.model_dump(mode="python")
            )
            expected_prefix = (
                None
                if payload.expected_prefix is None
                else contract.ExpectedCommitmentPrefix.model_validate(
                    payload.expected_prefix.model_dump(mode="python")
                )
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise _OwnerSourceArtifactRejectedError(
                "persistence payload models did not revalidate"
            ) from exc
        if (
            query != payload.query
            or reconciliation != payload.reconciliation
            or expected_domain != payload.expected_domain
            or expected_prefix != payload.expected_prefix
        ):
            raise _OwnerSourceArtifactRejectedError(
                "persistence payload changed during model revalidation"
            )

    @staticmethod
    def _wrap_write_failure(
        failure: (
            contract.ChronologyPersistenceManifestMismatch
            | contract.ChronologyPersistenceStoreIntegrityMismatch
            | contract.ChronologyProofPersistenceFailed
        ),
    ) -> contract.ChronologyProofPersistenceFailed:
        if isinstance(failure, contract.ChronologyProofPersistenceFailed):
            return failure
        return contract.ChronologyProofPersistenceFailed(
            result_kind="persistence_failed",
            failure=failure,
        )


class _ChronologyPersistenceRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._generation = self._new_generation()
        self._store_factory: Callable[[], ArtifactStore] | None = None
        self._verifier_factory: Callable[[], FullPrefixVerifier] | None = None
        self._admission_index_factory: (
            Callable[[], contract.PredicatePolicyAdmissionIndex] | None
        ) = None
        self._owner_provenance_verifier_factory: (
            Callable[[], contract.PredicatePolicyOwnerProvenanceVerifier] | None
        ) = None
        self._owners: weakref.WeakSet[_ChronologyPersistenceOwner] = weakref.WeakSet()
        self._entries: weakref.WeakKeyDictionary[
            _QualificationPersistenceContinuation, _ContinuationEntry
        ] = weakref.WeakKeyDictionary()
        if hasattr(os, "register_at_fork"):
            os.register_at_fork(
                before=self._before_fork,
                after_in_parent=self._after_fork_parent,
                after_in_child=self._after_fork_child,
            )

    @staticmethod
    def _new_generation() -> _ChronologyProcessGeneration:
        return _ChronologyProcessGeneration(creator_pid=os.getpid(), nonce=object())

    def _before_fork(self) -> None:
        self._lock.acquire()

    def _after_fork_parent(self) -> None:
        self._lock.release()

    def _after_fork_child(self) -> None:
        inherited_owners = tuple(self._owners)
        for owner in inherited_owners:
            owner._valid = False
        self._lock = threading.RLock()
        self._generation = self._new_generation()
        self._store_factory = None
        self._verifier_factory = None
        self._admission_index_factory = None
        self._owner_provenance_verifier_factory = None
        self._owners = weakref.WeakSet()
        self._entries = weakref.WeakKeyDictionary()

    def _appoint_for_test(
        self,
        *,
        store_factory: Callable[[], ArtifactStore],
        verifier_factory: Callable[[], FullPrefixVerifier],
        admission_index_factory: Callable[[], contract.PredicatePolicyAdmissionIndex],
        owner_provenance_verifier_factory: Callable[
            [], contract.PredicatePolicyOwnerProvenanceVerifier
        ],
    ) -> _ChronologyProcessGeneration:
        with self._lock:
            if self._entries:
                raise RuntimeError("cannot replace an appointment with live continuations")
            for owner in tuple(self._owners):
                owner._valid = False
            self._owners = weakref.WeakSet()
            self._generation = self._new_generation()
            self._store_factory = store_factory
            self._verifier_factory = verifier_factory
            self._admission_index_factory = admission_index_factory
            self._owner_provenance_verifier_factory = owner_provenance_verifier_factory
            return self._generation

    def _clear_for_test(self) -> None:
        with self._lock:
            for owner in tuple(self._owners):
                owner._valid = False
            self._generation = self._new_generation()
            self._store_factory = None
            self._verifier_factory = None
            self._admission_index_factory = None
            self._owner_provenance_verifier_factory = None
            self._owners = weakref.WeakSet()
            self._entries = weakref.WeakKeyDictionary()

    def _resolve_current_owner(self) -> _ChronologyPersistenceOwner | None:
        with self._lock:
            generation = self._generation
            store_factory = self._store_factory
            verifier_factory = self._verifier_factory
            admission_index_factory = self._admission_index_factory
            owner_provenance_verifier_factory = self._owner_provenance_verifier_factory
        if (
            store_factory is None
            or verifier_factory is None
            or admission_index_factory is None
            or owner_provenance_verifier_factory is None
        ):
            return None
        store = store_factory()
        verifier = verifier_factory()
        admission_index = admission_index_factory()
        owner_provenance_verifier = owner_provenance_verifier_factory()
        if not isinstance(store, ArtifactStore):
            raise TypeError("appointed chronology store does not satisfy ArtifactStore")
        if not isinstance(verifier, FullPrefixVerifier):
            raise TypeError("appointed chronology verifier is not FullPrefixVerifier")
        with self._lock:
            if generation is not self._generation or generation.creator_pid != os.getpid():
                return None
            owner = object.__new__(_ChronologyPersistenceOwner)
            owner._registry = self
            owner._store = store
            owner._verifier = verifier
            owner._admission_index = admission_index
            owner._owner_provenance_verifier = owner_provenance_verifier
            owner._generation = generation
            owner._creator_pid = os.getpid()
            owner._valid = True
            self._owners.add(owner)
            return owner

    def _owner_is_current(self, owner: _ChronologyPersistenceOwner) -> bool:
        with self._lock:
            return (
                owner._valid
                and owner._creator_pid == os.getpid()
                and owner._generation is self._generation
                and owner in self._owners
            )

    def _issue(
        self,
        owner: _ChronologyPersistenceOwner,
        payload: _PersistencePayload,
    ) -> _QualificationPersistenceContinuation:
        with self._lock:
            if not self._owner_is_current(owner):
                raise RuntimeError("chronology persistence owner generation is not current")
            continuation = object.__new__(_QualificationPersistenceContinuation)
            self._entries[continuation] = _ContinuationEntry(
                owner=owner,
                payload=payload,
                fingerprint=_payload_fingerprint(payload),
            )
            return continuation

    def _consume(
        self,
        continuation: _QualificationPersistenceContinuation,
    ) -> contract.ChronologyProofPersistenceResult:
        with self._lock:
            entry = self._entries.get(continuation)
            if entry is None:
                raise RuntimeError("unknown chronology persistence continuation")
            if not self._owner_is_current(entry.owner):
                raise RuntimeError("chronology persistence process generation is not current")
            if entry.state != "issued":
                raise RuntimeError("chronology persistence continuation is not issuable")
            if _payload_fingerprint(entry.payload) != entry.fingerprint:
                raise RuntimeError("chronology persistence payload changed after issue")
            entry.state = "borrowed"
        try:
            return entry.owner._persist_payload(entry.payload)
        finally:
            with self._lock:
                current = self._entries.get(continuation)
                if current is not None:
                    current.state = "spent"

    def _release(self, continuation: _QualificationPersistenceContinuation) -> None:
        with self._lock:
            self._entries.pop(continuation, None)


_PERSISTENCE_REGISTRY = _ChronologyPersistenceRegistry()


def _bundle_member_rows(bundle_bytes: bytes) -> tuple[dict[str, object], ...]:
    records = contract._split_framed_records(bundle_bytes)
    if not records or (len(records) - 1) % 2 != 0:
        raise _OwnerSourceArtifactRejectedError("bundle record denominator rejected")
    rows: list[dict[str, object]] = []
    for offset in range(1, len(records), 2):
        row = json.loads(records[offset])
        if not isinstance(row, dict):
            raise _OwnerSourceArtifactRejectedError("bundle member row is not a mapping")
        rows.append(row)
    return tuple(rows)


__all__ = [
    "ChronologyProofArtifactNotEstablished",
    "ChronologyProofArtifactReader",
]
