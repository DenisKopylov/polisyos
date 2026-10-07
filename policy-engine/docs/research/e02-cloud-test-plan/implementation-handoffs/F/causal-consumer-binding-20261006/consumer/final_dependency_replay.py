"""Replay unchanged consumer tests with the explicitly configured real worker.

The repository test fixture requires a lane-local worker venv. This replay uses
the already provisioned locked worker interpreter; all application modules and
worker scripts remain the candidate's canonical files.
"""
import os
from pathlib import Path
import runpy
import tempfile
import pytest

os.environ['POLISYOS_DOWHY_WORKER_PYTHON'] = '/workspace/e02-F-dowhy-20261006/policy-engine/workers/dowhy-014/.venv/bin/python'
ns = runpy.run_path('tests/unit/foundry/methods/catalog/causal/test_gcm_backend_contract.py')
ns['test_public_source_bound_validation_facade_identity_invocation_and_pickle']()
print('PASS canonical public facade identity, invocation, pickle')
root = Path(tempfile.mkdtemp(prefix='e02-F-root-dependency-'))
with pytest.MonkeyPatch.context() as patch:
    ns['test_actual_query_consumer_binds_complete_cas_projection_and_original_request'](root, None, patch)
print('PASS actual GCM producer, CAS full-peer projection and original-request controls')
print(f'cleanup_candidate={root}')
