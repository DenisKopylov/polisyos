"""Additive final observed-origin specs; preserve old specs and verify published bytes."""
from pathlib import Path
import gzip,hashlib,json,subprocess
D=Path('/tmp/e02-F-continuation-20261007/fit-tmle/root-final-transport-design')
R='/workspace/e02-F-closeout-20261006'
CDF='cdf61b4500e355a27db14260e80ce673ddf8869e'
FRY='c4ddc4bcbddc2a7526f541d51196b176e4311362'
PREFIX='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/installed-default-resource-recovery-20261007'
def data_binding(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def file_binding(p):return data_binding(p.read_bytes())
def git(*a):return subprocess.check_output(['git','-C',R,*a])
def head(remote):return git('rev-parse',remote).decode().strip()
def reachable(ref,remote):
 h=head(remote)
 subprocess.run(['git','-C',R,'merge-base','--is-ancestor',ref,h],check=True,capture_output=True)
 return h
def write(name,o):
 p=D/name
 with p.open('xb') as f:f.write((json.dumps(o,indent=2)+'\n').encode())
 return {'path':str(p),**file_binding(p)}
audit=[];outputs=[]
assert head('refs/remotes/origin/codex/e02-F-closeout-20261006')==CDF
assert head('refs/remotes/origin/codex/e02-F-fry-20261006')==FRY
for old,new in [('published-installed-de197-spec.json','published-installed-de197-final-cdf-spec.json'),('economic-quality-pure-git-spec.json','economic-quality-pure-git-final-cdf-spec.json')]:
 source=D/old;obj=json.loads(source.read_bytes());rows=obj['files'];newrows=[]
 for row in rows:
  b=git('show',row['git_ref']+':'+row['path']);assert data_binding(b)=={k:row[k] for k in ('bytes','sha256')}
  tip=reachable(row['git_ref'],row['remote_ref']);newrows.append({**row,'remote_head':tip})
  audit.append({'git_ref':row['git_ref'],'path':row['path'],**data_binding(b),'observed_remote_head':tip,'stored_readback':'PASS','scope':'Exact existing published bytes and observed reachability; no scientific replay.'})
 outputs.append(write(new,{**obj,'files':newrows,'previous_spec':{'path':str(source),**file_binding(source)},'refresh_scope':'Origin tip/readback changed only; immutable body references and historical scientific sources are identical.'}))
raw={p:git('show',FRY+':'+p) for p in (PREFIX+'.json',PREFIX+'/outputs.json')}
assert data_binding(raw[PREFIX+'.json'])=={'bytes':20686,'sha256':'90dc84a5d1cc424cd9768937693fe8e32267f2a4a1b1b8a78151ce03c35bff88'}
manifest=json.loads(raw[PREFIX+'/outputs.json']);assert manifest['tested_source_sha']=='519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82'
rows=[];seen={};remote='refs/remotes/origin/codex/e02-F-fry-20261006'
def refrow(path,b):
 return {'git_ref':FRY,'path':path,**data_binding(b),'remote_ref':remote,'remote_head':FRY,'extension_id':'new-final-installed-composition','role':'Already published installed recovery fresh-PID complete output/receipt. No duplicate body; source519 scope separate from old same-process primary and actual TMLE53.'}
for p,b in raw.items():rows.append(refrow(p,b))
for item in manifest['files']:
 p=item['committed_path'];expected={'bytes':item['stored_bytes'],'sha256':item['stored_sha256']}
 if p in seen:
  assert seen[p]==expected;continue
 seen[p]=expected;b=git('show',FRY+':'+p);assert data_binding(b)==expected
 decoded=gzip.decompress(b) if item['encoding']=='gzip' else b
 assert data_binding(decoded)=={'bytes':item['decoded_bytes'],'sha256':item['decoded_sha256']}
 rows.append(refrow(p,b));audit.append({'git_ref':FRY,'path':p,**expected,'encoding':item['encoding'],'decoded_binding':data_binding(decoded),'observed_remote_head':FRY,'stored_and_decoded_readback':'PASS','scope':'Complete actual deciding output byte custody; no method/scientific replay.'})
outputs.append(write('published-installed-c4dd-final-cdf-spec.json',{'files':rows,'actual_manifest_rows':len(manifest['files']),'distinct_stored_paths':len(seen),'scope':'Published current source519 recovery/fresh child receipt plus complete byte-bound stored/decoded outputs; default resource91 and original TMLE53 retain their existing distinct source scopes.'}))
outputs.append(write('final-published-byte-readback.json',{'outcome':'PASS','actual_final_document_candidate':CDF,'numerical_installed_candidate':'519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82','stored_readback_rows':len(audit),'files':audit,'raw_copies':0,'Git_writes':False,'science_tests_run':False}))
print(json.dumps({'prepared_specs_and_audit':outputs,'c4dd_logical_output_rows':len(manifest['files']),'c4dd_distinct_stored_outputs':len(seen),'root_source_writes':False,'Git_writes':False},indent=2))
