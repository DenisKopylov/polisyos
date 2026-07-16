from __future__ import annotations

import copy
import json
import os
from collections import Counter
from importlib import import_module
from pathlib import Path
from typing import Any

import duckdb
import pytest
from pydantic import ValidationError


def _insert_owner_rows(
    connection: duckdb.DuckDBPyConnection,
    *,
    suffix: str,
    connector_id: str,
    execution_tier: str,
    raw_variable: str,
    parser_supported: bool = True,
) -> None:
    connection.execute(
        "INSERT INTO ds_datasets VALUES (?, ?, 'CC-BY-4.0', FALSE, ?)",
        [f"dataset-{suffix}", f"Fixture dataset {suffix}", execution_tier],
    )
    connection.execute(
        """
        INSERT INTO ds_distributions VALUES (?, ?, ?, ?, ?, 0.8, ?)
        """,
        [
            f"distribution-{suffix}",
            f"dataset-{suffix}",
            f"https://example.test/{suffix}",
            connector_id,
            f"profile-{suffix}",
            parser_supported,
        ],
    )
    connection.execute(
        """
        INSERT INTO ds_schema_profiles VALUES (?, ?, ?, 1, ?, 'sample', 'json')
        """,
        [
            f"distribution-{suffix}",
            f"dataset-{suffix}",
            json.dumps([raw_variable]),
            "sha256:" + "a" * 64,
        ],
    )


@pytest.fixture
def catalog_path(tmp_path: Path) -> Path:
    path = tmp_path / "dataset_catalog.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute(
        """
        CREATE TABLE ds_metric_bindings (
            metric_id VARCHAR,
            dataset_id VARCHAR,
            distribution_id VARCHAR,
            connector_id VARCHAR,
            profile_id VARCHAR,
            request_dataset_id VARCHAR,
            confidence DOUBLE,
            metric_inference_confidence DOUBLE,
            default_filters VARCHAR,
            execution_tier VARCHAR,
            source VARCHAR
        )
        """
    )
    connection.execute(
        """
        INSERT INTO ds_metric_bindings VALUES
            ('metric_alpha', 'dataset-a', 'distribution-a', 'family.alpha',
             'profile-a', 'request-a', 0.9, 0.8, '{}', 'transport_ready', 'fixture'),
            ('metric_alpha', 'dataset-b', 'distribution-b', 'family.beta',
             'profile-b', 'request-b', 0.8, 0.7, '{}', 'fetchable', 'fixture'),
            ('metric_beta', 'dataset-c', 'distribution-c', 'family.alpha',
             'profile-c', 'request-c', 0.7, 0.6, '{}', 'catalog', 'fixture'),
            ('metric_delta', 'dataset-d', 'distribution-d', 'family.beta',
             'profile-d', 'request-d', 0.6, 0.5, '{}', 'transport_ready', 'fixture')
        """
    )
    connection.execute(
        """
        CREATE TABLE ds_observations (
            observation_id VARCHAR,
            dataset_id VARCHAR,
            raw_variable VARCHAR,
            canonical_var VARCHAR
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE ds_distributions (
            id VARCHAR,
            dataset_id VARCHAR,
            url VARCHAR,
            connector_type VARCHAR,
            profile_id VARCHAR,
            quality_score DOUBLE,
            parser_supported BOOLEAN
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE ds_variable_alignments (
            dataset_id VARCHAR,
            raw_variable VARCHAR,
            canonical_var VARCHAR,
            method VARCHAR,
            confidence DOUBLE,
            evidence VARCHAR,
            is_proxy BOOLEAN,
            proxy_penalty DOUBLE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE ds_schema_profiles (
            distribution_id VARCHAR,
            dataset_id VARCHAR,
            columns_json VARCHAR,
            sample_row_count INTEGER,
            preview_sample_hash VARCHAR,
            inference_mode VARCHAR,
            parser_mode VARCHAR
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE ds_datasets (
            id VARCHAR,
            title VARCHAR,
            access_license VARCHAR,
            access_auth_required BOOLEAN,
            execution_tier VARCHAR
        )
        """
    )
    _insert_owner_rows(
        connection,
        suffix="a",
        connector_id="family.alpha",
        execution_tier="transport_ready",
        raw_variable="raw-alpha",
    )
    _insert_owner_rows(
        connection,
        suffix="b",
        connector_id="family.beta",
        execution_tier="fetchable",
        raw_variable="raw-alpha",
    )
    _insert_owner_rows(
        connection,
        suffix="c",
        connector_id="family.alpha",
        execution_tier="catalog",
        raw_variable="raw-beta",
    )
    _insert_owner_rows(
        connection,
        suffix="d",
        connector_id="family.beta",
        execution_tier="transport_ready",
        raw_variable="raw-delta",
    )
    connection.execute(
        """
        INSERT INTO ds_observations VALUES
            ('observation-alpha', 'dataset-a', 'raw-alpha', 'metric_alpha'),
            ('observation-unrelated', 'dataset-z', 'raw-delta', 'metric_delta')
        """
    )
    connection.execute(
        """
        INSERT INTO ds_variable_alignments VALUES
            ('dataset-a', 'raw-alpha', 'metric_alpha', 'owner_exact', 0.99,
             'fixture-alpha', FALSE, 0.0),
            ('dataset-c', 'raw-beta', 'metric_beta', 'owner_alignment', 0.85,
             'fixture-beta', FALSE, 0.0),
            ('dataset-z', 'raw-delta', 'metric_delta', 'unrelated_alignment', 0.95,
             'fixture-unrelated', FALSE, 0.0)
        """
    )
    connection.close()
    return path


def _census() -> Any:
    return import_module("tools.quality.validation.layer3_gy_n13a_acquisition_census")


def test_census_boundary_models_are_strict() -> None:
    census = _census()

    boundary_models = (
        census.CatalogIdentity,
        census.AlignmentCandidate,
        census.MetricResolution,
        census.DemandRequirement,
        census.DemandVariableEvidence,
        census.ReverseDemandResidual,
        census.RouteRequirement,
        census.RouteProjection,
        census.VariableSupplyEvidence,
        census.RouteEvidence,
        census.FetchPlanSampleRow,
        census.FetchPlanProjection,
        census.FetchPlanExecutionFence,
        census.FetchPlanGenerationProof,
        census.ProbeBudget,
        census.SchemaProfileContract,
        census.ProbeRequest,
        census.ProbeRawResponse,
        census.DerivedLiveness,
        census.FamilyScorecard,
        census.GrowthBacklogRow,
        census.ProjectionBinding,
        census.DemandProjection,
        census.CensusManifest,
    )

    assert all(
        model.model_json_schema().get("additionalProperties") is False for model in boundary_models
    )


def test_catalog_source_derives_full_denominators_from_rows(
    catalog_path: Path,
) -> None:
    census = _census()

    source = census.read_catalog_source(
        catalog_path,
        source_locator="production_data/fixture/dataset_catalog.duckdb",
    )

    assert source.metric_ids == ("metric_alpha", "metric_beta", "metric_delta")
    assert source.connector_families == ("family.alpha", "family.beta")
    assert source.identity.binding_metric_count == 3
    assert source.identity.connector_family_count == 2
    assert source.identity.binding_row_count == 4
    assert source.identity.execution_tier_counts == {
        "catalog": 1,
        "fetchable": 1,
        "transport_ready": 2,
    }


def test_catalog_source_does_not_pin_metric_or_family_denominators(
    catalog_path: Path,
) -> None:
    census = _census()
    before = census.read_catalog_source(catalog_path, source_locator="fixture")
    connection = duckdb.connect(str(catalog_path))
    _insert_owner_rows(
        connection,
        suffix="g",
        connector_id="family.gamma",
        execution_tier="fetchable",
        raw_variable="raw-gamma",
    )
    connection.execute(
        """
        INSERT INTO ds_metric_bindings VALUES
            ('metric_gamma', 'dataset-g', 'distribution-g', 'family.gamma',
             'profile-g', 'request-g', 0.9, 0.9, '{}', 'fetchable', 'fixture')
        """
    )
    connection.close()

    after = census.read_catalog_source(catalog_path, source_locator="fixture")

    assert before.identity.binding_metric_count == 3
    assert before.identity.connector_family_count == 2
    assert after.identity.binding_metric_count == 4
    assert after.identity.connector_family_count == 3
    assert after.metric_ids[-1] == "metric_gamma"
    assert after.connector_families[-1] == "family.gamma"


