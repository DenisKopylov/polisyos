"""Implement the filesystem CAS boundary for blobs, manifests, lineage, and signatures."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import tempfile
import threading
import time
import uuid
from contextlib import AbstractContextManager, contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import datetime
from functools import wraps
from inspect import signature
from pathlib import Path, PurePosixPath
from types import UnionType
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    BinaryIO,
    Literal,
    ParamSpec,
    TypedDict,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

from pydantic import ValidationError

from polisyos.common.canonical import _admit_canon_spec
from polisyos.common.canonical_profile import CanonicalProfileRefusalError

from ..canon import content_hash
from ..canon.canon_json import (
    CanonSpec,
    CanonViolation,
    _validate_core_json_payload_conformance,
    to_canonical_bytes,
)
from ..observability import get_metrics, get_tracer
from ..observability.config import is_hpc_observability_enabled
from . import _atomic_write as _atomic_write_module
from ._atomic_write import (
    AtomicFileDurabilityError as _AtomicFileDurabilityError,
)
from ._atomic_write import (
    AtomicFileWriter as _AtomicFileWriter,
)
from ._atomic_write import (
    ensure_directory_durable as _ensure_directory_durable,
)
from ._integrity_ops import (
    ArtifactBoundedManifestRead,
    ArtifactBoundedManifestReadError,
    ArtifactIntegrityError,
    ArtifactMemberReadBoundsError,
    ArtifactMemberReadIntegrityError,
    ArtifactReadBoundsError,
    ArtifactStoreReadUsage,
    _artifact_store_read_usage,
)
from ._integrity_ops import (
    VerificationReport as VerificationReport,
)
from ._integrity_ops import (
    VerifiedArtifactSnapshot as _VerifiedArtifactSnapshot,
)
from ._integrity_ops import (
    _validate_read_integrity_with_digest as _validate_read_integrity_with_digest,
)
from ._integrity_ops import (
    read_verified_blob as _read_verified_blob,
)
from ._integrity_ops import (
    validate_manifest_identity as _validate_manifest_identity,
)
from ._integrity_ops import (
    validate_read_integrity as _validate_read_integrity,
)
from ._integrity_ops import (
    verify_filesystem_artifact as _verify_filesystem_artifact,
)
from ._layout import CASPathLayout as _CASPathLayout
from ._manifest_lifecycle import ManifestLifecycle as _ManifestLifecycle
from ._signature_ops import (
    sign_all_artifacts as _sign_all_artifacts,
)
from ._signature_ops import (
    sign_artifact as _sign_artifact,
)
from ._signature_ops import (
    verify_all_signatures as _verify_all_signatures,
)
from ._signature_ops import (
    verify_signature as _verify_signature,
)
from ._transfer_ops import (
    ExportReport,
    ImportReport,
    TransferAdmission,
    TransferMemberSnapshot,
)
from ._transfer_ops import (
    ImportPublication as ImportPublication,
)
from ._transfer_ops import (
    artifact_id_from_member as _artifact_id_from_member,
)
from ._transfer_ops import (
    export_subgraph as _export_subgraph,
)
from ._transfer_ops import (
    import_subgraph as _import_subgraph,
)
from ._transfer_ops import (
    member_profile_sha256 as _member_profile_sha256,
)
from ._transfer_ops import (
    normalize_archive_path as _normalize_archive_path,
)
from ._transfer_ops import (
    safe_member_path as _safe_member_path,
)
from ._transfer_ops import (
    snapshot_transfer_member as _snapshot_transfer_member,
)
from ._transfer_ops import (
    validate_transfer_signatures as _validate_transfer_signatures,
)
from .ids import ArtifactID
from .manifest import (
    ArtifactChildReleaseInfo,
    ArtifactManifest,
    ArtifactRef,
    ArtifactTenantContextInfo,
    InputRef,
    _canon_info_for_spec,
    _coerce_input_ref,
    artifact_ref_identity_key,
)
from .manifest import (
    CanonInfo as CanonInfo,
)
from .manifest import (
    artifact_reference_parts as _artifact_reference,
)
from .ownership import (
    ArtifactOwnershipError,
    ArtifactOwnershipIndex,
    ArtifactPublicReadClosureUnavailableError,
    ArtifactReadOnlyUnavailableError,
    ArtifactTransactionPendingError,
    _ArtifactTransactionLease,
)
from .protocol import (
    ArtifactReader,
    _CASStorageAdmission,
    _CASStorageMember,
    _validate_return_selected_profile,
)
from .signing import (
    BulkSigningReport,
    BulkVerificationReport,
    DetachedSignature,
    Ed25519Signer,
    Ed25519Verifier,
    SignatureVerificationResult,
    SignatureVerificationStatus,
    SigningConfig,
    SigningError,
    load_signer_from_config,
)
from .write_contract import ArtifactWriteOptions

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

    from ..observability import MetricsRegistry, PolicyOSTracer
    from ._transfer_ops import CASMemberStream
    from .backends.config import ArtifactStoreConfig
    from .batch_control import BatchAuthorizationLossSignal
    from .owned_json import _PreparedCoreJsonWrite


PutOptions = ArtifactWriteOptions
ArtifactMemberKind = Literal["blob", "manifest", "signature"]
_TransactionalParams = ParamSpec("_TransactionalParams")
_TransactionalResult = TypeVar("_TransactionalResult")
_READ_ONLY_READER_TOKEN = object()


class _ResolvedOwner(TypedDict):
    """One owner identity resolved from a concrete tenant scope."""

    tenant_id: str
    cell_id: str | None


def _artifact_member_kind(member: str) -> ArtifactMemberKind:
    """Map the transfer helper's string domain onto the guarded CAS members."""
    if member == "blob":
        return "blob"
    if member == "manifest":
        return "manifest"
    if member == "signature":
        return "signature"
    raise ValueError("cas_member_kind_invalid")


@dataclass
class _PublicReadSetCapture:
    """Actual successful public CAS operation/ref pairs during one owner replay."""

    store_token: object
    operation_refs: set[tuple[str, str, str, str, str | None]]

    def serialized_operation_refs(self) -> list[dict[str, Any]]:
        return [
            {
                "operation": operation,
                "artifact_id": artifact_id,
                "kind": kind,
                "media_type": media_type,
                "manifest_profile_sha256": profile,
            }
            for operation, artifact_id, kind, media_type, profile in sorted(
                self.operation_refs,
                key=lambda item: (
                    item[0],
                    item[1],
                    item[2],
                    item[3],
                    item[4] or "",
                ),
            )
        ]


@dataclass(frozen=True)
class _GovernedPublicReadCapability:
    """Opaque, one-store capability to replay one record's exact owner reads."""

    store_token: object
    record_id: str
    store_identity: str
    epoch: int
    operation_refs: frozenset[tuple[str, str, str, str, str | None]]


_PUBLIC_READ_CAPTURE: ContextVar[_PublicReadSetCapture | None] = ContextVar(
    "polisyos_public_read_set_capture", default=None
)
_GOVERNED_PUBLIC_READ: ContextVar[_GovernedPublicReadCapability | None] = ContextVar(
    "polisyos_governed_public_read", default=None
)
_PUBLIC_READ_OPERATION: ContextVar[str | None] = ContextVar(
    "polisyos_public_read_operation", default=None
)


def _canonical_artifact_id_sequence(
    artifact_ids: Iterable[ArtifactID],
) -> tuple[ArtifactID, ...]:
    """Return typed IDs unique and ordered by their canonical content identity."""
    return tuple(
        sorted(
            _iter_canonical_artifact_ids(artifact_ids),
            key=lambda artifact_id: artifact_id.hex,
        )
    )


def _iter_canonical_artifact_ids(
    artifact_ids: Iterable[ArtifactID],
) -> Iterator[ArtifactID]:
    """Yield first-seen typed IDs without draining an explicit source."""
    seen: set[str] = set()
    for artifact_id in artifact_ids:
        identity = artifact_id.hex
        if identity in seen:
            continue
        seen.add(identity)
        yield artifact_id


_TRANSACTION_INTENT_SCHEMA = "policyos.artifact_ownership_transaction_intent.v2"
_TRANSACTION_INTENT_SCHEMA_V3 = "policyos.artifact_ownership_transaction_intent.v3"


@dataclass(frozen=True, slots=True)
class ArtifactMemberReceipt:
    """Content identity for bytes streamed from one selected CAS member."""

    member: str
    sha256: str
    byte_size: int


@dataclass(frozen=True, slots=True)
class CASInventoryEntry:
    """One exact selected artifact view in a stable CAS inventory."""

    artifact_ref: ArtifactID | ArtifactRef
    manifest: ArtifactManifest
    blob_sha256: str
    blob_byte_size: int
    manifest_sha256: str
    manifest_byte_size: int


@dataclass(frozen=True, slots=True)
class CASInventorySnapshot:
    """Three-valued inventory verdict with declared scope and evidence inputs."""

    verdict: Literal["pass", "fail", "UNRUN"]
    inputs: tuple[str, ...]
    unresolved_by_construction: tuple[str, ...]
    owner_generation_sha256: str | None
    entries: tuple[CASInventoryEntry, ...]
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class CASManifestInventoryEntry:
    """One exact visible manifest view, without claiming payload verification."""

    artifact_ref: ArtifactID | ArtifactRef
    manifest: ArtifactManifest
    manifest_profile_sha256: str
    manifest_sha256: str
    manifest_byte_size: int


@dataclass(frozen=True, slots=True)
class CASManifestInventorySnapshot:
    """Three-valued stable manifest inventory with payload verification unresolved."""

    verdict: Literal["pass", "fail", "UNRUN"]
    inputs: tuple[str, ...]
    unresolved_by_construction: tuple[str, ...]
    owner_generation_sha256: str | None
    entries: tuple[CASManifestInventoryEntry, ...]
    reason: str | None = None


class _ArtifactStoreReadAttempt:
    """Mutable owner-side builder for immutable bounded-read usage receipts."""

    def __init__(self, *, stage: str) -> None:
        self._usage = _artifact_store_read_usage(
            observed_manifest_selection_bytes=0,
            observed_manifest_verification_bytes=0,
            observed_payload_bytes=0,
            observed_payload_size=None,
            payload_integrity_verified=False,
            failure_stage=stage,
        )

    @property
    def usage(self) -> ArtifactStoreReadUsage:
        """Return the latest immutable owner receipt, including partial attempts."""
        return self._usage

    def begin(self, field: str, *, stage: str) -> None:
        """Mark one transfer as attempted before control enters the read call."""
        if field not in {
            "observed_manifest_selection_bytes",
            "observed_manifest_verification_bytes",
            "observed_payload_bytes",
        }:
            raise ValueError("artifact_store_usage_field_invalid")
        self._usage = replace(self._usage, **{field: None, "failure_stage": stage})

    def complete(self, field: str, value: int, *, stage: str) -> None:
        """Record an exact owner-observed transfer count."""
        if type(value) is not int or value < 0:
            raise ValueError("artifact_store_usage_count_invalid")
        self._usage = replace(self._usage, **{field: value, "failure_stage": stage})

    def set_payload_size(self, value: int, *, stage: str) -> None:
        """Record the owner-checked selected member size before payload reads."""
        if type(value) is not int or value < 0:
            raise ValueError("artifact_store_payload_size_invalid")
        self._usage = replace(self._usage, observed_payload_size=value, failure_stage=stage)

    def stage(self, value: str) -> None:
        """Record the owner phase currently entered before a potentially failing operation."""
        if type(value) is not str or not value:
            raise ValueError("artifact_store_usage_stage_invalid")
        self._usage = replace(self._usage, failure_stage=value)

    def verified(self) -> None:
        """Mark the owner digest and size check as complete."""
        self._usage = replace(
            self._usage,
            payload_integrity_verified=True,
            failure_stage=None,
        )

    def succeeded(self) -> None:
        """Clear the in-progress phase after an exact bounded read succeeds."""
        self._usage = replace(self._usage, failure_stage=None)

    def failed(self, *, stage: str | None = None) -> None:
        """Retain a precise stage when known; never fill an unknown count."""
        self._usage = replace(
            self._usage,
            failure_stage=stage or self._usage.failure_stage or "bounded_read_attempt",
        )

    def cleanup_failed(
        self,
        error: BaseException,
        *,
        stage: str,
        primary_failure: bool,
    ) -> None:
        """Retain close failure separately from any earlier primary refusal."""
        if type(stage) is not str or not stage:
            raise ValueError("artifact_store_cleanup_stage_invalid")
        try:
            cleanup_code = getattr(error, "code", None)
        except Exception:
            cleanup_code = None
        if type(cleanup_code) is not str:
            cleanup_code = None
        failure_stage = self._usage.failure_stage
        if not primary_failure or failure_stage is None:
            failure_stage = stage if not primary_failure else "bounded_member_primary_failure"
        self._usage = replace(
            self._usage,
            failure_stage=failure_stage,
            cleanup_failure_stage=stage,
            cleanup_exception_type=type(error).__name__,
            cleanup_exception_code=cleanup_code,
        )


class _BoundedMemberOpenAttempt(AbstractContextManager["_VerifiedCASMemberStream"]):
    """Context manager whose usage receipt exists even if ``__enter__`` fails."""

    def __init__(
        self,
        store: FileSystemCAS,
        artifact_id: ArtifactRef,
        member: Literal["blob"],
        *,
        max_manifest_bytes: int,
        expected_manifest_sha256: str,
        max_member_bytes: int,
    ) -> None:
        self._store = store
        self._artifact_id = artifact_id
        self._member = member
        self._max_manifest_bytes = max_manifest_bytes
        self._expected_manifest_sha256 = expected_manifest_sha256
        self._max_member_bytes = max_member_bytes
        self._owner_attempt = _ArtifactStoreReadAttempt(stage="bounded_member_preflight")
        self._manager: AbstractContextManager[_VerifiedCASMemberStream] | None = None

    @property
    def usage(self) -> ArtifactStoreReadUsage:
        """Return the owner's exact or explicitly unknown phase measurements."""
        return self._owner_attempt.usage

    def __enter__(self) -> _VerifiedCASMemberStream:
        self._manager = self._store.open_member(
            self._artifact_id,
            self._member,
            max_manifest_bytes=self._max_manifest_bytes,
            expected_manifest_sha256=self._expected_manifest_sha256,
            max_member_bytes=self._max_member_bytes,
            _read_attempt=self._owner_attempt,
        )
        try:
            return self._manager.__enter__()
        except BaseException:
            self._owner_attempt.failed()
            raise

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool | None:
        if self._manager is None:
            self._owner_attempt.failed(stage="bounded_member_context_not_entered")
            return False
        try:
            return self._manager.__exit__(exc_type, exc, traceback)
        except BaseException:
            self._owner_attempt.failed()
            raise


class _VerifiedCASMemberStream:
    """Read-only selected stream with owner-measured bounded-read counters."""

    _CHUNK_SIZE = 1024 * 1024

    def __init__(
        self,
        raw: BinaryIO,
        *,
        member: str,
        expected_sha256: str,
        expected_size: int,
        manifest_verification_bytes: int = 0,
        max_member_bytes: int | None = None,
        opened_stat_signature: tuple[int, int, int, int, int] | None = None,
        read_attempt: _ArtifactStoreReadAttempt | None = None,
    ) -> None:
        self._raw = raw
        self._member = member
        self._expected_sha256 = expected_sha256
        self._expected_size = expected_size
        self._manifest_verification_bytes = manifest_verification_bytes
        self._max_member_bytes = max_member_bytes
        self._opened_stat_signature = opened_stat_signature
        self._read_attempt = read_attempt
        self._digest = hashlib.sha256()
        self._byte_size = 0
        self._receipt: ArtifactMemberReceipt | None = None

    @property
    def size(self) -> int:
        """Return the size recorded for this member while its lease is held."""
        return self._expected_size

    @property
    def member_size_bytes(self) -> int:
        """Return the exact file size reconciled with the selected manifest."""
        return self._expected_size

    @property
    def observed_manifest_verification_bytes(self) -> int:
        """Return selected-manifest bytes transferred by this owner-open."""
        return self._manifest_verification_bytes

    @property
    def observed_payload_bytes(self) -> int:
        """Return exact payload bytes returned to the caller so far."""
        return self._byte_size

    @property
    def payload_integrity_verified(self) -> bool:
        """Return whether this stream has a full owner-verified receipt."""
        return self._receipt is not None

    @property
    def receipt(self) -> ArtifactMemberReceipt:
        """Return the verified content receipt after the complete stream is read."""
        if self._receipt is None:
            raise RuntimeError("cas_member_stream_not_verified")
        return self._receipt

    def _record(self, payload: bytes, *, stage: str) -> None:
        self._digest.update(payload)
        self._byte_size += len(payload)
        if self._read_attempt is not None:
            self._read_attempt.complete(
                "observed_payload_bytes",
                self._byte_size,
                stage=stage,
            )

    def _read_raw(self, size: int, *, stage: str) -> bytes:
        """Read one chunk and retain unknown if the owner call itself fails."""
        if self._read_attempt is not None:
            self._read_attempt.begin("observed_payload_bytes", stage=stage)
        try:
            payload = self._raw.read(size)
        except BaseException:
            if self._read_attempt is not None:
                self._read_attempt.failed(stage=stage)
            raise
        if type(payload) is not bytes:
            if self._read_attempt is not None:
                self._read_attempt.failed(stage=stage)
            return payload
        if self._read_attempt is not None:
            self._read_attempt.complete(
                "observed_payload_bytes",
                self._byte_size + len(payload),
                stage=stage,
            )
        return payload

    def _integrity_error(self, code: str) -> ArtifactMemberReadIntegrityError:
        return ArtifactMemberReadIntegrityError(
            code,
            observed_manifest_verification_bytes=self._manifest_verification_bytes,
            observed_payload_bytes=self._byte_size,
            observed_payload_size=self._expected_size,
            payload_integrity_verified=False,
        )

    def read(self, size: int = -1) -> bytes:
        """Read no more than the remaining manifest- and caller-bounded size."""
        if self._receipt is not None:
            return b""
        if size == 0:
            return b""
        if self._byte_size >= self._expected_size:
            self.finish()
            return b""
        limit = self._CHUNK_SIZE if size is None or size < 0 else min(size, self._CHUNK_SIZE)
        limit = min(limit, self._expected_size - self._byte_size)
        if self._max_member_bytes is not None:
            if self._read_attempt is not None:
                self._read_attempt.stage("bounded_payload_bounds_validation")
            remaining = self._max_member_bytes - self._byte_size
            if remaining <= 0:
                raise ArtifactMemberReadBoundsError(
                    observed_member_size=self._expected_size,
                    max_member_bytes=self._max_member_bytes,
                    observed_manifest_verification_bytes=self._manifest_verification_bytes,
                    observed_payload_bytes=self._byte_size,
                )
            limit = min(limit, remaining)
        payload = self._read_raw(limit, stage="bounded_payload_read")
        if payload:
            self._record(payload, stage="bounded_payload_read")
            if self._max_member_bytes is not None:
                if self._read_attempt is not None:
                    self._read_attempt.stage("bounded_payload_bounds_validation")
                if self._byte_size > self._max_member_bytes:
                    raise ArtifactMemberReadBoundsError(
                        observed_member_size=self._expected_size,
                        max_member_bytes=self._max_member_bytes,
                        observed_manifest_verification_bytes=self._manifest_verification_bytes,
                        observed_payload_bytes=self._byte_size,
                    )
            if self._byte_size == self._expected_size:
                self.finish()
        else:
            self.finish()
        return payload

    def finish(self) -> ArtifactMemberReceipt:
        """Read only the manifest-sized remainder and verify before lease release."""
        if self._receipt is not None:
            return self._receipt
        if self._max_member_bytes is None:
            while payload := self._read_raw(
                self._CHUNK_SIZE,
                stage="bounded_payload_finish_read",
            ):
                self._record(payload, stage="bounded_payload_finish_read")
        else:
            while self._byte_size < self._expected_size:
                remaining = min(
                    self._CHUNK_SIZE,
                    self._max_member_bytes - self._byte_size,
                    self._expected_size - self._byte_size,
                )
                if remaining <= 0:
                    if self._read_attempt is not None:
                        self._read_attempt.stage("bounded_payload_bounds_validation")
                    raise ArtifactMemberReadBoundsError(
                        observed_member_size=self._expected_size,
                        max_member_bytes=self._max_member_bytes,
                        observed_manifest_verification_bytes=self._manifest_verification_bytes,
                        observed_payload_bytes=self._byte_size,
                    )
                payload = self._read_raw(remaining, stage="bounded_payload_finish_read")
                if not payload:
                    raise self._integrity_error("cas_member_stream_ended_early")
                self._record(payload, stage="bounded_payload_finish_read")
        if self._read_attempt is not None:
            self._read_attempt.stage("bounded_payload_finish_validation")
        if self._max_member_bytes is not None and self._opened_stat_signature is not None:
            current = os.fstat(self._raw.fileno())
            signature = (
                current.st_dev,
                current.st_ino,
                current.st_size,
                current.st_mtime_ns,
                current.st_ctime_ns,
            )
            if signature != self._opened_stat_signature:
                raise self._integrity_error("cas_member_changed_while_streaming")
        actual = self._digest.hexdigest()
        if self._byte_size != self._expected_size or actual != self._expected_sha256:
            if self._max_member_bytes is not None:
                raise self._integrity_error("cas_member_integrity_mismatch")
            raise ArtifactIntegrityError(f"CAS member changed while streaming: {self._member}")
        self._receipt = ArtifactMemberReceipt(
            member=self._member,
            sha256=actual,
            byte_size=self._byte_size,
        )
        if self._read_attempt is not None:
            self._read_attempt.verified()
        return self._receipt


def _default_tracer() -> PolicyOSTracer:
    return get_tracer()


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


def _file_content_hash(path: Path) -> str:
    """Hash a CAS blob from disk without buffering the complete payload."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _current_access_scope() -> object | None:
    try:
        from polisyos.core.security.tenant_context import (
            get_current_access_scope_or_none,
        )
    except ImportError:
        return None
    return get_current_access_scope_or_none()


def _current_tenant_id() -> str | None:
    try:
        from polisyos.core.security.tenant_context import get_current_tenant_id_or_none
    except ImportError:
        return None
    return get_current_tenant_id_or_none()


def _current_cell_id() -> str | None:
    try:
        from polisyos.core.security.tenant_context import get_current_cell_id
    except ImportError:
        return None
    return get_current_cell_id()


def _revalidate_input_ref(value: InputRef) -> InputRef:
    """Revalidate an existing input edge from its raw model fields."""
    if type(value) is not InputRef:
        raise TypeError("transactional CAS input selector requires InputRef")
    fields = dict(value.__dict__)
    if set(fields) != {"artifact_id", "role", "manifest_profile_sha256"}:
        raise ValueError("transactional CAS input selector fields are invalid")
    raw_artifact_id = fields.get("artifact_id")
    if isinstance(raw_artifact_id, ArtifactID):
        raw_artifact_id = raw_artifact_id.root
    artifact_id = ArtifactID.model_validate(raw_artifact_id)
    role = fields.get("role")
    if type(role) is not str:
        raise TypeError("transactional CAS input role must be a string")
    profile = fields.get("manifest_profile_sha256")
    if profile is not None and (
        type(profile) is not str or re.fullmatch(r"sha256:[0-9a-f]{64}", profile) is None
    ):
        raise ValueError("manifest_profile_sha256 must be sha256:<64 lowercase hex>")
    return InputRef.model_validate(
        {
            "artifact_id": artifact_id,
            "role": role,
            "manifest_profile_sha256": profile,
        }
    )


def _transactional_read_selector(
    value: object,
) -> ArtifactID | ArtifactRef | InputRef | str:
    """Normalize compatible selector models through the existing Core adapter."""
    if type(value) is InputRef:
        return _revalidate_input_ref(value)
    if isinstance(value, (ArtifactID, ArtifactRef, str)):
        return value

    from .ir_adapter import _coerce_core_artifact_selector

    try:
        return _coerce_core_artifact_selector(value)
    except (TypeError, ValueError) as exc:
        raise TypeError("transactional CAS read requires an artifact selector") from exc


def _selector_annotation_accepts_full_reference(annotation: object) -> bool:
    """Return whether a reader's declared selector union accepts a Core ref."""
    if annotation is ArtifactRef:
        return True
    origin = get_origin(annotation)
    if origin is Annotated:
        arguments = get_args(annotation)
        return bool(arguments) and _selector_annotation_accepts_full_reference(arguments[0])
    if origin in (Union, UnionType):
        return any(
            _selector_annotation_accepts_full_reference(argument)
            for argument in get_args(annotation)
        )
    return False


def _selector_annotation_accepts_input_reference(annotation: object) -> bool:
    """Return whether a reader's declared selector accepts an input edge."""
    if annotation is InputRef:
        return True
    origin = get_origin(annotation)
    if origin is Annotated:
        arguments = get_args(annotation)
        return bool(arguments) and _selector_annotation_accepts_input_reference(arguments[0])
    if origin in (Union, UnionType):
        return any(
            _selector_annotation_accepts_input_reference(argument)
            for argument in get_args(annotation)
        )
    return False


def _transactional_read_profile(
    value: object,
    *,
    parameter_name: str,
    allow_none: bool,
    selected_profile: str | None,
) -> str | None:
    """Validate an explicit profile and reconcile it with a selected ref."""
    if value is None:
        if not allow_none:
            raise TypeError(f"transactional CAS read {parameter_name} must be a string")
        return selected_profile
    if not isinstance(value, str):
        raise TypeError(f"transactional CAS read {parameter_name} must be a string")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None:
        raise ValueError(f"{parameter_name} must be sha256:<64 lowercase hex>")
    if selected_profile is not None and selected_profile != value:
        raise ValueError("conflicting manifest profile selectors")
    return value


def _transactional_read(
    *,
    profile_argument_index: int | None = None,
    signature_surface: bool = False,
    manifest_bytes_result: bool = False,
) -> Callable[
    [Callable[_TransactionalParams, _TransactionalResult]],
    Callable[_TransactionalParams, _TransactionalResult],
]:
    """Hold a shared artifact lease across an entire public CAS read."""

    def decorate(
        method: Callable[_TransactionalParams, _TransactionalResult],
    ) -> Callable[_TransactionalParams, _TransactionalResult]:
        method_signature = signature(method)
        method_parameters = tuple(method_signature.parameters.values())
        if len(method_parameters) < 2:
            raise TypeError("transactional CAS read requires receiver and selector parameters")
        receiver_parameter_name = method_parameters[0].name
        selector_parameter = method_parameters[1]
        selector_parameter_name = selector_parameter.name
        try:
            selector_annotation = get_type_hints(method).get(selector_parameter_name)
        except (NameError, TypeError) as exc:
            raise TypeError("transactional CAS read selector annotation is not resolvable") from exc
        selector_accepts_full_reference = _selector_annotation_accepts_full_reference(
            selector_annotation
        )
        selector_position = 1
        profile_position = (
            selector_position + 1 + profile_argument_index
            if profile_argument_index is not None
            else None
        )
        if profile_position is not None and profile_position >= len(method_parameters):
            raise TypeError("transactional CAS read profile parameter is missing")
        profile_parameter = (
            method_parameters[profile_position] if profile_position is not None else None
        )

        @wraps(method)
        def wrapped(
            *args: _TransactionalParams.args,
            **kwargs: _TransactionalParams.kwargs,
        ) -> _TransactionalResult:
            bound_call = method_signature.bind(*args, **kwargs)
            arguments = bound_call.arguments
            store_value: object = arguments[receiver_parameter_name]
            raw_selector_value: object = arguments[selector_parameter_name]
            if not isinstance(store_value, FileSystemCAS):
                raise TypeError("transactional CAS read requires a FileSystemCAS receiver")
            selector_value = _transactional_read_selector(raw_selector_value)
            if isinstance(selector_value, ArtifactRef) and not selector_accepts_full_reference:
                raise TypeError(
                    "transactional CAS read selector contract "
                    "does not accept full artifact references"
                )
            if isinstance(selector_value, InputRef):
                if not _selector_annotation_accepts_input_reference(selector_annotation):
                    raise TypeError(
                        "transactional CAS read selector contract does not accept input references"
                    )
                aid = selector_value.artifact_id
                profile_sha256 = selector_value.manifest_profile_sha256
            else:
                aid, profile_sha256, _ref = _artifact_reference(selector_value)
            if profile_parameter is not None:
                requested_profile = arguments.get(profile_parameter.name, profile_sha256)
                profile_sha256 = _transactional_read_profile(
                    requested_profile,
                    parameter_name=profile_parameter.name,
                    allow_none=profile_parameter.default is None,
                    selected_profile=profile_sha256,
                )
            transactional_method: Callable[..., _TransactionalResult] = method
            store = store_value
            with store._coordinator.artifact_lease(
                aid,
                exclusive=False,
                create_lock_files=not store._read_only,
            ):
                store._ownership_index.require_no_pending_transaction(
                    aid,
                    manifest_profile_sha256=profile_sha256,
                    signature_profile=(profile_sha256 or "default") if signature_surface else None,
                )
                store._require_enrolled_child_release(aid, profile_sha256)
                operation_token = _PUBLIC_READ_OPERATION.set(method.__name__)
                try:
                    if selector_value is raw_selector_value:
                        result = transactional_method(*args, **kwargs)
                    elif len(args) > selector_position:
                        normalized_args = (
                            *args[:selector_position],
                            selector_value,
                            *args[selector_position + 1 :],
                        )
                        result = transactional_method(*normalized_args, **kwargs)
                    else:
                        normalized_kwargs = {
                            **kwargs,
                            selector_parameter_name: selector_value,
                        }
                        result = transactional_method(*args, **normalized_kwargs)
                finally:
                    _PUBLIC_READ_OPERATION.reset(operation_token)
                store._require_child_read_result(
                    result,
                    artifact_id=aid,
                    selected_profile=profile_sha256,
                    manifest_bytes_result=manifest_bytes_result,
                )
                store._capture_public_read_operation(method.__name__, selector_value)
                return result

        return wrapped

    return decorate


