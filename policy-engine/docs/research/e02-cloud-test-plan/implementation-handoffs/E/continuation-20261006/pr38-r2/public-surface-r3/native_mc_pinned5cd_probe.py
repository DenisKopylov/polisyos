"""Small actual native MC consumer of canonical exported helper objects."""
from collections import Counter
from pathlib import Path
import hashlib,importlib,json,os,subprocess,sys
import numpy as np
import polisyos.foundry.uncertainty as f
from polisyos.foundry.uncertainty.sampling_admission import joint_carrier_digest
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import DistributionFamily,IntervalSemantics,NumericPolicySpec,NumericToleranceMode,PosteriorSamplesCarrier,PropagationMethod,UncertaintyEnvelope,UncertaintySource,persist_uncertainty_envelope,load_uncertainty_envelope
from polisyos.core.artifacts import FileSystemCAS
R=Path('/workspace/e02-E-continuation-20261006');REF='5cdfe613bf91fffbd578848c9e2f8275edc21ee7';O=Path(__file__).parent;mutant=os.environ.get('REMOVE_CDF_GUARD')=='1'
c=importlib.import_module('polisyos.foundry.uncertainty.sampling_admission');assert f.empirical_cdf is c.empirical_cdf
property_paths=['policy-engine/src/polisyos/foundry/uncertainty/sampling_admission.py','policy-engine/src/polisyos/foundry/uncertainty/__init__.py','policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py'];before={}
for path in property_paths:
 expected=subprocess.check_output(['git','show',REF+':'+path],cwd=R);assert (R/path).read_bytes()==expected;before[path]=hashlib.sha256(expected).hexdigest()
if mutant:
 def unsafe_cdf(probabilities):return np.cumsum(np.asarray(probabilities,dtype=np.float64),dtype=np.float64)
 f.empirical_cdf.__code__=unsafe_cdf.__code__
 assert f.empirical_cdf is c.empirical_cdf and 'empirical_cdf' in f.__all__
def inputs(weights):
 names=['a','b'];ids=['draw0','draw1','draw2'];result={}
 for n,p,s in [('a',2.25,(0.,1.,4.)),('b',3.,(0.,2.,5.))]:
  result[n]=UncertaintyEnvelope(point_estimate=p,confidence_interval=(0.,5.),confidence_level=None,distribution_family=DistributionFamily.BOOTSTRAP,source=UncertaintySource.ENSEMBLE,propagation_method=PropagationMethod.NONE,interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,gate_eligible=False,numeric_policy=NumericPolicySpec(mode=NumericToleranceMode.DECIMAL_EXACT),distribution_payload=PosteriorSamplesCarrier(samples=s,weights=weights))
 digest=joint_carrier_digest(names,result,ids)
 return {n:e.model_copy(update={'metadata':{'joint_sample_id':'independent-export-oracle','joint_draw_ids':ids,'joint_parameter_order':names,'joint_law_sha256':digest}}) for n,e in result.items()}
store=FileSystemCAS(O/('cas-5cd-mc-'+('removed' if mutant else 'positive')));results=[]
for label,weights in [('dyadic',(1.,1.,2.)),('collapsed',(.5,1e-20,.5))]:
 source=inputs(weights);refs={n:persist_uncertainty_envelope(store,e) for n,e in source.items()};fresh={n:load_uncertainty_envelope(FileSystemCAS(store.root),r) for n,r in refs.items()};calls=[]
 result=MonteCarloPropagator(f.PropagationConfig(mc_n_samples=256,mc_sampling_method='sobol',mc_qmc_scramble=False,compute_sensitivity=False)).propagate(lambda **p:calls.append((float(p['a']),float(p['b']))) or {'y':p['a']+p['b']},{'a':2.25,'b':3.},fresh,['y'])[0]
 if label=='dyadic':
  assert len(calls)==257;assert Counter(calls[1:])=={(0.,0.):64,(1.,2.):64,(4.,5.):128};draws=np.asarray(result.envelope.distribution_payload.samples);assert draws.mean()==5.25 and draws.var()==15.1875 and not result.envelope.gate_eligible
  results.append({'fixture':label,'callback_count':len(calls),'nominal_count':1,'actual_draw_rows':{str(k):v for k,v in Counter(calls[1:]).items()},'mean':float(draws.mean()),'variance':float(draws.var()),'gate_eligible':False})
 else:
  print(json.dumps({'fixture':label,'callback_count':len(calls),'family':result.envelope.distribution_family.value,'gate_eligible':result.envelope.gate_eligible,'removed_guard':mutant}),flush=True)
  assert calls==[], 'collapsed-law admission guard removed: actual native producer reached callbacks'
  assert result.envelope.distribution_family is DistributionFamily.UNKNOWN and not result.envelope.gate_eligible
  results.append({'fixture':label,'callback_count':0,'family':result.envelope.distribution_family.value,'gate_eligible':False})
print(json.dumps({'source_sha':REF,'real_native_consumer':'MonteCarloPropagator→configuredCAS persisted envelope→fresh read→257 callback dyadic positive /0 callbacks collapsed-law refusal','results':results,'new_actual_Welfare_consumer':'UNRUN-pending-frozen-source'},indent=2))

for path,h in before.items():assert hashlib.sha256((R/path).read_bytes()).hexdigest()==h
print(json.dumps({'source_property_paths':before,'before_after_equal':True},indent=2))
