from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests._helpers.mirror_contracts import assert_source_stem_has_static_contract

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_factlog_source_modules_have_static_contracts() -> None:
    assert_source_stem_has_static_contract('lex', 'factlog')


def test_lex_factlog_facade_preserves_fabric_reader_identity() -> None:
    from polisyos.fabric.world import load_world_facts as fabric_load_world_facts
    from polisyos.lex.factlog import load_world_facts as legacy_load_world_facts

    assert legacy_load_world_facts is fabric_load_world_facts


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
