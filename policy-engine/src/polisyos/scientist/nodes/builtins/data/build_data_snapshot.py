"""Public data build data snapshot module API."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.canon.canon_json import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef, DataViewRequestRef
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.error_semantics import emit_degraded_path
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_branching import branch_state
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_DATA_VIEW_REQUEST_REF,
)

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
    state_writes=[f"inputs.{INPUT_DATA_SNAPSHOT_REF}", "params.pii_scan_results"],
    produces=[INPUT_DATA_SNAPSHOT_REF],
)
_logger = get_logger(__name__)

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
            request_ref = DataViewRequestRef.model_validate(
                inputs[INPUT_DATA_VIEW_REQUEST_REF].model_dump()
            )
            snapshot_ref = ctx.fabric.snapshot(ctx.store, request_ref)
            pii_scan_summary = _read_snapshot_pii_summary(ctx, snapshot_ref)
            new_state = branch_state(state, write_paths=_SPEC.state_writes).state
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
    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(snapshot_ref.artifact_id))
        snapshot = DataSnapshot.model_validate(payload)
    except _DATA_SNAPSHOT_RUNTIME_ERRORS as exc:
        emit_degraded_path(
            component="scientist.nodes.build_data_snapshot",
            operation="read_snapshot_pii_summary",
            reason="snapshot_pii_summary_load_failed",
            exc=exc,
            details={"artifact_id": str(snapshot_ref.artifact_id)},
            log=_logger,
            metrics=ctx.metrics,
        )
        return None
    return _coerce_pii_scan_summary(snapshot.pii_scan_summary)


def _coerce_pii_scan_summary(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    result = dict(value)
    max_severity = result.get("max_severity")
    if max_severity is None:
        result["max_severity"] = "none"
    else:
        result["max_severity"] = str(max_severity).lower()
    total = result.get("total_entities_found")
    try:
        result["total_entities_found"] = max(0, int(total))
    except (TypeError, ValueError):
        result["total_entities_found"] = 0
    return result
