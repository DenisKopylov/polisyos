from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.foundry.methods.catalog.causal import interference as runtime
from polisyos.foundry.methods.catalog.causal._interference_contracts import (
    InterferenceAugmentedGraph,
    InterferenceIdentificationResult,
    _ReductionErrorBoundPlan,
    _SimplicialSupportGate,
    _TopologyCertificatePlan,
)
from polisyos.ir.analytics.causal_graph import CausalGraphModel, GraphType


def test_interference_contracts_are_reexported_from_runtime_module() -> None:
    assert runtime.InterferenceAugmentedGraph is InterferenceAugmentedGraph
    assert runtime.InterferenceIdentificationResult is InterferenceIdentificationResult
    assert runtime._SimplicialSupportGate is _SimplicialSupportGate
    assert runtime._TopologyCertificatePlan is _TopologyCertificatePlan
    assert runtime._ReductionErrorBoundPlan is _ReductionErrorBoundPlan


def test_interference_reduction_bound_contract_is_characterized() -> None:
    plan = _ReductionErrorBoundPlan(reduction_error_bound=0.25, assumptions=("bounded",))

    assert plan.reduction_error_bound == 0.25
    assert plan.assumptions == ("bounded",)


def _legacy_interference_payload() -> dict[str, object]:
    graph = CausalGraphModel(graph_type=GraphType.DAG, nodes=["X", "Y"], edges=[])
    augmented_graph = InterferenceAugmentedGraph(
        original_graph=graph,
        augmented_graph=graph,
        interference_type="none",
    )
    return InterferenceIdentificationResult(
        treatment="X",
        outcome="Y",
        status="identified",
        interference_detected=False,
        sutva_violated=False,
        augmented_graph=augmented_graph,
    ).model_dump(mode="json")


def test_interference_result_v1_0_legacy_payload_remains_readable() -> None:
    payload = _legacy_interference_payload()

    assert payload["schema_version"] == "1.0"
    assert (
        InterferenceIdentificationResult.model_validate(payload).model_dump(mode="json") == payload
    )

    legacy_non_identified = {**payload, "status": "non_identified"}
    assert (
        InterferenceIdentificationResult.model_validate(legacy_non_identified).status
        == "non_identified"
    )


@pytest.mark.parametrize("status", ["oracle_needed", "pag_ambiguous", "not_recoverable"])
def test_expanded_interference_statuses_require_schema_v1_1(status: str) -> None:
    legacy = _legacy_interference_payload()
    with pytest.raises(ValidationError):
        InterferenceIdentificationResult.model_validate({**legacy, "status": status})

    expanded = {
        **legacy,
        "schema_version": "1.1",
        "status": status,
    }
    assert InterferenceIdentificationResult.model_validate(expanded).status == status


def test_interference_result_rejects_unrecognized_schema_version() -> None:
    legacy = _legacy_interference_payload()

    with pytest.raises(ValidationError):
        InterferenceIdentificationResult.model_validate({**legacy, "schema_version": "1.2"})


def test_nullable_topology_indicators_require_schema_v1_1() -> None:
    legacy = _legacy_interference_payload()
    legacy_unknown = {
        **legacy,
        "interference_detected": None,
        "sutva_violated": None,
    }
    with pytest.raises(ValidationError):
        InterferenceIdentificationResult.model_validate(legacy_unknown)

    expanded_unknown = {
        **legacy_unknown,
        "schema_version": "1.1",
    }
    result = InterferenceIdentificationResult.model_validate(expanded_unknown)
    assert result.interference_detected is None
    assert result.sutva_violated is None
