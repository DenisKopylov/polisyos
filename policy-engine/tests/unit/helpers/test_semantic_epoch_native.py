"""Native acquisition fixture follows one live Catalog and epoch history."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    AcquisitionAuthorityError,
    AcquisitionAuthorityRegistry,
    build_authority_registry,
)
from polisyos.data_forge.domains.catalog.knowledge.overlay import OverlayAdmissionError
from tests._helpers.lane01_wdi_profiles import CandidateWDIProfile
from tests._helpers.semantic_epoch_native import make_native_live_measurement_history
from tests.integration.runtime_quality.test_program_graph_held_out_fund_binding import _fund_port
from tests.unit.runtime.quality.test_model_input_requirements import _opening_stock_port

if TYPE_CHECKING:
    from pathlib import Path


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
