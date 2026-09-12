"""Canonical admission and historical verification of exact owner PUBLIC records.

The finite profile is total over a raw typed Claim ledger. It permits only
injective relocation of typed identifiers and references, never prose editing.
Unknown metadata and identifiers embedded in material text are bounded refusals.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import AwareDatetime, BaseModel, JsonValue

from polisyos.core import artifacts, canon
from polisyos.scientist.evidence.claims.audit import _load_append_only_claim_ledger
from polisyos.scientist.evidence.claims.export import ClaimExportAudience
from polisyos.scientist.evidence.claims.head_index import (
    ClaimLedgerOwnerPort,
    PacketBoundClaimLedgerSnapshot,
)
from polisyos.scientist.evidence.claims.lifecycle import (
    AppendOnlyClaimLedger,
    ClaimLifecycleAction,
    ClaimLifecycleEvent,
)
from polisyos.scientist.evidence.claims.models import ClaimRecord, MethodNeedPrecondition
from polisyos.scientist.governance.continuous.governed_public_record_contracts import (
    MANDATE_PURPOSE,
    PUBLICATION_PROFILE,
    PUBLICATION_PURPOSE,
    PUBLICATION_RULE,
    GovernedPublicCustodyBinding,
    GovernedPublicRecord,
    GovernedPublicRecordBoundaryRead,
    GovernedPublicRecordDimensions,
    GovernedPublicRecordDraft,
    GovernedPublicRecordError,
    GovernedPublicRecordVerificationResponse,
    PublicationMandateStatement,
    PublicationSigningSlot,
    PublicationTrustedKey,
    _StrictModel,
)

GovernedPublicRecordProjection = GovernedPublicRecord
_T = TypeVar("_T", bound=BaseModel)
_ID = re.compile(r"^gpr_[A-Za-z0-9_-]{32}$")
_USES = ["bounded_public_custody"]
_DENIED = [
    "policy_performance",
    "current_policy_authority",
    "complete_public_history",
    "first_publication",
]
_LIMITATIONS = [
    "Exact assertions and statuses from the initial immutable owner-admitted root snapshot; transition heads are unsupported by this publication profile.",
    "No independent policy-performance claim.",
    "Publication time dates this issuance; historical or live snapshot selection and pending-event cutoff are not established.",
    "gph_ opaque reference handles preserve relations and JSON types; they are not CAS addresses or evidence retrieval URLs.",
    "Public evidence obtainability is not established.",
    "No claim of complete public history, first publication, current authority or indefinite durability.",
    "Disclosure proof covers this exact source tree and public proof metadata, not external side channels.",
]

# Every model field must be classified. New fields fail closed until the finite
# profile is extended; the verifier walks actual objects, including every value.
_REFERENCE_FIELDS: dict[type[BaseModel], frozenset[str]] = {
    artifacts.ArtifactRef: frozenset({"artifact_id"}),
    AppendOnlyClaimLedger: frozenset({"run_id", "base_ledger_ref"}),
    ClaimRecord: frozenset(
        {
            "claim_id",
            "run_id",
            "facet_refs",
            "obligation_refs",
            "concept_spine_refs",
            "authority_profile_refs",
            "baseline_refs",
            "alternative_refs",
            "comparison_refs",
            "evidence_refs",
            "counterevidence_refs",
            "uncertainty_profile_ref",
            "provenance_ref",
            "reviewer_refs",
        }
    ),
    MethodNeedPrecondition: frozenset(
        {"precondition_id", "claim_id", "facet_refs", "obligation_refs"}
    ),
    ClaimLifecycleEvent: frozenset(
        {
            "event_id",
            "claim_id",
            "run_id",
            "actor_id",
            "previous_claim_ref",
            "next_claim_ref",
            "evidence_refs",
            "reviewer_refs",
        }
    ),
}
_MATERIAL_FIELDS: dict[type[BaseModel], frozenset[str]] = {
    artifacts.ArtifactRef: frozenset({"kind", "media_type"}),
    AppendOnlyClaimLedger: frozenset(
        {
            "schema_version",
            "current_claims",
            "events",
            "retention_policy",
            "metadata",
        }
    ),
    ClaimRecord: frozenset(
        {
            "schema_version",
            "claim_type",
            "claim_family",
            "claim_use",
            "text",
            "normalized_subject",
            "support_status",
            "publishability",
            "readiness_level",
            "method_need_preconditions",
            "decomposition_source_class",
            "source_attribution",
            "blocked_reasons",
            "metadata",
        }
    ),
    MethodNeedPrecondition: frozenset(
        {
            "claim_type",
            "method_need",
            "reason",
            "source",
            "metadata",
        }
    ),
    ClaimLifecycleEvent: frozenset(
        {"schema_version", "action", "occurred_at", "reason", "metadata"}
    ),
}


def _bytes(value: BaseModel | dict[str, object] | dict[str, JsonValue]) -> bytes:
    data = (
        value.model_dump(mode="json", exclude_none=False) if isinstance(value, BaseModel) else value
    )
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def _digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def publication_trust_epoch(
    issuer_id: str,
    publisher_trusted_keys: tuple[PublicationTrustedKey, ...],
    mandate_trusted_keys: tuple[PublicationTrustedKey, ...],
) -> str:
    """Recompute the trust-policy epoch independently of its authorization subject."""
    rows = [
        {
            "role": role,
            "public_key_pem_hex": key.public_key_pem.hex(),
            "issuer_id": key.issuer_id,
            "purposes": sorted(key.purposes),
            "revoked": key.revoked,
        }
        for role, keys in (("publisher", publisher_trusted_keys), ("mandate", mandate_trusted_keys))
        for key in keys
    ]
    rows.sort(key=lambda row: json.dumps(row, sort_keys=True))
    return _digest(_bytes({"issuer_id": issuer_id, "keys": rows}))


class _PrivateDraft(_StrictModel):
    snapshot: PacketBoundClaimLedgerSnapshot
    prepared_at: AwareDatetime
    original_decision_id: str
    relocation: dict[str, str]
    public_document: dict[str, JsonValue]
    public_document_digest: str


class _ExactSignature(_StrictModel):
    artifact_ref: artifacts.ArtifactRef
    manifest_ref: artifacts.ArtifactRef
    signature_ref: artifacts.ArtifactRef


class _PrivateAdmission(_StrictModel):
    schema_version: Literal["polisyos.governed_public_admission.v1"] = (
        "polisyos.governed_public_admission.v1"
    )
    record_id: str
    issuer_id: str
    signing_key_id: str
    purpose: Literal["governed_public_record"] = PUBLICATION_PURPOSE
    draft_ref: artifacts.ArtifactRef
    publication: _ExactSignature
    mandate: _ExactSignature
    verifier_epoch: str
    published_at: AwareDatetime


class _IssuanceIndex(_StrictModel):
    record_id: str
    admission: _ExactSignature


def _metadata(value: BaseModel) -> None:
    metadata = getattr(value, "metadata", {})
    if isinstance(value, AppendOnlyClaimLedger):
        if metadata and (
            set(metadata) != {"base_schema_version", "created_by_node_id"}
            or metadata["base_schema_version"] != "1.0"
            or (
                metadata["created_by_node_id"] is not None
                and type(metadata["created_by_node_id"]) is not str
            )
        ):
            raise GovernedPublicRecordError("source_metadata_profile_unsupported")
        if value.retention_policy and (
            set(value.retention_policy) != {"max_events"}
            or type(value.retention_policy["max_events"]) is not int
            or value.retention_policy["max_events"] <= 0
        ):
            raise GovernedPublicRecordError("source_retention_profile_unsupported")
    elif isinstance(value, ClaimLifecycleEvent) and metadata:
        fields = {"claim_type", "support_status", "publishability", "readiness_level"}
        if value.action is not ClaimLifecycleAction.CREATED or set(metadata) != fields:
            raise GovernedPublicRecordError("source_metadata_profile_unsupported")
        if not all(type(item) is str for item in metadata.values()):
            raise GovernedPublicRecordError("source_metadata_profile_unsupported")
    elif metadata:
        raise GovernedPublicRecordError("source_metadata_profile_unsupported")


def _source_leaves(
    value: BaseModel,
) -> tuple[dict[tuple[str | int, ...], str], dict[str, JsonValue]]:
    leaves: dict[tuple[str | int, ...], str] = {}

    def walk(node: object, path: tuple[str | int, ...], reference: bool = False) -> None:
        if isinstance(node, artifacts.ArtifactID):
            if not reference:
                raise GovernedPublicRecordError("source_schema_profile_unsupported")
            leaves[path] = str(node)
        elif isinstance(node, BaseModel):
            cls = type(node)
            if cls not in _REFERENCE_FIELDS or set(cls.model_fields) != (
                _REFERENCE_FIELDS[cls] | _MATERIAL_FIELDS[cls]
            ):
                raise GovernedPublicRecordError("source_schema_profile_unsupported")
            _metadata(node)
            for field in cls.model_fields:
                walk(getattr(node, field), (*path, field), field in _REFERENCE_FIELDS[cls])
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, (*path, index), reference)
        elif reference and node is not None:
            leaves[path] = str(node)

    walk(value, ())
    if (
        isinstance(value, AppendOnlyClaimLedger)
        and value.metadata.get("created_by_node_id") is not None
    ):
        leaves[("metadata", "created_by_node_id")] = value.metadata["created_by_node_id"]
    # Preserve the actual owner's raw JSON codec, including tagged timestamps,
    # omitted optional fields and dictionary membership. No lossy DTO dump.
    return leaves, json.loads(canon.to_canonical_bytes(value, canon.CanonSpec(forbid_floats=False)))


def _project(
    ledger: AppendOnlyClaimLedger,
    *,
    mapping: dict[str, str] | None = None,
) -> tuple[dict[str, JsonValue], dict[str, str]]:
    leaves, raw = _source_leaves(ledger)
    originals = set(leaves.values())
    if mapping is None:
        mapping = {value: "gph_" + secrets.token_urlsafe(24) for value in sorted(originals)}
    if set(mapping) != originals or len(set(mapping.values())) != len(mapping):
        raise GovernedPublicRecordError("projection_relocation_invalid")
    for original, public in mapping.items():
        pattern = r"gph_[A-Za-z0-9_-]{32}"
        if re.fullmatch(pattern, public) is None or public in originals:
            raise GovernedPublicRecordError("projection_relocation_invalid")

    def transform(node: JsonValue, path: tuple[str | int, ...]) -> JsonValue:
        if path in leaves:
            return mapping[leaves[path]]
        if isinstance(node, dict):
            return {key: transform(child, (*path, key)) for key, child in node.items()}
        if isinstance(node, list):
            return [transform(child, (*path, index)) for index, child in enumerate(node)]
        if isinstance(node, str) and any(value and value in node for value in originals):
            raise GovernedPublicRecordError("source_reference_embedded_in_material")
        return node

    relocated = transform(raw, ())
    # The source model validates private references. The public encoding uses
    # handles, not pretend content hashes; the injective total transform retains
    # all field identities, membership, JSON types, relations and ordering.
    document: dict[str, JsonValue] = {
        "schema_version": "polisyos.governed_public_document.v1",
        "profile": PUBLICATION_PROFILE,
        "ledger": relocated,
        "permitted_uses": list(_USES),
        "denied_uses": list(_DENIED),
        "limitations": list(_LIMITATIONS),
    }
    return document, mapping


class GovernedPublicRecordOwner:
    """Single source intake and issuance emission boundary for governed PUBLIC."""

    def __init__(
        self,
        *,
        store: artifacts.FileSystemCAS,
        claim_owner: ClaimLedgerOwnerPort,
        index_root: Path,
        slot: PublicationSigningSlot,
    ) -> None:
        self.store = store
        self.claim_owner = claim_owner
        self.index_root = Path(index_root)
        self.slot = slot
        self.last_boundary_reads: tuple[GovernedPublicRecordBoundaryRead, ...] = ()
        self._publisher_verifier, self._publisher_keys = self._trust(slot.publisher_trusted_keys)
        self._mandate_verifier, self._mandate_keys = self._trust(slot.mandate_trusted_keys)

    @staticmethod
    def _trust(
        keys: tuple[PublicationTrustedKey, ...],
    ) -> tuple[artifacts.Ed25519Verifier, dict[str, PublicationTrustedKey]]:
        verifier = artifacts.Ed25519Verifier(strict_identity=False)
        rows: dict[str, PublicationTrustedKey] = {}
        for row in keys:
            key_id = verifier.load_trusted_key_pem(row.public_key_pem, identity=row.issuer_id)
            if key_id in rows:
                raise ValueError("publication_duplicate_trust_key")
            rows[key_id] = row
        return verifier, rows

    def _put(self, value: BaseModel | dict[str, object], name: str) -> artifacts.ArtifactRef:
        return self.store.put_bytes(
            _bytes(value),
            artifacts.ArtifactWriteOptions(
                kind=name,
                media_type="application/json",
                schema=artifacts.SchemaInfo(name=name, version="1"),
            ),
        )

    def _read(self, ref: artifacts.ArtifactRef, cls: type[_T], name: str) -> _T:
        self._raw(ref)
        manifest = self.store.get_manifest(ref.artifact_id)
        if (
            manifest.kind != name
            or ref.kind != name
            or ref.media_type != "application/json"
            or manifest.artifact_schema != artifacts.SchemaInfo(name=name, version="1")
        ):
            raise GovernedPublicRecordError("record_schema_invalid")
        raw = self.store.get_bytes(ref.artifact_id)
        result = cls.model_validate_json(raw)
        if _bytes(result) != raw:
            raise GovernedPublicRecordError("record_canonical_bytes_invalid")
        return result

    def _raw(self, ref: artifacts.ArtifactRef) -> bytes:
        try:
            result = self.store.verify(ref.artifact_id)
            raw = self.store.get_bytes(ref.artifact_id)
            manifest = self.store.get_manifest(ref.artifact_id)
            if (
                not result.ok
                or _digest(raw) != str(ref.artifact_id)
                or manifest.artifact_id != ref.artifact_id
                or manifest.kind != ref.kind
                or manifest.media_type != ref.media_type
            ):
                raise ValueError("CAS binding invalid")
            return raw
        except (OSError, ValueError, KeyError) as exc:
            raise GovernedPublicRecordError(
                "record_evidence_unavailable",
                reads=(
                    GovernedPublicRecordBoundaryRead(
                        operation="cas.verify_and_get_bytes",
                        selector=str(ref.artifact_id),
                        outcome="invalid",
                    ),
                ),
            ) from exc

    def _capture(self, ref: artifacts.ArtifactRef) -> _ExactSignature:
        self._raw(ref)
        blob_path, _ = self.store.get_paths(ref.artifact_id)
        signature = blob_path.with_suffix(".sig").read_bytes()
        return _ExactSignature(
            artifact_ref=ref,
            manifest_ref=self.store.put_bytes(
                self.store.get_manifest_bytes(ref.artifact_id),
                artifacts.ArtifactWriteOptions(
                    kind="scientist.publication.exact_manifest", media_type="application/json"
                ),
            ),
            signature_ref=self.store.put_bytes(
                signature,
                artifacts.ArtifactWriteOptions(
                    kind="scientist.publication.exact_signature", media_type="application/json"
                ),
            ),
        )

    def _signed(
        self,
        evidence: _ExactSignature,
        cls: type[_T],
        name: str,
        *,
        mandate: bool = False,
        historical: bool = False,
    ) -> tuple[_T, PublicationTrustedKey]:
        value = self._read(evidence.artifact_ref, cls, name)
        raw = self._raw(evidence.artifact_ref)
        manifest = self._raw(evidence.manifest_ref)
        sig_raw = self._raw(evidence.signature_ref)
        blob_path, _ = self.store.get_paths(evidence.artifact_ref.artifact_id)
        if (
            manifest != self.store.get_manifest_bytes(evidence.artifact_ref.artifact_id)
            or sig_raw != blob_path.with_suffix(".sig").read_bytes()
        ):
            raise GovernedPublicRecordError("record_exact_signature_evidence_changed")
        signature = artifacts.DetachedSignature.model_validate_json(sig_raw)
        verifier = self._mandate_verifier if mandate else self._publisher_verifier
        keys = self._mandate_keys if mandate else self._publisher_keys
        row = keys.get(signature.key_id)
        if row is None:
            raise GovernedPublicRecordError("record_key_untrusted")
        issuer_field, key_field = (
            ("authority_issuer_id", "authority_key_id")
            if mandate
            else ("issuer_id", "signing_key_id")
        )
        purpose = MANDATE_PURPOSE if mandate else PUBLICATION_PURPOSE
        if (
            getattr(value, issuer_field) != row.issuer_id
            or getattr(value, key_field) != signature.key_id
            or value.purpose != purpose
            or purpose not in row.purposes
        ):
            raise GovernedPublicRecordError("record_issuer_purpose_untrusted")
        if not verifier.verify(
            evidence.artifact_ref.artifact_id, raw, manifest, signature, strict_identity=False
        ).ok:
            raise GovernedPublicRecordError("record_signature_invalid")
        if row.revoked and not historical:
            raise GovernedPublicRecordError("record_key_revoked")
        return value, row

    @staticmethod
    def _atomic_new(path: Path, raw: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            temporary.unlink(missing_ok=True)

    def prepare(
        self,
        *,
        decision_id: str,
        decision_packet_ref: artifacts.ArtifactRef,
        issued_at: datetime,
    ) -> GovernedPublicRecordDraft:
        """Persist a private exact candidate; never write a public issuance index."""
        try:
            return self._prepare(
                decision_id=decision_id,
                decision_packet_ref=decision_packet_ref,
                issued_at=issued_at,
            )
        except GovernedPublicRecordError:
            raise
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise GovernedPublicRecordError(
                "publication_preparation_invalid", reads=self.last_boundary_reads
            ) from exc

    def _prepare(
        self,
        *,
        decision_id: str,
        decision_packet_ref: artifacts.ArtifactRef,
        issued_at: datetime,
    ) -> GovernedPublicRecordDraft:
        if issued_at.tzinfo is None:
            raise GovernedPublicRecordError("publication_time_invalid")
        snapshot = self.claim_owner.resolve_current_for_packet(
            decision_packet_ref=decision_packet_ref
        )
        self.last_boundary_reads = (
            GovernedPublicRecordBoundaryRead(
                operation="claim_owner.resolve_current_for_packet",
                selector=str(decision_packet_ref.artifact_id),
                outcome="read",
            ),
        )
        if type(snapshot) is not PacketBoundClaimLedgerSnapshot:
            raise GovernedPublicRecordError(
                "source_owner_not_admitted",
                reads=(
                    GovernedPublicRecordBoundaryRead(
                        operation="claim_owner.resolve_current_for_packet",
                        selector=str(decision_packet_ref.artifact_id),
                        outcome="unknown",
                    ),
                ),
            )
        if (
            snapshot.ledger.run_id != decision_id
            or snapshot.decision_packet_ref != decision_packet_ref
        ):
            raise GovernedPublicRecordError("source_scope_mismatch")
        self._historical_source(snapshot)
        self._eligible(snapshot)
        key = _digest(
            _bytes(
                {
                    "packet": str(decision_packet_ref.artifact_id),
                    "head": str(snapshot.head.head_ref.artifact_id),
                    "profile": PUBLICATION_PROFILE,
                }
            )
        ).split(":")[1]
        cache_path = self.index_root / "drafts" / (key + ".json")
        if cache_path.exists():
            ref = artifacts.ArtifactRef.model_validate_json(cache_path.read_bytes())
            draft = self._read(ref, _PrivateDraft, "scientist.publication.private_draft")
            if draft.snapshot != snapshot:
                raise GovernedPublicRecordError("source_changed_since_preparation")
        else:
            public_document, relocation = _project(snapshot.ledger)
            draft = _PrivateDraft(
                snapshot=snapshot,
                prepared_at=issued_at,
                original_decision_id=decision_id,
                relocation=relocation,
                public_document=public_document,
                public_document_digest=_digest(_bytes(public_document)),
            )
            ref = self._put(draft, "scientist.publication.private_draft")
            try:
                self._atomic_new(cache_path, _bytes(ref))
            except FileExistsError:
                return self.prepare(
                    decision_id=decision_id,
                    decision_packet_ref=decision_packet_ref,
                    issued_at=issued_at,
                )
        self._validate_draft(draft)
        return GovernedPublicRecordDraft(
            candidate_ref=ref,
            public_document=draft.public_document,
            public_document_digest=draft.public_document_digest,
        )

    @staticmethod
    def _eligible(snapshot: PacketBoundClaimLedgerSnapshot) -> None:
        claims = snapshot.ledger.current_claims
        exported = snapshot.public_export
        if (
            not claims
            or exported.audience is not ClaimExportAudience.PUBLIC
            or [item.claim_id for item in exported.claims] != [item.claim_id for item in claims]
            or any(not item.visible or not item.text.strip() for item in exported.claims)
            or exported.omitted_claim_ids
            or snapshot.current_head_projection.claim_currentness != "current"
            or snapshot.current_head_projection.claim_bridge_pending
        ):
            raise GovernedPublicRecordError("source_not_wholly_public_eligible")

    def _historical_source(self, snapshot: PacketBoundClaimLedgerSnapshot) -> AppendOnlyClaimLedger:
        ledger = self.claim_owner.verify_historical_packet_snapshot(snapshot=snapshot)
        if type(ledger) is not AppendOnlyClaimLedger:
            raise GovernedPublicRecordError(
                "claim_historical_transition_profile_unsupported"
                if ledger.code == "claim_historical_transition_profile_unsupported"
                else "historical_source_admission_not_established",
                reads=(
                    GovernedPublicRecordBoundaryRead(
                        operation="claim_owner.verify_historical_packet_snapshot",
                        selector=str(snapshot.head.head_ref.artifact_id),
                        outcome="invalid",
                    ),
                ),
            )
        return ledger

    def _validate_draft(self, draft: _PrivateDraft) -> None:
        snapshot = draft.snapshot
        ledger = self._historical_source(snapshot)
        if ledger.run_id != draft.original_decision_id or any(
            not claim.text.strip() for claim in ledger.current_claims
        ):
            raise GovernedPublicRecordError("source_scope_or_content_invalid")
        for ref in (
            snapshot.decision_packet_ref,
            snapshot.head.head_ref,
            snapshot.head.statement.root_receipt_ref,
            snapshot.head.statement.issuance_verifier_receipt_ref,
        ):
            self._raw(ref)
        stored_ledger = _load_append_only_claim_ledger(
            self.store, snapshot.head.statement.ledger_artifact_ref
        )
        if ledger != snapshot.ledger or stored_ledger != ledger:
            raise GovernedPublicRecordError("source_ledger_binding_invalid")
        public_document, _ = _project(ledger, mapping=draft.relocation)
        if (
            public_document != draft.public_document
            or _digest(_bytes(public_document)) != draft.public_document_digest
        ):
            raise GovernedPublicRecordError("projection_complete_transform_mismatch")

    def _mandate_binding(
        self,
        mandate: PublicationMandateStatement,
        draft: _PrivateDraft,
        record: GovernedPublicRecord,
    ) -> None:
        snapshot = draft.snapshot
        if (
            mandate.public_document_digest != draft.public_document_digest
            or mandate.decision_packet_ref != snapshot.decision_packet_ref
            or mandate.ledger_artifact_ref != snapshot.head.statement.ledger_artifact_ref
            or mandate.owner_scope_ref != snapshot.head.statement.owner_key.scope_ref
            or mandate.issuer_id != record.issuer_id
            or mandate.signing_key_id != record.signing_key_id
            or not mandate.valid_from <= record.issued_at < mandate.valid_until
            or mandate.issued_at > record.issued_at
            or draft.prepared_at > record.issued_at
        ):
            raise GovernedPublicRecordError("publication_mandate_binding_invalid")

    def issue(
        self,
        *,
        decision_id: str,
        decision_packet_ref: artifacts.ArtifactRef,
        issued_at: datetime,
    ) -> str:
        """Admit source, external mandate and exact publisher signature before indexing."""
        try:
            return self._issue(
                decision_id=decision_id,
                decision_packet_ref=decision_packet_ref,
                issued_at=issued_at,
            )
        except GovernedPublicRecordError:
            raise
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise GovernedPublicRecordError(
                "publication_issuance_invalid", reads=self.last_boundary_reads
            ) from exc

    def _issue(
        self,
        *,
        decision_id: str,
        decision_packet_ref: artifacts.ArtifactRef,
        issued_at: datetime,
    ) -> str:
        candidate = self.prepare(
            decision_id=decision_id, decision_packet_ref=decision_packet_ref, issued_at=issued_at
        )
        slot = self.slot
        if slot.signer is None or slot.issuer_id is None or slot.verifier_epoch is None:
            raise GovernedPublicRecordError("publication_signer_not_configured")
        if slot.mandate_ref is None:
            raise GovernedPublicRecordError("publication_mandate_not_configured")
        if slot.verifier_epoch != publication_trust_epoch(
            slot.issuer_id, slot.publisher_trusted_keys, slot.mandate_trusted_keys
        ):
            raise GovernedPublicRecordError("publication_verifier_epoch_mismatch")
        draft = self._read(
            candidate.candidate_ref, _PrivateDraft, "scientist.publication.private_draft"
        )
        row = self._publisher_keys.get(slot.signer.key_id)
        if (
            row is None
            or row.issuer_id != slot.issuer_id
            or PUBLICATION_PURPOSE not in row.purposes
        ):
            raise GovernedPublicRecordError("record_issuer_purpose_untrusted")
        if row.revoked:
            raise GovernedPublicRecordError("record_key_revoked")
        record = GovernedPublicRecord(
            record_id="gpr_" + secrets.token_urlsafe(24),
            decision_id=draft.relocation[draft.original_decision_id],
            issuer_id=slot.issuer_id,
            signing_key_id=slot.signer.key_id,
            issued_at=issued_at,
            public_document_digest=draft.public_document_digest,
        )
        mandate_evidence = self._capture(slot.mandate_ref)
        mandate, _ = self._signed(
            mandate_evidence,
            PublicationMandateStatement,
            "polisyos.publication_mandate",
            mandate=True,
        )
        self._mandate_binding(mandate, draft, record)
        if mandate.verifier_epoch != slot.verifier_epoch:
            raise GovernedPublicRecordError("publication_verifier_epoch_mismatch")
        # Re-read the actual owner after mandate verification and before signing.
        latest = self.claim_owner.resolve_current_for_packet(
            decision_packet_ref=decision_packet_ref
        )
        if latest != draft.snapshot:
            raise GovernedPublicRecordError("source_changed_during_admission")
        record_ref = self._put(record, "polisyos.governed_public_record")
        self.store.sign_artifact(
            record_ref.artifact_id, slot.signer, signer_identity=slot.issuer_id
        )
        publication = self._capture(record_ref)
        self._signed(publication, GovernedPublicRecord, "polisyos.governed_public_record")
        admission = _PrivateAdmission(
            record_id=record.record_id,
            issuer_id=record.issuer_id,
            signing_key_id=record.signing_key_id,
            draft_ref=candidate.candidate_ref,
            publication=publication,
            mandate=mandate_evidence,
            verifier_epoch=slot.verifier_epoch,
            published_at=record.issued_at,
        )
        admission_ref = self._put(admission, "scientist.publication.private_admission")
        self.store.sign_artifact(
            admission_ref.artifact_id, slot.signer, signer_identity=slot.issuer_id
        )
        index = _IssuanceIndex(record_id=record.record_id, admission=self._capture(admission_ref))
        self._resolve_index(index)
        self._atomic_new(self.index_root / "issued" / (record.record_id + ".json"), _bytes(index))
        return record.record_id

    def _resolve_index(
        self, index: _IssuanceIndex
    ) -> tuple[
        GovernedPublicRecord,
        _PrivateDraft,
        PublicationMandateStatement,
        PublicationTrustedKey,
        _PrivateAdmission,
    ]:
        admission, _ = self._signed(
            index.admission,
            _PrivateAdmission,
            "scientist.publication.private_admission",
            historical=True,
        )
        record, key = self._signed(
            admission.publication,
            GovernedPublicRecord,
            "polisyos.governed_public_record",
            historical=True,
        )
        mandate, _ = self._signed(
            admission.mandate,
            PublicationMandateStatement,
            "polisyos.publication_mandate",
            mandate=True,
            historical=True,
        )
        draft = self._read(
            admission.draft_ref, _PrivateDraft, "scientist.publication.private_draft"
        )
        self._validate_draft(draft)
        self._mandate_binding(mandate, draft, record)
        if (
            index.record_id != admission.record_id
            or index.record_id != record.record_id
            or admission.issuer_id != record.issuer_id
            or admission.signing_key_id != record.signing_key_id
            or admission.published_at != record.issued_at
            or admission.verifier_epoch != mandate.verifier_epoch
            or record.public_document_digest != draft.public_document_digest
            or record.decision_id != draft.relocation[draft.original_decision_id]
        ):
            raise GovernedPublicRecordError("record_private_admission_binding_invalid")
        return record, draft, mandate, key, admission

    def _index(self, record_id: str) -> _IssuanceIndex:
        if _ID.fullmatch(record_id) is None:
            raise GovernedPublicRecordError(
                "client_token_not_server_issued",
                reads=(
                    GovernedPublicRecordBoundaryRead(
                        operation="issued_locator_selection", selector=record_id, outcome="unknown"
                    ),
                ),
            )
        path = self.index_root / "issued" / (record_id + ".json")
        try:
            if path.is_symlink():
                raise GovernedPublicRecordError("issuance_index_invalid")
            result = _IssuanceIndex.model_validate_json(path.read_bytes())
        except FileNotFoundError as exc:
            raise GovernedPublicRecordError(
                "record_not_issued",
                reads=(
                    GovernedPublicRecordBoundaryRead(
                        operation="issued_index.read_bytes", selector=str(path), outcome="absent"
                    ),
                ),
            ) from exc
        if result.record_id != record_id:
            raise GovernedPublicRecordError("issuance_index_invalid")
        return result

    def verify(self, record_id: str) -> GovernedPublicRecordVerificationResponse:
        """Reverify exact historical admission; never promote it to current authority."""
        try:
            record, draft, _, key, _ = self._resolve_index(self._index(record_id))
        except (GovernedPublicRecordError, OSError, ValueError, TypeError, KeyError) as exc:
            code = (
                exc.code
                if isinstance(exc, GovernedPublicRecordError)
                else "record_evidence_invalid"
            )
            self.last_boundary_reads = (
                exc.reads
                if isinstance(exc, GovernedPublicRecordError)
                else (
                    GovernedPublicRecordBoundaryRead(
                        operation="issued_record.resolve", selector=record_id, outcome="invalid"
                    ),
                )
            )
            return GovernedPublicRecordVerificationResponse(
                record_id=record_id,
                report_authentication="not_established"
                if code in {"record_not_issued", "client_token_not_server_issued"}
                else "invalid",
                reason_codes=(code,),
                cryptographic_signature="invalid"
                if code == "record_signature_invalid"
                else "not_established",
                report_key_status="untrusted"
                if code == "record_key_untrusted"
                else "not_established",
            )
        return GovernedPublicRecordVerificationResponse(
            record_id=record_id,
            report_authentication="verified",
            cryptographic_signature="valid",
            report_key_status="revoked" if key.revoked else "trusted",
            decision_id=record.decision_id,
            issuer_id=record.issuer_id,
            issued_at=record.issued_at,
            public_document_digest=record.public_document_digest,
            public_document=draft.public_document,
            promoted_record=record,
            dimensions=GovernedPublicRecordDimensions(
                issuer_issuance="established",
                projection_faithfulness="established",
            ),
        )

    def issued_record_ids(self) -> tuple[str, ...]:
        """List this local owner's issued locators, without global-history claims."""
        directory = self.index_root / "issued"
        try:
            entries = tuple(directory.iterdir())
        except FileNotFoundError:
            self.last_boundary_reads = (
                GovernedPublicRecordBoundaryRead(
                    operation="issued_index.iterdir", selector=str(directory), outcome="absent"
                ),
            )
            return ()
        reads = [
            GovernedPublicRecordBoundaryRead(
                operation="issued_index.iterdir", selector=str(directory), outcome="read"
            )
        ]
        record_ids = []
        for path in entries:
            if path.suffix != ".json":
                reads.append(
                    GovernedPublicRecordBoundaryRead(
                        operation="issued_index.extension_selector",
                        selector=str(path),
                        outcome="unknown",
                        unresolved_by_construction=(
                            "unselected_index_extensions",
                            "other_owner_stores",
                            "unregistered_external_publications",
                        ),
                    )
                )
                continue
            try:
                if path.is_symlink() or not path.is_file() or _ID.fullmatch(path.stem) is None:
                    raise ValueError("invalid controlled index member")
                self._index(path.stem)
                reads.append(
                    GovernedPublicRecordBoundaryRead(
                        operation="issued_index.read_bytes",
                        selector=str(path),
                        outcome="read",
                    )
                )
            except (OSError, ValueError, GovernedPublicRecordError) as exc:
                reads.append(
                    GovernedPublicRecordBoundaryRead(
                        operation="issued_index.read_bytes", selector=str(path), outcome="invalid"
                    )
                )
                self.last_boundary_reads = tuple(reads)
                raise GovernedPublicRecordError(
                    "issuance_index_invalid", reads=tuple(reads)
                ) from exc
            record_ids.append(path.stem)
        self.last_boundary_reads = tuple(reads)
        return tuple(sorted(record_ids))

    def resolve_custody_binding(self, record_id: str) -> GovernedPublicCustodyBinding:
        """Resolve a historical admitted signature for the private custody bridge."""
        try:
            record, draft, mandate, _, admission = self._resolve_index(self._index(record_id))
        except GovernedPublicRecordError:
            raise
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise GovernedPublicRecordError(
                "record_evidence_invalid",
                reads=(
                    GovernedPublicRecordBoundaryRead(
                        operation="issued_record.resolve", selector=record_id, outcome="invalid"
                    ),
                ),
            ) from exc
        return GovernedPublicCustodyBinding(
            record_id=record_id,
            signature_ref=admission.publication.artifact_ref,
            decision_packet_ref=draft.snapshot.decision_packet_ref,
            affected_claim_ids=tuple(
                claim.claim_id for claim in draft.snapshot.ledger.current_claims
            ),
            published_at=record.issued_at,
            staleness_after_seconds=mandate.staleness_after_seconds,
        )


__all__ = [
    "GovernedPublicCustodyBinding",
    "GovernedPublicRecord",
    "GovernedPublicRecordDraft",
    "GovernedPublicRecordError",
    "GovernedPublicRecordOwner",
    "GovernedPublicRecordProjection",
    "GovernedPublicRecordVerificationResponse",
    "PublicationMandateStatement",
    "PublicationSigningSlot",
    "PublicationTrustedKey",
    "publication_trust_epoch",
]
