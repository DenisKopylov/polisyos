from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
from fractions import Fraction

import numpy as np

from polisyos.core.artifacts.ir_adapter import build_ir_artifact_store
from polisyos.foundry.uncertainty.config import AdaptiveStoppingConfig, PropagationConfig
from polisyos.foundry.uncertainty import monte_carlo as mc_module
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily, IntervalSemantics, ParametricFitCarrier,
    PosteriorSamplesCarrier, PropagationMethod, UncertaintyEnvelope,
    UncertaintySource, load_uncertainty_envelope, persist_uncertainty_envelope,
)

HERE = Path(__file__).resolve().parent
LANE = Path('/dev/shm/e02-orch03-20261008/c09')
SOURCE = LANE / 'policy-engine/src'
FREEZE = '1b8c9e1c84d9f2e86d4b0900bf5aa54515487747'
records = []
child_refs = []
start = time.monotonic()

def normal(std=1.0, metadata=None):
    return UncertaintyEnvelope(
        point_estimate=0., confidence_interval=(-2., 2.),
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        distribution_payload=ParametricFitCarrier(
            family=DistributionFamily.NORMAL, parameters={'mean': 0., 'std': std}),
        metadata={} if metadata is None else metadata, gate_eligible=False,
    )

def fraction_se(samples):
    xs = [Fraction.from_float(float(x)) for x in samples]
    if len(xs) < 2:
        return None, None
    mean = sum(xs) / len(xs)
    sq = sum((x - mean) ** 2 for x in xs) / (len(xs) * (len(xs) - 1))
    return math.sqrt(float(sq)), str(sq)

def sign(x=0.):
    return {'y': -1. if x < 0. else 1.}

def actual(name, *, env=None, cfg=None, fn=sign, removal=False):
    env = normal() if env is None else env
    cfg = PropagationConfig(mc_n_samples=100, mc_seed=61) if cfg is None else cfg
    t0 = time.monotonic()
    produced = mc_module.MonteCarloPropagator(cfg).propagate(fn, {'x': 0.}, {'x': env}, ['y'])[0]
    cas_root = HERE / name / 'cas'
    ref = persist_uncertainty_envelope(build_ir_artifact_store(cas_root), produced.envelope)
    reopened = load_uncertainty_envelope(build_ir_artifact_store(cas_root), ref)
    assert reopened.model_dump(mode='json') == produced.envelope.model_dump(mode='json')
    diagnostic = reopened.metadata['mean_estimator_error']
    assert diagnostic['gate_eligible'] is False
    assert reopened.gate_eligible is False
    payload = reopened.distribution_payload
    xs = list(payload.samples) if isinstance(payload, PosteriorSamplesCarrier) else []
    expected, exact_squared = fraction_se(xs)
    digest = hashlib.sha256(json.dumps(xs, allow_nan=False, separators=(',', ':')).encode()).hexdigest()
    row = {
        'name': name, 'source_sha': FREEZE, 'surface': 'actual_MonteCarloPropagator_persist_freshCAS',
        'removal': removal, 'input': env.model_dump(mode='json'),
        'configuration': cfg.model_dump(mode='json'), 'reference': ref.model_dump(mode='json'),
        'cas_root': str(cas_root), 'finite_samples': xs, 'sample_sha256': digest,
        'fraction_expected_se': expected, 'fraction_se_squared': exact_squared,
        'mean_estimator_error': diagnostic, 'result_diagnostics': produced.diagnostics,
        'output_gate_eligible': reopened.gate_eligible, 'mc_std': reopened.metadata.get('mc_std'),
        'body_seconds': time.monotonic() - t0,
    }
    records.append(row)
    child_refs.append({'name': name, 'reference': ref.model_dump(mode='json'), 'cas_root': str(cas_root),
                       'sample_sha256': digest, 'diagnostic': diagnostic})
    return row

