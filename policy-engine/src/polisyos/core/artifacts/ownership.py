"""Tenant ownership index for shared immutable CAS artifacts."""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import re
import shutil
import threading
import weakref
from collections.abc import Iterable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.core.canon.canon_json import CanonSpec, to_canonical_bytes

from ._atomic_write import (
    AtomicFileDurabilityError,
    AtomicFileWriter,
    ensure_directory_durable,
    fsync_directory,
)
from .ids import ArtifactID

OWNERSHIP_INDEX_SCHEMA_VERSION = "policyos.artifact_ownership_index.v2"
OWNERSHIP_SIGNATURE_SCHEMA_VERSION = "policyos.artifact_ownership_index_signature.v2"
OWNERSHIP_INDEX_POINTER_SCHEMA_VERSION = "policyos.artifact_ownership_index_pointer.v1"
OWNERSHIP_INDEX_GENERATION_SCHEMA_VERSION = "policyos.artifact_ownership_index_generation.v1"
OWNERSHIP_EVIDENCE_SCHEMA_VERSION_V3 = "policyos.artifact_ownership_evidence.v3"
OWNERSHIP_INDEX_FORMAT_POINTER_GENERATION_V1 = "pointer_generation_v1"
_OWNERSHIP_INDEX_SCHEMA_VERSION_V1 = "policyos.artifact_ownership_index.v1"
_OWNERSHIP_SIGNATURE_SCHEMA_VERSION_V1 = "policyos.artifact_ownership_index_signature.v1"
OWNERSHIP_MODE_SHARED_CAS = "shared_immutable_cas"
_FileIdentity = tuple[int, ...] | None
_HEX_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_TRANSACTION_INTENT_SCHEMA_V1 = "policyos.artifact_ownership_transaction_intent.v1"
_TRANSACTION_INTENT_SCHEMA = "policyos.artifact_ownership_transaction_intent.v2"
_TRANSACTION_INTENT_SCHEMA_V3 = "policyos.artifact_ownership_transaction_intent.v3"
_TRANSACTION_INTENT_FIELDS_V1 = frozenset(
    {
        "schema_version",
        "status",
        "mode",
        "operation_id",
        "artifact_id",
        "owner",
        "blob_sha256",
        "blob_stage",
        "views",
        "claims",
        "affected",
        "request_sha256",
    }
)
_TRANSACTION_INTENT_FIELDS = _TRANSACTION_INTENT_FIELDS_V1 | {"manifest_created_at"}
_TRANSACTION_INTENT_FIELDS_V3 = _TRANSACTION_INTENT_FIELDS | {"signatures"}


class _DuplicateJSONKeyError(ValueError):
    """Raised when an ownership index document contains ambiguous JSON keys."""


@dataclass(frozen=True)
class _OwnershipSnapshot:
    """One validated ownership view and the exact bytes needed to migrate it."""

    payload: dict[str, Any]
    signature: dict[str, Any] | None
    source_format: str
    persisted: bool
    legacy_index_bytes: bytes | None = None
    legacy_signature_bytes: bytes | None = None
    generation_sha256: str | None = None
    generation_path: Path | None = None
    pointer_sha256: str | None = None
    payload_sha256: str | None = None
    signature_sha256: str | None = None


class OwnershipIndexPublicationIndeterminateError(RuntimeError):
    """A pointer was replaced but its durable directory sync was not confirmed."""

    def __init__(self, generation_sha256: str, observed_generation_sha256: str | None) -> None:
        super().__init__("ownership_index_publication_indeterminate")
        self.generation_sha256 = generation_sha256
        self.observed_generation_sha256 = observed_generation_sha256


class ArtifactOwnershipError(PermissionError):
    """Raised when a tenant attempts to access an artifact it does not own."""


class ArtifactTransactionPendingError(ArtifactOwnershipError):
    """A requested artifact surface has an unresolved publication transaction."""

    code = "artifact_transaction_pending"

    def __init__(self, artifact_id: ArtifactID, *, surface: str) -> None:
        self.artifact_id = artifact_id
        self.surface = surface
        super().__init__(
            f"artifact_transaction_pending: {artifact_id} publication surface {surface} "
            "has not been reconciled with the current owner generation"
        )


@dataclass(frozen=True)
class _ArtifactTransactionLease:
    """Opaque proof that one root/artifact transaction boundary is held."""

    coordinator: _RootTransactionCoordinator
    artifact_hex: str
    exclusive: bool
    nonce: object


class _WriterPreferringRWLock:
    """Small writer-preferring gate for root-wide snapshots and ordinary operations."""

    def __init__(self) -> None:
        self._condition = threading.Condition(threading.Lock())
        self._readers = 0
        self._writer_active = False
        self._waiting_writers = 0

    @contextmanager
    def shared(self) -> Iterator[None]:
        with self._condition:
            while self._writer_active or self._waiting_writers:
                self._condition.wait()
            self._readers += 1
        try:
            yield
        finally:
            with self._condition:
                self._readers -= 1
                if self._readers == 0:
                    self._condition.notify_all()

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        with self._condition:
            self._waiting_writers += 1
            try:
                while self._writer_active or self._readers:
                    self._condition.wait()
                self._writer_active = True
            finally:
                self._waiting_writers -= 1
        try:
            yield
        finally:
            with self._condition:
                self._writer_active = False
                self._condition.notify_all()


class _RootTransactionCoordinator:
    """Coordinate bounded in-process and cross-process CAS lock stripes per root."""

    STRIPE_COUNT = 64

    def __init__(self, root: Path) -> None:
        self.root = root
        self.transaction_root = root / "artifacts" / "ownership" / "transactions"
        self.lock_directory = self.transaction_root / "locks"
        self.root_lock_path = self.transaction_root / "root.lock"
        ensure_directory_durable(self.transaction_root)
        ensure_directory_durable(self.lock_directory)
        AtomicFileWriter.write_once(self.root_lock_path, b"", durable_parent=True)
        self._root_gate = _WriterPreferringRWLock()
        self._artifact_locks = tuple(
            threading.RLock() for _ in range(self.STRIPE_COUNT)
        )
        self._active = threading.local()
        self._stage_recovery_lock = threading.Lock()
        self._stage_recovery_complete = False

    def _stripe(self, artifact_id: ArtifactID) -> int:
        return int(artifact_id.hex, 16) % self.STRIPE_COUNT

    @contextmanager
    def _lock_file(self, path: Path, operation: int) -> Iterator[object]:
        ensure_directory_durable(path.parent)
        AtomicFileWriter.write_once(path, b"", durable_parent=True)
        lock_file = path.open("a+b")
        try:
            fcntl.flock(lock_file.fileno(), operation)
            yield lock_file
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    @contextmanager
    def root_exclusive(self) -> Iterator[None]:
        """Hold the permanent root barrier exclusively for bounded maintenance."""
        with self._root_gate.exclusive(), self._lock_file(
            self.root_lock_path,
            fcntl.LOCK_EX,
        ):
            yield

    @contextmanager
    def artifact_lease(
        self,
        artifact_id: ArtifactID,
        *,
        exclusive: bool,
    ) -> Iterator[_ArtifactTransactionLease]:
        """Hold root-shared then one stable artifact stripe in lock-order sequence."""
        active = getattr(self._active, "leases", None)
        if active is None:
            active = {}
            self._active.leases = active
        existing = active.get(artifact_id.hex)
        if existing is not None:
            if exclusive and not existing.exclusive:
                raise RuntimeError("artifact_transaction_lock_upgrade_not_supported")
            yield existing
            return
        if active:
            raise RuntimeError("artifact_transaction_nested_distinct_id_not_supported")

        stripe = self._stripe(artifact_id)
        stripe_path = self.lock_directory / f"stripe-{stripe:02d}.lock"
        file_operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        with (
            self._root_gate.shared(),
            self._lock_file(self.root_lock_path, fcntl.LOCK_SH),
            self._artifact_locks[stripe],
            self._lock_file(stripe_path, file_operation),
        ):
            lease = _ArtifactTransactionLease(
                coordinator=self,
                artifact_hex=artifact_id.hex,
                exclusive=exclusive,
                nonce=object(),
            )
            active[artifact_id.hex] = lease
            try:
                yield lease
            finally:
                active.pop(artifact_id.hex, None)

    @contextmanager
    def artifact_leases(
        self,
        artifact_ids: Iterable[ArtifactID],
        *,
        exclusive: bool,
    ) -> Iterator[dict[str, _ArtifactTransactionLease]]:
        """Hold a deterministic set of artifact stripes under one root lease."""
        ids = tuple({artifact_id.hex: artifact_id for artifact_id in artifact_ids}.values())
        stripes = sorted({self._stripe(artifact_id) for artifact_id in ids})
        active = getattr(self._active, "leases", None)
        if active is None:
            active = {}
            self._active.leases = active
        if active:
            if all(artifact_id.hex in active for artifact_id in ids):
                leases = {artifact_id.hex: active[artifact_id.hex] for artifact_id in ids}
                if exclusive and any(not lease.exclusive for lease in leases.values()):
                    raise RuntimeError("artifact_transaction_lock_upgrade_not_supported")
                yield leases
                return
            raise RuntimeError("artifact_transaction_nested_batch_not_supported")

        operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        leases: dict[str, _ArtifactTransactionLease] = {}
        with self._root_gate.shared(), ExitStack() as stack:
            stack.enter_context(self._lock_file(self.root_lock_path, fcntl.LOCK_SH))
            for stripe in stripes:
                stack.enter_context(self._artifact_locks[stripe])
                stripe_path = self.lock_directory / f"stripe-{stripe:02d}.lock"
                stack.enter_context(self._lock_file(stripe_path, operation))
            for artifact_id in ids:
                lease = _ArtifactTransactionLease(
                    coordinator=self,
                    artifact_hex=artifact_id.hex,
                    exclusive=exclusive,
                    nonce=object(),
                )
                active[artifact_id.hex] = lease
                leases[artifact_id.hex] = lease
            try:
                yield leases
            finally:
                for artifact_id in ids:
                    active.pop(artifact_id.hex, None)

    def validate_lease(
        self,
        lease: _ArtifactTransactionLease,
        artifact_id: ArtifactID,
        *,
        exclusive: bool,
    ) -> None:
        active = getattr(self._active, "leases", {})
        if (
            lease.coordinator is not self
            or lease.artifact_hex != artifact_id.hex
            or (exclusive and not lease.exclusive)
            or active.get(artifact_id.hex) is not lease
        ):
            raise RuntimeError("artifact_transaction_lease_invalid")


