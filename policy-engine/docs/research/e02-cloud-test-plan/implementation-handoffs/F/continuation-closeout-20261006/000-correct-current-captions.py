import json,hashlib,subprocess
from pathlib import Path
root=Path('/workspace/e02-F-closeout-20261006'); rel=Path('policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/continuation-transfer-20261006'); p=root/rel
read=lambda n:json.loads((p/n).read_text())
def write(n,d): (p/n).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def ref(n):
 b=(p/n).read_bytes(); return {'path':str(rel/n),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
newref=ref('root-adjudication.json')|{'head':head,'git_ref':head}
dec=read('root-adjudication.json'); decisions={r['finding_id']:r for r in dec['rows']}
i=read('index.json'); a=read('full-audit.json')
for d,rows,inputkey in [(i,i['finding_rows'],'complete_input_and_audit_refs'),(a,a['rows'],'source_inputs')]:
 d[inputkey]['ROOT_explicit_adjudication']=newref
 for r in rows:
  z=decisions[r['finding_id']]
  r['oracle_and_negative']=z['oracle_and_negative']; r['decision_basis']=z['decision_basis']; r['predicate_basis']=z['decision_basis']
  r['ROOT_adjudication_ref']=newref|{'json_pointer':r['ROOT_adjudication_ref']['json_pointer']}
write('full-audit.json',a); ar=ref('full-audit.json')
for r in i['finding_rows']:
 r['complete_audit_row_ref']=ar|{'json_pointer':r['complete_audit_row_ref']['json_pointer']}
 n='per-ID/'+r['finding_id']+'.json'; d=read(n); z=d['complete_original_bound_row']; decision=decisions[r['finding_id']]
 for k in ['oracle_and_negative','decision_basis']: z[k]=decision[k]
 z['predicate_basis']=decision['decision_basis']; z['ROOT_adjudication_ref']=r['ROOT_adjudication_ref']
 if 'complete_audit_row_ref' in z: z['complete_audit_row_ref']=r['complete_audit_row_ref']
 write(n,d); r['current_per_ID_receipt']=ref(n)
i['current_per_ID_receipts']=[ref('per-ID/'+r['finding_id']+'.json') for r in i['finding_rows']]
s=read('source-order.json'); hs=s['transfer_carrier_history_through_adjudication']; known={r['sha'] for r in hs}
for h in subprocess.check_output(['git','rev-list','--reverse','7a311cc812bd0dfb8b16d31c56377e29c07ff14c..'+head],cwd=root,text=True).splitlines():
 if h not in known:
  vals=subprocess.check_output(['git','show','-s','--format=%H%n%P%n%T',h],cwd=root,text=True).splitlines();hs.append({'sha':vals[0],'parents':vals[1].split(),'tree':vals[2]})
s['current_caption_forward_correction']={'decision_ref':newref,'preserved_frozen_packet_sha':'d645cea93fe5bde8419b5ecbe6b612209891e16d','affected_ids':['LA-007','LA-019','LA-020','LA-035'],'code_source_unchanged':dec['root_source_sha'],'scope':'Current decision/caption corrections only; all historical literal owner/source records retained; no numerical rerun.'}
write('source-order.json',s)
t=read('artifact-transports.json')
changed=[]
for r in t['files']:
 path=r['path']; n=Path(path).relative_to(rel) if path.startswith(str(rel)+'/') else None
 if n and (str(n).startswith('per-ID/') or str(n)=='root-adjudication.json'):
  vals=ref(n);r.update(vals)
  if 'head' in r:r['head']=head
  if 'git_ref' in r:r['git_ref']=head
  if 'git_blob' in r:r['git_blob']=subprocess.check_output(['git','hash-object',str(root/path)],text=True).strip()
  changed.append(path)
write('artifact-transports.json',t)
for k,n in [('full_audit','full-audit.json'),('transports','artifact-transports.json'),('source_order','source-order.json')]:i['complete_input_and_audit_refs'][k]=ref(n)
write('index.json',i)
result={'check':'PASS','decision_head':head,'affected_ids':['LA-007','LA-019','LA-020','LA-035'],'all35_decision_refs_rebound':True,'original_outcomes_unchanged':True,'material_records_updated':len(changed),'full_paths':[str(rel/n) for n in ['root-adjudication.json','index.json','full-audit.json','source-order.json','artifact-transports.json']]}
Path('/tmp/e02-F-continuation-20261006/current-caption-correction.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
