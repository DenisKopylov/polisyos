"""Managed trusted-builtin child custody using the existing Core run and CAS.

This owner is installed by engine bootstrap with its actual run and a trusted
schema resolver. Node arguments are requests, never admission or release grants.
It does not confine arbitrary Python, foreign effects, or operating-system access.
"""

from __future__ import annotations

import hashlib
import json
import threading
from contextlib import AbstractContextManager, contextmanager, nullcontext, suppress
from copy import deepcopy
from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from polisyos.common.borrowed_execution import _OwnedEffectOutcomeUnknownError

from ..artifacts._manifest_lifecycle import ManifestLifecycle
from ..artifacts.child_release import (
    _CHILD_STAGING_TOKEN,
    _RELEASE_KIND,
    _RELEASE_SCHEMA,
    ChildJobReleaseClaim,
    ChildJobReleaseLocator,
    ChildJobScopeClaim,
    ChildJobSessionClaim,
    ChildReleaseRecord,
    ChildReleaseUnavailableError,
    _child_job_owner,
    _ChildReleaseLedger,
    child_binding_digest,
)
from ..artifacts.ids import ArtifactID
from ..artifacts.manifest import (
    ArtifactChildReleaseInfo,
    ArtifactManifest,
    ArtifactRef,
    ArtifactTenantContextInfo,
    InputRef,
    SchemaInfo,
    WarningRecord,
)
from ..artifacts.store import FileSystemCAS
from ..artifacts.write_contract import ArtifactWriteOptions
from .context import ChildRunStartUnknown, RunContext
from .manifest import RunManifest

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence
    from pathlib import Path

    from polisyos.common.borrowed_execution import _BorrowedControlLiveness

    from ..artifacts._integrity_ops import ArtifactBoundedManifestRead, VerificationReport
    from ..artifacts.canonical_profile import (
        CoreJsonArtifactBoundedRead,
        CoreJsonManifestBoundedRead,
        CoreJsonReadLimits,
    )
    from ..artifacts.protocol import ArtifactReader
    from ..artifacts.store import (
        ArtifactMemberReceipt,
        ImportPublication,
        _BoundedMemberOpenAttempt,
        _VerifiedCASMemberStream,
    )
    from ..canon import CanonSpec


class ChildComputationBinding(BaseModel):
    """Actual engine-admitted parent attempt and inherited wall deadline receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    root_run_id: str = Field(min_length=1)
    control_job_id: str | None
    parent_attempt_id: str = Field(min_length=1)
    parent_basis_ref: ArtifactRef
    tenant_id: str | None
    cell_id: str | None
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    template_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    admission_id: str = Field(min_length=1)
    child_invocation_id: str = Field(min_length=1)
    admission_generation: int = Field(ge=0)
    deadline: datetime

    @model_validator(mode="after")
    def _selected_and_aware(self) -> ChildComputationBinding:
        if self.parent_basis_ref.manifest_profile_sha256 is None:
            raise ValueError("child_parent_basis_profile_required")
        if self.deadline.tzinfo is None or self.deadline.utcoffset() is None:
            raise ValueError("child_deadline_not_aware")
        return self


class ChildPublicationFence(Protocol):
    """Configured actual job admission; publication holds only a short DB fence."""

    root_run_id: str
    control_job_id: str | None
    tenant_id: str | None
    cell_id: str | None

    def check_active(self) -> None:
        """Refuse a revoked, expired or superseded actual execution admission."""
        ...

    def local_consumption(self) -> AbstractContextManager[None]:
        """Fence a short local owner transition against parent revocation."""
        ...

    def authorize_release(self, candidate: ChildJobReleaseCandidate) -> ChildJobReleaseLocator:
        """Commit exact job-owner release authorization after live admission."""
        ...

    def publication(self) -> AbstractContextManager[None]:
        """Join currentness verification and Core's durable release-head commit."""
        ...


class ChildOutputClosureResolver(Protocol):
    """Configured typed schema owner, never a caller-supplied closure assertion."""

    def resolve(
        self, store: ArtifactReader, projection_ref: ArtifactRef
    ) -> tuple[ArtifactRef, ...]:
        """Recompute the complete typed payload and manifest selected-ref closure."""
        ...


def _key(ref: ArtifactRef) -> tuple[str, str, str, str]:
    if type(ref) is not ArtifactRef or ref.manifest_profile_sha256 is None:
        raise ChildReleaseUnavailableError("exact_selected_reference_required")
    return str(ref.artifact_id), ref.kind, ref.media_type, ref.manifest_profile_sha256


def _snapshot_selected_ref(ref: ArtifactRef) -> ArtifactRef:
    """Detach a typed or journaled ref before matching the owner's exact basis.

    Never call a subclass serializer: only the selected four fields are relevant,
    and the resulting key must still be present in this scope's owner-held set.
    """
    try:
        values = object.__getattribute__(ref, "__dict__")
        artifact_id = values["artifact_id"]
        if not isinstance(artifact_id, ArtifactID):
            raise TypeError
        raw_id = object.__getattribute__(artifact_id, "__dict__")["root"]
        kind = values["kind"]
        media_type = values["media_type"]
        profile = values["manifest_profile_sha256"]
        if any(type(item) is not str for item in (raw_id, kind, media_type, profile)):
            raise TypeError
        return ArtifactRef.model_validate(
            {
                "artifact_id": raw_id,
                "kind": kind,
                "media_type": media_type,
                "manifest_profile_sha256": profile,
            }
        )
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ChildReleaseUnavailableError("exact_selected_reference_required") from exc


def _selected(manifest: ArtifactManifest) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=manifest.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=ManifestLifecycle.profile_sha256(manifest),
    )


def _binding_payload(binding: ChildComputationBinding) -> dict[str, JsonValue]:
    # Round-trip through the strict DTO's JSON serializer, never arbitrary objects.
    return json.loads(binding.model_dump_json())


_JOB_SNAPSHOT_MAX_BYTES = 256 * 1024
_JOB_COLLECTION_MAX_ITEMS = 4096