_COORDINATOR_REGISTRY_LOCK = threading.Lock()
_COORDINATORS: weakref.WeakValueDictionary[str, _RootTransactionCoordinator] = (
    weakref.WeakValueDictionary()
)


def _coordinator_for_root(root: Path) -> _RootTransactionCoordinator:
    key = str(root)
    with _COORDINATOR_REGISTRY_LOCK:
        coordinator = _COORDINATORS.get(key)
        if coordinator is None:
            coordinator = _RootTransactionCoordinator(root)
            _COORDINATORS[key] = coordinator
        return coordinator


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _normal_tenant_id(value: str | None) -> str:
    tenant_id = str(value or "").strip()
    if not tenant_id:
        raise ArtifactOwnershipError("Tenant-scoped artifact access requires a tenant_id")
    return tenant_id


def _normal_cell_id(value: str | None) -> str | None:
    cell_id = str(value or "").strip()
    return cell_id or None


def _record_matches_owner(
    record: dict[str, Any],
    *,
    tenant_id: str,
    cell_id: str | None,
) -> bool:
    if "manifest_profile_sha256" in record:
        return False
    if record.get("tenant_id") != tenant_id:
        return False
    recorded_cell = _normal_cell_id(record.get("cell_id"))
    return recorded_cell == cell_id


def _record_matches_view_owner(
    record: dict[str, Any],
    *,
    manifest_profile_sha256: str,
    tenant_id: str,
    cell_id: str | None,
) -> bool:
    return (
        record.get("manifest_profile_sha256") == manifest_profile_sha256
        and record.get("tenant_id") == tenant_id
        and _normal_cell_id(record.get("cell_id")) == cell_id
    )


