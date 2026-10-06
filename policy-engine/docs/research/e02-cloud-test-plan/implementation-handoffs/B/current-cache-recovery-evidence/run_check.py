"""Freeze full tracked input bytes around one repository diagnostic command."""
import hashlib,json,os,pathlib,platform,resource,subprocess,sys,time
from datetime import datetime,timezone
root=pathlib.Path('/workspace/e02-B-current-execution-state')
label=sys.argv[1];argv=sys.argv[2:]
out=root/'_build/current-execution-state'/label;out.mkdir(parents=True,exist_ok=True)
env=dict(os.environ);env['PYTHONPATH']=str(root/'policy-engine/src')+':'+str(root/'policy-engine')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=root,text=True).strip()
paths=subprocess.check_output(['git','ls-tree','-r','--name-only',head],cwd=root,text=True).splitlines()
def inventory():
 return [{'path':p,'sha256':hashlib.sha256((root/p).read_bytes()).hexdigest(),'bytes':(root/p).stat().st_size} for p in paths]
before=inventory();(out/'input-closure.json').write_text(json.dumps(before,indent=2)+'\n')
start=datetime.now(timezone.utc).isoformat();t=time.perf_counter()
with (out/'stdout.txt').open('w') as log:r=subprocess.run(argv,cwd=root/'policy-engine',env=env,stdout=log,stderr=subprocess.STDOUT)
receipt={'target_sha':head,'candidate_tree_sha':tree,'command':argv,'cwd':str(root/'policy-engine'),'environment':{'python':'/workspace/polisyos/policy-engine/.venv/bin/python','PYTHONPATH':env['PYTHONPATH'],'platform':platform.platform()},'input_closure':{'path':str(out/'input-closure.json'),'sha256':hashlib.sha256((out/'input-closure.json').read_bytes()).hexdigest(),'tracked_paths':len(paths),'additional_git_input':'immutable base198076863e143dea9f89f02734b13d50dae3eed5/tree2b754a92c27959e2e747738d47ed0b419f3b6dd8'},'driver_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'start_utc':start,'end_utc':datetime.now(timezone.utc).isoformat(),'wall_s':time.perf_counter()-t,'max_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'exit':r.returncode,'source_unchanged':head==subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip() and before==inventory(),'outputs':[]}
for p in sorted(out.iterdir()):
 if p.is_file():receipt['outputs'].append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
(out/'wrapper.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt));sys.exit(r.returncode)
