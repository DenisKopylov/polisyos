"""Cold-import and ownership checks for the causal methods facade."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_causal_facade_metadata_is_lightweight_and_matches_runtime_exports() -> None:
    """Load names without catalog code, then resolve every name through its owner."""
    product_root = Path(__file__).resolve().parents[5]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(product_root / "src"), environment.get("PYTHONPATH", "")) if part
    )
    probe = """
import importlib
import sys

package = importlib.import_module("polisyos.foundry.methods.causal")
metadata = importlib.import_module("polisyos.foundry.methods.causal._exports")
names = metadata.CAUSAL_METHOD_EXPORTS
assert isinstance(names, tuple)
assert package.__all__ is names
assert "AIPWEstimator" in names
assert "AIPWEstimator" not in vars(package)
assert "polisyos.foundry.methods.causal._facade" not in sys.modules
assert "polisyos.foundry.methods.catalog.causal" not in sys.modules

first_export = package.AIPWEstimator
facade = sys.modules["polisyos.foundry.methods.causal._facade"]
assert facade.__all__ is names
assert first_export is facade.AIPWEstimator
for name in names:
    assert name in vars(facade), name
    assert getattr(package, name) is getattr(facade, name), name
"""
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=product_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
