import concurrent.futures,hashlib,json,os,subprocess,time
from pathlib import Path
root=Path('/dev/shm/e02-orch03-20261008/c08')
scratch=Path('/dev/shm/e02-orch03-20261008/c08-scratch')
python='/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'
source='2dd8339c210caf973586f7ddec69b6b0a48f1df7'
module=Path('policy-engine/src/polisyos/foundry/methods/catalog/causal/_partial_graph_queries.py')
tests='policy-engine/tests/unit/foundry/methods/catalog/causal/'
cases={
'full-family-removed':('return extensions, 2 ** len(unresolved)','return extensions[1:], 2 ** len(unresolved)',[tests+'test_partial_graph_queries.py::test_two_agreeing_chain_samples_do_not_hide_third_completion',tests+'test_partial_graph_query_consumer.py::test_actual_engine_audit_preserves_partial_query_in_fresh_cas_and_child']),
'profile-contradiction-removed':('if "mgraph" in graph.metadata:','if False and "mgraph" in graph.metadata:',[tests+'test_partial_graph_queries.py::test_unsupported_family_is_typed_limited_without_fake_coverage[graph3]']),
}
def run(item):
 name,(old,new,selectors)=item;export=scratch/name;export.mkdir(exist_ok=True)
 archive=subprocess.Popen(['git','archive',source,'policy-engine/src','policy-engine/tests','policy-engine/pyproject.toml','policy-engine/architecture'],cwd=root,stdout=subprocess.PIPE)
 extracted=subprocess.run(['tar','-x','-C',str(export)],stdin=archive.stdout,capture_output=True,text=True);archive.stdout.close();assert archive.wait()==0 and extracted.returncode==0,extracted.stderr
 original=(export/module).read_text();assert original.count(old)==1
 mutated=original.replace(old,new);(export/module).write_text(mutated)
 assert '_PROFILE =' in mutated and 'exhaustive_for_declared_profile' in mutated and 'authority_eligible' in mutated
 env=os.environ.copy();env['PYTHONPATH']=str(export/'policy-engine/src');env['TMPDIR']=str(scratch)
 guard=['-c',"import json,pathlib,sys;from polisyos.foundry.methods.catalog.causal import _partial_graph_queries as m;p=pathlib.Path(m.__file__).resolve();assert str(p).startswith(sys.argv[1]);print(json.dumps({'module':str(p),'profile':m._PROFILE}))",str(export)]
 g=subprocess.run([python,*guard],cwd=export,env=env,capture_output=True,text=True)
 assert g.returncode==0,g.stderr
 (scratch/f'{name}.source-guard.json').write_text(g.stdout)
 command=[python,'-m','pytest','-o','addopts=','--import-mode=importlib','--basetemp',str(scratch/f'{name}-pytest-temp'),'--junitxml',str(scratch/f'{name}.xml'),'-v',*selectors]
 started=time.time()
 with (scratch/f'{name}.stdout').open('wb') as out,(scratch/f'{name}.stderr').open('wb') as err:
  p=subprocess.run([python,str(scratch/'time_child.py'),str(scratch/f'{name}.time'),*command],cwd=export,env=env,stdout=out,stderr=err)
 record={'name':name,'source':source,'export':str(export),'command':command,'cwd':str(export),'pythonpath':env['PYTHONPATH'],'removed_runtime_property':old,'replacement':new,'retained_markers':['_PROFILE','exhaustive_for_declared_profile','orientation_assignments_checked','authority_eligible'],'original_sha256':hashlib.sha256(original.encode()).hexdigest(),'mutated_sha256':hashlib.sha256(mutated.encode()).hexdigest(),'returncode':p.returncode,'expected':'FAIL at behavioral assertions, never collection/setup error','wall_s':time.time()-started,'stdout':f'{name}.stdout','stderr':f'{name}.stderr','junit':f'{name}.xml','source_guard':f'{name}.source-guard.json'}
 (scratch/f'{name}.record.json').write_text(json.dumps(record,indent=2)+'\n')
 print(json.dumps(record),flush=True)
 return record
with concurrent.futures.ThreadPoolExecutor() as pool: records=list(pool.map(run,cases.items()))
(scratch/'removal-controls.json').write_text(json.dumps(records,indent=2)+'\n')