def test_catalog_source_fails_closed_on_fake_schema_profile_contract(
    catalog_path: Path,
) -> None:
    census = _census()
    connection = duckdb.connect(str(catalog_path))
    connection.execute("ALTER TABLE ds_schema_profiles DROP COLUMN inference_mode")
    connection.close()

    with pytest.raises(census.CatalogContractError) as exc_info:
        census.read_catalog_source(catalog_path, source_locator="fixture")

    assert exc_info.value.code == "catalog_schema_missing_columns"
    assert "ds_schema_profiles.inference_mode" in str(exc_info.value)


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (
            "DELETE FROM ds_datasets WHERE id = 'dataset-a'",
            "catalog_binding_dataset_missing",
        ),
        (
            "DELETE FROM ds_distributions WHERE id = 'distribution-a'",
            "catalog_binding_distribution_missing",
        ),
        (
            "UPDATE ds_distributions SET dataset_id = 'dataset-z' WHERE id = 'distribution-a'",
            "catalog_binding_distribution_dataset_mismatch",
        ),
        (
            "UPDATE ds_distributions SET connector_type = 'family.fake' "
            "WHERE id = 'distribution-a'",
            "catalog_binding_connector_mismatch",
        ),
        (
            "UPDATE ds_distributions SET profile_id = 'profile-fake' WHERE id = 'distribution-a'",
            "catalog_binding_profile_mismatch",
        ),
        (
            "UPDATE ds_metric_bindings SET request_dataset_id = ' ' "
            "WHERE distribution_id = 'distribution-a'",
            "catalog_binding_request_dataset_id_invalid",
        ),
        (
            "UPDATE ds_metric_bindings SET execution_tier = 'magic' "
            "WHERE distribution_id = 'distribution-a'",
            "catalog_binding_execution_tier_invalid",
        ),
        (
            "UPDATE ds_metric_bindings SET execution_tier = 'transport_ready' "
            "WHERE distribution_id = 'distribution-c'",
            "catalog_binding_execution_tier_mismatch",
        ),
        (
            "UPDATE ds_distributions SET parser_supported = FALSE WHERE id = 'distribution-a'",
            "catalog_binding_executable_parser_unsupported",
        ),
        (
            "DELETE FROM ds_schema_profiles WHERE distribution_id = 'distribution-a'",
            "catalog_binding_executable_schema_profile_missing",
        ),
    ],
)
def test_metric_resolution_fails_closed_on_invalid_binding_owner_edges(
    catalog_path: Path,
    mutation: str,
    expected_code: str,
) -> None:
    census = _census()
    connection = duckdb.connect(str(catalog_path))
    connection.execute(mutation)
    connection.close()

    with pytest.raises(census.CatalogContractError) as exc_info:
        census.derive_metric_resolutions(catalog_path)

    assert exc_info.value.code == expected_code


@pytest.mark.parametrize("read_path", ["source", "resolution", "reverse_demand"])
def test_all_catalog_read_paths_share_fake_executable_validation(
    catalog_path: Path,
    read_path: str,
) -> None:
    census = _census()
    connection = duckdb.connect(str(catalog_path))
    connection.execute(
        """
        UPDATE ds_distributions
        SET parser_supported = FALSE
        WHERE id = 'distribution-a'
        """
    )
    connection.close()

    def read_catalog_path() -> None:
        if read_path == "source":
            census.read_catalog_source(catalog_path, source_locator="fixture")
        elif read_path == "resolution":
            census.derive_metric_resolutions(catalog_path)
        else:
            census.measure_reverse_demand(
                catalog_path,
                (
                    census.DemandRequirement(
                        variable_id="metric_alpha",
                        demand_sources=("fixture.metric_alpha",),
                    ),
                ),
            )

    with pytest.raises(census.CatalogContractError) as exc_info:
        read_catalog_path()

    assert exc_info.value.code == "catalog_binding_executable_parser_unsupported"


@pytest.mark.parametrize(
    ("metric_id", "connector_id", "expected_code"),
    [
        ("", "family.alpha", "catalog_metric_id_invalid"),
        (None, "family.alpha", "catalog_metric_id_invalid"),
        ("metric_gamma", "", "catalog_connector_id_invalid"),
        ("metric_gamma", None, "catalog_connector_id_invalid"),
    ],
)
def test_catalog_source_fails_closed_on_invalid_denominator_owner_rows(
    catalog_path: Path,
    metric_id: str | None,
    connector_id: str | None,
    expected_code: str,
) -> None:
    census = _census()
    connection = duckdb.connect(str(catalog_path))
    connection.execute(
        """
        INSERT INTO ds_metric_bindings VALUES
            (?, 'dataset-g', 'distribution-g', ?, 'profile-g', 'request-g',
             0.9, 0.9, '{}', 'fetchable', 'fixture')
        """,
        [metric_id, connector_id],
    )
    connection.close()

    with pytest.raises(census.CatalogContractError) as exc_info:
        census.read_catalog_source(catalog_path, source_locator="fixture")

    assert exc_info.value.code == expected_code


def test_semantic_content_hash_excludes_only_declared_run_economics() -> None:
    census = _census()
    first = {
        "observed_at": "2026-07-16T10:00:00Z",
        "capture_wall_time_seconds": 12.0,
        "evidence": {"status": "dead", "count": 3},
    }
    second = {
        "observed_at": "2026-07-16T11:00:00Z",
        "capture_wall_time_seconds": 42.0,
        "evidence": {"status": "dead", "count": 3},
    }

    assert census.semantic_content_hash(first) == census.semantic_content_hash(second)

    second["evidence"]["status"] = "alive_conformant"
    assert census.semantic_content_hash(first) != census.semantic_content_hash(second)


def test_semantic_content_hash_keeps_nested_observation_time_decisive() -> None:
    census = _census()
    first = {"evidence": {"observed_at": "2026-07-16T10:00:00Z"}}
    second = {"evidence": {"observed_at": "2026-07-16T11:00:00Z"}}

    assert census.semantic_content_hash(first) != census.semantic_content_hash(second)


def test_probe_request_carries_one_request_variable_with_a_one_call_budget() -> None:
    census = _census()

    with pytest.raises(ValidationError):
        census.ProbeBudget(
            timeout_seconds=5.0,
            max_response_bytes=1024,
            minimum_interval_seconds=0.1,
            call_budget=2,
        )

    budget = census.ProbeBudget(
        timeout_seconds=5.0,
        max_response_bytes=1024,
        minimum_interval_seconds=0.1,
        call_budget=1,
    )
    profile = census.SchemaProfileContract(
        distribution_id="distribution-a",
        dataset_id="dataset-a",
        profile_id="profile-a",
        columns=("value",),
        sample_row_count=1,
        preview_sample_hash="sha256:" + "a" * 64,
        inference_mode="sample",
        parser_mode="json",
    )
    request = census.ProbeRequest(
        attempt_id="attempt-a",
        metric_id="metric-alpha",
        request_variable="value",
        connector_id="family.alpha",
        request_dataset_id="request-a",
        endpoint_url="https://example.test/data",
        schema_profile=profile,
        budget=budget,
        access_license="CC-BY-4.0",
        auth_required=False,
        dry_run_receipt_sha256="sha256:" + "b" * 64,
    )

    assert request.metric_id == "metric-alpha"
    assert request.request_variable == "value"
    assert request.budget.call_budget == 1


