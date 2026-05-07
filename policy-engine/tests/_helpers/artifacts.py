from __future__ import annotations

import platform
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.manifest import EnvInfo, GitInfo, InputRef, ProducerInfo, SchemaInfo
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
