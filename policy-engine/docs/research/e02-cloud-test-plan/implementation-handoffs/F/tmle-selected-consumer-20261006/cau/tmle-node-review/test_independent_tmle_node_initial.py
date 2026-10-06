"""Observe genuine selected jobs and distinguish input/report projection attacks."""
import copy
import importlib.util
import json
import os
import pathlib

import numpy as np
import pytest

from polisyos.core.canon import from_canonical_bytes
from polisyos.foundry.methods.catalog.causal import tmle_core as core
from polisyos.foundry.methods.catalog.causal.treatment_effects import TMLEEstimator
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as node

ROOT=pathlib.Path(os.environ['E02_TMLE_SOURCE_ROOT'])
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,ROOT/path)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
FIXTURES=load('_actual_node_fixtures','tests/unit/scientist/nodes/conftest.py')
for name in ('cas_store','registry_bundle_ref','execution_context','minimal_state'):
 globals()[name]=getattr(FIXTURES,name)
OWNER=load('_frozen_selected_tmle_owner','tests/unit/scientist/nodes/builtins/simulate/test_tmle_selected_consumer.py')

def spec(params):
 return JobSpec(job_kind='method',method_fqn=TMLEEstimator.signature.fqn,method_params=params,seed=18)

def test_real_selected_job_observes_complete_source_and_json_abi(execution_context,minimal_state,monkeypatch):
 data,params,state,source=OWNER._fixture(execution_context,minimal_state)
 basis=np.column_stack((data.covariates,data.confounders))
 calls=[];fit=core._fit_crossfit_fold
 def observe(**kw):
  np.testing.assert_array_equal(kw['X'],basis)
  calls.append((kw['rep_seed'],kw['fold_id'],kw['test_idx'].copy()))
  return fit(**kw)
 monkeypatch.setattr(core,'_SHARED_NUISANCE_CACHE',{})
 monkeypatch.setattr(core,'_SHARED_NUISANCE_CACHE_ORDER',[])
 monkeypatch.setattr(core,'_fit_crossfit_fold',observe)
 loaded=node._load_observational_data(execution_context,state,TMLEEstimator.signature.fqn)
 result=node._run_primary_causal_job(ctx=execution_context,state=state,spec=spec(params),observational_data=loaded)
 assert not result.issues and len(calls)==6
 for seed in (18,1015):
  assert sorted(i for s,_,indices in calls if s==seed for i in indices)==list(range(400))
 assert str(source.artifact_id) in {str(r.artifact_id) for r in execution_context.store.get_manifest(result.method_result_ref).inputs}
 saved=from_canonical_bytes(execution_context.store.get_bytes(result.method_result_ref))
 report=CausalEffectReport.model_validate(result.final_state['report'])
 assert saved['report']['method_params']['propensity_backend_candidates']==[]
 assert report.method_params['propensity_backend_candidates']==()
 assert report.point_estimate==saved['result']['ate']
 # A deliberate JSON-normalized peer differs in Python nestedAny tuple/list,
 # while representing the identical persisted report contract.
 peer=copy.deepcopy(result.final_state)
 peer['report']=CausalEffectReport.model_validate(json.loads(report.model_dump_json()))
 assert peer['report'].method_params['propensity_backend_candidates']==[]
 assert peer['report'].model_dump(mode='json')==report.model_dump(mode='json')
 node._reconcile_selected_causal_output(ctx=execution_context,result=result.model_copy(update={'final_state':peer}))
 node._verify_selected_tmle_projection(peer,observational_data=loaded,params=params)
 assert not report.to_uncertainty_envelope().gate_eligible and report.identified_estimand is None
 print(json.dumps({'actual_native_folds':len(calls),'full_adjustment_shape':list(basis.shape),'source_lineage':str(source.artifact_id),'tuple_list_equivalent':True,'point':report.point_estimate,'gate_eligible':False}))

@pytest.mark.parametrize('field',['covariates','confounders','outcome','treatment','sample_ids'])
def test_all_actual_source_fields_rejected_before_genuine_job(execution_context,minimal_state,monkeypatch,field):
 data,params,state,_=OWNER._fixture(execution_context,minimal_state)
 array=np.asarray(getattr(data,field)).copy()
 if field in ('outcome','treatment'):array[0]=1-array[0]
 elif field=='sample_ids':array=array[::-1].copy()
 else:array[0,0]+=0.5
 offered=data.model_copy(update={field:array})
 calls=[];run=node.run_job
 def observe(*args,**kwargs):
  calls.append(True);return run(*args,**kwargs)
 monkeypatch.setattr(node,'run_job',observe)
 with pytest.raises(ValueError,match='materialization/source mismatch'):
  node._run_primary_causal_job(ctx=execution_context,state=state,spec=spec(params),observational_data=offered)
 assert calls==[]

@pytest.mark.parametrize('field',['ate','standard_error'])
def test_genuine_job_raw_numeric_peer_change_rejected(execution_context,minimal_state,monkeypatch,field):
 data,params,state,_=OWNER._fixture(execution_context,minimal_state)
 calls=[];run=node.run_job
 def observed_real_job(*args,**kwargs):
  result=run(*args,**kwargs)
  assert not result.issues and result.method_result_ref is not None
  peer=copy.deepcopy(result.final_state)
  peer['result'][field]+=0.25
  # The original persisted result/report/envelope remain untouched in CAS.
  calls.append(result.method_result_ref.model_dump(mode='json'))
  return result.model_copy(update={'final_state':peer})
 monkeypatch.setattr(node,'run_job',observed_real_job)
 with pytest.raises(ValueError,match='numerical report projection mismatch'):
  node._run_primary_causal_job(ctx=execution_context,state=state,spec=spec(params),observational_data=data)
 assert len(calls)==1
