"""Forward correction: bind completed stdout, preserve first failed CLI/trace."""
from pathlib import Path
import hashlib,json
D=Path(__file__).parent
old=D/'own-helper-final-selection.json';obj=json.loads(old.read_bytes())
def binding(p):
 b=p.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def write(p,o):
 with p.open('xb') as f:f.write((json.dumps(o,indent=2)+'\n').encode())
rows=[];changes=[]
for row in obj['files']:
 actual=binding(Path(row['path']))
 if actual!={k:row[k] for k in ('bytes','sha256')}:changes.append({'path':row['path'],'selected':{k:row[k] for k in ('bytes','sha256')},'actual_completed':actual})
 rows.append({**row,**actual})
assert len(changes)==1 and changes[0]['path']==str(D/'build-final-cli.stdout.json')
extras=['own-helper-final-selection.json','final-cdf-v5-execution-cli.json','final-cdf-v5-cli-inputs.json','freeze_and_run_final_transport.py','final-cdf-v5-refresh.execution.json','final-cdf-v5-refresh.stdout.json','final-cdf-v5-refresh.stderr.txt','final-cdf-v5-runner.stdout.json','final-cdf-v5-runner.stderr.txt','fix_completed_cli_freeze.py']
seen={r['path'] for r in rows}
for name in extras:
 p=D/name
 if str(p) not in seen:rows.append({'path':str(p),**binding(p)});seen.add(str(p))
new=D/'own-helper-completed-final-selection.json';write(new,{**obj,'files':rows,'forward_correction':{'first_refresh':'ERROR, extension selected bytes differ','cause':'Author selected still-open builder stdout at zero bytes; after completion actual stdout570B. All other owner rows are exact. No product/helper defect; no scientific verdict.','old_input_and_full_trace_retained':True,'changed_inputs':changes,'original_selected_zero_byte_stdout_not_separately_staged':'not_established; old zero binding recorded only, actual completed stdout retained verbatim.'}})
base=json.loads((D/'final-cdf-v5-execution-cli.json').read_bytes());a=base['refresh_argv'][:]
idx=a.index('own-frozen-helper-inputs='+str(old));a[idx]='own-frozen-helper-inputs='+str(new)
idx=a.index('--output')+1;a[idx]=str(D/'selection-final-cdf-v5-completed.json')
cli=D/'final-cdf-v5-completed-execution-cli.json';a+=['--include-file',str(cli)]
base.update(refresh_argv=a,selection_output=a[idx]);base['validation_argv']=[base['validation_argv'][0],str(D/'publish_transport_v5.py'),'--selection',a[idx],'--repository','/workspace/e02-F-closeout-20261006'];base['explicit_selection_inputs']=[({**r,'path':str(new),**binding(new)} if r['id']=='own-frozen-helper-inputs' else r) for r in base['explicit_selection_inputs']];base['first_refresh_correction']={'original_CLI':str(D/'final-cdf-v5-execution-cli.json'),'original_full_ERROR':str(D/'final-cdf-v5-refresh.execution.json'),'completed_own_selection':str(new)};write(cli,base)
print(json.dumps({'completed_selection':{'path':str(new),**binding(new)},'completed_cli':{'path':str(cli),**binding(cli)},'changed_inputs':changes,'runtime_helper_source_changes':False},indent=2))
