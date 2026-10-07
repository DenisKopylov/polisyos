"""Bind already-published complete installed outputs by Git locators, no body copies."""
from pathlib import Path
import hashlib,json,subprocess
D=Path('/tmp/e02-F-continuation-20261007/fit-tmle/root-final-transport-design');repo='/workspace/e02-F-closeout-20261006';ref='de197363d4ba8a86b0e8c2fa0ff31c2858643d1c';remote='refs/remotes/origin/codex/e02-F-fry-20261006';prefix='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/installed-default-resource-final-20261007'
head=subprocess.check_output(['git','-C',repo,'rev-parse',remote],text=True).strip();assert head==ref
raw={path:subprocess.check_output(['git','-C',repo,'show',ref+':'+path]) for path in [prefix+'.json',prefix+'/outputs.json']};primary=json.loads(raw[prefix+'.json']);assert primary['tested_source_sha']=='519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82';assert primary['tested_source_tree_sha']=='750d28da94f372848fe6b2db5f88db95b94cb57d';assert len(raw[prefix+'.json'])==47204 and hashlib.sha256(raw[prefix+'.json']).hexdigest()=='d4cef17e72100250f5162b3642654882f1864c576e895ca8903b7b4f24e66f05'
rows=[]
for path,b in raw.items():rows.append({'git_ref':ref,'path':path,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'remote_ref':remote,'remote_head':head,'extension_id':'new-final-installed-composition','role':'Actual published external-source519 installed primary/full complete output manifest; no body duplication or scientific rerun.'})
seen=set()
for item in json.loads(raw[prefix+'/outputs.json'])['files']:
 path=item['committed_path'];key=(path,item['stored_sha256'])
 if key in seen:continue
 seen.add(key);rows.append({'git_ref':ref,'path':path,'bytes':item['stored_bytes'],'sha256':item['stored_sha256'],'remote_ref':remote,'remote_head':head,'extension_id':'new-final-installed-composition','role':'Already committed complete deciding output/replayer, exact stored bytes; lossless decoded identity declared in referenced outputs.json. No copied body.'})
p=D/'published-installed-de197-spec.json'
with p.open('xb') as s:s.write((json.dumps({'files':rows,'coverage':'135 logical declared output rows,98 distinct stored paths plus manifest and primary; all stored/decompressed bodies independently readback verified in published-output-byte-audit.json. Earlier131/199/53 results retain own exact sources.','scientific_scope':'519 wheel/sdist91 and six negative failures as source-bound own receipt; no repeated TMLE numerical tests or causal authority/shared-study admission positive.'},indent=2)+'\n').encode())
b=p.read_bytes();print(json.dumps({'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'existing_git_refs':len(rows),'origin_head':head},indent=2))
