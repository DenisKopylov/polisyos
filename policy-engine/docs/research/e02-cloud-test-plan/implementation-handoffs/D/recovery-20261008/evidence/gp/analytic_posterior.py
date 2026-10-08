"""Independent bounded GP oracle; scratch evidence, no product/test authority."""
import argparse
import copy
import hashlib
import importlib
import io
import json
import math
import os
import pathlib
import sys
import time

p = argparse.ArgumentParser()
p.add_argument('--source', required=True)
p.add_argument('--out', required=True)
p.add_argument('--removal', action='store_true')
a = p.parse_args()
source = pathlib.Path(a.source).resolve()
out = pathlib.Path(a.out).resolve()
out.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(source / 'src'))
sys.path.insert(0, str(source / 'tests'))

import numpy as np
import torch
import botorch
import gpytorch
from _helpers.search_strategies import make_evaluation
from polisyos.scientist.methods.search.strategies import bayesian as native
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import ParameterBounds

fits = []
real_fit = native.fit_gpytorch_mll
def observe_fit(mll):
    started = time.monotonic()
    result = real_fit(mll)
    fits.append({'wall_seconds': time.monotonic() - started,
                 'train_rows': int(mll.model.train_inputs[0].shape[-2])})
    return result
native.fit_gpytorch_mll = observe_fit

space = SearchSpace([ParameterBounds(name='x', lower=-5.0, upper=5.0)])
cfg = native.BayesianConfig(n_initial=9, refit_interval=50, max_train_size=64,
                            fallback_on_failure=False, seed=109)
strategy = native.BayesianOptimizer(space, cfg)
assert strategy._botorch_ready
compatibility = {'search_space_fingerprint': space.sobol_space_fingerprint(),
                 'input_transform_fingerprint': 'Normalize[0,1]',
                 'outcome_transform_fingerprint': 'Standardize[m=1]',
                 'noise_model_fingerprint': 'GaussianLikelihood[inferred]',
                 'objective_fingerprint': 'scalar_score[minimize]',
                 'context_fingerprint': 'synthetic/gp-oracle/v1'}
coordinates = [.13, .20, .29, .37, .48, .56, .64, .73, .79, .86]
scores = [2 + math.sin(7*x) + .2*x for x in coordinates]
evaluations = []
for i, (x, score) in enumerate(zip(coordinates, scores, strict=True)):
    evaluation = make_evaluation(candidate_id=f'synthetic-{i}', params={'x': 10*x-5},
                                 score=score, space=space)
    evaluation.provenance_ref = f'synthetic/gp-oracle/evaluation-{i}'
    evaluation.metadata = {'replicate_id': f'replica-{i}', 'seed': i,
                           'warm_start_compatibility': dict(compatibility)}
    evaluations.append(evaluation)
strategy.warm_start(evaluations[:6])
corpus = strategy._select_training_subset(evaluations[6:])
assert [e.candidate_id for e in corpus] == [e.candidate_id for e in evaluations]
strategy._iteration = len(corpus)
train_X, train_Y = strategy._prepare_training_data(corpus)
strategy._fit_gp(train_X, train_Y)
assert len(fits) == 1
queries = np.array([[.12], [.31], [.61], [.90]], dtype=np.float64)

def basis(model):
    assert type(model).__name__ == 'SingleTaskGP'
    assert type(model.covar_module).__name__ == 'RBFKernel'
    assert type(model.mean_module).__name__ == 'ConstantMean'
    assert type(model.likelihood).__name__ == 'GaussianLikelihood'
    assert model.covar_module.lengthscale.numel() == 1
    return {'model': type(model).__module__+'.'+type(model).__name__,
            'kernel': 'RBFKernel(unit amplitude, scalar lengthscale)',
            'mean_constant': float(model.mean_module.constant.detach().item()),
            'lengthscale': float(model.covar_module.lengthscale.detach().item()),
            'noise_variance_standardized': float(model.likelihood.noise.detach().item()),
            'input_offset': float(model.input_transform.offset.detach().item()),
            'input_coefficient': float(model.input_transform.coefficient.detach().item()),
            'outcome_mean': float(model.outcome_transform.means.detach().item()),
            'outcome_std': float(model.outcome_transform.stdvs.detach().item()),
            'dtype': str(next(model.parameters()).dtype),
            'device': str(next(model.parameters()).device)}

