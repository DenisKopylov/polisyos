"""Exact Git baseline/removal controls with native callers and unchanged markers."""
from __future__ import annotations
import hashlib
import importlib
import json
import subprocess
import sys
import types
import jax
import jax.numpy as jnp
import pytest

BASE = 'fb51511fef60c5123875e99ab2f19a9a0bd5d16f'
mode = sys.argv[1]
modules = {
    'polisyos.foundry.agent_sim.distributions': ['compute_gini_hard','compute_gini_soft','compute_gini_proxy','compute_distribution_aware_reward'],
    'polisyos.foundry.agent_sim.analysis': ['BehaviorAnalyzer.counterfactual_analysis'],
    'polisyos.foundry.agent_sim.credit_assignment': ['CentralizedCritic.build_global_observations'],
    'polisyos.foundry.agent_sim.metrics': ['standard_training_metrics'],
    'polisyos.foundry.agent_sim.modes': ['social_welfare_objective'],
    'polisyos.foundry.agent_sim.government_policy': ['build_government_welfare_reward'],
    'polisyos.foundry.methods.catalog.simulation.dynamics': ['AgentPopulationSimulationEstimator.pure_step'],
    'polisyos.foundry.plugins.economics.objectives': ['GiniObjective.evaluate','SocialWelfareObjective.evaluate'],
    'polisyos.foundry.plugins.economics.plugin': ['EconomicsPlugin._viz_wealth_distribution'],
}
restored=[]
if mode == 'base':
    for name, functions in modules.items():
        mod=importlib.import_module(name)
        path='policy-engine/src/'+name.replace('.','/')+'.py'
        blob=subprocess.check_output(['git','show',BASE+':'+path])
        ns=dict(vars(mod))
        exec(compile(blob, BASE+':'+path, 'exec'), ns)
        for function in functions:
            if '.' in function:
                cls, member=function.split('.')
                raw=vars(ns[cls])[member]
                setattr(getattr(mod,cls),member,raw)
            else:
                setattr(mod,function,ns[function])
        restored.append(dict(module=name,path=path,source_sha=BASE,bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest(),functions=functions))
    from polisyos.foundry.agent_sim.distributions import compute_gini_hard
    from polisyos.foundry.agent_sim.state import GlobalState,compute_aggregates
    from polisyos.foundry.plugins.economics import EconomicState
    values=[]
    for pair in ([-2.,1.],[-1.,2.]):
        a=jnp.asarray(pair); mask=jnp.ones(2,dtype=bool)
        state=GlobalState.empty(n_agents=2).replace(agents=GlobalState.empty(n_agents=2).agents.replace(wealth=a))
        economic=EconomicState.empty(n_agents=2,seed=7)
        economic=economic.replace(agents=economic.agents.replace(wealth=a)).update_aggregates()
        values.append(dict(input=pair,helper=float(compute_gini_hard(a,mask)),actual_aggregate=float(compute_aggregates(state.agents,compute_gini=True).gini_coefficient),plugin_aggregate=float(economic.distributions.gini_wealth)))
    print(json.dumps(dict(mode=mode,source_bindings=restored,signed_reproduction=values),indent=2),flush=True)
    args=['tests/unit/foundry/agent_sim/test_gini_domain.py','tests/unit/foundry/agent_sim/test_gini_consumers.py']
elif mode == 'admission-removal':
    mod=importlib.import_module('polisyos.foundry.agent_sim.distributions')
    original=mod._admit_gini_population
    # The name, signature, docstring and canonical refusal message remain present.
    original.__code__=(lambda values,active:jnp.where(active,values,0.0)).__code__
    print(json.dumps(dict(mode=mode,marker_preserved=hasattr(mod,'_admit_gini_population'),function_name=original.__name__,hard_owner=mod.compute_gini_hard.__qualname__)),flush=True)
    args=['tests/unit/foundry/agent_sim/test_gini_domain.py::test_classical_gini_refuses_invalid_active_population']
elif mode == 'cache-removal':
    mod=importlib.import_module('polisyos.foundry.plugins.economics.objectives')
    mod.GiniObjective.evaluate.__code__=(lambda self,state:state.distributions.gini_wealth).__code__
    print(json.dumps(dict(mode=mode,marker_preserved=mod.GiniObjective.evaluate.__name__=='evaluate',original_maximize=mod.GiniObjective().maximize)),flush=True)
    args=['tests/unit/foundry/agent_sim/test_gini_domain.py::test_registered_objective_refuses_current_signed_population_despite_valid_cached_metric','tests/unit/foundry/agent_sim/test_gini_domain.py::test_composite_interaction_current_population_is_admitted_at_registered_objective','tests/unit/foundry/agent_sim/test_gini_consumers.py::test_social_welfare_uses_current_gini_with_original_sign_and_weight']
elif mode == 'fiscal-removal':
    mod=importlib.import_module('polisyos.foundry.execute.mechanisms.fiscal')
    original=mod.IncomeTax.emit_patches
    def zero_debit(self,state,rng_key,target_mask=None):
        patch,key=original(self,state,rng_key,target_mask=target_mask)
        for record in patch['agents.income']:
            record['delta']=jnp.zeros_like(record['delta'])
        return patch,key
    mod.IncomeTax.emit_patches=zero_debit
    print(json.dumps(dict(mode=mode,class_name=mod.IncomeTax.__qualname__,preserved_patch_keys=['agents.income','government.balance'])),flush=True)
    args=['tests/unit/foundry/plugins/test_economic_profiles.py::test_registered_fiscal_producer_full_patch_reaches_state_consumer','tests/unit/foundry/plugins/test_economic_profile_consumers.py::test_registered_progressive_tax_complete_state_budget_and_step_profile']
else:
    raise SystemExit('unknown mode '+mode)
args += sys.argv[2:]
raise SystemExit(pytest.main(args))
