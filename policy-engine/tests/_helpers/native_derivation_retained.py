"""Reopen retained Native fixture facts without regenerating their source or fetch.

The caller supplies a new current demo identity deployment. Retained artifacts
remain historical facts; this setup neither renews a quote nor grants an action.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from polisyos.core import artifacts
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
    NativeDerivationLeafProviderSelection,
)
from polisyos.runtime.quality.acquisition_world_growth import (
    AcquisitionWorldGrowthAttempt,
    AcquisitionWorldGrowthConfig,
    NativeDerivationPortSelection,
    NativeDerivationRouteConfiguration,
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
                "SELECT receipt_ref, receipt_manifest_profile_sha256 FROM "
                "runtime_acquisition_action_heads WHERE source_job_id=? "
                "AND receipt_phase='terminal' ORDER BY action_generation, head_generation",
                (source_job_id,),
            )
        )
        if len(terminal_rows) != 1:
            raise ValueError("retained_native_fixture_terminal_not_unique")

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
    terminal_ref = artifacts.ArtifactRef(
        artifact_id=artifacts.ArtifactID.model_validate(terminal_rows[0]["receipt_ref"]),
        kind="runtime_quality.acquisition_route_loop_receipt",
        media_type="application/json",
        manifest_profile_sha256=terminal_rows[0]["receipt_manifest_profile_sha256"],
    )
    terminal = AcquisitionRouteLoopReceipt.model_validate(
        artifacts.load_core_json_artifact(store, terminal_ref)
    )
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
        configuration=configuration,
        state={
            "holder": {
                "metadata": {"native_authority": authority},
                "configuration": configuration,
            },
            "appointments": [],
        },
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
