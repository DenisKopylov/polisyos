"""Reviewer-owned analytical words and selected CAS view controls."""
import hashlib, importlib.util
from pathlib import Path
import jax
import numpy as np
import pytest
from polisyos.core.artifacts.manifest import ArtifactRef,InputRef
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.contracts.foundry import ExecPlan,ProgramGraph
from polisyos.foundry.compile.randomization import TreasuryPlan
from polisyos.foundry.execute._internal.graph import _treasury_node_key
p=Path('/workspace/e02-F-fry-20261006/policy-engine/tests/unit/foundry/compile/test_treasury_execution.py')
spec=importlib.util.spec_from_file_location('fry_author_fixture',p); fixture=importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)

@pytest.mark.parametrize('seed',[0,17,2147483655])
@pytest.mark.parametrize('root',[0,17,2147483655])
@pytest.mark.parametrize('node',['node:a','other','unicode_б'])
def test_all64bit_word_order_against_independent_hash_and_adverse_controls(seed,root,node):
 labels=['stream:default','node:'+node]
 salts=[int.from_bytes(hashlib.sha256((f'{root}:' if root else '').encode()+label.encode()).digest()[:8],'big') for label in labels]
 treasury=TreasuryPlan(root_seed=root,node_salts={node:salts[1]},stream_salts={'default':salts[0]})
 key=jax.random.PRNGKey(seed)
 expected=key
 for salt in salts:
  lo=int.from_bytes(salt.to_bytes(8,'big')[4:],'big'); hi=int.from_bytes(salt.to_bytes(8,'big')[:4],'big')
  expected=jax.random.fold_in(jax.random.fold_in(expected,np.uint32(lo)),np.uint32(hi))
 actual=_treasury_node_key(key,treasury,node)
 np.testing.assert_array_equal(jax.random.key_data(actual),jax.random.key_data(expected))
 for words in ([x for s in salts for x in (s>>32,s&0xffffffff)],[x for s in reversed(salts) for x in (s&0xffffffff,s>>32)],[s&0xffffffff for s in salts]):
  adverse=key
  for word in words: adverse=jax.random.fold_in(adverse,np.uint32(word))
  assert not np.array_equal(jax.random.key_data(adverse),jax.random.key_data(expected))

@pytest.mark.parametrize('kind',['duplicate_exec_program','missing_lowered','duplicate_lowered','wrong_lowered','requested_program_profile','selected_treasury_profile'])
def test_selected_manifest_admission_refuses_actual_lineage_escape(tmp_path,monkeypatch,kind):
 store,report,content=fixture._compile(tmp_path/'cas')
 plan=fixture._load(store,report.exec_plan_ref,ExecPlan); graph=fixture._load(store,report.program_graph_ref,ProgramGraph)
 expected=fixture._execute(store,report,content)
 em=store.get_manifest(report.exec_plan_ref)
 if kind=='duplicate_exec_program':
  inputs=list(em.inputs)+[x for x in em.inputs if x.role=='program_graph']; report=fixture._replace_plan(store,report,inputs=inputs)
  reason='treasury_requires_one_program_graph_input'
 elif kind=='selected_treasury_profile':
  treasury=fixture._load(store,report.treasury_plan_ref,TreasuryPlan); tm=store.get_manifest(report.treasury_plan_ref)
  bad=store.put_json(treasury,PutOptions(kind=tm.kind,media_type=tm.media_type,schema=tm.artifact_schema,inputs=[InputRef(artifact_id=report.exec_plan_ref.artifact_id,role='program_graph')]))
  assert bad.artifact_id==report.treasury_plan_ref.artifact_id
  assert bad.manifest_profile_sha256!=report.treasury_plan_ref.manifest_profile_sha256
  # Same bytes and untouched good selected view do not admit the bad view.
  np.testing.assert_array_equal(fixture._execute(store,report,content),expected)
  inputs=[InputRef(artifact_id=bad.artifact_id,role='treasury_plan',manifest_profile_sha256=bad.manifest_profile_sha256) if x.role=='treasury_plan' else x for x in em.inputs]
  report=fixture._replace_plan(store,report,inputs=inputs); reason='treasury_source_program_mismatch'
 else:
  gm=store.get_manifest(report.program_graph_ref); inputs=list(gm.inputs)
  if kind=='missing_lowered': inputs=[x for x in inputs if x.role!='lowered_ir']; reason='treasury_requires_one_lowered_ir_input'
  elif kind=='duplicate_lowered': inputs += [x for x in inputs if x.role=='lowered_ir']; reason='treasury_requires_one_lowered_ir_input'
  elif kind=='wrong_lowered': inputs=[x.model_copy(update={'artifact_id':report.treasury_plan_ref.artifact_id}) if x.role=='lowered_ir' else x for x in inputs]; reason='treasury_lowered_ir_input_mismatch'
  else: inputs += [InputRef(artifact_id=report.treasury_plan_ref.artifact_id,role='review_metadata')]; reason='treasury_program_profile_mismatch'
  selected=store.put_json(graph,PutOptions(kind=gm.kind,media_type=gm.media_type,schema=gm.artifact_schema,inputs=inputs))
  assert selected.artifact_id==report.program_graph_ref.artifact_id
  assert selected.manifest_profile_sha256!=report.program_graph_ref.manifest_profile_sha256
  if kind=='requested_program_profile':
   report=report.model_copy(update={'program_graph_ref':selected})
  else:
   edge=InputRef(artifact_id=selected.artifact_id,role='program_graph',manifest_profile_sha256=selected.manifest_profile_sha256)
   old=store.get_manifest(report.treasury_plan_ref); treasury=fixture._load(store,report.treasury_plan_ref,TreasuryPlan)
   treasury_ref=store.put_json(treasury,PutOptions(kind=old.kind,media_type=old.media_type,schema=old.artifact_schema,inputs=[edge]))
   inputs=[edge if x.role=='program_graph' else InputRef(artifact_id=treasury_ref.artifact_id,role='treasury_plan',manifest_profile_sha256=treasury_ref.manifest_profile_sha256) if x.role=='treasury_plan' else x for x in em.inputs]
   report=fixture._replace_plan(store,report.model_copy(update={'program_graph_ref':selected}),inputs=inputs)
 def forbidden(*args,**kwargs): pytest.fail('unadmitted lineage reached actual native kernel')
 monkeypatch.setattr(fixture.AdaptiveAgentMechanism,'emit_patches',forbidden)
 with pytest.raises(ValueError,match=reason): fixture._execute(store,report,content)
