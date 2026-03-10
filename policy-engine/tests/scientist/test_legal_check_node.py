from __future__ import annotations

import logging

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.governance.legal_check import LegalCheckNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_TRINITY_BUNDLE_REF,
)


def test_legal_check_skips_when_legal_context_is_missing(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_legal_skip")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.legal"))

    trinity_ref = store.put_json(
        {"policy_spec": {"interventions": []}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    simulation_result_ref = store.put_json(
        {"ok": True},
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_legal_skip",
        inputs={INPUT_TRINITY_BUNDLE_REF: trinity_ref},
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: simulation_result_ref},
    )

    outcome = LegalCheckNode().execute(ctx, state)

    assert outcome.status == "skip"
    assert outcome.error is None
    assert outcome.events
    assert outcome.events[0].message == "Legal check skipped: missing params.jurisdiction"
    assert outcome.events[0].attrs == {
        "skip_reason": "missing_jurisdiction",
        "required": "params.jurisdiction",
    }
