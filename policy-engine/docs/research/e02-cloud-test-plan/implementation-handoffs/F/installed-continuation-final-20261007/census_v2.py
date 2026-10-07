"""Reconcile literal native output and JUnit without promoting failed/omitted profiles."""
import re
import collections
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
base=Path(__file__).resolve().parent
config=json.loads((base/'installed-config.json').read_text());out={}
for kind in ('wheel','sdist'):
 tests=ET.parse(base/(kind+'-junit.xml')).getroot().findall('.//testcase');by_module=collections.defaultdict(collections.Counter)
 for test in tests:
  status='FAIL' if test.find('failure') is not None else 'ERROR' if test.find('error') is not None else 'SKIP' if test.find('skipped') is not None else 'PASS'
  by_module[test.attrib['classname'].split('.')[-1]][status]+=1
 raw=(base/(kind+'-native-v2.stdout.txt')).read_text();observations=[]
 for line in raw.splitlines():
  index=line.find('{"case":')
  if index>=0:
   try:observations.append(json.loads(line[index:]))
   except json.JSONDecodeError:pass
 assert len(observations)==53 and all(row['child_exit']==0 for row in observations)
 proofs=[];reports=[]
 for row in observations:
  lines=row['child_stdout'].splitlines();observer=json.loads(lines[0])['installed_reader_observer'];report=json.loads(lines[-1]);ref=Path(observer['proof']);proofraw=ref.read_bytes()
  assert len(proofraw)==observer['proof_bytes'] and hashlib.sha256(proofraw).hexdigest()==observer['proof_sha256']
  actual=json.loads(proofraw);assert actual['isolated']==1 and not actual['origin_violations'];assert observer['isolated']==1 and observer['origin_violations']==0
  assert report['report_status']=='success' and report['ci'] and report['native_gate_eligible'] is False
  assert report['value_refusal']['reason_code']=='method_output_contract_unresolved'
  assert any(issue['severity']=='blocker' and issue['path']==['artifacts_index','causal_envelope_ref'] for issue in report['confidence_issues'])
  reports.append(report['report_id']);proofs.append(observer['proof_sha256'])
 assert len(set(reports))==1
 parent=json.loads((base/(kind+'-installed-proof.json')).read_text());assert not parent['origin_violations']
 out[kind]={'actual_cases':len(tests),'outcomes':dict(collections.Counter(status for counts in by_module.values() for status,count in counts.items() for _ in range(count))),'by_module':dict(by_module),'parent_product_origins':len(parent['product_origins']),'fresh_isolated_readers':len(observations),'actual_reader_origin_proof_count':len(set(proofs)),'reader_origin_count_range':[min(json.loads(row['child_stdout'].splitlines()[0])['installed_reader_observer']['product_origins'] for row in observations),max(json.loads(row['child_stdout'].splitlines()[0])['installed_reader_observer']['product_origins'] for row in observations)],'zero_origin_escapes':True,'all_readers_same_actual_native_report':reports[0],'all_kept_SUCCESS_CI_candidate_Confidence_blocker_value_contract_refusal':True,'literal_warning_counts':{'expected_bad_SimulationResult_loads':sum('Degraded path component=governance.confidence_pass' in row['child_stderr'] for row in observations),'Prometheus_fixed9464_bootstrap_failures_child':sum('Prometheus metrics exporter disabled' in row['child_stderr'] for row in observations),'Prometheus_bootstrap_mentions_complete_stdout':raw.count('Prometheus metrics exporter disabled'),'PytestUnknownMarkWarning_unit':1,'Equinox_LayerNorm_deprecations':15,'actual_AnomalyFlag_warning_pattern':len(re.findall(r'\[(?:INFO|WARNING|ERROR)\] [^\\\n]*?: (?:nan_detected|inf_detected|unexpected_key|missing_key|empty_array|shape_mismatch|distribution_shift)', raw)),'LightGBM_literal':raw.count('LightGBM')},'stderr_expected_negative_Gini_JAX_callback_tracebacks':(base/(kind+'-native-v2.stderr.txt')).read_text().count('jax.pure_callback failed')}
proof={'source_sha':config['source_sha'],'source_tree':config['source_tree'],'profiles':out,'outcome':'FAIL','deciding_blocker':'32Graph cases each fail missing existing default seed_variable_alignments.yaml. Full162/no skip/error census kept. Archive3459declaredbyteclosure passing does not establish actual default-resource dependency closure.','warnings_scope':'Current literal162 counts only. Earlier15=14runtime+1instrumentation and0runtime/90optionalLightGBM profile are retained exact8236 proof, not remeasured in this affectedwave. Existing source conftest logging filters retained; no warning suppression introduced. Prometheus fixed-port bootstrap failures retained; exporter positive UNRUN.','scientific_limits':'Synthetic numerical candidates are not genuine operational/statistical/value authority or B56 admitted aggregate study budget.'}
(base/'native-census-v2.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps({'source_sha':config['source_sha'],'profiles':{kind:{key:value for key,value in row.items() if key in ('actual_cases','outcomes','fresh_isolated_readers','zero_origin_escapes','literal_warning_counts')} for kind,row in out.items()},'outcome':'FAIL'}))
