import hashlib,io,json,subprocess,tomllib,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
F=Path('/tmp/e02-F-graph-profile-20261007/foundry/installed-4ee')
O=Path('/tmp/e02-F-graph-profile-20261007/api-review/installed4ee')
C=json.loads((F/'installed-config.json').read_text());R=Path(C['git_root']);S=Path(C['site']);H='4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d';T='551d4e760dc1168f6ad8182c9b176f00e94a2281'
assert C['source_sha']==H and C['source_tree']==T

def ref(p):
 p=Path(p);d=p.read_bytes();return {'path':str(p),'bytes':len(d),'sha256':hashlib.sha256(d).hexdigest()}
def git(*args):return subprocess.check_output(['git',*args],cwd=R)
def digest(d):return {'bytes':len(d),'sha256':hashlib.sha256(d).hexdigest()}
def match(raw,row):assert digest(raw)=={k:row[k] for k in ('bytes','sha256')}
assert git('rev-parse',H+'^{tree}').decode().strip()==T
hatch=tomllib.loads(git('show',H+':policy-engine/hatch.toml').decode())
force=hatch['build']['targets']['wheel']['force-include'];assert len(force)==11
entries={}
for item in git('ls-tree','-rz','--full-tree',H).split(b'\0'):
 if item:
  meta,p=item.split(b'\t',1);mode,kind,oid=meta.decode().split();entries[p.decode()]=oid
