"""Serve a held-out opening stock from its signed activation through numerical N5."""

from __future__ import annotations

import json
from contextlib import ExitStack, closing, contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    artifact_manifest_profile_sha256,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
    read_core_json_artifact,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import (
    SchemaInfo,
    WarningRecord,
    artifact_ref_identity_key,
)
from polisyos.core.contracts import (
    ScopedCorrespondenceBasis,
    ScopedMeasurementOccurrence,
    load_resolved_input_binding_manifest,
)
from polisyos.core.contracts.epoch import load_verified_epoch_statement
from polisyos.core.contracts.model_input_requirements import (
    ModelInputPortDeclaration,
    load_model_input_obligation_set,
    load_model_input_port_declaration,
    persist_model_input_port_declaration,
)
from polisyos.core.contracts.runtime import (
    RunModelInputUseN5SuccessorProjectionV2,
    RunModelInputUseN5SuccessorResponse,
)
from polisyos.core.contracts.variable_binding import (
    MeasurementAxis,
    MeasurementBindingProfile,
    MeasurementBindingProfileRef,
    SelectedVariableBindingRef,
    VariableRepresentationRef,
    VariableSemanticDefinition,
    VariableSemanticDefinitionRef,
    load_variable_representation,
    variable_representation_manifest_inputs,
)
from polisyos.core.security.identity import PolicyOSRole
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.data_forge.read_api.catalog import (
    AcquisitionAuthorityError,
    build_authority_entry,
    build_authority_registry,
)
from polisyos.foundry.data_plane import load_input_bindings
from polisyos.foundry.execute import admit_semantic_horizon_step_chain, load_state_snapshot
from polisyos.ir.trinity import load_trinity_bundle_artifact
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.deployment_security import (
    DeploymentSecurityConfig,
    build_deployment_security,
)
from polisyos.runtime.http.services import control_plane_store as control_plane_store_owner
from polisyos.runtime.http.services import model_input_successor_action as successor_action_owner
from polisyos.runtime.http.services.control import generation_cycle as generation_owner
from polisyos.runtime.http.services.control.generation_cycle import (
    CompiledRecursiveGenerationCycleRun,
)
from polisyos.runtime.http.services.model_input_successor_action import (
    MODEL_INPUT_USE_PERMISSION,
    ModelInputSuccessorActionRequest,
    ModelInputUseActionCheckpoint,
    resolve_model_input_successor_action,
)
from polisyos.runtime.quality import agent_action_authority as authority
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.generation_cycle import (
    JointSimulationPort,
    load_joint_simulation_result,
)
from polisyos.runtime.quality.generic_simulation_admission import (
    GenericCycleSimulationAdmissionOwner,
    GenericCycleSimulationN5ExecutionV4,
    GenericCycleSimulationN5ExecutionV5,
    parse_generic_cycle_simulation_n5_execution,
)
from polisyos.runtime.quality.model_input_routing import (
    MODEL_INPUT_ROUTING_COMPATIBILITY_RULE_VERSION,
    MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION_V2,
    _routing_query_key,
    read_model_input_routing_report,
    read_model_input_routing_use_decision,
)
from polisyos.runtime.quality.model_input_successor_selection import (
    persist_model_input_successor_selection,
    read_model_input_successor_selection,
)
from polisyos.runtime.quality.substrate_registry import default_substrate_catalog_paths
from tests._helpers import acquisition_served_history as served
from tests._helpers.acquisition_human_decision import (
    _mandate_authority_evidence,
    persist_signed,
)
from tests._helpers.acquisition_production import _entry, bind_fixture_l1_catalog_source
from tests._helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker
from tests._helpers.lane01_candidate_action_served import _approve_candidate_action
from tests._helpers.lane01_wdi_profiles import CandidateWDIProfile
from tests._helpers.program_graph_tax_subsidy_input import (
    prepare_program_graph_tax_subsidy_input_case,
)
from tests._helpers.runtime_http import _DeterministicSpanSupportClient, _valid_intake_for_mode
from tests._helpers.semantic_epoch_native import make_native_live_measurement_history
from tests.integration.runtime_quality.test_generic_n4_child_profile_set_served import (
    controlled_candidate_gateway as _gateway_fixture,
)
from tests.integration.runtime_quality.test_program_graph_held_out_fund_binding import (
    _activated_fund,
    _bind_activated_fund,
    _fund_port,
    _held_out_declaration,
    _treasury_stock_declaration,
)
from tests.integration.runtime_quality.test_program_graph_model_input_served import (
    _INCOME,
    _OUTCOME,
    _fiscal_problem,
    _selected_profile,
    _stock_grounding_source,
    world_fixture,
)
from tests.integration.runtime_quality.test_program_graph_stock_n7_served import (
    _configure_stock_provider,
)
from tests.unit.runtime.quality.test_model_input_requirements import (
    _context as _input_context,
)
from tests.unit.runtime.quality.test_model_input_requirements import (
    _interface as _input_interface,
)
from tests.unit.runtime.quality.test_model_input_requirements import (
    _opening_stock_port,
)
from tests.unit.runtime.quality.test_model_input_requirements import (
    _preflight as _input_preflight,
)

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from polisyos.core.contracts.model_input_requirements import ModelInputPort
    from polisyos.data_forge.read_api.catalog import CanonicalAcquisitionAuthority
    from polisyos.runtime.http.services.control import ControlPlaneService
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationProfileV1,
    )
    from tests._helpers.controlled_candidate_profile import ControlledCandidateGateway

controlled_candidate_gateway = _gateway_fixture
_ROUTE_TEMPLATE = "/api/v1/runs/{run_id}/model-input-use"
_OPENING_CASH = 640.0
# The scheduled 1/8 subsidy debits the sum of the two eligible incomes.
_EXPECTED_BALANCES = (_OPENING_CASH, _OPENING_CASH, _OPENING_CASH - (100 + 200) / 8)


class _InjectedN5PersistCrash(BaseException):
    """Stop one worker after canonical V5 readback but before its checkpoint write."""


class _InjectedN5PreflightStop(BaseException):
    """Stop a real selected action immediately before its first physical N5."""


def _n5_projection_refs(
    result: Any,
) -> tuple[ArtifactRef | None, ArtifactRef | None, ArtifactRef | None]:
    """Project the selected numerical refs from either supported response version."""
    if isinstance(result, RunModelInputUseN5SuccessorProjectionV2):
        return (
            result.current_semantic_successor_ref,
            result.original_execution_ref,
            result.original_result_ref,
        )
    return result.semantic_successor_ref, result.n5_execution_ref, result.simulation_result_ref


def _held_out_methodology_declaration(
    store: FileSystemCAS, *, fact_log_root: Path
) -> tuple[ArtifactRef, ModelInputPort, SelectedVariableBindingRef]:
    """Build a held-out target port with an optional, test-owned Fabric method document."""
    from polisyos.fabric.docs.ingestion import ingest_doc_bytes
    from polisyos.fabric.docs.types import DocSourceSpec

    source_declaration_ref = _held_out_declaration(store)
    (source_port,) = load_model_input_port_declaration(store, source_declaration_ref).ports
    source_representation = load_variable_representation(store, source_port.representation_ref)
    assert source_representation.schema_version == "polisyos.catalog.variable_representation.v1"
    assert source_representation.methodology_ref is None

    document = ingest_doc_bytes(
        cas=store,
        fact_log_root=fact_log_root,
        source=DocSourceSpec(
            source_locator="repo://test/held-out-stock/measurement-method/r1",
            license="test-owned",
            title="Test-only measurement method",
        ),
        raw_bytes=(
            b"Test-owned method note for a controlled measurement fixture. "
            b"Its empirical validity and external authority are not established.\n"
        ),
        mime="text/plain",
    )
    document_manifest = store.get_manifest(document.raw_ref)
    methodology_ref = SelectedVariableBindingRef(
        artifact_id=document_manifest.artifact_id,
        kind=document_manifest.kind,
        media_type=document_manifest.media_type,
        manifest_profile_sha256=artifact_manifest_profile_sha256(document_manifest),
    )

    target_representation = source_representation.model_copy(
        update={
            "schema_version": "polisyos.catalog.variable_representation.v2",
            "representation_id": "test.public-benefit-fund.opening-cash-with-method",
            "methodology_ref": methodology_ref,
        }
    )
    target_representation_ref = VariableRepresentationRef.model_validate(
        store.put_json(
            target_representation,
            PutOptions(
                kind=target_representation.ARTIFACT_KIND,
                media_type=target_representation.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=target_representation.ARTIFACT_SCHEMA_NAME,
                    version="2.0",
                ),
                inputs=list(variable_representation_manifest_inputs(target_representation)),
            ),
            return_selected_profile=True,
        ).model_dump(mode="json")
    )
    source_profile = validate_core_model_json_artifact(
        MeasurementBindingProfile, store, source_port.binding_profile_ref
    )
    assert MeasurementAxis.METHODOLOGY_REF not in source_profile.optional_axes
    target_profile = source_profile.model_copy(
        update={
            "schema_version": "polisyos.catalog.measurement_binding_profile.v2",
            "optional_axes": (*source_profile.optional_axes, MeasurementAxis.METHODOLOGY_REF),
        }
    )
    target_profile_ref = MeasurementBindingProfileRef.model_validate(
        store.put_json(
            target_profile,
            PutOptions(
                kind=target_profile.ARTIFACT_KIND,
                media_type=target_profile.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(name=target_profile.ARTIFACT_SCHEMA_NAME, version="2.0"),
            ),
            return_selected_profile=True,
        ).model_dump(mode="json")
    )
    target_port = source_port.model_copy(
        update={
            "representation_ref": target_representation_ref,
            "binding_profile_ref": target_profile_ref,
        }
    )
    target_declaration_ref = persist_model_input_port_declaration(
        store, ModelInputPortDeclaration(ports=(target_port,))
    )
    return target_declaration_ref, source_port, methodology_ref


def _held_out_transport_reserve_declaration(store: FileSystemCAS) -> ArtifactRef:
    """Enroll an unrelated transport reserve on the existing opening-stock profile."""
    template_ref = _held_out_declaration(store)
    (template_port,) = load_model_input_port_declaration(store, template_ref).ports
    port = _fund_port(store, template_port, fund="transport-maintenance-reserve")
    return persist_model_input_port_declaration(store, ModelInputPortDeclaration(ports=(port,)))


def _misrepresented_transport_source_port(
    store: FileSystemCAS,
    port: ModelInputPort,
    *,
    axis: str,
) -> ModelInputPort:
    """Make same-label source metadata with one representation axis corrupted."""
    representation = load_variable_representation(store, port.representation_ref)
    updates: dict[str, object]
    if axis == "quantity_kind":
        updates = {"quantity_kind": "flow"}
    elif axis == "denominator_ref":
        evidence_ref = store.put_bytes(
            b"Test-only unrelated annual output definition; no empirical authority.\n",
            PutOptions(
                kind="tests.transport_reserve_denominator_definition",
                media_type="text/plain",
            ),
            return_selected_profile=True,
        )
        definition_ref = store.put_json(
            VariableSemanticDefinition(
                namespace="test.national-output",
                stable_id="annual-total",
                revision="1",
                meaning="Test-only annual economy-wide output denominator.",
                definition_evidence_refs=(
                    SelectedVariableBindingRef.model_validate(
                        evidence_ref.model_dump(mode="python")
                    ),
                ),
            ),
            PutOptions(
                kind="catalog.variable_semantic_definition",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.catalog.VariableSemanticDefinition",
                    version="1.0",
                ),
                inputs=[input_ref_from_artifact_ref(evidence_ref, role="definition_evidence")],
            ),
            return_selected_profile=True,
        )
        updates = {
            "denominator_ref": VariableSemanticDefinitionRef.model_validate(
                definition_ref.model_dump(mode="python")
            )
        }
    else:
        raise ValueError(f"unsupported test representation axis: {axis}")
    wrong_representation = representation.model_copy(update=updates)
    wrong_ref = VariableRepresentationRef.model_validate(
        store.put_json(
            wrong_representation,
            PutOptions(
                kind=wrong_representation.ARTIFACT_KIND,
                media_type=wrong_representation.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=wrong_representation.ARTIFACT_SCHEMA_NAME,
                    version="1.0",
                ),
                inputs=list(variable_representation_manifest_inputs(wrong_representation)),
            ),
            return_selected_profile=True,
        ).model_dump(mode="python")
    )
    return port.model_copy(update={"representation_ref": wrong_ref})


