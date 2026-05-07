"""
CI breaking-change detection test.

Compares the currently registered method signatures against a committed
baseline snapshot (``tests/_golden/foundry/signature_baseline.json``).

Usage
-----
Normal CI run::

    pytest tests/unit/foundry/contracts/test_signature_compat.py -v

Allow intentional breaking changes (update baseline after review)::

    FOUNDRY_ALLOW_BREAKING=1 pytest tests/unit/foundry/contracts/test_signature_compat.py

To regenerate the baseline after an approved breaking change::

    uv run polisyos-tools foundry update-signature-baseline

Architecture notes
------------------
- The baseline is committed to source control.
- A ``stable_hash`` of each ``MethodSignature`` is stored — not the full
  signature — to avoid serialising complex dataclasses to JSON.
- The test fails if any FQN present in the baseline has a different hash
  in the current registry (= breaking change without a baseline update).
- New FQNs added to the registry do NOT cause test failure (additive only).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

_BASELINE_PATH = (
    Path(__file__).resolve().parents[3] / "_golden" / "foundry" / "signature_baseline.json"
)
_ALLOW_BREAKING_ENV = "FOUNDRY_ALLOW_BREAKING"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_baseline() -> dict[str, str]:
    """Return {fqn: signature_hash} from the committed baseline file."""
    if not _BASELINE_PATH.exists():
        return {}
    with _BASELINE_PATH.open() as f:
        data = json.load(f)
    return data.get("signatures", {})


def _build_current_hashes(registry) -> dict[str, str]:
    """Build {fqn: signature_hash} from the live registry."""
    hashes: dict[str, str] = {}
    for sig in registry.list_all():
        try:
            hashes[sig.fqn] = sig.stable_digest()
        except Exception:
            hashes[sig.fqn] = "<error>"
    return hashes


def _is_major_bump(old_fqn: str, new_fqns: set[str]) -> bool:
    """
    Return True if a higher-major-version of fqn exists in new_fqns.
    e.g. old_fqn = "causal.did.standard@1.0.0" and "causal.did.standard@2.0.0" is present.
    """
    if "@" not in old_fqn:
        return False
    base, old_ver = old_fqn.rsplit("@", 1)
    try:
        old_major = int(old_ver.split(".")[0])
    except (ValueError, IndexError):
        return False
    for fqn in new_fqns:
        if "@" not in fqn:
            continue
        fqn_base, fqn_ver = fqn.rsplit("@", 1)
        if fqn_base != base:
            continue
        try:
            new_major = int(fqn_ver.split(".")[0])
            if new_major > old_major:
                return True
        except (ValueError, IndexError):
            continue
    return False


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _current_hashes(module_registry):
    """Current registry signature hashes (module-scoped for performance)."""
    return _build_current_hashes(module_registry)


@pytest.fixture(scope="module")
def _baseline():
    return _load_baseline()


class TestSignatureCompat:
    def test_baseline_exists_or_no_op(self, _baseline):
        """If no baseline file exists, the test passes (first-time setup)."""
        if not _BASELINE_PATH.exists():
            pytest.skip(
                "No signature baseline found. "
                "Run `uv run polisyos-tools foundry update-signature-baseline` to generate it."
            )

    def test_no_breaking_changes(self, _baseline, _current_hashes):
        """Fail if any baseline FQN has a different hash in current registry."""
        if not _baseline:
            pytest.skip("Baseline is empty — nothing to compare")

        if os.getenv(_ALLOW_BREAKING_ENV, "").lower() in {"1", "true", "yes"}:
            pytest.skip(f"{_ALLOW_BREAKING_ENV}=1 — skipping breaking change check")

        current_fqns = set(_current_hashes.keys())
        breaking: list[str] = []

        for fqn, old_hash in _baseline.items():
            if fqn not in _current_hashes:
                # FQN removed — check if a major bump replaces it
                if not _is_major_bump(fqn, current_fqns):
                    breaking.append(f"REMOVED (no major-version replacement): {fqn}")
            elif _current_hashes[fqn] != old_hash:
                breaking.append(
                    f"SIGNATURE CHANGED: {fqn}\n"
                    f"  baseline:  {old_hash}\n"
                    f"  current:   {_current_hashes[fqn]}"
                )

        if breaking:
            detail = "\n".join(breaking)
            pytest.fail(
                f"Breaking signature changes detected ({len(breaking)}):\n\n{detail}\n\n"
                f"If these changes are intentional:\n"
                f"  1. Bump the method's major version (e.g. @1.x.x → @2.0.0)\n"
                f"  2. Run: uv run polisyos-tools foundry update-signature-baseline\n"
                f"  3. Commit the updated baseline\n"
                f"Or set {_ALLOW_BREAKING_ENV}=1 to bypass this check temporarily."
            )

    def test_baseline_schema_version(self, _baseline):
        """Baseline must have a schema_version key."""
        if not _BASELINE_PATH.exists():
            pytest.skip("No baseline file")
        with _BASELINE_PATH.open() as f:
            data = json.load(f)
        assert "schema_version" in data, "Baseline missing 'schema_version'"
        assert data["schema_version"] == "1.0", (
            f"Unexpected schema_version: {data['schema_version']!r}"
        )

    def test_new_methods_not_blocked(self, _baseline, _current_hashes):
        """New FQNs in the registry (not in baseline) should not cause failure."""
        new_fqns = set(_current_hashes) - set(_baseline)
        # This is informational — not a failure
        if new_fqns:
            pass  # New methods detected — acceptable
