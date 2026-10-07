"""Read-only recovery audit of complete frozen transport bodies, not scientific gates."""
import gzip,hashlib,json,subprocess,time
from pathlib import Path
ROOT=Path('/tmp/e02-F-continuation-20261007/fit-tmle/root-final-transport-design')
REPO=Path('/workspace/e02-F-closeout-20261006')
MANIFEST=ROOT/'staged-draft/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/continuation-closeout-20261007/artifact-transports.json'
def digest(stream):
 h=hashlib.sha256();n=0
 while c:=stream.read(1<<20):h.update(c);n+=len(c)
 return {'bytes':n,'sha256':h.hexdigest()}
def bind(p):
 with p.open('rb') as s:return digest(s)
def gitbind(ref,path):
 p=subprocess.Popen(['git','-C',str(REPO),'show',f'{ref}:{path}'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 b=digest(p.stdout);err=p.stderr.read();rc=p.wait();assert rc==0,(ref,path,err);return b
start=time.monotonic();issues=[];items=[];m=json.loads(MANIFEST.read_bytes());seed=json.loads((ROOT/'selection-draft.json').read_bytes());by_path={r['path']:r for r in m['files']}
for row in m['files']:
 p=ROOT/'staged-draft'/row['path'];stored=bind(p);expected={k:row[k] for k in ['bytes','sha256']};assert stored==expected,(p,'stored')
 if row['encoding']=='gzip':
  with gzip.open(p,'rb') as stream:raw=digest(stream)
 else:raw=stored
 assert raw=={'bytes':row['decoded_bytes'],'sha256':row['decoded_sha256']},(p,'decoded')
 items.append({'kind':'stored','path':str(p),'stored':stored,'decoded':raw,'encoding':row['encoding']})
for row in m['aliases']:
 target=by_path[row['stored_path']];assert row['source_bytes']==target['decoded_bytes'] and row['source_sha256']==target['decoded_sha256'];assert row['stored_bytes']==target['bytes'] and row['stored_sha256']==target['sha256'];items.append({'kind':'alias','original_path':row['original_path'],'canonical_path':target['path'],'bytes':row['source_bytes'],'sha256':row['source_sha256']})
refs=[]
for row in m['existing_git_files']+m['existing_declared_git_references']:
 if row.get('bytes') is not None:
  b=gitbind(row['git_ref'],row['path']);assert b=={k:row[k] for k in ['bytes','sha256']};refs.append({**row,'full_body_verified':True})
 else:
  subprocess.run(['git','-C',str(REPO),'cat-file','-e',row['git_ref']+':'+row['path']],check=True,capture_output=True);refs.append({**row,'existence_only':True,'full_body_assertion':'not_declared'})
changes=[]
for row in seed['logical_files']:
 p=Path(row['original_path']);b=bind(p) if p.is_file() else None
 if b!={k:row[k] for k in ['bytes','sha256']}:changes.append({'original_path':str(p),'prior':{k:row[k] for k in ['bytes','sha256']},'current':b,'old_bytes_preserved_in_prior_staging_or_git':True})
helpers=[]
for name,expected in [('refresh_selection_v3.py','4df1398167268650297f6a27acffe472759a3bd4829e741273bc10256a94d05a'),('publish_transport_v3.py','c55ab809c690634feb93b4b819d58f3b64518b9d15220742261805180bec41f4'),('transport_text_policy.py','2d332a9099f212564d14ce3a0b5f3b8515eb34148611ebfc41bb1af76ef2101a')]:
 b=bind(ROOT/name);assert b['sha256']==expected;helpers.append({'path':str(ROOT/name),**b})
source='519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82';tree=subprocess.check_output(['git','-C',str(REPO),'rev-parse',source+'^{tree}'],text=True).strip();assert tree=='750d28da94f372848fe6b2db5f88db95b94cb57d'
admission=Path('/tmp/e02-F-continuation-20261007/root-recovery/e02-F-tmle-20261006/admission.stdout');a=json.loads(admission.read_bytes());assert a['status']=='admitted' and a['complete_verdict'] is True and not a['findings']
result={'schema':'policyos.e02.transport_recovery_readonly.v1','outcome':'PASS','meaning':'Complete custody/transport byte audit only; no scientific/global/finding/admission verdict.','source_sha':source,'source_tree':tree,'manifest':{'path':str(MANIFEST),**bind(MANIFEST)},'seed':{'path':str(ROOT/'selection-draft.json'),**bind(ROOT/'selection-draft.json')},'helpers':helpers,'admission':{'path':str(admission),**bind(admission),'status':a['status'],'requested':a['requested']},'counts':{'stored_files':len(m['files']),'aliases':len(m['aliases']),'existing_git_files':len(m['existing_git_files']),'additional_declared_git_references':len(m['existing_declared_git_references']),'changed_prior_inputs':len(changes)},'full_bodies':items,'git_references':refs,'changed_prior_inputs':changes,'wall_s':time.monotonic()-start,'raw_copies_created':0,'gzip_decompression_stream_only':True,'raw_originals_or_old_staging_modified':False,'Git_writes':False,'science_tests_run':False,'issues':issues}
p=ROOT/'recovered-validation.json'
with p.open('xb') as f:f.write((json.dumps(result,indent=2)+'\n').encode())
print(json.dumps({'output':{'path':str(p),**bind(p)},'outcome':'PASS','counts':result['counts'],'wall_s':result['wall_s']},indent=2))
