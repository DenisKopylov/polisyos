from __future__ import annotations

import pytest
from polisyos.foundry._registry import MECHANISM_REGISTRY, get_mechanism_descriptor
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.catalog.snapshot import build_method_catalog_snapshot
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def _reset_foundry_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def test_foundry_v2_snapshot_contains_mechanism_and_simulation_families() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_v2_unified")

    entries = {entry.fqn: entry for entry in snapshot.entries}
    assert "mechanism.runtime.income_tax@1.0.0" in entries
    assert "simulation.compartmental.sir@1.0.0" in entries
    assert "simulation.agent_based.population_dynamics@1.0.0" in entries
    assert entries["mechanism.runtime.income_tax@1.0.0"].kind == "mechanism"
    assert entries["simulation.agent_based.population_dynamics@1.0.0"].kind == "simulation"


def test_mechanism_registry_is_backed_by_unified_method_catalog() -> None:
    ensure_all_methods_registered()

    assert "income_tax" in MECHANISM_REGISTRY
    descriptor = get_mechanism_descriptor("income_tax")
    assert descriptor.method_fqn == "mechanism.runtime.income_tax@1.0.0"
    assert descriptor.mechanism_class_path == "polisyos.foundry.mechanisms:IncomeTax"


def test_mechanism_runtime_method_dispatches_patch_payload() -> None:
    pytest.importorskip("jax")
    import jax.numpy as jnp
    from polisyos.foundry.contracts.state import GlobalState as RuntimeGlobalState

    ensure_all_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    state = RuntimeGlobalState.empty(3, 2)
    agents = state.agents.replace(
        income=jnp.array([100.0, 100.0, 100.0], dtype=jnp.float32),
        reported_income=jnp.array([100.0, 100.0, 100.0], dtype=jnp.float32),
        active=jnp.array([True, True, False]),
    )
    state = state.replace(agents=agents)

    method_cls = registry.get("mechanism.runtime.income_tax@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=state,
        params={"rate": 0.2},
        seed=11,
    )

    delta = result.output["result"]["patches"]["agents.income"][0]["delta"]
    assert delta == pytest.approx([-20.0, -20.0, 0.0])
    assert result.output["result"]["mechanism_type"] == "income_tax"


def test_simulation_methods_dispatch_and_agent_sim_bridge_runs() -> None:
    pytest.importorskip("jax")
    import jax.numpy as jnp

    ensure_all_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    sir_cls = registry.get("simulation.compartmental.sir@1.0.0")
    sir_result = dispatcher.dispatch(
        method_class=sir_cls,
        signature=sir_cls.signature,
        state={"susceptible": 95.0, "infected": 5.0, "recovered": 0.0},
        params={"beta": 0.4, "gamma": 0.1, "n_steps": 12},
        seed=7,
    )
    assert len(sir_result.output["result"]["trajectory"]) == 12
    assert sir_result.output["result"]["peak_infected"] > 0.0

    abm_cls = registry.get("simulation.agent_based.population_dynamics@1.0.0")
    abm_result = dispatcher.dispatch(
        method_class=abm_cls,
        signature=abm_cls.signature,
        state={
            "initial_wealth": jnp.array([100.0, 120.0, 80.0, 90.0], dtype=jnp.float32),
            "initial_income": jnp.array([10.0, 12.0, 8.0, 9.0], dtype=jnp.float32),
            "active_mask": jnp.array([True, True, True, True]),
        },
        params={
            "n_steps": 3,
            "mechanism_names": ("taxation", "aging"),
            "mechanism_configs": {"taxation": {"progressive_factor": 0.0}},
            "seed": 0,
        },
        seed=7,
    )
    assert int(abm_result.output["result"]["final_time_step"]) == 3
    assert float(abm_result.output["result"]["final_total_wealth"]) >= 0.0
    assert abm_result.output["result"]["abm_result"]["identifiability_certificate"]["status"] == (
        "not_available"
    )
    assert abm_result.output["result"]["abm_result"]["bifurcation_report"]["status"] == (
        "not_available"
    )
