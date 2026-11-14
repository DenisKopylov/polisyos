"""Real selected compiler fixture for method-output-to-method-input execution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any, ClassVar

import numpy as np

from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.execution_plan import ExecutionPlan, ExecutionPlanRef, MethodDagNode
from polisyos.core.contracts.foundry import CompileRequest
from polisyos.core.contracts.method_input import (
    MethodOutputInputPortSource,
    RegistrySlotInputPortSource,
)
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.methods.base import (
    ComputeBackend,
    MethodKind,
    MethodMetadata,
    MethodSignature,
    SideEffectProfile,
    SlotSpec,
)
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.foundry.methods.registry import MethodRegistry
from tests._helpers.program_graph_tax_subsidy_input import ProgramGraphTaxSubsidyInputCase
from tests._helpers.selected_method_input import prepare_selected_method_input_case

_BASE_SIGNATURE = PeriodFlowToStock.signature
_BASE_INPUT = _BASE_SIGNATURE.get_input_slot("period_flow")
_BASE_OUTPUT = _BASE_SIGNATURE.get_output_slot("result")
SELECTED_METHOD_OUTPUT_CALLS: list[tuple[str, float]] = []
if _BASE_INPUT is None or _BASE_OUTPUT is None:  # pragma: no cover - fixture invariant
    raise RuntimeError("selected_method_output_input_base_abi_missing")


def _pure_signature(*, name: str, input_slot: SlotSpec, output_slot: SlotSpec) -> MethodSignature:
    """Return an exact scalar NumPy ABI with no patch channel."""
    return replace(
        _BASE_SIGNATURE,
        namespace="tests.selected_method_output_input",
        name=name,
        input_slots=frozenset({input_slot}),
        output_slots=frozenset({output_slot}),
        parameters=(),
        patch_targets=(),
        kind=MethodKind.PURE,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )


def _pure_metadata(name: str) -> MethodMetadata:
    """Describe the controlled test arithmetic without patch semantics."""
    return replace(
        PeriodFlowToStock.metadata,
        description=f"Controlled scalar arithmetic fixture: {name}.",
        equations={"output": "selected_input * declared_multiplier"},
        assumptions={"empirical_status": "not_established"},
        output_interpretation="Candidate arithmetic only; no state patch is emitted.",
        side_effect_profile=SideEffectProfile.NONE,
    )


class SelectedMethodOutputProducer:
    """Emit twice the external selected period flow as a scalar return value."""

    signature: ClassVar[MethodSignature] = _pure_signature(
        name="producer",
        input_slot=_BASE_INPUT,
        output_slot=_BASE_OUTPUT,
    )
    metadata: ClassVar[MethodMetadata] = _pure_metadata("producer")
    side_effect_profile: ClassVar[SideEffectProfile] = SideEffectProfile.NONE
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, np.float64]:
        """Double the explicit scalar input without reading ambient state."""
        del params
        value = np.asarray(state["period_flow"])
        if value.shape != () or value.dtype != np.dtype(np.float64):
            raise ValueError("selected_method_output_producer_input_invalid")
        source = float(value.item())
        SELECTED_METHOD_OUTPUT_CALLS.append(("producer", source))
        return {"result": np.float64(source * 2.0)}


class SelectedMethodOutputConsumer:
    """Emit three times the explicitly transferred producer result."""

    signature: ClassVar[MethodSignature] = _pure_signature(
        name="consumer",
        input_slot=replace(_BASE_INPUT, name="incoming_flow"),
        output_slot=replace(_BASE_OUTPUT, name="summary"),
    )
    metadata: ClassVar[MethodMetadata] = _pure_metadata("consumer")
    side_effect_profile: ClassVar[SideEffectProfile] = SideEffectProfile.NONE
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, np.float64]:
        """Triple the exact transferred scalar without coercion or fallback."""
        del params
        value = np.asarray(state["incoming_flow"])
        if value.shape != () or value.dtype != np.dtype(np.float64):
            raise ValueError("selected_method_output_consumer_input_invalid")
        source = float(value.item())
        SELECTED_METHOD_OUTPUT_CALLS.append(("consumer", source))
        return {"summary": np.float64(source * 3.0)}


class SelectedMethodOutputFailingConsumer:
    """Read the explicit transferred scalar, then fail inside the real call."""

    signature: ClassVar[MethodSignature] = _pure_signature(
        name="failing_consumer",
        input_slot=replace(_BASE_INPUT, name="incoming_flow"),
        output_slot=replace(_BASE_OUTPUT, name="summary"),
    )
    metadata: ClassVar[MethodMetadata] = _pure_metadata("failing_consumer")
    side_effect_profile: ClassVar[SideEffectProfile] = SideEffectProfile.NONE
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, np.float64]:
        """Record the read before raising so execution capture can retain it."""
        del params
        value = np.asarray(state["incoming_flow"])
        if value.shape != () or value.dtype != np.dtype(np.float64):
            raise ValueError("selected_method_output_failing_consumer_input_invalid")
        SELECTED_METHOD_OUTPUT_CALLS.append(("consumer_failed", float(value.item())))
        raise ValueError("selected_method_output_consumer_failure_control")


PRODUCER_NODE_ID = "flow.producer"
CONSUMER_NODE_ID = "flow.consumer"
CONSUMER_INPUT_ID = "incoming_flow"
PRODUCER_OUTPUT_ID = "result"


def build_selected_method_output_plan(
    *,
    producer_class: type[Any] = SelectedMethodOutputProducer,
    consumer_class: type[Any] = SelectedMethodOutputConsumer,
    consumer_source: MethodOutputInputPortSource | None = None,
    plan_id: str = "selected-method-output-input",
) -> ExecutionPlan:
    """Build the exact mapped ABI plan; compilation derives its transfer edge."""
    source = consumer_source or MethodOutputInputPortSource(
        source_kind="method_output",
        producer_node_id=PRODUCER_NODE_ID,
        output_slot_id=PRODUCER_OUTPUT_ID,
    )
    producer_signature = producer_class.signature
    consumer_signature = consumer_class.signature
    return ExecutionPlan(
        schema_version="1.2",
        plan_id=plan_id,
        method_dag=[
            MethodDagNode(
                node_id=PRODUCER_NODE_ID,
                method_fqn=producer_signature.fqn,
                method_version=producer_signature.version,
                backend=producer_signature.execution_backend.value,
                params={},
                reads_slots=sorted(producer_signature.input_slot_names),
                writes_slots=sorted(producer_signature.output_slot_names),
                state_writes=[],
                input_ports={
                    "period_flow": RegistrySlotInputPortSource(
                        source_kind="registry_slot",
                        slot_id="period_flow",
                    )
                },
            ),
            MethodDagNode(
                node_id=CONSUMER_NODE_ID,
                method_fqn=consumer_signature.fqn,
                method_version=consumer_signature.version,
                backend=consumer_signature.execution_backend.value,
                params={},
                reads_slots=sorted(consumer_signature.input_slot_names),
                writes_slots=sorted(consumer_signature.output_slot_names),
                state_writes=[],
                input_ports={CONSUMER_INPUT_ID: source},
            ),
        ],
    )


def persist_and_compile_selected_method_output_plan(
    case: ProgramGraphTaxSubsidyInputCase,
    plan: ExecutionPlan,
) -> Any:
    """Persist a selected plan with exact Trinity lineage and compile it normally."""
    plan_ref = case.store.put_json(
        plan,
        PutOptions(
            kind="scientist.execution_plan",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ExecutionPlan", version=plan.schema_version),
            inputs=[input_ref_from_artifact_ref(case.trinity_ref, role="policy_candidate")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return compile_foundry(
        case.store,
        CompileRequest(
            schema_version="1.2",
            input_kind="trinity",
            policy_ref=case.trinity_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            method_execution_plan_ref=ExecutionPlanRef.model_validate(plan_ref.model_dump()),
            return_selected_profile=True,
        ),
    )


def prepare_selected_method_output_input_case(
    tmp_path: Path,
    *,
    producer_class: type[Any] = SelectedMethodOutputProducer,
    consumer_class: type[Any] = SelectedMethodOutputConsumer,
) -> tuple[ProgramGraphTaxSubsidyInputCase, dict[str, Any]]:
    """Compile the real two-method graph against selected external-flow inputs.

    The existing selected-input fixture supplies the real Trinity, registry,
    model declaration, and snapshot. Its bootstrap plan and graph are replaced
    only by refs returned from compiling this actual two-node selected plan.
    """
    bootstrap_case, metadata = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
    )
    registry = MethodRegistry.get_instance()
    registry.register(producer_class, override=True)
    registry.register(consumer_class, override=True)
    try:
        compiled = persist_and_compile_selected_method_output_plan(
            bootstrap_case,
            build_selected_method_output_plan(
                producer_class=producer_class,
                consumer_class=consumer_class,
            ),
        )
        if not compiled.ok or compiled.exec_plan_ref is None:
            raise AssertionError(
                f"selected_method_output_fixture_compile_failed:{compiled.notes!r}"
            )
        graph_refs = tuple(
            item.ref for item in compiled.derived_refs if item.role == "program_graph"
        )
        if len(graph_refs) != 1 or compiled.compile_report_ref is None:
            raise AssertionError("selected_method_output_fixture_compiled_refs_missing")
        return (
            replace(
                bootstrap_case,
                exec_plan_ref=compiled.exec_plan_ref,
                program_graph_ref=graph_refs[0],
                compile_report_ref=compiled.compile_report_ref,
            ),
            metadata,
        )
    except BaseException:
        registry.unregister(producer_class.signature.fqn)
        registry.unregister(consumer_class.signature.fqn)
        bootstrap_case.close()
        raise