class FileSystemCAS:
    """Store immutable artifacts in a sharded filesystem content-addressed store.

    The stable on-disk ABI is:
    - `<root>/artifacts/sha256/ab/cd/<hex>.blob`
    - `<root>/artifacts/sha256/ab/cd/<hex>.manifest.json`
    - `<root>/artifacts/sha256/ab/cd/<hex>.sig` for optional detached signatures

    `put_json` and `put_bytes` derive `ArtifactID` from payload bytes, persist an
    `ArtifactManifest` sidecar, and optionally sign on write according to
    `SigningConfig`. Read/verify helpers raise standard Python IO/validation
    exceptions for missing or malformed artifacts.
    """

    CONNECTOR_CACHE_NAMESPACE = "connector_cache"

    def __init__(
        self,
        root: Path,
        *,
        signing_config: SigningConfig | None = None,
        metrics: MetricsRegistry | None = None,
        tracer: PolicyOSTracer | None = None,
        tenant_id: str | None = None,
        cell_id: str | None = None,
        ownership_enforced: bool | None = None,
        ownership_requires_scope: bool = True,
        ownership_index: ArtifactOwnershipIndex | None = None,
    ) -> None:
        self._initialize(
            root,
            signing_config=signing_config,
            metrics=metrics,
            tracer=tracer,
            tenant_id=tenant_id,
            cell_id=cell_id,
            ownership_enforced=ownership_enforced,
            ownership_requires_scope=ownership_requires_scope,
            ownership_index=ownership_index,
            read_only=False,
        )

    def has_stock_component_types(self) -> bool:
        """Check the exact stock component classes of this filesystem CAS.

        This checks type shape only; callers must independently establish
        configuration, filesystem relations, access enforcement, and authority.

        Returns:
            Whether this owner and its five components use the exact stock types.
        """
        from .ownership import _RootTransactionCoordinator

        return (
            type(self) is FileSystemCAS
            and type(self._ownership_index) is ArtifactOwnershipIndex
            and type(self._coordinator) is _RootTransactionCoordinator
            and type(self._layout) is _CASPathLayout
            and type(self._files) is _AtomicFileWriter
            and type(self._manifests) is _ManifestLifecycle
        )

    @classmethod
    def open_existing_read_only(cls, root: Path) -> ReadOnlyFileSystemCAS:
        """Open an existing CAS through only content-validating read methods.

        The returned handle refuses when its existing root, layout, or root
        transaction lock cannot be opened without creating filesystem state.
        """
        store = cls.__new__(cls)
        store._initialize(
            root,
            signing_config=None,
            metrics=None,
            tracer=None,
            tenant_id=None,
            cell_id=None,
            ownership_enforced=False,
            ownership_requires_scope=True,
            ownership_index=None,
            read_only=True,
        )
        store._coordinator.validate_existing_root_lock()
        return ReadOnlyFileSystemCAS(store, _token=_READ_ONLY_READER_TOKEN)

    def _initialize(
        self,
        root: Path,
        *,
        signing_config: SigningConfig | None,
        metrics: MetricsRegistry | None,
        tracer: PolicyOSTracer | None,
        tenant_id: str | None,
        cell_id: str | None,
        ownership_enforced: bool | None,
        ownership_requires_scope: bool,
        ownership_index: ArtifactOwnershipIndex | None,
        read_only: bool,
    ) -> None:
        self._read_only = read_only
        self._child_staging_infos: set[ArtifactChildReleaseInfo] = set()
        requested_root = Path(root)
        if read_only:
            if requested_root.is_symlink() or not requested_root.is_dir():
                raise ArtifactReadOnlyUnavailableError("cas_root_missing_or_invalid")
            canonical_root = requested_root.resolve(strict=True)
        else:
            requested_root.mkdir(parents=True, exist_ok=True)
            canonical_root = requested_root.resolve(strict=True)
        self._ownership_index = ownership_index or ArtifactOwnershipIndex(
            canonical_root,
            read_only=read_only,
        )
        if self._ownership_index.root != canonical_root:
            raise ValueError("filesystem_cas_ownership_root_mismatch")
        self.root = canonical_root
        self._public_read_store_identity = (
            "sha256:" + hashlib.sha256(os.fsencode(str(self.root))).hexdigest()
        )
        self._public_read_store_token = object()
        self._governed_public_read_owner_tokens: set[object] = set()
        self._coordinator = self._ownership_index._coordinator
        self._layout = _CASPathLayout(self.root)
        self.base = self._layout.base
        if read_only:
            if (
                self.base.is_symlink()
                or not self.base.is_dir()
                or self._ownership_index._path_has_symlink_component(self.base)
            ):
                raise ArtifactReadOnlyUnavailableError("cas_layout_missing_or_invalid")
        else:
            self.base.mkdir(parents=True, exist_ok=True)
        self._files = _AtomicFileWriter()
        self._manifests = _ManifestLifecycle()
        if read_only:
            self._tracer = None
            self._metrics = None
        else:
            observability_enabled = is_hpc_observability_enabled()
            self._tracer = (
                tracer
                if tracer is not None
                else (_default_tracer() if observability_enabled else None)
            )
            self._metrics = (
                metrics
                if metrics is not None
                else (_default_metrics() if observability_enabled else None)
            )
        self._hpc_enabled = self._tracer is not None or self._metrics is not None
        self._signing_config = signing_config or (
            SigningConfig() if read_only else SigningConfig.from_env()
        )
        self._default_signer: Ed25519Signer | None = None
        self._signer_lock = threading.Lock()
        self._storage_admission: _CASStorageAdmission | None = None
        self._tenant_id = tenant_id
        self._cell_id = cell_id
        self._ownership_enforced = (
            tenant_id is not None if ownership_enforced is None else bool(ownership_enforced)
        )
        self._ownership_requires_scope = bool(ownership_requires_scope)
        if not read_only:
            self._ownership_index.recover_orphan_stages()

    def _configure_child_staging(self, info: object, *, token: object) -> None:
        """Admit Core custody's private store view, never a served-root bypass."""
        from .child_release import _CHILD_STAGING_TOKEN, child_store_identity
        from .manifest import ArtifactChildReleaseInfo

        if token is not _CHILD_STAGING_TOKEN or type(info) is not ArtifactChildReleaseInfo:
            raise TypeError("child staging is configured by Core custody")
        if info.served_store_identity == child_store_identity(self.root):
            raise ValueError("a served store cannot use a private staging grant")
        self._child_staging_infos.add(info)

    def _private_child_infos(self) -> tuple[ArtifactChildReleaseInfo, ...]:
        return tuple(self._child_staging_infos)

    def _require_enrolled_child_release(
        self, artifact_id: ArtifactID, profile_sha256: str | None
    ) -> None:
        from .child_release import require_enrolled_child_release

        require_enrolled_child_release(
            self.root,
            artifact_id,
            profile_sha256,
            private_infos=self._private_child_infos(),
        )

    def _require_child_manifest_release(self, manifest: ArtifactManifest) -> None:
        from .child_release import require_child_release_manifest

        require_child_release_manifest(
            self.root,
            manifest,
            private_infos=self._private_child_infos(),
        )

    def _require_child_read_result(
        self,
        value: object,
        *,
        artifact_id: ArtifactID,
        selected_profile: str | None,
        manifest_bytes_result: bool,
    ) -> None:
        """Gate actual emitted sidecars without an unmetered manifest preread."""
        from .child_release import require_child_release_raw

        if isinstance(value, ArtifactManifest):
            self._require_child_manifest_release(value)
        elif isinstance(value, ArtifactBoundedManifestRead):
            require_child_release_raw(
                self.root,
                value.raw_manifest_bytes,
                private_infos=self._private_child_infos(),
            )
        elif isinstance(value, _VerifiedArtifactSnapshot):
            require_child_release_raw(
                self.root,
                value.manifest_bytes,
                private_infos=self._private_child_infos(),
            )
        elif manifest_bytes_result:
            if type(value) is not bytes:
                raise TypeError("manifest-byte read returned a non-byte result")
            require_child_release_raw(
                self.root,
                value,
                private_infos=self._private_child_infos(),
            )
        elif type(value) is bool and value:
            # Existence/signature probes must not reveal a pending child view.
            if selected_profile is None:
                self.get_manifest(artifact_id)
            else:
                self.get_manifest_by_profile(str(artifact_id), selected_profile)

    @contextmanager
    def _capture_public_read_set(self) -> Iterator[_PublicReadSetCapture]:
        """Capture successful typed CAS reads made by this exact store instance."""
        if _PUBLIC_READ_CAPTURE.get() is not None:
            raise RuntimeError("nested_public_read_set_capture_not_supported")
        capture = _PublicReadSetCapture(
            store_token=self._public_read_store_token,
            operation_refs=set(),
        )
        token = _PUBLIC_READ_CAPTURE.set(capture)
        try:
            yield capture
        finally:
            _PUBLIC_READ_CAPTURE.reset(token)

    def _register_governed_public_read_owner(self) -> object:
        """Bind a private owner token to this exact CAS instance."""
        token = object()
        self._governed_public_read_owner_tokens.add(token)
        return token

    @contextmanager
    def _authorize_governed_public_read(
        self,
        record_id: str,
        *,
        owner_token: object,
    ) -> Iterator[_GovernedPublicReadCapability]:
        """Install one current owner-index closure for the exact store and record."""
        if (
            not self._ownership_enforced
            or owner_token not in self._governed_public_read_owner_tokens
        ):
            raise ArtifactPublicReadClosureUnavailableError(
                record_id,
                operation="owner_read_capability",
            )
        if _GOVERNED_PUBLIC_READ.get() is not None:
            raise RuntimeError("nested_governed_public_read_not_supported")
        closure = self._ownership_index._get_public_read_closure(record_id)
        if (
            closure is None
            or closure["status"] != "active"
            or closure["purpose"] != "governed_public_record_replay"
            or closure["audience"] != "governed_public_owner_internal"
            or closure["store_identity"] != self._public_read_store_identity
        ):
            raise ArtifactPublicReadClosureUnavailableError(
                record_id,
                operation="owner_read_capability",
            )
        operation_refs = frozenset(
            (
                row["operation"],
                row["artifact_id"],
                row["kind"],
                row["media_type"],
                row["manifest_profile_sha256"],
            )
            for row in closure["operation_refs"]
        )
        capability = _GovernedPublicReadCapability(
            store_token=self._public_read_store_token,
            record_id=record_id,
            store_identity=self._public_read_store_identity,
            epoch=closure["epoch"],
            operation_refs=operation_refs,
        )
        token = _GOVERNED_PUBLIC_READ.set(capability)
        try:
            yield capability
        finally:
            _GOVERNED_PUBLIC_READ.reset(token)

    def _record_governed_public_read_closure(
        self,
        record_id: str,
        capture: _PublicReadSetCapture,
        *,
        owner_token: object,
    ) -> dict[str, Any]:
        """Persist only a read set captured from this store's successful owner calls."""
        if (
            capture.store_token is not self._public_read_store_token
            or owner_token not in self._governed_public_read_owner_tokens
        ):
            raise ValueError("public_read_capture_store_mismatch")
        return self._ownership_index._record_public_read_closure(
            record_id,
            store_identity=self._public_read_store_identity,
            operation_refs=capture.serialized_operation_refs(),
        )

    def _revoke_governed_public_read_closure(
        self,
        record_id: str,
        *,
        owner_token: object,
    ) -> bool:
        """Withdraw one record's current closure through the canonical owner index."""
        if owner_token not in self._governed_public_read_owner_tokens:
            raise ArtifactPublicReadClosureUnavailableError(
                record_id,
                operation="closure_withdrawal",
            )
        return self._ownership_index._revoke_public_read_closure(record_id)

    def _capture_public_read_operation(
        self,
        operation: str,
        artifact_id: ArtifactID | ArtifactRef | str,
    ) -> None:
        capture = _PUBLIC_READ_CAPTURE.get()
        if capture is None or capture.store_token is not self._public_read_store_token:
            return
        _aid, _profile, ref = _artifact_reference(artifact_id)
        if ref is None:
            raise ValueError("public_read_capture_requires_full_artifact_ref")
        identity = artifact_ref_identity_key(ref)
        capture.operation_refs.add((operation, *identity))

    def _require_governed_public_read(
        self,
        artifact_id: ArtifactID,
        manifest_profile_sha256: str | None,
        *,
        operation: str,
        ref: ArtifactRef | None,
    ) -> None:
        capability = _GOVERNED_PUBLIC_READ.get()
        current_operation = _PUBLIC_READ_OPERATION.get()
        if (
            capability is None
            or capability.store_token is not self._public_read_store_token
            or ref is None
            or current_operation is None
        ):
            raise ArtifactPublicReadClosureUnavailableError(
                capability.record_id if capability is not None else "",
                operation=operation,
            )
        identity = artifact_ref_identity_key(ref)
        if (
            identity[0] != str(artifact_id)
            or identity[3] != manifest_profile_sha256
            or current_operation
            not in {row[0] for row in capability.operation_refs if row[1:] == identity}
            or not self._ownership_index._public_read_closure_matches(
                capability.record_id,
                store_identity=capability.store_identity,
                epoch=capability.epoch,
                operation=current_operation,
                ref_identity=identity,
            )
        ):
            raise ArtifactPublicReadClosureUnavailableError(
                capability.record_id,
                operation=operation,
            )

    def _paths(self, artifact_id: ArtifactID) -> tuple[Path, Path]:
        return self._layout.paths(artifact_id)

    def _member_path(
        self,
        artifact_id: ArtifactID,
        member: ArtifactMemberKind,
        manifest_profile_sha256: str | None,
    ) -> Path:
        if member == "blob":
            return self._paths(artifact_id)[0]
        if member == "manifest":
            return self._manifest_path_for_ref(artifact_id, manifest_profile_sha256)
        if member == "signature":
            return self._sig_path(artifact_id, manifest_profile_sha256)
        raise ValueError("cas_member_kind_invalid")

    def _member_name(
        self,
        artifact_id: ArtifactID,
        member: ArtifactMemberKind,
        manifest_profile_sha256: str | None,
    ) -> str:
        """Return a stable archive locator without exposing the local path."""
        path = self._member_path(artifact_id, member, manifest_profile_sha256)
        return path.relative_to(self.root).as_posix()

    @contextmanager
    def open_member(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        member: ArtifactMemberKind,
        *,
        max_manifest_bytes: int | None = None,
        expected_manifest_sha256: str | None = None,
        max_member_bytes: int | None = None,
        _read_attempt: _ArtifactStoreReadAttempt | None = None,
    ) -> Iterator[_VerifiedCASMemberStream]:
        """Stream one selected member under its read lease with bounded memory.

        The context yields a read-only object with no filesystem path or file
        descriptor interface. The complete member is hashed before the lease is
        released, even if the caller reads only a prefix.
        """
        if max_manifest_bytes is not None and (
            type(max_manifest_bytes) is not int or max_manifest_bytes < 1
        ):
            raise ValueError("max_manifest_bytes must be a positive integer")
        if expected_manifest_sha256 is not None and (
            max_manifest_bytes is None
            or type(expected_manifest_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256) is None
        ):
            raise ValueError("expected_manifest_sha256 requires a bounded manifest read")
        if max_member_bytes is not None and (
            member != "blob"
            or type(max_member_bytes) is not int
            or max_member_bytes < 1
            or max_manifest_bytes is None
            or expected_manifest_sha256 is None
        ):
            raise ValueError("max_member_bytes requires a bounded exact-selected blob read")
        if _read_attempt is not None:
            _read_attempt.stage("bounded_member_open_preflight")
        aid, profile_sha256, ref = _artifact_reference(artifact_id)
        with self._coordinator.artifact_lease(
            aid,
            exclusive=False,
            create_lock_files=not self._read_only,
        ):
            self._ownership_index.require_no_pending_transaction(
                aid,
                manifest_profile_sha256=profile_sha256,
                signature_profile=(profile_sha256 or "default") if member == "signature" else None,
            )
            self._require_enrolled_child_release(aid, profile_sha256)
            self._require_blob_owner(aid, operation=f"read_{member}", ref=ref)
            if profile_sha256 is None:
                self._require_default_manifest_access(
                    aid,
                    operation=f"read_{member}",
                    ref=ref,
                )
            else:
                self._require_manifest_view_owner(
                    aid,
                    profile_sha256,
                    operation=f"read_{member}_manifest",
                    ref=ref,
                )

            manifest_path = self._manifest_path_for_ref(aid, profile_sha256)
            if self._ownership_index._path_has_symlink_component(manifest_path):
                raise ArtifactIntegrityError("CAS manifest path crosses a symlink")
            if max_manifest_bytes is None:
                manifest_bytes = manifest_path.read_bytes()
            else:
                manifest_bytes = self._read_cas_file_no_follow(
                    manifest_path,
                    member="manifest",
                    max_bytes=max_manifest_bytes,
                    raise_read_limit=True,
                    _read_attempt=_read_attempt,
                    _usage_field="observed_manifest_verification_bytes",
                    _usage_stage="manifest_verification_transfer",
                )
            if _read_attempt is not None:
                _read_attempt.complete(
                    "observed_manifest_verification_bytes",
                    len(manifest_bytes),
                    stage="manifest_verification_complete",
                )
            if expected_manifest_sha256 is not None and (
                hashlib.sha256(manifest_bytes).hexdigest() != expected_manifest_sha256
            ):
                if max_member_bytes is not None:
                    raise ArtifactMemberReadIntegrityError(
                        "cas_member_manifest_changed",
                        observed_manifest_verification_bytes=len(manifest_bytes),
                        observed_payload_bytes=0,
                        observed_payload_size=None,
                    )
                raise ArtifactIntegrityError(
                    f"Selected manifest changed between bounded read and member open for {aid}"
                )
            if _read_attempt is not None:
                _read_attempt.stage("bounded_manifest_verification")
            manifest = ArtifactManifest.model_validate_json(manifest_bytes)
            _validate_manifest_identity(aid, manifest)
            if profile_sha256 is not None and (
                self._manifests.profile_sha256(manifest) != profile_sha256
            ):
                raise ArtifactIntegrityError(f"Selected manifest profile mismatch for {aid}")
            if ref is not None and (
                ref.kind != manifest.kind or ref.media_type != manifest.media_type
            ):
                raise ArtifactIntegrityError(
                    f"Artifact reference type does not match selected manifest for {aid}"
                )

            self._require_child_manifest_release(manifest)
            selected_path = self._member_path(aid, member, profile_sha256)
            if _read_attempt is not None:
                _read_attempt.stage("bounded_member_open_status")
            if self._ownership_index._path_has_symlink_component(selected_path):
                raise ArtifactIntegrityError("CAS member path crosses a symlink")
            descriptor = os.open(
                selected_path,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            )
            primary_error: BaseException | None = None
            try:
                opened_stat = os.fstat(descriptor)
                if not stat.S_ISREG(opened_stat.st_mode):
                    raise ArtifactIntegrityError("CAS member is not a regular file")
                if _read_attempt is not None:
                    _read_attempt.set_payload_size(
                        opened_stat.st_size,
                        stage="bounded_member_status_checked",
                    )

                if member == "blob":
                    expected_sha256 = aid.hex
                    expected_size = manifest.byte_size
                elif member == "manifest":
                    expected_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
                    expected_size = len(manifest_bytes)
                elif member == "signature":
                    if opened_stat.st_size > 1024 * 1024:
                        raise ArtifactIntegrityError("CAS signature member exceeds its size bound")
                    signature_bytes = os.read(descriptor, opened_stat.st_size + 1)
                    if len(signature_bytes) != opened_stat.st_size:
                        raise ArtifactIntegrityError("CAS signature changed while opening")
                    signature = DetachedSignature.model_validate_json(signature_bytes)
                    if (
                        signature.artifact_id != str(aid)
                        or signature.statement.blob_sha256 != aid.hex
                        or signature.statement.manifest_sha256
                        != hashlib.sha256(manifest_bytes).hexdigest()
                    ):
                        raise ArtifactIntegrityError(f"Signature binding mismatch for {aid}")
                    expected_sha256 = hashlib.sha256(signature_bytes).hexdigest()
                    expected_size = len(signature_bytes)
                    os.lseek(descriptor, 0, os.SEEK_SET)
                else:
                    raise ValueError("cas_member_kind_invalid")

                if _read_attempt is not None:
                    _read_attempt.stage("bounded_member_size_validation")
                if opened_stat.st_size != expected_size:
                    if max_member_bytes is not None:
                        raise ArtifactMemberReadIntegrityError(
                            "cas_member_size_mismatch",
                            observed_manifest_verification_bytes=len(manifest_bytes),
                            observed_payload_bytes=0,
                            observed_payload_size=opened_stat.st_size,
                        )
                    raise ArtifactIntegrityError(f"CAS member size mismatch: {aid} {member}")
                if _read_attempt is not None:
                    _read_attempt.stage("bounded_member_bounds_validation")
                if max_member_bytes is not None and opened_stat.st_size > max_member_bytes:
                    raise ArtifactMemberReadBoundsError(
                        observed_member_size=opened_stat.st_size,
                        max_member_bytes=max_member_bytes,
                        observed_manifest_verification_bytes=len(manifest_bytes),
                    )
                opened_stat_signature = (
                    opened_stat.st_dev,
                    opened_stat.st_ino,
                    opened_stat.st_size,
                    opened_stat.st_mtime_ns,
                    opened_stat.st_ctime_ns,
                )
                raw = os.fdopen(
                    descriptor,
                    "rb",
                    buffering=0 if max_member_bytes is not None else -1,
                )
                descriptor = -1
                stream = _VerifiedCASMemberStream(
                    raw,
                    member=self._member_name(aid, member, profile_sha256),
                    expected_sha256=expected_sha256,
                    expected_size=expected_size,
                    manifest_verification_bytes=len(manifest_bytes),
                    max_member_bytes=max_member_bytes,
                    opened_stat_signature=(
                        opened_stat_signature if max_member_bytes is not None else None
                    ),
                    read_attempt=_read_attempt,
                )
                try:
                    yield stream
                except BaseException:
                    try:
                        raw.close()
                    except BaseException as close_error:
                        if _read_attempt is not None:
                            _read_attempt.cleanup_failed(
                                close_error,
                                stage="bounded_member_close",
                                primary_failure=True,
                            )
                    raise
                else:
                    try:
                        stream.finish()
                    except BaseException:
                        try:
                            raw.close()
                        except BaseException as close_error:
                            if _read_attempt is not None:
                                _read_attempt.cleanup_failed(
                                    close_error,
                                    stage="bounded_member_close",
                                    primary_failure=True,
                                )
                        raise
                    try:
                        raw.close()
                    except BaseException as close_error:
                        if _read_attempt is not None:
                            _read_attempt.cleanup_failed(
                                close_error,
                                stage="bounded_member_close",
                                primary_failure=False,
                            )
                        raise
            except BaseException as error:
                primary_error = error
                if _read_attempt is not None:
                    _read_attempt.failed(
                        stage=(_read_attempt.usage.failure_stage or "bounded_member_open_status")
                    )
                raise
            finally:
                if descriptor >= 0:
                    try:
                        os.close(descriptor)
                    except BaseException as close_error:
                        if _read_attempt is not None:
                            _read_attempt.cleanup_failed(
                                close_error,
                                stage="bounded_member_descriptor_close",
                                primary_failure=primary_error is not None,
                            )
                        if primary_error is None:
                            raise

    def open_member_bounded(
        self,
        artifact_id: ArtifactRef,
        member: Literal["blob"],
        *,
        max_manifest_bytes: int,
        expected_manifest_sha256: str,
        max_member_bytes: int,
    ) -> _BoundedMemberOpenAttempt:
        """Open an exact selected blob with an owner-enforced byte ceiling."""
        return _BoundedMemberOpenAttempt(
            self,
            artifact_id,
            member,
            max_manifest_bytes=max_manifest_bytes,
            expected_manifest_sha256=expected_manifest_sha256,
            max_member_bytes=max_member_bytes,
        )

    def copy_member_to(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        member: ArtifactMemberKind,
        destination: BinaryIO,
    ) -> ArtifactMemberReceipt:
        """Copy a complete owner-verified member to a caller-owned stream."""
        with self.open_member(artifact_id, member) as source:
            while payload := source.read(_VerifiedCASMemberStream._CHUNK_SIZE):
                destination.write(payload)
            return source.receipt

    def artifact_store_config(self) -> ArtifactStoreConfig:
        """Return declarative config needed to rebuild this store instance."""
        from .backends.config import ArtifactStoreConfig

        return ArtifactStoreConfig(backend="filesystem", root=str(self.root))

    def for_tenant(self, tenant_id: str, cell_id: str | None = None) -> FileSystemCAS:
        """Return a tenant-scoped view over the same immutable CAS root."""
        return FileSystemCAS(
            self.root,
            signing_config=self._signing_config,
            metrics=self._metrics,
            tracer=self._tracer,
            tenant_id=tenant_id,
            cell_id=cell_id,
            ownership_enforced=True,
            ownership_requires_scope=True,
            ownership_index=self._ownership_index,
        )

    def with_ambient_ownership_enforcement(self) -> FileSystemCAS:
        """Return a shared-CAS view that enforces ownership when a tenant scope exists."""
        if self._ownership_enforced:
            return self
        return FileSystemCAS(
            self.root,
            signing_config=self._signing_config,
            metrics=self._metrics,
            tracer=self._tracer,
            tenant_id=self._tenant_id,
            cell_id=self._cell_id,
            ownership_enforced=True,
            ownership_requires_scope=False,
            ownership_index=self._ownership_index,
        )

    def record_artifact_owner(
        self,
        artifact_id: ArtifactID | str,
        *,
        tenant_id: str | None = None,
        cell_id: str | None = None,
        writer: str | None = None,
    ) -> None:
        """Record a tenant ownership claim without changing the artifact ID."""
        if isinstance(artifact_id, str):
            artifact_id = ArtifactID.model_validate(artifact_id)
        owner_tenant, owner_cell = self._resolve_owner(
            tenant_id=tenant_id,
            cell_id=cell_id,
            required=True,
        )
        with self._coordinator.artifact_lease(artifact_id, exclusive=True) as lease:
            self._ownership_index.require_no_pending_transaction(artifact_id)
            self._ownership_index.record_owner(
                artifact_id,
                tenant_id=owner_tenant,
                cell_id=owner_cell,
                writer=writer,
                _lease=lease,
            )

    def ownership_evidence(
        self,
        *,
        tenant_id: str | None = None,
        cell_id: str | None = None,
    ) -> dict[str, object]:
        """Return ownership-index evidence for debug and canary bundles."""
        owner_tenant, owner_cell = self._resolve_owner(
            tenant_id=tenant_id,
            cell_id=cell_id,
            required=False,
        )
        return self._ownership_index.evidence(
            tenant_id=owner_tenant,
            cell_id=owner_cell,
        )

    def _manifest_path_for_ref(
        self,
        artifact_id: ArtifactID,
        manifest_profile_sha256: str | None,
    ) -> Path:
        if manifest_profile_sha256 is None:
            return self._paths(artifact_id)[1]
        return self._layout.view_manifest_path(artifact_id, manifest_profile_sha256)

    def _sig_path(
        self,
        artifact_id: ArtifactID,
        manifest_profile_sha256: str | None = None,
    ) -> Path:
        if manifest_profile_sha256 is not None:
            return self._layout.view_sig_path(artifact_id, manifest_profile_sha256)
        return self._layout.sig_path(artifact_id)

    def _record_integrity_failure(self, *, reason: str) -> None:
        recorder = getattr(self._metrics, "record_artifact_integrity_failure", None)
        if callable(recorder):
            recorder(backend="filesystem", reason=reason)

    @overload
    def _resolve_owner(
        self,
        *,
        tenant_id: str | None = None,
        cell_id: str | None = None,
        required: Literal[True],
    ) -> tuple[str, str | None]: ...

    @overload
    def _resolve_owner(
        self,
        *,
        tenant_id: str | None = None,
        cell_id: str | None = None,
        required: bool,
    ) -> tuple[str | None, str | None]: ...

    def _resolve_owner(
        self,
        *,
        tenant_id: str | None = None,
        cell_id: str | None = None,
        required: bool,
    ) -> tuple[str | None, str | None]:
        owner_tenant = tenant_id or self._tenant_id
        owner_cell = cell_id if cell_id is not None else self._cell_id
        if owner_tenant is None:
            access_scope = _current_access_scope()
            if access_scope is not None:
                owner_tenant = getattr(access_scope, "tenant_id", None)
                owner_cell = owner_cell or getattr(access_scope, "cell_id", None)
        if owner_tenant is None:
            owner_tenant = _current_tenant_id()
            owner_cell = owner_cell or _current_cell_id()
        if required and not owner_tenant:
            raise ArtifactOwnershipError(
                "Tenant-scoped artifact operation requires an active tenant owner"
            )
        return owner_tenant, owner_cell

    def _require_artifact_owner(
        self,
        artifact_id: ArtifactID,
        *,
        operation: str,
        ref: ArtifactRef | None = None,
    ) -> None:
        if not self._ownership_enforced:
            return
        closure_active = self._require_current_public_read_if_active(
            artifact_id,
            ref.manifest_profile_sha256 if ref is not None else None,
            operation=operation,
            ref=ref,
        )
        tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)
        if tenant_id is None:
            if not closure_active:
                self._require_unclaimed_without_owner(
                    artifact_id,
                    operation=operation,
                    ref=ref,
                    manifest_profile_sha256=(
                        ref.manifest_profile_sha256 if ref is not None else None
                    ),
                )
            return
        self._ownership_index.require_owner(
            artifact_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            operation=operation,
        )

    def _require_blob_owner(
        self,
        artifact_id: ArtifactID,
        *,
        operation: str,
        ref: ArtifactRef | None = None,
    ) -> None:
        if not self._ownership_enforced:
            return
        closure_active = self._require_current_public_read_if_active(
            artifact_id,
            ref.manifest_profile_sha256 if ref is not None else None,
            operation=operation,
            ref=ref,
        )
        tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)
        if tenant_id is None:
            if not closure_active:
                self._require_unclaimed_without_owner(
                    artifact_id,
                    operation=operation,
                    ref=ref,
                    manifest_profile_sha256=(
                        ref.manifest_profile_sha256 if ref is not None else None
                    ),
                )
            return
        self._ownership_index.require_blob_reader(
            artifact_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            operation=operation,
        )

    def _require_manifest_view_owner(
        self,
        artifact_id: ArtifactID,
        manifest_profile_sha256: str | None,
        *,
        operation: str,
        ref: ArtifactRef | None = None,
    ) -> None:
        if manifest_profile_sha256 is None:
            self._require_artifact_owner(artifact_id, operation=operation, ref=ref)
            return
        if not self._ownership_enforced:
            return
        closure_active = self._require_current_public_read_if_active(
            artifact_id,
            manifest_profile_sha256,
            operation=operation,
            ref=ref,
        )
        tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)
        if tenant_id is None:
            if not closure_active:
                self._require_unclaimed_without_owner(
                    artifact_id,
                    operation=operation,
                    ref=ref,
                    manifest_profile_sha256=manifest_profile_sha256,
                )
            return
        self._ownership_index.require_view_owner(
            artifact_id,
            manifest_profile_sha256,
            tenant_id=tenant_id,
            cell_id=cell_id,
            operation=operation,
        )

    def _require_unclaimed_without_owner(
        self,
        artifact_id: ArtifactID,
        *,
        operation: str,
        ref: ArtifactRef | None = None,
        manifest_profile_sha256: str | None = None,
    ) -> None:
        if _GOVERNED_PUBLIC_READ.get() is not None:
            self._require_governed_public_read(
                artifact_id,
                manifest_profile_sha256,
                operation=operation,
                ref=ref,
            )
            return
        if self._ownership_index.has_any_tenant_claim(artifact_id):
            raise ArtifactOwnershipError(
                f"Artifact {artifact_id} has tenant ownership claims; an active owner "
                f"is required for {operation}"
            )

    def _require_current_public_read_if_active(
        self,
        artifact_id: ArtifactID,
        manifest_profile_sha256: str | None,
        *,
        operation: str,
        ref: ArtifactRef | None,
    ) -> bool:
        if _GOVERNED_PUBLIC_READ.get() is None:
            return False
        self._require_governed_public_read(
            artifact_id,
            manifest_profile_sha256,
            operation=operation,
            ref=ref,
        )
        return True

    def _require_default_manifest_access(
        self,
        artifact_id: ArtifactID,
        *,
        operation: str,
        ref: ArtifactRef | None = None,
    ) -> None:
        """Authorize a default-view read using ownership evidence only."""
        self._require_artifact_owner(artifact_id, operation=operation, ref=ref)

    def _record_write_owner(
        self,
        artifact_id: ArtifactID,
        *,
        default_view_created: bool,
        lease: _ArtifactTransactionLease | None = None,
    ) -> None:
        if not self._ownership_enforced:
            return
        tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)
        if tenant_id is None:
            return
        if default_view_created:
            self._ownership_index.record_owner(
                artifact_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
                writer="FileSystemCAS",
                _lease=lease,
            )
        else:
            self._ownership_index.record_blob_reader(
                artifact_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
                writer="FileSystemCAS",
                _lease=lease,
            )

    def _record_write_view_owner(
        self,
        artifact_id: ArtifactID,
        manifest_profile_sha256: str,
        *,
        lease: _ArtifactTransactionLease | None = None,
    ) -> None:
        if not self._ownership_enforced:
            return
        tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)
        if tenant_id is None:
            return
        self._ownership_index.record_view_owner(
            artifact_id,
            manifest_profile_sha256,
            tenant_id=tenant_id,
            cell_id=cell_id,
            writer="FileSystemCAS",
            _lease=lease,
        )

    def _require_input_owners(self, opts: PutOptions) -> None:
        if not self._ownership_enforced:
            return
        for input_ref in opts.inputs or []:
            input_ref = _coerce_input_ref(input_ref)
            self._require_blob_owner(
                input_ref.artifact_id,
                operation=f"write input:{input_ref.role}",
            )
            self._require_manifest_view_owner(
                input_ref.artifact_id,
                input_ref.manifest_profile_sha256,
                operation=f"write input manifest:{input_ref.role}",
            )

    def _require_unclaimed_target_if_unscoped(
        self,
        artifact_id: ArtifactID,
        *,
        operation: str,
    ) -> None:
        if not self._ownership_enforced:
            return
        tenant_id, _cell_id = self._resolve_owner(required=self._ownership_requires_scope)
        if tenant_id is None:
            self._require_unclaimed_without_owner(artifact_id, operation=operation)

    def _ensure_default_signer(self) -> Ed25519Signer:
        if self._default_signer is not None:
            return self._default_signer
        with self._signer_lock:
            if self._default_signer is None:
                self._default_signer = load_signer_from_config(self._signing_config)
        return self._default_signer

    def _storage_member(
        self,
        path: Path,
        *,
        sha256: str,
        byte_size: int,
    ) -> _CASStorageMember:
        """Bind a planned final member to this store root and exact content size."""
        try:
            relative = PurePosixPath(path.relative_to(self.root).as_posix())
        except ValueError as exc:
            raise ArtifactIntegrityError("CAS quota member escaped its root") from exc
        return _CASStorageMember(
            relative_path=relative,
            sha256=sha256.removeprefix("sha256:"),
            byte_size=byte_size,
        )

    def _admit_storage_members(self, members: list[_CASStorageMember]) -> None:
        """Ask the active tenant wrapper to admit one exact final-member batch."""
        if self._storage_admission is None:
            return
        unique: dict[PurePosixPath, _CASStorageMember] = {}
        for member in members:
            previous = unique.get(member.relative_path)
            if previous is not None and previous != member:
                raise ArtifactIntegrityError("CAS quota plan contains conflicting final members")
            unique[member.relative_path] = member
        self._storage_admission.admit(tuple(unique.values()))

    def _prepare_sign_on_put(
        self,
        artifact_ref: ArtifactRef,
        *,
        data: bytes,
        manifest_bytes: bytes,
    ) -> tuple[DetachedSignature | None, Exception | None]:
        """Prepare the sign-on-put sidecar before tenant quota admission."""
        config = self._signing_config
        if self._storage_admission is None or not (config.enabled and config.sign_on_put):
            return None, None
        try:
            artifact_id, profile_sha256, _reference = _artifact_reference(artifact_ref)
            signature_path = self._sig_path(artifact_id, profile_sha256)
            if signature_path.exists():
                return None, None
            signer = self._ensure_default_signer()
            signature = signer.sign(
                artifact_id,
                data,
                manifest_bytes,
                signer_identity=config.default_identity,
            )
            return signature, None
        except Exception as exc:
            return None, exc

    def _finish_sign_on_put(
        self,
        artifact_ref: ArtifactRef,
        signature: DetachedSignature | None,
        signing_error: Exception | None,
    ) -> None:
        """Keep legacy signing errors while reusing the pre-admitted signature bytes."""
        if self._storage_admission is None:
            self._maybe_sign_on_put(artifact_ref)
            return
        if signing_error is not None:
            self._raise_signing_error(signing_error)
        if signature is None:
            self._maybe_sign_on_put(artifact_ref)
            return
        try:
            self.put_signature(artifact_ref, signature)
        except Exception as exc:
            self._raise_signing_error(exc)

    def _raise_signing_error(self, exc: Exception) -> None:
        """Apply the existing sign-on-put error policy after primary publication."""
        if self._signing_config.sign_on_put_policy.strip().lower() == "warn":
            raise SigningError(
                f"Artifact write completed but sign_on_put failed under warn policy: {exc}"
            ) from exc
        raise SigningError(f"Failed to sign artifact on put: {exc}") from exc

    def _maybe_sign_on_put(self, artifact_ref: ArtifactRef) -> None:
        config = self._signing_config
        if not (config.enabled and config.sign_on_put):
            return
        try:
            if self.has_signature(artifact_ref):
                return
            signer = self._ensure_default_signer()
            self.sign_artifact(
                artifact_ref,
                signer,
                signer_identity=config.default_identity,
            )
        except Exception as exc:
            if config.sign_on_put_policy.strip().lower() == "warn":
                raise SigningError(
                    f"Artifact write completed but sign_on_put failed under warn policy: {exc}"
                ) from exc
            raise SigningError(f"Failed to sign artifact on put: {exc}") from exc

    @_transactional_read()
    def has(self, artifact_id: ArtifactID | ArtifactRef | str) -> bool:
        """Return whether the blob and selected manifest view exist."""
        aid, profile_sha256, ref = _artifact_reference(artifact_id)
        blob, _ = self._paths(aid)
        manifest = self._manifest_path_for_ref(aid, profile_sha256)
        if self._read_only:
            blob_exists = self._read_only_member_present(blob, member="blob")
            manifest_exists = self._read_only_member_present(manifest, member="manifest")
            if manifest_exists and not blob_exists:
                raise ArtifactIntegrityError("selected CAS manifest exists without its blob")
            exists = blob_exists and manifest_exists
            if exists:
                selected = ref or aid
                try:
                    self.get_manifest(selected)
                    self.get_bytes(selected)
                except FileNotFoundError as exc:
                    blob_exists = self._read_only_member_present(blob, member="blob")
                    manifest_exists = self._read_only_member_present(manifest, member="manifest")
                    if manifest_exists and not blob_exists:
                        raise ArtifactIntegrityError(
                            "selected CAS manifest exists without its blob"
                        ) from exc
                    if blob_exists and manifest_exists:
                        raise ArtifactReadOnlyUnavailableError(
                            "cas_member_changed_during_read"
                        ) from exc
                    exists = False
        else:
            exists = blob.exists() and manifest.exists()
        if exists and self._ownership_enforced:
            tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)
            if tenant_id is None:
                exists = not self._ownership_index.has_any_tenant_claim(aid)
            else:
                exists = (
                    self._ownership_index.is_view_owned_by(
                        aid,
                        profile_sha256,
                        tenant_id=tenant_id,
                        cell_id=cell_id,
                    )
                    if profile_sha256 is not None
                    else self._ownership_index.is_owned_by(
                        aid,
                        tenant_id=tenant_id,
                        cell_id=cell_id,
                    )
                )
        if ref is not None and exists and not self._read_only:
            try:
                self.get_manifest(ref)
            except FileNotFoundError, ValueError, ArtifactOwnershipError:
                exists = False
        if self._hpc_enabled and self._metrics:
            if exists and self._metrics.artifact_cache_hits_total:
                self._metrics.artifact_cache_hits_total.add(1, {"kind": "existence_check"})
            elif not exists and self._metrics.artifact_cache_misses_total:
                self._metrics.artifact_cache_misses_total.add(1, {"kind": "existence_check"})
        return exists

    @_transactional_read(profile_argument_index=0)
    def has_manifest_view(
        self,
        artifact_id: ArtifactID | str,
        manifest_profile_sha256: str,
    ) -> bool:
        """Return whether an exact manifest view is present and owned by this store.

        This optional cache-admission probe does not infer metadata access from
        shared blob ownership.
        """
        aid = (
            ArtifactID.model_validate(artifact_id) if isinstance(artifact_id, str) else artifact_id
        )
        if re.fullmatch(r"sha256:[0-9a-f]{64}", manifest_profile_sha256) is None:
            raise ValueError("manifest_profile_sha256 must be sha256:<64 lowercase hex>")
        blob_path, _default_manifest_path = self._paths(aid)
        view_manifest_path = self._layout.view_manifest_path(aid, manifest_profile_sha256)
        if not blob_path.is_file() or not view_manifest_path.is_file():
            return False
        try:
            self._require_blob_owner(aid, operation="has_manifest_view")
            self._require_manifest_view_owner(
                aid,
                manifest_profile_sha256,
                operation="has_manifest_view",
            )
        except ArtifactOwnershipError:
            return False
        manifest = self._manifests.read(view_manifest_path)
        _validate_manifest_identity(aid, manifest)
        if self._manifests.profile_sha256(manifest) != manifest_profile_sha256:
            raise ArtifactIntegrityError(f"Selected manifest profile mismatch for {aid}")
        return True

    @_transactional_read()
    def get_bytes(self, artifact_id: ArtifactID | ArtifactRef | str) -> bytes:
        """Read artifact blob bytes and emit CAS read metrics/traces when enabled.

        Raises:
            FileNotFoundError: If the blob file is missing.
            OSError: If the blob file cannot be read.
        """
        aid, profile_sha256, ref = _artifact_reference(artifact_id)
        self._require_blob_owner(aid, operation="read", ref=ref)
        if profile_sha256 is not None:
            self._require_manifest_view_owner(
                aid,
                profile_sha256,
                operation="read_manifest",
                ref=ref,
            )
        blob, _ = self._paths(aid)
        if not self._hpc_enabled or self._tracer is None:
            return self._read_verified_blob(aid, blob, manifest_ref=ref)

        short_id = f"{aid.hex[:16]}..."
        with self._tracer.start_as_current_span(
            "cas.get_bytes",
            attributes={
                "cas.artifact_id": short_id,
                "cas.operation": "read",
            },
        ) as span:
            start = time.perf_counter()
            if not blob.exists():
                duration = time.perf_counter() - start
                if self._metrics and self._metrics.artifact_cache_misses_total:
                    self._metrics.artifact_cache_misses_total.add(1, {"kind": "blob"})
                if self._metrics and self._metrics.artifact_io_duration_seconds:
                    self._metrics.artifact_io_duration_seconds.record(
                        duration,
                        {"operation": "read", "kind": "blob", "cache_hit": "false"},
                    )
                span.set_attribute("cas.cache_hit", False)
                span.set_attribute("cas.duration_seconds", duration)
                raise FileNotFoundError(f"Artifact not found: {aid.hex}")

            data = self._read_verified_blob(aid, blob, manifest_ref=ref)
            duration = time.perf_counter() - start
            byte_size = len(data)

            if self._metrics and self._metrics.artifact_cache_hits_total:
                self._metrics.artifact_cache_hits_total.add(1, {"kind": "blob"})
            if self._metrics and self._metrics.artifact_io_bytes:
                self._metrics.artifact_io_bytes.record(
                    byte_size, {"operation": "read", "kind": "blob"}
                )
            if self._metrics and self._metrics.artifact_io_duration_seconds:
                self._metrics.artifact_io_duration_seconds.record(
                    duration,
                    {"operation": "read", "kind": "blob", "cache_hit": "true"},
                )

            span.set_attribute("cas.cache_hit", True)
            span.set_attribute("cas.byte_size", byte_size)
            span.set_attribute("cas.duration_seconds", duration)

            return data

    def import_exact_view(
        self,
        data: bytes,
        manifest_bytes: bytes,
        *,
        artifact_id: ArtifactID | ArtifactRef | str,
        signature_bytes: bytes | None = None,
    ) -> ArtifactRef:
        """Cache one already-owned CAS view without reconstructing signed bytes.

        The manifest and optional detached signature are validated and copied as
        their original bytes. An existing selector-free default is immutable; if
        it differs, the imported view is stored under its exact profile selector.
        Publication uses the same durable intent and owner-generation transaction
        as archive imports.
        """
        aid, requested_profile, ref = _artifact_reference(artifact_id)
        if content_hash(data) != aid.hex:
            raise ArtifactIntegrityError(f"Blob sha256 mismatch for {aid}")

        manifest = ArtifactManifest.model_validate_json(manifest_bytes)
        _validate_manifest_identity(aid, manifest)
        _validate_read_integrity(aid, data, manifest)
        profile_sha256 = self._manifests.profile_sha256(manifest)
        if requested_profile is not None and requested_profile != profile_sha256:
            raise ArtifactIntegrityError(f"Selected manifest profile mismatch for {aid}")
        if ref is not None and (ref.kind != manifest.kind or ref.media_type != manifest.media_type):
            raise ArtifactIntegrityError(
                f"Artifact reference type does not match selected manifest for {aid}"
            )

        if signature_bytes is not None:
            signature = DetachedSignature.model_validate_json(signature_bytes)
            if signature.artifact_id != str(aid):
                raise ArtifactIntegrityError(f"Signature artifact ID mismatch for {aid}")
            if signature.statement.blob_sha256 != aid.hex:
                raise ArtifactIntegrityError(f"Signature blob digest mismatch for {aid}")
            if signature.statement.manifest_sha256 != hashlib.sha256(manifest_bytes).hexdigest():
                raise ArtifactIntegrityError(f"Signature manifest digest mismatch for {aid}")

        prefix = f"artifacts/sha256/{aid.hex[:2]}/{aid.hex[2:4]}/{aid.hex}"
        blob_member = f"{prefix}.blob"
        manifest_member = (
            f"{prefix}.manifest.json"
            if requested_profile is None
            else f"{prefix}.view.{profile_sha256.removeprefix('sha256:')}.manifest.json"
        )
        members = {blob_member, manifest_member}
        if signature_bytes is not None:
            members.add(manifest_member.removesuffix(".manifest.json") + ".sig")

        intake = {
            blob_member: TransferMemberSnapshot(content_hash(data), len(data)),
            manifest_member: TransferMemberSnapshot(
                content_hash(manifest_bytes), len(manifest_bytes), manifest_bytes
            ),
        }
        if signature_bytes is not None:
            signature_member = manifest_member.removesuffix(".manifest.json") + ".sig"
            intake[signature_member] = TransferMemberSnapshot(
                content_hash(signature_bytes), len(signature_bytes), signature_bytes
            )

        with self._admit_import_members(intake) as admission:
            if not admission.pending_artifact_ids:
                imported = admission.exact_refs
            else:
                staging_root = Path(tempfile.mkdtemp(prefix=".cas-import-exact-", dir=self.root))

                def write_staged_member(member: str, payload: bytes) -> None:
                    safe_path = _safe_member_path(member)
                    if safe_path is None or safe_path.as_posix() != member:
                        raise ArtifactIntegrityError("CAS exact import member path is unsafe")
                    target = staging_root / Path(*safe_path.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    descriptor = os.open(
                        target,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                        0o600,
                    )
                    with os.fdopen(descriptor, "wb") as stream:
                        stream.write(payload)
                        stream.flush()
                        os.fsync(stream.fileno())

                try:
                    write_staged_member(blob_member, data)
                    write_staged_member(manifest_member, manifest_bytes)
                    if signature_bytes is not None:
                        signature_member = manifest_member.removesuffix(".manifest.json") + ".sig"
                        write_staged_member(signature_member, signature_bytes)
                    imported = self._publish_staged_import(
                        staging_root,
                        members,
                        {str(aid)},
                    ).refs
                finally:
                    if staging_root.exists() and not staging_root.is_symlink():
                        shutil.rmtree(staging_root)

        expected_profile = requested_profile or profile_sha256
        selected = next(
            (
                imported_ref
                for imported_ref in imported
                if imported_ref.manifest_profile_sha256 == expected_profile
            ),
            None,
        )
        if requested_profile is None:
            selected = next(
                (
                    imported_ref
                    for imported_ref in imported
                    if imported_ref.manifest_profile_sha256 is None
                ),
                selected,
            )
        if selected is None:
            raise ArtifactIntegrityError("CAS exact import did not publish its selected view")
        return selected

    @_transactional_read()
    def get_manifest(self, artifact_id: ArtifactID | ArtifactRef | str) -> ArtifactManifest:
        """Load and validate the default or explicitly selected manifest view.

        Raises:
            FileNotFoundError: If the manifest file is missing.
            ValueError: If the manifest JSON does not match `ArtifactManifest`.
        """
        aid, profile_sha256, ref = _artifact_reference(artifact_id)
        if profile_sha256 is not None:
            self._require_manifest_view_owner(
                aid,
                profile_sha256,
                operation="read_manifest",
                ref=ref,
            )
        else:
            self._require_default_manifest_access(
                aid,
                operation="read_manifest",
                ref=ref,
            )
        manp = self._manifest_path_for_ref(aid, profile_sha256)
        if self._read_only:
            manifest_bytes = self._read_cas_file_no_follow(manp, member="manifest")
            manifest = ArtifactManifest.model_validate_json(manifest_bytes)
        else:
            manifest = self._manifests.read(manp)
        try:
            _validate_manifest_identity(aid, manifest)
            if profile_sha256 is not None:
                actual_profile = self._manifests.profile_sha256(manifest)
                if actual_profile != profile_sha256:
                    raise ArtifactIntegrityError(f"Selected manifest profile mismatch for {aid}")
            if ref is not None and (
                ref.kind != manifest.kind or ref.media_type != manifest.media_type
            ):
                raise ArtifactIntegrityError(
                    f"Artifact reference type does not match selected manifest for {aid}"
                )
        except ArtifactIntegrityError as exc:
            self._record_integrity_failure(reason=type(exc).__name__)
            raise
        return manifest

    @_transactional_read(profile_argument_index=0)
    def get_manifest_by_profile(
        self,
        artifact_id: ArtifactID | str,
        manifest_profile_sha256: str,
    ) -> ArtifactManifest:
        """Resolve one selected manifest view without assuming the default kind."""
        aid = ArtifactID.model_validate(artifact_id)
        if re.fullmatch(r"sha256:[0-9a-f]{64}", manifest_profile_sha256) is None:
            raise ValueError("manifest_profile_sha256 must be sha256:<64 lowercase hex>")
        self._require_blob_owner(aid, operation="read_manifest_by_profile")
        self._require_manifest_view_owner(
            aid,
            manifest_profile_sha256,
            operation="read_manifest_by_profile",
        )
        manifest_path = self._manifest_path_for_ref(aid, manifest_profile_sha256)
        if self._ownership_index._path_has_symlink_component(manifest_path):
            raise ArtifactIntegrityError("CAS manifest path crosses a symlink")
        manifest = self._manifests.read(manifest_path)
        _validate_manifest_identity(aid, manifest)
        if self._manifests.profile_sha256(manifest) != manifest_profile_sha256:
            raise ArtifactIntegrityError(f"Selected manifest profile mismatch for {aid}")
        return manifest

    @_transactional_read(profile_argument_index=0, manifest_bytes_result=True)
    def get_raw_manifest_bytes(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        *,
        manifest_profile_sha256: str | None = None,
    ) -> bytes:
        """Read the exact selected sidecar bytes without constructing its typed model."""
        aid, selected_profile, ref = _artifact_reference(artifact_id)
        if manifest_profile_sha256 is not None:
            if re.fullmatch(r"sha256:[0-9a-f]{64}", manifest_profile_sha256) is None:
                raise ValueError("manifest_profile_sha256 must be sha256:<64 lowercase hex>")
            if selected_profile is not None and selected_profile != manifest_profile_sha256:
                raise ValueError("conflicting manifest profile selectors")
            selected_profile = manifest_profile_sha256
        self._require_blob_owner(aid, operation="read_raw_manifest", ref=ref)
        if selected_profile is None:
            self._require_default_manifest_access(
                aid,
                operation="read_raw_manifest",
                ref=ref,
            )
        else:
            self._require_manifest_view_owner(
                aid,
                selected_profile,
                operation="read_raw_manifest_view",
                ref=ref,
            )
        manifest_path = self._manifest_path_for_ref(aid, selected_profile)
        if self._ownership_index._path_has_symlink_component(manifest_path):
            raise ArtifactIntegrityError("CAS manifest path crosses a symlink")
        descriptor = os.open(manifest_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ArtifactIntegrityError("CAS manifest is not a regular file")
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                return stream.read()
        finally:
            os.close(descriptor)

    def _read_raw_manifest_bytes_bounded_owned(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        *,
        max_manifest_bytes: int,
        manifest_profile_sha256: str | None,
    ) -> ArtifactBoundedManifestRead:
        """Read one default or exact manifest through its guarded owner path."""
        if type(max_manifest_bytes) is not int or max_manifest_bytes < 1:
            raise ValueError("max_manifest_bytes must be a positive integer")
        if type(artifact_id) is ArtifactRef:
            aid, selected_profile, ref = _artifact_reference(artifact_id)
            if type(selected_profile) is not str or not selected_profile:
                raise ValueError("bounded_manifest_read_requires_profile_qualified_ref")
            if manifest_profile_sha256 is not None and manifest_profile_sha256 != selected_profile:
                raise ValueError("conflicting manifest profile selectors")
        else:
            aid = ArtifactID.model_validate(artifact_id)
            selected_profile = manifest_profile_sha256
            ref = None
        if selected_profile is not None and (
            type(selected_profile) is not str
            or re.fullmatch(r"sha256:[0-9a-f]{64}", selected_profile) is None
        ):
            raise ValueError("manifest_profile_sha256 must be sha256:<64 lowercase hex>")

        self._require_blob_owner(aid, operation="read_raw_manifest_bounded", ref=ref)
        if selected_profile is None:
            self._require_default_manifest_access(
                aid,
                operation="read_raw_manifest_bounded_default",
                ref=ref,
            )
            usage_stage = "default_manifest_transfer"
            attempt_stage = "default_manifest_preflight"
        else:
            self._require_manifest_view_owner(
                aid,
                selected_profile,
                operation="read_raw_manifest_bounded_selected",
                ref=ref,
            )
            usage_stage = "selected_manifest_transfer"
            attempt_stage = "selected_manifest_preflight"
        manifest_path = self._manifest_path_for_ref(aid, selected_profile)
        attempt = _ArtifactStoreReadAttempt(stage=attempt_stage)
        try:
            data = self._read_cas_file_no_follow(
                manifest_path,
                member="manifest",
                max_bytes=max_manifest_bytes,
                raise_read_limit=True,
                _read_attempt=attempt,
                _usage_field="observed_manifest_selection_bytes",
                _usage_stage=usage_stage,
            )
        except Exception as exc:
            attempt.failed()
            raise ArtifactBoundedManifestReadError(
                "cas_bounded_manifest_read_refused",
                usage=attempt.usage,
                original_exception=exc,
            ) from exc
        attempt.succeeded()
        return ArtifactBoundedManifestRead(raw_manifest_bytes=data, usage=attempt.usage)

    @_transactional_read(profile_argument_index=1, manifest_bytes_result=True)
    def get_raw_manifest_bytes_bounded(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        *,
        max_manifest_bytes: int,
        manifest_profile_sha256: str | None = None,
    ) -> bytes:
        """Read bounded default or exact raw manifest bytes without unbounded allocation."""
        return self._read_raw_manifest_bytes_bounded_owned(
            artifact_id,
            max_manifest_bytes=max_manifest_bytes,
            manifest_profile_sha256=manifest_profile_sha256,
        ).raw_manifest_bytes

    @_transactional_read(profile_argument_index=1)
    def read_raw_manifest_bytes_bounded(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        *,
        max_manifest_bytes: int,
        manifest_profile_sha256: str | None = None,
    ) -> ArtifactBoundedManifestRead:
        """Read default or exact manifest bytes with an immutable owner receipt."""
        return self._read_raw_manifest_bytes_bounded_owned(
            artifact_id,
            max_manifest_bytes=max_manifest_bytes,
            manifest_profile_sha256=manifest_profile_sha256,
        )

    @_transactional_read(manifest_bytes_result=True)
    def get_raw_manifest_bytes_bounded_for_input(
        self,
        input_ref: InputRef,
        *,
        max_manifest_bytes: int,
    ) -> bytes:
        """Read one bounded profile-qualified manifest selected by a lineage edge.

        InputRef carries no kind or media type. This method therefore selects
        only by its exact artifact ID and explicit profile digest; Core derives
        the complete ArtifactRef from the returned raw manifest bytes.
        """
        if type(max_manifest_bytes) is not int or max_manifest_bytes < 1:
            raise ValueError("max_manifest_bytes must be a positive integer")
        selected = _revalidate_input_ref(input_ref)
        aid = selected.artifact_id
        selected_profile = selected.manifest_profile_sha256
        if selected_profile is None:
            raise ValueError("bounded_manifest_read_requires_profile_qualified_input")
        self._require_blob_owner(
            aid,
            operation="read_raw_manifest_bounded_input",
        )
        self._require_manifest_view_owner(
            aid,
            selected_profile,
            operation="read_raw_manifest_bounded_input",
        )
        manifest_path = self._manifest_path_for_ref(aid, selected_profile)
        return self._read_cas_file_no_follow(
            manifest_path,
            member="manifest",
            max_bytes=max_manifest_bytes,
            raise_read_limit=True,
        )

    @_transactional_read()
    def read_raw_manifest_bytes_bounded_for_input(
        self,
        input_ref: InputRef,
        *,
        max_manifest_bytes: int,
    ) -> ArtifactBoundedManifestRead:
        """Read an input-selected manifest with an immutable owner transfer receipt."""
        if type(max_manifest_bytes) is not int or max_manifest_bytes < 1:
            raise ValueError("max_manifest_bytes must be a positive integer")
        selected = _revalidate_input_ref(input_ref)
        aid = selected.artifact_id
        selected_profile = selected.manifest_profile_sha256
        if selected_profile is None:
            raise ValueError("bounded_manifest_read_requires_profile_qualified_input")
        self._require_blob_owner(aid, operation="read_raw_manifest_bounded_input")
        self._require_manifest_view_owner(
            aid,
            selected_profile,
            operation="read_raw_manifest_bounded_input",
        )
        manifest_path = self._manifest_path_for_ref(aid, selected_profile)
        attempt = _ArtifactStoreReadAttempt(stage="selected_manifest_preflight")
        try:
            data = self._read_cas_file_no_follow(
                manifest_path,
                member="manifest",
                max_bytes=max_manifest_bytes,
                raise_read_limit=True,
                _read_attempt=attempt,
                _usage_field="observed_manifest_selection_bytes",
                _usage_stage="selected_manifest_transfer",
            )
        except Exception as exc:
            attempt.failed()
            raise ArtifactBoundedManifestReadError(
                "cas_bounded_manifest_read_refused",
                usage=attempt.usage,
                original_exception=exc,
            ) from exc
        attempt.succeeded()
        return ArtifactBoundedManifestRead(raw_manifest_bytes=data, usage=attempt.usage)

    @_transactional_read()
    def get_manifest_bytes(self, artifact_id: ArtifactID | ArtifactRef | str) -> bytes:
        """Return raw selected-manifest bytes through the owner read boundary."""
        with self.open_member(artifact_id, "manifest") as stream:
            chunks: list[bytes] = []
            while chunk := stream.read(_VerifiedCASMemberStream._CHUNK_SIZE):
                chunks.append(chunk)
        return b"".join(chunks)

    def _resume_signature_transaction(
        self,
        *,
        intent: dict[str, Any],
        signature_bytes: bytes,
        artifact_id: ArtifactID,
        signature_selector: str,
        owner: _ResolvedOwner | None,
        lease: _ArtifactTransactionLease,
    ) -> None:
        """Resume only an exact selected-view signature request."""
        signature_specs = intent.get("signatures", [])
        if (
            intent["schema_version"] != _TRANSACTION_INTENT_SCHEMA_V3
            or intent["mode"] != "signature"
            or intent["owner"] != owner
            or intent["blob_sha256"] != f"sha256:{artifact_id.hex}"
            or len(signature_specs) != 1
            or signature_specs[0]["selector"] != signature_selector
            or signature_specs[0]["signature_sha256"] != content_hash(signature_bytes, prefix=True)
        ):
            raise ArtifactTransactionPendingError(
                artifact_id,
                surface=f"signature:{signature_selector}",
            )
        view_specs = [view for view in intent["views"] if view["selector"] == signature_selector]
        if len(view_specs) != 1:
            raise ArtifactTransactionPendingError(
                artifact_id,
                surface=f"signature:{signature_selector}",
            )
        view_spec = view_specs[0]
        manifest_path = self._manifest_path_for_ref(
            artifact_id,
            None if signature_selector == "default" else signature_selector,
        )
        manifest_bytes = manifest_path.read_bytes()
        if content_hash(manifest_bytes, prefix=True) != view_spec["manifest_sha256"]:
            raise ArtifactTransactionPendingError(
                artifact_id,
                surface=f"signature:{signature_selector}",
            )

        signature_path = self._sig_path(
            artifact_id,
            None if signature_selector == "default" else signature_selector,
        )
        stage = self._ensure_transaction_stage(
            operation_id=intent["operation_id"],
            name="signature.stage",
            recorded_path=signature_specs[0]["signature_stage"],
            data=signature_bytes,
            expected_sha256=signature_specs[0]["signature_sha256"],
            final_path=signature_path,
        )
        self._publish_transaction_member(
            stage,
            signature_path,
            expected_sha256=signature_specs[0]["signature_sha256"],
        )
        if not self._ownership_index._intent_completion_is_recomputed(intent):
            raise ArtifactIntegrityError("artifact_transaction_signature_not_recomputed")
        committed = dict(intent)
        committed["status"] = "committed"
        self._ownership_index.write_transaction_intent(
            artifact_id,
            committed,
            lease=lease,
        )
        self._ownership_index.remove_transaction_intent(artifact_id, lease=lease)
        self._remove_transaction_stage(intent["operation_id"])

    def put_signature(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        signature: DetachedSignature,
    ) -> None:
        """Transactionally publish one immutable detached-signature sidecar."""
        aid, profile_sha256, _ref = _artifact_reference(artifact_id)
        signature_selector = profile_sha256 or "default"
        signature_bytes = signature.model_dump_json(
            by_alias=True,
            exclude_none=True,
            indent=2,
        ).encode("utf-8")
        if signature.artifact_id != str(aid):
            raise ValueError("signature artifact_id mismatch")

        with self._coordinator.artifact_lease(aid, exclusive=True) as lease:
            tenant_id: str | None = None
            cell_id: str | None = None
            if self._ownership_enforced:
                tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)
            owner: _ResolvedOwner | None = (
                {"tenant_id": tenant_id, "cell_id": cell_id}
                if self._ownership_enforced and tenant_id is not None
                else None
            )
            pending = self._ownership_index._read_transaction_intent(aid)
            if pending is not None:
                if self._ownership_index._committed_intent_matches_current_state(pending):
                    self._ownership_index.remove_transaction_intent(aid, lease=lease)
                    self._remove_transaction_stage(pending["operation_id"])
                elif pending["mode"] == "signature":
                    return self._resume_signature_transaction(
                        intent=pending,
                        signature_bytes=signature_bytes,
                        artifact_id=aid,
                        signature_selector=signature_selector,
                        owner=owner,
                        lease=lease,
                    )
                else:
                    raise ArtifactTransactionPendingError(aid, surface="artifact")

            self._ownership_index.require_no_pending_transaction(aid)
            self._require_blob_owner(aid, operation="put_signature")
            if profile_sha256 is None:
                self._require_default_manifest_access(aid, operation="put_signature")
            else:
                self._require_manifest_view_owner(
                    aid,
                    profile_sha256,
                    operation="put_signature",
                )
            blob_path, _default_manifest = self._paths(aid)
            manifest_path = self._manifest_path_for_ref(aid, profile_sha256)
            if self._ownership_index._path_has_symlink_component(
                blob_path
            ) or self._ownership_index._path_has_symlink_component(manifest_path):
                raise ArtifactIntegrityError("CAS signature binding crosses a symlink")
            manifest_bytes = manifest_path.read_bytes()
            manifest = ArtifactManifest.model_validate_json(manifest_bytes)
            _validate_manifest_identity(aid, manifest)
            if profile_sha256 is not None and (
                self._manifests.profile_sha256(manifest) != profile_sha256
            ):
                raise ArtifactIntegrityError(f"Selected manifest profile mismatch for {aid}")
            if _file_content_hash(blob_path) != aid.hex:
                raise ArtifactIntegrityError(f"Blob sha256 mismatch for {aid}")
            if (
                signature.statement.blob_sha256 != aid.hex
                or signature.statement.manifest_sha256 != hashlib.sha256(manifest_bytes).hexdigest()
            ):
                raise ValueError("signature statement does not match the selected artifact view")

            signature_path = self._sig_path(aid, profile_sha256)
            self._prepare_import_destination(signature_path, member=signature_path.name)
            if signature_path.exists():
                existing = signature_path.read_bytes()
                if existing != signature_bytes:
                    raise ArtifactIntegrityError("immutable signature sidecar conflicts")
                return None

            claims = self._ownership_index._transaction_claims_for(
                aid,
                tenant_id=owner["tenant_id"] if owner is not None else None,
                cell_id=owner["cell_id"] if owner is not None else None,
                manifest_profile_sha256=self._manifests.profile_sha256(manifest),
            )
            if owner is None and self._ownership_index.has_any_tenant_claim(aid):
                raise ArtifactOwnershipError(
                    f"Artifact {aid} signature write requires its current tenant owner"
                )
            operation_id = uuid.uuid4().hex
            signature_sha256 = content_hash(signature_bytes, prefix=True)
            intent: dict[str, Any] = {
                "schema_version": _TRANSACTION_INTENT_SCHEMA_V3,
                "status": "pending",
                "mode": "signature",
                "operation_id": operation_id,
                "artifact_id": str(aid),
                "owner": owner,
                "blob_sha256": "sha256:" + aid.hex,
                "blob_stage": None,
                "views": [
                    {
                        "selector": signature_selector,
                        "manifest_profile_sha256": self._manifests.profile_sha256(manifest),
                        "manifest_sha256": content_hash(manifest_bytes, prefix=True),
                        "manifest_stage": None,
                    }
                ],
                "claims": claims,
                "affected": {
                    "ambient_artifact": False,
                    "manifest_profiles": [],
                    "signature_profiles": [signature_selector],
                },
                "manifest_created_at": manifest.created_at.isoformat(),
                "signatures": [
                    {
                        "selector": signature_selector,
                        "signature_sha256": signature_sha256,
                        "signature_stage": self._transaction_stage_relative(
                            operation_id,
                            "signature.stage",
                        ),
                    }
                ],
                "request_sha256": "",
            }
            intent["request_sha256"] = self._ownership_index._transaction_request_digest(intent)
            self._ownership_index.write_transaction_intent(aid, intent, lease=lease)
            stage_path = self._stage_transaction_member(
                operation_id,
                "signature.stage",
                signature_bytes,
            )
            self._publish_transaction_member(
                stage_path,
                signature_path,
                expected_sha256=signature_sha256,
            )
            if not self._ownership_index._intent_completion_is_recomputed(intent):
                raise ArtifactIntegrityError("artifact_transaction_signature_not_recomputed")
            committed = dict(intent)
            committed["status"] = "committed"
            self._ownership_index.write_transaction_intent(aid, committed, lease=lease)
            self._ownership_index.remove_transaction_intent(aid, lease=lease)
            self._remove_transaction_stage(operation_id)

    @_transactional_read(signature_surface=True)
    def get_signature(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
    ) -> DetachedSignature | None:
        """Load a detached signature sidecar or return `None` when unsigned."""
        try:
            return DetachedSignature.model_validate_json(self.get_signature_bytes(artifact_id))
        except FileNotFoundError:
            return None

    @_transactional_read(signature_surface=True)
    def get_signature_bytes(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
    ) -> bytes:
        """Return the exact detached-signature bytes for the selected manifest view."""
        aid, _profile_sha256, _ref = _artifact_reference(artifact_id)
        try:
            with self.open_member(artifact_id, "signature") as stream:
                chunks: list[bytes] = []
                while chunk := stream.read(_VerifiedCASMemberStream._CHUNK_SIZE):
                    chunks.append(chunk)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Signature not found for artifact {aid}") from exc
        return b"".join(chunks)

    @_transactional_read(signature_surface=True)
    def has_signature(self, artifact_id: ArtifactID | ArtifactRef | str) -> bool:
        """Return whether a detached signature sidecar exists for `artifact_id`."""
        try:
            self.get_signature_bytes(artifact_id)
        except FileNotFoundError:
            return False
        return True

    def sign_artifact(
        self,
        artifact_id: ArtifactID | ArtifactRef,
        signer: Ed25519Signer,
        *,
        signer_identity: str | None = None,
    ) -> DetachedSignature:
        """Sign one stored artifact's blob+manifest pair and persist its sidecar."""
        aid, _profile_sha256, ref = _artifact_reference(artifact_id)
        selected: ArtifactID | ArtifactRef = ref or aid
        return _sign_artifact(
            artifact_id=aid,
            signer=signer,
            signer_identity=signer_identity,
            read_blob=lambda selected_id: self.get_bytes(selected),
            read_manifest_bytes=lambda selected_id: self.get_manifest_bytes(selected),
            write_signature=lambda selected_id, signature: self.put_signature(selected, signature),
            load_snapshot=lambda selected_id: self._load_verified_snapshot(selected),
        )

    def verify_signature(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        """Normalize identity before acquiring the CAS read lease."""
        try:
            aid, _profile_sha256, ref = _artifact_reference(artifact_id)
        except ValidationError:
            supplied_id = getattr(artifact_id, "artifact_id", artifact_id)
            if isinstance(supplied_id, ArtifactID):
                supplied_id = supplied_id.root
            result_id = supplied_id if isinstance(supplied_id, str) else "<malformed-artifact-id>"
            message = (
                "Malformed artifact reference"
                if isinstance(artifact_id, ArtifactRef)
                else "Malformed artifact ID"
            )
            return SignatureVerificationResult(
                status=SignatureVerificationStatus.ERROR,
                artifact_id=result_id,
                message=message,
            )

        # Keep the transactional decorator on the typed helper so malformed
        # public identities return ERROR before lease acquisition or CAS access.
        selected: ArtifactID | ArtifactRef = ref or aid
        return self._verify_signature_under_transaction_lease(
            selected,
            verifier,
            strict_identity=strict_identity,
        )

    @_transactional_read(signature_surface=True)
    def _verify_signature_under_transaction_lease(
        self,
        artifact_id: ArtifactID | ArtifactRef,
        verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = None,
    ) -> SignatureVerificationResult:
        """Verify a normalized selected identity while its CAS view is leased."""
        aid, _profile_sha256, ref = _artifact_reference(artifact_id)
        selected: ArtifactID | ArtifactRef = ref or aid
        loaded_snapshot: _VerifiedArtifactSnapshot | None = None

        def load_snapshot(_artifact_id: ArtifactID) -> _VerifiedArtifactSnapshot:
            nonlocal loaded_snapshot
            loaded_snapshot = self._load_verified_snapshot(selected)
            return loaded_snapshot

        def load_signature(_artifact_id: ArtifactID) -> DetachedSignature | None:
            if loaded_snapshot is None:
                raise ArtifactIntegrityError("signature_snapshot_not_loaded")
            return self._load_signature_for_snapshot(selected, loaded_snapshot)

        return _verify_signature(
            artifact_id=aid,
            verifier=verifier,
            strict_identity=strict_identity,
            verify_integrity=self.verify,
            load_signature=load_signature,
            read_blob=lambda selected_id: self.get_bytes(selected),
            read_manifest_bytes=lambda selected_id: self.get_manifest_bytes(selected),
            load_snapshot=load_snapshot,
        )

    def sign_all_artifacts(
        self,
        signer: Ed25519Signer,
        *,
        artifact_ids: Iterable[ArtifactID] | None = None,
        signer_identity: str | None = None,
        only_unsigned: bool = True,
        max_workers: int = 8,
        pending_window: int | None = None,
        cancel_event: threading.Event | None = None,
    ) -> BulkSigningReport:
        """Sign many artifacts concurrently and summarize signed/skipped/error counts."""
        ids = (
            self._iter_artifact_ids_lazy()
            if artifact_ids is None
            else _iter_canonical_artifact_ids(artifact_ids)
        )
        return _sign_all_artifacts(
            signer=signer,
            artifact_ids=ids,
            signer_identity=signer_identity,
            only_unsigned=only_unsigned,
            max_workers=max_workers,
            has_signature_for_artifact=self.has_signature,
            read_blob=self.get_bytes,
            read_manifest_bytes=self.get_manifest_bytes,
            write_signature=self.put_signature,
            pending_window=pending_window,
            cancel_event=cancel_event,
            load_snapshot=self._load_verified_snapshot,
        )

    def verify_all_signatures(
        self,
        verifier: Ed25519Verifier,
        *,
        artifact_ids: Iterable[ArtifactID] | None = None,
        max_workers: int = 8,
        strict_identity: bool | None = None,
        pending_window: int | None = None,
        cancel_event: threading.Event | None = None,
        authorization_loss_signal: BatchAuthorizationLossSignal | None = None,
    ) -> BulkVerificationReport:
        """Verify many artifact signatures concurrently and summarize verifier outcomes."""
        ids = (
            self._iter_artifact_ids_lazy()
            if artifact_ids is None
            else _iter_canonical_artifact_ids(artifact_ids)
        )
        return _verify_all_signatures(
            verifier=verifier,
            artifact_ids=ids,
            max_workers=max_workers,
            strict_identity=strict_identity,
            verify_one=lambda aid, v, strict: self.verify_signature(
                aid,
                v,
                strict_identity=strict,
            ),
            pending_window=pending_window,
            cancel_event=cancel_event,
            authorization_loss_signal=authorization_loss_signal,
        )

    def _transaction_stage_relative(self, operation_id: str, name: str) -> str:
        return (
            (self._coordinator.transaction_root / "stage" / operation_id / name)
            .relative_to(self.root)
            .as_posix()
        )

    def _ensure_transaction_stage(
        self,
        *,
        operation_id: str,
        name: str,
        recorded_path: object,
        data: bytes,
        expected_sha256: str,
        final_path: Path,
    ) -> Path | None:
        expected_relative = self._transaction_stage_relative(operation_id, name)
        if recorded_path != expected_relative:
            raise ArtifactIntegrityError("CAS transaction stage reference mismatch")
        stage_path = self.root / expected_relative
        if self._ownership_index._path_has_symlink_component(stage_path):
            raise ArtifactIntegrityError("CAS transaction stage path crosses a symlink")
        if stage_path.is_symlink():
            raise ArtifactIntegrityError("CAS transaction stage member is a symlink")
        if stage_path.exists():
            if not stage_path.is_file() or _file_content_hash(stage_path) != (
                expected_sha256.removeprefix("sha256:")
            ):
                raise ArtifactIntegrityError("CAS transaction stage digest mismatch")
            return stage_path
        if final_path.exists():
            if (
                final_path.is_symlink()
                or not final_path.is_file()
                or _file_content_hash(final_path) != expected_sha256.removeprefix("sha256:")
            ):
                raise ArtifactIntegrityError("CAS transaction final member mismatch")
            return None
        return self._stage_transaction_member(operation_id, name, data)

    def _record_transaction_claims(
        self,
        artifact_id: ArtifactID,
        intent: dict[str, Any],
        *,
        lease: _ArtifactTransactionLease,
    ) -> None:
        owner = intent["owner"]
        if owner is None:
            return
        claims = intent["claims"]
        if claims["default_owner"]:
            self._ownership_index.record_owner(
                artifact_id,
                tenant_id=owner["tenant_id"],
                cell_id=owner["cell_id"],
                writer="FileSystemCAS",
                _lease=lease,
            )
        if claims["blob_reader"]:
            self._ownership_index.record_blob_reader(
                artifact_id,
                tenant_id=owner["tenant_id"],
                cell_id=owner["cell_id"],
                writer="FileSystemCAS",
                _lease=lease,
            )
        for profile_sha256 in claims["view_owners"]:
            self._ownership_index.record_view_owner(
                artifact_id,
                profile_sha256,
                tenant_id=owner["tenant_id"],
                cell_id=owner["cell_id"],
                writer="FileSystemCAS",
                _lease=lease,
            )

    def _resume_publish_transaction(
        self,
        *,
        intent: dict[str, Any],
        data: bytes,
        opts: PutOptions,
        artifact_id: ArtifactID,
        sha: str,
        owner: _ResolvedOwner | None,
        lease: _ArtifactTransactionLease,
        return_selected_profile: bool,
    ) -> tuple[bool, str | None, str, DetachedSignature | None, Exception | None]:
        """Resume an exact write and return its profile and pre-admitted signature."""
        if (
            intent["schema_version"]
            not in {
                "policyos.artifact_ownership_transaction_intent.v2",
                _TRANSACTION_INTENT_SCHEMA_V3,
            }
            or intent["mode"] != "publish"
            or intent["owner"] != owner
            or intent["blob_sha256"] != "sha256:" + sha
        ):
            raise ArtifactTransactionPendingError(artifact_id, surface="artifact")

        created_at = datetime.fromisoformat(intent["manifest_created_at"])
        manifest = self._manifests.build(
            artifact_id=artifact_id,
            data=data,
            sha=sha,
            opts=opts,
            created_at=created_at,
        )
        manifest_bytes = self._manifests.to_bytes(manifest)
        profile_sha256 = self._manifests.profile_sha256(manifest)
        views = intent["views"]
        selected = [view for view in views if view["selector"] == profile_sha256]
        if len(selected) != 1 or selected[0]["manifest_profile_sha256"] != profile_sha256:
            raise ArtifactTransactionPendingError(artifact_id, surface="artifact")
        selected_spec = selected[0]
        manifest_sha256 = content_hash(manifest_bytes, prefix=True)
        default_specs = [view for view in views if view["selector"] == "default"]
        if len(default_specs) > 1 or len(views) != 1 + len(default_specs):
            raise ArtifactTransactionPendingError(artifact_id, surface="artifact")
        default_spec = default_specs[0] if default_specs else None

        for spec in views:
            if spec["manifest_stage"] is None:
                continue
            if (
                spec["manifest_profile_sha256"] != profile_sha256
                or spec["manifest_sha256"] != manifest_sha256
            ):
                raise ArtifactTransactionPendingError(artifact_id, surface="artifact")

        claims = intent["claims"]
        if owner is None:
            expected_claims = {
                "default_owner": False,
                "blob_reader": False,
                "view_owners": [],
            }
        else:
            default_was_created = (
                default_spec is not None and default_spec["manifest_stage"] is not None
            )
            already_default_owner = self._ownership_index.is_owned_by(
                artifact_id,
                tenant_id=owner["tenant_id"],
                cell_id=owner["cell_id"],
            )
            expected_claims = {
                "default_owner": bool(default_was_created or already_default_owner),
                "blob_reader": not default_was_created,
                "view_owners": [profile_sha256],
            }
        expected_affected = {
            "ambient_artifact": bool(
                intent["blob_stage"] is not None
                or (default_spec is not None and default_spec["manifest_stage"] is not None)
            ),
            "manifest_profiles": (
                [profile_sha256]
                if selected_spec["manifest_stage"] is not None or owner is not None
                else []
            ),
            "signature_profiles": [],
        }
        if claims != expected_claims or intent["affected"] != expected_affected:
            raise ArtifactTransactionPendingError(artifact_id, surface="artifact")

        blob_path, default_manifest_path = self._paths(artifact_id)
        if default_spec is None or default_spec["manifest_profile_sha256"] != profile_sha256:
            reference_profile = profile_sha256
        else:
            reference_profile = None
        selected_ref_profile = profile_sha256 if return_selected_profile else reference_profile
        signing_ref = ArtifactRef(
            artifact_id=artifact_id,
            kind=opts.kind,
            media_type=opts.media_type,
            manifest_profile_sha256=selected_ref_profile,
        )
        signing_manifest_path = self._manifest_path_for_ref(artifact_id, selected_ref_profile)
        signing_manifest_bytes = (
            signing_manifest_path.read_bytes()
            if signing_manifest_path.is_file()
            else manifest_bytes
        )
        prepared_signature, signing_error = self._prepare_sign_on_put(
            signing_ref,
            data=data,
            manifest_bytes=signing_manifest_bytes,
        )
        storage_members = [
            self._storage_member(
                blob_path,
                sha256=sha,
                byte_size=len(data),
            )
        ]
        for spec in views:
            final_path = (
                default_manifest_path
                if spec["selector"] == "default"
                else self._layout.view_manifest_path(artifact_id, profile_sha256)
            )
            storage_members.append(
                self._storage_member(
                    final_path,
                    sha256=str(spec["manifest_sha256"]),
                    byte_size=len(manifest_bytes),
                )
            )
        if prepared_signature is not None:
            signature_bytes = prepared_signature.model_dump_json(
                by_alias=True,
                exclude_none=True,
                indent=2,
            ).encode("utf-8")
            signature_path = self._sig_path(artifact_id, selected_ref_profile)
            storage_members.append(
                self._storage_member(
                    signature_path,
                    sha256=hashlib.sha256(signature_bytes).hexdigest(),
                    byte_size=len(signature_bytes),
                )
            )
        self._admit_storage_members(storage_members)

        blob_stage = (
            self._ensure_transaction_stage(
                operation_id=intent["operation_id"],
                name="blob.stage",
                recorded_path=intent["blob_stage"],
                data=data,
                expected_sha256="sha256:" + sha,
                final_path=blob_path,
            )
            if intent["blob_stage"] is not None
            else None
        )
        if intent["blob_stage"] is None and not blob_path.is_file():
            raise ArtifactIntegrityError("CAS transaction blob stage is unavailable")
        self._publish_transaction_member(
            blob_stage,
            blob_path,
            expected_sha256="sha256:" + sha,
        )

        for spec in views:
            selector = spec["selector"]
            if selector == "default":
                final_path = default_manifest_path
                stage_name = "manifest-default.stage"
            else:
                final_path = self._layout.view_manifest_path(artifact_id, profile_sha256)
                stage_name = "manifest-view.stage"
            self._prepare_import_destination(
                final_path,
                member=final_path.relative_to(self.root).as_posix(),
            )
            recorded_stage = spec["manifest_stage"]
            stage_path: Path | None = None
            if recorded_stage is not None:
                stage_path = self._ensure_transaction_stage(
                    operation_id=intent["operation_id"],
                    name=stage_name,
                    recorded_path=recorded_stage,
                    data=manifest_bytes,
                    expected_sha256=spec["manifest_sha256"],
                    final_path=final_path,
                )
            elif not final_path.is_file():
                raise ArtifactIntegrityError("CAS transaction manifest stage is unavailable")
            self._publish_transaction_member(
                stage_path,
                final_path,
                expected_sha256=spec["manifest_sha256"],
            )

        self._record_transaction_claims(artifact_id, intent, lease=lease)
        if not self._ownership_index._intent_completion_is_recomputed(intent):
            raise ArtifactIntegrityError(
                "artifact_transaction_owner_generation_or_bytes_unverified"
            )
        committed_intent = dict(intent)
        committed_intent["status"] = "committed"
        self._ownership_index.write_transaction_intent(
            artifact_id,
            committed_intent,
            lease=lease,
        )
        self._ownership_index.remove_transaction_intent(artifact_id, lease=lease)
        self._remove_transaction_stage(intent["operation_id"])

        return (
            intent["blob_stage"] is None,
            reference_profile,
            profile_sha256,
            prepared_signature,
            signing_error,
        )

    def _put_blob_and_manifest_once(
        self,
        *,
        data: bytes,
        opts: PutOptions,
        aid: ArtifactID,
        sha: str,
        return_selected_profile: bool,
        _json_write_admission: _PreparedCoreJsonWrite | None = None,
    ) -> tuple[bool, str | None, str, DetachedSignature | None, Exception | None]:
        """Publish one blob/view and return its profiles and pre-admitted signature."""
        if _json_write_admission is not None:
            from .owned_json import _validate_prepared_core_json_write

            admitted_options = _validate_prepared_core_json_write(self, _json_write_admission)
            if admitted_options != opts:
                raise CanonicalProfileRefusalError("core_json_writer_publication_options_mismatch")
        blob_path, default_manifest_path = self._paths(aid)

        def existing_manifest(path: Path) -> tuple[bytes, ArtifactManifest]:
            if _json_write_admission is None:
                return path.read_bytes(), self._manifests.read(path)
            maximum = _json_write_admission.policy.read_limits.max_manifest_bytes
            raw = self._read_cas_file_no_follow(
                path, member="manifest", max_bytes=maximum, raise_read_limit=True
            )
            return raw, ArtifactManifest.model_validate_json(raw)

        with self._coordinator.artifact_lease(aid, exclusive=True) as lease:
            if _json_write_admission is not None:
                # This first bounded cohort does not qualify recovery. Refuse
                # before reading/cleaning/resuming an intent, including a
                # committed one; legacy publication retains its recovery law.
                intent_path = self._ownership_index._transaction_intent_path(aid)
                if intent_path.exists() or intent_path.is_symlink():
                    raise CanonicalProfileRefusalError(
                        "core_json_writer_pending_transaction_unqualified"
                    )
            # Input ownership is mutable owner-generation state. Re-evaluate it
            # under the publication lease immediately before deriving selectors
            # and durable claims; the earlier public-boundary check is only a
            # fast rejection path.
            self._require_input_owners(opts)
            tenant_id: str | None = None
            cell_id: str | None = None
            if self._ownership_enforced:
                tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)
            owner: _ResolvedOwner | None = (
                {"tenant_id": tenant_id, "cell_id": cell_id}
                if self._ownership_enforced and tenant_id is not None
                else None
            )
            self._require_bound_context_for_owner(opts.tenant_context, owner)
            prior_intent = self._ownership_index._read_transaction_intent(aid)
            if prior_intent is not None:
                if self._ownership_index._committed_intent_matches_current_state(prior_intent):
                    self._ownership_index.remove_transaction_intent(aid, lease=lease)
                    self._remove_transaction_stage(prior_intent["operation_id"])
                else:
                    return self._resume_publish_transaction(
                        intent=prior_intent,
                        data=data,
                        opts=opts,
                        artifact_id=aid,
                        sha=sha,
                        owner=owner,
                        lease=lease,
                        return_selected_profile=return_selected_profile,
                    )
            self._ownership_index.require_no_pending_transaction(aid)
            self._require_unclaimed_target_if_unscoped(aid, operation="write")
            self._validate_import_destination(blob_path, member=blob_path.name)
            self._validate_import_destination(
                default_manifest_path,
                member=default_manifest_path.name,
            )

            blob_preexisted = blob_path.exists()
            if blob_preexisted:
                if _json_write_admission is None:
                    existing_hash = _file_content_hash(blob_path)
                else:
                    existing_blob = self._read_cas_file_no_follow(
                        blob_path, member="blob", max_bytes=len(data), raise_read_limit=True
                    )
                    existing_hash = content_hash(existing_blob)
                if existing_hash != sha:
                    raise ArtifactIntegrityError(f"Blob sha256 mismatch for {aid}")

            manifest = self._manifests.build(
                artifact_id=aid,
                data=data,
                sha=sha,
                opts=opts,
            )
            if _json_write_admission is not None:
                from .owned_json import _preflight_prepared_core_json_manifest

                _preflight_prepared_core_json_manifest(self, _json_write_admission, manifest)
            manifest_bytes = self._manifests.to_bytes(manifest)
            if _json_write_admission is not None:
                from .owned_json import _validate_prepared_core_json_manifest

                _validate_prepared_core_json_manifest(
                    self, _json_write_admission, manifest, manifest_bytes
                )
            profile_sha256 = self._manifests.profile_sha256(manifest)

            default_owner_admitted = False
            skip_default_manifest = getattr(opts, "child_release", None) is not None
            if owner is not None:
                default_owner_admitted = self._ownership_index.is_owned_by(
                    aid,
                    tenant_id=owner["tenant_id"],
                    cell_id=owner["cell_id"],
                )
                skip_default_manifest = skip_default_manifest or (
                    not default_owner_admitted
                    and (
                        default_manifest_path.exists()
                        or self._ownership_index.has_any_tenant_claim(aid)
                    )
                )

            default_bytes: bytes | None = None
            default_profile_sha256: str | None = None
            if not skip_default_manifest and default_manifest_path.exists():
                default_bytes, default_manifest = existing_manifest(default_manifest_path)
                _validate_manifest_identity(aid, default_manifest)
                _validate_read_integrity(aid, data, default_manifest)
                default_profile_sha256 = self._manifests.profile_sha256(default_manifest)

            view_path = self._layout.view_manifest_path(aid, profile_sha256)
            self._validate_import_destination(view_path, member=view_path.name)
            view_bytes: bytes | None = None
            if view_path.exists():
                view_bytes, existing_view = existing_manifest(view_path)
                _validate_manifest_identity(aid, existing_view)
                _validate_read_integrity(aid, data, existing_view)
                if self._manifests.profile_projection(existing_view) != (
                    self._manifests.profile_projection(manifest)
                ):
                    raise ArtifactIntegrityError(f"Manifest profile digest collision for {aid}")

            will_create_default = not skip_default_manifest and default_bytes is None
            will_create_view = view_bytes is None
            operation_id = uuid.uuid4().hex
            blob_stage_rel = (
                None
                if blob_preexisted
                else self._transaction_stage_relative(
                    operation_id,
                    "blob.stage",
                )
            )
            default_stage_rel = (
                self._transaction_stage_relative(operation_id, "manifest-default.stage")
                if will_create_default
                else None
            )
            view_stage_rel = (
                self._transaction_stage_relative(operation_id, "manifest-view.stage")
                if will_create_view
                else None
            )
            intent_views: list[dict[str, object]] = []
            if not skip_default_manifest:
                expected_default_bytes = default_bytes or manifest_bytes
                intent_views.append(
                    {
                        "selector": "default",
                        "manifest_profile_sha256": (default_profile_sha256 or profile_sha256),
                        "manifest_sha256": content_hash(expected_default_bytes, prefix=True),
                        "manifest_stage": default_stage_rel,
                    }
                )
            expected_view_bytes = view_bytes or manifest_bytes
            intent_views.append(
                {
                    "selector": profile_sha256,
                    "manifest_profile_sha256": profile_sha256,
                    "manifest_sha256": content_hash(expected_view_bytes, prefix=True),
                    "manifest_stage": view_stage_rel,
                }
            )
            if owner is None:
                claims: dict[str, object] = {
                    "default_owner": False,
                    "blob_reader": False,
                    "view_owners": [],
                }
            else:
                claims = {
                    "default_owner": bool(will_create_default or default_owner_admitted),
                    "blob_reader": not will_create_default,
                    "view_owners": [profile_sha256],
                }
            affected_profiles = [profile_sha256] if will_create_view or owner is not None else []
            intent: dict[str, object] = {
                "schema_version": _TRANSACTION_INTENT_SCHEMA_V3,
                "status": "pending",
                "mode": "publish",
                "operation_id": operation_id,
                "artifact_id": str(aid),
                "owner": owner,
                "blob_sha256": "sha256:" + sha,
                "blob_stage": blob_stage_rel,
                "views": intent_views,
                "claims": claims,
                "affected": {
                    "ambient_artifact": bool(not blob_preexisted or will_create_default),
                    "manifest_profiles": affected_profiles,
                    "signature_profiles": [],
                },
                "manifest_created_at": manifest.created_at.isoformat(),
                "signatures": [],
                "request_sha256": "",
            }
            intent["request_sha256"] = self._ownership_index._transaction_request_digest(intent)
            if skip_default_manifest:
                reference_profile = profile_sha256
            elif default_profile_sha256 is None:
                reference_profile = None
            else:
                reference_profile = (
                    profile_sha256 if profile_sha256 != default_profile_sha256 else None
                )
            selected_ref_profile = profile_sha256 if return_selected_profile else reference_profile
            signing_ref = ArtifactRef(
                artifact_id=aid,
                kind=opts.kind,
                media_type=opts.media_type,
                manifest_profile_sha256=selected_ref_profile,
            )
            if selected_ref_profile is None and default_bytes is not None:
                signing_manifest_bytes = default_bytes
            elif selected_ref_profile == profile_sha256 and view_bytes is not None:
                signing_manifest_bytes = view_bytes
            else:
                signing_manifest_bytes = manifest_bytes
            prepared_signature, signing_error = self._prepare_sign_on_put(
                signing_ref,
                data=data,
                manifest_bytes=signing_manifest_bytes,
            )
            storage_members: list[_CASStorageMember] = []
            if not blob_preexisted:
                storage_members.append(
                    self._storage_member(blob_path, sha256=sha, byte_size=len(data))
                )
            if will_create_default:
                storage_members.append(
                    self._storage_member(
                        default_manifest_path,
                        sha256=hashlib.sha256(manifest_bytes).hexdigest(),
                        byte_size=len(manifest_bytes),
                    )
                )
            if will_create_view:
                storage_members.append(
                    self._storage_member(
                        view_path,
                        sha256=hashlib.sha256(manifest_bytes).hexdigest(),
                        byte_size=len(manifest_bytes),
                    )
                )
            if prepared_signature is not None:
                signature_bytes = prepared_signature.model_dump_json(
                    by_alias=True,
                    exclude_none=True,
                    indent=2,
                ).encode("utf-8")
                signature_path = self._sig_path(aid, selected_ref_profile)
                storage_members.append(
                    self._storage_member(
                        signature_path,
                        sha256=hashlib.sha256(signature_bytes).hexdigest(),
                        byte_size=len(signature_bytes),
                    )
                )
            self._admit_storage_members(storage_members)
            for path in (blob_path, default_manifest_path, view_path):
                self._prepare_import_destination(
                    path,
                    member=path.relative_to(self.root).as_posix(),
                )
            self._ownership_index.write_transaction_intent(aid, intent, lease=lease)

            try:
                blob_stage = (
                    self._stage_transaction_member(operation_id, "blob.stage", data)
                    if blob_stage_rel is not None
                    else None
                )
                default_stage = (
                    self._stage_transaction_member(
                        operation_id,
                        "manifest-default.stage",
                        manifest_bytes,
                    )
                    if default_stage_rel is not None
                    else None
                )
                view_stage = (
                    self._stage_transaction_member(
                        operation_id,
                        "manifest-view.stage",
                        manifest_bytes,
                    )
                    if view_stage_rel is not None
                    else None
                )
                self._publish_transaction_member(
                    blob_stage,
                    blob_path,
                    expected_sha256="sha256:" + sha,
                )
                if not skip_default_manifest:
                    self._publish_transaction_member(
                        default_stage,
                        default_manifest_path,
                        expected_sha256=str(intent_views[0]["manifest_sha256"]),
                    )
                self._publish_transaction_member(
                    view_stage,
                    view_path,
                    expected_sha256=str(intent_views[-1]["manifest_sha256"]),
                )
                self._record_transaction_claims(aid, intent, lease=lease)
                if not self._ownership_index._intent_completion_is_recomputed(intent):
                    raise ArtifactIntegrityError(
                        "artifact_transaction_owner_generation_or_bytes_unverified"
                    )
                committed_intent = dict(intent)
                committed_intent["status"] = "committed"
                self._ownership_index.write_transaction_intent(
                    aid,
                    committed_intent,
                    lease=lease,
                )
                self._ownership_index.remove_transaction_intent(aid, lease=lease)
                self._remove_transaction_stage(operation_id)
            except BaseException:
                # Keep the durable pending intent; visible state is never rolled back.
                raise

            return (
                blob_preexisted,
                reference_profile,
                profile_sha256,
                prepared_signature,
                signing_error,
            )

    def put_bytes(
        self,
        data: bytes,
        opts: PutOptions,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        """Store bytes, optionally returning the exact profile selected by this write.

        The default preserves the historical profileless selector for the default view.
        When requested, the returned profile comes from the manifest computed and committed
        inside this write's artifact lease; no later default-view read is used to infer it.
        """
        _validate_return_selected_profile(return_selected_profile)
        sha = content_hash(data)
        aid = ArtifactID.from_sha256_hex(sha)
        self._require_input_owners(opts)

        if not self._hpc_enabled or self._tracer is None:
            (
                _deduplicated,
                default_ref_profile,
                selected_profile,
                prepared_signature,
                signing_error,
            ) = self._put_blob_and_manifest_once(
                data=data,
                opts=opts,
                aid=aid,
                sha=sha,
                return_selected_profile=return_selected_profile,
            )
            ref = ArtifactRef(
                artifact_id=aid,
                kind=opts.kind,
                media_type=opts.media_type,
                manifest_profile_sha256=(
                    selected_profile if return_selected_profile else default_ref_profile
                ),
            )
            self._finish_sign_on_put(ref, prepared_signature, signing_error)
            return ref

        short_id = f"{aid.hex[:16]}..."
        byte_size = len(data)
        with self._tracer.start_as_current_span(
            "cas.put",
            attributes={
                "cas.artifact_id": short_id,
                "cas.operation": "write",
                "cas.kind": opts.kind,
                "cas.byte_size": byte_size,
            },
        ) as span:
            start = time.perf_counter()
            (
                deduplicated,
                default_ref_profile,
                selected_profile,
                prepared_signature,
                signing_error,
            ) = self._put_blob_and_manifest_once(
                data=data,
                opts=opts,
                aid=aid,
                sha=sha,
                return_selected_profile=return_selected_profile,
            )

            duration = time.perf_counter() - start

            if self._metrics and self._metrics.artifact_operations_total:
                self._metrics.artifact_operations_total.add(
                    1, {"operation": "write", "kind": opts.kind}
                )
            if self._metrics and self._metrics.artifact_cache_hits_total and deduplicated:
                self._metrics.artifact_cache_hits_total.add(1, {"kind": "dedup"})
            if self._metrics and self._metrics.artifact_cache_misses_total and not deduplicated:
                self._metrics.artifact_cache_misses_total.add(1, {"kind": "dedup"})
            if self._metrics and self._metrics.artifact_io_bytes:
                self._metrics.artifact_io_bytes.record(
                    byte_size, {"operation": "write", "kind": opts.kind}
                )
            if self._metrics and self._metrics.artifact_io_duration_seconds:
                self._metrics.artifact_io_duration_seconds.record(
                    duration,
                    {
                        "operation": "write",
                        "kind": opts.kind,
                        "cache_hit": "true" if deduplicated else "false",
                    },
                )

            span.set_attribute("cas.deduplicated", deduplicated)
            span.set_attribute("cas.duration_seconds", duration)

            ref = ArtifactRef(
                artifact_id=aid,
                kind=opts.kind,
                media_type=opts.media_type,
                manifest_profile_sha256=(
                    selected_profile if return_selected_profile else default_ref_profile
                ),
            )
            self._finish_sign_on_put(ref, prepared_signature, signing_error)
            return ref

    def _put_bounded_core_json_write(self, prepared: _PreparedCoreJsonWrite) -> ArtifactRef:
        """Publish only Core's sealed owner/vector/reader-admitted representation."""
        from .owned_json import _validate_prepared_core_json_write

        opts = _validate_prepared_core_json_write(self, prepared)
        data = prepared.data
        sha = content_hash(data)
        aid = ArtifactID.from_sha256_hex(sha)
        self._require_input_owners(opts)
        _deduplicated, _default, profile, _signature, _signing_error = (
            self._put_blob_and_manifest_once(
                data=data,
                opts=opts,
                aid=aid,
                sha=sha,
                return_selected_profile=True,
                _json_write_admission=prepared,
            )
        )
        return ArtifactRef(
            artifact_id=aid,
            kind=opts.kind,
            media_type=opts.media_type,
            manifest_profile_sha256=profile,
        )

    def put_json(
        self,
        obj: object,
        opts: PutOptions,
        canon_spec: CanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        """Canonicalize JSON and optionally return the exact profile from this write."""
        _validate_return_selected_profile(return_selected_profile)
        canon_spec = _admit_canon_spec(
            canon_spec, CanonSpec, violation_type=CanonViolation, artifact_writer=True
        )
        canon = _canon_info_for_spec(canon_spec, opts.canon, violation_type=CanonViolation)
        data = to_canonical_bytes(obj, canon_spec)
        _validate_core_json_payload_conformance(data, canon_spec)
        opts2 = PutOptions(
            kind=opts.kind,
            media_type="application/json",
            schema=opts.schema,
            producer=opts.producer,
            env=opts.env,
            inputs=opts.inputs,
            canon=canon,
            governance=getattr(opts, "governance", None),
            tenant_context=getattr(opts, "tenant_context", None),
            same_input_closure=getattr(opts, "same_input_closure", None),
            authority=getattr(opts, "authority", None),
            warnings=getattr(opts, "warnings", None),
            child_release=getattr(opts, "child_release", None),
        )
        if return_selected_profile:
            return self.put_bytes(data, opts2, return_selected_profile=True)
        return self.put_bytes(data, opts2)

    @_transactional_read()
    def verify(self, artifact_id: ArtifactID | ArtifactRef | str) -> VerificationReport:
        """Check blob and exact selected manifest view integrity."""
        aid, profile_sha256, ref = _artifact_reference(artifact_id)
        if profile_sha256 is None:
            self._require_artifact_owner(aid, operation="verify", ref=ref)
        else:
            self._require_blob_owner(aid, operation="verify", ref=ref)
            self._require_manifest_view_owner(
                aid,
                profile_sha256,
                operation="verify_manifest",
                ref=ref,
            )
        blob, _default_manifest = self._paths(aid)
        manp = self._manifest_path_for_ref(aid, profile_sha256)
        if not self._hpc_enabled or self._tracer is None:
            report = _verify_filesystem_artifact(aid, blob_path=blob, manifest_path=manp)
        else:
            short_id = f"{aid.hex[:16]}..."
            with self._tracer.start_as_current_span(
                "cas.verify",
                attributes={"cas.artifact_id": short_id},
            ) as span:
                report = _verify_filesystem_artifact(
                    aid,
                    blob_path=blob,
                    manifest_path=manp,
                )
                span.set_attribute("cas.verified", report.ok)
                if report.byte_size is not None:
                    span.set_attribute("cas.byte_size", report.byte_size)

        if report.ok:
            from .child_release import ChildReleaseUnavailableError

            try:
                self.get_manifest(artifact_id)
            except ChildReleaseUnavailableError:
                raise
            except (OSError, ValueError) as exc:
                return report.model_copy(update={"ok": False, "error": str(exc)})
        return report

    def _verify_staged_artifact(
        self,
        artifact_id: ArtifactID | ArtifactRef,
        staging_root: Path,
    ) -> VerificationReport:
        """Verify one staged pair while retaining this store's failure telemetry."""
        aid, profile_sha256, ref = _artifact_reference(artifact_id)
        blob, _default_manifest = self._paths(aid)
        manifest = self._manifest_path_for_ref(aid, profile_sha256)
        staged_blob = staging_root / blob.relative_to(self.root)
        staged_manifest = staging_root / manifest.relative_to(self.root)
        actual_sha = None
        byte_size = None
        try:
            if staged_blob.is_symlink() or staged_manifest.is_symlink():
                raise ArtifactIntegrityError("staged CAS member crosses a symlink")
            if not staged_blob.is_file() or not staged_manifest.is_file():
                raise FileNotFoundError("staged CAS member missing")
            actual_sha = _file_content_hash(staged_blob)
            byte_size = staged_blob.stat().st_size
            manifest_bytes = staged_manifest.read_bytes()
            manifest_model = ArtifactManifest.model_validate_json(manifest_bytes)
            _validate_manifest_identity(aid, manifest_model)
            if actual_sha != aid.hex:
                raise ArtifactIntegrityError(f"Blob sha256 mismatch for {aid}")
            if manifest_model.byte_size != byte_size:
                raise ArtifactIntegrityError(f"Manifest byte size mismatch for {aid}")
            if profile_sha256 is not None and (
                self._manifests.profile_sha256(manifest_model) != profile_sha256
            ):
                raise ArtifactIntegrityError(f"Selected manifest profile mismatch for {aid}")
            if ref is not None and (
                ref.kind != manifest_model.kind or ref.media_type != manifest_model.media_type
            ):
                raise ArtifactIntegrityError(
                    f"Artifact reference type does not match selected manifest for {aid}"
                )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            self._record_integrity_failure(reason=type(exc).__name__)
            return VerificationReport(
                ok=False,
                artifact_id=str(aid),
                expected_sha256_hex=aid.hex,
                actual_sha256_hex=actual_sha,
                byte_size=byte_size,
                error=str(exc),
            )
        return VerificationReport(
            ok=True,
            artifact_id=str(aid),
            expected_sha256_hex=aid.hex,
            actual_sha256_hex=actual_sha,
            byte_size=byte_size,
        )

    def _validate_import_destination(self, path: Path, *, member: str) -> None:
        """Validate a final member path without creating directories or files."""
        if self.root.is_symlink():
            raise ArtifactIntegrityError("CAS root must not be a symlink")
        try:
            relative = path.relative_to(self.root)
        except ValueError as exc:
            raise ArtifactIntegrityError(f"CAS member escapes root: {member}") from exc

        current = self.root
        for component in relative.parts[:-1]:
            current = current / component
            if current.is_symlink():
                raise ArtifactIntegrityError(f"CAS member crosses a symlink: {member}")
            if current.exists() and not current.is_dir():
                raise ArtifactIntegrityError(f"CAS member parent is not a directory: {member}")

        if path.is_symlink():
            raise ArtifactIntegrityError(f"CAS member must not be a symlink: {member}")
        if path.exists() and not path.is_file():
            raise ArtifactIntegrityError(f"CAS member is not a regular file: {member}")

    def _prepare_import_destination(self, path: Path, *, member: str) -> None:
        """Create safe parent components and reject symlinked CAS paths."""
        if self.root.is_symlink():
            raise ArtifactIntegrityError("CAS root must not be a symlink")
        try:
            relative = path.relative_to(self.root)
        except ValueError as exc:
            raise ArtifactIntegrityError(f"CAS member escapes root: {member}") from exc

        current = self.root
        for component in relative.parts[:-1]:
            current = current / component
            if current.is_symlink():
                raise ArtifactIntegrityError(f"CAS member crosses a symlink: {member}")
            if current.exists():
                if not current.is_dir():
                    raise ArtifactIntegrityError(f"CAS member parent is not a directory: {member}")
            else:
                try:
                    current.mkdir()
                except FileExistsError:
                    if not current.is_dir():
                        raise ArtifactIntegrityError(
                            f"CAS member parent is not a directory: {member}"
                        ) from None
                _atomic_write_module.fsync_directory(current.parent)
                if current.is_symlink() or not current.is_dir():
                    raise ArtifactIntegrityError(f"CAS member parent is unsafe: {member}")

        if path.is_symlink():
            raise ArtifactIntegrityError(f"CAS member must not be a symlink: {member}")
        if path.exists() and not path.is_file():
            raise ArtifactIntegrityError(f"CAS member is not a regular file: {member}")

    @staticmethod
    def _import_manifest_profile(manifest: ArtifactManifest) -> dict[str, object]:
        """Return immutable manifest profile fields, excluding identity/time fields."""
        return manifest.model_dump(
            mode="json",
            by_alias=True,
            exclude={"artifact_id", "byte_size", "created_at", "integrity"},
        )

    def _stage_transaction_member(
        self,
        operation_id: str,
        name: str,
        data: bytes,
    ) -> Path:
        """Write one fsynced member beneath an owner-private same-filesystem stage."""
        stage_directory = self._coordinator.transaction_root / "stage" / operation_id
        if self._ownership_index._path_has_symlink_component(stage_directory):
            raise ArtifactIntegrityError("CAS transaction stage path crosses a symlink")
        _ensure_directory_durable(stage_directory)
        stage_path = stage_directory / name
        if stage_path.is_symlink() or stage_path.exists():
            raise ArtifactIntegrityError("CAS transaction stage path already exists")
        self._files.write_once(stage_path, data, durable_parent=True)
        if not stage_path.is_file() or stage_path.is_symlink():
            raise ArtifactIntegrityError("CAS transaction stage member is unsafe")
        if stage_path.stat().st_dev != self.root.stat().st_dev:
            raise ArtifactIntegrityError("CAS transaction stage is on another filesystem")
        return stage_path

    def _publish_transaction_member(
        self,
        stage_path: Path | None,
        final_path: Path,
        *,
        expected_sha256: str,
    ) -> bool:
        """Publish one immutable staged member and require its parent sync."""
        member = final_path.relative_to(self.root).as_posix()
        self._prepare_import_destination(final_path, member=member)
        if stage_path is not None:
            if (
                stage_path.is_symlink()
                or not stage_path.is_file()
                or stage_path.stat().st_dev != final_path.parent.stat().st_dev
            ):
                raise ArtifactIntegrityError("CAS transaction stage member is unsafe")
            if _file_content_hash(stage_path) != expected_sha256.removeprefix("sha256:"):
                raise ArtifactIntegrityError("CAS transaction stage digest mismatch")

        created = False
        if final_path.exists():
            if _file_content_hash(final_path) != expected_sha256.removeprefix("sha256:"):
                raise ArtifactIntegrityError(f"Immutable CAS member conflicts: {member}")
        else:
            if stage_path is None:
                raise ArtifactIntegrityError(f"CAS transaction stage is missing: {member}")
            try:
                os.link(stage_path, final_path)
                created = True
            except FileExistsError:
                if (
                    final_path.is_symlink()
                    or not final_path.is_file()
                    or _file_content_hash(final_path) != expected_sha256.removeprefix("sha256:")
                ):
                    raise ArtifactIntegrityError(
                        f"Immutable CAS member conflicts: {member}"
                    ) from None

        try:
            # This sync is strict even for a pre-existing member: a new owner
            # generation must not outrun the directory entry it relies on.
            _atomic_write_module.fsync_directory(final_path.parent)
        except OSError as exc:
            raise _AtomicFileDurabilityError(
                "CAS member exists but its parent directory sync failed",
                replaced=True,
            ) from exc
        if (
            final_path.is_symlink()
            or not final_path.is_file()
            or _file_content_hash(final_path) != expected_sha256.removeprefix("sha256:")
        ):
            raise ArtifactIntegrityError(f"CAS member digest mismatch: {member}")
        return created

    def _remove_transaction_stage(self, operation_id: str) -> None:
        stage_root = self._coordinator.transaction_root / "stage"
        stage_directory = stage_root / operation_id
        if stage_directory.is_symlink() or not stage_directory.exists():
            return
        if not stage_directory.is_dir():
            return
        if self._ownership_index._walk_private_regular_files(stage_directory) is None:
            return
        shutil.rmtree(stage_directory)
        _atomic_write_module.fsync_directory(stage_root)

    def _stage_import_source(
        self,
        *,
        operation_id: str,
        recorded_path: object,
        source_path: Path,
        final_path: Path,
        expected_sha256: str,
        resume: bool,
    ) -> Path | None:
        """Adopt one verified importer stage by hard link after durable intent."""
        if not isinstance(recorded_path, str):
            raise ArtifactIntegrityError("CAS import transaction stage reference missing")
        self._ownership_index._validate_transaction_stage_path(recorded_path, operation_id)
        stage_path = self.root / recorded_path
        if self._ownership_index._path_has_symlink_component(stage_path):
            raise ArtifactIntegrityError("CAS import transaction stage crosses a symlink")
        self._prepare_import_destination(stage_path, member=recorded_path)
        if stage_path.exists() and stage_path.is_symlink():
            raise ArtifactIntegrityError("CAS import transaction stage is a symlink")

        if final_path.exists():
            if (
                final_path.is_symlink()
                or not final_path.is_file()
                or _file_content_hash(final_path) != expected_sha256.removeprefix("sha256:")
            ):
                raise ArtifactIntegrityError("CAS import final member digest mismatch")
            return None

        try:
            source_path.relative_to(self.root)
        except ValueError as exc:
            raise ArtifactIntegrityError("CAS import source escaped its owner root") from exc
        if (
            self._ownership_index._path_has_symlink_component(source_path)
            or source_path.is_symlink()
            or not source_path.is_file()
        ):
            raise ArtifactIntegrityError("CAS import source stage is not a regular file")
        source_stat = source_path.stat()
        if source_stat.st_uid != os.geteuid() or source_stat.st_dev != self.root.stat().st_dev:
            raise ArtifactIntegrityError("CAS import source stage is not owner-controlled")

        if stage_path.exists():
            if not stage_path.is_file() or _file_content_hash(stage_path) != (
                expected_sha256.removeprefix("sha256:")
            ):
                raise ArtifactIntegrityError(
                    "CAS import stage differs from the exact retry request"
                    if resume
                    else "CAS import stage already exists"
                )
        else:
            try:
                os.link(source_path, stage_path, follow_symlinks=False)
            except FileExistsError:
                if (
                    stage_path.is_symlink()
                    or not stage_path.is_file()
                    or _file_content_hash(stage_path) != expected_sha256.removeprefix("sha256:")
                ):
                    raise ArtifactIntegrityError("CAS import stage publication conflict") from None
            if stage_path.is_symlink() or not stage_path.is_file():
                raise ArtifactIntegrityError("CAS import stage publication is unsafe")
            _atomic_write_module.fsync_directory(stage_path.parent)

        if stage_path.stat().st_dev != self.root.stat().st_dev or _file_content_hash(
            stage_path
        ) != expected_sha256.removeprefix("sha256:"):
            raise ArtifactIntegrityError("CAS import staged member digest mismatch")
        return stage_path

    @staticmethod
    def _require_bound_context_for_owner(
        context: ArtifactTenantContextInfo | None,
        owner: _ResolvedOwner | None,
        *,
        require_bound: bool = False,
    ) -> None:
        """Match an optional persisted tenant/cell context to the active CAS owner."""
        if owner is None:
            return
        tenant_id = owner["tenant_id"]
        if context is None:
            if require_bound:
                raise ArtifactOwnershipError(
                    f"Import is not owned by tenant {tenant_id}: manifest has no bound context"
                )
            return
        if context.tenant_id != tenant_id:
            raise ArtifactOwnershipError("Manifest is bound to a different tenant")
        if context.cell_id != owner["cell_id"]:
            raise ArtifactOwnershipError("Manifest is bound to a different cell")

    def _require_import_input_owners(
        self,
        source_by_artifact: dict[str, dict[str, Any]],
        owner: _ResolvedOwner | None,
    ) -> None:
        """Resolve every imported lineage ref against an existing or incoming exact view."""
        if not self._ownership_enforced:
            return
        for source_info in source_by_artifact.values():
            for source_view in source_info["source_views"]:
                for raw_input_ref in source_view["manifest"].inputs:
                    input_ref = _coerce_input_ref(raw_input_ref)
                    input_id = input_ref.artifact_id
                    if owner is None:
                        self._require_blob_owner(
                            input_id,
                            operation=f"import input:{input_ref.role}",
                        )
                        self._require_manifest_view_owner(
                            input_id,
                            input_ref.manifest_profile_sha256,
                            operation=f"import input manifest:{input_ref.role}",
                        )
                        continue

                    if self._ownership_index.has_any_tenant_claim(input_id):
                        self._ownership_index.require_blob_reader(
                            input_id,
                            tenant_id=owner["tenant_id"],
                            cell_id=owner["cell_id"],
                            operation=f"import input:{input_ref.role}",
                        )
                        if input_ref.manifest_profile_sha256 is None:
                            self._ownership_index.require_owner(
                                input_id,
                                tenant_id=owner["tenant_id"],
                                cell_id=owner["cell_id"],
                                operation=f"import input manifest:{input_ref.role}",
                            )
                        else:
                            self._ownership_index.require_view_owner(
                                input_id,
                                input_ref.manifest_profile_sha256,
                                tenant_id=owner["tenant_id"],
                                cell_id=owner["cell_id"],
                                operation=f"import input manifest:{input_ref.role}",
                            )
                        continue

                    imported_input = source_by_artifact.get(input_id.hex)
                    if imported_input is None:
                        raise ArtifactOwnershipError(
                            f"Unclaimed import input {input_id} is not part of the same import"
                        )
                    source_profiles = {view["profile"] for view in imported_input["source_views"]}
                    has_default_view = any(
                        view["member"].endswith(f"{input_id.hex}.manifest.json")
                        for view in imported_input["source_views"]
                    )
                    if input_ref.manifest_profile_sha256 is None:
                        input_is_in_import = has_default_view
                    else:
                        input_is_in_import = input_ref.manifest_profile_sha256 in source_profiles
                    if not input_is_in_import:
                        raise ArtifactOwnershipError(
                            f"Import does not carry the selected input view for {input_id}"
                        )

    @contextmanager
    def _admit_import_members(
        self,
        members: dict[str, TransferMemberSnapshot],
    ) -> Iterator[TransferAdmission]:
        """Admit only exact owned views or fully measured unclaimed inputs.

        A claimed artifact can only be a byte-for-byte no-op for the exact
        default/profile view already owned by the active tenant. New scoped
        imports must carry a manifest bound to that active tenant and cell.
        The exclusive leases remain held until the caller finishes staging and
        publication, so admission cannot race an owner-generation change.
        """
        _validate_transfer_signatures(members)
        grouped: dict[str, dict[str, TransferMemberSnapshot]] = {}
        for member, snapshot in members.items():
            safe_path = _safe_member_path(member)
            artifact_id = _artifact_id_from_member(member)
            if safe_path is None or safe_path.as_posix() != member or artifact_id is None:
                raise ArtifactIntegrityError(f"Unsafe import intake member: {member}")
            if not member.endswith(".blob"):
                metadata_limit = (
                    8 * 1024 * 1024 if member.endswith(".manifest.json") else 1024 * 1024
                )
                if snapshot.metadata is None or snapshot.byte_size > metadata_limit:
                    raise ArtifactIntegrityError("CAS import metadata is unavailable or oversized")
                if hashlib.sha256(snapshot.metadata).hexdigest() != snapshot.sha256:
                    raise ArtifactIntegrityError("CAS import metadata digest mismatch")
            grouped.setdefault(str(artifact_id), {})[member] = snapshot

        lock_ids: dict[str, ArtifactID] = {}
        parsed: dict[str, list[dict[str, Any]]] = {}
        for value, artifact_members in grouped.items():
            artifact_id = ArtifactID.model_validate(value)
            lock_ids[artifact_id.hex] = artifact_id
            prefix = (
                f"artifacts/sha256/{artifact_id.hex[:2]}/"
                + f"{artifact_id.hex[2:4]}/{artifact_id.hex}"
            )
            blob = artifact_members.get(prefix + ".blob")
            if blob is None or blob.sha256 != artifact_id.hex:
                raise ArtifactIntegrityError(f"Import blob content does not match {artifact_id}")
            views: list[dict[str, Any]] = []
            for member, snapshot in sorted(artifact_members.items()):
                if not member.endswith(".manifest.json"):
                    continue
                if snapshot.metadata is None:
                    raise ArtifactIntegrityError("Import manifest bytes unavailable")
                manifest = ArtifactManifest.model_validate_json(snapshot.metadata)
                _validate_manifest_identity(artifact_id, manifest)
                if manifest.byte_size != blob.byte_size:
                    raise ArtifactIntegrityError(f"Manifest byte size mismatch for {artifact_id}")
                profile = self._manifests.profile_sha256(manifest)
                encoded_profile = _member_profile_sha256(member)
                if encoded_profile is not None and encoded_profile != profile:
                    raise ArtifactIntegrityError(
                        f"Selected manifest profile mismatch for {artifact_id}"
                    )
                for raw_input_ref in manifest.inputs:
                    input_ref = _coerce_input_ref(raw_input_ref)
                    lock_ids[input_ref.artifact_id.hex] = input_ref.artifact_id
                views.append(
                    {
                        "member": member,
                        "manifest": manifest,
                        "profile": profile,
                    }
                )
            if not views:
                raise ArtifactIntegrityError(f"Import is missing manifest views for {artifact_id}")
            parsed[value] = views

        with self._coordinator.artifact_leases(lock_ids.values(), exclusive=True):
            owner: _ResolvedOwner | None = None
            if self._ownership_enforced:
                tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)
                if tenant_id is not None:
                    owner = {"tenant_id": tenant_id, "cell_id": cell_id}
            source_by_artifact = {
                artifact_id.hex: {
                    "source_views": [
                        {
                            "member": view["member"],
                            "manifest": view["manifest"],
                            "profile": view["profile"],
                        }
                        for view in views
                    ]
                }
                for value, views in parsed.items()
                for artifact_id in (ArtifactID.model_validate(value),)
            }
            self._require_import_input_owners(source_by_artifact, owner)

            exact_refs: list[ArtifactRef] = []
            canonical_exact_refs: list[ArtifactRef] = []
            pending_artifact_ids: set[str] = set()
            for value, artifact_members in grouped.items():
                artifact_id = ArtifactID.model_validate(value)
                for view in parsed[value]:
                    self._require_bound_context_for_owner(
                        view["manifest"].tenant_context,
                        owner,
                    )
                if not self._ownership_index.has_any_tenant_claim(artifact_id):
                    pending_artifact_ids.add(value)
                    continue
                if owner is None:
                    raise ArtifactOwnershipError(
                        f"Artifact {artifact_id} import requires its current tenant owner"
                    )
                self._ownership_index.require_no_pending_transaction(artifact_id)
                for view in parsed[value]:
                    member = view["member"]
                    profile = view["profile"]
                    selected_profile = _member_profile_sha256(member)
                    claims = self._ownership_index._transaction_claims_for(
                        artifact_id,
                        tenant_id=owner["tenant_id"],
                        cell_id=owner["cell_id"],
                        manifest_profile_sha256=profile,
                    )
                    owns_view = (
                        claims["default_owner"]
                        if selected_profile is None
                        else profile in claims["view_owners"]
                    )
                    if not owns_view:
                        raise ArtifactOwnershipError(
                            f"Artifact {artifact_id} exact view is not owned by tenant "
                            f"{owner['tenant_id']}"
                        )
                    exact_refs.append(
                        ArtifactRef(
                            artifact_id=artifact_id,
                            kind=view["manifest"].kind,
                            media_type=view["manifest"].media_type,
                            manifest_profile_sha256=selected_profile,
                        )
                    )
                    canonical_exact_refs.append(
                        ArtifactRef(
                            artifact_id=artifact_id,
                            kind=view["manifest"].kind,
                            media_type=view["manifest"].media_type,
                            manifest_profile_sha256=profile,
                        )
                    )
                for member, snapshot in artifact_members.items():
                    path = self.root / Path(*member.split("/"))
                    if self._ownership_index._path_has_symlink_component(path):
                        raise ArtifactIntegrityError("Existing imported member crosses a symlink")
                    try:
                        mode = path.lstat().st_mode
                    except FileNotFoundError:
                        raise ArtifactOwnershipError(
                            "Claimed import must already contain the exact complete view"
                        ) from None
                    if not stat.S_ISREG(mode):
                        raise ArtifactIntegrityError(
                            "Existing imported member is not a regular file"
                        )
                    if self._stream_file_digest(path) != (
                        snapshot.sha256,
                        snapshot.byte_size,
                    ):
                        raise ArtifactOwnershipError(
                            "Claimed import differs from its exact owned bytes/view"
                        )
                for view in parsed[value]:
                    owned_signature = view["member"].removesuffix(".manifest.json") + ".sig"
                    if (
                        owned_signature not in artifact_members
                        and (self.root / owned_signature).exists()
                    ):
                        raise ArtifactOwnershipError(
                            "Claimed import omits its exact owned signature"
                        )
            exact_order = sorted(
                range(len(exact_refs)),
                key=lambda index: (
                    exact_refs[index].artifact_id.hex,
                    exact_refs[index].manifest_profile_sha256 or "",
                    exact_refs[index].kind,
                    exact_refs[index].media_type,
                ),
            )
            yield TransferAdmission(
                exact_refs=tuple(exact_refs[index] for index in exact_order),
                pending_artifact_ids=frozenset(pending_artifact_ids),
                canonical_exact_refs=tuple(canonical_exact_refs[index] for index in exact_order),
            )

    def _publish_staged_import(
        self,
        staging_root: Path,
        members: set[str],
        artifact_refs: set[str],
    ) -> ImportPublication:
        """Re-admit staged bytes before the durable owner transaction publishes them."""
        try:
            staging_root.relative_to(self.root)
        except ValueError as exc:
            raise ArtifactIntegrityError("CAS import stage escaped its owner root") from exc
        if self._ownership_index._path_has_symlink_component(staging_root):
            raise ArtifactIntegrityError("CAS import staging root crosses a symlink")
        intake: dict[str, TransferMemberSnapshot] = {}
        for member in sorted(members):
            safe_path = _safe_member_path(member)
            artifact_id = _artifact_id_from_member(member)
            if safe_path is None or safe_path.as_posix() != member or artifact_id is None:
                raise ArtifactIntegrityError(f"Unsafe staged member: {member}")
            path = staging_root / Path(*safe_path.parts)
            if self._ownership_index._path_has_symlink_component(path):
                raise ArtifactIntegrityError("CAS import member crosses a symlink")
            descriptor = os.open(
                path,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
            )
            with os.fdopen(descriptor, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ArtifactIntegrityError("CAS import member is not a regular file")
                intake[member] = _snapshot_transfer_member(member, stream)
        with self._admit_import_members(intake) as admission:
            if not admission.pending_artifact_ids:
                return ImportPublication(
                    refs=admission.exact_refs,
                    published_refs=(),
                    reused_refs=admission.canonical_exact_refs or admission.exact_refs,
                )
            if set(artifact_refs) != set(admission.pending_artifact_ids):
                raise ArtifactIntegrityError("Admitted import set differs from staged artifacts")
            return self._publish_admitted_staged_import(staging_root, members, artifact_refs)

    def _publish_child_release_profiles(
        self,
        source: FileSystemCAS,
        refs: tuple[ArtifactRef, ...],
        ledger: object,
        *,
        token: object,
    ) -> ImportPublication:
        """Transfer only Core-enrolled child profiles, retaining their deny-first gate.

        This internal path reuses durable storage reservation and import publication.
        It does not admit arbitrary claimed manifest views and cannot commit release.
        No Root/job fence is held over this streaming preparation and transfer.
        """
        import errno
        import shutil

        from .child_release import (
            _CHILD_STAGING_TOKEN,
            _ChildReleaseLedger,
            _safe_read,
            child_store_identity,
        )

        if token is not _CHILD_STAGING_TOKEN or type(ledger) is not _ChildReleaseLedger:
            raise ArtifactIntegrityError("child_publication_owner_required")
        if type(source) is not FileSystemCAS or source is self:
            raise ArtifactIntegrityError("child_publication_private_source_required")
        if ledger.root != self.root.resolve(strict=True) or ledger.head().status != "pending":
            raise ArtifactIntegrityError("child_publication_pending_owner_required")
        if child_store_identity(source.root) == ledger.store_identity or not refs:
            raise ArtifactIntegrityError("child_publication_private_source_invalid")
        stage = self._coordinator.transaction_root / "stage" / ("child-" + ledger.release_id)
        if self._ownership_index._path_has_symlink_component(stage):
            raise ArtifactIntegrityError("child_transfer_stage_symlink")
        _ensure_directory_durable(stage)
        members: set[str] = set()
        artifact_refs: set[str] = set()
        profiles: set[tuple[str, str]] = set()
        for ref in refs:
            if type(ref) is not ArtifactRef or ref.manifest_profile_sha256 is None:
                raise ArtifactIntegrityError("child_transfer_selected_profile_required")
            key = (str(ref.artifact_id), ref.manifest_profile_sha256)
            if key in profiles:
                raise ArtifactIntegrityError("child_transfer_duplicate_profile")
            profiles.add(key)
            manifest = source.get_manifest(ref)
            info = manifest.child_release
            if (
                info is None
                or info not in source._private_child_infos()
                or info.release_id != ledger.release_id
                or info.root_run_id != ledger.root_run_id
                or info.served_store_identity != ledger.store_identity
            ):
                raise ArtifactIntegrityError("child_transfer_scope_not_owner_bound")
            enrollment = (
                self.root
                / "artifacts/ownership/child_releases/enrollments"
                / ref.artifact_id.hex
                / (ref.manifest_profile_sha256[7:] + ".json")
            )
            if _safe_read(self.root, enrollment) != info.model_dump_json().encode():
                raise ArtifactIntegrityError("child_transfer_not_enrolled_before_copy")
            prefix = (
                f"artifacts/sha256/{ref.artifact_id.hex[:2]}/"
                f"{ref.artifact_id.hex[2:4]}/{ref.artifact_id.hex}"
            )
            paths = (
                (prefix + ".blob", source._paths(ref.artifact_id)[0]),
                (
                    prefix + ".view." + ref.manifest_profile_sha256[7:] + ".manifest.json",
                    source._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256),
                ),
            )
            for member, source_path in paths:
                if member in members:
                    continue
                if (
                    source._ownership_index._path_has_symlink_component(source_path)
                    or not source_path.is_file()
                ):
                    raise ArtifactIntegrityError("child_transfer_source_unsafe")
                destination = stage / member
                if self._ownership_index._path_has_symlink_component(destination):
                    raise ArtifactIntegrityError("child_transfer_destination_unsafe")
                _ensure_directory_durable(destination.parent)
                if destination.exists():
                    raise ArtifactIntegrityError("child_transfer_stage_already_populated")
                # Hard-link immutable CAS content on the same volume; cross-volume
                # fallback copies only this selected closure, never input CAS bytes.
                try:
                    os.link(source_path, destination)
                except OSError as exc:
                    if exc.errno != errno.EXDEV:
                        raise
                    with source_path.open("rb") as reader, destination.open("xb") as writer:
                        shutil.copyfileobj(reader, writer, length=1024 * 1024)
                        writer.flush()
                        os.fsync(writer.fileno())
                members.add(member)
            artifact_refs.add(str(ref.artifact_id))
        # The existing publisher rehashes bodies, selected manifests and lineage,
        # reserves actual storage, and atomically records existing tenant ownership.
        return self._publish_admitted_staged_import(stage, members, artifact_refs)

    def _publish_admitted_staged_import(
        self,
        staging_root: Path,
        members: set[str],
        artifact_refs: set[str],
    ) -> ImportPublication:
        """Publish already-admitted members through durable owner transactions."""
        try:
            staging_root.relative_to(self.root)
        except ValueError as exc:
            raise ArtifactIntegrityError("CAS import stage escaped its owner root") from exc
        if self._ownership_index._path_has_symlink_component(staging_root):
            raise ArtifactIntegrityError("CAS import staging root crosses a symlink")

        staged_by_artifact: dict[str, set[str]] = {}
        for member in sorted(members):
            safe_path = _safe_member_path(member)
            if safe_path is None or safe_path.as_posix() != member:
                raise ArtifactIntegrityError(f"Unsafe staged member: {member}")
            artifact_id = _artifact_id_from_member(member)
            if artifact_id is None:
                raise ArtifactIntegrityError(f"Staged member is not a CAS artifact: {member}")
            staged_by_artifact.setdefault(str(artifact_id), set()).add(member)
        if set(staged_by_artifact) != set(artifact_refs):
            raise ArtifactIntegrityError("Staged artifact set does not match transfer inventory")

        artifact_ids = tuple(ArtifactID.model_validate(value) for value in sorted(artifact_refs))
        source_by_artifact: dict[str, dict[str, Any]] = {}
        lock_ids: dict[str, ArtifactID] = {aid.hex: aid for aid in artifact_ids}
        for artifact_id in artifact_ids:
            artifact_members = staged_by_artifact[str(artifact_id)]
            prefix = (
                f"artifacts/sha256/{artifact_id.hex[:2]}/"
                + f"{artifact_id.hex[2:4]}/{artifact_id.hex}"
            )
            blob_member = f"{prefix}.blob"
            if blob_member not in artifact_members:
                raise ArtifactIntegrityError(f"Import is missing blob for {artifact_id}")
            blob_source = staging_root / Path(*blob_member.split("/"))
            if (
                self._ownership_index._path_has_symlink_component(blob_source)
                or blob_source.is_symlink()
                or not blob_source.is_file()
            ):
                raise ArtifactIntegrityError("CAS import blob stage is unsafe")
            blob_sha, blob_size = self._stream_file_digest(blob_source)
            if blob_sha != artifact_id.hex:
                raise ArtifactIntegrityError(f"Staged blob content does not match {artifact_id}")

            manifest_members = sorted(
                member for member in artifact_members if member.endswith(".manifest.json")
            )
            if not manifest_members:
                raise ArtifactIntegrityError(f"Import is missing manifest views for {artifact_id}")
            source_views: list[dict[str, Any]] = []
            for manifest_member in manifest_members:
                manifest_source = staging_root / Path(*manifest_member.split("/"))
                if (
                    self._ownership_index._path_has_symlink_component(manifest_source)
                    or manifest_source.is_symlink()
                    or not manifest_source.is_file()
                ):
                    raise ArtifactIntegrityError("CAS import manifest stage is unsafe")
                if manifest_source.stat().st_size > 8 * 1024 * 1024:
                    raise ArtifactIntegrityError("CAS import manifest exceeds its size bound")
                manifest_data = manifest_source.read_bytes()
                manifest = ArtifactManifest.model_validate_json(manifest_data)
                _validate_manifest_identity(artifact_id, manifest)
                if manifest.byte_size != blob_size:
                    raise ArtifactIntegrityError(f"Manifest byte size mismatch for {artifact_id}")
                profile_sha256 = self._manifests.profile_sha256(manifest)
                encoded_profile = _member_profile_sha256(manifest_member)
                if encoded_profile is not None and encoded_profile != profile_sha256:
                    raise ArtifactIntegrityError(
                        f"Selected manifest profile mismatch for {artifact_id}"
                    )
                for raw_input_ref in manifest.inputs:
                    input_ref = _coerce_input_ref(raw_input_ref)
                    lock_ids[input_ref.artifact_id.hex] = input_ref.artifact_id

                signature_member = manifest_member.removesuffix(".manifest.json") + ".sig"
                signature_bytes: bytes | None = None
                if signature_member in artifact_members:
                    signature_source = staging_root / Path(*signature_member.split("/"))
                    if (
                        self._ownership_index._path_has_symlink_component(signature_source)
                        or signature_source.is_symlink()
                        or not signature_source.is_file()
                        or signature_source.stat().st_size > 1024 * 1024
                    ):
                        raise ArtifactIntegrityError("CAS import signature stage is unsafe")
                    signature_bytes = signature_source.read_bytes()
                    signature = DetachedSignature.model_validate_json(signature_bytes)
                    if (
                        signature.artifact_id != str(artifact_id)
                        or signature.statement.blob_sha256 != artifact_id.hex
                        or signature.statement.manifest_sha256
                        != hashlib.sha256(manifest_data).hexdigest()
                    ):
                        raise ArtifactIntegrityError(
                            f"Imported signature does not bind manifest view {artifact_id}"
                        )
                source_views.append(
                    {
                        "member": manifest_member,
                        "source": manifest_source,
                        "manifest": manifest,
                        "manifest_data": manifest_data,
                        "profile": profile_sha256,
                        "signature_data": signature_bytes,
                    }
                )
            source_by_artifact[artifact_id.hex] = {
                "artifact_id": artifact_id,
                "blob_source": blob_source,
                "blob_sha256": f"sha256:{blob_sha}",
                "blob_size": blob_size,
                "source_views": source_views,
                "members": artifact_members,
            }

        published_views: dict[tuple[str, str | None], ArtifactRef] = {}
        manifest_published: dict[tuple[str, str, str, str], ArtifactRef] = {}
        manifest_reused: dict[tuple[str, str, str, str], ArtifactRef] = {}

        def remember_view(entry: dict[str, Any], *, staged_by_intent: bool) -> None:
            reference = ArtifactRef(
                artifact_id=entry["artifact_id"],
                kind=entry["manifest"].kind,
                media_type=entry["manifest"].media_type,
                manifest_profile_sha256=entry["profile"],
            )
            key = (
                reference.artifact_id.hex,
                reference.kind,
                reference.media_type,
                reference.manifest_profile_sha256 or "",
            )
            (manifest_published if staged_by_intent else manifest_reused)[key] = reference

        with self._coordinator.artifact_leases(lock_ids.values(), exclusive=True) as leases:
            tenant_id: str | None = None
            cell_id: str | None = None
            if self._ownership_enforced:
                tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)
            owner: _ResolvedOwner | None = (
                {"tenant_id": tenant_id, "cell_id": cell_id}
                if self._ownership_enforced and tenant_id is not None
                else None
            )
            for source_info in source_by_artifact.values():
                for source_view in source_info["source_views"]:
                    self._require_bound_context_for_owner(
                        source_view["manifest"].tenant_context,
                        owner,
                    )
            self._require_import_input_owners(source_by_artifact, owner)

            storage_members: list[_CASStorageMember] = []
            for artifact_id in artifact_ids:
                self._require_unclaimed_target_if_unscoped(artifact_id, operation="import")
                source_info = source_by_artifact[artifact_id.hex]
                blob_path, default_manifest_path = self._paths(artifact_id)
                self._validate_import_destination(blob_path, member=blob_path.name)
                if blob_path.exists():
                    if _file_content_hash(blob_path) != artifact_id.hex:
                        raise ArtifactIntegrityError(
                            f"Existing CAS blob conflicts for {artifact_id}"
                        )
                else:
                    storage_members.append(
                        self._storage_member(
                            blob_path,
                            sha256=source_info["blob_sha256"],
                            byte_size=source_info["blob_size"],
                        )
                    )

                has_claims = (
                    self._ownership_enforced
                    and self._ownership_index.has_any_tenant_claim(artifact_id)
                )
                default_owned = bool(
                    owner is not None
                    and self._ownership_index.is_owned_by(
                        artifact_id,
                        tenant_id=owner["tenant_id"],
                        cell_id=owner["cell_id"],
                    )
                )
                default_existing_profile: str | None = None
                if default_manifest_path.exists():
                    self._validate_import_destination(
                        default_manifest_path,
                        member=default_manifest_path.name,
                    )
                    existing_default = ArtifactManifest.model_validate_json(
                        default_manifest_path.read_bytes()
                    )
                    _validate_manifest_identity(artifact_id, existing_default)
                    default_existing_profile = self._manifests.profile_sha256(existing_default)

                for source_view in source_info["source_views"]:
                    profile_sha256 = source_view["profile"]
                    is_source_default = source_view["member"].endswith(
                        f"{artifact_id.hex}.manifest.json"
                    )
                    can_use_default = (
                        is_source_default
                        and source_view["manifest"].child_release is None
                        and (default_owned or not has_claims)
                        and (
                            default_existing_profile is None
                            or default_existing_profile == profile_sha256
                        )
                    )
                    target_paths = [default_manifest_path] if can_use_default else []
                    selected_view_path = self._layout.view_manifest_path(
                        artifact_id, profile_sha256
                    )
                    if not can_use_default or is_source_default:
                        target_paths.append(selected_view_path)

                    for target_path in target_paths:
                        self._validate_import_destination(
                            target_path,
                            member=target_path.relative_to(self.root).as_posix(),
                        )
                        if target_path.exists():
                            target_manifest_bytes = target_path.read_bytes()
                            target_manifest = ArtifactManifest.model_validate_json(
                                target_manifest_bytes
                            )
                            _validate_manifest_identity(artifact_id, target_manifest)
                            if self._manifests.profile_sha256(target_manifest) != profile_sha256:
                                raise ArtifactIntegrityError(
                                    f"Existing manifest profile conflicts for {artifact_id}"
                                )
                        else:
                            target_manifest_bytes = source_view["manifest_data"]
                            storage_members.append(
                                self._storage_member(
                                    target_path,
                                    sha256=hashlib.sha256(target_manifest_bytes).hexdigest(),
                                    byte_size=len(target_manifest_bytes),
                                )
                            )

                        signature_bytes = source_view["signature_data"]
                        if signature_bytes is None:
                            continue
                        signature = DetachedSignature.model_validate_json(signature_bytes)
                        if (
                            signature.statement.manifest_sha256
                            != hashlib.sha256(target_manifest_bytes).hexdigest()
                        ):
                            raise ArtifactIntegrityError(
                                f"Imported signature does not bind selected view {artifact_id}"
                            )
                        selector = (
                            "default" if target_path == default_manifest_path else profile_sha256
                        )
                        signature_path = self._sig_path(
                            artifact_id,
                            None if selector == "default" else profile_sha256,
                        )
                        self._validate_import_destination(
                            signature_path,
                            member=signature_path.relative_to(self.root).as_posix(),
                        )
                        if signature_path.exists():
                            if signature_path.read_bytes() != signature_bytes:
                                raise ArtifactIntegrityError(
                                    f"Existing signature conflicts for {artifact_id}"
                                )
                        else:
                            storage_members.append(
                                self._storage_member(
                                    signature_path,
                                    sha256=hashlib.sha256(signature_bytes).hexdigest(),
                                    byte_size=len(signature_bytes),
                                )
                            )

            self._admit_storage_members(storage_members)

            for artifact_id in artifact_ids:
                self._require_unclaimed_target_if_unscoped(artifact_id, operation="import")
                source_info = source_by_artifact[artifact_id.hex]
                blob_path, default_manifest_path = self._paths(artifact_id)
                self._prepare_import_destination(blob_path, member=blob_path.name)
                if blob_path.exists() and _file_content_hash(blob_path) != artifact_id.hex:
                    raise ArtifactIntegrityError(f"Existing CAS blob conflicts for {artifact_id}")
                blob_needs_stage = not blob_path.exists()

                has_claims = (
                    self._ownership_enforced
                    and self._ownership_index.has_any_tenant_claim(artifact_id)
                )
                default_owned = bool(
                    owner is not None
                    and self._ownership_index.is_owned_by(
                        artifact_id,
                        tenant_id=owner["tenant_id"],
                        cell_id=owner["cell_id"],
                    )
                )
                publication_default_existing_profile: str | None = None
                if default_manifest_path.exists():
                    self._prepare_import_destination(
                        default_manifest_path,
                        member=default_manifest_path.name,
                    )
                    existing_default = ArtifactManifest.model_validate_json(
                        default_manifest_path.read_bytes()
                    )
                    _validate_manifest_identity(artifact_id, existing_default)
                    publication_default_existing_profile = self._manifests.profile_sha256(
                        existing_default
                    )

                desired_views: dict[str, dict[str, Any]] = {}
                desired_signatures: dict[str, dict[str, Any]] = {}
                for source_view in source_info["source_views"]:
                    profile_sha256 = source_view["profile"]
                    is_source_default = source_view["member"].endswith(
                        f"{artifact_id.hex}.manifest.json"
                    )
                    can_use_default = (
                        is_source_default
                        and source_view["manifest"].child_release is None
                        and (default_owned or not has_claims)
                        and (
                            publication_default_existing_profile is None
                            or publication_default_existing_profile == profile_sha256
                        )
                    )
                    view_targets = [default_manifest_path] if can_use_default else []
                    selected_view_path = self._layout.view_manifest_path(
                        artifact_id,
                        profile_sha256,
                    )
                    if not can_use_default or is_source_default:
                        view_targets.append(selected_view_path)

                    for target_path in view_targets:
                        selector = (
                            "default" if target_path == default_manifest_path else profile_sha256
                        )
                        self._prepare_import_destination(
                            target_path,
                            member=target_path.relative_to(self.root).as_posix(),
                        )
                        source_manifest = source_view["manifest"]
                        source_bytes = source_view["manifest_data"]
                        if target_path.exists():
                            manifest_data = target_path.read_bytes()
                            manifest = ArtifactManifest.model_validate_json(manifest_data)
                            _validate_manifest_identity(artifact_id, manifest)
                            if self._manifests.profile_sha256(manifest) != profile_sha256:
                                raise ArtifactIntegrityError(
                                    f"Existing manifest profile conflicts for {artifact_id}"
                                )
                        else:
                            manifest_data = source_bytes
                            manifest = source_manifest
                        digest = content_hash(manifest_data, prefix=True)
                        entry = {
                            "artifact_id": artifact_id,
                            "selector": selector,
                            "path": target_path,
                            "manifest": manifest,
                            "manifest_data": manifest_data,
                            "profile": profile_sha256,
                            "manifest_sha256": digest,
                            "needs_stage": not target_path.exists(),
                        }
                        previous = desired_views.get(selector)
                        if previous is not None and (
                            previous["manifest_sha256"] != digest or previous["path"] != target_path
                        ):
                            raise ArtifactIntegrityError(
                                f"Conflicting imported manifest views for {artifact_id}"
                            )
                        desired_views[selector] = entry

                        signature_bytes = source_view["signature_data"]
                        if signature_bytes is None:
                            continue
                        if (
                            DetachedSignature.model_validate_json(
                                signature_bytes
                            ).statement.manifest_sha256
                            != hashlib.sha256(manifest_data).hexdigest()
                        ):
                            raise ArtifactIntegrityError(
                                f"Imported signature does not bind selected view {artifact_id}"
                            )
                        signature_path = self._sig_path(
                            artifact_id,
                            None if selector == "default" else profile_sha256,
                        )
                        self._prepare_import_destination(
                            signature_path,
                            member=signature_path.relative_to(self.root).as_posix(),
                        )
                        if (
                            signature_path.exists()
                            and signature_path.read_bytes() != signature_bytes
                        ):
                            raise ArtifactIntegrityError(
                                f"Existing signature conflicts for {artifact_id}"
                            )
                        signature_entry = {
                            "selector": selector,
                            "path": signature_path,
                            "data": signature_bytes,
                            "sha256": content_hash(signature_bytes, prefix=True),
                            "needs_stage": not signature_path.exists(),
                        }
                        existing_signature = desired_signatures.get(selector)
                        if existing_signature is not None and (
                            existing_signature["sha256"] != signature_entry["sha256"]
                        ):
                            raise ArtifactIntegrityError(
                                f"Conflicting imported signatures for {artifact_id}"
                            )
                        desired_signatures[selector] = signature_entry

                if not desired_views:
                    raise ArtifactIntegrityError(
                        f"Import has no destination views for {artifact_id}"
                    )

                current_claims = self._ownership_index._transaction_claims_for(
                    artifact_id,
                    tenant_id=owner["tenant_id"] if owner is not None else None,
                    cell_id=owner["cell_id"] if owner is not None else None,
                    manifest_profile_sha256=next(
                        iter(entry["profile"] for entry in desired_views.values())
                    ),
                )
                default_claim = bool(
                    owner is not None
                    and ("default" in desired_views or current_claims["default_owner"])
                )
                blob_reader_claim = bool(
                    owner is not None and (not default_claim or current_claims["blob_reader"])
                )
                profile_claims = (
                    sorted({entry["profile"] for entry in desired_views.values()})
                    if owner is not None
                    else []
                )
                missing_profile_claims = set()
                for profile in profile_claims:
                    profile_claim = self._ownership_index._transaction_claims_for(
                        artifact_id,
                        tenant_id=owner["tenant_id"] if owner is not None else None,
                        cell_id=owner["cell_id"] if owner is not None else None,
                        manifest_profile_sha256=profile,
                    )
                    if profile not in profile_claim["view_owners"]:
                        missing_profile_claims.add(profile)

                claims = {
                    "default_owner": default_claim,
                    "blob_reader": blob_reader_claim,
                    "view_owners": profile_claims,
                }
                affected_profiles = sorted(
                    profile
                    for profile, entry in (
                        (value["profile"], value) for value in desired_views.values()
                    )
                    if (
                        entry["needs_stage"]
                        or (entry["selector"] != "default" and profile in missing_profile_claims)
                    )
                )
                affected_profiles = list(dict.fromkeys(affected_profiles))
                ambient_affected = bool(
                    blob_needs_stage
                    or desired_views.get("default", {}).get("needs_stage", False)
                    or (default_claim and not current_claims["default_owner"])
                    or (blob_reader_claim and not current_claims["blob_reader"])
                )
                signature_specs = []
                affected_signature_profiles = []
                for selector, entry in sorted(desired_signatures.items()):
                    signature_specs.append(
                        {
                            "selector": selector,
                            "signature_sha256": entry["sha256"],
                            "signature_stage": None,
                        }
                    )
                    if entry["needs_stage"]:
                        affected_signature_profiles.append(selector)

                blob_member_sha = source_info["blob_sha256"]
                default_created_at = next(
                    iter(
                        source_view["manifest"].created_at.isoformat()
                        for source_view in source_info["source_views"]
                    )
                )
                operation_id = uuid.uuid4().hex
                stage_names = {
                    selector: (
                        "manifest-default.stage"
                        if selector == "default"
                        else f"manifest-view-{selector.removeprefix('sha256:')}.stage"
                    )
                    for selector in desired_views
                }
                intent_views = [
                    {
                        "selector": selector,
                        "manifest_profile_sha256": entry["profile"],
                        "manifest_sha256": entry["manifest_sha256"],
                        "manifest_stage": (
                            self._transaction_stage_relative(operation_id, stage_names[selector])
                            if entry["needs_stage"]
                            else None
                        ),
                    }
                    for selector, entry in sorted(desired_views.items())
                ]
                for signature_spec in signature_specs:
                    selector = signature_spec["selector"]
                    if (
                        signature_spec["signature_stage"] is None
                        and desired_signatures[selector]["needs_stage"]
                    ):
                        stage_name = (
                            "signature-default.stage"
                            if selector == "default"
                            else f"signature-view-{selector.removeprefix('sha256:')}.stage"
                        )
                        signature_spec["signature_stage"] = self._transaction_stage_relative(
                            operation_id,
                            stage_name,
                        )
                affected = {
                    "ambient_artifact": ambient_affected,
                    "manifest_profiles": affected_profiles,
                    "signature_profiles": affected_signature_profiles,
                }
                if owner is None and self._ownership_index.has_any_tenant_claim(artifact_id):
                    raise ArtifactOwnershipError(
                        f"Artifact {artifact_id} import requires its current tenant owner"
                    )

                request_intent: dict[str, Any] = {
                    "schema_version": _TRANSACTION_INTENT_SCHEMA_V3,
                    "status": "pending",
                    "mode": "import",
                    "operation_id": operation_id,
                    "artifact_id": str(artifact_id),
                    "owner": owner,
                    "blob_sha256": blob_member_sha,
                    "blob_stage": (
                        self._transaction_stage_relative(operation_id, "blob.stage")
                        if blob_needs_stage
                        else None
                    ),
                    "views": intent_views,
                    "claims": claims,
                    "affected": affected,
                    "manifest_created_at": default_created_at,
                    "signatures": signature_specs,
                    "request_sha256": "",
                }
                prior = self._ownership_index._read_transaction_intent(artifact_id)
                committed_prior = (
                    prior is not None
                    and self._ownership_index._committed_intent_matches_current_state(prior)
                )
                if prior is not None and committed_prior:
                    self._ownership_index.remove_transaction_intent(
                        artifact_id,
                        lease=leases[artifact_id.hex],
                    )
                    self._remove_transaction_stage(prior["operation_id"])
                    prior = None
                if prior is not None:
                    prior_views = {spec["selector"]: spec for spec in prior["views"]}
                    prior_signature_specs = {
                        spec["selector"]: spec for spec in prior.get("signatures", [])
                    }
                    if (
                        prior["mode"] != "import"
                        or prior["owner"] != owner
                        or set(prior_views) != set(desired_views)
                        or set(prior_signature_specs) != set(desired_signatures)
                    ):
                        raise ArtifactTransactionPendingError(artifact_id, surface="artifact")

                    retry_intent = dict(request_intent)
                    retry_intent["claims"] = prior["claims"]
                    retry_intent["affected"] = prior["affected"]
                    retry_intent["blob_stage"] = prior["blob_stage"]
                    retry_intent["views"] = [
                        {
                            "selector": selector,
                            "manifest_profile_sha256": entry["profile"],
                            "manifest_sha256": entry["manifest_sha256"],
                            "manifest_stage": prior_views[selector]["manifest_stage"],
                        }
                        for selector, entry in sorted(desired_views.items())
                    ]
                    retry_intent["signatures"] = [
                        {
                            "selector": selector,
                            "signature_sha256": entry["sha256"],
                            "signature_stage": prior_signature_specs[selector]["signature_stage"],
                        }
                        for selector, entry in sorted(desired_signatures.items())
                    ]
                    retry_intent["request_sha256"] = (
                        self._ownership_index._transaction_request_digest(retry_intent)
                    )
                    if retry_intent["request_sha256"] != prior["request_sha256"]:
                        raise ArtifactTransactionPendingError(artifact_id, surface="artifact")
                    intent = prior
                    operation_id = prior["operation_id"]
                    for selector, spec in prior_views.items():
                        desired = desired_views[selector]
                        if (
                            desired["manifest_sha256"] != spec["manifest_sha256"]
                            or desired["profile"] != spec["manifest_profile_sha256"]
                        ):
                            raise ArtifactTransactionPendingError(
                                artifact_id,
                                surface=f"manifest:{selector}",
                            )
                    for selector, spec in prior_signature_specs.items():
                        if desired_signatures[selector]["sha256"] != spec["signature_sha256"]:
                            raise ArtifactTransactionPendingError(
                                artifact_id,
                                surface=f"signature:{selector}",
                            )
                    signature_specs = list(prior_signature_specs.values())
                else:
                    request_intent["request_sha256"] = (
                        self._ownership_index._transaction_request_digest(request_intent)
                    )
                    intent = request_intent
                    if (
                        intent["blob_stage"] is None
                        and not any(view["manifest_stage"] for view in intent["views"])
                        and not any(
                            signature["signature_stage"] for signature in intent["signatures"]
                        )
                        and not ambient_affected
                        and not affected_profiles
                    ):
                        for selector, entry in desired_views.items():
                            selected_profile = None if selector == "default" else entry["profile"]
                            reference = ArtifactRef(
                                artifact_id=artifact_id,
                                kind=entry["manifest"].kind,
                                media_type=entry["manifest"].media_type,
                                manifest_profile_sha256=selected_profile,
                            )
                            published_views[(str(artifact_id), selected_profile)] = reference
                            remember_view(entry, staged_by_intent=False)
                        continue
                    self._ownership_index.write_transaction_intent(
                        artifact_id,
                        intent,
                        lease=leases[artifact_id.hex],
                    )

                signature_by_selector = {
                    signature["selector"]: signature for signature in intent.get("signatures", [])
                }
                blob_stage = None
                if intent["blob_stage"] is not None:
                    blob_stage = self._stage_import_source(
                        operation_id=operation_id,
                        recorded_path=intent["blob_stage"],
                        source_path=source_info["blob_source"],
                        final_path=blob_path,
                        expected_sha256=intent["blob_sha256"],
                        resume=prior is not None,
                    )
                self._publish_transaction_member(
                    blob_stage,
                    blob_path,
                    expected_sha256=intent["blob_sha256"],
                )
                for selector, entry in sorted(desired_views.items()):
                    spec = next(view for view in intent["views"] if view["selector"] == selector)
                    manifest_stage = None
                    if spec["manifest_stage"] is not None:
                        source_member = entry.get("source_member")
                        if source_member is None:
                            source_member = next(
                                source_view["member"]
                                for source_view in source_info["source_views"]
                                if source_view["profile"] == entry["profile"]
                            )
                        source_manifest_path = staging_root / Path(*source_member.split("/"))
                        manifest_stage = self._stage_import_source(
                            operation_id=operation_id,
                            recorded_path=spec["manifest_stage"],
                            source_path=source_manifest_path,
                            final_path=entry["path"],
                            expected_sha256=spec["manifest_sha256"],
                            resume=prior is not None,
                        )
                    self._publish_transaction_member(
                        manifest_stage,
                        entry["path"],
                        expected_sha256=spec["manifest_sha256"],
                    )
                for selector, spec in sorted(signature_by_selector.items()):
                    entry = desired_signatures[selector]
                    signature_stage = None
                    if spec["signature_stage"] is not None:
                        source_signature = next(
                            source_view
                            for source_view in source_info["source_views"]
                            if source_view["signature_data"] == entry["data"]
                        )
                        source_member = (
                            source_signature["member"].removesuffix(".manifest.json") + ".sig"
                        )
                        signature_source = staging_root / Path(*source_member.split("/"))
                        signature_stage = self._stage_import_source(
                            operation_id=operation_id,
                            recorded_path=spec["signature_stage"],
                            source_path=signature_source,
                            final_path=entry["path"],
                            expected_sha256=spec["signature_sha256"],
                            resume=prior is not None,
                        )
                    self._publish_transaction_member(
                        signature_stage,
                        entry["path"],
                        expected_sha256=spec["signature_sha256"],
                    )

                self._record_transaction_claims(
                    artifact_id,
                    intent,
                    lease=leases[artifact_id.hex],
                )
                if not self._ownership_index._intent_completion_is_recomputed(intent):
                    raise ArtifactIntegrityError(
                        "artifact_import_owner_generation_or_bytes_unverified"
                    )
                committed = dict(intent)
                committed["status"] = "committed"
                self._ownership_index.write_transaction_intent(
                    artifact_id,
                    committed,
                    lease=leases[artifact_id.hex],
                )
                self._ownership_index.remove_transaction_intent(
                    artifact_id,
                    lease=leases[artifact_id.hex],
                )
                self._remove_transaction_stage(operation_id)
                staged_selectors = {
                    spec["selector"]
                    for spec in intent["views"]
                    if spec["manifest_stage"] is not None
                }
                for selector, entry in desired_views.items():
                    selected_profile = None if selector == "default" else entry["profile"]
                    reference = ArtifactRef(
                        artifact_id=artifact_id,
                        kind=entry["manifest"].kind,
                        media_type=entry["manifest"].media_type,
                        manifest_profile_sha256=selected_profile,
                    )
                    published_views[(str(artifact_id), selected_profile)] = reference
                    remember_view(entry, staged_by_intent=selector in staged_selectors)

        for key in manifest_published:
            manifest_reused.pop(key, None)
        return ImportPublication(
            refs=tuple(
                published_views[key]
                for key in sorted(published_views, key=lambda item: (item[0], item[1] or ""))
            ),
            published_refs=tuple(manifest_published[key] for key in sorted(manifest_published)),
            reused_refs=tuple(manifest_reused[key] for key in sorted(manifest_reused)),
        )

    @staticmethod
    def _stream_file_digest(path: Path) -> tuple[str, int]:
        """Hash a regular file with bounded memory."""
        digest = hashlib.sha256()
        byte_size = 0
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                byte_size += len(chunk)
        return digest.hexdigest(), byte_size

    def _bulk_inventory_artifact_ids(self) -> tuple[ArtifactID, ...]:
        """Freeze the default-view IDs from one verified owner inventory."""
        snapshot = self.inventory_snapshot()
        if snapshot.verdict != "pass":
            raise ArtifactIntegrityError(
                "bulk_cas_inventory_not_established:"
                f"{snapshot.verdict}:{snapshot.reason or 'no_reason'}"
            )
        return _canonical_artifact_id_sequence(
            entry.artifact_ref
            for entry in snapshot.entries
            if isinstance(entry.artifact_ref, ArtifactID)
        )

    def iter_artifact_ids(self) -> list[ArtifactID]:
        """List default-view IDs from one verified, stable CAS inventory."""
        return list(self._bulk_inventory_artifact_ids())

    def _owner_generation_token(self) -> str:
        evidence = self._ownership_index.evidence()
        generation = evidence.get("ownership_index_generation_sha256")
        if isinstance(generation, str):
            return generation
        payload_sha = str(evidence.get("ownership_index_digest") or "")
        signature_sha = str(evidence.get("ownership_index_signature_digest") or "")
        token = hashlib.sha256(f"{payload_sha}:{signature_sha}".encode()).hexdigest()
        return f"sha256:{token}"

    def _capture_inventory_member_paths(
        self,
    ) -> tuple[tuple[str, ...], dict[tuple[str, str], Path]]:
        """Parse the complete canonical member-name set without reading contents."""
        names: set[str] = set()
        walk_errors: list[OSError] = []

        def onerror(error: OSError) -> None:
            walk_errors.append(error)

        for directory, children, files in os.walk(
            self.base,
            topdown=True,
            followlinks=False,
            onerror=onerror,
        ):
            parent = Path(directory)
            if any((parent / child).is_symlink() for child in children):
                raise ArtifactIntegrityError("cas_inventory_symlink_directory")
            for filename in files:
                path = parent / filename
                if path.is_symlink() or not path.is_file():
                    raise ArtifactIntegrityError("cas_inventory_nonregular_member")
                names.add(path.relative_to(self.base).as_posix())
        if walk_errors:
            raise walk_errors[0]

        members: dict[tuple[str, str], Path] = {}
        member_pattern = re.compile(
            r"^(?P<artifact>[0-9a-f]{64})(?:\.view\.(?P<profile>[0-9a-f]{64}))?"
            r"\.(?P<kind>blob|manifest\.json|sig)$"
        )
        for name in names:
            relative = Path(name)
            if len(relative.parts) != 3:
                raise ArtifactIntegrityError("cas_inventory_member_path_invalid")
            shard_a, shard_b, filename = relative.parts
            match = member_pattern.fullmatch(filename)
            if (
                match is None
                or shard_a != match.group("artifact")[:2]
                or shard_b != match.group("artifact")[2:4]
            ):
                raise ArtifactIntegrityError("cas_inventory_member_name_invalid")
            selector = match.group("profile") or "default"
            kind = match.group("kind")
            key = (match.group("artifact"), f"{selector}:{kind}")
            if key in members:
                raise ArtifactIntegrityError("cas_inventory_duplicate_member")
            members[key] = self.base / relative

        artifacts = {artifact_hex for artifact_hex, _member_key in members}
        for artifact_hex in artifacts:
            if (artifact_hex, "default:blob") not in members:
                raise ArtifactIntegrityError("cas_inventory_blob_missing")
            if not any(
                key[0] == artifact_hex and key[1].endswith(":manifest.json") for key in members
            ):
                raise ArtifactIntegrityError("cas_inventory_manifest_missing")
            for member_key, _path in (
                (key[1], path) for key, path in members.items() if key[0] == artifact_hex
            ):
                selector, kind = member_key.split(":", 1)
                if kind == "sig" and (artifact_hex, f"{selector}:manifest.json") not in members:
                    raise ArtifactIntegrityError("cas_inventory_signature_view_missing")

        return tuple(sorted(names)), members

    def _capture_default_inventory_state(
        self,
        *,
        owner_scope: tuple[str | None, str | None],
    ) -> tuple[tuple[str, ...], tuple[ArtifactID, ...], str]:
        """Capture visible default-view identities without reading manifests or blobs."""
        _all_names, members = self._capture_inventory_member_paths()
        default_ids = {
            artifact_hex
            for artifact_hex, selector_kind in members
            if selector_kind == "default:blob"
            and (artifact_hex, "default:manifest.json") in members
        }
        tenant_id, cell_id = owner_scope
        visible_ids: list[ArtifactID] = []
        for artifact_hex in sorted(default_ids):
            artifact_id = ArtifactID.from_sha256_hex(artifact_hex)
            if self._ownership_enforced:
                if tenant_id is None:
                    if self._ownership_index.has_any_tenant_claim(artifact_id):
                        continue
                elif not self._ownership_index.is_owned_by(
                    artifact_id,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                ):
                    continue
            visible_ids.append(artifact_id)
        visible_hex = {artifact_id.hex for artifact_id in visible_ids}
        default_names = tuple(
            sorted(
                path.relative_to(self.base).as_posix()
                for (artifact_hex, selector_kind), path in members.items()
                if artifact_hex in visible_hex
                and selector_kind in {"default:blob", "default:manifest.json"}
            )
        )
        return default_names, tuple(visible_ids), self._owner_generation_token()

    def _authenticated_default_inventory_cursor(self) -> Iterator[ArtifactID]:
        """Yield default IDs from the active-scope membership projection.

        The first iteration walks the complete CAS name tree and materializes
        its member map and visible default IDs before yielding. It does not read
        every manifest or blob during that census. Cancellation stops later
        item admission, but cannot interrupt the initial filesystem walk. On
        successful exhaustion, the owner recomputes the active-scope default
        IDs and their blob/manifest member names. The shared owner-generation
        token is sampled but is not itself the completion predicate: unrelated
        tenant claims and signature-only writes may advance it without changing
        this scope's default membership.
        """
        owner_scope = (
            self._resolve_owner(required=self._ownership_requires_scope)
            if self._ownership_enforced
            else (None, None)
        )
        try:
            with self._coordinator.root_exclusive():
                names_before, ids_before, generation_before = self._capture_default_inventory_state(
                    owner_scope=owner_scope
                )
        except (ArtifactIntegrityError, OSError, ValueError, TypeError) as exc:
            raise ArtifactIntegrityError("cas_batch_inventory_capture_failed") from exc

        processed: set[str] = set()
        for artifact_id in ids_before:
            processed.add(artifact_id.hex)
            yield artifact_id

        try:
            with self._coordinator.root_exclusive():
                names_after, ids_after, generation_after = self._capture_default_inventory_state(
                    owner_scope=owner_scope
                )
        except (ArtifactIntegrityError, OSError, ValueError, TypeError) as exc:
            raise ArtifactIntegrityError("cas_batch_inventory_recheck_failed") from exc
        visible_membership_changed = names_before != names_after or tuple(
            artifact_id.hex for artifact_id in ids_after
        ) != tuple(sorted(processed))
        owner_generation_changed = generation_before != generation_after
        if visible_membership_changed:
            raise ArtifactIntegrityError("cas_batch_inventory_changed_during_scan")
        if owner_generation_changed:
            # Owner-index generations are shared across tenants and can advance
            # for signature-only writes. The complete active-scope projection
            # above is re-read at exhaustion, so generation-only churn outside
            # that projection does not make this batch incomplete.
            return

    def _capture_inventory_membership(
        self,
        *,
        artifact_id: ArtifactID | None = None,
    ) -> tuple[
        tuple[str, ...],
        tuple[tuple[ArtifactID, str | None, Path, ArtifactManifest, bytes], ...],
        str,
    ]:
        """Capture member names, exact manifest views, and owner generation under root lock."""
        names, members = self._capture_inventory_member_paths()

        visible_views: list[tuple[ArtifactID, str | None, Path, ArtifactManifest, bytes]] = []
        tenant_id: str | None = None
        cell_id: str | None = None
        if self._ownership_enforced:
            tenant_id, cell_id = self._resolve_owner(required=self._ownership_requires_scope)

        selected_artifact_id = artifact_id
        for (artifact_hex, selector_kind), manifest_path in sorted(members.items()):
            if selected_artifact_id is not None and artifact_hex != selected_artifact_id.hex:
                continue
            selector, kind = selector_kind.split(":", 1)
            if kind != "manifest.json":
                continue
            member_artifact_id = ArtifactID.from_sha256_hex(artifact_hex)
            profile_sha256 = None if selector == "default" else f"sha256:{selector}"
            if self._ownership_enforced:
                if tenant_id is None:
                    if self._ownership_index.has_any_tenant_claim(member_artifact_id):
                        continue
                elif profile_sha256 is None:
                    if not self._ownership_index.is_owned_by(
                        member_artifact_id,
                        tenant_id=tenant_id,
                        cell_id=cell_id,
                    ):
                        continue
                elif not self._ownership_index.is_view_owned_by(
                    member_artifact_id,
                    profile_sha256,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                ):
                    continue
            manifest_bytes = manifest_path.read_bytes()
            manifest = ArtifactManifest.model_validate_json(manifest_bytes)
            _validate_manifest_identity(member_artifact_id, manifest)
            actual_profile = self._manifests.profile_sha256(manifest)
            if profile_sha256 is not None and actual_profile != profile_sha256:
                raise ArtifactIntegrityError("cas_inventory_manifest_profile_mismatch")
            from .child_release import ChildReleaseUnavailableError

            try:
                self._require_child_manifest_release(manifest)
            except ChildReleaseUnavailableError:
                continue
            visible_views.append(
                (
                    member_artifact_id,
                    profile_sha256,
                    manifest_path,
                    manifest,
                    manifest_bytes,
                )
            )

        return names, tuple(visible_views), self._owner_generation_token()

    def inventory_snapshot(
        self,
        artifact_id: ArtifactID | str | None = None,
    ) -> CASInventorySnapshot:
        """Verify a stable inventory, optionally limiting verified views to one blob ID.

        The complete CAS name set and shared owner generation are still captured
        and rechecked. When ``artifact_id`` is supplied, only that ID's visible
        manifest views and blobs are read and verified. The active tenant scope
        can hide other tenant views; those remain explicitly unresolved.
        """
        selected_artifact_id = (
            None if artifact_id is None else ArtifactID.model_validate(artifact_id)
        )
        inputs = (
            "canonical CAS root member names",
            (
                "all visible manifest bytes and profiles"
                if selected_artifact_id is None
                else f"visible manifest bytes and profiles for {selected_artifact_id}"
            ),
            (
                "all visible blobs streamed under artifact read leases"
                if selected_artifact_id is None
                else f"visible blob {selected_artifact_id} streamed under artifact read leases"
            ),
            "signed ownership-index generation",
        )
        unresolved = (
            "detached signature contents",
            "direct filesystem writers outside the CAS lease protocol",
            "other tenant views hidden by the active tenant scope",
        )
        try:
            with self._coordinator.root_exclusive():
                names_before, views, generation_before = self._capture_inventory_membership(
                    artifact_id=selected_artifact_id
                )
        except ArtifactIntegrityError as exc:
            return CASInventorySnapshot(
                verdict="fail",
                inputs=inputs,
                unresolved_by_construction=unresolved,
                owner_generation_sha256=None,
                entries=(),
                reason=str(exc),
            )
        except (OSError, ValueError, TypeError) as exc:
            return CASInventorySnapshot(
                verdict="UNRUN",
                inputs=inputs,
                unresolved_by_construction=unresolved,
                owner_generation_sha256=None,
                entries=(),
                reason=f"inventory_capture_unavailable:{type(exc).__name__}",
            )

        entries: list[CASInventoryEntry] = []
        try:
            for (
                artifact_id,
                profile_sha256,
                _manifest_path,
                manifest,
                manifest_bytes,
            ) in views:
                ref: ArtifactID | ArtifactRef = artifact_id
                if profile_sha256 is not None:
                    ref = ArtifactRef(
                        artifact_id=artifact_id,
                        kind=manifest.kind,
                        media_type=manifest.media_type,
                        manifest_profile_sha256=profile_sha256,
                    )
                with self.open_member(ref, "blob") as blob_stream:
                    while blob_stream.read(_VerifiedCASMemberStream._CHUNK_SIZE):
                        pass
                blob_receipt = blob_stream.receipt
                with self.open_member(ref, "manifest") as manifest_stream:
                    while manifest_stream.read(_VerifiedCASMemberStream._CHUNK_SIZE):
                        pass
                manifest_receipt = manifest_stream.receipt
                if manifest_receipt.sha256 != hashlib.sha256(manifest_bytes).hexdigest():
                    raise ArtifactIntegrityError("cas_inventory_manifest_changed_during_scan")
                entries.append(
                    CASInventoryEntry(
                        artifact_ref=ref,
                        manifest=manifest,
                        blob_sha256="sha256:" + blob_receipt.sha256,
                        blob_byte_size=blob_receipt.byte_size,
                        manifest_sha256="sha256:" + manifest_receipt.sha256,
                        manifest_byte_size=manifest_receipt.byte_size,
                    )
                )
        except ArtifactIntegrityError as exc:
            return CASInventorySnapshot(
                verdict="fail",
                inputs=inputs,
                unresolved_by_construction=unresolved,
                owner_generation_sha256=generation_before,
                entries=tuple(entries),
                reason=str(exc),
            )
        except (OSError, ValueError, TypeError, ArtifactOwnershipError) as exc:
            return CASInventorySnapshot(
                verdict="UNRUN",
                inputs=inputs,
                unresolved_by_construction=unresolved,
                owner_generation_sha256=generation_before,
                entries=tuple(entries),
                reason=f"inventory_verify_unavailable:{type(exc).__name__}",
            )

        try:
            with self._coordinator.root_exclusive():
                names_after, _views_after, generation_after = self._capture_inventory_membership(
                    artifact_id=selected_artifact_id
                )
        except ArtifactIntegrityError as exc:
            return CASInventorySnapshot(
                verdict="fail",
                inputs=inputs,
                unresolved_by_construction=unresolved,
                owner_generation_sha256=generation_before,
                entries=tuple(entries),
                reason=str(exc),
            )
        except (OSError, ValueError, TypeError) as exc:
            return CASInventorySnapshot(
                verdict="UNRUN",
                inputs=inputs,
                unresolved_by_construction=unresolved,
                owner_generation_sha256=generation_before,
                entries=tuple(entries),
                reason=f"inventory_recheck_unavailable:{type(exc).__name__}",
            )
        if names_before != names_after or generation_before != generation_after:
            return CASInventorySnapshot(
                verdict="UNRUN",
                inputs=inputs,
                unresolved_by_construction=unresolved,
                owner_generation_sha256=generation_after,
                entries=tuple(entries),
                reason="inventory_changed_during_scan",
            )
        return CASInventorySnapshot(
            verdict="pass",
            inputs=inputs,
            unresolved_by_construction=unresolved,
            owner_generation_sha256=generation_after,
            entries=tuple(entries),
        )

    def manifest_inventory_snapshot(self, *, kind: str) -> CASManifestInventorySnapshot:
        """Select every visible manifest of one kind from a stable CAS metadata view.

        This method validates complete CAS member names and all visible manifest
        profiles before returning the requested kind. It does not open or verify
        any payload blob. Consumers must still resolve each selected manifest
        profile and verify selected payload bytes through their normal typed read
        before using an entry for reconciliation or admission.
        """
        inputs = (
            "complete canonical CAS root member names",
            "all active-scope manifest bytes, identities, and profiles",
            "signed ownership-index generation",
            f"all visible manifests with exact kind {kind!r}",
        )
        unresolved = (
            "all payload blob bytes and digests; selected payloads require consumer verification",
            "detached signature contents",
            "other tenant views hidden by the active tenant scope",
            "direct filesystem writers outside the CAS lease protocol",
        )
        if type(kind) is not str or not kind:
            return CASManifestInventorySnapshot(
                verdict="fail",
                inputs=inputs,
                unresolved_by_construction=unresolved,
                owner_generation_sha256=None,
                entries=(),
                reason="cas_manifest_inventory_kind_invalid",
            )

        def capture() -> tuple[
            tuple[str, ...],
            tuple[tuple[ArtifactID, str | None, Path, ArtifactManifest, bytes], ...],
            str,
            tuple[tuple[str, str | None, str, str], ...],
        ]:
            with self._coordinator.root_exclusive():
                names, views, generation = self._capture_inventory_membership()
            signature = tuple(
                sorted(
                    (
                        (
                            artifact_id.hex,
                            selector,
                            hashlib.sha256(manifest_bytes).hexdigest(),
                            self._manifests.profile_sha256(manifest),
                        )
                        for artifact_id, selector, _path, manifest, manifest_bytes in views
                    ),
                    key=lambda row: (row[0], row[1] or "", row[2], row[3]),
                )
            )
            return names, views, generation, signature

        try:
            names_before, views_before, generation_before, signature_before = capture()
        except (ArtifactIntegrityError, ValidationError) as exc:
            return CASManifestInventorySnapshot(
                verdict="fail",
                inputs=inputs,
                unresolved_by_construction=unresolved,
                owner_generation_sha256=None,
                entries=(),
                reason=(
                    str(exc)
                    if isinstance(exc, ArtifactIntegrityError)
                    else "cas_inventory_manifest_invalid"
                ),
            )
        except (OSError, ValueError, TypeError, ArtifactOwnershipError) as exc:
            return CASManifestInventorySnapshot(
                verdict="UNRUN",
                inputs=inputs,
                unresolved_by_construction=unresolved,
                owner_generation_sha256=None,
                entries=(),
                reason=f"manifest_inventory_capture_unavailable:{type(exc).__name__}",
            )

        entries: list[CASManifestInventoryEntry] = []
        for (
            artifact_id,
            selector,
            _manifest_path,
            manifest,
            manifest_bytes,
        ) in views_before:
            if manifest.kind != kind:
                continue
            profile_sha256 = self._manifests.profile_sha256(manifest)
            artifact_ref: ArtifactID | ArtifactRef = artifact_id
            if selector is not None:
                artifact_ref = ArtifactRef(
                    artifact_id=artifact_id,
                    kind=manifest.kind,
                    media_type=manifest.media_type,
                    manifest_profile_sha256=selector,
                )
            entries.append(
                CASManifestInventoryEntry(
                    artifact_ref=artifact_ref,
                    manifest=manifest,
                    manifest_profile_sha256=profile_sha256,
                    manifest_sha256="sha256:" + hashlib.sha256(manifest_bytes).hexdigest(),
                    manifest_byte_size=len(manifest_bytes),
                )
            )

        try:
            names_after, _views_after, generation_after, signature_after = capture()
        except (ArtifactIntegrityError, ValidationError) as exc:
            return CASManifestInventorySnapshot(
                verdict="fail",
                inputs=inputs,
                unresolved_by_construction=unresolved,
                owner_generation_sha256=generation_before,
                entries=tuple(entries),
                reason=(
                    str(exc)
                    if isinstance(exc, ArtifactIntegrityError)
                    else "cas_inventory_manifest_invalid"
                ),
            )
        except (OSError, ValueError, TypeError, ArtifactOwnershipError) as exc:
            return CASManifestInventorySnapshot(
                verdict="UNRUN",
                inputs=inputs,
                unresolved_by_construction=unresolved,
                owner_generation_sha256=generation_before,
                entries=tuple(entries),
                reason=f"manifest_inventory_recheck_unavailable:{type(exc).__name__}",
            )
        if (
            names_before != names_after
            or generation_before != generation_after
            or signature_before != signature_after
        ):
            return CASManifestInventorySnapshot(
                verdict="UNRUN",
                inputs=inputs,
                unresolved_by_construction=unresolved,
                owner_generation_sha256=generation_after,
                entries=tuple(entries),
                reason="manifest_inventory_changed_during_scan",
            )
        return CASManifestInventorySnapshot(
            verdict="pass",
            inputs=inputs,
            unresolved_by_construction=unresolved,
            owner_generation_sha256=generation_after,
            entries=tuple(entries),
        )

    def _iter_artifact_ids_lazy(self) -> Iterator[ArtifactID]:
        """Yield authenticated default IDs through the bounded batch cursor."""
        yield from self._authenticated_default_inventory_cursor()

    def export_subgraph(
        self,
        artifact_ids: Iterable[ArtifactID | ArtifactRef | str],
        target: Path,
        *,
        compress: bool = True,
        include_manifests: bool = True,
    ) -> ExportReport:
        """Export a CAS subgraph to a tarball or directory using the stable CAS layout."""
        artifact_ids = list(artifact_ids)
        for artifact_id in artifact_ids:
            aid, profile_sha256, _ref = _artifact_reference(artifact_id)
            if profile_sha256 is None:
                self._require_artifact_owner(aid, operation="export")
            else:
                self._require_blob_owner(aid, operation="export")
                self._require_manifest_view_owner(
                    aid,
                    profile_sha256,
                    operation="export_manifest",
                )

        for artifact_id in artifact_ids:
            self.get_manifest(artifact_id)

        def member_name(request: ArtifactID | ArtifactRef, member: str) -> str:
            aid, profile_sha256, _ref = _artifact_reference(request)
            return self._member_name(aid, _artifact_member_kind(member), profile_sha256)

        @contextmanager
        def open_member_for_export(
            request: ArtifactID | ArtifactRef,
            member: str,
        ) -> Iterator[CASMemberStream]:
            with self.open_member(request, _artifact_member_kind(member)) as stream:
                yield stream

        return _export_subgraph(
            open_member=open_member_for_export,
            member_name=member_name,
            artifact_ids=artifact_ids,
            target=target,
            compress=compress,
            include_manifests=include_manifests,
        )

    def import_subgraph(
        self,
        source: Path,
        *,
        verify_integrity: bool = False,
    ) -> ImportReport:
        """Import a CAS export from a directory/tarball and optionally re-verify integrity."""
        return _import_subgraph(
            root=self.root,
            verify_artifact=self._verify_staged_artifact,
            publish_staged=self._publish_staged_import,
            admit_members=self._admit_import_members,
            source=source,
            verify_integrity=verify_integrity,
        )

    @staticmethod
    def _normalize_archive_path(path: Path) -> Path:
        return _normalize_archive_path(path)

    @staticmethod
    def _safe_member_path(name: str) -> object:
        return _safe_member_path(name)

    @staticmethod
    def _artifact_id_from_member(path: str) -> ArtifactID | None:
        return _artifact_id_from_member(path)

    def _read_only_member_present(self, path: Path, *, member: str) -> bool:
        """Classify one CAS member without following links or hiding status errors."""
        try:
            relative = path.relative_to(self.root)
        except ValueError as exc:
            raise ArtifactReadOnlyUnavailableError("cas_member_outside_root") from exc
        if not relative.parts:
            raise ArtifactReadOnlyUnavailableError("cas_member_path_invalid")

        current = self.root
        for index, component in enumerate(relative.parts):
            current = current / component
            try:
                member_stat = os.lstat(current)
            except FileNotFoundError:
                return False
            except OSError as exc:
                raise ArtifactReadOnlyUnavailableError(f"cas_{member}_status_unavailable") from exc
            if stat.S_ISLNK(member_stat.st_mode):
                raise ArtifactIntegrityError(f"CAS {member} path crosses a symlink")
            if index < len(relative.parts) - 1:
                if not stat.S_ISDIR(member_stat.st_mode):
                    raise ArtifactIntegrityError(f"CAS {member} parent is not a directory")
            elif not stat.S_ISREG(member_stat.st_mode):
                raise ArtifactIntegrityError(f"CAS {member} member is not a regular file")
        return True

    def _read_cas_file_no_follow(
        self,
        path: Path,
        *,
        member: str,
        max_bytes: int | None = None,
        raise_read_limit: bool = False,
        _read_attempt: _ArtifactStoreReadAttempt | None = None,
        _usage_field: str | None = None,
        _usage_stage: str = "bounded_manifest_transfer",
    ) -> bytes:
        """Read one regular CAS member through a no-follow file descriptor."""
        descriptor = -1
        stream: BinaryIO | None = None
        data: bytes | None = None
        read_attempted = False
        transfer_prefix = _usage_stage.removesuffix("_transfer")
        phase = f"{transfer_prefix}_open_status"

        def _known_bounded_transfer_count() -> int | None:
            if type(data) is bytes:
                return len(data)
            return 0 if not read_attempted else None

        def _retain_bounded_transfer_count(error: Exception) -> None:
            if max_bytes is None:
                return
            count = _known_bounded_transfer_count()
            if count is None:
                return
            with suppress(TypeError):
                vars(error)["bytes_read"] = count

        try:
            if self._ownership_index._path_has_symlink_component(path):
                raise ArtifactIntegrityError(f"CAS {member} path crosses a symlink")
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            phase = f"{transfer_prefix}_preflight"
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise ArtifactIntegrityError(f"CAS {member} member is not a regular file")
            if max_bytes is not None and before.st_size > max_bytes:
                if raise_read_limit:
                    raise ArtifactReadBoundsError(
                        member=member,
                        observed_bytes=before.st_size,
                        max_bytes=max_bytes,
                        bytes_read=0,
                    )
                raise ArtifactIntegrityError(f"CAS {member} member exceeds its size bound")
            stream = os.fdopen(descriptor, "rb")
            descriptor = -1
            try:
                phase = _usage_stage
                read_attempted = True
                if _read_attempt is not None and _usage_field is not None:
                    _read_attempt.begin(_usage_field, stage=_usage_stage)
                data = stream.read(-1 if max_bytes is None else max_bytes + 1)
                if _read_attempt is not None and _usage_field is not None:
                    _read_attempt.complete(_usage_field, len(data), stage=_usage_stage)
                phase = f"{transfer_prefix}_postread_validation"
                after = os.fstat(stream.fileno())
            except BaseException:
                stream_to_close = stream
                stream = None
                if stream_to_close is not None:
                    try:
                        stream_to_close.close()
                    except BaseException as close_error:
                        if _read_attempt is not None:
                            _read_attempt.cleanup_failed(
                                close_error,
                                stage=f"{transfer_prefix}_close",
                                primary_failure=True,
                            )
                raise
            else:
                stream_to_close = stream
                if stream_to_close is None:
                    raise RuntimeError("cas_manifest_stream_missing_after_open") from None
                stream = None
                try:
                    stream_to_close.close()
                except BaseException as close_error:
                    if _read_attempt is not None:
                        _read_attempt.cleanup_failed(
                            close_error,
                            stage=f"{transfer_prefix}_close",
                            primary_failure=False,
                        )
                    phase = f"{transfer_prefix}_close"
                    raise
            if max_bytes is not None and len(data) > max_bytes and raise_read_limit:
                raise ArtifactReadBoundsError(
                    member=member,
                    observed_bytes=len(data),
                    max_bytes=max_bytes,
                    bytes_read=len(data),
                )
            if (
                len(data) != before.st_size
                or after.st_size != before.st_size
                or after.st_mtime_ns != before.st_mtime_ns
                or after.st_ctime_ns != before.st_ctime_ns
            ):
                raise ArtifactIntegrityError(f"CAS {member} member changed while reading")
            return data
        except FileNotFoundError as exc:
            _retain_bounded_transfer_count(exc)
            if _read_attempt is not None:
                _read_attempt.failed(stage=phase)
            raise
        except ArtifactIntegrityError as exc:
            _retain_bounded_transfer_count(exc)
            if _read_attempt is not None:
                _read_attempt.failed(stage=phase)
            raise
        except OSError as exc:
            _retain_bounded_transfer_count(exc)
            if _read_attempt is not None:
                _read_attempt.failed(stage=phase)
            if self._read_only:
                unavailable = ArtifactReadOnlyUnavailableError(f"cas_{member}_read_unavailable")
                _retain_bounded_transfer_count(unavailable)
                raise unavailable from exc
            raise
        except Exception as exc:
            _retain_bounded_transfer_count(exc)
            if _read_attempt is not None:
                _read_attempt.failed(stage=phase)
            raise
        finally:
            if stream is not None:
                try:
                    stream.close()
                except BaseException as close_error:
                    if _read_attempt is not None:
                        _read_attempt.cleanup_failed(
                            close_error,
                            stage=f"{transfer_prefix}_close",
                            primary_failure=True,
                        )
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except BaseException as exc:
                    if _read_attempt is not None:
                        _read_attempt.cleanup_failed(
                            exc,
                            stage=f"{transfer_prefix}_close",
                            primary_failure=True,
                        )

    def _load_signature_for_snapshot(
        self,
        artifact_ref: ArtifactID | ArtifactRef,
        snapshot: _VerifiedArtifactSnapshot,
    ) -> DetachedSignature | None:
        """Read a signature bound to the exact already-verified selected snapshot."""
        aid, profile_sha256, _ref = _artifact_reference(artifact_ref)
        self._ownership_index.require_no_pending_transaction(
            aid,
            manifest_profile_sha256=profile_sha256,
            signature_profile=profile_sha256 or "default",
        )
        signature_path = self._sig_path(aid, profile_sha256)
        try:
            signature_bytes = self._read_cas_file_no_follow(
                signature_path,
                member="signature",
                max_bytes=1024 * 1024,
            )
        except FileNotFoundError:
            return None
        signature = DetachedSignature.model_validate_json(signature_bytes)
        if (
            signature.artifact_id != str(aid)
            or signature.statement.blob_sha256 != aid.hex
            or signature.statement.manifest_sha256
            != hashlib.sha256(snapshot.manifest_bytes).hexdigest()
        ):
            raise ArtifactIntegrityError(f"Signature binding mismatch for {aid}")
        return signature

    def _read_verified_blob(
        self,
        artifact_id: ArtifactID,
        blob_path: Path,
        *,
        manifest_ref: ArtifactRef | None = None,
    ) -> bytes:
        if self._read_only:
            data = self._read_cas_file_no_follow(blob_path, member="blob")
            manifest = self.get_manifest(manifest_ref or artifact_id)
            try:
                _validate_read_integrity_with_digest(
                    artifact_id,
                    data=data,
                    manifest=manifest,
                    actual_sha256_hex=content_hash(data),
                )
            except ArtifactIntegrityError as exc:
                self._record_integrity_failure(reason=type(exc).__name__)
                raise
            return data
        return _read_verified_blob(
            artifact_id,
            blob_path,
            load_manifest=lambda selected_id: self.get_manifest(manifest_ref or selected_id),
            record_integrity_failure=self._record_integrity_failure,
        )

    @_transactional_read()
    def _load_verified_snapshot(
        self,
        artifact_id: ArtifactID | ArtifactRef,
    ) -> _VerifiedArtifactSnapshot:
        """Load one owned, integrity-checked bytes/manifest snapshot."""
        aid, profile_sha256, ref = _artifact_reference(artifact_id)
        self._require_blob_owner(aid, operation="verify")
        if profile_sha256 is None:
            self._require_default_manifest_access(aid, operation="verify_manifest")
        else:
            self._require_manifest_view_owner(
                aid,
                profile_sha256,
                operation="verify_manifest",
            )
        blob, _default_manifest = self._paths(aid)
        manifest_path = self._manifest_path_for_ref(aid, profile_sha256)
        manifest_bytes = self._read_cas_file_no_follow(
            manifest_path,
            member="manifest",
        )
        data = self._read_cas_file_no_follow(blob, member="blob")
        manifest = ArtifactManifest.model_validate_json(manifest_bytes)
        if profile_sha256 is not None and (
            self._manifests.profile_sha256(manifest) != profile_sha256
        ):
            raise ArtifactIntegrityError(f"Selected manifest profile mismatch for {aid}")
        if ref is not None and (ref.kind != manifest.kind or ref.media_type != manifest.media_type):
            raise ArtifactIntegrityError(
                f"Artifact reference type does not match selected manifest for {aid}"
            )
        actual_sha256_hex = content_hash(data)
        try:
            _validate_read_integrity_with_digest(
                aid,
                data=data,
                manifest=manifest,
                actual_sha256_hex=actual_sha256_hex,
            )
        except ArtifactIntegrityError as exc:
            self._record_integrity_failure(reason=type(exc).__name__)
            raise
        return _VerifiedArtifactSnapshot(
            data=data,
            manifest_bytes=manifest_bytes,
            actual_sha256_hex=actual_sha256_hex,
            byte_size=len(data),
        )


class ReadOnlyFileSystemCAS(ArtifactReader):
    """Expose a FileSystemCAS read path without exposing its writer interface."""

    __slots__ = ("__store",)

    def __init__(self, store: FileSystemCAS, *, _token: object) -> None:
        if _token is not _READ_ONLY_READER_TOKEN or not store._read_only:
            raise TypeError("read_only_filesystem_cas_must_use_existing_root_opener")
        self.__store = store

    def has(self, artifact_id: ArtifactID | ArtifactRef | str) -> bool:
        """Return whether the selected content-bound artifact view exists."""
        return self.__store.has(artifact_id)

    def get_bytes(self, artifact_id: ArtifactID | ArtifactRef | str) -> bytes:
        """Read bytes after existing owner, transaction, and integrity checks."""
        return self.__store.get_bytes(artifact_id)

    def open_member(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        member: ArtifactMemberKind,
        *,
        max_manifest_bytes: int | None = None,
        expected_manifest_sha256: str | None = None,
        max_member_bytes: int | None = None,
    ) -> AbstractContextManager[_VerifiedCASMemberStream]:
        """Stream one exact selected member through the existing owner-verified CAS path."""
        return self.__store.open_member(
            artifact_id,
            member,
            max_manifest_bytes=max_manifest_bytes,
            expected_manifest_sha256=expected_manifest_sha256,
            max_member_bytes=max_member_bytes,
        )

    def open_member_bounded(
        self,
        artifact_id: ArtifactRef,
        member: Literal["blob"],
        *,
        max_manifest_bytes: int,
        expected_manifest_sha256: str,
        max_member_bytes: int,
    ) -> _BoundedMemberOpenAttempt:
        """Open a bounded blob through the read-only owner facade."""
        return self.__store.open_member_bounded(
            artifact_id,
            member,
            max_manifest_bytes=max_manifest_bytes,
            expected_manifest_sha256=expected_manifest_sha256,
            max_member_bytes=max_member_bytes,
        )

    def get_manifest(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
    ) -> ArtifactManifest:
        """Read and validate the selected typed manifest view."""
        return self.__store.get_manifest(artifact_id)

    def get_manifest_by_profile(
        self,
        artifact_id: ArtifactID | str,
        manifest_profile_sha256: str,
    ) -> ArtifactManifest:
        """Resolve one exact selected manifest through the guarded store."""
        return self.__store.get_manifest_by_profile(artifact_id, manifest_profile_sha256)

    def get_raw_manifest_bytes(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        *,
        manifest_profile_sha256: str | None = None,
    ) -> bytes:
        """Read exact selected sidecar bytes through the guarded store."""
        return self.__store.get_raw_manifest_bytes(
            artifact_id,
            manifest_profile_sha256=manifest_profile_sha256,
        )

    def get_raw_manifest_bytes_bounded(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        *,
        max_manifest_bytes: int,
        manifest_profile_sha256: str | None = None,
    ) -> bytes:
        """Read bounded default or exact manifest bytes through the owner facade."""
        return self.__store.get_raw_manifest_bytes_bounded(
            artifact_id,
            max_manifest_bytes=max_manifest_bytes,
            manifest_profile_sha256=manifest_profile_sha256,
        )

    def get_raw_manifest_bytes_bounded_for_input(
        self,
        input_ref: InputRef,
        *,
        max_manifest_bytes: int,
    ) -> bytes:
        """Read exact bounded manifest bytes selected by one explicit input edge."""
        return self.__store.get_raw_manifest_bytes_bounded_for_input(
            input_ref,
            max_manifest_bytes=max_manifest_bytes,
        )

    def read_raw_manifest_bytes_bounded(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        *,
        max_manifest_bytes: int,
        manifest_profile_sha256: str | None = None,
    ) -> ArtifactBoundedManifestRead:
        """Read default or exact manifest bytes and owner usage through the facade."""
        return self.__store.read_raw_manifest_bytes_bounded(
            artifact_id,
            max_manifest_bytes=max_manifest_bytes,
            manifest_profile_sha256=manifest_profile_sha256,
        )

    def read_raw_manifest_bytes_bounded_for_input(
        self,
        input_ref: InputRef,
        *,
        max_manifest_bytes: int,
    ) -> ArtifactBoundedManifestRead:
        """Read an input-selected manifest with owner usage through the facade."""
        return self.__store.read_raw_manifest_bytes_bounded_for_input(
            input_ref,
            max_manifest_bytes=max_manifest_bytes,
        )

    def verify(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
    ) -> VerificationReport:
        """Verify the selected artifact view without exposing write operations."""
        return self.__store.verify(artifact_id)
