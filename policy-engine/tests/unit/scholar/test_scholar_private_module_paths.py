"""Prove the supported Scholar facade and reject retired deep module paths."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path


def test_supported_root_facade_and_retired_private_paths_in_clean_process() -> None:
    source_root = (Path.cwd() / "src").resolve()
    assert source_root.is_dir(), source_root
    child = textwrap.dedent(
        r"""
        import importlib
        import sys
        from pathlib import Path

        source_root = Path(sys.argv[1]).resolve()
        import polisyos
        import polisyos.scholar as scholar

        assert Path(polisyos.__file__).resolve().is_relative_to(source_root)
        assert Path(scholar.__file__).resolve().is_relative_to(source_root)
        assert all(Path(path).resolve().is_relative_to(source_root) for path in polisyos.__path__)
        assert len(scholar.__all__) == 30
        assert all(getattr(scholar, name) is not None for name in scholar.__all__)

        expected_class_owners = {
            **{
                name: "polisyos.scholar.orchestrator.errors"
                for name in (
                    "ScholarError",
                    "ScholarValidationError",
                    "ScholarDiscoverError",
                    "ScholarAcquireError",
                    "ScholarDocsError",
                    "ScholarClaimsError",
                    "ScholarReconcileError",
                    "ScholarBundleError",
                )
            },
            "ScholarPolicy": "polisyos.scholar.orchestrator.policies",
            "ScholarFabricCitation": "polisyos.scholar.orchestrator.provenance",
            "KnowledgeBundlePayloadV1": "polisyos.core.contracts.scholar",
            "EnrichmentReportV1": "polisyos.core.contracts.scholar",
            "EnrichResultV1": "polisyos.core.contracts.scholar",
        }
        assert len(expected_class_owners) == 13
        for name, module_name in expected_class_owners.items():
            value = getattr(scholar, name)
            assert value.__module__ == module_name, (name, value.__module__)
            owner = importlib.import_module(module_name)
            assert Path(owner.__file__).resolve().is_relative_to(source_root)

        core_scholar = importlib.import_module("polisyos.core.contracts.scholar")
        for name in ("KnowledgeBundlePayloadV1", "EnrichmentReportV1", "EnrichResultV1"):
            assert getattr(scholar, name) is getattr(core_scholar, name)

        retired_modules = (
            "polisyos.scholar.errors",
            "polisyos.scholar.freshness",
            "polisyos.scholar.freshness_store",
            "polisyos.scholar.policies",
            "polisyos.scholar.provenance",
            "polisyos.scholar.types",
        )
        for module_name in retired_modules:
            try:
                importlib.import_module(module_name)
            except ModuleNotFoundError as error:
                assert error.name == module_name, (module_name, error.name)
            else:
                raise AssertionError(f"retired private module unexpectedly imports: {module_name}")
            assert module_name not in sys.modules
        """
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(source_root)
    completed = subprocess.run(
        [sys.executable, "-c", child, str(source_root)],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, (
        f"clean-process Scholar facade check failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )
