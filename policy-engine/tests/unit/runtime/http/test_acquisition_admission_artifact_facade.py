"""Exercise the acquisition producer's actual artifact import boundary."""

from __future__ import annotations

import subprocess
import sys
import textwrap


def test_acquisition_producer_resolves_artifact_dependencies_through_facade() -> None:
    """Restoring private imports must fail even when all exported symbols remain."""
    probe = textwrap.dedent(
        """
        import builtins
        import importlib

        consumer = "polisyos.runtime.http.services.acquisition_admission_bundle"
        facade = "polisyos.core.artifacts"
        requests = []
        original_import = builtins.__import__

        def observed_import(name, globals=None, locals=None, fromlist=(), level=0):
            if (globals or {}).get("__name__") == consumer and (
                name == facade or name.startswith(facade + ".")
            ):
                requests.append(name)
            return original_import(name, globals, locals, fromlist, level)

        builtins.__import__ = observed_import
        importlib.import_module(consumer)
        assert requests, "The real consumer did not resolve its artifact dependencies"
        assert set(requests) == {facade}, requests
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
