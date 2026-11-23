from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from polisyos.core import artifacts
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.data_forge.read_api import catalog
from polisyos.runtime.http.services.acquisition_surface_execution import (
    _require_live_variable_route,
)
from polisyos.runtime.quality import generation_cycle
from polisyos.runtime.quality.acquisition_executor import (
    LiveAcquisitionExecutionError,
    LiveCatalogExecutionConstraints,
)
from polisyos.runtime.quality.acquisition_planner import (
    OrdinaryAcquisitionOffer,
    OrdinaryAcquisitionOfferScope,
    verify_ordinary_acquisition_offers,
)
from tests._helpers.acquisition_production import install_fixture_wdi_cost_basis, persist_wdi_route
from tests._helpers.lane01_wdi_profiles import (
    CandidateWDIProfile,
    FixtureWDIRoleBinding,
    build_fixture_wdi_authority_bundle,
)
from tests._helpers.runtime_http import _build_control_service
from tests.unit.runtime.quality.test_substrate_registry import _write_substrate_catalog_fixture

if TYPE_CHECKING:
    from pathlib import Path


_VARIABLE = "government.balance"
_ORIGINAL_DATASET = "GC.BAL.CASH.GD.ZS"
_ALTERNATE_DATASET = "GC.BAL.FIXTURE.ZS"


def _controlled_supplier_refs(
    repo_root: Path, store: artifacts.FileSystemCAS
) -> tuple[catalog.CanonicalAcquisitionAuthority, tuple[artifacts.ArtifactRef, ...]]:
    """Configure real Catalog edges for tests of source and geography selection."""
    original = CandidateWDIProfile(
        construct="fiscal.government_balance",
        indicator_id=_ORIGINAL_DATASET,
        source_title="Government cash balance (% of GDP)",
        source_description="Annual government cash balance as a share of GDP.",
        target_slot=_VARIABLE,
        raw_unit="percent_gdp",
        canonical_unit="percent_gdp",
        transform="identity",
        transform_ref="fabric://units/percent-gdp-identity/v1",
        population="central_government",
        fixture_value=1.0,
        source_provenance_class="observed",
        country_code="UKR",
        country_id="UA",
        year=2024,
        catalog_metric_id="gov_balance",
    )
    profiles = (
        original,
        replace(
            original,
            target_slot="fixture.government_balance_alternative",
            indicator_id=_ALTERNATE_DATASET,
        ),
        replace(original, target_slot="fixture.government_balance_alias"),
        replace(
            original,
            target_slot="fixture.government_balance_foreign",
            indicator_id="GC.BAL.FIXTURE.USA.ZS",
            country_code="USA",
            country_id="US",
        ),
    )
    authority, produced = build_fixture_wdi_authority_bundle(
        repo_root,
        profiles,
        role_bindings={
            profile.target_slot: FixtureWDIRoleBinding(attempt_ids=(f"offer-{index}",))
            for index, profile in enumerate(profiles)
        },
    )
    # The fixture builder uses distinct target names to make independent Catalog
    # edges. The deployment aligns those edges to the same canonical variable.
    entries = []
    for entry in produced:
        values = dict(entry)
        del values["entry_id"]
        values["target_variable"] = _VARIABLE
        entries.append(catalog.build_authority_entry(**values))
    registry = catalog.build_authority_registry(
        baseline_content_sha256=authority.provision.baseline_content_sha256,
        l5_measurement_registry_sha256=authority.provision.l5_measurement_registry_content_sha256,
        entries=tuple(entries),
    )
    authority.registry_path.write_text(
        json.dumps(registry.model_dump(mode="json"), sort_keys=True), encoding="utf-8"
    )
    entry_ids = {old.entry_id: new.entry_id for old, new in zip(produced, entries, strict=True)}
    receipt_provisions = [
        {**receipt.model_dump(mode="json"), "entry_id": entry_ids[receipt.entry_id]}
        for receipt in authority.provision.live_harness_receipts
    ]
    receipt_provisions.sort(key=lambda row: (row["entry_id"], row["attempt_id"]))
    provision = catalog.build_acquisition_authority_provision(
        baseline_owner_ref=authority.provision.baseline_owner_ref,
        baseline_content_sha256=authority.provision.baseline_content_sha256,
        l5_measurement_registry_owner_ref=authority.provision.l5_measurement_registry_owner_ref,
        l5_measurement_registry_content_sha256=(
            authority.provision.l5_measurement_registry_content_sha256
        ),
        live_harness_receipts=tuple(receipt_provisions),
    )
    (repo_root / catalog.DEFAULT_ACQUISITION_AUTHORITY_PROVISION).write_text(
        json.dumps(provision.model_dump(mode="json"), sort_keys=True), encoding="utf-8"
    )
    authority = catalog.CanonicalAcquisitionAuthority.from_provision(
        repo_root=repo_root, baseline_path=authority.baseline_path
    )
    return authority, tuple(
        catalog.persist_acquisition_supplier_declaration(store, authority, entry_id=entry.entry_id)
        for entry in entries
    )


