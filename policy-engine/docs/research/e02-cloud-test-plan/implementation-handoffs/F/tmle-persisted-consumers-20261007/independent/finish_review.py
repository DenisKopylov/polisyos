"""Bind complete independent native observations and a replayable synthetic CAS input."""
import gzip,hashlib,io,json,subprocess,tarfile,xml.etree.ElementTree as ET
from pathlib import Path
out=Path('/tmp/e02-F-continuation-20261007/foundry/fit-composed-review')
root=Path('/workspace/e02-F-tmle-20261006')
science='0c81614f5aa737a4b26c6c74044955a842b26cf4';metadata='8d94a937ca6e3f886ada9ad5c1f76dadb049da84'
def ref(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def git(*args):return subprocess.check_output(['git','-C',str(root),*args])
result=json.loads((out/'native-result.json').read_text())
assert result['source_sha']==science and result['exit_code']==0 and result['source_guard_unchanged']
suites=list(ET.parse(out/'native.xml').iter('testsuite'))
assert len(suites)==1 and suites[0].attrib['tests']=='53' and all(suites[0].attrib[x]=='0' for x in ('errors','failures','skipped'))
rows=[]
for line in (out/'native.stdout.txt').read_text().splitlines():
 at=line.find('{"case":')
 if at>=0:rows.append(json.loads(line[at:]))
assert len(rows)==53
observed=[]
for row in rows:
 assert row['child_exit']==0
 child=json.loads(row['child_stdout'].splitlines()[-1])
 spec=json.loads(Path(row['consumer_spec']).read_text())
 causal=[i for i in child['confidence_issues'] if i['code']=='CONFIDENCE_GATE_ELIGIBILITY_LOW' and i['path']==['artifacts_index','causal_envelope_ref'] and i['severity']=='blocker']
 loads=[i for i in child['confidence_issues'] if i['code']=='CONFIDENCE_SIM_RESULT_LOAD_FAILED']
 assert len(causal)==1 and len(loads)==int(spec['simulation_kind'] in {'missing','corrupt','wrong_model'})
 assert child['value_refusal']['reason_code']=='method_output_contract_unresolved'
 assert child['value_refusal']['resolved_contract_id'] is None and child['report_status']=='success' and not child['native_gate_eligible']
 observed.append({'case':row['case'],'spec_sha256':ref(Path(row['consumer_spec']))['sha256'],'report_id':child['report_id'],'bundle_id':child['bundle_id'],'source_id':child['source_id'],'point':child['point'],'ci':child['ci'],'persisted_envelope_point':child['persisted_envelope_point'],'persisted_envelope_ci':child['persisted_envelope_ci'],'offered_source':child['offered_source'],'offered_gate_eligible':child['offered_gate_eligible'],'causal_role_blockers':len(causal),'simulation_load_warnings':len(loads),'value_refusal':child['value_refusal']['reason_code']})
for key in ('report_id','bundle_id','source_id','point'):
 assert len({str(row[key]) for row in observed})==1
assert sum(x['simulation_load_warnings'] for x in observed)==36
packet=out/'native-tmp/tmle-consumers0/producer-packet.json'
cas=Path(json.loads(packet.read_text())['cas_root'])
inputs=sorted(p for p in (cas/'artifacts/sha256').rglob('*') if p.is_file())
# Keep the actual manifest/view layout needed by CAS; no ownership journals or locks.
archive=out/'native-cas-input.tar.gz'
with archive.open('wb') as stream:
 with gzip.GzipFile(fileobj=stream,mode='wb',mtime=0,filename='') as zipped:
  with tarfile.open(fileobj=zipped,mode='w') as tar:
   for p in inputs:
    raw=p.read_bytes();info=tarfile.TarInfo(str(p.relative_to(cas)));info.size=len(raw);info.mtime=0;info.mode=0o644;tar.addfile(info,io.BytesIO(raw))
archive_refs=[{**ref(p),'archive_member':str(p.relative_to(cas))} for p in inputs]
(out/'cas-input-manifest.json').write_text(json.dumps({'archive':ref(archive),'files':archive_refs,'total_raw_bytes':sum(x['bytes'] for x in archive_refs),'scope':'unique actual synthetic producer CAS; no production inputs, tracked product sources, ownership journals, or locks'},indent=2)+'\n')
actual_delta=git('diff','--name-only',science,metadata).decode().splitlines()
fragment='policy-engine/release-fragments/unreleased/2026-10-07-tmle-persisted-consumers.toml'
assert actual_delta==[fragment]
old=git('show',science+':'+fragment);new=git('show',metadata+':'+fragment)
assert old.replace(b'type = "other"',b'type = "added"')==new
review={'schema':'e02.foundry.fit-independent-review.v1','reviewer':'F/foundry independent of FIT author','outcome':'GO','scientific_source_sha':science,'scientific_source_tree':result['source_tree'],'metadata_candidate_sha':metadata,'metadata_candidate_tree':git('rev-parse',metadata+'^{tree}').decode().strip(),'implementation_scope':'three new test/docs/fragment paths only; zero product source delta','native':{'result':ref(out/'native-result.json'),'junit':ref(out/'native.xml'),'tests':53,'pass':53,'fail':0,'error':0,'skip':0,'wall_seconds':result['wall_seconds'],'pytest_seconds':float(suites[0].attrib['time']),'shared_native_identity':{key:observed[0][key] for key in ('report_id','bundle_id','source_id','point','ci','persisted_envelope_point','persisted_envelope_ci')},'case_axes':{'forged_source_cases':52,'native_unmodified_cases':1,'min_ratio':[0.0,1.0],'causal_location':['index','top'],'simulation_cases':13,'all53_child_exit':0,'all53_causal_role_blockers':1,'all53_value_refusal':'method_output_contract_unresolved'},'simulation_load_warning_cases':36,'stdout':ref(out/'native.stdout.txt'),'stderr':ref(out/'native.stderr.txt'),'same_report_bundle_source_all53':True,'new_quota':False},'independent_controls':json.loads((out/'mixed-controls.json').read_text()),'metadata_delta':{'paths':actual_delta,'change':'fragment type other → added; all test/docs/provider bytes unchanged','original_scoped_render':'FAIL retained by author','corrected_scoped_render':'author PASS read completely; metadata delta independently read'},'actual_synthetic_input':{'producer_packet':ref(packet),'cas_archive':ref(archive),'cas_input_manifest':ref(out/'cas-input-manifest.json'),'reconstruction':'restore archive in unique scratch CAS; replace only producer-packet cas_root; run official frozen53 test or independent supplied replayer','raw_files':len(inputs)},'authority_disposition':{'operational_EvalSafety':'genuine appointed/default-provider positive unavailable; failclosed default resolver/appointment/registry remain','statistical_identification':'SUCCESS+CI is candidate, accepted source/graph/estimand/target authority absent','value_projection':'actual upstream method_output_contract_unresolved before gate predicate312; no gate312-positive claim','whole_Node_production_authority':'UNRUN','B56_admitted_common_study_budget':'UNRUN'},'limitations':['Known 600-row synthetic DGP property; no admitted real-data causal conclusion.','Fuzzy/transport identification, genuine producer authority and native causal value contract are not supplied by this fixture.','Native53 subprocesses are fresh processes with source-bound PYTHONPATH; they are not installed -I witness.','Full production/cross-study/runtime admission positive and global integration acceptance remain separate.','Metadata fragment correction does not change numerical proof; original render FAIL retained.'],'recommendation':{'B54':'existing owner receipt unchanged; no new closure from this consumer slice','B56':'limited; no whole admitted production workload proof'},'source_guard':{'native_before_after':True,'mixed_before_after':True},'closure_ids':[]}
(out/'review.json').write_text(json.dumps(review,indent=2)+'\n')
selected=['capture_native.py','native-command.json','native-result.json','native.stdout.txt','native.stderr.txt','native.xml','capture_mixed.py','check_mixed_native_consumer.py','mixed-controls.json','cas-input-manifest.json','native-cas-input.tar.gz','review.json','finish_review.py']
for mode in ('mixed_priority','malformed_top','remove_role_issue'):selected.extend([mode+'.json',mode+'.stdout.txt',mode+'.stderr.txt'])
files=[ref(out/name) for name in selected]+[ref(packet)]
(out/'transfer-selection.json').write_text(json.dumps({'scientific_source_sha':science,'metadata_candidate_sha':metadata,'files':files,'scope':'23 unique independent measured inputs/outputs/replayers; no copied tracked bodies','publication':'FIT author may commit these verbatim as independent companions; own F authority packet will cite published refs'},indent=2)+'\n')
print(json.dumps({'GO':True,'native':53,'extra_actual_positives':2,'retained_marker_removal_expected_FAIL':1,'warning_cases':36,'files':len(files),'review':ref(out/'review.json'),'selection':ref(out/'transfer-selection.json')}))
