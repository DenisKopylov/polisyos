"""A real materialization error may permit local fallback; a string cannot."""

from __future__ import annotations

import pytest

from polisyos.runtime.quality.candidate_simulation import CandidateScenarioSetToRule
from polisyos.runtime.quality.generation_cycle import (
    _N5_CANDIDATE_LOCAL_FAILURE_ISSUER,
    GenerationCycleController,
    SimulationPortObservation,
)
from polisyos.runtime.quality.intervention_substrate import (
    InterventionSubstrateError,
    candidate_scenario_set_to_value,
)
from tests.unit.remediation.test_cyc_04 import _candidate


def test_generic_refusal_carries_only_actual_local_materialization_failure() -> None:
    """Consume the actual domain owner's error and remove retry power on replay."""
    rule = CandidateScenarioSetToRule(
        operator_kind="grant",
        parameter_id="amount",
        target_world_slot="government_balance",
        unit_id="USD",
        minimum=0,
        maximum=1,
    )
    with pytest.raises(InterventionSubstrateError) as caught:
        candidate_scenario_set_to_value(
            rule,
            operator_kind="grant",
            parameters={"amount": 2},
            linked_write_slots=("government_balance",),
        )
    error = caught.value
    assert error.code == "candidate_scenario_value_outside_profile_domain"
    controller = GenerationCycleController()
    candidate = _candidate("actual-local-domain-refusal", "a")
    local = controller._generic_cycle_simulation_refusal(
        candidate=candidate, code=error.code, candidate_local_exception=error
    )
    assert local._candidate_local_failure_issuer is _N5_CANDIDATE_LOCAL_FAILURE_ISSUER
    assert local.authority_blockers == (error.code,)
    assert local.diagnostics["request_builder"] == "persisted_generic_cycle_profile"
    replayed = SimulationPortObservation.model_validate(local.model_dump(mode="json"))
    assert replayed._candidate_local_failure_issuer is None
    for supplied in (None, ValueError(error.code), InterventionSubstrateError("foreign_scope")):
        refused = controller._generic_cycle_simulation_refusal(
            candidate=candidate, code=error.code, candidate_local_exception=supplied
        )
        assert refused._candidate_local_failure_issuer is None