def _sign_model_input_mandate(
    control: ControlPlaneService,
    *,
    trust: served._ExternalTrust,
    key_root: Path,
    signers: dict[str, Any],
    identities: dict[str, str],
    run_id: str,
    job_id: str,
    route_id: str,
    digest: str,
) -> dict[str, Any]:
    """Appoint a current synthetic mandate for this exact signed action resource."""
    now = datetime.now(UTC)
    valid_from = now - timedelta(minutes=1)
    valid_until = now + timedelta(hours=1)
    contract = served._contract()
    (base_envelope,) = contract.action_envelopes
    envelope = authority.DelegatedActionEnvelope.model_validate(
        {
            **base_envelope.model_dump(mode="python"),
            "action_kind": authority.MODEL_INPUT_USE_ACTION_KIND,
            "operation_id": authority.MODEL_INPUT_USE_ACTION_KIND,
            "required_permission": MODEL_INPUT_USE_PERMISSION,
            "mandate_owner_ref": identities["owner"],
            "authorized_subject": "acquisition-operator",
            "authorized_runtime_roles": (PolicyOSRole.ANALYST,),
            "required_tenant_id": served.TENANT,
            "required_resource_digest": digest,
            "valid_from": valid_from,
            "valid_until": valid_until,
        }
    )
    contract = type(contract).model_validate(
        {
            **contract.model_dump(mode="python"),
            "mandate_owner_ref": identities["owner"],
            "action_envelopes": (envelope,),
        }
    )
    context = {
        "tenant_id": served.TENANT,
        "cell_id": served.CELL,
        "run_id": run_id,
        "job_id": job_id,
        "now": now,
    }
    with tenant_scope(None, tenant_id=served.TENANT, cell_id=served.CELL):
        contract_ref = persist_signed(
            control,
            contract,
            kind=authority.DELEGATION_CONTRACT_ARTIFACT_KIND,
            schema_name="polisyos.runtime.DelegationContract",
            schema_version=authority.LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
            signer=signers["owner"],
            signer_identity=identities["owner"],
            **context,
        )
        current_ref = persist_signed(
            control,
            _mandate_authority_evidence(
                owner_ref=identities["owner"],
                signer_identity=identities["current"],
                rule_version_ref=contract.rule_version_ref,
                effective_from=valid_from,
                effective_until=valid_until,
            ),
            kind=authority.CURRENT_MANDATE_OWNER_ARTIFACT_KIND,
            schema_name="polisyos.runtime.CurrentMandateOwnerEvidence",
            schema_version=authority.CURRENT_MANDATE_OWNER_SCHEMA_VERSION,
            signer=signers["current"],
            signer_identity=identities["current"],
            **context,
        )
        limitation_ref = control._artifact_store.put_json(
            {"limitation": "Synthetic local ledger supplies candidate inputs only."},
            PutOptions(kind="test.acquisition.disconfirming", media_type="application/json"),
        )
    slot = {
        "tenant_id": served.TENANT,
        "cell_id": served.CELL,
        "run_id": run_id,
        "route_id": route_id,
        "resource_digest": digest,
        "delegation_contract_ref": contract_ref,
        "mandate_owner_ref": identities["owner"],
        "delegation_public_key_path": str(key_root / "owner.pub"),
        "current_mandate_evidence_ref": current_ref,
        "current_mandate_signer_identity": identities["current"],
        "current_mandate_public_key_path": str(key_root / "current.pub"),
        "verifier_provenance_ref": "fixture://appointment-registry",
        "decision_information_refs": [limitation_ref.model_dump(mode="json")],
        "decision_disconfirming_refs": [limitation_ref.model_dump(mode="json")],
    }
    trust.raw["acquisition_authority"]["mandates"] = [slot]
    return slot


def _assert_foundry_successor(
    store: FileSystemCAS,
    *,
    original: GenericCycleSimulationN5ExecutionV4,
    mutation: ModelInputSuccessorActionRequest,
    action_job_id: str,
    checkpoint: ModelInputUseActionCheckpoint,
    expected_methodology_ref: ArtifactRef | None = None,
    expected_balances: tuple[float, ...] = _EXPECTED_BALANCES,
) -> None:
    """Recompute every step through Foundry and check independent cash arithmetic."""
    execution_ref = checkpoint.execution_ref
    result_ref = checkpoint.result_ref
    assert execution_ref is not None and result_ref is not None
    execution = parse_generic_cycle_simulation_n5_execution(
        read_core_json_artifact(store, execution_ref).value
    )
    assert type(execution) is GenericCycleSimulationN5ExecutionV5
    assert execution.input_ref == original.input_ref
    assert execution.n4_source_ref == original.n4_source_ref
    assert execution.action_job_id == action_job_id and execution.result_ref == result_ref
    assert execution.semantic_successor_ref == checkpoint.semantic_successor_ref
    selected = GenericCycleSimulationAdmissionOwner(
        profiles=(), store=store
    ).prepare_semantic_successor_request(
        semantic_successor_ref=checkpoint.semantic_successor_ref,
        expected_blocked_execution_ref=mutation.blocked_execution_ref,
        expected_input_ref=original.input_ref,
    )
    assert selected.selection.activation_receipt_ref == mutation.activation_receipt_ref
    assert selected.selection.observation_id == mutation.observation_id
    request = selected.request
    assert execution.request_binding.request.model_dump(mode="json") == request.model_dump(
        mode="json"
    )
    result = load_joint_simulation_result(result_ref, store=store, expected_request=request)
    (plan,) = request.engine_plan
    selected_bindings = plan.program_semantic_input_bindings_ref
    assert selected_bindings is not None and selected_bindings.manifest_profile_sha256 is not None
    bindings = load_input_bindings(store, selected_bindings)
    manifest_ref = bindings.resolved_binding_manifest_ref
    assert manifest_ref is not None and manifest_ref.manifest_profile_sha256 is not None
    manifest = load_resolved_input_binding_manifest(store, manifest_ref)
    obligation_set, (obligation,) = load_model_input_obligation_set(
        store, original.model_input_obligation_set_ref
    )
    assert artifact_ref_identity_key(manifest.model_input_obligation_set_ref) == (
        artifact_ref_identity_key(original.model_input_obligation_set_ref)
    )
    assert artifact_ref_identity_key(manifest.data_snapshot_ref) == artifact_ref_identity_key(
        bindings.data_snapshot_ref
    )
    assert len(manifest.measurements) == 1
    (measurement,) = manifest.measurements
    assert artifact_ref_identity_key(measurement.model_input_obligation_ref) == (
        artifact_ref_identity_key(obligation_set.obligation_refs[0])
    )
    occurrence = validate_core_model_json_artifact(
        ScopedMeasurementOccurrence, store, measurement.selected_occurrence_ref
    )
    assert occurrence.observation_id == mutation.observation_id
    assert artifact_ref_identity_key(occurrence.source_receipt_ref) == artifact_ref_identity_key(
        mutation.activation_receipt_ref
    )
    correspondence = validate_core_model_json_artifact(
        ScopedCorrespondenceBasis, store, measurement.correspondence_ref
    )
    assert correspondence.model_port_id == obligation.port.port_id
    assert artifact_ref_identity_key(correspondence.occurrence_ref) == artifact_ref_identity_key(
        measurement.selected_occurrence_ref
    )
    assert artifact_ref_identity_key(correspondence.target_definition_ref) == (
        artifact_ref_identity_key(obligation.port.semantic_definition_ref)
    )
    assert artifact_ref_identity_key(correspondence.target_representation_ref) == (
        artifact_ref_identity_key(obligation.port.representation_ref)
    )
    if expected_methodology_ref is not None:
        from polisyos.core.contracts.fabric import (
            AcquiredObservationSemanticInputDataSnapshotLineage,
            DataSnapshot,
        )

        source_representation = load_variable_representation(
            store, correspondence.source_representation_ref
        )
        target_representation = load_variable_representation(
            store, correspondence.target_representation_ref
        )
        target_representation_manifest = store.get_manifest(
            correspondence.target_representation_ref
        )
        assert source_representation.schema_version == (
            "polisyos.catalog.variable_representation.v1"
        )
        assert source_representation.methodology_ref is None
        assert target_representation.schema_version == (
            "polisyos.catalog.variable_representation.v2"
        )
        assert target_representation.methodology_ref == expected_methodology_ref
        assert tuple(target_representation_manifest.inputs) == (
            variable_representation_manifest_inputs(target_representation)
        )
        assert any(
            edge.role == "methodology"
            and edge.artifact_id == expected_methodology_ref.artifact_id
            and edge.manifest_profile_sha256 == expected_methodology_ref.manifest_profile_sha256
            for edge in target_representation_manifest.inputs
        )
        profile = validate_core_model_json_artifact(
            MeasurementBindingProfile, store, correspondence.binding_profile_ref
        )
        assert profile.schema_version == "polisyos.catalog.measurement_binding_profile.v2"
        assert MeasurementAxis.METHODOLOGY_REF in profile.optional_axes
        snapshot = validate_core_model_json_artifact(
            DataSnapshot, store, bindings.data_snapshot_ref
        )
        lineage = snapshot.source_lineage
        assert isinstance(lineage, AcquiredObservationSemanticInputDataSnapshotLineage)
        assert artifact_ref_identity_key(lineage.selection.correspondence_basis_ref) == (
            artifact_ref_identity_key(measurement.correspondence_ref)
        )
        verified_limitations = result.verified_semantic_input_limitation_codes
        assert verified_limitations is not None
        assert "optional_axis_unknown:methodology_ref" in verified_limitations
    else:
        source_representation = load_variable_representation(
            store, correspondence.source_representation_ref
        )
        target_representation = load_variable_representation(
            store, correspondence.target_representation_ref
        )
        assert source_representation.schema_version == (
            "polisyos.catalog.variable_representation.v1"
        )
        assert target_representation.schema_version == (
            "polisyos.catalog.variable_representation.v1"
        )
        assert source_representation.methodology_ref is None
        assert target_representation.methodology_ref is None
    (route,) = read_model_input_routing_report(store, mutation.routing_report_ref).routes
    assert artifact_ref_identity_key(route.obligation_ref) == artifact_ref_identity_key(
        measurement.model_input_obligation_ref
    )
    assert route.source_descriptor is not None
    assert artifact_ref_identity_key(route.source_descriptor.source_semantic_definition_ref) == (
        artifact_ref_identity_key(correspondence.source_definition_ref)
    )
    assert len(result.physical_work_observations) == 1
    assert result.physical_work_observations[0].status == "completed"
    assert {trajectory.run_level for trajectory in result.trajectories} == {"individual", "joint"}
    for trajectory in result.trajectories:
        assert trajectory.engine_kind == "program_graph"
        (replication,) = trajectory.semantic_program_graph_replications
        steps = admit_semantic_horizon_step_chain(store, replication.step_result_refs)
        assert len(steps) == len(expected_balances)
        for step, expected in zip(steps, expected_balances, strict=True):
            assert step.basis is not None
            assert step.basis.input_bindings_ref == selected_bindings
            assert step.simulation_result.state_snapshot_ref is not None
            state = load_state_snapshot(
                store, snapshot_ref=step.simulation_result.state_snapshot_ref
            )
            assert float(state.government_balance) == expected
        assert trajectory.points[-1].outcomes[_OUTCOME] == expected_balances[-1]


def _assert_routing_use_selection(
    store: FileSystemCAS,
    *,
    mutation: ModelInputSuccessorActionRequest,
    checkpoint: ModelInputUseActionCheckpoint,
    run_id: str,
    source_job_id: str,
    action_job_id: str,
    expected_registry_sha256: str,
) -> None:
    """Reopen the public action's exact selection and any linked current-use decision."""
    selection = read_model_input_successor_selection(store, checkpoint.semantic_successor_ref)
    report = read_model_input_routing_report(store, mutation.routing_report_ref)
    assert report.schema_version == MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION_V2
    assert selection.schema_version == "polisyos.runtime.ModelInputSuccessorSelection@2.0"
    assert selection.tenant_id == served.TENANT
    assert selection.cell_id == served.CELL
    assert selection.run_id == run_id
    assert selection.source_job_id == source_job_id
    assert selection.action_job_id == action_job_id
    assert selection.compiled_ref == mutation.compiled_ref
    assert selection.blocked_execution_ref == mutation.blocked_execution_ref
    assert selection.routing_report_ref == mutation.routing_report_ref
    assert selection.activation_receipt_ref == mutation.activation_receipt_ref
    assert selection.observation_id == mutation.observation_id

    manifest = store.get_manifest(checkpoint.semantic_successor_ref)
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.version == "2.0"
    assert manifest.producer is not None
    assert manifest.producer.version == "2.0"
    assert manifest.tenant_context is not None
    assert manifest.tenant_context.tenant_id == served.TENANT
    assert manifest.tenant_context.cell_id == served.CELL
    decision_ref = selection.routing_use_decision_ref
    assert decision_ref is not None
    decision = read_model_input_routing_use_decision(store, decision_ref)
    (route,) = report.routes
    assert route.query_envelope is not None
    assert route.source_descriptor is not None
    assert route.disposition == "resolved"
    assert len(report.routes) == 1
    assert decision.routing_report_ref == mutation.routing_report_ref
    assert decision.route_port_id == route.port_id
    assert decision.query_key_sha256 == _routing_query_key(route.query_envelope).sha256
    assert decision.query_envelope_content_sha256 == route.query_envelope.content_sha256
    assert decision.authority_registry_content_sha256 == (
        route.source_descriptor.authority_registry_content_sha256
    )
    assert decision.authority_registry_content_sha256 == expected_registry_sha256
    assert decision.compatibility_rule_version == MODEL_INPUT_ROUTING_COMPATIBILITY_RULE_VERSION
    assert decision.active_tenant_id == served.TENANT
    assert decision.active_cell_id == served.CELL
    assert decision.authority_purpose == "candidate_model_input_route_recheck_only"
    linked = tuple(
        item for item in manifest.inputs if item.role == "model_input_routing_use_decision"
    )
    assert len(linked) == 1
    assert linked[0].artifact_id == decision_ref.artifact_id
    assert linked[0].manifest_profile_sha256 == decision_ref.manifest_profile_sha256
    decision_manifest = store.get_manifest(decision_ref)
    assert decision_manifest.artifact_schema is not None
    assert decision_manifest.artifact_schema.version == "1.0"
    assert decision_manifest.tenant_context is not None
    assert decision_manifest.tenant_context.tenant_id == served.TENANT
    assert decision_manifest.tenant_context.cell_id == served.CELL
    (report_input,) = tuple(
        item for item in decision_manifest.inputs if item.role == "routing_report"
    )
    assert report_input.artifact_id == mutation.routing_report_ref.artifact_id
    assert report_input.manifest_profile_sha256 == (
        mutation.routing_report_ref.manifest_profile_sha256
    )


