"""Source descriptors are discoverable while claim authority stays blocked."""

from __future__ import annotations

import pytest

from polisyos.runtime.quality.capability_resolver import (
    RequirementToCapabilityQuery,
    RequirementToCapabilityResolver,
)


@pytest.mark.parametrize(
    ("construct", "population", "indicator", "slot", "unit", "catalog_metric"),
    [
        (
            "economic.gdp",
            "national_economy",
            "NY.GDP.MKTP.CD",
            "global.gdp",
            "usd",
            "gdp",
        ),
        (
            "labor.unemployment_rate",
            "total_labor_force",
            "SL.UEM.TOTL.ZS",
            "global.unemployment_rate",
            "ratio",
            "labor.unemployment_rate",
        ),
    ],
)
def test_governed_catalog_candidate_cannot_become_claim_evidence(
    construct: str,
    population: str,
    indicator: str,
    slot: str,
    unit: str,
    catalog_metric: str,
) -> None:
    resolver = RequirementToCapabilityResolver.governed_fixture()
    candidates = [item for item in resolver.capabilities if item.construct_id == construct]
    assert len(candidates) == 1
    (candidate,) = candidates
    assert candidate.capability_lifecycle.state == "draft"
    assert candidate.scope.population == population
    assert candidate.scope.temporal_granularity == "annual"
    metadata = candidate.source_assets[0].metadata
    assert metadata["indicator_id"] == indicator
    assert metadata["source_release"] == "not_established"
    assert metadata["population_scope"] == population
    assert metadata["target_world_slot"] == slot
    assert metadata["canonical_unit"] == unit
    assert metadata["catalog_fetch_binding"] == {
        "metric_id": catalog_metric,
        "connector_id": "worldbank.wdi",
        "profile_id": "worldbank_wdi",
        "dataset_id": indicator,
    }
    if construct == "labor.unemployment_rate":
        assert metadata["observation_provenance"] == "model_output"
    query = RequirementToCapabilityQuery(
        requirement_id="fixture:source-candidate",
        construct=construct,
        entity_scope="country",
        population_filter={"type": population},
        geography="USA",
        time_window={"start": "2024-01-01", "end": "2024-12-31"},
        authority_level="governed_pilot",
        claim_use="claim_evidence_closeout",
    )
    result = resolver.resolve(query)
    assert result.status == "blocked_rights_boundary"
    assert result.selected_capability_ref is None
    assert not result.satisfies_claim_evidence

    mismatched = resolver.resolve(
        query.model_copy(update={"population_filter": {"type": "incompatible_population"}})
    )
    assert mismatched.selected_capability_ref is None
    assert any(
        rejection["rejection_reason"] == "population_filter_mismatch"
        for rejection in mismatched.rejected_alternatives
    )
