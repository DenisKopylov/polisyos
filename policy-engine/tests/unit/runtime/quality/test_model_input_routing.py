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
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import ExecPlanRef, FoundryInputBindingsRef, ProgramGraphRef
from polisyos.core.contracts.model_input_requirements import (
    ModelInputContext,
    ModelInputPhysicalEncoding,
    ModelInputPort,
    ModelInputPortDeclaration,
    load_program_graph_input_interface,
    persist_model_input_port_declaration,
)
from polisyos.core.contracts.variable_binding import (
    VariableRepresentation,
    VariableSemanticDefinition,
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
    ProgramGraphInputPreflight,
    SelectedProgramGraphInputBasis,
    derive_program_graph_input_interface,
    preflight_program_graph_inputs,
)
from polisyos.runtime.quality.model_input_routing import (
    _coarse_route_memberships,
    _current_authority_registry_sha256,
    _discover_port_routes,
    _routing_query_key,
    _verify_model_input_routing_report_current,
    persist_current_model_input_routing_use_decision,
    plan_selected_model_input_routing,
    read_model_input_routing_report,
    read_model_input_routing_use_decision,
    verify_model_input_routing_report,
    verify_model_input_routing_use_decision_current,
)
from polisyos.runtime.quality.model_input_successor_selection import (
    ModelInputSuccessorSelection,
    persist_model_input_successor_selection,
    read_model_input_successor_selection,
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
    from tests._helpers.program_graph_tax_subsidy_input import ProgramGraphTaxSubsidyInputCase


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
        l5_measurement_registry_sha256=(authority.provision.l5_measurement_registry_content_sha256),
        entries=entries,
    )
    registry_path = authority.repo_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY
    registry_path.write_text(registry.model_dump_json(), encoding="utf-8")
    return registry.content_sha256


def _candidate_route_ref(
    store: FileSystemCAS,
    kind: str,
    *,
    media_type: str = "application/json",
) -> ArtifactRef:
    """Persist a selected non-authoritative ref for the successor wire fixture."""
    return store.put_bytes(
        kind.encode("utf-8"),
        PutOptions(kind=kind, media_type=media_type),
        return_selected_profile=True,
    )


def _fiscal_input_declaration(
    store: CoreJSONArtifactStore,
    *,
    definition_revision: str = "r1",
    definition_meaning: str = (
        "Government fiscal balance measured for a bounded population and period."
    ),
) -> ArtifactRef:
    _, _, _, source_interface_ref = _model_inputs(
        store,
        definition_revision=definition_revision,
        definition_meaning=definition_meaning,
    )
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


