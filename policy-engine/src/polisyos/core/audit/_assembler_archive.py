"""Deterministic tarball creation, file checksums, index building, and JSON helpers."""

from __future__ import annotations

import gzip
import json
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactManifest
from polisyos.core.artifacts.signing import DetachedSignature
from polisyos.core.canon import streaming_hash

from .models import ExportOptions

__all__ = [
    "build_index",
    "compute_file_checksums",
    "create_deterministic_tarball",
    "normalize_archive_path",
    "write_checksums",
    "write_json",
]


# ---------------------------------------------------------------------------
# JSON serialisation helpers
# ---------------------------------------------------------------------------


def write_json(path: Path, payload: Any) -> None:
    """Write *payload* as pretty-printed JSON to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default),
        encoding="utf-8",
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python")
    return str(value)


# ---------------------------------------------------------------------------
# File checksums
# ---------------------------------------------------------------------------


def compute_file_checksums(
    root: Path,
    *,
    exclude: set[str],
) -> dict[str, str]:
    """SHA-256 every file under *root*, skipping paths in *exclude*."""
    checksums: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel in exclude:
            continue
        checksums[rel] = _sha256_path(path)
    return checksums


def _sha256_path(path: Path) -> str:
    with path.open("rb") as handle:
        return streaming_hash(iter(lambda: handle.read(1024 * 1024), b""))


def write_checksums(path: Path, checksums: dict[str, str]) -> None:
    """Write a BSD-style checksum manifest file."""
    lines = [f"{sha}  {rel}" for rel, sha in sorted(checksums.items(), key=lambda item: item[0])]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Deterministic tarball
# ---------------------------------------------------------------------------


def normalize_archive_path(path: Path) -> Path:
    """Ensure *path* ends with ``.polisyos-audit.tar.gz``."""
    suffixes = path.suffixes
    if len(suffixes) >= 3 and suffixes[-3:] == [".polisyos-audit", ".tar", ".gz"]:
        return path
    if len(suffixes) >= 2 and suffixes[-2:] == [".tar", ".gz"]:
        return path.with_name(path.name.replace(".tar.gz", ".polisyos-audit.tar.gz"))
    if path.suffix == ".tar":
        return path.with_suffix(".polisyos-audit.tar.gz")
    if path.suffix == ".gz":
        return path.with_name(path.name.replace(".gz", ".polisyos-audit.tar.gz"))
    return Path(f"{path}.polisyos-audit.tar.gz")


def create_deterministic_tarball(src_dir: Path, output_path: Path) -> Path:
    """Create a reproducible ``.tar.gz`` from *src_dir*."""
    archive_path = normalize_archive_path(output_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    with (
        archive_path.open("wb") as raw,
        gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw,
            mtime=0,
        ) as gz,
        tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar,
    ):
        for path in sorted(src_dir.rglob("*")):
            rel = path.relative_to(src_dir).as_posix()
            if path.is_symlink():
                continue
            info = tar.gettarinfo(str(path), arcname=rel)
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            if path.is_dir():
                info.mode = 0o755
                tar.addfile(info)
                continue
            if path.is_file():
                info.mode = 0o644
                with path.open("rb") as handle:
                    tar.addfile(info, handle)
    return archive_path


# ---------------------------------------------------------------------------
# Package index
# ---------------------------------------------------------------------------


def build_index(
    options: ExportOptions,
    *,
    run_id: str,
    run_status: str,
    artifact_ids: list[ArtifactID],
    signatures: dict[str, DetachedSignature],
    prov_json: dict[str, Any],
    checksums: dict[str, str],
    pkg_sig: dict[str, Any] | None,
    manifests: dict[str, ArtifactManifest],
    warnings: list[str],
    slsa: dict[str, Any],
    sbom: dict[str, Any],
) -> dict[str, Any]:
    """Build the top-level ``index.json`` for the audit package."""
    from ._assembler_slsa import find_decision_packet_id

    created_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    root = find_decision_packet_id(artifact_ids, manifests)
    files = [{"path": path, "sha256": sha} for path, sha in sorted(checksums.items())]
    return {
        "schema_version": "1.0.0",
        "package_format": "polisyos-audit-v1",
        "created_at": created_at,
        "created_by": {
            "tool": "polisyos",
            "command": f"audit export {run_id}",
        },
        "run_id": run_id,
        "run_status": run_status,
        "export_profile": options.profile.value,
        "provenance": {
            "format": "W3C-PROV-JSON",
            "path": "provenance/prov.json",
            "entity_count": len(prov_json.get("entity", {})),
            "activity_count": len(prov_json.get("activity", {})),
            "agent_count": len(prov_json.get("agent", {})),
        },
        "artifacts": {
            "total_count": len(artifact_ids),
            "signed_count": len(signatures),
            "unsigned_count": max(0, len(artifact_ids) - len(signatures)),
            "root_artifact_id": str(root) if root is not None else None,
        },
        "signatures": {
            "algorithm": "Ed25519",
            "package_checksum_signature": pkg_sig is not None,
        },
        "slsa": slsa,
        "sbom": sbom,
        "integrity": {
            "package_checksum_file": "verification/checksums.sha256",
            "package_checksum_signature": (
                "verification/checksums.sha256.sig" if pkg_sig is not None else None
            ),
            "algorithm": "SHA-256",
        },
        "warnings": sorted(set(warnings)),
        "files": files,
    }
