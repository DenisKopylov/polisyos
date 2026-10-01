from __future__ import annotations

import os
import platform
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    EnvInfo,
    GitInfo,
    InputRef,
    ProducerInfo,
    SchemaInfo,
    artifact_reference_parts,
)
from polisyos.core.artifacts.signing import DetachedSignature
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec


def put_json_artifact(
    store: FileSystemCAS,
    payload: Any,
    *,
    kind: str,
    inputs: list[InputRef] | None = None,
    schema_version: str = "1.0",
    forbid_floats: bool = False,
):
    return store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=kind, version=schema_version),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=forbid_floats),
    )


def overwrite_signature_sidecar_for_test(
    store: FileSystemCAS,
    artifact_ref: ArtifactID | ArtifactRef | str,
    replacement: DetachedSignature,
    *,
    tmp_root: Path,
) -> None:
    """Model out-of-band signature-file corruption inside one test's scratch root.

    Production CAS signature writes are immutable. This helper represents bytes
    changed outside that API, while requiring the selected CAS view to remain
    inside the current test's temporary directory.
    """
    tmp_root = Path(tmp_root)
    if tmp_root.is_symlink():
        raise ValueError("test tmp_root must not be a symlink")
    resolved_tmp_root = tmp_root.resolve(strict=True)
    if not resolved_tmp_root.is_dir():
        raise ValueError("test tmp_root must be a directory")

    cas_root = Path(store.root)
    resolved_cas_root = cas_root.resolve(strict=True)
    try:
        relative_cas_root = resolved_cas_root.relative_to(resolved_tmp_root)
    except ValueError as exc:
        raise ValueError("CAS root must be inside the supplied test tmp_root") from exc
    if not relative_cas_root.parts:
        raise ValueError("test tmp_root must contain a child CAS root")

    current = resolved_tmp_root
    for part in relative_cas_root.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("CAS root path must not contain symlinks")
        if not current.is_dir():
            raise ValueError("CAS root must be an existing directory below test tmp_root")

    artifact_id, profile_sha256, _validated_ref = artifact_reference_parts(artifact_ref)
    if replacement.artifact_id != str(artifact_id):
        raise ValueError("replacement signature artifact_id does not match selected artifact")
    signature_path = Path(store._sig_path(artifact_id, profile_sha256))
    try:
        relative_signature_path = signature_path.relative_to(resolved_cas_root)
    except ValueError as exc:
        raise ValueError("selected signature path must be inside the CAS root") from exc
    if not relative_signature_path.parts or any(
        part in {".", ".."} for part in relative_signature_path.parts
    ):
        raise ValueError("selected signature path must be a CAS descendant")

    current = resolved_cas_root
    signature_stat: os.stat_result | None = None
    for index, part in enumerate(relative_signature_path.parts):
        current = current / part
        try:
            entry_stat = current.lstat()
        except FileNotFoundError as exc:
            raise ValueError("selected signature sidecar must already exist") from exc
        if stat.S_ISLNK(entry_stat.st_mode):
            raise ValueError("selected signature path must not contain symlinks")
        if index < len(relative_signature_path.parts) - 1:
            if not stat.S_ISDIR(entry_stat.st_mode):
                raise ValueError("selected signature parent must be a directory")
        else:
            signature_stat = entry_stat
    if signature_stat is None or not stat.S_ISREG(signature_stat.st_mode):
        raise ValueError("selected signature sidecar must be a regular file")

    replacement_bytes = replacement.model_dump_json(
        by_alias=True,
        exclude_none=True,
        indent=2,
    ).encode("utf-8")
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    close_on_exec = getattr(os, "O_CLOEXEC", 0)
    read_descriptor = os.open(
        signature_path,
        os.O_RDONLY | no_follow | close_on_exec,
    )
    write_descriptor: int | None = None
    write_descriptor_matches_selected_file = False
    original_mode: int | None = None
    mode_temporarily_changed = False
    original_bytes = b""
    try:
        read_stat = os.fstat(read_descriptor)
        if (
            not stat.S_ISREG(read_stat.st_mode)
            or read_stat.st_dev != signature_stat.st_dev
            or read_stat.st_ino != signature_stat.st_ino
        ):
            raise ValueError("selected signature sidecar identity changed before opening")
        original_mode = stat.S_IMODE(read_stat.st_mode)
        original_parts: list[bytes] = []
        while chunk := os.read(read_descriptor, 65536):
            original_parts.append(chunk)
        original_bytes = b"".join(original_parts)
        if original_bytes == replacement_bytes:
            raise ValueError("replacement must change the persisted signature bytes")

        if not original_mode & stat.S_IWUSR:
            os.fchmod(read_descriptor, original_mode | stat.S_IWUSR)
            mode_temporarily_changed = True
        write_descriptor = os.open(
            signature_path,
            os.O_RDWR | no_follow | close_on_exec,
        )
        write_stat = os.fstat(write_descriptor)
        if (
            not stat.S_ISREG(write_stat.st_mode)
            or write_stat.st_dev != read_stat.st_dev
            or write_stat.st_ino != read_stat.st_ino
        ):
            raise ValueError("selected signature sidecar identity changed before writing")
        write_descriptor_matches_selected_file = True

        try:
            os.lseek(write_descriptor, 0, os.SEEK_SET)
            offset = 0
            while offset < len(replacement_bytes):
                written = os.write(write_descriptor, replacement_bytes[offset:])
                if written <= 0:
                    raise OSError("short write while corrupting test signature sidecar")
                offset += written
            os.ftruncate(write_descriptor, len(replacement_bytes))
            os.fsync(write_descriptor)
        except BaseException as write_error:
            os.lseek(write_descriptor, 0, os.SEEK_SET)
            offset = 0
            while offset < len(original_bytes):
                written = os.write(write_descriptor, original_bytes[offset:])
                if written <= 0:
                    raise OSError(
                        "short write while restoring test signature sidecar"
                    ) from write_error
                offset += written
            os.ftruncate(write_descriptor, len(original_bytes))
            os.fsync(write_descriptor)
            raise
    finally:
        try:
            if mode_temporarily_changed and original_mode is not None:
                restore_descriptor = (
                    write_descriptor
                    if write_descriptor_matches_selected_file and write_descriptor is not None
                    else read_descriptor
                )
                os.fchmod(restore_descriptor, original_mode)
                if stat.S_IMODE(os.fstat(restore_descriptor).st_mode) != original_mode:
                    raise OSError("signature sidecar mode was not restored after test corruption")
        finally:
            if write_descriptor is not None:
                os.close(write_descriptor)
            os.close(read_descriptor)


@pytest.fixture
def cas_root(tmp_path: Path) -> Path:
    return tmp_path / ".polisyos"


@pytest.fixture
def store(cas_root: Path) -> FileSystemCAS:
    return FileSystemCAS(cas_root)


@pytest.fixture
def artifact_json_builder(store: FileSystemCAS) -> Callable[..., Any]:
    def _builder(
        payload: Any,
        *,
        kind: str,
        inputs: list[InputRef] | None = None,
        schema_version: str = "1.0",
        forbid_floats: bool = False,
    ):
        return put_json_artifact(
            store,
            payload,
            kind=kind,
            inputs=inputs,
            schema_version=schema_version,
            forbid_floats=forbid_floats,
        )

    return _builder


@pytest.fixture
def producer() -> ProducerInfo:
    return ProducerInfo(
        component="tests.phase0",
        version="0.0.0",
        git=GitInfo(commit="0000000", dirty=False),
    )


@pytest.fixture
def env_info() -> EnvInfo:
    return EnvInfo(
        python=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        platform=platform.platform(),
        deps_lock_hash="sha256:" + "0" * 64,
    )