def _select_program_graph_routing_inputs(
    case: ProgramGraphTaxSubsidyInputCase,
    *,
    run_id: str,
) -> tuple[ModelInputPort, SelectedProgramGraphInputBasis, ProgramGraphInputPreflight]:
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
        run_id=run_id,
        candidate_id="program_graph_tax_subsidy_input",
        candidate_content_hash=str(case.policy_candidate_ref.artifact_id),
        design_problem_ref=str(case.trinity_ref.artifact_id),
        candidate_source_ref=case.policy_candidate_ref,
    )
    basis = SelectedProgramGraphInputBasis(
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
    return port, basis, preflight


def test_routing_rederives_registry_metadata_without_changing_exact_model_inputs(
    tmp_path: Path,
) -> None:
    """Refresh routing after metadata changes without changing numerical inputs."""
    case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path,
        opening_balance_usd=None,
        mechanism_start_step=2,
        model_input_port_declaration_builder=_fiscal_input_declaration,
    )
    try:
        port, selected_basis, preflight = _select_program_graph_routing_inputs(
            case,
            run_id="model-input-routing-metadata-refresh",
        )
        selected_entry = _authority_entry(port.semantic_definition_ref, port.representation_ref)
        unrelated_fields = _entry().model_dump(mode="python", exclude={"entry_id"})
        unrelated_fields["title"] = "Unrelated registry metadata before refresh."
        unrelated_before = build_authority_entry(**unrelated_fields)
        authority, _ = _resolver(
            tmp_path / "catalog-metadata-refresh",
            authority_entry=selected_entry,
        )
        initial_registry_hash = _replace_authority_registry(
            authority, (selected_entry, unrelated_before)
        )
        old_route = plan_selected_model_input_routing(
            case.store,
            obligation_set_ref=preflight.obligation_set_ref,
            selected_basis=selected_basis,
            catalog_authority=authority,
            report_version="2.0",
        )
        (old_binding,) = old_route.report.routes
        assert old_binding.source_descriptor is not None
        assert old_binding.query_envelope is not None
        assert (
            old_binding.source_descriptor.authority_registry_content_sha256 == initial_registry_hash
        )

        # An unrelated row's display metadata changes the registry digest, but
        # the selected model-input query and its exact source refs are unchanged.
        unrelated_fields["title"] = "Unrelated registry metadata after refresh."
        unrelated_after = build_authority_entry(**unrelated_fields)
        unrelated_registry_hash = _replace_authority_registry(
            authority, (selected_entry, unrelated_after)
        )
        fresh_unrelated = plan_selected_model_input_routing(
            case.store,
            obligation_set_ref=preflight.obligation_set_ref,
            selected_basis=selected_basis,
            catalog_authority=authority,
            report_version="2.0",
        )
        (unrelated_binding,) = fresh_unrelated.report.routes
        assert unrelated_binding.source_descriptor is not None
        assert unrelated_binding.query_envelope == old_binding.query_envelope
        assert unrelated_binding.source_descriptor.authority_registry_content_sha256 == (
            unrelated_registry_hash
        )
        assert unrelated_binding.source_descriptor.source_semantic_definition_ref == (
            old_binding.source_descriptor.source_semantic_definition_ref
        )
        assert unrelated_binding.source_descriptor.source_representation_ref == (
            old_binding.source_descriptor.source_representation_ref
        )
        assert unrelated_binding.source_descriptor.model_semantic_definition_ref == (
            old_binding.source_descriptor.model_semantic_definition_ref
        )
        assert unrelated_binding.source_descriptor.model_representation_ref == (
            old_binding.source_descriptor.model_representation_ref
        )
        assert (
            verify_model_input_routing_report(
                case.store,
                old_route.report_ref,
                expected_obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected_basis,
                catalog_authority=authority,
            )
            == old_route.report
        )

        # A title/description-only revision of the same selected semantic
        # definition is likewise a discovery-metadata change: the fresh query
        # must expose its current content-addressed entry while preserving the
        # exact model and numerical request basis.
        selected_fields = selected_entry.model_dump(mode="python", exclude={"entry_id"})
        selected_fields["title"] = "Fiscal balance source alias, revised for discovery."
        selected_fields["description"] = (
            "Updated searchable label; exact measurement and semantic refs are unchanged."
        )
        selected_metadata_revision = build_authority_entry(**selected_fields)
        assert selected_metadata_revision.entry_id != selected_entry.entry_id
        assert selected_metadata_revision.source_semantic_definition_ref == (
            selected_entry.source_semantic_definition_ref
        )
        assert selected_metadata_revision.source_representation_ref == (
            selected_entry.source_representation_ref
        )
        assert selected_metadata_revision.raw_field == selected_entry.raw_field
        assert selected_metadata_revision.canonical_unit == selected_entry.canonical_unit
        current_registry_hash = _replace_authority_registry(
            authority, (selected_metadata_revision, unrelated_after)
        )
        fresh_current = plan_selected_model_input_routing(
            case.store,
            obligation_set_ref=preflight.obligation_set_ref,
            selected_basis=selected_basis,
            catalog_authority=authority,
            report_version="2.0",
        )
        (current_binding,) = fresh_current.report.routes
        assert fresh_current.report_ref != fresh_unrelated.report_ref
        assert fresh_current.report.selected_invocation == old_route.report.selected_invocation
        assert fresh_current.report.obligation_set_ref == old_route.report.obligation_set_ref
        assert (
            fresh_current.report.compilation_report_ref == old_route.report.compilation_report_ref
        )
        assert current_binding.source_descriptor is not None
        assert current_binding.query_envelope is not None
        assert current_binding.source_descriptor.authority_entry_id == (
            selected_metadata_revision.entry_id
        )
        assert current_binding.source_descriptor.authority_registry_content_sha256 == (
            current_registry_hash
        )
        assert current_binding.query_envelope != old_binding.query_envelope
        assert current_binding.source_descriptor.source_semantic_definition_ref == (
            old_binding.source_descriptor.source_semantic_definition_ref
        )
        assert current_binding.source_descriptor.source_representation_ref == (
            old_binding.source_descriptor.source_representation_ref
        )
        assert current_binding.source_descriptor.model_semantic_definition_ref == (
            old_binding.source_descriptor.model_semantic_definition_ref
        )
        assert current_binding.source_descriptor.model_representation_ref == (
            old_binding.source_descriptor.model_representation_ref
        )
        assert (
            selected_basis.invocation(current_binding.source_descriptor.model_input_interface_ref)
            == old_route.report.selected_invocation
        )
        assert (
            verify_model_input_routing_report(
                case.store,
                fresh_current.report_ref,
                expected_obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected_basis,
                catalog_authority=authority,
            )
            == fresh_current.report
        )
        # The selected entry is content-addressed, so its revised discovery
        # metadata changes the exact query identity. The old report remains
        # readable as historical evidence, but it must no longer verify as the
        # current route.
        with pytest.raises(
            ValueError,
            match="model_input_routing_report_selection_mismatch",
        ):
            verify_model_input_routing_report(
                case.store,
                old_route.report_ref,
                expected_obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected_basis,
                catalog_authority=authority,
            )
        assert read_model_input_routing_report(case.store, old_route.report_ref) == old_route.report

        # New exact compatible competitors are different: they change the
        # route's scoped query envelope and must invalidate the current selection.
        relevant_countercandidate = _authority_entry(
            port.semantic_definition_ref,
            port.representation_ref,
            suffix="metadata-refresh-countercandidate",
        )
        _replace_authority_registry(
            authority,
            (selected_metadata_revision, unrelated_after, relevant_countercandidate),
        )
        with pytest.raises(ValueError, match="model_input_routing_report_selection_mismatch"):
            verify_model_input_routing_report(
                case.store,
                fresh_current.report_ref,
                expected_obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected_basis,
                catalog_authority=authority,
            )
    finally:
        case.close()


