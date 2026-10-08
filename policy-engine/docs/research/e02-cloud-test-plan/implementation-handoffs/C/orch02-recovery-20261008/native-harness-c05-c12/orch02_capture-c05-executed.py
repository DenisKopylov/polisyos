"""Record native/backend origins and relocate only pytest's hypothesis cache."""
from __future__ import annotations

import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import sys

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    # The repository otherwise hardcodes a mutable source-local hypothesis cache.
    # Preserve the test profile but place that cache beside this run's basetemp.
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", "") or ""
        if filename.endswith("/tests/conftest.py") and hasattr(module, "_configure_hypothesis_cache"):
            def isolated_hypothesis_cache():
                try:
                    from hypothesis import settings
                    from hypothesis.database import DirectoryBasedExampleDatabase
                except ModuleNotFoundError:
                    return
                cache = Path(os.environ["ORCH02_OUTPUT_DIR"]) / "hypothesis"
                settings.register_profile("polisyos", database=DirectoryBasedExampleDatabase(str(cache)))
                settings.load_profile("polisyos")
            module._configure_hypothesis_cache = isolated_hypothesis_cache


def pytest_sessionfinish(session, exitstatus):
    out = Path(os.environ["ORCH02_OUTPUT_DIR"])
    packages = {}
    for name in ["pytest", "numpy", "duckdb", "hnswlib", "pandas", "pyyaml", "openpyxl", "pydantic"]:
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    origins = {}
    source_prefixes = ("polisyos.", "tools.")
    native_modules = {"numpy", "numpy._core._multiarray_umath", "duckdb", "_duckdb", "hnswlib", "pytest"}
    for name, module in tuple(sys.modules.items()):
        if name not in native_modules | {"polisyos", "tools"} and not name.startswith(source_prefixes):
            continue
        filename = getattr(module, "__file__", None)
        if filename:
            p = Path(filename)
            origins[name] = {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    data = {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
            "packages": packages, "origins": origins, "pytest_exitstatus": int(exitstatus),
            "origin_denominator": "complete loaded sys.modules set matching polisyos/tools namespaces plus named native modules, with a filesystem __file__; unexecuted modules are not runtime input evidence",
            "cache_relocation": "external hypothesis database; source/tests unchanged"}
    (out / "runtime-origins.json").write_text(json.dumps(data, indent=2) + "\n")
