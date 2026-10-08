import copy,hashlib,importlib.util,json,math,pathlib,sys
import numpy as np
from statsmodels.api import OLS
from polisyos.foundry.methods.catalog.causal.did import StaggeredDifferenceInDifferences as Method
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.ir.analytics.causal import CausalEffectReport,load_causal_effect_report,persist_causal_effect_report
from polisyos.core.artifacts.store import FileSystemCAS
spec=importlib.util.spec_from_file_location('root_proposal', '/tmp/e02-F-continuation-20261006/cau/consumer-diagnostic-patch-proposal.py');proposal=importlib.util.module_from_spec(spec);spec.loader.exec_module(proposal)
timing=np.array([3,3,4,4,-1,-1,-1,-1]);y=np.tile(np.arange(6,dtype=float),(8,1));y[:4,:3]+=np.array([0.,.5,-.3]);y[:2,3:]+=np.array([1.,3.])[:,None];y[2:4,4:]+=np.array([2.,5.])[:,None];y[4:,3:]+=np.arange(4)[:,None]*.2
data=PanelObservationalData(outcome=y,treatment=(timing>=0).astype(int),time_treatment=2,treatment_timing=timing,unit_ids=np.arange(8));current=data.model_copy(update={'time_treatment':3})
old=Method.pure_step(data,{'n_bootstrap':99,'__rng__':np.random.default_rng(13)})['report'];fresh=Method.pure_step(current,{'n_bootstrap':99,'__rng__':np.random.default_rng(13)})['report'];proposal.verify_selected_did_diagnostics({'report':fresh},observational_data=current)
store=FileSystemCAS(pathlib.Path('/tmp/e02-F-continuation-20261006/cau/current-consumer-cas'));ref=persist_causal_effect_report(store,fresh);loaded=load_causal_effect_report(FileSystemCAS(pathlib.Path('/tmp/e02-F-continuation-20261006/cau/current-consumer-cas')),ref);proposal.verify_selected_did_diagnostics({'report':loaded},observational_data=current)
rejections=[]
def reject(name,report):
 try:proposal.verify_selected_did_diagnostics({'report':report},observational_data=current)
 except ValueError as e:rejections.append({'control':name,'outcome':'REFUSED','reason':str(e)});return
 raise AssertionError(name+' accepted')
reject('time_treatment-only stale report with same scalar markers',old)
for field,value in [('statistic',99.),('p_value',.99),('passed',not fresh.diagnostics[0].passed),('details',{'status':'no_detected_pretrend','identification_authority':True})]:
 payload=copy.deepcopy(fresh.model_dump(mode='json'));payload['diagnostics'][0][field]=value;assert payload['method_params']==fresh.model_dump(mode='json')['method_params'];reject('diagnostic-only '+field,payload)
# Make all offered diagnostic result hashes coherent, but keep the genuine scalar target.
payload=copy.deepcopy(fresh.model_dump(mode='json'));payload['diagnostics'][0]['p_value']=.99;contract=payload['method_params']['diagnostic_contract'];contract['diagnostics']=payload['diagnostics'];canonical=lambda x:json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode();contract['result_sha256']=hashlib.sha256(canonical(payload['diagnostics'])).hexdigest();payload['method_params']['diagnostic_binding']=hashlib.sha256(canonical(contract)).hexdigest();reject('coherent diagnostic forged-result hashes',payload)
oracles=[]
for t0 in [3,4,5]:
 d=current.model_copy(update={'time_treatment':t0});diag=Method._diagnostic_contract(d)['diagnostic_contract']['diagnostics'][0];delta=np.array([sum(y[i,t] for i in range(4))/4-sum(y[i,t] for i in range(4,8))/4 for t in range(t0)]);reference=OLS(delta,np.array([[1.,t] for t in range(t0)])).fit(cov_type='HC1');slope=float(reference.params[1]);se=float(reference.bse[1]);p=math.erfc(abs(slope/se)/math.sqrt(2));assert np.isclose(diag['statistic'],slope,rtol=1e-12,atol=1e-14);assert np.isclose(diag['details']['slope_se'],se,rtol=1e-12,atol=1e-14);assert np.isclose(diag['p_value'],p,rtol=1e-12,atol=1e-14);oracles.append({'t0':t0,'slope':slope,'HC1_se':se,'normal_p':p,'owner_diagnostic':diag})
print(json.dumps({'producer_module':sys.modules[Method.__module__].__file__,'current_input_positive':'PASS','actual_CAS_fresh_reader_positive':'PASS','rejections':rejections,'independent_actual_statsmodels_oracles':oracles,'limitation':'Portable proposed root function only, not whole admitted Scientist Node; nonrejection and content binding confer no identification authority.'},indent=2))
