"""Exact immutable root assembly bindings; no builder, checkout or runtime mutation."""
import gzip,hashlib,json,pathlib,subprocess
ROOT=pathlib.Path('/workspace/e02-F-api-20261006');OUT=pathlib.Path(__file__).resolve().parent;SHA='519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82';TREE='750d28da94f372848fe6b2db5f88db95b94cb57d';BASE='8236d9c368336a5ea20c1586f29aea7321db6536';RESOURCE='08983d96395fdde81ffa9e88d0150fd12c13fe2e';COMPANION='81f482e04bd8a2c85f894d425847c6e8657b6ea6';GRAPH='647f5d35362c2a5d7ad32283b804a5b03ea56e83'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def h(b):return hashlib.sha256(b).hexdigest()
def tree(sha,prefix):
 result={}
 for row in git('ls-tree','-r','--full-tree',sha,'--',prefix).decode().splitlines():
  head,path=row.split('\t');mode,kind,blob=head.split();assert kind=='blob';result[path]={'mode':mode,'blob':blob}
 return result
assert git('rev-parse',SHA+'^{tree}').decode().strip()==TREE
inspection=json.loads(pathlib.Path('/tmp/e02-F-continuation-20261007/api/resource-review-089/inspection.json').read_text());resourcepaths=[x['path'] for x in inspection['source_begin']]+[x['path'] for x in inspection['original_YAML_refs']];bindings=[]
for p in resourcepaths:
 expected=COMPANION if p in ['policy-engine/docs/reference/data-forge/catalog-default-resources.md','policy-engine/release-fragments/unreleased/2026-10-07-catalog-default-resources.toml','policy-engine/src/polisyos/data_forge/domains/README.md'] else RESOURCE
 b=git('show',SHA+':'+p);assert b==git('show',expected+':'+p);bindings.append({'path':p,'reviewed_sha':expected,'root_sha':SHA,'bytes':len(b),'sha256':h(b),'root_blob':git('rev-parse',SHA+':'+p).decode().strip(),'byte_equal':True})
graphpaths=['policy-engine/src/polisyos/foundry/methods/catalog/causal/graph_reconciliation.py','policy-engine/src/polisyos/scientist/nodes/builtins/causal/reconcile_causal_graph.py']
for p in graphpaths:
 b=git('show',SHA+':'+p);assert b==git('show',GRAPH+':'+p);bindings.append({'path':p,'reviewed_sha':GRAPH,'root_sha':SHA,'bytes':len(b),'sha256':h(b),'root_blob':git('rev-parse',SHA+':'+p).decode().strip(),'byte_equal':True})
# Complete declared runtime/tool trees, not a hand-picked provider list. Equal blob+mode means exact immutable Git bytes.
old={};new={}
for prefix in ['policy-engine/src','policy-engine/tools','policy-engine/workers']:
 old.update(tree(BASE,prefix));new.update(tree(SHA,prefix))
for p in ['policy-engine/pyproject.toml','policy-engine/uv.lock','policy-engine/hatch.toml']:
 old.update(tree(BASE,p));new.update(tree(SHA,p))
rows=[]
for p in sorted(set(old)|set(new)):
 before=old.get(p);after=new.get(p);same=before==after;rows.append({'path':p,'baseline':before,'final':after,'exact_blob_mode_equal':same})
changed=[r['path'] for r in rows if not r['exact_blob_mode_equal']];expectedchanges=[r['path'] for r in bindings if r['path'].startswith('policy-engine/src/') or r['path']=='policy-engine/hatch.toml'];assert sorted(changed)==sorted(expectedchanges),(changed,expectedchanges)
scientific_prefixes=['policy-engine/src/polisyos/foundry/methods/catalog/causal/','policy-engine/src/polisyos/ir/analytics/','policy-engine/src/polisyos/core/causal_engine/','policy-engine/src/polisyos/scientist/nodes/builtins/causal/','policy-engine/workers/'];science=[r for r in rows if any(r['path'].startswith(p) for p in scientific_prefixes)];assert all(r['exact_blob_mode_equal'] or r['path'] in graphpaths for r in science)
locks=[r for r in rows if pathlib.Path(r['path']).name in ['uv.lock','pyproject.toml','.python-version']];assert all(r['exact_blob_mode_equal'] for r in locks)
body=json.dumps({'root_sha':SHA,'baseline_sha':BASE,'profile':'Complete tracked src/tools/workers plus appmanifest/locks/Hatch; exact immutableGitblob+mode mapping, no trackedsourcebodyduplicate.','rows':rows},indent=2).encode()+b'\n';encoded=gzip.compress(body,mtime=0);path=OUT/'full-runtime-tool-worker-blob-comparison.json.gz';path.write_bytes(encoded)
result={'root_sha':SHA,'root_tree':TREE,'baseline_runtime_sha':BASE,'resource_runtime_sha':RESOURCE,'resource_companion_sha':COMPANION,'graph_runtime_sha':GRAPH,'resource_and_graph_bindings':bindings,'complete_denominator':len(rows),'unchanged_exact_blob_mode_rows':sum(r['exact_blob_mode_equal'] for r in rows),'changed_paths':changed,'scientific_prefix_denominator':len(science),'scientific_changed_paths':[r['path'] for r in science if not r['exact_blob_mode_equal']],'lock_manifest_python_version_denominator':len(locks),'all_locks_and_app_manifest_equal':True,'full_comparison':{'path':str(path),'stored_bytes':len(encoded),'stored_sha256':h(encoded),'decoded_bytes':len(body),'decoded_sha256':h(body)},'publication_boundary':'Root519immutableproducttree; laterreceipt-onlyrootheads do notretargetthissource. Competing3dde unmerged.','prior_b5_NO_GO_immutable':'c22786dfce8308bb7d48a177ccb1b109843262b5 remains130P32F/each.','scientific_replay':'UNRUN thisstep; unchangedproviders reused exact8236sourceprofile witnesses, notwholecurrentHEADPASS.'};(OUT/'source-bindings.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['resource_and_graph_bindings']},indent=2))
