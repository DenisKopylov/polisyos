"""Core-owned selected-profile admission for managed child computation outputs.

A manifest link discovers a release class; it never supplies permission. Readers
resolve the owner-controlled release head and immutable selected record before a
new child occurrence may leave the CAS. This is a managed trusted-code boundary,
not filesystem or arbitrary-Python isolation.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from ..canon import CanonSpec, to_canonical_bytes
from ._atomic_write import AtomicFileWriter, ensure_directory_durable
from ._manifest_lifecycle import ManifestLifecycle
from .manifest import ArtifactChildReleaseInfo, ArtifactManifest, ArtifactRef
from .ownership import ArtifactUnavailableError

if TYPE_CHECKING:
    from pathlib import Path

    from .ids import ArtifactID

_RELEASE_KIND = "core.child_computation_release"
_RELEASE_SCHEMA = "polisyos.core.ChildComputationReleaseRecord"
_RECORD_LIMIT = 8 * 1024 * 1024
_CHILD_STAGING_TOKEN = object()


class ChildReleaseUnavailableError(ArtifactUnavailableError):
    """A selected child occurrence has no verified committed owner release."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__("child_release_unavailable:" + reason)


class ChildReleaseRecord(BaseModel):
    """Immutable actual selected closure and managed binding of a parent release."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"
    release_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    root_run_id: str = Field(min_length=1)
    tenant_id: str | None
    cell_id: str | None
    parent_attempt_id: str = Field(min_length=1)
    parent_basis_ref: ArtifactRef
    projection_ref: ArtifactRef
    released_refs: tuple[ArtifactRef, ...]
    scope_bindings: tuple[ArtifactChildReleaseInfo, ...]
    binding_payloads: dict[str, dict[str, JsonValue]]
    execution_outcome: Literal["completed", "partial", "failed", "unknown"]
    parent_effects: dict[str, JsonValue]
    parent_effects_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    isolation_coverage: Literal["managed_interfaces_trusted_builtin_local"] = (
        "managed_interfaces_trusted_builtin_local"
    )


class _AwareDeadlineClaim(BaseModel):
    deadline: datetime

    @field_validator("deadline")
    @classmethod
    def _require_aware_deadline(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("job_release_deadline_not_aware")
        return value


class ChildJobSessionClaim(_AwareDeadlineClaim):
    """Exact parent-attempt locator that must be persisted before computation."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    release_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    root_run_id: str = Field(min_length=1)
    control_job_id: str = Field(min_length=1)
    parent_attempt_id: str = Field(min_length=1)
    parent_basis_ref: ArtifactRef
    tenant_id: str
    cell_id: str
    admission_generation: int = Field(ge=0, strict=True)
    deadline: datetime
    served_store_identity: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ChildJobReleaseClaim(_AwareDeadlineClaim):
    """Exact Core-owned selected release identity for job-owner admission."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    release_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    root_run_id: str = Field(min_length=1)
    control_job_id: str = Field(min_length=1)
    parent_attempt_id: str = Field(min_length=1)
    parent_basis_ref: ArtifactRef
    release_ref: ArtifactRef
    projection_ref: ArtifactRef
    released_refs: tuple[ArtifactRef, ...]
    parent_effects_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    tenant_id: str
    cell_id: str
    admission_generation: int = Field(ge=0, strict=True)
    deadline: datetime
    served_store_identity: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ChildJobReleaseLocator(BaseModel):
    """Immutable locator for a committed reserved control-job owner event."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    job_id: str = Field(min_length=1)
    event_id: int = Field(gt=0, strict=True)


