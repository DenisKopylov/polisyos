"""Independent S3 real-manifest field-removal witness; read-only owner inputs."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from polisyos.runtime.quality import generation_cycle
from polisyos.runtime.quality.intervention_substrate import load_l6_intervention_substrate

bundle = load_l6_intervention_substrate(Path.cwd())
real = bundle.observation_manifest
missing_routes = copy.deepcopy(real)
del missing_routes['routes']
null_routes = {**real, 'routes': None}
variants = {'absent': None, 'real': real, 'missing_routes': missing_routes, 'null_routes': null_routes}
results = {}
for name, manifest in variants.items():
    inputs = {'observation_family': 'budget_flows'}
    if manifest is not None:
        inputs['observation_to_contract_manifest'] = manifest
    result = generation_cycle._select_value_method(candidate={}, problem={}, inputs=inputs)
    results[name] = {'status': result.get('status'), 'selected_method_fqn': result.get('selected_method_fqn'), 'blockers': result.get('blockers'), 'selection_context_hash': result.get('selection_receipt', {}).get('selection_context_hash'), 'source_keys': sorted(manifest) if manifest is not None else None}
print(json.dumps(results, indent=2))
assert results['real']['status'] == 'selected'
assert results['null_routes']['status'] == 'blocked'
assert results['missing_routes']['status'] == 'selected'
assert results['missing_routes']['selected_method_fqn'] == results['absent']['selected_method_fqn']
