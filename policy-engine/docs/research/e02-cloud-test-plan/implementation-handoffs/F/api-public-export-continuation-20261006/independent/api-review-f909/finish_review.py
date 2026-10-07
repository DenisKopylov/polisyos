"""Freeze scoped representation/packaging review and full deciding output refs."""
import hashlib,json,pathlib,subprocess
D=pathlib.Path(__file__).resolve().parent;R=pathlib.Path('/workspace/e02-F-api-20261006');A=pathlib.Path('/tmp/e02-F-continuation-20261006/api')
SHA='f9095536592150362747b063c0f4cf3aac899bb0';TREE='c856bac7be6970c52161f4534aabb31524ddd9d8'
def h(b):return hashlib.sha256(b).hexdigest()
def ref(p):
 p=pathlib.Path(p);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':h(b),'full':True}
def git(*a):return subprocess.check_output(['git',*a],cwd=R)
def check_ref(x):
 b=pathlib.Path(x['path']).read_bytes();assert len(b)==x['bytes'] and h(b)==x['sha256']
def check_source(x):
 b=git('show',x['source_sha']+':'+x['source_path']);assert len(b)==x['bytes'] and h(b)==x['sha256']
names=['composition','composition-corrected','schema-packet'];records=[]
for n in names:
 r=json.loads((D/(n+'.json')).read_text());assert r['source_sha']==SHA and r['source_tree']==TREE and r['source_begin']==r['source_end'] and len(r['source_begin'])==6
 for x in r['source_begin']:check_source(x)
 for x in r['output_refs']:check_ref(x)
 records.append(r)
assert records[0]['exit_code']==1 and records[1]['exit_code']==records[2]['exit_code']==0
assert "AttributeError: module 'polisyos.ir.api' has no attribute 'CausalEstimatorInterval'" in (D/'composition.stderr.txt').read_text()
result=json.loads((D/'composition-corrected.stdout.txt').read_text())
assert (D/'composition-corrected.stdout.txt').read_bytes()==(D/'inspection.json').read_bytes()
assert result['native_static_representation']['entrypoints']==result['native_static_representation']['incomplete_canonical_violations']==38
assert len(result['all_explicit_read_refs'])==103
assert result['native_static_representation']['analytics_declared_candidates']==280
for x in result['exact_renderer_refs']+result['asset_refs']+[result['fixture_ref']]:check_source(x)
for x in result['canonical_consumer_controls']:check_ref(x['full_output']);assert x['actual_run_check_exit']==1 and x['incomplete_rows']==38
schema=json.loads((D/'schema-packet.stdout.txt').read_text())
for x in [schema['manifest_ref'],schema['canonical_generator_ref']]:check_source(x)
for row in schema['checks']:
 assert row['fresh_runtime_payload_equal'];check_source(row['snapshot_ref']);check_source(row['provider_ref'])
