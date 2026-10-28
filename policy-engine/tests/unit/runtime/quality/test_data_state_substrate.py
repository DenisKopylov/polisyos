from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb
import pytest

import polisyos.runtime.quality.data_state_substrate as data_state_substrate_module
from polisyos.runtime.quality.data_state_substrate import (
    DataStateSubstrateError,
    l1_dcat_variable_availability,
)
from polisyos.runtime.quality.substrate_registry import default_substrate_catalog_paths


def test_missing_catalog_and_unlisted_variable_have_distinct_owner_outcomes(
    tmp_path: Path,
) -> None:
    """Catalog absence is not reported as a variable-level unavailable result."""

    without_catalog = tmp_path / "catalog-absent"
    with pytest.raises(DataStateSubstrateError) as missing_catalog:
        l1_dcat_variable_availability(without_catalog, "unlisted-policy-metric")
    assert missing_catalog.value.code == "l1_dcat_missing"

    catalog_path = default_substrate_catalog_paths(tmp_path).l1_dcat_path
    catalog_path.parent.mkdir(parents=True)
    with duckdb.connect(str(catalog_path)) as connection:
        connection.execute("CREATE TABLE ds_metric_bindings (metric_id VARCHAR)")
        connection.execute("CREATE TABLE ds_observations (canonical_var VARCHAR)")
        connection.execute("CREATE TABLE ds_datasets (polisyos_metrics VARCHAR[])")

    unavailable = l1_dcat_variable_availability(tmp_path, "unlisted-policy-metric")

    assert unavailable.status == "unavailable"
    assert unavailable.variable_id == "unlisted-policy-metric"
    assert (
        unavailable.dataset_count,
        unavailable.metric_binding_count,
        unavailable.observation_count,
    ) == (0, 0, 0)


@pytest.mark.parametrize(
    "sidecar_name",
    [
        "fabric-world.duckdb.tmp",
        "fabric-world.duckdb.wal",
        "unrecognized-future-sidecar.bin",
    ],
)
def test_selected_fabric_snapshot_refuses_escaping_native_db_member_symlink_before_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sidecar_name: str,
) -> None:
    """The selected DB parent rejects any outside symlink before DB construction."""

    import polisyos.fabric.io.db as fabric_db_module

    workspace = tmp_path / "workspace"
    native_db_root = workspace / "fabric-world-db"
    native_db_root.mkdir(parents=True)
    outside_sidecar = tmp_path / "outside-sidecar"
    outside_sidecar.write_bytes(b"preserve-me")
    sidecar = native_db_root / sidecar_name
    sidecar.symlink_to(outside_sidecar)
    connection_attempts: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def refuse_database_construction(*args: object, **kwargs: object) -> None:
        connection_attempts.append((args, kwargs))
        raise AssertionError("SimulationDB must not open before the parent preflight")

    monkeypatch.setattr(fabric_db_module, "SimulationDB", refuse_database_construction)

    with pytest.raises(DataStateSubstrateError) as refused:
        data_state_substrate_module._write_fabric_world_snapshot(
            workspace_dir=workspace,
            snapshot_id="selected-snapshot",
            payload_hash="sha256:" + "a" * 64,
            stats={"bound_agent_count": 1},
            confine_outputs=True,
        )

    assert refused.value.code == "selected_workspace_output_path_escape"
    assert connection_attempts == []
    assert sidecar.is_symlink()
    assert outside_sidecar.read_bytes() == b"preserve-me"


