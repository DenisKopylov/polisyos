import concurrent.futures,datetime,hashlib,json,os,pathlib,subprocess,time
root=pathlib.Path('/workspace/e02-F-graph-20261006');product=root/'policy-engine'
out=pathlib.Path('/workspace/e02-F-20261006-receipts/graph/scm-frozen');out.mkdir(exist_ok=True)
source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
assert source=='d88fcd5ec298d0884b809c6a786731eb70d0d27e'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)
app='/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'
worker=str(product/'workers/dowhy-014/.venv/bin/python')
pytest=[app,'-m','pytest','-o','addopts=','-q']
base='198076863e143dea9f89f02734b13d50dae3eed5'
jobs=[
 ('semantics',pytest+['tests/unit/foundry/methods/catalog/causal/test_scm_result_semantics.py'],product,{'PYTHONPATH':'src:.'}),
 ('public-abi',pytest+['tests/unit/ir/test_root_facade_closeout.py','tests/unit/ir/test_schema_catalog.py','tests/unit/core/contracts/test_ir_ref_facades.py','tests/unit/foundry/methods/catalog/causal/test_facade_consumers.py'],product,{'PYTHONPATH':'src:.'}),
 ('worker-gcm',[worker,'-m','pytest','tests/test_worker.py','-k','genuine_gcm_assignment or gcm_fit_removal','-o','addopts=','--import-mode=importlib','-p','no:cacheprovider','-q','-s','--tb=short'],product/'workers/dowhy-014',{'PYTHONPATH':str(product/'workers/dowhy-014')}),
 ('worker-removal',[worker,'/workspace/e02-F-20261006-receipts/graph/removal-gcm-fit.py'],product/'workers/dowhy-014',{'PYTHONPATH':str(product/'workers/dowhy-014')}),
 ('schema-full',[app,'tools/quality/diagnostics/gen_schema.py','--check'],product,{'PYTHONPATH':'src:.'}),
 ('docs-gate',['uv','run','polisyos-tools','validation','check-docs-gate','--repo-root','.','--base-ref',base],product,{'PYTHONPATH':'src:.','UV_PROJECT_ENVIRONMENT':str(pathlib.Path(app).parents[1]),'UV_NO_SYNC':'1'}),
 ('emp01',['/workspace/e02-F-graph-env/bin/python','-m','pytest','-o','addopts=','tests/unit/remediation/test_emp_01.py','-q'],product,{'PYTHONPATH':'src:.:/workspace/e02-F-closeout-20261006/policy-engine/.venv/lib/python3.14/site-packages'}),
]
def run(job):
 name,argv,cwd,extra=job;env=os.environ.copy();env.update(extra)
 started=datetime.datetime.now(datetime.UTC).isoformat();t=time.monotonic()
 with (out/(name+'.stdout.txt')).open('wb') as stdout,(out/(name+'.stderr.txt')).open('wb') as stderr:
  p=subprocess.run(argv,cwd=cwd,env=env,stdout=stdout,stderr=stderr,check=False)
 outputs=[]
 for suffix in ('stdout.txt','stderr.txt'):
  f=out/(name+'.'+suffix);b=f.read_bytes();outputs.append({'path':str(f),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
 d={'source_sha':source,'source_tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=root,text=True).strip(),'argv':argv,'cwd':str(cwd),'environment_overrides':extra,'started_utc':started,'wall_s':time.monotonic()-t,'exit':p.returncode,'outputs':outputs}
 (out/(name+'.json')).write_text(json.dumps(d,indent=2)+'\n')
 return {'job':name,'exit':p.returncode,'wall_s':round(d['wall_s'],2),'bytes':sum(x['bytes'] for x in outputs)}
with concurrent.futures.ThreadPoolExecutor(max_workers=len(jobs)) as pool:
 for result in pool.map(run,jobs):print(json.dumps(result),flush=True)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==source
assert not subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)
