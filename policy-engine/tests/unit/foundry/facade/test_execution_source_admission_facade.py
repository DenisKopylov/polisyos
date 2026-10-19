from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("import_order", ["submodule_first", "facade_first"])
def test_execution_source_admission_resolves_to_owner_and_preserves_execute_identity(
    import_order: str,
) -> None:
    policy_engine_root = Path(__file__).resolve().parents[4]
    source_root = policy_engine_root / "src"
    env = dict(os.environ)
    prior_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(source_root)
        if not prior_pythonpath
        else os.pathsep.join((str(source_root), prior_pythonpath))
    )
    script = """
import importlib
import sys

order = sys.argv[1]
if order == "submodule_first":
    owner = importlib.import_module("polisyos.foundry.execute.api")
    facade = importlib.import_module("polisyos.foundry.execute")
else:
    facade = importlib.import_module("polisyos.foundry.execute")
    assert facade.admit_execution_source.__module__ == "polisyos.foundry.execute.api"
    owner = importlib.import_module("polisyos.foundry.execute.api")

assert facade.admit_execution_source is owner.admit_execution_source
assert facade.ExecutionSourceAdmission is owner.ExecutionSourceAdmission
assert facade.ExecutionSourceAdmissionRefusal is owner.ExecutionSourceAdmissionRefusal
assert facade.execute is owner.execute
assert callable(facade)

core = importlib.import_module("polisyos.core.artifacts")
trinity = importlib.import_module("polisyos.ir.trinity")
assert owner._require_return_selected_profile_writer is core.require_return_selected_profile_writer
assert owner.load_trinity_bundle_artifact is trinity.load_trinity_bundle_artifact
"""
    result = subprocess.run(
        [sys.executable, "-c", script, import_order],
        cwd=policy_engine_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
