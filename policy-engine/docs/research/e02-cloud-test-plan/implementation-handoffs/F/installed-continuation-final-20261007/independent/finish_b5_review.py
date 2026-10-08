from pathlib import Path
import gzip,hashlib,json,re,subprocess
out=Path(__file__).resolve().parent;packet=Path('/tmp/e02-F-continuation-20261007/foundry/installed-continuation-final')
def record(p):
 b=p.read_bytes();v={'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
 if p.suffix=='.gz':
  d=gzip.decompress(b);v['compression']='gzip';v['decoded_bytes']=len(d);v['decoded_sha256']=hashlib.sha256(d).hexdigest()
 return v
warnings={}
for kind in ('wheel','sdist'):
 stdout=(packet/(kind+'-native-v2.stdout.txt')).read_text();stderr=(packet/(kind+'-native-v2.stderr.txt')).read_text();rows=[]
 for line in stdout.splitlines():
  try:v=json.loads(line.lstrip('F.'))
  except ValueError:continue
  if isinstance(v,dict) and 'child_stdout' in v:rows.append(v)
 assert len(rows)==53
 warn=sum('operation=load_simulation_result' in row['child_stderr'] and 'reason=artifact_load_failed' in row['child_stderr'] for row in rows)
 prom=sum('Prometheus metrics exporter disabled after bootstrap failure' in row['child_stderr'] for row in rows)
 pattern=r'\[(?:INFO|WARNING|ERROR)\]\s+[^:\n]+:\s+(?:nan_detected|inf_detected|unexpected_key|missing_key|empty_array|shape_mismatch|distribution_shift)\b'
 flags=re.findall(pattern,stdout+'\n'+stderr)
 assert not flags
 terminal=re.findall(r'32 failed, 130 passed, (\d+) warnings in',stdout);assert terminal==['16']
 assert warn==36 and prom==36 and stderr.count('jax.pure_callback failed')==2
 warnings[kind]={'pytest_terminal_warnings':16,'PytestUnknownMarkWarning_unit':stdout.count('PytestUnknownMarkWarning: Unknown pytest.mark.unit'),'grouped_Equinox_deprecation_count_source_observation':'15 case locations grouped under one unchanged LayerNorm warning; full raw warning summary retained','decoded_TMLe_child_stderr_warning_episodes':warn,'decoded_Prometheus_bootstrap_failure_episodes':prom,'literal_9464_in_child_stderr':sum('9464' in row['child_stderr'] for row in rows),'port_scope':'Parent census names default9464; raw stderr reports address-in-use without port. No exporter positive witness','literal_SimulationResult_in_child_stderr':sum('SimulationResult' in row['child_stderr'] for row in rows),'actual_AnomalyFlag_str_pattern':pattern,'literal_anomaly_matches':flags,'stderr_expected_negative_Gini_callbacks':2,'source_quotas_or_warning_suppression_added':False,'historical_warning_proof_not_promoted':'Prior8236 fourteen false runtime anomalies/zero on corrected199 and90LGBM warning profile are separate source-specific observations, not newly measured here'}
meta={'source_sha':'b5a421d83336e0b50ad9a6747f3f7d041d4c1b5a','primary_review':record(out/'b5-independent-review.json'),'outcome':'FAIL','consumer_verdict':'NO-GO','custody_verdict':'PASS','resource_absence_own_actual_two_profile_probes':json.loads((out/'resource-absence.json').read_text()),'warning_review':warnings,'observer_errors_only':{'first_error':'Metadata assumed all failure assertions print actual seed diagnostic (26 direct,6 status-only actual); preserved original script/output','second_error':'Observer lives in exact frozen parent JSON child_stdout; nested decoding fixed without native rerun','commands':[{'argv':['python3',str(out/'review_b5_packet.py')],'cwd':'/workspace','stdout':str(out/('b5-'+label+'.stdout.txt')),'stderr':str(out/('b5-'+label+'.stderr.txt')),'exit_code':exitcode,'script_snapshot':str(out/snapshot)} for label,exitcode,snapshot in [('first-observer-error',1,'review_b5_packet_first_observer_error.py'),('second-observer-error',1,'review_b5_packet_second_observer_error.py'),('independent-review',0,'review_b5_packet.py')]]},'warning_observer_error':{'outcome':'ERROR','scope':'Literal SimulationResult/9464 matcher was too narrow for default loader episodes/address-in-use messages; corrected explicit operation and exporter failure predicates; complete old stdout/stderr and script preserved','argv':['python3',str(out/'finish_b5_review.py')],'cwd':'/workspace','exit_code':1},'native_or_heavyfit_reexecuted':False,'all_graph_product_resource_source_corrections_held_to_canonical_author':True,'authority_positive':'UNRUN/not established'}
(out/'b5-independent-review-companion.json').write_text(json.dumps(meta,indent=2)+'\n')
files=['b5-independent-review.json','b5-independent-review-companion.json','b5-full-source-manifest.json.gz','review_b5_packet.py','review_b5_packet_first_observer_error.py','review_b5_packet_second_observer_error.py','b5-independent-review.stdout.txt','b5-independent-review.stderr.txt','b5-first-observer-error.stdout.txt','b5-first-observer-error.stderr.txt','b5-second-observer-error.stdout.txt','b5-second-observer-error.stderr.txt','resource-absence.json','wheel-resource-absence.stdout.txt','wheel-resource-absence.stderr.txt','sdist-resource-absence.stdout.txt','sdist-resource-absence.stderr.txt','frozen-source-bindings.json','full-product-delta.diff','g-a0-resource-boundary-baseline.json','finish_b5_review.py','finish_b5_review_first_warning_observer_error.py','b5-warning-observer-error.stdout.txt','b5-warning-observer-error.stderr.txt']
selection={'outcome':'FAIL','scope':'Installed default composition consumer NO-GO; independent complete declared-byte custody PASS separately','primary_review':str(out/'b5-independent-review.json'),'files':[record(out/name) for name in files],'native_reexecuted':False,'complete_moderate_outputs':True,'source_or_installed_asset_mutation':False}
(packet/'independent-api-transfer-selection.json').write_text(json.dumps(selection,indent=2)+'\n')
print(json.dumps({'selection':record(packet/'independent-api-transfer-selection.json'),'primary':record(out/'b5-independent-review.json'),'companion':record(out/'b5-independent-review-companion.json'),'files':len(files),'bytes':sum(r['bytes'] for r in selection['files']),'decoded_total':sum(r.get('decoded_bytes',r['bytes']) for r in selection['files'])},indent=2))
