"""Source-derived manifest routing configuration witness for the actual N8 port."""
from __future__ import annotations

import inspect
import json
from pathlib import Path

from polisyos.runtime.quality.generation_cycle import FoundryValuePort, _select_value_method
from polisyos.runtime.quality.intervention_substrate import load_l6_intervention_substrate
from tests.unit.runtime.http.test_control_service_di import _explicit_simulation_execution_context
from tests.unit.runtime.quality.test_generation_cycle import _problem

problem = _problem()
source = load_l6_intervention_substrate(Path.cwd()).observation_manifest
context = _explicit_simulation_execution_context(problem)
port = FoundryValuePort(evaluation_context=context, observation_to_contract_manifest=source)
inputs = port._selection_inputs()
actual = _select_value_method(candidate={}, problem=problem, inputs=inputs)
owner_selected = _select_value_method(candidate={}, problem=problem,
    inputs={**inputs, 'observation_family': 'budget_flows'})
try:
    FoundryValuePort(evaluation_context=context, observation_to_contract_manifest=source,
        observation_family='budget_flows')
except TypeError as exc:
    config_error = str(exc)
else:
    config_error = None
print(json.dumps({
    'actual_port_constructor_signature': str(inspect.signature(FoundryValuePort)),
    'actual_selection_input_keys': sorted(inputs),
    'actual_problem_outcome': problem.outcome_of_interest.target_variable,
    'actual_port_source_status': actual['status'],
    'actual_port_source_blockers': actual.get('blockers'),
    'explicit_family_constructor_error': config_error,
    'manual_helper_owner_family_status': owner_selected['status'],
    'manual_helper_owner_family_method': owner_selected.get('selected_method_fqn'),
    'scope': 'Real source manifest; actual port config/serialization; fixture problem only, no candidate/promotion receipt construction',
}, indent=2))
assert actual['status'] == 'blocked'
assert actual['blockers'] == ('observation_family_missing',)
assert config_error is not None
assert owner_selected['status'] == 'selected'
