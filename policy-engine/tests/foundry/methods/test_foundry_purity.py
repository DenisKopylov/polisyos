"""Law B verification: Foundry data-plane purity.

Ensures that all foundry method modules are free of banned imports
(I/O, system access, heavy data-plane libraries in standard policy zones)
and that registered methods conform to the FoundryMethod protocol.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from polisyos.foundry.methods.base import ComputeBackend, MethodSignature
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.registry import MethodRegistry

REPO_ROOT = Path(__file__).resolve().parents[3]
LINT_SCRIPT = REPO_ROOT / "tools" / "lint" / "lint_foundry.py"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _foundry_root() -> Path:
    root = REPO_ROOT / "src" / "polisyos" / "foundry"
    assert root.exists(), f"Foundry root not found at {root}"
    return root


# ---------------------------------------------------------------------------
# A1: lint_foundry.py subprocess gate
# ---------------------------------------------------------------------------


class TestLintFoundrySubprocess:
    def test_lint_foundry_exit_zero(self) -> None:
        """Run lint_foundry.py as subprocess and assert clean exit."""
        result = subprocess.run(
            [sys.executable, str(LINT_SCRIPT), "--repo-root", str(REPO_ROOT)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"lint_foundry.py exited {result.returncode}:\n{result.stdout}\n{result.stderr}"
        )
        assert "clean" in result.stdout.lower(), (
            f"Expected 'clean' in output:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# A2: Protocol compliance for registered causal methods
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


class TestProtocolCompliance:
    def test_all_causal_methods_have_signature(self) -> None:
        """Every registered causal method must have a MethodSignature."""
        from polisyos.foundry.methods.catalog.causal import ensure_causal_methods_registered

        ensure_causal_methods_registered()
        registry = MethodRegistry.get_instance()

        all_sigs = registry.list_all()
        assert len(all_sigs) > 0, "No methods registered at all"

        for sig in all_sigs:
            assert isinstance(sig, MethodSignature), f"{sig.fqn} has wrong signature type"
            assert sig.fqn, "Method signature has empty FQN"
            assert "@" in sig.fqn, f"{sig.fqn} missing version separator"

    def test_all_causal_methods_have_pure_step(self) -> None:
        """Every registered causal method must define a pure_step."""
        from polisyos.foundry.methods.catalog.causal import ensure_causal_methods_registered

        ensure_causal_methods_registered()
        registry = MethodRegistry.get_instance()

        for fqn in registry:
            method_cls = registry.get(fqn)
            assert hasattr(method_cls, "pure_step"), (
                f"{fqn}: missing pure_step"
            )


# ---------------------------------------------------------------------------
# A3: Direct AST scan (reuse lint_foundry internals)
# ---------------------------------------------------------------------------


class TestDirectASTScan:
    def test_no_banned_imports_in_foundry(self) -> None:
        """Walk all foundry Python files and verify 0 ban-list violations."""
        sys.path.insert(0, str(REPO_ROOT / "tools" / "lint"))
        try:
            import lint_foundry as lf
        finally:
            sys.path.pop(0)

        foundry_roots = lf.find_foundry_roots(REPO_ROOT)
        assert foundry_roots, "No foundry roots found"

        violations = []
        for root in foundry_roots:
            for py_file in lf.iter_py_files(root):
                policy = lf._policy_for_file(py_file, root)
                outcome = lf._scan_file(
                    py_file,
                    repo_root=REPO_ROOT,
                    policy=policy,
                    apply_fix=False,
                )
                violations.extend(outcome.violations)

        assert violations == [], (
            f"Foundry ban-list violations:\n"
            + "\n".join(f"  {v.path}:{v.lineno} {v.message}" for v in violations)
        )


# ---------------------------------------------------------------------------
# A4: Backend isolation
# ---------------------------------------------------------------------------


class TestBackendIsolation:
    def test_compute_backend_values_are_strings(self) -> None:
        """ComputeBackend enum values must be plain strings for serialization."""
        for member in ComputeBackend:
            assert isinstance(member.value, str), (
                f"ComputeBackend.{member.name} has non-string value: {member.value!r}"
            )

    def test_no_foundry_catalog_imports_io_directly(self) -> None:
        """Scan catalog/ directory for direct I/O imports (os, pathlib, etc.)."""
        catalog_root = _foundry_root() / "methods" / "catalog"
        assert catalog_root.exists(), "catalog directory not found"

        io_modules = {"os", "pathlib", "shutil", "glob", "tempfile", "subprocess"}
        violations = []

        for py_file in catalog_root.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root_mod = alias.name.split(".")[0]
                        if root_mod in io_modules:
                            violations.append(
                                f"{py_file.relative_to(REPO_ROOT)}:{node.lineno} import {alias.name}"
                            )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    root_mod = node.module.split(".")[0]
                    if root_mod in io_modules:
                        violations.append(
                            f"{py_file.relative_to(REPO_ROOT)}:{node.lineno} from {node.module}"
                        )

        assert violations == [], (
            f"Catalog files importing I/O modules:\n" + "\n".join(f"  {v}" for v in violations)
        )