def test_l1_dcat_count_queries_return_positive_counts_from_duckdb(tmp_path: Path) -> None:
    # Exercise the actual owner schema with nonzero results in each scalar.
    catalog_path = default_substrate_catalog_paths(tmp_path).l1_dcat_path
    catalog_path.parent.mkdir(parents=True)
    with duckdb.connect(str(catalog_path)) as connection:
        connection.execute("CREATE TABLE ds_metric_bindings (metric_id VARCHAR)")
        connection.execute("CREATE TABLE ds_observations (canonical_var VARCHAR)")
        connection.execute("CREATE TABLE ds_datasets (polisyos_metrics VARCHAR[])")
        connection.execute("INSERT INTO ds_metric_bindings VALUES ('policy-metric')")
        connection.execute(
            "INSERT INTO ds_observations VALUES ('policy-metric'), ('policy-metric')"
        )
        connection.execute("INSERT INTO ds_datasets VALUES (['policy-metric'])")

    result = l1_dcat_variable_availability(tmp_path, "policy-metric")

    assert result.status == "available"
    assert (
        result.dataset_count,
        result.metric_binding_count,
        result.observation_count,
    ) == (1, 1, 2)


def test_split_data_state_paths_bind_code_overlay_and_selected_l1_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The source owner supplies data while code continues to own the overlay."""

    from polisyos.data_forge import read_api

    code_root = tmp_path / "code-owner"
    data_root = tmp_path / "physical-data-owner"
    code_root.mkdir()
    (data_root / "production_data").mkdir(parents=True)
    (data_root / "production_data/manifest.json").write_text("{}\n", encoding="utf-8")

    def write_catalog(path: Path, *, include_selected: bool) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with duckdb.connect(str(path)) as connection:
            connection.execute("CREATE TABLE ds_metric_bindings (metric_id VARCHAR)")
            connection.execute("CREATE TABLE ds_observations (canonical_var VARCHAR)")
            connection.execute("CREATE TABLE ds_datasets (polisyos_metrics VARCHAR[])")
            if include_selected:
                connection.execute("INSERT INTO ds_metric_bindings VALUES ('selected-only')")

    code_catalog = default_substrate_catalog_paths(code_root).l1_dcat_path
    selected_paths = default_substrate_catalog_paths(
        code_root,
        source_owner_root=data_root,
    )
    write_catalog(code_catalog, include_selected=False)
    write_catalog(selected_paths.l1_dcat_path, include_selected=True)

    def tree_hashes(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    data_before = tree_hashes(data_root)
    from polisyos.data_forge.domains.catalog.knowledge import store as catalog_store_module

    original_open = catalog_store_module.open_catalog_read_session
    opened: list[tuple[Path, Path | None]] = []

    def record_open(path: Path, *, overlay_path: Path | None = None) -> Any:
        opened.append((Path(path), overlay_path))
        return original_open(path, overlay_path=overlay_path)

    monkeypatch.setattr(catalog_store_module, "open_catalog_read_session", record_open)
    selected = l1_dcat_variable_availability(
        code_root,
        "selected-only",
        production_data_root=data_root,
    )
    default = l1_dcat_variable_availability(code_root, "selected-only")

    assert selected.status == "available"
    assert selected.metric_binding_count == 1
    assert default.status == "unavailable"
    assert opened == [
        (
            selected_paths.l1_dcat_path,
            read_api.catalog.default_acquisition_overlay_path(code_root),
        ),
        (code_catalog, read_api.catalog.default_acquisition_overlay_path(code_root)),
    ]
    assert tree_hashes(data_root) == data_before


def test_split_data_state_source_paths_reject_a_symlink_escape(tmp_path: Path) -> None:
    """L1 and every L4 source path remain under the selected physical owner."""

    code_root = tmp_path / "code-owner"
    data_root = tmp_path / "physical-data-owner"
    code_root.mkdir()
    (data_root / "production_data").mkdir(parents=True)
    selected = data_state_substrate_module._default_data_state_paths(
        code_root,
        production_data_root=data_root,
    )
    legacy = data_state_substrate_module._default_data_state_paths(code_root)
    selected_paths = (
        selected.l1_dcat_path,
        selected.agent_registry_full,
        selected.firm_fundamentals_annual,
        selected.budget_flows_monthly_sparse,
        selected.corrected_firm_panels,
        selected.calibrated_household_cells,
    )
    legacy_paths = (
        legacy.l1_dcat_path,
        legacy.agent_registry_full,
        legacy.firm_fundamentals_annual,
        legacy.budget_flows_monthly_sparse,
        legacy.corrected_firm_panels,
        legacy.calibrated_household_cells,
    )
    assert all(path.is_relative_to(data_root) for path in selected_paths)
    assert all(path.is_relative_to(code_root) for path in legacy_paths)

    outside = tmp_path / "outside.parquet"
    outside.write_bytes(b"controlled-outside-source")
    escaped = selected.agent_registry_full
    escaped.parent.mkdir(parents=True, exist_ok=True)
    try:
        escaped.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("filesystem does not permit symlink fixtures")
    for path in (
        selected.l1_dcat_path,
        selected.firm_fundamentals_annual,
        selected.budget_flows_monthly_sparse,
        selected.corrected_firm_panels,
        selected.calibrated_household_cells,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    with pytest.raises(DataStateSubstrateError, match="production_data_path_unbound"):
        data_state_substrate_module._require_paths(
            selected,
            production_data_root=data_root,
        )


@pytest.mark.parametrize("nested_escape", [False, True])
def test_selected_data_forge_snapshot_refuses_workspace_symlink_escape(
    tmp_path: Path,
    nested_escape: bool,
) -> None:
    """The L4 snapshot producer rejects a snapshot-root link before writing through it."""

    workspace = tmp_path / "caller-workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    snapshot_root = workspace / "selected-snapshot"
    if nested_escape:
        snapshot_root.mkdir()
        (snapshot_root / "unexpected-child").symlink_to(outside, target_is_directory=True)
    else:
        snapshot_root.symlink_to(outside, target_is_directory=True)

    with pytest.raises(DataStateSubstrateError, match="selected_workspace_output_path_escape"):
        data_state_substrate_module._write_data_forge_snapshot_binding(
            workspace_dir=workspace,
            snapshot_id="selected-snapshot",
            payload={"fixture": "candidate-only"},
            payload_content_hash="sha256:" + "a" * 64,
            confine_outputs=True,
        )

    assert list(outside.iterdir()) == []


def test_split_l4_materializer_requires_disjoint_workspace_and_scoped_cas(
    tmp_path: Path,
) -> None:
    """Split-source materialization cannot write into either source root."""

    code_root = tmp_path / "code-owner"
    data_root = tmp_path / "physical-data-owner"
    workspace = tmp_path / "caller-workspace"
    code_root.mkdir()
    (data_root / "production_data").mkdir(parents=True)
    workspace.mkdir()
    store = data_state_substrate_module.FileSystemCAS(workspace / "cas")

    with pytest.raises(
        DataStateSubstrateError,
        match="split_data_workspace_overlaps_source_root",
    ):
        data_state_substrate_module.materialize_l4_data_state_snapshot(
            store,
            repo_root=code_root,
            workspace_dir=data_root,
            production_data_root=data_root,
        )

    outside_store = data_state_substrate_module.FileSystemCAS(tmp_path / "outside-cas")
    with pytest.raises(
        DataStateSubstrateError,
        match="split_data_cas_outside_workspace",
    ):
        data_state_substrate_module.materialize_l4_data_state_snapshot(
            outside_store,
            repo_root=code_root,
            workspace_dir=workspace,
            production_data_root=data_root,
        )

    with pytest.raises(DataStateSubstrateError, match="production_data_path_missing"):
        data_state_substrate_module.materialize_l4_data_state_snapshot(
            store,
            repo_root=code_root,
            workspace_dir=workspace,
            production_data_root=data_root,
        )


@pytest.mark.parametrize(
    ("row", "expected_code"),
    [
        (None, "l1_dcat_scalar_row_missing"),
        ((), "l1_dcat_scalar_row_shape_invalid"),
        ((0, 1), "l1_dcat_scalar_row_shape_invalid"),
        (("0",), "l1_dcat_scalar_value_invalid"),
        ((True,), "l1_dcat_scalar_value_invalid"),
        ((-1,), "l1_dcat_scalar_value_invalid"),
    ],
)
def test_l1_dcat_scalar_consumer_fails_closed_on_absent_or_malformed_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    row: tuple[object, ...] | None,
    expected_code: str,
) -> None:
    # Drive the public consumer with a controlled malformed backend row.
    class _ControlledConnection:
        closed = False

        def execute(self, query: str, parameters: list[object]) -> _ControlledConnection:
            del query, parameters
            return self

        def fetchone(self) -> tuple[object, ...] | None:
            return row

        def close(self) -> None:
            self.closed = True

    catalog_path = default_substrate_catalog_paths(tmp_path).l1_dcat_path
    catalog_path.parent.mkdir(parents=True)
    # A nonempty controlled backing file lets the real store bind its byte identity.
    catalog_path.write_bytes(b"controlled malformed backend fixture")
    connection = _ControlledConnection()
    from polisyos.data_forge.domains.catalog.knowledge import store as catalog_store_module

    monkeypatch.setattr(
        catalog_store_module,
        "open_catalog_read_session",
        lambda *_args, **_kwargs: connection,
    )

    with pytest.raises(DataStateSubstrateError) as failure:
        l1_dcat_variable_availability(tmp_path, "policy-metric")

    assert failure.value.code == expected_code
    assert connection.closed


def test_snapshot_binding_uses_read_api_publishers_and_preserves_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.data_forge import read_api

    publish = read_api.write_publish_manifest
    finalize = read_api.finalize_snapshot
    calls: list[tuple[str, object]] = []

    def _publish(**kwargs: Any) -> Path:
        calls.append(("publish", kwargs))
        return publish(**kwargs)

    def _finalize(snapshot_root: str | Path, **kwargs: Any) -> Path:
        calls.append(("finalize", (snapshot_root, kwargs)))
        return finalize(snapshot_root, **kwargs)

    monkeypatch.setattr(read_api, "write_publish_manifest", _publish)
    monkeypatch.setattr(read_api, "finalize_snapshot", _finalize)

    payload = {"fixture": "controlled", "rows": [{"metric": "income", "value": 2}]}
    binding_path = data_state_substrate_module._write_data_forge_snapshot_binding(
        workspace_dir=tmp_path / "snapshots",
        snapshot_id="fixture-snapshot",
        payload=payload,
        payload_content_hash=hashlib.sha256(b"controlled-payload").hexdigest(),
        lineage_refs=("fixture://controlled-payload",),
        claim_requirement_bindings=(),
    )

    assert data_state_substrate_module._data_forge_snapshot_role() == "domain"
    assert read_api.pipeline_binding_surface("ukraine") == ("domain", "ukraine")
    assert [kind for kind, _detail in calls] == ["publish", "finalize"]
    assert binding_path.is_file()
    snapshot_root = tmp_path / "snapshots" / "fixture-snapshot"
    publish_manifest = json.loads(
        (snapshot_root / "ukraine" / "publish" / "manifest.json").read_text(encoding="utf-8")
    )
    snapshot_manifest = json.loads(
        (snapshot_root / "snapshot_manifest.json").read_text(encoding="utf-8")
    )
    binding = json.loads(binding_path.read_text(encoding="utf-8"))

    assert publish_manifest["kind"] == "publish"
    assert publish_manifest["pipeline"] == "ukraine"
    assert snapshot_manifest["pipelines"]["ukraine"] == publish_manifest
    assert binding["bindings"][0]["role"] == "domain"
    assert binding["bindings"][0]["read_api_surface"] == "ukraine"
    assert binding["bindings"][0]["read_api_identity"] == "ukraine@fixture-snapshot"
