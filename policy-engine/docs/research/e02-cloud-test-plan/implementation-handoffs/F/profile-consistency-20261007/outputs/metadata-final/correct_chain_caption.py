from pathlib import Path
import json,subprocess,hashlib
ROOT=Path('/workspace/e02-F-closeout-20261006');SOURCE='852cc3707bfc7dee132ec07a9ed5adcb5911fdf2';P='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/continuation-transfer-20261007/';OUT=Path('/dev/shm/e02-F-profile-consistency-20261007/ledger');D=json.JSONDecoder()
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def ws(s,i):
 while i<len(s) and s[i].isspace():i+=1
 return i
def field(s,key):
 assert s[0]=='{';i=ws(s,1)
 while s[i]!='}':
  k,a=D.raw_decode(s,i);i=ws(s,a);assert s[i]==':';start=ws(s,i+1);_,last=D.raw_decode(s,start)
  if k==key:return start,last
  i=ws(s,last)
  if s[i]==',':i=ws(s,i+1)
 raise KeyError(key)
def item(s,key,fid):
 start,last=field(s,key);assert s[start]=='[';i=ws(s,start+1)
 while s[i]!=']':
  value,end=D.raw_decode(s,i)
  if value['finding_id']==fid:return i,end
  i=ws(s,end)
  if s[i]==',':i=ws(s,i+1)
 raise KeyError(fid)
def replace_value(s,key,value):
 a,b=field(s,key);return s[:a]+json.dumps(value,ensure_ascii=False)+s[b:]
assert git('symbolic-ref','--short','HEAD').decode().strip()=='codex/e02-F-closeout-20261006';assert git('rev-parse','HEAD').decode().strip()==SOURCE
names=[P+'per-ID/B214.json',P+'index.json',P+'full-audit.json'];before={p:(ROOT/p).read_bytes() for p in names};pid=json.loads(before[names[0]]); old=pid['profile_consistency_followup']['actual_chains'][0]
assert 'schema-valid retagged DAG/ADMG -> registered MethodJob' in old
new='Genuine build_mgraph with synthetic DATA confidence0.9 for cutoff -> schema-valid retagged ADMG dict/JSON -> registered MethodJob/direct/supplied/current-selected ReconcileCausalGraphNode -> no reconciled artifact; original MGraph remains readable. A valid retagged DAG is exercised by the actual ComposeSCMFragments sibling; direct/Node DAG cases use malformed reserved-profile claims. Clean same-node-name/edge ADMG -> actual job/Node -> CAS -> fresh reader remains supported.'
for name in names[:2]:
 s=before[name].decode();needle=json.dumps(old,ensure_ascii=False);assert s.count(needle)==1;(ROOT/name).write_text(s.replace(needle,json.dumps(new,ensure_ascii=False),1))
data=(ROOT/names[0]).read_bytes(); values={'bytes':len(data),'sha256':sha(data)}
for name,key in [(names[1],'per_ID_complete_records'),(names[2],'rows')]:
 s=(ROOT/name).read_text();a,b=item(s,key,'B214');record=s[a:b]
 for k,v in values.items():record=replace_value(record,k,v)
 (ROOT/name).write_text(s[:a]+record+s[b:])
idx=json.loads((ROOT/names[1]).read_text());audit=json.loads((ROOT/names[2]).read_text());updated=json.loads(data);prior=json.loads(before[names[0]])
prior['profile_consistency_followup']['actual_chains'][0]=new;assert prior==updated
assert audit['rows']==idx['per_ID_complete_records']; assert idx['summary']==json.loads(git('show',SOURCE+':'+names[1]))['summary']
for row in idx['rows']:
 p=P+'per-ID/'+row['finding_id']+'.json';raw=(ROOT/p).read_bytes();record=next(v for v in idx['per_ID_complete_records'] if v['finding_id']==row['finding_id']);assert len(raw)==record['bytes'] and sha(raw)==record['sha256'];obj=json.loads(raw)
 for k,v in row.items():assert obj[k]==v,(row['finding_id'],k)
 if row['finding_id']!='B214':assert raw==git('show',SOURCE+':'+p)
assert len(idx['rows'])==35;assert sum(len(row['original_card_refs']) for row in idx['rows'])==36;assert git('rev-parse','HEAD').decode().strip()==SOURCE
meta=json.loads((OUT/'ledger-author-validation.json').read_text());meta['B214_new_record']=next(v for v in idx['per_ID_complete_records'] if v['finding_id']=='B214');meta['non_author_caption_correction']={'requested_by':'Independent graph reviewer','changed_field':'B214.profile_consistency_followup.actual_chains[0] and matching index row','old':old,'new':new,'dependent_record_hashes_updated':True,'other34_byte_identical':True,'source_runtime_inputs_changed':False,'runtime_rerun_required':False};(OUT/'ledger-author-validation.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'B214':meta['B214_new_record'],'correction':meta['non_author_caption_correction'],'author_validation_bytes':(OUT/'ledger-author-validation.json').stat().st_size,'author_validation_sha256':sha((OUT/'ledger-author-validation.json').read_bytes()),'summary':idx['summary'],'role':'AUTHOR validation only'},ensure_ascii=False,indent=2))
