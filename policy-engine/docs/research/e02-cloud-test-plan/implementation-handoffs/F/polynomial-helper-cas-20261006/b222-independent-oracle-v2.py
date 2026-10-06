"""Independent cubic fit/query/twin oracle and unavailable nonlinear-posterior falsifier."""
import hashlib,json,pathlib,subprocess,numpy as np
from polisyos.core.artifacts import FileSystemCAS,PutOptions
from polisyos.core.canon import CanonSpec,from_canonical_bytes
from polisyos.foundry.methods.catalog.causal.gcm_fit import _fit_additive_noise_poly,HybridSCMFit
from polisyos.foundry.methods.catalog.causal.gcm_query import GCMQuery
from polisyos.foundry.methods.catalog.causal.protocols import SCMFitData,SCMQueryData,TwinNetworkQueryData
from polisyos.foundry.methods.catalog.causal.twin_network_query import TwinNetworkQuery
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal_graph import CausalGraphModel,CausalEdge,GraphType
from polisyos.ir.analytics.causal_queries import CausalQuery,CausalQueryResult
from polisyos.ir.analytics.structural_causal_model import MechanismFamily,MechanismSource,NodeMechanism,StructuralCausalModelSpec,persist_structural_causal_model_spec,load_structural_causal_model_spec
from polisyos.ir.analytics.twin_network import TwinNetworkResult
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job
store=FileSystemCAS('/tmp/e02-F-continuation-20261006/cau/b222-independent-oracle-cas')
x=np.linspace(-2,2,41);y=2+3*x-.5*x*x+.25*x*x*x
graph=CausalGraphModel(graph_type=GraphType.DAG,nodes=['X','Y'],edges=[CausalEdge(src='X',dst='Y')])
source=store.put_json({'data':np.column_stack([x,y]).tolist(),'columns':['X','Y']},PutOptions(kind='tests.cubic_rows',media_type='application/json'),canon_spec=CanonSpec(forbid_floats=False))
rows=np.asarray(from_canonical_bytes(store.get_bytes(source))['data']);params=_fit_additive_noise_poly(rows[:,1],rows[:,:1],['X'],degree=3)
assert params['fit_mode']=='additive_noise_poly'
for key,value in {'__intercept__':2.,'X^1':3.,'X^2':-.5,'X^3':.25}.items():assert abs(params['poly_coefficients'][key]-value)<1e-11
model=StructuralCausalModelSpec(schema_version='1.0',graph=graph,fitted=True,fit_method='manual',mechanisms=[NodeMechanism(variable='X',family=MechanismFamily.EMPIRICAL,family_params={'mean':float(x.mean()),'std':float(x.std()),'observed_samples':x.tolist(),'observed_samples_source':str(source.artifact_id),'observed_sample_alignment':str(source.artifact_id),'joint_sample_group':str(source.artifact_id)},source=MechanismSource.DATA_FITTED),NodeMechanism(variable='Y',parents=['X'],family=MechanismFamily.ADDITIVE_NOISE,family_params=params,source=MechanismSource.DATA_FITTED)])
model_ref=persist_structural_causal_model_spec(store,model);model=load_structural_causal_model_spec(FileSystemCAS(store.root),model_ref)
def job(method,state,slot):
    MethodRegistry.get_instance().register(method,override=True)
    ref=store.put_json(state.model_dump(mode='json'),PutOptions(kind='tests.cubic_method_source',media_type='application/json'),canon_spec=CanonSpec(forbid_floats=False))
    result=run_job(JobSpec(job_kind='method',method_fqn=method.signature.fqn,input_refs={slot:ref},method_params={'enable_dowhy_comparison':False} if method is GCMQuery else {},seed=31),cas_root=store.root,method_state=state)
    assert not result.issues and result.method_result_ref is not None
    return from_canonical_bytes(store.get_bytes(result.method_result_ref))
q=SCMQueryData(scm_spec=model,query=CausalQuery(query_type='interventional',treatment_variable='X',treatment_value=2.,outcome_variable='Y',n_samples=32))
r=CausalQueryResult.model_validate(job(GCMQuery,q,'scm_query_data')['causal_query_result'])
assert abs(r.result_mean-8.)<1e-10 and np.max(np.abs(np.asarray(r.result_distribution)-8.))<1e-10
factual={'X':1.,'Y':5.};t=TwinNetworkQueryData(scm_spec=model,factual_condition=factual,treatment_variable='X',factual_treatment_value=1.,counterfactual_treatment_value=2.,outcome_variable='Y',n_samples=32)
tr=TwinNetworkResult.model_validate(job(TwinNetworkQuery,t,'twin_network_query_data')['twin_network_result'])
assert abs(tr.po_factual_mean-5.)<1e-10 and abs(tr.po_counter_mean-8.25)<1e-10 and abs(tr.ite_mean-3.25)<1e-10
assert r.estimator_interval is None and tr.estimator_interval is None and not r.to_uncertainty_envelope().gate_eligible and not tr.to_uncertainty_envelope().gate_eligible
# Missing X is an actual unsupported nonlinear posterior case, not fabricated authority.
partial=TwinNetworkQuery.pure_step(t.model_copy(update={'factual_condition':{'Y':5.}}),{'__seed__':31})['twin_network_result']
assert partial.metadata['abduction_profile']!='linear_gaussian_posterior'
assert partial.metadata['abduction_gate_eligible'] is False and partial.metadata['abduction_limitation'] and not partial.to_uncertainty_envelope().gate_eligible
# Actual observed-data default remains its declared native linear fit route.
fitted=HybridSCMFit.pure_step(SCMFitData(data=rows,column_names=['X','Y'],graph=graph),{'fit_backend':'native_hybrid'})['scm_spec']
assert next(m for m in fitted.mechanisms if m.variable=='Y').family is MechanismFamily.LINEAR
print(json.dumps({'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'source_tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),'known_law':'f(x)=2+3x-.5x²+.25x³; f1=4.75,f2=8; factualY5 preserves U=.25; counter8.25, ITE3.25','fitted_parameters':params,'query_mean':r.result_mean,'twin':{'factual':tr.po_factual_mean,'counter':tr.po_counter_mean,'ite':tr.ite_mean},'partial_nonlinear_profile':partial.metadata,'partial_warnings':partial.abduction_warnings,'default_fit_family':'linear','estimator_interval':None,'manual_model_ref':model_ref.model_dump(mode='json'),'source_ref':source.model_dump(mode='json'),'scope':'Synthetic fitted payload compatibility and full-factual residual algebra only; no nonlinear posterior/default fitter/evaluation authority claim'},indent=2),flush=True)
