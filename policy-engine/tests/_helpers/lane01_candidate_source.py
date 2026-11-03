"""Real compiler and controlled WDI/Fabric candidate-source test fixture."""

from __future__ import annotations

import socket
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

import aiohttp
import pytest

from polisyos.core import artifacts
from polisyos.data_forge.read_api import catalog
from polisyos.data_requirement import DataRequirementCompilationReport, DataRequirementCompiler
from polisyos.runtime.quality.acquisition_executor import (
    LiveCatalogExecutionConstraints,
    execute_live_catalog_acquisition,
)
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionRequirementBasisBinding,
    persist_and_verify_data_requirement_compilation_report,
)
from polisyos.runtime.quality.candidate_acquisition_source import (
    CandidateAcquisitionSource,
    persist_candidate_acquisition_source,
    read_candidate_acquisition_source,
)
from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver
from tests._helpers.lane01_wdi_profiles import (
    UNEMPLOYMENT_PROFILE,
    CandidateWDIProfile,
    build_fixture_wdi_authority,
    fixture_wdi_response,
)


@dataclass(frozen=True, slots=True)
class Lane01CandidateSourceFixture:
    """Keep the actual selected candidate source and its owner inputs together."""

    store: artifacts.ArtifactStore
    authority: catalog.CanonicalAcquisitionAuthority
    entry: catalog.AcquisitionAuthorityEntry
    evidence: catalog.LiveSourceExecutionEvidence
    binding: AcquisitionRequirementBasisBinding
    requirement_id: str
    candidate_digest: str
    source_ref: artifacts.ArtifactRef
    source: CandidateAcquisitionSource


def compile_lane01_candidate_report(
    *,
    scenario_id: str = "lane01-unemployment",
    lifecycle_override: Literal["draft", "governed", "active", "deprecated", "withdrawn"]
    | None = None,
) -> DataRequirementCompilationReport:
    """Compile the real scoped candidate-discovery requirement for one scenario."""
    resolver = RequirementToCapabilityResolver.governed_fixture()
    if lifecycle_override is not None:
        capabilities = tuple(
            capability.model_copy(
                update={
                    "capability_lifecycle": capability.capability_lifecycle.model_copy(
                        update={"state": lifecycle_override}
                    )
                }
            )
            if capability.construct_id == "labor.unemployment_rate"
            else capability
            for capability in resolver.capabilities
        )
        resolver = RequirementToCapabilityResolver(
            capabilities=capabilities,
            failure_modes=resolver.failure_modes,
            acquisition_strategies=resolver.acquisition_strategies,
            conflicts=resolver.conflicts,
            capability_index_ref=f"capability-index:controlled-lifecycle-{lifecycle_override}",
        )
    return DataRequirementCompiler(
        capability_resolver=resolver, require_capability_index=True
    ).compile_for_scenario(
        {
            "scenario_id": scenario_id,
            "text": "Assess employment policy using the annual unemployment rate in the United States.",
            "domain": "social",
            "scope_profile": {
                "profile_id": "scope:lane01-unemployment-usa-2024:v1",
                "jurisdiction": "USA",
                "population": "total_labor_force",
                "entity_scope": "country",
                "time_window": {"start": "2024-01-01", "end": "2024-12-31"},
                "time_role": "observation_time",
                "granularity": "annual",
                "required_constructs": ["labor.unemployment_rate"],
            },
        }
    )


def build_lane01_candidate_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    store: artifacts.ArtifactStore | None = None,
    tenant_id: str = "tenant-lane01",
    cell_id: str = "cell-lane01",
    run_id: str = "run-lane01",
    job_id: str = "job-lane01",
    route_id: str = "route-lane01",
    profile: CandidateWDIProfile = UNEMPLOYMENT_PROFILE,
    response_body: bytes | None = None,
    declared_population: str | None = None,
    lifecycle_override: Literal["draft", "governed", "active", "deprecated", "withdrawn"]
    | None = None,
) -> Lane01CandidateSourceFixture:
    """Compile a real scoped requirement and execute one intercepted source request."""
    report = compile_lane01_candidate_report(lifecycle_override=lifecycle_override)
    matches = [
        resolution
        for resolution in (report.capability_requirement_resolutions or ())
        if resolution.query.construct == "labor.unemployment_rate"
        and resolution.candidate_discovery is not None
        and resolution.candidate_discovery.candidates
    ]
    if len(matches) != 1 or len(matches[0].candidate_discovery.candidates) != 1:
        raise AssertionError("real compiler must select one candidate discovery")
    selected = matches[0]
    requirement_id = selected.query.requirement_id
    candidate_digest = selected.candidate_discovery.candidates[0].content_digest
    artifact_store = store if store is not None else artifacts.FileSystemCAS(tmp_path / "cas")
    binding = persist_and_verify_data_requirement_compilation_report(
        artifact_store, report, expected_scenario_id="lane01-unemployment"
    )
    authority, entry = build_fixture_wdi_authority(tmp_path / "repo", profile)
    body = fixture_wdi_response(profile) if response_body is None else response_body

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
        assert method == "GET"
        assert str(url).endswith(
            f"/country/{profile.country_code}/indicator/{profile.indicator_id}"
        )
        assert isinstance(kwargs["params"], Mapping)
        return Response()

    def forbid_socket(*args: object, **kwargs: object) -> None:
        del args, kwargs
        pytest.fail("controlled WDI fixture attempted a network socket")

    monkeypatch.setattr(aiohttp.ClientSession, "_request", intercept)
    monkeypatch.setattr(socket.socket, "connect", forbid_socket)
    monkeypatch.setattr(socket.socket, "connect_ex", forbid_socket)
    root = getattr(artifact_store, "root")  # noqa: B009 - protocol does not require a root
    evidence = execute_live_catalog_acquisition(
        authority=authority,
        entry_id=entry.entry_id,
        attempt_id="lane01-fixture-wdi-001",
        constraints=LiveCatalogExecutionConstraints(
            country_code=profile.country_code,
            start_year=profile.year,
            end_year=profile.year,
            page_size=1000,
            max_response_bytes=65_536,
            max_decompressed_bytes=65_536,
            timeout_cap_seconds=15.0,
            heartbeat_cap_seconds=5.0,
        ),
        journal_path=tmp_path / "journal.jsonl",
        cas_root=root,
        artifact_store=artifact_store,
    )
    source_ref = persist_candidate_acquisition_source(
        artifact_store,
        authority=authority,
        entry_id=entry.entry_id,
        live_source_execution=evidence,
        requirement_basis_binding=binding,
        requirement_id=requirement_id,
        candidate_digest=candidate_digest,
        target_slot_id=profile.target_slot,
        country_code=profile.country_code,
        year=profile.year,
        population=profile.population if declared_population is None else declared_population,
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_id=run_id,
        job_id=job_id,
        route_id=route_id,
    )
    source = read_candidate_acquisition_source(artifact_store, source_ref=source_ref)
    return Lane01CandidateSourceFixture(
        store=artifact_store,
        authority=authority,
        entry=entry,
        evidence=evidence,
        binding=binding,
        requirement_id=requirement_id,
        candidate_digest=candidate_digest,
        source_ref=source_ref,
        source=source,
    )
