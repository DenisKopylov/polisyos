"""Export one exact immutable Git source and neutral complete selected test carriers."""
import gzip,hashlib,json,os,subprocess,tarfile,time,tomllib
from pathlib import Path
scratch=Path('/tmp/e02-F-continuation-20261007/foundry/installed-continuation-final')
git_root=Path('/workspace/e02-F-fry-20261006')
sha='b5a421d83336e0b50ad9a6747f3f7d041d4c1b5a';tree='055871c409ce72e6a29619b235698aa45a6844d4'
def git(*args):return subprocess.check_output(['git','-C',str(git_root),*args])
assert git('rev-parse',sha+'^{tree}').decode().strip()==tree
archive=scratch/'source-git.tar.gz';assert not archive.exists()
start=time.monotonic()
argv=['git','-C',str(git_root),'archive','--format=tar',sha]
with archive.open('wb') as stream:
 with gzip.GzipFile(fileobj=stream,mode='wb',mtime=0,filename='') as zipper:
  process=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  while chunk:=process.stdout.read(1024*1024):zipper.write(chunk)
  error=process.stderr.read();code=process.wait()
(scratch/'git-archive.stderr.txt').write_bytes(error);assert code==0
source=scratch/'source';source.mkdir(exist_ok=False)
with tarfile.open(archive) as tar:tar.extractall(source,filter='data')
# Prove every extracted Git file from its original blob, without duplicating source bodies in receipts.
entries=[]
for item in git('ls-tree','-rz','--full-tree',sha).split(b'\0'):
 if item:
  head,path=item.split(b'\t',1);mode,kind,oid=head.decode().split();assert kind=='blob' and mode in ('100644','100755');entries.append((path.decode(),oid))
stream=subprocess.Popen(['git','-C',str(git_root),'cat-file','--batch'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
# Interleave requests/readbacks so no full-source memory or pipe deadlock.
aggregate=hashlib.sha256();total=0
for path,oid in entries:
 stream.stdin.write((oid+'\n').encode());stream.stdin.flush();parts=stream.stdout.readline().decode().split();assert parts[:2]==[oid,'blob'];raw=stream.stdout.read(int(parts[2]));assert stream.stdout.read(1)==b'\n';actual=(source/path).read_bytes();assert actual==raw,path
 h=hashlib.sha256(raw).hexdigest();aggregate.update((path+'\0'+h+'\0'+str(len(raw))+'\n').encode());total+=len(raw)
stream.stdin.close();assert stream.wait()==0
proof={'source_sha':sha,'source_tree':tree,'command':argv,'cwd':str(git_root),'exit_code':code,'archive':{'path':str(archive),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()},'source_root':str(source),'complete_Git_blob_files_verified':len(entries),'complete_bytes_verified':total,'ordered_path_hash_size_aggregate':aggregate.hexdigest(),'root_uncommitted_docs':'excluded by exact Gitarchive; not source inputs','wall_seconds':time.monotonic()-start,'outcome':'PASS','new_quota':False}
(scratch/'source-export-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
selectors=['tests/unit/scientist/methods/causal/test_graph_intake_current_content.py','tests/unit/scientist/methods/causal/test_reconcile_causal_graph_node.py','tests/unit/scientist/nodes/builtins/causal/test_reconcile_causal_graph.py','tests/unit/foundry/methods/catalog/causal/test_graph_reconciliation.py','tests/unit/foundry/methods/catalog/causal/test_installed_graph_contract_reconciliation.py','tests/unit/scientist/governance/test_tmle_persisted_evidence_consumers.py','tests/unit/foundry/plugins/test_historical_income_baseline.py','tests/unit/foundry/agent_sim/test_signed_gini_producer_route.py']
fixture_paths=set(selectors)
for selected in selectors:
 for folder in Path(selected).parents:
  if str(folder)=='.':continue
  for name in ('conftest.py','__init__.py'):
   relative=str(folder/name)
   if (source/'policy-engine'/relative).is_file():fixture_paths.add(relative)
for p in (source/'policy-engine/tests/_helpers').rglob('*.py'):fixture_paths.add(str(p.relative_to(source/'policy-engine')))
if (source/'policy-engine/tests/quarantine.toml').exists():fixture_paths.add('tests/quarantine.toml')
refs=[]
for path in sorted(fixture_paths):
 original=source/'policy-engine'/path;raw=original.read_bytes();blob=git('rev-parse',sha+':policy-engine/'+path).decode().strip()
 for kind in ('wheel','sdist'):
  target=scratch/(kind+'-consumer')/path;target.parent.mkdir(parents=True,exist_ok=True);assert not target.exists();target.write_bytes(raw)
 refs.append({'git_sha':sha,'path':'policy-engine/'+path,'blob':blob,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'role':'selected_test' if path in selectors else 'actual_ancestor_or_helper_fixture'})
for kind in ('wheel','sdist'):assert not (scratch/(kind+'-consumer')/'src').exists()
(scratch/'carrier-manifest.json').write_text(json.dumps({'source_sha':sha,'source_tree':tree,'selectors':selectors,'expected_cases_per_profile':162,'case_breakdown':{'Graph':79,'API':2,'FIT':53,'ECO':28},'files':refs,'source_fallback':'neutral sibling src absent; no symlink to source; exact fixture bodies only'},indent=2)+'\n')
hatch=tomllib.loads((source/'policy-engine/hatch.toml').read_text());resources=hatch['build']['targets']['wheel']['force-include'];assert len(resources)==7
assets={Path(target).name:{'bytes':(source/'policy-engine'/path).stat().st_size,'sha256':hashlib.sha256((source/'policy-engine'/path).read_bytes()).hexdigest()} for path,target in resources.items() if '/_dowhy_profile/' in target}
(scratch/'profile-expected.json').write_text(json.dumps({'source_sha':sha,'assets':assets,'forced_resource_count':len(resources),'worker_assets':len(assets)},indent=2)+'\n')
config={'source_sha':sha,'source_tree':tree,'git_root':str(git_root),'source_root':str(source),'scratch':str(scratch),'app_python':'/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python','worker_python':'/workspace/e02-F-dowhy-20261006/policy-engine/workers/dowhy-014/.venv/bin/python','dependency_site':'/workspace/e02-F-closeout-20261006/policy-engine/.venv/lib/python3.14/site-packages','selectors':selectors,'expected_cases_per_profile':162,'source_export_proof':str(scratch/'source-export-proof.json'),'carrier_manifest':str(scratch/'carrier-manifest.json'),'source_owned_test_filters':'Actual unmodified source conftest CPU/no-preallocate/logger setup retained. New launcher must not attribute omitted historical warnings to currentzero.','no_product_PYTHONPATH':True,'new_quota':False}
(scratch/'setup-config.json').write_text(json.dumps(config,indent=2)+'\n')
print(json.dumps({'outcome':'PASS','source_sha':sha,'archive_bytes':archive.stat().st_size,'source_files':len(entries),'carrier_files':len(refs),'selectors':len(selectors),'expected_cases_per_profile':162}))
