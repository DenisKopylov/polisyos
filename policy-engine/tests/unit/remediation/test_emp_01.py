"""Test-first witnesses for the bounded EMP-01 empirical-value contracts.

The witnesses intentionally exercise owner boundaries rather than asserting
private implementation markers.  They remain candidate-only evidence: this
package does not mint calibration, transport, or publication authority.
"""

from __future__ import annotations

from dataclasses import replace
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


def _candidate_transport_context_without_graph() -> cycle_substrate.TransportContextEvidence:
    """Build the valid optional-graph shape emitted by the typed context owner."""

    return cycle_substrate.TransportContextEvidence(
        status="candidate_context_only_not_transport_authority",
        source_context_id="source",
        target_context_id="target",
        source_profile_content_hash="sha256:" + "a" * 64,
        target_profile_content_hash="sha256:" + "b" * 64,
        substrate_input_content_hash="sha256:" + "c" * 64,
        context_binding_hash="sha256:" + "f" * 64,
        covariates=(
            cycle_substrate.TransportCovariateObservation(
                canonical_var="income",
                source_value=1.0,
                target_value=2.0,
                source_row_content_hash="sha256:" + "d" * 64,
                target_row_content_hash="sha256:" + "e" * 64,
            ),
        ),
    )


def _emp01_transport_context(
    *,
    problem: Any,
    base_context: Any,
    graph_ref: Any | None,
) -> cycle_substrate.CycleSubstrateContext:
    """Bind an optional selected graph through the existing cycle-context owner."""

    problem_ref = (
        cycle_substrate.cycle_job_design_problem_ref(problem)
        if graph_ref is not None
        else generation_cycle.gy_content_hash(problem.model_dump(mode="json"))
    )
    source_profile_hash = (
        base_context.source_profile.content_hash
        if base_context.source_profile is not None
        else None
    )
    context_binding_hash = cycle_substrate.cycle_substrate_context_binding_hash(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        substrate_input_content_hash=base_context.substrate_input_content_hash,
        substrate_registry_content_hash=base_context.substrate_registry.content_hash,
        world_model_record_id=base_context.world_model_record.world_model_record_id,
        world_model_record_content_hash=base_context.world_model_record.content_hash,
        world_model_record_authority_status=base_context.world_model_record.authority_status,
        selected_registry_entry_hashes=base_context.selected_registry_entry_hashes,
        source_profile_content_hash=source_profile_hash,
    )
    transport = cycle_substrate.TransportContextEvidence(
        status="candidate_context_only_not_transport_authority",
        source_context_id="controlled-source",
        target_context_id="controlled-target",
        source_profile_content_hash="sha256:" + "1" * 64,
        target_profile_content_hash="sha256:" + "2" * 64,
        substrate_input_content_hash=base_context.substrate_input_content_hash,
        context_binding_hash=context_binding_hash,
        covariates=(
            cycle_substrate.TransportCovariateObservation(
                canonical_var="income",
                source_value=1.0,
                target_value=2.0,
                source_row_content_hash="sha256:" + "3" * 64,
                target_row_content_hash="sha256:" + "4" * 64,
            ),
        ),
        causal_graph_ref=graph_ref,
    )
    return cycle_substrate.build_cycle_substrate_context(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        substrate_registry=base_context.substrate_registry,
        selected_registry_entry_hashes=base_context.selected_registry_entry_hashes,
        world_model_record=base_context.world_model_record,
        intervention_substrate=base_context.intervention_substrate,
        candidate_levers=base_context.candidate_levers,
        transport_context=transport,
        source_pack_content_hash=base_context.source_pack_content_hash,
        substrate_input_content_hash=base_context.substrate_input_content_hash,
        source_profile=base_context.source_profile,
    )


