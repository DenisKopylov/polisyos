"""Remove actual monitor properties in memory while preserving public markers."""
from __future__ import annotations

import inspect
import json
from pathlib import Path
import sys

import pytest

from polisyos.foundry.methods.backends import dispatch
from polisyos.foundry.methods.lifecycle.output_monitor import MethodOutputMonitor

mode = sys.argv[1]
TEST = 'tests/unit/foundry/methods/backends/test_output_anomaly_count.py'
if mode == 'no_consumption':
    target = dispatch._consumed_raw_output_keys
    def replacement(*, method_class, signature, raw_output, slot_outputs):
        return frozenset()
    selection = 'nan_inf_vector and consumed_source'
elif mode == 'no_sidecars':
    target = MethodOutputMonitor.check_output_contract
    def replacement(self, *, slot_outputs, raw_output, expected_keys=None,
                    array_keys=frozenset(), consumed_raw_keys=frozenset()):
        return self.check_basic(dict(slot_outputs), expected_keys=expected_keys)
    selection = 'nan_inf_vector and distinct_sidecar'
elif mode == 'broad_identity_skip':
    target = dispatch._consumed_raw_output_keys
    def replacement(*, method_class, signature, raw_output, slot_outputs):
        if not isinstance(raw_output, Mapping):
            return frozenset({'output'})
        return frozenset(key for key, value in raw_output.items()
                         if any(value is canonical for canonical in slot_outputs.values()))
    selection = 'unused_alias_retains_anomalies'
else:
    raise ValueError(mode)

before = {'id': id(target), 'name': target.__name__, 'qualname': target.__qualname__,
          'module': target.__module__, 'doc': target.__doc__,
          'signature': str(inspect.signature(target)), 'annotations': repr(target.__annotations__)}
original_code = target.__code__
target.__code__ = replacement.__code__
after = {'id': id(target), 'name': target.__name__, 'qualname': target.__qualname__,
         'module': target.__module__, 'doc': target.__doc__,
         'signature': str(inspect.signature(target)), 'annotations': repr(target.__annotations__)}
assert before == after, (before, after)
print(json.dumps({'property_removal': mode, 'markers_preserved': before,
                  'code_changed': target.__code__ is not original_code}, sort_keys=True))
try:
    code = pytest.main([TEST, '-k', selection, '-o', 'addopts=', '-p', 'no:cacheprovider',
                       '-q', '-s', '--tb=short',
                       '--basetemp=' + str(Path(__file__).parent / ('removal-' + mode + '-tmp'))])
finally:
    target.__code__ = original_code
raise SystemExit(code)
