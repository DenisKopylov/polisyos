"""Test-first witnesses for the bounded EMP-01 empirical-value contracts.

The witnesses intentionally exercise owner boundaries rather than asserting
private implementation markers.  They remain candidate-only evidence: this
package does not mint calibration, transport, or publication authority.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import duckdb
import pytest

import polisyos.runtime.quality.generation_cycle as generation_cycle
from polisyos.data_forge import read_api
from polisyos.runtime.quality import cycle_substrate, data_state_substrate, substrate_registry


def _project_value_outer_set(
    *,
    confidence_interval: tuple[float, float],
    forecast_tier: str = "direct",
) -> Any:
    """Project a small estimator report through the live value owner helper."""

    transport = generation_cycle.ValueTransportReceipt(
        status="direct",
        world_model_record_id="world_model_record_emp01",
        world_model_record_content_hash="sha256:" + "a" * 64,
        transport_result_ref="sha256:" + "b" * 64,
        transport_status="identified",
        transport_mode="direct",
        identification_engine="emp01-test-engine",
    )
    calibration = generation_cycle.ValueCalibrationReceipt(
        status="pass",
        forecast_tier=forecast_tier,
        calibration_record_ref="calibration://emp01/test",
        uncertainty_interval_refs=("interval://emp01/test/95",),
    )
    report = SimpleNamespace(
        point_estimate=4.0,
        confidence_interval=confidence_interval,
        method="emp01_test_method",
    )
    return generation_cycle._value_outer_set_from_foundry_result(
        method_result=SimpleNamespace(output={"report": report}),
        transport_receipt=transport,
        calibration_receipt=calibration,
        world_record=SimpleNamespace(
            content_hash="sha256:" + "a" * 64,
            valid_time_scope="2026-Q3",
        ),
        data_trust=generation_cycle.DataTrust(
            tier="emp01_test",
            trust_cap=0.8,
            trust_multiplier=0.8,
            min_coverage=0.0,
            max_coverage=1.0,
            promotion_floor=0.0,
            authority_ref="repo://emp01/test-trust",
        ),
    )


def _seed_emp01_catalog(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    rows: tuple[tuple[Any, ...], ...],
    *,
    bulk_region_rows: tuple[str, int] | None = None,
) -> Path:
    """Seed the real catalog table consumed by the production DuckDB query."""

    catalog_path = tmp_path / "l1.duckdb"
    with duckdb.connect(str(catalog_path)) as connection:
        connection.execute(
            """
            CREATE TABLE ds_observations (
                observation_id VARCHAR PRIMARY KEY,
                dataset_id VARCHAR NOT NULL,
                raw_variable VARCHAR NOT NULL,
                canonical_var VARCHAR NOT NULL,
                country_code VARCHAR NOT NULL,
                year INTEGER,
                survey_year INTEGER,
                wave INTEGER,
                value DOUBLE,
                condition_json VARCHAR DEFAULT '{}'
            )
            """
        )
        values = [
            (
                observation_id,
                dataset_id,
                "outcome",
                "outcome",
                country_code,
                period,
                None,
                None,
                value,
                condition_json,
            )
            for country_code, period, value, dataset_id, observation_id, condition_json in rows
        ]
        if values:
            connection.executemany(
                "INSERT INTO ds_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                values,
            )
        if bulk_region_rows is not None:
            country_code, row_count = bulk_region_rows
            dataset_id = "dataset-percent" if country_code == "UA" else "dataset-foreign"
            connection.execute(
                """
                INSERT INTO ds_observations
                SELECT
                    'obs-bulk-' || CAST(row_number AS VARCHAR),
                    ?,
                    'outcome',
                    'outcome',
                    ?,
                    CAST(1900 + row_number AS INTEGER),
                    NULL,
                    NULL,
                    CAST(row_number AS DOUBLE),
                    '{"unit":"percent"}'
                FROM range(?) AS generated(row_number)
                """,
                [dataset_id, country_code, row_count],
            )
    monkeypatch.setattr(
        substrate_registry,
        "default_substrate_catalog_paths",
        lambda _repo_root: SimpleNamespace(l1_dcat_path=catalog_path),
    )
    monkeypatch.setattr(
        read_api.catalog,
        "default_acquisition_overlay_path",
        lambda _repo_root: None,
    )
    return catalog_path


def test_scope_is_bound_before_limit_and_ambiguous_units_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Unbound measurement units are refused after applying the geographic scope."""

    rows = (
        ("UA", 2020, 10.0, "dataset-percent", "obs-ua-percent-2020", '{"unit":"percent"}'),
        ("UA", 2020, 1000.0, "dataset-usd", "obs-ua-usd-2020", '{"unit":"usd"}'),
        ("UA", 2021, 11.0, "dataset-percent", "obs-ua-percent-2021", '{"unit":"percent"}'),
        ("UA", 2022, 12.0, "dataset-percent", "obs-ua-percent-2022", '{"unit":"percent"}'),
        ("UA", 2023, 13.0, "dataset-percent", "obs-ua-percent-2023", '{"unit":"percent"}'),
    )
    foreign_row_count = 20_001
    _seed_emp01_catalog(
        monkeypatch,
        tmp_path,
        rows,
        bulk_region_rows=("PL", foreign_row_count),
    )
    monkeypatch.setattr(
        data_state_substrate,
        "l1_dcat_variable_availability",
        lambda *_args, **_kwargs: SimpleNamespace(
            status="available",
            coverage_ref="catalog://emp01/outcome",
            dataset_count=3,
            metric_binding_count=1,
            observation_count=len(rows) + foreign_row_count,
        ),
    )

    candidate = SimpleNamespace(
        atom=SimpleNamespace(target_world_slots=("outcome",)),
    )
    problem = SimpleNamespace(
        outcome_of_interest=SimpleNamespace(target_variable="outcome"),
        jurisdiction_time=SimpleNamespace(region="UA"),
        runtime_hints={},
    )
    with pytest.raises(
        generation_cycle.ValueOwnerAccessError,
        match="measurement-unit-binding",
    ) as exc_info:
        generation_cycle.RealValueOwnerGateway(repo_root=tmp_path).load_value_data_profile(
            candidate=candidate,
            problem=problem,
            world_record=SimpleNamespace(),
        )

    assert exc_info.value.code == "acquire_data:value_owner_unit_binding_ambiguous"


