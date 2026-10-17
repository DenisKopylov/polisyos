from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_normpack_reads_fabric_owner_and_retired_lex_factlog_is_not_importable() -> None:
    script = """
import importlib
import json
import sys
from polisyos.fabric.world import load_world_facts
from polisyos.lex.normpack import select_sources
try:
    importlib.import_module("polisyos.lex.factlog")
except ModuleNotFoundError:
    legacy_importable = False
else:
    legacy_importable = True
print(json.dumps({
    "legacy_importable": legacy_importable,
    "same_reader": select_sources.load_world_facts is load_world_facts,
    "reader_module": select_sources.load_world_facts.__module__,
    "legacy_loaded": "polisyos.lex.factlog" in sys.modules,
}))
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-B", "-c", script],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "legacy_importable": False,
        "same_reader": True,
        "reader_module": "polisyos.fabric.world.store.segments",
        "legacy_loaded": False,
    }
