from __future__ import annotations

import logging
from dataclasses import replace
from typing import Callable

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState


@pytest.fixture
def cas_store(tmp_path) -> FileSystemCAS:
    return FileSystemCAS(tmp_path)


@pytest.fixture
def registry_bundle_ref(cas_store):
    return build_default_registry_bundle(cas_store).bundle_ref


@pytest.fixture
def execution_context(cas_store, registry_bundle_ref) -> ExecutionContext:
    run = RunContext.start(store=cas_store, registry_bundle=registry_bundle_ref, run_id="R_test")
    return ExecutionContext(store=cas_store, run=run, logger=logging.getLogger("test.nodes"))


@pytest.fixture
def minimal_state(registry_bundle_ref) -> ExperimentState:
    return ExperimentState(
        run_id="R_test",
        inputs={"registry_bundle_ref": registry_bundle_ref},
    )


@pytest.fixture
def artifact_ref_factory(cas_store):
    """Return a callable that creates distinct ArtifactRef objects."""
    from polisyos.core.artifacts.store import PutOptions

    counter = 0

    def _make(kind: str = "test.artifact", data: dict | None = None):
        nonlocal counter
        counter += 1
        payload = data or {"seq": counter}
        return cas_store.put_json(payload, PutOptions(kind=kind, media_type="application/json"))

    return _make
