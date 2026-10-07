"""Read-only independent complete b5 archive/site/carrier/native custody verification."""
from pathlib import Path
import collections,gzip,hashlib,io,json,os,subprocess,tarfile,time,tomllib,xml.etree.ElementTree as ET,zipfile
out=Path(__file__).resolve().parent
packet=Path('/tmp/e02-F-continuation-20261007/foundry/installed-continuation-final')
gitroot=Path('/workspace/e02-F-api-20261006')
sha='b5a421d83336e0b50ad9a6747f3f7d041d4c1b5a';tree='055871c409ce72e6a29619b235698aa45a6844d4'
def git(*args):return subprocess.check_output(['git',*args],cwd=gitroot)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def record(path):
 raw=path.read_bytes();return {'path':str(path),'bytes':len(raw),'sha256':digest(raw)}
def read(name):return json.loads((packet/name).read_text())
start=time.monotonic();config=read('installed-config.json');source=read('source-export-proof.json');carrier=read('carrier-manifest.json');author=read('archive-installed-source-bindings.json')
assert config['source_sha']==sha and config['source_tree']==tree
assert git('rev-parse',sha+'^{tree}').decode().strip()==tree
entries=[]
for item in git('ls-tree','-rz','--full-tree',sha).split(b'\0'):
 if not item:continue
 metadata,name=item.split(b'\t',1);mode,kind,oid=metadata.decode().split()
 assert kind=='blob' and mode in ('100644','100755'),(name,mode,kind)
 entries.append((name.decode(),oid))