def _selected_profile_transport_case(tmp_path: Path) -> tuple[Any, ...]:
    """Build a controlled candidate-only graph/CAS/context chain for EMP-01."""

    from polisyos.core.artifacts import FileSystemCAS, ensure_ir_artifact_store
    from polisyos.ir.analytics.causal_graph import (
        CausalEdge,
        CausalGraphModel,
        GraphType,
        persist_causal_graph_model,
    )
    from tests._helpers.controlled_candidate_profile import (
        _controlled_profile_cycle_basis,
    )
    from tests._helpers.controlled_candidate_profile import (
        _problem as controlled_problem,
    )

    problem, base_context = _controlled_profile_cycle_basis(
        controlled_problem("emp01_selected_graph_transport")
    )
    store = FileSystemCAS(tmp_path / "selected-graph-cas")
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["tax_rate", "income", "firm_survival"],
        edges=[
            CausalEdge(src="tax_rate", dst="income"),
            CausalEdge(src="income", dst="firm_survival"),
        ],
        discovery_method="controlled_transport_algorithm_fixture",
    )
    graph_ref = persist_causal_graph_model(
        ensure_ir_artifact_store(store),
        graph,
        return_selected_profile=True,
    )
    context = _emp01_transport_context(
        problem=problem,
        base_context=base_context,
        graph_ref=graph_ref,
    )
    candidate = SimpleNamespace(
        candidate_id="emp01_selected_graph_candidate",
        atom=SimpleNamespace(
            treatment_variable="tax_rate",
            target_world_slots=("firm_survival",),
            content_hash=generation_cycle.gy_content_hash(
                {"fixture": "emp01_selected_graph_candidate"}
            ),
        ),
    )
    return problem, base_context, context, candidate, store, graph, graph_ref


def test_selected_profile_graph_reaches_fresh_candidate_transport_receipt(
    tmp_path: Path,
) -> None:
    """A real selected graph traverses CAS, run basis, fresh replay, and receipt."""

    problem, base_context, context, candidate, store, graph, graph_ref = (
        _selected_profile_transport_case(tmp_path)
    )
    world_record = base_context.world_model_record
    gateway = generation_cycle.RealValueOwnerGateway(
        cycle_substrate_context=context,
        artifact_store=store,
    )

    receipt, refusal = gateway.run_transport(
        candidate=candidate,
        problem=problem,
        world_record=world_record,
        solver_mode="simplified",
    )

    assert refusal is None
    assert isinstance(receipt, generation_cycle.ValueTransportRunReceiptV1)
    assert receipt.status == "transported_limited"
    assert receipt.transport_status == "identified"
    assert receipt.transport_mode == "transport_formula"
    assert receipt.transport_run_basis_ref.manifest_profile_sha256 is not None
    assert context.authority_purpose == "cycle_input_candidate_only"
    assert context.transport_context is not None
    assert context.transport_context.causal_graph_ref == graph_ref

    basis, request, stored_diagram, result = generation_cycle._resolve_value_transport_run_basis(
        store=store,
        run_basis_ref=receipt.transport_run_basis_ref,
        candidate=candidate,
        problem=problem,
        cycle_substrate_context=context,
        world_record=world_record,
    )
    assert request.solver_mode == basis.solver_mode == "simplified"
    assert request.authority_scope == "candidate_fixture_only"
    assert request.production_value_eligible is False
    assert basis.selected_graph_ref.model_dump(mode="json") == graph_ref.model_dump(mode="json")
    assert stored_diagram.base_graph.model_dump(mode="json") == graph.model_dump(mode="json")
    assert [
        (node.target_variable, node.source_value, node.target_value)
        for node in stored_diagram.s_nodes
    ] == [("income", 1.0, 2.0)]
    assert result.status.value == receipt.transport_status
    assert result.transport_mode.value == receipt.transport_mode


