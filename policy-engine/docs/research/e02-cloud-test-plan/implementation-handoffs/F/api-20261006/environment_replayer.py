from pathlib import Path
import importlib.metadata as md,importlib.util,json,platform,subprocess,sys
scratch=Path('/workspace/e02-F-20261006-receipts/api')
packages=['pytest','numpy','scipy','scikit-learn','networkx','lightgbm','ruff','pydantic','hatchling']
versions={}
for name in packages:
    try: versions[name]=md.version(name)
    except md.PackageNotFoundError: versions[name]=None
commands={}
for name,argv in [('uv',['uv','--version']),('node',['node','--version']),('pnpm',['corepack','pnpm','--version'])]:
    r=subprocess.run(argv,capture_output=True,text=True)
    commands[name]={'argv':argv,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
root=Path('/workspace/e02-F-api-20261006')
source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
r={'python':platform.python_version(),'executable':sys.executable,'sys_path':sys.path,'platform':platform.platform(),'source_sha':source,'packages':versions,'tools':commands,'optional_baseline_backends':{name:{'available':importlib.util.find_spec(name) is not None,'outcome':'UNRUN','reason':'Python3.14 baseline marker excluded; availability is never nativebackend witness'} for name in ['dowhy','econml']},'isolation_limits':['Source checks use own cwd PYTHONPATH=src:. and readonly shared application dependencies.','Installed products use distinct owned environments, Python -I and neutral cwd; dependencies reused via direct readonly site path without external editable pth processing.','No shared environment mutation, no process/thread/CPU quotas.'],'canonical_toolchain_difference':['Actual uv0.12.19 differs from canonical contributor0.9.21; actual Node24 differs from Node22 baseline.','Two frontend generators unavailable: complete architecture overallUNRUN; partial artifact red attributionnot_established.']}
(scratch/'environment.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