def test_manifest_versions_are_literal_and_observation_time_is_datetime() -> None:
    census = _census()
    properties = census.CensusManifest.model_json_schema()["properties"]

    assert properties["schema_version"]["const"] == census.SCHEMA_VERSION
    assert properties["rule_version"]["const"] == census.RULE_VERSION
    assert properties["observed_at"]["format"] == "date-time"


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("table_row_counts", {"ds_metric_bindings": -1}),
        ("execution_tier_counts", {"catalog": -1}),
    ],
)
def test_catalog_identity_rejects_negative_count_maps(
    field_name: str,
    value: dict[str, int],
) -> None:
    census = _census()
    fields: dict[str, Any] = {
        "source_locator": "fixture",
        "catalog_content_sha256": "sha256:" + "a" * 64,
        "catalog_byte_size": 1,
        "table_row_counts": {"ds_metric_bindings": 1},
        "binding_row_count": 1,
        "binding_metric_count": 1,
        "connector_family_count": 1,
        "execution_tier_counts": {"catalog": 1},
    }
    fields[field_name] = value

    with pytest.raises(ValidationError):
        census.CatalogIdentity(**fields)


def test_other_count_maps_reject_negative_values() -> None:
    census = _census()

    with pytest.raises(ValidationError):
        census.RouteEvidence(
            route=census.RouteRequirement(
                route_id="route-a",
                domain_role="domain-a",
                demanded_metrics=("metric-a",),
                witness_kind="owner_acquisition_route",
                candidate_ref="candidate-a",
                requirement_gap_id="gap-a",
                gap_source="grounding_owner",
                row_addressable_variable=None,
                planner_gap_kind="relation_gap",
                planner_strategy_kind="acquire",
                blocker_codes=("relation_missing",),
                missing_requirement_fields=("relation:candidate-a",),
                missing_link="relation:candidate-a",
            ),
            declared_supply=census.VariableSupplyEvidence(
                variable_ids=("metric-a",),
                local_observation_count=0,
                binding_count=1,
                executable_binding_count=0,
                binding_tier_counts={"catalog": -1},
                alignment_count=0,
                nonproxy_alignment_count=0,
                connector_ids=("family.alpha",),
            ),
            row_addressable_supply=None,
            route_class=census.RouteClass.NOT_A_DATA_GAP,
        )

    with pytest.raises(ValidationError):
        census.FamilyScorecard(
            connector_id="family.alpha",
            selected_probe_count=1,
            live_attempt_count=1,
            dry_run_passed=True,
            liveness_counts={census.LivenessState.DEAD: -1},
            tier_decay_findings=(),
        )


def _alignment_candidate(census: Any) -> Any:
    return census.AlignmentCandidate(
        dataset_id="dataset-a",
        raw_variable="raw-a",
        canonical_variable="metric-b",
        confidence=0.9,
        is_proxy=False,
        proxy_penalty=0.0,
        method="owner",
        evidence="fixture",
        bound_observation_edge_missing=False,
    )


def test_metric_resolution_enforces_status_evidence_algebra() -> None:
    census = _census()
    candidate = _alignment_candidate(census)

    exact = census.MetricResolution(
        metric_id="metric-a",
        resolution_status=census.ResolutionStatus.EXACT,
        resolution_scope=census.ResolutionScope.DATASET_LEVEL_IDENTITY,
        binding_count=1,
        binding_dataset_count=1,
        exact_observation_count=1,
        alignment_candidate_count=0,
        binding_tier_counts={"catalog": 1},
        connector_ids=("family.alpha",),
        exact_canonical_variable="metric-a",
        limitations=(census.ResolutionLimitation.CATALOG_BINDING_FIELD_EDGE_MISSING,),
    )
    aligned = census.MetricResolution(
        metric_id="metric-b",
        resolution_status=census.ResolutionStatus.VIA_ALIGNMENT,
        resolution_scope=census.ResolutionScope.DATASET_LEVEL_IDENTITY,
        binding_count=1,
        binding_dataset_count=1,
        exact_observation_count=0,
        alignment_candidate_count=1,
        binding_tier_counts={"catalog": 1},
        connector_ids=("family.alpha",),
        best_alignment=candidate,
        alignment_candidates=(candidate,),
        limitations=(census.ResolutionLimitation.CATALOG_BINDING_FIELD_EDGE_MISSING,),
    )
    unresolved = census.MetricResolution(
        metric_id="metric-c",
        resolution_status=census.ResolutionStatus.UNRESOLVED,
        resolution_scope=census.ResolutionScope.DATASET_LEVEL_IDENTITY,
        binding_count=1,
        binding_dataset_count=1,
        exact_observation_count=0,
        alignment_candidate_count=0,
        binding_tier_counts={"catalog": 1},
        connector_ids=("family.alpha",),
    )

    assert exact.exact_canonical_variable == "metric-a"
    assert aligned.best_alignment == candidate
    assert unresolved.best_alignment is None

    invalid_rows = (
        {
            "metric_id": "metric-a",
            "resolution_status": census.ResolutionStatus.EXACT,
            "resolution_scope": census.ResolutionScope.DATASET_LEVEL_IDENTITY,
            "binding_count": 1,
            "binding_dataset_count": 1,
            "exact_observation_count": 0,
            "alignment_candidate_count": 0,
            "binding_tier_counts": {"catalog": 1},
            "connector_ids": ("family.alpha",),
            "limitations": (census.ResolutionLimitation.CATALOG_BINDING_FIELD_EDGE_MISSING,),
        },
        {
            "metric_id": "metric-b",
            "resolution_status": census.ResolutionStatus.VIA_ALIGNMENT,
            "resolution_scope": census.ResolutionScope.DATASET_LEVEL_IDENTITY,
            "binding_count": 1,
            "binding_dataset_count": 1,
            "exact_observation_count": 0,
            "alignment_candidate_count": 0,
            "binding_tier_counts": {"catalog": 1},
            "connector_ids": ("family.alpha",),
            "limitations": (census.ResolutionLimitation.CATALOG_BINDING_FIELD_EDGE_MISSING,),
        },
        {
            "metric_id": "metric-c",
            "resolution_status": census.ResolutionStatus.UNRESOLVED,
            "resolution_scope": census.ResolutionScope.DATASET_LEVEL_IDENTITY,
            "binding_count": 1,
            "binding_dataset_count": 1,
            "exact_observation_count": 0,
            "alignment_candidate_count": 1,
            "binding_tier_counts": {"catalog": 1},
            "connector_ids": ("family.alpha",),
            "best_alignment": candidate,
            "alignment_candidates": (candidate,),
        },
    )
    for row in invalid_rows:
        with pytest.raises(ValidationError):
            census.MetricResolution(**row)


def test_canonical_json_bytes_are_byte_stable() -> None:
    census = _census()

    left = {"metrics": ["b", "a"], "nested": {"z": 1, "a": True}}
    right = {"nested": {"a": True, "z": 1}, "metrics": ["b", "a"]}

    assert census.canonical_json_bytes(left) == census.canonical_json_bytes(right)
    assert census.canonical_json_bytes(left).endswith(b"\n")


def test_metric_resolution_partition_uses_only_binding_linked_owner_evidence(
    catalog_path: Path,
) -> None:
    census = _census()

    rows = census.derive_metric_resolutions(catalog_path)
    by_metric = {row.metric_id: row for row in rows}

    assert Counter(row.resolution_status for row in rows) == {
        census.ResolutionStatus.EXACT: 1,
        census.ResolutionStatus.VIA_ALIGNMENT: 1,
        census.ResolutionStatus.UNRESOLVED: 1,
    }
    assert by_metric["metric_alpha"].exact_observation_count == 1
    assert by_metric["metric_alpha"].binding_tier_counts == {
        "fetchable": 1,
        "transport_ready": 1,
    }
    assert by_metric["metric_alpha"].connector_ids == (
        "family.alpha",
        "family.beta",
    )
    assert by_metric["metric_alpha"].limitations == (
        census.ResolutionLimitation.CATALOG_BINDING_FIELD_EDGE_MISSING,
    )
    assert by_metric["metric_beta"].best_alignment.dataset_id == "dataset-c"
    assert by_metric["metric_beta"].best_alignment.raw_variable == "raw-beta"
    assert by_metric["metric_beta"].alignment_candidate_count == 1
    assert by_metric["metric_delta"].resolution_status is census.ResolutionStatus.UNRESOLVED


