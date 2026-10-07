from __future__ import annotations
import contextlib,hashlib,importlib.util,json,math,pathlib,platform,subprocess,sys,time,traceback
repo=pathlib.Path('/dev/shm/e02-D-oct07-continuation');product=repo/'policy-engine';out=pathlib.Path(sys.argv[1]);fixture=pathlib.Path('/dev/shm/e02-D-B124-independent-tests/v2/test_service_trial_deduplication.py')
paths=['src/polisyos/scientist/methods/autotune/runtime.py','src/polisyos/scientist/methods/search/service.py','src/polisyos/scientist/methods/search/controller.py','src/polisyos/scientist/methods/search/frontier.py','src/polisyos/scientist/methods/search/objective.py','src/polisyos/common/serialization.py']
def state():
 return {'source':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=repo,text=True).strip(),'status':subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True),'source_paths':{p:hashlib.sha256((product/p).read_bytes()).hexdigest() for p in paths},'fixture_path':str(fixture),'fixture_sha256':hashlib.sha256(fixture.read_bytes()).hexdigest()}
before=state();assert before['source']=='b652b77eeec25f8ff1bd744d84ed20bd1b6cb21e' and before['status']==''
spec=importlib.util.spec_from_file_location('test_service_trial_deduplication',fixture);owner=importlib.util.module_from_spec(spec);sys.modules[spec.name]=owner;spec.loader.exec_module(owner)
from polisyos.scientist.methods.autotune.models import BenchmarkEvaluation,load_model_artifact
from polisyos.scientist.methods.search.run_state import SearchRunState
from polisyos.scientist.methods.search.service import _decode_checkpoint
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.manifest import ArtifactRef
cases=[]
for name,present,value in [('missing_primary',False,1),('genuine_zero',True,0),('ordinary_one',True,1)]:
 root=out/name;root.mkdir();record={'case':name,'metric_present':present,'candidate_value':value,'source':before,'check':'UNRUN','intended_property':'missing primary remains unavailable; present finite literal zero stays available, one stays actual1; not scientific law'}
 with (root/'stdout.txt').open('w') as stdout,(root/'stderr.txt').open('w') as stderr,contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
  try:
   corpus=owner._corpus()[:1];corpus[0]['value']=value
   runner,store,registry,suite,evaluator,loop=owner._runner(root,corpus,include_metric=present,promotable=False)
   result=runner.run(loop,suite_ref=suite,max_iterations=1)
   row=result.history[0];refs=row.stage_b_result['simulation_results'];evaluation_ref=ArtifactRef.model_validate(refs['evaluation_artifact_ref']);fresh=FileSystemCAS(root/'cas');evaluation=load_model_artifact(fresh,evaluation_ref,BenchmarkEvaluation);checkpoint=ArtifactRef.model_validate(result.telemetry['checkpoint_ref']);snapshot=fresh.get_verified_snapshot(checkpoint);saved=SearchRunState.from_checkpoint(_decode_checkpoint(snapshot.data)['run_state'])
   availability=refs.get('metric_assessment');passed=(not math.isfinite(row.objective_value) and saved.best_candidate is None and not saved.pareto_points) if not present else (math.isfinite(row.objective_value) and row.objective_value == -float(value))
   record.update(check='PASS' if passed else 'FAIL',actual_metric=evaluation.holdout_metrics,actual_status=evaluation.status,history_objective=row.objective_value,history_count=len(result.history),actual_calls=evaluator.calls,simulation_results=refs,metric_assessment=availability,best_candidate=saved.best_candidate,best_objective=saved.best_objective,frontier=saved.pareto_front,checkpoint_ref=checkpoint.model_dump(mode='json'),checkpoint_sha256=hashlib.sha256(snapshot.data).hexdigest(),evaluation_ref=evaluation_ref.model_dump(mode='json'),evaluation_snapshot_sha256=hashlib.sha256(fresh.get_verified_snapshot(evaluation_ref).data).hexdigest(),history_readback_matches=saved.history==result.history)
   print(json.dumps(record,sort_keys=True,default=str))
  except Exception as exc:
   record.update(check='ERROR',exception_type=type(exc).__name__,exception=str(exc));traceback.print_exc()
 record['outputs']={name:{'sha256':hashlib.sha256((root/name).read_bytes()).hexdigest(),'bytes':(root/name).stat().st_size} for name in ['stdout.txt','stderr.txt']};cases.append(record)
after=state();assert before==after
packet={'source':before,'source_unchanged':True,'cases':cases,'environment':{'python':sys.version,'executable':sys.executable,'platform':platform.platform()},'scope':'Actual existing native evaluator→immutableCAS→scalar/history/best/front→fresh owned reader diagnostic; no dedup/custom pipeline/source writes; no scientific/fiscal/invoice claim','P38':'Absent owned primary metric is substituted with actual numerical zero after normal typed response intake, creating a finite scalar/best/front instead of unavailable. Literal measuredzero is separate positive.'}
(out/'observations.json').write_text(json.dumps(packet,indent=2,default=str)+'\n');print(json.dumps({'directory':str(out),'source':before['source'],'tree':before['tree'],'cases':[(x['case'],x['check'],x.get('history_objective')) for x in cases]}))