def test_routing_use_decision_persists_query_and_fences_registry_currentness(
    tmp_path: Path,
) -> None:
    """Persist an actual route recheck and refuse the old registry binding."""
    scoped_store = FileSystemCAS(
        tmp_path / "cas",
        tenant_id="tenant-a",
        cell_id="cell-a",
        ownership_enforced=False,
    )
    case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path,
        opening_balance_usd=None,
        mechanism_start_step=2,
        model_input_port_declaration_builder=_fiscal_input_declaration,
        store=scoped_store,
    )
    try:
        port, selected_basis, preflight = _select_program_graph_routing_inputs(
            case,
            run_id="model-input-routing-use-decision",
        )
        selected_entry = _authority_entry(port.semantic_definition_ref, port.representation_ref)
        unrelated_fields = _entry().model_dump(mode="python", exclude={"entry_id"})
        unrelated_fields["title"] = "Unrelated row before use decision."
        unrelated_before = build_authority_entry(**unrelated_fields)
        authority, _ = _resolver(
            tmp_path / "catalog-use-decision",
            authority_entry=selected_entry,
        )
        _replace_authority_registry(authority, (selected_entry, unrelated_before))
        route_result = plan_selected_model_input_routing(
            case.store,
            obligation_set_ref=preflight.obligation_set_ref,
            selected_basis=selected_basis,
            catalog_authority=authority,
            report_version="2.0",
        )
        (route,) = route_result.report.routes
        assert route.query_envelope is not None

        # The reverse query key preserves exact scope and port identity while
        # ignoring result rows and the envelope's derived self-hash.
        rowless_envelope = route.query_envelope.model_copy(
            update={"rows": (), "content_sha256": "sha256:" + "0" * 64}
        )
        assert _routing_query_key(rowless_envelope) == _routing_query_key(route.query_envelope)
        other_port_envelope = route.query_envelope.model_copy(
            update={"model_input_port_id": "other-port"}
        )
        assert _routing_query_key(other_port_envelope) != _routing_query_key(route.query_envelope)
        other_scope = route.query_envelope.scope.model_copy(update={"period_basis": "fiscal_year"})
        other_scope_envelope = route.query_envelope.model_copy(update={"scope": other_scope})
        assert _routing_query_key(other_scope_envelope) != _routing_query_key(route.query_envelope)

        use_decision_ref, decision = persist_current_model_input_routing_use_decision(
            case.store,
            route_result.report_ref,
            expected_obligation_set_ref=preflight.obligation_set_ref,
            selected_basis=selected_basis,
            catalog_authority=authority,
            tenant_id="tenant-a",
            cell_id="cell-a",
            route_port_id=route.port_id,
        )
        assert decision.reverse_view_status == "recomputed"
        assert decision.cas_owner_generation_sha256 is not None
        assert decision.query_subscriber_refs == (route_result.report_ref,)
        assert read_model_input_routing_use_decision(case.store, use_decision_ref) == decision
        assert (
            verify_model_input_routing_use_decision_current(
                case.store,
                use_decision_ref,
                expected_report_ref=route_result.report_ref,
                expected_obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected_basis,
                catalog_authority=authority,
            )
            == decision
        )

        foundry_bindings_ref = _candidate_route_ref(case.store, "foundry.input_bindings")
        successor = ModelInputSuccessorSelection(
            schema_version="polisyos.runtime.ModelInputSuccessorSelection@2.0",
            tenant_id="tenant-a",
            cell_id="cell-a",
            run_id="run-a",
            source_job_id="source-job",
            compiled_ref=_candidate_route_ref(
                case.store, "runtime.compiled_recursive_generation_cycle"
            ),
            blocked_execution_ref=_candidate_route_ref(
                case.store, "runtime.quality.generic_cycle_simulation_n5_execution"
            ),
            routing_report_ref=route_result.report_ref,
            routing_use_decision_ref=use_decision_ref,
            activation_receipt_ref=_candidate_route_ref(
                case.store,
                "epoch.activated_overlay_admission_receipt",
                media_type="application/vnd.polisyos.epoch+json",
            ),
            observation_id="selected-observation",
            observation_content_sha256="sha256:" + "b" * 64,
            route_id="sha256:" + "c" * 64,
            action_job_id="action-job",
            action_worker_id="worker-a",
            action_attempt=1,
            action_phase_ref=_candidate_route_ref(
                case.store, "runtime.quality.model_input_use_action_phase"
            ),
            authority_decision_ref=_candidate_route_ref(
                case.store, "runtime_quality.agent_action_authority_decision"
            ),
            reentry_budget_window_id="d" * 64,
            reentry_budget_window_digest="e" * 64,
            semantic_foundry_input_bindings_ref=FoundryInputBindingsRef.model_validate(
                foundry_bindings_ref.model_dump(mode="python")
            ),
        )
        successor_ref = persist_model_input_successor_selection(case.store, successor)
        assert read_model_input_successor_selection(case.store, successor_ref) == successor
        assert (
            verify_model_input_routing_use_decision_current(
                case.store,
                use_decision_ref,
                expected_report_ref=route_result.report_ref,
                expected_obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected_basis,
                catalog_authority=authority,
            )
            == decision
        )

        unrelated_fields["title"] = "Unrelated row after use decision."
        unrelated_after = build_authority_entry(**unrelated_fields)
        _replace_authority_registry(authority, (selected_entry, unrelated_after))
        with pytest.raises(
            ValueError,
            match="model_input_routing_use_decision_currentness_mismatch",
        ):
            verify_model_input_routing_use_decision_current(
                case.store,
                use_decision_ref,
                expected_report_ref=route_result.report_ref,
                expected_obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected_basis,
                catalog_authority=authority,
            )

        # The registry revision is part of one use decision's final fence,
        # while unrelated metadata does not change the route/query binding.
        # Reverify the original report and issue a fresh decision for that
        # same route without changing its selected source or envelope.
        verified_after_unrelated_change = verify_model_input_routing_report(
            case.store,
            route_result.report_ref,
            expected_obligation_set_ref=preflight.obligation_set_ref,
            selected_basis=selected_basis,
            catalog_authority=authority,
        )
        assert verified_after_unrelated_change == route_result.report
        (verified_route_after_unrelated_change,) = verified_after_unrelated_change.routes
        assert verified_route_after_unrelated_change.query_envelope == route.query_envelope
        assert verified_route_after_unrelated_change.source_descriptor is not None
        assert route.source_descriptor is not None
        assert (
            verified_route_after_unrelated_change.source_descriptor.source_semantic_definition_ref
            == route.source_descriptor.source_semantic_definition_ref
        )
        assert (
            verified_route_after_unrelated_change.source_descriptor.source_representation_ref
            == route.source_descriptor.source_representation_ref
        )
        assert (
            verified_route_after_unrelated_change.source_descriptor.model_semantic_definition_ref
            == route.source_descriptor.model_semantic_definition_ref
        )
        assert (
            verified_route_after_unrelated_change.source_descriptor.model_representation_ref
            == route.source_descriptor.model_representation_ref
        )
        fresh_use_decision_ref, fresh_decision = persist_current_model_input_routing_use_decision(
            case.store,
            route_result.report_ref,
            expected_obligation_set_ref=preflight.obligation_set_ref,
            selected_basis=selected_basis,
            catalog_authority=authority,
            tenant_id="tenant-a",
            cell_id="cell-a",
            route_port_id=route.port_id,
        )
        assert fresh_use_decision_ref != use_decision_ref
        assert fresh_decision.routing_report_ref == route_result.report_ref
        assert fresh_decision.query_key_sha256 == decision.query_key_sha256
        assert (
            fresh_decision.query_envelope_content_sha256 == decision.query_envelope_content_sha256
        )
        assert (
            fresh_decision.authority_registry_content_sha256
            == _current_authority_registry_sha256(authority)
        )
        assert fresh_decision.authority_registry_content_sha256 != (
            decision.authority_registry_content_sha256
        )
        assert fresh_decision.query_subscriber_refs == decision.query_subscriber_refs
        assert (
            verify_model_input_routing_use_decision_current(
                case.store,
                fresh_use_decision_ref,
                expected_report_ref=route_result.report_ref,
                expected_obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected_basis,
                catalog_authority=authority,
            )
            == fresh_decision
        )

        # A same-query compatible countercandidate changes the semantic
        # selection and invalidates both the report and any fresh decision.
        countercandidate = _authority_entry(
            port.semantic_definition_ref,
            port.representation_ref,
            suffix="use-decision-countercandidate",
        )
        _replace_authority_registry(authority, (selected_entry, unrelated_after, countercandidate))
        with pytest.raises(
            ValueError,
            match="model_input_routing_report_selection_mismatch",
        ):
            verify_model_input_routing_report(
                case.store,
                route_result.report_ref,
                expected_obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected_basis,
                catalog_authority=authority,
            )
        with pytest.raises(ValueError, match="model_input_routing_report_selection_mismatch"):
            persist_current_model_input_routing_use_decision(
                case.store,
                route_result.report_ref,
                expected_obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected_basis,
                catalog_authority=authority,
                tenant_id="tenant-a",
                cell_id="cell-a",
                route_port_id=route.port_id,
            )
        _replace_authority_registry(authority, (selected_entry, unrelated_before))

        # A late same-query report written without tenant metadata is visible
        # in the complete inventory and makes the earlier subscriber view
        # unestablished instead of silently leaving the new report out.
        second_basis = replace(
            selected_basis,
            context=selected_basis.context.model_copy(
                update={"run_id": "model-input-routing-use-decision-late"}
            ),
        )
        second_preflight = preflight_program_graph_inputs(
            case.store,
            interface_ref=preflight.invocation.interface_ref,
            program_graph_ref=second_basis.program_graph_ref,
            exec_plan_ref=second_basis.exec_plan_ref,
            registry_bundle_ref=second_basis.registry_bundle_ref,
            input_bindings_ref=second_basis.input_bindings_ref,
            context=second_basis.context,
            steps=second_basis.steps,
            parameter_override_bundle_ref=second_basis.parameter_override_bundle_ref,
        )
        unscoped_store = FileSystemCAS(scoped_store.root)
        late_report = plan_selected_model_input_routing(
            unscoped_store,
            obligation_set_ref=second_preflight.obligation_set_ref,
            selected_basis=second_basis,
            catalog_authority=authority,
            report_version="2.0",
        )
        (late_route,) = late_report.report.routes
        assert late_route.query_envelope is not None
        assert _routing_query_key(late_route.query_envelope) == _routing_query_key(
            route.query_envelope
        )
        assert late_report.report_ref != route_result.report_ref
        with pytest.raises(
            ValueError,
            match="model_input_routing_use_decision_inventory_stale",
        ):
            verify_model_input_routing_use_decision_current(
                case.store,
                use_decision_ref,
                expected_report_ref=route_result.report_ref,
                expected_obligation_set_ref=preflight.obligation_set_ref,
                selected_basis=selected_basis,
                catalog_authority=authority,
            )

    finally:
        case.close()


