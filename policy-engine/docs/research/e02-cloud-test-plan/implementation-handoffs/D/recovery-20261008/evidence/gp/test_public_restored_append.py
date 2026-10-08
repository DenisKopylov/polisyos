"""Independent scratch witness for public same-basis continuation; source read only."""
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path('/workspace/ORCH04-C13/policy-engine')
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))

from _helpers.search_strategies import make_evaluation
from polisyos.scientist.methods.search.strategies import bayesian as native
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import ParameterBounds


def test_public_restored_append_before_due_interval_keeps_fitted_parameters(monkeypatch):
    space = SearchSpace([ParameterBounds(name='x', lower=-5.0, upper=5.0)])
    config = native.BayesianConfig(n_initial=1, refit_interval=50,
                                   num_restarts=3, raw_samples=32, seed=109,
                                   fallback_on_failure=False)
    real_fit = native.fit_gpytorch_mll
    fit_calls = []

    def spy(mll):
        fit_calls.append(int(mll.model.train_inputs[0].shape[-2]))
        return real_fit(mll)

    monkeypatch.setattr(native, 'fit_gpytorch_mll', spy)
    strategy = native.BayesianOptimizer(space, config)
    observations = [make_evaluation(candidate_id=f'synthetic-{i}',
                                    params={'x': -3.5+i}, score=(i-3)**2,
                                    space=space) for i in range(8)]
    initial_candidate = strategy.suggest(observations)
    assert initial_candidate.source_strategy == 'bayesian_acquisition'
    assert fit_calls == [8]
    state = strategy.get_state()
    restored = native.BayesianOptimizer(space, config)
    restored.set_state(state)
    assert fit_calls == [8]
    expanded = [*observations, make_evaluation(candidate_id='synthetic-new',
                                              params={'x': 4.0}, score=.25, space=space)]
    candidate = restored.suggest(expanded)
    assert candidate.source_strategy == 'bayesian_acquisition'
    report = {'original_iteration': state.iteration, 'expanded_iteration': restored._iteration,
              'refit_interval':config.refit_interval, 'real_fit_train_row_counts':fit_calls,
              'source':native.__file__, 'restored_last_refit_iteration':restored._last_refit_iteration,
              'restored_last_train_size':restored._last_train_size,
              'actual_source_imports':[
                  {'module':name, 'path':str(path), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
                  for name,module in sorted(sys.modules.items())
                  if (origin:=getattr(module,'__file__',None)) and
                  (path:=pathlib.Path(origin)).is_file() and str(path).startswith(str(ROOT))]}
    pathlib.Path('/workspace/ORCH04-evidence/gp/public-restored-append/report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='actual_source_imports'}))
    assert fit_calls == [8], 'same-basis append before scheduled refit must condition learned model without a new MLL fit'
