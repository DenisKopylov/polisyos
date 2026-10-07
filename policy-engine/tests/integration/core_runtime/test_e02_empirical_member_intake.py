"""End-to-end C member admission into A's empirical owner profile."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import duckdb
import pytest

from polisyos.data_forge.domains.catalog.knowledge.overlay import (
    ActivatedAcquisitionObservationProjection,
    CanonicalAcquisitionObservation,
)
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.runtime.quality import (
    data_state_substrate,
    substrate_registry,
)
from polisyos.runtime.quality import (
    generation_cycle as generation_cycle_module,
)
from polisyos.runtime.quality.generation_cycle import (
    FoundryValuePort,
    RealValueOwnerGateway,
    ValueOwnerAccessError,
    gy_content_hash,
)
from tests.unit.data_forge.domains.catalog.knowledge.test_overlay import (
    _scenario_with_raw_rows,
)
from tests.unit.runtime.quality.test_acquisition_executor import (
    _activate_real_epoch_scenario,
)


def _activate_scenario(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rows: list[dict[str, object]],
) -> tuple[Any, ActivatedAcquisitionObservationProjection]:
    """Build, admit, activate, and read a genuine C projection for A."""
    scenario = _scenario_with_raw_rows(tmp_path, monkeypatch, rows)
    _production, activated = _activate_real_epoch_scenario(scenario)
    projection = scenario.overlay.read_activated_semantic_epoch_observations(
        receipt_ref=activated.receipt_ref,
        artifact_store=scenario.store,
        passport=scenario.passport,
        authority=scenario.authority,
    )
    paths = SimpleNamespace(l1_dcat_path=scenario.authority.baseline_path)
    monkeypatch.setattr(
        data_state_substrate,
        "default_substrate_catalog_paths",
        lambda _repo_root: paths,
    )
    monkeypatch.setattr(
        substrate_registry,
        "default_substrate_catalog_paths",
        lambda _repo_root: paths,
    )
    return scenario, projection


def _four_ratio_rows() -> list[dict[str, object]]:
    return [
        {
            "country_code": "UA",
            "year": year,
            "distress_score": value,
            "condition_json": {"unit": "ratio"},
        }
        for year, value in ((2021, 0.42), (2022, 0.51), (2023, 0.47), (2024, 0.56))
    ]


def _activate_four_row_scenario(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Any, ActivatedAcquisitionObservationProjection]:
    """Build and activate the genuine four-row positive control."""
    scenario, projection = _activate_scenario(tmp_path, monkeypatch, _four_ratio_rows())
    assert len(projection.observations) == 4
    return scenario, projection


def _seed_baseline_nonmembers_before_authority_freeze(
    monkeypatch: pytest.MonkeyPatch,
    *,
    row_count: int,
    years: tuple[int, ...] | None = None,
) -> None:
    """Seed visible epoch-zero rows before the fixture hashes its baseline."""
    if years is not None and len(years) != row_count:
        raise ValueError("baseline_seed_year_denominator_mismatch")
    builder = catalog_read_api.build_slice0_fixture_catalog_graph
    rows = [
        (
            f"baseline-nonmember-{index:05d}",
            "acquisition.local.corrected_firm_panels",
            "distress_score",
            "cells.distress_score",
            "UA",
            years[index] if years is not None else 2024,
            None,
            None,
            0.99,
            json.dumps({"unit": "ratio"}),
        )
        for index in range(row_count)
    ]

    def build_fixture_with_baseline_nonmembers(graph_root: str | Path | None = None) -> object:
        if graph_root is None:
            raise AssertionError("this fixture path requires an isolated catalog root")
        root = Path(graph_root)
        graph = builder(graph_root)
        graph.close()
        baseline_path = root / "catalog.duckdb"
        con = duckdb.connect(str(baseline_path))
        try:
            con.executemany(
                "INSERT INTO ds_observations "
                "(observation_id, dataset_id, raw_variable, canonical_var, country_code, "
                "year, survey_year, wave, value, condition_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        finally:
            con.close()
        # _authority closes the returned graph after this hook. Reopen it only after
        # seeding so that its single close releases the live post-seed catalog handle.
        return type(graph)(db_path=baseline_path, index_dir=root)

    monkeypatch.setattr(
        catalog_read_api,
        "build_slice0_fixture_catalog_graph",
        build_fixture_with_baseline_nonmembers,
    )


def _disable_exact_projection_member_query_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the real owner function with only its exact-ID SQL gate disabled."""
    function_name = "_load_value_data_profile_from_l1_dcat"
    original = getattr(generation_cycle_module, function_name)
    source = inspect.getsource(original)
    needle = "observation_projection is not None,\n            list(selected_projection_ids),"
    replacement = "False,\n            list(selected_projection_ids),"
    assert source.count(needle) == 1
    counterfactual_source = source.replace(needle, replacement, 1)
    counterfactual_module = "from __future__ import annotations\n" + counterfactual_source
    namespace = generation_cycle_module.__dict__.copy()
    exec(  # noqa: S102 - controlled source mutation probes the live SQL gate in memory.
        compile(
            counterfactual_module,
            inspect.getsourcefile(original) or "<generation_cycle>",
            "exec",
        ),
        namespace,
    )
    counterfactual = namespace[function_name]
    assert inspect.signature(counterfactual) == inspect.signature(original)
    monkeypatch.setattr(generation_cycle_module, function_name, counterfactual)


