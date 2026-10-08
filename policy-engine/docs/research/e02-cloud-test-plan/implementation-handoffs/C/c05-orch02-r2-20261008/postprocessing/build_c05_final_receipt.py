"""Post-process captured outputs only; this does not execute tests or mutate source."""
from __future__ import annotations
import hashlib,json,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter

P=Path(__file__).resolve().parent
REPO=Path('/workspace/orch02-c05')
SHA='5ccbfa15c5671623a4c1ff7a3145460c5ca5a857'
WAVE=P/'c05-wave-definition-5ccbfa15.json'

def digest(path):
 return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
 wave=json.loads(WAVE.read_text()); commands=[]; observed_paths={}; outside=[]
 for definition in wave['commands']:
  raw=P/'raw'/definition['name']; m=json.loads((raw/'command.json').read_text()); origins=json.loads((raw/'runtime-origins.json').read_text()); resource=json.loads((raw/'resource.json').read_text())
  assert m['source_sha']==SHA and m['source_binding_intact']
  result={'name':definition['name'],'command_receipt':str(raw/'command.json'),'command_receipt_sha256':digest(raw/'command.json'),'argv':m['argv'],'environment':m['environment'],'cwd':m['cwd'],'executable_path':m['executable_path'],'executable_resolved':m['executable_resolved'],'executable_sha256':m['executable_sha256'],'raw_exit_code':m['exit_code'],'source_sha':m['source_sha'],'source_tree':m['source_tree'],'source_sha_after':m['source_sha_after'],'source_binding_intact':m['source_binding_intact'],'source_status_all_before':m['source_status_all_before'],'source_status_all_after':m['source_status_all_after'],'started_at_utc':m['started_at_utc'],'finished_at_utc':m['finished_at_utc'],'wall_seconds':m['wall_seconds'],'resource':resource,'purpose':definition['purpose'],'harness_sha256':m['harness_sha256'],'plugin_sha256':m['plugin_sha256'],'explicit_external_plugins':m['explicit_external_plugins'],'python':origins['python'],'packages':origins['packages'],'origin_denominator':origins['origin_denominator'],'origin_counts':{'all':len(origins['origins']),'owned':sum(k in {'polisyos','tools'} or k.startswith(('polisyos.','tools.')) for k in origins['origins'])},'outputs':{f.name:{'path':str(f),'bytes':f.stat().st_size,'sha256':digest(f)} for f in raw.iterdir() if f.is_file()}}
  for name,entry in origins['origins'].items():
   if name not in {'polisyos','tools'} and not name.startswith(('polisyos.','tools.')):continue
   try:relative=Path(entry['path']).relative_to(REPO).as_posix()
   except ValueError:outside.append({'command':definition['name'],'name':name,**entry});continue
   observed_paths.setdefault(relative,[]).append({'command':definition['name'],'name':name,'observed_sha256':entry['sha256']})
  result['native_origins']={k:v for k,v in origins['origins'].items() if k not in {'polisyos','tools'} and not k.startswith(('polisyos.','tools.'))}
  if (raw/'selected-tests.json').exists():
   selected=json.loads((raw/'selected-tests.json').read_text());result['test_selection']=selected
   for filename,entry in selected['physical_test_inputs'].items():
    try:relative=Path(filename).relative_to(REPO).as_posix()
    except ValueError:
     assert filename in wave['harnesses'] and entry['sha256']==wave['harnesses'][filename]['sha256'];continue
    observed_paths.setdefault(relative,[]).append({'command':definition['name'],'name':'<selected physical pytest input>','observed_sha256':entry['sha256']})
  if (raw/'junit.xml').exists():
   cases=ET.parse(raw/'junit.xml').findall('.//testcase');failures=[]
   for case in cases:
    for tag in ['failure','error','skipped']:
     node=case.find(tag)
     if node is not None:failures.append({'name':case.get('name'),'classname':case.get('classname'),'tag':tag,'message':node.get('message'),'body':node.text})
   result['junit']={'cases':len(cases),'passed':len(cases)-len(failures),'failures':sum(f['tag']=='failure' for f in failures),'errors':sum(f['tag']=='error' for f in failures),'skips':sum(f['tag']=='skipped' for f in failures),'raw_nonpass_cases':failures}
  else:result['junit']=None;result['junit_basis']='Direct in-process property observer driver, not pytest; complete original semantic events/stdout/stderr retained, no fabricated JUnit or pytest PASS count'
  for filename,key in [('semantic.json','semantic'),('session-events.json','actual_sessions'),('wvs-events.json','actual_wvs'),('runtime-binding-events.json','actual_bindings')]:
   if (raw/filename).exists():result[key]=json.loads((raw/filename).read_text())
  if 'semantic' in result:
   semantic=result['semantic'];relative=Path(semantic['owned_fixture_source']).relative_to(REPO).as_posix()
   observed_paths.setdefault(relative,[]).append({'command':definition['name'],'name':'<semantic AST original owned fixture>','observed_sha256':semantic['source_sha256']})
  commands.append(result)
 proc=subprocess.Popen(['git','-C',str(REPO),'cat-file','--batch'],stdin=subprocess.PIPE,stdout=subprocess.PIPE); bindings={}; mismatches=[]
 for relative,observations in sorted(observed_paths.items()):
  proc.stdin.write(f'{SHA}:{relative}\n'.encode());proc.stdin.flush();head=proc.stdout.readline().decode().strip().split();assert len(head)==3,head
  size=int(head[2]);body=proc.stdout.read(size);assert proc.stdout.read(1)==b'\n';source_hash=hashlib.sha256(body).hexdigest();matched=all(o['observed_sha256']==source_hash for o in observations)
  bindings[relative]={'git_blob':head[0],'bytes':size,'source_sha256':source_hash,'matches_all_observations':matched,'observations':observations}
  if not matched:mismatches.append(relative)
 proc.stdin.close();assert proc.wait()==0
 main_command=commands[0];initial=P/'c05-native-initial-receipt-2734ee49.json';initial_data=json.loads(initial.read_text())
 assert main_command['junit']=={'cases':119,'passed':119,'failures':0,'errors':0,'skips':0,'raw_nonpass_cases':[]},main_command['junit']
 assert main_command['test_selection']['nodeids']==initial_data['test_selection']['nodeids']
 assert not mismatches and not outside
 report={'schema':'orch02r2.independent-c05-final-native-receipt.v1','owner':'/root/native_c05_c12 independent direct tester; no children/source edits','source_sha':SHA,'source_tree':main_command['source_tree'],'wave_definition':str(WAVE),'wave_definition_sha256':digest(WAVE),'initial_red':{'source_sha':initial_data['source_sha'],'receipt':str(initial),'receipt_sha256':digest(initial),'cases':119,'passed':117,'failures':2,'errors':0,'skips':0,'actual_class':'Restored existing context-before-global-before-owner resolution entry at3 affected consumers; initial raw RED preserved, no test/harness changes'},'final_affected_denominator':{'selected_unique_pytest_cases':119,'passed':119,'same_selected_nodes_as_initial':True,'full_changed_input_files':{'DFI03':48,'DFK02':36,'catalog_retrieval':24},'borrowed_changed_loader_API_SQL_cases':10,'independent_actual_owner_global_context_case':1,'assertion_or_harness_weakening':False},'commands':commands,'harnesses':wave['harnesses'],'source_inputs':wave['source_inputs'],'supplier_contour':wave['supplier_contour'],'runtime_source_binding':{'denominator':'Complete loaded polisyos/tools file-bearing sys.modules origins plus all selected owned physical test inputs, bound to exact final source Git objects; no full executed function closure claim','distinct_git_inputs':len(bindings),'outside_owned_lane':outside,'mismatches':mismatches,'rows':bindings},'deciding_semantics':{},'limits':['No G composition, source adoption, formal closure, production corpus, architecture or complete locked runtime profile acceptance inferred','Full119 on new5ccb inputs explicitly authorized after actual2734 RED; old661112/36/scanner not replayed','Only covered sequential profile policy currentness; ALL headers/credentials/auth overlays, remote versions, concurrent atomic snapshots and arbitrary retrieval registry injections remain declared boundaries','Legacy empty-plan dispatcher test is branch witness, not nonempty legacy data proof; new real legacyWorldBank2cases separately prove actual session reuse/cleanup and native SQL rows','Borrowed Eurostat parallel transport/capability callbacks controlled by fixture; actual API/cache close/SQL exercised, absent lazy HTTP session not claimed','WVS core cache removal decides actual aggregation annotation reader quantity, not numerical mean-versus-mode divergence; call-count removal only owned operation1vs4, no whole performance claim','Direct assertion observer scripts retain raw semantic events and classifier labels separately; no fabricated JUnit counts for those drivers']}
 by_name={c['name']:c for c in commands}
 marker_expressions={"registry_path.read_bytes() == registry_bytes", "config.stage_state_path.read_bytes() == marker_bytes", "config.observation_ingest_checkpoint_path.read_bytes() == checkpoint_bytes", "config.benchmark_report_path.read_bytes() == report_bytes"}
 scalar_expressions={"partial['evaluation_mode'] == 'partial-eval'", "partial['metrics']['benchmark_partial_eval'] == 1", "partial['diagnostic_context']['core_output_receipt_current'] is False", "'benchmark' not in stale.skipped_stages"}
 for label in ['profile','seed']:
  control=by_name[f'c05-5ccb-{label}-control'];removed=by_name[f'c05-5ccb-{label}-removed'];cs=control['semantic'];rs=removed['semantic']
  markers=[e for e in rs['events'] if e['expression'] in marker_expressions]
  assert len(markers)==4 and all(e['holds'] for e in markers)
  scalar_events=[e for e in rs['events'] if e['expression'] in scalar_expressions]
  assert len(scalar_events)==4 and all(not e['holds'] for e in scalar_events)
  assert cs['error'] is None and rs['error'] is None and cs['verdict']=='PASS' and rs['verdict']=='DISCRIMINATING'
  report['deciding_semantics'][label+'_material_basis']={'control_raw_label':cs['verdict'],'control_literal_assertions':len(cs['events']),'control_all_hold':all(e['holds'] for e in cs['events']),'removed_raw_label':rs['verdict'],'removed_raw_exit':removed['raw_exit_code'],'removed_error':rs['error'],'only_removed_quantity':rs['removal']['quantity'],'unchanged_marker_byte_comparisons':markers,'actual_deciding_scalar_events':scalar_events,'actual_behavior':'Before producer repair, benchmark-only invocation incorrectly skips benchmark and retains full-ready/partial-eval=0/current=True report; unchanged canonical data/evidence/fetch trace retained. The control computes partial-eval/current=False. No claim the removed run freshly recomputed the stale report.','stop_before_producer_repair':True,'full_native_positive_producer_repair':'Both unchanged owned material_change parameters pass in final119; actual producer refetch/persisted rows and seed evidence assertions remain active'}
 wvs_control=by_name['c05-5ccb-wvs-control']['semantic'];wvs_removed=by_name['c05-5ccb-wvs-removed']['semantic'];divergent=[e for e in wvs_removed['events'] if not e['holds']]
 assert wvs_control['verdict']=='PASS' and wvs_removed['verdict']=='DISCRIMINATING' and wvs_removed['error'] is None and len(divergent)==2
 report['deciding_semantics']['wvs_actual_warm_reader']={'control_raw_label':wvs_control['verdict'],'removed_raw_label':wvs_removed['verdict'],'only_removed_quantity':wvs_removed['removal']['quantity'],'actual_divergent_events':divergent,'boundary':'Both real selected bulk-row aggregation metadata and normalized condition metadata retain weighted_mean instead of new weighted_mode. Value fixture remains1; no numerical mean/mode discriminator claim.'}
 observed=main_command['actual_sessions'];removed=by_name['c05-5ccb-session-reuse-removed']['actual_sessions']
 main_closes=[e for e in observed['events'] if e['kind']=='actual_canonical_cache_close' and 'test_real_catalog_session' in e['nodeid']]
 removed_closes=[e for e in removed['events'] if e['kind']=='actual_canonical_cache_close']
 assert len(main_closes)==2 and len(removed_closes)==2 and all(e['all_observed_sessions_closed'] and e['worldbank_session_state_none'] for e in main_closes+removed_closes)
 assert all(len(e['observed_sessions'])==1 for e in main_closes) and all(len(e['observed_sessions'])==2 for e in removed_closes)
 assert by_name['c05-5ccb-session-reuse-removed']['junit']['failures']==2
 report['deciding_semantics']['actual_canonical_session_reuse']={'control':'Same2 owned real legacy API success/error cases PASS in119:2 normalized requests,1 canonical handle/actualClientSession, real original close/disconnect, nativeSQL2rows2.5 or2failures/no rows','removed_raw_exit':1,'removed_junit_failures':2,'actual_failure_surface':'Unchanged owned len(connected)==1 observes2==1 in both cases','only_removed_quantity':removed['removed_quantity'],'actual_sessions_after_close_control':main_closes,'actual_sessions_after_close_removed':removed_closes,'actual_removed_persisted_outputs':[e for e in removed['events'] if e['kind']=='actual_persisted_ingest'],'isolation_cleanup':'Product original cache.close disconnects current handle; only deliberately orphaned old handle disconnected on same loop by observer; all4 total sessions closed across2cases. No cache/provider/store substitution.'}
 forward=by_name['c05-5ccb-wvs-forwarding-removed'];events=forward['actual_wvs']['events'];reads=[e for e in events if e['kind']=='actual_policy_snapshot_read'];cells=[e for e in events if e['kind']=='actual_normalizer_without_forwarding'];sql=[e for e in events if e['kind']=='actual_duckdb_bulk_result']
 assert len(reads)==4 and len(cells)==3 and len(sql)==1 and forward['junit']['failures']==1
 report['deciding_semantics']['wvs_owned_operation_call_count']={'control':'Unchanged owned final119 test passes1read per operation and changed policy value0->2 under real DuckDB3cell aggregation','removed_raw_exit':1,'removed_junit_failures':1,'actual_failure_surface':'Unchanged owned reads==1 assertion observes4==1','only_removed_quantity':forward['actual_wvs']['removed_quantity'],'actual_policy_reads':len(reads),'actual_native_SQL_cells':len(cells),'actual_cells':cells,'actual_duckdb_rows':sql,'boundary':'Matched removal fails at first operation call-count assertion before second policy phase; initial native aggregate value0/sample_size3 remains preserved. No whole-law throughput/RSS/performance acceptance.'}
 report['deciding_semantics']['owner_global_context_dispatch']=main_command['actual_bindings']
 report['postprocessor']={'path':str(Path(__file__).resolve()),'sha256':digest(Path(__file__).resolve()),'basis':'Postprocessing captured bytes/Git source objects only; no tests or source mutation'}
 out=P/'c05-native-final-receipt-5ccbfa15.json';out.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'receipt':str(out),'sha256':digest(out),'bytes':out.stat().st_size,'distinct_git_inputs':len(bindings),'counts':[{'name':c['name'],'exit':c['raw_exit_code'],'junit':{k:v for k,v in c['junit'].items() if k!='raw_nonpass_cases'} if c['junit'] else None,'semantic_verdict':c.get('semantic',{}).get('verdict'),'semantic_error':c.get('semantic',{}).get('error'),'wall':c['wall_seconds'],'rss':c['resource']['maximum_resident_set_size_kib']} for c in commands]},indent=2))

if __name__=='__main__':main()
