"""Exact selected source, actual availability and explicit readmission witnesses."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, cast

import duckdb
import pytest

from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.data_state_substrate import l1_dcat_variable_availability
from polisyos.runtime.quality.substrate_registry import (
    CatalogServingSourceSelection,
    SubstrateRegistryError,
    build_substrate_registry,
    build_substrate_registry_from_existing_catalogs,
    catalog_serving_source_scope,
    default_substrate_catalog_paths,
    load_substrate_registry,
    persist_substrate_registry,
    require_catalog_source_registry_binding,
    resolve_catalog_serving_source,
)
from tests.unit.runtime.quality.test_substrate_registry import _write_substrate_catalog_fixture

if TYPE_CHECKING:
    from polisyos.runtime.quality.substrate_registry import CatalogServingSourcePaths
    from polisyos.runtime.quality.world_model_record import WorldModelRecord


_VARIABLE = "government.balance"


def _selected_fixture(
    tmp_path: Path, *, populated: bool = False
) -> tuple[Path, Path, CatalogServingSourcePaths]:
    code = tmp_path / "code"
    owner = tmp_path / "data-owner"
    _write_substrate_catalog_fixture(code)
    _write_substrate_catalog_fixture(owner)
    # Both roots have real epoch registries. Different scoped source bytes make
    # code-root ownership distinguishable without adding an unscoped regime.
    code_epoch = default_substrate_catalog_paths(code).epoch_schema_regime_registry_path
    owner_epoch = default_substrate_catalog_paths(owner).epoch_schema_regime_registry_path
    assert code_epoch is not None and owner_epoch is not None
    payload = json.loads(owner_epoch.read_text())
    payload["regimes"]["ukraine_schema_v2"]["source_version"] = "data-owner-decoy"
    owner_epoch.write_text(json.dumps(payload))
    selected = owner / "snapshot/datasets/graph/dataset_catalog.duckdb"
    selected.parent.mkdir(parents=True)
    selected.write_bytes(default_substrate_catalog_paths(owner).l1_dcat_path.read_bytes())
    with duckdb.connect(str(selected)) as connection:
        connection.execute("ALTER TABLE ds_metric_bindings ADD COLUMN metric_id VARCHAR")
        connection.execute("ALTER TABLE ds_datasets ADD COLUMN polisyos_metrics VARCHAR[]")
        connection.execute("""CREATE TABLE ds_observations(
            canonical_var VARCHAR, country_code VARCHAR, year INTEGER,
            survey_year INTEGER, wave INTEGER, value DOUBLE,
            dataset_id VARCHAR, observation_id VARCHAR, condition_json VARCHAR
        )""")
        if populated:
            connection.executemany(
                "INSERT INTO ds_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        _VARIABLE,
                        "UA",
                        2020 + i,
                        None,
                        None,
                        float(i),
                        "controlled-data",
                        f"controlled-observation-{i}",
                        '{"unit":"synthetic index"}',
                    )
                    for i in range(8)
                ],
            )
    source = resolve_catalog_serving_source(
        code,
        selection=CatalogServingSourceSelection(
            snapshot_root=owner / "snapshot",
            source_owner_root=owner,
            catalog_run_profile="prod_full",
        ),
        requested_profile="prod_full",
    )
    return code, owner, source


def test_selected_registry_reconciles_actual_value_owner_and_code_epoch(tmp_path: Path) -> None:
    from polisyos.runtime.quality.generation_cycle import (
        RealValueOwnerGateway,
        ValueOwnerAccessError,
        _blocked_value_owner_failure,
    )
    from tests._helpers import controlled_candidate_profile as fixtures

    code, _owner, source = _selected_fixture(tmp_path)
    base_problem = fixtures._problem("c32-actual-value-owner")
    problem = base_problem.model_copy(
        update={
            "outcome_of_interest": base_problem.outcome_of_interest.model_copy(
                update={"target_variable": _VARIABLE, "metric_id": _VARIABLE}
            ),
            "objectives": [
                base_problem.objectives[0].model_copy(
                    update={"objective_id": _VARIABLE, "metric_id": _VARIABLE}
                )
            ],
        }
    )
    candidate = fixtures._Candidate(
        candidate_id="c32-gap-candidate",
        atom=fixtures._Atom(
            intervention_id="c32-gap-atom",
            content_hash=gy_content_hash({"candidate": "c32-gap-candidate"}),
            target_world_slots=(_VARIABLE,),
        ),
        diversity_key=("test", "test", "test", "test"),
    )
    with catalog_serving_source_scope(source):
        registry = build_substrate_registry_from_existing_catalogs(code)
        require_catalog_source_registry_binding(code, registry, source)
        availability = l1_dcat_variable_availability(code, _VARIABLE)
        assert availability.status == "unavailable"
        gateway = RealValueOwnerGateway(repo_root=code, catalog_serving_source=source)
        with pytest.raises(ValueOwnerAccessError) as refused:
            # This early missing-data owner path does not consume a WMR. No
            # synthetic WMR is passed off as a successful world observation.
            gateway.load_value_data_profile(
                candidate=candidate, problem=problem, world_record=cast("WorldModelRecord", None)
            )
        assert refused.value.owner_gap_evidence == availability
        assert refused.value.owner_access_ref == availability.coverage_ref
        observation = _blocked_value_owner_failure(
            failure=refused.value,
            fallback_code="fixture_must_not_use_fallback",
            fallback_reason_prefix="",
            candidate=candidate,
            problem=problem,
            mode="simulate_only",
            started=0.0,
            candidate_id=candidate.candidate_id,
        )
        gap = observation.acquisition_requirement
        assert gap is not None
        assert gap.metadata["availability"] == availability.model_dump(mode="json")
        assert gap.metadata["candidate_binding"]["design_problem_ref"] == gy_content_hash(
            problem.model_dump(mode="json")
        )
    epoch_path = default_substrate_catalog_paths(code).epoch_schema_regime_registry_path
    assert epoch_path is not None
    expected_epoch_ref = "sha256:" + hashlib.sha256(epoch_path.read_bytes()).hexdigest()
    assert expected_epoch_ref in registry.source_catalog_refs
    assert any(
        ref.startswith("catalog_read_source_content://sha256:")
        for ref in registry.source_catalog_refs
    )


@pytest.mark.parametrize("changed_owner", ["observation", "dataset", "null_source", "empty_source"])
def test_same_summary_different_actual_availability_refuses_old_selected_registry(
    tmp_path: Path, changed_owner: str
) -> None:
    code, _owner, source = _selected_fixture(tmp_path)
    with catalog_serving_source_scope(source):
        registry = build_substrate_registry_from_existing_catalogs(code)
        before = l1_dcat_variable_availability(code, _VARIABLE)
        assert before.status == "unavailable"
        with duckdb.connect(str(source.database_path)) as connection:
            if changed_owner == "observation":
                connection.execute(
                    "INSERT INTO ds_observations(canonical_var) VALUES (?)", [_VARIABLE]
                )
            elif changed_owner == "dataset":
                connection.execute("UPDATE ds_datasets SET polisyos_metrics = [?]", [_VARIABLE])
            else:
                connection.execute(
                    "INSERT INTO ds_metric_bindings(source, metric_id) VALUES (?, ?)",
                    [None if changed_owner == "null_source" else "", _VARIABLE],
                )
        with pytest.raises(
            SubstrateRegistryError, match="catalog_source_content_changed_readmission_required"
        ):
            require_catalog_source_registry_binding(code, registry, source)
    readmitted = resolve_catalog_serving_source(
        code,
        selection=CatalogServingSourceSelection(
            snapshot_root=source.snapshot_root,
            source_owner_root=source.source_owner_root,
            catalog_run_profile="prod_full",
        ),
        requested_profile="prod_full",
    )
    with catalog_serving_source_scope(readmitted):
        refreshed = build_substrate_registry_from_existing_catalogs(code)
        after = l1_dcat_variable_availability(code, _VARIABLE)
        assert after.status == "available"
        assert refreshed.content_hash != registry.content_hash
        with pytest.raises(
            SubstrateRegistryError, match="catalog_source_registry_binding_mismatch"
        ):
            require_catalog_source_registry_binding(code, registry, readmitted)


@pytest.mark.parametrize("replacement_location", ["inside", "outside"])
def test_post_admission_member_symlink_refuses_actual_availability_read(
    tmp_path: Path, replacement_location: str
) -> None:
    code, owner, source = _selected_fixture(tmp_path)
    target = (owner if replacement_location == "inside" else tmp_path) / "replacement.duckdb"
    target.write_bytes(source.database_path.read_bytes())
    source.database_path.unlink()
    source.database_path.symlink_to(target)
    with (
        catalog_serving_source_scope(source),
        pytest.raises(SubstrateRegistryError, match="catalog_source_database_path_unbound"),
    ):
        l1_dcat_variable_availability(code, _VARIABLE)


def test_old_registry_artifact_loads_but_live_explicit_reuse_requires_readmission(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS

    code, _owner, source = _selected_fixture(tmp_path)
    with catalog_serving_source_scope(source):
        current = build_substrate_registry_from_existing_catalogs(code)
        legacy = build_substrate_registry(
            current.entries,
            producer_ref=current.producer_ref,
            source_catalog_refs=tuple(
                ref
                for ref in current.source_catalog_refs
                if not ref.startswith("catalog_read_source_content://")
            ),
        )
        store = FileSystemCAS(tmp_path / "cas")
        ref = persist_substrate_registry(store, legacy)
        assert load_substrate_registry(store, ref) == legacy
        with pytest.raises(
            SubstrateRegistryError, match="catalog_source_registry_readmission_required"
        ):
            require_catalog_source_registry_binding(code, legacy, source)
        require_catalog_source_registry_binding(code, current, source)
        with pytest.raises(SubstrateRegistryError, match="catalog_source_readmission_required"):
            _read_source_availability(code, replace(source, read_source_identity=None))


def _read_source_availability(code: Path, source: CatalogServingSourcePaths) -> None:
    with catalog_serving_source_scope(source):
        l1_dcat_variable_availability(code, _VARIABLE)


@pytest.mark.parametrize("owner_kind", ["missing", "file", "outside"])
def test_selected_source_owner_errors_remain_typed(tmp_path: Path, owner_kind: str) -> None:
    code, _owner, source = _selected_fixture(tmp_path)
    owner = tmp_path / "different-owner"
    if owner_kind == "file":
        owner.write_text("a file is not an owner directory")
    elif owner_kind == "outside":
        owner.mkdir()
    expected = {
        "missing": "substrate_source_owner_root_unavailable",
        "file": "substrate_source_owner_root_not_directory",
        "outside": "substrate_source_path_outside_repo_root",
    }[owner_kind]
    with pytest.raises(SubstrateRegistryError, match=expected):
        resolve_catalog_serving_source(
            code,
            selection=CatalogServingSourceSelection(
                snapshot_root=source.snapshot_root,
                source_owner_root=owner,
                catalog_run_profile="prod_full",
            ),
            requested_profile="prod_full",
        )


def test_missing_overlay_becoming_present_requires_explicit_source_readmission(
    tmp_path: Path,
) -> None:
    code, _owner, source = _selected_fixture(tmp_path)
    with catalog_serving_source_scope(source):
        registry = build_substrate_registry_from_existing_catalogs(code)
        assert source.read_source_identity is not None
        assert source.read_source_identity[2] is None
        source.overlay_path.parent.mkdir(parents=True, exist_ok=True)
        # Arbitrary newly arrived bytes are enough to invalidate the old empty
        # overlay basis; they are never opened or accepted as an admitted epoch.
        source.overlay_path.write_bytes(b"unadmitted overlay bytes")
        with pytest.raises(
            SubstrateRegistryError, match="catalog_source_content_changed_readmission_required"
        ):
            require_catalog_source_registry_binding(code, registry, source)
        with pytest.raises(
            SubstrateRegistryError, match="catalog_source_content_changed_readmission_required"
        ):
            l1_dcat_variable_availability(code, _VARIABLE)


def test_default_registry_hash_is_unchanged_after_explicit_source_scope(tmp_path: Path) -> None:
    code, _owner, source = _selected_fixture(tmp_path)
    before = build_substrate_registry_from_existing_catalogs(code)
    with catalog_serving_source_scope(source):
        explicit = build_substrate_registry_from_existing_catalogs(code)
    after = build_substrate_registry_from_existing_catalogs(code)
    assert after == before
    assert not any(
        ref.startswith("catalog_read_source_content://") for ref in before.source_catalog_refs
    )
    assert explicit.content_hash != before.content_hash


def _actual_profile_gateway_inputs():
    from polisyos.runtime.quality.generation_cycle import RealValueOwnerGateway
    from tests._helpers import controlled_candidate_profile as fixtures

    base = fixtures._problem("c32-available-owner")
    problem = base.model_copy(
        update={
            "outcome_of_interest": base.outcome_of_interest.model_copy(
                update={
                    "target_variable": _VARIABLE,
                    "metric_id": _VARIABLE,
                }
            ),
        }
    )
    candidate = fixtures._Candidate(
        candidate_id="c32-available-candidate",
        atom=fixtures._Atom(
            "c32-available-atom", gy_content_hash("c32-available"), target_world_slots=(_VARIABLE,)
        ),
        diversity_key=("test", "test", "test", "test"),
    )
    return RealValueOwnerGateway, problem, candidate


def test_available_owner_reads_all_actual_rows_under_the_admitted_source(tmp_path: Path) -> None:
    code, _owner, source = _selected_fixture(tmp_path, populated=True)
    gateway_type, problem, candidate = _actual_profile_gateway_inputs()
    gateway = gateway_type(repo_root=code, catalog_serving_source=source)
    with catalog_serving_source_scope(source):
        profile = gateway.load_value_data_profile(
            candidate=candidate, problem=problem, world_record=cast("WorldModelRecord", None)
        )
    assert profile.owner_row_count == 8
    assert profile.outcome == _VARIABLE
    assert profile.measurement_unit == "synthetic index"
    assert tuple(row.outcome_value for row in profile.rows) == tuple(float(i) for i in range(8))
    assert profile.treatment_assignment_status == "owner_assignment_unresolved"
    assert profile.owner_access_ref.startswith(f"catalog_source://{source.database_path}")


def test_available_owner_refuses_replacement_between_availability_and_native_profile_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.data_forge.domains.catalog.knowledge import store as store_module
    from polisyos.runtime.quality.generation_cycle import ValueOwnerAccessError

    code, _owner, source = _selected_fixture(tmp_path, populated=True)
    other_root = tmp_path / "foreign"
    _other_code, _other_owner, other = _selected_fixture(other_root, populated=True)
    with duckdb.connect(str(other.database_path)) as connection:
        connection.execute("UPDATE ds_observations SET value = value + 1000")
    original_open = store_module.open_catalog_read_session
    opened = 0

    def replace_before_second_native_open(path: Path, *, overlay_path: Path | None = None):
        nonlocal opened
        opened += 1
        if opened == 2:
            other.database_path.replace(source.database_path)
        return original_open(path, overlay_path=overlay_path)

    monkeypatch.setattr(
        store_module, "open_catalog_read_session", replace_before_second_native_open
    )
    gateway_type, problem, candidate = _actual_profile_gateway_inputs()
    gateway = gateway_type(repo_root=code, catalog_serving_source=source)
    with (
        catalog_serving_source_scope(source),
        pytest.raises(ValueOwnerAccessError) as failure,
    ):
        gateway.load_value_data_profile(
            candidate=candidate, problem=problem, world_record=cast("WorldModelRecord", None)
        )
    assert opened == 2
    assert failure.value.code == "catalog_read_source_changed_while_opening"
    assert "catalog_fetch_source_changed_while_opening" in str(failure.value)
    assert failure.value.owner_gap_evidence is None


def test_appearing_wal_remains_a_source_refusal_not_a_missing_variable(tmp_path: Path) -> None:
    from polisyos.runtime.quality.generation_cycle import ValueOwnerAccessError

    code, _owner, source = _selected_fixture(tmp_path, populated=True)
    source.database_path.with_name(source.database_path.name + ".wal").write_bytes(
        b"pending native state"
    )
    gateway_type, problem, candidate = _actual_profile_gateway_inputs()
    gateway = gateway_type(repo_root=code, catalog_serving_source=source)
    with (
        catalog_serving_source_scope(source),
        pytest.raises(ValueOwnerAccessError) as failure,
    ):
        gateway.load_value_data_profile(
            candidate=candidate, problem=problem, world_record=cast("WorldModelRecord", None)
        )
    assert failure.value.code == "catalog_read_source_checkpoint_required"
    assert failure.value.owner_gap_evidence is None
    assert failure.value.code != "acquire_data:value_panel_data_missing"


def test_n7_registry_readmission_is_a_typed_cycle_refusal_with_its_original_cause(
    tmp_path: Path,
) -> None:
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleError,
        _n7_substrate_registry,
    )
    from tests._helpers import controlled_candidate_profile as fixtures

    code, _owner, source = _selected_fixture(tmp_path)
    legacy = build_substrate_registry_from_existing_catalogs(code)
    problem = fixtures._problem("c32-readmission").model_copy(
        update={
            "runtime_hints": {"substrate_registry": legacy.model_dump(mode="json")},
        }
    )
    with (
        catalog_serving_source_scope(source),
        pytest.raises(GenerationCycleError) as failure,
    ):
        _n7_substrate_registry(
            problem, families=(_VARIABLE,), repo_root=code, catalog_serving_source=source
        )
    assert failure.value.code == "n7_catalog_source_refused"
    assert failure.value.source_refusal_code == "catalog_source_registry_readmission_required"
    assert isinstance(failure.value.__cause__, SubstrateRegistryError)


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_registry", [False, True])
async def test_controller_keeps_real_owner_gap_and_fresh_planner_or_typed_readmission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, legacy_registry: bool
) -> None:
    """A component cycle uses actual owner evidence; no planner report is authored.

    The existing controlled generation input is explicitly contract-testing.
    This is not an ordinary served CGF or measured empirical capability proof.
    """
    import time

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.quality.acquisition_planner import load_acquisition_planner_report
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        RealValueOwnerGateway,
        ValueOwnerAccessError,
        _blocked_value_owner_failure,
    )
    from tests._helpers import controlled_candidate_profile as fixtures
    from tests._helpers.acquisition_production import install_fixture_wdi_cost_basis

    code, _owner, source = _selected_fixture(tmp_path)
    _gateway_type, problem, _candidate = _actual_profile_gateway_inputs()
    problem = problem.model_copy(
        update={
            "jurisdiction_time": problem.jurisdiction_time.model_copy(
                update={
                    "region": "UKR",
                    "data_time": "2024",
                }
            ),
            "objectives": [
                problem.objectives[0].model_copy(
                    update={
                        "objective_id": _VARIABLE,
                        "metric_id": _VARIABLE,
                    }
                )
            ],
        }
    )
    if legacy_registry:
        prior = build_substrate_registry_from_existing_catalogs(code)
        problem = problem.model_copy(
            update={
                "runtime_hints": {"substrate_registry": prior.model_dump(mode="json")},
            }
        )
    install_fixture_wdi_cost_basis(monkeypatch)
    gateway = RealValueOwnerGateway(repo_root=code, catalog_serving_source=source)
    observed_evidence = []

    class ActualMissingDataOwnerPort:
        def __call__(self, *, candidate, problem, simulation, cycle_index):
            del cycle_index
            started = time.monotonic()
            try:
                gateway.load_value_data_profile(
                    candidate=candidate,
                    problem=problem,
                    world_record=simulation.world_model_record,
                )
            except ValueOwnerAccessError as exc:
                observed_evidence.append(exc.owner_gap_evidence)
                return _blocked_value_owner_failure(
                    failure=exc,
                    fallback_code="fixture_fallback_must_not_run",
                    fallback_reason_prefix="",
                    candidate=candidate,
                    problem=problem,
                    mode="simulate_only",
                    started=started,
                    candidate_id=candidate.candidate_id,
                )
            raise AssertionError("the actual fixture catalog must lack the selected variable")

    store = FileSystemCAS(tmp_path / "controller-cas")
    with catalog_serving_source_scope(source):
        controller = GenerationCycleController(
            generation_port=fixtures._CgfGenerationPort(target_world_slots=(_VARIABLE,)),
            value_port=ActualMissingDataOwnerPort(),
            authority_scope="contract_testing",
            artifact_store=store,
            repo_root=code,
        )
        result = await controller.run(
            problem, budget_state=fixtures._budget(), min_cycles=1, max_cycles=1
        )
    assert len(observed_evidence) == 1
    assert observed_evidence[0] is not None
    assert len(result.cycles) == 1
    cycle = result.cycles[0]
    assert cycle.terminal_kind == "acquisition_required"
    assert cycle.value_port.acquisition_requirement is not None
    actual_gap = cycle.value_port.acquisition_requirement
    assert actual_gap.metadata["availability"] == observed_evidence[0].model_dump(mode="json")
    if legacy_registry:
        assert cycle.acquisition_routing_report_ref is None
        assert cycle.counterexample.diagnostic.code == (
            "n6.acquisition.n7_catalog_source_refused.catalog_source_registry_readmission_required"
        )
        assert cycle.acquisition_receipt is None
    else:
        assert cycle.acquisition_routing_report_ref is not None
        fresh = load_acquisition_planner_report(
            FileSystemCAS(tmp_path / "controller-cas"), cycle.acquisition_routing_report_ref
        )
        assert fresh == cycle.acquisition_routing_report
        assert len(fresh.acquisition_records) == 1
        record = fresh.acquisition_records[0]
        assert record.requirement_gap_ref == actual_gap.requirement_gap_id
        assert record.gap_type == actual_gap.gap_type
        assert _VARIABLE in record.scenario_requirement_refs
        assert fresh.requirement_basis_binding is not None
        assert fresh.basis_limitation_code != "unbound_requirement_input_refused"


def test_existing_owned_native_layout_is_admitted_without_copy_or_relocation(
    tmp_path: Path,
) -> None:
    code, owner, source = _selected_fixture(tmp_path, populated=True)
    legacy = owner / "production_data/retained-catalog/catalog.duckdb"
    legacy.parent.mkdir(parents=True)
    source.database_path.replace(legacy)
    before = hashlib.sha256(legacy.read_bytes()).hexdigest()
    admitted = resolve_catalog_serving_source(
        code,
        selection=CatalogServingSourceSelection(
            snapshot_root=owner,
            source_owner_root=owner,
            database_relative_path=legacy.relative_to(owner),
            catalog_run_profile="prod_full",
        ),
        requested_profile="prod_full",
    )
    gateway_type, problem, candidate = _actual_profile_gateway_inputs()
    with catalog_serving_source_scope(admitted):
        profile = gateway_type(
            repo_root=code, catalog_serving_source=admitted
        ).load_value_data_profile(
            candidate=candidate, problem=problem, world_record=cast("WorldModelRecord", None)
        )
        registry = build_substrate_registry_from_existing_catalogs(code)
        require_catalog_source_registry_binding(code, registry, admitted)
    assert profile.owner_row_count == 8
    assert admitted.database_path == legacy
    assert hashlib.sha256(legacy.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("relative", ["../foreign.duckdb", "/absolute.duckdb", "."])
def test_relative_member_cannot_escape_or_replace_the_snapshot_root(
    relative: str, tmp_path: Path
) -> None:
    with pytest.raises(ValueError, match="catalog_source_database_relative_path_invalid"):
        CatalogServingSourceSelection(
            snapshot_root=tmp_path,
            database_relative_path=Path(relative),
            catalog_run_profile="preflight_core",
        )


def test_default_builder_and_historical_artifact_match_the_exact_slice_base_source(
    tmp_path: Path,
) -> None:
    """Compare actual base-owner code under the same frozen dependency/profile inputs.

    This local source-compatibility witness requires the named Git object. It
    is not a full historic environment replay or inherited-red attribution.
    """
    import importlib.util
    import subprocess
    import sys

    from polisyos.core.artifacts.store import FileSystemCAS

    code, _owner, _source = _selected_fixture(tmp_path)
    actual = build_substrate_registry_from_existing_catalogs(code)
    product_root = Path(__file__).resolve().parents[4]
    command = [
        "/usr/bin/git",
        "show",
        "2ef22b8818f8a35611af3898c07c7121ca89075d:policy-engine/src/polisyos/runtime/quality/substrate_registry.py",
    ]
    raw = subprocess.check_output(command, cwd=product_root)
    assert (
        hashlib.sha256(raw).hexdigest()
        == "4bb061b74455402a5bd130b29fd7594a579a3b3a74bac0a55c3def9df0542531"
    )
    module_path = tmp_path / "exact_base_registry_owner.py"
    module_path.write_bytes(raw)
    module_name = "c32_exact_slice_base_registry_owner"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        old = module.build_substrate_registry_from_existing_catalogs(code)
        assert old.model_dump(mode="json") == actual.model_dump(mode="json")
        old_store = FileSystemCAS(tmp_path / "base-owner-cas")
        old_ref = module.persist_substrate_registry(old_store, old)
        fresh = load_substrate_registry(FileSystemCAS(tmp_path / "base-owner-cas"), old_ref)
        assert fresh.model_dump(mode="json") == old.model_dump(mode="json")
    finally:
        del sys.modules[module_name]


def test_unknown_source_basis_cannot_take_the_legacy_readmission_branch(tmp_path: Path) -> None:
    code, _owner, source = _selected_fixture(tmp_path)
    unknown = replace(source, selection_basis="unknown")
    with (
        catalog_serving_source_scope(unknown),
        pytest.raises(SubstrateRegistryError, match="catalog_source_context_invalid"),
    ):
        l1_dcat_variable_availability(code, _VARIABLE)


def test_absent_relative_member_and_explicit_default_keep_selected_artifact_bytes(
    tmp_path: Path,
) -> None:
    code, owner, source = _selected_fixture(tmp_path, populated=True)
    legacy_shape = {
        "snapshot_root": owner / "snapshot",
        "source_owner_root": owner,
        "catalog_run_profile": "prod_full",
    }
    absent = CatalogServingSourceSelection.model_validate(legacy_shape)
    explicit = CatalogServingSourceSelection.model_validate(
        {**legacy_shape, "database_relative_path": "datasets/graph/dataset_catalog.duckdb"}
    )
    gateway_type, problem, candidate = _actual_profile_gateway_inputs()
    selected_bytes = []
    for selection in (absent, explicit):
        resolved = resolve_catalog_serving_source(
            code, selection=selection, requested_profile="prod_full"
        )
        assert resolved.database_path == source.database_path
        assert resolved.read_source_identity == source.read_source_identity
        with catalog_serving_source_scope(resolved):
            registry = build_substrate_registry_from_existing_catalogs(code)
            profile = gateway_type(
                repo_root=code, catalog_serving_source=resolved
            ).load_value_data_profile(
                candidate=candidate, problem=problem, world_record=cast("WorldModelRecord", None)
            )
            selected_bytes.append((registry.model_dump_json(), profile.model_dump_json()))
    assert selected_bytes[0] == selected_bytes[1]
