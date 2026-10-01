"""Behavioral witnesses for the lazy runtime control package boundary."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
CONTROL_PACKAGE_NAME = "polisyos.runtime.http.services.control"
CONTROL_API_NAME = f"{CONTROL_PACKAGE_NAME}.api"
CONTROL_RESPONSE_SHAPES_NAME = f"{CONTROL_PACKAGE_NAME}.response_shapes"
CONTROL_PACKAGE_DIR = (
    REPO_ROOT / "src" / "polisyos" / "runtime" / "http" / "services" / "control"
)


def _run_fresh_python(source: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        value
        for value in (
            str(REPO_ROOT / "src"),
            str(REPO_ROOT),
            env.get("PYTHONPATH", ""),
        )
        if value
    )
    env["POLISYOS_CONTROL_PACKAGE_DIR"] = str(CONTROL_PACKAGE_DIR)
    env["POLISYOS_SOURCE_ROOT"] = str(REPO_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=False,
        text=True,
        timeout=90,
    )


def test_store_first_import_keeps_child_owner_without_loading_public_api() -> None:
    result = _run_fresh_python(
        f"""
        import importlib
        import os
        import sys
        from pathlib import Path

        from polisyos.runtime.http.services.control_plane_store import (
            AcquisitionActionHeadRecord,
            ControlPlaneStore,
        )

        api_name = {CONTROL_API_NAME!r}
        assert api_name not in sys.modules

        response_shapes = importlib.import_module(
            {CONTROL_RESPONSE_SHAPES_NAME!r}
        )
        store = importlib.import_module(
            "polisyos.runtime.http.services.control_plane_store"
        )
        expected_source_root = Path(os.environ["POLISYOS_SOURCE_ROOT"]).resolve()
        assert Path(store.__file__).resolve().is_relative_to(expected_source_root)
        assert Path(response_shapes.__file__).resolve().is_relative_to(expected_source_root)
        assert AcquisitionActionHeadRecord.__module__ == store.__name__
        assert ControlPlaneStore.__module__ == store.__name__
        assert (
            store._operator_diagnostic_from_failure_payload
            is response_shapes._operator_diagnostic_from_failure_payload
        )
        assert (
            store._operator_diagnostic_from_quality_payload
            is response_shapes._operator_diagnostic_from_quality_payload
        )
        assert store.build_control_job_projection_shape is (
            response_shapes.build_control_job_projection_shape
        )
        assert api_name not in sys.modules
        """
    )

    assert result.returncode == 0, result.stderr


def test_public_facade_preserves_api_symbol_and_all_identity() -> None:
    result = _run_fresh_python(
        f"""
        import importlib
        import os
        import sys
        from pathlib import Path

        package = importlib.import_module({CONTROL_PACKAGE_NAME!r})
        api_name = {CONTROL_API_NAME!r}
        assert api_name not in sys.modules

        from polisyos.runtime.http.services.control import ControlPlaneService

        api = importlib.import_module(api_name)
        expected_source_root = Path(os.environ["POLISYOS_SOURCE_ROOT"]).resolve()
        assert Path(package.__file__).resolve().is_relative_to(expected_source_root)
        assert Path(api.__file__).resolve().is_relative_to(expected_source_root)
        assert ControlPlaneService is api.ControlPlaneService
        assert package.__all__ is api.__all__
        assert all(
            getattr(package, name) is getattr(api, name)
            for name in api.__all__
        )
        from types import ModuleType

        assert all(
            not isinstance(getattr(api, name), ModuleType)
            for name in api.__all__
        )
        assert "artifacts" not in api.__all__
        assert not hasattr(api, "artifacts")
        artifact_child = importlib.import_module(
            f"{CONTROL_PACKAGE_NAME}.artifacts"
        )
        assert package.artifacts is artifact_child
        assert artifact_child.__name__ == f"{CONTROL_PACKAGE_NAME}.artifacts"
        """
    )

    assert result.returncode == 0, result.stderr


def test_eager_api_initialization_removal_mutant_reopens_store_cycle() -> None:
    result = _run_fresh_python(
        f"""
        import importlib.abc
        import importlib.util
        import os
        import sys
        from pathlib import Path

        package_name = {CONTROL_PACKAGE_NAME!r}
        package_dir = Path(os.environ["POLISYOS_CONTROL_PACKAGE_DIR"])
        initializer = package_dir / "__init__.py"

        class EagerFacadeLoader:
            def create_module(self, spec):
                del spec
                return None

            def exec_module(self, module):
                source = initializer.read_text(encoding="utf-8")
                mutant = source + "\\nfrom .api import *\\n"
                exec(compile(mutant, str(initializer), "exec"), module.__dict__)

        class EagerFacadeFinder(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                del path, target
                if fullname != package_name:
                    return None
                spec = importlib.util.spec_from_file_location(
                    fullname,
                    initializer,
                    submodule_search_locations=[str(package_dir)],
                )
                assert spec is not None
                spec.loader = EagerFacadeLoader()
                return spec

        sys.meta_path.insert(0, EagerFacadeFinder())
        try:
            from polisyos.runtime.http.services.control_plane_store import (
                AcquisitionActionHeadRecord,
            )
        except ImportError as exc:
            message = str(exc)
            assert "AcquisitionActionHeadRecord" in message, message
            assert "partially initialized module" in message, message
        else:
            raise AssertionError(
                "eager API initialization no longer exposes the partial-store cycle"
            )
        """
    )

    assert result.returncode == 0, result.stderr
