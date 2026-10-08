"""Run exactly commissioned frozen source's three real selected-worker consumers.
No checkout, source/Git/environment synchronization or scheduler/quota mutations.
"""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess,sys,time,xml.etree.ElementTree as ET
D=Path(__file__).parent
TEST='tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py'
NAMES=['test_public_complete_report_builder_abi_and_real_producer_invocation','test_real_worker_job_cas_fresh_python314_reader','test_real_estimate_point_only_survives_parent_cas_and_reader']
def binding(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def file_binding(p):return binding(p.read_bytes())
def save(name,obj):
 p=D/name
 with p.open('xb') as f:f.write((json.dumps(obj,indent=2)+'\n').encode())
 return {'path':str(p),**file_binding(p)}
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--candidate',required=True);ap.add_argument('--checkout',type=Path,required=True);ap.add_argument('--parent-python',type=Path,required=True);ap.add_argument('--worker-python',type=Path,required=True);a=ap.parse_args()
 if not re.fullmatch('[0-9a-f]{40}',a.candidate):raise ValueError('Exact frozen source SHA required')
 checkout=a.checkout.resolve();cwd=checkout/'policy-engine'
 def git(*v):return subprocess.check_output(['git','-C',str(checkout),*v])
 def guard():
  head=git('rev-parse','HEAD').decode().strip();assert head==a.candidate,(head,a.candidate)
  branch=git('symbolic-ref','-q','HEAD').decode().strip()
  status=git('status','--porcelain=v1','--untracked-files=all').decode()
  assert not any(line and not line.startswith('?? ') for line in status.splitlines()),status
  providers=[
   'tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py',
   'src/polisyos/foundry/methods/catalog/causal/dowhy_identify_estimate.py',
   'src/polisyos/foundry/methods/catalog/causal/_dowhy_worker.py',
   'src/polisyos/ir/analytics/causal.py',
   'src/polisyos/ir/analytics/uncertainty.py',
   'src/polisyos/scientist/compute/runner.py',
   'src/polisyos/foundry/methods/components/io.py',
   'workers/dowhy-014/worker.py','workers/dowhy-014/protocol.py',
   'workers/dowhy-014/uv.lock','workers/dowhy-014/pyproject.toml',
   'workers/dowhy-014/.python-version',
  ]
  rows=[]
  for path in providers:
   full='policy-engine/'+path;raw=git('show',a.candidate+':'+full);working=(cwd/path).read_bytes();assert working==raw,path
   rows.append({'path':full,'git_ref':a.candidate,'git_blob':git('rev-parse',a.candidate+':'+full).decode().strip(),**binding(raw),'working_bytes_equal_Git':True})
  return {'head':head,'tree':git('rev-parse',a.candidate+'^{tree}').decode().strip(),'branch':branch,'actual_status':status,'tracked_clean':True,'complete_guard_path_set':rows,'scope':'Current exact selected test + enumerated direct producer/report/runner/io/profile inputs and actual whole tracked-diff guard. Not a full dynamic callgraph or production input census.'}
 begin=guard();assert a.parent_python.is_file() and a.worker_python.is_file()
 tmp=D/'frozen-native-cas';assert not tmp.exists(),'Never delete/reuse an existing basetemp'
 env=os.environ.copy();env.update(POLISYOS_METRICS_PORT='9468',PYTHONPATH=str(cwd/'src')+':'+str(cwd/'tools'),E02_TEST_DOWHY_WORKER_PYTHON=str(a.worker_python),PYTHONDONTWRITEBYTECODE='1',MPLCONFIGDIR=str(D/'mpl-native'))
 junit=D/'frozen-native.junit.xml';out=D/'frozen-native.stdout.txt';err=D/'frozen-native.stderr.txt';rss=D/'frozen-native.time.txt'
 pyargv=[str(a.parent_python),'-B','-m','pytest',*[TEST+'::'+n for n in NAMES],'-o','addopts=','--import-mode=importlib','-p','no:cacheprovider','-q','-s','--tb=short','--basetemp='+str(tmp),'--junitxml='+str(junit)]
 assert hasattr(os,'wait4');argv=pyargv
 spec={'candidate_sha':a.candidate,'candidate_tree_sha':begin['tree'],'argv':argv,'pytest_argv':pyargv,'cwd':str(cwd),'environment_overrides':{k:env[k] for k in ['POLISYOS_METRICS_PORT','PYTHONPATH','E02_TEST_DOWHY_WORKER_PYTHON','PYTHONDONTWRITEBYTECODE','MPLCONFIGDIR']},'inherited_environment':True,'CPU_thread_worker_process_quota_added':False,'native_backend_profile':'Actual configured standalone Python3.12 DoWhy0.14; application baseline remains3.14 with DoWhy/EconML exclusions. No mock estimator/skip/missing-backend substitution.','test_scope':'Three current exact-source actual MethodJob/producer/public factory/CAS/fresh3.14 interval non-gating and genuinely fitted point-only readers; known synthetic DGP only. No authority or admitted shared study budget positive.','start_guard':begin,'runner':{'path':str(Path(__file__).resolve()),**file_binding(Path(__file__))},'parent_interpreter':{'path':str(a.parent_python),'resolved':str(a.parent_python.resolve())},'worker_interpreter':{'path':str(a.worker_python),'resolved':str(a.worker_python.resolve())}}
 save('frozen-native.spec.json',spec)
 start=time.perf_counter()
 with out.open('xb') as so,err.open('xb') as se:
  p=subprocess.Popen(argv,cwd=cwd,env=env,stdout=so,stderr=se)
  waited_pid,wait_status,usage=os.wait4(p.pid,0);assert waited_pid==p.pid
  p.returncode=os.waitstatus_to_exitcode(wait_status)
 with rss.open('xb') as f:
  f.write((json.dumps({'measurement':'Linux os.wait4 actual native pytest process rusage','pid':p.pid,'ru_maxrss_KiB':usage.ru_maxrss,'user_cpu_seconds':usage.ru_utime,'system_cpu_seconds':usage.ru_stime,'scope':'Actual child/waited descendants high-water rusage, not simultaneous aggregate cgroup peak or global CPU budget proof. No optional external time executable, quota or timeout added.'},indent=2)+'\n').encode())
 wall=time.perf_counter()-start;end=guard();assert begin['complete_guard_path_set']==end['complete_guard_path_set']
 counts=None
 if junit.exists():
  tree=ET.parse(junit);cases=tree.findall('.//testcase');counts={'tests':len(cases),'failures':sum(x.find('failure') is not None for x in cases),'errors':sum(x.find('error') is not None for x in cases),'skips':sum(x.find('skipped') is not None for x in cases)};counts['passes']=counts['tests']-counts['failures']-counts['errors']-counts['skips']
 record={'candidate_sha':a.candidate,'candidate_tree_sha':begin['tree'],'exit_code':p.returncode,'outcome':'PASS' if p.returncode==0 and counts and counts['tests']==3 and counts['passes']==3 else 'ERROR' if counts is None else 'SKIP' if counts['skips'] else 'FAIL','wall_seconds':wall,'junit_counts':counts,'spec':{'path':str(D/'frozen-native.spec.json'),**file_binding(D/'frozen-native.spec.json')},'stdout':{'path':str(out),**file_binding(out)},'stderr':{'path':str(err),**file_binding(err)},'time_full_output':{'path':str(rss),**file_binding(rss)},'junit':{'path':str(junit),**file_binding(junit)} if junit.exists() else None,'end_guard':end,'scope':'Actual3-case scientific/backend/consumer witness only; no formal finding closure, production assumptions, causal authority or B56 admission claim.'}
 save('frozen-native.receipt.json',record);print(json.dumps(record,indent=2));return p.returncode
if __name__=='__main__':sys.exit(main())
