from pathlib import Path
import hashlib,json,math,os,resource,sys,time
root=Path('/dev/shm/e02-orch03-20261008/c09/policy-engine')
sys.path.insert(0,str(root/'src'))
import pytest
from polisyos.scientist.methods.backtesting import evaluator
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
mode=sys.argv[1]
if mode=='guard':
 def legacy(value):
  try:
   lower,upper=float(value[0]),float(value[1])
  except (TypeError,ValueError,IndexError,KeyError):
   return None,'invalid_interval_shape'
  if not math.isfinite(lower) or not math.isfinite(upper):return None,'non_finite_interval'
  if lower>upper:lower,upper=upper,lower
  return (lower,upper),None
 evaluator._read_interval=legacy
 suffix='tests/unit/scientist/methods/backtesting/test_evaluator_interval_admission.py::'
 selectors=[suffix+'test_invalid_interval_preserves_point_comparisons_and_requested_denominator[interval0-reversed_interval]',suffix+'test_invalid_interval_preserves_point_comparisons_and_requested_denominator[interval1-invalid_interval_shape]',suffix+'test_actual_backtest_keeps_unavailable_intervals_non_gating_after_cas_readback[interval0]']
else:
 original=BacktestOrchestrator._run_single_scenario
 def bridge_removed(self,*args,**kwargs):
  result=original(self,*args,**kwargs)
  return (*result[:-1],[r for r in result[-1] if r!='interval_admission_limited'])
 BacktestOrchestrator._run_single_scenario=bridge_removed
 selectors=['tests/unit/scientist/methods/backtesting/test_evaluator_interval_admission.py::test_actual_backtest_keeps_unavailable_intervals_non_gating_after_cas_readback[interval0]']
out=Path('/dev/shm/e02-orch03-20261008/c09-scratch')
argv=['-q',*selectors,f'--basetemp={out/("removed-"+mode)}',f'--junitxml={out/("removed-"+mode+".junit.xml")}','-o',f'cache_dir={out/("removed-"+mode+"-cache")}']
start=time.monotonic();rc=pytest.main(argv)
metadata={'source_sha':'ee0b2c85289d8c5537ba4e01713d9be71e2f557e','source_tree':'072e8906ac69f5b3589550a8bd9d57b4cb41b4a3','mode':mode,'argv':argv,'pytest_returncode':rc,'expected_returncode':1,'wall_seconds_after_import':time.monotonic()-start,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'method':'in-process replacement of actual runtime property; source enums/strings/markers and files unchanged'}
(out/('removed-'+mode+'.execution.json')).write_text(json.dumps(metadata,indent=2)+'\n')
sys.exit(0 if rc==1 else 2)
