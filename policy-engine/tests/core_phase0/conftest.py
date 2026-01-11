from __future__ import annotations

import platform
import sys
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.manifest import EnvInfo, GitInfo, ProducerInfo


@pytest.fixture()
def cas_root(tmp_path: Path) -> Path:
    return tmp_path / ".polisyos"


@pytest.fixture()
def store(cas_root: Path) -> FileSystemCAS:
    return FileSystemCAS(cas_root)


@pytest.fixture()
def producer() -> ProducerInfo:
    return ProducerInfo(
        component="tests.phase0",
        version="0.0.0",
        git=GitInfo(commit="0000000", dirty=False),
    )


@pytest.fixture()
def env_info() -> EnvInfo:
    return EnvInfo(
        python=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        platform=platform.platform(),
        deps_lock_hash="sha256:" + "0" * 64,
    )
