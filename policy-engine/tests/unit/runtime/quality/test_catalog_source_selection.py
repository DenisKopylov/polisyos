from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import duckdb
import pytest
from polisyos.runtime.quality.data_state_substrate import l1_dcat_variable_availability
from polisyos.runtime.quality.substrate_registry import (
    CatalogServingSourceSelection,
    SubstrateRegistryError,
    catalog_serving_source_scope,
    resolve_catalog_serving_source,
)


def _write_minimal_catalog(path: Path, *, include_variable: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(path))
    try:
        connection.execute("CREATE TABLE ds_metric_bindings(metric_id VARCHAR)")
        connection.execute("CREATE TABLE ds_observations(canonical_var VARCHAR)")
        connection.execute("CREATE TABLE ds_datasets(polisyos_metrics VARCHAR[])")
        if include_variable:
            connection.execute("INSERT INTO ds_metric_bindings VALUES ('employment_rate')")
    finally:
        connection.close()


def test_request_context_opens_selected_l1_and_restores_legacy_default(tmp_path: Path) -> None:
    legacy = (
        tmp_path / "production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
    )
    modern_root = tmp_path / "candidate"
    modern = modern_root / "datasets/graph/dataset_catalog.duckdb"
    _write_minimal_catalog(legacy, include_variable=False)
    _write_minimal_catalog(modern, include_variable=True)
    source = resolve_catalog_serving_source(
        tmp_path,
        selection=CatalogServingSourceSelection(
            snapshot_root=modern_root,
            catalog_run_profile="prod_full",
        ),
        requested_profile="prod_full",
    )

    with catalog_serving_source_scope(source):
        selected = l1_dcat_variable_availability(tmp_path, "employment_rate")
    after_scope = l1_dcat_variable_availability(tmp_path, "employment_rate")

    assert selected.status == "available"
    assert selected.coverage_ref.startswith(f"catalog_source://{modern.as_posix()}#")
    assert after_scope.status == "unavailable"
    assert source.selection_basis == "explicit_path_candidate_only"


def test_selection_fails_closed_on_profile_missing_path_and_cross_root(tmp_path: Path) -> None:
    modern_root = tmp_path / "candidate"
    _write_minimal_catalog(
        modern_root / "datasets/graph/dataset_catalog.duckdb",
        include_variable=True,
    )
    selection = CatalogServingSourceSelection(
        snapshot_root=modern_root,
        catalog_run_profile="prod_full",
    )
    with pytest.raises(SubstrateRegistryError, match="catalog_source_selection_profile_mismatch"):
        resolve_catalog_serving_source(
            tmp_path,
            selection=selection,
            requested_profile="preflight_core",
        )
    with pytest.raises(SubstrateRegistryError, match="catalog_source_snapshot_missing"):
        resolve_catalog_serving_source(
            tmp_path,
            selection=CatalogServingSourceSelection(
                snapshot_root=tmp_path / "missing",
                catalog_run_profile="prod_full",
            ),
            requested_profile="prod_full",
        )

    not_directory = tmp_path / "snapshot-file"
    not_directory.write_text("not a directory")
    with pytest.raises(SubstrateRegistryError, match="catalog_source_snapshot_not_directory"):
        resolve_catalog_serving_source(
            tmp_path,
            selection=CatalogServingSourceSelection(
                snapshot_root=not_directory,
                catalog_run_profile="prod_full",
            ),
            requested_profile="prod_full",
        )

    empty_root = tmp_path / "empty-snapshot"
    empty_root.mkdir()
    with pytest.raises(SubstrateRegistryError, match="catalog_source_database_missing"):
        resolve_catalog_serving_source(
            tmp_path,
            selection=CatalogServingSourceSelection(
                snapshot_root=empty_root,
                catalog_run_profile="prod_full",
            ),
            requested_profile="prod_full",
        )
    source = resolve_catalog_serving_source(
        tmp_path,
        selection=selection,
        requested_profile="prod_full",
    )
    with catalog_serving_source_scope(source), pytest.raises(
        SubstrateRegistryError,
        match="catalog_source_repo_root_mismatch",
    ):
        l1_dcat_variable_availability(tmp_path / "other", "employment_rate")


def test_snapshot_root_symlink_is_canonicalized_and_db_member_symlink_refuses(
    tmp_path: Path,
) -> None:
    real_root = tmp_path / "real"
    database = real_root / "datasets/graph/dataset_catalog.duckdb"
    _write_minimal_catalog(database, include_variable=True)
    root_link = tmp_path / "root-link"
    root_link.symlink_to(real_root, target_is_directory=True)
    source = resolve_catalog_serving_source(
        tmp_path,
        selection=CatalogServingSourceSelection(
            snapshot_root=root_link,
            catalog_run_profile="prod_full",
        ),
        requested_profile="prod_full",
    )
    assert source.snapshot_root == real_root.resolve()

    redirected = tmp_path / "redirected.duckdb"
    redirected.write_bytes(database.read_bytes())
    database.unlink()
    database.symlink_to(redirected)
    with pytest.raises(SubstrateRegistryError, match="catalog_source_database_path_unbound"):
        resolve_catalog_serving_source(
            tmp_path,
            selection=CatalogServingSourceSelection(
                snapshot_root=root_link,
                catalog_run_profile="prod_full",
            ),
            requested_profile="prod_full",
        )

