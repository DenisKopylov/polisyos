from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_retired_lex_factlog_module_fails_in_a_fresh_interpreter() -> None:
    """The removed Lex facade cannot shadow the Fabric reader owner."""

    module_name = "polisyos.lex." + "factlog"
    probe = """
import importlib
import sys

name = sys.argv[1]
try:
    importlib.import_module(name)
except ModuleNotFoundError as exc:
    assert exc.name == name
else:
    raise AssertionError(f"retired module still resolves: {name}")
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-c", probe, module_name],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_normpack_reader_imports_fabric_owner_without_legacy_factlog() -> None:
    """Internal NormPack reads must bind the canonical Fabric owner directly."""

    script = """
        import json
        import sys

        from polisyos.lex.normpack import select_sources

        print(
            json.dumps(
                {
                    "legacy_loaded": "polisyos.lex.factlog" in sys.modules,
                    "fabric_loaded": "polisyos.fabric.world" in sys.modules,
                    "reader_module": select_sources.load_world_facts.__module__,
                }
            )
        )
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {
        "legacy_loaded": False,
        "fabric_loaded": True,
        "reader_module": "polisyos.fabric.world.store.segments",
    }
