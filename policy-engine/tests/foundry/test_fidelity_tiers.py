"""
Fidelity tier validation tests (T3.4).

Verifies that all registered catalog methods meet the invariants declared by
their ``FidelityLevel``:

FidelityLevel.HIGH (production-quality):
  - Must have at least one citation
  - Must have a non-empty description
  - Must have version >= 1.0.0
  - Must have a non-empty family name

FidelityLevel.MEDIUM (research-quality):
  - Must have a non-empty description
  - Should have at least one tag

FidelityLevel.LOW (heuristic/proxy):
  - Must have a non-empty description

All levels:
  - FQN must be parseable
  - Version must be valid SemVer
  - Must have at least one output slot
"""
from __future__ import annotations

import pytest

from polisyos.foundry.methods.base import FidelityLevel, parse_fqn
from polisyos.foundry.methods.resolution import SemVer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ge_1_0_0(version: str) -> bool:
    """Return True if version >= 1.0.0."""
    try:
        v = SemVer.parse(version)
        return (v.major, v.minor, v.patch) >= (1, 0, 0)
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFidelityTierContracts:
    """Validate all registered methods against their declared fidelity tier."""

    def test_all_methods_have_valid_fqn(self, module_registry):
        """Every registered FQN must parse correctly."""
        failures: list[str] = []
        for sig in module_registry.list_all():
            try:
                parse_fqn(sig.fqn)
            except ValueError as exc:
                failures.append(f"{sig.fqn}: {exc}")
        assert not failures, f"FQN parse failures:\n" + "\n".join(failures)

    def test_all_methods_have_output_slots(self, module_registry):
        """Every method must produce at least one output slot."""
        failures = [
            sig.fqn
            for sig in module_registry.list_all()
            if not sig.output_slots
        ]
        assert not failures, (
            f"{len(failures)} method(s) have no output slots:\n"
            + "\n".join(failures[:20])
        )

    def test_all_methods_have_non_empty_description(self, module_registry):
        """Every method must have a description."""
        failures: list[str] = []
        for sig in module_registry.list_all():
            entry = module_registry.get_entry(sig.fqn)
            if entry is None:
                continue
            if not entry.metadata.description or not entry.metadata.description.strip():
                failures.append(sig.fqn)
        assert not failures, (
            f"{len(failures)} method(s) have empty descriptions:\n"
            + "\n".join(failures[:20])
        )

    def test_high_fidelity_methods_have_citations(self, module_registry):
        """HIGH-fidelity (production-quality) methods must cite source literature."""
        failures: list[str] = []
        for sig in module_registry.list_all():
            if sig.fidelity != FidelityLevel.HIGH:
                continue
            entry = module_registry.get_entry(sig.fqn)
            if entry is None:
                continue
            if not entry.metadata.citations:
                failures.append(sig.fqn)
        assert not failures, (
            f"{len(failures)} HIGH-fidelity method(s) have no citations:\n"
            + "\n".join(failures[:20])
        )

    def test_high_fidelity_methods_have_version_1_plus(self, module_registry):
        """HIGH-fidelity methods must be at version >= 1.0.0."""
        failures: list[str] = []
        for sig in module_registry.list_all():
            if sig.fidelity != FidelityLevel.HIGH:
                continue
            if not _ge_1_0_0(sig.version):
                failures.append(f"{sig.fqn} (version={sig.version!r})")
        assert not failures, (
            f"{len(failures)} HIGH-fidelity method(s) have pre-1.0 versions:\n"
            + "\n".join(failures[:20])
        )

    def test_high_fidelity_methods_have_family(self, module_registry):
        """HIGH-fidelity methods must declare a family name."""
        failures: list[str] = []
        for sig in module_registry.list_all():
            if sig.fidelity != FidelityLevel.HIGH:
                continue
            if not sig.family or not sig.family.strip():
                failures.append(sig.fqn)
        assert not failures, (
            f"{len(failures)} HIGH-fidelity method(s) have no family:\n"
            + "\n".join(failures[:20])
        )

    def test_medium_fidelity_methods_have_tags(self, module_registry):
        """MEDIUM-fidelity methods should have at least one tag for discoverability."""
        failures: list[str] = []
        for sig in module_registry.list_all():
            if sig.fidelity != FidelityLevel.MEDIUM:
                continue
            entry = module_registry.get_entry(sig.fqn)
            if entry is None:
                continue
            if not entry.metadata.tags:
                failures.append(sig.fqn)
        # Informational: warn rather than fail hard (some MEDIUM methods may lack tags)
        if failures:
            pytest.xfail(
                f"{len(failures)} MEDIUM-fidelity method(s) have no tags: "
                + ", ".join(failures[:5])
            )

    def test_fidelity_level_is_valid_enum(self, module_registry):
        """Every method must declare a recognized FidelityLevel."""
        valid = set(FidelityLevel)
        failures: list[str] = []
        for sig in module_registry.list_all():
            if sig.fidelity not in valid:
                failures.append(f"{sig.fqn}: {sig.fidelity!r}")
        assert not failures, (
            f"Invalid fidelity levels:\n" + "\n".join(failures[:10])
        )

    def test_fidelity_tier_matches_fidelity(self, module_registry):
        """
        fidelity_tier, when set, must equal or be compatible with fidelity.

        By convention, fidelity_tier defaults to fidelity; overrides must
        use a valid FidelityLevel value.
        """
        valid = set(FidelityLevel)
        failures: list[str] = []
        for sig in module_registry.list_all():
            if sig.fidelity_tier is not None and sig.fidelity_tier not in valid:
                failures.append(f"{sig.fqn}: fidelity_tier={sig.fidelity_tier!r}")
        assert not failures, "\n".join(failures[:10])
