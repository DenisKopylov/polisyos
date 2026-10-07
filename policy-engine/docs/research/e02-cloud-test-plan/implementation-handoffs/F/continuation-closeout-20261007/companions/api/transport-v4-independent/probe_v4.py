"""Independent small exact-code transport intake, alias and encoding controls."""
from pathlib import Path
import copy,gzip,hashlib,json,os,subprocess,time
OUT=Path(__file__).resolve().parent
DESIGN=Path('/tmp/e02-F-continuation-20261007/fit-tmle/root-final-transport-design')
PYTHON='/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'
REPO='/workspace/e02-F-api-20261006';SOURCE='519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82'
EXPECTED={'refresh_selection_v4.py':'3df0d51dffda5c4ad5f6232c759d830efd23bd5c5ce3b43cf6a56050fb8d63a7','refresh_selection_v3.py':'4df1398167268650297f6a27acffe472759a3bd4829e741273bc10256a94d05a','publish_transport_v3.py':'c55ab809c690634feb93b4b819d58f3b64518b9d15220742261805180bec41f4','transport_text_policy.py':'2d332a9099f212564d14ce3a0b5f3b8515eb34148611ebfc41bb1af76ef2101a'}
def digest(body):return hashlib.sha256(body).hexdigest()
def file_ref(path):
    path=Path(path);body=path.read_bytes();return {'path':str(path),'bytes':len(body),'sha256':digest(body)}
def write(path,obj):path.write_text(json.dumps(obj,indent=2)+'\n')
def guard():
    for name,sha in EXPECTED.items():assert file_ref(DESIGN/name)['sha256']==sha,name
RECORDS=[]
def capture(label,argv):
    env=os.environ.copy();env.pop('PYTHONPATH',None);env['PYTHONDONTWRITEBYTECODE']='1';start=time.monotonic();p=subprocess.run(argv,cwd=OUT,env=env,capture_output=True)
    row={'label':label,'argv':argv,'cwd':str(OUT),'environment':{'PYTHONPATH':'absent','PYTHONDONTWRITEBYTECODE':'1'},'exit_code':p.returncode,'seconds':time.monotonic()-start}
    for name,body in [('stdout',p.stdout),('stderr',p.stderr)]:
        path=OUT/(label+'.'+name+'.txt');path.write_bytes(body);row[name]=file_ref(path)
    RECORDS.append(row);write(OUT/'executions.json',RECORDS);return row
seed=OUT/'seed.json';prior=OUT/'prior.json';stage=OUT/'prior-stage';stage.mkdir(exist_ok=True)
write(seed,{'logical_files':[],'pending_extensions':[],'existing_declared_git_references':[],'source_window':{'scope':'Small standalone transport fixture, not scientific evidence'},'selection_inputs':[],'policy':{'sanitation':'none'},'draft':False})
write(prior,{'files':[],'aliases':[],'existing_git_files':[]})
raw=b'alpha  \r\nbeta\n\n';a=OUT/'a.gz';b=OUT/'b.gz';a.write_bytes(gzip.compress(raw,mtime=0));b.write_bytes(gzip.compress(raw,mtime=7));assert a.read_bytes()!=b.read_bytes() and gzip.decompress(a.read_bytes())==gzip.decompress(b.read_bytes())==raw
base=file_ref(a)|{'encoding':'gzip','decoded_bytes':len(raw),'decoded_sha256':digest(raw)}
def refresh(label,obj):
    selection=OUT/(label+'.input.json');write(selection,obj);output=OUT/(label+'.selected.json')
    argv=[PYTHON,str(DESIGN/'refresh_selection_v4.py'),'--seed-selection',str(seed),'--prior-manifest',str(prior),'--prior-staging-root',str(stage),'--repository',REPO,'--final-source-sha',SOURCE,'--output',str(output),'--include-selection',label+'='+str(selection)]
    return capture(label+'-refresh',argv),output
results=[];guard()
for schema in ['files','items','selection']:
    record,path=refresh('valid-'+schema,{schema:[base]});assert record['exit_code']==0
    selected=json.loads(path.read_text());row=next(r for r in selected['logical_files'] if r['original_path']==str(a));assert row['input_encoding']=='gzip' and row['input_binding']=={'bytes':base['bytes'],'sha256':base['sha256']} and row['bytes']==len(raw) and row['sha256']==digest(raw)
    dest=OUT/('materialized-'+schema);pub=capture('valid-'+schema+'-publish',[PYTHON,str(DESIGN/'publish_transport_v3.py'),'--selection',str(path),'--repository',REPO,'--materialize','--destination',str(dest)]);assert pub['exit_code']==0
    copied=dest/row['target_path'];assert copied.read_bytes()==a.read_bytes() and gzip.decompress(copied.read_bytes())==raw
    results.append({'case':'valid-'+schema,'outcome':'PASS','copied_precompressed_bytes_identical':True,'full_decoded_bytes_identical':True,'input_encoding_and_binding_preserved':True})
