from __future__ import annotations
import json,os,pathlib,subprocess,sys,time,hashlib,platform
cfg=json.loads(pathlib.Path(sys.argv[1]).read_bytes());prefix=pathlib.Path(cfg['prefix']);prefix.parent.mkdir(parents=True,exist_ok=True)
bind=lambda p:{'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
repo=cfg.get('repo');paths=cfg.get('source_paths',[])
def snapshot():
 result=[]
 for p in paths:
  expected=subprocess.check_output(['git','show',cfg['source_sha']+':'+p],cwd=repo);actual=(pathlib.Path(repo)/p).read_bytes()
  assert actual==expected,p
  result.append({'path':p,'bytes':len(actual),'sha256':hashlib.sha256(actual).hexdigest(),'git_blob':subprocess.check_output(['git','rev-parse',cfg['source_sha']+':'+p],cwd=repo).decode().strip()})
 return result
before=snapshot();started=time.monotonic();env=os.environ.copy();env.update(cfg.get('env',{}))
with pathlib.Path(str(prefix)+'.stdout').open('wb') as out,pathlib.Path(str(prefix)+'.stderr').open('wb') as err:
 r=subprocess.run(cfg['argv'],cwd=cfg['cwd'],env=env,stdout=out,stderr=err)
after=snapshot();assert before==after
record={'schema':'independent-native-check/1','config':bind(pathlib.Path(sys.argv[1])),'argv':cfg['argv'],'cwd':cfg['cwd'],'source_sha':cfg.get('source_sha'),'source_tree':subprocess.check_output(['git','rev-parse',cfg['source_sha']+'^{tree}'],cwd=repo).decode().strip() if repo else None,'environment_overrides':cfg.get('env',{}),'launcher_python':platform.python_version(),'source_before':before,'source_after':after,'exit':r.returncode,'wall_s':time.monotonic()-started,'stdout':bind(pathlib.Path(str(prefix)+'.stdout')),'stderr':bind(pathlib.Path(str(prefix)+'.stderr'))}
pathlib.Path(str(prefix)+'.execution.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:v for k,v in record.items() if k not in ['source_before','source_after']}))
raise SystemExit(r.returncode)
