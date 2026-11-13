"""Native acquisition fixture follows one live Catalog and epoch history."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import TYPE_CHECKING

import aiohttp
import pytest
from aiohttp import web

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.security.authz import AuthzInput
from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    AcquisitionAuthorityError,
    AcquisitionAuthorityRegistry,
    build_authority_registry,
)
from polisyos.data_forge.domains.catalog.knowledge.overlay import OverlayAdmissionError
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
from polisyos.runtime.http.deployment_security import DeploymentOPAClient, OPADeploymentConfig
from tests._helpers.lane01_wdi_profiles import GDP_PROFILE, CandidateWDIProfile
from tests._helpers.semantic_epoch_native import (
    _install_native_live_source_transport,
    make_native_live_measurement_history,
)
from tests.integration.runtime_quality.test_program_graph_held_out_fund_binding import _fund_port
from tests.unit.runtime.quality.test_model_input_requirements import _opening_stock_port

if TYPE_CHECKING:
    from pathlib import Path


def test_live_source_transport_is_isolated_from_real_opa_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fixture transport fences the source while the real OPA client can POST."""

    async def scenario() -> None:
        original_request = aiohttp.ClientSession._request
        original_get_session = WorldBankConnector._get_session
        fixture = SimpleNamespace(
            profile=GDP_PROFILE,
            response_body=None,
            transport_calls=0,
            used_attempts=[],
        )
        received: list[dict[str, object]] = []

        async def opa(request: web.Request) -> web.Response:
            received.append(await request.json())
            return web.json_response({"result": {"allow": False, "reason": "test-denial"}})

        app = web.Application()
        app.router.add_post("/v1/data/polisyos/authz/decision", opa)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        assert site._server is not None
        port = site._server.sockets[0].getsockname()[1]
        connector = WorldBankConnector()
        handle = await connector.connect(ConnectionConfig(url=WorldBankConnector._BASE_URL))
        url = (
            f"{WorldBankConnector._BASE_URL}/country/{GDP_PROFILE.country_code}"
            f"/indicator/{GDP_PROFILE.indicator_id}"
        )
        params = {
            "date": f"{GDP_PROFILE.year}:{GDP_PROFILE.year}",
            "format": "json",
            "page": "1",
            "per_page": "1000",
        }
        try:
            with monkeypatch.context() as source_patch:
                _install_native_live_source_transport(source_patch, fixture)
                assert aiohttp.ClientSession._request is original_request
                session = await connector._get_session(handle)
                with pytest.raises(
                    AssertionError, match="native_live_fixture_unexpected_transport"
                ):
                    async with session.get(url, params=params):
                        pass

                fixture.response_body = b'{"controlled":true}'
                fixture.used_attempts.append("test-attempt")
                for method, invalid_url, invalid_params in (
                    ("POST", url, params),
                    ("GET", url.replace("api.worldbank.org", "invalid.example"), params),
                    ("GET", url + "/unexpected", params),
                    ("GET", url, {**params, "page": "2"}),
                ):
                    with pytest.raises(
                        AssertionError, match="native_live_fixture_unexpected_transport"
                    ):
                        async with session.request(method, invalid_url, params=invalid_params):
                            pass

                opa_client = DeploymentOPAClient(
                    OPADeploymentConfig(url=f"http://127.0.0.1:{port}")
                )
                authz = AuthzInput(
                    request_method="POST",
                    request_path="/test/action",
                    request_headers={},
                    identity_tenant_id="test-tenant",
                    identity_cell_id="test-cell",
                    identity_principal_type="service",
                    identity_roles=frozenset(),
                    identity_mfa_verified=False,
                )
                result = await opa_client._query_opa(authz)
                assert result == {"allow": False, "reason": "test-denial"}
                assert received == [{"input": authz.to_opa_input()}]

                async with session.get(url, params=params) as response:
                    assert await response.read() == fixture.response_body
                assert fixture.transport_calls == 1
                with pytest.raises(
                    AssertionError, match="native_live_fixture_unexpected_transport"
                ):
                    async with session.get(url, params=params):
                        pass
                fixture.response_body = None
                with pytest.raises(
                    AssertionError, match="native_live_fixture_unexpected_transport"
                ):
                    async with session.get(url, params=params):
                        pass
            assert WorldBankConnector._get_session is original_get_session
        finally:
            await connector.disconnect(handle)
            await runner.cleanup()

    asyncio.run(scenario())


