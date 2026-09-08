"""Actual N8 default configuration serialization witness, no world builder."""
from __future__ import annotations

import json

from polisyos.runtime.quality.generation_cycle import FoundryValuePort, _select_value_method
from tests.unit.runtime.http.test_control_service_di import _explicit_simulation_execution_context
from tests.unit.runtime.quality.test_generation_cycle import _problem

port = FoundryValuePort(evaluation_context=_explicit_simulation_execution_context(_problem()))
inputs = port._selection_inputs()
actual = _select_value_method(candidate={}, problem={}, inputs=inputs)
manual_absence = _select_value_method(candidate={}, problem={}, inputs={})
print(json.dumps({
    'constructor_manifest_argument': 'omitted',
    'actual_owner_selection_inputs': inputs,
    'actual_default_status': actual['status'],
    'actual_default_blockers': actual.get('blockers'),
    'manual_absence_status': manual_absence['status'],
    'manual_absence_method': manual_absence.get('selected_method_fqn'),
}, indent=2))
assert 'observation_to_contract_manifest' in inputs
assert inputs['observation_to_contract_manifest'] is None
assert actual['status'] == 'blocked'
assert actual['blockers'] == ('value_method_manifest_source_invalid',)
assert manual_absence['status'] == 'selected'
