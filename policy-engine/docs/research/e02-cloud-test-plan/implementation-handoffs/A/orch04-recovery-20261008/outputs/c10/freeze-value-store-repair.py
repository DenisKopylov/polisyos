import hashlib,json,subprocess
from pathlib import Path
root=Path('/workspace/ORCH04-C10');e=Path('/workspace/ORCH04-evidence/c10')
def git(*a):return subprocess.check_output(['git',*a],cwd=root,text=True).strip()
def raw(ref,path):return subprocess.check_output(['git','show',ref+':'+path],cwd=root)
p=e/'source-input-manifest.json';(e/'source-input-manifest-cfe46cfa.json').write_bytes(p.read_bytes());m=json.loads(p.read_text());prior=m['source_commit'];head=git('rev-parse','HEAD');tree=git('rev-parse','HEAD^{tree}');parents=git('show','-s','--format=%P','HEAD').split()
for row in m['files']:
 b=raw(head,row['path']);row.update({'postimage_git_blob':git('rev-parse',head+':'+row['path']),'postimage_sha256':hashlib.sha256(b).hexdigest()})
m.update({'source_commit':head,'source_tree':tree,'source_parents':parents,'status_at_freeze':git('status','--porcelain')});r=m['test_companion_repair'];r['checked_source_at_test_only_repair']=prior;r['production_and_frontend_blobs_exact_unchanged_relative_to_03a_at_cfe']=r.pop('production_and_frontend_blobs_exact_unchanged')
path='policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py';delta=git('diff','--name-only',prior,head).splitlines();assert delta==[path]
m['value_consumer_store_binding_repair']={'preimage_source':prior,'preimage_tree':'3313e6e84959cd7d43ad18aa083baf26563a0c86','postimage_source':head,'postimage_tree':tree,'delta_paths':delta,'preimage_blob':git('rev-parse',prior+':'+path),'postimage_blob':git('rev-parse',head+':'+path),'mechanism':'recursive protected leaf FoundryValuePort now receives canonical self._artifact_store derived from PromotionRuntime.store, matching existing N6/store and sibling default/reentry value consumers','existing_protocol':'FoundryValuePort artifact_store:ArtifactStore|None; simulation_evaluation_input_ref uses passedstore for actual persisted N5 provenance','strict_test':'actual_n5_input_ref retains runtime.store identity assertion','prior_native_deciding':'cfe affectedwholeepoch37=34PASS3FAIL (strictCASidentity plus2sharedguard/Core diagnostics), retained raw; finalaffectedrun pending','review':'independent reviewer diagnosed realowned route wiring omission; immutable delta review pending','frontends_allother_paths_exact_unchanged':True}
for row in m['files']:
 if row['path']!=path:assert raw(head,row['path'])==raw(prior,row['path'])
p.write_text(json.dumps(m,indent=2)+'\n');(e/'leaf-receipt-draft/source-manifest.json').write_bytes(p.read_bytes())
cp=e/'companion-requirements.json';d=json.loads(cp.read_text());d.update({'source_commit':head,'source_tree':tree});cp.write_text(json.dumps(d,indent=2)+'\n');(e/'leaf-receipt-draft/companion-requirements.json').write_bytes(cp.read_bytes())
lp=e/'leaf-receipt-draft/lease-packet.json';l=json.loads(lp.read_text());l['actual_pair'].update({'source_head':head,'source_tree':tree,'status_at_freeze':git('status','--porcelain')});l['source_paths']=m['files'];l['admission']['new_source_lineage']+=' ->'+head+' existing typed value consumer store wiring';lp.write_text(json.dumps(l,indent=2)+'\n')
print(json.dumps({'head':head,'tree':tree,'parents':parents,'delta':delta,'status':git('status','--porcelain')}))