frozen = basis(strategy._model)
params_before = {n: v.detach().clone() for n, v in strategy._model.named_parameters()}
transform_before = {name: {n: v.detach().clone() for n,v in getattr(strategy._model, name).state_dict().items()}
                    for name in ('input_transform', 'outcome_transform')}

def oracle(xs, ys, fixed):
    # NumPy only: independent matrix conditioning; no torch/model/kernel/posterior call.
    x = (np.asarray(xs, dtype=np.float64) - fixed['input_offset']) / fixed['input_coefficient']
    q = (queries - fixed['input_offset']) / fixed['input_coefficient']
    y = (np.asarray(ys, dtype=np.float64).reshape(-1) - fixed['outcome_mean']) / fixed['outcome_std']
    def rbf(left, right):
        distance = (left[:, None, :] - right[None, :, :]) / fixed['lengthscale']
        return np.exp(-.5 * np.sum(distance * distance, axis=-1))
    C = rbf(x, x) + fixed['noise_variance_standardized'] * np.eye(len(x))
    L = np.linalg.cholesky(C)
    alpha = np.linalg.solve(L.T, np.linalg.solve(L, y-fixed['mean_constant']))
    cross = rbf(x, q)
    V = np.linalg.solve(L, cross)
    mean = fixed['mean_constant'] + cross.T @ alpha
    cov = rbf(q, q) - V.T @ V
    return (mean * fixed['outcome_std'] + fixed['outcome_mean'],
            cov * fixed['outcome_std'] ** 2, float(np.linalg.cond(C)))

comparisons = []
def compare(label, owner, xs, ys, fixed):
    mean, covariance, condition = oracle(xs, ys, fixed)
    with torch.no_grad():
        posterior = owner._model.posterior(torch.tensor(queries, dtype=torch.float64), observation_noise=False)
        observed_mean = posterior.mean.detach().numpy().reshape(-1)
        observed_cov = posterior.distribution.covariance_matrix.detach().numpy()
    dmean = float(np.max(np.abs(mean-observed_mean)))
    dcov = float(np.max(np.abs(covariance-observed_cov)))
    result = {'label': label, 'matches': bool(np.allclose(mean, observed_mean, rtol=2e-7, atol=2e-8)
                                               and np.allclose(covariance, observed_cov, rtol=2e-7, atol=2e-8)),
              'oracle_mean': mean.tolist(), 'native_mean': observed_mean.tolist(),
              'oracle_latent_covariance': covariance.tolist(), 'native_latent_covariance': observed_cov.tolist(),
              'max_mean_absolute_error': dmean, 'max_covariance_absolute_error': dcov,
              'training_covariance_condition_number': condition, 'fit_calls_so_far': len(fits)}
    comparisons.append(result)
    print(json.dumps(result))
    return result['matches']

X0 = train_X.detach().numpy()
Y0 = train_Y.detach().numpy()
assert compare('original_fitted', strategy, X0, Y0, frozen)
state0 = strategy.get_state()
(out / 'initial-model-state.pt').write_bytes(state0.model_state)
restored0 = native.BayesianOptimizer(space, copy.deepcopy(cfg))
restored0.set_state(state0)
assert compare('restored_before_append', restored0, X0, Y0, frozen)
assert len(fits) == 1, 'restore itself must not fit'

newx = .93
newscore = 2 + math.sin(7*newx) + .2*newx
new = make_evaluation(candidate_id='synthetic-append', params={'x': 10*newx-5},
                      score=newscore, space=space)
new.provenance_ref = 'synthetic/gp-oracle/evaluation-append'
new.metadata = {'replicate_id': 'append', 'seed': 10,
                'warm_start_compatibility': dict(compatibility)}
