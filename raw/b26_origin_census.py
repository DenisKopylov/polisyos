from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

MODULES = (
    "polisyos.core.contracts.runtime",
    "polisyos.runtime.http.app",
    "polisyos.runtime.http.services.control.generation_cycle",
    "polisyos.runtime.quality.joint_simulation_horizon",
    "polisyos.runtime.http.routes.n5_interaction_diagnostics",
    "tests.unit.runtime.http.test_n5_interaction_diagnostics_api",
    "tests.unit.runtime.quality.test_n5_interaction_diagnostics_projection",
)


def pytest_sessionfinish(session, exitstatus):
    rows = []
    for name in MODULES:
        module = sys.modules.get(name)
        source = Path(module.__file__).resolve() if module and module.__file__ else None
        rows.append(
            {
                "module": name,
                "file": str(source) if source else None,
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest()
                if source and source.is_file()
                else None,
            }
        )
    destination = Path(os.environ["B26_ORIGIN_CENSUS_PATH"])
    destination.write_text(
        json.dumps(
            {
                "git_head": os.environ.get("B26_GIT_HEAD"),
                "cwd": os.getcwd(),
                "pythonpath": os.environ.get("PYTHONPATH"),
                "pytest_exitstatus": exitstatus,
                "modules": rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
