"""Local G replay with actual catalog custody and an isolated runtime fixture."""
from __future__ import annotations
import argparse,datetime,hashlib,json,os,pathlib,platform,subprocess,time,xml.etree.ElementTree as ET
p=argparse.ArgumentParser();p.add_argument('--repo',type=pathlib.Path,required=True);p.add_argument('--python',type=pathlib.Path,required=True);p.add_argument('--sha',required=True);p.add_argument('--out',type=pathlib.Path,required=True);args=p.parse_args()
repo=args.repo.resolve();cwd=repo/'policy-engine';out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
def git(*argv):return subprocess.check_output(['git',*argv],cwd=repo,text=True).strip()
def source():return {'sha':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'status':git('status','--porcelain'),'branch':git('symbolic-ref','--short','HEAD')}
def identity(path):
 result={'path':str(path),'resolved_path':str(path.resolve()),'is_file':path.is_file()}
 if path.is_file():
  h=hashlib.sha256()
  with path.open('rb') as f:
   for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
  result.update(bytes=path.stat().st_size,sha256=h.hexdigest())
 return result
before=source();assert before['sha']==args.sha and not before['status'],before
catalog=cwd/'production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb'
overlay=cwd/'architecture/policy_design_case/layer3_gy_acquisition_overlay.duckdb'
test=cwd/'tests/integration/scientist/test_res_03_real_simulation_route.py'
inputs={'catalog':identity(catalog),'acquisition_overlay':identity(overlay),'test':identity(test)}
env=os.environ.copy();env.update(PYTHONPATH='src',POLISYOS_METRICS_PORT='0',PYTHONDONTWRITEBYTECODE='1')
argv=[str(args.python.resolve()),'-m','pytest','-o','addopts=','-o',f'cache_dir={out / "cache"}','-q','tests/integration/scientist/test_res_03_real_simulation_route.py',f'--basetemp={out / "fixture"}',f'--junitxml={out / "junit.xml"}']
packet={'source_before':before,'inputs_before':inputs,'argv':argv,'cwd':str(cwd),'executable':str(args.python.resolve()),'environment':{k:env[k] for k in ('PYTHONPATH','POLISYOS_METRICS_PORT','PYTHONDONTWRITEBYTECODE')},'python':subprocess.check_output([str(args.python.resolve()),'--version'],text=True).strip(),'start_utc':datetime.datetime.now(datetime.UTC).isoformat(),'namespace':'local G production-input replay; distinct from B cloud producer receipt'}
if not inputs['catalog']['is_file']:
 packet.update(outcome='UNRUN',reason='actual production catalog required by default lifecycle startup is absent',source_after=source());(out/'receipt.json').write_text(json.dumps(packet,indent=2)+'\n');raise SystemExit(2)
start=time.monotonic()
with (out/'stdout.txt').open('wb') as log:
 child=subprocess.Popen(argv,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT);_,status,usage=os.wait4(child.pid,0);child.returncode=os.waitstatus_to_exitcode(status)
packet.update(exit_code=child.returncode,wall_seconds=time.monotonic()-start,max_rss=usage.ru_maxrss,rss_unit='bytes' if platform.system()=='Darwin' else 'KiB',resource_method='direct wait4 child rusage',source_after=source(),inputs_after={'catalog':identity(catalog),'acquisition_overlay':identity(overlay),'test':identity(test)},end_utc=datetime.datetime.now(datetime.UTC).isoformat())
cases=ET.parse(out/'junit.xml').getroot().findall('.//testcase') if (out/'junit.xml').is_file() else []
counts={'total':len(cases),'pass':sum(all(c.find(k) is None for k in ['failure','error','skipped']) for c in cases),'fail':sum(c.find('failure') is not None for c in cases),'error':sum(c.find('error') is not None for c in cases),'skip':sum(c.find('skipped') is not None for c in cases)}
packet.update(native_cases=counts,outcome='PASS' if child.returncode==0 and counts=={'total':1,'pass':1,'fail':0,'error':0,'skip':0} else 'FAIL' if child.returncode else 'UNRESOLVED')
if packet['source_after']!=before or packet['inputs_after']!=inputs:packet.update(outcome='UNRESOLVED',reason='candidate or actual production input changed during replay')
for name in ['stdout.txt','junit.xml']:
 f=out/name
 if f.is_file():packet.setdefault('outputs',{})[name]=identity(f)
(out/'receipt.json').write_text(json.dumps(packet,indent=2)+'\n');print(json.dumps(packet,indent=2));raise SystemExit(child.returncode if packet['outcome']!='UNRESOLVED' else 2)