def _assert_semantic_input_selection_refusals(
    store: FileSystemCAS,
    *,
    semantic_successor_ref: ArtifactRef,
    blocked_execution_ref: ArtifactRef,
    input_ref: ArtifactRef,
) -> None:
    """Prove a bad selected manifest or missing binding cannot re-enter N5."""
    owner = GenericCycleSimulationAdmissionOwner(profiles=(), store=store)
    selection = read_model_input_successor_selection(store, semantic_successor_ref)
    selected_bindings_ref = selection.semantic_foundry_input_bindings_ref
    bindings = load_input_bindings(store, selected_bindings_ref)
    manifest_ref = bindings.resolved_binding_manifest_ref
    assert manifest_ref is not None and manifest_ref.manifest_profile_sha256 is not None

    wrong_profile = "sha256:" + "0" * 64
    if wrong_profile == manifest_ref.manifest_profile_sha256:
        wrong_profile = "sha256:" + "1" * 64
    wrong_manifest_ref = type(manifest_ref).model_validate(
        {**manifest_ref.model_dump(mode="python"), "manifest_profile_sha256": wrong_profile}
    )
    mismatched_bindings = bindings.model_copy(
        update={"resolved_binding_manifest_ref": wrong_manifest_ref}
    )
    selected_bindings_manifest = store.get_manifest(selected_bindings_ref)
    mismatched_bindings_ref = store.put_json(
        mismatched_bindings,
        PutOptions(
            kind=selected_bindings_manifest.kind,
            media_type=selected_bindings_manifest.media_type,
            schema=selected_bindings_manifest.artifact_schema,
            canon=selected_bindings_manifest.canon,
            producer=selected_bindings_manifest.producer,
            inputs=selected_bindings_manifest.inputs,
            governance=selected_bindings_manifest.governance,
            tenant_context=selected_bindings_manifest.tenant_context,
            warnings=selected_bindings_manifest.warnings,
        ),
        return_selected_profile=True,
    )
    typed_mismatched_ref = type(selected_bindings_ref).model_validate(
        mismatched_bindings_ref.model_dump(mode="python")
    )
    mismatched_selection_ref = persist_model_input_successor_selection(
        store,
        selection.model_copy(update={"semantic_foundry_input_bindings_ref": typed_mismatched_ref}),
    )
    with pytest.raises(ValueError, match="foundry_input_bindings_semantic_manifest_edge_mismatch"):
        owner.prepare_semantic_successor_request(
            semantic_successor_ref=mismatched_selection_ref,
            expected_blocked_execution_ref=blocked_execution_ref,
            expected_input_ref=input_ref,
        )

    binding_blob, _ = store._paths(selected_bindings_ref.artifact_id)
    withheld_binding = binding_blob.with_name(f"{binding_blob.name}.withheld-test")
    binding_blob.rename(withheld_binding)
    try:
        with pytest.raises((FileNotFoundError, CanonicalProfileRefusalError)) as missing_binding:
            owner.prepare_semantic_successor_request(
                semantic_successor_ref=semantic_successor_ref,
                expected_blocked_execution_ref=blocked_execution_ref,
                expected_input_ref=input_ref,
            )
        if isinstance(missing_binding.value, CanonicalProfileRefusalError):
            assert missing_binding.value.code == "canon_profile_payload_unavailable"
    finally:
        withheld_binding.rename(binding_blob)


def _assert_v2_methodology_preflight(
    *,
    tmp_path: Path,
    store: FileSystemCAS,
    active: Any,
    control: ControlPlaneService,
    job: Any,
    profile: GenericCycleSimulationProfileV1,
    report_ref: ArtifactRef,
    report: Any,
    receipt_ref: ArtifactRef,
    observation_id: str,
    source_port: ModelInputPort,
    methodology_ref: SelectedVariableBindingRef,
) -> None:
    """Exercise target-document availability through the real pre-N5 Foundry reader."""
    from polisyos.core.contracts.fabric import (
        AcquiredObservationSemanticInputDataSnapshotLineage,
        DataSnapshot,
    )
    from polisyos.foundry.data_plane import (
        load_input_bindings,
        reconcile_semantic_input_bindings,
    )
    from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
    from polisyos.runtime.quality.model_input_requirements import (
        SelectedProgramGraphInputBasis,
    )
    from polisyos.runtime.quality.model_input_routing import (
        materialize_routed_model_input_observation,
    )

    invocation = report.selected_invocation
    selected_basis = SelectedProgramGraphInputBasis(
        context=invocation.context,
        program_graph_ref=invocation.program_graph_ref,
        exec_plan_ref=invocation.exec_plan_ref,
        registry_bundle_ref=invocation.registry_bundle_ref,
        input_bindings_ref=invocation.input_bindings_ref,
        steps=invocation.steps,
    )
    passport = AdmissionPassport.model_validate(
        load_verified_epoch_statement(
            store=store,
            ref=active.projections[active.entries[0].target_variable].passport_ref,
            expected_kind="epoch.acquisition_passport_snapshot",
        )
    )
    source_representation = load_variable_representation(store, source_port.representation_ref)
    assert source_representation.methodology_ref is None
    _, (obligation,) = load_model_input_obligation_set(store, report.obligation_set_ref)
    target_representation = load_variable_representation(store, obligation.port.representation_ref)
    assert target_representation.methodology_ref == methodology_ref

    ledger = control.llm_producer_settlement_store._ledger
    ledger_before = ledger.snapshot()
    source_job_before = control._control_store.get_job(job.job_id)
    assert source_job_before == job
    candidate = materialize_routed_model_input_observation(
        store,
        report_ref=report_ref,
        expected_obligation_set_ref=report.obligation_set_ref,
        selected_basis=selected_basis,
        catalog_authority=active.authority,
        overlay=active.overlay,
        receipt_ref=receipt_ref,
        passport=passport,
        observation_id=observation_id,
        profile_selection_ref=profile.profile_selection_ref,
        workspace_dir=tmp_path / "v2-methodology-preflight",
        transaction_time=datetime(2026, 10, 2, 12, tzinfo=UTC),
    )
    assert candidate.semantic_foundry_input_bindings_ref is not None
    bindings = load_input_bindings(store, candidate.semantic_foundry_input_bindings_ref)
    snapshot = validate_core_model_json_artifact(DataSnapshot, store, candidate.data_snapshot_ref)
    lineage = snapshot.source_lineage
    assert isinstance(lineage, AcquiredObservationSemanticInputDataSnapshotLineage)
    basis = validate_core_model_json_artifact(
        ScopedCorrespondenceBasis,
        store,
        lineage.selection.correspondence_basis_ref,
    )
    assert basis.source_representation_ref == source_port.representation_ref
    assert basis.target_representation_ref == obligation.port.representation_ref
    positive_notes = reconcile_semantic_input_bindings(store, bindings)
    assert "semantic_input_limitation:optional_axis_unknown:methodology_ref" in positive_notes

    target_document_blob, _ = store._paths(methodology_ref.artifact_id)
    withheld_document = target_document_blob.with_name("withheld-target-methodology")
    target_document_blob.rename(withheld_document)
    try:
        assert (
            load_variable_representation(store, source_port.representation_ref).methodology_ref
            is None
        )
        with pytest.raises(FileNotFoundError):
            reconcile_semantic_input_bindings(store, bindings)
    finally:
        withheld_document.rename(target_document_blob)

    assert (
        load_variable_representation(store, source_port.representation_ref).methodology_ref is None
    )
    assert load_variable_representation(store, basis.target_representation_ref).methodology_ref == (
        methodology_ref
    )
    assert reconcile_semantic_input_bindings(store, bindings) == positive_notes
    assert ledger.snapshot() == ledger_before
    assert control._control_store.get_job(job.job_id) == source_job_before


