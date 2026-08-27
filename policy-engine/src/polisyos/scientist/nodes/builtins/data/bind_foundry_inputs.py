"""Public data bind foundry inputs module API."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.foundry import FoundryInputBindingRule
from polisyos.foundry.data_plane import (
    UkraineFoundryIntakeResult,
    build_input_bindings,
    load_ukraine_foundry_intake,
)
from polisyos.foundry.methods import MethodRegistry, ensure_all_methods_registered
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_INPUT_BINDING_REPORT_REF,
    ARTIFACT_STATE_SNAPSHOT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_INPUT_BINDINGS_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
    INPUT_UKRAINE_FOUNDRY_METHOD_BUNDLE_REF,
    INPUT_UKRAINE_SELECTED_METHOD_CONTRACT_REF,
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

logger = get_logger(__name__)

_ZERO_HASH = f"sha256:{'0' * 64}"
_BINDING_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_BINDING_LOAD_ERRORS = (TypeError, ValueError, ValidationError, FileNotFoundError, OSError)
_UKRAINE_INTAKE_CONFIG_KEY = "ukraine_foundry_intake"
_UKRAINE_INTAKE_RECEIPT_KEY = "ukraine_foundry_intake_receipt_ref"
_UKRAINE_METHOD_SELECTION_CONFIG_KEY = "ukraine_foundry_method_selection"

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
        f"params.{_UKRAINE_INTAKE_CONFIG_KEY}",
        f"params.{_UKRAINE_METHOD_SELECTION_CONFIG_KEY}",
    ],
    state_writes=[
        f"inputs.{INPUT_INPUT_BINDINGS_REF}",
        f"artifacts_index.{ARTIFACT_STATE_SNAPSHOT_REF}",
        f"artifacts_index.{ARTIFACT_INPUT_BINDING_REPORT_REF}",
        f"artifacts_index.{_UKRAINE_INTAKE_RECEIPT_KEY}",
        f"inputs.{INPUT_UKRAINE_FOUNDRY_METHOD_BUNDLE_REF}",
        f"inputs.{INPUT_UKRAINE_SELECTED_METHOD_CONTRACT_REF}",
        "observational_data_ref",
        "causal_method_fqn",
        "params.proxy_identification_bundle",
    ],
    produces=[
        INPUT_INPUT_BINDINGS_REF,
        ARTIFACT_STATE_SNAPSHOT_REF,
        ARTIFACT_INPUT_BINDING_REPORT_REF,
        _UKRAINE_INTAKE_RECEIPT_KEY,
        INPUT_UKRAINE_FOUNDRY_METHOD_BUNDLE_REF,
        INPUT_UKRAINE_SELECTED_METHOD_CONTRACT_REF,
    ],
)


class _UkraineFoundryMethodSelection(BaseModel):
    """Strict explicit method-input routing request; no default is permitted."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_key: str = Field(min_length=1)
    method_fqn: str = Field(min_length=1)


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

    def bind(self, params: dict[str, Any]) -> BindFoundryInputsNode:
        if not params:
            return self
        strict_model_spec_match = params.get(
            "strict_model_spec_match",
            self.strict_model_spec_match,
        )
        return replace(self, strict_model_spec_match=bool(strict_model_spec_match))

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        intake_config = state.params.get(_UKRAINE_INTAKE_CONFIG_KEY)
        selection_config = state.params.get(_UKRAINE_METHOD_SELECTION_CONFIG_KEY)
        if INPUT_INPUT_BINDINGS_REF in state.inputs and intake_config is None:
            return NodeOutcome(status="ok", state=state)

        data_snapshot_ref = state.inputs.get(INPUT_DATA_SNAPSHOT_REF)
        registry_bundle_ref = state.inputs.get(INPUT_REGISTRY_BUNDLE_REF)
        intake: UkraineFoundryIntakeResult | None = None
        selected_contract_ref = None
        selected_method_fqn: str | None = None
        selected_contract_key: str | None = None
        if intake_config is not None:
            try:
                intake = _load_ukraine_intake(ctx, intake_config)
                selection = _resolve_ukraine_method_selection(intake, selection_config)
                if selection is not None:
                    selected_contract_key = selection.contract_key
                    selected_method_fqn = selection.method_fqn
                    selected_contract_ref = intake.method_contract_refs[
                        selection.contract_key
                    ]
                intake_snapshot_ref = intake.data_snapshot_ref
            except _BINDING_VALIDATION_ERRORS as exc:
                error = NodeError(
                    code=node_errors.ERROR_DATA_PLANE_BIND_FAILED,
                    message=f"Failed to load verified Ukraine Foundry intake: {exc}",
                )
                event = NodeEvent(level="error", message="Ukraine intake verification failed")
                return NodeOutcome(status="fail", state=state, error=error, events=[event])
            if (
                data_snapshot_ref is not None
                and data_snapshot_ref.artifact_id != intake_snapshot_ref.artifact_id
            ):
                error = NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message="Ukraine intake snapshot does not match supplied data_snapshot_ref",
                    details={
                        "supplied_data_snapshot_ref": str(data_snapshot_ref.artifact_id),
                        "intake_data_snapshot_ref": str(intake_snapshot_ref.artifact_id),
                    },
                )
                return NodeOutcome(status="fail", state=state, error=error)
            data_snapshot_ref = intake_snapshot_ref
        elif selection_config is not None:
            error = NodeError(
                code=node_errors.ERROR_INVALID_STATE,
                message=(
                    "ukraine_foundry_method_selection requires a verified "
                    "ukraine_foundry_intake"
                ),
            )
            return NodeOutcome(status="fail", state=state, error=error)

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
        except _BINDING_VALIDATION_ERRORS as exc:
            error = NodeError(
                code=node_errors.ERROR_DATA_PLANE_BIND_FAILED,
                message=f"Failed to build foundry.input_bindings: {exc}",
            )
            event = NodeEvent(level="error", message="Input binding materialization failed")
            return NodeOutcome(status="fail", state=state, error=error, events=[event])

        intake_receipt_ref = intake.receipt_ref if intake is not None else None

        write_paths = [
            f"inputs.{INPUT_INPUT_BINDINGS_REF}",
            f"artifacts_index.{ARTIFACT_STATE_SNAPSHOT_REF}",
            f"artifacts_index.{ARTIFACT_INPUT_BINDING_REPORT_REF}",
        ]
        if intake is not None:
            write_paths.extend(
                [
                    f"artifacts_index.{_UKRAINE_INTAKE_RECEIPT_KEY}",
                    f"inputs.{INPUT_UKRAINE_FOUNDRY_METHOD_BUNDLE_REF}",
                    "params.proxy_identification_bundle",
                ]
            )
        if selected_contract_ref is not None:
            write_paths.append(f"inputs.{INPUT_UKRAINE_SELECTED_METHOD_CONTRACT_REF}")
        if selected_contract_key == "d2_panel_observational":
            write_paths.extend(["observational_data_ref", "causal_method_fqn"])
        new_state = branch_state(
            state,
            write_paths=tuple(write_paths),
        ).state
        new_state.inputs[INPUT_INPUT_BINDINGS_REF] = result.input_bindings_ref
        new_state.artifacts_index[ARTIFACT_STATE_SNAPSHOT_REF] = result.bound_state_snapshot_ref
        new_state.artifacts_index[ARTIFACT_INPUT_BINDING_REPORT_REF] = (
            result.input_binding_report_ref
        )
        if intake is not None and intake_receipt_ref is not None:
            new_state.artifacts_index[_UKRAINE_INTAKE_RECEIPT_KEY] = intake_receipt_ref
            new_state.inputs[INPUT_UKRAINE_FOUNDRY_METHOD_BUNDLE_REF] = (
                intake.method_input_bundle_ref
            )
            new_state.params["proxy_identification_bundle"] = intake.proxy_identification_bundle
        if selected_contract_ref is not None:
            new_state.inputs[INPUT_UKRAINE_SELECTED_METHOD_CONTRACT_REF] = selected_contract_ref
        if (
            selected_contract_key == "d2_panel_observational"
            and selected_contract_ref is not None
            and selected_method_fqn is not None
        ):
            new_state.observational_data_ref = selected_contract_ref
            new_state.causal_method_fqn = selected_method_fqn

        artifacts = [
            result.input_bindings_ref,
            result.bound_state_snapshot_ref,
            result.input_binding_report_ref,
        ]
        if intake_receipt_ref is not None:
            artifacts.append(intake_receipt_ref)
        if intake is not None:
            artifacts.append(intake.method_input_bundle_ref)
        if selected_contract_ref is not None:
            artifacts.append(selected_contract_ref)
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


