"""Test-first witnesses for the bounded EMP-01 empirical-value contracts.

The witnesses intentionally exercise owner boundaries rather than asserting
private implementation markers.  They remain candidate-only evidence: this
package does not mint calibration, transport, or publication authority.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

import polisyos.runtime.quality.generation_cycle as generation_cycle
from polisyos.data_forge import read_api
from polisyos.runtime.quality import cycle_substrate, data_state_substrate, substrate_registry
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState


def _project_value_outer_set(
    *,
    confidence_interval: tuple[float, float],
    point_estimate: Any = 4.0,
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
        point_estimate=point_estimate,
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


def _seed_synthetic_baseline_identity(catalog_path: Path) -> None:
    """Build a bounded C baseline-only state with no active epochs or passports."""

    catalog_path.write_bytes(b"emp01 synthetic baseline-only fixture")
    state = read_api.catalog.project_catalog_acquisition_state(
        catalog_path,
        overlay_path=None,
    )
    assert state.overlay_exists is False
    assert state.epochs == ()
    assert state.passports == ()


class _RowsCursor:
    description = tuple(
        (name,)
        for name in (
            "unit_id",
            "period_id",
            "value",
            "dataset_id",
            "observation_id",
            "condition_json",
        )
    )

    def __init__(self, rows: tuple[tuple[Any, ...], ...]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._rows)


class _RowsConnection:
    def __init__(self, rows: tuple[tuple[Any, ...], ...]) -> None:
        self._rows = rows
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def execute(self, statement: str, parameters: Any = None) -> _RowsCursor:
        self.calls.append((statement, tuple(parameters or ())))
        rows = self._rows
        if "country_code = CAST(? AS VARCHAR)" in statement:
            selected_parameters = tuple(parameters or ())
            scope_region = (
                selected_parameters[3]
                if len(selected_parameters) > 3
                else selected_parameters[1]
            )
            rows = tuple(row for row in rows if row[0] == scope_region)
        return _RowsCursor(rows)

    def close(self) -> None:
        return None


def test_scope_is_bound_before_limit_and_ambiguous_units_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Unbound measurement units are refused after applying the geographic scope."""

    catalog_path = tmp_path / "l1.duckdb"
    _seed_synthetic_baseline_identity(catalog_path)
    rows = (
        ("UA", 2020, 10.0, "dataset-percent", "obs-ua-percent-2020", '{"unit":"percent"}'),
        ("UA", 2020, 1000.0, "dataset-usd", "obs-ua-usd-2020", '{"unit":"usd"}'),
        ("UA", 2021, 11.0, "dataset-percent", "obs-ua-percent-2021", '{"unit":"percent"}'),
        ("UA", 2022, 12.0, "dataset-percent", "obs-ua-percent-2022", '{"unit":"percent"}'),
        ("UA", 2023, 13.0, "dataset-percent", "obs-ua-percent-2023", '{"unit":"percent"}'),
        ("PL", 2020, 99.0, "dataset-foreign", "obs-pl-2020", '{"unit":"percent"}'),
        ("PL", 2021, 98.0, "dataset-foreign", "obs-pl-2021", '{"unit":"percent"}'),
    )
    connection = _RowsConnection(rows)

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
    monkeypatch.setattr(
        read_api.catalog,
        "open_catalog_read_session",
        lambda _path, overlay_path=None: connection,
    )
    monkeypatch.setattr(
        data_state_substrate,
        "l1_dcat_variable_availability",
        lambda *_args, **_kwargs: SimpleNamespace(
            status="available",
            coverage_ref="catalog://emp01/outcome",
            dataset_count=3,
            metric_binding_count=1,
            observation_count=len(rows),
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
    ):
        generation_cycle.RealValueOwnerGateway(repo_root=tmp_path).load_value_data_profile(
            candidate=candidate,
            problem=problem,
            world_record=SimpleNamespace(),
        )

    assert connection.calls
    assert connection.calls[0][1][0] == "outcome"
    statement = connection.calls[0][0]
    assert statement.index("country_code = CAST(? AS VARCHAR)") < statement.index("LIMIT")
    assert connection.calls[0][1][3] == "UA"


def test_scope_filter_excludes_other_regions_before_profile_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A declared region is applied in the owner query before profile shaping."""

    catalog_path = tmp_path / "l1.duckdb"
    _seed_synthetic_baseline_identity(catalog_path)
    rows = (
        ("UA", 2020, 10.0, "dataset-percent", "obs-ua-2020", '{"unit":"percent"}'),
        ("UA", 2021, 11.0, "dataset-percent", "obs-ua-2021", '{"unit":"percent"}'),
        ("UA", 2022, 12.0, "dataset-percent", "obs-ua-2022", '{"unit":"percent"}'),
        ("UA", 2023, 13.0, "dataset-percent", "obs-ua-2023", '{"unit":"percent"}'),
        ("PL", 2020, 99.0, "dataset-foreign", "obs-pl-2020", '{"unit":"percent"}'),
        ("PL", 2021, 98.0, "dataset-foreign", "obs-pl-2021", '{"unit":"percent"}'),
        ("PL", 2022, 97.0, "dataset-foreign", "obs-pl-2022", '{"unit":"percent"}'),
        ("PL", 2023, 96.0, "dataset-foreign", "obs-pl-2023", '{"unit":"percent"}'),
    )
    connection = _RowsConnection(rows)

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
    monkeypatch.setattr(
        read_api.catalog,
        "open_catalog_read_session",
        lambda _path, overlay_path=None: connection,
    )
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
    assert connection.calls
    assert connection.calls[0][1][0] == "outcome"
    assert connection.calls[0][1][3] == "UA"


def test_cross_period_mixed_dataset_units_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Distinct source identities across periods cannot masquerade as one unit."""

    catalog_path = tmp_path / "l1.duckdb"
    _seed_synthetic_baseline_identity(catalog_path)
    rows = (
        ("UA", 2020, 10.0, "dataset-percent", "obs-ua-2020", '{"unit":"percent"}'),
        ("UA", 2021, 1000.0, "dataset-usd", "obs-ua-2021", '{"unit":"usd"}'),
        ("UA", 2022, 12.0, "dataset-percent", "obs-ua-2022", '{"unit":"percent"}'),
        ("UA", 2023, 1100.0, "dataset-usd", "obs-ua-2023", '{"unit":"usd"}'),
    )
    connection = _RowsConnection(rows)

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
    monkeypatch.setattr(
        read_api.catalog,
        "open_catalog_read_session",
        lambda _path, overlay_path=None: connection,
    )
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

    catalog_path = tmp_path / "l1.duckdb"
    _seed_synthetic_baseline_identity(catalog_path)
    rows = tuple(
        ("UA", 2000 + index, float(index), "dataset-percent", f"obs-{index}", '{"unit":"percent"}')
        for index in range(20_001)
    )
    connection = _RowsConnection(rows)
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
    monkeypatch.setattr(
        read_api.catalog,
        "open_catalog_read_session",
        lambda _path, overlay_path=None: connection,
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
    assert connection.calls
    assert "LIMIT ?" in connection.calls[0][0]
    assert connection.calls[0][1][-1] == 20_001


def test_empty_selected_profile_returns_no_profile_before_unit_binding(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An empty synthetic baseline-only selection remains distinct from insufficient."""

    catalog_path = tmp_path / "l1.duckdb"
    _seed_synthetic_baseline_identity(catalog_path)
    connection = _RowsConnection(())
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
    monkeypatch.setattr(
        read_api.catalog,
        "open_catalog_read_session",
        lambda _path, overlay_path=None: connection,
    )

    assert (
        generation_cycle._load_value_data_profile_from_l1_dcat(
            repo_root=tmp_path,
            outcome="outcome",
            owner_access_ref="catalog://emp01/outcome",
            scope_region="UA",
        )
        is None
    )

    monkeypatch.setattr(
        data_state_substrate,
        "l1_dcat_variable_availability",
        lambda *_args, **_kwargs: SimpleNamespace(
            status="available",
            coverage_ref="catalog://emp01/outcome",
            dataset_count=1,
            metric_binding_count=1,
            observation_count=0,
        ),
    )
    with pytest.raises(generation_cycle.ValueOwnerAccessError) as exc_info:
        generation_cycle.RealValueOwnerGateway(repo_root=tmp_path).load_value_data_profile(
            candidate=SimpleNamespace(
                atom=SimpleNamespace(target_world_slots=("outcome",)),
            ),
            problem=SimpleNamespace(
                outcome_of_interest=SimpleNamespace(target_variable="outcome"),
                jurisdiction_time=SimpleNamespace(region="UA"),
                runtime_hints={},
            ),
            world_record=SimpleNamespace(),
        )
    assert exc_info.value.code == "acquire_data:value_owner_rows_missing"


@pytest.mark.parametrize("row_count", [1, 2, 3])
def test_nonempty_under_four_profile_is_insufficient_at_loader_and_gateway(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    row_count: int,
) -> None:
    """Synthetic baseline rows 1–3 are insufficient, distinct from empty and truncated."""

    catalog_path = tmp_path / "l1.duckdb"
    _seed_synthetic_baseline_identity(catalog_path)
    rows = tuple(
        (
            "UA",
            2020 + index,
            10.0 + index,
            "dataset-ratio",
            f"obs-ua-{2020 + index}",
            '{"unit":"ratio"}',
        )
        for index in range(row_count)
    )
    connection = _RowsConnection(rows)
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
    monkeypatch.setattr(
        read_api.catalog,
        "open_catalog_read_session",
        lambda _path, overlay_path=None: connection,
    )
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

    loader_kwargs = {
        "repo_root": tmp_path,
        "outcome": "outcome",
        "owner_access_ref": "catalog://emp01/outcome",
        "scope_region": "UA",
    }
    with pytest.raises(generation_cycle.ValueOwnerAccessError) as loader_exc_info:
        generation_cycle._load_value_data_profile_from_l1_dcat(**loader_kwargs)
    assert loader_exc_info.value.code == "acquire_data:value_owner_rows_insufficient"

    with pytest.raises(generation_cycle.ValueOwnerAccessError) as exc_info:
        generation_cycle.RealValueOwnerGateway(repo_root=tmp_path).load_value_data_profile(
            candidate=SimpleNamespace(
                atom=SimpleNamespace(target_world_slots=("outcome",)),
            ),
            problem=SimpleNamespace(
                outcome_of_interest=SimpleNamespace(target_variable="outcome"),
                jurisdiction_time=SimpleNamespace(region="UA"),
                runtime_hints={},
            ),
            world_record=SimpleNamespace(),
        )

    assert exc_info.value.code == "acquire_data:value_owner_rows_insufficient"
    assert len(connection.calls) == 2
    assert all("LIMIT ?" in statement for statement, _ in connection.calls)
    assert all(parameters[-1] == 20_001 for _, parameters in connection.calls)
    assert all(parameters[0] == "outcome" for _, parameters in connection.calls)
    assert all(parameters[3] == "UA" for _, parameters in connection.calls)


@pytest.mark.parametrize("row_count", [1, 2, 3])
@pytest.mark.asyncio
async def test_default_cycle_value_refusal_survives_persisted_run_readback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    row_count: int,
) -> None:
    """The default N8 owner path persists a sparse-profile refusal after real N5."""

    from polisyos.core.security.tenant_context import tenant_scope
    from tests.unit.runtime.quality.test_generation_cycle import (
        _owner_program_graph_n5_witness,
        _problem,
    )

    problem = _problem("emp01_sparse_profile_cycle").model_copy(
        update={"problem_statement": "Synthetic EMP01 fixture; no policy claim."}
    )
    witness = _owner_program_graph_n5_witness(
        tmp_path / "n5",
        income_values=(1000.0, 2000.0),
        problem_seed=problem,
    )
    problem = witness.problem
    try:
        outcome = problem.outcome_of_interest.target_variable
        catalog_path = tmp_path / "l1.duckdb"
        _seed_synthetic_baseline_identity(catalog_path)
        # These baseline-only rows test the four-row floor, not an empirical panel.
        rows = tuple(
            (
                "UA",
                2020 + index,
                10.0 + index,
                "dataset-ratio",
                f"obs-ua-{2020 + index}",
                '{"unit":"ratio"}',
            )
            for index in range(row_count)
        )
        connection = _RowsConnection(rows)
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
        monkeypatch.setattr(
            read_api.catalog,
            "open_catalog_read_session",
            lambda _path, overlay_path=None: connection,
        )
        monkeypatch.setattr(
            data_state_substrate,
            "l1_dcat_variable_availability",
            lambda *_args, **_kwargs: SimpleNamespace(
                status="available",
                coverage_ref=f"catalog://emp01/{outcome}",
                dataset_count=1,
                metric_binding_count=1,
                observation_count=row_count,
            ),
        )

        class _FixtureGenerationPort:
            async def __call__(self, _problem: Any, *, cycle_index: int) -> Any:
                assert cycle_index == 0
                candidate = witness.candidate
                return SimpleNamespace(
                    status="generated",
                    candidates=(candidate,),
                    surrogate_rankings=(
                        SimpleNamespace(
                            candidate_id=candidate.candidate_id,
                            score=0.9,
                            voi_estimate=10.0,
                        ),
                    ),
                    grounding_dispositions=(),
                )

        class _FixtureGroundingPort:
            def __call__(self, *, candidate: Any, **_kwargs: Any) -> Any:
                return generation_cycle.CandidateGroundingObservation(
                    candidate_id=str(candidate.candidate_id),
                    status="grounded_shadow",
                    grounding_score=0.8,
                    current_valid=False,
                    grounding_source="cgf_firewall",
                    grounding_disposition="synthetic_test_only",
                    report_ref="synthetic-fixture://emp01/grounding",
                )

        class _FixturePromotionPort:
            def __call__(self, **_kwargs: Any) -> Any:
                return generation_cycle.PromotionPortObservation(
                    status="not_promoted",
                    reason="synthetic_emp01_test_only",
                )

        controller = generation_cycle.GenerationCycleController(
            generation_port=_FixtureGenerationPort(),
            grounding_port=_FixtureGroundingPort(),
            promotion_port=_FixturePromotionPort(),
            repo_root=tmp_path,
            cycle_substrate_context=witness.context,
            artifact_store=witness.store,
            authority_scope="contract_testing",
        )
        assert isinstance(controller._simulation_port, generation_cycle.JointSimulationPort)
        assert isinstance(
            controller._value_port,
            generation_cycle._DefaultSimulationBoundFoundryValuePort,
        )
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            run = await controller.run(
                problem,
                budget_state=BudgetState(
                    limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
                ),
                min_cycles=1,
                max_cycles=1,
            )

        simulation = run.cycles[-1].simulation
        assert simulation.status == "joint_simulated"
        assert simulation.simulation_ref is not None
        assert simulation.simulation_result_ref is not None
        assert witness.store.verify(simulation.simulation_result_ref.artifact_id).ok

        expected_reason = (
            f"selected owner profile has {row_count} usable rows; at least 4 are required "
            f"owner_access_ref=catalog://emp01/{outcome}#selected-row-count"
        )
        assert run.value_port.status == "value_blocked", run.value_port.model_dump(
            mode="json"
        )
        assert run.value_port.authority_blockers == (
            "acquire_data:value_owner_rows_insufficient",
        ), run.value_port.model_dump(mode="json")
        assert run.value_port.reason == expected_reason
        assert run.value_port.acquisition_requirement is None
        assert run.cycles[-1].value_port.status == "value_blocked"
        assert run.cycles[-1].value_port.authority_blockers == (
            "acquire_data:value_owner_rows_insufficient",
        )
        assert run.cycles[-1].value_port.reason == expected_reason
        assert run.cycles[-1].value_port.acquisition_requirement is None
        assert len(connection.calls) == 1
        assert "LIMIT ?" in connection.calls[0][0]
        assert connection.calls[0][1][-1] == 20_001

        persisted_path = tmp_path / "generation-cycle-run.json"
        persisted_path.write_text(
            json.dumps(run.model_dump(mode="json"), sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        persisted = json.loads(persisted_path.read_text(encoding="utf-8"))
        restored = generation_cycle.GenerationCycleRun.from_persisted_payload(persisted)
        assert restored.value_port.reason == expected_reason
        assert restored.value_port.authority_blockers == (
            "acquire_data:value_owner_rows_insufficient",
        )
        assert restored.value_port.acquisition_requirement is None
        assert restored.cycles[-1].value_port.reason == expected_reason
        assert restored.cycles[-1].value_port.authority_blockers == (
            "acquire_data:value_owner_rows_insufficient",
        )
        assert restored.cycles[-1].value_port.acquisition_requirement is None
        assert generation_cycle.validate_generation_cycle_run_history(persisted) == ()

        tampered = json.loads(persisted_path.read_text(encoding="utf-8"))
        tampered["value_port"]["reason"] = "owner rows are sufficient"
        assert generation_cycle.validate_generation_cycle_run_history(tampered)
    finally:
        witness.store.close()


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