positive = actual('typed_normal_100')
assert positive['mean_estimator_error']['status'] == 'conditional_estimate'
assert math.isclose(positive['mean_estimator_error']['standard_error'], positive['fraction_expected_se'], rel_tol=1e-12)
assert positive['mean_estimator_error']['requested_draw_count'] == positive['mean_estimator_error']['attempted_draw_count'] == positive['mean_estimator_error']['finite_output_count'] == 100
assert positive['mean_estimator_error']['assumptions_verified'] is False
assert positive['mean_estimator_error']['source_law_authority'] == 'not_established'
assert positive['mean_estimator_error']['standard_error'] < positive['mc_std'] / 5

repeat = actual('same_seed_repeat')
assert repeat['sample_sha256'] == positive['sample_sha256']
assert repeat['mean_estimator_error'] == positive['mean_estimator_error']

more = actual('typed_normal_400', cfg=PropagationConfig(mc_n_samples=400, mc_seed=61))
assert more['mean_estimator_error']['finite_output_count'] == 400
assert math.isclose(more['mean_estimator_error']['standard_error'], more['fraction_expected_se'], rel_tol=1e-12)
# This tests exact corpus arithmetic, not an IID population coverage guarantee.
assert more['mean_estimator_error']['standard_error'] < positive['mean_estimator_error']['standard_error']

weighted = normal(metadata={'iid': True, 'sampling_law': 'independent_normal'}).model_copy(update={
    'distribution_family': DistributionFamily.BOOTSTRAP,
    'distribution_payload': PosteriorSamplesCarrier(samples=(-1., 1.), weights=(0.85, 0.15), sample_axis='draw'),
})
weighted_row = actual('weighted_fake_iid', env=weighted)
assert weighted_row['mean_estimator_error']['status'] == 'unavailable'
assert weighted_row['mean_estimator_error']['standard_error'] is None
assert weighted_row['mean_estimator_error']['reason'] == 'unsupported_input_sampling_law'

qmc_cfg = PropagationConfig(mc_n_samples=100, mc_seed=61, mc_sampling_method='sobol', mc_qmc_scramble=True, mc_qmc_replicates=2)
qmc_row = actual('qmc_two_scrambles_pooled', cfg=qmc_cfg)
assert qmc_row['mean_estimator_error']['status'] == 'unavailable'
assert qmc_row['mean_estimator_error']['standard_error'] is None
assert qmc_row['mean_estimator_error']['reason'] == 'qmc_replica_means_not_retained'

def one_success_fn():
    calls = 0
    def callback(x=0.):
        nonlocal calls
        calls += 1
        return {'y': 3. if calls <= 2 else float('nan')}
    return callback

one = actual('one_success_100_attempts', fn=one_success_fn())
assert one['mean_estimator_error']['finite_output_count'] == 1
assert one['mean_estimator_error']['requested_draw_count'] == one['mean_estimator_error']['attempted_draw_count'] == 100
assert one['mean_estimator_error']['status'] == 'unavailable'
assert one['mean_estimator_error']['standard_error'] is None
assert one['mean_estimator_error']['reason'] == 'insufficient_independent_draws'
assert one['result_diagnostics']['n_failed'] == 99

fake = actual('counterfeit_mean_error', env=normal(metadata={'mean_estimator_error': {'status': 'admitted', 'standard_error': 999., 'gate_eligible': True}}))
assert fake['mean_estimator_error']['status'] == 'conditional_estimate'
assert math.isclose(fake['mean_estimator_error']['standard_error'], fake['fraction_expected_se'], rel_tol=1e-12)
assert fake['mean_estimator_error']['assumptions_verified'] is False

# Remove only runtime law/count guards, retain enum strings, scope, input identities,
# provenance and all non-gating/assumption markers. Never mutate live source files.
original = mc_module._mean_estimator_error
def removal(values, **kwargs):
    result = original(values, **kwargs)
    n = int(values.size)
    result.update(status='conditional_estimate', reason=None,
                  standard_error=float(np.std(values, dtype=np.float64, ddof=1) / math.sqrt(n)) if n >= 2 else 0.,
                  formula='sample_standard_deviation_ddof1/sqrt(n)')
    return result