expanded = [*evaluations, new]
strategy._iteration = len(expanded)
X1, Y1 = strategy._prepare_training_data(expanded)
strategy._fit_gp(X1, Y1)
preserved_parameters = all(torch.equal(v, dict(strategy._model.named_parameters())[n]) for n,v in params_before.items())
preserved_transforms = all(torch.equal(v, getattr(strategy._model, name).state_dict()[n])
                           for name, state in transform_before.items() for n,v in state.items())
append_matches = compare('native_append_frozen_basis', strategy, X1.detach().numpy(), Y1.detach().numpy(), frozen)
assert preserved_parameters and preserved_transforms
assert len(fits) == 1
assert append_matches != a.removal, 'matched conditioning removal must differ; unmodified source must match'

if not a.removal:
    state1 = strategy.get_state()
    (out / 'post-append-model-state.pt').write_bytes(state1.model_state)
    restored1 = native.BayesianOptimizer(space, copy.deepcopy(cfg))
    restored1.set_state(state1)
    restored_after_append_matches = compare('restored_after_append_frozen_basis', restored1,
                                             X1.detach().numpy(), Y1.detach().numpy(), frozen)
    calls_before_restored_append = len(fits)
    restored0._iteration = len(expanded)
    Xr, Yr = restored0._prepare_training_data(expanded)
    restored0._fit_gp(Xr, Yr)
    restored_append_extra_fits = len(fits)-calls_before_restored_append
    compare('restored_append_vs_original_frozen_basis', restored0, Xr.detach().numpy(), Yr.detach().numpy(), frozen)
    # Corrupt one independently specified input basis; markers/model unchanged.
    mutated_basis = dict(frozen, lengthscale=frozen['lengthscale'] * 1.7)
    assert not compare('oracle_lengthscale_substitution_negative', strategy,
                       X1.detach().numpy(), Y1.detach().numpy(), mutated_basis)
else:
    restored_after_append_matches = None
    restored_append_extra_fits = None

report = {'schema': 'policyos.orch04.gp-bounded-conformance.v1',
          'source_root': str(source), 'pid': os.getpid(),
          'python': sys.version, 'executable': sys.executable,
          'imports': {m.__name__: {'version': m.__version__, 'file':m.__file__} for m in (np,torch,botorch,gpytorch)},
          'native_import': native.__file__,
          'fixture': {'authority':'synthetic engineering witness only', 'physical_space':[-5.0,5.0],
                      'coordinates':coordinates, 'scores_minimize':scores,
                      'queries':queries.tolist(), 'append':{'x':newx,'score':newscore},
                      'warm_ids':[e.candidate_id for e in evaluations[:6]],
                      'current_ids':[e.candidate_id for e in evaluations[6:]],
                      'compatibility':compatibility},
          'basis':frozen, 'tolerance':{'rtol':2e-7,'atol':2e-8}, 'fit_calls':fits,
          'preserved_parameters_after_append':preserved_parameters,
          'preserved_transforms_after_append':preserved_transforms,
          'original_append_matches':append_matches,
          'restored_after_append_matches':restored_after_append_matches,
          'same_basis_restored_append_extra_fit_calls':restored_append_extra_fits,
          'conditioning_removal':a.removal, 'comparisons':comparisons,
          'limitations':['1D scalar GaussianLikelihood/ConstantMean/unit-amplitude RBF, ten plus one synthetic unique points',
                         'actual native genuine MLL fit; frozen fitted parameters from this fixture, not calibration/scientific authority',
                         'NumPy Cholesky reference limited to nondegenerate positive definite finite fixture',
                         'no production data, cross-backend bit identity, acquisition-quality/general law, transfer CAS bridge or authority proof']}
(out / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
print(json.dumps({k:report[k] for k in ('original_append_matches','restored_after_append_matches','same_basis_restored_append_extra_fit_calls','conditioning_removal')}))
if not a.removal and (not restored_after_append_matches or restored_append_extra_fits):
    sys.exit(1)
