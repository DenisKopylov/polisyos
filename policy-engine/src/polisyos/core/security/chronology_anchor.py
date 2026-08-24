"""Exact-byte codecs and role-separated anchor verification primitives.

This module deliberately contains no production appointment.  It can verify an
appointment and the evidence selected by it, but it cannot decide who the
acceptance owner or writer-independent holder is.
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, TypeVar, get_args, get_origin

from pydantic import BaseModel

from polisyos.core.artifacts import ArtifactID, ArtifactRef, DetachedSignature
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts import chronology as contract
from polisyos.core.security.full_prefix import FullPrefixVerifier

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactVerifier


_MEDIA_TYPE = "application/octet-stream"
_ModelT = TypeVar("_ModelT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class AnchorCodec:
    """One frozen semantic domain and its strict statement codec, if typed."""

    key: str
    domain: bytes
    model: type[BaseModel] | None
    preimage_kind: Literal["strict_model", "exact_canonical_bytes"]
    canon_spec: contract.CanonSpec
    fixture_factory: Literal["c3_deterministic_zero_one"]


def _codec(
    key: str,
    model: type[BaseModel] | None,
    *,
    signed_evidence: bool = False,
) -> AnchorCodec:
    prefix = "polisyos." if signed_evidence else "polisyos.chronology."
    return AnchorCodec(
        key=key,
        domain=f"{prefix}{key}\0".encode(),
        model=model,
        preimage_kind="strict_model" if model is not None else "exact_canonical_bytes",
        canon_spec=contract.CHRONOLOGY_CANON_SPEC,
        fixture_factory="c3_deterministic_zero_one",
    )


# Trust snapshots and the retention package are exact canonical byte domains.
# The plan names no authority DTO for either trust snapshot; inventing one here
# would turn a verifier input into a new owner-held carrier.  Their bytes remain
# mandatory and domain-bound while authority stays institutionally supplied.
C3_CANONICAL_CODECS: Mapping[str, AnchorCodec] = MappingProxyType(
    {
        row.key: row
        for row in (
            _codec("anchor-acceptance-statement.v1", contract.AnchorAcceptanceStatement),
            _codec("anchor-acceptance-candidate.v1", contract.AnchorAcceptanceRecord),
            _codec(
                "anchor-lineage-append.v1",
                contract.AnchorAcceptanceAppendSuccessStatement,
            ),
            _codec(
                "anchor-acceptance-receipt.v1",
                contract.AnchorAcceptanceReceiptStatement,
            ),
            _codec("anchor-retention-statement.v1", contract.AnchorRetentionStatement),
            _codec("anchor-custody-receipt.v1", contract.AnchorCustodyReceiptStatement),
            _codec(
                "anchor-readback-challenge.v1",
                contract.AnchorReadbackChallengeStatement,
            ),
            _codec(
                "anchor-readback-receipt.v1",
                contract.AnchorReadbackReceiptStatement,
            ),
            _codec(
                "signed-artifact-evidence-record.v1",
                contract.SignedArtifactEvidenceRecord,
                signed_evidence=True,
            ),
            _codec(
                "anchor-acceptance-appointment.v1",
                contract.AcceptanceVerifierAppointmentStatement,
            ),
            _codec(
                "anchor-acceptance-appointment-verification.v1",
                contract.AcceptanceAppointmentVerificationStatement,
            ),
            _codec(
                "anchor-holder-appointment.v1",
                contract.HolderVerifierAppointmentStatement,
            ),
            _codec(
                "anchor-holder-appointment-verification.v1",
                contract.HolderAppointmentVerificationStatement,
            ),
            _codec("anchor-acceptance-trust-snapshot.v1", None),
            _codec("anchor-holder-trust-snapshot.v1", None),
            _codec(
                "anchor-acceptance-lineage-state.v1",
                contract.AnchorAcceptanceLineageStateStatement,
            ),
            _codec("anchor-retention-package.v1", contract.AnchorRetentionObjectGraph),
        )
    }
)


C3_PRODUCTION_MODULES: tuple[str, ...] = (
    "polisyos.core",
    "polisyos.core.artifacts.signed_evidence",
    "polisyos.core.contracts",
    "polisyos.core.contracts.chronology",
    "polisyos.core.security",
    "polisyos.core.security.anchor_lineage",
    "polisyos.core.security.chronology_anchor",
    "polisyos.runtime.http.container",
    "polisyos.runtime.quality.chronology_custody",
)

C3_MODULE_CLASSIFICATION: Mapping[str, Literal["model_owner", "verified_no_cluster3_model"]] = (
    MappingProxyType(
        {
            module: (
                "model_owner"
                if module
                in {
                    "polisyos.core.artifacts.signed_evidence",
                    "polisyos.core.contracts.chronology",
                    "polisyos.core.security.anchor_lineage",
                    "polisyos.core.security.chronology_anchor",
                }
                else "verified_no_cluster3_model"
            )
            for module in C3_PRODUCTION_MODULES
        }
    )
)

C3_CONTRACT_MODEL_NAMES: tuple[str, ...] = (
    "AnchorAcceptanceRequest",
    "OwnerDerivedAcceptedPrefix",
    "AnchorAcceptanceStatement",
    "AnchorAcceptanceReceiptStatement",
    "SignedArtifactEvidenceRecord",
    "PersistedSignedArtifactEvidence",
    "SignedArtifactEvidence",
    "AnchorAcceptanceReceipt",
    "AnchorAcceptanceRecord",
    "AcceptanceVerifierAppointmentStatement",
    "HolderVerifierAppointmentStatement",
    "AcceptanceAppointmentVerificationStatement",
    "HolderAppointmentVerificationStatement",
    "VerifiedAcceptanceVerifierAppointment",
    "VerifiedHolderVerifierAppointment",
    "AnchorRetentionStatement",
    "AnchorRetentionPackage",
    "AnchorAcceptanceEvidenceBundle",
    "AnchorRetentionObjectGraph",
    "AnchorCustodyReceiptStatement",
    "AnchorCustodyReceiptRecord",
    "AnchorCustodyReceipt",
    "AnchorAcceptanceLineageKey",
    "AnchorReadbackChallengeStatement",
    "PersistedAnchorReadbackChallenge",
    "AnchorReadbackReceiptStatement",
    "AnchorReadbackReceiptRecord",
    "AnchorReadbackReceipt",
    "AcceptanceUnavailableNonReceipt",
    "RetentionUnavailableNonReceipt",
    "AcceptanceRejectedNonReceipt",
    "RetentionRejectedNonReceipt",
    "VerifiedAnchorAcceptance",
    "VerifiedAnchorRetention",
    "VerifiedAcceptanceOutcome",
    "UnavailableAcceptanceOutcome",
    "RejectedAcceptanceOutcome",
    "VerifiedRetentionOutcome",
    "UnavailableRetentionOutcome",
    "RejectedRetentionOutcome",
    "AnchorCustodyVerification",
    "AcceptedAnchorRecordEntry",
    "AnchorAcceptanceLineageStateStatement",
    "AnchorAcceptanceLineageState",
    "AnchorAcceptanceAppendSuccessStatement",
    "PersistedAnchorAcceptanceAppendSuccess",
    "AnchorAcceptanceAppendConflict",
    "EstablishedAcceptanceAppointment",
    "UnavailableAcceptanceAppointment",
    "EstablishedHolderAppointment",
    "UnavailableHolderAppointment",
    "EpochAnchorAppointmentResolution",
)


@dataclass(frozen=True, slots=True)
class C3ModelRegistryRow:
    """Exactly one codec disposition for one concrete Cluster-3 DTO."""

    model: str
    registry_class: Literal["canonical_codec", "persisted_transport", "failure_or_result"]
    codec_key: str | None
    no_domain_reason: str | None


_C3_TRANSPORT_MODELS = frozenset(
    {
        "OwnerDerivedAcceptedPrefix",
        "PersistedSignedArtifactEvidence",
        "SignedArtifactEvidence",
        "AnchorAcceptanceReceipt",
        "AnchorRetentionPackage",
        "AnchorAcceptanceEvidenceBundle",
        "AnchorCustodyReceiptRecord",
        "AnchorCustodyReceipt",
        "AnchorAcceptanceLineageKey",
        "PersistedAnchorReadbackChallenge",
        "AnchorReadbackReceiptRecord",
        "AnchorReadbackReceipt",
        "AcceptedAnchorRecordEntry",
        "VerifiedAcceptanceVerifierAppointment",
        "VerifiedHolderVerifierAppointment",
        "AnchorAcceptanceLineageState",
        "PersistedAnchorAcceptanceAppendSuccess",
    }
)


def _build_model_registry() -> Mapping[str, C3ModelRegistryRow]:
    codec_by_model = {
        row.model.__name__: row.key for row in C3_CANONICAL_CODECS.values() if row.model is not None
    }
    rows: dict[str, C3ModelRegistryRow] = {}
    for model_name in C3_CONTRACT_MODEL_NAMES:
        if model_name in codec_by_model:
            rows[model_name] = C3ModelRegistryRow(
                model=model_name,
                registry_class="canonical_codec",
                codec_key=codec_by_model[model_name],
                no_domain_reason=None,
            )
        elif model_name in _C3_TRANSPORT_MODELS:
            rows[model_name] = C3ModelRegistryRow(
                model=model_name,
                registry_class="persisted_transport",
                codec_key=None,
                no_domain_reason=(
                    "wrapper or byte graph carries identities of already constructed bytes"
                ),
            )
        else:
            rows[model_name] = C3ModelRegistryRow(
                model=model_name,
                registry_class="failure_or_result",
                codec_key=None,
                no_domain_reason=(
                    "query/result DTO is never independently persisted as a canonical domain"
                ),
            )
    return MappingProxyType(rows)


C3_MODEL_REGISTRY: Mapping[str, C3ModelRegistryRow] = _build_model_registry()


@dataclass(frozen=True, slots=True)
class C3HashFieldRule:
    """Generated decisive identity-field rule for one concrete C3 DTO field."""

    model: str
    field_path: str
    role: str
    identity_class: Literal["raw", "semantic", "institutional"]
    exact_preimage: str
    ordering: str
    domain: str | None
    persisting_owner: str
    self_field_exclusion: str


def _contains_artifact_ref(annotation: object) -> bool:
    if annotation is ArtifactRef:
        return True
    return any(_contains_artifact_ref(arg) for arg in get_args(annotation))


def _is_digest_field(field: object) -> bool:
    metadata = getattr(field, "metadata", ())
    return any(getattr(item, "pattern", None) == r"^sha256:[0-9a-f]{64}$" for item in metadata)


_C3_RAW_ROLES = frozenset(
    {
        "acceptance_receipt_record_ref",
        "acceptance_receipt_ref",
        "acceptance_record_ref",
        "append_receipt_ref",
        "artifact_ref",
        "asserted_prior_acceptance_record_refs",
        "bundle_ref",
        "candidate_record_ref",
        "challenge_record_ref",
        "current_record_refs",
        "custody_receipt_record_raw_bytes_hash",
        "custody_receipt_record_ref",
        "decisive_evidence_refs",
        "evidence_record_ref",
        "exact_manifest_raw_bytes_hash",
        "expected_head_refs",
        "lineage_append_receipt_ref",
        "lineage_key_ref",
        "native_reconciliation_ref",
        "observed_head_refs",
        "package_ref",
        "predecessor_record_refs",
        "previous_head_refs",
        "prior_acceptance_record_refs",
        "raw_blob_bytes_hash",
        "readback_receipt_record_raw_bytes_hash",
        "readback_receipt_record_ref",
        "receipt_record_raw_bytes_hash",
        "receipt_record_ref",
        "resulting_head_refs",
        "signature_artifact_ref",
        "signature_raw_bytes_hash",
        "signed_evidence_record_refs",
        "signed_statement_evidence_ref",
        "statement_artifact_ref",
        "statement_evidence_ref",
        "subject_artifact_ref",
    }
)

_C3_INSTITUTIONAL_ROLES = frozenset(
    {
        "acceptance_appointment_content_hash",
        "acceptance_appointment_ref",
        "appointment_basis_ref",
        "appointment_content_hash",
        "appointment_evidence_record_content_hash",
        "appointment_evidence_record_ref",
        "appointment_evidence_ref",
        "appointment_key_ref",
        "appointment_ref",
        "appointment_verification_receipt_content_hash",
        "appointment_verification_receipt_ref",
        "custody_boundary_evidence_ref",
        "holder_appointment_content_hash",
        "holder_appointment_ref",
        "resolved_appointment_ref",
        "resolver_provenance_ref",
        "retention_policy_ref",
        "signer_provenance_ref",
        "signing_profile_ref",
        "trust_config_content_hash",
        "trust_config_ref",
        "trust_snapshot_content_hash",
        "verification_receipt_content_hash",
        "verification_receipt_ref",
        "verifier_provenance_ref",
    }
)

_C3_SEMANTIC_ROLES = frozenset(
    {
        "acceptance_digest",
        "acceptance_receipt_content_hash",
        "acceptance_receipt_record_content_hash",
        "acceptance_record_content_hash",
        "admission_cutoff_ref",
        "append_receipt_content_hash",
        "bundle_content_hash",
        "challenge_record_content_hash",
        "evidence_record_content_hash",
        "expected_package_content_hash",
        "lineage_append_receipt_content_hash",
        "lineage_state_content_hash",
        "owner_lineage_state_content_hash",
        "package_content_hash",
        "receipt_record_content_hash",
        "requested_query_context_ref",
        "resulting_state_content_hash",
        "scope_ref",
        "signed_statement_evidence_content_hash",
        "state_content_hash",
        "statement_content_hash",
    }
)


def _identity_class(*, field_name: str) -> Literal["raw", "semantic", "institutional"]:
    matches = tuple(
        identity_class
        for identity_class, roles in (
            ("raw", _C3_RAW_ROLES),
            ("semantic", _C3_SEMANTIC_ROLES),
            ("institutional", _C3_INSTITUTIONAL_ROLES),
        )
        if field_name in roles
    )
    if len(matches) != 1:
        raise RuntimeError(
            f"C3 hash role {field_name!r} has {len(matches)} explicit classifications"
        )
    return matches[0]


def _persisting_owner(model_name: str) -> str:
    if any(token in model_name for token in ("Holder", "Retention", "Custody", "Readback")):
        return "appointed_holder_or_holder_verifier"
    if "Appointment" in model_name:
        return "institutional_appointment_resolver"
    return "acceptance_owner_or_acceptance_verifier"


def _build_hash_field_rules() -> Mapping[str, C3HashFieldRule]:
    rows: dict[str, C3HashFieldRule] = {}
    for model_name in C3_CONTRACT_MODEL_NAMES:
        model = getattr(contract, model_name)
        for field_name, field in model.model_fields.items():
            artifact_ref = _contains_artifact_ref(field.annotation)
            if not artifact_ref and not _is_digest_field(field):
                continue
            field_path = f"{field_name}.artifact_id" if artifact_ref else field_name
            key = f"{model_name}.{field_path}"
            identity_class = _identity_class(field_name=field_name)
            rows[key] = C3HashFieldRule(
                model=model_name,
                field_path=field_path,
                role=field_name,
                identity_class=identity_class,
                exact_preimage=(
                    "verified appointment snapshot; never recomputed locally as authority"
                    if identity_class == "institutional"
                    else "exact bytes named by ArtifactRef"
                    if identity_class == "raw"
                    else "domain-separated canonical framed bytes"
                ),
                ordering=(
                    "tuple order preserved"
                    if get_origin(field.annotation) is tuple
                    else "single value"
                ),
                domain=(
                    None
                    if identity_class != "semantic"
                    else "owning codec or explicitly imported semantic domain"
                ),
                persisting_owner=_persisting_owner(model_name),
                self_field_exclusion=key,
            )
    return MappingProxyType(rows)


C3_HASH_FIELD_RULES: Mapping[str, C3HashFieldRule] = _build_hash_field_rules()


def canonical_statement_bytes(statement: BaseModel) -> bytes:
    """Encode a typed statement with the shared raw-mapping framing rule."""

    return contract._frame_record(
        contract._canonical_raw_bytes(contract._raw_model_mapping(statement))
    )


def canonical_exact_mapping_bytes(mapping: Mapping[str, object]) -> bytes:
    """Encode one fresh raw mapping for a domain without an authority DTO."""

    return contract._frame_record(contract._canonical_raw_bytes(dict(mapping)))


def semantic_content_hash(codec_key: str, payload: bytes) -> contract.Digest:
    """Return the frozen domain-separated identity for exact framed bytes."""

    try:
        codec = C3_CANONICAL_CODECS[codec_key]
    except KeyError as exc:
        raise ValueError(f"unknown anchor codec: {codec_key}") from exc
    return contract._sha256_digest(codec.domain, payload)


def raw_content_hash(payload: bytes) -> contract.Digest:
    """Return the raw CAS identity, with no semantic domain prefix."""

    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _artifact_ref(payload: bytes, *, kind: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(raw_content_hash(payload)),
        kind=kind,
        media_type=_MEDIA_TYPE,
    )


def parse_canonical_statement(payload: bytes, model: type[_ModelT]) -> _ModelT:
    """Parse, strictly validate, and byte-for-byte reserialize one statement."""

    frames = contract._split_framed_records(payload)
    if len(frames) != 1:
        raise ValueError("anchor statement must contain exactly one frame")
    raw = from_canonical_bytes(frames[0])
    if not isinstance(raw, dict):
        raise ValueError("anchor statement must decode to a mapping")
    parsed = model.model_validate(raw)
    if canonical_statement_bytes(parsed) != payload:
        raise ValueError("anchor statement is not canonical for its strict codec")
    return parsed


def verify_signed_evidence(
    evidence: contract.SignedArtifactEvidence,
    *,
    verifier: ArtifactVerifier,
) -> bool:
    """Verify exact evidence bytes and the detached signature cryptographically."""

    record = parse_canonical_statement(
        evidence.persisted.record_bytes,
        contract.SignedArtifactEvidenceRecord,
    )
    raw_checks = (
        (
            str(evidence.persisted.evidence_record_ref.artifact_id),
            raw_content_hash(evidence.persisted.record_bytes),
        ),
        (
            evidence.persisted.evidence_record_content_hash,
            semantic_content_hash(
                "signed-artifact-evidence-record.v1",
                evidence.persisted.record_bytes,
            ),
        ),
        (str(record.artifact_ref.artifact_id), raw_content_hash(evidence.blob_bytes)),
        (record.raw_blob_bytes_hash, raw_content_hash(evidence.blob_bytes)),
        (
            record.exact_manifest_raw_bytes_hash,
            raw_content_hash(evidence.exact_manifest_bytes),
        ),
        (
            record.signature_raw_bytes_hash,
            raw_content_hash(evidence.detached_signature_bytes),
        ),
        (
            str(record.signature_artifact_ref.artifact_id),
            raw_content_hash(evidence.detached_signature_bytes),
        ),
    )
    if any(expected != observed for expected, observed in raw_checks):
        return False
    try:
        signature = DetachedSignature.model_validate_json(evidence.detached_signature_bytes)
    except ValueError:
        return False
    result = verifier.verify(
        record.artifact_ref.artifact_id,
        evidence.blob_bytes,
        evidence.exact_manifest_bytes,
        signature,
        strict_identity=True,
    )
    return bool(result.ok)


def _trusted_key_ids(snapshot_bytes: bytes) -> frozenset[str] | None:
    """Parse the exact appointment snapshot without treating its shape as trust."""

    try:
        frames = contract._split_framed_records(snapshot_bytes)
        if len(frames) != 1:
            return None
        mapping = from_canonical_bytes(frames[0])
    except (TypeError, ValueError):
        return None
    if not isinstance(mapping, dict) or canonical_exact_mapping_bytes(mapping) != snapshot_bytes:
        return None
    values = mapping.get("trusted_keys")
    if (
        not isinstance(values, list)
        or not values
        or not all(isinstance(value, str) and value for value in values)
    ):
        return None
    return frozenset(values)


def _evidence_key_is_appointed(
    evidence: contract.SignedArtifactEvidence,
    *,
    trust_snapshot_bytes: bytes,
) -> bool:
    """Bind an authentic signature to the exact appointed trust snapshot."""

    trusted = _trusted_key_ids(trust_snapshot_bytes)
    if trusted is None:
        return False
    try:
        signature = DetachedSignature.model_validate_json(evidence.detached_signature_bytes)
    except ValueError:
        return False
    return signature.key_id in trusted


def _acceptance_rejection(
    *,
    code: Literal[
        "anchor_signature_unverified",
        "anchor_query_or_lineage_mismatch",
        "accepted_anchor_lineage_conflict",
    ],
    subject_ref: ArtifactRef,
    query_ref: contract.Digest,
    appointment_ref: ArtifactRef,
    verifier_ref: ArtifactRef,
    evidence_refs: tuple[ArtifactRef, ...],
) -> contract.AcceptanceRejectedNonReceipt:
    return contract.AcceptanceRejectedNonReceipt(
        status="rejected",
        component="acceptance",
        code=code,
        subject_artifact_ref=subject_ref,
        requested_query_context_ref=query_ref,
        appointment_ref=appointment_ref,
        verifier_provenance_ref=verifier_ref,
        decisive_evidence_refs=evidence_refs,
        predicate_class="independently_reconciled",
    )


def _retention_rejection(
    *,
    code: Literal[
        "anchor_package_mismatch",
        "anchor_signature_unverified",
        "anchor_readback_mismatch",
        "anchor_query_or_lineage_mismatch",
    ],
    subject_ref: ArtifactRef,
    query_ref: contract.Digest,
    appointment_ref: ArtifactRef,
    verifier_ref: ArtifactRef,
    evidence_refs: tuple[ArtifactRef, ...],
) -> contract.RetentionRejectedNonReceipt:
    return contract.RetentionRejectedNonReceipt(
        status="rejected",
        component="retention",
        code=code,
        subject_artifact_ref=subject_ref,
        requested_query_context_ref=query_ref,
        appointment_ref=appointment_ref,
        verifier_provenance_ref=verifier_ref,
        decisive_evidence_refs=evidence_refs,
        predicate_class="independently_reconciled",
    )


def _verify_acceptance_appointment(
    appointment: contract.VerifiedAcceptanceVerifierAppointment,
    *,
    verifier: ArtifactVerifier,
) -> (
    tuple[
        contract.AcceptanceVerifierAppointmentStatement,
        contract.AcceptanceAppointmentVerificationStatement,
    ]
    | None
):
    if (
        appointment.signed_appointment_evidence.blob_bytes != appointment.statement_bytes
        or appointment.signed_verification_evidence.blob_bytes
        != appointment.verification_statement_bytes
        or not verify_signed_evidence(appointment.signed_appointment_evidence, verifier=verifier)
        or not verify_signed_evidence(appointment.signed_verification_evidence, verifier=verifier)
        or not _evidence_key_is_appointed(
            appointment.signed_appointment_evidence,
            trust_snapshot_bytes=appointment.trust_config_bytes,
        )
        or not _evidence_key_is_appointed(
            appointment.signed_verification_evidence,
            trust_snapshot_bytes=appointment.trust_config_bytes,
        )
    ):
        return None
    try:
        statement = parse_canonical_statement(
            appointment.statement_bytes,
            contract.AcceptanceVerifierAppointmentStatement,
        )
        verification = parse_canonical_statement(
            appointment.verification_statement_bytes,
            contract.AcceptanceAppointmentVerificationStatement,
        )
    except ValueError:
        return None
    checks = (
        str(appointment.appointment_ref.artifact_id)
        == raw_content_hash(appointment.statement_bytes),
        appointment.appointment_content_hash
        == semantic_content_hash("anchor-acceptance-appointment.v1", appointment.statement_bytes),
        verification.appointment_ref == appointment.appointment_ref,
        verification.appointment_content_hash == appointment.appointment_content_hash,
        verification.trust_config_ref == statement.trust_config_ref,
        verification.trust_config_content_hash == statement.trust_config_content_hash,
        verification.appointment_evidence_record_ref
        == appointment.signed_appointment_evidence.persisted.evidence_record_ref,
        verification.appointment_evidence_record_content_hash
        == appointment.signed_appointment_evidence.persisted.evidence_record_content_hash,
        verification.verifier_provenance_ref == statement.verifier_provenance_ref,
        str(statement.trust_config_ref.artifact_id)
        == raw_content_hash(appointment.trust_config_bytes),
        statement.trust_config_content_hash
        == semantic_content_hash(
            "anchor-acceptance-trust-snapshot.v1", appointment.trust_config_bytes
        ),
        appointment.verification_receipt_content_hash
        == semantic_content_hash(
            "anchor-acceptance-appointment-verification.v1",
            appointment.verification_statement_bytes,
        ),
        str(appointment.verification_receipt_ref.artifact_id)
        == raw_content_hash(appointment.verification_statement_bytes),
    )
    if not all(checks):
        return None
    return statement, verification


def _verify_holder_appointment(
    appointment: contract.VerifiedHolderVerifierAppointment,
    *,
    verifier: ArtifactVerifier,
) -> (
    tuple[
        contract.HolderVerifierAppointmentStatement,
        contract.HolderAppointmentVerificationStatement,
    ]
    | None
):
    if (
        appointment.signed_appointment_evidence.blob_bytes != appointment.statement_bytes
        or appointment.signed_verification_evidence.blob_bytes
        != appointment.verification_statement_bytes
        or not verify_signed_evidence(appointment.signed_appointment_evidence, verifier=verifier)
        or not verify_signed_evidence(appointment.signed_verification_evidence, verifier=verifier)
        or not _evidence_key_is_appointed(
            appointment.signed_appointment_evidence,
            trust_snapshot_bytes=appointment.trust_config_bytes,
        )
        or not _evidence_key_is_appointed(
            appointment.signed_verification_evidence,
            trust_snapshot_bytes=appointment.trust_config_bytes,
        )
    ):
        return None
    try:
        statement = parse_canonical_statement(
            appointment.statement_bytes,
            contract.HolderVerifierAppointmentStatement,
        )
        verification = parse_canonical_statement(
            appointment.verification_statement_bytes,
            contract.HolderAppointmentVerificationStatement,
        )
    except ValueError:
        return None
    checks = (
        str(appointment.appointment_ref.artifact_id)
        == raw_content_hash(appointment.statement_bytes),
        appointment.appointment_content_hash
        == semantic_content_hash("anchor-holder-appointment.v1", appointment.statement_bytes),
        verification.appointment_ref == appointment.appointment_ref,
        verification.appointment_content_hash == appointment.appointment_content_hash,
        verification.trust_config_ref == statement.trust_config_ref,
        verification.trust_config_content_hash == statement.trust_config_content_hash,
        verification.appointment_evidence_record_ref
        == appointment.signed_appointment_evidence.persisted.evidence_record_ref,
        verification.appointment_evidence_record_content_hash
        == appointment.signed_appointment_evidence.persisted.evidence_record_content_hash,
        verification.verifier_provenance_ref == statement.verifier_provenance_ref,
        str(statement.trust_config_ref.artifact_id)
        == raw_content_hash(appointment.trust_config_bytes),
        statement.trust_config_content_hash
        == semantic_content_hash("anchor-holder-trust-snapshot.v1", appointment.trust_config_bytes),
        appointment.verification_receipt_content_hash
        == semantic_content_hash(
            "anchor-holder-appointment-verification.v1",
            appointment.verification_statement_bytes,
        ),
        str(appointment.verification_receipt_ref.artifact_id)
        == raw_content_hash(appointment.verification_statement_bytes),
    )
    if not all(checks):
        return None
    return statement, verification


@dataclass(frozen=True, slots=True)
class ExactAnchorAcceptanceReceiptVerifier:
    """Verify acceptance from exact bytes, appointment, and owner lineage."""

    artifact_verifier: ArtifactVerifier

    def verify(
        self,
        *,
        receipt: contract.AnchorAcceptanceReceipt,
        appointment: contract.VerifiedAcceptanceVerifierAppointment,
        evidence: contract.AnchorAcceptanceEvidenceBundle,
        lineage: contract.AnchorAcceptanceLineageRepository,
        requested_query_context_ref: contract.Digest,
    ) -> contract.VerifiedAnchorAcceptance | contract.AcceptanceNonReceipt:
        appointment_models = _verify_acceptance_appointment(
            appointment, verifier=self.artifact_verifier
        )
        verifier_ref = ArtifactRef(
            artifact_id=ArtifactID.model_validate(raw_content_hash(b"unverified-verifier")),
            kind="chronology.verifier",
            media_type=_MEDIA_TYPE,
        )
        if appointment_models is not None:
            appointment_statement, _ = appointment_models
            verifier_ref = appointment_statement.verifier_provenance_ref
        decisive = (
            receipt.signed_receipt_evidence.persisted.evidence_record_ref,
            evidence.acceptance_statement_evidence.persisted.evidence_record_ref,
        )
        if (
            appointment_models is None
            or receipt.signed_receipt_evidence.blob_bytes != receipt.statement_bytes
            or evidence.acceptance_receipt_signed_evidence.blob_bytes != receipt.statement_bytes
            or not verify_signed_evidence(
                receipt.signed_receipt_evidence, verifier=self.artifact_verifier
            )
            or not verify_signed_evidence(
                evidence.acceptance_statement_evidence,
                verifier=self.artifact_verifier,
            )
            or not _evidence_key_is_appointed(
                receipt.signed_receipt_evidence,
                trust_snapshot_bytes=appointment.trust_config_bytes,
            )
            or not _evidence_key_is_appointed(
                evidence.acceptance_statement_evidence,
                trust_snapshot_bytes=appointment.trust_config_bytes,
            )
        ):
            return _acceptance_rejection(
                code="anchor_signature_unverified",
                subject_ref=receipt.receipt_record_ref,
                query_ref=requested_query_context_ref,
                appointment_ref=appointment.appointment_ref,
                verifier_ref=verifier_ref,
                evidence_refs=decisive,
            )
        appointment_statement, _ = appointment_models
        try:
            acceptance_statement = parse_canonical_statement(
                evidence.acceptance_statement_evidence.blob_bytes,
                contract.AnchorAcceptanceStatement,
            )
            candidate = parse_canonical_statement(
                evidence.acceptance_record_bytes,
                contract.AnchorAcceptanceRecord,
            )
            receipt_statement = parse_canonical_statement(
                receipt.statement_bytes,
                contract.AnchorAcceptanceReceiptStatement,
            )
            append = parse_canonical_statement(
                evidence.lineage_append_receipt_bytes,
                contract.AnchorAcceptanceAppendSuccessStatement,
            )
        except ValueError:
            return _acceptance_rejection(
                code="anchor_query_or_lineage_mismatch",
                subject_ref=receipt.receipt_record_ref,
                query_ref=requested_query_context_ref,
                appointment_ref=appointment.appointment_ref,
                verifier_ref=verifier_ref,
                evidence_refs=decisive,
            )
        key = contract.AnchorAcceptanceLineageKey(
            family="epoch",
            proof_domain=acceptance_statement.parsed_header.proof_domain,
            scope_ref=acceptance_statement.parsed_header.scope_ref,
            authority_purpose=acceptance_statement.authority_purpose,
        )
        state = lineage.resolve_lineage(key=key)
        state_statement = parse_canonical_statement(
            state.statement_bytes,
            contract.AnchorAcceptanceLineageStateStatement,
        )
        acceptance_record_ref = receipt_statement.acceptance_record_ref
        current = acceptance_record_ref in state_statement.current_record_refs
        record_position = next(
            (
                index
                for index, item in enumerate(state_statement.records)
                if item.acceptance_record_ref == acceptance_record_ref
            ),
            None,
        )
        retained = record_position is not None
        retained_entry = (
            state_statement.records[record_position] if record_position is not None else None
        )
        derived_prefix_bindings = tuple(
            any(
                item.acceptance_record_ref == row.acceptance_record_ref
                and item.acceptance_record_content_hash == row.acceptance_record_content_hash
                and item.signed_statement_evidence_ref == row.statement_evidence_ref
                for item in state_statement.records
            )
            and row.acceptance_record_ref in acceptance_statement.prior_acceptance_record_refs
            for row in acceptance_statement.derived_prior_prefixes
        )
        derived_prefix_keys = tuple(
            (row.expected_prefix.member_count, row.expected_prefix.commitment_head)
            for row in acceptance_statement.derived_prior_prefixes
        )
        historical_state_hash: contract.Digest | None = None
        prior_state_hash: contract.Digest | None = None
        if record_position is not None:
            historical_statement = contract.AnchorAcceptanceLineageStateStatement(
                key=key,
                current_record_refs=(acceptance_record_ref,),
                records=state_statement.records[: record_position + 1],
            )
            historical_state_hash = semantic_content_hash(
                "anchor-acceptance-lineage-state.v1",
                canonical_statement_bytes(historical_statement),
            )
            prior_statement = contract.AnchorAcceptanceLineageStateStatement(
                key=key,
                current_record_refs=candidate.prior_acceptance_record_refs,
                records=state_statement.records[:record_position],
            )
            prior_state_hash = semantic_content_hash(
                "anchor-acceptance-lineage-state.v1",
                canonical_statement_bytes(prior_statement),
            )
        bindings = (
            receipt.receipt_record_bytes == receipt.statement_bytes,
            evidence.acceptance_receipt_bytes == receipt.statement_bytes,
            evidence.acceptance_receipt_signed_evidence == receipt.signed_receipt_evidence,
            str(receipt.receipt_record_ref.artifact_id)
            == raw_content_hash(receipt.statement_bytes),
            receipt.receipt_record_content_hash
            == semantic_content_hash("anchor-acceptance-receipt.v1", receipt.statement_bytes),
            acceptance_statement.requested_query_context_ref == requested_query_context_ref,
            receipt_statement.requested_query_context_ref == requested_query_context_ref,
            acceptance_statement.parsed_header.requested_query_context_ref
            == requested_query_context_ref,
            acceptance_statement.parsed_header.requested_cutoff_ref
            == acceptance_statement.admission_cutoff_ref,
            acceptance_statement.admission_cutoff_ref == receipt_statement.admission_cutoff_ref,
            acceptance_statement.parsed_header.family == "epoch",
            acceptance_statement.parsed_header.proof_domain == appointment_statement.proof_domain,
            acceptance_statement.authority_purpose == appointment_statement.authority_purpose,
            acceptance_statement.acceptance_appointment_ref == appointment.appointment_ref,
            acceptance_statement.acceptance_appointment_content_hash
            == appointment.appointment_content_hash,
            acceptance_statement.accepting_owner_ref == appointment_statement.accepting_owner_ref,
            acceptance_statement.appointment_verification_receipt_ref
            == appointment.verification_receipt_ref,
            acceptance_statement.appointment_verification_receipt_content_hash
            == appointment.verification_receipt_content_hash,
            acceptance_statement.trust_snapshot_content_hash
            == semantic_content_hash(
                "anchor-acceptance-trust-snapshot.v1", appointment.trust_config_bytes
            ),
            acceptance_statement.verifier_provenance_ref
            == str(appointment_statement.verifier_provenance_ref.artifact_id),
            acceptance_statement.owner_lineage_state_content_hash == prior_state_hash,
            acceptance_statement.prior_acceptance_record_refs
            == candidate.prior_acceptance_record_refs,
            bool(acceptance_statement.prior_acceptance_record_refs)
            == bool(acceptance_statement.derived_prior_prefixes),
            len(derived_prefix_keys) == len(set(derived_prefix_keys)),
            all(derived_prefix_bindings),
            candidate.acceptance_digest
            == semantic_content_hash(
                "anchor-acceptance-statement.v1",
                evidence.acceptance_statement_evidence.blob_bytes,
            ),
            str(candidate.statement_artifact_ref.artifact_id)
            == raw_content_hash(evidence.acceptance_statement_evidence.blob_bytes),
            candidate.statement_content_hash == candidate.acceptance_digest,
            candidate.signed_statement_evidence_ref
            == evidence.acceptance_statement_evidence.persisted.evidence_record_ref,
            receipt_statement.acceptance_digest == candidate.acceptance_digest,
            receipt_statement.signed_statement_evidence_ref
            == candidate.signed_statement_evidence_ref,
            str(acceptance_record_ref.artifact_id)
            == raw_content_hash(evidence.acceptance_record_bytes),
            receipt_statement.acceptance_record_content_hash
            == semantic_content_hash(
                "anchor-acceptance-candidate.v1", evidence.acceptance_record_bytes
            ),
            receipt_statement.lineage_key_ref == raw_content_hash(canonical_statement_bytes(key)),
            append.acceptance_record_ref == acceptance_record_ref,
            append.status in {"appended", "idempotent"},
            append.key == key,
            append.expected_head_refs == candidate.prior_acceptance_record_refs,
            append.previous_head_refs == candidate.prior_acceptance_record_refs,
            append.resulting_head_refs == (acceptance_record_ref,),
            str(receipt_statement.lineage_append_receipt_ref.artifact_id)
            == raw_content_hash(evidence.lineage_append_receipt_bytes),
            receipt_statement.lineage_append_receipt_content_hash
            == semantic_content_hash(
                "anchor-lineage-append.v1", evidence.lineage_append_receipt_bytes
            ),
            append.resulting_state_content_hash == historical_state_hash,
            retained_entry is not None,
            retained_entry is not None
            and retained_entry.acceptance_record_content_hash
            == receipt_statement.acceptance_record_content_hash,
            retained_entry is not None
            and retained_entry.acceptance_digest == candidate.acceptance_digest,
            retained_entry is not None
            and retained_entry.signed_statement_evidence_ref
            == candidate.signed_statement_evidence_ref,
            retained_entry is not None
            and retained_entry.requested_query_context_ref == requested_query_context_ref,
            retained_entry is not None
            and retained_entry.admission_cutoff_ref == receipt_statement.admission_cutoff_ref,
            retained_entry is not None
            and retained_entry.predecessor_record_refs == candidate.prior_acceptance_record_refs,
            retained,
        )
        if not all(bindings):
            return _acceptance_rejection(
                code="anchor_query_or_lineage_mismatch",
                subject_ref=acceptance_record_ref,
                query_ref=requested_query_context_ref,
                appointment_ref=appointment.appointment_ref,
                verifier_ref=verifier_ref,
                evidence_refs=decisive,
            )
        return contract.VerifiedAnchorAcceptance(
            acceptance_digest=candidate.acceptance_digest,
            acceptance_record_ref=acceptance_record_ref,
            acceptance_record_content_hash=receipt_statement.acceptance_record_content_hash,
            acceptance_receipt_record_ref=receipt.receipt_record_ref,
            acceptance_receipt_record_content_hash=receipt.receipt_record_content_hash,
            lineage_append_receipt_ref=receipt_statement.lineage_append_receipt_ref,
            lineage_append_receipt_content_hash=(
                receipt_statement.lineage_append_receipt_content_hash
            ),
            lineage_state_content_hash=append.resulting_state_content_hash,
            lineage_position="current" if current else "historical_for_exact_query",
            accepting_owner_ref=acceptance_statement.accepting_owner_ref,
            statement_content_hash=candidate.statement_content_hash,
            signed_statement_evidence_ref=candidate.signed_statement_evidence_ref,
            acceptance_appointment_ref=appointment.appointment_ref,
            acceptance_appointment_content_hash=appointment.appointment_content_hash,
            verifier_provenance_ref=verifier_ref,
            requested_query_context_ref=requested_query_context_ref,
            admission_cutoff_ref=receipt_statement.admission_cutoff_ref,
            prior_acceptance_record_refs=candidate.prior_acceptance_record_refs,
            predicate_class="independently_reconciled",
        )


@dataclass(frozen=True, slots=True)
class ExactAnchorHolderReceiptVerifier:
    """Verify holder-returned package/receipts without a writer repository."""

    artifact_verifier: ArtifactVerifier

    def verify_retention_and_readback(
        self,
        *,
        retention: contract.AnchorCustodyReceipt,
        readback: contract.AnchorReadbackReceipt,
        challenge: contract.PersistedAnchorReadbackChallenge,
        appointment: contract.VerifiedHolderVerifierAppointment,
    ) -> contract.VerifiedAnchorRetention | contract.RetentionNonReceipt:
        appointment_models = _verify_holder_appointment(
            appointment, verifier=self.artifact_verifier
        )
        fallback_verifier = ArtifactRef(
            artifact_id=ArtifactID.model_validate(raw_content_hash(b"unverified-holder")),
            kind="chronology.verifier",
            media_type=_MEDIA_TYPE,
        )
        verifier_ref = (
            appointment_models[0].verifier_provenance_ref
            if appointment_models is not None
            else fallback_verifier
        )
        evidence_refs = (
            retention.signed_statement_evidence.persisted.evidence_record_ref,
            readback.signed_statement_evidence.persisted.evidence_record_ref,
        )
        try:
            challenge_statement = parse_canonical_statement(
                challenge.statement_bytes,
                contract.AnchorReadbackChallengeStatement,
            )
        except ValueError:
            challenge_statement = None
        query_ref = (
            challenge_statement.requested_query_context_ref
            if isinstance(challenge_statement, contract.AnchorReadbackChallengeStatement)
            else raw_content_hash(challenge.statement_bytes)
        )
        if (
            appointment_models is None
            or retention.signed_statement_evidence.blob_bytes != retention.statement_bytes
            or readback.signed_statement_evidence.blob_bytes != readback.statement_bytes
            or not verify_signed_evidence(
                retention.signed_statement_evidence,
                verifier=self.artifact_verifier,
            )
            or not verify_signed_evidence(
                readback.signed_statement_evidence,
                verifier=self.artifact_verifier,
            )
            or not _evidence_key_is_appointed(
                retention.signed_statement_evidence,
                trust_snapshot_bytes=appointment.trust_config_bytes,
            )
            or not _evidence_key_is_appointed(
                readback.signed_statement_evidence,
                trust_snapshot_bytes=appointment.trust_config_bytes,
            )
        ):
            return _retention_rejection(
                code="anchor_signature_unverified",
                subject_ref=readback.receipt_record_ref,
                query_ref=query_ref,
                appointment_ref=appointment.appointment_ref,
                verifier_ref=verifier_ref,
                evidence_refs=evidence_refs,
            )
        if not isinstance(challenge_statement, contract.AnchorReadbackChallengeStatement):
            return _retention_rejection(
                code="anchor_readback_mismatch",
                subject_ref=readback.receipt_record_ref,
                query_ref=query_ref,
                appointment_ref=appointment.appointment_ref,
                verifier_ref=verifier_ref,
                evidence_refs=evidence_refs,
            )
        holder_statement, _ = appointment_models
        try:
            custody_statement = parse_canonical_statement(
                retention.statement_bytes, contract.AnchorCustodyReceiptStatement
            )
            custody_record = parse_canonical_statement(
                retention.receipt_record_bytes, contract.AnchorCustodyReceiptRecord
            )
            readback_statement = parse_canonical_statement(
                readback.statement_bytes, contract.AnchorReadbackReceiptStatement
            )
            readback_record = parse_canonical_statement(
                readback.receipt_record_bytes, contract.AnchorReadbackReceiptRecord
            )
            graph = parse_canonical_statement(
                readback.package_bytes, contract.AnchorRetentionObjectGraph
            )
            retention_statement = parse_canonical_statement(
                graph.retention_statement_bytes, contract.AnchorRetentionStatement
            )
            acceptance_appointment_models = _verify_acceptance_appointment(
                graph.acceptance_appointment,
                verifier=self.artifact_verifier,
            )
            acceptance_statement = parse_canonical_statement(
                graph.acceptance_evidence.acceptance_statement_evidence.blob_bytes,
                contract.AnchorAcceptanceStatement,
            )
            acceptance_candidate = parse_canonical_statement(
                graph.acceptance_evidence.acceptance_record_bytes,
                contract.AnchorAcceptanceRecord,
            )
            acceptance_receipt = parse_canonical_statement(
                graph.acceptance_evidence.acceptance_receipt_bytes,
                contract.AnchorAcceptanceReceiptStatement,
            )
            acceptance_append = parse_canonical_statement(
                graph.acceptance_evidence.lineage_append_receipt_bytes,
                contract.AnchorAcceptanceAppendSuccessStatement,
            )
            custody_evidence_record = parse_canonical_statement(
                retention.signed_statement_evidence.persisted.record_bytes,
                contract.SignedArtifactEvidenceRecord,
            )
            readback_evidence_record = parse_canonical_statement(
                readback.signed_statement_evidence.persisted.record_bytes,
                contract.SignedArtifactEvidenceRecord,
            )
            acceptance_statement_evidence_record = parse_canonical_statement(
                graph.acceptance_evidence.acceptance_statement_evidence.persisted.record_bytes,
                contract.SignedArtifactEvidenceRecord,
            )
            acceptance_receipt_evidence_record = parse_canonical_statement(
                graph.acceptance_evidence.acceptance_receipt_signed_evidence.persisted.record_bytes,
                contract.SignedArtifactEvidenceRecord,
            )
        except ValueError:
            return _retention_rejection(
                code="anchor_package_mismatch",
                subject_ref=readback.receipt_record_ref,
                query_ref=query_ref,
                appointment_ref=appointment.appointment_ref,
                verifier_ref=verifier_ref,
                evidence_refs=evidence_refs,
            )
        package_ref = raw_content_hash(readback.package_bytes)
        package_hash = semantic_content_hash("anchor-retention-package.v1", readback.package_bytes)
        expected_domain = contract.ChronologyProofDomain(
            format=acceptance_statement.parsed_header.format,
            profile=acceptance_statement.parsed_header.profile,
            proof_domain=acceptance_statement.parsed_header.proof_domain,
            family=acceptance_statement.parsed_header.family,
            scope_ref=acceptance_statement.parsed_header.scope_ref,
            authority_purpose=acceptance_statement.parsed_header.authority_purpose,
        )
        bundle_proof = FullPrefixVerifier().verify_bundle(
            graph.bundle_bytes,
            expected_domain=expected_domain,
            expected_bundle_content_hash=acceptance_statement.bundle_content_hash,
        )
        prior_prefix_proofs = tuple(
            FullPrefixVerifier().verify_bundle(
                graph.bundle_bytes,
                expected_domain=expected_domain,
                expected_prefix=row.expected_prefix,
                expected_bundle_content_hash=acceptance_statement.bundle_content_hash,
            )
            for row in acceptance_statement.derived_prior_prefixes
        )
        acceptance_key = contract.AnchorAcceptanceLineageKey(
            family="epoch",
            proof_domain=acceptance_statement.parsed_header.proof_domain,
            scope_ref=acceptance_statement.parsed_header.scope_ref,
            authority_purpose=acceptance_statement.authority_purpose,
        )
        acceptance_appointment_statement = (
            acceptance_appointment_models[0] if acceptance_appointment_models is not None else None
        )
        derived_prefix_refs = tuple(
            row.acceptance_record_ref for row in acceptance_statement.derived_prior_prefixes
        )
        derived_prefix_ref_ids = tuple(str(ref.artifact_id) for ref in derived_prefix_refs)
        derived_prefix_keys = tuple(
            (row.expected_prefix.member_count, row.expected_prefix.commitment_head)
            for row in acceptance_statement.derived_prior_prefixes
        )
        bindings = (
            acceptance_appointment_models is not None,
            verify_signed_evidence(
                graph.acceptance_evidence.acceptance_statement_evidence,
                verifier=self.artifact_verifier,
            ),
            verify_signed_evidence(
                graph.acceptance_evidence.acceptance_receipt_signed_evidence,
                verifier=self.artifact_verifier,
            ),
            _evidence_key_is_appointed(
                graph.acceptance_evidence.acceptance_statement_evidence,
                trust_snapshot_bytes=graph.acceptance_appointment.trust_config_bytes,
            ),
            _evidence_key_is_appointed(
                graph.acceptance_evidence.acceptance_receipt_signed_evidence,
                trust_snapshot_bytes=graph.acceptance_appointment.trust_config_bytes,
            ),
            readback.retention_receipt == retention,
            str(retention.receipt_record_ref.artifact_id)
            == raw_content_hash(retention.receipt_record_bytes),
            retention.receipt_record_raw_bytes_hash
            == raw_content_hash(retention.receipt_record_bytes),
            str(readback.receipt_record_ref.artifact_id)
            == raw_content_hash(readback.receipt_record_bytes),
            readback.receipt_record_raw_bytes_hash
            == raw_content_hash(readback.receipt_record_bytes),
            custody_record.statement_artifact_ref == custody_evidence_record.artifact_ref,
            custody_record.statement_content_hash
            == semantic_content_hash("anchor-custody-receipt.v1", retention.statement_bytes),
            custody_record.signed_statement_evidence_ref
            == retention.signed_statement_evidence.persisted.evidence_record_ref,
            custody_record.signed_statement_evidence_content_hash
            == retention.signed_statement_evidence.persisted.evidence_record_content_hash,
            readback_record.statement_artifact_ref == readback_evidence_record.artifact_ref,
            readback_record.statement_content_hash
            == semantic_content_hash("anchor-readback-receipt.v1", readback.statement_bytes),
            readback_record.signed_statement_evidence_ref
            == readback.signed_statement_evidence.persisted.evidence_record_ref,
            readback_record.signed_statement_evidence_content_hash
            == readback.signed_statement_evidence.persisted.evidence_record_content_hash,
            challenge.challenge_record_content_hash
            == semantic_content_hash("anchor-readback-challenge.v1", challenge.statement_bytes),
            str(challenge.challenge_record_ref.artifact_id)
            == raw_content_hash(challenge.statement_bytes),
            challenge_statement.holder_appointment_ref == appointment.appointment_ref,
            holder_statement.family == "epoch",
            holder_statement.proof_domain == challenge_statement.proof_domain,
            holder_statement.authority_purpose == challenge_statement.authority_purpose,
            custody_statement.holder_appointment_ref == appointment.appointment_ref,
            readback_statement.holder_appointment_ref == appointment.appointment_ref,
            retention_statement.holder_appointment_ref == appointment.appointment_ref,
            retention_statement.holder_appointment_content_hash
            == appointment.appointment_content_hash,
            graph.holder_appointment == appointment,
            graph.acceptance_appointment.appointment_ref
            == retention_statement.acceptance_appointment_ref,
            graph.acceptance_appointment.appointment_content_hash
            == retention_statement.acceptance_appointment_content_hash,
            acceptance_appointment_statement is not None,
            acceptance_appointment_statement is not None
            and acceptance_statement.parsed_header.family
            == acceptance_appointment_statement.family,
            acceptance_appointment_statement is not None
            and acceptance_statement.parsed_header.proof_domain
            == acceptance_appointment_statement.proof_domain,
            acceptance_appointment_statement is not None
            and acceptance_statement.authority_purpose
            == acceptance_appointment_statement.authority_purpose,
            acceptance_appointment_statement is not None
            and acceptance_statement.accepting_owner_ref
            == acceptance_appointment_statement.accepting_owner_ref,
            acceptance_appointment_statement is not None
            and acceptance_statement.verifier_provenance_ref
            == str(acceptance_appointment_statement.verifier_provenance_ref.artifact_id),
            acceptance_statement.acceptance_appointment_ref
            == graph.acceptance_appointment.appointment_ref,
            acceptance_statement.acceptance_appointment_content_hash
            == graph.acceptance_appointment.appointment_content_hash,
            acceptance_statement.appointment_verification_receipt_ref
            == graph.acceptance_appointment.verification_receipt_ref,
            acceptance_statement.appointment_verification_receipt_content_hash
            == graph.acceptance_appointment.verification_receipt_content_hash,
            acceptance_statement.trust_snapshot_content_hash
            == semantic_content_hash(
                "anchor-acceptance-trust-snapshot.v1",
                graph.acceptance_appointment.trust_config_bytes,
            ),
            graph.acceptance_evidence.acceptance_statement_evidence.blob_bytes
            == canonical_statement_bytes(acceptance_statement),
            graph.acceptance_evidence.acceptance_receipt_signed_evidence.blob_bytes
            == graph.acceptance_evidence.acceptance_receipt_bytes,
            str(acceptance_statement.bundle_ref.artifact_id)
            == raw_content_hash(graph.bundle_bytes),
            acceptance_statement.bundle_content_hash
            == contract.chronology_bundle_content_hash(graph.bundle_bytes),
            isinstance(bundle_proof, contract.FullPrefixVerified),
            isinstance(bundle_proof, contract.FullPrefixVerified)
            and bundle_proof.parsed_header == acceptance_statement.parsed_header,
            isinstance(bundle_proof, contract.FullPrefixVerified)
            and bundle_proof.bundle_content_hash == acceptance_statement.bundle_content_hash,
            all(isinstance(result, contract.FullPrefixVerified) for result in prior_prefix_proofs),
            all(
                isinstance(result, contract.FullPrefixVerified)
                and result.parsed_header == acceptance_statement.parsed_header
                and result.bundle_content_hash == acceptance_statement.bundle_content_hash
                for result in prior_prefix_proofs
            ),
            len(derived_prefix_ref_ids) == len(set(derived_prefix_ref_ids)),
            len(derived_prefix_keys) == len(set(derived_prefix_keys)),
            all(
                ref in acceptance_statement.prior_acceptance_record_refs
                for ref in derived_prefix_refs
            ),
            bool(acceptance_statement.prior_acceptance_record_refs)
            == bool(acceptance_statement.derived_prior_prefixes),
            str(acceptance_statement.native_reconciliation_ref.artifact_id)
            == raw_content_hash(graph.native_reconciliation_bytes),
            acceptance_statement.parsed_header.requested_query_context_ref
            == acceptance_statement.requested_query_context_ref,
            acceptance_statement.parsed_header.requested_cutoff_ref
            == acceptance_statement.admission_cutoff_ref,
            acceptance_statement.parsed_header.authority_purpose
            == acceptance_statement.authority_purpose,
            retention_statement.bundle_ref == acceptance_statement.bundle_ref,
            retention_statement.bundle_content_hash == acceptance_statement.bundle_content_hash,
            retention_statement.native_reconciliation_ref
            == acceptance_statement.native_reconciliation_ref,
            retention_statement.acceptance_receipt_ref
            == acceptance_receipt_evidence_record.artifact_ref,
            retention_statement.acceptance_receipt_content_hash
            == semantic_content_hash(
                "anchor-acceptance-receipt.v1",
                graph.acceptance_evidence.acceptance_receipt_bytes,
            ),
            retention_statement.prior_acceptance_record_refs
            == acceptance_candidate.prior_acceptance_record_refs,
            acceptance_statement.prior_acceptance_record_refs
            == acceptance_candidate.prior_acceptance_record_refs,
            retention_statement.requested_query_context_ref
            == acceptance_statement.requested_query_context_ref,
            retention_statement.admission_cutoff_ref == acceptance_receipt.admission_cutoff_ref,
            acceptance_receipt.acceptance_digest == acceptance_candidate.acceptance_digest,
            acceptance_candidate.acceptance_digest
            == semantic_content_hash(
                "anchor-acceptance-statement.v1",
                graph.acceptance_evidence.acceptance_statement_evidence.blob_bytes,
            ),
            acceptance_candidate.statement_content_hash == acceptance_candidate.acceptance_digest,
            acceptance_receipt.acceptance_record_content_hash
            == semantic_content_hash(
                "anchor-acceptance-candidate.v1",
                graph.acceptance_evidence.acceptance_record_bytes,
            ),
            str(acceptance_receipt.acceptance_record_ref.artifact_id)
            == raw_content_hash(graph.acceptance_evidence.acceptance_record_bytes),
            acceptance_candidate.statement_artifact_ref
            == acceptance_statement_evidence_record.artifact_ref,
            acceptance_candidate.signed_statement_evidence_ref
            == (
                graph.acceptance_evidence.acceptance_statement_evidence.persisted.evidence_record_ref
            ),
            acceptance_receipt.signed_statement_evidence_ref
            == (
                graph.acceptance_evidence.acceptance_statement_evidence.persisted.evidence_record_ref
            ),
            acceptance_receipt.requested_query_context_ref
            == acceptance_statement.requested_query_context_ref,
            acceptance_receipt.admission_cutoff_ref == acceptance_statement.admission_cutoff_ref,
            acceptance_receipt.lineage_key_ref
            == raw_content_hash(canonical_statement_bytes(acceptance_key)),
            str(acceptance_receipt.lineage_append_receipt_ref.artifact_id)
            == raw_content_hash(graph.acceptance_evidence.lineage_append_receipt_bytes),
            acceptance_receipt.lineage_append_receipt_content_hash
            == semantic_content_hash(
                "anchor-lineage-append.v1",
                graph.acceptance_evidence.lineage_append_receipt_bytes,
            ),
            acceptance_append.acceptance_record_ref == acceptance_receipt.acceptance_record_ref,
            acceptance_append.status in {"appended", "idempotent"},
            acceptance_append.key == acceptance_key,
            acceptance_append.expected_head_refs
            == acceptance_candidate.prior_acceptance_record_refs,
            acceptance_append.previous_head_refs
            == acceptance_candidate.prior_acceptance_record_refs,
            acceptance_append.resulting_head_refs == (acceptance_receipt.acceptance_record_ref,),
            custody_statement.holder_ref == holder_statement.holder_ref,
            readback_statement.holder_ref == holder_statement.holder_ref,
            challenge_statement.package_ref == package_ref,
            custody_statement.package_ref == package_ref,
            readback_statement.package_ref == package_ref,
            challenge_statement.expected_package_content_hash == package_hash,
            custody_statement.package_content_hash == package_hash,
            readback_statement.package_content_hash == package_hash,
            readback_statement.challenge_record_ref == challenge.challenge_record_ref,
            readback_statement.challenge_record_content_hash
            == challenge.challenge_record_content_hash,
            readback_statement.custody_receipt_record_ref
            == challenge_statement.custody_receipt_record_ref,
            challenge_statement.custody_receipt_record_ref == retention.receipt_record_ref,
            readback_statement.custody_receipt_record_raw_bytes_hash
            == challenge_statement.custody_receipt_record_raw_bytes_hash,
            challenge_statement.custody_receipt_record_raw_bytes_hash
            == retention.receipt_record_raw_bytes_hash,
            readback_statement.requested_query_context_ref
            == challenge_statement.requested_query_context_ref,
            readback_statement.object_version_ref
            == challenge_statement.expected_object_version_ref,
            custody_statement.object_version_ref == challenge_statement.expected_object_version_ref,
            retention_statement.requested_query_context_ref
            == challenge_statement.requested_query_context_ref,
            retention_statement.family == acceptance_statement.parsed_header.family,
            retention_statement.authority_purpose == challenge_statement.authority_purpose,
            retention_statement.proof_domain == challenge_statement.proof_domain,
            challenge_statement.lineage_key == acceptance_key,
            challenge_statement.lineage_key.family == challenge_statement.family,
            challenge_statement.lineage_key.proof_domain == challenge_statement.proof_domain,
            challenge_statement.lineage_key.authority_purpose
            == challenge_statement.authority_purpose,
            custody_statement.family == challenge_statement.family,
            readback_statement.family == challenge_statement.family,
            custody_statement.proof_domain == challenge_statement.proof_domain,
            readback_statement.proof_domain == challenge_statement.proof_domain,
            custody_statement.authority_purpose == challenge_statement.authority_purpose,
            readback_statement.authority_purpose == challenge_statement.authority_purpose,
            custody_statement.requested_query_context_ref
            == challenge_statement.requested_query_context_ref,
            custody_statement.retention_policy_ref == readback_statement.retention_policy_ref,
        )
        if not all(bindings):
            return _retention_rejection(
                code="anchor_readback_mismatch",
                subject_ref=readback.receipt_record_ref,
                query_ref=query_ref,
                appointment_ref=appointment.appointment_ref,
                verifier_ref=verifier_ref,
                evidence_refs=evidence_refs,
            )
        return contract.VerifiedAnchorRetention(
            holder_ref=holder_statement.holder_ref,
            custody_receipt_record_ref=retention.receipt_record_ref,
            custody_receipt_record_raw_bytes_hash=(retention.receipt_record_raw_bytes_hash),
            readback_receipt_record_ref=readback.receipt_record_ref,
            readback_receipt_record_raw_bytes_hash=(readback.receipt_record_raw_bytes_hash),
            challenge_record_ref=challenge.challenge_record_ref,
            challenge_record_content_hash=challenge.challenge_record_content_hash,
            package_ref=package_ref,
            package_content_hash=package_hash,
            object_version_ref=readback_statement.object_version_ref,
            retention_policy_ref=readback_statement.retention_policy_ref,
            holder_appointment_ref=appointment.appointment_ref,
            holder_appointment_content_hash=appointment.appointment_content_hash,
            verifier_provenance_ref=verifier_ref,
            signed_evidence_record_refs=evidence_refs,
            requested_query_context_ref=query_ref,
            predicate_class="independently_reconciled",
        )


class InMemoryAnchorReadbackChallengeRepository:
    """Test-only exact-byte challenge store keyed by raw CAS identity."""

    def __init__(self) -> None:
        self._records: dict[str, contract.PersistedAnchorReadbackChallenge] = {}
        self._lock = threading.Lock()

    def persist(
        self, statement: contract.AnchorReadbackChallengeStatement
    ) -> contract.PersistedAnchorReadbackChallenge:
        payload = canonical_statement_bytes(statement)
        ref = _artifact_ref(payload, kind="core.chronology.anchor_readback_challenge")
        persisted = contract.PersistedAnchorReadbackChallenge(
            challenge_record_ref=ref,
            challenge_record_content_hash=semantic_content_hash(
                "anchor-readback-challenge.v1", payload
            ),
            statement_bytes=payload,
        )
        with self._lock:
            previous = self._records.setdefault(str(ref.artifact_id), persisted)
            if previous != persisted:
                raise ValueError("challenge ref re-used for different bytes")
            return previous

    def resolve(
        self, *, challenge_record_ref: ArtifactRef
    ) -> contract.PersistedAnchorReadbackChallenge:
        with self._lock:
            try:
                return self._records[str(challenge_record_ref.artifact_id)]
            except KeyError as exc:
                raise FileNotFoundError(str(challenge_record_ref.artifact_id)) from exc


def build_retention_package(
    graph: contract.AnchorRetentionObjectGraph,
) -> contract.AnchorRetentionPackage:
    """Build raw and semantic package identities from the complete byte graph."""

    payload = canonical_statement_bytes(graph)
    return contract.AnchorRetentionPackage(
        package_ref=raw_content_hash(payload),
        package_content_hash=semantic_content_hash("anchor-retention-package.v1", payload),
        package_bytes=payload,
    )


def verify_retention_package(package: contract.AnchorRetentionPackage) -> bool:
    """Reparse the complete graph and recompute both package identities."""

    try:
        parse_canonical_statement(package.package_bytes, contract.AnchorRetentionObjectGraph)
    except ValueError:
        return False
    return package.package_ref == raw_content_hash(
        package.package_bytes
    ) and package.package_content_hash == semantic_content_hash(
        "anchor-retention-package.v1", package.package_bytes
    )


__all__ = [
    "C3_CANONICAL_CODECS",
    "C3_CONTRACT_MODEL_NAMES",
    "C3_HASH_FIELD_RULES",
    "C3_MODEL_REGISTRY",
    "C3_MODULE_CLASSIFICATION",
    "C3_PRODUCTION_MODULES",
    "AnchorCodec",
    "C3HashFieldRule",
    "C3ModelRegistryRow",
    "ExactAnchorAcceptanceReceiptVerifier",
    "ExactAnchorHolderReceiptVerifier",
    "InMemoryAnchorReadbackChallengeRepository",
    "build_retention_package",
    "canonical_exact_mapping_bytes",
    "canonical_statement_bytes",
    "parse_canonical_statement",
    "raw_content_hash",
    "semantic_content_hash",
    "verify_retention_package",
    "verify_signed_evidence",
]