mc_module._mean_estimator_error = removal
try:
    for name, env, cfg, fn in [
        ('removed_guard_weighted', weighted, None, sign),
        ('removed_guard_qmc', None, qmc_cfg, sign),
        ('removed_guard_one_success', None, None, one_success_fn()),
    ]:
        row = actual(name, env=env, cfg=cfg, fn=fn, removal=True)
        d = row['mean_estimator_error']
        assert d['assumptions_verified'] is False and d['source_law_authority'] == 'not_established'
        assert d['sampling_law'] == 'implemented_product_of_typed_normal_fits'
        try:
            assert d['status'] == 'unavailable' and d['standard_error'] is None, 'runtime eligibility discriminator rejected property removal'
        except AssertionError as exc:
            row['discriminator_result'] = 'EXPECTED_FAIL'
            row['discriminator_message'] = str(exc)
        else:
            raise AssertionError('retained-marker discriminator failed to detect guard removal')
    ordinary = actual('removed_guard_supported_positive', removal=True)
    assert math.isclose(ordinary['mean_estimator_error']['standard_error'], ordinary['fraction_expected_se'], rel_tol=1e-12)
    ordinary['discriminator_result'] = 'PASS ordinary supported profile remains executable'
finally:
    mc_module._mean_estimator_error = original

(HERE / 'child-inputs.json').write_text(json.dumps(child_refs, sort_keys=True, indent=2))
cmd = [sys.executable, str(HERE / 'fresh-child.py')]
ct = time.monotonic()
child = subprocess.run(cmd, capture_output=True, text=True, env=os.environ.copy())
child_seconds = time.monotonic() - ct
(HERE / 'fresh-child.stdout.json').write_text(child.stdout)
(HERE / 'fresh-child.stderr.txt').write_text(child.stderr)
assert child.returncode == 0, child.stderr
child_summary = json.loads(child.stdout)
assert child_summary['ref_count'] == len(child_refs)

# Record all actually imported maintained module source identities against the
# immutable candidate, not a claim about every possible dynamic import.
origins = []
for name, module in sorted(sys.modules.items()):
    if not name.startswith('polisyos') or not getattr(module, '__file__', None):
        continue
    p = Path(module.__file__).resolve()
    if p.suffix != '.py':
        continue
    assert p.is_relative_to(SOURCE), str(p)
    rel = p.relative_to(LANE).as_posix()
    expected = subprocess.run(['git', 'rev-parse', f'{FREEZE}:{rel}'], cwd=LANE, capture_output=True, text=True, check=True).stdout.strip()
    actual_blob = hashlib.sha1(b'blob ' + str(p.stat().st_size).encode() + b'\0' + p.read_bytes()).hexdigest()
    assert actual_blob == expected, (name, rel)
    origins.append({'module': name, 'path': str(p), 'git_blob': actual_blob,
                    'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
(HERE / 'loaded-module-origins.json').write_text(json.dumps(origins, sort_keys=True, indent=2))
print(json.dumps({
    'source_sha': FREEZE, 'source_tree': '7a4ee9e71c793827abef998540dcd12ab129c4ba',
    'parent_sha': '514f90058104f7dd8ada1c83b8bf5f62bfc33b88',
    'python': sys.version, 'executable': sys.executable, 'pid': os.getpid(),
    'packages': {p: importlib.metadata.version(p) for p in ['numpy', 'jax', 'scipy', 'pydantic']},
    'producer': mc_module.__file__, 'records': records,
    'positive_native_reports': 7, 'guard_removal_expected_fail': 3,
    'removal_supported_control_pass': 1, 'fresh_child_refs': len(child_refs),
    'fresh_child_command': cmd, 'fresh_child_exit': child.returncode,
    'fresh_child_seconds': child_seconds,
    'loaded_module_count': len(origins), 'loaded_module_mismatches': 0,
    'body_seconds': time.monotonic() - start,
    'max_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    'status': 'PASS bounded numerical production/CAS checks; conditional assumptions unverified; no authority or whole B21 closure',
}, sort_keys=True, indent=2, allow_nan=False))
