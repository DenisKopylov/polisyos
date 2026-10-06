from concurrent.futures import ThreadPoolExecutor
import hashlib, importlib.metadata, json, os, pathlib, platform, subprocess, sys, time

root=pathlib.Path('/workspace/e02-E-pr38-r2-receipts/independent-ddm-reviewer')
leaf=pathlib.Path('/workspace/e02-E-pcl-20261006')
cwd=leaf/'policy-engine'
python='/workspace/e02-E-continuation-20261006/policy-engine/.venv/bin/python'
paths=subprocess.check_output(['git','diff','--name-only','22998874b5f32434c462065baaca44a78e967f91','74b26eb067dea76d90b134641e66537759e4dc0f'],cwd=leaf,text=True).splitlines()
def identity():
    return {p:{'sha256':hashlib.sha256((leaf/p).read_bytes()).hexdigest(),'bytes':(leaf/p).stat().st_size,'git_target_sha256':hashlib.sha256(subprocess.check_output(['git','show','74b26eb067dea76d90b134641e66537759e4dc0f:'+p],cwd=leaf)).hexdigest()} for p in paths}
before=identity()
env=os.environ.copy(); env['PYTHONPATH']='src'; env['UV_NO_SYNC']='1'
versions={p:importlib.metadata.version(p) for p in ('numpy','scipy','pydantic','pytest','arch','statsmodels','jax','ruff')}
base={'cwd':str(cwd),'python':python,'python_version':sys.version,'platform':platform.platform(),'packages':versions,'env_overrides':{'PYTHONPATH':'src','UV_NO_SYNC':'1'},'source_sha':'74b26eb067dea76d90b134641e66537759e4dc0f','source_tree':'dfd78fc6417f8659c8a981a82712bb0e07fcc940','baseline_sha':'22998874b5f32434c462065baaca44a78e967f91','root_base_sha':'028829629a9c30454e44d25e7bea7be3ea05b561','head_before':subprocess.check_output(['git','rev-parse','HEAD','HEAD^{tree}'],cwd=leaf,text=True).splitlines(),'probe_sha256':hashlib.sha256((root/'pcl_probe.py').read_bytes()).hexdigest(),'footprint_before':before}
def run(mode):
    argv=[python,str(root/'pcl_probe.py'),mode]
    start=time.time()
    result=subprocess.run(argv,cwd=cwd,env=env,capture_output=True)
    path=root/(mode+'.attempt2.stdout')
    path.write_bytes(result.stdout+result.stderr)
    record=dict(mode=mode,argv=argv,cwd=str(cwd),started_epoch=start,wall_seconds=time.time()-start,exit_code=result.returncode,expected_exit=1 if mode=='remove_loader_recompute' else 0,stdout=str(path),stdout_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),stdout_bytes=path.stat().st_size)
    record['expected_outcome']=record['exit_code']==record['expected_exit']
    print(json.dumps(record),flush=True)
    return record
with ThreadPoolExecutor() as pool:
    records=list(pool.map(run,('native','native_noclient','old_base','remove_graph_store','remove_loader_recompute')))
base['commands']=records
base['footprint_after']=identity()
base['source_files_unchanged']=base['footprint_after']==before
base['actual_source_files_match_target']=all(before[p]['sha256']==before[p]['git_target_sha256'] for p in paths if '/src/' in p)
base['head_after']=subprocess.check_output(['git','rev-parse','HEAD','HEAD^{tree}'],cwd=leaf,text=True).splitlines()
base['all_expected_outcomes']=all(r['expected_outcome'] for r in records)
(root/'checks.json').write_text(json.dumps(base,indent=2,sort_keys=True)+'\n')
sys.exit(0 if base['all_expected_outcomes'] and base['source_files_unchanged'] and base['actual_source_files_match_target'] else 1)
