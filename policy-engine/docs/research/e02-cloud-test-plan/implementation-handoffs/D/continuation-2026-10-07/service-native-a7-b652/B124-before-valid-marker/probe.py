from pathlib import Path
import contextlib,hashlib,json,subprocess,sys,traceback
from runpy import run_path
root=Path('/dev/shm/e02-D-oct07-continuation');product=root/'policy-engine';out=Path(sys.argv[1]);paths=['src/polisyos/scientist/methods/search/controller.py','src/polisyos/scientist/methods/search/frontier.py','src/polisyos/scientist/methods/search/pareto_registry.py','tests/unit/scientist/methods/search/test_semantic_dates_persisted_consumers.py']
def state():return {'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'status':subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True),'inputs':{n:hashlib.sha256((product/n).read_bytes()).hexdigest() for n in paths}}
source=run_path(str(product/paths[-1]));actual=source['_date_stage_b'];before=state();assert before['head']=='a7efe4b431986c3d79f490879cf49dbdedb1349e' and not before['status']
observations=[]
for profile,marker in [('invalid-format','unchanged-upstream-hash-marker'),('retained-valid-format','sha256:'+'a'*64)]:
 case=out/profile;case.mkdir();registry=source['ParetoRegistry'](case/'registry');service=source['_date_service'](case/'cas',registry)
 def false_marker(candidate,context):
  result=actual(candidate,context);result['policy_evaluation']=result['policy_evaluation'].model_copy(update={'metadata':{**result['policy_evaluation'].metadata,'candidate_hash':marker}});return result
 service.controller._stage_b=false_marker
 record={'profile':profile,'retained_returned_marker':marker,'source':before,'input_profile':'same actual native date3 defining positive; only returned metadata.candidate_hash added unchanged'}
 with (case/'stdout.txt').open('w') as stdout,(case/'stderr.txt').open('w') as stderr,contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
  try:
   result=service.run_search(initial_context={});fresh=source['ParetoRegistry'](case/'registry').get_snapshot(result.search_id)
   record.update(check='FAIL' if len(fresh.entries)!=2 else 'PASS',observed_history=len(result.history),semantic_dates=[r.candidate['semantic']['metadata']['starts_at'] for r in result.history],expected_distinct_logical_subjects=2,observed_distinct_registry_subjects=len(fresh.entries),registry_keys=list(fresh.entries),retained_evaluation_ids=[r.policy_evaluation.candidate_id for r in result.history],checkpoint_ref=service.checkpoint_ref.model_dump(mode='json'),fresh_registry=fresh.model_dump(mode='json'))
   print(json.dumps(record,default=str))
  except Exception as exc:
   record.update(check='ERROR',exception_type=type(exc).__name__,exception_message=str(exc));traceback.print_exc()
 record['after']=state();assert before==record['after'];record['outputs']={f:{'sha256':hashlib.sha256((case/f).read_bytes()).hexdigest(),'bytes':(case/f).stat().st_size} for f in ['stdout.txt','stderr.txt']};observations.append(record)
(out/'observations.json').write_text(json.dumps({'source_sha':before['head'],'profile':'bounded actual returned-hash marker diagnostic; no productionlaw or closureclaim','cases':observations},indent=2,default=str)+'\n');print(json.dumps({'out':str(out),'results':[(r['profile'],r['check'],r.get('observed_distinct_registry_subjects')) for r in observations]}))
