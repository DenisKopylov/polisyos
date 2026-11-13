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


def test_live_acquisition_replay_joins_typed_source_snapshot_and_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replay a real live fixture and refuse changed ID, selected view or parent."""
    from dataclasses import fields

    from polisyos.core import artifacts
    from polisyos.core.contracts import epoch
    from polisyos.core.contracts.fabric import DataSnapshot
    from polisyos.runtime.quality import acquisition_executor
    from tests._helpers.acquisition_epoch_production import build_production_admission_case

    case = build_production_admission_case(
        tmp_path,
        monkeypatch,
        scope_payload={"domain": "public-finance", "jurisdiction": "UA"},
        authority_purpose="candidate_simulation",
    )
    activation = acquisition_executor.admit_acquisition_with_production_semantic_epoch(
        **case.call_args, epoch_deployment=case.deployment
    )
    assert isinstance(activation, acquisition_executor.ActivatedSemanticEpochAdmissionReceipt)
    passport = acquisition_executor.AdmissionPassport.model_validate(
        epoch.load_verified_epoch_statement(
            store=case.store,
            ref=activation.passport_ref,
            expected_kind="epoch.acquisition_passport_snapshot",
        )
    )
    live = passport.live_source_execution
    assert live is not None
    snapshot_ref = live.data_snapshot_ref
    snapshot = DataSnapshot.model_validate(
        artifacts.load_core_json_artifact(case.store, snapshot_ref)
    )
    source_ref = snapshot.data_ref
    assert source_ref.artifact_id == live.normalized_data_artifact_id
    assert snapshot.evidence_ref == live.evidence_bundle_ref
    assert source_ref.manifest_profile_sha256 is not None

    def replay():
        return data_state_substrate_module._replay_acquired_observation_projection(
            case.store,
            receipt_ref=activation.overlay_admission_receipt_ref,
            passport_ref=activation.passport_ref,
            expected_source_ref=source_ref,
            activation=activation,
        )

    expected = replay()
    assert expected.variable_id == passport.variable_id
    assert expected.observations

    # The live selected record is the framed normalized result; its bytes and
    # the raw HTTP watermark are distinct. Reopen both through the Catalog owner.
    from polisyos.core.contracts.variable_binding import (
        SelectedVariableBindingRef,
        scoped_source_selection_from_passport_mapping,
    )
    from polisyos.data_forge.read_api import catalog as catalog_read_api
    from polisyos.fabric import connectors
    from polisyos.fabric.data_plane import content_sha256

    assert live.raw_artifact_ref is not None
    passport_mapping = passport.model_dump(mode="json")
    selection = scoped_source_selection_from_passport_mapping(
        passport_mapping,
        source_receipt_ref=SelectedVariableBindingRef.model_validate(
            activation.overlay_admission_receipt_ref.model_dump(mode="json")
        ),
        source_passport_ref=SelectedVariableBindingRef.model_validate(
            activation.passport_ref.model_dump(mode="json")
        ),
        source_boundary_candidate_ref=SelectedVariableBindingRef.model_validate(
            passport.semantic_boundary_candidate_ref.model_dump(mode="json")
        ),
        source_record_ref=SelectedVariableBindingRef.model_validate(
            source_ref.model_dump(mode="json")
        ),
    )

    def replay_rows(mapping: dict[str, object] | None = None) -> bytes:
        return catalog_read_api.read_scoped_measurement_source_body(
            case.store,
            passport_mapping=passport_mapping if mapping is None else mapping,
            source_selection=selection,
        )

    raw_http = case.store.get_bytes(live.raw_artifact_ref)
    row_bytes = replay_rows()
    assert "sha256:" + hashlib.sha256(raw_http).hexdigest() == passport.source_watermark
    assert "sha256:" + hashlib.sha256(row_bytes).hexdigest() == (
        passport.measured_profile.sample_content_sha256
    )
    assert raw_http != row_bytes != case.store.get_bytes(source_ref)
    assert json.loads(row_bytes)

    # Keep raw and normalized rows mutually consistent while substituting a
    # foreign indicator or ISO3 country. Neither substitution may inherit the
    # source's declared population/geography merely from matching shape.
    from polisyos.data_forge.domains.catalog.knowledge import acquisition_authority as source_owner

    for field in ("indicator", "country"):
        changed = json.loads(raw_http)
        if field == "indicator":
            changed[1][0]["indicator"]["id"] = "FOREIGN.INDICATOR"
        else:
            changed[1][0]["countryiso3code"] = "USA"
        frame = connectors.normalize_worldbank_records(
            changed[1], passport.registration.request_dataset_id
        )
        normalized = frame.to_dict(orient="records")
        if field == "indicator":
            assert normalized[0]["indicator_id"] == changed[1][0]["indicator"]["id"]
        else:
            assert changed[1][0]["country"]["id"] == json.loads(raw_http)[1][0]["country"]["id"]
            assert normalized[0]["country_code"] == changed[1][0]["countryiso3code"]
        assert not source_owner._live_normalized_coordinates_match(
            normalized,
            indicator_id=passport.registration.request_dataset_id,
            country_codes=passport.registration.country_codes,
        )

    # Both actual consumers must use the shared owner check, not merely have a
    # helper that refuses the above consistent foreign rows in isolation.
    with monkeypatch.context() as context:
        context.setattr(source_owner, "_live_normalized_coordinates_match", lambda *_a, **_k: False)
        with pytest.raises(ValueError, match="scoped_source_live_coordinate_mismatch"):
            replay_rows()
        with pytest.raises(ValueError, match="scoped_source_live_coordinate_mismatch"):
            replay()

    # A matching normalized payload cannot bypass its Fabric writer-profile
    # owner in either the shared reader or the Runtime historical consumer.
    with monkeypatch.context() as context:
        context.setattr(
            connectors, "verify_selected_cache_payload_writer_profile", lambda *_a, **_k: False
        )
        with pytest.raises(
            ValueError, match="scoped_source_live_normalized_writer_profile_mismatch"
        ):
            replay_rows()
        with pytest.raises(
            ValueError, match="scoped_source_live_normalized_writer_profile_mismatch"
        ):
            replay()

    # A different actual normalizer result must not be accepted merely because
    # the selected raw and normalized manifests and reported hashes remain valid.
    normalizer = connectors.normalize_worldbank_records

    def altered_normalization(rows, indicator):
        frame = normalizer(rows, indicator)
        frame.loc[0, "value"] = float(frame.loc[0, "value"]) + 1.0
        return frame

    with monkeypatch.context() as context:
        context.setattr(connectors, "normalize_worldbank_records", altered_normalization)
        with pytest.raises(ValueError, match="scoped_source_live_normalized_projection_mismatch"):
            replay_rows()
        with pytest.raises(ValueError, match="scoped_source_live_normalized_projection_mismatch"):
            replay()

    # Preserve the raw bytes while grafting a foreign selected manifest. Even
    # if the local evidence object's content identity is recomputed, the actual
    # raw writer profile must be re-established.
    raw_manifest = case.store.get_manifest(live.raw_artifact_ref)
    raw_options = {
        field.name: getattr(
            raw_manifest, "artifact_schema" if field.name == "schema" else field.name
        )
        for field in fields(artifacts.PutOptions)
    }
    raw_options["producer"] = artifacts.ProducerInfo(component="fixture.foreign-raw", version="1")
    foreign_raw = case.store.put_bytes(
        raw_http, artifacts.PutOptions(**raw_options), return_selected_profile=True
    )
    assert foreign_raw.artifact_id == live.raw_artifact_ref.artifact_id
    assert foreign_raw.manifest_profile_sha256 != live.raw_artifact_ref.manifest_profile_sha256
    foreign_proof = live.model_copy(update={"raw_artifact_ref": foreign_raw})
    foreign_mapping = foreign_proof.model_dump(mode="json")
    foreign_mapping["content_sha256"] = content_sha256(
        {key: value for key, value in foreign_mapping.items() if key != "content_sha256"}
    )
    with pytest.raises(RuntimeError, match="live_raw_selected_profile_drift"):
        replay_rows({**passport_mapping, "live_source_execution": foreign_mapping})

    # Perturb only the in-memory typed ID after the actual owner verification;
    # persisted receipts, selected source and snapshot remain unchanged.
    verify_owner = data_state_substrate_module._verify_historical_acquisition_activation

    def change_normalized_id(*args: Any, **kwargs: Any) -> None:
        verify_owner(*args, **kwargs)
        verified_passport = kwargs["passport"]
        assert verified_passport.live_source_execution is not None
        object.__setattr__(
            verified_passport.live_source_execution,
            "normalized_data_artifact_id",
            artifacts.ArtifactID.model_validate("sha256:" + "f" * 64),
        )

    with monkeypatch.context() as context:
        context.setattr(
            data_state_substrate_module,
            "_verify_historical_acquisition_activation",
            change_normalized_id,
        )
        with pytest.raises(DataStateSubstrateError, match="semantic_source_snapshot_mismatch"):
            replay()

    # Preserve source bytes and kind while changing the selected manifest view.
    manifest = case.store.get_manifest(source_ref)
    options = {
        field.name: getattr(manifest, "artifact_schema" if field.name == "schema" else field.name)
        for field in fields(artifacts.PutOptions)
    }
    options["producer"] = artifacts.ProducerInfo(component="fixture.foreign-view", version="1")
    foreign_ref = case.store.put_bytes(
        case.store.get_bytes(source_ref),
        artifacts.PutOptions(**options),
        return_selected_profile=True,
    )
    assert foreign_ref.artifact_id == source_ref.artifact_id
    assert foreign_ref.manifest_profile_sha256 != source_ref.manifest_profile_sha256
    read_json = artifacts.load_core_json_artifact

    def foreign_snapshot(store: object, ref: object, *args: Any, **kwargs: Any) -> Any:
        value = read_json(store, ref, *args, **kwargs)
        if ref == snapshot_ref:
            return DataSnapshot.model_validate(value).model_copy(update={"data_ref": foreign_ref})
        return value

    with monkeypatch.context() as context:
        context.setattr(artifacts, "load_core_json_artifact", foreign_snapshot)
        with pytest.raises(DataStateSubstrateError, match="semantic_source_snapshot_mismatch"):
            replay()

    # Removing the actual snapshot parent must fail closed; restore before replay.
    blob, _ = case.store._paths(snapshot_ref.artifact_id)
    removed = blob.with_suffix(".test-removed")
    blob.rename(removed)
    try:
        with pytest.raises((FileNotFoundError, ValueError)):
            replay()
    finally:
        removed.rename(blob)
    assert replay() == expected
