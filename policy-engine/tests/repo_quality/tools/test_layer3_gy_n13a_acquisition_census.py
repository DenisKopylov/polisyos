from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

import duckdb
import pytest
from pydantic import ValidationError


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
            quality_score DOUBLE
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
            access_license VARCHAR,
            access_auth_required BOOLEAN,
            execution_tier VARCHAR
        )
        """
    )
    connection.close()
    return path


def _census() -> Any:
    return import_module(
        "tools.quality.validation.layer3_gy_n13a_acquisition_census"
    )


def test_census_boundary_models_are_strict() -> None:
    census = _census()

    boundary_models = (
        census.CatalogIdentity,
        census.AlignmentCandidate,
        census.MetricResolution,
        census.ReverseDemandResidual,
        census.RouteEvidence,
        census.FetchPlanProjection,
        census.ProbeBudget,
        census.SchemaProfileContract,
        census.ProbeRequest,
        census.ProbeRawResponse,
        census.DerivedLiveness,
        census.FamilyScorecard,
        census.GrowthBacklogRow,
        census.ProjectionBinding,
        census.CensusManifest,
    )

    assert all(
        model.model_json_schema().get("additionalProperties") is False
        for model in boundary_models
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
            route_id="route-a",
            demanded_metrics=("metric-a",),
            local_observation_count=0,
            binding_tier_counts={"catalog": -1},
            alignment_count=0,
            planner_gap_kind="relation_gap",
            planner_strategy_kind="acquire",
            blocker_codes=(),
            missing_link="missing relation",
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
        canonical_variable="canonical-a",
        confidence=0.9,
        is_proxy=False,
        proxy_penalty=0.0,
        method="owner",
        evidence="fixture",
    )


def test_metric_resolution_enforces_status_evidence_algebra() -> None:
    census = _census()
    candidate = _alignment_candidate(census)

    exact = census.MetricResolution(
        metric_id="metric-a",
        resolution_status=census.ResolutionStatus.EXACT,
        binding_count=1,
        exact_canonical_variable="metric-a",
    )
    aligned = census.MetricResolution(
        metric_id="metric-b",
        resolution_status=census.ResolutionStatus.VIA_ALIGNMENT,
        binding_count=1,
        best_alignment=candidate,
        alignment_candidates=(candidate,),
    )
    unresolved = census.MetricResolution(
        metric_id="metric-c",
        resolution_status=census.ResolutionStatus.UNRESOLVED,
        binding_count=1,
    )

    assert exact.exact_canonical_variable == "metric-a"
    assert aligned.best_alignment == candidate
    assert unresolved.best_alignment is None

    invalid_rows = (
        {
            "metric_id": "metric-a",
            "resolution_status": census.ResolutionStatus.EXACT,
            "binding_count": 1,
        },
        {
            "metric_id": "metric-b",
            "resolution_status": census.ResolutionStatus.VIA_ALIGNMENT,
            "binding_count": 1,
        },
        {
            "metric_id": "metric-c",
            "resolution_status": census.ResolutionStatus.UNRESOLVED,
            "binding_count": 1,
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
