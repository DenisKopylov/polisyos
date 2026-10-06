import concurrent.futures,hashlib,json,os,subprocess,time
from pathlib import Path
out=Path(__file__).parent;author=Path('/workspace/e02-F-20261006-receipts/installed-latest')
source='5cd190d24d133f618fcc66ecc01f70c8a1b4f1f6'
env=os.environ.copy();env.pop('PYTHONPATH',None);env['PYTHONDONTWRITEBYTECODE']='1'
def run(kind):
 m=json.loads((author/(kind+'-setup-manifest.json')).read_text());cmd=[m['python'],'-I',str(out/'cache_abi_launch.py'),kind];start=time.monotonic();p=subprocess.run(cmd,cwd=m['consumer'],env=env,capture_output=True);wall=time.monotonic()-start
 refs={}
 for stream,raw in [('stdout',p.stdout),('stderr',p.stderr)]:
  path=out/(kind+'-cache-abi.'+stream+'.txt');path.write_bytes(raw);refs[stream]={'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
 for name,b in m['assets'].items():assert hashlib.sha256((Path(m['site'])/'polisyos/foundry/methods/catalog/causal/_dowhy_profile'/name).read_bytes()).hexdigest()==b['sha256']
 return {'source_sha':source,'source_tree':'c75afd88c27037708844f48d7789fbcbe84a4797','profile':kind,'command':cmd,'cwd':m['consumer'],'environment':{'PYTHONPATH':'unset','PYTHONDONTWRITEBYTECODE':'1','Python-I':True},'wall_s':wall,'exit':p.returncode,'outcome':'PASS' if p.returncode==0 else 'FAIL','output':refs['stdout']['path'],'output_ref':refs['stdout'],'stderr':refs['stderr'],'profile_assets_unchanged':True}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(run,['wheel','sdist']))
(out/'cache-abi-pair.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2));assert all(r['exit']==0 for r in rows)