class ChildJobScopeClaim(BaseModel):
    """Complete owner-snapshotted child scope admission decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    session: ChildJobSessionClaim
    session_intent: ChildJobReleaseLocator
    scope_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    child_run_id: str = Field(min_length=1)
    child_invocation_id: str = Field(min_length=1)
    scope_binding_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    input_grants_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ChildJobOwnerVerifier(Protocol):
    """A bootstrap-appointed actual durable job owner, never a per-read callback."""

    def verify_intent(self, locator: ChildJobReleaseLocator, claim: ChildJobSessionClaim) -> None:
        """Resolve a committed reserved intent and compare its complete claim."""

    def verify_scope(self, locator: ChildJobReleaseLocator, claim: ChildJobScopeClaim) -> None:
        """Resolve the committed scope decision and its exact parent session."""
        ...

    def verify_release(self, locator: ChildJobReleaseLocator, claim: ChildJobReleaseClaim) -> None:
        """Resolve a committed reserved authorization and compare its complete claim."""
        ...


_JOB_OWNER_BOOTSTRAP_TOKEN = object()
_JOB_OWNER_LOCK = threading.RLock()
_JOB_OWNER_BY_STORE: dict[str, ChildJobOwnerVerifier] = {}


def _install_child_job_owner(
    store_identity: str, owner: ChildJobOwnerVerifier, *, token: object
) -> None:
    """Install one trusted owner per store during runtime bootstrap."""
    if token is not _JOB_OWNER_BOOTSTRAP_TOKEN:
        raise ChildReleaseUnavailableError("job_owner_bootstrap_required")
    with _JOB_OWNER_LOCK:
        existing = _JOB_OWNER_BY_STORE.get(store_identity)
        if existing is not None and existing is not owner:
            raise ChildReleaseUnavailableError("job_owner_bootstrap_conflict")
        _JOB_OWNER_BY_STORE[store_identity] = owner


def _child_job_owner(store_identity: str) -> ChildJobOwnerVerifier:
    with _JOB_OWNER_LOCK:
        owner = _JOB_OWNER_BY_STORE.get(store_identity)
    if owner is None:
        raise ChildReleaseUnavailableError("job_release_authority_bridge_unavailable")
    return owner


class _ChildReleaseHead(BaseModel):
    """Owner operational head; a released head selects one immutable record."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"
    release_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    root_run_id: str = Field(min_length=1)
    served_store_identity: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    status: Literal["pending", "released", "revoked"]
    release_ref: ArtifactRef | None = None
    job_authorization: ChildJobReleaseLocator | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    reason: str | None = None


def child_store_identity(root: Path) -> str:
    """Bind a release to its actual canonical served filesystem CAS owner."""
    try:
        resolved = root.resolve(strict=True)
    except OSError as exc:
        raise ChildReleaseUnavailableError("served_owner_unavailable") from exc
    return "sha256:" + hashlib.sha256(os.fsencode(str(resolved))).hexdigest()


def child_binding_digest(payload: dict[str, JsonValue]) -> str:
    """Hash the complete finite JSON-mode binding under a fixed Core codec."""
    data = to_canonical_bytes(payload, CanonSpec(exclude_none=False))
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _safe_read(root: Path, path: Path, *, limit: int = _RECORD_LIMIT) -> bytes:
    try:
        relative = path.relative_to(root)
        current = root
        for part in relative.parts[:-1]:
            current = current / part
            if not stat.S_ISDIR(os.lstat(current).st_mode):
                raise ChildReleaseUnavailableError("owner_path_not_directory")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ChildReleaseUnavailableError("owner_member_not_regular")
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                data = stream.read(limit + 1)
            if len(data) > limit:
                raise ChildReleaseUnavailableError("owner_record_limit")
            return data
        finally:
            os.close(descriptor)
    except ChildReleaseUnavailableError:
        raise
    except (OSError, ValueError) as exc:
        raise ChildReleaseUnavailableError("owner_state_unavailable") from exc


def _safe_directory(root: Path, path: Path) -> None:
    relative = path.relative_to(root)
    current = root
    for part in relative.parts:
        current = current / part
        if os.path.lexists(current) and not stat.S_ISDIR(os.lstat(current).st_mode):
            raise ChildReleaseUnavailableError("owner_directory_unsafe")
    ensure_directory_durable(path)


def _head_path(root: Path, release_id: str) -> Path:
    if len(release_id) != 32 or any(c not in "0123456789abcdef" for c in release_id):
        raise ChildReleaseUnavailableError("release_id_invalid")
    return root / "artifacts/ownership/child_releases/heads" / (release_id + ".json")


def _key(ref: ArtifactRef) -> tuple[str, str, str, str]:
    if ref.manifest_profile_sha256 is None:
        raise ChildReleaseUnavailableError("selected_profile_required")
    return str(ref.artifact_id), ref.kind, ref.media_type, ref.manifest_profile_sha256


