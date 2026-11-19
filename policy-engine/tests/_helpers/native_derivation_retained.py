"""Reopen retained Native fixture facts without regenerating their source or fetch.

The caller supplies a new current demo identity deployment. Retained artifacts
remain historical facts; this setup neither renews a quote nor grants an action.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from polisyos.core import artifacts, contracts, security
from polisyos.core.artifacts import artifact_ref_identity_key
from polisyos.core.artifacts.store import CASManifestInventorySnapshot
from polisyos.data_forge.read_api import catalog
from polisyos.runtime.http.services.control.generation_cycle import (
    CompiledRecursiveGenerationCycleRun,
)
from polisyos.runtime.quality.acquisition_planner import (
    _n7_load_configured_candidate_port_source,
    load_n7_derivation_bundle,
    load_native_derivation_leaf_cost_profile,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionRouteLoopReceipt,
    AcquisitionRoutePhaseReceipt,
    NativeDerivationLeafProviderSelection,
)
from polisyos.runtime.quality.acquisition_world_growth import (
    AcquisitionWorldGrowthAttempt,
    AcquisitionWorldGrowthConfig,
    AcquisitionWorldGrowthDeferral,
    NativeDerivationPortSelection,
    NativeDerivationRouteConfiguration,
)
from polisyos.runtime.quality.epoch_deployment import (
    EpochDeploymentConfig,
    EpochTrustedIssuerConfig,
)
from polisyos.runtime.quality.generic_simulation_admission import (
    GenericCycleSimulationProfileV1,
)
from polisyos.runtime.quality.substrate_registry import default_substrate_catalog_paths

if TYPE_CHECKING:
    from polisyos.runtime.http.services.control.run_lifecycle import (
        VerifiedAcquisitionActionOutcome,
    )
    from polisyos.runtime.http.services.control_plane_store import AcquisitionActionHeadRecord


def _selected_profiles(store: Any, kind: str) -> tuple[artifacts.ArtifactRef, ...]:
    """Use the complete canonical manifest denominator, then typed owner readers."""
    snapshot = store.manifest_inventory_snapshot(kind=kind)
    if type(snapshot) is not CASManifestInventorySnapshot or snapshot.verdict != "pass":
        raise ValueError("retained_native_fixture_manifest_inventory_not_established")
    selected = {}
    for row in snapshot.entries:
        ref = artifacts.artifact_ref_for_manifest(row.manifest)
        if ref.kind != kind or ref.manifest_profile_sha256 is None:
            raise ValueError("retained_native_fixture_inventory_profile_invalid")
        selected[artifact_ref_identity_key(ref)] = ref
    return tuple(selected[key] for key in sorted(selected))


def _selected_retained_ref(
    store: Any, ref: artifacts.ArtifactRef, kind: str
) -> artifacts.ArtifactRef:
    """Reopen one full selector through the complete canonical view inventory."""
    if type(ref) is not artifacts.ArtifactRef or ref.manifest_profile_sha256 is None:
        raise ValueError("retained_native_continuation_selected_profile_missing")
    actual = tuple(
        value
        for value in _selected_profiles(store, kind)
        if artifact_ref_identity_key(value) == artifact_ref_identity_key(ref)
    )
    if len(actual) != 1:
        raise ValueError("retained_native_continuation_selected_profile_missing")
    return actual[0]


def load_retained_native_source_fixture(
    base: Path,
    *,
    binding_id: str,
    cost_profile_refs: tuple[artifacts.ArtifactRef, ...] | None = None,
    original_purchase_ref: artifacts.ArtifactRef | None = None,
) -> SimpleNamespace:
    """Load exact historical inputs for a future explicitly configured fixture app.

    This reads the existing SQLite job/head selections in read-only mode. It
    does not initialize the database, provision Catalog, rewrite any source,
    create an epoch issuer, or open an app. The normal app owner must still
    reconcile this selection before a GET or any independently authorized use.
    """
    base = base.resolve(strict=True)
    database = base / "control.sqlite3"
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = tuple(
            connection.execute(
                "SELECT j.job_id, j.run_id, j.payload_ref, p.progress_json FROM control_jobs j "
                "JOIN control_job_progress p ON p.job_id=j.job_id "
                "WHERE j.job_kind='natural_language_run' AND j.state='completed'"
            )
        )
        if len(rows) != 1:
            raise ValueError("retained_native_fixture_source_job_not_unique")
        source_job_id, run_id = rows[0]["job_id"], rows[0]["run_id"]
        progress = json.loads(rows[0]["progress_json"])
        owner = progress["execution_owner_binding"]
        tenant_id, cell_id = owner["tenant_id"], owner["cell_id"]
        terminal_rows = tuple(
            connection.execute(
                "SELECT receipt_ref, receipt_manifest_profile_sha256, action_generation, "
                "route_id, job_id FROM "
                "runtime_acquisition_action_heads WHERE source_job_id=? "
                "AND receipt_phase='terminal' ORDER BY action_generation, head_generation",
                (source_job_id,),
            )
        )
        executing_rows = tuple(
            connection.execute(
                "SELECT receipt_ref, receipt_manifest_profile_sha256, action_generation, "
                "route_id, job_id FROM runtime_acquisition_action_heads "
                "WHERE source_job_id=? AND receipt_phase='executing'",
                (source_job_id,),
            )
        )

    store = artifacts.FileSystemCAS(base / "cas").for_tenant(tenant_id, cell_id)
    compiled_ref = artifacts.ArtifactRef.model_validate(
        progress["compiled_recursive_generation_cycle_artifact_ref"]
    )
    compiled = CompiledRecursiveGenerationCycleRun.model_validate(
        artifacts.load_core_json_artifact(store, compiled_ref)
    )
    handoff = compiled.generic_cycle_simulation_handoff
    if handoff is None:
        raise ValueError("retained_native_fixture_original_handoff_missing")
    profile = GenericCycleSimulationProfileV1.model_validate(
        artifacts.load_core_json_artifact(store, handoff.profile_ref)
    )
    if profile != handoff.profile or (handoff.job_id, handoff.run_id) != (source_job_id, run_id):
        raise ValueError("retained_native_fixture_original_profile_mismatch")
    original_purchases = []
    for row in terminal_rows:
        candidate_ref = artifacts.ArtifactRef(
            artifact_id=artifacts.ArtifactID.model_validate(row["receipt_ref"]),
            kind="runtime_quality.acquisition_route_loop_receipt",
            media_type="application/json",
            manifest_profile_sha256=row["receipt_manifest_profile_sha256"],
        )
        candidate = AcquisitionRouteLoopReceipt.model_validate(
            artifacts.load_core_json_artifact(store, candidate_ref)
        )
        if candidate.terminal_outcome != "quarantined_no_growth":
            continue
        phases = tuple(
            phase
            for phase in executing_rows
            if (phase["action_generation"], phase["route_id"], phase["job_id"])
            == (row["action_generation"], row["route_id"], row["job_id"])
        )
        if len(phases) != 1:
            raise ValueError("retained_native_fixture_executing_phase_not_unique")
        phase_ref = artifacts.ArtifactRef(
            artifact_id=artifacts.ArtifactID.model_validate(phases[0]["receipt_ref"]),
            kind="runtime_quality.acquisition_route_phase_receipt",
            media_type="application/json",
            manifest_profile_sha256=phases[0]["receipt_manifest_profile_sha256"],
        )
        phase = AcquisitionRoutePhaseReceipt.model_validate(
            artifacts.load_core_json_artifact(store, phase_ref)
        )
        if (
            phase.owner_declared_profile_ref is not None
            and phase.prior_paid_input_admission is None
        ):
            original_purchases.append((candidate_ref, candidate))
    if original_purchase_ref is not None:
        selected_purchase = _selected_retained_ref(
            store, original_purchase_ref, "runtime_quality.acquisition_route_loop_receipt"
        )
        original_purchases = [
            row
            for row in original_purchases
            if artifact_ref_identity_key(row[0]) == artifact_ref_identity_key(selected_purchase)
        ]
    if len(original_purchases) != 1:
        raise ValueError("retained_native_fixture_original_purchase_not_unique")
    terminal_ref, terminal = original_purchases[0]
    if (
        terminal.terminal_outcome != "quarantined_no_growth"
        or terminal.source_job_id != source_job_id
        or terminal.run_id != run_id
        or terminal.compiled_ref != str(compiled_ref.artifact_id)
    ):
        raise ValueError("retained_native_fixture_quarantine_scope_mismatch")

    if cost_profile_refs is None:
        cost_rows = tuple(
            (ref, load_native_derivation_leaf_cost_profile(store, ref))
            for ref in _selected_profiles(
                store, "runtime.quality.native_derivation_leaf_cost_profile"
            )
        )
        cost_rows = tuple(
            (ref, value)
            for ref, value in cost_rows
            if (value.scope.source_job_id, value.scope.run_id) == (source_job_id, run_id)
        )
    else:
        from tests._helpers.native_derivation_quotes import select_native_fixture_cost_profiles

        cost_rows = select_native_fixture_cost_profiles(
            store,
            cost_profile_refs,
            expected_source_actor=(tenant_id, cell_id, run_id, source_job_id),
        )
    if not cost_rows:
        raise ValueError("retained_native_fixture_cost_inputs_missing")
    source_ref = cost_rows[0][1].scope.configured_port_source_ref
    if any(
        artifact_ref_identity_key(value.scope.configured_port_source_ref)
        != artifact_ref_identity_key(source_ref)
        for _, value in cost_rows
    ):
        raise ValueError("retained_native_fixture_cost_source_ambiguous")
    source = _n7_load_configured_candidate_port_source(store, source_ref)
    bundle = load_n7_derivation_bundle(store, source.derivation_bundle_ref)
    if {value.scope.source_node_id for _, value in cost_rows} != {
        node.node_id for node in bundle.source_nodes
    }:
        raise ValueError("retained_native_fixture_cost_leaf_denominator_mismatch")
    providers = []
    for _, value in cost_rows:
        declaration = catalog.load_acquisition_supplier_declaration(
            store, value.scope.selected_supplier_ref
        )
        providers.append(
            NativeDerivationLeafProviderSelection(
                source_node_id=value.scope.source_node_id,
                supplier_ref=value.scope.selected_supplier_ref,
                authority_entry_id=declaration.entry.entry_id,
                connector_id=declaration.connector_id,
            )
        )

    attempt_rows = []
    for ref in _selected_profiles(store, "runtime_quality.acquisition_world_growth_attempt"):
        attempt = AcquisitionWorldGrowthAttempt.model_validate(
            artifacts.load_core_json_artifact(store, ref)
        )
        if str(ref.artifact_id) in terminal.owner_receipt_refs:
            attempt_rows.append((ref, attempt))
    if len(attempt_rows) != 1:
        raise ValueError("retained_native_fixture_paid_attempt_not_unique")
    attempt_ref, attempt = attempt_rows[0]
    if (
        attempt.selection.route_id != terminal.route_id
        or attempt.action_phase_ref not in terminal.owner_receipt_refs
    ):
        raise ValueError("retained_native_fixture_paid_attempt_scope_mismatch")
    deferrals = tuple(
        (
            ref,
            AcquisitionWorldGrowthDeferral.model_validate(
                artifacts.load_core_json_artifact(store, ref)
            ),
        )
        for ref in _selected_profiles(store, "runtime_quality.acquisition_world_growth_deferral")
        if str(ref.artifact_id) in terminal.owner_receipt_refs
    )
    if len(deferrals) != 1 or deferrals[0][1].attempt_ref != str(attempt_ref.artifact_id):
        raise ValueError("retained_native_fixture_deferral_not_unique")
    deferral_ref, deferral = deferrals[0]
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge

    pointer_roots = {
        pointer.parent
        for pointer in (base / "cas/runtime/acquisition/world-growth").rglob("*.attempt.json")
        if AcquisitionWorldGrowthBridge._attempt_pointer_ref(pointer, require_selected=True)
        == attempt_ref
    }
    if len(pointer_roots) != 1:
        raise ValueError("retained_native_fixture_attempt_path_not_unique")
    epoch_history_root = next(iter(pointer_roots)) / "epochs"
    if not epoch_history_root.is_dir():
        raise ValueError("retained_native_fixture_epoch_history_missing")
    authority = catalog.CanonicalAcquisitionAuthority.from_provision(
        repo_root=base / "knowledge",
        baseline_path=default_substrate_catalog_paths(base / "knowledge").l1_dcat_path,
    )
    adopted = NativeDerivationRouteConfiguration(
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_id=run_id,
        source_job_id=source_job_id,
        configured_port_source_ref=source_ref,
        owner_declared_cost_profile_refs=tuple(ref for ref, _ in cost_rows),
        ports=(
            NativeDerivationPortSelection(
                derivation_bundle_ref=source.derivation_bundle_ref,
                registered_profile_ref=bundle.registered_profile_ref,
                binding_id=binding_id,
            ),
        ),
        supplier_selections=tuple(providers),
    )
    configuration = AcquisitionWorldGrowthConfig(
        routes=(attempt.selection,), native_derivation_routes=(adopted,)
    )
    return SimpleNamespace(
        base=base,
        store=store,
        cas_root=base / "cas",
        runs_root=base / "cas/runs",
        root=base / "knowledge",
        control_database=database,
        tenant_id=tenant_id,
        cell_id=cell_id,
        job_id=source_job_id,
        control_run_id=run_id,
        core_run_id=progress["core_run_id"],
        compiled=compiled,
        compiled_ref=compiled_ref,
        source_payload_ref=rows[0]["payload_ref"],
        profile=profile,
        source=source,
        source_ref=source_ref,
        terminal=terminal,
        terminal_ref=terminal_ref,
        attempt=attempt,
        attempt_ref=attempt_ref,
        deferral=deferral,
        deferral_ref=deferral_ref,
        epoch_history_root=epoch_history_root,
        configuration=configuration,
        cost_profile_refs=tuple(ref for ref, _ in cost_rows),
        state={
            "holder": {
                "metadata": {"native_authority": authority},
                "configuration": configuration,
            },
            "appointments": [],
        },
    )


@contextmanager
def retained_native_demo_source_case(
    base: Path,
    output_root: Path,
    *,
    cost_profile_refs: tuple[artifacts.ArtifactRef, ...] | None = None,
    original_purchase_ref: artifacts.ArtifactRef | None = None,
) -> Iterator[SimpleNamespace]:
    """Open fresh demo authentication over exact retained facts and existing keys.

    This starts the controlled JWT/OPA fixtures, not a Runtime app or action.
    It loads the original eight institutional keys; it issues no institutional
    act and never substitutes an old grant for current authentication.
    """
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http import deployment_security
    from tests._helpers.acquisition_served_history import _existing_key_config, _ExternalTrust

    trust_root = output_root / "current-demo-trust"
    trust_root.mkdir(parents=True)
    trust = _ExternalTrust(trust_root)
    try:
        signers, identities = _existing_key_config(base / "trust", trust)

        def deployment() -> Any:
            return deployment_security.build_deployment_security(
                deployment_security.DeploymentSecurityConfig.from_mapping(trust.raw)
            )

        claims = deployment().identity_provider.extract_user_claims(
            trust.tokens["acquisition-operator"]
        )
        with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
            fixture = load_retained_native_source_fixture(
                base,
                binding_id="configured-native-two-leaf",
                cost_profile_refs=cost_profile_refs,
                original_purchase_ref=original_purchase_ref,
            )
        if (fixture.tenant_id, fixture.cell_id) != (claims.tenant_id, claims.cell_id):
            raise ValueError("retained_native_demo_actor_scope_mismatch")
        fixture.claims = claims
        bind_retained_native_source_app(fixture, deployment_security_factory=deployment)
        yield SimpleNamespace(
            case=fixture,
            trust=trust,
            signers=signers,
            identities=identities,
            claims=claims,
            deployment=deployment,
        )
    finally:
        trust.close()


@dataclass(frozen=True, slots=True)
class RetainedNativeEpochPolicySelection:
    """Locate an existing signed policy input; this is no current action grant."""

    epoch_admission_evidence_ref: artifacts.ArtifactRef
    epoch_public_key_path: Path


@dataclass(frozen=True, slots=True)
class RetainedNativeAdmissionSelection:
    """Locate existing fixture acts; these inputs grant no Runtime operation."""

    epoch_admission_evidence_ref: artifacts.ArtifactRef
    epoch_public_key_path: Path
    delegation_contract_ref: artifacts.ArtifactRef
    current_mandate_evidence_ref: artifacts.ArtifactRef
    human_decision_record_ref: artifacts.ArtifactRef | None = None


@contextmanager
def retained_native_owner_scope(fixture: SimpleNamespace, claims: Any) -> Iterator[None]:
    """Bind all fixture bootstrap reads to the actual authenticated owner.

    This is a data-read scope, not an action permission. The live control
    handler still establishes its own current authority and execution lease.
    """
    from polisyos.core.security.tenant_context import tenant_scope

    if (claims.tenant_id, claims.cell_id) != (fixture.tenant_id, fixture.cell_id):
        raise ValueError("retained_native_resume_claim_scope_mismatch")
    with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
        yield


def read_retained_native_action_resume_inputs(
    fixture: SimpleNamespace,
    checkpoint: SimpleNamespace,
    *,
    claims: Any,
    control: Any,
    idempotency_key: str,
) -> SimpleNamespace:
    """Read the existing job's exact stored request in one owned bootstrap.

    No projection is reconstructed and no job is created or leased. A caller
    must establish the actual head's recovery purpose before dispatch: new
    protected use requires current authority; already selected custody does not
    turn an expired historical receipt into a current grant.
    """
    from polisyos.runtime.http.services.acquisition_action_service import (
        AcquisitionRouteMutationRequest,
    )

    if checkpoint.human_decision_record_ref is None:
        raise ValueError("retained_native_resume_human_decision_missing")
    with retained_native_owner_scope(fixture, claims):
        job = control._control_store.get_job(checkpoint.action_job_id)
        if job is None:
            raise ValueError("retained_native_resume_job_missing")
        if (
            job.job_id != checkpoint.action_job_id
            or job.kind != "acquisition"
            or job.run_id != fixture.control_run_id
        ):
            raise ValueError("retained_native_resume_job_scope_mismatch")
        payload_ref = control._require_control_job_payload_ref(job)
        payload = control._load_payload_ref(
            payload_ref, kind="runtime.control_job_payload.acquisition"
        )
        if (
            payload.get("tenant_id"),
            payload.get("cell_id"),
            payload.get("run_id"),
            payload.get("route_id"),
        ) != (
            fixture.tenant_id,
            fixture.cell_id,
            fixture.control_run_id,
            checkpoint.mandate_slot["route_id"],
        ):
            raise ValueError("retained_native_resume_payload_scope_mismatch")
        request = AcquisitionRouteMutationRequest.model_validate(payload.get("request"))
        if request.idempotency_key != idempotency_key:
            raise ValueError("retained_native_resume_idempotency_mismatch")
    return SimpleNamespace(job=job, payload_ref=payload_ref, payload=payload, request=request)


def require_retained_native_human_decision_current(record: Any) -> None:
    """Check time after the canonical reader has established receipt custody.

    This predicate grants nothing on its own. Signature, exact job/source,
    current mandate, permission and lease checks remain with their owners.
    """
    now = datetime.now(UTC)
    if (
        record.valid_from is None
        or record.valid_until is None
        or not (record.valid_from <= now < record.valid_until)
    ):
        raise ValueError("retained_native_human_decision_not_current")


def require_retained_native_resume_descendant(
    *,
    store: Any,
    control_store: Any,
    before_head: AcquisitionActionHeadRecord,
    before_ref: artifacts.ArtifactRef,
    outcome: VerifiedAcquisitionActionOutcome,
) -> None:
    """Bind a resume assertion to the canonical owner's verified phase chain.

    The sink, not this assertion helper, verifies receipt/event ancestry. The
    historical SQL owner preserves the exact selected profile for its members.
    """
    scope_fields = (
        "tenant_id",
        "cell_id",
        "run_id",
        "source_job_id",
        "route_id",
        "job_id",
        "action_generation",
    )
    if any(getattr(outcome.head, field) != getattr(before_head, field) for field in scope_fields):
        raise ValueError("retained_native_resume_action_identity_changed")
    if sum(item.receipt_ref == before_head.receipt_ref for item in outcome.phase_chain) != 1:
        raise ValueError("retained_native_resume_selected_ancestor_missing")
    if (
        before_ref.manifest_profile_sha256 is None
        or before_head.receipt_manifest_profile_sha256 is None
    ):
        raise ValueError("retained_native_resume_ancestor_profile_required")
    ancestor = control_store.get_acquisition_action_head_by_receipt(
        tenant_id=before_head.tenant_id,
        cell_id=before_head.cell_id,
        run_id=before_head.run_id,
        source_job_id=before_head.source_job_id,
        route_id=before_head.route_id,
        action_generation=before_head.action_generation,
        receipt_ref=before_head.receipt_ref,
    )
    if ancestor != before_head:
        raise ValueError("retained_native_resume_selected_ancestor_changed")
    actual = artifacts.artifact_ref_for_manifest(
        artifacts.resolve_manifest_by_profile(
            store, ancestor.receipt_ref, ancestor.receipt_manifest_profile_sha256
        )
    )
    if artifact_ref_identity_key(actual) != artifact_ref_identity_key(before_ref):
        raise ValueError("retained_native_resume_ancestor_profile_changed")


@contextmanager
def forbid_retained_native_resume_effects() -> Iterator[None]:
    """Block fresh institutional acts, provider I/O and N4/N5 before their body.

    Reuse the C100 PY_START primitive. Forbidden entries stay enabled after a
    caught refusal; unrelated code disables its own first-start notification.
    Slot 5 is fixture-local and is never taken from another observer.
    """
    from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
    from polisyos.foundry.execute._internal.graph import execute_program_graph
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
    )
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.http.services.human_decisions import HumanDecisionService
    from polisyos.runtime.quality.acquisition_executor import (
        admit_acquisition_with_production_semantic_epoch,
    )
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
    from polisyos.runtime.quality.generation_cycle import N4GenerationPort
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
    )
    from tests._helpers.acquisition_served_history import (
        _appoint_served_acquisition_mandate,
    )
    from tests._helpers.semantic_epoch_native import (
        NativeEpochFixtureCustodian,
        sign_native_epoch_scenario,
    )

    functions = (
        WorldBankConnector.fetch,
        WorldBankWDIAcquisitionExecutionPort.reserve_route_binding,
        AcquisitionWorldGrowthBridge._admit_stored_attempt,
        admit_acquisition_with_production_semantic_epoch,
        N4GenerationPort.__call__,
        JointSimulationHorizonController.run,
        execute_program_graph,
        _appoint_served_acquisition_mandate,
        HumanDecisionService.create_record,
        ControlPlaneStore.reserve_human_decision_action,
        artifacts.Ed25519Signer.sign,
        sign_native_epoch_scenario,
        NativeEpochFixtureCustodian.create.__func__,
        NativeEpochFixtureCustodian.persist_or_reuse,
    )
    targets = {id(function.__code__): function.__code__ for function in functions}
    monitoring = sys.monitoring
    if monitoring.get_tool(5) is not None or monitoring.get_events(5):
        raise RuntimeError("retained_native_resume_monitoring_slot_occupied")

    def started(code: Any, offset: int) -> Any:
        del offset
        if targets.get(id(code)) is code:
            if sys._getframe(1).f_code is not code:
                raise AssertionError("retained_native_resume_actual_entry_not_established")
            raise AssertionError(f"retained_native_resume_forbidden_effect:{code.co_qualname}")
        return monitoring.DISABLE

    monitoring.use_tool_id(5, "retained-native-resume-effects")
    try:
        monitoring.register_callback(5, monitoring.events.PY_START, started)
        monitoring.set_events(5, monitoring.events.PY_START)
        yield
    finally:
        if monitoring.get_tool(5) != "retained-native-resume-effects":
            raise RuntimeError("retained_native_resume_monitoring_owner_changed")
        monitoring.set_events(5, 0)
        monitoring.register_callback(5, monitoring.events.PY_START, None)
        monitoring.free_tool_id(5)


def _verify_retained_selected_signature(
    store: Any,
    ref: artifacts.ArtifactRef,
    verifier: artifacts.Ed25519Verifier,
) -> None:
    """Require a selected fixture reference and delegate signature custody to Core."""
    if ref.manifest_profile_sha256 is None:
        raise ValueError("retained_native_continuation_signature_profile_missing")
    verified = store.verify_signature(ref, verifier, strict_identity=True)
    if verified.status is not artifacts.SignatureVerificationStatus.VALID:
        raise ValueError("retained_native_continuation_mandate_signature_invalid")


def load_retained_native_epoch_policy(
    fixture: SimpleNamespace,
    selection: RetainedNativeEpochPolicySelection,
    *,
    prepared_epoch_ref: artifacts.ArtifactRef | None = None,
    prior_config: EpochDeploymentConfig | None = None,
) -> EpochDeploymentConfig:
    """Read unchanged signed policy for one exact prepared epoch with public trust.

    The native owner reconciles the signature, evidence, policy and relation
    against the independently reopened prepared epoch and its query. A later
    epoch extends the existing deployment's public trust and admission selection.
    """
    from polisyos.runtime.quality.semantic_epoch import (
        EpochResolutionQuery,
        SemanticEpochManifest,
    )
    from polisyos.runtime.quality.semantic_epoch_qualification import (
        SemanticEpochNativePolicyOwner,
        build_semantic_epoch_native_deployment,
    )

    store = fixture.store
    admission_ref = _selected_retained_ref(
        store,
        selection.epoch_admission_evidence_ref,
        "core.chronology.signed_artifact_evidence_record",
    )
    prepared = contracts.epoch.load_verified_epoch_statement(
        store=store,
        ref=prepared_epoch_ref or fixture.deferral.negative_receipt.prepared_epoch_ref,
        expected_kind="epoch.prepared",
    )
    prepared_query = EpochResolutionQuery.model_validate(prepared["query"])
    manifest_ref = artifacts.ArtifactRef.model_validate(prepared["stamp"]["semantic_manifest_ref"])
    manifest = SemanticEpochManifest.model_validate(
        contracts.epoch.load_verified_epoch_statement(
            store=store, ref=manifest_ref, expected_kind="epoch.semantic_manifest"
        )
    )
    if (
        manifest.scope_identity != prepared_query.scope_identity
        or manifest.authority_purpose != prepared_query.authority_purpose
        or manifest.requested_query_context_ref != prepared_query.requested_query_context_ref
    ):
        raise ValueError("retained_native_epoch_policy_prepared_query_mismatch")
    query = contracts.chronology.NativeChronologyQuery(
        domain=contracts.chronology.ChronologyProofDomain(
            format=contracts.chronology.FULL_PREFIX_FORMAT,
            profile=contracts.chronology.FULL_PREFIX_PROFILE,
            proof_domain="semantic_epoch",
            family="epoch",
            scope_ref=prepared_query.scope_identity.scope_identity_ref,
            authority_purpose=prepared_query.authority_purpose,
        ),
        requested_cutoff_ref=manifest.epoch_ref,
        requested_query_context_ref=prepared_query.requested_query_context_ref,
    )
    issuer = EpochTrustedIssuerConfig(
        identity="fixture-native-epoch-owner",
        public_key_path=selection.epoch_public_key_path,
        roles=("predicate_policy_admission",),
    )
    if prior_config is None:
        prior_config = EpochDeploymentConfig(
            evidence_cas_root=store.root,
            native_epoch_history_root=fixture.epoch_history_root,
        )
    if (
        prior_config.evidence_cas_root != store.root
        or prior_config.native_epoch_history_root != fixture.epoch_history_root
    ):
        raise ValueError("retained_native_epoch_policy_roots_mismatch")
    admissions = {
        artifact_ref_identity_key(ref): ref
        for ref in (*prior_config.predicate_policy_admission_refs, admission_ref)
    }
    config = prior_config.model_copy(
        update={
            "trusted_issuers": tuple(dict.fromkeys((*prior_config.trusted_issuers, issuer))),
            "predicate_policy_admission_refs": tuple(admissions.values()),
        },
    )
    deployment = build_semantic_epoch_native_deployment(config)
    with deployment.composition_scope(runtime_artifact_store=store):
        owner = deployment._state().chronology_policy_owner
        if type(owner) is not SemanticEpochNativePolicyOwner:
            raise ValueError("retained_native_epoch_policy_owner_not_established")
        admission, policy, _relation, record, evidence = owner._resolve(query)
        provenance = policy.statement.owner_provenance_ref
        if (
            evidence.persisted.evidence_record_ref != admission_ref
            or record.signing_profile_ref != provenance
            or record.signer_provenance_ref != provenance
            or admission.policy_content_hash
            != contracts.chronology._predicate_policy_content_hash(policy.statement)
            or policy.statement.owner_provenance_content_hash
            != security.raw_content_hash(deployment._repository().read_raw(artifact_ref=provenance))
        ):
            raise ValueError("retained_native_epoch_policy_provenance_mismatch")
    return config


def load_retained_native_admission_checkpoint(
    fixture: SimpleNamespace,
    selection: RetainedNativeAdmissionSelection,
    *,
    institution_key_root: Path,
) -> SimpleNamespace:
    """Reopen signed current fixture acts without issuing or renewing any act.

    The current live Runtime must still recheck its permission, DS9, PA2,
    source, meaning and epoch fences. Paths configure verifiers only; no
    private key is loaded and no signed body or validity interval is changed.
    """
    return _load_retained_native_admission_checkpoint(
        fixture, selection, institution_key_root=institution_key_root, require_current=True
    )


def load_retained_native_action_resume_checkpoint(
    fixture: SimpleNamespace,
    selection: RetainedNativeAdmissionSelection,
    *,
    institution_key_root: Path,
) -> SimpleNamespace:
    """Load signed locators for custody of an already selected action outcome.

    This only configures the original public-key verifiers. The maintained
    resume caller must obtain the exact post-outcome head from the canonical
    sink before dispatch. It cannot use these historical inputs for a new
    activation, mandate, provider call or numerical execution.
    """
    return _load_retained_native_admission_checkpoint(
        fixture, selection, institution_key_root=institution_key_root, require_current=False
    )


def _load_retained_native_admission_checkpoint(
    fixture: SimpleNamespace,
    selection: RetainedNativeAdmissionSelection,
    *,
    institution_key_root: Path,
    require_current: bool,
) -> SimpleNamespace:
    """Share exact selected signature and source checks across read purposes."""
    from polisyos.runtime.quality import agent_action_authority as authority

    store = fixture.store

    epoch_config = load_retained_native_epoch_policy(
        fixture,
        RetainedNativeEpochPolicySelection(
            epoch_admission_evidence_ref=selection.epoch_admission_evidence_ref,
            epoch_public_key_path=selection.epoch_public_key_path,
        ),
    )
    contract_ref = _selected_retained_ref(
        store,
        selection.delegation_contract_ref,
        "runtime_quality.agent_action_delegation_contract",
    )
    current_ref = _selected_retained_ref(
        store, selection.current_mandate_evidence_ref, "runtime_quality.current_mandate_owner"
    )
    contract = authority.DelegationContract.model_validate(
        artifacts.load_core_json_artifact(store, contract_ref)
    )
    current = authority.CurrentMandateOwnerEvidence.model_validate(
        artifacts.load_core_json_artifact(store, current_ref)
    )
    for ref, identity, name in (
        (contract_ref, contract.mandate_owner_ref, "owner"),
        (current_ref, current.evidence_signer_identity, "current"),
    ):
        verifier = artifacts.Ed25519Verifier(strict_identity=True)
        verifier.load_trusted_key_file(institution_key_root / f"{name}.pub", identity=identity)
        _verify_retained_selected_signature(store, ref, verifier)
    contexts = tuple(
        store.get_manifest(ref).same_input_closure for ref in (contract_ref, current_ref)
    )
    if (
        any(context is None for context in contexts)
        or len({(row.tenant_id, row.cell_id, row.run_id, row.job_id) for row in contexts}) != 1
        or (contexts[0].tenant_id, contexts[0].cell_id, contexts[0].run_id)
        != (fixture.tenant_id, fixture.cell_id, fixture.control_run_id)
        or contract.mandate_owner_ref != current.mandate_owner_ref
        or contract.rule_version_ref != current.delegation_rule_version_ref
        or len(contract.action_envelopes) != 1
    ):
        raise ValueError("retained_native_continuation_mandate_scope_mismatch")
    envelope = contract.action_envelopes[0]
    now = datetime.now(UTC)
    if (
        not current.current
        or current.revoked_at is not None
        or (
            require_current
            and (
                not (current.effective_from <= now < current.effective_until)
                or not (envelope.valid_from <= now < envelope.valid_until)
            )
        )
        or envelope.required_tenant_id != fixture.tenant_id
    ):
        raise ValueError("retained_native_continuation_mandate_not_current")
    information = _selected_profiles(store, "test.acquisition.disconfirming")
    if len(information) != 1:
        raise ValueError("retained_native_continuation_information_not_unique")
    slot = {
        "tenant_id": fixture.tenant_id,
        "cell_id": fixture.cell_id,
        "run_id": fixture.control_run_id,
        "route_id": fixture.terminal.route_id,
        "resource_digest": envelope.required_resource_digest,
        "delegation_contract_ref": str(contract_ref.artifact_id),
        "mandate_owner_ref": contract.mandate_owner_ref,
        "delegation_public_key_path": str(institution_key_root / "owner.pub"),
        "current_mandate_evidence_ref": str(current_ref.artifact_id),
        "current_mandate_signer_identity": current.evidence_signer_identity,
        "current_mandate_public_key_path": str(institution_key_root / "current.pub"),
        "verifier_provenance_ref": "fixture://appointment-registry",
        "decision_information_refs": [information[0].model_dump(mode="json")],
        "decision_disconfirming_refs": [information[0].model_dump(mode="json")],
    }
    return SimpleNamespace(
        epoch_config=epoch_config,
        mandate_slot=slot,
        action_job_id=contexts[0].job_id,
        human_decision_record_ref=(
            _selected_retained_ref(
                store,
                selection.human_decision_record_ref,
                "runtime_quality.agent_action_human_decision",
            )
            if selection.human_decision_record_ref is not None
            else None
        ),
    )


def bind_retained_native_source_app(
    fixture: SimpleNamespace, *, deployment_security_factory: Callable[[], Any]
) -> None:
    """Select a new current demo deployment over the retained source and paths.

    Every factory call uses the normal fresh Runtime context. It does not issue
    a mandate or reuse the disposed prior app, identity endpoint, or guard.
    """
    from polisyos.runtime.http.app import create_runtime_api_app

    def app_factory() -> Any:
        return create_runtime_api_app(
            cas_root=fixture.cas_root,
            core_runs_root=fixture.runs_root,
            generic_cycle_simulation_profiles=(fixture.profile,),
            generic_cycle_simulation_root_profile_id=fixture.profile.profile_id,
            allow_fixture_identity=False,
            deployment_security=deployment_security_factory(),
            enable_security_middlewares=True,
            enable_csrf_protection=False,
            repo_root=fixture.root,
        )

    fixture.app_factory = app_factory
