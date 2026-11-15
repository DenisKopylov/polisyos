"""Reopen retained Native fixture facts without regenerating their source or fetch.

The caller supplies a new current demo identity deployment. Retained artifacts
remain historical facts; this setup neither renews a quote nor grants an action.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from polisyos.core import FileSystemSignedArtifactEvidenceRepository, artifacts, contracts, security
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


def load_retained_native_source_fixture(
    base: Path,
    *,
    binding_id: str,
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
                "SELECT j.job_id, j.run_id, p.progress_json FROM control_jobs j "
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

    cost_rows = tuple(
        (ref, load_native_derivation_leaf_cost_profile(store, ref))
        for ref in _selected_profiles(store, "runtime.quality.native_derivation_leaf_cost_profile")
    )
    cost_rows = tuple(
        (ref, value)
        for ref, value in cost_rows
        if (value.scope.source_job_id, value.scope.run_id) == (source_job_id, run_id)
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
        state={
            "holder": {
                "metadata": {"native_authority": authority},
                "configuration": configuration,
            },
            "appointments": [],
        },
    )


@dataclass(frozen=True, slots=True)
class RetainedNativeAdmissionSelection:
    """Locate existing fixture acts; these inputs grant no Runtime operation."""

    epoch_admission_evidence_ref: artifacts.ArtifactRef
    epoch_public_key_path: Path
    delegation_contract_ref: artifacts.ArtifactRef
    current_mandate_evidence_ref: artifacts.ArtifactRef
    human_decision_record_ref: artifacts.ArtifactRef | None = None


def _verify_retained_selected_signature(
    store: Any,
    ref: artifacts.ArtifactRef,
    verifier: artifacts.Ed25519Verifier,
) -> None:
    """Verify a legacy ID sidecar only for its exact selected manifest and blob."""
    if ref.manifest_profile_sha256 is None:
        raise ValueError("retained_native_continuation_signature_profile_missing")
    selected_manifest = store.get_manifest_bytes(ref)
    signature = store.get_signature(ref)
    if signature is None:
        # The existing institutional fixture producer signed the default ID.
        # Its sidecar proves this selected view only when the signed bytes agree.
        if store.get_manifest_bytes(ref.artifact_id) != selected_manifest:
            raise ValueError("retained_native_continuation_signature_profile_mismatch")
        signature = store.get_signature(ref.artifact_id)
    if signature is None:
        raise ValueError("retained_native_continuation_mandate_signature_missing")
    verified = verifier.verify(
        ref.artifact_id,
        store.get_bytes(ref),
        selected_manifest,
        signature,
        strict_identity=True,
    )
    if verified.status is not artifacts.SignatureVerificationStatus.VALID:
        raise ValueError("retained_native_continuation_mandate_signature_invalid")


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
    from polisyos.runtime.quality import agent_action_authority as authority

    store = fixture.store

    def selected(ref: artifacts.ArtifactRef, kind: str) -> artifacts.ArtifactRef:
        actual = tuple(
            value
            for value in _selected_profiles(store, kind)
            if artifact_ref_identity_key(value) == artifact_ref_identity_key(ref)
        )
        if len(actual) != 1 or ref.manifest_profile_sha256 is None:
            raise ValueError("retained_native_continuation_selected_profile_missing")
        return actual[0]

    admission_ref = selected(
        selection.epoch_admission_evidence_ref, "core.chronology.signed_artifact_evidence_record"
    )
    evidence = FileSystemSignedArtifactEvidenceRepository(store).read_exact(
        evidence_record_ref=admission_ref
    )
    epoch_identity = "fixture-native-epoch-owner"
    epoch_verifier = artifacts.Ed25519Verifier(strict_identity=True)
    epoch_verifier.load_trusted_key_file(selection.epoch_public_key_path, identity=epoch_identity)
    if not security.verify_signed_evidence(evidence, verifier=epoch_verifier):
        raise ValueError("retained_native_continuation_epoch_signature_invalid")
    admission = security.parse_canonical_statement(
        evidence.blob_bytes, contracts.chronology.PredicatePolicyAdmissionStatement
    )
    prepared = contracts.epoch.load_verified_epoch_statement(
        store=store,
        ref=fixture.deferral.negative_receipt.prepared_epoch_ref,
        expected_kind="epoch.prepared",
    )
    manifest_ref = artifacts.ArtifactRef.model_validate(prepared["stamp"]["semantic_manifest_ref"])
    manifest = contracts.epoch.load_verified_epoch_statement(
        store=store, ref=manifest_ref, expected_kind="epoch.semantic_manifest"
    )
    if (
        admission.key.scope_ref != fixture.attempt.selection.epoch_scope_identity.scope_identity_ref
        or admission.key.authority_purpose != fixture.attempt.selection.authority_purpose
        or admission.key.requested_cutoff_ref != manifest["epoch_ref"]
        or admission.requested_query_context_ref != prepared["query"]["requested_query_context_ref"]
    ):
        raise ValueError("retained_native_continuation_epoch_scope_mismatch")
    epoch_config = EpochDeploymentConfig(
        evidence_cas_root=store.root,
        native_epoch_history_root=fixture.epoch_history_root,
        trusted_issuers=(
            EpochTrustedIssuerConfig(
                identity=epoch_identity,
                public_key_path=selection.epoch_public_key_path,
                roles=("predicate_policy_admission",),
            ),
        ),
        predicate_policy_admission_refs=(admission_ref,),
    )
    contract_ref = selected(
        selection.delegation_contract_ref, "runtime_quality.agent_action_delegation_contract"
    )
    current_ref = selected(
        selection.current_mandate_evidence_ref, "runtime_quality.current_mandate_owner"
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
        or not (current.effective_from <= now < current.effective_until)
        or not (envelope.valid_from <= now < envelope.valid_until)
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
            selected(
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
