import ast,hashlib,json,pathlib,subprocess,sys
import numpy as np
from polisyos.foundry.methods.catalog.causal.did import StaggeredDifferenceInDifferences
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.ir.analytics.causal import CausalEffectReport,EstimationStatus,load_causal_effect_report,persist_causal_effect_report
from polisyos.core.artifacts.store import FileSystemCAS
base='4c5a11ff8050c6108f6753177b96e6714cef401f';consumer='421f1dd977b237307394c68820caab4156716eb2';path='policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py'
raw=subprocess.check_output(['git','show',consumer+':'+path]);tree=ast.parse(raw);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_verify_selected_did_target');ns={'Any':object,'PanelObservationalData':PanelObservationalData,'CausalEffectReport':CausalEffectReport,'EstimationStatus':EstimationStatus,'StaggeredDifferenceInDifferences':StaggeredDifferenceInDifferences};exec(compile(ast.Module(body=[node],type_ignores=[]),consumer+':'+path,'exec'),ns)
timing=np.array([3,3,4,4,-1,-1,-1,-1]);y=np.tile(np.arange(6,dtype=float),(8,1));y[:4,:3]+=np.array([0.,.5,-.3]);y[:2,3:]+=np.array([1.,3.])[:,None];y[2:4,4:]+=np.array([2.,5.])[:,None];y[4:,3:]+=np.arange(4)[:,None]*.2
data=PanelObservationalData(outcome=y,treatment=(timing>=0).astype(int),time_treatment=2,treatment_timing=timing,unit_ids=np.arange(8));changed=data.model_copy(update={'time_treatment':3});params={'n_bootstrap':99};outputs=[]
for d in [data,changed]:outputs.append(StaggeredDifferenceInDifferences.pure_step(d,{**params,'__rng__':np.random.default_rng(13)}))
a,b=[o['report'] for o in outputs];assert a.status is b.status is EstimationStatus.SUCCESS
assert a.point_estimate==b.point_estimate and a.method_params['target_binding']==b.method_params['target_binding'];assert a.diagnostics!=b.diagnostics
cas=FileSystemCAS(pathlib.Path('/tmp/e02-F-continuation-20261006/cau/base-probe-cas'));ref=persist_causal_effect_report(cas,a);fresh=load_causal_effect_report(FileSystemCAS(cas.base_path if hasattr(cas,'base_path') else pathlib.Path('/tmp/e02-F-continuation-20261006/cau/base-probe-cas')),ref)
ns['_verify_selected_did_target']({'report':fresh},observational_data=changed,params=params)
print(json.dumps({'producer_source':base,'consumer_source':consumer,'consumer_path':path,'consumer_source_sha256':hashlib.sha256(raw).hexdigest(),'producer_module':sys.modules[StaggeredDifferenceInDifferences.__module__].__file__,'theta':a.point_estimate,'theta_and_markers_unchanged':True,'old_diagnostic':[d.model_dump(mode='json') for d in a.diagnostics],'current_diagnostic':[d.model_dump(mode='json') for d in b.diagnostics],'actual_consumer_helper_after_actual_CAS_fresh_read':'ACCEPTS_STALE_DIAGNOSTIC','scope':'exact native helper source AST executed without changes against candidate classes; whole Scientist job/Node UNRUN'},indent=2))
