import subprocess,json,hashlib,gzip
from pathlib import Path
root=Path('/workspace/e02-F-closeout-20261006');prefix=Path('policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F'); h='d7a4458da62f02af02e433cab9edf8d13fca5424';d=root/prefix/'continuation-publication-readback-20261006';d.mkdir()
sha=lambda b:hashlib.sha256(b).hexdigest()
rows=[]
for name,cmd in [('remote',['git','ls-remote','origin','refs/heads/codex/e02-F-closeout-20261006']),('PR65',['gh','api','repos/DenisKopylov/polisyos/pulls/65']),('status',['git','status','--porcelain=v1','--branch']),('product-delta',['git','diff','--name-status','8236d9c368336a5ea20c1586f29aea7321db6536',h,'--','policy-engine/src','policy-engine/tests','policy-engine/tools','policy-engine/hatch_build.py','policy-engine/workers','policy-engine/pyproject.toml','policy-engine/uv.lock'])]:
 r=subprocess.run(cmd,cwd=root,capture_output=True); assert r.returncode==0
 outputs=[]
 for s,b in [('stdout',r.stdout),('stderr',r.stderr)]:
  path=d/(name+'.'+s);path.write_bytes(b);outputs.append({'path':str(path.relative_to(root)),'bytes':len(b),'sha256':sha(b)})
 rows.append({'name':name,'command':cmd,'cwd':str(root),'exit_code':r.returncode,'outputs':outputs})
assert (d/'remote.stdout').read_text().split()[0]==h
pr=json.loads((d/'PR65.stdout').read_bytes());assert pr['head']['sha']==h and pr['draft'] and pr['state']=='open' and pr['merged_at'] is None and pr['base']['ref']=='main'
assert not (d/'product-delta.stdout').read_bytes()
tpath=prefix/'continuation-closeout-20261006'/'transport.json'; raw=subprocess.check_output(['git','show',h+':'+str(tpath)],cwd=root);t=json.loads(raw);checked=[]
for r in t['files']:
 b=subprocess.check_output(['git','show',h+':'+r['path']],cwd=root);assert len(b)==r['bytes'] and sha(b)==r['sha256'];z=gzip.decompress(b) if r['encoding']=='gzip' else b;assert len(z)==r['decoded_bytes'] and sha(z)==r['decoded_sha256'];checked.append(r|{'head':h,'git_stored_check':'PASS','decoded_check':'PASS'})
primary=prefix/'continuation-closeout-20261006.json';b=subprocess.check_output(['git','show',h+':'+str(primary)],cwd=root);r=json.loads(b)
assert len(r['per_id'])==35 and r['frozen_packet_sha']=='f17b9a52784d9484ef65563dc6695240629bdfc6' and not r['formal_G_acceptance']
receipt={'schema':'policyos.e02.publication_readback.v1','unit':'F','check':'PASS','branch':'codex/e02-F-closeout-20261006','published_receipt_carrier_sha':h,'published_receipt_carrier_tree':subprocess.check_output(['git','rev-parse',h+'^{tree}'],cwd=root,text=True).strip(),'product_source_sha':r['candidate_source_sha'],'product_source_tree':r['candidate_tree_sha'],'frozen_full35_packet_sha':r['frozen_packet_sha'],'primary_receipt':{'head':h,'path':str(primary),'bytes':len(b),'sha256':sha(b)},'full_output_transport':{'head':h,'path':str(tpath),'bytes':len(raw),'sha256':sha(raw)},'complete_git_output_readback':checked,'complete_publication_commands':rows,'Git_remote_exact_SHA':'PASS','PR_head_exact_SHA':'PASS','PR_state':'open draft unmerged; base main; no main or G integration publication','PR_body_sha256':sha(pr['body'].encode()),'source_code_delta_from_frozen_product':[],'formal_G_acceptance':False,'preservation':'No deletion/Trashclear; active worker symlink remains untracked intentionally. This forward document binds the already published final receipt; own carrier resolved from Git.'}
(d/'readback_final.py').write_bytes(Path(__file__).read_bytes()); (root/prefix/'continuation-publication-readback-20261006.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'check':'PASS','carrier':h,'full_files':len(checked),'per_ID':len(r['per_id']),'PR':pr['html_url'],'product_unchanged':True}))
