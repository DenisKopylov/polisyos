from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]


def test_snapshot_first_import_preserves_catalog_export_identity() -> None:
    script = """
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "src"))
from polisyos.foundry.methods.catalog.snapshot import (
    build_method_catalog_provenance_manifest,
    build_method_catalog_runtime_identity,
    ensure_all_methods_registered,
)
import polisyos.foundry.methods.catalog as catalog
from polisyos.foundry.methods.catalog.dependency_authority import (
    DependencyProfileResolutionFailure,
    MethodCatalogDependencyAuthorityRequest,
)
assert catalog.build_method_catalog_provenance_manifest is build_method_catalog_provenance_manifest
assert catalog.build_method_catalog_runtime_identity is build_method_catalog_runtime_identity
assert catalog.DependencyProfileResolutionFailure is DependencyProfileResolutionFailure
assert catalog.MethodCatalogDependencyAuthorityRequest is MethodCatalogDependencyAuthorityRequest
assert catalog.ensure_all_methods_registered is ensure_all_methods_registered
assert {
    "DependencyProfileResolutionFailure",
    "MethodCatalogDependencyAuthorityRequest",
    "build_method_catalog_provenance_manifest",
    "build_method_catalog_runtime_identity",
} <= set(catalog.__all__)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
