from decimal import Decimal

import jax
import jax.numpy as jnp
import pytest

from polisyos.foundry.contracts.fidelity import FidelityLevel
from polisyos.foundry.profiles import CompileProfileLevel, FoundryCompileProfile
from polisyos.foundry.queue import QueueMechanism, QueueState, fidelity_gap_report, simulate_queue
from polisyos.foundry.specs import (
    get_mechanism_spec,
    mechanism_catalog,
    validate_mechanism_params,
)
from polisyos.foundry.trace import TraceEvent, TraceSlice


def test_trace_models_preserve_event_payloads() -> None:
    event = TraceEvent(
        phase="execute",
        event="node_start",
        payload={"node_id": "tax", "slot": "agents.income"},
    )
    trace = TraceSlice(events=[event])

    assert trace.events[0].phase == "execute"
    assert trace.events[0].payload["node_id"] == "tax"


def test_compile_profile_factories_toggle_nan_guard_as_expected() -> None:
    assert FoundryCompileProfile.fast().level == CompileProfileLevel.FAST
    assert FoundryCompileProfile.mvp().level == CompileProfileLevel.MVP
    assert FoundryCompileProfile.strict().level == CompileProfileLevel.STRICT
    assert FoundryCompileProfile.fast().nan_guard_enabled is False
    assert FoundryCompileProfile.strict().nan_guard_enabled is True


def test_queue_helpers_simulate_and_report_fidelity_gap() -> None:
    state = QueueState(queue_length=jnp.array(3.0, dtype=jnp.float32))
    fluid = QueueMechanism(
        service_rate=1.0,
        arrival_rate=2.0,
        fidelity=FidelityLevel.SURROGATE_FLUID,
    )
    hard = QueueMechanism(
        service_rate=1.0,
        arrival_rate=2.0,
        fidelity=FidelityLevel.HARD_DISCRETE,
    )

    fluid_state = simulate_queue(fluid, state, jax.random.PRNGKey(0), steps=3)
    hard_state = simulate_queue(hard, state, jax.random.PRNGKey(1), steps=3)
    report = fidelity_gap_report(fluid_state, hard_state)

    assert float(fluid_state.queue_length) >= 0.0
    assert float(hard_state.queue_length) >= 0.0
    assert report["abs_diff"] >= 0.0
    assert report["rel_diff"] >= 0.0


def test_mechanism_catalog_contains_runtime_mechanisms() -> None:
    names = {entry["name"] for entry in mechanism_catalog()}
    assert {"income_tax", "labor_market", "tax_subsidy"} <= names


def test_get_mechanism_spec_and_param_validation_accept_known_runtime_inputs() -> None:
    spec = get_mechanism_spec("income_tax")

    assert spec.description
    validate_mechanism_params("income_tax", {"rate": "25%"}, mechanism_spec=spec)
    validate_mechanism_params("tax_subsidy", {"rate": Decimal("0.4")})


def test_validate_mechanism_params_rejects_unknown_or_out_of_range_values() -> None:
    with pytest.raises(ValueError, match="Unknown mechanism type"):
        get_mechanism_spec("missing_runtime_mechanism")

    with pytest.raises(ValueError, match="above max"):
        validate_mechanism_params("income_tax", {"rate": "150%"})

    with pytest.raises(ValueError, match="unknown param 'extra'"):
        validate_mechanism_params("income_tax", {"rate": 0.2, "extra": True})
