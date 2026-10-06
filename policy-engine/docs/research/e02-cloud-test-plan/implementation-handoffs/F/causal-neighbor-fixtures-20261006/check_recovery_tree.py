"""Actual full-tree reconciliation of the accepted recovery checkpoint."""
import hashlib,json,pathlib,subprocess
root=pathlib.Path('/workspace/e02-F-graph-20261006');out=pathlib.Path(__file__).parent
checkpoint='b52c64c36504e17da9ae3f70f5551bfd1e01a5d5';target='7185572917f7a3db5e93385a176cb611b35aff42'
command=['git','diff','--exit-code',checkpoint,target,'--'];r=subprocess.run(command,cwd=root,capture_output=True)
refs=[]
for name,b in [('stdout',r.stdout),('stderr',r.stderr)]:
 p=out/('recovery-tree-check.'+name+'.txt');p.write_bytes(b);refs.append({'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
a=subprocess.check_output(['git','rev-parse',checkpoint+'^{tree}'],cwd=root).decode().strip();b=subprocess.check_output(['git','rev-parse',target+'^{tree}'],cwd=root).decode().strip()
d={'command':command,'checkpoint_sha':checkpoint,'target_sha':target,'checkpoint_tree':a,'target_tree':b,'exit_code':r.returncode,'check':'PASS' if r.returncode==0 and a==b else 'FAIL','output_refs':refs,'complete_tree_denominator':True};p=out/'recovery-tree-check.json';p.write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d));assert d['check']=='PASS'
