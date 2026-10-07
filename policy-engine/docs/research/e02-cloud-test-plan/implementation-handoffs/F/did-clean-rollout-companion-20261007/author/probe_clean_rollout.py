#!/usr/bin/env python3
"""Run the genuine clean-rollout case, not the full benchmark wave."""
import inspect
import json
import platform
import sys
import traceback
from importlib import metadata

import numpy as np

from benchmarks.natural_experiments import policy_natural_experiments as benchmark

def main():
    case=benchmark._case_clean_rollout()
    data=inspect.getclosurevars(case.runner).nonlocals['data']
    result=case.runner()
    treated=data.treatment==1;control=data.treatment==0;t0=data.time_treatment
    # Direct four group/time means on the actual balanced fixture, independent
    # of the owner's flattened OLS design and diagnostic helper.
    hand=(float(np.mean(data.outcome[treated,t0:]))-float(np.mean(data.outcome[treated,:t0]))) - (float(np.mean(data.outcome[control,t0:]))-float(np.mean(data.outcome[control,:t0])))
    report=result['report']
    print(json.dumps({'case':case.name,'fixture':{'n_units':data.n_units,'n_periods':data.n_periods,'pre_periods':data.pre_periods,'post_periods':data.post_periods,'time_treatment':t0,'expected_att':result['expected_point_estimate'],'outcome':data.outcome.tolist(),'treatment':data.treatment.tolist()},'independent_four_means_att':hand,'report':report.model_dump(mode='json'),'environment':{'python':platform.python_version(),'executable':sys.executable,'versions':{name:metadata.version(name) for name in ['numpy','scipy','statsmodels','pydantic']},'benchmark_origin':benchmark.__file__,'estimator_origin':inspect.getfile(benchmark.StandardDifferenceInDifferences),'backend_scope':'nativeStandardDiD/statsmodels; no DoWhy/EconML worker claim'}},ensure_ascii=False,indent=2),flush=True)
    assert abs(hand-float(report.point_estimate))<1e-10
    try:
        accepted=case.checker(result)
    except AssertionError:
        traceback.print_exc()
        return 1
    print(json.dumps({'actual_checker':bool(accepted),'oracle':'same actual fixture/runtime result, nativepretrend semantics and unchanged ATT bound','not_parallel_trend_identification':True}))
    return 0 if accepted else 1

if __name__=='__main__':raise SystemExit(main())