def test_fresh_transport_admission_refuses_removed_or_substituted_graph(
    tmp_path: Path,
) -> None:
    """Missing, replaced, or absent-in-CAS graphs never reuse a receipt."""

    from polisyos.core.artifacts import FileSystemCAS

    problem, base_context, context, candidate, store, _graph, graph_ref = (
        _selected_profile_transport_case(tmp_path)
    )
    world_record = base_context.world_model_record
    gateway = generation_cycle.RealValueOwnerGateway(
        cycle_substrate_context=context,
        artifact_store=store,
    )
    receipt, refusal = gateway.run_transport(
        candidate=candidate,
        problem=problem,
        world_record=world_record,
        solver_mode="simplified",
    )
    assert refusal is None
    assert receipt is not None

    removed_context = _emp01_transport_context(
        problem=problem,
        base_context=base_context,
        graph_ref=None,
    )
    with pytest.raises(ValueError, match="transport_run_basis_binding_mismatch"):
        generation_cycle._resolve_value_transport_run_basis(
            store=store,
            run_basis_ref=receipt.transport_run_basis_ref,
            candidate=candidate,
            problem=problem,
            cycle_substrate_context=removed_context,
            world_record=world_record,
        )

    missing_store = FileSystemCAS(tmp_path / "removed-graph-cas")
    missing_graph_gateway = generation_cycle.RealValueOwnerGateway(
        cycle_substrate_context=context,
        artifact_store=missing_store,
    )
    with pytest.raises(generation_cycle.ValueOwnerAccessError) as missing_graph:
        missing_graph_gateway.build_transport_inputs(
            candidate=candidate,
            problem=problem,
            world_record=world_record,
        )
    assert missing_graph.value.code == "acquire_data:causal_graph_artifact_unresolved"

    wrong_profile_ref = graph_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "0" * 64}
    )
    wrong_profile_context = _emp01_transport_context(
        problem=problem,
        base_context=base_context,
        graph_ref=wrong_profile_ref,
    )
    wrong_profile_gateway = generation_cycle.RealValueOwnerGateway(
        cycle_substrate_context=wrong_profile_context,
        artifact_store=store,
    )
    with pytest.raises(generation_cycle.ValueOwnerAccessError) as wrong_profile:
        wrong_profile_gateway.build_transport_inputs(
            candidate=candidate,
            problem=problem,
            world_record=world_record,
        )
    assert wrong_profile.value.code == "acquire_data:causal_graph_artifact_unresolved"


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
    original_paths = substrate_registry.default_substrate_catalog_paths
    fixture_root = tmp_path.resolve()

    def fixture_paths(
        repo_root: Path,
        *,
        source_owner_root: Path | None = None,
    ) -> substrate_registry.SubstrateCatalogPaths:
        paths = original_paths(repo_root, source_owner_root=source_owner_root)
        selected_owner = (
            Path(source_owner_root).resolve() if source_owner_root is not None else None
        )
        if Path(repo_root).resolve() != fixture_root:
            return paths
        if selected_owner is not None and selected_owner != fixture_root:
            return paths
        return replace(paths, l1_dcat_path=catalog_path)

    monkeypatch.setattr(substrate_registry, "default_substrate_catalog_paths", fixture_paths)
    monkeypatch.setattr(
        read_api.catalog,
        "default_acquisition_overlay_path",
        lambda _repo_root: None,
    )
    return catalog_path