def _validate_profile_sha256(value: str) -> None:
    prefix, separator, digest = str(value).partition(":")
    if (
        prefix != "sha256"
        or not separator
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError("manifest_profile_sha256 must be sha256:<64 lowercase hex>")


class ArtifactOwnershipIndex:
    """Persist tenant ownership claims next to a shared immutable filesystem CAS.

    The index is intentionally separate from blob/manifests so artifact IDs stay
    canonical content hashes across tenants. A write claims ownership for the
    current tenant; reads require a matching claim when the CAS is tenant-scoped.
    """

    def __init__(self, root: Path) -> None:
        requested_root = Path(root)
        ensure_directory_durable(requested_root)
        self.root = requested_root.resolve(strict=True)
        self._coordinator = _coordinator_for_root(self.root)
        self.directory = self.root / "artifacts" / "ownership"
        self.path = self.directory / "index.json"
        self.signature_path = self.directory / "index.signature.json"
        self._lock_path = self.directory / "index.lock"
        self._lock = threading.Lock()
        self._claim_file_identities: tuple[_FileIdentity, ...] | None = None
        self._claim_ids_cache: frozenset[str] | None = None

    @property
    def transaction_root(self) -> Path:
        """Return the private operational journal root for this CAS owner."""
        return self._coordinator.transaction_root

    def _transaction_intent_path(self, artifact_id: ArtifactID) -> Path:
        return (
            self.transaction_root
            / "intents"
            / artifact_id.hex[:2]
            / f"{artifact_id.hex}.json"
        )

    def _read_transaction_intent(self, artifact_id: ArtifactID) -> dict[str, Any] | None:
        path = self._transaction_intent_path(artifact_id)
        if self._path_has_symlink_component(path):
            raise ArtifactTransactionPendingError(artifact_id, surface="artifact")
        try:
            raw = self._read_private_file_no_follow(path)
        except FileNotFoundError:
            return None
        except OSError:
            raise ArtifactTransactionPendingError(artifact_id, surface="artifact") from None
        try:
            document = _decode_json(raw, reject_duplicate_keys=True)
            self._validate_transaction_intent(document, artifact_id)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
            raise ArtifactTransactionPendingError(artifact_id, surface="artifact") from None
        return document

    def _validate_transaction_intent(
        self,
        document: Any,
        artifact_id: ArtifactID,
    ) -> None:
        if not isinstance(document, dict):
            raise ValueError("artifact_ownership_transaction_intent_invalid")
        schema_version = document.get("schema_version")
        legacy_v1 = schema_version == _TRANSACTION_INTENT_SCHEMA_V1
        legacy_v2 = schema_version == _TRANSACTION_INTENT_SCHEMA
        expected_fields = (
            _TRANSACTION_INTENT_FIELDS_V1
            if legacy_v1
            else _TRANSACTION_INTENT_FIELDS
            if legacy_v2
            else _TRANSACTION_INTENT_FIELDS_V3
        )
        if set(document) != expected_fields:
            raise ValueError("artifact_ownership_transaction_intent_invalid")
        allowed_modes = {"publish"} if legacy_v1 or legacy_v2 else {
            "publish",
            "import",
            "signature",
        }
        if (
            schema_version
            not in {
                _TRANSACTION_INTENT_SCHEMA_V1,
                _TRANSACTION_INTENT_SCHEMA,
                _TRANSACTION_INTENT_SCHEMA_V3,
            }
            or document["status"] not in {"pending", "committed"}
            or document["mode"] not in allowed_modes
            or document["artifact_id"] != str(artifact_id)
            or not isinstance(document["operation_id"], str)
            or re.fullmatch(r"[0-9a-f]{32}", document["operation_id"]) is None
            or not isinstance(document["blob_sha256"], str)
            or _HEX_SHA256.fullmatch(document["blob_sha256"]) is None
            or not isinstance(document["request_sha256"], str)
            or _HEX_SHA256.fullmatch(document["request_sha256"]) is None
        ):
            raise ValueError("artifact_ownership_transaction_intent_invalid")

        owner = document["owner"]
        if owner is not None and (
            not isinstance(owner, dict)
            or set(owner) != {"tenant_id", "cell_id"}
            or not isinstance(owner["tenant_id"], str)
            or not owner["tenant_id"].strip()
            or (owner["cell_id"] is not None and not isinstance(owner["cell_id"], str))
        ):
            raise ValueError("artifact_ownership_transaction_intent_invalid")

        self._validate_transaction_stage_path(document["blob_stage"], document["operation_id"])
        views = document["views"]
        if not isinstance(views, list) or not views:
            raise ValueError("artifact_ownership_transaction_intent_invalid")
        selectors: set[str] = set()
        for view in views:
            if (
                not isinstance(view, dict)
                or set(view)
                != {
                    "selector",
                    "manifest_profile_sha256",
                    "manifest_sha256",
                    "manifest_stage",
                }
                or (
                    view["selector"] != "default"
                    and not _HEX_SHA256.fullmatch(str(view["selector"]))
                )
                or not isinstance(view["manifest_profile_sha256"], str)
                or _HEX_SHA256.fullmatch(view["manifest_profile_sha256"]) is None
                or not isinstance(view["manifest_sha256"], str)
                or _HEX_SHA256.fullmatch(view["manifest_sha256"]) is None
            ):
                raise ValueError("artifact_ownership_transaction_intent_invalid")
            selector = view["selector"]
            if (
                selector in selectors
                or (selector != "default" and selector != view["manifest_profile_sha256"])
            ):
                raise ValueError("artifact_ownership_transaction_intent_invalid")
            selectors.add(selector)
            self._validate_transaction_stage_path(
                view["manifest_stage"],
                document["operation_id"],
            )

        signatures = document.get("signatures", [])
        if not isinstance(signatures, list):
            raise ValueError("artifact_ownership_transaction_intent_invalid")
        signature_selectors: set[str] = set()
        for signature in signatures:
            if (
                not isinstance(signature, dict)
                or set(signature) != {"selector", "signature_sha256", "signature_stage"}
                or (
                    signature["selector"] != "default"
                    and not _HEX_SHA256.fullmatch(str(signature["selector"]))
                )
                or not isinstance(signature["signature_sha256"], str)
                or _HEX_SHA256.fullmatch(signature["signature_sha256"]) is None
            ):
                raise ValueError("artifact_ownership_transaction_intent_invalid")
            selector = signature["selector"]
            if selector in signature_selectors:
                raise ValueError("artifact_ownership_transaction_intent_invalid")
            signature_selectors.add(selector)
            self._validate_transaction_stage_path(
                signature["signature_stage"],
                document["operation_id"],
            )

        mode = document["mode"]
        if (
            (mode == "signature" and len(signatures) != 1)
            or (
                mode == "signature"
                and signatures[0]["signature_stage"] is None
            )
            or (
                mode == "signature"
                and (
                    document["blob_stage"] is not None
                    or any(view["manifest_stage"] is not None for view in views)
                )
            )
        ):
            raise ValueError("artifact_ownership_transaction_intent_invalid")

        claims = document["claims"]
        if (
            not isinstance(claims, dict)
            or set(claims) != {"default_owner", "blob_reader", "view_owners"}
            or type(claims["default_owner"]) is not bool
            or type(claims["blob_reader"]) is not bool
            or not isinstance(claims["view_owners"], list)
            or any(
                not isinstance(profile, str) or _HEX_SHA256.fullmatch(profile) is None
                for profile in claims["view_owners"]
            )
            or len(set(claims["view_owners"])) != len(claims["view_owners"])
        ):
            raise ValueError("artifact_ownership_transaction_intent_invalid")
        affected = document["affected"]
        if (
            not isinstance(affected, dict)
            or set(affected) != {"ambient_artifact", "manifest_profiles", "signature_profiles"}
            or type(affected["ambient_artifact"]) is not bool
            or not isinstance(affected["manifest_profiles"], list)
            or not isinstance(affected["signature_profiles"], list)
            or any(
                not isinstance(profile, str) or _HEX_SHA256.fullmatch(profile) is None
                for profile in affected["manifest_profiles"]
            )
            or any(
                not isinstance(selector, str)
                or (selector != "default" and _HEX_SHA256.fullmatch(selector) is None)
                for selector in affected["signature_profiles"]
            )
            or len(set(affected["manifest_profiles"]))
            != len(affected["manifest_profiles"])
            or len(set(affected["signature_profiles"]))
            != len(affected["signature_profiles"])
        ):
            raise ValueError("artifact_ownership_transaction_intent_invalid")

        if owner is None:
            if claims["default_owner"] or claims["blob_reader"] or claims["view_owners"]:
                raise ValueError("artifact_ownership_transaction_intent_invalid")
        else:
            profiles = {view["manifest_profile_sha256"] for view in views}
            if not set(claims["view_owners"]).issubset(profiles):
                raise ValueError("artifact_ownership_transaction_intent_invalid")
        profiles = {view["manifest_profile_sha256"] for view in views}
        view_selectors = {view["selector"] for view in views}
        staged_signature_selectors = {
            signature["selector"]
            for signature in signatures
            if signature["signature_stage"] is not None
        }
        if (
            not signature_selectors.issubset(view_selectors)
            or (mode == "signature" and affected["manifest_profiles"])
            or (mode == "signature" and affected["ambient_artifact"])
            or not set(affected["manifest_profiles"]).issubset(profiles)
            or (document["blob_stage"] is not None and not affected["ambient_artifact"])
            or any(
                view["manifest_stage"] is not None
                and not (
                    affected["ambient_artifact"]
                    if view["selector"] == "default"
                    else view["manifest_profile_sha256"] in affected["manifest_profiles"]
                )
                for view in views
            )
            or staged_signature_selectors != set(affected["signature_profiles"])
        ):
            raise ValueError("artifact_ownership_transaction_intent_invalid")

        if not legacy_v1:
            created_at = document["manifest_created_at"]
            if not isinstance(created_at, str):
                raise ValueError("artifact_ownership_transaction_intent_invalid")
            try:
                parsed_created_at = datetime.fromisoformat(created_at)
            except ValueError as exc:
                raise ValueError("artifact_ownership_transaction_intent_invalid") from exc
            if parsed_created_at.tzinfo is None or parsed_created_at.utcoffset() is None:
                raise ValueError("artifact_ownership_transaction_intent_invalid")

        digest = (
            self._transaction_request_digest_v1(document)
            if legacy_v1
            else self._transaction_request_digest(document)
        )
        if digest != document["request_sha256"]:
            raise ValueError("artifact_ownership_transaction_intent_digest_mismatch")

    def _validate_transaction_stage_path(self, value: Any, operation_id: str) -> None:
        if value is None:
            return
        if not isinstance(value, str):
            raise ValueError("artifact_ownership_transaction_stage_path_invalid")
        relative = Path(value)
        expected_prefix = Path("artifacts/ownership/transactions/stage")
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[: len(expected_prefix.parts)] != expected_prefix.parts
            or len(relative.parts) != len(expected_prefix.parts) + 2
            or relative.parts[len(expected_prefix.parts)] != operation_id
        ):
            raise ValueError("artifact_ownership_transaction_stage_path_invalid")

    def _path_has_symlink_component(self, path: Path) -> bool:
        try:
            relative = path.relative_to(self.root)
        except ValueError:
            return True
        current = self.root
        for component in relative.parts:
            current = current / component
            if current.is_symlink():
                return True
        return False

    @staticmethod
    def _transaction_request_digest(document: dict[str, Any]) -> str:
        views = [
            {
                "selector": view["selector"],
                "manifest_profile_sha256": view["manifest_profile_sha256"],
                **(
                    {"manifest_sha256": view["manifest_sha256"]}
                    if document.get("schema_version") == _TRANSACTION_INTENT_SCHEMA_V3
                    else {}
                ),
            }
            for view in document["views"]
        ]
        request = {
            "mode": document["mode"],
            "artifact_id": document["artifact_id"],
            "owner": document["owner"],
            "blob_sha256": document["blob_sha256"],
            "views": views,
            "claims": document["claims"],
            "affected": document["affected"],
        }
        if "signatures" in document:
            request["signatures"] = [
                {
                    "selector": signature["selector"],
                    "signature_sha256": signature["signature_sha256"],
                }
                for signature in document["signatures"]
            ]
        return _digest_payload(request)

    @staticmethod
    def _transaction_request_digest_v1(document: dict[str, Any]) -> str:
        views = [
            {
                "selector": view["selector"],
                "manifest_profile_sha256": view["manifest_profile_sha256"],
                "manifest_sha256": view["manifest_sha256"],
            }
            for view in document["views"]
        ]
        request = {
            "mode": document["mode"],
            "artifact_id": document["artifact_id"],
            "owner": document["owner"],
            "blob_sha256": document["blob_sha256"],
            "views": views,
            "claims": document["claims"],
            "affected": document["affected"],
        }
        return _digest_payload(request)

    def _intent_completion_is_recomputed(self, document: dict[str, Any]) -> bool:
        artifact_id = ArtifactID.model_validate(document["artifact_id"])
        directory = (
            self.root
            / "artifacts"
            / "sha256"
            / artifact_id.hex[:2]
            / artifact_id.hex[2:4]
        )
        blob_path = directory / f"{artifact_id.hex}.blob"
        try:
            if self._path_has_symlink_component(blob_path):
                return False
            if _file_sha256(blob_path) != document["blob_sha256"]:
                return False
            for view in document["views"]:
                selector = view["selector"]
                if selector == "default":
                    manifest_path = directory / f"{artifact_id.hex}.manifest.json"
                else:
                    profile_hex = selector.removeprefix("sha256:")
                    manifest_path = (
                        directory / f"{artifact_id.hex}.view.{profile_hex}.manifest.json"
                    )
                if self._path_has_symlink_component(manifest_path):
                    return False
                if _file_sha256(manifest_path) != view["manifest_sha256"]:
                    return False
            for signature in document.get("signatures", []):
                selector = signature["selector"]
                suffix = (
                    ".sig"
                    if selector == "default"
                    else f".view.{selector.removeprefix('sha256:')}.sig"
                )
                signature_path = directory / f"{artifact_id.hex}{suffix}"
                if self._path_has_symlink_component(signature_path):
                    return False
                if _file_sha256(signature_path) != signature["signature_sha256"]:
                    return False
        except OSError:
            return False

        owner = document["owner"]
        claims = document["claims"]
        if owner is None:
            if claims["default_owner"] or claims["blob_reader"] or claims["view_owners"]:
                return False
            try:
                return not self.has_any_tenant_claim(artifact_id)
            except (OSError, ValueError, TypeError):
                return False

        try:
            # All expected rows must be present in one validated owner generation.
            payload = self._load_snapshot().payload
            owner_records = _artifacts_mapping(payload).get(str(artifact_id), [])
            blob_reader_records = _blob_readers_mapping(payload).get(str(artifact_id), [])
        except (OSError, ValueError, TypeError):
            return False
        tenant_id = owner["tenant_id"]
        cell_id = owner["cell_id"]
        if claims["default_owner"] and not any(
            _record_matches_owner(record, tenant_id=tenant_id, cell_id=cell_id)
            for record in owner_records
        ):
            return False
        if claims["blob_reader"] and not any(
            _record_matches_owner(record, tenant_id=tenant_id, cell_id=cell_id)
            for record in blob_reader_records
        ):
            return False
        return all(
            any(
                _record_matches_view_owner(
                    record,
                    manifest_profile_sha256=profile,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                )
                for record in owner_records
            )
            for profile in claims["view_owners"]
        )

    def require_no_pending_transaction(
        self,
        artifact_id: ArtifactID | str,
        *,
        manifest_profile_sha256: str | None = None,
        signature_profile: str | None = None,
    ) -> None:
        """Deny reads of only the surfaces affected by an unresolved operation."""
        aid = _coerce_artifact_id(artifact_id)
        document = self._read_transaction_intent(aid)
        if document is None:
            return
        if document["status"] == "committed":
            if self._intent_completion_is_recomputed(document):
                return
        elif (
            document["owner"] is not None
            and self._intent_completion_is_recomputed(document)
        ):
            # A tenant generation is the independent completion signal.
            return
        affected = document["affected"]
        selected_signature = signature_profile or "default"
        if (
            affected["ambient_artifact"]
            or (
                manifest_profile_sha256 is not None
                and manifest_profile_sha256 in affected["manifest_profiles"]
            )
            or selected_signature in affected["signature_profiles"]
        ):
            surface = (
                f"signature:{selected_signature}"
                if selected_signature in affected["signature_profiles"]
                else manifest_profile_sha256 or "artifact"
            )
            raise ArtifactTransactionPendingError(aid, surface=surface)

    def write_transaction_intent(
        self,
        artifact_id: ArtifactID,
        document: dict[str, Any],
        *,
        lease: _ArtifactTransactionLease,
    ) -> Path:
        """Durably write the deny-only intent while the matching artifact lease is held."""
        self._coordinator.validate_lease(lease, artifact_id, exclusive=True)
        self._validate_transaction_intent(document, artifact_id)
        path = self._transaction_intent_path(artifact_id)
        ensure_directory_durable(path.parent)
        AtomicFileWriter.write_atomic(path, _json_bytes(document), durable_parent=True)
        return path

    def remove_transaction_intent(
        self,
        artifact_id: ArtifactID,
        *,
        lease: _ArtifactTransactionLease,
    ) -> None:
        """Durably remove a reconciled intent without changing owner authority."""
        self._coordinator.validate_lease(lease, artifact_id, exclusive=True)
        path = self._transaction_intent_path(artifact_id)
        try:
            path.unlink()
        except FileNotFoundError:
            return
        fsync_directory(path.parent)

    def recover_orphan_stages(self) -> None:
        """Remove stage directories that no durable intent can still reference."""
        coordinator = self._coordinator
        with coordinator._stage_recovery_lock:
            if coordinator._stage_recovery_complete:
                return
            with coordinator.root_exclusive():
                self._recover_orphan_stages_locked()
            coordinator._stage_recovery_complete = True

    def _recover_orphan_stages_locked(self) -> None:
        stage_root = self.transaction_root / "stage"
        intent_root = self.transaction_root / "intents"
        if (
            self._path_has_symlink_component(stage_root)
            or self._path_has_symlink_component(intent_root)
        ):
            return
        if not stage_root.is_dir():
            return
        referenced: set[str] = set()
        try:
            intent_paths = self._walk_private_regular_files(intent_root)
            if intent_paths is None:
                return
            for intent_path in intent_paths:
                if intent_path.suffix != ".json":
                    continue
                document = _decode_json(
                    self._read_private_file_no_follow(intent_path),
                    reject_duplicate_keys=True,
                )
                artifact_text = (
                    document.get("artifact_id") if isinstance(document, dict) else None
                )
                artifact_id = ArtifactID.model_validate(artifact_text)
                self._validate_transaction_intent(document, artifact_id)
                if intent_path != self._transaction_intent_path(artifact_id):
                    return
                operation_id = document["operation_id"]
                if document["blob_stage"] is not None:
                    referenced.add(operation_id)
                if (
                    any(view["manifest_stage"] is not None for view in document["views"])
                    or any(
                        signature["signature_stage"] is not None
                        for signature in document.get("signatures", [])
                    )
                ):
                    referenced.add(operation_id)
        except (OSError, ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
            return

        removed_any = False
        for stage_path in stage_root.iterdir():
            if stage_path.is_symlink() or not stage_path.is_dir():
                continue
            if stage_path.name in referenced:
                continue
            if self._walk_private_regular_files(stage_path) is None:
                continue
            shutil.rmtree(stage_path)
            removed_any = True
        if removed_any:
            fsync_directory(stage_root)

    def _walk_private_regular_files(self, root: Path) -> tuple[Path, ...] | None:
        """List a private tree without following symlinks or special files."""
        if self._path_has_symlink_component(root):
            return None
        if not root.exists():
            return ()
        files: list[Path] = []
        pending = [root]
        try:
            while pending:
                directory = pending.pop()
                for child in directory.iterdir():
                    if child.is_symlink():
                        return None
                    if child.is_dir():
                        pending.append(child)
                    elif child.is_file():
                        files.append(child)
                    else:
                        return None
        except OSError:
            return None
        return tuple(files)

    @staticmethod
    def _read_private_file_no_follow(path: Path) -> bytes:
        """Read one private journal file without following a final symlink."""
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 65536)
                if not chunk:
                    return b"".join(chunks)
                chunks.append(chunk)
        finally:
            os.close(descriptor)

    def record_owner(
        self,
        artifact_id: ArtifactID | str,
        *,
        tenant_id: str,
        cell_id: str | None = None,
        writer: str | None = None,
        _lease: _ArtifactTransactionLease | None = None,
    ) -> None:
        """Upsert one tenant ownership claim for an immutable CAS artifact."""
        aid = _coerce_artifact_id(artifact_id)
        if _lease is None:
            with self._coordinator.artifact_lease(aid, exclusive=True) as lease:
                self.require_no_pending_transaction(aid)
                self.record_owner(
                    aid,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                    writer=writer,
                    _lease=lease,
                )
            return
        self._coordinator.validate_lease(_lease, aid, exclusive=True)
        normalized_tenant = _normal_tenant_id(tenant_id)
        normalized_cell = _normal_cell_id(cell_id)
        with self._lock, self._cross_instance_write_lock():
            payload = self._load_payload()
            artifacts = _artifacts_mapping(payload)
            records = list(artifacts.get(str(aid), []))
            if any(
                _record_matches_owner(
                    record,
                    tenant_id=normalized_tenant,
                    cell_id=normalized_cell,
                )
                for record in records
            ):
                return
            record: dict[str, Any] = {
                "tenant_id": normalized_tenant,
                "claimed_at": _utc_now(),
            }
            if normalized_cell is not None:
                record["cell_id"] = normalized_cell
            if writer:
                record["writer"] = str(writer)
            records.append(record)
            artifacts[str(aid)] = sorted(
                records,
                key=lambda item: (
                    str(item.get("tenant_id") or ""),
                    str(item.get("cell_id") or ""),
                    str(item.get("claimed_at") or ""),
                ),
            )
            payload["artifacts"] = dict(sorted(artifacts.items()))
            self._write_payload(payload)

    def record_blob_reader(
        self,
        artifact_id: ArtifactID | str,
        *,
        tenant_id: str,
        cell_id: str | None = None,
        writer: str | None = None,
        _lease: _ArtifactTransactionLease | None = None,
    ) -> None:
        """Admit a tenant to shared payload bytes without granting default-view access."""
        aid = _coerce_artifact_id(artifact_id)
        if _lease is None:
            with self._coordinator.artifact_lease(aid, exclusive=True) as lease:
                self.require_no_pending_transaction(aid)
                self.record_blob_reader(
                    aid,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                    writer=writer,
                    _lease=lease,
                )
            return
        self._coordinator.validate_lease(_lease, aid, exclusive=True)
        normalized_tenant = _normal_tenant_id(tenant_id)
        normalized_cell = _normal_cell_id(cell_id)
        with self._lock, self._cross_instance_write_lock():
            payload = self._load_payload()
            blob_readers = _blob_readers_mapping(payload)
            records = list(blob_readers.get(str(aid), []))
            if any(
                _record_matches_owner(
                    record,
                    tenant_id=normalized_tenant,
                    cell_id=normalized_cell,
                )
                for record in records
            ):
                return
            record: dict[str, Any] = {
                "tenant_id": normalized_tenant,
                "claimed_at": _utc_now(),
            }
            if normalized_cell is not None:
                record["cell_id"] = normalized_cell
            if writer:
                record["writer"] = str(writer)
            records.append(record)
            blob_readers[str(aid)] = sorted(
                records,
                key=lambda item: (
                    str(item.get("tenant_id") or ""),
                    str(item.get("cell_id") or ""),
                    str(item.get("claimed_at") or ""),
                ),
            )
            payload["blob_readers"] = dict(sorted(blob_readers.items()))
            self._write_payload(payload)

    def is_blob_readable_by(
        self,
        artifact_id: ArtifactID | str,
        *,
        tenant_id: str,
        cell_id: str | None = None,
    ) -> bool:
        """Return whether a tenant may read payload bytes for an artifact."""
        aid = _coerce_artifact_id(artifact_id)
        if self.is_owned_by(aid, tenant_id=tenant_id, cell_id=cell_id):
            return True
        normalized_tenant = _normal_tenant_id(tenant_id)
        normalized_cell = _normal_cell_id(cell_id)
        records = _blob_readers_mapping(self._load_payload()).get(str(aid), [])
        return any(
            _record_matches_owner(
                record,
                tenant_id=normalized_tenant,
                cell_id=normalized_cell,
            )
            for record in records
        )

    def require_blob_reader(
        self,
        artifact_id: ArtifactID | str,
        *,
        tenant_id: str,
        cell_id: str | None = None,
        operation: str = "read",
    ) -> None:
        """Fail closed unless the tenant may read this blob's payload bytes."""
        aid = _coerce_artifact_id(artifact_id)
        if self.is_blob_readable_by(aid, tenant_id=tenant_id, cell_id=cell_id):
            return
        normalized_tenant = _normal_tenant_id(tenant_id)
        normalized_cell = _normal_cell_id(cell_id)
        raise ArtifactOwnershipError(
            f"Artifact {aid} payload is not readable by tenant "
            f"{_owner_label(normalized_tenant, normalized_cell)} for {operation}"
        )

    def record_view_owner(
        self,
        artifact_id: ArtifactID | str,
        manifest_profile_sha256: str,
        *,
        tenant_id: str,
        cell_id: str | None = None,
        writer: str | None = None,
        _lease: _ArtifactTransactionLease | None = None,
    ) -> None:
        """Admit one tenant to one exact manifest view of a shared blob."""
        aid = _coerce_artifact_id(artifact_id)
        if _lease is None:
            with self._coordinator.artifact_lease(aid, exclusive=True) as lease:
                self.require_no_pending_transaction(
                    aid,
                    manifest_profile_sha256=manifest_profile_sha256,
                )
                self.record_view_owner(
                    aid,
                    manifest_profile_sha256,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                    writer=writer,
                    _lease=lease,
                )
            return
        self._coordinator.validate_lease(_lease, aid, exclusive=True)
        _validate_profile_sha256(manifest_profile_sha256)
        normalized_tenant = _normal_tenant_id(tenant_id)
        normalized_cell = _normal_cell_id(cell_id)
        with self._lock, self._cross_instance_write_lock():
            payload = self._load_payload()
            artifacts = _artifacts_mapping(payload)
            records = list(artifacts.get(str(aid), []))
            if any(
                _record_matches_view_owner(
                    record,
                    manifest_profile_sha256=manifest_profile_sha256,
                    tenant_id=normalized_tenant,
                    cell_id=normalized_cell,
                )
                for record in records
            ):
                return
            record: dict[str, Any] = {
                "tenant_id": normalized_tenant,
                "manifest_profile_sha256": manifest_profile_sha256,
                "claimed_at": _utc_now(),
            }
            if normalized_cell is not None:
                record["cell_id"] = normalized_cell
            if writer:
                record["writer"] = str(writer)
            records.append(record)
            artifacts[str(aid)] = sorted(
                records,
                key=lambda item: (
                    str(item.get("tenant_id") or ""),
                    str(item.get("cell_id") or ""),
                    str(item.get("manifest_profile_sha256") or ""),
                    str(item.get("claimed_at") or ""),
                ),
            )
            payload["artifacts"] = dict(sorted(artifacts.items()))
            self._write_payload(payload)

    def is_view_owned_by(
        self,
        artifact_id: ArtifactID | str,
        manifest_profile_sha256: str,
        *,
        tenant_id: str,
        cell_id: str | None = None,
    ) -> bool:
        """Return whether this tenant was admitted to the exact profile view."""
        aid = _coerce_artifact_id(artifact_id)
        _validate_profile_sha256(manifest_profile_sha256)
        normalized_tenant = _normal_tenant_id(tenant_id)
        normalized_cell = _normal_cell_id(cell_id)
        return any(
            _record_matches_view_owner(
                record,
                manifest_profile_sha256=manifest_profile_sha256,
                tenant_id=normalized_tenant,
                cell_id=normalized_cell,
            )
            for record in self.owners_for(aid)
        )

    def require_view_owner(
        self,
        artifact_id: ArtifactID | str,
        manifest_profile_sha256: str,
        *,
        tenant_id: str,
        cell_id: str | None = None,
        operation: str = "read",
    ) -> None:
        """Fail closed unless the tenant owns this exact metadata view."""
        aid = _coerce_artifact_id(artifact_id)
        if self.is_view_owned_by(
            aid,
            manifest_profile_sha256,
            tenant_id=tenant_id,
            cell_id=cell_id,
        ):
            return
        normalized_tenant = _normal_tenant_id(tenant_id)
        normalized_cell = _normal_cell_id(cell_id)
        raise ArtifactOwnershipError(
            f"Manifest view {manifest_profile_sha256} for artifact {aid} is not owned "
            f"by tenant {_owner_label(normalized_tenant, normalized_cell)} for {operation}"
        )

    def owners_for(self, artifact_id: ArtifactID | str) -> list[dict[str, Any]]:
        """Return ownership records for one artifact, newest index view first."""
        aid = _coerce_artifact_id(artifact_id)
        payload = self._load_payload()
        records = _artifacts_mapping(payload).get(str(aid), [])
        return [dict(record) for record in records]

    def _transaction_claims_for(
        self,
        artifact_id: ArtifactID,
        *,
        tenant_id: str | None,
        cell_id: str | None,
        manifest_profile_sha256: str,
    ) -> dict[str, Any]:
        """Capture exact existing claim rows for one already-authorized transaction."""
        if tenant_id is None:
            return {"default_owner": False, "blob_reader": False, "view_owners": []}
        normalized_tenant = _normal_tenant_id(tenant_id)
        normalized_cell = _normal_cell_id(cell_id)
        payload = self._load_snapshot().payload
        owner_records = _artifacts_mapping(payload).get(str(artifact_id), [])
        blob_reader_records = _blob_readers_mapping(payload).get(str(artifact_id), [])
        return {
            "default_owner": any(
                _record_matches_owner(
                    record,
                    tenant_id=normalized_tenant,
                    cell_id=normalized_cell,
                )
                for record in owner_records
            ),
            "blob_reader": any(
                _record_matches_owner(
                    record,
                    tenant_id=normalized_tenant,
                    cell_id=normalized_cell,
                )
                for record in blob_reader_records
            ),
            "view_owners": (
                [manifest_profile_sha256]
                if any(
                    _record_matches_view_owner(
                        record,
                        manifest_profile_sha256=manifest_profile_sha256,
                        tenant_id=normalized_tenant,
                        cell_id=normalized_cell,
                    )
                    for record in owner_records
                )
                else []
            ),
        }

    def has_any_tenant_claim(self, artifact_id: ArtifactID | str) -> bool:
        """Return whether any tenant claim covers this artifact or its blob.

        This is a read-only aggregate query for ambient callers without an
        established owner. It validates every signed v1/v2 claim row before
        returning a negative result, so malformed rows cannot become an
        unclaimed-candidate classification. Historical index and signature
        bytes are never rewritten by this query.
        """
        aid = _coerce_artifact_id(artifact_id)
        return str(aid) in self._validated_claimed_artifact_ids()

    def claimed_artifact_ids(self) -> set[str]:
        """Return every artifact ID covered by any validated tenant claim."""
        return set(self._validated_claimed_artifact_ids())

    def _validated_claimed_artifact_ids(self) -> frozenset[str]:
        """Cache validated claim IDs until either signed file identity changes."""
        with self._lock:
            for _attempt in range(3):
                before = self._current_file_identities()
                if self._claim_ids_cache is not None and before == self._claim_file_identities:
                    return self._claim_ids_cache

                payload = self._load_payload()
                artifacts = _artifacts_mapping(payload)
                blob_readers = _blob_readers_mapping(payload)
                claimed_ids = frozenset(artifacts).union(blob_readers)
                after = self._current_file_identities()
                if before == after:
                    self._claim_file_identities = after
                    self._claim_ids_cache = claimed_ids
                    return claimed_ids

            self._invalidate_claim_cache()
            raise ValueError("ownership_index_changed_during_validation")

    def _current_file_identities(
        self,
    ) -> tuple[_FileIdentity, ...]:
        pointer = _load_json_file(self.path)
        generation_identity: _FileIdentity = None
        if (
            isinstance(pointer, dict)
            and pointer.get("schema_version") == OWNERSHIP_INDEX_POINTER_SCHEMA_VERSION
        ):
            generation_sha256 = pointer.get("generation_sha256")
            if isinstance(generation_sha256, str) and _HEX_SHA256.fullmatch(generation_sha256):
                generation_path = self._generation_path(generation_sha256)
                generation_identity = self._file_identity(generation_path)
        return (
            self._file_identity(self.path),
            self._file_identity(self.signature_path),
            generation_identity,
        )

    def _generation_path(self, generation_sha256: str) -> Path:
        if not _HEX_SHA256.fullmatch(generation_sha256):
            raise ValueError("ownership_index_pointer_invalid")
        generation_hex = generation_sha256.removeprefix("sha256:")
        return self.directory / "generations" / f"{generation_hex}.json"

    @staticmethod
    def _file_identity(path: Path) -> _FileIdentity:
        try:
            stat_result = path.stat()
        except FileNotFoundError:
            return None
        return (
            stat_result.st_dev,
            stat_result.st_ino,
            stat_result.st_size,
            stat_result.st_mtime_ns,
            stat_result.st_ctime_ns,
        )

    def _invalidate_claim_cache(self) -> None:
        self._claim_file_identities = None
        self._claim_ids_cache = None

    @contextmanager
    def _cross_instance_write_lock(self) -> Iterator[None]:
        """Serialize ownership-index read/modify/write across instances and processes."""
        ensure_directory_durable(self.directory)
        with self._lock_path.open("a+b") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def is_owned_by(
        self,
        artifact_id: ArtifactID | str,
        *,
        tenant_id: str,
        cell_id: str | None = None,
    ) -> bool:
        """Return whether the artifact has a matching tenant ownership claim."""
        normalized_tenant = _normal_tenant_id(tenant_id)
        normalized_cell = _normal_cell_id(cell_id)
        return any(
            _record_matches_owner(
                record,
                tenant_id=normalized_tenant,
                cell_id=normalized_cell,
            )
            for record in self.owners_for(artifact_id)
        )

    def require_owner(
        self,
        artifact_id: ArtifactID | str,
        *,
        tenant_id: str,
        cell_id: str | None = None,
        operation: str = "read",
    ) -> None:
        """Fail closed unless the tenant owns the artifact."""
        aid = _coerce_artifact_id(artifact_id)
        normalized_tenant = _normal_tenant_id(tenant_id)
        normalized_cell = _normal_cell_id(cell_id)
        if self.is_owned_by(aid, tenant_id=normalized_tenant, cell_id=normalized_cell):
            return
        owners = self.owners_for(aid)
        owner_labels = [
            _owner_label(record.get("tenant_id"), record.get("cell_id")) for record in owners
        ]
        owner_text = ", ".join(owner_labels) if owner_labels else "unowned"
        raise ArtifactOwnershipError(
            f"Artifact {aid} is not owned by tenant "
            f"{_owner_label(normalized_tenant, normalized_cell)} for {operation}; "
            f"current owners: {owner_text}"
        )

    def evidence(
        self,
        *,
        tenant_id: str | None = None,
        cell_id: str | None = None,
    ) -> dict[str, Any]:
        """Return evidence metadata suitable for canary/debug bundles."""
        with self._lock:
            snapshot = self._load_snapshot()
            payload = snapshot.payload
            artifacts = _artifacts_mapping(payload)
            blob_readers = _blob_readers_mapping(payload)
            digest = snapshot.payload_sha256 or _digest_payload(payload)
            signature = snapshot.signature or self._signature_payload(payload, digest=digest)
        evidence: dict[str, Any] = {
            "mode": OWNERSHIP_MODE_SHARED_CAS,
            "schema_version": str(payload["schema_version"]),
            "ownership_index_path": str(self.path),
            "ownership_index_digest": digest,
            "ownership_index_signature_digest": (
                snapshot.signature_sha256 or _digest_payload(signature)
            ),
            "artifact_count": len(artifacts),
            "blob_reader_claim_count": sum(len(records) for records in blob_readers.values()),
            "manifest_view_claim_count": sum(
                1
                for records in artifacts.values()
                for record in records
                if isinstance(record.get("manifest_profile_sha256"), str)
            ),
        }
        if snapshot.source_format in {
            _OWNERSHIP_INDEX_SCHEMA_VERSION_V1,
            OWNERSHIP_INDEX_SCHEMA_VERSION,
        }:
            evidence["ownership_index_signature_path"] = str(self.signature_path)
        if snapshot.source_format == OWNERSHIP_INDEX_POINTER_SCHEMA_VERSION:
            if (
                snapshot.generation_sha256 is None
                or snapshot.generation_path is None
                or snapshot.pointer_sha256 is None
            ):
                raise ValueError("ownership_index_generation_invalid")
            evidence.update(
                {
                    "ownership_evidence_schema_version": (OWNERSHIP_EVIDENCE_SCHEMA_VERSION_V3),
                    "ownership_index_format": (OWNERSHIP_INDEX_FORMAT_POINTER_GENERATION_V1),
                    "ownership_index_pointer_schema_version": (
                        OWNERSHIP_INDEX_POINTER_SCHEMA_VERSION
                    ),
                    "ownership_index_pointer_sha256": snapshot.pointer_sha256,
                    "ownership_index_generation_schema_version": (
                        OWNERSHIP_INDEX_GENERATION_SCHEMA_VERSION
                    ),
                    "ownership_index_generation_path": str(snapshot.generation_path),
                    "ownership_index_generation_sha256": snapshot.generation_sha256,
                    "ownership_index_signature_locator": {
                        "container_ref": snapshot.generation_sha256,
                        "member": "signature",
                    },
                    "ownership_index_pre_v3_history_status": (
                        self._pre_v3_history_status(snapshot.generation_sha256)
                    ),
                }
            )
        elif snapshot.source_format == "ephemeral_empty_v2":
            evidence.update(
                {
                    "ownership_evidence_schema_version": (OWNERSHIP_EVIDENCE_SCHEMA_VERSION_V3),
                    "ownership_index_format": "ephemeral_empty_v2",
                    "ownership_index_persisted": False,
                    "ownership_index_signature_path": None,
                    "ownership_index_pointer_schema_version": None,
                    "ownership_index_pointer_sha256": None,
                    "ownership_index_generation_schema_version": None,
                    "ownership_index_generation_path": None,
                    "ownership_index_generation_sha256": None,
                    "ownership_index_signature_locator": None,
                    "ownership_index_pre_v3_history_status": "no_pre_v3_pair",
                }
            )
        if tenant_id:
            normalized_tenant = _normal_tenant_id(tenant_id)
            normalized_cell = _normal_cell_id(cell_id)
            evidence["tenant_id"] = normalized_tenant
            if normalized_cell is not None:
                evidence["cell_id"] = normalized_cell
            evidence["tenant_artifact_count"] = sum(
                1
                for records in artifacts.values()
                if any(
                    _record_matches_owner(
                        record,
                        tenant_id=normalized_tenant,
                        cell_id=normalized_cell,
                    )
                    for record in records
                )
            )
        return evidence

    def _pre_v3_history_status(self, generation_sha256: str) -> str:
        """Classify only the pre-v3 history proven by the retained parent chain."""
        visited: set[str] = set()
        current_sha256 = generation_sha256
        while True:
            if current_sha256 in visited or _HEX_SHA256.fullmatch(current_sha256) is None:
                return "pre_v3_history_unresolved"
            visited.add(current_sha256)
            try:
                generation_bytes = self._generation_path(current_sha256).read_bytes()
                if _sha256_bytes(generation_bytes) != current_sha256:
                    return "pre_v3_history_unresolved"
                generation = _decode_json(
                    generation_bytes,
                    reject_duplicate_keys=True,
                )
                self._parse_generation(generation)
            except (
                OSError,
                UnicodeDecodeError,
                json.JSONDecodeError,
                TypeError,
                ValueError,
            ):
                return "pre_v3_history_unresolved"

            if generation["legacy_source"] is not None:
                return "current_pair_captured; earlier_overwritten_generations_unresolved"
            parent_sha256 = generation["parent_generation_sha256"]
            if parent_sha256 is None:
                return "no_pre_v3_pair"
            current_sha256 = parent_sha256

    def _load_payload(self) -> dict[str, Any]:
        return self._load_snapshot().payload

    def _load_snapshot(self) -> _OwnershipSnapshot:
        try:
            index_bytes = self.path.read_bytes()
        except FileNotFoundError:
            if self.signature_path.exists():
                raise ValueError("ownership_index_signature_invalid") from None
            return _OwnershipSnapshot(
                payload={
                    "schema_version": OWNERSHIP_INDEX_SCHEMA_VERSION,
                    "mode": OWNERSHIP_MODE_SHARED_CAS,
                    "artifacts": {},
                    "blob_readers": {},
                },
                signature=None,
                source_format="ephemeral_empty_v2",
                persisted=False,
            )
        try:
            raw = _decode_json(index_bytes, reject_duplicate_keys=True)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            raise ValueError("ownership_index_document_invalid") from None
        if isinstance(raw, dict) and raw.get("schema_version") == (
            OWNERSHIP_INDEX_POINTER_SCHEMA_VERSION
        ):
            return self._load_generation_snapshot(index_bytes)
        try:
            signature_bytes = self.signature_path.read_bytes()
        except FileNotFoundError:
            raise ValueError("ownership_index_signature_invalid") from None
        return self._parse_legacy_pair(index_bytes, signature_bytes)

    def _parse_legacy_pair(
        self,
        index_bytes: bytes,
        signature_bytes: bytes,
    ) -> _OwnershipSnapshot:
        try:
            raw = _decode_json(index_bytes, reject_duplicate_keys=True)
            signature = _decode_json(signature_bytes, reject_duplicate_keys=True)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            raise ValueError("ownership_index_signature_invalid") from None
        if not isinstance(raw, dict):
            raise ValueError("ownership_index_signature_invalid")
        schema_version = raw.get("schema_version")
        if "schema_version" not in raw:
            # Historical v1 signatures cover a canonical projection with defaults.
            raw["schema_version"] = _OWNERSHIP_INDEX_SCHEMA_VERSION_V1
            schema_version = _OWNERSHIP_INDEX_SCHEMA_VERSION_V1
        if schema_version == _OWNERSHIP_INDEX_SCHEMA_VERSION_V1:
            raw.setdefault("mode", OWNERSHIP_MODE_SHARED_CAS)
            raw.setdefault("artifacts", {})
            if "blob_readers" in raw or not set(raw).issubset(
                {"schema_version", "mode", "artifacts"}
            ):
                raise ValueError("ownership_index_signature_invalid")
        elif schema_version == OWNERSHIP_INDEX_SCHEMA_VERSION:
            required_v2_fields = {
                "schema_version",
                "mode",
                "artifacts",
                "blob_readers",
            }
            if not required_v2_fields.issubset(raw):
                raise ValueError("ownership_index_signature_invalid")
            if not isinstance(raw.get("blob_readers"), dict) or not set(raw).issubset(
                required_v2_fields
            ):
                raise ValueError("ownership_index_signature_invalid")
        else:
            raise ValueError("ownership_index_signature_invalid")
        if raw.get("mode") != OWNERSHIP_MODE_SHARED_CAS:
            raise ValueError("ownership_index_signature_invalid")
        try:
            _artifacts_mapping(raw)
            if schema_version == OWNERSHIP_INDEX_SCHEMA_VERSION:
                _blob_readers_mapping(raw)
        except (TypeError, ValueError):
            raise ValueError("ownership_index_signature_invalid") from None
        expected_signature = self._signature_payload(raw, digest=_digest_payload(raw))
        if not isinstance(signature, dict) or signature != expected_signature:
            raise ValueError("ownership_index_signature_invalid")
        return _OwnershipSnapshot(
            payload=raw,
            signature=signature,
            source_format=str(schema_version),
            persisted=True,
            legacy_index_bytes=index_bytes,
            legacy_signature_bytes=signature_bytes,
            payload_sha256=_digest_payload(raw),
            signature_sha256=_digest_payload(signature),
        )

    def _load_generation_snapshot(self, pointer_bytes: bytes) -> _OwnershipSnapshot:
        try:
            pointer = _decode_json(pointer_bytes, reject_duplicate_keys=True)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            raise ValueError("ownership_index_pointer_invalid") from None
        if (
            not isinstance(pointer, dict)
            or set(pointer) != {"schema_version", "mode", "generation_sha256"}
            or pointer.get("schema_version") != OWNERSHIP_INDEX_POINTER_SCHEMA_VERSION
            or pointer.get("mode") != OWNERSHIP_MODE_SHARED_CAS
            or not isinstance(pointer.get("generation_sha256"), str)
            or _HEX_SHA256.fullmatch(pointer["generation_sha256"]) is None
        ):
            raise ValueError("ownership_index_pointer_invalid")
        generation_sha256 = pointer["generation_sha256"]
        generation_path = self._generation_path(generation_sha256)
        try:
            generation_bytes = generation_path.read_bytes()
            if _sha256_bytes(generation_bytes) != generation_sha256:
                raise ValueError("ownership_index_generation_invalid")
            generation = _decode_json(generation_bytes, reject_duplicate_keys=True)
            snapshot = self._parse_generation(generation)
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ):
            raise ValueError("ownership_index_generation_invalid") from None
        return _OwnershipSnapshot(
            payload=snapshot.payload,
            signature=snapshot.signature,
            source_format=OWNERSHIP_INDEX_POINTER_SCHEMA_VERSION,
            persisted=True,
            generation_sha256=generation_sha256,
            generation_path=generation_path,
            pointer_sha256=_sha256_bytes(pointer_bytes),
            payload_sha256=snapshot.payload_sha256,
            signature_sha256=snapshot.signature_sha256,
        )

    def _parse_generation(self, generation: Any) -> _OwnershipSnapshot:
        expected_fields = {
            "schema_version",
            "mode",
            "parent_generation_sha256",
            "payload",
            "payload_sha256",
            "signature",
            "legacy_source",
        }
        if (
            not isinstance(generation, dict)
            or set(generation) != expected_fields
            or generation.get("schema_version") != OWNERSHIP_INDEX_GENERATION_SCHEMA_VERSION
            or generation.get("mode") != OWNERSHIP_MODE_SHARED_CAS
        ):
            raise ValueError("ownership_index_generation_invalid")
        parent_generation_sha256 = generation.get("parent_generation_sha256")
        if parent_generation_sha256 is not None and (
            not isinstance(parent_generation_sha256, str)
            or _HEX_SHA256.fullmatch(parent_generation_sha256) is None
        ):
            raise ValueError("ownership_index_generation_invalid")

        payload = generation.get("payload")
        self._validate_v2_payload(payload)
        payload_sha256 = generation.get("payload_sha256")
        if (
            not isinstance(payload_sha256, str)
            or _HEX_SHA256.fullmatch(payload_sha256) is None
            or _digest_payload(payload) != payload_sha256
        ):
            raise ValueError("ownership_index_generation_invalid")
        signature = generation.get("signature")
        expected_signature = self._signature_payload(payload, digest=payload_sha256)
        if not isinstance(signature, dict) or signature != expected_signature:
            raise ValueError("ownership_index_generation_invalid")

        legacy_source = generation.get("legacy_source")
        if legacy_source is not None:
            if parent_generation_sha256 is not None:
                raise ValueError("ownership_index_generation_invalid")
            legacy_snapshot = self._validate_legacy_source(legacy_source)
            self._validate_legacy_claims_preserved(legacy_snapshot.payload, payload)
        return _OwnershipSnapshot(
            payload=payload,
            signature=signature,
            source_format=OWNERSHIP_INDEX_GENERATION_SCHEMA_VERSION,
            persisted=True,
            payload_sha256=payload_sha256,
            signature_sha256=_digest_payload(signature),
        )

    def _validate_v2_payload(self, payload: Any) -> None:
        required_fields = {"schema_version", "mode", "artifacts", "blob_readers"}
        if (
            not isinstance(payload, dict)
            or set(payload) != required_fields
            or payload.get("schema_version") != OWNERSHIP_INDEX_SCHEMA_VERSION
            or payload.get("mode") != OWNERSHIP_MODE_SHARED_CAS
        ):
            raise ValueError("ownership_index_generation_invalid")
        try:
            _artifacts_mapping(payload)
            _blob_readers_mapping(payload)
        except (TypeError, ValueError):
            raise ValueError("ownership_index_generation_invalid") from None

    def _validate_legacy_source(self, legacy_source: Any) -> _OwnershipSnapshot:
        fields = {
            "index_bytes_base64",
            "index_bytes_sha256",
            "signature_bytes_base64",
            "signature_bytes_sha256",
        }
        if not isinstance(legacy_source, dict) or set(legacy_source) != fields:
            raise ValueError("ownership_index_generation_invalid")
        try:
            index_bytes = base64.b64decode(legacy_source["index_bytes_base64"], validate=True)
            signature_bytes = base64.b64decode(
                legacy_source["signature_bytes_base64"], validate=True
            )
        except (TypeError, ValueError):
            raise ValueError("ownership_index_generation_invalid") from None
        if (
            base64.b64encode(index_bytes).decode("ascii") != legacy_source["index_bytes_base64"]
            or base64.b64encode(signature_bytes).decode("ascii")
            != legacy_source["signature_bytes_base64"]
            or _sha256_bytes(index_bytes) != legacy_source["index_bytes_sha256"]
            or _sha256_bytes(signature_bytes) != legacy_source["signature_bytes_sha256"]
        ):
            raise ValueError("ownership_index_generation_invalid")
        return self._parse_legacy_pair(index_bytes, signature_bytes)

    @staticmethod
    def _validate_legacy_claims_preserved(
        legacy_payload: dict[str, Any],
        generation_payload: dict[str, Any],
    ) -> None:
        """Require migration to retain every row admitted by the exact old pair."""
        for field, get_mapping in (
            ("artifacts", _artifacts_mapping),
            ("blob_readers", _blob_readers_mapping),
        ):
            legacy_rows_by_id = get_mapping(legacy_payload)
            generation_rows_by_id = get_mapping(generation_payload)
            for artifact_id, legacy_rows in legacy_rows_by_id.items():
                remaining_rows = list(generation_rows_by_id.get(artifact_id, []))
                for legacy_row in legacy_rows:
                    try:
                        remaining_rows.remove(legacy_row)
                    except ValueError:
                        raise ValueError(
                            f"ownership_index_generation_{field}_history_lost"
                        ) from None

    def _write_payload(self, payload: dict[str, Any]) -> None:
        self._invalidate_claim_cache()
        previous = self._load_snapshot()
        next_payload = dict(payload)
        next_payload["schema_version"] = OWNERSHIP_INDEX_SCHEMA_VERSION
        next_payload["mode"] = OWNERSHIP_MODE_SHARED_CAS
        next_payload.setdefault("artifacts", {})
        next_payload.setdefault("blob_readers", {})
        self._validate_v2_payload(next_payload)

        payload_sha256 = _digest_payload(next_payload)
        signature = self._signature_payload(next_payload, digest=payload_sha256)
        if previous.source_format == OWNERSHIP_INDEX_POINTER_SCHEMA_VERSION:
            parent_generation_sha256 = previous.generation_sha256
            legacy_source: dict[str, str] | None = None
        elif previous.persisted:
            if previous.legacy_index_bytes is None or previous.legacy_signature_bytes is None:
                raise ValueError("ownership_index_signature_invalid")
            parent_generation_sha256 = None
            legacy_source = {
                "index_bytes_base64": base64.b64encode(previous.legacy_index_bytes).decode("ascii"),
                "index_bytes_sha256": _sha256_bytes(previous.legacy_index_bytes),
                "signature_bytes_base64": base64.b64encode(previous.legacy_signature_bytes).decode(
                    "ascii"
                ),
                "signature_bytes_sha256": _sha256_bytes(previous.legacy_signature_bytes),
            }
        else:
            parent_generation_sha256 = None
            legacy_source = None

        generation = {
            "schema_version": OWNERSHIP_INDEX_GENERATION_SCHEMA_VERSION,
            "mode": OWNERSHIP_MODE_SHARED_CAS,
            "parent_generation_sha256": parent_generation_sha256,
            "payload": next_payload,
            "payload_sha256": payload_sha256,
            "signature": signature,
            "legacy_source": legacy_source,
        }
        generation_bytes = _json_bytes(generation)
        generation_sha256 = _sha256_bytes(generation_bytes)
        generation_path = self._generation_path(generation_sha256)
        generations_directory = generation_path.parent
        ensure_directory_durable(generations_directory)
        created = AtomicFileWriter.write_once(
            generation_path,
            generation_bytes,
            durable_parent=True,
        )
        if not created:
            try:
                existing_bytes = generation_path.read_bytes()
            except OSError:
                raise ValueError("ownership_index_generation_invalid") from None
            if existing_bytes != generation_bytes:
                raise ValueError("ownership_index_generation_invalid")
            fsync_directory(generations_directory)

        pointer = {
            "schema_version": OWNERSHIP_INDEX_POINTER_SCHEMA_VERSION,
            "mode": OWNERSHIP_MODE_SHARED_CAS,
            "generation_sha256": generation_sha256,
        }
        pointer_bytes = _json_bytes(pointer)
        try:
            AtomicFileWriter.write_atomic(self.path, pointer_bytes, durable_parent=True)
        except AtomicFileDurabilityError as exc:
            if not exc.replaced:
                raise
            observed_generation_sha256: str | None = None
            try:
                observed = self._load_snapshot()
                observed_generation_sha256 = observed.generation_sha256
            except (OSError, TypeError, ValueError):
                pass
            raise OwnershipIndexPublicationIndeterminateError(
                generation_sha256,
                observed_generation_sha256,
            ) from exc
        self._invalidate_claim_cache()

    def _signature_payload(self, payload: dict[str, Any], *, digest: str) -> dict[str, Any]:
        index_schema_version = str(payload.get("schema_version") or OWNERSHIP_INDEX_SCHEMA_VERSION)
        if index_schema_version == _OWNERSHIP_INDEX_SCHEMA_VERSION_V1:
            signature_schema_version = _OWNERSHIP_SIGNATURE_SCHEMA_VERSION_V1
        elif index_schema_version == OWNERSHIP_INDEX_SCHEMA_VERSION:
            signature_schema_version = OWNERSHIP_SIGNATURE_SCHEMA_VERSION
        else:
            raise ValueError("ownership_index_signature_invalid")
        signed_statement = {
            "schema_version": signature_schema_version,
            "mode": OWNERSHIP_MODE_SHARED_CAS,
            "index_sha256": digest,
            "index_schema_version": index_schema_version,
            "algorithm": "sha256-local-integrity",
            "key_id": "local-cas-ownership-index",
        }
        signature = _digest_payload(signed_statement)
        return {**signed_statement, "signature": signature}


