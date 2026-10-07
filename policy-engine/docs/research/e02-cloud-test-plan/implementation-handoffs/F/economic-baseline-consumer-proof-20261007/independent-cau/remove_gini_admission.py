import sys,json,platform
import jax.numpy as jnp
from polisyos.foundry.agent_sim import distributions as owner
original=owner._admit_gini_population

def no_admission(values,active):
 return jnp.where(active,values,0.0)
# Same canonical function object, native return type, name/module/signature and
# every other producer/consumer intact; only population-domain refusal removed.
original.__code__=no_admission.__code__
assert owner._admit_gini_population is original
import pytest
print(json.dumps({'python':platform.python_version(),'owner':owner.__file__,'removed':'canonical active-population domain refusal only','unchanged':'native actor/labor/tax/state/plugin/PPO/current metric consumers; no site/source writes'}),flush=True)
raise SystemExit(pytest.main(['-q','-s','-o','addopts=','-p','no:cacheprovider','tests/unit/foundry/agent_sim/test_signed_gini_producer_route.py','-k','actual_bridge_and_ppo_refuse']))
