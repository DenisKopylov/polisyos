import subprocess,json,hashlib,os
from pathlib import Path
out=Path('/tmp/e02-F-continuation-20261007/intake/admission');out.mkdir(exist_ok=True)
rows=json.loads(Path('/tmp/e02-F-continuation-20261007/intake/helper-identities.json').read_text());rows.insert(0,{'branch':'codex/e02-F-closeout-20261006','path':'/workspace/e02-F-closeout-20261006','sha':'072d45a56d1119fe3e7665cec2cbbdca015d2934'})
ps=[]
for row in rows:
 name=Path(row['path']).name
 cmd=['uv','run','--no-sync','polisyos-tools','workspace','doctor','--worktree-admission','resume','--branch',row['branch'],'--path',row['path']]
 env=os.environ.copy();env['E02_TOPIC_BRANCH']=row['branch'];env['E02_WORKTREE_ROOT']=row['path']
 stdout=(out/(name+'.json')).open('wb');stderr=(out/(name+'.stderr')).open('wb')
 proc=subprocess.Popen(cmd,cwd='/workspace/e02-F-closeout-20261006/policy-engine',env=env,stdout=stdout,stderr=stderr);ps.append((row,cmd,proc,stdout,stderr))
result=[]
for row,cmd,proc,stdout,stderr in ps:
 rc=proc.wait();stdout.close();stderr.close();p=out/(Path(row['path']).name+'.json');b=p.read_bytes();result.append(row|{'command':cmd,'cwd':'/workspace/e02-F-closeout-20261006/policy-engine','returncode':rc,'full_json':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
(out/'index.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps([{'branch':r['branch'],'returncode':r['returncode']} for r in result]));assert all(r['returncode']==0 for r in result)
