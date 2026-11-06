"""Source descriptors are discoverable while claim authority stays blocked."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core import artifacts
from polisyos.data_requirement import DataRequirementCompilationReport
from polisyos.runtime.quality.candidate_acquisition_source import (
    _validate_scope,
    read_candidate_acquisition_source,
)
from polisyos.runtime.quality.capability_resolver import (
    RequirementToCapabilityQuery,
    RequirementToCapabilityResolver,
)
from tests._helpers.lane01_candidate_source import (
    GDP_COMPILER_INPUT,
    UNEMPLOYMENT_COMPILER_INPUT,
    Lane01CandidateCompilerInput,
    Lane01CandidateSourceFixture,
    build_lane01_candidate_source,
)
from tests._helpers.lane01_wdi_profiles import (
    GDP_PROFILE,
    UNEMPLOYMENT_PROFILE,
    CandidateWDIProfile,
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


def _compiled_source_scope(fixture: Lane01CandidateSourceFixture) -> dict[str, object]:
    """Reopen the actual compiled descriptor and current Catalog owner for source admission."""
    report = DataRequirementCompilationReport.model_validate(
        artifacts.load_core_json_artifact(fixture.store, fixture.binding.compiler_report_ref)
    )
    (resolution,) = report.capability_requirement_resolutions or ()
    discovery = resolution.candidate_discovery
    assert discovery is not None
    (candidate,) = discovery.candidates
    source = fixture.source
    return {
        "resolved": fixture.authority.resolve(fixture.entry.entry_id),
        "target_slot_id": source.target_slot_id,
        "country_code": source.country_code,
        "year": source.year,
        "population": source.population,
        "denominator": source.denominator,
        "quantity_kind": source.quantity_kind,
        "canonical_unit": source.canonical_unit,
        "query": resolution.query,
        "discovery": discovery,
        "candidate": candidate,
    }


@pytest.mark.parametrize(
    ("profile", "compiler_input", "catalog_metric"),
    [
        (GDP_PROFILE, GDP_COMPILER_INPUT, "gdp"),
        (UNEMPLOYMENT_PROFILE, UNEMPLOYMENT_COMPILER_INPUT, "labor.unemployment_rate"),
    ],
)
def test_source_owner_keeps_canonical_construct_separate_from_catalog_metric(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    profile: CandidateWDIProfile,
    compiler_input: Lane01CandidateCompilerInput,
    catalog_metric: str,
) -> None:
    """Real source production and fresh replay preserve both identifier roles."""
    fixture = build_lane01_candidate_source(
        tmp_path, monkeypatch, profile=profile, compiler_input=compiler_input
    )
    scope = _compiled_source_scope(fixture)
    query = scope["query"]
    candidate = scope["candidate"]
    assert query.construct == profile.construct
    assert candidate.construct_ref == f"construct:{profile.construct}"
    assert candidate.source_assets[0]["metadata"]["catalog_fetch_binding"]["metric_id"] == (
        catalog_metric
    )
    assert fixture.entry.upstream_metric_id == catalog_metric
    assert fixture.source.resolved_source.upstream_catalog_projection["metric_id"] == catalog_metric
    assert fixture.source.resolved_source.registration.metric_id == profile.target_slot
    assert fixture.source.observation_class == profile.source_provenance_class
    assert fixture.source.status == "candidate_only"
    assert "claim_evidence_not_established" in fixture.source.limitations
    if profile is GDP_PROFILE:
        assert query.construct != catalog_metric
    else:
        assert profile.catalog_metric_id is None
    assert isinstance(fixture.store, artifacts.FileSystemCAS)
    reopened_store = artifacts.FileSystemCAS(fixture.store.root)
    assert (
        read_candidate_acquisition_source(
            reopened_store, source_ref=fixture.source_ref, authority=fixture.authority
        )
        == fixture.source
    )
    for prefix in ("", "construct:"):
        canonical_candidate = type(candidate).model_validate(
            candidate.model_dump(mode="json") | {"construct_ref": prefix + profile.construct}
        )
        _validate_scope(**(scope | {"candidate": canonical_candidate}))


def test_source_owner_refuses_forged_construct_with_catalog_metric_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A retained descriptor hash and correct Catalog metric cannot bind a foreign construct."""
    fixture = build_lane01_candidate_source(
        tmp_path, monkeypatch, profile=GDP_PROFILE, compiler_input=GDP_COMPILER_INPUT
    )
    scope = _compiled_source_scope(fixture)
    candidate = scope["candidate"]
    forged = candidate.model_copy(update={"construct_ref": "construct:unrelated.gdp"})
    assert forged.content_digest == candidate.content_digest
    assert forged.descriptor == candidate.descriptor
    assert fixture.entry.upstream_metric_id == "gdp"
    with pytest.raises(ValueError, match="candidate_source_descriptor_scope_mismatch"):
        _validate_scope(**(scope | {"candidate": forged}))


@pytest.mark.parametrize("wrong_metric", ["economic.gdp", "unrelated_metric"])
def test_source_owner_refuses_forged_fetch_metric_with_canonical_construct_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wrong_metric: str
) -> None:
    """Coherently compiled descriptor bytes must still match the independent Catalog metric."""
    governed = RequirementToCapabilityResolver.governed_fixture()
    capabilities = []
    for capability in governed.capabilities:
        if capability.construct_id != GDP_PROFILE.construct:
            capabilities.append(capability)
            continue
        (asset,) = capability.source_assets
        fetch = asset.metadata["catalog_fetch_binding"] | {"metric_id": wrong_metric}
        capabilities.append(
            capability.model_copy(
                update={
                    "source_assets": (
                        asset.model_copy(
                            update={"metadata": asset.metadata | {"catalog_fetch_binding": fetch}}
                        ),
                    )
                }
            )
        )
    resolver = RequirementToCapabilityResolver(
        capabilities=capabilities,
        capability_index_ref="capability-index:test-forged-gdp-catalog-metric",
    )
    with pytest.raises(ValueError, match="candidate_source_descriptor_scope_mismatch"):
        build_lane01_candidate_source(
            tmp_path,
            monkeypatch,
            profile=GDP_PROFILE,
            compiler_input=GDP_COMPILER_INPUT,
            capability_resolver=resolver,
        )