def _load_through_default_root_gateway(
    scenario: Any,
    projection: ActivatedAcquisitionObservationProjection | None,
) -> Any:
    """Exercise the root's actual default RealValueOwnerGateway and row loader."""
    outcome = scenario.passport.variable_id
    root_port = FoundryValuePort(
        evaluation_context=None,  # type: ignore[arg-type]  # This test targets the owner bridge.
        repo_root=scenario.authority.repo_root,
        catalog_overlay_path=scenario.overlay.overlay_path,
        artifact_store=scenario.store,
        activated_observation_projection=projection,
    )
    assert isinstance(root_port._owner_gateway, RealValueOwnerGateway)
    candidate = SimpleNamespace(atom=SimpleNamespace(target_world_slots=(outcome,)))
    problem = SimpleNamespace(
        outcome_of_interest=SimpleNamespace(target_variable=outcome),
        jurisdiction_time=SimpleNamespace(region="UA"),
    )
    return root_port._owner_gateway.load_value_data_profile(
        candidate=candidate,
        problem=problem,  # type: ignore[arg-type]
        world_record=object(),  # The profile query does not derive periods from WMR.
    )


def _load_through_default_controller_gateway(
    scenario: Any,
    projection: ActivatedAcquisitionObservationProjection,
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    """Exercise the controller-owned default wrapper and its real C-backed gateway."""
    outcome = scenario.passport.variable_id
    captured_init: list[dict[str, Any]] = []
    real_foundry_port = generation_cycle_module.FoundryValuePort

    class CapturingFoundryValuePort:
        def __init__(self, **kwargs: Any) -> None:
            captured_init.append(kwargs)
            self._delegate = real_foundry_port(**kwargs)

        def __call__(self, **kwargs: Any) -> Any:
            # Keep the controller and default wrapper real. Invoke the real owner
            # gateway directly so this focused test does not claim an N8 value
            # result from its synthetic N5 fixture.
            return self._delegate._owner_gateway.load_value_data_profile(
                candidate=kwargs["candidate"],
                problem=kwargs["problem"],
                world_record=object(),
            )

    monkeypatch.setattr(
        generation_cycle_module,
        "FoundryValuePort",
        CapturingFoundryValuePort,
    )
    monkeypatch.setattr(
        generation_cycle_module,
        "simulation_value_execution_context",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(
        catalog_read_api,
        "default_acquisition_overlay_path",
        lambda _repo_root: scenario.overlay.overlay_path,
    )
    controller = generation_cycle_module.GenerationCycleController(
        repo_root=scenario.authority.repo_root,
        artifact_store=scenario.store,
        activated_observation_projection=projection,
        authority_scope="contract_testing",
    )
    default_value_port = controller._value_port
    assert isinstance(
        default_value_port,
        generation_cycle_module._DefaultSimulationBoundFoundryValuePort,
    )
    candidate = SimpleNamespace(
        candidate_id="candidate_e02_empirical_controller",
        atom=SimpleNamespace(target_world_slots=(outcome,)),
    )
    problem = SimpleNamespace(
        outcome_of_interest=SimpleNamespace(target_variable=outcome),
        jurisdiction_time=SimpleNamespace(region="UA"),
    )
    simulation = generation_cycle_module.SimulationPortObservation(
        candidate_id=candidate.candidate_id,
        status="simulation_pending_n5",
    )
    profile = default_value_port(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )
    assert len(captured_init) == 1
    assert captured_init[0]["activated_observation_projection"] is projection
    return profile


def _expected_profile_source_hashes(
    outcome: str,
    measurement_unit: str,
    projection: ActivatedAcquisitionObservationProjection,
) -> set[str]:
    return {
        gy_content_hash(
            {
                "outcome": outcome,
                "unit_id": "UA",
                "period_id": int(projected.observation.year),
                "value": projected.observation.value,
                "dataset_id": projected.observation.dataset_id,
                "observation_id": projected.observation.observation_id,
                "measurement_unit": measurement_unit,
            }
        )
        for projected in projection.observations
    }


def _assert_exact_four_member_profile(
    profile: Any,
    scenario: Any,
    projection: ActivatedAcquisitionObservationProjection,
) -> None:
    outcome = scenario.passport.variable_id
    field_binding = scenario.passport.registration.field_binding
    passport_unit = field_binding.canonical_unit
    assert passport_unit
    assert field_binding.raw_unit == passport_unit
    declared_units = {
        json.loads(projected.observation.condition_json).get("unit")
        for projected in projection.observations
    }
    assert declared_units == {passport_unit}
    expected_hashes = _expected_profile_source_hashes(outcome, passport_unit, projection)
    actual_hashes = {digest for row in profile.rows for digest in row.source_row_content_hashes}
    assert profile.owner_row_count == 4
    assert profile.owner_row_count == len(projection.observations)
    assert tuple(row.unit_id for row in profile.rows) == ("UA",) * 4
    assert tuple(row.period_id for row in profile.rows) == (2021, 2022, 2023, 2024)
    assert actual_hashes == expected_hashes
    assert profile.owner_rows_content_hash == gy_content_hash(
        tuple(row.model_dump(mode="json") for row in profile.rows)
    )
    # Exact C membership establishes row identity only. C v1 does not establish
    # how these period coordinates bind to valid/as-of/policy/data-time roles.
    assert projection.source_time_status == "not_established"


def test_default_root_gateway_uses_exact_c_members_before_cap_and_grouping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Visible baseline nonmembers cannot displace the four admitted C members."""
    _seed_baseline_nonmembers_before_authority_freeze(monkeypatch, row_count=20_001)
    scenario, projection = _activate_four_row_scenario(tmp_path, monkeypatch)
    outcome = scenario.passport.variable_id

    con = catalog_read_api.open_catalog_read_session(
        scenario.authority.baseline_path,
        overlay_path=scenario.overlay.overlay_path,
    )
    try:
        visible_scoped_rows = con.execute(
            "SELECT count(*) FROM ds_observations WHERE canonical_var = ? "
            "AND country_code = 'UA' AND value IS NOT NULL "
            "AND COALESCE(year, survey_year, wave) IS NOT NULL",
            [outcome],
        ).fetchone()[0]
    finally:
        con.close()
    assert len(projection.observations) == 4
    assert visible_scoped_rows == 20_005

    profile = _load_through_default_controller_gateway(scenario, projection, monkeypatch)

    _assert_exact_four_member_profile(profile, scenario, projection)

    # R1: retain the real function, query, markers, and parameter arity while
    # removing only the query's exact-ID enabler. The same positive must then fail
    # at the real row cap because the unprojected epoch-zero rows remain visible.
    with monkeypatch.context() as counterfactual:
        _disable_exact_projection_member_query_filter(counterfactual)
        with pytest.raises(ValueOwnerAccessError) as raised:
            _load_through_default_root_gateway(scenario, projection)
    assert raised.value.code == "acquire_data:value_owner_rows_truncated"


def test_active_c_claim_without_member_projection_refuses_before_availability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An active target passport cannot enter the unprojected catalog union."""
    scenario, projection = _activate_four_row_scenario(tmp_path, monkeypatch)
    assert projection.variable_id == scenario.passport.variable_id

    def availability_must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("active target claim was not refused before availability")

    monkeypatch.setattr(
        data_state_substrate,
        "l1_dcat_variable_availability",
        availability_must_not_run,
    )
    with pytest.raises(ValueOwnerAccessError) as raised:
        _load_through_default_root_gateway(scenario, None)

    assert raised.value.code == "acquire_data:active_observation_projection_missing"


def test_unavailable_c_state_projection_refuses_before_availability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed C overlay state cannot be treated as an empty active set."""
    scenario, _projection = _activate_four_row_scenario(tmp_path, monkeypatch)
    con = duckdb.connect(str(scenario.overlay.overlay_path))
    try:
        con.execute("DROP TABLE acquisition_passports")
    finally:
        con.close()

    def availability_must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("unavailable C state was not refused before availability")

    monkeypatch.setattr(
        data_state_substrate,
        "l1_dcat_variable_availability",
        availability_must_not_run,
    )
    with pytest.raises(ValueOwnerAccessError) as raised:
        _load_through_default_root_gateway(scenario, None)

    assert raised.value.code == "acquire_data:active_observation_state_unavailable"


def test_no_active_c_claim_keeps_epoch_zero_rows_in_baseline_only_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pending C epoch does not displace four valid baseline observations."""
    _seed_baseline_nonmembers_before_authority_freeze(
        monkeypatch,
        row_count=4,
        years=(2017, 2018, 2019, 2020),
    )
    scenario = _scenario_with_raw_rows(tmp_path, monkeypatch, _four_ratio_rows())
    state = catalog_read_api.project_catalog_acquisition_state(
        scenario.authority.baseline_path,
        overlay_path=scenario.overlay.overlay_path,
    )
    assert state.active_epoch_count == 0
    assert state.pending_epoch_count == 1
    assert any(
        row.variable_id == scenario.passport.variable_id
        for row in state.passports
    )

    real_project_catalog_acquisition_state = (
        catalog_read_api.project_catalog_acquisition_state
    )
    state_overlay_arguments: list[Path | None] = []

    def record_acquisition_state_projection(
        baseline_path: Path,
        *,
        overlay_path: Path | None = None,
    ) -> Any:
        state_overlay_arguments.append(overlay_path)
        return real_project_catalog_acquisition_state(
            baseline_path,
            overlay_path=overlay_path,
        )

    real_open_catalog_read_session = catalog_read_api.open_catalog_read_session
    overlay_arguments: list[Path | None] = []

    def record_catalog_read_session(
        baseline_path: Path,
        *,
        overlay_path: Path | None = None,
    ) -> Any:
        overlay_arguments.append(overlay_path)
        return real_open_catalog_read_session(
            baseline_path,
            overlay_path=overlay_path,
        )

    monkeypatch.setattr(
        catalog_read_api,
        "project_catalog_acquisition_state",
        record_acquisition_state_projection,
    )
    monkeypatch.setattr(
        catalog_read_api,
        "open_catalog_read_session",
        record_catalog_read_session,
    )
    profile = _load_through_default_root_gateway(scenario, None)

    assert profile.owner_row_count == 4
    assert tuple(row.period_id for row in profile.rows) == (2017, 2018, 2019, 2020)
    assert tuple(row.unit_id for row in profile.rows) == ("UA",) * 4
    assert all(row.outcome_value == pytest.approx(0.99) for row in profile.rows)
    # C sees the pending overlay but availability and row intake explicitly select
    # its epoch-zero-only read mode because no target claim is active.
    assert state_overlay_arguments == [scenario.overlay.overlay_path]
    assert overlay_arguments.count(None) >= 2


def test_same_country_nonmember_cannot_replace_a_missing_c_member_in_denominator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A replacement country row cannot make an incomplete C member set look whole."""
    scenario, projection = _activate_four_row_scenario(tmp_path, monkeypatch)
    missing = projection.observations[0].observation
    con = duckdb.connect(str(scenario.overlay.overlay_path))
    try:
        con.execute(
            "DELETE FROM ds_observations WHERE observation_id = ?",
            [missing.observation_id],
        )
        con.execute(
            "INSERT INTO ds_observations "
            "(observation_id, dataset_id, raw_variable, canonical_var, country_code, "
            "year, survey_year, wave, value, condition_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "unprojected-denominator-replacement",
                "foreign-dataset",
                "distress_score",
                scenario.passport.variable_id,
                "UA",
                missing.year,
                None,
                None,
                missing.value,
                json.dumps({"unit": "ratio"}),
            ],
        )
    finally:
        con.close()

    with pytest.raises(ValueOwnerAccessError) as raised:
        _load_through_default_root_gateway(scenario, projection)

    assert raised.value.code == "acquire_data:active_observation_projection_drift"


def _physical_canonical_observation_fields(scenario: Any) -> tuple[str, ...]:
    """Return C model fields that are actually columns in this overlay relation."""
    con = duckdb.connect(str(scenario.overlay.overlay_path), read_only=True)
    try:
        available_columns = {
            str(column[1])
            for column in con.execute("PRAGMA table_info('ds_observations')").fetchall()
        }
    finally:
        con.close()
    return tuple(
        field_name
        for field_name in CanonicalAcquisitionObservation.model_fields
        if field_name in available_columns
    )


def _different_valid_physical_value(field_name: str, current_value: object) -> object:
    """Change one typed physical field while keeping the raw row model-valid."""
    if field_name == "condition_json":
        payload = json.loads(str(current_value))
        payload["physical-row-test"] = "changed"
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    if current_value is None:
        return 2025
    if isinstance(current_value, bool):
        return not current_value
    if isinstance(current_value, int):
        return current_value + 1
    if isinstance(current_value, float):
        return current_value + 0.01
    if isinstance(current_value, str):
        return current_value + "-physical-tamper"
    raise AssertionError(f"No valid tamper is defined for C physical field {field_name}")


def _activation_markers(scenario: Any) -> tuple[object, ...]:
    con = duckdb.connect(str(scenario.overlay.overlay_path), read_only=True)
    try:
        row = con.execute(
            "SELECT passport_id, admission_content_sha256, admitted_observation_count, "
            "pending_overlay_receipt_ref, admitted_boundary_evidence_ref, "
            "semantic_epoch_production_receipt_ref, activated_overlay_receipt_ref, "
            "epoch_activation_state FROM acquisition_epochs WHERE epoch_id = ?",
            [scenario.passport.epoch_id],
        ).fetchone()
        assert row is not None
        return row
    finally:
        con.close()


def test_active_projection_rejects_tampering_of_every_physical_c_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every stored C model column is bound while activation stays unchanged."""
    scenario, projection = _activate_four_row_scenario(tmp_path, monkeypatch)
    selected = projection.observations[0].observation
    markers_before = _activation_markers(scenario)
    physical_fields = _physical_canonical_observation_fields(scenario)
    assert physical_fields

    for field_name in physical_fields:
        original_value = getattr(selected, field_name)
        replacement = _different_valid_physical_value(field_name, original_value)
        assert replacement != original_value
        con = duckdb.connect(str(scenario.overlay.overlay_path))
        try:
            # Names come from the physical schema intersected with the C model.
            con.execute(
                f"UPDATE ds_observations SET {field_name} = ? WHERE observation_id = ?",  # noqa: S608
                [replacement, selected.observation_id],
            )
        finally:
            con.close()

        try:
            assert _activation_markers(scenario) == markers_before
            with pytest.raises(ValueOwnerAccessError) as raised:
                _load_through_default_root_gateway(scenario, projection)
            assert raised.value.code == "acquire_data:active_observation_projection_drift"
        finally:
            # Restore even the primary key before probing the next physical field.
            current_observation_id = (
                replacement if field_name == "observation_id" else selected.observation_id
            )
            con = duckdb.connect(str(scenario.overlay.overlay_path))
            try:
                con.execute(
                    f"UPDATE ds_observations SET {field_name} = ? WHERE observation_id = ?",  # noqa: S608
                    [original_value, current_observation_id],
                )
            finally:
                con.close()


_NONPHYSICAL_PROVENANCE_FIELDS = (
    "acquisition_method",
    "source_watermark",
    "dataset_version",
)


def _forge_projection_field(
    projection: ActivatedAcquisitionObservationProjection,
    field_name: str,
) -> ActivatedAcquisitionObservationProjection:
    """Reissue a self-consistent view with one altered C-derived provenance field."""
    observations = [row.observation for row in projection.observations]
    original = observations[0]
    payload = original.model_dump(mode="json")
    current_value = payload[field_name]
    assert isinstance(current_value, str)
    payload[field_name] = f"{current_value}-forged"
    observations[0] = CanonicalAcquisitionObservation.model_validate(payload)
    return ActivatedAcquisitionObservationProjection.issue(
        receipt_ref=projection.receipt_ref,
        receipt_content_sha256=projection.receipt_content_sha256,
        passport_ref=projection.passport_ref,
        passport_content_sha256=projection.passport_content_sha256,
        variable_id=projection.variable_id,
        epoch_id=projection.epoch_id,
        passport_id=projection.passport_id,
        admission_content_sha256=projection.admission_content_sha256,
        observations=observations,
    )


@pytest.mark.parametrize("field_name", _NONPHYSICAL_PROVENANCE_FIELDS)
def test_c_owner_rejects_rehashed_nonphysical_provenance_forgery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field_name: str,
) -> None:
    """Recomputed projection hashes cannot authorize forged passport-derived fields."""
    scenario, projection = _activate_four_row_scenario(tmp_path, monkeypatch)
    forged_projection = _forge_projection_field(projection, field_name)
    assert forged_projection.projection_content_sha256 != projection.projection_content_sha256

    with pytest.raises(ValueOwnerAccessError) as raised:
        _load_through_default_root_gateway(scenario, forged_projection)

    assert raised.value.code == "acquire_data:active_observation_projection_drift"


def test_c_admitted_condition_unit_conflict_is_refused_by_a_profile_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C can persist the signed body; A refuses a row unit that conflicts with its passport."""
    rows = _four_ratio_rows()
    rows[2]["condition_json"] = {"unit": "percent"}
    scenario, projection = _activate_scenario(tmp_path, monkeypatch, rows)
    binding = scenario.passport.registration.field_binding
    declared_units = {
        json.loads(projected.observation.condition_json).get("unit")
        for projected in projection.observations
    }

    # The actual C readback and active passport bind this stored source body; its
    # condition metadata disagrees with the registered identity transform ratio.
    assert projection.variable_id == scenario.passport.variable_id
    assert len(projection.observations) == 4
    assert binding.raw_unit == binding.canonical_unit == "ratio"
    assert declared_units == {"ratio", "percent"}

    with pytest.raises(ValueOwnerAccessError) as raised:
        _load_through_default_root_gateway(scenario, projection)

    assert raised.value.code == "acquire_data:active_observation_unit_binding_mismatch"


def _write_l1_catalog(path: Path, rows: list[tuple[object, ...]]) -> None:
    """Create the minimal real DuckDB tables read by the availability/profile APIs."""
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE ds_observations (observation_id VARCHAR, dataset_id VARCHAR, "
            "raw_variable VARCHAR, canonical_var VARCHAR, country_code VARCHAR, year INTEGER, "
            "survey_year INTEGER, wave INTEGER, value DOUBLE, condition_json VARCHAR)"
        )
        con.execute("CREATE TABLE ds_metric_bindings (metric_id VARCHAR)")
        con.execute("CREATE TABLE ds_datasets (polisyos_metrics VARCHAR[])")
        con.executemany(
            "INSERT INTO ds_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    finally:
        con.close()


def test_nonfinite_scoped_row_refuses_instead_of_reducing_profile_denominator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A scoped Inf row cannot silently disappear and yield an apparently complete panel."""
    path = tmp_path / "l1.duckdb"
    rows = [
        (
            f"obs-{year}",
            "dataset-UA",
            "x",
            "distress_score",
            "UA",
            year,
            None,
            None,
            value,
            '{"unit":"ratio"}',
        )
        for year, value in ((2020, 0.1), (2021, 0.2), (2022, 0.3), (2023, 0.4))
    ]
    rows.append(
        (
            "obs-inf",
            "dataset-UA",
            "x",
            "distress_score",
            "UA",
            2024,
            None,
            None,
            float("inf"),
            '{"unit":"ratio"}',
        )
    )
    _write_l1_catalog(path, rows)
    paths = SimpleNamespace(l1_dcat_path=path)
    monkeypatch.setattr(
        data_state_substrate,
        "default_substrate_catalog_paths",
        lambda _repo_root: paths,
    )
    monkeypatch.setattr(
        substrate_registry,
        "default_substrate_catalog_paths",
        lambda _repo_root: paths,
    )
    monkeypatch.setattr(
        catalog_read_api,
        "default_acquisition_overlay_path",
        lambda _repo_root: None,
    )

    candidate = SimpleNamespace(atom=SimpleNamespace(target_world_slots=("distress_score",)))
    problem = SimpleNamespace(
        outcome_of_interest=SimpleNamespace(target_variable="distress_score"),
        jurisdiction_time=SimpleNamespace(region="UA"),
    )
    with pytest.raises(ValueOwnerAccessError) as raised:
        RealValueOwnerGateway(repo_root=tmp_path).load_value_data_profile(
            candidate=candidate,
            problem=problem,  # type: ignore[arg-type]
            world_record=object(),
        )

    assert raised.value.code == "acquire_data:value_owner_row_non_finite"


# No test maps year/survey_year/wave to a request's valid/as-of/policy/data times:
# the activated C projection says source_time_status="not_established". The rows
# above are tested for exact membership, not for task-time admissibility.
