"""Import/export helper operations for `FileSystemCAS`."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tarfile
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Protocol

from polisyos.common.serialization import fast_json_dumps, fast_json_dumps_bytes

from .ids import ArtifactID

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

_CAS_EXPORT_MEMBER_RE = re.compile(
    r"^artifacts/sha256/[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{64}\.(?:blob|manifest\.json|sig)$"
)
_CAS_EXPORT_LAYOUT = "artifacts/sha256/ab/cd/<hex>.(blob|manifest.json|sig)"
_CAS_EXPORT_OWNER = "polisyos.filesystem_cas.export"


class IntegrityVerificationReport(Protocol):
    """Minimal integrity report protocol used by import verification helpers."""

    ok: bool


@dataclass(frozen=True)
class ExportReport:
    """Summarize CAS bundle export results and missing dependencies."""

    exported_artifacts: int
    total_bytes: int
    output_path: Path
    missing_artifacts: list[str]
    missing_manifests: list[str]


@dataclass(frozen=True)
class ImportReport:
    """Summarize a CAS bundle import and integrity verification results."""

    imported_files: int
    imported_artifacts: int
    total_bytes: int
    source: Path
    skipped_entries: list[str]
    verification_failed: list[str]


def _member_digest(path: Path) -> tuple[str, int]:
    """Return the content binding for one exported member."""
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def _inventory_payload(
    *,
    exported: int,
    requested: int,
    members: dict[str, tuple[str, int]],
) -> dict[str, object]:
    """Build a deterministic export manifest with a closed member inventory."""
    ordered_members = sorted(members)
    return {
        "schema_version": "1.0",
        "cas_layout": _CAS_EXPORT_LAYOUT,
        "export_owner": _CAS_EXPORT_OWNER,
        "exported_artifacts": exported,
        "requested_artifacts": requested,
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


def _prepare_directory_export(target: Path) -> None:
    """Prepare only an owned export directory without deleting user files."""
    if target.is_symlink():
        raise ValueError(f"Export target must not be a symlink: {target}")
    if target.exists() and not target.is_dir():
        raise ValueError(f"Export target is not a directory: {target}")
    target.mkdir(parents=True, exist_ok=True)
    marker = target / "export_manifest.json"
    if marker.is_symlink():
        raise ValueError(f"Export manifest must not be a symlink: {marker}")
    if not marker.exists():
        if any(target.rglob("*")):
            raise ValueError("Refusing to reuse an unowned non-empty export directory")
        return

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
    assert previous_members is not None
    owned_paths = {
        target / Path(*PurePosixPath(member).parts) for member in previous_members
    }
    for member in previous_members:
        path = target / Path(*PurePosixPath(member).parts)
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Owned export member is missing: {member}")
        if previous_bindings[member] != _member_digest(path):
            raise ValueError(f"Owned export member changed: {member}")
    foreign_files = [
        path
        for path in target.rglob("*")
        if path.is_file() and path not in owned_paths and path != marker
    ]
    if foreign_files:
        raise ValueError("Refusing to remove unowned files from an export directory")
    for path in owned_paths | {marker}:
        if path.is_file() or path.is_symlink():
            path.unlink()


def _stage_member(
    *,
    staging_root: Path,
    safe_path: PurePosixPath,
    data: bytes,
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

    actual_sha, actual_size = hashlib.sha256(data).hexdigest(), len(data)
    expected_binding = bindings.get(member)
    if expected_binding is not None and expected_binding != (actual_sha, actual_size):
        artifact_id = artifact_id_from_member(member)
        if artifact_id is not None:
            binding_failures.add(str(artifact_id))

    destination = staging_root / Path(*safe_path.parts)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    total_bytes[0] += actual_size
    artifact_id = artifact_id_from_member(member)
    if artifact_id is not None:
        imported_artifacts.add(str(artifact_id))


def _publish_staged_members(
    *,
    staging_root: Path,
    root: Path,
    members: set[str],
) -> None:
    """Publish a verified closed member set from owned staging into the CAS root."""
    for member in sorted(members):
        safe_path = safe_member_path(member)
        if safe_path is None:
            raise ValueError(f"Unsafe staged member: {member}")
        source = staging_root / Path(*safe_path.parts)
        destination = root / Path(*safe_path.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)


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
    if file_name.endswith(".blob"):
        hex64 = file_name[: -len(".blob")]
    elif file_name.endswith(".manifest.json"):
        hex64 = file_name[: -len(".manifest.json")]
    elif file_name.endswith(".sig"):
        hex64 = file_name[: -len(".sig")]
    else:
        return None
    if not re.fullmatch(r"[0-9a-f]{64}", hex64):
        return None
    return ArtifactID.from_sha256_hex(hex64)


def export_subgraph(
    *,
    root: Path,
    get_paths: Callable[[ArtifactID], tuple[Path, Path]],
    get_sig_path: Callable[[ArtifactID], Path],
    artifact_ids: Iterable[ArtifactID],
    target: Path,
    compress: bool = True,
    include_manifests: bool = True,
) -> ExportReport:
    """Export a CAS subgraph to a tarball or directory using the stable ABI."""
    missing_artifacts: list[str] = []
    missing_manifests: list[str] = []
    total_bytes = 0
    exported = 0
    member_bindings: dict[str, tuple[str, int]] = {}

    sorted_ids = sorted(artifact_ids, key=lambda aid: aid.hex)
    if compress:
        archive_path = normalize_archive_path(target)
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive_path, "w:gz", format=tarfile.PAX_FORMAT) as tar:
            for artifact_id in sorted_ids:
                blob_path, manifest_path = get_paths(artifact_id)
                if not blob_path.exists():
                    missing_artifacts.append(str(artifact_id))
                    continue
                arc_blob = str(blob_path.relative_to(root))
                tar.add(blob_path, arcname=arc_blob, recursive=False)
                member_bindings[arc_blob] = _member_digest(blob_path)
                total_bytes += member_bindings[arc_blob][1]

                if include_manifests:
                    if not manifest_path.exists():
                        missing_manifests.append(str(artifact_id))
                    else:
                        arc_manifest = str(manifest_path.relative_to(root))
                        tar.add(manifest_path, arcname=arc_manifest, recursive=False)
                        member_bindings[arc_manifest] = _member_digest(manifest_path)
                        total_bytes += member_bindings[arc_manifest][1]
                sig_path = get_sig_path(artifact_id)
                if sig_path.exists():
                    arc_sig = str(sig_path.relative_to(root))
                    tar.add(sig_path, arcname=arc_sig, recursive=False)
                    member_bindings[arc_sig] = _member_digest(sig_path)
                    total_bytes += member_bindings[arc_sig][1]
                exported += 1

            meta_payload = _inventory_payload(
                exported=exported,
                requested=len(sorted_ids),
                members=member_bindings,
            )
            meta_bytes = fast_json_dumps_bytes(meta_payload, sort_keys=True)
            info = tarfile.TarInfo(name="export_manifest.json")
            info.size = len(meta_bytes)
            info.mtime = 0
            tar.addfile(info, BytesIO(meta_bytes))
            total_bytes += len(meta_bytes)
        output_path = archive_path
    else:
        _prepare_directory_export(target)
        for artifact_id in sorted_ids:
            blob_path, manifest_path = get_paths(artifact_id)
            if not blob_path.exists():
                missing_artifacts.append(str(artifact_id))
                continue
            dst_blob = target / blob_path.relative_to(root)
            dst_blob.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(blob_path, dst_blob)
            arc_blob = str(blob_path.relative_to(root))
            member_bindings[arc_blob] = _member_digest(dst_blob)
            total_bytes += member_bindings[arc_blob][1]

            if include_manifests:
                if not manifest_path.exists():
                    missing_manifests.append(str(artifact_id))
                else:
                    dst_manifest = target / manifest_path.relative_to(root)
                    dst_manifest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(manifest_path, dst_manifest)
                    arc_manifest = str(manifest_path.relative_to(root))
                    member_bindings[arc_manifest] = _member_digest(dst_manifest)
                    total_bytes += member_bindings[arc_manifest][1]
            sig_path = get_sig_path(artifact_id)
            if sig_path.exists():
                dst_sig = target / sig_path.relative_to(root)
                dst_sig.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(sig_path, dst_sig)
                arc_sig = str(sig_path.relative_to(root))
                member_bindings[arc_sig] = _member_digest(dst_sig)
                total_bytes += member_bindings[arc_sig][1]
            exported += 1

        meta_path = target / "export_manifest.json"
        meta_path.write_text(
            fast_json_dumps(
                _inventory_payload(
                    exported=exported,
                    requested=len(sorted_ids),
                    members=member_bindings,
                ),
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        total_bytes += meta_path.stat().st_size
        output_path = target

    return ExportReport(
        exported_artifacts=exported,
        total_bytes=total_bytes,
        output_path=output_path,
        missing_artifacts=missing_artifacts,
        missing_manifests=missing_manifests,
    )


def import_subgraph(
    *,
    root: Path,
    verify_artifact: Callable[[ArtifactID], IntegrityVerificationReport],
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
    root.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(prefix=".cas-import-", dir=root))

    try:
        inventory_data: bytes | None = None
        if source.is_dir():
            manifest_path = source / "export_manifest.json"
            if manifest_path.is_file() and not manifest_path.is_symlink():
                inventory_data = manifest_path.read_bytes()
        else:
            with tarfile.open(source, "r:*") as tar:
                manifest_members = [
                    member
                    for member in tar.getmembers()
                    if member.name == "export_manifest.json" and member.isfile()
                ]
                if len(manifest_members) > 1:
                    raise ValueError("Transfer contains duplicate export manifests")
                if manifest_members:
                    extracted = tar.extractfile(manifest_members[0])
                    if extracted is None:
                        raise ValueError("Transfer export manifest cannot be read")
                    with extracted:
                        inventory_data = extracted.read()

        allowed_members, bindings = _parse_inventory(
            inventory_data or b"{}",
            require_inventory=verify_integrity,
        )

        if source.is_dir():
            for path in sorted(source.rglob("*")):
                if path.is_symlink():
                    skipped_entries.append(str(path.relative_to(source)))
                    continue
                if not path.is_file():
                    continue
                relative = path.relative_to(source).as_posix()
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
                data = path.read_bytes()
                _stage_member(
                    staging_root=staging_root,
                    safe_path=safe_path,
                    data=data,
                    allowed_members=allowed_members,
                    bindings=bindings,
                    binding_failures=binding_failures,
                    seen_members=seen_members,
                    imported_artifacts=imported_artifacts,
                    total_bytes=total_bytes,
                )
                staged_members.add(member)
        else:
            with tarfile.open(source, "r:*") as tar:
                for member in tar.getmembers():
                    if member.name == "export_manifest.json":
                        continue
                    if not member.isfile():
                        skipped_entries.append(member.name)
                        continue
                    safe_path = safe_member_path(member.name)
                    if safe_path is None:
                        skipped_entries.append(member.name)
                        continue
                    member_name = safe_path.as_posix()
                    if allowed_members is not None and member_name not in allowed_members:
                        skipped_entries.append(member_name)
                        continue
                    extracted = tar.extractfile(member)
                    if extracted is None:
                        skipped_entries.append(member.name)
                        continue
                    with extracted:
                        data = extracted.read()
                    _stage_member(
                        staging_root=staging_root,
                        safe_path=safe_path,
                        data=data,
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
                    "Transfer is missing inventory members: "
                    + ", ".join(sorted(missing_members))
                )

        if verify_integrity:
            from ._integrity_ops import verify_filesystem_artifact

            for artifact_ref in sorted(imported_artifacts):
                artifact_id = ArtifactID.model_validate(artifact_ref)
                blob_path = staging_root / Path(*safe_member_path(
                    f"artifacts/sha256/{artifact_id.hex[:2]}/{artifact_id.hex[2:4]}"
                    f"/{artifact_id.hex}.blob"
                ).parts)
                manifest_path = staging_root / Path(*safe_member_path(
                    f"artifacts/sha256/{artifact_id.hex[:2]}/{artifact_id.hex[2:4]}"
                    f"/{artifact_id.hex}.manifest.json"
                ).parts)
                report = verify_filesystem_artifact(
                    artifact_id,
                    blob_path=blob_path,
                    manifest_path=manifest_path,
                )
                if not report.ok:
                    verification_failed.append(artifact_ref)

        verification_failed = sorted(set(verification_failed) | binding_failures)
        if verification_failed:
            return ImportReport(
                imported_files=0,
                imported_artifacts=len(imported_artifacts),
                total_bytes=total_bytes[0],
                source=source,
                skipped_entries=skipped_entries,
                verification_failed=verification_failed,
            )

        _publish_staged_members(
            staging_root=staging_root,
            root=root,
            members=staged_members,
        )
        return ImportReport(
            imported_files=len(staged_members),
            imported_artifacts=len(imported_artifacts),
            total_bytes=total_bytes[0],
            source=source,
            skipped_entries=skipped_entries,
            verification_failed=[],
        )
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
