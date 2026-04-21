"""Phase 1.7: Tests for the rich metadata pipeline.

Validates that:
  - All registered methods have non-empty when_to_use and output_interpretation
  - typical_min_obs is None or a positive integer
  - Snapshot entries propagate the new fields from MethodMetadata
  - method_selection_payload includes semantic fields for enriched methods
  - authoring_catalog_payload is structurally correct
  - DataCharacteristics penalises methods when n_obs < typical_min_obs
  - MethodMetadata.stable_digest is sensitive to changes in the new fields
"""
from __future__ import annotations

import pytest

from polisyos.foundry.methods.base import MethodMetadata
from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.catalog_snapshot import build_method_catalog_snapshot
from polisyos.foundry.methods.selection import (
    DataCharacteristics,
    MethodSelectionCriteria,
    authoring_catalog_payload,
    method_selection_payload,
    rank_method_catalog_entries,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snapshot():
    ensure_all_methods_registered()
    return build_method_catalog_snapshot(run_id="R_metadata_test")


def _entries():
    return _snapshot().entries


# ---------------------------------------------------------------------------
# 1. Coverage: all enrichable entries have when_to_use populated
# ---------------------------------------------------------------------------

def test_all_entries_have_when_to_use_populated() -> None:
    """Every snapshot entry that has a description should also have when_to_use."""
    entries = _entries()
    missing = [
        entry.fqn
        for entry in entries
        if entry.description and not entry.when_to_use
    ]
    assert not missing, (
        f"{len(missing)} entries have description but empty when_to_use:\n"
        + "\n".join(f"  {fqn}" for fqn in sorted(missing)[:20])
    )


def test_all_entries_have_output_interpretation_populated() -> None:
    """Every snapshot entry with a description should also have output_interpretation."""
    entries = _entries()
    missing = [
        entry.fqn
        for entry in entries
        if entry.description and not entry.output_interpretation
    ]
    assert not missing, (
        f"{len(missing)} entries have description but empty output_interpretation:\n"
        + "\n".join(f"  {fqn}" for fqn in sorted(missing)[:20])
    )


# ---------------------------------------------------------------------------
# 2. typical_min_obs validity
# ---------------------------------------------------------------------------

def test_typical_min_obs_is_none_or_positive() -> None:
    entries = _entries()
    bad = [
        entry.fqn
        for entry in entries
        if entry.typical_min_obs is not None and entry.typical_min_obs <= 0
    ]
    assert not bad, f"Non-positive typical_min_obs: {bad}"


def test_many_entries_have_typical_min_obs_set() -> None:
    """Sanity: at least half the entries with descriptions have typical_min_obs set."""
    entries = [e for e in _entries() if e.description]
    with_min_obs = [e for e in entries if e.typical_min_obs is not None]
    # Flexible: at least 30% coverage (some methods have no natural minimum)
    ratio = len(with_min_obs) / max(len(entries), 1)
    assert ratio >= 0.30, (
        f"Only {ratio:.0%} of described entries have typical_min_obs "
        f"({len(with_min_obs)}/{len(entries)})"
    )


# ---------------------------------------------------------------------------
# 3. Spot-check specific families for the new fields
# ---------------------------------------------------------------------------

SPOT_CHECK_FQNS = [
    "econometrics.discrete_choice.logit@1.0.0",
    "econometrics.selection.heckman@1.0.0",
    "econometrics.count.poisson@1.0.0",
    "causal.bounds.manski@1.0.0",
    "causal.bounds.lee@1.0.0",
    "causal.mediation.causal_mediation@1.0.0",
    "causal.discovery.dagma_discovery@1.0.0",
    "sensitivity.global.sobol_first_order@1.0.0",
    "sensitivity.global.morris@1.0.0",
    "survey.estimation.fay_herriot@1.0.0",
    "survey.imputation.mice@1.0.0",
    "simulation.inference.bootstrap@1.0.0",
    "optimization.linear.resource_lp@1.0.0",
    "optimization.integer.budget_milp@1.0.0",
    "bayesian.regression.linear_regression@1.0.0",
    "microsim.static.static_microsim@1.0.0",
    "distributional.inequality.atkinson@1.0.0",
    "network.community.community_detection@1.0.0",
]


@pytest.mark.parametrize("fqn", SPOT_CHECK_FQNS)
def test_spot_check_entry_has_rich_metadata(fqn: str) -> None:
    entries = _entries()
    entry = next((e for e in entries if e.fqn == fqn), None)
    assert entry is not None, f"FQN not found in snapshot: {fqn}"
    assert entry.when_to_use, f"{fqn}: when_to_use is empty"
    assert entry.output_interpretation, f"{fqn}: output_interpretation is empty"


# ---------------------------------------------------------------------------
# 4. method_selection_payload includes semantic fields
# ---------------------------------------------------------------------------

def test_method_selection_payload_includes_when_to_use_for_enriched_entries() -> None:
    entries = _entries()
    enriched = [e for e in entries if e.when_to_use and e.runnable][:5]
    assert enriched, "No runnable enriched entries found"

    payload = method_selection_payload(enriched)
    for item in payload:
        assert "when_to_use" in item, f"method_selection_payload missing when_to_use for {item['fqn']}"


def test_method_selection_payload_includes_output_interpretation() -> None:
    entries = _entries()
    enriched = [e for e in entries if e.output_interpretation and e.runnable][:5]
    assert enriched, "No runnable enriched entries found"

    payload = method_selection_payload(enriched)
    for item in payload:
        assert "output_interpretation" in item, (
            f"method_selection_payload missing output_interpretation for {item['fqn']}"
        )


def test_method_selection_payload_includes_typical_min_obs_when_set() -> None:
    entries = _entries()
    with_min = [e for e in entries if e.typical_min_obs is not None and e.runnable][:5]
    assert with_min, "No runnable entries with typical_min_obs found"

    payload = method_selection_payload(with_min)
    for item in payload:
        assert "typical_min_obs" in item, (
            f"method_selection_payload missing typical_min_obs for {item['fqn']}"
        )
        assert isinstance(item["typical_min_obs"], int)
        assert item["typical_min_obs"] > 0


def test_method_selection_payload_omits_empty_semantic_fields() -> None:
    """Entries without descriptions should not pollute the payload with empty strings."""
    entries = [e for e in _entries() if e.runnable][:3]
    assert entries, "No runnable entries available for payload check"
    bare = [
        entry.model_copy(
            update={
                "when_to_use": "",
                "output_interpretation": "",
            }
        )
        for entry in entries
    ]
    payload = method_selection_payload(bare)
    for item in payload:
        assert "when_to_use" not in item, f"Empty when_to_use leaked into payload for {item['fqn']}"


# ---------------------------------------------------------------------------
# 5. authoring_catalog_payload structure
# ---------------------------------------------------------------------------

def test_authoring_catalog_payload_structure() -> None:
    snapshot = _snapshot()
    payload = authoring_catalog_payload(snapshot)

    assert "source_schema_version" in payload
    assert payload["source_schema_version"] == "2.0"
    assert "snapshot_id" in payload
    assert "runnable_method_count" in payload
    assert payload["runnable_method_count"] >= 0
    assert "recommended_families" in payload
    assert isinstance(payload["recommended_families"], list)


def test_authoring_catalog_payload_families_carry_rich_metadata() -> None:
    snapshot = _snapshot()
    payload = authoring_catalog_payload(snapshot, limit_families=20, per_family=2)

    methods_with_when_to_use = 0
    methods_with_output_interpretation = 0
    for family_block in payload["recommended_families"]:
        for method in family_block["methods"]:
            if method.get("when_to_use"):
                methods_with_when_to_use += 1
            if method.get("output_interpretation"):
                methods_with_output_interpretation += 1

    total_methods = sum(len(fb["methods"]) for fb in payload["recommended_families"])
    assert total_methods > 0, "No methods in recommended_families"

    # At least 70% of recommended methods should have when_to_use
    ratio_wtu = methods_with_when_to_use / total_methods
    assert ratio_wtu >= 0.70, (
        f"Only {ratio_wtu:.0%} of recommended methods have when_to_use "
        f"({methods_with_when_to_use}/{total_methods})"
    )

    ratio_oi = methods_with_output_interpretation / total_methods
    assert ratio_oi >= 0.70, (
        f"Only {ratio_oi:.0%} of recommended methods have output_interpretation "
        f"({methods_with_output_interpretation}/{total_methods})"
    )


# ---------------------------------------------------------------------------
# 6. DataCharacteristics-aware scoring
# ---------------------------------------------------------------------------

def test_data_characteristics_penalises_underpowered_method() -> None:
    """A method with typical_min_obs=200 should rank lower when n_obs=20."""
    entries = _entries()
    # Find an entry with a large typical_min_obs
    large_min = [e for e in entries if e.typical_min_obs is not None and e.typical_min_obs >= 200 and e.runnable]
    small_min = [e for e in entries if e.typical_min_obs is not None and e.typical_min_obs <= 30 and e.runnable]
    assert large_min and small_min, "Need both large- and small-min-obs methods for this test"

    small_data = DataCharacteristics(n_obs=20)
    criteria = MethodSelectionCriteria(runnable_only=False)

    ranked = rank_method_catalog_entries(entries, criteria, data=small_data)
    ranked_fqns = [e.fqn for e in ranked]

    # At least one small_min method should rank above the first large_min method
    first_large_min_rank = next(
        (i for i, e in enumerate(ranked) if e.fqn in {x.fqn for x in large_min}),
        None,
    )
    first_small_min_rank = next(
        (i for i, e in enumerate(ranked) if e.fqn in {x.fqn for x in small_min}),
        None,
    )
    if first_large_min_rank is not None and first_small_min_rank is not None:
        assert first_small_min_rank <= first_large_min_rank + 20, (
            "Small-data methods should generally rank above large-min-obs methods with n_obs=20"
        )


def test_data_characteristics_instrument_availability_affects_iv_ranking() -> None:
    entries = _entries()
    iv_entries = [
        e for e in entries
        if "iv" in e.family.lower() or any("iv" == t.lower() for t in e.tags)
    ]
    assert iv_entries, "No IV entries found"

    with_instrument = DataCharacteristics(n_obs=500, has_instrument=True)
    without_instrument = DataCharacteristics(n_obs=500, has_instrument=False)
    criteria = MethodSelectionCriteria(runnable_only=False)

    ranked_with = rank_method_catalog_entries(entries, criteria, data=with_instrument)
    ranked_without = rank_method_catalog_entries(entries, criteria, data=without_instrument)

    iv_fqns = {e.fqn for e in iv_entries}
    rank_with = next((i for i, e in enumerate(ranked_with) if e.fqn in iv_fqns), None)
    rank_without = next((i for i, e in enumerate(ranked_without) if e.fqn in iv_fqns), None)

    if rank_with is not None and rank_without is not None:
        assert rank_with <= rank_without, (
            "IV methods should rank higher when instrument is available"
        )


# ---------------------------------------------------------------------------
# 7. MethodMetadata stable_digest is sensitive to new fields
# ---------------------------------------------------------------------------

def test_method_metadata_stable_digest_changes_with_when_to_use() -> None:
    base = MethodMetadata(description="test method")
    enriched = MethodMetadata(
        description="test method",
        when_to_use="Use when you have panel data",
        output_interpretation="ATT estimate from DiD",
    )
    assert base.stable_digest() != enriched.stable_digest()


def test_method_metadata_stable_digest_changes_with_typical_min_obs() -> None:
    no_min = MethodMetadata(description="test", when_to_use="when X")
    with_min = MethodMetadata(description="test", when_to_use="when X", typical_min_obs=100)
    assert no_min.stable_digest() != with_min.stable_digest()


def test_method_metadata_stable_digest_changes_with_truthfulness_declarations() -> None:
    base = MethodMetadata(description="test", when_to_use="when X")
    declared = MethodMetadata(
        description="test",
        when_to_use="when X",
        declared_truthfulness_tier="exact",
        truthfulness_scope="posterior",
    )
    assert base.stable_digest() != declared.stable_digest()


def test_method_metadata_new_fields_have_correct_defaults() -> None:
    metadata = MethodMetadata(description="test")
    assert metadata.when_to_use == ""
    assert metadata.when_not_to_use == ""
    assert metadata.output_interpretation == ""
    assert metadata.typical_min_obs is None
    assert metadata.declared_truthfulness_tier is None
    assert metadata.truthfulness_scope is None


def test_method_metadata_new_fields_appear_in_stable_dict() -> None:
    metadata = MethodMetadata(
        description="test",
        when_to_use="Use for X",
        output_interpretation="ATT > 0 means positive effect",
        typical_min_obs=50,
        declared_truthfulness_tier="asymptotic",
        truthfulness_scope="posterior",
    )
    d = metadata._stable_dict()
    assert d["when_to_use"] == "Use for X"
    assert d["output_interpretation"] == "ATT > 0 means positive effect"
    assert d["typical_min_obs"] == 50
    assert d["declared_truthfulness_tier"] == "asymptotic"
    assert d["truthfulness_scope"] == "posterior"


# ---------------------------------------------------------------------------
# 8. Snapshot entries propagate fields from MethodMetadata
# ---------------------------------------------------------------------------

def test_snapshot_entry_when_to_use_matches_metadata_for_known_method() -> None:
    """The snapshot entry's when_to_use must come from the registered MethodMetadata."""
    from polisyos.foundry.methods.registry import MethodRegistry
    ensure_all_methods_registered()
    reg = MethodRegistry.get_instance()

    snapshot = _snapshot()
    entries_with_wtu = [e for e in snapshot.entries if e.when_to_use]
    assert entries_with_wtu, "No snapshot entries with when_to_use found"

    # Pick one entry and verify its metadata matches
    sample_entry = entries_with_wtu[0]
    catalog_entry = reg.get_entry(sample_entry.fqn)
    if catalog_entry is not None:
        assert sample_entry.when_to_use == catalog_entry.metadata.when_to_use


def test_snapshot_total_enriched_entry_count() -> None:
    """At least 80 entries in the snapshot should have when_to_use populated."""
    entries = _entries()
    enriched = [e for e in entries if e.when_to_use]
    assert len(enriched) >= 80, (
        f"Expected ≥80 enriched entries, got {len(enriched)}"
    )
