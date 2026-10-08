"""Read exact published peer artifacts, including decoded full deciding bytes."""
import gzip,hashlib,json,subprocess
from pathlib import Path
repo='/workspace/e02-F-fry-20261006';out=Path('/tmp/e02-F-continuation-20261007/foundry')
head='e04ddf884071b17ffb1d021c9a6b23f826d76774';prefix='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/tmle-persisted-consumers-20261007'
def git(*args):return subprocess.check_output(['git','-C',repo,*args])
def ref(sha,path):
 b=git('show',sha+':'+path);return {'git_sha':sha,'path':path,'blob':git('rev-parse',sha+':'+path).decode().strip(),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
remote=git('ls-remote','origin','refs/heads/codex/e02-F-tmle-20261006').decode()
assert remote.split()[0]==head
index=json.loads(git('show',head+':'+prefix+'/outputs.json'))
selection=json.loads((out/'fit-composed-review/transfer-selection.json').read_text())
by_origin={x['original_path']:x for x in index['files']}
verified=[]
for original in selection['files']:
 declared=by_origin[original['path']]
 raw=git('show',head+':'+declared['path'])
 assert len(raw)==declared['bytes'] and hashlib.sha256(raw).hexdigest()==declared['sha256']
 decoded=gzip.decompress(raw) if declared['encoding']=='gzip' else raw
 assert len(decoded)==original['bytes'] and hashlib.sha256(decoded).hexdigest()==original['sha256']
 assert decoded==Path(original['path']).read_bytes()
 verified.append(dict(ref(head,declared['path']),encoding=declared['encoding'],decoded_bytes=len(decoded),decoded_sha256=hashlib.sha256(decoded).hexdigest(),original_path=original['path']))
result={'outcome':'PASS','commands':[['git','ls-remote','origin','refs/heads/codex/e02-F-tmle-20261006'],['git','show',head+':'+prefix+'/outputs.json'],'git show exactHead:path per23 declared original refs; gzip-decode where declared; compare every complete raw byte to independent original'],'cwd':repo,'environment':'host stdlib read-only Git/gzip/sha256; no product import or backend claim','peer_head':head,'remote_readback':remote,'scientific_source':'0c81614f5aa737a4b26c6c74044955a842b26cf4','metadata_candidate':'8d94a937ca6e3f886ada9ad5c1f76dadb049da84','primary':ref(head,prefix+'.json'),'output_index':ref(head,prefix+'/outputs.json'),'verified_unique_independent_artifacts':verified,'count':len(verified),'G_acceptance':'not_assumed','copies_of_tracked_bodies':False}
(out/'peer-transport-witness.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'outcome':'PASS','peer_remote_head':head,'unique_independent_refs':len(verified),'full_decoded_native_stdout_bytes':next(x['decoded_bytes'] for x in verified if x['original_path'].endswith('native.stdout.txt'))}))