expected={p.removeprefix('policy-engine/src/').removeprefix('policy-engine/'):p for p in entries if p.startswith(('policy-engine/src/polisyos/','policy-engine/tools/'))}
for p,target in force.items():assert target not in expected;expected[target]='policy-engine/'+p
pre=json.loads((F/'pre-native-custody.json').read_text());assert pre['source_sha']==H and pre['source_tree']==T and pre['outcome']=='PASS'
rows=pre['bindings'];assert len(rows)==len(expected)==3464 and len(set(x['destination'] for x in rows))==3464
assert {x['destination']:x['source'] for x in rows}==expected
queries=[entries[x['source']] for x in rows]
cp=subprocess.run(['git','cat-file','--batch'],cwd=R,input=('\n'.join(queries)+'\n').encode(),capture_output=True,check=True)
stream=io.BytesIO(cp.stdout);observed=[];total=0
match(Path(C['wheel']).read_bytes(),pre['wheel'])
with zipfile.ZipFile(C['wheel']) as whl:
 assert {n for n in whl.namelist() if n.startswith(('polisyos/','tools/')) and not n.endswith('/')}==set(expected)
 for row,oid in zip(rows,queries,strict=True):
  header=stream.readline().decode().split();assert header[:2]==[oid,'blob'] and row['git_blob']==oid
  raw=stream.read(int(header[2]));assert stream.read(1)==b'\n';match(raw,row)
  assert (R/row['source']).read_bytes()==raw
  assert whl.read(row['destination'])==raw and (S/row['destination']).read_bytes()==raw
  total+=len(raw);observed.append({'source':row['source'],'git_blob':oid,'destination':row['destination'],'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'role':row['role']})
 assert not stream.read()
actual_py={p.relative_to(S).as_posix() for top in ('polisyos','tools') for p in (S/top).rglob('*.py')}
assert actual_py=={p for p in expected if p.endswith('.py')} and len(actual_py)==3147
carrier=json.loads((F/'carrier-manifest.json').read_text());assert carrier['source_sha']==H and carrier['source_tree']==T
bridges=[]
for row in carrier['files']:
 absolute=Path(row['path']);logical='policy-engine/'+absolute.relative_to(Path(C['carrier'])).as_posix();raw=git('show',H+':'+logical)
 assert row['git_sha']==H and row['git_blob']==entries[logical] and absolute.read_bytes()==raw
 match(raw,row);bridges.append({'logical_path':logical,'absolute_path':str(absolute),'git_blob':row['git_blob'],'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
assert len(bridges)==28 and not (Path(C['carrier'])/'src').exists()
# All complete saved execution streams, including both nondeciding harness errors.
executions=[]
for p in sorted(F.glob('*.execution.json')):
 e=json.loads(p.read_text());assert e['source_sha']==H and e['source_tree']==T
 for key in ('stdout','stderr'):assert ref(e[key]['path'])==e[key]
 executions.append({'name':p.stem.removesuffix('.execution'),'receipt':ref(p),'exit_code':e['exit_code'],'command':e['argv'],'cwd':e['cwd'],'environment':e.get('environment'),'stdout':e['stdout'],'stderr':e['stderr']})
# Complete origin/data proof inspection; no consumer execution or imports.
proofs=[]
for name in ['collect-proof.json','native-proof.json','removal-proof.json','fresh-admg/fresh-reader-proof.json','fresh-admg/fresh-bridge-proof.json']:
 p=F/name;j=json.loads(p.read_text());assert j['source_sha']==H and j['source_tree']==T
 origins=j['product_origins'];assert all(Path(path).resolve().is_relative_to(S.resolve()) for path in origins.values())
 isolation=j.get('isolated',j.get('parent_isolated'));assert isolation==1
 proofs.append({'name':name,'proof':ref(p),'owned_origin_count':len(origins),'origin_violations':0,'isolation':1,'pytest_exit':j.get('pytest_exit',j.get('raw_pytest_exit'))})
collect=json.loads((F/'collect-proof.json').read_text());native=json.loads((F/'native-proof.json').read_text())
assert collect['collected_ids']==native['collected_ids'] and len(native['collected_ids'])==16
xml=ET.parse(F/'native-junit.xml').getroot();suite=next(xml.iter('testsuite'));counts={k:int(suite.attrib[k]) for k in ('tests','failures','errors','skipped')}
assert counts=={'tests':16,'failures':0,'errors':0,'skipped':0}
removed_xml=ET.parse(F/'removal-junit.xml').getroot();removed_suite=next(removed_xml.iter('testsuite'));removed_counts={k:int(removed_suite.attrib[k]) for k in ('tests','failures','errors','skipped')}
assert removed_counts=={'tests':1,'failures':1,'errors':0,'skipped':0}
fail=next(removed_xml.iter('failure'));assert 'job.issues' in fail.text and 'assert ([]' in fail.text
# Actual independentPID and complete selected model/manifest relation equality.
P=F/'fresh-admg';r=json.loads((P/'fresh-reader-proof.json').read_text());parent=json.loads((P/'fresh-bridge-proof.json').read_text());payload=json.loads((P/'reader-input.json').read_text());child=json.loads((P/'fresh-reader.command.json').read_text())
assert r['outcome']==parent['outcome']=='PASS' and r['reader_pid']!=r['parent_pid']==parent['parent_pid']
assert r['isolated']==parent['parent_isolated']==1 and child['exit_code']==0 and '-I' in child['argv']
for key in ('stdout','stderr'):assert ref(child[key]['path'])==child[key]
assert r['selected_graph_ref']==parent['selected_graph_ref']==payload['selected_graph_ref'] and r['method_result_ref']==parent['method_result_ref']==payload['method_result_ref']
assert r['complete_typed_model_matches_parent'] and r['detached_row_mutation_does_not_rewrite_model']
assert {tuple(v) for v in r['literal_relation_oracle']}=={('Y','X','tail','arrow',None),('X','Y','arrow','arrow',None)}
assert payload['expected_model']['graph_type']=='admg'
assert r['manifest']==parent['selected_manifest'] and r['manifest']['kind']=='ir.causal_graph_model'
assert any(row['role']=='data_graph' and row['artifact_id']==r['method_result_ref']['artifact_id'] for row in r['manifest']['inputs'])
# Reopened selected CAS exact payload bytes/manifest identities inspected; no product import.
cas=Path(payload['cas_root']);selected=r['selected_graph_ref']['artifact_id'];method=r['method_result_ref']['artifact_id'];cas_rows=[]
for p in sorted(cas.rglob('*')):
 if p.is_file() and ('registry' not in p.parts):
  cas_rows.append(ref(p))
assert cas_rows
post=json.loads((F/'post-native-custody.json').read_text());assert post['outcome']=='PASS' and post['source_sha']==H and post['source_tree']==T
assert post['candidate_wheel']==pre['wheel'] and post['complete_candidate_source_wheel_site_files']==3464 and post['actual_python_files']==3147
assert len(post['carrier_logical_to_absolute_binding_adapter'])==28 and len(post['unchanged_packaging_lock_resources'])==14
for row in post['unchanged_packaging_lock_resources']:
 assert git('rev-parse',row['old_source_sha']+':'+row['path']).decode().strip()==row['git_blob']==entries[row['path']]
# Old profile post-custody is independently inspected evidence, not reexecuted here.
env=json.loads((F/'installed-environment.json').read_text());assert env['isolated']==1 and env['environment']['PYTHONPATH']=='absent' and env['environment']['POLISYOS_METRICS_PORT']=='9466'
assert (S/'e02_readonly_dependencies.pth').read_text()==C['dependency_site']+'\n'==env['literal_dependency_pth']
pth=[{'path':str(p),'text':p.read_text()} for p in sorted(S.glob('*.pth'))]
assert all(p['text'].strip()==C['dependency_site'] or p['text'].strip()=='import _virtualenv' for p in pth)
warning_lines=[line for line in (F/'native.stdout.txt').read_text().splitlines() if 'Warning:' in line]
assert len(warning_lines)==1 and 'PytestUnknownMarkWarning' in warning_lines[0]
assert not any(x in (F/'native.stdout.txt').read_text() for x in ['Prometheus bootstrap failed','RuntimeWarning','AnomalyFlag'])
result={'schema':'e02.F.api.installed4ee.packet_audit.v1','outcome':'PASS','source_sha':H,'source_tree':T,'wheel':pre['wheel'],'source_wheel_site_census':{'complete_files':3464,'tracked_product_files':sum(x['role']=='tracked_product' for x in rows),'forced_resources':len(force),'actual_python_files':3147,'total_product_resource_bytes':total,'full_binding_reference':ref(F/'pre-native-custody.json'),'full_actual_table':observed,'extra_missing_source_wheel_site_python':0},'carrier_census':{'files':28,'logical_absolute_bindings':bridges,'src_fallback_directory_absent':True},'executions':executions,'inspected_native_counts':counts,'inspected_native_collected_ids':native['collected_ids'],'inspected_native_warning_lines':warning_lines,'inspected_removal_counts':removed_counts,'inspected_removal_full_failure':fail.text,'inspected_origin_proofs':proofs,'different_pid_child':{'parent_pid':parent['parent_pid'],'reader_pid':r['reader_pid'],'parent_isolated':1,'child_isolated':1,'selected_graph_ref':r['selected_graph_ref'],'method_result_ref':r['method_result_ref'],'relation_oracle':r['literal_relation_oracle'],'same_complete_model':True,'selected_manifest_lineage':True,'detached_rows':True,'child_execution':child,'reader_payload':ref(P/'reader-input.json')},'pth':pth,'installed_environment':env,'post_native_custody':ref(F/'post-native-custody.json'),'old519_custody_scope':'Author fullpostguard read/execution inspected; no oldsites/archives rerun by reviewer and no prior519science transfer to4ee.','scope':'Independent complete saved packet/script/byte/origin/consumer/removal review; no new build/native fit/import/wave execution','limits':['Only current wheel qualified; new sdistUNRUN.','Actual synthetic ADMG selectedCAS child is independentPID; no realworldRuntime/identification positive.','Unsupported graph family rejection is reconciliation/Compose/Node-specific, not all partial graph consumers.','Initial collection/freshbridge failures are nondeciding harnessERROR, all exact raw/script snapshots preserved.','No broader estimator/backend/native199/79/TMLE53 repeat or authority/Gclosure.','OriginalqualityRuff103FAIL/static38FAIL/scanner2ERROR retained separate original-inputscope.']}
(O/'packet-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'audit':ref(O/'packet-audit.json'),'outcome':'PASS','full_files':3464,'resources':11,'actual_python':3147,'carrier':28,'native16':counts,'child_different_pid':True,'removal1':removed_counts,'inspected_execution_records':len(executions)},indent=2))
