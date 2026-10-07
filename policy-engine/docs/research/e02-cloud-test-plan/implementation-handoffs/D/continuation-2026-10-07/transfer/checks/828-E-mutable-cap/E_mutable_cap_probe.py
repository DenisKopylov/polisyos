"""Bounded owner-input reproducer: mutable DOE cap at the public sampler."""
import hashlib
import importlib.metadata
import json
import platform
import sys
from polisyos.scientist.methods.doe.designs import SensitivityPlan, ParameterSpec, SensitivityMethod
from polisyos.scientist.methods.doe.sampling import generate_sensitivity_samples

plan = SensitivityPlan(method=SensitivityMethod.MORRIS,
    parameter_specs=[ParameterSpec(name='x', lower_bound=0.0, upper_bound=1.0)],
    n_trajectories=2, max_estimated_runs=5, seed=7)
initial = plan.model_dump(mode='json')
first = generate_sensitivity_samples(plan)
plan.n_trajectories = 5
second = generate_sensitivity_samples(plan)
print(json.dumps({
    'initial_plan': initial, 'consumed_mutated_plan': plan.model_dump(mode='json'),
    'initial_samples': first.tolist(), 'mutated_samples': second.tolist(),
    'estimated_runs': plan.estimated_runs, 'refused_before_materialization': False,
    'outcome': 'FAIL', 'criterion': 'consumed mutable cap is enforced before backend materialization',
    'source': '828283eefe9c3ae14e0f99899a0a502a8b1a253c',
    'backend': {'SALib': importlib.metadata.version('SALib'), 'numpy': importlib.metadata.version('numpy'),
                'python': sys.version, 'platform': platform.platform()},
    'module_path': sys.modules[generate_sensitivity_samples.__module__].__file__,
    'module_sha256': hashlib.sha256(open(sys.modules[generate_sensitivity_samples.__module__].__file__, 'rb').read()).hexdigest(),
    'authority_limit': 'finite declared Morris experiment; no production/population-law or E B100 closure claim',
}, indent=2))