for row in schema['new_typed_bindings']:check_source(row['provider_ref'])
report={
 'reviewer':'graph_scm','role':'independent_read_only_composed_representation_and_projection','check':'PASS','decision':'GO_bounded_packaging_and_representation','outcome':'limited','candidate_sha':SHA,'candidate_tree':TREE,
 'slice_base_sha':'34808bdae09b4a8dbd35bda989c4dc787dcb4e86','packaging_sha':'a8c40ac9dca0d680dd82187e2538cbba9a34eb08','merged_root_source_sha':'7185572917f7a3db5e93385a176cb611b35aff42',
 'scope':'Six-path composed representation/packaging slice only: four packaging/test/docs paths plus two exact canonical outputs. Runtime parser admission source unchanged from approved a7; no new algorithm, generated schema write, build or full architecture verdict.',
 'source_bindings':records[1]['source_begin'],'source_begin_end_check':'PASS','findings':[],
 'checks':[
  {'name':'Exact canonical JSON and Markdown re-render','check':'PASS','outcome':'limited','output':str(D/'composition-corrected.stdout.txt'),'JSON_bytes':305296,'JSON_sha256':'93a37fc07dd2c58c8bb76c268718790e476290e70ca3f6181cdf1ddad0fe9a84','markdown_bytes':127724,'markdown_sha256':'928f050cf4b43bd8b0af692ce9895869710c2cbe25f0c93fb77a6c537d7a61a0'},
  {'name':'Actual canonical representation consumer fresh','check':'FAIL','outcome':'limited','exit_code':1,'incomplete_rows':38,'json_drift':False,'markdown_drift':False,'output':str(D/'fresh.canonical-check.stdout.txt'),'scope':'Representation freshness PASS; selected actual consumer still FAIL for all38UNKNOWN rows. Unrelated graph/baseline/README/exception/workflow/generated-family axes explicitly omitted in memory; this is not full architecture.'},
  {'name':'Canonical JSON corrupt total/complete fields refusal','check':'FAIL','outcome':'limited','expected':'JSON drift rejection','exit_code':1,'output':str(D/'corrupt_total_complete_field.canonical-check.stdout.txt'),'scope':'Memory input changes actual analytics total null→0 and completefalse→true; actual canonical run_check adds JSON drift and preserves38incomplete. No checker source or baseline change.'},
  {'name':'Canonical Markdown unknown→0 field refusal','check':'FAIL','outcome':'limited','expected':'Markdown drift rejection','exit_code':1,'output':str(D/'corrupt_unknown_markdown.canonical-check.stdout.txt'),'scope':'One literal unknown-label field modified only in memory; actual checker rejects Markdown drift and preserves38incomplete.'},
  {'name':'HATCH canonical mapping/source assets/fixture','check':'PASS','outcome':'limited','output':str(D/'composition-corrected.stdout.txt'),'force_include_count':7,'worker_assets':6,'source_assets_equal_refs':['5cd190d24d133f618fcc66ecc01f70c8a1b4f1f6','7185572917f7a3db5e93385a176cb611b35aff42'],'fixture_bytes':11758,'fixture_sha256':'b8f9227a18737490a539a70cbace221344a72e4935c6f28d9a7f35b65dc40f42','scope':'Force includes exactly six existing worker assets plus one digest resource; six original sdist source paths retained. Actual source profile resolver returns candidate workers/dowhy-014. Not installed build/numerical backend proof.'},
  {'name':'SCM1.1 and current TMLE enum schema packets','check':'PASS','outcome':'limited','output':str(D/'schema-packet.stdout.txt'),'scope':'Existing canonical generator recomputes fresh runtime schemas for StructuralCausalModelSpec and CausalEffectReport; payloads exactly equal current snapshots plus full/semantic manifest hashes. Source default1.1 and CausalMethod.TMLE actual enum are bound. No full-family schema freshness claim.'},
  {'name':'Actual newly composed typed bindings and incomplete candidates','check':'PASS','outcome':'limited','output':str(D/'schema-packet.stdout.txt'),'scope':'CausalEstimatorInterval and CausalResultKind root IR/analytics are identical leaf objects with explicit canonical registry owners. ir.api is binding registry, not an invented direct class facade. SCMTrainingRows/SCMFitProvenance root bindings retained. No InternalTwinNetwork root promotion. Analytics280 and world41 are unproved candidates, known0/nulltotal.'},
  {'name':'Initial reviewer registry/facade assumption','check':'ERROR','outcome':'limited','output':str(D/'composition.stderr.txt'),'scope':'Reviewer initially accessed class as ir.api attribute; this module supplies the canonical binding registry and helpers. Exact original AttributeError retained. Distinct corrected script verifies registry owner tuples and actual root/analytics class identity. No product defect or source repair.'},
  {'name':'Historical analytics selector 278 vs composed280','check':'FAIL','outcome':'limited','role':'author_execution_independently_inspected_not_rerun','output':str(A/'composed-analytics-historical-expectation.stdout'),'scope':'Known stale native-test literal; author retains full original1FAIL and is root-authorized to update only the selector assertion after this source hold. No parser/snapshot/resource mutation required.'},
 ],
 'inspection':result,'schema_packet':schema,'executions':records,
 'inspection_transport_alias':{'original_ref':ref(D/'inspection.json'),'transport_ref':ref(D/'composition-corrected.stdout.txt'),'basis':'Exact full byte equality measured; one stored body, no summary/truncation.'},
 'related_finding_ids':['LA-020','LA-007','LA-019','B215','B54','B56'],'closure_ids':[],
 'limits':['All38namespace rows remain UNKNOWN and canonical incompleteFAIL; source candidates are not proven native exports or totals.', 'Historical analytics278 at0c/a7 differs from actual composed280. New CausalEstimatorInterval/CausalResultKind registry entries explain the difference; exact current objects verified separately.', 'Freshness here is only two canonical representation files and two schema packets; no broader generated families, exceptions, README policy, deep-import collection or architecture green claimed.', 'No new wheel/sdist build or old installed/numerical PASS relabelled; packaging fixture bytes have an immutable origin but must run in the later installed profile.', 'No production CAS/input authority, causal validity, real data or G acceptance closure.', 'All read-only runs bound frozen f909source before/after; hold released after source reads complete. Scratch writes and memory corruption injection only.'],
 'author_hold_release':'All pinned f909 reads and scoped native checks complete. Author may apply root-authorized test-only composed analytics expectation correction; canonical generation/source resources require no change.'
}
(D/'review.json').write_text(json.dumps(report,indent=2)+'\n')
files=[D/'review.json',D/'finish_review.py',D/'run_check.py',D/'inspect_composition.py',D/'inspect_composition_corrected.py',D/'check_schema_packet.py']
for n in names:files += [D/(n+'.json'),D/(n+'.stdout.txt'),D/(n+'.stderr.txt')]
files += [pathlib.Path(x['full_output']['path']) for x in result['canonical_consumer_controls']]
files += [A/'composed-analytics-historical-expectation.stdout',A/'composed-analytics-historical-expectation.stderr']
assert len(files)==len(set(files))
selection={'source_sha':SHA,'source_tree':TREE,'check':'PASS','decision':'GO_bounded_packaging_and_representation','unique_full_files':len(files),'items':[ref(p) for p in files],'lossless_identical_output_aliases':[report['inspection_transport_alias']]}
selection['full_bytes']=sum(x['bytes'] for x in selection['items'])
(D/'transfer-selection.json').write_text(json.dumps(selection,indent=2)+'\n')
print(json.dumps({'review':ref(D/'review.json'),'selection':ref(D/'transfer-selection.json'),'full_files':len(files),'full_bytes':selection['full_bytes']}))
