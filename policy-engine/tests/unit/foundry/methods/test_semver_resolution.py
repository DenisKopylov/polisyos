"""
Tests for pip-style SemVer constraint resolution in resolution.py.

Verifies:
- parse_pip_specifier: recognises ~=, >=/<, ==, bare version
- resolve_by_specifier: selects highest matching version from a list
- resolve_method_version: high-level helper that queries the registry
- ResolutionError raised when no version satisfies the constraint
"""

from __future__ import annotations

import pytest
from polisyos.foundry.methods.exceptions import ResolutionError
from polisyos.foundry.methods.resolution import (
    parse_pip_specifier,
    resolve_by_specifier,
    resolve_method_version,
)

# ---------------------------------------------------------------------------
# parse_pip_specifier
# ---------------------------------------------------------------------------


class TestParsePipSpecifier:
    def test_compatible_release(self):
        spec = parse_pip_specifier("~=1.2")
        assert spec.contains("1.2.0")
        assert spec.contains("1.9.9")
        assert not spec.contains("2.0.0")
        assert not spec.contains("1.1.9")

    def test_range_constraint(self):
        spec = parse_pip_specifier(">=1.0,<2.0")
        assert spec.contains("1.0.0")
        assert spec.contains("1.9.9")
        assert not spec.contains("2.0.0")
        assert not spec.contains("0.9.9")

    def test_exact_eq(self):
        spec = parse_pip_specifier("==1.3.0")
        assert spec.contains("1.3.0")
        assert not spec.contains("1.3.1")

    def test_bare_version_treated_as_exact(self):
        spec = parse_pip_specifier("1.0.0")
        assert spec.contains("1.0.0")
        assert not spec.contains("1.0.1")

    def test_exclusion(self):
        spec = parse_pip_specifier(">=1.0,!=1.3,<2.0")
        assert spec.contains("1.2.0")
        assert not spec.contains("1.3.0")

    def test_invalid_specifier_raises(self):
        with pytest.raises(ValueError, match="Invalid pip-style specifier"):
            parse_pip_specifier("not-a-version!")

    def test_pre_releases_excluded_by_default(self):
        spec = parse_pip_specifier(">=1.0,<2.0")
        assert not spec.contains("1.5.0a1")


# ---------------------------------------------------------------------------
# resolve_by_specifier
# ---------------------------------------------------------------------------

_AVAILABLE = ["0.9.0", "1.0.0", "1.1.0", "1.2.0", "1.3.0", "2.0.0", "2.1.0"]


class TestResolveBySpecifier:
    def test_compatible_release_selects_latest_in_range(self):
        result = resolve_by_specifier(_AVAILABLE, "~=1.1")
        assert result == "1.3.0"

    def test_range_constraint_excludes_major(self):
        result = resolve_by_specifier(_AVAILABLE, ">=1.0,<2.0")
        assert result == "1.3.0"

    def test_exact_version(self):
        result = resolve_by_specifier(_AVAILABLE, "==1.2.0")
        assert result == "1.2.0"

    def test_bare_version(self):
        result = resolve_by_specifier(_AVAILABLE, "1.1.0")
        assert result == "1.1.0"

    def test_no_match_raises_resolution_error(self):
        with pytest.raises(ResolutionError):
            resolve_by_specifier(_AVAILABLE, ">=3.0")

    def test_excludes_specific_version(self):
        result = resolve_by_specifier(_AVAILABLE, ">=1.0,!=1.3.0,<2.0")
        assert result == "1.2.0"

    def test_selects_highest_matching(self):
        result = resolve_by_specifier(_AVAILABLE, ">=2.0")
        assert result == "2.1.0"

    def test_include_prerelease(self):
        available = ["1.0.0", "1.1.0a1", "1.0.1"]
        # pre-release excluded by default
        result = resolve_by_specifier(available, ">=1.0")
        assert result == "1.0.1"
        # pre-release included when requested
        result = resolve_by_specifier(available, ">=1.0", include_prerelease=True)
        assert result == "1.1.0a1"


# ---------------------------------------------------------------------------
# resolve_method_version — requires a live registry
# ---------------------------------------------------------------------------


class TestResolveMethodVersion:
    """Integration tests using the conftest module_registry fixture."""

    def test_no_specifier_returns_latest(self, module_registry):
        """None specifier should return the highest registered version."""
        # Pick an FQN base we know is registered
        all_sigs = list(module_registry.list_all())
        assert all_sigs, "Registry is empty"

        fqn = all_sigs[0].fqn
        base = fqn.rsplit("@", 1)[0]

        result = resolve_method_version(base, None, module_registry)
        assert result.startswith(base + "@")

    def test_specifier_pins_version(self, module_registry):
        """~=1.0 should resolve to a 1.x version if one is registered."""
        all_sigs = list(module_registry.list_all())
        assert all_sigs, "Registry is empty"

        # Find a method with version 1.0.0
        v1_sigs = [s for s in all_sigs if s.version.startswith("1.")]
        assert v1_sigs, "No 1.x methods registered"

        fqn = v1_sigs[0].fqn
        base = fqn.rsplit("@", 1)[0]

        result = resolve_method_version(base, "~=1.0", module_registry)
        assert "@1." in result

    def test_unsatisfiable_specifier_raises(self, module_registry):
        """A specifier that can't match any version raises ResolutionError."""
        all_sigs = list(module_registry.list_all())
        assert all_sigs, "Registry is empty"

        fqn = all_sigs[0].fqn
        base = fqn.rsplit("@", 1)[0]

        with pytest.raises(ResolutionError):
            resolve_method_version(base, ">=99.0", module_registry)

    def test_unregistered_base_raises(self, module_registry):
        """An entirely unknown base name raises ResolutionError."""
        with pytest.raises(ResolutionError):
            resolve_method_version("ghost.nonexistent.method", "~=1.0", module_registry)
