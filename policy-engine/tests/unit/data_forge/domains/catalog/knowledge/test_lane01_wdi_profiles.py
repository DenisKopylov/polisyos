"""Actual catalog authority resolves two isolated synthetic source contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests._helpers.lane01_wdi_profiles import (
    GDP_PROFILE,
    UNEMPLOYMENT_PROFILE,
    CandidateWDIProfile,
    build_fixture_wdi_authority,
    fixture_wdi_response,
)


@pytest.mark.parametrize("profile", [GDP_PROFILE, UNEMPLOYMENT_PROFILE])
def test_owned_catalog_binds_exact_declared_wdi_contract(
    tmp_path: Path, profile: CandidateWDIProfile
) -> None:
    authority, entry = build_fixture_wdi_authority(tmp_path, profile)
    resolved = authority.resolve(entry.entry_id)
    binding = resolved.field_binding
    assert resolved.registration.connector_id == "worldbank.wdi"
    assert resolved.registration.request_dataset_id == profile.indicator_id
    assert resolved.registration.country_codes == (profile.country_code,)
    assert resolved.registration.temporal_start == str(profile.year)
    assert resolved.registration.temporal_end == str(profile.year)
    assert binding.canonical_variable == profile.target_slot
    assert (binding.raw_unit, binding.canonical_unit) == (
        profile.raw_unit,
        profile.canonical_unit,
    )
    assert binding.unit_transform == profile.transform
    assert binding.aggregation_method == "identity"
    if profile is UNEMPLOYMENT_PROFILE:
        assert (binding.valid_min, binding.valid_max) == (0.0, 1.0)

    response = json.loads(fixture_wdi_response(profile))
    assert len(response[1]) == 1
    (row,) = response[1]
    assert row["indicator"]["id"] == profile.indicator_id
    assert row["countryiso3code"] == profile.country_code
    assert row["country"]["id"] == profile.country_id
    assert row["date"] == str(profile.year)
    assert row["value"] == profile.fixture_value
