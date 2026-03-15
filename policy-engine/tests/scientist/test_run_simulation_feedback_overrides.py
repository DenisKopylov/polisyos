from __future__ import annotations

import logging

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.foundry import ExecuteResult
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.simulate.run_simulation import RunSimulationNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_EXEC_PLAN_REF,
    INPUT_INPUT_BINDINGS_REF,
    INPUT_PARAMETER_OVERRIDE_BUNDLE_REF,
    INPUT_REGISTRY_BUNDLE_REF,
)


class _CaptureFoundryPort:
    def __init__(self) -> None:
        self.request = None

    def execute(self, store: FileSystemCAS, request):  # noqa: ANN001
        self.request = request
        return ExecuteResult(ok=True, simulation_result_ref=None, derived_refs=[], notes=[])


def _put_json(store: FileSystemCAS, payload: dict, *, kind: str):
    return store.put_json(
        payload,
        PutOptions(kind=kind, media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def test_run_simulation_passes_parameter_override_bundle_ref(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_override")
    foundry = _CaptureFoundryPort()
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.override"),
        foundry=foundry,
    )

    exec_plan_ref = _put_json(store, {"plan": {}}, kind="foundry.exec_plan")
    input_bindings_ref = _put_json(store, {"bindings": []}, kind="foundry.input_bindings")
    override_bundle_ref = _put_json(
        store,
        {"schema_version": "1.0", "overrides": {"tax_node": {"rate": 0.33}}, "sources": {}, "notes": []},
        kind="foundry.parameter_override_bundle",
    )

    state = ExperimentState(
        run_id="R_override",
        inputs={
            INPUT_INPUT_BINDINGS_REF: input_bindings_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_PARAMETER_OVERRIDE_BUNDLE_REF: override_bundle_ref,
        },
        artifacts_index={ARTIFACT_EXEC_PLAN_REF: exec_plan_ref},
    )

    outcome = RunSimulationNode().execute(ctx, state)
    assert outcome.status == "ok"
    assert foundry.request is not None
    assert foundry.request.parameter_override_bundle_ref.artifact_id == override_bundle_ref.artifact_id
