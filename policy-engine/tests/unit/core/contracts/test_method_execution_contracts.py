from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts import (
    MethodExecutionBundle as PublicMethodExecutionBundle,
)
from polisyos.core.contracts import (
    MethodMetricInputCapturePayload as PublicMethodMetricInputCapturePayload,
)
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecuteResult,
    MethodExecutionBundle,
    MethodExecutionDispatchRecord,
    MethodExecutionOccurrence,
    MethodExecutionReturnedSlot,
    MethodMetricBinding,
    MethodMetricBindingRequest,
    MethodMetricBindingSet,
    MethodMetricBindingSetRef,
    MethodOutputPayload,
)
from polisyos.foundry.execute._internal.graph import _returned_slot_inventory_row
from polisyos.ir.kernel.method_metrics import (
    MethodMetricSemanticContract,
    MethodMetricSourceUnit,
)
from polisyos.ir.kernel.units import RateUnit


def _ref(kind: str, suffix: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + suffix * 64,
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "f" * 64,
    )


def _binding() -> MethodMetricBinding:
    return MethodMetricBinding(
        binding_id="metric.binding.one",
        objective_id="objective.one",
        metric_id="metric.one",
        node_id="method.one",
        method_fqn="test.metric",
        method_version="1.0.0",
        method_abi_digest="a" * 64,
        method_abi_digest_algorithm="blake2b",
        method_build_digest="sha256:" + "d" * 64,
        method_build_digest_scope="class_source_only",
        output_slot_id="result",
        output_shape="scalar",
        semantics=MethodMetricSemanticContract(
            quantity_kind="economic.rate",
            quantity_role="outcome.level",
            population_id="population.target",
            axes=("time.year",),
            denominator_id="population.eligible",
            time_role="period.end",
            producer_contract_id="producer.policy_metric.v1",
        ),
        source_unit=MethodMetricSourceUnit(dimension="ratio", symbol="ratio", scale=1.0),
        target_unit=RateUnit(base="percent"),
        law_id="policyos.ir.method_metric.direct_output.v1",
        law_version="1.0",
        law_code_digest="sha256:" + "b" * 64,
        adapter_id="policyos.ir.method_metric.unit_adapter.v1",
        adapter_version="1.0",
        adapter_code_digest="sha256:" + "c" * 64,
        conversion_operation="ratio_to_percent",
        conversion_factor_numerator=100,
        conversion_factor_denominator=1,
        availability="available",
    )


def _dispatch(*, outcome: str = "not_run") -> MethodExecutionDispatchRecord:
    return MethodExecutionDispatchRecord(
        outcome=outcome,
        input_state_status="not_started",
        parameter_resolution_status="captured",
        seed_status="not_started",
        rng_state_status="not_started",
        backend_identity_status="not_started",
        backend_trace_status="not_started",
        fallback_status="not_started",
    )


def _occurrence(
    invocation_id: str = "graph-invocation.000001",
) -> MethodExecutionOccurrence:
    return MethodExecutionOccurrence(
        occurrence_id=f"{invocation_id}:0:method.one",
        invocation_id=invocation_id,
        plan_index=0,
        node_id="method.one",
        node_kind="method",
        status="planned",
        method_fqn="test.metric",
        method_version="1.0.0",
        method_abi_digest="a" * 64,
        method_abi_digest_algorithm="blake2b",
        returned_slot_inventory_status="not_started",
        dispatch=_dispatch(),
    )


def test_binding_set_rejects_duplicate_binding_identity() -> None:
    graph_ref = _ref("foundry.program_graph", "1")
    registry_ref = _ref("core.registry_bundle", "2")
    binding = _binding()

    with pytest.raises(ValidationError, match="duplicate_method_metric_binding_id"):
        MethodMetricBindingSet(
            program_graph_ref=graph_ref,
            policy_ref=_ref("ir.trinity_bundle", "3"),
            registry_bundle_ref=registry_ref,
            metric_registry_ref=_ref("ir.metric_registry", "4"),
            units_registry_ref=_ref("ir.units_registry", "5"),
            bindings=[binding, binding],
        )


def test_binding_set_rejects_same_output_slot_selected_for_two_metrics() -> None:
    binding = _binding()
    second = binding.model_copy(
        update={
            "binding_id": "metric.binding.two",
            "objective_id": "objective.two",
        }
    )
    with pytest.raises(ValidationError, match="duplicate_method_metric_selected_output_slot"):
        MethodMetricBindingSet(
            program_graph_ref=_ref("foundry.program_graph", "1"),
            policy_ref=_ref("ir.trinity_bundle", "3"),
            registry_bundle_ref=_ref("core.registry_bundle", "2"),
            metric_registry_ref=_ref("ir.metric_registry", "4"),
            units_registry_ref=_ref("ir.units_registry", "5"),
            bindings=[binding, second],
        )


