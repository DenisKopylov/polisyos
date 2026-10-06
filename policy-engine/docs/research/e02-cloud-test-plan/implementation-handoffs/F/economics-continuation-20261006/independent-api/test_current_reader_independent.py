import inspect
from pathlib import Path
import jax
import jax.numpy as jnp
import numpy as np
import pytest
from polisyos.foundry.agent_sim.distributions import compute_gini_hard
from polisyos.foundry.plugins.economics import EconomicsPlugin, EconomicState
from polisyos.foundry.plugins.economics.objectives import GiniObjective


def test_actual_owned_origin_and_current_masked_pairwise_population():
    owner=Path(inspect.getfile(compute_gini_hard)).resolve()
    assert owner.is_relative_to(Path('/workspace/e02-F-economics-20261006/policy-engine/src'))
    original=EconomicState.empty(n_agents=6,seed=71)
    values=np.array([1.,np.nan,4.,-np.inf,9.,0.],dtype=np.float32)
    active=np.array([1,0,1,0,1,1],dtype=bool)
    current=original.replace(agents=original.agents.replace(wealth=jnp.asarray(values),active=jnp.asarray(active)))
    assert float(current.distributions.gini_wealth)==float(original.distributions.gini_wealth)
    assert np.isfinite(float(current.distributions.gini_wealth))
    selected=values[active]
    oracle=np.abs(selected[:,None]-selected[None,:]).sum()/(2*len(selected)*selected.sum())
    assert float(current.distributions.gini_wealth)!=pytest.approx(float(oracle),abs=1e-5)
    plugin=EconomicsPlugin()
    objective=plugin.get_objectives()['gini']
    assert isinstance(objective,GiniObjective)
    for evaluate in (objective.evaluate,jax.jit(objective.evaluate)):
        assert float(evaluate(current))==pytest.approx(float(oracle),abs=2e-7)
        permutation=jnp.asarray([4,0,5,2,3,1])
        permuted=current.replace(agents=current.agents.replace(wealth=current.agents.wealth[permutation],active=current.agents.active[permutation]))
        assert float(evaluate(permuted))==pytest.approx(float(oracle),abs=2e-7)


def test_current_population_refuses_signed_value_behind_valid_scalar():
    original=EconomicState.empty(n_agents=4,seed=71)
    current=original.replace(agents=original.agents.replace(wealth=jnp.asarray([-2.,1.,4.,4.])))
    assert float(current.distributions.gini_wealth)==float(original.distributions.gini_wealth)
    assert np.isfinite(float(current.distributions.gini_wealth))
    for evaluate in (GiniObjective().evaluate,jax.jit(GiniObjective().evaluate)):
        with pytest.raises((RuntimeError,ValueError),match='classical Gini requires finite nonnegative'):
            jax.block_until_ready(evaluate(current))


def test_distributional_report_unavailable_and_historical_loss_are_distinct_owners():
    from polisyos.foundry.analysis.distributional import build_distributional_report,build_income_quintile_breakdown
    from polisyos.foundry.contracts.state import GlobalState
    from polisyos.foundry.methods.loss import policy_loss_fn
    from polisyos.foundry.plugins.economics.baselines import normalized_income_budget_loss
    values=np.tile(np.asarray([-2.,1.]),5)
    report=build_distributional_report([build_income_quintile_breakdown(values,values)],incomes_before=values,incomes_after=values)
    assert report.overall_gini_before is None and report.overall_gini_after is None
    state=GlobalState.empty(n_agents=4,n_firms=1)
    state=state.replace(agents=state.agents.replace(income=jnp.asarray([.25,.75,0.,0.]),active=jnp.zeros(4,dtype=bool)))
    assert policy_loss_fn is normalized_income_budget_loss
    assert float(jax.jit(policy_loss_fn)(state))==pytest.approx(-.25)
