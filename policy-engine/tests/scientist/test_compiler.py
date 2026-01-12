from datetime import datetime

import jax
import jax.numpy as jnp
import pytest
from polisyos.foundry.domain.state import GlobalState
from polisyos.ir.contract import PolicyEntity, PolicyRequestIR
from polisyos.ir.types import EntityType, TranslatableString
from polisyos.scientist.orchestrator.compiler import compile_policy


def test_compile_policy_roundtrip_rate() -> None:
    dummy_ir = PolicyRequestIR(
        project_name=TranslatableString(en="Test Reform", ua="Test"),
        schema_version="1.0",
        generated_at=datetime.utcnow().isoformat(),
        generator={"name": "policy-engine", "version": "0.1.0"},
        currency="USD",
        time_unit="year",
        price_base_year=2024,
        simulation_params={"scope_years": 1, "time_frequency": "M"},
        scenarios={
            "random_seed": 7,
            "shocks": [],
            "timeline": {"start_year": 2024, "end_year": 2024},
        },
        entities=[
            PolicyEntity(
                id="all",
                entity_type=EntityType.AGENT,
                name=TranslatableString(en="All", ua="All"),
            )
        ],
        objectives=[],
        interventions=[
            {
                "id": "tax_cut_2025",
                "name": {"en": "Tax Cut", "ua": "Tax Cut"},
                "target_selector": {"all_of": [{"field": "id", "operator": "==", "value": "all"}]},
                "mechanism_type": "tax_subsidy",
                "parameters": {"rate": 0.15},
            }
        ],
    )

    n_agents = 100
    policy_model = compile_policy(dummy_ir, n_agents=n_agents)
    first_mech = policy_model.steps[0]

    assert float(first_mech.rate) == pytest.approx(0.15, abs=1e-6)

    state = GlobalState.empty(n_agents=n_agents, n_firms=5)
    state = state.replace(agents=state.agents.replace(income=jnp.ones(n_agents) * 1000.0))
    next_state, _ = policy_model(state, jax.random.PRNGKey(0))
    avg_income = jnp.mean(next_state.agents.income)

    assert float(avg_income) == pytest.approx(1150.0, abs=1e-3)
