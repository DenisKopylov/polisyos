"""Append Git-byte binding to existing immutable author source/outputs."""
from pathlib import Path
import subprocess,hashlib,json,ast
OUT=Path(__file__).parent;ROOT=Path('/workspace/e02-E-continuation-20261006');SHA='cfd79255aab85544082fcf24f93db894202fbfa2';BASE='5e3e3727685132f270a3a07b9f63dd962a88cd96'
manifest=json.loads((OUT/'postimage-manifest.json').read_text());origins=json.loads((OUT/'native-origins-combined.json').read_text())
get=lambda args:subprocess.check_output(['git','-C',str(ROOT),*args])
parent=get(['rev-parse',SHA+'^']).decode().strip();tree=get(['rev-parse',SHA+'^{tree}']).decode().strip()
paths=get(['diff-tree','--no-commit-id','--name-only','-r',SHA]).decode().splitlines();assert sorted(paths)==sorted(row['path'] for row in manifest['paths'])
postimages=[]
for row in manifest['paths']:
 raw=get(['show',SHA+':'+row['path']]);assert hashlib.sha256(raw).hexdigest()==row['after_sha256']
 postimages.append({'path':row['path'],'git_blob':get(['rev-parse',SHA+':'+row['path']]).decode().strip(),'sha256':row['after_sha256'],'bytes':len(raw)})
# One Git cat-file process proves every actual loaded product module maps to committed bytes.
refs=[SHA+':'+row['path'] for row in origins['module_origins']]
raw=get(['cat-file','--batch']) if False else subprocess.check_output(['git','-C',str(ROOT),'cat-file','--batch'],input=('\n'.join(refs)+'\n').encode())
pos=0;joins=[];mismatches=[]
for row in origins['module_origins']:
 end=raw.index(b'\n',pos);oid,typ,size=raw[pos:end].decode().split();assert typ=='blob';start=end+1;payload=raw[start:start+int(size)];assert raw[start+int(size):start+int(size)+1]==b'\n';pos=start+int(size)+1
 digest=hashlib.sha256(payload).hexdigest()
 if digest!=row['sha256']:mismatches.append({'module':row['module'],'path':row['path'],'executed_sha256':row['sha256'],'committed_sha256':digest})
 joins.append({'module':row['module'],'path':row['path'],'git_blob':oid,'sha256':digest,'role':row['role']})
assert pos==len(raw) and not mismatches
lines='module\tpath\tgit_blob\tsha256\torigin_role\n'+''.join('\t'.join(row[k] for k in ('module','path','git_blob','sha256','role'))+'\n' for row in joins)
(OUT/'source-checkpoint-loaded-joins.tsv').write_text(lines)
for name in ('propagate_welfare','propagate_uncertainty'):
 path='policy-engine/src/polisyos/scientist/nodes/builtins/simulate/'+name+'.py'
 body=lambda text:[ast.dump(node,include_attributes=False) for node in ast.parse(text).body if not isinstance(node,(ast.Import,ast.ImportFrom))]
 assert body(get(['show',BASE+':'+path]))==body(get(['show',SHA+':'+path]))
cov='policy-engine/src/polisyos/foundry/uncertainty/covariance.py';assert get(['show',BASE+':'+cov])==get(['show',SHA+':'+cov])
result={'schema':'policyos.e02.owned_facade_source_checkpoint_binding.v1','state':'Exact_git_byte_binding_of_reviewed_scratch_source_and_actual_native_inputs','base':BASE,'base_tree':'3b63e778d5b6d17b2e9edc3b4bf91af079b32eb0','implementation_sha':SHA,'implementation_tree':tree,'implementation_parent':parent,'actual_native_framing_sha':json.loads((OUT/'native-combined-receipt.json').read_text())['framing_HEAD'],'actual_native_execution':'Existing17 author native tests on immutable scratch source plus5e-equivalent root inputs; this binding is static Git-byte reconciliation, not a new numerical execution on cfd.','original_author_packet_index_sha256':hashlib.sha256((OUT/'index.json').read_bytes()).hexdigest(),'original_author_receipt_sha256':hashlib.sha256((OUT/'author-receipt.json').read_bytes()).hexdigest(),'original_source_patch_sha256':manifest['patch_sha256'],'exact_source_commit_diff_path_count':len(paths),'exact_source_commit_postimages':postimages,'actual_loaded_product_modules_joined_to_commit':len(joins),'loaded_module_mismatches':mismatches,'loaded_join_file':'source-checkpoint-loaded-joins.tsv','loaded_join_sha256':hashlib.sha256(lines.encode()).hexdigest(),'both_Node_non_import_AST_unchanged':True,'canonical_covariance_bytes_unchanged':True,'review_scope':'Author binding only; DDM independent bounded code verdict and root/G source acceptance separate. No main publication or finding ledger change.'}
(OUT/'source-checkpoint-binding.json').write_text(json.dumps(result,indent=2)+'\n')
files=['bind_source_checkpoint.py','source-checkpoint-binding.json','source-checkpoint-loaded-joins.tsv']
index={'schema':'policyos.e02.appendonly_source_binding_companion_index.v1','original_index_sha256':result['original_author_packet_index_sha256'],'implementation_sha':SHA,'files':[{'path':name,'bytes':len((OUT/name).read_bytes()),'sha256':hashlib.sha256((OUT/name).read_bytes()).hexdigest()} for name in files]}
(OUT/'source-binding-index.json').write_text(json.dumps(index,indent=2)+'\n')
print(json.dumps({'implementation_sha':SHA,'implementation_tree':tree,'parent':parent,'source_paths':len(paths),'executed_modules_git_joined':len(joins),'mismatches':mismatches,'binding_sha256':hashlib.sha256((OUT/'source-checkpoint-binding.json').read_bytes()).hexdigest(),'binding_index_sha256':hashlib.sha256((OUT/'source-binding-index.json').read_bytes()).hexdigest()},indent=2))
