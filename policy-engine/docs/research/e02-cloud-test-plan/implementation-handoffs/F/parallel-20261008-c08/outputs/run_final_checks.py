import concurrent.futures, hashlib, json, os, platform, subprocess, sys, time
from pathlib import Path
root=Path('/dev/shm/e02-orch03-20261008/c08')
scratch=Path('/dev/shm/e02-orch03-20261008/c08-scratch')
python='/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'
newfiles=['policy-engine/src/polisyos/foundry/methods/catalog/causal/_partial_graph_queries.py','policy-engine/tests/unit/foundry/methods/catalog/causal/test_partial_graph_queries.py','policy-engine/tests/unit/foundry/methods/catalog/causal/test_partial_graph_query_consumer.py']
commands={
'final-pytest':[python,'-m','pytest','-o','addopts=','--import-mode=importlib','--basetemp',str(scratch/'pytest-temp'),'--junitxml',str(scratch/'final-pytest.xml'),'-v',*newfiles[1:]],
'final-ruff':[python,'-m','ruff','check',*newfiles,'policy-engine/src/polisyos/foundry/methods/catalog/causal/causal_engine/identification.py'],
'final-format':[python,'-m','ruff','format','--check',*newfiles],
'production-invocation':[python,'-m','polisyos.runtime.quality.production_invocation','--base','f00dd7661a8d3329fb1fa1b049decb0d1d2f277b','--receipt',str(scratch/'production-invocation.json')],
}
current=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
assert current=='2dd8339c210caf973586f7ddec69b6b0a48f1df7',current
env=os.environ.copy();env['PYTHONPATH']=str(root/'policy-engine/src')+':'+str(root/'policy-engine/tools');env['TMPDIR']=str(scratch)
def run(item):
 name,args=item;started=time.time();cwd=root/'policy-engine' if name=='production-invocation' else root
 with (scratch/f'{name}.stdout').open('wb') as out,(scratch/f'{name}.stderr').open('wb') as err:
  completed=subprocess.run([python,str(scratch/'time_child.py'),str(scratch/f'{name}.time'),*args],cwd=cwd,env=env,stdout=out,stderr=err)
 row={'name':name,'command':args,'cwd':str(cwd),'returncode':completed.returncode,'wall_s':time.time()-started,'stdout':f'{name}.stdout','stderr':f'{name}.stderr','time':f'{name}.time'}
 (scratch/f'{name}.record.json').write_text(json.dumps(row,indent=2)+'\n')
 print(json.dumps(row),flush=True)
 return row
with concurrent.futures.ThreadPoolExecutor() as pool: rows=list(pool.map(run,commands.items()))
identity={'source':current,'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=root,text=True).strip(),'interpreter':subprocess.check_output([python,'-VV'],text=True).strip(),'executable':python,'platform':platform.platform(),'pythonpath':env['PYTHONPATH'],'commands':rows,'cloud_compute_quota':None}
(scratch/'final-checks.json').write_text(json.dumps(identity,indent=2)+'\n')