def test_scope_filter_excludes_other_regions_before_profile_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A declared region is applied in the owner query before profile shaping."""

    rows = (
        ("UA", 2020, 10.0, "dataset-percent", "obs-ua-2020", '{"unit":"percent"}'),
        ("UA", 2021, 11.0, "dataset-percent", "obs-ua-2021", '{"unit":"percent"}'),
        ("UA", 2022, 12.0, "dataset-percent", "obs-ua-2022", '{"unit":"percent"}'),
        ("UA", 2023, 13.0, "dataset-percent", "obs-ua-2023", '{"unit":"percent"}'),
    )
    _seed_emp01_catalog(monkeypatch, tmp_path, rows, bulk_region_rows=("PL", 20_001))
    monkeypatch.setattr(
        data_state_substrate,
        "l1_dcat_variable_availability",
        lambda *_args, **_kwargs: SimpleNamespace(
            status="available",
            coverage_ref="catalog://emp01/outcome",
            dataset_count=2,
            metric_binding_count=1,
            observation_count=len(rows) + 20_001,
        ),
    )

    profile = generation_cycle.RealValueOwnerGateway(repo_root=tmp_path).load_value_data_profile(
        candidate=SimpleNamespace(atom=SimpleNamespace(target_world_slots=("outcome",))),
        problem=SimpleNamespace(
            outcome_of_interest=SimpleNamespace(target_variable="outcome"),
            jurisdiction_time=SimpleNamespace(region="UA"),
            runtime_hints={},
        ),
        world_record=SimpleNamespace(),
    )

    assert profile.unit_count == 1
    assert all(row.unit_id == "UA" for row in profile.rows)
    assert all(len(row.source_row_content_hashes) == 1 for row in profile.rows)


def test_cross_period_mixed_dataset_units_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Distinct source identities across periods cannot masquerade as one unit."""

    rows = (
        ("UA", 2020, 10.0, "dataset-percent", "obs-ua-2020", '{"unit":"percent"}'),
        ("UA", 2021, 1000.0, "dataset-usd", "obs-ua-2021", '{"unit":"usd"}'),
        ("UA", 2022, 12.0, "dataset-percent", "obs-ua-2022", '{"unit":"percent"}'),
        ("UA", 2023, 1100.0, "dataset-usd", "obs-ua-2023", '{"unit":"usd"}'),
    )
    _seed_emp01_catalog(monkeypatch, tmp_path, rows)
    monkeypatch.setattr(
        data_state_substrate,
        "l1_dcat_variable_availability",
        lambda *_args, **_kwargs: SimpleNamespace(
            status="available",
            coverage_ref="catalog://emp01/outcome",
            dataset_count=2,
            metric_binding_count=1,
            observation_count=len(rows),
        ),
    )

    with pytest.raises(
        generation_cycle.ValueOwnerAccessError,
        match="measurement-unit-binding",
    ):
        generation_cycle.RealValueOwnerGateway(repo_root=tmp_path).load_value_data_profile(
            candidate=SimpleNamespace(atom=SimpleNamespace(target_world_slots=("outcome",))),
            problem=SimpleNamespace(
                outcome_of_interest=SimpleNamespace(target_variable="outcome"),
                jurisdiction_time=SimpleNamespace(region="UA"),
                runtime_hints={},
            ),
            world_record=SimpleNamespace(),
        )


