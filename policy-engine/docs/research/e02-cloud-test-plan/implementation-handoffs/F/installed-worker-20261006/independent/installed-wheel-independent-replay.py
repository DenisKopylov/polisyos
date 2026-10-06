import os,subprocess,time,json,hashlib,zipfile,resource
from pathlib import Path
w=Path('/workspace/e02-F-installed-worker-20261006');scratch=Path('/workspace/e02-F-20261006-receipts/installed-worker');out=Path('/workspace/e02-F-20261006-receipts/dowhy');stem='installed-wheel-ab56-independent'
def git(*args):return subprocess.check_output(['git',*args],cwd=w,text=True).strip()
def ref(p):
 p=Path(p);b=p.read_bytes();return {'path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
source=git('rev-parse','HEAD');tree=git('rev-parse','HEAD^{tree}');assert source=='ab56a0f3414c6e903f7dcdaaa7b7ed540b1923c5';assert git('diff','--name-only')=='' and git('diff','--cached','--name-only')==''
manifest=json.loads((scratch/'wheel-setup-manifest.json').read_text());assert manifest['source_sha']==source
wheel=Path(manifest['artifact']);assert ref(wheel)['sha256']==manifest['artifact_sha256'];site=Path(manifest['site']);profile=site/'polisyos/foundry/methods/catalog/causal/_dowhy_profile'
bindings=[]
for name,entry in manifest['assets'].items():
 b=(profile/name).read_bytes();actual=subprocess.check_output(['git','show',source+':'+entry['source_path']],cwd=w);assert b==actual and hashlib.sha256(b).hexdigest()==entry['sha256'];bindings.append({'installed_path':str(profile/name),'source_path':entry['source_path'],'sha256':entry['sha256'],'bytes':len(b)})
for name,entry in manifest['carriers'].items():
 b=(Path(manifest['consumer'])/name).read_bytes();actual=subprocess.check_output(['git','show',source+':'+entry['source_path']],cwd=w);assert b==actual and hashlib.sha256(b).hexdigest()==entry['sha256'];bindings.append({'installed_path':str(Path(manifest['consumer'])/name),'source_path':entry['source_path'],'sha256':entry['sha256'],'bytes':len(b)})
# Complete runtime-code denominator from the actual wheel; no sampled origin inference.
with zipfile.ZipFile(wheel) as z:
 records=[]
 for path in sorted(z.namelist()):
  if not path.endswith('.py') or not (path.startswith('polisyos/') or path.startswith('tools/')):continue
  name=Path(path).name
  if path.startswith('polisyos/foundry/methods/catalog/causal/_dowhy_profile/'):
   source_path='policy-engine/workers/dowhy-014/'+name
  else:source_path='policy-engine/'+('src/' if path.startswith('polisyos/') else '')+path
  blob=z.read(path);tracked=subprocess.check_output(['git','show',source+':'+source_path],cwd=w);assert blob==tracked and (site/path).read_bytes()==blob,path
  records.append({'path':path,'source_path':source_path,'sha256':hashlib.sha256(blob).hexdigest()})
 code_denominator={'file_type_paths':'All actual wheel polisyos/**/*.py + tools/**/*.py including projected private worker Python assets','files':len(records),'path_content_sha256':hashlib.sha256(json.dumps(records,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'archive_installed_git_discrepancies':0}
cmd=[str(scratch/'wheel-env/bin/python'),'-I',str(scratch/'final_launch.py'),'wheel'];t=time.monotonic();env=os.environ.copy();env.pop('PYTHONPATH',None)
with (out/(stem+'.stdout')).open('wb') as a,(out/(stem+'.stderr')).open('wb') as b:r=subprocess.run(cmd,cwd=manifest['consumer'],env=env,stdout=a,stderr=b,timeout=180)
for entry in bindings:assert Path(entry['installed_path']).read_bytes()==subprocess.check_output(['git','show',source+':'+entry['source_path']],cwd=w),entry
for record in records:assert hashlib.sha256((site/record['path']).read_bytes()).hexdigest()==record['sha256'],record['path']
assert not (profile/'worker.py.e02-temporarily-retired').exists();assert git('rev-parse','HEAD')==source and git('diff','--name-only')=='' and git('diff','--cached','--name-only')==''
d={'schema':'policyos.e02.independent_native_run.v1','source_sha':source,'tree':tree,'command':cmd,'cwd':manifest['consumer'],'environment':{'python_isolated':'-I','PYTHONPATH':'unset','worker_interpreter':'/workspace/e02-F-dowhy-20261006/policy-engine/workers/dowhy-014/.venv/bin/python','application_dependencies':'owned installed product plus readonly shared third-party .pth; no independently resolved whole app environment'},'process_exit_code':r.returncode,'wall_s':time.monotonic()-t,'rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'manifest':ref(scratch/'wheel-setup-manifest.json'),'launcher':ref(scratch/'final_launch.py'),'artifact':ref(wheel),'bindings':bindings,'complete_wheel_python_input_denominator':code_denominator,'source_after':git('rev-parse','HEAD'),'tracked_source_after_clean':True,'actual_status_after':git('status','--porcelain'),'all_assets_and_runtime_code_restored_exact':True,'outputs':{k:ref(out/(stem+'.'+k)) for k in ('stdout','stderr')}}
(out/(stem+'.json')).write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d,indent=2));print('\n'.join((out/(stem+'.stdout')).read_text().splitlines()[-5:]))
