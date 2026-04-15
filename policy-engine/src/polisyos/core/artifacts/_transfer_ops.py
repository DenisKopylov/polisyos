"""Import/export helper operations for `FileSystemCAS`."""
from __future__ import annotations

import re
import shutil
import tarfile
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
                total_bytes += blob_path.stat().st_size

                if include_manifests:
                    if not manifest_path.exists():
                        missing_manifests.append(str(artifact_id))
                    else:
                        arc_manifest = str(manifest_path.relative_to(root))
                        tar.add(manifest_path, arcname=arc_manifest, recursive=False)
                        total_bytes += manifest_path.stat().st_size
                sig_path = get_sig_path(artifact_id)
                if sig_path.exists():
                    arc_sig = str(sig_path.relative_to(root))
                    tar.add(sig_path, arcname=arc_sig, recursive=False)
                    total_bytes += sig_path.stat().st_size
                exported += 1

            meta_payload = {
                "schema_version": "1.0",
                "cas_layout": "artifacts/sha256/ab/cd/<hex>.(blob|manifest.json|sig)",
                "exported_artifacts": exported,
                "requested_artifacts": len(sorted_ids),
            }
            meta_bytes = fast_json_dumps_bytes(meta_payload, sort_keys=True)
            info = tarfile.TarInfo(name="export_manifest.json")
            info.size = len(meta_bytes)
            info.mtime = 0
            tar.addfile(info, BytesIO(meta_bytes))
            total_bytes += len(meta_bytes)
        output_path = archive_path
    else:
        target.mkdir(parents=True, exist_ok=True)
        for artifact_id in sorted_ids:
            blob_path, manifest_path = get_paths(artifact_id)
            if not blob_path.exists():
                missing_artifacts.append(str(artifact_id))
                continue
            dst_blob = target / blob_path.relative_to(root)
            dst_blob.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(blob_path, dst_blob)
            total_bytes += blob_path.stat().st_size

            if include_manifests:
                if not manifest_path.exists():
                    missing_manifests.append(str(artifact_id))
                else:
                    dst_manifest = target / manifest_path.relative_to(root)
                    dst_manifest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(manifest_path, dst_manifest)
                    total_bytes += manifest_path.stat().st_size
            sig_path = get_sig_path(artifact_id)
            if sig_path.exists():
                dst_sig = target / sig_path.relative_to(root)
                dst_sig.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(sig_path, dst_sig)
                total_bytes += sig_path.stat().st_size
            exported += 1

        meta_path = target / "export_manifest.json"
        meta_path.write_text(
            fast_json_dumps(
                {
                    "schema_version": "1.0",
                    "cas_layout": "artifacts/sha256/ab/cd/<hex>.(blob|manifest.json|sig)",
                    "exported_artifacts": exported,
                    "requested_artifacts": len(sorted_ids),
                },
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
    """Import a CAS export from a directory/tarball and optionally re-verify it."""
    imported_files = 0
    imported_artifacts: set[str] = set()
    total_bytes = 0
    skipped_entries: list[str] = []
    verification_failed: list[str] = []

    if source.is_dir():
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(source)
            safe_path = safe_member_path(str(rel))
            if safe_path is None:
                skipped_entries.append(str(rel))
                continue
            if safe_path == PurePosixPath("export_manifest.json"):
                continue
            dst = root / Path(*safe_path.parts)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dst)
            imported_files += 1
            total_bytes += path.stat().st_size
            artifact_id = artifact_id_from_member(str(safe_path))
            if artifact_id is not None:
                imported_artifacts.add(str(artifact_id))
    else:
        with tarfile.open(source, "r:*") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                safe_path = safe_member_path(member.name)
                if safe_path is None:
                    skipped_entries.append(member.name)
                    continue
                if safe_path == PurePosixPath("export_manifest.json"):
                    continue
                dst = root / Path(*safe_path.parts)
                dst.parent.mkdir(parents=True, exist_ok=True)
                extracted = tar.extractfile(member)
                if extracted is None:
                    skipped_entries.append(member.name)
                    continue
                with extracted, dst.open("wb") as handle:
                    shutil.copyfileobj(extracted, handle)
                imported_files += 1
                total_bytes += int(member.size)
                artifact_id = artifact_id_from_member(str(safe_path))
                if artifact_id is not None:
                    imported_artifacts.add(str(artifact_id))

    if verify_integrity:
        for artifact_ref in sorted(imported_artifacts):
            report = verify_artifact(ArtifactID.model_validate(artifact_ref))
            if not report.ok:
                verification_failed.append(artifact_ref)

    return ImportReport(
        imported_files=imported_files,
        imported_artifacts=len(imported_artifacts),
        total_bytes=total_bytes,
        source=source,
        skipped_entries=skipped_entries,
        verification_failed=verification_failed,
    )
