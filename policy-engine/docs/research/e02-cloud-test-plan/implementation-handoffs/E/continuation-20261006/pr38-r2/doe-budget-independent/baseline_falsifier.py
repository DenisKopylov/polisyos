"""Independent exact old source falsifier, replacing SALib sample only with a counted spy."""
import hashlib,json,os,platform,subprocess,sys,time
from pathlib import Path
from unittest.mock import patch
import numpy as np
from polisyos.scientist.methods.doe.designs import ParameterSpec,SensitivityMethod,SensitivityPlan
from polisyos.scientist.methods.doe import sampling,analysis
from SALib.sample import morris,sobol,fast_sampler
BASE='a2677935015e8a0e7f2dfd5412b671e13fb3175a'
LANE=Path('/workspace/e02-E-continuation-20261006')
OUT=Path('/workspace/e02-E-pr38-r2-receipts/independent-cal-reviewer/doe-budget')
def git(*args):return subprocess.check_output(['git','-C',str(LANE),*args])
def sha(x):return hashlib.sha256(x).hexdigest()
paths=git('ls-files','policy-engine/src').decode().splitlines()
before={p:sha((LANE/p).read_bytes()) for p in paths}
assert all((LANE/p).read_bytes()==git('show',BASE+':'+p) for p in paths)
class BackendReached(RuntimeError):pass
cases=[]
for method,backend in [(SensitivityMethod.MORRIS,morris),(SensitivityMethod.SOBOL,sobol),(SensitivityMethod.FAST,fast_sampler)]:
 n=65 if method==SensitivityMethod.FAST else 2
 k=2; factor={SensitivityMethod.MORRIS:k+1,SensitivityMethod.SOBOL:2*k+2,SensitivityMethod.FAST:k}[method]
 cap=n*factor
 plan=SensitivityPlan(method=method,parameter_specs=[ParameterSpec(name=name,lower_bound=0,upper_bound=1) for name in ['x','z']],n_trajectories=n,max_estimated_runs=cap,seed=19,input_law='independent')
 assert plan.estimated_runs==cap
 plan.n_trajectories=n+1
 calls=[]
 def spy(*args,**kwargs):calls.append({'N':kwargs.get('N'),'num_vars':args[0]['num_vars']});raise BackendReached('real SALib sample inlet reached')
 for path in ['generate','identity']:
  calls.clear()
  with patch.object(backend,'sample',spy):
   try:
    if path=='generate':sampling.generate_sensitivity_samples(plan)
    else:analysis._analysis_identity(plan,np.zeros((cap,k)),np.zeros(cap))
    outcome='ACCEPTED_identity_without_budget_admission'
   except BackendReached:outcome='BACKEND_REACHED_before_budget_refusal'
   except Exception as e:outcome=type(e).__name__+':'+str(e)
  if path=='generate' or method==SensitivityMethod.SOBOL:assert calls==[{'N':n+1,'num_vars':k}]
  else:assert outcome=='ACCEPTED_identity_without_budget_admission' and not calls
  cases.append({'method':method.value,'path':path,'admitted_N':n,'mutated_N':n+1,'declared_cap':cap,'actual_estimated':(n+1)*factor,'backend_calls':list(calls),'evaluator_calls':0,'outcome':outcome,'property_outcome':'FAIL_expected_escape'})
assert all(before[p]==sha((LANE/p).read_bytes()) for p in paths)
origins={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith('polisyos') and getattr(m,'__file__',None)}
assert all(Path(p).is_relative_to(LANE/'policy-engine/src') and Path(p).read_bytes()==git('show',BASE+':'+str(Path(p).relative_to(LANE))) for p in origins.values())
result={'source':BASE,'tree':git('rev-parse',BASE+'^{tree}').decode().strip(),'module_source':{n:sha(Path(m.__file__).read_bytes()) for n,m in sys.modules.items() if n in ['polisyos.scientist.methods.doe.designs','polisyos.scientist.methods.doe.sampling','polisyos.scientist.methods.doe.analysis']},'tracked_source_count':len(paths),'tracked_source_digest':sha(json.dumps(before,sort_keys=True).encode()),'before_after_equal':True,'all_module_origins_exact_Git_blobs':True,'origin_count':len(origins),'environment':{'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'numpy':np.__version__,'SALib':'1.5.2','PYTHONPATH':os.environ.get('PYTHONPATH'),'backend_scope':'actual SALib inlet intercepted before allocation; no numeric estimator claim','no_caps':True},'cases':cases,'negative_control_basis':'Only sample function spy replaced; real generate/identity caller and admitted mutation execute exact old source.'}
(OUT/'baseline-a267-falsifier.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
