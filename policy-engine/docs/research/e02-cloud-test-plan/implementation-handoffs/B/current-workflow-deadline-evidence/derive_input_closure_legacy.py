"""Derive a receipt's file-hash manifest from immutable Git inputs, without a checkout."""
from __future__ import annotations
import argparse, hashlib, json, subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source-sha',required=True);p.add_argument('--kind',choices=('native','full-tracked'),required=True);p.add_argument('--test-file',action='append',default=[]);p.add_argument('--overlay',action='append',default=[]);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
paths=subprocess.check_output(['git','ls-tree','-r','--name-only',a.source_sha],text=True).splitlines()
if a.kind=='native':
 paths=[n for n in paths if n.endswith('.py') and (n.startswith('policy-engine/src/') or n.endswith('conftest.py'))]
 paths+=['policy-engine/pyproject.toml','policy-engine/uv.lock','policy-engine/pytest.ini',*a.test_file]
paths=sorted(set(paths)); overlays=dict(item.rsplit('=',1) for item in a.overlay)
a.output.parent.mkdir(parents=True,exist_ok=True)
requests=a.output.with_suffix('.git-requests.txt');requests.write_text(''.join(overlays.get(n,a.source_sha)+':'+n+'\n' for n in paths))
result=[]
with requests.open('rb') as request:
 child=subprocess.Popen(['git','cat-file','--batch'],stdin=request,stdout=subprocess.PIPE)
 for name in paths:
  header=child.stdout.readline().decode().split()
  if len(header)!=3 or header[1]!='blob':raise RuntimeError('Git blob unavailable: '+name+' '+repr(header))
  remaining=int(header[2]); size=remaining;digest=hashlib.sha256()
  while remaining:
   data=child.stdout.read(min(1048576,remaining))
   if not data:raise RuntimeError('incomplete Git blob '+name)
   digest.update(data);remaining-=len(data)
  if child.stdout.read(1)!=b'\n':raise RuntimeError('invalid Git batch delimiter')
  result.append({'path':name,'sha256':digest.hexdigest(),'bytes':size})
 if child.wait()!=0:raise RuntimeError('Git batch failed')
a.output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'path':str(a.output),'source_sha':a.source_sha,'kind':a.kind,'paths':len(result),'bytes':a.output.stat().st_size,'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest()}))
