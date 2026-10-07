from __future__ import annotations
import argparse,hashlib,json,os,pathlib,subprocess,time
S=pathlib.Path(__file__).parent;REPO=pathlib.Path('/workspace/e02-F-closeout-20261006');ROOT=REPO/'policy-engine';SHA='d09e2b546f5ccf2ed1c297e9578661358270f92b';TREE='ede8862d0204d6d8d34fceb4f425929bd5c093ed';PYTHON=str(ROOT/'.venv/bin/python');WORKER=str(ROOT/'workers/dowhy-014/.venv/bin/python')
PATHS=['policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py','policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_tmle_selected_consumer.py','policy-engine/src/polisyos/foundry/methods/catalog/causal/treatment_effects.py','policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py','policy-engine/src/polisyos/foundry/methods/catalog/causal/protocols.py','policy-engine/src/polisyos/ir/analytics/causal.py','policy-engine/src/polisyos/ir/analytics/uncertainty.py','policy-engine/src/polisyos/scientist/compute/runner.py','policy-engine/src/polisyos/scientist/compute/job_spec.py']
SIBLING='policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_causal_selected_consumers.py'
def bind(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def source():
 head=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip();tree=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD^{tree}'],text=True).strip();rows=[]
 for path in PATHS:
  b=(REPO/path).read_bytes();frozen=subprocess.check_output(['git','-C',str(REPO),'show',SHA+':'+path]);assert b==frozen,path
  rows.append({'path':path,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'git_blob':subprocess.check_output(['git','-C',str(REPO),'rev-parse',SHA+':'+path],text=True).strip(),'source_ref':SHA})
 sibling=bind(REPO/SIBLING);assert (REPO/SIBLING).read_bytes()==subprocess.check_output(['git','-C',str(REPO),'show',head+':'+SIBLING]);sibling['source_ref']=head
 return {'defining_source_sha':SHA,'defining_source_tree':TREE,'checkout_head':head,'checkout_tree':tree,'defining_files':rows,'sibling_source':sibling,'whole_input_denominator':'not_established; notP41'}
parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['native','native-corrected','removal-projection','removal-source']);a=parser.parse_args()
owner='tests/unit/scientist/nodes/builtins/simulate/test_tmle_selected_consumer.py'
if a.mode=='native-corrected':
 argv=[PYTHON,'-m','pytest','-o','addopts=','-p','no:cacheprovider','-q','-s','--tb=short',str(S/'test_independent_tmle_node.py')+'::test_genuine_job_raw_numeric_peer_change_rejected']
elif a.mode=='native':
 argv=[PYTHON,'-m','pytest','-o','addopts=','-p','no:cacheprovider','-q','-s','--tb=short',owner,str(S/'test_independent_tmle_node.py'),'tests/unit/scientist/nodes/builtins/simulate/test_causal_selected_consumers.py::test_selected_scalar_job_persisted_target_fresh_reader','tests/unit/scientist/nodes/builtins/simulate/test_causal_selected_consumers.py::test_real_dowhy_primary_binding_and_canonical_consumer']
else:
 selector=owner+'::'+('test_actual_persisted_reader_refuses_peer_report_change_retaining_result' if a.mode=='removal-projection' else 'test_actual_primary_job_refuses_changed_adjustment_source')
 argv=[PYTHON,str(S/'removal.py'),'projection' if a.mode=='removal-projection' else 'source',selector]
env=dict(os.environ,PYTHONPATH=str(ROOT/'src')+':'+str(ROOT),PYTHONDONTWRITEBYTECODE='1',E02_TMLE_SOURCE_ROOT=str(ROOT),E02_TEST_DOWHY_WORKER_PYTHON=WORKER)
begin=source();start=time.time();out=S/(a.mode+'.stdout.txt');err=S/(a.mode+'.stderr.txt')
with out.open('wb') as o,err.open('wb') as e:result=subprocess.run(argv,cwd=ROOT,env=env,stdout=o,stderr=e)
end=source();assert begin['defining_files']==end['defining_files'] and begin['sibling_source']['sha256']==end['sibling_source']['sha256']
receipt={'schema':'e02-independent-native-execution-v1','mode':a.mode,'argv':argv,'cwd':str(ROOT),'environment_overrides':{k:env[k] for k in ['PYTHONPATH','PYTHONDONTWRITEBYTECODE','E02_TMLE_SOURCE_ROOT','E02_TEST_DOWHY_WORKER_PYTHON']},'source_begin':begin,'source_end':end,'exit_code':result.returncode,'elapsed_seconds':time.time()-start,'stdout':bind(out),'stderr':bind(err),'replayer':bind(pathlib.Path(__file__)),'independent_selector':bind(S/'test_independent_tmle_node.py'),'removal_script':bind(S/'removal.py')}
(S/(a.mode+'.execution.json')).write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'mode':a.mode,'exit_code':result.returncode,'elapsed_seconds':receipt['elapsed_seconds'],'stdout':receipt['stdout'],'stderr':receipt['stderr']}))
