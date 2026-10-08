"""Freeze completed helper captures without future SHA or recursive self-hash."""
from pathlib import Path
import hashlib,json,sys
from transport_text_policy import transport_text_policy
D=Path(__file__).parent;PREFIX='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/continuation-closeout-20261007';selected=D/'selection-final-cdf-v5-completed.json';o=json.loads(selected.read_bytes())
def binding(p):
 h=hashlib.sha256();n=0
 with p.open('rb') as f:
  while b:=f.read(1<<20):n+=len(b);h.update(b)
 return {'bytes':n,'sha256':h.hexdigest()}
assert binding(selected)=={'bytes':1572145,'sha256':'860c3784156b773e8e1a8f9ae47cc0c5d434d66a3e6f52c05009effb548a303d'}
assert not o['pending_extensions'] and not o['draft']
context=[]
for name in ['final-cdf-v5-refresh.execution.json','final-cdf-v5-refresh.stdout.json','final-cdf-v5-refresh.stderr.txt','final-cdf-v5-execution-cli.json','final-cdf-v5-completed-execution-cli.json','root-recovery/final-primary-template-ready.json']:
 p=(D/name) if not name.startswith('root-recovery/') else D.parent.parent/name
 row=next(r for r in o['logical_files'] if r['original_path']==str(p))
 assert binding(p)=={k:row[k] for k in ['bytes','sha256']}
 context.append({'original_path':str(p),**binding(p),'scope':'Original completed ERROR/trace/input, completed CLI or ROOT ready template already preserved in frozen main input. No copied context bodies.'})
files=[]
for name in ['fix-completed-cli.stdout.json','fix-completed-cli.stderr.txt','execute_completed_cli.py','execute-completed-cli.stdout.json','execute-completed-cli.stderr.txt','final-cdf-v5-completed-refresh.execution.json','final-cdf-v5-completed-refresh.stdout.json','final-cdf-v5-completed-refresh.stderr.txt','final-cdf-v5-completed-validate.execution.json','final-cdf-v5-completed-validate.stdout.json','final-cdf-v5-completed-validate.stderr.txt','materialize_late_transport_capture.py','prepare_late_capture_selection.py']:
 p=D/name;encoding='gzip' if transport_text_policy(p)['gzip_required'] else 'identity';files.append({'original_path':str(p),**binding(p),'target_path':PREFIX+'/late-transport-validation/'+name+('.gz' if encoding=='gzip' else ''),'encoding':encoding,'role':'Complete actual completed helper byte-custody output/context/replayer; original outcomes and environmental/source scopes unchanged.'})
plan=D/'late-refresh-validation-selection.json'
obj={'schema':'policyos.e02.complete_late_transport_selection.v1','files':files,'frozen_main_selection':{'original_path':str(selected),**binding(selected)},'already_main_transported_context':context,'actual_document_source':'cdf61b4500e355a27db14260e80ce673ddf8869e','numerical_installed_source':'519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82','exact_ROOT_main_publisher_argv':[sys.executable,str(D/'publish_transport_v5.py'),'--selection',str(selected),'--repository','/workspace/e02-F-closeout-20261006','--materialize','--destination','/workspace/e02-F-closeout-20261006','--primary-template','/tmp/e02-F-continuation-20261007/root-recovery/final-primary-template-ready.json'],'exact_ROOT_late_materialize_argv':[sys.executable,str(D/'materialize_late_transport_capture.py'),'--selection',str(plan),'--materialize','--destination','/workspace/e02-F-closeout-20261006'],'ordering':'ROOT main publisher materializes first, then ROOT late materializer verifies the ACTUAL materialized manifest and frozen selection hash, writes independent complete sidecar. ROOT adds returned actual outputs.json path/hash to its generated primary only; frozen template/selection/main manifest remain unchanged. No future commit SHA is declared.','no_new_scientific_verdict':True,'original_first_refresh':'ERROR; author captured still-open builder stdout as0B, actual completed stdout570B. Original input/argv/trace retained in main; completed binding used in final.','ROOT_primary_source_window':'cdf document carrier only;519 numerical installed candidate remains separate; old d833/old scanner scopes not promoted.'}
with plan.open('xb') as f:f.write((json.dumps(obj,indent=2)+'\n').encode())
print(json.dumps({'plan':{'path':str(plan),**binding(plan)},'late_complete_files':len(files),'new_scientific_tests':0,'root_or_Git_writes':False},indent=2))
