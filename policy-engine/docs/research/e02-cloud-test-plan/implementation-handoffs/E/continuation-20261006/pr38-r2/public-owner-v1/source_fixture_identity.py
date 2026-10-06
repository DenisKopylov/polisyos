from pathlib import Path
import hashlib,json,os,subprocess
O=Path(__file__).parent;R=Path('/workspace/e02-E-continuation-20261006');F=O/'fixture-current';ref='c0f146702219cd3280c3b7d06e9d2bc4c7b95dd6'
paths=['policy-engine/src','policy-engine/tools/devx/architecture','policy-engine/tools/lib','policy-engine/architecture/public_surface/contract.toml','policy-engine/architecture/generated_artifacts.toml','policy-engine/pyproject.toml','policy-engine/architecture/production_quality/method_catalog_dependency_digest_domains.toml','policy-engine/ruff.toml','policy-engine/architecture/tooling/ruff/generated.toml']
rows=[];differences=[]
for raw in subprocess.check_output(['git','ls-tree','-r','-z',ref,'--',*paths],cwd=R).split(b'\0'):
 if not raw:continue
 metadata,path=raw.decode().split('\t');mode,kind,expected=metadata.split();p=F/path
 data=os.readlink(p).encode() if p.is_symlink() else p.read_bytes();actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
 if expected!=actual:differences.append(path)
 rows.append({'path':path,'git_blob':expected,'sha256':hashlib.sha256(data).hexdigest()})
assert not differences,differences
py_expected={r['path'] for r in rows if r['path'].endswith('.py')};py_actual={str(p.relative_to(F)) for root in ['policy-engine/src','policy-engine/tools/devx/architecture','policy-engine/tools/lib'] for p in (F/root).rglob('*.py') if '__pycache__' not in p.parts};assert py_actual==py_expected,(py_actual-py_expected,py_expected-py_actual)
result={'candidate_sha':ref,'candidate_tree':subprocess.check_output(['git','rev-parse',ref+'^{tree}'],cwd=R,text=True).strip(),'tracked_source_subtree':subprocess.check_output(['git','rev-parse',ref+':policy-engine/src'],cwd=R,text=True).strip(),'full_input_paths':paths,'all_selected_git_blobs_match':True,'selected_file_count':len(rows),'python_file_count':len(py_expected),'extra_or_missing_python_paths':[],'source_identity_index_sha256':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),'full_index_scratch_file':str(O/'source-fixture-full-index.json'),'fixture_is_git_checkout':False}
(O/'source-fixture-full-index.json').write_text(json.dumps(rows,indent=2)+'\n');(O/'source-fixture-identity.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
