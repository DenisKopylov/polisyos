from __future__ import annotations

from polisyos.foundry.methods.catalog.causal import interference as runtime
from polisyos.foundry.methods.catalog.causal._interference_contracts import (
    InterferenceAugmentedGraph,
    InterferenceIdentificationResult,
    _ReductionErrorBoundPlan,
    _SimplicialSupportGate,
    _TopologyCertificatePlan,
)


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
