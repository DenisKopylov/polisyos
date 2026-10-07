import copy
import hashlib
import inspect
import json
import platform
import sys
from importlib import metadata
from pathlib import Path
import numpy as np
from benchmarks.natural_experiments import policy_natural_experiments as benchmark

case = benchmark._case_clean_rollout()
data = inspect.getclosurevars(case.runner).nonlocals['data']
result = case.runner()
report = result['report']
treated = data.treatment == 1
control = data.treatment == 0
t0 = data.time_treatment
hand = (float(np.mean(data.outcome[treated, t0:])) - float(np.mean(data.outcome[treated, :t0]))) - (float(np.mean(data.outcome[control, t0:])) - float(np.mean(data.outcome[control, :t0])))
assert abs(hand - float(report.point_estimate)) < 1e-10
assert case.checker(result) is True
index = next(i for i, d in enumerate(report.diagnostics) if d.test_name == 'pre_trend_parallelism')
controls = []

def rejected(name, updates=None, detail_updates=None, remove_detail=None, remove_diagnostic=False, report_updates=None):
    diagnostics = list(report.diagnostics)
    if remove_diagnostic:
        diagnostics.pop(index)
    else:
        test = diagnostics[index]
        fields = dict(updates or {})
        if detail_updates or remove_detail:
            details = copy.deepcopy(test.details)
            details.update(detail_updates or {})
            if remove_detail:
                details.pop(remove_detail, None)
            fields['details'] = details
        diagnostics[index] = test.model_copy(update=fields)
    changed = report.model_copy(update={'diagnostics': diagnostics, **(report_updates or {})})
    offered = {**result, 'report': changed}
    try:
        case.checker(offered)
    except AssertionError as error:
        controls.append({'name': name, 'outcome': 'PASS', 'actual_refusal': str(error), 'unchanged_method': changed.method == report.method, 'unchanged_status': changed.status == report.status, 'offered_report': changed.model_dump(mode='json')})
    else:
        raise AssertionError(f'{name} falsely accepted')

rejected('passed_true', updates={'passed': True})
rejected('statistic_invented', updates={'statistic': 0.0})
rejected('p_value_invented', updates={'p_value': 0.5})
rejected('status_passed', detail_updates={'status': 'passed'})
rejected('wrong_reason', detail_updates={'reason': 'enough_periods'})
rejected('missing_reason', remove_detail='reason')
rejected('identification_authority_true', detail_updates={'identification_authority': True})
rejected('missing_identification_authority', remove_detail='identification_authority')
rejected('missing_pretrend_diagnostic', remove_diagnostic=True)
rejected('att_drift', report_updates={'point_estimate': float(report.point_estimate) + 1.0})
root = Path('/workspace/e02-F-closeout-20261006/policy-engine/src').resolve()
origins = []
for name, module in sorted(sys.modules.items()):
    if name == 'polisyos' or name.startswith('polisyos.'):
        path = getattr(module, '__file__', None)
        if path:
            actual = Path(path).resolve()
            assert actual.is_relative_to(root), (name, str(actual))
            origins.append({'module': name, 'path': str(actual)})
print(json.dumps({'scope': 'one genuine native StandardDiD clean-rollout; ten output-checker falsifiers reuse that report; no worker/scientific authority claim', 'case': case.name, 'fixture': {'outcome': data.outcome.tolist(), 'treatment': data.treatment.tolist(), 'time_treatment': t0, 'pre_periods': data.pre_periods, 'post_periods': data.post_periods}, 'actual_report': report.model_dump(mode='json'), 'independent_four_means_att': hand, 'checker_positive': True, 'negative_controls': controls, 'origins': origins, 'environment': {'executable': sys.executable, 'python': platform.python_version(), 'versions': {name: metadata.version(name) for name in ['numpy','scipy','statsmodels','pydantic']}, 'benchmark_origin': benchmark.__file__, 'estimator_origin': inspect.getfile(benchmark.StandardDifferenceInDifferences)}}, ensure_ascii=False, indent=2))
