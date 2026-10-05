from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_profiles_shim_points_to_core() -> None:
    from polisyos.core.governance.profiles import ValidationProfile as CoreValidationProfile
    from polisyos.scientist.governance.profiles import ValidationProfile as LegacyValidationProfile

    assert LegacyValidationProfile is CoreValidationProfile


def test_canonical_pass_contracts_are_owned_by_core() -> None:
    from polisyos.core.governance.passes.base import PassContext as CorePassContext
    from polisyos.core.governance.passes.legal_pass import LegalPass as CoreLegalPass
    from polisyos.core.governance.passes.safety_pass import SafetyPass as CoreSafetyPass
    from polisyos.scientist.governance.passes import LegalPass, SafetyPass

    assert CorePassContext.__module__ == "polisyos.core.governance.passes.base"
    assert CoreLegalPass.__module__ == "polisyos.core.governance.passes.legal_pass"
    assert CoreSafetyPass.__module__ == "polisyos.core.governance.passes.safety_pass"
    assert LegalPass is CoreLegalPass
    assert SafetyPass is CoreSafetyPass


def test_retired_scientist_compatibility_modules_fail_in_fresh_interpreters() -> None:
    """Retired shim paths no longer resolve; living pass namespace remains intact."""

    retired_modules = (
        "polisyos.scientist.evidence._" + "shim",
        *(
            "polisyos.scientist.governance.passes." + leaf
            for leaf in ("base", "legal_pass", "safety_pass")
        ),
    )
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
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(REPO_ROOT / "src")

    for module_name in retired_modules:
        result = subprocess.run(
            [sys.executable, "-c", probe, module_name],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"{module_name}: {result.stderr}"

    from polisyos.scientist.governance import passes

    assert passes.__file__ is not None
    assert "PassContext" in passes.__all__


def test_legal_backend_shims_point_to_core() -> None:
    from polisyos.core.governance.legal.ast_policy import ASTPolicy as CoreASTPolicy
    from polisyos.core.governance.legal.backends.expr_ast import (
        ExpressionASTBackend as CoreExpressionASTBackend,
    )
    from polisyos.core.governance.legal.backends.stub import StubBackend as CoreStubBackend
    from polisyos.scientist.governance.legal.ast_policy import ASTPolicy as LegacyASTPolicy
    from polisyos.scientist.governance.legal.backends.expr_ast import (
        ExpressionASTBackend as LegacyExpressionASTBackend,
    )
    from polisyos.scientist.governance.legal.backends.stub import StubBackend as LegacyStubBackend

    assert LegacyASTPolicy is CoreASTPolicy
    assert LegacyExpressionASTBackend is CoreExpressionASTBackend
    assert LegacyStubBackend is CoreStubBackend
