from __future__ import annotations
from fractions import Fraction
import hashlib, json, pathlib, platform, random, sys
import jax, jax.numpy as jnp, numpy as np
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.plugins.economics.baselines import normalized_income_budget_loss as evaluate
from polisyos.foundry.methods.loss import policy_loss_fn as public_alias
from polisyos.foundry.methods._internal.loss import policy_loss_fn as internal_alias
assert evaluate is public_alias is internal_alias
if '--remove-normalization' in sys.argv:
 def missing_normalization(final_state,min_balance=-1000.0):
  incomes=jnp.asarray(final_state.agents.income,dtype=jnp.float32)
  minimum=jnp.asarray(min_balance,dtype=jnp.float32)
  violation=jnp.maximum(0.,minimum-final_state.government_balance)/jnp.maximum(jnp.abs(minimum),1.)
  return -jnp.mean(incomes)+10.*jnp.square(violation)
 evaluate.__code__=missing_normalization.__code__
assert evaluate is public_alias is internal_alias
rng=random.Random(3507);records=[]
compiled=jax.jit(evaluate)
for count in [1,3,7,31]:
 for replicate in range(8):
  values=[Fraction(rng.randint(-200,200),8) for _ in range(count)]
  minimum=Fraction(rng.choice([-1000,0,17]),4)
  balance=minimum-Fraction(rng.randint(-100,100),4)
  mean=sum(values)/count;scale=max(sum(abs(x) for x in values)/count,Fraction(1));penalty=max(minimum-balance,Fraction(0))/max(abs(minimum),Fraction(1));expected=-mean/scale+10*penalty*penalty
  state=GlobalState.empty(n_agents=count,n_firms=1)
  state=state.replace(agents=state.agents.replace(income=jnp.asarray([float(v) for v in values],dtype=jnp.float32)),government_balance=jnp.asarray(float(balance),dtype=jnp.float32))
  observations=[float(evaluate(state,min_balance=float(minimum))),float(compiled(state,min_balance=float(minimum)))]
  print(json.dumps({'count':count,'replicate':replicate,'income_rationals':[str(v) for v in values],'minimum':str(minimum),'balance':str(balance),'expected_rational':str(expected),'eager_jit':observations}),flush=True)
  np.testing.assert_allclose(observations,float(expected),rtol=3e-6,atol=2e-6)
  records.append(observations)
def loss(values):
 state=GlobalState.empty(n_agents=2,n_firms=1)
 state=state.replace(agents=state.agents.replace(income=values),government_balance=jnp.asarray(0.,dtype=jnp.float32))
 return evaluate(state,min_balance=100.)
for values,expected in [([-.25,.5],[-.5,-.5]),([-2.,4.],[-2/9,-1/9])]:
 gradient=np.asarray(jax.grad(loss)(jnp.asarray(values,dtype=jnp.float32)));np.testing.assert_allclose(gradient,expected,rtol=2e-6,atol=1e-6);print(json.dumps({'independent_analytic_gradient':expected,'native_gradient':gradient.tolist(),'income':values}),flush=True)
import polisyos.foundry.plugins.economics.baselines as owner
print(json.dumps({'check':'PASS','exact_fraction_panels':32,'native_eager_jit_comparisons':64,'analytic_gradient_cases':2,'aliases_identical':True,'python':platform.python_version(),'jax':jax.__version__,'owner':owner.__file__,'owner_sha256':hashlib.sha256(pathlib.Path(owner.__file__).read_bytes()).hexdigest(),'authority':'original finite baseline formula only; no welfare/optimizer/production authority'}))
