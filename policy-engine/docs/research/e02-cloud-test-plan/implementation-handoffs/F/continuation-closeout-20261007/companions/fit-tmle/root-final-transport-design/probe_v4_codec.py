"""Tiny transport-metadata discriminators, never domain data or scientific tests."""
from pathlib import Path
import gzip,hashlib,json,subprocess,time
D=Path('/tmp/e02-F-continuation-20261007/fit-tmle/root-final-transport-design');P=D/'v4-codec-probe';P.mkdir();python='/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python';repo='/workspace/e02-F-closeout-20261006'
def bind(p):b=p.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def put(p,o):
 with p.open('xb') as f:f.write((json.dumps(o,indent=2)+'\n').encode())
def call(name,args,code):
 start=time.monotonic();cmd=[python,*args]
 with (P/(name+'.stdout')).open('xb') as out,(P/(name+'.stderr')).open('xb') as err:r=subprocess.run(cmd,stdout=out,stderr=err)
 put(P/(name+'.execution.json'),{'command':cmd,'cwd':str(Path.cwd()),'exit_code':r.returncode,'expected_exit':code,'wall_s':time.monotonic()-start,'scope':'Synthetic transport metadata only; no source/domain/backend test.'});assert r.returncode==code,(name,r.returncode)
seed={'logical_files':[],'existing_declared_git_references':[],'pending_extensions':[],'source_window':{'meaning':'Synthetic transport metadata only; real Git source identity is used to test parser binding.'},'selection_inputs':[],'policy':{'sanitation':'none'},'counts':{}}
put(P/'seed.json',seed);put(P/'prior.json',{'files':[],'aliases':[],'existing_git_files':[]});(P/'oldstage').mkdir();payload=b'Complete synthetic metadata output\t\nwith blank line\n\n';p=P/'fixture.stdout.gz'
with p.open('xb') as f:f.write(gzip.compress(payload,mtime=0))
row={'path':str(p),**bind(p),'encoding':'gzip','decoded_bytes':len(payload),'decoded_sha256':hashlib.sha256(payload).hexdigest()}
base=[str(D/'refresh_selection_v4.py'),'--seed-selection',str(P/'seed.json'),'--prior-manifest',str(P/'prior.json'),'--prior-staging-root',str(P/'oldstage'),'--repository',repo,'--final-source-sha','46cc03546f2572986962555ddf04d858163c1cf6']
results=[]
for key in ['files','items','selection']:
 ext=P/(key+'.json');put(ext,{key:[row],**({'files':1} if key=='selection' else {})});sel=P/(key+'-output.json');call('refresh-'+key,base+['--include-selection','probe='+str(ext),'--output',str(sel)],0);out=json.loads(sel.read_bytes());record=next(r for r in out['logical_files'] if r['original_path']==str(p));assert record['input_encoding']=='gzip' and record['input_binding']==bind(p) and record['encoding']=='gzip';dest=P/(key+'-stage');call('publish-'+key,[str(D/'publish_transport_v3.py'),'--selection',str(sel),'--repository',repo,'--materialize','--destination',str(dest)],0);target=dest/record['target_path'];assert target.read_bytes()==p.read_bytes() and gzip.decompress(target.read_bytes())==payload;results.append({'mode':key,'outcome':'PASS','stored_bytes_exact_reused':True,'same_complete_decoded_payload':True})
for name,changed,message in [('bad-stored',{**row,'sha256':'0'*64},'extension selected bytes differ'),('bad-decoded',{**row,'decoded_sha256':'0'*64},'extension gzip decoded bytes differ')]:
 ext=P/(name+'.json');put(ext,{'files':[changed]});call(name,base+['--include-selection','probe='+str(ext),'--output',str(P/(name+'-output.json'))],1);assert message in (P/(name+'.stderr')).read_text();results.append({'mode':name,'outcome':'FAIL','expected_control_detected':True,'marker_encoding_retained':'gzip'})
ext=P/'ambiguous.json';put(ext,{'files':[row],'selection':[row]});call('ambiguous',base+['--include-selection','probe='+str(ext),'--output',str(P/'ambiguous-output.json')],1);assert 'unambiguous complete file-row list' in (P/'ambiguous.stderr').read_text();results.append({'mode':'ambiguous','outcome':'FAIL','expected_control_detected':True})
put(P/'results.json',{'results':results,'science_tests_run':False,'source_Git_writes':False,'synthetic_scope':'Only codec/schema/complete-byte custody; no fake catalog seed or authority fixture.'});print(json.dumps({'results':results,'complete_output_dir':str(P)},indent=2))
