import subprocess
import sys

import pytest

import polisyos.calibration as calibration
import polisyos.calibration.continuous as continuous

source = subprocess.check_output(
    [
        "/usr/bin/git",
        "show",
        "6c80d1ac520e78a7b79d02402031c5a1673a6161:policy-engine/src/polisyos/calibration/continuous.py",
    ]
).decode()
# Remove the actual root-facade route by restoring the immutable old consumer bytes.
# The public facade, its names, test, rule and store implementation remain intact.
exec(compile(source, "<immutable-before-route-continuous>", "exec"), continuous.__dict__)  # noqa: S102 - Pinned immutable Git removal source.
for name in ("evaluate_continuous", "load_continuous_evaluation", "persist_continuous_evaluation"):
    setattr(calibration, name, getattr(continuous, name))
result = pytest.main(
    [
        "tests/unit/calibration/test_core_artifact_routes.py::test_actual_persistence_consumes_core_root_binding",
        "-q",
        "--junitxml=/workspace/e02-E-pr38-r3-receipts/imports-r4/core-route-removal.xml",
    ]
)
sys.stdout.write(f"property_removal_pytest_exit={result}\n")
sys.exit(result)