def _bounded_snapshot(value: object) -> bytes:
    """Encode a finite job-owner snapshot with early size and shape refusal."""
    pending = [value]
    nodes = 0
    while pending:
        current = pending.pop()
        nodes += 1
        if nodes > _JOB_SNAPSHOT_MAX_BYTES:
            raise ChildReleaseUnavailableError("job_owner_snapshot_limit")
        if type(current) is str and len(current) > _JOB_SNAPSHOT_MAX_BYTES:
            raise ChildReleaseUnavailableError("job_owner_snapshot_limit")
        if type(current) is dict:
            if len(current) > _JOB_COLLECTION_MAX_ITEMS:
                raise ChildReleaseUnavailableError("job_owner_snapshot_limit")
            pending.extend(current.keys())
            pending.extend(current.values())
        elif type(current) in {tuple, list}:
            if len(current) > _JOB_COLLECTION_MAX_ITEMS:
                raise ChildReleaseUnavailableError("job_owner_snapshot_limit")
            pending.extend(current)
    chunks: list[bytes] = []
    total = 0
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), allow_nan=False)
    for text in encoder.iterencode(value):
        if len(text) > _JOB_SNAPSHOT_MAX_BYTES:
            raise ChildReleaseUnavailableError("job_owner_snapshot_limit")
        chunk = text.encode()
        total += len(chunk)
        if total > _JOB_SNAPSHOT_MAX_BYTES:
            raise ChildReleaseUnavailableError("job_owner_snapshot_limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _model_snapshot(value: BaseModel | None) -> bytes:
    """Freeze complete typed JSON content without retaining mutable nested DTOs."""
    _preflight_raw_shape([value])
    payload = None if value is None else value.model_dump(mode="json")
    return _bounded_snapshot(payload)


@dataclass(frozen=True)
class ChildReleaseReceipt:
    """Selected author result; distinct from engine, reviewer and G acceptance."""

    release_id: str
    release_ref: ArtifactRef
    projection_ref: ArtifactRef
    released_refs: tuple[ArtifactRef, ...]
    execution_outcome: Literal["completed", "partial", "failed", "unknown"]
    release_outcome: Literal[
        "released",
        "released_ack_reconciled",
        "release_visible_durability_unknown",
        "release_state_unknown",
    ]
    isolation_coverage: Literal["managed_interfaces_trusted_builtin_local"] = (
        "managed_interfaces_trusted_builtin_local"
    )
    root_run_id: str | None = None
    parent_attempt_id: str | None = None
    parent_basis_json: bytes | None = None
    job_intent_locator: ChildJobReleaseLocator | None = None
    job_authorization_locator: ChildJobReleaseLocator | None = None


@dataclass(frozen=True)
class ChildRecoveryLocator:
    """Stable parent basis and optional committed job intent for reconciliation."""

    release_id: str
    root_run_id: str
    parent_attempt_id: str
    parent_basis_json: bytes
    job_intent_locator: ChildJobReleaseLocator | None


class ChildComputationOutcomeUnknown(_OwnedEffectOutcomeUnknownError):  # noqa: N818
    """A child computation has an unresolved durable or in-flight outcome."""

    recovery: ChildRecoveryLocator | None = None


class ChildParentSettlementError(ChildComputationOutcomeUnknown):
    """A release or its settlement has an outcome requiring owner reconciliation."""

    def __init__(self, receipt: ChildReleaseReceipt) -> None:
        self.receipt = receipt
        self.recovery = (
            ChildRecoveryLocator(
                release_id=receipt.release_id,
                root_run_id=receipt.root_run_id,
                parent_attempt_id=receipt.parent_attempt_id,
                parent_basis_json=receipt.parent_basis_json,
                job_intent_locator=receipt.job_intent_locator,
            )
            if receipt.root_run_id is not None
            and receipt.parent_attempt_id is not None
            and receipt.parent_basis_json is not None
            else None
        )
        self.reason = "child_release_or_parent_settlement_unknown"
        super().__init__(self.reason)


_CHILD_GUARDED_READER_BOOTSTRAP_TOKEN = object()


class _ChildGuardedReadService(Protocol):
    """Fixed Runtime-appointed reader; no caller-provided worker callbacks."""

    def require_registration(self) -> None:
        """Reconcile the actual guarded registrations before owner decisions."""

    def require_control_registration(self, control: object) -> None:
        """Reconcile the same registrations on an admitted control worker."""

    def publication_registration(self) -> AbstractContextManager[None]:
        """Order the short release-head decision against registration changes."""

    def read_manifest(
        self,
        capability: ChildOneRefReadCapability,
        *,
        max_manifest_bytes: int,
        allow_profile_absent: bool,
    ) -> CoreJsonManifestBoundedRead: ...

    def read_input_manifest(
        self,
        capability: ChildOneRefReadCapability,
        input_ref: InputRef,
        *,
        max_manifest_bytes: int,
    ) -> CoreJsonManifestBoundedRead: ...

    def read_json(
        self, capability: ChildOneRefReadCapability, *, limits: CoreJsonReadLimits
    ) -> CoreJsonArtifactBoundedRead: ...

    def read_blob(self, capability: ChildOneRefReadCapability) -> bytes: ...

    def has(self, capability: ChildOneRefReadCapability) -> bool: ...

    def verify(self, capability: ChildOneRefReadCapability) -> VerificationReport: ...

    def write_bytes(self, capability: ChildStageWriteCapability) -> ArtifactRef: ...

    def write_json(self, capability: ChildStageWriteCapability) -> ArtifactRef: ...

    def verify_blob(
        self,
        capability: ChildOneRefReadCapability,
        *,
        max_manifest_bytes: int,
        max_member_bytes: int,
    ) -> ArtifactMemberReceipt: ...

    def transfer_selected(
        self, capability: ChildSelectedTransferCapability
    ) -> ImportPublication: ...

    def has_unsettled_operations(self) -> bool: ...


class ChildOneRefReadCapability:
    """Opaque owner-issued read of one exact profile on one actual CAS owner."""

    def __init__(
        self,
        owner: ChildComputationCustody,
        store: _ManagedStore,
        source: FileSystemCAS,
        ref: ArtifactRef,
    ) -> None:
        self.__owner = owner
        self.__store = store
        self.__source = source
        self.__ref_snapshot = _model_snapshot(ref)
        self.__thread_id = threading.get_ident()

    def _claim_for_runtime(
        self, expected_session: ChildComputationCustody
    ) -> tuple[FileSystemCAS, ArtifactRef]:
        """Reconcile owner identity and scope on its original execution thread."""
        owner = self.__owner
        if expected_session is not owner or threading.get_ident() != self.__thread_id:
            raise ChildReleaseUnavailableError("guarded_read_session_or_thread_mismatch")
        with owner._lock:
            if owner._read_capabilities.get(id(self)) is not self:
                raise ChildReleaseUnavailableError("guarded_read_capability_not_current")
        ref = ArtifactRef.model_validate_json(self.__ref_snapshot)
        source, actual = self.__store._resolve(ref)
        if source is not self.__source or _model_snapshot(actual) != self.__ref_snapshot:
            raise ChildReleaseUnavailableError("guarded_read_selected_ref_changed")
        return source, actual.model_copy(deep=True)


def _write_value_snapshot(value: object) -> object:
    """Project exact typed write metadata into finite detached JSON values."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _write_value_snapshot(getattr(value, field.name)) for field in fields(value)
        }
    if type(value) in {list, tuple}:
        return [_write_value_snapshot(item) for item in value]
    if type(value) is dict:
        return {key: _write_value_snapshot(item) for key, item in value.items()}
    if value is None or type(value) in {str, bool, int, float}:
        return value
    raise ChildReleaseUnavailableError("guarded_write_metadata_untyped")


class ChildGuardedStageWriteUnknown(ChildComputationOutcomeUnknown):
    """A guarded stage write or its capture has an unresolved outcome."""

    def __init__(
        self,
        *,
        release_id: str,
        root_run_id: str,
        parent_attempt_id: str,
        parent_basis_json: bytes,
        job_intent_locator: ChildJobReleaseLocator | None,
        observed_ref: ArtifactRef | None = None,
    ) -> None:
        self.recovery = ChildRecoveryLocator(
            release_id=release_id,
            root_run_id=root_run_id,
            parent_attempt_id=parent_attempt_id,
            parent_basis_json=parent_basis_json,
            job_intent_locator=job_intent_locator,
        )
        self.observed_ref = observed_ref.model_copy(deep=True) if observed_ref is not None else None
        self.reason = "guarded_stage_write_or_capture_unknown"
        super().__init__(self.reason)


class ChildSessionAdmissionUnknown(ChildComputationOutcomeUnknown):
    """A session owner transaction may have committed without a known locator."""

    def __init__(self, recovery: ChildRecoveryLocator | None) -> None:
        self.recovery = recovery
        super().__init__("child_session_admission_unknown")


class ChildScopePreparationUnknown(ChildComputationOutcomeUnknown):
    """A private child start may have persisted an incomplete run."""

    def __init__(
        self,
        recovery: ChildRecoveryLocator | None,
        *,
        child_run_id: str,
        run_dir: str,
        scope_id: str | None,
    ) -> None:
        self.recovery = recovery
        self.child_run_id = child_run_id
        self.run_dir = run_dir
        self.scope_id = scope_id
        super().__init__("child_scope_preparation_unknown")


class ChildScopeAdmissionUnknown(ChildComputationOutcomeUnknown):
    """A scope admission event may have committed without a known outcome."""

    def __init__(
        self,
        recovery: ChildRecoveryLocator | None,
        *,
        scope_claim_json: bytes,
        scope_locator: ChildJobReleaseLocator | None = None,
    ) -> None:
        if type(scope_claim_json) is not bytes or len(scope_claim_json) > _JOB_SNAPSHOT_MAX_BYTES:
            raise ValueError("scope_recovery_claim_bytes_required")
        self.recovery = recovery
        self.scope_claim_json = scope_claim_json
        self.scope_locator = (
            scope_locator.model_copy(deep=True) if scope_locator is not None else None
        )
        super().__init__("child_scope_admission_unknown")


class ChildRevocationUnknown(ChildComputationOutcomeUnknown):
    """A durable revocation could not be acknowledged and needs reconciliation."""

    def __init__(self, recovery: ChildRecoveryLocator | None) -> None:
        self.recovery = recovery
        super().__init__("child_revocation_unknown")


class ChildGuardedReadUnknown(ChildComputationOutcomeUnknown):
    """A timed-out guarded CAS read may still be in flight."""

    def __init__(self, recovery: ChildRecoveryLocator | None) -> None:
        self.recovery = recovery
        self.reason = "guarded_cas_read_unknown"
        super().__init__(self.reason)


class ChildGuardedTransferUnknown(ChildComputationOutcomeUnknown):
    """A selected transfer may still have in-flight private/public CAS effects."""

    def __init__(self, recovery: ChildRecoveryLocator | None) -> None:
        self.recovery = recovery
        self.reason = "guarded_selected_transfer_unknown"
        super().__init__(self.reason)


class ChildStageWriteCapability:
    """Owner-issued one-use private-stage write, detached from caller objects."""

    def __init__(
        self,
        owner: ChildComputationCustody,
        store: _ManagedStore,
        kind: Literal["bytes", "json"],
        payload: object,
        options: ArtifactWriteOptions,
        canon_spec: CanonSpec | None,
        *,
        allow_preparing: bool = False,
    ) -> None:
        from ..canon import CanonSpec as CoreCanonSpec
        from ..canon import to_canonical_bytes

        self.__owner = owner
        self.__store = store
        self.__stage = owner._stage
        self.__kind = kind
        self.__allow_preparing = allow_preparing
        self.__thread_id = threading.get_ident()
        _preflight_raw_shape([getattr(options, field.name) for field in fields(options)])
        self.__options = deepcopy(options)
        self.__options_snapshot = _bounded_snapshot(_write_value_snapshot(self.__options))
        self.__canon_spec = deepcopy(canon_spec)
        self.__spec_snapshot = _bounded_snapshot(_write_value_snapshot(self.__canon_spec))
        if kind == "bytes":
            if type(payload) is not bytes or canon_spec is not None:
                raise ChildReleaseUnavailableError("guarded_write_payload_invalid")
            self.__payload_bytes = payload
        elif kind == "json":
            spec = self.__canon_spec if self.__canon_spec is not None else CoreCanonSpec()
            self.__payload_bytes = to_canonical_bytes(payload, spec)
        else:
            raise ChildReleaseUnavailableError("guarded_write_kind_invalid")

    def _expected_digest(self) -> str:
        """Return the immutable canonical/byte payload digest for readback binding."""
        return hashlib.sha256(self.__payload_bytes).hexdigest()

    def _claim_for_runtime(
        self, expected_session: ChildComputationCustody
    ) -> tuple[
        FileSystemCAS, Literal["bytes", "json"], object, ArtifactWriteOptions, CanonSpec | None
    ]:
        """Return detached options/payload only to the owner thread while active."""
        from ..canon import CanonSpec as CoreCanonSpec
        from ..canon import from_canonical_bytes, to_canonical_bytes

        owner = self.__owner
        if expected_session is not owner or threading.get_ident() != self.__thread_id:
            raise ChildReleaseUnavailableError("guarded_write_session_or_thread_mismatch")
        with owner._lock:
            if (
                owner._write_capabilities.get(id(self)) is not self
                or owner._stage is not self.__stage
            ):
                raise ChildReleaseUnavailableError("guarded_write_capability_not_current")
        self.__store._require_guarded_write_current(allow_preparing=self.__allow_preparing)
        if (
            _bounded_snapshot(_write_value_snapshot(self.__options)) != self.__options_snapshot
            or _bounded_snapshot(_write_value_snapshot(self.__canon_spec)) != self.__spec_snapshot
        ):
            raise ChildReleaseUnavailableError("guarded_write_metadata_changed")
        if self.__kind == "json":
            spec = self.__canon_spec if self.__canon_spec is not None else CoreCanonSpec()
            payload = from_canonical_bytes(
                self.__payload_bytes, max_depth=spec.max_depth, version=spec.version
            )
            if to_canonical_bytes(payload, spec) != self.__payload_bytes:
                raise ChildReleaseUnavailableError("guarded_write_payload_roundtrip_mismatch")
        else:
            payload = self.__payload_bytes
        return (
            self.__stage,
            self.__kind,
            payload,
            deepcopy(self.__options),
            deepcopy(self.__canon_spec),
        )


class ChildSelectedTransferCapability:
    """Owner-issued exact selected transfer, with no job grant on the worker."""

    def __init__(self, owner: ChildComputationCustody, refs: Sequence[ArtifactRef]) -> None:
        self.__owner = owner
        self.__source = owner._stage
        self.__served = owner._served
        self.__ledger = owner._ledger
        self.__refs = tuple(_model_snapshot(ref) for ref in refs)
        self.__thread_id = threading.get_ident()

    def _claim_for_runtime(
        self, expected_session: ChildComputationCustody
    ) -> tuple[FileSystemCAS, FileSystemCAS, tuple[ArtifactRef, ...], _ChildReleaseLedger]:
        """Resolve unchanged owner, selected refs and current attempt on its thread."""
        owner = self.__owner
        if expected_session is not owner or threading.get_ident() != self.__thread_id:
            raise ChildReleaseUnavailableError("guarded_transfer_session_or_thread_mismatch")
        with owner._lock:
            if owner._transfer_capability is not self or owner._state != "preparing":
                raise ChildReleaseUnavailableError("guarded_transfer_capability_not_current")
            if owner._stage is not self.__source or owner._served is not self.__served:
                raise ChildReleaseUnavailableError("guarded_transfer_backend_changed")
            if owner._ledger is not self.__ledger or owner._binding is None:
                raise ChildReleaseUnavailableError("guarded_transfer_owner_changed")
            binding = owner._binding
        owner._check_root(binding)
        refs = tuple(ArtifactRef.model_validate_json(raw) for raw in self.__refs)
        return self.__source, self.__served, refs, self.__ledger


class _ManagedStore:
    """Exact-basis facade; deliberately no generic delegation or raw-store escape."""

    __slots__ = (
        "__binding",
        "__info",
        "__owner",
        "__refs",
        "__scope_id",
        "__weakref__",
        "__writable",
        "__writes",
    )

    def __init__(
        self,
        owner: ChildComputationCustody,
        scope_id: str,
        binding: ChildComputationBinding,
        info: ArtifactChildReleaseInfo,
        refs: Sequence[ArtifactRef],
        *,
        writable: bool = True,
    ) -> None:
        self.__owner = owner
        self.__scope_id = scope_id
        self.__binding = binding.model_copy(deep=True)
        self.__info = info
        self.__refs = {_key(ref): _model_snapshot(ref) for ref in refs}
        self.__writes: dict[tuple[str, str, str, str], bytes] = {}
        self.__writable = writable
        if owner._guarded_reader_service is not None:
            from ..artifacts.canonical_profile import (
                _GUARDED_CANONICAL_BOOTSTRAP_TOKEN,
                _register_guarded_canonical_reader,
            )

            _register_guarded_canonical_reader(self, token=_GUARDED_CANONICAL_BOOTSTRAP_TOKEN)

    @property
    def _tenant_id(self) -> str | None:
        return self.__binding.tenant_id

    @property
    def _cell_id(self) -> str | None:
        return self.__binding.cell_id

    def _enroll(self, refs: Sequence[ArtifactRef]) -> None:
        self.__refs.update((_key(ref), _model_snapshot(ref)) for ref in refs)

    def _admission_refs_snapshot(self) -> bytes:
        """Freeze this actual scope's complete selected input grant without I/O."""
        values = [raw.decode("utf-8") for _, raw in sorted(self.__refs.items())]
        _preflight_raw_shape([values])
        return _bounded_snapshot(values)

    def _written(self) -> tuple[ArtifactRef, ...]:
        return tuple(ArtifactRef.model_validate_json(raw) for raw in self.__writes.values())

    def _require_owned_release_profile(self, ref: ArtifactRef, manifest: ArtifactManifest) -> None:
        """Reconcile a private run artifact against this scope's actual writes."""
        source, selected = self._resolve(ref)
        if (
            source is not self.__owner._stage
            or _key(selected) not in self.__writes
            or self.__owner._infos.get(self.__scope_id) != self.__info
            or manifest.child_release != self.__info
            or _selected(manifest) != selected
        ):
            raise ChildReleaseUnavailableError("private_release_profile_not_owned")

    def _resolve(
        self, value: ArtifactID | ArtifactRef | str, profile: str | None = None
    ) -> tuple[FileSystemCAS, ArtifactRef]:
        self.__owner._require_store_active(self.__scope_id, writing=False)
        if isinstance(value, ArtifactRef):
            selected = _snapshot_selected_ref(value)
            if profile is not None and profile != selected.manifest_profile_sha256:
                raise ChildReleaseUnavailableError("conflicting_profile_selector")
            key = _key(selected)
            raw = self.__refs.get(key) or self.__writes.get(key)
        else:
            aid = ArtifactID.model_validate(value)
            matches = {
                key: raw
                for key, raw in (*self.__refs.items(), *self.__writes.items())
                if key[0] == str(aid) and (profile is None or key[3] == profile)
            }
            key, raw = next(iter(matches.items())) if len(matches) == 1 else (None, None)
        if key is None or raw is None:
            raise ChildReleaseUnavailableError("private_exact_read_basis_denied")
        ref = ArtifactRef.model_validate_json(raw)
        if _key(ref) != key:
            raise ChildReleaseUnavailableError("private_exact_read_basis_corrupt")
        return self.__owner._source_for(ref), ref

    def is_previously_authorized(self, ref: ArtifactRef) -> bool:
        """Test the session's original exact input grant, never a staged write."""
        source, selected = self._resolve(ref)
        key = _key(selected)
        if source is not self.__owner._served or key not in self.__owner._prior_inputs:
            return False
        if key not in self.__owner._inputs:
            return False
        if self.__owner._guarded_reader_service is not None:
            read = self._guarded_manifest_read(
                selected,
                max_manifest_bytes=8 * 1024 * 1024,
                manifest_profile_sha256=None,
                allow_profile_absent=True,
            )
            return _selected(read.manifest) == selected
        return _selected(source.get_manifest(selected)) == selected

    def _issue_guarded_read(self, ref: ArtifactRef) -> ChildOneRefReadCapability:
        """Mint one owner-held exact-ref capability after current scope admission."""
        source, selected = self._resolve(ref)
        capability = ChildOneRefReadCapability(self.__owner, self, source, selected)
        with self.__owner._lock:
            if self.__owner._state not in {"open", "preparing", "released"}:
                raise ChildReleaseUnavailableError("guarded_read_session_closed")
            if len(self.__owner._read_capabilities) >= _JOB_COLLECTION_MAX_ITEMS:
                raise ChildReleaseUnavailableError("guarded_read_capability_limit")
            self.__owner._read_capabilities[id(capability)] = capability
        return capability

    def _release_guarded_read(self, capability: ChildOneRefReadCapability) -> None:
        """Invalidate a one-ref capability on success, refusal or timeout."""
        with self.__owner._lock:
            if self.__owner._read_capabilities.get(id(capability)) is capability:
                del self.__owner._read_capabilities[id(capability)]

    def _require_guarded_write_current(self, *, allow_preparing: bool = False) -> None:
        self.__owner._require_store_active(self.__scope_id, writing=not allow_preparing)
        if allow_preparing and self.__owner._state != "preparing":
            raise ChildReleaseUnavailableError("guarded_release_record_not_preparing")

    def _issue_guarded_write(
        self,
        kind: Literal["bytes", "json"],
        payload: object,
        options: ArtifactWriteOptions,
        canon_spec: CanonSpec | None,
        *,
        allow_preparing: bool = False,
    ) -> ChildStageWriteCapability:
        self._require_guarded_write_current(allow_preparing=allow_preparing)
        capability = ChildStageWriteCapability(
            self.__owner,
            self,
            kind,
            payload,
            options,
            canon_spec,
            allow_preparing=allow_preparing,
        )
        with self.__owner._lock:
            if self.__owner._state != ("preparing" if allow_preparing else "open"):
                raise ChildReleaseUnavailableError("guarded_write_session_closed")
            if len(self.__owner._write_capabilities) >= _JOB_COLLECTION_MAX_ITEMS:
                raise ChildReleaseUnavailableError("guarded_write_capability_limit")
            self.__owner._write_capabilities[id(capability)] = capability
        return capability

    def _release_guarded_write(self, capability: ChildStageWriteCapability) -> None:
        with self.__owner._lock:
            if self.__owner._write_capabilities.get(id(capability)) is capability:
                del self.__owner._write_capabilities[id(capability)]

    def _capture_guarded_write(
        self,
        ref: ArtifactRef,
        capability: ChildStageWriteCapability,
        options: ArtifactWriteOptions,
        *,
        media_type: str,
        allow_profile_absent: bool,
        allow_preparing: bool = False,
    ) -> None:
        if (
            type(ref) is not ArtifactRef
            or ref.manifest_profile_sha256 is None
            or ref.kind != options.kind
            or ref.media_type != media_type
            or ref.artifact_id.hex != capability._expected_digest()
        ):
            raise ChildReleaseUnavailableError("guarded_write_result_identity_mismatch")
        key = _key(ref)
        with self.__owner._lock:
            if self.__owner._state != ("preparing" if allow_preparing else "open"):
                raise ChildReleaseUnavailableError("guarded_write_session_closed")
            existing = self.__owner._writes.get(key)
            if existing is not None and existing[1] != self.__scope_id:
                raise ChildReleaseUnavailableError("guarded_write_scope_conflict")
            self.__owner._writes[key] = (ref.model_copy(deep=True), self.__scope_id)
            self.__writes[key] = _model_snapshot(ref)
        read = self._guarded_manifest_read(
            ref,
            max_manifest_bytes=8 * 1024 * 1024,
            manifest_profile_sha256=None,
            allow_profile_absent=allow_profile_absent,
        )
        if read.manifest.child_release != self.__info or _selected(read.manifest) != ref:
            raise ChildReleaseUnavailableError("managed_write_owner_mismatch")
        with self.__owner._lock:
            if self.__owner._state != ("preparing" if allow_preparing else "open"):
                raise ChildReleaseUnavailableError("guarded_write_session_closed")
            self.__owner._enforce_job_owner_budget()

    def _perform_guarded_write(
        self,
        kind: Literal["bytes", "json"],
        payload: object,
        options: ArtifactWriteOptions,
        canon_spec: CanonSpec | None,
        *,
        allow_preparing: bool = False,
    ) -> ArtifactRef:
        service = self.__owner._guarded_reader_service
        if service is None:
            raise ChildReleaseUnavailableError("guarded_reader_not_appointed")
        capability = self._issue_guarded_write(
            kind, payload, options, canon_spec, allow_preparing=allow_preparing
        )
        observed_ref: ArtifactRef | None = None
        try:
            ref = (
                service.write_bytes(capability)
                if kind == "bytes"
                else service.write_json(capability)
            )
            if type(ref) is ArtifactRef:
                observed_ref = ref.model_copy(deep=True)
            capability._claim_for_runtime(self.__owner)
            self._capture_guarded_write(
                ref,
                capability,
                options,
                media_type=options.media_type if kind == "bytes" else "application/json",
                allow_profile_absent=kind == "bytes",
                allow_preparing=allow_preparing,
            )
            return ref.model_copy(deep=True)
        except BaseException as exc:
            with self.__owner._lock:
                if self.__owner._state != "released":
                    self.__owner._state = "revoked"
            binding_snapshot = self.__owner._admitted_binding_snapshot
            if binding_snapshot is None:
                raise ChildReleaseUnavailableError("guarded_write_binding_missing") from exc
            binding = ChildComputationBinding.model_validate_json(binding_snapshot)
            raise ChildGuardedStageWriteUnknown(
                release_id=self.__owner._release_id,
                root_run_id=binding.root_run_id,
                parent_attempt_id=binding.parent_attempt_id,
                parent_basis_json=_model_snapshot(binding.parent_basis_ref),
                job_intent_locator=self.__owner._job_intent_locator,
                observed_ref=observed_ref,
            ) from exc
        finally:
            self._release_guarded_write(capability)

    def _guarded_manifest_read(
        self,
        value: ArtifactRef | ArtifactID,
        *,
        max_manifest_bytes: int,
        manifest_profile_sha256: str | None,
        allow_profile_absent: bool,
    ) -> CoreJsonManifestBoundedRead:
        from ..artifacts.canonical_profile import CoreJsonManifestBoundedRead

        _source, selected = self._resolve(value, manifest_profile_sha256)
        service = self.__owner._guarded_reader_service
        if service is None:
            raise ChildReleaseUnavailableError("guarded_reader_not_appointed")
        capability = self._issue_guarded_read(selected)
        try:
            result = service.read_manifest(
                capability,
                max_manifest_bytes=max_manifest_bytes,
                allow_profile_absent=allow_profile_absent,
            )
            if type(result) is not CoreJsonManifestBoundedRead or result.effective_ref != selected:
                raise ChildReleaseUnavailableError("guarded_manifest_receipt_mismatch")
            capability._claim_for_runtime(self.__owner)
            return result
        finally:
            self._release_guarded_read(capability)

    def _guarded_input_manifest_read(
        self, input_ref: InputRef, *, max_manifest_bytes: int
    ) -> CoreJsonManifestBoundedRead:
        from ..artifacts.canonical_profile import CoreJsonManifestBoundedRead

        input_snapshot = _model_snapshot(input_ref)
        _source, selected = self._resolve(input_ref.artifact_id, input_ref.manifest_profile_sha256)
        service = self.__owner._guarded_reader_service
        if service is None:
            raise ChildReleaseUnavailableError("guarded_reader_not_appointed")
        capability = self._issue_guarded_read(selected)
        try:
            result = service.read_input_manifest(
                capability, input_ref.model_copy(deep=True), max_manifest_bytes=max_manifest_bytes
            )
            if (
                type(result) is not CoreJsonManifestBoundedRead
                or result.effective_ref != selected
                or _model_snapshot(input_ref) != input_snapshot
            ):
                raise ChildReleaseUnavailableError("guarded_input_manifest_receipt_mismatch")
            capability._claim_for_runtime(self.__owner)
            return result
        finally:
            self._release_guarded_read(capability)

    def _guarded_json_read(
        self,
        selected_ref: ArtifactRef,
        *,
        limits: CoreJsonReadLimits,
        manifest_read: CoreJsonManifestBoundedRead | None,
    ) -> CoreJsonArtifactBoundedRead:
        from ..artifacts.canonical_profile import (
            CoreJsonArtifactBoundedRead,
            CoreJsonManifestBoundedRead,
        )

        _source, selected = self._resolve(selected_ref)
        if manifest_read is not None and (
            type(manifest_read) is not CoreJsonManifestBoundedRead
            or manifest_read.effective_ref != selected
            or len(manifest_read.raw_manifest_bytes) > limits.max_manifest_bytes
        ):
            raise ChildReleaseUnavailableError("guarded_manifest_receipt_mismatch")
        service = self.__owner._guarded_reader_service
        if service is None:
            raise ChildReleaseUnavailableError("guarded_reader_not_appointed")
        capability = self._issue_guarded_read(selected)
        try:
            result = service.read_json(capability, limits=limits)
            if (
                type(result) is not CoreJsonArtifactBoundedRead
                or result.effective_ref != selected
                or result.limits != limits
                or not result.payload_integrity_verified
                or (
                    manifest_read is not None
                    and result.raw_manifest_bytes != manifest_read.raw_manifest_bytes
                )
            ):
                raise ChildReleaseUnavailableError("guarded_json_receipt_mismatch")
            _ = result.profile_read  # Recompute sealed canonical bytes/identity on owner thread.
            capability._claim_for_runtime(self.__owner)
            return result
        finally:
            self._release_guarded_read(capability)

    def _guarded_verify_blob(self, ref: ArtifactRef, *, byte_size: int) -> None:
        from ..artifacts.store import ArtifactMemberReceipt

        service = self.__owner._guarded_reader_service
        if service is None:
            raise ChildReleaseUnavailableError("guarded_reader_not_appointed")
        capability = self._issue_guarded_read(ref)
        try:
            receipt = service.verify_blob(
                capability,
                max_manifest_bytes=8 * 1024 * 1024,
                max_member_bytes=max(byte_size, 1),
            )
            if (
                type(receipt) is not ArtifactMemberReceipt
                or receipt.member
                != self.__owner._source_for(ref)._member_name(
                    ref.artifact_id, "blob", ref.manifest_profile_sha256
                )
                or receipt.sha256 != ref.artifact_id.hex
                or receipt.byte_size != byte_size
            ):
                raise ChildReleaseUnavailableError("guarded_blob_receipt_mismatch")
            capability._claim_for_runtime(self.__owner)
        finally:
            self._release_guarded_read(capability)

    def has(self, artifact_id: ArtifactID | ArtifactRef | str) -> bool:
        """Test availability only inside this exact authorized view."""
        service = self.__owner._guarded_reader_service
        if service is not None:
            _source, ref = self._resolve(artifact_id)
            capability = self._issue_guarded_read(ref)
            try:
                result = service.has(capability)
                if type(result) is not bool:
                    raise ChildReleaseUnavailableError("guarded_has_result_invalid")
                capability._claim_for_runtime(self.__owner)
                return result
            finally:
                self._release_guarded_read(capability)
        store, ref = self._resolve(artifact_id)
        return store.has(ref)

    def get_bytes(self, artifact_id: ArtifactID | ArtifactRef | str) -> bytes:
        """Read one exact authorized selected artifact."""
        service = self.__owner._guarded_reader_service
        if service is not None:
            _source, ref = self._resolve(artifact_id)
            capability = self._issue_guarded_read(ref)
            try:
                data = service.read_blob(capability)
                if (
                    type(data) is not bytes
                    or hashlib.sha256(data).hexdigest() != ref.artifact_id.hex
                ):
                    raise ChildReleaseUnavailableError("guarded_blob_result_invalid")
                capability._claim_for_runtime(self.__owner)
                return data
            finally:
                self._release_guarded_read(capability)
        store, ref = self._resolve(artifact_id)
        return store.get_bytes(ref)

    def get_manifest(self, artifact_id: ArtifactID | ArtifactRef | str) -> ArtifactManifest:
        """Read one exact authorized selected manifest."""
        if self.__owner._guarded_reader_service is not None:
            read = self._guarded_manifest_read(
                artifact_id,
                max_manifest_bytes=8 * 1024 * 1024,
                manifest_profile_sha256=None,
                allow_profile_absent=True,
            )
            return read.manifest
        store, ref = self._resolve(artifact_id)
        return store.get_manifest(ref)

    def get_manifest_by_profile(
        self, artifact_id: ArtifactID | str, manifest_profile_sha256: str
    ) -> ArtifactManifest:
        """Read a selected profile without permitting a default-view substitution."""
        if self.__owner._guarded_reader_service is not None:
            read = self._guarded_manifest_read(
                ArtifactID.model_validate(artifact_id),
                max_manifest_bytes=8 * 1024 * 1024,
                manifest_profile_sha256=manifest_profile_sha256,
                allow_profile_absent=True,
            )
            return read.manifest
        store, ref = self._resolve(artifact_id, manifest_profile_sha256)
        return store.get_manifest(ref)

    def get_raw_manifest_bytes(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        *,
        manifest_profile_sha256: str | None = None,
    ) -> bytes:
        """Read exact raw bytes through existing owner checks."""
        if self.__owner._guarded_reader_service is not None:
            return self._guarded_manifest_read(
                artifact_id,
                max_manifest_bytes=8 * 1024 * 1024,
                manifest_profile_sha256=manifest_profile_sha256,
                allow_profile_absent=True,
            ).raw_manifest_bytes
        store, ref = self._resolve(artifact_id, manifest_profile_sha256)
        return store.get_raw_manifest_bytes(ref)

    def get_raw_manifest_bytes_bounded(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        *,
        max_manifest_bytes: int,
        manifest_profile_sha256: str | None = None,
    ) -> bytes:
        """Preserve the actual bounded selected-sidecar read budget."""
        if self.__owner._guarded_reader_service is not None:
            return self._guarded_manifest_read(
                artifact_id,
                max_manifest_bytes=max_manifest_bytes,
                manifest_profile_sha256=manifest_profile_sha256,
                allow_profile_absent=True,
            ).raw_manifest_bytes
        store, ref = self._resolve(artifact_id, manifest_profile_sha256)
        return store.get_raw_manifest_bytes_bounded(ref, max_manifest_bytes=max_manifest_bytes)

    def read_raw_manifest_bytes_bounded(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        *,
        max_manifest_bytes: int,
        manifest_profile_sha256: str | None = None,
    ) -> ArtifactBoundedManifestRead:
        """Preserve the actual bounded selected-sidecar read and usage result."""
        if self.__owner._guarded_reader_service is not None:
            from ..artifacts._integrity_ops import ArtifactBoundedManifestRead

            read = self._guarded_manifest_read(
                artifact_id,
                max_manifest_bytes=max_manifest_bytes,
                manifest_profile_sha256=manifest_profile_sha256,
                allow_profile_absent=True,
            )
            if read.usage is None:
                raise ChildReleaseUnavailableError("guarded_manifest_usage_missing")
            return ArtifactBoundedManifestRead(read.raw_manifest_bytes, read.usage)
        store, ref = self._resolve(artifact_id, manifest_profile_sha256)
        return store.read_raw_manifest_bytes_bounded(ref, max_manifest_bytes=max_manifest_bytes)

    def get_raw_manifest_bytes_bounded_for_input(
        self, input_ref: InputRef, *, max_manifest_bytes: int
    ) -> bytes:
        """Read only an admitted exact input profile."""
        if self.__owner._guarded_reader_service is not None:
            if type(input_ref) is not InputRef or input_ref.manifest_profile_sha256 is None:
                raise ChildReleaseUnavailableError("exact_selected_reference_required")
            _source, ref = self._resolve(input_ref.artifact_id, input_ref.manifest_profile_sha256)
            return self._guarded_manifest_read(
                ref,
                max_manifest_bytes=max_manifest_bytes,
                manifest_profile_sha256=None,
                allow_profile_absent=True,
            ).raw_manifest_bytes
        store, ref = self._resolve(input_ref.artifact_id, input_ref.manifest_profile_sha256)
        return store.get_raw_manifest_bytes_bounded(ref, max_manifest_bytes=max_manifest_bytes)

    def read_raw_manifest_bytes_bounded_for_input(
        self, input_ref: InputRef, *, max_manifest_bytes: int
    ) -> ArtifactBoundedManifestRead:
        """Return measured usage for an admitted exact input profile."""
        if self.__owner._guarded_reader_service is not None:
            from ..artifacts._integrity_ops import ArtifactBoundedManifestRead

            if type(input_ref) is not InputRef or input_ref.manifest_profile_sha256 is None:
                raise ChildReleaseUnavailableError("exact_selected_reference_required")
            _source, ref = self._resolve(input_ref.artifact_id, input_ref.manifest_profile_sha256)
            read = self._guarded_manifest_read(
                ref,
                max_manifest_bytes=max_manifest_bytes,
                manifest_profile_sha256=None,
                allow_profile_absent=True,
            )
            if read.usage is None:
                raise ChildReleaseUnavailableError("guarded_manifest_usage_missing")
            return ArtifactBoundedManifestRead(read.raw_manifest_bytes, read.usage)
        store, ref = self._resolve(input_ref.artifact_id, input_ref.manifest_profile_sha256)
        return store.read_raw_manifest_bytes_bounded(ref, max_manifest_bytes=max_manifest_bytes)

    def verify(self, artifact_id: ArtifactID | ArtifactRef | str) -> VerificationReport:
        """Verify existing bytes and profile inside the private basis."""
        service = self.__owner._guarded_reader_service
        if service is not None:
            from ..artifacts._integrity_ops import VerificationReport

            _source, ref = self._resolve(artifact_id)
            capability = self._issue_guarded_read(ref)
            try:
                result = service.verify(capability)
                if (
                    type(result) is not VerificationReport
                    or result.artifact_id != str(ref.artifact_id)
                    or result.expected_sha256_hex != ref.artifact_id.hex
                    or (result.ok and result.actual_sha256_hex != ref.artifact_id.hex)
                ):
                    raise ChildReleaseUnavailableError("guarded_verify_result_invalid")
                capability._claim_for_runtime(self.__owner)
                return result
            finally:
                self._release_guarded_read(capability)
        store, ref = self._resolve(artifact_id)
        return store.verify(ref)

    def iter_artifact_ids(self) -> list[ArtifactID]:
        """Enumerate this facade's admitted refs, never the shared private namespace."""
        self.__owner._require_store_active(self.__scope_id, writing=False)
        return sorted(
            {ArtifactID.model_validate(key[0]) for key in (*self.__refs, *self.__writes)}, key=str
        )

    @contextmanager
    def open_member(
        self,
        artifact_id: ArtifactID | ArtifactRef | str,
        member: Literal["blob", "manifest", "signature"],
        *,
        max_manifest_bytes: int | None = None,
        expected_manifest_sha256: str | None = None,
        max_member_bytes: int | None = None,
    ) -> Iterator[_VerifiedCASMemberStream]:
        """Use the underlying verified stream without exposing its path or descriptor."""
        if self.__owner._guarded_reader_service is not None:
            raise ChildReleaseUnavailableError("guarded_direct_read_operation_unavailable")
        store, ref = self._resolve(artifact_id)
        with store.open_member(
            ref,
            member,
            max_manifest_bytes=max_manifest_bytes,
            expected_manifest_sha256=expected_manifest_sha256,
            max_member_bytes=max_member_bytes,
        ) as stream:
            yield stream

    def open_member_bounded(
        self,
        artifact_id: ArtifactRef,
        member: Literal["blob"],
        *,
        max_manifest_bytes: int,
        expected_manifest_sha256: str,
        max_member_bytes: int,
    ) -> _BoundedMemberOpenAttempt:
        """Preserve the existing bounded stream and its actual read usage receipts."""
        if self.__owner._guarded_reader_service is not None:
            raise ChildReleaseUnavailableError("guarded_direct_read_operation_unavailable")
        store, ref = self._resolve(artifact_id)
        return store.open_member_bounded(
            ref,
            member,
            max_manifest_bytes=max_manifest_bytes,
            expected_manifest_sha256=expected_manifest_sha256,
            max_member_bytes=max_member_bytes,
        )

    def _options(self, opts: ArtifactWriteOptions) -> ArtifactWriteOptions:
        if type(opts) is not ArtifactWriteOptions:
            raise ChildReleaseUnavailableError("managed_write_options_type_invalid")
        if opts.child_release is not None:
            raise ChildReleaseUnavailableError("caller_child_release_metadata_forbidden")
        if opts.authority is not None or opts.same_input_closure is not None:
            raise ChildReleaseUnavailableError("candidate_child_authority_write_forbidden")
        expected = (
            ArtifactTenantContextInfo(
                tenant_id=self.__binding.tenant_id, cell_id=self.__binding.cell_id
            )
            if self.__binding.tenant_id is not None
            else None
        )
        if opts.tenant_context is not None and opts.tenant_context != expected:
            raise ChildReleaseUnavailableError("child_write_tenant_mismatch")
        normalized: list[InputRef] = []
        if (
            self.__binding.control_job_id is not None
            and opts.inputs is not None
            and len(opts.inputs) > _JOB_COLLECTION_MAX_ITEMS
        ):
            self.__owner._refuse_job_owner_budget()
        for edge in opts.inputs or ():
            if type(edge) is not InputRef:
                raise ChildReleaseUnavailableError("child_write_input_type_invalid")
            _store, ref = self._resolve(edge.artifact_id, edge.manifest_profile_sha256)
            normalized.append(
                edge.model_copy(update={"manifest_profile_sha256": ref.manifest_profile_sha256})
            )
        return replace(opts, child_release=self.__info, tenant_context=expected, inputs=normalized)

    def put_bytes(
        self, data: bytes, opts: ArtifactWriteOptions, *, return_selected_profile: bool = False
    ) -> ArtifactRef:
        """Force the actual owner class and retain the exact written occurrence."""
        if not self.__writable:
            raise ChildReleaseUnavailableError("private_handoff_read_only")
        self.__owner._require_store_active(self.__scope_id, writing=True)
        forced = self._options(opts)
        if self.__owner._guarded_reader_service is not None:
            return self._perform_guarded_write("bytes", data, forced, None)
        ref = self.__owner._stage.put_bytes(data, forced, return_selected_profile=True)
        self.__owner._capture_write(self.__scope_id, ref)
        self.__writes[_key(ref)] = _model_snapshot(ref)
        return ref

    def put_json(
        self,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec: CanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        """Apply existing canonical JSON checks before an owner-bound child write."""
        if not self.__writable:
            raise ChildReleaseUnavailableError("private_handoff_read_only")
        self.__owner._require_store_active(self.__scope_id, writing=True)
        forced = self._options(opts)
        if self.__owner._guarded_reader_service is not None:
            return self._perform_guarded_write("json", obj, forced, canon_spec)
        ref = self.__owner._stage.put_json(obj, forced, canon_spec, return_selected_profile=True)
        self.__owner._capture_write(self.__scope_id, ref)
        self.__writes[_key(ref)] = _model_snapshot(ref)
        return ref


@dataclass(frozen=True)
class ChildStagingScope:
    """Opaque registered child; constructing a lookalike does not enroll it."""

    scope_id: str
    binding: ChildComputationBinding
    run: RunContext
    store: _ManagedStore


@contextmanager
def _try_root_custody_locks(owner: ChildComputationCustody) -> Iterator[None]:
    """Use actual owner locks without waiting while the outer grant is held."""
    root_lock = owner._root._worker_merge_lock
    if not root_lock.acquire(blocking=False):
        raise ChildReleaseUnavailableError("prepared_scope_root_transition_busy")
    try:
        if not owner._lock.acquire(blocking=False):
            raise ChildReleaseUnavailableError("prepared_scope_owner_busy")
        try:
            yield
        finally:
            owner._lock.release()
    finally:
        root_lock.release()


class ChildPreparedScope:
    """Owner-held private scope awaiting a durable job/grant admission decision."""

    def __init__(
        self,
        owner: ChildComputationCustody,
        scope: ChildStagingScope,
        root_snapshot: tuple[bytes, bytes],
    ) -> None:
        self.__owner = owner
        self.__scope = scope
        self.__root_snapshot = root_snapshot
        self.__binding_snapshot = _model_snapshot(scope.binding)
        self.__info_snapshot = _model_snapshot(owner._infos[scope.scope_id])
        self.__parent_snapshot = _bounded_snapshot(
            scope.binding.model_dump(mode="json", exclude={"child_invocation_id"})
        )
        self.__input_snapshot = scope.store._admission_refs_snapshot()
        self.__store = scope.store
        self.__run = scope.run
        self.__thread_id = threading.get_ident()
        self.__claim_snapshot: bytes | None = None
        self.__admitted = False

    @contextmanager
    def _short_decision(self) -> Iterator[None]:
        """Take the existing Root/custody locks without waiting under job/grant."""
        with _try_root_custody_locks(self.__owner):
            yield

    def _owned_claim(
        self, *, control_operation: _ChildControlOperation | None = None
    ) -> ChildJobScopeClaim:
        """Recompute the exact locally owned scope claim without external I/O."""
        owner = self.__owner
        scope = self.__scope
        binding = owner._binding
        intent = owner._job_intent_locator
        if (
            owner._prepared_scopes.get(scope.scope_id) is not self
            or owner._scopes.get(scope.scope_id) is not scope
            or owner._state != "open"
            or scope.scope_id in owner._revoked
            or scope.store is not self.__store
            or scope.run is not self.__run
            or _model_snapshot(scope.binding) != self.__binding_snapshot
            or scope.store._admission_refs_snapshot() != self.__input_snapshot
            or binding is None
            or _model_snapshot(binding) != owner._admitted_binding_snapshot
            or _bounded_snapshot(binding.model_dump(mode="json", exclude={"child_invocation_id"}))
            != self.__parent_snapshot
            or scope.scope_id not in owner._bindings
            or _model_snapshot(owner._bindings[scope.scope_id]) != self.__binding_snapshot
            or scope.scope_id not in owner._infos
            or _model_snapshot(owner._infos[scope.scope_id]) != self.__info_snapshot
            or type(intent) is not ChildJobReleaseLocator
            or binding.control_job_id is None
            or binding.tenant_id is None
            or binding.cell_id is None
        ):
            raise ChildReleaseUnavailableError("prepared_scope_not_current")
        owner._require_root_snapshot(
            scope.binding, self.__root_snapshot, control_operation=control_operation
        )
        session = ChildJobSessionClaim(
            release_id=owner._release_id,
            root_run_id=binding.root_run_id,
            control_job_id=binding.control_job_id,
            parent_attempt_id=binding.parent_attempt_id,
            parent_basis_ref=binding.parent_basis_ref.model_copy(deep=True),
            tenant_id=binding.tenant_id,
            cell_id=binding.cell_id,
            admission_generation=binding.admission_generation,
            deadline=binding.deadline,
            served_store_identity=owner._ledger.store_identity,
        )
        return ChildJobScopeClaim(
            session=session,
            session_intent=intent.model_copy(deep=True),
            scope_id=scope.scope_id,
            child_run_id=scope.run.run_manifest.run_id,
            child_invocation_id=scope.binding.child_invocation_id,
            scope_binding_sha256="sha256:" + hashlib.sha256(self.__binding_snapshot).hexdigest(),
            input_grants_sha256="sha256:" + hashlib.sha256(self.__input_snapshot).hexdigest(),
        )

    def recompute(self) -> ChildJobScopeClaim:
        """Resolve current owner state before entering the job/resource decision."""
        if threading.get_ident() != self.__thread_id or self.__admitted:
            raise ChildReleaseUnavailableError("prepared_scope_not_current")
        owner = self.__owner
        if owner._root_preflight(self.__scope.binding) != self.__root_snapshot:
            raise ChildReleaseUnavailableError("prepared_scope_parent_changed")
        with self._short_decision():
            claim = self._owned_claim()
            self.__claim_snapshot = _model_snapshot(claim)
            return ChildJobScopeClaim.model_validate_json(self.__claim_snapshot)

    def _issue_guarded_operation(self, control: object) -> _ChildControlOperation:
        from .worker_lifecycle import ChildRuntimeCapability

        owner = self.__owner
        capability = ChildRuntimeCapability.for_parent(
            owner._root, session=owner, runtime_control=control
        )
        operation = capability._issue_scope_operation(self)
        if type(operation) is not _ChildControlOperation:
            raise ChildReleaseUnavailableError("control_operation_not_owner_issued")
        return operation

    def admit(
        self, claim: ChildJobScopeClaim, *, expected_parent: ChildComputationBinding
    ) -> bytes:
        """Freeze the local decision before the job owner inserts its event."""
        return self._admission(claim, expected_parent=expected_parent, control_operation=None)

    def _admission(
        self,
        claim: ChildJobScopeClaim,
        *,
        expected_parent: ChildComputationBinding,
        control_operation: _ChildControlOperation | None,
    ) -> bytes:
        if (
            (threading.get_ident() != self.__thread_id and control_operation is None)
            or type(claim) is not ChildJobScopeClaim
            or type(expected_parent) is not ChildComputationBinding
        ):
            raise ChildReleaseUnavailableError("prepared_scope_claim_invalid")
        if control_operation is not None:
            control_operation._require_worker(self.__owner)
        _preflight_raw_shape([expected_parent])
        parent_snapshot = _bounded_snapshot(
            expected_parent.model_dump(mode="json", exclude={"child_invocation_id"})
        )
        with self._short_decision():
            _preflight_raw_shape([expected_parent])
            if (
                self.__admitted
                or self.__claim_snapshot is None
                or parent_snapshot != self.__parent_snapshot
                or _bounded_snapshot(
                    expected_parent.model_dump(mode="json", exclude={"child_invocation_id"})
                )
                != self.__parent_snapshot
                or _model_snapshot(claim) != self.__claim_snapshot
                or _model_snapshot(self._owned_claim(control_operation=control_operation))
                != self.__claim_snapshot
            ):
                raise ChildReleaseUnavailableError("prepared_scope_claim_changed")
            self.__admitted = True
            decision = self.__claim_snapshot
        return decision

    def _admission_for_control(
        self, claim: ChildJobScopeClaim, operation: _ChildControlOperation
    ) -> bytes:
        binding = self.__owner._binding
        if binding is None:
            raise ChildReleaseUnavailableError("prepared_scope_parent_missing")
        return self._admission(claim, expected_parent=binding, control_operation=operation)

    def _check_control_current(
        self, claim: ChildJobScopeClaim, operation: _ChildControlOperation
    ) -> None:
        operation._require_worker(self.__owner)
        with self._short_decision():
            if (
                not self.__admitted
                or self.__claim_snapshot is None
                or type(claim) is not ChildJobScopeClaim
                or _model_snapshot(claim) != self.__claim_snapshot
                or _model_snapshot(self._owned_claim(control_operation=operation))
                != self.__claim_snapshot
            ):
                raise ChildReleaseUnavailableError("prepared_scope_claim_changed")

    def complete(self, locator: ChildJobReleaseLocator) -> ChildStagingScope:
        """Reconcile the committed job-owner event, then transfer the scope once."""
        owner = self.__owner
        if threading.get_ident() != self.__thread_id or type(locator) is not ChildJobReleaseLocator:
            raise ChildReleaseUnavailableError("prepared_scope_locator_invalid")
        if not self.__admitted or self.__claim_snapshot is None:
            raise ChildReleaseUnavailableError("prepared_scope_not_admitted")
        locator_snapshot = _model_snapshot(locator)
        claim = ChildJobScopeClaim.model_validate_json(self.__claim_snapshot)
        result = _child_job_owner(claim.session.served_store_identity).verify_scope(locator, claim)
        if result is not None:
            raise ChildReleaseUnavailableError("job_owner_verifier_protocol_invalid")
        if _model_snapshot(locator) != locator_snapshot:
            raise ChildReleaseUnavailableError("prepared_scope_locator_changed")
        if owner._root_preflight(self.__scope.binding) != self.__root_snapshot:
            raise ChildReleaseUnavailableError("prepared_scope_parent_changed")
        registration = (
            owner._guarded_reader_service.publication_registration()
            if owner._guarded_reader_service is not None
            else nullcontext()
        )
        with (
            owner._root._parent_state_transition_lease(run_scoped=False),
            owner._lock,
            owner._local_consumption(),
            registration,
        ):
            if _model_snapshot(self._owned_claim()) != self.__claim_snapshot:
                raise ChildReleaseUnavailableError("prepared_scope_claim_changed")
            scope = self.__scope
            del owner._prepared_scopes[scope.scope_id]
            return scope

    def abandon(self) -> None:
        """Close a rejected prepared scope after the outer job/grant lock is released."""
        owner = self.__owner
        if threading.get_ident() != self.__thread_id:
            raise ChildReleaseUnavailableError("prepared_scope_thread_mismatch")
        with owner._lock:
            if owner._prepared_scopes.get(self.__scope.scope_id) is not self:
                raise ChildReleaseUnavailableError("prepared_scope_not_current")
            del owner._prepared_scopes[self.__scope.scope_id]
            self.__admitted = False
        revoke_error: BaseException | None = None
        try:
            owner.revoke(self.__scope, reason="prepared_scope_admission_failed")
        except BaseException as exc:
            revoke_error = exc
        try:
            # Existing Root owner releases its active lease without issuing a
            # terminal CAS write; the private store remains revoked. A failed
            # suspension is not a quiescence or rollback receipt.
            self.__scope.run.suspend_for_resume()
        except BaseException as exc:
            if revoke_error is not None:
                revoke_error.add_note("Private scope suspension also failed: " + type(exc).__name__)
            else:
                raise ChildRevocationUnknown(owner._recovery_locator()) from exc
        if revoke_error is not None:
            raise revoke_error


@dataclass(frozen=True)
class PrivateChildHandoff:
    """Selected private handoff; no public release or authority is implied."""

    scope_id: str
    binding: ChildComputationBinding
    projection_ref: ArtifactRef
    selected_refs: tuple[ArtifactRef, ...]
    store: ArtifactReader


class ChildJobSessionIntent:
    """Opaque Core-owned parent-attempt locator, established before computation."""

    def __init__(self, owner: ChildComputationCustody, binding: ChildComputationBinding) -> None:
        self.__owner = owner
        self.__binding = binding.model_copy(deep=True)
        self.__binding_snapshot = _model_snapshot(self.__binding)
        if self.__binding_snapshot != owner._admitted_binding_snapshot:
            raise ChildReleaseUnavailableError("job_session_binding_not_owner_admitted")
        self.__claim_snapshot: bytes | None = None
        self.__tail_snapshot: bytes | None = None

    def recompute(self) -> ChildJobSessionClaim:
        """Validate the actual Root and invocation basis outside the DB lock."""
        owner = self.__owner
        binding = self.__binding
        if binding.control_job_id is None or binding.tenant_id is None or binding.cell_id is None:
            raise ChildReleaseUnavailableError("job_release_scope_missing")
        tail = _model_snapshot(owner._root._runtime_invocation_tail_ref)
        if _model_snapshot(binding) != self.__binding_snapshot:
            raise ChildReleaseUnavailableError("job_session_binding_changed")
        owner._check_root(binding)
        with owner._lock:
            if owner._job_intent is not self or owner._state != "open":
                raise ChildReleaseUnavailableError("job_session_intent_not_current")
            if (
                _model_snapshot(owner._root._runtime_invocation_tail_ref) != tail
                or _model_snapshot(owner._binding) != self.__binding_snapshot
            ):
                raise ChildReleaseUnavailableError("job_session_basis_changed")
            claim = ChildJobSessionClaim(
                release_id=owner._release_id,
                root_run_id=binding.root_run_id,
                control_job_id=binding.control_job_id,
                parent_attempt_id=binding.parent_attempt_id,
                parent_basis_ref=binding.parent_basis_ref,
                tenant_id=binding.tenant_id,
                cell_id=binding.cell_id,
                admission_generation=binding.admission_generation,
                deadline=binding.deadline,
                served_store_identity=owner._ledger.store_identity,
            )
            self.__tail_snapshot = tail
            self.__claim_snapshot = _model_snapshot(claim)
            return claim.model_copy(deep=True)

    def _issue_guarded_operation(self, control: object) -> _ChildControlOperation:
        from .worker_lifecycle import ChildRuntimeCapability

        owner = self.__owner
        capability = ChildRuntimeCapability.for_parent(
            owner._root, session=owner, runtime_control=control
        )
        operation = capability._issue_session_operation(self)
        if type(operation) is not _ChildControlOperation:
            raise ChildReleaseUnavailableError("control_operation_not_owner_issued")
        return operation

    def admission(self, claim: ChildJobSessionClaim) -> bytes:
        """Freeze the local Root decision before the actual job-owner transaction."""
        return self._admission(claim, control_operation=None)

    def _admission(
        self, claim: ChildJobSessionClaim, *, control_operation: _ChildControlOperation | None
    ) -> bytes:
        owner = self.__owner
        with _try_root_custody_locks(owner):
            if owner._root._active_lease is None:
                raise ChildReleaseUnavailableError("root_active_lease_missing")
            owner._root._require_active_lease_owner()
            owner._require_guarded_owner_identity(control_operation=control_operation)
            if (
                owner._job_intent is not self
                or owner._state != "open"
                or self.__claim_snapshot is None
                or type(claim) is not ChildJobSessionClaim
                or _model_snapshot(claim) != self.__claim_snapshot
                or _model_snapshot(self.__binding) != self.__binding_snapshot
                or _model_snapshot(owner._binding) != self.__binding_snapshot
                or _model_snapshot(owner._root._runtime_invocation_tail_ref) != self.__tail_snapshot
                or owner._root._closed
                or owner._root._suspended
                or owner._root.run_manifest.status != "running"
                or (
                    owner._root.run_manifest.run_id,
                    owner._root.run_manifest.control_job_id,
                    owner._root.run_manifest.tenant_id,
                    owner._root.run_manifest.cell_id,
                )
                != (
                    self.__binding.root_run_id,
                    self.__binding.control_job_id,
                    self.__binding.tenant_id,
                    self.__binding.cell_id,
                )
                or self.__binding.deadline <= datetime.now(UTC)
            ):
                raise ChildReleaseUnavailableError("job_session_admission_stale")
            decision = self.__claim_snapshot
        return decision


_CHILD_CONTROL_OPERATION_TOKEN = object()


class _ChildControlOwner(Protocol):
    def _require_control_worker(self) -> None: ...

    def _check_control_admission(self, admission: object) -> None: ...

    def _control_liveness_for_core(
        self, owner: ChildComputationCustody
    ) -> _BorrowedControlLiveness: ...


class _ChildControlOperation:
    """One Core-recorded decision for the exact guarded control worker."""

    __slots__ = (
        "__active_thread",
        "__claim_snapshot",
        "__control",
        "__handle",
        "__kind",
        "__liveness",
        "__owner",
        "__parent_thread",
        "__used",
    )

    def __init__(
        self,
        owner: ChildComputationCustody,
        handle: ChildJobSessionIntent | ChildJobReleaseCandidate | ChildPreparedScope,
        claim: ChildJobSessionClaim | ChildJobReleaseClaim | ChildJobScopeClaim,
        kind: Literal["session", "authorization", "scope"],
        control: _ChildControlOwner,
        liveness: _BorrowedControlLiveness,
        *,
        token: object,
    ) -> None:
        if token is not _CHILD_CONTROL_OPERATION_TOKEN:
            raise ChildReleaseUnavailableError("control_operation_not_owner_issued")
        self.__owner = owner
        self.__handle = handle
        self.__kind = kind
        self.__claim_snapshot = _model_snapshot(claim)
        self.__control = control
        self.__liveness = liveness
        self.__parent_thread = threading.get_ident()
        self.__active_thread: int | None = None
        self.__used = False

    def _require_worker(self, owner: ChildComputationCustody) -> None:
        control: object = self.__control
        if (
            owner is not self.__owner
            or self.__active_thread != threading.get_ident()
            or self.__active_thread == self.__parent_thread
            or owner._control_operations.get(id(self)) is not self
            or owner._fence is not control
        ):
            raise ChildReleaseUnavailableError("control_operation_not_current")
        self.__control._require_control_worker()
        self.__liveness._require_current()

    def _preview(self) -> ChildJobSessionClaim | ChildJobReleaseClaim | ChildJobScopeClaim:
        """Return the detached owner claim only to the registered control worker."""
        self.__control._require_control_worker()
        self.__liveness._require_current()
        with self.__owner._lock:
            if self.__used or self.__owner._control_operations.get(id(self)) is not self:
                raise ChildReleaseUnavailableError("control_operation_not_current")
        return self._claim_model()

    def _claim_model(self) -> ChildJobSessionClaim | ChildJobReleaseClaim | ChildJobScopeClaim:
        model = {
            "session": ChildJobSessionClaim,
            "authorization": ChildJobReleaseClaim,
            "scope": ChildJobScopeClaim,
        }[self.__kind]
        return model.model_validate_json(self.__claim_snapshot)

    def _check_admission(self, admission: object) -> None:
        self.__control._require_control_worker()
        self.__liveness._require_current()
        self.__control._check_control_admission(admission)

    @contextmanager
    def _decision(self) -> Iterator[None]:
        """Consume the operation once under actual parent-attempt liveness."""
        owner = self.__owner
        self.__control._require_control_worker()
        with self.__liveness._admission():
            if not owner._lock.acquire(blocking=False):
                raise ChildReleaseUnavailableError("control_operation_owner_busy")
            try:
                if self.__used or owner._control_operations.get(id(self)) is not self:
                    raise ChildReleaseUnavailableError("control_operation_not_current")
                self.__used = True
                self.__active_thread = threading.get_ident()
            finally:
                owner._lock.release()
            try:
                self._require_worker(owner)
                yield
            finally:
                self.__active_thread = None

    def _admit(
        self, claim: ChildJobSessionClaim | ChildJobReleaseClaim | ChildJobScopeClaim
    ) -> bytes:
        self._require_worker(self.__owner)
        if (
            type(claim) is not type(self._claim_model())
            or _model_snapshot(claim) != self.__claim_snapshot
        ):
            raise ChildReleaseUnavailableError("control_operation_claim_changed")
        if (
            self.__kind == "scope"
            and type(self.__handle) is ChildPreparedScope
            and type(claim) is ChildJobScopeClaim
        ):
            return self.__handle._admission_for_control(claim, self)
        if (
            self.__kind == "session"
            and type(self.__handle) is ChildJobSessionIntent
            and type(claim) is ChildJobSessionClaim
        ):
            return self.__handle._admission(claim, control_operation=self)
        if (
            self.__kind == "authorization"
            and type(self.__handle) is ChildJobReleaseCandidate
            and type(claim) is ChildJobReleaseClaim
        ):
            return self.__handle._admission(claim, control_operation=self)
        raise ChildReleaseUnavailableError("control_operation_claim_changed")

    def _require_active(self) -> None:
        self._require_worker(self.__owner)
        claim = self._claim_model()
        if (
            self.__kind == "scope"
            and type(self.__handle) is ChildPreparedScope
            and type(claim) is ChildJobScopeClaim
        ):
            self.__handle._check_control_current(claim, self)
        else:
            self._admit(claim)

    def _recovery(self) -> ChildRecoveryLocator | None:
        if threading.get_ident() != self.__parent_thread:
            raise ChildReleaseUnavailableError("control_operation_parent_thread_mismatch")
        return self.__owner._recovery_locator()

    def _scope_recovery(self) -> tuple[ChildRecoveryLocator | None, bytes]:
        if threading.get_ident() != self.__parent_thread or self.__kind != "scope":
            raise ChildReleaseUnavailableError("control_operation_parent_thread_mismatch")
        return self.__owner._recovery_locator(), self.__claim_snapshot


def _preflight_raw_shape(pending: list[object]) -> None:
    """Bound raw owner objects before copying or normalizing their contents."""
    nodes = 0
    chars = 0
    while pending:
        item = pending.pop()
        nodes += 1
        if nodes > _JOB_SNAPSHOT_MAX_BYTES:
            raise ChildReleaseUnavailableError("job_owner_snapshot_limit")
        if isinstance(item, BaseModel):
            pending.append(item.__dict__)
        elif type(item) is dict:
            if len(item) > _JOB_COLLECTION_MAX_ITEMS:
                raise ChildReleaseUnavailableError("job_owner_snapshot_limit")
            pending.extend(item.keys())
            pending.extend(item.values())
        elif type(item) in {tuple, list, set, frozenset}:
            if len(item) > _JOB_COLLECTION_MAX_ITEMS:
                raise ChildReleaseUnavailableError("job_owner_snapshot_limit")
            pending.extend(item)
        elif type(item) in {str, bytes}:
            chars += len(item)
            if chars > _JOB_SNAPSHOT_MAX_BYTES:
                raise ChildReleaseUnavailableError("job_owner_snapshot_limit")


def _release_owner_snapshot(owner: ChildComputationCustody) -> bytes:
    """Freeze the complete live selection basis without retaining nested DTOs."""
    if any(
        len(items) > _JOB_COLLECTION_MAX_ITEMS
        for items in (
            owner._bindings,
            owner._infos,
            owner._writes,
            owner._inputs,
            owner._prior_inputs,
            owner._job_allowed_scopes,
            owner._updates,
            owner._events,
            owner._handoff_grants,
        )
    ):
        raise ChildReleaseUnavailableError("job_owner_snapshot_limit")
    _preflight_raw_shape(
        [
            owner._bindings,
            owner._infos,
            owner._writes,
            owner._inputs,
            owner._prior_inputs,
            owner._job_allowed_scopes,
            owner._updates,
            owner._events,
            owner._handoff_grants,
        ]
    )
    value = {
        "bindings": {key: _binding_payload(item) for key, item in owner._bindings.items()},
        "infos": {key: item.model_dump(mode="json") for key, item in owner._infos.items()},
        "writes": [
            {"identity": list(key), "ref": ref.model_dump(mode="json"), "scope": scope}
            for key, (ref, scope) in sorted(owner._writes.items())
        ],
        "inputs": [
            {"identity": list(key), "ref": ref.model_dump(mode="json")}
            for key, ref in sorted(owner._inputs.items())
        ],
        "prior_inputs": [list(key) for key in sorted(owner._prior_inputs)],
        "allowed_scopes": sorted(owner._job_allowed_scopes),
        "handoff_grants": {
            key: [raw.decode("utf-8") for raw in value]
            for key, value in owner._handoff_grants.items()
        },
        "parent_scope": owner._parent_scope,
        "effects": owner._effects_payload(),
    }
    return _bounded_snapshot(value)


class ChildJobReleaseCandidate:
    """Owner-held handle that recomputes a selected private release claim.

    This handle is issued by the configured Core custody session, never by a
    request or an independent caller. Its claim is not itself job authority.
    """

    def __init__(self, owner: ChildComputationCustody, record_ref: ArtifactRef) -> None:
        self.__owner = owner
        self.__record_ref = record_ref.model_copy(deep=True)
        self.__record_snapshot = _model_snapshot(self.__record_ref)
        self.__binding_snapshot: bytes | None = None
        self.__owner_snapshot: bytes | None = None
        self.__claim_snapshot: bytes | None = None
        self.__tail_snapshot: bytes | None = None

    def recompute(self) -> ChildJobReleaseClaim:
        """Resolve the actual staged record and final closure outside the DB lock."""
        owner = self.__owner
        with owner._lock:
            if owner._job_candidate is not self or owner._state != "preparing":
                raise ChildReleaseUnavailableError("job_release_candidate_not_current")
            binding = owner._binding
            parent = owner._parent
            if binding is None or parent is None or binding.control_job_id is None:
                raise ChildReleaseUnavailableError("job_release_candidate_binding_missing")
            owner_snapshot = _release_owner_snapshot(owner)
        tail = _model_snapshot(owner._root._runtime_invocation_tail_ref)
        binding_snapshot = _model_snapshot(binding)
        if binding_snapshot != owner._admitted_binding_snapshot:
            raise ChildReleaseUnavailableError("job_release_binding_not_owner_admitted")
        if _model_snapshot(self.__record_ref) != self.__record_snapshot:
            raise ChildReleaseUnavailableError("job_release_record_identity_changed")
        owner._check_root(binding)
        record_store = parent if owner._guarded_reader_service is not None else owner._stage
        manifest = record_store.get_manifest(self.__record_ref)
        if (
            _selected(manifest) != self.__record_ref
            or manifest.kind != _RELEASE_KIND
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name != _RELEASE_SCHEMA
            or manifest.artifact_schema.version != "1.0"
        ):
            raise ChildReleaseUnavailableError("job_release_candidate_record_invalid")
        record = ChildReleaseRecord.model_validate_json(record_store.get_bytes(self.__record_ref))
        closure = owner._closure(parent, record.projection_ref)
        selected = tuple(ref for ref in closure if _key(ref) in owner._writes)
        if (
            record.release_id != owner._release_id
            or record.root_run_id != binding.root_run_id
            or record.parent_attempt_id != binding.parent_attempt_id
            or record.parent_basis_ref != binding.parent_basis_ref
            or record.tenant_id != binding.tenant_id
            or record.cell_id != binding.cell_id
            or {_key(ref) for ref in record.released_refs} != {_key(ref) for ref in selected}
            or any(
                owner._writes[_key(ref)][1] != owner._parent_scope
                and owner._writes[_key(ref)][1] not in owner._job_allowed_scopes
                for ref in selected
            )
            or {info.scope_id for info in record.scope_bindings}
            != {owner._writes[_key(ref)][1] for ref in selected}
            or child_binding_digest(record.parent_effects) != record.parent_effects_sha256
            or record.parent_effects != owner._effects_payload()
            or set(record.binding_payloads) != {info.scope_id for info in record.scope_bindings}
            or any(
                info.scope_id not in owner._bindings
                or owner._infos.get(info.scope_id) != info
                or record.binding_payloads[info.scope_id]
                != _binding_payload(owner._bindings[info.scope_id])
                for info in record.scope_bindings
            )
        ):
            raise ChildReleaseUnavailableError("job_release_candidate_content_mismatch")
        if binding.tenant_id is None or binding.cell_id is None:
            raise ChildReleaseUnavailableError("job_release_scope_missing")
        claim = ChildJobReleaseClaim(
            release_id=owner._release_id,
            root_run_id=binding.root_run_id,
            control_job_id=binding.control_job_id,
            parent_attempt_id=binding.parent_attempt_id,
            parent_basis_ref=binding.parent_basis_ref,
            release_ref=self.__record_ref,
            projection_ref=record.projection_ref,
            released_refs=record.released_refs,
            parent_effects_sha256=record.parent_effects_sha256,
            tenant_id=binding.tenant_id,
            cell_id=binding.cell_id,
            admission_generation=binding.admission_generation,
            deadline=binding.deadline,
            served_store_identity=owner._ledger.store_identity,
        )
        with owner._lock:
            if (
                owner._job_candidate is not self
                or owner._state != "preparing"
                or _model_snapshot(owner._root._runtime_invocation_tail_ref) != tail
                or _model_snapshot(owner._binding) != binding_snapshot
                or _release_owner_snapshot(owner) != owner_snapshot
                or _model_snapshot(self.__record_ref) != self.__record_snapshot
            ):
                raise ChildReleaseUnavailableError("job_release_candidate_changed")
            self.__tail_snapshot = tail
            self.__binding_snapshot = binding_snapshot
            self.__owner_snapshot = owner_snapshot
            self.__claim_snapshot = _model_snapshot(claim)
            return claim.model_copy(deep=True)

    def authorized_claim(self) -> ChildJobReleaseClaim:
        """Return only the last owner-recomputed claim for event reconciliation."""
        owner = self.__owner
        with owner._lock:
            if owner._job_candidate is not self or self.__claim_snapshot is None:
                raise ChildReleaseUnavailableError("job_release_candidate_not_recomputed")
            return ChildJobReleaseClaim.model_validate_json(self.__claim_snapshot)

    def _issue_guarded_operation(self, control: object) -> _ChildControlOperation:
        from .worker_lifecycle import ChildRuntimeCapability

        owner = self.__owner
        capability = ChildRuntimeCapability.for_parent(
            owner._root, session=owner, runtime_control=control
        )
        operation = capability._issue_release_operation(self)
        if type(operation) is not _ChildControlOperation:
            raise ChildReleaseUnavailableError("control_operation_not_owner_issued")
        return operation

    def admission(self, claim: ChildJobReleaseClaim) -> bytes:
        """Freeze the local release decision before the actual job-owner transaction."""
        return self._admission(claim, control_operation=None)

    def _admission(
        self, claim: ChildJobReleaseClaim, *, control_operation: _ChildControlOperation | None
    ) -> bytes:
        owner = self.__owner
        with _try_root_custody_locks(owner):
            if owner._root._active_lease is None:
                raise ChildReleaseUnavailableError("root_active_lease_missing")
            owner._root._require_active_lease_owner()
            owner._require_guarded_owner_identity(control_operation=control_operation)
            binding = owner._binding
            if (
                owner._job_candidate is not self
                or owner._state != "preparing"
                or self.__claim_snapshot is None
                or type(claim) is not ChildJobReleaseClaim
                or _model_snapshot(claim) != self.__claim_snapshot
                or binding is None
                or _model_snapshot(binding) != self.__binding_snapshot
                or self.__binding_snapshot != owner._admitted_binding_snapshot
                or self.__owner_snapshot is None
                or _release_owner_snapshot(owner) != self.__owner_snapshot
                or _model_snapshot(self.__record_ref) != self.__record_snapshot
                or _model_snapshot(owner._root._runtime_invocation_tail_ref) != self.__tail_snapshot
                or owner._root._closed
                or owner._root._suspended
                or owner._root.run_manifest.status != "running"
                or (
                    owner._root.run_manifest.run_id,
                    owner._root.run_manifest.control_job_id,
                    owner._root.run_manifest.tenant_id,
                    owner._root.run_manifest.cell_id,
                )
                != (binding.root_run_id, binding.control_job_id, binding.tenant_id, binding.cell_id)
                or binding.deadline <= datetime.now(UTC)
            ):
                raise ChildReleaseUnavailableError("job_release_admission_stale")
            decision = self.__claim_snapshot
        return decision


_CHILD_GUARDED_ROOT_BOOTSTRAP_TOKEN = object()


class ChildGuardedRootBinding:
    """One-use factory-attested Root/proxy/backend relation for trusted bootstrap."""

    def __init__(self, root_run: RunContext, backend: FileSystemCAS, *, token: object) -> None:
        if token is not _CHILD_GUARDED_ROOT_BOOTSTRAP_TOKEN:
            raise ChildReleaseUnavailableError("guarded_root_bootstrap_required")
        if type(root_run) is not RunContext or type(backend) is not FileSystemCAS:
            raise ChildReleaseUnavailableError("guarded_root_binding_type_invalid")
        self.__root = root_run
        self.__proxy = root_run.store
        self.__backend = backend
        self.__thread = threading.get_ident()
        self.__consumed = False

    def _consume(self, root_run: RunContext) -> FileSystemCAS:
        if (
            self.__consumed
            or root_run is not self.__root
            or root_run.store is not self.__proxy
            or threading.get_ident() != self.__thread
        ):
            raise ChildReleaseUnavailableError("guarded_root_binding_changed")
        self.__consumed = True
        return self.__backend


def _bind_guarded_root(
    root_run: RunContext, backend: FileSystemCAS, *, token: object
) -> ChildGuardedRootBinding:
    """Mint only after trusted Runtime factory attests the actual proxy/backend."""
    return ChildGuardedRootBinding(root_run, backend, token=token)


class ChildComputationCustody:
    """One configured parent-session owner of private runs and final publication."""

    def __init__(
        self,
        root_run: RunContext,
        *,
        staging_root: Path,
        closure_resolver: ChildOutputClosureResolver,
        publication_fence: ChildPublicationFence | None = None,
        served_roots: Sequence[Path] = (),
        _guarded_root_binding: ChildGuardedRootBinding | None = None,
    ) -> None:
        if type(root_run) is not RunContext:
            raise ChildReleaseUnavailableError("actual_filesystem_root_owner_required")
        if root_run.run_manifest.control_job_id is None:
            raise ChildReleaseUnavailableError("jobless_child_computation_unsupported")
        if type(root_run.store) is FileSystemCAS:
            if _guarded_root_binding is not None:
                raise ChildReleaseUnavailableError("unexpected_guarded_root_binding")
            served = root_run.store
            guarded_root = False
        else:
            if type(_guarded_root_binding) is not ChildGuardedRootBinding:
                raise ChildReleaseUnavailableError("actual_filesystem_root_owner_required")
            served = _guarded_root_binding._consume(root_run)
            guarded_root = True
        root_run._require_active_lease_owner()
        root_run._validate_run_owner_binding()
        self._root = root_run
        self._served = served
        self._guarded_root_required = guarded_root
        self._guarded_root_proxy = root_run.store if guarded_root else None
        self._resolver = closure_resolver
        self._fence = publication_fence
        self._lock = threading.RLock()
        self._release_id = uuid4().hex
        self._state = "open"
        self._binding: ChildComputationBinding | None = None
        self._admitted_binding_snapshot: bytes | None = None
        self._scopes: dict[str, ChildStagingScope] = {}
        self._prepared_scopes: dict[str, ChildPreparedScope] = {}
        self._scope_preparations: set[str] = set()
        self._handoffs: dict[str, PrivateChildHandoff] = {}
        self._handoff_grants: dict[str, tuple[bytes, ...]] = {}
        self._read_capabilities: dict[int, ChildOneRefReadCapability] = {}
        self._write_capabilities: dict[int, ChildStageWriteCapability] = {}
        self._transfer_capability: ChildSelectedTransferCapability | None = None
        self._guarded_reader_service: _ChildGuardedReadService | None = None
        self._guarded_reader_identity: _ChildGuardedReadService | None = None
        self._infos: dict[str, ArtifactChildReleaseInfo] = {}
        self._bindings: dict[str, ChildComputationBinding] = {}
        self._writes: dict[tuple[str, str, str, str], tuple[ArtifactRef, str]] = {}
        self._inputs: dict[tuple[str, str, str, str], ArtifactRef] = {}
        self._prior_inputs: set[tuple[str, str, str, str]] = set()
        self._revoked: set[str] = set()
        self._parent: _ManagedStore | None = None
        self._parent_scope: str | None = None
        self._updates: list[dict[str, object]] = []
        self._events: list[dict[str, object]] = []
        self._receipt: ChildReleaseReceipt | None = None
        self._effects_settled = False
        self._job_candidate: ChildJobReleaseCandidate | None = None
        self._job_allowed_scopes: frozenset[str] = frozenset()
        self._job_intent: ChildJobSessionIntent | None = None
        self._job_intent_locator: ChildJobReleaseLocator | None = None
        self._control_operations: dict[int, _ChildControlOperation] = {}
        self._control_issued: dict[tuple[str, int], object] = {}
        if self._fence is not None:
            m = root_run.run_manifest
            if (
                self._fence.root_run_id,
                self._fence.control_job_id,
                self._fence.tenant_id,
                self._fence.cell_id,
            ) != (m.run_id, m.control_job_id, m.tenant_id, m.cell_id):
                raise ChildReleaseUnavailableError("publication_fence_identity_mismatch")
            self._fence.check_active()
        elif root_run.run_manifest.control_job_id is not None:
            raise ChildReleaseUnavailableError("control_job_publication_fence_required")
        candidate = staging_root.absolute()
        candidate.mkdir(parents=True, exist_ok=True)
        resolved = candidate.resolve(strict=True)
        if resolved != candidate or any(
            part.is_symlink() for part in (candidate, *candidate.parents)
        ):
            raise ChildReleaseUnavailableError("private_staging_symlink_forbidden")
        roots = [self._served.root.resolve(strict=True), *(path.resolve() for path in served_roots)]
        if root_run._trace_path is not None:
            roots.append(root_run._trace_path.parent.parent.resolve(strict=True))
        if any(
            resolved == path or path in resolved.parents or resolved in path.parents
            for path in roots
        ):
            raise ChildReleaseUnavailableError("private_staging_overlaps_served_or_scanned_root")
        self._staging_root = resolved / self._release_id
        self._staging_root.mkdir()
        self._stage = FileSystemCAS(
            self._staging_root / "cas",
            tenant_id=root_run.tenant_id,
            cell_id=root_run.cell_id,
            ownership_enforced=False,
        )
        self._ledger = _ChildReleaseLedger(
            self._served.root, self._release_id, root_run.run_manifest.run_id
        )

    def _check_root(self, binding: ChildComputationBinding) -> None:
        self._require_guarded_owner_identity()
        self._root._require_active_lease_owner()
        self._root._validate_run_owner_binding()
        m = self._root.run_manifest
        if self._root._closed or self._root._suspended or m.status != "running":
            raise ChildReleaseUnavailableError("root_not_active")
        if (binding.root_run_id, binding.control_job_id, binding.tenant_id, binding.cell_id) != (
            m.run_id,
            m.control_job_id,
            m.tenant_id,
            m.cell_id,
        ):
            raise ChildReleaseUnavailableError("binding_root_identity_mismatch")
        if binding.deadline <= datetime.now(UTC):
            raise ChildReleaseUnavailableError("inherited_deadline_expired")
        attempts = [
            item
            for item in self._root.read_runtime_invocation_attempts()
            if item.basis_ref == binding.parent_basis_ref
        ]
        if (
            len(attempts) != 1
            or attempts[0].outcome is not None
            or attempts[0].basis.attempt_id != binding.parent_attempt_id
        ):
            raise ChildReleaseUnavailableError("parent_attempt_not_current")
        if self._fence is not None:
            self._fence.check_active()

    @contextmanager
    def _local_consumption(self) -> Iterator[None]:
        """Hold the actual parent admission only for a short Core transition."""
        if self._fence is None:
            yield
        else:
            with self._fence.local_consumption():
                yield

    def _root_preflight(self, binding: ChildComputationBinding) -> tuple[bytes, bytes]:
        """Resolve actual currentness before taking the local custody lock."""
        tail = _model_snapshot(self._root._runtime_invocation_tail_ref)
        binding_snapshot = _model_snapshot(binding)
        if binding is self._binding and binding_snapshot != self._admitted_binding_snapshot:
            raise ChildReleaseUnavailableError("owner_admitted_binding_changed")
        self._check_root(binding)
        if (
            _model_snapshot(self._root._runtime_invocation_tail_ref) != tail
            or _model_snapshot(binding) != binding_snapshot
        ):
            raise ChildReleaseUnavailableError("parent_attempt_changed_during_preflight")
        return tail, binding_snapshot

    def _require_root_snapshot(
        self,
        binding: ChildComputationBinding,
        snapshot: tuple[bytes, bytes],
        *,
        control_operation: _ChildControlOperation | None = None,
    ) -> None:
        """Recheck in-memory owner state under the local lock, without DB or CAS I/O."""
        self._require_guarded_owner_identity(control_operation=control_operation)
        m = self._root.run_manifest
        if (
            self._root._closed
            or self._root._suspended
            or m.status != "running"
            or _model_snapshot(self._root._runtime_invocation_tail_ref) != snapshot[0]
            or _model_snapshot(binding) != snapshot[1]
            or binding.deadline <= datetime.now(UTC)
            or (binding.root_run_id, binding.control_job_id, binding.tenant_id, binding.cell_id)
            != (m.run_id, m.control_job_id, m.tenant_id, m.cell_id)
        ):
            raise ChildReleaseUnavailableError("parent_attempt_snapshot_stale")
        if self._root._active_lease is None:
            raise ChildReleaseUnavailableError("root_active_lease_missing")
        self._root._require_active_lease_owner()

    def _admit_binding(self, binding: ChildComputationBinding) -> None:
        if self._guarded_root_required and self._guarded_reader_service is None:
            raise ChildReleaseUnavailableError("guarded_reader_not_appointed")
        if type(binding) is not ChildComputationBinding:
            raise ChildReleaseUnavailableError("binding_type_invalid")
        if binding.control_job_id is None:
            raise ChildReleaseUnavailableError("jobless_child_computation_unsupported")
        incoming_snapshot = _model_snapshot(binding)
        self._check_root(binding)
        with self._lock:
            if self._state != "open":
                raise ChildReleaseUnavailableError("session_not_open")
            if _model_snapshot(binding) != incoming_snapshot:
                raise ChildReleaseUnavailableError("binding_changed_during_admission")
            if self._binding is not None:
                if _model_snapshot(self._binding) != self._admitted_binding_snapshot:
                    raise ChildReleaseUnavailableError("owner_admitted_binding_changed")
                excluded = {"child_invocation_id"}
                if binding.model_dump(exclude=excluded) != self._binding.model_dump(
                    exclude=excluded
                ):
                    raise ChildReleaseUnavailableError("different_parent_admission_session")
            else:
                self._binding = binding.model_copy(deep=True)
                self._admitted_binding_snapshot = _model_snapshot(self._binding)

    def _recovery_locator(self) -> ChildRecoveryLocator | None:
        """Return the immutable originally admitted parent basis when available."""
        if self._admitted_binding_snapshot is None:
            return None
        binding = ChildComputationBinding.model_validate_json(self._admitted_binding_snapshot)
        return ChildRecoveryLocator(
            release_id=self._release_id,
            root_run_id=binding.root_run_id,
            parent_attempt_id=binding.parent_attempt_id,
            parent_basis_json=_model_snapshot(binding.parent_basis_ref),
            job_intent_locator=self._job_intent_locator,
        )

    def _appoint_guarded_reader(self, service: _ChildGuardedReadService, *, token: object) -> None:
        """Install exactly one trusted factory-built Runtime reader before any scope."""
        if token is not _CHILD_GUARDED_READER_BOOTSTRAP_TOKEN:
            raise ChildReleaseUnavailableError("guarded_reader_bootstrap_required")
        with self._lock:
            if (
                self._guarded_reader_service is not None
                or self._parent_scope is not None
                or self._scopes
                or self._infos
            ):
                raise ChildReleaseUnavailableError("guarded_reader_appointment_closed")
            self._guarded_reader_service = service
            self._guarded_reader_identity = service

    def _require_guarded_owner_identity(
        self, *, control_operation: _ChildControlOperation | None = None
    ) -> None:
        if self._guarded_reader_service is not self._guarded_reader_identity:
            raise ChildReleaseUnavailableError("guarded_reader_owner_changed")
        if self._guarded_root_required and (
            self._guarded_reader_service is None or self._root.store is not self._guarded_root_proxy
        ):
            raise ChildReleaseUnavailableError("guarded_root_owner_changed")
        if self._guarded_reader_service is not None:
            if control_operation is None:
                self._guarded_reader_service.require_registration()
            else:
                control_operation._require_worker(self)
                self._guarded_reader_service.require_control_registration(self._fence)

    def _issue_control_operation(
        self,
        handle: ChildJobSessionIntent | ChildJobReleaseCandidate | ChildPreparedScope,
        control: _ChildControlOwner,
        *,
        kind: Literal["session", "authorization", "scope"],
    ) -> _ChildControlOperation:
        """Record one owner-checked guarded decision before dispatch."""
        from polisyos.common.borrowed_execution import _BorrowedControlLiveness

        from .worker_lifecycle import _require_fixed_runtime_child_control

        _require_fixed_runtime_child_control(control)
        expected_type = {
            "session": ChildJobSessionIntent,
            "authorization": ChildJobReleaseCandidate,
            "scope": ChildPreparedScope,
        }[kind]
        control_identity: object = control
        if self._fence is not control_identity or type(handle) is not expected_type:
            raise ChildReleaseUnavailableError("control_operation_owner_mismatch")
        claim = handle.recompute()
        if (
            (kind == "session" and self._job_intent is not handle)
            or (kind == "authorization" and self._job_candidate is not handle)
            or (
                kind == "scope"
                and (
                    type(claim) is not ChildJobScopeClaim
                    or self._prepared_scopes.get(claim.scope_id) is not handle
                )
            )
        ):
            raise ChildReleaseUnavailableError("control_operation_owner_mismatch")
        liveness = control._control_liveness_for_core(self)
        if type(liveness) is not _BorrowedControlLiveness:
            raise ChildReleaseUnavailableError("control_operation_liveness_not_established")
        with self._lock:
            key = (kind, id(handle))
            if (
                key in self._control_issued
                or self._state != ("preparing" if kind == "authorization" else "open")
                or len(self._control_issued) >= _JOB_COLLECTION_MAX_ITEMS
            ):
                raise ChildReleaseUnavailableError("control_operation_already_issued")
            operation = _ChildControlOperation(
                self, handle, claim, kind, control, liveness, token=_CHILD_CONTROL_OPERATION_TOKEN
            )
            self._control_issued[key] = handle
            self._control_operations[id(operation)] = operation
        return operation

    def job_session_intent(self, binding: ChildComputationBinding) -> ChildJobSessionIntent:
        """Create the owner-held parent locator before any child computation."""
        self._admit_binding(binding)
        if binding.control_job_id is None:
            raise ChildReleaseUnavailableError("job_session_requires_job_binding")
        with self._lock:
            if self._job_intent is not None:
                raise ChildReleaseUnavailableError("job_session_intent_already_created")
            self._job_intent = ChildJobSessionIntent(self, binding)
            return self._job_intent

    def bind_job_intent(
        self, intent: ChildJobSessionIntent, locator: ChildJobReleaseLocator
    ) -> None:
        """Bind only a freshly resolved committed owner intent to this session."""
        claim = intent.recompute()
        if locator.job_id != claim.control_job_id:
            raise ChildReleaseUnavailableError("job_session_locator_mismatch")
        result = _child_job_owner(self._ledger.store_identity).verify_intent(locator, claim)
        if result is not None:
            raise ChildReleaseUnavailableError("job_owner_verifier_protocol_invalid")
        with self._lock:
            if self._job_intent is not intent or self._state != "open":
                raise ChildReleaseUnavailableError("job_session_intent_not_current")
            self._job_intent_locator = locator

    def _validate_input(self, ref: ArtifactRef) -> ArtifactRef:
        _key(ref)
        if _key(ref) in self._writes:
            if self._parent is None:
                raise ChildReleaseUnavailableError("private_input_without_parent_basis")
            manifest = self._parent.get_manifest(ref)
            source = self._parent
        else:
            manifest = self._served.get_manifest(ref)
            source = self._served
        # The member owner streams and hashes the complete blob on context exit.
        with source.open_member(ref, "blob"):
            pass
        if _selected(manifest) != ref:
            raise ChildReleaseUnavailableError("input_selected_profile_mismatch")
        if source is self._served:
            with self._lock:
                self._prior_inputs.add(_key(ref))
        return ref.model_copy(deep=True)

    def _system_inputs(self) -> tuple[ArtifactRef, ...]:
        m = self._root.run_manifest
        values = (
            m.registry_bundle,
            m.capability_manifest_ref,
            m.environment_manifest_ref,
            m.sbom_ref,
            m.tee_attestation_ref,
            self._root._owner_snapshot_ref,
            self._binding.parent_basis_ref if self._binding is not None else None,
        )
        return tuple(_selected(self._served.get_manifest(ref)) for ref in values if ref is not None)

    def _refuse_job_owner_budget(self) -> None:
        """Close the private session after a bounded-profile refusal."""
        with self._lock:
            if self._state != "released":
                self._state = "revoked"
        raise ChildReleaseUnavailableError("job_owner_snapshot_limit")

    def _check_job_owner_raw(self, value: object) -> None:
        try:
            _preflight_raw_shape([value])
        except ChildReleaseUnavailableError:
            self._refuse_job_owner_budget()

    def _check_job_owner_value(self, value: object) -> None:
        try:
            _bounded_snapshot(value)
        except ChildReleaseUnavailableError:
            self._refuse_job_owner_budget()

    def _enforce_job_owner_budget(self) -> None:
        """Refuse oversized job sessions before accepting more owner state."""
        if self._binding is not None and self._binding.control_job_id is not None:
            try:
                _release_owner_snapshot(self)
            except ChildReleaseUnavailableError:
                self._state = "revoked"
                raise

    def _new_guarded_store(
        self, binding: ChildComputationBinding, inputs: Sequence[ArtifactRef], *, child_run_id: str
    ) -> tuple[str, _ManagedStore]:
        """Admit exact candidates through the appointed full-operation CAS guard."""
        m = self._root.run_manifest
        system = (
            m.registry_bundle,
            m.capability_manifest_ref,
            m.environment_manifest_ref,
            m.sbom_ref,
            m.tee_attestation_ref,
            self._root._owner_snapshot_ref,
            binding.parent_basis_ref,
        )
        raw_candidates = (*inputs, *(ref for ref in system if ref is not None))
        if len(raw_candidates) > _JOB_COLLECTION_MAX_ITEMS:
            self._refuse_job_owner_budget()
        self._check_job_owner_raw(raw_candidates)
        candidates = tuple(ref.model_copy(deep=True) for ref in raw_candidates)
        for ref in candidates:
            _key(ref)  # A profileless candidate is not an exact input grant.
            if _key(ref) in self._writes:
                if self._parent is None:
                    raise ChildReleaseUnavailableError("private_input_without_parent_basis")
                self._parent._resolve(ref)
        scope_id = uuid4().hex
        info = ArtifactChildReleaseInfo(
            release_id=self._release_id,
            scope_id=scope_id,
            binding_sha256=child_binding_digest(_binding_payload(binding)),
            served_store_identity=self._ledger.store_identity,
            root_run_id=binding.root_run_id,
            child_run_id=child_run_id,
        )
        self._stage._configure_child_staging(info, token=_CHILD_STAGING_TOKEN)
        with self._lock:
            if self._state != "open":
                raise ChildReleaseUnavailableError("session_closed_during_scope_preparation")
            self._inputs.update((_key(ref), ref.model_copy(deep=True)) for ref in candidates)
            self._infos[scope_id] = info
            self._bindings[scope_id] = binding.model_copy(deep=True)
            self._enforce_job_owner_budget()
        store = _ManagedStore(self, scope_id, binding, info, candidates)
        try:
            for ref in candidates:
                read = store._guarded_manifest_read(
                    ref,
                    max_manifest_bytes=8 * 1024 * 1024,
                    manifest_profile_sha256=None,
                    allow_profile_absent=True,
                )
                store._guarded_verify_blob(ref, byte_size=read.manifest.byte_size)
                source, selected = store._resolve(ref)
                if source is self._served:
                    with self._lock:
                        self._prior_inputs.add(_key(selected))
                        self._enforce_job_owner_budget()
        except BaseException:
            with self._lock:
                self._state = "revoked"
            raise
        return scope_id, store

    def _new_store(
        self, binding: ChildComputationBinding, inputs: Sequence[ArtifactRef], *, child_run_id: str
    ) -> tuple[str, _ManagedStore]:
        self._admit_binding(binding)
        if binding.control_job_id is not None:
            if len(inputs) > _JOB_COLLECTION_MAX_ITEMS:
                self._refuse_job_owner_budget()
            self._check_job_owner_raw(list(inputs))
            self._check_job_owner_value([ref.model_dump(mode="json") for ref in inputs])
        if binding.control_job_id is not None and self._job_intent_locator is None:
            raise ChildReleaseUnavailableError("job_session_intent_not_bound")
        if self._guarded_reader_service is not None:
            return self._new_guarded_store(binding, inputs, child_run_id=child_run_id)
        # Validation and actual existing CAS reads/capacity are outside the owner lock.
        requested = tuple(self._validate_input(ref) for ref in inputs)
        basis = (*requested, *(self._validate_input(ref) for ref in self._system_inputs()))
        scope_id = uuid4().hex
        info = ArtifactChildReleaseInfo(
            release_id=self._release_id,
            scope_id=scope_id,
            binding_sha256=child_binding_digest(_binding_payload(binding)),
            served_store_identity=self._ledger.store_identity,
            root_run_id=binding.root_run_id,
            child_run_id=child_run_id,
        )
        self._stage._configure_child_staging(info, token=_CHILD_STAGING_TOKEN)
        with self._lock:
            if self._state != "open":
                raise ChildReleaseUnavailableError("session_closed_during_scope_preparation")
            self._inputs.update((_key(ref), ref) for ref in basis)
            self._infos[scope_id] = info
            self._bindings[scope_id] = binding.model_copy(deep=True)
            self._enforce_job_owner_budget()
        return scope_id, _ManagedStore(self, scope_id, binding, info, basis)

    def parent_store(
        self, binding: ChildComputationBinding, *, input_refs: Sequence[ArtifactRef]
    ) -> _ManagedStore:
        """Return this session's one private parent writer and selected handoff view."""
        with self._lock:
            if self._state != "open" or self._parent_scope is not None:
                raise ChildReleaseUnavailableError("parent_writer_already_configured_or_closed")
            self._parent_scope = "preparing-parent"
        try:
            scope_id, store = self._new_store(binding, input_refs, child_run_id=binding.root_run_id)
            with self._lock:
                if self._state != "open":
                    raise ChildReleaseUnavailableError("session_closed_during_parent_preparation")
                self._parent_scope, self._parent = scope_id, store
                for grant in self._handoff_grants.values():
                    store._enroll(tuple(ArtifactRef.model_validate_json(raw) for raw in grant))
                return store
        except BaseException as exc:
            self._revoke_preserving_outcome(exc, reason="parent_store_preparation_failed")
            raise

    def prepare_scope(
        self, binding: ChildComputationBinding, *, input_refs: Sequence[ArtifactRef]
    ) -> ChildPreparedScope:
        """Prepare a private child outside job/resource admission and return its handle."""
        child_id = str(uuid4())
        with self._lock:
            if self._state != "open":
                raise ChildReleaseUnavailableError("session_closed_during_scope_preparation")
            self._scope_preparations.add(child_id)
        run: RunContext | None = None
        scope_id: str | None = None
        try:
            scope_id, store = self._new_store(binding, input_refs, child_run_id=child_id)
            # Refuse a known stale parent before creating a durable child run;
            # the second preflight below still rechecks after preparation.
            self._root_preflight(binding)
            run = RunContext.start_child(
                self._root,
                store=store,
                parent_basis_ref=binding.parent_basis_ref,
                run_id=child_id,
                run_dir=self._staging_root / "runs" / child_id,
            )
            scope = ChildStagingScope(scope_id, binding.model_copy(deep=True), run, store)
            with self._lock:
                self._scopes[scope_id] = scope
            binding_ref = store.put_json(
                _binding_payload(binding),
                ArtifactWriteOptions(
                    kind="core.child_computation_binding",
                    media_type="application/json",
                    schema=SchemaInfo(name="polisyos.core.ChildComputationBinding", version="1.0"),
                    inputs=[
                        InputRef(
                            artifact_id=binding.parent_basis_ref.artifact_id,
                            role="parent_attempt",
                            manifest_profile_sha256=binding.parent_basis_ref.manifest_profile_sha256,
                        )
                    ],
                ),
            )
            run.add_input(binding_ref)
            snapshot = self._root_preflight(scope.binding)
            with self._lock:
                if self._state != "open" or self._scopes.get(scope_id) is not scope:
                    raise ChildReleaseUnavailableError("scope_closed_during_preparation")
                prepared = ChildPreparedScope(self, scope, snapshot)
                self._prepared_scopes[scope_id] = prepared
                self._scope_preparations.remove(child_id)
            return prepared
        except BaseException as exc:
            with self._lock:
                self._scope_preparations.discard(child_id)
                if self._state != "released":
                    self._state = "revoked"
            # No producer has received this scope. Existing finalize releases its
            # active lease in finally; a failed terminal write remains uncertain.
            cleanup_error: BaseException | None = None
            if run is not None:
                try:
                    run.finalize(status="fail", errors=[{"reason": "child_preparation_failed"}])
                except BaseException as failed_cleanup:
                    cleanup_error = failed_cleanup
                    exc.add_note(
                        "Private run finalization failed: " + type(failed_cleanup).__name__
                    )
            if isinstance(exc, ChildRunStartUnknown):
                unknown = ChildScopePreparationUnknown(
                    self._recovery_locator(),
                    child_run_id=exc.run_id,
                    run_dir=str(exc.run_dir),
                    scope_id=scope_id,
                )
                self._revoke_preserving_outcome(unknown, reason="child_preparation_failed")
                raise unknown from exc
            self._revoke_preserving_outcome(exc, reason="child_preparation_failed")
            if cleanup_error is not None and not isinstance(exc, ChildComputationOutcomeUnknown):
                raise ChildRevocationUnknown(self._recovery_locator()) from exc
            raise

    def open_scope(
        self, binding: ChildComputationBinding, *, input_refs: Sequence[ArtifactRef]
    ) -> ChildStagingScope:
        """Refuse the legacy unfenced scope route; use trusted engine admission."""
        raise ChildReleaseUnavailableError("direct_child_scope_admission_unsupported")

    def _require_store_active(self, scope_id: str, *, writing: bool) -> None:
        if scope_id not in self._bindings or scope_id in self._revoked:
            raise ChildReleaseUnavailableError("scope_not_active")
        if writing and self._state != "open":
            raise ChildReleaseUnavailableError("session_writes_closed")
        if not writing and self._state not in {"open", "preparing", "released"}:
            raise ChildReleaseUnavailableError("session_reads_closed")
        self._check_root(self._bindings[scope_id])

    def _capture_write(self, scope_id: str, ref: ArtifactRef) -> None:
        self._require_store_active(scope_id, writing=True)
        manifest = self._stage.get_manifest(ref)
        if manifest.child_release != self._infos[scope_id] or _selected(manifest) != ref:
            raise ChildReleaseUnavailableError("managed_write_owner_mismatch")
        with self._lock:
            if self._state != "open" or scope_id in self._revoked:
                raise ChildReleaseUnavailableError("scope_closed_during_write")
            self._writes[_key(ref)] = (ref.model_copy(deep=True), scope_id)
            self._enforce_job_owner_budget()

    def _source_for(self, ref: ArtifactRef) -> FileSystemCAS:
        if _key(ref) in self._prior_inputs:
            return self._served
        if _key(ref) in self._writes:
            return self._stage
        if _key(ref) in self._inputs:
            return self._served
        raise ChildReleaseUnavailableError("reference_outside_session")

    def check_active(self, scope: ChildStagingScope) -> None:
        """Reconcile the opaque scope with actual current parent run/job admission."""
        if self._scopes.get(scope.scope_id) is not scope:
            raise ChildReleaseUnavailableError("scope_handle_not_owned")
        self._require_store_active(scope.scope_id, writing=False)

    def _revoke_preserving_outcome(self, original: BaseException, *, reason: str) -> None:
        try:
            self.revoke_parent(reason=reason)
        except BaseException as revocation_error:
            if isinstance(original, ChildComputationOutcomeUnknown):
                original.add_note(
                    "Durable revocation also requires reconciliation: "
                    + type(revocation_error).__name__
                )
                return
            unknown = ChildRevocationUnknown(self._recovery_locator())
            unknown.add_note("Revocation error: " + type(revocation_error).__name__)
            raise unknown from original

    def revoke(self, scope: ChildStagingScope, *, reason: str) -> None:
        """Revoke future managed access without asserting arbitrary-effect rollback."""
        with self._lock:
            if self._scopes.get(scope.scope_id) is not scope:
                raise ChildReleaseUnavailableError("scope_handle_not_owned")
            if not reason:
                raise ValueError("revocation_reason_required")
            self._revoked.add(scope.scope_id)
            if self._state != "released":
                self._state = "revoked"
                try:
                    self._ledger.revoke(reason)
                except BaseException as exc:
                    raise ChildRevocationUnknown(self._recovery_locator()) from exc

    def revoke_parent(self, *, reason: str) -> None:
        """Close all managed session writes, even if no child has been opened."""
        if not reason:
            raise ValueError("revocation_reason_required")
        with self._lock:
            self._revoked.update(self._bindings)
            if self._state != "released":
                self._state = "revoked"
                try:
                    self._ledger.revoke(reason)
                except BaseException as exc:
                    raise ChildRevocationUnknown(self._recovery_locator()) from exc

    def _closure(
        self, store: ArtifactReader, projection_ref: ArtifactRef
    ) -> tuple[ArtifactRef, ...]:
        result = self._resolver.resolve(store, projection_ref)
        if type(result) is not tuple:
            raise ChildReleaseUnavailableError("resolver_must_return_selected_tuple")
        if (
            self._binding is not None
            and self._binding.control_job_id is not None
            and len(result) > _JOB_COLLECTION_MAX_ITEMS
        ):
            self._refuse_job_owner_budget()
        closure: dict[tuple[str, str, str, str], ArtifactRef] = {}
        for ref in (projection_ref, *result):
            key = _key(ref)
            manifest = store.get_manifest(ref)
            if _selected(manifest) != ref:
                raise ChildReleaseUnavailableError("closure_profile_mismatch")
            if self._guarded_reader_service is not None:
                if type(store) is not _ManagedStore:
                    raise ChildReleaseUnavailableError("guarded_scope_owner_required")
                store._guarded_verify_blob(ref, byte_size=manifest.byte_size)
            else:
                with store.open_member(ref, "blob"):
                    pass
            closure[key] = ref.model_copy(deep=True)
        return tuple(closure.values())

    def admit_handoff(
        self, scope: ChildStagingScope, projection_ref: ArtifactRef
    ) -> PrivateChildHandoff:
        """Privately admit only the typed selected handoff; never publish a child."""
        self.check_active(scope)
        if (
            not scope.run._closed
            or scope.run._suspended
            or scope.run.run_manifest.finished_at is None
        ):
            raise ChildReleaseUnavailableError("child_execution_not_quiescent")
        if _key(projection_ref) not in {_key(ref) for ref in scope.store._written()}:
            raise ChildReleaseUnavailableError("handoff_projection_not_scope_owned")
        closure = self._closure(scope.store, projection_ref)
        binding = self._bindings[scope.scope_id]
        tail = self._root_preflight(binding)
        with self._lock:
            self._require_root_snapshot(binding, tail)
            if self._scopes.get(scope.scope_id) is not scope or scope.scope_id in self._revoked:
                raise ChildReleaseUnavailableError("scope_not_active")
            if scope.scope_id in self._handoffs:
                raise ChildReleaseUnavailableError("scope_handoff_already_selected")
            view = _ManagedStore(
                self,
                scope.scope_id,
                self._bindings[scope.scope_id],
                self._infos[scope.scope_id],
                closure,
                writable=False,
            )
            handoff = PrivateChildHandoff(
                scope.scope_id, scope.binding, projection_ref, closure, view
            )
            self._handoffs[scope.scope_id] = handoff
            self._handoff_grants[scope.scope_id] = tuple(_model_snapshot(ref) for ref in closure)
            self._enforce_job_owner_budget()
            if self._parent is not None:
                self._parent._enroll(closure)
            return handoff

    def stage_parent_run_update(self, changes: Mapping[str, object]) -> None:
        """Stage existing allowlisted provenance effects for final parent settlement."""
        allowed = {
            "execution_profile",
            "control_job_id",
            "capability_manifest_ref",
            "environment_manifest_ref",
            "sbom_ref",
            "tee_attestation_ref",
        }
        binding = self._binding
        if binding is None:
            raise ChildReleaseUnavailableError("parent_update_fields_or_state_invalid")
        tail = self._root_preflight(binding)
        with self._lock:
            self._require_root_snapshot(binding, tail)
            if (
                self._binding is not binding
                or self._state != "open"
                or not changes
                or set(changes) - allowed
            ):
                raise ChildReleaseUnavailableError("parent_update_fields_or_state_invalid")
            if (
                "control_job_id" in changes
                and changes["control_job_id"] != self._binding.control_job_id
            ):
                raise ChildReleaseUnavailableError("parent_control_job_replacement_forbidden")
            payload = self._root.run_manifest.model_dump(mode="python")
            for previous in self._updates:
                payload.update(previous)
            payload.update(changes)
            validated = RunManifest.model_validate(payload)
            self._updates.append({key: getattr(validated, key) for key in changes})
            self._enforce_job_owner_budget()

    def stage_parent_event(
        self,
        phase: str,
        event: str,
        *,
        inputs: Sequence[ArtifactRef] = (),
        outputs: Sequence[ArtifactRef] = (),
        metrics: Mapping[str, float | int] | None = None,
        warnings: Sequence[WarningRecord] = (),
    ) -> None:
        """Stage a normal parent event without mutating the public Root trace."""
        binding = self._binding
        if binding is None:
            raise ChildReleaseUnavailableError("parent_event_state_or_owner_invalid")
        if binding.control_job_id is not None:
            if any(
                len(items) > _JOB_COLLECTION_MAX_ITEMS
                for items in (inputs, outputs, warnings, metrics or {})
            ):
                self._refuse_job_owner_budget()
            self._check_job_owner_raw([inputs, outputs, warnings, dict(metrics or {})])
            self._check_job_owner_value(dict(metrics or {}))
            self._check_job_owner_value(
                [ref.model_dump(mode="json") for ref in (*inputs, *outputs)]
            )
            self._check_job_owner_value([warning.model_dump(mode="json") for warning in warnings])
        tail = self._root_preflight(binding)
        with self._lock:
            self._require_root_snapshot(binding, tail)
            if (
                self._binding is not binding
                or self._state != "open"
                or phase == "core"
                or event.startswith("RUN_")
            ):
                raise ChildReleaseUnavailableError("parent_event_state_or_owner_invalid")
            # Round-trip a finite JSON representation now; NaN and unknown objects fail.
            json.dumps(dict(metrics or {}), allow_nan=False)
            for ref in (*inputs, *outputs):
                _key(ref)
                self._source_for(ref)
            self._events.append(
                {
                    "phase": phase,
                    "event": event,
                    "inputs": list(inputs),
                    "outputs": list(outputs),
                    "metrics": dict(metrics or {}),
                    "warnings": list(warnings),
                }
            )
            self._enforce_job_owner_budget()

    def _effects_payload(self) -> dict[str, JsonValue]:
        def normalize(value: object) -> JsonValue:
            if type(value) in {ArtifactRef, WarningRecord}:
                return value.model_dump(mode="json")
            if value is None or type(value) in {str, bool, int, float}:
                json.dumps(value, allow_nan=False)
                return value
            if type(value) in {tuple, list}:
                return [normalize(item) for item in value]
            if type(value) is dict and all(type(key) is str for key in value):
                return {key: normalize(item) for key, item in value.items()}
            raise ChildReleaseUnavailableError("parent_effect_not_finite_typed_json")

        return {"updates": normalize(self._updates), "events": normalize(self._events)}

    def _execution_outcome(
        self, handoffs: Sequence[PrivateChildHandoff]
    ) -> Literal["completed", "partial", "failed", "unknown"]:
        statuses = [self._scopes[item.scope_id].run.run_manifest.status for item in handoffs]
        if statuses and all(value == "ok" for value in statuses):
            return "completed"
        if any(value in {"fail", "failed", "error"} for value in statuses):
            return "partial" if any(value == "ok" for value in statuses) else "failed"
        return "unknown"

    def release_parent(
        self, handoffs: Sequence[PrivateChildHandoff], final_projection_ref: ArtifactRef
    ) -> ChildReleaseReceipt:
        """Publish exactly the final typed parent closure through one durable head."""
        if self._binding is not None and self._binding.control_job_id is None:
            raise ChildReleaseUnavailableError("jobless_child_computation_unsupported")
        with self._lock:
            if self._receipt is not None:
                if (
                    self._receipt.projection_ref != final_projection_ref
                    or not self._effects_settled
                ):
                    raise ChildParentSettlementError(self._receipt)
                return replace(self._receipt, release_outcome="released_ack_reconciled")
        binding = self._binding
        if binding is None:
            raise ChildReleaseUnavailableError("parent_release_not_ready")
        tail = self._root_preflight(binding)
        with self._lock:
            self._require_root_snapshot(binding, tail)
            if self._receipt is not None:
                if (
                    self._receipt.projection_ref != final_projection_ref
                    or not self._effects_settled
                ):
                    raise ChildParentSettlementError(self._receipt)
                return replace(self._receipt, release_outcome="released_ack_reconciled")
            if self._binding is None or self._parent is None or self._state != "open":
                raise ChildReleaseUnavailableError("parent_release_not_ready")
            if self._scope_preparations or self._prepared_scopes:
                raise ChildReleaseUnavailableError("child_scope_admission_pending")
            if self._write_capabilities:
                raise ChildReleaseUnavailableError("guarded_stage_write_in_flight")
            if self._binding is not binding:
                raise ChildReleaseUnavailableError("parent_release_not_ready")
            if any(self._handoffs.get(item.scope_id) is not item for item in handoffs):
                raise ChildReleaseUnavailableError("handoff_handle_not_owned")
            selected_scope_ids = {item.scope_id for item in handoffs}
            self._job_allowed_scopes = frozenset(selected_scope_ids)
            if len(selected_scope_ids) != len(handoffs):
                raise ChildReleaseUnavailableError("duplicate_handoff")
            if _key(final_projection_ref) not in {_key(ref) for ref in self._parent._written()}:
                raise ChildReleaseUnavailableError("final_projection_not_parent_owned")
            self._state = "preparing"
        # The candidate binds recovery identity before entering the cross-owner commit.
        candidate_receipt: ChildReleaseReceipt | None = None
        commit_attempted = False
        authorization_attempted = False
        # No job DB or Root transition lock over resolver, validation, capacity or copy.
        try:
            closure = self._closure(self._parent, final_projection_ref)
            selected = tuple(ref for ref in closure if _key(ref) in self._writes)
            for ref in selected:
                scope_id = self._writes[_key(ref)][1]
                if scope_id != self._parent_scope and scope_id not in selected_scope_ids:
                    raise ChildReleaseUnavailableError("final_closure_uses_unadmitted_handoff")
            selected_keys = {_key(ref) for ref in selected}
            for changes in self._updates:
                for value in changes.values():
                    if (
                        isinstance(value, ArtifactRef)
                        and _key(value) not in selected_keys
                        and _key(value) not in self._inputs
                    ):
                        raise ChildReleaseUnavailableError("parent_update_ref_not_released")
            for event in self._events:
                for ref in (*event["inputs"], *event["outputs"]):
                    if _key(ref) not in selected_keys and _key(ref) not in self._inputs:
                        raise ChildReleaseUnavailableError("parent_event_ref_not_released")
            used_scopes = {self._writes[_key(ref)][1] for ref in selected}
            outcome = self._execution_outcome(handoffs)
            record = ChildReleaseRecord(
                release_id=self._release_id,
                root_run_id=self._binding.root_run_id,
                tenant_id=self._binding.tenant_id,
                cell_id=self._binding.cell_id,
                parent_attempt_id=self._binding.parent_attempt_id,
                parent_basis_ref=self._binding.parent_basis_ref,
                projection_ref=final_projection_ref,
                released_refs=selected,
                scope_bindings=tuple(self._infos[key] for key in sorted(used_scopes)),
                binding_payloads={
                    key: _binding_payload(self._bindings[key]) for key in sorted(used_scopes)
                },
                execution_outcome=outcome,
                parent_effects=self._effects_payload(),
                parent_effects_sha256=child_binding_digest(self._effects_payload()),
            )
            if self._parent_scope is None:
                raise ChildReleaseUnavailableError("parent_scope_missing")
            record_options = ArtifactWriteOptions(
                kind=_RELEASE_KIND,
                media_type="application/json",
                schema=SchemaInfo(name=_RELEASE_SCHEMA, version="1.0"),
                tenant_context=(
                    ArtifactTenantContextInfo(
                        tenant_id=self._binding.tenant_id, cell_id=self._binding.cell_id
                    )
                    if self._binding.tenant_id is not None
                    else None
                ),
                child_release=self._infos[self._parent_scope],
            )
            if self._guarded_reader_service is None:
                record_ref = self._stage.put_json(
                    record.model_dump(mode="json"), record_options, return_selected_profile=True
                )
            else:
                record_ref = self._parent._perform_guarded_write(
                    "json",
                    record.model_dump(mode="json"),
                    record_options,
                    None,
                    allow_preparing=True,
                )
            publication = (*selected, record_ref)
            manifest_store = (
                self._parent if self._guarded_reader_service is not None else self._stage
            )
            self._ledger.enroll(
                tuple((ref, manifest_store.get_manifest(ref).child_release) for ref in publication)
            )
            if self._guarded_reader_service is None:
                self._served._publish_child_release_profiles(
                    self._stage, publication, self._ledger, token=_CHILD_STAGING_TOKEN
                )
            else:
                with self._lock:
                    if self._transfer_capability is not None or self._state != "preparing":
                        raise ChildReleaseUnavailableError("guarded_transfer_not_ready")
                    transfer = ChildSelectedTransferCapability(self, publication)
                    self._transfer_capability = transfer
                try:
                    from ..artifacts.store import ImportPublication

                    publication_receipt = self._guarded_reader_service.transfer_selected(transfer)
                    if type(publication_receipt) is not ImportPublication:
                        raise ChildReleaseUnavailableError("guarded_transfer_receipt_invalid")
                    transfer._claim_for_runtime(self)
                except BaseException as exc:
                    raise ChildGuardedTransferUnknown(self._recovery_locator()) from exc
                finally:
                    with self._lock:
                        if self._transfer_capability is transfer:
                            self._transfer_capability = None
            candidate_receipt = ChildReleaseReceipt(
                self._release_id,
                record_ref,
                final_projection_ref,
                selected,
                outcome,
                "release_state_unknown",
                root_run_id=self._binding.root_run_id,
                parent_attempt_id=self._binding.parent_attempt_id,
                parent_basis_json=_model_snapshot(self._binding.parent_basis_ref),
                job_intent_locator=(
                    self._job_intent_locator.model_copy(deep=True)
                    if self._job_intent_locator is not None
                    else None
                ),
            )
            job_authorization: ChildJobReleaseLocator | None = None
            if self._binding.control_job_id is not None:
                if self._fence is None or self._job_intent_locator is None:
                    raise ChildReleaseUnavailableError("job_release_authority_bridge_unavailable")
                with self._lock:
                    self._job_candidate = ChildJobReleaseCandidate(self, record_ref)
                    candidate = self._job_candidate
                authorization_attempted = True
                job_authorization = self._fence.authorize_release(candidate)
                candidate_receipt = replace(
                    candidate_receipt,
                    job_authorization_locator=job_authorization.model_copy(deep=True),
                )
                claim = candidate.authorized_claim()
                result = _child_job_owner(self._ledger.store_identity).verify_release(
                    job_authorization, claim
                )
                if result is not None:
                    raise ChildReleaseUnavailableError("job_owner_verifier_protocol_invalid")
            local_tail = self._root_preflight(self._binding)
            fence = (
                self._fence.publication()
                if self._fence is not None and job_authorization is None
                else nullcontext()
            )
            registration = (
                self._guarded_reader_service.publication_registration()
                if self._guarded_reader_service is not None
                else nullcontext()
            )
            with (
                fence,
                self._root._parent_state_transition_lease(run_scoped=False),
                self._lock,
                self._local_consumption(),
                registration,
            ):
                if job_authorization is None:
                    self._require_root_snapshot(self._binding, local_tail)
                else:
                    # The exact Root/candidate check and owner head commit share
                    # this transition; a parent close cannot win between them.
                    candidate.admission(claim)
                if self._state != "preparing":
                    raise ChildReleaseUnavailableError("session_revoked_during_copy")
                commit_attempted = True
                self._ledger.commit(record_ref, job_authorization=job_authorization)
                receipt = replace(candidate_receipt, release_outcome="released")
                # Set before context exit: a lost DB/fence acknowledgement after
                # the durable CAS commit must retain the committed receipt.
                self._receipt = receipt
                self._state = "released"
            # The job DB fence is no longer held. Each actual Root operation uses
            # its existing lifecycle owner. Cancellation before settlement refuses
            # remaining effects; committed release is historical, never rolled back.
            total = len(self._updates) + len(self._events)
            self._ledger.record_settlement("pending", completed=0, total=total)
            completed = 0
            for changes in self._updates:
                self._check_root(self._binding)
                self._root.update_manifest(**changes)
                completed += 1
                self._ledger.record_settlement("pending", completed=completed, total=total)
            for event in self._events:
                self._check_root(self._binding)
                self._root.emit(**event)
                completed += 1
                self._ledger.record_settlement("pending", completed=completed, total=total)
            self._ledger.record_settlement("settled", completed=completed, total=total)
            self._effects_settled = True
            return receipt
        except BaseException as exc:
            with self._lock:
                if self._receipt is None and commit_attempted and candidate_receipt is not None:
                    try:
                        head = self._ledger.head()
                    except Exception:
                        self._receipt = candidate_receipt
                    else:
                        if (
                            head.status == "released"
                            and head.release_ref == candidate_receipt.release_ref
                        ):
                            self._receipt = replace(
                                candidate_receipt,
                                release_outcome="release_visible_durability_unknown",
                            )
                        elif head.status != "pending":
                            self._receipt = candidate_receipt
                if (
                    self._receipt is None
                    and authorization_attempted
                    and candidate_receipt is not None
                ):
                    # A DB authorization acknowledgement can itself be lost. The
                    # persisted parent-basis intent is the restart recovery locator.
                    self._receipt = candidate_receipt
                if self._receipt is not None:
                    # Best effort only: never replace the original post-commit failure.
                    with suppress(Exception):
                        self._ledger.record_settlement(
                            "unknown", completed=-1, total=len(self._updates) + len(self._events)
                        )
                    if isinstance(exc, ChildParentSettlementError):
                        raise
                    raise ChildParentSettlementError(self._receipt) from exc
                if self._state == "preparing":
                    self._state = "revoked"
                    self._revoke_preserving_outcome(
                        exc, reason="release_preparation_or_currentness_failed"
                    )
            raise

    def release(self, scope: ChildStagingScope, projection_ref: ArtifactRef) -> ChildReleaseReceipt:
        """One-scope convenience using the same parent-session join, never a bypass."""
        handoff = self.admit_handoff(scope, projection_ref)
        if self._parent is None:
            store = self.parent_store(scope.binding, input_refs=())
            store._enroll(handoff.selected_refs)
            # The parent projection is an actual new owner write, not a caller alias.
            manifest = scope.store.get_manifest(projection_ref)
            final = store.put_bytes(
                scope.store.get_bytes(projection_ref),
                ArtifactWriteOptions(
                    kind=manifest.kind,
                    media_type=manifest.media_type,
                    schema=manifest.artifact_schema,
                    inputs=[
                        InputRef(
                            artifact_id=projection_ref.artifact_id,
                            role="child_projection",
                            manifest_profile_sha256=projection_ref.manifest_profile_sha256,
                        )
                    ],
                ),
            )
        else:
            raise ChildReleaseUnavailableError("single_scope_release_requires_unconfigured_parent")
        return self.release_parent((handoff,), final)
