"""Public data build data snapshot module API."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from pydantic import ValidationError

from polisyos.core.artifacts import profile_bound_ref
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef, DataViewRequestRef
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_DATA_VIEW_REQUEST_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_build_data_snapshot@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Build Data Snapshot",
    description="Build a Fabric DataSnapshot for Foundry execution.",
    tags=["builtin", "data"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        f"inputs.{INPUT_DATA_SNAPSHOT_REF}",
        f"inputs.{INPUT_DATA_VIEW_REQUEST_REF}",
    ],
    state_writes=[
        f"inputs.{INPUT_DATA_SNAPSHOT_REF}",
        f"inputs.{INPUT_DATA_VIEW_REQUEST_REF}",
        "params.pii_scan_results",
    ],
    produces=[INPUT_DATA_SNAPSHOT_REF],
)
_DATA_SNAPSHOT_RUNTIME_ERRORS = (
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)


@dataclass(frozen=True)
class BuildDataSnapshotNode:
    """Build data_snapshot_ref via Fabric port."""

    allow_fabric: bool = True

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def bind(self, params: dict[str, Any]) -> BuildDataSnapshotNode:
        if not params:
            return self
        allow_fabric = params.get("allow_fabric", self.allow_fabric)
        return replace(self, allow_fabric=bool(allow_fabric))

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if INPUT_DATA_SNAPSHOT_REF in state.inputs:
            return NodeOutcome(status="ok", state=state)

        inputs = dict(state.inputs)

        if self.allow_fabric and ctx.fabric is not None and INPUT_DATA_VIEW_REQUEST_REF in inputs:
            request_ref = profile_bound_ref(
                ctx.store,
                DataViewRequestRef.model_validate(inputs[INPUT_DATA_VIEW_REQUEST_REF].model_dump()),
            )
            try:
                snapshot_ref = ctx.fabric.snapshot(ctx.store, request_ref)
                pii_scan_summary = _read_snapshot_pii_summary(ctx, snapshot_ref)
            except _DATA_SNAPSHOT_RUNTIME_ERRORS as exc:
                error = NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message=f"Fabric returned an invalid selected DataSnapshot: {exc}",
                    details={"input": INPUT_DATA_SNAPSHOT_REF},
                )
                event = NodeEvent(level="error", message="DataSnapshot owner admission failed")
                return NodeOutcome(status="fail", state=state, error=error, events=[event])
            new_state = branch_state(state, write_paths=_SPEC.state_writes).state
            new_state.inputs[INPUT_DATA_VIEW_REQUEST_REF] = request_ref
            new_state.inputs[INPUT_DATA_SNAPSHOT_REF] = snapshot_ref
            if pii_scan_summary is not None:
                new_state.params["pii_scan_results"] = pii_scan_summary
            return NodeOutcome(status="ok", state=new_state, artifacts=[snapshot_ref])

        error = NodeError(
            code=node_errors.ERROR_MISSING_INPUT,
            message="Missing data_snapshot_ref and no supported builder input is available",
            details={"required": [INPUT_DATA_SNAPSHOT_REF, INPUT_DATA_VIEW_REQUEST_REF]},
        )
        event = NodeEvent(level="error", message="Data snapshot inputs missing")
        return NodeOutcome(status="fail", state=state, error=error, events=[event])


def _read_snapshot_pii_summary(
    ctx: ExecutionContext,
    snapshot_ref: DataSnapshotRef,
) -> dict[str, Any] | None:
    from polisyos.core.artifacts import validate_core_model_json_artifact

    snapshot = validate_core_model_json_artifact(DataSnapshot, ctx.store, snapshot_ref)
    return _coerce_pii_scan_summary(snapshot.pii_scan_summary)


def _coerce_pii_scan_summary(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError("selected DataSnapshot PII summary must be a mapping or absent")
    return dict(value)
