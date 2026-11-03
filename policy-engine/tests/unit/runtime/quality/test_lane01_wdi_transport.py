"""Actual WDI/Fabric transport against two test-owned, bounded source profiles."""

from __future__ import annotations

import socket
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import aiohttp
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    AcquisitionAuthorityError,
)
from polisyos.data_forge.domains.catalog.knowledge.overlay import (
    ObservationProvenanceClass,
    derive_canonical_observations,
)
from polisyos.runtime.quality.acquisition_executor import (
    LiveAcquisitionExecutionError,
    LiveCatalogExecutionConstraints,
    execute_live_catalog_acquisition,
)
from tests._helpers.lane01_wdi_profiles import (
    GDP_PROFILE,
    UNEMPLOYMENT_PROFILE,
    CandidateWDIProfile,
    build_fixture_wdi_authority,
    fixture_wdi_response,
)


def _constraints(
    profile: CandidateWDIProfile, *, country: str | None = None, year: int | None = None
):
    selected_year = profile.year if year is None else year
    return LiveCatalogExecutionConstraints(
        country_code=country or profile.country_code,
        start_year=selected_year,
        end_year=selected_year,
        page_size=1000,
        max_response_bytes=65_536,
        max_decompressed_bytes=65_536,
        timeout_cap_seconds=15.0,
        heartbeat_cap_seconds=5.0,
    )


@pytest.mark.parametrize("profile", [GDP_PROFILE, UNEMPLOYMENT_PROFILE])
def test_native_connector_reopens_exact_profile_and_rejects_missing_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: CandidateWDIProfile
) -> None:
    authority, entry = build_fixture_wdi_authority(tmp_path / "repo", profile)
    body = fixture_wdi_response(profile)
    calls: list[tuple[str, str, dict[str, str]]] = []

    class Response:
        status = 200
        headers: ClassVar[dict[str, str]] = {"content-type": "application/json"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            del args

        async def read(self) -> bytes:
            return body

        def release(self) -> None:
            pass

        async def wait_for_close(self) -> None:
            pass

        def close(self) -> None:
            pass

    async def intercept(_session: object, method: str, url: object, **kwargs: object):
        params = kwargs["params"]
        assert isinstance(params, Mapping)
        calls.append((method, str(url), {str(k): str(v) for k, v in params.items()}))
        return Response()

    def forbid_socket(*args: object, **kwargs: object) -> None:
        del args, kwargs
        pytest.fail("controlled WDI fixture attempted a network socket")

    monkeypatch.setattr(aiohttp.ClientSession, "_request", intercept)
    monkeypatch.setattr(socket.socket, "connect", forbid_socket)
    monkeypatch.setattr(socket.socket, "connect_ex", forbid_socket)
    store = FileSystemCAS(tmp_path / "cas")
    evidence = execute_live_catalog_acquisition(
        authority=authority,
        entry_id=entry.entry_id,
        attempt_id="lane01-fixture-wdi-001",
        constraints=_constraints(profile),
        journal_path=tmp_path / "journal.jsonl",
        cas_root=tmp_path / "cas",
        artifact_store=store,
    )
    assert len(calls) == 1
    assert calls[0][0] == "GET"
    assert calls[0][1].endswith(f"/country/{profile.country_code}/indicator/{profile.indicator_id}")
    assert calls[0][2]["date"] == f"{profile.year}:{profile.year}"
    reopened = authority.resolve_live_source_execution(entry.entry_id, evidence, store)
    assert reopened.row_count == 1
    assert reopened.data.iloc[0]["value"] == profile.fixture_value
    assert reopened.data.iloc[0]["country_code"] == profile.country_code
    assert reopened.data.iloc[0]["year"] == profile.year

    normalized = authority.resolve_live_source_body(entry.entry_id, evidence, store)
    (observation,) = derive_canonical_observations(
        normalized,
        passport=SimpleNamespace(
            epoch_id=1,
            source_watermark=evidence.raw_body_sha256,
            dataset_version="controlled-test-release",
            observation_class=(
                ObservationProvenanceClass.MODEL_OUTPUT
                if profile is UNEMPLOYMENT_PROFILE
                else ObservationProvenanceClass.OBSERVED
            ),
        ),
        registration=authority.resolve(entry.entry_id).registration,
    )
    expected = (
        profile.fixture_value / 100 if profile is UNEMPLOYMENT_PROFILE else profile.fixture_value
    )
    assert observation.value == pytest.approx(expected)
    assert (observation.country_code, observation.year) == (profile.country_code, profile.year)
    if profile is UNEMPLOYMENT_PROFILE:
        assert observation.observation_class is ObservationProvenanceClass.MODEL_OUTPUT

    get_bytes = store.get_bytes

    def refuse_normalized_bytes(artifact_id: object):
        if str(artifact_id) == str(evidence.normalized_data_artifact_id):
            raise FileNotFoundError("controlled source removal")
        return get_bytes(artifact_id)

    with monkeypatch.context() as scoped:
        scoped.setattr(store, "get_bytes", refuse_normalized_bytes)
        with pytest.raises(AcquisitionAuthorityError, match="live_source_execution_invalid"):
            authority.resolve_live_source_execution(entry.entry_id, evidence, store)


@pytest.mark.parametrize("profile", [GDP_PROFILE, UNEMPLOYMENT_PROFILE])
@pytest.mark.parametrize("mismatch", ["country", "period"])
def test_wrong_scope_is_refused_before_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: CandidateWDIProfile, mismatch: str
) -> None:
    authority, entry = build_fixture_wdi_authority(tmp_path / "repo", profile)

    async def refuse_transport(*args: object, **kwargs: object):
        del args, kwargs
        pytest.fail("out-of-scope source reached transport")

    monkeypatch.setattr(aiohttp.ClientSession, "_request", refuse_transport)
    constraints = (
        _constraints(profile, country="DEU")
        if mismatch == "country"
        else _constraints(profile, year=2023)
    )
    with pytest.raises(LiveAcquisitionExecutionError, match="outside_authority_"):
        execute_live_catalog_acquisition(
            authority=authority,
            entry_id=entry.entry_id,
            attempt_id="lane01-fixture-wdi-001",
            constraints=constraints,
            journal_path=tmp_path / "journal.jsonl",
            cas_root=tmp_path / "cas",
            artifact_store=FileSystemCAS(tmp_path / "cas"),
        )
