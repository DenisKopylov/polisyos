"""Conservative source qualification of immutable969 outputs after fiscal-only delta."""
from pathlib import Path
import ast,gzip,hashlib,json,subprocess,sys
ROOT=Path('/dev/shm/e02-D-oct07-continuation');OLD='96905636726483fdea3a98d9313871d825b54a9e';NEW=sys.argv[1];OUT=Path(sys.argv[2]);OUT.mkdir(exist_ok=True)
EVIDENCE=Path('/dev/shm/e02-D-oct07-service-start/final-native-969');OBJECTIVE='policy-engine/src/polisyos/scientist/methods/search/objective.py'
def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args],text=True).strip()
def sha(data):return hashlib.sha256(data).hexdigest()
def blob(ref,path):return subprocess.check_output(['git','-C',str(ROOT),'show',ref+':'+path])
def body(source):
 result={}
 for n in ast.parse(source).body:
  label=getattr(n,'name',None) or ast.dump(n,include_attributes=False)
  result[label]=sha(ast.dump(n,include_attributes=False).encode())
 return result
assert git('rev-parse','HEAD')==NEW and not git('status','--porcelain=v1','-uno')
assert all(line.startswith('?? policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/') for line in git('status','--porcelain=v1').splitlines()), 'Only pre-existing untracked handoff outputs may be outside tracked deciding inputs'
old,new=blob(OLD,OBJECTIVE),blob(NEW,OBJECTIVE);old_body,new_body=body(old),body(new)
common_changes=[name for name in sorted(set(old_body)&set(new_body)) if old_body[name]!=new_body[name]]
assert common_changes==['_read_metric_aliases'],common_changes
removed=set(old_body)-set(new_body);added=set(new_body)-set(old_body)
assert not removed and len(added)==1 and all('decimal' in name for name in added),(removed,added)
production_delta=[p for p in git('diff','--name-only',OLD,NEW,'--','policy-engine/src').splitlines() if p]
assert production_delta==[OBJECTIVE],production_delta
old_inputs=json.loads(gzip.decompress((EVIDENCE/'frozen-inputs.json.gz').read_bytes()))
def binding(path):
 before,after=blob(OLD,path),blob(NEW,path)
 assert before==after,path
 assert old_inputs[path]['sha256']==sha(before),path
 return {'path':path,'old_git_blob':git('rev-parse',OLD+':'+path),'new_git_blob':git('rev-parse',NEW+':'+path),'sha256':sha(after),'unchanged':True}
paths=['policy-engine/src/polisyos/scientist/methods/search/service.py','policy-engine/src/polisyos/scientist/methods/search/controller.py','policy-engine/src/polisyos/scientist/methods/search/run_state.py','policy-engine/src/polisyos/scientist/methods/search/stopping.py','policy-engine/src/polisyos/scientist/methods/search/frontier.py','policy-engine/src/polisyos/scientist/methods/autotune/runtime.py','policy-engine/src/polisyos/scientist/methods/autotune/registry.py','policy-engine/src/polisyos/scientist/methods/autotune/dedup.py','policy-engine/src/polisyos/common/serialization.py']
cohorts=[]
for name in ['dedup','service','champion','paid-original','native-doe','contracts']:
 receipt=EVIDENCE/(name+'.receipt.json');raw=receipt.read_bytes();r=json.loads(raw)
 assert r['source_sha']==OLD and r['source_sha_after']==OLD and r['same_inputs'] and not r['changed_inputs']
 tests=[argument for argument in r['argv'] if argument.startswith('tests/')]
 for test in tests:
  path='policy-engine/'+test.split('::')[0]
  if path not in paths:paths.append(path)
 outputs={}
 for suffix in ['stdout.txt','stderr.txt','junit.xml']:
  q=EVIDENCE/(name+'.'+suffix);assert sha(q.read_bytes())==r['outputs'][suffix]['sha256']
  outputs[suffix]={'path':str(q),'bytes':q.stat().st_size,'sha256':sha(q.read_bytes())}
 cases=r['cases'];affected=[c for c in cases if name=='service' and any(module in c['classname'] for module in ['test_service_batch_control_reasons','test_service_control_cleanup_independent','test_service_ask_publication_review'])]
 cohorts.append({'cohort':name,'immutable_test_source':OLD,'check_results_remain_at':OLD,'old_receipt':{'path':str(receipt),'sha256':sha(raw)},'old_case_phases':r['case_phases'],'old_outputs':outputs,'carried_cases':[c for c in cases if c not in affected],'needs_actual_replay_cases':affected,'qualification':'old output retained and producer/property branch qualified; this record is NOT a new execution or new PASS on the successor source'})