def test_resolution_scope_and_limitations_recompute_from_catalog_keys(
    catalog_path: Path,
) -> None:
    census = _census()
    connection = duckdb.connect(str(catalog_path))
    connection.execute("ALTER TABLE ds_metric_bindings ADD COLUMN raw_variable VARCHAR")
    connection.execute("ALTER TABLE ds_observations ADD COLUMN distribution_id VARCHAR")
    connection.execute(
        """
        UPDATE ds_metric_bindings
        SET raw_variable = CASE dataset_id
            WHEN 'dataset-a' THEN 'raw-alpha'
            WHEN 'dataset-b' THEN 'raw-alpha'
            WHEN 'dataset-c' THEN 'raw-beta'
            WHEN 'dataset-d' THEN 'raw-delta'
        END
        """
    )
    connection.execute(
        """
        UPDATE ds_observations
        SET distribution_id = CASE dataset_id
            WHEN 'dataset-a' THEN 'distribution-a'
            ELSE 'distribution-z'
        END
        """
    )
    connection.close()

    rows = census.derive_metric_resolutions(catalog_path)
    by_metric = {row.metric_id: row for row in rows}

    assert all(
        row.resolution_scope is census.ResolutionScope.DISTRIBUTION_FIELD_BOUND for row in rows
    )
    assert by_metric["metric_alpha"].resolution_status is census.ResolutionStatus.EXACT
    assert by_metric["metric_beta"].resolution_status is census.ResolutionStatus.VIA_ALIGNMENT
    assert by_metric["metric_alpha"].limitations == ()
    assert by_metric["metric_beta"].limitations == ()

    connection = duckdb.connect(str(catalog_path))
    connection.execute(
        """
        UPDATE ds_metric_bindings
        SET raw_variable = 'not-raw-beta'
        WHERE metric_id = 'metric_beta'
        """
    )
    connection.close()
    flipped = next(
        row
        for row in census.derive_metric_resolutions(catalog_path)
        if row.metric_id == "metric_beta"
    )

    assert flipped.resolution_status is census.ResolutionStatus.UNRESOLVED


def test_unrelated_dataset_alignment_does_not_resolve_metric(
    catalog_path: Path,
) -> None:
    census = _census()

    row = next(
        row
        for row in census.derive_metric_resolutions(catalog_path)
        if row.metric_id == "metric_delta"
    )

    assert row.resolution_status is census.ResolutionStatus.UNRESOLVED
    assert row.alignment_candidates == ()


def test_same_dataset_predicate_is_decisive_for_exact_resolution(
    catalog_path: Path,
) -> None:
    census = _census()
    connection = duckdb.connect(str(catalog_path))
    connection.execute(
        """
        INSERT INTO ds_observations VALUES
            ('observation-beta-unrelated', 'dataset-z', 'raw-beta', 'metric_beta')
        """
    )
    connection.close()

    before = next(
        row
        for row in census.derive_metric_resolutions(catalog_path)
        if row.metric_id == "metric_beta"
    )
    connection = duckdb.connect(str(catalog_path))
    connection.execute(
        """
        UPDATE ds_observations
        SET dataset_id = 'dataset-c'
        WHERE observation_id = 'observation-beta-unrelated'
        """
    )
    connection.close()
    after = next(
        row
        for row in census.derive_metric_resolutions(catalog_path)
        if row.metric_id == "metric_beta"
    )

    assert before.resolution_status is census.ResolutionStatus.VIA_ALIGNMENT
    assert after.resolution_status is census.ResolutionStatus.EXACT


def test_metric_resolution_denominator_grows_without_code_changes(
    catalog_path: Path,
) -> None:
    census = _census()
    connection = duckdb.connect(str(catalog_path))
    _insert_owner_rows(
        connection,
        suffix="n",
        connector_id="family.novel",
        execution_tier="fetchable",
        raw_variable="raw-novel",
    )
    connection.execute(
        """
        INSERT INTO ds_metric_bindings VALUES
            ('metric_novel', 'dataset-n', 'distribution-n', 'family.novel',
             'profile-n', 'request-n', 0.88, 0.8, '{}', 'fetchable', 'fixture')
        """
    )
    connection.execute(
        """
        INSERT INTO ds_variable_alignments VALUES
            ('dataset-n', 'raw-novel', 'metric_novel', 'owner_alignment', 0.87,
             'fixture-novel', TRUE, 0.25)
        """
    )
    connection.close()

    rows = census.derive_metric_resolutions(catalog_path)
    novel = next(row for row in rows if row.metric_id == "metric_novel")

    assert len(rows) == 4
    assert novel.resolution_status is census.ResolutionStatus.VIA_ALIGNMENT
    assert novel.proxy_only is True
    assert novel.best_alignment.proxy_penalty == 0.25
    assert novel.limitations == (census.ResolutionLimitation.CATALOG_BINDING_FIELD_EDGE_MISSING,)


def test_resolution_status_is_recomputed_when_decisive_owner_edge_changes(
    catalog_path: Path,
) -> None:
    census = _census()
    before = next(
        row
        for row in census.derive_metric_resolutions(catalog_path)
        if row.metric_id == "metric_beta"
    )
    connection = duckdb.connect(str(catalog_path))
    _insert_owner_rows(
        connection,
        suffix="o",
        connector_id="family.alpha",
        execution_tier="catalog",
        raw_variable="raw-catalog-only",
    )
    connection.execute(
        """
        UPDATE ds_variable_alignments
        SET canonical_var = 'not_metric_beta'
        WHERE dataset_id = 'dataset-c'
        """
    )
    connection.close()
    after = next(
        row
        for row in census.derive_metric_resolutions(catalog_path)
        if row.metric_id == "metric_beta"
    )

    assert before.resolution_status is census.ResolutionStatus.VIA_ALIGNMENT
    assert after.resolution_status is census.ResolutionStatus.UNRESOLVED


def test_alignment_order_and_proxy_evidence_recompute_from_owner_rows(
    catalog_path: Path,
) -> None:
    census = _census()
    connection = duckdb.connect(str(catalog_path))
    connection.execute(
        """
        INSERT INTO ds_variable_alignments VALUES
            ('dataset-c', 'raw-beta-second', 'metric_beta', 'owner_alignment', 0.80,
             'fixture-beta-second', FALSE, 0.0)
        """
    )
    connection.close()
    before = next(
        row
        for row in census.derive_metric_resolutions(catalog_path)
        if row.metric_id == "metric_beta"
    )

    connection = duckdb.connect(str(catalog_path))
    connection.execute(
        """
        UPDATE ds_variable_alignments
        SET confidence = 0.65, is_proxy = TRUE, proxy_penalty = 0.30
        WHERE dataset_id = 'dataset-c' AND raw_variable = 'raw-beta'
        """
    )
    connection.close()
    after = next(
        row
        for row in census.derive_metric_resolutions(catalog_path)
        if row.metric_id == "metric_beta"
    )

    assert before.alignment_ambiguous is True
    assert before.best_alignment.raw_variable == "raw-beta"
    assert after.best_alignment.raw_variable == "raw-beta-second"
    mutated = next(
        candidate
        for candidate in after.alignment_candidates
        if candidate.raw_variable == "raw-beta"
    )
    assert mutated.confidence == 0.65
    assert mutated.is_proxy is True
    assert mutated.proxy_penalty == 0.30