def _coerce_artifact_id(value: ArtifactID | str) -> ArtifactID:
    if isinstance(value, ArtifactID):
        return value
    return ArtifactID.model_validate(value)


def _artifacts_mapping(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return _validated_claim_mapping(
        payload.get("artifacts"),
        allow_manifest_views=True,
    )


def _blob_readers_mapping(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    if payload.get("schema_version") == _OWNERSHIP_INDEX_SCHEMA_VERSION_V1:
        return {}
    return _validated_claim_mapping(
        payload.get("blob_readers"),
        allow_manifest_views=False,
    )


def _validated_claim_mapping(
    raw: Any,
    *,
    allow_manifest_views: bool,
) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(raw, dict):
        raise ValueError("ownership_index_signature_invalid")
    result: dict[str, list[dict[str, Any]]] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            raise ValueError("ownership_index_signature_invalid")
        try:
            artifact_id = str(_coerce_artifact_id(key))
        except (TypeError, ValueError):
            raise ValueError("ownership_index_signature_invalid") from None
        if artifact_id != key or not isinstance(value, list) or not value:
            raise ValueError("ownership_index_signature_invalid")
        records: list[dict[str, Any]] = []
        for record in value:
            if not isinstance(record, dict):
                raise ValueError("ownership_index_signature_invalid")
            allowed_fields = {"tenant_id", "claimed_at", "cell_id", "writer"}
            if allow_manifest_views:
                allowed_fields.add("manifest_profile_sha256")
            if set(record).difference(allowed_fields):
                raise ValueError("ownership_index_signature_invalid")
            tenant_id = record.get("tenant_id")
            claimed_at = record.get("claimed_at")
            if (
                not isinstance(tenant_id, str)
                or not tenant_id.strip()
                or not isinstance(claimed_at, str)
                or not claimed_at.strip()
            ):
                raise ValueError("ownership_index_signature_invalid")
            if "cell_id" in record and (
                not isinstance(record["cell_id"], str) or not record["cell_id"].strip()
            ):
                raise ValueError("ownership_index_signature_invalid")
            if "writer" in record and (
                not isinstance(record["writer"], str) or not record["writer"].strip()
            ):
                raise ValueError("ownership_index_signature_invalid")
            if "manifest_profile_sha256" in record:
                try:
                    _validate_profile_sha256(record["manifest_profile_sha256"])
                except (TypeError, ValueError):
                    raise ValueError("ownership_index_signature_invalid") from None
            records.append(dict(record))
        result[artifact_id] = records
    return result


def _owner_label(tenant_id: object, cell_id: object | None = None) -> str:
    tenant = str(tenant_id or "").strip() or "<missing>"
    cell = _normal_cell_id(str(cell_id)) if cell_id is not None else None
    return f"{tenant}/{cell}" if cell else tenant


def _digest_payload(payload: Any) -> str:
    data = to_canonical_bytes(payload, CanonSpec(forbid_floats=False))
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return "sha256:" + digest.hexdigest()
    except OSError:
        return None


def _decode_json(data: bytes, *, reject_duplicate_keys: bool = False) -> Any:
    text = data.decode("utf-8")
    if not reject_duplicate_keys:
        return json.loads(text)

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise _DuplicateJSONKeyError("duplicate_json_key")
            value[key] = item
        return value

    return json.loads(text, object_pairs_hook=unique_object)


def _load_json_file(path: Path) -> Any:
    try:
        return _decode_json(path.read_bytes(), reject_duplicate_keys=True)
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    except _DuplicateJSONKeyError:
        raise ValueError("ownership_index_document_invalid") from None


__all__ = [
    "OWNERSHIP_EVIDENCE_SCHEMA_VERSION_V3",
    "OWNERSHIP_INDEX_FORMAT_POINTER_GENERATION_V1",
    "OWNERSHIP_INDEX_GENERATION_SCHEMA_VERSION",
    "OWNERSHIP_INDEX_POINTER_SCHEMA_VERSION",
    "OWNERSHIP_INDEX_SCHEMA_VERSION",
    "OWNERSHIP_MODE_SHARED_CAS",
    "OWNERSHIP_SIGNATURE_SCHEMA_VERSION",
    "ArtifactOwnershipError",
    "ArtifactOwnershipIndex",
    "OwnershipIndexPublicationIndeterminateError",
]