def _run_activated_held_out_stock_scenario(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: ControlledCandidateGateway,
    *,
    methodology_v2: bool,
    fund: str = "public-benefit-fund",
    retained_sequence: bool = False,
    preflight_first_n5: bool = False,
) -> None:
    """Exercise one selected held-out stock profile through the served successor route."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("POLISYOS_RUNTIME_EXECUTION_PROFILE", "development")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", str(tmp_path / "control.sqlite3"))
    monkeypatch.setenv("POLISYOS_CACHE_HOME", str(tmp_path / "runtime-cache"))
    cas_root = tmp_path / "cas"
    runs_root = cas_root / "runs"
    problem_data = _fiscal_problem().model_dump(mode="json")
    fund_label = {
        "public-benefit-fund": "public-benefit fund",
        "transport-maintenance-reserve": "regional transport reserve",
        "treasury": "treasury",
    }[fund]
    problem_data["nl_provenance"]["raw_request"] = (
        f"Evaluate one bounded tax subsidy using the {fund_label}'s opening cash in USD. "
        "Do not promote generated candidates."
    )
    problem = DesignProblem.model_validate(problem_data)
    original_compiler = generation_owner.build_design_problem_from_nl_request
    source_ports: list[ModelInputPort] = []
    methodology_refs: list[SelectedVariableBindingRef] = []

    def build_port_declaration(store: FileSystemCAS) -> ArtifactRef:
        if not methodology_v2:
            if retained_sequence:
                return _treasury_stock_declaration(store)
            return (
                _held_out_declaration(store)
                if fund == "public-benefit-fund"
                else _held_out_transport_reserve_declaration(store)
            )
        declaration_ref, source_port, methodology_ref = _held_out_methodology_declaration(
            store,
            fact_log_root=tmp_path / "fabric-methodology-facts",
        )
        source_ports.append(source_port)
        methodology_refs.append(methodology_ref)
        return declaration_ref

    async def bind_actual_compiler_output(**kwargs: object) -> DesignProblem:
        compiled = await original_compiler(
            **{**kwargs, "span_support_client": _DeterministicSpanSupportClient()}
        )
        controlled_candidate_gateway.admit_compiled_problem(compiled)
        return compiled

    monkeypatch.setattr(
        generation_owner, "build_design_problem_from_nl_request", bind_actual_compiler_output
    )

    store = FileSystemCAS(cas_root).for_tenant(served.TENANT, served.CELL)
    with (
        closing(served._ExternalTrust(tmp_path)) as trust,
        ExitStack() as resources,
    ):
        signers, identities = served._key_config(tmp_path, trust)
        with tenant_scope(None, tenant_id=served.TENANT, cell_id=served.CELL):
            case = prepare_program_graph_tax_subsidy_input_case(
                tmp_path / "graph",
                opening_balance_usd=None,
                mechanism_start_step=2,
                intervention_notes=("do.target=agents.income",),
                intervention_measurement_expectations={
                    "sign": "increase",
                    "outcome": [_INCOME],
                    "effect_path": ["tax_subsidy", _INCOME, _INCOME],
                    "estimand": "average_treatment_effect",
                },
                model_input_port_declaration_builder=build_port_declaration,
                store=store,
                snapshot_id=world_fixture.SNAPSHOT_ID,
            )
            assert case.model_input_port_declaration_ref is not None
            (port,) = load_model_input_port_declaration(
                store, case.model_input_port_declaration_ref
            ).ports
            source_port = source_ports[0] if methodology_v2 else port
            expected_methodology_ref = methodology_refs[0] if methodology_v2 else None
            trinity = load_trinity_bundle_artifact(
                ensure_ir_artifact_store(store), case.trinity_ref
            )
        model_id = _configure_stock_provider(
            controlled_candidate_gateway,
            problem=problem,
            trinity=trinity,
            evidence_root=tmp_path / "llm",
        )

        def app(root: Path, profile: GenericCycleSimulationProfileV1 | None = None) -> Any:
            # Each app reopens the same tenant-owned bootstrap artifacts.
            with tenant_scope(None, tenant_id=served.TENANT, cell_id=served.CELL):
                return create_runtime_api_app(
                    cas_root=cas_root,
                    core_runs_root=runs_root,
                    deployment_security=build_deployment_security(
                        DeploymentSecurityConfig.from_mapping(trust.raw)
                    ),
                    enable_security_middlewares=True,
                    enable_csrf_protection=False,
                    repo_root=root,
                    generic_cycle_simulation_profiles=() if profile is None else (profile,),
                    generic_cycle_simulation_root_profile_id=None
                    if profile is None
                    else profile.profile_id,
                )

        def crash_after_durable_n5_persist(
            control: Any,
            *,
            action_job_id: str,
            evaluation_decision_present: bool,
        ) -> dict[str, Any]:
            from tests._helpers.candidate_experiment_served_execution import (
                _dispatch_crash_probe_once,
            )

            persist_n5_execution = GenericCycleSimulationAdmissionOwner.persist_n5_execution
            persisted: list[tuple[ArtifactRef, ArtifactRef, ArtifactRef]] = []

            def persist_then_crash(owner: Any, *args: Any, **kwargs: Any) -> ArtifactRef:
                execution_ref = persist_n5_execution(owner, *args, **kwargs)
                semantic_ref = kwargs.get("semantic_successor_ref")
                result_ref = kwargs.get("result_ref")
                if semantic_ref is not None:
                    assert kwargs.get("status") == "joint_simulated"
                    assert isinstance(result_ref, ArtifactRef)
                    persisted.append((execution_ref, result_ref, semantic_ref))
                    raise _InjectedN5PersistCrash("after durable Generic V5 readback")
                return execution_ref

            monkeypatch.setattr(
                GenericCycleSimulationAdmissionOwner,
                "persist_n5_execution",
                persist_then_crash,
            )
            try:
                with pytest.raises(_InjectedN5PersistCrash):
                    _dispatch_crash_probe_once(
                        control=control,
                        expected_job_id=action_job_id,
                        lease_seconds=10,
                    )
            finally:
                monkeypatch.setattr(
                    GenericCycleSimulationAdmissionOwner,
                    "persist_n5_execution",
                    persist_n5_execution,
                )
            assert len(persisted) == 1
            execution_ref, result_ref, semantic_ref = persisted[0]
            execution = parse_generic_cycle_simulation_n5_execution(
                read_core_json_artifact(store, execution_ref).value
            )
            assert type(execution) is GenericCycleSimulationN5ExecutionV5
            assert execution.action_job_id == action_job_id
            assert execution.semantic_successor_ref == semantic_ref
            assert execution.result_ref == result_ref
            interrupted_job = control._control_store.get_job(action_job_id)
            assert interrupted_job is not None and interrupted_job.state == "running"
            assert interrupted_job.attempt == 1
            assert interrupted_job.lease_expires_at is not None
            pending = ModelInputUseActionCheckpoint.model_validate(
                interrupted_job.progress["model_input_use"]
            )
            assert pending.semantic_successor_ref == semantic_ref
            assert pending.execution_ref is None and pending.result_ref is None
            assert (pending.evaluation_decision_ref is not None) is evaluation_decision_present
            if not evaluation_decision_present:
                assert pending.evaluation_expected_frontier_revision == 0
                assert pending.evaluation_expected_frontier_ref is None
            ledger_snapshot = control.llm_producer_settlement_store.snapshot_safe().model_dump(
                mode="json"
            )
            return {
                "action_job_id": action_job_id,
                "execution_ref": execution_ref,
                "result_ref": result_ref,
                "semantic_successor_ref": semantic_ref,
                "lease_expires_at": interrupted_job.lease_expires_at,
                "pending_checkpoint": pending,
                "ledger_snapshot": ledger_snapshot,
                "invocation_reservations": (
                    control.llm_producer_settlement_store._ledger.snapshot().invocation_reservations
                ),
            }

        def recover_durable_n5_crash(
            crash: dict[str, Any],
        ) -> tuple[Any, ModelInputUseActionCheckpoint]:
            with TestClient(app(root, profile)) as retry_client:
                retry_control = retry_client.app.state.runtime_container.control_service
                stop_embedded_control_worker(retry_control)
                before_retry = retry_control._control_store.get_job(crash["action_job_id"])
                assert before_retry is not None and before_retry.state == "running"
                assert before_retry.attempt == 1
                assert before_retry.lease_expires_at == crash["lease_expires_at"]
                ledger_before_retry = (
                    retry_control.llm_producer_settlement_store.snapshot_safe().model_dump(
                        mode="json"
                    )
                )
                assert ledger_before_retry == crash["ledger_snapshot"]
                recovery_now = before_retry.lease_expires_at + timedelta(seconds=1)

                def forbid_duplicate_n5(*args: Any, **kwargs: Any) -> Any:
                    del args, kwargs
                    raise AssertionError("durable recovery attempted a second semantic N5")

                with monkeypatch.context() as recovery_patch:
                    recovery_patch.setattr(
                        control_plane_store_owner,
                        "_utc_now",
                        lambda: recovery_now,
                    )
                    recovery_patch.setattr(
                        JointSimulationPort,
                        "run_semantic_successor",
                        forbid_duplicate_n5,
                    )
                    assert (
                        dispatch_one_control_job(
                            store=retry_control._control_store,
                            handler=retry_control._process_control_job,
                            expected_job_id=crash["action_job_id"],
                        )
                        == crash["action_job_id"]
                    )
                recovered_job = retry_control._control_store.get_job(crash["action_job_id"])
                assert recovered_job is not None and recovered_job.state == "completed", (
                    None if recovered_job is None else recovered_job.error_message
                )
                assert recovered_job.attempt == 2
                recovered = ModelInputUseActionCheckpoint.model_validate(
                    recovered_job.progress["model_input_use"]
                )
                assert recovered.semantic_successor_ref == crash["semantic_successor_ref"]
                assert recovered.execution_ref == crash["execution_ref"]
                assert recovered.result_ref == crash["result_ref"]
                ledger_after_retry = (
                    retry_control.llm_producer_settlement_store.snapshot_safe().model_dump(
                        mode="json"
                    )
                )
                assert ledger_after_retry == ledger_before_retry
                assert (
                    retry_control.llm_producer_settlement_store._ledger.snapshot().invocation_reservations
                    == crash["invocation_reservations"]
                )
                return recovered_job, recovered

        seeds = []
        unrelated_entry = _entry()

        def launch_before_activation(catalog: CanonicalAcquisitionAuthority) -> None:
            registry = catalog._load_registry()
            assert unrelated_entry.source_semantic_definition_ref is None
            initial_registry = build_authority_registry(
                baseline_content_sha256=registry.baseline_content_sha256,
                l5_measurement_registry_sha256=registry.l5_measurement_registry_sha256,
                entries=(*registry.entries, unrelated_entry),
            )
            catalog.registry_path.write_text(initial_registry.model_dump_json(), encoding="utf-8")
            root = catalog.repo_root
            skg_prior = _stock_grounding_source(root)
            prior_catalog = default_substrate_catalog_paths(root).l1_dcat_path
            prior_catalog.rename(tmp_path / "unused-grounding-only.duckdb")
            bind_fixture_l1_catalog_source(root, catalog.baseline_path)
            assert prior_catalog.resolve(strict=True) == catalog.baseline_path
            with tenant_scope(None, tenant_id=served.TENANT, cell_id=served.CELL):
                profile = _selected_profile(
                    case, trinity, problem, tmp_path / "world", skg_prior=skg_prior
                )
            with TestClient(app(root, profile)) as client:
                control = client.app.state.runtime_container.control_service
                stop_embedded_control_worker(control)
                launched = client.post(
                    "/api/v1/control/runs/nl",
                    headers={
                        "Authorization": trust.authorization_header("acquisition-operator"),
                        "X-Tenant-ID": served.TENANT,
                        "Idempotency-Key": "held-out-fund-before-activation",
                    },
                    json={
                        "request": problem.nl_provenance.raw_request,
                        "llm_model": model_id,
                        "max_iterations": 1,
                        "run_budget_usd": 5.0,
                        "run_budget_scope": "metered_paid_producers_and_bounded_candidate",
                        "context": {
                            "evaluation_safety_attempt": _valid_intake_for_mode(
                                "simulate_only"
                            ).model_dump(mode="json")
                        },
                    },
                )
                assert launched.status_code == 200, launched.text
                job_id = launched.json()["job_id"]
                assert (
                    dispatch_one_control_job(
                        store=control._control_store,
                        handler=control._process_control_job,
                        expected_job_id=job_id,
                    )
                    == job_id
                )
                job = control._control_store.get_job(job_id)
                assert job is not None and job.state == "completed", (
                    None if job is None else job.error_message
                )
                assert not control.llm_producer_settlement_store._ledger.snapshot().invocation_reservations
                seeds.append((job, profile))

        @contextmanager
        def activate_selected_stock() -> Any:
            if not retained_sequence:
                with _activated_fund(
                    tmp_path / "held-out-activation",
                    store=store,
                    port=source_port,
                    fund=fund,
                    before_activation=launch_before_activation,
                ) as active:
                    yield active
                return

            if methodology_v2 or fund != "treasury":
                raise AssertionError("retained_stock_sequence_requires_the_typed_treasury_port")
            live_profile = CandidateWDIProfile(
                construct="test.treasury.opening-cash",
                indicator_id="TEST.OPENING.CASH.USD",
                source_title="Test-owned opening cash stock",
                source_description=(
                    "Controlled USD opening-stock observations for a candidate-only test."
                ),
                target_slot="test.treasury.opening-cash",
                raw_unit="usd",
                canonical_unit="usd",
                transform="identity",
                transform_ref="fabric://units/usd-identity/v1",
                population="population:treasury",
                fixture_value=_OPENING_CASH,
                source_provenance_class="observed",
                valid_min=0.0,
                valid_max=10_000.0,
                country_code="UKR",
                country_id="UA",
                year=2022,
                catalog_metric_id="test.treasury.opening-cash",
            )
            live_history = make_native_live_measurement_history(
                tmp_path / "live-stock-history",
                profile=live_profile,
                semantic_definition_ref=source_port.semantic_definition_ref,
                representation_ref=source_port.representation_ref,
                source_measure_scope={
                    "population": "population:treasury",
                    "temporal_granularity": "annual",
                    "source_geography_id": "UA",
                    "geography_ref": "UA",
                    "jurisdiction_ref": "UA",
                    "time_period_basis": "calendar_year",
                },
                attempt_ids=(
                    "held-out-stock-a-initial",
                    "held-out-stock-b-equal",
                    "held-out-stock-c-changed",
                ),
                artifact_store=store,
                monkeypatch=monkeypatch,
            )
            try:
                launch_before_activation(live_history.authority)
                active = live_history.admit(_OPENING_CASH)
                active.live_history = live_history
                yield active
            finally:
                live_history.overlay.close()

        resources.enter_context(tenant_scope(None, tenant_id=served.TENANT, cell_id=served.CELL))
        active = resources.enter_context(activate_selected_stock())
        try:
            root = active.repo_root
            (entry,) = active.entries
            projection = active.projections[entry.target_variable]
            (selected_observation,) = projection.observations
            if methodology_v2:
                ((source_job, selected_profile),) = seeds
                compiled_ref = ArtifactRef.model_validate(
                    source_job.progress["compiled_recursive_generation_cycle_artifact_ref"]
                )
                compiled = CompiledRecursiveGenerationCycleRun.model_validate(
                    read_core_json_artifact(store, compiled_ref).value
                )
                (node,) = compiled.recursive_run.leaf_nodes
                assert node.cycle_run is not None
                (cycle,) = node.cycle_run.cycles
                blocked_execution_ref = cycle.simulation.generic_n5_execution_ref
                report_ref = cycle.model_input_routing_report_ref
                assert blocked_execution_ref is not None and report_ref is not None
                blocked_execution = parse_generic_cycle_simulation_n5_execution(
                    read_core_json_artifact(store, blocked_execution_ref).value
                )
                assert type(blocked_execution) is GenericCycleSimulationN5ExecutionV4
                assert blocked_execution.status == "simulation_blocked"
                assert blocked_execution.result_ref is None
                report = read_model_input_routing_report(store, report_ref)
                assert expected_methodology_ref is not None
                with TestClient(app(root, selected_profile)) as preflight_client:
                    control = preflight_client.app.state.runtime_container.control_service
                    stop_embedded_control_worker(control)
                    _assert_v2_methodology_preflight(
                        tmp_path=tmp_path,
                        store=store,
                        active=active,
                        control=control,
                        job=source_job,
                        profile=selected_profile,
                        report_ref=report_ref,
                        report=report,
                        receipt_ref=projection.receipt_ref,
                        observation_id=selected_observation.observation.observation_id,
                        source_port=source_port,
                        methodology_ref=expected_methodology_ref,
                    )
        except BaseException:
            resources.close()
            raise
        if not retained_sequence:
            resources.close()
        registry_path = active.authority.registry_path
        registry_bytes = registry_path.read_bytes()
        registry = active.authority._load_registry()
        assert entry in registry.entries and unrelated_entry in registry.entries
        renamed = build_authority_entry(
            **{
                **unrelated_entry.identity_payload(),
                "title": unrelated_entry.title + " (corrected title)",
            }
        )
        updated = build_authority_registry(
            baseline_content_sha256=registry.baseline_content_sha256,
            l5_measurement_registry_sha256=registry.l5_measurement_registry_sha256,
            entries=tuple(
                renamed if item == unrelated_entry else item for item in registry.entries
            ),
        )
        assert updated.content_sha256 != registry.content_sha256
        ((job, profile),) = seeds
        run_id = job.run_id
        assert run_id is not None
        core_run_id = job.progress["core_run_id"]
        compiled_ref = ArtifactRef.model_validate(
            job.progress["compiled_recursive_generation_cycle_artifact_ref"]
        )
        compiled = CompiledRecursiveGenerationCycleRun.model_validate(
            read_core_json_artifact(store, compiled_ref).value
        )
        (node,) = compiled.recursive_run.leaf_nodes
        assert node.cycle_run is not None
        (cycle,) = node.cycle_run.cycles
        execution_ref = cycle.simulation.generic_n5_execution_ref
        report_ref = cycle.model_input_routing_report_ref
        assert execution_ref is not None and report_ref is not None
        original = parse_generic_cycle_simulation_n5_execution(
            read_core_json_artifact(store, execution_ref).value
        )
        assert type(original) is GenericCycleSimulationN5ExecutionV4
        assert original.status == "simulation_blocked" and original.result_ref is None
        _, (obligation,) = load_model_input_obligation_set(
            store, original.model_input_obligation_set_ref
        )
        assert obligation.port == port and obligation.dependencies[0].first_required_step == 2
        assert port.semantic_definition_ref is not None
        definition = validate_core_model_json_artifact(
            VariableSemanticDefinition, store, port.semantic_definition_ref
        )
        if fund == "transport-maintenance-reserve":
            assert definition.namespace == "test.transport-maintenance-reserve"
            assert definition.stable_id == "opening-cash"
            assert port.binding_profile_ref == _opening_stock_port(store).binding_profile_ref
            assert entry.target_variable == "test.transport-maintenance-reserve.opening-cash"
            assert entry.raw_field == "opening_cash_usd"
        report = read_model_input_routing_report(store, report_ref)
        (route,) = report.routes
        descriptor = route.source_descriptor
        assert route.disposition == "resolved" and descriptor is not None
        assert descriptor.authority_entry_id == entry.entry_id
        assert descriptor.source_semantic_definition_ref == port.semantic_definition_ref
        assert selected_observation.observation.value == _OPENING_CASH

        mutation = ModelInputSuccessorActionRequest(
            compiled_ref=compiled_ref,
            blocked_execution_ref=execution_ref,
            routing_report_ref=report_ref,
            activation_receipt_ref=projection.receipt_ref,
            observation_id=selected_observation.observation.observation_id,
            idempotency_key=f"held-out-{fund}-opening-cash-use",
        )
        path = f"/api/v1/runs/{run_id}/model-input-use"

        with trust.authorization_exchange("acquisition-operator") as operator_authorization:
            with TestClient(app(root, profile)) as client:
                control = client.app.state.runtime_container.control_service
                stop_embedded_control_worker(control)
                ref = mutation.activation_receipt_ref
                manifest = store.get_manifest(ref)
                sibling = store.put_bytes(
                    store.get_bytes(ref),
                    PutOptions(
                        kind=manifest.kind,
                        media_type=manifest.media_type,
                        schema=manifest.artifact_schema,
                        canon=manifest.canon,
                        producer=manifest.producer,
                        inputs=manifest.inputs,
                        governance=manifest.governance,
                        tenant_context=manifest.tenant_context,
                        warnings=[
                            WarningRecord(code="test.foreign_activation", msg="Same receipt bytes")
                        ],
                    ),
                    return_selected_profile=True,
                )
                assert (
                    sibling.artifact_id == ref.artifact_id
                    and sibling.manifest_profile_sha256 != ref.manifest_profile_sha256
                )
                assert load_verified_epoch_statement(
                    store=store, ref=sibling, expected_kind=ref.kind
                ) == load_verified_epoch_statement(store=store, ref=ref, expected_kind=ref.kind)
                foreign, _ = trust.post(
                    client,
                    path + "/decision-request",
                    mutation.model_copy(update={"activation_receipt_ref": sibling}).model_dump(
                        mode="json"
                    ),
                    route=_ROUTE_TEMPLATE + "/decision-request",
                )
                assert foreign.status_code == 409, foreign.text
                assert foreign.json()["code"] == "active_epoch_receipt_binding_mismatch"
                blob, _ = store._paths(ref.artifact_id)
                withheld = tmp_path / "withheld-activation"
                blob.rename(withheld)
                try:
                    missing, _ = trust.post(
                        client,
                        path + "/decision-request",
                        mutation.model_dump(mode="json"),
                        route=_ROUTE_TEMPLATE + "/decision-request",
                    )
                    assert missing.status_code == 409, missing.text
                    assert missing.json()["code"] == "model_input_use_source_not_established"
                finally:
                    withheld.rename(blob)
                initial, digest = trust.post(
                    client,
                    path + "/decision-request",
                    mutation.model_dump(mode="json"),
                    route=_ROUTE_TEMPLATE + "/decision-request",
                )
                assert initial.status_code == 200, initial.text
                assert initial.json()["outcome"] == "decision_required"
                action_job_id = initial.json()["job_id"]
                route_id = initial.json()["route_id"]
                denied, _ = trust.post(
                    client,
                    path + "/execute",
                    {
                        "request": mutation.model_dump(mode="json"),
                        "decision_ref": initial.json()["authority_decision_ref"],
                    },
                    route=_ROUTE_TEMPLATE + "/execute",
                )
                assert denied.status_code == 409, denied.text
                assert denied.json()["code"] == "model_input_use_live_authority_not_established"
                assert control._control_store.get_job(action_job_id) is None
                assert not control.llm_producer_settlement_store._ledger.snapshot().invocation_reservations
                slot = _sign_model_input_mandate(
                    control,
                    trust=trust,
                    key_root=tmp_path,
                    signers=signers,
                    identities=identities,
                    run_id=run_id,
                    job_id=action_job_id,
                    route_id=route_id,
                    digest=digest,
                )

            with TestClient(app(root, profile)) as client:
                control = client.app.state.runtime_container.control_service
                stop_embedded_control_worker(control)
                _approve_candidate_action(
                    client=client,
                    control=control,
                    closure=SimpleNamespace(
                        tenant_id=served.TENANT, cell_id=served.CELL, run_id=run_id
                    ),
                    path=path,
                    template=_ROUTE_TEMPLATE,
                    mutation=mutation,
                    job_id=action_job_id,
                    slot=slot,
                    cas_root=cas_root,
                    trust=trust,
                    signers=signers,
                    identities=identities,
                )

            with TestClient(app(root, profile)) as client:
                control = client.app.state.runtime_container.control_service
                stop_embedded_control_worker(control)
                allowed, same_digest = trust.post(
                    client,
                    path + "/decision-request",
                    mutation.model_dump(mode="json"),
                    route=_ROUTE_TEMPLATE + "/decision-request",
                )
                assert allowed.status_code == 200 and same_digest == digest, allowed.text
                assert allowed.json()["outcome"] == "decision_available", allowed.text
                execution_body = {
                    "request": mutation.model_dump(mode="json"),
                    "decision_ref": allowed.json()["authority_decision_ref"],
                }
                no_step_up = client.post(
                    path + "/execute",
                    json=execution_body,
                    headers={
                        "Authorization": operator_authorization,
                        "X-Tenant-ID": served.TENANT,
                    },
                )
                assert no_step_up.status_code == 403, no_step_up.text
                assert no_step_up.json()["code"] == "step_up_required"
                assert control._control_store.get_job(action_job_id) is None
                assert not control.llm_producer_settlement_store._ledger.snapshot().invocation_reservations
                execute, _ = trust.post(
                    client,
                    path + "/execute",
                    execution_body,
                    route=_ROUTE_TEMPLATE + "/execute",
                )
                assert execute.status_code == 200, execute.text
                assert execute.json()["job_id"] == action_job_id
                final_fence_controls = {"exercised": False}
                verify_selected_routing_use_decision = (
                    successor_action_owner._verify_selected_routing_use_decision_current
                )

                def verify_with_pre_n5_controls(
                    selected_store: FileSystemCAS,
                    selected_action: Any,
                    selected_record: Any,
                ) -> None:
                    verify_selected_routing_use_decision(
                        selected_store, selected_action, selected_record
                    )
                    if final_fence_controls["exercised"]:
                        return
                    assert selected_record.routing_use_decision_ref is not None
                    persisted_job = control._control_store.get_job(action_job_id)
                    assert persisted_job is not None and persisted_job.state == "running"
                    persisted_checkpoint = ModelInputUseActionCheckpoint.model_validate(
                        persisted_job.progress["model_input_use"]
                    )
                    assert persisted_checkpoint.execution_ref is None
                    assert persisted_checkpoint.result_ref is None
                    _assert_routing_use_selection(
                        selected_store,
                        mutation=mutation,
                        checkpoint=persisted_checkpoint,
                        run_id=run_id,
                        source_job_id=job.job_id,
                        action_job_id=action_job_id,
                        expected_registry_sha256=registry.content_sha256,
                    )
                    ledger = control.llm_producer_settlement_store._ledger
                    reservations_before_controls = ledger.snapshot().invocation_reservations
                    progress_before_controls = persisted_job.progress
                    try:
                        registry_path.write_text(updated.model_dump_json(), encoding="utf-8")
                        with pytest.raises(
                            ValueError,
                            match="model_input_routing_use_decision_currentness_mismatch",
                        ):
                            verify_selected_routing_use_decision(
                                selected_store, selected_action, selected_record
                            )
                    finally:
                        registry_path.write_bytes(registry_bytes)

                    decision_blob, _ = selected_store._paths(
                        selected_record.routing_use_decision_ref.artifact_id
                    )
                    withheld_decision = tmp_path / "withheld-routing-use-decision"
                    decision_blob.rename(withheld_decision)
                    try:
                        with pytest.raises((FileNotFoundError, CanonicalProfileRefusalError)):
                            verify_selected_routing_use_decision(
                                selected_store, selected_action, selected_record
                            )
                    finally:
                        withheld_decision.rename(decision_blob)
                    assert ledger.snapshot().invocation_reservations == (
                        reservations_before_controls
                    )
                    assert control._control_store.get_job(action_job_id).progress == (
                        progress_before_controls
                    )
                    final_fence_controls["exercised"] = True

                def preflight_before_first_n5(
                    selected_control: Any, *, selected_action_job_id: str
                ) -> None:
                    from tests._helpers.candidate_experiment_served_execution import (
                        _dispatch_crash_probe_once,
                    )

                    preflight_owner_calls: list[tuple[Any, Any, Any, Any]] = []

                    def stop_at_real_n5_entry(port: Any, **run_kwargs: Any) -> Any:
                        assert type(port) is JointSimulationPort
                        assert set(run_kwargs) == {
                            "semantic_successor_ref",
                            "expected_blocked_execution_ref",
                            "expected_input_ref",
                            "currentness_resolver",
                        }
                        assert callable(run_kwargs["currentness_resolver"])
                        semantic_ref = run_kwargs["semantic_successor_ref"]
                        assert isinstance(semantic_ref, ArtifactRef)
                        selection = read_model_input_successor_selection(store, semantic_ref)
                        assert selection.authority_purpose == "candidate_simulation_input_only"
                        assert selection.action_job_id == selected_action_job_id
                        assert selection.source_job_id == job.job_id
                        assert selection.compiled_ref == compiled_ref
                        assert selection.blocked_execution_ref == execution_ref
                        assert selection.routing_report_ref == report_ref
                        assert selection.activation_receipt_ref == mutation.activation_receipt_ref
                        assert selection.observation_id == mutation.observation_id
                        leased_action = selected_control._control_store.get_job(
                            selected_action_job_id
                        )
                        assert leased_action is not None and leased_action.state == "running"
                        assert leased_action.lease_owner is not None
                        assert selection.action_attempt == leased_action.attempt == 1
                        assert selection.action_worker_id == leased_action.lease_owner

                        owner = port._generic_cycle_simulation_admission_owner
                        assert type(owner) is GenericCycleSimulationAdmissionOwner
                        prepared = owner.prepare_semantic_successor_request(
                            semantic_successor_ref=semantic_ref,
                            expected_blocked_execution_ref=run_kwargs[
                                "expected_blocked_execution_ref"
                            ],
                            expected_input_ref=run_kwargs["expected_input_ref"],
                        )
                        assert prepared.selection == selection
                        assert run_kwargs["expected_blocked_execution_ref"] == execution_ref
                        assert run_kwargs["expected_input_ref"] == original.input_ref
                        assert prepared.input_record.profile == profile
                        quota = prepared.input_record.n5.invocation_quota_policy
                        assert quota.total_units == 3 and quota.protected_units == 1
                        assert quota.work_unit == "n5_physical_invocation"
                        (plan,) = prepared.request.engine_plan
                        selected_bindings_ref = plan.program_semantic_input_bindings_ref
                        assert (
                            selected_bindings_ref == selection.semantic_foundry_input_bindings_ref
                        )
                        bindings = load_input_bindings(store, selected_bindings_ref)
                        manifest_ref = bindings.resolved_binding_manifest_ref
                        assert manifest_ref is not None
                        manifest = load_resolved_input_binding_manifest(store, manifest_ref)
                        assert len(manifest.measurements) == 1
                        (measurement,) = manifest.measurements
                        occurrence = validate_core_model_json_artifact(
                            ScopedMeasurementOccurrence,
                            store,
                            measurement.selected_occurrence_ref,
                        )
                        assert occurrence.observation_id == selection.observation_id
                        assert occurrence.source_receipt_ref == selection.activation_receipt_ref
                        assert float(occurrence.canonical_value) == _OPENING_CASH
                        assert occurrence.canonical_unit == "usd"
                        assert occurrence.country_code == "UKR" and occurrence.year == 2022
                        assert occurrence.source_scope.population_ref == "population:treasury"
                        assert occurrence.source_scope.geography_ref == "UA"
                        assert occurrence.source_scope.jurisdiction_ref == "UA"
                        assert occurrence.source_scope.period_basis == "calendar_year"
                        condition = json.loads(occurrence.condition_json)
                        assert condition["population_ref"] == "population:treasury"
                        assert condition["geography_ref"] == "UA"
                        assert condition["jurisdiction_ref"] == "UA"
                        assert condition["time_period_basis"] == "calendar_year"
                        reservations = selected_control.llm_producer_settlement_store._ledger.snapshot().invocation_reservations
                        assert not reservations
                        preflight_owner_calls.append((semantic_ref, selection, prepared, quota))
                        raise _InjectedN5PreflightStop("real selected request reached N5 entry")

                    run_semantic_successor = JointSimulationPort.run_semantic_successor
                    monkeypatch.setattr(
                        JointSimulationPort,
                        "run_semantic_successor",
                        stop_at_real_n5_entry,
                    )
                    try:
                        with pytest.raises(_InjectedN5PreflightStop):
                            _dispatch_crash_probe_once(
                                control=selected_control,
                                expected_job_id=selected_action_job_id,
                                lease_seconds=10,
                            )
                    finally:
                        monkeypatch.setattr(
                            JointSimulationPort,
                            "run_semantic_successor",
                            run_semantic_successor,
                        )
                    assert len(preflight_owner_calls) == 1
                    semantic_ref, _selection, _prepared, _quota = preflight_owner_calls[0]
                    pending_job = selected_control._control_store.get_job(selected_action_job_id)
                    assert pending_job is not None and pending_job.state == "running"
                    assert pending_job.attempt == 1
                    assert pending_job.lease_expires_at is not None
                    pending = ModelInputUseActionCheckpoint.model_validate(
                        pending_job.progress["model_input_use"]
                    )
                    assert pending.semantic_successor_ref == semantic_ref
                    assert pending.execution_ref is None and pending.result_ref is None
                    assert pending.evaluation_decision_ref is None
                    assert pending.evaluation_expected_frontier_revision == 0
                    assert pending.evaluation_expected_frontier_ref is None
                    assert not (
                        selected_control.llm_producer_settlement_store._ledger.snapshot().invocation_reservations
                    )

                monkeypatch.setattr(
                    successor_action_owner,
                    "_verify_selected_routing_use_decision_current",
                    verify_with_pre_n5_controls,
                )
                initial_crash: dict[str, Any] | None = None
                try:
                    if preflight_first_n5:
                        preflight_before_first_n5(
                            control,
                            selected_action_job_id=action_job_id,
                        )
                    elif retained_sequence:
                        initial_crash = crash_after_durable_n5_persist(
                            control,
                            action_job_id=action_job_id,
                            evaluation_decision_present=False,
                        )
                    else:
                        assert (
                            dispatch_one_control_job(
                                store=control._control_store,
                                handler=control._process_control_job,
                                expected_job_id=action_job_id,
                            )
                            == action_job_id
                        )
                finally:
                    registry_path.write_bytes(registry_bytes)
                assert final_fence_controls["exercised"]
                if preflight_first_n5:
                    return
                if initial_crash is not None:
                    action, checkpoint = recover_durable_n5_crash(initial_crash)
                else:
                    action = control._control_store.get_job(action_job_id)
                    assert action is not None and action.state == "completed", (
                        None if action is None else action.error_message
                    )
                    checkpoint = ModelInputUseActionCheckpoint.model_validate(
                        action.progress["model_input_use"]
                    )
                assert action is not None and action.state == "completed", (
                    None if action is None else action.error_message
                )
                _assert_routing_use_selection(
                    store,
                    mutation=mutation,
                    checkpoint=checkpoint,
                    run_id=run_id,
                    source_job_id=job.job_id,
                    action_job_id=action_job_id,
                    expected_registry_sha256=registry.content_sha256,
                )
                assert (
                    len(
                        control.llm_producer_settlement_store._ledger.snapshot().invocation_reservations
                    )
                    == 1
                )

        fresh = FileSystemCAS(cas_root).for_tenant(served.TENANT, served.CELL)
        with TestClient(app(root)) as reader:
            stop_embedded_control_worker(reader.app.state.runtime_container.control_service)
            headers = {
                "Authorization": trust.authorization_header("acquisition-operator"),
                "X-Tenant-ID": served.TENANT,
            }
            original_get = reader.get(f"/api/v1/runs/{core_run_id}", headers=headers)
            assert original_get.status_code == 200, original_get.text
            (row,) = original_get.json()["run"]["generic_cycle_simulation"]["n5_observations"]
            assert (
                row["status"] == "simulation_blocked" and row.get("simulation_result_ref") is None
            )
            assert row["n5_owner_join_status"] == "resolved"
            assert (
                ArtifactRef.model_validate(row["model_input_routing"]["report_ref"]) == report_ref
            )
            result_path = path + f"/{action_job_id}/n5-result"
            successor = reader.get(result_path, headers=headers)
            assert successor.status_code == 200, successor.text
            selected = RunModelInputUseN5SuccessorResponse.model_validate(successor.json()).result
            assert selected.action_status == "completed", selected.limitation_code
            assert selected.result_status == "resolved", selected.limitation_code
            assert selected.action_job_id == action_job_id
            selected_semantic_ref, selected_execution_ref, selected_result_ref = (
                _n5_projection_refs(selected)
            )
            assert selected_semantic_ref == checkpoint.semantic_successor_ref
            assert selected_execution_ref == checkpoint.execution_ref
            assert selected_result_ref == checkpoint.result_ref
            assert selected_result_ref is not None
            if isinstance(selected, RunModelInputUseN5SuccessorProjectionV2):
                assert selected.original_action_job_id == action_job_id
            assert selected.authority_purpose == "cycle_input_candidate_only"
            expected_limitation_codes = (
                (
                    "external_empirical_origin_not_established",
                    "optional_axis_unknown:methodology_ref",
                    "source_currentness_not_established",
                )
                if expected_methodology_ref is not None
                else (
                    "external_empirical_origin_not_established",
                    "source_currentness_not_established",
                )
            )
            assert selected.semantic_input_limitation_codes == expected_limitation_codes
            assert (
                selected.currentness_status == "not_established"
                and not selected.publication_authority
            )
            blocked = selected.blocked_source
            assert blocked is not None and blocked.status == "simulation_blocked"
            assert blocked.source_job_id == job.job_id
            assert (
                blocked.blocked_execution_ref == execution_ref
                and blocked.routing_report_ref == report_ref
            )
            assert blocked.model_input_obligation_set_ref == original.model_input_obligation_set_ref
            assert selected.result_body is not None
            for trajectory in selected.result_body.trajectories:
                assert (
                    tuple(point.outcomes[_OUTCOME] for point in trajectory.points)
                    == _EXPECTED_BALANCES
                )
            if expected_methodology_ref is not None:
                assert checkpoint.result_ref is not None
                result_content = reader.get(
                    "/api/v1/artifacts/"
                    f"{selected_result_ref.artifact_id}/content"
                    f"?manifest_profile_sha256={selected_result_ref.manifest_profile_sha256}",
                    headers={**headers, "Accept": "application/octet-stream"},
                )
                assert result_content.status_code == 403, result_content.text
                assert result_content.json()["code"] == "artifact_tenant_unscoped"
            reader_control = reader.app.state.runtime_container.control_service
            reservations_before_binding_controls = reader_control.llm_producer_settlement_store._ledger.snapshot().invocation_reservations
            action_before_binding_controls = reader_control._control_store.get_job(action_job_id)
            assert action_before_binding_controls is not None
            _assert_foundry_successor(
                fresh,
                original=original,
                mutation=mutation,
                action_job_id=action_job_id,
                checkpoint=checkpoint,
                expected_methodology_ref=expected_methodology_ref,
            )
            _assert_semantic_input_selection_refusals(
                fresh,
                semantic_successor_ref=checkpoint.semantic_successor_ref,
                blocked_execution_ref=execution_ref,
                input_ref=original.input_ref,
            )
            assert (
                reader_control.llm_producer_settlement_store._ledger.snapshot().invocation_reservations
                == reservations_before_binding_controls
            )
            assert reader_control._control_store.get_job(action_job_id) == (
                action_before_binding_controls
            )
            assert checkpoint.result_ref is not None
            blob, _ = fresh._paths(checkpoint.result_ref.artifact_id)
            withheld = tmp_path / "withheld-successor-result"
            blob.rename(withheld)
            try:
                removed = reader.get(result_path, headers=headers)
                assert removed.status_code == 200, removed.text
                limited = RunModelInputUseN5SuccessorResponse.model_validate(removed.json()).result
                assert limited.action_status == "completed"
                assert limited.result_status == "not_established"
                assert limited.blocked_source == blocked
                _, limited_execution_ref, limited_result_ref = _n5_projection_refs(limited)
                assert limited_execution_ref is None and limited_result_ref is None
                assert limited.result_body is None
            finally:
                withheld.rename(blob)

        if retained_sequence:
            target_representation = load_variable_representation(
                store, source_port.representation_ref
            )
            assert target_representation.quantity_kind == "stock"
            assert target_representation.measure_form == "absolute"
            assert target_representation.unit_id == "usd"
            assert target_representation.time_support == "state_start"
            assert target_representation.temporal_granularity == "annual"
            assert target_representation.population_ref == "population:treasury"
            assert port.scope.population_ref == "population:treasury"
            assert port.scope.geography_ref == "UA"
            assert port.scope.jurisdiction_ref == "UA"
            assert port.scope.period_basis == "calendar_year"
            live_history = active.live_history
            assert live_history.transport_calls == 1
            assert active.evidence.call_count == 1
            first_raw_artifact_id = active.evidence.raw_artifact_id
            first_normalized_content_sha256 = active.evidence.normalized_result_content_sha256
            first_execution_ref = checkpoint.execution_ref
            first_result_ref = checkpoint.result_ref
            assert first_execution_ref is not None and first_result_ref is not None

            def execute_current_measurement(
                value: float,
                *,
                sequence_key: str,
                current_occurrence: Any | None = None,
                crash_after_persist: bool = False,
            ) -> tuple[ModelInputSuccessorActionRequest, Any, ModelInputUseActionCheckpoint, Any]:
                current = (
                    live_history.admit(value) if current_occurrence is None else current_occurrence
                )
                assert live_history.transport_calls == len(live_history.used_attempts)
                assert current.evidence.call_count == 1
                assert current.passport.source_lane == "live_fetch"
                assert current.passport.authority_entry_id == entry.entry_id
                source_entry = current.passport.source_authority_entry
                assert source_entry is not None and source_entry.source_measure_scope is not None
                assert source_entry.source_semantic_definition_ref == (
                    source_port.semantic_definition_ref
                )
                assert source_entry.source_representation_ref == source_port.representation_ref
                source_scope = source_entry.source_measure_scope
                assert source_scope.population == "population:treasury"
                assert source_scope.source_geography_id == "UA"
                assert source_scope.geography_ref == "UA"
                assert source_scope.jurisdiction_ref == "UA"
                assert source_scope.time_period_basis == "calendar_year"
                assert current.passport.field_binding.canonical_unit == "usd"
                (current_entry,) = current.entries
                assert current_entry.entry_id == entry.entry_id
                current_projection = current.projections[current_entry.target_variable]
                (current_observation,) = current_projection.observations
                assert current_observation.observation.value == value
                assert current_observation.observation.country_code == "UKR"
                assert current_observation.observation.year == 2022
                condition = json.loads(current_observation.observation.condition_json)
                assert condition["population_ref"] == "population:treasury"
                assert condition["geography_ref"] == "UA"
                assert condition["jurisdiction_ref"] == "UA"
                assert condition["time_period_basis"] == "calendar_year"
                raw_ref = current.evidence.raw_artifact_ref
                assert raw_ref is not None
                raw_payload = json.loads(store.get_bytes(raw_ref))
                assert isinstance(raw_payload, list) and len(raw_payload) == 2
                raw_rows = raw_payload[1]
                assert isinstance(raw_rows, list) and len(raw_rows) == 1
                (raw_row,) = raw_rows
                assert raw_row["countryiso3code"] == "UKR"
                assert raw_row["country"]["id"] == "UA"
                assert raw_row["indicator"]["id"] == "TEST.OPENING.CASH.USD"
                assert raw_row["value"] == value
                assert current_projection.receipt_ref != projection.receipt_ref
                assert current_projection.passport_ref != projection.passport_ref
                assert (
                    current_observation.observation.observation_id
                    != selected_observation.observation.observation_id
                )
                request = ModelInputSuccessorActionRequest(
                    compiled_ref=compiled_ref,
                    blocked_execution_ref=execution_ref,
                    routing_report_ref=report_ref,
                    activation_receipt_ref=current_projection.receipt_ref,
                    observation_id=current_observation.observation.observation_id,
                    idempotency_key=f"held-out-treasury-{sequence_key}-opening-cash-use",
                )
                action_path = f"/api/v1/runs/{run_id}/model-input-use"
                closure = SimpleNamespace(
                    tenant_id=served.TENANT,
                    cell_id=served.CELL,
                    run_id=run_id,
                )
                reservations_before_current: tuple[Any, ...] | None = None
                with trust.authorization_exchange(
                    "acquisition-operator"
                ) as sequence_operator_authorization:
                    with TestClient(app(root, profile)) as decision_client:
                        sequence_control = (
                            decision_client.app.state.runtime_container.control_service
                        )
                        stop_embedded_control_worker(sequence_control)
                        reservations_before_current = sequence_control.llm_producer_settlement_store._ledger.snapshot().invocation_reservations
                        initial_response, sequence_digest = trust.post(
                            decision_client,
                            action_path + "/decision-request",
                            request.model_dump(mode="json"),
                            route=_ROUTE_TEMPLATE + "/decision-request",
                        )
                        assert initial_response.status_code == 200, initial_response.text
                        assert initial_response.json()["outcome"] == "decision_required"
                        sequence_job_id = initial_response.json()["job_id"]
                        sequence_route_id = initial_response.json()["route_id"]
                        slot = _sign_model_input_mandate(
                            sequence_control,
                            trust=trust,
                            key_root=tmp_path,
                            signers=signers,
                            identities=identities,
                            run_id=run_id,
                            job_id=sequence_job_id,
                            route_id=sequence_route_id,
                            digest=sequence_digest,
                        )

                    with TestClient(app(root, profile)) as approval_client:
                        sequence_control = (
                            approval_client.app.state.runtime_container.control_service
                        )
                        stop_embedded_control_worker(sequence_control)
                        _approve_candidate_action(
                            client=approval_client,
                            control=sequence_control,
                            closure=closure,
                            path=action_path,
                            template=_ROUTE_TEMPLATE,
                            mutation=request,
                            job_id=sequence_job_id,
                            slot=slot,
                            cas_root=cas_root,
                            trust=trust,
                            signers=signers,
                            identities=identities,
                        )

                    with TestClient(app(root, profile)) as execute_client:
                        sequence_control = (
                            execute_client.app.state.runtime_container.control_service
                        )
                        stop_embedded_control_worker(sequence_control)
                        approved, approved_digest = trust.post(
                            execute_client,
                            action_path + "/decision-request",
                            request.model_dump(mode="json"),
                            route=_ROUTE_TEMPLATE + "/decision-request",
                        )
                        assert approved.status_code == 200, approved.text
                        assert approved_digest == sequence_digest
                        assert approved.json()["outcome"] == "decision_available"
                        execute_body = {
                            "request": request.model_dump(mode="json"),
                            "decision_ref": approved.json()["authority_decision_ref"],
                        }
                        missing_step_up = execute_client.post(
                            action_path + "/execute",
                            json=execute_body,
                            headers={
                                "Authorization": sequence_operator_authorization,
                                "X-Tenant-ID": served.TENANT,
                            },
                        )
                        assert missing_step_up.status_code == 403, missing_step_up.text
                        assert missing_step_up.json()["code"] == "step_up_required"
                        assert sequence_control._control_store.get_job(sequence_job_id) is None
                        execute_response, _ = trust.post(
                            execute_client,
                            action_path + "/execute",
                            execute_body,
                            route=_ROUTE_TEMPLATE + "/execute",
                        )
                        assert execute_response.status_code == 200, execute_response.text
                        assert execute_response.json()["job_id"] == sequence_job_id
                        crash: dict[str, Any] | None = None
                        if crash_after_persist:
                            crash = crash_after_durable_n5_persist(
                                sequence_control,
                                action_job_id=sequence_job_id,
                                evaluation_decision_present=True,
                            )
                        else:
                            assert (
                                dispatch_one_control_job(
                                    store=sequence_control._control_store,
                                    handler=sequence_control._process_control_job,
                                    expected_job_id=sequence_job_id,
                                )
                                == sequence_job_id
                            )
                        if crash is not None:
                            current_job, current_checkpoint = recover_durable_n5_crash(crash)
                        else:
                            current_job = sequence_control._control_store.get_job(sequence_job_id)
                            current_checkpoint = (
                                None
                                if current_job is None
                                else ModelInputUseActionCheckpoint.model_validate(
                                    current_job.progress["model_input_use"]
                                )
                            )
                        assert current_job is not None and current_job.state == "completed", (
                            None if current_job is None else current_job.error_message
                        )
                        assert current_checkpoint is not None
                        if crash is None:
                            assert reservations_before_current is not None
                            assert (
                                sequence_control.llm_producer_settlement_store._ledger.snapshot().invocation_reservations
                                == reservations_before_current
                            )
                        _assert_routing_use_selection(
                            store,
                            mutation=request,
                            checkpoint=current_checkpoint,
                            run_id=run_id,
                            source_job_id=job.job_id,
                            action_job_id=sequence_job_id,
                            expected_registry_sha256=registry.content_sha256,
                        )

                with TestClient(app(root)) as sequence_reader:
                    stop_embedded_control_worker(
                        sequence_reader.app.state.runtime_container.control_service
                    )
                    current_response = sequence_reader.get(
                        action_path + f"/{sequence_job_id}/n5-result",
                        headers={
                            "Authorization": trust.authorization_header("acquisition-operator"),
                            "X-Tenant-ID": served.TENANT,
                        },
                    )
                    assert current_response.status_code == 200, current_response.text
                    current_result = RunModelInputUseN5SuccessorResponse.model_validate(
                        current_response.json()
                    ).result
                assert isinstance(current_result, RunModelInputUseN5SuccessorProjectionV2)
                assert current_result.action_status == "completed"
                assert current_result.result_status == "resolved"
                assert current_result.current_semantic_successor_ref == (
                    current_checkpoint.semantic_successor_ref
                )
                assert current_result.current_use_decision_ref is not None
                assert current_result.current_basis_ref is not None
                assert current_result.selected_basis_ref is not None
                assert current_result.result_body is not None
                assert current_result.authority_purpose == "cycle_input_candidate_only"
                assert current_result.currentness_status == "not_established"
                assert not current_result.publication_authority
                assert not current_result.observed_admission
                assert "external_empirical_origin_not_established" in (
                    current_result.semantic_input_limitation_codes
                )
                return request, current, current_checkpoint, current_result

            equal_request, equal_current, equal_checkpoint, equal_result = (
                execute_current_measurement(_OPENING_CASH, sequence_key="same-value-b1")
            )
            assert equal_current.evidence.raw_artifact_id == first_raw_artifact_id
            assert (
                equal_current.evidence.normalized_result_content_sha256
                == first_normalized_content_sha256
            )
            assert equal_checkpoint.execution_ref is None
            assert equal_checkpoint.result_ref is None
            assert equal_checkpoint.evaluation_decision_ref is not None
            assert equal_result.basis_comparison_result == "equivalent"
            assert equal_result.predicate_provenance == "recomputed"
            assert equal_result.evaluation_provenance == "retained_prior"
            assert equal_result.original_action_job_id == action_job_id
            assert equal_result.original_semantic_successor_ref == selected_semantic_ref
            assert equal_result.original_execution_ref == first_execution_ref
            assert equal_result.original_result_ref == first_result_ref
            assert equal_result.current_semantic_successor_ref != selected_semantic_ref
            assert equal_result.frontier_selection == "selected"
            assert equal_result.result_body is not None
            for trajectory in equal_result.result_body.trajectories:
                assert tuple(point.outcomes[_OUTCOME] for point in trajectory.points) == (
                    _EXPECTED_BALANCES
                )
            assert live_history.transport_calls == 2

            prior_frontier_ref = equal_result.frontier_ref
            prior_frontier_revision = equal_result.frontier_revision
            seen_action_jobs = {action_job_id, equal_result.action_job_id}
            seen_authority_decisions = {equal_result.current_authority_decision_ref}
            seen_use_decisions = {equal_result.current_use_decision_ref}
            seen_semantic_successors = {equal_result.current_semantic_successor_ref}
            for sequence_key in ("same-value-b2", "same-value-b3"):
                reused_request, reused_current, reused_checkpoint, reused_result = (
                    execute_current_measurement(
                        _OPENING_CASH,
                        sequence_key=sequence_key,
                        current_occurrence=equal_current,
                    )
                )
                assert reused_current is equal_current
                assert reused_request.activation_receipt_ref == equal_request.activation_receipt_ref
                assert reused_request.observation_id == equal_request.observation_id
                assert reused_checkpoint.execution_ref is None
                assert reused_checkpoint.result_ref is None
                assert reused_checkpoint.evaluation_decision_ref is not None
                assert reused_checkpoint.evaluation_current_basis_ref is not None
                assert reused_result.basis_comparison_result == "equivalent"
                assert reused_result.predicate_provenance == "recomputed"
                assert reused_result.evaluation_provenance == "retained_prior"
                assert reused_result.original_action_job_id == action_job_id
                assert reused_result.original_semantic_successor_ref == selected_semantic_ref
                assert reused_result.original_execution_ref == first_execution_ref
                assert reused_result.original_result_ref == first_result_ref
                assert reused_result.frontier_ref == prior_frontier_ref
                assert reused_result.frontier_revision == prior_frontier_revision
                assert reused_result.frontier_selection == "selected"
                assert reused_result.action_job_id not in seen_action_jobs
                assert reused_result.current_authority_decision_ref not in seen_authority_decisions
                assert reused_result.current_use_decision_ref not in seen_use_decisions
                assert reused_result.current_semantic_successor_ref not in seen_semantic_successors
                seen_action_jobs.add(reused_result.action_job_id)
                seen_authority_decisions.add(reused_result.current_authority_decision_ref)
                seen_use_decisions.add(reused_result.current_use_decision_ref)
                seen_semantic_successors.add(reused_result.current_semantic_successor_ref)
                assert reused_result.result_body is not None
                for trajectory in reused_result.result_body.trajectories:
                    assert tuple(point.outcomes[_OUTCOME] for point in trajectory.points) == (
                        _EXPECTED_BALANCES
                    )
                assert live_history.transport_calls == 2

            changed_value = 602.5
            changed_balances = (changed_value, changed_value, changed_value - (100 + 200) / 8)
            changed_request, changed_current, changed_checkpoint, changed_result = (
                execute_current_measurement(
                    changed_value,
                    sequence_key="changed-c",
                    crash_after_persist=True,
                )
            )
            assert changed_current.evidence.raw_artifact_id != first_raw_artifact_id
            assert (
                changed_current.evidence.normalized_result_content_sha256
                != first_normalized_content_sha256
            )
            equal_projection = equal_current.projections[entry.target_variable]
            changed_projection = changed_current.projections[entry.target_variable]
            (equal_observation,) = equal_projection.observations
            (changed_observation,) = changed_projection.observations
            assert changed_projection.receipt_ref != equal_projection.receipt_ref
            assert changed_projection.passport_ref != equal_projection.passport_ref
            assert changed_observation.observation.observation_id != (
                equal_observation.observation.observation_id
            )
            assert changed_checkpoint.execution_ref is not None
            assert changed_checkpoint.execution_ref != first_execution_ref
            assert changed_checkpoint.result_ref is not None
            assert changed_checkpoint.result_ref != first_result_ref
            assert changed_result.basis_comparison_result == "different"
            assert changed_result.predicate_provenance == "recomputed"
            assert changed_result.evaluation_provenance == "new_execution"
            assert changed_result.original_action_job_id == changed_result.action_job_id
            assert changed_result.original_semantic_successor_ref == (
                changed_result.current_semantic_successor_ref
            )
            assert changed_result.original_execution_ref == changed_checkpoint.execution_ref
            assert changed_result.original_result_ref == changed_checkpoint.result_ref
            assert changed_result.frontier_selection == "selected"
            assert changed_result.result_body is not None
            for trajectory in changed_result.result_body.trajectories:
                assert tuple(point.outcomes[_OUTCOME] for point in trajectory.points) == (
                    changed_balances
                )
            _assert_foundry_successor(
                store,
                original=original,
                mutation=changed_request,
                action_job_id=changed_result.action_job_id,
                checkpoint=changed_checkpoint,
                expected_balances=changed_balances,
            )
            with TestClient(app(root)) as post_change_reader:
                post_change_control = post_change_reader.app.state.runtime_container.control_service
                stop_embedded_control_worker(post_change_control)
                quota_snapshot = post_change_control.llm_producer_settlement_store.snapshot_safe()
                quota_profile = quota_snapshot.invocation_profiles[run_id]
                assert quota_profile.total_units == 3
                assert quota_profile.protected_units == 1
                reservations = tuple(
                    row
                    for row in quota_snapshot.invocation_reservations.values()
                    if row.run_id == run_id and row.profile_digest == quota_profile.profile_digest
                )
                assert len(reservations) == 2
                assert all(
                    row.purpose == "standard" and row.status == "completed" and row.units == 1
                    for row in reservations
                )
                reservations_before_historical_read = (
                    post_change_control.llm_producer_settlement_store._ledger.snapshot()
                )
                historical_response = post_change_reader.get(
                    path + f"/{equal_result.action_job_id}/n5-result",
                    headers={
                        "Authorization": trust.authorization_header("acquisition-operator"),
                        "X-Tenant-ID": served.TENANT,
                    },
                )
                assert historical_response.status_code == 200, historical_response.text
                historical_b = RunModelInputUseN5SuccessorResponse.model_validate(
                    historical_response.json()
                ).result
                assert isinstance(historical_b, RunModelInputUseN5SuccessorProjectionV2)
                assert historical_b.action_status == "completed"
                assert historical_b.result_status == "resolved"
                assert historical_b.action_job_id == equal_result.action_job_id
                assert historical_b.current_semantic_successor_ref == (
                    equal_result.current_semantic_successor_ref
                )
                assert historical_b.frontier_selection == "superseded"
                assert historical_b.basis_comparison_result == "equivalent"
                assert historical_b.evaluation_provenance == "retained_prior"
                assert historical_b.original_action_job_id == action_job_id
                assert historical_b.original_semantic_successor_ref == selected_semantic_ref
                assert historical_b.original_execution_ref == first_execution_ref
                assert historical_b.original_result_ref == first_result_ref
                assert historical_b.result_body == equal_result.result_body
                assert historical_b.result_body is not None
                for trajectory in historical_b.result_body.trajectories:
                    assert tuple(point.outcomes[_OUTCOME] for point in trajectory.points) == (
                        _EXPECTED_BALANCES
                    )
                assert historical_b.currentness_status == "not_established"
                assert not historical_b.publication_authority
                assert not historical_b.observed_admission
                assert (
                    post_change_control.llm_producer_settlement_store._ledger.snapshot()
                    == reservations_before_historical_read
                )
            assert live_history.transport_calls == 3
            assert live_history.used_attempts == [
                "held-out-stock-a-initial",
                "held-out-stock-b-equal",
                "held-out-stock-c-changed",
            ]
            return

        try:
            registry_path.write_text(updated.model_dump_json(), encoding="utf-8")
            with (
                trust.authorization_exchange("acquisition-operator"),
                TestClient(app(root, profile)) as current_reader,
            ):
                current_control = current_reader.app.state.runtime_container.control_service
                stop_embedded_control_worker(current_control)
                ledger = current_control.llm_producer_settlement_store._ledger
                reservations = ledger.snapshot().invocation_reservations
                assert len(reservations) == 1
                current_decision, current_digest = trust.post(
                    current_reader,
                    path + "/decision-request",
                    mutation.model_dump(mode="json"),
                    route=_ROUTE_TEMPLATE + "/decision-request",
                )
                if current_decision.status_code == 200:
                    # A cached response for the old job cannot satisfy a fresh
                    # current selection of the same activated observation.
                    with tenant_scope(None, tenant_id=served.TENANT, cell_id=served.CELL):
                        fresh_selection = resolve_model_input_successor_action(
                            current_control,
                            tenant_id=served.TENANT,
                            cell_id=served.CELL,
                            run_id=run_id,
                            request=mutation.model_copy(
                                update={"idempotency_key": "unrelated-metadata-fresh-use"}
                            ),
                        )
                    assert fresh_selection.route_id == route_id
                    assert fresh_selection.job_id != action_job_id
                    assert fresh_selection.passport_ref == projection.passport_ref
                    activation_blob, _ = fresh._paths(mutation.activation_receipt_ref.artifact_id)
                    withheld_activation = tmp_path / "withheld-activation-after-registry-update"
                    activation_blob.rename(withheld_activation)
                    try:
                        refused_missing, _ = trust.post(
                            current_reader,
                            path + "/decision-request",
                            mutation.model_copy(
                                update={
                                    "idempotency_key": "missing-activation-after-registry-update"
                                }
                            ).model_dump(mode="json"),
                            route=_ROUTE_TEMPLATE + "/decision-request",
                        )
                        assert refused_missing.status_code == 409, refused_missing.text
                        assert refused_missing.json()["code"] == (
                            "model_input_use_source_not_established"
                        )
                    finally:
                        withheld_activation.rename(activation_blob)
                    competitor = build_authority_entry(
                        **{**entry.identity_payload(), "title": entry.title + " (competing entry)"}
                    )
                    ambiguous = build_authority_registry(
                        baseline_content_sha256=updated.baseline_content_sha256,
                        l5_measurement_registry_sha256=updated.l5_measurement_registry_sha256,
                        entries=(*updated.entries, competitor),
                    )
                    registry_path.write_text(ambiguous.model_dump_json(), encoding="utf-8")
                    refused_competitor, _ = trust.post(
                        current_reader,
                        path + "/decision-request",
                        mutation.model_copy(
                            update={"idempotency_key": "competing-catalog-source"}
                        ).model_dump(mode="json"),
                        route=_ROUTE_TEMPLATE + "/decision-request",
                    )
                    assert refused_competitor.status_code == 409, refused_competitor.text
                    assert refused_competitor.json()["code"] == (
                        "model_input_use_source_not_established"
                    )
                assert ledger.snapshot().invocation_reservations == reservations
        finally:
            registry_path.write_bytes(registry_bytes)

        # Withdraw only the current source entry through the canonical registry
        # format. Keep the original activation, signed action and numerical
        # evidence available for historical replay.
        withdrawn = build_authority_registry(
            baseline_content_sha256=registry.baseline_content_sha256,
            l5_measurement_registry_sha256=registry.l5_measurement_registry_sha256,
            entries=tuple(item for item in registry.entries if item.entry_id != entry.entry_id),
        )
        try:
            registry_path.write_text(withdrawn.model_dump_json(), encoding="utf-8")
            with pytest.raises(AcquisitionAuthorityError, match="authority_entry_unresolved"):
                active.authority.resolve(entry.entry_id)

            with (
                trust.authorization_exchange("acquisition-operator") as operator_authorization,
                TestClient(app(root)) as historical_reader,
            ):
                historical_control = historical_reader.app.state.runtime_container.control_service
                stop_embedded_control_worker(historical_control)
                ledger = historical_control.llm_producer_settlement_store._ledger
                reservations = ledger.snapshot().invocation_reservations
                assert len(reservations) == 1
                new_use = mutation.model_copy(update={"idempotency_key": "withdrawn-stock-use"})
                refused, _ = trust.post(
                    historical_reader,
                    path + "/decision-request",
                    new_use.model_dump(mode="json"),
                    route=_ROUTE_TEMPLATE + "/decision-request",
                )
                assert refused.status_code == 409, refused.text
                assert refused.json()["code"] == "model_input_use_source_not_established"

                with tenant_scope(None, tenant_id=served.TENANT, cell_id=served.CELL):
                    _assert_foundry_successor(
                        fresh,
                        original=original,
                        mutation=mutation,
                        action_job_id=action_job_id,
                        checkpoint=checkpoint,
                        expected_methodology_ref=expected_methodology_ref,
                    )
                historical_headers = {
                    "Authorization": operator_authorization,
                    "X-Tenant-ID": served.TENANT,
                }
                historical = historical_reader.get(result_path, headers=historical_headers)
                assert ledger.snapshot().invocation_reservations == reservations
                assert historical.status_code == 200, historical.text
                replayed = RunModelInputUseN5SuccessorResponse.model_validate(historical.json())
                assert replayed.result == selected, historical.text

                decision_id = ArtifactID.model_validate(execution_body["decision_ref"])
                signature = fresh._sig_path(decision_id)
                withheld_signature = tmp_path / "withheld-successor-approval-signature"
                signature.rename(withheld_signature)
                try:
                    unsigned = historical_reader.get(result_path, headers=historical_headers)
                    assert unsigned.status_code == 200, unsigned.text
                    unverified = RunModelInputUseN5SuccessorResponse.model_validate(
                        unsigned.json()
                    ).result
                    assert unverified.action_status == "completed"
                    assert unverified.result_status == "not_established"
                    assert unverified.limitation_code == (
                        "model_input_use_history_approval_not_established"
                    )
                    assert unverified.simulation_result_ref is None
                    assert unverified.result_body is None
                finally:
                    withheld_signature.rename(signature)
        finally:
            registry_path.write_bytes(registry_bytes)

        assert current_decision.status_code == 200, current_decision.text
        assert current_digest == digest
        decision = current_decision.json()
        assert decision["outcome"] == "decision_required", current_decision.text
        assert decision["route_id"] == route_id
        assert decision["job_id"] == action_job_id
        assert decision["authority_decision_ref"] != execution_body["decision_ref"]


@pytest.mark.integration
def test_transport_reserve_metadata_only_stock_uses_served_successor_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: ControlledCandidateGateway,
) -> None:
    """A differently named transport stock reaches Foundry as a candidate input."""
    _run_activated_held_out_stock_scenario(
        tmp_path,
        monkeypatch,
        controlled_candidate_gateway,
        methodology_v2=False,
        fund="transport-maintenance-reserve",
    )


@pytest.mark.integration
@pytest.mark.parametrize("wrong_axis", [("quantity_kind",), ("denominator_ref",)])
def test_transport_reserve_catalog_rejects_same_label_wrong_stock_semantics(
    tmp_path: Path,
    wrong_axis: tuple[str],
) -> None:
    """The real Catalog binding validator rejects a mislabeled transport source."""
    from polisyos.runtime.quality.data_state_substrate import (
        DataStateSubstrateError,
    )
    from polisyos.runtime.quality.model_input_requirements import (
        SelectedProgramGraphInputBasis,
    )
    from polisyos.runtime.quality.model_input_routing import plan_selected_model_input_routing

    axis = wrong_axis[0]
    case = prepare_program_graph_tax_subsidy_input_case(
        tmp_path / "graph",
        opening_balance_usd=None,
        model_input_port_declaration_builder=_held_out_transport_reserve_declaration,
        snapshot_id="held-out-transport-reserve-adversarial",
    )
    try:
        interface_ref = _input_interface(case)
        assert case.model_input_port_declaration_ref is not None
        (target_port,) = load_model_input_port_declaration(
            case.store, case.model_input_port_declaration_ref
        ).ports
        preflight = _input_preflight(case, interface_ref, _input_context(case), steps=(0,))
        invocation = preflight.invocation
        selected = SelectedProgramGraphInputBasis(
            context=invocation.context,
            program_graph_ref=invocation.program_graph_ref,
            exec_plan_ref=invocation.exec_plan_ref,
            registry_bundle_ref=invocation.registry_bundle_ref,
            input_bindings_ref=invocation.input_bindings_ref,
            steps=(0,),
        )
        wrong_port = _misrepresented_transport_source_port(case.store, target_port, axis=axis)
        routes = []

        def route_source(authority: CanonicalAcquisitionAuthority) -> None:
            routes.append(
                plan_selected_model_input_routing(
                    case.store,
                    obligation_set_ref=preflight.obligation_set_ref,
                    selected_basis=selected,
                    catalog_authority=authority,
                )
            )

        with (
            _activated_fund(
                tmp_path / f"transport-reserve-{axis}",
                store=case.store,
                port=wrong_port,
                fund="transport-maintenance-reserve",
                before_activation=route_source,
            ) as active,
            pytest.raises(
                DataStateSubstrateError,
                match="acquisition_semantic_correspondence_not_candidate",
            ),
        ):
            _bind_activated_fund(
                case,
                active=active,
                routing=routes.pop(),
                preflight=preflight,
                source_port=wrong_port,
                workspace=tmp_path / f"refused-transport-{axis}",
            )
    finally:
        case.close()


@pytest.mark.integration
def test_activated_held_out_stock_executes_through_ordinary_signed_model_input_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: ControlledCandidateGateway,
) -> None:
    """Preserve the original v1 served stock scenario."""
    _run_activated_held_out_stock_scenario(
        tmp_path,
        monkeypatch,
        controlled_candidate_gateway,
        methodology_v2=False,
    )


@pytest.mark.integration
def test_equal_current_stock_retains_prior_result_then_changed_stock_executes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: ControlledCandidateGateway,
) -> None:
    """Fresh equal stock use retains A; changed stock gets a physical N5 run."""
    _run_activated_held_out_stock_scenario(
        tmp_path,
        monkeypatch,
        controlled_candidate_gateway,
        methodology_v2=False,
        fund="treasury",
        retained_sequence=True,
    )


@pytest.mark.integration
def test_activated_treasury_stock_preflight_reaches_real_n5_without_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: ControlledCandidateGateway,
) -> None:
    """Check selected stock binding and finite profile before the physical N5 call."""
    _run_activated_held_out_stock_scenario(
        tmp_path,
        monkeypatch,
        controlled_candidate_gateway,
        methodology_v2=False,
        fund="treasury",
        retained_sequence=True,
        preflight_first_n5=True,
    )


@pytest.mark.integration
def test_v2_optional_methodology_flows_through_served_foundry_and_fresh_artifact_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: ControlledCandidateGateway,
) -> None:
    """Retain optional-method unknown as a candidate limitation through a fresh result read."""
    _run_activated_held_out_stock_scenario(
        tmp_path,
        monkeypatch,
        controlled_candidate_gateway,
        methodology_v2=True,
    )
