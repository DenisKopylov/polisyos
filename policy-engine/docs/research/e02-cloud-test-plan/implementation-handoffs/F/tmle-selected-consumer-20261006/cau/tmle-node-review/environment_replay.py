import importlib.metadata,json,pathlib,platform,subprocess,sys
from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as node
from polisyos.foundry.methods.catalog.causal import treatment_effects,tmle_core
worker='/workspace/e02-F-closeout-20261006/policy-engine/workers/dowhy-014/.venv/bin/python'
script="import importlib.metadata,json,platform,sys;print(json.dumps({'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'distributions':sorted([{'name':d.metadata['Name'],'version':d.version} for d in importlib.metadata.distributions()],key=lambda d:d['name'].lower())}))"
observed=subprocess.run([worker,'-c',script],capture_output=True,text=True,check=False)
result={'app':{'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'origins':{'node':node.__file__,'tmle':treatment_effects.__file__,'core':tmle_core.__file__},'distributions':sorted([{'name':d.metadata['Name'],'version':d.version} for d in importlib.metadata.distributions()],key=lambda d:d['name'].lower())},'worker':{'exit_code':observed.returncode,'stdout':observed.stdout,'stderr':observed.stderr,'environment':json.loads(observed.stdout) if observed.returncode==0 else None},'profile':'App3.14 nativeTMLE; genuine isolated selected3.12 worker DoWhy sibling; no shim/absencePASS or authorityclaim.'}
pathlib.Path(__file__).with_name('environment.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'app_python':sys.version,'worker_python':result['worker']['environment']['python'],'worker_return_code':observed.returncode}))
