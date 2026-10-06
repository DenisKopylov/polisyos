import hashlib,json,os,subprocess,tarfile,time,zipfile
from pathlib import Path
root=Path('/workspace/e02-F-installed-worker-20261006');author=Path('/workspace/e02-F-20261006-receipts/installed-latest');out=Path('/workspace/e02-F-20261006-receipts/final-root/installed-latest-independent');source='5cd190d24d133f618fcc66ecc01f70c8a1b4f1f6'
a=json.loads((author/'archive-source-bindings.json').read_text());ins=json.loads((author/'installed-source-bindings.json').read_text());assert a['source_sha']==ins['source_sha']==source
assert a['total_byte_bound']==2917 and all(p['byte_bindings']==2917 for p in ins['profiles'].values())
def show(path):return subprocess.check_output(['git','show',source+':'+path],cwd=root)
def digest(raw):return hashlib.sha256(raw).hexdigest()
# Batch Git source-byte denominator; archives and installed tree are read directly again.
paths={b['source_path'] for b in a['bindings']}
with zipfile.ZipFile(a['wheel']['path']) as wheel:
 actualpy=sorted(n for n in wheel.namelist() if n.endswith('.py') and n.startswith(('polisyos/','tools/')))
 py_sources={n:('policy-engine/workers/dowhy-014/'+Path(n).name if n.startswith('polisyos/foundry/methods/catalog/causal/_dowhy_profile/') else 'policy-engine/src/'+n if n.startswith('polisyos/') else 'policy-engine/'+n) for n in actualpy}
 paths.update(py_sources.values());ordered=sorted(paths)
 batch=subprocess.run(['git','cat-file','--batch'],input=''.join(source+':'+p+'\n' for p in ordered).encode(),cwd=root,capture_output=True,check=True).stdout
 blobs={};cursor=0
 for path in ordered:
  e=batch.index(b'\n',cursor);header=batch[cursor:e].decode().split();assert len(header)==3 and header[1]=='blob',(path,header)
  count=int(header[2]);raw=batch[e+1:e+1+count];assert batch[e+1+count:e+2+count]==b'\n';cursor=e+2+count;blobs[path]=(raw,header[0])
 assert cursor==len(batch)
 with tarfile.open(a['sdist']['path'],'r:gz') as tar:
  members={m.name.split('/',1)[1]:m for m in tar.getmembers() if m.isfile() and '/' in m.name}
  checks=[]
  for b in a['bindings']:
   raw,blob=blobs[b['source_path']];assert blob==b['git_blob'] and digest(raw)==b['sha256'] and len(raw)==b['bytes']
   assert wheel.read(b['wheel_path'])==raw
   assert tar.extractfile(members[b['sdist_path']]).read()==raw
   per={}
   for kind,profile in ins['profiles'].items():
    path=Path(profile['site'])/b['wheel_path'];assert path.read_bytes()==raw;per[kind]=str(path)
   checks.append({'source_path':b['source_path'],'git_blob':blob,'sha256':digest(raw),'bytes':len(raw),'archive_paths':{k:b[k+'_path'] for k in ['wheel','sdist']},'installed_paths':per})
  python_checks=[]
  for member,path in py_sources.items():
   raw,blob=blobs[path];assert wheel.read(member)==raw
   sdist_member=path.removeprefix('policy-engine/');assert tar.extractfile(members[sdist_member]).read()==raw
   for profile in ins['profiles'].values():assert (Path(profile['site'])/member).read_bytes()==raw
   python_checks.append({'wheel_path':member,'source_path':path,'git_blob':blob,'sha256':digest(raw),'bytes':len(raw)})
  for kind,profile in ins['profiles'].items():
   site=Path(profile['site']);actual_installed={str(p.relative_to(site)) for top in ['polisyos','tools'] for p in (site/top).rglob('*.py')};assert actual_installed==set(actualpy),(kind,len(actual_installed),len(actualpy),list(actual_installed-set(actualpy))[:5])
proof={'source_sha':source,'source_tree':a['source_tree'],'product_byte_denominator':len(checks),'actual_python_denominator':len(python_checks),'profile_count':2,'byte_violations':0,'six_profile_assets_restored':True,'product_bindings':checks,'all_actual_python_bindings':python_checks}
(out/'full-source-archive-installed-bindings.json').write_text(json.dumps(proof,indent=2)+'\n')
# Independent Python-I runtime readback; no profile asset retirement or mutation.
results=[];env=os.environ.copy();env.pop('PYTHONPATH',None);env['PYTHONDONTWRITEBYTECODE']='1'
for kind in ['wheel','sdist']:
 manifest=json.loads((author/(kind+'-setup-manifest.json')).read_text());cmd=[manifest['python'],'-I',str(author/'compatibility_launch.py'),kind];start=time.monotonic();p=subprocess.run(cmd,cwd=manifest['consumer'],env=env,capture_output=True);wall=time.monotonic()-start
 (out/(kind+'-compatibility.stdout.txt')).write_bytes(p.stdout);(out/(kind+'-compatibility.stderr.txt')).write_bytes(p.stderr)
 r={'source_sha':source,'profile':kind,'command':cmd,'cwd':manifest['consumer'],'environment':{'PYTHONPATH':'unset','PYTHONDONTWRITEBYTECODE':'1','Python-I':True},'exit':p.returncode,'outcome':'PASS' if p.returncode==0 else 'FAIL','wall_s':wall,'output':str(out/(kind+'-compatibility.stdout.txt')),'stderr':str(out/(kind+'-compatibility.stderr.txt'))}
 results.append(r);assert p.returncode==0,p.stdout[-2000:]
 print(kind,p.returncode,wall,p.stdout.decode().splitlines()[1:5])
# All six private assets still intact after read-only replays.
for kind in ['wheel','sdist']:
 manifest=json.loads((author/(kind+'-setup-manifest.json')).read_text());private=Path(manifest['site'])/'polisyos/foundry/methods/catalog/causal/_dowhy_profile'
 for name,b in manifest['assets'].items():assert digest((private/name).read_bytes())==b['sha256']
summary={'source_sha':source,'source_tree':a['source_tree'],'byte_proof_output':str(out/'full-source-archive-installed-bindings.json'),'native_checks':results,'decision':'GO_bounded_installed_identity_and_ABI','product_byte_denominator':2917,'actual_python_denominator':len(actualpy),'live_backend_numerical_cases':'Author actuallatest wheel3/sdist3 outputs separately sourcebound; reviewer has not repeated asset-mutating3-case suites.','profile_assets_unchanged':True,'limits':['No real-data/source authority or production admission.','Dependencies reused readonly, not independently resolved.','Oldab56source green is not used as latestsource proof; all current5cd Git/archive/site bytes rechecked directly.']}
(out/'replay-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