process=subprocess.Popen(['git','cat-file','--batch'],cwd=gitroot,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
# Queries are fed by a separate writer to avoid pipe fill deadlocks while complete bytes stream.
import threading
def feed():
 for _,oid in entries:process.stdin.write((oid+'\n').encode())
 process.stdin.close()
thread=threading.Thread(target=feed);thread.start()
source_rows=[];aggregate=hashlib.sha256();total=0;expected={};by_source={}
for name,oid in entries:
 header=process.stdout.readline().decode().strip().split();assert header[:2]==[oid,'blob']
 raw=process.stdout.read(int(header[2]));assert process.stdout.read(1)==b'\n'
 exported=Path(config['source_root'])/name
 assert exported.is_file() and exported.read_bytes()==raw,(name,'Git/export difference')
 row={'source':name,'git_blob':oid,'bytes':len(raw),'sha256':digest(raw)};source_rows.append(row);by_source[name]=row
 aggregate.update((name+'\0'+row['sha256']+'\0'+str(len(raw))+'\n').encode());total+=len(raw)
 if name.startswith(('policy-engine/src/polisyos/','policy-engine/tools/')):
  dest=name.removeprefix('policy-engine/src/').removeprefix('policy-engine/')
  assert dest not in expected;expected[dest]=dict(row,destination=dest,role='tracked_product')
assert not process.stdout.read();thread.join();assert process.wait()==0
assert len(entries)==source['complete_Git_blob_files_verified']==17843
assert total==source['complete_bytes_verified']==550021601
assert aggregate.hexdigest()==source['ordered_path_hash_size_aggregate']
hatch=tomllib.loads(git('show',sha+':policy-engine/hatch.toml').decode());resources=hatch['build']['targets']['wheel']['force-include']
assert len(resources)==7
product_count=len(expected)
for src,dest in resources.items():
 assert dest not in expected
 expected[dest]=dict(by_source['policy-engine/'+src],destination=dest,role='forced_resource')
assert product_count==3452 and len(expected)==3459
assert len(author['source_bindings'])==len(expected)
assert {r['destination']:r for r in author['source_bindings']}==expected
source_archive=Path(source['archive']['path']);assert record(source_archive)==source['archive']
with tarfile.open(source_archive) as archive:
 members=[m for m in archive.getmembers() if m.isfile()];assert {m.name for m in members}==set(by_source)
 assert not any(m.issym() or m.islnk() for m in archive.getmembers())
 for m in members:
  raw=archive.extractfile(m).read();row=by_source[m.name];assert len(raw)==row['bytes'] and digest(raw)==row['sha256'],m.name
archive_records={}
seed='policy-engine/data/dataset_catalog/seed_variable_alignments.yaml'
with tarfile.open(config['archives']['sdist']) as archive:
 prefix=archive.getnames()[0].split('/')[0]+'/'
 names=set(archive.getnames())
 for row in expected.values():
  member=prefix+row['source'].removeprefix('policy-engine/');raw=archive.extractfile(member).read()
  assert len(raw)==row['bytes'] and digest(raw)==row['sha256'],('sdist',member)
 assert prefix+seed.removeprefix('policy-engine/') not in names
for kind in ('wheel','rebuilt_wheel'):
 path=Path(config['archives'][kind])
 with zipfile.ZipFile(path) as archive:
  names={n for n in archive.namelist() if n.startswith(('polisyos/','tools/')) and not n.endswith('/')}
  assert names==set(expected),(kind,names-set(expected),set(expected)-names)
  for name,row in expected.items():
   raw=archive.read(name);assert len(raw)==row['bytes'] and digest(raw)==row['sha256'],(kind,name)
  assert not any(n.endswith('/seed_variable_alignments.yaml') for n in archive.namelist())
for kind,path in config['archives'].items():
 archive_records[kind]=record(Path(path));assert archive_records[kind]==author['archives'][kind]
assert archive_records['wheel']['sha256']==archive_records['rebuilt_wheel']['sha256']
profiles={};failure_sets=[];input_refs=[]
for kind,site_name in config['sites'].items():
 site=Path(site_name)
 for dest,row in expected.items():
  raw=(site/dest).read_bytes();assert len(raw)==row['bytes'] and digest(raw)==row['sha256'],(kind,dest)
 actual_python={p.relative_to(site).as_posix() for base in ('polisyos','tools') for p in (site/base).rglob('*.py')}
 assert actual_python=={n for n in expected if n.endswith('.py')};assert len(actual_python)==3146
 pths=[dict(record(p),content=p.read_text()) for p in sorted(site.glob('*.pth'))]
 assert (site/'e02_readonly_dependencies.pth').read_text()==config['dependency_site']+'\n'
 assert not any('polisyos' in r['content'] or str(config['source_root']) in r['content'] for r in pths)
 current=packet/(kind+'-consumer');assert not (current/'src').exists()
 for row in carrier['files']:
  name=row['path'];raw=(current/name.removeprefix('policy-engine/')).read_bytes();canonical=git('show',sha+':'+name)
  assert raw==canonical and digest(raw)==row['sha256'] and len(raw)==row['bytes'] and git('rev-parse',sha+':'+name).decode().strip()==row['blob']
 installed=read(kind+'-installed-proof.json');assert installed['source_sha']==sha and installed['source_tree']==tree and installed['isolated']==1
 assert not installed['origin_violations']
 assert all(Path(v).resolve().is_relative_to(site.resolve()) for v in installed['product_origins'].values())
 assert len(installed['collected_ids'])==162 and len(installed['adapted_tmle_readers'])==53
 assert not any(Path(v).is_relative_to(Path(config['source_root'])) for v in installed['sys_path'] if v)
 reader_rows=[]
 for p in sorted((packet/(kind+'-reader-origin-proofs')).glob('*.json')):
  body=json.loads(p.read_text());assert body['source_sha']==sha and body['isolated']==1 and not body['origin_violations']
  assert all(Path(v).resolve().is_relative_to(site.resolve()) for v in body['product_origins'].values())
  reader_rows.append(record(p))
 xml=ET.parse(packet/(kind+'-junit.xml'));cases=xml.findall('.//testcase');assert len(cases)==162
 counts=collections.Counter();modules={};failure_ids=[];failure_diagnostics=[]
 for case in cases:
  failure=case.find('failure');error=case.find('error');skip=case.find('skipped')
  outcome='FAIL' if failure is not None else 'ERROR' if error is not None else 'SKIP' if skip is not None else 'PASS'
  counts[outcome]+=1;module=case.attrib['classname'].split('.')[-1];modules.setdefault(module,collections.Counter())[outcome]+=1
  if failure is not None:
   text=(failure.text or '')+' '+failure.attrib.get('message','')
   assert module.startswith('test_')
   direct_seed=('seed_variable_alignments.yaml' in text and ('No such file' in text or 'FileNotFoundError' in text))
   failure_diagnostics.append({'id':case.attrib['classname']+'::'+case.attrib['name'],'direct_seed_diagnostic':direct_seed,'source_inference_if_not_direct':'Same default alignment/composition path; assertion omits NodeError body, no additional native replay'})
   failure_ids.append(case.attrib['classname']+'::'+case.attrib['name'])
 assert counts=={'PASS':130,'FAIL':32},counts
 failure_sets.append({v.split('tests.',1)[-1] for v in failure_ids})
 stdout=(packet/(kind+'-native-v2.stdout.txt')).read_text();stderr=(packet/(kind+'-native-v2.stderr.txt')).read_text();run=read(kind+'-native-v2.json')
 assert run['exit_code']==1 and run['environment']['PYTHONPATH']=='absent'
 for key in ('stdout','stderr','resources'):assert record(Path(run[key]['path']))==run[key]
 observers=[]
 for line in stdout.splitlines():
  try:v=json.loads(line.lstrip('.'))
  except (ValueError,TypeError):continue
  if isinstance(v,dict) and 'child_stdout' in v:
   assert v['child_exit']==0
   bodies=[json.loads(child_line) for child_line in v['child_stdout'].splitlines() if child_line]
   found=[body['installed_reader_observer'] for body in bodies if 'installed_reader_observer' in body]
   assert len(found)==1;observers.extend(found)
   result=bodies[-1]
   assert result['report_status']=='success' and result['report_method']=='tmle' and result['native_gate_eligible'] is False
   assert result['value_refusal']['status']=='value_refused'
   assert any('non-gating candidate' in issue['message'] for issue in result['confidence_issues'])
 assert len(observers)==53
 for v in observers:
  assert v['source_sha']==sha and v['isolated']==1 and v['origin_violations']==0
  assert record(Path(v['proof']))=={'path':v['proof'],'bytes':v['proof_bytes'],'sha256':v['proof_sha256']}
 profiles[kind]={'outcomes':dict(counts),'by_module':{k:dict(v) for k,v in modules.items()},'failure_ids':sorted(failure_ids),'failure_diagnostics':failure_diagnostics,'direct_seed_diagnostic_count':sum(r['direct_seed_diagnostic'] for r in failure_diagnostics),'failure_common_basis':'Missing existing default seed_variable_alignments.yaml directly printed in a subset; remaining status-only assertions classified by same canonical alignment source path (source inference, not direct body proof)' ,'product_origins':len(installed['product_origins']),'fresh_TMLe_I_reader_invocations':len(observers),'unique_reader_proofs':reader_rows,'actual_python_files':len(actual_python),'declared_product_resource_bytes':len(expected),'pth':pths,'native_command':run,'full_stdout':record(packet/(kind+'-native-v2.stdout.txt')),'full_stderr':record(packet/(kind+'-native-v2.stderr.txt')),'full_junit':record(packet/(kind+'-junit.xml')),'current_warnings_from_full_author_census':read('native-census-v2.json')['profiles'][kind]['literal_warning_counts'],'negative_gini_stderr_tracebacks':stderr.count('jax.pure_callback failed')}
assert failure_sets[0]==failure_sets[1]
for row in read('setup-command-records.json'):
 if 'exit_code' in row:assert row['exit_code']==0
 for key in ('stdout','stderr'):
  if key in row:assert record(Path(row[key]['path']))==row[key]
loader='policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/variable_alignment.py'
report={'source_sha':sha,'source_tree':tree,'outcome':'FAIL','consumer_verdict':'NO-GO: default composition seed resource absent in both genuinely installed profiles','custody_verdict':'PASS bounded complete declared source/archive/site/carrier byte contract; excludes complete runtime resource dependency closure','archives':archive_records,'source_export':{'files':len(entries),'bytes':total,'aggregate':aggregate.hexdigest(),'archive':record(source_archive)},'declared_resources':resources,'complete_product_resource_files':len(expected),'complete_actual_python_files':3146,'carrier_files_each_profile':len(carrier['files']),'profiles':profiles,'resource_class':{'maintained_facade':'polisyos.data_forge.read_api.catalog.default_seed_alignments_path','canonical_owner':loader,'owner_sha256':by_source[loader]['sha256'],'source_seed':by_source[seed],'existing_default':'Path(__file__).resolve().parents[6]/data/dataset_catalog/seed_variable_alignments.yaml','canonical_yaml_present_git_export':True,'yaml_absent_source_sdist_wheel_and_both_installs':True,'required_owner_direction':'Canonical source/package durable Path resolver plus finite original-resource HATCH/sdist mapping; no CWD/neighbor data fallback, source injection or version-specific upward wheel data placement'},'scientific_authority_limit':'Known synthetic candidates only; all real admitted/Runtime operational/statistical/value-positive authority and B56 study budget remain unestablished','historical_proof_limits':'Historical8236 installed199 and competing3dde receipts remain source-specific; no current whole-head PASS','native_reexecuted':False,'new_authority_or_resource_injected':False,'source_sites_archives_unchanged':True,'observer_history':{'outcome':'ERROR','scope':'Reviewer metadata assumed every failure XML repeats NodeError; six status-only assertions omit underlying message. Corrected direct-vs-source-inference attribution; native not rerun','full_stderr':record(out/'b5-first-observer-error.stderr.txt'),'original_script':record(out/'review_b5_packet_first_observer_error.py'),'second_observer_error':{'scope':'Reader observer is nested in outer source diagnostic child_stdout, not top-level; normalize only pytest dot prefix and parse canonical JSON child lines, no native rerun','full_stderr':record(out/'b5-second-observer-error.stderr.txt'),'script':record(out/'review_b5_packet_second_observer_error.py')}},'seconds':time.monotonic()-start}
(out/'b5-independent-review.json').write_text(json.dumps(report,indent=2)+'\n')
(out/'b5-full-source-manifest.json.gz').write_bytes(gzip.compress((json.dumps(source_rows,indent=2)+'\n').encode(),mtime=0))
print(json.dumps({'review':record(out/'b5-independent-review.json'),'full_manifest':record(out/'b5-full-source-manifest.json.gz'),'source_count':len(entries),'product_count':len(expected),'case_counts':{k:r['outcomes'] for k,r in profiles.items()},'observer_history':{'outcome':'ERROR','scope':'Reviewer metadata assumed every failure XML repeats NodeError; six status-only assertions omit underlying message. Corrected direct-vs-source-inference attribution; native not rerun','full_stderr':record(out/'b5-first-observer-error.stderr.txt'),'original_script':record(out/'review_b5_packet_first_observer_error.py'),'second_observer_error':{'scope':'Reader observer is nested in outer source diagnostic child_stdout, not top-level; normalize only pytest dot prefix and parse canonical JSON child lines, no native rerun','full_stderr':record(out/'b5-second-observer-error.stderr.txt'),'script':record(out/'review_b5_packet_second_observer_error.py')}},'seconds':time.monotonic()-start},indent=2))
