"""Capture independent read-only mixed consumer controls against a real native CAS."""
import hashlib,json,os,platform,subprocess,time
from pathlib import Path
root=Path('/workspace/e02-F-tmle-20261006')
out=Path('/tmp/e02-F-continuation-20261007/foundry/fit-composed-review')
sha='0c81614f5aa737a4b26c6c74044955a842b26cf4'
python='/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'
packet=out/'native-tmp/tmle-consumers0/producer-packet.json'
replay=out/'check_mixed_native_consumer.py'
def git(*args):return subprocess.check_output(['git','-C',str(root),*args])
def guard():
 assert git('rev-parse','HEAD').decode().strip()==sha
 assert not git('status','--porcelain')
 return {'sha':sha,'tree':git('rev-parse','HEAD^{tree}').decode().strip(),'status':'clean'}
def ref(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
env=os.environ.copy();env['PYTHONPATH']=str(root/'policy-engine/src')+':'+str(root/'policy-engine/tools')
before=guard();runs=[]
for mode in ('mixed_priority','malformed_top','remove_role_issue'):
 argv=[python,str(replay),str(packet),mode]
 stdout=out/(mode+'.stdout.txt');stderr=out/(mode+'.stderr.txt')
 start=time.monotonic()
 with stdout.open('wb') as so,stderr.open('wb') as se:
  process=subprocess.Popen(argv,cwd=root/'policy-engine',env=env,stdout=so,stderr=se)
 runs.append((mode,argv,stdout,stderr,start,process))
results=[]
for mode,argv,stdout,stderr,start,process in runs:
 code=process.wait()
 expected=1 if mode=='remove_role_issue' else 0
 raw=stdout.read_text();err=stderr.read_text()
 complete=(code==expected and '"native_status": "success"' in raw)
 if mode=='remove_role_issue':complete=complete and 'AssertionError' in err and '"causal_blocker_count": 0' in raw and '"marker_preserved": true' in raw
 result={'mode':mode,'source_guard':before,'command':argv,'cwd':str(root/'policy-engine'),'environment':{'python':python,'PYTHONPATH':env['PYTHONPATH'],'new_quota':False,'worker_required':False,'backend':'actual native NumPy/scikit-learn TMLE persisted producer and actual Confidence/value consumers'},'packet':ref(packet),'replayer':ref(replay),'exit_code':code,'expected_exit_code':expected,'wall_until_wait_seconds':time.monotonic()-start,'outcome':'PASS' if complete else 'FAIL','observed_runtime_result':'expected_assertion_failure_after_actual_consumer' if mode=='remove_role_issue' and complete else 'actual_consumer_pass' if complete else 'not_established','stdout':ref(stdout),'stderr':ref(stderr),'source_guard_after':guard()}
 (out/(mode+'.json')).write_text(json.dumps(result,indent=2)+'\n');results.append(result)
(out/'mixed-controls.json').write_text(json.dumps({'source':before,'runs':results,'outcome':'PASS' if all(x['outcome']=='PASS' for x in results) else 'FAIL'},indent=2)+'\n')
print(json.dumps([{'mode':x['mode'],'exit':x['exit_code'],'outcome':x['outcome']} for x in results]))
