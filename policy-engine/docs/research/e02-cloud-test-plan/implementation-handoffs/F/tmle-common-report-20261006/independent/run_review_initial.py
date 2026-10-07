from __future__ import annotations
import argparse,hashlib,json,os,pathlib,subprocess,time
SCRATCH=pathlib.Path(__file__).parent
REPO=pathlib.Path('/workspace/e02-F-tmle-20261006')
ROOT=REPO/'policy-engine'
PYTHON='/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'
SHA='6c711bd2d4f1b6bf851c42a5f3d22b795efb020d'
PATHS=['policy-engine/src/polisyos/foundry/methods/catalog/causal/treatment_effects.py','policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py','policy-engine/src/polisyos/ir/analytics/causal.py','policy-engine/tests/unit/foundry/methods/catalog/causal/test_tmle_common_report.py','policy-engine/src/polisyos/foundry/methods/components/io.py','policy-engine/src/polisyos/scientist/compute/runner.py']
def source():
 head=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip()
 tree=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD^{tree}'],text=True).strip()
 items=[]
 for path in PATHS:
  actual=(REPO/path).read_bytes();frozen=subprocess.check_output(['git','-C',str(REPO),'show',SHA+':'+path]);assert actual==frozen,path
  items.append({'path':path,'bytes':len(actual),'sha256':hashlib.sha256(actual).hexdigest(),'git_blob':subprocess.check_output(['git','-C',str(REPO),'rev-parse',SHA+':'+path],text=True).strip()})
 assert head==SHA,head
 return {'sha':head,'tree':tree,'files':items}
parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['native','removal-se','removal-order']);args=parser.parse_args()
env=dict(os.environ,PYTHONPATH=str(ROOT/'src')+':'+str(ROOT),PYTHONDONTWRITEBYTECODE='1',E02_TMLE_SOURCE_ROOT=str(ROOT))
independent=str(SCRATCH/'test_independent_tmle_projection.py')
selector=independent+'::test_actual_job_full_adjustment_order_defaults_and_independent_eif_projection'
if args.mode=='native':
 command=[PYTHON,'-m','pytest','-o','addopts=','-p','no:cacheprovider','-q','-s','--tb=short',independent,'tests/unit/foundry/methods/catalog/causal/test_tmle_common_report.py','tests/unit/foundry/methods/catalog/causal/test_treatment_effects.py::test_tmle_targets_deterministically_and_reports_targeting_summary']
else:
 command=[PYTHON,str(SCRATCH/'removal.py'),'report_se' if args.mode=='removal-se' else 'basis_order',selector]
begin=source()
start=time.time()
stdout=SCRATCH/(args.mode+'.stdout.txt');stderr=SCRATCH/(args.mode+'.stderr.txt')
with stdout.open('wb') as out,stderr.open('wb') as err:
 result=subprocess.run(command,cwd=ROOT,env=env,stdout=out,stderr=err,check=False)
elapsed=time.time()-start;end=source()
def binding(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
metadata={'schema':'e02-independent-native-execution-v1','mode':args.mode,'argv':command,'cwd':str(ROOT),'environment_overrides':{k:env[k] for k in ['PYTHONPATH','PYTHONDONTWRITEBYTECODE','E02_TMLE_SOURCE_ROOT']},'source_begin':begin,'source_end':end,'exit_code':result.returncode,'elapsed_seconds':elapsed,'stdout':binding(stdout),'stderr':binding(stderr),'replayer':binding(pathlib.Path(__file__)),'independent_selector':binding(pathlib.Path(independent)),'removal_script':binding(SCRATCH/'removal.py')}
(SCRATCH/(args.mode+'.execution.json')).write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps({'mode':args.mode,'exit_code':result.returncode,'elapsed_seconds':elapsed,'stdout':metadata['stdout'],'stderr':metadata['stderr']}))
