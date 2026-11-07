"""Import/export helper operations for `FileSystemCAS`."""

from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tarfile
import tempfile
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager, suppress
from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, BinaryIO, Literal, Protocol

from polisyos.common.serialization import fast_json_dumps_bytes

from ._atomic_write import fsync_directory
from ._export_admission import (
    DEFAULT_MAX_RETAINED_BYTES,
    DEFAULT_MAX_RETAINED_GENERATIONS,
    ExportResourceError,
    _BudgetedArchiveWriter,
    _export_target_admission,
    _ExportAdmission,
)
from ._integrity_ops import ArtifactIntegrityError, validate_manifest_identity
from ._manifest_lifecycle import ManifestLifecycle
from .ids import ArtifactID
from .manifest import ArtifactManifest, ArtifactRef, artifact_reference_parts
from .signing import (
    SIGNATURE_ALGORITHM,
    SIGNATURE_FORMAT_VERSION,
    SIGNATURE_STATEMENT_TYPE,
    DetachedSignature,
    SignatureVerificationResult,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from contextlib import AbstractContextManager

_CAS_EXPORT_MEMBER_RE = re.compile(
    r"^artifacts/sha256/[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{64}"
    r"(?:\.view\.[0-9a-f]{64})?\.(?:blob|manifest\.json|sig)$"
)
_CAS_EXPORT_LAYOUT = "artifacts/sha256/ab/cd/<hex>(.view.<profile>)?.(blob|manifest.json|sig)"
_CAS_EXPORT_OWNER = "polisyos.filesystem_cas.export"
_VIEW_MANIFEST_MEMBER_RE = re.compile(
    r"^(?P<artifact_id>[0-9a-f]{64})\.view\.(?P<profile>[0-9a-f]{64})\.manifest\.json$"
)


class IntegrityVerificationReport(Protocol):
    """Minimal integrity report protocol used by import verification helpers."""

    ok: bool


class _TransferReadStream(Protocol):
    """Byte-only source used to snapshot an incoming transfer member."""

    def read(self, size: int = -1) -> bytes: ...


@dataclass(frozen=True, slots=True)
class TransferMemberSnapshot:
    """Measured content identity for one member admitted from a transfer."""

    sha256: str
    byte_size: int
    metadata: bytes | None = None


@dataclass(frozen=True, slots=True)
class TransferAdmission:
    """Exact no-op refs and the unclaimed artifact set admitted for publication."""

    exact_refs: tuple[ArtifactRef, ...]
    pending_artifact_ids: frozenset[str]
    canonical_exact_refs: tuple[ArtifactRef, ...] = ()


@dataclass(frozen=True, slots=True)
class ImportPublication:
    """Refs returned by the owner transaction and its measured view disposition."""

    refs: tuple[ArtifactRef, ...]
    published_refs: tuple[ArtifactRef, ...]
    reused_refs: tuple[ArtifactRef, ...]
    basis: Literal["durable_owner_manifest_stage_intent", "exact_owned_view_admission"] = (
        "durable_owner_manifest_stage_intent"
    )
    signature_verified_refs: tuple[ArtifactRef, ...] = ()
    imported_member_count: int | None = None


def snapshot_transfer_member(member: str, stream: _TransferReadStream) -> TransferMemberSnapshot:
    """Hash actual incoming bytes while retaining only bounded metadata members."""
    metadata_member = not member.endswith(".blob")
    byte_limit = 8 * 1024 * 1024 if member.endswith(".manifest.json") else 1024 * 1024
    digest = hashlib.sha256()
    metadata = bytearray()
    byte_size = 0
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
        byte_size += len(chunk)
        if metadata_member:
            if byte_size > byte_limit:
                raise ArtifactIntegrityError("CAS import metadata exceeds its size bound")
            metadata.extend(chunk)
    return TransferMemberSnapshot(
        sha256=digest.hexdigest(),
        byte_size=byte_size,
        metadata=bytes(metadata) if metadata_member else None,
    )


def validate_transfer_signatures(members: dict[str, TransferMemberSnapshot]) -> None:
    """Verify each supplied signature envelope binds measured blob and manifest bytes."""
    for member, snapshot in sorted(members.items()):
        if not member.endswith(".sig"):
            continue
        artifact_id = artifact_id_from_member(member)
        if artifact_id is None or snapshot.metadata is None:
            raise ArtifactIntegrityError("CAS import signature member is unbound")
        manifest_member = member.removesuffix(".sig") + ".manifest.json"
        manifest = members.get(manifest_member)
        blob_member = (
            f"artifacts/sha256/{artifact_id.hex[:2]}/{artifact_id.hex[2:4]}/{artifact_id.hex}.blob"
        )
        blob = members.get(blob_member)
        if manifest is None or manifest.metadata is None or blob is None:
            raise ArtifactIntegrityError("CAS import signature targets a missing member")
        try:
            signature = DetachedSignature.model_validate_json(snapshot.metadata)
            manifest_sha = hashlib.sha256(manifest.metadata).hexdigest()
            if (
                signature.version != SIGNATURE_FORMAT_VERSION
                or signature.algorithm != SIGNATURE_ALGORITHM
                or signature.statement.type != SIGNATURE_STATEMENT_TYPE
                or signature.artifact_id != str(artifact_id)
                or signature.statement.blob_sha256 != blob.sha256
                or signature.statement.manifest_sha256 != manifest_sha
            ):
                raise ArtifactIntegrityError("CAS import signature binding mismatch")
        except (TypeError, ValueError) as exc:
            raise ArtifactIntegrityError("CAS import signature is invalid") from exc


@contextmanager
def _opened_archive(source: Path) -> Iterator[tarfile.TarFile]:
    """Keep one no-follow regular archive inode open for intake and staging reads."""
    source_stat = source.lstat()
    if not stat.S_ISREG(source_stat.st_mode):
        raise ValueError("Transfer archive source must be a regular file")
    try:
        descriptor = os.open(
            source,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
    except OSError as exc:
        if exc.errno in {errno.ELOOP, errno.ENXIO, errno.ENODEV, errno.EISDIR}:
            raise ValueError("Transfer archive source must be a regular file") from exc
        raise
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Transfer archive source must be a regular file")
        with tarfile.open(fileobj=stream, mode="r:*") as archive:
            yield archive


def _read_directory_inventory(descriptor: int) -> bytes | None:
    """Read the optional inventory relative to a pinned no-follow directory."""
    try:
        member = os.open(
            "export_manifest.json",
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
            dir_fd=descriptor,
        )
    except FileNotFoundError:
        return None
    with os.fdopen(member, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 8 * 1024 * 1024:
            raise ValueError("Transfer inventory must be a bounded regular file")
        return stream.read(8 * 1024 * 1024 + 1)


def _iter_directory_members(
    descriptor: int,
) -> Iterator[tuple[str, BinaryIO | None]]:
    """Read members relative to the pinned transfer root without following links."""
    for directory, directories, files, parent in os.fwalk(
        ".", topdown=True, follow_symlinks=False, dir_fd=descriptor
    ):
        directories.sort()
        for name in tuple(directories):
            metadata = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISDIR(metadata.st_mode):
                directories.remove(name)
                yield (PurePosixPath(directory) / name).as_posix(), None
        for name in sorted(files):
            relative = (PurePosixPath(directory) / name).as_posix()
            metadata = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISREG(metadata.st_mode):
                yield relative, None
                continue
            member = os.open(
                name,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
                dir_fd=parent,
            )
            with os.fdopen(member, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ValueError(f"Transfer member must be a regular file: {relative}")
                yield relative, stream


class CASMemberReceipt(Protocol):
    """Verified digest and size for one owner-streamed CAS member."""

    @property
    def member(self) -> str: ...

    @property
    def sha256(self) -> str: ...

    @property
    def byte_size(self) -> int: ...


class CASMemberStream(Protocol):
    """Bounded read surface for one CAS member while its owner lease is held."""

    @property
    def size(self) -> int: ...

    @property
    def receipt(self) -> CASMemberReceipt: ...

    def read(self, size: int = -1) -> bytes: ...


@dataclass(frozen=True)
class ExportReport:
    """Summarize CAS bundle export results and missing dependencies."""

    exported_artifacts: int
    total_bytes: int
    output_path: Path
    missing_artifacts: list[str]
    missing_manifests: list[str]
    previous_generation: Path | None = None
    retained_paths: tuple[Path, ...] = ()
    retained_bytes: int = 0
    max_retained_generations: int = DEFAULT_MAX_RETAINED_GENERATIONS
    max_retained_bytes: int = DEFAULT_MAX_RETAINED_BYTES


@dataclass(frozen=True)
class ImportReport:
    """Summarize received identities, persisted-view outcomes, and verification."""

    imported_files: int
    imported_artifacts: int
    total_bytes: int
    source: Path
    skipped_entries: list[str]
    verification_failed: list[str]
    imported_refs: tuple[ArtifactRef, ...] = ()
    received_artifact_ids: tuple[str, ...] = ()
    published_refs: tuple[ArtifactRef, ...] = ()
    reused_refs: tuple[ArtifactRef, ...] = ()
    integrity_verified_refs: tuple[ArtifactRef, ...] = ()
    integrity_verification_requested: bool = False
    disposition_basis: Literal[
        "received_members_rejected_before_admission",
        "exact_owned_view_admission",
        "durable_owner_manifest_stage_intent",
        "verification_failed_before_publication",
        "legacy_callback_refs_without_transaction_disposition",
    ] = "received_members_rejected_before_admission"
    signature_verification_requested: bool = False
    signature_verified_refs: tuple[ArtifactRef, ...] = ()


def _canonical_import_refs(
    refs: tuple[ArtifactRef, ...] | list[ArtifactRef],
) -> tuple[ArtifactRef, ...]:
    """Deduplicate selected views by a total order over their canonical profile identity."""
    by_identity: dict[tuple[str, str, str, str], ArtifactRef] = {}
    for ref in refs:
        key = (
            ref.artifact_id.hex,
            ref.kind,
            ref.media_type,
            ref.manifest_profile_sha256 or "",
        )
        by_identity[key] = ref
    return tuple(by_identity[key] for key in sorted(by_identity))


def _member_digest(path: Path) -> tuple[str, int]:
    """Return the content binding for one exported member."""
    digest = hashlib.sha256()
    byte_size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            byte_size += len(chunk)
    return digest.hexdigest(), byte_size


def _inventory_payload(
    *,
    exported: int,
    requested: int,
    exported_views: int,
    requested_views: int,
    members: dict[str, tuple[str, int]],
) -> dict[str, object]:
    """Build a deterministic export manifest with a closed member inventory."""
    ordered_members = sorted(members)
    return {
        "schema_version": "2.0",
        "cas_layout": _CAS_EXPORT_LAYOUT,
        "export_owner": _CAS_EXPORT_OWNER,
        "exported_artifacts": exported,
        "requested_artifacts": requested,
        "exported_views": exported_views,
        "requested_views": requested_views,
        "members": ordered_members,
        "member_bindings": [
            {
                "path": member,
                "sha256": members[member][0],
                "byte_size": members[member][1],
            }
            for member in ordered_members
        ],
    }


def _parse_inventory(
    data: bytes,
    *,
    require_inventory: bool,
) -> tuple[set[str] | None, dict[str, tuple[str, int]]]:
    """Parse and validate an export manifest before any CAS publication."""
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid export manifest JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Export manifest must be a JSON object")

    raw_members = payload.get("members")
    if raw_members is None:
        if require_inventory:
            raise ValueError("Export manifest is missing the exact members inventory")
        return None, {}
    if not isinstance(raw_members, list) or not all(
        isinstance(member, str) for member in raw_members
    ):
        raise ValueError("Export manifest members must be a list of paths")

    members = set(raw_members)
    if len(members) != len(raw_members):
        raise ValueError("Export manifest contains duplicate members")
    for member in members:
        safe_path = safe_member_path(member)
        if safe_path is None or safe_path == PurePosixPath("export_manifest.json"):
            raise ValueError(f"Export manifest contains unsafe member: {member}")

    raw_bindings = payload.get("member_bindings", [])
    if not isinstance(raw_bindings, list):
        raise ValueError("Export manifest member_bindings must be a list")
    bindings: dict[str, tuple[str, int]] = {}
    for raw_binding in raw_bindings:
        if not isinstance(raw_binding, dict):
            raise ValueError("Export manifest member binding must be an object")
        path = raw_binding.get("path")
        sha256 = raw_binding.get("sha256")
        byte_size = raw_binding.get("byte_size")
        if (
            not isinstance(path, str)
            or not isinstance(sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", sha256)
            or not isinstance(byte_size, int)
            or byte_size < 0
            or path not in members
            or path in bindings
        ):
            raise ValueError("Export manifest contains an invalid member binding")
        bindings[path] = (sha256, byte_size)
    if require_inventory and set(bindings) != members:
        raise ValueError("Export manifest bindings do not cover the members inventory")
    return members, bindings


def _validate_directory_export(target: Path) -> set[Path]:
    """Validate a reusable export directory and return its owned members."""
    if target.is_symlink():
        raise ValueError(f"Export target must not be a symlink: {target}")
    if target.exists() and not target.is_dir():
        raise ValueError(f"Export target is not a directory: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        return set()
    marker = target / "export_manifest.json"
    if marker.is_symlink():
        raise ValueError(f"Export manifest must not be a symlink: {marker}")
    if not marker.exists():
        if any(target.rglob("*")):
            raise ValueError("Refusing to reuse an unowned non-empty export directory")
        return set()

    try:
        marker_payload = json.loads(marker.read_text("utf-8"))
    except (OSError, UnicodeDecodeError, TypeError, ValueError) as exc:
        raise ValueError("Refusing to reuse an invalid export directory marker") from exc
    if (
        not isinstance(marker_payload, dict)
        or marker_payload.get("export_owner") != _CAS_EXPORT_OWNER
    ):
        raise ValueError("Refusing to reuse an unowned export directory")
    previous_members, previous_bindings = _parse_inventory(
        marker.read_bytes(),
        require_inventory=True,
    )
    if previous_members is None:
        raise ValueError("Owned export directory marker has no members inventory")
    owned_paths = {target / Path(*PurePosixPath(member).parts) for member in previous_members}
    for member in previous_members:
        path = target / Path(*PurePosixPath(member).parts)
        _reject_symlink_components(path, target, member=member)
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Owned export member is missing: {member}")
        if previous_bindings[member] != _member_digest(path):
            raise ValueError(f"Owned export member changed: {member}")
    owned_entries = owned_paths | {marker}
    for owned_path in tuple(owned_paths):
        parent = owned_path.parent
        while parent != target:
            owned_entries.add(parent)
            parent = parent.parent
    foreign_entries = [path for path in target.rglob("*") if path not in owned_entries]
    if foreign_entries:
        raise ValueError("Refusing to remove unowned files or entries from an export directory")
    return owned_paths | {marker}


def _prepare_directory_export(target: Path) -> None:
    """Prepare only an owned export directory without deleting user files."""
    owned_paths = _validate_directory_export(target)
    for path in owned_paths:
        if path.is_file() or path.is_symlink():
            path.unlink()


def _export_entry_identity(path: Path) -> tuple[int, int] | None:
    """Return no-follow entry identity, or no identity when it cannot be established."""
    try:
        metadata = path.lstat()
    except OSError:
        return None
    return metadata.st_dev, metadata.st_ino


class ImportSignatureVerificationError(ArtifactIntegrityError):
    """Refuse a required selected signature before any import publication."""

    def __init__(self, artifact_ref: ArtifactRef, result: SignatureVerificationResult) -> None:
        self.artifact_ref = artifact_ref
        self.result = result
        super().__init__(
            f"Required import signature {result.status.value} for {artifact_ref.artifact_id} "
            f"profile={artifact_ref.manifest_profile_sha256}: {result.message}"
        )


class ExportDurabilityError(OSError):
    """Expose publication visibility and retained paths without promising rollback.

    ``replaced`` is None when the selected inode cannot be established. A
    staging path names retained bytes, never a claim that they form a complete
    export. Retention and eventual reclamation belong to the caller.
    """

    def __init__(
        self,
        message: str,
        *,
        replaced: bool | None,
        previous_generation: Path | None = None,
        staging_path: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.replaced = replaced
        self.previous_generation = previous_generation
        self.staging_path = staging_path


def _regular_archive_mode(target: Path) -> int | None:
    """Admit the supplied final pathname itself, before any private staging."""
    try:
        metadata = target.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"Archive export target must be a regular file: {target}")
    return stat.S_IMODE(metadata.st_mode)


def _publish_archive_generation(
    staging: Path,
    target: Path,
    *,
    expected_identity: tuple[int, int] | None,
) -> Path | None:
    """Publish a descriptor-owned file, retaining the actually displaced archive."""
    return _publish_export_generation(
        staging, target, expected_identity=expected_identity, directory=False
    )


def _rename_export_generation(staging: Path, target: Path, *, exchange: bool) -> None:
    """Publish files or directories with one native exchange or no-replace rename."""
    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "linux":
        rename = getattr(library, "renameat2", None)
        if rename is None:
            raise NotImplementedError("Atomic export rename is unavailable")
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        result = rename(-100, os.fsencode(staging), -100, os.fsencode(target), 2 if exchange else 1)
    elif sys.platform == "darwin":
        rename = getattr(library, "renamex_np", None)
        if rename is None:
            raise NotImplementedError("Atomic export rename is unavailable")
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(os.fsencode(staging), os.fsencode(target), 2 if exchange else 4)
    else:
        raise NotImplementedError("Atomic export rename is unavailable")
    if result != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(target))


def _exchange_directory_generation(staging: Path, target: Path) -> None:
    """Exchange either regular export files or directories through the shared primitive."""
    _rename_export_generation(staging, target, exchange=True)


def _publish_export_generation(
    staging: Path,
    target: Path,
    *,
    expected_identity: tuple[int, int] | None,
    directory: bool,
) -> Path | None:
    """Select the owned inode once, preserving the actually displaced namespace entry."""
    if expected_identity is None or _export_entry_identity(staging) != expected_identity:
        raise ExportDurabilityError(
            "Export staging identity is not established; publication refused",
            replaced=False,
            staging_path=staging,
        )
    try:
        prior = target.lstat()
    except FileNotFoundError:
        prior = None
    valid_kind = stat.S_ISDIR if directory else stat.S_ISREG
    if prior is not None and not valid_kind(prior.st_mode):
        raise ExportDurabilityError(
            "Export destination has an unsupported entry kind; publication refused",
            replaced=False,
            staging_path=staging,
        )
    exchanged = prior is not None
    try:
        if exchanged:
            _exchange_directory_generation(staging, target)
        else:
            # Never remove an entry created by another writer after the missing check.
            _rename_export_generation(staging, target, exchange=False)
    except BaseException as error:
        selected = _export_entry_identity(target)
        staged = _export_entry_identity(staging)
        visible = (
            True
            if selected == expected_identity
            else False
            if staged == expected_identity
            else None
        )
        previous = (
            staging if exchanged and staged is not None and staged != expected_identity else None
        )
        if not isinstance(error, Exception):
            error.add_note(
                f"Export visibility={visible}; retained_stage={staging}; previous={previous}"
            )
            raise
        raise ExportDurabilityError(
            f"Export publication failed: {error}; retained_stage={staging}; previous={previous}",
            replaced=visible,
            previous_generation=previous,
            staging_path=staging,
        ) from error
    previous = staging if exchanged else None
    if _export_entry_identity(target) != expected_identity:
        raise ExportDurabilityError(
            "Published export inode is not the owned staged inode; visibility not established",
            replaced=None,
            previous_generation=previous,
            staging_path=staging,
        )
    if previous is not None:
        try:
            previous_mode = previous.lstat().st_mode
        except OSError as error:
            raise ExportDurabilityError(
                "Export selected but displaced entry cannot be established",
                replaced=True,
                previous_generation=previous,
                staging_path=staging,
            ) from error
        if not valid_kind(previous_mode):
            raise ExportDurabilityError(
                "Export selected but displaced entry has an untrusted kind",
                replaced=True,
                previous_generation=previous,
                staging_path=staging,
            )
    try:
        fsync_directory(target.parent)
    except OSError as error:
        raise ExportDurabilityError(
            f"Export was selected; parent durability is uncertain: {error}; previous={previous}",
            replaced=True,
            previous_generation=previous,
            staging_path=staging,
        ) from error
    return previous


def _sync_directory_generation(staging: Path) -> None:
    """Sync the inventory and every staged directory before selecting the generation."""
    with (staging / "export_manifest.json").open("rb") as inventory:
        os.fsync(inventory.fileno())
    for directory, _directories, _files in os.walk(staging, topdown=False):
        fsync_directory(Path(directory))


def _publish_directory_generation(
    staging_root: Path,
    target: Path,
    *,
    expected_identity: tuple[int, int] | None,
) -> Path | None:
    """Publish a complete directory without sweeping any retained or failed tree."""
    return _publish_export_generation(
        staging_root, target, expected_identity=expected_identity, directory=True
    )


def _reject_symlink_components(path: Path, root: Path, *, member: str) -> None:
    """Reject a member whose parent or final path crosses a symlink."""
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Member escapes owned root: {member}") from exc
    current = root
    if current.is_symlink():
        raise ValueError(f"Member root must not be a symlink: {member}")
    for component in relative.parts:
        current = current / component
        if current.is_symlink():
            raise ValueError(f"Member crosses a symlink: {member}")


def _stage_member(
    *,
    staging_root: Path,
    safe_path: PurePosixPath,
    data: BinaryIO,
    allowed_members: set[str] | None,
    bindings: dict[str, tuple[str, int]],
    binding_failures: set[str],
    seen_members: set[str],
    imported_artifacts: set[str],
    total_bytes: list[int],
) -> None:
    """Validate and stage one member without writing into the live CAS root."""
    member = safe_path.as_posix()
    if member in seen_members:
        raise ValueError(f"Duplicate transfer member: {member}")
    seen_members.add(member)
    if allowed_members is not None and member not in allowed_members:
        return

    destination = staging_root / Path(*safe_path.parts)
    _reject_symlink_components(destination, staging_root, member=member)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(destination, staging_root, member=member)
    descriptor = os.open(
        destination,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    digest = hashlib.sha256()
    actual_size = 0
    with os.fdopen(descriptor, "wb") as sink:
        while chunk := data.read(1024 * 1024):
            sink.write(chunk)
            digest.update(chunk)
            actual_size += len(chunk)
        sink.flush()
        os.fsync(sink.fileno())
    actual_sha = digest.hexdigest()
    expected_binding = bindings.get(member)
    if expected_binding is not None and expected_binding != (actual_sha, actual_size):
        artifact_id = artifact_id_from_member(member)
        if artifact_id is not None:
            binding_failures.add(str(artifact_id))
    total_bytes[0] += actual_size
    artifact_id = artifact_id_from_member(member)
    if artifact_id is not None:
        imported_artifacts.add(str(artifact_id))


def normalize_archive_path(path: Path) -> Path:
    """Normalize directory/tarball targets to the supported archive suffix."""
    suffixes = path.suffixes
    if len(suffixes) >= 2 and suffixes[-2:] == [".tar", ".gz"]:
        return path
    if path.suffix == ".tar":
        return path.with_suffix(".tar.gz")
    return Path(f"{path}.tar.gz")


def safe_member_path(name: str) -> PurePosixPath | None:
    """Return a normalized member path when it matches the supported CAS export ABI."""
    rel = PurePosixPath(name)
    if rel.is_absolute():
        return None
    if any(part in ("..", "") for part in rel.parts):
        return None
    if rel == PurePosixPath("export_manifest.json"):
        return rel
    if not _CAS_EXPORT_MEMBER_RE.fullmatch(rel.as_posix()):
        return None
    return rel


def artifact_id_from_member(path: str) -> ArtifactID | None:
    """Derive one artifact ID from a stable CAS bundle member path."""
    file_name = Path(path).name
    match = re.fullmatch(
        r"(?P<artifact_id>[0-9a-f]{64})(?:\.view\.[0-9a-f]{64})?"
        r"\.(?:blob|manifest\.json|sig)",
        file_name,
    )
    if match is None:
        return None
    return ArtifactID.from_sha256_hex(match.group("artifact_id"))


def member_profile_sha256(path: str) -> str | None:
    """Return the selected profile digest encoded by a secondary-view member."""
    match = _VIEW_MANIFEST_MEMBER_RE.fullmatch(Path(path).name)
    return f"sha256:{match.group('profile')}" if match is not None else None


def _validate_staged_manifest_views(
    staging_root: Path,
    artifact_id: ArtifactID,
    manifest_members: Iterable[str],
) -> None:
    """Validate every staged manifest against the shared blob and its path selector."""
    blob_path = (
        staging_root
        / "artifacts"
        / "sha256"
        / artifact_id.hex[:2]
        / artifact_id.hex[2:4]
        / f"{artifact_id.hex}.blob"
    )
    if not blob_path.is_file() or blob_path.is_symlink():
        raise ArtifactIntegrityError(f"Transfer is missing the immutable blob for {artifact_id}")
    blob_sha, blob_size = _member_digest(blob_path)
    if blob_sha != artifact_id.hex:
        raise ArtifactIntegrityError(f"Transfer blob hash mismatch for {artifact_id}")
    for member in manifest_members:
        manifest_path = staging_root / Path(*PurePosixPath(member).parts)
        if not manifest_path.is_file() or manifest_path.is_symlink():
            raise ArtifactIntegrityError(f"Transfer is missing manifest view {member}")
        manifest = ArtifactManifest.model_validate_json(manifest_path.read_bytes())
        validate_manifest_identity(artifact_id, manifest)
        if manifest.byte_size != blob_size:
            raise ArtifactIntegrityError(f"Transfer manifest byte size mismatch for {artifact_id}")
        profile_sha256 = member_profile_sha256(member)
        if profile_sha256 is not None and ManifestLifecycle.profile_sha256(manifest) != (
            profile_sha256
        ):
            raise ArtifactIntegrityError(f"Selected manifest profile mismatch for {artifact_id}")


def _validate_staged_signatures(
    staging_root: Path,
    imported_artifacts: set[str],
    staged_members: set[str],
) -> None:
    """Fail closed when an imported signature is malformed or misbound."""
    for sig_member in sorted(member for member in staged_members if member.endswith(".sig")):
        artifact_id = artifact_id_from_member(sig_member)
        if artifact_id is None or str(artifact_id) not in imported_artifacts:
            raise ValueError(f"Invalid signature member path: {sig_member}")
        sig_path = staging_root / Path(*PurePosixPath(sig_member).parts)
        signature_stem = sig_member.removesuffix(".sig")
        blob_member = (
            f"artifacts/sha256/{artifact_id.hex[:2]}/{artifact_id.hex[2:4]}/{artifact_id.hex}.blob"
        )
        manifest_member = f"{signature_stem}.manifest.json"
        blob_path = staging_root / Path(*PurePosixPath(blob_member).parts)
        manifest_path = staging_root / Path(*PurePosixPath(manifest_member).parts)
        try:
            signature = DetachedSignature.model_validate_json(sig_path.read_text("utf-8"))
            if signature.version != SIGNATURE_FORMAT_VERSION:
                raise ValueError(f"unsupported signature version: {signature.version}")
            if signature.algorithm != SIGNATURE_ALGORITHM:
                raise ValueError(f"unsupported signature algorithm: {signature.algorithm}")
            if signature.statement.type != SIGNATURE_STATEMENT_TYPE:
                raise ValueError(
                    f"unsupported signature statement type: {signature.statement.type}"
                )
            if signature.artifact_id != str(artifact_id):
                raise ValueError("signature artifact_id does not match member path")
            if not blob_path.is_file() or blob_path.is_symlink():
                raise ValueError("signature blob binding target is missing")
            if not manifest_path.is_file() or manifest_path.is_symlink():
                raise ValueError("signature manifest binding target is missing")
            blob_sha, _blob_size = _member_digest(blob_path)
            manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            if signature.statement.blob_sha256 != blob_sha:
                raise ValueError("signature blob_sha256 does not match staged blob")
            if signature.statement.manifest_sha256 != manifest_sha:
                raise ValueError("signature manifest_sha256 does not match staged manifest")
        except (OSError, UnicodeDecodeError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid detached signature for {artifact_id}: {exc}") from exc


@contextmanager
def _new_export_member(root_descriptor: int, name: str) -> Iterator[BinaryIO]:
    """Create a staged member exclusively below a pinned no-follow directory."""
    parts = PurePosixPath(name).parts
    if not parts or PurePosixPath(name).is_absolute() or ".." in parts:
        raise ValueError("Export member escapes its private stage")
    current = os.dup(root_descriptor)
    try:
        for part in parts[:-1]:
            with suppress(FileExistsError):
                os.mkdir(part, mode=0o700, dir_fd=current)
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            os.close(current)
            current = child
        descriptor = os.open(
            parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=current
        )
        with os.fdopen(descriptor, "wb") as stream:
            yield stream
    finally:
        os.close(current)


def export_subgraph(
    *,
    open_member: Callable[[ArtifactID | ArtifactRef, str], AbstractContextManager[CASMemberStream]],
    member_name: Callable[[ArtifactID | ArtifactRef, str], str],
    artifact_ids: Iterable[ArtifactID | ArtifactRef | str],
    target: Path,
    compress: bool = True,
    include_manifests: bool = True,
    max_retained_generations: int = DEFAULT_MAX_RETAINED_GENERATIONS,
    max_retained_bytes: int = DEFAULT_MAX_RETAINED_BYTES,
) -> ExportReport:
    """Admit finite target resources before consuming source IDs or creating a stage."""
    output = normalize_archive_path(target) if compress else target
    target_mode: int | None = None

    def validate_target() -> None:
        nonlocal target_mode
        if compress:
            target_mode = _regular_archive_mode(output)
        else:
            _validate_directory_export(output)
            target_mode = stat.S_IMODE(output.stat().st_mode) if output.exists() else None

    with _export_target_admission(
        output,
        max_retained_generations=max_retained_generations,
        max_retained_bytes=max_retained_bytes,
        validate_target=validate_target,
    ) as admission:
        try:
            report = _export_generation(
                open_member=open_member,
                member_name=member_name,
                artifact_ids=artifact_ids,
                target=output,
                compress=compress,
                include_manifests=include_manifests,
                _admission=admission,
                _target_mode=target_mode,
            )
            # After selection only the actually displaced locator can remain.
            admission.staging_path = report.previous_generation
            snapshot = admission.after_publication()
        except ExportResourceError as error:
            # Reconcile actual retained bytes after the owned stream has closed.
            snapshot = admission.snapshot()
            raise admission.refusal(
                error.reason,
                snapshot.paths,
                snapshot.byte_size,
                replaced=error.replaced,
            ) from error
        return replace(
            report,
            retained_paths=snapshot.paths,
            retained_bytes=snapshot.byte_size,
            max_retained_generations=max_retained_generations,
            max_retained_bytes=max_retained_bytes,
        )


def _export_generation(
    *,
    open_member: Callable[[ArtifactID | ArtifactRef, str], AbstractContextManager[CASMemberStream]],
    member_name: Callable[[ArtifactID | ArtifactRef, str], str],
    artifact_ids: Iterable[ArtifactID | ArtifactRef | str],
    target: Path,
    _admission: _ExportAdmission,
    _target_mode: int | None,
    compress: bool = True,
    include_manifests: bool = True,
) -> ExportReport:
    """Export selected CAS members through their owner-held streaming reads."""
    missing_artifacts: list[str] = []
    missing_manifests: list[str] = []
    total_bytes = 0
    previous_generation: Path | None = None
    member_bindings: dict[str, tuple[str, int]] = {}

    requests_by_key: dict[tuple[str, str], ArtifactID | ArtifactRef] = {}
    for value in artifact_ids:
        artifact_id, profile_sha256, ref = artifact_reference_parts(value)
        request = ref or artifact_id
        requests_by_key[(artifact_id.hex, profile_sha256 or "default")] = request
    requests = [
        requests_by_key[key] for key in sorted(requests_by_key, key=lambda item: (item[0], item[1]))
    ]
    requested_ids = {key[0] for key in requests_by_key}
    exported_ids: set[str] = set()
    exported_views: set[tuple[str, str]] = set()
    added_members: set[str] = set()

    def add_archive_member(
        tar: tarfile.TarFile,
        request: ArtifactID | ArtifactRef,
        kind: str,
    ) -> int:
        name = member_name(request, kind)
        if name in added_members:
            return 0
        with open_member(request, kind) as stream:
            info = tarfile.TarInfo(name=name)
            info.size = stream.size
            info.mtime = 0
            tar.addfile(info, stream)
        receipt = stream.receipt
        member_bindings[name] = (receipt.sha256.removeprefix("sha256:"), receipt.byte_size)
        added_members.add(name)
        return receipt.byte_size

    def copy_directory_member(
        staging_descriptor: int,
        request: ArtifactID | ArtifactRef,
        kind: str,
    ) -> int:
        name = member_name(request, kind)
        if name in added_members:
            return 0
        with (
            open_member(request, kind) as stream,
            _new_export_member(staging_descriptor, name) as sink,
        ):
            while payload := stream.read(1024 * 1024):
                _admission.consume(len(payload))
                sink.write(payload)
            sink.flush()
            os.fsync(sink.fileno())
        receipt = stream.receipt
        member_bindings[name] = (receipt.sha256.removeprefix("sha256:"), receipt.byte_size)
        added_members.add(name)
        return receipt.byte_size

    if compress:
        archive_path = normalize_archive_path(target)
        target_mode = _target_mode
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            prefix=f".{archive_path.name}.staging-", dir=archive_path.parent
        )
        staging_archive = Path(name)
        _admission.staging_path = staging_archive
        metadata = os.fstat(descriptor)
        archive_identity = metadata.st_dev, metadata.st_ino
        archive_replaced: bool | None = False
        try:
            with os.fdopen(descriptor, "w+b") as output:
                with tarfile.open(
                    staging_archive,
                    "w:gz",
                    fileobj=_BudgetedArchiveWriter(output, _admission),
                    format=tarfile.PAX_FORMAT,
                ) as tar:
                    for request in requests:
                        artifact_id, profile_sha256, _ref = artifact_reference_parts(request)
                        try:
                            total_bytes += add_archive_member(tar, request, "blob")
                        except FileNotFoundError:
                            missing_artifacts.append(str(artifact_id))
                            continue

                        manifest_available = False
                        if include_manifests:
                            try:
                                total_bytes += add_archive_member(tar, request, "manifest")
                                manifest_available = True
                            except FileNotFoundError:
                                missing_manifests.append(str(artifact_id))
                        with suppress(FileNotFoundError):
                            total_bytes += add_archive_member(tar, request, "signature")
                        exported_ids.add(str(artifact_id))
                        if manifest_available:
                            exported_views.add((str(artifact_id), profile_sha256 or "default"))

                    meta_payload = _inventory_payload(
                        exported=len(exported_ids),
                        requested=len(requested_ids),
                        exported_views=len(exported_views),
                        requested_views=len(requests),
                        members=member_bindings,
                    )
                    meta_bytes = fast_json_dumps_bytes(meta_payload, sort_keys=True)
                    info = tarfile.TarInfo(name="export_manifest.json")
                    info.size = len(meta_bytes)
                    info.mtime = 0
                    tar.addfile(info, BytesIO(meta_bytes))
                    total_bytes += len(meta_bytes)
                output.flush()
                if target_mode is not None:
                    os.fchmod(output.fileno(), target_mode)
                os.fsync(output.fileno())
                # Confirm the completed private entry before any target selection.
                fsync_directory(archive_path.parent)
                _admission.before_publication(staging_archive)
                archive_replaced = None
                previous_generation = _publish_archive_generation(
                    staging_archive, archive_path, expected_identity=archive_identity
                )
                archive_replaced = True
        except (ExportDurabilityError, ExportResourceError):
            raise
        except BaseException as error:
            if not isinstance(error, Exception):
                error.add_note(
                    f"Retained export stage={staging_archive}; publication={archive_replaced}"
                )
                raise
            raise ExportDurabilityError(
                f"Export failed: {error}; retained_stage={staging_archive}",
                replaced=archive_replaced,
                previous_generation=previous_generation,
                staging_path=staging_archive,
            ) from error
        # Pathname cleanup cannot bind an unlink atomically to our opened inode.
        # Preserve failed stages and displaced generations for explicit reclamation.
        output_path = archive_path
    else:
        target_mode = _target_mode
        staging_root = Path(
            tempfile.mkdtemp(prefix=f".{target.name}.generation-", dir=target.parent)
        )
        _admission.staging_path = staging_root
        staging_descriptor = os.open(staging_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        metadata = os.fstat(staging_descriptor)
        staging_identity = metadata.st_dev, metadata.st_ino
        publication_attempted = False
        try:
            for request in requests:
                artifact_id, profile_sha256, _ref = artifact_reference_parts(request)
                try:
                    total_bytes += copy_directory_member(staging_descriptor, request, "blob")
                except FileNotFoundError:
                    missing_artifacts.append(str(artifact_id))
                    continue

                manifest_available = False
                if include_manifests:
                    try:
                        total_bytes += copy_directory_member(
                            staging_descriptor, request, "manifest"
                        )
                        manifest_available = True
                    except FileNotFoundError:
                        missing_manifests.append(str(artifact_id))
                with suppress(FileNotFoundError):
                    total_bytes += copy_directory_member(staging_descriptor, request, "signature")
                exported_ids.add(str(artifact_id))
                if manifest_available:
                    exported_views.add((str(artifact_id), profile_sha256 or "default"))

            meta_bytes = fast_json_dumps_bytes(
                _inventory_payload(
                    exported=len(exported_ids),
                    requested=len(requested_ids),
                    exported_views=len(exported_views),
                    requested_views=len(requests),
                    members=member_bindings,
                ),
                sort_keys=True,
            )
            with _new_export_member(staging_descriptor, "export_manifest.json") as inventory:
                _admission.consume(len(meta_bytes))
                inventory.write(meta_bytes)
                inventory.flush()
                os.fsync(inventory.fileno())
            total_bytes += len(meta_bytes)
            if target_mode is not None:
                os.fchmod(staging_descriptor, target_mode)
            if _export_entry_identity(staging_root) != staging_identity:
                raise ValueError("Export staging directory identity changed")
            _sync_directory_generation(staging_root)
            # An unknown staging member is not part of a complete owned export.
            _validate_directory_export(staging_root)
            _admission.before_publication(staging_root)
            publication_attempted = True
            previous_generation = _publish_directory_generation(
                staging_root, target, expected_identity=staging_identity
            )
            _validate_directory_export(target)
        except (ExportDurabilityError, ExportResourceError):
            raise
        except BaseException as error:
            if not isinstance(error, Exception):
                error.add_note(
                    f"Retained export stage={staging_root}; publication={publication_attempted}"
                )
                raise
            raise ExportDurabilityError(
                f"Export failed: {error}; retained_stage={staging_root}",
                replaced=None if publication_attempted else False,
                previous_generation=previous_generation,
                staging_path=staging_root,
            ) from error
        finally:
            # Even an originally owned root can contain a late foreign child.
            # Retain failures for the caller; never recursively remove this tree.
            os.close(staging_descriptor)
        output_path = target

    return ExportReport(
        exported_artifacts=len(exported_ids),
        total_bytes=total_bytes,
        output_path=output_path,
        missing_artifacts=missing_artifacts,
        missing_manifests=missing_manifests,
        previous_generation=previous_generation,
    )


def import_subgraph(
    *,
    root: Path,
    verify_artifact: Callable[[ArtifactID | ArtifactRef, Path], IntegrityVerificationReport],
    publish_staged: Callable[
        [Path, set[str], set[str]], ImportPublication | tuple[ArtifactRef, ...]
    ],
    admit_members: Callable[
        [dict[str, TransferMemberSnapshot]],
        AbstractContextManager[TransferAdmission],
    ],
    source: Path,
    verify_integrity: bool = False,
    signature_verification_requested: bool = False,
) -> ImportReport:
    """Admit a content-bound transfer before staging or publishing CAS members."""
    imported_artifacts: set[str] = set()
    binding_failures: set[str] = set()
    skipped_entries: list[str] = []
    verification_failed: list[str] = []
    verified_refs: list[ArtifactRef] = []
    staged_members: set[str] = set()
    seen_members: set[str] = set()
    total_bytes = [0]
    source_handles = ExitStack()
    staging_root: Path | None = None
    if root.is_symlink():
        raise ValueError("CAS root must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)

    try:
        if source.is_symlink():
            raise ValueError("Transfer source must not be a symlink")
        source_is_directory = source.is_dir()
        directory_descriptor: int | None = None
        tar: tarfile.TarFile | None = None
        inventory_data: bytes | None = None
        if source_is_directory:
            directory_descriptor = os.open(
                source,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            )
            source_handles.callback(os.close, directory_descriptor)
            inventory_data = _read_directory_inventory(directory_descriptor)
        else:
            tar = source_handles.enter_context(_opened_archive(source))
            manifest_members = [
                member
                for member in tar.getmembers()
                if (
                    member.isfile()
                    and safe_member_path(member.name) == PurePosixPath("export_manifest.json")
                )
            ]
            if len(manifest_members) > 1:
                raise ValueError("Transfer contains duplicate export manifests")
            if manifest_members:
                info = manifest_members[0]
                if info.size > 8 * 1024 * 1024:
                    raise ValueError("Transfer inventory exceeds its size bound")
                extracted = tar.extractfile(info)
                if extracted is None:
                    raise ValueError("Transfer export manifest cannot be read")
                with extracted:
                    inventory_data = extracted.read(8 * 1024 * 1024 + 1)

        allowed_members, bindings = _parse_inventory(
            inventory_data or b"{}",
            require_inventory=verify_integrity,
        )

        def incoming_members() -> Iterator[tuple[PurePosixPath, _TransferReadStream]]:
            if source_is_directory:
                if directory_descriptor is None:
                    raise RuntimeError("Directory intake descriptor is unavailable")
                for relative, stream in _iter_directory_members(directory_descriptor):
                    safe_path = safe_member_path(relative)
                    if stream is None or safe_path is None:
                        if relative not in skipped_entries:
                            skipped_entries.append(relative)
                        continue
                    if safe_path == PurePosixPath("export_manifest.json"):
                        continue
                    if allowed_members is not None and safe_path.as_posix() not in allowed_members:
                        if relative not in skipped_entries:
                            skipped_entries.append(relative)
                        continue
                    yield safe_path, stream
                return

            if tar is None:
                raise RuntimeError("Archive intake handle is unavailable")
            for archive_member in tar.getmembers():
                safe_path = safe_member_path(archive_member.name)
                if safe_path == PurePosixPath("export_manifest.json"):
                    continue
                if not archive_member.isfile() or safe_path is None:
                    if archive_member.name not in skipped_entries:
                        skipped_entries.append(archive_member.name)
                    continue
                if allowed_members is not None and safe_path.as_posix() not in allowed_members:
                    if safe_path.as_posix() not in skipped_entries:
                        skipped_entries.append(safe_path.as_posix())
                    continue
                extracted = tar.extractfile(archive_member)
                if extracted is None:
                    if archive_member.name not in skipped_entries:
                        skipped_entries.append(archive_member.name)
                    continue
                with extracted:
                    yield safe_path, extracted

        intake: dict[str, TransferMemberSnapshot] = {}
        for safe_path, stream in incoming_members():
            member_name = safe_path.as_posix()
            if member_name in intake:
                raise ValueError(f"Duplicate transfer member: {member_name}")
            snapshot = snapshot_transfer_member(member_name, stream)
            intake[member_name] = snapshot
            artifact_id = artifact_id_from_member(member_name)
            if artifact_id is None:
                raise ValueError(f"Transfer member is not a CAS artifact: {member_name}")
            imported_artifacts.add(str(artifact_id))
            expected = bindings.get(member_name)
            if expected is not None and expected != (snapshot.sha256, snapshot.byte_size):
                binding_failures.add(str(artifact_id))
            if member_name.endswith(".blob") and snapshot.sha256 != artifact_id.hex:
                binding_failures.add(str(artifact_id))

        if allowed_members is not None:
            missing_members = allowed_members - set(intake)
            if missing_members:
                raise ValueError(
                    "Transfer is missing inventory members: " + ", ".join(sorted(missing_members))
                )

        intake_total_bytes = sum(snapshot.byte_size for snapshot in intake.values())
        validate_transfer_signatures(intake)
        if binding_failures:
            return ImportReport(
                imported_files=0,
                imported_artifacts=len(imported_artifacts),
                total_bytes=intake_total_bytes,
                source=source,
                skipped_entries=skipped_entries,
                verification_failed=sorted(binding_failures),
                received_artifact_ids=tuple(sorted(imported_artifacts)),
                integrity_verification_requested=verify_integrity,
                signature_verification_requested=signature_verification_requested,
                disposition_basis="received_members_rejected_before_admission",
            )

        admission = source_handles.enter_context(admit_members(intake))
        canonical_exact_refs = admission.canonical_exact_refs or admission.exact_refs
        if not admission.pending_artifact_ids and not signature_verification_requested:
            exact_failures: set[str] = set()
            if verify_integrity:
                for ref, canonical_ref in zip(
                    admission.exact_refs, canonical_exact_refs, strict=True
                ):
                    verification = verify_artifact(ref, root)
                    if verification.ok:
                        verified_refs.append(canonical_ref)
                    else:
                        exact_failures.add(str(ref.artifact_id))
            if exact_failures:
                return ImportReport(
                    imported_files=0,
                    imported_artifacts=len(imported_artifacts),
                    total_bytes=intake_total_bytes,
                    source=source,
                    skipped_entries=skipped_entries,
                    verification_failed=sorted(exact_failures),
                    received_artifact_ids=tuple(sorted(imported_artifacts)),
                    reused_refs=_canonical_import_refs(canonical_exact_refs),
                    integrity_verified_refs=_canonical_import_refs(verified_refs),
                    integrity_verification_requested=verify_integrity,
                    signature_verification_requested=signature_verification_requested,
                    disposition_basis="verification_failed_before_publication",
                )
            return ImportReport(
                imported_files=0,
                imported_artifacts=len(imported_artifacts),
                total_bytes=intake_total_bytes,
                source=source,
                skipped_entries=skipped_entries,
                verification_failed=[],
                imported_refs=admission.exact_refs,
                received_artifact_ids=tuple(sorted(imported_artifacts)),
                reused_refs=_canonical_import_refs(canonical_exact_refs),
                integrity_verified_refs=_canonical_import_refs(verified_refs),
                integrity_verification_requested=verify_integrity,
                signature_verification_requested=signature_verification_requested,
                disposition_basis="exact_owned_view_admission",
            )

        staging_root = Path(tempfile.mkdtemp(prefix=".cas-import-", dir=root))
        snapshot_bindings = {
            name: (snapshot.sha256, snapshot.byte_size) for name, snapshot in intake.items()
        }
        staged_artifacts: set[str] = set()
        for safe_path, stream in incoming_members():
            member_name = safe_path.as_posix()
            artifact_id = artifact_id_from_member(member_name)
            if artifact_id is None or (
                not signature_verification_requested
                and str(artifact_id) not in admission.pending_artifact_ids
            ):
                continue
            _stage_member(
                staging_root=staging_root,
                safe_path=safe_path,
                data=stream,
                allowed_members=allowed_members,
                bindings=snapshot_bindings,
                binding_failures=binding_failures,
                seen_members=seen_members,
                imported_artifacts=staged_artifacts,
                total_bytes=total_bytes,
            )
            staged_members.add(member_name)

        expected_staged = {
            member
            for member in intake
            if signature_verification_requested
            or str(artifact_id_from_member(member)) in admission.pending_artifact_ids
        }
        if expected_staged != staged_members:
            raise ValueError("Transfer changed its admitted member set before staging")

        staged_by_artifact: dict[str, set[str]] = {}
        for member in staged_members:
            artifact_id = artifact_id_from_member(member)
            if artifact_id is not None:
                staged_by_artifact.setdefault(str(artifact_id), set()).add(member)

        if verify_integrity:
            for artifact_ref in sorted(staged_artifacts):
                artifact_id = ArtifactID.model_validate(artifact_ref)
                artifact_members = staged_by_artifact.get(artifact_ref, set())
                blob_member = (
                    f"artifacts/sha256/{artifact_id.hex[:2]}/{artifact_id.hex[2:4]}"
                    f"/{artifact_id.hex}.blob"
                )
                manifest_members = sorted(
                    member for member in artifact_members if member.endswith(".manifest.json")
                )
                if blob_member not in artifact_members or not manifest_members:
                    raise ValueError(
                        f"Transfer must contain a blob and at least one manifest view for "
                        f"{artifact_id}"
                    )
                try:
                    _validate_staged_manifest_views(
                        staging_root,
                        artifact_id,
                        manifest_members,
                    )
                except (OSError, ValueError, TypeError):
                    verification_failed.append(artifact_ref)
                    continue
                for manifest_member in manifest_members:
                    encoded_profile = member_profile_sha256(manifest_member)
                    manifest = ArtifactManifest.model_validate_json(
                        (staging_root / Path(*PurePosixPath(manifest_member).parts)).read_bytes()
                    )
                    profile_sha256 = ManifestLifecycle.profile_sha256(manifest)
                    selected: ArtifactID | ArtifactRef
                    if encoded_profile is None:
                        selected = artifact_id
                    else:
                        selected = ArtifactRef(
                            artifact_id=artifact_id,
                            kind=manifest.kind,
                            media_type=manifest.media_type,
                            manifest_profile_sha256=profile_sha256,
                        )
                    report = verify_artifact(selected, staging_root)
                    if report.ok:
                        verified_refs.append(
                            ArtifactRef(
                                artifact_id=artifact_id,
                                kind=manifest.kind,
                                media_type=manifest.media_type,
                                manifest_profile_sha256=profile_sha256,
                            )
                        )
                    else:
                        verification_failed.append(artifact_ref)

        if verify_integrity:
            for ref, canonical_ref in zip(admission.exact_refs, canonical_exact_refs, strict=True):
                verification = verify_artifact(ref, root)
                if verification.ok:
                    verified_refs.append(canonical_ref)
                else:
                    verification_failed.append(str(ref.artifact_id))

        verification_failed = sorted(set(verification_failed) | binding_failures)
        _validate_staged_signatures(staging_root, staged_artifacts, staged_members)
        if verification_failed:
            return ImportReport(
                imported_files=0,
                imported_artifacts=len(imported_artifacts),
                total_bytes=intake_total_bytes,
                source=source,
                skipped_entries=skipped_entries,
                verification_failed=verification_failed,
                received_artifact_ids=tuple(sorted(imported_artifacts)),
                reused_refs=_canonical_import_refs(canonical_exact_refs),
                integrity_verified_refs=_canonical_import_refs(verified_refs),
                integrity_verification_requested=verify_integrity,
                signature_verification_requested=signature_verification_requested,
                disposition_basis="verification_failed_before_publication",
            )

        publication = publish_staged(staging_root, staged_members, staged_artifacts)
        if isinstance(publication, ImportPublication):
            callback_refs = publication.refs
            published_refs = publication.published_refs
            reused_refs = _canonical_import_refs(
                list(canonical_exact_refs) + list(publication.reused_refs)
            )
            disposition_basis: Literal[
                "durable_owner_manifest_stage_intent",
                "exact_owned_view_admission",
                "legacy_callback_refs_without_transaction_disposition",
            ] = publication.basis
        else:
            callback_refs = publication
            published_refs = ()
            reused_refs = _canonical_import_refs(canonical_exact_refs)
            disposition_basis = "legacy_callback_refs_without_transaction_disposition"
        imported_refs = admission.exact_refs + callback_refs
        return ImportReport(
            imported_files=(
                publication.imported_member_count
                if isinstance(publication, ImportPublication)
                and publication.imported_member_count is not None
                else len(staged_members)
            ),
            imported_artifacts=len(imported_artifacts),
            total_bytes=intake_total_bytes,
            source=source,
            skipped_entries=skipped_entries,
            verification_failed=[],
            imported_refs=imported_refs,
            received_artifact_ids=tuple(sorted(imported_artifacts)),
            published_refs=_canonical_import_refs(published_refs),
            reused_refs=reused_refs,
            integrity_verified_refs=_canonical_import_refs(verified_refs),
            integrity_verification_requested=verify_integrity,
            signature_verification_requested=signature_verification_requested,
            signature_verified_refs=(
                publication.signature_verified_refs
                if isinstance(publication, ImportPublication)
                else ()
            ),
            disposition_basis=disposition_basis,
        )
    finally:
        source_handles.close()
        if staging_root is not None:
            shutil.rmtree(staging_root, ignore_errors=True)