def _route_run(
    *,
    witness_kind: str,
    demanded_variable: str,
    gap_variable: str | None = None,
    route_suffix: str = "a",
) -> dict[str, Any]:
    gap_id = f"requirement-gap:{route_suffix}"
    candidate_ref = f"candidate-{route_suffix}"
    row_addressable = witness_kind == "owner_data_gap"
    variable = gap_variable or demanded_variable
    missing_fields = [
        f"canonical_variable_observations:{variable}"
        if row_addressable
        else f"grounding_relation_or_owner_lever:{candidate_ref}"
    ]
    blocker = (
        "method_estimand_binding_mismatch"
        if witness_kind == "estimand_binding_refusal"
        else "acquire_data:value_panel_data_missing"
        if row_addressable
        else "value_world_model_record_unwired"
    )
    source = "l1_dcat_variable_availability" if row_addressable else "cgf_grounding_coverage"
    route_owner = {
        "owner_content_hash": "sha256:" + "a" * 64,
        "owner_schema": "policyos.runtime.acquisition_requirement_gap.v1",
        "planner_report_content_hash": "sha256:" + "b" * 64,
        "requirement_gap_id": gap_id,
    }
    witness = {
        "kind": witness_kind,
        "candidate_ref": candidate_ref,
        (
            "grounding_route" if witness_kind == "estimand_binding_refusal" else "acquisition_route"
        ): route_owner,
    }
    metadata: dict[str, Any] = {
        "source": source,
        "candidate_binding": {
            "candidate_id": candidate_ref,
            "design_problem_ref": "sha256:" + "c" * 64,
        },
    }
    if row_addressable:
        metadata["availability"] = {
            "variable_id": variable,
            "observation_count": 0,
            "metric_binding_count": 0,
            "dataset_count": 0,
            "status": "unavailable",
            "coverage_ref": f"repo://catalog#variable/{variable}",
        }
    data_need_spec = {
        "requirement_gap_id": gap_id,
        "gap_type": "data_snapshot_release",
        "requirement_family": "data_requirement",
        "missing_requirement_fields": missing_fields,
        "producer_output_ref": f"repo://catalog#variable/{variable}",
        "metadata": metadata,
    }
    acquisition_record = {
        "gap_id": gap_id,
        "gap_type": "data_snapshot_release",
        "requirement_family": "data_requirement",
        "missing_requirement_fields": missing_fields,
        "recommended_strategy": "production_snapshot_build",
        "producer_expected": "data_forge.snapshot",
    }
    return {
        "domain_role": f"domain-{route_suffix}",
        "raw_request": "A neutral request with no classifier authority.",
        "design_problem": {
            "outcome_of_interest": {
                "metric_id": demanded_variable,
                "target_variable": demanded_variable,
            },
            "objectives": [{"metric_id": demanded_variable}],
            "candidate_lever_space": {"candidate_levers": [{"target_slot": demanded_variable}]},
        },
        "evidence_witness": witness,
        "terminal": {
            "blocking_obligations": [blocker],
            "data_need_spec": data_need_spec,
            "costed_plan": {
                "canonical_planner_report": {"acquisition_records": [acquisition_record]}
            },
        },
    }


def _upstream_demand_payloads() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    route = _route_run(
        witness_kind="owner_acquisition_route",
        demanded_variable="outcome_metric",
        route_suffix="renamed",
    )
    route["domain_role"] = "renamed_domain"
    route["design_problem"] = {
        "outcome_of_interest": {
            "metric_id": "outcome_metric",
            "target_variable": "outcome_target",
        },
        "objectives": [{"metric_id": "objective_metric"}],
        "candidate_lever_space": {"candidate_levers": [{"target_slot": "lever_target"}]},
    }
    capstone = {
        "domain_runs": {
            "renamed_route": route,
        }
    }
    intervention_substrate = {
        "measured_coverage": {
            "world_slot": {"details": [{"target_world_slots": ["world.slot", "world.other"]}]}
        }
    }
    value_gate = {
        "transport_component_proofs": {
            "renamed_proof": {"selection_nodes": [{"target_variable": "transport_target"}]}
        }
    }
    return capstone, intervention_substrate, value_gate


def test_reverse_demand_projection_is_generic_and_content_bound() -> None:
    census = _census()
    capstone, intervention_substrate, value_gate = _upstream_demand_payloads()

    projection = census.extract_reverse_demand_projection(
        capstone=capstone,
        intervention_substrate=intervention_substrate,
        value_gate=value_gate,
        capstone_source="capstone.json",
        intervention_substrate_source="l6.json",
        value_gate_source="value.json",
    )

    assert tuple(row.variable_id for row in projection.demands) == (
        "lever_target",
        "objective_metric",
        "outcome_metric",
        "outcome_target",
        "transport_target",
        "world.other",
        "world.slot",
    )
    assert projection.demands[0].demand_sources == (
        "capstone.domain_runs.renamed_route.design_problem."
        "candidate_lever_space.candidate_levers[0].target_slot",
    )
    assert tuple(binding.projection_id for binding in projection.projection_bindings) == (
        "capstone_cycle_demands",
        "intervention_substrate_world_slots",
        "value_gate_target_requirements",
    )

    changed = dict(value_gate)
    changed["transport_component_proofs"] = {
        "new_key": {"selection_nodes": [{"target_variable": "novel_transport_target"}]}
    }
    changed_projection = census.extract_reverse_demand_projection(
        capstone=capstone,
        intervention_substrate=intervention_substrate,
        value_gate=changed,
        capstone_source="capstone.json",
        intervention_substrate_source="l6.json",
        value_gate_source="value.json",
    )

    assert "novel_transport_target" in {row.variable_id for row in changed_projection.demands}
    assert (
        projection.projection_bindings[-1].projection_content_sha256
        != changed_projection.projection_bindings[-1].projection_content_sha256
    )


def test_reverse_demand_measurement_keeps_supported_rows_and_typed_residuals(
    catalog_path: Path,
) -> None:
    census = _census()
    capstone, intervention_substrate, value_gate = _upstream_demand_payloads()
    capstone["domain_runs"]["renamed_route"]["design_problem"]["outcome_of_interest"][
        "metric_id"
    ] = "metric_alpha"
    capstone["domain_runs"]["renamed_route"]["design_problem"]["objectives"] = [
        {"metric_id": "metric_beta"}
    ]
    connection = duckdb.connect(str(catalog_path))
    _insert_owner_rows(
        connection,
        suffix="o",
        connector_id="family.alpha",
        execution_tier="catalog",
        raw_variable="raw-catalog-only",
    )
    connection.execute(
        """
        INSERT INTO ds_metric_bindings VALUES
            ('catalog_only_metric', 'dataset-o', 'distribution-o', 'family.alpha',
             'profile-o', 'request-o', 0.4, 0.4, '{}', 'catalog', 'fixture')
        """
    )
    capstone["domain_runs"]["renamed_route"]["design_problem"]["outcome_of_interest"][
        "target_variable"
    ] = "catalog_only_metric"
    connection.close()
    projection = census.extract_reverse_demand_projection(
        capstone=capstone,
        intervention_substrate=intervention_substrate,
        value_gate=value_gate,
        capstone_source="capstone.json",
        intervention_substrate_source="l6.json",
        value_gate_source="value.json",
    )

    rows = census.measure_reverse_demand(catalog_path, projection.demands)
    by_variable = {row.variable_id: row for row in rows}
    residuals = census.reverse_demand_residuals(rows)

    assert len(rows) == len(projection.demands)
    assert by_variable["metric_alpha"].gap_kind is None
    assert by_variable["metric_alpha"].executable_binding_count == 2
    assert by_variable["catalog_only_metric"].gap_kind is census.DemandGapKind.CONNECTOR
    assert by_variable["catalog_only_metric"].binding_tier_counts == {"catalog": 1}
    assert by_variable["metric_beta"].gap_kind is census.DemandGapKind.CONNECTOR
    assert by_variable["lever_target"].gap_kind is census.DemandGapKind.BINDING
    assert {row.variable_id for row in residuals} == {
        row.variable_id for row in rows if row.gap_kind is not None
    }


def test_reverse_demand_projection_rejects_denominator_shrink() -> None:
    census = _census()
    capstone, intervention_substrate, value_gate = _upstream_demand_payloads()
    del capstone["domain_runs"]["renamed_route"]["design_problem"]["outcome_of_interest"][
        "metric_id"
    ]

    with pytest.raises(census.CatalogContractError) as exc_info:
        census.extract_reverse_demand_projection(
            capstone=capstone,
            intervention_substrate=intervention_substrate,
            value_gate=value_gate,
            capstone_source="capstone.json",
            intervention_substrate_source="l6.json",
            value_gate_source="value.json",
        )

    assert exc_info.value.code == "demand_projection_missing_field"


