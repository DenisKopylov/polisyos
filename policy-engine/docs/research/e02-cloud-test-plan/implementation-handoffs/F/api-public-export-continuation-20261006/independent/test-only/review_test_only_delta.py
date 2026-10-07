"""Bind the test-only composed-name expectation without rerunning old waves."""
import hashlib,json,pathlib,subprocess
D=pathlib.Path(__file__).resolve().parent;A=pathlib.Path('/tmp/e02-F-continuation-20261006/api');R=pathlib.Path('/workspace/e02-F-api-20261006')
OLD='f9095536592150362747b063c0f4cf3aac899bb0';SHA='0c522b88cff658aa4cdf4990ada70dd363989e0d';TREE='0b308e5f5993121db26e1b3d0a3347817ef371c5'
def git(*a):return subprocess.check_output(['git',*a],cwd=R)
def ref(p):
 p=pathlib.Path(p);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'full':True}
paths=git('diff','--name-only',OLD,SHA).decode().splitlines();assert paths==['policy-engine/tests/repo_quality/architecture/test_public_surface_export_resolution.py']
body=git('show',SHA+':'+paths[0]);assert git('rev-parse',SHA+'^{tree}').decode().strip()==TREE
record=json.loads((A/'composed-analytics-final-native.json').read_text());assert record['target_sha']==SHA and record['tree_sha']==TREE and record['exit_code']==0 and record['source_status_before']==record['source_status_after']==''
for key in ['stdout','stderr']:
 b=pathlib.Path(record[key]['path']).read_bytes();assert len(b)==record[key]['bytes'] and hashlib.sha256(b).hexdigest()==record[key]['sha256']
assert '1 passed, 1 warning' in (A/'composed-analytics-final-native.stdout').read_text()
report={'reviewer':'graph_scm','role':'independent_read_only_test_only_delta','check':'PASS','decision':'GO_test_only_expectation','outcome':'limited','candidate_sha':SHA,'candidate_tree':TREE,'delta_predecessor_sha':OLD,'delta_path':paths[0],'source_ref':{'source_sha':SHA,'source_path':paths[0],'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()},'source_delta':'Exactly one test function changes: removes historical literal278, retains complete map/name equality and typedUNKNOWN/known0/null assertions; adds two explicit canonical owner tuples and actual analytics-to-leaf object identity. No implementation, HATCH, schema or generated snapshot changes.','prior_composition_review_ref':ref(D/'review.json'),'author_native_execution':record,'checks':[{'name':'Complete static diff read and sole test footprint','check':'PASS','outcome':'limited','output':str(D/'test-only-delta.patch')},{'name':'Actual single native selector','check':'PASS','outcome':'limited','role':'author_execution_independently_inspected_not_reexecuted','passed':1,'failed':0,'error':0,'skip':0,'warnings':1,'output':str(A/'composed-analytics-final-native.stdout')}],'closure_ids':[],'limits':['f909 representation/HATCH/schema GO retains its exact source; code and generated data unchanged by this test-only delta.','No a7/f909/installed/numerical or fullarchitecture execution relabelled; actual38UNKNOWN canonicalFAIL preserved.']}
(D/'test-only-delta.patch').write_bytes(git('diff',OLD,SHA))
(D/'test-only-delta-review.json').write_text(json.dumps(report,indent=2)+'\n')
files=[D/'test-only-delta-review.json',D/'review_test_only_delta.py',D/'test-only-delta.patch',A/'composed-analytics-final-native.json',A/'composed-analytics-final-native.stdout',A/'composed-analytics-final-native.stderr',A/'composed-analytics-final-native-spec.json']
selection={'source_sha':SHA,'source_tree':TREE,'check':'PASS','unique_full_files':len(files),'items':[ref(p) for p in files]};selection['full_bytes']=sum(x['bytes'] for x in selection['items'])
(D/'test-only-delta-transfer-selection.json').write_text(json.dumps(selection,indent=2)+'\n')
print(json.dumps({'review':ref(D/'test-only-delta-review.json'),'selection':ref(D/'test-only-delta-transfer-selection.json')}))
