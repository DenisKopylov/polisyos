"""Import/export helper operations for `FileSystemCAS`."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tarfile
import tempfile
from contextlib import ExitStack, contextmanager, suppress
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, BinaryIO, Protocol

from polisyos.common.serialization import fast_json_dumps, fast_json_dumps_bytes

from ._atomic_write import AtomicFileDurabilityError, fsync_directory
from ._integrity_ops import ArtifactIntegrityError, validate_manifest_identity
from ._manifest_lifecycle import ManifestLifecycle
from .ids import ArtifactID
from .manifest import ArtifactManifest, ArtifactRef, artifact_reference_parts
from .signing import (
    SIGNATURE_ALGORITHM,
    SIGNATURE_FORMAT_VERSION,
    SIGNATURE_STATEMENT_TYPE,
    DetachedSignature,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator
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
    """Byte-only read capability required by the transfer staging owner."""

    def read(self, size: int = -1) -> bytes: ...


class CASMemberReceipt(Protocol):
    """Verified digest and size for one owner-streamed CAS member."""

    member: str
    sha256: str
    byte_size: int


class CASMemberStream(Protocol):
    """Bounded read surface for one CAS member while its owner lease is held."""

    size: int
    receipt: CASMemberReceipt

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


@dataclass(frozen=True)
class ImportReport:
    """Summarize a CAS bundle import and integrity verification results."""

    imported_files: int
    imported_artifacts: int
    total_bytes: int
    source: Path
    skipped_entries: list[str]
    verification_failed: list[str]
    imported_refs: tuple[ArtifactRef, ...] = ()


class ExportDurabilityError(AtomicFileDurabilityError):
    """Retain publication visibility and the accessible previous generation."""

    def __init__(self, message: str, *, replaced: bool, previous_generation: Path | None) -> None:
        super().__init__(message, replaced=replaced)
        self.previous_generation = previous_generation


def _regular_archive_mode(target: Path) -> int | None:
    """Admit the supplied final pathname itself, before any private staging."""
    try:
        metadata = target.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"Archive export target must be a regular file: {target}")
    return stat.S_IMODE(metadata.st_mode)


def _publish_archive_generation(staging: Path, target: Path) -> Path | None:
    """Atomically replace one complete file and retain its previous inode."""
    previous: Path | None = None
    if _regular_archive_mode(target) is not None:
        descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.previous-", dir=target.parent)
        os.close(descriptor)
        previous = Path(name)
        previous.unlink()
        os.link(target, previous, follow_symlinks=False)
        try:
            fsync_directory(target.parent)
        except OSError as error:
            raise ExportDurabilityError(
                f"Previous export retained at {previous}; publication has not occurred",
                replaced=False,
                previous_generation=previous,
            ) from error
    os.replace(staging, target)
    try:
        fsync_directory(target.parent)
    except OSError as error:
        raise ExportDurabilityError(
            f"Export was replaced; parent durability is uncertain; previous={previous}",
            replaced=True,
            previous_generation=previous,
        ) from error
    return previous


def _exchange_directory_generation(staging: Path, target: Path) -> None:
    """Use one supported native exchange; never fall back to a rename gap."""
    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "linux":
        exchange = getattr(library, "renameat2", None)
        if exchange is None:
            raise NotImplementedError("Atomic directory exchange is unavailable")
        exchange.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        exchange.restype = ctypes.c_int
        result = exchange(-100, os.fsencode(staging), -100, os.fsencode(target), 2)
    elif sys.platform == "darwin":
        exchange = getattr(library, "renamex_np", None)
        if exchange is None:
            raise NotImplementedError("Atomic directory exchange is unavailable")
        exchange.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        exchange.restype = ctypes.c_int
        result = exchange(os.fsencode(staging), os.fsencode(target), 2)
    else:
        raise NotImplementedError("Atomic directory exchange is unavailable")
    if result != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(target))


def _sync_directory_generation(staging: Path) -> None:
    """Sync the inventory and every staged directory before selecting the generation."""
    with (staging / "export_manifest.json").open("rb") as inventory:
        os.fsync(inventory.fileno())
    for directory, _directories, _files in os.walk(staging, topdown=False):
        fsync_directory(Path(directory))


@contextmanager
def _opened_archive(source: Path) -> Iterator[tarfile.TarFile]:
    """Keep the same archive inode open for metadata and member reads."""
    with tarfile.open(source, "r:*") as archive:
        yield archive


def _read_directory_inventory(descriptor: int) -> bytes | None:
    try:
        member = os.open(
            "export_manifest.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor
        )
    except FileNotFoundError:
        return None
    with os.fdopen(member, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Transfer inventory must be a regular file")
        return stream.read()


def _iter_directory_members(descriptor: int) -> Iterator[tuple[str, BinaryIO | None]]:
    """Open members relative to the pinned generation, even after its path is swapped."""
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
            member = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            with os.fdopen(member, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ValueError(f"Transfer member must be a regular file: {relative}")
                yield relative, stream


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


def _publish_directory_generation(staging_root: Path, target: Path) -> Path | None:
    """Select one complete generation atomically and preserve the previous directory."""
    if not target.exists() or not any(target.iterdir()):
        os.replace(staging_root, target)
        previous = None
    else:
        _exchange_directory_generation(staging_root, target)
        previous = staging_root
    try:
        fsync_directory(target.parent)
    except OSError as error:
        raise ExportDurabilityError(
            f"Export was replaced; parent durability is uncertain; previous={previous}",
            replaced=True,
            previous_generation=previous,
        ) from error
    return previous


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
    data: _TransferReadStream,
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


def export_subgraph(
    *,
    open_member: Callable[[ArtifactID | ArtifactRef, str], AbstractContextManager[CASMemberStream]],
    member_name: Callable[[ArtifactID | ArtifactRef, str], str],
    artifact_ids: Iterable[ArtifactID | ArtifactRef | str],
    target: Path,
    compress: bool = True,
    include_manifests: bool = True,
) -> ExportReport:
    """Export selected CAS members through their owner-held streaming reads."""
    missing_artifacts: list[str] = []
    missing_manifests: list[str] = []
    total_bytes = 0
    member_bindings: dict[str, tuple[str, int]] = {}
    previous_generation: Path | None = None

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
        staging_root: Path,
        request: ArtifactID | ArtifactRef,
        kind: str,
    ) -> int:
        name = member_name(request, kind)
        if name in added_members:
            return 0
        destination = staging_root / Path(*PurePosixPath(name).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open_member(request, kind) as stream, destination.open("wb") as sink:
            while payload := stream.read(1024 * 1024):
                sink.write(payload)
            sink.flush()
            os.fsync(sink.fileno())
        receipt = stream.receipt
        member_bindings[name] = (receipt.sha256.removeprefix("sha256:"), receipt.byte_size)
        added_members.add(name)
        return receipt.byte_size

    if compress:
        archive_path = normalize_archive_path(target)
        target_mode = _regular_archive_mode(archive_path)
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            prefix=f".{archive_path.name}.staging-", dir=archive_path.parent
        )
        os.close(descriptor)
        staging_archive = Path(name)
        try:
            with tarfile.open(staging_archive, "w:gz", format=tarfile.PAX_FORMAT) as tar:
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
            if target_mode is not None:
                staging_archive.chmod(target_mode)
            with staging_archive.open("rb") as stream:
                os.fsync(stream.fileno())
            previous_generation = _publish_archive_generation(staging_archive, archive_path)
        finally:
            staging_archive.unlink(missing_ok=True)
        output_path = archive_path
    else:
        _validate_directory_export(target)
        target_mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else None
        staging_root = Path(
            tempfile.mkdtemp(prefix=f".{target.name}.generation-", dir=target.parent)
        )
        try:
            for request in requests:
                artifact_id, profile_sha256, _ref = artifact_reference_parts(request)
                try:
                    total_bytes += copy_directory_member(staging_root, request, "blob")
                except FileNotFoundError:
                    missing_artifacts.append(str(artifact_id))
                    continue

                manifest_available = False
                if include_manifests:
                    try:
                        total_bytes += copy_directory_member(staging_root, request, "manifest")
                        manifest_available = True
                    except FileNotFoundError:
                        missing_manifests.append(str(artifact_id))
                with suppress(FileNotFoundError):
                    total_bytes += copy_directory_member(staging_root, request, "signature")
                exported_ids.add(str(artifact_id))
                if manifest_available:
                    exported_views.add((str(artifact_id), profile_sha256 or "default"))

            meta_path = staging_root / "export_manifest.json"
            meta_path.write_text(
                fast_json_dumps(
                    _inventory_payload(
                        exported=len(exported_ids),
                        requested=len(requested_ids),
                        exported_views=len(exported_views),
                        requested_views=len(requests),
                        members=member_bindings,
                    ),
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            total_bytes += meta_path.stat().st_size
            if target_mode is not None:
                staging_root.chmod(target_mode)
            _sync_directory_generation(staging_root)
            previous_generation = _publish_directory_generation(staging_root, target)
        except ExportDurabilityError as error:
            previous_generation = error.previous_generation
            raise
        finally:
            if staging_root.exists() and staging_root != previous_generation:
                shutil.rmtree(staging_root, ignore_errors=True)
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
    publish_staged: Callable[[Path, set[str], set[str]], tuple[ArtifactRef, ...]],
    source: Path,
    verify_integrity: bool = False,
) -> ImportReport:
    """Import a CAS export through an owned, verified staging generation."""
    imported_artifacts: set[str] = set()
    binding_failures: set[str] = set()
    skipped_entries: list[str] = []
    verification_failed: list[str] = []
    staged_members: set[str] = set()
    seen_members: set[str] = set()
    total_bytes = [0]
    source_handles = ExitStack()
    source_is_directory = source.is_dir()
    if root.is_symlink():
        raise ValueError("CAS root must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(prefix=".cas-import-", dir=root))

    try:
        inventory_data: bytes | None = None
        if source_is_directory:
            if source.is_symlink():
                raise ValueError("Transfer directory must not be a symlink")
            directory_descriptor = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            source_handles.callback(os.close, directory_descriptor)
            inventory_data = _read_directory_inventory(directory_descriptor)
        else:
            if not stat.S_ISREG(source.stat().st_mode):
                raise ValueError("Transfer archive must be a regular file")
            tar = source_handles.enter_context(_opened_archive(source))
            inventory_members = [
                member
                for member in tar.getmembers()
                if (
                    member.isfile()
                    and safe_member_path(member.name) == PurePosixPath("export_manifest.json")
                )
            ]
            if len(inventory_members) > 1:
                raise ValueError("Transfer contains duplicate export manifests")
            if inventory_members:
                extracted = tar.extractfile(inventory_members[0])
                if extracted is None:
                    raise ValueError("Transfer export manifest cannot be read")
                with extracted:
                    inventory_data = extracted.read()
        allowed_members, bindings = _parse_inventory(
            inventory_data or b"{}",
            require_inventory=verify_integrity,
        )

        if source_is_directory:
            for relative, stream in _iter_directory_members(directory_descriptor):
                if stream is None:
                    skipped_entries.append(relative)
                    continue
                safe_path = safe_member_path(relative)
                if safe_path is None:
                    skipped_entries.append(relative)
                    continue
                if safe_path == PurePosixPath("export_manifest.json"):
                    continue
                member = safe_path.as_posix()
                if allowed_members is not None and member not in allowed_members:
                    skipped_entries.append(member)
                    continue
                _stage_member(
                    staging_root=staging_root,
                    safe_path=safe_path,
                    data=stream,
                    allowed_members=allowed_members,
                    bindings=bindings,
                    binding_failures=binding_failures,
                    seen_members=seen_members,
                    imported_artifacts=imported_artifacts,
                    total_bytes=total_bytes,
                )
                staged_members.add(member)
        else:
            for tar_member in tar.getmembers():
                safe_path = safe_member_path(tar_member.name)
                if safe_path == PurePosixPath("export_manifest.json"):
                    continue
                if not tar_member.isfile():
                    skipped_entries.append(tar_member.name)
                    continue
                if safe_path is None:
                    skipped_entries.append(tar_member.name)
                    continue
                member_name = safe_path.as_posix()
                if allowed_members is not None and member_name not in allowed_members:
                    skipped_entries.append(member_name)
                    continue
                extracted = tar.extractfile(tar_member)
                if extracted is None:
                    skipped_entries.append(tar_member.name)
                    continue
                with extracted:
                    _stage_member(
                        staging_root=staging_root,
                        safe_path=safe_path,
                        data=extracted,
                        allowed_members=allowed_members,
                        bindings=bindings,
                        binding_failures=binding_failures,
                        seen_members=seen_members,
                        imported_artifacts=imported_artifacts,
                        total_bytes=total_bytes,
                    )
                staged_members.add(member_name)
        if allowed_members is not None:
            missing_members = allowed_members - staged_members
            if missing_members:
                raise ValueError(
                    "Transfer is missing inventory members: " + ", ".join(sorted(missing_members))
                )

        staged_by_artifact: dict[str, set[str]] = {}
        for member in staged_members:
            artifact_id = artifact_id_from_member(member)
            if artifact_id is not None:
                staged_by_artifact.setdefault(str(artifact_id), set()).add(member)

        if verify_integrity:
            for artifact_ref in sorted(imported_artifacts):
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
                    profile_sha256 = member_profile_sha256(manifest_member)
                    if profile_sha256 is None:
                        selected: ArtifactID | ArtifactRef = artifact_id
                    else:
                        manifest = ArtifactManifest.model_validate_json(
                            (
                                staging_root / Path(*PurePosixPath(manifest_member).parts)
                            ).read_bytes()
                        )
                        selected = ArtifactRef(
                            artifact_id=artifact_id,
                            kind=manifest.kind,
                            media_type=manifest.media_type,
                            manifest_profile_sha256=profile_sha256,
                        )
                    report = verify_artifact(selected, staging_root)
                    if not report.ok:
                        verification_failed.append(artifact_ref)
                        break

        verification_failed = sorted(set(verification_failed) | binding_failures)
        _validate_staged_signatures(staging_root, imported_artifacts, staged_members)
        if verification_failed:
            return ImportReport(
                imported_files=0,
                imported_artifacts=len(imported_artifacts),
                total_bytes=total_bytes[0],
                source=source,
                skipped_entries=skipped_entries,
                verification_failed=verification_failed,
            )

        imported_refs = publish_staged(staging_root, staged_members, imported_artifacts)
        return ImportReport(
            imported_files=len(staged_members),
            imported_artifacts=len(imported_artifacts),
            total_bytes=total_bytes[0],
            source=source,
            skipped_entries=skipped_entries,
            verification_failed=[],
            imported_refs=imported_refs,
        )
    finally:
        source_handles.close()
        shutil.rmtree(staging_root, ignore_errors=True)
