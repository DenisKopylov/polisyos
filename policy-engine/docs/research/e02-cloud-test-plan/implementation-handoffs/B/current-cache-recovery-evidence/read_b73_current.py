"""Read actual current frozen-wave CAS outputs; no fixture or source mutation."""
import hashlib
import importlib.util
import json
import pathlib
import sys

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.scientist.orchestration.engine.checkpoint import (
    load_checkpoint,
    load_checkpoint_history,
    materialize_checkpoint_state,
)
from polisyos.scientist.orchestration.engine.executor import _merge_cached_outcome_state
from polisyos.scientist.orchestration.engine.idempotency import NodeCacheEntry, NodeResultCache, compute_idempotency_key
from polisyos.scientist.orchestration.engine.state import ExperimentState

root=pathlib.Path('/workspace/e02-B-current-execution-state')
test=root/'policy-engine/tests/integration/scientist/test_checkpoint_resume.py'
spec=importlib.util.spec_from_file_location('b73_current_source_input',test)
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
out=[]
inputs=[
 ('publication_before_head',root/'_build/current-execution-state/frozen-cache-consumers/tmp/test_seeded_checkpoint_publica0/after_artifact_before_head','R_b73_seeded_publication_cut_after_artifact_before_head'),
 ('fail_fast',root/'_build/current-execution-state/frozen-cache-consumers/tmp/test_parallel_resume_fail_fast0/fail_fast','R_b73_failure_policy_fail_fast'),
]
for label,cas_root,run_id in inputs:
 store=FileSystemCAS(cas_root);run_dir=cas_root/'runs'/run_id
 history=load_checkpoint_history(run_dir)
 checkpoints=[]
 for h in history.entries:
  c=load_checkpoint(store,h.checkpoint_ref)
  checkpoints.append({'ref':h.checkpoint_ref.model_dump(mode='json'),'verified':store.verify(h.checkpoint_ref).ok,'metadata':c.metadata.model_dump(mode='json'),'params':materialize_checkpoint_state(store,h.checkpoint_ref)['params']})
 trace=run_dir/'trace.jsonl';records=[json.loads(line) for line in trace.read_text().splitlines()]
 registry=m._seeded_parallel_registry();workflow=m._seeded_parallel_workflow()
 invocations={str(i.node_id):i for i in workflow.nodes if i.alias in ['left','right']}
 cache=NodeResultCache(store,run_id)
 observed=[];resume_ordinal=0
 for event_index,event in enumerate(records):
  if event['event']=='CHECKPOINT_RESUMED':resume_ordinal+=1
  if event['event']!='NODE_CACHE_STORE':continue
  for raw in event.get('refs',{}).get('outputs',[]):
   ref=ArtifactRef.model_validate(raw)
   if ref.kind!='scientist.node_cache_entry':continue
   data=store.get_bytes(ref);entry=NodeCacheEntry.model_validate(from_canonical_bytes(data))
   inv=invocations.get(entry.node_id)
   if inv is None:continue
   node=registry.get(inv.node_id)
   initial=ExperimentState(run_id=run_id,params={'seed':29,'step1':1})
   key=compute_idempotency_key(node.spec,initial,inv.params)
   assert key==entry.idempotency_key
   cache.load_entry(ref);outcome=cache.get(key);assert outcome is not None
   current=ExperimentState(run_id=run_id,params={'seed':29,'step1':1,'unrelated':'current'})
   applied=_merge_cached_outcome_state(alias=inv.alias,node=node,base_state=current,outcome=outcome)
   assert applied.params=={'seed':29,'step1':1,'unrelated':'current',inv.alias:1 if inv.alias=='left' else 2}
   observed.append({'publication_resume_ordinal':resume_ordinal,'trace_event_index':event_index,'alias':inv.alias,'ref':ref.model_dump(mode='json'),'verified':store.verify(ref).ok,'blob_sha256':hashlib.sha256(data).hexdigest(),'payload':entry.model_dump(mode='json'),'manifest':store.get_manifest(ref).model_dump(mode='json'),'native_apply_params':applied.params})
 out.append({'label':label,'cas_root':str(cas_root),'run_id':run_id,'history':checkpoints,'trace_sha256':hashlib.sha256(trace.read_bytes()).hexdigest(),'trace_publication_readback':observed,'trace_hits':[e for e in records if e['event']=='NODE_CACHE_HIT']})
print(json.dumps({'source_sha':'79b2a7095b15f159d0ca168e8c15a8f94727b685','test_sha256':hashlib.sha256(test.read_bytes()).hexdigest(),'observed_cases':out,'not_observed':'after_head_before_history and continue loop iterations were not reached after original assertions failed'},indent=2))
