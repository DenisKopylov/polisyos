"""Actual published gzip Git body distinguishes stored from decoded matching."""
from pathlib import Path
import gzip,hashlib,json,os,subprocess,time
OUT=Path(__file__).resolve().parent/'git-binding-controls';DESIGN=Path('/tmp/e02-F-continuation-20261007/fit-tmle/root-final-transport-design')
PYTHON='/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python';REPO='/workspace/e02-F-api-20261006'
GIT_SHA='c4ddc4bcbddc2a7526f541d51196b176e4311362';REMOTE='refs/remotes/origin/codex/e02-F-fry-20261006'
GIT_PATH='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/installed-default-resource-final-20261007/app-python-version.stdout.txt.gz'
EXPECTED={'refresh_selection_v5.py':'1ed83f18c764e2dd74234580d8cb88d9c24d55118e1d4b29a08b24280686048d','publish_transport_v5.py':'39c07c78cc45087d3e4552b9d6de6a62788f43bae31fa89c4da1e1733ecaefa2'}
def digest(b):return hashlib.sha256(b).hexdigest()
def ref(p):b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':digest(b)}
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def guard():
 for name,sha in EXPECTED.items():assert ref(DESIGN/name)['sha256']==sha
records=[]
def run(label,argv):
 env=os.environ.copy();env.pop('PYTHONPATH',None);env['PYTHONDONTWRITEBYTECODE']='1';t=time.monotonic();p=subprocess.run(argv,cwd=OUT,env=env,capture_output=True)
 record={'label':label,'argv':argv,'cwd':str(OUT),'environment':{'PYTHONPATH':'absent','PYTHONDONTWRITEBYTECODE':'1'},'exit_code':p.returncode,'seconds':time.monotonic()-t}
 for field,body in [('stdout',p.stdout),('stderr',p.stderr)]:path=OUT/(label+'.'+field+'.txt');path.write_bytes(body);record[field]=ref(path)
 records.append(record);write(OUT/'executions.json',records);return record
seed=OUT/'seed.json';prior=OUT/'prior.json';stage=OUT/'prior-stage';stage.mkdir()
write(seed,{'logical_files':[],'pending_extensions':[],'existing_declared_git_references':[],'source_window':{'scope':'Tiny actual Git custody check, no science'},'selection_inputs':[],'policy':{'sanitation':'none'},'draft':False});write(prior,{'files':[],'aliases':[],'existing_git_files':[]})
guard()
raw_record=run('read-actual-published-gzip',['git','-C',REPO,'show',GIT_SHA+':'+GIT_PATH]);assert raw_record['exit_code']==0
body=Path(raw_record['stdout']['path']).read_bytes();decoded=gzip.decompress(body)
a=OUT/'actual-git.gz';b=OUT/'same-decoded-other-container.gz';a.write_bytes(body);b.write_bytes(gzip.compress(decoded,mtime=123));assert b.read_bytes()!=body and gzip.decompress(b.read_bytes())==decoded
spec=OUT/'existing-git-spec.json';write(spec,[{'git_ref':GIT_SHA,'path':GIT_PATH,'bytes':len(body),'sha256':digest(body),'remote_ref':REMOTE,'remote_head':GIT_SHA}])
rows=[ref(a)|{'encoding':'gzip','decoded_bytes':len(decoded),'decoded_sha256':digest(decoded)},ref(b)|{'encoding':'gzip-lossless','decoded_bytes':len(decoded),'decoded_sha256':digest(decoded)}]
selection=OUT/'input.json';write(selection,{'files':rows});output=OUT/'selected.json'
record=run('refresh-actual-git',[PYTHON,str(DESIGN/'refresh_selection_v5.py'),'--seed-selection',str(seed),'--prior-manifest',str(prior),'--prior-staging-root',str(stage),'--repository',REPO,'--final-source-sha','519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82','--output',str(output),'--include-selection','tinygit='+str(selection),'--existing-git-spec',str(spec)]);assert record['exit_code']==0
selected=json.loads(output.read_text());same=next(r for r in selected['logical_files'] if r['original_path']==str(a));different=next(r for r in selected['logical_files'] if r['original_path']==str(b));assert same['disposition']=='existing_git' and different['disposition']=='transport'
assert same['input_binding']=={'bytes':len(body),'sha256':digest(body)} and same['bytes']==len(decoded) and same['sha256']==digest(decoded)
record=run('publish-actual-git',[PYTHON,str(DESIGN/'publish_transport_v5.py'),'--selection',str(output),'--repository',REPO,'--materialize','--destination',str(OUT/'materialized')]);assert record['exit_code']==0
assert (OUT/'materialized'/different['target_path']).read_bytes()==b.read_bytes()
guard();result={'outcome':'PASS','cases':2,'actual_Git_head':GIT_SHA,'observed_remote_ref':REMOTE,'actual_Git_path':GIT_PATH,'actual_stored_binding':ref(a),'actual_decoded_binding':{'bytes':len(decoded),'sha256':digest(decoded)},'exact_stored_body_matches_existing_Git':True,'same_decoded_different_stored_body_not_false_existing_Git':True,'all_helper_source_hashes':EXPECTED,'science_tests_run':False};write(OUT/'results.json',result);print(json.dumps(result,indent=2))
