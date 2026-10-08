"""Commission the unchanged source-guarded runner with a unique receipt directory."""
from pathlib import Path
import hashlib,importlib.util,json,os,subprocess,sys,time
D=Path(__file__).parent;SCRIPT=D.parent/'run_frozen_focused_native.py';R=Path('/workspace/e02-F-closeout-20261006');SHA='4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d'
def binding(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def save(name,o):
 with (D/name).open('xb') as f:f.write((json.dumps(o,indent=2)+'\n').encode())
assert binding(SCRIPT)['sha256']=='45eb8bb69d3ac32c5aeeed72396bf72220a7b48c09fae71a71836fe39a645f65'
program="""import importlib.metadata as m,json,sys
from pathlib import Path
versions={}
for n in ('dowhy','numpy','scipy','statsmodels','pytest','pydantic','econml'):
 try:
  dist=m.distribution(n);versions[n]={'version':dist.version,'distribution_root':str(dist.locate_file(''))}
 except m.PackageNotFoundError:versions[n]=None
print(json.dumps({'python':sys.version,'executable':sys.executable,'resolved_executable':str(Path(sys.executable).resolve()),'distributions':versions,'scope':'Current installed environment identity; no backend PASS from parent optional absence.'},sort_keys=True,indent=2))
"""
for role,exe in [('parent',R/'policy-engine/.venv/bin/python'),('worker',R/'policy-engine/workers/dowhy-014/.venv/bin/python')]:
 out=D/(role+'-versions.stdout.json');err=D/(role+'-versions.stderr.txt');a=[str(exe),'-B','-I','-c',program];start=time.perf_counter()
 with out.open('xb') as so,err.open('xb') as se:p=subprocess.run(a,cwd=D,env=os.environ.copy(),stdout=so,stderr=se)
 save(role+'-versions.execution.json',{'argv':a,'cwd':str(D),'exit_code':p.returncode,'outcome':'PASS' if p.returncode==0 else 'ERROR','wall_seconds':time.perf_counter()-start,'stdout':binding(out),'stderr':binding(err),'scope':'Actual environment metadata only; no scientific result.'});assert p.returncode==0
spec=importlib.util.spec_from_file_location('fit_frozen_native_runner',SCRIPT);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
# Only the scratch output directory is selected here. The runner body, exact
# source guards, real three selectors, parent/worker and scientific assertions
# remain unchanged; this avoids copying the frozen script into another carrier.
m.D=D
sys.argv=[str(SCRIPT),'--candidate',SHA,'--checkout',str(R),'--parent-python',str(R/'policy-engine/.venv/bin/python'),'--worker-python',str(R/'policy-engine/workers/dowhy-014/.venv/bin/python')]
save('launcher-input.json',{'actual_argv':sys.argv,'launcher':binding(Path(__file__)),'runner':binding(SCRIPT),'output_directory':str(D),'output_directory_only_override':True,'no_source_or_Git_writes':True,'source_freeze':'ROOT commissioned exact candidate and attached existing checkout.'})
sys.exit(m.main())
