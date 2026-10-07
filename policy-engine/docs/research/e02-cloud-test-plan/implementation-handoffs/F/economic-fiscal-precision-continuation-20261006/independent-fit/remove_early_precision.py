"""Remove receiving-dtype precision while retaining the true fiscal owner/markers."""
from functools import wraps
import inspect
import json
import os
from pathlib import Path
import jax.numpy as jnp
import pytest
from polisyos.foundry.execute.mechanisms import fiscal

original = fiscal._validate_rate
@wraps(original)
def forced32(rate, *, label='rate', dtype=jnp.float32):
    return original(rate, label=label, dtype=jnp.float32)

fiscal._validate_rate = forced32
print('REMOVED_PROPERTY', json.dumps({'source_sha': os.environ['FISCAL_REVIEW_SHA'],
    'removed': 'precise source/receiving dtype before multiply; force old float32 conversion',
    'retained': ['canonical classes', 'registered mechanism IDs', 'Decimal policy source',
                 'compiler/CAS/state slots', 'public rate field', 'validation/helper signature',
                 'fidelity', 'whole source Git bytes'],
    'signature': str(inspect.signature(fiscal._validate_rate)), 'source_files_written': False}))
file = Path(__file__).with_name('test_fiscal_independent.py')
raise SystemExit(pytest.main([str(file) + '::test_decimal_policy_compiler_native_execution_and_fresh_process_state[income_tax]',
    '-o', 'addopts=', '-p', 'no:cacheprovider', '-q', '-s', '--tb=short',
    '--basetemp=' + str(Path(__file__).parent / 'removal-tmp')]))