def _load_ukraine_intake(
    ctx: ExecutionContext,
    config: Any,
) -> UkraineFoundryIntakeResult:
    """Validate node config and invoke the sole Ukraine intake surface."""

    if not isinstance(config, Mapping):
        raise ValueError("ukraine_foundry_intake must be a mapping")
    allowed_root = config.get("allowed_root")
    stage_manifests = config.get("stage_manifests")
    if not isinstance(allowed_root, str) or not allowed_root.strip():
        raise ValueError("ukraine_foundry_intake.allowed_root must be a non-empty path")
    if not isinstance(stage_manifests, Mapping):
        raise ValueError("ukraine_foundry_intake.stage_manifests must be a mapping")
    return load_ukraine_foundry_intake(
        # The bridge owns persistence of its inspection receipt, so this node
        # only transports its already-materialized result through workflow state.
        store=ctx.store,
        stage_manifests={str(key): Path(str(value)) for key, value in stage_manifests.items()},
        allowed_root=Path(allowed_root),
    )


def _resolve_ukraine_method_selection(
    intake: UkraineFoundryIntakeResult,
    value: Any,
) -> _UkraineFoundryMethodSelection | None:
    """Validate one explicit contract/method pair against the registered signature."""

    if value is None:
        return None
    try:
        selection = _UkraineFoundryMethodSelection.model_validate(value)
    except ValidationError as exc:
        raise ValueError(f"invalid ukraine_foundry_method_selection: {exc}") from exc

    contract = intake.method_contracts.get(selection.contract_key)
    contract_ref = intake.method_contract_refs.get(selection.contract_key)
    if contract is None or contract_ref is None:
        raise ValueError(
            f"unknown Ukraine Foundry contract key: {selection.contract_key}"
        )
    contract_id = getattr(contract, "contract_id", None)
    if not isinstance(contract_id, str) or not contract_id:
        raise ValueError(
            f"Ukraine Foundry contract lacks a stable contract_id: {selection.contract_key}"
        )

    ensure_all_methods_registered()
    signature = MethodRegistry.get_instance().get_signature(selection.method_fqn)
    if signature is None:
        raise ValueError(f"unknown Foundry method: {selection.method_fqn}")
    accepted_contract_ids = {
        slot.contract_id for slot in signature.input_slots if slot.contract_id is not None
    }
    if contract_id not in accepted_contract_ids:
        raise ValueError(
            f"Foundry method {selection.method_fqn} does not accept contract {contract_id}"
        )
    return selection


def _parse_binding_rules(value: Any) -> list[FoundryInputBindingRule] | None:
    if value is None:
        return None
    if isinstance(value, list):
        rules: list[FoundryInputBindingRule] = []
        for item in value:
            try:
                rules.append(FoundryInputBindingRule.model_validate(item))
            except _BINDING_VALIDATION_ERRORS:
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
    except _BINDING_LOAD_ERRORS:
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