assert sum(len(c['needs_actual_replay_cases']) for c in cohorts)==18
rationale={
 'dedup':'Actual40 native factory/CAS/profile controls use _AutotuneObjective._extract_value (common finite_real_scalar), plus8 dedup-only helper controls. Native replay v2 returns before objective_build; source/helper/configuration and full test blobs unchanged.',
 'service':'18 builtin BudgetDeficit extraction and module-digest replay controls require current execution. Remaining23 are factory _AutotuneObjective2, custom _Cost native lifecycle8, topology/execution-plan13; their actual branches and full test/runtime source bytes are unchanged.',
 'champion':'Direct qualified registry primitive/snapshot cases and actual Runner promotion consumer use unchanged registry/common basis and native _AutotuneObjective; no fiscal alias extractor path.',
 'paid-original':'Actual SearchController integration uses GDPGrowthObjective, whose complete AST/globals/Base/Composite AST is unchanged and does not call _read_metric_aliases; direct controller, no builtin-objective replay profile.',
 'native-doe':'Actual SearchLoopRunner typed mutation/qualified SALib artifact factory uses unchanged _AutotuneObjective and native replay v2; no sampler/scientific law inferred and old13 PASS remains exact969.',
 'contracts':'Actual Legacy adapter/controller uses custom _Objective with unchanged CompositeObjective; custom replay profile is unavailable by existing contract, not builtin objective_build.'}
for c in cohorts:c['basis']=rationale[c['cohort']]
result={'old_source':{'sha':OLD,'tree':git('rev-parse',OLD+'^{tree}')},'successor_source':{'sha':NEW,'tree':git('rev-parse',NEW+'^{tree}')},'actual_production_delta':production_delta,'objective':{'old_sha256':sha(old),'new_sha256':sha(new),'common_changed_top_level_ast':common_changes,'added_top_level_ast':sorted(added),'removed_top_level_ast':sorted(removed),'unchanged_symbol_ast_sha256':{name:old_body[name] for name in sorted(set(old_body)&set(new_body)) if old_body[name]==new_body[name]},'semantic_dependency':'BudgetDeficitObjective alone calls _read_metric_aliases; all other objective classes/methods/constants retain exact AST and imports are additive standard library names with no existing binding collision.'},'unchanged_bindings':[binding(p) for p in paths],'cohorts':cohorts,'mypy':{'exact_prior_test_source':OLD,'successor_runtime_source_blob_unchanged':True,'successor_objective_public_annotations_unchanged':True,'result':'prior strict runtime mypy0 retained at969; no successor typecheck execution asserted','prior_manifest':str(Path('/dev/shm/e02-D-runner-mypy-after-969-dy94hlnx/command.json'))},'limitations':['This qualified transfer applies only to the exact fiscal-only source diff and listed unchanged runtime/test blobs.','No whole41 successor replay or whole-D PASS is claimed.','No original scientific/unit law, production caller appointment, migration authority or G integration acceptance follows from this source qualification.','Actual18 current execution is a separate deciding receipt and required before completing this delta.']}
p=OUT/'969-fiscal-only-source-qualified-carry.json';p.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes()),'replay_cases':sum(len(c['needs_actual_replay_cases']) for c in cohorts),'unchanged_bindings':len(paths)},indent=2))
