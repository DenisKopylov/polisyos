"""Public audit safe tar module API."""
from __future__ import annotations

import shutil
import tarfile
from pathlib import Path


class UnsafeArchiveError(RuntimeError):
    """Raised when tarball contains unsafe members."""


def safe_extract_tar(
    archive_path: Path,
    target_dir: Path,
    *,
    max_total_bytes: int = 2 * 1024 * 1024 * 1024,
) -> Path:
    """
    Safely extract tar archive into target_dir.

    Security controls:
    - reject absolute paths and path traversal (`..`)
    - reject symlink/hardlink/device entries
    - enforce uncompressed size limit
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive_path, "r:*") as tar:
        members = tar.getmembers()
        _validate_members(members, target_dir, max_total_bytes=max_total_bytes)
        try:
            # Python 3.12+: built-in hardened extraction that blocks path traversal and links.
            tar.extractall(target_dir, members=members, filter="data")
            return target_dir
        except TypeError:
            # Python <3.12 fallback: rely on explicit member validation above.
            pass

        for member in members:
            rel = Path(member.name)
            out_path = target_dir / rel
            if member.isdir():
                out_path.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                continue
            out_path.parent.mkdir(parents=True, exist_ok=True)
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            with extracted, out_path.open("wb") as handle:
                shutil.copyfileobj(extracted, handle)

    return target_dir


def _validate_members(
    members: list[tarfile.TarInfo],
    target_dir: Path,
    *,
    max_total_bytes: int,
) -> None:
    total_size = 0
    resolved_target = target_dir.resolve()
    for member in members:
        if member.islnk() or member.issym():
            raise UnsafeArchiveError(f"Archive contains link entry: {member.name}")
        if member.isdev():
            raise UnsafeArchiveError(f"Archive contains device entry: {member.name}")

        rel = Path(member.name)
        if rel.is_absolute():
            raise UnsafeArchiveError(f"Archive contains absolute path: {member.name}")
        if any(part in ("", "..") for part in rel.parts):
            raise UnsafeArchiveError(f"Archive contains unsafe path: {member.name}")

        total_size += int(member.size)
        if total_size > max_total_bytes:
            raise UnsafeArchiveError("Archive exceeds extraction size limit")

        resolved_out = (target_dir / rel).resolve()
        if resolved_target not in resolved_out.parents and resolved_out != resolved_target:
            raise UnsafeArchiveError(f"Path traversal detected: {member.name}")