def test_checker_accepts_external_upstream_artifact_paths(
    catalog_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    checker = import_module("tools.quality.validation.check_layer3_gy_n13a_acquisition_census")
    capstone, intervention_substrate, value_gate = _upstream_demand_payloads()
    artifact_payloads = {
        "external-capstone.json": capstone,
        "external-l6.json": intervention_substrate,
        "external-value.json": value_gate,
    }
    for filename, payload in artifact_payloads.items():
        (tmp_path / filename).write_text(json.dumps(payload), encoding="utf-8")

    exit_code = checker.main(
        [
            "--catalog-path",
            str(catalog_path),
            "--capstone-path",
            str(tmp_path / "external-capstone.json"),
            "--intervention-substrate-path",
            str(tmp_path / "external-l6.json"),
            "--value-gate-path",
            str(tmp_path / "external-value.json"),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert [
        row["source_artifact"] for row in payload["reverse_demand_summary"]["projection_bindings"]
    ] == [
        "external://external-capstone.json",
        "external://external-l6.json",
        "external://external-value.json",
    ]
    assert payload["route_summary"]["denominator_count"] == 1
    assert payload["route_summary"]["counts"] == {"not_a_data_gap": 1}
    assert payload["fetch_plan_summary"]["sample_count"] == 1
    assert payload["fetch_plan_summary"]["plan_count"] == 1
    assert payload["fetch_plan_summary"]["preview_calls"] == 0
    assert payload["fetch_plan_summary"]["execute_calls"] == 0
    assert (
        payload["route_summary"]["projection_binding"]["source_artifact"]
        == "external://external-capstone.json"
    )


def test_production_metric_resolution_partition_when_catalog_is_declared() -> None:
    catalog_value = os.environ.get("POLISYOS_N13A_PRODUCTION_CATALOG")
    if not catalog_value:
        pytest.skip("set POLISYOS_N13A_PRODUCTION_CATALOG for the read-only census witness")
    census = _census()

    catalog_path = Path(catalog_value)
    rows = census.derive_metric_resolutions(catalog_path)
    connection = duckdb.connect(str(catalog_path), read_only=True)
    try:
        metric_ids = tuple(
            str(row[0])
            for row in connection.execute(
                """
                SELECT DISTINCT metric_id
                FROM ds_metric_bindings
                ORDER BY metric_id
                """
            ).fetchall()
        )
        columns = {
            (str(table_name), str(column_name))
            for table_name, column_name in connection.execute(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_name IN ('ds_metric_bindings', 'ds_observations')
                """
            ).fetchall()
        }
        field_bound = ("ds_metric_bindings", "raw_variable") in columns and (
            "ds_observations",
            "distribution_id",
        ) in columns
        if field_bound:
            exact_query = """
                SELECT DISTINCT binding.metric_id
                FROM ds_metric_bindings AS binding
                JOIN ds_observations AS observed
                  ON observed.dataset_id = binding.dataset_id
                 AND observed.distribution_id = binding.distribution_id
                 AND observed.raw_variable = binding.raw_variable
                 AND observed.canonical_var = binding.metric_id
            """
            alignment_query = """
                SELECT DISTINCT binding.metric_id
                FROM ds_metric_bindings AS binding
                JOIN ds_variable_alignments AS aligned
                  ON aligned.dataset_id = binding.dataset_id
                 AND aligned.raw_variable = binding.raw_variable
                 AND aligned.canonical_var = binding.metric_id
            """
        else:
            exact_query = """
                SELECT DISTINCT binding.metric_id
                FROM ds_metric_bindings AS binding
                JOIN ds_observations AS observed
                  ON observed.dataset_id = binding.dataset_id
                 AND observed.canonical_var = binding.metric_id
            """
            alignment_query = """
                SELECT DISTINCT binding.metric_id
                FROM ds_metric_bindings AS binding
                JOIN ds_variable_alignments AS aligned
                  ON aligned.dataset_id = binding.dataset_id
                 AND aligned.canonical_var = binding.metric_id
            """
        exact_ids = {str(row[0]) for row in connection.execute(exact_query).fetchall()}
        alignment_ids = {str(row[0]) for row in connection.execute(alignment_query).fetchall()}
    finally:
        connection.close()

    expected_counts = Counter(
        census.ResolutionStatus.EXACT
        if metric_id in exact_ids
        else census.ResolutionStatus.VIA_ALIGNMENT
        if metric_id in alignment_ids
        else census.ResolutionStatus.UNRESOLVED
        for metric_id in metric_ids
    )
    expected_scope = (
        census.ResolutionScope.DISTRIBUTION_FIELD_BOUND
        if field_bound
        else census.ResolutionScope.DATASET_LEVEL_IDENTITY
    )

    assert tuple(row.metric_id for row in rows) == metric_ids
    assert Counter(row.resolution_status for row in rows) == expected_counts
    assert all(row.resolution_scope is expected_scope for row in rows)
    assert all(
        row.limitations
        == (
            (census.ResolutionLimitation.CATALOG_BINDING_FIELD_EDGE_MISSING,)
            if expected_scope is census.ResolutionScope.DATASET_LEVEL_IDENTITY
            and row.resolution_status is not census.ResolutionStatus.UNRESOLVED
            else ()
        )
        for row in rows
    )


def _route_projection(census: Any, runs: dict[str, dict[str, Any]]) -> Any:
    return census.extract_route_projection(
        capstone={"domain_runs": runs},
        capstone_source="architecture/policy_design_case/capstone.json",
    )


def test_route_projection_and_classes_are_generic_over_all_domain_runs(
    catalog_path: Path,
) -> None:
    census = _census()
    runs = {
        "method_route": _route_run(
            witness_kind="estimand_binding_refusal",
            demanded_variable="metric_alpha",
            route_suffix="method",
        ),
        "structural_route": _route_run(
            witness_kind="owner_acquisition_route",
            demanded_variable="metric_alpha",
            route_suffix="structural",
        ),
        "row_route": _route_run(
            witness_kind="owner_data_gap",
            demanded_variable="metric_alpha",
            gap_variable="metric_alpha",
            route_suffix="row",
        ),
    }

    projection = _route_projection(census, runs)
    evidence = census.measure_route_evidence(catalog_path, projection)
    by_id = {row.route.route_id: row for row in evidence}

    assert tuple(row.route_id for row in projection.routes) == (
        "method_route",
        "row_route",
        "structural_route",
    )
    assert projection.projection_binding.projected_item_count == len(runs)
    assert by_id["method_route"].route_class is census.RouteClass.NOT_A_DATA_GAP
    assert by_id["structural_route"].route_class is census.RouteClass.NOT_A_DATA_GAP
    assert by_id["row_route"].route_class is census.RouteClass.LOCAL_LIFT
    assert by_id["method_route"].declared_supply.binding_count == 2
    assert by_id["method_route"].declared_supply.executable_binding_count == 2
    assert by_id["method_route"].declared_supply.local_observation_count == 1
    assert by_id["method_route"].row_addressable_supply is None
    assert by_id["row_route"].row_addressable_supply is not None


def test_route_classifier_ignores_role_names_and_stale_hypothesis_prose(
    catalog_path: Path,
) -> None:
    census = _census()
    original_run = _route_run(
        witness_kind="owner_acquisition_route",
        demanded_variable="metric_alpha",
        route_suffix="original",
    )
    original = _route_projection(census, {"opaque-a": original_run})
    original_class = census.measure_route_evidence(catalog_path, original)[0].route_class

    renamed_run = copy.deepcopy(original_run)
    renamed_run["domain_role"] = "water_quality_hypothesis_is_stale"
    renamed_run["raw_request"] = (
        "This prose says unseen water quality, but prose is not route evidence."
    )
    renamed = _route_projection(census, {"totally-renamed": renamed_run})
    renamed_class = census.measure_route_evidence(catalog_path, renamed)[0].route_class

    stale_prose_only = copy.deepcopy(original_run)
    stale_prose_only["raw_request"] = "unseen water quality WHO Eurostat"
    stale_projection = _route_projection(census, {"opaque-a": stale_prose_only})

    assert original_class is census.RouteClass.NOT_A_DATA_GAP
    assert renamed_class is original_class
    assert (
        stale_projection.projection_binding.projection_content_sha256
        == original.projection_binding.projection_content_sha256
    )


def test_owner_data_gap_precedence_is_local_then_live_then_unresolved(
    catalog_path: Path,
) -> None:
    census = _census()
    connection = duckdb.connect(str(catalog_path))
    _insert_owner_rows(
        connection,
        suffix="live",
        connector_id="family.live",
        execution_tier="fetchable",
        raw_variable="raw-live",
    )
    connection.execute(
        """
        INSERT INTO ds_metric_bindings VALUES
            ('metric_live', 'dataset-live', 'distribution-live', 'family.live',
             'profile-live', 'request-live', 0.8, 0.8, '{}', 'fetchable', 'fixture')
        """
    )
    connection.close()
    projection = _route_projection(
        census,
        {
            "local": _route_run(
                witness_kind="owner_data_gap",
                demanded_variable="metric_alpha",
                gap_variable="metric_alpha",
                route_suffix="local",
            ),
            "live": _route_run(
                witness_kind="owner_data_gap",
                demanded_variable="metric_live",
                gap_variable="metric_live",
                route_suffix="live",
            ),
            "neither": _route_run(
                witness_kind="owner_data_gap",
                demanded_variable="metric_missing",
                gap_variable="metric_missing",
                route_suffix="neither",
            ),
        },
    )

    by_id = {
        row.route.route_id: row for row in census.measure_route_evidence(catalog_path, projection)
    }

    assert by_id["local"].route_class is census.RouteClass.LOCAL_LIFT
    assert by_id["live"].route_class is census.RouteClass.LIVE_FETCHABLE
    assert by_id["neither"].route_class is census.RouteClass.UNRESOLVED


def test_owner_data_gap_decisive_source_flips_change_the_recomputed_class(
    catalog_path: Path,
) -> None:
    census = _census()
    projection = _route_projection(
        census,
        {
            "route": _route_run(
                witness_kind="owner_data_gap",
                demanded_variable="metric_alpha",
                gap_variable="metric_alpha",
            )
        },
    )

    local = census.measure_route_evidence(catalog_path, projection)[0]
    connection = duckdb.connect(str(catalog_path))
    connection.execute("DELETE FROM ds_observations WHERE canonical_var = 'metric_alpha'")
    connection.close()
    live = census.measure_route_evidence(catalog_path, projection)[0]
    connection = duckdb.connect(str(catalog_path))
    connection.execute(
        "UPDATE ds_metric_bindings SET execution_tier = 'catalog' WHERE metric_id = 'metric_alpha'"
    )
    connection.execute(
        "UPDATE ds_datasets SET execution_tier = 'catalog' WHERE id IN ('dataset-a', 'dataset-b')"
    )
    connection.close()
    unresolved = census.measure_route_evidence(catalog_path, projection)[0]

    assert local.route_class is census.RouteClass.LOCAL_LIFT
    assert live.route_class is census.RouteClass.LIVE_FETCHABLE
    assert unresolved.route_class is census.RouteClass.UNRESOLVED


def test_structural_route_does_not_become_a_data_gap_when_rows_are_added(
    catalog_path: Path,
) -> None:
    census = _census()
    projection = _route_projection(
        census,
        {
            "route": _route_run(
                witness_kind="owner_acquisition_route",
                demanded_variable="new_structural_metric",
            )
        },
    )
    before = census.measure_route_evidence(catalog_path, projection)[0]
    connection = duckdb.connect(str(catalog_path))
    _insert_owner_rows(
        connection,
        suffix="structural",
        connector_id="family.structural",
        execution_tier="transport_ready",
        raw_variable="raw-structural",
    )
    connection.execute(
        """
        INSERT INTO ds_metric_bindings VALUES
            ('new_structural_metric', 'dataset-structural',
             'distribution-structural', 'family.structural', 'profile-structural',
             'request-structural', 0.9, 0.9, '{}', 'transport_ready', 'fixture')
        """
    )
    connection.execute(
        """
        INSERT INTO ds_observations VALUES
            ('observation-structural', 'dataset-structural', 'raw-structural',
             'new_structural_metric')
        """
    )
    connection.close()
    after = census.measure_route_evidence(catalog_path, projection)[0]

    assert before.route_class is census.RouteClass.NOT_A_DATA_GAP
    assert after.route_class is census.RouteClass.NOT_A_DATA_GAP
    assert before.declared_supply.local_observation_count == 0
    assert after.declared_supply.local_observation_count == 1


@pytest.mark.parametrize(
    "mutation",
    [
        "gap_id_mismatch",
        "missing_availability_owner",
        "missing_variable_mismatch",
    ],
)
def test_owner_data_gap_fails_closed_without_coherent_owner_evidence(
    mutation: str,
) -> None:
    census = _census()
    run = _route_run(
        witness_kind="owner_data_gap",
        demanded_variable="metric_alpha",
        gap_variable="metric_alpha",
    )
    if mutation == "gap_id_mismatch":
        run["evidence_witness"]["acquisition_route"]["requirement_gap_id"] = "requirement-gap:fake"
    elif mutation == "missing_availability_owner":
        del run["terminal"]["data_need_spec"]["metadata"]["availability"]
    else:
        run["terminal"]["data_need_spec"]["missing_requirement_fields"] = [
            "canonical_variable_observations:some_other_metric"
        ]

    with pytest.raises(census.CatalogContractError):
        _route_projection(census, {"route": run})


def test_route_class_label_is_rejected_when_it_disagrees_with_evidence(
    catalog_path: Path,
) -> None:
    census = _census()
    projection = _route_projection(
        census,
        {
            "route": _route_run(
                witness_kind="owner_data_gap",
                demanded_variable="metric_alpha",
                gap_variable="metric_alpha",
            )
        },
    )
    evidence = census.measure_route_evidence(catalog_path, projection)[0]
    pinned = evidence.model_dump(mode="json")
    pinned["route_class"] = census.RouteClass.LIVE_FETCHABLE.value

    with pytest.raises(ValidationError):
        census.RouteEvidence.model_validate(pinned)


@pytest.mark.skipif(
    not os.environ.get("POLISYOS_N13A_PRODUCTION_CATALOG"),
    reason="production catalog is an explicit read-only witness",
)
def test_actual_capstone_route_classes_recompute_from_owner_evidence() -> None:
    census = _census()
    catalog_path = Path(os.environ["POLISYOS_N13A_PRODUCTION_CATALOG"])
    capstone_path = (
        Path(__file__).resolve().parents[3]
        / "architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json"
    )
    capstone = json.loads(capstone_path.read_text(encoding="utf-8"))
    projection = census.read_route_projection(
        capstone_path=capstone_path,
        capstone_source="architecture/policy_design_case/"
        "layer3_gy_depth_n_universality_contract.json",
    )
    rows = census.measure_route_evidence(catalog_path, projection)

    assert len(rows) == len(capstone["domain_runs"])
    assert {row.route.route_id: row.route.witness_kind for row in rows} == {
        route_id: run["evidence_witness"]["kind"]
        for route_id, run in capstone["domain_runs"].items()
    }
    assert all(
        row.route_class is census.RouteClass.NOT_A_DATA_GAP
        for row in rows
        if row.route.witness_kind != "owner_data_gap"
    )


def _fixture_route_evidence(census: Any, catalog_path: Path) -> tuple[Any, ...]:
    projection = _route_projection(
        census,
        {
            "opaque-route": _route_run(
                witness_kind="owner_acquisition_route",
                demanded_variable="metric_alpha",
            )
        },
    )
    return census.measure_route_evidence(catalog_path, projection)


def test_real_catalog_owner_generates_fetch_plan_proofs_without_execution(
    catalog_path: Path,
    tmp_path: Path,
) -> None:
    census = _census()
    resolutions = census.derive_metric_resolutions(catalog_path)
    route_rows = _fixture_route_evidence(census, catalog_path)

    proof = census.generate_fetch_plan_proofs(
        catalog_path,
        metric_resolutions=resolutions,
        route_evidence=route_rows,
        scratch_dir=tmp_path / "plan-only",
        source_locator="fixture/catalog.duckdb",
    )

    assert proof.capability_status == "implemented_but_not_orchestrated"
    assert proof.sample_binding.projected_item_count == len(proof.sample_rows)
    assert len(proof.plans) == len(proof.sample_rows)
    assert {row.metric_id for row in proof.sample_rows} == {"metric_alpha"}
    plan = proof.plans[0]
    assert plan.metric_id == "metric_alpha"
    assert plan.connector_id == "family.alpha"
    assert plan.catalog_dataset_id == "dataset-a"
    assert plan.distribution_id == "distribution-a"
    assert plan.request_dataset_id == "request-a"
    assert plan.profile_id == "profile-a"
    assert plan.execution_tier == "transport_ready"
    assert plan.source_lane == "catalog"
    assert plan.persist_payload is False
    assert proof.execution_fence.preview_calls == 0
    assert proof.execution_fence.execute_calls == 0
    assert proof.execution_fence.catalog_content_before_sha256 == (
        proof.execution_fence.catalog_content_after_sha256
    )
    assert proof.execution_fence.scratch_tree_before_sha256 == (
        proof.execution_fence.scratch_tree_after_sha256
    )


def test_fetch_plan_sample_grows_from_a_new_owner_family_without_code_changes(
    catalog_path: Path,
    tmp_path: Path,
) -> None:
    census = _census()
    connection = duckdb.connect(str(catalog_path))
    _insert_owner_rows(
        connection,
        suffix="plan",
        connector_id="family.plan",
        execution_tier="transport_ready",
        raw_variable="raw-plan",
    )
    connection.execute(
        """
        INSERT INTO ds_metric_bindings VALUES
            ('metric_plan', 'dataset-plan', 'distribution-plan', 'family.plan',
             'profile-plan', 'request-plan', 0.95, 0.95, '{}',
             'transport_ready', 'fixture')
        """
    )
    connection.execute(
        """
        INSERT INTO ds_observations VALUES
            ('observation-plan', 'dataset-plan', 'raw-plan', 'metric_plan')
        """
    )
    connection.close()

    proof = census.generate_fetch_plan_proofs(
        catalog_path,
        metric_resolutions=census.derive_metric_resolutions(catalog_path),
        route_evidence=_fixture_route_evidence(census, catalog_path),
        scratch_dir=tmp_path / "plan-growth",
        source_locator="fixture/catalog.duckdb",
    )
    by_metric = {row.metric_id: row for row in proof.sample_rows}

    assert "metric_plan" in by_metric
    assert "primary_connector:family.plan" in by_metric["metric_plan"].selection_reasons
    assert any(
        plan.metric_id == "metric_plan" and plan.connector_id == "family.plan"
        for plan in proof.plans
    )


def test_fetch_plan_execution_attempt_is_hard_red(
    catalog_path: Path,
    tmp_path: Path,
) -> None:
    census = _census()

    class MaliciousService:
        def __init__(self, *, executor: Any, **_: Any) -> None:
            self.executor = executor

        def _resolve_via_catalog(self, _: list[Any]) -> tuple[list[Any], list[Any]]:
            self.executor.preview(None)
            raise AssertionError("the forbidden executor must raise first")

    with pytest.raises(census.CensusExecutionFenceError) as exc_info:
        census.generate_fetch_plan_proofs(
            catalog_path,
            metric_resolutions=census.derive_metric_resolutions(catalog_path),
            route_evidence=_fixture_route_evidence(census, catalog_path),
            scratch_dir=tmp_path / "malicious-plan",
            source_locator="fixture/catalog.duckdb",
            _service_factory=MaliciousService,
        )

    assert exc_info.value.code == "fetch_plan_execution_forbidden"


def test_fetch_plan_proof_models_reject_executable_or_unearned_claims() -> None:
    census = _census()
    plan = {
        "plan_id": "plan-a",
        "metric_id": "metric-a",
        "selection_reasons": ("capstone_route:route-a",),
        "connector_id": "family.alpha",
        "catalog_dataset_id": "dataset-a",
        "distribution_id": "distribution-a",
        "request_dataset_id": "request-a",
        "profile_id": "profile-a",
        "filters": {},
        "execution_tier": "transport_ready",
        "source_lane": "catalog",
        "persist_payload": False,
        "owner_type": "polisyos.core.contracts.control.FetchPlan",
    }

    with pytest.raises(ValidationError):
        census.FetchPlanProjection(**{**plan, "persist_payload": True})
    with pytest.raises(ValidationError):
        census.FetchPlanProjection(**{**plan, "execution_tier": "catalog"})
    with pytest.raises(ValidationError):
        census.FetchPlanExecutionFence(
            preview_calls=1,
            execute_calls=0,
            catalog_resolution_calls=1,
            expected_catalog_resolution_calls=1,
            catalog_content_before_sha256="sha256:" + "a" * 64,
            catalog_content_after_sha256="sha256:" + "a" * 64,
            scratch_tree_before_sha256="sha256:" + "b" * 64,
            scratch_tree_after_sha256="sha256:" + "b" * 64,
            forbidden_owners=("FetchExecutor.preview",),
        )


@pytest.mark.skipif(
    not os.environ.get("POLISYOS_N13A_PRODUCTION_CATALOG"),
    reason="production catalog is an explicit read-only witness",
)
def test_production_fetch_plan_generation_uses_real_graph_and_w2_demands(
    tmp_path: Path,
) -> None:
    census = _census()
    catalog_path = Path(os.environ["POLISYOS_N13A_PRODUCTION_CATALOG"])
    capstone_path = (
        Path(__file__).resolve().parents[3]
        / "architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json"
    )
    route_projection = census.read_route_projection(
        capstone_path=capstone_path,
        capstone_source="architecture/policy_design_case/"
        "layer3_gy_depth_n_universality_contract.json",
    )
    route_rows = census.measure_route_evidence(catalog_path, route_projection)
    resolutions = census.derive_metric_resolutions(catalog_path)

    proof = census.generate_fetch_plan_proofs(
        catalog_path,
        metric_resolutions=resolutions,
        route_evidence=route_rows,
        scratch_dir=tmp_path / "production-plan-only",
        source_locator="production_data/catalog.duckdb",
    )
    resolved = {
        row.metric_id: row
        for row in resolutions
        if row.resolution_status is not census.ResolutionStatus.UNRESOLVED
    }
    connection = duckdb.connect(str(catalog_path), read_only=True)
    try:
        demanded_executable = {
            str(row[0])
            for route in route_rows
            for row in connection.execute(
                """
                SELECT DISTINCT metric_id
                FROM ds_metric_bindings
                WHERE metric_id IN (SELECT UNNEST(?))
                  AND execution_tier IN ('fetchable', 'transport_ready')
                """,
                [list(route.route.demanded_metrics)],
            ).fetchall()
            if str(row[0]) in resolved
        }
    finally:
        connection.close()

    sample_metrics = {row.metric_id for row in proof.sample_rows}
    assert demanded_executable <= sample_metrics
    assert len(proof.plans) == len(proof.sample_rows)
    assert proof.execution_fence.catalog_resolution_calls == len(proof.sample_rows)
    assert proof.execution_fence.preview_calls == 0
    assert proof.execution_fence.execute_calls == 0
    assert all(plan.source_lane == "catalog" for plan in proof.plans)
    assert all(plan.persist_payload is False for plan in proof.plans)
