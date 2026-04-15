from __future__ import annotations

import shutil
import tarfile
from io import BytesIO

import pytest

import polisyos.core.audit.safe_tar as safe_tar_module
from polisyos.core.audit.safe_tar import safe_extract_tar


def _build_archive(path, *, name: str, payload: bytes) -> None:
    with tarfile.open(path, "w:gz") as tar:
        info = tarfile.TarInfo(name=name)
        info.size = len(payload)
        tar.addfile(info, BytesIO(payload))


def test_safe_extract_tar_cleans_partial_files_on_failure(tmp_path, monkeypatch) -> None:
    archive = tmp_path / "bundle.tar.gz"
    _build_archive(archive, name="artifact.txt", payload=b"payload")
    target = tmp_path / "out"
    target.mkdir()

    def _raise_type_error(self, path, members=None, filter=None):  # noqa: ANN001
        del self, path, members, filter
        raise TypeError("fallback path")

    def _copy_boom(src, dst, length=16 * 1024):  # noqa: ANN001
        del src, length
        dst.write(b"partial")
        raise OSError("copy failed")

    monkeypatch.setattr(safe_tar_module.tarfile.TarFile, "extractall", _raise_type_error)
    monkeypatch.setattr(safe_tar_module.shutil, "copyfileobj", _copy_boom)

    with pytest.raises(OSError, match="copy failed"):
        safe_extract_tar(archive, target)

    assert list(tmp_path.glob("out.extract-*")) == []
    assert list(target.iterdir()) == []


def test_safe_extract_tar_extracts_atomically(tmp_path) -> None:
    archive = tmp_path / "bundle.tar.gz"
    _build_archive(archive, name="artifact.txt", payload=b"payload")
    target = tmp_path / "out"
    target.mkdir()

    extracted = safe_extract_tar(archive, target)

    assert extracted == target
    assert (target / "artifact.txt").read_bytes() == b"payload"
