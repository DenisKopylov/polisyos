from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactTenantContextInfo,
    CoreJSONArtifactStore,
    PutOptions,
    SelectedProfileVerificationReader,
    read_core_manifest_profile,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import ExecPlanRef, ProgramGraphRef
from polisyos.core.contracts.model_input_requirements import (
    ModelInputContext,
    ModelInputPhysicalEncoding,
    ModelInputPortDeclaration,
    load_program_graph_input_interface,
    persist_model_input_port_declaration,
)
from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
    AcquisitionAuthorityEntry,
    build_authority_entry,
    build_authority_registry,
)
from polisyos.runtime.http.errors import RuntimeHTTPError
from polisyos.runtime.http.routes.runs import _generic_model_input_routing_projection
from polisyos.runtime.quality.model_input_requirements import (
    SelectedProgramGraphInputBasis,
    derive_program_graph_input_interface,
    preflight_program_graph_inputs,
)
from polisyos.runtime.quality.model_input_routing import (
    _discover_port_routes,
    _verify_model_input_routing_report_current,
    plan_selected_model_input_routing,
    verify_model_input_routing_report,
)
from polisyos.runtime.quality.substrate_registry import resolve_catalog_serving_source
from tests._helpers.acquisition_production import _entry, _resolver
from tests._helpers.program_graph_tax_subsidy_input import (
    prepare_program_graph_tax_subsidy_input_case,
)
from tests.unit.data_forge.domains.catalog.knowledge.test_acquisition_authority_model_input_discovery import (
    _authority_entry,
    _model_inputs,
)

if TYPE_CHECKING:
    from polisyos.data_forge.read_api.catalog import CanonicalAcquisitionAuthority
    from polisyos.runtime.quality.substrate_registry import CatalogServingSourcePaths


def _projection_catalog_source(
    authority: CanonicalAcquisitionAuthority,
) -> CatalogServingSourcePaths:
    source = resolve_catalog_serving_source(
        authority.repo_root, selection=None, requested_profile=None
    )
    return replace(
        source,
        database_path=authority.baseline_path,
        index_dir=authority.baseline_path.parent,
        substrate_paths=replace(
            source.substrate_paths,
            l1_dcat_path=authority.baseline_path,
            measurement_registry_path=authority.l5_path,
        ),
    )


def _replace_authority_registry(
    authority: CanonicalAcquisitionAuthority,
    entries: tuple[AcquisitionAuthorityEntry, ...],
) -> str:
    registry = build_authority_registry(
        baseline_content_sha256=authority.provision.baseline_content_sha256,
        l5_measurement_registry_sha256=(
            authority.provision.l5_measurement_registry_content_sha256
        ),
        entries=entries,
    )
    registry_path = authority.repo_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY
    registry_path.write_text(registry.model_dump_json(), encoding="utf-8")
    return registry.content_sha256


def _fiscal_input_declaration(store: CoreJSONArtifactStore) -> ArtifactRef:
    _, _, _, source_interface_ref = _model_inputs(store)
    source_interface = load_program_graph_input_interface(store, source_interface_ref)
    port = source_interface.ports[0].model_copy(
        update={
            "slot_id": "government.balance",
            "state_path": "government_balance",
            "purpose": "initial_state",
            "physical_encoding": ModelInputPhysicalEncoding(
                shape=(),
                dtype="float32",
                max_absolute_error=Decimal("0"),
            ),
        }
    )
    return persist_model_input_port_declaration(
        store,
        ModelInputPortDeclaration(ports=(port,)),
    )


