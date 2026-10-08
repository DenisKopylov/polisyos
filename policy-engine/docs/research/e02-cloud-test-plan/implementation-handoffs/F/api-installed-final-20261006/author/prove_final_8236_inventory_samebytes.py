from pathlib import Path
import hashlib,json,subprocess
root=Path('/workspace/e02-F-api-20261006');scratch=Path('/tmp/e02-F-continuation-20261006/api');sha='8236d9c368336a5ea20c1586f29aea7321db6536'
git=lambda *args:subprocess.check_output(['git',*args],cwd=root)
assert git('rev-parse','HEAD').decode().strip()==sha
assert git('rev-parse','HEAD^{tree}').decode().strip()=='724a77c88d4e6699ffead58a5e3e3990fb88640a'
assert not git('status','--porcelain','--untracked-files=no')
paths=['policy-engine/architecture/public_surface/inventory.json','policy-engine/docs/reference/public-surface.md'];same=[]
for relative in paths:
 old=git('show',sha+':'+relative);current=(root/relative).read_bytes();assert old==current
 same.append({'path':relative,'bytes':len(current),'sha256':hashlib.sha256(current).hexdigest(),'byte_equal_to_frozen_git':True})
entries={}
for item in git('ls-tree','-rz','--full-tree',sha).split(b'\0'):
 if item:
  meta,path=item.split(b'\t',1);mode,kind,oid=meta.decode().split();entries[path.decode()]=(kind,oid)
data=json.loads((root/paths[0]).read_text());rows=[r for p in data['packages'] for r in p['entrypoints']]
reads={};operations=0
for row in rows:
 for inp in row['export_resolution']['inputs']:
  operations+=1;relative='policy-engine/'+inp['path']
  if inp['operation']=='read_bytes':
   raw=git('show',sha+':'+relative);assert len(raw)==inp['bytes'] and hashlib.sha256(raw).hexdigest()==inp['sha256'],relative
   reads[relative]=inp['sha256']
  elif inp['operation']=='is_file':
   assert inp['result']==(relative in entries and entries[relative][0]=='blob'),(relative,inp)
  else:raise AssertionError(inp)
assert len(rows)==38 and all(r['export_count'] is None and r['known_export_count']==0 and r['export_resolution']['complete'] is False for r in rows)
proof={'source_sha':sha,'source_tree':'724a77c88d4e6699ffead58a5e3e3990fb88640a','branch':'codex/e02-F-api-20261006','generation_record':str(scratch/'final-8236-inventory-generation.json'),'generated_outputs':same,'byte_delta_paths':[],'input_denominator':{'entrypoints':len(rows),'explicit_file_operations':operations,'unique_read_bytes_paths':len(reads),'all_read_bytes_and_is_file_operations_reconciled_with_exact_git':True,'source_of_declared_inputs':paths[0]+'@'+sha},'canonical_completeness_gate':{'outcome':'FAIL','incomplete_entrypoints':38,'unknown_total':True,'known_zero_means':'No runtime export names proven by conservative finite parser; not runtime namespace zero.'},'historical_generation_preserved':'composed-inventory-generation.json remains unchanged; fresh deciding record separately written.','source_guard':'attached clean same exact SHA/tree before and after generation; no implementation commit needed because zero byte delta.'}
p=scratch/'final-8236-inventory-samebytes-proof.json';assert not p.exists();p.write_text(json.dumps(proof,indent=2)+'\n');raw=p.read_bytes();print(json.dumps({'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'unique_reads':len(reads),'explicit_operations':operations,'source_sha':sha,'generated_delta':[]}))
