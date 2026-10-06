"""Isolated real descriptor-exhaustion input; retain the original traceback."""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import resource
import sys
from pathlib import Path

from polisyos.scientist.orchestration.engine import retry
from polisyos.scientist.orchestration.engine.state import ExperimentState

mode, preparation, effects = sys.argv[1:]
if preparation in {"synchronize", "shared"}:
    importlib.import_module("multiprocessing.synchronize")
if preparation == "shared":
    importlib.import_module("multiprocessing.sharedctypes")
    warm_value = retry.mp.get_context("fork").Value("d", 0.0)


def descriptors():
    values = []
    for descriptor in range(256):
        try:
            os.fstat(descriptor)
        except OSError:
            continue
        values.append(descriptor)
    return values


class Node:
    def execute(self, _ctx, state):
        Path(effects).write_text("physical body executed")
        return retry.NodeOutcome(status="ok", state=state)


loop = asyncio.new_event_loop() if mode == "async" else None
before = descriptors()
original = resource.getrlimit(resource.RLIMIT_NOFILE)
soft = max(before) + 3
retained = []
try:
    resource.setrlimit(resource.RLIMIT_NOFILE, (soft, original[1]))
    kwargs = {"timeout_s": 0.1, "authority": retry._AttemptAuthority()}
    state = ExperimentState(run_id="R_actual_setup_fault")
    if mode == "async":
        loop.run_until_complete(
            retry._execute_with_timeout_process_async(Node(), None, state, **kwargs)
        )
    else:
        retry._execute_with_timeout_process(Node(), None, state, **kwargs)
except BaseException as exc:
    retained.append(exc)
    failure = {
        "type": type(exc).__name__,
        "errno": getattr(exc, "errno", None),
        "message": str(exc),
    }
finally:
    resource.setrlimit(resource.RLIMIT_NOFILE, original)
after = descriptors()
print(
    json.dumps(
        {
            "mode": mode,
            "preparation": preparation,
            "before": before,
            "after": after,
            "new_descriptors": sorted(set(after) - set(before)),
            "fault_limit": soft,
            "failure": failure,
            "body_effect": Path(effects).exists(),
            "retained_exception": bool(retained),
        }
    )
)

if loop is not None:
    loop.close()