def test_selected_model_input_routes_to_candidate_descriptor_or_named_absence(
    tmp_path: Path,
) -> None:
    case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path,
        opening_balance_usd=None,
        mechanism_start_step=2,
        model_input_port_declaration_builder=_fiscal_input_declaration,
    )
    try:
        graph_ref = ProgramGraphRef.model_validate(case.program_graph_ref.model_dump(mode="python"))
        exec_plan_ref = ExecPlanRef.model_validate(case.exec_plan_ref.model_dump(mode="python"))
        interface_ref = derive_program_graph_input_interface(
            case.store,
            program_graph_ref=graph_ref,
            exec_plan_ref=exec_plan_ref,
            registry_bundle_ref=case.registry_bundle_ref,
        )
        assert interface_ref is not None
        interface = load_program_graph_input_interface(case.store, interface_ref)
        (port,) = interface.ports
        context = ModelInputContext(
            run_id="model-input-routing-test",
            candidate_id="program_graph_tax_subsidy_input",
            candidate_content_hash=str(case.policy_candidate_ref.artifact_id),
            design_problem_ref=str(case.trinity_ref.artifact_id),
            candidate_source_ref=case.policy_candidate_ref,
        )
        selected_basis = SelectedProgramGraphInputBasis(
            context=context,
            program_graph_ref=graph_ref,
            exec_plan_ref=exec_plan_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            input_bindings_ref=case.input_bindings_ref,
            steps=(0, 1, 2),
        )
        preflight = preflight_program_graph_inputs(
            case.store,
            interface_ref=interface_ref,
            program_graph_ref=graph_ref,
            exec_plan_ref=exec_plan_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            input_bindings_ref=case.input_bindings_ref,
            context=context,
            steps=(0, 1, 2),
        )
        assert len(preflight.obligation_refs) == 1

        compatible_authority, _ = _resolver(
            tmp_path / "catalog-compatible",
            authority_entry=_authority_entry(
                port.semantic_definition_ref,
                port.representation_ref,
            ),
        )
        resolved = plan_selected_model_input_routing(
            case.store,
            obligation_set_ref=preflight.obligation_set_ref,
            selected_basis=selected_basis,
            catalog_authority=compatible_authority,
        )
        (resolved_route,) = resolved.report.routes
        assert resolved.report.status == "candidate_descriptors_resolved"
        assert resolved.report.schema_version == "1.0"
        assert resolved_route.disposition == "resolved"
        assert resolved_route.reason_code is None
        assert resolved_route.query_envelope is None
        assert resolved_route.source_descriptor is not None
        assert resolved_route.source_descriptor.query_envelope is None
        assert resolved_route.source_descriptor.semantic_correspondence == "not_established"
        assert resolved_route.voi_status == "unknown"
        assert resolved_route.fetch_status == "not_attempted"
        assert resolved.report_ref.manifest_profile_sha256 is not None

        class ForgedCatalogAuthority:
            def discover_model_input_source_descriptor(self, *args: object, **kwargs: object):
                return resolved_route.source_descriptor

        forged_authority = ForgedCatalogAuthority()
        with pytest.raises(
            TypeError,
            match="model_input_routing_catalog_authority_not_canonical",
        ):
            plan_selected_model_input_routing(
                object(),
                obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected_basis,
                catalog_authority=forged_authority,
            )
        with pytest.raises(
            TypeError,
            match="model_input_routing_catalog_authority_not_canonical",
        ):
            verify_model_input_routing_report(
                object(),
                resolved.report_ref,
                expected_obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected_basis,
                catalog_authority=forged_authority,
            )

        fresh_store = FileSystemCAS(case.store_root)
        legacy_manifest = fresh_store.get_manifest(resolved.report_ref)
        assert legacy_manifest.artifact_schema is not None
        assert legacy_manifest.artifact_schema.version == "1.0"
        legacy_payload = json.loads(fresh_store.get_bytes(resolved.report_ref))
        assert legacy_payload["schema_version"] == "1.0"
        assert "query_envelope" not in legacy_payload["routes"][0]
        assert "query_envelope" not in legacy_payload["routes"][0]["source_descriptor"]
        assert (
            verify_model_input_routing_report(
                fresh_store,
                resolved.report_ref,
                expected_obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected_basis,
                catalog_authority=compatible_authority,
            )
            == resolved.report
        )

        v2_authority, _ = _resolver(
            tmp_path / "catalog-v2",
            authority_entry=_authority_entry(
                port.semantic_definition_ref,
                port.representation_ref,
                suffix="v2-selected",
            ),
        )
        (selected_entry,) = v2_authority._load_registry().entries
        unrelated_fields = _entry().model_dump(mode="python", exclude={"entry_id"})
        unrelated_fields["title"] = "Unrelated registry metadata before routing."
        unrelated_before = build_authority_entry(**unrelated_fields)
        registry_before_sha256 = _replace_authority_registry(
            v2_authority,
            (selected_entry, unrelated_before),
        )
        routed_v2 = plan_selected_model_input_routing(
            case.store,
            obligation_set_ref=preflight.obligation_set_ref,
            selected_basis=selected_basis,
            catalog_authority=v2_authority,
            report_version="2.0",
        )
        (route_v2,) = routed_v2.report.routes
        assert routed_v2.report.schema_version == "2.0"
        assert route_v2.query_envelope is not None
        assert [row.entry_id for row in route_v2.query_envelope.rows] == [
            selected_entry.entry_id
        ]
        assert route_v2.query_envelope.rows[0].disposition == "compatible"
        assert route_v2.source_descriptor is not None
        assert route_v2.source_descriptor.query_envelope is None
        assert (
            route_v2.source_descriptor.authority_registry_content_sha256
            == registry_before_sha256
        )
        v2_manifest = fresh_store.get_manifest(routed_v2.report_ref)
        assert v2_manifest.artifact_schema is not None
        assert v2_manifest.artifact_schema.version == "2.0"

        # Same local identifier/revision is not a Catalog alias contract: this
        # separate meaning must not enter the exact-definition query or stale
        # the already persisted model binding.
        lookalike_definition_ref, lookalike_representation_ref, _, _ = _model_inputs(
            case.store,
            definition_meaning=(
                "A different balance definition sharing the same local label and revision."
            ),
        )
        assert lookalike_definition_ref != port.semantic_definition_ref
        same_label_different_meaning_entry = _authority_entry(
            lookalike_definition_ref,
            lookalike_representation_ref,
            suffix="same-label-different-meaning",
        )

        # Keep the exact definition, dataset, units, scope and N5 obligation.
        # The nearby fiscal flow still cannot supply the model's opening stock.
        flow_definition_ref, flow_representation_ref, _, _ = _model_inputs(
            case.store, source_quantity_kind="flow"
        )
        assert flow_definition_ref == port.semantic_definition_ref
        flow_entry = build_authority_entry(
            **{
                **selected_entry.model_dump(mode="python", exclude={"entry_id"}),
                "source_representation_ref": flow_representation_ref,
            }
        )
        registry_with_lookalike_sha256 = _replace_authority_registry(
            v2_authority,
            (selected_entry, unrelated_before, same_label_different_meaning_entry),
        )
        assert registry_with_lookalike_sha256 != registry_before_sha256
        assert (
            verify_model_input_routing_report(
                fresh_store,
                routed_v2.report_ref,
                expected_obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected_basis,
                catalog_authority=v2_authority,
            )
            == routed_v2.report
        )
        _replace_authority_registry(
            v2_authority,
            (flow_entry, unrelated_before, same_label_different_meaning_entry),
        )
        flow_routing = plan_selected_model_input_routing(
            case.store,
            obligation_set_ref=preflight.obligation_set_ref,
            selected_basis=selected_basis,
            catalog_authority=v2_authority,
            report_version="2.0",
        )
        assert flow_routing.report_ref != routed_v2.report_ref
        assert flow_routing.report.obligation_set_ref == routed_v2.report.obligation_set_ref
        assert flow_routing.report.status == "candidate_descriptors_limited"
        assert flow_routing.report.authority_purpose == "candidate_acquisition_routing_only"
        (flow_route,) = flow_routing.report.routes
        assert flow_route.obligation_ref == route_v2.obligation_ref
        assert flow_route.disposition == "conflict"
        assert flow_route.reason_code == "model_input_source_descriptor_incompatible"
        assert flow_route.source_descriptor is None
        assert flow_route.fetch_status == "not_attempted"
        assert flow_route.query_envelope is not None
        (flow_row,) = flow_route.query_envelope.rows
        assert flow_row.entry_id == flow_entry.entry_id
        assert flow_row.disposition == "incompatible"
        assert flow_row.reason_codes == ("required_axis_mismatch:quantity_kind",)
        assert (
            verify_model_input_routing_report(
                fresh_store,
                flow_routing.report_ref,
                expected_obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected_basis,
                catalog_authority=v2_authority,
            )
            == flow_routing.report
        )

        revised_unrelated_fields = unrelated_before.model_dump(
            mode="python",
            exclude={"entry_id"},
        )
        revised_unrelated_fields["title"] = "Unrelated registry metadata after routing."
        unrelated_after = build_authority_entry(**revised_unrelated_fields)
        registry_after_sha256 = _replace_authority_registry(
            v2_authority,
            (selected_entry, unrelated_after, same_label_different_meaning_entry),
        )
        assert registry_after_sha256 != registry_before_sha256

        stored_v2, current_v2 = _verify_model_input_routing_report_current(
            fresh_store,
            routed_v2.report_ref,
            expected_obligation_set_ref=preflight.obligation_set_ref,
            selected_basis=selected_basis,
            catalog_authority=v2_authority,
        )
        assert stored_v2 == routed_v2.report
        assert current_v2 != stored_v2
        (current_route_v2,) = current_v2.routes
        assert current_route_v2.query_envelope == route_v2.query_envelope
        assert current_route_v2.source_descriptor is not None
        assert (
            current_route_v2.source_descriptor.authority_registry_content_sha256
            == registry_after_sha256
        )
        assert (
            verify_model_input_routing_report(
                fresh_store,
                routed_v2.report_ref,
                expected_obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected_basis,
                catalog_authority=v2_authority,
            )
            == routed_v2.report
        )

        countercandidate = _authority_entry(
            port.semantic_definition_ref,
            port.representation_ref,
            suffix="new-countercandidate",
        )
        _replace_authority_registry(
            v2_authority,
            (
                selected_entry,
                unrelated_after,
                same_label_different_meaning_entry,
                countercandidate,
            ),
        )
        current_routes = _discover_port_routes(
            fresh_store,
            compilation_report=routed_v2.compilation_report,
            catalog_authority=v2_authority,
            include_query_envelope=True,
        )
        (ambiguous_route,) = current_routes
        assert ambiguous_route.disposition == "ambiguous"
        assert ambiguous_route.query_envelope is not None
        assert len(ambiguous_route.query_envelope.rows) == 2
        assert sum(
            row.disposition == "compatible" for row in ambiguous_route.query_envelope.rows
        ) == 2
        with pytest.raises(
            ValueError,
            match="model_input_routing_report_selection_mismatch",
        ):
            verify_model_input_routing_report(
                fresh_store,
                routed_v2.report_ref,
                expected_obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected_basis,
                catalog_authority=v2_authority,
            )

        no_match_authority, _ = _resolver(tmp_path / "catalog-no-match")
        absent = plan_selected_model_input_routing(
            case.store,
            obligation_set_ref=preflight.obligation_set_ref,
            selected_basis=selected_basis,
            catalog_authority=no_match_authority,
        )
        (absent_route,) = absent.report.routes
        assert absent.report.status == "candidate_descriptors_limited"
        assert absent_route.disposition == "absent"
        assert absent_route.reason_code == "model_input_source_descriptor_unresolved"
        assert absent_route.source_descriptor is None
        assert absent_route.voi_status == "unknown"
        assert absent_route.fetch_status == "not_attempted"
        absent_v2 = plan_selected_model_input_routing(
            case.store,
            obligation_set_ref=preflight.obligation_set_ref,
            selected_basis=selected_basis,
            catalog_authority=no_match_authority,
            report_version="2.0",
        )
        (absent_v2_route,) = absent_v2.report.routes
        assert absent_v2_route.query_envelope is not None
        assert absent_v2_route.query_envelope.rows == ()
        assert (
            verify_model_input_routing_report(
                fresh_store,
                absent_v2.report_ref,
                expected_obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected_basis,
                catalog_authority=no_match_authority,
            )
            == absent_v2.report
        )

        projection_for = partial(
            _generic_model_input_routing_projection,
            store=SelectedProfileVerificationReader(fresh_store),
            obligation_set_ref=preflight.obligation_set_ref,
            selected_basis=selected_basis,
            tenant_id="routing-tenant",
            cell_id="routing-cell",
        )
        compatible_source = _projection_catalog_source(compatible_authority)
        no_match_source = _projection_catalog_source(no_match_authority)
        projected = projection_for(
            report_ref=resolved.report_ref, catalog_serving_source=compatible_source
        )
        assert projected.status == "candidate_descriptors_resolved"
        assert projected.obligation_set_ref == preflight.obligation_set_ref
        assert projected.report_ref == resolved.report_ref
        assert projected.authority_purpose == "candidate_acquisition_routing_only"
        assert projected.voi_status == "unknown"
        assert projected.fetch_status == "not_attempted"
        assert [(row.port_id, row.disposition, row.reason_code) for row in projected.ports] == [
            (port.port_id, "resolved", None)
        ]
        limited = projection_for(
            report_ref=absent.report_ref, catalog_serving_source=no_match_source
        )
        assert limited.status == "candidate_descriptors_limited"
        assert limited.report_ref == absent.report_ref
        assert [(row.port_id, row.disposition, row.reason_code) for row in limited.ports] == [
            (port.port_id, "absent", "model_input_source_descriptor_unresolved")
        ]

        missing_profile = resolved.report_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "0" * 64}
        )
        for refused in (
            projection_for(report_ref=missing_profile, catalog_serving_source=compatible_source),
            projection_for(report_ref=resolved.report_ref, catalog_serving_source=no_match_source),
        ):
            assert refused.status == "not_established"
            assert (
                refused.limitation_code == "generic_n5_model_input_routing_replay_not_established"
            )
            assert refused.report_ref is None
            assert refused.obligation_set_ref is None
            assert refused.ports == ()

        report_manifest = case.store.get_manifest(resolved.report_ref)
        foreign_scope = ArtifactTenantContextInfo(tenant_id="foreign", cell_id="foreign")
        foreign_ref = case.store.put_bytes(
            case.store.get_bytes(resolved.report_ref),
            PutOptions(
                kind=report_manifest.kind,
                media_type=report_manifest.media_type,
                schema=report_manifest.artifact_schema,
                canon=report_manifest.canon,
                inputs=report_manifest.inputs,
                tenant_context=foreign_scope,
            ),
            return_selected_profile=True,
        )
        assert foreign_ref.artifact_id == resolved.report_ref.artifact_id
        assert foreign_ref.manifest_profile_sha256 != resolved.report_ref.manifest_profile_sha256
        foreign_manifest, _ = read_core_manifest_profile(fresh_store, foreign_ref)
        assert foreign_manifest.tenant_context == foreign_scope
        with pytest.raises(RuntimeHTTPError) as denied:
            projection_for(report_ref=foreign_ref, catalog_serving_source=compatible_source)
        assert denied.value.status_code == 403
        assert denied.value.code == "generic_n5_model_input_routing_scope_refused"

        wrong_basis = replace(selected_basis, steps=(0, 1))
        with pytest.raises(ValueError, match="model_input_preflight_invocation_mismatch"):
            plan_selected_model_input_routing(
                case.store,
                obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=wrong_basis,
                catalog_authority=compatible_authority,
            )
    finally:
        case.close()
