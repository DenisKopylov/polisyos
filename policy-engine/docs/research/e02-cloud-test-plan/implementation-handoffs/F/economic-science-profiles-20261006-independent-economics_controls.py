import json, numpy as np, jax, jax.numpy as jnp
from polisyos.foundry.agent_sim.distributions import compute_gini_hard
from polisyos.foundry.agent_sim.state import _gini_from_values
count=0
with jax.experimental.enable_x64():
 for n in (1,3,7,25):
  rng=np.random.default_rng(411+n)
  values=rng.uniform(.05,3,n)
  mask=rng.random(n)>.3
  if not mask.any():mask[0]=True
  for scale in (1e-250,1e-12,1.,1e250):
   v=values*scale;a=v[mask]/np.max(v[mask])
   expected=np.abs(a[:,None]-a[None,:]).sum()/(2*len(a)*a.sum())
   padded=np.r_[v,np.nan,np.inf,0.]
   active=np.r_[mask,False,False,False]
   for f in (compute_gini_hard,jax.jit(compute_gini_hard),_gini_from_values,jax.jit(_gini_from_values)):
    actual=float(f(jnp.asarray(padded),jnp.asarray(active)))
    assert np.isclose(actual,expected,rtol=1e-12,atol=1e-12),(n,scale,actual,expected)
    count+=1
 for f in (compute_gini_hard,_gini_from_values):
  assert float(f(jnp.zeros(3),jnp.ones(3,dtype=bool)))==0
  assert np.isnan(float(f(jnp.array([-1.,1.,0.]),jnp.ones(3,dtype=bool))))
  count+=2
print(json.dumps({'checks':count,'result':'PASS','oracle':'independent pairwise formula; actual eager/JIT owners and aggregate padding law','source':compute_gini_hard.__code__.co_filename}))