def test_non_country_region_refuses_country_code_binding(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A basin-like jurisdiction cannot be silently treated as a country."""

    monkeypatch.setattr(
        data_state_substrate,
        "l1_dcat_variable_availability",
        lambda *_args, **_kwargs: SimpleNamespace(
            status="available",
            coverage_ref="catalog://emp01/outcome",
            dataset_count=1,
            metric_binding_count=1,
            observation_count=4,
        ),
    )

    with pytest.raises(
        generation_cycle.ValueOwnerAccessError,
        match="country_code",
    ):
        generation_cycle.RealValueOwnerGateway(repo_root=tmp_path).load_value_data_profile(
            candidate=SimpleNamespace(atom=SimpleNamespace(target_world_slots=("outcome",))),
            problem=SimpleNamespace(
                outcome_of_interest=SimpleNamespace(target_variable="outcome"),
                jurisdiction_time=SimpleNamespace(region="dnieper_basin"),
                runtime_hints={},
            ),
            world_record=SimpleNamespace(),
        )


def test_owner_row_cap_refuses_truncated_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A bounded catalog read never classifies an incomplete owner panel."""

    _seed_emp01_catalog(
        monkeypatch,
        tmp_path,
        (),
        bulk_region_rows=("UA", 20_001),
    )

    with pytest.raises(
        generation_cycle.ValueOwnerAccessError,
        match="row cap",
    ) as exc_info:
        generation_cycle._load_value_data_profile_from_l1_dcat(
            repo_root=tmp_path,
            outcome="outcome",
            owner_access_ref="catalog://emp01/outcome",
            scope_region="UA",
        )

    assert exc_info.value.code == "acquire_data:value_owner_rows_truncated"


def test_empty_selected_profile_returns_no_profile_before_unit_binding(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An empty scoped selection is incomplete, not a unit-binding violation."""

    _seed_emp01_catalog(monkeypatch, tmp_path, ())

    assert (
        generation_cycle._load_value_data_profile_from_l1_dcat(
            repo_root=tmp_path,
            outcome="outcome",
            owner_access_ref="catalog://emp01/outcome",
            scope_region="UA",
        )
        is None
    )


def test_identification_set_and_statistical_uncertainty_remain_separate() -> None:
    """Point identification must not erase a non-zero native statistical interval."""

    value_set = _project_value_outer_set(confidence_interval=(1.0, 10.0))

    assert value_set.identification_status == "point"
    assert value_set.lower == (4.0,)
    assert value_set.upper == (4.0,)
    assert getattr(value_set, "statistical_lower", None) == (1.0,)
    assert getattr(value_set, "statistical_upper", None) == (10.0,)


def test_asymmetric_interval_is_preserved_by_value_projection() -> None:
    """Proxy projection must not replace an asymmetric native interval with a symmetric guess."""

    value_set = _project_value_outer_set(
        confidence_interval=(1.0, 10.0),
        forecast_tier="transported_limited",
    )

    assert value_set.identification_status == "proxy"
    assert value_set.lower == (1.0,)
    assert value_set.upper == (10.0,)
    assert getattr(value_set, "statistical_lower", None) == (1.0,)
    assert getattr(value_set, "statistical_upper", None) == (10.0,)
    assert value_set.lower != (0.0,)


def test_selection_diagram_requires_verified_causal_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Measured context deltas alone cannot establish a verified causal artifact."""

    class _Problem:
        domain = "emp01-domain"
        runtime_hints: ClassVar[dict[str, Any]] = {}

        def model_dump(self, *, mode: str) -> dict[str, str]:
            assert mode == "json"
            return {"problem": "emp01"}

    problem = _Problem()
    world_record = SimpleNamespace(
        world_model_record_id="world_model_record_emp01",
        content_hash="sha256:" + "c" * 64,
    )
    transport_context = SimpleNamespace(
        source_context_id="source",
        target_context_id="target",
        covariates=(
            SimpleNamespace(
                canonical_var="income",
                source_value=1.0,
                target_value=2.0,
                source_row_content_hash="sha256:" + "d" * 64,
                target_row_content_hash="sha256:" + "e" * 64,
            ),
        ),
    )
    bound_context = SimpleNamespace(
        design_problem_ref=generation_cycle.gy_content_hash(problem.model_dump(mode="json")),
        domain=problem.domain,
        world_model_record_content_hash=world_record.content_hash,
        world_model_record=world_record,
        transport_context=transport_context,
        content_hash="sha256:" + "f" * 64,
    )
    monkeypatch.setattr(
        cycle_substrate,
        "revalidate_cycle_substrate_context",
        lambda _context: bound_context,
    )

    with pytest.raises(generation_cycle.ValueOwnerAccessError) as exc_info:
        generation_cycle._build_candidate_selection_diagram(
            candidate=SimpleNamespace(
                candidate_id="emp01-candidate",
                atom=SimpleNamespace(
                    treatment_variable="treatment",
                    target_world_slots=("outcome",),
                ),
            ),
            problem=problem,
            world_record=world_record,
            query_treatment="treatment",
            query_outcome="outcome",
            cycle_substrate_context=SimpleNamespace(),
        )

    assert exc_info.value.code == "acquire_data:causal_graph_artifact_unresolved"


def test_raw_graph_without_artifact_bridge_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raw graph hints cannot cross the generation-cycle boundary unverified."""

    class _Problem:
        domain = "emp01-domain"

        def __init__(self, graph_payload: dict[str, Any]) -> None:
            self.runtime_hints = {"causal_graph_model": graph_payload}

        def model_dump(self, *, mode: str) -> dict[str, str]:
            assert mode == "json"
            return {"problem": "emp01"}

    problem_ref = generation_cycle.gy_content_hash({"problem": "emp01"})
    world_record = SimpleNamespace(
        world_model_record_id="world_model_record_emp01",
        content_hash="sha256:" + "c" * 64,
    )
    problem = _Problem(
        {
            "graph_type": "dag",
            "nodes": ["treatment", "outcome", "income"],
            "edges": [
                {
                    "src": "treatment",
                    "dst": "outcome",
                    "mark_src": "tail",
                    "mark_dst": "arrow",
                }
            ],
            "metadata": {
                "design_problem_ref": problem_ref,
                "world_model_record_content_hash": world_record.content_hash,
            },
        }
    )
    transport_context = SimpleNamespace(
        source_context_id="source",
        target_context_id="target",
        covariates=(
            SimpleNamespace(
                canonical_var="income",
                source_value=1.0,
                target_value=2.0,
                source_row_content_hash="sha256:" + "d" * 64,
                target_row_content_hash="sha256:" + "e" * 64,
            ),
        ),
    )
    bound_context = SimpleNamespace(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        world_model_record_content_hash=world_record.content_hash,
        world_model_record=world_record,
        transport_context=transport_context,
        content_hash="sha256:" + "e" * 64,
    )
    monkeypatch.setattr(
        cycle_substrate,
        "revalidate_cycle_substrate_context",
        lambda _context: bound_context,
    )

    with pytest.raises(generation_cycle.ValueOwnerAccessError) as exc_info:
        generation_cycle._build_candidate_selection_diagram(
            candidate=SimpleNamespace(
                candidate_id="emp01-candidate",
                atom=SimpleNamespace(
                    treatment_variable="treatment",
                    target_world_slots=("outcome",),
                ),
            ),
            problem=problem,
            world_record=world_record,
            query_treatment="treatment",
            query_outcome="outcome",
            cycle_substrate_context=SimpleNamespace(),
        )

    assert exc_info.value.code == "acquire_data:causal_graph_artifact_unresolved"
