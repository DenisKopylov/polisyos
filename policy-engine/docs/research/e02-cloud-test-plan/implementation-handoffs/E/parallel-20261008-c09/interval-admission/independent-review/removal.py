from __future__ import annotations
import json,os,time,resource
from pathlib import Path
from polisyos.scientist.methods.backtesting import evaluator as evaluator_module
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan,PredictionSource
from polisyos.core.artifacts.ir_adapter import build_ir_artifact_store
from polisyos.ir.analytics.backtest import load_backtest_report
from polisyos.ir.registry.refs import BacktestReportRef
ROOT=Path('/dev/shm/e02-orch03-20261008/oracle-empirical/review-d095')
start=time.monotonic();records=[]
orig=evaluator_module._read_interval

def legacy(value):
    try:
        lo,hi=float(value[0]),float(value[1])
    except (TypeError,ValueError,IndexError,OverflowError):
        return None,'invalid_interval_shape'
    if lo>hi:lo,hi=hi,lo
    return (lo,hi),None

def run(name):
    d=ROOT/name;d.mkdir(exist_ok=True)
    h=d/'history.json';h.write_text('{"m":[0,0,0]}')
    p=HistoricalValidationPlan(plan_id=name,historical_data_path=str(h),prediction_source=PredictionSource.PROVIDED,predicted_outcomes={'m':[0.,0.,0.]},prediction_intervals={'m':[(1.,-1.)]*3},ground_truth_outcomes={'m':[0.,0.,0.]})
    cas=d/'cas';report=BacktestOrchestrator(cas_root=str(cas)).run([p],report_id=name)
    fresh=load_backtest_report(build_ir_artifact_store(cas),BacktestReportRef(artifact_id=report.cas_artifact_id))
    try:
        assert fresh.scenarios[0].coverage_probability is None
        assert not fresh.trust_eligible
    except AssertionError:
        state='EXPECTED_FAIL'
    else:
        state='UNEXPECTED_PASS'
    records.append({'case':name,'negative_test_state':state,'cas_ref':report.cas_artifact_id,'fresh_coverage':fresh.scenarios[0].coverage_probability,'fresh_trust_eligible':fresh.trust_eligible,'fresh_degraded':fresh.degraded,'retained_interval_admission':fresh.scenarios[0].metadata['interval_admission']})
    assert state=='EXPECTED_FAIL'

evaluator_module._read_interval=legacy
run('guard_removed')
evaluator_module._read_interval=orig
orig_bridge=BacktestOrchestrator._run_single_scenario

def bridge_removed(self,plan):
    scenario,warnings,requested,effective,reasons=orig_bridge(self,plan)
    return scenario,warnings,requested,effective,[r for r in reasons if r!='interval_admission_limited']
BacktestOrchestrator._run_single_scenario=bridge_removed
# Actual limited interval persists, while the consumer readiness discriminator fails.
d=ROOT/'bridge_removed';d.mkdir(exist_ok=True);h=d/'history.json';h.write_text('{"m":[0,0,0]}')
p=HistoricalValidationPlan(plan_id='bridge_removed',historical_data_path=str(h),prediction_source=PredictionSource.PROVIDED,predicted_outcomes={'m':[0.,0.,0.]},prediction_intervals={'m':[(1.,-1.)]*3},ground_truth_outcomes={'m':[0.,0.,0.]})
cas=d/'cas';report=BacktestOrchestrator(cas_root=str(cas)).run([p],report_id='bridge_removed')
fresh=load_backtest_report(build_ir_artifact_store(cas),BacktestReportRef(artifact_id=report.cas_artifact_id))
try:
    assert fresh.degraded and not fresh.trust_eligible
except AssertionError:
    state='EXPECTED_FAIL'
else:
    state='UNEXPECTED_PASS'
records.append({'case':'bridge_removed','negative_test_state':state,'cas_ref':report.cas_artifact_id,'fresh_coverage':fresh.scenarios[0].coverage_probability,'fresh_trust_eligible':fresh.trust_eligible,'fresh_degraded':fresh.degraded,'retained_interval_admission':fresh.scenarios[0].metadata['interval_admission']})
assert state=='EXPECTED_FAIL'
BacktestOrchestrator._run_single_scenario=orig_bridge
print(json.dumps({'source':'d095dbd5527ae8462f85c382a40877f16574c58a','method':'in-process removal of runtime helper/consumer effect; unchanged file markers remain; no source mutation','pid':os.getpid(),'records':records,'wall_seconds':time.monotonic()-start,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},indent=2,sort_keys=True))
