"""Adapt the actual owner's row-list schema and reference reconstructible Git bodies."""
from pathlib import Path
import hashlib,json,re,subprocess
D=Path('/tmp/e02-F-continuation-20261007/fit-tmle/root-final-transport-design');R=Path('/tmp/e02-F-continuation-20261007');repo='/workspace/e02-F-closeout-20261006';source=R/'economics/recovery-review-20261007/transfer-selection-final.json';raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()=='65409d69d6fdfd29a101b4b66aee5ca2ab3fdd34e837ac02689248ffa2dd2716';owner=json.loads(raw);rows=owner['selection'];assert owner['files']==len(rows)==73

def binding(path):
 h=hashlib.sha256();n=0
 with path.open('rb') as f:
  while b:=f.read(1<<20):n+=len(b);h.update(b)
 return {'bytes':n,'sha256':h.hexdigest()}
def write(name,obj):
 p=D/name
 with p.open('xb') as f:f.write((json.dumps(obj,indent=2)+'\n').encode())
 return {'path':str(p),**binding(p)}
for row in rows:assert binding(Path(row['path']))=={k:row[k] for k in ['bytes','sha256']},row['path']
remote_names=['refs/remotes/origin/codex/e02-F-closeout-20261006','refs/remotes/origin/codex/e02-integration','refs/remotes/origin/codex/e02-F-economics-20261006']
remotes=[(n,subprocess.check_output(['git','-C',repo,'rev-parse',n],text=True).strip()) for n in remote_names]
def authority(ref):
 for remote,head in remotes:
  result=subprocess.run(['git','-C',repo,'merge-base','--is-ancestor',ref,head],capture_output=True)
  if result.returncode==0:return {'remote_ref':remote,'remote_head':head}
 raise ValueError('No currently observed published ref reaches requested immutable source: '+ref)
commands=json.loads((R/'economics/recovery-review-20261007/commands.json').read_bytes());published=[]
for cmd in commands:
 a=cmd['argv']
 if len(a)!=3 or a[:2]!=['git','show'] or ':' not in a[2] or cmd['exit_code']!=0:continue
 ref,path=a[2].split(':',1)
 if not re.fullmatch('[0-9a-f]{40}',ref):continue
 body=subprocess.check_output(['git','-C',repo,'show',a[2]]);actual={'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()};expected={k:cmd['stdout'][k] for k in ['bytes','sha256']};assert actual==expected
 published.append({'git_ref':ref,'path':path,**actual,**authority(ref),'original_path':cmd['stdout']['path'],'role':'Actual pure Git-show source/previous-receipt output exactly equals already-published immutable body; referenced without copying tracked source.'})
review=json.loads((R/'economics/recovery-review-20261007/source-review.json').read_bytes());excluded=[];exclude_paths=set()
for card in review['original_cards']:
 ref=card['source_sha'];path=card['path'];start,end=card['lines'];body=subprocess.check_output(['git','-C',repo,'show',ref+':'+path]);block=b''.join(body.splitlines(keepends=True)[start-1:end]);p=R/'economics/recovery-review-20261007'/(card['finding_id']+'-original-full-card.md');assert block==p.read_bytes();assert len(block)==card['block_bytes'] and hashlib.sha256(block).hexdigest()==card['block_sha256'];exclude_paths.add(str(p));excluded.append({'original_path':str(p),'finding_id':card['finding_id'],'original_binding':binding(p),'source_git_ref':ref,'source_path':path,'source_lines_inclusive':[start,end],'source_full_binding':{'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()},'reconstruction':'b"".join(git_show_bytes.splitlines(keepends=True)[start-1:end]); exact output equals original card bytes, verified now. Existing author recovery_review.py and this replayer retained.','disposition':'reconstructible tracked source excerpt, not copied; original selection+source-review full bindings retained.'});published.append({'git_ref':ref,'path':path,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),**authority(ref),'role':'Immutable original complete card source at actual published ancestor; two exact byte/line excerpts reconstructible, no duplicate source/card bodies.'})
adapted=[r for r in rows if r['path'] not in exclude_paths];adapted.append({'path':str(source),**binding(source)})
a=write('economic-quality-v3-adapter.json',{'schema':'policyos.e02.explicit_transport_selection.v1','files':adapted,'original_owner_selection':{'path':str(source),**binding(source)},'original73_rows_complete_byte_binding_verified':True,'explicit_reconstruction_only_rows':excluded,'pure_Git_body_equivalent_refs':len(published)-len(excluded),'new31_caption_instrument_outputs':'Both complete current-caption31/source-qualified and operating-caption locator instruments retained; no truncated substitution.','format_adapter_only':'Owner files field is count, owner selection field is row list; immutable V3 files-list contract adapted explicitly, no old file modified or scientific outcome changed.'})
g=write('economic-quality-pure-git-spec.json',{'files':published,'policy':'Actual complete pureGitshow source/old receipt equality + current observed origin ancestry. Full deciding native/scanner/error/review outputs stay transported unless exact body already published.'})
print(json.dumps({'adapter':a,'existing_git_spec':g,'owner_rows':len(rows),'reconstructible_source_card_rows':len(excluded),'actual_pure_git_equal_rows':len(published)-len(excluded),'scientific_or_Git_writes':False},indent=2))