def test_routing_reverse_view_requires_complete_typed_query_roles() -> None:
    """Manifest role extraction fails closed instead of treating gaps as no routes."""
    from types import SimpleNamespace

    def role(role_name: str, artifact_id: str) -> SimpleNamespace:
        return SimpleNamespace(
            role=role_name,
            artifact_id=artifact_id,
            manifest_profile_sha256="sha256:" + "a" * 64,
        )

    complete_manifest = SimpleNamespace(
        inputs=[
            role("selected_input_interface", "interface"),
            role("route.0.model_semantic_definition", "definition"),
            role("route.0.model_representation", "representation"),
            role("route.0.measurement_binding_profile", "profile"),
        ]
    )
    memberships, error = _coarse_route_memberships(complete_manifest)
    assert error is None
    assert memberships == (
        (
            ("interface", "sha256:" + "a" * 64),
            ("definition", "sha256:" + "a" * 64),
            ("representation", "sha256:" + "a" * 64),
            ("profile", "sha256:" + "a" * 64),
        ),
    )

    incomplete_manifest = SimpleNamespace(inputs=complete_manifest.inputs[:-1])
    missing_memberships, missing_error = _coarse_route_memberships(incomplete_manifest)
    assert missing_memberships == ()
    assert missing_error == "model_input_routing_reverse_view_query_roles_incomplete"

    malformed_manifest = SimpleNamespace(
        inputs=[*complete_manifest.inputs, role("route.malformed.definition", "ignored")]
    )
    malformed_memberships, malformed_error = _coarse_route_memberships(malformed_manifest)
    assert malformed_memberships == ()
    assert malformed_error == "model_input_routing_reverse_view_manifest_role_invalid"

    gapped_manifest = SimpleNamespace(
        inputs=[
            *complete_manifest.inputs,
            role("route.2.model_semantic_definition", "definition-2"),
            role("route.2.model_representation", "representation-2"),
            role("route.2.measurement_binding_profile", "profile-2"),
        ]
    )
    gapped_memberships, gapped_error = _coarse_route_memberships(gapped_manifest)
    assert gapped_memberships == ()
    assert gapped_error == "model_input_routing_reverse_view_route_roles_incomplete"


