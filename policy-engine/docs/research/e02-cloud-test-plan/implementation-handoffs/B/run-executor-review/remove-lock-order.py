"""Remove only the admission/base-lock separation for the real lock oracle."""
from __future__ import annotations

import runpy
import sys
from polisyos.common import async_tools

original_submit = async_tools._SharedExecutor.submit

def submit_under_admission(self, fn, /, *args, **kwargs):
    with self._admission_lock:
        return original_submit(self, fn, *args, **kwargs)

async_tools._SharedExecutor.submit = submit_under_admission
probe_path = sys.argv[1]
sys.argv = [probe_path, '--child', 'shutdown-submit']
runpy.run_path(probe_path, run_name='__main__')
