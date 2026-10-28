"""Read-only replay of Root-admitted retained native output, without model fitting.

This optional local profile is a frozen historical software replay. It does not
establish a live job grant, an external permission, or production currentness.
Root must bind the retained case/source paths in the execution admission and
sandbox them read-only; only the new pytest tmp_path may receive writes.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from polisyos.core.artifacts import read_core_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.substrate_registry import CatalogServingSourceSelection
from polisyos.scientist.methods.search.uncertainty import (
    SearchAssessedObservationV2,
    SearchUnassessedObservationV2,
    SearchUncertaintyTicketState,
    _unavailable_routing_score,
    compute_relative_interval_halfwidth_routing,
    load_search_uncertainty_basis_v2,
)
from tests._helpers.runtime_http import _build_registry_providers
from tests.unit.runtime.quality.test_catalog_source_identity import _selected_fixture


@pytest.mark.parametrize(
    ("case_index", "expected_status", "refusal"),
    [
        (1, "available", None),
        (2, "unavailable", "source_assignment_edge_missing_or_ambiguous"),
        (3, "unavailable", "acquire_data:value_owner_unit_binding_ambiguous"),
        (4, "unavailable", "acquire_data:value_owner_unit_binding_ambiguous"),
    ],
)
def test_real_retained_native_assessment_replays_source_comparability(
    tmp_path, monkeypatch, case_index, expected_status, refusal
) -> None:
    """Reopen real outputs and falsify their declared score with the join intact."""
    admitted_case = os.environ.get("POLISYOS_C71_RETAINED_CASE")
    if not admitted_case:
        pytest.skip("Root-admitted retained native case is unavailable; replay is UNRUN")
    case_root = Path(admitted_case).resolve(strict=True)
    retained = case_root / "basetemp" / f"test_owned_hte_outbox_records_{case_index}"
    cas_root = retained / ".polisyos"
    source_db = cas_root / "control_plane.sqlite3"
    copied_db = tmp_path / "historical-snapshot.sqlite3"
    # SQLite's consistent read-only backup includes committed WAL state. Only
    # this small DB is copied; retained CAS/index/pointer bytes are not copied.
    with sqlite3.connect(source_db.as_uri() + "?mode=ro", uri=True) as source:
        with sqlite3.connect(copied_db) as destination:
            source.backup(destination)
        row = source.execute(
            "SELECT job_id, run_id, payload_json FROM control_outbox_events "
            "WHERE topic=? ORDER BY created_at,event_id LIMIT 1",
            ("control.search.hte_completed",),
        ).fetchone()
    assert row is not None
    payload = json.loads(row[2])
    control = ControlPlaneStore(sqlite_path=str(copied_db))
    scope = control.historical_completed_job_execution_scope(job_id=row[0], expected_run_id=row[1])
    assert scope.status == "established"
    assert scope.actor_authenticated is True
    # Exact FileSystemCAS preserves the production owner checks. Root's outer
    # sandbox must deny every retained write; setup/write failures are not a
    # successful property oracle. All service mutable state is under tmp_path.
    store = FileSystemCAS(cas_root, ownership_enforced=True)
    code_root, owner_root, selected_catalog = _selected_fixture(tmp_path / "catalog")
    selection = CatalogServingSourceSelection(
        snapshot_root=selected_catalog.snapshot_root,
        source_owner_root=owner_root,
        database_relative_path=selected_catalog.database_relative_path,
        catalog_run_profile="prod_full",
    )
    providers = replace(
        _build_registry_providers(catalog_run_profile="prod_full"),
        catalog_source_selection=selection,
    )
    service = ControlPlaneService(
        cas_root=tmp_path / "runtime",
        core_runs_root=cas_root / "runs",
        artifact_store=store,
        control_store=control,
        repo_root=code_root,
        registry_providers=providers,
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="dev",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(copied_db),
            postgres_dsn=None,
        ),
    )
    calls = []

    def actual_join(**kwargs):
        calls.append(kwargs["selected_method_input_ref"])
        return service.verify_search_hte_source_projection_join(**kwargs)

    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher

    def no_refit(*_args, **_kwargs):
        raise AssertionError("retained replay must not dispatch or refit an estimator")

    monkeypatch.setattr(MethodDispatcher, "dispatch", no_refit)
    try:
        with tenant_scope(None, tenant_id=scope.tenant_id, cell_id=scope.cell_id):
            binding_ref = ArtifactRef.model_validate(payload["search_uncertainty_task_binding_ref"])
            binding = read_core_json_artifact(store, binding_ref).value
            state = SearchUncertaintyTicketState(
                store, completion_owner=service, source_projection_verifier=actual_join
            )
            current = state.read_current_snapshot(binding["ticket_id"])
            assert current is not None
            assert current.status == "available_as_of_task_epoch"
            assert current.resolved_projection is not None
            assert calls, "fresh reconciliation did not invoke the real source join"
            selected = current.projection.current_obligations[0].successors[0]
            observation = SearchAssessedObservationV2.model_validate(
                read_core_json_artifact(store, selected.observation_ref).value
            )
            assert observation.routing_score.status == expected_status
            if refusal is not None:
                assert observation.routing_score.unavailable_reason == "scope_not_comparable"
                assert f"source_variable_to_array_join_refused:{refusal}" in observation.limitations
            basis = load_search_uncertainty_basis_v2(store, observation.basis_ref)
            predecessor = SearchUnassessedObservationV2.model_validate(
                read_core_json_artifact(store, observation.predecessor_ref).value
            )
            association = service.resolve_historical_completed_method_execution(
                job_id=observation.job_id,
                completed_event_id=observation.completed_event_id,
                tenant_id=scope.tenant_id,
                cell_id=scope.cell_id,
            )
            assert association is not None
            score_kwargs = {
                "profile_ref": observation.routing_score.profile_ref,
                "theta": observation.theta,
                "lower_bound": observation.lower_bound,
                "upper_bound": observation.upper_bound,
                "confidence_level": observation.confidence_level,
                "comparison_key": observation.routing_score.comparison_key,
            }
            # This is an intentionally false declaration, not a producer or
            # issuer positive. The unchanged real source read must defeat it.
            forged_score = (
                _unavailable_routing_score(**score_kwargs, reason="scope_not_comparable")
                if expected_status == "available"
                else compute_relative_interval_halfwidth_routing(
                    **score_kwargs, unit_binding_status="bound"
                )
            )
            forged = observation.model_copy(update={"routing_score": forged_score})
            before_calls = len(calls)
            with pytest.raises(ValueError, match="recomputed source join"):
                state._replay_source_bound_assessment(
                    successor=forged,
                    association=association,
                    basis=basis,
                    predecessor=predecessor,
                    predecessor_ref=observation.predecessor_ref,
                    routing_profile_ref=observation.routing_score.profile_ref,
                )
            assert len(calls) > before_calls
    finally:
        service.close()
        control.close()