def test_emp01_catalog_fixture_preserves_the_selected_data_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A foreign physical owner cannot be silently replaced by the EMP01 fixture."""
    original_paths = substrate_registry.default_substrate_catalog_paths
    fixture_path = _seed_emp01_catalog(monkeypatch, tmp_path, ())
    for selected_owner in (None, tmp_path):
        paths = substrate_registry.default_substrate_catalog_paths(
            tmp_path, source_owner_root=selected_owner
        )
        assert isinstance(paths, substrate_registry.SubstrateCatalogPaths)
        assert paths == replace(
            original_paths(tmp_path, source_owner_root=selected_owner), l1_dcat_path=fixture_path
        )
    foreign_owner = tmp_path / "foreign-selected-data-owner"
    foreign_owner.mkdir()
    observed = substrate_registry.default_substrate_catalog_paths(
        tmp_path, source_owner_root=foreign_owner
    )
    assert observed == original_paths(tmp_path, source_owner_root=foreign_owner)
    assert observed.l1_dcat_path.is_relative_to(foreign_owner)
    assert observed.l1_dcat_path != fixture_path


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


def test_scope_change_selects_distinct_input_identity_with_equal_summaries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Actual Catalog rows follow scope even when shape, values and labels agree."""
    from polisyos.pdc import gy_content_hash

    periods = (2020, 2021, 2022, 2023)
    values = (10.0, 11.0, 12.0, 13.0)
    rows = tuple(
        (
            region,
            period,
            value,
            "dataset-percent",
            f"obs-{region}-{period}",
            '{"unit":"percent"}',
        )
        for region in ("UA", "PL")
        for period, value in zip(periods, values, strict=True)
    )
    _seed_emp01_catalog(monkeypatch, tmp_path, rows)
    monkeypatch.setattr(
        data_state_substrate,
        "l1_dcat_variable_availability",
        lambda *_args, **_kwargs: SimpleNamespace(
            status="available",
            coverage_ref="catalog://emp01/outcome",
            dataset_count=1,
            metric_binding_count=1,
            observation_count=len(rows),
        ),
    )
    candidate = SimpleNamespace(atom=SimpleNamespace(target_world_slots=("outcome",)))
    gateway = generation_cycle.RealValueOwnerGateway(repo_root=tmp_path)
    profiles = {
        region: gateway.load_value_data_profile(
            candidate=candidate,
            problem=SimpleNamespace(
                outcome_of_interest=SimpleNamespace(target_variable="outcome"),
                jurisdiction_time=SimpleNamespace(region=region),
                runtime_hints={},
            ),
            world_record=SimpleNamespace(),
        )
        for region in ("UA", "PL")
    }
    for region, profile in profiles.items():
        assert tuple(
            (row.unit_id, row.period_id, row.outcome_value, row.measurement_unit)
            for row in profile.rows
        ) == tuple(
            (region, period, value, "percent")
            for period, value in zip(periods, values, strict=True)
        )
        expected_source_hashes = {
            gy_content_hash(
                {
                    "outcome": "outcome",
                    "unit_id": region,
                    "period_id": period,
                    "value": value,
                    "dataset_id": "dataset-percent",
                    "observation_id": f"obs-{region}-{period}",
                    "measurement_unit": "percent",
                }
            )
            for period, value in zip(periods, values, strict=True)
        }
        assert {
            source_hash for row in profile.rows for source_hash in row.source_row_content_hashes
        } == expected_source_hashes
    assert profiles["UA"].outcome == profiles["PL"].outcome == "outcome"
    assert profiles["UA"].measurement_unit == profiles["PL"].measurement_unit == "percent"
    assert profiles["UA"].available_data_modalities == profiles["PL"].available_data_modalities
    assert profiles["UA"].owner_row_count == profiles["PL"].owner_row_count == 4
    assert profiles["UA"].period_count == profiles["PL"].period_count == 4
    assert profiles["UA"].content_hash != profiles["PL"].content_hash
    assert profiles["UA"].owner_rows_content_hash != profiles["PL"].owner_rows_content_hash


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


def test_report_only_interval_requires_owner_run_basis() -> None:
    """A method report alone cannot separate identification from sampling uncertainty."""

    with pytest.raises(
        ValueError, match="foundry_method_refused_value:owner_method_run_basis_missing"
    ):
        _project_value_outer_set(confidence_interval=(1.0, 10.0))


def test_unbound_asymmetric_interval_cannot_use_transport_receipt_as_run_basis() -> None:
    """A transport receipt does not bind an otherwise unowned estimator report."""

    with pytest.raises(
        ValueError, match="foundry_method_refused_value:owner_method_run_basis_missing"
    ):
        _project_value_outer_set(
            confidence_interval=(1.0, 10.0),
            forecast_tier="transported_limited",
        )


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
    transport_context = _candidate_transport_context_without_graph()
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
    transport_context = _candidate_transport_context_without_graph()
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