def test_method_metric_binding_intake_rejects_more_than_128_rows() -> None:
    selections = [
        MethodMetricBindingRequest(
            objective_id=f"objective.{index}",
            node_id=f"method.{index}",
            output_slot_id="result",
        )
        for index in range(129)
    ]
    with pytest.raises(ValidationError, match="at most 128 items"):
        CompileRequest(
            schema_version="1.1",
            policy_ref=_ref("ir.trinity_bundle", "3"),
            method_metric_bindings=selections,
        )

    with pytest.raises(ValidationError, match="at most 128 items"):
        MethodMetricBindingSet(
            program_graph_ref=_ref("foundry.program_graph", "1"),
            policy_ref=_ref("ir.trinity_bundle", "3"),
            registry_bundle_ref=_ref("core.registry_bundle", "2"),
            metric_registry_ref=_ref("ir.metric_registry", "4"),
            units_registry_ref=_ref("ir.units_registry", "5"),
            bindings=[_binding() for _ in range(129)],
        )


def test_capture_contract_preserves_repeated_method_occurrences() -> None:
    binding_set_ref = MethodMetricBindingSetRef.model_validate(
        _ref("foundry.method_metric_binding_set", "6").model_dump(mode="python")
    )
    occurrences = [_occurrence(), _occurrence("graph-invocation.000002")]
    bundle = MethodExecutionBundle(
        program_graph_ref=_ref("foundry.program_graph", "1"),
        exec_plan_ref=_ref("foundry.exec_plan", "7"),
        method_metric_binding_set_ref=binding_set_ref,
        occurrences=occurrences,
        limitations=("loaded_method_entrypoint_digest_is_not_transitive_build_provenance",),
    )

    assert [item.occurrence_id for item in bundle.occurrences] == [
        "graph-invocation.000001:0:method.one",
        "graph-invocation.000002:0:method.one",
    ]
    with pytest.raises(ValidationError, match="duplicate_method_execution_occurrence_id"):
        MethodExecutionBundle(
            program_graph_ref=_ref("foundry.program_graph", "1"),
            exec_plan_ref=_ref("foundry.exec_plan", "7"),
            method_metric_binding_set_ref=binding_set_ref,
            occurrences=[occurrences[0], occurrences[0]],
        )


def test_capture_contract_inventories_unselected_emitted_slots() -> None:
    row = MethodExecutionReturnedSlot(
        slot_id="diagnostic_vector",
        declared_by_signature=False,
        returned="returned",
        runtime_type="numpy.ndarray",
        runtime_shape=(4,),
        runtime_shape_status="captured",
        runtime_dtype="float64",
        codec_status="unsupported_codec",
        retention_status="unsupported_codec",
        limitation="output_slot_not_selected_for_metric_capture",
    )

    assert row.slot_id == "diagnostic_vector"
    assert row.returned == "returned"
    assert row.retention_status == "unsupported_codec"


def test_output_payload_preserves_integer_precision_and_rejects_boolean() -> None:
    payload = MethodOutputPayload(
        occurrence_id="graph-invocation.000001:0:method.one",
        invocation_id="graph-invocation.000001",
        node_id="method.one",
        slot_id="result",
        value=2**53 + 1,
    )

    assert payload.value == 2**53 + 1
    with pytest.raises(ValidationError):
        MethodOutputPayload(
            occurrence_id="graph-invocation.000001:0:method.one",
            invocation_id="graph-invocation.000001",
            node_id="method.one",
            slot_id="result",
            value=True,
        )


def test_failed_capture_refs_do_not_claim_simulation_success() -> None:
    bundle_ref = _ref("foundry.method_execution_bundle", "8")
    result = ExecuteResult(
        schema_version="1.1",
        ok=False,
        simulation_result_ref=None,
        method_execution_bundle_ref=bundle_ref,
    )

    assert result.ok is False
    assert result.simulation_result_ref is None
    assert result.method_execution_bundle_ref == bundle_ref
    with pytest.raises(
        ValidationError,
        match="method_execution_bundle_requires_execute_result_schema_1_1",
    ):
        ExecuteResult(
            ok=False,
            method_execution_bundle_ref=bundle_ref,
        )


def test_unselected_return_inventory_preserves_known_codec_failure() -> None:
    row = _returned_slot_inventory_row(
        slot_id="diagnostic",
        value=object(),
        declared_slot=None,
        selected_output=None,
    )

    assert row.returned == "returned"
    assert row.codec_status == "unsupported_codec"
    assert row.retention_status == "unsupported_codec"
    assert row.limitation == "returned_method_output_codec_unsupported"


def test_method_execution_contracts_are_available_from_stable_core_facade() -> None:
    assert PublicMethodExecutionBundle is MethodExecutionBundle
    assert PublicMethodMetricInputCapturePayload.__name__ == "MethodMetricInputCapturePayload"
