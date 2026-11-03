"""Test-only native epoch queries bind each profile's real selected scope."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from tests._helpers.acquisition_epoch_production import production_admission_inputs
from tests._helpers.lane01_wdi_profiles import (
    GDP_PROFILE,
    UNEMPLOYMENT_PROFILE,
    CandidateWDIProfile,
    build_fixture_wdi_authority,
)


@pytest.mark.parametrize(
    ("profile", "domain"), [(GDP_PROFILE, "fiscal"), (UNEMPLOYMENT_PROFILE, "labor")]
)
def test_fixture_native_epoch_uses_explicit_profile_scope(
    tmp_path: Path, profile: CandidateWDIProfile, domain: str
) -> None:
    authority, _ = build_fixture_wdi_authority(tmp_path / "repo", profile)
    scope = {
        "domain": domain,
        "jurisdiction": profile.country_code,
        "year": profile.year,
        "population": profile.population,
    }
    selected = production_admission_inputs(
        tmp_path,
        store=FileSystemCAS(tmp_path / "cas"),
        authority=authority,
        overlay_path=tmp_path / "overlay.duckdb",
        epoch_history_root=tmp_path / "history",
        scope_payload=scope,
        authority_purpose="candidate_simulation",
    )
    assert json.loads(selected["epoch_scope_identity"].identity_bytes) == scope
    assert selected["authority_purpose"] == "candidate_simulation"
