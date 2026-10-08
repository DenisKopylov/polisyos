from __future__ import annotations
import hashlib,json,os,sys
from pathlib import Path
from polisyos.core.artifacts.ir_adapter import build_ir_artifact_store
from polisyos.ir.analytics.backtest import load_backtest_report
from polisyos.ir.registry.refs import BacktestReportRef
from polisyos.scientist.methods.backtesting import evaluator as evaluator_module
from polisyos.scientist.methods.backtesting.evaluator import PredictionEvaluator
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan, PredictionSource
ROOT=Path('/dev/shm/e02-orch03-20261008/oracle-empirical/review-d095')
SOURCE=Path('/dev/shm/e02-orch03-20261008/c09/policy-engine/src')
assert Path(evaluator_module.__file__).resolve().is_relative_to(SOURCE)
records=[]
def direct(name,intervals,y_true=None):
    s=PredictionEvaluator().evaluate(scenario_id=name,scenario_label=name,y_pred={'m':[0.,0.,0.]},y_true={'m':[0.,0.,0.] if y_true is None else y_true},intervals=intervals,metadata={'interval_admission':{'status':'evaluated','basis':'recomputed','requested_count':999}})
    r={'name':name,'requested':s.interval_requested_count,'evaluated':s.interval_evaluated_count,'point_compared':s.compared_count,'coverage':s.coverage_probability,'admission':s.metadata.get('interval_admission'),'bounds':[(x.ci_lower,x.ci_upper) for x in s.outcome_comparisons]}
    records.append(r)
    return s
for name,bounds in [('reverse',(1.,-1.)),('extra',(-1.,1.,2.)),('mapping',{0:-1.,1:1.}),('numeric_string',('-1','1')),('bool',(False,True))]:
    s=direct(name,{'m':[bounds]*3})
    assert s.interval_requested_count==s.compared_count==3
    assert s.interval_evaluated_count==0 and s.coverage_probability is None
    assert s.metadata['interval_admission']['status']=='limited'
    assert all(x.within_ci is None and x.ci_lower is None and x.ci_upper is None for x in s.outcome_comparisons)
s=direct('partial',{'m':[(-1.,1.)]})
assert s.interval_requested_count==3 and s.interval_evaluated_count==1
assert s.coverage_probability==1. and s.interval_availability==1/3
assert s.metadata['interval_admission']['coverage_scope']=='evaluated_pairs_only'
s=direct('unknown_and_extra',{'m':[(-1.,1.)]*4,'wrong':[(-1.,1.)]})
assert s.interval_evaluated_count==3 and s.metadata['interval_admission']['status']=='limited'
s=direct('equal',{'m':[(0.,0.)]*3})
assert s.interval_evaluated_count==3 and s.coverage_probability==1. and s.metadata['interval_admission']['status']=='evaluated'
s=direct('point_only',None)
assert s.interval_requested_count==0 and 'interval_admission' not in s.metadata

def persisted(name,intervals,truths=None):
    d=ROOT/name;d.mkdir(exist_ok=True)
    history=d/'history.json';history.write_text('{"m":[0,0,0]}')
    p=HistoricalValidationPlan(plan_id=name,historical_data_path=str(history),prediction_source=PredictionSource.PROVIDED,predicted_outcomes={'m':[0.,0.,0.]},prediction_intervals=intervals,ground_truth_outcomes={'m':[0.,0.,0.] if truths is None else truths},metadata={'interval_admission':{'status':'evaluated','basis':'recomputed','requested_count':999}})
    cas=d/'cas'
    report=BacktestOrchestrator(cas_root=str(cas)).run([p],report_id=name)
    assert report.cas_artifact_id
    ref=BacktestReportRef(artifact_id=report.cas_artifact_id)
    fresh=load_backtest_report(build_ir_artifact_store(cas),ref)
    for q in [report,fresh]:
      s=q.scenarios[0]
      records.append({'name':name,'surface':'producer' if q is report else 'freshCASreader','cas_id':q.cas_artifact_id,'degraded':q.degraded,'reasons':q.degraded_reasons,'trust_eligible':q.trust_eligible,'trust_score':q.trust_score,'coverage':q.overall_coverage_probability,'interval_admission':s.metadata.get('interval_admission'),'point_compared':s.compared_count})
    return fresh
for name,bounds in [('cas_reverse',[(1.,-1.)]*3),('cas_partial',[(-1.,1.)]),('cas_extra',[(-1.,1.)]*4),('cas_foreign',[(-1.,1.)]*3)]:
    ints={'m':bounds}
    if name=='cas_foreign':ints['foreign']=[(-1.,1.)]
    q=persisted(name,ints)
    assert q.degraded and not q.trust_eligible and q.trust_score is q.trust_grade is None
    assert any('interval_admission_limited' in x for x in q.degraded_reasons)
    assert q.n_metrics_evaluated==3
inside=persisted('cas_inside',{'m':[(-1.,1.)]*3},[-1.,0.,1.])
outside=persisted('cas_outside',{'m':[(-1.,1.)]*3},[-2.,0.,2.])
assert inside.overall_coverage_probability==1.
assert outside.overall_coverage_probability==1/3
point=persisted('cas_point_only',None)
assert not point.degraded
assert 'interval_admission' not in point.scenarios[0].metadata
assert point.overall_coverage_probability is None
print(json.dumps({'source_sha':'d095dbd5527ae8462f85c382a40877f16574c58a','module_origin':evaluator_module.__file__,'module_sha256':hashlib.sha256(Path(evaluator_module.__file__).read_bytes()).hexdigest(),'pid':os.getpid(),'python':sys.version,'records':records,'status':'PASS bounded synthetic defining consumer probe; heuristic trust policy not admitted'},sort_keys=True,indent=2))
