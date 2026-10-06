"""Independent five-inlet real-domain oracle, covariance callback and pilot controls."""
from pathlib import Path
from fractions import Fraction
import hashlib,importlib,json,math,os,subprocess,sys,warnings
import numpy as np
R=Path('/workspace/e02-E-continuation-20261006');S=R/'policy-engine/src';REF='ec042402ec91fbdcb51006852e29fe67f38d9452';O=Path(__file__).parent
import polisyos.foundry.uncertainty as f
from polisyos.foundry.uncertainty import sampling_admission as c
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import DistributionFamily,IntervalSemantics,PropagationMethod,UncertaintyEnvelope,UncertaintySource
property_paths=['policy-engine/src/polisyos/foundry/uncertainty/sampling_admission.py','policy-engine/src/polisyos/foundry/uncertainty/__init__.py','policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py'];before={}
for p in property_paths:
 expected=subprocess.check_output(['git','show',REF+':'+p],cwd=R);assert (R/p).read_bytes()==expected;before[p]=hashlib.sha256(expected).hexdigest()
mutant=os.environ.get('REMOVE_REAL_DOMAIN_GUARD')=='1'
if mutant:
 def unsafe_real(values):return np.asarray(values,dtype=np.float64)
 c._real_float64.__code__=unsafe_real.__code__
# Canonical object identity and the 19-name package contract survive removal.
for name in ['admit_empirical_weights','empirical_cdf','admit_unit_uniform']:assert getattr(f,name) is getattr(c,name) and name in f.__all__
assert len(f.__all__)==19
properties=[];refusals=[]
plan=c.BoundedIIDMeanPlan(metric_id='fixture-y',pilot_samples=256)
epsilon=.05;m=256;delta_pilot=delta_main=.025;a=math.sqrt(math.log(4/delta_pilot)/(2*m));variance=min(.25,max(0.,a));n=math.ceil((2*variance+2*epsilon/3)*math.log(2/delta_main)/(epsilon**2));u,N=c.frozen_bernstein_budget(np.zeros(m),plan);assert u==variance and N==n==408
properties.append({'property':'independent-all-zero-IID-pilot-mean-oracle','U':u,'N':N,'outcome':'PASS','authority':'numerical formula only; actual independent bounded law required separately'})
for inlet,call in [('weights',lambda values:f.admit_empirical_weights(values,2)),('CDF',f.empirical_cdf),('uniform',f.admit_unit_uniform),('range',c.admit_float32_range),('pilot',lambda values:c.frozen_bernstein_budget(values,c.BoundedIIDMeanPlan(metric_id='y',pilot_samples=2)))]:
 for label,value in [('nonzero-imag',np.array([.5+.1j,.5-.1j])),('zero-imag',np.array([.5+0j,.5+0j])),('object-complex',np.array([.5+.1j,.5-.1j],dtype=object)),('strings',np.array(['.5','.5'])),('datetime',np.array(['2026-10-06','2026-10-07'],dtype='datetime64[D]'))]:
  with warnings.catch_warnings(record=True) as observed:
   warnings.simplefilter('always')
   try:call(value)
   except ValueError as exc:assert 'real numeric' in str(exc);assert not observed;refusals.append({'inlet':inlet,'case':label,'exception':'ValueError','warnings':0})
   else:raise AssertionError('removed real-domain guard admitted '+inlet+'/'+label)
properties.append({'property':'five-common-inlets-non-real-refusal-before-cast','cases':len(refusals),'outcome':'PASS'})
for values in [np.array([1,1,2],np.int64),np.array([1,1,2],np.float32),np.array([1,1,2],np.float64),np.array([Fraction(1),Fraction(1),Fraction(2)],object)]:
 p=f.admit_empirical_weights(values,3);np.testing.assert_array_equal(p,[.25,.25,.5]);np.testing.assert_array_equal(f.empirical_cdf(p),[.25,.5,1.])
properties.append({'property':'supported-real-int-float32-float64-Fraction-object-dyadic-law','outcome':'PASS'})
calls=[];env=UncertaintyEnvelope(point_estimate=0.,confidence_interval=(-1.96,1.96),confidence_level=.95,distribution_family=DistributionFamily.NORMAL,source=UncertaintySource.CALIBRATION,propagation_method=PropagationMethod.NONE,interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,gate_eligible=False,metadata={'std':1.,'covariance_params':['x'],'covariance_row':np.array([1.+5j])})
r=MonteCarloPropagator(f.PropagationConfig(mc_n_samples=100,compute_sensitivity=False)).propagate(lambda **p:calls.append(p) or {'y':p['x']},{'x':0.},{'x':env},['y'])[0];assert calls==[] and r.envelope.distribution_family is DistributionFamily.UNKNOWN and not r.envelope.gate_eligible
properties.append({'property':'actual-native-MC-complex-covariance-pre-nominal-refusal','callback_count':0,'family':r.envelope.distribution_family.value,'gate_eligible':False,'outcome':'PASS'})
modules=[]
for name,module in sorted(sys.modules.items()):
 if name.startswith('polisyos.') and getattr(module,'__file__',None):
  path=Path(module.__file__).resolve();assert path.is_relative_to(S);rel='policy-engine/src/'+str(path.relative_to(S));expected=subprocess.check_output(['git','show',REF+':'+rel],cwd=R);assert path.read_bytes()==expected;modules.append({'module':name,'path':rel,'sha256':hashlib.sha256(expected).hexdigest()})
for p,h in before.items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h
result={'source_sha':REF,'source_tree':subprocess.check_output(['git','rev-parse',REF+'^{tree}'],cwd=R,text=True).strip(),'properties':properties,'refusals':refusals,'module_origin_count':len(modules),'module_origins':modules,'source_property_paths':before,'source_before_after_equal':True,'verdict':'GO-bounded-common-real-domain-property','new_Welfare_consumer':'UNRUN-pending-frozen-source','no_finding_closure_or_law_authority':True}
(O/'real-domain-independent-probe.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['source_sha','source_tree','properties','module_origin_count','source_property_paths','source_before_after_equal','verdict']},indent=2))