def _read_head(root: Path, release_id: str) -> _ChildReleaseHead:
    try:
        head = _ChildReleaseHead.model_validate_json(_safe_read(root, _head_path(root, release_id)))
    except ChildReleaseUnavailableError:
        raise
    except ValueError as exc:
        raise ChildReleaseUnavailableError("head_invalid") from exc
    if head.release_id != release_id or head.served_store_identity != child_store_identity(root):
        raise ChildReleaseUnavailableError("head_owner_mismatch")
    return head


def refuse_remote_child_manifest(raw: bytes) -> None:
    """Deny a marked remote view: this backend cannot resolve its local owner."""
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return  # Preserve the raw port's historic malformed-byte behavior.
    if isinstance(value, dict) and value.get("child_release") is not None:
        raise ChildReleaseUnavailableError("remote_release_verifier_unavailable")


def _read_durable_release_head(root: Path, release_id: str) -> _ChildReleaseHead:
    """Fsync the owner directory and reread before a reader grants release."""
    from . import _atomic_write

    head = _read_head(root, release_id)
    if head.status != "released":
        return head
    try:
        _atomic_write.fsync_directory(_head_path(root, release_id).parent)
    except OSError as exc:
        raise ChildReleaseUnavailableError("release_durability_unavailable") from exc
    if _read_head(root, release_id) != head:
        raise ChildReleaseUnavailableError("release_head_changed_during_durability_check")
    return head


def _record_from_head(root: Path, head: _ChildReleaseHead) -> ChildReleaseRecord:
    ref = head.release_ref
    if ref is None or ref.manifest_profile_sha256 is None or ref.kind != _RELEASE_KIND:
        raise ChildReleaseUnavailableError("release_record_ref_missing")
    aid = ref.artifact_id
    base = root / "artifacts/sha256" / aid.hex[:2] / aid.hex[2:4]
    raw_manifest = _safe_read(
        root,
        base / (aid.hex + ".view." + ref.manifest_profile_sha256[7:] + ".manifest.json"),
    )
    raw_payload = _safe_read(root, base / (aid.hex + ".blob"))
    try:
        manifest = ArtifactManifest.model_validate_json(raw_manifest)
        record = ChildReleaseRecord.model_validate_json(raw_payload)
    except ValueError as exc:
        raise ChildReleaseUnavailableError("release_record_invalid") from exc
    if (
        hashlib.sha256(raw_payload).hexdigest() != aid.hex
        or manifest.artifact_id != aid
        or manifest.kind != _RELEASE_KIND
        or manifest.media_type != "application/json"
        or manifest.byte_size != len(raw_payload)
        or ManifestLifecycle.profile_sha256(manifest) != ref.manifest_profile_sha256
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != _RELEASE_SCHEMA
        or manifest.artifact_schema.version != "1.0"
        or record.release_id != head.release_id
        or record.root_run_id != head.root_run_id
        or (manifest.tenant_context.tenant_id if manifest.tenant_context is not None else None)
        != record.tenant_id
        or (manifest.tenant_context.cell_id if manifest.tenant_context is not None else None)
        != record.cell_id
        or manifest.child_release is None
        or manifest.child_release.release_id != head.release_id
        or manifest.child_release.root_run_id != head.root_run_id
        or manifest.child_release.served_store_identity != head.served_store_identity
    ):
        raise ChildReleaseUnavailableError("release_record_content_mismatch")
    if child_binding_digest(record.parent_effects) != record.parent_effects_sha256:
        raise ChildReleaseUnavailableError("parent_effects_digest_mismatch")
    # Bind the record's own staged occurrence too; a copied bare record is no grant.
    _require_record_scope(record, manifest.child_release)
    keys = [_key(value) for value in record.released_refs]
    if len(keys) != len(set(keys)) or _key(record.projection_ref) not in keys:
        raise ChildReleaseUnavailableError("release_membership_invalid")
    _verify_job_authorization(head, record)
    return record


