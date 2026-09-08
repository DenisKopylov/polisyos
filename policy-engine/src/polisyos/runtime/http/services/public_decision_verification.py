"""Issue and verify retained public-document reports through the existing CAS.

The configured key is authorized only to issue verification reports. Neither
this signature nor a document projection supplies PUBLIC decision issuance or
current authority. Reads verify captured bytes and never re-sign old records.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import TypeAdapter

from polisyos.core import artifacts, canon
from polisyos.runtime.http.services.public_decision_verification_contracts import (
    PUBLIC_VERIFICATION_PURPOSE,
    PUBLIC_VERIFICATION_RECORD_KIND,
    PUBLIC_VERIFICATION_RECORD_SCHEMA,
    PUBLIC_VERIFICATION_RULE_VERSION,
    PublicDecisionJsonValue,
    PublicDecisionVerificationIssuanceIndex,
    PublicDecisionVerificationReason,
    PublicDecisionVerificationRecord,
    PublicDecisionVerificationResponse,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

_RECORD_ID = re.compile(r"pvr_[A-Za-z0-9_-]{32}\Z")
_PUBLIC_DOCUMENT = TypeAdapter(dict[str, PublicDecisionJsonValue])


class PublicDecisionVerificationError(RuntimeError):
    """Typed issuance failure that never returns a publicly addressable record."""

    def __init__(self, code: PublicDecisionVerificationReason) -> None:
        """Bind a stable API reason without exposing storage or key details."""
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PublicDecisionVerificationTrustedKey:
    """Deployment-owned public key binding to one issuer and permitted purposes."""

    public_key_pem: bytes
    issuer_id: str
    purposes: frozenset[str]
    revoked: bool = False

    def __post_init__(self) -> None:
        """Reject malformed policy rather than treating a string as a purpose set."""
        if (
            type(self.public_key_pem) is not bytes
            or not self.public_key_pem
            or type(self.issuer_id) is not str
            or not self.issuer_id.strip()
            or type(self.purposes) is not frozenset
            or any(type(purpose) is not str or not purpose for purpose in self.purposes)
            or type(self.revoked) is not bool
        ):
            raise ValueError("public verification key policy is malformed")


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _digest(payload: bytes) -> str:
    return f"sha256:{canon.content_hash(payload)}"


class PublicDecisionVerificationService:
    """Server-owned issuance index and byte-bound Ed25519 report verification."""

    def __init__(
        self,
        *,
        store: artifacts.FileSystemCAS,
        index_root: Path,
        issuer_id: str,
        signer: artifacts.Ed25519Signer | None,
        trusted_keys: tuple[PublicDecisionVerificationTrustedKey, ...],
        rule_version: str = PUBLIC_VERIFICATION_RULE_VERSION,
    ) -> None:
        """Compose explicit server trust; missing signing material never self-generates."""
        if not issuer_id or not rule_version:
            raise ValueError("verification issuer and rule version must be explicit")
        self._store = store
        self._index_root = index_root
        self._issuer_id = issuer_id
        self._signer = signer
        self._rule_version = rule_version
        self._keys: dict[str, PublicDecisionVerificationTrustedKey] = {}
        # Revocation is intentionally reported separately from mathematical validity.
        # Identity hints in the unsigned sidecar do not decide either dimension.
        self._verifier = artifacts.Ed25519Verifier(strict_identity=False)
        for row in trusted_keys:
            if not row.issuer_id or type(row.revoked) is not bool:
                raise ValueError("public verification key policy is malformed")
            key_id = self._verifier.load_trusted_key_pem(row.public_key_pem, identity=row.issuer_id)
            if key_id in self._keys:
                raise ValueError("public verification key has duplicate trust bindings")
            self._keys[key_id] = row

    def issue(
        self,
        *,
        decision_id: str,
        public_document: Mapping[str, object],
        issued_at: datetime,
    ) -> str:
        """Persist document, signed report and issuance index before returning its ID.

        Raises:
            PublicDecisionVerificationError: If issuer trust, validation, persistence,
                signature readback, or durable index publication fails.
        """
        signer = self._signer
        trust = self._keys.get(signer.key_id) if signer is not None else None
        if (
            signer is None
            or trust is None
            or trust.revoked
            or trust.issuer_id != self._issuer_id
            or PUBLIC_VERIFICATION_PURPOSE not in trust.purposes
        ):
            raise PublicDecisionVerificationError("verification_issuer_not_configured")
        try:
            document = _PUBLIC_DOCUMENT.validate_python(dict(public_document), strict=True)
            document_bytes = _json_bytes(document)
            record = PublicDecisionVerificationRecord(
                record_id=f"pvr_{secrets.token_urlsafe(24)}",
                decision_id=decision_id,
                issuer_id=self._issuer_id,
                signing_key_id=signer.key_id,
                rule_version=self._rule_version,
                issued_at=issued_at,
                public_document_digest=_digest(document_bytes),
            )
        except (TypeError, ValueError) as exc:
            raise PublicDecisionVerificationError("public_document_invalid") from exc
        try:
            document_ref = self._store.put_bytes(
                document_bytes,
                artifacts.ArtifactWriteOptions(
                    kind="runtime.public_decision_verification_document",
                    media_type="application/json",
                ),
            )
            record_ref = self._store.put_bytes(
                _json_bytes(record.model_dump(mode="json")),
                artifacts.ArtifactWriteOptions(
                    kind=PUBLIC_VERIFICATION_RECORD_KIND,
                    media_type="application/json",
                    schema=artifacts.SchemaInfo(
                        name=PUBLIC_VERIFICATION_RECORD_SCHEMA, version="1"
                    ),
                    inputs=[
                        artifacts.InputRef(
                            artifact_id=document_ref.artifact_id, role="public_document"
                        )
                    ],
                ),
            )
            self._store.sign_artifact(record_ref.artifact_id, signer, signer_identity=None)
            entry = PublicDecisionVerificationIssuanceIndex(
                record_id=record.record_id,
                record_artifact_ref=str(record_ref.artifact_id),
                decision_id=decision_id,
                issuer_id=self._issuer_id,
                rule_version=self._rule_version,
                public_document_digest=record.public_document_digest,
            )
        except (OSError, TypeError, ValueError, RuntimeError) as exc:
            raise PublicDecisionVerificationError("record_evidence_unavailable") from exc
        receipt = self._verify_entry(entry)
        if receipt.report_authentication != "verified":
            raise PublicDecisionVerificationError(receipt.reason_codes[0])
        self._publish_index(entry)
        return record.record_id

    def _publish_index(self, entry: PublicDecisionVerificationIssuanceIndex) -> None:
        temporary: Path | None = None
        try:
            self._index_root.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=self._index_root, prefix=".pending-", delete=False
            ) as stream:
                temporary = Path(stream.name)
                stream.write(_json_bytes(entry.model_dump(mode="json")))
                stream.flush()
                os.fsync(stream.fileno())
            # Linking is atomic and fails on collision; an issued ID is never overwritten.
            os.link(temporary, self._index_root / f"{entry.record_id}.json")
            directory = os.open(self._index_root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError as exc:
            raise PublicDecisionVerificationError("issuance_index_write_failed") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def issued_record_ids(self) -> tuple[str, ...]:
        """Enumerate this controlled index, without claiming complete public history."""
        if not self._index_root.exists():
            return ()
        if not self._index_root.is_dir():
            raise PublicDecisionVerificationError("issuance_index_invalid")
        result: list[str] = []
        for path in sorted(self._index_root.glob("*.json")):
            try:
                entry = PublicDecisionVerificationIssuanceIndex.model_validate_json(
                    path.read_bytes()
                )
                if path.is_symlink() or path.stem != entry.record_id:
                    raise ValueError("issued record index identity mismatch")
            except (OSError, TypeError, ValueError) as exc:
                raise PublicDecisionVerificationError("issuance_index_invalid") from exc
            result.append(entry.record_id)
        return tuple(result)

    def verify(self, record_id: str) -> PublicDecisionVerificationResponse:
        """Resolve an issued opaque ID and authenticate the exact retained document."""
        if _RECORD_ID.fullmatch(record_id) is None:
            reason: PublicDecisionVerificationReason = (
                "client_token_not_server_issued"
                if "." in record_id and "/" not in record_id
                else "record_not_issued"
            )
            return self._nonreceipt(
                record_id,
                reason,
                authentication="invalid"
                if reason == "client_token_not_server_issued"
                else "not_established",
            )
        path = self._index_root / f"{record_id}.json"
        try:
            if path.is_symlink():
                return self._nonreceipt(
                    record_id, "issuance_index_invalid", authentication="invalid"
                )
            entry = PublicDecisionVerificationIssuanceIndex.model_validate_json(path.read_bytes())
            if entry.record_id != record_id:
                raise ValueError("issued record ID changed")
        except FileNotFoundError:
            return self._nonreceipt(record_id, "record_not_issued")
        except (OSError, TypeError, ValueError):
            return self._nonreceipt(record_id, "issuance_index_invalid", authentication="invalid")
        return self._verify_entry(entry)

    @staticmethod
    def _nonreceipt(
        record_id: str,
        reason: PublicDecisionVerificationReason,
        *,
        authentication: Literal["invalid", "not_established"] = "not_established",
        signature: Literal["valid", "invalid", "not_established"] = "not_established",
        key_status: Literal[
            "trusted", "revoked", "untrusted", "not_established"
        ] = "not_established",
    ) -> PublicDecisionVerificationResponse:
        return PublicDecisionVerificationResponse(
            record_id=record_id,
            report_authentication=authentication,
            cryptographic_signature=signature,
            report_key_status=key_status,
            reason_codes=(reason, "promoted_public_record_not_established"),
        )

    def _verify_entry(
        self, entry: PublicDecisionVerificationIssuanceIndex
    ) -> PublicDecisionVerificationResponse:
        record_id = entry.record_id
        try:
            artifact_id = artifacts.ArtifactID.model_validate(entry.record_artifact_ref)
            blob = self._store.get_bytes(artifact_id)
            manifest_bytes = self._store.get_manifest_bytes(artifact_id)
            signature = self._store.get_signature(artifact_id)
        except (OSError, TypeError, ValueError, RuntimeError):
            return self._nonreceipt(
                record_id, "record_evidence_unavailable", authentication="invalid"
            )
        if signature is None:
            return self._nonreceipt(record_id, "record_signature_missing")
        trust = self._keys.get(signature.key_id)
        if trust is None:
            return self._nonreceipt(record_id, "record_key_untrusted", key_status="untrusted")
        key_status: Literal["trusted", "revoked"] = "revoked" if trust.revoked else "trusted"
        verification = self._verifier.verify(
            artifact_id, blob, manifest_bytes, signature, strict_identity=False
        )
        if verification.status is not artifacts.SignatureVerificationStatus.VALID:
            return self._nonreceipt(
                record_id,
                "record_signature_invalid",
                authentication="invalid",
                signature="invalid",
                key_status=key_status,
            )
        if trust.revoked:
            return self._nonreceipt(
                record_id, "record_key_revoked", signature="valid", key_status="revoked"
            )
        if trust.issuer_id != self._issuer_id or PUBLIC_VERIFICATION_PURPOSE not in trust.purposes:
            return self._nonreceipt(
                record_id,
                "record_issuer_purpose_untrusted",
                signature="valid",
                key_status=key_status,
            )
        try:
            record = PublicDecisionVerificationRecord.model_validate_json(blob)
            manifest = artifacts.ArtifactManifest.model_validate_json(manifest_bytes)
            if (
                record.model_fields_set != set(PublicDecisionVerificationRecord.model_fields)
                or _digest(blob) != entry.record_artifact_ref
                or record.record_id != entry.record_id
                or record.decision_id != entry.decision_id
                or record.issuer_id != entry.issuer_id
                or record.issuer_id != trust.issuer_id
                or record.signing_key_id != signature.key_id
                or record.rule_version != entry.rule_version
                or record.rule_version != self._rule_version
                or record.public_document_digest != entry.public_document_digest
                or manifest.kind != PUBLIC_VERIFICATION_RECORD_KIND
                or manifest.artifact_schema is None
                or manifest.artifact_schema.name != PUBLIC_VERIFICATION_RECORD_SCHEMA
                or manifest.artifact_schema.version != "1"
            ):
                raise ValueError("signed record binding changed")
        except (TypeError, ValueError):
            return self._nonreceipt(
                record_id,
                "record_binding_invalid",
                authentication="invalid",
                signature="valid",
                key_status=key_status,
            )
        try:
            document_bytes = self._store.get_bytes(record.public_document_digest)
            if _digest(document_bytes) != record.public_document_digest:
                raise ValueError("document digest changed")
            document = _PUBLIC_DOCUMENT.validate_json(document_bytes, strict=True)
        except (OSError, TypeError, ValueError, RuntimeError):
            return self._nonreceipt(
                record_id,
                "public_document_binding_invalid",
                authentication="invalid",
                signature="valid",
                key_status=key_status,
            )
        return PublicDecisionVerificationResponse(
            record_id=record_id,
            report_authentication="verified",
            cryptographic_signature="valid",
            report_key_status="trusted",
            reason_codes=("promoted_public_record_not_established",),
            decision_id=record.decision_id,
            issuer_id=record.issuer_id,
            issued_at=record.issued_at,
            public_document_digest=record.public_document_digest,
            public_document=document,
        )
