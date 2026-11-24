"""Serve two declared alternatives for one actual N7 model-input leaf.

This controlled fixture exercises producer-to-API routing before any source
fetch or numerical execution. Catalog entries are synthetic declarations, not
evidence of independent providers, observation rights, price, or currentness.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from polisyos.core.artifacts import ArtifactRef, artifact_ref_identity_key
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.runtime.http.services.acquisition_action_service import (
    NativeDerivationLeafRouteProjection,
)
from polisyos.runtime.quality.acquisition_planner import (
    load_n7_derivation_bundle,
    n7_pending_unique_derivation_source_gaps,
)
from polisyos.runtime.quality.acquisition_route_loop import NativeDerivationLeafProviderSelection
from polisyos.runtime.quality.acquisition_world_growth import (
    NativeDerivationPlanningRoleSupplier,
    NativeDerivationRouteConfiguration,
)
from tests._helpers.control_worker import stop_embedded_control_worker
from tests._helpers.lane01_wdi_profiles import (
    FixtureWDIRegisteredSourceSemantics,
    FixtureWDIRoleBinding,
    build_fixture_wdi_authority_bundle,
)
from tests.integration.runtime_quality.test_native_derivation_acquisition_served import (
    configured_native_source_case,
)
from tests.integration.runtime_quality.test_native_derivation_acquisition_served import (
    controlled_candidate_gateway as _gateway_fixture,
)

controlled_candidate_gateway = _gateway_fixture


def _add_second_gdp_declaration(
    *, store: Any, root: Path, holder: dict[str, Any], **_kwargs: Any
) -> None:
    """Add one genuine test-owned declaration to the stock selected GDP role."""
    setup = holder["setup"]
    (first,) = (row for row in holder["rows"] if row["role"] == setup.profile.denominator_role)
    original = catalog_read_api.load_acquisition_supplier_declaration(store, first["ref"])
    entry = original.entry
    assert entry.source_semantic_definition_ref is not None
    assert entry.source_representation_ref is not None
    assert entry.source_measure_scope is not None
    (source_profile,) = (
        row
        for row in holder["metadata"]["native_profiles"]
        if row.target_slot == entry.target_variable
    )
    alternate = replace(
        source_profile,
        source_description=source_profile.source_description
        + " A second controlled declaration of the same source scope.",
    )
    authority, (alternate_entry,) = build_fixture_wdi_authority_bundle(
        root / "second-gdp-declaration",
        (alternate,),
        role_bindings={
            alternate.target_slot: FixtureWDIRoleBinding(
                attempt_ids=("native-second-gdp-declaration",),
                registered_source_semantics=FixtureWDIRegisteredSourceSemantics(
                    source_semantic_definition_ref=entry.source_semantic_definition_ref,
                    source_representation_ref=entry.source_representation_ref,
                    source_measure_scope=entry.source_measure_scope.model_dump(mode="json"),
                    country_codes=entry.country_codes,
                ),
            )
        },
    )
    alternate_ref = catalog_read_api.persist_acquisition_supplier_declaration(
        store, authority, entry_id=alternate_entry.entry_id
    )
    selected = catalog_read_api.load_acquisition_supplier_declaration(store, alternate_ref)
    assert artifact_ref_identity_key(alternate_ref) != artifact_ref_identity_key(first["ref"])
    assert selected.entry.target_variable == entry.target_variable
    assert selected.entry.catalog_raw_variable == entry.catalog_raw_variable == "NY.GDP.MKTP.CD"
    provider = NativeDerivationLeafProviderSelection(
        source_node_id=first["provider"].source_node_id,
        supplier_ref=alternate_ref,
        authority_entry_id=selected.entry.entry_id,
        connector_id=selected.connector_id,
    )
    row = {
        "role": first["role"],
        "ref": alternate_ref,
        "provider": provider,
        "selection_row": NativeDerivationPlanningRoleSupplier(
            role=first["role"], provider=provider, source_declaration_ref=alternate_ref
        ),
    }
    holder["rows"] = (*holder["rows"], row)
    holder["alternate_gdp_ref"] = alternate_ref


@pytest.mark.integration
def test_two_gdp_declarations_share_one_actual_n7_leaf_in_fresh_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
    record_property: Any,
) -> None:
    """Two source declarations retain one target through a fresh API reader."""
    with configured_native_source_case(
        tmp_path,
        monkeypatch,
        controlled_candidate_gateway,
        catalog_ready=_add_second_gdp_declaration,
    ) as (served, holder):
        route_path = f"/api/v1/runs/{served.control_run_id}/acquisition-routes"
        scope = {
            "tenant_id": served.claims.tenant_id,
            "cell_id": served.claims.cell_id,
            "run_id": served.control_run_id,
            "source_job_id": served.job_id,
        }
        with tenant_scope(None, tenant_id=served.claims.tenant_id, cell_id=served.claims.cell_id):
            initial_control = served.service
            initial_heads = initial_control._control_store.list_acquisition_action_heads_for_source(
                **scope
            )
            initial_job = initial_control._control_store.get_job(served.job_id)
            initial_ledger = initial_control.llm_producer_settlement_store._ledger.snapshot()
            assert initial_heads == ()
        response = served.client.get(route_path)
        assert response.status_code == 200, response.text
        with tenant_scope(None, tenant_id=served.claims.tenant_id, cell_id=served.claims.cell_id):
            assert (
                initial_control._control_store.list_acquisition_action_heads_for_source(**scope)
                == initial_heads
            )
            assert initial_control._control_store.get_job(served.job_id) == initial_job
            assert (
                initial_control.llm_producer_settlement_store._ledger.snapshot() == initial_ledger
            )
        routes = response.json()["routes"]
        assert len(routes) == 3
        record_property("source_job_id", served.job_id)
        record_property("source_run_id", served.control_run_id)
        record_property("test_cas_root", str(served.cas_root))
        record_property("unpriced_route_projections", json.dumps(routes, sort_keys=True))
        projections = tuple(
            NativeDerivationLeafRouteProjection.model_validate(row) for row in routes
        )
        assert all(row.route_status == "inputs_pending" for row in projections)
        assert all(
            row.reason_codes == ("native_leaf_owner_cost_profile_not_established",)
            for row in projections
        )
        gdp = tuple(row for row in projections if row.source_node_id == "input-b")
        ratio = tuple(row for row in projections if row.source_node_id == "input-a")
        assert len(gdp) == 2 and len(ratio) == 1
        assert len({row.route_id for row in projections}) == 3
        assert len({row.requirement_gap_id for row in gdp}) == 1
        assert len({row.planner_record_id for row in gdp}) == 1
        assert (
            len({artifact_ref_identity_key(row.derivation_bundle_ref) for row in projections}) == 1
        )
        gdp_suppliers = {artifact_ref_identity_key(row.selected_supplier_ref) for row in gdp}
        expected = {
            artifact_ref_identity_key(row["ref"])
            for row in holder["rows"]
            if row["role"] == holder["setup"].profile.denominator_role
        }
        assert gdp_suppliers == expected and len(expected) == 2
        assert all("cost_basis" not in row and "replay_pins" not in row for row in routes)

        # An independently opened API instance must re-adopt the same deployment
        # selection before resolving the persisted source and its two alternatives.
        with TestClient(served.app_factory()) as reader:
            control = reader.app.state.runtime_container.control_service
            stop_embedded_control_worker(control)
            with tenant_scope(
                None, tenant_id=served.claims.tenant_id, cell_id=served.claims.cell_id
            ):
                control.bind_native_derivation_route_configuration(holder["configuration"])
                heads_before = control._control_store.list_acquisition_action_heads_for_source(
                    **scope
                )
                assert heads_before == initial_heads
                job_before = control._control_store.get_job(served.job_id)
                ledger_before = control.llm_producer_settlement_store._ledger.snapshot()
                assert job_before == initial_job
                assert ledger_before == initial_ledger
                action_service = reader.app.state.runtime_container.acquisition_action_service
                loop = action_service._route_loop(
                    tenant_id=served.claims.tenant_id, cell_id=served.claims.cell_id
                )
                origin = loop._resolve_verified_origin(
                    run_id=served.control_run_id, native_derivation=True
                )
                assert origin.job.job_id == served.job_id
                assert origin.configured_port_source.numerical_execution_status == "unrun"
                assert (
                    origin.configured_port_source.schema_version
                    == "policyos.runtime.n7_configured_candidate_port_source.v3"
                )
                assert artifact_ref_identity_key(
                    origin.configured_port_source.derivation_bundle_ref
                ) == (artifact_ref_identity_key(gdp[0].derivation_bundle_ref))
                bundle = load_n7_derivation_bundle(
                    control._artifact_store, origin.configured_port_source.derivation_bundle_ref
                )
                assert bundle.schema_version == "policyos.runtime.n7_derivation_bundle.v2"
                gdp_leaf = next(item for item in bundle.source_nodes if item.node_id == "input-b")
                assert gdp_leaf.requirement_gap is not None
                assert gdp_leaf.requirement_gap.requirement_gap_id == gdp[0].requirement_gap_id
                assert gdp_leaf.requirement_gap.metadata["satisfaction_status"] == "unsatisfied"
                for field in (
                    "historical_catalog_absence",
                    "source_currentness",
                    "measurement_admission",
                ):
                    assert gdp_leaf.requirement_gap.metadata[field] == "not_established"
                assert {
                    artifact_ref_identity_key(row.supplier_ref)
                    for row in gdp_leaf.supplier_alternatives
                } == expected
                assert (
                    sum(
                        item.requirement_gap_id == gdp_leaf.requirement_gap.requirement_gap_id
                        for item in n7_pending_unique_derivation_source_gaps(bundle)
                    )
                    == 1
                )
                assert bundle.target_satisfaction_status == "unsatisfied"
                record_property(
                    "configured_source_ref",
                    json.dumps(
                        origin.report.candidate_lineage.port_source_ref.model_dump(mode="json"),
                        sort_keys=True,
                    ),
                )
                record_property(
                    "compiled_source_ref",
                    json.dumps(served.compiled_ref.model_dump(mode="json"), sort_keys=True),
                )
            read = reader.get(route_path)
            assert read.status_code == 200, read.text
            assert read.json()["routes"] == routes
            for row in routes:
                detail = reader.get(f"{route_path}/{row['route_id']}")
                assert detail.status_code == 200, detail.text
                assert detail.json() == row

            # The stock pre-numerical source carrier can still own the exact
            # explicit-provider path when its reopened derivation plan is V2.
            with tenant_scope(
                None, tenant_id=served.claims.tenant_id, cell_id=served.claims.cell_id
            ):
                selected_ref = ArtifactRef.model_validate(gdp[0].selected_supplier_ref)
                selected_declaration = catalog_read_api.load_acquisition_supplier_declaration(
                    control._artifact_store, selected_ref
                )
                provider = NativeDerivationLeafProviderSelection(
                    source_node_id=gdp[0].source_node_id,
                    supplier_ref=selected_ref,
                    authority_entry_id=selected_declaration.entry.entry_id,
                    connector_id=selected_declaration.connector_id,
                )
                source_ref = origin.report.candidate_lineage.port_source_ref
                route = NativeDerivationRouteConfiguration(
                    tenant_id=served.claims.tenant_id,
                    cell_id=served.claims.cell_id,
                    run_id=served.control_run_id,
                    source_job_id=origin.job.job_id,
                    configured_port_source_ref=source_ref,
                    supplier_selections=(provider,),
                )
                control.bind_native_derivation_route_configuration(
                    holder["configuration"].model_copy(
                        update={"native_derivation_routes": (route,)}
                    )
                )
                assert control.native_derivation_leaf_provider_selections(
                    tenant_id=served.claims.tenant_id,
                    cell_id=served.claims.cell_id,
                    run_id=served.control_run_id,
                    source_job_id=origin.job.job_id,
                    configured_port_source_ref=source_ref,
                ) == (provider,)
                assert holder["fetch_calls"] == []
                assert served.semantic_kernel_entries == []
                control.bind_native_derivation_route_configuration(holder["configuration"])

            # The exact previously selected declaration is an input of the
            # bundle. Missing bytes must refuse the old route; restoring the
            # identical bytes reopens the same two projections.
            selected = ArtifactRef.model_validate(holder["alternate_gdp_ref"])
            blob_path, _manifest_path = served.store._paths(selected.artifact_id)
            original_bytes = blob_path.read_bytes()
            withheld = tmp_path / "withheld-alternate-gdp-declaration"
            blob_path.replace(withheld)
            try:
                refused = reader.get(route_path)
                assert refused.status_code == 409, refused.text
                assert refused.json()["code"] == "native_model_input_source_not_established"
            finally:
                withheld.replace(blob_path)
            assert blob_path.read_bytes() == original_bytes
            restored = reader.get(route_path)
            assert restored.status_code == 200, restored.text
            assert restored.json()["routes"] == routes
            with tenant_scope(
                None, tenant_id=served.claims.tenant_id, cell_id=served.claims.cell_id
            ):
                assert control._control_store.list_acquisition_action_heads_for_source(**scope) == (
                    heads_before
                )
                assert control._control_store.get_job(served.job_id) == job_before
                assert control.llm_producer_settlement_store._ledger.snapshot() == ledger_before
        assert holder["fetch_calls"] == []
        assert served.semantic_kernel_entries == []
