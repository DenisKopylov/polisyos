"""Independent native covariance positive/nullspace and pre-callback law refusal."""
import json, math, pathlib
import numpy as np
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.foundry.uncertainty.dispatcher import PropagationDispatcher
from polisyos.ir.analytics import DistributionFamily,IntervalSemantics,PropagationMethod,UncertaintyEnvelope,UncertaintySource
import polisyos.foundry.uncertainty.monte_carlo as native
assert pathlib.Path(native.__file__).is_relative_to('/workspace/e02-E-mc-20261006/policy-engine/src')
names=['a','b']
def laws(cov,family=DistributionFamily.NORMAL):
 return {name:UncertaintyEnvelope(point_estimate=0.,confidence_interval=(-1.96*math.sqrt(cov[i][i]),1.96*math.sqrt(cov[i][i])),confidence_level=.95,distribution_family=family,source=UncertaintySource.CALIBRATION,propagation_method=PropagationMethod.NONE,interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,gate_eligible=False,metadata={'std':math.sqrt(cov[i][i]),'covariance_params':names,'covariance_row':cov[i]}) for i,name in enumerate(names)}
records=[]
for method in ['random','sobol','halton']:
 cfg=PropagationConfig(mc_n_samples=4096,mc_sampling_method=method,mc_seed=31621,compute_sensitivity=False)
 for cov,label,sign,oracle in [([[.0025,.001],[.001,.01]],'full_covariance',1,.0145),([[.0025,.0025],[.0025,.0025]],'singular_nullspace',-1,0.)]:
  calls=[]
  def f(**p):
   calls.append((float(p['a']),float(p['b'])))
   return {'y':p['a']+sign*p['b']}
  r=MonteCarloPropagator(cfg).propagate(f,{'a':0.,'b':0.},laws(cov),['y'])[0]
  draws=np.array(calls[1:]); y=draws[:,0]+sign*draws[:,1]
  assert len(draws)>=4096
  observed=float(np.var(y)); assert abs(observed-oracle) < (.002 if oracle else 1e-18), (method,label,observed)
  assert not r.envelope.gate_eligible
  if not oracle: assert np.max(np.abs(y))<1e-9
  records.append({'method':method,'law':label,'oracle_variance':oracle,'actual_callback_draws':len(draws),'actual_variance':observed,'result':'PASS'})
 for cls in [MonteCarloPropagator,PropagationDispatcher]:
  calls=[]
  u=laws([[1/12,0],[0,1/12]],DistributionFamily.UNIFORM)
  u={n:e.model_copy(update={'point_estimate':.5,'confidence_interval':(0.,1.),'confidence_level':None,'interval_semantics':IntervalSemantics.DETERMINISTIC_BOUNDS}) for n,e in u.items()}
  r=cls(cfg).propagate(lambda **p:calls.append(p) or {'y':p['a']+p['b']},{'a':.5,'b':.5},u,['y'])[0]
  assert calls==[] and r.envelope.distribution_family is DistributionFamily.UNKNOWN and not r.envelope.gate_eligible
  assert r.envelope.metadata['failure']=='unsupported_joint_sampling_law'
  records.append({'method':method,'entry':cls.__name__,'law':'covariance_only_uniform','callback_count':0,'result':'typed_refusal'})
print(json.dumps({'source':'d69d2fad34de9923209fde3e20439e46f36f6750','independent_covariance_formula':'w.T @ C @ w; tied difference variance 0','records':records},indent=2))