for label,mutator in [('bad-stored-sha',lambda r:r.update(sha256='0'*64)),('bad-stored-size',lambda r:r.update(bytes=r['bytes']+1)),('bad-decoded-sha',lambda r:r.update(decoded_sha256='0'*64)),('bad-decoded-size',lambda r:r.update(decoded_bytes=r['decoded_bytes']+1)),('missing-decoded-identity',lambda r:r.pop('decoded_sha256')),('unknown-encoding',lambda r:r.update(encoding='brotli'))]:
    row=copy.deepcopy(base);mutator(row);record,path=refresh(label,{'files':[row]});assert record['exit_code']!=0 and not path.exists();results.append({'case':label,'outcome':'PASS','actual_intake_exit':record['exit_code'],'bad_input_refused':True})
record,path=refresh('ambiguous',{'files':[base],'items':[base]});assert record['exit_code']!=0 and not path.exists();results.append({'case':'ambiguous','outcome':'PASS','bad_input_refused':True})
# Recomputed decoded-alias scope must not be confused with original compressed identity.
second=file_ref(b)|{'encoding':'gzip','decoded_bytes':len(raw),'decoded_sha256':digest(raw)}
record,path=refresh('different-stored-same-decoded',{'files':[base,second]});assert record['exit_code']==0
selected=json.loads(path.read_text());row_a=next(r for r in selected['logical_files'] if r['original_path']==str(a));row_b=next(r for r in selected['logical_files'] if r['original_path']==str(b))
assert row_a['disposition']=='transport' and row_b['disposition']=='alias'
dest=OUT/'materialized-different-container';record=capture('different-container-publish',[PYTHON,str(DESIGN/'publish_transport_v3.py'),'--selection',str(path),'--repository',REPO,'--materialize','--destination',str(dest)]);assert record['exit_code']==0
copied=(dest/row_a['target_path']).read_bytes();results.append({'case':'different-stored-same-decoded','outcome':'OBSERVED','canonical_original_stored_bytes_preserved':copied==a.read_bytes(),'other_original_stored_bytes_recoverable_from_alias':copied==b.read_bytes(),'decoded_identity_equal':gzip.decompress(copied)==raw,'alias_input_binding_preserved_in_selection':row_b['input_binding']=={'bytes':second['bytes'],'sha256':second['sha256']},'scope_question':'Deduplication binds decoded bytes; original distinct gzip-container bytes are not both transported.'})
# An explicitly declared unsupported compression dialect must not be admitted as identity.
codec=copy.deepcopy(base);codec.pop('encoding');codec['codec']='gzip lossless';codec['decoded_sha256']='0'*64
record,path=refresh('codec-only-wrong-decoded',{'files':[codec]})
results.append({'case':'codec-only-wrong-decoded','outcome':'FAIL' if record['exit_code']==0 else 'PASS','actual_intake_exit':record['exit_code'],'wrong_decoded_identity_accepted':record['exit_code']==0,'selected_row':next((r for r in json.loads(path.read_text())['logical_files'] if r['original_path']==str(a)),None) if path.exists() else None})
# The publisher must reject a false alias even with retained alias markers.
altered=copy.deepcopy(selected);row=next(r for r in altered['logical_files'] if r['original_path']==str(b));row['canonical_original_path']=str(DESIGN/'refresh_selection_v4.py');bad=OUT/'bad-alias.selected.json';write(bad,altered)
record=capture('bad-alias-validate',[PYTHON,str(DESIGN/'publish_transport_v3.py'),'--selection',str(bad),'--repository',REPO]);assert record['exit_code']!=0;results.append({'case':'bad-alias','outcome':'PASS','actual_publisher_exit':record['exit_code'],'bad_alias_refused':True})
# Exact Git ref validation refuses unattested/future locators, rather than minting them.
spec=OUT/'future-git-spec.json';write(spec,[{'git_ref':'f'*40,'path':'AGENTS.md','bytes':0,'sha256':digest(b''),'remote_ref':'refs/remotes/origin/codex/e02-integration'}]);future=OUT/'future-git.selected.json'
argv=[PYTHON,str(DESIGN/'refresh_selection_v4.py'),'--seed-selection',str(seed),'--prior-manifest',str(prior),'--prior-staging-root',str(stage),'--repository',REPO,'--final-source-sha',SOURCE,'--output',str(future),'--existing-git-spec',str(spec)]
record=capture('future-git-refusal',argv);assert record['exit_code']!=0 and not future.exists();results.append({'case':'future-git','outcome':'PASS','unknown_ref_refused':True})
guard();write(OUT/'results.json',{'source_guard':EXPECTED,'science_tests_run':False,'Git_or_product_writes':False,'input_payload_bytes':len(raw),'results':results,'actual_control_counts':dict(__import__('collections').Counter(r['outcome'] for r in results))});print(json.dumps({'cases':len(results),'outcomes':dict(__import__('collections').Counter(r['outcome'] for r in results)),'results':results},indent=2))
