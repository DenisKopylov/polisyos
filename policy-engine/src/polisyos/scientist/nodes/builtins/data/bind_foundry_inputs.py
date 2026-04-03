"""Public data bind foundry inputs module API."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.foundry import FoundryInputBindingRule
from polisyos.foundry.data_plane import build_input_bindings
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_INPUT_BINDING_REPORT_REF,
    ARTIFACT_STATE_SNAPSHOT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_INPUT_BINDINGS_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
)

logger = get_logger(__name__)

_ZERO_HASH = f"sha256:{'0' * 64}"

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_bind_foundry_inputs@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Bind Foundry Inputs",
    description="Build deterministic foundry.input_bindings and bound state snapshot.",
    tags=["builtin", "data", "foundry"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        f"inputs.{INPUT_DATA_SNAPSHOT_REF}",
        f"inputs.{INPUT_REGISTRY_BUNDLE_REF}",
        f"inputs.{INPUT_TRINITY_BUNDLE_REF}",
        "params.foundry_input_binding_rules",
    ],
    state_writes=[
        f"inputs.{INPUT_INPUT_BINDINGS_REF}",
        f"artifacts_index.{ARTIFACT_STATE_SNAPSHOT_REF}",
        f"artifacts_index.{ARTIFACT_INPUT_BINDING_REPORT_REF}",
    ],
    produces=[
        INPUT_INPUT_BINDINGS_REF,
        ARTIFACT_STATE_SNAPSHOT_REF,
        ARTIFACT_INPUT_BINDING_REPORT_REF,
    ],
)


@dataclass(frozen=True)
class BindFoundryInputsNode:
    """Data-stage DAG node that converts data snapshots and registry rules into Foundry input bindings.

    Requires a data snapshot and registry bundle, optionally enforces ModelSpec
    consistency, and writes the input-bindings ref, bound state snapshot, and
    input-binding report needed by simulation and compile stages.
    """
    strict_model_spec_match: bool = True

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def bind(self, params: dict[str, Any]) -> "BindFoundryInputsNode":
        if not params:
            return self
        strict_model_spec_match = params.get(
            "strict_model_spec_match",
            self.strict_model_spec_match,
        )
        return replace(self, strict_model_spec_match=bool(strict_model_spec_match))

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if INPUT_INPUT_BINDINGS_REF in state.inputs:
            return NodeOutcome(status="ok", state=state)

        data_snapshot_ref = state.inputs.get(INPUT_DATA_SNAPSHOT_REF)
        registry_bundle_ref = state.inputs.get(INPUT_REGISTRY_BUNDLE_REF)
        if data_snapshot_ref is None or registry_bundle_ref is None:
            error = NodeError(
                code=node_errors.ERROR_MISSING_INPUT,
                message="Missing data_snapshot_ref or registry_bundle_ref for input bindings",
                details={
                    "required": [INPUT_DATA_SNAPSHOT_REF, INPUT_REGISTRY_BUNDLE_REF],
                },
            )
            return NodeOutcome(status="fail", state=state, error=error)

        if self.strict_model_spec_match:
            mismatch = _check_model_spec_consistency(ctx, state, data_snapshot_ref.artifact_id.hex)
            if mismatch is not None:
                error = NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message="ModelSpec data_snapshot_ref mismatch for binding stage",
                    details=mismatch,
                )
                return NodeOutcome(status="fail", state=state, error=error)

        rules = _parse_binding_rules(state.params.get("foundry_input_binding_rules"))
        try:
            result = build_input_bindings(
                ctx.store,
                data_snapshot_ref=data_snapshot_ref,
                registry_bundle_ref=registry_bundle_ref,
                rules=rules,
                notes=["scientist.node_bind_foundry_inputs"],
            )
        except Exception as exc:
            error = NodeError(
                code=node_errors.ERROR_DATA_PLANE_BIND_FAILED,
                message=f"Failed to build foundry.input_bindings: {exc}",
            )
            event = NodeEvent(level="error", message="Input binding materialization failed")
            return NodeOutcome(status="fail", state=state, error=error, events=[event])

        new_state = state.model_copy(deep=True)
        new_state.inputs[INPUT_INPUT_BINDINGS_REF] = result.input_bindings_ref
        new_state.artifacts_index[ARTIFACT_STATE_SNAPSHOT_REF] = result.bound_state_snapshot_ref
        new_state.artifacts_index[ARTIFACT_INPUT_BINDING_REPORT_REF] = (
            result.input_binding_report_ref
        )

        artifacts = [
            result.input_bindings_ref,
            result.bound_state_snapshot_ref,
            result.input_binding_report_ref,
        ]
        events = [
            NodeEvent(
                level="info",
                message=(
                    "Foundry input bindings materialized "
                    f"({len(result.applied_binding_ids)} rules applied)"
                ),
            )
        ]
        return NodeOutcome(status="ok", state=new_state, artifacts=artifacts, events=events)


def _parse_binding_rules(value: Any) -> list[FoundryInputBindingRule] | None:
    if value is None:
        return None
    if isinstance(value, list):
        rules: list[FoundryInputBindingRule] = []
        for item in value:
            try:
                rules.append(FoundryInputBindingRule.model_validate(item))
            except (TypeError, ValueError):
                logger.debug(
                    "Failed to validate binding rule item: %s",
                    item,
                    exc_info=True,
                )
                continue
        return rules or None
    return None


def _check_model_spec_consistency(
    ctx: ExecutionContext,
    state: ExperimentState,
    effective_data_snapshot_hex: str,
) -> dict[str, str] | None:
    trinity_ref = state.inputs.get(INPUT_TRINITY_BUNDLE_REF)
    if trinity_ref is None:
        return None
    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(trinity_ref.artifact_id))
        trinity = TrinityBundle.model_validate(payload)
    except Exception:
        logger.debug(
            "Failed to load trinity bundle for model-spec consistency check from ref %s",
            trinity_ref,
            exc_info=True,
        )
        return None

    expected = str(trinity.model_spec.data_snapshot_ref).strip()
    if not expected or expected == _ZERO_HASH:
        return None

    effective = f"sha256:{effective_data_snapshot_hex}"
    if expected == effective:
        return None
    return {
        "model_spec_data_snapshot_ref": expected,
        "effective_data_snapshot_ref": effective,
    }


__all__ = ["BindFoundryInputsNode"]
