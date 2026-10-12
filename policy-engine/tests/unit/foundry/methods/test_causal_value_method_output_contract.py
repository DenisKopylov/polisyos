"""Actual causal report owners remain reachable through the N8 selector."""

from __future__ import annotations

from polisyos.foundry.methods.catalog.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.catalog.causal.did import StandardDifferenceInDifferences
from polisyos.foundry.methods.catalog.causal.synthetic_control import SyntheticControlMethod
from polisyos.foundry.methods.selection.advisor import (
    reachable_value_method_fqns,
    select_value_method_for_problem,
)
from polisyos.foundry.methods.selection.registry import MethodRegistry
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.ir.analytics.uncertainty import OutputContractCapability
from tests.unit.runtime.quality.test_value_gate import (
    _avg_income_candidate,
    _avg_income_problem,
)


def test_real_causal_report_producers_declare_and_reach_n8_value_projection() -> None:
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    reachable = set(reachable_value_method_fqns(registry=registry))
    candidate = _avg_income_candidate()
    problem = _avg_income_problem()

    for method in (StandardDifferenceInDifferences, SyntheticControlMethod):
        signature = method.signature
        report_slot = next(slot for slot in signature.output_slots if slot.name == "report")
        assert report_slot.contract_id == CausalEffectReport.contract_id
        assert (
            OutputContractCapability.VALUE_UNCERTAINTY_PROJECTION
            in report_slot.contract_capabilities
        )
        assert signature.fqn in reachable

        selection = select_value_method_for_problem(
            candidate=candidate,
            problem=problem,
            requested_method_fqn=signature.fqn,
        )
        assert selection["status"] == "selected"
        assert selection["selected_method_fqn"] == signature.fqn
