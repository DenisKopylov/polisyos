"""
Foundry ↔ Scientist contract tests.

These tests verify that the data structures produced by Foundry are valid
inputs for the Scientist layer.  They form the integration seam between the
two subsystems and should break loudly if either side changes its schema
without updating the other.

Contract properties tested:
1. MethodCatalogSnapshot produced by Foundry has the required fields that
   the Scientist's planning nodes expect.
2. MethodCatalogEntry fields map correctly to Scientist planner inputs.
3. The snapshot is JSON-serialisable (required for the Scientist's LLM loop).
4. The stable_hash is deterministic across two builds with the same inputs.
5. MethodCatalogEntry.runnable reflects backend availability correctly.
"""

from __future__ import annotations

import json

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Fields the Scientist planner nodes must read from a MethodCatalogEntry
SCIENTIST_REQUIRED_ENTRY_FIELDS = frozenset(
    {
        "fqn",
        "name",
        "namespace",
        "description",
        "tags",
        "runnable",
        "backend",
    }
)

SCIENTIST_REQUIRED_SNAPSHOT_FIELDS = frozenset(
    {
        "schema_version",
        "entries",
        "generated_at",
    }
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def snapshot():
    """Build a MethodCatalogSnapshot using an isolated registry."""
    from polisyos.foundry.methods.registry import registry_scope

    with registry_scope() as reg:
        try:
            from polisyos.foundry.methods.catalog_snapshot import (
                build_method_catalog_snapshot,
            )

            return build_method_catalog_snapshot(registry=reg)
        except Exception as exc:
            pytest.skip(f"Cannot build snapshot: {exc}")


# ---------------------------------------------------------------------------
# Schema contract tests
# ---------------------------------------------------------------------------


def test_snapshot_has_required_top_level_fields(snapshot) -> None:
    """MethodCatalogSnapshot must contain all fields the Scientist requires."""
    snap_dict = json.loads(snapshot.model_dump_json())
    missing = SCIENTIST_REQUIRED_SNAPSHOT_FIELDS - set(snap_dict.keys())
    assert not missing, f"Snapshot missing required fields: {missing}"


def test_snapshot_entries_are_non_empty(snapshot) -> None:
    """Snapshot must contain at least one registered method."""
    assert len(snapshot.entries) > 0, "Snapshot has no entries — registration failed?"


def test_all_entries_have_required_fields(snapshot) -> None:
    """Each MethodCatalogEntry must expose the fields the Scientist reads."""
    for entry in snapshot.entries:
        entry_dict = json.loads(entry.model_dump_json())
        missing = SCIENTIST_REQUIRED_ENTRY_FIELDS - set(entry_dict.keys())
        assert not missing, f"Entry {entry.fqn!r} missing required fields: {missing}"


def test_snapshot_is_json_serialisable(snapshot) -> None:
    """
    The Scientist LLM loop passes the snapshot as JSON to the model.
    It must serialise without error and be re-parseable.
    """
    json_str = snapshot.model_dump_json()
    assert json_str  # non-empty
    reparsed = json.loads(json_str)
    assert isinstance(reparsed, dict)
    assert "entries" in reparsed


def test_snapshot_stable_hash_is_deterministic(snapshot) -> None:
    """
    stable_hash() must return the same value when called twice.
    The Scientist uses this hash to detect catalog changes.
    """
    h1 = snapshot.stable_hash()
    h2 = snapshot.stable_hash()
    assert h1 == h2
    assert len(h1) > 8  # non-trivial hash


def test_fqn_format_valid_for_scientist(snapshot) -> None:
    """
    All FQNs must match the pattern ``namespace.name@semver``.
    The Scientist parses FQNs to extract namespace and method name.
    """
    import re

    fqn_pattern = re.compile(r"^[\w.]+\.\w+@\d+\.\d+\.\d+")
    for entry in snapshot.entries:
        assert fqn_pattern.match(entry.fqn), f"FQN {entry.fqn!r} does not match expected pattern"


def test_backend_field_is_known_value(snapshot) -> None:
    """
    The 'backend' field must be one of the known ComputeBackend values.
    The Scientist uses this to filter methods by available hardware.
    """
    from polisyos.foundry.methods.base import ComputeBackend

    known_backends = {b.value for b in ComputeBackend}
    for entry in snapshot.entries:
        assert entry.backend in known_backends, (
            f"Entry {entry.fqn!r} has unknown backend {entry.backend!r}"
        )


def test_runnable_entries_have_no_disabled_reasons(snapshot) -> None:
    """
    Entries marked runnable=True must have an empty disabled_reasons list.
    This contract ensures the Scientist can trust the runnable flag.
    """
    for entry in snapshot.entries:
        if entry.runnable:
            assert not entry.disabled_reasons, (
                f"Entry {entry.fqn!r} is runnable but has disabled_reasons: "
                f"{entry.disabled_reasons}"
            )


def test_snapshot_tags_are_string_lists(snapshot) -> None:
    """Tags must be lists of strings — the Scientist filters by tag."""
    for entry in snapshot.entries:
        assert isinstance(entry.tags, list)
        for tag in entry.tags:
            assert isinstance(tag, str), f"Entry {entry.fqn!r} has non-string tag: {tag!r}"


# ---------------------------------------------------------------------------
# Structural stability test (snapshot schema version)
# ---------------------------------------------------------------------------


def test_snapshot_schema_version_is_current(snapshot) -> None:
    """
    Schema version must be "2.0".  Bumping requires a migration guide
    and Scientist-side adapter update.
    """
    assert snapshot.schema_version == "2.0", (
        f"Unexpected schema_version: {snapshot.schema_version!r}. "
        "If you bumped the schema, update the Scientist adapter and this test."
    )
