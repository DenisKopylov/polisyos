from pathlib import Path
import gzip, json, hashlib

repo=Path('/workspace/e02-F-closeout-20261006')
s=Path('/tmp/e02-F-continuation-20261006/fit-final35-review')
d=repo/'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/continuation-transfer-20261006/reviews/semantic'
j=json.loads((s/'transfer-selection.json').read_text())
records=[]
for x in j['files']:
    p=Path(x['original_path']);b=p.read_bytes()
    assert len(b)==x['bytes'] and hashlib.sha256(b).hexdigest()==x['sha256']
    q=d/x['relative_path'];q=q.with_name(q.name+'.gz') if len(b)>800 else q
    q.parent.mkdir(parents=True,exist_ok=True)
    e=gzip.compress(b,mtime=0) if len(b)>800 else b;q.write_bytes(e)
    records.append({'path':str(q.relative_to(repo)),'bytes':len(e),'sha256':hashlib.sha256(e).hexdigest(),
                    'decoded_bytes':len(b),'decoded_sha256':hashlib.sha256(b).hexdigest(),
                    'encoding':'gzip' if len(b)>800 else 'raw','original_execution_path':str(p)})
p=s/'transfer-selection.json';q=d/'transfer-selection.json';q.write_bytes(p.read_bytes())
records.append({'path':str(q.relative_to(repo)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'encoding':'raw'})
error={'schema':'F-root-publisher-observer-error/1','check':'ERROR','phase':'First semantic review companion transfer before any file write',
       'cause':'ROOT assumed file entries contain path; actual independently supplied schema uses original_path/relative_path.',
       'observed_tool_response_stdout':"selectionkeys ['schema', 'reviewer', 'candidate_source_sha', 'verdict', 'files', 'unique_files', 'unique_bytes', 'reconstruction_only', 'existing_git_files', 'existing_evidence_scope', 'not_copied', 'limits']\n",
       'observed_tool_response_stderr':"Traceback (most recent call last):\n  File \"<stdin>\", line 6, in <module>\nKeyError: 'path'\n",
       'custody':'Complete returned tool text preserved; original stderr/stdout were not separately stored as byte files. Initial stdin publisher script not separately saved. No product/file mutation preceded the failure.',
       'correction':'Use the actual original_path/relative_path entry fields. Corrected exact script and all full unique companions preserved; no numerical rerun.'}
(d/'initial-publisher-observer-error.json').write_text(json.dumps(error,indent=2)+'\n')
for p in [d/'initial-publisher-observer-error.json',Path(__file__)]:
    q=p if p.parent==d else d/'corrected-publisher.py'
    if q!=p:q.write_bytes(p.read_bytes())
    b=q.read_bytes();records.append({'path':str(q.relative_to(repo)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'encoding':'raw'})
transport={'schema':'policyos.e02.output_transport.v1','complete_companions':records,
           'reconstruction_only_inputs':j['reconstruction_only'],
           'role':'Independent complete original35 semantic review; exact frozen code/Git refs, not institutional authority or native scientific reruns'}
(d/'transport.json').write_text(json.dumps(transport,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'unique_outputs_carried':len(records),'transport':str((d/'transport.json').relative_to(repo))}))