def _verify_job_authorization(head: _ChildReleaseHead, record: ChildReleaseRecord) -> None:
    """Require a committed owner event bound to the actual complete release."""
    payloads = tuple(record.binding_payloads.values())
    if not payloads or any("control_job_id" not in item for item in payloads):
        raise ChildReleaseUnavailableError("release_job_binding_missing")
    if any(
        item["control_job_id"] is not None and type(item["control_job_id"]) is not str
        for item in payloads
    ):
        raise ChildReleaseUnavailableError("release_job_binding_invalid")
    if any(
        type(item.get("admission_generation")) is not int or type(item.get("deadline")) is not str
        for item in payloads
    ):
        raise ChildReleaseUnavailableError("release_job_binding_invalid")
    job_ids = {item["control_job_id"] for item in payloads}
    generations = {item["admission_generation"] for item in payloads}
    deadlines = {item["deadline"] for item in payloads}
    if job_ids == {None}:
        raise ChildReleaseUnavailableError("jobless_child_release_unsupported")
    if len(job_ids) != 1 or len(generations) != 1 or len(deadlines) != 1:
        raise ChildReleaseUnavailableError("release_job_binding_mismatch")
    job_id = next(iter(job_ids))
    generation = next(iter(generations))
    deadline = next(iter(deadlines))
    if (
        type(job_id) is not str
        or not job_id
        or type(generation) is not int
        or type(deadline) is not str
        or head.release_ref is None
        or head.job_authorization is None
        or head.job_authorization.job_id != job_id
        or record.tenant_id is None
        or record.cell_id is None
    ):
        raise ChildReleaseUnavailableError("job_release_authority_bridge_unavailable")
    claim = ChildJobReleaseClaim(
        release_id=record.release_id,
        root_run_id=record.root_run_id,
        control_job_id=job_id,
        parent_attempt_id=record.parent_attempt_id,
        parent_basis_ref=record.parent_basis_ref,
        release_ref=head.release_ref,
        projection_ref=record.projection_ref,
        released_refs=record.released_refs,
        parent_effects_sha256=record.parent_effects_sha256,
        tenant_id=record.tenant_id,
        cell_id=record.cell_id,
        admission_generation=generation,
        deadline=deadline,
        served_store_identity=head.served_store_identity,
    )
    result = _child_job_owner(head.served_store_identity).verify_release(
        head.job_authorization, claim
    )
    if result is not None:
        raise ChildReleaseUnavailableError("job_owner_verifier_protocol_invalid")