def test_new_semantic_definition_revision_rebinds_selected_model_input(
    tmp_path: Path,
) -> None:
    """A compiled model revision must carry its exact changed semantic definition."""
    old_case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path / "definition-r1",
        opening_balance_usd=None,
        mechanism_start_step=2,
        model_input_port_declaration_builder=_fiscal_input_declaration,
    )
    new_case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path / "definition-r2",
        opening_balance_usd=None,
        mechanism_start_step=2,
        model_input_port_declaration_builder=partial(
            _fiscal_input_declaration,
            definition_revision="r2",
            definition_meaning=(
                "Government fiscal balance for a bounded population and period,"
                " including the explicitly revised opening-balance convention."
            ),
        ),
    )
    try:
        old_port, old_basis, old_preflight = _select_program_graph_routing_inputs(
            old_case,
            run_id="model-input-definition-r1",
        )
        new_port, new_basis, new_preflight = _select_program_graph_routing_inputs(
            new_case,
            run_id="model-input-definition-r2",
        )
        old_definition = validate_core_model_json_artifact(
            VariableSemanticDefinition,
            old_case.store,
            old_port.semantic_definition_ref,
        )
        new_definition = validate_core_model_json_artifact(
            VariableSemanticDefinition,
            new_case.store,
            new_port.semantic_definition_ref,
        )
        assert (old_definition.namespace, old_definition.stable_id) == (
            new_definition.namespace,
            new_definition.stable_id,
        )
        assert old_definition.revision == "r1"
        assert new_definition.revision == "r2"
        assert old_definition.meaning != new_definition.meaning
        assert old_port.semantic_definition_ref != new_port.semantic_definition_ref

        old_representation = validate_core_model_json_artifact(
            VariableRepresentation,
            old_case.store,
            old_port.representation_ref,
        )
        new_representation = validate_core_model_json_artifact(
            VariableRepresentation,
            new_case.store,
            new_port.representation_ref,
        )
        assert old_representation.model_dump(
            mode="python",
            exclude={"semantic_definition_ref"},
        ) == new_representation.model_dump(
            mode="python",
            exclude={"semantic_definition_ref"},
        )

        authority, _ = _resolver(
            tmp_path / "catalog-definition-revisions",
            authority_entry=_authority_entry(
                old_port.semantic_definition_ref,
                old_port.representation_ref,
                suffix="definition-r1",
            ),
        )
        old_entry = authority._load_registry().entries[0]
        new_entry = _authority_entry(
            new_port.semantic_definition_ref,
            new_port.representation_ref,
            suffix="definition-r2",
        )
        old_route = plan_selected_model_input_routing(
            old_case.store,
            obligation_set_ref=old_preflight.obligation_set_ref,
            selected_basis=old_basis,
            catalog_authority=authority,
            report_version="2.0",
        )
        assert (
            verify_model_input_routing_report(
                old_case.store,
                old_route.report_ref,
                expected_obligation_set_ref=old_preflight.obligation_set_ref,
                selected_basis=old_basis,
                catalog_authority=authority,
            )
            == old_route.report
        )
        _replace_authority_registry(authority, (old_entry, new_entry))
        assert (
            verify_model_input_routing_report(
                old_case.store,
                old_route.report_ref,
                expected_obligation_set_ref=old_preflight.obligation_set_ref,
                selected_basis=old_basis,
                catalog_authority=authority,
            )
            == old_route.report
        )
        new_route = plan_selected_model_input_routing(
            new_case.store,
            obligation_set_ref=new_preflight.obligation_set_ref,
            selected_basis=new_basis,
            catalog_authority=authority,
            report_version="2.0",
        )
        (old_binding,) = old_route.report.routes
        (new_binding,) = new_route.report.routes
        assert old_binding.disposition == new_binding.disposition == "resolved"
        assert old_binding.query_envelope is not None
        assert new_binding.query_envelope is not None
        assert (
            old_binding.query_envelope.model_semantic_definition_ref
            == old_port.semantic_definition_ref
        )
        assert (
            new_binding.query_envelope.model_semantic_definition_ref
            == new_port.semantic_definition_ref
        )
        assert old_binding.query_envelope.model_semantic_definition_ref != (
            new_binding.query_envelope.model_semantic_definition_ref
        )
        with pytest.raises(
            ValueError,
            match="model_input_routing_obligation_set_selection_mismatch",
        ):
            verify_model_input_routing_report(
                old_case.store,
                old_route.report_ref,
                expected_obligation_set_ref=new_preflight.obligation_set_ref,
                selected_basis=new_basis,
                catalog_authority=authority,
            )
        assert (
            verify_model_input_routing_report(
                new_case.store,
                new_route.report_ref,
                expected_obligation_set_ref=new_preflight.obligation_set_ref,
                selected_basis=new_basis,
                catalog_authority=authority,
            )
            == new_route.report
        )
    finally:
        old_case.close()
        new_case.close()


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
        port, selected_basis, preflight = _select_program_graph_routing_inputs(
            case,
            run_id="model-input-routing-test",
        )

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
        assert [row.entry_id for row in route_v2.query_envelope.rows] == [selected_entry.entry_id]
        assert route_v2.query_envelope.rows[0].disposition == "compatible"
        assert route_v2.source_descriptor is not None
        assert route_v2.source_descriptor.query_envelope is None
        assert (
            route_v2.source_descriptor.authority_registry_content_sha256 == registry_before_sha256
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
        assert (
            sum(row.disposition == "compatible" for row in ambiguous_route.query_envelope.rows) == 2
        )
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
