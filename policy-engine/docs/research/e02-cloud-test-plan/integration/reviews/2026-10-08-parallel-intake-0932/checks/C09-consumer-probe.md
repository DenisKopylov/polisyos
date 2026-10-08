# Exact verification harness transcript

This is the recorded Python reproduction recipe, not a new product module. Save the fenced body to an isolated scratch script before using the receipt argv; input source/tree and qualifications are in verdict.json.

```python
from __future__ import annotations
import json,sys,hashlib,subprocess
from pathlib import Path
checkout=Path(sys.argv[1]);out=Path(sys.argv[2]);gitroot=Path(sys.argv[3]);sha='ee0b2c85289d8c5537ba4e01713d9be71e2f557e';sys.path.insert(0,str(checkout/'policy-engine/src'))
from polisyos.core.artifacts.ir_adapter import build_ir_artifact_store
from polisyos.ir.analytics.backtest import load_backtest_report,persist_backtest_report
from polisyos.ir.registry.refs import BacktestReportRef
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan,PredictionSource
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.governance.backtest_matrix import _score_backtest_scenarios
from polisyos.scientist.methods.backtesting.temporal import TemporalEvaluationResult,build_temporal_backtest_report
from polisyos.calibration.forecast_bridge import _recompute_and_reconcile
fixtures=out/'consumer-fixtures';fixtures.mkdir(exist_ok=True);history=fixtures/'history.json';history.write_text('{"metric":[0,0,0]}')
plan=HistoricalValidationPlan(plan_id='partial-interval',plan_label='synthetic paired observations',historical_data_path=str(history),prediction_source=PredictionSource.PROVIDED,predicted_outcomes={'metric':[0.,0.,0.]},prediction_intervals={'metric':[(-2.,2.)]},ground_truth_outcomes={'metric':[0.,0.,0.]})
cas=fixtures/'cas';report=BacktestOrchestrator(cas_root=str(cas)).run([plan]);assert report.cas_artifact_id
ref=BacktestReportRef(artifact_id=report.cas_artifact_id,kind='ir.backtest_report',media_type='application/json');fresh=load_backtest_report(build_ir_artifact_store(cas),ref);scenario=fresh.scenarios[0]
assert scenario.metadata['interval_admission']['status']=='limited';assert scenario.interval_requested_count==3 and scenario.interval_evaluated_count==1
score=_score_backtest_scenarios([scenario])
# Public builder consumes a typed carrier whose scenario was produced by real orchestrator and fresh CAS reader.
carrier=TemporalEvaluationResult(scenario=scenario,pointwise_metrics={'path_rmse':0.,'path_mae':0.,'endpoint_abs_error':0.},functional_metrics={'integral_effect_abs_error':0.},uncertainty_metrics={'band_coverage':float(scenario.coverage_probability)},diagnostics_checks={'complete':True},gating_checks={'diagnostics_handled':True},thresholds={},acceptance_checks={},expected_outcome='pass',actual_outcome='pass',matches_expected_outcome=True,passes=True)
temporal=build_temporal_backtest_report(report_id='partial-temporal-projection',evaluations=[carrier]);store=build_ir_artifact_store(cas);tref=persist_backtest_report(store,temporal);temporal_fresh=load_backtest_report(store,tref)
recomputed=_recompute_and_reconcile(fresh)
origins=[];bad=[]
for name,mod in sorted(sys.modules.items()):
 if name!='polisyos' and not name.startswith('polisyos.'):continue
 file=getattr(mod,'__file__',None)
 if not file:continue
 path=Path(file).resolve()
 try:relative=path.relative_to(checkout).as_posix()
 except ValueError:bad.append({'module':name,'outside':str(path)});continue
 actual=subprocess.check_output(['git','hash-object',str(path)],cwd=gitroot,text=True).strip();expected=subprocess.check_output(['git','rev-parse',sha+':'+relative],cwd=gitroot,text=True).strip();origins.append({'module':name,'path':relative,'actual_blob':actual,'candidate_blob':expected})
 if actual!=expected:bad.append(origins[-1])
(out/'C09-consumer-probe-origins.json').write_text(json.dumps({'source':sha,'origins':origins,'mismatches':bad},indent=2)+'\n');assert not bad
result={'source':sha,'tree':'072e8906ac69f5b3589550a8bd9d57b4cb41b4a3','fixture_only':True,'production_authority_claim':False,'main_report':{'requested_intervals':scenario.interval_requested_count,'evaluated_intervals':scenario.interval_evaluated_count,'conditional_coverage':scenario.coverage_probability,'admission':scenario.metadata['interval_admission'],'degraded':fresh.degraded,'trust_eligible':fresh.trust_eligible,'degraded_reasons':fresh.degraded_reasons},'matrix_scoring':{'conditional_limited_scenario_score':score,'full_leaderboard_pipeline_executed':False},'temporal_public_builder_and_fresh_reader':{'admission':temporal_fresh.scenarios[0].metadata['interval_admission'],'degraded':temporal_fresh.degraded,'trust_eligible':temporal_fresh.trust_eligible,'report_persisted_and_fresh_loaded':True,'upstream_trajectory_producer_executed':False},'forecast_observation_reconciliation_only':list(recomputed),'usable_for_calibration_or_S10_gate_executed':False,'loaded_file_backed_polisyos_modules':len(origins),'source_mismatches':0}
print(json.dumps(result,ensure_ascii=False,indent=2));(out/'C09-consumer-probe.result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
# This is an assertion of the required propagation property, not a claim the current implementation passes.
assert not temporal_fresh.trust_eligible and temporal_fresh.degraded, 'C09 interval limitation escaped the public temporal persisted-report builder'
```
