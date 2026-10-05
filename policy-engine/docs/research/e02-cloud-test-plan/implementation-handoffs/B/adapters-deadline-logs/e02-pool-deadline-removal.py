from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
import runpy
import sys
import textwrap

from polisyos.fabric.connectors import pool

mode = sys.argv[1]
print(json.dumps({'mode': mode, 'module': pool.__file__, 'module_sha256': hashlib.sha256(Path(pool.__file__).read_bytes()).hexdigest(), 'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'scope': 'Isolated interpreter only; candidate source/docs/markers untouched, actual pool path executes with one property removed.'}), flush=True)
if mode == 'deadline':
    pool.ConnectionPool._raise_if_acquire_expired = lambda self, deadline: None
    runpy.run_path('/tmp/e02-pool-late-admission-probe.py', run_name='__main__')
elif mode == 'successful-registration':
    source = inspect.getsource(pool.ConnectionPool._acquire_owned_before_deadline)
    block = '                        self._active_acquires -= 1\n                        acquire_registered = False\n                        if self._active_acquires == 0:\n                            self._active_acquires_done.set()\n'
    assert source.count(block) == 1, 'exact candidate successful commit binding required'
    namespace = {}
    exec(textwrap.dedent(source.replace(block, '')), vars(pool), namespace)
    pool.ConnectionPool._acquire_owned_before_deadline = namespace['_acquire_owned_before_deadline']
    import pytest
    sys.exit(pytest.main(['-o', 'addopts=', '-q', '--tb=short', 'tests/unit/fabric/connectors/test_pool_e02.py::test_successful_acquire_does_not_await_metadata_after_publication']))
else:
    raise ValueError(mode)