def test_live_fixture_admits_distinct_fetches_under_one_native_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same source can return revised values without changing its route."""
    store = FileSystemCAS(tmp_path / "cas")
    port = _fund_port(store, _opening_stock_port(store), fund="treasury")
    profile = CandidateWDIProfile(
        construct="test.treasury.opening-cash",
        indicator_id="POLICYOS.FIXTURE.TREASURY.STOCK",
        source_title="Test-owned annual treasury stock (current US$)",
        source_description="Controlled test responses; no external empirical source is asserted.",
        target_slot="test.treasury.opening-cash",
        raw_unit="usd",
        canonical_unit="usd",
        transform="identity",
        transform_ref="fabric://units/usd-identity/v1",
        population="population:treasury",
        fixture_value=640.0,
        source_provenance_class="observed",
        valid_min=0.0,
        valid_max=10_000.0,
        country_code="UKR",
        country_id="UA",
        year=2022,
    )
    history = make_native_live_measurement_history(
        tmp_path / "source",
        profile=profile,
        semantic_definition_ref=port.semantic_definition_ref,
        representation_ref=port.representation_ref,
        attempt_ids=("fixture-A", "fixture-B", "fixture-C"),
        artifact_store=store,
        monkeypatch=monkeypatch,
        source_measure_scope={
            "population": "population:treasury",
            "temporal_granularity": "annual",
            "source_geography_id": "UA",
            "geography_ref": "UA",
            "jurisdiction_ref": "UA",
            "time_period_basis": "calendar_year",
        },
    )
    try:
        source = history.authority.resolve(history.entry.entry_id)
        assert source.entry.source_semantic_definition_ref == port.semantic_definition_ref
        assert source.entry.source_representation_ref == port.representation_ref
        declared_scope = source.entry.source_measure_scope
        assert declared_scope is not None
        assert declared_scope.population == "population:treasury"
        assert declared_scope.source_geography_id == "UA"
        assert declared_scope.geography_ref == "UA"
        assert declared_scope.jurisdiction_ref == "UA"
        assert declared_scope.time_period_basis == "calendar_year"
        assert port.scope.population_ref == "population:treasury"
        assert port.scope.geography_ref == port.scope.jurisdiction_ref == "UA"
        original_registry = source.registry_content_sha256
        original_provision = source.authority_provision_content_sha256
        admissions = tuple(history.admit(value) for value in (640.0, 640.0, 602.5))
        assert history.transport_calls == 3
        assert [item.evidence.authorization.attempt_id for item in admissions] == [
            "fixture-A",
            "fixture-B",
            "fixture-C",
        ]
        assert all(item.authority is history.authority for item in admissions)
        assert all(item.overlay is history.overlay for item in admissions)
        assert all(item.passport.source_lane == "live_fetch" for item in admissions)
        assert all(item.passport.source_authority_verified for item in admissions)
        assert all(item.passport.field_binding.canonical_unit == "usd" for item in admissions)
        assert all(
            item.passport.source_watermark == item.evidence.raw_body_sha256 for item in admissions
        )
        assert all(
            item.finalized.case.scenario.candidate.statement.source_record_ref.artifact_id
            == item.evidence.normalized_data_artifact_id
            for item in admissions
        )
        assert all(
            item.evidence.raw_artifact_id != item.evidence.normalized_data_artifact_id
            for item in admissions
        )
        assert all(item.passport.license_evidence.license_id == "CC-BY-4.0" for item in admissions)
        assert all(
            item.passport.authority_entry_id == history.entry.entry_id for item in admissions
        )
        assert all(
            item.passport.authority_registry_content_sha256 == original_registry
            for item in admissions
        )
        assert all(
            item.passport.authority_provision_content_sha256 == original_provision
            for item in admissions
        )
        assert len({item.passport.passport_id for item in admissions}) == 3
        assert (
            len({str(item.finalized.activated.receipt_ref.artifact_id) for item in admissions}) == 3
        )
        rows = [item.projections[history.entry.target_variable].observations for item in admissions]
        assert [row[0].observation.value for row in rows] == [640.0, 640.0, 602.5]
        assert all(len(row) == 1 for row in rows)
        assert all(row[0].observation.year == 2022 for row in rows)
        assert all(row[0].observation.country_code == "UKR" for row in rows)
        assert all(
            json.loads(row[0].observation.condition_json)
            == {
                "population_ref": "population:treasury",
                "geography_ref": "UA",
                "jurisdiction_ref": "UA",
                "time_period_basis": "calendar_year",
            }
            for row in rows
        )
        assert admissions[0].evidence.raw_body_sha256 == admissions[1].evidence.raw_body_sha256
        assert admissions[1].evidence.raw_body_sha256 != admissions[2].evidence.raw_body_sha256
        for item in admissions:
            reread = history.overlay.read_activated_semantic_epoch_observations(
                receipt_ref=item.finalized.activated.receipt_ref,
                artifact_store=store,
                passport=item.passport,
                authority=history.authority,
            )
            assert reread == item.projections[history.entry.target_variable]

        # Fresh owner readback must respect an updated registry, while the
        # historical, signed receipt remains intact and readable on restoration.
        registry_path = history.authority.registry_path
        registry_bytes = registry_path.read_bytes()
        original = AcquisitionAuthorityRegistry.model_validate_json(registry_bytes)
        withdrawn = build_authority_registry(
            baseline_content_sha256=original.baseline_content_sha256,
            l5_measurement_registry_sha256=original.l5_measurement_registry_sha256,
            entries=(),
        )
        assert withdrawn.content_sha256 != original.content_sha256
        try:
            registry_path.write_text(withdrawn.model_dump_json(), encoding="utf-8")
            with pytest.raises(OverlayAdmissionError, match="acquisition_authority_unresolved"):
                history.overlay.read_activated_semantic_epoch_observations(
                    receipt_ref=admissions[0].finalized.activated.receipt_ref,
                    artifact_store=store,
                    passport=admissions[0].passport,
                    authority=history.authority,
                )
        finally:
            registry_path.write_bytes(registry_bytes)
        assert (
            history.overlay.read_activated_semantic_epoch_observations(
                receipt_ref=admissions[0].finalized.activated.receipt_ref,
                artifact_store=store,
                passport=admissions[0].passport,
                authority=history.authority,
            )
            == admissions[0].projections[history.entry.target_variable]
        )

        with pytest.raises(
            AcquisitionAuthorityError, match="live_harness_receipt_provision_unresolved"
        ):
            history.authority.resolve_live_harness_receipt(
                history.entry.entry_id, "fixture-unknown"
            )
        provisioned = next(
            receipt
            for receipt in history.authority.provision.live_harness_receipts
            if receipt.attempt_id == "fixture-B"
        )
        receipt_path = history.repo_root / provisioned.relative_path()
        receipt_bytes = receipt_path.read_bytes()
        try:
            receipt_path.write_bytes(receipt_bytes + b" ")
            with pytest.raises(
                AcquisitionAuthorityError, match="live_harness_receipt_content_drift"
            ):
                history.authority.resolve_live_harness_receipt(history.entry.entry_id, "fixture-B")
        finally:
            receipt_path.write_bytes(receipt_bytes)
        history.authority.resolve_live_harness_receipt(history.entry.entry_id, "fixture-B")
        with pytest.raises(ValueError, match="attempt_not_available"):
            history.admit(1.0)
    finally:
        history.overlay.close()
