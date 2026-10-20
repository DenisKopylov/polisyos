from __future__ import annotations

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext


def _run(tmp_path) -> RunContext:
    store = FileSystemCAS(tmp_path)
    registry = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    return RunContext.start(store=store, registry_bundle=registry, run_id="owner-event-emission")


def test_generic_emit_cannot_mint_core_or_run_owner_events(tmp_path) -> None:
    run = _run(tmp_path)
    ref = ArtifactRef(
        artifact_id=ArtifactID("sha256:" + "a" * 64),
        kind="scientist.candidate",
        media_type="application/json",
    )

    with pytest.raises(ValueError, match="run_context_owner_event_reserved"):
        run.emit("core", "RUN_OUTPUT_ADDED", outputs=[ref])
    with pytest.raises(ValueError, match="run_context_owner_event_reserved"):
        run.emit("candidate", "RUN_FINALIZED", outputs=[ref])

    run.emit("scientist.node.candidate", "NODE_STARTED")
    assert run.read_runtime_owner_output_refs() == ()
