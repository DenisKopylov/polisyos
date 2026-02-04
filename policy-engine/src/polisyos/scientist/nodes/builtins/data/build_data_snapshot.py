from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef, DataViewRequestRef
from polisyos.core.contracts.foundry import StateSnapshotRef
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata

from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_DATA_VIEW_REQUEST_REF,
    INPUT_STATE_SNAPSHOT_REF,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_build_data_snapshot@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Build Data Snapshot",
    description="Build or wrap a Fabric DataSnapshot for Foundry execution.",
    tags=["builtin", "data"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        f"inputs.{INPUT_DATA_SNAPSHOT_REF}",
        f"inputs.{INPUT_DATA_VIEW_REQUEST_REF}",
        f"inputs.{INPUT_STATE_SNAPSHOT_REF}",
    ],
    state_writes=[f"inputs.{INPUT_DATA_SNAPSHOT_REF}"],
    produces=[INPUT_DATA_SNAPSHOT_REF],
)


@dataclass(frozen=True)
class BuildDataSnapshotNode:
    """Build data_snapshot_ref via Fabric port or wrap an existing state snapshot."""

    allow_fabric: bool = True

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def bind(self, params: dict[str, Any]) -> "BuildDataSnapshotNode":
        if not params:
            return self
        allow_fabric = params.get("allow_fabric", self.allow_fabric)
        return replace(self, allow_fabric=bool(allow_fabric))

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if INPUT_DATA_SNAPSHOT_REF in state.inputs:
            return NodeOutcome(status="ok", state=state)

        inputs = dict(state.inputs)

        if self.allow_fabric and ctx.fabric is not None and INPUT_DATA_VIEW_REQUEST_REF in inputs:
            request_ref = DataViewRequestRef.model_validate(
                inputs[INPUT_DATA_VIEW_REQUEST_REF].model_dump()
            )
            snapshot_ref = ctx.fabric.snapshot(ctx.store, request_ref)
            new_state = state.model_copy(deep=True)
            new_state.inputs[INPUT_DATA_SNAPSHOT_REF] = snapshot_ref
            return NodeOutcome(status="ok", state=new_state, artifacts=[snapshot_ref])

        if INPUT_STATE_SNAPSHOT_REF in inputs:
            snapshot_ref = StateSnapshotRef.model_validate(
                inputs[INPUT_STATE_SNAPSHOT_REF].model_dump()
            )
            snapshot = DataSnapshot(data_ref=snapshot_ref)
            snapshot_ref_payload = ctx.store.put_json(
                snapshot,
                PutOptions(
                    kind="fabric.data_snapshot",
                    media_type="application/json",
                    schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.1.0"),
                    inputs=[InputRef(artifact_id=snapshot_ref.artifact_id, role="state_snapshot")],
                ),
            )
            data_snapshot_ref = DataSnapshotRef(artifact_id=snapshot_ref_payload.artifact_id)
            new_state = state.model_copy(deep=True)
            new_state.inputs[INPUT_DATA_SNAPSHOT_REF] = data_snapshot_ref
            return NodeOutcome(status="ok", state=new_state, artifacts=[data_snapshot_ref])

        error = NodeError(
            code=node_errors.ERROR_MISSING_INPUT,
            message="Missing data_snapshot_ref and no fallback available",
            details={"required": [INPUT_DATA_SNAPSHOT_REF, INPUT_STATE_SNAPSHOT_REF]},
        )
        event = NodeEvent(level="error", message="Data snapshot inputs missing")
        return NodeOutcome(status="fail", state=state, error=error, events=[event])