class ChildRecordedSettlement(BaseModel):
    """Freshly resolved owner journal observation, not proof of actual effects or cost."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    classification: Literal["settlement_journal_recorded"] = "settlement_journal_recorded"
    release_id: str
    root_run_id: str
    parent_attempt_id: str
    parent_basis_json: bytes
    release_ref_json: bytes
    projection_ref_json: bytes
    parent_effects_sha256: str
    journal_effect_count: int
    journal_sha256: str
    job_intent_locator_json: bytes
    job_authorization_locator_json: bytes


def resolve_recorded_child_settlement(
    served_store: object,
    *,
    intent_locator: ChildJobReleaseLocator,
    expected_intent: ChildJobSessionClaim,
) -> ChildRecordedSettlement:
    """Resolve committed release/intent and the durable settled journal freshly.

    The trusted caller supplies its bootstrap-appointed exact served CAS and
    independently bound intent. This observation does not verify real Root
    effects, child physical completion, obligations, or budget settlement.
    """
    from . import _atomic_write
    from .store import FileSystemCAS

    if type(served_store) is not FileSystemCAS:
        raise ChildReleaseUnavailableError("settlement_served_owner_unavailable")
    if (
        type(intent_locator) is not ChildJobReleaseLocator
        or type(expected_intent) is not ChildJobSessionClaim
    ):
        raise ChildReleaseUnavailableError("settlement_intent_binding_invalid")
    try:
        expected_bytes = expected_intent.model_dump_json().encode()
        locator_bytes = intent_locator.model_dump_json().encode()
    except Exception as exc:
        raise ChildReleaseUnavailableError("settlement_intent_binding_invalid") from exc
    if len(expected_bytes) > _RECORD_LIMIT or len(locator_bytes) > _RECORD_LIMIT:
        raise ChildReleaseUnavailableError("settlement_intent_binding_invalid")
    try:
        expected = ChildJobSessionClaim.model_validate_json(expected_bytes)
        locator = ChildJobReleaseLocator.model_validate_json(locator_bytes)
        root = served_store.root.resolve(strict=True)
    except (OSError, ValueError) as exc:
        raise ChildReleaseUnavailableError("settlement_intent_binding_invalid") from exc
    try:
        store_identity = child_store_identity(root)
    except OSError as exc:
        raise ChildReleaseUnavailableError("settlement_served_owner_unavailable") from exc
    if (
        store_identity != expected.served_store_identity
        or locator.job_id != expected.control_job_id
    ):
        raise ChildReleaseUnavailableError("settlement_served_owner_mismatch")
    head = _read_durable_release_head(root, expected.release_id)
    if head.status != "released" or head.release_ref is None or head.job_authorization is None:
        raise ChildReleaseUnavailableError("settlement_release_not_committed")
    try:
        record = _record_from_head(root, head)
    except ChildReleaseUnavailableError:
        raise
    except Exception as exc:
        raise ChildReleaseUnavailableError("settlement_release_owner_unavailable") from exc
    payloads = tuple(record.binding_payloads.values())
    if (
        not payloads
        or len(record.scope_bindings) != len(payloads)
        or {info.scope_id for info in record.scope_bindings} != set(record.binding_payloads)
    ):
        raise ChildReleaseUnavailableError("settlement_binding_missing")
    for info in record.scope_bindings:
        _require_record_scope(record, info)
    for payload in payloads:
        try:
            actual = ChildJobSessionClaim(
                release_id=record.release_id,
                root_run_id=record.root_run_id,
                control_job_id=payload.get("control_job_id"),
                parent_attempt_id=record.parent_attempt_id,
                parent_basis_ref=record.parent_basis_ref,
                tenant_id=record.tenant_id,
                cell_id=record.cell_id,
                admission_generation=payload.get("admission_generation"),
                deadline=payload.get("deadline"),
                served_store_identity=head.served_store_identity,
            )
        except ValueError as exc:
            raise ChildReleaseUnavailableError("settlement_binding_invalid") from exc
        if actual != expected:
            raise ChildReleaseUnavailableError("settlement_intent_record_mismatch")
    try:
        result = _child_job_owner(expected.served_store_identity).verify_intent(locator, expected)
    except Exception as exc:
        raise ChildReleaseUnavailableError("settlement_intent_unavailable") from exc
    if result is not None:
        raise ChildReleaseUnavailableError("job_owner_verifier_protocol_invalid")
    try:
        unchanged = (
            expected_intent.model_dump_json().encode() == expected_bytes
            and intent_locator.model_dump_json().encode() == locator_bytes
        )
    except Exception as exc:
        raise ChildReleaseUnavailableError("settlement_intent_binding_changed") from exc
    if not unchanged:
        raise ChildReleaseUnavailableError("settlement_intent_binding_changed")
    effects = record.parent_effects
    if (
        set(effects) != {"updates", "events"}
        or type(effects["updates"]) is not list
        or type(effects["events"]) is not list
    ):
        raise ChildReleaseUnavailableError("settlement_effect_shape_invalid")
    count = len(effects["updates"]) + len(effects["events"])
    path = _head_path(root, expected.release_id).with_name(expected.release_id + ".settlement.json")
    raw = _safe_read(root, path)
    try:
        _atomic_write.fsync_directory(path.parent)
        if _safe_read(root, path) != raw:
            raise ChildReleaseUnavailableError("settlement_changed_during_read")

        def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, item in pairs:
                if key in result:
                    raise ValueError("duplicate_settlement_journal_key")
                result[key] = item
            return result

        value = json.loads(raw, object_pairs_hook=unique_pairs)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ChildReleaseUnavailableError("settlement_journal_unavailable") from exc
    if (
        type(value) is not dict
        or set(value) != {"schema_version", "release_id", "status", "completed", "total"}
        or value["schema_version"] != "1.0"
        or value["release_id"] != expected.release_id
        or value["status"] != "settled"
        or type(value["completed"]) is not int
        or type(value["total"]) is not int
        or value["completed"] != count
        or value["total"] != count
    ):
        raise ChildReleaseUnavailableError("settlement_journal_not_settled")
    if _read_durable_release_head(root, expected.release_id) != head:
        raise ChildReleaseUnavailableError("settlement_head_changed_during_read")
    return ChildRecordedSettlement(
        release_id=record.release_id,
        root_run_id=record.root_run_id,
        parent_attempt_id=record.parent_attempt_id,
        parent_basis_json=record.parent_basis_ref.model_dump_json().encode(),
        release_ref_json=head.release_ref.model_dump_json().encode(),
        projection_ref_json=record.projection_ref.model_dump_json().encode(),
        parent_effects_sha256=record.parent_effects_sha256,
        journal_effect_count=count,
        journal_sha256="sha256:" + hashlib.sha256(raw).hexdigest(),
        job_intent_locator_json=locator_bytes,
        job_authorization_locator_json=head.job_authorization.model_dump_json().encode(),
    )


def _require_record_scope(record: ChildReleaseRecord, info: ArtifactChildReleaseInfo) -> None:
    matches = [value for value in record.scope_bindings if value.scope_id == info.scope_id]
    payload = record.binding_payloads.get(info.scope_id)
    if len(matches) != 1 or matches[0] != info or payload is None:
        raise ChildReleaseUnavailableError("scope_binding_missing")
    if child_binding_digest(payload) != info.binding_sha256:
        raise ChildReleaseUnavailableError("scope_binding_digest_mismatch")
    if (
        payload.get("root_run_id") != info.root_run_id
        or payload.get("parent_attempt_id") != record.parent_attempt_id
        or payload.get("tenant_id") != record.tenant_id
        or payload.get("cell_id") != record.cell_id
    ):
        raise ChildReleaseUnavailableError("scope_binding_owner_mismatch")


def require_child_release_manifest(
    root: Path,
    manifest: ArtifactManifest,
    *,
    private_infos: tuple[ArtifactChildReleaseInfo, ...] = (),
) -> None:
    """Resolve the actual release of a manifest without granting from its tag."""
    info = manifest.child_release
    if info is None:
        return
    store_identity = child_store_identity(root)
    if info in private_infos and store_identity != info.served_store_identity:
        return
    if info.served_store_identity != store_identity:
        raise ChildReleaseUnavailableError("served_owner_mismatch")
    head = _read_durable_release_head(root, info.release_id)
    if head.status != "released":
        raise ChildReleaseUnavailableError("not_released:" + head.status)
    if head.root_run_id != info.root_run_id:
        raise ChildReleaseUnavailableError("root_run_mismatch")
    record = _record_from_head(root, head)
    _require_record_scope(record, info)
    selected = ArtifactRef(
        artifact_id=manifest.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=ManifestLifecycle.profile_sha256(manifest),
    )
    permitted = (*record.released_refs, head.release_ref)
    if not any(value is not None and _key(value) == _key(selected) for value in permitted):
        raise ChildReleaseUnavailableError("selected_view_not_released")


def require_child_release_raw(
    root: Path,
    raw_manifest: bytes,
    *,
    private_infos: tuple[ArtifactChildReleaseInfo, ...] = (),
) -> None:
    """Gate a raw sidecar at its existing transfer boundary, without a preread.

    Legacy raw-byte ports retain their existing malformed-byte behavior. A valid
    declared child class is parsed and resolved, never accepted by shape alone.
    The enrollment check separately protects known copied views before transfer.
    """
    try:
        value = json.loads(raw_manifest)
    except (UnicodeError, ValueError):
        return
    if not isinstance(value, dict) or value.get("child_release") is None:
        return
    try:
        manifest = ArtifactManifest.model_validate(value)
    except ValueError as exc:
        raise ChildReleaseUnavailableError("child_manifest_invalid") from exc
    require_child_release_manifest(root, manifest, private_infos=private_infos)


def require_enrolled_child_release(
    root: Path,
    artifact_id: ArtifactID,
    profile: str | None,
    *,
    private_infos: tuple[ArtifactChildReleaseInfo, ...] = (),
) -> None:
    """Check a copied view's operational enrollment before any public transfer."""
    if profile is None:
        return  # Default aliases are checked against their actual parsed manifest.
    path = (
        root
        / "artifacts/ownership/child_releases/enrollments"
        / artifact_id.hex
        / (profile.removeprefix("sha256:") + ".json")
    )
    if not os.path.lexists(path):
        return  # The actual manifest emission still discovers a missing enrollment.
    try:
        info = ArtifactChildReleaseInfo.model_validate_json(_safe_read(root, path))
    except ChildReleaseUnavailableError:
        raise
    except ValueError as exc:
        raise ChildReleaseUnavailableError("enrollment_invalid") from exc
    if info in private_infos and child_store_identity(root) != info.served_store_identity:
        return
    head = _read_durable_release_head(root, info.release_id)
    if head.status != "released":
        raise ChildReleaseUnavailableError("not_released:" + head.status)
    record = _record_from_head(root, head)
    _require_record_scope(record, info)
    if not any(
        str(ref.artifact_id) == str(artifact_id) and ref.manifest_profile_sha256 == profile
        for ref in (*record.released_refs, head.release_ref)
        if ref is not None
    ):
        raise ChildReleaseUnavailableError("enrolled_view_not_selected")


