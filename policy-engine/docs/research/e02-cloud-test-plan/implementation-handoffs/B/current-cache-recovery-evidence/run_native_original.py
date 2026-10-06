"""Capture exact fresh-source native invocation without changing its source."""
import hashlib,json,os,pathlib,platform,resource,subprocess,sys,time
from datetime import datetime,timezone
root=pathlib.Path('/workspace/e02-B-current-execution-state')
label=sys.argv[1]
tests=sys.argv[2:]
out=root/'_build/current-execution-state'/label
out.mkdir(parents=True,exist_ok=True)
python='/workspace/polisyos/policy-engine/.venv/bin/python'
env=dict(os.environ)
env['PYTHONPATH']=str(root/'policy-engine/src')+':'+str(root/'policy-engine')
argv=[python,'-m','pytest','-q',*tests,'--junitxml='+str(out/'cohort.xml'),'--basetemp='+str(out/'tmp')]
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=root,text=True).strip()
paths=subprocess.check_output(['git','ls-tree','-r','--name-only',head],cwd=root,text=True).splitlines()
inputs=[p for p in paths if p.endswith('.py') and (p.startswith('policy-engine/src/') or p.endswith('conftest.py'))]
inputs+=['policy-engine/pyproject.toml','policy-engine/uv.lock','policy-engine/pytest.ini',*tests]
inputs=sorted(set(inputs))
closure=[{'path':p,'sha256':hashlib.sha256((root/p).read_bytes()).hexdigest(),'bytes':(root/p).stat().st_size} for p in inputs]
(out/'input-closure.json').write_text(json.dumps(closure,indent=2)+'\n')
origin_modules=["polisyos.scientist.orchestration.engine.async_executor","polisyos.scientist.orchestration.engine.executor","polisyos.scientist.orchestration.engine.idempotency","polisyos.scientist.orchestration.engine.checkpoint","polisyos.scientist.orchestration.engine.state_branching","polisyos.scientist.orchestration.engine.state_merge","polisyos.scientist.orchestration.engine.runner.serialization","polisyos.common.async_tools","polisyos.core.artifacts.store"]
probe_code="import importlib,importlib.metadata,json,sys; mods="+repr(origin_modules)+"; print(json.dumps({'python':sys.version,'origins':{n:importlib.import_module(n).__file__ for n in mods},'distributions':sorted((d.metadata['Name'],d.version) for d in importlib.metadata.distributions())}))"
probe=subprocess.run([python,"-c",probe_code],cwd=root,env=env,capture_output=True,text=True,check=True)
probe_data=json.loads(probe.stdout)
(out/'environment.json').write_text(json.dumps(probe_data,indent=2)+'\n')
assert all(str(root/'policy-engine/src') in v for v in probe_data['origins'].values()),probe_data['origins']
driver_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
start=datetime.now(timezone.utc).isoformat()
t=time.perf_counter()
with (out/'native.txt').open('w') as log:
 r=subprocess.run(argv,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
wall=time.perf_counter()-t
after=[{'path':p,'sha256':hashlib.sha256((root/p).read_bytes()).hexdigest(),'bytes':(root/p).stat().st_size} for p in inputs]
receipt={'source_sha':head,'source_tree':tree,'source_binding':'tracked HEAD plus exact input-closure bytes; draft status is recorded separately','driver_sha256':driver_sha256,'command':argv,'cwd':str(root),'environment':{'python':python,'PYTHONPATH':env['PYTHONPATH'],'platform':platform.platform(),'details':str(out/'environment.json'),'python_version':probe_data['python']},'input_closure':{'path':str(out/'input-closure.json'),'sha256':hashlib.sha256((out/'input-closure.json').read_bytes()).hexdigest(),'paths':len(closure),'fixture_inputs':'Exact test code, isolated basetemp/cas/run paths, no production data'},'start_utc':start,'end_utc':datetime.now(timezone.utc).isoformat(),'wall_s':wall,'max_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'exit':r.returncode,'source_unchanged':head==subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip() and closure==after,'outputs':[]}
for p in sorted(out.iterdir()):
 if p.is_file(): receipt['outputs'].append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
(out/'wrapper.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
sys.exit(r.returncode)
