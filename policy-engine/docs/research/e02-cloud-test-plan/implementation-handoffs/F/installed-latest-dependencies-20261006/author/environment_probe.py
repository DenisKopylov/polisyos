import importlib.metadata,json,pathlib,platform,subprocess,sys
records={}
for p in ['policy-engine','pytest','numpy','scipy','scikit-learn','networkx','lightgbm','dowhy','econml']:
 try:records[p]=importlib.metadata.version(p)
 except importlib.metadata.PackageNotFoundError:records[p]=None
root=pathlib.Path('/workspace/e02-F-installed-worker-20261006');app=root/'policy-engine'
worker='/workspace/e02-F-dowhy-20261006/policy-engine/workers/dowhy-014/.venv/bin/python'
workerprobe=subprocess.check_output([worker,'-I','-c',"import importlib.metadata,json,platform,sys;print(json.dumps({'python':platform.python_version(),'executable':sys.executable,'packages':{p:importlib.metadata.version(p) for p in ['dowhy','numpy','scipy','pandas','scikit-learn','networkx']}}))"],text=True)
print(json.dumps({'python':platform.python_version(),'executable':sys.executable,'prefix':sys.prefix,'sys_path':sys.path,'isolated':sys.flags.isolated,'application_packages':records,'baseline_markers':{'dowhy':"python_version < '3.13' (>=0.13,<0.14)",'econml':'python_version < 3.14'},'worker':json.loads(workerprobe),'uv':subprocess.check_output(['uv','--version'],text=True).strip(),'node':subprocess.check_output(['node','--version'],text=True).strip(),'pnpm':subprocess.check_output(['pnpm','--version'],text=True).strip(),'environment_mutations':'owned wheel/sdist installed sites only; shared app and worker .venv read-only','cloud_compute_policy':'no artificial CPU, process, or thread quota; all ready checks started'} ,indent=2))
