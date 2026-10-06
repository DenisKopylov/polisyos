import ast
import json
import subprocess
import sys

import jax.numpy as jnp
import numpy as np
import pytest

import polisyos.foundry.agent_sim.distributions as distribution
import polisyos.foundry.agent_sim.state as agent_state
import polisyos.foundry.agent_sim.wiring.executors as wiring
import polisyos.foundry.plugins.economics.state as economic

mode = sys.argv[1]
base = '198076863e143dea9f89f02734b13d50dae3eed5'
path = 'policy-engine/src/polisyos/foundry/agent_sim/state.py' if mode == 'aggregate' else 'policy-engine/src/polisyos/foundry/agent_sim/distributions.py'
source = subprocess.check_output(['git','show',f'{base}:{path}'],text=True) if mode in {'epsilon','aggregate'} else open('src/polisyos/foundry/agent_sim/distributions.py').read()
parsed = ast.parse(source)
function_name = '_gini_from_values' if mode == 'aggregate' else 'compute_gini_hard'
node = next(node for node in parsed.body if isinstance(node,ast.FunctionDef) and node.name == function_name)
function_source = ast.get_source_segment(source,node)
if mode == 'normalization':
    old = 'normalized = sorted_values / jnp.where(scale == 0, 1.0, scale)'
    assert old in function_source
    function_source = function_source.replace(old,'normalized = sorted_values')
namespace = dict(agent_state.__dict__ if mode == 'aggregate' else distribution.__dict__)
exec(compile(function_source, f'<remove-{mode}-retain-public-name-and-dtype>', 'exec'),namespace)
mutant = namespace[function_name]
if mode == 'aggregate':
    agent_state._gini_from_values = mutant
else:
    distribution.compute_gini_hard = mutant
    economic.compute_gini_hard = mutant
    wiring.compute_gini_hard = mutant
ordinary = mutant(jnp.asarray([1.,2.,3.]), jnp.ones(3,dtype=jnp.bool_))
assert mutant.__name__ == function_name
assert ordinary.shape == () and ordinary.dtype == jnp.float32 and np.isfinite(float(ordinary))
print(json.dumps({'mode':mode,'cheap_proxy':'same public name, scalar shape, float32 dtype and finite ordinary output','proxy_outcome':'PASS','ordinary':float(ordinary)}),flush=True)
test = 'tests/unit/foundry/agent_sim/test_gini_science.py'
if mode == 'aggregate':
    targets = [test+'::test_native_aggregate_and_pure_executor_share_active_population_oracle']
else:
    targets = [test+'::test_exact_gini_matches_pairwise_oracle_across_units[profile0-1e-12-eager-float32]',test+'::test_exact_gini_exhaustive_small_nonnegative_population[eager]',test+'::test_scientific_statistic_reaches_native_plugin_and_global_state_consumers'] if mode == 'epsilon' else [test+'::test_float32_gini_normalizes_before_sum_overflow',test+'::test_float64_gini_survives_extreme_finite_rescaling']
code = pytest.main([*targets,'-o','addopts=','-v','--tb=short'])
print(json.dumps({'mode':mode,'property_deleted':True,'expected_test_returncode':1,'actual_test_returncode':int(code),'removal_rejected':int(code)==1}),flush=True)
raise SystemExit(0 if int(code)==1 else 1)