class _ChildReleaseLedger:
    """Core operational owner using one atomic head for a selected parent release."""

    def __init__(self, root: Path, release_id: str, root_run_id: str) -> None:
        self.root = root.resolve(strict=True)
        self.release_id = release_id
        self.root_run_id = root_run_id
        self.store_identity = child_store_identity(self.root)
        self.path = _head_path(self.root, release_id)
        _safe_directory(self.root, self.path.parent)
        head = _ChildReleaseHead(
            release_id=release_id,
            root_run_id=root_run_id,
            served_store_identity=self.store_identity,
            status="pending",
        )
        if not AtomicFileWriter.write_once(
            self.path, head.model_dump_json().encode(), durable_parent=True
        ):
            old = _read_head(self.root, release_id)
            if old != head:
                raise ChildReleaseUnavailableError("release_session_already_exists")

    def head(self) -> _ChildReleaseHead:
        """Read the actual current head, including an acknowledgement-lost commit."""
        return _read_head(self.root, self.release_id)

    def enroll(self, refs: tuple[tuple[ArtifactRef, ArtifactChildReleaseInfo], ...]) -> None:
        """Persist exact deny-first associations before any served-root copy."""
        if self.head().status != "pending":
            raise ChildReleaseUnavailableError("enrollment_not_pending")
        for ref, info in refs:
            _key(ref)
            if info.release_id != self.release_id or info.root_run_id != self.root_run_id:
                raise ChildReleaseUnavailableError("enrollment_session_mismatch")
            path = (
                self.root
                / "artifacts/ownership/child_releases/enrollments"
                / ref.artifact_id.hex
                / (ref.manifest_profile_sha256[7:] + ".json")
            )
            _safe_directory(self.root, path.parent)
            data = info.model_dump_json().encode()
            if (
                not AtomicFileWriter.write_once(path, data, durable_parent=True)
                and _safe_read(self.root, path) != data
            ):
                raise ChildReleaseUnavailableError("enrollment_conflict")

    def commit(
        self, release_ref: ArtifactRef, *, job_authorization: ChildJobReleaseLocator | None = None
    ) -> bool:
        """Commit once; reconcile exact durable bytes if the acknowledgement is lost."""
        current = self.head()
        if current.status == "released":
            # A reread alone does not establish the earlier writer's durability.
            raise ChildReleaseUnavailableError("release_requires_owner_reconciliation")
        if current.status != "pending":
            raise ChildReleaseUnavailableError("release_session_revoked")
        updated = current.model_copy(
            update={
                "status": "released",
                "release_ref": release_ref,
                "job_authorization": job_authorization,
            }
        )
        data = updated.model_dump_json().encode()
        # A visible reread after failed fsync does not establish crash durability.
        # The caller reconciles every raised outcome without retry or rollback claims.
        AtomicFileWriter.write_atomic(self.path, data, durable_parent=True)
        return False

    def record_settlement(
        self, state: Literal["pending", "settled", "unknown"], *, completed: int, total: int
    ) -> None:
        """Record acknowledgement progress, never permission or a claim of rollback."""
        if self.head().status != "released":
            raise ChildReleaseUnavailableError("settlement_requires_committed_release")
        path = self.path.with_name(self.release_id + ".settlement.json")
        payload = json.dumps(
            {
                "schema_version": "1.0",
                "release_id": self.release_id,
                "status": state,
                "completed": completed,
                "total": total,
            },
            sort_keys=True,
        ).encode()
        AtomicFileWriter.write_atomic(path, payload, durable_parent=True)

    def revoke(self, reason: str) -> None:
        """Refuse later release while retaining an already committed historical release."""
        current = self.head()
        if current.status == "released":
            return
        updated = current.model_copy(update={"status": "revoked", "reason": reason})
        AtomicFileWriter.write_atomic(
            self.path, updated.model_dump_json().encode(), durable_parent=True
        )