def test_nl_wrapper_binds_selected_source_for_sync_consumers(tmp_path: Path) -> None:
    legacy = (
        tmp_path / "production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
    )
    modern_root = tmp_path / "candidate"
    modern = modern_root / "datasets/graph/dataset_catalog.duckdb"
    _write_minimal_catalog(legacy, include_variable=False)
    _write_minimal_catalog(modern, include_variable=True)
    source = resolve_catalog_serving_source(
        tmp_path,
        selection=CatalogServingSourceSelection(
            snapshot_root=modern_root,
            catalog_run_profile="prod_full",
        ),
        requested_profile="prod_full",
    )

    from polisyos.runtime.http.services.control.nl_pipeline import NaturalLanguageRunMixin

    mixin = NaturalLanguageRunMixin()
    mixin._catalog_serving_source = source

    def _read_selected_l1(**_kwargs: object) -> dict[str, str]:
        return {"status": l1_dcat_variable_availability(tmp_path, "employment_rate").status}

    mixin._execute_nl_pipeline_impl = _read_selected_l1
    result = mixin._execute_nl_pipeline(
        run_id="run-1",
        nl_request="select candidate catalog",
        context={},
        domain_hint=None,
        data_source=None,
        max_iterations=1,
        llm_models=["test-model"],
        max_parallel_models=1,
        run_budget_usd=None,
        per_model_budget_usd=None,
        checkpoint_policy="none",
        execution_plan_ref=None,
        execution_plan_payload=None,
        stop_criteria_payload=None,
        governance_constraints_payload=None,
        expected_outputs_payload=None,
    )

    assert result["status"] == "available"
    assert l1_dcat_variable_availability(tmp_path, "employment_rate").status == "unavailable"

def test_malformed_selection_refuses_instead_of_falling_back_to_legacy(tmp_path: Path) -> None:
    with pytest.raises(SubstrateRegistryError, match="catalog_source_selection_invalid"):
        resolve_catalog_serving_source(
            tmp_path,
            selection=object(),  # type: ignore[arg-type]
            requested_profile=None,
        )


def test_default_value_port_constructs_with_selected_source_without_evaluation_context(
    tmp_path: Path,
) -> None:
    modern_root = tmp_path / "candidate"
    _write_minimal_catalog(
        modern_root / "datasets/graph/dataset_catalog.duckdb",
        include_variable=True,
    )
    source = resolve_catalog_serving_source(
        tmp_path,
        selection=CatalogServingSourceSelection(
            snapshot_root=modern_root,
            catalog_run_profile="prod_full",
        ),
        requested_profile="prod_full",
    )

    from polisyos.runtime.quality.generation_cycle import (
        FoundryValuePort,
        GenerationCycleController,
        RealValueOwnerGateway,
        _DefaultSimulationBoundFoundryValuePort,
    )

    # No EvaluationExecutionContext means the recursive leaf passes value_port=None
    # and the real default value-port constructor must bind the source safely.
    with catalog_serving_source_scope(source):
        controller = GenerationCycleController(
            generation_port=cast(Any, object()),
            grounding_port=cast(Any, object()),
            simulation_port=cast(Any, object()),
            promotion_port=cast(Any, object()),
            authority_scope="contract_testing",
            repo_root=tmp_path,
            catalog_serving_source=source,
        )

    default_port = controller._value_port
    assert isinstance(default_port, _DefaultSimulationBoundFoundryValuePort)
    assert default_port.catalog_serving_source is source

    # The wrapper creates FoundryValuePort after N5 supplies the evaluation context.
    # Reconstruct its exact deferred constructor handoff without evaluating a candidate.
    value_port = FoundryValuePort(
        evaluation_context=cast(Any, object()),
        eval_safety_verifier=default_port.eval_safety_verifier,
        owner_gateway=default_port.owner_gateway,
        data_trust=default_port.data_trust,
        repo_root=default_port.repo_root,
        artifact_store=default_port.artifact_store,
        **default_port._selection_configuration(),
    )
    owner_gateway = value_port._owner_gateway
    assert isinstance(owner_gateway, RealValueOwnerGateway)
    assert owner_gateway.catalog_serving_source is source


def test_runtime_container_source_selection_is_appended_to_positional_fields() -> None:
    from dataclasses import fields

    from polisyos.runtime.http.container import RuntimeContainerConfig

    init_fields = [field.name for field in fields(RuntimeContainerConfig) if field.init]
    original_positional_prefix = (
        "cas_root",
        "core_runs_root",
        "max_preview_bytes",
        "lineage_max_depth",
        "lineage_max_nodes",
        "allow_unscoped_artifacts",
        "artifact_redaction_hooks",
        "metrics_factory",
        "tracer_factory",
        "overrides",
        "normative_authority_trust",
        "candidate_simulation_profiles",
        "candidate_simulation_model_declarations",
        "generic_cycle_simulation_profiles",
        "generic_cycle_simulation_root_profile_id",
        "enable_contract_testing_credal_source_attempts",
        "process_worker_capacity",
        "process_worker_profile_revision",
        "catalog_run_profile",
    )
    assert len(original_positional_prefix) == 19
    assert init_fields[: len(original_positional_prefix)] == list(original_positional_prefix)
    assert init_fields[len(original_positional_prefix)] == "catalog_source_selection"
