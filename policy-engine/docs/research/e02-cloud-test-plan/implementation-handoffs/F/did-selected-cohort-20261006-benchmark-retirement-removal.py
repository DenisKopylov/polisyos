import importlib,json,sys,numpy as np
from polisyos.foundry.methods.catalog.causal.did import DifferenceInDifferences,StandardDifferenceInDifferences
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData

def retired(*args,**kwargs):raise AssertionError('Actual maintained caller reached historical aggregate producer')
DifferenceInDifferences.pure_step=retired
outcome=np.tile(np.arange(5,dtype=float),(8,1));outcome[:3,3:]+=3.
data=PanelObservationalData(outcome=outcome,treatment=np.array([1,1,1,0,0,0,0,0]),time_treatment=3,unit_ids=np.arange(8))
rows=[]
for name,runner,key in [('benchmarks.interference.policy_did_interference','_runner_did','artifact'),('benchmarks.natural_experiments.policy_natural_experiments','_runner_standard_did','report')]:
 module=importlib.import_module(name)
 report=getattr(module,runner)(data,seed=19)[key]
 assert report.point_estimate==3.0000000000000013 or abs(report.point_estimate-3.)<1e-12
 assert report.method_params['covariance_procedure']=='hc1'
 # Remove the actual consumer's dedicated binding in this process only. Production
 # source/signature/metadata remain byte-identical; no marker bypass substitutes an estimator.
 module.StandardDifferenceInDifferences=DifferenceInDifferences
 try:getattr(module,runner)(data,seed=19)
 except AssertionError as exc:rows.append({'consumer':name+'.'+runner,'native_ATT':report.point_estimate,'native_status':report.status.value,'removal':'REJECTED','actual_consumer_rejection':str(exc),'canonical_registered_fqn':StandardDifferenceInDifferences.signature.fqn})
 else:raise AssertionError('Removal failed to exercise retired producer')
print(json.dumps({'outcome':'EXPECTED_REMOVAL_REJECTION','consumers':rows},indent=2))
sys.exit(1)