@pytest.mark.asyncio
async def test_costed_n7_offers_require_distinct_catalog_fetches_and_current_scope_price(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(generation_cycle, "_N7_SOURCE_SEMANTIC_EMISSION_ENABLED", True)
    install_fixture_wdi_cost_basis(monkeypatch)
    substrate = tmp_path / "substrate"
    _write_substrate_catalog_fixture(substrate)
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    control = _build_control_service(tmp_path / "control", artifact_store=store)
    try:
        route, _ = await persist_wdi_route(control, generation_cycle_repo_root=substrate)
        assert _require_live_variable_route(route) == _VARIABLE
        record = route.planner_record
        gap = route.source_cycle.value_port.acquisition_requirement
        plan_ref = route.source_cycle.acquisition_routing_report_ref
        job = control._control_store.get_job(route.source_job_id)
        assert job is not None
        assert gap is not None and plan_ref is not None and record.compiled_requirement_ref
        with tenant_scope(None, tenant_id=route.tenant_id, cell_id=route.cell_id):
            # The ordinary compiled cycle stores the legacy default pointer.
            selected_plan_ref = artifacts.artifact_ref_for_manifest(store.get_manifest(plan_ref))
        scope = OrdinaryAcquisitionOfferScope(
            tenant_id=route.tenant_id,
            cell_id=route.cell_id,
            run_id=route.run_id,
            source_job_id=route.source_job_id,
            design_problem_ref=route.design_problem_ref,
            candidate_id=route.source_cycle.selected_candidate_ref,
            compiled_ref=artifacts.ArtifactRef.model_validate(
                job.progress["compiled_recursive_generation_cycle_artifact_ref"]
            ),
            scenario_id=route.design_problem.design_problem_id,
            planner_report_ref=selected_plan_ref,
            planner_record_id=record.acquisition_id,
            compiled_requirement_ref=record.compiled_requirement_ref,
            source_gap_id=gap.requirement_gap_id,
            canonical_variable_id=_VARIABLE,
            canonical_unit="percent_gdp",
            country_code=route.design_problem.jurisdiction_time.region,
            year=int(route.design_problem.jurisdiction_time.data_time),
        )
        constraints = LiveCatalogExecutionConstraints(
            country_code=scope.country_code,
            start_year=scope.year,
            end_year=scope.year,
            page_size=1_000,
            max_response_bytes=65_536,
            max_decompressed_bytes=65_536,
            timeout_cap_seconds=15.0,
            heartbeat_cap_seconds=5.0,
        )
        now = datetime(2026, 11, 19, tzinfo=UTC)
        with tenant_scope(None, tenant_id=scope.tenant_id, cell_id=scope.cell_id):
            authority, refs = _controlled_supplier_refs(tmp_path / "offers", store)
            original, alternative, alias, foreign_supplier = (
                OrdinaryAcquisitionOffer(
                    scope=scope,
                    supplier_ref=ref,
                    cost_basis_hash=route.cost_basis_hash,
                    effective_at=now - timedelta(days=1),
                    expires_at=now + timedelta(days=1 + index),
                )
                for index, ref in enumerate(refs)
            )

            def verify(*offers: OrdinaryAcquisitionOffer) -> tuple[str, ...]:
                reopened = verify_ordinary_acquisition_offers(
                    store,
                    authority=authority,
                    scope=scope,
                    planner_report=route.planner_report,
                    cost_basis=route.cost_basis_record,
                    constraints=constraints,
                    offers=offers,
                    now=now,
                )
                assert all(result.cost_basis == route.cost_basis_record for result in reopened)
                return tuple(result.source.registration.request_dataset_id for result in reopened)

            assert verify(original, alternative) == (_ORIGINAL_DATASET, _ALTERNATE_DATASET)
            assert verify(alias) == (_ORIGINAL_DATASET,)
            assert original.supplier_ref != alias.supplier_ref
            assert original.content_hash != alias.content_hash
            with pytest.raises(ValueError, match="ordinary_acquisition_offer_source_not_distinct"):
                verify(original, alias)
            with pytest.raises(ValueError, match="ordinary_acquisition_offer_scope_mismatch"):
                verify(
                    original,
                    alternative.model_copy(
                        update={"scope": scope.model_copy(update={"candidate_id": "foreign"})}
                    ),
                )
            with pytest.raises(
                LiveAcquisitionExecutionError, match="live_request_outside_authority_countries"
            ):
                verify(original, foreign_supplier)
            with pytest.raises(ValueError, match="ordinary_acquisition_offer_not_current"):
                verify(original, alternative.model_copy(update={"expires_at": now}))
            with pytest.raises(ValueError, match="ordinary_acquisition_offer_cost_mismatch"):
                verify(
                    original,
                    alternative.model_copy(update={"cost_basis_hash": "sha256:" + "0" * 64}),
                )
    finally:
        control.close()
